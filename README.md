# Panel Practice

A free, open-source, **fully local** mock panel interview. You speak out loud; a simulated panel (names and titles you provide, one distinct voice each) asks questions built from your résumé and the job description, probes vague answers, and then gives you written coaching. Everything runs on your own Mac: no accounts, no API keys, no cloud, no cost. Your résumé and recordings never leave the machine.

> **Status: working prototype (v0.1).** The full voice loop works end to end. See [Known limits](#known-limits).

## How it works

```text
Safari/Chrome  ──WebSocket (HTTPS)──►  FastAPI server (your Mac)
 mic → 16 kHz PCM                       Parakeet STT  →  LLM (llama.cpp, any OpenAI-compatible model)
 plays WAV per sentence  ◄───────────   Kokoro TTS, one voice per panelist (speaks sentence 1 while the LLM writes sentence 2)
```

- **You are never cut off.** The panel only listens when it is your turn and only replies when you press **I'm finished** or pause for 5 seconds. **I wasn't finished** takes back a premature reply and keeps recording.
- **Plain WebSocket, not WebRTC.** It works behind any NAT and through Cloudflare Tunnel with no open ports.

## Requirements

Apple Silicon Mac, 16 GB+ (developed on an M4 with 24 GB), macOS 14+, [uv](https://docs.astral.sh/uv/), [Homebrew](https://brew.sh), about 15 GB free disk.

## Quick start

```bash
scripts/setup.sh                                  # deps, llama.cpp, the default model (~11 GB)
$EDITOR config/round.json                         # your role, panel, résumé, job description
scripts/run-llm.sh models/gpt-oss-20b-MXFP4.gguf  # terminal 1: the language model
uv run python -m panelpractice.server             # terminal 2: app (first start loads and warms the speech models)
open http://127.0.0.1:8000
```

Panel voices are Kokoro voice IDs (`af_sarah`, `am_michael`, `bf_emma`, `bm_george`, …) in `config/round.json`.

To use another model, run any OpenAI-compatible server and set `PP_LLM_URL` / `PP_LLM_MODEL` (see `.env.example`).

## Tests

```bash
uv run pytest                                     # unit tests
uv run python scripts/e2e.py answer1.wav ...      # headless run against a live server; prints latency per turn
```

## Known limits

- Voices are good, not human-perfect: Kokoro-82M is the best permissively licensed option we found, and was **not** beaten in our research by anything we may legally use, but trails paid voices in blind tests.
- The panel replies about 2-3 s after you finish (target 1.8 s).
- No barge-in: the mic is closed while the panel speaks.
- A 20B local model is weaker than frontier models at holding personas and at exact quoting in the debrief. Quotes in the debrief are not yet verified against the transcript.
- Only tested on macOS 14+ with Chromium headless; **Safari and a real iMac are untested.**
- Single user, no login. Do not expose it to the internet without adding authentication.

## Docs

`docs/adr/` records decisions and measurements.

## Contributing and license

Issues and pull requests welcome. Apache-2.0; see `LICENSE` and `NOTICE` (Parakeet weights are CC-BY-4.0).
