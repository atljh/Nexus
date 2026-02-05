"""
Device Fingerprint Generator - генерация реалистичных параметров устройства.

Используется для создания консистентных device fingerprints на основе unique_id
(например, номера телефона). Один и тот же unique_id всегда вернёт одинаковый fingerprint.

Поддерживаемые платформы:
- android: Samsung, Xiaomi, Google Pixel, OnePlus
- ios: iPhone модели
- desktop: Windows/macOS Desktop клиент
"""

import hashlib
from typing import Literal, TypedDict, Optional


class DeviceFingerprint(TypedDict):
    """Структура fingerprint устройства."""

    api_id: int
    api_hash: str
    device_model: str
    system_version: str
    app_version: str
    lang_code: str
    system_lang_code: str


# Официальные API credentials из Telegram
OFFICIAL_APIS = {
    "android": {
        "api_id": 6,
        "api_hash": "eb06d4abfb49dc3eeb1aeb98ae0f581e",
    },
    "ios": {
        "api_id": 10840,
        "api_hash": "33c45224029d59cb3ad0c16134215aeb",
    },
    "desktop": {
        "api_id": 2040,
        "api_hash": "b18441a1ff607e10a989891a5462e627",
    },
}

# Реальные Android устройства (модель + SDK версия)
ANDROID_DEVICES = [
    # Samsung Galaxy S серия
    {"device_model": "Samsung SM-G998B", "system_version": "SDK 31"},  # S21 Ultra
    {"device_model": "Samsung SM-S908B", "system_version": "SDK 33"},  # S22 Ultra
    {"device_model": "Samsung SM-S918B", "system_version": "SDK 34"},  # S23 Ultra
    {"device_model": "Samsung SM-G991B", "system_version": "SDK 31"},  # S21
    {"device_model": "Samsung SM-G996B", "system_version": "SDK 31"},  # S21+
    # Samsung Galaxy A серия
    {"device_model": "Samsung SM-A536B", "system_version": "SDK 33"},  # A53 5G
    {"device_model": "Samsung SM-A546B", "system_version": "SDK 34"},  # A54 5G
    {"device_model": "Samsung SM-A526B", "system_version": "SDK 31"},  # A52 5G
    {"device_model": "Samsung SM-A336B", "system_version": "SDK 32"},  # A33 5G
    {"device_model": "Samsung SM-A155F", "system_version": "SDK 34"},  # A15
    # Xiaomi / Redmi
    {"device_model": "Xiaomi M2101K6G", "system_version": "SDK 30"},  # Redmi Note 10 Pro
    {"device_model": "Xiaomi 2201116SG", "system_version": "SDK 32"},  # 12 Pro
    {"device_model": "Xiaomi 23049RAD8C", "system_version": "SDK 34"},  # Redmi Note 12
    {"device_model": "Xiaomi 2203121C", "system_version": "SDK 33"},  # Redmi Note 11 Pro
    {"device_model": "Xiaomi 22101316G", "system_version": "SDK 33"},  # Redmi Note 12 Pro
    {"device_model": "Xiaomi 2107113SG", "system_version": "SDK 31"},  # 11T Pro
    # Google Pixel
    {"device_model": "Google Pixel 7", "system_version": "SDK 33"},
    {"device_model": "Google Pixel 7 Pro", "system_version": "SDK 34"},
    {"device_model": "Google Pixel 7a", "system_version": "SDK 33"},
    {"device_model": "Google Pixel 8", "system_version": "SDK 34"},
    {"device_model": "Google Pixel 8 Pro", "system_version": "SDK 34"},
    {"device_model": "Google Pixel 6a", "system_version": "SDK 33"},
    # OnePlus
    {"device_model": "OnePlus NE2215", "system_version": "SDK 33"},  # 10 Pro
    {"device_model": "OnePlus CPH2449", "system_version": "SDK 33"},  # 11
    {"device_model": "OnePlus LE2115", "system_version": "SDK 31"},  # 9 Pro
    {"device_model": "OnePlus KB2003", "system_version": "SDK 30"},  # 8T
    # Realme
    {"device_model": "Realme RMX3630", "system_version": "SDK 33"},  # GT Neo 5
    {"device_model": "Realme RMX3561", "system_version": "SDK 32"},  # GT 2 Pro
    # OPPO
    {"device_model": "OPPO CPH2451", "system_version": "SDK 33"},  # Find X5 Pro
    {"device_model": "OPPO CPH2305", "system_version": "SDK 32"},  # Reno 7
    # Huawei
    {"device_model": "Huawei VOG-L29", "system_version": "SDK 29"},  # P30 Pro
    {"device_model": "Huawei ELS-NX9", "system_version": "SDK 29"},  # P40 Pro
]

