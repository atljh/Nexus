"""Settings API - Application settings and data management."""
import asyncio
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database.database import get_db
from database.models import (
    Account, Proxy, AccountGroup, AccountTag, Task, TaskLog,
    CommentTemplate, TargetChannel, AccountBlacklist, CommentHistory,
    AIPromptTemplate, account_tags,
)

router = APIRouter()


async def _stop_active_tasks(db: Session) -> None:
    """Cancel queued tasks and wait until workers stop touching the database."""
    from workers.task_queue import task_queue

    queued_ids = set(task_queue.get_running_tasks())
    if queued_ids:
        await asyncio.gather(
            *(task_queue.cancel(task_id) for task_id in queued_ids),
            return_exceptions=True,
        )

        deadline = time.monotonic() + 5.0
        while any(task_queue.is_running(task_id) for task_id in queued_ids):
            if time.monotonic() >= deadline:
                raise HTTPException(
                    status_code=409,
                    detail="Cannot clear data while background tasks are still stopping",
                )
            await asyncio.sleep(0.1)

    active_tasks = db.query(Task).filter(Task.status.in_(["running", "paused"])).all()
    if active_tasks:
        now = datetime.now(timezone.utc)
        for task in active_tasks:
            task.status = "cancelled"
            task.completed_at = now
            task.last_error = "Cancelled by data reset"
        db.commit()


@router.delete("/clear-all")
async def clear_all_data(db: Session = Depends(get_db)):
    """Delete all user data: accounts, proxies, tasks, templates, etc."""
    await _stop_active_tasks(db)

    # Order matters due to foreign key constraints
    db.execute(account_tags.delete())
    db.query(TaskLog).delete()
    db.query(TargetChannel).delete()
    db.query(AccountBlacklist).delete()
    db.query(CommentHistory).delete()
    db.query(Task).delete()
    db.query(Account).delete()
    db.query(Proxy).delete()
    db.query(AccountGroup).delete()
    db.query(AccountTag).delete()
    db.query(CommentTemplate).delete()
    db.query(AIPromptTemplate).delete()
    db.commit()
    return {"status": "ok"}
