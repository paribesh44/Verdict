import { invokeMcpTool } from "@/lib/mcp/client";

export type FirecrawlAutonomousInput = {
  query: string;
  depth?: number;
};

export async function runFirecrawlAutonomousSearch(
  mcpEndpoint: string,
  actorId: string,
  input: FirecrawlAutonomousInput
) {
  return invokeMcpTool(mcpEndpoint, {
    actorId,
    intent: "research_navigation",
    toolName: "firecrawl.agent.search",
    input
  });
}
