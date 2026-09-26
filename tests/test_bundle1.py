"""Tests for Bundle 1 (Milestone A, conditional selection): fo_bundle1_conditional_selection.

Checks that docs/milestones/bundle1/build_bundle1.py reproduces bundle1_v1.json and BUNDLE1.md byte for byte, that the
JSON validates against its schema, that every architecture x mandatory-field cell carries the full metadata, that the
outcome is one of the two allowed forms, that any ELIMINATED_WITHIN_TESTED_ENVELOPE traces to a lane-24 demonstrated
gate, that P_feed / T_feed stay EXPLICITLY_UNAVAILABLE, that the input sha256 pins hold (and that a changed or missing
input raises), and that the forbidden wording is absent.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "docs" / "milestones" / "bundle1" / "build_bundle1.py"


def _load():
    spec = importlib.util.spec_from_file_location("build_bundle1", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bb = _load()
JSON_PATH = REPO / bb.OUT_JSON_REL
MD_PATH = REPO / bb.OUT_MD_REL
SCHEMA_PATH = REPO / bb.SCHEMA_REL
FIELDS = [f for f, _, _ in bb.MANDATORY_FIELDS]


@pytest.fixture(scope="module")
def rendered():
    return bb.render_all()


@pytest.fixture(scope="module")
def doc():
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


def test_build_reproduces_byte_for_byte(rendered):
    js, md = rendered
    assert JSON_PATH.read_text(encoding="utf-8") == js
    assert MD_PATH.read_text(encoding="utf-8") == md


def test_check_mode_cli():
    r = subprocess.run([sys.executable, str(SCRIPT), "--check"], capture_output=True, text=True, cwd=REPO, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr


def test_schema_valid(doc):
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert bb.validate(doc, schema) == []


def test_schema_rejects_filled_feed_pressure(doc):
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    bad = copy.deepcopy(doc)
    c = bad["admissibility"]["cells"]["hall_only"]["P_feed"]
    c.update(status="POPULATED", value=0.05, evidence_class="assumed")
    assert bb.validate(bad, schema)


def test_field_set_matches_operating_model(doc):
    assert FIELDS == ["m_dot_s", "P_feed", "T_feed", "x_s", "V_d", "T", "P_bus", "m", "Q_reject", "life", "startup", "eta_u",
                      "stability"]
    om = " ".join((REPO / "docs/orchestration/OPERATING_MODEL.md").read_text(encoding="utf-8").split())
    assert bb.OPERATING_MODEL_FIELD_SET in om
    assert [f["id"] for f in doc["mandatory_fields"]] == FIELDS


def test_every_cell_has_full_metadata(doc):
    reg = json.loads((REPO / "docs/orchestration/lane_registry_v1.json").read_text())
    known = {l["id"] for l in reg["lanes"]} | {l["id"] for l in reg["follow_ons"]}
    trig = {t["id"] for t in json.loads((REPO / "docs/orchestration/trigger_registry_v1.json").read_text())["triggers"]}
    pinned = {p for _, p, _ in bb.PINS}
    cells = doc["admissibility"]["cells"]
    assert set(cells) == set(bb.ARCHS)
    for a in bb.ARCHS:
        assert list(cells[a]) == FIELDS
        for f in FIELDS:
            c = cells[a][f]
            assert c["status"] in ("POPULATED", "EXPLICITLY_UNAVAILABLE"), (a, f)
            for k in ("units", "derivation", "uncertainty_status"):
                assert isinstance(c[k], str) and c[k].strip(), (a, f, k)
            assert c["operating_point"]["id"].startswith("OP-") and c["operating_point"]["definition"].strip()
            assert c["evidence"], (a, f)
            for e in c["evidence"]:
                assert e["path"] in pinned, (a, f, e["path"])
                assert e["input_lane"] in bb.PREREQUISITES or e["input_lane"] in bb.CONTEXT
                assert e["locator"].strip()
            assert c["evidence_class"] in bb.EVIDENCE_CLASSES
            if c["status"] == "EXPLICITLY_UNAVAILABLE":
                assert c["value"] is None and c["evidence_class"] == "none"
                assert c["uncertainty_status"].startswith("unavailable:")
                assert c["blocking"], (a, f)
            else:
                assert c["value"] is not None and c["evidence_class"] != "none"
            for b in c["blocking"]:
                assert b["what"].strip()
                if b["kind"] == "lane":
                    assert b["id"] in known, b
                if b["kind"] == "trigger":
                    assert b["id"] in trig, b
    assert doc["admissibility"]["verdict"] == "ADMISSIBLE"
    assert doc["admissibility"]["problems"] == []


def test_feed_state_pressure_temperature_unavailable(doc):
    for a in bb.ARCHS:
        for f in ("P_feed", "T_feed", "m_dot_s", "x_s"):
            c = doc["admissibility"]["cells"][a][f]
            assert c["status"] == "EXPLICITLY_UNAVAILABLE" and c["value"] is None, (a, f)
        assert doc["admissibility"]["cells"][a]["P_feed"]["units"] == "Pa"
        assert doc["admissibility"]["cells"][a]["T_feed"]["units"] == "K"


def test_feed_input_really_tbd():
    fe = json.loads((REPO / bb.FE).read_text())
    for c in fe["cases"]:
        for k in ("p_feed_Pa", "T_gas_K"):
            assert c["feed_state"][k]["value"] is None and c["feed_state"][k]["evidence_class"] == "TBD"


def test_hall_dependent_fields_not_populated(doc):
    for a in bb.ARCHS:
        for f in ("T", "P_bus", "eta_u", "stability", "life", "Q_reject"):
            assert doc["admissibility"]["cells"][a][f]["status"] == "EXPLICITLY_UNAVAILABLE"


def test_p_bus_uses_full_boundary_component_set(doc):
    ab_spec = importlib.util.spec_from_file_location("_ab", REPO / "abep_sim" / "arch_boundary.py")
    ab = importlib.util.module_from_spec(ab_spec)
    ab_spec.loader.exec_module(ab)
    for a in bb.ARCHS:
        d = doc["admissibility"]["cells"][a]["P_bus"]["derivation"]
        for comp in ab.REQUIRED_COMPONENTS[a]:
            assert comp in d, (a, comp)


def test_outcome_form(doc):
    oc = doc["outcome"]
    assert oc["form"] in bb.OUTCOME_FORMS
    if oc["form"] == "CONDITIONAL_BASELINE":
        assert oc["architecture"] in bb.ARCHS
        assert oc["label"] == f"CONDITIONAL_BASELINE({oc['architecture']})"
        assert oc["conditions"]
        for c in oc["conditions"]:
            assert c["pass_criterion"] and c["demonstrated_by"] and c["source"]
    else:
        assert oc["architecture"] is None and oc["label"] == "NO_BASELINE_YET"
        assert oc["blocking_lanes"] and any(oc["blocking_fields"][a] for a in bb.ARCHS)
    assert doc["decision_rule"]["status"] == "PROPOSED"


def test_rule_is_mechanical(doc):
    """Re-apply the rule to the committed cells and the lane-24 status: same outcome."""
    gates = bb.gates_extract()
    res = bb.apply_rule(doc["admissibility"]["cells"], doc["admissibility"], gates)
    assert res["form"] == doc["outcome"]["form"] and res["architecture"] == doc["outcome"]["architecture"]


def test_rule_single_candidate_and_discriminator_branches(doc):
    gates = bb.gates_extract()
    cells = doc["admissibility"]["cells"]
    g2 = copy.deepcopy(gates)
    for a in ("rf_hall", "ecr_hall"):
        g2["per"][a]["eliminated"] = True
        g2["per"][a]["elimination_basis"] = ["G2_bus_power: synthetic test"]
        g2["eliminated"].append(a)
    res = bb.apply_rule(cells, doc["admissibility"], g2)
    assert res["form"] == "CONDITIONAL_BASELINE" and res["architecture"] == "hall_only"
    c2 = copy.deepcopy(cells)
    c2["ecr_hall"]["m"].update(status="POPULATED", value=[1.0], evidence_class="measured", basis="measurement_same_hardware")
    res = bb.apply_rule(c2, doc["admissibility"], gates)
    assert res["form"] == "CONDITIONAL_BASELINE" and res["architecture"] == "ecr_hall"
    c3 = copy.deepcopy(cells)
    for a in bb.ARCHS:  # identical populated values on a milestone-A basis do not discriminate
        c3[a]["m"].update(status="POPULATED", value=[1.0], evidence_class="measured", basis="measurement_same_hardware")
    assert bb.apply_rule(c3, doc["admissibility"], gates)["form"] == "NO_BASELINE_YET"


def test_eliminations_trace_to_lane24(doc):
    st = json.loads((REPO / bb.HGS).read_text())
    for a, s in doc["hard_gates"]["per_architecture"].items():
        if s["bundle_status"] == "ELIMINATED_WITHIN_TESTED_ENVELOPE":
            assert a in st["eliminated"] and st["architectures"][a]["eliminated"] is True
            assert st["architectures"][a]["elimination_basis"]
            assert s["lane24_elimination_basis"] == st["architectures"][a]["elimination_basis"]
        else:
            assert st["architectures"][a]["eliminated"] is False
    assert doc["hard_gates"]["lane24_eliminated"] == st["eliminated"]


def test_overlay_counts_read_from_inputs(doc):
    rf = json.loads((REPO / bb.RFO).read_text())["placement_counts"]
    ecr = json.loads((REPO / bb.ECRO).read_text())["placement_counts"]
    ov = doc["hard_gates"]["overlays"]
    assert ov["rf_hall"]["placement_counts"] == rf
    assert ov["ecr_hall"]["placement_counts"] == ecr


def test_input_pins_verified():
    out = bb.verify_pins()
    assert len(out) == len(bb.PINS)
    for lane, rel, digest in bb.PINS:
        assert hashlib.sha256((REPO / rel).read_bytes()).hexdigest() == digest
    assert set(bb.PREREQUISITES) == {l for l, _, _ in bb.PINS} - set(bb.CONTEXT)


def test_changed_or_missing_input_raises(tmp_path):
    lane, rel, digest = bb.PINS[0]
    with pytest.raises(bb.InputError):
        bb.verify_pins([(lane, rel, "0" * 64)])
    with pytest.raises(bb.InputError):
        bb.verify_pins([(lane, rel + ".missing", digest)])
    # a changed copy of a pinned file in a scratch repo root is refused
    root = tmp_path / "repo"
    (root / Path(rel).parent).mkdir(parents=True)
    shutil.copy(REPO / rel, root / rel)
    bb.verify_pins([(lane, rel, digest)], repo=root)
    with open(root / rel, "ab") as fh:
        fh.write(b"\n")
    with pytest.raises(bb.InputError):
        bb.verify_pins([(lane, rel, digest)], repo=root)


def test_claim_identities_match_pins(doc):
    gov = bb.check_governance()
    assert doc["claim"]["prerequisite_identities_match_pins"] is True
    for i in doc["inputs"]:
        commit = bb.PREREQUISITES.get(i["lane"]) or bb.CONTEXT[i["lane"]]
        assert i["commit"] == commit
        assert i["verification_protocol"] == gov["protocols"][i["lane"]]["protocol"]


def test_pinned_files_equal_lane_commit_blobs():
    if shutil.which("git") is None:
        pytest.skip("git not available")
    for lane, rel, digest in bb.PINS:
        commit = bb.PREREQUISITES.get(lane) or bb.CONTEXT[lane]
        r = subprocess.run(["git", "show", f"{commit}:{rel}"], capture_output=True, cwd=REPO)
        if r.returncode != 0:
            pytest.skip(f"lane commit {commit[:10]} not available in this clone")
        assert hashlib.sha256(r.stdout).hexdigest() == digest, rel


def test_evidence_weight_flags(doc):
    reg = json.loads((REPO / "docs/orchestration/lane_registry_v1.json").read_text())
    single = {l["id"] for l in reg["lanes"] if l.get("verification_protocol") == "single-lens-v1"}
    ew = doc["evidence_weight"]
    assert set(ew["inputs_single_lens"]) == {i["lane"] for i in doc["inputs"] if i["lane"] in single}
    assert set(ew["blocking_lanes_single_lens"]) == set(doc["outcome"]["blocking_lanes"]) & single
    for i in doc["inputs"]:
        assert i["decisive_for_B_or_C_allowed"] is (i["lane"] not in single)


def test_three_questions_and_owner_questions(doc):
    q = doc["three_questions"]
    assert q["i_conditional_selection_now"].startswith(doc["outcome"]["label"])
    reg = json.loads((REPO / "docs/orchestration/lane_registry_v1.json").read_text())
    known = {l["id"] for l in reg["lanes"]} | {l["id"] for l in reg["follow_ons"]}
    trig = {t["id"] for t in json.loads((REPO / "docs/orchestration/trigger_registry_v1.json").read_text())["triggers"]}
    for it in q["ii_what_blocks_physics_backed_selection"]:
        for i in it["ids"]:
            assert i in known or i in trig, i
    assert q["iii_what_could_overturn"]
    lanes = {o["lane"] for o in doc["owner_questions_open"]}
    assert {"lane_16_feed_envelope", "lane_17_hall_reference", "lane_20_ppu_magnet", "lane_24_hard_gates",
            "fo_rf_breakeven_overlay", "fo_ecr_breakeven_overlay", "fo_hall_sustainment_envelope"} <= lanes


def test_forbidden_wording_absent():
    for p in (JSON_PATH, MD_PATH):
        assert bb.forbidden_hits(p.read_text(encoding="utf-8")) == [], p


def test_decision_rule_precedes_tables():
    md = MD_PATH.read_text(encoding="utf-8")
    i_rule = md.index("## 1. Decision rule (PROPOSED")
    i_adm = md.index("## 2. Admissibility")
    i_out = md.index("## 4. Outcome")
    assert i_rule < i_adm < i_out
