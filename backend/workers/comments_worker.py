"""
Comments Worker - Executes commenting tasks using Telethon.

Features:
- Error classification with SendStatus/SendResult
- Account blacklist per channel
- Comment history tracking
- AI comment generation (OpenAI-compatible)
- Spintax fallback
- Monitoring mode (real-time new post watching)
- Discussion group auto-join with cache
- Multiple account rotation modes
"""

import asyncio
import random
import logging
from datetime import datetime
from typing import List, Dict, Optional, Callable, Any, Set, Tuple

from sqlalchemy.orm import Session
from telethon import events
from telethon.tl.functions.channels import JoinChannelRequest, GetFullChannelRequest
from telethon.tl.functions.messages import GetDiscussionMessageRequest

from database.database import SessionLocal
from database.models import (
    Task, TaskLog, Account, TargetChannel, CommentTemplate,
    AccountBlacklist, CommentHistory, AIPromptTemplate,
)
from telegram.client import BaseClient
from workers.spintax import parse_spintax, DEFAULT_COMMENT_TEMPLATES
from workers.shared import SendStatus, SendResult, ErrorClassifier
from workers.shared.ai_service import AIService

logger = logging.getLogger(__name__)

# Statuses that indicate an account should be skipped
SKIP_ACCOUNT_STATUSES = {"banned", "spamblock", "session_expired", "invalid", "deactivated"}


