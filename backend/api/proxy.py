from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from datetime import datetime
import aiohttp
from aiohttp_socks import ProxyConnector

from database.database import get_session
from database.models import Proxy

router = APIRouter()


class ProxyCreate(BaseModel):
    type: str = "socks5"
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None


class ProxyBulkCreate(BaseModel):
    proxies: List[str]  # Format: host:port or host:port:user:pass
    type: str = "socks5"


@router.get("")
async def get_proxies(
    status: Optional[str] = None,
    session: AsyncSession = Depends(get_session)
):
    """Get all proxies"""
    query = select(Proxy).options(selectinload(Proxy.accounts))

    if status:
        query = query.where(Proxy.status == status)

    result = await session.execute(query)
    proxies = result.scalars().all()

    return {"data": [p.to_dict() for p in proxies]}


@router.get("/{proxy_id}")
async def get_proxy(
    proxy_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get single proxy"""
    query = select(Proxy).options(
        selectinload(Proxy.accounts)
    ).where(Proxy.id == proxy_id)

    result = await session.execute(query)
    proxy = result.scalar_one_or_none()

    if not proxy:
        raise HTTPException(status_code=404, detail="Proxy not found")

    return proxy.to_dict()


@router.post("")
async def create_proxy(
    data: ProxyCreate,
    session: AsyncSession = Depends(get_session)
):
    """Create new proxy"""
    proxy = Proxy(
        type=data.type,
        host=data.host,
        port=data.port,
        username=data.username,
        password=data.password
    )

    session.add(proxy)
    await session.commit()
    await session.refresh(proxy)

    return proxy.to_dict()


@router.post("/bulk")
async def create_proxies_bulk(
    data: ProxyBulkCreate,
    session: AsyncSession = Depends(get_session)
):
    """Create multiple proxies at once"""
    created = []

    for line in data.proxies:
        parts = line.strip().split(":")
        if len(parts) < 2:
            continue

        proxy = Proxy(
            type=data.type,
            host=parts[0],
            port=int(parts[1]),
            username=parts[2] if len(parts) > 2 else None,
            password=parts[3] if len(parts) > 3 else None
        )

        session.add(proxy)
        created.append(proxy)

    await session.commit()

    return {"created": len(created)}


@router.put("/{proxy_id}")
async def update_proxy(
    proxy_id: int,
    data: ProxyCreate,
    session: AsyncSession = Depends(get_session)
):
    """Update proxy"""
    query = select(Proxy).where(Proxy.id == proxy_id)
    result = await session.execute(query)
    proxy = result.scalar_one_or_none()

    if not proxy:
        raise HTTPException(status_code=404, detail="Proxy not found")

    proxy.type = data.type
    proxy.host = data.host
    proxy.port = data.port
    proxy.username = data.username
    proxy.password = data.password

    await session.commit()
    await session.refresh(proxy)

    return proxy.to_dict()


@router.delete("/{proxy_id}")
async def delete_proxy(
    proxy_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Delete proxy"""
    query = select(Proxy).where(Proxy.id == proxy_id)
    result = await session.execute(query)
    proxy = result.scalar_one_or_none()

    if not proxy:
        raise HTTPException(status_code=404, detail="Proxy not found")

    await session.delete(proxy)
    await session.commit()

    return {"success": True}


@router.post("/{proxy_id}/check")
async def check_proxy(
    proxy_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Check if proxy is working"""
    query = select(Proxy).where(Proxy.id == proxy_id)
    result = await session.execute(query)
    proxy = result.scalar_one_or_none()

    if not proxy:
        raise HTTPException(status_code=404, detail="Proxy not found")

    try:
        # Build proxy URL
        auth = f"{proxy.username}:{proxy.password}@" if proxy.username else ""
        proxy_url = f"{proxy.type}://{auth}{proxy.host}:{proxy.port}"

        connector = ProxyConnector.from_url(proxy_url)

        async with aiohttp.ClientSession(connector=connector) as client:
            async with client.get("https://api.ipify.org?format=json", timeout=10) as resp:
                if resp.status == 200:
                    proxy.status = "valid"
                else:
                    proxy.status = "invalid"

    except Exception as e:
        proxy.status = "invalid"

    proxy.last_checked_at = datetime.utcnow()
    await session.commit()

    return {"status": proxy.status}


@router.post("/check-all")
async def check_all_proxies(
    session: AsyncSession = Depends(get_session)
):
    """Check all proxies"""
    query = select(Proxy)
    result = await session.execute(query)
    proxies = result.scalars().all()

    # TODO: Run checks in parallel
    checked = 0
    for proxy in proxies:
        try:
            auth = f"{proxy.username}:{proxy.password}@" if proxy.username else ""
            proxy_url = f"{proxy.type}://{auth}{proxy.host}:{proxy.port}"
            connector = ProxyConnector.from_url(proxy_url)

            async with aiohttp.ClientSession(connector=connector) as client:
                async with client.get("https://api.ipify.org", timeout=10) as resp:
                    proxy.status = "valid" if resp.status == 200 else "invalid"
        except:
            proxy.status = "invalid"

        proxy.last_checked_at = datetime.utcnow()
        checked += 1

    await session.commit()

    return {"checked": checked}
