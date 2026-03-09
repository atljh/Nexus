"""
Tests for account metadata resolution helpers.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from telegram.account_metadata import (
    extract_api_credentials,
    extract_device_fingerprint,
    resolve_account_connection_params,
)


class DummyAccount:
    def __init__(self, **kwargs):
        self.api_id = kwargs.get("api_id")
        self.api_hash = kwargs.get("api_hash")
        self.device_fingerprint = kwargs.get("device_fingerprint")
        self.extra_data = kwargs.get("extra_data")


def test_extract_api_credentials_supports_aliases():
    api_id, api_hash = extract_api_credentials(
        {"app_id": "2040", "app_hash": "b18441a1ff607e10a989891a5462e627"}
    )
    assert api_id == 2040
    assert api_hash == "b18441a1ff607e10a989891a5462e627"


def test_extract_device_fingerprint_supports_aliases():
    fp = extract_device_fingerprint(
        {
            "device": "Desktop",
            "sdk": "Windows 10",
            "app_version": "5.2.0 x64",
            "lang_pack": "uk",
            "system_lang_pack": "uk-UA",
        }
    )
    assert fp["device_model"] == "Desktop"
    assert fp["system_version"] == "Windows 10"
    assert fp["app_version"] == "5.2.0 x64"
    assert fp["lang_code"] == "uk"
    assert fp["system_lang_code"] == "uk-UA"


def test_resolve_account_connection_params_uses_extra_data_fallback():
    acc = DummyAccount(
        api_id=None,
        api_hash=None,
        device_fingerprint="null",
        extra_data={
            "app_id": 2040,
            "app_hash": "b18441a1ff607e10a989891a5462e627",
            "device": "Desktop",
            "sdk": "Windows 11",
            "app_version": "5.3.1 x64",
            "lang_pack": "en",
            "system_lang_pack": "en-us",
        },
    )

    api_id, api_hash, fp = resolve_account_connection_params(acc)

    assert api_id == 2040
    assert api_hash == "b18441a1ff607e10a989891a5462e627"
    assert fp["device_model"] == "Desktop"
    assert fp["system_version"] == "Windows 11"
    assert fp["app_version"] == "5.3.1 x64"
