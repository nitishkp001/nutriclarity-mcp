"""FastMCP server exposing Open Food Facts nutrition tools."""

from __future__ import annotations

import asyncio

from fastmcp import FastMCP

from .client import (
    OpenFoodFactsClient,
    OpenFoodFactsError,
    OpenFoodFactsWriteClient,
    ProductNotFoundError,
)
from .config import load_write_config
from .formatters import (
    format_alternatives,
    format_comparison,
    format_product,
    format_scores,
    format_search_results,
    nutriscore_rank,
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


# --- Optional write support (add/edit products) ---------------------------
# These tools are registered only when OFF_USERNAME and OFF_PASSWORD are set.
# Writes target the Open Food Facts sandbox unless OFF_ENVIRONMENT=production.

# Maps friendly tool args -> (Open Food Facts nutriment key, unit).
_NUTRIMENT_MAP: dict[str, tuple[str, str]] = {
    "energy_kcal": ("energy-kcal", "kcal"),
    "fat": ("fat", "g"),
    "saturated_fat": ("saturated-fat", "g"),
    "carbohydrates": ("carbohydrates", "g"),
    "sugars": ("sugars", "g"),
    "fiber": ("fiber", "g"),
    "proteins": ("proteins", "g"),
    "salt": ("salt", "g"),
}

_write_config = load_write_config()

if _write_config.enabled:

    @mcp.tool
    async def add_or_update_product(
        barcode: str,
        product_name: str | None = None,
        brands: str | None = None,
        quantity: str | None = None,
        categories: str | None = None,
        ingredients_text: str | None = None,
        nutrition_data_per: str = "100g",
        energy_kcal: float | None = None,
        fat: float | None = None,
        saturated_fat: float | None = None,
        carbohydrates: float | None = None,
        sugars: float | None = None,
        fiber: float | None = None,
        proteins: float | None = None,
        salt: float | None = None,
    ) -> str:
        """Create or edit a product in Open Food Facts (WRITE).

        Only the fields you pass are changed; omitted fields are left untouched.
        This writes to a real, shared database, so provide accurate data taken
        from the physical product label.

        Args:
            barcode: Product barcode (digits only). Required.
            product_name: Product name.
            brands: Brand(s), comma-separated.
            quantity: Net quantity, e.g. "400 g".
            categories: Categories, comma-separated.
            ingredients_text: Full ingredients list as printed on the label.
            nutrition_data_per: "100g" (default) or "serving" — the basis for the
                nutriment values below.
            energy_kcal, fat, saturated_fat, carbohydrates, sugars, fiber,
            proteins, salt: Nutriment values (energy in kcal, others in grams)
                per `nutrition_data_per`.
        """
        text_fields = {
            "product_name": product_name,
            "brands": brands,
            "quantity": quantity,
            "categories": categories,
            "ingredients_text": ingredients_text,
        }
        fields: dict[str, str] = {k: v for k, v in text_fields.items() if v is not None}

        nutriment_args = {
            "energy_kcal": energy_kcal,
            "fat": fat,
            "saturated_fat": saturated_fat,
            "carbohydrates": carbohydrates,
            "sugars": sugars,
            "fiber": fiber,
            "proteins": proteins,
            "salt": salt,
        }
        has_nutriments = any(v is not None for v in nutriment_args.values())
        if has_nutriments:
            fields["nutrition_data_per"] = nutrition_data_per
            for arg, value in nutriment_args.items():
                if value is None:
                    continue
                off_key, unit = _NUTRIMENT_MAP[arg]
                fields[f"nutriment_{off_key}"] = str(value)
                fields[f"nutriment_{off_key}_unit"] = unit

        if not fields:
            return "Nothing to write: provide at least one field to add or update."

        async with OpenFoodFactsWriteClient(
            _write_config.username,
            _write_config.password,
            base_url=_write_config.base_url,
            http_basic_auth=_write_config.http_basic_auth,
        ) as client:
            try:
                await client.write_product(barcode, fields)
            except (OpenFoodFactsError, ValueError) as exc:
                return f"Error: {exc}"

        product_url = f"{_write_config.base_url}/product/{barcode}"
        return (
            f"Saved to Open Food Facts ({_write_config.environment}).\n"
            f"Updated {len(fields)} field(s) on barcode {barcode}.\n"
            f"View: {product_url}"
        )


@mcp.tool
async def find_healthier_alternative(barcode: str, limit: int = 5) -> str:
    """Suggest healthier products in the same category as the given product.

    Looks up the product, then searches its category for items with a better
    (lower) Nutri-Score, returning the healthiest matches first.

    Args:
        barcode: The product barcode, digits only.
        limit: Maximum number of alternatives to return (1-10, default 5).
    """
    limit = max(1, min(limit, 10))

    async with OpenFoodFactsClient() as client:
        try:
            product = await client.get_product(barcode)
        except ProductNotFoundError as exc:
            return str(exc)
        except (OpenFoodFactsError, ValueError) as exc:
            return f"Error: {exc}"

        base_rank = nutriscore_rank(product)
        if base_rank is None:
            return (
                f"{product.get('product_name') or barcode} has no Nutri-Score, so "
                "healthier alternatives can't be ranked."
            )
        if base_rank == 1:
            return (
                f"{product.get('product_name') or barcode} already has Nutri-Score A "
                "— it's the healthiest grade."
            )

        # Walk categories from most specific to broadest and stop at the first
        # one that actually contains healthier products, so suggestions stay in
        # the closest matching category rather than drifting to a broad parent.
        categories = product.get("categories_tags") or []
        own_code = product.get("code", "")
        alternatives: list[dict] = []
        for category in reversed(categories):
            try:
                candidates = await client.search_by_category(category, page_size=50)
            except (OpenFoodFactsError, ValueError):
                continue
            seen: set[str] = {own_code}
            better: list[dict] = []
            for cand in candidates:
                code = cand.get("code")
                rank = nutriscore_rank(cand)
                if not code or code in seen or rank is None:
                    continue
                if rank < base_rank:
                    seen.add(code)
                    better.append(cand)
            if better:
                alternatives = better
                break

        alternatives.sort(key=lambda p: (nutriscore_rank(p) or 99))
        alternatives = alternatives[:limit]

    return format_alternatives(product, alternatives)


def main() -> None:
    """Console-script entry point. Runs the server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
