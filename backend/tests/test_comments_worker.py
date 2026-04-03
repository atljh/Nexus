"""
Tests for CommentsWorker - client pool, entity cache, discussion group join,
comment sending, blacklist, account selection, SlowModeWait handling.

All Telegram/DB interactions are mocked. Tests verify the worker's internal logic.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from datetime import datetime, timezone

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from workers.comments_worker import CommentsWorker, SKIP_ACCOUNT_STATUSES
from workers.shared import SendStatus, SendResult


# ── Helpers ──

def make_account(id, session_string="session_abc", proxy=None, phone="+123", status="valid"):
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
    acc.status = status
    return acc


def make_entity(channel_id=100, title="Test Channel", username="test"):
    entity = MagicMock()
    entity.id = channel_id
    entity.title = title
    entity.username = username
    return entity


def make_target(channel_username="@test", channel_id=100, channel_title="Test", can_comment=True, status="joined"):
    target = MagicMock()
    target.channel_username = channel_username
    target.channel_id = channel_id
    target.channel_title = channel_title
    target.can_comment = can_comment
    target.status = status
    target.comments_sent = 0
    target.error_message = None
    return target


# ── Worker Init ──

class TestWorkerInit:
    """Test CommentsWorker initialization."""

    def test_init_empty_pools(self):
        worker = CommentsWorker(task_id=42)
        assert worker.task_id == 42
        assert worker._clients == {}
        assert worker._entities == {}
        assert worker._failed_accounts == set()
        assert worker._linked_chat_cache == {}
        assert worker._account_comment_count == {}
        assert worker._blacklist_cache == set()
        assert worker._ai_service is None
        assert worker.on_progress is None

    def test_init_with_progress(self):
        cb = AsyncMock()
        worker = CommentsWorker(task_id=1, on_progress=cb)
        assert worker.on_progress is cb


# ── Client Pool ──

@pytest.fixture
def worker():
    return CommentsWorker(task_id=1)


@pytest.mark.asyncio
async def test_connect_accounts_skips_no_session(worker):
    """Accounts without session_string are skipped."""
    acc = make_account(1, session_string=None)

    with patch("workers.comments_worker.BaseClient"):
        connected = await worker._connect_accounts([acc], MagicMock())

    assert connected == 0
    assert 1 in worker._failed_accounts


@pytest.mark.asyncio
async def test_connect_accounts_skips_bad_status(worker):
    """Accounts with banned/spamblock/etc status are skipped."""
    acc = make_account(1, status="banned")

    with patch("workers.comments_worker.BaseClient"):
        connected = await worker._connect_accounts([acc], MagicMock())

    assert connected == 0
    assert 1 in worker._failed_accounts


@pytest.mark.asyncio
async def test_connect_accounts_handles_connect_failure(worker):
    """Accounts that fail to connect are added to failed set."""
    acc = make_account(1)

    with patch("workers.comments_worker.BaseClient") as MockClient:
        instance = MockClient.return_value
        instance.connect = AsyncMock(side_effect=Exception("connection refused"))
        instance.disconnect = AsyncMock()

        connected = await worker._connect_accounts([acc], MagicMock())

    assert connected == 0
    assert 1 in worker._failed_accounts


@pytest.mark.asyncio
async def test_connect_accounts_success(worker):
    """Successfully connected accounts are in the pool."""
    acc = make_account(1)

    with patch("workers.comments_worker.BaseClient") as MockClient:
        instance = MockClient.return_value
        instance.connect = AsyncMock()
        instance.check_auth = AsyncMock()

        connected = await worker._connect_accounts([acc], MagicMock())

    assert connected == 1
    assert 1 in worker._clients


@pytest.mark.asyncio
async def test_setup_channels_public_flow_checks_subscription_and_joins(worker):
    """Public/numeric targets must still run subscription/join logic after entity resolution."""
    target = make_target(channel_username="@publictest", channel_id=None, channel_title=None, can_comment=False, status="pending")
    entity = make_entity(channel_id=777, title="Public Test", username="publictest")

    worker._clients[1] = MagicMock()
    worker._resolve_entity = AsyncMock(return_value=entity)
    worker._check_subscription = AsyncMock(return_value=(False, None))
    worker._join_channel = AsyncMock(return_value=(True, None))
    worker._get_linked_chat = AsyncMock(return_value=999)
    worker._join_discussion_group = AsyncMock(return_value=(True, None))
    worker._track_channel_membership = MagicMock()

    with patch("workers.comments_worker.asyncio.sleep", new=AsyncMock()):
        ready = await worker._setup_channels_for_account(1, [target], MagicMock())

    assert ready == 1
    worker._check_subscription.assert_awaited_once_with(1, entity)
    worker._join_channel.assert_awaited_once_with(1, entity, "@publictest")
    assert target.status == "joined"
    assert target.can_comment is True
    assert 1 not in worker._failed_accounts


@pytest.mark.asyncio
async def test_connect_accounts_disconnects_on_auth_failure(worker):
    """If connect() succeeds but check_auth() fails, client must be disconnected."""
    acc = make_account(1)

    with patch("workers.comments_worker.BaseClient") as MockClient:
        instance = MockClient.return_value
        instance.connect = AsyncMock()
        instance.check_auth = AsyncMock(side_effect=Exception("session expired"))
        instance.disconnect = AsyncMock()

        connected = await worker._connect_accounts([acc], MagicMock())

    assert connected == 0
    assert 1 in worker._failed_accounts
    assert 1 not in worker._clients
    instance.disconnect.assert_called_once()


@pytest.mark.asyncio
async def test_connect_accounts_mixed(worker):
    """Mix of successful, failed, and no-session accounts."""
    acc1 = make_account(1)
    acc2 = make_account(2)
    acc3 = make_account(3, session_string=None)

    call_count = 0

    with patch("workers.comments_worker.BaseClient") as MockClient:
        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            instance = MagicMock()
            if call_count == 1:
                instance.connect = AsyncMock()
                instance.check_auth = AsyncMock()
            else:
                instance.connect = AsyncMock(side_effect=Exception("fail"))
                instance.disconnect = AsyncMock()
            return instance

        MockClient.side_effect = side_effect

        connected = await worker._connect_accounts([acc1, acc2, acc3], MagicMock())

    assert connected == 1
    assert 1 in worker._clients
    assert 2 in worker._failed_accounts
    assert 3 in worker._failed_accounts


@pytest.mark.asyncio
async def test_disconnect_all(worker):
    """All clients should be disconnected and pools cleared."""
    c1 = MagicMock()
    c1.disconnect = AsyncMock()
    c2 = MagicMock()
    c2.disconnect = AsyncMock()

    worker._clients = {1: c1, 2: c2}
    worker._entities = {(1, "@ch"): "e1", (2, "@ch"): "e2"}

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

    await worker._disconnect_all()

    assert worker._clients == {}


# ── Entity Resolution ──

@pytest.mark.asyncio
async def test_resolve_entity_cached(worker):
    """Entity should be resolved once per (account_id, channel) and cached."""
    mock_client = MagicMock()
    entity = make_entity(200)
    mock_client.client = MagicMock()
    mock_client.client.get_entity = AsyncMock(return_value=entity)

    worker._clients[1] = mock_client

    result1 = await worker._resolve_entity(1, "@test")
    result2 = await worker._resolve_entity(1, "@test")

    assert result1 is entity
    assert result2 is entity
    mock_client.client.get_entity.assert_called_once_with("@test")


@pytest.mark.asyncio
async def test_resolve_entity_different_channels(worker):
    """Different channels should get different cache entries."""
    mock_client = MagicMock()
    entity1 = make_entity(100)
    entity2 = make_entity(200)
    mock_client.client = MagicMock()
    mock_client.client.get_entity = AsyncMock(side_effect=[entity1, entity2])

    worker._clients[1] = mock_client

    r1 = await worker._resolve_entity(1, "@ch1")
    r2 = await worker._resolve_entity(1, "@ch2")

    assert r1 is entity1
    assert r2 is entity2
    assert mock_client.client.get_entity.call_count == 2


@pytest.mark.asyncio
async def test_resolve_entity_different_accounts(worker):
    """Different accounts should get separate cache entries for the same channel."""
    mc1 = MagicMock()
    entity1 = make_entity(100)
    mc1.client = MagicMock()
    mc1.client.get_entity = AsyncMock(return_value=entity1)

    mc2 = MagicMock()
    entity2 = make_entity(100)
    mc2.client = MagicMock()
    mc2.client.get_entity = AsyncMock(return_value=entity2)

    worker._clients[1] = mc1
    worker._clients[2] = mc2

    r1 = await worker._resolve_entity(1, "@test")
    r2 = await worker._resolve_entity(2, "@test")

    assert r1 is entity1
    assert r2 is entity2


@pytest.mark.asyncio
async def test_resolve_entity_after_invite_join_falls_back_to_target(worker):
    """Comments worker should re-resolve the joined channel when invite import returned no entity."""
    entity = make_entity(-100123)
    worker._resolve_entity = AsyncMock(return_value=entity)

    result = await worker._resolve_entity_after_invite_join(1, "-100123", None)

    assert result is entity
    worker._resolve_entity.assert_awaited_once_with(1, "-100123")


@pytest.mark.asyncio
async def test_resolve_entity_after_invite_join_skips_plain_invite(worker):
    """Pure invite links cannot be re-resolved if Telegram returned no entity."""
    worker._resolve_entity = AsyncMock()

    result = await worker._resolve_entity_after_invite_join(1, "https://t.me/+abc123", None)

    assert result is None
    worker._resolve_entity.assert_not_called()


# ── Subscription & Join ──

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

    is_sub, error = await worker._check_subscription(1, make_entity())

    assert is_sub is False
    assert error is None


@pytest.mark.asyncio
async def test_check_subscription_channel_private(worker):
    """ChannelPrivateError → CHANNEL_PRIVATE error string."""
    from telethon.errors import ChannelPrivateError

    mock_client = MagicMock()
    mock_client.client = AsyncMock(side_effect=ChannelPrivateError(request=None))

    worker._clients[1] = mock_client

    is_sub, error = await worker._check_subscription(1, make_entity())

    assert is_sub is False
    assert error == "CHANNEL_PRIVATE"


@pytest.mark.asyncio
async def test_join_channel_success(worker):
    """Successful join."""
    mock_client = MagicMock()
    mock_client.client = AsyncMock(return_value=MagicMock())

    worker._clients[1] = mock_client

    success, error = await worker._join_channel(1, make_entity(), "@test")

    assert success is True
    assert error is None


@pytest.mark.asyncio
async def test_join_channel_private(worker):
    """ChannelPrivateError on join."""
    from telethon.errors import ChannelPrivateError

    mock_client = MagicMock()
    mock_client.client = AsyncMock(side_effect=ChannelPrivateError(request=None))

    worker._clients[1] = mock_client

    success, error = await worker._join_channel(1, make_entity(), "@test")

    assert success is False
    assert "private" in error.lower()


@pytest.mark.asyncio
async def test_join_channel_too_many(worker):
    """ChannelsTooMuchError on join."""
    from telethon.errors import ChannelsTooMuchError

    mock_client = MagicMock()
    mock_client.client = AsyncMock(side_effect=ChannelsTooMuchError(request=None))

    worker._clients[1] = mock_client

    success, error = await worker._join_channel(1, make_entity(), "@test")

    assert success is False
    assert "too many" in error.lower()


@pytest.mark.asyncio
async def test_join_channel_flood_wait_raises(worker):
    """FloodWaitError should be re-raised, not caught."""
    from telethon.errors import FloodWaitError

    mock_client = MagicMock()
    mock_client.client = AsyncMock(side_effect=FloodWaitError(request=None, capture=5))

    worker._clients[1] = mock_client

    with pytest.raises(FloodWaitError):
        await worker._join_channel(1, make_entity(), "@test")


# ── Linked Chat & Discussion Group ──

@pytest.mark.asyncio
async def test_get_linked_chat_found(worker):
    """Successfully get linked discussion group."""
    mock_client = MagicMock()
    full_result = MagicMock()
    full_result.full_chat.linked_chat_id = 999
    mock_client.client = AsyncMock(return_value=full_result)

    worker._clients[1] = mock_client
    entity = make_entity(100)

    linked = await worker._get_linked_chat(1, entity)

    assert linked == 999
    assert worker._linked_chat_cache[(1, 100)] == 999


@pytest.mark.asyncio
async def test_get_linked_chat_none(worker):
    """No linked discussion group."""
    mock_client = MagicMock()
    full_result = MagicMock()
    full_result.full_chat.linked_chat_id = None
    mock_client.client = AsyncMock(return_value=full_result)

    worker._clients[1] = mock_client
    entity = make_entity(100)

    linked = await worker._get_linked_chat(1, entity)

    assert linked is None
    assert worker._linked_chat_cache[(1, 100)] is None


@pytest.mark.asyncio
async def test_get_linked_chat_cached(worker):
    """Cached value should be returned without API call."""
    mock_client = MagicMock()
    mock_client.client = AsyncMock()

    worker._clients[1] = mock_client
    worker._linked_chat_cache[(1, 100)] = 999

    entity = make_entity(100)
    linked = await worker._get_linked_chat(1, entity)

    assert linked == 999
    mock_client.client.assert_not_called()


@pytest.mark.asyncio
async def test_get_linked_chat_error_returns_none(worker):
    """On error, return None and cache it."""
    mock_client = MagicMock()
    mock_client.client = AsyncMock(side_effect=Exception("network error"))

    worker._clients[1] = mock_client
    entity = make_entity(100)

    linked = await worker._get_linked_chat(1, entity)

    assert linked is None
    assert worker._linked_chat_cache[(1, 100)] is None


@pytest.mark.asyncio
async def test_join_discussion_group_already_member(worker):
    """If already a member, return success without joining."""
    telegram_client = AsyncMock(return_value=MagicMock())
    telegram_client.get_input_entity = AsyncMock(return_value="input_entity")
    telegram_client.get_entity = AsyncMock()

    mock_client = MagicMock()
    mock_client.client = telegram_client

    worker._clients[1] = mock_client

    success, error = await worker._join_discussion_group(1, 999)

    assert success is True
    assert error is None
    telegram_client.get_input_entity.assert_awaited_once_with(999)


@pytest.mark.asyncio
async def test_join_discussion_group_needs_join(worker):
    """If not a member, join the group."""
    from telethon.errors import UserNotParticipantError

    async def mock_call(request):
        request_name = type(request).__name__
        if request_name == "GetParticipantRequest":
            raise UserNotParticipantError(request=None)
        if request_name == "JoinChannelRequest":
            return MagicMock()
        raise AssertionError(f"Unexpected request: {request_name}")

    telegram_client = AsyncMock(side_effect=mock_call)
    telegram_client.get_input_entity = AsyncMock(return_value="input_entity")
    telegram_client.get_entity = AsyncMock()

    mock_client = MagicMock()
    mock_client.client = telegram_client
    worker._clients[1] = mock_client

    success, error = await worker._join_discussion_group(1, 999)

    assert success is True
    assert error is None


@pytest.mark.asyncio
async def test_join_discussion_group_uses_get_entity_fallback(worker):
    """Fallback to get_entity when get_input_entity cannot resolve the group."""
    telegram_client = AsyncMock(return_value=MagicMock())
    telegram_client.get_input_entity = AsyncMock(side_effect=ValueError("not cached"))
    telegram_client.get_entity = AsyncMock(return_value="resolved_entity")

    mock_client = MagicMock()
    mock_client.client = telegram_client
    worker._clients[1] = mock_client

    success, error = await worker._join_discussion_group(1, 999)

    assert success is True
    assert error is None
    telegram_client.get_entity.assert_awaited_once_with(999)


@pytest.mark.asyncio
async def test_join_discussion_group_flood_wait_raises(worker):
    """FloodWaitError should be re-raised."""
    from telethon.errors import UserNotParticipantError, FloodWaitError

    async def mock_call(request):
        request_name = type(request).__name__
        if request_name == "GetParticipantRequest":
            raise UserNotParticipantError(request=None)
        if request_name == "JoinChannelRequest":
            raise FloodWaitError(request=None, capture=10)
        raise AssertionError(f"Unexpected request: {request_name}")

    telegram_client = AsyncMock(side_effect=mock_call)
    telegram_client.get_input_entity = AsyncMock(return_value="input_entity")
    telegram_client.get_entity = AsyncMock()

    mock_client = MagicMock()
    mock_client.client = telegram_client
    worker._clients[1] = mock_client

    with pytest.raises(FloodWaitError):
        await worker._join_discussion_group(1, 999)


# ── Send Comment ──

@pytest.mark.asyncio
async def test_send_comment_success(worker):
    """Successful comment sending."""
    mock_client = MagicMock()
    sent_msg = MagicMock()
    sent_msg.id = 456

    # Mock iter_messages to return a post
    mock_msg = MagicMock()
    mock_msg.id = 123

    async def mock_iter_messages(*args, **kwargs):
        yield mock_msg

    mock_client.client = MagicMock()
    mock_client.client.iter_messages = mock_iter_messages
    mock_client.client.send_message = AsyncMock(return_value=sent_msg)

    worker._clients[1] = mock_client
    entity = make_entity(100)
    worker._entities[(1, "@test")] = entity

    target = make_target()
    result = await worker._send_comment(1, target, "Hello!")

    assert result.success is True
    assert result.status == SendStatus.OK
    assert result.sent_message is sent_msg
    mock_client.client.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_send_comment_with_explicit_post_id(worker):
    """When post_id is provided, skip iter_messages."""
    mock_client = MagicMock()
    sent_msg = MagicMock()

    mock_client.client = MagicMock()
    mock_client.client.send_message = AsyncMock(return_value=sent_msg)

    worker._clients[1] = mock_client
    entity = make_entity(100)
    worker._entities[(1, "@test")] = entity

    target = make_target()
    result = await worker._send_comment(1, target, "Hello!", post_id=42)

    assert result.success is True
    # comment_to should use 42
    call_kwargs = mock_client.client.send_message.call_args[1]
    assert call_kwargs["comment_to"] == 42


@pytest.mark.asyncio
async def test_send_comment_no_posts(worker):
    """Channel has no posts → SKIP."""
    mock_client = MagicMock()

    async def mock_iter_messages(*args, **kwargs):
        return
        yield  # empty async generator

    mock_client.client = MagicMock()
    mock_client.client.iter_messages = mock_iter_messages

    worker._clients[1] = mock_client
    worker._entities[(1, "@test")] = make_entity(100)

    target = make_target()
    result = await worker._send_comment(1, target, "Hello!")

    assert result.status == SendStatus.SKIP
    assert "No posts" in result.message


@pytest.mark.asyncio
async def test_send_comment_slow_mode(worker):
    """SlowModeWaitError → SLOW_MODE with wait_seconds."""
    from telethon.errors import SlowModeWaitError

    mock_client = MagicMock()
    mock_client.client = MagicMock()
    mock_client.client.send_message = AsyncMock(
        side_effect=SlowModeWaitError(request=None, capture=30)
    )

    worker._clients[1] = mock_client
    worker._entities[(1, "@test")] = make_entity(100)

    target = make_target()
    result = await worker._send_comment(1, target, "Hello!", post_id=10)

    assert result.status == SendStatus.SLOW_MODE
    assert result.wait_seconds == 30
    assert "SlowMode" in result.message


@pytest.mark.asyncio
async def test_send_comment_flood_wait(worker):
    """FloodWaitError → FLOOD_WAIT with wait_seconds."""
    from telethon.errors import FloodWaitError

    mock_client = MagicMock()
    mock_client.client = MagicMock()
    mock_client.client.send_message = AsyncMock(
        side_effect=FloodWaitError(request=None, capture=60)
    )

    worker._clients[1] = mock_client
    worker._entities[(1, "@test")] = make_entity(100)

    target = make_target()
    result = await worker._send_comment(1, target, "Hello!", post_id=10)

    assert result.status == SendStatus.FLOOD_WAIT
    assert result.wait_seconds == 60


@pytest.mark.asyncio
async def test_send_comment_write_forbidden(worker):
    """ChatWriteForbiddenError → WRITE_FORBIDDEN (does NOT add to _failed_accounts)."""
    from telethon.errors import ChatWriteForbiddenError

    mock_client = MagicMock()
    mock_client.client = MagicMock()
    mock_client.client.send_message = AsyncMock(
        side_effect=ChatWriteForbiddenError(request=None)
    )

    worker._clients[1] = mock_client
    worker._entities[(1, "@test")] = make_entity(100)

    target = make_target()
    result = await worker._send_comment(1, target, "Hello!", post_id=10)

    assert result.status == SendStatus.WRITE_FORBIDDEN
    # Unlike likes_worker, comments worker does NOT add to _failed_accounts
    # for channel-level errors (account may work in other channels)
    assert 1 not in worker._failed_accounts


@pytest.mark.asyncio
async def test_send_comment_banned_in_channel(worker):
    """UserBannedInChannelError → BANNED."""
    from telethon.errors import UserBannedInChannelError

    mock_client = MagicMock()
    mock_client.client = MagicMock()
    mock_client.client.send_message = AsyncMock(
        side_effect=UserBannedInChannelError(request=None)
    )

    worker._clients[1] = mock_client
    worker._entities[(1, "@test")] = make_entity(100)

    target = make_target()
    result = await worker._send_comment(1, target, "Hello!", post_id=10)

    assert result.status == SendStatus.BANNED


@pytest.mark.asyncio
async def test_send_comment_channel_private(worker):
    """ChannelPrivateError → NO_ACCESS."""
    from telethon.errors import ChannelPrivateError

    mock_client = MagicMock()
    mock_client.client = MagicMock()
    mock_client.client.send_message = AsyncMock(
        side_effect=ChannelPrivateError(request=None)
    )

    worker._clients[1] = mock_client
    worker._entities[(1, "@test")] = make_entity(100)

    target = make_target()
    result = await worker._send_comment(1, target, "Hello!", post_id=10)

    assert result.status == SendStatus.NO_ACCESS


@pytest.mark.asyncio
async def test_send_comment_msg_id_invalid(worker):
    """MsgIdInvalidError → ERROR."""
    from telethon.errors import MsgIdInvalidError

    mock_client = MagicMock()
    mock_client.client = MagicMock()
    mock_client.client.send_message = AsyncMock(
        side_effect=MsgIdInvalidError(request=None)
    )

    worker._clients[1] = mock_client
    worker._entities[(1, "@test")] = make_entity(100)

    target = make_target()
    result = await worker._send_comment(1, target, "Hello!", post_id=10)

    assert result.status == SendStatus.ERROR
    assert "comments" in result.error.lower() or "Invalid" in result.error


@pytest.mark.asyncio
async def test_send_comment_no_client(worker):
    """No client in pool → ERROR."""
    target = make_target()
    result = await worker._send_comment(1, target, "Hello!")

    assert result.status == SendStatus.ERROR
    assert "not connected" in result.message.lower()


@pytest.mark.asyncio
async def test_send_comment_no_entity_resolves_on_fly(worker):
    """No cached entity → try to resolve on the fly."""
    mock_client = MagicMock()
    entity = make_entity(100)
    sent_msg = MagicMock()

    mock_client.client = MagicMock()
    mock_client.client.get_entity = AsyncMock(return_value=entity)
    mock_client.client.send_message = AsyncMock(return_value=sent_msg)

    worker._clients[1] = mock_client
    # No entity cached

    target = make_target()
    result = await worker._send_comment(1, target, "Hello!", post_id=10)

    assert result.success is True
    # Entity should now be cached
    assert (1, "@test") in worker._entities


@pytest.mark.asyncio
async def test_send_comment_no_entity_resolve_fails(worker):
    """No cached entity and resolve fails → ERROR."""
    mock_client = MagicMock()
    mock_client.client = MagicMock()
    mock_client.client.get_entity = AsyncMock(side_effect=Exception("not found"))

    worker._clients[1] = mock_client

    target = make_target()
    result = await worker._send_comment(1, target, "Hello!")

    assert result.status == SendStatus.ERROR
    assert "not resolved" in result.message.lower()


# ── Handle Send Result ──

class TestHandleSendResult:
    """Test _handle_send_result: blacklist, account status, pool exclusion."""

    def test_success_does_nothing(self):
        worker = CommentsWorker(task_id=1)
        db = MagicMock()
        account = make_account(1)
        target = make_target()
        result = SendResult(status=SendStatus.OK, message="ok")

        worker._handle_send_result(db, account, target, result)

        assert 1 not in worker._failed_accounts
        assert len(worker._blacklist_cache) == 0

    def test_account_banned_excludes_from_pool(self):
        worker = CommentsWorker(task_id=1)
        db = MagicMock()
        account = make_account(1)
        target = make_target()
        result = SendResult(status=SendStatus.ACCOUNT_BANNED, message="banned", error="banned")

        worker._handle_send_result(db, account, target, result)

        assert 1 in worker._failed_accounts

    def test_session_expired_excludes_from_pool(self):
        worker = CommentsWorker(task_id=1)
        db = MagicMock()
        account = make_account(1)
        target = make_target()
        result = SendResult(status=SendStatus.SESSION_EXPIRED, message="expired", error="expired")

        worker._handle_send_result(db, account, target, result)

        assert 1 in worker._failed_accounts

    def test_write_forbidden_blacklists_channel_not_pool(self):
        """WRITE_FORBIDDEN should blacklist for channel but NOT exclude from pool."""
        worker = CommentsWorker(task_id=1)
        db = MagicMock()
        account = make_account(1)
        target = make_target()

        # Mock AccountBlacklist.add_to_blacklist
        with patch("workers.comments_worker.AccountBlacklist") as MockBL:
            MockBL.add_to_blacklist = MagicMock()

            result = SendResult(
                status=SendStatus.WRITE_FORBIDDEN,
                message="forbidden",
                error="forbidden"
            )
            worker._handle_send_result(db, account, target, result)

        # NOT excluded from pool (can still comment in other channels)
        assert 1 not in worker._failed_accounts
        # But blacklisted for this channel
        assert (1, "id:100") in worker._blacklist_cache or (1, "un:@test") in worker._blacklist_cache

    def test_banned_blacklists_channel(self):
        """BANNED should blacklist for channel."""
        worker = CommentsWorker(task_id=1)
        db = MagicMock()
        account = make_account(1)
        target = make_target()

        with patch("workers.comments_worker.AccountBlacklist") as MockBL:
            MockBL.add_to_blacklist = MagicMock()

            result = SendResult(status=SendStatus.BANNED, message="banned", error="banned")
            worker._handle_send_result(db, account, target, result)

        assert (1, "id:100") in worker._blacklist_cache


# ── Account Selection ──

class TestSelectAccount:
    """Test _select_account with pool, blacklist, and limit filtering."""

    def test_selects_available_account(self):
        worker = CommentsWorker(task_id=1)
        worker._clients = {1: MagicMock(), 2: MagicMock()}

        accounts = [make_account(1), make_account(2)]
        result = worker._select_account(accounts, "random", 10, 0)

        assert result is not None
        assert result.id in [1, 2]

    def test_skips_failed_accounts(self):
        worker = CommentsWorker(task_id=1)
        worker._clients = {1: MagicMock(), 2: MagicMock()}
        worker._failed_accounts = {1}

        accounts = [make_account(1), make_account(2)]
        result = worker._select_account(accounts, "random", 10, 0)

        assert result.id == 2

    def test_skips_accounts_not_in_pool(self):
        worker = CommentsWorker(task_id=1)
        worker._clients = {1: MagicMock()}

        accounts = [make_account(1), make_account(2)]
        result = worker._select_account(accounts, "random", 10, 0)

        assert result.id == 1

    def test_skips_exhausted_accounts(self):
        worker = CommentsWorker(task_id=1)
        worker._clients = {1: MagicMock(), 2: MagicMock()}
        worker._account_comment_count = {1: 10}

        accounts = [make_account(1), make_account(2)]
        result = worker._select_account(accounts, "random", 10, 0)

        assert result.id == 2

    def test_skips_blacklisted_accounts(self):
        worker = CommentsWorker(task_id=1)
        worker._clients = {1: MagicMock(), 2: MagicMock()}
        worker._blacklist_cache = {(1, "id:100")}

        accounts = [make_account(1), make_account(2)]
        result = worker._select_account(accounts, "random", 10, 0, channel_id=100)

        assert result.id == 2

    def test_returns_none_when_all_exhausted(self):
        worker = CommentsWorker(task_id=1)
        worker._clients = {1: MagicMock()}
        worker._account_comment_count = {1: 10}

        accounts = [make_account(1)]
        result = worker._select_account(accounts, "random", 10, 0)

        assert result is None

    def test_round_robin_mode(self):
        worker = CommentsWorker(task_id=1)
        worker._clients = {1: MagicMock(), 2: MagicMock(), 3: MagicMock()}

        accounts = [make_account(1), make_account(2), make_account(3)]

        results = [
            worker._select_account(accounts, "round_robin", 100, i).id
            for i in range(6)
        ]
        assert results == [1, 2, 3, 1, 2, 3]

    def test_skips_bad_status_accounts(self):
        worker = CommentsWorker(task_id=1)
        worker._clients = {1: MagicMock(), 2: MagicMock()}

        accounts = [make_account(1, status="banned"), make_account(2)]
        result = worker._select_account(accounts, "random", 10, 0)

        assert result.id == 2


# ── Target Channel Selection ──

class TestSelectTargetChannel:
    def test_selects_valid_target(self):
        worker = CommentsWorker(task_id=1)
        t1 = make_target(can_comment=True, status="joined")
        t2 = make_target(can_comment=False, status="cannot_comment")

        result = worker._select_target_channel([t1, t2])
        assert result is t1

    def test_returns_none_when_no_valid_targets(self):
        worker = CommentsWorker(task_id=1)
        t1 = make_target(can_comment=False, status="error")

        result = worker._select_target_channel([t1])
        assert result is None


# ── Blacklist Cache ──

class TestBlacklistCache:
    def test_is_blacklisted_by_channel_id(self):
        worker = CommentsWorker(task_id=1)
        worker._blacklist_cache = {(1, "id:100")}

        assert worker._is_blacklisted_cached(1, 100, None) is True
        assert worker._is_blacklisted_cached(1, 200, None) is False
        assert worker._is_blacklisted_cached(2, 100, None) is False

    def test_is_blacklisted_by_username(self):
        worker = CommentsWorker(task_id=1)
        worker._blacklist_cache = {(1, "un:@test")}

        assert worker._is_blacklisted_cached(1, None, "@test") is True
        assert worker._is_blacklisted_cached(1, None, "@other") is False

    def test_add_to_blacklist_cache(self):
        worker = CommentsWorker(task_id=1)

        worker._add_to_blacklist_cache(1, 100, "@test")

        assert (1, "id:100") in worker._blacklist_cache
        assert (1, "un:@test") in worker._blacklist_cache

    def test_load_blacklist_cache(self):
        worker = CommentsWorker(task_id=1)
        db = MagicMock()

        # Mock query result
        db.query.return_value.filter.return_value.all.return_value = [
            (1, 100, "@ch1"),
            (2, 200, None),
        ]

        worker._load_blacklist_cache(db, [1, 2])

        assert (1, "id:100") in worker._blacklist_cache
        assert (1, "un:@ch1") in worker._blacklist_cache
        assert (2, "id:200") in worker._blacklist_cache


# ── Should Comment ──

class TestShouldComment:
    def test_all_mode_always_true(self):
        worker = CommentsWorker(task_id=1)
        assert worker._should_comment("anything", {"comment_mode": "all"}) is True

    def test_keywords_mode_matches(self):
        worker = CommentsWorker(task_id=1)
        config = {"comment_mode": "keywords", "keywords": ["crypto", "bitcoin"]}
        assert worker._should_comment("Buy crypto now!", config) is True
        assert worker._should_comment("Buy stocks now!", config) is False

    def test_keywords_mode_case_insensitive(self):
        worker = CommentsWorker(task_id=1)
        config = {"comment_mode": "keywords", "keywords": ["Crypto"]}
        assert worker._should_comment("buy CRYPTO now", config) is True

    def test_keywords_mode_empty_keywords_returns_true(self):
        worker = CommentsWorker(task_id=1)
        config = {"comment_mode": "keywords", "keywords": []}
        assert worker._should_comment("anything", config) is True

    def test_random_mode(self):
        worker = CommentsWorker(task_id=1)
        config = {"comment_mode": "random", "comment_probability": 1.0}
        assert worker._should_comment("test", config) is True

        config2 = {"comment_mode": "random", "comment_probability": 0.0}
        assert worker._should_comment("test", config2) is False

    def test_unknown_mode_defaults_true(self):
        worker = CommentsWorker(task_id=1)
        assert worker._should_comment("test", {"comment_mode": "unknown"}) is True


# ── AI Service Init ──

class TestInitAIService:
    def test_no_ai_enabled(self):
        worker = CommentsWorker(task_id=1)
        worker._init_ai_service({"ai_enabled": False})
        assert worker._ai_service is None

    def test_ai_enabled_no_key(self):
        worker = CommentsWorker(task_id=1)
        worker._init_ai_service({"ai_enabled": True, "ai_api_key": ""})
        assert worker._ai_service is None

    def test_ai_enabled_with_key(self):
        worker = CommentsWorker(task_id=1)
        with patch("workers.comments_worker.AIService") as MockAI:
            worker._init_ai_service({
                "ai_enabled": True,
                "ai_api_key": "sk-test",
                "ai_model": "gpt-4o",
                "ai_base_url": "https://api.openai.com/v1",
            })
        assert worker._ai_service is not None


# ── Setup Channels ──

@pytest.mark.asyncio
async def test_setup_channels_with_discussion_group(worker):
    """Full setup: resolve → subscribe → get linked chat → join discussion."""
    from telethon.errors import UserNotParticipantError

    entity = make_entity(100)
    mock_client = MagicMock()

    call_count = 0

    async def mock_call(request):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # GetParticipantRequest for channel → already subscribed
            return MagicMock()
        elif call_count == 2:
            # GetFullChannelRequest → linked_chat_id=999
            result = MagicMock()
            result.full_chat.linked_chat_id = 999
            return result
        elif call_count == 3:
            # GetParticipantRequest for discussion → not subscribed
            raise UserNotParticipantError(request=None)
        elif call_count == 4:
            # JoinChannelRequest for discussion → success
            return MagicMock()

    mock_client.client = mock_call
    mock_client.client.get_entity = AsyncMock(return_value=entity)

    # We need client to be callable and have get_entity
    # Reset to use a proper MagicMock with both behaviors
    mock_client2 = MagicMock()
    mock_client2.client = MagicMock()
    mock_client2.client.get_entity = AsyncMock(return_value=entity)
    mock_client2.client.__call__ = mock_call
    # Override to use the callable for Telethon requests
    mock_client2.client.side_effect = None

    # Simpler approach: just mock _resolve_entity and other methods directly
    worker._clients[1] = MagicMock()

    with patch.object(worker, '_resolve_entity', AsyncMock(return_value=entity)), \
         patch.object(worker, '_check_subscription', AsyncMock(return_value=(True, None))), \
         patch.object(worker, '_get_linked_chat', AsyncMock(return_value=999)), \
         patch.object(worker, '_join_discussion_group', AsyncMock(return_value=(True, None))):

        target = make_target(can_comment=False, status="pending")
        db = MagicMock()
        ready = await worker._setup_channels_for_account(1, [target], db)

    assert ready == 1
    assert target.can_comment is True
    assert target.status == "joined"


@pytest.mark.asyncio
async def test_setup_channels_no_discussion_group(worker):
    """Channel without discussion group → cannot comment."""
    entity = make_entity(100)
    worker._clients[1] = MagicMock()

    with patch.object(worker, '_resolve_entity', AsyncMock(return_value=entity)), \
         patch.object(worker, '_check_subscription', AsyncMock(return_value=(True, None))), \
         patch.object(worker, '_get_linked_chat', AsyncMock(return_value=None)):

        target = make_target(can_comment=False, status="pending")
        db = MagicMock()
        ready = await worker._setup_channels_for_account(1, [target], db)

    assert ready == 0
    assert target.can_comment is False
    assert target.status == "cannot_comment"


@pytest.mark.asyncio
async def test_setup_channels_auto_join(worker):
    """Not subscribed → join → re-resolve → get linked chat."""
    entity = make_entity(100)
    worker._clients[1] = MagicMock()

    resolve_call_count = 0

    async def mock_resolve(account_id, channel):
        nonlocal resolve_call_count
        resolve_call_count += 1
        return entity

    with patch.object(worker, '_resolve_entity', side_effect=mock_resolve), \
         patch.object(worker, '_check_subscription', AsyncMock(return_value=(False, None))), \
         patch.object(worker, '_join_channel', AsyncMock(return_value=(True, None))), \
         patch.object(worker, '_get_linked_chat', AsyncMock(return_value=999)), \
         patch.object(worker, '_join_discussion_group', AsyncMock(return_value=(True, None))):

        target = make_target(can_comment=False, status="pending")
        db = MagicMock()
        ready = await worker._setup_channels_for_account(1, [target], db)

    assert ready == 1
    # Entity should have been popped from cache and re-resolved (2 calls)
    assert resolve_call_count == 2


@pytest.mark.asyncio
async def test_setup_channels_flood_wait_excludes_account(worker):
    """FloodWait during setup should put the account on cooldown, not fail it permanently."""
    from telethon.errors import FloodWaitError

    entity = make_entity(100)
    worker._clients[1] = MagicMock()

    async def mock_resolve(account_id, channel):
        raise FloodWaitError(request=None, capture=60)

    with patch.object(worker, '_resolve_entity', side_effect=mock_resolve):
        target = make_target()
        db = MagicMock()
        await worker._setup_channels_for_account(1, [target], db)

    assert 1 not in worker._failed_accounts
    assert 1 in worker._flood_wait_until


@pytest.mark.asyncio
async def test_setup_channels_skips_blacklisted(worker):
    """Blacklisted channels should be skipped."""
    worker._clients[1] = MagicMock()
    worker._blacklist_cache = {(1, "id:100")}

    target = make_target(channel_id=100)
    db = MagicMock()

    with patch.object(worker, '_resolve_entity', AsyncMock()) as mock_resolve:
        ready = await worker._setup_channels_for_account(1, [target], db)

    assert ready == 0
    mock_resolve.assert_not_called()


# ── SKIP_ACCOUNT_STATUSES ──

class TestSkipAccountStatuses:
    def test_contains_expected_statuses(self):
        assert "banned" in SKIP_ACCOUNT_STATUSES
        assert "spamblock" in SKIP_ACCOUNT_STATUSES
        assert "session_expired" in SKIP_ACCOUNT_STATUSES
        assert "invalid" in SKIP_ACCOUNT_STATUSES
        assert "deactivated" in SKIP_ACCOUNT_STATUSES

    def test_valid_not_in_skip(self):
        assert "valid" not in SKIP_ACCOUNT_STATUSES


# ── Get Proxy Dict ──

class TestGetProxyDict:
    def test_no_proxy(self):
        acc = make_account(1)
        acc.proxy = None
        assert CommentsWorker._get_proxy_dict(acc) is None

    def test_with_proxy(self):
        acc = make_account(1)
        acc.proxy = MagicMock()
        acc.proxy.type = "socks5"
        acc.proxy.host = "1.2.3.4"
        acc.proxy.port = 1080
        acc.proxy.username = "user"
        acc.proxy.password = "pass"

        result = CommentsWorker._get_proxy_dict(acc)
        assert result == {
            "type": "socks5",
            "host": "1.2.3.4",
            "port": 1080,
            "username": "user",
            "password": "pass",
        }
