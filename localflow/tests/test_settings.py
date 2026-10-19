import json

from localflow.core.config import settings
from localflow.core.config.settings import Config


def test_defaults_when_no_config_file(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "CONFIG_PATH", tmp_path / "missing.json")
    cfg = Config.load()
    # Apex (MLX) writes Roman Hinglish itself; stock Whisper needs "hi" + the LLM transliteration
    assert cfg.asr_language == ("en" if settings.APPLE_SILICON else "hi")
    assert cfg.cleanup_enabled is not settings.APPLE_SILICON


def test_config_file_overrides_and_ignores_unknown_keys(tmp_path, monkeypatch):
    path = tmp_path / "localflow.json"
    path.write_text(json.dumps({"hotkey": "cmd_r", "vocabulary": ["Kubernetes"], "not_a_field": 1}))
    monkeypatch.setattr(settings, "CONFIG_PATH", path)
    cfg = Config.load()
    assert cfg.hotkey == "cmd_r"
    assert cfg.vocabulary == ["Kubernetes"]
    assert not hasattr(cfg, "not_a_field")


def test_models_dir_is_inside_static():
    assert settings.MODELS_DIR == settings.BASE_DIR / "static" / "models"


def test_save_persists_only_given_keys_and_keeps_existing(tmp_path, monkeypatch):
    path = tmp_path / "localflow.json"
    path.write_text(json.dumps({"vocabulary": ["Altaf"]}))
    monkeypatch.setattr(settings, "CONFIG_PATH", path)
    cfg = Config.load()
    cfg.input_device = "Altaf’s iPhone Microphone"
    cfg.save("input_device")
    saved = json.loads(path.read_text())
    assert saved == {"vocabulary": ["Altaf"], "input_device": "Altaf’s iPhone Microphone"}
    assert Config.load().input_device == "Altaf’s iPhone Microphone"
