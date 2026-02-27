"""Tasks API - Create and manage automation tasks."""
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from database.database import get_db
from database.models import (
    Task, TaskLog, Account, CommentTemplate, TargetChannel,
    AccountBlacklist, CommentHistory, AIPromptTemplate,
)

router = APIRouter()


# ============ Pydantic Schemas ============

class TaskConfig(BaseModel):
    """Configuration for a task."""
    channel: str = Field(..., description="Channel username or link")
    post_id: Optional[int] = Field(None, description="Specific post ID")
    reactions: List[str] = Field(["👍"], description="List of reaction emojis")
    emoji_mode: str = Field("single", description="single | random | all")


class CreateLikesTaskRequest(BaseModel):
    """Request to create a likes task."""
    config: TaskConfig
    account_ids: List[int] = Field(..., description="Account IDs to use")
    total_actions: int = Field(10, ge=1, le=10000, description="Number of reactions to send")
    min_delay: float = Field(30.0, ge=1, le=3600, description="Min delay between actions (seconds)")
    max_delay: float = Field(120.0, ge=1, le=3600, description="Max delay between actions (seconds)")
    max_concurrent: int = Field(1, ge=1, le=10, description="Max concurrent executions")


class CommentsTaskConfig(BaseModel):
    """Configuration for comments task."""
    channels: List[str] = Field(..., description="List of target channels")
    templates: List[str] = Field(default=[], description="Comment templates with spintax")
    rotation_mode: str = Field("random", description="random or round_robin")
    comments_per_account: int = Field(10, ge=1, le=100, description="Max comments per account")
    mode: str = Field("single", description="single or monitoring")
    # Comment filtering
    comment_mode: str = Field("all", description="all, random, or keywords")
    comment_probability: float = Field(0.5, ge=0, le=1, description="Probability for random mode")
    keywords: List[str] = Field(default=[], description="Keywords for keyword mode")
    # AI settings
    ai_enabled: bool = Field(False, description="Enable AI comment generation")
    ai_api_key: Optional[str] = Field(None, description="OpenAI API key")
    ai_model: str = Field("gpt-4o-mini", description="AI model name")
    ai_base_url: str = Field("https://api.openai.com/v1", description="API base URL")
    ai_prompt_id: Optional[int] = Field(None, description="AI prompt template ID")
    ai_temperature: float = Field(0.7, ge=0, le=2, description="AI temperature")


class CreateCommentsTaskRequest(BaseModel):
    """Request to create a comments task."""
    config: CommentsTaskConfig
    account_ids: List[int] = Field(..., description="Account IDs to use")
    total_actions: int = Field(10, ge=1, le=10000, description="Number of comments to send")
    min_delay: float = Field(30.0, ge=1, le=3600, description="Min delay between actions")
    max_delay: float = Field(120.0, ge=1, le=3600, description="Max delay between actions")


class CommentTemplateRequest(BaseModel):
    """Request to create/update a comment template."""
    name: str = Field(..., min_length=1, max_length=100)
    content: str = Field(..., min_length=1)
    is_default: bool = Field(False)


class CommentTemplateResponse(BaseModel):
    """Comment template response."""
    id: int
    name: str
    content: str
    is_default: bool
    created_at: str


class TargetChannelResponse(BaseModel):
    """Target channel response."""
    id: int
    task_id: int
    channel_username: str
    channel_id: Optional[int]
    channel_title: Optional[str]
    status: str
    can_comment: bool
    error_message: Optional[str]
    comments_sent: int
    created_at: str


class UpdateTaskRequest(BaseModel):
    """Request to update a task."""
    status: Optional[str] = None
    min_delay: Optional[float] = None
    max_delay: Optional[float] = None


class TaskResponse(BaseModel):
    """Task response."""
    id: int
    task_type: str
    status: str
    config: dict
    total_actions: int
    completed_actions: int
    failed_actions: int
    min_delay: float
    max_delay: float
    max_concurrent: int
    last_error: Optional[str]
    started_at: Optional[str]
    completed_at: Optional[str]
    created_at: str
    accounts_count: int
    progress: float


class TaskLogResponse(BaseModel):
    """Task log response."""
    id: int
    task_id: int
    account_id: Optional[int]
    action_type: str
    target: Optional[str]
    success: bool
    message: Optional[str]
    error: Optional[str]
    extra_data: Optional[dict]
    created_at: str


