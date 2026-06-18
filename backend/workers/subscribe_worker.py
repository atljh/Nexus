"""
Subscribe Worker - Joins accounts to a saved channel using Telethon.

Reuses the connect + resolve + auto-join machinery from LikesWorker, but only
performs the subscription step (no reactions). One account == one action, so
task progress maps directly to "accounts processed".
"""

import asyncio
import random
import logging
import re
from datetime import datetime, timezone
from typing import Callable, Optional

from telethon.errors import ChannelPrivateError, FloodWaitError

from database.database import SessionLocal
from database.models import Task, TaskLog
from utils.channel_registry import upsert_channel_membership
from workers.likes_worker import LikesWorker

logger = logging.getLogger(__name__)

# Short FloodWaits are slept through and retried once; longer ones fail the
# account (the user can re-run the button later — already-member accounts are
# skipped, so only the not-yet-subscribed ones get retried).
FLOOD_WAIT_RETRY_CAP_SECONDS = 60


class SubscribeWorker(LikesWorker):
    """Worker that subscribes accounts to a single channel."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # The SavedChannel this task subscribes to; threaded into the membership
        # upsert so counts always land on the exact channel the user clicked
        # (and never spawn a duplicate SavedChannel).
        self._saved_channel_id = None

    def _track_channel_membership(self, db, **kwargs) -> None:
        """Override the parent helper to pin membership to the clicked channel."""
        try:
            upsert_channel_membership(
                db,
                touch_last_used=kwargs.get("status") == "member",
                prefer_id=self._saved_channel_id,
                **kwargs,
            )
        except ValueError:
            logger.debug(
                "Account %s: skipped channel registry update (unresolved target)",
                kwargs.get("account_id"),
            )

    def _record_subscribe_log(
        self,
        db,
        account_id: int,
        target: Optional[str],
        success: bool,
        message: str,
        error: Optional[str] = None,
    ) -> None:
        db.add(TaskLog(
            task_id=self.task_id,
            account_id=account_id,
            action_type="subscribe",
            target=target,
            success=success,
            message=message,
            error=error,
        ))

    async def execute(
        self,
        cancel_event: asyncio.Event,
        pause_event: asyncio.Event,
    ):
        """Execute the subscribe task."""
        db = SessionLocal()
        try:
            task = db.query(Task).filter(Task.id == self.task_id).first()
            if not task:
                logger.error(f"Task {self.task_id} not found")
                return

            if task.status != "running":
                task.status = "running"
                task.started_at = datetime.now(timezone.utc)
                db.commit()

            accounts = list(task.accounts)
            if not accounts:
                task.status = "failed"
                task.last_error = "No accounts assigned to task"
                db.commit()
                return

            self._accounts_map = {a.id: a for a in accounts}

            # Parse channel target / invite link (same conventions as likes)
            config = task.config or {}
            self._saved_channel_id = config.get("channel_id")
            channel = config.get("channel", "") or ""
            channel, _, invite_hash = self._parse_channel(channel)

            invite_link = config.get("invite_link", "") or ""
            if invite_link and not invite_hash:
                _, _, invite_hash = self._parse_channel(invite_link)
                if not invite_hash:
                    m = re.match(r'(?:https?://)?t\.me/(?:\+|joinchat/)([a-zA-Z0-9_-]+)', invite_link)
                    if m:
                        invite_hash = m.group(1)

            max_concurrent = task.max_concurrent or 1

            logger.info(
                f"Starting subscribe task {self.task_id}: channel={channel!r} "
                f"invite_hash={'yes' if invite_hash else 'no'} accounts={len(accounts)}"
            )

            # Phase 1: connect all accounts in parallel
            connected = await self._connect_accounts(accounts, db, max_concurrent)
            if connected == 0:
                task.status = "failed"
                task.failed_actions = len(accounts)
                task.last_error = "All accounts failed to connect"
                db.commit()
                return

            completed = task.completed_actions
            failed = task.failed_actions

            try:
                for account in accounts:
                    if cancel_event.is_set():
                        task.status = "cancelled"
                        task.completed_at = datetime.now(timezone.utc)
                        db.commit()
                        logger.info(f"Subscribe task {self.task_id} cancelled")
                        return

                    await pause_event.wait()

                    # Account could not connect during phase 1
                    if account.id in self._failed_accounts or account.id not in self._clients:
                        failed += 1
                        task.failed_actions = failed
                        self._record_subscribe_log(
                            db, account.id, channel, False,
                            "Action was not executed", "Account failed to connect",
                        )
                        db.commit()
                        await self._emit_progress(task, completed)
                        continue

                    did_join = await self._subscribe_one(
                        db, account, channel, invite_link, invite_hash
                    )

                    if did_join is None:
                        failed += 1
                        task.failed_actions = failed
                    else:
                        completed += 1
                        task.completed_actions = completed
                    db.commit()
                    await self._emit_progress(task, completed)

                    # Pace only when an actual join happened — already-member
                    # accounts carry no detection risk.
                    if did_join:
                        await asyncio.sleep(random.uniform(task.min_delay, task.max_delay))

                if completed > 0:
                    task.status = "completed"
                elif failed > 0:
                    task.status = "failed"
                    if not task.last_error:
                        task.last_error = "No accounts could be subscribed"
                else:
                    task.status = "completed"
                task.completed_at = datetime.now(timezone.utc)
                db.commit()

                logger.info(
                    f"Subscribe task {self.task_id} done: subscribed={completed}, failed={failed}"
                )
            finally:
                await self._disconnect_all()

        except Exception as e:
            logger.exception(f"Subscribe task {self.task_id} failed with error: {e}")
            try:
                task = db.query(Task).filter(Task.id == self.task_id).first()
                if task:
                    task.status = "failed"
                    task.last_error = str(e)
                    task.completed_at = datetime.now(timezone.utc)
                    db.commit()
            except Exception as cleanup_error:
                logger.debug(f"Task cleanup error: {cleanup_error}")
            await self._disconnect_all()
        finally:
            db.close()

    async def _emit_progress(self, task: Task, completed: int) -> None:
        if not self.on_progress:
            return
        try:
            await self.on_progress(self.task_id, completed, task.total_actions, "")
        except Exception as e:
            logger.warning(f"Progress callback error: {e}")

    async def _subscribe_one(
        self,
        db,
        account,
        channel: str,
        invite_link: str,
        invite_hash: Optional[str],
        _flood_retry: bool = True,
    ) -> Optional[bool]:
        """Subscribe a single (connected) account.

        Returns True if a real join happened, False if the account was already a
        member, or None on failure.
        """
        try:
            if invite_hash:
                joined, join_error, entity, did_join = await self._join_via_invite(
                    account.id, invite_hash
                )
                entity = await self._resolve_entity_after_invite_join(account.id, channel, entity)
                if not joined or not entity:
                    reason = join_error or "Channel entity could not be resolved after join"
                    membership_status = self._membership_status_from_error(reason)
                    if membership_status:
                        self._track_channel_membership(
                            db, account_id=account.id, status=membership_status,
                            target=channel, invite_link=invite_link or channel, error=reason,
                        )
                    self._record_subscribe_log(db, account.id, channel, False, "Action was not executed", reason)
                    return None

                self._entities[account.id] = entity
                self._track_channel_membership(
                    db, account_id=account.id, status="member",
                    target=channel, invite_link=invite_link or channel, entity=entity,
                )
                self._record_subscribe_log(
                    db, account.id, channel, True,
                    "Joined via invite link" if did_join else "Already subscribed",
                )
                return did_join

            # Public / numeric ID channel flow
            entity = await self._resolve_entity(account.id, channel)
            is_subscribed, sub_error = await self._check_subscription(account.id, entity)
            if sub_error == "CHANNEL_PRIVATE":
                is_subscribed = False

            did_join = False
            if not is_subscribed:
                did_join = True
                joined, join_error = await self._join_channel(account.id, entity, channel)
                if not joined:
                    reason = join_error or "Join failed"
                    membership_status = self._membership_status_from_error(reason) or "failed"
                    self._track_channel_membership(
                        db, account_id=account.id, status=membership_status,
                        target=channel, invite_link=invite_link or None, entity=entity, error=reason,
                    )
                    self._record_subscribe_log(db, account.id, channel, False, "Action was not executed", reason)
                    return None
                self._entities.pop(account.id, None)
                entity = await self._resolve_entity(account.id, channel)

            self._track_channel_membership(
                db, account_id=account.id, status="member",
                target=channel, invite_link=invite_link or None, entity=entity,
            )
            self._record_subscribe_log(
                db, account.id, channel, True,
                "Joined channel" if did_join else "Already subscribed",
            )
            return did_join

        except ChannelPrivateError:
            reason = "Private channel requires invite link"
            self._track_channel_membership(
                db, account_id=account.id, status="failed",
                target=channel, invite_link=invite_link or None, error=reason,
            )
            self._record_subscribe_log(db, account.id, channel, False, "Action was not executed", reason)
            return None
        except FloodWaitError as e:
            if _flood_retry and e.seconds <= FLOOD_WAIT_RETRY_CAP_SECONDS:
                logger.info(f"Account {account.id}: FloodWait {e.seconds}s on subscribe, sleeping then retrying")
                await asyncio.sleep(e.seconds + 1)
                return await self._subscribe_one(
                    db, account, channel, invite_link, invite_hash, _flood_retry=False
                )
            reason = f"FloodWait: {e.seconds}s"
            self._record_subscribe_log(db, account.id, channel, False, "Action was not executed", reason)
            return None
        except Exception as e:
            reason = str(e)[:200]
            membership_status = self._membership_status_from_error(reason)
            if membership_status:
                self._track_channel_membership(
                    db, account_id=account.id, status=membership_status,
                    target=channel, invite_link=invite_link or None, error=reason,
                )
            logger.warning(f"Account {account.id}: subscribe failed — {e}")
            self._record_subscribe_log(db, account.id, channel, False, "Action was not executed", reason)
            return None


async def start_subscribe_task(task_id: int, on_progress: Optional[Callable] = None) -> bool:
    """Helper to submit a subscribe task to the queue."""
    from workers.task_queue import task_queue

    worker = SubscribeWorker(task_id=task_id, on_progress=on_progress)
    return await task_queue.submit(task_id=task_id, worker_coro=worker.execute)
