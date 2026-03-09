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
from .telegram_client import TelegramClient, API_LANG_PACKS
from .client import BaseClient, validate_session
from .tdata_converter import TDataConverter, SimpleTDataConverter, convert_tdata_to_session, parse_tdata_to_session
from .account_checker import AccountChecker, AccountStatus, AccountCheckResult, account_checker
from .two_factor import TwoFactorManager, TwoFactorStatus, TwoFactorCheckResult, TwoFactorSetResult, two_factor_manager
from .auth_service import AuthService, AuthStep, AuthSession, AuthStartResult, AuthVerifyResult, auth_service
from .device_generator import (
    generate_device_fingerprint,
    generate_fingerprint_for_api,
    detect_platform_from_api_id,
    get_device_for_session,
    DeviceFingerprint,
    OFFICIAL_APIS,
    ANDROID_DEVICES,
    IOS_DEVICES,
    DESKTOP_DEVICES,
)

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
    # Custom TelegramClient
    "TelegramClient",
    "API_LANG_PACKS",
    # Client
    "BaseClient",
    "validate_session",
    # TData
    "TDataConverter",
    "SimpleTDataConverter",
    "convert_tdata_to_session",
    "parse_tdata_to_session",
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
    # Device Fingerprint
    "generate_device_fingerprint",
    "generate_fingerprint_for_api",
    "detect_platform_from_api_id",
    "get_device_for_session",
    "DeviceFingerprint",
    "OFFICIAL_APIS",
    "ANDROID_DEVICES",
    "IOS_DEVICES",
    "DESKTOP_DEVICES",
]