class AIPromptRequest(BaseModel):
    """Request to create/update an AI prompt template."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    prompt_template: str = Field(..., min_length=1)
    ai_model: str = Field("gpt-4o-mini")
    temperature: float = Field(0.7, ge=0, le=2)
    max_length: int = Field(200, ge=10, le=2000)
    is_default: bool = Field(False)


# ============ Routes ============
# IMPORTANT: Static prefix routes MUST be registered before dynamic /{task_id}
# routes, otherwise FastAPI will try to parse "templates" etc. as task_id int.

# ── Task list & creation ──

@router.get("", response_model=List[TaskResponse])
async def get_tasks(
    task_type: Optional[str] = Query(None, description="Filter by task type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """Get all tasks with optional filters."""
    query = db.query(Task).options(joinedload(Task.accounts))

    if task_type:
        query = query.filter(Task.task_type == task_type)
    if status:
        query = query.filter(Task.status == status)

    tasks = query.order_by(Task.created_at.desc()).offset(offset).limit(limit).all()
    return [task.to_dict() for task in tasks]


@router.get("/active", response_model=List[TaskResponse])
async def get_active_tasks(db: Session = Depends(get_db)):
    """Get all active (running or pending) tasks."""
    tasks = db.query(Task).options(joinedload(Task.accounts)).filter(
        Task.status.in_(["pending", "running"])
    ).order_by(Task.created_at.desc()).all()
    return [task.to_dict() for task in tasks]


# ── Statistics ──

@router.get("/stats/summary")
async def get_task_stats(db: Session = Depends(get_db)):
    """Get task statistics summary."""
    total = db.query(Task).count()
    running = db.query(Task).filter(Task.status == "running").count()
    pending = db.query(Task).filter(Task.status == "pending").count()
    completed = db.query(Task).filter(Task.status == "completed").count()
    failed = db.query(Task).filter(Task.status == "failed").count()

    return {
        "total": total,
        "running": running,
        "pending": pending,
        "completed": completed,
        "failed": failed
    }


# ── Comment Templates ──

@router.get("/templates", response_model=List[CommentTemplateResponse])
async def get_templates(db: Session = Depends(get_db)):
    """Get all comment templates."""
    templates = db.query(CommentTemplate).order_by(CommentTemplate.created_at.desc()).all()
    return [t.to_dict() for t in templates]


@router.post("/templates", response_model=CommentTemplateResponse)
async def create_template(request: CommentTemplateRequest, db: Session = Depends(get_db)):
    """Create a new comment template."""
    from workers.spintax import validate_spintax

    # Validate spintax
    is_valid, error = validate_spintax(request.content)
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Invalid spintax: {error}")

    template = CommentTemplate(
        name=request.name,
        content=request.content,
        is_default=request.is_default
    )

    db.add(template)
    db.commit()
    db.refresh(template)

    return template.to_dict()


@router.put("/templates/{template_id}", response_model=CommentTemplateResponse)
async def update_template(
    template_id: int,
    request: CommentTemplateRequest,
    db: Session = Depends(get_db)
):
    """Update a comment template."""
    from workers.spintax import validate_spintax

    template = db.query(CommentTemplate).filter(CommentTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Validate spintax
    is_valid, error = validate_spintax(request.content)
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Invalid spintax: {error}")

    template.name = request.name
    template.content = request.content
    template.is_default = request.is_default

    db.commit()
    db.refresh(template)

    return template.to_dict()


@router.delete("/templates/{template_id}")
async def delete_template(template_id: int, db: Session = Depends(get_db)):
    """Delete a comment template."""
    template = db.query(CommentTemplate).filter(CommentTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    db.delete(template)
    db.commit()

    return {"message": "Template deleted"}


@router.post("/templates/preview")
async def preview_template(content: str, count: int = 5, db: Session = Depends(get_db)):
    """Preview spintax template with sample outputs."""
    from workers.spintax import validate_spintax, generate_samples, count_variants

    is_valid, error = validate_spintax(content)
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Invalid spintax: {error}")

    samples = generate_samples(content, count)
    total_variants = count_variants(content)

    return {
        "samples": samples,
        "total_variants": total_variants
    }


# ── AI Prompt Templates ──

@router.get("/ai-prompts", response_model=list)
async def get_ai_prompts(db: Session = Depends(get_db)):
    """Get all AI prompt templates."""
    prompts = db.query(AIPromptTemplate).order_by(AIPromptTemplate.created_at.desc()).all()
    return [p.to_dict() for p in prompts]


@router.post("/ai-prompts")
async def create_ai_prompt(request: AIPromptRequest, db: Session = Depends(get_db)):
    """Create a new AI prompt template."""
    # Validate template has required placeholders
    if "{post_text}" not in request.prompt_template:
        raise HTTPException(
            status_code=400,
            detail="Prompt template must contain {post_text} placeholder"
        )

    prompt = AIPromptTemplate(
        name=request.name,
        description=request.description,
        prompt_template=request.prompt_template,
        ai_model=request.ai_model,
        temperature=request.temperature,
        max_length=request.max_length,
        is_default=request.is_default,
    )
    db.add(prompt)
    db.commit()
    db.refresh(prompt)
    return prompt.to_dict()


@router.put("/ai-prompts/{prompt_id}")
async def update_ai_prompt(
    prompt_id: int,
    request: AIPromptRequest,
    db: Session = Depends(get_db)
):
    """Update an AI prompt template."""
    prompt = db.query(AIPromptTemplate).filter(AIPromptTemplate.id == prompt_id).first()
    if not prompt:
        raise HTTPException(status_code=404, detail="AI prompt not found")

    if "{post_text}" not in request.prompt_template:
        raise HTTPException(
            status_code=400,
            detail="Prompt template must contain {post_text} placeholder"
        )

    prompt.name = request.name
    prompt.description = request.description
    prompt.prompt_template = request.prompt_template
    prompt.ai_model = request.ai_model
    prompt.temperature = request.temperature
    prompt.max_length = request.max_length
    prompt.is_default = request.is_default

    db.commit()
    db.refresh(prompt)
    return prompt.to_dict()


@router.delete("/ai-prompts/{prompt_id}")
async def delete_ai_prompt(prompt_id: int, db: Session = Depends(get_db)):
    """Delete an AI prompt template."""
    prompt = db.query(AIPromptTemplate).filter(AIPromptTemplate.id == prompt_id).first()
    if not prompt:
        raise HTTPException(status_code=404, detail="AI prompt not found")

    db.delete(prompt)
    db.commit()
    return {"message": "AI prompt deleted"}


# ── Comment History (static prefix) ──

@router.get("/comment-history/by-account/{account_id}")
async def get_account_comment_history(
    account_id: int,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """Get comment history for a specific account."""
    items = db.query(CommentHistory).filter(
        CommentHistory.account_id == account_id
    ).order_by(CommentHistory.created_at.desc()).offset(offset).limit(limit).all()
    return [h.to_dict() for h in items]


# ── Blacklist (static prefix) ──

@router.get("/blacklist/{account_id}")
async def get_account_blacklist(
    account_id: int,
    db: Session = Depends(get_db)
):
    """Get blacklist entries for an account."""
    items = db.query(AccountBlacklist).filter(
        AccountBlacklist.account_id == account_id
    ).order_by(AccountBlacklist.created_at.desc()).all()
    return [b.to_dict() for b in items]


@router.delete("/blacklist/{blacklist_id}")
async def delete_blacklist_entry(
    blacklist_id: int,
    db: Session = Depends(get_db)
):
    """Remove an entry from the blacklist."""
    entry = db.query(AccountBlacklist).filter(AccountBlacklist.id == blacklist_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Blacklist entry not found")

    db.delete(entry)
    db.commit()
    return {"message": "Blacklist entry removed"}


# ── Task creation (static prefix) ──

@router.post("/likes", response_model=TaskResponse)
async def create_likes_task(request: CreateLikesTaskRequest, db: Session = Depends(get_db)):
    """Create a new likes (reactions) task."""
    # Validate accounts exist and are valid
    accounts = db.query(Account).filter(
        Account.id.in_(request.account_ids),
        Account.status == "valid"
    ).all()

    if not accounts:
        raise HTTPException(status_code=400, detail="No valid accounts found")

    if len(accounts) < len(request.account_ids):
        invalid_count = len(request.account_ids) - len(accounts)
        # Continue with valid accounts, just warn
        pass

    # Normalize channel
    channel = request.config.channel.strip()
    if channel.startswith("https://t.me/"):
        channel = "@" + channel.replace("https://t.me/", "").split("/")[0]
    elif not channel.startswith("@"):
        channel = "@" + channel

    # Validate emoji_mode
    if request.config.emoji_mode not in ("single", "random", "all"):
        raise HTTPException(status_code=400, detail="emoji_mode must be 'single', 'random', or 'all'")

    # Create task
    task = Task(
        task_type="likes",
        status="pending",
        config={
            "channel": channel,
            "post_id": request.config.post_id,
            "reactions": request.config.reactions,
            "emoji_mode": request.config.emoji_mode,
        },
        total_actions=request.total_actions,
        min_delay=request.min_delay,
        max_delay=request.max_delay,
        max_concurrent=request.max_concurrent
    )
    task.accounts = accounts

    db.add(task)
    db.commit()
    db.refresh(task)

    return task.to_dict()


@router.post("/comments", response_model=TaskResponse)
async def create_comments_task(request: CreateCommentsTaskRequest, db: Session = Depends(get_db)):
    """Create a new comments task."""
    # Validate accounts
    accounts = db.query(Account).filter(
        Account.id.in_(request.account_ids),
        Account.status == "valid"
    ).all()

    if not accounts:
        raise HTTPException(status_code=400, detail="No valid accounts found")

    # Normalize channels
    channels = []
    for ch in request.config.channels:
        ch = ch.strip()
        if ch.startswith("https://t.me/"):
            ch = "@" + ch.replace("https://t.me/", "").split("/")[0]
        elif not ch.startswith("@"):
            ch = "@" + ch
        channels.append(ch)

    # Build config with AI settings
    task_config = {
        "channels": channels,
        "templates": request.config.templates,
        "rotation_mode": request.config.rotation_mode,
        "comments_per_account": request.config.comments_per_account,
        "mode": request.config.mode,
        "comment_mode": request.config.comment_mode,
        "comment_probability": request.config.comment_probability,
        "keywords": request.config.keywords,
        "ai_enabled": request.config.ai_enabled,
        "ai_model": request.config.ai_model,
        "ai_base_url": request.config.ai_base_url,
        "ai_temperature": request.config.ai_temperature,
    }
    if request.config.ai_api_key:
        task_config["ai_api_key"] = request.config.ai_api_key
    if request.config.ai_prompt_id:
        task_config["ai_prompt_id"] = request.config.ai_prompt_id

    # Create task
    task = Task(
        task_type="comments",
        status="pending",
        config=task_config,
        total_actions=request.total_actions,
        min_delay=request.min_delay,
        max_delay=request.max_delay,
        max_concurrent=1
    )
    task.accounts = accounts

    db.add(task)
    db.commit()
    db.refresh(task)

    return task.to_dict()


# ============ Dynamic /{task_id} routes ============
# These MUST come after all static prefix routes above.

@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: int, db: Session = Depends(get_db)):
    """Get a specific task by ID."""
    task = db.query(Task).options(joinedload(Task.accounts)).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task.to_dict()


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(task_id: int, request: UpdateTaskRequest, db: Session = Depends(get_db)):
    """Update a task."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if request.status:
        if request.status not in ["pending", "running", "paused", "completed", "failed", "cancelled"]:
            raise HTTPException(status_code=400, detail="Invalid status")
        task.status = request.status
        if request.status == "running" and not task.started_at:
            task.started_at = datetime.now(timezone.utc)
        elif request.status in ["completed", "failed", "cancelled"]:
            task.completed_at = datetime.now(timezone.utc)

    if request.min_delay is not None:
        task.min_delay = request.min_delay
    if request.max_delay is not None:
        task.max_delay = request.max_delay

    db.commit()
    db.refresh(task)
    return task.to_dict()


