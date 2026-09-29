"""Dry-run mocks. Schema-shaped canned data so the whole pipeline flows with no
key and no network. Score and theme marks follow the active spec's criteria, so
custom criteria flow through dry runs too.
"""
from __future__ import annotations

from typing import Any

from . import config, replay, spec as spec_mod

_MARKS = ["strong", "partial", "weak"]


def _subject(user: str) -> str:
    return user.splitlines()[0] if user else ""


def _scout(subj: str, h: int) -> dict[str, Any]:
    org = subj.replace("Organization:", "").strip() or "the organization"
    print(f"  scout    {org[:48]}")
    return {"queries": [f"{org} Africa economic transformation recent"],
            "candidates": [
                {"name": f"{org} value-addition initiative",
                 "one_liner": "A recent program on keeping more value onshore.",
                 "year": "2024", "url": f"https://example.org/a{h % 997}.pdf", "source_type": "report"},
                {"name": f"{org} evidence-to-policy lab",
                 "one_liner": "A pilot moving research into practice.",
                 "year": "2025", "url": f"https://example.org/b{h % 991}", "source_type": "webpage"}]}


def _read(subj: str, h: int) -> dict[str, Any]:
    keep = h % 5 != 0
    band = ["emerging", "frontier", "maturing"][h % 3]
    print(f"  read     {subj[:48]}  keep={keep} band={band}")
    return {"keep": keep, "band": band,
            "keep_reason": ("Names a program and carries a measured result." if keep
                            else "No named program and no concrete result on the page."),
            "what": "An approach that adds value in a new sector.",
            "evidence": "A pilot showed measurable gains in output and jobs.",
            "uptake": "One government has begun to adopt it.",
            "quotes": ["The program raised local value retention by a measurable margin."],
            "locator": "Section 3, Results, page 14", "verbatim": True,
            "access_note": "Published 2024.",
            **{k: ("Ghana" if k == "countries" else f"Sample {k.replace('_', ' ')}.")
               for k in spec_mod.reader_fields(config.active_spec())}}


def _score(subj: str, h: int) -> dict[str, Any]:
    print(f"  score    {subj[:48]}")
    out: dict[str, Any] = {}
    for i, c in enumerate(spec_mod.criteria(config.active_spec())):
        out[c["key"]] = _MARKS[(h + i) % 2]
        out["reason_" + c["key"]] = "Grounded in the evidence on record."
    out["overall"] = ["high", "medium"][h % 2]
    out["evidence_basis"] = "The pilot's measured gain in local value retention."
    out["self_check"] = "consistent"
    out["self_check_note"] = "The marks follow from the evidence."
    return out


def _verify(subj: str, h: int) -> dict[str, Any]:
    if h % 3 == 0:
        print(f"  verify   {subj[:48]}  partial")
        return {"status": "partial", "confirming_quote": "", "note": "Rests on secondary sources.",
                "primary_url": "", "claim_supported": False, "figure_check": "n/a", "discrepancies": []}
    print(f"  verify   {subj[:48]}  verified")
    return {"status": "verified", "confirming_quote": "The institution's own page states the gain.",
            "note": "Confirmed on the primary source.", "primary_url": "https://example.org/primary",
            "claim_supported": True, "figure_check": "Figure matches the source.", "discrepancies": []}


def _audit(subj: str, h: int) -> dict[str, Any]:
    flag = h % 7 == 0
    print(f"  audit    {subj[:48]}  {'flag' if flag else 'pass'}")
    return {"quote_supports_claim": not flag, "score_matches_evidence": "overstated" if flag else "consistent",
            "source_is_primary": True, "verdict": "flag" if flag else "pass",
            "notes": "Chain is internally consistent." if not flag else "Score looks high."}


def _librarian(subj: str) -> dict[str, Any]:
    org = subj.replace("Organization:", "").strip() or "the organization"
    print(f"  library  finding reports for {org[:40]}")
    return {"reports": [
        {"title": f"{org} value-addition working paper", "date": "2024",
         "url": "https://example.org/report-value-addition.pdf", "type": "working paper"},
        {"title": f"{org} annual report 2024", "date": "2024",
         "url": "https://example.org/annual-2024.pdf", "type": "annual report"}]}


def _frame_orgs(user: str) -> dict[str, Any]:
    names = [l[2:].strip() for l in user.splitlines() if l.startswith("- ")]
    print(f"  frame    {len(names)} added organizations")
    return {"organizations": [
        {"name": n, "type": "Analyst-added", "region": "",
         "why": "Added by the analyst, framed for the roster."} for n in names]}


