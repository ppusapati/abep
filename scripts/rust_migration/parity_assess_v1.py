"""Parity campaigns of the SC-WP-11 assessment contracts (crate abep-assess):

  gates  PARITY-C-ABEP_SIM_ASSESSMENT_DESIGN_GATES_PY-V1   (design_gates E1-E14, rfp_power_gate, statewise_envelope,
                                                            bus_power gate_verdict, icp45a_margin)
  rvm    PARITY-C-DOCS_REQUIREMENTS_RVM_A9-RULES_AND_ICP_GATE-V1 (rvm_rules, GNG-ICP-01 evaluator, RVM replay)

  python scripts/rust_migration/parity_assess_v1.py dev|score gates|rvm

The Python reference is imported read-only; the Rust side is `abep-assess-parity eval` (release build). Development
runs use the development seed and print a summary only; `score` runs once with the scoring seed and writes the report
(parity_report_v1.json + .md) and the captured reference outputs next to the contract.
"""
from __future__ import annotations

import copy
import datetime
import gzip
import hashlib
import json
import math
import os
import platform
import random
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "docs/requirements/rvm_a9"))
sys.path.insert(0, str(ROOT / "docs/experiments/hall_icp/p1_icp_bench"))

from abep_sim import bus_boundary_a9_v2 as BB  # noqa: E402
from abep_sim.assessment import design_gates as DG  # noqa: E402
from abep_sim.design import architecture_optimizer as AO  # noqa: E402
from abep_sim.design import upstream_a9_13 as U13  # noqa: E402
from abep_sim.design import intake_synthesis as ISY  # noqa: E402
from abep_sim.programme import design_synthesis as DS  # noqa: E402
import rvm_rules as RR  # noqa: E402
import a9_21_icp_gate as IG  # noqa: E402
import a9_19_rvm as A19  # noqa: E402
import p1_reducer as P1  # noqa: E402

CONTRACTS = {
    "gates": "docs/rust_migration/contracts/C-ABEP_SIM_ASSESSMENT_DESIGN_GATES_PY/parity_prereg_v1.json",
    "rvm": "docs/rust_migration/contracts/C-DOCS_REQUIREMENTS_RVM_A9-RULES_AND_ICP_GATE/parity_prereg_v1.json",
}
MESSAGE_CLASSES = {"A913RuleError", "BoundaryA9Error", "OptimizerError", "RuntimeError", "RvmError", "IcpGateError"}
A931_HC05_BASIS = ("A9.31 sec. 10 (OQ-NPICP-02): a model-derived I_e,cap that is VERIFIED but not bench-validated does "
                   "not satisfy HC-05; NOT_EVALUATED outside a VALIDATED_BENCH domain cell (a measured I_e,cap "
                   "supersedes the model at the measured point); the record carries no qualifying validation_basis")
RUST_SOURCES = ["Cargo.toml", "Cargo.lock", "rust-toolchain.toml", "crates/abep-types/src/**", "crates/abep-config/src/**",
                "crates/abep-mission/src/**", "crates/abep-gaspath/src/**", "crates/abep-assess/**"]
EVALUATED, PARAMETRIC, INCOMPLETE, NOT_EV, SYN = AO.OBJECTIVE_STATUSES
FLIGHT = "hall_icp_neutralizer"


# ============================================================================================== utilities
def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha_file(p: Path) -> str:
    return sha_bytes(Path(p).read_bytes())


