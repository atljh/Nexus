"""Tests for database.models — model serialization and helper functions."""
import sys
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.models import (
    _utc_iso,
    _sanitize_task_config,
    Proxy,
    AccountGroup,
    AccountTag,
    Task,
    TaskLog,
    CommentTemplate,
    TargetChannel,
)


class TestUtcIso:
    """Tests for _utc_iso() datetime formatting."""

    def test_none_returns_none(self):
        assert _utc_iso(None) is None

    def test_naive_datetime(self):
        dt = datetime(2024, 3, 15, 10, 30, 0)
        result = _utc_iso(dt)
        assert result == "2024-03-15T10:30:00Z"

    def test_aware_datetime_strips_tzinfo(self):
        dt = datetime(2024, 3, 15, 10, 30, 0, tzinfo=timezone.utc)
        result = _utc_iso(dt)
        assert result == "2024-03-15T10:30:00Z"
        assert "+00:00" not in result

    def test_with_microseconds(self):
        dt = datetime(2024, 1, 1, 0, 0, 0, 123456)
        result = _utc_iso(dt)
        assert result.endswith("Z")
        assert "123456" in result


class TestSanitizeTaskConfig:
    """Tests for _sanitize_task_config()."""

    def test_none_returns_empty_dict(self):
        assert _sanitize_task_config(None) == {}

    def test_non_dict_returns_empty_dict(self):
        assert _sanitize_task_config("string") == {}
        assert _sanitize_task_config(123) == {}
        assert _sanitize_task_config([1, 2]) == {}

    def test_masks_ai_api_key(self):
        config = {"channel": "@test", "ai_api_key": "sk-secret-key-123"}
        result = _sanitize_task_config(config)
        assert result["ai_api_key"] == "***"
        assert result["channel"] == "@test"

    def test_no_ai_key_unchanged(self):
        config = {"channel": "@test", "reactions": ["👍"]}
        result = _sanitize_task_config(config)
        assert result == config

    def test_does_not_mutate_original(self):
        config = {"ai_api_key": "secret"}
        _sanitize_task_config(config)
        assert config["ai_api_key"] == "secret"

    def test_empty_dict(self):
        assert _sanitize_task_config({}) == {}


class TestProxyGetConnectionString:
    """Tests for Proxy.get_connection_string() using real instances."""

    def test_no_auth(self):
        proxy = Proxy(type="socks5", host="1.2.3.4", port=1080)
        assert proxy.get_connection_string() == "socks5://1.2.3.4:1080"

    def test_with_auth(self):
        proxy = Proxy(type="socks5", host="1.2.3.4", port=1080, username="user", password="pass")
        assert proxy.get_connection_string() == "socks5://user:pass@1.2.3.4:1080"

    def test_http(self):
        proxy = Proxy(type="http", host="proxy.com", port=8080)
        assert proxy.get_connection_string() == "http://proxy.com:8080"

    def test_https(self):
        proxy = Proxy(type="https", host="secure.proxy", port=443, username="u", password="p")
        assert proxy.get_connection_string() == "https://u:p@secure.proxy:443"


class TestProxyToDict:
    """Tests for Proxy.to_dict()."""

    @patch("database.models._is_loaded", return_value=False)
    def test_basic_serialization(self, mock_loaded):
        proxy = Proxy(
            type="socks5", host="1.2.3.4", port=1080,
            status="working", ping_ms=50, geo="US",
            external_ip="5.6.7.8",
            created_at=datetime(2024, 1, 1),
        )
        proxy.id = 1
        d = proxy.to_dict()
        assert d["host"] == "1.2.3.4"
        assert d["port"] == 1080
        assert d["status"] == "working"
        assert d["ping_ms"] == 50
        assert d["geo"] == "US"
        assert d["accounts_count"] == 0

    @patch("database.models._is_loaded", return_value=False)
    def test_password_excluded(self, mock_loaded):
        proxy = Proxy(
            type="socks5", host="x", port=1080,
            username="user", password="secret",
            created_at=datetime(2024, 1, 1),
        )
        proxy.id = 1
        d = proxy.to_dict()
        # password should NOT be in to_dict output
        assert "password" not in d


