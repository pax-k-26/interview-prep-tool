# ADR-001: Fully local pipeline over a WebSocket (supersedes PRD §2.3 and §3.1 for the open-source build)

**Date:** 2026-10-10. **Status:** accepted for the prototype.

## Context
The goal changed from "best product on paid APIs" to "best product that is free and fully open source", published as a GitHub repo anyone can run on one Apple Silicon Mac. The PRD's LiveKit + Deepgram + ElevenLabs + Claude stack needs paid accounts. A self-hosted LiveKit server needs inbound UDP, which Cloudflare Tunnel does not carry.

## Decision
- Browser and server exchange audio over a **WebSocket** (plain HTTPS/TCP). No WebRTC, no LiveKit, no TURN, no router ports. It works through Cloudflare Tunnel.
- STT: Parakeet TDT 0.6B v2 (mlx-audio). TTS: Kokoro-82M (mlx-audio), one voice per panelist. LLM: any OpenAI-compatible endpoint; default gpt-oss-20b via llama.cpp.
- Turn-taking is ours: the mic streams only while it is the candidate's turn (the panel never talks over her and never hears itself); an **I'm finished** button, a 5 s silence auto-commit, and **I wasn't finished** recovery.
- Plain static HTML client, no build step.

## Consequences
- Zero marginal cost and no accounts. All data stays on the machine.
- No barge-in and no true full-duplex (the mic is closed while the panel speaks). Acceptable for interview practice; revisit.
- TCP head-of-line blocking can add delay on bad networks; fine for turn-based speech.
- Voice realism is below ElevenLabs (the research measured ~82% preference for ElevenLabs over Kokoro). Providers are small modules (`speech.py`, `llm.py`) so a better open TTS can be dropped in.

## Measured on a Mac mini M4 24 GB (2026-10-10)
- gpt-oss-20b MXFP4 (llama.cpp): prefill 424 tok/s at 4k and 333 tok/s at 16k; decode 35.7 tok/s.
- Metal recommended working set: 19.07 GB.
- Warm turn, her commit to first panel audio: 2.0-2.8 s (STT 0.4 s, LLM first token ~1 s, first-sentence TTS ~0.5 s). Opening line: 1.3 s.
- Target in the PRD was a median of 1.8 s; not yet met.
