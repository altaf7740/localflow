from dataclasses import dataclass, field
from pathlib import Path
import json

CONFIG_PATH = Path.home() / ".localflow.json"
MODELS_DIR = Path(__file__).resolve().parent.parent / "models"

HINGLISH_PROMPT = (
    "Haan bhai, main abhi ghar pe hoon. Tum log lunch ke baad call join kar lena, "
    "aur jo bhi issue hai woh mujhe message kar dena."
)


@dataclass
class Config:
    asr_model: str = str(MODELS_DIR / "whisper-large-v3-turbo-mlx")
    # "hi" recognises Hindi words most accurately (in Devanagari); the cleanup
    # step transliterates to Roman. "en" writes Roman directly but misspells.
    asr_language: str = "hi"
    asr_prompt: str = HINGLISH_PROMPT
    cleanup_enabled: bool = True
    cleanup_model: str = "qwen2.5:7b-instruct"
    ollama_url: str = "http://localhost:11434"
    # pynput key name held to dictate
    hotkey: str = "alt_r"
    vocabulary: list[str] = field(default_factory=list)

    @classmethod
    def load(cls) -> "Config":
        if CONFIG_PATH.exists():
            data = json.loads(CONFIG_PATH.read_text())
            known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
            return cls(**known)
        return cls()