# Реальные iOS устройства
IOS_DEVICES = [
    # iPhone 13 серия
    {"device_model": "iPhone 13", "system_version": "15.6"},
    {"device_model": "iPhone 13 mini", "system_version": "15.5"},
    {"device_model": "iPhone 13 Pro", "system_version": "16.0"},
    {"device_model": "iPhone 13 Pro Max", "system_version": "16.1"},
    # iPhone 14 серия
    {"device_model": "iPhone 14", "system_version": "16.4"},
    {"device_model": "iPhone 14 Plus", "system_version": "16.5"},
    {"device_model": "iPhone 14 Pro", "system_version": "17.0"},
    {"device_model": "iPhone 14 Pro Max", "system_version": "17.1"},
    # iPhone 15 серия
    {"device_model": "iPhone 15", "system_version": "17.2"},
    {"device_model": "iPhone 15 Plus", "system_version": "17.3"},
    {"device_model": "iPhone 15 Pro", "system_version": "17.4"},
    {"device_model": "iPhone 15 Pro Max", "system_version": "17.5"},
    # iPhone 12 серия
    {"device_model": "iPhone 12", "system_version": "15.4"},
    {"device_model": "iPhone 12 Pro", "system_version": "16.2"},
    {"device_model": "iPhone 12 Pro Max", "system_version": "16.3"},
    {"device_model": "iPhone SE", "system_version": "16.0"},
]

# Desktop варианты
DESKTOP_DEVICES = [
    {"device_model": "Desktop", "system_version": "Windows 10"},
    {"device_model": "Desktop", "system_version": "Windows 11"},
    {"device_model": "MacBook Pro", "system_version": "macOS 13.0"},
    {"device_model": "MacBook Air", "system_version": "macOS 14.0"},
    {"device_model": "iMac", "system_version": "macOS 13.5"},
]

# Актуальные версии приложений
APP_VERSIONS = {
    "android": "10.14.5",
    "ios": "10.3.1",
    "desktop": "4.16.8",
}

Platform = Literal["android", "ios", "desktop"]


def generate_device_fingerprint(
    unique_id: str,
    platform: Platform = "android",
    lang_code: str = "en",
    system_lang_code: str = "en",
) -> DeviceFingerprint:
    """
    Генерирует консистентный device fingerprint на основе unique_id.

    Один и тот же unique_id ВСЕГДА вернёт одинаковый fingerprint.
    Это важно для сохранения консистентности сессии.

    Args:
        unique_id: Уникальный идентификатор (например, номер телефона или session name)
        platform: Платформа - "android", "ios" или "desktop"
        lang_code: Код языка (default: "en")
        system_lang_code: Системный код языка (default: "en")

    Returns:
        DeviceFingerprint с полным набором параметров
    """
    # Генерируем hash для консистентного выбора устройства
    hash_bytes = hashlib.md5(unique_id.encode()).digest()
    hash_int = int.from_bytes(hash_bytes, byteorder="big")

    # Выбираем устройство на основе hash
    if platform == "android":
        devices = ANDROID_DEVICES
    elif platform == "ios":
        devices = IOS_DEVICES
    else:
        devices = DESKTOP_DEVICES

    device = devices[hash_int % len(devices)]
    api_config = OFFICIAL_APIS[platform]

    return DeviceFingerprint(
        api_id=api_config["api_id"],
        api_hash=api_config["api_hash"],
        device_model=device["device_model"],
        system_version=device["system_version"],
        app_version=APP_VERSIONS[platform],
        lang_code=lang_code,
        system_lang_code=system_lang_code,
    )


def detect_platform_from_api_id(api_id: int) -> Platform:
    """
    Определяет платформу по api_id.

    Args:
        api_id: Telegram API ID

    Returns:
        Platform: "android", "ios" или "desktop"
    """
    # Android API IDs
    if api_id in (4, 5, 6, 21724, 16623):
        return "android"
    # iOS API IDs
    elif api_id in (8, 10840):
        return "ios"
    # macOS API ID
    elif api_id == 2834:
        return "desktop"
    # Desktop API IDs (Telegram Desktop)
    elif api_id in (2040, 17349):
        return "desktop"
    # Web API IDs - treat as desktop
    elif api_id == 2496:
        return "desktop"
    # Default to android (most common)
    else:
        return "android"


def generate_fingerprint_for_api(
    unique_id: str,
    api_id: int,
    lang_code: str = "en",
    system_lang_code: str = "en",
) -> dict:
    """
    Генерирует device fingerprint, сохраняя указанный api_id.

    Полезно когда api_id уже известен из сессии, но нужно
    сгенерировать реалистичные device_model и system_version.

    Args:
        unique_id: Уникальный идентификатор
        api_id: Telegram API ID (будет сохранён)
        lang_code: Код языка
        system_lang_code: Системный код языка

    Returns:
        Dict с device параметрами (без api_id/api_hash)
    """
    platform = detect_platform_from_api_id(api_id)

    hash_bytes = hashlib.md5(unique_id.encode()).digest()
    hash_int = int.from_bytes(hash_bytes, byteorder="big")

    if platform == "android":
        devices = ANDROID_DEVICES
    elif platform == "ios":
        devices = IOS_DEVICES
    else:
        devices = DESKTOP_DEVICES

    device = devices[hash_int % len(devices)]

    return {
        "device_model": device["device_model"],
        "system_version": device["system_version"],
        "app_version": APP_VERSIONS[platform],
        "lang_code": lang_code,
        "system_lang_code": system_lang_code,
    }


def get_device_for_session(
    session_string: str,
    phone: Optional[str] = None,
    platform: Platform = "android",
) -> DeviceFingerprint:
    """
    Получает fingerprint для сессии.

    Использует телефон если есть, иначе хэш от session_string.

    Args:
        session_string: Telethon session string
        phone: Номер телефона (опционально)
        platform: Платформа

    Returns:
        DeviceFingerprint
    """
    unique_id = phone if phone else hashlib.md5(session_string.encode()).hexdigest()[:16]
    return generate_device_fingerprint(unique_id, platform)
