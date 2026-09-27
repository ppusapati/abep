"""Tests for Bundle 1 (Milestone A, conditional selection): fo_bundle1_conditional_selection, bundle versions v1 to v5.

v1 (bundle1_v1.json / BUNDLE1.md / bundle1_v1.schema.json) is the historical record of T_BUNDLE1 attempt 2; v2, v3 and v4
(bundle1_vN.json / BUNDLE1_vN.md / bundle1_vN.schema.json / governance_snapshot_vN.json) are the records of the bundle1_v2,
bundle1_v3 and bundle1_v4 repairs: all are verified by their recorded sha256 and never rebuilt. v5: checks that
docs/milestones/bundle1/build_bundle1.py reproduces bundle1_v5.json and BUNDLE1_v5.md byte for byte from the pinned inputs
and the pinned governance snapshot (never the live governance files), that every pin is current, that the v4 -> v5 change
log is consistent (fo_veto_layer context re-pin only, 0 decision-relevant changes), that the repair chain wf_60b458bb-a8d
is recorded in the governance snapshot, that the ECHT-N2 status is
carried, that the JSON
validates against its schema, that every architecture x mandatory-field cell carries the full metadata, that the
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


@pytest.fixture(scope="module")
def snap():
    return json.loads((REPO / bb.GOV_SNAPSHOT_REL).read_text(encoding="utf-8"))


def test_field_set_matches_operating_model(doc, snap):
    assert FIELDS == ["m_dot_s", "P_feed", "T_feed", "x_s", "V_d", "T", "P_bus", "m", "Q_reject", "life", "startup", "eta_u",
                      "stability"]
    assert snap["operating_model_checked"]["field_set"] == bb.OPERATING_MODEL_FIELD_SET
    assert [f["id"] for f in doc["mandatory_fields"]] == FIELDS


def test_every_cell_has_full_metadata(doc, snap):
    known = set(snap["lane_ids"]) | set(snap["fo_ids"])
    trig = set(snap["trigger_ids"])
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


def test_claim_identities_and_repin_log(doc, snap):
    gov = bb.load_governance()
    claim = snap["claim"]["prerequisites"]
    differ = sorted(l for l, c in bb.PREREQUISITES.items() if claim[l]["identity"] != c)
    assert differ == sorted(bb.REPINS) == ["fo_hall_sustainment_envelope", "lane_09_hall_sustainment"]
    assert doc["claim"]["prerequisite_identities_match_pins"] is False
    assert sorted(r["lane"] for r in doc["claim"]["repin_log"]) == differ
    for r in doc["claim"]["repin_log"]:
        assert r["claim_identity"] == claim[r["lane"]]["identity"] and r["pinned_identity"] == bb.PREREQUISITES[r["lane"]]
        assert r["reason"].strip() and r["verification_record"].strip()
    for i in doc["inputs"]:
        commit = bb.PREREQUISITES.get(i["lane"]) or bb.CONTEXT[i["lane"]]
        assert i["commit"] == commit
        assert i["verification_protocol"] == gov["protocols"][i["lane"]]["protocol"]


def test_undocumented_identity_change_raises(monkeypatch):
    monkeypatch.setitem(bb.PREREQUISITES, "lane_07_rf_evidence", "f" * 40)
    with pytest.raises(bb.InputError):
        bb.load_governance()


def test_pinned_files_equal_lane_commit_blobs():
    if shutil.which("git") is None:
        pytest.skip("git not available")
    for lane, rel, digest in bb.PINS:
        commit = bb.PREREQUISITES.get(lane) or bb.CONTEXT[lane]
        r = subprocess.run(["git", "show", f"{commit}:{rel}"], capture_output=True, cwd=REPO)
        if r.returncode != 0:
            pytest.skip(f"lane commit {commit[:10]} not available in this clone")
        assert hashlib.sha256(r.stdout).hexdigest() == digest, rel


def test_evidence_weight_flags(doc, snap):
    single = set(snap["single_lens_lanes"])
    ew = doc["evidence_weight"]
    assert set(ew["inputs_single_lens"]) == {i["lane"] for i in doc["inputs"] if i["lane"] in single}
    assert set(ew["blocking_lanes_single_lens"]) == set(doc["outcome"]["blocking_lanes"]) & single
    for i in doc["inputs"]:
        assert i["decisive_for_B_or_C_allowed"] is (i["lane"] not in single)


def _walk(o):
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from _walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from _walk(v)


def test_blocker_protocol_labels_match_snapshot(doc, snap):
    """No blocking annotation may claim a verification protocol the pinned governance snapshot does not record."""
    single = set(snap["single_lens_lanes"])
    n = 0
    for d in _walk(doc):
        if d.get("kind") == "lane" and isinstance(d.get("what"), str):
            n += 1
            if "single-lens" in d["what"]:
                assert d["id"] in single, (d["id"], d["what"])
            if "two-lens" in d["what"]:
                assert d["id"] not in single, (d["id"], d["what"])
    assert n > 0


def test_rf_thresholds_scoped_to_overlay_box(doc):
    txt = " ".join(doc["three_questions"]["iii_what_could_overturn"])
    assert "182.149" in txt and "2208.19" in txt
    assert "declared box" in txt and "omega_f = 0" in txt and "NOT evaluated on the lane-17" in txt


def test_three_questions_and_owner_questions(doc, snap):
    q = doc["three_questions"]
    assert q["i_conditional_selection_now"].startswith(doc["outcome"]["label"])
    known = set(snap["lane_ids"]) | set(snap["fo_ids"])
    trig = set(snap["trigger_ids"])
    for it in q["ii_what_blocks_physics_backed_selection"]:
        for i in it["ids"]:
            assert i in known or i in trig, i
    assert q["iii_what_could_overturn"]
    lanes = {o["lane"] for o in doc["owner_questions_open"]}
    assert {"lane_16_feed_envelope", "lane_17_hall_reference", "lane_20_ppu_magnet", "lane_24_hard_gates",
            "fo_rf_breakeven_overlay", "fo_ecr_breakeven_overlay", "fo_hall_sustainment_envelope"} <= lanes


def test_forbidden_wording_absent():
    for p in (JSON_PATH, MD_PATH, REPO / bb.GOV_SNAPSHOT_REL, REPO / bb.SCHEMA_REL):
        assert bb.forbidden_hits(p.read_text(encoding="utf-8")) == [], p


def test_decision_rule_precedes_tables():
    md = MD_PATH.read_text(encoding="utf-8")
    i_rule = md.index("## 1. Decision rule (PROPOSED")
    i_adm = md.index("## 2. Admissibility")
    i_out = md.index("## 4. Outcome")
    assert i_rule < i_adm < i_out


# ----------------------------------------------------------------------------------------------------------------------
# v1 historical record, governance snapshot, change log, ECHT status, context lanes (bundle1_v2 to v5 repairs)
# ----------------------------------------------------------------------------------------------------------------------
def test_v1_record_verified_by_sha256():
    for rel, digest in bb.V1_RECORD["files"].items():
        assert hashlib.sha256((REPO / rel).read_bytes()).hexdigest() == digest, rel
    v1 = bb.verify_v1_record()
    assert v1["id"] == "bundle1_v1" and v1["outcome"]["label"] == "NO_BASELINE_YET"


def test_v1_record_change_detected(tmp_path):
    root = tmp_path / "repo"
    for rel in bb.V1_RECORD["files"]:
        (root / Path(rel).parent).mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO / rel, root / rel)
    bb.verify_v1_record(root)
    with open(root / "docs/milestones/bundle1/BUNDLE1.md", "ab") as fh:
        fh.write(b"\n")
    with pytest.raises(bb.InputError):
        bb.verify_v1_record(root)


def test_v1_files_equal_their_verified_commit():
    if shutil.which("git") is None:
        pytest.skip("git not available")
    for rel, digest in bb.V1_RECORD["files"].items():
        r = subprocess.run(["git", "show", f"{bb.V1_RECORD['commit']}:{rel}"], capture_output=True, cwd=REPO)
        if r.returncode != 0:
            pytest.skip("v1 commit not available in this clone")
        assert hashlib.sha256(r.stdout).hexdigest() == digest, rel


def test_governance_snapshot_pinned(tmp_path):
    assert hashlib.sha256((REPO / bb.GOV_SNAPSHOT_REL).read_bytes()).hexdigest() == bb.GOV_SNAPSHOT_SHA256
    bad = tmp_path / "snap.json"
    bad.write_bytes((REPO / bb.GOV_SNAPSHOT_REL).read_bytes() + b"\n")
    with pytest.raises(bb.InputError):
        bb.load_governance(bad)


def test_build_does_not_read_live_governance(monkeypatch, rendered):
    """Registry / ledger bookkeeping cannot break reproduction: the build never opens the live governance files."""
    monkeypatch.setattr(bb, "_live_gov_text", lambda rel: (_ for _ in ()).throw(AssertionError(f"live governance read: {rel}")))
    assert bb.render_all() == rendered


def test_governance_snapshot_matches_captured_commit(snap):
    if shutil.which("git") is None:
        pytest.skip("git not available")
    for rel, digest in snap["source_files_sha256"].items():
        r = subprocess.run(["git", "show", f"{snap['captured_from_commit']}:{rel}"], capture_output=True, cwd=REPO)
        if r.returncode != 0:
            pytest.skip("snapshot commit not available in this clone")
        assert hashlib.sha256(r.stdout).hexdigest() == digest, rel


def test_change_log(doc):
    cl = doc["change_log"]
    assert cl["from"] == "bundle1_v4" and cl["to"] == "bundle1_v5"
    assert all(cl["unchanged"].values()), cl["unchanged"]
    assert cl["decision_relevant_changes"] == []
    assert cl["inputs_added"] == [] and cl["inputs_removed"] == []
    assert [(i["lane"], i["role"]) for i in cl["inputs_changed"]] == [("fo_veto_layer", "context")]
    ch = cl["inputs_changed"][0]
    assert ch["from_commit"].startswith("7a7eb68") and ch["to_commit"] == bb.CONTEXT["fo_veto_layer"]
    assert bb.CONTEXT["fo_veto_layer"].startswith("deafae0")
    assert [f["path"] for f in ch["files"]] == ["docs/architecture_comparison/veto_layer/veto_layer_v1.json"]
    assert ch["files"][0]["from_sha256"].startswith("1f4c2d8d") and ch["files"][0]["to_sha256"].startswith("1371e435")
    v4 = json.loads((REPO / bb.V4_RECORD["json"]).read_text(encoding="utf-8"))
    assert bb.change_log(v4, doc) == cl
    older = [json.loads((REPO / r["json"]).read_text(encoding="utf-8")) for r in (bb.V2_RECORD, bb.V3_RECORD)]
    v1 = json.loads((REPO / "docs/milestones/bundle1/bundle1_v1.json").read_text(encoding="utf-8"))
    for old in [v4, *older, v1]:
        assert old["outcome"]["label"] == doc["outcome"]["label"] == "NO_BASELINE_YET"
        assert old["decision_rule"] == doc["decision_rule"]
    assert doc["decision_rule"]["id"] == "B1-DR-1"
    assert doc["outcome"] == v4["outcome"]
    # the veto-layer context re-pin changes none of the veto-layer readings Bundle 1 carries
    for k in ("status", "status_counts", "cells", "eliminated_within_tested_envelope", "veto_candidates"):
        assert doc["context_followons"]["fo_veto_layer"][k] == v4["context_followons"]["fo_veto_layer"][k], k
    # the only metadata changes: veto-layer commit annotations and dropped stale protocol labels on cells, the single-lens list
    # (second lens recorded at base), and the RF-threshold scope note in question (iii)
    for path in cl["metadata_changes"]:
        assert path.startswith(("admissibility.cells.", "evidence_weight.")) or path == "three_questions.iii_what_could_overturn[1]", path
    assert doc["evidence_weight"]["blocking_lanes_single_lens"] == []


def test_every_pin_matches_current_file():
    """All prerequisite and context pins are current (no stale pin left after the re-pin race)."""
    for lane, rel, digest in bb.PINS:
        assert hashlib.sha256((REPO / rel).read_bytes()).hexdigest() == digest, (lane, rel)


@pytest.mark.parametrize("rec_name", ["V2_RECORD", "V3_RECORD", "V4_RECORD"])
def test_historical_record_verified_by_sha256(tmp_path, rec_name):
    rec = getattr(bb, rec_name)
    verify = {"V2_RECORD": bb.verify_v2_record, "V3_RECORD": bb.verify_v3_record, "V4_RECORD": bb.verify_v4_record}[rec_name]
    for rel, digest in rec["files"].items():
        assert hashlib.sha256((REPO / rel).read_bytes()).hexdigest() == digest, rel
    old = verify()
    assert old["id"] == rec["id"] and old["outcome"]["label"] == "NO_BASELINE_YET"
    root = tmp_path / "repo"
    for rel in rec["files"]:
        (root / Path(rel).parent).mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO / rel, root / rel)
    verify(root)
    md = next(r for r in rec["files"] if r.endswith(".md"))
    with open(root / md, "ab") as fh:
        fh.write(b"\n")
    with pytest.raises(bb.InputError):
        verify(root)


@pytest.mark.parametrize("rec_name", ["V2_RECORD", "V3_RECORD", "V4_RECORD"])
def test_historical_files_equal_their_verified_commit(rec_name):
    rec = getattr(bb, rec_name)
    if shutil.which("git") is None:
        pytest.skip("git not available")
    for rel, digest in rec["files"].items():
        r = subprocess.run(["git", "show", f"{rec['commit']}:{rel}"], capture_output=True, cwd=REPO)
        if r.returncode != 0:
            pytest.skip(f"{rec['id']} commit not available in this clone")
        assert hashlib.sha256(r.stdout).hexdigest() == digest, rel
    r = subprocess.run(["git", "show", f"{rec['commit']}:{bb.SCRIPT_REL}"], capture_output=True, cwd=REPO)
    assert hashlib.sha256(r.stdout).hexdigest() == rec["builder_sha256_at_commit"]


def test_historical_records_and_repair_records(doc, snap):
    assert [h["id"] for h in doc["historical_records"]] == ["bundle1_v1", "bundle1_v2", "bundle1_v3", "bundle1_v4"]
    assert doc["supersedes"]["id"] == "bundle1_v4" and doc["supersedes"]["commit"] == bb.V4_RECORD["commit"]
    recs = {(r["lane"], r["pinned_identity"]): r for r in snap["repair_records"]}
    expected_runs = {
        ("fo_veto_layer", bb.CONTEXT["fo_veto_layer"]): "wf_60b458bb-a8d",
        ("fo_experiment_package", bb.CONTEXT["fo_experiment_package"]): "wf_16b7de5d-7b9",
        ("fo_hall_sustainment_envelope", bb.PREREQUISITES["fo_hall_sustainment_envelope"]): "wf_e16cec30-7b2",
        ("fo_bundle1_conditional_selection", bb.V2_RECORD["commit"]): "wf_e16cec30-7b2",
        ("fo_bundle1_conditional_selection", bb.V3_RECORD["commit"]): "wf_16b7de5d-7b9",
        ("fo_bundle1_conditional_selection", bb.V4_RECORD["commit"]): "wf_e6704550-845",
    }
    assert set(recs) == set(expected_runs)
    for key, r in recs.items():
        assert r["registry_repair"]["workflow_run"] == expected_runs[key]
        subj = r["merge_commit_subject"]
        if r["merge_commit"] is None:  # repair chain of this run: integrated by fast-forward, no merge commit
            assert key == ("fo_veto_layer", bb.CONTEXT["fo_veto_layer"]) and subj is None
            assert r["integration"] == {"mode": "fast-forward", "integration_commit": bb.INTEGRATION_COMMIT,
                                        "ancestor_of_integration_commit": True, "registry_commit": bb.GOV_CAPTURE_COMMIT}
            continue
        m = bb.MERGE_SUBJECT.match(subj)
        assert m and m.group("lane") == r["lane"] and r["pinned_identity"].startswith(m.group("sha")), subj
    for r in doc["claim"]["repin_log"] + doc["claim"]["context_repin_log"]:
        assert "TBD" not in r["verification_record"]
    assert [r["lane"] for r in doc["claim"]["context_repin_log"]] == ["fo_veto_layer", "fo_experiment_package"]
    vl = doc["context_followons"]["fo_veto_layer"]["verified"]
    assert vl["commit"] == bb.CONTEXT["fo_veto_layer"] and vl["ledger_verified_commit"].startswith("3e7805c")
    xp = doc["context_followons"]["fo_experiment_package"]["verified"]
    assert xp["commit"] == bb.CONTEXT["fo_experiment_package"] and xp["ledger_verified_commit"].startswith("c09fac4")


def test_repair_chain_recorded(doc, snap):
    rc = snap["repair_chain"]
    assert rc["workflow_run"] == bb.REPAIR_CHAIN_RUN == "wf_60b458bb-a8d"
    assert rc["registry_commit"] == bb.GOV_CAPTURE_COMMIT == snap["captured_from_commit"]
    assert rc["registry_commit_parent"] == bb.BASE_COMMIT and rc["integration_commit"] == bb.INTEGRATION_COMMIT
    assert rc["registry_commit_changes"] == sorted(["docs/orchestration/lane_registry_v1.json", bb.REPAIR_CHAIN_SCRIPT])
    assert [e["lane"] for e in rc["entries"]] == ["lane_15_thermal_life", "fo_veto_layer", "fo_bundle1_conditional_selection"]
    for e in rc["entries"]:
        assert e["registry_repair"]["workflow_run"] == "wf_60b458bb-a8d"
        assert e["registry_repair"]["workflow_key"] == bb.REPAIR_CHAIN[e["lane"]]["workflow_key"]
        assert e["commit"] == bb.REPAIR_CHAIN[e["lane"]]["commit"]
    assert rc["entries"][1]["commit"] == bb.CONTEXT["fo_veto_layer"]
    assert doc["provenance"]["governance_snapshot"]["repair_chain"] == rc
    assert "wf_60b458bb-a8d" in snap["protocols"]["fo_veto_layer"]["notes"][0]
    if shutil.which("git") is None:
        pytest.skip("git not available")
    for e in rc["entries"]:
        if e["commit"]:
            r = subprocess.run(["git", "merge-base", "--is-ancestor", e["commit"], bb.INTEGRATION_COMMIT], cwd=REPO)
            if r.returncode not in (0, 1):
                pytest.skip("repair-chain commits not available in this clone")
            assert r.returncode == 0, e["lane"]
    r = subprocess.run(["git", "show", f"{bb.GOV_CAPTURE_COMMIT}:docs/orchestration/lane_registry_v1.json"], capture_output=True, cwd=REPO)
    if r.returncode != 0:
        pytest.skip("governance commit not available in this clone")
    reg = json.loads(r.stdout)
    entries = {x["id"]: x for x in reg["lanes"] + reg["follow_ons"]}
    for e in rc["entries"]:
        assert e["registry_repair"] in entries[e["lane"]]["repairs"]


def test_blocker_annotations_not_duplicated(doc):
    for a in bb.ARCHS:
        for f in FIELDS:
            for b in doc["admissibility"]["cells"][a][f]["blocking"]:
                assert b["what"].count(" VERIFIED at ") <= 1, (a, f, b["what"])


def test_echt_status_carried(doc):
    ec = doc["carried_statuses"]["echt_n2"]
    m = json.loads((REPO / bb.HSM).read_text())
    src = {e["id"]: e["repository_status"] for e in m["entries"] if "repository_status" in e}
    assert [i["item"] for i in ec["lane09_items"]] == sorted(src) == ["E03", "E04"]
    for i in ec["lane09_items"]:
        rs = src[i["item"]]
        assert i["status"] == rs["status"] == "HISTORICAL_UNSUPPORTED"
        assert i["literature_transfer_use"] == rs["literature_transfer_use"]
        assert i["score_bearing"] is False and i["transport_discriminator"] is False
        assert i["forced_assumptions_relevant_to_transfer"] == rs["forced_assumptions_relevant_to_transfer"]
    assert [d["forced_assumption"] for d in ec["hsenv_declared_uncertainties"]] == ["A1", "A1"]
    assert "HISTORICAL_UNSUPPORTED" in " ".join(doc["admissibility"]["cells"]["hall_only"]["stability"]["notes"])


def test_context_lanes_metadata_only(doc):
    v1 = json.loads((REPO / "docs/milestones/bundle1/bundle1_v1.json").read_text(encoding="utf-8"))
    for a in bb.ARCHS:
        for f in FIELDS:
            c1, c2 = v1["admissibility"]["cells"][a][f], doc["admissibility"]["cells"][a][f]
            assert c1["status"] == c2["status"] and c1["value"] == c2["value"]
            assert [(b["kind"], b["id"]) for b in c1["blocking"]] == [(b["kind"], b["id"]) for b in c2["blocking"]]
    cx = doc["context_followons"]
    for lane, trig in bb.CONTEXT_TRIGGERS.items():
        assert cx[lane]["verified"]["trigger"] == trig and cx[lane]["verified"]["commit"] == bb.CONTEXT[lane]
        if lane not in bb.CONTEXT_REPINS:
            assert "ledger_verified_commit" not in cx[lane]["verified"]
    assert cx["fo_veto_layer"]["eliminated_within_tested_envelope"] == [] and cx["fo_veto_layer"]["veto_candidates"] == []
    for a in bb.ARCHS:
        assert "fo_aux_bus_comparison" in " ".join(doc["admissibility"]["cells"][a]["P_bus"]["notes"])
