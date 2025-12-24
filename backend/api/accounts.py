import json
import tempfile
import zipfile
import shutil
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from database.database import get_session
from database.models import Account, Proxy, AccountGroup, AccountTag
from telegram import (
    convert_tdata_to_session,
    validate_session,
    SessionManager,
    TDataError,
)

router = APIRouter()


class AccountCreate(BaseModel):
    phone: Optional[str] = None
    session_string: Optional[str] = None
    proxy_id: Optional[int] = None
    group_id: Optional[int] = None


class AccountUpdate(BaseModel):
    proxy_id: Optional[int] = None
    group_id: Optional[int] = None
    tag_ids: Optional[List[int]] = None


class SessionImport(BaseModel):
    session_string: str
    proxy_id: Optional[int] = None


@router.get("")
async def get_accounts(
    status: Optional[str] = None,
    group_id: Optional[int] = None,
    tag_id: Optional[int] = None,
    session: AsyncSession = Depends(get_session)
):
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
    account = Account(
        phone=data.phone,
        session_string=data.session_string,
        proxy_id=data.proxy_id,
        group_id=data.group_id,
        status="unchecked" if not data.session_string else "pending"
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


@router.post("/{account_id}/check")
async def check_account(
    account_id: int,
    session: AsyncSession = Depends(get_session)
):
    query = select(Account).options(
        selectinload(Account.proxy)
    ).where(Account.id == account_id)

    result = await session.execute(query)
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    if not account.session_string:
        return {"valid": False, "error": "No session string"}

    proxy_config = None
    if account.proxy:
        proxy_config = {
            "type": account.proxy.type,
            "host": account.proxy.host,
            "port": account.proxy.port,
            "username": account.proxy.username,
            "password": account.proxy.password,
        }

    is_valid, user_info, error = await validate_session(
        account.session_string,
        proxy=proxy_config
    )

    if is_valid and user_info:
        account.telegram_id = user_info.get("telegram_id")
        account.username = user_info.get("username")
        account.first_name = user_info.get("first_name")
        account.last_name = user_info.get("last_name")
        if user_info.get("phone"):
            account.phone = user_info.get("phone")
        account.status = "valid"
    else:
        account.status = "invalid"

    await session.commit()

    return {
        "valid": is_valid,
        "user_info": user_info,
        "error": error
    }


@router.post("/import/tdata")
async def import_tdata(
    file: UploadFile = File(...),
    proxy_id: Optional[int] = Form(None),
    session: AsyncSession = Depends(get_session)
):
    """
    Import account from tdata zip archive.

    The zip should contain tdata folder from Telegram Desktop.
    """
    if not file.filename.endswith('.zip'):
        raise HTTPException(
            status_code=400,
            detail="File must be a .zip archive containing tdata folder"
        )

    proxy_config = None
    if proxy_id:
        proxy_result = await session.execute(
            select(Proxy).where(Proxy.id == proxy_id)
        )
        proxy = proxy_result.scalar_one_or_none()
        if proxy:
            proxy_config = {
                "type": proxy.type,
                "host": proxy.host,
                "port": proxy.port,
                "username": proxy.username,
                "password": proxy.password,
            }

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        zip_path = temp_path / "upload.zip"
        with open(zip_path, "wb") as f:
            content = await file.read()
            f.write(content)

        extract_path = temp_path / "extracted"
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_path)

        tdata_path = None
        for item in extract_path.rglob("tdata"):
            if item.is_dir():
                tdata_path = item
                break

        if not tdata_path:
            if (extract_path / "key_data").exists() or (extract_path / "key_datas").exists():
                tdata_path = extract_path
            else:
                raise HTTPException(
                    status_code=400,
                    detail="tdata folder not found in archive"
                )

        try:
            # Convert tdata to session
            session_string, metadata = await convert_tdata_to_session(
                str(tdata_path),
                proxy=proxy_config
            )

            # Check if account already exists
            existing = await session.execute(
                select(Account).where(
                    Account.telegram_id == metadata.get("telegram_id")
                )
            )
            if existing.scalar_one_or_none():
                raise HTTPException(
                    status_code=400,
                    detail=f"Account {metadata.get('telegram_id')} already exists"
                )

            # Create account
            account = Account(
                telegram_id=metadata.get("telegram_id"),
                username=metadata.get("username"),
                first_name=metadata.get("first_name"),
                last_name=metadata.get("last_name"),
                phone=metadata.get("phone"),
                session_string=session_string,
                proxy_id=proxy_id,
                status="valid"
            )

            session.add(account)
            await session.commit()
            await session.refresh(account)

            return {
                "success": True,
                "account": account.to_dict(),
                "message": f"Successfully imported @{metadata.get('username', metadata.get('telegram_id'))}"
            }

        except TDataError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


