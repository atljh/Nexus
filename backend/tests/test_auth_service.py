"""Tests for telegram.auth_service — authorization flow logic."""
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from telegram.auth_service import AuthService, AuthSession, AuthStep


class TestNormalizePhone:
    """Tests for AuthService._normalize_phone()."""

    def setup_method(self):
        self.svc = AuthService()

    def test_already_normalized(self):
        assert self.svc._normalize_phone("+79001234567") == "+79001234567"

    def test_adds_plus(self):
        assert self.svc._normalize_phone("79001234567") == "+79001234567"

    def test_removes_spaces(self):
        assert self.svc._normalize_phone("+7 900 123 45 67") == "+79001234567"

    def test_removes_dashes(self):
        assert self.svc._normalize_phone("+7-900-123-45-67") == "+79001234567"

    def test_removes_parens(self):
        assert self.svc._normalize_phone("+7(900)1234567") == "+79001234567"

    def test_combined_formatting(self):
        assert self.svc._normalize_phone("7 (900) 123-45-67") == "+79001234567"


class TestCleanupExpired:
    """Tests for session expiry cleanup."""

    def setup_method(self):
        self.svc = AuthService()

    def test_removes_expired(self):
        expired = AuthSession(
            session_id="expired",
            phone="+123",
            session_string="s",
            phone_code_hash="h",
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        self.svc._sessions["expired"] = expired
        self.svc._cleanup_expired()
        assert "expired" not in self.svc._sessions

    def test_keeps_valid(self):
        valid = AuthSession(
            session_id="valid",
            phone="+123",
            session_string="s",
            phone_code_hash="h",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
        self.svc._sessions["valid"] = valid
        self.svc._cleanup_expired()
        assert "valid" in self.svc._sessions


class TestCancelAuth:
    """Tests for cancel_auth()."""

    def setup_method(self):
        self.svc = AuthService()

    @pytest.mark.asyncio
    async def test_cancel_existing(self):
        session = AuthSession(
            session_id="to_cancel",
            phone="+123",
            session_string="s",
            phone_code_hash="h",
        )
        self.svc._sessions["to_cancel"] = session
        result = await self.svc.cancel_auth("to_cancel")
        assert result is True
        assert "to_cancel" not in self.svc._sessions

    @pytest.mark.asyncio
    async def test_cancel_nonexistent(self):
        result = await self.svc.cancel_auth("nonexistent")
        assert result is False


class TestGetSessionInfo:
    """Tests for get_session_info()."""

    def setup_method(self):
        self.svc = AuthService()

    def test_existing_session(self):
        session = AuthSession(
            session_id="info_test",
            phone="+79001234567",
            session_string="s",
            phone_code_hash="h",
            needs_password=True,
        )
        self.svc._sessions["info_test"] = session
        info = self.svc.get_session_info("info_test")
        assert info is not None
        assert info["phone"] == "+79001234567"
        assert info["needs_password"] is True

    def test_nonexistent_session(self):
        info = self.svc.get_session_info("nope")
        assert info is None

    def test_expired_session_cleaned(self):
        expired = AuthSession(
            session_id="old",
            phone="+1",
            session_string="s",
            phone_code_hash="h",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        self.svc._sessions["old"] = expired
        info = self.svc.get_session_info("old")
        assert info is None


class TestAuthStep:
    """Tests for AuthStep enum."""

    def test_values(self):
        assert AuthStep.PHONE == "phone"
        assert AuthStep.CODE == "code"
        assert AuthStep.PASSWORD == "password"
        assert AuthStep.SUCCESS == "success"

    def test_is_string(self):
        assert isinstance(AuthStep.PHONE, str)


class TestStartAuthRequiresProxy:
    """start_auth() should reject requests without proxy."""

    def setup_method(self):
        self.svc = AuthService()

    @pytest.mark.asyncio
    async def test_no_proxy_returns_error(self):
        result = await self.svc.start_auth("+79001234567", proxy=None)
        assert result.success is False
        assert "Proxy is required" in result.error
