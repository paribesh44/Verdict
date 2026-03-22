# Verdict

Verdict is a system-centric AI scaffold that combines:

- **LangGraph orchestration** for stateful multi-agent workflows
- **MARS hierarchical review** (Author → Independent Reviewers → Meta-Reviewer) with node-level streaming and a visual ReasoningGraph (ReactFlow)
- **AG-UI event streams** and A2UI declarative rendering
- **MCP-based tool routing** (including Firecrawl integration), with a PRIVATE-route guardrail that blocks external calls when triage is privacy-sensitive
- **Distributed state** via Redis (approvals, trajectory, extraction) with in-memory fallbacks
- **On-device or local SLM triage** (Anthropic, OpenAI, or Ollama) and PII redaction for local-only queries
- **Zero-trust policy gates** with human-in-the-loop interrupts
- **Audit plane** with an LLM-as-Judge scoring Faithfulness and Answer Correctness, and GAIA 2.0 / ARE eval reporting to `evals/latest_report.md`

For architecture details, see `docs/architecture.md`.

## Monorepo Layout

- `src/` - Next.js 15 host runtime, trusted UI renderer, ReasoningGraph (ReactFlow), and Session Insights drawer
- `services/orchestrator/` - FastAPI + LangGraph control plane (Redis-backed state, PII redaction, audit plane)
- `services/mcp_gateway/` - FastAPI MCP gateway for tool execution
- `contracts/` - JSON schemas for AG-UI and A2UI contracts
- `evals/` - GAIA 2.0 / ARE evaluation harness and audit reporting (`latest_report.md`)
- `docs/` - Architecture and operational documentation

## Prerequisites

- Node.js 20+ and npm
- Python 3.11+

## Quick Start

### Docker Compose

From repo root:

```bash
docker compose up --build
```

This starts Redis, the orchestrator, MCP gateway, and the Next.js host. The orchestrator uses `REDIS_URL=redis://redis:6379` and `MCP_GATEWAY_URL=http://mcp_gateway:9001/v1/tools/invoke`. The browser must reach the orchestrator at `http://localhost:8001` (mapped port).

- Next.js: `http://localhost:3000`
- Orchestrator: `http://localhost:8001`
- MCP Gateway: `http://localhost:9001`
- Redis: `localhost:6379`

## Environment Variables

**Single `.env` at repo root:** Next.js, the orchestrator, and the MCP gateway all read from the root `.env`. Copy `.env.example` to `.env` and fill in your keys. Do not commit `.env`.

### Frontend

- `NEXT_PUBLIC_ORCHESTRATOR_BASE_URL` (default: `http://localhost:8001`)

### Orchestrator

- `CORS_ALLOW_ORIGINS` (default: `http://localhost:3000,http://127.0.0.1:3000`)
- `MCP_GATEWAY_URL` (default: empty, tool calls stay in scaffold/fallback mode)
- `REDIS_URL` (optional; if set, approvals, trajectory, and extraction use Redis with keys `verdict:approval:{id}`, `verdict:trajectory:{trace_id}`, `verdict:extraction:{trace_id}`)
- `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` – for triage, extraction, MARS, and Judge (audit)
- `OLLAMA_BASE_URL` (default: `http://localhost:11434`) – for local Ollama triage when no cloud keys are set
- `OLLAMA_TRIAGE_MODEL` (default: `llama3.2`) – model used for triage when using Ollama

### MCP Gateway

- `FIRECRAWL_API_KEY` (required for real Firecrawl calls)
- `FIRECRAWL_BASE_URL` (default: `https://api.firecrawl.dev`)
- `FIRECRAWL_TIMEOUT_SECONDS` (default: `20`)

