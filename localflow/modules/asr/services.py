import numpy as np

from ...core.config.settings import APPLE_SILICON, Config
from ...shared.audio import load_wav

MIN_SAMPLES = 16000 // 4  # ignore taps shorter than 250 ms

_faster_whisper_model = None


def transcribe(audio: np.ndarray | str, cfg: Config) -> str:
    if isinstance(audio, str):
        audio = load_wav(audio)
    if audio.size < MIN_SAMPLES or np.abs(audio).max() < 0.01:
        return ""
    prompt = cfg.asr_prompt
    if cfg.vocabulary:
        prompt += " " + ", ".join(cfg.vocabulary) + "."
    # an empty prompt still becomes a lone space token, which derails decoding
    prompt = prompt.strip() or None
    if _use_mlx(cfg):
        return _transcribe_mlx(audio, prompt, cfg)
    return _transcribe_faster_whisper(audio, prompt, cfg)


def warmup(cfg: Config):
    transcribe(np.zeros(16000, dtype=np.float32) + 0.02, cfg)


def _use_mlx(cfg: Config) -> bool:
    if cfg.asr_backend == "auto":
        return APPLE_SILICON
    return cfg.asr_backend == "mlx"


def _transcribe_mlx(audio, prompt: str | None, cfg: Config) -> str:
    import mlx_whisper

    result = mlx_whisper.transcribe(
        audio,
        path_or_hf_repo=cfg.asr_model,
        language=cfg.asr_language,
        initial_prompt=prompt,
        temperature=0.0,
        condition_on_previous_text=False,
    )
    return result["text"].strip()


def _transcribe_faster_whisper(audio, prompt: str | None, cfg: Config) -> str:
    segments, _ = _load_faster_whisper(cfg).transcribe(
        audio,
        language=cfg.asr_language,
        initial_prompt=prompt,
        temperature=0.0,
        condition_on_previous_text=False,
        beam_size=5,
    )
    return " ".join(s.text.strip() for s in segments).strip()


def _load_faster_whisper(cfg: Config):
    global _faster_whisper_model
    if _faster_whisper_model is None:
        import ctranslate2
        from faster_whisper import WhisperModel

        if ctranslate2.get_cuda_device_count() > 0:
            try:
                _faster_whisper_model = WhisperModel(cfg.faster_whisper_model, device="cuda", compute_type="float16")
                print(f"[asr] faster-whisper {cfg.faster_whisper_model} on cuda", flush=True)
                return _faster_whisper_model
            except (RuntimeError, ValueError) as e:  # GPU present but cuBLAS/cuDNN missing
                print(f"[asr] CUDA unavailable ({e}); falling back to CPU", flush=True)
        print(f"[asr] faster-whisper {cfg.faster_whisper_model} on cpu (int8)", flush=True)
        _faster_whisper_model = WhisperModel(cfg.faster_whisper_model, device="cpu", compute_type="int8")
    return _faster_whisper_model
