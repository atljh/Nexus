"""
Task Queue - Manages async task execution with concurrency control.
"""

import asyncio
import logging
from typing import Dict, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class RunningTask:
    """Represents a running task in the queue."""
    task_id: int
    asyncio_task: asyncio.Task
    cancel_event: asyncio.Event
    pause_event: asyncio.Event


class TaskQueue:
    """
    Async task queue for managing automation tasks.
    Supports pause, resume, and cancel operations.
    """

    def __init__(self):
        self._running_tasks: Dict[int, RunningTask] = {}
        self._lock = asyncio.Lock()
        self._on_progress: Optional[Callable] = None
        self._on_complete: Optional[Callable] = None

    def set_callbacks(
        self,
        on_progress: Optional[Callable] = None,
        on_complete: Optional[Callable] = None
    ):
        """Set callback functions for progress and completion."""
        self._on_progress = on_progress
        self._on_complete = on_complete

    async def submit(
        self,
        task_id: int,
        worker_coro: Callable[..., Any],
        *args,
        **kwargs
    ) -> bool:
        """
        Submit a task for execution.

        Args:
            task_id: Database task ID
            worker_coro: Async function to execute
            *args, **kwargs: Arguments for the worker

        Returns:
            True if submitted successfully
        """
        async with self._lock:
            if task_id in self._running_tasks:
                logger.warning(f"Task {task_id} is already running")
                return False

            cancel_event = asyncio.Event()
            pause_event = asyncio.Event()
            pause_event.set()  # Start unpaused

            # Create wrapper that handles events
            async def task_wrapper():
                try:
                    await worker_coro(
                        *args,
                        cancel_event=cancel_event,
                        pause_event=pause_event,
                        **kwargs
                    )
                except asyncio.CancelledError:
                    logger.info(f"Task {task_id} was cancelled")
                except Exception as e:
                    logger.exception(f"Task {task_id} failed: {e}")
                finally:
                    async with self._lock:
                        self._running_tasks.pop(task_id, None)
                    if self._on_complete:
                        try:
                            await self._on_complete(task_id)
                        except Exception as e:
                            logger.exception(f"Error in completion callback: {e}")

            asyncio_task = asyncio.create_task(task_wrapper())

            self._running_tasks[task_id] = RunningTask(
                task_id=task_id,
                asyncio_task=asyncio_task,
                cancel_event=cancel_event,
                pause_event=pause_event
            )

            logger.info(f"Task {task_id} submitted to queue")
            return True

    async def cancel(self, task_id: int) -> bool:
        """Cancel a running task."""
        async with self._lock:
            running = self._running_tasks.get(task_id)
            if running is None:
                return False

            running.cancel_event.set()
            running.pause_event.set()  # Unpause so it can check cancel

        # Give task time to gracefully stop without blocking queue operations.
        await asyncio.sleep(0.5)

        if not running.asyncio_task.done():
            running.asyncio_task.cancel()

        logger.info(f"Task {task_id} cancelled")
        return True

    async def pause(self, task_id: int) -> bool:
        """Pause a running task."""
        async with self._lock:
            if task_id not in self._running_tasks:
                return False

            self._running_tasks[task_id].pause_event.clear()
            logger.info(f"Task {task_id} paused")
            return True

    async def resume(self, task_id: int) -> bool:
        """Resume a paused task."""
        async with self._lock:
            if task_id not in self._running_tasks:
                return False

            self._running_tasks[task_id].pause_event.set()
            logger.info(f"Task {task_id} resumed")
            return True

    def is_running(self, task_id: int) -> bool:
        """Check if a task is running."""
        return task_id in self._running_tasks

    def get_running_tasks(self) -> list:
        """Get list of running task IDs."""
        return list(self._running_tasks.keys())


# Global task queue instance
task_queue = TaskQueue()
