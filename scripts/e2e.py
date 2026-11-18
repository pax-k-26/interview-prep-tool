"""Headless end-to-end run against a live server: plays WAV answers as the candidate and prints per-turn latency.
Usage: uv run python scripts/e2e.py answer1.wav answer2.wav ..."""
import asyncio
import json
import sys
import time
import wave

import numpy as np
import websockets


def pcm16k(path: str) -> bytes:
    with wave.open(path) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32)
        n = int(len(x) * 16000 / w.getframerate())
        return np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype("<i2").tobytes()


async def until_state(ws, want: str, t0: float):
    first_audio = None
    while True:
        m = await ws.recv()
        if isinstance(m, bytes):
            first_audio = first_audio or time.time() - t0
            continue
        d = json.loads(m)
        if d["type"] == "caption":
            print(f"  {d['speaker']}: {d['text']}")
        elif d["type"] == "transcript":
            print(f"  [heard] {d['text']}")
        elif d["type"] == "state" and d["state"] == want:
            return first_audio, d
        elif d["type"] == "debrief":
            return first_audio, d


async def main(answers: list[str]) -> None:
    async with websockets.connect("ws://127.0.0.1:8000/ws", max_size=None) as ws:
        t0 = time.time()
        await ws.send(json.dumps({"type": "start"}))
        fa, _ = await until_state(ws, "your_turn", t0)
        print(f"opening: first audio {fa:.1f}s, turn done {time.time() - t0:.1f}s")
        for a in answers:
            await ws.send(pcm16k(a))
            t0 = time.time()
            await ws.send(json.dumps({"type": "finish"}))
            fa, _ = await until_state(ws, "your_turn", t0)
            print(f"turn: commit->first audio {fa:.1f}s, done {time.time() - t0:.1f}s")
        t0 = time.time()
        await ws.send(json.dumps({"type": "end"}))
        _, d = await until_state(ws, "never", t0)
        print(f"debrief in {time.time() - t0:.1f}s:\n{d['markdown']}")


asyncio.run(main(sys.argv[1:]))
