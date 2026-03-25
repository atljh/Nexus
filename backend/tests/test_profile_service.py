"""Tests for telegram.profile_service privacy updates."""

import importlib
import sys
from pathlib import Path

import pytest
from telethon.tl.functions.account import GetPrivacyRequest, SetPrivacyRequest
from telethon.tl.types import (
    InputPrivacyKeyAddedByPhone,
    InputPrivacyKeyPhoneNumber,
    InputPrivacyValueAllowContacts,
    InputPrivacyValueDisallowAll,
    PrivacyValueAllowContacts,
    PrivacyValueDisallowAll,
)
from telethon.tl.types.account import PrivacyRules

sys.path.insert(0, str(Path(__file__).parent.parent))

importlib.import_module("telegram.profile_service")
from telegram.profile_service import ProfileService


class _PrivacyClient:
    def __init__(self, authorized: bool = True, privacy_rules: dict[type, list] | None = None):
        self.authorized = authorized
        self.privacy_rules = privacy_rules or {}
        self.requests = []

    async def connect(self):
        return None

    async def is_user_authorized(self):
        return self.authorized

    async def disconnect(self):
        return None

    async def __call__(self, request):
        self.requests.append(request)
        if isinstance(request, GetPrivacyRequest):
            return PrivacyRules(
                rules=self.privacy_rules.get(type(request.key), []),
                chats=[],
                users=[],
            )
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
    set_requests = [request for request in client.requests if isinstance(request, SetPrivacyRequest)]
    assert len(set_requests) == 2
    assert isinstance(set_requests[0].key, InputPrivacyKeyPhoneNumber)
    assert isinstance(set_requests[0].rules[0], InputPrivacyValueDisallowAll)
    assert isinstance(set_requests[1].key, InputPrivacyKeyAddedByPhone)
    assert isinstance(set_requests[1].rules[0], InputPrivacyValueAllowContacts)


@pytest.mark.asyncio
async def test_hide_phone_number_fails_for_unauthorized_session(monkeypatch):
    service = ProfileService()
    client = _PrivacyClient(authorized=False)

    monkeypatch.setattr(service, "_create_client", lambda *args, **kwargs: client)

    result = await service.hide_phone_number("session")

    assert result.success is False
    assert result.errors == {"auth": "Session not authorized"}
    assert client.requests == []


@pytest.mark.asyncio
async def test_hide_phone_number_treats_matching_rules_as_success(monkeypatch):
    service = ProfileService()
    client = _PrivacyClient(privacy_rules={
        InputPrivacyKeyPhoneNumber: [PrivacyValueDisallowAll()],
        InputPrivacyKeyAddedByPhone: [PrivacyValueAllowContacts()],
    })

    monkeypatch.setattr(service, "_create_client", lambda *args, **kwargs: client)

    result = await service.hide_phone_number("session")

    assert result.success is True
    assert result.updated_fields == [
        "phone_number_visibility",
        "phone_discovery",
    ]
    assert len(client.requests) == 2
    assert all(isinstance(request, GetPrivacyRequest) for request in client.requests)
