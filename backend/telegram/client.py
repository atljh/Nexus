"""
Telegram Client wrapper for Nexus
"""

import asyncio
import logging
from typing import Optional, Dict, Tuple, Any

logger = logging.getLogger(__name__)

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    AuthKeyUnregisteredError,
    AuthKeyDuplicatedError,
    AuthKeyPermEmptyError,
    UserDeactivatedError,
    UserDeactivatedBanError,
    SessionRevokedError,
    SessionExpiredError as TelethonSessionExpired,
    PhoneNumberBannedError,
    FloodWaitError,
)

from .session_manager import SessionManager
from .exceptions import UnauthorizedError, SessionExpiredError, ProxyError
from .device_generator import (
    generate_device_fingerprint,
    generate_fingerprint_for_api,
    detect_platform_from_api_id,
    OFFICIAL_APIS,
)


class BaseClient:
    """
    Base Telegram client wrapper.
    Provides unified interface for Telegram operations.
    Uses device fingerprinting to emulate real devices.
    """

    # Default to Android official API (most common)
    DEFAULT_API_ID = OFFICIAL_APIS["android"]["api_id"]  # 6
    DEFAULT_API_HASH = OFFICIAL_APIS["android"]["api_hash"]

    def __init__(
        self,
        session_string: str,
        api_id: Optional[int] = None,
        api_hash: Optional[str] = None,
        proxy: Optional[Dict] = None,
        connection_retries: int = 5,
        request_retries: int = 5,
        timeout: int = 10,
        # Device fingerprint parameters
        device_model: Optional[str] = None,
        system_version: Optional[str] = None,
        app_version: Optional[str] = None,
        lang_code: Optional[str] = None,
        system_lang_code: Optional[str] = None,
        unique_id: Optional[str] = None,  # For consistent fingerprint generation
    ):
        self.session_string = session_string
        self.api_id = api_id or self.DEFAULT_API_ID
        self.api_hash = api_hash or self.DEFAULT_API_HASH
        self.proxy_dict = proxy
        self.proxy = self._format_proxy(proxy) if proxy else None
        self.connection_retries = connection_retries
        self.request_retries = request_retries
        self.timeout = timeout

        # Generate device fingerprint if not provided
        self._setup_device_fingerprint(
            device_model=device_model,
            system_version=system_version,
            app_version=app_version,
            lang_code=lang_code,
            system_lang_code=system_lang_code,
            unique_id=unique_id,
        )

        self._client: Optional[TelegramClient] = None

    def _setup_device_fingerprint(
        self,
        device_model: Optional[str] = None,
        system_version: Optional[str] = None,
        app_version: Optional[str] = None,
        lang_code: Optional[str] = None,
        system_lang_code: Optional[str] = None,
        unique_id: Optional[str] = None,
    ):
        """
        Setup device fingerprint parameters.

        If explicit params provided - use them.
        Otherwise generate consistent fingerprint based on unique_id or session hash.
        """
        if all([device_model, system_version, app_version]):
            # Use provided device params
            self.device_model = device_model
            self.system_version = system_version
            self.app_version = app_version
            self.lang_code = lang_code or "en"
            self.system_lang_code = system_lang_code or "en"
        elif any([device_model, system_version, app_version]):
            # Some params provided but not all — generate missing ones
            seed = unique_id or self.session_string[:32] if self.session_string else "default"

            fingerprint = generate_fingerprint_for_api(
                unique_id=seed,
                api_id=self.api_id,
                lang_code=lang_code or "en",
                system_lang_code=system_lang_code or "en",
            )

            self.device_model = device_model or fingerprint["device_model"]
            self.system_version = system_version or fingerprint["system_version"]
            self.app_version = app_version or fingerprint["app_version"]
            self.lang_code = lang_code or fingerprint["lang_code"]
            self.system_lang_code = system_lang_code or fingerprint["system_lang_code"]
        else:
            # No device params provided — leave as None, Telethon will use its platform defaults
            # This is critical for accounts imported from other clients (e.g. Desktop)
            # to avoid fingerprint mismatch that triggers account freezing
            self.device_model = None
            self.system_version = None
            self.app_version = None
            self.lang_code = lang_code or "en"
            self.system_lang_code = system_lang_code or "en"

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
        """Create TelegramClient instance with device fingerprint"""
        session = SessionManager.create_memory_session(self.session_string)

        # Only pass device params if they are set; otherwise let Telethon use its defaults
        kwargs = dict(
            proxy=self.proxy,
            connection_retries=self.connection_retries,
            request_retries=self.request_retries,
            timeout=self.timeout,
            lang_code=self.lang_code,
            system_lang_code=self.system_lang_code,
        )
        if self.device_model:
            kwargs["device_model"] = self.device_model
        if self.system_version:
            kwargs["system_version"] = self.system_version
        if self.app_version:
            kwargs["app_version"] = self.app_version

        return TelegramClient(
            session,
            self.api_id,
            self.api_hash,
            **kwargs,
        )

    async def _test_proxy_connection(self) -> dict:
        """
        Test proxy connectivity before connecting to Telegram.

        For SOCKS proxies: test via aiohttp_socks to api.telegram.org.
        For HTTP proxies: test CONNECT tunnel to Telegram DC.

        Returns:
            Dict with test results: {"success": bool, "response_time": float, "error": str|None}
        """
        import time
        import base64

        if not self.proxy_dict:
            return {"success": True, "response_time": 0, "error": None}

        start = time.time()
        proxy_type = (
            self.proxy_dict.get("type")
            or self.proxy_dict.get("proxy_type")
            or "socks5"
        )
        addr = self.proxy_dict.get("host") or self.proxy_dict.get("addr")
        port = int(self.proxy_dict.get("port", 1080))
        username = self.proxy_dict.get("username")
        password = self.proxy_dict.get("password")

        try:
            if proxy_type.lower().startswith("socks"):
                try:
                    from aiohttp_socks import ProxyConnector
                    import aiohttp

                    proxy_url = f"{proxy_type}://"
                    if username and password:
                        proxy_url += f"{username}:{password}@"
                    proxy_url += f"{addr}:{port}"

                    timeout = aiohttp.ClientTimeout(total=5)
                    connector = ProxyConnector.from_url(proxy_url)

                    async with aiohttp.ClientSession(
                        connector=connector, timeout=timeout
                    ) as session:
                        async with session.get("https://api.telegram.org") as response:
                            elapsed = time.time() - start
                            return {
                                "success": True,
                                "response_time": elapsed,
                                "error": None,
                            }
                except ImportError:
                    return {"success": True, "response_time": 0, "error": None}
                except Exception as e:
                    elapsed = time.time() - start
                    return {
                        "success": False,
                        "response_time": elapsed,
                        "error": f"SOCKS proxy not working: {e}",
                    }
            else:
                # HTTP proxy: test CONNECT to Telegram DC
                telegram_dc = "149.154.167.50"
                telegram_port = 443

                try:
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_connection(addr, port), timeout=5
                    )
                except Exception as e:
                    elapsed = time.time() - start
                    return {
                        "success": False,
                        "response_time": elapsed,
                        "error": f"Cannot connect to proxy: {e}",
                    }

                try:
                    connect_request = f"CONNECT {telegram_dc}:{telegram_port} HTTP/1.1\r\n"
                    connect_request += f"Host: {telegram_dc}:{telegram_port}\r\n"

                    if username and password:
                        credentials = base64.b64encode(
                            f"{username}:{password}".encode()
                        ).decode()
                        connect_request += f"Proxy-Authorization: Basic {credentials}\r\n"

                    connect_request += "\r\n"

                    writer.write(connect_request.encode())
                    await writer.drain()

                    response = await asyncio.wait_for(reader.readline(), timeout=5)
                    response_str = response.decode().strip()

                    writer.close()
                    try:
                        await writer.wait_closed()
                    except Exception as e:
                        logger.debug(f"Writer close error: {e}")

                    elapsed = time.time() - start

                    if "200" in response_str:
                        return {"success": True, "response_time": elapsed, "error": None}
                    elif "407" in response_str:
                        return {
                            "success": False,
                            "response_time": elapsed,
                            "error": "Invalid proxy username or password",
                        }
                    elif "403" in response_str:
                        return {
                            "success": False,
                            "response_time": elapsed,
                            "error": "Proxy blocked connection to Telegram",
                        }
                    else:
                        return {
                            "success": False,
                            "response_time": elapsed,
                            "error": "This proxy does not support Telegram connections",
                        }

                except asyncio.TimeoutError:
                    try:
                        writer.close()
                    except Exception as e:
                        logger.debug(f"Writer close error: {e}")
                    elapsed = time.time() - start
                    return {
                        "success": False,
                        "response_time": elapsed,
                        "error": "Timeout testing CONNECT to Telegram",
                    }
                except Exception as e:
                    try:
                        writer.close()
                    except Exception as e2:
                        logger.debug(f"Writer close error: {e2}")
                    elapsed = time.time() - start
                    return {
                        "success": False,
                        "response_time": elapsed,
                        "error": f"Error testing CONNECT: {e}",
                    }

        except Exception as e:
            elapsed = time.time() - start
            return {
                "success": False,
                "response_time": elapsed,
                "error": str(e),
            }

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
    unique_id: Optional[str] = None,
    device_model: Optional[str] = None,
    system_version: Optional[str] = None,
    app_version: Optional[str] = None,
    lang_code: Optional[str] = None,
    check_frozen: bool = False,
) -> Tuple[bool, Optional[Dict], Optional[str]]:
    """
    Validate session string and get account info.

    Args:
        session_string: Telethon session string
        proxy: Optional proxy config
        api_id: Optional API ID
        api_hash: Optional API Hash
        unique_id: Unique ID for consistent device fingerprint (e.g. phone number)
        device_model: Optional explicit device model
        system_version: Optional explicit system version
        app_version: Optional explicit app version
        lang_code: Optional language code

    Returns:
        Tuple[is_valid, user_info, error_code]
        error_code is a translation key like "session_expired", "banned", etc.
    """
    try:
        client = BaseClient(
            session_string=session_string,
            api_id=api_id,
            api_hash=api_hash,
            proxy=proxy,
            connection_retries=3,
            timeout=15,
            unique_id=unique_id,
            device_model=device_model,
            system_version=system_version,
            app_version=app_version,
            lang_code=lang_code,
        )

        async with client:
            await client.check_auth()
            me = await client.get_me()

            # Check if user is restricted/frozen
            is_restricted = getattr(me, "restricted", False)
            restriction_reason = getattr(me, "restriction_reason", None)

            if is_restricted:
                reason_text = ""
                if restriction_reason:
                    # restriction_reason is a list of RestrictionReason objects
                    reasons = [getattr(r, "reason", str(r)) for r in restriction_reason]
                    reason_text = ", ".join(reasons)
                return False, None, f"restricted:{reason_text}" if reason_text else "restricted"

            # Try to perform a search to detect frozen accounts
            # Frozen accounts get FROZEN_METHOD_INVALID error
            # WARNING: This action is suspicious from a "new device" — only run if explicitly requested
            if check_frozen:
                try:
                    from telethon.tl.functions.contacts import SearchRequest
                    await client._client(SearchRequest(q='telegram', limit=1))
                except Exception as action_error:
                    error_str = str(action_error).lower()
                    if "frozen" in error_str:
                        return False, None, "frozen"
                    elif "deactivated" in error_str or "banned" in error_str:
                        return False, None, "banned"
                    elif "forbidden" in error_str or "restricted" in error_str:
                        return False, None, "restricted"
                    elif "flood" in error_str:
                        # Flood is not a permanent issue, account might still be valid
                        pass
                    # Other errors - account might still be valid
                    pass

            user_info = {
                "telegram_id": me.id,
                "username": me.username,
                "first_name": me.first_name,
                "last_name": me.last_name,
                "phone": me.phone,
                "is_premium": getattr(me, "premium", False),
            }

            return True, user_info, None

    except (UserDeactivatedBanError, PhoneNumberBannedError):
        return False, None, "banned"
    except UserDeactivatedError:
        return False, None, "deactivated"
    except AuthKeyDuplicatedError:
        return False, None, "auth_key_duplicated"
    except (AuthKeyUnregisteredError, AuthKeyPermEmptyError):
        return False, None, "session_expired"
    except (SessionRevokedError, TelethonSessionExpired):
        return False, None, "session_revoked"
    except FloodWaitError as e:
        return False, None, f"flood_wait:{e.seconds}"
    except (UnauthorizedError, SessionExpiredError):
        return False, None, "session_expired"
    except ConnectionError:
        return False, None, "connection_failed"
    except Exception as e:
        error_str = str(e).lower()
        # Parse common errors
        if "deactivated" in error_str and "ban" in error_str:
            return False, None, "banned"
        elif "deactivated" in error_str:
            return False, None, "deactivated"
        elif "auth" in error_str and "key" in error_str:
            if "duplicat" in error_str:
                return False, None, "auth_key_duplicated"
            else:
                return False, None, "session_expired"
        elif "session" in error_str and ("revok" in error_str or "expir" in error_str):
            return False, None, "session_revoked"
        elif "flood" in error_str:
            return False, None, "flood_wait"
        elif "timeout" in error_str or "timed out" in error_str:
            return False, None, "timeout"
        elif "connection" in error_str or "connect" in error_str:
            return False, None, "connection_failed"
        else:
            return False, None, f"unknown:{str(e)[:100]}"
