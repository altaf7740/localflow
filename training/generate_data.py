"""Build (messy dictation -> clean text) pairs for the cleanup model from clean Hinglish sentences.

Every clean corpus sentence is the target. Its input is the same sentence as someone might say it:
a word said wrong then corrected ("Lisa nahi Mary ko bolo"), a stutter, fillers, or, for about a
third of examples, left as is so the model learns to keep negations and discourse words intact.

Usage: uv run python -m training.generate_data [--n 60000] [--seed 0]
Writes training/data/{train,valid}.jsonl as {"prompt": messy, "completion": clean}.
"""

import argparse
import json
import random
import re
from pathlib import Path

DATA = Path(__file__).parent / "data"
CORPUS = DATA / "hinglish_upload_v1.json"  # findnitai/english-to-hinglish, Apache-2.0

DAYS = [
    ["aaj", "kal", "parso"],
    ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
    ["somvar", "mangalvar", "budhvar", "guruvar", "shukravar", "shanivar", "ravivar"],
]
NUMBER_WORDS = ["ek", "teen", "chaar", "paanch", "chhe", "saat", "aath", "nau", "das", "bees", "pachaas", "sau"]
NOUNS = [
    ["chai", "coffee", "lassi", "juice", "paani"],
    ["ghar", "office", "market", "gym", "school", "college", "hospital"],
    ["email", "message", "call", "text", "mail"],
    ["meeting", "call", "presentation", "interview", "class"],
    ["mummy", "papa", "bhaiya", "didi", "dost"],
    ["alarm", "reminder", "timer"],
    ["song", "gaana", "video", "podcast", "playlist"],
    ["spotify", "youtube", "whatsapp", "gmail", "slack"],
]
NAMES = (
    "Rahul Amit Priya Neha Rohan Anjali Vikram Pooja Arjun Sneha Karan Riya Aditya Kavya Ishaan Meera "
    "Sahil Tanvi Nikhil Simran Lisa Mary John David Sarah Michael Emma James Anna Mark"
).split()
# cue said between the wrong word and the right one; weights roughly follow how people talk
# ("matlab" is left out: "kal tak, matlab parso tak" explains rather than corrects)
CUES = ["nahi", "nahin", "nahi nahi", "sorry", "I mean", "actually", "wait", "no"]
CUE_WEIGHTS = [6, 3, 3, 3, 2, 2, 1, 1]
FILLERS = ["umm", "uh", "hmm", "you know", "basically"]
# capitalised but not names: words that start a clause or acronyms people say as words
SKIP_CAPITALISED = {"main", "mujhe", "kya", "the", "and", "for", "you", "please", "ok", "okay"}
REDUPLICATED = ["jaldi jaldi", "dheere dheere", "kya kya", "kabhi kabhi", "alag alag", "thoda thoda", "baar baar"]


def load_sentences() -> list[str]:
    out = []
    for line in CORPUS.read_text().splitlines():
        s = json.loads(line)["translation"]["hi_ng"]
        s = re.sub(r"\s+([,.?!’'])", r"\1", " ".join(s.split())).replace("’ ", "’")
        if 3 <= len(s.split()) <= 25 and not re.search(r"[ऀ-ॿ]|http|[@#()]|__", s):
            out.append(s)
    return out


def proper_nouns(sentences: list[str], top: int = 3000) -> list[str]:
    """Capitalised words from the corpus (names, places, apps), to swap with each other."""
    counts = {}
    for s in sentences:
        for w in s.split()[1:]:
            w = re.sub(r"[^\w]", "", w)
            if w[:1].isupper() and w.isalpha() and len(w) > 2 and w.lower() not in SKIP_CAPITALISED:
                counts[w] = counts.get(w, 0) + 1
    return sorted(counts, key=counts.get, reverse=True)[:top]


def find_slots(words: list[str], nouns: list[str]) -> list[tuple[int, list[str]]]:
    """Words that could have been said wrong, each with the alternatives a speaker might have said."""
    slots = []
    for i, w in enumerate(words):
        core = re.sub(r"[^\w]", "", w)
        low = core.lower()
        group = next((g for g in DAYS + NOUNS if low in g), None)
        if group:
            slots.append((i, [x for x in group if x != low]))
        elif core.isdigit():
            n = int(core)
            slots.append((i, [str(x) for x in {n + 1, n + 2, max(n - 1, 0), n * 2, n + 10} if x != n]))
        elif low in NUMBER_WORDS:
            slots.append((i, [x for x in NUMBER_WORDS if x != low]))
        elif i > 0 and core[:1].isupper() and core.isalpha() and len(core) > 2:
            slots.append((i, [x for x in NAMES + nouns if x != core]))
    return slots


def _swap(word: str, alt: str) -> str:
    """Put `alt` in place of `word`, keeping its capitalisation and trailing punctuation."""
    core = re.sub(r"[^\w]+$", "", word)
    alt = alt.capitalize() if core[:1].isupper() else alt
    return alt + word[len(core) :]


def _cue(rng: random.Random) -> str:
    cue = rng.choices(CUES, CUE_WEIGHTS)[0]
    style = rng.random()
    if style < 0.5:
        return f", {cue}, "
    if style < 0.8:
        return f" {cue} "
    return f", {cue} "


