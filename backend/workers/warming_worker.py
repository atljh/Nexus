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


class WarmingWorker(LikesWorker):
    """Worker for account warming tasks."""

    INTER_ACCOUNT_STAGGER_MIN = 10.0
    INTER_ACCOUNT_STAGGER_MAX = 30.0
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
    def _normalize_public_target(target: str) -> str:
        target = target.strip()
        private_match = re.match(r"(?:https?://)?t\.me/c/(\d+)(?:/\d+)?$", target, re.IGNORECASE)
        if private_match:
            return f"-100{private_match.group(1)}"

        public_match = re.match(r"(?:https?://)?t\.me/([a-zA-Z0-9_]+)(?:/\d+)?$", target, re.IGNORECASE)
        if public_match:
            return f"@{public_match.group(1)}"

        if target.startswith("@") and target[1:].lstrip("-").isdigit():
            return target[1:]

        if target.startswith("@") or target.lstrip("-").isdigit():
            return target

        return f"@{target}"

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
    ) -> tuple[bool, Optional[str], Optional[str]]:
        invite_hash = self._extract_invite_hash(target)
        if invite_hash:
            joined, join_error, _entity = await self._join_via_invite(account_id, invite_hash)
            if joined:
                return True, "Joined via invite link", None
            return False, ACTION_SKIPPED_MESSAGE, join_error or "Join via invite failed"

        normalized_target = self._normalize_public_target(target)
        try:
            entity = await self._resolve_entity(account_id, normalized_target)
        except ChannelPrivateError:
            return False, ACTION_SKIPPED_MESSAGE, PRIVATE_CHANNEL_INVITE_REQUIRED

        is_subscribed, sub_error = await self._check_subscription(account_id, entity)
        if is_subscribed:
            return True, "Already subscribed", None

        if sub_error == "CHANNEL_PRIVATE":
            return False, ACTION_SKIPPED_MESSAGE, PRIVATE_CHANNEL_INVITE_REQUIRED
        if sub_error:
            return False, ACTION_SKIPPED_MESSAGE, sub_error

        joined, join_error = await self._join_channel(account_id, entity, normalized_target)
        if joined:
            self._entities.pop((account_id, normalized_target), None)
            return True, "Joined channel", None

        return False, ACTION_SKIPPED_MESSAGE, join_error or "Join failed"

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
                "Starting warming task %s: accounts=%s targets=%s preset=%s",
                self.task_id,
                len(accounts),
                len(targets),
                (task.config or {}).get("speed_preset", "safe"),
            )

            await self._connect_accounts(accounts, db, task.max_concurrent or 1)

            for account in accounts:
                if account.id not in self._clients:
                    self._blocked_accounts[account.id] = ACCOUNT_UNAVAILABLE_ERROR

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

                for account_index, account in enumerate(accounts):
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
                        continue

                    try:
                        success, message, error = await self._warm_single_target(account.id, target)
                    except FloodWaitError as exc:
                        self._flood_wait_until[account.id] = time.monotonic() + exc.seconds
                        success = False
                        message = ACTION_SKIPPED_MESSAGE
                        error = f"FloodWait: {exc.seconds}s"
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

                    if account_index < len(accounts) - 1:
                        stagger = random.uniform(
                            self.INTER_ACCOUNT_STAGGER_MIN,
                            self.INTER_ACCOUNT_STAGGER_MAX,
                        )
                        should_continue = await self._wait_with_control(
                            stagger,
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
