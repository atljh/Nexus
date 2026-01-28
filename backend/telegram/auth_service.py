"""
Account authorization service for new Telegram accounts.
Implements phone -> SMS code -> 2FA password flow.

Unlike web version (GramGPT), this desktop version uses in-memory
session storage instead of Redis since we have a single process.
"""

import uuid
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

from telethon import TelegramClient
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
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime = field(default_factory=lambda: datetime.utcnow() + timedelta(minutes=10))


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
    """

    DEFAULT_API_ID = 2040
    DEFAULT_API_HASH = "b18441a1ff607e10a989891a5462e627"
    SESSION_TTL_MINUTES = 10

    def __init__(self):
        self._sessions: Dict[str, AuthSession] = {}

    def _cleanup_expired(self):
        """Remove expired sessions."""
        now = datetime.utcnow()
        expired = [sid for sid, sess in self._sessions.items() if sess.expires_at < now]
        for sid in expired:
            del self._sessions[sid]

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
            proxy: Proxy configuration (recommended for safety)

        Returns:
            AuthStartResult with session_id for next step
        """
        self._cleanup_expired()

        phone = self._normalize_phone(phone)

        client = None
        try:
            proxy_tuple = self._format_proxy(proxy)

            # Create new Telethon client with empty StringSession
            client = TelegramClient(
                StringSession(),
                self.DEFAULT_API_ID,
                self.DEFAULT_API_HASH,
                proxy=proxy_tuple,
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

            # Recreate client from saved session string
            client = TelegramClient(
                StringSession(auth_session.session_string),
                self.DEFAULT_API_ID,
                self.DEFAULT_API_HASH,
                proxy=proxy_tuple,
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

            client = TelegramClient(
                StringSession(auth_session.session_string),
                self.DEFAULT_API_ID,
                self.DEFAULT_API_HASH,
                proxy=proxy_tuple,
            )

            await client.connect()

            # Resend code
            sent_code = await client.send_code_request(auth_session.phone)

            # Update session
            auth_session.phone_code_hash = sent_code.phone_code_hash
            auth_session.session_string = client.session.save()
            auth_session.expires_at = datetime.utcnow() + timedelta(minutes=self.SESSION_TTL_MINUTES)

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
