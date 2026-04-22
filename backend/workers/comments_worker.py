"""
Comments Worker - Executes commenting tasks using Telethon.

Uses a pre-connected client pool with round-robin rotation.
Based on tg_comments logic: resolve → check subscription → auto-join
→ join discussion group → send comment.
"""

import asyncio
import random
import logging
import re
import time
from datetime import datetime, timezone
from typing import List, Dict, Optional, Callable, Any, Set, Tuple

from sqlalchemy.orm import Session
from telethon import events
from telethon.tl.functions.channels import (
    JoinChannelRequest,
    GetFullChannelRequest,
    GetParticipantRequest,
)
from telethon.tl.functions.messages import (
    CheckChatInviteRequest,
    ImportChatInviteRequest,
)
from telethon.tl.types import ChatInviteAlready, InputPeerSelf
from telethon.errors import (
    FloodWaitError,
    ChannelPrivateError,
    UserNotParticipantError,
    ChatWriteForbiddenError,
    UserBannedInChannelError,
    ChannelsTooMuchError,
    SlowModeWaitError,
    MsgIdInvalidError,
    InviteHashExpiredError,
    InviteHashInvalidError,
    UserAlreadyParticipantError,
)

try:
    from telethon.errors import ChatGuestSendForbiddenError
except ImportError:
    ChatGuestSendForbiddenError = None

try:
    from telethon.errors import InviteRequestSentError
except ImportError:
    InviteRequestSentError = None

from database.database import SessionLocal
from database.models import (
    Task, TaskLog, Account, TargetChannel, CommentTemplate,
    AccountBlacklist, CommentHistory, AIPromptTemplate,
)
from telegram.client import BaseClient
from telegram.exceptions import UnauthorizedError, SessionExpiredError, ProxyError
from telegram.account_metadata import (
    normalize_device_fingerprint,
    resolve_account_connection_params,
)
from utils.channel_registry import upsert_channel_membership
from workers.spintax import choose_unique_variant, DEFAULT_COMMENT_TEMPLATES
from workers.shared import SendStatus, SendResult, ErrorClassifier
from workers.shared.ai_service import AIService
from workers.shared.account_safety import AccountSafetyValidator

logger = logging.getLogger(__name__)

SKIP_ACCOUNT_STATUSES = {
    "banned",
    "spamblock",
    "session_expired",
    "needs_reauth",
    "invalid",
    "deactivated",
}


class UniqueCommentGenerationError(RuntimeError):
    """Raised when a task can no longer produce a unique comment."""


