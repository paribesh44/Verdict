from typing import Any, Dict

from .mcp import MCPClient


async def autonomous_research(
    mcp_client: MCPClient,
    actor_id: str,
    query: str,
    approval_id: str | None = None,
) -> Dict[str, Any]:
    return await mcp_client.call_tool(
        actor_id=actor_id,
        intent="research_navigation",
        tool_name="firecrawl.agent.search",
        input_payload={"query": query, "depth": 2},
        approval_id=approval_id,
    )
