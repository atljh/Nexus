"""
Tests for TaskConfig and CreateLikesTaskRequest pydantic schemas.
"""

from datetime import datetime, timedelta, timezone
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
        assert normalize_warming_target("https://t.me/example/123?single") == "@example"
        assert normalize_warming_target("https://t.me/+InviteHash123/") == "https://t.me/+InviteHash123"
        assert normalize_warming_target("bad target!") == ""

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

        assert get_warming_delay_range("safe") == (600.0, 1200.0)
        assert get_warming_delay_range("normal") == (300.0, 600.0)
        assert get_warming_delay_range(None) == (60.0, 120.0)

    def test_warming_delay_range_normalization(self):
        from api.tasks import normalize_warming_delay_range

        assert normalize_warming_delay_range(36000.0, 18000.0) == (18000.0, 36000.0)
        assert normalize_warming_delay_range(None, None, "normal") == (300.0, 600.0)
        assert normalize_warming_delay_range(None, None, None) == (60.0, 120.0)

    def test_warming_safety_delay_floor_uses_youngest_account(self):
        from api.tasks import get_warming_safety_delay_floor, apply_warming_safety_delay_floor

        class StubAccount:
            def __init__(self, age_days: int):
                self.register_time = None
                self.created_at = datetime.now(timezone.utc) - timedelta(days=age_days)

        accounts = [StubAccount(20), StubAccount(1)]

        assert get_warming_safety_delay_floor(accounts) == (1800.0, 3600.0)
        assert apply_warming_safety_delay_floor(accounts, 60.0, 120.0) == (1800.0, 3600.0)

    def test_warming_task_config_normalization(self):
        from api.tasks import normalize_warming_task_config

        assert normalize_warming_task_config({
            "targets": ["testchannel", "@testchannel", "bad target!"],
            "speed_preset": "fast",
            "unexpected": "value",
        }) == {
            "targets": ["@testchannel"],
            "unexpected": "value",
        }

        assert normalize_warming_task_config({
            "targets": ["testchannel"],
            "speed_preset": "normal",
        }) == {
            "targets": ["@testchannel"],
            "speed_preset": "normal",
        }

    def test_warming_total_actions_counts_all_assigned_accounts(self):
        from api.tasks import calculate_warming_total_actions

        class StubAccount:
            def __init__(self, status: str):
                self.status = status

        accounts = [
            StubAccount("valid"),
            StubAccount("invalid"),
            StubAccount("banned"),
        ]

        assert calculate_warming_total_actions(accounts, {
            "targets": ["@channel_one", "@channel_two"],
            "speed_preset": "safe",
        }) == 6

    def test_update_warming_delays_reapply_safety_floor(self):
        from api.tasks import normalize_updated_task_delays

        class StubAccount:
            def __init__(self, age_days: int):
                self.register_time = None
                self.created_at = datetime.now(timezone.utc) - timedelta(days=age_days)

        class StubTask:
            task_type = "warming"
            min_delay = 18000.0
            max_delay = 36000.0
            config = {"targets": ["@channel"]}
            accounts = [StubAccount(1)]

        assert normalize_updated_task_delays(StubTask(), 60.0, 300.0) == (1800.0, 3600.0)

    def test_update_non_warming_delays_swap_and_clamp(self):
        from api.tasks import normalize_updated_task_delays

        class StubTask:
            task_type = "likes"
            min_delay = 30.0
            max_delay = 60.0
            config = {}
            accounts = []

        assert normalize_updated_task_delays(StubTask(), 5000.0, 10.0) == (10.0, 3600.0)
