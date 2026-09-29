"""B4: the full funder scan. Grounded fields only, no contact details, fit ranked in code."""
from __future__ import annotations

import asyncio

import pytest

from scan import config, funders, io_xlsx, pipeline, sources, spec

CFG = {"roster_types": ["foundation", "mdb", "bilateral", "private sector"], "max_additions": 2,
       "from_postures": ["adopt", "adapt"], "priority_countries": ["Ghana", "Côte d'Ivoire", "Niger", "Kenya"],
       "theme_names": ["TVET at secondary level", "Financing education", "Secondary education"]}


def _field(value, quote="q", url="https://funder.org/strategy"):
    return {"value": value, "quote": quote, "url": url}


def test_list_takes_roster_funders_then_capped_additions():
    roster = [{"name": "Mastercard Foundation", "type": "Foundation"},
              {"name": "LEAP Africa", "type": "CSO"},
              {"name": "African Development Bank (AfDB)", "type": "MDB"}]
    rows = [{"evidence_record": {"posture_allowed": "adopt", "funders": ["AfDB", "Jacobs Foundation"]},
             "funders": "Jacobs Foundation; UNICEF"},
            {"evidence_record": {"posture_allowed": "adapt", "funders": ["UNICEF", "GIZ"]}},
            {"evidence_record": {"posture_allowed": "watch", "funders": ["Watch-only Funder"]}}]
    out = funders.build_list(roster, rows, CFG)
    names = [f["name"] for f in out]
    assert names[:2] == ["Mastercard Foundation", "African Development Bank (AfDB)"]
    assert "LEAP Africa" not in names and "AfDB" not in names, "roster match by acronym"
    assert "Watch-only Funder" not in names
    assert names[2:] == ["UNICEF", "GIZ"], "cap, most-named first, then by name"


def test_ungrounded_fields_become_not_found(monkeypatch):
    monkeypatch.setattr(sources, "quote_exact", lambda url, q: q == "grounded")
    rec = {"name": "F", "strategy": {**_field("Youth strategy", quote="grounded"), "period": "2024-2030"},
           "themes": _field(["TVET at secondary level"], quote="invented"),
           "countries": _field(["Ghana"], quote="grounded"), "instruments": _field(["grants"], quote=""),
           "size": _field("$1 million", quote="invented"), "eligibility": _field("yes", quote="invented"),
           "calls": []}
    g = asyncio.run(funders.ground(rec))
    assert g["strategy"]["value"] == "Youth strategy" and g["countries"]["value"] == ["Ghana"]
    assert g["themes"]["value"] == [] and g["size"]["value"] == "not found"
    assert g["eligibility"]["value"] == "not found" and g["instruments"]["value"] == []
    assert len(g["dropped_fields"]) == 4


def test_contact_details_are_stripped_but_years_and_money_kept():
    s = funders._clean("Contact jane.doe@funder.org or +233 30 123 4567. Strategy 2024-2030, $5,000,000 grants.")
    assert "@" not in s and "4567" not in s
    assert "2024-2030" in s and "$5,000,000" in s


def test_fit_is_ranked_in_code():
    strong = {"name": "Strong", "strategy": {"value": "x", "period": "2024-2030", "grounded": True},
              "themes": {"value": ["TVET at secondary level", "Financing education"]},
              "countries": {"value": ["Ghana", "Cote d'Ivoire", "Kenya", "Niger"]},
              "eligibility": {"value": "yes"}}
    weak = {"name": "Weak", "strategy": {"value": "x", "period": "2019-2023", "grounded": True},
            "themes": {"value": ["Unrelated"]}, "countries": {"value": ["Sub-Saharan Africa"]},
            "eligibility": {"value": "unclear"}}
    ranked = funders.rank([weak, strong], CFG, now_year=2026)
    assert [r["name"] for r in ranked] == ["Strong", "Weak"]
    assert strong["fit"]["points"] == {"themes": 4, "countries": 3, "eligibility": 3, "active": 2}
    assert weak["fit"]["points"] == {"themes": 0, "countries": 1, "eligibility": 1, "active": 0}


def test_cache_keeps_similar_names_apart(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "WORK_DIR", tmp_path)
    assert funders.cache_path("Dangote Foundation") != funders.cache_path("Dangote Group")
    funders.write_cached("Dangote Foundation", {"name": "Dangote Foundation"})
    assert funders.read_cached("Dangote Foundation") == {"name": "Dangote Foundation"}
    assert funders.read_cached("Dangote Group") is None


def test_spec_funder_config_takes_theme_names_from_the_seed():
    sp = {"funders": {"max_additions": 15}, "themes_seed": [{"name": "A", "relation": "current"}]}
    assert spec.funder_config(sp)["theme_names"] == ["A"]
    assert spec.funder_config({}) is None


def test_run_funders_dry_run_caches_and_ranks(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DRY_RUN", True)
    monkeypatch.setattr(config, "WORK_DIR", tmp_path)
    monkeypatch.setattr(config, "INPUT_DIR", tmp_path)
    monkeypatch.setattr(config, "ORG_SHEET", tmp_path / "organizations.xlsx")
    monkeypatch.setattr(config, "SPEC", {**spec.DEFAULT_SPEC, "profile": "yes",
                                         "themes_seed": [{"name": "TVET at secondary level", "relation": "current"}],
                                         "funders": {k: v for k, v in CFG.items() if k != "theme_names"}})
    io_xlsx.write_orgs_list([{"name": "Mastercard Foundation", "type": "Foundation"},
                             {"name": "LEAP Africa", "type": "CSO"}])
    out = asyncio.run(pipeline.run_funders({}, []))
    assert [r["name"] for r in out] == ["Mastercard Foundation"]
    assert out[0]["fit"]["score"] == 0, "dry-run quotes cannot be grounded, so nothing scores"
    assert funders.read_cached("Mastercard Foundation") is not None
    assert (tmp_path / "funders.json").exists()


def test_not_found_is_never_a_funder():
    rows = [{"evidence_record": {"posture_allowed": "adopt", "funders": ["not found"]}, "funders": "Not found."}]
    assert funders.build_list([], rows, CFG) == []


@pytest.mark.parametrize("deadline,passed", [
    ("April 23, 2026", True), ("Spring 2026", True), ("December 1, 2026", False), ("October 2026", False),
    ("2025", True), ("rolling", False), ("", False),
])
def test_expired_calls_are_not_open(deadline, passed):
    from datetime import datetime
    assert funders.deadline_passed(deadline, today=datetime(2026, 9, 17)) is passed
