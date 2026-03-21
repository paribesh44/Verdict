export type JsonValue =
  | string
  | number
  | boolean
  | null
  | { [key: string]: JsonValue }
  | JsonValue[];

export type ModelPatchOperation = "replace" | "append" | "merge";

export type DataUpdate = {
  path: string;
  op: ModelPatchOperation;
  value: JsonValue;
};

export type ComponentBinding = {
  prop: string;
  path: string;
};

export type SurfaceComponentBlueprint = {
  id: string;
  component: string;
  props?: Record<string, JsonValue>;
  bindings?: ComponentBinding[];
};
