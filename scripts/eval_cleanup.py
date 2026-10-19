"""Score Roman-Hinglish cleanup: rules alone vs the fine-tuned model (with rules as fallback).

Cases come from localflow/static/eval/cleanup.tsv (said<TAB>expected): self-corrections that must
resolve and negations or discourse words that must be left alone. --valid also scores the held-out
synthetic pairs in training/data/valid.jsonl.

Usage: make eval-cleanup [ARGS="--model <mlx model dir> --valid"]
   or: uv run python -m scripts.eval_cleanup [same flags]
"""

import json
import sys
import time
from dataclasses import replace
from pathlib import Path

from localflow.core.config.settings import STATIC_DIR, Config
from localflow.modules.cleanup import model, services
from localflow.modules.evaluation.metrics import normalize

CASES = STATIC_DIR / "eval" / "cleanup.tsv"
VALID = Path(__file__).parents[1] / "training" / "data" / "valid.jsonl"


def score(name: str, cfg: Config, cases: list[tuple[str, str]], show: bool):
    services.warmup(cfg)
    ok, times, wrong_changes = 0, [], 0
    for said, expected in cases:
        t0 = time.perf_counter()
        out = services.clean(said, cfg)
        times.append(time.perf_counter() - t0)
        hit = normalize(out) == normalize(expected)
        ok += hit
        # worst kind of miss: the text needed no change but was changed anyway
        wrong_changes += not hit and normalize(said) == normalize(expected)
        if show and not hit:
            print(f"  ✗ {said}\n      -> {out}\n      expected {expected}")
    times.sort()
    print(
        f"{name}: {ok}/{len(cases)} correct ({ok / len(cases):.1%}), {wrong_changes} changed when they "
        f"shouldn't be | p50 {times[len(times) // 2] * 1000:.0f} ms, p90 {times[int(len(times) * 0.9)] * 1000:.0f} ms"
    )


def main():
    model_path = sys.argv[sys.argv.index("--model") + 1] if "--model" in sys.argv else Config().cleanup_model_path
    rules_only = Config(cleanup_enabled=False, cleanup_model_path="")
    with_model = replace(rules_only, cleanup_model_path=model_path)
    sets = {"cleanup.tsv": [tuple(line.split("\t")) for line in CASES.read_text().splitlines() if line]}
    if "--valid" in sys.argv:
        sets["valid.jsonl"] = [(r["prompt"], r["completion"]) for r in map(json.loads, VALID.open())]
    for set_name, cases in sets.items():
        print(f"\n=== {set_name} ({len(cases)} cases) ===")
        show = len(cases) < 100
        score("rules", rules_only, cases, show)
        if model.available(with_model):
            score(f"model ({Path(model_path).name}) + rules", with_model, cases, show)
        else:
            print(f"no model at {model_path}")


if __name__ == "__main__":
    main()