class CommentsWorker:
    """
    Worker for executing commenting tasks.

    Supports:
    - Multiple channels monitoring
    - Account rotation (random, round-robin)
    - Spintax + AI comment generation
    - Automatic channel/discussion group joining
    - Error classification and auto-blacklisting
    - Comment history
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
        self._linked_chat_cache: Dict[int, Optional[int]] = {}
        self._ai_service: Optional[AIService] = None
        # In-memory blacklist cache: set of (account_id, channel_key) tuples
        self._blacklist_cache: Set[Tuple[int, str]] = set()

    def _init_ai_service(self, config: dict) -> None:
        """Initialize AI service from task config if enabled."""
        if not config.get("ai_enabled"):
            return
        api_key = config.get("ai_api_key", "")
        if not api_key:
            logger.warning("AI enabled but no API key provided, falling back to spintax")
            return
        self._ai_service = AIService(
            api_key=api_key,
            model=config.get("ai_model", "gpt-4o-mini"),
            base_url=config.get("ai_base_url", "https://api.openai.com/v1"),
        )

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
            rotation_mode = config.get("rotation_mode", "random")
            comments_per_account = config.get("comments_per_account", 10)
            mode = config.get("mode", "single")

            if not channels:
                task.status = "failed"
                task.last_error = "No target channels specified"
                db.commit()
                return

            # Use default templates if none provided
            if not comment_templates:
                comment_templates = [t["content"] for t in DEFAULT_COMMENT_TEMPLATES]

            # Initialize AI service
            self._init_ai_service(config)

            # Pre-load blacklist cache (1 SQL query instead of N*M)
            self._load_blacklist_cache(db, [a.id for a in accounts])

            logger.info(
                f"Starting comments task {self.task_id}: "
                f"channels={len(channels)}, accounts={len(accounts)}, "
                f"mode={mode}, rotation={rotation_mode}, "
                f"ai={'on' if self._ai_service else 'off'}"
            )

            # Initialize target channels in DB
            target_channels = await self._init_target_channels(db, task, channels)

            # Join channels with first valid account
            await self._join_channels(db, task, accounts[0], target_channels)

            # Monitoring mode — delegate
            if mode == "monitoring":
                await self._execute_monitoring(
                    db, task, accounts, target_channels, config,
                    comment_templates, cancel_event, pause_event
                )
                return

            # Single (batch) mode
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

                # Select account based on rotation mode (with blacklist)
                target = self._select_target_channel(target_channels)
                if not target:
                    logger.warning("No valid target channels remaining")
                    break

                account = self._select_account(
                    db, accounts, rotation_mode, comments_per_account,
                    account_index, target.channel_id, target.channel_username
                )
                account_index += 1

                if not account:
                    logger.warning("All accounts exhausted or blacklisted")
                    break

                # Generate comment
                comment_text, is_ai = await self._generate_comment(
                    config, comment_templates, db,
                    post_text="", channel_title=target.channel_title or target.channel_username
                )

                # Send comment
                result = await self._send_comment(
                    account=account,
                    target=target,
                    comment=comment_text,
                    db=db,
                )

                # Handle result
                self._handle_send_result(db, account, target, result)

                # Log action
                log = TaskLog(
                    task_id=self.task_id,
                    account_id=account.id,
                    action_type="comment",
                    target=target.channel_username,
                    success=result.success,
                    message=result.message,
                    error=result.error if not result.success else None,
                    extra_data={"comment": comment_text[:100], "status": result.status.value}
                )
                db.add(log)

                # Save comment history
                self._save_comment_history(
                    db, account, target, self.task_id,
                    comment_text=comment_text,
                    post_id=None,
                    comment_id=getattr(result.sent_message, 'id', None) if result.sent_message else None,
                    success=result.success,
                    error_message=result.error if not result.success else None,
                    ai_generated=is_ai,
                    ai_model=config.get("ai_model") if is_ai else None,
                )

                if result.success:
                    completed += 1
                    task.completed_actions = completed
                    target.comments_sent += 1
                    self._account_comment_count[account.id] = \
                        self._account_comment_count.get(account.id, 0) + 1
                else:
                    failed += 1
                    task.failed_actions = failed
                    if result.error:
                        task.last_error = result.error

                    # FLOOD_WAIT — sleep
                    if result.status == SendStatus.FLOOD_WAIT and result.wait_seconds:
                        wait = min(result.wait_seconds, 300)
                        logger.info(f"Flood wait: sleeping {wait}s")
                        await asyncio.sleep(wait)

                db.commit()

                if self.on_progress:
                    try:
                        await self.on_progress(
                            self.task_id,
                            completed,
                            task.total_actions,
                            result.message or result.error or ""
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
            except Exception:
                pass
        finally:
            if self._ai_service:
                await self._ai_service.close()
            db.close()

    # ============ Monitoring Mode ============

    async def _execute_monitoring(
        self,
        db: Session,
        task: Task,
        accounts: List[Account],
        targets: List[TargetChannel],
        config: dict,
        comment_templates: List[str],
        cancel_event: asyncio.Event,
        pause_event: asyncio.Event,
    ):
        """Execute in monitoring mode — watch for new posts and comment in real-time."""
        valid_targets = [t for t in targets if t.can_comment and t.status == "joined"]
        if not valid_targets:
            task.status = "failed"
            task.last_error = "No commentable channels found"
            db.commit()
            return

        # Use first available account for monitoring
        monitor_account = next(
            (a for a in accounts if a.session_string and a.status not in SKIP_ACCOUNT_STATUSES),
            None
        )
        if not monitor_account:
            task.status = "failed"
            task.last_error = "No valid accounts for monitoring"
            db.commit()
            return

        proxy = self._get_proxy_dict(monitor_account)
        device_fp = monitor_account.device_fingerprint or {}

        try:
            client = BaseClient(
                session_string=monitor_account.session_string,
                api_id=monitor_account.api_id,
                api_hash=monitor_account.api_hash,
                proxy=proxy,
                connection_retries=3,
                timeout=15,
                device_model=device_fp.get("device_model"),
                system_version=device_fp.get("system_version"),
                app_version=device_fp.get("app_version"),
                lang_code=device_fp.get("lang_code"),
                system_lang_code=device_fp.get("system_lang_code"),
                unique_id=monitor_account.phone or str(monitor_account.telegram_id),
            )

            async with client:
                await client.check_auth()

                # Resolve channel entities and join discussion groups
                channel_entities = []
                for target in valid_targets:
                    try:
                        entity = await client.client.get_entity(target.channel_username)
                        channel_entities.append(entity)
                        await self._join_discussion_group(client, entity, target)
                    except Exception as e:
                        logger.warning(f"Cannot resolve {target.channel_username}: {e}")

                if not channel_entities:
                    task.status = "failed"
                    task.last_error = "Failed to resolve any channels"
                    db.commit()
                    return

                seen_grouped_ids: Set[int] = set()
                completed = task.completed_actions
                rotation_mode = config.get("rotation_mode", "random")
                comments_per_account = config.get("comments_per_account", 10)
                account_index = 0

                @client.client.on(events.NewMessage(chats=channel_entities))
                async def handler(event):
                    nonlocal completed, account_index

                    if cancel_event.is_set():
                        return

                    # Skip megagroup posts (these are comments, not channel posts)
                    if event.is_group:
                        return

                    # Skip grouped_id duplicates (album posts)
                    if event.grouped_id:
                        if event.grouped_id in seen_grouped_ids:
                            return
                        seen_grouped_ids.add(event.grouped_id)

                    post_text = event.text or ""

                    # Check if we should comment on this post
                    if not self._should_comment(post_text, config):
                        return

                    await pause_event.wait()

                    # Get channel info
                    chat = await event.get_chat()
                    channel_title = getattr(chat, 'title', '')
                    channel_username = getattr(chat, 'username', '')
                    if channel_username:
                        channel_username = f"@{channel_username}"

                    # Select a commenting account (different from monitor)
                    commenting_accounts = [a for a in accounts if a.id != monitor_account.id]
                    if not commenting_accounts:
                        commenting_accounts = accounts

                    target_obj = next(
                        (t for t in valid_targets if t.channel_id == chat.id),
                        valid_targets[0] if valid_targets else None,
                    )

                    commenting_account = self._select_account(
                        db, commenting_accounts, rotation_mode, comments_per_account,
                        account_index, chat.id, channel_username
                    )
                    account_index += 1

                    if not commenting_account:
                        logger.warning("No available account for commenting")
                        return

                    # Generate comment
                    comment_text, is_ai = await self._generate_comment(
                        config, comment_templates, db,
                        post_text=post_text, channel_title=channel_title
                    )

                    # Random delay before commenting
                    delay = random.uniform(task.min_delay, task.max_delay)
                    await asyncio.sleep(delay)

                    # Send comment using the commenting account
                    result = await self._send_comment_with_account(
                        account=commenting_account,
                        channel_entity_id=chat.id,
                        channel_username=channel_username,
                        post_id=event.id,
                        comment=comment_text,
                        db=db,
                    )

                    # Handle result
                    if target_obj:
                        self._handle_send_result(db, commenting_account, target_obj, result)

                    # Save history
                    self._save_comment_history(
                        db, commenting_account, target_obj, self.task_id,
                        comment_text=comment_text,
                        post_id=event.id,
                        post_text=post_text[:500],
                        comment_id=getattr(result.sent_message, 'id', None) if result.sent_message else None,
                        success=result.success,
                        error_message=result.error if not result.success else None,
                        ai_generated=is_ai,
                        ai_model=config.get("ai_model") if is_ai else None,
                    )

                    if result.success:
                        completed += 1
                        task.completed_actions = completed
                        if target_obj:
                            target_obj.comments_sent += 1
                        self._account_comment_count[commenting_account.id] = \
                            self._account_comment_count.get(commenting_account.id, 0) + 1

                    # Log
                    log = TaskLog(
                        task_id=self.task_id,
                        account_id=commenting_account.id,
                        action_type="comment",
                        target=channel_username,
                        success=result.success,
                        message=result.message,
                        error=result.error if not result.success else None,
                        extra_data={
                            "comment": comment_text[:100],
                            "post_id": event.id,
                            "status": result.status.value,
                            "mode": "monitoring",
                        }
                    )
                    db.add(log)
                    db.commit()

                    if self.on_progress:
                        try:
                            await self.on_progress(
                                self.task_id, completed, task.total_actions,
                                result.message or result.error or ""
                            )
                        except Exception as e:
                            logger.warning(f"Progress callback error: {e}")

                    # Check limit
                    if task.total_actions > 0 and completed >= task.total_actions:
                        cancel_event.set()

                # Wait until cancelled or limit reached
                logger.info(f"Task {self.task_id}: monitoring {len(channel_entities)} channels")
                while not cancel_event.is_set():
                    await asyncio.sleep(1)

                task.status = "completed" if completed > 0 else "cancelled"
                task.completed_at = datetime.utcnow()
                db.commit()
                logger.info(f"Task {self.task_id} monitoring ended: {completed} comments sent")

        except Exception as e:
            logger.exception(f"Monitoring error: {e}")
            task.status = "failed"
            task.last_error = str(e)
            task.completed_at = datetime.utcnow()
            db.commit()

    # ============ Channel Management ============

    async def _init_target_channels(
        self, db: Session, task: Task, channels: List[str]
    ) -> List[TargetChannel]:
        """Initialize target channels in database."""
        targets = []
        for channel in channels:
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

        proxy = self._get_proxy_dict(account)
        device_fp = account.device_fingerprint or {}

        try:
            client = BaseClient(
                session_string=account.session_string,
                api_id=account.api_id,
                api_hash=account.api_hash,
                proxy=proxy,
                connection_retries=3,
                timeout=15,
                device_model=device_fp.get("device_model"),
                system_version=device_fp.get("system_version"),
                app_version=device_fp.get("app_version"),
                lang_code=device_fp.get("lang_code"),
                system_lang_code=device_fp.get("system_lang_code"),
                unique_id=account.phone or str(account.telegram_id),
            )

            async with client:
                await client.check_auth()

                for target in targets:
                    try:
                        entity = await client.client.get_entity(target.channel_username)
                        target.channel_id = entity.id
                        target.channel_title = getattr(entity, 'title', None)

                        try:
                            await client.client(JoinChannelRequest(entity))
                        except Exception:
                            pass

                        # Check discussion group and join it
                        await self._join_discussion_group(client, entity, target)

                    except Exception as e:
                        result = ErrorClassifier.classify(e)
                        target.status = "error"
                        target.error_message = result.message
                        target.can_comment = False

                db.commit()

        except Exception as e:
            logger.exception(f"Failed to join channels: {e}")

    async def _join_discussion_group(
        self, client: BaseClient, entity, target: TargetChannel
    ):
        """Check for discussion group and join it."""
        try:
            full = await client.client(GetFullChannelRequest(entity))
            linked_chat_id = full.full_chat.linked_chat_id
            self._linked_chat_cache[entity.id] = linked_chat_id

            if linked_chat_id:
                target.can_comment = True
                target.status = "joined"

                # Try to join the discussion group
                try:
                    await client.client(JoinChannelRequest(linked_chat_id))
                except Exception:
                    pass  # Already member or can't join
            else:
                target.can_comment = False
                target.status = "cannot_comment"
                target.error_message = "No discussion group linked"
        except Exception as e:
            target.can_comment = False
            target.status = "error"
            target.error_message = str(e)

    # ============ Account Selection ============

    def _load_blacklist_cache(self, db: Session, account_ids: List[int]) -> None:
        """Pre-load blacklist entries into memory cache (1 query instead of N*M)."""
        entries = db.query(
            AccountBlacklist.account_id,
            AccountBlacklist.channel_id,
            AccountBlacklist.channel_username,
        ).filter(AccountBlacklist.account_id.in_(account_ids)).all()

        for account_id, channel_id, channel_username in entries:
            if channel_id:
                self._blacklist_cache.add((account_id, f"id:{channel_id}"))
            if channel_username:
                self._blacklist_cache.add((account_id, f"un:{channel_username}"))

    def _is_blacklisted_cached(
        self, account_id: int, channel_id: Optional[int], channel_username: Optional[str]
    ) -> bool:
        """Check blacklist using in-memory cache (O(1) lookup)."""
        if channel_id and (account_id, f"id:{channel_id}") in self._blacklist_cache:
            return True
        if channel_username and (account_id, f"un:{channel_username}") in self._blacklist_cache:
            return True
        return False

    def _add_to_blacklist_cache(
        self, account_id: int, channel_id: Optional[int], channel_username: Optional[str]
    ) -> None:
        """Add entry to in-memory blacklist cache."""
        if channel_id:
            self._blacklist_cache.add((account_id, f"id:{channel_id}"))
        if channel_username:
            self._blacklist_cache.add((account_id, f"un:{channel_username}"))

    def _select_account(
        self,
        db: Session,
        accounts: List[Account],
        mode: str,
        limit: int,
        index: int,
        channel_id: Optional[int] = None,
        channel_username: Optional[str] = None,
    ) -> Optional[Account]:
        """Select next account with blacklist filtering (uses in-memory cache)."""
        available = []
        for a in accounts:
            # Skip exhausted accounts
            if self._account_comment_count.get(a.id, 0) >= limit:
                continue
            # Skip accounts with bad status
            if a.status in SKIP_ACCOUNT_STATUSES:
                continue
            # Skip blacklisted accounts (O(1) cache lookup)
            if self._is_blacklisted_cached(a.id, channel_id, channel_username):
                continue
            available.append(a)

        if not available:
            return None

        if mode == "round_robin":
            return available[index % len(available)]
        else:
            return random.choice(available)

    def _select_target_channel(self, targets: List[TargetChannel]) -> Optional[TargetChannel]:
        """Select a target channel that can receive comments."""
        valid = [t for t in targets if t.can_comment and t.status == "joined"]
        if not valid:
            return None
        return random.choice(valid)

    # ============ Comment Generation ============

    async def _generate_comment(
        self,
        config: dict,
        templates: List[str],
        db: Session,
        post_text: str = "",
        channel_title: str = "",
    ) -> Tuple[str, bool]:
        """
        Generate a comment.

        Returns:
            (comment_text, is_ai_generated)
        """
        # AI generation
        if self._ai_service:
            prompt_template = None
            prompt_id = config.get("ai_prompt_id")
            if prompt_id:
                prompt = db.query(AIPromptTemplate).filter(AIPromptTemplate.id == prompt_id).first()
                if prompt:
                    prompt_template = prompt.prompt_template

            ai_comment = await self._ai_service.generate_comment(
                post_text=post_text,
                channel_title=channel_title,
                prompt_template=prompt_template,
                temperature=config.get("ai_temperature", 0.7),
                max_tokens=config.get("ai_max_tokens", 200),
            )
            if ai_comment:
                return ai_comment, True

            logger.warning("AI generation failed, falling back to spintax")

        # Spintax fallback
        template = random.choice(templates)
        return parse_spintax(template), False

    def _should_comment(self, post_text: str, config: dict) -> bool:
        """Decide whether to comment on a post based on config."""
        comment_mode = config.get("comment_mode", "all")

        if comment_mode == "all":
            return True

        if comment_mode == "random":
            probability = config.get("comment_probability", 0.5)
            return random.random() < probability

        if comment_mode == "keywords":
            keywords = config.get("keywords", [])
            if not keywords:
                return True
            text_lower = post_text.lower()
            return any(kw.lower() in text_lower for kw in keywords)

        return True

    # ============ Send Comment ============

    async def _send_comment(
        self,
        account: Account,
        target: TargetChannel,
        comment: str,
        db: Session,
    ) -> SendResult:
        """Send a comment to the latest post in a channel."""
        if not account.session_string:
            return SendResult(
                status=SendStatus.ERROR,
                message="No session string",
                error="No session string",
            )

        proxy = self._get_proxy_dict(account)
        device_fp = account.device_fingerprint or {}

        try:
            client = BaseClient(
                session_string=account.session_string,
                api_id=account.api_id,
                api_hash=account.api_hash,
                proxy=proxy,
                connection_retries=3,
                timeout=15,
                device_model=device_fp.get("device_model"),
                system_version=device_fp.get("system_version"),
                app_version=device_fp.get("app_version"),
                lang_code=device_fp.get("lang_code"),
                system_lang_code=device_fp.get("system_lang_code"),
                unique_id=account.phone or str(account.telegram_id),
            )

            async with client:
                await client.check_auth()

                entity = await client.client.get_entity(target.channel_username)

                # Get latest post
                post_id = None
                async for msg in client.client.iter_messages(entity, limit=1):
                    post_id = msg.id
                    break

                if not post_id:
                    return SendResult(
                        status=SendStatus.SKIP,
                        message="No posts in channel",
                        entity_id=target.channel_id,
                        entity_title=target.channel_title,
                    )

                # Get discussion message
                discussion = await client.client(GetDiscussionMessageRequest(
                    peer=entity,
                    msg_id=post_id
                ))

                if discussion.messages:
                    disc_msg = discussion.messages[0]
                    sent = await client.client.send_message(
                        entity=disc_msg.peer_id,
                        message=comment,
                        reply_to=disc_msg.id
                    )

                    account.last_used_at = datetime.utcnow()
                    db.commit()

                    return SendResult(
                        status=SendStatus.OK,
                        message=f"Comment sent to {target.channel_username}/{post_id}",
                        entity_id=target.channel_id,
                        entity_title=target.channel_title,
                        sent_message=sent,
                    )

                return SendResult(
                    status=SendStatus.SKIP,
                    message="No discussion messages found",
                    entity_id=target.channel_id,
                    entity_title=target.channel_title,
                )

        except Exception as e:
            result = ErrorClassifier.classify(e)
            result.entity_id = target.channel_id
            result.entity_title = target.channel_title
            return result

    async def _send_comment_with_account(
        self,
        account: Account,
        channel_entity_id: int,
        channel_username: str,
        post_id: int,
        comment: str,
        db: Session,
    ) -> SendResult:
        """Send a comment to a specific post using a specific account (for monitoring mode)."""
        if not account.session_string:
            return SendResult(
                status=SendStatus.ERROR,
                message="No session string",
                error="No session string",
            )

        proxy = self._get_proxy_dict(account)
        device_fp = account.device_fingerprint or {}

        try:
            client = BaseClient(
                session_string=account.session_string,
                api_id=account.api_id,
                api_hash=account.api_hash,
                proxy=proxy,
                connection_retries=3,
                timeout=15,
                device_model=device_fp.get("device_model"),
                system_version=device_fp.get("system_version"),
                app_version=device_fp.get("app_version"),
                lang_code=device_fp.get("lang_code"),
                system_lang_code=device_fp.get("system_lang_code"),
                unique_id=account.phone or str(account.telegram_id),
            )

            async with client:
                await client.check_auth()

                entity = await client.client.get_entity(channel_entity_id)

                # Get discussion message for this specific post
                discussion = await client.client(GetDiscussionMessageRequest(
                    peer=entity,
                    msg_id=post_id
                ))

                if discussion.messages:
                    disc_msg = discussion.messages[0]
                    sent = await client.client.send_message(
                        entity=disc_msg.peer_id,
                        message=comment,
                        reply_to=disc_msg.id
                    )

                    account.last_used_at = datetime.utcnow()
                    db.commit()

                    return SendResult(
                        status=SendStatus.OK,
                        message=f"Comment sent to {channel_username}/{post_id}",
                        entity_id=channel_entity_id,
                        entity_title=channel_username,
                        sent_message=sent,
                    )

                return SendResult(
                    status=SendStatus.SKIP,
                    message="No discussion messages found",
                    entity_id=channel_entity_id,
                    entity_title=channel_username,
                )

        except Exception as e:
            result = ErrorClassifier.classify(e)
            result.entity_id = channel_entity_id
            result.entity_title = channel_username
            return result

    # ============ Result Handling ============

    def _handle_send_result(
        self,
        db: Session,
        account: Account,
        target: TargetChannel,
        result: SendResult,
    ):
        """Handle SendResult: blacklist, update account status, etc."""
        if result.success:
            return

        # Auto-blacklist entity
        if result.status.should_blacklist_entity:
            reason = ErrorClassifier.get_blacklist_reason(result.status)
            if reason:
                AccountBlacklist.add_to_blacklist(
                    db, account.id, reason,
                    channel_id=target.channel_id,
                    channel_username=target.channel_username,
                    channel_title=target.channel_title,
                    error_message=result.error,
                )
                # Update in-memory cache
                self._add_to_blacklist_cache(
                    account.id, target.channel_id, target.channel_username
                )
                logger.info(
                    f"Blacklisted account {account.id} for {target.channel_username}: {reason}"
                )

        # Update account status for account-level errors
        if result.status.should_update_account_status:
            new_status = ErrorClassifier.get_recommended_account_status(result)
            if new_status and account.status != new_status:
                logger.warning(
                    f"Account {account.id} status: {account.status} -> {new_status} "
                    f"(reason: {result.status.value})"
                )
                account.status = new_status
                db.commit()

    # ============ History ============

    def _save_comment_history(
        self,
        db: Session,
        account: Account,
        target: Optional[TargetChannel],
        task_id: int,
        comment_text: str,
        post_id: Optional[int] = None,
        post_text: Optional[str] = None,
        comment_id: Optional[int] = None,
        success: bool = False,
        error_message: Optional[str] = None,
        ai_generated: bool = False,
        ai_model: Optional[str] = None,
    ):
        """Save a comment to history."""
        history = CommentHistory(
            account_id=account.id,
            task_id=task_id,
            channel_id=target.channel_id if target else None,
            channel_username=target.channel_username if target else None,
            channel_title=target.channel_title if target else None,
            post_id=post_id,
            comment_id=comment_id,
            comment_text=comment_text[:2000],
            post_text=post_text[:2000] if post_text else None,
            success=success,
            error_message=error_message,
            ai_generated=ai_generated,
            ai_model=ai_model,
        )
        db.add(history)

    # ============ Helpers ============

    @staticmethod
    def _get_proxy_dict(account: Account) -> Optional[dict]:
        """Get proxy dict from account."""
        if not account.proxy:
            return None
        return {
            "type": account.proxy.type,
            "host": account.proxy.host,
            "port": account.proxy.port,
            "username": account.proxy.username,
            "password": account.proxy.password,
        }


async def start_comments_task(task_id: int, on_progress: Optional[Callable] = None):
    """Helper function to start a comments task."""
    from workers.task_queue import task_queue

    worker = CommentsWorker(task_id=task_id, on_progress=on_progress)

    await task_queue.submit(
        task_id=task_id,
        worker_coro=worker.execute
    )
