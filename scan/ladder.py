"""The evidence ladder: how strong the proof is that a program works.

The model reads an evaluation and proposes a level. The code sets the level. It
reads the method sentence the model quoted, checks that sentence is really in the
evaluation, maps the method words to a level, and applies the caps. Where the model
and the code disagree, the lower level stands and the row is flagged.

    E5  replicated: a systematic review or meta-analysis, or RCTs in two or more countries
    E4  causal: a randomized controlled trial of this program, evaluated independently
    E3  credible comparison: a quasi-experimental design
    E2  measured change with no comparison group
    E1  described only

Based on the Maryland Scientific Methods Scale as used by the What Works Centre for
Local Economic Growth, with the Nesta Standards of Evidence requirement that the top
levels show replication and independence.
"""
from __future__ import annotations

import re
from typing import Any

from . import io_xlsx

LEVELS = {1: "E1", 2: "E2", 3: "E3", 4: "E4", 5: "E5"}
METHODS = ["systematic_review", "meta_analysis", "rct", "quasi_experimental",
           "before_after", "descriptive", "none"]
_METHOD_LEVEL = {"systematic_review": 5, "meta_analysis": 5, "rct": 4, "quasi_experimental": 3,
                 "before_after": 2, "descriptive": 1, "none": 1}

# An evaluation that reports no result yet, because the study is still running or the
# document only refers to results held elsewhere, is not evidence that a design works.
_NO_RESULT = re.compile(r"\bnot stated\b|\bnot (yet )?(reported|available|published|released)\b|"
                        r"\bno (results?|effect sizes?|findings?) (are |were |is )?(yet )?(reported|stated|given|available)\b|"
                        r"\b(results?|findings?) (are|is) (pending|forthcoming|expected)\b|"
                        r"\b(study|trial|evaluation) is (still )?(ongoing|underway|in progress)\b|"
                        r"\bdue to (end|conclude|report)\b|\bresults are not\b", re.I)


def reports_a_result(effect: str) -> bool:
    """Does the evaluation actually report an outcome? An empty or 'not stated' summary,
    or one that says the study is still running, does not."""
    e = (effect or "").strip()
    return bool(e) and not _NO_RESULT.search(e)

# Method words, English and French, strongest first. Matched on the grounded quote
# only, lowercased, with accents kept (the French patterns carry them).
_TERMS: list[tuple[int, str]] = [
    (5, r"systematic review|meta[- ]?analys[ie]s|revue syst[ée]matique|m[ée]ta[- ]?analyse"),
    (4, r"randomi[sz]ed|randomi[sz]ation|\brcts?\b|random assignment|\brandomly\b|at random|"
        r"\ba random (half|third|quarter|subset|sample)\b|lottery|"
        r"al[ée]atoire|randomis[ée]e?s?|tirage au sort"),
    (3, r"difference[- ]in[- ]differences?|regression discontinuity|"
        r"propensity score matching|matching estimator|matched comparison|exact matching|synthetic control|"
        r"instrumental variables?|quasi[- ]experiment\w*|comparison group|"
        r"\bmatch(es|ed)?\b[^.]{0,80}\bwith (similar|comparable)\b|"
        r"control group|double diff[ée]rence|diff[ée]rence de diff[ée]rences|r[ée]gression sur discontinuit[ée]|"
        r"appariement|groupe de comparaison|groupe t[ée]moin|quasi[- ]exp[ée]riment\w*"),
    (2, r"baseline and endline|before and after|pre-? ?and[- ]post|pre[- ]post|tracer stud(y|ies)|"
        r"monitoring data|follow[- ]up survey|enqu[êe]te de suivi|avant et apr[èe]s|situation de r[ée]f[ée]rence"),
]

