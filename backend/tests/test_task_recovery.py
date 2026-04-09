"""Tests for stale task recovery after backend restart."""

from datetime import datetime, timezone
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).parent.parent))

from api.tasks import pause_task
from utils.task_recovery import (
    ALL_WARMING_ACTIONS_FAILED_ERROR,
    INTERRUPTED_BY_APP_RESTART_ERROR,
    TASK_RESTART_REQUIRED_ERROR,
    reconcile_interrupted_task,
    reconcile_stale_active_tasks,
)
from workers.task_queue import task_queue


class StubTask:
    def __init__(
        self,
        *,
        task_type: str = "likes",
        status: str = "running",
        total_actions: int = 0,
        completed_actions: int = 0,
        failed_actions: int = 0,
        started_at=None,
        completed_at=None,
        last_error=None,
    ):
        self.task_type = task_type
        self.status = status
        self.total_actions = total_actions
        self.completed_actions = completed_actions
        self.failed_actions = failed_actions
        self.started_at = started_at
        self.completed_at = completed_at
        self.last_error = last_error


def test_reconcile_interrupted_task_resets_unstarted_task_to_pending():
    task = StubTask(
        status="paused",
        total_actions=5,
        started_at=datetime(2026, 4, 8, 9, 0, tzinfo=timezone.utc),
        completed_at=datetime(2026, 4, 8, 9, 30, tzinfo=timezone.utc),
        last_error="Old error",
    )

    status = reconcile_interrupted_task(
        task,
        now=datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc),
    )

    assert status == "pending"
    assert task.started_at is None
    assert task.completed_at is None
    assert task.last_error is None


def test_reconcile_interrupted_task_cancels_partially_processed_task():
    now = datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc)
    task = StubTask(
        status="running",
        total_actions=5,
        completed_actions=2,
        failed_actions=1,
        started_at=datetime(2026, 4, 8, 9, 0, tzinfo=timezone.utc),
    )

    status = reconcile_interrupted_task(task, now=now)

    assert status == "cancelled"
    assert task.completed_at == now
    assert task.last_error == INTERRUPTED_BY_APP_RESTART_ERROR


def test_reconcile_interrupted_task_marks_finished_task_completed():
    now = datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc)
    task = StubTask(
        status="running",
        total_actions=3,
        completed_actions=2,
        failed_actions=1,
        started_at=datetime(2026, 4, 8, 9, 0, tzinfo=timezone.utc),
    )

    status = reconcile_interrupted_task(task, now=now)

    assert status == "completed"
    assert task.completed_at == now


def test_reconcile_interrupted_task_keeps_all_failed_warming_task_failed():
    now = datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc)
    task = StubTask(
        task_type="warming",
        status="running",
        total_actions=3,
        completed_actions=0,
        failed_actions=3,
        started_at=datetime(2026, 4, 8, 9, 0, tzinfo=timezone.utc),
    )

    status = reconcile_interrupted_task(task, now=now)

    assert status == "failed"
    assert task.completed_at == now
    assert task.last_error == ALL_WARMING_ACTIONS_FAILED_ERROR


class _QueryStub:
    def __init__(self, tasks):
        self.tasks = tasks

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self.tasks[0] if self.tasks else None

    def all(self):
        return self.tasks


class _DbStub:
    def __init__(self, tasks):
        self.tasks = tasks
        self.commits = 0

    def query(self, _model):
        return _QueryStub(self.tasks)

    def commit(self):
        self.commits += 1

    def refresh(self, _task):
        return None


def test_reconcile_stale_active_tasks_handles_running_and_paused():
    pending_started = datetime(2026, 4, 8, 8, 0, tzinfo=timezone.utc)
    tasks = [
        StubTask(status="running", total_actions=5, completed_actions=0, started_at=pending_started),
        StubTask(status="paused", total_actions=5, completed_actions=1),
    ]
    db = _DbStub(tasks)

    recovered = reconcile_stale_active_tasks(
        db,
        now=datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc),
    )

    assert recovered == 2
    assert db.commits == 1
    assert tasks[0].status == "pending"
    assert tasks[0].started_at is None
    assert tasks[1].status == "cancelled"
    assert tasks[1].last_error == INTERRUPTED_BY_APP_RESTART_ERROR


@pytest.mark.asyncio
async def test_pause_task_reconciles_partial_warming_task_when_queue_entry_is_missing(monkeypatch):
    task = StubTask(
        task_type="warming",
        status="running",
        total_actions=4,
        completed_actions=1,
        failed_actions=1,
        started_at=datetime(2026, 4, 8, 9, 0, tzinfo=timezone.utc),
    )
    db = _DbStub([task])

    async def _pause_missing(_task_id: int) -> bool:
        return False

    monkeypatch.setattr(task_queue, "pause", _pause_missing)

    with pytest.raises(HTTPException) as exc_info:
        await pause_task(1, db)

    exc = exc_info.value
    assert exc.status_code == 409
    assert exc.detail == TASK_RESTART_REQUIRED_ERROR
    assert task.status == "cancelled"
    assert task.last_error == INTERRUPTED_BY_APP_RESTART_ERROR
