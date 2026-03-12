"""Tests for API Pydantic schemas across multiple modules."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from pydantic import ValidationError

from api.tasks import (
    TaskConfig,
    CreateLikesTaskRequest,
    CreateCommentsTaskRequest,
    CommentsTaskConfig,
    CommentTemplateRequest,
    PreviewTemplateRequest,
    AddTaskLogRequest,
    UpdateTaskRequest,
)


class TestCreateCommentsTaskRequest:
    """Tests for CreateCommentsTaskRequest Pydantic model."""

    def test_minimal(self):
        req = CreateCommentsTaskRequest(
            config=CommentsTaskConfig(channels=["@test"]),
            account_ids=[1, 2],
        )
        assert req.total_actions == 10
        assert req.min_delay == 30.0
        assert req.max_delay == 120.0
        assert req.max_concurrent == 1

    def test_with_max_concurrent(self):
        req = CreateCommentsTaskRequest(
            config=CommentsTaskConfig(channels=["@test"]),
            account_ids=[1],
            max_concurrent=5,
        )
        assert req.max_concurrent == 5

    def test_delay_swap(self):
        """min_delay > max_delay should be auto-swapped."""
        req = CreateCommentsTaskRequest(
            config=CommentsTaskConfig(channels=["@test"]),
            account_ids=[1],
            min_delay=100.0,
            max_delay=10.0,
        )
        assert req.min_delay == 10.0
        assert req.max_delay == 100.0

    def test_invalid_total_actions_zero(self):
        with pytest.raises(ValidationError):
            CreateCommentsTaskRequest(
                config=CommentsTaskConfig(channels=["@test"]),
                account_ids=[1],
                total_actions=0,
            )

    def test_max_concurrent_bounds(self):
        with pytest.raises(ValidationError):
            CreateCommentsTaskRequest(
                config=CommentsTaskConfig(channels=["@test"]),
                account_ids=[1],
                max_concurrent=20,
            )

    def test_ai_settings(self):
        req = CreateCommentsTaskRequest(
            config=CommentsTaskConfig(
                channels=["@test"],
                ai_enabled=True,
                ai_api_key="sk-test",
                ai_model="gpt-4o",
                ai_temperature=0.9,
            ),
            account_ids=[1],
        )
        assert req.config.ai_enabled is True
        assert req.config.ai_model == "gpt-4o"
        assert req.config.ai_temperature == 0.9


class TestCommentsTaskConfig:
    """Tests for CommentsTaskConfig Pydantic model."""

    def test_defaults(self):
        cfg = CommentsTaskConfig(channels=["@ch"])
        assert cfg.rotation_mode == "random"
        assert cfg.comments_per_account == 10
        assert cfg.mode == "single"
        assert cfg.comment_mode == "all"
        assert cfg.comment_probability == 0.5
        assert cfg.ai_enabled is False
        assert cfg.ai_model == "gpt-4o-mini"

    def test_keywords_mode(self):
        cfg = CommentsTaskConfig(
            channels=["@ch"],
            comment_mode="keywords",
            keywords=["crypto", "bitcoin"],
        )
        assert cfg.comment_mode == "keywords"
        assert len(cfg.keywords) == 2

    def test_monitoring_mode(self):
        cfg = CommentsTaskConfig(
            channels=["@ch"],
            mode="monitoring",
        )
        assert cfg.mode == "monitoring"


class TestCommentTemplateRequest:
    """Tests for CommentTemplateRequest Pydantic model."""

    def test_valid(self):
        req = CommentTemplateRequest(name="Test", content="{Hi|Hello}!")
        assert req.name == "Test"
        assert req.is_default is False

    def test_name_too_long(self):
        with pytest.raises(ValidationError):
            CommentTemplateRequest(name="x" * 101, content="ok")

    def test_empty_name(self):
        with pytest.raises(ValidationError):
            CommentTemplateRequest(name="", content="ok")

    def test_empty_content(self):
        with pytest.raises(ValidationError):
            CommentTemplateRequest(name="ok", content="")


class TestPreviewTemplateRequest:
    """Tests for PreviewTemplateRequest Pydantic model."""

    def test_defaults(self):
        req = PreviewTemplateRequest(content="{Hi|Hello}")
        assert req.count == 5

    def test_custom_count(self):
        req = PreviewTemplateRequest(content="test", count=10)
        assert req.count == 10


class TestAddTaskLogRequest:
    """Tests for AddTaskLogRequest Pydantic model."""

    def test_minimal(self):
        req = AddTaskLogRequest(action_type="reaction", success=True)
        assert req.account_id is None
        assert req.target is None
        assert req.message is None
        assert req.error is None
        assert req.extra_data is None

    def test_full(self):
        req = AddTaskLogRequest(
            action_type="comment",
            success=False,
            account_id=42,
            target="@channel/123",
            message="Sent",
            error="Flood wait",
            extra_data={"wait_seconds": 300},
        )
        assert req.account_id == 42
        assert req.extra_data["wait_seconds"] == 300


class TestUpdateTaskRequest:
    """Tests for UpdateTaskRequest Pydantic model."""

    def test_all_optional(self):
        req = UpdateTaskRequest()
        assert req.status is None
        assert req.min_delay is None
        assert req.max_delay is None

    def test_partial_update(self):
        req = UpdateTaskRequest(status="paused")
        assert req.status == "paused"
        assert req.min_delay is None


class TestCreateLikesTaskRequestDelaySwap:
    """Additional tests for CreateLikesTaskRequest delay auto-swap."""

    def test_equal_delays_unchanged(self):
        req = CreateLikesTaskRequest(
            config=TaskConfig(channel="@test"),
            account_ids=[1],
            min_delay=50.0,
            max_delay=50.0,
        )
        assert req.min_delay == 50.0
        assert req.max_delay == 50.0

    def test_normal_order_unchanged(self):
        req = CreateLikesTaskRequest(
            config=TaskConfig(channel="@test"),
            account_ids=[1],
            min_delay=10.0,
            max_delay=60.0,
        )
        assert req.min_delay == 10.0
        assert req.max_delay == 60.0
