"""Tests for A9-05 (fo_a9_05_hall_icp_validation_inputs): ICP-neutralizer evidence extraction and the Hall -> ICP
validation-input list.

Pure file checks plus the two deterministic builders; no network, no Julia, fast (< 2 s).
Run: python -m pytest -q tests/test_hall_icp_validation_inputs.py
"""
import importlib.util
import json
import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EV_DIR = os.path.join(ROOT, "docs", "evidence", "icp_neutralizer")
VI_DIR = os.path.join(ROOT, "docs", "experiments", "hall_icp", "validation_inputs")
EV_BUILDER = os.path.join(EV_DIR, "build_icp_neutralizer_evidence.py")
VI_BUILDER = os.path.join(VI_DIR, "build_hall_icp_validation_inputs.py")
EV_JSON = os.path.join(EV_DIR, "icp_neutralizer_evidence_v1.json")
VI_JSON = os.path.join(VI_DIR, "hall_icp_validation_inputs_v1.json")
PIXELS = os.path.join(EV_DIR, "takahashi2024_fig_pixels_v1.json")

A9 = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer.json"
ANSWERS = "docs/decisions/OD_2026_09_29_owner_answers_147.json"
PACK = "docs/decisions/OD_2026_09_29_OWNER_DECISION_PACK_147.md"
EPISTEMIC = {"measured", "digitized", "inferred", "model-derived", "assumed", None}
BASIS = {"reported", "digitized", "derived", "authors_estimate", "not_reported"}
FREEZE_TOKENS = ("NOW", "LOCK-1", "LOCK-2", "after-evidence")


