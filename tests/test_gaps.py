"""The gap scan's own rules: coverage read as coverage, a thin area kept rather than
dropped, and every gap checked against the material the scan read."""
from __future__ import annotations

from scan import coverage, ladder, pipeline

GATES = {"use": {"min": 4}, "scope": {"min": 3, "max": 3}, "commission": {"max": 2}}
MERIT = {"adopt": {"min": 4, "or_replicated_africa_min": 3}, "adapt": {"min": 3}, "watch": {"min": 1}}


def test_a_banded_gate_maps_each_level_to_one_posture():
    assert [ladder.best_posture(lv, False, GATES) for lv in (1, 2, 3, 4, 5)] == [
        "commission", "commission", "scope", "use", "use"]
    assert ladder.banded(GATES) and not ladder.banded(MERIT)
    # the merit gates are untouched: the horizon scan still reads the level as merit
    assert [ladder.best_posture(lv, False, MERIT) for lv in (1, 3, 5)] == ["watch", "adapt", "adopt"]


def test_a_theme_takes_the_posture_its_coverage_earns():
    rows = [{"name": "A", "evidence_record": {"level": 1}}, {"name": "B", "evidence_record": {"level": 3}}]
    themes = [{"name": "T", "members": ["A", "B"], "posture": "use"}]
    pipeline.apply_posture_gates(rows, themes, GATES)
    # the model asked for use; the best-covered member carries E3, so the code says scope
    assert themes[0]["posture"] == "scope" and themes[0]["evidence_level"] == "E3"
    assert [r["posture"] for r in rows] == ["commission", "scope"]


def test_a_thin_area_is_kept_when_it_names_an_open_question():
    cfg = {"entry_rule": "gap", "geography": {"africa_min": 2, "non_africa_min": 3}}
    thin = {"level": 1, "label": "E1", "african": True}
    assert pipeline._entry_check({"open_questions": "not found", "level_of_view": "one project"}, thin, cfg)
    assert not pipeline._entry_check(
        {"open_questions": "Whether the gains hold at national scale is untested.",
         "level_of_view": "one project"}, thin, cfg)
    assert not pipeline._entry_check({"open_questions": "not found", "level_of_view": "the national system"},
                                     thin, cfg)
    # the proven-design rule is unchanged: thin evidence is still held back there
    assert pipeline._entry_check({"open_questions": "Something is open."}, thin,
                                 {"geography": {"africa_min": 2}})


def test_a_gap_must_rest_on_the_material_or_the_map():
    rows = [{"name": "A", "what": "A training program.", "quotes": [],
             "open_questions": "The report says the effect on earnings at scale remains unknown."}]
    themes = [{"name": "T", "members": ["A"]}]
    cov = [{"theme": "T", "Ghana": "E4", "Niger": ""}]
    gaps = [
        {"theme": "T", "basis": "stated", "question": "q1",
         "quote": "the effect on earnings at scale remains unknown"},
        {"theme": "T", "basis": "stated", "question": "q2", "quote": "young people prefer shorter courses"},
        {"theme": "T", "basis": "coverage", "question": "q3", "countries_missing": ["Niger"]},
        {"theme": "T", "basis": "coverage", "question": "q4", "countries_missing": ["Ghana"]},
        {"theme": "Not a theme here", "basis": "coverage", "question": "q5", "countries_missing": ["Niger"]},
    ]
    out = pipeline.ground_gaps(gaps, rows, cov, themes)
    assert [g["grounded"] for g in out] == [True, False, True, False, False]
    assert "not in the material" in out[1]["ground_note"]


def test_the_coverage_map_says_where_the_scan_found_nothing():
    rows = [{"name": "A", "countries": "Ghana; Uganda", "evidence_record": {"level": 4},
             "level_of_view": "the national system", "inclusion": "young women", "open_questions": "not found"},
            {"name": "B", "countries": "Colombia", "evidence_record": {"level": 3},
             "level_of_view": "one project", "inclusion": "not found",
             "open_questions": "Whether it transfers is untested."}]
    themes = [{"name": "T", "posture": "scope", "members": ["A", "B"]}]
    g = coverage.grid(rows, themes, ["Ghana", "Niger", "Uganda"])[0]
    assert g["Ghana"] == "E4" and g["Uganda"] == "E4" and g["Niger"] == ""
    assert g["Elsewhere"] == "E3" and g["Countries with nothing"] == 1
    assert g["Looks at a whole system"] == 1 and g["Speaks to inclusion"] == 1
    assert g["Names an open question"] == 1
    assert coverage.as_rows([g], ["Ghana", "Niger", "Uganda"])[0][:4] == ["T", "scope", 2, "E4"]


def test_the_map_reads_against_the_institute_s_own_study():
    rows = [{"name": "A", "countries": "Ghana", "evidence_record": {"level": 4}},
            {"name": "B", "countries": "Nigeria", "evidence_record": {"level": 2}}]
    themes = [{"name": "T", "posture": "commission", "members": ["A", "B"]}]
    nine = ["Côte d'Ivoire", "Ethiopia", "Ghana", "Niger", "Rwanda", "Uganda", "Nigeria", "Kenya", "South Africa"]
    six = nine[:6]
    g = coverage.grid(rows, themes, nine, six)[0]
    # Ghana is the only one of the study's six with anything in it
    assert g["Study countries covered"] == 1 and g["Study countries with nothing"] == 5
    assert g["Countries with nothing"] == 7
    cols = coverage.columns(nine, six)
    assert "Study countries with nothing" in cols
    assert coverage.as_rows([g], nine, six)[0][cols.index("Study countries covered")] == 1
    # without a study named, the map keeps its plain shape
    assert "Study countries covered" not in coverage.columns(nine)
