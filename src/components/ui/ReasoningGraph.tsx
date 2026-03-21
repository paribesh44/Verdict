"use client";

import {
  ReactFlow,
  Background,
  BackgroundVariant,
  Controls,
  Edge,
  Node,
  Position,
  Handle,
  useNodesState,
  useEdgesState,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import React, { useMemo, useEffect } from "react";
import type { AguiEvent } from "@/lib/contracts/agui";

const MARS_NODE_IDS = ["author", "reviewer_a", "reviewer_b", "meta_reviewer"] as const;
const EDGES: Edge[] = [
  { id: "e-author-ra", source: "author", target: "reviewer_a", animated: true, style: { stroke: '#64748b' } },
  { id: "e-ra-rb", source: "reviewer_a", target: "reviewer_b", animated: true, style: { stroke: '#64748b' } },
  { id: "e-rb-meta", source: "reviewer_b", target: "meta_reviewer", animated: true, style: { stroke: '#64748b' } },
];

type NodeState = "idle" | "running" | "completed";

export type MarsNodeData = {
  label: string;
  status: NodeState;
  metrics?: { tokens: number; latency: number };
};

// Icon helper based on agent name
function getIconForAgent(label: string) {
  if (label.includes("Author")) return "✍️";
  if (label.includes("Meta")) return "🧠";
  return "🔎"; // Reviewers
}

// ... (nodeStateFromEvents function remains exactly the same, omitted for brevity)
function nodeStateFromEvents(events: AguiEvent[]): Record<string, { status: NodeState; metrics?: { tokens: number; latency: number } }> {
  const state: Record<string, { status: NodeState; metrics?: { tokens: number; latency: number } }> = {};
  MARS_NODE_IDS.forEach((id) => { state[id] = { status: "idle" }; });
  for (const event of events) {
    if (event.eventType !== "STATE_DELTA") continue;
    const path = event.payload.path;
    if (!path.startsWith("/research/graph/nodes/")) continue;
    const nodeName = path.slice("/research/graph/nodes/".length);
    if (!MARS_NODE_IDS.includes(nodeName as (typeof MARS_NODE_IDS)[number])) continue;
    const value = event.payload.value as { status?: string; metrics?: { tokens?: number; latency?: number } };
    state[nodeName] = {
      status: (value?.status === "running" ? "running" : value?.status === "completed" ? "completed" : "idle") as NodeState,
      metrics: value?.metrics ? { tokens: value.metrics.tokens ?? 0, latency: value.metrics.latency ?? 0 } : undefined,
    };
  }
  return state;
}

function MarsNode({ data, id }: NodeProps<Node<MarsNodeData>>) {
  const status = data?.status ?? "idle";
  const metrics = data?.metrics;
  const isRunning = status === "running";
  const isCompleted = status === "completed";

  // Dynamic styling based on state
  const baseStyle = "relative rounded-xl border px-5 py-4 min-w-[180px] text-left transition-all duration-300 shadow-lg";
  const idleStyle = "border-slate-700 bg-slate-800/80 text-slate-400";
  const runningStyle = "border-indigo-500 bg-indigo-500/10 text-white shadow-[0_0_15px_rgba(99,102,241,0.3)] ring-1 ring-indigo-500";
  const completedStyle = "border-emerald-500/50 bg-emerald-500/5 text-slate-200";

  return (
    <div className={`${baseStyle} ${isRunning ? runningStyle : isCompleted ? completedStyle : idleStyle}`}>
      {/* Target Handle (Left) */}
      {id !== "author" && (
        <Handle type="target" position={Position.Left} className="!bg-slate-600 !w-1.5 !h-4 !rounded-sm !border-none" />
      )}

      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2 font-medium">
          <span>{getIconForAgent(data.label)}</span>
          {data?.label ?? ""}
        </div>
        {isRunning && <span className="flex w-2 h-2 rounded-full bg-indigo-500 animate-pulse"></span>}
        {isCompleted && <span className="text-emerald-500 text-sm">✓</span>}
      </div>

      {metrics ? (
        <div className="flex items-center gap-3 text-xs mt-3 pt-3 border-t border-slate-700/50">
          <span className="flex items-center gap-1 opacity-80">
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h7" /></svg>
            {metrics.tokens}
          </span>
          <span className="flex items-center gap-1 opacity-80">
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
            {(metrics.latency ?? 0).toFixed(2)}s
          </span>
        </div>
      ) : (
        <div className="h-4 mt-3 pt-3 border-t border-transparent"></div> /* Spacer for alignment */
      )}

      {/* Source Handle (Right) */}
      {id !== "meta_reviewer" && (
        <Handle type="source" position={Position.Right} className="!bg-slate-600 !w-1.5 !h-4 !rounded-sm !border-none" />
      )}
    </div>
  );
}

const nodeTypes = { mars: MarsNode as React.ComponentType<NodeProps<Node<MarsNodeData>>> };

const initialNodes: Node<MarsNodeData>[] = [
  { id: "author", type: "mars", position: { x: 0, y: 60 }, data: { label: "Author", status: "idle" } },
  { id: "reviewer_a", type: "mars", position: { x: 280, y: 0 }, data: { label: "Reviewer A", status: "idle" } },
  { id: "reviewer_b", type: "mars", position: { x: 280, y: 120 }, data: { label: "Reviewer B", status: "idle" } },
  { id: "meta_reviewer", type: "mars", position: { x: 560, y: 60 }, data: { label: "Meta Reviewer", status: "idle" } },
];

export function ReasoningGraph({ events }: { events: AguiEvent[] }) {
  const nodeState = useMemo(() => nodeStateFromEvents(events), [events]);
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, , onEdgesChange] = useEdgesState(EDGES);

  useEffect(() => {
    setNodes((nds) =>
      nds.map((n) => {
        const s = nodeState[n.id];
        return s ? { ...n, data: { ...n.data, status: s.status, metrics: s.metrics } } : n;
      })
    );
  }, [nodeState, setNodes]);

  return (
    <div className="h-[280px] w-full rounded-xl overflow-hidden bg-slate-950/50">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        className="bg-transparent"
      >
        {/* Update the variant prop here */}
        <Background color="#334155" size={2} gap={16} variant={BackgroundVariant.Dots} />
        <Controls showInteractive={false} className="bg-slate-900 border-slate-700 fill-slate-300 rounded-lg overflow-hidden shadow-lg" />
      </ReactFlow>
    </div>
  );
}