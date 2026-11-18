#!/usr/bin/env bash
# Serve a local GGUF model on 127.0.0.1:8080 (OpenAI-compatible). Usage: scripts/run-llm.sh path/to/model.gguf
set -euo pipefail
exec llama-server -m "${1:?path to .gguf}" --host 127.0.0.1 --port 8080 \
  -c 16384 -fa on --jinja --cache-reuse 256 --reasoning-format auto
