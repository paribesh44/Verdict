"use client";

import { ORCHESTRATOR_BASE_URL } from "@/lib/config";

export type ApprovalActionProps = {
  approvalId: string;
  reason: string;
  requestedAction: string;
  onApprove: () => void;
  onDeny: () => void;
  onResume: () => void;
  approved: boolean;
  isResuming: boolean;
};

export function ApprovalAction({
  approvalId,
  reason,
  requestedAction,
  onApprove,
  onDeny,
  onResume,
  approved,
  isResuming,
}: ApprovalActionProps) {
  async function handleApprove() {
    try {
      const res = await fetch(`${ORCHESTRATOR_BASE_URL}/v1/approvals/${approvalId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approved: true }),
      });
      if (res.ok) onApprove();
    } catch {
      // onError can be used by parent if we add it
    }
  }

  async function handleDeny() {
    try {
      const res = await fetch(`${ORCHESTRATOR_BASE_URL}/v1/approvals/${approvalId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approved: false }),
      });
      if (res.ok) onDeny();
    } catch {
      // ignore
    }
  }

  if (approved) {
    return (
      <section
        style={{
          border: "1px solid #2f3355",
          borderRadius: 12,
          padding: 16,
          background: "#12152a",
        }}
      >
        <p style={{ margin: "0 0 10px 0", color: "#9fa8ce", fontSize: 14 }}>
          Approval granted. Continue the research run with the same request.
        </p>
        <button
          type="button"
          onClick={onResume}
          disabled={isResuming}
          style={{
            padding: "10px 14px",
            borderRadius: 10,
            cursor: isResuming ? "not-allowed" : "pointer",
            background: "#2f3355",
            color: "#f7f8ff",
            border: "none",
          }}
        >
          {isResuming ? "Resuming..." : "Resume research"}
        </button>
      </section>
    );
  }

  return (
    <section
      style={{
        border: "1px solid #6b5b2e",
        borderRadius: 12,
        padding: 16,
        background: "#1a1a2e",
      }}
    >
      <p style={{ margin: "0 0 8px 0", color: "#ffd89d", fontSize: 14 }}>
        Pending approval: {reason}
      </p>
      <p style={{ margin: 0, color: "#9fa8ce", fontSize: 12 }}>
        Requested action: {requestedAction} ({approvalId})
      </p>
      <div style={{ display: "flex", gap: 10, marginTop: 12 }}>
        <button
          type="button"
          onClick={handleApprove}
          style={{
            padding: "8px 14px",
            borderRadius: 8,
            cursor: "pointer",
            background: "#2d5a2d",
            color: "#f7f8ff",
            border: "none",
          }}
        >
          Approve
        </button>
        <button
          type="button"
          onClick={handleDeny}
          style={{
            padding: "8px 14px",
            borderRadius: 8,
            cursor: "pointer",
            background: "#5a2d2d",
            color: "#f7f8ff",
            border: "none",
          }}
        >
          Deny
        </button>
      </div>
    </section>
  );
}
