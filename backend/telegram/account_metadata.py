"""
Helpers for resolving API credentials and device fingerprint metadata.

Used to keep account connection params consistent across import/check/worker flows.
"""

import json
from typing import Any, Dict, Optional, Tuple

from .device_generator import (
    detect_platform_from_api_id,
    generate_device_fingerprint,
    generate_fingerprint_for_api,
    get_tdesktop_fingerprint,
)


FINGERPRINT_FIELDS = (
    "device_model",
    "system_version",
    "app_version",
    "lang_code",
    "system_lang_code",
)
CORE_FINGERPRINT_FIELDS = (
    "device_model",
    "system_version",
    "app_version",
)


def normalize_json_dict(value: Optional[Any]) -> Dict[str, Any]:
    """Normalize value to dict (supports plain JSON string)."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return {}
    return {}


def normalize_device_fingerprint(value: Optional[Any]) -> Dict[str, Any]:
    """Normalize stored fingerprint to a dict with known keys."""
    data = normalize_json_dict(value)
    if not data:
        return {}
    result: Dict[str, Any] = {}
    for field in FINGERPRINT_FIELDS:
        if data.get(field) is not None:
            result[field] = data.get(field)
    return result


def extract_api_credentials(metadata: Optional[Any]) -> Tuple[Optional[int], Optional[str]]:
    """
    Extract api_id/api_hash from metadata.
    Supports aliases: app_id/app_hash.
    """
    data = normalize_json_dict(metadata)
    api_id_raw = data.get("api_id") or data.get("app_id")
    api_hash_raw = data.get("api_hash") or data.get("app_hash")

    api_id: Optional[int] = None
    if api_id_raw is not None and str(api_id_raw).strip():
        try:
            api_id = int(api_id_raw)
        except (TypeError, ValueError):
            api_id = None

    api_hash: Optional[str] = None
    if api_hash_raw is not None and str(api_hash_raw).strip():
        api_hash = str(api_hash_raw).strip()

    return api_id, api_hash


def extract_device_fingerprint(metadata: Optional[Any]) -> Dict[str, Any]:
    """
    Extract device params from metadata, including alias keys.
    Supports nested "device_fingerprint" object.
    """
    data = normalize_json_dict(metadata)
    if not data:
        return {}

    nested_fp = normalize_device_fingerprint(data.get("device_fingerprint"))

    def pick(*keys: str) -> Optional[Any]:
        for key in keys:
            value = data.get(key)
            if value is not None and value != "":
                return value
        return None

    result = {
        "device_model": nested_fp.get("device_model") or pick(
            "device_model", "device", "device_name"
        ),
        "system_version": nested_fp.get("system_version") or pick(
            "system_version", "sdk", "android_version"
        ),
        "app_version": nested_fp.get("app_version") or pick(
            "app_version", "appVersion"
        ),
        "lang_code": nested_fp.get("lang_code") or pick(
            "lang_code", "lang_pack"
        ) or "en",
        "system_lang_code": nested_fp.get("system_lang_code") or pick(
            "system_lang_code", "system_lang_pack"
        ) or "en-US",
    }

    return {k: v for k, v in result.items() if v is not None}


def merge_device_fingerprint(
    primary: Optional[Any],
    fallback: Optional[Any],
) -> Dict[str, Any]:
    """Merge fingerprint fields from primary and fallback sources."""
    primary_fp = normalize_device_fingerprint(primary)
    fallback_fp = extract_device_fingerprint(fallback)

    merged = dict(primary_fp)
    for field in FINGERPRINT_FIELDS:
        if merged.get(field) is None and fallback_fp.get(field) is not None:
            merged[field] = fallback_fp.get(field)
    return merged


def has_complete_device_fingerprint(value: Optional[Any]) -> bool:
    """Return True when device_model/system_version/app_version are all present."""
    fingerprint = normalize_device_fingerprint(value)
    return all(str(fingerprint.get(field) or "").strip() for field in CORE_FINGERPRINT_FIELDS)


def ensure_complete_device_fingerprint(
    primary: Optional[Any],
    fallback: Optional[Any] = None,
    *,
    unique_id: Optional[Any] = None,
    api_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Return a fingerprint with core device fields filled in when possible.

    Some legacy imports only store lang_code/system_lang_code. In that case we
    synthesize a stable fallback fingerprint based on unique_id and api_id.
    """
    merged = merge_device_fingerprint(primary, fallback)
    if has_complete_device_fingerprint(merged):
        return merged

    seed = str(unique_id).strip() if unique_id is not None and str(unique_id).strip() else ""
    if not seed:
        return merged

    lang_code = str(merged.get("lang_code") or "en")
    system_lang_code = str(merged.get("system_lang_code") or "en-US")

    if api_id is not None:
        platform = detect_platform_from_api_id(api_id)
        if platform == "desktop":
            generated = get_tdesktop_fingerprint(
                lang_code=lang_code,
                system_lang_code=system_lang_code,
            )
        else:
            generated = generate_fingerprint_for_api(
                unique_id=seed,
                api_id=api_id,
                lang_code=lang_code,
                system_lang_code=system_lang_code,
            )
    else:
        generated = generate_device_fingerprint(
            unique_id=seed,
            lang_code=lang_code,
            system_lang_code=system_lang_code,
        )

    completed = dict(merged)
    for field in FINGERPRINT_FIELDS:
        if completed.get(field) in (None, ""):
            completed[field] = generated.get(field)
    return {k: v for k, v in completed.items() if v is not None}


def resolve_account_connection_params(account: Any) -> Tuple[Optional[int], Optional[str], Dict[str, Any]]:
    """
    Resolve (api_id, api_hash, device_fingerprint) for account connection.

    Priority:
    1. Account columns (`api_id`, `api_hash`, `device_fingerprint`)
    2. `account.extra_data` aliases (`app_id`, `app_hash`, device aliases)
    """
    api_id = getattr(account, "api_id", None)
    api_hash = getattr(account, "api_hash", None)

    extra_data = normalize_json_dict(getattr(account, "extra_data", None))
    if api_id is None or not api_hash:
        extra_api_id, extra_api_hash = extract_api_credentials(extra_data)
        if api_id is None:
            api_id = extra_api_id
        if not api_hash:
            api_hash = extra_api_hash

    unique_id = (
        getattr(account, "phone", None)
        or getattr(account, "telegram_id", None)
        or getattr(account, "id", None)
        or getattr(account, "session_string", None)
    )

    device_fingerprint = ensure_complete_device_fingerprint(
        getattr(account, "device_fingerprint", None),
        extra_data,
        unique_id=unique_id,
        api_id=api_id,
    )

    return api_id, api_hash, device_fingerprint
