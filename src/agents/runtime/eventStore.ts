import type { AguiEvent } from "@/lib/contracts/agui";
import type { A2UIEnvelope } from "@/lib/contracts/a2ui";
import type { DataUpdate, SurfaceComponentBlueprint } from "@/lib/contracts/types";
import { applyDataUpdates, type DataModel } from "./dataModel";

export type RuntimeSnapshot = {
  events: AguiEvent[];
  components: SurfaceComponentBlueprint[];
  dataModel: DataModel;
};

export class RuntimeEventStore {
  private events: AguiEvent[] = [];
  private envelopes: A2UIEnvelope[] = [];
  private components: SurfaceComponentBlueprint[] = [];
  private dataModel: DataModel = {};

  appendEvent(event: AguiEvent): void {
    this.events.push(event);
  }

  appendEnvelope(envelope: A2UIEnvelope): void {
    this.envelopes.push(envelope);
    if (envelope.type === "surfaceUpdate") {
      this.components = envelope.components as SurfaceComponentBlueprint[];
      return;
    }
    if (envelope.type === "dataModelUpdate") {
      this.dataModel = applyDataUpdates(this.dataModel, envelope.updates as DataUpdate[]);
    }
  }

  replay(): RuntimeSnapshot {
    return {
      events: [...this.events],
      components: [...this.components],
      dataModel: structuredClone(this.dataModel)
    };
  }
}
