"""FastAPI server: serves the web client and runs one interview session per WebSocket."""
import asyncio
import json
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from . import llm, speech
from .director import END_TOKEN, StreamParser, system_prompt

ROOT = Path(__file__).resolve().parent.parent


@asynccontextmanager
async def lifespan(_: FastAPI):
    await speech.warm()  # load + compile both speech models before the first interview
    yield


app = FastAPI(lifespan=lifespan)


def load_round() -> dict:
    p = ROOT / "config" / "round.json"
    return json.loads((p if p.exists() else ROOT / "config" / "round.example.json").read_text())


@app.get("/")
def index() -> FileResponse:
    return FileResponse(ROOT / "web" / "index.html")


@app.get("/api/round")
def api_round() -> dict:
    r = load_round()
    return {k: r[k] for k in ("role", "organization", "panel")}


DEBRIEF_PROMPT = """You are a warm, rigorous interview coach. Below is the transcript of a mock panel interview. Write a debrief in Markdown with exactly these sections:
## What went well (2-3 points, each with a short exact quote from her)
## Top 3 priorities (each: what happened with an exact quote, why a panel would care, and what a stronger answer would include. Describe the shape of a better answer; never write a script for her)
## Delivery (length, hedging, structure)
## Practice next (one concrete thing)
Be specific and honest, strengths first, never harsh. Only use facts that appear in the transcript. Plain English."""


class Session:
    def __init__(self, ws: WebSocket):
        self.ws, self.round = ws, load_round()
        self.voices = {p["name"]: p["voice"] for p in self.round["panel"]}
        self.names = list(self.voices)
        self.messages = [{"role": "system", "content": system_prompt(self.round)}]
        self.buf = b""
        self.prev_buf = b""
        self.turn_start = 0  # index in messages where the in-flight turn began
        self.task: asyncio.Task | None = None
        self.started = time.time()
        self.log: list[dict] = []
        self.ended = False

    async def send(self, **kw) -> None:
        await self.ws.send_text(json.dumps(kw))

    async def say(self, speaker: str, text: str) -> None:
        self.log.append({"speaker": speaker, "text": text})
        await self.send(type="caption", speaker=speaker, text=text)
        t = time.perf_counter()
        wav = await speech.speak(text, self.voices[speaker])
        print(f"  tts {time.perf_counter() - t:.2f}s for {len(text.split())} words", flush=True)
        await self.ws.send_bytes(wav)

    async def director_turn(self, user_text: str) -> None:
        mins = (time.time() - self.started) / 60
        note = f"\n[Elapsed: {mins:.0f} of {self.round.get('minutes', 30)} minutes.]"
        self.turn_start = len(self.messages)
        self.messages.append({"role": "user", "content": user_text + note})
        await self.send(type="state", state="thinking")
        full, parser = "", StreamParser(self.names)
        t0 = time.perf_counter()
        async for tok in llm.stream(self.messages):
            if not full:
                print(f"  llm first token {time.perf_counter() - t0:.2f}s", flush=True)
            full += tok
            # Speak each finished sentence while the model keeps generating.
            for who, sent in parser.feed(tok):
                await self.say(who, sent)
        for who, sent in parser.feed("", final=True):
            await self.say(who, sent)
        self.messages.append({"role": "assistant", "content": full})
        if END_TOKEN in full:
            await self.finish_interview()
        else:
            await self.send(type="state", state="your_turn")

    async def finish_interview(self) -> None:
        if self.ended:
            return
        self.ended = True
        await self.send(type="state", state="debriefing")
        transcript = "\n".join(f"{m['speaker']}: {m['text']}" for m in self.log)
        md = await llm.complete([{"role": "system", "content": DEBRIEF_PROMPT}, {"role": "user", "content": transcript}])
        out = ROOT / "data" / "sessions"
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{time.strftime('%Y%m%d-%H%M%S')}.json").write_text(json.dumps({"log": self.log, "debrief": md}, indent=1))
        await self.send(type="debrief", markdown=md)

    async def commit(self) -> None:
        if len(self.buf) < 16000 * 2 * 0.4:  # under 0.4 s of audio
            self.buf = b""
            return await self.send(type="state", state="your_turn")
        await self.send(type="state", state="thinking")
        self.prev_buf, audio, self.buf = self.buf, self.buf, b""
        t = time.perf_counter()
        text = await speech.transcribe(audio)
        print(f"  stt {time.perf_counter() - t:.2f}s for {len(audio) / 32000:.1f}s audio", flush=True)
        await self.send(type="transcript", text=text)
        self.log.append({"speaker": "Candidate", "text": text})
        await self.director_turn(text or "(inaudible)")

    def spawn(self, coro) -> None:
        self.task = asyncio.create_task(coro)
        self.task.add_done_callback(self._report)

    def _report(self, t: asyncio.Task) -> None:
        if not t.cancelled() and t.exception():
            print(f"TURN FAILED: {t.exception()!r}", flush=True)
            asyncio.create_task(self.send(type="error", message="Something went wrong on the server. Press I'm finished to retry, or reload."))

    async def cancel_turn(self) -> None:
        if self.task and not self.task.done():
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)

    async def resume_answer(self) -> None:
        """'I wasn't finished': drop the panel's reply and keep recording on top of the previous audio."""
        await self.cancel_turn()
        del self.messages[self.turn_start :]
        while self.log and self.log[-1]["speaker"] != "Candidate":
            self.log.pop()
        if self.log and self.log[-1]["speaker"] == "Candidate":
            self.log.pop()
        self.buf, self.prev_buf = self.prev_buf, b""
        await self.send(type="state", state="your_turn")

    async def run(self) -> None:
        try:
            while True:
                m = await self.ws.receive()
                if m.get("bytes"):
                    self.buf += m["bytes"]
                    continue
                if m.get("type") == "websocket.disconnect":
                    break
                msg = json.loads(m["text"])
                t = msg["type"]
                if t == "start":
                    self.spawn(self.director_turn("[Begin the interview.]"))
                elif t == "finish":
                    self.spawn(self.commit())
                elif t == "continue":
                    await self.resume_answer()
                elif t == "end":
                    await self.cancel_turn()
                    self.spawn(self.finish_interview())
        except WebSocketDisconnect:
            pass
        finally:
            await self.cancel_turn()


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    await Session(ws).run()


def main() -> None:
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
