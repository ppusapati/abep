"""Experimental decision package (fo_experiment_package; docs/architecture_comparison/experiment_package/).

Checks that the package reproduces byte for byte from its pinned inputs, validates against its schema, carries a unit,
evidence class and source for every number, stays a DRAFT (nothing locked or decided), names no preferred architecture
and eliminates none (lane-24 evaluator templates), leaves the valve-outlet feed state and the compressor bus draw TBD,
covers every lane-25 measurement / decisive quantity / open owner question, and refuses missing or changed inputs.
"""
from __future__ import annotations

import importlib.util
import json
import re
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PKG_DIR = ROOT / "docs" / "architecture_comparison" / "experiment_package"
SCRIPT = PKG_DIR / "build_experiment_package.py"


def _load_builder():
    spec = importlib.util.spec_from_file_location("_test_exppkg_builder", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


B = _load_builder()
PKG = B.build()
STORED = json.loads((PKG_DIR / "experiment_package_v1.json").read_text(encoding="utf-8"))


def test_reproduces_byte_for_byte():
    assert (PKG_DIR / "experiment_package_v1.json").read_text(encoding="utf-8") == B.dumps(PKG)
    assert (PKG_DIR / "EXPERIMENT_PACKAGE.md").read_text(encoding="utf-8") == B.render_md(PKG)
    assert B.main(["--check"]) == 0


def test_schema_and_number_discipline():
    B.validate(STORED)                                    # schema + numeric-leaf + forbidden-pattern checks
    assert B.numeric_leaf_errors(STORED) == []
    bad = json.loads(json.dumps(STORED))
    bad["decisions"][0]["options"][0]["loose_number"] = 0.3
    assert B.numeric_leaf_errors(bad)


def test_draft_status_nothing_locked():
    assert STORED["status"] == "DRAFT_PENDING_OWNER"
    for d in STORED["decisions"]:
        assert d["status"] == "OPEN_OWNER_DECISION"
        assert d["recommendation"]["status"] == "PROPOSED"
        assert d["recommendation"]["option"] in {o["id"] for o in d["options"]}
    assert STORED["reconciliation"]["status"] == "PROPOSED"


def test_no_winner_no_elimination():
    text = json.dumps(STORED)
    for pat in B.FORBIDDEN_PATTERNS:
        assert not re.search(pat, text), pat
    templates = STORED["hard_gate_context"]["outcome_templates"]["templates"]
    assert {t["architecture"] for t in templates} == {"hall_only", "rf_hall", "ecr_hall"}
    assert all(t["evaluator_eliminated"] is False for t in templates)
    assert STORED["hard_gate_context"]["current_status"]["eliminated"] == []
    for row in STORED["traceability"]["rows"]:
        for h in row["hard_gates"]:
            assert h["can_eliminate_from_minimum_experiment"] is False


def test_feed_state_and_compressor_stay_tbd():
    whats = {t["what"] for t in STORED["tbd_register"]}
    assert "compressor bus draw per operating point" in whats
    assert any(w.startswith("valve-outlet feed state") for w in whats)
    blockers = {b for t in STORED["tbd_register"] for b in t["blocked_by"]}
    assert any(b.startswith("lane_33_upstream_icd") for b in blockers)
    assert any(b.startswith("lane_16_feed_envelope") for b in blockers)
    # no number object claims to be a compressor draw or a feed-state value
    def walk(o, path=""):
        if isinstance(o, dict):
            if "value" in o and isinstance(o["value"], (int, float)) and not isinstance(o["value"], bool):
                assert "compressor" not in path.lower() and "p_feed" not in path.lower(), path
            for k, v in o.items():
                walk(v, f"{path}.{k}")
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f"{path}[{i}]")
    walk(STORED)


def test_coverage_of_lane25_measurements_and_open_questions():
    draft = json.loads((ROOT / B.INPUTS["minexp_draft"][0]).read_text(encoding="utf-8"))
    rows = STORED["traceability"]["rows"]
    assert {m for r in rows for m in r["measurement"]["lane25"]} == {m["id"] for m in draft["measurements"]}
    assert {q for r in rows for q in r["measurement"]["quantities"]} == {q["id"] for q in draft["decisive_quantities"]}
    refs = {x for d in STORED["decisions"] for x in d["source"].get("lane_25_open_decision", [])}
    assert len(refs) == len(draft["open_owner_decisions"])
    assert STORED["traceability"]["M_PREION_nodes_not_traced"] == []
    titles = " ".join(d["title"] for d in STORED["decisions"])
    for key in ("T-BUDGET-SHARES", "STOP-MARGIN", "P_lo", "T-ISO-INTERP", "LOCK-1 / LOCK-2"):
        assert key in titles, key


def test_consequences_use_lane25_tools():
    d01 = next(d for d in STORED["decisions"] if d["id"] == "D-01")
    eq = d01["options"][0]["consequences"]["statistics_and_targets"]
    draft = json.loads((ROOT / B.INPUTS["minexp_draft"][0]).read_text(encoding="utf-8"))
    for n, row in draft["derived_numbers"]["plan_by_n"].items():
        assert eq[n]["k_primary"]["value"] == pytest.approx(row["k_primary"]["value"], rel=1e-7)
        assert eq[n]["u_T_max"]["value"] == pytest.approx(row["u_T_max"]["value"], rel=1e-7)
    d03 = next(d for d in STORED["decisions"] if d["id"] == "D-03")
    a, b = (o["consequences"]["readings"]["hall_on_readings_if_both_arms_stop_at_subset"]["value"]
            for o in d03["options"])
    assert b > a
    d02 = next(d for d in STORED["decisions"] if d["id"] == "D-02")
    assert all(g["stop_margin_subset_of_sign_form"] for g in d02["grid_comparison"])


def test_missing_or_changed_input_raises(tmp_path):
    key = "minexp_draft"
    rel, lane, sha = B.INPUTS[key]
    pins = {key: (rel, lane, sha)}
    with pytest.raises(FileNotFoundError):
        B.verify_inputs(tmp_path, pins)
    dst = tmp_path / rel
    dst.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / rel, dst)
    B.verify_inputs(tmp_path, pins)                        # identical copy passes
    dst.write_bytes(dst.read_bytes() + b" ")
    with pytest.raises(B.InputChanged):
        B.verify_inputs(tmp_path, pins)


def test_every_input_pinned_with_lane():
    for key, (rel, lane, sha) in B.INPUTS.items():
        assert lane and re.fullmatch(r"[0-9a-f]{64}", sha), key
        assert B.sha256_file(ROOT / rel) == sha, key
    assert [i["path"] for i in STORED["inputs"]] == [v[0] for v in B.INPUTS.values()]
