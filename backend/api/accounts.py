from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from database.database import get_session
from database.models import Account, Proxy, AccountGroup, AccountTag

router = APIRouter()


class AccountCreate(BaseModel):
    phone: Optional[str] = None
    proxy_id: Optional[int] = None
    group_id: Optional[int] = None


class AccountUpdate(BaseModel):
    proxy_id: Optional[int] = None
    group_id: Optional[int] = None
    tag_ids: Optional[List[int]] = None


@router.get("")
async def get_accounts(
    status: Optional[str] = None,
    group_id: Optional[int] = None,
    tag_id: Optional[int] = None,
    session: AsyncSession = Depends(get_session)
):
    """Get all accounts with optional filters"""
    query = select(Account).options(
        selectinload(Account.proxy),
        selectinload(Account.group),
        selectinload(Account.tags)
    )

    if status:
        query = query.where(Account.status == status)
    if group_id:
        query = query.where(Account.group_id == group_id)
    if tag_id:
        query = query.join(Account.tags).where(AccountTag.id == tag_id)

    result = await session.execute(query)
    accounts = result.scalars().all()

    return {"data": [acc.to_dict() for acc in accounts]}


@router.get("/{account_id}")
async def get_account(
    account_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get single account by ID"""
    query = select(Account).options(
        selectinload(Account.proxy),
        selectinload(Account.group),
        selectinload(Account.tags)
    ).where(Account.id == account_id)

    result = await session.execute(query)
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    return account.to_dict()


@router.post("")
async def create_account(
    data: AccountCreate,
    session: AsyncSession = Depends(get_session)
):
    """Create new account"""
    account = Account(
        phone=data.phone,
        proxy_id=data.proxy_id,
        group_id=data.group_id,
        status="unchecked"
    )

    session.add(account)
    await session.commit()
    await session.refresh(account)

    return account.to_dict()


@router.put("/{account_id}")
async def update_account(
    account_id: int,
    data: AccountUpdate,
    session: AsyncSession = Depends(get_session)
):
    """Update account"""
    query = select(Account).options(
        selectinload(Account.tags)
    ).where(Account.id == account_id)

    result = await session.execute(query)
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    if data.proxy_id is not None:
        account.proxy_id = data.proxy_id
    if data.group_id is not None:
        account.group_id = data.group_id
    if data.tag_ids is not None:
        # Update tags
        tags_result = await session.execute(
            select(AccountTag).where(AccountTag.id.in_(data.tag_ids))
        )
        account.tags = list(tags_result.scalars().all())

    await session.commit()
    await session.refresh(account)

    return account.to_dict()


@router.delete("/{account_id}")
async def delete_account(
    account_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Delete account"""
    query = select(Account).where(Account.id == account_id)
    result = await session.execute(query)
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    await session.delete(account)
    await session.commit()

    return {"success": True}


@router.post("/bulk-action")
async def bulk_action(
    action: str,
    account_ids: List[int],
    value: Optional[int] = None,
    session: AsyncSession = Depends(get_session)
):
    """Perform bulk action on accounts"""
    query = select(Account).where(Account.id.in_(account_ids))
    result = await session.execute(query)
    accounts = result.scalars().all()

    if action == "delete":
        for acc in accounts:
            await session.delete(acc)
    elif action == "set_proxy":
        for acc in accounts:
            acc.proxy_id = value
    elif action == "set_group":
        for acc in accounts:
            acc.group_id = value

    await session.commit()

    return {"success": True, "affected": len(accounts)}


@router.post("/import/tdata")
async def import_tdata(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session)
):
    """Import accounts from tdata zip"""
    # TODO: Implement tdata import
    return {"message": "tdata import not yet implemented"}


@router.post("/import/json")
async def import_json(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session)
):
    """Import accounts from JSON session"""
    # TODO: Implement JSON session import
    return {"message": "JSON import not yet implemented"}