def _corroborate() -> dict[str, Any]:
    print("  corrob   checking a second, independent source")
    return {"corroborated": True, "source": "An independent institution",
            "url": "https://example.org/second-source", "quote": "A second source confirms the gain.",
            "note": "Confirmed on an independent source."}


def _discover() -> dict[str, Any]:
    print("  discover organizations")
    return {"organizations": [
        {"name": "African Economic Research Consortium (AERC)", "type": "African policy institute",
         "region": "Africa", "why": "Strong research-to-policy track record."},
        {"name": "Policy Center for the New South", "type": "African policy institute",
         "region": "Africa", "why": "Atlantic and Africa economic dialogue."},
        {"name": "UN Trade and Development (UNCTAD)", "type": "Multilateral", "region": "Global",
         "why": "Trade and productive-capacity work."}]}


def _themes(user: str) -> dict[str, Any]:
    crit = spec_mod.criteria(config.active_spec())
    members = [l[2:].split(":")[0].strip() for l in user.splitlines() if l.startswith("- ")]
    print(f"  theme    clustering {len(members)} approaches")

    def theme(name, tag, posture, mark, mem, top2):
        d = {"name": name, "tag": tag, "posture": posture, "rationale": "A clear rationale for this theme.",
             "marquee": mem[0] if mem else "", "members": mem, "top2": top2}
        for c in crit:
            d[c["key"]] = mark
        return d

    sp = config.active_spec()
    if sp.get("themes_seed"):
        seed = sp["themes_seed"]
        ps = spec_mod.postures(sp)
        out = []
        for i, s in enumerate(seed[:4]):
            mem = members[i * 3:(i + 1) * 3]
            if mem:
                # the first theme asks for the top posture on purpose, so the gates are exercised
                out.append(theme(s["name"].lower(), "new", ps[0] if i == 0 else ps[min(i, len(ps) - 1)],
                                 "strong", mem, i == 0))
        if len(members) > 12:
            out.append(theme("An invented theme outside the list", "new", ps[0], "partial", members[12:13], False))
        return {"themes": out}

    # Two of these are deliberately NON-compliant, so the dry run exercises the gates
    # rather than a set already in the right shape. The third is tagged existing but
    # asks to enter, which spec.coerce_theme must correct. The fourth is tagged new but
    # names work the institute already runs, which spec.screen_existing must catch,
    # and which is exactly what shipped in run 4be936d649.
    return {"themes": [
        theme("Blue economy and coastal value addition", "new", "enter", "strong", members[:3], True),
        theme("Sovereign and strategic investment funds", "adjacent", "enter", "partial", members[3:5], True),
        theme("Financing Africa's future", "existing", "enter", "strong", members[5:7], False),
        theme("AI-driven policy experimentation platforms", "new", "enter", "strong", members[7:9], True)]}


_FILLER = (
    "The scan points to two clean new areas, the blue economy and coastal value addition, and "
    "sovereign and strategic investment funds, and both turn on Africa keeping more of the value "
    "it creates in a sector it is only now entering. The capital and the technical knowledge "
    "already sit with the financiers and the specialist providers, which leaves the question of "
    "who captures the value open, and that question is the institute's to define and own. Read "
    "through the DEPTH lens, the opening advances diversification into a new productive sector, "
    "export competitiveness in processed goods, and productivity across the coastal value chain, "
    "so the mandate fit is direct and the ground is genuinely open. ")


def _synth() -> dict[str, Any]:
    """A memo shaped to the ACTIVE spec, so a dry run exercises the real structure and
    the length floor rather than a stub that would fail its own check."""
    print("  synth    writing memo and scorecard intro")
    sp = config.active_spec()
    m = spec_mod.memo_spec(sp)
    floor = int(m.get("min_words", 4000))
    sections = m.get("sections", [])
    # spread the floor across the sections, with a little headroom so the mock always
    # clears its own gate even as the spec's section list changes
    per = max(1, int(floor * 1.15 / max(1, len(sections)) / len(_FILLER.split())) + 1)
    filler = _FILLER
    title = "# Global scan, a wrap-up on the new areas to enter"
    if sp.get("brief_checks"):
        filler = ("The scan found program designs that help young people find work, and some have strong proof "
                  "while others still need more study; the team can use them to plan the next proposal. ")
        title = "# Program designs that help young people find work"
        ceiling = int(m.get("max_words") or floor * 1.2)
        per = max(1, int((floor + ceiling) / 2 / max(1, len(sections)) / len(filler.split())))
    parts = [title, "", filler.strip(), ""]
    for s in sections:
        parts += [f"## {s['heading']}", "", ((filler if sp.get("brief_checks") else _FILLER) * per).strip(), ""]
    memo = "\n".join(parts)
    return {"memo_markdown": memo,
            "scorecard_intro": "Themes scored on the criteria, with two clean new areas to enter first."}


