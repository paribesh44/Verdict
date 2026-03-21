"use client";

import {
  ReactFlow,
  Background,
  Controls,
  Edge,
  Node,
  Position,
  useNodesState,
  useEdgesState,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import React, { useMemo, useEffect } from "react";
import type { AguiEvent } from "@/lib/contracts/agui";

const MARS_NODE_IDS = ["author", "reviewer_a", "reviewer_b", "meta_reviewer"] as const;
const EDGES: Edge[] = [
  { id: "e-author-ra", source: "author", target: "reviewer_a" },
  { id: "e-ra-rb", source: "reviewer_a", target: "reviewer_b" },
  { id: "e-rb-meta", source: "reviewer_b", target: "meta_reviewer" },
];

type NodeState = "idle" | "running" | "completed";

export type MarsNodeData = {
  label: string;
  status: NodeState;
  metrics?: { tokens: number; latency: number };
};

function nodeStateFromEvents(events: AguiEvent[]): Record<string, { status: NodeState; metrics?: { tokens: number; latency: number } }> {
  const state: Record<string, { status: NodeState; metrics?: { tokens: number; latency: number } }> = {};
  MARS_NODE_IDS.forEach((id) => {
    state[id] = { status: "idle" };
  });
  for (const event of events) {
    if (event.eventType !== "STATE_DELTA") continue;
    const path = event.payload.path;
    if (!path.startsWith("/research/graph/nodes/")) continue;
    const nodeName = path.slice("/research/graph/nodes/".length);
    if (!MARS_NODE_IDS.includes(nodeName as (typeof MARS_NODE_IDS)[number])) continue;
    const value = event.payload.value as { status?: string; metrics?: { tokens?: number; latency?: number } };
    state[nodeName] = {
      status: (value?.status === "running" ? "running" : value?.status === "completed" ? "completed" : "idle") as NodeState,
      metrics: value?.metrics
        ? { tokens: value.metrics.tokens ?? 0, latency: value.metrics.latency ?? 0 }
        : undefined,
    };
  }
  return state;
}

function MarsNode({ data }: NodeProps<Node<MarsNodeData>>) {
  const status = data?.status ?? "idle";
  const metrics = data?.metrics;
  const isRunning = status === "running";
  const isCompleted = status === "completed";
  return (
    <div
      className={`
        rounded-lg border-2 px-4 py-3 min-w-[140px] text-center
        ${isRunning ? "border-amber-500 bg-amber-500/10 animate-pulse" : ""}
        ${isCompleted ? "border-emerald-500 bg-emerald-500/10" : ""}
        ${status === "idle" ? "border-slate-600 bg-slate-800/50" : ""}
      `}
    >
      <div className="font-medium text-slate-200">{data?.label ?? ""}</div>
      {isCompleted && (
        <span className="text-emerald-400 text-sm" aria-hidden>
          ✓
        </span>
      )}
      {metrics != null && (
        <div className="text-xs text-slate-400 mt-1">
          {metrics.tokens} tok · {(metrics.latency ?? 0).toFixed(2)}s
        </div>
      )}
    </div>
  );
}

const nodeTypes = { mars: MarsNode as React.ComponentType<NodeProps<Node<MarsNodeData>>> };

const initialNodes: Node<MarsNodeData>[] = [
  { id: "author", type: "mars", position: { x: 0, y: 60 }, data: { label: "Author", status: "idle" }, sourcePosition: Position.Right, targetPosition: Position.Left },
  { id: "reviewer_a", type: "mars", position: { x: 200, y: 20 }, data: { label: "Reviewer A", status: "idle" }, sourcePosition: Position.Right, targetPosition: Position.Left },
  { id: "reviewer_b", type: "mars", position: { x: 200, y: 100 }, data: { label: "Reviewer B", status: "idle" }, sourcePosition: Position.Right, targetPosition: Position.Left },
  { id: "meta_reviewer", type: "mars", position: { x: 400, y: 60 }, data: { label: "Meta Reviewer", status: "idle" }, sourcePosition: Position.Right, targetPosition: Position.Left },
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
    <div className="h-[220px] w-full rounded-xl border border-slate-700 bg-slate-900/80">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        className="bg-transparent"
      >
        <Background color="#475569" gap={12} />
        <Controls showInteractive={false} className="bg-slate-800 rounded-lg" />
      </ReactFlow>
    </div>
  );
}
