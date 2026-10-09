import json

from src.core.config import settings
from src.core.config.settings import Config


def test_defaults_when_no_config_file(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "CONFIG_PATH", tmp_path / "missing.json")
    cfg = Config.load()
    assert cfg.asr_language == "hi"
    assert cfg.cleanup_enabled is True


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