AFRICAN_COUNTRIES = {
    "algeria", "angola", "benin", "botswana", "burkina faso", "burundi", "cabo verde", "cape verde",
    "cameroon", "central african republic", "chad", "comoros", "congo", "democratic republic of the congo",
    "drc", "cote d'ivoire", "côte d'ivoire", "ivory coast", "djibouti", "egypt", "equatorial guinea",
    "eritrea", "eswatini", "swaziland", "ethiopia", "gabon", "gambia", "the gambia", "ghana", "guinea",
    "guinea-bissau", "kenya", "lesotho", "liberia", "libya", "madagascar", "malawi", "mali",
    "mauritania", "mauritius", "morocco", "mozambique", "namibia", "niger", "nigeria", "rwanda",
    "sao tome and principe", "são tomé and príncipe", "senegal", "seychelles", "sierra leone",
    "somalia", "south africa", "south sudan", "sudan", "tanzania", "togo", "tunisia", "uganda",
    "zambia", "zimbabwe", "africa", "sub-saharan africa", "west africa", "east africa",
    "southern africa", "north africa", "central africa", "sahel",
}


def label(level: int) -> str:
    return LEVELS.get(int(level), "E1")


def parse_level(v: Any) -> int:
    m = re.search(r"[1-5]", str(v or ""))
    return int(m.group(0)) if m else 1


def level_from_terms(quote: str) -> int:
    """The level the method words in a quoted sentence support, 1 when none. Hyphens
    are normalized first, since extracted PDFs break "difference-in-differences" into
    "difference -in-differences"."""
    low = re.sub(r"\s*-\s*", "-", (quote or "").lower())
    for level, pat in _TERMS:
        if re.search(pat, low):
            return level
    return 1


def is_african(countries: list[str] | str, region: str = "") -> bool | None:
    """True when any named country or region is in Africa, False when places are
    named and none is, None when nothing is named and the region says nothing."""
    if isinstance(countries, str):
        countries = [c for c in re.split(r"[;,/]| and ", countries) if c.strip()]
    names = [c.strip().lower() for c in countries or [] if str(c).strip()]
    if names:
        return any(n in AFRICAN_COUNTRIES or any(a in n for a in ("africa", "sahel")) for n in names)
    r = (region or "").strip().lower()
    if "africa" in r:
        return True
    return None if not r or r in ("global", "multiple", "various") else False


def _same_body(a: str, b: str) -> bool:
    na, nb = io_xlsx._norm_org(a), io_xlsx._norm_org(b)
    return bool(na and nb) and (na == nb or na in nb or nb in na)


def _host(url: str) -> str:
    m = re.match(r"https?://([^/]+)", (url or "").lower())
    return re.sub(r"^www\.", "", m.group(1)) if m else ""


def grade(ev: dict[str, Any], implementer: str, method_grounded: bool | None,
          outcome_grounded: bool | None = None, implementer_site: str = "") -> dict[str, Any]:
    """Set one evaluation's level, in code. Returns the evaluation with `level`,
    `code_level`, `model_level`, `caps`, and `flags` filled in.

    Rules, each a cap, the lowest one wins:
      1. the method sentence must be found word for word in the evaluation, else E2
      2. the level cannot exceed what the method words in that sentence support
      3. E4 and E5 need independence, else E3. Independent means evaluated by someone
         other than the organization that delivers the program: academic teams that run
         a trial with the implementer or a research partner count as independent, and
         so does a peer-reviewed publication. Not independent means the implementer
         grading itself, or a document published on its own site and not peer reviewed.
      4. an evaluation that measures only outputs, or reports no result yet, is capped at E2
      5. an evaluation of a different program counts for nothing, E1
    and the model's own level is a ceiling too. An outcome sentence that is not found
    word for word is flagged for the reviewer, not capped: the caps rest on the design,
    and extracted PDFs often break the wording of a results sentence."""
    ev = dict(ev)
    model_level = parse_level(ev.get("model_level"))
    method = str(ev.get("method", "none")).lower()
    caps: list[str] = []
    level = min(model_level, _METHOD_LEVEL.get(method, 1))

    code_level = level_from_terms(ev.get("method_quote", ""))
    if method_grounded is not True and min(level, code_level) > 2:
        caps.append("method sentence not found in the evaluation, capped at E2")
    if method_grounded is not True:
        code_level = min(code_level, 2)
    level = min(level, code_level)

    evaluator = str(ev.get("evaluator", ""))
    own_site = bool(implementer_site) and _host(ev.get("url", "")) == _host(implementer_site)
    independent = ((bool(ev.get("independent")) and not _same_body(evaluator, implementer) and not own_site)
                   or bool(ev.get("peer_reviewed")))
    if level >= 4 and not independent:
        caps.append("published by the implementer and not peer reviewed, capped at E3" if own_site
                    else "evaluator not independent of the implementer, capped at E3")
        level = 3
    if level > 2 and not reports_a_result(str(ev.get("effect_summary", ""))):
        caps.append("the evaluation reports no result yet, capped at E2")
        level = 2
    if str(ev.get("outcome_type", "")).lower() == "outputs_only":
        if level > 2:
            caps.append("measures outputs, not outcomes, capped at E2")
        level = min(level, 2)
    if ev.get("program_matches") is False:
        caps.append("evaluates a different program, not counted")
        level = 1

    flags = []
    if outcome_grounded is False:
        flags.append("outcome sentence not found word for word in the evaluation")
    if model_level != level:
        flags.append(f"model said {label(model_level)}, code set {label(level)}")
    ev.update({"level": level, "code_level": code_level, "model_level": model_level,
               "independent_checked": independent, "caps": caps, "flags": flags})
    return ev


