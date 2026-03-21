# Verdict

Verdict is a production-grade, system-centric AI scaffold that combines:

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

### Option A: Docker Compose (recommended for production-like runs)

From repo root:

```bash
docker compose up --build
```

This starts Redis, the orchestrator, MCP gateway, and the Next.js host. The orchestrator uses `REDIS_URL=redis://redis:6379` and `MCP_GATEWAY_URL=http://mcp_gateway:9001/v1/tools/invoke`. The browser must reach the orchestrator at `http://localhost:8001` (mapped port).

- Next.js: `http://localhost:3000`
- Orchestrator: `http://localhost:8001`
- MCP Gateway: `http://localhost:9001`
- Redis: `localhost:6379`

### Option B: Local development

#### 1) Install frontend dependencies

From repo root:

```bash
npm install
```

#### 2) Create orchestrator virtual environment

From repo root:

```bash
python -m venv services/orchestrator/.venv
services/orchestrator/.venv/bin/pip install -e "services/orchestrator[dev]"
```

#### 3) Run both services

From repo root:

```bash
npm run dev
```

This starts:

- Next.js host at `http://localhost:3000`
- Orchestrator API at `http://localhost:8001`

Optional: set `REDIS_URL` to use Redis for approvals, trajectory, and extraction (e.g. `REDIS_URL=redis://localhost:6379`). Without it, in-memory backends are used.

#### 4) (Optional) Enable real MCP tool execution

From repo root:

```bash
python -m venv services/mcp_gateway/.venv
services/mcp_gateway/.venv/bin/pip install -e "services/mcp_gateway[dev]"
npm run dev:mcp
```

Add your API keys to the **root `.env` file** (see below). All services read from this single file.

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

## Useful Scripts

From repo root:

- `npm run dev` - run web + orchestrator concurrently
- `npm run dev:with-mcp` - run web + orchestrator + MCP gateway
- `npm run dev:web` - run Next.js only
- `npm run dev:orchestrator` - run FastAPI orchestrator only
- `npm run dev:mcp` - run FastAPI MCP gateway only
- `npm run lint` - lint TypeScript/TSX sources
- `npm run typecheck` - TypeScript type checking
- `npm run test` - run frontend/runtime tests with Vitest
- `npm run generate:contracts` - generate TypeScript + Python contract models from JSON schemas

## Testing

From repo root:

```bash
npm run test
```

From orchestrator package:

```bash
services/orchestrator/.venv/bin/python -m pytest services/orchestrator/tests
```

From MCP gateway package:

```bash
services/mcp_gateway/.venv/bin/python -m pytest services/mcp_gateway/tests
```

## API Endpoints (Orchestrator)

- `GET /health` - service health check
- `POST /v1/research/stream` - SSE stream of AG-UI events and A2UI envelopes (includes STATE_DELTA for MARS node lifecycle at `/research/graph/nodes/{node_name}`)
- `POST /v1/approvals/{approval_id}` - approve or deny a pending sensitive action (Redis or in-memory)
- `GET /v1/trajectory/{trace_id}` - fetch recorded reasoning trajectory steps (Redis or in-memory); used by the Session Insights drawer
- `POST /v1/eval/audit` - run Judge LLM on a trace; body: `{ "traceId": string, "groundTruth"?: string }`; returns `faithfulness` and `answerCorrectness` (0–1)

## UI Features

- **ReasoningGraph** – ReactFlow diagram of the MARS topology (author → reviewer_a → reviewer_b → meta_reviewer). Subscribes to STATE_DELTA events to show running (pulse) and completed (checkmark + tokens/latency) per node.
- **Session Insights** – Drawer that fetches `GET /v1/trajectory/{trace_id}` and displays total tokens, latency, and per-step breakdown (Tailwind-styled).

## Evaluation and Audit

Run the GAIA 2.0 ARE runner with audit and report generation:

```bash
python evals/gaia2_are_runner.py --tasks evals/tasks/sample_gaia2_tasks.jsonl --orchestrator-url http://localhost:8001 --audit --report evals/latest_report.md
```

With `--audit`, the runner parses the stream for `traceId`, calls `POST /v1/eval/audit` with task ground truth, aggregates Faithfulness and Answer Correctness, computes F1 for the extraction pipeline, and writes `evals/latest_report.md`.