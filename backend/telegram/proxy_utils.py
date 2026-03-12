"""Shared proxy utilities for Telegram modules."""
from typing import Dict, Optional, Tuple

import socks


def format_proxy(proxy: Optional[Dict]) -> Optional[Tuple]:
    """Format proxy dict to Telethon tuple format.

    Returns (socks_type, host, port, rdns, username, password) or None.
    """
    if not proxy:
        return None

    proxy_type = proxy.get("type", "socks5").lower()

    if proxy_type == "socks5":
        ptype = socks.SOCKS5
    elif proxy_type == "socks4":
        ptype = socks.SOCKS4
    elif proxy_type in ("http", "https"):
        ptype = socks.HTTP
    else:
        ptype = socks.SOCKS5

    return (
        ptype,
        proxy.get("host") or proxy.get("addr"),
        int(proxy.get("port", 1080)),
        True,  # rdns
        proxy.get("username"),
        proxy.get("password"),
    )
