"""
Comments Worker - Executes commenting tasks using Telethon.

Features:
- Channel subscription/joining
- Post monitoring
- Spintax comment generation
- Multiple account rotation modes
"""

import asyncio
import random
import logging
from datetime import datetime
from typing import List, Dict, Optional, Callable, Any, Set

from sqlalchemy.orm import Session
from telethon.errors import (
    FloodWaitError,
    ChatWriteForbiddenError,
    ChannelPrivateError,
    UserBannedInChannelError,
    MsgIdInvalidError,
    ChatAdminRequiredError,
    UserNotParticipantError,
    SlowModeWaitError,
)
from telethon.tl.types import Channel, Chat, InputPeerChannel
from telethon.tl.functions.channels import JoinChannelRequest, GetFullChannelRequest
from telethon.tl.functions.messages import GetDiscussionMessageRequest

from database.database import SessionLocal
from database.models import Task, TaskLog, Account, TargetChannel, CommentTemplate
from telegram.client import BaseClient
from workers.spintax import parse_spintax, DEFAULT_COMMENT_TEMPLATES

logger = logging.getLogger(__name__)


class CommentsWorker:
    """
    Worker for executing commenting tasks.

    Supports:
    - Multiple channels monitoring
    - Account rotation (random, round-robin)
    - Spintax comment generation
    - Automatic channel joining
    """

    def __init__(
        self,
        task_id: int,
        on_progress: Optional[Callable[[int, int, int, str], Any]] = None,
    ):
        self.task_id = task_id
        self.on_progress = on_progress
        self._used_accounts: Set[int] = set()
        self._account_comment_count: Dict[int, int] = {}

    async def execute(
        self,
        cancel_event: asyncio.Event,
        pause_event: asyncio.Event,
    ):
        """Execute the comments task."""
        db = SessionLocal()
        try:
            task = db.query(Task).filter(Task.id == self.task_id).first()
            if not task:
                logger.error(f"Task {self.task_id} not found")
                return

            task.status = "running"
            task.started_at = datetime.utcnow()
            db.commit()

            accounts = list(task.accounts)
            if not accounts:
                task.status = "failed"
                task.last_error = "No accounts assigned to task"
                db.commit()
                return

            config = task.config
            channels = config.get("channels", [])
            comment_templates = config.get("templates", [])
            rotation_mode = config.get("rotation_mode", "random")  # random, round_robin
            comments_per_account = config.get("comments_per_account", 10)
            mode = config.get("mode", "single")  # single, monitoring

            if not channels:
                task.status = "failed"
                task.last_error = "No target channels specified"
                db.commit()
                return

            # Use default templates if none provided
            if not comment_templates:
                comment_templates = [t["content"] for t in DEFAULT_COMMENT_TEMPLATES]

            logger.info(
                f"Starting comments task {self.task_id}: "
                f"channels={len(channels)}, accounts={len(accounts)}, "
                f"mode={mode}, rotation={rotation_mode}"
            )

            # Initialize target channels in DB
            target_channels = await self._init_target_channels(db, task, channels)

            # Join channels with first valid account
            await self._join_channels(db, task, accounts[0], target_channels)

            completed = task.completed_actions
            failed = task.failed_actions
            account_index = 0

            while completed + failed < task.total_actions:
                if cancel_event.is_set():
                    task.status = "cancelled"
                    task.completed_at = datetime.utcnow()
                    db.commit()
                    return

                await pause_event.wait()

                # Select account based on rotation mode
                account = self._select_account(
                    accounts, rotation_mode, comments_per_account, account_index
                )
                account_index += 1

                if not account:
                    logger.warning("All accounts exhausted comment limit")
                    break

                # Select target channel
                target = self._select_target_channel(target_channels)
                if not target:
                    logger.warning("No valid target channels")
                    break

                # Generate comment from template
                template = random.choice(comment_templates)
                comment_text = parse_spintax(template)

                # Send comment
                success, message, error = await self._send_comment(
                    account=account,
                    channel=target.channel_username,
                    comment=comment_text,
                    db=db
                )

                # Log action
                log = TaskLog(
                    task_id=self.task_id,
                    account_id=account.id,
                    action_type="comment",
                    target=target.channel_username,
                    success=success,
                    message=message,
                    error=error,
                    extra_data={"comment": comment_text[:100]}
                )
                db.add(log)

                if success:
                    completed += 1
                    task.completed_actions = completed
                    target.comments_sent += 1
                    self._account_comment_count[account.id] = \
                        self._account_comment_count.get(account.id, 0) + 1
                else:
                    failed += 1
                    task.failed_actions = failed
                    if error:
                        task.last_error = error

                db.commit()

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

                # Delay
                if completed + failed < task.total_actions:
                    delay = random.uniform(task.min_delay, task.max_delay)
                    await asyncio.sleep(delay)

            task.status = "completed"
            task.completed_at = datetime.utcnow()
            db.commit()

            logger.info(f"Task {self.task_id} completed: success={completed}, failed={failed}")

        except Exception as e:
            logger.exception(f"Task {self.task_id} failed: {e}")
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

    async def _init_target_channels(
        self, db: Session, task: Task, channels: List[str]
    ) -> List[TargetChannel]:
        """Initialize target channels in database."""
        targets = []
        for channel in channels:
            # Normalize channel name
            if channel.startswith("https://t.me/"):
                channel = "@" + channel.replace("https://t.me/", "").split("/")[0]
            elif not channel.startswith("@"):
                channel = "@" + channel

            existing = db.query(TargetChannel).filter(
                TargetChannel.task_id == task.id,
                TargetChannel.channel_username == channel
            ).first()

            if existing:
                targets.append(existing)
            else:
                target = TargetChannel(
                    task_id=task.id,
                    channel_username=channel
                )
                db.add(target)
                targets.append(target)

        db.commit()
        return targets

    async def _join_channels(
        self,
        db: Session,
        task: Task,
        account: Account,
        targets: List[TargetChannel]
    ):
        """Join target channels and check commenting ability."""
        if not account.session_string:
            return

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
                await client.check_auth()

                for target in targets:
                    try:
                        entity = await client.client.get_entity(target.channel_username)
                        target.channel_id = entity.id
                        target.channel_title = getattr(entity, 'title', None)

                        # Try to join if not already member
                        try:
                            await client.client(JoinChannelRequest(entity))
                        except Exception:
                            pass  # Already member or can't join

                        # Check if channel has discussion group (comments enabled)
                        try:
                            full = await client.client(GetFullChannelRequest(entity))
                            if full.full_chat.linked_chat_id:
                                target.can_comment = True
                                target.status = "joined"
                            else:
                                target.can_comment = False
                                target.status = "cannot_comment"
                                target.error_message = "No discussion group linked"
                        except Exception as e:
                            target.can_comment = False
                            target.status = "error"
                            target.error_message = str(e)

                    except ChannelPrivateError:
                        target.status = "error"
                        target.error_message = "Channel is private"
                    except Exception as e:
                        target.status = "error"
                        target.error_message = str(e)

                db.commit()

        except Exception as e:
            logger.exception(f"Failed to join channels: {e}")

    def _select_account(
        self,
        accounts: List[Account],
        mode: str,
        limit: int,
        index: int
    ) -> Optional[Account]:
        """Select next account based on rotation mode."""
        available = [
            a for a in accounts
            if self._account_comment_count.get(a.id, 0) < limit
        ]

        if not available:
            return None

        if mode == "round_robin":
            return available[index % len(available)]
        else:  # random
            return random.choice(available)

    def _select_target_channel(self, targets: List[TargetChannel]) -> Optional[TargetChannel]:
        """Select a target channel that can receive comments."""
        valid = [t for t in targets if t.can_comment and t.status == "joined"]
        if not valid:
            return None
        return random.choice(valid)

    async def _send_comment(
        self,
        account: Account,
        channel: str,
        comment: str,
        db: Session,
    ) -> tuple[bool, Optional[str], Optional[str]]:
        """Send a comment to the latest post in a channel."""
        if not account.session_string:
            return False, None, "No session string"

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
                await client.check_auth()

                # Get channel entity
                entity = await client.client.get_entity(channel)

                # Get latest post
                async for msg in client.client.iter_messages(entity, limit=1):
                    post_id = msg.id
                    break
                else:
                    return False, None, "No posts in channel"

                # Get discussion message (the post in the linked group)
                try:
                    discussion = await client.client(GetDiscussionMessageRequest(
                        peer=entity,
                        msg_id=post_id
                    ))

                    # Send reply to discussion
                    if discussion.messages:
                        disc_msg = discussion.messages[0]
                        await client.client.send_message(
                            entity=disc_msg.peer_id,
                            message=comment,
                            reply_to=disc_msg.id
                        )

                        account.last_used_at = datetime.utcnow()
                        db.commit()

                        return True, f"Comment sent to {channel}/{post_id}", None

                except Exception as e:
                    return False, None, f"Cannot comment: {e}"

        except FloodWaitError as e:
            await asyncio.sleep(min(e.seconds, 300))
            return False, None, f"FloodWait: {e.seconds}s"

        except SlowModeWaitError as e:
            return False, None, f"Slow mode: wait {e.seconds}s"

        except (ChatWriteForbiddenError, UserBannedInChannelError):
            return False, None, "Cannot comment in this channel"

        except UserNotParticipantError:
            return False, None, "Not a member of discussion group"

        except Exception as e:
            logger.exception(f"Error sending comment: {e}")
            return False, None, str(e)


async def start_comments_task(task_id: int, on_progress: Optional[Callable] = None):
    """Helper function to start a comments task."""
    from workers.task_queue import task_queue

    worker = CommentsWorker(task_id=task_id, on_progress=on_progress)

    await task_queue.submit(
        task_id=task_id,
        worker_coro=worker.execute
    )
