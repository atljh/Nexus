"""
Integration tests for the four client-requested features:
  1. angry/rage reactions in the auto-likes palette
  2. RU/UA name generation
  3. "subscribe unsubscribed accounts" channel flow (endpoint + worker)
  4. load-balanced proxy assignment

Telegram network calls are mocked (no live sessions). DB access uses an
isolated temp SQLite file with our OWN engines — the app's real engine /
SessionLocal are never touched, so this file is safe to run in any order
alongside the rest of the suite (it cannot wipe ~/.Nexus/nexus.db).
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio  # noqa: E402
from unittest.mock import AsyncMock, MagicMock  # noqa: E402

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession, async_sessionmaker, create_async_engine,
)

from database.database import Base  # noqa: E402
from database.models import (  # noqa: E402
    Account, Proxy, Task, SavedChannel, ChannelMembership,
)

# ── Our own isolated DB (NOT the app's engine) ──
_DB_FILE = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_DB_FILE.close()
_sync_engine = create_engine(f"sqlite:///{_DB_FILE.name}")
_Session = sessionmaker(bind=_sync_engine, expire_on_commit=False)
_async_engine = create_async_engine(f"sqlite+aiosqlite:///{_DB_FILE.name}")
_AsyncSession = async_sessionmaker(_async_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(bind=_sync_engine)
    Base.metadata.create_all(bind=_sync_engine)
    yield
    Base.metadata.drop_all(bind=_sync_engine)


def _proxy(host, port=1080):
    return Proxy(host=host, port=port, type="socks5", status="valid")


def _account(acc_id, status="valid", proxy_id=None, session=True):
    return Account(
        id=acc_id,
        status=status,
        proxy_id=proxy_id,
        session_string=f"sess_{acc_id}" if session else None,
        phone=f"+100000{acc_id}",
        telegram_id=900000 + acc_id,
    )


def _entity(username="testchan", ch_id=555):
    e = MagicMock()
    e.id = ch_id
    e.title = "Test"
    e.username = username
    return e


# ─────────────────────────── 1. Reactions ───────────────────────────

def test_angry_reactions_in_backend_map():
    from workers.likes_worker import REACTIONS_MAP
    assert REACTIONS_MAP["😡"] == "😡"
    assert REACTIONS_MAP["🤬"] == "🤬"
    assert REACTIONS_MAP["angry"] == "😡"
    # bare emoji, no variation selector
    assert [hex(ord(c)) for c in "😡"] == ["0x1f621"]
    assert [hex(ord(c)) for c in "🤬"] == ["0x1f92c"]


# ─────────────────────────── 2. Name generator ───────────────────────────

def test_name_generator_gender_and_locale():
    from telegram.profile_data import (
        generate_random_profile,
        MALE_NAMES_RU, FEMALE_NAMES_RU, LAST_NAMES_RU_MALE, LAST_NAMES_RU_FEMALE,
        MALE_NAMES_UA, FEMALE_NAMES_UA, MALE_NAMES_EN,
    )
    # female RU surnames are the male forms + "а"
    assert len(LAST_NAMES_RU_MALE) == len(LAST_NAMES_RU_FEMALE)
    for m, f in zip(LAST_NAMES_RU_MALE, LAST_NAMES_RU_FEMALE):
        assert f == m + "а", f"{f} should be {m}а"
    # no gender cross-contamination
    assert not (set(MALE_NAMES_RU) & set(FEMALE_NAMES_RU))
    assert not (set(MALE_NAMES_UA) & set(FEMALE_NAMES_UA))

    for _ in range(300):
        p = generate_random_profile(gender="male", locale="ru")
        assert p["first_name"] in MALE_NAMES_RU
        if p["last_name"]:
            assert p["last_name"] in LAST_NAMES_RU_MALE
        p = generate_random_profile(gender="female", locale="ru")
        assert p["first_name"] in FEMALE_NAMES_RU
        if p["last_name"]:
            assert p["last_name"] in LAST_NAMES_RU_FEMALE

    # unknown locale falls back to EN
    assert generate_random_profile(gender="male", locale="zz")["first_name"] in MALE_NAMES_EN


# ─────────────────────────── 4. Proxy balancing ───────────────────────────

@pytest.mark.asyncio
async def test_balanced_proxy_assignment_evens_out_load():
    from api.accounts import assign_proxies, AssignProxiesRequest

    s = _Session()
    p1, p2, p3 = _proxy("1.1.1.1"), _proxy("2.2.2.2"), _proxy("3.3.3.3")
    s.add_all([p1, p2, p3])
    s.flush()
    pids = [p1.id, p2.id, p3.id]
    # Fixed (not reassigned): 3 on p1, 1 on p2, 0 on p3 → uneven, like the complaint
    fixed = [_account(1, proxy_id=p1.id), _account(2, proxy_id=p1.id),
             _account(3, proxy_id=p1.id), _account(4, proxy_id=p2.id)]
    reassign = [_account(10 + i, proxy_id=None) for i in range(6)]
    s.add_all(fixed + reassign)
    s.commit()
    reassign_ids = [a.id for a in reassign]
    fixed_ids = [a.id for a in fixed]
    s.close()

    async with _AsyncSession() as asess:
        result = await assign_proxies(
            AssignProxiesRequest(account_ids=reassign_ids, proxy_ids=pids, mode="balanced"),
            asess,
        )
    assert result["success"] and result["updated"] == 6

    s = _Session()
    counts = {pid: s.query(Account).filter(Account.proxy_id == pid).count() for pid in pids}
    for fid in fixed_ids:
        assert s.get(Account, fid).proxy_id in pids
    for rid in reassign_ids:
        assert s.get(Account, rid).proxy_id in pids
    s.close()

    assert sum(counts.values()) == 10  # 4 fixed + 6 reassigned, none lost
    assert max(counts.values()) - min(counts.values()) <= 1, counts


# ─────────────────────────── 3. Subscribe endpoint ───────────────────────────

@pytest.mark.asyncio
async def test_subscribe_endpoint_selects_unsubscribed_and_creates_task(monkeypatch):
    import workers.subscribe_worker as sw
    from api.channels import subscribe_unsubscribed_accounts, SubscribeAccountsRequest

    started = {}

    async def fake_start(task_id):
        started["task_id"] = task_id
        return True

    monkeypatch.setattr(sw, "start_subscribe_task", fake_start)

    s = _Session()
    chan = SavedChannel(normalized_target="@testchan", title="Test", is_private=False)
    s.add(chan)
    s.flush()
    members = [_account(1), _account(2)]              # already members → skip
    fresh = [_account(3), _account(4), _account(5)]   # valid non-members → include
    failed = [_account(6)]                            # failed membership → retry/include
    invalid = [_account(7, status="invalid")]         # not valid → skip
    s.add_all(members + fresh + failed + invalid)
    s.flush()
    for a in members:
        s.add(ChannelMembership(channel_id=chan.id, account_id=a.id, status="member"))
    s.add(ChannelMembership(channel_id=chan.id, account_id=failed[0].id, status="failed"))
    s.commit()
    chan_id = chan.id
    s.close()

    s = _Session()
    result = await subscribe_unsubscribed_accounts(chan_id, SubscribeAccountsRequest(), s)
    s.close()

    assert result["success"] is True
    assert result["total"] == 4
    assert result["task_id"] is not None
    assert started["task_id"] == result["task_id"]

    s = _Session()
    task = s.get(Task, result["task_id"])
    assert task.task_type == "subscribe"
    assert task.status == "running"
    assert task.total_actions == 4
    assert task.started_at is not None
    assert task.config["channel"] == "@testchan"
    assert task.config["channel_id"] == chan_id
    assert {a.id for a in task.accounts} == {3, 4, 5, 6}
    s.close()


@pytest.mark.asyncio
async def test_subscribe_endpoint_noop_when_all_subscribed(monkeypatch):
    import workers.subscribe_worker as sw
    from api.channels import subscribe_unsubscribed_accounts, SubscribeAccountsRequest

    monkeypatch.setattr(sw, "start_subscribe_task", AsyncMock(return_value=True))

    s = _Session()
    chan = SavedChannel(normalized_target="@allin", is_private=False)
    s.add(chan)
    s.flush()
    a = _account(1)
    s.add(a)
    s.flush()
    s.add(ChannelMembership(channel_id=chan.id, account_id=a.id, status="member"))
    s.commit()
    chan_id = chan.id
    s.close()

    s = _Session()
    result = await subscribe_unsubscribed_accounts(chan_id, SubscribeAccountsRequest(), s)
    assert result["task_id"] is None and result["total"] == 0
    assert s.query(Task).count() == 0
    s.close()


# ─────────────────────────── 3b. Subscribe worker ───────────────────────────

def test_subscribe_worker_joins_and_tracks_membership_on_clicked_channel(monkeypatch):
    from workers.subscribe_worker import SubscribeWorker
    monkeypatch.setattr("workers.subscribe_worker.SessionLocal", _Session)

    s = _Session()
    chan = SavedChannel(normalized_target="@testchan", username="testchan", is_private=False)
    s.add(chan)
    s.flush()
    chan_id = chan.id
    accts = [_account(101), _account(102), _account(103)]
    s.add_all(accts)
    s.flush()
    task = Task(
        task_type="subscribe", status="running",
        config={"channel": "@testchan", "channel_id": chan_id},
        total_actions=3, min_delay=0, max_delay=0, max_concurrent=1,
    )
    task.accounts = accts
    s.add(task)
    s.commit()
    task_id = task.id
    s.close()

    worker = SubscribeWorker(task_id=task_id)

    async def fake_connect(accounts, db, max_concurrent=1):
        for a in accounts:
            worker._clients[a.id] = MagicMock()
        return len(accounts)

    async def fake_join(account_id, entity, channel):
        if account_id == 103:
            return False, "Account banned in channel"
        return True, None

    worker._connect_accounts = fake_connect
    worker._resolve_entity = AsyncMock(return_value=_entity())
    worker._check_subscription = AsyncMock(return_value=(False, None))  # not subscribed → join
    worker._join_channel = fake_join
    worker._disconnect_all = AsyncMock()

    cancel_event, pause_event = asyncio.Event(), asyncio.Event()
    pause_event.set()
    asyncio.run(worker.execute(cancel_event, pause_event))

    s = _Session()
    task = s.get(Task, task_id)
    assert task.completed_actions == 2
    assert task.failed_actions == 1
    assert task.completed_actions + task.failed_actions == task.total_actions
    assert task.status == "completed"
    # prefer_id pinned membership to the clicked channel — no duplicate created
    assert s.query(SavedChannel).count() == 1
    members = s.query(ChannelMembership).filter(
        ChannelMembership.channel_id == chan_id, ChannelMembership.status == "member"
    ).count()
    failed = s.query(ChannelMembership).filter(
        ChannelMembership.channel_id == chan_id, ChannelMembership.status == "failed"
    ).count()
    assert members == 2 and failed == 1
    s.close()


def test_subscribe_worker_all_connect_fail_marks_failed(monkeypatch):
    from workers.subscribe_worker import SubscribeWorker
    monkeypatch.setattr("workers.subscribe_worker.SessionLocal", _Session)

    s = _Session()
    chan = SavedChannel(normalized_target="@c2", username="c2", is_private=False)
    s.add(chan)
    s.flush()
    accts = [_account(201), _account(202)]
    s.add_all(accts)
    s.flush()
    task = Task(
        task_type="subscribe", status="running",
        config={"channel": "@c2", "channel_id": chan.id},
        total_actions=2, min_delay=0, max_delay=0, max_concurrent=1,
    )
    task.accounts = accts
    s.add(task)
    s.commit()
    task_id = task.id
    s.close()

    worker = SubscribeWorker(task_id=task_id)
    worker._connect_accounts = AsyncMock(return_value=0)
    worker._disconnect_all = AsyncMock()

    cancel_event, pause_event = asyncio.Event(), asyncio.Event()
    pause_event.set()
    asyncio.run(worker.execute(cancel_event, pause_event))

    s = _Session()
    task = s.get(Task, task_id)
    assert task.status == "failed"
    assert task.failed_actions == 2
    s.close()
