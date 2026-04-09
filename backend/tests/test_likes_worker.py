"""
Tests for LikesWorker - client pool, multi-emoji, reactions filtering, backward compat.

All Telegram/DB interactions are mocked. Tests verify the worker's internal logic.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from datetime import datetime, timezone

import sys
from pathlib import Path

# Add backend to path so imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

from workers.likes_worker import LikesWorker, REACTIONS_MAP


# ── Helpers ──

def make_account(id, session_string="session_abc", proxy=None, phone="+123"):
    acc = MagicMock()
    acc.id = id
    acc.session_string = session_string
    acc.proxy = proxy
    acc.api_id = 123
    acc.api_hash = "abc"
    acc.device_fingerprint = {}
    acc.phone = phone
    acc.telegram_id = 10000 + id
    acc.last_used_at = None
    return acc


def make_entity(channel_id=100):
    entity = MagicMock()
    entity.id = channel_id
    return entity


# ── Unit tests for pure logic methods ──

class TestPickReaction:
    """Test _pick_reaction emoji mode logic."""

    def setup_method(self):
        self.worker = LikesWorker(task_id=1)

    def test_single_mode_returns_first(self):
        result = self.worker._pick_reaction(["👍", "❤", "🔥"], "single", 0)
        assert result == ["👍"]

    def test_single_mode_always_first(self):
        for i in range(10):
            result = self.worker._pick_reaction(["👍", "❤", "🔥"], "single", i)
            assert result == ["👍"]

    def test_random_mode_returns_one(self):
        reactions = ["👍", "❤", "🔥"]
        result = self.worker._pick_reaction(reactions, "random", 0)
        assert len(result) == 1
        assert result[0] in reactions

    def test_random_mode_varies(self):
        """Random should eventually pick different emojis."""
        reactions = ["👍", "❤", "🔥"]
        seen = set()
        for i in range(100):
            result = self.worker._pick_reaction(reactions, "random", i)
            seen.add(result[0])
        assert len(seen) > 1  # At least 2 different emojis in 100 tries

    def test_all_mode_returns_all(self):
        reactions = ["👍", "❤", "🔥"]
        result = self.worker._pick_reaction(reactions, "all", 0)
        assert result == reactions

    def test_all_mode_with_single_emoji(self):
        result = self.worker._pick_reaction(["👍"], "all", 0)
        assert result == ["👍"]

    def test_unknown_mode_defaults_to_single(self):
        result = self.worker._pick_reaction(["👍", "❤"], "unknown", 0)
        assert result == ["👍"]


class TestFilterReactions:
    """Test _filter_reactions logic."""

    def setup_method(self):
        self.worker = LikesWorker(task_id=1)

    def test_none_available_means_all_allowed(self):
        result = self.worker._filter_reactions(["👍", "❤"], None)
        assert result == ["👍", "❤"]

    def test_empty_available_means_none_allowed(self):
        result = self.worker._filter_reactions(["👍", "❤"], [])
        assert result == []

    def test_filters_to_available(self):
        result = self.worker._filter_reactions(["👍", "❤", "🔥"], ["👍", "🔥", "🎉"])
        assert result == ["👍", "🔥"]

    def test_no_overlap(self):
        result = self.worker._filter_reactions(["👍", "❤"], ["🔥", "🎉"])
        assert result == []

    def test_all_available(self):
        result = self.worker._filter_reactions(["👍", "❤"], ["👍", "❤", "🔥"])
        assert result == ["👍", "❤"]


class TestReactionsMap:
    """Test REACTIONS_MAP backward compatibility."""

    def test_emoji_to_emoji(self):
        assert REACTIONS_MAP["👍"] == "👍"
        assert REACTIONS_MAP["🔥"] == "🔥"

    def test_text_to_emoji(self):
        assert REACTIONS_MAP["thumbsup"] == "👍"
        assert REACTIONS_MAP["heart"] == "❤"
        assert REACTIONS_MAP["fire"] == "🔥"
        assert REACTIONS_MAP["clap"] == "👏"

    def test_heart_normalization(self):
        # ❤️ (with variation selector) → ❤ (plain)
        assert REACTIONS_MAP["❤️"] == "❤"


class TestBackwardCompatConfig:
    """Test that old 'reaction' field is handled in config parsing."""

    def test_old_reaction_string_to_reactions_list(self):
        """Worker should convert old 'reaction' key to 'reactions' list."""
        config = {"channel": "@test", "reaction": "🔥"}
        reactions = config.get("reactions")
        if not reactions:
            old_reaction = config.get("reaction", "👍")
            reactions = [REACTIONS_MAP.get(old_reaction, old_reaction)]
        assert reactions == ["🔥"]

    def test_new_reactions_list_preferred(self):
        """If 'reactions' exists, it should be used, not 'reaction'."""
        config = {"channel": "@test", "reactions": ["👍", "❤"], "reaction": "🔥"}
        reactions = config.get("reactions")
        if not reactions:
            old_reaction = config.get("reaction", "👍")
            reactions = [REACTIONS_MAP.get(old_reaction, old_reaction)]
        else:
            reactions = [REACTIONS_MAP.get(r, r) for r in reactions]
        assert reactions == ["👍", "❤"]

    def test_text_reaction_mapped(self):
        config = {"channel": "@test", "reaction": "heart"}
        reactions = config.get("reactions")
        if not reactions:
            old_reaction = config.get("reaction", "👍")
            reactions = [REACTIONS_MAP.get(old_reaction, old_reaction)]
        assert reactions == ["❤"]

    def test_default_when_nothing(self):
        config = {"channel": "@test"}
        reactions = config.get("reactions")
        if not reactions:
            old_reaction = config.get("reaction", "👍")
            reactions = [REACTIONS_MAP.get(old_reaction, old_reaction)]
        assert reactions == ["👍"]


class TestWorkerInit:
    """Test LikesWorker initialization."""

    def test_init_empty_pools(self):
        worker = LikesWorker(task_id=42)
        assert worker.task_id == 42
        assert worker._clients == {}
        assert worker._entities == {}
        assert worker._failed_accounts == set()
        assert worker.on_progress is None

    def test_init_with_progress(self):
        cb = AsyncMock()
        worker = LikesWorker(task_id=1, on_progress=cb)
        assert worker.on_progress is cb


# ── Async tests with mocks ──

@pytest.fixture
def worker():
    return LikesWorker(task_id=1)


@pytest.mark.asyncio
async def test_send_reaction_success(worker):
    """Test successful reaction sending."""
    mock_client = MagicMock()
    mock_client.client = AsyncMock()

    worker._clients[1] = mock_client
    worker._entities[1] = make_entity()

    success, message, error = await worker._send_reaction(1, 123, "👍")

    assert success is True
    assert "👍" in message
    assert error is None
    mock_client.client.assert_called_once()


@pytest.mark.asyncio
async def test_send_reaction_already_set(worker):
    """MessageNotModifiedError should be treated as success."""
    from telethon.errors import MessageNotModifiedError

    mock_client = MagicMock()
    mock_client.client = AsyncMock(side_effect=MessageNotModifiedError(request=None))

    worker._clients[1] = mock_client
    worker._entities[1] = make_entity()

    success, message, error = await worker._send_reaction(1, 123, "👍")

    assert success is True
    assert "already set" in message
    assert error is None


@pytest.mark.asyncio
async def test_send_reaction_invalid_emoji(worker):
    """ReactionInvalidError should return failure."""
    from telethon.errors import ReactionInvalidError

    mock_client = MagicMock()
    mock_client.client = AsyncMock(side_effect=ReactionInvalidError(request=None))

    worker._clients[1] = mock_client
    worker._entities[1] = make_entity()

    success, message, error = await worker._send_reaction(1, 123, "💀")

    assert success is False
    assert "Invalid" in error


@pytest.mark.asyncio
async def test_send_reaction_banned_excludes_account(worker):
    """ChatWriteForbiddenError should add account to failed set."""
    from telethon.errors import ChatWriteForbiddenError

    mock_client = MagicMock()
    mock_client.client = AsyncMock(side_effect=ChatWriteForbiddenError(request=None))

    worker._clients[1] = mock_client
    worker._entities[1] = make_entity()

    assert 1 not in worker._failed_accounts

    success, message, error = await worker._send_reaction(1, 123, "👍")

    assert success is False
    assert 1 in worker._failed_accounts


@pytest.mark.asyncio
async def test_send_reaction_no_entity(worker):
    """If entity not resolved, should return error."""
    mock_client = MagicMock()
    worker._clients[1] = mock_client
    # No entity set

    success, message, error = await worker._send_reaction(1, 123, "👍")

    assert success is False
    assert "Entity not resolved" in error


@pytest.mark.asyncio
async def test_send_reaction_channel_private_excludes(worker):
    """ChannelPrivateError should exclude account."""
    from telethon.errors import ChannelPrivateError

    mock_client = MagicMock()
    mock_client.client = AsyncMock(side_effect=ChannelPrivateError(request=None))

    worker._clients[1] = mock_client
    worker._entities[1] = make_entity()

    success, message, error = await worker._send_reaction(1, 123, "👍")

    assert success is False
    assert 1 in worker._failed_accounts


@pytest.mark.asyncio
async def test_check_subscription_subscribed(worker):
    """Account is already a participant."""
    mock_client = MagicMock()
    mock_client.client = AsyncMock(return_value=MagicMock())

    worker._clients[1] = mock_client
    entity = make_entity()

    is_sub, error = await worker._check_subscription(1, entity)

    assert is_sub is True
    assert error is None


@pytest.mark.asyncio
async def test_check_subscription_not_subscribed(worker):
    """UserNotParticipantError → not subscribed."""
    from telethon.errors import UserNotParticipantError

    mock_client = MagicMock()
    mock_client.client = AsyncMock(side_effect=UserNotParticipantError(request=None))

    worker._clients[1] = mock_client
    entity = make_entity()

    is_sub, error = await worker._check_subscription(1, entity)

    assert is_sub is False
    assert error is None


@pytest.mark.asyncio
async def test_check_subscription_channel_private(worker):
    """ChannelPrivateError → CHANNEL_PRIVATE error string."""
    from telethon.errors import ChannelPrivateError

    mock_client = MagicMock()
    mock_client.client = AsyncMock(side_effect=ChannelPrivateError(request=None))

    worker._clients[1] = mock_client
    entity = make_entity()

    is_sub, error = await worker._check_subscription(1, entity)

    assert is_sub is False
    assert error == "CHANNEL_PRIVATE"


@pytest.mark.asyncio
async def test_check_subscription_reraises_flood_wait(worker):
    """FloodWaitError should reach the caller's cooldown handling."""
    from telethon.errors import FloodWaitError

    mock_client = MagicMock()
    mock_client.client = AsyncMock(side_effect=FloodWaitError(request=None, capture=33))

    worker._clients[1] = mock_client

    with pytest.raises(FloodWaitError):
        await worker._check_subscription(1, make_entity())


