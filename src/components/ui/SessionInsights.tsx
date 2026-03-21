"use client";

import { useCallback, useEffect, useState } from "react";
import { ORCHESTRATOR_BASE_URL } from "@/lib/config";

type TrajectoryStep = {
  trace_id: string;
  step_name: string;
  precision: number;
  recall: number;
  token_estimate: number;
  latency_ms: number;
  timestamp: string;
};

type TrajectoryResponse = {
  traceId: string;
  steps: TrajectoryStep[];
};

export function SessionInsights({
  traceId,
  open,
  onClose,
}: {
  traceId: string | null;
  open: boolean;
  onClose: () => void;
}) {
  const [data, setData] = useState<TrajectoryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchTrajectory = useCallback(async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${ORCHESTRATOR_BASE_URL}/v1/trajectory/${id}`);
      if (!res.ok) throw new Error(`Failed to load trajectory: ${res.status}`);
      const json: TrajectoryResponse = await res.json();
      setData(json);
    } catch (e) {
      setError((e as Error).message);
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open && traceId) fetchTrajectory(traceId);
  }, [open, traceId, fetchTrajectory]);

  if (!open) return null;

  const totalTokens = data?.steps.reduce((acc, s) => acc + s.token_estimate, 0) ?? 0;
  const totalLatency = data?.steps.reduce((acc, s) => acc + s.latency_ms, 0) ?? 0;

  return (
    <>
      <div
        className="fixed inset-0 bg-black/50 z-40"
        aria-hidden
        onClick={onClose}
      />
      <div
        className="fixed right-0 top-0 bottom-0 w-full max-w-md bg-slate-900 border-l border-slate-700 z-50 shadow-xl overflow-y-auto"
        role="dialog"
        aria-label="Session Insights"
      >
        <div className="p-4 flex items-center justify-between border-b border-slate-700">
          <h2 className="text-lg font-semibold text-slate-100">Session Insights</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-slate-400 hover:text-slate-200 rounded p-1"
            aria-label="Close"
          >
            ✕
          </button>
        </div>
        <div className="p-4 space-y-4">
          {traceId && (
            <p className="text-xs text-slate-500 font-mono truncate" title={traceId}>
              Trace: {traceId.slice(0, 8)}…
            </p>
          )}
          {loading && <p className="text-slate-400">Loading…</p>}
          {error && <p className="text-red-400 text-sm">{error}</p>}
          {data && !loading && (
            <>
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-lg bg-slate-800 p-3 border border-slate-700">
                  <div className="text-xs text-slate-400 uppercase tracking-wider">Total tokens</div>
                  <div className="text-xl font-semibold text-slate-100">{totalTokens}</div>
                </div>
                <div className="rounded-lg bg-slate-800 p-3 border border-slate-700">
                  <div className="text-xs text-slate-400 uppercase tracking-wider">Total latency</div>
                  <div className="text-xl font-semibold text-slate-100">{(totalLatency / 1000).toFixed(2)}s</div>
                </div>
              </div>
              <div>
                <h3 className="text-sm font-medium text-slate-300 mb-2">Steps</h3>
                <ul className="space-y-2">
                  {data.steps.map((step, i) => (
                    <li
                      key={`${step.step_name}-${i}`}
                      className="rounded-lg bg-slate-800/80 p-3 border border-slate-700 text-sm"
                    >
                      <div className="font-medium text-slate-200">{step.step_name}</div>
                      <div className="text-slate-400 text-xs mt-1">
                        {step.token_estimate} tokens · {step.latency_ms}ms
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            </>
          )}
        </div>
      </div>
    </>
  );
}