@router.post("/{task_id}/start", response_model=TaskResponse)
async def start_task(task_id: int, db: Session = Depends(get_db)):
    """Start a pending task."""
    from workers.likes_worker import start_likes_task
    from workers.comments_worker import start_comments_task
    from workers.task_queue import task_queue

    task = db.query(Task).options(joinedload(Task.accounts)).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status not in ["pending", "paused"]:
        raise HTTPException(status_code=400, detail=f"Cannot start task with status: {task.status}")

    # Check if already running in queue
    if task_queue.is_running(task_id):
        # Resume if paused
        await task_queue.resume(task_id)
        task.status = "running"
        db.commit()
        db.refresh(task)
        return task.to_dict()

    # Start the worker based on task type
    if task.task_type == "likes":
        await start_likes_task(task_id)
    elif task.task_type == "comments":
        await start_comments_task(task_id)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown task type: {task.task_type}")

    db.refresh(task)
    return task.to_dict()


@router.post("/{task_id}/pause", response_model=TaskResponse)
async def pause_task(task_id: int, db: Session = Depends(get_db)):
    """Pause a running task."""
    from workers.task_queue import task_queue

    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != "running":
        raise HTTPException(status_code=400, detail="Can only pause running tasks")

    # Pause in queue
    await task_queue.pause(task_id)

    task.status = "paused"
    db.commit()
    db.refresh(task)
    return task.to_dict()


