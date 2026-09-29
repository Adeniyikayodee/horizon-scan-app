"""Evaluation harness, on Google's two axes.

  1. Trajectory eval  (objective, no judge): run Scout on each golden org and
     measure whether it hit the org's own domain (grounding), how much of the
     expected substance it recovered (recall), and how much of what it returned
     cites the org's own site (primary-source precision).
  2. Final-response eval (LLM judge): score a produced memo on a rubric.

Run:  python -m scan eval [--provider openrouter --model ...] [--judge out/synthesis_memo.md]
"""
from __future__ import annotations

import json
from pathlib import Path

from . import agents, config
from .client import structured_call

GOLDEN = config.ROOT / "eval" / "golden.json"

RUBRIC_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["themes_supported", "sources_primary", "house_style", "actionability", "overall", "notes"],
    "properties": {
        "themes_supported": {"type": "string", "enum": ["strong", "partial", "weak"]},
        "sources_primary": {"type": "string", "enum": ["strong", "partial", "weak"]},
        "house_style": {"type": "string", "enum": ["strong", "partial", "weak"]},
        "actionability": {"type": "string", "enum": ["strong", "partial", "weak"]},
        "overall": {"type": "string", "enum": ["strong", "adequate", "weak"]},
        "notes": {"type": "string"},
    },
}


def _load_golden() -> list[dict]:
    return json.loads(GOLDEN.read_text(encoding="utf-8"))["orgs"]


async def trajectory() -> list[dict]:
    ctx = config.load_context()
    out = []
    for g in _load_golden():
        try:
            scout = await agents.scout(ctx, {"name": g["name"], "type": g.get("type", ""),
                                             "region": g.get("region", "")})
        except Exception as e:
            out.append({"org": g["name"], "error": str(e)[:80]})
            continue
        cands = scout["candidates"]
        blob = " ".join((c.get("name", "") + " " + c.get("one_liner", "")) for c in cands).lower()
        urls = " ".join(c.get("url", "") for c in cands)
        kw = g.get("expect_keywords", [])
        matched = [k for k in kw if k.lower() in blob]
        dom = g.get("expect_domains", [])
        on_domain = sum(1 for c in cands if any(d in c.get("url", "") for d in dom))
        out.append({
            "org": g["name"], "found": len(cands),
            "recall": round(len(matched) / len(kw), 2) if kw else 0.0,
            "domain_hit": any(d in urls for d in dom),
            "precision": round(on_domain / len(cands), 2) if cands else 0.0,
            "matched": matched,
        })
    return out


async def judge_memo(memo_text: str) -> dict:
    rubric = ("Score the memo, being critical. themes_supported: are the themes backed by the "
              "approaches. sources_primary: does it rest on primary sources. house_style: US English, "
              "active voice, serial comma, no em dashes, and no trace of any tool or AI. actionability: "
              "are the recommendations clear and specific. Mark each strong, partial, or weak, then an "
              "overall of strong, adequate, or weak, with notes.")
    # tier="strong" or the cheap search model grades the strong model's prose on the
    # OpenRouter path. Note the standing weakness: this is a same-family judge, so the
    # trajectory eval above is the objective half and this is the softer one.
    return await structured_call(
        model=config.MODEL_OPUS,
        frame="You are an evaluation judge for a research institute. " + rubric,
        user="MEMO TO SCORE:\n\n" + memo_text,
        schema=RUBRIC_SCHEMA, tier="strong",
    )


def print_trajectory(rows: list[dict]) -> None:
    print("\nTRAJECTORY EVAL, retrieval quality on the golden set")
    print("-" * 74)
    recs, precs, hits, n = [], [], 0, 0
    for r in rows:
        if r.get("error"):
            print(f"  {r['org'][:36]:36}  ERROR {r['error']}")
            continue
        n += 1
        recs.append(r["recall"]); precs.append(r["precision"]); hits += int(r["domain_hit"])
        print(f"  {r['org'][:36]:36}  found {r['found']:2}   recall {r['recall']:.2f}   "
              f"domain-hit {'Y' if r['domain_hit'] else 'N'}   primary-precision {r['precision']:.2f}")
    if n:
        print("-" * 74)
        print(f"  {'AGGREGATE':36}  recall {sum(recs)/n:.2f}   domain-hit {hits}/{n}   "
              f"primary-precision {sum(precs)/n:.2f}")


