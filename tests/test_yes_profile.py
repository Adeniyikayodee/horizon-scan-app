"""B6: the YES profile loads, runs end to end in test mode, and keeps its rules."""
from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
from pathlib import Path

from openpyxl import load_workbook

from scan import config, io_xlsx, pipeline, spec

PROFILE = Path(__file__).resolve().parent.parent / "profiles" / "yes"


def test_profile_is_complete():
    sp = json.loads((PROFILE / "profile.json").read_text())
    assert len(sp["themes_seed"]) == 10
    assert [c["key"] for c in sp["criteria"]][:3] == ["evidence_strength", "outcome_relevance", "acet_role"]
    assert sp["evidence"]["score_key"] == "evidence_strength"
    assert sp["memo"]["min_words"] < sp["brief_checks"]["target_words"] < sp["memo"]["max_words"]
    for f in ("themes.md", "output_spec.md", "policy.md", "exemplar.md"):
        assert (PROFILE / "context" / f).exists()
    orgs = io_xlsx.read_orgs(PROFILE / "organizations.xlsx")
    assert len(orgs) == 40 and all(o.get("website", "").startswith("https://") for o in orgs)


def test_evidence_mark_is_set_from_the_level():
    appr = {"score": {"evidence_strength": "strong", "reason_evidence_strength": "model"}}
    pipeline._set_evidence_mark(appr, {"level": 2, "label": "E2", "best": {"title": "Tracer study"}},
                                {"score_key": "evidence_strength"})
    assert appr["score"]["evidence_strength"] == "weak"
    assert appr["score"]["reason_evidence_strength"] == "Set from the evidence level, E2: Tracer study."


def test_press_cannot_verify(monkeypatch):
    monkeypatch.setattr(config, "SPEC", {"unverifiable_source_types": ["press"]})
    row = {"source_type": "press", "verification": {"status": "verified", "note": ""}}
    pipeline._hold_unverifiable_source(row)
    assert row["verification"]["status"] == "partial"


def test_yes_dry_run_end_to_end(monkeypatch):
    base = Path(tempfile.mkdtemp(prefix="yes-dry-"))
    pdir = base / "profiles" / "yes"
    shutil.copytree(PROFILE, pdir, ignore=shutil.ignore_patterns("run"))
    monkeypatch.setattr(config, "PROFILES_DIR", base / "profiles")
    monkeypatch.setattr(config, "ROOT", base)
    for k in ("SPEC", "WORK_DIR", "ORGS_WORK", "REVIEW_DIR", "OUT_DIR", "MANIFEST", "ORG_SHEET", "DRY_RUN"):
        monkeypatch.setattr(config, k, getattr(config, k))
    config.DRY_RUN = True
    config.use_profile("yes")
    asyncio.run(pipeline.run_stage1())
    asyncio.run(pipeline.run_stage2())
    out = config.OUT_DIR
    assert (out / "yes_scan_brief.md").exists() and (out / "yes_scan_brief.docx").exists()
    wb = load_workbook(out / "program_design_options.xlsx")
    assert wb.sheetnames == ["Options", "Funder map"]
    rows = list(wb["Options"].iter_rows(values_only=True))
    header = rows[0]
    themes = {r[header.index("Theme")] for r in rows[1:]}
    allowed = {t["name"] for t in config.active_spec()["themes_seed"]} | {None, ""}
    assert themes <= allowed, "every option sits in a theme from the fixed list, or awaits review"
    postures = {r[header.index("Posture")] for r in rows[1:]}
    assert postures <= {"adopt", "adapt", "watch"}
    # nothing in test mode can be grounded, so nothing may read above watch
    assert postures == {"watch"}
    assert len(list(wb["Funder map"].iter_rows())) - 1 == 21
    assert not (out / "theme_scorecard.xlsx").exists()
