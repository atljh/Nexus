"""
Proxy checker with parallel execution and GEO detection.
Based on GramGPT implementation.
"""
import asyncio
import time
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum

import aiohttp
from aiohttp_socks import ProxyConnector


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
        except Exception:
            pass

        return None


# Singleton instance
proxy_checker = ProxyChecker()
