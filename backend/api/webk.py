"""
WebK Session API endpoints

Provides session data for Telegram WebK viewer in Electron webview.
"""

import logging
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from database.database import get_session
from database.models import Account
from services.session_to_webk import convert_account_to_webk

logger = logging.getLogger(__name__)

router = APIRouter(tags=["webk"])


@router.get("/{account_id}/webk-session")
async def get_webk_session(
    account_id: int,
    fetch_real_salt: bool = True,
    db: AsyncSession = Depends(get_session)
):
    """
    Get WebK session data for an account.

    This endpoint converts the account's Telethon session to WebK localStorage format,
    which can be injected into Telegram Web K for viewing the account.

    Args:
        account_id: Account ID
        fetch_real_salt: Whether to connect to Telegram for real server_salt (recommended, slower)

    Returns:
        WebK session data with proxy configuration
    """
    # Fetch account with proxy
    result = await db.execute(
        select(Account)
        .options(selectinload(Account.proxy))
        .where(Account.id == account_id)
    )
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    if not account.session_string:
        raise HTTPException(status_code=400, detail="Account has no session")

    if not account.telegram_id:
        raise HTTPException(status_code=400, detail="Account has no telegram_id")

    # Proxy is required for security
    if not account.proxy:
        raise HTTPException(status_code=400, detail="Account has no proxy assigned. Proxy is required for WebK viewer.")

    # Check proxy status
    if account.proxy.status not in ("working", "slow", "very_slow", "unchecked"):
        raise HTTPException(
            status_code=400,
            detail=f"Proxy is not working (status: {account.proxy.status})"
        )

    # Use default API credentials if account doesn't have custom ones
    api_id = account.api_id or 2040
    api_hash = account.api_hash or "b18441a1ff607e10a989891a5462e627"

    # Prepare proxy config
    proxy_config = {
        "type": account.proxy.type,
        "host": account.proxy.host,
        "port": account.proxy.port,
        "username": account.proxy.username,
        "password": account.proxy.password,
    }

    try:
        logger.info(f"Converting session for account {account_id} with proxy {proxy_config.get('type')}://{proxy_config.get('host')}:{proxy_config.get('port')}")

        # Convert session to WebK format
        webk_data = await convert_account_to_webk(
            session_string=account.session_string,
            telegram_id=account.telegram_id,
            api_id=api_id,
            api_hash=api_hash,
            proxy=proxy_config,
            device_fingerprint=account.device_fingerprint,
            fetch_real_salt=fetch_real_salt,
        )

        if not webk_data:
            logger.error(f"convert_account_to_webk returned None for account {account_id}")
            raise HTTPException(status_code=500, detail="Failed to convert session to WebK format")

        return {
            "success": True,
            "session_data": webk_data,
            "proxy": proxy_config,
            "device_fingerprint": account.device_fingerprint,
            "account": {
                "id": account.id,
                "telegram_id": account.telegram_id,
                "username": account.username,
                "phone": account.phone,
                "first_name": account.first_name,
                "last_name": account.last_name,
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Error converting session for account {account_id}:\n{error_details}")
        raise HTTPException(status_code=500, detail=f"Session conversion failed: {str(e)}")


@router.post("/{account_id}/webk-session/refresh")
async def refresh_webk_session(
    account_id: int,
    db: AsyncSession = Depends(get_session)
):
    """
    Refresh WebK session with real server_salt from Telegram.

    Always fetches the real salt by connecting to Telegram.
    Use this if the initial session injection fails.
    """
    return await get_webk_session(account_id, fetch_real_salt=True, db=db)
