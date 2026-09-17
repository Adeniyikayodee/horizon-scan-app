"""The quarterly (horizon) scan must not move while the engine is refactored.

A dry run records every model call the agents make (model, frame, user message,
schema, web, effort, tier, max_tokens) and every artifact the run writes, then
compares both against a snapshot taken on the code before the refactor. Prompts
are the agents' behavior, so an unchanged prompt set plus unchanged outputs is
the proof that the horizon scan still does exactly what it did.

Regenerate ONLY on purpose:  SNAPSHOT_UPDATE=1 python -m pytest -q tests/test_horizon_snapshot.py
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import tempfile
from pathlib import Path

from openpyxl import load_workbook

from scan import agents, config, io_xlsx, pipeline, spec

SNAP = Path(__file__).parent / "snapshots" / "horizon"
_DATE = re.compile(r"\b(January|February|March|April|May|June|July|August|September|October|"
                   r"November|December) \d{1,2}, \d{4}\b|\b\d{4}-\d{2}-\d{2}\b")


def _norm(obj):
    return json.loads(_DATE.sub("<DATE>", json.dumps(obj, ensure_ascii=False, sort_keys=True)))


def _cells(path: Path) -> list:
    wb = load_workbook(path)
    return {ws.title: [[("" if v is None else v) for v in r] for r in ws.iter_rows(values_only=True)]
            for ws in wb.worksheets}


def _isolate() -> Path:
    base = Path(tempfile.mkdtemp(prefix="scan-snapshot-"))
    config.WORK_DIR = base / "work"
    config.ORGS_WORK = config.WORK_DIR / "orgs"
    config.REVIEW_DIR = base / "review"
    config.OUT_DIR = base / "out"
    config.INPUT_DIR = base / "input"
    config.MANIFEST = config.WORK_DIR / "manifest.json"
    config.ORG_SHEET = config.INPUT_DIR / "organizations.xlsx"
    for d in (config.ORGS_WORK, config.REVIEW_DIR, config.OUT_DIR, config.INPUT_DIR):
        d.mkdir(parents=True, exist_ok=True)
    return base


def _run() -> dict:
    config.DRY_RUN = True
    config.SPEC = None
    config.SCAN_MODE = "africa"
    _isolate()
    io_xlsx.write_sample_orgs()

    calls: list[dict] = []
    original = agents.structured_call

    async def recorder(**kw):
        calls.append({k: kw.get(k) for k in
                      ("model", "frame", "user", "schema", "web", "effort", "tier", "max_tokens")})
        return await original(**kw)

    agents.structured_call = recorder
    try:
        asyncio.run(pipeline.run_stage1())
        asyncio.run(pipeline.run_stage2())
    finally:
        agents.structured_call = original
        config.SPEC = None

    calls = sorted(calls, key=lambda c: json.dumps(c, sort_keys=True, ensure_ascii=False))
    out = {
        "calls": calls,
        "longlist_full": json.loads((config.WORK_DIR / "longlist_full.json").read_text()),
        "spec": json.loads((config.WORK_DIR / "spec.json").read_text()),
        "longlist": _cells(config.REVIEW_DIR / "longlist.xlsx"),
        "open_questions": (config.REVIEW_DIR / "open_questions.md").read_text(),
        "hunches": (config.REVIEW_DIR / "hunches.md").read_text(),
        "theme_screen": (config.REVIEW_DIR / "theme_screen.md").read_text(),
        "scorecard": _cells(config.OUT_DIR / "theme_scorecard.xlsx"),
        "map": _cells(config.OUT_DIR / "innovation_map.xlsx"),
        "memo": (config.OUT_DIR / "synthesis_memo.md").read_text(),
    }
    return _norm(out)


def test_horizon_unchanged() -> None:
    got = _run()
    SNAP.mkdir(parents=True, exist_ok=True)
    if os.environ.get("SNAPSHOT_UPDATE") == "1":
        for k, v in got.items():
            (SNAP / f"{k}.json").write_text(json.dumps(v, ensure_ascii=False, indent=1, sort_keys=True))
        return
    for k, v in got.items():
        want = json.loads((SNAP / f"{k}.json").read_text())
        assert v == want, f"horizon scan changed: {k}"
