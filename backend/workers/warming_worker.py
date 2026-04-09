"""
Warming Worker - Slowly subscribes accounts to a list of channels or invite links.

The MVP keeps the behavior intentionally conservative:
- join one target per account in a wave
- wait a long randomized delay between waves
- support pause/cancel even during multi-hour cooldowns
"""

import asyncio
import logging
import random
import re
import time
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from telethon.errors import FloodWaitError, ChannelPrivateError

from database.database import SessionLocal
from database.models import Task, TaskLog
from workers.likes_worker import LikesWorker

logger = logging.getLogger(__name__)

ACTION_SKIPPED_MESSAGE = "Action was not executed"
ACCOUNT_UNAVAILABLE_ERROR = "Account unavailable before warming started"
PRIVATE_CHANNEL_INVITE_REQUIRED = "Private channel requires invite link"
ALL_WARMING_ACTIONS_FAILED = "All warming actions failed"
ALL_ACCOUNTS_FAILED_TO_CONNECT = "All accounts failed to connect"
ALL_ELIGIBLE_ACCOUNTS_EXHAUSTED = "All eligible accounts exhausted before reaching total actions"
INVALID_WARMING_TARGET = "Invalid warming target"


class WarmingWorker(LikesWorker):
    """Worker for account warming tasks."""

    INTER_ACCOUNT_STAGGER_MIN = 45.0
    INTER_ACCOUNT_STAGGER_MAX = 120.0
    FAILURE_BACKOFF_MIN = 15.0
    FAILURE_BACKOFF_MAX = 45.0
    WAIT_CHUNK_SECONDS = 5.0

    def __init__(
        self,
        task_id: int,
        on_progress: Optional[Callable[[int, int, int, str], Any]] = None,
    ):
        super().__init__(task_id=task_id, on_progress=on_progress)
        self._blocked_accounts: dict[int, str] = {}
        self._entities: dict[tuple[int, str], Any] = {}

    async def _resolve_entity(self, account_id: int, channel: str) -> Any:
        """Resolve and cache entity per (account_id, channel)."""
        key = (account_id, channel)
        if key in self._entities:
            return self._entities[key]

        client = self._clients[account_id]
        clean = channel
        if clean.startswith("@") and clean[1:].lstrip("-").isdigit():
            clean = clean[1:]

        try:
            channel_id = int(clean)
            entity = await client.client.get_entity(channel_id)
        except (ValueError, TypeError):
            entity = await client.client.get_entity(channel)

        self._entities[key] = entity
        return entity

    @staticmethod
    def _extract_invite_hash(target: str) -> Optional[str]:
        match = re.match(r"(?:https?://)?t\.me/(?:\+|joinchat/)([a-zA-Z0-9_-]+)", target, re.IGNORECASE)
        return match.group(1) if match else None

    @staticmethod
    def _normalize_public_target(target: str) -> Optional[str]:
        target = target.strip()
        private_match = re.match(
            r"(?:https?://)?t\.me/c/(\d+)(?:/\d+)?/?(?:\?.*)?$",
            target,
            re.IGNORECASE,
        )
        if private_match:
            return f"-100{private_match.group(1)}"

        public_match = re.match(
            r"(?:https?://)?t\.me/([a-zA-Z0-9_]+)(?:/\d+)?/?(?:\?.*)?$",
            target,
            re.IGNORECASE,
        )
        if public_match:
            username = public_match.group(1)
            return f"@{username}" if re.fullmatch(r"[a-zA-Z0-9_]{5,32}", username) else None

        if target.startswith("@") and target[1:].lstrip("-").isdigit():
            return target[1:]

        if target.startswith("@"):
            username = target[1:]
            return target if re.fullmatch(r"[a-zA-Z0-9_]{5,32}", username) else None

        if target.lstrip("-").isdigit():
            return target

        if re.fullmatch(r"[a-zA-Z0-9_]{5,32}", target):
            return f"@{target}"

        return None

    async def _wait_with_control(
        self,
        total_seconds: float,
        cancel_event: asyncio.Event,
        pause_event: asyncio.Event,
    ) -> bool:
        """Sleep in short chunks so pause/cancel still work during long delays."""
        remaining = max(0.0, float(total_seconds))
        while remaining > 0:
            if cancel_event.is_set():
                return False

            await pause_event.wait()

            chunk = min(self.WAIT_CHUNK_SECONDS, remaining)
            started = time.monotonic()
            try:
                await asyncio.wait_for(cancel_event.wait(), timeout=chunk)
                return False
            except asyncio.TimeoutError:
                remaining -= time.monotonic() - started

        return not cancel_event.is_set()

    @staticmethod
    def _get_account_block_reason(error: Optional[str]) -> Optional[str]:
        if not error:
            return None

        lowered = error.lower()
        if "joined too many channels" in lowered:
            return error
        if "session" in lowered and ("expired" in lowered or "revoked" in lowered):
            return error
        if "not authorized" in lowered:
            return error
        if "spamblock" in lowered or "peer_flood" in lowered:
            return error
        if "auth key" in lowered:
            return error
        return None

    def _block_account_for_current_task(self, account_id: int, reason: str) -> str:
        """Stop using an account for the rest of the current warming run."""
        self._blocked_accounts[account_id] = reason
        self._flood_wait_until.pop(account_id, None)
        return reason

    def _has_actionable_accounts(self, accounts: list[Any]) -> bool:
        """Return True while at least one connected account can still warm targets."""
        return any(
            account.id in self._clients and account.id not in self._blocked_accounts
            for account in accounts
        )

    def _fail_task_early(self, db, task: Task, error: str) -> None:
        """Finish the task immediately once no future warming progress is possible."""
        task.status = "failed"
        if not task.last_error:
            task.last_error = error
        task.completed_at = datetime.now(timezone.utc)
        db.commit()

    async def _wait_after_account(
        self,
        *,
        account_index: int,
        total_accounts: int,
        success: bool,
        cancel_event: asyncio.Event,
        pause_event: asyncio.Event,
    ) -> bool:
        """Apply a conservative delay before the next account in the wave."""
        if account_index >= total_accounts - 1:
            return True

        delay_min = self.INTER_ACCOUNT_STAGGER_MIN if success else self.FAILURE_BACKOFF_MIN
        delay_max = self.INTER_ACCOUNT_STAGGER_MAX if success else self.FAILURE_BACKOFF_MAX
        delay = random.uniform(delay_min, delay_max)
        return await self._wait_with_control(
            delay,
            cancel_event=cancel_event,
            pause_event=pause_event,
        )

    async def _record_action(
        self,
        db,
        task: Task,
        account_id: int,
        target: str,
        success: bool,
        message: Optional[str] = None,
        error: Optional[str] = None,
        extra_data: Optional[dict] = None,
    ) -> None:
        db.add(TaskLog(
            task_id=self.task_id,
            account_id=account_id,
            action_type="join_channel",
            target=target,
            success=success,
            message=message,
            error=error,
            extra_data=extra_data,
        ))

        if success:
            task.completed_actions += 1
            self._record_account_action(account_id)
            account = self._accounts_map.get(account_id)
            if account:
                account.last_used_at = datetime.now(timezone.utc)
        else:
            task.failed_actions += 1
            if error:
                task.last_error = error

        db.commit()

        if self.on_progress:
            try:
                await self.on_progress(
                    self.task_id,
                    task.completed_actions,
                    task.total_actions,
                    message or error or "",
                )
            except Exception as exc:
                logger.warning(f"Progress callback error: {exc}")

    async def _warm_single_target(
        self,
        account_id: int,
        target: str,
    ) -> tuple[bool, Optional[str], Optional[str], Any, Optional[str]]:
        invite_hash = self._extract_invite_hash(target)
        if invite_hash:
            joined, join_error, entity = await self._join_via_invite(account_id, invite_hash)
            entity = await self._resolve_entity_after_invite_join(account_id, target, entity)
            if joined:
                return True, "Joined via invite link", None, entity, target
            return False, ACTION_SKIPPED_MESSAGE, join_error or "Join via invite failed", entity, target

        normalized_target = self._normalize_public_target(target)
        if not normalized_target:
            return False, ACTION_SKIPPED_MESSAGE, INVALID_WARMING_TARGET, None, None

        try:
            entity = await self._resolve_entity(account_id, normalized_target)
        except ChannelPrivateError:
            return False, ACTION_SKIPPED_MESSAGE, PRIVATE_CHANNEL_INVITE_REQUIRED, None, None

        is_subscribed, sub_error = await self._check_subscription(account_id, entity)
        if is_subscribed:
            return True, "Already subscribed", None, entity, None

        if sub_error == "CHANNEL_PRIVATE":
            return False, ACTION_SKIPPED_MESSAGE, PRIVATE_CHANNEL_INVITE_REQUIRED, entity, None
        if sub_error:
            return False, ACTION_SKIPPED_MESSAGE, sub_error, entity, None

        joined, join_error = await self._join_channel(account_id, entity, normalized_target)
        if joined:
            self._entities.pop((account_id, normalized_target), None)
            entity = await self._resolve_entity(account_id, normalized_target)
            return True, "Joined channel", None, entity, None

        return False, ACTION_SKIPPED_MESSAGE, join_error or "Join failed", entity, None

    async def execute(
        self,
        cancel_event: asyncio.Event,
        pause_event: asyncio.Event,
    ):
        """Execute the warming task."""
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
                task.completed_at = datetime.now(timezone.utc)
                db.commit()
                return

            targets = list((task.config or {}).get("targets") or [])
            if not targets:
                task.status = "failed"
                task.last_error = "No warming targets specified"
                task.completed_at = datetime.now(timezone.utc)
                db.commit()
                return

            self._accounts_map = {account.id: account for account in accounts}

            logger.info(
                "Starting warming task %s: accounts=%s targets=%s delay=%ss-%ss",
                self.task_id,
                len(accounts),
                len(targets),
                task.min_delay,
                task.max_delay,
            )

            await self._connect_accounts(accounts, db, task.max_concurrent or 1)

            for account in accounts:
                if account.id not in self._clients:
                    self._blocked_accounts[account.id] = ACCOUNT_UNAVAILABLE_ERROR

            if not self._has_actionable_accounts(accounts):
                self._fail_task_early(db, task, ALL_ACCOUNTS_FAILED_TO_CONNECT)
                logger.info("Task %s failed before warming started: no accounts connected", self.task_id)
                return

            for index, target in enumerate(targets):
                if cancel_event.is_set():
                    task.status = "cancelled"
                    task.completed_at = datetime.now(timezone.utc)
                    db.commit()
                    logger.info(f"Task {self.task_id} cancelled")
                    return

                await pause_event.wait()
                logger.info(
                    "Task %s: warming wave %s/%s target=%s",
                    self.task_id,
                    index + 1,
                    len(targets),
                    target,
                )

                wave_accounts = list(accounts)
                random.shuffle(wave_accounts)

                for account_index, account in enumerate(wave_accounts):
                    if cancel_event.is_set():
                        task.status = "cancelled"
                        task.completed_at = datetime.now(timezone.utc)
                        db.commit()
                        logger.info(f"Task {self.task_id} cancelled")
                        return

                    await pause_event.wait()

                    blocked_reason = self._blocked_accounts.get(account.id)
                    if blocked_reason or account.id not in self._clients:
                        await self._record_action(
                            db,
                            task,
                            account.id,
                            target,
                            success=False,
                            message=ACTION_SKIPPED_MESSAGE,
                            error=blocked_reason or ACCOUNT_UNAVAILABLE_ERROR,
                        )
                        should_continue = await self._wait_after_account(
                            account_index=account_index,
                            total_accounts=len(wave_accounts),
                            success=False,
                            cancel_event=cancel_event,
                            pause_event=pause_event,
                        )
                        if not should_continue:
                            task.status = "cancelled"
                            task.completed_at = datetime.now(timezone.utc)
                            db.commit()
                            logger.info(f"Task {self.task_id} cancelled")
                            return
                        continue

                    cooldown_until = self._flood_wait_until.get(account.id)
                    now = time.monotonic()
                    if cooldown_until and now >= cooldown_until:
                        self._flood_wait_until.pop(account.id, None)
                        cooldown_until = None

                    if cooldown_until and now < cooldown_until:
                        remaining = max(1, int(cooldown_until - now))
                        await self._record_action(
                            db,
                            task,
                            account.id,
                            target,
                            success=False,
                            message=ACTION_SKIPPED_MESSAGE,
                            error=f"FloodWait: {remaining}s",
                        )
                        should_continue = await self._wait_after_account(
                            account_index=account_index,
                            total_accounts=len(wave_accounts),
                            success=False,
                            cancel_event=cancel_event,
                            pause_event=pause_event,
                        )
                        if not should_continue:
                            task.status = "cancelled"
                            task.completed_at = datetime.now(timezone.utc)
                            db.commit()
                            logger.info(f"Task {self.task_id} cancelled")
                            return
                        continue

                    try:
                        success, message, error, entity, invite_link_used = await self._warm_single_target(account.id, target)
                    except FloodWaitError as exc:
                        success = False
                        message = ACTION_SKIPPED_MESSAGE
                        error = self._block_account_for_current_task(
                            account.id,
                            f"FloodWait: {exc.seconds}s",
                        )
                        entity = None
                        invite_link_used = None
                    except Exception as exc:
                        logger.warning(
                            "Task %s: account %s failed while warming %s: %s",
                            self.task_id,
                            account.id,
                            target,
                            exc,
                        )
                        success = False
                        message = ACTION_SKIPPED_MESSAGE
                        error = str(exc)[:200]
                        entity = None
                        invite_link_used = None

                    if success:
                        self._track_channel_membership(
                            db,
                            account_id=account.id,
                            status="member",
                            target=target,
                            invite_link=invite_link_used,
                            entity=entity,
                        )
                    else:
                        membership_status = self._membership_status_from_error(error) if error else None
                        if membership_status:
                            self._track_channel_membership(
                                db,
                                account_id=account.id,
                                status=membership_status,
                                target=target,
                                invite_link=invite_link_used,
                                entity=entity,
                                error=error,
                            )

                    block_reason = self._get_account_block_reason(error)
                    if block_reason:
                        self._blocked_accounts[account.id] = block_reason

                    await self._record_action(
                        db,
                        task,
                        account.id,
                        target,
                        success=success,
                        message=message,
                        error=error,
                        extra_data={"wave": index + 1},
                    )

                    if account_index < len(wave_accounts) - 1:
                        should_continue = await self._wait_after_account(
                            account_index=account_index,
                            total_accounts=len(wave_accounts),
                            success=success,
                            cancel_event=cancel_event,
                            pause_event=pause_event,
                        )
                        if not should_continue:
                            task.status = "cancelled"
                            task.completed_at = datetime.now(timezone.utc)
                            db.commit()
                            logger.info(f"Task {self.task_id} cancelled")
                            return

                if index < len(targets) - 1:
                    if not self._has_actionable_accounts(accounts):
                        self._fail_task_early(db, task, ALL_ELIGIBLE_ACCOUNTS_EXHAUSTED)
                        logger.info(
                            "Task %s stopped early: no actionable accounts remain after wave %s/%s",
                            self.task_id,
                            index + 1,
                            len(targets),
                        )
                        return

                    delay = random.uniform(task.min_delay, task.max_delay)
                    should_continue = await self._wait_with_control(
                        delay,
                        cancel_event=cancel_event,
                        pause_event=pause_event,
                    )
                    if not should_continue:
                        task.status = "cancelled"
                        task.completed_at = datetime.now(timezone.utc)
                        db.commit()
                        logger.info(f"Task {self.task_id} cancelled")
                        return

            if cancel_event.is_set():
                task.status = "cancelled"
                task.completed_at = datetime.now(timezone.utc)
                db.commit()
                logger.info(f"Task {self.task_id} cancelled")
                return

            if task.completed_actions > 0:
                task.status = "completed"
            else:
                task.status = "failed"
                if not task.last_error:
                    task.last_error = ALL_WARMING_ACTIONS_FAILED

            task.completed_at = datetime.now(timezone.utc)
            db.commit()

            logger.info(
                "Warming task %s finished: success=%s failed=%s",
                self.task_id,
                task.completed_actions,
                task.failed_actions,
            )

        except Exception as exc:
            logger.exception(f"Warming task {self.task_id} failed with error: {exc}")
            try:
                task = db.query(Task).filter(Task.id == self.task_id).first()
                if task:
                    task.status = "failed"
                    task.last_error = str(exc)
                    task.completed_at = datetime.now(timezone.utc)
                    db.commit()
            except Exception as cleanup_exc:
                logger.debug(f"Task cleanup error: {cleanup_exc}")
        finally:
            await self._disconnect_all()
            db.close()


async def start_warming_task(task_id: int, on_progress: Optional[Callable] = None) -> bool:
    """Helper function to start a warming task."""
    from workers.task_queue import task_queue

    worker = WarmingWorker(task_id=task_id, on_progress=on_progress)
    return await task_queue.submit(task_id=task_id, worker_coro=worker.execute)
