import { z } from "zod";

const baseEventSchema = z.object({
  eventId: z.string().min(1),
  traceId: z.string().min(1),
  // JSON Schema `date-time` allows timezone offsets (e.g. +00:00).
  timestamp: z.string().datetime({ offset: true })
});

const textMessageEventSchema = baseEventSchema.extend({
  eventType: z.literal("TEXT_MESSAGE_CONTENT"),
  payload: z.object({
    role: z.enum(["system", "assistant", "user", "tool"]),
    content: z.string()
  })
});

const toolCallStartEventSchema = baseEventSchema.extend({
  eventType: z.literal("TOOL_CALL_START"),
  payload: z.object({
    toolName: z.string().min(1),
    callId: z.string().min(1),
    arguments: z.record(z.unknown())
  })
});

const stateDeltaEventSchema = baseEventSchema.extend({
  eventType: z.literal("STATE_DELTA"),
  payload: z.object({
    path: z.string().min(1),
    op: z.enum(["replace", "append", "merge"]),
    value: z.unknown()
  })
});

const interruptEventSchema = baseEventSchema.extend({
  eventType: z.literal("INTERRUPT"),
  payload: z.object({
    approvalId: z.string().min(1),
    reason: z.string().min(1),
    requestedAction: z.string().min(1)
  })
});

export const aguiEventSchema = z.discriminatedUnion("eventType", [
  textMessageEventSchema,
  toolCallStartEventSchema,
  stateDeltaEventSchema,
  interruptEventSchema
]);

export type AguiEvent = z.infer<typeof aguiEventSchema>;
