"""
TData to Session converter
Converts Telegram Desktop tdata to Telethon session
"""

import json
import os
import sqlite3
import asyncio
import shutil
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple

from telethon.sessions import StringSession
from telethon.crypto import AuthKey

from .client import BaseClient
from .exceptions import TDataError, UnauthorizedError, SessionExpiredError

logger = logging.getLogger("nexus.tdata_converter")


class TDataConverter:
    """
    Converter tdata -> session + metadata

    Uses tdesktop-decrypter for extracting auth_key from tdata,
    then creates Telethon session directly via SQLite.
    """

    # Telegram DC servers (official addresses)
    DC_SERVERS = {
        1: ("149.154.175.53", 443),
        2: ("149.154.167.41", 443),
        3: ("149.154.175.100", 443),
        4: ("149.154.167.92", 443),
        5: ("91.108.56.130", 443),
    }

    DEFAULT_API_ID = 2040
    DEFAULT_API_HASH = "b18441a1ff607e10a989891a5462e627"

    async def convert_tdata(
        self,
        tdata_path: str,
        proxy: Optional[Dict] = None,
        api_id: Optional[int] = None,
        api_hash: Optional[str] = None,
    ) -> Tuple[str, Dict]:
        """
        Convert tdata to session string and metadata.

        Args:
            tdata_path: Path to tdata folder
            proxy: Proxy config (optional for local desktop app)
            api_id: Telegram API ID
            api_hash: Telegram API Hash

        Returns:
            Tuple[session_string, metadata_dict]

        Raises:
            TDataError: If conversion fails
        """
        api_id = api_id or self.DEFAULT_API_ID
        api_hash = api_hash or self.DEFAULT_API_HASH

        logger.info(f"Starting tdata conversion: {tdata_path}")

        # Extract data using tdesktop-decrypter
        tdata_info = await self._extract_tdata_info(tdata_path)

        if not tdata_info.get("accounts"):
            raise TDataError(
                "No accounts found in tdata.\n\n"
                "Possible reasons:\n"
                "1. Telegram Desktop is not logged in\n"
                "2. TData folder is incomplete or corrupted\n"
                "3. Wrong folder uploaded (should be 'tdata' folder)\n\n"
                "How to fix:\n"
                "1. Open Telegram Desktop and log in\n"
                "2. Close Telegram Desktop completely\n"
                "3. Export the tdata folder:\n"
                "   - Windows: %APPDATA%\\Telegram Desktop\\tdata\n"
                "   - macOS: ~/Library/Application Support/Telegram Desktop/tdata\n"
                "   - Linux: ~/.local/share/TelegramDesktop/tdata\n"
                "4. Upload the complete tdata folder"
            )

        # Use first account
        account_data = tdata_info["accounts"][0]
        logger.info(f"Found account: user_id={account_data.get('user_id')}")

        # Create session in temp file
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_session_path = Path(temp_dir) / "temp.session"

            # Create SQLite session file
            await self._create_telethon_session(account_data, temp_session_path)

            # Convert to string session and validate
            session_string = self._sqlite_to_string_session(temp_session_path)

            # Try to connect and get user info
            metadata = await self._validate_and_get_info(
                session_string, api_id, api_hash, proxy
            )

        logger.info("TData conversion completed successfully")
        return session_string, metadata

    async def _extract_tdata_info(
        self, tdata_path: str, passcode: Optional[str] = None
    ) -> Dict:
        """
        Extract info from tdata using tdesktop-decrypter.

        Args:
            tdata_path: Path to tdata folder
            passcode: Optional local passcode

        Returns:
            Dict with account info

        Raises:
            TDataError: On extraction errors
        """
        tdata_path = Path(tdata_path)

        # Check if path ends with 'tdata', try to find it inside
        if tdata_path.name != "tdata":
            potential_tdata = tdata_path / "tdata"
            if potential_tdata.exists():
                tdata_path = potential_tdata

        if not tdata_path.exists():
            raise TDataError(f"TData folder not found: {tdata_path}")

        logger.info(f"Extracting data from: {tdata_path}")

        # Find tdesktop-decrypter
        tdesktop_cmd = self._find_tdesktop_decrypter()

        # Build command
        cmd = [str(tdesktop_cmd), str(tdata_path), "-j"]
        if passcode:
            cmd.extend(["-p", passcode])

        try:
            result = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(
                result.communicate(), timeout=60.0
            )

            if result.returncode != 0:
                error_msg = stderr.decode("utf-8", errors="ignore").strip()

                if "passcode" in error_msg.lower() or "password" in error_msg.lower():
                    raise TDataError(
                        "TData is protected with a local passcode.\n\n"
                        "How to fix:\n"
                        "1. Open Telegram Desktop\n"
                        "2. Go to Settings -> Privacy & Security\n"
                        "3. Find 'Local Passcode' and turn it off\n"
                        "4. Restart Telegram Desktop\n"
                        "5. Close Telegram Desktop completely\n"
                        "6. Export the tdata folder again"
                    )
                elif "not found" in error_msg.lower() or "no such file" in error_msg.lower():
                    raise TDataError(
                        "Required files missing in tdata folder.\n\n"
                        "The folder should contain:\n"
                        "  - key_data or key_datas file\n"
                        "  - D877xxxxx folders\n\n"
                        "Make sure to export the complete tdata folder.\n"
                        "Close Telegram Desktop before copying."
                    )
                else:
                    raise TDataError(f"tdesktop-decrypter failed: {error_msg}")

            # Parse JSON output
            try:
                data = json.loads(stdout.decode("utf-8"))
                logger.info(f"Found {len(data.get('accounts', []))} accounts")
                return data
            except json.JSONDecodeError as e:
                raise TDataError(f"Failed to parse tdesktop-decrypter output: {e}")

        except asyncio.TimeoutError:
            raise TDataError(
                "TData extraction timed out (60 seconds).\n\n"
                "This can happen when:\n"
                "- TData folder is very large\n"
                "- System is under heavy load\n\n"
                "Try again in a few minutes."
            )
        except FileNotFoundError:
            raise TDataError(
                "tdesktop-decrypter not found. Install it with:\n"
                "pip install tdesktop-decrypter"
            )

    def _find_tdesktop_decrypter(self) -> Path:
        """Find tdesktop-decrypter executable."""
        import sys

        # Try in same venv as current Python
        python_bin = Path(sys.executable).parent
        tdesktop_cmd = python_bin / "tdesktop-decrypter"

        if tdesktop_cmd.exists():
            return tdesktop_cmd

        # Fallback: use PATH
        system_cmd = shutil.which("tdesktop-decrypter")
        if system_cmd:
            return Path(system_cmd)

        raise FileNotFoundError("tdesktop-decrypter not found")

    async def _create_telethon_session(
        self, account_data: Dict, output_path: Path
    ) -> None:
        """
        Create Telethon session file from account data.

        Args:
            account_data: Account data from tdesktop-decrypter
            output_path: Path for saving .session file
        """
        user_id = account_data["user_id"]
        dc_id = account_data["main_dc_id"]

        # Get auth_key for main DC
        dc_auth_keys = account_data.get("dc_auth_keys", {})
        auth_key_hex = dc_auth_keys.get(str(dc_id))

        if not auth_key_hex:
            raise TDataError(f"No auth key found for DC {dc_id}")

        auth_key = bytes.fromhex(auth_key_hex)

        logger.info(f"Creating session: user_id={user_id}, dc_id={dc_id}")

        # Get server address
        server_address, port = self.DC_SERVERS.get(
            dc_id, (f"dc{dc_id}.telegram.org", 443)
        )

        # Create SQLite database for Telethon
        conn = sqlite3.connect(str(output_path))
        c = conn.cursor()

        # Create tables (Telethon session v8 structure)
        c.execute("""
            CREATE TABLE sessions (
                dc_id INTEGER PRIMARY KEY,
                server_address TEXT,
                port INTEGER,
                auth_key BLOB,
                takeout_id INTEGER
            )
        """)

        c.execute("""
            CREATE TABLE entities (
                id INTEGER PRIMARY KEY,
                hash INTEGER NOT NULL,
                username TEXT,
                phone INTEGER,
                name TEXT,
                date INTEGER
            )
        """)

        c.execute("""
            CREATE TABLE sent_files (
                md5_digest BLOB,
                file_size INTEGER,
                type INTEGER,
                id INTEGER,
                hash INTEGER,
                PRIMARY KEY(md5_digest, file_size, type)
            )
        """)

        c.execute("""
            CREATE TABLE update_state (
                id INTEGER PRIMARY KEY,
                pts INTEGER,
                qts INTEGER,
                date INTEGER,
                seq INTEGER
            )
        """)

        c.execute("""
            CREATE TABLE version (
                version INTEGER PRIMARY KEY
            )
        """)

        # Session format version (8 for Telethon 1.x)
        c.execute("INSERT INTO version VALUES (8)")

        # Insert session data
        c.execute(
            "INSERT INTO sessions VALUES (?, ?, ?, ?, ?)",
            (dc_id, server_address, port, auth_key, None),
        )

        conn.commit()
        conn.close()

        logger.info(f"Session file created: {output_path}")

    def _sqlite_to_string_session(self, session_path: Path) -> str:
        """
        Convert SQLite session to StringSession directly.

        Args:
            session_path: Path to .session file

        Returns:
            StringSession string
        """
        logger.info("Converting SQLite session to StringSession...")

        # Read session data from SQLite
        conn = sqlite3.connect(str(session_path))
        c = conn.cursor()

        c.execute("SELECT dc_id, server_address, port, auth_key FROM sessions")
        row = c.fetchone()
        conn.close()

        if not row:
            raise TDataError("No session data found in SQLite file")

        dc_id, server_address, port, auth_key = row

        # Create StringSession directly
        string_session = StringSession()
        string_session._dc_id = dc_id
        string_session._server_address = server_address
        string_session._port = port
        string_session._auth_key = AuthKey(data=auth_key)
        string_session._takeout_id = None

        session_string = string_session.save()
        logger.info(f"StringSession created (length: {len(session_string)})")

        return session_string

    async def _validate_and_get_info(
        self,
        session_string: str,
        api_id: int,
        api_hash: str,
        proxy: Optional[Dict],
    ) -> Dict:
        """
        Validate session and get user info.

        Args:
            session_string: Telethon session string
            api_id: API ID
            api_hash: API Hash
            proxy: Proxy config

        Returns:
            Metadata dict with user info
        """
        client = BaseClient(
            session_string=session_string,
            api_id=api_id,
            api_hash=api_hash,
            proxy=proxy,
            connection_retries=3,
            timeout=10,
        )

        # Test proxy before connecting to Telegram
        if proxy:
            logger.info("Testing proxy before Telegram connection...")
            proxy_test = await client._test_proxy_connection()
            if not proxy_test.get("success"):
                error_msg = proxy_test.get("error", "Unknown error")
                proxy_type = proxy.get("type") or proxy.get("proxy_type") or "unknown"
                proxy_addr = proxy.get("host") or proxy.get("addr") or "unknown"
                proxy_port = proxy.get("port", "")
                raise TDataError(
                    f"Proxy is not working: {error_msg}\n\n"
                    f"Proxy: {proxy_type}://{proxy_addr}:{proxy_port}\n\n"
                    "Please check:\n"
                    "1. Proxy is online and accessible\n"
                    "2. Username and password are correct\n"
                    "3. Proxy supports Telegram connections (CONNECT for HTTP)"
                )
            logger.info(f"Proxy test passed ({proxy_test.get('response_time', 0):.2f}s)")

        try:
            async with client:
                await client.check_auth()
                me = await client.get_me()

                if not me:
                    raise TDataError("Failed to get user info from Telegram")

                logger.info(f"User: {me.id} (@{me.username})")

                # Get bio via GetFullUserRequest
                user_bio = ""
                try:
                    from telethon.tl.functions.users import GetFullUserRequest
                    from telethon.tl.types import InputUserSelf

                    full_user_result = await client.client(
                        GetFullUserRequest(InputUserSelf())
                    )
                    if full_user_result and full_user_result.full_user:
                        user_bio = getattr(full_user_result.full_user, "about", None) or ""
                        logger.info(f"Bio retrieved: {len(user_bio)} chars")
                except Exception as bio_err:
                    logger.warning(f"Could not retrieve bio: {bio_err}")

                return {
                    "telegram_id": me.id,
                    "username": me.username,
                    "first_name": me.first_name,
                    "last_name": me.last_name,
                    "phone": me.phone,
                    "bio": user_bio,
                    "is_bot": getattr(me, "bot", False),
                    "is_verified": getattr(me, "verified", False),
                    "is_premium": getattr(me, "premium", False),
                    "session_string": session_string,
                    "api_id": api_id,
                    "api_hash": api_hash,
                    "device_fingerprint": {},
                    "source": "tdata",
                    "converter_version": "tdesktop-decrypter",
                }

        except (UnauthorizedError, SessionExpiredError) as e:
            raise TDataError(
                f"TData converted successfully, but the account is invalid.\n\n"
                f"Error: {e}\n\n"
                "This means:\n"
                "- The TData is old or the account was logged out\n"
                "- You need to re-authorize in Telegram Desktop\n"
                "- Or use a different, active TData folder"
            )
        except TDataError:
            raise
        except Exception as e:
            if "proxy" in str(e).lower() or "connection" in str(e).lower():
                raise TDataError(
                    f"Connection error during validation.\n\n"
                    "Possible causes:\n"
                    "- Proxy is not working or offline\n"
                    "- Proxy is blocked or doesn't support Telegram\n"
                    "- Invalid proxy credentials\n\n"
                    "Try using a SOCKS5 proxy instead of HTTP."
                )
            raise


    async def convert_and_save(
        self,
        tdata_path: str,
        output_dir: str,
        proxy: Optional[Dict] = None,
        api_id: Optional[int] = None,
        api_hash: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Convert tdata and save session + JSON to files.

        Args:
            tdata_path: Path to tdata folder
            output_dir: Directory for saving output files
            proxy: Proxy config
            api_id: API ID
            api_hash: API Hash

        Returns:
            Tuple[session_file_path, json_file_path]
        """
        session_string, metadata = await self.convert_tdata(
            tdata_path, proxy, api_id, api_hash
        )

        os.makedirs(output_dir, exist_ok=True)

        phone = metadata.get("phone", "unknown")
        session_file = os.path.join(output_dir, f"{phone}.session")
        json_file = os.path.join(output_dir, f"{phone}.json")

        with open(session_file, "w") as f:
            f.write(session_string)

        with open(json_file, "w") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        logger.info(f"Files saved: {session_file}, {json_file}")
        return session_file, json_file


class SimpleTDataConverter:
    """
    Simplified tdata validator for quick structure checks.
    No network operations — only validates local file structure.
    """

    @staticmethod
    async def extract_session_from_tdata(
        tdata_path: str, phone_number: str
    ) -> Optional[Dict]:
        """
        Validate tdata structure and return basic info.

        Args:
            tdata_path: Path to tdata folder
            phone_number: Phone number of the account

        Returns:
            Dict with validation info, or None if invalid
        """
        tdata_dir = Path(tdata_path)

        if not tdata_dir.exists():
            return None

        # Look for key_data or key_datas
        has_key_file = False
        for key_file in ["key_data", "key_datas"]:
            if (tdata_dir / key_file).exists():
                has_key_file = True
                break

        if not has_key_file:
            # Check nested tdata subfolder
            tdata_subdir = tdata_dir / "tdata"
            if tdata_subdir.exists():
                for key_file in ["key_data", "key_datas"]:
                    if (tdata_subdir / key_file).exists():
                        has_key_file = True
                        break

        if not has_key_file:
            return None

        return {
            "tdata_path": str(tdata_path),
            "phone_number": phone_number,
            "has_key_file": True,
            "requires_conversion": True,
            "message": "TData found but needs full conversion with tdesktop-decrypter",
        }


async def convert_tdata_to_session(
    tdata_path: str,
    proxy: Optional[Dict] = None,
    api_id: Optional[int] = None,
    api_hash: Optional[str] = None,
) -> Tuple[str, Dict]:
    """
    Quick function to convert tdata to session.

    Args:
        tdata_path: Path to tdata folder
        proxy: Proxy config
        api_id: API ID
        api_hash: API Hash

    Returns:
        Tuple[session_string, metadata]
    """
    converter = TDataConverter()
    return await converter.convert_tdata(tdata_path, proxy, api_id, api_hash)


async def parse_tdata_to_session(tdata_path: str) -> str:
    """
    Parse tdata folder and extract session string WITHOUT validation.
    Use this for initial parsing when proxy is not yet assigned.

    Args:
        tdata_path: Path to tdata folder

    Returns:
        session_string (without connecting to Telegram)
    """
    converter = TDataConverter()

    logger.info(f"Parsing tdata (no validation): {tdata_path}")

    # Extract data using tdesktop-decrypter
    tdata_info = await converter._extract_tdata_info(tdata_path)

    if not tdata_info.get("accounts"):
        raise TDataError(
            "No accounts found in tdata. "
            "Make sure Telegram Desktop is logged in and closed before export."
        )

    # Use first account
    account_data = tdata_info["accounts"][0]
    logger.info(f"Found account: user_id={account_data.get('user_id')}")

    # Create session in temp file
    import tempfile

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_session_path = Path(temp_dir) / "temp.session"

        # Create SQLite session file
        await converter._create_telethon_session(account_data, temp_session_path)

        # Convert to string session (no validation)
        session_string = converter._sqlite_to_string_session(temp_session_path)

    logger.info(f"Session string extracted (length: {len(session_string)})")
    return session_string
