"use client";

import type { JsonValue } from "@/lib/contracts/types";

type SurfaceProps = Record<string, JsonValue>;

function asStringArray(value: JsonValue | undefined): string[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => String(item));
}

export function StatusCard({ title, value }: SurfaceProps) {
  return (
    <article
      style={{
        border: "1px solid #2f3355",
        borderRadius: 12,
        padding: 16,
        background: "#12152a"
      }}
    >
      <p style={{ margin: 0, color: "#9fa8ce", fontSize: 12 }}>{String(title ?? "Status")}</p>
      <h3 style={{ margin: "8px 0 0 0" }}>{String(value ?? "")}</h3>
    </article>
  );
}

export function ClaimsList({ title, claims }: SurfaceProps) {
  const claimList = asStringArray(claims);

  return (
    <section>
      <h3 style={{ margin: "0 0 8px 0" }}>{String(title ?? "Claims")}</h3>
      <ul style={{ margin: 0, paddingLeft: 20 }}>
        {claimList.map((claim) => (
          <li key={claim}>{claim}</li>
        ))}
      </ul>
    </section>
  );
}

export function MessageSurface({ role, content }: SurfaceProps) {
  return (
    <article
      style={{
        border: "1px solid #2f3355",
        borderRadius: 10,
        padding: 12,
        background: "#0f1120"
      }}
    >
      <strong style={{ display: "block", marginBottom: 6 }}>{String(role ?? "assistant")}</strong>
      <span>{String(content ?? "")}</span>
    </article>
  );
}

export const trustedCatalog = {
  StatusCard,
  ClaimsList,
  MessageSurface
};

export type TrustedComponentName = keyof typeof trustedCatalog;
