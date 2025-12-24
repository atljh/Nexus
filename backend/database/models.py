from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, Table, Column, Text
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
    status: Mapped[str] = mapped_column(String(20), default="unchecked")  # unchecked, valid, invalid
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
    # unchecked, checking, valid, invalid, banned, spamblock, session_expired

    # Session storage
    session_string: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

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
            "proxy": self.proxy.to_dict() if self.proxy else None,
            "proxy_id": self.proxy_id,
            "group": self.group.to_dict() if self.group else None,
            "group_id": self.group_id,
            "tags": [tag.to_dict() for tag in self.tags] if self.tags else [],
            "last_checked_at": self.last_checked_at.isoformat() if self.last_checked_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "created_at": self.created_at.isoformat()
        }
