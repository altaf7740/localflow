from localflow.core.config.settings import Config
from localflow.modules.cleanup import services
from localflow.modules.cleanup.prompt import TRANSLITERATE_PROMPT


def test_disabled_cleanup_returns_raw_text():
    cfg = Config(cleanup_enabled=False)
    assert services.clean("कल मिलते हैं", cfg) == "कल मिलते हैं"


def test_falls_back_to_raw_text_when_ollama_is_down():
    cfg = Config(ollama_url="http://localhost:1")
    assert services.clean("kal milte hain", cfg) == "kal milte hain"


def test_leftover_devanagari_triggers_transliteration_pass(monkeypatch):
    calls = []

    def fake_chat(messages, cfg):
        calls.append(messages[0]["content"])
        return "Main सोच रहा था" if len(calls) == 1 else "Main soch raha tha"

    monkeypatch.setattr(services, "_chat", fake_chat)
    assert services.clean("मैं सोच रहा था", Config()) == "Main soch raha tha"
    assert calls[1] == TRANSLITERATE_PROMPT


def test_roman_output_skips_transliteration_pass(monkeypatch):
    calls = []
    monkeypatch.setattr(services, "_chat", lambda messages, cfg: calls.append(1) or "Kal milte hain.")
    assert services.clean("kal milte hain", Config()) == "Kal milte hain."
    assert len(calls) == 1
