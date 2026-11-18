#!/usr/bin/env bash
# One-time setup on Apple Silicon: Python deps, spaCy model, llama.cpp, and the default LLM (~11 GB).
set -euo pipefail
command -v uv >/dev/null || { echo "Install uv first: https://docs.astral.sh/uv/"; exit 1; }
command -v llama-server >/dev/null || brew install llama.cpp
uv sync
uv run python -m spacy download en_core_web_sm
mkdir -p models
[ -f models/gpt-oss-20b-MXFP4.gguf ] || curl -L -o models/gpt-oss-20b-MXFP4.gguf \
  https://huggingface.co/ggml-org/gpt-oss-20b-GGUF/resolve/main/gpt-oss-20b-MXFP4.gguf
[ -f config/round.json ] || cp config/round.example.json config/round.json
echo "Done. Edit config/round.json, then: scripts/run-llm.sh models/gpt-oss-20b-MXFP4.gguf  (terminal 1)  and  uv run python -m panelpractice.server  (terminal 2)"
