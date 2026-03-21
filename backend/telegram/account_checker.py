"""
Account checker with parallel execution and detailed status detection.
Based on GramGPT implementation.
"""
import asyncio
import json
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)

from .telegram_client import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    AuthKeyDuplicatedError,
    AuthKeyUnregisteredError,
    AuthKeyPermEmptyError,
    UserDeactivatedError,
    UserDeactivatedBanError,
    SessionRevokedError,
    SessionExpiredError as TelethonSessionExpired,
    PhoneNumberBannedError,
    FloodWaitError,
    PhoneNumberInvalidError,
)
from telethon.tl.functions.messages import GetHistoryRequest
from telethon.tl.functions.account import GetAuthorizationsRequest

from .session_manager import SessionManager
from .device_generator import OFFICIAL_APIS


class AccountStatus(str, Enum):
    UNCHECKED = "unchecked"
    CHECKING = "checking"
    VALID = "valid"
    INVALID = "invalid"
    BANNED = "banned"
    FROZEN = "frozen"
    MUTED = "muted"  # Restricted from messaging
    SPAMBLOCK = "spamblock"
    SESSION_EXPIRED = "session_expired"
    DEACTIVATED = "deactivated"
    NEEDS_REAUTH = "needs_reauth"
    CONNECTION_FAILED = "connection_failed"


@dataclass
class AccountCheckResult:
    account_id: int
    status: AccountStatus
    telegram_id: Optional[int] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    is_premium: bool = False
    spamblock: Optional[bool] = None
    flood_wait: bool = False
    error_code: Optional[str] = None
    error: Optional[str] = None


