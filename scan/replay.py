"""Test-mode replay of a recorded YES run, for showing the app without cost.

Test mode normally fills the flow with canned placeholder text. When the app turns on
config.REPLAY, test mode instead replays what the models actually answered in a finished
run: the programs each organization yielded, the readings and their exact quotes, the
scores, the evaluations and their grades, the Verifier and Auditor verdicts, the funder
records, and the brief. Nothing is invented and nothing is fetched. The code still runs
every gate, grade, and check on those answers, so the result is the recorded run.

The fixture is built once from a finished run folder:

    python -m scan.replay build [profiles/yes/run]

Organizations that are not in the recording fall through to the ordinary mocks.
"""
from __future__ import annotations

import json
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

from . import config, spec

PROFILE = "yes"
FIXTURE = config.PROFILES_DIR / PROFILE / "demo" / "replay.json"

# The recorded run placed only the options that passed review. Every other recorded
# program gets the seed theme it reads closest to, so a reviewer who keeps more options
# in the demo still sees them themed. The seven recorded placements come from the run's
# own options workbook and override these.
_THEME_OF = {
    "Young Africa Works – TVET": "TVET in higher education",
    "Africa Youth Employment Clock": "Implementation research",
    "Digital Economy Program": "Digital integration: gaps and inequality",
    "Next Wave: Market Making for Entrepreneurs": "Entrepreneurship and youth-led business",
    "Skills for Innovation, Resilience and Aspirations (SIRA)": "Quality, decent jobs for young people",
    "Skills for Economic Transformation and Jobs (SET4Jobs)": "TVET at secondary level",
    "Emprega Program (Mozambique)": "Quality, decent jobs for young people",
    "Employment and Skills for Development in Africa": "Quality, decent jobs for young people",
    "Skills Initiative for Africa (SIFA)": "TVET at secondary level",
    "GenerationDigital!": "Digital integration: gaps and inequality",
    "Ethio-German Sustainable Training and Education Programme IV": "TVET at secondary level",
    "Skills for Youth Employability, Entrepreneurship and Empowerment (S4YEEE)": "TVET at secondary level",
    "Career Path Development for Employment (CPD4E)": "TVET in higher education",
    "Investing in Young Businesses in Africa – Women Entrepreneurship for Africa (IYBA-WE4A)":
        "Entrepreneurship and youth-led business",
    "GIZ Kenya Accelerator Programme for Youth-Led Businesses (with KIBT)": "Entrepreneurship and youth-led business",
    "STEP UP II Digital Skills Programme": "Digital integration: gaps and inequality",
    "Ikamva Digital": "Digital integration: gaps and inequality",
    "KIC AgriTech Challenge": "Entrepreneurship and youth-led business",
    "KIC AgriTech Challenge Pro": "Entrepreneurship and youth-led business",
    "Young Farmer Business Academy (YFBA)": "Entrepreneurship and youth-led business",
    "KIC/AGRA Start-Up Kits for Disadvantaged Youth": "Entrepreneurship and youth-led business",
    "SAGE Project": "Secondary education",
    "Social Innovators Programme (SIP)": "Entrepreneurship and youth-led business",
    "Youth Leadership Development Programme (YLDP)":
        "Young people in policymaking for employment, skills, and transformation",
    "Lead The Way (LTW)": "Young people in policymaking for employment, skills, and transformation",
    "SA Youth (SAYouth.mobi)": "Quality, decent jobs for young people",
    "National Pathway Management Network (NPMN)": "Quality, decent jobs for young people",
    "Digital Inclusion for Youth Employment": "Digital integration: gaps and inequality",
    "Programme National de Stage, d'Apprentissage et de Reconversion (PNSAR 2024-2025)":
        "Quality, decent jobs for young people",
    "Jóvenes en Acción": "Financing education",
    "Jóvenes en Acción (portal de registro)": "Financing education",
}

_MARK_PTS = {"strong": 3, "partial": 2, "weak": 1}