@router.post("/{task_id}/cancel", response_model=TaskResponse)
async def cancel_task(task_id: int, db: Session = Depends(get_db)):
    """Cancel a task."""
    from workers.task_queue import task_queue

    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status in ["completed", "failed", "cancelled"]:
        raise HTTPException(status_code=400, detail="Task already finished")

    # Cancel in queue
    await task_queue.cancel(task_id)

    task.status = "cancelled"
    task.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(task)
    return task.to_dict()


@router.delete("/{task_id}")
async def delete_task(task_id: int, db: Session = Depends(get_db)):
    """Delete a task and its logs."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status == "running":
        raise HTTPException(status_code=400, detail="Cannot delete running task. Cancel it first.")

    db.delete(task)
    db.commit()
    return {"message": "Task deleted"}


# ── Task Logs ──

@router.get("/{task_id}/logs", response_model=List[TaskLogResponse])
async def get_task_logs(
    task_id: int,
    success: Optional[bool] = Query(None, description="Filter by success"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """Get logs for a specific task."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    query = db.query(TaskLog).filter(TaskLog.task_id == task_id)

    if success is not None:
        query = query.filter(TaskLog.success == success)

    logs = query.order_by(TaskLog.created_at.desc()).offset(offset).limit(limit).all()
    return [log.to_dict() for log in logs]