class TestTaskProgress:
    """Tests for Task.to_dict() progress calculation."""

    def _make_task(self, total=100, completed=50, failed=10, **kwargs):
        defaults = dict(
            task_type="likes",
            status="running",
            config={"channel": "@test"},
            total_actions=total,
            completed_actions=completed,
            failed_actions=failed,
            min_delay=30.0,
            max_delay=120.0,
            max_concurrent=1,
            last_error=None,
            started_at=None,
            completed_at=None,
            created_at=datetime(2024, 1, 1),
        )
        defaults.update(kwargs)
        task = Task(**defaults)
        task.id = 1
        return task

    @patch("database.models._is_loaded", return_value=False)
    def test_progress_calculation(self, mock_loaded):
        task = self._make_task(total=100, completed=50, failed=10)
        d = task.to_dict()
        assert d["progress"] == 60.0

    @patch("database.models._is_loaded", return_value=False)
    def test_progress_zero_total(self, mock_loaded):
        task = self._make_task(total=0, completed=0, failed=0)
        d = task.to_dict()
        assert d["progress"] == 0

    @patch("database.models._is_loaded", return_value=False)
    def test_progress_capped_at_100(self, mock_loaded):
        task = self._make_task(total=10, completed=15, failed=5)
        d = task.to_dict()
        assert d["progress"] == 100.0

    @patch("database.models._is_loaded", return_value=False)
    def test_config_sanitized(self, mock_loaded):
        task = self._make_task(config={"channel": "@t", "ai_api_key": "sk-xxx"})
        d = task.to_dict()
        assert d["config"]["ai_api_key"] == "***"

    @patch("database.models._is_loaded", return_value=False)
    def test_accounts_count_when_not_loaded(self, mock_loaded):
        task = self._make_task()
        d = task.to_dict()
        assert d["accounts_count"] == 0

    @patch("database.models._is_loaded", return_value=False)
    def test_all_fields_present(self, mock_loaded):
        task = self._make_task()
        d = task.to_dict()
        expected_keys = {
            "id", "task_type", "status", "config",
            "total_actions", "completed_actions", "failed_actions",
            "min_delay", "max_delay", "max_concurrent",
            "last_error", "started_at", "completed_at", "created_at",
            "accounts_count", "progress",
        }
        assert expected_keys.issubset(d.keys())


class TestTaskLogToDict:
    """Tests for TaskLog.to_dict()."""

    def _make_log(self, **kwargs):
        defaults = dict(
            task_id=10,
            account_id=5,
            action_type="reaction",
            target="@channel/123",
            success=True,
            message="Reaction 👍 sent",
            error=None,
            extra_data=None,
            created_at=datetime(2024, 6, 15, 12, 30, 0),
        )
        defaults.update(kwargs)
        log = TaskLog(**defaults)
        log.id = 1
        return log

    def test_basic_fields(self):
        log = self._make_log()
        d = log.to_dict()
        assert d["id"] == 1
        assert d["task_id"] == 10
        assert d["action_type"] == "reaction"
        assert d["success"] is True
        assert d["created_at"].endswith("Z")

    def test_error_included(self):
        log = self._make_log(success=False, error="Flood wait")
        d = log.to_dict()
        assert d["success"] is False
        assert d["error"] == "Flood wait"

    def test_extra_data(self):
        log = self._make_log(extra_data={"wait_seconds": 300})
        d = log.to_dict()
        assert d["extra_data"]["wait_seconds"] == 300


class TestCommentTemplateToDict:
    """Tests for CommentTemplate.to_dict()."""

    def test_serializes_correctly(self):
        tmpl = CommentTemplate(
            name="Greeting",
            content="{Hi|Hello} there!",
            is_default=True,
            created_at=datetime(2024, 1, 1),
        )
        tmpl.id = 1
        d = tmpl.to_dict()
        assert d["name"] == "Greeting"
        assert d["content"] == "{Hi|Hello} there!"
        assert d["is_default"] is True


class TestAccountGroupToDict:
    """Tests for AccountGroup.to_dict()."""

    @patch("database.models._is_loaded", return_value=False)
    def test_no_accounts_loaded(self, mock_loaded):
        group = AccountGroup(
            name="Premium",
            color="#ff0000",
            created_at=datetime(2024, 1, 1),
        )
        group.id = 1
        d = group.to_dict()
        assert d["name"] == "Premium"
        assert d["color"] == "#ff0000"
        assert d["accounts_count"] == 0


class TestAccountTagToDict:
    """Tests for AccountTag.to_dict()."""

    def test_serializes_correctly(self):
        tag = AccountTag(name="VIP", color="#a855f7")
        tag.id = 1
        d = tag.to_dict()
        assert d["name"] == "VIP"
        assert d["color"] == "#a855f7"


class TestTargetChannelToDict:
    """Tests for TargetChannel.to_dict()."""

    def test_serializes_correctly(self):
        ch = TargetChannel(
            task_id=1,
            channel_username="@test_channel",
            channel_id=12345,
            channel_title="Test Channel",
            status="joined",
            can_comment=True,
            comments_sent=42,
            created_at=datetime(2024, 1, 1),
        )
        ch.id = 1
        d = ch.to_dict()
        assert d["channel_username"] == "@test_channel"
        assert d["channel_id"] == 12345
        assert d["status"] == "joined"
        assert d["can_comment"] is True
        assert d["comments_sent"] == 42

    def test_error_state(self):
        ch = TargetChannel(
            task_id=1,
            channel_username="@broken",
            status="error",
            can_comment=False,
            error_message="Channel not found",
            created_at=datetime(2024, 1, 1),
        )
        ch.id = 2
        d = ch.to_dict()
        assert d["status"] == "error"
        assert d["error_message"] == "Channel not found"
