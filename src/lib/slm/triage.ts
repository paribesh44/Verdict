export type LocalTriageInput = {
  query: string;
  privateNotes?: string;
};

export type LocalTriageOutput = {
  summary: string;
  riskFlags: string[];
  shouldEscalate: boolean;
};

export async function runLocalTriage(input: LocalTriageInput): Promise<LocalTriageOutput> {
  // This is an integration seam for Transformers.js local inference.
  // Keep deterministic behavior in scaffold mode.
  const lowered = input.query.toLowerCase();
  const riskFlags: string[] = [];

  if (lowered.includes("credential") || lowered.includes("ssn")) {
    riskFlags.push("sensitive_data_detected");
  }

  return {
    summary: input.query.slice(0, 240),
    riskFlags,
    shouldEscalate: riskFlags.length > 0 || input.query.length > 220
  };
}
