"""Tests for persistent channel registry helpers."""

from datetime import datetime
from pathlib import Path
import sys
from unittest.mock import MagicMock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.database import Base
from database.models import Account, ChannelMembership, SavedChannel
from utils.channel_registry import upsert_channel_membership, upsert_saved_channel


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    return Session()


def make_account(account_id: int) -> Account:
    account = Account(
        id=account_id,
        session_string=f"session_{account_id}",
        status="valid",
        created_at=datetime(2024, 1, 1),
    )
    return account


def make_entity(channel_id: int, title: str, username: str | None = None):
    entity = MagicMock()
    entity.id = channel_id
    entity.title = title
    entity.username = username
    return entity


def test_upsert_saved_channel_invite_only_normalizes_private_channel():
    db = make_session()

    channel = upsert_saved_channel(
        db,
        target="https://t.me/+YS_wZLCoTK4wMTgy",
    )
    db.commit()

    assert channel.invite_link == "https://t.me/+YS_wZLCoTK4wMTgy"
    assert channel.invite_hash == "YS_wZLCoTK4wMTgy"
    assert channel.is_private is True
    assert channel.normalized_target is None


def test_upsert_saved_channel_merges_manual_invite_once_entity_is_known():
    db = make_session()

    original = upsert_saved_channel(
        db,
        target="https://t.me/+_Xa2Zz-Wir40MzUy",
        title="Manual name",
    )
    db.commit()

    entity = make_entity(248149892, "Адвокат права")
    updated = upsert_saved_channel(
        db,
        target="-100248149892",
        invite_link="https://t.me/+_Xa2Zz-Wir40MzUy",
        entity=entity,
    )
    db.commit()

    assert updated.id == original.id
    assert updated.telegram_channel_id == 248149892
    assert updated.normalized_target == "-100248149892"
    assert updated.title == "Адвокат права"
    assert db.query(SavedChannel).count() == 1


def test_upsert_channel_membership_reuses_single_row_per_account_channel():
    db = make_session()
    db.add(make_account(1))
    db.commit()

    first_channel, first_membership = upsert_channel_membership(
        db,
        account_id=1,
        status="pending_approval",
        target="https://t.me/+inviteHash123",
        error="Join request sent, awaiting admin approval",
    )
    db.commit()

    entity = make_entity(123456789, "Closed channel")
    second_channel, second_membership = upsert_channel_membership(
        db,
        account_id=1,
        status="member",
        target="-100123456789",
        invite_link="https://t.me/+inviteHash123",
        entity=entity,
    )
    db.commit()

    assert first_channel.id == second_channel.id
    assert first_membership.id == second_membership.id
    assert second_membership.status == "member"
    assert second_membership.last_error is None
    assert db.query(ChannelMembership).count() == 1


def test_upsert_saved_channel_prefer_id_updates_existing_row_instead_of_creating_duplicate():
    db = make_session()

    channel = upsert_saved_channel(
        db,
        target="https://t.me/+inviteHash456",
        title="Original",
    )
    db.commit()

    updated = upsert_saved_channel(
        db,
        target="@newchannelname",
        invite_link="https://t.me/+inviteHash456",
        title="Updated",
        prefer_id=channel.id,
    )
    db.commit()

    assert updated.id == channel.id
    assert updated.normalized_target == "@newchannelname"
    assert updated.invite_link == "https://t.me/+inviteHash456"
    assert updated.title == "Updated"
    assert db.query(SavedChannel).count() == 1
