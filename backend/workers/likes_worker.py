"""
Likes Worker - Executes reaction tasks using Telethon.

Uses a pre-connected client pool with round-robin rotation.
Based on tg_reacter logic: resolve → check subscription → auto-join → react.
"""

import asyncio
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
from telethon.tl.functions.messages import (
    CheckChatInviteRequest,
    ImportChatInviteRequest,
)
from telethon.tl.types import (
    ReactionEmoji,
    ChatReactionsAll,
    ChatReactionsSome,
    ChatReactionsNone,
    ChatInviteAlready,
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
    InviteHashExpiredError,
    InviteHashInvalidError,
    UserAlreadyParticipantError,
)

try:
    from telethon.errors import InviteRequestSentError
except ImportError:
    InviteRequestSentError = None

from database.database import SessionLocal
from database.models import Task, TaskLog, Account
from telegram.client import BaseClient
from telegram.exceptions import UnauthorizedError, SessionExpiredError, ProxyError
from telegram.account_metadata import (
    normalize_device_fingerprint,
    resolve_account_connection_params,
)
from utils.channel_registry import upsert_channel_membership
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


SKIP_ACCOUNT_STATUSES = {
    "banned",
    "spamblock",
    "session_expired",
    "needs_reauth",
    "invalid",
    "deactivated",
}


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
        self._flood_wait_until: Dict[int, float] = {}  # account_id -> monotonic timestamp when cooldown expires
        self._account_action_times: Dict[int, List[float]] = {}  # account_id -> list of timestamps
        self._accounts_map: Dict[int, Any] = {}  # account_id -> Account (for warming multiplier)

    @staticmethod
    def _normalize_device_fingerprint(value: Optional[Any]) -> Dict[str, Any]:
        return normalize_device_fingerprint(value)

    @staticmethod
    def _classify_connect_failure(error: Exception) -> Tuple[Optional[str], str, str]:
        message = str(error)[:300] if str(error) else type(error).__name__
        lower = message.lower()

        if isinstance(error, UnauthorizedError) or "not authorized" in lower:
            return "needs_reauth", "not_authorized", "Session is not authorized"

        if isinstance(error, SessionExpiredError):
            if "revok" in lower:
                return "session_expired", "session_revoked", message
            if "authkeyunregistered" in lower or ("key" in lower and "register" in lower):
                return "session_expired", "auth_key_unregistered", message
            return "session_expired", "session_expired", message

        if "session" in lower and ("expir" in lower or "revok" in lower):
            return "session_expired", "session_expired", message

        if isinstance(error, (ProxyError, ConnectionError, TimeoutError, OSError)):
            return "connection_failed", "connection_failed", message

        if "timeout" in lower:
            return "connection_failed", "timeout", message

        return None, "connect_failed", message

    def _record_connect_failure_log(
        self,
        db: Session,
        account_id: int,
        error_code: str,
        error_message: str,
    ) -> None:
        db.add(TaskLog(
            task_id=self.task_id,
            account_id=account_id,
            action_type="connect",
            target=None,
            success=False,
            message="Action was not executed",
            error=error_message,
            extra_data={"error_code": error_code},
        ))

    def _record_setup_failure_log(
        self,
        db: Session,
        account_id: int,
        target: Optional[str],
        error_message: str,
        *,
        extra_data: Optional[dict] = None,
    ) -> None:
        db.add(TaskLog(
            task_id=self.task_id,
            account_id=account_id,
            action_type="setup",
            target=target,
            success=False,
            message="Action was not executed",
            error=error_message,
            extra_data=extra_data,
        ))

    def _record_setup_success_log(
        self,
        db: Session,
        account_id: int,
        target: Optional[str],
        message: str,
    ) -> None:
        db.add(TaskLog(
            task_id=self.task_id,
            account_id=account_id,
            action_type="setup",
            target=target,
            success=True,
            message=message,
            error=None,
        ))

    @staticmethod
    def _membership_status_from_error(error: Optional[str]) -> Optional[str]:
        if not error:
            return None
        if "awaiting admin approval" in error.lower():
            return "pending_approval"
        return "failed"

    def _track_channel_membership(
        self,
        db: Session,
        *,
        account_id: int,
        status: str,
        target: Optional[str],
        invite_link: Optional[str] = None,
        entity: Any = None,
        error: Optional[str] = None,
    ) -> None:
        try:
            upsert_channel_membership(
                db,
                account_id=account_id,
                status=status,
                target=target,
                invite_link=invite_link,
                entity=entity,
                error=error,
                touch_last_used=status == "member",
            )
        except ValueError:
            logger.debug(
                "Account %s: skipped channel registry update for unresolved target=%s invite=%s",
                account_id,
                target,
                invite_link,
            )

    # ── Client pool management ──

    async def _connect_accounts(
        self, accounts: List[Account], db: Session, max_concurrent: int = 1
    ) -> int:
        """Pre-connect accounts in parallel. Returns count of successfully connected."""
        semaphore = asyncio.Semaphore(max_concurrent)
        connected = 0
        lock = asyncio.Lock()

        async def connect_one(account: Account):
            nonlocal connected

            if account.status in SKIP_ACCOUNT_STATUSES:
                logger.warning(f"Account {account.id}: status {account.status}, skipping")
                self._failed_accounts.add(account.id)
                async with lock:
                    self._record_connect_failure_log(
                        db, account.id,
                        f"status_{account.status}",
                        f"Account skipped by status: {account.status}",
                    )
                    db.commit()
                return

            if not account.session_string:
                logger.warning(f"Account {account.id}: no session string, skipping")
                self._failed_accounts.add(account.id)
                async with lock:
                    account.status = "invalid"
                    account.last_check_error_code = "missing_session"
                    account.last_check_error = "No session string"
                    account.last_checked_at = datetime.now(timezone.utc)
                    self._record_connect_failure_log(db, account.id, "missing_session", "No session string")
                    db.commit()
                return

            proxy = None
            if account.proxy:
                proxy = {
                    "type": account.proxy.type,
                    "host": account.proxy.host,
                    "port": account.proxy.port,
                    "username": account.proxy.username,
                    "password": account.proxy.password,
                }

            resolved_api_id, resolved_api_hash, device_fp = resolve_account_connection_params(account)

            client = None
            async with semaphore:
                # Small stagger to avoid burst connections
                await asyncio.sleep(random.uniform(0.2, 0.8))
                try:
                    client = BaseClient(
                        session_string=account.session_string,
                        api_id=resolved_api_id,
                        api_hash=resolved_api_hash,
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
                    # Pre-task proxy validation
                    if proxy:
                        proxy_test = await client._test_proxy_connection()
                        if not proxy_test.get("success"):
                            error_msg = proxy_test.get("error", "Proxy test failed")
                            logger.warning(f"Account {account.id}: proxy failed pre-check: {error_msg}")
                            self._failed_accounts.add(account.id)
                            async with lock:
                                self._record_connect_failure_log(db, account.id, "proxy_failed", error_msg)
                                db.commit()
                            return

                    await client.connect()
                    await client.check_auth()

                    # Geo validation (warning only)
                    proxy_geo = account.proxy.geo if account.proxy else None
                    geo_warnings = AccountSafetyValidator.validate_geo_match(account.geo, proxy_geo)
                    for w in geo_warnings:
                        logger.warning(f"Account {account.id}: {w}")

                    # Fingerprint validation
                    locked_fingerprint = self._normalize_device_fingerprint(account.device_fingerprint)
                    fp_valid, fp_errors = AccountSafetyValidator.validate_fingerprint(
                        device_fp, locked_fingerprint
                    )
                    if not fp_valid:
                        for e in fp_errors:
                            logger.error(f"Account {account.id}: {e}")
                        self._failed_accounts.add(account.id)
                        await client.disconnect()
                        return

                    # Lock fingerprint on first connect
                    async with lock:
                        AccountSafetyValidator.lock_fingerprint(account, device_fp, db)

                    self._clients[account.id] = client
                    async with lock:
                        connected += 1
                        # Log successful connection
                        db.add(TaskLog(
                            task_id=self.task_id,
                            account_id=account.id,
                            action_type="connect",
                            target=None,
                            success=True,
                            message="Connected",
                            error=None,
                        ))
                        db.commit()
                    logger.info(f"Account {account.id}: connected successfully")

                except Exception as e:
                    logger.warning(f"Account {account.id}: connect failed — {e}")
                    self._failed_accounts.add(account.id)
                    new_status, error_code, error_message = self._classify_connect_failure(e)
                    async with lock:
                        if new_status:
                            account.status = new_status
                        account.last_check_error_code = error_code
                        account.last_check_error = error_message
                        account.last_checked_at = datetime.now(timezone.utc)
                        self._record_connect_failure_log(db, account.id, error_code, error_message)
                        db.commit()
                    if client:
                        try:
                            await client.disconnect()
                        except Exception:
                            pass

        await asyncio.gather(*[connect_one(a) for a in accounts])
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
        """Resolve and cache entity per client. Supports @username, username, and numeric IDs."""
        if account_id in self._entities:
            return self._entities[account_id]

        client = self._clients[account_id]
        # Strip @ from numeric IDs (e.g. @-1003548071275 → -1003548071275)
        clean = channel
        if clean.startswith("@") and clean[1:].lstrip("-").isdigit():
            clean = clean[1:]
        # Support numeric channel IDs (e.g. -1003548071275 from t.me/c/ links)
        try:
            channel_id = int(clean)
            entity = await client.client.get_entity(channel_id)
        except (ValueError, TypeError):
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
        except FloodWaitError:
            raise
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

    async def _join_via_invite(
        self, account_id: int, invite_hash: str
    ) -> Tuple[bool, Optional[str], Any, bool]:
        """Join channel via invite hash.

        Returns (success, error, entity, joined_now). joined_now is True only when
        ImportChatInviteRequest actually executed; False if account was already a member.
        """
        client = self._clients[account_id]
        try:
            # Check if already a member
            invite_info = await client.client(CheckChatInviteRequest(hash=invite_hash))
            if isinstance(invite_info, ChatInviteAlready):
                return True, None, invite_info.chat, False
        except Exception:
            pass

        try:
            updates = await client.client(ImportChatInviteRequest(hash=invite_hash))
            entity = updates.chats[0] if updates.chats else None
            return True, None, entity, True
        except UserAlreadyParticipantError:
            # Already in, re-check to get entity
            try:
                invite_info = await client.client(CheckChatInviteRequest(hash=invite_hash))
                if isinstance(invite_info, ChatInviteAlready):
                    return True, None, invite_info.chat, False
            except Exception:
                pass
            return True, None, None, False
        except InviteHashExpiredError:
            return False, "Invite link expired", None, False
        except InviteHashInvalidError:
            return False, "Invite link invalid", None, False
        except ChannelPrivateError:
            return False, "Channel is private, cannot join", None, False
        except UserBannedInChannelError:
            return False, "Account banned in channel", None, False
        except ChannelsTooMuchError:
            return False, "Account joined too many channels", None, False
        except FloodWaitError:
            raise
        except Exception as e:
            err_str = str(e).lower()
            # InviteRequestSentError — channel requires admin approval
            if "inviterequestsent" in err_str or "request" in err_str and "sent" in err_str:
                return False, "Join request sent, awaiting admin approval", None, False
            return False, f"Join via invite failed: {str(e)[:50]}", None, False

    @staticmethod
    def _is_invite_target(value: Optional[str]) -> bool:
        if not value:
            return False
        return bool(re.match(r'(?:https?://)?t\.me/(?:\+|joinchat/)', value))

    async def _resolve_entity_after_invite_join(
        self,
        account_id: int,
        channel: Optional[str],
        entity: Any,
    ) -> Any:
        """Resolve the channel after a successful invite join when Telegram returned no entity."""
        if entity is not None:
            return entity

        if not channel or self._is_invite_target(channel):
            return None

        self._entities.pop(account_id, None)
        try:
            return await self._resolve_entity(account_id, channel)
        except Exception as exc:
            logger.debug(
                "Account %s: failed to resolve joined entity for %s: %s",
                account_id,
                channel,
                exc,
            )
            return None

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
            logger.warning(
                f"Account {account_id}: entity missing when sending reaction "
                f"msg_id={msg_id} reaction={reaction!r}"
            )
            return False, None, "Entity not resolved"

        logger.debug(
            f"Account {account_id}: SendReactionRequest msg_id={msg_id} "
            f"reaction={reaction!r} peer_id={entity.id}"
        )
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
            # Temporary cooldown — account will be retried after wait expires
            wait = e.seconds
            self._flood_wait_until[account_id] = time.monotonic() + wait
            logger.warning(f"FloodWait {wait}s on account {account_id} — cooldown until +{wait}s")
            return False, None, f"FloodWait: {wait}s"

        except ReactionInvalidError:
            return False, None, "Invalid reaction emoji"

        except UserBannedInChannelError:
            self._failed_accounts.add(account_id)
            return False, None, "Account banned in channel"

        except ChatWriteForbiddenError:
            self._failed_accounts.add(account_id)
            return False, None, "Account cannot react in this channel"

        except ChannelPrivateError:
            self._failed_accounts.add(account_id)
            return False, None, "Channel is private"

        except MsgIdInvalidError:
            return False, None, "Invalid message ID"

        except Exception as e:
            error_str = str(e)[:200].lower()
            # Detect spamblock patterns
            if any(p in error_str for p in ("peer_flood", "a wait of", "spam")):
                self._failed_accounts.add(account_id)
                return False, None, f"Spamblock: {str(e)[:100]}"
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
    def _parse_channel(channel: str, post_id: Optional[int] = None) -> tuple[str, Optional[int], Optional[str]]:
        """
        Parse channel input — supports @channel, username, t.me links,
        private channel links (t.me/c/ID/post), and invite links (t.me/+HASH).
        Returns (channel, post_id, invite_hash).
        """
        # Private channel format: t.me/c/CHANNEL_ID/POST_ID
        m = re.match(r'(?:https?://)?t\.me/c/(\d+)(?:/(\d+))?', channel)
        if m:
            channel_id = int(m.group(1))
            if m.group(2) and not post_id:
                post_id = int(m.group(2))
            return "-100" + str(channel_id), post_id, None

        # Invite link format: t.me/+HASH or t.me/joinchat/HASH
        m = re.match(r'(?:https?://)?t\.me/(?:\+|joinchat/)([a-zA-Z0-9_-]+)', channel)
        if m:
            return channel, post_id, m.group(1)

        # Public channel: t.me/username/POST_ID
        m = re.match(r'(?:https?://)?t\.me/([a-zA-Z0-9_]+)(?:/(\d+))?', channel)
        if m:
            channel = m.group(1)
            if m.group(2) and not post_id:
                post_id = int(m.group(2))
        return channel, post_id, None

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
            raw_channel = channel
            # Parse t.me links (e.g. https://t.me/channel/12345, t.me/c/ID/post, t.me/+HASH)
            channel, post_id, invite_hash = self._parse_channel(channel, post_id)

            # Separate invite link for private channels (t.me/c/ format)
            invite_link = config.get("invite_link", "")
            if invite_link and not invite_hash:
                _, _, invite_hash = self._parse_channel(invite_link)
                if not invite_hash:
                    # Try extracting hash directly
                    m = re.match(r'(?:https?://)?t\.me/(?:\+|joinchat/)([a-zA-Z0-9_-]+)', invite_link)
                    if m:
                        invite_hash = m.group(1)

            logger.debug(
                f"Task {self.task_id}: parsed config raw_channel={raw_channel!r} "
                f"channel={channel!r} post_id={post_id!r} "
                f"invite_link={invite_link!r} invite_hash={invite_hash!r}"
            )

            # Backward compat: old "reaction" (str) → new "reactions" (list)
            reactions = config.get("reactions")
            if not reactions:
                old_reaction = config.get("reaction", "👍")
                reactions = [REACTIONS_MAP.get(old_reaction, old_reaction)]
            else:
                reactions = [REACTIONS_MAP.get(r, r) for r in reactions]

            emoji_mode = config.get("emoji_mode", "single")
            max_concurrent = task.max_concurrent or 1

            logger.info(
                f"Starting likes task {self.task_id}: "
                f"channel={channel}, post_id={post_id}, reactions={reactions}, "
                f"emoji_mode={emoji_mode}, accounts={len(accounts)}, "
                f"total={task.total_actions}, max_concurrent={max_concurrent}"
            )

            # Phase 1: Pre-connect all accounts (parallel)
            connected = await self._connect_accounts(accounts, db, max_concurrent)
            if connected == 0:
                task.status = "failed"
                task.last_error = "All accounts failed to connect"
                db.commit()
                return

            logger.info(f"Task {self.task_id}: {connected}/{len(accounts)} accounts connected")

            try:
                # Phase 2: Resolve entity + check subscription + auto-join for each account
                resolution_errors: list[str] = []
                setup_progress = 0
                setup_total = len(accounts)
                setup_start = time.monotonic()
                last_progress_log = setup_start
                for account in accounts:
                    if account.id in self._failed_accounts:
                        logger.debug(
                            f"Task {self.task_id}: skip setup for account {account.id} "
                            f"(in _failed_accounts)"
                        )
                        continue
                    if account.id not in self._clients:
                        logger.debug(
                            f"Task {self.task_id}: skip setup for account {account.id} "
                            f"(no client)"
                        )
                        continue

                    setup_progress += 1
                    # Periodic INFO progress so file logs show liveness during long setups.
                    # Logs every 25 accounts OR every 60s of wall time, whichever comes first.
                    now = time.monotonic()
                    if (
                        setup_progress == 1
                        or setup_progress % 25 == 0
                        or now - last_progress_log >= 60
                    ):
                        elapsed = now - setup_start
                        rate = setup_progress / elapsed if elapsed > 0 else 0
                        logger.info(
                            f"Task {self.task_id}: setup progress "
                            f"{setup_progress}/{setup_total} "
                            f"(elapsed={elapsed:.0f}s, rate={rate:.2f}/s, "
                            f"flood_wait={len(self._flood_wait_until)})"
                        )
                        last_progress_log = now

                    logger.debug(
                        f"Account {account.id}: setup via "
                        f"{'invite' if invite_hash else 'public'} flow"
                    )
                    did_join = False
                    try:
                        if invite_hash:
                            # Invite link flow: join via hash, then resolve entity
                            joined, join_error, entity, did_join = await self._join_via_invite(
                                account.id, invite_hash
                            )
                            logger.debug(
                                f"Account {account.id}: _join_via_invite → "
                                f"joined={joined} error={join_error!r} "
                                f"entity={type(entity).__name__ if entity else None}"
                                f"{f' id={entity.id}' if entity is not None else ''}"
                            )
                            entity = await self._resolve_entity_after_invite_join(
                                account.id,
                                channel,
                                entity,
                            )
                            logger.debug(
                                f"Account {account.id}: after _resolve_entity_after_invite_join "
                                f"entity={type(entity).__name__ if entity else None}"
                                f"{f' id={entity.id}' if entity is not None else ''}"
                            )
                            if not joined or not entity:
                                failure_reason = join_error or "Channel entity could not be resolved after join"
                                membership_status = self._membership_status_from_error(failure_reason)
                                if membership_status:
                                    self._track_channel_membership(
                                        db,
                                        account_id=account.id,
                                        status=membership_status,
                                        target=channel,
                                        invite_link=invite_link or channel,
                                        error=failure_reason,
                                    )
                                logger.warning(
                                    f"Account {account.id}: cannot join via invite — {failure_reason}"
                                )
                                self._record_setup_failure_log(
                                    db,
                                    account.id,
                                    channel,
                                    failure_reason,
                                    extra_data={"phase": "resolve"},
                                )
                                db.commit()
                                resolution_errors.append(failure_reason)
                                self._failed_accounts.add(account.id)
                                continue
                            self._entities[account.id] = entity
                            self._track_channel_membership(
                                db,
                                account_id=account.id,
                                status="member",
                                target=channel,
                                invite_link=invite_link or channel,
                                entity=entity,
                            )
                            self._record_setup_success_log(
                                db,
                                account.id,
                                channel,
                                "Joined via invite link" if did_join else "Already subscribed",
                            )
                            db.commit()
                            # Anti-detection delay only when an actual join happened.
                            # Already-member accounts have no detection risk to spread out.
                            if did_join:
                                await asyncio.sleep(random.uniform(2, 5))
                        else:
                            # Public / numeric ID channel flow
                            entity = None
                            try:
                                entity = await self._resolve_entity(account.id, channel)
                            except ChannelPrivateError:
                                # Channel is private — no invite hash available
                                failure_reason = "Private channel requires invite link"
                                self._track_channel_membership(
                                    db,
                                    account_id=account.id,
                                    status="failed",
                                    target=channel,
                                    invite_link=invite_link or None,
                                    error=failure_reason,
                                )
                                logger.warning(
                                    f"Account {account.id}: channel private, no invite link"
                                )
                                self._record_setup_failure_log(
                                    db,
                                    account.id,
                                    channel,
                                    failure_reason,
                                    extra_data={"phase": "resolve"},
                                )
                                db.commit()
                                resolution_errors.append(failure_reason)
                                self._failed_accounts.add(account.id)
                                continue

                            is_subscribed, sub_error = await self._check_subscription(account.id, entity)

                            if sub_error == "CHANNEL_PRIVATE":
                                is_subscribed = False

                            if not is_subscribed:
                                did_join = True
                                joined, join_error = await self._join_channel(account.id, entity, channel)
                                if not joined:
                                    failure_reason = join_error or "Join failed"
                                    membership_status = self._membership_status_from_error(failure_reason) or "failed"
                                    self._track_channel_membership(
                                        db,
                                        account_id=account.id,
                                        status=membership_status,
                                        target=channel,
                                        invite_link=invite_link or None,
                                        entity=entity,
                                        error=failure_reason,
                                    )
                                    logger.warning(
                                        f"Account {account.id}: cannot join channel — {failure_reason}"
                                    )
                                    self._record_setup_failure_log(
                                        db,
                                        account.id,
                                        channel,
                                        failure_reason,
                                        extra_data={"phase": "resolve"},
                                    )
                                    db.commit()
                                    resolution_errors.append(failure_reason)
                                    self._failed_accounts.add(account.id)
                                    continue

                                # Re-resolve entity after join
                                self._entities.pop(account.id, None)
                                entity = await self._resolve_entity(account.id, channel)
                            self._track_channel_membership(
                                db,
                                account_id=account.id,
                                status="member",
                                target=channel,
                                invite_link=invite_link or None,
                                entity=entity,
                            )
                            self._record_setup_success_log(
                                db,
                                account.id,
                                channel,
                                "Joined channel" if did_join else "Already subscribed",
                            )
                            db.commit()

                            # Anti-detection delay only when an actual join happened.
                            # Already-member accounts have no detection risk to spread out.
                            if did_join:
                                await asyncio.sleep(random.uniform(2, 5))

                    except ChannelPrivateError:
                        failure_reason = "Private channel requires invite link"
                        self._track_channel_membership(
                            db,
                            account_id=account.id,
                            status="failed",
                            target=channel,
                            invite_link=invite_link or None,
                            error=failure_reason,
                        )
                        logger.warning(f"Account {account.id}: channel private")
                        self._record_setup_failure_log(
                            db,
                            account.id,
                            channel,
                            failure_reason,
                            extra_data={"phase": "resolve"},
                        )
                        db.commit()
                        resolution_errors.append(failure_reason)
                        self._failed_accounts.add(account.id)
                    except FloodWaitError as e:
                        failure_reason = f"FloodWait: {e.seconds}s"
                        logger.warning(f"Account {account.id}: FloodWait {e.seconds}s during resolve")
                        self._record_setup_failure_log(
                            db,
                            account.id,
                            channel,
                            failure_reason,
                            extra_data={"phase": "resolve"},
                        )
                        db.commit()
                        resolution_errors.append(failure_reason)
                        self._flood_wait_until[account.id] = time.monotonic() + e.seconds
                    except Exception as e:
                        failure_reason = str(e)[:200]
                        membership_status = self._membership_status_from_error(failure_reason)
                        if membership_status:
                            self._track_channel_membership(
                                db,
                                account_id=account.id,
                                status=membership_status,
                                target=channel,
                                invite_link=invite_link or None,
                                error=failure_reason,
                            )
                        logger.warning(f"Account {account.id}: resolve/join failed — {e}")
                        self._record_setup_failure_log(
                            db,
                            account.id,
                            channel,
                            failure_reason,
                            extra_data={"phase": "resolve"},
                        )
                        db.commit()
                        resolution_errors.append(failure_reason)
                        self._failed_accounts.add(account.id)

                # Check we still have active accounts (include flood-wait — they'll recover)
                active_ids = [
                    a.id for a in accounts
                    if a.id in self._clients and a.id not in self._failed_accounts
                ]
                # Also include flood-wait accounts (they are temporarily paused, not failed)
                for a in accounts:
                    if a.id in self._flood_wait_until and a.id in self._clients and a.id not in active_ids:
                        active_ids.append(a.id)
                logger.info(
                    f"Task {self.task_id}: setup complete — active={len(active_ids)} "
                    f"failed={len(self._failed_accounts)} flood_wait={len(self._flood_wait_until)} "
                    f"entities_resolved={len(self._entities)}"
                )
                if not active_ids:
                    task.status = "failed"
                    unique_resolution_errors = {error for error in resolution_errors if error}
                    if len(unique_resolution_errors) == 1:
                        task.last_error = next(iter(unique_resolution_errors))
                    else:
                        task.last_error = "All accounts failed during channel resolution"
                    db.commit()
                    return

                # Phase 3: Check available reactions (using first active account)
                first_id = active_ids[0]
                available = await self._get_available_reactions(first_id, self._entities[first_id])
                logger.debug(
                    f"Task {self.task_id}: available reactions via account {first_id} = {available!r}"
                )
                if available is not None and len(available) == 0:
                    task.status = "failed"
                    task.last_error = "Reactions are disabled in this channel"
                    db.commit()
                    return

                filtered_reactions = self._filter_reactions(reactions, available)
                logger.debug(
                    f"Task {self.task_id}: requested reactions={reactions} → "
                    f"filtered={filtered_reactions} emoji_mode={emoji_mode}"
                )
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

                # Phase 5: Send reactions in parallel batches
                completed = task.completed_actions
                failed = task.failed_actions
                done_accounts: set = set()  # accounts that already reacted
                termination_reason: Optional[str] = None
                db_lock = asyncio.Lock()
                logger.info(
                    f"Task {self.task_id}: entering reaction loop with post_id={post_id} "
                    f"total_actions={task.total_actions} starting "
                    f"completed={completed} failed={failed}"
                )
                empty_batch_ticks = 0

                async def _ensure_entity_resolved(account_id: int) -> Optional[str]:
                    """Lazy entity resolve for accounts that missed setup (e.g. FloodWait).

                    Returns None on success (entity available), or an error string for the
                    caller to skip this account this tick. On FloodWait, the account is
                    re-cooldowned via _flood_wait_until and tried again later.
                    """
                    if account_id in self._entities:
                        return None
                    try:
                        if invite_hash:
                            joined, join_err, ent, _ = await self._join_via_invite(
                                account_id, invite_hash
                            )
                            ent = await self._resolve_entity_after_invite_join(
                                account_id, channel, ent
                            )
                            if not joined or not ent:
                                self._failed_accounts.add(account_id)
                                return join_err or "Channel entity could not be resolved"
                            self._entities[account_id] = ent
                        else:
                            await self._resolve_entity(account_id, channel)
                        return None
                    except FloodWaitError as e:
                        self._flood_wait_until[account_id] = time.monotonic() + e.seconds
                        return f"FloodWait: {e.seconds}s"
                    except Exception as e:
                        self._failed_accounts.add(account_id)
                        return f"Resolve failed: {str(e)[:100]}"

                async def _process_account_reaction(account_id: int, emoji: str):
                    """Send reaction for a single account. Returns (account_id, success)."""
                    nonlocal completed, failed

                    success, message, error = await self._send_reaction(
                        account_id, post_id, emoji
                    )

                    account = self._accounts_map.get(account_id)

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

                    async with db_lock:
                        db.add(log)
                        if success:
                            completed += 1
                            task.completed_actions = completed
                            self._record_account_action(account_id)
                            if account:
                                account.last_used_at = datetime.now(timezone.utc)
                        else:
                            failed += 1
                            task.failed_actions = failed
                            if error:
                                task.last_error = error
                            # Update account status in DB for persistent errors
                            if account and error:
                                err_lower = error.lower()
                                if "banned" in err_lower:
                                    account.status = "banned"
                                elif "spamblock" in err_lower or "peer_flood" in err_lower:
                                    account.status = "spamblock"
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

                    return account_id, success

                while completed + failed < task.total_actions:
                    if cancel_event.is_set():
                        task.status = "cancelled"
                        task.completed_at = datetime.now(timezone.utc)
                        db.commit()
                        logger.info(f"Task {self.task_id} cancelled")
                        return

                    await pause_event.wait()

                    # Clear expired flood-wait cooldowns
                    now = time.monotonic()
                    expired = [aid for aid, until in self._flood_wait_until.items() if now >= until]
                    for aid in expired:
                        del self._flood_wait_until[aid]

                    # Collect a batch of available accounts (up to max_concurrent)
                    batch: List[int] = []
                    for aid in active_ids:
                        if len(batch) >= max_concurrent:
                            break
                        if (
                            aid not in self._failed_accounts
                            and aid not in done_accounts
                            and aid not in self._flood_wait_until
                            and not self._is_account_rate_limited(aid)
                        ):
                            # Lazy entity resolve. For most accounts setup already
                            # populated _entities, so this is a cheap dict check.
                            # Only accounts that hit FloodWait/error during setup
                            # (their cooldown has now expired) actually do a resolve.
                            if aid not in self._entities:
                                err = await _ensure_entity_resolved(aid)
                                if err is not None:
                                    continue
                            batch.append(aid)

                    if not batch:
                        all_exhausted = all(
                            aid in self._failed_accounts or aid in done_accounts
                            for aid in active_ids
                        )
                        if all_exhausted:
                            logger.info(f"Task {self.task_id}: all accounts exhausted")
                            termination_reason = "All eligible accounts exhausted before reaching total actions"
                            break
                        # Log WHY batch is empty (throttled: first few ticks, then every ~5 min).
                        empty_batch_ticks += 1
                        if empty_batch_ticks <= 3 or empty_batch_ticks % 5 == 0:
                            reasons: Dict[str, int] = {}
                            for aid in active_ids:
                                if aid in self._failed_accounts:
                                    reasons["failed"] = reasons.get("failed", 0) + 1
                                elif aid in done_accounts:
                                    reasons["done"] = reasons.get("done", 0) + 1
                                elif aid in self._flood_wait_until:
                                    reasons["flood_wait"] = reasons.get("flood_wait", 0) + 1
                                elif self._is_account_rate_limited(aid):
                                    reasons["rate_limited"] = reasons.get("rate_limited", 0) + 1
                                else:
                                    reasons["eligible_but_missed"] = (
                                        reasons.get("eligible_but_missed", 0) + 1
                                    )
                            logger.info(
                                f"Task {self.task_id}: empty batch (tick {empty_batch_ticks}) "
                                f"active={len(active_ids)} breakdown={reasons}"
                            )
                        # Some accounts may be in flood-wait cooldown or rate-limited — wait and retry
                        if self._flood_wait_until:
                            # Wait until earliest cooldown expires
                            earliest = min(self._flood_wait_until.values())
                            wait = max(1, earliest - time.monotonic())
                            logger.info(f"Accounts in flood-wait cooldown, waiting {wait:.0f}s")
                            await asyncio.sleep(min(wait, 60))
                        else:
                            logger.info("All accounts rate-limited, cooling down 60s")
                            await asyncio.sleep(60)
                        continue
                    empty_batch_ticks = 0

                    # Send reactions for the whole batch in parallel
                    tasks_list = []
                    for account_id in batch:
                        if completed + failed >= task.total_actions:
                            break
                        emojis = self._pick_reaction(filtered_reactions, emoji_mode, completed)
                        for emoji in emojis:
                            tasks_list.append((account_id, emoji))

                    if tasks_list:
                        results = await asyncio.gather(
                            *[_process_account_reaction(aid, em) for aid, em in tasks_list],
                            return_exceptions=True,
                        )
                        for r in results:
                            if isinstance(r, Exception):
                                logger.warning(f"Batch reaction error: {r}")
                            elif isinstance(r, tuple):
                                aid, success = r
                                if success:
                                    done_accounts.add(aid)

                    # Delay between batches
                    if completed + failed < task.total_actions:
                        delay = random.uniform(task.min_delay, task.max_delay)
                        logger.debug(f"Waiting {delay:.1f}s before next batch")
                        await asyncio.sleep(delay)

                if completed + failed >= task.total_actions:
                    task.status = "completed"
                else:
                    task.status = "failed"
                    if not task.last_error:
                        task.last_error = termination_reason or "Task stopped before reaching total actions"
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


async def start_likes_task(task_id: int, on_progress: Optional[Callable] = None) -> bool:
    """
    Helper function to start a likes task.

    Args:
        task_id: The task ID
        on_progress: Optional progress callback (task_id, completed, total, message)
    """
    from workers.task_queue import task_queue

    worker = LikesWorker(task_id=task_id, on_progress=on_progress)

    return await task_queue.submit(
        task_id=task_id,
        worker_coro=worker.execute
    )