@router.post("/{task_id}/logs")
async def add_task_log(
    task_id: int,
    action_type: str,
    success: bool,
    account_id: Optional[int] = None,
    target: Optional[str] = None,
    message: Optional[str] = None,
    error: Optional[str] = None,
    extra_data: Optional[dict] = None,
    db: Session = Depends(get_db)
):
    """Add a log entry for a task (used by worker)."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    log = TaskLog(
        task_id=task_id,
        account_id=account_id,
        action_type=action_type,
        target=target,
        success=success,
        message=message,
        error=error,
        extra_data=extra_data
    )

    # Update task counters
    if success:
        task.completed_actions += 1
    else:
        task.failed_actions += 1
        if error:
            task.last_error = error

    # Check if task is complete
    if task.completed_actions + task.failed_actions >= task.total_actions:
        task.status = "completed"
        task.completed_at = datetime.now(timezone.utc)

    db.add(log)
    db.commit()
    db.refresh(log)

    return log.to_dict()


# ── Target Channels ──

@router.get("/{task_id}/channels", response_model=List[TargetChannelResponse])
async def get_task_channels(task_id: int, db: Session = Depends(get_db)):
    """Get target channels for a comments task."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    channels = db.query(TargetChannel).filter(TargetChannel.task_id == task_id).all()
    return [ch.to_dict() for ch in channels]


# ── Comment History (per task) ──

@router.get("/{task_id}/comment-history")
async def get_task_comment_history(
    task_id: int,
    success: Optional[bool] = Query(None),
    ai_only: bool = Query(False),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """Get comment history for a specific task."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    query = db.query(CommentHistory).filter(CommentHistory.task_id == task_id)
    if success is not None:
        query = query.filter(CommentHistory.success == success)
    if ai_only:
        query = query.filter(CommentHistory.ai_generated == True)

    items = query.order_by(CommentHistory.created_at.desc()).offset(offset).limit(limit).all()
    return [h.to_dict() for h in items]
