"""The coverage map: where the evidence sits, and where it runs out.

Computed in code from the kept rows, with no model call. For each theme it reads the
best evidence level found in each priority country, whether anything looks at a whole
system rather than one project, and whether any of it speaks to the young people the
team must reach. A blank cell is the finding: nothing in this scan covers that theme
in that country.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

from . import ladder

_SPLIT = re.compile(r"[;,/]| and ")
_NOT_FOUND = ("", "not found", "none", "n/a", "unclear", "not stated", "no")
_ALIAS = {"ivory coast": "cote divoire", "cote d ivoire": "cote divoire", "drc": "democratic republic of the congo"}


def _key(name: str) -> str:
    """A country name flattened for comparison: no accents, no punctuation, one space.
    Kept strict on purpose, since Niger and Nigeria are different countries and a loose
    match would quietly credit one with the other's evidence."""
    s = unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()
    s = re.sub(r"\s+", " ", s)
    return _ALIAS.get(s, s)


def _mentions(entry: str, country: str) -> bool:
    """Does this entry name that country? Whole words only, so "northern Ghana" counts
    and "Nigeria" never counts as Niger."""
    e, c = _key(entry), _key(country)
    return bool(e and c) and (e == c or re.search(rf"\b{re.escape(c)}\b", e) is not None)


def _countries(row: dict[str, Any]) -> list[str]:
    raw = row.get("countries", "")
    if isinstance(raw, list):
        parts = raw
    else:
        parts = _SPLIT.split(str(raw or ""))
    return [str(p).strip() for p in parts if str(p).strip()]


def _level(row: dict[str, Any]) -> int:
    return int((row.get("evidence_record") or {}).get("level", 1))


def _said(row: dict[str, Any], field: str) -> bool:
    v = str(row.get(field, "")).strip().lower()
    return bool(v) and v not in _NOT_FOUND and not v.startswith("not found")


def _system_level(row: dict[str, Any]) -> bool:
    v = str(row.get("level_of_view", "")).strip().lower()
    return any(w in v for w in ("system", "ecosystem", "sector", "national", "policy", "cross", "review"))


def grid(rows: list[dict[str, Any]], themes: list[dict[str, Any]],
         priority_countries: list[str], study_countries: list[str] | None = None) -> list[dict[str, Any]]:
    """One record per theme: the best evidence level in each priority country, and what
    the theme rests on. Levels are labels (E1 to E5), and an empty string means the scan
    found nothing there."""
    by_name = {r.get("name", ""): r for r in rows}
    out = []
    for t in themes:
        members = [by_name[m] for m in t.get("members") or [] if m in by_name]
        best: dict[str, int] = {}
        elsewhere = 0
        for r in members:
            names, lv = _countries(r), _level(r)
            hit = False
            for c in priority_countries:
                if any(_mentions(n, c) for n in names):
                    best[c] = max(best.get(c, 0), lv)
                    hit = True
            if not hit:
                elsewhere = max(elsewhere, lv)
        rec: dict[str, Any] = {
            "theme": t.get("name", ""), "posture": t.get("posture", ""), "options": len(members),
            "best": ladder.label(max([_level(r) for r in members] or [1])) if members else "",
        }
        for c in priority_countries:
            rec[c] = ladder.label(best[c]) if c in best else ""
        rec["Elsewhere"] = ladder.label(elsewhere) if elsewhere else ""
        rec["Countries with nothing"] = len([c for c in priority_countries if c not in best])
        study = [c for c in (study_countries or []) if c in priority_countries]
        if study:
            rec["Study countries covered"] = len([c for c in study if c in best])
            rec["Study countries with nothing"] = len([c for c in study if c not in best])
        rec["Looks at a whole system"] = sum(1 for r in members if _system_level(r))
        rec["Speaks to inclusion"] = sum(1 for r in members if _said(r, "inclusion"))
        rec["Names an open question"] = sum(1 for r in members if _said(r, "open_questions"))
        out.append(rec)
    return out


def _tail(study_countries: list[str] | None) -> list[str]:
    tail = ["Elsewhere", "Countries with nothing"]
    if study_countries:
        tail += ["Study countries covered", "Study countries with nothing"]
    return tail + ["Looks at a whole system", "Speaks to inclusion", "Names an open question"]


def columns(priority_countries: list[str], study_countries: list[str] | None = None) -> list[str]:
    return ["Theme", "Posture", "Options", "Best evidence"] + list(priority_countries) + _tail(study_countries)


def as_rows(records: list[dict[str, Any]], priority_countries: list[str],
            study_countries: list[str] | None = None) -> list[list[Any]]:
    keys = (["theme", "posture", "options", "best"] + list(priority_countries) + _tail(study_countries))
    return [[r.get(k, "") for k in keys] for r in records]
