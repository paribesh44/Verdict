"use client";

import { FormEvent, useCallback, useMemo, useRef, useState } from "react";
import { streamResearch } from "@/agents/runtime/aguiClient";
import type { DataModel } from "@/agents/runtime/dataModel";
import { RuntimeEventStore } from "@/agents/runtime/eventStore";
import { ApprovalAction } from "@/components/ui/ApprovalAction";
import { A2UIRenderer } from "@/components/ui/A2UIRenderer";
import { ReasoningGraph } from "@/components/ui/ReasoningGraph";
import { SessionInsights } from "@/components/ui/SessionInsights";
import type { AguiEvent } from "@/lib/contracts/agui";
import type { SurfaceComponentBlueprint } from "@/lib/contracts/types";
import { ORCHESTRATOR_BASE_URL } from "@/lib/config";

function getLatestInterrupt(events: AguiEvent[]) {
  for (let index = events.length - 1; index >= 0; index -= 1) {
    const event = events[index];
    if (event.eventType === "INTERRUPT") {
      return event;
    }
  }
  return undefined;
}

export default function Page() {
  const [query, setQuery] = useState("Summarize the latest Verdict AI orchestration patterns.");
  const [events, setEvents] = useState<AguiEvent[]>([]);
  const [components, setComponents] = useState<SurfaceComponentBlueprint[]>([]);
  const [dataModel, setDataModel] = useState<DataModel>({});
  const [isRunning, setIsRunning] = useState(false);
  const [isResuming, setIsResuming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [approvedApprovalId, setApprovedApprovalId] = useState<string | null>(null);
  const [deniedApprovalIds, setDeniedApprovalIds] = useState<Set<string>>(new Set());
  const [sessionInsightsOpen, setSessionInsightsOpen] = useState(false);
  const [lastTraceId, setLastTraceId] = useState<string | null>(null);
  const storeRef = useRef(new RuntimeEventStore());

  const latestInterrupt = useMemo(() => getLatestInterrupt(events), [events]);
  const interruptApproved =
    latestInterrupt?.eventType === "INTERRUPT" &&
    approvedApprovalId === latestInterrupt.payload.approvalId;
  const interruptDenied =
    latestInterrupt?.eventType === "INTERRUPT" &&
    deniedApprovalIds.has(latestInterrupt.payload.approvalId);

  const runStream = useCallback(
    async (approvalId?: string) => {
      setIsRunning(true);
      setError(null);
      try {
        await streamResearch(
          `${ORCHESTRATOR_BASE_URL}/v1/research/stream`,
          {
            query,
            actorId: "local-user",
            intent: "research",
            ...(approvalId ? { approvalId } : {}),
          },
          {
            onEvent: (incoming) => {
              if ("traceId" in incoming) setLastTraceId(incoming.traceId);
              storeRef.current.appendEvent(incoming);
              const snapshot = storeRef.current.replay();
              setEvents(snapshot.events);
              setComponents(snapshot.components);
              setDataModel(snapshot.dataModel);
            },
            onEnvelope: (incoming) => {
              storeRef.current.appendEnvelope(incoming);
              const snapshot = storeRef.current.replay();
              setEvents(snapshot.events);
              setComponents(snapshot.components);
              setDataModel(snapshot.dataModel);
            },
            onError: (incomingError) => {
              setError(incomingError.message);
            },
          }
        );
      } catch (streamError) {
        setError((streamError as Error).message);
      } finally {
        setIsRunning(false);
        setIsResuming(false);
        if (approvalId) setApprovedApprovalId(null);
      }
    },
    [query]
  );

  async function handleRun(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setEvents([]);
    setComponents([]);
    setDataModel({});
    setApprovedApprovalId(null);
    setLastTraceId(null);
    storeRef.current = new RuntimeEventStore();
    await runStream();
  }

  function handleResume() {
    if (!approvedApprovalId) return;
    setIsResuming(true);
    runStream(approvedApprovalId);
  }

  return (
    <main style={{ maxWidth: 980, margin: "40px auto", padding: "0 20px", display: "grid", gap: 18 }}>
      <h1 style={{ margin: 0 }}>Verdict</h1>
      <form onSubmit={handleRun} style={{ display: "grid", gap: 10 }}>
        <label htmlFor="query">Research request</label>
        <textarea
          id="query"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          rows={4}
          style={{ width: "100%", borderRadius: 10, padding: 12, background: "#11142a", color: "#f7f8ff" }}
        />
        <button
          type="submit"
          disabled={isRunning}
          style={{ width: 220, padding: "10px 14px", borderRadius: 10, cursor: "pointer" }}
        >
          {isRunning ? "Running..." : "Run MARS Research"}
        </button>
      </form>

      {error ? <p style={{ color: "#ffadad" }}>Error: {error}</p> : null}

      {latestInterrupt?.eventType === "INTERRUPT" && !interruptDenied ? (
        <ApprovalAction
          approvalId={latestInterrupt.payload.approvalId}
          reason={latestInterrupt.payload.reason}
          requestedAction={latestInterrupt.payload.requestedAction}
          onApprove={() => setApprovedApprovalId(latestInterrupt.payload.approvalId)}
          onDeny={() =>
            setDeniedApprovalIds((prev: Set<string>) =>
              new Set(prev).add(latestInterrupt.payload.approvalId)
            )
          }
          onResume={handleResume}
          approved={!!interruptApproved}
          isResuming={isResuming}
        />
      ) : null}
      {interruptDenied ? (
        <p style={{ color: "#ce8a8a" }}>Approval was denied. Start a new research request.</p>
      ) : null}

      <ReasoningGraph events={events} />
      <A2UIRenderer components={components} dataModel={dataModel} />

      <button
        type="button"
        onClick={() => setSessionInsightsOpen(true)}
        className="mt-2 text-sm text-slate-400 hover:text-slate-200"
      >
        Session Insights
      </button>
      <SessionInsights
        traceId={lastTraceId}
        open={sessionInsightsOpen}
        onClose={() => setSessionInsightsOpen(false)}
      />
    </main>
  );
}
