"""Structural checks for the wall-erosion / life evidence database (docs/evidence/wall_life/sputter_yield_db_v1.json).

The database is evidence only (not wired into any model). These tests keep it honest: it parses, every yield entry names its
projectile, target, energy range, source and evidence class, every transcribed value sits inside the declared energy range,
and the non-validation statements that gate its use (solver wall flux, screening candidates, no design life) stay present.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "docs" / "evidence" / "wall_life" / "sputter_yield_db_v1.json"
MD_PATH = ROOT / "docs" / "evidence" / "wall_life" / "WALL_LIFE_EVIDENCE.md"

EVIDENCE_CLASSES = {"measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed"}
REQUESTED_PROJECTILES = {"N+", "N2+", "O+", "O2+", "Xe+"}
REQUESTED_TARGETS = {"BN", "BN-SiO2", "SiC", "Al2O3"}
COVERAGE_STATUSES = {"measured_transcribed", "measured_values_TBD", "model_proxy_only", "none_located"}


@pytest.fixture(scope="module")
def db() -> dict:
    with DB_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def _num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def test_json_parses_and_has_top_level_sections(db):
    for key in ("id", "version", "date", "status", "sources", "entries", "extrapolation_policy", "hard_statements",
                "coverage_matrix", "gaps", "hardware_tests_required"):
        assert key in db, key
    assert db["id"] == "sputter_yield_db_v1"
    assert db["entries"], "database has no yield entries"


def test_every_entry_has_required_fields(db):
    source_ids = {s["id"] for s in db["sources"]}
    ids = [e.get("id") for e in db["entries"]]
    assert all(ids) and len(ids) == len(set(ids)), "entry ids must be present and unique"
    for e in db["entries"]:
        tag = e["id"]
        assert isinstance(e.get("projectile"), str) and e["projectile"].strip(), f"{tag}: projectile"
        assert isinstance(e.get("target"), str) and e["target"].strip(), f"{tag}: target"
        srcs = e.get("source")
        assert isinstance(srcs, list) and srcs, f"{tag}: source must be a non-empty list"
        assert set(srcs) <= source_ids, f"{tag}: unknown source id(s) {set(srcs) - source_ids}"
        assert e.get("evidence_class") in EVIDENCE_CLASSES, f"{tag}: evidence_class {e.get('evidence_class')!r}"
        assert e.get("evidence_level") in range(1, 8), f"{tag}: evidence_level must be 1..7 (docs/EVIDENCE.md)"
        er = e.get("energy_range_eV")
        assert isinstance(er, dict), f"{tag}: energy_range_eV"
        if _num(er.get("min")) and _num(er.get("max")):
            assert 0 < er["min"] < er["max"], f"{tag}: energy range must satisfy 0 < min < max"
        else:
            # an unknown range is allowed only when it is said to be TBD and why
            assert isinstance(er.get("tbd"), str) and er["tbd"].strip(), f"{tag}: non-numeric energy range needs a 'tbd' reason"
        for key in ("uncertainty", "applicability_domain", "validation_status", "transformation_chain", "values_status"):
            assert isinstance(e.get(key), str) and e[key].strip(), f"{tag}: {key}"


def test_values_status_matches_data(db):
    for e in db["entries"]:
        if e["values_status"] == "transcribed":
            data = e.get("data")
            assert data and data.get("columns") and data.get("rows"), f"{e['id']}: transcribed entry without data"
            n = len(data["columns"])
            assert all(len(r) == n for r in data["rows"]), f"{e['id']}: ragged data rows"
        else:
            assert e["values_status"].startswith("TBD"), f"{e['id']}: values_status must be 'transcribed' or 'TBD - ...'"
            assert e.get("data") is None, f"{e['id']}: TBD entry must not carry numbers"
            assert "VALUES_TBD" in e.get("extrapolation_flags_for_ABEP", []), f"{e['id']}: TBD entry must be flagged"


def test_transcribed_energies_inside_declared_range(db):
    for e in db["entries"]:
        data = e.get("data")
        if not data or "E_eV" not in data["columns"]:
            continue
        i = data["columns"].index("E_eV")
        lo, hi = e["energy_range_eV"]["min"], e["energy_range_eV"]["max"]
        for row in data["rows"]:
            assert lo <= row[i] <= hi, f"{e['id']}: E = {row[i]} eV outside declared {lo}-{hi} eV"


def test_extrapolation_policy_flags_are_defined_and_used(db):
    flags = db["extrapolation_policy"]["flags"]
    for f in ("E_BELOW_MEASURED", "E_ABOVE_MEASURED", "PROJECTILE_PROXY", "TARGET_PROXY", "MOLECULAR_ION_ASSUMPTION",
              "TEMPERATURE_OUTSIDE_MEASURED", "VALUES_TBD"):
        assert f in flags and flags[f].strip(), f
    assert "OUT_OF_DOMAIN" in db["extrapolation_policy"]["result_status_rule"]
    for e in db["entries"]:
        for used in e.get("extrapolation_flags_for_ABEP", []):
            assert used.split()[0] in flags, f"{e['id']}: undefined flag {used!r}"


def test_hard_statements_present(db):
    hs = db["hard_statements"]
    flux = hs["solver_wall_flux_is_not_an_erosion_prediction"]
    assert "WallSheath" in flux and "NOT a validated erosion prediction" in flux
    sc = hs["screening_candidates_not_for_design_life"]
    assert "sgb-screen-01..09" in sc and "MUST NOT be used for design life" in sc
    assert "No N/O design-life" in hs["no_design_life_from_this_version"]


def test_coverage_matrix_spans_requested_pairs(db):
    cm = db["coverage_matrix"]
    assert REQUESTED_PROJECTILES <= set(cm)
    entry_ids = {e["id"] for e in db["entries"]}
    for p in REQUESTED_PROJECTILES:
        assert REQUESTED_TARGETS <= set(cm[p]), f"{p}: missing requested targets"
        for t, cell in cm[p].items():
            assert cell["status"] in COVERAGE_STATUSES, f"{p}/{t}: status {cell['status']!r}"
            for ref in cell["entries"]:
                assert ref.split(" ")[0] in entry_ids, f"{p}/{t}: unknown entry {ref!r}"
            if cell["status"] == "none_located":
                assert not cell["entries"], f"{p}/{t}: none_located cell lists entries"


def test_no_n_o_projectile_claimed_measured_on_primary_walls(db):
    """Guard against silently promoting proxies: N/O on BN, BN-SiO2 or SiC has no transcribed measured entry."""
    for e in db["entries"]:
        projectiles = {e["projectile"], *e.get("additional_projectiles", [])}
        if projectiles & {"N+", "N2+", "O+", "O2+"} and e["target"] in {"BN", "BN-SiO2", "SiC"}:
            assert not (e["evidence_class"] == "measured" and e["values_status"] == "transcribed"), e["id"]


def test_sources_are_cited_with_access_status(db):
    for s in db["sources"]:
        assert s.get("citation", "").strip(), s["id"]
        assert s.get("access", "").strip(), s["id"]
        assert s.get("evidence_level") in range(1, 8), s["id"]
        if "sha256" in s:
            assert len(s["sha256"]) == 64 and all(c in "0123456789abcdef" for c in s["sha256"]), s["id"]


def test_hardware_tests_and_gaps_listed(db):
    assert len(db["hardware_tests_required"]) >= 5
    assert len(db["gaps"]) >= 5
    for h in db["hardware_tests_required"]:
        assert h["id"] and h["test"] and h["measure"] and h["why"]


def test_companion_document_exists_and_points_back():
    text = MD_PATH.read_text(encoding="utf-8")
    assert "sputter_yield_db_v1.json" in text
    assert "not a validated erosion prediction" in text


def test_milestone_relevance_declared(db):
    """Operating model section 1: every lane states which question it answers; registry says lane_32 answers (iii)."""
    mr = db["milestone_relevance"]
    assert mr["lane_id"] == "lane_32_wall_life"
    assert mr["answers"] == "iii"
    for key in ("milestone_A", "milestone_B", "milestone_C", "verification_status"):
        assert isinstance(mr.get(key), str) and mr[key].strip(), key
    assert mr["milestone_A"].startswith("NON-DECISIVE")
    assert "single-lens" in mr["verification_status"]
    md = MD_PATH.read_text(encoding="utf-8")
    assert "Milestone A" in md and "(iii)" in md


def test_consumer_requirements_bind_flags_and_crosswalk(db):
    cr = db["consumer_requirements"]
    assert "thermal_life.py" in cr["known_consumer"]
    assert "1e-9" in cr["unit_crosswalk"] and "1.602176634e-19" in cr["unit_crosswalk"]
    joined = " ".join(cr["required_behaviour"])
    assert "NOT_DEMONSTRATED" in joined and "OUT_OF_DOMAIN" in joined
    for flag in db["extrapolation_policy"]["flags"]:
        assert flag in joined, flag
    assert any(g["id"] == "G11" for g in db["gaps"])
