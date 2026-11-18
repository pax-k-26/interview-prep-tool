"""Local speech: Parakeet STT and Kokoro TTS via mlx-audio. All MLX work runs on ONE thread (MLX streams are thread-bound)."""
import asyncio
import io
import os
import tempfile
import wave
from concurrent.futures import ThreadPoolExecutor

import numpy as np

STT_MODEL = os.environ.get("PP_STT_MODEL", "mlx-community/parakeet-tdt-0.6b-v2")
TTS_MODEL = os.environ.get("PP_TTS_MODEL", "mlx-community/Kokoro-82M-bf16")
_pool = ThreadPoolExecutor(max_workers=1)
_models: dict = {}


def _wav_bytes(pcm: np.ndarray, sr: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(pcm, -1, 1) * 32767).astype("<i2").tobytes())
    return buf.getvalue()


def _stt(pcm16k: bytes) -> str:
    if "stt" not in _models:
        from mlx_audio.stt.utils import load_model
        _models["stt"] = load_model(STT_MODEL)
    audio = np.frombuffer(pcm16k, dtype="<i2").astype(np.float32) / 32768
    with tempfile.NamedTemporaryFile(suffix=".wav") as f:
        f.write(_wav_bytes(audio, 16000))
        f.flush()
        return _models["stt"].generate(f.name).text.strip()


def _tts(text: str, voice: str) -> bytes:
    if "tts" not in _models:
        from mlx_audio.tts.utils import load_model
        _models["tts"] = load_model(TTS_MODEL)
    # Kokoro voices starting with 'b' are British English, 'a' American.
    chunks = [np.array(r.audio) for r in _models["tts"].generate(text=text, voice=voice, speed=1.0, lang_code=voice[0])]
    return _wav_bytes(np.concatenate(chunks), 24000)


async def transcribe(pcm16k: bytes) -> str:
    return await asyncio.get_running_loop().run_in_executor(_pool, _stt, pcm16k)


async def speak(text: str, voice: str) -> bytes:
    return await asyncio.get_running_loop().run_in_executor(_pool, _tts, text, voice)


async def warm() -> None:
    """Load both models and run each once so the first real turn is fast."""
    await speak("Hello.", "am_michael")
    noise = (np.random.default_rng(0).normal(0, 300, 16000 * 25)).astype("<i2").tobytes()  # long clip: compiles the real-length path
    await transcribe(noise)
