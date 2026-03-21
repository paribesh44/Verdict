import { describe, expect, it } from "vitest";
import { parseRuntimeMessage } from "@/agents/runtime/aguiClient";

describe("parseRuntimeMessage", () => {
  it("parses AG-UI events", () => {
    const message = parseRuntimeMessage(
      JSON.stringify({
        kind: "aguiEvent",
        event: {
          eventId: "evt-1",
          traceId: "trace-1",
          timestamp: new Date().toISOString(),
          eventType: "TEXT_MESSAGE_CONTENT",
          payload: { role: "assistant", content: "hello" }
        }
      })
    );

    expect(message.kind).toBe("aguiEvent");
  });

  it("parses A2UI envelopes", () => {
    const message = parseRuntimeMessage(
      JSON.stringify({
        kind: "a2uiEnvelope",
        envelope: {
          requestId: "req-1",
          timestamp: new Date().toISOString(),
          type: "beginRendering",
          surfaceId: "main"
        }
      })
    );

    expect(message.kind).toBe("a2uiEnvelope");
  });

  it("accepts timestamps with timezone offsets", () => {
    const eventMessage = parseRuntimeMessage(
      JSON.stringify({
        kind: "aguiEvent",
        event: {
          eventId: "evt-2",
          traceId: "trace-2",
          timestamp: "2026-02-27T01:23:45+00:00",
          eventType: "STATE_DELTA",
          payload: { path: "/research/status", op: "replace", value: "running" }
        }
      })
    );

    const envelopeMessage = parseRuntimeMessage(
      JSON.stringify({
        kind: "a2uiEnvelope",
        envelope: {
          requestId: "req-2",
          timestamp: "2026-02-27T01:23:45+00:00",
          type: "beginRendering",
          surfaceId: "main"
        }
      })
    );

    expect(eventMessage.kind).toBe("aguiEvent");
    expect(envelopeMessage.kind).toBe("a2uiEnvelope");
  });
});
