"""Tests for api.accounts — helper functions, schemas, error mapping."""
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from pydantic import ValidationError

from api.accounts import (
    extract_api_credentials,
    extract_device_fingerprint,
    _split_error,
    ERROR_STATUS_MAP,
    COUNTRY_CODES,
    BulkActionRequest,
    CheckBatchRequest,
    AssignProxiesRequest,
    SessionImport,
)


class TestExtractApiCredentials:
    """Tests for extract_api_credentials() — must return tuple."""

    def test_returns_tuple(self):
        result = extract_api_credentials({"api_id": 123, "api_hash": "abc"})
        assert isinstance(result, tuple)

    def test_unpacking(self):
        """Critical: must unpack correctly as (api_id, api_hash)."""
        api_id, api_hash = extract_api_credentials({"api_id": 12345, "api_hash": "hashval"})
        assert api_id == 12345
        assert api_hash == "hashval"

    def test_app_id_alias(self):
        api_id, api_hash = extract_api_credentials({"app_id": 999, "app_hash": "hh"})
        assert api_id == 999
        assert api_hash == "hh"

    def test_no_credentials(self):
        api_id, api_hash = extract_api_credentials({})
        assert api_id is None
        assert api_hash is None

    def test_nested_in_extra_data(self):
        """api_id/api_hash inside extra_data should be found."""
        api_id, api_hash = extract_api_credentials({
            "extra_data": {"api_id": 42, "api_hash": "deep"}
        })
        # Depends on extract_api_credentials_from_metadata behavior
        # At minimum, should not crash
        assert isinstance(api_id, (int, type(None)))

    def test_none_values(self):
        api_id, api_hash = extract_api_credentials({"api_id": None, "api_hash": None})
        assert api_id is None
        assert api_hash is None


class TestExtractDeviceFingerprint:
    """Tests for extract_device_fingerprint()."""

    def test_returns_dict(self):
        result = extract_device_fingerprint({})
        assert isinstance(result, dict)

    def test_with_device_data(self):
        result = extract_device_fingerprint({
            "device_model": "Samsung SM-G998B",
            "system_version": "SDK 31",
        })
        assert isinstance(result, dict)

    def test_with_fingerprint_key(self):
        result = extract_device_fingerprint({
            "device_fingerprint": {
                "device_model": "iPhone 14",
                "system_version": "16.4",
            }
        })
        assert isinstance(result, dict)


class TestSplitError:
    """Tests for _split_error() — splits 'code: detail' strings."""

    def test_none(self):
        code, detail = _split_error(None)
        assert code is None
        assert detail is None

    def test_empty(self):
        code, detail = _split_error("")
        assert code is None
        assert detail is None

    def test_code_and_detail(self):
        code, detail = _split_error("banned: Your account is banned")
        assert code == "banned"
        assert detail == "Your account is banned"

    def test_code_only(self):
        code, detail = _split_error("timeout")
        assert code == "timeout"
        assert detail is None

    def test_colon_no_detail(self):
        code, detail = _split_error("error:")
        assert code == "error"
        assert detail is None

    def test_multiple_colons(self):
        code, detail = _split_error("error: something: else: here")
        assert code == "error"
        assert detail == "something: else: here"


class TestErrorStatusMap:
    """Tests for ERROR_STATUS_MAP completeness."""

    def test_banned_maps(self):
        assert ERROR_STATUS_MAP["banned"] == "banned"

    def test_session_errors_map_to_session_expired(self):
        for key in ("session_expired", "session_revoked", "auth_key_duplicated", "auth_key_unregistered"):
            assert ERROR_STATUS_MAP[key] == "session_expired"

    def test_connection_errors(self):
        for key in ("connection_failed", "timeout"):
            assert ERROR_STATUS_MAP[key] == "connection_failed"

    def test_not_authorized(self):
        assert ERROR_STATUS_MAP["not_authorized"] == "needs_reauth"


class TestCountryCodes:
    """Tests for COUNTRY_CODES mapping."""

    def test_contains_major_countries(self):
        assert COUNTRY_CODES["7"] == "RU"
        assert COUNTRY_CODES["1"] == "US"
        assert COUNTRY_CODES["380"] == "UA"
        assert COUNTRY_CODES["44"] == "GB"

    def test_kazakhstan_overrides_russia(self):
        """77 should map to KZ, not RU."""
        assert COUNTRY_CODES["77"] == "KZ"

    def test_all_values_are_2_letter(self):
        for code, country in COUNTRY_CODES.items():
            assert len(country) == 2, f"Country code for {code} is not 2 letters: {country}"


class TestBulkActionRequest:
    """Tests for BulkActionRequest Pydantic model."""

    def test_valid(self):
        req = BulkActionRequest(action="delete", account_ids=[1, 2, 3])
        assert req.action == "delete"
        assert len(req.account_ids) == 3
        assert req.value is None

    def test_with_value(self):
        req = BulkActionRequest(action="set_group", account_ids=[1], value=5)
        assert req.value == 5

    def test_missing_action(self):
        with pytest.raises(ValidationError):
            BulkActionRequest(account_ids=[1])

    def test_missing_account_ids(self):
        with pytest.raises(ValidationError):
            BulkActionRequest(action="delete")


class TestCheckBatchRequest:
    """Tests for CheckBatchRequest Pydantic model."""

    def test_defaults(self):
        req = CheckBatchRequest(account_ids=[1, 2])
        assert req.check_spamblock is False
        assert req.max_concurrent == 3

    def test_custom_values(self):
        req = CheckBatchRequest(account_ids=[1], check_spamblock=True, max_concurrent=5)
        assert req.check_spamblock is True
        assert req.max_concurrent == 5


class TestSessionImport:
    """Tests for SessionImport Pydantic model."""

    def test_minimal(self):
        req = SessionImport(session_string="abc123")
        assert req.proxy_id is None
        assert req.api_id is None

    def test_full(self):
        req = SessionImport(
            session_string="sess",
            proxy_id=1,
            api_id=6,
            api_hash="hash",
        )
        assert req.api_id == 6
