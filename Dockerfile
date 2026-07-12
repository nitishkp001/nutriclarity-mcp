# syntax=docker/dockerfile:1
FROM python:3.12-slim

# uv for fast, reproducible installs
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install dependencies first for better layer caching
COPY pyproject.toml README.md ./
COPY src ./src

RUN uv pip install --system --no-cache .

# MCP servers speak over stdio by default
ENTRYPOINT ["nutriclarity-mcp"]
