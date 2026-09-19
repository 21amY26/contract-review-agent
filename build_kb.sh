#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Prefer the project virtualenv's interpreter so dependencies (python-docx,
# sentence-transformers, chromadb, ...) resolve even when the venv isn't
# activated. Falls back to an active venv, then python3 on PATH.
if [ -x "$SCRIPT_DIR/.venv/bin/python" ]; then
  PY="$SCRIPT_DIR/.venv/bin/python"
elif [ -n "${VIRTUAL_ENV:-}" ] && [ -x "$VIRTUAL_ENV/bin/python" ]; then
  PY="$VIRTUAL_ENV/bin/python"
else
  PY="python3"
fi
echo "Using interpreter: $PY"

if [ -d "kb/chroma" ]; then
  rm -rf "kb/chroma"
fi
mkdir -p "kb/chroma"

"$PY" -m src.ingestion.ingest_contracts kb/contracts/cuad kb/contracts/sec
"$PY" -m src.ingestion.ingest_compliance kb/policies/gdpr kb/policies/hipaa kb/policies/iso27001 kb/policies/internal
"$PY" -m src.ingestion.ingest_risks kb/risks/risk_rules.json

