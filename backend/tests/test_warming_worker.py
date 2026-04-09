"""
Tests for WarmingWorker.

Focus on the worker's local decision-making; Telegram and database access stay mocked.
"""

import asyncio
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from workers.warming_worker import (
    WarmingWorker,
    PRIVATE_CHANNEL_INVITE_REQUIRED,
    INVALID_WARMING_TARGET,
    ACTION_SKIPPED_MESSAGE,
    ALL_ACCOUNTS_FAILED_TO_CONNECT,
    ALL_ELIGIBLE_ACCOUNTS_EXHAUSTED,
)


class TestWarmingWorkerHelpers:
    def setup_method(self):
        self.worker = WarmingWorker(task_id=1)

    def test_extract_invite_hash(self):
        assert self.worker._extract_invite_hash("https://t.me/+abc123") == "abc123"
        assert self.worker._extract_invite_hash("https://t.me/joinchat/Hash_42") == "Hash_42"
        assert self.worker._extract_invite_hash("@publicchannel") is None

    def test_normalize_public_target(self):
        assert self.worker._normalize_public_target("channelname") == "@channelname"
        assert self.worker._normalize_public_target("https://t.me/example") == "@example"
        assert self.worker._normalize_public_target("https://t.me/c/123456/7") == "-100123456"
        assert self.worker._normalize_public_target("bad target!") is None

    def test_account_block_reason(self):
        assert self.worker._get_account_block_reason("Account joined too many channels") == "Account joined too many channels"
        assert self.worker._get_account_block_reason("FloodWait: 60s") is None

    def test_block_account_for_current_task_clears_flood_cooldown(self):
        self.worker._flood_wait_until[7] = 123.0

        reason = self.worker._block_account_for_current_task(7, "FloodWait: 60s")

        assert reason == "FloodWait: 60s"
        assert self.worker._blocked_accounts[7] == "FloodWait: 60s"
        assert 7 not in self.worker._flood_wait_until


@pytest.mark.asyncio
async def test_wait_after_account_uses_failure_backoff():
    worker = WarmingWorker(task_id=1)
    worker._wait_with_control = AsyncMock(return_value=True)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("workers.warming_worker.random.uniform", lambda a, b: 22.5)
        result = await worker._wait_after_account(
            account_index=0,
            total_accounts=2,
            success=False,
            cancel_event=asyncio.Event(),
            pause_event=asyncio.Event(),
        )

    assert result is True
    worker._wait_with_control.assert_awaited_once()
    assert worker._wait_with_control.await_args.args[0] == 22.5


@pytest.mark.asyncio
async def test_wait_after_account_skips_last_account_delay():
    worker = WarmingWorker(task_id=1)
    worker._wait_with_control = AsyncMock(return_value=True)

    result = await worker._wait_after_account(
        account_index=1,
        total_accounts=2,
        success=False,
        cancel_event=asyncio.Event(),
        pause_event=asyncio.Event(),
    )

    assert result is True
    worker._wait_with_control.assert_not_awaited()


@pytest.mark.asyncio
async def test_warm_single_target_invite_success():
    worker = WarmingWorker(task_id=1)
    worker._join_via_invite = AsyncMock(return_value=(True, None, None))
    worker._resolve_entity_after_invite_join = AsyncMock(return_value=None)

    success, message, error, entity, invite_link = await worker._warm_single_target(1, "https://t.me/+abc123")

    assert success is True
    assert message == "Joined via invite link"
    assert error is None
    assert entity is None
    assert invite_link == "https://t.me/+abc123"


@pytest.mark.asyncio
async def test_warm_single_target_already_subscribed():
    worker = WarmingWorker(task_id=1)
    entity = object()
    worker._resolve_entity = AsyncMock(return_value=entity)
    worker._check_subscription = AsyncMock(return_value=(True, None))

    success, message, error, resolved_entity, invite_link = await worker._warm_single_target(1, "@channel")

    assert success is True
    assert message == "Already subscribed"
    assert error is None
    assert resolved_entity is entity
    assert invite_link is None


@pytest.mark.asyncio
async def test_warm_single_target_private_channel_needs_invite():
    worker = WarmingWorker(task_id=1)
    entity = object()
    worker._resolve_entity = AsyncMock(return_value=entity)
    worker._check_subscription = AsyncMock(return_value=(False, "CHANNEL_PRIVATE"))

    success, message, error, resolved_entity, invite_link = await worker._warm_single_target(1, "@channel")

    assert success is False
    assert message == "Action was not executed"
    assert error == PRIVATE_CHANNEL_INVITE_REQUIRED
    assert resolved_entity is entity
    assert invite_link is None


@pytest.mark.asyncio
async def test_warm_single_target_rejects_invalid_target():
    worker = WarmingWorker(task_id=1)

    success, message, error, entity, invite_link = await worker._warm_single_target(1, "bad target!")

    assert success is False
    assert message == "Action was not executed"
    assert error == INVALID_WARMING_TARGET
    assert entity is None
    assert invite_link is None


