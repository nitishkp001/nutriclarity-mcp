"""Turn raw Open Food Facts product dicts into concise, LLM-friendly text."""

from __future__ import annotations

from typing import Any

# Nutriment keys we surface, mapped to human labels and units. Open Food Facts
# stores per-100g values under "<key>_100g".
NUTRIENT_ROWS: list[tuple[str, str, str]] = [
    ("energy-kcal", "Energy", "kcal"),
    ("fat", "Fat", "g"),
    ("saturated-fat", "Saturated fat", "g"),
    ("carbohydrates", "Carbohydrates", "g"),
    ("sugars", "Sugars", "g"),
    ("fiber", "Fiber", "g"),
    ("proteins", "Protein", "g"),
    ("salt", "Salt", "g"),
    ("sodium", "Sodium", "g"),
]

NUTRISCORE_RANK = {"a": 1, "b": 2, "c": 3, "d": 4, "e": 5}

NOVA_DESCRIPTIONS = {
    1: "Unprocessed or minimally processed foods",
    2: "Processed culinary ingredients",
    3: "Processed foods",
    4: "Ultra-processed foods",
}


def _name(product: dict[str, Any]) -> str:
    name = (product.get("product_name") or "").strip()
    brand = (product.get("brands") or "").strip()
    code = product.get("code") or "?"
    if name and brand:
        header = f"{name} — {brand}"
    elif name:
        header = name
    else:
        header = "(unnamed product)"
    return f"{header} [barcode: {code}]"


def _nutriment(nutriments: dict[str, Any], key: str) -> float | None:
    value = nutriments.get(f"{key}_100g")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def format_product(product: dict[str, Any]) -> str:
    """Full nutrition breakdown for a single product."""
    lines: list[str] = [_name(product)]

    quantity = product.get("quantity")
    serving = product.get("serving_size")
    if quantity:
        lines.append(f"Quantity: {quantity}")
    if serving:
        lines.append(f"Serving size: {serving}")

    nutriments = product.get("nutriments") or {}
    lines.append("")
    lines.append("Nutrition per 100 g/ml:")
    any_nutrient = False
    for key, label, unit in NUTRIENT_ROWS:
        value = _nutriment(nutriments, key)
        if value is not None:
            any_nutrient = True
            lines.append(f"  - {label}: {value:g} {unit}")
    if not any_nutrient:
        lines.append("  (no nutrition data available)")

    scores = format_scores(product, header=False)
    if scores:
        lines.append("")
        lines.append(scores)

    allergens = (product.get("allergens") or "").replace("en:", "").strip()
    if allergens:
        lines.append("")
        lines.append(f"Allergens: {allergens}")

    ingredients = (product.get("ingredients_text") or "").strip()
    if ingredients:
        lines.append("")
        lines.append(f"Ingredients: {ingredients}")

    return "\n".join(lines)


def format_scores(product: dict[str, Any], *, header: bool = True) -> str:
    """Nutri-Score / NOVA / Eco-Score summary. Returns '' if none present."""
    parts: list[str] = []

    nutriscore = (product.get("nutriscore_grade") or "").upper()
    if nutriscore and nutriscore not in ("UNKNOWN", "NOT-APPLICABLE"):
        parts.append(f"  - Nutri-Score: {nutriscore} (A = healthiest, E = least healthy)")

    nova = product.get("nova_group")
    if nova is not None:
        try:
            nova_int = int(nova)
            desc = NOVA_DESCRIPTIONS.get(nova_int, "")
            parts.append(f"  - NOVA group: {nova_int} ({desc})")
        except (TypeError, ValueError):
            pass

    ecoscore = (product.get("ecoscore_grade") or "").upper()
    if ecoscore and ecoscore not in ("UNKNOWN", "NOT-APPLICABLE"):
        parts.append(f"  - Eco-Score: {ecoscore} (A = lowest environmental impact)")

    if not parts:
        return ""

    if header:
        return _name(product) + "\n\nScores:\n" + "\n".join(parts)
    return "Scores:\n" + "\n".join(parts)


def format_search_results(products: list[dict[str, Any]], query: str) -> str:
    """Compact list of search hits with key nutrition + scores."""
    if not products:
        return f'No products found for "{query}".'

    lines = [f'Found {len(products)} result(s) for "{query}":', ""]
    for i, product in enumerate(products, start=1):
        nutriments = product.get("nutriments") or {}
        energy = _nutriment(nutriments, "energy-kcal")
        energy_str = f"{energy:g} kcal/100g" if energy is not None else "energy n/a"
        nutriscore = (product.get("nutriscore_grade") or "").upper()
        score_str = f", Nutri-Score {nutriscore}" if nutriscore and nutriscore != "UNKNOWN" else ""
        lines.append(f"{i}. {_name(product)}")
        lines.append(f"   {energy_str}{score_str}")
    lines.append("")
    lines.append("Use get_product_by_barcode with a barcode above for full details.")
    return "\n".join(lines)


def nutriscore_rank(product: dict[str, Any]) -> int | None:
    """Numeric rank of a product's Nutri-Score (1=A best .. 5=E worst)."""
    grade = (product.get("nutriscore_grade") or "").lower()
    return NUTRISCORE_RANK.get(grade)


def format_alternatives(
    original: dict[str, Any], alternatives: list[dict[str, Any]]
) -> str:
    """Present healthier same-category alternatives to a product."""
    orig_grade = (original.get("nutriscore_grade") or "").upper() or "?"
    lines = [
        f"{_name(original)} has Nutri-Score {orig_grade}.",
        "",
    ]
    if not alternatives:
        lines.append(
            "No products with a better Nutri-Score were found in the same category."
        )
        return "\n".join(lines)

    lines.append("Healthier alternatives in the same category (better Nutri-Score):")
    lines.append("")
    for i, product in enumerate(alternatives, start=1):
        grade = (product.get("nutriscore_grade") or "").upper() or "?"
        nutriments = product.get("nutriments") or {}
        energy = _nutriment(nutriments, "energy-kcal")
        sugars = _nutriment(nutriments, "sugars")
        details = []
        if energy is not None:
            details.append(f"{energy:g} kcal")
        if sugars is not None:
            details.append(f"{sugars:g} g sugar")
        detail_str = f" ({', '.join(details)} /100g)" if details else ""
        lines.append(f"{i}. Nutri-Score {grade} — {_name(product)}{detail_str}")
    return "\n".join(lines)


def format_comparison(products: list[dict[str, Any]]) -> str:
    """Side-by-side nutrition comparison table (per 100 g/ml)."""
    if not products:
        return "No products to compare."

    headers = ["Nutrient (per 100g)"]
    for p in products:
        name = (p.get("product_name") or "").strip() or (p.get("code") or "?")
        headers.append(name[:24])

    rows: list[list[str]] = []
    for key, label, unit in NUTRIENT_ROWS:
        row = [f"{label} ({unit})"]
        for p in products:
            value = _nutriment(p.get("nutriments") or {}, key)
            row.append(f"{value:g}" if value is not None else "—")
        rows.append(row)

    # Nutri-Score row
    score_row = ["Nutri-Score"]
    for p in products:
        grade = (p.get("nutriscore_grade") or "").upper()
        score_row.append(grade if grade and grade != "UNKNOWN" else "—")
    rows.append(score_row)

    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def fmt_row(cells: list[str]) -> str:
        return " | ".join(cell.ljust(widths[i]) for i, cell in enumerate(cells))

    sep = "-+-".join("-" * w for w in widths)
    out = [fmt_row(headers), sep]
    out.extend(fmt_row(row) for row in rows)
    return "\n".join(out)
