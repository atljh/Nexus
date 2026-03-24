"""Tests for telegram.device_generator — device fingerprint generation."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from telegram.device_generator import (
    generate_device_fingerprint,
    detect_platform_from_api_id,
    generate_fingerprint_for_api,
    get_tdesktop_fingerprint,
    OFFICIAL_APIS,
    ANDROID_DEVICES,
    IOS_DEVICES,
    DESKTOP_DEVICES,
    APP_VERSIONS,
)


class TestGenerateDeviceFingerprint:
    """Tests for generate_device_fingerprint()."""

    def test_returns_dict_with_required_keys(self):
        fp = generate_device_fingerprint("test_id")
        assert "api_id" in fp
        assert "api_hash" in fp
        assert "device_model" in fp
        assert "system_version" in fp
        assert "app_version" in fp
        assert "lang_code" in fp
        assert "system_lang_code" in fp

    def test_consistency_same_id(self):
        """Same unique_id must always produce the same fingerprint."""
        fp1 = generate_device_fingerprint("+79001234567")
        fp2 = generate_device_fingerprint("+79001234567")
        assert fp1 == fp2

    def test_different_ids_may_differ(self):
        """Different unique_ids should generally produce different fingerprints."""
        fp1 = generate_device_fingerprint("phone_1")
        fp2 = generate_device_fingerprint("phone_2")
        # They might coincidentally match, but at least api_id should be the same
        # since both default to android
        assert fp1["api_id"] == fp2["api_id"]

    def test_android_platform(self):
        fp = generate_device_fingerprint("id", platform="android")
        assert fp["api_id"] == OFFICIAL_APIS["android"]["api_id"]
        assert fp["api_hash"] == OFFICIAL_APIS["android"]["api_hash"]

    def test_ios_platform(self):
        fp = generate_device_fingerprint("id", platform="ios")
        assert fp["api_id"] == OFFICIAL_APIS["ios"]["api_id"]
        assert fp["api_hash"] == OFFICIAL_APIS["ios"]["api_hash"]

    def test_desktop_platform(self):
        fp = generate_device_fingerprint("id", platform="desktop")
        assert fp["api_id"] == OFFICIAL_APIS["desktop"]["api_id"]
        assert fp["api_hash"] == OFFICIAL_APIS["desktop"]["api_hash"]

    def test_custom_lang_codes(self):
        fp = generate_device_fingerprint("id", lang_code="ru", system_lang_code="ru-RU")
        assert fp["lang_code"] == "ru"
        assert fp["system_lang_code"] == "ru-RU"

    def test_android_device_model_realistic(self):
        """Android device model should come from ANDROID_DEVICES list."""
        fp = generate_device_fingerprint("id", platform="android")
        models = [d["device_model"] for d in ANDROID_DEVICES]
        assert fp["device_model"] in models

    def test_ios_device_model_realistic(self):
        fp = generate_device_fingerprint("id", platform="ios")
        models = [d["device_model"] for d in IOS_DEVICES]
        assert fp["device_model"] in models

    def test_desktop_device_model_realistic(self):
        fp = generate_device_fingerprint("id", platform="desktop")
        models = [d["device_model"] for d in DESKTOP_DEVICES]
        assert fp["device_model"] in models

    def test_app_version_contains_platform_version(self):
        for platform in ("android", "ios", "desktop"):
            fp = generate_device_fingerprint("id", platform=platform)
            base_version = APP_VERSIONS[platform]
            assert base_version in fp["app_version"]


class TestGetTDesktopFingerprint:
    """Tests for get_tdesktop_fingerprint()."""

    def test_returns_stable_windows_tdesktop_defaults(self):
        fp = get_tdesktop_fingerprint()
        assert fp["api_id"] == OFFICIAL_APIS["desktop"]["api_id"]
        assert fp["api_hash"] == OFFICIAL_APIS["desktop"]["api_hash"]
        assert fp["device_model"] == "Desktop"
        assert fp["system_version"] == "Windows 10"
        assert fp["app_version"] == APP_VERSIONS["desktop"] + " x64"

    def test_respects_lang_codes(self):
        fp = get_tdesktop_fingerprint(lang_code="uk", system_lang_code="uk-UA")
        assert fp["lang_code"] == "uk"
        assert fp["system_lang_code"] == "uk-UA"


class TestDetectPlatformFromApiId:
    """Tests for detect_platform_from_api_id()."""

    def test_android_ids(self):
        for api_id in (4, 5, 6, 21724, 16623):
            assert detect_platform_from_api_id(api_id) == "android"

    def test_ios_ids(self):
        for api_id in (8, 10840):
            assert detect_platform_from_api_id(api_id) == "ios"

    def test_desktop_ids(self):
        for api_id in (2040, 17349, 2834, 2496):
            assert detect_platform_from_api_id(api_id) == "desktop"

    def test_unknown_defaults_android(self):
        assert detect_platform_from_api_id(99999) == "android"

    def test_zero_defaults_android(self):
        assert detect_platform_from_api_id(0) == "android"


class TestGenerateFingerprintForApi:
    """Tests for generate_fingerprint_for_api()."""

    def test_returns_device_params(self):
        result = generate_fingerprint_for_api("uid", api_id=6)
        assert "device_model" in result
        assert "system_version" in result
        assert "app_version" in result

    def test_consistency(self):
        r1 = generate_fingerprint_for_api("uid", api_id=6)
        r2 = generate_fingerprint_for_api("uid", api_id=6)
        assert r1 == r2

    def test_android_api_gets_android_device(self):
        result = generate_fingerprint_for_api("uid", api_id=6)
        models = [d["device_model"] for d in ANDROID_DEVICES]
        assert result["device_model"] in models

    def test_ios_api_gets_ios_device(self):
        result = generate_fingerprint_for_api("uid", api_id=10840)
        models = [d["device_model"] for d in IOS_DEVICES]
        assert result["device_model"] in models

    def test_desktop_api_gets_desktop_device(self):
        result = generate_fingerprint_for_api("uid", api_id=2040)
        models = [d["device_model"] for d in DESKTOP_DEVICES]
        assert result["device_model"] in models


class TestDeviceListsNotEmpty:
    """Ensure device lists contain entries."""

    def test_android_devices_not_empty(self):
        assert len(ANDROID_DEVICES) > 10

    def test_ios_devices_not_empty(self):
        assert len(IOS_DEVICES) > 5

    def test_desktop_devices_not_empty(self):
        assert len(DESKTOP_DEVICES) >= 3

    def test_all_android_have_required_keys(self):
        for d in ANDROID_DEVICES:
            assert "device_model" in d
            assert "system_version" in d

    def test_all_ios_have_required_keys(self):
        for d in IOS_DEVICES:
            assert "device_model" in d
            assert "system_version" in d

    def test_all_desktop_have_required_keys(self):
        for d in DESKTOP_DEVICES:
            assert "device_model" in d
            assert "system_version" in d

    def test_official_apis_have_all_platforms(self):
        for platform in ("android", "ios", "desktop"):
            assert platform in OFFICIAL_APIS
            assert "api_id" in OFFICIAL_APIS[platform]
            assert "api_hash" in OFFICIAL_APIS[platform]
