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


async def extract_claims(
    mcp_client: MCPClient,
    actor_id: str,
    urls: list[str],
    approval_id: str | None = None,
) -> Dict[str, Any]:
    return await mcp_client.call_tool(
        actor_id=actor_id,
        intent="research_extraction",
        tool_name="firecrawl.extract", # Assuming your MCP gateway maps this
        input_payload={
            "urls": urls,
            "prompt": "Extract 3 to 5 full, complete sentences that define the core concepts of the page. Do not use ellipses (...).",
        },
        approval_id=approval_id,
    )