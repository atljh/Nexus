"""
Session Converter: Telethon StringSession to Telegram Web K Format

Converts Telethon StringSession to the JSON format used by Telegram Web K (localStorage format)
Adapted for Nexus desktop app from GramGPT reference implementation.
"""

import struct
import time
import logging
from hashlib import sha1
from typing import Optional, Dict, Any

from telethon.sessions import StringSession
from telethon import TelegramClient

logger = logging.getLogger(__name__)


class StringSessionToWebKConverter:
    """
    Converts Telethon StringSession to Telegram Web K localStorage format
    """

    def __init__(self, session_string: str):
        """
        Initialize converter with StringSession string

        Args:
            session_string: Telethon StringSession string (base64 encoded)
        """
        self.session_string = session_string
        self._session: Optional[StringSession] = None
        self._parsed = False

    def _parse_session(self) -> bool:
        """Parse the StringSession to extract auth data"""
        if self._parsed:
            return self._session is not None

        try:
            self._session = StringSession(self.session_string)

            # Validate that session has required data
            if not hasattr(self._session, '_dc_id') or not self._session._dc_id:
                logger.error("StringSession does not contain DC ID")
                return False

            if not hasattr(self._session, '_auth_key') or not self._session._auth_key:
                logger.error("StringSession does not contain auth_key")
                return False

            self._parsed = True
            return True

        except Exception as e:
            logger.error(f"Failed to parse StringSession: {e}")
            self._parsed = True
            return False

    def _calculate_auth_key_fingerprint(self, auth_key: bytes) -> str:
        """
        Calculate auth_key fingerprint for Telegram Web K

        Args:
            auth_key: Auth key bytes (256 bytes)

        Returns:
            Hex string of last 8 bytes from SHA1 hash
        """
        try:
            # Calculate SHA1 hash of auth_key
            key_hash = sha1(auth_key).digest()

            # Take last 8 bytes in little-endian order
            fingerprint_bytes = key_hash[-8:]

            # Convert to hex string (reversed for little-endian)
            fingerprint = "".join(f"{b:02x}" for b in reversed(fingerprint_bytes))

            return fingerprint

        except Exception as e:
            logger.error(f"Failed to calculate fingerprint: {e}")
            return "0" * 16

    def convert_to_webk_format(
        self,
        user_id: Optional[int] = None,
        server_salt: Optional[bytes] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Convert StringSession to Telegram Web K localStorage format

        Args:
            user_id: Telegram user ID (required for full session)
            server_salt: Optional server salt bytes (8 bytes). If not provided, uses zero salt.

        Returns:
            Dictionary with Web K format data or None if conversion failed
        """
        if not self._parse_session():
            return None

        dc_id = self._session._dc_id
        auth_key_obj = self._session._auth_key

        # Get raw bytes from AuthKey object if needed
        if hasattr(auth_key_obj, 'key'):
            auth_key = auth_key_obj.key
        else:
            auth_key = auth_key_obj

        # Validate auth_key length (must be 256 bytes)
        if len(auth_key) != 256:
            logger.error(f"Invalid auth_key length: {len(auth_key)} bytes (expected 256)")
            return None

        # Use provided salt or zero salt (will be updated by Telegram on first connection)
        if server_salt is None or len(server_salt) != 8:
            logger.warning("Using zero salt (will be updated on first connection)")
            server_salt = b"\x00" * 8

        # Calculate auth_key fingerprint
        auth_key_fingerprint = self._calculate_auth_key_fingerprint(auth_key)

        # Convert auth_key and server_salt to arrays (Web K format)
        auth_key_array = list(auth_key)
        server_salt_array = list(server_salt)

        # Convert to hex for account1 object
        auth_key_hex = "".join(f"{b:02x}" for b in auth_key)
        server_salt_hex = "".join(f"{b:02x}" for b in server_salt)

        # Create Web K format
        webk_data = {
            "dc": dc_id,
            f"dc{dc_id}_auth_key": auth_key_array,
            f"dc{dc_id}_server_salt": server_salt_array,
        }

        # Add user_auth if user_id is provided
        if user_id:
            webk_data["user_auth"] = {
                "dcID": dc_id,
                "id": user_id,
            }

            # Add account1 object (required for proper Web K session)
            webk_data["account1"] = {
                f"dc{dc_id}_auth_key": auth_key_hex,
                f"dc{dc_id}_server_salt": server_salt_hex,
                "auth_key_fingerprint": auth_key_fingerprint,
                "dcId": dc_id,
                "date": int(time.time()),
                "userId": user_id,
            }

            webk_data["auth_key_fingerprint"] = auth_key_fingerprint

        logger.info(
            f"Session converted: DC{dc_id}, user_id={user_id}, fingerprint={auth_key_fingerprint[:8]}..."
        )
        return webk_data

    async def convert_with_real_salt(
        self,
        api_id: int,
        api_hash: str,
        user_id: Optional[int] = None,
        proxy: Optional[Dict[str, Any]] = None,
        device_fingerprint: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Convert StringSession to Web K format with REAL server_salt from Telegram.

        Connects to Telegram to fetch the current server_salt, which fixes
        AUTH_KEY_UNREGISTERED errors that occur with zero/heuristic salt.

        Args:
            api_id: Telegram API ID
            api_hash: Telegram API hash
            user_id: Optional Telegram user ID (will be fetched if not provided)
            proxy: Optional proxy configuration dict
            device_fingerprint: Optional device fingerprint dict

        Returns:
            Dictionary with Web K format data or None if conversion failed
        """
        if not self._parse_session():
            return None

        dc_id = self._session._dc_id
        auth_key_obj = self._session._auth_key

        # Get raw bytes from AuthKey object if needed
        if hasattr(auth_key_obj, 'key'):
            auth_key = auth_key_obj.key
        else:
            auth_key = auth_key_obj

        if len(auth_key) != 256:
            logger.error(f"Invalid auth_key length: {len(auth_key)} bytes (expected 256)")
            return None

        real_server_salt = None

        try:
            logger.info("Connecting to Telegram to fetch real server_salt...")

            # Build client kwargs with device fingerprint
            client_kwargs = {
                "api_id": api_id,
                "api_hash": api_hash,
            }

            # Apply device fingerprint if provided
            if device_fingerprint:
                if device_fingerprint.get("device_model"):
                    client_kwargs["device_model"] = device_fingerprint["device_model"]
                if device_fingerprint.get("system_version"):
                    client_kwargs["system_version"] = device_fingerprint["system_version"]
                if device_fingerprint.get("app_version"):
                    client_kwargs["app_version"] = device_fingerprint["app_version"]
                if device_fingerprint.get("lang_code"):
                    client_kwargs["lang_code"] = device_fingerprint["lang_code"]
                if device_fingerprint.get("system_lang_code"):
                    client_kwargs["system_lang_code"] = device_fingerprint["system_lang_code"]

            # Convert proxy format for Telethon
            telethon_proxy = None
            skip_connection = False

            if proxy:
                proxy_type = proxy.get("type", "socks5").lower()
                if proxy_type in ("socks5", "socks4"):
                    import socks
                    telethon_proxy = (
                        socks.SOCKS5 if proxy_type == "socks5" else socks.SOCKS4,
                        proxy["host"],
                        proxy["port"],
                        True,  # rdns
                        proxy.get("username"),
                        proxy.get("password"),
                    )
                elif proxy_type in ("http", "https"):
                    # HTTP proxies have limited support in Telethon for async connections
                    # Skip salt fetch and use zero salt - Telegram will update it on first real connection
                    logger.info("HTTP proxy detected, skipping salt fetch (will use zero salt)")
                    skip_connection = True

            if skip_connection:
                # Return session with zero salt for HTTP proxies
                return self.convert_to_webk_format(user_id=user_id, server_salt=None)

            if telethon_proxy:
                client_kwargs["proxy"] = telethon_proxy

            # Create client with StringSession
            client = TelegramClient(
                StringSession(self.session_string),
                **client_kwargs
            )

            await client.connect()

            try:
                if not await client.is_user_authorized():
                    logger.warning("Session not authorized during salt fetch, using zero salt")
                else:
                    # Get user info if not provided
                    if not user_id:
                        me = await client.get_me()
                        user_id = me.id
                        logger.info(f"Fetched user_id: {user_id}")

                    # Extract REAL server_salt from Telethon's internal state
                    if hasattr(client, "_sender") and client._sender:
                        sender = client._sender

                        # Try different paths to get salt
                        if hasattr(sender, "state") and hasattr(sender.state, "salt"):
                            salt = sender.state.salt
                            if isinstance(salt, int):
                                real_server_salt = salt.to_bytes(8, byteorder="little", signed=True)
                            else:
                                real_server_salt = salt
                            logger.info(f"Extracted server_salt from sender.state")
                        elif hasattr(sender, "_state") and hasattr(sender._state, "salt"):
                            salt = sender._state.salt
                            if isinstance(salt, int):
                                real_server_salt = salt.to_bytes(8, byteorder="little", signed=True)
                            else:
                                real_server_salt = salt
                            logger.info(f"Extracted server_salt from sender._state")
            finally:
                await client.disconnect()

        except Exception as e:
            logger.error(f"Failed to fetch real server_salt: {e}")
            logger.warning("Falling back to zero salt")

        # Use zero salt as fallback
        if not real_server_salt:
            real_server_salt = b"\x00" * 8

        return self.convert_to_webk_format(user_id=user_id, server_salt=real_server_salt)


async def convert_account_to_webk(
    session_string: str,
    telegram_id: int,
    api_id: int,
    api_hash: str,
    proxy: Optional[Dict[str, Any]] = None,
    device_fingerprint: Optional[Dict[str, Any]] = None,
    fetch_real_salt: bool = True,
) -> Optional[Dict[str, Any]]:
    """
    Convenience function to convert account session to WebK format.

    Args:
        session_string: Telethon StringSession string
        telegram_id: Telegram user ID
        api_id: Telegram API ID
        api_hash: Telegram API hash
        proxy: Optional proxy configuration
        device_fingerprint: Optional device fingerprint
        fetch_real_salt: Whether to connect to Telegram for real salt (recommended)

    Returns:
        Dictionary with WebK format or None if conversion failed
    """
    converter = StringSessionToWebKConverter(session_string)

    if fetch_real_salt and api_id and api_hash:
        return await converter.convert_with_real_salt(
            api_id=api_id,
            api_hash=api_hash,
            user_id=telegram_id,
            proxy=proxy,
            device_fingerprint=device_fingerprint,
        )
    else:
        return converter.convert_to_webk_format(user_id=telegram_id)
