"""Store for ExtractionBundle + final answer by trace_id (for audit)."""

from __future__ import annotations

import json
from typing import Any, Dict, Tuple

from app.rag.schemas import ExtractionBundle


class ExtractionStore:
    """In-memory store (fallback when REDIS_URL is not set)."""

    def __init__(self) -> None:
        self._data: Dict[str, Dict[str, Any]] = {}

    async def set(self, trace_id: str, bundle: ExtractionBundle, final_answer: str) -> None:
        self._data[trace_id] = {
            "bundle": bundle.model_dump(mode="json"),
            "final_answer": final_answer,
        }

    async def get(self, trace_id: str) -> Tuple[ExtractionBundle | None, str | None]:
        raw = self._data.get(trace_id)
        if not raw:
            return None, None
        bundle = ExtractionBundle.model_validate(raw["bundle"])
        return bundle, raw.get("final_answer", "")


def _extraction_key(trace_id: str) -> str:
    return f"verdict:extraction:{trace_id}"


class RedisExtractionStore(ExtractionStore):
    """Redis-backed extraction store."""

    def __init__(self, redis_url: str) -> None:
        super().__init__()
        self._redis_url = redis_url
        self._client: Any = None

    def _get_client(self):
        if self._client is None:
            import redis.asyncio as aioredis
            self._client = aioredis.from_url(self._redis_url, decode_responses=True)
        return self._client

    async def set(self, trace_id: str, bundle: ExtractionBundle, final_answer: str) -> None:
        key = _extraction_key(trace_id)
        payload = json.dumps({
            "bundle": bundle.model_dump(mode="json"),
            "final_answer": final_answer,
        })
        client = self._get_client()
        await client.set(key, payload, ex=86400)

    async def get(self, trace_id: str) -> Tuple[ExtractionBundle | None, str | None]:
        key = _extraction_key(trace_id)
        client = self._get_client()
        raw = await client.get(key)
        if not raw:
            return None, None
        data = json.loads(raw)
        bundle = ExtractionBundle.model_validate(data["bundle"])
        return bundle, data.get("final_answer", "")
