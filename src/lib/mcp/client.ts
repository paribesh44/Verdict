export type McpToolRequest = {
  actorId: string;
  intent: string;
  toolName: string;
  input: Record<string, unknown>;
};

export type McpToolResponse = {
  ok: boolean;
  data?: unknown;
  error?: string;
};

export async function invokeMcpTool(
  endpoint: string,
  request: McpToolRequest
): Promise<McpToolResponse> {
  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request)
  });

  if (!response.ok) {
    return { ok: false, error: `MCP call failed (${response.status})` };
  }

  return (await response.json()) as McpToolResponse;
}
