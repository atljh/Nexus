"""
Account authorization service for new Telegram accounts.
Implements phone -> SMS code -> 2FA password flow.

Unlike web version (GramGPT), this desktop version uses in-memory
session storage instead of Redis since we have a single process.

SECURITY: All connections MUST use proxy to protect user's IP.
"""

import uuid
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

from .telegram_client import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    PhoneNumberInvalidError,
    PhoneNumberBannedError,
    PhoneNumberFloodError,
    PasswordHashInvalidError,
    FloodWaitError,
)

from .device_generator import generate_device_fingerprint, OFFICIAL_APIS


class AuthStep(str, Enum):
    """Authentication flow steps."""
    PHONE = "phone"
    CODE = "code"
    PASSWORD = "password"
    SUCCESS = "success"


@dataclass
class AuthSession:
    """Stores authentication state between steps."""
    session_id: str
    phone: str
    session_string: str  # Telethon StringSession (saved after connect)
    phone_code_hash: str
    proxy: Optional[Dict] = None
    needs_password: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(minutes=10))


@dataclass
class AuthStartResult:
    """Result of start_auth operation."""
    success: bool
    session_id: Optional[str] = None
    phone: Optional[str] = None
    error: Optional[str] = None


@dataclass
class AuthVerifyResult:
    """Result of verify_code operation."""
    success: bool
    status: str = ""  # "success" | "password_required"
    account_data: Optional[Dict] = None
    session_string: Optional[str] = None
    error: Optional[str] = None