def _load_mod(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def evb():
    return _load_mod(EV_BUILDER, "build_icp_neutralizer_evidence")


@pytest.fixture(scope="module")
def vib():
    return _load_mod(VI_BUILDER, "build_hall_icp_validation_inputs")


@pytest.fixture(scope="module")
def ev():
    with open(EV_JSON, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def vi():
    with open(VI_JSON, encoding="utf-8") as f:
        return json.load(f)


# ---------------- reproducibility and pins ----------------

def test_builders_reproduce_exactly(evb, vib):
    assert evb.check() == []
    assert vib.check() == []


def test_pins_hold(evb, vib):
    assert evb.verify_pins() == []
    assert vib.verify_pins() == []


def test_owner_decisions_pinned(ev, vi):
    for doc in (ev, vi):
        paths = {p["path"] for p in doc["authority_pins"]}
        assert {A9, ANSWERS, PACK} <= paths


def test_governance_never_pinned(ev, vi):
    for doc in (ev, vi):
        pinned = [p["path"] for k in ("authority_pins", "deliverable_pins", "historical_pins") for p in doc.get(k, [])]
        for p in pinned:
            assert "orchestration" not in p
        for g in doc["governance_read_never_pinned"]:
            assert g not in pinned


def test_evidence_input_hash_matches(vi):
    import hashlib
    with open(EV_JSON, "rb") as f:
        assert hashlib.sha256(f.read()).hexdigest() == vi["evidence_input"]["sha256"]


# ---------------- part 1: evidence ----------------

def test_anchor_identity(ev):
    a = ev["anchor"]
    assert a["doi"] == "10.1007/s44205-024-00081-2"
    assert "CC BY-NC-ND 4.0" in a["license"]
    assert re.fullmatch(r"[0-9a-f]{64}", a["retrieval"]["sha256"])
    assert a["retrieval"]["pages"] == 10
    assert "not validation of Vyovrinda hardware" in a["evidence_class"]


def test_pdf_not_committed():
    for d in (EV_DIR, VI_DIR):
        for fn in os.listdir(d):
            assert not fn.lower().endswith((".pdf", ".png", ".jpg"))


def test_extraction_items_have_provenance(ev):
    ids = set()
    for e in ev["extraction"]:
        assert e["id"] not in ids
        ids.add(e["id"])
        assert e["locator"]
        assert e["value_basis"] in BASIS
        assert e["epistemic"] in EPISTEMIC
        if e["value_basis"] == "not_reported":
            assert e["value"] is None and e["evidence_class"] == "not reported"
        else:
            assert e["value"] is not None and e["evidence_class"] == "published analog"
    # the anchor facts the A9 decision relies on
    by = {e["id"]: e for e in ev["extraction"]}
    assert by["TK-20"]["value"] == 13.56 and by["TK-21"]["value"] == 200
    assert by["TK-26"]["value"] == 0.1 and by["TK-24"]["value"] == 0.36
    assert by["TK-60"]["value_basis"] == "not_reported"  # no thrust measured
    assert by["TK-72"]["value_basis"] == "not_reported"  # no life data


def test_digitized_values_follow_pixel_record(ev):
    with open(PIXELS, encoding="utf-8") as f:
        pix = json.load(f)
    assert pix["source_pdf_sha256"] == ev["anchor"]["retrieval"]["sha256"]
    cal = pix["fig4"]["calibration"]["b_y_ID"]
    (p0, p1), (v0, v1) = cal["px"], cal["value"]
    rows = {r["VD_nominal_V"]: r for r in ev["digitized_fig4"]["rows"]}
    m = {x["VD_nominal_V"]: x for x in pix["fig4"]["markers"]}
    top, bot = m[200]["ID_b"]["runs_px"][-1]
    assert rows[200]["ID_A"] == pytest.approx(v0 + (v1 - v0) * ((top + bot) / 2 - p0) / (p1 - p0), abs=1e-3)
    # consistency with the text: I_D 'about 1 A' (p. 8), V_K 'to -100 V' (p. 6), V_max '120-130 V' (p. 6)
    ids = [r["ID_A"] for r in rows.values() if r.get("ID_A") is not None]
    assert 0.8 < max(ids) < 1.2
    assert -110 < rows[260]["VK_V"] < -85
    assert all(115 <= rows[v]["Vmax_V"] <= 132 for v in (180, 200, 220, 240, 260))
    assert rows[220]["ID_occluded"] is True


def test_survey_bounded_and_labelled(ev):
    srcs = ev["survey"]["sources"]
    assert 1 <= len(srcs) <= 8
    for s in srcs:
        assert s["doi"] and s["url"] and s["retrieved_on"]
        acc = s["access"]
        full = acc.startswith("full text")
        assert full or acc.startswith("ABSTRACT-ONLY") or acc.startswith("METADATA-ONLY")
        if full:
            assert re.fullmatch(r"[0-9a-f]{64}", s["sha256"])
        else:
            assert s["sha256"] is None
        for d in s["derived"]:
            assert d["value_basis"] == "derived" and d["formula"]
    by = {s["id"]: s for s in srcs}
    d = {x["value"] for x in by["S-01"]["derived"]}
    assert 15.1 in d and 100.4 in d


def test_lawful_acquisition_list(ev):
    la = ev["lawful_acquisition_list"]
    assert la["owner_answer_row"] == 7
    assert len(la["items"]) >= 5
    assert all("owner-accepted order, A9.1 OQ-EV-02" in x["priority"] for x in la["items"])   # A9-10


def test_analog_vs_hardware_split(ev):
    s = ev["analog_can_bound_vs_hardware_only"]
    assert s["analog_can_bound"] and s["hardware_only"]
    assert any("life" in x for x in s["hardware_only"])


# ---------------- part 2: validation inputs ----------------

REQUIRED_TOPICS = ["VI-RF-02", "VI-RF-03", "VI-RF-05", "VI-EX-01", "VI-EX-03", "VI-EX-07", "VI-HD-01", "VI-GAS-01",
                   "VI-GAS-02", "VI-GAS-03", "VI-SU-01", "VI-SU-03", "VI-LF-01", "VI-LF-05", "VI-RF-10"]


def test_row145_topics_present(vi):
    ids = {i["id"] for i in vi["items"]}
    for t in REQUIRED_TOPICS:
        assert t in ids, t


def test_item_fields_complete(vi, ev):
    ev_ids = {e["id"] for e in ev["extraction"]} | {s["id"] for s in ev["survey"]["sources"]} | \
             {d["id"] for d in ev["survey"]["reused_from_repository"]}
    for it in vi["items"]:
        for k in ("definition", "units", "how_obtained", "producing_stage", "value", "evidence_class", "basis",
                  "source", "status", "freeze_point", "consumers", "analog_bound", "supply"):
            assert it[k] not in (None, ""), (it["id"], k)
        assert any(tok in it["freeze_point"] for tok in FREEZE_TOKENS), it["id"]
        assert set(it["configurations"]) <= {"hall_c1_reference", "hall_icp_neutralizer"}
        for c in it["consumers"]:
            assert c in vi["consumers"]
        for r in it["how_obtained"]["analog_refs"]:
            assert r in ev_ids
        if it["how_obtained"]["route"] != "owner_allocation":
            assert "PENDING docs/experiments/hall_icp/prereg_framework/" in it["producing_stage"]


def test_no_prediction_only_owner_values(vi):
    rows_re = re.compile(r"row \d+")
    for it in vi["items"]:
        v = it["value"]
        if isinstance(v, str) and v.startswith("TBD"):
            continue
        assert it["how_obtained"]["route"] == "owner_allocation", it["id"]
        assert it["evidence_class"] == "owner-allocation"
        assert rows_re.search(it["source"]), it["id"]


def test_owner_given_values(vi):
    by = {i["id"]: i for i in vi["items"]}
    assert by["VI-RF-01"]["value"] == 13.56
    assert "row 109" in by["VI-PB-04"]["source"]
    assert "0-500 W" in by["VI-RF-02"]["value"]


def test_unbooked_icp_gas_feed_flagged(vi):
    g = {i["id"]: i for i in vi["items"]}["VI-GAS-01"]
    # A9-10: the row-46 flag is resolved by A9.1 HIQ-06 (G-REUSE primary, no dedicated ICP flow)
    assert g["value"].startswith("G-REUSE (A9.1 HIQ-06)") and "mdot_ICP,dedicated = 0" in g["value"]
    assert g["status"] == "OWNER_GIVEN (A9.1 HIQ-06)"
    q = {q["id"]: q for q in vi["open_owner_questions"]}["OQ-VI-01"]
    assert q["status"].startswith("ANSWERED_BY_A9_1 (HIQ-06)")


def test_analog_vs_hardware_marked(vi):
    for it in vi["items"]:
        assert it["supply"] in ("owner", "H-1 hardware only",
                                "analog can bound (context only); value from H-1 hardware")
    c = vi["summary_counts"]
    assert c["hardware_only"] > 0 and c["analog_can_bound_context"] > 0


def test_pending_lanes_referenced_not_fabricated(vi):
    txt = json.dumps(vi)
    for lane in ("docs/experiments/hall_icp/prereg_framework/", "docs/architecture_comparison/power_boundary_a9/",
                 "docs/interfaces/icp_neutralizer/", "docs/experiments/hall_icp/uncertainty_budget/"):
        # A9-10 review repair: a reference may be resolved to the merged lane (named with its file) instead
        assert ("PENDING " + lane in txt or ("PENDING abep_sim/bus_boundary_a9.py + " + lane) in txt
                or "abep_sim/bus_boundary_a9.py SLOTS" in txt or "schemas/interfaces/icp_neutralizer_icd_v1.json" in txt
                or re.search(re.escape(lane) + r"[a-z0-9_]+\.json", txt)), lane


def test_vocabulary(vi):
    dv = vi["decision_vocabulary"]
    assert any("NO_VIABLE_CASE" in x for x in dv["outcomes_known_from_owner_answers"])
    assert "OPEN" in dv["status_not_outcome"]
    assert not any(x.startswith("OPEN") for x in dv["outcomes_known_from_owner_answers"])
    assert dv["winner"].startswith("none")
    assert vi["configuration_ids"] == ["hall_c1_reference", "hall_icp_neutralizer"]


def test_required_sections(vi, ev):
    for doc in (vi, ev):
        for k in ("interface_demands", "owner_answers_applied", "open_owner_questions", "historical_reuse",
                  "m16_impact", "h3_h4_inputs"):
            assert doc[k], k
    dirs = {d["direction"] for d in vi["interface_demands"]}
    assert dirs == {"to", "from"}
    rows = {o["row"] for o in vi["owner_answers_applied"]}
    assert {37, 38, 46, 70, 72, 108, 109, 145, 146} <= rows
    for q in vi["open_owner_questions"]:
        assert q["proposed_answer"]


def test_historical_artifacts_unchanged(vib):
    import hashlib
    for p in vib.HISTORICAL_PINS:
        with open(os.path.join(ROOT, p["path"]), "rb") as f:
            assert hashlib.sha256(f.read()).hexdigest() == p["sha256"]


def test_no_forbidden_sources_or_substrings():
    for d in (EV_DIR, VI_DIR):
        for fn in os.listdir(d):
            if fn.endswith(".py"):
                with open(os.path.join(d, fn), encoding="utf-8") as f:
                    src = f.read()
                assert "xe" + "_ledger" not in src, fn
                assert "plasma_devices" not in src.replace("abep_sim/plasma_devices.py", ""), fn
                assert "import abep_sim" not in src and "from abep_sim" not in src, fn


def test_no_dependency_on_parallel_lane_paths():
    for d in (EV_DIR, VI_DIR):
        for fn in os.listdir(d):
            if fn.endswith(".py"):
                with open(os.path.join(d, fn), encoding="utf-8") as f:
                    src = f.read()
                assert ".claude/worktrees" not in src
                assert "import bus_boundary_a9" not in src and "from abep_sim" not in src