def print_rubric(res: dict) -> None:
    print("\nFINAL-RESPONSE EVAL, memo rubric (LLM judge)")
    print("-" * 74)
    for k in ("themes_supported", "sources_primary", "house_style", "actionability"):
        print(f"  {k:20} {res.get(k, '?')}")
    print(f"  {'OVERALL':20} {res.get('overall', '?')}")
    if res.get("notes"):
        print(f"  notes: {res['notes']}")


# --- the evidence ladder against a golden set of known evaluations ----------------
async def evidence_eval(golden_path) -> dict:
    """Grade every golden evaluation the way the pipeline does (fetch, read, ground,
    grade) and score the result against the known level.

    Targets (from the golden file): exact matches at or above exact_match_min, no
    evaluation graded E4 or above when it should not be, and no E3 or above resting on
    a method sentence that was not found in the document."""
    import asyncio

    from . import ladder, sources
    golden = json.loads(Path(golden_path).read_text(encoding="utf-8"))
    ctx = config.load_context()
    rows = []
    for e in golden["evaluations"]:
        doc = await asyncio.to_thread(sources.fetch_text, e["url"], config.READ_MAX_CHARS)
        if not doc:
            rows.append({**e, "error": "document could not be read"})
            continue
        try:
            r = await agents.read_evidence(ctx, {"name": e["program"], "what": ""},
                                           {"title": e["title"], "evaluator": e["evaluator"], "url": e["url"]}, doc)
        except Exception as ex:
            rows.append({**e, "error": str(ex)[:120]})
            continue
        mg = await asyncio.to_thread(sources.quote_exact, e["url"], r["method_quote"])
        og = await asyncio.to_thread(sources.quote_exact, e["url"], r["outcome_quote"])
        g = ladder.grade({**r}, implementer=e["implementer"], method_grounded=mg, outcome_grounded=og)
        rows.append({**e, "graded": g["level"], "model_level": g["model_level"], "method": r["method"],
                     "method_quote": r["method_quote"], "method_grounded": mg, "caps": g["caps"],
                     "flags": g["flags"]})
    graded = [r for r in rows if "graded" in r]
    exact = sum(1 for r in graded if r["graded"] == r["expected_level"])
    false_high = [r["id"] for r in graded if r["graded"] >= 4 and r["expected_level"] < 4]
    ungrounded = [r["id"] for r in graded if r["graded"] >= 3 and r["method_grounded"] is not True]
    t = golden.get("targets", {})
    rate = exact / len(rows) if rows else 0.0
    passed = (rate >= float(t.get("exact_match_min", 0.9)) and len(false_high) <= int(t.get("false_e4_plus_max", 0))
              and len(ungrounded) <= int(t.get("e3_plus_ungrounded_max", 0)))
    return {"rows": rows, "exact": exact, "total": len(rows), "rate": round(rate, 3),
            "false_e4_plus": false_high, "e3_plus_ungrounded": ungrounded, "passed": passed}