class CommentsWorker:
    """
    Worker for executing commenting tasks.

    Uses a pre-connected client pool with round-robin account rotation.
    Handles auto-join channel + discussion group, SlowModeWait, blacklisting.
    """

    def __init__(
        self,
        task_id: int,
        on_progress: Optional[Callable[[int, int, int, str], Any]] = None,
    ):
        self.task_id = task_id
        self.on_progress = on_progress
        self._clients: Dict[int, BaseClient] = {}
        self._entities: Dict[Tuple[int, str], Any] = {}  # (account_id, channel) -> entity
        self._failed_accounts: set = set()
        self._flood_wait_until: Dict[int, float] = {}  # account_id -> monotonic timestamp when cooldown expires
        self._linked_chat_cache: Dict[int, Optional[int]] = {}  # channel_entity_id -> linked_chat_id
        self._account_comment_count: Dict[int, int] = {}
        self._account_action_times: Dict[int, list] = {}  # account_id -> list of timestamps
        self._blacklist_cache: Set[Tuple[int, str]] = set()
        self._ready_target_accounts: Set[Tuple[int, int]] = set()
        self._used_comment_keys: Set[str] = set()
        self._used_template_keys: Set[str] = set()
        self._ai_service: Optional[AIService] = None
        self._accounts_map: Dict[int, Any] = {}  # account_id -> Account (for warming multiplier)
        self._invite_hashes: List[str] = []  # invite hashes from config invite_links

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
        title: Optional[str] = None,
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
                title=title,
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

            proxy = self._get_proxy_dict(account)
            resolved_api_id, resolved_api_hash, device_fp = resolve_account_connection_params(account)

            client = None
            async with semaphore:
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

                    proxy_geo = account.proxy.geo if account.proxy else None
                    geo_warnings = AccountSafetyValidator.validate_geo_match(account.geo, proxy_geo)
                    for w in geo_warnings:
                        logger.warning(f"Account {account.id}: {w}")

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

                    async with lock:
                        AccountSafetyValidator.lock_fingerprint(account, device_fp, db)

                    self._clients[account.id] = client
                    async with lock:
                        connected += 1
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
        """Resolve and cache entity per (account_id, channel). Supports @username and numeric IDs."""
        key = (account_id, channel)
        if key in self._entities:
            return self._entities[key]

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
        self._entities[key] = entity
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
        except FloodWaitError:
            raise
        except Exception as e:
            return False, f"Join failed: {str(e)[:50]}"

    @staticmethod
    def _extract_invite_hash(channel: str) -> Optional[str]:
        """Extract invite hash from t.me/+HASH or t.me/joinchat/HASH links."""
        m = re.match(r'(?:https?://)?t\.me/(?:\+|joinchat/)([a-zA-Z0-9_-]+)', channel)
        return m.group(1) if m else None

    @staticmethod
    def _is_invite_target(value: Optional[str]) -> bool:
        if not value:
            return False
        return bool(re.match(r'(?:https?://)?t\.me/(?:\+|joinchat/)', value))

    async def _join_via_invite(self, account_id: int, invite_hash: str) -> Tuple[bool, Optional[str], Any]:
        """Join channel via invite hash. Returns (success, error, entity)."""
        client = self._clients[account_id]
        try:
            invite_info = await client.client(CheckChatInviteRequest(hash=invite_hash))
            if isinstance(invite_info, ChatInviteAlready):
                return True, None, invite_info.chat
        except Exception:
            pass

        try:
            updates = await client.client(ImportChatInviteRequest(hash=invite_hash))
            entity = updates.chats[0] if updates.chats else None
            return True, None, entity
        except UserAlreadyParticipantError:
            try:
                invite_info = await client.client(CheckChatInviteRequest(hash=invite_hash))
                if isinstance(invite_info, ChatInviteAlready):
                    return True, None, invite_info.chat
            except Exception:
                pass
            return True, None, None
        except InviteHashExpiredError:
            return False, "Invite link expired", None
        except InviteHashInvalidError:
            return False, "Invite link invalid", None
        except ChannelPrivateError:
            return False, "Channel is private, cannot join", None
        except UserBannedInChannelError:
            return False, "Account banned in channel", None
        except ChannelsTooMuchError:
            return False, "Account joined too many channels", None
        except FloodWaitError:
            raise
        except Exception as e:
            err_str = str(e).lower()
            if "inviterequestsent" in err_str or ("request" in err_str and "sent" in err_str):
                return False, "Join request sent, awaiting admin approval", None
            return False, f"Join via invite failed: {str(e)[:50]}", None

    async def _resolve_entity_after_invite_join(
        self,
        account_id: int,
        target_channel: Optional[str],
        entity: Any,
    ) -> Any:
        """Resolve the joined channel if invite import succeeded without returning entity."""
        if entity is not None:
            return entity

        if not target_channel or self._is_invite_target(target_channel):
            return None

        self._entities.pop((account_id, target_channel), None)
        try:
            return await self._resolve_entity(account_id, target_channel)
        except Exception as exc:
            logger.debug(
                "Account %s: failed to resolve joined entity for %s: %s",
                account_id,
                target_channel,
                exc,
            )
            return None

    async def _get_linked_chat(
        self, account_id: int, entity: Any
    ) -> Tuple[Optional[int], Optional[str]]:
        """Get linked discussion group ID for a channel.
        Returns (linked_chat_id, error). linked_chat_id is None when the channel
        has no discussion group linked OR the API call failed; in the failure case
        the error string describes the underlying cause for diagnostics."""
        entity_id = entity.id
        cache_key = (account_id, entity_id)

        # Only cache the numeric ID; each account needs its own GetFullChannelRequest
        # call to populate Telethon's internal entity cache for get_input_entity()
        if cache_key in self._linked_chat_cache:
            return self._linked_chat_cache[cache_key], None

        client = self._clients[account_id]
        try:
            full = await client.client(GetFullChannelRequest(entity))
            linked_chat_id = full.full_chat.linked_chat_id
            self._linked_chat_cache[cache_key] = linked_chat_id
            return linked_chat_id, None
        except Exception as e:
            logger.warning(f"Account {account_id}: GetFullChannelRequest failed — {e}")
            self._linked_chat_cache[cache_key] = None
            return None, f"{type(e).__name__}: {str(e)[:200]}"

    async def _join_discussion_group(self, account_id: int, linked_chat_id: int) -> Tuple[bool, Optional[str]]:
        """Join the linked discussion group by ID.
        Relies on Telethon's internal entity cache (populated by prior GetFullChannelRequest)."""
        client = self._clients[account_id]
        try:
            # Resolve via Telethon's cache (populated by GetFullChannelRequest in _get_linked_chat)
            try:
                input_entity = await client.client.get_input_entity(linked_chat_id)
            except (ValueError, TypeError):
                # Fallback: try get_entity
                try:
                    input_entity = await client.client.get_entity(linked_chat_id)
                except Exception:
                    logger.warning(f"Account {account_id}: cannot resolve discussion group {linked_chat_id}")
                    return False, f"Cannot resolve group {linked_chat_id}"

            try:
                await client.client(GetParticipantRequest(input_entity, "me"))
                return True, None  # Already joined
            except UserNotParticipantError:
                pass  # Need to join
            except Exception:
                pass  # Can't check — try joining anyway

            await client.client(JoinChannelRequest(input_entity))
            logger.info(f"Account {account_id}: joined discussion group {linked_chat_id}")
            return True, None
        except FloodWaitError:
            raise
        except Exception as e:
            logger.warning(f"Account {account_id}: discussion group {linked_chat_id} join error: {e}")
            return False, str(e)[:50]

    # ── AI Service ──

    def _init_ai_service(self, config: dict) -> None:
        """Initialize AI service from task config if enabled."""
        if not config.get("ai_enabled"):
            return
        from utils.encryption import encryption_service

        api_key = encryption_service.decrypt_safe(config.get("ai_api_key", ""))
        if not api_key:
            logger.warning("AI enabled but no API key provided, falling back to spintax")
            return
        self._ai_service = AIService(
            api_key=api_key,
            model=config.get("ai_model", "gpt-4o-mini"),
            base_url=config.get("ai_base_url", "https://api.openai.com/v1"),
        )

    # ── Target channel management ──

    async def _init_target_channels(
        self, db: Session, task: Task, channels: List[str]
    ) -> List[TargetChannel]:
        """Initialize target channels in database."""
        import re
        targets = []
        for channel in channels:
            # Strip @ from numeric channel IDs (e.g. @-1003548071275 → -1003548071275)
            if channel.startswith("@") and channel[1:].lstrip("-").isdigit():
                channel = channel[1:]
            # Private channel link: t.me/c/CHANNEL_ID/POST_ID
            m = re.match(r'(?:https?://)?t\.me/c/(\d+)(?:/\d+)?', channel)
            if m:
                channel = "-100" + m.group(1)
            # Invite link: t.me/+HASH or t.me/joinchat/HASH — keep as-is for invite flow
            elif re.match(r'(?:https?://)?t\.me/(?:\+|joinchat/)', channel):
                pass  # keep original link
            elif channel.startswith("https://t.me/") or channel.startswith("http://t.me/"):
                channel = "@" + channel.split("t.me/")[1].split("/")[0]
            elif not channel.startswith("@") and not channel.lstrip("-").isdigit():
                channel = "@" + channel

            existing = db.query(TargetChannel).filter(
                TargetChannel.task_id == task.id,
                TargetChannel.channel_username == channel
            ).first()

            if existing:
                targets.append(existing)
            else:
                target = TargetChannel(
                    task_id=task.id,
                    channel_username=channel
                )
                db.add(target)
                targets.append(target)

        db.commit()
        return targets

    async def _setup_channels_for_account(
        self, account_id: int, targets: List[TargetChannel], db: Session
    ) -> int:
        """Setup all channels for a single account: resolve, join, get discussion group.
        Returns number of channels ready for commenting."""
        ready = 0
        for target in targets:
            self._mark_target_unready_for_account(account_id, target.id)

            if self._is_blacklisted_cached(account_id, target.channel_id, target.channel_username):
                db.add(TaskLog(
                    task_id=self.task_id,
                    account_id=account_id,
                    action_type="setup",
                    target=target.channel_username,
                    success=False,
                    message="Channel blacklisted from a previous run",
                ))
                continue

            try:
                invite_hash = self._extract_invite_hash(target.channel_username)

                # Determine the best join strategy
                use_invite_hash = invite_hash  # from channel_username itself (t.me/+HASH)
                if not use_invite_hash and self._invite_hashes:
                    # Numeric -100 channel IDs need invite hash to join
                    clean_ch = target.channel_username
                    if clean_ch.startswith("@"):
                        clean_ch = clean_ch[1:]
                    if clean_ch.lstrip("-").isdigit():
                        use_invite_hash = self._invite_hashes[0]

                if use_invite_hash:
                    # Invite link flow: join via hash, then use entity from result
                    joined, join_error, entity = await self._join_via_invite(
                        account_id, use_invite_hash
                    )
                    entity = await self._resolve_entity_after_invite_join(
                        account_id,
                        target.channel_username,
                        entity,
                    )
                    if not joined or not entity:
                        membership_status = self._membership_status_from_error(join_error or "Join via invite failed")
                        if membership_status:
                            self._track_channel_membership(
                                db,
                                account_id=account_id,
                                status=membership_status,
                                target=target.channel_username,
                                invite_link=f"https://t.me/+{use_invite_hash}" if use_invite_hash else None,
                                error=join_error or "Join via invite failed",
                            )
                        logger.warning(
                            f"Account {account_id}: cannot join {target.channel_username} via invite — {join_error}"
                        )
                        continue
                    self._entities[(account_id, target.channel_username)] = entity
                    target.channel_id = entity.id
                    target.channel_title = getattr(entity, 'title', None)
                    self._track_channel_membership(
                        db,
                        account_id=account_id,
                        status="member",
                        target=target.channel_username,
                        invite_link=f"https://t.me/+{use_invite_hash}" if use_invite_hash else None,
                        entity=entity,
                        title=target.channel_title,
                    )
                    await asyncio.sleep(random.uniform(1, 3))
                else:
                    # Public channel flow: resolve → check subscription → join
                    entity = await self._resolve_entity(account_id, target.channel_username)
                    target.channel_id = entity.id
                    target.channel_title = getattr(entity, 'title', None)

                    # Check subscription
                    is_subscribed, sub_error = await self._check_subscription(account_id, entity)

                    if sub_error == "CHANNEL_PRIVATE":
                        is_subscribed = False

                    successful_invite_hash = None
                    if not is_subscribed:
                        joined, join_error = await self._join_channel(account_id, entity, target.channel_username)
                        if not joined and self._invite_hashes:
                            # Fallback: try invite links
                            for ih in self._invite_hashes:
                                joined, join_error, inv_entity = await self._join_via_invite(account_id, ih)
                                if joined:
                                    successful_invite_hash = ih
                                    if inv_entity:
                                        entity = inv_entity
                                        self._entities[(account_id, target.channel_username)] = entity
                                        target.channel_id = entity.id
                                        target.channel_title = getattr(entity, 'title', None)
                                    break
                        if not joined:
                            membership_status = self._membership_status_from_error(join_error or "Join failed") or "failed"
                            self._track_channel_membership(
                                db,
                                account_id=account_id,
                                status=membership_status,
                                target=target.channel_username,
                                invite_link=(
                                    f"https://t.me/+{successful_invite_hash or self._invite_hashes[0]}"
                                    if self._invite_hashes
                                    else None
                                ),
                                entity=entity,
                                title=target.channel_title,
                                error=join_error or "Join failed",
                            )
                            logger.warning(
                                f"Account {account_id}: cannot join {target.channel_username} — {join_error}"
                            )
                            continue

                        # Re-resolve after join to refresh the account-specific entity cache.
                        self._entities.pop((account_id, target.channel_username), None)
                        entity = await self._resolve_entity(account_id, target.channel_username)
                        target.channel_id = entity.id
                        target.channel_title = getattr(entity, 'title', None)
                        await asyncio.sleep(random.uniform(1, 3))

                    self._track_channel_membership(
                        db,
                        account_id=account_id,
                        status="member",
                        target=target.channel_username,
                        invite_link=(
                            f"https://t.me/+{successful_invite_hash or self._invite_hashes[0]}"
                            if self._invite_hashes and target.channel_username.lstrip("@").lstrip("-").isdigit()
                            else None
                        ),
                        entity=entity,
                        title=target.channel_title,
                    )

                # Get linked discussion group
                linked_chat_id, link_error = await self._get_linked_chat(account_id, entity)

                if linked_chat_id:
                    # Join discussion group (required for commenting)
                    dg_joined, dg_error = await self._join_discussion_group(account_id, linked_chat_id)
                    if dg_joined:
                        self._mark_target_ready_for_account(account_id, target.id)
                        target.can_comment = True
                        target.status = "joined"
                        target.error_message = None
                        ready += 1
                        db.add(TaskLog(
                            task_id=self.task_id,
                            account_id=account_id,
                            action_type="setup",
                            target=target.channel_username,
                            success=True,
                            message=f"Discussion group {linked_chat_id} ready",
                        ))
                    else:
                        logger.warning(
                            f"Account {account_id}: cannot join discussion group — {dg_error}"
                        )
                        if not target.can_comment:
                            target.status = "error"
                            target.error_message = f"Discussion group join failed: {dg_error}"
                        db.add(TaskLog(
                            task_id=self.task_id,
                            account_id=account_id,
                            action_type="setup",
                            target=target.channel_username,
                            success=False,
                            message=f"Discussion group join failed: {dg_error}",
                            error=f"discussion_group_id={linked_chat_id}",
                        ))
                else:
                    if not target.can_comment:
                        target.status = "cannot_comment"
                        target.error_message = link_error or "No discussion group linked"
                    db.add(TaskLog(
                        task_id=self.task_id,
                        account_id=account_id,
                        action_type="setup",
                        target=target.channel_username,
                        success=False,
                        message="No discussion group linked",
                        error=link_error,
                    ))

            except ChannelPrivateError:
                self._track_channel_membership(
                    db,
                    account_id=account_id,
                    status="failed",
                    target=target.channel_username,
                    error="Private channel requires invite link",
                )
                logger.warning(f"Account {account_id}: {target.channel_username} — channel private")
                if not target.can_comment:
                    target.status = "error"
                    target.error_message = "Private channel requires invite link"
                db.add(TaskLog(
                    task_id=self.task_id,
                    account_id=account_id,
                    action_type="setup",
                    target=target.channel_username,
                    success=False,
                    message="Private channel requires invite link",
                ))
            except FloodWaitError as e:
                logger.warning(f"Account {account_id}: FloodWait {e.seconds}s during setup — cooldown")
                self._flood_wait_until[account_id] = time.monotonic() + e.seconds
                db.add(TaskLog(
                    task_id=self.task_id,
                    account_id=account_id,
                    action_type="setup",
                    target=target.channel_username,
                    success=False,
                    message=f"FloodWait: {e.seconds}s",
                ))
                return ready
            except Exception as e:
                membership_status = self._membership_status_from_error(str(e)[:50])
                if membership_status:
                    self._track_channel_membership(
                        db,
                        account_id=account_id,
                        status=membership_status,
                        target=target.channel_username,
                        error=str(e)[:50],
                    )
                logger.warning(
                    f"Account {account_id}: {target.channel_username} setup failed — {e}"
                )
                if not target.can_comment:
                    target.status = "error"
                    target.error_message = str(e)[:200]
                db.add(TaskLog(
                    task_id=self.task_id,
                    account_id=account_id,
                    action_type="setup",
                    target=target.channel_username,
                    success=False,
                    message="Setup failed",
                    error=f"{type(e).__name__}: {str(e)[:200]}",
                ))

        db.commit()
        return ready

    # ── Account Selection (blacklist) ──

    def _load_blacklist_cache(self, db: Session, account_ids: List[int]) -> None:
        """Pre-load blacklist entries into memory cache."""
        entries = db.query(
            AccountBlacklist.account_id,
            AccountBlacklist.channel_id,
            AccountBlacklist.channel_username,
        ).filter(AccountBlacklist.account_id.in_(account_ids)).all()

        for account_id, channel_id, channel_username in entries:
            if channel_id:
                self._blacklist_cache.add((account_id, f"id:{channel_id}"))
            if channel_username:
                self._blacklist_cache.add((account_id, f"un:{channel_username}"))

    def _is_blacklisted_cached(
        self, account_id: int, channel_id: Optional[int], channel_username: Optional[str]
    ) -> bool:
        """Check blacklist using in-memory cache."""
        if channel_id and (account_id, f"id:{channel_id}") in self._blacklist_cache:
            return True
        if channel_username and (account_id, f"un:{channel_username}") in self._blacklist_cache:
            return True
        return False

    def _add_to_blacklist_cache(
        self, account_id: int, channel_id: Optional[int], channel_username: Optional[str]
    ) -> None:
        """Add entry to in-memory blacklist cache."""
        if channel_id:
            self._blacklist_cache.add((account_id, f"id:{channel_id}"))
        if channel_username:
            self._blacklist_cache.add((account_id, f"un:{channel_username}"))

    def _mark_target_ready_for_account(self, account_id: int, target_id: Optional[int]) -> None:
        if target_id is not None:
            self._ready_target_accounts.add((account_id, target_id))

    def _mark_target_unready_for_account(self, account_id: int, target_id: Optional[int]) -> None:
        if target_id is not None:
            self._ready_target_accounts.discard((account_id, target_id))

    def _is_account_ready_for_target(self, account_id: int, target_id: Optional[int]) -> bool:
        if target_id is None:
            return True
        return (account_id, target_id) in self._ready_target_accounts

    def _is_account_permanently_unavailable(self, account: Account, limit: int) -> bool:
        """Check whether an account is exhausted for the remainder of the task."""
        return (
            account.id in self._failed_accounts
            or account.id not in self._clients
            or self._account_comment_count.get(account.id, 0) >= limit
            or account.status in SKIP_ACCOUNT_STATUSES
        )

    def _is_account_temporarily_unavailable(self, account_id: int) -> bool:
        """Check whether an account may recover later in this task."""
        return account_id in self._flood_wait_until or self._is_account_rate_limited(account_id)

    def _has_immediately_available_account_for_target(
        self,
        accounts: List[Account],
        limit: int,
        target_id: Optional[int],
        channel_id: Optional[int],
        channel_username: Optional[str],
    ) -> bool:
        """Return True when an account can comment right now for this target."""
        for account in accounts:
            if self._is_account_permanently_unavailable(account, limit):
                continue
            if self._is_account_temporarily_unavailable(account.id):
                continue
            if not self._is_account_ready_for_target(account.id, target_id):
                continue
            if self._is_blacklisted_cached(account.id, channel_id, channel_username):
                continue
            return True
        return False

    def _has_recoverable_account_for_target(
        self,
        accounts: List[Account],
        limit: int,
        target_id: Optional[int],
        channel_id: Optional[int],
        channel_username: Optional[str],
    ) -> bool:
        """Return True when a target still has any non-blacklisted account left."""
        for account in accounts:
            if self._is_account_permanently_unavailable(account, limit):
                continue
            if not self._is_account_ready_for_target(account.id, target_id):
                continue
            if self._is_blacklisted_cached(account.id, channel_id, channel_username):
                continue
            return True
        return False

    def _has_recoverable_account_for_any_target(
        self,
        accounts: List[Account],
        targets: List[TargetChannel],
        limit: int,
    ) -> bool:
        """Check whether any target can still be served later by any account."""
        valid_targets = [t for t in targets if t.can_comment and t.status == "joined"]
        for target in valid_targets:
            if self._has_recoverable_account_for_target(
                accounts,
                limit,
                target.id,
                target.channel_id,
                target.channel_username,
            ):
                return True
        return False

    # ── Rate limiting ──

    # Max comments per account per hour (soft limit — skips to next account)
    MAX_ACTIONS_PER_ACCOUNT_PER_HOUR = 30

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

    def _select_account(
        self,
        accounts: List[Account],
        mode: str,
        limit: int,
        index: int,
        target_id: Optional[int] = None,
        channel_id: Optional[int] = None,
        channel_username: Optional[str] = None,
    ) -> Optional[Account]:
        """Select next account with blacklist, pool, and rate limit filtering."""
        available = []
        for a in accounts:
            if self._is_account_permanently_unavailable(a, limit):
                continue
            if self._is_account_temporarily_unavailable(a.id):
                continue
            if not self._is_account_ready_for_target(a.id, target_id):
                continue
            if self._is_blacklisted_cached(a.id, channel_id, channel_username):
                continue
            available.append(a)

        if not available:
            return None

        if mode == "round_robin":
            return available[index % len(available)]
        else:
            return random.choice(available)

    def _select_target_channel(
        self,
        targets: List[TargetChannel],
        accounts: Optional[List[Account]] = None,
        limit: Optional[int] = None,
    ) -> Optional[TargetChannel]:
        """Select a target channel that can receive comments."""
        valid = [t for t in targets if t.can_comment and t.status == "joined"]
        if accounts is not None and limit is not None:
            valid = [
                target for target in valid
                if self._has_immediately_available_account_for_target(
                    accounts,
                    limit,
                    target.id,
                    target.channel_id,
                    target.channel_username,
                )
            ]
        if not valid:
            return None
        return random.choice(valid)

    # ── Comment Generation ──

    UNIQUE_AI_ATTEMPTS = 3
    UNIQUE_TEMPLATE_ATTEMPTS = 40
    UNIQUE_VARIANT_POOL_LIMIT = 512

    @staticmethod
    def _normalize_text_key(value: Optional[str]) -> str:
        return " ".join((value or "").split()).casefold()

    @classmethod
    def _normalize_templates(cls, templates: List[str]) -> List[str]:
        normalized: List[str] = []
        seen: Set[str] = set()
        for template in templates:
            cleaned = " ".join((template or "").split())
            if not cleaned:
                continue
            key = cls._normalize_text_key(cleaned)
            if key in seen:
                continue
            seen.add(key)
            normalized.append(cleaned)
        return normalized

    def _load_used_comment_keys(self, db: Session) -> None:
        """Restore already sent comments for restarted tasks."""
        history_rows = db.query(CommentHistory.comment_text).filter(
            CommentHistory.task_id == self.task_id,
            CommentHistory.success.is_(True),
        ).all()
        for (comment_text,) in history_rows:
            key = self._normalize_text_key(comment_text)
            if key:
                self._used_comment_keys.add(key)

    def _mark_comment_used(self, comment_text: str, template_key: Optional[str] = None) -> None:
        """Mark a successfully sent comment as consumed for this task."""
        comment_key = self._normalize_text_key(comment_text)
        if comment_key:
            self._used_comment_keys.add(comment_key)
        if template_key:
            self._used_template_keys.add(template_key)

    async def _generate_comment(
        self,
        config: dict,
        templates: List[str],
        db: Session,
        post_text: str = "",
        channel_title: str = "",
    ) -> Tuple[str, bool, Optional[str]]:
        """Generate a unique comment. Returns (comment_text, is_ai_generated, template_key)."""
        if self._ai_service:
            prompt_template = None
            prompt_id = config.get("ai_prompt_id")
            if prompt_id:
                prompt = db.query(AIPromptTemplate).filter(AIPromptTemplate.id == prompt_id).first()
                if prompt:
                    prompt_template = prompt.prompt_template

            for _ in range(self.UNIQUE_AI_ATTEMPTS):
                ai_comment = await self._ai_service.generate_comment(
                    post_text=post_text,
                    channel_title=channel_title,
                    prompt_template=prompt_template,
                    temperature=config.get("ai_temperature", 0.7),
                    max_tokens=config.get("ai_max_tokens", 200),
                )
                comment_text = " ".join((ai_comment or "").split())
                if not comment_text:
                    continue
                if self._normalize_text_key(comment_text) not in self._used_comment_keys:
                    return comment_text, True, None

            logger.warning("AI generation failed, falling back to spintax")

        normalized_templates = self._normalize_templates(templates)
        if not normalized_templates:
            raise UniqueCommentGenerationError("No comment templates available")

        attempted_template_keys: Set[str] = set()
        for _ in range(max(self.UNIQUE_TEMPLATE_ATTEMPTS, len(normalized_templates) * 3)):
            unused_templates = [
                template for template in normalized_templates
                if self._normalize_text_key(template) not in self._used_template_keys
            ]
            candidate_pool = unused_templates or normalized_templates
            candidate_pool = [
                template for template in candidate_pool
                if self._normalize_text_key(template) not in attempted_template_keys
            ] or (unused_templates or normalized_templates)

            template = random.choice(candidate_pool)
            template_key = self._normalize_text_key(template)
            attempted_template_keys.add(template_key)

            comment_text = choose_unique_variant(
                template,
                self._used_comment_keys,
                limit=self.UNIQUE_VARIANT_POOL_LIMIT,
                max_random_attempts=self.UNIQUE_TEMPLATE_ATTEMPTS,
            )
            if not comment_text:
                continue
            comment_text = " ".join(comment_text.split())
            return comment_text, False, template_key

        raise UniqueCommentGenerationError("Unique comment templates exhausted")

    def _should_comment(self, post_text: str, config: dict) -> bool:
        """Decide whether to comment on a post based on config."""
        comment_mode = config.get("comment_mode", "all")

        if comment_mode == "all":
            return True

        if comment_mode == "random":
            probability = config.get("comment_probability", 0.5)
            return random.random() < probability

        if comment_mode == "keywords":
            keywords = config.get("keywords", [])
            if not keywords:
                return True
            text_lower = post_text.lower()
            return any(kw.lower() in text_lower for kw in keywords)

        return True

    # ── Send Comment ──

    async def _send_comment(
        self,
        account_id: int,
        target: TargetChannel,
        comment: str,
        post_id: Optional[int] = None,
    ) -> SendResult:
        """Send a comment using a pre-connected client from the pool."""
        client = self._clients.get(account_id)
        if not client:
            return SendResult(
                status=SendStatus.ERROR,
                message="Client not connected",
                error="Client not connected",
            )

        entity = self._entities.get((account_id, target.channel_username))
        if not entity:
            # Try to resolve on the fly
            try:
                entity = await self._resolve_entity(account_id, target.channel_username)
            except Exception:
                return SendResult(
                    status=SendStatus.ERROR,
                    message="Entity not resolved",
                    error="Entity not resolved",
                )

        try:
            # Get latest post if not specified
            if not post_id:
                async for msg in client.client.iter_messages(entity, limit=1):
                    post_id = msg.id
                    break

            if not post_id:
                return SendResult(
                    status=SendStatus.SKIP,
                    message="No posts in channel",
                    entity_id=target.channel_id,
                    entity_title=target.channel_title,
                )

            # Send comment using comment_to (simpler than GetDiscussionMessageRequest).
            # Force send_as=InputPeerSelf() so Telegram doesn't fall back to a non-self
            # default identity that can't post in the discussion group (ChatWriteForbidden).
            sent = await client.client.send_message(
                entity=entity,
                message=comment,
                comment_to=post_id,
                send_as=InputPeerSelf(),
                parse_mode=None,
            )

            return SendResult(
                status=SendStatus.OK,
                message=f"Comment sent to {target.channel_username}/{post_id}",
                entity_id=target.channel_id,
                entity_title=target.channel_title,
                sent_message=sent,
            )

        except SlowModeWaitError as e:
            return SendResult(
                status=SendStatus.SLOW_MODE,
                message=f"SlowMode: {e.seconds}s",
                error=f"SlowModeWait: {e.seconds}s",
                wait_seconds=e.seconds,
                entity_id=target.channel_id,
                entity_title=target.channel_title,
            )

        except FloodWaitError as e:
            # Temporary cooldown — account will be retried after wait expires
            wait = e.seconds
            self._flood_wait_until[account_id] = time.monotonic() + wait
            logger.warning(f"FloodWait {wait}s on account {account_id} — cooldown until +{wait}s")
            return SendResult(
                status=SendStatus.FLOOD_WAIT,
                message=f"FloodWait: {e.seconds}s",
                error=f"FloodWait: {e.seconds}s",
                wait_seconds=e.seconds,
                entity_id=target.channel_id,
                entity_title=target.channel_title,
            )

        except ChatWriteForbiddenError:
            return SendResult(
                status=SendStatus.WRITE_FORBIDDEN,
                message="Cannot comment in this channel",
                error="Chat write forbidden",
                entity_id=target.channel_id,
                entity_title=target.channel_title,
            )

        except UserBannedInChannelError:
            return SendResult(
                status=SendStatus.BANNED,
                message="Account banned in channel",
                error="Banned in channel",
                entity_id=target.channel_id,
                entity_title=target.channel_title,
            )

        except ChannelPrivateError:
            return SendResult(
                status=SendStatus.NO_ACCESS,
                message="Channel is private",
                error="Channel is private",
                entity_id=target.channel_id,
                entity_title=target.channel_title,
            )

        except MsgIdInvalidError:
            return SendResult(
                status=SendStatus.ERROR,
                message="Invalid message ID",
                error="Message ID invalid — post may not support comments",
                entity_id=target.channel_id,
                entity_title=target.channel_title,
            )

        except Exception as e:
            if ChatGuestSendForbiddenError and isinstance(e, ChatGuestSendForbiddenError):
                # Need to join the linked discussion group first, then retry once.
                logger.info(f"Account {account_id}: ChatGuestSendForbidden — joining discussion group and retrying")
                linked_chat_id, _ = await self._get_linked_chat(account_id, entity)
                if linked_chat_id:
                    dg_joined, _ = await self._join_discussion_group(account_id, linked_chat_id)
                    if dg_joined:
                        await asyncio.sleep(random.uniform(1, 2))
                        try:
                            sent = await client.client.send_message(
                                entity=entity,
                                message=comment,
                                comment_to=post_id,
                                send_as=InputPeerSelf(),
                                parse_mode=None,
                            )
                            return SendResult(
                                status=SendStatus.OK,
                                message=f"Comment sent to {target.channel_username}/{post_id}",
                                entity_id=target.channel_id,
                                entity_title=target.channel_title,
                                sent_message=sent,
                            )
                        except Exception as retry_err:
                            retry_result = ErrorClassifier.classify(retry_err)
                            retry_result.message = "Cannot comment after joining discussion group"
                            retry_result.entity_id = target.channel_id
                            retry_result.entity_title = target.channel_title
                            return retry_result

                return SendResult(
                    status=SendStatus.WRITE_FORBIDDEN,
                    message="Must join discussion group before commenting",
                    error="ChatGuestSendForbiddenError",
                    entity_id=target.channel_id,
                    entity_title=target.channel_title,
                )

            result = ErrorClassifier.classify(e)
            result.entity_id = target.channel_id
            result.entity_title = target.channel_title
            return result

    # ── Result Handling ──

    def _handle_send_result(
        self,
        db: Session,
        account: Account,
        target: TargetChannel,
        result: SendResult,
    ):
        """Handle SendResult: blacklist, update account status, pool exclusion."""
        if result.success:
            return

        # Account-level issue → exclude from pool rotation entirely
        if result.status.should_stop_task:
            self._failed_accounts.add(account.id)

        # Channel-level issue → blacklist for this channel only
        if result.status.should_blacklist_entity:
            reason = ErrorClassifier.get_blacklist_reason(result.status)
            if reason:
                AccountBlacklist.add_to_blacklist(
                    db, account.id, reason,
                    channel_id=target.channel_id,
                    channel_username=target.channel_username,
                    channel_title=target.channel_title,
                    error_message=result.error,
                )
                self._add_to_blacklist_cache(
                    account.id, target.channel_id, target.channel_username
                )
                logger.info(
                    f"Blacklisted account {account.id} for {target.channel_username}: {reason}"
                )

        # Update account DB status for account-level errors
        if result.status.should_update_account_status:
            new_status = ErrorClassifier.get_recommended_account_status(result)
            if new_status and account.status != new_status:
                logger.warning(
                    f"Account {account.id} status: {account.status} -> {new_status} "
                    f"(reason: {result.status.value})"
                )
                account.status = new_status
                db.commit()

    # ── History ──

    def _save_comment_history(
        self,
        db: Session,
        account: Account,
        target: Optional[TargetChannel],
        task_id: int,
        comment_text: str,
        post_id: Optional[int] = None,
        post_text: Optional[str] = None,
        comment_id: Optional[int] = None,
        success: bool = False,
        error_message: Optional[str] = None,
        ai_generated: bool = False,
        ai_model: Optional[str] = None,
    ):
        """Save a comment to history."""
        history = CommentHistory(
            account_id=account.id,
            task_id=task_id,
            channel_id=target.channel_id if target else None,
            channel_username=target.channel_username if target else None,
            channel_title=target.channel_title if target else None,
            post_id=post_id,
            comment_id=comment_id,
            comment_text=comment_text[:2000],
            post_text=post_text[:2000] if post_text else None,
            success=success,
            error_message=error_message,
            ai_generated=ai_generated,
            ai_model=ai_model,
        )
        db.add(history)

    # ── Helpers ──

    @staticmethod
    def _get_proxy_dict(account: Account) -> Optional[dict]:
        """Get proxy dict from account."""
        if not account.proxy:
            return None
        return {
            "type": account.proxy.type,
            "host": account.proxy.host,
            "port": account.proxy.port,
            "username": account.proxy.username,
            "password": account.proxy.password,
        }

    # ── Main execution ──

    async def execute(
        self,
        cancel_event: asyncio.Event,
        pause_event: asyncio.Event,
    ):
        """Execute the comments task."""
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

            config = task.config
            channels = config.get("channels", [])

            # Extract invite hashes from invite_links config
            raw_invite_links = config.get("invite_links", [])
            logger.info(f"Task {self.task_id}: invite_links from config = {raw_invite_links}")
            for link in raw_invite_links:
                h = self._extract_invite_hash(link)
                if h:
                    self._invite_hashes.append(h)
            logger.info(f"Task {self.task_id}: extracted invite_hashes = {self._invite_hashes}")

            comment_templates = config.get("templates", [])
            rotation_mode = config.get("rotation_mode", "random")
            comments_per_account = config.get("comments_per_account", 10)
            target_post_id = config.get("post_id")  # specific post to comment on
            mode = config.get("mode", "single")

            if not channels:
                task.status = "failed"
                task.last_error = "No target channels specified"
                db.commit()
                return

            if not comment_templates:
                comment_templates = [t["content"] for t in DEFAULT_COMMENT_TEMPLATES]

            self._init_ai_service(config)
            self._load_blacklist_cache(db, [a.id for a in accounts])
            self._load_used_comment_keys(db)

            max_concurrent = task.max_concurrent or 1

            logger.info(
                f"Starting comments task {self.task_id}: "
                f"channels={len(channels)}, accounts={len(accounts)}, "
                f"mode={mode}, rotation={rotation_mode}, "
                f"max_concurrent={max_concurrent}, "
                f"ai={'on' if self._ai_service else 'off'}"
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
                # Phase 2: Initialize target channels in DB
                target_channels = await self._init_target_channels(db, task, channels)

                # Phase 3: Setup channels for each account (resolve, join, discussion group)
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

                    await self._setup_channels_for_account(account.id, target_channels, db)

                # Check we have commentable channels
                valid_targets = [t for t in target_channels if t.can_comment and t.status == "joined"]
                if not valid_targets:
                    task.status = "failed"
                    task.last_error = "No commentable channels found (no discussion groups linked)"
                    db.commit()
                    return

                # Check we still have active accounts
                active_ids = [
                    a.id for a in accounts
                    if a.id in self._clients and a.id not in self._failed_accounts
                ]
                if not active_ids:
                    task.status = "failed"
                    task.last_error = "All accounts failed during channel setup"
                    db.commit()
                    return

                # Monitoring mode
                if mode == "monitoring":
                    await self._execute_monitoring(
                        db, task, accounts, valid_targets, config,
                        comment_templates, cancel_event, pause_event
                    )
                    return

                # Phase 4: Single (batch) mode — send comments
                completed = task.completed_actions
                failed = task.failed_actions
                account_index = 0
                termination_reason: Optional[str] = None

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
                    expired_cooldowns = [aid for aid, until in self._flood_wait_until.items() if now >= until]
                    for aid in expired_cooldowns:
                        del self._flood_wait_until[aid]

                    # Select target channel
                    target = self._select_target_channel(
                        valid_targets,
                        accounts=accounts,
                        limit=comments_per_account,
                    )
                    if not target:
                        if self._has_recoverable_account_for_any_target(
                            accounts,
                            valid_targets,
                            comments_per_account,
                        ):
                            if self._flood_wait_until:
                                earliest = min(self._flood_wait_until.values())
                                wait = max(1, earliest - time.monotonic())
                                logger.info(
                                    "No target has an immediately available account, waiting %.0fs",
                                    wait,
                                )
                                await asyncio.sleep(min(wait, 60))
                            else:
                                logger.info("All eligible accounts are rate-limited, cooling down 60s")
                                await asyncio.sleep(60)
                            continue

                        logger.warning("All accounts exhausted or blacklisted for remaining targets")
                        termination_reason = "All accounts exhausted or blacklisted for remaining targets"
                        break

                    # Select account (with blacklist + pool check)
                    account = self._select_account(
                        accounts, rotation_mode, comments_per_account,
                        account_index, target.id, target.channel_id, target.channel_username
                    )
                    account_index += 1

                    if not account:
                        if not self._has_recoverable_account_for_any_target(
                            accounts,
                            valid_targets,
                            comments_per_account,
                        ):
                            logger.warning("All accounts exhausted or blacklisted for remaining targets")
                            termination_reason = "All accounts exhausted or blacklisted for remaining targets"
                            break
                        if self._flood_wait_until:
                            earliest = min(self._flood_wait_until.values())
                            wait = max(1, earliest - time.monotonic())
                            logger.info(f"Accounts in flood-wait cooldown, waiting {wait:.0f}s")
                            await asyncio.sleep(min(wait, 60))
                        else:
                            logger.info("All accounts rate-limited, cooling down 60s")
                            await asyncio.sleep(60)
                        continue

                    # Generate comment
                    try:
                        comment_text, is_ai, template_key = await self._generate_comment(
                            config, comment_templates, db,
                            post_text="", channel_title=target.channel_title or target.channel_username
                        )
                    except UniqueCommentGenerationError as exc:
                        logger.warning("Task %s: %s", self.task_id, exc)
                        termination_reason = str(exc)
                        task.last_error = termination_reason
                        break

                    # Send comment
                    result = await self._send_comment(
                        account_id=account.id,
                        target=target,
                        comment=comment_text,
                        post_id=target_post_id,
                    )

                    # Handle result (blacklist, account status, pool exclusion)
                    self._handle_send_result(db, account, target, result)

                    # Log
                    log = TaskLog(
                        task_id=self.task_id,
                        account_id=account.id,
                        action_type="comment",
                        target=target.channel_username,
                        success=result.success,
                        message=result.message,
                        error=result.error if not result.success else None,
                        extra_data={"comment": comment_text[:100], "status": result.status.value}
                    )
                    db.add(log)

                    # Save comment history
                    self._save_comment_history(
                        db, account, target, self.task_id,
                        comment_text=comment_text,
                        post_id=None,
                        comment_id=getattr(result.sent_message, 'id', None) if result.sent_message else None,
                        success=result.success,
                        error_message=result.error if not result.success else None,
                        ai_generated=is_ai,
                        ai_model=config.get("ai_model") if is_ai else None,
                    )

                    if result.success:
                        completed += 1
                        task.completed_actions = completed
                        target.comments_sent += 1
                        self._mark_comment_used(comment_text, template_key)
                        self._account_comment_count[account.id] = \
                            self._account_comment_count.get(account.id, 0) + 1
                        self._record_account_action(account.id)
                        account.last_used_at = datetime.now(timezone.utc)
                    else:
                        failed += 1
                        task.failed_actions = failed
                        if result.error:
                            task.last_error = result.error

                        # SLOW_MODE — sleep (FloodWait handled via _flood_wait_until cooldown)
                        if result.wait_seconds and result.status == SendStatus.SLOW_MODE:
                            wait = min(result.wait_seconds, 300)
                            logger.info(f"SlowMode: sleeping {wait}s")
                            await asyncio.sleep(wait)

                    db.commit()

                    if self.on_progress:
                        try:
                            await self.on_progress(
                                self.task_id,
                                completed,
                                task.total_actions,
                                result.message or result.error or ""
                            )
                        except Exception as e:
                            logger.warning(f"Progress callback error: {e}")

                    # Delay
                    if completed + failed < task.total_actions:
                        delay = random.uniform(task.min_delay, task.max_delay)
                        await asyncio.sleep(delay)

                if completed + failed >= task.total_actions:
                    task.status = "completed"
                else:
                    task.status = "failed"
                    if not task.last_error:
                        task.last_error = termination_reason or "Task stopped before reaching total actions"
                task.completed_at = datetime.now(timezone.utc)
                db.commit()

                logger.info(f"Task {self.task_id} completed: success={completed}, failed={failed}")

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
            if self._ai_service:
                await self._ai_service.close()
            db.close()

    # ── Monitoring Mode ──

    async def _execute_monitoring(
        self,
        db: Session,
        task: Task,
        accounts: List[Account],
        valid_targets: List[TargetChannel],
        config: dict,
        comment_templates: List[str],
        cancel_event: asyncio.Event,
        pause_event: asyncio.Event,
    ):
        """Execute in monitoring mode — watch for new posts and comment in real-time.
        Uses pre-connected clients from the pool."""
        active_ids = [
            a.id for a in accounts
            if a.id in self._clients and a.id not in self._failed_accounts
        ]
        if not active_ids:
            task.status = "failed"
            task.last_error = "No valid accounts for monitoring"
            db.commit()
            return

        # Use first active client as monitor
        monitor_id = active_ids[0]
        monitor_client = self._clients[monitor_id]

        # Resolve channel entities for monitoring
        channel_entities = []
        for target in valid_targets:
            entity = self._entities.get((monitor_id, target.channel_username))
            if entity:
                channel_entities.append(entity)

        if not channel_entities:
            task.status = "failed"
            task.last_error = "Failed to resolve any channels for monitoring"
            db.commit()
            return

        seen_grouped_ids: Set[int] = set()
        completed = task.completed_actions
        rotation_mode = config.get("rotation_mode", "random")
        comments_per_account = config.get("comments_per_account", 10)
        account_index = 0
        handler_lock = asyncio.Lock()
        stop_reason: Optional[str] = None

        @monitor_client.client.on(events.NewMessage(chats=channel_entities))
        async def handler(event):
            nonlocal completed, account_index, stop_reason

            if cancel_event.is_set():
                return

            # Skip megagroup posts (comments, not channel posts)
            if event.is_group:
                return

            # Skip grouped_id duplicates (album posts)
            if event.grouped_id:
                if event.grouped_id in seen_grouped_ids:
                    return
                seen_grouped_ids.add(event.grouped_id)

            post_text = event.text or ""
            if not self._should_comment(post_text, config):
                return

            await pause_event.wait()

            async with handler_lock:
                if cancel_event.is_set():
                    return
                if task.total_actions > 0 and completed >= task.total_actions:
                    return

                # Clear expired flood-wait cooldowns
                now = time.monotonic()
                expired_cooldowns = [aid for aid, until in self._flood_wait_until.items() if now >= until]
                for aid in expired_cooldowns:
                    del self._flood_wait_until[aid]

                chat = await event.get_chat()
                channel_title = getattr(chat, 'title', '')
                channel_username = getattr(chat, 'username', '')
                if channel_username:
                    channel_username = f"@{channel_username}"

                target_obj = next(
                    (t for t in valid_targets if t.channel_id == chat.id),
                    valid_targets[0] if valid_targets else None,
                )

                # Select commenting account
                commenting_account = self._select_account(
                    accounts, rotation_mode, comments_per_account,
                    account_index,
                    target_obj.id if target_obj else None,
                    chat.id,
                    channel_username,
                )
                account_index += 1

                if not commenting_account:
                    if not self._has_recoverable_account_for_any_target(
                        accounts,
                        valid_targets,
                        comments_per_account,
                    ):
                        stop_reason = "All accounts exhausted or blacklisted for remaining targets"
                        task.last_error = stop_reason
                        db.commit()
                        cancel_event.set()
                    else:
                        logger.warning("No available account for commenting")
                    return

                try:
                    comment_text, is_ai, template_key = await self._generate_comment(
                        config, comment_templates, db,
                        post_text=post_text, channel_title=channel_title
                    )
                except UniqueCommentGenerationError as exc:
                    stop_reason = str(exc)
                    task.last_error = stop_reason
                    db.commit()
                    cancel_event.set()
                    return

                # Random delay before commenting
                delay = random.uniform(task.min_delay, task.max_delay)
                await asyncio.sleep(delay)

                # Send comment using pre-connected client
                result = await self._send_comment(
                    account_id=commenting_account.id,
                    target=target_obj,
                    comment=comment_text,
                    post_id=event.id,
                )

                # Handle result
                if target_obj:
                    self._handle_send_result(db, commenting_account, target_obj, result)

                # Save history
                self._save_comment_history(
                    db, commenting_account, target_obj, self.task_id,
                    comment_text=comment_text,
                    post_id=event.id,
                    post_text=post_text[:500],
                    comment_id=getattr(result.sent_message, 'id', None) if result.sent_message else None,
                    success=result.success,
                    error_message=result.error if not result.success else None,
                    ai_generated=is_ai,
                    ai_model=config.get("ai_model") if is_ai else None,
                )

                if result.success:
                    completed += 1
                    task.completed_actions = completed
                    if target_obj:
                        target_obj.comments_sent += 1
                    self._mark_comment_used(comment_text, template_key)
                    self._account_comment_count[commenting_account.id] = \
                        self._account_comment_count.get(commenting_account.id, 0) + 1
                    self._record_account_action(commenting_account.id)
                else:
                    task.failed_actions += 1
                    if result.error:
                        task.last_error = result.error
                    # SLOW_MODE — sleep (FloodWait handled via _flood_wait_until cooldown)
                    if result.wait_seconds and result.status == SendStatus.SLOW_MODE:
                        wait = min(result.wait_seconds, 300)
                        logger.info(f"Monitoring SlowMode: sleeping {wait}s")
                        await asyncio.sleep(wait)

                # Log
                log = TaskLog(
                    task_id=self.task_id,
                    account_id=commenting_account.id,
                    action_type="comment",
                    target=channel_username,
                    success=result.success,
                    message=result.message,
                    error=result.error if not result.success else None,
                    extra_data={
                        "comment": comment_text[:100],
                        "post_id": event.id,
                        "status": result.status.value,
                        "mode": "monitoring",
                    }
                )
                db.add(log)
                db.commit()

                if self.on_progress:
                    try:
                        await self.on_progress(
                            self.task_id, completed, task.total_actions,
                            result.message or result.error or ""
                        )
                    except Exception as e:
                        logger.warning(f"Progress callback error: {e}")

                # Check limit
                if task.total_actions > 0 and completed >= task.total_actions:
                    cancel_event.set()

        # Wait until cancelled or limit reached
        logger.info(f"Task {self.task_id}: monitoring {len(channel_entities)} channels")
        try:
            while not cancel_event.is_set():
                await asyncio.sleep(1)
        finally:
            # Remove event handler to prevent memory leak
            monitor_client.client.remove_event_handler(handler)

        if stop_reason:
            task.status = "failed"
            task.last_error = stop_reason
        else:
            task.status = "completed" if completed >= task.total_actions else "cancelled"
        task.completed_at = datetime.now(timezone.utc)
        db.commit()
        logger.info(f"Task {self.task_id} monitoring ended: {completed} comments sent")


async def start_comments_task(task_id: int, on_progress: Optional[Callable] = None) -> bool:
    """Helper function to start a comments task."""
    from workers.task_queue import task_queue

    worker = CommentsWorker(task_id=task_id, on_progress=on_progress)

    return await task_queue.submit(
        task_id=task_id,
        worker_coro=worker.execute
    )
