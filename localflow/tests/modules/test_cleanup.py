import pytest

from localflow.core.config.settings import Config
from localflow.modules.cleanup import model, rules, services
from localflow.modules.cleanup.prompt import TRANSLITERATE_PROMPT


def _no_llm(*args, **kwargs):
    raise AssertionError("LLM should not be called")


def test_strips_only_non_word_fillers():
    assert rules.clean("umm, kal hum milte hain, uh matlab") == "Kal hum milte hain, matlab"
    assert rules.clean("Take him to the ER. Hmm.") == "Take him to the ER."


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Kal nahin parson office aaunga.", "Parson office aaunga."),
        ("kal nahi, parso milte hain", "Parso milte hain"),
        ("Monday nahi Tuesday ko meeting hai.", "Tuesday ko meeting hai."),
        ("Do kilo nahi nahi teen kilo chahiye.", "Teen kilo chahiye."),
        ("Rahul ko call karo, actually Amit ko call karo.", "Amit ko call karo."),
        ("Main kal Delhi ja raha hoon, wait, Mumbai ja raha hoon.", "Main kal Mumbai ja raha hoon."),
        ("Hum log Monday ko meet karte hain, sorry, Wednesday ko.", "Hum log Wednesday ko meet karte hain."),
        ("Usko paanch hazaar bhej do, I mean das hazaar.", "Usko das hazaar bhej do."),
        ("Main ghar pe hoon, actually office mein hoon.", "Main office mein hoon."),
        ("Meeting teen baje hai, nahi nahi, chaar.", "Meeting chaar baje hai."),
        ("Kal meeting hai. Rahul ko call karo, actually Amit ko call karo.", "Kal meeting hai. Amit ko call karo."),
    ],
)
def test_self_corrections_keep_the_final_version(text, expected):
    assert rules.clean(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "Main kal nahi aaunga.",
        "Mujhe nahi pata ki deadline kab hai.",
        "Aaj nahi to kal kar lenge.",
        "Sorry, main late ho gaya.",
        "Nahi nahi, main theek hoon.",
        "Ye kaam do din mein nahi hoga.",
        "Main ja raha hoon, nahi to wo naraz hoga.",
        "Kya tum aa rahe ho, nahi aa rahe?",
        "Main ghar ja raha hoon, actually bahut thak gaya hoon.",
        "Wo aa gaya, actually main bhi aa gaya.",
        "Ye kaam kal tak hoga, matlab parso tak.",
        # unresolvable: nothing lines up, so it stays as spoken rather than being guessed at
        "Rahul ko bolo, nahi, Amit ko mail kar do.",
        "Usko do nahi teen copies chahiye.",
    ],
)
def test_everything_else_is_left_as_spoken(text):
    assert rules.clean(text) == text


def test_roman_text_never_calls_the_llm(monkeypatch):
    monkeypatch.setattr(services, "_chat", _no_llm)
    cfg = Config(cleanup_enabled=True)
    assert services.clean("Rahul ko call karo, actually Amit ko call karo.", cfg) == "Amit ko call karo."


def test_disabled_cleanup_still_applies_rules_but_keeps_devanagari():
    cfg = Config(cleanup_enabled=False)
    assert services.clean("umm कल मिलते हैं", cfg) == "कल मिलते हैं"


def test_falls_back_to_raw_text_when_ollama_is_down():
    cfg = Config(cleanup_enabled=True, ollama_url="http://localhost:1")
    assert services.clean("कल मिलते हैं", cfg) == "कल मिलते हैं"


def test_leftover_devanagari_triggers_transliteration_pass(monkeypatch):
    calls = []

    def fake_chat(messages, cfg):
        calls.append(messages[0]["content"])
        return "Main सोच रहा था" if len(calls) == 1 else "Main soch raha tha"

    monkeypatch.setattr(services, "_chat", fake_chat)
    assert services.clean("मैं सोच रहा था", Config(cleanup_enabled=True)) == "Main soch raha tha"
    assert calls[1] == TRANSLITERATE_PROMPT


def test_roman_llm_output_skips_transliteration_pass(monkeypatch):
    calls = []
    monkeypatch.setattr(services, "_chat", lambda messages, cfg: calls.append(1) or "Kal milte hain.")
    assert services.clean("कल मिलते हैं", Config(cleanup_enabled=True)) == "Kal milte hain."
    assert len(calls) == 1


def test_warmup_loads_the_model_only_when_cleanup_is_on(monkeypatch):
    calls = []
    monkeypatch.setattr(services, "_chat", lambda messages, cfg: calls.append(cfg.cleanup_model) or "")
    services.warmup(Config(cleanup_enabled=False))
    services.warmup(Config(cleanup_enabled=True, cleanup_model="m"))
    assert calls == ["m"]


def test_model_output_is_used_when_available(monkeypatch):
    monkeypatch.setattr(model, "available", lambda cfg: True)
    monkeypatch.setattr(model, "clean", lambda text, cfg: "amit ko call karo.")
    assert services.clean("Rahul ko bolo, nahi, Amit ko call karo.", Config()) == "Amit ko call karo."


def test_rules_take_over_when_model_declines(monkeypatch):
    monkeypatch.setattr(model, "available", lambda cfg: True)
    monkeypatch.setattr(model, "clean", lambda text, cfg: None)
    assert services.clean("Kal nahin parson office aaunga.", Config()) == "Parson office aaunga."


def test_model_is_skipped_for_fluent_text_and_devanagari(monkeypatch):
    monkeypatch.setattr(model, "_load", _no_llm)
    assert model.clean("Kal ki meeting mein timeline discuss karna hai.", Config()) is None
    monkeypatch.setattr(model, "available", _no_llm)
    services.clean("कल मिलते हैं", Config(cleanup_enabled=False))


@pytest.mark.parametrize(
    "before, after, added",
    [
        ("Rahul ko call karo, actually Amit ko call karo.", "Amit ko call karo.", False),
        ("Hum Monday ko milte hain, sorry, Wednesday ko.", "Hum Wednesday ko milte hain.", False),
        ("Rahul ko call karo, actually Amit ko call karo.", "Sure, main Amit ko call karta hoon.", True),
    ],
)
def test_guard_rejects_words_that_were_never_said(before, after, added):
    assert model.adds_words(before, after) is added


def test_llm_cleanup_is_off_by_default_and_on_demand_for_roman_text(monkeypatch):
    monkeypatch.setattr(services, "_chat", lambda messages, cfg: "Kal milte hain.")
    assert services.clean("umm kal milte hain", Config(cleanup_enabled=False, cleanup_model_path="")) == "Kal milte hain"
    on = Config(cleanup_enabled=False, cleanup_model_path="", llm_cleanup=True)
    assert services.clean("umm kal milte hain", on) == "Kal milte hain."


def test_llm_cleanup_output_with_an_invented_word_is_dropped(monkeypatch):
    monkeypatch.setattr(services, "_chat", lambda messages, cfg: "Kal zaroor milte hain.")
    on = Config(cleanup_enabled=False, cleanup_model_path="", llm_cleanup=True)
    assert services.clean("kal milte hain", on) == "Kal milte hain"


def test_llm_cleanup_falls_back_when_ollama_is_down(monkeypatch):
    monkeypatch.setattr(services, "_chat", lambda messages, cfg: "")
    on = Config(cleanup_enabled=False, cleanup_model_path="", llm_cleanup=True)
    assert services.clean("kal milte hain", on) == "Kal milte hain"
