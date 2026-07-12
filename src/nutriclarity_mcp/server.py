"""FastMCP server exposing Open Food Facts nutrition tools."""

from __future__ import annotations

import asyncio

from fastmcp import FastMCP

from .client import (
    OpenFoodFactsClient,
    OpenFoodFactsError,
    ProductNotFoundError,
)
from .formatters import (
    format_comparison,
    format_product,
    format_scores,
    format_search_results,
)

mcp = FastMCP(
    name="NutriClarity",
    instructions=(
        "Provides food nutrition data from Open Food Facts. Look up products by "
        "barcode, search by name/brand, get Nutri-Score/NOVA/Eco-Score ratings, "
        "and compare products side by side."
    ),
)


@mcp.tool
async def get_product_by_barcode(barcode: str) -> str:
    """Get full nutrition facts for a food product by its barcode (EAN/UPC).

    Args:
        barcode: The product barcode, digits only (e.g. "3017620422003").

    Returns nutrition per 100g, scores, allergens and ingredients when available.
    """
    async with OpenFoodFactsClient() as client:
        try:
            product = await client.get_product(barcode)
        except ProductNotFoundError as exc:
            return str(exc)
        except (OpenFoodFactsError, ValueError) as exc:
            return f"Error: {exc}"
    return format_product(product)


@mcp.tool
async def search_products(query: str, page_size: int = 5) -> str:
    """Search food products by name or brand.

    Args:
        query: Free-text search, e.g. "nutella" or "oat milk".
        page_size: Number of results to return (1-25, default 5).

    Returns a compact list including barcodes; use get_product_by_barcode for
    full details on any result.
    """
    async with OpenFoodFactsClient() as client:
        try:
            products = await client.search(query, page_size=page_size)
        except (OpenFoodFactsError, ValueError) as exc:
            return f"Error: {exc}"
    return format_search_results(products, query)


@mcp.tool
async def get_nutrition_scores(barcode: str) -> str:
    """Get the Nutri-Score, NOVA processing group and Eco-Score for a product.

    Args:
        barcode: The product barcode, digits only.
    """
    async with OpenFoodFactsClient() as client:
        try:
            product = await client.get_product(barcode)
        except ProductNotFoundError as exc:
            return str(exc)
        except (OpenFoodFactsError, ValueError) as exc:
            return f"Error: {exc}"
    scores = format_scores(product, header=True)
    return scores or "No Nutri-Score/NOVA/Eco-Score data available for this product."


@mcp.tool
async def compare_products(barcodes: list[str]) -> str:
    """Compare the nutrition of two or more products side by side.

    Args:
        barcodes: A list of 2+ product barcodes (digits only).

    Returns a per-100g comparison table. Products that cannot be found are noted.
    """
    if len(barcodes) < 2:
        return "Please provide at least two barcodes to compare."

    async with OpenFoodFactsClient() as client:
        results = await asyncio.gather(
            *(client.get_product(b) for b in barcodes),
            return_exceptions=True,
        )

    products = []
    problems = []
    for barcode, result in zip(barcodes, results, strict=True):
        if isinstance(result, dict):
            products.append(result)
        else:
            problems.append(f"  - {barcode}: {result}")

    if len(products) < 2:
        detail = "\n".join(problems)
        return f"Not enough products could be loaded to compare.\n{detail}"

    out = format_comparison(products)
    if problems:
        out += "\n\nCould not load:\n" + "\n".join(problems)
    return out


def main() -> None:
    """Console-script entry point. Runs the server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
