"""
Tests for WarmingWorker.

Focus on the worker's local decision-making; Telegram and database access stay mocked.
"""

import asyncio
from unittest.mock import AsyncMock

import pytest

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from workers.warming_worker import WarmingWorker, PRIVATE_CHANNEL_INVITE_REQUIRED


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

    def test_account_block_reason(self):
        assert self.worker._get_account_block_reason("Account joined too many channels") == "Account joined too many channels"
        assert self.worker._get_account_block_reason("FloodWait: 60s") is None


@pytest.mark.asyncio
async def test_warm_single_target_invite_success():
    worker = WarmingWorker(task_id=1)
    worker._join_via_invite = AsyncMock(return_value=(True, None, None))

    success, message, error = await worker._warm_single_target(1, "https://t.me/+abc123")

    assert success is True
    assert message == "Joined via invite link"
    assert error is None


@pytest.mark.asyncio
async def test_warm_single_target_already_subscribed():
    worker = WarmingWorker(task_id=1)
    worker._resolve_entity = AsyncMock(return_value=object())
    worker._check_subscription = AsyncMock(return_value=(True, None))

    success, message, error = await worker._warm_single_target(1, "@channel")

    assert success is True
    assert message == "Already subscribed"
    assert error is None


@pytest.mark.asyncio
async def test_warm_single_target_private_channel_needs_invite():
    worker = WarmingWorker(task_id=1)
    worker._resolve_entity = AsyncMock(return_value=object())
    worker._check_subscription = AsyncMock(return_value=(False, "CHANNEL_PRIVATE"))

    success, message, error = await worker._warm_single_target(1, "@channel")

    assert success is False
    assert message == "Action was not executed"
    assert error == PRIVATE_CHANNEL_INVITE_REQUIRED


@pytest.mark.asyncio
async def test_wait_with_control_cancelled():
    worker = WarmingWorker(task_id=1)
    cancel_event = asyncio.Event()
    pause_event = asyncio.Event()
    pause_event.set()
    cancel_event.set()

    result = await worker._wait_with_control(30, cancel_event=cancel_event, pause_event=pause_event)

    assert result is False
