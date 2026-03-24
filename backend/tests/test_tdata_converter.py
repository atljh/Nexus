"""Tests for telegram.tdata_converter helpers."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from telegram.device_generator import ANDROID_DEVICES
from telegram.tdata_converter import build_tdata_device_fingerprint


def test_build_tdata_device_fingerprint_uses_stable_tdesktop_defaults():
    fp = build_tdata_device_fingerprint(api_id=2040, unique_id="session-seed")

    assert fp["device_model"] == "Desktop"
    assert fp["system_version"] == "Windows 10"
    assert fp["app_version"].endswith(" x64")
    assert fp["lang_code"] == "en"
    assert fp["system_lang_code"] == "en-US"


def test_build_tdata_device_fingerprint_keeps_custom_api_platform():
    fp = build_tdata_device_fingerprint(
        api_id=6,
        unique_id="session-seed",
        lang_code="uk",
        system_lang_code="uk-UA",
    )

    assert fp["device_model"] in [device["device_model"] for device in ANDROID_DEVICES]
    assert fp["system_version"].startswith("SDK ")
    assert fp["lang_code"] == "uk"
    assert fp["system_lang_code"] == "uk-UA"
