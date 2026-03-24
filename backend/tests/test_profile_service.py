"""Tests for telegram.profile_service privacy updates."""

import importlib
import sys
from pathlib import Path

import pytest
from telethon.tl.functions.account import SetPrivacyRequest
from telethon.tl.types import (
    InputPrivacyKeyAddedByPhone,
    InputPrivacyKeyPhoneNumber,
    InputPrivacyValueAllowContacts,
    InputPrivacyValueDisallowAll,
)

sys.path.insert(0, str(Path(__file__).parent.parent))

importlib.import_module("telegram.profile_service")
from telegram.profile_service import ProfileService


class _PrivacyClient:
    def __init__(self, authorized: bool = True):
        self.authorized = authorized
        self.requests = []

    async def connect(self):
        return None

    async def is_user_authorized(self):
        return self.authorized

    async def disconnect(self):
        return None

    async def __call__(self, request):
        self.requests.append(request)
        return object()


@pytest.mark.asyncio
async def test_hide_phone_number_updates_visibility_and_discovery(monkeypatch):
    service = ProfileService()
    client = _PrivacyClient()

    monkeypatch.setattr(service, "_create_client", lambda *args, **kwargs: client)

    result = await service.hide_phone_number("session")

    assert result.success is True
    assert result.updated_fields == [
        "phone_number_visibility",
        "phone_discovery",
    ]
    assert len(client.requests) == 2
    assert all(isinstance(request, SetPrivacyRequest) for request in client.requests)
    assert isinstance(client.requests[0].key, InputPrivacyKeyPhoneNumber)
    assert isinstance(client.requests[0].rules[0], InputPrivacyValueDisallowAll)
    assert isinstance(client.requests[1].key, InputPrivacyKeyAddedByPhone)
    assert isinstance(client.requests[1].rules[0], InputPrivacyValueAllowContacts)


@pytest.mark.asyncio
async def test_hide_phone_number_fails_for_unauthorized_session(monkeypatch):
    service = ProfileService()
    client = _PrivacyClient(authorized=False)

    monkeypatch.setattr(service, "_create_client", lambda *args, **kwargs: client)

    result = await service.hide_phone_number("session")

    assert result.success is False
    assert result.errors == {"auth": "Session not authorized"}
    assert client.requests == []