@router.post("/import/json")
async def import_json_session(
    file: UploadFile = File(...),
    proxy_id: Optional[int] = Form(None),
    session: AsyncSession = Depends(get_session)
):
    """
    Import accounts from JSON file containing session strings.

    JSON format:
    [
        {"session_string": "...", "phone": "+1234567890"},
        ...
    ]
    or single object:
    {"session_string": "...", "phone": "+1234567890"}
    """
    if not file.filename.endswith('.json'):
        raise HTTPException(
            status_code=400,
            detail="File must be a .json file"
        )

    try:
        content = await file.read()
        data = json.loads(content.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")

    # Normalize to list
    if isinstance(data, dict):
        data = [data]

    if not isinstance(data, list):
        raise HTTPException(status_code=400, detail="JSON must be array or object")

    # Get proxy config
    proxy_config = None
    if proxy_id:
        proxy_result = await session.execute(
            select(Proxy).where(Proxy.id == proxy_id)
        )
        proxy = proxy_result.scalar_one_or_none()
        if proxy:
            proxy_config = {
                "type": proxy.type,
                "host": proxy.host,
                "port": proxy.port,
                "username": proxy.username,
                "password": proxy.password,
            }

    imported = []
    errors = []

    for i, item in enumerate(data):
        session_string = item.get("session_string") or item.get("session")

        if not session_string:
            errors.append({"index": i, "error": "Missing session_string"})
            continue

        # Validate session string format
        if not SessionManager.validate_session_string(session_string):
            errors.append({"index": i, "error": "Invalid session string format"})
            continue

        # Validate with Telegram
        is_valid, user_info, error = await validate_session(
            session_string,
            proxy=proxy_config
        )

        if not is_valid:
            errors.append({"index": i, "error": error or "Session invalid"})
            continue

        # Check if account exists
        existing = await session.execute(
            select(Account).where(
                Account.telegram_id == user_info.get("telegram_id")
            )
        )
        if existing.scalar_one_or_none():
            errors.append({
                "index": i,
                "error": f"Account {user_info.get('telegram_id')} already exists"
            })
            continue

        # Create account
        account = Account(
            telegram_id=user_info.get("telegram_id"),
            username=user_info.get("username"),
            first_name=user_info.get("first_name"),
            last_name=user_info.get("last_name"),
            phone=user_info.get("phone") or item.get("phone"),
            session_string=session_string,
            proxy_id=proxy_id,
            status="valid"
        )

        session.add(account)
        imported.append(user_info)

    await session.commit()

    return {
        "success": True,
        "imported": len(imported),
        "errors": errors,
        "accounts": imported
    }


@router.post("/import/session-string")
async def import_session_string(
    data: SessionImport,
    session: AsyncSession = Depends(get_session)
):
    """Import single account from session string"""

    # Validate format
    if not SessionManager.validate_session_string(data.session_string):
        raise HTTPException(status_code=400, detail="Invalid session string format")

    # Get proxy config
    proxy_config = None
    if data.proxy_id:
        proxy_result = await session.execute(
            select(Proxy).where(Proxy.id == data.proxy_id)
        )
        proxy = proxy_result.scalar_one_or_none()
        if proxy:
            proxy_config = {
                "type": proxy.type,
                "host": proxy.host,
                "port": proxy.port,
                "username": proxy.username,
                "password": proxy.password,
            }

    # Validate with Telegram
    is_valid, user_info, error = await validate_session(
        data.session_string,
        proxy=proxy_config
    )

    if not is_valid:
        raise HTTPException(status_code=400, detail=error or "Session is invalid")

    # Check if exists
    existing = await session.execute(
        select(Account).where(
            Account.telegram_id == user_info.get("telegram_id")
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail=f"Account {user_info.get('telegram_id')} already exists"
        )

    # Create account
    account = Account(
        telegram_id=user_info.get("telegram_id"),
        username=user_info.get("username"),
        first_name=user_info.get("first_name"),
        last_name=user_info.get("last_name"),
        phone=user_info.get("phone"),
        session_string=data.session_string,
        proxy_id=data.proxy_id,
        status="valid"
    )

    session.add(account)
    await session.commit()
    await session.refresh(account)

    return {
        "success": True,
        "account": account.to_dict()
    }
