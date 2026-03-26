"""Tests for BaseClient proxy precheck behavior."""

import sys
from pathlib import Path

import pytest
import python_socks.async_.asyncio as python_socks_asyncio

sys.path.insert(0, str(Path(__file__).parent.parent))

from telegram.client import BaseClient


class _DummySocket:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class _SuccessfulProxy:
    def __init__(self, sock: _DummySocket):
        self.sock = sock
        self.calls = []

    async def connect(self, dest_host: str, dest_port: int):
        self.calls.append((dest_host, dest_port))
        return self.sock


class _AuthFailingProxy:
    async def connect(self, dest_host: str, dest_port: int):
        raise RuntimeError("Username and password authentication failure")


@pytest.mark.asyncio
async def test_base_client_socks_precheck_uses_telegram_dc_tcp(monkeypatch):
    sock = _DummySocket()
    proxy = _SuccessfulProxy(sock)

    monkeypatch.setattr(
        python_socks_asyncio.Proxy,
        "from_url",
        staticmethod(lambda url: proxy),
    )

    client = BaseClient(
        session_string="session",
        proxy={"type": "socks5", "host": "127.0.0.1", "port": 1080},
    )

    result = await client._test_proxy_connection()

    assert result["success"] is True
    assert result["error"] is None
    assert proxy.calls == [("149.154.167.50", 443)]
    assert sock.closed is True


@pytest.mark.asyncio
async def test_base_client_socks_precheck_preserves_auth_failure(monkeypatch):
    monkeypatch.setattr(
        python_socks_asyncio.Proxy,
        "from_url",
        staticmethod(lambda url: _AuthFailingProxy()),
    )

    client = BaseClient(
        session_string="session",
        proxy={
            "type": "socks5",
            "host": "127.0.0.1",
            "port": 1080,
            "username": "user",
            "password": "pass",
        },
    )

    result = await client._test_proxy_connection()

    assert result["success"] is False
    assert result["error"] == "SOCKS proxy not working: Username and password authentication failure"
