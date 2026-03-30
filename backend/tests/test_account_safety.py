"""Tests for account safety and fingerprint locking."""

from datetime import datetime, timezone
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from workers.shared.account_safety import AccountSafetyValidator


class StubDb:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1


class StubAccount:
    def __init__(self, fingerprint=None, locked_at=None):
        self.id = 1
        self.device_fingerprint = fingerprint
        self.fingerprint_locked_at = locked_at


def test_extract_fingerprint_normalizes_values():
    fingerprint = AccountSafetyValidator.extract_fingerprint({
        "device_model": " Desktop ",
        "system_version": 10,
        "app_version": "6.6.2",
        "lang_code": "",
        "system_lang_code": None,
    })

    assert fingerprint == {
        "device_model": "Desktop",
        "system_version": "10",
        "app_version": "6.6.2",
    }


def test_lock_fingerprint_overwrites_partial_existing_value():
    account = StubAccount(fingerprint={"lang_code": "en"})
    db = StubDb()

    locked = AccountSafetyValidator.lock_fingerprint(account, {
        "device_model": "Desktop",
        "system_version": "Windows 10",
        "app_version": "6.6.2 x64",
        "lang_code": "en",
        "system_lang_code": "en-US",
    }, db)

    assert locked is True
    assert account.device_fingerprint == {
        "device_model": "Desktop",
        "system_version": "Windows 10",
        "app_version": "6.6.2 x64",
        "lang_code": "en",
        "system_lang_code": "en-US",
    }
    assert isinstance(account.fingerprint_locked_at, datetime)
    assert db.commits == 1


def test_lock_fingerprint_repairs_missing_fingerprint_when_locked_at_exists():
    locked_at = datetime.now(timezone.utc)
    account = StubAccount(fingerprint=None, locked_at=locked_at)
    db = StubDb()

    locked = AccountSafetyValidator.lock_fingerprint(account, {
        "device_model": "Desktop",
        "system_version": "Windows 10",
        "app_version": "6.6.2 x64",
    }, db)

    assert locked is True
    assert account.device_fingerprint == {
        "device_model": "Desktop",
        "system_version": "Windows 10",
        "app_version": "6.6.2 x64",
    }
    assert account.fingerprint_locked_at == locked_at
    assert db.commits == 1


def test_validate_fingerprint_uses_normalized_values():
    is_valid, errors = AccountSafetyValidator.validate_fingerprint(
        {"device_model": "Desktop", "system_version": 10, "app_version": "6.6.2"},
        {"device_model": "Desktop", "system_version": "10", "app_version": "6.6.2"},
    )

    assert is_valid is True
    assert errors == []