# --- building the fixture from a finished run ---------------------------------------
def build(src: Path, out: Path = FIXTURE) -> Path:
    import openpyxl

    from . import io_xlsx

    work = src / "work"
    roster = {o["name"]: o for o in io_xlsx.read_orgs(config.PROFILES_DIR / PROFILE / "organizations.xlsx")}
    manifest = json.loads((work / "manifest.json").read_text(encoding="utf-8"))
    by_name = {}
    for f in sorted((work / "orgs").glob("*.jsonl")):
        p = json.loads(f.read_text(encoding="utf-8").splitlines()[-1])
        by_name[p["org"]] = p
    orgs = []
    for key in sorted(manifest):                       # the run's own order
        p = by_name.get(manifest[key]["org"])
        if not p:
            continue
        info = roster.get(p["org"], {})
        orgs.append({"name": p["org"], "type": info.get("type", ""), "region": info.get("region", ""),
                     "website": info.get("website", ""), "rows": p.get("rows", []),
                     "dropped": p.get("dropped", []), "reports_found": p.get("reports_found", 0)})

    themes = dict(_THEME_OF)
    wb = openpyxl.load_workbook(src / "out" / "program_design_options.xlsx", read_only=True)
    for r in wb["Options"].iter_rows(min_row=2, values_only=True):
        if r and r[0] and r[1]:
            themes[r[1]] = r[0]

    hunches = []
    hp = src / "review" / "hunches.md"
    if hp.exists():
        for line in hp.read_text(encoding="utf-8").splitlines():
            m = re.match(r"- (.+?): (.+)", line)
            if m:
                hunches.append({"name": m.group(1).strip(), "note": m.group(2).strip()})

    funders = {}
    for f in sorted((work / "funders").glob("*.json")):
        rec = json.loads(f.read_text(encoding="utf-8"))
        funders[rec["name"]] = {k: rec.get(k) for k in
                                ("strategy", "themes", "countries", "instruments", "size", "eligibility", "calls")}

    brief = (src / "out" / "yes_scan_brief.md").read_text(encoding="utf-8")
    recorded_spec = json.loads((work / "spec.json").read_text(encoding="utf-8"))
    recorded = next((r.get("accessed", "") for o in orgs for r in o["rows"] if r.get("accessed")), "")
    missing = [r["name"] for o in orgs for r in o["rows"] if r["name"] not in themes]
    if missing:
        raise SystemExit(f"no theme for: {missing}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"recorded": recorded, "source": str(src.relative_to(config.ROOT)),
                               "spec": recorded_spec, "orgs": orgs, "themes": themes, "hunches": hunches,
                               "funders": funders, "brief": brief}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    return out


# --- reading it back ------------------------------------------------------------------
@lru_cache(maxsize=1)
def _data() -> dict[str, Any] | None:
    if not FIXTURE.exists():
        return None
    d = json.loads(FIXTURE.read_text(encoding="utf-8"))
    d["_org"] = {o["name"]: o for o in d["orgs"]}
    d["_row"] = {r["name"]: r for o in d["orgs"] for r in o["rows"]}
    d["_drop"] = {x["name"]: x for o in d["orgs"] for x in o["dropped"]
                  if x.get("stage") == "not kept at reading"}
    ground: dict[tuple[str, str], Any] = {}
    for r in d["_row"].values():
        url = r.get("url", "")
        q = (r.get("verification") or {}).get("confirming_quote", "")
        if q:
            ground[(url, q)] = r.get("quote_grounded")
        for x in [q for q in (r.get("quotes") or []) if q][:3]:
            ground.setdefault((url, x), r.get("reading_grounded"))
        for e in (r.get("evidence_record") or {}).get("evaluations") or []:
            ground[(e.get("url", ""), e.get("method_quote", ""))] = e.get("method_grounded")
            ground[(e.get("url", ""), e.get("outcome_quote", ""))] = e.get("outcome_grounded")
    for f in d["funders"].values():
        for k in ("strategy", "themes", "countries", "instruments", "size", "eligibility"):
            item = f.get(k) or {}
            if item.get("quote"):
                ground[(item.get("url", ""), item["quote"])] = item.get("grounded")
    d["_ground"] = ground
    return d


def available() -> bool:
    return FIXTURE.exists()


def active() -> bool:
    """Replay only in test mode, only when the app asked for it, and only for the scan
    that was recorded, so the tests and command-line dry runs keep the plain mocks."""
    return bool(config.DRY_RUN and getattr(config, "REPLAY", False) and available()
                and spec.profile_name(config.active_spec()) == PROFILE)


def recorded_on() -> str:
    d = _data()
    return d["recorded"] if d else ""


def spec_of_the_run() -> dict[str, Any]:
    """The scan spec the recorded run was produced under. The demo runs on this rather
    than on today's profile, so editing the profile never leaves the demo half-old."""
    d = _data()
    return json.loads(json.dumps(d.get("spec") or {})) if d else {}


def orgs() -> list[dict[str, str]]:
    """The recorded roster, in the run's order."""
    d = _data()
    return [{k: o[k] for k in ("name", "type", "region", "website")} for o in d["orgs"]] if d else []


def grounded(url: str, quote: str):
    """What the recorded run found when it checked this quote against this source.
    None when the pair was never checked, the same as a source that cannot be read."""
    d = _data()
    return d["_ground"].get((url, quote)) if d else None


