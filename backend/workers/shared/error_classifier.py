"""
Error classifier for Telegram operations.

Two-phase classification:
1. By exception type (FloodWaitError -> FLOOD_WAIT, etc.)
2. By error string pattern matching

Ported from GramGPT with English messages and adaptations for Nexus.
"""

import logging
from typing import Optional, Tuple

from workers.shared.send_status import SendStatus, SendResult

logger = logging.getLogger(__name__)

# ============ Error Patterns ============

BAN_PATTERNS = [
    "USER_BANNED_IN_CHANNEL",
    "BANNED_RIGHTS",
    "You can't write in this chat",
    "you were banned",
    "banned from this",
]

ACCESS_PATTERNS = [
    "CHANNEL_PRIVATE",
    "CHAT_ADMIN_REQUIRED",
    "INVITE_HASH_EXPIRED",
    "INVITE_HASH_INVALID",
    "The channel specified is private",
    "CHAT_RESTRICTED",
    "USER_RESTRICTED",
    "PEER_ID_INVALID",
]

WRITE_FORBIDDEN_PATTERNS = [
    "CHAT_WRITE_FORBIDDEN",
    "ChatWriteForbiddenError",
    "You can't send messages in this chat",
    "CHAT_SEND_PLAIN_FORBIDDEN",
]

SKIP_PATTERNS = [
    "MSG_ID_INVALID",
    "MESSAGE_ID_INVALID",
    "CHAT_SEND_MEDIA_FORBIDDEN",
    "CHAT_SEND_PHOTOS_FORBIDDEN",
    "REACTIONS_TOO_MANY",
    "Message not found",
    "message was deleted",
]

FLOOD_PATTERNS = [
    "FLOOD_WAIT",
    "FloodWaitError",
    "Too many requests",
    "rate limit",
]

ACCOUNT_BAN_PATTERNS = [
    "USER_DEACTIVATED_BAN",
    "AUTH_KEY_UNREGISTERED",
    "Your account has been banned",
    "account was banned",
    "PHONE_NUMBER_BANNED",
]

SESSION_ERROR_PATTERNS = [
    "SESSION_REVOKED",
    "SESSION_EXPIRED",
    "AUTH_KEY_DUPLICATED",
    "USER_DEACTIVATED",
    "Could not find a matching Constructor",
    "The key is not registered",
    "session was invalidated",
]

ACCOUNT_FROZEN_PATTERNS = [
    "PHONE_NUMBER_FLOOD",
    "account is temporarily frozen",
    "account has been frozen",
]

SPAMBLOCK_PATTERNS = [
    "PEER_FLOOD",
    "SEND_AS_PEER_INVALID",
    "SendAsPeerInvalidError",
    "A wait of",
]

KICKED_PATTERNS = [
    "CHAT_FORBIDDEN",
    "kicked from",
    "removed from",
    "USER_KICKED",
]

NOT_IN_CHANNEL_PATTERNS = [
    "USER_NOT_PARTICIPANT",
    "UserNotParticipantError",
    "not a member",
    "CHANNEL_INVALID",
]


