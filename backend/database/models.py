from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, Table, Column, Text, JSON, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.database import Base


# Many-to-many relationship table for accounts and tags
account_tags = Table(
    "account_tags",
    Base.metadata,
    Column("account_id", Integer, ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)
)


class AccountGroup(Base):
    __tablename__ = "account_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    color: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    accounts: Mapped[List["Account"]] = relationship(back_populates="group")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "color": self.color,
            "accounts_count": len(self.accounts) if self.accounts else 0,
            "created_at": self.created_at.isoformat()
        }


class AccountTag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    color: Mapped[str] = mapped_column(String(20), default="#a855f7")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    accounts: Mapped[List["Account"]] = relationship(
        secondary=account_tags,
        back_populates="tags"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "color": self.color
        }


class Proxy(Base):
    __tablename__ = "proxies"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(10), default="socks5")  # socks5, http, https
    host: Mapped[str] = mapped_column(String(255))
    port: Mapped[int] = mapped_column(Integer)
    username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    password: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="unchecked")
    # Status: unchecked, working, slow, very_slow, not_working, timeout

    # Check results
    ping_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    geo: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)  # Country code: RU, US, UA
    external_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)  # IPv4/IPv6

    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    accounts: Mapped[List["Account"]] = relationship(back_populates="proxy")

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.type,
            "host": self.host,
            "port": self.port,
            "username": self.username,
            "status": self.status,
            "ping_ms": self.ping_ms,
            "geo": self.geo,
            "external_ip": self.external_ip,
            "accounts_count": len(self.accounts) if self.accounts else 0,
            "last_checked_at": self.last_checked_at.isoformat() if self.last_checked_at else None,
            "created_at": self.created_at.isoformat()
        }

    def get_connection_string(self):
        auth = f"{self.username}:{self.password}@" if self.username else ""
        return f"{self.type}://{auth}{self.host}:{self.port}"


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, unique=True)
    username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Status
    status: Mapped[str] = mapped_column(String(30), default="unchecked")
    # unchecked, checking, valid, invalid, banned, muted, spamblock, session_expired, deactivated, needs_reauth

    # Session storage
    session_string: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Extended metadata from JSON import
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    spamblock: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    register_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    geo: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)  # Country code: RU, US, UA

    # 2FA (Two-Factor Authentication)
    has_2fa: Mapped[bool] = mapped_column(Boolean, default=False)
    password_hint: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    two_fa_password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Stored for auto-login
    two_fa_set_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Proxy
    proxy_id: Mapped[Optional[int]] = mapped_column(ForeignKey("proxies.id", ondelete="SET NULL"), nullable=True)
    proxy: Mapped[Optional["Proxy"]] = relationship(back_populates="accounts")

    # Group
    group_id: Mapped[Optional[int]] = mapped_column(ForeignKey("account_groups.id", ondelete="SET NULL"), nullable=True)
    group: Mapped[Optional["AccountGroup"]] = relationship(back_populates="accounts")

    # Tags
    tags: Mapped[List["AccountTag"]] = relationship(
        secondary=account_tags,
        back_populates="accounts"
    )

    # Timestamps
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "telegram_id": self.telegram_id,
            "username": self.username,
            "phone": self.phone,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "status": self.status,
            "spamblock": self.spamblock,
            "geo": self.geo,
            "register_time": self.register_time.isoformat() if self.register_time else None,
            "has_2fa": self.has_2fa,
            "password_hint": self.password_hint,
            "two_fa_set_at": self.two_fa_set_at.isoformat() if self.two_fa_set_at else None,
            "metadata": self.extra_data,
            "proxy": self.proxy.to_dict() if self.proxy else None,
            "proxy_id": self.proxy_id,
            "group": self.group.to_dict() if self.group else None,
            "group_id": self.group_id,
            "tags": [tag.to_dict() for tag in self.tags] if self.tags else [],
            "last_checked_at": self.last_checked_at.isoformat() if self.last_checked_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "created_at": self.created_at.isoformat()
        }


