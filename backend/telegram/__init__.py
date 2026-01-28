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
from .account_checker import AccountChecker, AccountStatus, AccountCheckResult, account_checker
from .two_factor import TwoFactorManager, TwoFactorStatus, TwoFactorCheckResult, TwoFactorSetResult, two_factor_manager
from .auth_service import AuthService, AuthStep, AuthSession, AuthStartResult, AuthVerifyResult, auth_service

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
    # Account Checker
    "AccountChecker",
    "AccountStatus",
    "AccountCheckResult",
    "account_checker",
    # Two-Factor Authentication
    "TwoFactorManager",
    "TwoFactorStatus",
    "TwoFactorCheckResult",
    "TwoFactorSetResult",
    "two_factor_manager",
    # Auth Service
    "AuthService",
    "AuthStep",
    "AuthSession",
    "AuthStartResult",
    "AuthVerifyResult",
    "auth_service",
]
