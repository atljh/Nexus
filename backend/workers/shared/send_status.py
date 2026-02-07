"""
Send status enum and result dataclass for unified Telegram action handling.

Ported from GramGPT with adaptations for Nexus desktop app:
- Removed ALL_ACCOUNTS_UNAVAILABLE, ALL_ACCOUNTS_QUARANTINED (not needed for desktop)
- English messages
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Any


class SendStatus(Enum):
    """Unified status for all Telegram send operations."""

    # Success
    OK = "ok"
    ALREADY_DONE = "already_done"

    # Skip (non-error, just skip this action)
    SKIP = "skip"

    # Rate limiting
    FLOOD_WAIT = "flood_wait"
    SLOW_MODE = "slow_mode"

    # Channel-level errors (account blocked for specific channel)
    BANNED = "banned"
    NO_ACCESS = "no_access"
    WRITE_FORBIDDEN = "write_forbidden"
    RESTRICTED = "restricted"
    KICKED_FROM_DISCUSSION = "kicked_from_discussion"
    NOT_IN_CHANNEL = "not_in_channel"

    # Account-level errors (account cannot be used at all)
    ACCOUNT_BANNED = "account_banned"
    ACCOUNT_DEACTIVATED = "account_deactivated"
    ACCOUNT_FROZEN = "account_frozen"
    SESSION_EXPIRED = "session_expired"
    SPAMBLOCK = "spamblock"

    # Generic errors
    ERROR = "error"
    NETWORK_ERROR = "network_error"
    TIMEOUT = "timeout"

    @property
    def is_success(self) -> bool:
        return self in (SendStatus.OK, SendStatus.ALREADY_DONE)

    @property
    def is_temporary(self) -> bool:
        return self in (
            SendStatus.FLOOD_WAIT,
            SendStatus.SLOW_MODE,
            SendStatus.NETWORK_ERROR,
            SendStatus.TIMEOUT,
        )

    @property
    def is_ban(self) -> bool:
        return self in (
            SendStatus.BANNED,
            SendStatus.KICKED_FROM_DISCUSSION,
        )

    @property
    def is_account_issue(self) -> bool:
        return self in (
            SendStatus.ACCOUNT_BANNED,
            SendStatus.ACCOUNT_DEACTIVATED,
            SendStatus.ACCOUNT_FROZEN,
            SendStatus.SESSION_EXPIRED,
            SendStatus.SPAMBLOCK,
        )

    @property
    def should_blacklist_entity(self) -> bool:
        """Whether to add this channel to account's blacklist."""
        return self in (
            SendStatus.BANNED,
            SendStatus.NO_ACCESS,
            SendStatus.WRITE_FORBIDDEN,
            SendStatus.RESTRICTED,
            SendStatus.KICKED_FROM_DISCUSSION,
        )

    @property
    def should_stop_task(self) -> bool:
        """Whether to stop using this account for any further actions."""
        return self in (
            SendStatus.ACCOUNT_BANNED,
            SendStatus.ACCOUNT_DEACTIVATED,
            SendStatus.ACCOUNT_FROZEN,
            SendStatus.SESSION_EXPIRED,
            SendStatus.SPAMBLOCK,
        )

    @property
    def should_update_account_status(self) -> bool:
        """Whether the account's DB status should be updated."""
        return self.is_account_issue

    @property
    def is_recoverable(self) -> bool:
        return self in (
            SendStatus.FLOOD_WAIT,
            SendStatus.SLOW_MODE,
            SendStatus.NETWORK_ERROR,
            SendStatus.TIMEOUT,
            SendStatus.NOT_IN_CHANNEL,
        )

    @property
    def is_permanent(self) -> bool:
        return self in (
            SendStatus.ACCOUNT_BANNED,
            SendStatus.ACCOUNT_DEACTIVATED,
            SendStatus.BANNED,
            SendStatus.KICKED_FROM_DISCUSSION,
        )


@dataclass
class SendResult:
    """Result of a send operation with full context."""

    status: SendStatus
    message: str = ""
    error: Optional[str] = None
    wait_seconds: Optional[int] = None
    entity_id: Optional[int] = None
    entity_title: Optional[str] = None
    sent_message: Optional[Any] = None

    @property
    def success(self) -> bool:
        return self.status.is_success

    @property
    def should_blacklist(self) -> bool:
        return self.status.should_blacklist_entity

    @property
    def should_stop(self) -> bool:
        return self.status.should_stop_task

    def __str__(self) -> str:
        parts = [f"[{self.status.value}]"]
        if self.message:
            parts.append(self.message)
        if self.error:
            parts.append(f"(error: {self.error})")
        if self.wait_seconds:
            parts.append(f"(wait: {self.wait_seconds}s)")
        return " ".join(parts)
