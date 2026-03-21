"""Tests for telegram.account_checker session error classification."""

import importlib
import sys
from pathlib import Path

import pytest
from telethon.errors import (
    AuthKeyDuplicatedError,
    SessionExpiredError as TelethonSessionExpired,
)

sys.path.insert(0, str(Path(__file__).parent.parent))

account_checker_module = importlib.import_module("telegram.account_checker")
from telegram.account_checker import AccountChecker, AccountStatus


class _FailingClient:
    def __init__(self, *args, **kwargs):
        self._error = kwargs.pop("_error")

    async def connect(self):
        raise self._error

    async def disconnect(self):
        return None


@pytest.mark.asyncio
async def test_check_single_maps_auth_key_duplicated_to_session_expired(monkeypatch):
    checker = AccountChecker()
    error = AuthKeyDuplicatedError(request=None)

    monkeypatch.setattr(
        account_checker_module.SessionManager,
        "create_memory_session",
        lambda session_string: object(),
    )
    monkeypatch.setattr(
        account_checker_module,
        "TelegramClient",
        lambda *args, **kwargs: _FailingClient(*args, _error=error, **kwargs),
    )

    result = await checker.check_single(account_id=1, session_string="session")

    assert result.status == AccountStatus.SESSION_EXPIRED
    assert result.error_code == "auth_key_duplicated"


@pytest.mark.asyncio
async def test_check_single_maps_session_expired_error(monkeypatch):
    checker = AccountChecker()
    error = TelethonSessionExpired(request=None)

    monkeypatch.setattr(
        account_checker_module.SessionManager,
        "create_memory_session",
        lambda session_string: object(),
    )
    monkeypatch.setattr(
        account_checker_module,
        "TelegramClient",
        lambda *args, **kwargs: _FailingClient(*args, _error=error, **kwargs),
    )

    result = await checker.check_single(account_id=2, session_string="session")

    assert result.status == AccountStatus.SESSION_EXPIRED
    assert result.error_code == "session_expired"


@pytest.mark.asyncio
async def test_check_single_parses_wrapped_duplicate_ip_error(monkeypatch):
    checker = AccountChecker()
    error = RuntimeError(
        "The authorization key was used under two different IP addresses simultaneously"
    )

    monkeypatch.setattr(
        account_checker_module.SessionManager,
        "create_memory_session",
        lambda session_string: object(),
    )
    monkeypatch.setattr(
        account_checker_module,
        "TelegramClient",
        lambda *args, **kwargs: _FailingClient(*args, _error=error, **kwargs),
    )

    result = await checker.check_single(account_id=3, session_string="session")

    assert result.status == AccountStatus.SESSION_EXPIRED
    assert result.error_code == "auth_key_duplicated"