class ErrorClassifier:
    """Classifies Telegram errors into SendResult with proper status and message."""

    @staticmethod
    def classify(error: Exception) -> SendResult:
        """
        Classify an exception into a SendResult.

        Two-phase classification:
        1. By exception type (most specific)
        2. By error string pattern matching (fallback)
        """
        # Phase 1: Classify by exception type
        status, message, wait_seconds = ErrorClassifier._classify_by_type(error)
        if status is not None:
            return SendResult(
                status=status,
                message=message or str(error),
                error=str(error),
                wait_seconds=wait_seconds,
            )

        # Phase 2: Classify by string pattern
        error_str = str(error)
        status, message = ErrorClassifier._classify_by_pattern(error_str)
        if status is not None:
            return SendResult(
                status=status,
                message=message or error_str,
                error=error_str,
            )

        # Unknown error
        logger.warning(f"Unclassified error: {type(error).__name__}: {error}")
        return SendResult(
            status=SendStatus.ERROR,
            message=f"Unknown error: {type(error).__name__}",
            error=str(error),
        )

    @staticmethod
    def _classify_by_type(
        error: Exception,
    ) -> Tuple[Optional[SendStatus], Optional[str], Optional[int]]:
        """Classify error by its exception type."""
        error_type = type(error).__name__

        # FloodWait - extract wait time
        if error_type == "FloodWaitError":
            seconds = getattr(error, "seconds", 60)
            return SendStatus.FLOOD_WAIT, f"Flood wait: {seconds}s", seconds

        # SlowMode - extract wait time
        if error_type == "SlowModeWaitError":
            seconds = getattr(error, "seconds", 60)
            return SendStatus.SLOW_MODE, f"Slow mode: wait {seconds}s", seconds

        # Ban errors
        if error_type == "UserBannedInChannelError":
            return SendStatus.BANNED, "Account banned in this channel", None

        if error_type in ("ChatWriteForbiddenError", "ChatSendPlainForbiddenError"):
            return SendStatus.WRITE_FORBIDDEN, "Write forbidden in this chat", None

        if error_type == "ChannelPrivateError":
            return SendStatus.NO_ACCESS, "Channel is private", None

        if error_type in ("ChatAdminRequiredError", "UserRestrictedError"):
            return SendStatus.RESTRICTED, "Admin required or user restricted", None

        if error_type == "UserNotParticipantError":
            return SendStatus.NOT_IN_CHANNEL, "Not a member of the channel", None

        if error_type == "ChatForbiddenError":
            return SendStatus.KICKED_FROM_DISCUSSION, "Kicked from chat", None

        if error_type == "InviteHashExpiredError":
            return SendStatus.NO_ACCESS, "Invite link expired", None

        # Account-level errors
        if error_type in ("UserDeactivatedBanError", "PhoneNumberBannedError"):
            return SendStatus.ACCOUNT_BANNED, "Account banned by Telegram", None

        if error_type == "UserDeactivatedError":
            return SendStatus.ACCOUNT_DEACTIVATED, "Account deactivated", None

        if error_type in ("AuthKeyUnregisteredError", "AuthKeyDuplicatedError"):
            return SendStatus.SESSION_EXPIRED, "Session expired or revoked", None

        if error_type == "SessionRevokedError":
            return SendStatus.SESSION_EXPIRED, "Session revoked", None

        if error_type == "PhoneNumberFloodError":
            return SendStatus.ACCOUNT_FROZEN, "Account frozen (phone flood)", None

        # Skip errors
        if error_type == "MsgIdInvalidError":
            return SendStatus.SKIP, "Message no longer exists", None

        if error_type in ("ChatSendMediaForbiddenError", "ChatSendPhotosForbiddenError"):
            return SendStatus.SKIP, "Media not allowed", None

        if error_type == "ReactionsTooManyError":
            return SendStatus.SKIP, "Too many unique reactions on message", None

        # Network errors
        if error_type in ("ConnectionError", "TimeoutError", "OSError"):
            return SendStatus.NETWORK_ERROR, f"Network error: {error_type}", None

        return None, None, None

    @staticmethod
    def _classify_by_pattern(
        error_str: str,
    ) -> Tuple[Optional[SendStatus], Optional[str]]:
        """Classify error by string pattern matching."""

        for pattern in BAN_PATTERNS:
            if pattern in error_str:
                return SendStatus.BANNED, f"Banned (pattern: {pattern})"

        for pattern in ACCESS_PATTERNS:
            if pattern in error_str:
                return SendStatus.NO_ACCESS, f"No access (pattern: {pattern})"

        for pattern in WRITE_FORBIDDEN_PATTERNS:
            if pattern in error_str:
                return SendStatus.WRITE_FORBIDDEN, f"Write forbidden (pattern: {pattern})"

        for pattern in SKIP_PATTERNS:
            if pattern in error_str:
                return SendStatus.SKIP, f"Skipped (pattern: {pattern})"

        for pattern in FLOOD_PATTERNS:
            if pattern in error_str:
                return SendStatus.FLOOD_WAIT, f"Rate limited (pattern: {pattern})"

        for pattern in ACCOUNT_BAN_PATTERNS:
            if pattern in error_str:
                return SendStatus.ACCOUNT_BANNED, f"Account banned (pattern: {pattern})"

        for pattern in SESSION_ERROR_PATTERNS:
            if pattern in error_str:
                return SendStatus.SESSION_EXPIRED, f"Session invalid (pattern: {pattern})"

        for pattern in ACCOUNT_FROZEN_PATTERNS:
            if pattern in error_str:
                return SendStatus.ACCOUNT_FROZEN, f"Account frozen (pattern: {pattern})"

        for pattern in SPAMBLOCK_PATTERNS:
            if pattern in error_str:
                return SendStatus.SPAMBLOCK, f"Spamblock (pattern: {pattern})"

        for pattern in KICKED_PATTERNS:
            if pattern in error_str:
                return SendStatus.KICKED_FROM_DISCUSSION, f"Kicked from discussion (pattern: {pattern})"

        for pattern in NOT_IN_CHANNEL_PATTERNS:
            if pattern in error_str:
                return SendStatus.NOT_IN_CHANNEL, f"Not in channel (pattern: {pattern})"

        return None, None

    @staticmethod
    def get_blacklist_reason(status: SendStatus) -> Optional[str]:
        """Get blacklist reason string for DB storage."""
        reasons = {
            SendStatus.BANNED: "banned",
            SendStatus.NO_ACCESS: "no_access",
            SendStatus.WRITE_FORBIDDEN: "write_forbidden",
            SendStatus.RESTRICTED: "restricted",
            SendStatus.KICKED_FROM_DISCUSSION: "kicked",
        }
        return reasons.get(status)

    @staticmethod
    def get_recommended_account_status(result: SendResult) -> Optional[str]:
        """
        Get recommended account status for DB update based on error.

        Returns:
            Account status string or None if no change needed.
        """
        status = result.status

        if status == SendStatus.SESSION_EXPIRED:
            return "session_expired"

        if status == SendStatus.ACCOUNT_BANNED:
            return "banned"

        if status == SendStatus.ACCOUNT_DEACTIVATED:
            return "invalid"

        if status == SendStatus.ACCOUNT_FROZEN:
            return "invalid"

        if status == SendStatus.SPAMBLOCK:
            return "spamblock"

        # Severe FloodWait — mark as muted
        if status == SendStatus.FLOOD_WAIT:
            wait_seconds = result.wait_seconds or 0
            if wait_seconds > 300:
                return "spamblock"

        return None
