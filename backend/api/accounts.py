import json
import tempfile
import zipfile
import shutil
import random
import re
from pathlib import Path
from typing import Optional, List
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from database.database import get_session
from database.models import Account, Proxy, AccountGroup, AccountTag
from utils.encryption import encryption_service
from telegram import (
    convert_tdata_to_session,
    parse_tdata_to_session,
    validate_session,
    SessionManager,
    TDataError,
    account_checker,
    AccountStatus,
    two_factor_manager,
    auth_service,
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


class CheckBatchRequest(BaseModel):
    account_ids: List[int]
    check_spamblock: bool = False
    max_concurrent: int = 3


class ProxyAssignment(BaseModel):
    account_id: int
    proxy_id: Optional[int]


class AssignProxiesRequest(BaseModel):
    assignments: Optional[List[ProxyAssignment]] = None
    # OR bulk assignment
    account_ids: Optional[List[int]] = None
    proxy_ids: Optional[List[int]] = None
    mode: Optional[str] = "sequential"  # sequential | random


# Models for new import flow
class ParsedAccount(BaseModel):
    """Account parsed from files but not yet saved"""
    temp_id: str  # Temporary ID for frontend tracking
    session_string: str
    telegram_id: Optional[int] = None
    phone: Optional[str] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    spamblock: Optional[bool] = None
    register_time: Optional[str] = None
    geo: Optional[str] = None
    source_file: Optional[str] = None


class VerifyAccountRequest(BaseModel):
    """Request to verify a single account"""
    session_string: str
    proxy_id: int


class VerifyAccountsRequest(BaseModel):
    """Request to verify multiple accounts"""
    accounts: List[dict]  # [{session_string, proxy_id, temp_id}]


class SaveAccountsRequest(BaseModel):
    """Request to save verified accounts"""
    accounts: List[dict]  # Full account data with proxy_id and verification results


def extract_api_credentials(json_data: dict) -> dict:
    """
    Extract API credentials from JSON data.
    Supports both naming conventions: api_id/app_id, api_hash/app_hash.
    """
    # api_id (supports api_id and app_id)
    api_id = json_data.get("api_id") or json_data.get("app_id")
    if api_id:
        api_id = int(api_id)

    # api_hash (supports api_hash and app_hash)
    api_hash = json_data.get("api_hash") or json_data.get("app_hash")

    return {
        "api_id": api_id,
        "api_hash": api_hash,
    }


def extract_device_fingerprint(json_data: dict) -> dict:
    """
    Extract device fingerprint from JSON data.
    Supports various naming conventions.
    """
    # Device model
    device_model = (
        json_data.get("device") or
        json_data.get("device_model") or
        json_data.get("device_name")
    )

    # System version (SDK for Android)
    system_version = (
        json_data.get("sdk") or
        json_data.get("system_version") or
        json_data.get("android_version")
    )

    # App version
    app_version = (
        json_data.get("app_version") or
        json_data.get("appVersion")
    )

    # Lang code (supports lang_code and lang_pack)
    lang_code = (
        json_data.get("lang_code") or
        json_data.get("lang_pack") or
        "en"
    )

    # System lang code
    system_lang_code = (
        json_data.get("system_lang_code") or
        json_data.get("system_lang_pack") or
        "en"
    )

    return {
        "device_model": device_model,
        "system_version": system_version,
        "app_version": app_version,
        "lang_code": lang_code,
        "system_lang_code": system_lang_code,
    }


# Country code mapping for GEO detection from phone number
COUNTRY_CODES = {
    "7": "RU", "77": "KZ", "380": "UA", "375": "BY",
    "1": "US", "44": "GB", "49": "DE", "33": "FR",
    "39": "IT", "34": "ES", "48": "PL", "90": "TR",
    "55": "BR", "52": "MX", "86": "CN", "91": "IN",
    "81": "JP", "82": "KR", "84": "VN", "66": "TH",
    "62": "ID", "60": "MY", "63": "PH", "65": "SG",
    "971": "AE", "966": "SA", "972": "IL", "20": "EG",
    "27": "ZA", "234": "NG", "254": "KE",
}


@router.get("")
async def get_accounts(
    status: Optional[str] = None,
    group_id: Optional[int] = None,
    tag_id: Optional[int] = None,
    offset: int = 0,
    limit: int = 0,
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

    if limit > 0:
        query = query.offset(offset).limit(limit)

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
        account.proxy_id = data.proxy_id if data.proxy_id != 0 else None
    if data.group_id is not None:
        account.group_id = data.group_id if data.group_id != 0 else None
    if data.tag_ids is not None:
        tags_result = await session.execute(
            select(AccountTag).where(AccountTag.id.in_(data.tag_ids))
        )
        account.tags = list(tags_result.scalars().all())

    await session.commit()

    # Re-fetch with all relations loaded
    fresh_query = select(Account).options(
        selectinload(Account.proxy),
        selectinload(Account.group),
        selectinload(Account.tags)
    ).where(Account.id == account_id)
    fresh_result = await session.execute(fresh_query)
    account = fresh_result.scalar_one()

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

    # SECURITY: Proxy is required for checking accounts
    if not account.proxy:
        return {"valid": False, "error": "No proxy assigned. Assign a proxy before checking."}

    proxy_config = {
        "type": account.proxy.type,
        "host": account.proxy.host,
        "port": account.proxy.port,
        "username": account.proxy.username,
        "password": account.proxy.password,
    }

    # Get device fingerprint from account
    device_fp = account.device_fingerprint or {}

    # Use phone for consistent device fingerprint
    unique_id = account.phone or str(account.telegram_id) or account.session_string[:32]
    is_valid, user_info, error = await validate_session(
        account.session_string,
        proxy=proxy_config,
        api_id=account.api_id,
        api_hash=account.api_hash,
        unique_id=unique_id,
        device_model=device_fp.get("device_model"),
        system_version=device_fp.get("system_version"),
        app_version=device_fp.get("app_version"),
        lang_code=device_fp.get("lang_code"),
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

    # Get proxy config - REQUIRED for security
    if not proxy_id:
        raise HTTPException(
            status_code=400,
            detail="Proxy is required for tdata import to protect your IP"
        )

    proxy_result = await session.execute(
        select(Proxy).where(Proxy.id == proxy_id)
    )
    proxy = proxy_result.scalar_one_or_none()
    if not proxy:
        raise HTTPException(status_code=404, detail="Proxy not found")

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

    # Get proxy config - REQUIRED for security
    if not proxy_id:
        raise HTTPException(
            status_code=400,
            detail="Proxy is required for import to protect your IP"
        )

    proxy_result = await session.execute(
        select(Proxy).where(Proxy.id == proxy_id)
    )
    proxy = proxy_result.scalar_one_or_none()
    if not proxy:
        raise HTTPException(status_code=404, detail="Proxy not found")

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
        # Use phone from item for consistent device fingerprint
        unique_id = item.get("phone") or str(i)
        is_valid, user_info, error = await validate_session(
            session_string,
            proxy=proxy_config,
            unique_id=unique_id,
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

    # Get proxy config - REQUIRED for security
    if not data.proxy_id:
        raise HTTPException(
            status_code=400,
            detail="Proxy is required for import to protect your IP"
        )

    proxy_result = await session.execute(
        select(Proxy).where(Proxy.id == data.proxy_id)
    )
    proxy = proxy_result.scalar_one_or_none()
    if not proxy:
        raise HTTPException(status_code=404, detail="Proxy not found")

    proxy_config = {
        "type": proxy.type,
        "host": proxy.host,
        "port": proxy.port,
        "username": proxy.username,
        "password": proxy.password,
    }

    # Validate with Telegram
    # Use session string hash for consistent device fingerprint
    is_valid, user_info, error = await validate_session(
        data.session_string,
        proxy=proxy_config,
        unique_id=data.session_string[:32],
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


def detect_geo_from_phone(phone: Optional[str]) -> Optional[str]:
    """Detect country code from phone number"""
    if not phone:
        return None

    # Clean phone number
    cleaned = re.sub(r"[^\d+]", "", phone)
    if cleaned.startswith("+"):
        cleaned = cleaned[1:]

    # Try to match country codes (longest first)
    for length in [3, 2, 1]:
        prefix = cleaned[:length]
        if prefix in COUNTRY_CODES:
            return COUNTRY_CODES[prefix]

    return None


@router.post("/check-batch")
async def check_batch_accounts(
    data: CheckBatchRequest,
    session: AsyncSession = Depends(get_session)
):
    """
    Check multiple accounts in parallel.

    Returns detailed status for each account.
    """
    query = select(Account).options(
        selectinload(Account.proxy)
    ).where(Account.id.in_(data.account_ids))

    result = await session.execute(query)
    accounts = result.scalars().all()

    if not accounts:
        return {"checked": 0, "results": []}

    # Filter accounts without proxy (SECURITY: proxy is required)
    accounts_with_proxy = []
    accounts_without_proxy = []
    for acc in accounts:
        if acc.proxy:
            accounts_with_proxy.append(acc)
        else:
            accounts_without_proxy.append(acc)

    # Set checking status only for accounts with proxy
    for acc in accounts_with_proxy:
        acc.status = "checking"
    await session.commit()

    # Prepare account data for checker
    account_data = []
    for acc in accounts_with_proxy:
        proxy_config = {
            "type": acc.proxy.type,
            "host": acc.proxy.host,
            "port": acc.proxy.port,
            "username": acc.proxy.username,
            "password": acc.proxy.password,
        }

        account_data.append({
            "id": acc.id,
            "session_string": acc.session_string,
            "proxy": proxy_config,
            "phone": acc.phone,  # For consistent device fingerprint
            "telegram_id": acc.telegram_id,
            # API credentials from account
            "api_id": acc.api_id,
            "api_hash": acc.api_hash,
            # Device fingerprint from account
            "device_fingerprint": acc.device_fingerprint,
        })

    # Configure checker concurrency
    account_checker.max_concurrent = data.max_concurrent

    # Check all in parallel
    check_results = await account_checker.check_batch(
        accounts=account_data,
        check_spamblock=data.check_spamblock
    )

    # Update accounts in DB
    results_map = {r.account_id: r for r in check_results}
    response_results = []

    for acc in accounts:
        check_result = results_map.get(acc.id)
        if check_result:
            acc.status = check_result.status.value
            acc.last_checked_at = datetime.now(timezone.utc)

            # Update user info if valid
            if check_result.status == AccountStatus.VALID:
                if check_result.telegram_id:
                    acc.telegram_id = check_result.telegram_id
                if check_result.username:
                    acc.username = check_result.username
                if check_result.first_name:
                    acc.first_name = check_result.first_name
                if check_result.last_name:
                    acc.last_name = check_result.last_name
                if check_result.phone:
                    acc.phone = check_result.phone

            # Update spamblock if checked
            if check_result.spamblock is not None:
                acc.spamblock = check_result.spamblock

            response_results.append({
                "id": acc.id,
                "status": acc.status,
                "telegram_id": acc.telegram_id,
                "username": acc.username,
                "spamblock": acc.spamblock,
                "error": check_result.error
            })

    await session.commit()

    # Mark accounts without proxy as invalid and add to results
    for acc in accounts_without_proxy:
        acc.status = "invalid"
        acc.last_checked_at = datetime.now(timezone.utc)
        response_results.append({
            "id": acc.id,
            "status": "invalid",
            "telegram_id": acc.telegram_id,
            "username": acc.username,
            "spamblock": None,
            "error": "No proxy assigned. Assign a proxy before checking."
        })

    return {
        "checked": len(accounts_with_proxy),
        "skipped_no_proxy": len(accounts_without_proxy),
        "results": response_results
    }


@router.post("/assign-proxies")
async def assign_proxies(
    data: AssignProxiesRequest,
    session: AsyncSession = Depends(get_session)
):
    """
    Assign proxies to accounts.

    Supports two modes:
    1. Individual assignments via 'assignments' list
    2. Bulk assignment via 'account_ids' + 'proxy_ids' with mode (sequential/random)
    """
    if data.assignments:
        # Individual assignments
        account_ids = [a.account_id for a in data.assignments]
        query = select(Account).where(Account.id.in_(account_ids))
        result = await session.execute(query)
        accounts = {acc.id: acc for acc in result.scalars().all()}

        updated = 0
        for assignment in data.assignments:
            acc = accounts.get(assignment.account_id)
            if acc:
                acc.proxy_id = assignment.proxy_id
                updated += 1

        await session.commit()
        return {"success": True, "updated": updated}

    elif data.account_ids and data.proxy_ids:
        # Bulk assignment
        query = select(Account).where(Account.id.in_(data.account_ids))
        result = await session.execute(query)
        accounts = list(result.scalars().all())

        if not accounts:
            return {"success": False, "error": "No accounts found"}

        proxy_ids = data.proxy_ids

        if data.mode == "random":
            # Random assignment
            for acc in accounts:
                acc.proxy_id = random.choice(proxy_ids)
        else:
            # Sequential assignment (with cycling)
            for i, acc in enumerate(accounts):
                acc.proxy_id = proxy_ids[i % len(proxy_ids)]

        await session.commit()
        return {"success": True, "updated": len(accounts)}

    else:
        raise HTTPException(
            status_code=400,
            detail="Either 'assignments' or both 'account_ids' and 'proxy_ids' required"
        )


@router.post("/import/session-json")
async def import_session_json_pairs(
    session_files: List[UploadFile] = File(...),
    json_files: List[UploadFile] = File(...),
    proxy_id: Optional[int] = Form(None),
    session: AsyncSession = Depends(get_session)
):
    """
    Import accounts from session + json file pairs.

    JSON file should contain metadata:
    {
        "id": telegram_id,
        "phone": "+1234567890",
        "username": "username",
        "first_name": "Name",
        "last_name": "Surname",
        "spamblock": false,
        "register_time": "2023-01-01T00:00:00",
        "geo": "RU"
    }
    """
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

    # Build file maps by base name
    def get_base_name(filename: str) -> str:
        """Extract base name without extension and _telethon suffix"""
        name = Path(filename).stem
        if name.endswith("_telethon"):
            name = name[:-9]
        return name.lower()

    session_map = {}
    for sf in session_files:
        base = get_base_name(sf.filename)
        session_map[base] = sf

    json_map = {}
    for jf in json_files:
        base = get_base_name(jf.filename)
        json_map[base] = jf

    # Match pairs
    imported = []
    errors = []

    for base_name, session_file in session_map.items():
        json_file = json_map.get(base_name)

        if not json_file:
            errors.append({
                "file": session_file.filename,
                "error": "No matching JSON file found"
            })
            continue

        try:
            # Read session file
            session_content = await session_file.read()

            # Convert .session file to string
            with tempfile.NamedTemporaryFile(suffix=".session", delete=False) as tmp:
                tmp.write(session_content)
                tmp_path = tmp.name

            try:
                session_string = await SessionManager.session_file_to_string(tmp_path)
            finally:
                Path(tmp_path).unlink(missing_ok=True)

            if not session_string:
                errors.append({
                    "file": session_file.filename,
                    "error": "Failed to convert session file"
                })
                continue

            # Read and parse JSON
            json_content = await json_file.read()
            json_data = json.loads(json_content.decode("utf-8"))

            # Extract metadata
            telegram_id = json_data.get("id") or json_data.get("telegram_id")
            phone = json_data.get("phone") or json_data.get("phone_number")
            username = json_data.get("username")
            first_name = json_data.get("first_name")
            last_name = json_data.get("last_name")
            geo = json_data.get("geo")

            # Parse spamblock - can be bool, string ("free", "banned"), or None
            spamblock_raw = json_data.get("spamblock")
            spamblock = None
            if isinstance(spamblock_raw, bool):
                spamblock = spamblock_raw
            elif isinstance(spamblock_raw, str):
                spamblock = spamblock_raw.lower() not in ("free", "false", "no", "0", "")
            register_time_str = json_data.get("register_time")

            # Parse register_time
            register_time = None
            if register_time_str:
                try:
                    if isinstance(register_time_str, str):
                        register_time = datetime.fromisoformat(
                            register_time_str.replace("Z", "+00:00")
                        )
                except (ValueError, TypeError):
                    pass

            # Detect geo from phone if not provided
            if not geo and phone:
                geo = detect_geo_from_phone(phone)

            # Check for duplicate
            if telegram_id:
                existing = await session.execute(
                    select(Account).where(Account.telegram_id == telegram_id)
                )
                if existing.scalar_one_or_none():
                    errors.append({
                        "file": session_file.filename,
                        "error": f"Account {telegram_id} already exists"
                    })
                    continue

            # Create account
            account = Account(
                telegram_id=telegram_id,
                username=username,
                phone=phone,
                first_name=first_name,
                last_name=last_name,
                session_string=session_string,
                proxy_id=proxy_id,
                status="unchecked",
                extra_data=json_data,
                spamblock=spamblock,
                register_time=register_time,
                geo=geo,
            )

            session.add(account)
            imported.append({
                "file": session_file.filename,
                "telegram_id": telegram_id,
                "username": username,
                "phone": phone,
                "geo": geo,
            })

        except json.JSONDecodeError as e:
            errors.append({
                "file": json_file.filename,
                "error": f"Invalid JSON: {str(e)}"
            })
        except Exception as e:
            errors.append({
                "file": session_file.filename,
                "error": str(e)
            })

    await session.commit()

    return {
        "success": True,
        "imported": len(imported),
        "errors": len(errors),
        "accounts": imported,
        "error_details": errors
    }


# ============================================================
# 2FA Management Endpoints
# ============================================================

class TwoFASetRequest(BaseModel):
    password: str
    hint: Optional[str] = ""


class TwoFAChangeRequest(BaseModel):
    current_password: str
    new_password: str
    new_hint: Optional[str] = ""


class TwoFARemoveRequest(BaseModel):
    current_password: str


class TwoFABulkSetRequest(BaseModel):
    account_ids: List[int]
    password: str
    hint: Optional[str] = ""
    max_concurrent: int = 3


@router.get("/{account_id}/2fa/status")
async def get_2fa_status(
    account_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Check 2FA status for an account."""
    query = select(Account).options(
        selectinload(Account.proxy)
    ).where(Account.id == account_id)

    result = await session.execute(query)
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    if not account.session_string:
        raise HTTPException(status_code=400, detail="No session string")

    proxy_config = None
    if account.proxy:
        proxy_config = {
            "type": account.proxy.type,
            "host": account.proxy.host,
            "port": account.proxy.port,
            "username": account.proxy.username,
            "password": account.proxy.password,
        }

    check_result = await two_factor_manager.check_2fa_status(
        account.session_string,
        proxy=proxy_config,
        api_id=account.api_id,
        api_hash=account.api_hash,
        device_fingerprint=account.device_fingerprint,
        unique_id=account.phone or str(account.telegram_id),
    )

    # Only update database if check succeeded (no error)
    if check_result.error is None:
        account.has_2fa = check_result.has_2fa
        if check_result.password_hint:
            account.password_hint = check_result.password_hint
        await session.commit()

    return {
        "has_2fa": check_result.has_2fa,
        "password_hint": check_result.password_hint,
        "error": check_result.error,
    }


@router.post("/{account_id}/2fa/set")
async def set_2fa(
    account_id: int,
    data: TwoFASetRequest,
    session: AsyncSession = Depends(get_session)
):
    """Set 2FA password on account."""
    query = select(Account).options(
        selectinload(Account.proxy)
    ).where(Account.id == account_id)

    result = await session.execute(query)
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    if not account.session_string:
        raise HTTPException(status_code=400, detail="No session string")

    if account.has_2fa:
        raise HTTPException(status_code=400, detail="2FA already enabled. Use change endpoint.")

    proxy_config = None
    if account.proxy:
        proxy_config = {
            "type": account.proxy.type,
            "host": account.proxy.host,
            "port": account.proxy.port,
            "username": account.proxy.username,
            "password": account.proxy.password,
        }

    set_result = await two_factor_manager.set_2fa(
        account.session_string,
        new_password=data.password,
        hint=data.hint or "",
        proxy=proxy_config,
        api_id=account.api_id,
        api_hash=account.api_hash,
        device_fingerprint=account.device_fingerprint,
        unique_id=account.phone or str(account.telegram_id),
    )

    if not set_result.success:
        raise HTTPException(status_code=400, detail=set_result.error)

    # Update database
    account.has_2fa = True
    account.password_hint = data.hint
    account.two_fa_password = encryption_service.encrypt(data.password)  # Encrypted for security
    account.two_fa_set_at = datetime.now(timezone.utc)

    await session.commit()

    return {"success": True, "message": "2FA enabled successfully"}


@router.post("/{account_id}/2fa/change")
async def change_2fa(
    account_id: int,
    data: TwoFAChangeRequest,
    session: AsyncSession = Depends(get_session)
):
    """Change 2FA password."""
    query = select(Account).options(
        selectinload(Account.proxy)
    ).where(Account.id == account_id)

    result = await session.execute(query)
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    if not account.session_string:
        raise HTTPException(status_code=400, detail="No session string")

    if not account.has_2fa:
        raise HTTPException(status_code=400, detail="2FA not enabled. Use set endpoint.")

    proxy_config = None
    if account.proxy:
        proxy_config = {
            "type": account.proxy.type,
            "host": account.proxy.host,
            "port": account.proxy.port,
            "username": account.proxy.username,
            "password": account.proxy.password,
        }

    change_result = await two_factor_manager.change_2fa(
        account.session_string,
        current_password=data.current_password,
        new_password=data.new_password,
        new_hint=data.new_hint or "",
        proxy=proxy_config,
        api_id=account.api_id,
        api_hash=account.api_hash,
        device_fingerprint=account.device_fingerprint,
        unique_id=account.phone or str(account.telegram_id),
    )

    if not change_result.success:
        raise HTTPException(status_code=400, detail=change_result.error)

    # Update database
    account.password_hint = data.new_hint
    account.two_fa_password = encryption_service.encrypt(data.new_password)  # Encrypted for security
    account.two_fa_set_at = datetime.now(timezone.utc)

    await session.commit()

    return {"success": True, "message": "2FA password changed successfully"}


@router.post("/{account_id}/2fa/remove")
async def remove_2fa(
    account_id: int,
    data: TwoFARemoveRequest,
    session: AsyncSession = Depends(get_session)
):
    """Remove 2FA from account."""
    query = select(Account).options(
        selectinload(Account.proxy)
    ).where(Account.id == account_id)

    result = await session.execute(query)
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    if not account.session_string:
        raise HTTPException(status_code=400, detail="No session string")

    if not account.has_2fa:
        raise HTTPException(status_code=400, detail="2FA not enabled")

    proxy_config = None
    if account.proxy:
        proxy_config = {
            "type": account.proxy.type,
            "host": account.proxy.host,
            "port": account.proxy.port,
            "username": account.proxy.username,
            "password": account.proxy.password,
        }

    remove_result = await two_factor_manager.remove_2fa(
        account.session_string,
        current_password=data.current_password,
        proxy=proxy_config,
        api_id=account.api_id,
        api_hash=account.api_hash,
        device_fingerprint=account.device_fingerprint,
        unique_id=account.phone or str(account.telegram_id),
    )

    if not remove_result.success:
        raise HTTPException(status_code=400, detail=remove_result.error)

    # Update database
    account.has_2fa = False
    account.password_hint = None
    account.two_fa_password = None
    account.two_fa_set_at = None

    await session.commit()

    return {"success": True, "message": "2FA removed successfully"}


@router.post("/2fa/bulk-set")
async def bulk_set_2fa(
    data: TwoFABulkSetRequest,
    session: AsyncSession = Depends(get_session)
):
    """Set 2FA password on multiple accounts in parallel."""
    import asyncio

    query = select(Account).options(
        selectinload(Account.proxy)
    ).where(Account.id.in_(data.account_ids))

    result = await session.execute(query)
    accounts = list(result.scalars().all())

    if not accounts:
        return {"success": False, "results": [], "error": "No accounts found"}

    semaphore = asyncio.Semaphore(data.max_concurrent)
    results = []

    async def set_2fa_for_account(account):
        async with semaphore:
            if not account.session_string:
                return {"id": account.id, "success": False, "error": "No session string"}

            if account.has_2fa:
                return {"id": account.id, "success": False, "error": "2FA already enabled"}

            proxy_config = None
            if account.proxy:
                proxy_config = {
                    "type": account.proxy.type,
                    "host": account.proxy.host,
                    "port": account.proxy.port,
                    "username": account.proxy.username,
                    "password": account.proxy.password,
                }

            try:
                set_result = await two_factor_manager.set_2fa(
                    account.session_string,
                    new_password=data.password,
                    hint=data.hint or "",
                    proxy=proxy_config,
                    api_id=account.api_id,
                    api_hash=account.api_hash,
                    device_fingerprint=account.device_fingerprint,
                    unique_id=account.phone or str(account.telegram_id),
                )

                if set_result.success:
                    account.has_2fa = True
                    account.password_hint = data.hint
                    account.two_fa_password = encryption_service.encrypt(data.password)
                    account.two_fa_set_at = datetime.now(timezone.utc)
                    return {"id": account.id, "success": True}
                else:
                    return {"id": account.id, "success": False, "error": set_result.error}
            except Exception as e:
                return {"id": account.id, "success": False, "error": str(e)}

    tasks = [set_2fa_for_account(acc) for acc in accounts]
    results = await asyncio.gather(*tasks)

    await session.commit()

    success_count = sum(1 for r in results if r["success"])
    return {
        "success": True,
        "results": results,
        "total": len(accounts),
        "succeeded": success_count,
        "failed": len(accounts) - success_count,
    }


# ============================================================
# New Account Authorization Endpoints
# ============================================================

class AuthStartRequest(BaseModel):
    phone: str
    proxy: Optional[dict] = None


class AuthVerifyRequest(BaseModel):
    session_id: str
    code: str
    password: Optional[str] = None


class AuthResendRequest(BaseModel):
    session_id: str


class AuthCancelRequest(BaseModel):
    session_id: str


@router.post("/auth/start")
async def auth_start(
    data: AuthStartRequest,
    session: AsyncSession = Depends(get_session)
):
    """
    Start phone authorization flow.

    Send SMS code to the provided phone number.
    Returns session_id for next steps.
    """
    result = await auth_service.start_auth(
        phone=data.phone,
        proxy=data.proxy,
    )

    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)

    return {
        "session_id": result.session_id,
        "phone": result.phone,
        "status": "code_sent",
        "message": f"Code sent to {result.phone}",
    }


@router.post("/auth/verify")
async def auth_verify(
    data: AuthVerifyRequest,
    session: AsyncSession = Depends(get_session)
):
    """
    Verify SMS code and complete authorization.

    If 2FA is enabled, returns status="password_required".
    Call again with password to complete.
    """
    result = await auth_service.verify_code(
        session_id=data.session_id,
        code=data.code,
        password=data.password,
    )

    if not result.success and result.status != "password_required":
        raise HTTPException(status_code=400, detail=result.error)

    if result.status == "password_required":
        return {
            "status": "password_required",
            "message": "2FA password required",
        }

    # Success - create account
    if result.account_data:
        # Check if account already exists
        existing = await session.execute(
            select(Account).where(
                Account.telegram_id == result.account_data["telegram_id"]
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail=f"Account {result.account_data['telegram_id']} already exists"
            )

        # Detect geo from phone
        geo = detect_geo_from_phone(result.account_data.get("phone"))

        # Create new account
        account = Account(
            telegram_id=result.account_data["telegram_id"],
            username=result.account_data.get("username"),
            first_name=result.account_data.get("first_name"),
            last_name=result.account_data.get("last_name"),
            phone=result.account_data.get("phone"),
            session_string=result.session_string,
            status="valid",
            geo=geo,
        )

        session.add(account)
        await session.commit()
        await session.refresh(account)

        return {
            "status": "success",
            "account_id": account.id,
            "telegram_id": result.account_data["telegram_id"],
            "username": result.account_data.get("username"),
            "phone": result.account_data.get("phone"),
            "message": "Account authorized successfully",
        }

    return {"status": "success"}


@router.post("/auth/resend")
async def auth_resend(data: AuthResendRequest):
    """Resend SMS code for existing session."""
    result = await auth_service.resend_code(data.session_id)

    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)

    return {
        "session_id": result.session_id,
        "phone": result.phone,
        "status": "code_sent",
        "message": f"Code resent to {result.phone}",
    }


@router.post("/auth/cancel")
async def auth_cancel(data: AuthCancelRequest):
    """Cancel ongoing authorization."""
    await auth_service.cancel_auth(data.session_id)

    return {"status": "cancelled", "message": "Authorization cancelled"}


@router.get("/auth/session/{session_id}")
async def auth_session_info(session_id: str):
    """Get info about auth session."""
    info = auth_service.get_session_info(session_id)

    if not info:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    return info


# ============================================================
# New Import Flow: Parse -> Assign Proxy -> Verify -> Save
# ============================================================

@router.post("/import/parse")
async def parse_import_files(
    session_files: List[UploadFile] = File(default=[]),
    json_files: List[UploadFile] = File(default=[]),
    tdata_file: Optional[UploadFile] = File(default=None),
):
    """
    Parse import files without saving to database.
    Returns list of parsed accounts for preview.
    """
    import uuid

    parsed_accounts = []
    errors = []

    print(f"[PARSE] session_files={len(session_files)}, json_files={len(json_files)}, tdata={tdata_file is not None}")
    for sf in session_files:
        print(f"[PARSE] session: '{sf.filename}' size={sf.size}")
    for jf in json_files:
        print(f"[PARSE] json: '{jf.filename}' size={jf.size}")

    # Helper to get base name
    def get_base_name(filename: str) -> str:
        name = Path(filename).stem
        if name.endswith("_telethon"):
            name = name[:-9]
        return name.lower()

    # Process tdata
    if tdata_file:
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                zip_path = temp_path / "tdata.zip"

                content = await tdata_file.read()
                zip_path.write_bytes(content)

                extract_path = temp_path / "extracted"
                with zipfile.ZipFile(zip_path, 'r') as zf:
                    zf.extractall(extract_path)

                # Find tdata folder
                tdata_path = None
                for root, dirs, files in extract_path.walk():
                    if "tdata" in dirs:
                        tdata_path = root / "tdata"
                        break

                if not tdata_path:
                    if (extract_path / "key_data").exists() or (extract_path / "key_datas").exists():
                        tdata_path = extract_path
                    else:
                        raise HTTPException(status_code=400, detail="tdata folder not found in archive")

                # Convert tdata to session (without validation - proxy not assigned yet)
                session_string = await parse_tdata_to_session(tdata_path)

                parsed_accounts.append({
                    "temp_id": str(uuid.uuid4()),
                    "session_string": session_string,
                    "source_file": tdata_file.filename,
                    "telegram_id": None,
                    "phone": None,
                    "username": None,
                    "first_name": None,
                    "last_name": None,
                    "spamblock": None,
                    "register_time": None,
                    "geo": None,
                })

        except Exception as e:
            errors.append({
                "file": tdata_file.filename,
                "error": str(e)
            })

    # Process session + json pairs
    if session_files and json_files:
        session_map = {}
        for sf in session_files:
            base = get_base_name(sf.filename)
            print(f"[PARSE] session base: '{base}' <- '{sf.filename}'")
            session_map[base] = sf

        json_map = {}
        for jf in json_files:
            base = get_base_name(jf.filename)
            print(f"[PARSE] json base: '{base}' <- '{jf.filename}'")
            json_map[base] = jf

        print(f"[PARSE] session keys: {list(session_map.keys())}")
        print(f"[PARSE] json keys: {list(json_map.keys())}")

        for base_name, session_file in session_map.items():
            json_file = json_map.get(base_name)

            if not json_file:
                errors.append({
                    "file": session_file.filename,
                    "error": "No matching JSON file found"
                })
                continue

            try:
                # Read session file
                session_content = await session_file.read()
                print(f"[PARSE] Processing pair '{base_name}': session={len(session_content)} bytes")

                # Convert .session file to string
                with tempfile.NamedTemporaryFile(suffix=".session", delete=False) as tmp:
                    tmp.write(session_content)
                    tmp_path = tmp.name

                try:
                    session_string = await SessionManager.session_file_to_string(tmp_path)
                except Exception as conv_err:
                    print(f"[PARSE] Session conversion ERROR for '{base_name}': {conv_err}")
                    raise
                finally:
                    Path(tmp_path).unlink(missing_ok=True)

                if not session_string:
                    print(f"[PARSE] Empty session string for '{base_name}'")
                    errors.append({
                        "file": session_file.filename,
                        "error": "Failed to convert session file"
                    })
                    continue

                # Read and parse JSON
                json_content = await json_file.read()
                json_data = json.loads(json_content.decode("utf-8"))

                # Extract metadata
                telegram_id = json_data.get("id") or json_data.get("telegram_id")
                phone = json_data.get("phone") or json_data.get("phone_number")
                username = json_data.get("username")
                first_name = json_data.get("first_name")
                last_name = json_data.get("last_name")
                geo = json_data.get("geo")

                # Extract API credentials from JSON
                api_creds = extract_api_credentials(json_data)

                # Extract device fingerprint from JSON
                device_fp = extract_device_fingerprint(json_data)

                # Parse spamblock
                spamblock_raw = json_data.get("spamblock")
                spamblock = None
                if isinstance(spamblock_raw, bool):
                    spamblock = spamblock_raw
                elif isinstance(spamblock_raw, str):
                    spamblock = spamblock_raw.lower() not in ("free", "false", "no", "0", "")

                register_time_str = json_data.get("register_time")

                # Detect geo from phone if not provided
                if not geo and phone:
                    geo = detect_geo_from_phone(phone)

                parsed_accounts.append({
                    "temp_id": str(uuid.uuid4()),
                    "session_string": session_string,
                    "source_file": session_file.filename,
                    "telegram_id": telegram_id,
                    "phone": phone,
                    "username": username,
                    "first_name": first_name,
                    "last_name": last_name,
                    "spamblock": spamblock,
                    "register_time": register_time_str,
                    "geo": geo,
                    # API credentials from JSON
                    "api_id": api_creds.get("api_id"),
                    "api_hash": api_creds.get("api_hash"),
                    # Device fingerprint from JSON
                    "device_fingerprint": device_fp,
                })

            except Exception as e:
                errors.append({
                    "file": session_file.filename,
                    "error": str(e)
                })

    print(f"[PARSE] RESULT: {len(parsed_accounts)} accounts, {len(errors)} errors")
    for e in errors:
        print(f"[PARSE] ERROR: {e}")

    return {
        "accounts": parsed_accounts,
        "errors": errors,
        "total_parsed": len(parsed_accounts),
        "total_errors": len(errors)
    }


@router.post("/import/parse-tdata")
async def parse_tdata_folder(
    tdata_files: List[UploadFile] = File(default=[]),
    # Paths are sent as form fields: path_0, path_1, etc.
):
    """
    Parse tdata folder files (uploaded as individual files with paths).
    Supports multiple tdata folders in one request.
    Reconstructs folder structure and converts each to session.
    """
    import uuid
    import re

    parsed_accounts = []
    errors = []

    if not tdata_files:
        return {
            "accounts": [],
            "errors": [{"file": "tdata", "error": "No files uploaded"}],
            "total_parsed": 0,
            "total_errors": 1
        }

    try:
        # Group files by their tdata root path
        # Path format: "parent/account1/tdata/key_data" -> group by "parent/account1/tdata"
        tdata_groups: dict[str, list[tuple[UploadFile, str]]] = {}

        for file in tdata_files:
            filename = file.filename or ""
            normalized = filename.replace('\\', '/')
            # Find tdata path in filename
            match = re.search(r'^(.*?/tdata|tdata)/', normalized)
            if match:
                tdata_root = match.group(1)
                # Get relative path after tdata/
                if normalized.startswith('tdata/'):
                    rel_path = normalized[6:]  # Remove "tdata/"
                else:
                    rel_path = normalized.split('/tdata/', 1)[-1]
                if tdata_root not in tdata_groups:
                    tdata_groups[tdata_root] = []
                tdata_groups[tdata_root].append((file, rel_path))

        # Fallback: selected folder IS a tdata folder (not named "tdata")
        # Detect by presence of key_data/key_datas among uploaded files
        if not tdata_groups:
            has_key_data = any(
                (f.filename or "").replace('\\', '/').split('/')[-1] in ("key_data", "key_datas")
                for f in tdata_files
            )
            if has_key_data:
                # Determine root folder name from first file
                root_folder = None
                for f in tdata_files:
                    normalized = (f.filename or "").replace('\\', '/')
                    parts = normalized.split('/')
                    if len(parts) >= 2:
                        root_folder = parts[0]
                        break
                if root_folder:
                    for f in tdata_files:
                        normalized = (f.filename or "").replace('\\', '/')
                        prefix = root_folder + '/'
                        if normalized.startswith(prefix):
                            rel_path = normalized[len(prefix):]
                            tdata_groups.setdefault(root_folder, []).append((f, rel_path))

        if not tdata_groups:
            return {
                "accounts": [],
                "errors": [{"file": "tdata", "error": "No valid tdata paths found"}],
                "total_parsed": 0,
                "total_errors": 1
            }

        # Process each tdata group separately
        for tdata_root, files in tdata_groups.items():
            try:
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_path = Path(temp_dir)
                    tdata_path = temp_path / "tdata"
                    tdata_path.mkdir(parents=True, exist_ok=True)

                    # Save files preserving folder structure
                    for file, rel_path in files:
                        content = await file.read()
                        await file.seek(0)  # Reset for potential re-read

                        file_path = tdata_path / rel_path
                        file_path.parent.mkdir(parents=True, exist_ok=True)
                        file_path.write_bytes(content)

                    # Check if we have valid tdata structure
                    has_key_data = (tdata_path / "key_data").exists() or (tdata_path / "key_datas").exists()

                    if not has_key_data:
                        errors.append({
                            "file": tdata_root,
                            "error": "Invalid tdata structure - key_data not found"
                        })
                        continue

                    # Convert tdata to session (without validation - proxy not assigned yet)
                    try:
                        session_string = await parse_tdata_to_session(tdata_path)

                        # Extract folder name for source_file
                        source_name = tdata_root.rsplit('/', 1)[0] if '/' in tdata_root else tdata_root
                        source_name = source_name.rsplit('/', 1)[-1] if '/' in source_name else source_name

                        parsed_accounts.append({
                            "temp_id": str(uuid.uuid4()),
                            "session_string": session_string,
                            "source_file": source_name or "tdata",
                            "telegram_id": None,
                            "phone": None,
                            "username": None,
                            "first_name": None,
                            "last_name": None,
                            "spamblock": None,
                            "register_time": None,
                            "geo": None,
                        })
                    except Exception as e:
                        errors.append({
                            "file": tdata_root,
                            "error": str(e)
                        })

            except Exception as e:
                errors.append({
                    "file": tdata_root,
                    "error": f"Failed to process: {str(e)}"
                })

    except Exception as e:
        errors.append({
            "file": "tdata",
            "error": f"Failed to process tdata folders: {str(e)}"
        })

    return {
        "accounts": parsed_accounts,
        "errors": errors,
        "total_parsed": len(parsed_accounts),
        "total_errors": len(errors)
    }


@router.post("/import/verify")
async def verify_parsed_accounts(
    data: VerifyAccountsRequest,
    session: AsyncSession = Depends(get_session)
):
    """
    Verify parsed accounts with their assigned proxies.
    Each account must have a proxy_id assigned.
    """
    results = []

    for acc_data in data.accounts:
        session_string = acc_data.get("session_string")
        proxy_id = acc_data.get("proxy_id")
        temp_id = acc_data.get("temp_id")

        if not session_string:
            results.append({
                "temp_id": temp_id,
                "status": "error",
                "error": "No session string"
            })
            continue

        if not proxy_id:
            results.append({
                "temp_id": temp_id,
                "status": "error",
                "error": "No proxy assigned"
            })
            continue

        # Get proxy config
        proxy_result = await session.execute(
            select(Proxy).where(Proxy.id == proxy_id)
        )
        proxy = proxy_result.scalar_one_or_none()

        if not proxy:
            results.append({
                "temp_id": temp_id,
                "status": "error",
                "error": "Proxy not found"
            })
            continue

        proxy_config = {
            "type": proxy.type,
            "host": proxy.host,
            "port": proxy.port,
            "username": proxy.username,
            "password": proxy.password,
        }

        # Get API credentials and device fingerprint from JSON
        api_id = acc_data.get("api_id")
        api_hash = acc_data.get("api_hash")
        device_fp = acc_data.get("device_fingerprint") or {}

        # Validate session with Telegram
        # Use phone for consistent device fingerprinting
        unique_id = acc_data.get("phone") or temp_id
        try:
            is_valid, user_info, error = await validate_session(
                session_string,
                proxy=proxy_config,
                api_id=api_id,  # From JSON file
                api_hash=api_hash,  # From JSON file
                unique_id=unique_id,
                # Device fingerprint from JSON
                device_model=device_fp.get("device_model"),
                system_version=device_fp.get("system_version"),
                app_version=device_fp.get("app_version"),
                lang_code=device_fp.get("lang_code"),
            )

            if is_valid and user_info:
                results.append({
                    "temp_id": temp_id,
                    "status": "valid",
                    "telegram_id": user_info.get("telegram_id"),
                    "username": user_info.get("username"),
                    "phone": user_info.get("phone"),
                    "first_name": user_info.get("first_name"),
                    "last_name": user_info.get("last_name"),
                    # Return api_id/api_hash/device_fingerprint for saving
                    "api_id": api_id,
                    "api_hash": api_hash,
                    "device_fingerprint": device_fp,
                })
            else:
                results.append({
                    "temp_id": temp_id,
                    "status": "invalid",
                    "error": error or "Session invalid"
                })

        except Exception as e:
            results.append({
                "temp_id": temp_id,
                "status": "error",
                "error": str(e)
            })

    return {
        "results": results,
        "total_valid": len([r for r in results if r.get("status") == "valid"]),
        "total_invalid": len([r for r in results if r.get("status") != "valid"])
    }


@router.post("/import/save")
async def save_verified_accounts(
    data: SaveAccountsRequest,
    session: AsyncSession = Depends(get_session)
):
    """
    Save verified accounts to database.
    """
    saved = []
    errors = []

    for acc_data in data.accounts:
        try:
            telegram_id = acc_data.get("telegram_id")

            # Check for duplicate
            if telegram_id:
                existing = await session.execute(
                    select(Account).where(Account.telegram_id == telegram_id)
                )
                if existing.scalar_one_or_none():
                    errors.append({
                        "temp_id": acc_data.get("temp_id"),
                        "error": "Account already exists"
                    })
                    continue

            # Parse register_time
            register_time = None
            register_time_str = acc_data.get("register_time")
            if register_time_str:
                try:
                    if isinstance(register_time_str, str):
                        register_time = datetime.fromisoformat(
                            register_time_str.replace("Z", "+00:00")
                        )
                except (ValueError, TypeError):
                    pass

            # Create account
            account = Account(
                telegram_id=telegram_id,
                phone=acc_data.get("phone"),
                username=acc_data.get("username"),
                first_name=acc_data.get("first_name"),
                last_name=acc_data.get("last_name"),
                session_string=acc_data.get("session_string"),
                proxy_id=acc_data.get("proxy_id"),
                status=acc_data.get("status", "valid"),
                spamblock=acc_data.get("spamblock"),
                register_time=register_time,
                geo=acc_data.get("geo"),
                # API credentials from JSON
                api_id=acc_data.get("api_id"),
                api_hash=acc_data.get("api_hash"),
                # Device fingerprint from JSON
                device_fingerprint=acc_data.get("device_fingerprint"),
            )

            session.add(account)
            await session.flush()

            saved.append({
                "temp_id": acc_data.get("temp_id"),
                "account_id": account.id,
                "telegram_id": telegram_id
            })

        except Exception as e:
            errors.append({
                "temp_id": acc_data.get("temp_id"),
                "error": str(e)
            })

    await session.commit()

    return {
        "saved": saved,
        "errors": errors,
        "total_saved": len(saved),
        "total_errors": len(errors)
    }
