"use client";

import React, { useState } from "react";
import type { JsonValue } from "@/lib/contracts/types";

type SurfaceProps = Record<string, JsonValue>;

function asStringArray(value: JsonValue | undefined): string[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => String(item));
}

// 1. The Metric Card (e.g., MARS Token Gain Ratio)
export function StatusCard({ title, value }: SurfaceProps) {
  return (
    <article className="relative overflow-hidden rounded-xl bg-slate-900 border border-slate-800 p-5 shadow-sm transition-all hover:border-slate-700">
      <div className="absolute top-0 right-0 p-4 opacity-10">
        <svg className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
        </svg>
      </div>
      <p className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">
        {String(title ?? "Status")}
      </p>
      <h3 className="text-2xl font-light text-slate-100">
        {String(value ?? "")}
      </h3>
    </article>
  );
}

// Helper Component for Individual Expandable Claims
function ClaimItem({ claim }: { claim: string }) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div 
      onClick={() => setIsOpen(!isOpen)}
      className="flex items-start gap-3 p-4 rounded-xl bg-slate-900/50 border border-slate-800 hover:border-slate-700 transition-all shadow-sm cursor-pointer group"
    >
      {/* Check Icon */}
      <div className="mt-0.5 text-slate-500 group-hover:text-emerald-500 transition-colors flex-shrink-0">
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      </div>
      
      {/* Claim Text */}
      <div className="flex-1">
        <p className={`text-sm text-slate-300 leading-relaxed transition-all duration-200 ${isOpen ? "" : "line-clamp-2"}`}>
          {claim}
        </p>
      </div>

      {/* Expand/Collapse Chevron */}
      <div className="mt-0.5 text-slate-600 group-hover:text-slate-400 transition-colors flex-shrink-0">
        <svg 
          className={`w-4 h-4 transition-transform duration-200 ${isOpen ? "rotate-180" : ""}`} 
          fill="none" 
          viewBox="0 0 24 24" 
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </div>
    </div>
  );
}

// 2. The Extracted Claims List
export function ClaimsList({ title, claims }: SurfaceProps) {
  const claimList = asStringArray(claims);

  if (claimList.length === 0) return null;

  return (
    <section className="flex flex-col gap-4">
      <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-2">
        <svg className="w-4 h-4 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
        </svg>
        {String(title ?? "Extracted Claims")}
      </h3>
      <div className="grid grid-cols-1 gap-3">
        {claimList.map((claim, index) => (
          <ClaimItem key={index} claim={claim} />
        ))}
      </div>
    </section>
  );
}

// 3. The Assistant Synthesis (The highlighted, final verdict)
export function MessageSurface({ role, content }: SurfaceProps) {
  const isAssistant = String(role ?? "").toLowerCase() === "assistant";

  return (
    <article className="relative mt-2">
      {/* Subtle background glow for the assistant's final output */}
      {isAssistant && (
        <div className="absolute -inset-[1px] bg-gradient-to-r from-indigo-500/20 to-purple-500/20 rounded-2xl blur-sm opacity-50"></div>
      )}
      
      <div className={`relative p-6 rounded-2xl border shadow-xl ${
        isAssistant 
          ? "bg-slate-950 border-indigo-500/30" 
          : "bg-slate-900 border-slate-800"
      }`}>
        <div className="flex items-center gap-2 mb-3 border-b border-slate-800 pb-3">
          {isAssistant && (
            <span className="flex w-2 h-2 rounded-full bg-indigo-500 animate-pulse"></span>
          )}
          <strong className={`text-sm font-medium uppercase tracking-wider ${
            isAssistant ? "text-indigo-400" : "text-slate-400"
          }`}>
            {String(role ?? "Assistant")}
          </strong>
        </div>
        
        <div className="text-base text-slate-200 leading-relaxed whitespace-pre-wrap">
          {String(content ?? "")}
        </div>
      </div>
    </article>
  );
}

export const trustedCatalog = {
  StatusCard,
  ClaimsList,
  MessageSurface,
};

export type TrustedComponentName = keyof typeof trustedCatalog;