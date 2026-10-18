import re

SPELLING_VARIANTS = {
    "me": "mein",
    "mai": "main",
    "hume": "humein",
    "hamein": "humein",
    "hamen": "humein",
    "to": "toh",
    "bohot": "bahut",
    "bhot": "bahut",
}


def normalize(text: str) -> list[str]:
    """Lowercase, drop punctuation, and fold common Roman-Hindi spelling variants."""
    text = re.sub(r"[^\w\s]", " ", text.lower())
    words = []
    for w in text.split():
        w = re.sub(r"(.)\1+", r"\1", w)  # meeting -> meting, karna/kaarna
        w = w.replace("ee", "i").replace("oo", "u")
        words.append(SPELLING_VARIANTS.get(w, w))
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