class AuthService:
    """
    Manages phone authorization flow for new accounts.

    Flow:
    1. start_auth(phone, proxy) -> Sends SMS code, returns session_id
    2. verify_code(session_id, code) -> Verifies code
       - If 2FA enabled -> returns "password_required"
       - If success -> returns account data and session_string
    3. verify_code(session_id, code, password) -> Complete auth with 2FA

    Sessions are stored in memory with 10-minute TTL.

    SECURITY: Proxy is REQUIRED for all operations to protect user's IP.
    """

    # Use Android official API (most common, least suspicious)
    DEFAULT_API_ID = OFFICIAL_APIS["android"]["api_id"]  # 6
    DEFAULT_API_HASH = OFFICIAL_APIS["android"]["api_hash"]
    SESSION_TTL_MINUTES = 10

    def __init__(self):
        self._sessions: Dict[str, AuthSession] = {}

    def _cleanup_expired(self):
        """Remove expired sessions."""
        now = datetime.now(timezone.utc)
        expired = [sid for sid, sess in self._sessions.items() if sess.expires_at < now]
        for sid in expired:
            del self._sessions[sid]

    @staticmethod
    def _format_proxy(proxy: Optional[Dict]) -> Optional[Tuple]:
        """Format proxy dict to Telethon tuple format."""
        from telegram.proxy_utils import format_proxy
        return format_proxy(proxy)

    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone number format."""
        # Remove spaces, dashes, and other formatting
        phone = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        # Add + prefix if missing
        if not phone.startswith("+"):
            phone = "+" + phone
        return phone

    async def start_auth(
        self,
        phone: str,
        proxy: Optional[Dict] = None,
    ) -> AuthStartResult:
        """
        Start authentication by sending SMS code.

        Args:
            phone: Phone number with country code (e.g., +1234567890)
            proxy: Proxy configuration (REQUIRED for safety)

        Returns:
            AuthStartResult with session_id for next step

        SECURITY: Proxy is required to protect user's real IP from Telegram.
        """
        # SECURITY: Require proxy for all auth operations
        if not proxy:
            return AuthStartResult(
                success=False,
                error="Proxy is required for authorization to protect your IP"
            )

        self._cleanup_expired()

        phone = self._normalize_phone(phone)

        client = None
        try:
            proxy_tuple = self._format_proxy(proxy)

            # Generate device fingerprint based on phone number
            fingerprint = generate_device_fingerprint(
                unique_id=phone,
                platform="android",
            )

            # Create new Telethon client with empty StringSession and device fingerprint
            client = TelegramClient(
                StringSession(),
                self.DEFAULT_API_ID,
                self.DEFAULT_API_HASH,
                proxy=proxy_tuple,
                device_model=fingerprint["device_model"],
                system_version=fingerprint["system_version"],
                app_version=fingerprint["app_version"],
                lang_code=fingerprint["lang_code"],
                system_lang_code=fingerprint["system_lang_code"],
            )

            await client.connect()

            # Send code request
            sent_code = await client.send_code_request(phone)

            # Save session string for reuse in next step
            session_string = client.session.save()

            await client.disconnect()

            # Create auth session
            session_id = str(uuid.uuid4())
            auth_session = AuthSession(
                session_id=session_id,
                phone=phone,
                session_string=session_string,
                phone_code_hash=sent_code.phone_code_hash,
                proxy=proxy,
            )

            self._sessions[session_id] = auth_session

            return AuthStartResult(
                success=True,
                session_id=session_id,
                phone=phone,
            )

        except PhoneNumberInvalidError:
            return AuthStartResult(
                success=False,
                error="Invalid phone number format"
            )
        except PhoneNumberBannedError:
            return AuthStartResult(
                success=False,
                error="Phone number is banned"
            )
        except PhoneNumberFloodError:
            return AuthStartResult(
                success=False,
                error="Too many attempts. Try again later"
            )
        except FloodWaitError as e:
            return AuthStartResult(
                success=False,
                error=f"Too many requests. Wait {e.seconds} seconds"
            )
        except Exception as e:
            return AuthStartResult(success=False, error=str(e))
        finally:
            if client and client.is_connected():
                await client.disconnect()

    async def verify_code(
        self,
        session_id: str,
        code: str,
        password: Optional[str] = None,
    ) -> AuthVerifyResult:
        """
        Verify SMS code and optionally 2FA password.

        Args:
            session_id: Session ID from start_auth
            code: SMS code received
            password: 2FA password (if required)

        Returns:
            AuthVerifyResult with status and account data
        """
        self._cleanup_expired()

        auth_session = self._sessions.get(session_id)
        if not auth_session:
            return AuthVerifyResult(
                success=False,
                error="Invalid or expired session. Please start again."
            )

        client = None
        try:
            proxy_tuple = self._format_proxy(auth_session.proxy)

            # Generate consistent device fingerprint based on phone
            fingerprint = generate_device_fingerprint(
                unique_id=auth_session.phone,
                platform="android",
            )

            # Recreate client from saved session string with device fingerprint
            client = TelegramClient(
                StringSession(auth_session.session_string),
                self.DEFAULT_API_ID,
                self.DEFAULT_API_HASH,
                proxy=proxy_tuple,
                device_model=fingerprint["device_model"],
                system_version=fingerprint["system_version"],
                app_version=fingerprint["app_version"],
                lang_code=fingerprint["lang_code"],
                system_lang_code=fingerprint["system_lang_code"],
            )

            await client.connect()

            try:
                if auth_session.needs_password and password:
                    # Second attempt with password only (after code was already verified)
                    await client.sign_in(password=password)
                else:
                    # First attempt with code
                    await client.sign_in(
                        auth_session.phone,
                        code,
                        phone_code_hash=auth_session.phone_code_hash,
                    )

            except SessionPasswordNeededError:
                # 2FA required
                if not password:
                    # Update session string after partial auth
                    auth_session.session_string = client.session.save()
                    auth_session.needs_password = True

                    await client.disconnect()

                    return AuthVerifyResult(
                        success=True,
                        status="password_required",
                        error="2FA password required",
                    )

                # Password was provided with code - try to sign in
                try:
                    await client.sign_in(password=password)
                except PasswordHashInvalidError:
                    await client.disconnect()
                    return AuthVerifyResult(
                        success=False,
                        error="Invalid 2FA password"
                    )

            except PhoneCodeInvalidError:
                await client.disconnect()
                return AuthVerifyResult(success=False, error="Invalid code")

            except PhoneCodeExpiredError:
                await client.disconnect()
                # Remove expired session
                if session_id in self._sessions:
                    del self._sessions[session_id]
                return AuthVerifyResult(
                    success=False,
                    error="Code expired. Please start again."
                )

            except PasswordHashInvalidError:
                await client.disconnect()
                return AuthVerifyResult(
                    success=False,
                    error="Invalid 2FA password"
                )

            # Success - get user info
            me = await client.get_me()
            session_string = client.session.save()

            await client.disconnect()

            # Cleanup session
            if session_id in self._sessions:
                del self._sessions[session_id]

            return AuthVerifyResult(
                success=True,
                status="success",
                session_string=session_string,
                account_data={
                    "telegram_id": me.id,
                    "username": me.username,
                    "first_name": me.first_name,
                    "last_name": me.last_name,
                    "phone": me.phone,
                    "is_premium": getattr(me, "premium", False),
                    "api_id": self.DEFAULT_API_ID,
                    "api_hash": self.DEFAULT_API_HASH,
                    "device_fingerprint": {
                        "device_model": fingerprint.get("device_model"),
                        "system_version": fingerprint.get("system_version"),
                        "app_version": fingerprint.get("app_version"),
                        "lang_code": fingerprint.get("lang_code"),
                        "system_lang_code": fingerprint.get("system_lang_code"),
                    },
                },
            )

        except FloodWaitError as e:
            return AuthVerifyResult(
                success=False,
                error=f"Too many requests. Wait {e.seconds} seconds"
            )
        except Exception as e:
            return AuthVerifyResult(success=False, error=str(e))
        finally:
            if client and client.is_connected():
                await client.disconnect()

    async def resend_code(self, session_id: str) -> AuthStartResult:
        """
        Resend SMS code for existing session.

        Args:
            session_id: Session ID from start_auth

        Returns:
            AuthStartResult with updated session info
        """
        self._cleanup_expired()

        auth_session = self._sessions.get(session_id)
        if not auth_session:
            return AuthStartResult(
                success=False,
                error="Invalid or expired session. Please start again."
            )

        client = None
        try:
            proxy_tuple = self._format_proxy(auth_session.proxy)

            # Generate consistent device fingerprint based on phone
            fingerprint = generate_device_fingerprint(
                unique_id=auth_session.phone,
                platform="android",
            )

            client = TelegramClient(
                StringSession(auth_session.session_string),
                self.DEFAULT_API_ID,
                self.DEFAULT_API_HASH,
                proxy=proxy_tuple,
                device_model=fingerprint["device_model"],
                system_version=fingerprint["system_version"],
                app_version=fingerprint["app_version"],
                lang_code=fingerprint["lang_code"],
                system_lang_code=fingerprint["system_lang_code"],
            )

            await client.connect()

            # Resend code
            sent_code = await client.send_code_request(auth_session.phone)

            # Update session
            auth_session.phone_code_hash = sent_code.phone_code_hash
            auth_session.session_string = client.session.save()
            auth_session.expires_at = datetime.now(timezone.utc) + timedelta(minutes=self.SESSION_TTL_MINUTES)

            await client.disconnect()

            return AuthStartResult(
                success=True,
                session_id=session_id,
                phone=auth_session.phone,
            )

        except FloodWaitError as e:
            return AuthStartResult(
                success=False,
                error=f"Too many requests. Wait {e.seconds} seconds"
            )
        except Exception as e:
            return AuthStartResult(success=False, error=str(e))
        finally:
            if client and client.is_connected():
                await client.disconnect()

    async def cancel_auth(self, session_id: str) -> bool:
        """
        Cancel authentication and cleanup session.

        Args:
            session_id: Session ID to cancel

        Returns:
            True if session was found and removed
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def get_session_info(self, session_id: str) -> Optional[Dict]:
        """
        Get info about auth session.

        Args:
            session_id: Session ID

        Returns:
            Dict with session info or None if not found
        """
        self._cleanup_expired()

        auth_session = self._sessions.get(session_id)
        if not auth_session:
            return None

        return {
            "phone": auth_session.phone,
            "needs_password": auth_session.needs_password,
            "expires_at": auth_session.expires_at.isoformat(),
            "created_at": auth_session.created_at.isoformat(),
        }


# Singleton instance
auth_service = AuthService()