@pytest.mark.asyncio
async def test_wait_with_control_cancelled():
    worker = WarmingWorker(task_id=1)
    cancel_event = asyncio.Event()
    pause_event = asyncio.Event()
    pause_event.set()
    cancel_event.set()

    result = await worker._wait_with_control(30, cancel_event=cancel_event, pause_event=pause_event)

    assert result is False


class _FakeQuery:
    def __init__(self, task):
        self._task = task

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self._task


class _FakeDB:
    def __init__(self, task):
        self.task = task
        self.commit_calls = 0
        self.closed = False

    def query(self, *_args, **_kwargs):
        return _FakeQuery(self.task)

    def add(self, *_args, **_kwargs):
        return None

    def commit(self):
        self.commit_calls += 1

    def close(self):
        self.closed = True


def _make_task(*, targets, accounts, status="pending"):
    return SimpleNamespace(
        id=1,
        status=status,
        accounts=accounts,
        config={"targets": targets},
        min_delay=18_000.0,
        max_delay=36_000.0,
        max_concurrent=1,
        completed_actions=0,
        failed_actions=0,
        total_actions=len(accounts) * len(targets),
        last_error=None,
        started_at=None,
        completed_at=None,
    )


@pytest.mark.asyncio
async def test_execute_fails_fast_when_no_accounts_connect(monkeypatch):
    accounts = [SimpleNamespace(id=1), SimpleNamespace(id=2)]
    task = _make_task(targets=["@target"], accounts=accounts)
    db = _FakeDB(task)
    worker = WarmingWorker(task_id=1)

    monkeypatch.setattr("workers.warming_worker.SessionLocal", lambda: db)
    worker._connect_accounts = AsyncMock(return_value=0)
    worker._disconnect_all = AsyncMock()
    worker._record_action = AsyncMock()

    cancel_event = asyncio.Event()
    pause_event = asyncio.Event()
    pause_event.set()

    await worker.execute(cancel_event=cancel_event, pause_event=pause_event)

    assert task.status == "failed"
    assert task.last_error == ALL_ACCOUNTS_FAILED_TO_CONNECT
    assert isinstance(task.completed_at, datetime)
    worker._record_action.assert_not_awaited()
    worker._disconnect_all.assert_awaited_once()
    assert db.closed is True


@pytest.mark.asyncio
async def test_execute_stops_before_inter_wave_delay_when_all_accounts_exhausted(monkeypatch):
    account = SimpleNamespace(id=1)
    task = _make_task(targets=["@one", "@two"], accounts=[account])
    db = _FakeDB(task)
    worker = WarmingWorker(task_id=1)

    async def _record_action(*_args, success, error=None, **_kwargs):
        if success:
            task.completed_actions += 1
        else:
            task.failed_actions += 1
            task.last_error = error

    monkeypatch.setattr("workers.warming_worker.SessionLocal", lambda: db)
    worker._connect_accounts = AsyncMock(side_effect=lambda accounts, *_args: worker._clients.update({accounts[0].id: object()}) or 1)
    worker._disconnect_all = AsyncMock()
    worker._track_channel_membership = lambda *_args, **_kwargs: None
    worker._warm_single_target = AsyncMock(return_value=(
        False,
        ACTION_SKIPPED_MESSAGE,
        "Account joined too many channels",
        None,
        None,
    ))
    worker._record_action = AsyncMock(side_effect=_record_action)
    worker._wait_with_control = AsyncMock(return_value=True)

    cancel_event = asyncio.Event()
    pause_event = asyncio.Event()
    pause_event.set()

    await worker.execute(cancel_event=cancel_event, pause_event=pause_event)

    assert task.status == "failed"
    assert task.last_error == "Account joined too many channels"
    assert task.failed_actions == 1
    assert isinstance(task.completed_at, datetime)
    worker._wait_with_control.assert_not_awaited()
    worker._disconnect_all.assert_awaited_once()
    assert ALL_ELIGIBLE_ACCOUNTS_EXHAUSTED != task.last_error


@pytest.mark.asyncio
async def test_execute_honors_cancel_after_last_action(monkeypatch):
    account = SimpleNamespace(id=1)
    task = _make_task(targets=["@one"], accounts=[account], status="running")
    db = _FakeDB(task)
    worker = WarmingWorker(task_id=1)
    cancel_event = asyncio.Event()
    pause_event = asyncio.Event()
    pause_event.set()

    async def _record_action(*_args, success, error=None, **_kwargs):
        if success:
            task.completed_actions += 1
        else:
            task.failed_actions += 1
            task.last_error = error
        cancel_event.set()

    monkeypatch.setattr("workers.warming_worker.SessionLocal", lambda: db)
    worker._connect_accounts = AsyncMock(side_effect=lambda accounts, *_args: worker._clients.update({accounts[0].id: object()}) or 1)
    worker._disconnect_all = AsyncMock()
    worker._track_channel_membership = lambda *_args, **_kwargs: None
    worker._warm_single_target = AsyncMock(return_value=(True, "Joined channel", None, None, None))
    worker._record_action = AsyncMock(side_effect=_record_action)

    await worker.execute(cancel_event=cancel_event, pause_event=pause_event)

    assert task.status == "cancelled"
    assert isinstance(task.completed_at, datetime)
    worker._disconnect_all.assert_awaited_once()
