"""
Account checker with parallel execution and detailed status detection.
Based on GramGPT implementation.
"""
import asyncio
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    AuthKeyUnregisteredError,
    UserDeactivatedError,
    UserDeactivatedBanError,
    SessionRevokedError,
    PhoneNumberBannedError,
    FloodWaitError,
    PhoneNumberInvalidError,
)
from telethon.tl.functions.messages import GetHistoryRequest
from telethon.tl.functions.account import GetAuthorizationsRequest

from .session_manager import SessionManager


class AccountStatus(str, Enum):
    UNCHECKED = "unchecked"
    CHECKING = "checking"
    VALID = "valid"
    INVALID = "invalid"
    BANNED = "banned"
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
    error: Optional[str] = None


class AccountChecker:
    """Async account checker with parallel execution and detailed status detection."""

    DEFAULT_API_ID = 2040
    DEFAULT_API_HASH = "b18441a1ff607e10a989891a5462e627"

    def __init__(
        self,
        max_concurrent: int = 3,
        connection_timeout: int = 30,
    ):
        self.max_concurrent = max_concurrent
        self.connection_timeout = connection_timeout
        self._semaphore: Optional[asyncio.Semaphore] = None

    def _format_proxy(self, proxy: Optional[Dict]) -> Optional[tuple]:
        """Format proxy dict to Telethon tuple format"""
        if not proxy:
            return None

        import socks

        proxy_type = proxy.get("type", "socks5").lower()

        if proxy_type == "socks5":
            ptype = socks.SOCKS5
        elif proxy_type == "socks4":
            ptype = socks.SOCKS4
        elif proxy_type in ("http", "https"):
            ptype = socks.HTTP
        else:
            ptype = socks.SOCKS5

        return (
            ptype,
            proxy.get("host") or proxy.get("addr"),
            int(proxy.get("port", 1080)),
            True,  # rdns
            proxy.get("username"),
            proxy.get("password"),
        )

    async def check_single(
        self,
        account_id: int,
        session_string: str,
        proxy: Optional[Dict] = None,
        check_spamblock: bool = False,
    ) -> AccountCheckResult:
        """
        Check a single account.

        Args:
            account_id: Database ID of the account
            session_string: Telethon session string
            proxy: Optional proxy config
            check_spamblock: Whether to check spamblock status via @SpamBot

        Returns:
            AccountCheckResult with detailed status
        """
        result = AccountCheckResult(
            account_id=account_id,
            status=AccountStatus.INVALID
        )

        client = None
        try:
            session = SessionManager.create_memory_session(session_string)
            proxy_tuple = self._format_proxy(proxy)

            client = TelegramClient(
                session,
                self.DEFAULT_API_ID,
                self.DEFAULT_API_HASH,
                proxy=proxy_tuple,
                connection_retries=3,
                timeout=self.connection_timeout,
            )

            await client.connect()

            # Check authorization
            if not await client.is_user_authorized():
                result.status = AccountStatus.NEEDS_REAUTH
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
            result.status = AccountStatus.VALID

            # Check spamblock if requested
            if check_spamblock:
                spamblock = await self._check_spamblock(client)
                result.spamblock = spamblock
                if spamblock:
                    result.status = AccountStatus.SPAMBLOCK

            return result

        except (AuthKeyUnregisteredError, SessionRevokedError) as e:
            result.status = AccountStatus.SESSION_EXPIRED
            result.error = f"Session expired: {type(e).__name__}"

        except UserDeactivatedError:
            result.status = AccountStatus.DEACTIVATED
            result.error = "Account deactivated by user"

        except (UserDeactivatedBanError, PhoneNumberBannedError) as e:
            result.status = AccountStatus.BANNED
            result.error = f"Account banned: {type(e).__name__}"

        except PhoneNumberInvalidError:
            result.status = AccountStatus.INVALID
            result.error = "Phone number invalid"

        except FloodWaitError as e:
            # Account is valid but rate limited
            result.status = AccountStatus.VALID
            result.error = f"Flood wait: {e.seconds}s"

        except ConnectionError as e:
            result.status = AccountStatus.CONNECTION_FAILED
            result.error = f"Connection failed: {str(e)}"

        except asyncio.TimeoutError:
            result.status = AccountStatus.CONNECTION_FAILED
            result.error = "Connection timeout"

        except Exception as e:
            result.status = AccountStatus.INVALID
            result.error = f"Error: {str(e)}"

        finally:
            if client:
                try:
                    await client.disconnect()
                except:
                    pass

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

                # Check for spamblock indicators
                spamblock_keywords = [
                    "ограничен",
                    "restricted",
                    "limited",
                    "spam",
                    "временно",
                    "temporary",
                ]

                for keyword in spamblock_keywords:
                    if keyword in message_text:
                        return True

                # Check for "no limits" indicators
                no_limit_keywords = [
                    "no limits",
                    "нет ограничений",
                    "free",
                    "good",
                ]

                for keyword in no_limit_keywords:
                    if keyword in message_text:
                        return False

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
            accounts: List of dicts with 'id', 'session_string', and optional 'proxy'
            check_spamblock: Whether to check spamblock for each account

        Returns:
            List of AccountCheckResult objects
        """
        self._semaphore = asyncio.Semaphore(self.max_concurrent)

        async def check_with_semaphore(account_data: Dict[str, Any]) -> AccountCheckResult:
            async with self._semaphore:
                return await self.check_single(
                    account_id=account_data["id"],
                    session_string=account_data["session_string"],
                    proxy=account_data.get("proxy"),
                    check_spamblock=check_spamblock,
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
