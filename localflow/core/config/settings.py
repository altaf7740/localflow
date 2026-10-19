import json
import platform
import sys
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_PATH = Path.home() / ".localflow.json"
BASE_DIR = Path(__file__).resolve().parents[2]  # localflow/
STATIC_DIR = BASE_DIR / "static"
MODELS_DIR = STATIC_DIR / "models"
APPLE_SILICON = sys.platform == "darwin" and platform.machine() == "arm64"

HINGLISH_PROMPT = (
    "Haan bhai, main abhi ghar pe hoon. Tum log lunch ke baad call join kar lena, "
    "aur jo bhi issue hai woh mujhe message kar dena."
)


@dataclass
class Config:
    # "auto" = MLX on Apple Silicon, faster-whisper (CUDA or CPU) everywhere else
    asr_backend: str = "auto"
    # Oriserve Whisper-Hindi2Hinglish-Apex: a large-v3-turbo fine-tune that writes Roman Hinglish itself
    asr_model: str = str(MODELS_DIR / "whisper-hindi2hinglish-apex-mlx")
    # no CTranslate2 build of Apex exists yet, so faster-whisper stays on stock turbo + LLM cleanup
    faster_whisper_model: str = "large-v3-turbo"
    # Apex: "en" keeps its Roman output ("hi" breaks it). Stock turbo: "hi" recognises Hindi words
    # most accurately (in Devanagari) and the cleanup step transliterates to Roman.
    asr_language: str = "en" if APPLE_SILICON else "hi"
    asr_prompt: str = HINGLISH_PROMPT
    # Ollama LLM pass, only needed to transliterate stock Whisper's Devanagari. Filler and
    # self-correction rules always run.
    cleanup_enabled: bool = not APPLE_SILICON
    # MLX model fine-tuned only for Hinglish self-corrections and fillers (training/); rules alone
    # when the directory doesn't exist
    cleanup_model_path: str = str(MODELS_DIR / "hinglish-cleanup-mlx")
    cleanup_model: str = "qwen2.5:7b-instruct"
    ollama_url: str = "http://localhost:11434"
    # pynput key name held to dictate. Right Alt is AltGr on many Windows/Linux layouts.
    hotkey: str = "alt_l" if sys.platform == "darwin" else "ctrl_r"
    vocabulary: list[str] = field(default_factory=list)
    # input device name; empty = system default
    input_device: str = ""

    @classmethod
    def load(cls) -> "Config":
        if CONFIG_PATH.exists():
            data = json.loads(CONFIG_PATH.read_text())
            known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
            return cls(**known)
        return cls()

    def save(self, *keys: str):
        """Persist the given fields to ~/.localflow.json, keeping whatever else is in the file."""
        data = json.loads(CONFIG_PATH.read_text()) if CONFIG_PATH.exists() else {}
        for key in keys:
            data[key] = getattr(self, key)
        CONFIG_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False))
