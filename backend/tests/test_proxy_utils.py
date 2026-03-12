"""Tests for telegram.proxy_utils — shared proxy formatting utility."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import socks
from telegram.proxy_utils import format_proxy


class TestFormatProxy:
    """Tests for format_proxy()."""

    def test_none_returns_none(self):
        assert format_proxy(None) is None

    def test_empty_dict_returns_none(self):
        assert format_proxy({}) is None

    def test_socks5_default(self):
        result = format_proxy({"host": "1.2.3.4", "port": 1080})
        assert result[0] == socks.SOCKS5
        assert result[1] == "1.2.3.4"
        assert result[2] == 1080
        assert result[3] is True  # rdns
        assert result[4] is None  # username
        assert result[5] is None  # password

    def test_socks5_explicit(self):
        result = format_proxy({"type": "socks5", "host": "proxy.test", "port": 9050})
        assert result[0] == socks.SOCKS5
        assert result[1] == "proxy.test"
        assert result[2] == 9050

    def test_socks4(self):
        result = format_proxy({"type": "socks4", "host": "proxy.test", "port": 1080})
        assert result[0] == socks.SOCKS4

    def test_http(self):
        result = format_proxy({"type": "http", "host": "proxy.test", "port": 8080})
        assert result[0] == socks.HTTP

    def test_https_maps_to_http(self):
        result = format_proxy({"type": "https", "host": "proxy.test", "port": 443})
        assert result[0] == socks.HTTP

    def test_unknown_type_defaults_socks5(self):
        result = format_proxy({"type": "unknowntype", "host": "x", "port": 1})
        assert result[0] == socks.SOCKS5

    def test_case_insensitive_type(self):
        result = format_proxy({"type": "SOCKS5", "host": "x", "port": 1})
        assert result[0] == socks.SOCKS5

        result2 = format_proxy({"type": "Http", "host": "x", "port": 1})
        assert result2[0] == socks.HTTP

    def test_with_credentials(self):
        result = format_proxy({
            "type": "socks5",
            "host": "proxy.test",
            "port": 1080,
            "username": "user",
            "password": "pass123",
        })
        assert result[4] == "user"
        assert result[5] == "pass123"

    def test_addr_fallback(self):
        """GramGPT compatibility — 'addr' key instead of 'host'."""
        result = format_proxy({"addr": "10.0.0.1", "port": 1080})
        assert result[1] == "10.0.0.1"

    def test_host_takes_priority_over_addr(self):
        result = format_proxy({"host": "primary", "addr": "fallback", "port": 1080})
        assert result[1] == "primary"

    def test_port_default_1080(self):
        result = format_proxy({"host": "x"})
        assert result[2] == 1080

    def test_port_as_string(self):
        result = format_proxy({"host": "x", "port": "9050"})
        assert result[2] == 9050

    def test_tuple_length(self):
        result = format_proxy({"host": "x", "port": 1080})
        assert len(result) == 6
