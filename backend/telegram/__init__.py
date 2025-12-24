"""
Telegram module for Nexus
Provides session management and Telegram client operations
"""

from .exceptions import (
    TelegramError,
    SessionError,
    UnauthorizedError,
    SessionExpiredError,
    ProxyError,
    TDataError,
)
from .session_manager import SessionManager
from .client import BaseClient, validate_session
from .tdata_converter import TDataConverter, convert_tdata_to_session

__all__ = [
    # Exceptions
    "TelegramError",
    "SessionError",
    "UnauthorizedError",
    "SessionExpiredError",
    "ProxyError",
    "TDataError",
    # Session
    "SessionManager",
    # Client
    "BaseClient",
    "validate_session",
    # TData
    "TDataConverter",
    "convert_tdata_to_session",
]