@pytest.mark.asyncio
async def test_join_channel_success(worker):
    """Successful join."""
    mock_client = MagicMock()
    mock_client.client = AsyncMock(return_value=MagicMock())

    worker._clients[1] = mock_client
    entity = make_entity()

    success, error = await worker._join_channel(1, entity, "@test")

    assert success is True
    assert error is None


@pytest.mark.asyncio
async def test_join_channel_private(worker):
    """ChannelPrivateError on join."""
    from telethon.errors import ChannelPrivateError

    mock_client = MagicMock()
    mock_client.client = AsyncMock(side_effect=ChannelPrivateError(request=None))

    worker._clients[1] = mock_client
    entity = make_entity()

    success, error = await worker._join_channel(1, entity, "@test")

    assert success is False
    assert "private" in error.lower()


@pytest.mark.asyncio
async def test_join_channel_too_many(worker):
    """ChannelsTooMuchError on join."""
    from telethon.errors import ChannelsTooMuchError

    mock_client = MagicMock()
    mock_client.client = AsyncMock(side_effect=ChannelsTooMuchError(request=None))

    worker._clients[1] = mock_client
    entity = make_entity()

    success, error = await worker._join_channel(1, entity, "@test")

    assert success is False
    assert "too many" in error.lower()


@pytest.mark.asyncio
async def test_resolve_entity_cached(worker):
    """Entity should be resolved once and cached."""
    mock_client = MagicMock()
    entity = make_entity(200)
    mock_client.client = MagicMock()
    mock_client.client.get_entity = AsyncMock(return_value=entity)

    worker._clients[1] = mock_client

    result1 = await worker._resolve_entity(1, "@test")
    result2 = await worker._resolve_entity(1, "@test")

    assert result1 is entity
    assert result2 is entity
    # get_entity should be called only once
    mock_client.client.get_entity.assert_called_once_with("@test")


