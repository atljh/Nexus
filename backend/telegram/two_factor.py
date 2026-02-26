"""
Two-Factor Authentication management for Telegram accounts.
Provides methods to check, set, change, and remove 2FA.
"""

import asyncio
from typing import Optional, Dict, Tuple
from dataclasses import dataclass
from enum import Enum

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.account import GetPasswordRequest, UpdatePasswordSettingsRequest
from telethon.tl.types.account import PasswordInputSettings
from telethon.password import compute_check
from telethon.errors import PasswordHashInvalidError

from .session_manager import SessionManager
from .device_generator import OFFICIAL_APIS


class TwoFactorStatus(str, Enum):
    NOT_SET = "not_set"
    ENABLED = "enabled"
    CHECKING = "checking"


@dataclass
class TwoFactorCheckResult:
    """Result of 2FA status check."""
    has_2fa: bool
    password_hint: Optional[str] = None
    error: Optional[str] = None


@dataclass
class TwoFactorSetResult:
    """Result of 2FA set/change/remove operation."""
    success: bool
    error: Optional[str] = None


class TwoFactorManager:
    """
    Manages 2FA operations for Telegram accounts.

    Methods:
        check_2fa_status: Check if account has 2FA enabled
        set_2fa: Enable 2FA on account
        change_2fa: Change existing 2FA password
        remove_2fa: Disable 2FA on account
    """

    # Use Android official API (consistent with other modules)
    DEFAULT_API_ID = OFFICIAL_APIS["android"]["api_id"]  # 6
    DEFAULT_API_HASH = OFFICIAL_APIS["android"]["api_hash"]

    def __init__(self, connection_timeout: int = 30):
        self.connection_timeout = connection_timeout

    def _format_proxy(self, proxy: Optional[Dict]) -> Optional[Tuple]:
        """Format proxy dict to Telethon tuple format."""
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

    def _create_client(
        self,
        session_string: str,
        proxy: Optional[Dict] = None,
        api_id: Optional[int] = None,
        api_hash: Optional[str] = None,
        device_fingerprint: Optional[Dict] = None,
        unique_id: Optional[str] = None,
    ) -> TelegramClient:
        """Create TelegramClient instance with device fingerprint."""
        from .device_generator import generate_fingerprint_for_api

        session = SessionManager.create_memory_session(session_string)
        proxy_tuple = self._format_proxy(proxy)

        # Use provided api_id/api_hash or defaults
        used_api_id = api_id or self.DEFAULT_API_ID
        used_api_hash = api_hash or self.DEFAULT_API_HASH

        # Use device fingerprint from account if provided
        # If no fingerprint — don't generate a fake one, let Telethon use its defaults
        client_kwargs = dict(
            proxy=proxy_tuple,
            timeout=self.connection_timeout,
        )

        if device_fingerprint and device_fingerprint.get("device_model"):
            client_kwargs["device_model"] = device_fingerprint.get("device_model")
            client_kwargs["system_version"] = device_fingerprint.get("system_version")
            client_kwargs["app_version"] = device_fingerprint.get("app_version")
            client_kwargs["lang_code"] = device_fingerprint.get("lang_code", "en")
            client_kwargs["system_lang_code"] = device_fingerprint.get("system_lang_code", "en")

        return TelegramClient(
            session,
            used_api_id,
            used_api_hash,
            **client_kwargs,
        )

    async def check_2fa_status(
        self,
        session_string: str,
        proxy: Optional[Dict] = None,
        api_id: Optional[int] = None,
        api_hash: Optional[str] = None,
        device_fingerprint: Optional[Dict] = None,
        unique_id: Optional[str] = None,
    ) -> TwoFactorCheckResult:
        """
        Check if account has 2FA enabled and get password hint.

        Args:
            session_string: Telethon session string
            proxy: Optional proxy configuration
            api_id: Optional API ID from account
            api_hash: Optional API hash from account
            device_fingerprint: Optional device fingerprint from account
            unique_id: Optional unique ID for fingerprint generation

        Returns:
            TwoFactorCheckResult with has_2fa status and hint
        """
        client = None
        try:
            client = self._create_client(
                session_string, proxy, api_id, api_hash, device_fingerprint, unique_id
            )
            await client.connect()

            if not await client.is_user_authorized():
                return TwoFactorCheckResult(
                    has_2fa=False,
                    error="Session not authorized"
                )

            pwd = await client(GetPasswordRequest())

            return TwoFactorCheckResult(
                has_2fa=pwd.has_password,
                password_hint=pwd.hint if pwd.has_password else None,
            )

        except Exception as e:
            return TwoFactorCheckResult(has_2fa=False, error=str(e))
        finally:
            if client:
                try:
                    await client.disconnect()
                except:
                    pass

    async def set_2fa(
        self,
        session_string: str,
        new_password: str,
        hint: str = "",
        proxy: Optional[Dict] = None,
        api_id: Optional[int] = None,
        api_hash: Optional[str] = None,
        device_fingerprint: Optional[Dict] = None,
        unique_id: Optional[str] = None,
    ) -> TwoFactorSetResult:
        """
        Set 2FA password on account.

        Args:
            session_string: Telethon session string
            new_password: New 2FA password to set
            hint: Optional password hint
            proxy: Optional proxy configuration
            api_id: Optional API ID from account
            api_hash: Optional API hash from account
            device_fingerprint: Optional device fingerprint from account
            unique_id: Optional unique ID for fingerprint generation

        Returns:
            TwoFactorSetResult with success status
        """
        client = None
        try:
            client = self._create_client(
                session_string, proxy, api_id, api_hash, device_fingerprint, unique_id
            )
            await client.connect()

            if not await client.is_user_authorized():
                return TwoFactorSetResult(
                    success=False,
                    error="Session not authorized"
                )

            # Check if 2FA already enabled
            pwd = await client(GetPasswordRequest())
            if pwd.has_password:
                return TwoFactorSetResult(
                    success=False,
                    error="2FA already enabled. Use change_2fa to modify."
                )

            # Use Telethon's built-in edit_2fa method
            await client.edit_2fa(
                new_password=new_password,
                hint=hint or "",
            )

            return TwoFactorSetResult(success=True)

        except Exception as e:
            error_msg = str(e)
            if "PASSWORD_HASH_INVALID" in error_msg.upper():
                error_msg = "Invalid password hash"
            return TwoFactorSetResult(success=False, error=error_msg)
        finally:
            if client:
                try:
                    await client.disconnect()
                except:
                    pass

    async def change_2fa(
        self,
        session_string: str,
        current_password: str,
        new_password: str,
        new_hint: str = "",
        proxy: Optional[Dict] = None,
        api_id: Optional[int] = None,
        api_hash: Optional[str] = None,
        device_fingerprint: Optional[Dict] = None,
        unique_id: Optional[str] = None,
    ) -> TwoFactorSetResult:
        """
        Change existing 2FA password.

        Args:
            session_string: Telethon session string
            current_password: Current 2FA password
            new_password: New 2FA password
            new_hint: Optional new password hint
            proxy: Optional proxy configuration
            api_id: Optional API ID from account
            api_hash: Optional API hash from account
            device_fingerprint: Optional device fingerprint from account
            unique_id: Optional unique ID for fingerprint generation

        Returns:
            TwoFactorSetResult with success status
        """
        client = None
        try:
            client = self._create_client(
                session_string, proxy, api_id, api_hash, device_fingerprint, unique_id
            )
            await client.connect()

            if not await client.is_user_authorized():
                return TwoFactorSetResult(
                    success=False,
                    error="Session not authorized"
                )

            # Check if 2FA is enabled
            pwd = await client(GetPasswordRequest())
            if not pwd.has_password:
                return TwoFactorSetResult(
                    success=False,
                    error="2FA not enabled. Use set_2fa first."
                )

            # Use edit_2fa with current password
            await client.edit_2fa(
                current_password=current_password,
                new_password=new_password,
                hint=new_hint or "",
            )

            return TwoFactorSetResult(success=True)

        except PasswordHashInvalidError:
            return TwoFactorSetResult(
                success=False,
                error="Invalid current password"
            )
        except Exception as e:
            error_msg = str(e)
            if "PASSWORD_HASH_INVALID" in error_msg.upper():
                error_msg = "Invalid current password"
            return TwoFactorSetResult(success=False, error=error_msg)
        finally:
            if client:
                try:
                    await client.disconnect()
                except:
                    pass

    async def remove_2fa(
        self,
        session_string: str,
        current_password: str,
        proxy: Optional[Dict] = None,
        api_id: Optional[int] = None,
        api_hash: Optional[str] = None,
        device_fingerprint: Optional[Dict] = None,
        unique_id: Optional[str] = None,
    ) -> TwoFactorSetResult:
        """
        Remove 2FA from account.

        Args:
            session_string: Telethon session string
            current_password: Current 2FA password to verify
            proxy: Optional proxy configuration
            api_id: Optional API ID from account
            api_hash: Optional API hash from account
            device_fingerprint: Optional device fingerprint from account
            unique_id: Optional unique ID for fingerprint generation

        Returns:
            TwoFactorSetResult with success status
        """
        client = None
        try:
            client = self._create_client(
                session_string, proxy, api_id, api_hash, device_fingerprint, unique_id
            )
            await client.connect()

            if not await client.is_user_authorized():
                return TwoFactorSetResult(
                    success=False,
                    error="Session not authorized"
                )

            pwd = await client(GetPasswordRequest())

            if not pwd.has_password:
                return TwoFactorSetResult(
                    success=False,
                    error="2FA not enabled"
                )

            # Use edit_2fa to remove password (set empty new_password)
            await client.edit_2fa(
                current_password=current_password,
                new_password=None,  # None removes 2FA
            )

            return TwoFactorSetResult(success=True)

        except PasswordHashInvalidError:
            return TwoFactorSetResult(
                success=False,
                error="Invalid password"
            )
        except Exception as e:
            error_msg = str(e)
            if "PASSWORD_HASH_INVALID" in error_msg.upper():
                error_msg = "Invalid password"
            return TwoFactorSetResult(success=False, error=error_msg)
        finally:
            if client:
                try:
                    await client.disconnect()
                except:
                    pass


# Singleton instance
two_factor_manager = TwoFactorManager()
