"""
Session Manager for Telegram sessions
Handles conversion between session formats
"""

import asyncio
from pathlib import Path
from typing import Optional, Dict

from telethon import TelegramClient
from telethon.sessions import StringSession

from .exceptions import SessionError
from .device_generator import OFFICIAL_APIS


class SessionManager:
    """
    Manager for Telegram sessions.

    Supports conversion between formats:
    - .session (SQLite) → StringSession
    - StringSession → data for DB
    """

    # Use Android official API (consistent with other modules)
    DEFAULT_API_ID = OFFICIAL_APIS["android"]["api_id"]  # 6
    DEFAULT_API_HASH = OFFICIAL_APIS["android"]["api_hash"]

    @classmethod
    async def session_file_to_string(
        cls,
        session_path: Path | str,
        api_id: Optional[int] = None,
        api_hash: Optional[str] = None,
    ) -> str:
        """
        Convert .session file to StringSession.

        Args:
            session_path: Path to .session file (Path or str)
            api_id: API ID (optional, uses default)
            api_hash: API Hash (optional, uses default)

        Returns:
            String session

        Raises:
            SessionError: If failed to read session
        """
        # Convert to Path if string
        if isinstance(session_path, str):
            session_path = Path(session_path)

        if not session_path.exists():
            raise SessionError(f"Session file not found: {session_path}")

        # Check if file contains a StringSession string (not SQLite)
        try:
            raw = session_path.read_bytes()
            # StringSession is a short base64 string (starts with '1'), typically < 512 bytes
            if len(raw) < 1024:
                text = raw.decode('utf-8', errors='ignore').strip()
                if text and cls.validate_session_string(text):
                    return text
        except Exception:
            pass

        try:
            api_id = api_id or cls.DEFAULT_API_ID
            api_hash = api_hash or cls.DEFAULT_API_HASH

            loop = asyncio.get_event_loop()
            client = TelegramClient(str(session_path), api_id, api_hash, loop=loop)

            string_session = StringSession()
            string_session._server_address = client.session.server_address
            string_session._takeout_id = client.session.takeout_id
            string_session._auth_key = client.session.auth_key
            string_session._dc_id = client.session.dc_id
            string_session._port = client.session.port

            session_string = string_session.save()

            # Explicitly close the SQLite session to release file lock (Windows)
            client.session.close()
            del string_session, client

            return session_string

        except Exception as e:
            raise SessionError(f"Session conversion error: {str(e)}")

    @staticmethod
    def string_to_session_data(session_string: str) -> Dict:
        """Extract session data from string session"""
        try:
            ss = StringSession(session_string)
            return {
                "dc_id": ss._dc_id,
                "server_address": ss._server_address,
                "port": ss._port,
                "auth_key": ss._auth_key.key if ss._auth_key else None,
            }
        except Exception as e:
            raise SessionError(f"Session string parse error: {str(e)}")

    @staticmethod
    def validate_session_string(session_string: str) -> bool:
        """Validate session string format"""
        try:
            ss = StringSession(session_string)
            return ss._dc_id is not None and ss._auth_key is not None
        except Exception:
            return False

    @classmethod
    async def batch_convert_to_string(
        cls,
        session_paths: list[Path],
        api_id: Optional[int] = None,
        api_hash: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Batch convert .session files to string sessions.

        Args:
            session_paths: List of paths to .session files
            api_id: API ID
            api_hash: API Hash

        Returns:
            Dict {filename: string_session}
        """
        results = {}

        for session_path in session_paths:
            try:
                session_string = await cls.session_file_to_string(
                    session_path, api_id, api_hash
                )
                results[session_path.name] = session_string
            except SessionError as e:
                results[session_path.name] = f"ERROR: {str(e)}"

        return results

    @staticmethod
    def create_memory_session(session_string: str) -> StringSession:
        """Create in-memory session from string"""
        return StringSession(session_string)
