"""The funder scan: who funds this work, and how well each funder fits the program.

The model reads each funder's own strategy and program pages and records what they
say, with the sentence that says it. The code keeps only what it can find in the
cited page, strips any personal contact detail, and ranks fit. Nothing here is a
judgment the model makes on its own.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
from datetime import datetime
from typing import Any

from . import config, io_xlsx, sources

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_CAND = re.compile(r"[+(]?\d[\d\s().-]{7,}\d")
_YEAR_RANGE = re.compile(r"^(19|20)\d{2}\s*[-/]\s*(19|20)\d{2}$")
_YEAR = re.compile(r"(?:19|20)\d{2}")

NOT_FOUND = "not found"


def _strip_phone(m: re.Match) -> str:
    s = m.group(0)
    digits = sum(ch.isdigit() for ch in s)
    if _YEAR_RANGE.match(s.strip()):
        return s
    return "" if s[0] in "+(" or 10 <= digits <= 13 else s


def _clean(v: Any) -> Any:
    """No personal contact details in anything the funder scan keeps."""
    if isinstance(v, str):
        return _PHONE_CAND.sub(_strip_phone, _EMAIL.sub("", v)).strip()
    if isinstance(v, list):
        return [_clean(x) for x in v]
    if isinstance(v, dict):
        return {k: _clean(x) for k, x in v.items()}
    return v


def build_list(roster: list[dict[str, str]], rows: list[dict[str, Any]], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """The funders to scan: every roster organization of a funder type, then funders
    named on options that may be adopted or adapted and are not on the roster, most
    often named first, capped."""
    types = [t.lower() for t in cfg.get("roster_types") or []]
    lead = set(cfg.get("from_postures") or ["adopt", "adapt"])
    out: list[dict[str, Any]] = []
    sigs: list[dict] = []

    def known(name: str) -> bool:
        sig = io_xlsx._org_sig(name)
        return any(io_xlsx._same_org(sig, s) for s in sigs)

    for o in roster:
        if any(t in (o.get("type") or "").lower() for t in types) and not known(o["name"]):
            out.append({"name": o["name"], "type": o.get("type", ""), "source": "roster"})
            sigs.append(io_xlsx._org_sig(o["name"]))

    counts: dict[str, int] = {}
    for r in rows:
        rec = r.get("evidence_record") or {}
        if rec.get("posture_allowed") not in lead:
            continue
        names = list(rec.get("funders") or [])
        names += [n.strip() for n in re.split(r"[;,]", str(r.get("funders", ""))) if n.strip()]
        for n in dict.fromkeys(names):
            counts[n] = counts.get(n, 0) + 1
    added = 0
    for name, c in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        if added >= int(cfg.get("max_additions", 15)):
            break
        if known(name):
            continue
        out.append({"name": name, "type": "", "source": f"named on {c} option(s)"})
        sigs.append(io_xlsx._org_sig(name))
        added += 1
    return out


async def ground(record: dict[str, Any]) -> dict[str, Any]:
    """Keep a field only when its quote is found in its page. A field that fails is
    set to not found, and the reason is kept for the reviewer."""
    rec = _clean(dict(record))
    rec["dropped_fields"] = []
    for f in ("strategy", "themes", "countries", "instruments", "size", "eligibility"):
        item = rec.get(f) or {}
        quote, url = item.get("quote", ""), item.get("url", "")
        ok = await asyncio.to_thread(sources.quote_exact, url, quote) if quote and url else None
        item["grounded"] = ok
        if ok is not True:
            if item.get("value") not in (None, "", [], NOT_FOUND):
                rec["dropped_fields"].append(f"{f}: quote not found in the cited page")
            item["value"] = [] if isinstance(item.get("value"), list) else NOT_FOUND
        rec[f] = item
    calls = []
    for c in rec.get("calls") or []:
        if c.get("url") and not (not config.DRY_RUN and await asyncio.to_thread(sources.link_dead, c["url"])):
            calls.append(c)
    rec["calls"] = calls
    return rec


def _norm_place(s: str) -> str:
    return re.sub(r"[^a-z ]", "", (s or "").lower().replace("côte", "cote").replace("ô", "o")).strip()


def fit(rec: dict[str, Any], cfg: dict[str, Any], now_year: int | None = None) -> dict[str, Any]:
    """Rank fit to the program, in code, from grounded fields only.

      themes      2 points per matching program theme, up to 10
      countries   1 point per priority country named, up to 3, or 1 for Africa-wide
      eligibility 3 when an African think tank is an eligible partner, 1 when unclear
      active      2 when the strategy period runs to this year or later
    """
    now_year = now_year or datetime.now().year
    seed = {t.lower() for t in cfg.get("theme_names") or []}
    themes = [t for t in (rec.get("themes") or {}).get("value") or [] if t.lower() in seed]
    t_pts = min(10, 2 * len(set(t.lower() for t in themes)))

    priority = {_norm_place(c) for c in cfg.get("priority_countries") or []}
    named = {_norm_place(c) for c in (rec.get("countries") or {}).get("value") or []}
    hits = priority & named
    c_pts = min(3, len(hits)) if hits else (1 if any("africa" in n for n in named) else 0)

    elig = str((rec.get("eligibility") or {}).get("value", "")).lower()
    e_pts = 3 if elig == "yes" else 1 if elig == "unclear" else 0

    period = str((rec.get("strategy") or {}).get("period", ""))
    years = [int(y) for y in _YEAR.findall(period)]
    a_pts = 2 if (rec.get("strategy") or {}).get("grounded") is True and years and max(years) >= now_year else 0

    return {"score": t_pts + c_pts + e_pts + a_pts, "themes_matched": sorted(set(themes)),
            "countries_matched": sorted(hits), "points": {"themes": t_pts, "countries": c_pts,
                                                          "eligibility": e_pts, "active": a_pts}}


def rank(records: list[dict[str, Any]], cfg: dict[str, Any], now_year: int | None = None) -> list[dict[str, Any]]:
    for r in records:
        r["fit"] = fit(r, cfg, now_year)
    return sorted(records, key=lambda r: (-r["fit"]["score"], r.get("name", "")))


def cache_path(name: str):
    """Keyed on the full name. The organization normalizer drops words such as
    Foundation and Group, which would put Dangote Foundation and Dangote Group in one
    file, so a short hash of the whole name keeps them apart."""
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")[:48] or "funder"
    digest = hashlib.sha1((name or "").strip().lower().encode("utf-8")).hexdigest()[:8]
    return config.WORK_DIR / "funders" / f"{slug}-{digest}.json"


def read_cached(name: str) -> dict[str, Any] | None:
    p = cache_path(name)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def write_cached(name: str, rec: dict[str, Any]) -> None:
    p = cache_path(name)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
