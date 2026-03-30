"""
Tests for TaskConfig and CreateLikesTaskRequest pydantic schemas.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from pydantic import ValidationError


class TestTaskConfig:
    """Test TaskConfig schema validation."""

    def test_default_values(self):
        from api.tasks import TaskConfig

        config = TaskConfig(channel="@test")
        assert config.channel == "@test"
        assert config.post_id is None
        assert config.reactions == ["👍"]
        assert config.emoji_mode == "single"

    def test_custom_reactions(self):
        from api.tasks import TaskConfig

        config = TaskConfig(channel="@test", reactions=["👍", "❤", "🔥"])
        assert config.reactions == ["👍", "❤", "🔥"]

    def test_emoji_modes(self):
        from api.tasks import TaskConfig

        for mode in ["single", "random", "all"]:
            config = TaskConfig(channel="@test", emoji_mode=mode)
            assert config.emoji_mode == mode

    def test_channel_required(self):
        from api.tasks import TaskConfig

        with pytest.raises(ValidationError):
            TaskConfig()

    def test_post_id_optional(self):
        from api.tasks import TaskConfig

        config = TaskConfig(channel="@test", post_id=123)
        assert config.post_id == 123

    def test_empty_reactions_list_allowed(self):
        from api.tasks import TaskConfig

        config = TaskConfig(channel="@test", reactions=[])
        assert config.reactions == []

    def test_single_reaction(self):
        from api.tasks import TaskConfig

        config = TaskConfig(channel="@test", reactions=["🔥"])
        assert config.reactions == ["🔥"]


class TestCreateLikesTaskRequest:
    """Test CreateLikesTaskRequest schema."""

    def test_minimal_request(self):
        from api.tasks import CreateLikesTaskRequest, TaskConfig

        req = CreateLikesTaskRequest(
            config=TaskConfig(channel="@test"),
            account_ids=[1, 2, 3]
        )
        assert req.config.channel == "@test"
        assert req.config.reactions == ["👍"]
        assert req.config.emoji_mode == "single"
        assert req.account_ids == [1, 2, 3]
        assert req.total_actions == 10
        assert req.min_delay == 30.0
        assert req.max_delay == 120.0

    def test_full_request(self):
        from api.tasks import CreateLikesTaskRequest, TaskConfig

        req = CreateLikesTaskRequest(
            config=TaskConfig(
                channel="@mychannel",
                post_id=456,
                reactions=["👍", "❤", "🔥"],
                emoji_mode="random"
            ),
            account_ids=[1, 2],
            total_actions=50,
            min_delay=10.0,
            max_delay=60.0,
            max_concurrent=3
        )
        assert req.config.reactions == ["👍", "❤", "🔥"]
        assert req.config.emoji_mode == "random"
        assert req.total_actions == 50
        assert req.max_concurrent == 3

    def test_total_actions_bounds(self):
        from api.tasks import CreateLikesTaskRequest, TaskConfig

        # Too low
        with pytest.raises(ValidationError):
            CreateLikesTaskRequest(
                config=TaskConfig(channel="@test"),
                account_ids=[1],
                total_actions=0
            )

        # Too high
        with pytest.raises(ValidationError):
            CreateLikesTaskRequest(
                config=TaskConfig(channel="@test"),
                account_ids=[1],
                total_actions=10001
            )

    def test_delay_bounds(self):
        from api.tasks import CreateLikesTaskRequest, TaskConfig

        with pytest.raises(ValidationError):
            CreateLikesTaskRequest(
                config=TaskConfig(channel="@test"),
                account_ids=[1],
                min_delay=0  # < 1
            )

    def test_account_ids_required(self):
        from api.tasks import CreateLikesTaskRequest, TaskConfig

        with pytest.raises(ValidationError):
            CreateLikesTaskRequest(
                config=TaskConfig(channel="@test")
            )


class TestWarmingHelpers:
    """Test warming-specific schema helpers."""

    def test_warming_target_normalization(self):
        from api.tasks import normalize_warming_target

        assert normalize_warming_target("channelname") == "@channelname"
        assert normalize_warming_target("https://t.me/example") == "@example"
        assert normalize_warming_target("https://t.me/+InviteHash123") == "https://t.me/+InviteHash123"
        assert normalize_warming_target("https://t.me/c/123456/7") == "-100123456"

    def test_warming_targets_deduplicate(self):
        from api.tasks import normalize_warming_targets

        assert normalize_warming_targets([
            "testchannel",
            "@testchannel",
            "https://t.me/+abc",
            "https://t.me/+abc",
        ]) == ["@testchannel", "https://t.me/+abc"]

    def test_warming_delay_preset(self):
        from api.tasks import get_warming_delay_range

        assert get_warming_delay_range("safe") == (14400.0, 21600.0)
        assert get_warming_delay_range("normal") == (7200.0, 14400.0)
