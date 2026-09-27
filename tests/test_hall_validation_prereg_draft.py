"""Invariants of the W5 held-out Hall-transport validation pre-registration DRAFT.

docs/validation/hall_transport_v2_prereg/ (fo_hall_validation_prereg_draft). Pure file checks; no simulation, no Julia,
no dependency on other lanes' planned paths.
"""
import importlib.util
import json
import re
from fractions import Fraction
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
D = REPO / "docs" / "validation" / "hall_transport_v2_prereg"
DRAFT = D / "hall_transport_v2_prereg_DRAFT.json"
MD = D / "HALL_TRANSPORT_V2_PREREG_DRAFT.md"

# anything that would make P5 (Xe or N2 v1) data a target, tolerance source or registration input
P5_EVIDENCE = re.compile(r"p5|brabston|p5_n2_campaign|hallthruster_bridge/validation|identification/|cases/|bfield/"
                         r"|peterson", re.IGNORECASE)

W4_OBSERVABLES = {"VO-ID", "VO-T", "VO-BZ", "VO-FEED", "VO-SPECIES", "VO-IEDF", "VO-DIV", "VO-TENE", "VO-OSC",
                  "VO-IGNEXT"}


@pytest.fixture(scope="module")
def draft():
    return json.loads(DRAFT.read_text(encoding="utf-8"))


def _walk(obj, path=()):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield path + (k,), k, v
            yield from _walk(v, path + (k,))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk(v, path + (i,))


def test_draft_status_not_locked(draft):
    assert draft["status"] == "DRAFT_PENDING_OWNER"
    assert draft["locked"] is False
    assert draft["lock"] is None
    assert draft["score_bearing_runs_authorized"] is False
    assert draft["simulation_runs_performed"] == []
    assert draft["measurements_existing"] == []


def test_nothing_marked_locked_anywhere(draft):
    for path, key, val in _walk(draft):
        if key in ("locked", "frozen", "is_locked"):
            assert val is False, path
        if key == "status" and isinstance(val, str):
            assert not re.search(r"\b(LOCKED|FROZEN|FINAL|APPROVED)\b", val), (path, val)
    # no lock artefact is created by the draft
    assert not (D / "lock").exists()
    assert not any("lock" in p.name.lower() for p in D.iterdir() if p.is_file())
    md = MD.read_text(encoding="utf-8")
    assert "DRAFT_PENDING_OWNER" in md
    assert "Not locked" in md


def test_no_criterion_uses_p5_data_as_new_evidence(draft):
    for cid, c in draft["criteria"].items():
        for field in ("target_source", "tolerance_source"):
            assert field in c, (cid, field)
            assert not P5_EVIDENCE.search(c[field]), (cid, field, c[field])
        assert "new common-hardware experiment" in c["target_source"] or c["target_source"].startswith("H-1"), cid
    for oid, o in draft["observables"].items():
        if oid == "note":
            continue
        assert not P5_EVIDENCE.search(o["target_source"]), (oid, o["target_source"])
    for reg in draft["registration_inputs"]["items"]:
        assert not P5_EVIDENCE.search(reg["instrument_or_source"]), reg["id"]
    rel = draft["relation_to_p5_n2_v1"]
    assert rel["v1_outcome"] == "INCONCLUSIVE"
    assert rel["v1_outcome_changed_by_this_draft"] is False
    forbidden = " ".join(rel["forbidden_as_evidence"])
    for needle in ("hallthruster_bridge/validation", "cases/p5_n2.json", "identification", "bfield"):
        assert needle in forbidden


def test_observable_classification_complete_and_disjoint(draft):
    obs = {k: v for k, v in draft["observables"].items() if k != "note"}
    assert set(obs) == W4_OBSERVABLES
    held = {k for k, v in obs.items() if v["class"].startswith("HELD_OUT")}
    reg = {k for k, v in obs.items() if v["class"].startswith("REGISTRATION")}
    assert held and reg and not (held & reg)
    assert {"VO-ID", "VO-T", "VO-IGNEXT"} <= {k for k in held if "GATING" in obs[k]["class"]
                                              and "NON_GATING" not in obs[k]["class"]}
    assert {"VO-BZ", "VO-FEED"} <= reg
    for k in held:
        assert obs[k]["criterion"] in draft["criteria"], k
    gating = {k for k, c in draft["criteria"].items() if c["gating"]}
    assert gating == {"C-ID", "C-T", "C-SUST"}


