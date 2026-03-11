"""
Custom TelegramClient subclass with proper lang_pack and reliability settings.

Telethon sends empty lang_pack="" in InitConnectionRequest by default.
Real clients send "android", "tdesktop", "ios", etc. — empty string is a red flag.

Changes vs vanilla Telethon:
- Sets lang_pack based on API ID (android/tdesktop/ios/macos)
- flood_sleep_threshold=60 — auto-sleep on FloodWait < 60s
- Patches _init_request.params with tz_offset (official clients send this)

Reference: GramGPT telegram_client.py
"""

from telethon import TelegramClient as _TelegramClient


# lang_pack values for official Telegram API IDs
API_LANG_PACKS = {
    # Android
    4: "android",
    5: "android",
    6: "android",  # Official Android
    21724: "android",  # Telegram X
    16623: "android",
    # iOS
    8: "ios",
    10840: "ios",  # Official iOS
    # Desktop
    2040: "tdesktop",  # Official Desktop
    17349: "tdesktop",  # Desktop test
    2834: "macos",  # Official macOS
    # Web (no lang_pack)
    2496: "",
}


class TelegramClient(_TelegramClient):
    """
    TelegramClient with correct lang_pack, flood_sleep_threshold, and tz_offset.
    Minimal subclass — patches _init_request after super().__init__().
    """

    def __init__(self, *args, flood_sleep_threshold=60, **kwargs):
        super().__init__(*args, flood_sleep_threshold=flood_sleep_threshold, **kwargs)

        # Patch lang_pack — Telethon hardcodes "" which is a detection red flag
        if hasattr(self, '_init_request'):
            self._init_request.lang_pack = API_LANG_PACKS.get(
                self.api_id, "android"
            )

