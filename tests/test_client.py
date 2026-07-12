"""Tests for the Open Food Facts client and formatters (fully mocked, no network)."""

from __future__ import annotations

import httpx
import pytest
import respx

from nutriclarity_mcp.client import (
    BASE_URL,
    OpenFoodFactsClient,
    OpenFoodFactsError,
    ProductNotFoundError,
)
from nutriclarity_mcp.formatters import (
    format_comparison,
    format_product,
    format_scores,
    format_search_results,
)

NUTELLA = {
    "code": "3017620422003",
    "product_name": "Nutella",
    "brands": "Ferrero",
    "quantity": "400 g",
    "nutriscore_grade": "e",
    "nova_group": 4,
    "ecoscore_grade": "d",
    "nutriments": {
        "energy-kcal_100g": 539,
        "fat_100g": 30.9,
        "saturated-fat_100g": 10.6,
        "sugars_100g": 56.3,
        "proteins_100g": 6.3,
        "salt_100g": 0.107,
    },
}

OATMILK = {
    "code": "1234567890123",
    "product_name": "Oat Drink",
    "brands": "Oatly",
    "nutriscore_grade": "b",
    "nova_group": 3,
    "nutriments": {
        "energy-kcal_100g": 46,
        "fat_100g": 1.5,
        "sugars_100g": 3.3,
        "proteins_100g": 1.0,
        "salt_100g": 0.09,
    },
}


@respx.mock
async def test_get_product_found():
    respx.get(f"{BASE_URL}/api/v2/product/3017620422003.json").mock(
        return_value=httpx.Response(200, json={"status": 1, "product": NUTELLA})
    )
    async with OpenFoodFactsClient() as client:
        product = await client.get_product("3017620422003")
    assert product["product_name"] == "Nutella"


@respx.mock
async def test_get_product_not_found():
    respx.get(f"{BASE_URL}/api/v2/product/0000000000000.json").mock(
        return_value=httpx.Response(200, json={"status": 0, "product": None})
    )
    async with OpenFoodFactsClient() as client:
        with pytest.raises(ProductNotFoundError):
            await client.get_product("0000000000000")


async def test_get_product_rejects_non_numeric():
    async with OpenFoodFactsClient() as client:
        with pytest.raises(ValueError):
            await client.get_product("abc")


@respx.mock
async def test_get_product_http_error():
    respx.get(f"{BASE_URL}/api/v2/product/3017620422003.json").mock(
        return_value=httpx.Response(500)
    )
    async with OpenFoodFactsClient() as client:
        with pytest.raises(OpenFoodFactsError):
            await client.get_product("3017620422003")


@respx.mock
async def test_search():
    respx.get(f"{BASE_URL}/cgi/search.pl").mock(
        return_value=httpx.Response(200, json={"products": [NUTELLA]})
    )
    async with OpenFoodFactsClient() as client:
        products = await client.search("nutella")
    assert len(products) == 1
    assert products[0]["code"] == "3017620422003"


async def test_search_rejects_empty():
    async with OpenFoodFactsClient() as client:
        with pytest.raises(ValueError):
            await client.search("   ")


def test_format_product():
    out = format_product(NUTELLA)
    assert "Nutella" in out
    assert "Energy: 539 kcal" in out
    assert "Nutri-Score: E" in out
    assert "NOVA group: 4" in out


def test_format_scores_empty():
    assert format_scores({"nutriments": {}}) == ""


def test_format_search_results_empty():
    assert 'No products found for "xyz"' in format_search_results([], "xyz")


def test_format_comparison():
    out = format_comparison([NUTELLA, OATMILK])
    assert "Nutella" in out
    assert "Oat Drink" in out
    assert "Energy" in out
