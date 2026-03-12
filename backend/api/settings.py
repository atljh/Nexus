"""Settings API - Application settings and data management."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database.database import get_db
from database.models import (
    Account, Proxy, AccountGroup, AccountTag, Task, TaskLog,
    CommentTemplate, TargetChannel, AccountBlacklist, CommentHistory,
    AIPromptTemplate, account_tags,
)

router = APIRouter()


@router.delete("/clear-all")
def clear_all_data(db: Session = Depends(get_db)):
    """Delete all user data: accounts, proxies, tasks, templates, etc."""
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
