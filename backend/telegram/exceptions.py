class TelegramError(Exception):
    """Base exception for Telegram operations"""
    pass


class SessionError(TelegramError):
    """Error with session handling"""
    pass


class UnauthorizedError(TelegramError):
    """Account is not authorized"""
    pass


class SessionExpiredError(TelegramError):
    """Session has expired"""
    pass


class ProxyError(TelegramError):
    """Proxy connection error"""
    pass


class TDataError(TelegramError):
    """Error during tdata conversion"""
    pass
