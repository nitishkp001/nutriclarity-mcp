"""Tests for optional write support (config + write client), fully mocked."""

from __future__ import annotations

import httpx
import pytest
import respx

from nutriclarity_mcp.client import OpenFoodFactsError, OpenFoodFactsWriteClient
from nutriclarity_mcp.config import (
    PRODUCTION_BASE_URL,
    SANDBOX_BASE_URL,
    load_write_config,
)


def test_write_disabled_without_credentials():
    cfg = load_write_config({})
    assert cfg.enabled is False


def test_write_defaults_to_sandbox():
    cfg = load_write_config({"OFF_USERNAME": "alice", "OFF_PASSWORD": "pw"})
    assert cfg.enabled is True
    assert cfg.environment == "sandbox"
    assert cfg.base_url == SANDBOX_BASE_URL


def test_write_production_requires_explicit_opt_in():
    cfg = load_write_config(
        {"OFF_USERNAME": "alice", "OFF_PASSWORD": "pw", "OFF_ENVIRONMENT": "production"}
    )
    assert cfg.environment == "production"
    assert cfg.base_url == PRODUCTION_BASE_URL


def test_write_unknown_environment_falls_back_to_sandbox():
    cfg = load_write_config(
        {"OFF_USERNAME": "alice", "OFF_PASSWORD": "pw", "OFF_ENVIRONMENT": "prod"}
    )
    assert cfg.environment == "sandbox"


@respx.mock
async def test_write_product_success():
    route = respx.post(f"{SANDBOX_BASE_URL}/cgi/product_jqm2.pl").mock(
        return_value=httpx.Response(200, json={"status": 1, "status_verbose": "fields saved"})
    )
    async with OpenFoodFactsWriteClient("alice", "pw", base_url=SANDBOX_BASE_URL) as client:
        result = await client.write_product("3017620422003", {"product_name": "Test"})

    assert result["status"] == 1
    # Credentials and identifying params are included in the POST body.
    sent = route.calls.last.request.content.decode()
    assert "user_id=alice" in sent
    assert "app_name=nutriclarity-mcp" in sent


@respx.mock
async def test_write_product_rejected():
    respx.post(f"{SANDBOX_BASE_URL}/cgi/product_jqm2.pl").mock(
        return_value=httpx.Response(200, json={"status": 0, "status_verbose": "bad login"})
    )
    async with OpenFoodFactsWriteClient("alice", "pw", base_url=SANDBOX_BASE_URL) as client:
        with pytest.raises(OpenFoodFactsError):
            await client.write_product("3017620422003", {"product_name": "Test"})


@respx.mock
async def test_write_product_bad_login_gives_clear_message():
    respx.post(f"{SANDBOX_BASE_URL}/cgi/product_jqm2.pl").mock(
        return_value=httpx.Response(403, text="<html>incorrect user name or password</html>")
    )
    async with OpenFoodFactsWriteClient("alice", "pw", base_url=SANDBOX_BASE_URL) as client:
        with pytest.raises(OpenFoodFactsError, match="Authentication failed"):
            await client.write_product("3017620422003", {"product_name": "Test"})


async def test_write_product_rejects_non_numeric_barcode():
    async with OpenFoodFactsWriteClient("alice", "pw", base_url=SANDBOX_BASE_URL) as client:
        with pytest.raises(ValueError):
            await client.write_product("abc", {"product_name": "Test"})
