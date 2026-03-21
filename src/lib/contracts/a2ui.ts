import { z } from "zod";

const bindingSchema = z.object({
  prop: z.string().min(1),
  path: z.string().min(1)
});

const componentSchema = z.object({
  id: z.string().min(1),
  component: z.string().min(1),
  props: z.record(z.unknown()).optional(),
  bindings: z.array(bindingSchema).optional()
});

const dataUpdateSchema = z.object({
  path: z.string().min(1),
  op: z.enum(["replace", "append", "merge"]),
  value: z.unknown()
});

const envelopeBaseSchema = z.object({
  requestId: z.string().min(1),
  // JSON Schema `date-time` allows timezone offsets (e.g. +00:00).
  timestamp: z.string().datetime({ offset: true })
});

const surfaceUpdateSchema = envelopeBaseSchema.extend({
  type: z.literal("surfaceUpdate"),
  components: z.array(componentSchema).min(1)
});

const dataModelUpdateSchema = envelopeBaseSchema.extend({
  type: z.literal("dataModelUpdate"),
  updates: z.array(dataUpdateSchema).min(1)
});

const beginRenderingSchema = envelopeBaseSchema.extend({
  type: z.literal("beginRendering"),
  surfaceId: z.string().min(1)
});

export const a2uiEnvelopeSchema = z.discriminatedUnion("type", [
  surfaceUpdateSchema,
  dataModelUpdateSchema,
  beginRenderingSchema
]);

export type A2UIEnvelope = z.infer<typeof a2uiEnvelopeSchema>;
