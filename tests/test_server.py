import hmac
import os
import pytest


def test_verify_api_key_valid(monkeypatch):
    from server.auth import verify_api_key

    monkeypatch.setenv("TI_API_KEY", "a" * 32)
    monkeypatch.delenv("TI_API_KEY_OLD", raising=False)
    assert verify_api_key("a" * 32) is True


def test_verify_api_key_invalid(monkeypatch):
    from server.auth import verify_api_key

    monkeypatch.setenv("TI_API_KEY", "a" * 32)
    monkeypatch.delenv("TI_API_KEY_OLD", raising=False)
    assert verify_api_key("b" * 32) is False


def test_verify_api_key_old_accepted(monkeypatch):
    from server.auth import verify_api_key

    monkeypatch.setenv("TI_API_KEY", "new_key_" + "a" * 24)
    monkeypatch.setenv("TI_API_KEY_OLD", "old_key_" + "b" * 24)
    assert verify_api_key("old_key_" + "b" * 24) is True


def test_verify_api_key_empty_rejected(monkeypatch):
    from server.auth import verify_api_key

    monkeypatch.setenv("TI_API_KEY", "a" * 32)
    monkeypatch.delenv("TI_API_KEY_OLD", raising=False)
    assert verify_api_key("") is False
