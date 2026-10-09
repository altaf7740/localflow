"""Compare ASR configs on src/static/eval/clips against src/static/eval/references.tsv.

Usage: make eval [ARGS="--no-cleanup --llm <ollama model>"]
   or: uv run python -m scripts.run_eval [--no-cleanup] [--llm <ollama model>]
"""

import sys
import time
from dataclasses import replace

from src.core.config.settings import STATIC_DIR, Config
from src.modules.asr import services as asr
from src.modules.cleanup import services as cleanup
from src.modules.evaluation.metrics import wer

EVAL_DIR = STATIC_DIR / "eval"


def main():
    use_cleanup = "--no-cleanup" not in sys.argv
    refs = dict(line.split("\t", 1) for line in (EVAL_DIR / "references.tsv").read_text().splitlines() if line)
    base = Config.load()
    if "--llm" in sys.argv:
        base.cleanup_model = sys.argv[sys.argv.index("--llm") + 1]
    configs = {
        "turbo/en+prompt": replace(base, asr_language="en"),
        "turbo/hi": replace(base, asr_language="hi"),
    }
    for name, cfg in configs.items():
        cfg.cleanup_enabled = use_cleanup
        asr.warmup(cfg)
        total, t_asr, t_llm = 0.0, 0.0, 0.0
        print(f"\n=== {name} ===")
        for clip, ref in refs.items():
            t0 = time.time()
            raw = asr.transcribe(str(EVAL_DIR / "clips" / f"{clip}.wav"), cfg)
            t1 = time.time()
            out = cleanup.clean(raw, cfg)
            t2 = time.time()
            t_asr, t_llm = t_asr + t1 - t0, t_llm + t2 - t1
            score = wer(ref, out)
            total += score
            print(f"{clip} WER={score:.2f}\n  raw: {raw}\n  out: {out}")
        n = len(refs)
        print(f"-> mean WER {total / n:.3f} | asr {t_asr / n:.2f}s | llm {t_llm / n:.2f}s per clip")


if __name__ == "__main__":
    main()
