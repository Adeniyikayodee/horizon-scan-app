"""Test-mode replay: it answers from the recorded YES run only when the app asks for it,
and what it answers is the recording, not canned text."""
from __future__ import annotations

import json

import pytest

from scan import config, mock, replay, schemas

pytestmark = pytest.mark.skipif(not replay.available(), reason="no recorded run fixture")


@pytest.fixture
def yes_replay(monkeypatch):
    prof = json.loads((config.PROFILES_DIR / "yes" / "profile.json").read_text(encoding="utf-8"))
    prof["profile"] = "yes"
    monkeypatch.setattr(config, "SPEC", prof)
    monkeypatch.setattr(config, "DRY_RUN", True)
    monkeypatch.setattr(config, "REPLAY", True)


def test_off_unless_the_app_asks(monkeypatch):
    monkeypatch.setattr(config, "DRY_RUN", True)
    monkeypatch.setattr(config, "REPLAY", False)
    assert not replay.active()
    out = mock.mock_response(schemas.SCOUT_SCHEMA, "Organization: Educate!")
    assert "value-addition initiative" in out["candidates"][0]["name"]      # the plain mock


def test_scout_and_read_come_from_the_recording(yes_replay):
    org = replay.orgs()[0]["name"]
    scout = mock.mock_response(schemas.SCOUT_SCHEMA, f"Organization: {org}")
    assert scout["candidates"]
    first = scout["candidates"][0]["name"]
    row = replay._data()["_row"][first]
    reading = mock.mock_response({"properties": {"keep": {}}}, f"Candidate: {first}\nWhat: x")
    assert reading["keep"] is True and reading["quotes"] == row["quotes"]


def test_quote_checks_never_fetch_in_a_dry_run(yes_replay):
    row = next(r for r in replay._data()["_row"].values() if r.get("quote_grounded") is not None)
    q = row["verification"]["confirming_quote"]
    from scan import sources
    assert sources.quote_grounded(row["url"], q) == row["quote_grounded"]
    assert sources.quote_exact("https://example.com/never-recorded", "a quote that was never checked") is None


def test_an_unrecorded_organization_falls_through(yes_replay):
    out = mock.mock_response(schemas.SCOUT_SCHEMA, "Organization: Not In The Recording")
    assert "value-addition initiative" in out["candidates"][0]["name"]