def git(*a: str) -> str:
    return subprocess.run(["git", *a], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


def encode(v):
    if isinstance(v, float) and not math.isfinite(v):
        return {"float": "NaN" if v != v else ("+inf" if v > 0 else "-inf")}
    if isinstance(v, dict):
        return {str(k): encode(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [encode(x) for x in v]
    if isinstance(v, set):
        return [encode(x) for x in sorted(v)]
    return v


def decode(v):
    if isinstance(v, dict):
        if set(v) == {"float"} and v["float"] in ("NaN", "+inf", "-inf"):
            return {"NaN": float("nan"), "+inf": float("inf"), "-inf": float("-inf")}[v["float"]]
        return {k: decode(x) for k, x in v.items()}
    if isinstance(v, list):
        return [decode(x) for x in v]
    return v


def canon(v) -> str:
    return json.dumps(encode(v), ensure_ascii=False, sort_keys=False, allow_nan=False)


def py_result(fn):
    try:
        v = fn()
    except Exception as e:  # noqa: BLE001 - every exception class is an observable
        return {"outcome": "RAISED", "class": type(e).__name__, "message": str(e)}
    return {"outcome": "RETURNED", "value": encode(v)}


def ulp(x: float) -> float:
    if x == 0 or not math.isfinite(x):
        return 5e-324
    e = math.frexp(abs(x))[1] - 1
    return max(2.0 ** (e - 52), 5e-324)


# ============================================================================================== Python calls
def table_by_sid(pairs):
    t = {}
    for k, v in pairs:
        t[k] = v
    return t


def positional_fn(seq, states):
    pos = {id(s): i for i, s in enumerate(states)}
    return lambda st: copy.deepcopy(seq[pos[id(st)]])


class H1Map:
    def __init__(self, status, table, states):
        self.status = status
        self._t = table
        self._pos = {id(s): i for i, s in enumerate(states)}

    def min_feed_state(self, st, thrust_N, offered):
        return copy.deepcopy(self._t[self._pos[id(st)]])


def h1tol(h):
    if h is None:
        return None
    return U13.H1Tolerance(h["quantity"], h["value_frac"], h["status"], h["source"])


def with_files(a, fn):
    """Write a['files'] into a scratch directory; root = <scratch>/<a['root_rel']>."""
    tmp = Path(tempfile.mkdtemp(prefix="abep-assess-py-"))
    try:
        for rel, text in a.get("files", {}).items():
            p = tmp / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
        root = tmp / a.get("root_rel", "base")
        root.mkdir(parents=True, exist_ok=True)
        return fn(root)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


MUTATED = []


def py_call(fn, a):
    """The reference call on decoded arguments; records any call that changed its inputs (INV-G-03)."""
    d = decode(copy.deepcopy(a))
    before = canon(d)
    r = _py_call(fn, d)
    if canon(d) != before:
        MUTATED.append(fn)
    return r


def _py_call(fn, a):
    if fn == "hard_constraints":
        return py_result(lambda: {"HARD_CONSTRAINTS": [dict(c) for c in DG.HARD_CONSTRAINTS],
                                  "HARD_CONSTRAINT_LIMITS": DG.HARD_CONSTRAINT_LIMITS,
                                  "GATE_THRESHOLDS_LIMITS": DG.GATE_THRESHOLDS["limits"],
                                  "PRE_EVALUATED_OBJECTIVES": list(DG.PRE_EVALUATED_OBJECTIVES)})
    if fn == "evaluate_constraints":
        return py_result(lambda: DG.evaluate_constraints(a["values"]))
    if fn == "hard_constraint_partition":
        return py_result(lambda: [list(map(list, x)) for x in DG.hard_constraint_partition(a["evaluations"])])
    if fn == "constraint_met_value_kinds":
        return py_result(lambda: sorted(DG.constraint_met_value_kinds(a["evaluations"])))
    if fn == "rfp_power_gate":
        return py_result(lambda: DG.bus_power_gate(a["steady"], a["startup"]))
    if fn == "bus_power_gate_verdict":
        if a["supplied"] is None:
            return py_result(lambda: DS.bus_power(FLIGHT, None, None)["gate_verdict"])
        return py_result(lambda: DS.bus_power(FLIGHT, None, a["supplied"])["gate_verdict"])
    if fn == "ripple_feed_quality":
        return py_result(lambda: DG.ripple_feed_quality(a["ripple_frac"], a["ripple_status"], h1tol(a["h1"])))
    if fn == "statewise_envelope":
        t = table_by_sid(a["margins"])
        return py_result(lambda: U13.statewise_envelope(a["requirement_id"], a["states"], lambda s: t[s["state_id"]],
                                                        a["value_status"]))
    if fn == "statewise_drag_compensation":
        st = a["states"]
        return py_result(lambda: DG.statewise_drag_compensation(st, positional_fn(a["thrust"], st),
                                                                positional_fn(a["drag"], st), a["hall_admitted"]))
    if fn == "feed_state_sufficiency":
        st = a["states"]
        req = None if a["required"] is None else positional_fn(a["required"], st)
        m = None if a["h1_map"] is None else H1Map(a["h1_map"]["status"], a["h1_map"]["table"], st)
        gate = 0.38e-6 if a["fixed_mass_flow_gate"] else None
        return py_result(lambda: DG.feed_state_sufficiency(st, positional_fn(a["offered"], st), req, m, gate))
    if fn == "pareto_s6_17":
        return py_result(lambda: DG.pareto_s6_17(a["rows"], weights=a["weights"]))
    if fn == "propellant_paths_check":
        return py_result(lambda: DG.propellant_paths_check(a["paths"]))
    if fn == "rvm_gate_snapshot":
        return py_result(lambda: DG.rvm_gate_snapshot())
    if fn == "owner_state":
        return py_result(lambda: DG.owner_state(a["qid"]))
    if fn == "status_label":
        return py_result(lambda: DG.status_label(a["qid"]))
    if fn == "apply_to_questions":
        return py_result(lambda: DG.apply_to_questions(a["questions"]))
    if fn == "icp45a_margin":
        return py_result(lambda: P1.icp45a_margin(a["i"], a["idm"], a["k"], a["ue"], a["ud"]))
    # ---- contract 2
    if fn == "rvm_vocabularies":
        return py_result(lambda: {
            "STATUSES": list(RR.STATUSES), "ROLES": list(RR.ROLES), "ARTIFACT_KINDS": list(RR.ARTIFACT_KINDS),
            "NOT_APPLICABLE_KIND": RR.NOT_APPLICABLE_KIND, "EVALUATING_KINDS": list(RR.EVALUATING_KINDS),
            "ARTIFACT_FIELDS": {k: (t.__name__ if isinstance(t, type) else "(" + ", ".join(x.__name__ for x in t) + ")")
                                for k, t in RR.ARTIFACT_FIELDS.items()},
            "RULES": dict(RR.RULES)})
    if fn == "validate_artifact":
        return py_result(lambda: RR.validate_artifact(a["artifact"]))
    if fn == "assign_status":
        return py_result(lambda: list(RR.assign_status(a["artifacts"], a["requirement_frozen"])))
    if fn == "is_not_applicable_cell":
        return py_result(lambda: RR.is_not_applicable_cell(a["artifacts"]))
    if fn == "floor_fail_check":
        return py_result(lambda: RR.floor_fail_check(a["readings"], a["limit"], a["strict"]))
    if fn in ("assert_status_vocabulary", "assert_no_pass_without_measurement"):
        doc = committed_rvm() if a["doc"] == "COMMITTED" else a["doc"]
        return py_result(lambda: getattr(RR, fn)(doc))
    if fn == "rvm_replay":
        def replay():
            d = committed_rvm()
            out = []
            for r in d["rows"]:
                for cfg, cell in r["configurations"].items():
                    s, rule, reason = RR.assign_status([{k: v for k, v in x.items() if k != "detail"}
                                                        for x in cell["artifacts"]], r["requirement_frozen"])
                    out.append([r["id"], cfg, s, rule, reason])
            return out
        return py_result(replay)
    if fn == "gng_icp_01_replay":
        g = next(x for x in committed_rvm()["owner_approved_gates"] if x["id"] == "GNG-ICP-01")
        return py_result(lambda: IG.evaluate(g["criteria"], g["evidence"]))
    if fn == "icp_gate_evaluate":
        return py_result(lambda: with_files(a, lambda root: IG.evaluate(a["criteria"], a["evidence"], root)))
    if fn == "lock1_release_reportable":
        return py_result(lambda: IG.lock1_release_reportable(a["gates"]))
    raise KeyError(fn)


_RVM = None


def committed_rvm():
    global _RVM
    if _RVM is None:
        _RVM = json.loads((ROOT / RR_PATH).read_text(encoding="utf-8"))
    return copy.deepcopy(_RVM)


RR_PATH = "docs/requirements/rvm_a9/rvm_a9_v1.json"


# ============================================================================================== expected Rust (DIVs)
def expected_rust(fn, a, py):
    """The registered DIV-01 transformation of the reference output (A9.31 sec. 10)."""
    if fn != "evaluate_constraints" or py["outcome"] != "RETURNED":
        return py
    rec = decode(a)["values"].get("M_n_LB") if isinstance(a.get("values"), dict) else None
    if not isinstance(rec, dict) or not rec.get("uncertainty_basis") or \
            rec.get("validation_basis") in ("VALIDATED_BENCH", "MEASURED"):
        return py
    out = copy.deepcopy(py)
    for row in out["value"]:
        if row["id"] == "HC-05":
            row["status"] = "NOT_EVALUATED"
            row["basis"] = A931_HC05_BASIS
    return out


# ============================================================================================== generators
STATUSES_OBJ = [EVALUATED, PARAMETRIC, INCOMPLETE, NOT_EV, SYN, "UNKNOWN_STATUS"]
U13_C = [U13.C_MET, U13.C_VIOLATED, U13.C_NOT_EVALUATED, U13.C_MET_PARAMETRIC, U13.C_VIOLATED_PARAMETRIC,
         U13.C_MET_SYNTHETIC, U13.C_VIOLATED_SYNTHETIC, "SOMETHING_ELSE", None]
CONSTRAINT_ST = [AO.C_MET, AO.C_VIOLATED, AO.C_NOT_EVALUATED, AO.C_MET_PARAMETRIC, AO.C_VIOLATED_PARAMETRIC]
VS = list(U13.VALUE_STATUSES)
EC = ["measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed", "owner-allocation"]
GM_OK = {"sample_rate_Sa_s": 100000.0, "bandwidth_Hz": 20000.0, "anti_alias_documented": True, "synchronized": True,
         "source": "bus channel record"}


def rand_value(rng, limit):
    u = rng.random()
    if u < 0.45:
        return limit * rng.uniform(0.5, 1.5) if limit else rng.uniform(-1, 1)
    if u < 0.55:
        return limit if limit is not None else 0.0
    if u < 0.65:
        return rng.randint(0, 3) * (int(limit) if limit and limit >= 1 else 1)
    if u < 0.72:
        return -0.0
    if u < 0.8:
        return float("inf") if rng.random() < 0.5 else float("-inf")
    if u < 0.88:
        return float("nan")
    return None


def gen_values(rng):
    vals = {}
    for c in DG.HARD_CONSTRAINTS:
        if rng.random() < 0.25:
            continue
        o = c["objective"]
        if o in DG.PRE_EVALUATED_OBJECTIVES:
            rec = {"status": rng.choice(U13_C)}
            if rng.random() < 0.4:
                rec["average_hides_violation"] = rng.choice([True, False, 1, 0])
        else:
            rec = {"status": rng.choice(STATUSES_OBJ), "value": rand_value(rng, c["limit"])}
            if c["id"] == "HC-05":
                if rng.random() < 0.7:
                    rec["uncertainty_basis"] = rng.choice(["P1-IT-29 one-sided", "", None])
                vb = rng.choice(["absent", None, "VALIDATED_BENCH", "MEASURED", "NOT_VALIDATED"])
                if vb != "absent":
                    rec["validation_basis"] = vb
            if c["id"] == "HC-03" and rng.random() < 0.6:
                rec["gate_verdict"] = rng.choice(["PASS", "FAIL", "NOT_EVALUABLE"])
        if rng.random() < 0.05:
            rec = None
        vals[o] = rec
    return vals


def gen_ledger(rng, label, target=None):
    inst = BB.installed_slots(FLIGHT, [])
    p_tbd = rng.choice([0.0, 0.0, 0.0, 0.1])
    loads, effs = {}, {}
    scale = (target or rng.uniform(600, 2400)) / len(inst)
    for s in inst:
        if rng.random() < p_tbd:
            rec = {"P_W": "TBD", "tbd_requires": "tbd:" + s}
        else:
            rec = {"P_W": round(rng.uniform(0, 2 * scale), rng.choice([0, 3, 6])), "evidence_class": rng.choice(EC),
                   "source": "src:" + s}
        if s == "icp_rf_source":
            rec["plane"] = "generator_dc_input"
        loads[s] = rec
        effs[s] = {"value": 1.0 if rng.random() < 0.3 else rng.uniform(0.85, 1.0), "evidence_class": rng.choice(EC),
                   "source": "eff:" + s, "path": rng.choice(["internal_bus", "direct"])}
    fe = {"value": rng.uniform(0.9, 1.0), "evidence_class": rng.choice(EC), "source": "fe"}
    basis = rng.choice([None] + list(BB.POWER_BASES))
    gm = rng.choice([None, GM_OK, dict(GM_OK, sample_rate_Sa_s=50000.0)])
    led = BB.ledger(FLIGHT, loads, effs, fe, (), label=label, power_basis=basis, gate_measurement=copy.deepcopy(gm))
    if rng.random() < 0.05:
        led = dict(led, boundary_version="bus_power_boundary_a9_v1")
    if rng.random() < 0.05:
        led = {k: v for k, v in led.items() if k != "booked_tbd_slots"}
    return led


def gen_states(rng, n, weighted=None):
    ids = [f"S{rng.randint(0, 40):02d}" if rng.random() < 0.15 else f"S{i:03d}" for i in range(n)]
    st = []
    for sid in ids:
        d = {"state_id": sid}
        if weighted:
            d["weight"] = rng.choice([1.0, 2, rng.uniform(0.1, 3.0)])
        st.append(d)
    return st


def value_rec(rng, sid, scale=0.03):
    s = rng.choice(VS + (["UNKNOWN"] if rng.random() < 0.03 else []))
    v = None if s == U13.VALUE_TBD and rng.random() < 0.7 else rng.uniform(0, scale)
    if rng.random() < 0.02:
        v = float("nan")
    return {"state_id": sid, "status": s, "value_N": v, "source": "harness"}


def build_gates(seed):
    calls = []

    def add(eid, fn, args):
        calls.append({"id": f"{eid}-{len(calls):05d}", "entry": eid, "fn": fn, "args": encode(args)})

    req_states = ISY.required_states()
    sids = [s.state_id for s in req_states]
    rho = [s.rho_kg_m3 for s in req_states]
    med = sorted(rho)[len(rho) // 2] if len(rho) % 2 else 0.5 * (sorted(rho)[len(rho) // 2 - 1] + sorted(rho)[len(rho) // 2])
    st196 = [{"state_id": i} for i in sids]
    # ---- golden
    add("E1", "hard_constraints", {})
    add("E2", "evaluate_constraints", {"values": {}})
    add("E2", "evaluate_constraints", {"values": {"P_bus_W": DS.bus_power(FLIGHT, None, None)}})
    gm_led = BB.ledger(FLIGHT, {s: {"P_W": 50.0, "evidence_class": "measured", "source": "m"} | (
        {"plane": "generator_dc_input"} if s == "icp_rf_source" else {}) for s in BB.installed_slots(FLIGHT, [])},
        {s: {"value": 1.0, "evidence_class": "measured", "source": "m", "path": "direct"}
         for s in BB.installed_slots(FLIGHT, [])}, {"value": 1.0, "evidence_class": "measured", "source": "fe"},
        (), label="G-04", power_basis="p_bus_1ms_max", gate_measurement=GM_OK)
    add("E5", "rfp_power_gate", {"steady": gm_led, "startup": [gm_led]})
    off = AO.official_ledger(FLIGHT)
    add("E5", "rfp_power_gate", {"steady": off, "startup": [off]})
    add("E6", "bus_power_gate_verdict", {"supplied": None})
    add("E8", "statewise_envelope", {"requirement_id": "PARITY-RHO-MED", "states": st196,
                                     "margins": [[i, r - med] for i, r in zip(sids, rho)], "value_status": "EVIDENCE"})
    tbd = [{"state_id": i, "status": "TBD", "value_N": None} for i in sids]
    ref = [{"state_id": i, "status": U13.VALUE_REFERENCE, "value_N": 0.001 + 1e-6 * k} for k, i in enumerate(sids)]
    add("E9", "statewise_drag_compensation", {"states": st196, "thrust": tbd, "drag": ref, "hall_admitted": False})
    syn_t = [{"state_id": i, "status": U13.VALUE_SYNTHETIC, "value_N": 0.012} for i in sids]
    syn_d = [{"state_id": i, "status": U13.VALUE_SYNTHETIC, "value_N": 0.011 + 2e-5 * (k % 100)} for k, i in enumerate(sids)]
    add("E9", "statewise_drag_compensation", {"states": st196, "thrust": syn_t, "drag": syn_d, "hall_admitted": False})
    add("E10", "feed_state_sufficiency", {"states": st196[:5], "offered": [{} for _ in range(5)], "required": None,
                                          "h1_map": None, "fixed_mass_flow_gate": False})
    add("E12", "propellant_paths_check", {"paths": AO.MODELLED_PROPELLANT_PATHS})
    add("E12", "propellant_paths_check", {"paths": None})
    add("E13", "rvm_gate_snapshot", {})
    oq = json.loads((ROOT / DG.OQ5_REL).read_text())
    for qid in sorted({r["id"] for r in oq["rows"]}) + ["NO-SUCH-ID"]:
        add("E14", "owner_state", {"qid": qid})
        add("E14", "status_label", {"qid": qid})
    add("E15", "icp45a_margin", {"i": 10.0, "idm": 8.0, "k": 1.6448536269514722, "ue": 0.2, "ud": 0.1})
    # ---- edge cases
    hc05 = lambda **kw: {"values": {"M_n_LB": {"status": EVALUATED, "value": 0.2, **kw}}}  # noqa: E731
    add("E2", "evaluate_constraints", hc05())
    add("E2", "evaluate_constraints", hc05(uncertainty_basis="UB"))
    for vb in ("VALIDATED_BENCH", "MEASURED", "NOT_VALIDATED", None):
        add("E2", "evaluate_constraints", hc05(uncertainty_basis="UB", validation_basis=vb))
        add("E2", "evaluate_constraints", {"values": {"M_n_LB": {"status": EVALUATED, "value": -0.1,
                                                                 "uncertainty_basis": "UB", "validation_basis": vb}}})
    for vs in STATUSES_OBJ:
        for gv in ("PASS", "FAIL", "NOT_EVALUABLE"):
            add("E2", "evaluate_constraints", {"values": {"P_bus_W": {"status": vs, "value": 1400.0, "gate_verdict": gv}}})
    for v in (-0.0, 0, 3, 0.012, 0.025, 1500.0, 1500, 40.0, 39.999999, float("inf"), float("nan"), 15000.0, 50.0):
        add("E2", "evaluate_constraints", {"values": {o: {"status": EVALUATED, "value": v} for o in
                                                      ("thrust_N", "thrust_capability_N", "P_bus_W", "m_wet_kg",
                                                       "thermal_margin_K", "firing_life_h", "drag_intake_max_N",
                                                       "propellant_capability")}})
        add("E2", "evaluate_constraints", {"values": {o: {"status": PARAMETRIC, "value": v} for o in
                                                      ("thrust_N", "m_wet_kg", "firing_life_h")}})
    for st in U13_C:
        add("E2", "evaluate_constraints", {"values": {o: {"status": st, "average_hides_violation": True}
                                                      for o in DG.PRE_EVALUATED_OBJECTIVES}})
    for bad in ([], "x", {"a": 1}):
        add("E5", "rfp_power_gate", {"steady": gm_led, "startup": bad})
    add("E5", "rfp_power_gate", {"steady": dict(gm_led, boundary_version="v0"), "startup": [gm_led]})
    add("E5", "rfp_power_gate", {"steady": "not a ledger", "startup": [gm_led]})
    for basis in BB.POWER_BASES + (None,):
        for tot in (1000.0, 1499.999, 1500.0, 2000.0):
            l2 = dict(gm_led, power_basis=basis, P_bus_W=tot)
            add("E5", "rfp_power_gate", {"steady": l2, "startup": [l2]})
            l3 = dict(l2, gate_measurement_conformant=False)
            add("E5", "rfp_power_gate", {"steady": l3, "startup": [gm_led]})
            l4 = dict(l2, P_bus_W=None, status="INCOMPLETE_EVIDENCE", P_bus_lower_bound_W=tot)
            add("E5", "rfp_power_gate", {"steady": l4, "startup": [l4]})
    h_ok = {"quantity": "ripple", "value_frac": 0.05, "status": "EVIDENCE", "source": "H-1 measured"}
    for rf in (0.01, 0.05, 0.06, 0, None, -0.1, True, float("nan"), float("inf"), 1):
        for rs in ("EVIDENCE", "TBD", "PARAMETRIC_SENSITIVITY", "BOGUS"):
            for h in (None, h_ok, {"quantity": "ripple", "value_frac": None, "status": "TBD", "source": "tbd"},
                      dict(h_ok, quantity="pressure"), dict(h_ok, status="SYNTHETIC_TEST_DATA_NOT_EVIDENCE"),
                      dict(h_ok, status="BOGUS"), dict(h_ok, quantity="nope"), dict(h_ok, value_frac=-1.0),
                      dict(h_ok, source="  ")):
                add("E7", "ripple_feed_quality", {"ripple_frac": rf, "ripple_status": rs, "h1": h})
    add("E8", "statewise_envelope", {"requirement_id": "X", "states": st196[:3], "margins": [[i, 1.0] for i in sids[:3]],
                                     "value_status": "NOPE"})
    add("E8", "statewise_envelope", {"requirement_id": "X", "states": [], "margins": [], "value_status": "EVIDENCE"})
    add("E8", "statewise_envelope", {"requirement_id": "X", "states": [{"state_id": "a", "weight": -1.0}],
                                     "margins": [["a", 1.0]], "value_status": "EVIDENCE"})
    for m in (0.0, -0.0, -1e-300, float("nan")):
        for vs in VS:
            add("E8", "statewise_envelope", {"requirement_id": "E", "states": [{"state_id": "a"}, {"state_id": "b"}],
                                             "margins": [["a", m], ["b", 1.0]], "value_status": vs})
    add("E9", "statewise_drag_compensation", {"states": [], "thrust": [], "drag": [], "hall_admitted": False})
    one = [{"state_id": "a"}]
    add("E9", "statewise_drag_compensation", {"states": one, "thrust": [{"state_id": "b", "status": "TBD"}],
                                              "drag": [{"state_id": "a", "status": "TBD"}], "hall_admitted": False})
    add("E9", "statewise_drag_compensation", {"states": one, "thrust": [{"state_id": "a", "status": "TBD"}],
                                              "drag": [{"state_id": "c", "status": "TBD"}], "hall_admitted": False})
    add("E9", "statewise_drag_compensation", {"states": one, "thrust": [{"state_id": "a", "status": "XX"}],
                                              "drag": [{"state_id": "a", "status": "TBD"}], "hall_admitted": False})
    add("E9", "statewise_drag_compensation", {"states": one, "thrust": [{"state_id": "a", "status": "EVIDENCE",
                                                                         "value_N": float("inf")}],
                                              "drag": [{"state_id": "a", "status": "EVIDENCE", "value_N": 0.01}],
                                              "hall_admitted": True})
    for adm in (True, False):
        add("E9", "statewise_drag_compensation", {
            "states": [{"state_id": "a"}, {"state_id": "b"}],
            "thrust": [{"state_id": "a", "status": "EVIDENCE", "value_N": 0.02},
                       {"state_id": "b", "status": "EVIDENCE", "value_N": 0.005}],
            "drag": [{"state_id": "a", "status": "EVIDENCE", "value_N": 0.01},
                     {"state_id": "b", "status": "EVIDENCE", "value_N": 0.01}], "hall_admitted": adm})
    feed_ok = {"mdot_kgps": 1e-6, "P_Pa": 0.5, "T_K": 300.0, "x_mole": {"N2": 0.8}, "ripple_frac": 0.01,
               "status": "EVIDENCE"}
    req_ok = {"mdot_kgps": 0.9e-6, "P_Pa": 0.4, "T_range_K": [250.0, 350.0], "x_domain_ok": True,
              "ripple_tolerance_frac": 0.02}
    two = [{"state_id": "a"}, {"state_id": "b"}]
    rt = [{"state_id": "a", "status": "EVIDENCE", "value_N": 0.012}, {"state_id": "b", "status": "EVIDENCE",
                                                                         "value_N": 0.012}]
    add("E10", "feed_state_sufficiency", {"states": two, "offered": [feed_ok, feed_ok], "required": rt,
                                          "h1_map": {"status": "VALIDATED", "table": [req_ok, req_ok]},
                                          "fixed_mass_flow_gate": True})
    for ms in ("VALIDATED", U13.SYNTHETIC, "DRAFT", ""):
        add("E10", "feed_state_sufficiency", {"states": two, "offered": [feed_ok, dict(feed_ok, ripple_frac=0.0)],
                                              "required": rt, "h1_map": {"status": ms, "table": [req_ok, None]},
                                              "fixed_mass_flow_gate": False})
    add("E10", "feed_state_sufficiency", {"states": two, "offered": [feed_ok, feed_ok], "required": None,
                                          "h1_map": {"status": "VALIDATED", "table": [req_ok, req_ok]},
                                          "fixed_mass_flow_gate": False})
    add("E10", "feed_state_sufficiency", {"states": two, "offered": [dict(feed_ok, P_Pa=None), feed_ok], "required": rt,
                                          "h1_map": {"status": "VALIDATED", "table": [req_ok, req_ok]},
                                          "fixed_mass_flow_gate": False})
    add("E10", "feed_state_sufficiency", {"states": two, "offered": [feed_ok, feed_ok],
                                          "required": [rt[0], dict(rt[1], state_id="z")],
                                          "h1_map": {"status": "VALIDATED", "table": [req_ok, req_ok]},
                                          "fixed_mass_flow_gate": False})
    add("E11", "pareto_s6_17", {"rows": [], "weights": {"a": 1}})
    add("E11", "pareto_s6_17", {"rows": [{"id": "a", "constraints": {"x": AO.C_VIOLATED}},
                                         {"id": "b", "constraints": {"x": AO.C_NOT_EVALUATED},
                                          "objectives": {k: 1.0 for k, _, _ in U13.PARETO_OBJECTIVES_S6_17}},
                                         {"id": "c", "objectives": {k: True for k, _, _ in U13.PARETO_OBJECTIVES_S6_17}}],
                                "weights": None})
    paths = AO.MODELLED_PROPELLANT_PATHS
    for p in ({"air": [], "xe": paths["xe"]}, {"air": paths["air"]}, {"air": ["filter", "intake", "compressor"],
              "xe": ["xe_tank"]}, {"air": paths["air"], "xe": ["xe_tank", "atmospheric_gas_chamber"]},
              {"air": paths["air"], "xe": ["xe_tank", "c1_feed"]}, {"air": ["compressor", "intake"], "xe": ["tank_b"]},
              {"air": ["intake", "compressor"], "xe": ["xe_tank", "cathode_x", "hollow_cathode"]}):
        add("E12", "propellant_paths_check", {"paths": p})
    # ---- randomized (one generator per entry)
    counts = {"E2": 600, "E3": 150, "E4": 150, "E5": 500, "E6": 150, "E7": 400, "E8": 300, "E9": 300, "E10": 300,
              "E11": 300, "E12": 300, "E14": 150, "E15": 300}
    rng = lambda e: random.Random(seed * 1000 + e)  # noqa: E731
    r = rng(2)
    for _ in range(counts["E2"]):
        add("E2", "evaluate_constraints", {"values": gen_values(r)})
    for e, fn in ((3, "hard_constraint_partition"), (4, "constraint_met_value_kinds")):
        r = rng(e)
        for _ in range(counts[f"E{e}"]):
            evs = []
            for j in range(r.randint(1, 6)):
                cs = [{"id": f"HC-{k:02d}", "status": r.choice(CONSTRAINT_ST + [U13.C_MET_SYNTHETIC]),
                       "value_status": r.choice(STATUSES_OBJ + [None])} for k in range(1, r.randint(1, 13))]
                evs.append({"vector": f"v{j}", "constraints": cs})
            add(f"E{e}", fn, {"evaluations": evs})
    r = rng(5)
    pairs = []
    for k in range(counts["E5"]):
        steady = gen_ledger(r, f"steady{k}")
        steps = [gen_ledger(r, f"step{k}.{j}") for j in range(r.randint(1, 4))]
        pairs.append((steady, steps))
        add("E5", "rfp_power_gate", {"steady": steady, "startup": steps})
    r = rng(6)
    for _ in range(counts["E6"]):
        steady, steps = r.choice(pairs)
        sup = {"steady": steady, "startup": steps}
        if r.random() < 0.3:
            sup["synthetic"] = True
        add("E6", "bus_power_gate_verdict", {"supplied": sup})
    r = rng(7)
    for _ in range(counts["E7"]):
        rf = r.choice([r.uniform(0, 0.2), 0, 1, None, -r.uniform(0, 1), float("nan"), True])
        h = r.choice([None, {"quantity": "ripple", "value_frac": r.uniform(0.01, 0.2),
                             "status": r.choice(VS[:-1] + ["NOPE"]), "source": "s"},
                      {"quantity": "ripple", "value_frac": None, "status": "TBD", "source": "s"}])
        add("E7", "ripple_feed_quality", {"ripple_frac": rf, "ripple_status": r.choice(VS + ["NOPE"]), "h1": h})
    r = rng(8)
    for _ in range(counts["E8"]):
        st = gen_states(r, r.randint(2, 12), weighted=r.random() < 0.3)
        m = [[s["state_id"], r.choice([r.uniform(-1, 1), 0.0, -0.0])] for s in st]
        add("E8", "statewise_envelope", {"requirement_id": "AG-R", "states": st, "margins": m,
                                         "value_status": r.choice(VS)})
    r = rng(9)
    for _ in range(counts["E9"]):
        st = gen_states(r, r.randint(2, 10), weighted=r.random() < 0.2)
        add("E9", "statewise_drag_compensation", {"states": st, "thrust": [value_rec(r, s["state_id"]) for s in st],
                                                  "drag": [value_rec(r, s["state_id"]) for s in st],
                                                  "hall_admitted": r.random() < 0.5})
    r = rng(10)
    for _ in range(counts["E10"]):
        st = gen_states(r, r.randint(2, 8))
        offered, table = [], []
        for s in st:
            o = {k: v * r.uniform(0.5, 2) if isinstance(v, float) else v for k, v in feed_ok.items()}
            o["ripple_frac"] = r.choice([0.0, r.uniform(0, 0.05)])
            o["status"] = r.choice(VS[:-1] + ["TBD"])
            if r.random() < 0.1:
                o[r.choice(list(U13.FEED_STATE_FIELDS))] = None
            if r.random() < 0.05:
                del o["status"]
            offered.append(o)
            table.append(None if r.random() < 0.1 else {**req_ok, "x_domain_ok": r.random() < 0.9,
                                                        "T_range_K": [r.uniform(200, 320), r.uniform(320, 400)]})
        req = None if r.random() < 0.05 else [value_rec(r, s["state_id"]) for s in st]
        mp = None if r.random() < 0.05 else {"status": r.choice(["VALIDATED", U13.SYNTHETIC, "DRAFT"]), "table": table}
        add("E10", "feed_state_sufficiency", {"states": st, "offered": offered, "required": req, "h1_map": mp,
                                              "fixed_mass_flow_gate": r.random() < 0.02})
    r = rng(11)
    keys = [k for k, _, _ in U13.PARETO_OBJECTIVES_S6_17]
    for _ in range(counts["E11"]):
        rows = []
        for j in range(r.randint(2, 10)):
            row = {"id": f"r{r.randint(0, 99):02d}"}
            if r.random() < 0.9:
                row["constraints"] = {f"HC-{k:02d}": r.choice(CONSTRAINT_ST) for k in r.sample(range(1, 13), r.randint(0, 4))}
            if r.random() < 0.95:
                row["objectives"] = {k: r.choice([float(r.randint(0, 3)), r.uniform(0, 1), r.uniform(0, 1),
                                                  float("nan"), None, True]) for k in keys if r.random() < 0.97}
            rows.append(row)
        add("E11", "pareto_s6_17", {"rows": rows, "weights": None})
    r = rng(12)
    names = list(U13.AIR_PATH) + list(U13.XE_PATH) + ["xe_tank_2", "cathode_x", "c1", "chamber_shared"]
    for _ in range(counts["E12"]):
        air = list(U13.AIR_PATH)
        xe = list(U13.XE_PATH)
        for lst in (air, xe):
            for _ in range(r.randint(0, 2)):
                op = r.random()
                if op < 0.3 and lst:
                    lst.pop(r.randrange(len(lst)))
                elif op < 0.6:
                    lst.insert(r.randint(0, len(lst)), r.choice(names))
                elif len(lst) > 1:
                    i, j = r.sample(range(len(lst)), 2)
                    lst[i], lst[j] = lst[j], lst[i]
        p = {"air": air, "xe": xe}
        if r.random() < 0.05:
            p = None
        add("E12", "propellant_paths_check", {"paths": p})
    r = rng(14)
    ids = sorted({x["id"] for x in oq["rows"]})
    for _ in range(counts["E14"]):
        qs = []
        for _ in range(r.randint(1, 5)):
            q = {"id": r.choice(ids + ["UNKNOWN-1", "UNKNOWN-2"]), "text": "q"}
            if r.random() < 0.5:
                q["status"] = r.choice(["TBD_OWNER", "RAISED", "OPEN"])
            if r.random() < 0.2:
                q["status_as_raised"] = "OLD"
            qs.append(q)
        add("E14", "apply_to_questions", {"questions": qs})
    r = rng(15)
    for _ in range(counts["E15"]):
        add("E15", "icp45a_margin", {"i": r.uniform(0, 20), "idm": r.uniform(0.5, 10), "k": r.uniform(1.6, 3),
                                     "ue": r.uniform(1e-4, 1), "ud": r.uniform(1e-4, 1)})
    return calls


# ---------------------------------------------------------------------------------------------- contract 2
FIELDS = list(RR.ARTIFACT_FIELDS)


def rand_artifact(r, k):
    kind = r.choice(RR.ARTIFACT_KINDS)
    a = {"path": r.choice(["docs/x.json", ""]) if r.random() < 0.05 else "docs/x.json",
         "id": f"A{k}", "role": r.choice(RR.ROLES + (("BOGUS",) if r.random() < 0.03 else ())),
         "kind": kind if r.random() > 0.02 else "BOGUS", "evidence_state": "state",
         "evaluated": r.random() < 0.6, "verified": r.random() < 0.5, "measured": kind == "MEASUREMENT",
         "synthetic": r.random() < 0.02, "in_domain": r.choice([True, False, None]),
         "meets": r.choice([True, False, None]), "coverage_complete": r.random() < 0.5,
         "evidenced_terms": r.randint(0, 4), "numerical_failure": r.random() < 0.15,
         "lower_bound_verified": kind == "BUDGET_EVALUATION" and r.random() < 0.5,
         "exceeds_limit_every_reading": r.choice([True, False, None]) if kind == "BUDGET_EVALUATION" else None}
    if a["kind"] not in RR.EVALUATING_KINDS and r.random() < 0.9:
        a["evaluated"] = False
    if not a["evaluated"] and r.random() < 0.9:
        a["meets"] = None
    if a["kind"] != "MEASUREMENT" and a["meets"] is True and r.random() < 0.9:
        a["meets"] = None
    u = r.random()
    if u < 0.04:
        del a[r.choice(FIELDS)]
    elif u < 0.08:
        a[r.choice(FIELDS)] = r.choice([1, 0, "x", None, 1.0, -1, [], True])
    return a


def build_rvm(seed):
    calls = []

    def add(eid, fn, args):
        calls.append({"id": f"{eid}-{len(calls):05d}", "entry": eid, "fn": fn, "args": encode(args)})

    add("R1", "rvm_vocabularies", {})
    add("R6", "rvm_replay", {})
    add("R5", "assert_status_vocabulary", {"doc": "COMMITTED"})
    add("R5", "assert_no_pass_without_measurement", {"doc": "COMMITTED"})
    add("R8", "gng_icp_01_replay", {})
    add("R8", "lock1_release_reportable", {"gates": [{"status": "NOT_EVALUATED", "mandatory": True}]})
    add("R7", "icp_gate_evaluate", {"criteria": "PENDING_OWNER_ACCEPTANCE", "evidence": []})
    add("R7", "icp_gate_evaluate", {"criteria": None, "evidence": None})
    base = {"path": "p", "id": "M1", "role": "DETERMINING", "kind": "MEASUREMENT", "evidence_state": "s",
            "evaluated": True, "verified": True, "measured": True, "synthetic": False, "in_domain": True, "meets": True,
            "coverage_complete": True, "evidenced_terms": 1, "numerical_failure": False, "lower_bound_verified": False,
            "exceeds_limit_every_reading": None}
    # ER-01 / ER-02
    for f in FIELDS:
        add("R2", "validate_artifact", {"artifact": {k: v for k, v in base.items() if k != f}})
        for bad in (1, True, -1, "x", 1.5, [], None):
            add("R2", "validate_artifact", {"artifact": dict(base, **{f: bad})})
    for mut in ({"synthetic": True}, {"kind": "BUDGET_EVALUATION"}, {"measured": False},
                {"kind": "PLAN_OR_FRAMEWORK", "measured": False}, {"evaluated": False},
                {"kind": "BUDGET_EVALUATION", "measured": False, "meets": True},
                {"lower_bound_verified": True}, {"exceeds_limit_every_reading": True}, {"path": ""}, {"id": ""},
                {"role": "X"}, {"kind": "X"}):
        add("R2", "validate_artifact", {"artifact": dict(base, **mut)})
    add("R2", "validate_artifact", {"artifact": "not a dict"})
    # ER-03 / ER-04
    add("R3", "assign_status", {"artifacts": [base], "requirement_frozen": 1})
    add("R3", "assign_status", {"artifacts": [], "requirement_frozen": True})
    na = dict(base, kind="NOT_APPLICABLE_GROUND_REFERENCE", measured=False, evaluated=False, meets=None)
    add("R3", "assign_status", {"artifacts": [na, base], "requirement_frozen": True})
    add("R3", "assign_status", {"artifacts": [dict(base, role="SUPPORTING")], "requirement_frozen": True})
    budget = dict(base, kind="BUDGET_EVALUATION", measured=False, meets=None, verified=False)
    for arts, fr in (([dict(budget, numerical_failure=True)], True), ([dict(base, meets=False)], True),
                     ([base], True), ([base], False), ([dict(base, coverage_complete=False)], True),
                     ([dict(budget, lower_bound_verified=True, exceeds_limit_every_reading=True)], True),
                     ([dict(budget, in_domain=False)], True), ([budget], True),
                     ([dict(budget, evidenced_terms=0)], True), ([na], True)):
        add("R3", "assign_status", {"artifacts": arts, "requirement_frozen": fr})
        add("R3", "is_not_applicable_cell", {"artifacts": arts})
    # ER-05
    add("R4", "floor_fail_check", {"readings": [], "limit": 40, "strict": True})
    for v in (float("nan"), float("inf"), True, "x", None):
        add("R4", "floor_fail_check", {"readings": [{"reading": "r", "floor_only_kg": v}], "limit": 40, "strict": True})
    for strict in (True, False):
        add("R4", "floor_fail_check", {"readings": [{"reading": "a", "floor_only_kg": 40}, {"reading": "b",
                                       "floor_only_kg": 40.0000001}], "limit": 40.0, "strict": strict})
    # ER-06
    d = committed_rvm()
    d2 = copy.deepcopy(d)
    d2["rows"][0]["configurations"][FLIGHT]["status"] = "GREEN"
    add("R5", "assert_status_vocabulary", {"doc": d2})
    d3 = copy.deepcopy(d)
    d3["status_vocabulary"] = list(reversed(d3["status_vocabulary"]))
    add("R5", "assert_status_vocabulary", {"doc": d3})
    d4 = copy.deepcopy(d)
    d4["rows"][1]["configurations"][FLIGHT]["status"] = "PASS"
    add("R5", "assert_no_pass_without_measurement", {"doc": d4})
    d5 = copy.deepcopy(d4)
    d5["rows"][1]["configurations"][FLIGHT]["artifacts"].append(base)
    add("R5", "assert_no_pass_without_measurement", {"doc": d5})
    # ER-07 (scratch files)
    files = {"base/decision.md": "owner decision text\n", "base/ev1.json": "{\"met\": 1}\n",
             "base/ev2.json": "{\"met\": 2}\n", "outside.md": "outside\n", "base/sub/ev3.json": "three\n"}
    shas = {k: sha_bytes(v.encode()) for k, v in files.items()}
    dec = {"path": "decision.md", "sha256": shas["base/decision.md"]}
    items = [{"id": "C1", "text": "electron current at the registered H-1 point"}, {"id": "C2", "text": "ignition"}]
    ev = [{"criterion_id": "C1", "result": "MET", "source": {"path": "ev1.json", "sha256": shas["base/ev1.json"]}},
          {"criterion_id": "C2", "result": "MET", "source": {"path": "sub/ev3.json", "sha256": shas["base/sub/ev3.json"]}}]
    acc = {"status": "OWNER_ACCEPTED", "owner_decision": dec, "items": items}
    prop = next(p for p in A19.RECORDER_PROPOSALS if p["id"] == "RP-A919-01")["proposal"]
    er07 = [
        ({"status": "PENDING"}, ev), (dict(acc, note="see RP-A919-01"), ev), (dict(acc, note="recorder proposal"), ev),
        (dict(acc, items=[{"id": "C1"}]), ev), (dict(acc, items=["C1"]), ev),
        (dict(acc, items=[{"id": "C1", "text": prop[10:60]}]), ev), (dict(acc, owner_decision=None), ev),
        (dict(acc, owner_decision={"path": "decision.md", "sha256": "abc"}), ev),
        (dict(acc, owner_decision={"path": "decision.md", "sha256": "0" * 64}), ev),
        (dict(acc, owner_decision={"path": "decision.md", "sha256": shas["base/decision.md"] + "\n"}), ev),
        (dict(acc, owner_decision={"path": "../outside.md", "sha256": shas["outside.md"]}), ev),
        (dict(acc, owner_decision={"path": "missing.md", "sha256": shas["outside.md"]}), ev),
        (dict(acc, items=[]), ev), (dict(acc, items=[{"id": "C1", "text": "a"}, {"id": "C1", "text": "b"}]), ev),
        (dict(acc, items=[{"id": "", "text": "a"}]), ev), (acc, []), (acc, [ev[0]]),
        (acc, [ev[0], dict(ev[1], result="NOT_MET")]), (acc, ev), (acc, ev + ["junk", 3]),
        (acc, [ev[0], dict(ev[1], source={"path": "sub/ev3.json", "sha256": "1" * 64})]),
        (acc, [ev[0], dict(ev[1], result="MAYBE")]), (acc, [ev[0], dict(ev[1], source=None)]),
    ]
    for c, e in er07:
        add("R7", "icp_gate_evaluate", {"criteria": c, "evidence": e, "files": files, "root_rel": "base"})
    for g in ([], [{"status": "GO", "mandatory": False}], [{"mandatory": True}], [{"status": "GO"}],
              [{"status": "GO", "mandatory": 0}, {"status": "NO_GO", "mandatory": 1}]):
        add("R8", "lock1_release_reportable", {"gates": g})
    # randomized
    rng = lambda e: random.Random(seed * 1000 + e)  # noqa: E731
    r = rng(2)
    for k in range(500):
        add("R2", "validate_artifact", {"artifact": rand_artifact(r, k)})
    r = rng(3)
    for k in range(1000):
        arts = [rand_artifact(r, f"{k}.{j}") for j in range(r.randint(1, 5))]
        add("R3", "assign_status", {"artifacts": arts, "requirement_frozen": r.random() < 0.5})
    r = rng(4)
    for _ in range(400):
        rd = [{"reading": f"r{j}", "floor_only_kg": r.choice([r.uniform(0, 80), float(r.randint(0, 80)), r.randint(0, 80)])}
              for j in range(r.randint(1, 6))]
        add("R4", "floor_fail_check", {"readings": rd, "limit": r.choice([40, 40.0, r.uniform(0, 80)]),
                                       "strict": r.random() < 0.5})
    r = rng(7)
    for _ in range(500):
        its = [{"id": r.choice(["C1", "C2", "C3", "C4", ""]), "text": r.choice(["alpha", "beta", prop[:30], "", "gamma"])}
               for _ in range(r.randint(1, 4))]
        c = {"status": r.choice(["OWNER_ACCEPTED", "OWNER_ACCEPTED", "PENDING_OWNER_ACCEPTANCE"]),
             "owner_decision": r.choice([dec, dict(dec, sha256="2" * 64), {"path": "../outside.md",
                                                                          "sha256": shas["outside.md"]}, dec]),
             "items": its}
        evs = []
        for _ in range(r.randint(0, 6)):
            src = r.choice([{"path": "ev1.json", "sha256": shas["base/ev1.json"]},
                            {"path": "ev2.json", "sha256": shas["base/ev2.json"]},
                            {"path": "ev2.json", "sha256": shas["base/ev1.json"]}])
            evs.append({"criterion_id": r.choice(["C1", "C2", "C3", "C4"]), "result": r.choice(["MET", "NOT_MET", "X"]),
                        "source": src})
        add("R7", "icp_gate_evaluate", {"criteria": c, "evidence": evs, "files": files, "root_rel": "base"})
    r = rng(8)
    for _ in range(200):
        gs = []
        for _ in range(r.randint(0, 5)):
            g = {}
            st = r.choice(["GO", "NO_GO", "NOT_EVALUATED", None])
            if st is not None:
                g["status"] = st
            m = r.choice([True, False, "absent", 0, 1])
            if m != "absent":
                g["mandatory"] = m
            gs.append(g)
        add("R8", "lock1_release_reportable", {"gates": gs})
    return calls


# ============================================================================================== Rust side
def cargo_build() -> Path:
    env = dict(os.environ, PATH=f"/root/.cargo/bin:{os.environ.get('PATH', '')}", CARGO_INCREMENTAL="0")
    subprocess.run(["cargo", "build", "--release", "--locked", "-p", "abep-assess", "--bin", "abep-assess-parity"],
                   cwd=ROOT, check=True, env=env, capture_output=True)
    return ROOT / "target" / "release" / "abep-assess-parity"


def rust_eval(binary: Path, calls, work: Path, tag: str):
    p = work / f"calls_{tag}.json"
    p.write_text(json.dumps([{"fn": c["fn"], "args": c["args"]} for c in calls], ensure_ascii=False), encoding="utf-8")
    r = subprocess.run([str(binary), "--repo", str(ROOT), "eval", str(p)], capture_output=True, check=True)
    return json.loads(r.stdout), r.stdout


# ============================================================================================== comparison
def tree_ulp(p, r, path, stats):
    if isinstance(p, float) and isinstance(r, float):
        if p == r and math.copysign(1, p) == math.copysign(1, r):
            return []
        d = abs(p - r)
        u = d / ulp(p)
        stats["max_ulp"] = max(stats["max_ulp"], u)
        return [] if u <= 4 else [f"{path}: {p!r} vs {r!r} ({u:.3g} ulp)"]
    if isinstance(p, dict) and isinstance(r, dict):
        if list(p) != list(r):
            return [f"{path}: keys {list(p)} != {list(r)}"]
        out = []
        for k in p:
            out += tree_ulp(p[k], r[k], f"{path}.{k}", stats)
        return out
    return [] if canon(p) == canon(r) else [f"{path}: {canon(p)[:200]} != {canon(r)[:200]}"]


def compare(call, py, rs, stats):
    if py["outcome"] != rs["outcome"]:
        return [f"outcome {py['outcome']} != {rs['outcome']} (py {py.get('class')}: {py.get('message')!r}; rust "
                f"{rs.get('class')}: {rs.get('message')!r})"]
    if py["outcome"] == "RAISED":
        if py["class"] in MESSAGE_CLASSES:
            if py["class"] != rs["class"]:
                return [f"class {py['class']} != {rs['class']} ({py['message']!r} / {rs['message']!r})"]
            if py["message"] != rs["message"]:
                return [f"message: py {py['message']!r} | rust {rs['message']!r}"]
        stats["raised_other"] += py["class"] not in MESSAGE_CLASSES
        return []
    if call["fn"] == "icp45a_margin":
        return tree_ulp(py["value"], rs["value"], "$", stats)
    a, b = canon(py["value"]), canon(rs["value"])
    if a == b:
        stats["bit_identical"] += 1
        return []
    return [f"value differs: py {a[:400]} | rust {b[:400]}"]


# ============================================================================================== invariants
STATUS_KEYS = {"status", "state_status"}
FORBIDDEN_STATUS = {"PASS", "COMPLY", "COMPLIES", "SELECTED", "WINNER", "QUALIFIED", "OPTIMUM"}


def status_words(v, out):
    if isinstance(v, dict):
        for k, x in v.items():
            if k in STATUS_KEYS and isinstance(x, str):
                out.add(x)
            status_words(x, out)
    elif isinstance(v, list):
        for x in v:
            status_words(x, out)
    return out


def inv_gates(calls, pys, rss, rss2):
    inv = {}
    bad = []
    for c, p in zip(calls, rss):
        if p["outcome"] != "RETURNED":
            continue
        if c["fn"] == "evaluate_constraints":
            for row in p["value"]:
                if row["status"] == AO.C_MET and row["value_status"] not in (EVALUATED, SYN):
                    bad.append(c["id"])
                if row["id"] == "HC-05" and row["status"] in (AO.C_MET, AO.C_VIOLATED):
                    rec = decode(c["args"])["values"].get("M_n_LB") or {}
                    if not (rec.get("uncertainty_basis") and rec.get("validation_basis") in ("VALIDATED_BENCH", "MEASURED")):
                        bad.append(c["id"] + ":HC05")
        if c["entry"] in ("E2", "E7", "E8", "E9", "E10", "E11", "E12") and status_words(p["value"], set()) & FORBIDDEN_STATUS:
            bad.append(c["id"] + ":word")
    inv["INV-G-01 (no MET on non-evidence; no PASS / COMPLY status value in E2 / E7-E12)"] = not [b for b in bad if not b.endswith(":HC05")]
    inv["INV-G-02 (HC-05 MET / VIOLATED only with a VALIDATED_BENCH / MEASURED basis, Rust)"] = not [b for b in bad if b.endswith(":HC05")]
    inv["INV-G-03 (inputs unchanged by every reference call; Rust borrows &Value immutably)"] = not MUTATED
    src = "\n".join(p.read_text() for p in sorted((ROOT / "crates/abep-assess/src").rglob("*.rs")))
    code = "\n".join(line.split("//")[0] for line in src.splitlines())
    lits = re.findall(r"(?<![\w.])(1500(?:\.0)?|40\.0|0\.012|0\.025|50\.0|15000(?:\.0)?)(?![\w.])", code)
    inv["INV-G-04 (no requirement literal in crates/abep-assess/src)"] = not lits
    inv["INV-G-05 (statewise quantifier called, not re-implemented)"] = (
        "fn statewise_quantifier" not in src and "abep_mission::statewise::statewise_quantifier" in src)
    inv["INV-G-06 (two Rust runs byte-identical)"] = rss2
    return inv, bad


def inv_rvm(calls, pys, rss, rss2):
    inv = {}
    ok1 = True
    for c, p in zip(calls, rss):
        if c["fn"] == "assign_status" and p["outcome"] == "RETURNED" and p["value"][0] == "PASS":
            a = decode(c["args"])
            det = [x for x in a["artifacts"] if x["role"] == "DETERMINING"]
            if not (a["requirement_frozen"] is True and any(
                    x["kind"] == "MEASUREMENT" and x["verified"] and x["measured"] and x["in_domain"] is True and
                    x["meets"] is True and x["coverage_complete"] for x in det)):
                ok1 = False
    inv["INV-R-01 (PASS only on a verified, measured, in-domain covering measurement with a frozen basis)"] = ok1
    d = committed_rvm()
    want = [[r["id"], cfg, cell["status"], cell["rule"], cell["reason"]] for r in d["rows"]
            for cfg, cell in r["configurations"].items()]
    rep = [p for c, p in zip(calls, rss) if c["fn"] == "rvm_replay"]
    gng = [p for c, p in zip(calls, rss) if c["fn"] == "gng_icp_01_replay"]
    g = next(x for x in d["owner_approved_gates"] if x["id"] == "GNG-ICP-01")
    inv["INV-R-02 (replay reproduces every committed cell and GNG-ICP-01)"] = bool(rep) and all(
        p["outcome"] == "RETURNED" and p["value"] == want for p in rep) and bool(gng) and all(
        p["value"]["status"] == g["status"] == "NOT_EVALUATED" and p["value"]["reason"] == g["status_reason"] for p in gng)
    ok3 = True
    for c, p in zip(calls, rss):
        if c["fn"] == "icp_gate_evaluate" and p["outcome"] == "RETURNED" and p["value"]["status"] == "GO":
            cr = decode(c["args"])["criteria"]
            if not (isinstance(cr, dict) and cr.get("status") == "OWNER_ACCEPTED"):
                ok3 = False
    inv["INV-R-03 (GO only on accepted criteria with verified citations)"] = ok3
    rvm_prop = next(p for p in d["recorder_proposals_open_for_owner"] if p["id"] == "RP-A919-01")["proposal"]
    inv["INV-R-04 (RVM proposal text == a9_19_rvm.RECORDER_PROPOSALS[RP-A919-01])"] = rvm_prop == next(
        p for p in A19.RECORDER_PROPOSALS if p["id"] == "RP-A919-01")["proposal"]
    inv["INV-R-05 (two Rust runs byte-identical)"] = rss2
    return inv, []


# ============================================================================================== campaign
LEDGER = {
    "gates": [
        {"component": "C-ABEP_SIM_ASSESSMENT_DESIGN_GATES_PY", "request":
         "PARTIAL admission on PARITY_PASS (contract PARITY-C-ABEP_SIM_ASSESSMENT_DESIGN_GATES_PY-V1): HARD_CONSTRAINTS, "
         "evaluate_constraints (with DIV-01, A9.31 sec. 10), hard_constraint_partition, constraint_met_value_kinds, "
         "bus_power_gate, ripple_feed_quality, statewise_drag_compensation, feed_state_sufficiency, pareto_s6_17, "
         "propellant_paths_check, rvm_gate_snapshot, owner_state, status_label, apply_to_questions -> crates/abep-assess "
         "(abep_assess::{gates, power_gate, statewise, pareto, propellant, rvm, owner_state}); gate_snapshot stays "
         "PYTHON_REFERENCE (wraps the F8 robust_optimizer.design_gate_snapshot, SC-WP-10)"},
        {"component": "C-ABEP_SIM_BUS_BOUNDARY_A9_V2_PY", "request":
         "the pending rfp_power_gate (and the transient_gate field it produces) admitted in abep-assess "
         "(abep_assess::power_gate::rfp_power_gate; limit from config p_bus_max_W): with the SC-WP-05 partial admission "
         "the row's flight scope is complete (GROUND_REFERENCE_TEST_METADATA stays GROUND_REFERENCE_ONLY)"},
        {"component": "C-ABEP_SIM_PROGRAMME_DESIGN_SYNTHESIS_PY", "request":
         "the pending gate_verdict field of bus_power admitted in abep-assess (abep_assess::power_gate::"
         "bus_power_gate_verdict); every other function of design_synthesis stays with SC-WP-10"},
        {"component": "C-ABEP_SIM_DESIGN_UPSTREAM_A9_13_PY", "request":
         "partial admission of statewise_envelope and _rec_value (abep_assess::statewise; over the admitted "
         "abep_mission::statewise::statewise_quantifier)"},
        {"component": "C-DOCS_EXPERIMENTS_HALL_ICP_P1_ICP_BENCH", "request":
         "partial admission of the kernel icp45a_margin (abep_assess::neutralization::icp45a_margin; A9.29 sec. 4: "
         "M_n in assessment only); the P1 reducer stays PYTHON_REFERENCE (SC-WP-03)"},
    ],
    "rvm": [
        {"component": "C-DOCS_REQUIREMENTS_RVM_A9", "request":
         "PARTIAL admission on PARITY_PASS (contract PARITY-C-DOCS_REQUIREMENTS_RVM_A9-RULES_AND_ICP_GATE-V1): "
         "rvm_rules.py (whole module) and a9_21_icp_gate.evaluate / lock1_release_reportable -> crates/abep-assess "
         "(abep_assess::{rvm, icp_gate}); the RVM document builder (build_rvm_a9.py and its row / application "
         "modules) stays PYTHON_REFERENCE; the committed rvm_a9_v1.json is consumed sha256-pinned"},
    ],
}


def reference_check(contract):
    return [f["path"] for f in contract["reference_implementation"]["files"]
            if sha_file(ROOT / f["path"]) != f["sha256_at_registration"]]


def environment():
    import numpy
    rustc = subprocess.run(["/root/.cargo/bin/rustc", "--version"], capture_output=True, text=True).stdout.strip()
    try:
        cpu = next(line.split(":", 1)[1].strip() for line in open("/proc/cpuinfo") if line.startswith("model name"))
    except (OSError, StopIteration):
        cpu = platform.processor()
    return {"python": platform.python_version(), "numpy": numpy.__version__, "rustc": rustc,
            "platform": f"{platform.system()} {platform.release()} {platform.machine()}", "cpu": cpu,
            "thread_env": {k: os.environ.get(k) for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS")}}


def source_sha256(paths):
    out = {}
    for pat in paths:
        if pat.endswith("/**"):
            for p in sorted((ROOT / pat[:-3]).rglob("*")):
                if p.is_file():
                    out[p.relative_to(ROOT).as_posix()] = sha_file(p)
        else:
            out[pat] = sha_file(ROOT / pat)
    return out


def write_refs(cdir, requests, expected, py_results, rs_results):
    rd = cdir / "reference_outputs"
    rd.mkdir(parents=True, exist_ok=True)
    files = {}
    for name, obj in (("requests.json.gz", requests), ("expected_rust_outputs.json.gz", expected),
                      ("python_outputs.json.gz", py_results), ("rust_outputs_at_scoring.json.gz", rs_results)):
        b = gzip.compress(json.dumps(obj, ensure_ascii=False, allow_nan=False).encode(), mtime=0)
        (rd / name).write_bytes(b)
        files[name] = sha_bytes(b)
    man = {"captured_at_python_commit": git("rev-parse", "HEAD"), "files": files,
           "note": "expected_rust_outputs = python_outputs after the registered DIV transformations"}
    (rd / "MANIFEST.json").write_text(json.dumps(man, indent=1) + "\n", encoding="utf-8")
    return man


def render_md(rep):
    L = [f"# Parity report v1 - {rep['contract']['id']}", "",
         f"Verdict: **{rep['parity']}** ({rep['verdict']}). Generated from `parity_report_v1.json`.", "",
         f"* Contract `{rep['contract']['path']}` sha256 `{rep['contract']['sha256']}`, registered in "
         f"`{rep['contract']['registered_in_commit'][:12]}`.",
         f"* Python reference commit `{rep['python_commit'][:12]}`; Rust commit `{rep['rust_commit'][:12]}` "
         f"(git_dirty: {len(rep['git_dirty'])} path(s)); {rep['build_provenance']['rustc']}.",
         f"* Environment: Python {rep['environment']['python']}, numpy {rep['environment']['numpy']}.",
         f"* Scoring seed {rep['seed']}; {rep['n_vectors']} vectors; {rep['n_failures']} per-test failures; "
         f"{rep['stats']['bit_identical']} returned values byte-identical; max ulp (E15) {rep['stats']['max_ulp']:.3g}; "
         f"{rep['stats']['raised_other']} reference refusals outside the registered classes (outcome only, DIV-04 / "
         f"DIV-R02).", "", "## Calls per entry", ""]
    for k, v in sorted(rep["calls_per_entry"].items()):
        L.append(f"* {k}: {v}")
    L += ["", "## Checks", ""]
    for k, v in rep["checks"].items():
        L.append(f"* {k}: {'pass' if v else 'FAIL'}")
    L += ["", "## Invariants", ""]
    for k, v in rep["invariants"].items():
        L.append(f"* {k}: {'pass' if v else 'FAIL'}")
    if rep["failures"]:
        L += ["", "## Failures (first 30)", ""] + [f"* {f}" for f in rep["failures"][:30]]
    if rep.get("notes"):
        L += ["", "## Notes", ""] + [f"* {n}" for n in rep["notes"]]
    L += ["", "## Ledger update requested", ""] + [f"* {x['component']}: {x['request']}"
                                                   for x in rep["ledger_update_requested"]]
    L += ["", "Parity is not physics validation, not a gate PASS and not a change of any threshold or frozen record.", ""]
    return "\n".join(L)


def run(key, mode):
    cpath = ROOT / CONTRACTS[key]
    contract = json.loads(cpath.read_text())
    seed = contract["campaign_seeds"]["scoring_master_seed" if mode == "score" else "development_master_seed"]
    changed = reference_check(contract)
    if changed and mode == "score":
        print(f"REFUSED_REFERENCE_CHANGED: {changed}")
        return 3
    manifest = sha_file(ROOT / "config/MANIFEST.json")
    if manifest != contract["governing_hashes"]["config_manifest"]["sha256"]:
        print("INPUT_MISMATCH: config/MANIFEST.json")
        return 3
    calls = build_gates(seed) if key == "gates" else build_rvm(seed)
    binary = cargo_build()
    work = Path(tempfile.mkdtemp(prefix="abep-assess-parity-"))
    try:
        rss, out1 = rust_eval(binary, calls, work, "a")
        _, out2 = rust_eval(binary, calls, work, "b")
        pys = [py_call(c["fn"], c["args"]) for c in calls]
        exp = [expected_rust(c["fn"], c["args"], p) for c, p in zip(calls, pys)]
        stats = {"bit_identical": 0, "max_ulp": 0.0, "raised_other": 0}
        failures = []
        per_entry = {}
        for c, e, r in zip(calls, exp, rss):
            per_entry[c["entry"]] = per_entry.get(c["entry"], 0) + 1
            for f in compare(c, e, r, stats):
                failures.append(f"{c['id']} {c['fn']}: {f}")
        inv, _ = (inv_gates if key == "gates" else inv_rvm)(calls, pys, rss, out1 == out2)
        checks = {"per_test": not failures, "invariants": all(inv.values()), "reference_unchanged": not changed,
                  "governing_hashes": True}
        checks["all"] = all(checks.values())
        if mode == "dev":
            print(json.dumps({"contract": contract["id"], "mode": "dev (not a verdict)", "seed": seed,
                              "vectors": len(calls), "n_failures": len(failures), "failures": failures[:25],
                              "invariants": inv, "stats": stats}, indent=1))
            return 0
        parity = "PARITY_PASS" if checks["all"] else "PARITY_FAIL"
        rel = str(cpath.relative_to(ROOT))
        now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
        rep = {
            "schema": "abep_rust_parity_report_v1",
            "contract": {"id": contract["id"], "path": rel, "sha256": sha_file(cpath),
                         "registered_in_commit": git("log", "--diff-filter=A", "--format=%H", "--", rel).splitlines()[-1]},
            "parity": parity, "verdict": "ADMITTED" if checks["all"] else "NOT_ADMITTED",
            "python_commit": contract["reference_implementation"]["python_commit"],
            "python_commit_at_scoring_head": git("rev-parse", "HEAD"),
            "reference_sha256": {f["path"]: sha_file(ROOT / f["path"]) for f in contract["reference_implementation"]["files"]},
            "rust_commit": git("rev-parse", "HEAD"), "git_dirty": git("status", "--porcelain").splitlines(),
            "build_provenance": {"rustc": environment()["rustc"], "cargo_lock_sha256": sha_file(ROOT / "Cargo.lock"),
                                 "binary_sha256": sha_file(binary), "source_sha256": source_sha256(RUST_SOURCES)},
            "environment": environment(), "seed": seed, "date_utc": now, "n_vectors": len(calls),
            "n_failures": len(failures), "calls_per_entry": per_entry, "stats": stats, "checks": checks,
            "invariants": inv, "failures": failures,
            "notes": [
                "INV-G-01 is checked on status-valued fields (keys 'status' / 'state_status'): the reference's own "
                "basis texts quote gate verdicts (e.g. 'rfp_power_gate verdict PASS (EVALUATED)') and are compared "
                "for equality, not scanned for words",
                "DIV-01 (A9.31 sec. 10) applied to the reference output of every evaluate_constraints vector whose "
                "HC-05 record has an uncertainty basis without a VALIDATED_BENCH / MEASURED validation basis",
            ] if key == "gates" else ["R7 citations are evaluated against identical scratch trees written by each "
                                      "implementation (root = <scratch>/base)"],
            "campaign_history": [{"execution": "scoring", "seed": seed, "date_utc": now, "parity": parity,
                                  "development_runs": "development-seed runs only, never reported (development_rule)"}],
            "ledger_update_requested": LEDGER[key] if checks["all"] else [
                {"component": LEDGER[key][0]["component"],
                 "request": "NONE (parity failed: stays PYTHON_REFERENCE; a fix needs a new contract version)"}],
        }
        cdir = cpath.parent
        rep["captured_reference_outputs"] = write_refs(cdir, calls, exp, pys, rss)
        (cdir / "parity_report_v1.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        (cdir / "parity_report_v1.md").write_text(render_md(rep), encoding="utf-8")
        print(f"{contract['id']}: {parity} ({len(calls)} vectors, {len(failures)} failures)")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main(argv):
    if len(argv) != 3 or argv[1] not in ("dev", "score") or argv[2] not in CONTRACTS:
        print(__doc__)
        return 2
    return run(argv[2], argv[1])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