def test_candidates_are_the_nine_screening_sets_within_prior(draft):
    ids = draft["candidates"]["ids"]
    assert ids == [f"sgb-screen-{i:02d}" for i in range(1, 10)]
    ens = json.loads((REPO / "hallthruster_bridge/ensemble/transport_ensemble_v0.json").read_text())
    sc = {c["ensemble_member_id"]: c for c in ens["screening_candidates"]}
    assert set(ids) == set(sc)
    for i in ids:
        assert Fraction(sc[i]["transport_parameters"]["anom_scale"]).limit_denominator(10**6) <= Fraction(1, 16)
    assert draft["candidates"]["set_closed_at_lock"] is True


def test_chemistry_domain_rule_not_relaxed(draft):
    ch = draft["chemistry"]
    assert ch["mandatory_configs"] == ["n2_n.toml", "n2_n_di_lower.toml", "n2_n_nel_wang.toml",
                                       "n2_n_di_lower_nel_wang.toml"]
    dr = ch["domain_rule"]
    assert dr["f_out_tolerance"] == 1e-12
    assert dr["mean_energy_cap_eV"] == 45 and dr["T_e_cap_eV"] == 30
    assert dr["relaxed"] is False
    rs = draft["run_status"]
    assert rs["statuses"] == ["PASS", "FAIL_VALIDATION", "OUT_OF_DOMAIN", "NUMERICAL_FAILURE"]
    assert rs["precedence"] == ["NUMERICAL_FAILURE", "OUT_OF_DOMAIN", "FAIL_VALIDATION", "PASS"]
    assert "hallthruster_bridge/prereg/p5_n2_run_status_rule_v1.json" in rs["adopted_by_reference"]
    # OUT_OF_DOMAIN never yields FAIL, and never PROMOTABLE
    cand = draft["verdict_logic"]["candidate"]
    assert "OUT_OF_DOMAIN" in cand["INCONCLUSIVE_NOT_ELIGIBLE"]
    assert "NOT rejected" in cand["INCONCLUSIVE_NOT_ELIGIBLE"]
    assert "never admits" in draft["verdict_logic"]["after_PROMOTABLE"]


def test_runnability_depends_on_geometry_and_inflow_gap(draft):
    gates = {g["id"]: g for g in draft["runnability_gates"]["gates"]}
    assert "geometry" in gates["RG-01"]["item"] and gates["RG-01"]["required_before_PF1"] is True
    assert "inflow" in gates["RG-03"]["item"].lower() and "lane 35" in gates["RG-03"]["owner_lane"]
    assert "B(z)" in gates["RG-02"]["item"] and gates["RG-02"]["required_before_PF1"] is True
    fam = {f["id"]: f for f in draft["condition_families"]["families"]}
    assert fam["F4"]["role"] == "SEQUESTERED_FOR_FUTURE_PREREG"
    assert fam["F5"]["role"] == "SEQUESTERED_FOR_FUTURE_PREREG"


def test_thresholds_have_status_and_source(draft):
    allowed = {"RFP", "PROPOSED", "TBD_FROM_INSTRUMENTATION", "PRE_REGISTERED_PROJECT_RULE"}
    for t in draft["thresholds"]:
        assert t["status"] in allowed, t["id"]
        assert t["source"], t["id"]
        if t["status"] == "RFP":
            assert "RFP" in t["source"]
    # every criterion value that depends on measurement uncertainty is TBD_FROM_INSTRUMENTATION
    assert draft["criteria"]["C-ID"]["u_exp"] == "TBD_FROM_INSTRUMENTATION"
    assert draft["criteria"]["C-T"]["u_exp"] == "TBD_FROM_INSTRUMENTATION"
    for c in draft["criteria"].values():
        assert c["status"] == "PROPOSED"
    for vp in draft["owner_decisions"]:
        assert vp["id"].startswith("VP-") and vp["PROPOSED"]


def test_milestones_stated(draft):
    m = draft["milestones"]
    assert m["supports"] == ["B"]
    assert m["B"]["needs_to_reach_B"]
    for k in ("A", "C", "operating_model_questions"):
        assert k in m


def test_custody_predictions_frozen_before_hall_on_data(draft):
    seq = " ".join(draft["custody_and_blinding"]["sequence"])
    assert "LOCK-H1" in seq and "before any Hall-on reading" in seq
    assert "PF-1" in seq and "BEFORE the first Hall-on reading" in seq
    assert "score once" in seq


def test_pins_match_repository():
    spec = importlib.util.spec_from_file_location("pin_inputs", D / "pin_inputs.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.check_pins() == []