def readable(program: str, url: str) -> bool:
    """Whether the recorded run could read this evaluation. One it could not read was
    skipped then, so it is skipped now."""
    if not active():
        return True
    r = _data()["_row"].get(program)
    if not r:
        return True
    return any(e.get("url") == url for e in (r.get("evidence_record") or {}).get("evaluations") or [])


def row_value(program: str, key: str, default: Any = None) -> Any:
    if not active():
        return default
    r = _data()["_row"].get(program)
    return r.get(key, default) if r else default


# --- answering the stages ---------------------------------------------------------------
def _field(user: str, label: str) -> str:
    m = re.search(rf"^{re.escape(label)}:\s*(.*)$", user, re.M)
    return m.group(1).strip() if m else ""


def _named(user: str, label: str) -> dict[str, Any] | None:
    """The recorded row a prompt is about. Names can hold a colon, so match the
    longest recorded name the line starts with."""
    line = _field(user, label)
    rows = _data()["_row"]
    if line in rows:
        return rows[line]
    hits = [n for n in rows if line.startswith(n)]
    return rows[max(hits, key=len)] if hits else None


def _scout(user: str) -> dict[str, Any] | None:
    o = _data()["_org"].get(_field(user, "Organization"))
    if not o:
        return None
    if "first search was thin" in user:
        return {"queries": [], "candidates": []}
    cands = [{"name": r["name"], "one_liner": r.get("report_title") or r.get("what", ""),
              "year": str(r.get("year", "")), "url": r.get("url", ""),
              "source_type": r.get("source_type") or "report"} for r in o["rows"]]
    cands += [{"name": x["name"], "one_liner": x.get("reason", ""), "year": "", "url": o.get("website", ""),
               "source_type": "webpage"} for x in o["dropped"] if x.get("stage") == "not kept at reading"]
    queries = next((r.get("queries") for r in o["rows"] if r.get("queries")), [])
    return {"queries": queries, "candidates": cands}


def _librarian(user: str) -> dict[str, Any] | None:
    o = _data()["_org"].get(_field(user, "Organization"))
    if not o:
        return None
    seen, reports = set(), []
    for r in o["rows"]:
        if r.get("report_title") and r.get("url") and r["url"] not in seen:
            seen.add(r["url"])
            reports.append({"title": r["report_title"], "date": r.get("report_date", ""),
                            "url": r["url"], "type": r.get("source_type") or "report"})
    return {"reports": reports}


def _read(user: str) -> dict[str, Any] | None:
    name = _field(user, "Candidate")
    d = _data()
    if name in d["_drop"]:
        return {"keep": False, "keep_reason": d["_drop"][name].get("reason", ""), "band": "emerging",
                "what": "", "evidence": "", "uptake": "", "quotes": [], "locator": "", "verbatim": False,
                "access_note": ""}
    r = d["_row"].get(name)
    if not r:
        return None
    out = {k: r.get(k) for k in ("band", "what", "evidence", "uptake", "quotes", "locator", "verbatim",
                                 "access_note", "read_chars", "source_chars", "source_truncated",
                                 "source_reachable")}
    out.update({"keep": True, "keep_reason": "Kept in the recorded run."})
    out.update({k: r.get(k, "") for k in spec.reader_fields(config.active_spec())})
    return out


def _score(user: str) -> dict[str, Any] | None:
    r = _named(user, "Approach")
    if not r:
        return None
    s = {k: v for k, v in (r.get("score") or {}).items() if not k.startswith("_")}
    s.setdefault("overall", r.get("overall", ""))
    return s


def _verify(user: str) -> dict[str, Any] | None:
    line = _field(user, "Claim to check")
    rows = _data()["_row"]
    hits = [n for n in rows if line.startswith(n)]
    if not hits:
        return None
    r = rows[max(hits, key=len)]
    # the row's own check names the program's description, an evaluation's check names
    # its effect summary; only the first line of either is in hand
    claim = line[len(r["name"]):].lstrip(" —").strip()
    if claim and not (r.get("what") or "").strip().startswith(claim):
        for e in (r.get("evidence_record") or {}).get("evaluations") or []:
            if e.get("verification") and (e.get("effect_summary") or "").strip().startswith(claim):
                return {k: v for k, v in e["verification"].items() if not k.startswith("_")}
    return {k: v for k, v in (r.get("verification") or {}).items() if not k.startswith("_")}


def _audit(user: str) -> dict[str, Any] | None:
    r = _named(user, "Approach")
    if not r or not r.get("audit"):
        return None
    return {k: v for k, v in r["audit"].items() if not k.startswith("_")}