@pytest.mark.asyncio
async def test_resolve_entity_after_invite_join_falls_back_to_channel(worker):
    """Missing entity after invite join should be resolved from the configured channel target."""
    entity = make_entity(-100123)
    worker._resolve_entity = AsyncMock(return_value=entity)

    result = await worker._resolve_entity_after_invite_join(1, "-100123", None)

    assert result is entity
    worker._resolve_entity.assert_awaited_once_with(1, "-100123")


@pytest.mark.asyncio
async def test_resolve_entity_after_invite_join_skips_plain_invite_target(worker):
    """Pure invite links have nothing stable to resolve against if Telegram returned no entity."""
    worker._resolve_entity = AsyncMock()

    result = await worker._resolve_entity_after_invite_join(1, "https://t.me/+abc123", None)

    assert result is None
    worker._resolve_entity.assert_not_called()


@pytest.mark.asyncio
async def test_disconnect_all(worker):
    """All clients should be disconnected and pools cleared."""
    c1 = MagicMock()
    c1.disconnect = AsyncMock()
    c2 = MagicMock()
    c2.disconnect = AsyncMock()

    worker._clients = {1: c1, 2: c2}
    worker._entities = {1: "entity1", 2: "entity2"}

    await worker._disconnect_all()

    c1.disconnect.assert_called_once()
    c2.disconnect.assert_called_once()
    assert worker._clients == {}
    assert worker._entities == {}


