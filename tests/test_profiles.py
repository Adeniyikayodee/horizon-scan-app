"""B1: scan-specific rules live in the profile, with the horizon scan as default."""
from __future__ import annotations

import json

import pytest

from scan import agents, config, pipeline, spec

YES_LIKE = {
    "profile": "yes",
    "criteria": [
        {"key": "evidence_strength", "name": "Evidence strength", "definition": "d", "weight": 2},
        {"key": "inclusion", "name": "Inclusion", "definition": "d", "weight": 1},
    ],
    "postures": ["adopt", "adapt", "watch"],
    "tags": ["current", "interest", "new"],
    "fallback": {"posture": "watch", "tag": "new"},
    "portfolio_mode": "baseline",
    "drop_bands": [],
    "lead": {"count": 5, "postures": ["adopt", "adapt"], "tags": ["current", "interest", "new"]},
    "prompts": {"scout": "YES SCOUT"},
}


@pytest.fixture
def yes_spec():
    before = config.SPEC
    config.SPEC = json.loads(json.dumps(YES_LIKE))
    yield config.SPEC
    config.SPEC = before


def test_default_spec_sets_no_profile_keys():
    for k in ("profile", "prompts", "postures", "tags", "portfolio_mode", "drop_bands", "lead",
              "posture_text", "portfolio_text", "fallback", "context_dir"):
        assert k not in spec.DEFAULT_SPEC, k


def test_horizon_defaults():
    sp = spec.DEFAULT_SPEC
    assert spec.profile_name(sp) == "horizon"
    assert spec.postures(sp) == ["enter", "watch", "deepen"]
    assert spec.tags(sp) == ["existing", "adjacent", "new"]
    assert spec.portfolio_mode(sp) == "exclude"
    assert spec.drop_bands(sp) == ["maturing"]
    assert spec.lead_rule(sp) == {"count": 2, "postures": ["enter"], "tags": ["new", "adjacent"]}
    assert spec.prompt(sp, "scout", "X") == "X"


def test_profile_prompt_reaches_the_agent(yes_spec):
    assert agents._i("scout", agents.SCOUT_I) == "YES SCOUT"
    assert agents._i("reader", agents.READER_I) == agents.READER_I


def test_themes_schema_follows_profile(yes_spec):
    item = spec.themes_schema(yes_spec)["properties"]["themes"]["items"]["properties"]
    assert item["posture"]["enum"] == ["adopt", "adapt", "watch"]
    assert item["tag"]["enum"] == ["current", "interest", "new"]


def test_profile_coerce_falls_to_cautious_values(yes_spec):
    t = spec.coerce_theme({"name": "n", "tag": "existing", "posture": "enter"}, yes_spec)
    assert (t["tag"], t["posture"]) == ("new", "watch")
    swapped = spec.coerce_theme({"name": "n", "tag": "adopt", "posture": "current"}, yes_spec)
    assert (swapped["tag"], swapped["posture"]) == ("current", "adopt")


def test_baseline_mode_screens_nothing(yes_spec):
    themes = [{"name": "TVET at secondary level", "tag": "current", "posture": "adopt",
               "rationale": "youth employment and tvet skills development", "members": []}]
    out = spec.screen_existing(themes, yes_spec)
    assert out[0]["tag"] == "current" and out[0]["posture"] == "adopt"
    assert "screened" not in out[0]


def test_lead_rule_picks_up_to_count(yes_spec):
    themes = [{"name": f"T{i}", "tag": "current", "posture": p, "evidence_strength": "strong",
               "inclusion": "partial"} for i, p in enumerate(["adopt"] * 4 + ["adapt"] * 2 + ["watch"])]
    chosen = pipeline._apply_top2(themes)
    assert len(chosen) == 5 and "T6" not in chosen


def test_auditor_sees_profile_criteria(yes_spec):
    line = agents._scores_line({"evidence_strength": "strong", "inclusion": "weak", "overall": "high"})
    assert line == "Evidence strength strong, Inclusion weak, overall high"


def test_auditor_line_unchanged_for_horizon():
    before, config.SPEC = config.SPEC, None
    try:
        line = agents._scores_line({"mandate_fit": "strong", "research_to_policy": "partial",
                                    "african_traction": "weak", "white_space": "strong", "overall": "high"})
    finally:
        config.SPEC = before
    assert line == "mandate strong, policy partial, traction weak, white space strong, overall high"


def test_use_profile_loads_and_isolates_paths(tmp_path, monkeypatch):
    pdir = tmp_path / "profiles" / "demo"
    pdir.mkdir(parents=True)
    (pdir / "profile.json").write_text(json.dumps({"research_question": "q"}))
    monkeypatch.setattr(config, "PROFILES_DIR", tmp_path / "profiles")
    for k in ("SPEC", "WORK_DIR", "ORGS_WORK", "REVIEW_DIR", "OUT_DIR", "MANIFEST", "ORG_SHEET"):
        monkeypatch.setattr(config, k, getattr(config, k))
    config.use_profile("demo")
    assert config.SPEC["profile"] == "demo"
    assert config.WORK_DIR == pdir / "run" / "work"
    assert config.ORG_SHEET == pdir / "organizations.xlsx"
    assert config.OUT_DIR.is_dir()


def test_use_profile_horizon_is_a_no_op(monkeypatch):
    monkeypatch.setattr(config, "SPEC", None)
    work = config.WORK_DIR
    config.use_profile("horizon")
    config.use_profile(None)
    assert config.SPEC is None and config.WORK_DIR == work


def test_unknown_profile_stops(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROFILES_DIR", tmp_path)
    with pytest.raises(SystemExit):
        config.use_profile("nope")


def test_both_scans_route_the_same_way(monkeypatch):
    """Tiered routing belongs to the engine, so the horizon scan and the YES scan each
    get the same model for the same step."""
    import json as _json
    from pathlib import Path
    from scan import client
    monkeypatch.setattr(config, "CLI_ROUTE_MODE", "tiered")
    monkeypatch.setattr(config, "SPEC", None)
    horizon = {s: client.cli_route(s) for s in ("scout", "reader", "scorer", "themer", "synthesizer")}
    yes = _json.loads((Path(__file__).resolve().parent.parent / "profiles" / "yes" / "profile.json").read_text())
    monkeypatch.setattr(config, "SPEC", yes)
    assert {s: client.cli_route(s) for s in horizon} == horizon
    assert horizon["reader"][0] == "claude-opus-5" and horizon["scorer"][0].startswith("claude-haiku")
