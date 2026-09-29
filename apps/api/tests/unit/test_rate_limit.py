from __future__ import annotations

import asyncio

from apps.api.app.core.config import SecuritySettings
from apps.api.app.core.security.rate_limit import _check_rate_limit


class _FakeRequest:
    class App:
        class state:
            redis = None

    app = App()


def test_rate_limit_allows_requests_under_threshold() -> None:
    buckets: dict[str, list[float]] = {}

    async def run():
        allowed_first = await _check_rate_limit(
            _FakeRequest(),
            bucket_key="client:/v1/qa/ask",
            limit=2,
            window_seconds=60,
            memory_buckets=buckets,
        )
        allowed_second = await _check_rate_limit(
            _FakeRequest(),
            bucket_key="client:/v1/qa/ask",
            limit=2,
            window_seconds=60,
            memory_buckets=buckets,
        )
        blocked = await _check_rate_limit(
            _FakeRequest(),
            bucket_key="client:/v1/qa/ask",
            limit=2,
            window_seconds=60,
            memory_buckets=buckets,
        )
        return allowed_first, allowed_second, blocked

    first, second, blocked = asyncio.run(run())
    assert first is True
    assert second is True
    assert blocked is False
