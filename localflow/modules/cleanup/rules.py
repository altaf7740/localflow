"""Deterministic cleanup for Roman-Hinglish dictation: fillers and self-corrections, no model."""

import re

# only sounds that are never words; "matlab", "basically" or "nahi nahi" can carry meaning
FILLERS = re.compile(r"\b(?:u+m+|u+h+|h+m+)\b[,.]?\s*", re.IGNORECASE)

CUE = r"(?:nahi+n?|nahi+n?,? nahi+n?|no|sorry|I mean)"
DAY = (
    r"(?:aaj|kal|parso+n?|parsoo?m|narso|today|tomorrow|(?:mon|tues|wednes|thurs|fri|satur|sun)day"
    r"|so?mva+r|mangalva+r|budhva+r|guruva+r|shukrava+r|shaniva+r|ravivaa?r)"
)
NUM = r"(?:\d+(?:[.:]\d+)?|ek|do|teen|cha+r|pa+nch|chh?e|sa+t|a+th|nau|das|gyarah|barah|pandrah|bees|pachaas|sau)"
UNIT = r"(?:baje|hazaa?r|lakh|crore|minute|minutes|ghante|din|hafte|mahine|saal|kilo|rupaye|rupees|percent)"
# bare "do" is usually the verb ("bhej do"), so before a cue it only counts as a number with a unit
AMOUNT_BEFORE_CUE = rf"(?:(?!do\b){NUM}(?: {UNIT})?|do {UNIT})"
AMOUNT = rf"(?:{NUM}(?: {UNIT})?)"
# "kal nahi parso", "teen baje, sorry, chaar baje": both sides the same kind of word, so the
# cue can only be a correction. "Aaj nahi to kal" or "main nahi aaunga" never match.
SIMPLE_CORRECTION = re.compile(
    rf"\b(?:{DAY}|{AMOUNT_BEFORE_CUE})\s*,?\s+{CUE}\s*,?\s+({DAY}|{AMOUNT})\b", re.IGNORECASE
)
# a cue between the words being replaced (reparandum) and their replacement (repair). It needs a
# comma or a doubled "nahi", so a plain negation ("mujhe nahi pata") or a leading "Sorry," never
# matches, and "…, nahi to …" means "otherwise". "matlab" is left out: it usually explains, not corrects.
REPAIR_CUE = re.compile(
    r"\s*,\s*(?:nahi+n?(?:,? nahi+n?)?|no|sorry|I mean|actually|wait)(?!\s+toh?\b)\s*,?\s+"
    r"|\s+nahi+n?,? nahi+n?,?\s+",
    re.IGNORECASE,
)
SINGLE_WORD = re.compile(rf"^(?:{DAY}|{NUM})$", re.IGNORECASE)
SENTENCE = re.compile(r"[^.?!]+[.?!]*")
MAX_CHANGED = 2  # a repair may differ from what it replaces in at most this many words


def clean(text: str) -> str:
    text = SIMPLE_CORRECTION.sub(r"\1", FILLERS.sub("", text)).strip()
    text = "".join(_resolve_repair(s) for s in SENTENCE.findall(text))
    return text[:1].upper() + text[1:]


def _resolve_repair(sentence: str) -> str:
    """ "Rahul ko call karo, actually Amit ko call karo" -> "Amit ko call karo".

    The repair usually echoes what it replaces, so look for the same-length stretch before the cue
    that matches it word for word except for one or two words. If nothing lines up, keep the
    sentence exactly as spoken rather than guess.
    """
    cue = REPAIR_CUE.search(sentence)
    if not cue:
        return sentence
    lead = sentence[: len(sentence) - len(sentence.lstrip())]
    body = sentence.rstrip()
    end = body[len(body.rstrip(".?!")) :]
    trailing = sentence[len(body) :]
    before, repair = sentence[: cue.start()].split(), body[cue.end() : len(body) - len(end)].split()
    if not before or not repair:
        return sentence
    start = _align(before, repair)
    if start is None:
        return sentence
    return lead + " ".join(before[:start] + repair + before[start + len(repair) :]) + end + trailing


def _align(before: list[str], repair: list[str]) -> int | None:
    """Index in `before` where `repair` replaces an equally long stretch, or None if unsure."""
    norm = [_word(w) for w in before]
    rep = [_word(w) for w in repair]
    if len(rep) == 1:
        # nothing to line up with; only a day or number can safely replace the latest of its kind
        if not SINGLE_WORD.match(rep[0]):
            return None
        same_kind = [i for i, w in enumerate(norm) if SINGLE_WORD.match(w) and w != "do"]
        return same_kind[-1] if same_kind else None
    best, best_matches = None, 0
    for start in range(len(norm) - len(rep) + 1):
        matches = sum(a == b for a, b in zip(norm[start:], rep))
        changed = len(rep) - matches
        if 1 <= changed <= MAX_CHANGED and matches >= best_matches:  # ties go to the latest stretch
            best, best_matches = start, matches
    return best if best_matches else None


def _word(w: str) -> str:
    return re.sub(r"[^\w]", "", w.lower())