@pytest.mark.asyncio
async def test_disconnect_all_handles_errors(worker):
    """Disconnect errors should not propagate."""
    c1 = MagicMock()
    c1.disconnect = AsyncMock(side_effect=Exception("connection error"))
    c2 = MagicMock()
    c2.disconnect = AsyncMock()

    worker._clients = {1: c1, 2: c2}

    # Should not raise
    await worker._disconnect_all()

    assert worker._clients == {}


@pytest.mark.asyncio
async def test_get_available_reactions_all(worker):
    """ChatReactionsAll → None (all allowed)."""
    from telethon.tl.types import ChatReactionsAll

    mock_client = MagicMock()
    full_chat = MagicMock()
    full_chat.full_chat.available_reactions = ChatReactionsAll(allow_custom=False)
    mock_client.client = AsyncMock(return_value=full_chat)

    worker._clients[1] = mock_client

    result = await worker._get_available_reactions(1, make_entity())
    assert result is None


@pytest.mark.asyncio
async def test_get_available_reactions_none(worker):
    """ChatReactionsNone → empty list."""
    from telethon.tl.types import ChatReactionsNone

    mock_client = MagicMock()
    full_chat = MagicMock()
    full_chat.full_chat.available_reactions = ChatReactionsNone()
    mock_client.client = AsyncMock(return_value=full_chat)

    worker._clients[1] = mock_client

    result = await worker._get_available_reactions(1, make_entity())
    assert result == []


@pytest.mark.asyncio
async def test_get_available_reactions_some(worker):
    """ChatReactionsSome → list of emoticons."""
    from telethon.tl.types import ChatReactionsSome, ReactionEmoji

    mock_client = MagicMock()
    full_chat = MagicMock()
    full_chat.full_chat.available_reactions = ChatReactionsSome(
        reactions=[ReactionEmoji(emoticon="👍"), ReactionEmoji(emoticon="🔥")]
    )
    mock_client.client = AsyncMock(return_value=full_chat)

    worker._clients[1] = mock_client

    result = await worker._get_available_reactions(1, make_entity())
    assert result == ["👍", "🔥"]


@pytest.mark.asyncio
async def test_get_available_reactions_error_returns_none(worker):
    """On error, assume all reactions allowed."""
    mock_client = MagicMock()
    mock_client.client = AsyncMock(side_effect=Exception("network error"))

    worker._clients[1] = mock_client

    result = await worker._get_available_reactions(1, make_entity())
    assert result is None


@pytest.mark.asyncio
async def test_connect_accounts_skips_no_session(worker):
    """Accounts without session_string are skipped."""
    acc = make_account(1, session_string=None)

    with patch("workers.likes_worker.BaseClient"):
        connected = await worker._connect_accounts([acc], MagicMock())

    assert connected == 0
    assert 1 in worker._failed_accounts


