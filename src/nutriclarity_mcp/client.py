"""Thin async client for the Open Food Facts API.

Docs: https://openfoodfacts.github.io/openfoodfacts-server/api/

Only public read endpoints are used, so no authentication is required. Open Food
Facts asks every client to send a descriptive User-Agent so they can identify
traffic and contact maintainers if needed.
"""

from __future__ import annotations

from typing import Any

import httpx

from . import __version__

BASE_URL = "https://world.openfoodfacts.org"

# A descriptive User-Agent is requested by Open Food Facts for all API traffic.
USER_AGENT = (
    f"nutriclarity-mcp/{__version__} "
    "(+https://github.com/nitish/nutriclarity-mcp)"
)

# Fields we ask Open Food Facts to return. Keeping this list tight makes
# responses smaller and faster and keeps the tool output focused.
PRODUCT_FIELDS = [
    "code",
    "product_name",
    "brands",
    "quantity",
    "serving_size",
    "categories",
    "ingredients_text",
    "allergens",
    "nutriscore_grade",
    "nova_group",
    "ecoscore_grade",
    "nutriments",
    "image_front_url",
]


class ProductNotFoundError(Exception):
    """Raised when a barcode does not resolve to a product."""


class OpenFoodFactsError(Exception):
    """Raised when the Open Food Facts API returns an unexpected error."""


class OpenFoodFactsClient:
    """Async wrapper around the Open Food Facts REST API."""

    def __init__(self, *, timeout: float = 15.0, base_url: str = BASE_URL) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        )

    async def __aenter__(self) -> OpenFoodFactsClient:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get_product(self, barcode: str) -> dict[str, Any]:
        """Fetch a single product by its barcode (EAN/UPC).

        Raises:
            ProductNotFoundError: if the barcode is unknown.
            OpenFoodFactsError: on network/HTTP/parse failures.
        """
        barcode = barcode.strip()
        if not barcode.isdigit():
            raise ValueError("Barcode must contain digits only (EAN/UPC).")

        try:
            resp = await self._client.get(
                f"/api/v2/product/{barcode}.json",
                params={"fields": ",".join(PRODUCT_FIELDS)},
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:  # network, timeout, bad status
            raise OpenFoodFactsError(f"Failed to reach Open Food Facts: {exc}") from exc
        except ValueError as exc:  # JSON decode
            raise OpenFoodFactsError("Open Food Facts returned malformed JSON.") from exc

        # status == 1 means found; 0 means not found.
        if data.get("status") != 1 or not data.get("product"):
            raise ProductNotFoundError(f"No product found for barcode {barcode}.")

        return data["product"]

    async def search(self, query: str, *, page_size: int = 5) -> list[dict[str, Any]]:
        """Free-text search for products by name/brand.

        Returns a (possibly empty) list of product dicts.
        """
        query = query.strip()
        if not query:
            raise ValueError("Search query must not be empty.")

        page_size = max(1, min(page_size, 25))

        try:
            resp = await self._client.get(
                "/cgi/search.pl",
                params={
                    "search_terms": query,
                    "search_simple": 1,
                    "action": "process",
                    "json": 1,
                    "page_size": page_size,
                    "fields": ",".join(PRODUCT_FIELDS),
                },
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            raise OpenFoodFactsError(f"Failed to reach Open Food Facts: {exc}") from exc
        except ValueError as exc:
            raise OpenFoodFactsError("Open Food Facts returned malformed JSON.") from exc

        return data.get("products", []) or []


class OpenFoodFactsWriteClient:
    """Async client for the authenticated Add/Edit product endpoint.

    Writes go to whichever ``base_url`` is passed (sandbox by default via
    ``config.load_write_config``). Credentials are sent as ``user_id`` /
    ``password`` POST fields, as required by Open Food Facts.
    """

    def __init__(
        self,
        username: str,
        password: str,
        *,
        base_url: str,
        http_basic_auth: tuple[str, str] | None = None,
        timeout: float = 20.0,
    ) -> None:
        self._username = username
        self._password = password
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
            # Sandbox host is gated behind HTTP Basic Auth; production is not.
            auth=httpx.BasicAuth(*http_basic_auth) if http_basic_auth else None,
        )

    async def __aenter__(self) -> OpenFoodFactsWriteClient:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def write_product(self, barcode: str, fields: dict[str, str]) -> dict[str, Any]:
        """Create or update a product. ``fields`` are Open Food Facts form params.

        Raises:
            OpenFoodFactsError: on network/HTTP failures or a rejected write.
        """
        barcode = barcode.strip()
        if not barcode.isdigit():
            raise ValueError("Barcode must contain digits only (EAN/UPC).")

        payload: dict[str, str] = {
            "code": barcode,
            "user_id": self._username,
            "password": self._password,
            # Identify the client for Open Food Facts moderation.
            "app_name": "nutriclarity-mcp",
            "app_version": __version__,
            **fields,
        }

        try:
            resp = await self._client.post("/cgi/product_jqm2.pl", data=payload)
        except httpx.HTTPError as exc:
            raise OpenFoodFactsError(f"Failed to reach Open Food Facts: {exc}") from exc

        # A wrong account login is reported as 401/403 with an HTML error page.
        if resp.status_code in (401, 403):
            raise OpenFoodFactsError(
                "Authentication failed. Check OFF_USERNAME (your account username, "
                "not email) and OFF_PASSWORD, and that the account exists on this "
                "environment (sandbox accounts are separate from production)."
            )

        try:
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            raise OpenFoodFactsError(f"Failed to reach Open Food Facts: {exc}") from exc
        except ValueError as exc:
            raise OpenFoodFactsError("Open Food Facts returned a non-JSON response.") from exc

        # status == 1 means the write succeeded.
        if data.get("status") != 1:
            reason = data.get("status_verbose") or "unknown error"
            raise OpenFoodFactsError(f"Write was rejected: {reason}")

        return data