def correction(words: list[str], nouns: list[str], rng: random.Random) -> str | None:
    """The speaker says a wrong word first, then the right one, in one of four shapes."""
    slots = find_slots(words, nouns)
    if not slots:
        return None
    i, alts = rng.choice(slots)
    wrong = _swap(words[i], rng.choice(alts))
    right = words[i]
    strip = lambda w: re.sub(r"[,.?!]+$", "", w)  # noqa: E731
    shape = rng.random()
    if shape < 0.35:  # inline: "Lisa nahi Mary ko bolo"
        out = words[:i] + [strip(wrong) + _cue(rng).rstrip() + " " + right] + words[i + 1 :]
        return " ".join(out).replace(" ,", ",")
    if shape < 0.6:  # short repair after the clause: "Monday ko meet karte hain, sorry, Wednesday ko"
        tail = words[i + 1 : i + 1 + rng.randint(0, 2)]
        said = " ".join(words[:i] + [wrong] + words[i + 1 :]).rstrip(".?!")
        repair = " ".join([strip(right)] + [strip(w) for w in tail])
        return said + _cue(rng) + repair + _end(words)
    if shape < 0.85:  # repeat from a few words back: "Rahul ko call karo, actually Amit ko call karo"
        start = rng.randint(max(0, i - 3), i)
        said = " ".join(words[: i + 1 + rng.randint(0, 3)][:i] + [wrong] + words[i + 1 : i + 1 + rng.randint(0, 3)])
        return strip(said) + _cue(rng) + " ".join(words[start:])
    # abandoned restart: "Rahul ko bolo, nahi, Amit ko mail kar do"
    filler_tail = rng.sample(["bolo", "karo", "bhejo", "dekho", "hai", "tha", "ko", "se"], rng.randint(0, 2))
    said = " ".join(words[:i] + [strip(wrong)] + filler_tail)
    return said + _cue(rng) + " ".join(words)


def _end(words: list[str]) -> str:
    m = re.search(r"[.?!]+$", words[-1])
    return m.group(0) if m else ""


def stutter(words: list[str], rng: random.Random) -> str | None:
    i = rng.randrange(len(words))
    if re.search(r"[,.?!]$", words[i]):
        return None
    n = rng.choice([1, 1, 2])
    return " ".join(words[: i + n] + words[i : i + n] + words[i + n :])


def fillers(words: list[str], rng: random.Random) -> str:
    out = list(words)
    for _ in range(rng.choice([1, 1, 2])):
        f = rng.choice(FILLERS)
        pos = rng.randrange(len(out) + 1)
        out.insert(pos, f + ("," if rng.random() < 0.5 else ""))
    return " ".join(out)


def keep_example(sentence: str, other: str, rng: random.Random) -> str:
    """Text that looks like it has a cue but must come out unchanged."""
    kind = rng.random()
    s = sentence.rstrip(".?!")
    o = other[:1].lower() + other[1:]
    if kind < 0.2:
        return f"{s}, nahi to {o}"
    if kind < 0.35:
        return f"Sorry, {sentence[:1].lower() + sentence[1:]}"
    if kind < 0.5:
        return f"Actually {sentence[:1].lower() + sentence[1:]}"
    if kind < 0.65:
        return f"{s}, actually {o}"
    if kind < 0.8:
        words = sentence.split()
        i = rng.randrange(len(words) + 1)
        return " ".join(words[:i] + [rng.choice(REDUPLICATED)] + words[i:])
    return sentence


def make_pair(sentence: str, other: str, nouns: list[str], rng: random.Random) -> dict | None:
    words = sentence.split()
    kind = rng.random()
    if kind < 0.35:
        target = keep_example(sentence, other, rng)
        return {"prompt": target, "completion": target}
    if kind < 0.75:
        messy = correction(words, nouns, rng)
    elif kind < 0.87:
        messy = stutter(words, rng)
    else:
        messy = fillers(words, rng)
    if messy and rng.random() < 0.15:  # some examples carry two kinds of mess
        messy = fillers(messy.split(), rng)
    if not messy or messy == sentence:
        return None
    return {"prompt": messy, "completion": sentence}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=60000)
    ap.add_argument("--valid", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    sentences = load_sentences()
    nouns = proper_nouns(sentences)
    rng.shuffle(sentences)
    # valid uses sentences the training set never sees
    split = {"valid": sentences[: len(sentences) // 10], "train": sentences[len(sentences) // 10 :]}
    for name, pool, n in (("train", split["train"], args.n), ("valid", split["valid"], args.valid)):
        pairs = []
        while len(pairs) < n:
            pair = make_pair(rng.choice(pool), rng.choice(pool), nouns, rng)
            if pair:
                pairs.append(pair)
        with open(DATA / f"{name}.jsonl", "w") as f:
            for p in pairs:
                f.write(json.dumps(p, ensure_ascii=False) + "\n")
        print(f"{name}: {len(pairs)} pairs from {len(pool)} sentences")


if __name__ == "__main__":
    main()
