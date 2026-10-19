"""Score pipelines on localflow/static/eval/clips against localflow/static/eval/references.tsv.

Always runs the configured pipeline (Config.load()), plus:
  --asr <mlx model dir>[:lang]  another Whisper model, no LLM cleanup (repeatable; lang defaults to "en")
  --llm <ollama model>          the configured ASR followed by LLM cleanup with that model
  --no-cleanup                  turn LLM cleanup off for the configured pipeline

Usage: make eval [ARGS="--asr <dir>:hi --llm qwen2.5:7b-instruct"]
   or: uv run python -m scripts.run_eval [same flags]
"""

import sys
import time
from dataclasses import replace

from localflow.core.config.settings import STATIC_DIR, Config
from localflow.modules.asr import services as asr
from localflow.modules.cleanup import services as cleanup
from localflow.modules.evaluation.metrics import wer

EVAL_DIR = STATIC_DIR / "eval"
RUNS = 3  # timed repeats per clip; the median is reported

try:
    import mlx.core as mx
except ImportError:  # faster-whisper platforms
    mx = None


def flag_values(name: str) -> list[str]:
    return [sys.argv[i + 1] for i, arg in enumerate(sys.argv[:-1]) if arg == name]


def pipelines() -> dict[str, Config]:
    base = Config.load()
    if "--no-cleanup" in sys.argv:
        base.cleanup_enabled = False
    configs = {"configured": base}
    for spec in flag_values("--asr"):
        path, _, lang = spec.partition(":")
        configs[spec] = replace(
            base, asr_backend="mlx", asr_model=path, asr_language=lang or "en", cleanup_enabled=False
        )
    for model in flag_values("--llm"):
        configs[f"configured + {model}"] = replace(base, cleanup_enabled=True, cleanup_model=model)
    return configs


def median(xs: list[float]) -> float:
    return sorted(xs)[len(xs) // 2]


def main():
    refs = dict(line.split("\t", 1) for line in (EVAL_DIR / "references.tsv").read_text().splitlines() if line)
    rows = []
    for name, cfg in pipelines().items():
        if mx:
            mx.reset_peak_memory()
        asr.warmup(cfg)
        cleanup.warmup(cfg)
        scores, t_asr, t_llm = [], [], []
        print(f"\n=== {name} ===")
        for clip, ref in refs.items():
            path = str(EVAL_DIR / "clips" / f"{clip}.wav")
            a, c = [], []
            for _ in range(RUNS):
                t0 = time.perf_counter()
                raw = asr.transcribe(path, cfg)
                t1 = time.perf_counter()
                out = cleanup.clean(raw, cfg)
                a.append(t1 - t0)
                c.append(time.perf_counter() - t1)
            t_asr.append(median(a))
            t_llm.append(median(c))
            scores.append(wer(ref, out))
            print(f"{clip} WER={scores[-1]:.2f}\n  raw: {raw}\n  out: {out}", flush=True)
        n = len(refs)
        mem = f"{mx.get_peak_memory() / 1e9:.2f}" if mx else "-"
        rows.append((name, sum(scores) / n, sum(t_asr) / n, sum(t_llm) / n, mem))
        if mx:
            mx.clear_cache()
    print("\n| pipeline | mean WER | asr s/clip | cleanup s/clip | total s/clip | peak MLX GB |")
    print("|---|---|---|---|---|---|")
    for name, w, a, c, mem in rows:
        print(f"| {name} | {w:.3f} | {a:.2f} | {c:.2f} | {a + c:.2f} | {mem} |")


if __name__ == "__main__":
    main()
