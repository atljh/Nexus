"""
Telegram profile management service.
Provides methods to update name, bio, username, and profile photo.
"""

import asyncio
import logging
import random
from typing import Optional, Dict, Tuple, List
from dataclasses import dataclass, field

from .telegram_client import TelegramClient
from .session_manager import SessionManager
from .device_generator import OFFICIAL_APIS

from telethon.tl.functions.account import UpdateProfileRequest, UpdateUsernameRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest, DeletePhotosRequest
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.types import InputUserSelf
from telethon.errors import (
    FirstNameInvalidError,
    AboutTooLongError,
    UsernameOccupiedError,
    UsernameInvalidError,
    UsernameNotModifiedError,
    FloodWaitError,
)

logger = logging.getLogger(__name__)


@dataclass
class ProfileUpdateResult:
    """Result of a profile update operation."""
    success: bool
    updated_fields: List[str] = field(default_factory=list)
    errors: Dict[str, str] = field(default_factory=dict)
    new_values: Dict[str, str] = field(default_factory=dict)


class ProfileService:
    """
    Manages Telegram profile operations.

    Methods:
        update_profile: Update name, bio, username in Telegram
        get_current_profile: Get current profile info from Telegram
    """

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

    async def update_profile(
        self,
        session_string: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        bio: Optional[str] = None,
        username: Optional[str] = None,
        proxy: Optional[Dict] = None,
        api_id: Optional[int] = None,
        api_hash: Optional[str] = None,
        device_fingerprint: Optional[Dict] = None,
    ) -> ProfileUpdateResult:
        """
        Update Telegram profile fields.
        Only provided (non-None) fields will be updated.
        Uses random order and delays between operations for human-like behavior.
        """
        client = None
        result = ProfileUpdateResult(success=True)

        try:
            client = self._create_client(
                session_string, proxy, api_id, api_hash, device_fingerprint
            )
            await client.connect()

            if not await client.is_user_authorized():
                return ProfileUpdateResult(
                    success=False,
                    errors={"auth": "Session not authorized"}
                )

            # Simulate "opening app"
            try:
                await client.get_dialogs(limit=3)
                await asyncio.sleep(random.uniform(0.3, 0.8))
            except Exception:
                pass

            # Build operations list
            operations = []

            if first_name is not None or last_name is not None:
                operations.append(("name", first_name, last_name))

            if bio is not None:
                operations.append(("bio", bio))

            if username is not None:
                operations.append(("username", username))

            # Random order for human-like behavior
            random.shuffle(operations)

            for i, op in enumerate(operations):
                if i > 0:
                    await asyncio.sleep(random.uniform(0.5, 1.5))

                op_type = op[0]

                try:
                    if op_type == "name":
                        _, fn, ln = op
                        kwargs = {}
                        if fn is not None:
                            kwargs["first_name"] = fn[:64]
                        if ln is not None:
                            kwargs["last_name"] = ln[:64]
                        await client(UpdateProfileRequest(**kwargs))
                        if fn is not None:
                            result.updated_fields.append("first_name")
                            result.new_values["first_name"] = fn[:64]
                        if ln is not None:
                            result.updated_fields.append("last_name")
                            result.new_values["last_name"] = ln[:64]

                    elif op_type == "bio":
                        bio_text = op[1][:140]
                        await client(UpdateProfileRequest(about=bio_text))
                        result.updated_fields.append("bio")
                        result.new_values["bio"] = bio_text

                    elif op_type == "username":
                        uname = op[1]
                        if uname == "":
                            # Remove username
                            await client(UpdateUsernameRequest(""))
                        else:
                            await client(UpdateUsernameRequest(uname))
                        result.updated_fields.append("username")
                        result.new_values["username"] = uname

                except FirstNameInvalidError:
                    result.errors["name"] = "Invalid first name"
                    result.success = False
                except AboutTooLongError:
                    result.errors["bio"] = "Bio too long"
                    result.success = False
                except UsernameOccupiedError:
                    result.errors["username"] = "Username already taken"
                    result.success = False
                except UsernameInvalidError:
                    result.errors["username"] = "Invalid username format"
                    result.success = False
                except UsernameNotModifiedError:
                    # Username is already set to this value — treat as success
                    result.updated_fields.append("username")
                    result.new_values["username"] = op[1]
                except FloodWaitError as e:
                    result.errors[op_type] = f"Rate limited, wait {e.seconds}s"
                    result.success = False
                except Exception as e:
                    result.errors[op_type] = str(e)
                    result.success = False

            return result

        except Exception as e:
            return ProfileUpdateResult(success=False, errors={"connection": str(e)})
        finally:
            if client:
                try:
                    await client.disconnect()
                except Exception:
                    pass

    async def get_current_profile(
        self,
        session_string: str,
        proxy: Optional[Dict] = None,
        api_id: Optional[int] = None,
        api_hash: Optional[str] = None,
        device_fingerprint: Optional[Dict] = None,
    ) -> Dict:
        """Fetch current profile data from Telegram."""
        client = None
        try:
            client = self._create_client(
                session_string, proxy, api_id, api_hash, device_fingerprint
            )
            await client.connect()

            if not await client.is_user_authorized():
                return {"error": "Session not authorized"}

            full = await client(GetFullUserRequest(InputUserSelf()))
            user = full.users[0]

            return {
                "first_name": user.first_name or "",
                "last_name": user.last_name or "",
                "username": user.username or "",
                "bio": full.full_user.about or "",
                "is_premium": bool(user.premium),
            }

        except Exception as e:
            return {"error": str(e)}
        finally:
            if client:
                try:
                    await client.disconnect()
                except Exception:
                    pass


# Singleton
profile_service = ProfileService()
