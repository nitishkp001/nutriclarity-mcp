"""Configuration for optional write (add/edit) support.

Write tools are OFF by default. They only activate when both OFF_USERNAME and
OFF_PASSWORD are set. Writes target the Open Food Facts **sandbox** unless
OFF_ENVIRONMENT is explicitly set to "production", so testing can never touch
the real public database by accident.

Environment variables:
    OFF_USERNAME    Open Food Facts account username (NOT email). Required to enable writes.
    OFF_PASSWORD    Open Food Facts account password. Required to enable writes.
    OFF_ENVIRONMENT "sandbox" (default) or "production".
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# Read API always uses production data (open, unauthenticated).
READ_BASE_URL = "https://world.openfoodfacts.org"

# Write hosts. The sandbox has its own separate accounts and data.
PRODUCTION_BASE_URL = "https://world.openfoodfacts.org"
SANDBOX_BASE_URL = "https://world.openfoodfacts.net"


# The Open Food Facts staging server is itself behind HTTP Basic Auth. These
# shared credentials are published in their docs and only gate the sandbox host.
SANDBOX_HTTP_AUTH = ("off", "off")


@dataclass(frozen=True)
class WriteConfig:
    enabled: bool
    username: str | None
    password: str | None
    environment: str  # "sandbox" or "production"
    base_url: str
    # HTTP Basic Auth for the host itself (sandbox only); None in production.
    http_basic_auth: tuple[str, str] | None


def load_write_config(env: dict[str, str] | None = None) -> WriteConfig:
    """Build the write configuration from environment variables."""
    env = env if env is not None else dict(os.environ)

    username = (env.get("OFF_USERNAME") or "").strip() or None
    password = env.get("OFF_PASSWORD") or None

    environment = (env.get("OFF_ENVIRONMENT") or "sandbox").strip().lower()
    if environment == "production":
        base_url = PRODUCTION_BASE_URL
        http_basic_auth: tuple[str, str] | None = None
    else:
        environment = "sandbox"
        base_url = SANDBOX_BASE_URL
        http_basic_auth = SANDBOX_HTTP_AUTH

    enabled = bool(username and password)
    return WriteConfig(
        enabled=enabled,
        username=username,
        password=password,
        environment=environment,
        base_url=base_url,
        http_basic_auth=http_basic_auth,
    )
