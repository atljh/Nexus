"""
Telegram session management service.
Provides methods to list and terminate other active sessions.
"""

import asyncio
import logging
from typing import Optional, Dict, Tuple, List
from dataclasses import dataclass, field

from .telegram_client import TelegramClient
from .session_manager import SessionManager
from .device_generator import OFFICIAL_APIS

from telethon.tl.functions.account import GetAuthorizationsRequest, ResetAuthorizationRequest
from telethon.errors import FloodWaitError, FreshResetAuthorisationForbiddenError

logger = logging.getLogger(__name__)


@dataclass
class SessionInfo:
    """Single authorization session info."""
    hash: int
    device_model: str
    platform: str
    system_version: str
    api_id: int
    app_name: str
    app_version: str
    ip: str
    country: str
    date_created: int
    date_active: int
    is_current: bool


@dataclass
class TerminateResult:
    """Result of session termination."""
    success: bool
    terminated_count: int = 0
    total_other_sessions: int = 0
    errors: List[str] = field(default_factory=list)


class SessionService:
    """Manages Telegram session operations."""

    DEFAULT_API_ID = OFFICIAL_APIS["android"]["api_id"]
    DEFAULT_API_HASH = OFFICIAL_APIS["android"]["api_hash"]

    def __init__(self, connection_timeout: int = 30):
        self.connection_timeout = connection_timeout

    @staticmethod
    def _format_proxy(proxy: Optional[Dict]) -> Optional[Tuple]:
        from telegram.proxy_utils import format_proxy
        return format_proxy(proxy)

    def _create_client(
        self,
        session_string: str,
        proxy: Optional[Dict] = None,
        api_id: Optional[int] = None,
        api_hash: Optional[str] = None,
        device_fingerprint: Optional[Dict] = None,
    ) -> TelegramClient:
        session = SessionManager.create_memory_session(session_string)
        proxy_tuple = self._format_proxy(proxy)

        used_api_id = api_id or self.DEFAULT_API_ID
        used_api_hash = api_hash or self.DEFAULT_API_HASH

        client_kwargs = dict(
            proxy=proxy_tuple,
            timeout=self.connection_timeout,
        )

        if device_fingerprint and device_fingerprint.get("device_model"):
            client_kwargs["device_model"] = device_fingerprint.get("device_model")
            client_kwargs["system_version"] = device_fingerprint.get("system_version")
            client_kwargs["app_version"] = device_fingerprint.get("app_version")
            client_kwargs["lang_code"] = device_fingerprint.get("lang_code", "en")
            client_kwargs["system_lang_code"] = device_fingerprint.get("system_lang_code", "en-US")

        return TelegramClient(
            session,
            used_api_id,
            used_api_hash,
            **client_kwargs,
        )

    async def get_sessions(
        self,
        session_string: str,
        proxy: Optional[Dict] = None,
        api_id: Optional[int] = None,
        api_hash: Optional[str] = None,
        device_fingerprint: Optional[Dict] = None,
    ) -> Dict:
        """Get list of all active sessions."""
        client = None
        try:
            client = self._create_client(
                session_string, proxy, api_id, api_hash, device_fingerprint
            )
            await client.connect()

            if not await client.is_user_authorized():
                return {"error": "Session not authorized", "sessions": []}

            result = await client(GetAuthorizationsRequest())

            sessions = []
            for auth in result.authorizations:
                sessions.append(SessionInfo(
                    hash=auth.hash,
                    device_model=auth.device_model or "",
                    platform=auth.platform or "",
                    system_version=auth.system_version or "",
                    api_id=auth.api_id,
                    app_name=auth.app_name or "",
                    app_version=auth.app_version or "",
                    ip=auth.ip or "",
                    country=auth.country or "",
                    date_created=auth.date_created,
                    date_active=auth.date_active,
                    is_current=auth.hash == 0,
                ))

            return {
                "sessions": [
                    {
                        "hash": s.hash,
                        "device_model": s.device_model,
                        "platform": s.platform,
                        "system_version": s.system_version,
                        "api_id": s.api_id,
                        "app_name": s.app_name,
                        "app_version": s.app_version,
                        "ip": s.ip,
                        "country": s.country,
                        "date_created": s.date_created,
                        "date_active": s.date_active,
                        "is_current": s.is_current,
                    }
                    for s in sessions
                ],
                "total": len(sessions),
                "other_count": sum(1 for s in sessions if not s.is_current),
            }

        except Exception as e:
            return {"error": str(e), "sessions": []}
        finally:
            if client:
                try:
                    await client.disconnect()
                except Exception:
                    pass

    async def terminate_other_sessions(
        self,
        session_string: str,
        proxy: Optional[Dict] = None,
        api_id: Optional[int] = None,
        api_hash: Optional[str] = None,
        device_fingerprint: Optional[Dict] = None,
    ) -> TerminateResult:
        """Terminate all other sessions (except current)."""
        client = None
        try:
            client = self._create_client(
                session_string, proxy, api_id, api_hash, device_fingerprint
            )
            await client.connect()

            if not await client.is_user_authorized():
                return TerminateResult(success=False, errors=["Session not authorized"])

            # Get all sessions
            result = await client(GetAuthorizationsRequest())

            other_sessions = [
                auth for auth in result.authorizations
                if auth.hash != 0
            ]

            if not other_sessions:
                return TerminateResult(success=True, terminated_count=0, total_other_sessions=0)

            terminated = 0
            errors = []

            for auth in other_sessions:
                try:
                    await client(ResetAuthorizationRequest(hash=auth.hash))
                    terminated += 1
                    # Small delay between terminations
                    if terminated < len(other_sessions):
                        await asyncio.sleep(0.3)
                except FreshResetAuthorisationForbiddenError:
                    errors.append(f"Cannot terminate recent session ({auth.device_model}): too fresh")
                except FloodWaitError as e:
                    errors.append(f"Rate limited, wait {e.seconds}s")
                    break
                except Exception as e:
                    errors.append(f"Failed to terminate {auth.device_model}: {str(e)}")

            return TerminateResult(
                success=terminated > 0 or not errors,
                terminated_count=terminated,
                total_other_sessions=len(other_sessions),
                errors=errors,
            )

        except Exception as e:
            return TerminateResult(success=False, errors=[str(e)])
        finally:
            if client:
                try:
                    await client.disconnect()
                except Exception:
                    pass


# Singleton
session_service = SessionService()
