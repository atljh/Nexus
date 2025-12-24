"""
Telegram Client wrapper for Nexus
"""

import asyncio
from typing import Optional, Dict, Tuple, Any

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    AuthKeyUnregisteredError,
    UserDeactivatedError,
    UserDeactivatedBanError,
    SessionRevokedError,
    PhoneNumberBannedError,
)

from .session_manager import SessionManager
from .exceptions import UnauthorizedError, SessionExpiredError, ProxyError


class BaseClient:
    """
    Base Telegram client wrapper.
    Provides unified interface for Telegram operations.
    """

    DEFAULT_API_ID = 2040
    DEFAULT_API_HASH = "b18441a1ff607e10a989891a5462e627"

    def __init__(
        self,
        session_string: str,
        api_id: Optional[int] = None,
        api_hash: Optional[str] = None,
        proxy: Optional[Dict] = None,
        connection_retries: int = 5,
        request_retries: int = 5,
        timeout: int = 10,
    ):
        self.session_string = session_string
        self.api_id = api_id or self.DEFAULT_API_ID
        self.api_hash = api_hash or self.DEFAULT_API_HASH
        self.proxy = self._format_proxy(proxy) if proxy else None
        self.connection_retries = connection_retries
        self.request_retries = request_retries
        self.timeout = timeout

        self._client: Optional[TelegramClient] = None

    def _format_proxy(self, proxy: Dict) -> Tuple:
        """Format proxy dict to Telethon tuple format"""
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

    def _create_client(self) -> TelegramClient:
        """Create TelegramClient instance"""
        session = SessionManager.create_memory_session(self.session_string)

        return TelegramClient(
            session,
            self.api_id,
            self.api_hash,
            proxy=self.proxy,
            connection_retries=self.connection_retries,
            request_retries=self.request_retries,
            timeout=self.timeout,
        )

    async def __aenter__(self):
        """Async context manager entry"""
        self._client = self._create_client()
        await self._client.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self._client:
            await self._client.disconnect()
            self._client = None

    async def connect(self):
        """Connect to Telegram"""
        if not self._client:
            self._client = self._create_client()
        await self._client.connect()

    async def disconnect(self):
        """Disconnect from Telegram"""
        if self._client:
            await self._client.disconnect()
            self._client = None

    async def check_auth(self) -> bool:
        """
        Check if session is authorized.

        Returns:
            True if authorized

        Raises:
            UnauthorizedError: If not authorized
            SessionExpiredError: If session expired
        """
        if not self._client:
            raise RuntimeError("Client not connected")

        try:
            is_auth = await self._client.is_user_authorized()
            if not is_auth:
                raise UnauthorizedError("Session is not authorized")
            return True

        except (AuthKeyUnregisteredError, SessionRevokedError) as e:
            raise SessionExpiredError(f"Session expired: {e}")
        except (UserDeactivatedError, UserDeactivatedBanError, PhoneNumberBannedError) as e:
            raise UnauthorizedError(f"Account deactivated or banned: {e}")

    async def get_me(self) -> Any:
        """Get current user info"""
        if not self._client:
            raise RuntimeError("Client not connected")
        return await self._client.get_me()

    @property
    def client(self) -> TelegramClient:
        """Access underlying TelegramClient"""
        if not self._client:
            raise RuntimeError("Client not connected")
        return self._client


async def validate_session(
    session_string: str,
    proxy: Optional[Dict] = None,
    api_id: Optional[int] = None,
    api_hash: Optional[str] = None,
) -> Tuple[bool, Optional[Dict], Optional[str]]:
    """
    Validate session string and get account info.

    Args:
        session_string: Telethon session string
        proxy: Optional proxy config
        api_id: Optional API ID
        api_hash: Optional API Hash

    Returns:
        Tuple[is_valid, user_info, error_message]
    """
    try:
        client = BaseClient(
            session_string=session_string,
            api_id=api_id,
            api_hash=api_hash,
            proxy=proxy,
            connection_retries=3,
            timeout=10,
        )

        async with client:
            await client.check_auth()
            me = await client.get_me()

            user_info = {
                "telegram_id": me.id,
                "username": me.username,
                "first_name": me.first_name,
                "last_name": me.last_name,
                "phone": me.phone,
                "is_premium": getattr(me, "premium", False),
            }

            return True, user_info, None

    except (UnauthorizedError, SessionExpiredError) as e:
        return False, None, str(e)
    except Exception as e:
        return False, None, f"Connection error: {str(e)}"
