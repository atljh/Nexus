"""
Likes Worker - Executes reaction tasks using Telethon.
"""

import asyncio
import random
import logging
from datetime import datetime
from typing import List, Dict, Optional, Callable, Any

from sqlalchemy.orm import Session
from telethon.errors import (
    FloodWaitError,
    ReactionInvalidError,
    ChatWriteForbiddenError,
    ChannelPrivateError,
    UserBannedInChannelError,
    MsgIdInvalidError,
)

from database.database import SessionLocal
from database.models import Task, TaskLog, Account
from telegram.client import BaseClient

logger = logging.getLogger(__name__)

# Available reactions
REACTIONS_MAP = {
    "👍": "👍",
    "thumbsup": "👍",
    "👎": "👎",
    "thumbsdown": "👎",
    "❤️": "❤",
    "heart": "❤",
    "🔥": "🔥",
    "fire": "🔥",
    "🥰": "🥰",
    "😢": "😢",
    "👏": "👏",
    "clap": "👏",
    "😁": "😁",
    "🤔": "🤔",
    "🎉": "🎉",
    "🤯": "🤯",
    "😱": "😱",
    "🤬": "🤬",
    "💩": "💩",
}


class LikesWorker:
    """
    Worker for executing likes (reactions) tasks.

    Handles:
    - Sending reactions to posts
    - Flood wait handling
    - Error recovery
    - Progress reporting
    """

    def __init__(
        self,
        task_id: int,
        on_progress: Optional[Callable[[int, int, int, str], Any]] = None,
    ):
        self.task_id = task_id
        self.on_progress = on_progress  # (task_id, completed, total, message)

    async def execute(
        self,
        cancel_event: asyncio.Event,
        pause_event: asyncio.Event,
    ):
        """
        Execute the likes task.

        Args:
            cancel_event: Event to signal cancellation
            pause_event: Event to signal pause (cleared = paused)
        """
        db = SessionLocal()
        try:
            # Load task
            task = db.query(Task).filter(Task.id == self.task_id).first()
            if not task:
                logger.error(f"Task {self.task_id} not found")
                return

            # Update status
            task.status = "running"
            task.started_at = datetime.utcnow()
            db.commit()

            # Get accounts
            accounts = list(task.accounts)
            if not accounts:
                task.status = "failed"
                task.last_error = "No accounts assigned to task"
                db.commit()
                return

            # Parse config
            config = task.config
            channel = config.get("channel", "")
            post_id = config.get("post_id")
            reaction = config.get("reaction", "👍")

            # Normalize reaction
            reaction = REACTIONS_MAP.get(reaction, reaction)

            logger.info(
                f"Starting likes task {self.task_id}: "
                f"channel={channel}, post_id={post_id}, reaction={reaction}, "
                f"accounts={len(accounts)}, total={task.total_actions}"
            )

            # Execute reactions
            completed = task.completed_actions
            failed = task.failed_actions

            # Round-robin through accounts
            account_index = 0

            while completed + failed < task.total_actions:
                # Check cancel
                if cancel_event.is_set():
                    task.status = "cancelled"
                    task.completed_at = datetime.utcnow()
                    db.commit()
                    logger.info(f"Task {self.task_id} cancelled")
                    return

                # Check pause
                await pause_event.wait()

                # Get next account
                account = accounts[account_index % len(accounts)]
                account_index += 1

                # Execute single reaction
                success, message, error = await self._send_reaction(
                    account=account,
                    channel=channel,
                    post_id=post_id,
                    reaction=reaction,
                    db=db
                )

                # Log the action
                log = TaskLog(
                    task_id=self.task_id,
                    account_id=account.id,
                    action_type="reaction",
                    target=f"{channel}/{post_id}" if post_id else channel,
                    success=success,
                    message=message,
                    error=error,
                    extra_data={"reaction": reaction}
                )
                db.add(log)

                if success:
                    completed += 1
                    task.completed_actions = completed
                else:
                    failed += 1
                    task.failed_actions = failed
                    if error:
                        task.last_error = error

                db.commit()

                # Progress callback
                if self.on_progress:
                    try:
                        await self.on_progress(
                            self.task_id,
                            completed,
                            task.total_actions,
                            message or error or ""
                        )
                    except Exception as e:
                        logger.warning(f"Progress callback error: {e}")

                # Delay between actions
                if completed + failed < task.total_actions:
                    delay = random.uniform(task.min_delay, task.max_delay)
                    logger.debug(f"Waiting {delay:.1f}s before next action")
                    await asyncio.sleep(delay)

            # Task completed
            task.status = "completed"
            task.completed_at = datetime.utcnow()
            db.commit()

            logger.info(
                f"Task {self.task_id} completed: "
                f"success={completed}, failed={failed}"
            )

        except Exception as e:
            logger.exception(f"Task {self.task_id} failed with error: {e}")
            try:
                task = db.query(Task).filter(Task.id == self.task_id).first()
                if task:
                    task.status = "failed"
                    task.last_error = str(e)
                    task.completed_at = datetime.utcnow()
                    db.commit()
            except:
                pass
        finally:
            db.close()

    async def _send_reaction(
        self,
        account: Account,
        channel: str,
        post_id: Optional[int],
        reaction: str,
        db: Session,
    ) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Send a reaction using an account.

        Returns:
            (success, message, error)
        """
        if not account.session_string:
            return False, None, "No session string"

        # Get proxy config
        proxy = None
        if account.proxy:
            proxy = {
                "type": account.proxy.type,
                "host": account.proxy.host,
                "port": account.proxy.port,
                "username": account.proxy.username,
                "password": account.proxy.password,
            }

        try:
            client = BaseClient(
                session_string=account.session_string,
                proxy=proxy,
                connection_retries=3,
                timeout=15,
            )

            async with client:
                # Check authorization
                await client.check_auth()

                # Resolve channel
                try:
                    entity = await client.client.get_entity(channel)
                except Exception as e:
                    return False, None, f"Cannot resolve channel: {e}"

                # Get the message/post to react to
                if post_id:
                    msg_id = post_id
                else:
                    # Get the latest post
                    async for msg in client.client.iter_messages(entity, limit=1):
                        msg_id = msg.id
                        break
                    else:
                        return False, None, "No messages found in channel"

                # Send reaction
                from telethon.tl.functions.messages import SendReactionRequest
                from telethon.tl.types import ReactionEmoji

                await client.client(SendReactionRequest(
                    peer=entity,
                    msg_id=msg_id,
                    reaction=[ReactionEmoji(emoticon=reaction)]
                ))

                # Update account last_used
                account.last_used_at = datetime.utcnow()
                db.commit()

                return True, f"Reaction {reaction} sent to {channel}/{msg_id}", None

        except FloodWaitError as e:
            logger.warning(f"FloodWait for {e.seconds}s on account {account.id}")
            # Wait for flood
            await asyncio.sleep(min(e.seconds, 300))  # Max 5 min wait
            return False, None, f"FloodWait: {e.seconds}s"

        except ReactionInvalidError:
            return False, None, "Invalid reaction emoji"

        except (ChatWriteForbiddenError, UserBannedInChannelError):
            return False, None, "Account cannot react in this channel"

        except ChannelPrivateError:
            return False, None, "Channel is private"

        except MsgIdInvalidError:
            return False, None, "Invalid message ID"

        except Exception as e:
            logger.exception(f"Error sending reaction: {e}")
            return False, None, str(e)


async def start_likes_task(task_id: int, on_progress: Optional[Callable] = None):
    """
    Helper function to start a likes task.

    Args:
        task_id: The task ID
        on_progress: Optional progress callback (task_id, completed, total, message)
    """
    from workers.task_queue import task_queue

    worker = LikesWorker(task_id=task_id, on_progress=on_progress)

    await task_queue.submit(
        task_id=task_id,
        worker_coro=worker.execute
    )
