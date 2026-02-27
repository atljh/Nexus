"""
Account Safety Validator — fingerprint locking, geo validation, warming stage.

Ported from GramGPT AccountSafetyValidator, adapted for Nexus (SQLAlchemy sync, SQLite).
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Fields compared during fingerprint validation
FINGERPRINT_FIELDS = (
    "device_model",
    "system_version",
    "app_version",
    "lang_code",
    "system_lang_code",
)

# Geo aliases: common names / codes → ISO 3166-1 alpha-2
GEO_ALIASES: Dict[str, str] = {
    # Russia
    "russia": "RU", "ru": "RU", "rus": "RU", "russian federation": "RU",
    # Ukraine
    "ukraine": "UA", "ua": "UA", "ukr": "UA",
    # USA
    "usa": "US", "us": "US", "united states": "US", "america": "US",
    # Germany
    "germany": "DE", "de": "DE", "deu": "DE", "deutschland": "DE",
    # UK
    "uk": "GB", "gb": "GB", "united kingdom": "GB", "england": "GB",
    # France
    "france": "FR", "fr": "FR", "fra": "FR",
    # Netherlands
    "netherlands": "NL", "nl": "NL", "nld": "NL", "holland": "NL",
    # Poland
    "poland": "PL", "pl": "PL", "pol": "PL",
    # Kazakhstan
    "kazakhstan": "KZ", "kz": "KZ", "kaz": "KZ",
    # Turkey
    "turkey": "TR", "tr": "TR", "tur": "TR", "türkiye": "TR",
    # India
    "india": "IN", "in": "IN", "ind": "IN",
    # Brazil
    "brazil": "BR", "br": "BR", "bra": "BR",
    # Canada
    "canada": "CA", "ca": "CA", "can": "CA",
    # Belarus
    "belarus": "BY", "by": "BY", "blr": "BY",
    # Moldova
    "moldova": "MD", "md": "MD", "mda": "MD",
    # Georgia
    "georgia": "GE", "ge": "GE", "geo": "GE",
    # Finland
    "finland": "FI", "fi": "FI", "fin": "FI",
    # Latvia
    "latvia": "LV", "lv": "LV", "lva": "LV",
    # Lithuania
    "lithuania": "LT", "lt": "LT", "ltu": "LT",
    # Estonia
    "estonia": "EE", "ee": "EE", "est": "EE",
}

# Warming stage thresholds: (min_days, max_days, multiplier)
WARMING_STAGES = [
    (0, 3, 0.5),
    (3, 7, 0.7),
    (7, 14, 1.0),
    (14, 30, 1.2),
    (30, None, 1.4),
]


def normalize_geo(geo: Optional[str]) -> Optional[str]:
    """Normalize geo string to ISO 3166-1 alpha-2 code."""
    if not geo:
        return None
    geo_stripped = geo.strip().lower()
    if geo_stripped in GEO_ALIASES:
        return GEO_ALIASES[geo_stripped]
    # Already a 2-letter code
    if len(geo_stripped) == 2:
        return geo_stripped.upper()
    return geo.strip().upper()


class AccountSafetyValidator:
    """Validates account fingerprint, geo, and warming stage before task execution."""

    @staticmethod
    def lock_fingerprint(account, device_params: dict, db: Session) -> bool:
        """
        Lock fingerprint on first connect.
        If account already has fingerprint_locked_at, does nothing.
        Returns True if fingerprint was locked (first time).
        """
        if account.fingerprint_locked_at is not None:
            return False

        if not device_params:
            return False

        # Save device fingerprint if not yet saved
        if not account.device_fingerprint:
            account.device_fingerprint = {
                field: device_params.get(field) for field in FINGERPRINT_FIELDS
            }

        account.fingerprint_locked_at = datetime.now(timezone.utc)
        db.commit()

        logger.info(f"Account {account.id}: fingerprint locked")
        return True

    @staticmethod
    def validate_fingerprint(
        current_params: dict, locked_fingerprint: Optional[dict]
    ) -> Tuple[bool, List[str]]:
        """
        Compare current device params against locked fingerprint.
        Returns (is_valid, list_of_errors).
        If no locked fingerprint exists, always valid (first connect).
        """
        if not locked_fingerprint:
            return True, []

        if not current_params:
            return False, ["No device params provided but fingerprint is locked"]

        errors = []
        for field in FINGERPRINT_FIELDS:
            locked_val = locked_fingerprint.get(field)
            current_val = current_params.get(field)
            # Skip comparison if locked value was not set
            if locked_val is None:
                continue
            if current_val != locked_val:
                errors.append(
                    f"Fingerprint mismatch: {field} "
                    f"(expected={locked_val!r}, got={current_val!r})"
                )

        return len(errors) == 0, errors

    @staticmethod
    def validate_geo_match(
        account_geo: Optional[str], proxy_geo: Optional[str]
    ) -> List[str]:
        """
        Check if account geo matches proxy geo.
        Returns list of warnings (empty if match or if data unavailable).
        """
        if not account_geo or not proxy_geo:
            return []

        norm_account = normalize_geo(account_geo)
        norm_proxy = normalize_geo(proxy_geo)

        if not norm_account or not norm_proxy:
            return []

        if norm_account != norm_proxy:
            return [
                f"Geo mismatch: account geo={norm_account}, "
                f"proxy geo={norm_proxy}"
            ]
        return []

    @staticmethod
    def get_account_age_days(account) -> int:
        """Get account age in days from register_time or created_at."""
        ref_time = account.register_time or account.created_at
        if not ref_time:
            return 0

        now = datetime.now(timezone.utc)
        # Make ref_time timezone-aware if naive
        if ref_time.tzinfo is None:
            ref_time = ref_time.replace(tzinfo=timezone.utc)

        delta = now - ref_time
        return max(0, delta.days)

    @staticmethod
    def get_warming_multiplier(account) -> float:
        """
        Get progressive rate limit multiplier based on account age.
        Younger accounts get lower multipliers (fewer allowed actions).
        """
        age_days = AccountSafetyValidator.get_account_age_days(account)

        for min_days, max_days, multiplier in WARMING_STAGES:
            if max_days is None:
                return multiplier
            if min_days <= age_days < max_days:
                return multiplier

        return 1.0

    @staticmethod
    def validate_before_task(
        account, device_params: dict, db: Session
    ) -> Tuple[bool, List[str], List[str]]:
        """
        Full pre-task validation: fingerprint + geo + warming info.
        Returns (is_valid, warnings, errors).
        """
        warnings: List[str] = []
        errors: List[str] = []

        # 1. Fingerprint validation
        fp_valid, fp_errors = AccountSafetyValidator.validate_fingerprint(
            device_params, account.device_fingerprint
        )
        if not fp_valid:
            errors.extend(fp_errors)

        # 2. Geo validation (warning only)
        proxy_geo = None
        if account.proxy:
            proxy_geo = account.proxy.geo
        geo_warnings = AccountSafetyValidator.validate_geo_match(
            account.geo, proxy_geo
        )
        warnings.extend(geo_warnings)

        # 3. Warming info
        age_days = AccountSafetyValidator.get_account_age_days(account)
        multiplier = AccountSafetyValidator.get_warming_multiplier(account)
        if multiplier < 1.0:
            warnings.append(
                f"Account age: {age_days}d, warming multiplier: {multiplier}x"
            )

        is_valid = len(errors) == 0
        return is_valid, warnings, errors