# Many-to-many relationship table for tasks and accounts
task_accounts = Table(
    "task_accounts",
    Base.metadata,
    Column("task_id", Integer, ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
    Column("account_id", Integer, ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True)
)


class Task(Base):
    """Task for auto-likes, auto-comments, etc."""
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Task type: likes, comments, etc.
    task_type: Mapped[str] = mapped_column(String(50))  # likes, comments

    # Status: pending, running, paused, completed, failed, cancelled
    status: Mapped[str] = mapped_column(String(20), default="pending")

    # Target configuration (JSON)
    # For likes: { "channel": "@channel", "post_id": 123, "reaction": "👍", "mode": "single" | "monitoring" }
    config: Mapped[dict] = mapped_column(JSON, default=dict)

    # Execution settings
    total_actions: Mapped[int] = mapped_column(Integer, default=0)  # Target number of actions
    completed_actions: Mapped[int] = mapped_column(Integer, default=0)
    failed_actions: Mapped[int] = mapped_column(Integer, default=0)

    # Delay settings (seconds)
    min_delay: Mapped[float] = mapped_column(Float, default=30.0)
    max_delay: Mapped[float] = mapped_column(Float, default=120.0)

    # Concurrency
    max_concurrent: Mapped[int] = mapped_column(Integer, default=1)

    # Error tracking
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    accounts: Mapped[List["Account"]] = relationship(
        secondary=task_accounts,
        backref="tasks"
    )
    logs: Mapped[List["TaskLog"]] = relationship(back_populates="task", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "task_type": self.task_type,
            "status": self.status,
            "config": self.config,
            "total_actions": self.total_actions,
            "completed_actions": self.completed_actions,
            "failed_actions": self.failed_actions,
            "min_delay": self.min_delay,
            "max_delay": self.max_delay,
            "max_concurrent": self.max_concurrent,
            "last_error": self.last_error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat(),
            "accounts_count": len(self.accounts) if self.accounts else 0,
            "progress": round(self.completed_actions / self.total_actions * 100, 1) if self.total_actions > 0 else 0
        }


class TaskLog(Base):
    """Individual action log for a task."""
    __tablename__ = "task_logs"

    id: Mapped[int] = mapped_column(primary_key=True)

    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))
    task: Mapped["Task"] = relationship(back_populates="logs")

    account_id: Mapped[Optional[int]] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True)

    # Action details
    action_type: Mapped[str] = mapped_column(String(50))  # reaction, comment, join, etc.
    target: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # channel/post

    # Result
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Extra data (JSON)
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "task_id": self.task_id,
            "account_id": self.account_id,
            "action_type": self.action_type,
            "target": self.target,
            "success": self.success,
            "message": self.message,
            "error": self.error,
            "extra_data": self.extra_data,
            "created_at": self.created_at.isoformat()
        }


class CommentTemplate(Base):
    """Comment template with spintax support."""
    __tablename__ = "comment_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    content: Mapped[str] = mapped_column(Text)  # Supports spintax: {Hello|Hi|Hey}
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "content": self.content,
            "is_default": self.is_default,
            "created_at": self.created_at.isoformat()
        }


class TargetChannel(Base):
    """Target channel for commenting tasks."""
    __tablename__ = "target_channels"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))

    channel_username: Mapped[str] = mapped_column(String(100))
    channel_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    channel_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Status: pending, joined, error, cannot_comment
    status: Mapped[str] = mapped_column(String(20), default="pending")
    can_comment: Mapped[bool] = mapped_column(Boolean, default=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    last_post_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    comments_sent: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "task_id": self.task_id,
            "channel_username": self.channel_username,
            "channel_id": self.channel_id,
            "channel_title": self.channel_title,
            "status": self.status,
            "can_comment": self.can_comment,
            "error_message": self.error_message,
            "last_post_id": self.last_post_id,
            "comments_sent": self.comments_sent,
            "created_at": self.created_at.isoformat()
        }