def combine(evaluations: list[dict[str, Any]]) -> dict[str, Any]:
    """The approach's level across its graded evaluations: the best single level,
    raised to E5 when two or more E4 evaluations cover different countries. Also
    whether E3 or better is replicated in Africa (two or more such evaluations with an
    African country), which the Adopt gate uses."""
    counted = [e for e in evaluations if e.get("program_matches") is not False]
    best = max([e.get("level", 1) for e in counted] or [1])
    rct_countries = [frozenset(c.strip().lower() for c in (e.get("countries") or []))
                     for e in counted if e.get("level", 1) >= 4]
    rct_countries = [c for c in rct_countries if c]
    disjoint = any(a.isdisjoint(b) for i, a in enumerate(rct_countries) for b in rct_countries[i + 1:])
    if best == 4 and disjoint:
        best = 5
    africa_e3 = [e for e in counted if e.get("level", 1) >= 3 and is_african(e.get("countries") or [])]
    return {"level": best, "label": label(best), "replicated_in_africa": len(africa_e3) >= 2,
            "evaluations": counted}


def allowed_postures(level: int, replicated_in_africa: bool, gates: dict[str, Any]) -> list[str]:
    """The postures an option may carry at this evidence level, best first.
    gates = {"adopt": {"min": 4, "or_replicated_africa_min": 3}, "adapt": {"min": 3},
             "watch": {"min": 1}}"""
    out = []
    for posture, g in gates.items():
        ok = level >= int(g.get("min", 1))
        alt = g.get("or_replicated_africa_min")
        if not ok and alt is not None and replicated_in_africa and level >= int(alt):
            ok = True
        if ok:
            out.append(posture)
    return out


def best_posture(level: int, replicated_in_africa: bool, gates: dict[str, Any]) -> str:
    allowed = allowed_postures(level, replicated_in_africa, gates)
    return allowed[0] if allowed else list(gates)[-1]


def cap_posture(proposed: str, level: int, replicated_in_africa: bool, gates: dict[str, Any]) -> str:
    """The model's proposed posture if the evidence allows it, else the best one the
    evidence does allow. Never promotes."""
    order = list(gates)
    allowed = allowed_postures(level, replicated_in_africa, gates)
    if proposed in allowed:
        return proposed
    best = allowed[0] if allowed else order[-1]
    if proposed in order and order.index(proposed) > order.index(best):
        return proposed
    return best


def entry_allowed(level: int, african: bool | None, geo: dict[str, Any]) -> bool:
    """Africa first: an African (or unplaced) program enters at the African minimum,
    a program outside Africa only at the higher minimum."""
    if african is False:
        return level >= int(geo.get("non_africa_min", 3))
    return level >= int(geo.get("africa_min", 1))
