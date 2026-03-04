"""
Likes Worker - Executes reaction tasks using Telethon.

Uses a pre-connected client pool with round-robin rotation.
Based on tg_reacter logic: resolve → check subscription → auto-join → react.
"""

import asyncio
import itertools
import random
import logging
import re
import time
from datetime import datetime, timezone
from typing import List, Dict, Optional, Callable, Any, Tuple

from sqlalchemy.orm import Session
from telethon.tl.functions.messages import SendReactionRequest
from telethon.tl.functions.channels import (
    GetFullChannelRequest,
    GetParticipantRequest,
    JoinChannelRequest,
)
from telethon.tl.types import (
    ReactionEmoji,
    ChatReactionsAll,
    ChatReactionsSome,
    ChatReactionsNone,
)
from telethon.errors import (
    FloodWaitError,
    ReactionInvalidError,
    ChatWriteForbiddenError,
    ChannelPrivateError,
    UserBannedInChannelError,
    UserNotParticipantError,
    MsgIdInvalidError,
    MessageNotModifiedError,
    ChannelsTooMuchError,
)

from database.database import SessionLocal
from database.models import Task, TaskLog, Account
from telegram.client import BaseClient
from workers.shared.account_safety import AccountSafetyValidator

logger = logging.getLogger(__name__)

# Available reactions
REACTIONS_MAP = {
    "👍": "👍",
    "thumbsup": "👍",
    "👎": "👎",
    "thumbsdown": "👎",
    "❤️": "❤",
    "heart": "❤",
    "🔥": "🔥",
    "fire": "🔥",
    "🥰": "🥰",
    "😢": "😢",
    "👏": "👏",
    "clap": "👏",
    "😁": "😁",
    "🤔": "🤔",
    "🎉": "🎉",
    "🤯": "🤯",
    "😱": "😱",
    "🤬": "🤬",
    "💩": "💩",
}


SKIP_ACCOUNT_STATUSES = {"banned", "spamblock", "session_expired", "invalid", "deactivated"}


