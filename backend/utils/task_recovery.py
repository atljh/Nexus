"""Helpers for reconciling task state after backend or queue interruptions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from database.models import Task

INTERRUPTED_BY_APP_RESTART_ERROR = "Interrupted by app restart"
TASK_RESTART_REQUIRED_ERROR = "Task was interrupted and must be restarted"
ALL_WARMING_ACTIONS_FAILED_ERROR = "All warming actions failed"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def reconcile_interrupted_task(task: Task, *, now: Optional[datetime] = None) -> str:
    """
    Normalize a stale running/paused task after the in-memory queue was lost.

    Fresh tasks with no processed actions can safely return to pending.
    Partially processed tasks cannot be resumed deterministically, so they are
    marked cancelled and must be restarted explicitly.
    """
    safe_now = now or _utcnow()
    total_actions = max(0, int(task.total_actions or 0))
    completed_actions = max(0, int(task.completed_actions or 0))
    failed_actions = max(0, int(task.failed_actions or 0))
    processed_actions = max(0, int(completed_actions + failed_actions))

    if total_actions > 0 and processed_actions >= total_actions:
        if getattr(task, "task_type", None) == "warming" and completed_actions == 0 and failed_actions > 0:
            task.status = "failed"
            if not task.last_error:
                task.last_error = ALL_WARMING_ACTIONS_FAILED_ERROR
        else:
            task.status = "completed"
        if task.completed_at is None:
            task.completed_at = safe_now
        return task.status

    if processed_actions > 0:
        task.status = "cancelled"
        task.completed_at = safe_now
        task.last_error = INTERRUPTED_BY_APP_RESTART_ERROR
        return task.status

    task.status = "pending"
    task.started_at = None
    task.completed_at = None
    task.last_error = None
    return task.status


def reconcile_stale_active_tasks(db: Session, *, now: Optional[datetime] = None) -> int:
    """Reconcile all running/paused tasks left behind after a backend restart."""
    stale_tasks = db.query(Task).filter(Task.status.in_(["running", "paused"])).all()
    if not stale_tasks:
        return 0

    safe_now = now or _utcnow()
    for task in stale_tasks:
        reconcile_interrupted_task(task, now=safe_now)

    db.commit()
    return len(stale_tasks)