def evidence_report(res: dict) -> str:
    """The accuracy check as a short markdown report."""
    from . import ladder
    lines = ["# Evidence ladder accuracy check\n",
             f"Exact match: {res['exact']} of {res['total']} ({round(res['rate'] * 100)} percent). "
             f"Graded E4 or above when it should not be: {len(res['false_e4_plus'])}. "
             f"E3 or above without a grounded method sentence: {len(res['e3_plus_ungrounded'])}. "
             f"Result: {'PASS' if res['passed'] else 'FAIL'}.\n",
             "| Evaluation | Expected | Graded | Model | Method sentence found | Caps |", "|---|---|---|---|---|---|"]
    for r in res["rows"]:
        if "error" in r:
            lines.append(f"| {r['id']} | {ladder.label(r['expected_level'])} | error | | | {r['error']} |")
            continue
        lines.append(f"| {r['id']} | {ladder.label(r['expected_level'])} | {ladder.label(r['graded'])} | "
                     f"{r['model_level']} | {r['method_grounded']} | {'; '.join(r['caps'])} |")
    lines.append("\n## Method sentences quoted\n")
    for r in res["rows"]:
        if "graded" in r:
            lines.append(f"- {r['id']}: \"{r['method_quote'][:220]}\"")
    return "\n".join(lines) + "\n"


# --- can the Evidence agent FIND the known evaluation? -----------------------------
def _title_key(t: str) -> set[str]:
    import re
    stop = {"the", "a", "an", "of", "for", "in", "and", "on", "from", "to", "with", "evidence"}
    return {w for w in re.findall(r"[a-z]+", (t or "").lower()) if len(w) > 3 and w not in stop}


def _same_evaluation(found: dict, known: dict) -> bool:
    """A found result matches the known evaluation when it points at the same host
    and path, or its title shares most of the known title's words."""
    from .ladder import _host
    if _host(found.get("url", "")) and found.get("url", "").split("?")[0].rstrip("/") == known["url"].split("?")[0].rstrip("/"):
        return True
    k, f = _title_key(known.get("title", "")), _title_key(found.get("title", ""))
    return bool(k) and len(k & f) / len(k) >= 0.6


async def search_recall(golden_path) -> dict:
    """For every golden evaluation above E1, run the Evidence agent's search (both
    passes, as the pipeline does) and record whether the known evaluation, or the same
    study under another title, was found. Target: search_recall_min in the golden file."""
    golden = json.loads(Path(golden_path).read_text(encoding="utf-8"))
    ctx = config.load_context()
    evcfg = config.active_spec().get("evidence") or {}
    rows = []
    for e in golden["evaluations"]:
        if e["expected_level"] < 2:
            continue
        appr = {"name": e["program"], "what": ""}
        org = {"name": e["implementer"], "region": ""}
        try:
            found = await agents.find_evidence(ctx, org, appr, evcfg.get("search_first") or [])
            hit = any(_same_evaluation(f, e) for f in found)
            if not hit:
                more = await agents.find_evidence(ctx, org, appr, evcfg.get("search_first") or [], hint=(
                    "The first search did not find it. Search again more widely: the program's name with "
                    "\"randomized\", \"impact evaluation\", and \"evaluation\"; working paper series such as "
                    "NBER, IZA, the World Bank Policy Research Working Papers, and 3ie reports."))
                found += more
                hit = any(_same_evaluation(f, e) for f in more)
            rows.append({"id": e["id"], "found": hit, "results": [f.get("title", "")[:80] for f in found]})
        except Exception as ex:
            rows.append({"id": e["id"], "error": str(ex)[:120]})
    got = sum(1 for r in rows if r.get("found"))
    target = float(golden.get("targets", {}).get("search_recall_min", 0.8))
    rate = got / len(rows) if rows else 0.0
    return {"rows": rows, "found": got, "total": len(rows), "rate": round(rate, 3), "passed": rate >= target}


def recall_report(res: dict) -> str:
    lines = ["# Evidence search recall check\n",
             f"Known evaluations found: {res['found']} of {res['total']} ({round(res['rate'] * 100)} percent). "
             f"Result: {'PASS' if res['passed'] else 'FAIL'}.\n",
             "| Evaluation | Found | What the search returned |", "|---|---|---|"]
    for r in res["rows"]:
        if "error" in r:
            lines.append(f"| {r['id']} | error | {r['error']} |")
        else:
            lines.append(f"| {r['id']} | {'yes' if r['found'] else 'no'} | {'; '.join(r['results'])[:300]} |")
    return "\n".join(lines) + "\n"
