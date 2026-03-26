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


class _FailingSession:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def get(self, *args, **kwargs):
        raise RuntimeError("[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed")


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


@pytest.mark.asyncio
async def test_check_single_uses_telegram_success_when_ip_lookup_fails_for_socks(monkeypatch):
    checker = ProxyChecker(max_retries=1)

    async def fake_telegram_test(proxy_url: str):
        return {"success": True, "error": None, "ping_ms": 321}

    monkeypatch.setattr(checker, "_test_socks_proxy_telegram", fake_telegram_test)
    monkeypatch.setattr(
        python_socks_asyncio.Proxy,
        "from_url",
        staticmethod(lambda url: object()),
    )
    monkeypatch.setattr("api.proxy_checker.aiohttp.ClientSession", _FailingSession)
    monkeypatch.setattr("api.proxy_checker.ProxyConnector.from_url", staticmethod(lambda url: object()))

    result = await checker.check_single(
        proxy_id=1,
        proxy_url="socks5://127.0.0.1:1080",
        lookup_geo=False,
    )

    assert result.status.value == "working"
    assert result.ping_ms == 321
    assert result.external_ip is None
    assert result.error is None


@pytest.mark.asyncio
async def test_check_single_uses_telegram_success_when_ip_lookup_fails_for_http(monkeypatch):
    checker = ProxyChecker(max_retries=1)

    async def fake_http_connect(*args, **kwargs):
        return {"success": True, "error": None, "ping_ms": 4200}

    monkeypatch.setattr(checker, "_test_http_proxy_connect", fake_http_connect)
    monkeypatch.setattr("api.proxy_checker.aiohttp.ClientSession", _FailingSession)
    monkeypatch.setattr("api.proxy_checker.ProxyConnector.from_url", staticmethod(lambda url: object()))

    result = await checker.check_single(
        proxy_id=2,
        proxy_url="http://127.0.0.1:8080",
        lookup_geo=False,
    )

    assert result.status.value == "slow"
    assert result.ping_ms == 4200
    assert result.external_ip is None
    assert result.error is None
