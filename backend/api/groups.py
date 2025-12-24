from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from database.database import get_session
from database.models import AccountGroup

router = APIRouter()


class GroupCreate(BaseModel):
    name: str
    color: Optional[str] = None


@router.get("")
async def get_groups(
    session: AsyncSession = Depends(get_session)
):
    """Get all groups"""
    query = select(AccountGroup).options(selectinload(AccountGroup.accounts))
    result = await session.execute(query)
    groups = result.scalars().all()

    return {"data": [g.to_dict() for g in groups]}


@router.post("")
async def create_group(
    data: GroupCreate,
    session: AsyncSession = Depends(get_session)
):
    """Create new group"""
    group = AccountGroup(
        name=data.name,
        color=data.color
    )

    session.add(group)
    await session.commit()
    await session.refresh(group)

    return group.to_dict()


@router.put("/{group_id}")
async def update_group(
    group_id: int,
    data: GroupCreate,
    session: AsyncSession = Depends(get_session)
):
    """Update group"""
    query = select(AccountGroup).where(AccountGroup.id == group_id)
    result = await session.execute(query)
    group = result.scalar_one_or_none()

    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    group.name = data.name
    if data.color:
        group.color = data.color

    await session.commit()
    await session.refresh(group)

    return group.to_dict()


@router.delete("/{group_id}")
async def delete_group(
    group_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Delete group"""
    query = select(AccountGroup).where(AccountGroup.id == group_id)
    result = await session.execute(query)
    group = result.scalar_one_or_none()

    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    await session.delete(group)
    await session.commit()

    return {"success": True}
