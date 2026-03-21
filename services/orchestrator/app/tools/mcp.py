from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

import httpx


@dataclass
class MCPClient:
    endpoint: str
    timeout_seconds: float = 20.0

    async def call_tool(
        self,
        actor_id: str,
        intent: str,
        tool_name: str,
        input_payload: Dict[str, Any],
        approval_id: str | None = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "actorId": actor_id,
            "intent": intent,
            "toolName": tool_name,
            "input": input_payload,
        }
        if approval_id:
            payload["approvalId"] = approval_id
        headers = {
            "Content-Type": "application/json",
            "X-Actor-Id": actor_id,
            "X-Intent": intent,
        }
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                self.endpoint,
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            return response.json()
