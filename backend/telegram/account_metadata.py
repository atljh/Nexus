"""
Helpers for resolving API credentials and device fingerprint metadata.

Used to keep account connection params consistent across import/check/worker flows.
"""

import json
from typing import Any, Dict, Optional, Tuple


FINGERPRINT_FIELDS = (
    "device_model",
    "system_version",
    "app_version",
    "lang_code",
    "system_lang_code",
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
        ) or "en-us",
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

    device_fingerprint = merge_device_fingerprint(
        getattr(account, "device_fingerprint", None),
        extra_data,
    )

    return api_id, api_hash, device_fingerprint