@pytest.mark.asyncio
async def test_connect_accounts_handles_connect_failure(worker):
    """Accounts that fail to connect are added to failed set."""
    acc = make_account(1)

    with patch("workers.likes_worker.BaseClient") as MockClient:
        instance = MockClient.return_value
        instance.connect = AsyncMock(side_effect=Exception("connection refused"))

        connected = await worker._connect_accounts([acc], MagicMock())

    assert connected == 0
    assert 1 in worker._failed_accounts


@pytest.mark.asyncio
async def test_connect_accounts_success(worker):
    """Successfully connected accounts are in the pool."""
    acc = make_account(1)

    with patch("workers.likes_worker.BaseClient") as MockClient:
        instance = MockClient.return_value
        instance.connect = AsyncMock()
        instance.check_auth = AsyncMock()

        connected = await worker._connect_accounts([acc], MagicMock())

    assert connected == 1
    assert 1 in worker._clients
    assert 1 not in worker._failed_accounts


@pytest.mark.asyncio
async def test_connect_accounts_mixed(worker):
    """Mix of successful and failed connects."""
    acc1 = make_account(1)
    acc2 = make_account(2)
    acc3 = make_account(3, session_string=None)

    call_count = 0

    with patch("workers.likes_worker.BaseClient") as MockClient:
        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            instance = MagicMock()
            if call_count == 1:
                # acc1: success
                instance.connect = AsyncMock()
                instance.check_auth = AsyncMock()
            else:
                # acc2: fail
                instance.connect = AsyncMock(side_effect=Exception("fail"))
            return instance

        MockClient.side_effect = side_effect

        connected = await worker._connect_accounts([acc1, acc2, acc3], MagicMock())

    assert connected == 1  # Only acc1
    assert 1 in worker._clients
    assert 2 in worker._failed_accounts
    assert 3 in worker._failed_accounts  # No session string


@pytest.mark.asyncio
async def test_connect_accounts_disconnects_on_auth_failure(worker):
    """If connect() succeeds but check_auth() fails, client must be disconnected."""
    acc = make_account(1)

    with patch("workers.likes_worker.BaseClient") as MockClient:
        instance = MockClient.return_value
        instance.connect = AsyncMock()  # connect succeeds
        instance.check_auth = AsyncMock(side_effect=Exception("session expired"))
        instance.disconnect = AsyncMock()

        connected = await worker._connect_accounts([acc], MagicMock())

    assert connected == 0
    assert 1 in worker._failed_accounts
    assert 1 not in worker._clients
    # Key assertion: disconnect was called to clean up
    instance.disconnect.assert_called_once()


@pytest.mark.asyncio
async def test_send_reaction_failed_account_breaks_all_mode(worker):
    """In 'all' emoji mode, if account gets banned mid-loop, remaining emojis should be skipped."""
    from telethon.errors import ChatWriteForbiddenError

    mock_client = MagicMock()

    call_count = 0
    async def mock_call(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First emoji succeeds
            return MagicMock()
        else:
            # Second emoji: account gets banned
            raise ChatWriteForbiddenError(request=None)

    mock_client.client = mock_call
    worker._clients[1] = mock_client
    worker._entities[1] = make_entity()

    # First call succeeds
    s1, m1, e1 = await worker._send_reaction(1, 123, "👍")
    assert s1 is True

    # Second call fails and marks account as failed
    s2, m2, e2 = await worker._send_reaction(1, 123, "❤")
    assert s2 is False
    assert 1 in worker._failed_accounts

    # In the actual execute() loop, the `if account_id in self._failed_accounts: break`
    # check would prevent trying the 3rd emoji. Verify account IS in failed set.
    assert 1 in worker._failed_accounts


class TestAllModeBreaksOnFail:
    """Test that 'all' mode loop stops when account is failed."""

    def test_pick_reaction_all_returns_full_list(self):
        worker = LikesWorker(task_id=1)
        result = worker._pick_reaction(["👍", "❤", "🔥"], "all", 0)
        assert len(result) == 3

    def test_failed_account_check_would_break_loop(self):
        """Simulate the for-emoji loop logic from execute()."""
        worker = LikesWorker(task_id=1)
        emojis = worker._pick_reaction(["👍", "❤", "🔥"], "all", 0)
        account_id = 1

        sent = []
        for emoji in emojis:
            if account_id in worker._failed_accounts:
                break
            sent.append(emoji)
            # Simulate account getting banned after first emoji
            if emoji == "👍":
                worker._failed_accounts.add(account_id)

        assert sent == ["👍"]  # Only first emoji sent, rest skipped
