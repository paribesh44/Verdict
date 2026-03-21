from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict
from uuid import uuid4


@dataclass
class ApprovalTicket:
    approval_id: str
    trace_id: str
    reason: str
    requested_action: str
    approved: bool = False
    denied: bool = False
    expires_at: datetime | None = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if self.expires_at is not None:
            d["expires_at"] = self.expires_at.isoformat()
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> ApprovalTicket:
        expires = d.get("expires_at")
        if isinstance(expires, str):
            d = {**d, "expires_at": datetime.fromisoformat(expires.replace("Z", "+00:00"))}
        return cls(**d)


class ApprovalStore:
    """In-memory approval store (fallback when REDIS_URL is not set)."""

    def __init__(self) -> None:
        self._tickets: Dict[str, ApprovalTicket] = {}

    async def create(
        self, trace_id: str, reason: str, requested_action: str, ttl_seconds: int = 600
    ) -> ApprovalTicket:
        approval_id = str(uuid4())
        ticket = ApprovalTicket(
            approval_id=approval_id,
            trace_id=trace_id,
            reason=reason,
            requested_action=requested_action,
            approved=False,
            denied=False,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds),
        )
        self._tickets[approval_id] = ticket
        return ticket

    async def get(self, approval_id: str) -> ApprovalTicket | None:
        return self._tickets.get(approval_id)

    async def approve(self, approval_id: str) -> ApprovalTicket:
        ticket = self._tickets[approval_id]
        ticket.approved = True
        return ticket

    async def deny(self, approval_id: str) -> ApprovalTicket:
        ticket = self._tickets[approval_id]
        ticket.denied = True
        return ticket

    async def is_approved(self, approval_id: str) -> bool:
        ticket = self._tickets.get(approval_id)
        if not ticket:
            return False
        if ticket.denied:
            return False
        if ticket.expires_at and datetime.now(timezone.utc) > ticket.expires_at:
            return False
        return ticket.approved


def _approval_key(approval_id: str) -> str:
    return f"verdict:approval:{approval_id}"


class RedisApprovalStore(ApprovalStore):
    """Redis-backed approval store. Uses verdict:approval:{id} with TTL."""

    def __init__(self, redis_url: str) -> None:
        super().__init__()
        self._redis_url = redis_url
        self._client: Any = None

    def _get_client(self):
        if self._client is None:
            import redis.asyncio as aioredis
            self._client = aioredis.from_url(self._redis_url, decode_responses=True)
        return self._client

    async def create(
        self, trace_id: str, reason: str, requested_action: str, ttl_seconds: int = 600
    ) -> ApprovalTicket:
        approval_id = str(uuid4())
        ticket = ApprovalTicket(
            approval_id=approval_id,
            trace_id=trace_id,
            reason=reason,
            requested_action=requested_action,
            approved=False,
            denied=False,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds),
        )
        key = _approval_key(approval_id)
        client = self._get_client()
        await client.set(key, json.dumps(ticket.to_dict()), ex=ttl_seconds)
        return ticket

    async def get(self, approval_id: str) -> ApprovalTicket | None:
        client = self._get_client()
        raw = await client.get(_approval_key(approval_id))
        if raw is None:
            return None
        return ApprovalTicket.from_dict(json.loads(raw))

    async def approve(self, approval_id: str) -> ApprovalTicket:
        ticket = await self.get(approval_id)
        if not ticket:
            raise KeyError(approval_id)
        ticket.approved = True
        key = _approval_key(approval_id)
        client = self._get_client()
        ttl = await client.ttl(key)
        await client.set(key, json.dumps(ticket.to_dict()), ex=max(ttl, 60))
        return ticket

    async def deny(self, approval_id: str) -> ApprovalTicket:
        ticket = await self.get(approval_id)
        if not ticket:
            raise KeyError(approval_id)
        ticket.denied = True
        key = _approval_key(approval_id)
        client = self._get_client()
        ttl = await client.ttl(key)
        await client.set(key, json.dumps(ticket.to_dict()), ex=max(ttl, 60))
        return ticket

    async def is_approved(self, approval_id: str) -> bool:
        ticket = await self.get(approval_id)
        if not ticket:
            return False
        if ticket.denied:
            return False
        if ticket.expires_at and datetime.now(timezone.utc) > ticket.expires_at:
            return False
        return ticket.approved
