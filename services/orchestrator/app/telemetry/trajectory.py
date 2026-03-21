from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List


@dataclass
class TrajectoryStep:
    trace_id: str
    step_name: str
    precision: float
    recall: float
    token_estimate: int
    latency_ms: int
    timestamp: str


class TrajectoryLogger:
    """In-memory trajectory logger (fallback when REDIS_URL is not set)."""

    def __init__(self) -> None:
        self._steps: List[TrajectoryStep] = []

    async def record(
        self,
        trace_id: str,
        step_name: str,
        precision: float,
        recall: float,
        token_estimate: int,
        latency_ms: int,
    ) -> None:
        self._steps.append(
            TrajectoryStep(
                trace_id=trace_id,
                step_name=step_name,
                precision=precision,
                recall=recall,
                token_estimate=token_estimate,
                latency_ms=latency_ms,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        )

    def as_dicts(self) -> List[Dict[str, Any]]:
        return [asdict(step) for step in self._steps]

    async def get_steps_for_trace(self, trace_id: str) -> List[Dict[str, Any]]:
        matches = [step for step in self._steps if step.trace_id == trace_id]
        return [asdict(step) for step in matches]


def _trajectory_key(trace_id: str) -> str:
    return f"verdict:trajectory:{trace_id}"


class RedisTrajectoryLogger(TrajectoryLogger):
    """Redis-backed trajectory logger. Uses verdict:trajectory:{trace_id} list."""

    def __init__(self, redis_url: str) -> None:
        super().__init__()
        self._redis_url = redis_url
        self._client: Any = None

    def _get_client(self):
        if self._client is None:
            import redis.asyncio as aioredis
            self._client = aioredis.from_url(self._redis_url, decode_responses=True)
        return self._client

    async def record(
        self,
        trace_id: str,
        step_name: str,
        precision: float,
        recall: float,
        token_estimate: int,
        latency_ms: int,
    ) -> None:
        step = TrajectoryStep(
            trace_id=trace_id,
            step_name=step_name,
            precision=precision,
            recall=recall,
            token_estimate=token_estimate,
            latency_ms=latency_ms,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        key = _trajectory_key(trace_id)
        client = self._get_client()
        await client.rpush(key, json.dumps(asdict(step)))
        # Optional: expire key after 24h so we don't grow unbounded
        await client.expire(key, 86400)

    def as_dicts(self) -> List[Dict[str, Any]]:
        # Redis logger doesn't keep full list in memory; use get_steps_for_trace per trace
        return []

    async def get_steps_for_trace(self, trace_id: str) -> List[Dict[str, Any]]:
        key = _trajectory_key(trace_id)
        client = self._get_client()
        raw_list = await client.lrange(key, 0, -1)
        return [json.loads(item) for item in raw_list]
