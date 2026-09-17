"""B2: windows per source tier and a fixed theme list, both enforced in code."""
from __future__ import annotations

import pytest

from scan import config, io_xlsx, pipeline, spec

TIERS = {
    "program": {"from": 2023, "to": 2026, "label": "Program pages and reports"},
    "evaluation": {"from": 2015, "to": 2026, "label": "Independent evaluations",
                   "note": "Evaluations take years."},
}
SEED = [{"name": "TVET at secondary level", "relation": "current"},
        {"name": "Financing education", "relation": "interest"}]


@pytest.fixture
def profile():
    before = config.SPEC
    config.SPEC = {**spec.DEFAULT_SPEC, "profile": "yes", "windows": TIERS, "themes_seed": SEED,
                   "max_extra_themes": 1, "extra_min_members": 3}
    yield config.SPEC
    config.SPEC = before


def test_horizon_window_unchanged():
    before, config.SPEC = config.SPEC, None
    try:
        assert config.window() == (config.YEAR_MIN, config.YEAR_MAX)
        assert config.window("evaluation") == (config.YEAR_MIN, config.YEAR_MAX)
        assert config.window_rule().startswith("# Standing hard rule")
        assert f"The recency window is {config.YEAR_MIN} to {config.YEAR_MAX}" in config.window_rule()
    finally:
        config.SPEC = before


def test_windows_per_tier(profile):
    assert config.window("program") == (2023, 2026)
    assert config.window("evaluation") == (2015, 2026)
    assert pipeline._out_of_window(2018, "program")
    assert not pipeline._out_of_window(2018, "evaluation")
    assert not pipeline._out_of_window(None, "program")
    rule = config.window_rule()
    assert "Program pages and reports: published or updated from 2023 to 2026." in rule
    assert "Independent evaluations: published or updated from 2015 to 2026. Evaluations take years." in rule


def test_seed_names_and_relation_come_from_the_profile(profile):
    themes = [{"name": "tvet at secondary level!", "tag": "new", "members": ["a"]},
              {"name": "Financing Education", "tag": "current", "members": ["b"]}]
    out, unplaced = spec.enforce_theme_seed(themes, profile)
    assert [(t["name"], t["tag"]) for t in out] == [
        ("TVET at secondary level", "current"), ("Financing education", "interest")]
    assert unplaced == []


def test_seed_merges_duplicates(profile):
    themes = [{"name": "TVET at secondary level", "members": ["a", "b"]},
              {"name": "TVET at Secondary Level", "members": ["b", "c"]}]
    out, _ = spec.enforce_theme_seed(themes, profile)
    assert len(out) == 1 and out[0]["members"] == ["a", "b", "c"]


def test_extra_theme_needs_members_and_a_free_slot(profile):
    themes = [{"name": "Green jobs", "tag": "current", "members": ["a", "b", "c", "d"]},
              {"name": "Sports for jobs", "members": ["e", "f", "g"]},
              {"name": "Tiny", "members": ["h"]}]
    out, unplaced = spec.enforce_theme_seed(themes, profile)
    assert [(t["name"], t["tag"]) for t in out] == [("Green jobs", "new")]
    assert sorted(u["name"] for u in unplaced) == ["Sports for jobs", "Tiny"]


def test_no_seed_passes_through():
    themes = [{"name": "Anything", "members": []}]
    assert spec.enforce_theme_seed(themes, spec.DEFAULT_SPEC) == (themes, [])


def test_unplaced_written_for_review(profile, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "REVIEW_DIR", tmp_path)
    p = io_xlsx.write_theme_screen([], [{"name": "Tiny", "members": ["h"]}])
    text = p.read_text()
    assert "Outside the fixed theme list" in text and "- Tiny: h" in text
    assert "Outside the fixed theme list" not in io_xlsx.write_theme_screen([], []).read_text()
