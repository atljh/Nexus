"""
Proxy checker with parallel execution and GEO detection.
Based on GramGPT implementation.
"""
import asyncio
import base64
import logging
import time
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

import aiohttp
from aiohttp_socks import ProxyConnector


# Telegram MTProto DC servers for connectivity test
TELEGRAM_DC_SERVERS = [
    ("149.154.167.50", 443),  # DC2
    ("149.154.175.53", 443),  # DC1
]


class ProxyStatus(str, Enum):
    UNCHECKED = "unchecked"
    WORKING = "working"
    SLOW = "slow"  # > 2000ms
    VERY_SLOW = "very_slow"  # > 8000ms
    NOT_WORKING = "not_working"
    TIMEOUT = "timeout"


@dataclass
class ProxyCheckResult:
    proxy_id: int
    status: ProxyStatus
    ping_ms: Optional[int] = None
    external_ip: Optional[str] = None
    geo: Optional[str] = None
    error: Optional[str] = None


class ProxyChecker:
    """Async proxy checker with parallel execution and GEO lookup."""

    TEST_URLS = [
        "https://api.ipify.org",
        "https://ifconfig.me/ip",
        "https://icanhazip.com",
    ]

    def __init__(
        self,
        timeout: int = 30,
        max_concurrent: int = 50,
        max_retries: int = 2
    ):
        self.timeout = timeout
        self.max_concurrent = max_concurrent
        self.max_retries = max_retries
        self._semaphore: Optional[asyncio.Semaphore] = None

    async def check_single(
        self,
        proxy_id: int,
        proxy_url: str,
        lookup_geo: bool = True
    ) -> ProxyCheckResult:
        """
        Check a single proxy.

        Args:
            proxy_id: Database ID of the proxy
            proxy_url: Full proxy URL (e.g., socks5://user:pass@host:port)
            lookup_geo: Whether to lookup GEO by IP

        Returns:
            ProxyCheckResult with status, ping, IP, and GEO
        """
        result = ProxyCheckResult(
            proxy_id=proxy_id,
            status=ProxyStatus.NOT_WORKING
        )

        # Test Telegram DC reachability first
        parsed = urlparse(proxy_url)
        if parsed.scheme and parsed.scheme.startswith("socks"):
            telegram_test = await self._test_socks_proxy_telegram(proxy_url)
            if not telegram_test["success"]:
                result.error = telegram_test["error"]
                return result
        elif parsed.scheme in ("http", "https"):
            telegram_test = await self._test_http_proxy_connect(
                proxy_host=parsed.hostname,
                proxy_port=parsed.port,
                username=parsed.username,
                password=parsed.password,
            )
            if not telegram_test["success"]:
                result.error = telegram_test["error"]
                return result

        for attempt in range(self.max_retries):
            for test_url in self.TEST_URLS:
                try:
                    connector = ProxyConnector.from_url(proxy_url)

                    start_time = time.monotonic()

                    async with aiohttp.ClientSession(connector=connector) as session:
                        async with session.get(
                            test_url,
                            timeout=aiohttp.ClientTimeout(total=self.timeout)
                        ) as response:
                            if response.status == 200:
                                ping_ms = int((time.monotonic() - start_time) * 1000)

                                # Get external IP
                                text = await response.text()
                                external_ip = text.strip()

                                # Determine status based on ping
                                if ping_ms < 2000:
                                    status = ProxyStatus.WORKING
                                elif ping_ms < 8000:
                                    status = ProxyStatus.SLOW
                                else:
                                    status = ProxyStatus.VERY_SLOW

                                result.status = status
                                result.ping_ms = ping_ms
                                result.external_ip = external_ip

                                # Lookup GEO
                                if lookup_geo and external_ip:
                                    result.geo = await self._lookup_geo(external_ip)

                                return result

                except asyncio.TimeoutError:
                    result.status = ProxyStatus.TIMEOUT
                    result.error = "Connection timeout"
                except Exception as e:
                    result.error = str(e)

        return result

    async def _test_socks_proxy_telegram(self, proxy_url: str) -> Dict[str, Any]:
        """
        Test SOCKS proxy connectivity to Telegram DC servers.
        Makes a TCP connection through the SOCKS proxy to DC servers.
        """
        try:
            from python_socks.async_.asyncio import Proxy
        except ImportError:
            # If python-socks not installed, skip the check
            return {"success": True, "error": None}

        last_error: Optional[str] = None

        for dc_host, dc_port in TELEGRAM_DC_SERVERS:
            try:
                proxy = Proxy.from_url(proxy_url)
                sock = await asyncio.wait_for(
                    proxy.connect(dest_host=dc_host, dest_port=dc_port),
                    timeout=10,
                )
                sock.close()
                return {"success": True, "error": None}
            except asyncio.TimeoutError:
                last_error = "Connection timeout"
                continue
            except Exception as e:
                logger.debug(f"SOCKS telegram test failed for {dc_host}: {e}")
                last_error = str(e)
                if "authentication failure" in last_error.lower():
                    return {"success": False, "error": last_error}
                continue

        return {
            "success": False,
            "error": last_error or "Proxy cannot connect to Telegram servers. Telegram may be blocked on this proxy.",
        }

    async def _test_http_proxy_connect(
        self,
        proxy_host: str,
        proxy_port: int,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Test HTTP proxy CONNECT method to Telegram DC servers.
        Many HTTP proxies work for regular traffic but don't support CONNECT tunneling
        needed for Telegram MTProto.
        """
        for dc_host, dc_port in TELEGRAM_DC_SERVERS:
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(proxy_host, proxy_port), timeout=5
                )
            except Exception as e:
                logger.debug(f"HTTP proxy connect failed to {proxy_host}:{proxy_port}: {e}")
                continue

            try:
                connect_request = f"CONNECT {dc_host}:{dc_port} HTTP/1.1\r\n"
                connect_request += f"Host: {dc_host}:{dc_port}\r\n"

                if username and password:
                    credentials = base64.b64encode(
                        f"{username}:{password}".encode()
                    ).decode()
                    connect_request += f"Proxy-Authorization: Basic {credentials}\r\n"

                connect_request += "\r\n"

                writer.write(connect_request.encode())
                await writer.drain()

                response = await asyncio.wait_for(reader.readline(), timeout=5)
                response_str = response.decode().strip()

                writer.close()
                try:
                    await writer.wait_closed()
                except Exception as e:
                    logger.debug(f"Writer close error: {e}")

                if "200" in response_str:
                    return {"success": True, "error": None}
                elif "407" in response_str:
                    return {"success": False, "error": "Invalid proxy username or password"}
                elif "403" in response_str:
                    return {"success": False, "error": "Proxy blocked connection to Telegram"}
                else:
                    return {
                        "success": False,
                        "error": "This proxy does not support Telegram connections (no CONNECT support)",
                    }

            except asyncio.TimeoutError:
                try:
                    writer.close()
                except Exception as e:
                    logger.debug(f"Writer close error: {e}")
                continue
            except Exception as e:
                logger.debug(f"HTTP CONNECT test error: {e}")
                try:
                    writer.close()
                except Exception as e2:
                    logger.debug(f"Writer close error: {e2}")
                continue

        return {
            "success": False,
            "error": "Could not connect to Telegram servers through this proxy",
        }

    async def check_batch(
        self,
        proxies: List[Dict[str, Any]],
        lookup_geo: bool = True
    ) -> List[ProxyCheckResult]:
        """
        Check multiple proxies in parallel.

        Args:
            proxies: List of dicts with 'id' and 'url' keys
            lookup_geo: Whether to lookup GEO for each proxy

        Returns:
            List of ProxyCheckResult objects
        """
        self._semaphore = asyncio.Semaphore(self.max_concurrent)

        async def check_with_semaphore(proxy_data: Dict[str, Any]) -> ProxyCheckResult:
            async with self._semaphore:
                return await self.check_single(
                    proxy_id=proxy_data["id"],
                    proxy_url=proxy_data["url"],
                    lookup_geo=lookup_geo
                )

        tasks = [check_with_semaphore(p) for p in proxies]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle any exceptions
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append(ProxyCheckResult(
                    proxy_id=proxies[i]["id"],
                    status=ProxyStatus.NOT_WORKING,
                    error=str(result)
                ))
            else:
                final_results.append(result)

        return final_results

    async def _lookup_geo(self, ip: str) -> Optional[str]:
        """
        Lookup country code by IP address using ip-api.com.

        Args:
            ip: IP address to lookup

        Returns:
            Two-letter country code (e.g., RU, US, UA) or None
        """
        try:
            async with aiohttp.ClientSession() as session:
                url = f"http://ip-api.com/json/{ip}?fields=status,countryCode"
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("status") == "success":
                            return data.get("countryCode")
        except Exception as e:
            logger.debug(f"GEO lookup failed for {ip}: {e}")

        return None


# Singleton instance
proxy_checker = ProxyChecker()
