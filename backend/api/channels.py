"""Persistent channel registry API."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from database.database import get_db
from database.models import Account, ChannelMembership, SavedChannel, Task
from utils.channel_registry import (
    normalize_invite_link,
    normalize_public_channel_target,
    upsert_saved_channel,
)

router = APIRouter()


class SavedChannelRequest(BaseModel):
    target: Optional[str] = Field(None, description="Public @username, -100 ID, t.me/c link, or invite link")
    invite_link: Optional[str] = Field(None, description="Invite link for a private channel")
    title: Optional[str] = Field(None, description="Optional manual title")


def _membership_counts(db: Session, channel_ids: list[int]) -> dict[int, dict[str, int]]:
    if not channel_ids:
        return {}

    rows = db.query(
        ChannelMembership.channel_id,
        func.count(ChannelMembership.id),
        func.sum(case((ChannelMembership.status == "member", 1), else_=0)),
        func.sum(case((ChannelMembership.status == "pending_approval", 1), else_=0)),
        func.sum(case((ChannelMembership.status == "failed", 1), else_=0)),
    ).filter(
        ChannelMembership.channel_id.in_(channel_ids)
    ).group_by(ChannelMembership.channel_id).all()

    counts: dict[int, dict[str, int]] = {}
    for channel_id, total, members, pending, failed in rows:
        counts[channel_id] = {
            "memberships_count": int(total or 0),
            "members_count": int(members or 0),
            "pending_count": int(pending or 0),
            "failed_count": int(failed or 0),
        }
    return counts


def _serialize_channel(channel: SavedChannel, counts: Optional[dict[str, int]] = None) -> dict:
    payload = channel.to_dict()
    payload.update({
        "memberships_count": 0,
        "members_count": 0,
        "pending_count": 0,
        "failed_count": 0,
    })
    if counts:
        payload.update(counts)
    return payload


@router.get("")
def get_saved_channels(
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(SavedChannel)
    if search:
        needle = f"%{search.strip()}%"
        query = query.filter(or_(
            SavedChannel.title.ilike(needle),
            SavedChannel.username.ilike(needle),
            SavedChannel.normalized_target.ilike(needle),
            SavedChannel.invite_link.ilike(needle),
        ))

    channels = query.order_by(SavedChannel.updated_at.desc(), SavedChannel.id.desc()).all()
    counts = _membership_counts(db, [channel.id for channel in channels])
    return [_serialize_channel(channel, counts.get(channel.id)) for channel in channels]


@router.get("/{channel_id}")
def get_saved_channel(
    channel_id: int,
    db: Session = Depends(get_db),
):
    channel = db.query(SavedChannel).filter(SavedChannel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    counts = _membership_counts(db, [channel.id])
    return _serialize_channel(channel, counts.get(channel.id))


@router.get("/{channel_id}/memberships")
def get_channel_memberships(
    channel_id: int,
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    channel = db.query(SavedChannel).filter(SavedChannel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    status_order = case(
        (ChannelMembership.status == "member", 0),
        (ChannelMembership.status == "pending_approval", 1),
        (ChannelMembership.status == "failed", 2),
        else_=3,
    )

    query = db.query(ChannelMembership, Account).join(
        Account,
        Account.id == ChannelMembership.account_id,
    ).filter(ChannelMembership.channel_id == channel_id)

    if status:
        query = query.filter(ChannelMembership.status == status)

    rows = query.order_by(
        status_order,
        Account.status.asc(),
        func.coalesce(Account.first_name, Account.username, Account.phone, "").asc(),
        Account.id.asc(),
    ).all()

    memberships = []
    for membership, account in rows:
        item = membership.to_dict()
        item["account"] = {
            "id": account.id,
            "username": account.username,
            "phone": account.phone,
            "first_name": account.first_name,
            "last_name": account.last_name,
            "status": account.status,
        }
        memberships.append(item)

    counts = _membership_counts(db, [channel.id])
    return {
        "channel": _serialize_channel(channel, counts.get(channel.id)),
        "memberships": memberships,
    }


@router.post("")
def create_saved_channel(
    payload: SavedChannelRequest,
    db: Session = Depends(get_db),
):
    normalized_target = normalize_public_channel_target(payload.target)
    normalized_invite = normalize_invite_link(payload.invite_link) or normalize_invite_link(payload.target)

    if not normalized_target and not normalized_invite:
        raise HTTPException(status_code=400, detail="Provide a valid channel target or invite link")

    channel = upsert_saved_channel(
        db,
        target=payload.target,
        invite_link=payload.invite_link,
        title=payload.title,
        prefer_id=None,
    )
    db.commit()
    db.refresh(channel)
    return _serialize_channel(channel)


@router.put("/{channel_id}")
def update_saved_channel(
    channel_id: int,
    payload: SavedChannelRequest,
    db: Session = Depends(get_db),
):
    channel = db.query(SavedChannel).filter(SavedChannel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    target = payload.target if payload.target is not None else channel.normalized_target
    invite_link = payload.invite_link if payload.invite_link is not None else channel.invite_link
    title = payload.title if payload.title is not None else channel.title

    if not normalize_public_channel_target(target) and not normalize_invite_link(invite_link) and not normalize_invite_link(target):
        raise HTTPException(status_code=400, detail="Provide a valid channel target or invite link")

    updated = upsert_saved_channel(
        db,
        target=target,
        invite_link=invite_link,
        title=title,
        prefer_id=channel.id,
    )
    db.commit()
    db.refresh(updated)
    counts = _membership_counts(db, [updated.id])
    return _serialize_channel(updated, counts.get(updated.id))


@router.delete("/{channel_id}")
def delete_saved_channel(
    channel_id: int,
    db: Session = Depends(get_db),
):
    channel = db.query(SavedChannel).filter(SavedChannel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    db.delete(channel)
    db.commit()
    return {"success": True}


class SubscribeAccountsRequest(BaseModel):
    account_ids: Optional[List[int]] = Field(
        None, description="Restrict to these accounts; default = all valid accounts not yet members"
    )
    min_delay: float = Field(15.0, ge=1, le=3600, description="Min delay between joins (seconds)")
    max_delay: float = Field(45.0, ge=1, le=3600, description="Max delay between joins (seconds)")
    max_concurrent: int = Field(1, ge=1, le=5, description="Max concurrent connections")


@router.post("/{channel_id}/subscribe")
async def subscribe_unsubscribed_accounts(
    channel_id: int,
    payload: SubscribeAccountsRequest,
    db: Session = Depends(get_db),
):
    """Create and start a background task that subscribes every valid account
    that is not yet a member of this channel (and retries previously failed ones)."""
    from workers.subscribe_worker import start_subscribe_task

    channel = db.query(SavedChannel).filter(SavedChannel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    target = channel.normalized_target or channel.invite_link
    if not target:
        raise HTTPException(status_code=400, detail="Channel has no resolvable target")

    # Accounts already subscribed to this channel — those are skipped.
    member_ids = {
        row[0]
        for row in db.query(ChannelMembership.account_id).filter(
            ChannelMembership.channel_id == channel_id,
            ChannelMembership.status == "member",
        ).all()
    }

    query = db.query(Account).filter(Account.status == "valid")
    if payload.account_ids:
        query = query.filter(Account.id.in_(payload.account_ids))
    accounts = [acc for acc in query.all() if acc.id not in member_ids]

    if not accounts:
        return {
            "success": True,
            "task_id": None,
            "total": 0,
            "message": "All valid accounts are already subscribed",
        }

    min_delay = min(payload.min_delay, payload.max_delay)
    max_delay = max(payload.min_delay, payload.max_delay)

    task_config = {"channel": target, "channel_id": channel.id}
    if channel.invite_link:
        task_config["invite_link"] = channel.invite_link

    task = Task(
        task_type="subscribe",
        status="running",
        config=task_config,
        total_actions=len(accounts),
        min_delay=min_delay,
        max_delay=max_delay,
        max_concurrent=payload.max_concurrent,
        started_at=datetime.now(timezone.utc),
    )
    task.accounts = accounts
    db.add(task)
    db.commit()
    db.refresh(task)

    submitted = await start_subscribe_task(task.id)
    if not submitted:
        task.status = "pending"
        task.last_error = "Task is already running in queue"
        db.commit()
        raise HTTPException(status_code=409, detail="Failed to start subscribe task")

    return {
        "success": True,
        "task_id": task.id,
        "total": len(accounts),
        "message": f"Subscribing {len(accounts)} account(s)",
    }
