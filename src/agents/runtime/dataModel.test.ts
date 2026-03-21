import { describe, expect, it } from "vitest";
import { applyDataUpdates } from "@/agents/runtime/dataModel";

describe("applyDataUpdates", () => {
  it("replaces and appends values using JSON pointers", () => {
    const result = applyDataUpdates(
      {},
      [
        { path: "/research/status", op: "replace", value: "running" },
        { path: "/research/claims", op: "append", value: "Claim A" },
        { path: "/research/claims", op: "append", value: "Claim B" }
      ]
    );

    expect(result).toEqual({
      research: { status: "running", claims: ["Claim A", "Claim B"] }
    });
  });

  it("merges object payloads on merge operation", () => {
    const result = applyDataUpdates(
      { research: { stats: { precision: 0.8 } } },
      [{ path: "/research/stats", op: "merge", value: { recall: 0.7 } }]
    );

    expect(result).toEqual({
      research: { stats: { precision: 0.8, recall: 0.7 } }
    });
  });
});
