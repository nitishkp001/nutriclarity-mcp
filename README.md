# NutriClarity MCP 🥗

[![CI](https://github.com/nitishkp001/nutriclarity-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/nitishkp001/nutriclarity-mcp/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/nutriclarity-mcp.svg)](https://pypi.org/project/nutriclarity-mcp/)
[![Python](https://img.shields.io/pypi/pyversions/nutriclarity-mcp.svg)](https://pypi.org/project/nutriclarity-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

An open-source [Model Context Protocol](https://modelcontextprotocol.io) server that gives
any LLM access to **food nutrition data** — look up products by barcode, search by name,
read Nutri-Score / NOVA / Eco-Score ratings, and compare products side by side.

Powered by [Open Food Facts](https://world.openfoodfacts.org), a free, open, crowd-sourced
food products database. No API key required.

## Tools

| Tool | Description |
| --- | --- |
| `get_product_by_barcode(barcode)` | Full nutrition facts, scores, allergens & ingredients for a barcode (EAN/UPC). |
| `search_products(query, page_size=5)` | Search products by name or brand; returns barcodes + a nutrition summary. |
| `get_nutrition_scores(barcode)` | Nutri-Score (A–E), NOVA processing group (1–4), and Eco-Score for a product. |
| `compare_products(barcodes)` | Side-by-side per-100g comparison table for 2+ products. |
| `add_or_update_product(...)` | **Optional / opt-in.** Create or edit a product. Only enabled when credentials are set (see below). |

Reading needs **no API key or account** — it's open data. Only the optional write
tool requires an Open Food Facts login.

## Quick start

The easiest way to run it is with [`uvx`](https://docs.astral.sh/uv/) (no install, no clone):

```bash
uvx nutriclarity-mcp
```

### Claude Desktop / Cursor / any MCP client

Add this to your MCP config (e.g. `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "nutriclarity": {
      "command": "uvx",
      "args": ["nutriclarity-mcp"]
    }
  }
}
```

Then ask things like:
- *"What's the nutrition of barcode 3017620422003?"*
- *"Search for oat milk and show me the healthiest option."*
- *"Compare Coke and Pepsi nutrition."*

### Docker

```bash
docker run -i --rm ghcr.io/nitishkp001/nutriclarity-mcp
```

MCP config:

```json
{
  "mcpServers": {
    "nutriclarity": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "ghcr.io/nitishkp001/nutriclarity-mcp"]
    }
  }
}
```

## Optional: write support (adding/editing products)

By default the server is **read-only** — no account, no risk. If you want the LLM
to be able to contribute or correct product data, enable the `add_or_update_product`
tool by providing an [Open Food Facts account](https://world.openfoodfacts.org/):

| Env var | Description |
| --- | --- |
| `OFF_USERNAME` | Your account **username** (not your email). Enables writes when set with the password. |
| `OFF_PASSWORD` | Your account password. |
| `OFF_ENVIRONMENT` | `sandbox` (default) or `production`. |

**Writes go to the [sandbox](https://world.openfoodfacts.net) by default**, so you can
test safely without touching the real database. Set `OFF_ENVIRONMENT=production` only
when you deliberately want to edit the live, public database. Sandbox accounts are
separate from production accounts — register on each site you target.

```json
{
  "mcpServers": {
    "nutriclarity": {
      "command": "uvx",
      "args": ["nutriclarity-mcp"],
      "env": {
        "OFF_USERNAME": "your-username",
        "OFF_PASSWORD": "your-password",
        "OFF_ENVIRONMENT": "sandbox"
      }
    }
  }
}
```

> ⚠️ Open Food Facts is a shared, public database used by millions. If you enable
> production writes, make sure the data you submit is accurate and taken from the
> real product label. The tool changes only the fields you pass.

## Local development

Requires [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/nitishkp001/nutriclarity-mcp
cd nutriclarity-mcp
uv sync --extra dev        # install deps
uv run nutriclarity-mcp    # run the server over stdio
uv run pytest              # run tests
uv run ruff check .        # lint
```

To inspect the tools interactively, use the [MCP Inspector](https://github.com/modelcontextprotocol/inspector):

```bash
npx @modelcontextprotocol/inspector uv run nutriclarity-mcp
```

## How it works

- Built with [FastMCP](https://github.com/jlowin/fastmcp).
- Calls the Open Food Facts REST API (`/api/v2/product/{barcode}` and `/cgi/search.pl`).
- Sends a descriptive `User-Agent` as Open Food Facts requests, and asks only for the fields
  it needs to keep responses small.

## Data & attribution

Product data comes from [Open Food Facts](https://world.openfoodfacts.org) and is made
available under the [Open Database License (ODbL)](https://opendatacommons.org/licenses/odbl/1-0/).
Individual contents are under the Database Contents License. Nutrition data is crowd-sourced
and may be incomplete or inaccurate — do not rely on it for medical decisions.

## License

MIT © 2026 — see [LICENSE](LICENSE). This project is not affiliated with or endorsed by
Open Food Facts.