def _find_evidence(user: str) -> dict[str, Any] | None:
    r = _named(user, "Program")
    if not r:
        return None
    evs = [e for e in (r.get("evidence_record") or {}).get("evaluations") or [] if not e.get("own")]
    if "first search found no evaluation" in user:
        evs = []                                     # the recorded first pass is the whole answer
    return {"evaluations": [{k: str(e.get(k, "")) for k in ("title", "year", "evaluator", "type", "url")}
                            for e in evs]}


def _read_evidence(user: str) -> dict[str, Any] | None:
    r = _named(user, "Program")
    url = _field(user, "Link")
    if not r:
        return None
    e = next((e for e in (r.get("evidence_record") or {}).get("evaluations") or [] if e.get("url") == url), None)
    if not e:
        return None
    out = {k: e.get(k) for k in ("program_matches", "method", "method_quote", "outcome_type", "outcomes",
                                 "outcome_quote", "effect_summary", "sample", "countries", "year", "evaluator",
                                 "independent", "peer_reviewed", "funders", "funder_quote", "cost_per_outcome",
                                 "cost_quote")}
    out["model_level"] = f"e{int(e.get('model_level') or 1)}"
    return out


def _funder(user: str) -> dict[str, Any] | None:
    f = _data()["funders"].get(_field(user, "Funder"))
    if not f:
        return None
    out = {}
    for k in ("strategy", "themes", "countries", "instruments", "size", "eligibility"):
        item = dict(f.get(k) or {})
        item.pop("grounded", None)
        out[k] = item
    out["calls"] = f.get("calls") or []
    return out


def _themes(user: str) -> dict[str, Any] | None:
    d = _data()
    kept = []
    for line in user.splitlines():
        if not line.startswith("- "):
            continue
        hits = [n for n in d["_row"] if line[2:].startswith(n + ":")]
        if hits:
            kept.append(max(hits, key=len))
    if not kept:
        return None
    crit = spec.criteria(config.active_spec())
    top = spec.postures(config.active_spec())[0]
    groups: dict[str, list[str]] = {}
    for n in kept:
        groups.setdefault(d["themes"][n], []).append(n)
    out = []
    for name, members in groups.items():
        rows = [d["_row"][m] for m in members]
        best = max(rows, key=lambda r: (r.get("evidence_record") or {}).get("level", 0))
        t = {"name": name, "tag": "current", "posture": top, "marquee": best["name"], "members": members,
             "top2": False,
             "rationale": (f"{len(members)} option{'s' if len(members) != 1 else ''} passed review here; "
                           f"the strongest evidence is {(best.get('evidence_record') or {}).get('label', 'E1')}, "
                           f"for {best['name']}.")}
        for c in crit:     # a theme carries the best mark any of its options earned
            t[c["key"]] = max((str((r.get("score") or {}).get(c["key"], "weak")) for r in rows),
                              key=lambda m: _MARK_PTS.get(m, 0))
        out.append(t)
    return {"themes": out}


def respond(schema: dict[str, Any], user: str) -> dict[str, Any] | None:
    """The recorded answer for this call, or None to fall through to the plain mock.
    The dispatch mirrors mock.mock_response."""
    if not active():
        return None
    keys = set(schema.get("properties", {}).keys())
    d = _data()
    if "eligibility" in keys and "calls" in keys:
        return _funder(user)
    if "evaluations" in keys:
        return _find_evidence(user)
    if "method_quote" in keys:
        return _read_evidence(user)
    if "candidates" in keys:
        return _scout(user)
    if "reports" in keys:
        return _librarian(user)
    if "keep" in keys:
        return _read(user)
    if "corroborated" in keys:
        return {"corroborated": False, "source": "", "url": "", "quote": "",
                "note": "The second-source check is not replayed in test mode."}
    if "quote_supports_claim" in keys:
        return _audit(user)
    if "overall" in keys and "evidence_basis" in keys:
        return _score(user)
    if "status" in keys:
        return _verify(user)
    if "themes" in keys:
        return _themes(user)
    if "memo_markdown" in keys:
        return {"memo_markdown": d["brief"], "scorecard_intro": ""}
    if "patterns" in keys:
        return {"patterns": d["hunches"]} if d["hunches"] else None
    return None


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "build":
        src = Path(sys.argv[2]) if len(sys.argv) > 2 else config.PROFILES_DIR / PROFILE / "run"
        p = build(src.resolve())
        _data.cache_clear()
        d = _data()
        print(f"wrote {p.relative_to(config.ROOT)}: {len(d['orgs'])} organizations, {len(d['_row'])} programs, "
              f"{len(d['funders'])} funders, recorded {d['recorded']}")
    else:
        print("usage: python -m scan.replay build [run folder]")
