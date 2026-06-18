"""Helpers for persistent channel registry and account membership tracking."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from database.models import ChannelMembership, SavedChannel

CHANNEL_MEMBERSHIP_STATUSES = {
    "member",
    "pending_approval",
    "failed",
    "unknown",
}

USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_]{5,32}$")
NUMERIC_TARGET_PATTERN = re.compile(r"^-?\d+$")
PRIVATE_LINK_PATTERN = re.compile(
    r"(?:https?://)?t\.me/c/(\d+)(?:/\d+)?/?(?:\?.*)?$",
    re.IGNORECASE,
)
INVITE_LINK_PATTERN = re.compile(
    r"(?:https?://)?t\.me/(?:\+|joinchat/)([a-zA-Z0-9_-]+)\/?(?:\?.*)?$",
    re.IGNORECASE,
)
PUBLIC_LINK_PATTERN = re.compile(
    r"(?:https?://)?t\.me/([a-zA-Z0-9_]+)(?:/\d+)?/?(?:\?.*)?$",
    re.IGNORECASE,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def normalize_invite_link(value: Optional[str]) -> Optional[str]:
    target = " ".join((value or "").split())
    if not target:
        return None

    match = INVITE_LINK_PATTERN.match(target)
    if not match:
        return None
    return f"https://t.me/+{match.group(1)}"


def extract_invite_hash(value: Optional[str]) -> Optional[str]:
    normalized = normalize_invite_link(value)
    if not normalized:
        return None
    match = INVITE_LINK_PATTERN.match(normalized)
    return match.group(1) if match else None


def normalize_public_channel_target(value: Optional[str]) -> Optional[str]:
    target = " ".join((value or "").split())
    if not target:
        return None

    private_match = PRIVATE_LINK_PATTERN.match(target)
    if private_match:
        return f"-100{private_match.group(1)}"

    if INVITE_LINK_PATTERN.match(target):
        return None

    public_match = PUBLIC_LINK_PATTERN.match(target)
    if public_match:
        username = public_match.group(1)
        return f"@{username.lower()}" if USERNAME_PATTERN.fullmatch(username) else None

    if target.startswith("@") and NUMERIC_TARGET_PATTERN.fullmatch(target[1:]):
        return target[1:]

    if target.startswith("@"):
        username = target[1:]
        return f"@{username.lower()}" if USERNAME_PATTERN.fullmatch(username) else None

    if NUMERIC_TARGET_PATTERN.fullmatch(target):
        return target

    if USERNAME_PATTERN.fullmatch(target):
        return f"@{target.lower()}"

    return None


def _normalize_title(value: Optional[str]) -> Optional[str]:
    normalized = " ".join((value or "").split())
    return normalized[:255] if normalized else None


def _entity_username(entity: Any) -> Optional[str]:
    username = getattr(entity, "username", None)
    if not username or not USERNAME_PATTERN.fullmatch(username):
        return None
    return username.lower()


def _entity_title(entity: Any) -> Optional[str]:
    title = getattr(entity, "title", None)
    if title:
        return _normalize_title(title)

    first_name = " ".join(
        part for part in [getattr(entity, "first_name", None), getattr(entity, "last_name", None)] if part
    )
    return _normalize_title(first_name)


def _normalized_target_from_entity(entity: Any) -> Optional[str]:
    username = _entity_username(entity)
    if username:
        return f"@{username}"

    entity_id = getattr(entity, "id", None)
    if entity_id is None:
        return None

    try:
        raw_id = int(entity_id)
    except (TypeError, ValueError):
        return None

    if raw_id < 0:
        return str(raw_id)
    return f"-100{raw_id}"


def _telegram_channel_id_from_target(target: Optional[str]) -> Optional[int]:
    if not target:
        return None

    clean = target.strip()
    if clean.startswith("-100") and clean[4:].isdigit():
        return int(clean[4:])

    if clean.isdigit():
        return int(clean)

    return None


def _telegram_channel_id_from_entity(entity: Any) -> Optional[int]:
    value = getattr(entity, "id", None)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _membership_status_priority(status: str) -> int:
    return {
        "member": 3,
        "pending_approval": 2,
        "failed": 1,
        "unknown": 0,
    }.get(status, -1)


def _merge_membership(primary: ChannelMembership, duplicate: ChannelMembership) -> None:
    duplicate_is_better = (
        _membership_status_priority(duplicate.status) > _membership_status_priority(primary.status)
        or (
            duplicate.last_checked_at
            and primary.last_checked_at
            and duplicate.last_checked_at > primary.last_checked_at
        )
    )

    if duplicate_is_better:
        primary.status = duplicate.status
        primary.last_error = duplicate.last_error

    if duplicate.joined_at and (primary.joined_at is None or duplicate.joined_at < primary.joined_at):
        primary.joined_at = duplicate.joined_at

    if duplicate.last_checked_at and (
        primary.last_checked_at is None or duplicate.last_checked_at > primary.last_checked_at
    ):
        primary.last_checked_at = duplicate.last_checked_at

    if not primary.last_error and duplicate.last_error:
        primary.last_error = duplicate.last_error


def _merge_saved_channels(db: Session, primary: SavedChannel, duplicates: list[SavedChannel]) -> SavedChannel:
    for duplicate in duplicates:
        if duplicate.id == primary.id:
            continue

        if primary.telegram_channel_id is None and duplicate.telegram_channel_id is not None:
            primary.telegram_channel_id = duplicate.telegram_channel_id
        if not primary.normalized_target and duplicate.normalized_target:
            primary.normalized_target = duplicate.normalized_target
        if not primary.username and duplicate.username:
            primary.username = duplicate.username
        if not primary.title and duplicate.title:
            primary.title = duplicate.title
        if not primary.invite_link and duplicate.invite_link:
            primary.invite_link = duplicate.invite_link
        if not primary.invite_hash and duplicate.invite_hash:
            primary.invite_hash = duplicate.invite_hash
        if duplicate.last_resolved_at and (
            primary.last_resolved_at is None or duplicate.last_resolved_at > primary.last_resolved_at
        ):
            primary.last_resolved_at = duplicate.last_resolved_at
        if duplicate.last_used_at and (
            primary.last_used_at is None or duplicate.last_used_at > primary.last_used_at
        ):
            primary.last_used_at = duplicate.last_used_at
        if not primary.last_error and duplicate.last_error:
            primary.last_error = duplicate.last_error

        duplicate_memberships = db.query(ChannelMembership).filter(
            ChannelMembership.channel_id == duplicate.id
        ).all()
        for membership in duplicate_memberships:
            existing = db.query(ChannelMembership).filter(
                ChannelMembership.channel_id == primary.id,
                ChannelMembership.account_id == membership.account_id,
            ).first()

            if existing:
                _merge_membership(existing, membership)
                db.delete(membership)
            else:
                membership.channel_id = primary.id

        db.delete(duplicate)

    primary.updated_at = _utcnow()
    db.flush()
    return primary


def find_matching_saved_channels(
    db: Session,
    *,
    telegram_channel_id: Optional[int] = None,
    normalized_target: Optional[str] = None,
    username: Optional[str] = None,
    invite_hash: Optional[str] = None,
    invite_link: Optional[str] = None,
    exclude_id: Optional[int] = None,
) -> list[SavedChannel]:
    matches: list[SavedChannel] = []
    seen_ids: set[int] = set()

    def _append(items: list[SavedChannel]) -> None:
        for item in items:
            if exclude_id is not None and item.id == exclude_id:
                continue
            if item.id in seen_ids:
                continue
            seen_ids.add(item.id)
            matches.append(item)

    if telegram_channel_id is not None:
        _append(db.query(SavedChannel).filter(SavedChannel.telegram_channel_id == telegram_channel_id).all())
    if normalized_target:
        _append(db.query(SavedChannel).filter(SavedChannel.normalized_target == normalized_target).all())
    if username:
        _append(db.query(SavedChannel).filter(SavedChannel.username == username).all())
    if invite_hash:
        _append(db.query(SavedChannel).filter(SavedChannel.invite_hash == invite_hash).all())
    if invite_link:
        _append(db.query(SavedChannel).filter(SavedChannel.invite_link == invite_link).all())

    return matches


def upsert_saved_channel(
    db: Session,
    *,
    target: Optional[str] = None,
    invite_link: Optional[str] = None,
    entity: Any = None,
    title: Optional[str] = None,
    last_error: Optional[str] = None,
    touch_last_used: bool = False,
    exclude_id: Optional[int] = None,
    prefer_id: Optional[int] = None,
) -> SavedChannel:
    resolved_target = _normalized_target_from_entity(entity)
    normalized_target = resolved_target or normalize_public_channel_target(target)
    normalized_invite_link = normalize_invite_link(invite_link) or normalize_invite_link(target)
    invite_hash = extract_invite_hash(normalized_invite_link)
    telegram_channel_id = _telegram_channel_id_from_entity(entity) or _telegram_channel_id_from_target(normalized_target)
    username = _entity_username(entity)
    if username is None and normalized_target and normalized_target.startswith("@"):
        username = normalized_target[1:]

    normalized_title = _entity_title(entity) or _normalize_title(title)
    is_private = bool(normalized_invite_link) or bool(normalized_target and not normalized_target.startswith("@"))
    if username:
        is_private = False

    if not any([
        telegram_channel_id is not None,
        normalized_target,
        normalized_invite_link,
        username,
        normalized_title,
    ]):
        raise ValueError("Cannot register channel without a target, invite link, or resolved entity")

    matches = find_matching_saved_channels(
        db,
        telegram_channel_id=telegram_channel_id,
        normalized_target=normalized_target,
        username=username,
        invite_hash=invite_hash,
        invite_link=normalized_invite_link,
        exclude_id=exclude_id,
    )

    preferred = None
    if prefer_id is not None:
        preferred = db.query(SavedChannel).filter(SavedChannel.id == prefer_id).first()

    if preferred is not None:
        primary = preferred
        duplicates = [item for item in matches if item.id != primary.id]
        if duplicates:
            primary = _merge_saved_channels(db, primary, duplicates)
    elif matches:
        primary = matches[0]
        duplicates = [item for item in matches if item.id != primary.id]
        if duplicates:
            primary = _merge_saved_channels(db, primary, duplicates)
    else:
        primary = SavedChannel()
        db.add(primary)

    now = _utcnow()
    if telegram_channel_id is not None:
        primary.telegram_channel_id = telegram_channel_id
    if normalized_target:
        primary.normalized_target = normalized_target
    if username:
        primary.username = username
    if normalized_title:
        primary.title = normalized_title
    if normalized_invite_link:
        primary.invite_link = normalized_invite_link
    if invite_hash:
        primary.invite_hash = invite_hash
    primary.is_private = is_private

    if entity is not None or telegram_channel_id is not None or normalized_title:
        primary.last_resolved_at = now
        if not last_error:
            primary.last_error = None
    elif last_error:
        primary.last_error = last_error

    if touch_last_used:
        primary.last_used_at = now

    primary.updated_at = now
    db.flush()
    return primary


def upsert_channel_membership(
    db: Session,
    *,
    account_id: int,
    status: str,
    target: Optional[str] = None,
    invite_link: Optional[str] = None,
    entity: Any = None,
    title: Optional[str] = None,
    error: Optional[str] = None,
    touch_last_used: bool = False,
    prefer_id: Optional[int] = None,
) -> tuple[SavedChannel, ChannelMembership]:
    safe_status = status if status in CHANNEL_MEMBERSHIP_STATUSES else "unknown"
    channel = upsert_saved_channel(
        db,
        target=target,
        invite_link=invite_link,
        entity=entity,
        title=title,
        last_error=error if safe_status == "failed" else None,
        touch_last_used=touch_last_used,
        prefer_id=prefer_id,
    )

    membership = db.query(ChannelMembership).filter(
        ChannelMembership.channel_id == channel.id,
        ChannelMembership.account_id == account_id,
    ).first()

    if membership is None:
        membership = ChannelMembership(
            channel_id=channel.id,
            account_id=account_id,
        )
        db.add(membership)

    now = _utcnow()
    membership.status = safe_status
    membership.last_checked_at = now
    membership.updated_at = now

    if safe_status == "member":
        if membership.joined_at is None:
            membership.joined_at = now
        membership.last_error = None
    else:
        membership.last_error = error

    db.flush()
    return channel, membership
