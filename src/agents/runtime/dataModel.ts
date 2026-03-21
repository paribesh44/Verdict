import set from "jsonpointer";
import type { DataUpdate, JsonValue } from "@/lib/contracts/types";

export type DataModel = Record<string, JsonValue>;

function mergeObjects(
  existing: Record<string, JsonValue>,
  incoming: Record<string, JsonValue>
): Record<string, JsonValue> {
  return { ...existing, ...incoming };
}

export function applyDataUpdates(model: DataModel, updates: DataUpdate[]): DataModel {
  const nextModel: DataModel = structuredClone(model);

  for (const update of updates) {
    if (update.op === "replace") {
      set.set(nextModel, update.path, update.value);
      continue;
    }

    if (update.op === "append") {
      const current = set.get(nextModel, update.path);
      if (!Array.isArray(current)) {
        set.set(nextModel, update.path, [update.value] as JsonValue[]);
        continue;
      }
      set.set(nextModel, update.path, [...current, update.value] as JsonValue[]);
      continue;
    }

    const current = set.get(nextModel, update.path);
    if (
      current !== null &&
      typeof current === "object" &&
      !Array.isArray(current) &&
      update.value !== null &&
      typeof update.value === "object" &&
      !Array.isArray(update.value)
    ) {
      set.set(
        nextModel,
        update.path,
        mergeObjects(
          current as Record<string, JsonValue>,
          update.value as Record<string, JsonValue>
        )
      );
    } else {
      set.set(nextModel, update.path, update.value);
    }
  }

  return nextModel;
}
