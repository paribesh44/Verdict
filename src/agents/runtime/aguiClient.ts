import { aguiEventSchema, type AguiEvent } from "@/lib/contracts/agui";
import { a2uiEnvelopeSchema, type A2UIEnvelope } from "@/lib/contracts/a2ui";

export type RuntimeMessage =
  | { kind: "aguiEvent"; event: AguiEvent }
  | { kind: "a2uiEnvelope"; envelope: A2UIEnvelope };

export type StreamHandlers = {
  onEvent?: (event: AguiEvent) => void;
  onEnvelope?: (envelope: A2UIEnvelope) => void;
  onError?: (error: Error) => void;
};

export type StartResearchPayload = {
  query: string;
  actorId: string;
  intent: string;
  approvalId?: string;
};

export function parseRuntimeMessage(raw: string): RuntimeMessage {
  const parsed = JSON.parse(raw) as unknown;
  if (!parsed || typeof parsed !== "object") {
    throw new Error("Runtime message must be an object");
  }

  const withKind = parsed as { kind?: string };
  if (withKind.kind === "aguiEvent") {
    return {
      kind: "aguiEvent",
      event: aguiEventSchema.parse((parsed as { event: unknown }).event)
    };
  }

  if (withKind.kind === "a2uiEnvelope") {
    return {
      kind: "a2uiEnvelope",
      envelope: a2uiEnvelopeSchema.parse((parsed as { envelope: unknown }).envelope)
    };
  }

  throw new Error("Unknown runtime message kind");
}

export async function streamResearch(
  endpoint: string,
  payload: StartResearchPayload,
  handlers: StreamHandlers
): Promise<void> {
  const body: Record<string, string> = {
    query: payload.query,
    actorId: payload.actorId,
    intent: payload.intent
  };
  if (payload.approvalId) body.approvalId = payload.approvalId;
  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });

  if (!response.ok || !response.body) {
    throw new Error(`Unable to open AG-UI stream (${response.status})`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let isDone = false;

  try {
    while (!isDone) {
      const chunk = await reader.read();
      if (chunk.done) {
        isDone = true;
        continue;
      }
      buffer += decoder.decode(chunk.value, { stream: true });

      const parts = buffer.split("\n\n");
      buffer = parts.pop() ?? "";

      for (const part of parts) {
        const dataLine = part
          .split("\n")
          .find((line) => line.startsWith("data:"));
        if (!dataLine) continue;
        const payloadRaw = dataLine.slice(5).trim();
        if (!payloadRaw) continue;

        const message = parseRuntimeMessage(payloadRaw);
        if (message.kind === "aguiEvent") {
          handlers.onEvent?.(message.event);
        } else {
          handlers.onEnvelope?.(message.envelope);
        }
      }
    }
  } catch (error) {
    handlers.onError?.(error as Error);
    throw error;
  } finally {
    reader.releaseLock();
  }
}
