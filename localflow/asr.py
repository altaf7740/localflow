import numpy as np
import mlx_whisper

from .config import Config

MIN_SAMPLES = 16000 // 4  # ignore taps shorter than 250 ms


def transcribe(audio: np.ndarray | str, cfg: Config) -> str:
    if isinstance(audio, np.ndarray):
        if audio.size < MIN_SAMPLES or np.abs(audio).max() < 0.01:
            return ""
    prompt = cfg.asr_prompt
    if cfg.vocabulary:
        prompt += " " + ", ".join(cfg.vocabulary) + "."
    result = mlx_whisper.transcribe(
        audio,
        path_or_hf_repo=cfg.asr_model,
        language=cfg.asr_language,
        initial_prompt=prompt,
        temperature=0.0,
        condition_on_previous_text=False,
    )
    return result["text"].strip()


def warmup(cfg: Config):
    transcribe(np.zeros(16000, dtype=np.float32) + 0.02, cfg)
