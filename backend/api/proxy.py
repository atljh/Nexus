from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from datetime import datetime

from database.database import get_session
from database.models import Proxy
from api.proxy_checker import proxy_checker, ProxyStatus

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


class ProxyCheckBatch(BaseModel):
    proxy_ids: List[int]
    lookup_geo: bool = True


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

    # Build proxy URL
    proxy_url = proxy.get_connection_string()

    # Check using ProxyChecker
    check_result = await proxy_checker.check_single(
        proxy_id=proxy.id,
        proxy_url=proxy_url,
        lookup_geo=True
    )

    # Update proxy with results
    proxy.status = check_result.status.value
    proxy.ping_ms = check_result.ping_ms
    proxy.external_ip = check_result.external_ip
    proxy.geo = check_result.geo
    proxy.last_checked_at = datetime.utcnow()

    await session.commit()

    return {
        "status": proxy.status,
        "ping_ms": proxy.ping_ms,
        "external_ip": proxy.external_ip,
        "geo": proxy.geo
    }


@router.post("/check-batch")
async def check_batch_proxies(
    data: ProxyCheckBatch,
    session: AsyncSession = Depends(get_session)
):
    """Check multiple proxies in parallel"""
    query = select(Proxy).where(Proxy.id.in_(data.proxy_ids))
    result = await session.execute(query)
    proxies = result.scalars().all()

    if not proxies:
        return {"checked": 0, "results": []}

    # Prepare proxy data for checker
    proxy_data = [
        {"id": p.id, "url": p.get_connection_string()}
        for p in proxies
    ]

    # Check all in parallel
    check_results = await proxy_checker.check_batch(
        proxies=proxy_data,
        lookup_geo=data.lookup_geo
    )

    # Update proxies in DB
    results_map = {r.proxy_id: r for r in check_results}
    response_results = []

    for proxy in proxies:
        check_result = results_map.get(proxy.id)
        if check_result:
            proxy.status = check_result.status.value
            proxy.ping_ms = check_result.ping_ms
            proxy.external_ip = check_result.external_ip
            proxy.geo = check_result.geo
            proxy.last_checked_at = datetime.utcnow()

            response_results.append({
                "id": proxy.id,
                "status": proxy.status,
                "ping_ms": proxy.ping_ms,
                "external_ip": proxy.external_ip,
                "geo": proxy.geo
            })

    await session.commit()

    return {
        "checked": len(response_results),
        "results": response_results
    }


@router.post("/check-all")
async def check_all_proxies(
    session: AsyncSession = Depends(get_session)
):
    """Check all proxies in parallel"""
    query = select(Proxy)
    result = await session.execute(query)
    proxies = result.scalars().all()

    if not proxies:
        return {"checked": 0, "results": []}

    # Prepare proxy data for checker
    proxy_data = [
        {"id": p.id, "url": p.get_connection_string()}
        for p in proxies
    ]

    # Check all in parallel
    check_results = await proxy_checker.check_batch(
        proxies=proxy_data,
        lookup_geo=True
    )

    # Update proxies in DB
    results_map = {r.proxy_id: r for r in check_results}
    response_results = []

    for proxy in proxies:
        check_result = results_map.get(proxy.id)
        if check_result:
            proxy.status = check_result.status.value
            proxy.ping_ms = check_result.ping_ms
            proxy.external_ip = check_result.external_ip
            proxy.geo = check_result.geo
            proxy.last_checked_at = datetime.utcnow()

            response_results.append({
                "id": proxy.id,
                "status": proxy.status,
                "ping_ms": proxy.ping_ms,
                "geo": proxy.geo
            })

    await session.commit()

    return {
        "checked": len(response_results),
        "results": response_results
    }