def _gaps(user: str) -> dict[str, Any]:
    themes = [l.split('"name": "')[1].split('"')[0] for l in user.splitlines() if '"name": "' in l]
    print(f"  gaps     drafting the register across {len(set(themes))} themes")
    return {"gaps": [{
        "question": "What does it take for a training system to raise productivity across an economy?",
        "theme": themes[0] if themes else "", "basis": "coverage", "quote": "",
        "source": "The coverage map", "what_is_known": "Single programs are evaluated, systems are not.",
        "countries_covered": ["Ghana"], "countries_missing": ["Niger"],
        "inclusion_gap": "Not answered for young people with disabilities.",
        "what_it_would_take": "A study across several countries that follows the system, not one project.",
        "who_is_closest": "An independent research group."}]}


def _hunches() -> dict[str, Any]:
    print("  hunches  seeding cross-org patterns")
    return {"patterns": [
        {"name": "Value capture recurs", "note": "Several approaches turn on keeping value onshore."},
        {"name": "Coastal sectors look open", "note": "The blue economy appears underserved."}]}


def _find_evidence(subj: str, h: int) -> dict[str, Any]:
    print(f"  evidence finding evaluations for {subj[:40]}")
    return {"evaluations": [
        {"title": "Impact evaluation of the program", "year": "2021",
         "evaluator": "An independent research group", "type": "impact evaluation",
         "url": f"https://example.org/eval{h % 97}.pdf"}]}


def _read_evidence(subj: str, h: int) -> dict[str, Any]:
    print(f"  evidence reading {subj[:40]}")
    rct = h % 2 == 0
    return {"program_matches": True, "method": "rct" if rct else "before_after",
            "method_quote": ("Young people were randomly assigned to the program or a control group."
                             if rct else "We compare baseline and endline surveys of participants."),
            "outcome_type": "outcomes", "outcomes": ["employment", "earnings"],
            "outcome_quote": "Employment rose among participants.",
            "effect_summary": "Employment rose by a measured amount.", "sample": "1,000 young people",
            "countries": ["Ghana"], "year": "2021", "evaluator": "An independent research group",
            "independent": True, "peer_reviewed": False, "funders": ["A foundation"], "funder_quote": "Funded by a foundation.",
            "cost_per_outcome": "not found", "cost_quote": "", "model_level": "E4" if rct else "E2"}


def _funder(subj: str) -> dict[str, Any]:
    name = subj.replace("Funder:", "").strip()
    print(f"  funder   {name[:48]}")
    url = "https://example.org/strategy"

    def f(value, quote="The strategy says so."):
        return {"value": value, "quote": quote, "url": url}
    return {"strategy": {**f("Youth employment strategy"), "period": "2024-2030"},
            "themes": f(["TVET at secondary level"]), "countries": f(["Ghana", "Kenya"]),
            "instruments": f(["grants"]), "size": f("not found"), "eligibility": f("unclear"),
            "calls": []}


def mock_response(schema: dict[str, Any], user: str) -> dict[str, Any]:
    recorded = replay.respond(schema, user)
    if recorded is not None:
        return recorded
    keys = set(schema.get("properties", {}).keys())
    subj = _subject(user)
    h = sum(ord(c) for c in user)

    if "eligibility" in keys and "calls" in keys:
        return _funder(subj)
    if "evaluations" in keys:
        return _find_evidence(subj, h)
    if "method_quote" in keys:
        return _read_evidence(subj, h)
    if "candidates" in keys:
        return _scout(subj, h)
    if "reports" in keys:
        return _librarian(subj)
    if "keep" in keys:
        return _read(subj, h)
    if "corroborated" in keys:
        return _corroborate()
    if "organizations" in keys:
        return _frame_orgs(user) if "to frame" in user.lower() else _discover()
    if "quote_supports_claim" in keys:
        return _audit(subj, h)
    if "overall" in keys and "evidence_basis" in keys:
        return _score(subj, h)
    if "status" in keys:
        return _verify(subj, h)
    if "themes" in keys:
        return _themes(user)
    if "memo_markdown" in keys:
        return _synth()
    if "gaps" in keys:
        return _gaps(user)
    if "patterns" in keys:
        return _hunches()
    return {}
