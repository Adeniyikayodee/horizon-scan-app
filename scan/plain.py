"""Plain-language checks for a brief, run in code on every draft.

The brief is written for a reader of about 15. These checks hold it there and hold
it to ACET house style. Each returns plain notes the Synthesizer can act on in one
rewrite pass, and whatever survives the rewrite is listed for the analyst. The checks
never edit the text themselves, since changing words and keeping meaning are two
different jobs.
"""
from __future__ import annotations

import re
from typing import Any

# Antithesis: setting up one idea only to knock it down for another. Each pattern is
# matched per sentence, case-insensitive.
ANTITHESIS = [
    (r"\bnot\s+(?:just|only|merely|simply)\b[^.?!]*\bbut\b", "not just X but Y"),
    (r"\bnot\s+(?:only)\b[^.?!]*\bbut also\b", "not only X but also Y"),
    (r"\b(?:is|are|was|were|isn't|aren't|wasn't|weren't)\s+not\b[^.?!]{0,80}?,\s*(?:but|it is|it's|they are|rather)\b",
     "is not X, but Y"),
    (r"\b(?:isn't|aren't|wasn't|weren't|is not|are not)\s+about\b[^.?!]*\b(?:it's|it is|they're|they are|but)\s+about\b",
     "is not about X, it is about Y"),
    (r"\bless\s+(?:about\s+)?\w+[^.?!]{0,60}?\bmore\s+(?:about\s+)?\w+", "less X, more Y"),
    (r"\bmore than just\b", "more than just"),
    (r"\brather than\b", "rather than"),
    (r"\binstead of\b", "instead of"),
    (r"\bnot\b[^.?!,;]{1,60},\s*but\b", "not X, but Y"),
    (r"^\s*(?:it'?s|this is)\s+not\b[^.?!]*[.]\s*(?:it'?s|this is)\b", "It's not X. It's Y."),
]

_DASHES = "—–―‒−"
_ACRONYM = re.compile(r"\b[A-Z][A-Z0-9&]{1,}[a-z]?\b")
_KNOWN = {"E1", "E2", "E3", "E4", "E5", "US", "OK"}


def _prose(markdown: str) -> str:
    """The running prose of a markdown brief: headings, table rows, and link targets
    removed, list markers dropped, so the checks read sentences only."""
    out = []
    for line in (markdown or "").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("|"):
            continue
        s = re.sub(r"^\s*(?:[-*+]|\d+[.)])\s+", "", s)
        s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
        s = re.sub(r"https?://\S+", "", s)
        s = s.replace("**", "").replace("*", "")
        if s and s[-1] not in ".?!:":
            s += "."
        out.append(s)
    return " ".join(out)


def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.?!])\s+(?=[A-Z0-9\"'(])", text.strip())
    return [p for p in parts if re.search(r"[A-Za-z]", p)]


def words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z'-]*|\d[\d,.]*", text)


def syllables(word: str) -> int:
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return 1
    if len(w) <= 3:
        return 1
    w = re.sub(r"(?:[^laeiouy]es|ed|[^laeiouy]e)$", "", w)
    w = re.sub(r"^y", "", w)
    return max(1, len(re.findall(r"[aeiouy]{1,2}", w)))


def reading_grade(text: str) -> float:
    """Flesch-Kincaid grade level of the prose."""
    sents = sentences(text)
    ws = [w for w in words(text) if re.match(r"[A-Za-z]", w)]
    if not sents or not ws:
        return 0.0
    syl = sum(syllables(w) for w in ws)
    return round(0.39 * (len(ws) / len(sents)) + 11.8 * (syl / len(ws)) - 15.59, 1)


def avg_sentence_length(text: str) -> float:
    sents = sentences(text)
    return round(len(words(text)) / len(sents), 1) if sents else 0.0


def antithesis_hits(text: str) -> list[str]:
    hits = []
    for sent in sentences(text):
        for pat, name in ANTITHESIS:
            if re.search(pat, sent, re.I):
                hits.append(f'{name}: "{sent.strip()[:140]}"')
                break
    return hits


def acronym_hits(text: str) -> list[str]:
    """An acronym must be spelled out at its first use, as 'Full Name (ACR)'."""
    hits, seen = [], set()
    for m in _ACRONYM.finditer(text):
        a = m.group(0)
        if a in seen or a in _KNOWN or a.isdigit():
            continue
        seen.add(a)
        before = text[max(0, m.start() - 1):m.start()]
        if before != "(":
            hits.append(f"acronym not spelled out at first use: {a}")
    return hits


def house_hits(text: str) -> list[str]:
    hits = []
    for m in re.finditer(r"(?<![\w.,$£€%-])([0-9])(?![\w.,%:/-])", text):
        ctx = text[max(0, m.start() - 12):m.end() + 12]
        if re.search(r"\bE[1-5]\b|page|section|table|figure|step|level", ctx, re.I):
            continue
        hits.append(f'spell out numbers zero to nine: "{ctx.strip()}"')
    if "%" in text:
        hits.append('use "percent" in prose, not %')
    if any(d in text for d in _DASHES):
        hits.append("dash: use commas or rewrite")
    return hits


def check(markdown: str, cfg: dict[str, Any]) -> list[str]:
    """Every plain-language and house-style issue in a brief, as notes.

    cfg: {"max_grade": 9, "max_sentence_words": 20, "target_words": 2700,
          "word_tolerance": 0.10}"""
    text = _prose(markdown)
    issues: list[str] = []
    grade = reading_grade(text)
    if grade > float(cfg.get("max_grade", 9)):
        issues.append(f"reading grade {grade}, above {cfg.get('max_grade', 9)}: use shorter words and sentences")
    avg = avg_sentence_length(text)
    if avg > float(cfg.get("max_sentence_words", 20)):
        issues.append(f"average sentence {avg} words, above {cfg.get('max_sentence_words', 20)}")
    target = int(cfg.get("target_words", 0) or 0)
    if target:
        n = len(re.findall(r"\S+", markdown or ""))
        tol = float(cfg.get("word_tolerance", 0.10))
        if not (target * (1 - tol) <= n <= target * (1 + tol)):
            issues.append(f"{n:,} words, the target is {target:,} within {int(tol * 100)} percent")
    issues += antithesis_hits(text)
    issues += acronym_hits(text)
    issues += house_hits(text)
    return issues