class AccountChecker:
    """Async account checker with parallel execution and detailed status detection."""

    # Use Android official API (most common, least suspicious)
    DEFAULT_API_ID = OFFICIAL_APIS["android"]["api_id"]  # 6
    DEFAULT_API_HASH = OFFICIAL_APIS["android"]["api_hash"]

    def __init__(
        self,
        max_concurrent: int = 3,
        connection_timeout: int = 30,
        delay_between: float = 2.0,
    ):
        self.max_concurrent = max_concurrent
        self.connection_timeout = connection_timeout
        self.delay_between = delay_between
        self._semaphore: Optional[asyncio.Semaphore] = None

    @staticmethod
    def _format_proxy(proxy: Optional[Dict]) -> Optional[tuple]:
        """Format proxy dict to Telethon tuple format"""
        from telegram.proxy_utils import format_proxy
        return format_proxy(proxy)

    @staticmethod
    def _normalize_device_fingerprint(device_fingerprint: Optional[Any]) -> Dict[str, Any]:
        """
        Ensure device fingerprint is a dict.
        Some legacy rows may store JSON as plain string.
        """
        if isinstance(device_fingerprint, dict):
            return device_fingerprint
        if isinstance(device_fingerprint, str):
            try:
                parsed = json.loads(device_fingerprint)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                return {}
        return {}

    @staticmethod
    def _apply_session_error(
        result: AccountCheckResult,
        error_code: str,
        error: str,
    ) -> AccountCheckResult:
        """Normalize revoked/duplicated/unregistered sessions to a stable status."""
        result.status = AccountStatus.SESSION_EXPIRED
        result.error_code = error_code
        result.error = error
        return result

    async def check_single(
        self,
        account_id: int,
        session_string: str,
        proxy: Optional[Dict] = None,
        check_spamblock: bool = False,
        unique_id: Optional[str] = None,
        api_id: Optional[int] = None,
        api_hash: Optional[str] = None,
        device_fingerprint: Optional[Dict] = None,
    ) -> AccountCheckResult:
        """
        Check a single account.

        Args:
            account_id: Database ID of the account
            session_string: Telethon session string
            proxy: Optional proxy config
            check_spamblock: Whether to check spamblock status via @SpamBot
            unique_id: Optional unique ID for consistent device fingerprint
            api_id: Optional API ID from account (uses default if not provided)
            api_hash: Optional API hash from account (uses default if not provided)
            device_fingerprint: Optional device fingerprint from account

        Returns:
            AccountCheckResult with detailed status
        """
        result = AccountCheckResult(
            account_id=account_id,
            status=AccountStatus.INVALID
        )

        # Use provided api_id/api_hash or defaults
        used_api_id = api_id or self.DEFAULT_API_ID
        used_api_hash = api_hash or self.DEFAULT_API_HASH

        client = None
        try:
            session = SessionManager.create_memory_session(session_string)
            proxy_tuple = self._format_proxy(proxy)

            # Use device fingerprint from account if provided
            # If no fingerprint — don't generate a fake one, let Telethon use its defaults
            # This prevents fingerprint mismatch for accounts imported from other clients
            client_kwargs = dict(
                proxy=proxy_tuple,
                connection_retries=3,
                timeout=self.connection_timeout,
            )

            normalized_fp = self._normalize_device_fingerprint(device_fingerprint)
            if normalized_fp.get("device_model"):
                client_kwargs["device_model"] = normalized_fp.get("device_model")
                client_kwargs["system_version"] = normalized_fp.get("system_version")
                client_kwargs["app_version"] = normalized_fp.get("app_version")
                client_kwargs["lang_code"] = normalized_fp.get("lang_code", "en")
                client_kwargs["system_lang_code"] = normalized_fp.get("system_lang_code", "en-US")

            client = TelegramClient(
                session,
                used_api_id,
                used_api_hash,
                **client_kwargs,
            )

            await client.connect()

            # Check authorization
            if not await client.is_user_authorized():
                result.status = AccountStatus.NEEDS_REAUTH
                result.error_code = "not_authorized"
                result.error = "Session requires re-authorization"
                return result

            # Get user info
            me = await client.get_me()
            result.telegram_id = me.id
            result.username = me.username
            result.first_name = me.first_name
            result.last_name = me.last_name
            result.phone = me.phone
            result.is_premium = getattr(me, "premium", False)

            # Frozen check #1 — free, from get_me()
            me_deleted = getattr(me, "deleted", False)
            if me_deleted:
                result.status = AccountStatus.FROZEN
                result.error = "Account frozen (deleted=True)"
                return result

            # Frozen check #2 — help.GetAppConfig (official Telegram API)
            # Read-only, safe for all accounts
            # Ref: https://core.telegram.org/api/auth#frozen-accounts
            try:
                from telethon.tl.functions.help import GetAppConfigRequest
                app_config_result = await client(GetAppConfigRequest(hash=0))

                freeze_since = None
                if hasattr(app_config_result, 'config'):
                    for item in app_config_result.config.value:
                        if item.key == 'freeze_since_date':
                            freeze_since = int(item.value.value)
                            break

                if freeze_since and freeze_since > 0:
                    result.status = AccountStatus.FROZEN
                    result.error = f"Account frozen since {freeze_since} (unix)"
                    return result
            except Exception as e:
                logger.debug(f"[FrozenCheck] GetAppConfig failed for account {account_id}: {e}")

            result.status = AccountStatus.VALID

            # Check spamblock if requested
            if check_spamblock:
                spamblock = await self._check_spamblock(client)
                result.spamblock = spamblock
                if spamblock:
                    result.status = AccountStatus.SPAMBLOCK

            return result

        except AuthKeyDuplicatedError as e:
            self._apply_session_error(
                result,
                "auth_key_duplicated",
                f"Session duplicated across IPs: {type(e).__name__}",
            )

        except (AuthKeyUnregisteredError, AuthKeyPermEmptyError) as e:
            self._apply_session_error(
                result,
                "auth_key_unregistered",
                f"Session expired: {type(e).__name__}",
            )

        except (SessionRevokedError, TelethonSessionExpired) as e:
            self._apply_session_error(
                result,
                "session_revoked" if isinstance(e, SessionRevokedError) else "session_expired",
                f"Session expired: {type(e).__name__}",
            )

        except UserDeactivatedError:
            result.status = AccountStatus.DEACTIVATED
            result.error_code = "deactivated"
            result.error = "Account deactivated by user"

        except (UserDeactivatedBanError, PhoneNumberBannedError) as e:
            result.status = AccountStatus.BANNED
            result.error_code = "banned"
            result.error = f"Account banned: {type(e).__name__}"

        except PhoneNumberInvalidError:
            result.status = AccountStatus.INVALID
            result.error_code = "phone_number_invalid"
            result.error = "Phone number invalid"

        except FloodWaitError as e:
            # Account is valid but rate limited
            result.status = AccountStatus.VALID
            result.flood_wait = True
            result.error_code = "flood_wait"
            result.error = f"Flood wait: {e.seconds}s"

        except ConnectionError as e:
            result.status = AccountStatus.CONNECTION_FAILED
            result.error_code = "connection_failed"
            result.error = f"Connection failed: {str(e)}"

        except asyncio.TimeoutError:
            result.status = AccountStatus.CONNECTION_FAILED
            result.error_code = "timeout"
            result.error = "Connection timeout"

        except Exception as e:
            error_str = str(e).lower()
            if "frozen" in error_str:
                result.status = AccountStatus.FROZEN
                result.error_code = "frozen"
                result.error = f"Account frozen: {str(e)}"
            elif "not authorized" in error_str or "not authorised" in error_str:
                result.status = AccountStatus.NEEDS_REAUTH
                result.error_code = "not_authorized"
                result.error = f"Session requires re-authorization: {str(e)}"
            elif (
                ("auth" in error_str or "authorization" in error_str)
                and "key" in error_str
                and (
                    "duplicat" in error_str
                    or ("different" in error_str and "ip" in error_str)
                )
            ):
                self._apply_session_error(
                    result,
                    "auth_key_duplicated",
                    f"Session duplicated across IPs: {str(e)}",
                )
            elif (
                ("auth" in error_str or "authorization" in error_str)
                and "key" in error_str
                and (
                    "unregistered" in error_str
                    or "not registered" in error_str
                    or "perm empty" in error_str
                )
            ):
                self._apply_session_error(
                    result,
                    "auth_key_unregistered",
                    f"Session expired: {str(e)}",
                )
            elif "session" in error_str and ("revok" in error_str or "terminat" in error_str):
                self._apply_session_error(
                    result,
                    "session_revoked",
                    f"Session expired: {str(e)}",
                )
            elif "session" in error_str and "expir" in error_str:
                self._apply_session_error(
                    result,
                    "session_expired",
                    f"Session expired: {str(e)}",
                )
            else:
                result.status = AccountStatus.INVALID
                result.error_code = "unknown_error"
                result.error = f"Error: {str(e)}"

        finally:
            if client:
                try:
                    await client.disconnect()
                except Exception as e:
                    logger.debug(f"Disconnect error: {e}")

        return result

    async def _check_spamblock(self, client: TelegramClient) -> bool:
        """
        Check if account has spamblock by messaging @SpamBot.

        WARNING: This sends a message to @SpamBot which may trigger
        additional restrictions. Use sparingly.

        Returns:
            True if account has spamblock
        """
        try:
            spambot = await client.get_entity("@SpamBot")

            # Send /start command
            await client.send_message(spambot, "/start")

            # Wait for response
            await asyncio.sleep(2)

            # Get response
            history = await client(GetHistoryRequest(
                peer=spambot,
                limit=1,
                offset_date=None,
                offset_id=0,
                max_id=0,
                min_id=0,
                add_offset=0,
                hash=0,
            ))

            if history.messages:
                message_text = history.messages[0].message.lower()

                # Check for "no limits" first to avoid false positives
                no_limit_keywords = [
                    "no limits",
                    "нет ограничений",
                    "your account is free",
                    "good news",
                    "no limits on your account",
                ]

                for keyword in no_limit_keywords:
                    if keyword in message_text:
                        return False

                # Check for spamblock indicators
                spamblock_keywords = [
                    "your account is limited",
                    "ваш аккаунт ограничен",
                    "account is restricted",
                    "temporarily limited",
                    "временно ограничен",
                ]

                for keyword in spamblock_keywords:
                    if keyword in message_text:
                        return True

            return False

        except Exception:
            # If we can't check, assume no spamblock
            return False

    async def check_batch(
        self,
        accounts: List[Dict[str, Any]],
        check_spamblock: bool = False,
    ) -> List[AccountCheckResult]:
        """
        Check multiple accounts in parallel.

        Args:
            accounts: List of dicts with 'id', 'session_string', optional 'proxy', 'phone',
                      'api_id', 'api_hash', 'device_fingerprint'
            check_spamblock: Whether to check spamblock for each account

        Returns:
            List of AccountCheckResult objects
        """
        self._semaphore = asyncio.Semaphore(self.max_concurrent)
        self._check_counter = 0

        async def check_with_semaphore(account_data: Dict[str, Any]) -> AccountCheckResult:
            async with self._semaphore:
                # Delay between checks to avoid triggering anti-abuse systems
                if self._check_counter > 0 and self.delay_between > 0:
                    await asyncio.sleep(self.delay_between)
                self._check_counter += 1
                # Use phone or telegram_id for consistent device fingerprint
                unique_id = (
                    account_data.get("phone") or
                    str(account_data.get("telegram_id", "")) or
                    account_data["session_string"][:32]
                )
                return await self.check_single(
                    account_id=account_data["id"],
                    session_string=account_data["session_string"],
                    proxy=account_data.get("proxy"),
                    check_spamblock=check_spamblock,
                    unique_id=unique_id,
                    # API credentials from account
                    api_id=account_data.get("api_id"),
                    api_hash=account_data.get("api_hash"),
                    # Device fingerprint from account
                    device_fingerprint=account_data.get("device_fingerprint"),
                )

        tasks = [check_with_semaphore(acc) for acc in accounts]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle any exceptions
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append(AccountCheckResult(
                    account_id=accounts[i]["id"],
                    status=AccountStatus.INVALID,
                    error=str(result)
                ))
            else:
                final_results.append(result)

        return final_results


# Singleton instance
account_checker = AccountChecker()
