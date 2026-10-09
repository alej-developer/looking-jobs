"""Retry helper for public ATS APIs."""

import asyncio

import httpx

from src.scraper.base import get_with_retry


def test_retries_rate_limit():
    calls = {"n": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429)
        return httpx.Response(200, json={"ok": True})

    async def scenario() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            async def no_wait(_delay: float) -> None:
                return None

            response = await get_with_retry(
                client,
                "https://example.com/jobs",
                sleep=no_wait,
            )
            assert response.status_code == 200

    asyncio.run(scenario())
    assert calls["n"] == 2
