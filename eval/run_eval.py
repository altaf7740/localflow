"""Compare ASR configs on eval/clips against eval/references.tsv.

Usage: uv run python eval/run_eval.py [--no-cleanup] [--llm <ollama model>]
"""
import re
import sys
import time
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from localflow import asr, cleanup
from localflow.config import Config

ROOT = Path(__file__).parent


def normalize(text: str) -> list[str]:
    """Lowercase, drop punctuation, and fold common Roman-Hindi spelling variants."""
    text = re.sub(r"[^\w\s]", " ", text.lower())
    words = []
    for w in text.split():
        w = re.sub(r"(.)\1+", r"\1", w)  # meeting -> meting, karna/kaarna
        w = w.replace("ee", "i").replace("oo", "u")
        w = {"me": "mein", "mai": "main", "hume": "humein", "hamein": "humein",
             "hamen": "humein", "to": "toh", "bohot": "bahut", "bhot": "bahut"}.get(w, w)
        words.append(w)
    return words


def wer(ref: str, hyp: str) -> float:
    r, h = normalize(ref), normalize(hyp)
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(h) + 1):
            cur = min(d[j] + 1, d[j - 1] + 1, prev + (r[i - 1] != h[j - 1]))
            prev, d[j] = d[j], cur
    return d[len(h)] / max(len(r), 1)


def main():
    use_cleanup = "--no-cleanup" not in sys.argv
    refs = dict(line.split("\t", 1) for line in (ROOT / "references.tsv").read_text().splitlines() if line)
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
            raw = asr.transcribe(str(ROOT / "clips" / f"{clip}.wav"), cfg)
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
