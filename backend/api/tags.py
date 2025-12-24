from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from database.database import get_session
from database.models import AccountTag

router = APIRouter()


class TagCreate(BaseModel):
    name: str
    color: Optional[str] = "#a855f7"


@router.get("")
async def get_tags(
    session: AsyncSession = Depends(get_session)
):
    """Get all tags"""
    query = select(AccountTag)
    result = await session.execute(query)
    tags = result.scalars().all()

    return {"data": [t.to_dict() for t in tags]}


@router.post("")
async def create_tag(
    data: TagCreate,
    session: AsyncSession = Depends(get_session)
):
    """Create new tag"""
    tag = AccountTag(
        name=data.name,
        color=data.color
    )

    session.add(tag)
    await session.commit()
    await session.refresh(tag)

    return tag.to_dict()


@router.put("/{tag_id}")
async def update_tag(
    tag_id: int,
    data: TagCreate,
    session: AsyncSession = Depends(get_session)
):
    """Update tag"""
    query = select(AccountTag).where(AccountTag.id == tag_id)
    result = await session.execute(query)
    tag = result.scalar_one_or_none()

    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    tag.name = data.name
    tag.color = data.color

    await session.commit()
    await session.refresh(tag)

    return tag.to_dict()


@router.delete("/{tag_id}")
async def delete_tag(
    tag_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Delete tag"""
    query = select(AccountTag).where(AccountTag.id == tag_id)
    result = await session.execute(query)
    tag = result.scalar_one_or_none()

    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    await session.delete(tag)
    await session.commit()

    return {"success": True}
