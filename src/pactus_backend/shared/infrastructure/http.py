"""Shared HTTP client helpers for outbound integrations."""

import httpx
from fastapi import Request


def build_http_client() -> httpx.AsyncClient:
    """Builds a reusable AsyncClient with keep-alive enabled."""
    return httpx.AsyncClient(
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
        follow_redirects=False,
    )


def get_http_client(request: Request) -> httpx.AsyncClient:
    """Returns the application-scoped HTTP client."""
    return request.app.state.http_client
