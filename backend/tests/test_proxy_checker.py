"""Tests for proxy checker error reporting."""

import importlib
import sys
from pathlib import Path

import pytest
import python_socks.async_.asyncio as python_socks_asyncio

sys.path.insert(0, str(Path(__file__).parent.parent))

importlib.import_module("api.proxy_checker")
from api.proxy_checker import ProxyChecker


class _AuthFailingProxy:
    async def connect(self, dest_host: str, dest_port: int):
        raise RuntimeError("Username and password authentication failure")


@pytest.mark.asyncio
async def test_socks_telegram_check_preserves_auth_failure(monkeypatch):
    checker = ProxyChecker()

    monkeypatch.setattr(
        python_socks_asyncio.Proxy,
        "from_url",
        staticmethod(lambda url: _AuthFailingProxy()),
    )

    result = await checker._test_socks_proxy_telegram("socks5://user:pass@127.0.0.1:1080")

    assert result == {
        "success": False,
        "error": "Username and password authentication failure",
    }
