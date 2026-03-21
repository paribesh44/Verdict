#!/usr/bin/env bash
# Generate TypeScript and Python types from contracts/*.schema.json.
# Run from repo root. Idempotent.

set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

CONTRACTS_DIR="${ROOT}/contracts"
TS_OUT="${ROOT}/src/lib/contracts/generated"
PY_OUT="${ROOT}/services/orchestrator/app/contracts/generated"

mkdir -p "$TS_OUT" "$PY_OUT"

# TypeScript: json-schema-to-typescript (binary json2ts)
echo "Generating TypeScript from JSON Schema..."
npx --yes json-schema-to-typescript@15.0.4 -i "${CONTRACTS_DIR}/agui-events.schema.json" -o "${TS_OUT}/agui-events.ts"
npx --yes json-schema-to-typescript@15.0.4 -i "${CONTRACTS_DIR}/a2ui-envelope.schema.json" -o "${TS_OUT}/a2ui-envelope.ts"

# Python: datamodel-code-generator (orchestrator venv)
echo "Generating Python from JSON Schema..."
PY_VENV="${ROOT}/services/orchestrator/.venv/bin"
(cd "${ROOT}/services/orchestrator" && \
  "${PY_VENV}/datamodel-codegen" \
    --input ../../contracts/agui-events.schema.json \
    --input-file-type jsonschema \
    --output app/contracts/generated/agui_events.py \
    --output-model-type pydantic_v2.BaseModel)
(cd "${ROOT}/services/orchestrator" && \
  "${PY_VENV}/datamodel-codegen" \
    --input ../../contracts/a2ui-envelope.schema.json \
    --input-file-type jsonschema \
    --output app/contracts/generated/a2ui_envelope.py \
    --output-model-type pydantic_v2.BaseModel)

echo "Done. TS: ${TS_OUT}; Python: ${PY_OUT}"