class LikesWorker:
    """
    Worker for executing likes (reactions) tasks.

    Uses a pre-connected client pool with round-robin account rotation.
    Handles auto-join, available reactions check, and multi-emoji modes.
    """

    # Max actions per account per hour (soft limit — skips to next account)
    MAX_ACTIONS_PER_ACCOUNT_PER_HOUR = 60

    def __init__(
        self,
        task_id: int,
        on_progress: Optional[Callable[[int, int, int, str], Any]] = None,
    ):
        self.task_id = task_id
        self.on_progress = on_progress
        self._clients: Dict[int, BaseClient] = {}
        self._entities: Dict[int, Any] = {}
        self._failed_accounts: set = set()
        self._account_action_times: Dict[int, List[float]] = {}  # account_id -> list of timestamps
        self._accounts_map: Dict[int, Any] = {}  # account_id -> Account (for warming multiplier)

    # ── Client pool management ──

    async def _connect_accounts(self, accounts: List[Account], db: Session) -> int:
        """Pre-connect all accounts. Returns count of successfully connected."""
        connected = 0
        for i, account in enumerate(accounts):
            # Delay between connections to avoid suspicion
            if i > 0:
                await asyncio.sleep(random.uniform(0.5, 1.5))

            if account.status in SKIP_ACCOUNT_STATUSES:
                logger.warning(f"Account {account.id}: status {account.status}, skipping")
                self._failed_accounts.add(account.id)
                continue

            if not account.session_string:
                logger.warning(f"Account {account.id}: no session string, skipping")
                self._failed_accounts.add(account.id)
                continue

            proxy = None
            if account.proxy:
                proxy = {
                    "type": account.proxy.type,
                    "host": account.proxy.host,
                    "port": account.proxy.port,
                    "username": account.proxy.username,
                    "password": account.proxy.password,
                }

            device_fp = account.device_fingerprint or {}

            client = None
            try:
                client = BaseClient(
                    session_string=account.session_string,
                    api_id=account.api_id,
                    api_hash=account.api_hash,
                    proxy=proxy,
                    connection_retries=3,
                    timeout=15,
                    device_model=device_fp.get("device_model"),
                    system_version=device_fp.get("system_version"),
                    app_version=device_fp.get("app_version"),
                    lang_code=device_fp.get("lang_code"),
                    system_lang_code=device_fp.get("system_lang_code"),
                    unique_id=account.phone or str(account.telegram_id),
                )
                await client.connect()
                await client.check_auth()

                # Geo validation (warning only, does not block)
                proxy_geo = account.proxy.geo if account.proxy else None
                geo_warnings = AccountSafetyValidator.validate_geo_match(account.geo, proxy_geo)
                for w in geo_warnings:
                    logger.warning(f"Account {account.id}: {w}")

                # Fingerprint validation (blocks on mismatch)
                fp_valid, fp_errors = AccountSafetyValidator.validate_fingerprint(
                    device_fp, account.device_fingerprint
                )
                if not fp_valid:
                    for e in fp_errors:
                        logger.error(f"Account {account.id}: {e}")
                    self._failed_accounts.add(account.id)
                    await client.disconnect()
                    continue

                # Lock fingerprint on first connect
                AccountSafetyValidator.lock_fingerprint(account, device_fp, db)

                self._clients[account.id] = client
                connected += 1
                logger.debug(f"Account {account.id}: connected")
            except Exception as e:
                logger.warning(f"Account {account.id}: connect failed — {e}")
                self._failed_accounts.add(account.id)
                # Disconnect if client was partially connected
                if client:
                    try:
                        await client.disconnect()
                    except Exception:
                        pass

        return connected

    async def _disconnect_all(self):
        """Disconnect all clients in the pool."""
        for account_id, client in self._clients.items():
            try:
                await client.disconnect()
            except Exception as e:
                logger.debug(f"Account {account_id}: disconnect error — {e}")
        self._clients.clear()
        self._entities.clear()

    # ── Channel resolution & subscription ──

    async def _resolve_entity(self, account_id: int, channel: str) -> Any:
        """Resolve and cache entity per client."""
        if account_id in self._entities:
            return self._entities[account_id]

        client = self._clients[account_id]
        entity = await client.client.get_entity(channel)
        self._entities[account_id] = entity
        return entity

    async def _check_subscription(self, account_id: int, entity: Any) -> Tuple[bool, Optional[str]]:
        """Check if account is subscribed to channel."""
        client = self._clients[account_id]
        try:
            await client.client(GetParticipantRequest(entity, "me"))
            return True, None
        except UserNotParticipantError:
            return False, None
        except ChannelPrivateError:
            return False, "CHANNEL_PRIVATE"
        except Exception as e:
            return False, str(e)[:50]

    async def _join_channel(self, account_id: int, entity: Any, channel: str) -> Tuple[bool, Optional[str]]:
        """Try to join the channel. Returns (success, error)."""
        client = self._clients[account_id]
        try:
            await client.client(JoinChannelRequest(entity))
            return True, None
        except ChannelPrivateError:
            return False, "Channel is private, cannot join"
        except UserBannedInChannelError:
            return False, "Account banned in channel"
        except ChannelsTooMuchError:
            return False, "Account joined too many channels"
        except FloodWaitError as e:
            raise e
        except Exception as e:
            return False, f"Join failed: {str(e)[:50]}"

    # ── Available reactions check ──

    async def _get_available_reactions(self, account_id: int, entity: Any) -> Optional[List[str]]:
        """
        Get list of available reaction emojis for a channel.
        Returns None if all reactions allowed, empty list if none, or list of allowed emojis.
        """
        client = self._clients[account_id]
        try:
            result = await client.client(GetFullChannelRequest(entity))
            available = result.full_chat.available_reactions

            if isinstance(available, ChatReactionsAll):
                return None  # All reactions allowed
            elif isinstance(available, ChatReactionsSome):
                return [
                    r.emoticon for r in available.reactions
                    if isinstance(r, ReactionEmoji)
                ]
            elif isinstance(available, ChatReactionsNone):
                return []  # No reactions allowed
            else:
                return None  # Unknown type, assume all allowed
        except Exception as e:
            logger.debug(f"Cannot get available reactions: {e}")
            return None  # Assume all allowed on error

    def _filter_reactions(self, reactions: List[str], available: Optional[List[str]]) -> List[str]:
        """Filter requested reactions against available ones."""
        if available is None:
            return reactions  # All allowed
        if not available:
            return []  # None allowed
        return [r for r in reactions if r in available]

    # ── Reaction sending ──

    async def _send_reaction(
        self,
        account_id: int,
        msg_id: int,
        reaction: str,
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Send a single reaction using a pre-connected client."""
        client = self._clients[account_id]
        entity = self._entities.get(account_id)

        if not entity:
            return False, None, "Entity not resolved"

        try:
            await client.client(SendReactionRequest(
                peer=entity,
                msg_id=msg_id,
                reaction=[ReactionEmoji(emoticon=reaction)]
            ))
            return True, f"Reaction {reaction} sent", None

        except MessageNotModifiedError:
            return True, "Reaction already set", None

        except FloodWaitError as e:
            logger.warning(f"FloodWait {e.seconds}s on account {account_id} — quarantining")
            self._failed_accounts.add(account_id)
            return False, None, f"FloodWait: {e.seconds}s (account quarantined)"

        except ReactionInvalidError:
            return False, None, "Invalid reaction emoji"

        except (ChatWriteForbiddenError, UserBannedInChannelError):
            self._failed_accounts.add(account_id)
            return False, None, "Account cannot react in this channel"

        except ChannelPrivateError:
            self._failed_accounts.add(account_id)
            return False, None, "Channel is private"

        except MsgIdInvalidError:
            return False, None, "Invalid message ID"

        except Exception as e:
            logger.warning(f"Reaction error on account {account_id}: {e}")
            return False, None, str(e)[:100]

    # ── Rate limiting ──

    def _is_account_rate_limited(self, account_id: int) -> bool:
        """Check if account exceeded hourly action limit (adjusted by warming multiplier)."""
        now = time.monotonic()
        times = self._account_action_times.get(account_id, [])
        # Purge entries older than 1 hour
        times = [t for t in times if now - t < 3600]
        self._account_action_times[account_id] = times

        account = self._accounts_map.get(account_id)
        if account:
            multiplier = AccountSafetyValidator.get_warming_multiplier(account)
            effective_limit = int(self.MAX_ACTIONS_PER_ACCOUNT_PER_HOUR * multiplier)
        else:
            effective_limit = self.MAX_ACTIONS_PER_ACCOUNT_PER_HOUR

        return len(times) >= effective_limit

    def _record_account_action(self, account_id: int) -> None:
        """Record an action timestamp for rate limiting."""
        self._account_action_times.setdefault(account_id, []).append(time.monotonic())

    # ── Emoji mode helpers ──

    def _pick_reaction(self, reactions: List[str], emoji_mode: str, action_index: int) -> List[str]:
        """
        Pick reaction(s) based on emoji_mode.
        Returns list of emojis to send for this action.
        - single: first emoji
        - random: random one
        - all: all emojis (each as separate action)
        """
        if emoji_mode == "random":
            return [random.choice(reactions)]
        elif emoji_mode == "all":
            return reactions  # caller will iterate
        else:  # single
            return [reactions[0]]

    # ── Link parsing ──

    @staticmethod
    def _parse_channel(channel: str, post_id: Optional[int] = None) -> tuple[str, Optional[int]]:
        """
        Parse channel input — supports @channel, username, and t.me links.
        Returns (channel, post_id).
        """
        m = re.match(r'(?:https?://)?t\.me/([a-zA-Z0-9_]+)(?:/(\d+))?', channel)
        if m:
            channel = m.group(1)
            if m.group(2) and not post_id:
                post_id = int(m.group(2))
        return channel, post_id

    # ── Main execution ──

    async def execute(
        self,
        cancel_event: asyncio.Event,
        pause_event: asyncio.Event,
    ):
        """Execute the likes task."""
        db = SessionLocal()
        try:
            task = db.query(Task).filter(Task.id == self.task_id).first()
            if not task:
                logger.error(f"Task {self.task_id} not found")
                return

            if task.status != "running":
                task.status = "running"
                task.started_at = datetime.now(timezone.utc)
                db.commit()

            accounts = list(task.accounts)
            if not accounts:
                task.status = "failed"
                task.last_error = "No accounts assigned to task"
                db.commit()
                return

            # Build accounts map for warming multiplier lookups
            self._accounts_map = {a.id: a for a in accounts}

            # Parse config
            config = task.config
            channel = config.get("channel", "")
            post_id = config.get("post_id")
            # Parse t.me links (e.g. https://t.me/channel/12345)
            channel, post_id = self._parse_channel(channel, post_id)

            # Backward compat: old "reaction" (str) → new "reactions" (list)
            reactions = config.get("reactions")
            if not reactions:
                old_reaction = config.get("reaction", "👍")
                reactions = [REACTIONS_MAP.get(old_reaction, old_reaction)]
            else:
                reactions = [REACTIONS_MAP.get(r, r) for r in reactions]

            emoji_mode = config.get("emoji_mode", "single")

            logger.info(
                f"Starting likes task {self.task_id}: "
                f"channel={channel}, post_id={post_id}, reactions={reactions}, "
                f"emoji_mode={emoji_mode}, accounts={len(accounts)}, total={task.total_actions}"
            )

            # Phase 1: Pre-connect all accounts
            connected = await self._connect_accounts(accounts, db)
            if connected == 0:
                task.status = "failed"
                task.last_error = "All accounts failed to connect"
                db.commit()
                return

            logger.info(f"Task {self.task_id}: {connected}/{len(accounts)} accounts connected")

            try:
                # Phase 2: Resolve entity + check subscription + auto-join for each account
                setup_index = 0
                for account in accounts:
                    if account.id in self._failed_accounts:
                        continue
                    if account.id not in self._clients:
                        continue

                    # Delay between account setups to avoid mass-join detection
                    if setup_index > 0:
                        await asyncio.sleep(random.uniform(1, 3))
                    setup_index += 1

                    try:
                        # Resolve entity
                        entity = await self._resolve_entity(account.id, channel)

                        # Check subscription
                        is_subscribed, sub_error = await self._check_subscription(account.id, entity)

                        if sub_error == "CHANNEL_PRIVATE":
                            # Try joining anyway
                            is_subscribed = False

                        if not is_subscribed:
                            joined, join_error = await self._join_channel(account.id, entity, channel)
                            if not joined:
                                logger.warning(
                                    f"Account {account.id}: cannot join channel — {join_error}"
                                )
                                self._failed_accounts.add(account.id)
                                continue

                            # Re-resolve entity after join
                            self._entities.pop(account.id, None)
                            entity = await self._resolve_entity(account.id, channel)

                            # Delay after join
                            await asyncio.sleep(random.uniform(2, 5))

                    except ChannelPrivateError:
                        logger.warning(f"Account {account.id}: channel private")
                        self._failed_accounts.add(account.id)
                    except FloodWaitError as e:
                        logger.warning(f"Account {account.id}: FloodWait {e.seconds}s during resolve")
                        self._failed_accounts.add(account.id)
                    except Exception as e:
                        logger.warning(f"Account {account.id}: resolve/join failed — {e}")
                        self._failed_accounts.add(account.id)

                # Check we still have active accounts
                active_ids = [
                    a.id for a in accounts
                    if a.id in self._clients and a.id not in self._failed_accounts
                ]
                if not active_ids:
                    task.status = "failed"
                    task.last_error = "All accounts failed during channel resolution"
                    db.commit()
                    return

                # Phase 3: Check available reactions (using first active account)
                first_id = active_ids[0]
                available = await self._get_available_reactions(first_id, self._entities[first_id])
                if available is not None and len(available) == 0:
                    task.status = "failed"
                    task.last_error = "Reactions are disabled in this channel"
                    db.commit()
                    return

                filtered_reactions = self._filter_reactions(reactions, available)
                if not filtered_reactions:
                    task.status = "failed"
                    task.last_error = f"Requested reactions not available in channel. Available: {available}"
                    db.commit()
                    return

                # Phase 4: Get message ID
                if not post_id:
                    # Get latest post using first active client
                    client = self._clients[first_id]
                    entity = self._entities[first_id]
                    async for msg in client.client.iter_messages(entity, limit=1):
                        post_id = msg.id
                        break
                    else:
                        task.status = "failed"
                        task.last_error = "No messages found in channel"
                        db.commit()
                        return

                # Phase 5: Send reactions with round-robin
                completed = task.completed_actions
                failed = task.failed_actions
                done_accounts: set = set()  # accounts that already reacted
                account_cycle = itertools.cycle(active_ids)

                while completed + failed < task.total_actions:
                    if cancel_event.is_set():
                        task.status = "cancelled"
                        task.completed_at = datetime.now(timezone.utc)
                        db.commit()
                        logger.info(f"Task {self.task_id} cancelled")
                        return

                    await pause_event.wait()

                    # Find next available account (skip failed, done, rate-limited)
                    account_id = None
                    for _ in range(len(active_ids)):
                        candidate = next(account_cycle)
                        if (
                            candidate not in self._failed_accounts
                            and candidate not in done_accounts
                            and not self._is_account_rate_limited(candidate)
                        ):
                            account_id = candidate
                            break

                    if account_id is None:
                        # No available account right now
                        all_exhausted = all(
                            aid in self._failed_accounts or aid in done_accounts
                            for aid in active_ids
                        )
                        if all_exhausted:
                            logger.info(f"Task {self.task_id}: all accounts exhausted")
                            break
                        # Some accounts are just rate-limited — wait and retry
                        logger.info("All accounts rate-limited, cooling down 60s")
                        await asyncio.sleep(60)
                        continue

                    # Pick reaction(s) for this action
                    emojis = self._pick_reaction(filtered_reactions, emoji_mode, completed)
                    account_had_success = False

                    for emoji in emojis:
                        if completed + failed >= task.total_actions:
                            break
                        if account_id in self._failed_accounts:
                            break

                        success, message, error = await self._send_reaction(
                            account_id, post_id, emoji
                        )

                        # Find account for log
                        account = next((a for a in accounts if a.id == account_id), None)

                        log = TaskLog(
                            task_id=self.task_id,
                            account_id=account_id,
                            action_type="reaction",
                            target=f"{channel}/{post_id}",
                            success=success,
                            message=message,
                            error=error,
                            extra_data={"reaction": emoji}
                        )
                        db.add(log)

                        if success:
                            completed += 1
                            task.completed_actions = completed
                            self._record_account_action(account_id)
                            account_had_success = True
                            if account:
                                account.last_used_at = datetime.now(timezone.utc)
                        else:
                            failed += 1
                            task.failed_actions = failed
                            if error:
                                task.last_error = error

                        db.commit()

                        if self.on_progress:
                            try:
                                await self.on_progress(
                                    self.task_id,
                                    completed,
                                    task.total_actions,
                                    message or error or ""
                                )
                            except Exception as e:
                                logger.warning(f"Progress callback error: {e}")

                    # Mark account as done after processing all emojis
                    if account_had_success:
                        done_accounts.add(account_id)

                    # Delay between actions
                    if completed + failed < task.total_actions:
                        delay = random.uniform(task.min_delay, task.max_delay)
                        logger.debug(f"Waiting {delay:.1f}s before next action")
                        await asyncio.sleep(delay)

                # Task completed
                task.status = "completed"
                task.completed_at = datetime.now(timezone.utc)
                db.commit()

                logger.info(
                    f"Task {self.task_id} completed: "
                    f"success={completed}, failed={failed}"
                )

            finally:
                await self._disconnect_all()

        except Exception as e:
            logger.exception(f"Task {self.task_id} failed with error: {e}")
            try:
                task = db.query(Task).filter(Task.id == self.task_id).first()
                if task:
                    task.status = "failed"
                    task.last_error = str(e)
                    task.completed_at = datetime.now(timezone.utc)
                    db.commit()
            except Exception as e:
                logger.debug(f"Task cleanup error: {e}")
            await self._disconnect_all()
        finally:
            db.close()


async def start_likes_task(task_id: int, on_progress: Optional[Callable] = None):
    """
    Helper function to start a likes task.

    Args:
        task_id: The task ID
        on_progress: Optional progress callback (task_id, completed, total, message)
    """
    from workers.task_queue import task_queue

    worker = LikesWorker(task_id=task_id, on_progress=on_progress)

    await task_queue.submit(
        task_id=task_id,
        worker_coro=worker.execute
    )
