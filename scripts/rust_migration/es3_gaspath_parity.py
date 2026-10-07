#!/usr/bin/env python3
"""ES-3 gas-path parity harness (lane B3; A9.29 sec. 6, SC-WP-02).

Implements the vector generators, reference calls, tolerance classes and decision rules registered in

* docs/rust_migration/contracts/C-ABEP_SIM_DESIGN_FILTER_STAGE_PY/parity_prereg_v{1,2}.json  (contract key 'filter')
* docs/rust_migration/contracts/C-ABEP_SIM_COMPRESSOR_PY/parity_prereg_v{1,2}.json           (contract key 'compressor')
* docs/rust_migration/contracts/C-ABEP_SIM_DESIGN_PLENUM_FEED_PY/parity_prereg_v{1..7}.json (contract key 'plenum')

The active version of each key is CONTRACT_VERSION; a superseded version keeps its report (immutable). Version 2 of
the filter and compressor contracts repeats version 1 with fresh seeds (see their 'supersedes' records). Version 2 of
the plenum contract is version 1 minus the entries listed in its scope_reduction_v2.excluded_harness_entries
(plenum.transient_run P42, plenum.transient_case P43): their vectors are generated and dropped before any call.
Version 3 of the plenum contract is the full v1 scope with the transients P42 / P43 / P45 under the A9.31 sec. 5
convergence-derived procedure (transient_convergence_procedure_v3): the refinement mode runs the registered refinement
grid once and writes the frozen envelope record; the scoring mode reads it. Version 4 is version 3 with the transient
RUST_DEFECT fix registered and fresh seeds (v3 was superseded before any scored run); the procedure is unchanged.
Version 5 (v4 superseded before any scored run) scores the five rounding-dominated segment cascade diagnostics through
their primitives (reported with conditioning) and registers a larger refinement grid. Version 6 (v5 superseded before
any scored run: its frozen refinement record exposed a Rust integrator that damped growing modes) registers the
growing-mode guard of the Rust integrator and fresh seeds; the procedure is v5's. Version 7 (v6 superseded before any
scored run) adds the input-only stability class (strata S / U / R, stratified held-out and refinement draws), scores
the unstable stratum against the converged reference (DIV-P-REF-01), reports closing-valve xO extrema and requires the
non-vacuity check of every scored family before the scoring run (transient_convergence_procedure_v7).

The Python reference is called read-only; the Rust side is the `abep-gaspath-parity` binary of crates/abep-gaspath.

    python3 scripts/rust_migration/es3_gaspath_parity.py dev   filter|compressor|plenum   # development seed; no verdict
    python3 scripts/rust_migration/es3_gaspath_parity.py score filter|compressor|plenum   # scoring seed, ONCE
    python3 scripts/rust_migration/es3_gaspath_parity.py refine plenum                    # v7 envelope record, ONCE
    python3 scripts/rust_migration/es3_gaspath_parity.py refine-dev plenum OUT_JSON N     # development draft only

A scoring run refuses to start when parity_report_v<n>.json exists, when a reference file differs from its registered
sha256 (REFUSED_REFERENCE_CHANGED) or when a Rust / harness source has uncommitted changes.

Harness-level definitions the contracts leave to the harness (fixed here, before any scoring run):

* Leaf classification. Every leaf of the Python record (JSON form: tuples as lists, numpy arrays as lists, non-finite
  floats as 'NaN' / '+inf' / '-inf') is compared with the Rust leaf at the same path. Non-float leaves, dict key SETS and
  list lengths are EXACT_VALUE. A float leaf is 'copied' (EXACT_VALUE) when its non-zero Python value occurs among the
  float inputs of the vector (conservative: a computed value that coincides with an input must then match exactly);
  every other float is 'computed' and takes the entry's registered float class. In the transient entries (P42, P43,
  P45) a solution sample can equal an input (the regulated pressure equals its setpoint), so there only the leaves
  copied by construction (setpoint_Pa, duration_s, t_start_s, V_m3, T_comp_limit_K, shaft_hz, amplitude) are 'copied'.
* Plenum-contract entry indices (the contract registers counts per P-number): P30 orbital_period_s / cbar /
  kT_over_m; P31 IntakeState (q_fwd, e_f1, escape_probability) and f1_candidate_id; P32 filter factories and
  FilterCase.coefficients; P33 filter_case_from_stage (incl. E-P-06); P34 Plenum (validation incl. E-P-01, wall area,
  k_rec, leak, feed conductance, reservoir); P35 CompressorPlant (from_design, stages, characteristic, leak, shaft_hz,
  cascade); P36 Chain.node_coefficients and solve_pressures; P37 steady_operating_point / evaluate (incl. E-P-03);
  P38 intake_side + steady_sweep (+ the Rust scalar twin, INV-P-02); P39 area_for_pressure (incl. E-P-02),
  bisection_failed (E-P-04), lambda_upper_m; P40 settling_time / segment_metrics / _domain_reasons on synthetic
  segments; P41 ripple_transfer / inlet_node_tau_per_m3; P42 TransientRun.run on event_sequence (incl. E-P-05);
  P43 transient_case; P44 orbit_quasi_static; P45 orbit_simulated; P46 strict_blockers, status_from_reasons,
  reasons_from_bits; P47 scheduled_operation / compare_control_modes (incl. E-P-07); P48 pareto_ids,
  intake_controller_state; P49 Reservoir conductance / steady_state (incl. E-P-08) / size_orifice_for_pressure /
  startup_transient; P50 constants; upstream P10 pressure_domain_status / classify_pressure_target; P11
  combine_value_status / constraint_status; P12 SetpointSchedule x controller states (setpoint, controller_view);
  P13 FixedSetpoint; P14 ScheduleInput; P15 H1Tolerance; P16 governing_band; P17 characterization_coverage; P18
  refuse_fixed_mass_flow_gate; P19 flight_feed_requirement; P20 flow_gap_record; P21 refuse_feed_requirement_lowering;
  P22 state_coverage; P23 RobustParetoSet; P24 refuse_candidate_evidence; P25 verify_decision_records, cite,
  dense_state_only_operation.
* Plenum contract v3 transient leaves (P42 / P43 / P45): the family map V3_FAMILY (registered families and scales of
  transient_convergence_procedure_v3), p_inlet_max_Pa through the primitive image (diag_images; v5: the five cascade
  diagnostics are reported with conditioning, scored through their primitives), the closed-form leaves (sample times, steady network) in the ULP classes; any other transient float leaf is a harness
  error. Threshold proximity follows threshold_proximity_rule.v3_transient leaf by leaf (proximity_transient_v3) and
  is counted per leaf.
"""
from __future__ import annotations

import os
import sys

if os.environ.get("OMP_NUM_THREADS") != "1" or os.environ.get("OPENBLAS_NUM_THREADS") != "1":
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["OPENBLAS_NUM_THREADS"] = "1"
    os.execv(sys.executable, [sys.executable] + sys.argv)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
for _k in ("ABEP_ATMOSPHERE", "ABEP_ALLOW_TABLE_ATMOSPHERE"):
    os.environ.pop(_k, None)

import copy  # noqa: E402
import dataclasses  # noqa: E402
import datetime  # noqa: E402
import gzip  # noqa: E402
import hashlib  # noqa: E402
import itertools  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import platform  # noqa: E402
import re  # noqa: E402
import statistics  # noqa: E402
import struct  # noqa: E402
import subprocess  # noqa: E402
import time  # noqa: E402
import types  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

from abep_sim import compressor as cmod  # noqa: E402
from abep_sim import reservoir as rmod  # noqa: E402
from abep_sim import rotor_strength as rs  # noqa: E402
from abep_sim.constants import M_SPECIES  # noqa: E402
from abep_sim.design import architecture_optimizer as aopt  # noqa: E402
from abep_sim.design import compressor_synthesis as cs  # noqa: E402
from abep_sim.design import filter_stage as fs  # noqa: E402
from abep_sim.design import intake_synthesis as isy  # noqa: E402
from abep_sim.design import plenum_feed as pf  # noqa: E402
from abep_sim.design import upstream_a9_13 as u13  # noqa: E402
from abep_sim.materials import DB  # noqa: E402

CDIR = os.path.join(ROOT, "docs", "rust_migration", "contracts")
CONTRACT_DIRS = {"filter": "C-ABEP_SIM_DESIGN_FILTER_STAGE_PY", "compressor": "C-ABEP_SIM_COMPRESSOR_PY",
                 "plenum": "C-ABEP_SIM_DESIGN_PLENUM_FEED_PY"}
BIN = os.path.join(ROOT, "target", "release", "abep-gaspath-parity")
SYN = "SYNTHETIC_PARITY_VECTOR_NOT_EVIDENCE"
SPECIES = ("O", "N2", "O2")
CF = {"k_ulp": 4, "r_rel": 1e-12}
STEADY = {"k_ulp": 4, "r_rel": 1e-9}
SPECIES_NAMES = {"O", "N2", "O2", "Xe"}


def sha_file(p: str) -> str:
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


CONTRACT_VERSION = {"filter": 2, "compressor": 2, "plenum": 7}


def version_of(key: str, version=None) -> int:
    return version or CONTRACT_VERSION[key]


def ref_dir_name(n: int) -> str:
    return "reference_outputs" if n == 1 else f"reference_outputs_v{n}"


def load_contract(key: str, version=None) -> tuple[dict, str, str]:
    p = os.path.join(CDIR, CONTRACT_DIRS[key], f"parity_prereg_v{version_of(key, version)}.json")
    return json.load(open(p)), sha_file(p), p


def excluded_entries(contract: dict, key: str) -> set:
    """Entries a scope-reduced contract version removes (scope_reduction_v<n>.excluded_harness_entries)."""
    return set((contract.get(f"scope_reduction_v{version_of(key)}") or {}).get("excluded_harness_entries", ()))


def jnum(x):
    """JSON transport of a float (non-finite values as the registered strings)."""
    if isinstance(x, float) and math.isnan(x):
        return "NaN"
    if isinstance(x, float) and math.isinf(x):
        return "+inf" if x > 0 else "-inf"
    return x


def unj(x):
    if x == "NaN":
        return float("nan")
    if x == "+inf":
        return float("inf")
    if x == "-inf":
        return float("-inf")
    return x


def rng(master: int, entry: int) -> np.random.Generator:
    return np.random.default_rng(np.random.SeedSequence([master, entry]))


def U(g, a, b) -> float:
    return float(g.uniform(a, b))


def LU(g, a, b) -> float:
    return float(10.0 ** g.uniform(a, b))


def P(g, p) -> bool:
    return bool(g.random() < p)


def pick(g, seq, p=None):
    i = int(g.choice(len(seq), p=p))
    return seq[i]


def tojson(x):
    """Python result -> JSON form (tuples as lists, numpy as Python, non-finite floats as the registered strings)."""
    if isinstance(x, dict):
        return {str(k): tojson(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [tojson(v) for v in x]
    if isinstance(x, np.ndarray):
        return [tojson(v) for v in x.tolist()]
    if isinstance(x, (np.bool_,)):
        return bool(x)
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, np.floating):
        return jnum(float(x))
    if isinstance(x, float):
        return jnum(x)
    return x


def input_floats(args) -> set:
    out = set()

    def walk(v):
        if isinstance(v, dict):
            for w in v.values():
                walk(w)
        elif isinstance(v, (list, tuple)):
            for w in v:
                walk(w)
        elif isinstance(v, float) and math.isfinite(v) and v != 0.0:
            out.add(v)
    walk(args)
    return out


# ----------------------------------------------------------------------------------------------------------------------
# Rust runner
# ----------------------------------------------------------------------------------------------------------------------
MATERIALS = {k: {"density": m.density, "yield_MPa": m.yield_MPa, "T_max_K": m.T_max_K, "gamma_min": m.gamma_min,
                 "gamma0": m.gamma0, "gamma_Ea_eV": m.gamma_Ea_eV} for k, m in DB.items()}


def build_rust() -> None:
    subprocess.run(["cargo", "build", "--release", "--locked", "-p", "abep-gaspath", "--bin", "abep-gaspath-parity"],
                   cwd=ROOT, check=True, env={**os.environ, "PATH": "/root/.cargo/bin:" + os.environ.get("PATH", "")})


def run_rust(requests: list) -> tuple[dict, bytes, list, float]:
    payload = json.dumps({"repo_root": ROOT, "materials": MATERIALS, "requests": requests}, allow_nan=False).encode()
    t0 = time.perf_counter()
    p = subprocess.run([BIN], input=payload, capture_output=True, check=True)
    wall = time.perf_counter() - t0
    out = json.loads(p.stdout)
    timing = [json.loads(line) for line in p.stderr.decode().splitlines() if line.startswith("{")]
    return out, p.stdout, timing, wall


# ----------------------------------------------------------------------------------------------------------------------
# Tolerance classes
# ----------------------------------------------------------------------------------------------------------------------
def exact_equal(a, b) -> bool:
    """EXACT_VALUE: equal value; booleans only equal booleans; numbers by value (-0.0 == 0.0); dict key SETS."""
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a == b
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(exact_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return set(a) == set(b) and all(exact_equal(a[k], b[k]) for k in a)
    return type(a) is type(b) and a == b


def is_num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def norm_path(path) -> str:
    out = []
    for c in path:
        if isinstance(c, int):
            out.append("[]")
        elif c in SPECIES_NAMES:
            out.append("<s>")
        else:
            m = re.match(r"^(.*)\.(O|N2|O2|Xe)$", c)
            out.append(m.group(1) + ".<s>" if m else c)
    return "/".join(out) or "<root>"


class Tally:
    """Per-entry, per-observable accounting."""

    def __init__(self):
        self.obs: dict = {}
        self.failures: list = []
        self.unscored: dict = {}

    def _o(self, entry, name, cls):
        k = f"{entry}::{name}::{cls}"
        if k not in self.obs:
            self.obs[k] = {"entry": entry, "observable": name, "tolerance_class": cls, "n": 0, "n_fail": 0,
                           "n_bit_identical": 0, "max_abs_diff": 0.0, "max_rel_diff": 0.0, "max_ulp": 0.0}
        return self.obs[k]

    def fail(self, vid, entry, name, rust, py, extra=None):
        row = {"vector": vid, "entry": entry, "observable": name, "rust": repr(rust)[:300], "python": repr(py)[:300]}
        if extra:
            row.update(extra)
        self.failures.append(row)

    def exact(self, entry, name, rust, py, vid, path=""):
        o = self._o(entry, name, "EXACT_VALUE")
        o["n"] += 1
        same = exact_equal(rust, py)
        if same:
            o["n_bit_identical"] += 1
        else:
            o["n_fail"] += 1
            self.fail(vid, entry, name, rust, py, {"path": path})
        return same

    def unfail(self, f):
        """Withdraw a recorded failure (threshold proximity: NOT_SCORED_AT_THRESHOLD)."""
        o = self.obs[f"{f['entry']}::{f['observable']}::{f.get('class') or 'EXACT_VALUE'}"]
        o["n_fail"] -= 1

    def flt(self, entry, name, rust, py, spec, vid, path=""):
        """spec: ('ULP', tol) | ('SOLVER', tol) | ('ENV', tol) | ('UNSCORED', None)."""
        kind, tol = spec
        if kind == "UNSCORED":
            u = self.unscored.setdefault(f"{entry}::{name}", {"entry": entry, "observable": name, "n": 0,
                                                              "max_abs_diff": 0.0, "max_rel_diff": 0.0})
            u["n"] += 1
            if is_num(rust) and is_num(py) and math.isfinite(rust) and math.isfinite(py):
                d = abs(float(rust) - float(py))
                u["max_abs_diff"] = max(u["max_abs_diff"], d)
                if py:
                    u["max_rel_diff"] = max(u["max_rel_diff"], d / abs(py))
            return True
        cls = {"ULP": "ULP_BOUNDED", "ENV": "CONVERGENCE_ENVELOPE"}.get(kind, "SOLVER_TOLERANCE")
        o = self._o(entry, name, cls)
        if kind == "ENV":
            o["family"] = tol.get("family")
        o["tolerance"] = tol
        o["n"] += 1
        ok = False
        if is_num(rust) and is_num(py):
            r, p = float(rust), float(py)
            if r == p:
                ok = True
                o["n_bit_identical"] += 1 if struct.pack("<d", r) == struct.pack("<d", p) else 0
            else:
                d = abs(r - p)
                u = math.ulp(p)
                o["max_abs_diff"] = max(o["max_abs_diff"], d)
                o["max_ulp"] = max(o["max_ulp"], d / u)
                if p != 0.0:
                    o["max_rel_diff"] = max(o["max_rel_diff"], d / abs(p))
                if kind == "ENV":
                    # CONVERGENCE_ENVELOPE: (E_py + E_rust) s_F (or the primitive image W) + the STEADY floating
                    # residual allowance max(4 ulp, 1e-9 |py|); a NOT_EVALUATED envelope fails
                    a = tol.get("abs_env")
                    allowed = (a + max(4 * u, 1e-9 * abs(p))) if a is not None else -1.0
                    ok = d <= allowed
                    if allowed > 0:
                        o["max_used_frac"] = max(o.get("max_used_frac", 0.0), d / allowed)
                elif kind == "ULP":
                    ok = ((d <= tol.get("k_ulp", 0) * u) or ("r_rel" in tol and d <= tol["r_rel"] * abs(p))
                          or ("a_abs" in tol and d <= tol["a_abs"]))
                else:
                    ok = (d <= tol.get("abs", 0.0) + tol.get("rel", 0.0) * abs(p)) or d <= tol.get("k_ulp", 0) * u
        else:
            ok = exact_equal(rust, py)      # non-finite strings: equal strings
            if ok:
                o["n_bit_identical"] += 1
        if not ok:
            o["n_fail"] += 1
            self.fail(vid, entry, name, rust, py, {"path": path, "tolerance": tol, "class": cls})
        return ok

    def summary(self):
        return {"observables": list(self.obs.values()), "n_failures": len(self.failures),
                "failures_first_50": self.failures[:50], "reported_not_scored": list(self.unscored.values())}


def compare_tree(t: Tally, entry: str, vid: str, rust, py, rule, ctx, path=()):
    """Recursive comparison. rule(ctx, path, py_leaf) -> ('ULP', tol) | ('SOLVER', tol) | ('UNSCORED', None) |
    ('EXACT', None) for float leaves; ctx carries the vector, its input floats and the Python root."""
    name = norm_path(path)
    if ctx.get("skip") is not None and ctx["skip"](ctx["entry"], path):
        t.flt(entry, name, rust, py, ("UNSCORED", None), vid, "/".join(map(str, path)))
        return
    if isinstance(py, dict) and isinstance(rust, dict):
        t.exact(entry, name + " {keys}", sorted(rust), sorted(py), vid, "/".join(map(str, path)))
        for k in py:
            if k in rust:
                compare_tree(t, entry, vid, rust[k], py[k], rule, ctx, path + (k,))
        return
    if isinstance(py, list) and isinstance(rust, list):
        t.exact(entry, name + " [len]", len(rust), len(py), vid, "/".join(map(str, path)))
        for i, (a, b) in enumerate(zip(rust, py)):
            compare_tree(t, entry, vid, a, b, rule, ctx, path + (i,))
        return
    if isinstance(py, float) or (isinstance(py, str) and py in ("NaN", "+inf", "-inf")) or \
            (isinstance(rust, float) and is_num(py)):
        spec = rule(ctx, path, py)
        if spec[0] != "UNSCORED" and isinstance(py, float) and py != 0.0 and py in ctx["inputs"] and \
                COPIED_OK.get(ctx["entry"], lambda p_: True)(path):
            spec = ("EXACT", None)
        if spec[0] == "EXACT":
            t.exact(entry, name, rust, py, vid, "/".join(map(str, path)))
        else:
            t.flt(entry, name, rust, py, spec, vid, "/".join(map(str, path)))
        return
    t.exact(entry, name, rust, py, vid, "/".join(map(str, path)))


def py_call(fn):
    """('OK', json value) or ('ERROR', exception class name, message)."""
    try:
        return ("OK", tojson(fn()), None)
    except Exception as e:  # noqa: BLE001 - every exception class is compared by name
        return ("ERROR", type(e).__name__, str(e))


def rust_outcome(r):
    if r["outcome"] == "OK":
        return ("OK", r["value"], None)
    return ("ERROR", r["error_class"], r.get("error_message"))


# ======================================================================================================================
# Filter contract (key 'filter')
# ======================================================================================================================
def ev_spec(value, units="-", status="EVIDENCED", evidence_class="measured", source=SYN, uncertainty=None, basis="",
            evidence_level=None, domain=None, requires=None):
    return {"value": jnum(value) if isinstance(value, float) else value, "units": units, "status": status,
            "evidence_class": evidence_class, "source": source, "uncertainty": uncertainty, "basis": basis,
            "evidence_level": evidence_level, "domain": domain, "requires": requires}


def tbd_spec(requires="synthetic TBD", units="-"):
    return {"value": None, "units": units, "status": "TBD", "requires": requires}


def py_ev(d):
    return fs.EV(value=unj(d.get("value")), units=d.get("units", ""), status=d.get("status", ""),
                 evidence_class=d.get("evidence_class"), source=d.get("source"), uncertainty=d.get("uncertainty"),
                 basis=d.get("basis", "") if d.get("basis") is not None else "", evidence_level=d.get("evidence_level"),
                 domain=d.get("domain"), requires=d.get("requires"))


def py_protection(d):
    return fs.ProtectionFunction(target=d["target"], mechanism=d["mechanism"],
                                 capture_efficiency=py_ev(d["capture_efficiency"]),
                                 evidence_note=d.get("evidence_note") or "")


def py_material(d):
    kw = {"material": d["material"], "ao_compatibility": d.get("ao_compatibility") or "INCOMPLETE_EVIDENCE",
          "surrogate_label": d.get("surrogate_label") or "NONE", "evidence_refs": tuple(d.get("evidence_refs") or ()),
          "note": d.get("note") or ""}
    if d.get("o_recombination_probability") is not None:
        kw["o_recombination_probability"] = py_ev(d["o_recombination_probability"])
    if d.get("ao_erosion_yield") is not None:
        kw["ao_erosion_yield"] = py_ev(d["ao_erosion_yield"])
    return fs.MaterialApplicability(**kw)


ELEMENT_KEYS = {"element_temperature_K": "element_temperature_K", "energy_accommodation": "energy_accommodation",
                "contaminant_capacity_kg": "contaminant_capacity_kg", "face_area_m2": "face_area_m2",
                "areal_mass_kg_m2": "areal_mass_kg_m2"}


def py_stage(d):
    sp = tuple(d.get("species") or ("O", "N2", "O2"))
    fi = d.get("forward_incidence") or "diffuse_thermal"
    desc = d.get("description") or ""
    prot = tuple(py_protection(x) for x in d.get("protection") or [])
    mats = tuple(py_material(x) for x in d.get("materials") or [])
    rve = tuple(tuple(x) for x in d.get("research_variant_evidence") or [])
    f = d["factory"]
    if f == "none":
        st = fs.FilterStage.none(sp)
    elif f == "tbd":
        st = fs.FilterStage.tbd(d.get("stage_id") or "", d.get("concept_id") or "", sp, fi, desc, prot, mats,
                                d.get("role") or fs.ROLE_BASELINE)
    elif f == "catalytic":
        st = fs.FilterStage.catalytic_research_variant(d.get("stage_id") or "", d.get("concept_id") or "", sp, fi,
                                                       desc, mats, rve)
    elif f == "custom":
        recs = {k: py_ev(v) for k, v in (d.get("records") or {}).items()}
        tr = {}
        for s in sp:
            t = fs.tbd_species_transport(s)
            if s in (d.get("drop_routing") or []):
                t = dataclasses.replace(t, product_to_outlet_f=None, product_to_outlet_b=None)
            rep = {k.split(".")[0]: v for k, v in recs.items() if "." in k and k.split(".", 1)[1] == s}
            if rep:
                t = dataclasses.replace(t, **rep)
            tr[s] = t
        kw = {}
        if "face_area_m2" in recs:
            kw["face_area_m2"] = recs["face_area_m2"]
        if "areal_mass_kg_m2" in recs:
            kw["areal_mass_kg_m2"] = recs["areal_mass_kg_m2"]
        st = fs.FilterStage(stage_id=d.get("stage_id") or "", concept_id=d.get("concept_id") or "",
                            kind=d.get("kind") or "element", transport=tr, forward_incidence=fi,
                            regime=d.get("regime") or "free_molecular", protection=prot, materials=mats,
                            description=desc, role=d.get("role") or fs.ROLE_BASELINE, research_variant_evidence=rve,
                            **kw)
    else:
        raise RuntimeError("factory")
    er = d.get("element_records") or {}
    if er:
        st = dataclasses.replace(st, **{ELEMENT_KEYS[k]: py_ev(v) for k, v in er.items()})
    return st


def py_inlet(d):
    ip = d.get("incident_power_W")
    return fs.InletState(mdot_forward_kgps={k: unj(v) for k, v in d["mdot_forward_kgps"]},
                         mdot_back_incident_kgps={k: unj(v) for k, v in d["mdot_back_incident_kgps"]},
                         back_incident_basis=d.get("back_incident_basis") or "", T_gas_K=unj(d.get("T_gas_K")),
                         incidence=d.get("incidence") or "", knudsen_number=unj(d.get("knudsen_number")),
                         label=d.get("label") or "", provenance=d.get("provenance") or "",
                         incident_power_W=None if ip is None else {k: unj(v) for k, v in ip},
                         incident_power_source=d.get("incident_power_source") or "")


def py_case(d):
    if d is None:
        return None
    return fs.SensitivityCase(case_id=d.get("case_id") or "", label=d.get("label") or "",
                              overrides={k: unj(v) for k, v in d["overrides"]}, rationale=d.get("rationale") or "",
                              regime_assumption=d.get("regime_assumption"),
                              temperature_override_K=unj(d.get("temperature_override_K")))


def stage_param_ids(spec):
    """The parameter ids of the stage spec (Python order), for override generation."""
    return list(py_stage({**spec, "element_records": {}, "records": {}, "drop_routing": []}
                         if spec["factory"] == "custom" else {**spec, "element_records": {}}).parameter_ids())


def fraction_value(g, pid):
    k = pid.split(".")[0]
    s = pid.split(".")[1] if "." in pid else None
    if k in ("tau_f", "tau_b"):
        return U(g, 0, 1)
    if k in ("capture_f", "capture_b"):
        return U(g, 0, 0.2) if P(g, 0.5) else 0.0
    if k in ("conversion_f", "conversion_b"):
        if s == "O":
            return U(g, 0, 0.3) if P(g, 0.5) else 0.0
        return U(g, 0, 0.1) if P(g, 0.03) else 0.0
    if k.startswith("product_to_outlet"):
        return U(g, 0, 1)
    if k == "alpha_conductance":
        return 0.0 if P(g, 0.05) else U(g, 0, 1)
    if k == "face_area_m2":
        return LU(g, -3, 0)
    if k == "areal_mass_kg_m2":
        return U(g, 0.1, 5)
    raise RuntimeError(pid)


def units_of(pid):
    return {"face_area_m2": "m^2", "areal_mass_kg_m2": "kg/m^2"}.get(pid, "-")


def gen_stage(g):
    sp = pick(g, [("O", "N2", "O2"), ("N2", "O2"), ("O", "N2"), ("O", "N2", "O2", "Xe")], p=[0.7, 0.1, 0.1, 0.1])
    factory = pick(g, ["none", "tbd", "catalytic", "custom"], p=[0.1, 0.6, 0.15, 0.15])
    fi = "diffuse_thermal" if P(g, 0.7) else "hyperthermal_directed"
    spec = {"factory": factory, "species": list(sp), "stage_id": "F2-SYN", "concept_id": "FC-SYN",
            "forward_incidence": fi, "description": "synthetic parity stage"}
    if factory == "none":
        spec["forward_incidence"] = "diffuse_thermal"
        return spec
    if factory == "custom":
        recs = {}
        for pid in stage_param_ids(spec):
            if not P(g, 0.5):
                continue
            kind = pick(g, ["usable", "assumed", "placeholder"], p=[0.7, 0.15, 0.15])
            k, s = (pid.split(".") + [None])[:2]
            val = 0.0 if (k in ("conversion_f", "conversion_b") and s != "O") else fraction_value(g, pid)
            if kind == "usable":
                st = pick(g, ["EVIDENCED", "MODEL_DERIVED", "OWNER_GIVEN"])
                recs[pid] = ev_spec(val, units_of(pid), st, "measured")
            elif kind == "assumed":
                recs[pid] = ev_spec(val, units_of(pid), "MODEL_DERIVED", "assumed")
            else:
                recs[pid] = ev_spec(val, units_of(pid), "PLACEHOLDER_NOT_A_FLIGHT_DESIGN", "assumed")
        spec["records"] = recs
    er = {}
    for k, lo, hi, un in (("energy_accommodation", 0, 1, "-"), ("contaminant_capacity_kg", 0, 1, "kg"),
                          ("element_temperature_K", 200, 600, "K")):
        if not P(g, 0.5):
            er[k] = ev_spec(U(g, lo, hi), un, "EVIDENCED", "measured")
    spec["element_records"] = er
    if P(g, 0.3):
        ao = pick(g, list(fs.AO_GATE_OUTCOMES))
        sur = pick(g, list(fs.SURROGATE_LABELS))
        if ao == "GATE_SATISFIED_WITHIN_EVIDENCE_DOMAIN" and sur == fs.NO_ATOMIC_O:
            sur = "NONE"
        spec["materials"] = [{"material": "SYN-MAT", "ao_compatibility": ao, "surrogate_label": sur,
                              "evidence_refs": [] if ao == "INCOMPLETE_EVIDENCE" else ["SYN-REF"], "note": SYN}]
    if P(g, 0.3) and factory != "catalytic":
        spec["protection"] = [{"target": "particulates_debris", "mechanism": "synthetic screen",
                               "capture_efficiency": tbd_spec("synthetic capture efficiency"), "evidence_note": SYN}]
    if factory == "catalytic":
        spec["research_variant_evidence"] = [[it, "SYN-REF"] for it in fs.CATALYTIC_VARIANT_EVIDENCE if P(g, 0.5)]
    return spec


def gen_inlet(g, spec, t_null_p=0.2):
    sp = spec.get("species") or ["O", "N2", "O2"]
    fwd = [[s, LU(g, -9, -5)] for s in sp]
    back = [[s, LU(g, -10, -6) if P(g, 0.7) else 0.0] for s in sp]
    T = U(g, 150, 1500) if not P(g, t_null_p) else None
    kn = LU(g, -1.5, 1.5) if P(g, 0.6) else None
    label = pick(g, ["EVIDENCE", "PARAMETRIC_SENSITIVITY", "NORMALIZED_UNIT_INPUT"], p=[0.5, 0.3, 0.2])
    fi = spec.get("forward_incidence") or "diffuse_thermal"
    inc = fi if P(g, 0.85) else ("hyperthermal_directed" if fi == "diffuse_thermal" else "diffuse_thermal")
    ip = [[s, U(g, 0, 1e-3)] for s in sp] if P(g, 0.4) else None
    return {"mdot_forward_kgps": fwd, "mdot_back_incident_kgps": back, "back_incident_basis": "synthetic F4 coupling",
            "T_gas_K": T, "incidence": inc, "knudsen_number": kn, "label": label, "provenance": SYN,
            "incident_power_W": ip, "incident_power_source": SYN if ip is not None else ""}


def gen_case(g, spec):
    if P(g, 0.3):
        return None
    ov = []
    fracs = []
    for pid in stage_param_ids(spec):
        if P(g, 0.85):
            ov.append([pid, fraction_value(g, pid)])
            if pid.split(".")[0] in ("tau_f", "tau_b", "capture_f", "capture_b", "conversion_f", "conversion_b",
                                     "product_to_outlet_f", "product_to_outlet_b", "alpha_conductance"):
                fracs.append(len(ov) - 1)
    if fracs and P(g, 0.05):
        i = fracs[int(g.integers(len(fracs)))]
        ov[i][1] = U(g, 1, 1.5) if P(g, 0.5) else -U(g, 0, 0.5)
    return {"case_id": "SC-SYN", "label": "PARAMETRIC_SENSITIVITY (synthetic parity case)", "overrides": ov,
            "rationale": SYN, "regime_assumption": "free_molecular" if P(g, 0.6) else None,
            "temperature_override_K": U(g, 150, 1500) if P(g, 0.3) else None}


def full_records(sp, tau=0.6, conv_o=0.0, cap=0.0, routing=0.5, alpha=0.5, face=0.01, areal=1.0, tau_b=None,
                 status="EVIDENCED", cls="measured"):
    recs = {"face_area_m2": ev_spec(face, "m^2", status, cls), "areal_mass_kg_m2": ev_spec(areal, "kg/m^2", status,
                                                                                          cls)}
    for s in sp:
        recs[f"tau_f.{s}"] = ev_spec(tau, "-", status, cls)
        recs[f"tau_b.{s}"] = ev_spec(tau if tau_b is None else tau_b, "-", status, cls)
        recs[f"capture_f.{s}"] = ev_spec(cap, "-", status, cls)
        recs[f"capture_b.{s}"] = ev_spec(cap, "-", status, cls)
        c = conv_o if s == "O" else 0.0
        recs[f"conversion_f.{s}"] = ev_spec(c, "-", status, cls)
        recs[f"conversion_b.{s}"] = ev_spec(c, "-", status, cls)
        recs[f"alpha_conductance.{s}"] = ev_spec(alpha, "-", status, cls)
        if s == "O":
            recs[f"product_to_outlet_f.{s}"] = ev_spec(routing, "-", status, cls)
            recs[f"product_to_outlet_b.{s}"] = ev_spec(routing, "-", status, cls)
    return recs


def full_case(sp, tau=0.6, conv_o=0.0, cap=0.0, routing=0.5, alpha=0.5, face=0.01, areal=1.0, extra=None,
              regime="free_molecular", T=None):
    ov = [["face_area_m2", face], ["areal_mass_kg_m2", areal]]
    for s in sp:
        ov += [[f"tau_f.{s}", tau], [f"tau_b.{s}", tau], [f"capture_f.{s}", cap], [f"capture_b.{s}", cap],
               [f"conversion_f.{s}", conv_o if s == "O" else 0.0], [f"conversion_b.{s}", conv_o if s == "O" else 0.0],
               [f"alpha_conductance.{s}", alpha]]
        if s == "O":
            ov += [[f"product_to_outlet_f.{s}", routing], [f"product_to_outlet_b.{s}", routing]]
    for k, v in (extra or {}).items():
        for p in ov:
            if p[0] == k:
                p[1] = v
                break
        else:
            ov.append([k, v])
    return {"case_id": "SC-EDGE", "label": "PARAMETRIC_SENSITIVITY (edge)", "overrides": ov, "rationale": SYN,
            "regime_assumption": regime, "temperature_override_K": T}


def simple_inlet(sp, f=1e-6, b=1e-7, T=300.0, kn=5.0, inc="diffuse_thermal", label="EVIDENCE", ip=None):
    return {"mdot_forward_kgps": [[s, f] for s in sp], "mdot_back_incident_kgps": [[s, b] for s in sp],
            "back_incident_basis": "edge", "T_gas_K": T, "incidence": inc, "knudsen_number": kn, "label": label,
            "provenance": SYN, "incident_power_W": None if ip is None else [[s, ip] for s in sp],
            "incident_power_source": SYN if ip is not None else ""}


def filter_edges():
    S3 = ["O", "N2", "O2"]
    tb = {"factory": "tbd", "species": S3, "stage_id": "F2-EDGE", "concept_id": "FC-EDGE"}
    cu = {"factory": "custom", "species": S3, "stage_id": "F2-EDGE", "concept_id": "FC-EDGE",
          "records": full_records(S3)}
    E = []
    E.append(("none-identity", {"factory": "none", "species": S3}, simple_inlet(S3), None, 1e6))
    E.append(("tbd-all", tb, simple_inlet(S3), None, 1e6))
    E.append(("catalytic-all", {"factory": "catalytic", "species": S3, "stage_id": "F2-EDGE", "concept_id": "FC-EDGE"},
              simple_inlet(S3), None, 1e6))
    E.append(("incidence-mismatch", tb, simple_inlet(S3, inc="hyperthermal_directed"), full_case(S3), 1e6))
    E.append(("kn-0.5", tb, simple_inlet(S3, kn=0.5), full_case(S3, regime=None), 1e6))
    E.append(("kn-none-no-case", cu, simple_inlet(S3, kn=None), None, 1e6))
    E.append(("regime-assumed-no-kn", tb, simple_inlet(S3, kn=None), full_case(S3), 1e6))
    E.append(("zero-alpha", tb, simple_inlet(S3), full_case(S3, alpha=0.0), 1e6))
    E.append(("net-reverse", tb, simple_inlet(S3, f=1e-7, b=1e-6), full_case(S3), 1e6))
    E.append(("o-conv-no-o2", {**tb, "species": ["O", "N2"]}, simple_inlet(["O", "N2"]),
              full_case(["O", "N2"], conv_o=0.2), 1e6))
    E.append(("n2-conversion", tb, simple_inlet(S3), full_case(S3, extra={"conversion_f.N2": 0.1}), 1e6))
    E.append(("tau-1.2", tb, simple_inlet(S3), full_case(S3, extra={"tau_f.N2": 1.2}), 1e6))
    E.append(("tau-neg", tb, simple_inlet(S3), full_case(S3, extra={"tau_b.O2": -0.1}), 1e6))
    E.append(("sum-gt-1", tb, simple_inlet(S3), full_case(S3, tau=0.6, cap=0.3, conv_o=0.2), 1e6))
    E.append(("routing-1.5", tb, simple_inlet(S3), full_case(S3, conv_o=0.2, routing=1.5), 1e6))
    E.append(("zero-flows", tb, simple_inlet(S3, f=0.0, b=0.0), full_case(S3), 1e6))
    E.append(("placeholder-case", tb, simple_inlet(S3), "PLACEHOLDER", 1e6))
    E.append(("unknown-override", tb, simple_inlet(S3), full_case(S3, extra={"tau_f.Xe": 0.5}), 1e6))
    E.append(("species-differ", tb, simple_inlet(["O", "N2"]), full_case(S3), 1e6))
    E.append(("hyperthermal-full", {**cu, "forward_incidence": "hyperthermal_directed"},
              simple_inlet(S3, inc="hyperthermal_directed"), None, 1e6))
    E.append(("reciprocity-note", {**cu, "records": full_records(S3, tau=0.6, tau_b=0.4)}, simple_inlet(S3), None,
              1e6))
    E.append(("thermal-upper-bound", {**cu, "element_records": {"energy_accommodation": ev_spec(0.8)}},
              simple_inlet(S3, ip=1e-4), None, 1e6))
    E.append(("thermal-converted-o", {**cu, "records": full_records(S3, conv_o=0.2),
                                      "element_records": {"energy_accommodation": ev_spec(0.8)}},
              simple_inlet(S3, ip=1e-4), None, 1e6))
    E.append(("catalytic-4-items", {"factory": "catalytic", "species": S3, "stage_id": "F2-EDGE",
                                    "concept_id": "FC-EDGE",
                                    "research_variant_evidence": [[i, "SYN-REF"] for i in fs.CATALYTIC_VARIANT_EVIDENCE]},
              simple_inlet(S3), full_case(S3, conv_o=0.2), 1e6))
    E.append(("inventory-duration-neg", tb, simple_inlet(S3), full_case(S3, cap=0.1), -1.0))
    E.append(("inventory-duration-nan", tb, simple_inlet(S3), full_case(S3, cap=0.1), "NaN"))
    return E


def construct_vectors():
    S3 = ["O", "N2", "O2"]
    ok_ev = ev_spec(0.5)
    ok_inlet = simple_inlet(S3)
    ok_case = full_case(S3)
    V = []

    def ev(name, **kw):
        V.append((name, "ev", {**ok_ev, **kw}))
    ev("ev-status", status="BOGUS")
    ev("ev-units", units="")
    V.append(("ev-tbd-value", "ev", {**tbd_spec(), "value": 0.5}))
    V.append(("ev-tbd-no-requires", "ev", {**tbd_spec(), "requires": None}))
    ev("ev-nonfinite", value="NaN")
    ev("ev-class", evidence_class="guess")
    ev("ev-source", source="")
    ev("ev-level-0", evidence_level=0)
    ev("ev-level-8", evidence_level=8)
    ev("ev-level-true", evidence_level=True)
    prot = {"target": "particulates_debris", "mechanism": "screen", "capture_efficiency": tbd_spec()}
    V.append(("prot-target", "protection", {**prot, "target": "bogus"}))
    V.append(("prot-mechanism", "protection", {**prot, "mechanism": "  "}))
    mat = {"material": "SYN", "ao_compatibility": "INCOMPLETE_EVIDENCE", "surrogate_label": "NONE", "evidence_refs": []}
    V.append(("mat-ao", "material", {**mat, "ao_compatibility": "BOGUS"}))
    V.append(("mat-surrogate", "material", {**mat, "surrogate_label": "BOGUS"}))
    V.append(("mat-no-atomic-o", "material", {**mat, "ao_compatibility": "GATE_SATISFIED_WITHIN_EVIDENCE_DOMAIN",
                                              "surrogate_label": fs.NO_ATOMIC_O, "evidence_refs": ["R"]}))
    V.append(("mat-no-refs", "material", {**mat, "ao_compatibility": "OUT_OF_DOMAIN"}))
    V.append(("inlet-label", "inlet", {**ok_inlet, "label": "BOGUS"}))
    V.append(("inlet-ip-species", "inlet", {**ok_inlet, "incident_power_W": [["O", 1e-4]], "incident_power_source": "s"}))
    V.append(("inlet-ip-negative", "inlet", {**ok_inlet, "incident_power_W": [[s, -1e-4] for s in S3],
                                             "incident_power_source": "s"}))
    V.append(("inlet-ip-source", "inlet", {**ok_inlet, "incident_power_W": [[s, 1e-4] for s in S3],
                                           "incident_power_source": " "}))
    V.append(("inlet-incidence", "inlet", {**ok_inlet, "incidence": "bogus"}))
    V.append(("inlet-provenance", "inlet", {**ok_inlet, "provenance": " "}))
    V.append(("inlet-species-differ", "inlet", {**ok_inlet, "mdot_back_incident_kgps": [["O", 0.0], ["N2", 0.0]]}))
    V.append(("inlet-species-unknown", "inlet", {**ok_inlet, "mdot_forward_kgps": [["O", 1e-6], ["He3", 1e-6]],
                                                 "mdot_back_incident_kgps": [["O", 0.0], ["He3", 0.0]]}))
    V.append(("inlet-negative", "inlet", {**ok_inlet, "mdot_forward_kgps": [["O", -1e-6], ["N2", 1e-6], ["O2", 1e-6]]}))
    V.append(("inlet-nan", "inlet", {**ok_inlet, "mdot_forward_kgps": [["O", "NaN"], ["N2", 1e-6], ["O2", 1e-6]]}))
    V.append(("inlet-T0", "inlet", {**ok_inlet, "T_gas_K": 0.0}))
    V.append(("inlet-Kn0", "inlet", {**ok_inlet, "knudsen_number": 0.0}))
    V.append(("case-label", "case", {**ok_case, "label": "SENSITIVITY"}))
    V.append(("case-id", "case", {**ok_case, "case_id": " "}))
    V.append(("case-override", "case", {**ok_case, "overrides": [["tau_f.O", "+inf"]]}))
    V.append(("case-regime", "case", {**ok_case, "regime_assumption": "transitional"}))
    V.append(("case-T0", "case", {**ok_case, "temperature_override_K": 0.0}))
    cu = {"factory": "custom", "species": S3, "stage_id": "F2-C", "concept_id": "FC-C", "records": {}}
    V.append(("stage-kind", "stage", {**cu, "kind": "bogus"}))
    V.append(("stage-role", "stage", {**cu, "role": "BOGUS"}))
    V.append(("stage-none-role", "stage", {**cu, "kind": "none"}))
    V.append(("stage-element-reference-role", "stage", {**cu, "role": fs.ROLE_REFERENCE_BOUND}))
    V.append(("stage-research-on-baseline", "stage", {**cu, "research_variant_evidence": [
        [fs.CATALYTIC_VARIANT_EVIDENCE[0], "R"]]}))
    V.append(("stage-research-malformed", "stage", {"factory": "catalytic", "species": S3, "stage_id": "F2-C",
                                                    "concept_id": "FC-C",
                                                    "research_variant_evidence": [["bogus item", "R"]]}))
    V.append(("stage-incidence", "stage", {"factory": "tbd", "species": S3, "stage_id": "F2-C", "concept_id": "FC-C",
                                           "forward_incidence": "bogus"}))
    V.append(("stage-regime", "stage", {**cu, "regime": "transitional"}))
    V.append(("stage-species", "stage", {"factory": "tbd", "species": ["O", "He3"], "stage_id": "F2-C",
                                         "concept_id": "FC-C"}))
    V.append(("stage-o-no-routing", "stage", {**cu, "drop_routing": ["O"]}))
    V.append(("stage-n2-conversion", "stage", {**cu, "records": {"conversion_f.N2": ev_spec(0.1)}}))
    # valid controls
    V.append(("ok-ev", "ev", ok_ev))
    V.append(("ok-protection", "protection", prot))
    V.append(("ok-material", "material", {**mat, "ao_compatibility": "OUT_OF_DOMAIN", "evidence_refs": ["R"]}))
    V.append(("ok-inlet", "inlet", ok_inlet))
    V.append(("ok-case", "case", ok_case))
    V.append(("ok-stage", "stage", {**cu, "records": full_records(S3)}))
    return V


def vectors_filter(master: int) -> list:
    V = []

    def add(vid, entry, args, **meta):
        V.append({"id": vid, "entry": entry, "args": args, **meta})
    table = [x for x, _ in fs.COLE_TABLE_2_5]
    for i, x in enumerate(table):
        add(f"F01-G-{i:02d}", "filter.cole", {"l_over_d": x})
    g = rng(master, 1)
    lo, hi = math.log10(0.05), math.log10(500.0)
    for i in range(400):
        add(f"F01-R-{i:03d}", "filter.cole", {"l_over_d": LU(g, lo, hi)})
    for i, x in enumerate([0.0499999, 500.0000001, 0.0, -1.0, "NaN", "+inf", "-inf"]):
        add(f"F01-E-{i}", "filter.cole", {"l_over_d": x})
    g = rng(master, 2)
    for i in range(200):
        add(f"F02-R-{i:03d}", "filter.plate", {"l_over_d": LU(g, lo, hi), "open_fraction": 1.0 - U(g, 0, 1)})
    for i, (ld, of) in enumerate([(10.0, 1.0), (10.0, 0.0), (10.0, 1.0000001), (10.0, "NaN"), (600.0, 0.5)]):
        add(f"F02-E-{i}", "filter.plate", {"l_over_d": ld, "open_fraction": of})
    g = rng(master, 3)
    for i in range(200):
        add(f"F03-R-{i:03d}", "filter.mean_speed", {"species": pick(g, ["O", "N2", "O2", "Xe"]),
                                                    "T_K": LU(g, 1, 4)})
    for i, (s, T) in enumerate([("He", 300.0), ("O", -1.0), ("N2", 0.0)]):
        add(f"F03-E-{i}", "filter.mean_speed", {"species": s, "T_K": T})
    for s in ("O", "N2", "O2", "Xe"):
        add(f"F04-G-{s}", "filter.tbd_transport", {"species": s})
    for i, st in enumerate([{"factory": "none"}, {"factory": "none", "species": ["O", "N2"]},
                            {"factory": "tbd", "stage_id": "F2-SYN", "concept_id": "FC-SYN"},
                            {"factory": "tbd", "stage_id": "F2-SYN", "concept_id": "FC-SYN",
                             "species": ["N2", "O2", "Xe"]},
                            {"factory": "catalytic", "stage_id": "F2-SYN", "concept_id": "FC-SYN"}]):
        add(f"F05-G-{i}", "filter.stage_parameters", {"stage": st})
    g = rng(master, 6)
    for i in range(600):
        spec = gen_stage(g)
        inl = gen_inlet(g, spec)
        cas = gen_case(g, spec)
        add(f"F06-R-{i:03d}", "filter.apply", {"stage": spec, "inlet": inl, "case": cas,
                                               "duration_s": U(g, 0, 1e8)})
    for name, spec, inl, cas, dur in filter_edges():
        if cas == "PLACEHOLDER":
            cas = placeholder_case_spec(spec)
        add(f"F06-E-{name}", "filter.apply", {"stage": spec, "inlet": inl, "case": cas, "duration_s": dur})
    g = rng(master, 7)
    for i in range(200):
        spec = gen_stage(g)
        cas = gen_case(g, spec)
        add(f"F07-R-{i:03d}", "filter.backflow", {"stage": spec, "case": cas,
                                                  "T_gas_K": U(g, 150, 1500) if P(g, 0.85) else None})
    for i, st in enumerate([{"factory": "tbd", "stage_id": "F2-SYN", "concept_id": "FC-SYN"},
                            {"factory": "tbd", "stage_id": "F2-SYN", "concept_id": "FC-SYN",
                             "species": ["O", "N2", "O2", "Xe"]}, {"factory": "none"}]):
        add(f"F08-G-{i}", "filter.placeholder", {"stage": st})
    for name, what, spec in construct_vectors():
        add(f"F09-{name}", "filter.construct", {"what": what, "spec": spec})
    return V


def placeholder_case_spec(spec):
    c = fs.placeholder_sensitivity_case(py_stage(spec))
    return {"case_id": c.case_id, "label": c.label, "overrides": [[k, v] for k, v in c.overrides.items()],
            "rationale": c.rationale, "regime_assumption": c.regime_assumption,
            "temperature_override_K": c.temperature_override_K}


def py_filter(v):
    a = v["args"]
    e = v["entry"]
    if e == "filter.cole":
        return py_call(lambda: fs.cole_transmission_probability(unj(a["l_over_d"])).to_dict())
    if e == "filter.plate":
        return py_call(lambda: fs.perforated_plate_alpha(unj(a["l_over_d"]), unj(a["open_fraction"])).to_dict())
    if e == "filter.mean_speed":
        return py_call(lambda: fs.mean_speed_m_s(a["species"], unj(a["T_K"])))
    if e == "filter.tbd_transport":
        return py_call(lambda: {k: r.to_dict() for k, r in fs.tbd_species_transport(a["species"]).records().items()})
    if e == "filter.stage_parameters":
        def f():
            st = py_stage(a["stage"])
            return {"parameter_ids": list(st.parameter_ids()), "to_dict": st.to_dict()}
        return py_call(f)
    if e == "filter.apply":
        def f():
            st = py_stage(a["stage"])
            inl = py_inlet(a["inlet"])
            c = py_case(a["case"])
            r = st.apply(inl, c)
            try:
                ri = fs.retained_inventory_kg(r, unj(a["duration_s"]))
            except Exception as exc:  # noqa: BLE001
                ri = {"__error__": type(exc).__name__}
            return {"result": r.to_dict(), "species_transmission": r.species_transmission(),
                    "to_f3_record": r.to_f3_record(), "to_f1_record": r.to_f1_record(), "retained_inventory": ri}
        return py_call(f)
    if e == "filter.backflow":
        return py_call(lambda: py_stage(a["stage"]).backflow_coupling(unj(a["T_gas_K"]), py_case(a["case"])))
    if e == "filter.placeholder":
        def f():
            c = fs.placeholder_sensitivity_case(py_stage(a["stage"]))
            return {"values": fs.repository_placeholder_values(),
                    "case": {"case_id": c.case_id, "label": c.label, "overrides": dict(c.overrides),
                             "rationale": c.rationale, "regime_assumption": c.regime_assumption,
                             "temperature_override_K": c.temperature_override_K}}
        return py_call(f)
    if e == "filter.construct":
        def f():
            {"ev": py_ev, "protection": py_protection, "material": py_material, "inlet": py_inlet, "case": py_case,
             "stage": py_stage}[a["what"]](a["spec"])
            return "CONSTRUCTED"
        return py_call(f)
    raise RuntimeError(e)


DIFF_KEYS = {"net_downstream_kgps", "species_balance_residual_kgps", "mass_balance_residual_kgps",
             "converted_minus_produced_kgps"}


def rule_filter(ctx, path, py):
    tol = dict(CF)
    root = ctx["py"]
    if ctx["entry"] == "filter.apply" and isinstance(root, dict) and isinstance(root.get("result"), dict):
        S = (root["result"].get("totals") or {}).get("incident_kgps")
        leaf = path[-1] if path else ""
        parent = path[-2] if len(path) >= 2 else ""
        if isinstance(S, float):
            if leaf in DIFF_KEYS or parent == "mdot_s_net_downstream_kgps":
                tol["a_abs"] = 1e-12 * S
            sp = leaf if parent in ("delta_p_s_Pa",) else (parent if leaf == "delta_p_Pa" else None)
            if sp is not None:
                coef = ((root["result"].get("species") or {}).get(sp) or {}).get("delta_p_per_net_kgps_Pa")
                if isinstance(coef, float):
                    tol["a_abs"] = 1e-12 * S * coef
    return ("ULP", tol)


def checks_filter(t, vectors, py_out, rres):
    """CONS-F-01 on Rust outputs, INV-F-03 / INV-F-04 on both."""
    cons, inv3, inv4 = [], True, True
    for v in vectors:
        r = rres[v["id"]]
        po = py_out[v["id"]]
        for side, val in (("rust", r["value"] if r["outcome"] == "OK" else None),
                          ("python", po[1] if po[0] == "OK" else None)):
            if not isinstance(val, dict):
                continue
            blob = json.dumps(val.get("result", val))
            if v["entry"] in ("filter.apply", "filter.backflow"):
                res = val.get("result", val)
                for w in fs.FORBIDDEN_STATUS_WORDS:
                    if re.search(r'"(status|label)": "[^"]*' + w, blob):
                        inv4 = False
                if res.get("admissible_as_baseline") not in (None, False):
                    inv4 = False
                if v["entry"] == "filter.apply" and v["args"]["stage"]["factory"] in ("tbd", "catalytic") and \
                        v["args"]["case"] is None and res.get("status") in ("NUMERIC", "NO_FILTER_IDENTITY"):
                    inv3 = False
        if v["entry"] == "filter.apply" and r["outcome"] == "OK":
            res = r["value"]["result"]
            if res["status"] in ("NUMERIC", "NO_FILTER_IDENTITY"):
                tot = res["totals"]
                S = tot["incident_kgps"]
                worst = max([abs(tot["mass_balance_residual_kgps"]), abs(tot["converted_minus_produced_kgps"])]
                            + [abs(x["species_balance_residual_kgps"]) for x in res["species"].values()])
                cons.append({"vector": v["id"], "residual_kgps": worst, "limit_kgps": 1e-12 * S,
                             "ok": worst <= 1e-12 * S})
    return {"CONS-F-01": {"n": len(cons), "n_fail": sum(1 for c in cons if not c["ok"]),
                          "max_residual_over_incident": max((c["residual_kgps"] / max(c["limit_kgps"] * 1e12, 1e-300)
                                                             for c in cons), default=0.0),
                          "failures": [c for c in cons if not c["ok"]][:20], "ok": all(c["ok"] for c in cons)},
            "INV-F-03": {"ok": inv3}, "INV-F-04": {"ok": inv4}}


# ======================================================================================================================
# Compressor contract (key 'compressor')
# ======================================================================================================================
COMP_FIELDS = [f.name for f in dataclasses.fields(cmod.DragCompressor)]
FIXED_FIELDS = [f for f, (role, *_r) in cs.FIELD_ROLES.items() if role == cs.FIXED]
DRAWN = {"turbo_rows", "turbo_area_m2", "turbo_radius_m", "n_stages", "rotor_radius_m", "rpm", "h_mm", "w_mm",
         "L_per_stage_m", "xi", "rotor_material", "T_gas_K", "leak_conductance_m3_s", "k_bear_W_per_rads", "eta_motor",
         "P_ctrl_W"}
FRAC_FIELDS = {f for f, d in cs.COEFFICIENT_DOMAIN.items() if d == "frac"}
SYN_TI, SYN_AL, SYN_CF = "SYN-BASIS-TI", "SYN-BASIS-AL", "SYN-BASIS-CFRP"


def syn_basis(g, basis_id=SYN_TI, material="Ti6Al4V"):
    n = 2 if P(g, 0.5) else 3
    Ts = sorted(U(g, 250, 800) for _ in range(n))
    pts = []
    for T in Ts:
        fty = U(g, 5e8, 9e8)
        pts.append([T, fty, fty * U(g, 1, 1.2)])
    return {"basis_id": basis_id, "materials_db_key": material, "material_spec": SYN, "product_form": SYN,
            "condition": SYN, "section_thickness_range_m": [0.01, 0.2], "design_temperature_K": U(g, Ts[0], Ts[-1]),
            "allowable_basis": "A-basis (synthetic)", "allowable_source": SYN, "allowables": pts,
            "density_kg_m3": U(g, 4000, 4600), "density_source": SYN, "factor_yield": U(g, 1, 2),
            "factor_ultimate": U(g, 1, 2), "factors_source": SYN, "max_design_speed_rpm": U(g, 2e4, 1e5),
            "proof_spin_basis": "synthetic proof-spin basis (" + SYN + ")", "registration": SYN,
            "proof_spin_not_applicable_reason": None, "notes": SYN}


def py_basis(d):
    st = d.get("section_thickness_range_m")
    st = tuple(unj(x) for x in st) if isinstance(st, list) and len(st) == 2 else st
    al = d.get("allowables")
    al = tuple(rs.AllowablePoint(*[unj(x) for x in p]) for p in al) if isinstance(al, list) else al
    kw = {f.name: unj(d.get(f.name)) for f in dataclasses.fields(rs.RotorStrengthBasis)}
    kw.update({"section_thickness_range_m": st, "allowables": al, "notes": d.get("notes") or ""})
    return rs.RotorStrengthBasis(**kw)


class Registered:
    """Registers the vector's synthetic bases in rotor_strength.REGISTRY for one reference call (then restores)."""

    def __init__(self, bases):
        self.bases = bases or []

    def __enter__(self):
        self.saved = dict(rs.REGISTRY)
        rs.REGISTRY.clear()
        for b in self.bases:
            rs.register_basis(py_basis(b))

    def __exit__(self, *exc):
        rs.REGISTRY.clear()
        rs.REGISTRY.update(self.saved)


def gen_registry(g):
    reg = []
    if P(g, 0.3):
        reg.append(syn_basis(g))
    return reg


def gen_coeffs(g, reg):
    d = cs.module_defaults()
    c = {f: d[f] for f in COMP_FIELDS}
    c["turbo_rows"] = 0 if P(g, 0.05) else int(g.integers(1, 7))
    a = U(g, 0.05, 0.5)
    nu = pick(g, list(cs.HUB_RATIO_PARAMETRIC))
    c["turbo_area_m2"] = a
    c["turbo_radius_m"] = math.sqrt(a / (math.pi * (1.0 - nu ** 2)))
    c["n_stages"] = int(g.integers(0, 5))
    c["rotor_radius_m"] = U(g, 0.03, 0.1)
    c["rpm"] = U(g, 5e3, 9e4)
    c["h_mm"] = U(g, 1, 5)
    c["w_mm"] = U(g, 5, 20)
    c["L_per_stage_m"] = U(g, 0.1, 0.5)
    c["xi"] = U(g, 0.3, 0.9)
    c["rotor_material"] = pick(g, ["Ti6Al4V", "Al6061", "CFRP", "SS316"], p=[0.7, 0.1, 0.1, 0.1])
    c["T_gas_K"] = U(g, 250, 450)
    c["leak_conductance_m3_s"] = U(g, 0, 5e-4)
    c["k_bear_W_per_rads"] = U(g, 0, 1e-3)
    c["eta_motor"] = U(g, 0.5, 0.95)
    c["P_ctrl_W"] = U(g, 0, 20)
    for f in FIXED_FIELDS:
        if f in DRAWN:
            continue
        if not P(g, 0.5):
            v = d[f] * U(g, 0.8, 1.2)
            c[f] = min(v, 1.0) if f in FRAC_FIELDS else v
    r = g.random()
    registered = any(b["basis_id"] == SYN_TI for b in reg)
    c["rotor_strength_basis_id"] = None if r < 0.4 else ((SYN_TI if registered else None) if r < 0.9
                                                         else "UNREGISTERED-ID")
    c["rotor_stock_thickness_m"] = U(g, 0.005, 0.25) if P(g, 0.7) else None
    return c


def gen_mdot(g, lo=-8, hi=-5):
    return [[s, LU(g, lo, hi)] for s in SPECIES]


def py_comp(spec):
    kw = {f: spec[f] for f in COMP_FIELDS if f in spec}
    c = cmod.DragCompressor(**kw)
    c.set_rotor_strength_basis(spec.get("rotor_strength_basis_id"), unj(spec.get("rotor_stock_thickness_m")))
    return c


def gen_inlet_record(g, lo=-8, hi=-5.5, p_lo=-4, p_hi=-0.3, rid="SYN-INLET"):
    return {"record_id": rid, "mdot_kgps": gen_mdot(g, lo, hi), "p_total_Pa": LU(g, p_lo, p_hi), "T_K": U(g, 250, 450),
            "label": "PARAMETRIC_SENSITIVITY" if P(g, 0.8) else "F1_F2_INTERFACE_RECORD",
            "source": SYN, "evidence_class": "assumed" if P(g, 0.7) else "model-derived", "status": "",
            "p_species_Pa": None, "extra": {}}


def py_inlet_record(d):
    ps = d.get("p_species_Pa")
    return cs.InletRecord(record_id=d.get("record_id") or "", mdot_kgps={k: unj(v) for k, v in d["mdot_kgps"]},
                          p_total_Pa=unj(d["p_total_Pa"]), T_K=unj(d["T_K"]), label=d.get("label") or "",
                          source=d.get("source") or "", evidence_class=d.get("evidence_class") or "",
                          status=d.get("status") or "",
                          p_species_Pa=None if ps is None else {k: unj(v) for k, v in ps},
                          extra=dict(d.get("extra") or {}))


def random_design(g, i):
    a = U(g, 0.05, 0.5)
    nu = pick(g, list(cs.HUB_RATIO_PARAMETRIC))
    r = cs.r_turbo_from_area(a, nu)
    u = U(g, 50, 600)
    mat = pick(g, ["Ti6Al4V", "Al6061", "CFRP", "SS316"], p=[0.85, 0.05, 0.05, 0.05])
    return {"id": f"RND-{i}", "N_turbo": int(g.integers(1, 7)), "A_turbo_m2": a, "R_turbo_m": r,
            "u_tip_turbo_mps": u, "rpm": cs.rpm_from_tip(u, r), "N_drag": int(g.integers(0, 5)),
            "rotor_material": mat, **cs.hub_geometry(a, nu)}


DEFAULT_DESIGNS = None


def default_designs():
    global DEFAULT_DESIGNS
    if DEFAULT_DESIGNS is None:
        DEFAULT_DESIGNS = cs.SearchGrid().designs()
    return DEFAULT_DESIGNS


def extra_full():
    return {k: "SYN-RECORD (" + SYN + ")" for k in cs.CFRP_EXTRA_BASIS_KEYS}


def gen_evidence(g, reg):
    if P(g, 0.6):
        return None
    ev = {}
    for f in [FIXED_FIELDS[int(i)] for i in g.choice(len(FIXED_FIELDS), size=int(g.integers(1, 5)), replace=False)]:
        v = cs.module_defaults()[f] * U(g, 0.8, 1.2)
        if f in FRAC_FIELDS:
            v = min(v, 1.0)
        if cs.COEFFICIENT_DOMAIN[f] == "nonneg" and v == 0.0:
            v = 0.0
        ev[f] = {"value": v, "evidence_class": "measured", "source": SYN}
    if P(g, 0.5):
        ev["rotor_density"] = {"value": DB["Ti6Al4V"].density if P(g, 0.5) else DB["Ti6Al4V"].density * U(g, 0.9, 1.1),
                               "evidence_class": "measured", "source": SYN}
    if any(b["basis_id"] == SYN_TI for b in reg) and P(g, 0.7):
        ev["rotor_strength_basis_id"] = {"value": SYN_TI}
    if P(g, 0.3):
        ev["material_extra_basis"] = extra_full() if P(g, 0.5) else {cs.AO_DISPOSITION_KEY: "SYN"}
    return ev


def inlet_edges():
    ok = {"record_id": "E", "mdot_kgps": [["O", 4e-7], ["N2", 3e-7], ["O2", 2e-8]], "p_total_Pa": 0.01, "T_K": 350.0,
          "label": "PARAMETRIC_SENSITIVITY", "source": SYN, "evidence_class": "assumed", "status": "",
          "p_species_Pa": None, "extra": {}}
    conv = py_inlet_record(ok).module_partial_pressures()
    return [("label", {**ok, "label": "BOGUS"}), ("species", {**ok, "mdot_kgps": [["O", 4e-7], ["N2", 3e-7]]}),
            ("negative", {**ok, "mdot_kgps": [["O", -4e-7], ["N2", 3e-7], ["O2", 2e-8]]}),
            ("nan", {**ok, "mdot_kgps": [["O", "NaN"], ["N2", 3e-7], ["O2", 2e-8]]}),
            ("zero-total", {**ok, "mdot_kgps": [["O", 0.0], ["N2", 0.0], ["O2", 0.0]]}),
            ("p0", {**ok, "p_total_Pa": 0.0}), ("T-nan", {**ok, "T_K": "NaN"}),
            ("class", {**ok, "evidence_class": "guess"}), ("source", {**ok, "source": " "}),
            ("p-sum", {**ok, "p_species_Pa": [["O", conv["O"] * 1.1], ["N2", conv["N2"]], ["O2", conv["O2"]]]}),
            ("p-convention", {**ok, "p_species_Pa": [["O", conv["N2"]], ["N2", conv["O"]], ["O2", conv["O2"]]]})]


def basis_mutation(g, b):
    b = copy.deepcopy(b)
    kind = int(g.integers(0, 12))
    if kind == 0:
        b[pick(g, ["basis_id", "materials_db_key", "material_spec", "product_form", "condition", "allowable_basis",
                   "allowable_source", "density_source", "factors_source", "registration"])] = pick(g, ["", "  "])
    elif kind == 1:
        b[pick(g, ["design_temperature_K", "density_kg_m3", "max_design_speed_rpm"])] = pick(g, [0.0, -1.0, "NaN"])
    elif kind == 2:
        b[pick(g, ["factor_yield", "factor_ultimate"])] = U(g, 0.5, 0.99)
    elif kind == 3:
        p = b["allowables"][int(g.integers(len(b["allowables"])))]
        p[1] = p[2] * U(g, 1.01, 1.2)
    elif kind == 4:
        b["allowables"] = list(reversed(b["allowables"]))
    elif kind == 5:
        b["allowables"].append(list(b["allowables"][-1]))
    elif kind == 6:
        b["design_temperature_K"] = b["allowables"][-1][0] + U(g, 1, 100)
    elif kind == 7:
        b["proof_spin_basis"] = None
        b["proof_spin_not_applicable_reason"] = "synthetic reason" if P(g, 0.5) else None
    elif kind == 8:
        b["section_thickness_range_m"] = pick(g, [[0.2, 0.01], [0.01], [0.0, 0.2], ["NaN", 0.2]])
    elif kind == 9:
        b["allowables"] = []
    elif kind == 10:
        b["allowables"][0][int(g.integers(0, 3))] = pick(g, [0.0, -5.0, "NaN"])
    else:
        b["design_temperature_K"] = b["allowables"][0][0] - U(g, 1, 100)
    return b


def vectors_compressor(master: int) -> list:
    V = []

    def add(vid, entry, args):
        V.append({"id": vid, "entry": entry, "args": args})
    d0 = {f: cs.module_defaults()[f] for f in COMP_FIELDS}
    gold_mdot = [["O", 4e-7], ["N2", 3e-7], ["O2", 2e-8]]
    # C01 run
    add("C01-G-defaults", "compressor.run", {"coeffs": d0, "p_in_Pa": 0.01, "mdot": gold_mdot, "self_consistent": True,
                                            "registry": []})
    add("C01-E-unobtainium", "compressor.run", {"coeffs": {**d0, "rotor_material": "Unobtainium"}, "p_in_Pa": 0.01,
                                                "mdot": gold_mdot, "self_consistent": True, "registry": []})
    add("C01-E-capacity", "compressor.run", {"coeffs": d0, "p_in_Pa": 1e-6, "mdot": [[s, 1e-5] for s in SPECIES],
                                             "self_consistent": True, "registry": []})
    add("C01-E-overflow", "compressor.run", {"coeffs": {**d0, "turbo_kK": 1e3}, "p_in_Pa": 0.01, "mdot": gold_mdot,
                                             "self_consistent": True, "registry": []})
    g = rng(master, 1)
    for i in range(300):
        reg = gen_registry(g)
        c = gen_coeffs(g, reg)
        add(f"C01-R-{i:03d}", "compressor.run", {"coeffs": c, "p_in_Pa": LU(g, -4, -0.5), "mdot": gen_mdot(g),
                                                 "self_consistent": P(g, 0.85), "registry": reg})
    g = rng(master, 2)
    for i in range(24):
        reg = gen_registry(g)
        c = gen_coeffs(g, reg)
        add(f"C02-R-{i:02d}", "compressor.size_for", {
            "coeffs": c, "p_in_Pa": LU(g, -4, -1.5), "mdot": gen_mdot(g), "CR_target": LU(g, 0.5, 3),
            "rpm_max": U(g, 2e4, 9e4), "max_turbo_rows": int(g.integers(1, 7)), "max_drag_stages": int(g.integers(0, 5)),
            "registry": reg})
    g = rng(master, 3)
    for i in range(200):
        b = syn_basis(g)
        if P(g, 0.8):
            b = basis_mutation(g, b)
        add(f"C03-R-{i:03d}", "compressor.basis_problems", {"basis": b})
    g = rng(master, 4)
    for i in range(100):
        b = syn_basis(g)
        Ts = [p[0] for p in b["allowables"]]
        T = U(g, Ts[0] - 50, Ts[-1] + 50) if P(g, 0.7) else pick(g, Ts)
        add(f"C04-R-{i:03d}", "compressor.allowables_at", {"basis": b, "T_K": T})
    g = rng(master, 5)
    for i in range(60):
        add(f"C05-R-{i:02d}", "compressor.tip_speed_allowable", {"basis": syn_basis(g)})
    g = rng(master, 6)
    for i in range(300):
        reg = [syn_basis(g)] if P(g, 0.7) else []
        bid = pick(g, [SYN_TI, None, "UNREGISTERED-ID"], p=[0.7, 0.15, 0.15])
        mat = "Ti6Al4V" if P(g, 0.8) else pick(g, ["Al6061", "CFRP", "SS316"])
        rpm = U(g, 0, 1.2e5)
        if P(g, 0.2):
            rpm = int(round(rpm))
        add(f"C06-R-{i:03d}", "compressor.qualify_rotor", {
            "registry": reg, "basis_id": bid, "rotor_material": mat, "tip_speed_mps": U(g, 0, 600), "rpm": rpm,
            "T_rotor_K": U(g, 200, 900), "stock_thickness_m": U(g, 0.005, 0.25) if P(g, 0.7) else None})
    g = rng(master, 106)
    b = syn_basis(g)
    base = {"registry": [b], "basis_id": SYN_TI, "rotor_material": "Ti6Al4V", "tip_speed_mps": 300.0, "rpm": 50000.0,
            "T_rotor_K": b["allowables"][0][0], "stock_thickness_m": 0.05}
    for name, kw in (("tip-nan", {"tip_speed_mps": "NaN"}), ("tip-neg", {"tip_speed_mps": -1.0}),
                     ("rpm-nan", {"rpm": "NaN"}), ("T-nan", {"T_rotor_K": "NaN"}),
                     ("T-above", {"T_rotor_K": b["design_temperature_K"] + 10.0}), ("stock-null",
                                                                                   {"stock_thickness_m": None}),
                     ("stock-0", {"stock_thickness_m": 0.0}), ("stock-outside", {"stock_thickness_m": 0.3}),
                     ("material", {"rotor_material": "Al6061"}), ("unregistered", {"basis_id": "UNREGISTERED-ID"}),
                     ("null-id", {"basis_id": None})):
        add(f"C06-E-{name}", "compressor.qualify_rotor", {**base, **kw})
    g = rng(master, 7)
    b = syn_basis(g)
    add("C07-E-incomplete", "compressor.register_basis", {"registry_before": [], "basis": {**b, "registration": ""}})
    add("C07-E-duplicate", "compressor.register_basis", {"registry_before": [b], "basis": b})
    add("C07-V-1", "compressor.register_basis", {"registry_before": [], "basis": b})
    add("C07-V-2", "compressor.register_basis", {"registry_before": [syn_basis(g, SYN_AL, "Al6061")], "basis": b})
    g = rng(master, 9)
    for i in range(100):
        r = gen_inlet_record(g, -8, -5, -4, -0.3, rid=f"SYN-{i}")
        if P(g, 0.3):
            conv = py_inlet_record(r).module_partial_pressures()
            r["p_species_Pa"] = [[s, conv[s]] for s in SPECIES]
        if P(g, 0.2):
            r["extra"] = {"note": SYN}
        add(f"C09-R-{i:03d}", "compressor.inlet_record", {"inlet": r})
    for name, r in inlet_edges():
        add(f"C09-E-{name}", "compressor.inlet_record", {"inlet": r})
    add("C10-G-default", "compressor.search_grid", {"grid": None, "registry": []})
    g = rng(master, 10)
    for i in range(20):
        reg = [syn_basis(g, SYN_AL, "Al6061")] if P(g, 0.3) else []
        mats = ["Ti6Al4V"] + (["Al6061"] if reg else [])
        grid = {"n_turbo": sorted({int(x) for x in g.integers(1, 7, size=int(g.integers(1, 4)))}),
                "a_turbo_m2": [U(g, 0.05, 0.5) for _ in range(int(g.integers(1, 3)))],
                "n_tip_speeds": int(g.integers(2, 7)),
                "n_drag": sorted({int(x) for x in g.integers(0, 5, size=int(g.integers(1, 3)))}),
                "materials": mats,
                "hub_ratios": sorted({pick(g, list(cs.HUB_RATIO_PARAMETRIC)) for _ in range(int(g.integers(1, 4)))})}
        add(f"C10-R-{i:02d}", "compressor.search_grid", {"grid": grid, "registry": reg})
    for name, grid in (("al-no-basis", {"materials": ["Ti6Al4V", "Al6061"]}), ("hub-1", {"hub_ratios": [0.0, 1.0]}),
                       ("tips-1", {"n_tip_speeds": 1}), ("a0", {"a_turbo_m2": [0.0, 0.1]})):
        add(f"C10-E-{name}", "compressor.search_grid", {"grid": grid, "registry": []})
    g = rng(master, 11)
    for i in range(100):
        k = i % 3
        if k == 0:
            add(f"C11-R-{i:03d}", "compressor.r_turbo_from_area", {"a_m2": U(g, 0.05, 0.5),
                                                                   "hub_ratio": pick(g, list(cs.HUB_RATIO_PARAMETRIC))
                                                                   if P(g, 0.7) else U(g, 0, 1)})
        elif k == 1:
            add(f"C11-R-{i:03d}", "compressor.hub_geometry", {"a_m2": U(g, 0.05, 0.5),
                                                              "hub_ratio": pick(g, list(cs.HUB_RATIO_PARAMETRIC))
                                                              if P(g, 0.7) else U(g, 0, 1)})
        else:
            add(f"C11-R-{i:03d}", "compressor.rpm_from_tip", {"u_mps": U(g, 50, 600), "r_m": U(g, 0.05, 0.5)})
    g = rng(master, 12)
    regs = {"empty": [], "ti": [syn_basis(g)], "all": [syn_basis(g), syn_basis(g, SYN_AL, "Al6061"),
                                                         syn_basis(g, SYN_CF, "CFRP")]}
    extras = {"none": None, "partial": {cs.AO_DISPOSITION_KEY: "SYN"}, "full": extra_full()}
    for m in DB:
        for rk, reg in regs.items():
            for ek, ex in extras.items():
                add(f"C12-{m}-{rk}-{ek}", "compressor.material_admission", {"material": m, "extra": ex,
                                                                             "registry": reg})
    add("C12-E-unobtainium", "compressor.material_admission", {"material": "Unobtainium", "extra": None,
                                                                "registry": []})
    g = rng(master, 13)
    dd = default_designs()
    for i in range(100):
        d = dd[int(g.integers(len(dd)))] if P(g, 0.5) else random_design(g, i)
        add(f"C13-V-{i:03d}", "compressor.validate_design", {"design": d})
    for f in FIXED_FIELDS:
        for j, val in enumerate([0.0, -1.0, "NaN", "+inf", 1.5, True]):
            add(f"C13-C-{f}-{j}", "compressor.validate_coefficient", {"name": f, "value": val})
    add("C13-C-searched", "compressor.validate_coefficient", {"name": "turbo_rows", "value": 3.0})
    good = dict(dd[100])
    for name, kw in (("rpm0", {"rpm": 0.0}), ("A-nan", {"A_turbo_m2": "NaN"}), ("R-neg", {"R_turbo_m": -1.0}),
                     ("N-1.5", {"N_turbo": 1.5}), ("N-neg", {"N_turbo": -1}), ("N-true", {"N_turbo": True}),
                     ("material", {"rotor_material": "Unobtainium"}), ("hub-1", {"hub_ratio": 1.0}),
                     ("R-inconsistent", {"R_turbo_m": good["R_turbo_m"] * 1.01})):
        add(f"C13-D-{name}", "compressor.validate_design", {"design": {**good, **kw}})
    g = rng(master, 14)
    for i in range(60):
        reg = gen_registry(g)
        r = gen_inlet_record(g, rid=f"SYN-{i}")
        ev = gen_evidence(g, reg)
        if ev is not None and P(g, 0.3):
            f = pick(g, FIXED_FIELDS)
            ev[f] = {"value": pick(g, [0.0, -1.0, "NaN", 1.5]), "evidence_class": "measured", "source": SYN}
        if ev is not None and P(g, 0.2):
            ev["rotor_density"] = {"value": pick(g, ["NaN", -1.0, 0.0]), "evidence_class": "measured", "source": SYN}
        add(f"C14-R-{i:02d}", "compressor.strict_blockers", {"inlet": r, "coefficient_evidence": ev, "registry": reg})
    g = rng(master, 15)
    for i in range(400):
        reg = gen_registry(g)
        if P(g, 0.1):
            reg.append(syn_basis(g, SYN_AL, "Al6061"))
        d = dict(dd[int(g.integers(len(dd)))]) if P(g, 0.6) else random_design(g, i)
        if P(g, 0.3):
            d["rotor_stock_thickness_m"] = U(g, 0.005, 0.25)
        r = gen_inlet_record(g, rid=f"SYN-{i}")
        add(f"C15-R-{i:03d}", "compressor.evaluate_design", {
            "design": d, "inlet": r, "mode": cs.MODE_PARAMETRIC if P(g, 0.85) else cs.MODE_STRICT,
            "coefficient_evidence": gen_evidence(g, reg), "registry": reg})
    gold_inlet = {"record_id": "GOLD", "mdot_kgps": gold_mdot, "p_total_Pa": 0.01, "T_K": 350.0,
                  "label": "PARAMETRIC_SENSITIVITY", "source": SYN, "evidence_class": "assumed", "status": "",
                  "p_species_Pa": None, "extra": {}}
    add("C15-E-overflow", "compressor.evaluate_design", {
        "design": dd[0], "inlet": gold_inlet, "mode": cs.MODE_PARAMETRIC,
        "coefficient_evidence": {"turbo_kK": {"value": 1e3, "evidence_class": "measured", "source": SYN}},
        "registry": []})
    add("C15-E-mode", "compressor.evaluate_design", {"design": dd[0], "inlet": gold_inlet, "mode": "turbo",
                                                     "coefficient_evidence": None, "registry": []})
    g = rng(master, 16)
    for i in range(100):
        c = gen_coeffs(g, [])
        add(f"C16-R-{i:03d}", "compressor.stage_trace", {"coeffs": c, "p_in_Pa": LU(g, -4, -0.5),
                                                         "mdot": gen_mdot(g), "registry": []})
    g = rng(master, 17)
    for i in range(100):
        ps = [[s, LU(g, -4, -0.5) if P(g, 0.85) else 0.0] for s in SPECIES if P(g, 0.9)]
        add(f"C17-R-{i:03d}", "compressor.drag_knudsen", {"p_species": ps, "T_K": U(g, 250, 450),
                                                          "h_m": U(g, 1e-3, 5e-3)})
    g = rng(master, 18)
    for i in range(50):
        recs = []
        n = int(g.integers(3, 21))
        for j in range(n):
            if P(g, 0.15):
                recs.append({"id": f"R{j:02d}", "outputs": None})
                continue
            o = {"P_out_Pa": LU(g, -3, 0), "mdot_delivered_total_kgps": LU(g, -8, -6),
                 "P_compressor_el_W": U(g, 5, 200), "m_compressor_kg": U(g, 1, 10), "S_turbo_m3_s": U(g, 1, 50)}
            if recs and P(g, 0.15):
                prev = recs[int(g.integers(len(recs)))]
                if prev["outputs"]:
                    o = dict(prev["outputs"])
            if P(g, 0.05):
                o[pick(g, list(o))] = pick(g, ["NaN", "+inf"])
            recs.append({"id": f"R{j:02d}", "outputs": o})
        order = list(g.permutation(len(recs)))
        add(f"C18-R-{i:02d}", "compressor.pareto_front", {"records": [recs[int(k)] for k in order],
                                                          "objectives": "secondary" if P(g, 0.3) else "primary"})
    for k, (p, mult) in enumerate(((0.001, 1.0), (0.01, 2.0), (0.05, 5.0), (0.2, 10.0))):
        inl = {**gold_inlet, "record_id": f"GOLD-{k}", "p_total_Pa": p, "mdot_kgps": [[s, v * mult]
                                                                                      for s, v in gold_mdot]}
        add(f"C19-G-{k}", "compressor.synthesize", {"inlet": inl, "mode": cs.MODE_PARAMETRIC, "grid": None,
                                                    "coefficient_evidence": None, "registry": []})
    add("C19-E-strict", "compressor.synthesize", {"inlet": gold_inlet, "mode": cs.MODE_STRICT, "grid": None,
                                                  "coefficient_evidence": None, "registry": []})
    g = rng(master, 19)
    for i in range(2):
        reg = [syn_basis(g)]
        grid = {"n_turbo": [1, 3, 5], "a_turbo_m2": [U(g, 0.05, 0.5)], "n_tip_speeds": 4, "n_drag": [0, 2],
                "materials": ["Ti6Al4V"], "hub_ratios": [0.0, 0.5]}
        add(f"C19-R-{i}", "compressor.synthesize", {"inlet": gen_inlet_record(g, rid=f"SYN-{i}"),
                                                    "mode": cs.MODE_PARAMETRIC, "grid": grid,
                                                    "coefficient_evidence": {"rotor_strength_basis_id": {"value": SYN_TI}}
                                                    if i == 1 else None, "registry": reg})
    add("C19-E-mode", "compressor.synthesize", {"inlet": gold_inlet, "mode": "turbo", "grid": None,
                                                "coefficient_evidence": None, "registry": []})
    g = rng(master, 20)
    for i in range(4):
        recs = []
        for j in range(int(g.integers(3, 8))):
            recs.append({"id": f"F{j}", "outputs": {"P_out_Pa": LU(g, -2, 0), "mdot_delivered_total_kgps": LU(g, -8, -6),
                                                    "P_compressor_el_W": U(g, 5, 200), "m_compressor_kg": U(g, 1, 10),
                                                    "S_turbo_m3_s": U(g, 1, 50)}})
        add(f"C20-R-{i}", "compressor.size_for_comparison", {
            "inlet": {**gold_inlet, "p_total_Pa": LU(g, -3, -1.5)}, "cr_target": U(g, 2, 50),
            "a_turbo_m2": pick(g, list(cs.SearchGrid().a_turbo_m2)), "front_records": recs, "material": "Ti6Al4V",
            "mode": cs.MODE_PARAMETRIC, "registry": []})
    add("C21-G-constants", "compressor.constants", {})
    g = rng(master, 22)
    add("C22-G-official", "compressor.ledger_slot", {"compressor_P_W": None, "compressor_source": ""})
    for i in range(10):
        add(f"C22-R-{i}", "compressor.ledger_slot", {"compressor_P_W": U(g, 0, 500),
                                                     "compressor_source": "" if P(g, 0.5) else f"synthetic source {i}"})
    return V


def py_constants_compressor():
    return {"module_defaults": cs.module_defaults(),
            "FIELD_ROLES": [[f, *v] for f, v in cs.FIELD_ROLES.items()],
            "COEFFICIENT_DOMAIN": [[k, d] for k, d in cs.COEFFICIENT_DOMAIN.items()],
            "REASONS": list(cs.REASONS), "DOMAIN_REASONS": list(cs.DOMAIN_REASONS),
            "INLET_INDEPENDENT_REASONS": list(cs.INLET_INDEPENDENT_REASONS),
            "HUB_RATIO_PARAMETRIC": list(cs.HUB_RATIO_PARAMETRIC), "HUB_BOUND_SOURCES": list(cs.HUB_BOUND_SOURCES),
            "CFRP_EXTRA_BASIS_KEYS": list(cs.CFRP_EXTRA_BASIS_KEYS), "P_MOLECULAR_LIMIT_PA": cs.P_MOLECULAR_LIMIT_PA,
            "KN_FREE_MOLECULAR_MIN": cs.KN_FREE_MOLECULAR_MIN, "SIGMA_C_M2": dict(cs.SIGMA_C_M2),
            "U_TIP_PUBLISHED_MAX_MPS": cs.U_TIP_PUBLISHED_MAX_MPS, "TI64_FTY_A_BASIS_PA": cs.TI64_FTY_A_BASIS_PA,
            "RECIRC_RTOL": cs.RECIRC_RTOL, "MIRROR_RTOL": cs.MIRROR_RTOL, "RPM_SEARCH_MIN": cs.RPM_SEARCH_MIN,
            "SIZE_FOR_MAX_TURBO_ROWS": cs.SIZE_FOR_MAX_TURBO_ROWS,
            "SIZE_FOR_MAX_DRAG_STAGES": cs.SIZE_FOR_MAX_DRAG_STAGES,
            "OWNER_MASS_ALLOCATION_KG": cs.OWNER_MASS_ALLOCATION_KG,
            "LI2015_INLET_DIAMETER_M": cs.LI2015_INLET_DIAMETER_M,
            "A_INLET_MIN_B025_RANGE_M2": list(cs.A_INLET_MIN_B025_RANGE_M2),
            "CITED_ALLOWABLES_PA": dict(cs.CITED_ALLOWABLES_PA), "MATERIALS_EXCLUDED": dict(cs.MATERIALS_EXCLUDED),
            "LEGACY_SENSITIVITY_LABEL": rs.LEGACY_SENSITIVITY_LABEL, "OWNER_DECISION_ID": rs.OWNER_DECISION_ID,
            "REFERENCE_RECORDS": rs.REFERENCE_RECORDS, "RECIRC_MAX_ITER": cmod.DragCompressor.RECIRC_MAX_ITER,
            "DragCompressor.RECIRC_RTOL": cmod.DragCompressor.RECIRC_RTOL,
            "GAEDE_IN_DOMAIN": cmod.DragCompressor.GAEDE_IN_DOMAIN,
            "GAEDE_OUT_OF_DOMAIN": cmod.DragCompressor.GAEDE_OUT_OF_DOMAIN}


def py_ledger_slot(p_w, source):
    L = aopt.official_ledger("hall_icp_neutralizer", compressor_P_W=p_w, compressor_source=source)
    it = next(i for i in L["items"] if i["slot"] == "compressor")
    return {"P_W": it["P_W"], "evidence_class": it["evidence_class"], "source": it["source"],
            "ledger_label": L["label"], "status": "NOT_EVALUATED"}


def py_args_obj(x):
    """Transported JSON -> Python object (non-finite strings back to floats, recursively)."""
    if isinstance(x, dict):
        return {k: py_args_obj(v) for k, v in x.items()}
    if isinstance(x, list):
        return [py_args_obj(v) for v in x]
    return unj(x)


def py_compressor(v):
    a = v["args"]
    e = v["entry"]
    reg = a.get("registry")

    def call(fn):
        def wrapped():
            with Registered(reg):
                return fn()
        return py_call(wrapped)
    if e == "compressor.run":
        return call(lambda: py_comp(a["coeffs"]).run(unj(a["p_in_Pa"]), {k: unj(x) for k, x in a["mdot"]},
                                                      a["self_consistent"]))
    if e == "compressor.size_for":
        return call(lambda: py_comp(a["coeffs"]).size_for(unj(a["p_in_Pa"]), {k: unj(x) for k, x in a["mdot"]},
                                                           a["CR_target"], a["rpm_max"], a["max_turbo_rows"],
                                                           a["max_drag_stages"]))
    if e == "compressor.basis_problems":
        return call(lambda: rs.basis_problems(py_basis(a["basis"])))
    if e == "compressor.allowables_at":
        return call(lambda: rs.allowables_at(py_basis(a["basis"]), a["T_K"]))
    if e == "compressor.tip_speed_allowable":
        return call(lambda: rs.tip_speed_allowable(py_basis(a["basis"])))
    if e == "compressor.qualify_rotor":
        return call(lambda: rs.qualify_rotor(a["basis_id"], a["rotor_material"], unj(a["tip_speed_mps"]),
                                             unj(a["rpm"]), unj(a["T_rotor_K"]), unj(a["stock_thickness_m"])))
    if e == "compressor.register_basis":
        def f():
            with Registered(a["registry_before"]):
                rs.register_basis(py_basis(a["basis"]))
            return "REGISTERED"
        return py_call(f)
    if e == "compressor.inlet_record":
        def f():
            r = py_inlet_record(a["inlet"])
            return {"as_dict": r.as_dict(), "module_partial_pressures": r.module_partial_pressures()}
        return call(f)
    if e == "compressor.search_grid":
        def f():
            gd = a["grid"]
            g = cs.SearchGrid() if gd is None else cs.SearchGrid(**{k: tuple(py_args_obj(x)) if isinstance(x, list)
                                                                     else x for k, x in gd.items()})
            return g.designs()
        return call(f)
    if e == "compressor.r_turbo_from_area":
        return call(lambda: cs.r_turbo_from_area(a["a_m2"], a["hub_ratio"]))
    if e == "compressor.hub_geometry":
        return call(lambda: cs.hub_geometry(a["a_m2"], a["hub_ratio"]))
    if e == "compressor.rpm_from_tip":
        return call(lambda: cs.rpm_from_tip(a["u_mps"], a["r_m"]))
    if e == "compressor.material_admission":
        return call(lambda: cs.material_admission(a["material"], a["extra"]))
    if e == "compressor.validate_coefficient":
        return call(lambda: cs.validate_coefficient(a["name"], unj(a["value"])))
    if e == "compressor.validate_design":
        def f():
            cs.validate_design(py_args_obj(a["design"]))
            return "VALID"
        return call(f)
    if e == "compressor.strict_blockers":
        return call(lambda: cs.strict_blockers(py_inlet_record(a["inlet"]), py_args_obj(a["coefficient_evidence"])))
    if e == "compressor.evaluate_design":
        return call(lambda: cs.evaluate_design(py_args_obj(a["design"]), py_inlet_record(a["inlet"]), a["mode"],
                                               py_args_obj(a["coefficient_evidence"])))
    if e == "compressor.stage_trace":
        return call(lambda: cs.stage_trace(py_comp(a["coeffs"]), unj(a["p_in_Pa"]), {k: unj(x) for k, x in a["mdot"]}))
    if e == "compressor.drag_knudsen":
        return call(lambda: cs.drag_knudsen_upper({k: unj(x) for k, x in a["p_species"]}, a["T_K"], a["h_m"]))
    if e == "compressor.pareto_front":
        obj = cs.SECONDARY_OBJECTIVES if a["objectives"] == "secondary" else cs.PRIMARY_OBJECTIVES
        return call(lambda: cs.pareto_front(py_args_obj(a["records"]), obj))
    if e == "compressor.synthesize":
        def f():
            gd = a["grid"]
            g = None if gd is None else cs.SearchGrid(**{k: tuple(x) if isinstance(x, list) else x
                                                          for k, x in gd.items()})
            return cs.synthesize(py_inlet_record(a["inlet"]), a["mode"], g, py_args_obj(a["coefficient_evidence"]))
        return call(f)
    if e == "compressor.size_for_comparison":
        return call(lambda: cs.size_for_comparison(py_inlet_record(a["inlet"]), a["cr_target"], a["a_turbo_m2"],
                                                   py_args_obj(a["front_records"]), a["material"], a["mode"]))
    if e == "compressor.constants":
        return py_call(py_constants_compressor)
    if e == "compressor.ledger_slot":
        return py_call(lambda: py_ledger_slot(a["compressor_P_W"], a["compressor_source"]))
    raise RuntimeError(e)


ITERATIVE = {"compressor.run", "compressor.size_for", "compressor.evaluate_design", "compressor.synthesize",
             "compressor.size_for_comparison"}
KGS_MAPS = {"leak_kgps", "recirculated_kgps", "delivered_kgps"}


def inlet_mdot_total(a):
    if "mdot" in a:
        return sum(unj(x) for _, x in a["mdot"])
    if "inlet" in a and isinstance(a["inlet"], dict):
        return sum(unj(x) for _, x in a["inlet"]["mdot_kgps"])
    return 0.0


def rule_compressor(ctx, path, py):
    e = ctx["entry"]
    if e not in ITERATIVE:
        return ("ULP", CF)
    tol = {"rel": 1e-10, "k_ulp": 4, "abs": 0.0}
    leaf = path[-1] if path else ""
    parent = path[-2] if len(path) >= 2 else ""
    if parent in KGS_MAPS or (parent == "mdot_delivered_kgps"):
        tol["abs"] = 1e-12 * inlet_mdot_total(ctx["vector"]["args"])
    if leaf in ("residual", "recirculation_residual", "recirculation_frac"):
        tol["abs"] = 1e-12
    return ("SOLVER", tol)


def checks_compressor(t, vectors, py_out, rres):
    cons1, cons2, inv2, inv4 = [], [], True, True
    for v in vectors:
        r = rres[v["id"]]
        po = py_out[v["id"]]
        a = v["args"]
        if v["entry"] == "compressor.run" and r["outcome"] == "OK":
            val = r["value"]
            if a.get("self_consistent"):
                exp = {k: unj(x) for k, x in a["mdot"]}
                ok = all(val["delivered_kgps"][k] == exp[k] for k in exp)
                cons1.append({"vector": v["id"], "ok": ok})
            c = a["coeffs"]
            P_el, P_gas, P_bear = val["P_el_W"], val["P_gas_W"], val["P_bear_W"]
            if all(isinstance(x, float) for x in (P_el, P_gas, P_bear, val["torque_Nm"])):
                omega = c["rpm"] * 2 * math.pi / 60.0
                r1 = abs(P_el - ((P_gas + P_bear) / c["eta_motor"] + c["P_ctrl_W"]))
                r2 = abs(val["torque_Nm"] * omega - (P_gas + P_bear))
                cons2.append({"vector": v["id"], "residual_rel": max(r1, r2) / max(abs(P_el), 1e-300),
                              "ok": max(r1, r2) <= 1e-12 * abs(P_el)})
            if not a.get("registry"):
                for side in (val, po[1] if po[0] == "OK" else None):
                    if side and (side.get("rotor_qualification") != rs.Q_NOT_EVALUATED_MATERIAL_BASIS
                                 or side.get("rotor_ok") is not False
                                 or side.get("sizing_mode") != rs.SIZING_PARAMETRIC_SENSITIVITY):
                        inv2 = False
        if v["id"] == "C19-E-strict":
            for side in (r.get("value"), po[1] if po[0] == "OK" else None):
                if not side or side.get("status") != cs.ST_NOT_EVALUATED_MATERIAL_BASIS or not side.get("blockers") \
                        or side.get("designs"):
                    inv4 = False
    return {"CONS-C-01": {"n": len(cons1), "n_fail": sum(1 for c in cons1 if not c["ok"]),
                          "failures": [c for c in cons1 if not c["ok"]][:20], "ok": all(c["ok"] for c in cons1)},
            "CONS-C-02": {"n": len(cons2), "n_fail": sum(1 for c in cons2 if not c["ok"]),
                          "max_residual_rel": max((c["residual_rel"] for c in cons2), default=0.0),
                          "failures": [c for c in cons2 if not c["ok"]][:20], "ok": all(c["ok"] for c in cons2)},
            "INV-C-02": {"ok": inv2}, "INV-C-04": {"ok": inv4}}


# ======================================================================================================================
# Plenum / feed contract (key 'plenum'; plenum_feed + reservoir + upstream_a9_13)
# ======================================================================================================================
_POOL = None
_F3 = None
F1_AREAS = [0.25, 0.5, 1.0]
F1_SCEN = ["cll_a0.8", "maxwell_a1", "maxwell_a0.5", "cll_a0.5"]
FLOOR: dict = {}        # vector id -> forward source mass flow sum_s f_s m_s / (k T) (kg/s floor basis)
TAP: dict = {}          # vector id -> per-segment u_cmd at the segment end (+ samples), Python reference instrumentation
_CUR = {"vid": None}


def pool():
    global _POOL
    if _POOL is None:
        _POOL = pf.load_f1_records(pf.load_f1(Path(ROOT)), F1_AREAS, scenarios=F1_SCEN, states=None)
    return _POOL


def f3_grid():
    global _F3
    if _F3 is None:
        _F3 = json.load(open(os.path.join(ROOT, "docs/design_synthesis/f3_compressor/f3_compressor_designs_v1.json"))
                        )["design_grid"]
    return _F3


def intake_spec(it):
    return {"candidate": it.candidate, "area_m2": it.area_m2, "state": it.state, "scenario": it.scenario,
            "T_K": it.T_K, "mdot_fwd_kgps": [[s, it.mdot_fwd_kgps[s]] for s in SPECIES],
            "p_passive_Pa": [[s, it.p_passive_Pa[s]] for s in SPECIES], "K_back": [[s, it.K_back[s]] for s in SPECIES],
            "f1_status": it.f1_status, "source": it.source, "alt_km": isy.state_alt_km(it.state)}


def py_intake_state(d):
    return pf.IntakeState(candidate=d["candidate"], area_m2=d["area_m2"], state=d["state"], scenario=d["scenario"],
                          T_K=d["T_K"], mdot_fwd_kgps={k: v for k, v in d["mdot_fwd_kgps"]},
                          p_passive_Pa={k: v for k, v in d["p_passive_Pa"]}, K_back={k: v for k, v in d["K_back"]},
                          f1_status=d["f1_status"], source=d.get("source") or "")


def py_filter_case(d):
    f = d["factory"]
    if f == "none":
        return pf.filter_none()
    if f == "parametric":
        return pf.filter_parametric(d["tau"])
    if f == "placeholder":
        return pf.filter_placeholder()
    if f == "stage":
        return pf.filter_case_from_stage(d["case_id"], py_stage(d["stage"]), py_case(d["case"]), d.get("note") or "")
    raise RuntimeError(f)


def fc_dict(fc):
    d = dataclasses.asdict(fc)
    d["reference_bound_only"] = fc.reference_bound_only
    return d


def py_plenum_obj(d):
    kw = {k: unj(d[k]) for k in ("volume_m3", "gamma_wall", "leak_area_m2") if k in d}
    if "T_K" in d:
        kw["T_K"] = unj(d["T_K"])
    return pf.Plenum(wall_case=d.get("wall_case") or "", **kw)


def py_plant(d):
    return pf.CompressorPlant.from_design(d["design"], d.get("T_K", pf.T_CHAIN_K))


def py_chain(d):
    return pf.Chain(py_intake_state(d["intake"]), py_filter_case(d["filter"]), py_plant(d["plant"]),
                    py_plenum_obj(d["plenum"]))


def py_controller(d):
    return pf.Controller(d["Kp"], d["Ti_s"], d["f_valve_hz"], d["authority"])


def gen_filter_spec(g):
    r = g.random()
    if r < 0.3:
        return {"factory": "none"}
    if r < 0.8:
        return {"factory": "parametric", "tau": pick(g, [0.9, 0.7, 0.5]) if P(g, 0.5) else U(g, 0.05, 1)}
    return {"factory": "placeholder"}


def gen_plenum_spec(g, v_lo=-3.5, v_hi=-1.0):
    r = g.random()
    gamma = 0.0 if r < 0.4 else (DB["Ti6Al4V"].gamma_O(350.0) if r < 0.7 else U(g, 0, 0.1))
    return {"volume_m3": LU(g, v_lo, v_hi), "gamma_wall": gamma, "wall_case": "SYN-WALL (" + SYN + ")",
            "leak_area_m2": pf.RES_DEFAULTS["leak_area_m2"] if P(g, 0.7) else U(g, 0, 1e-6)}


def gen_chain(g, rec=None):
    rec = rec if rec is not None else pool()[int(g.integers(len(pool())))]
    return {"intake": intake_spec(rec), "filter": gen_filter_spec(g),
            "plant": {"design": f3_grid()[int(g.integers(len(f3_grid())))]}, "plenum": gen_plenum_spec(g)}


def forward_source_kgps(chain_obj, density_factor=1.0):
    co = chain_obj.node_coefficients(density_factor)
    return sum(co[s]["f"] / pf.kT_over_m(s, chain_obj.intake.T_K) for s in SPECIES)


def design_records():
    return [r for r in pool() if r.state == "h200_f150"]


def gen_controller(g):
    return {"Kp": U(g, 0.5, 10), "Ti_s": U(g, 0.1, 3), "f_valve_hz": pick(g, [0.1, 1.0, 10.0]),
            "authority": U(g, 1.5, 4)}


def synth_segment(g, kind=None):
    D = U(g, 5, 120)
    te = np.unique(np.concatenate([[0.0], np.geomspace(1e-6 * max(D, 1.0), D, 150)]))
    te[-1] = D
    t = [float(x) for x in te]
    r = LU(g, -3, -1)

    def osc(final, amp):
        k, w, ph = LU(g, -2, 0.5), U(g, 0, 2), U(g, 0, 2 * math.pi)
        return [final * (1.0 + amp * math.exp(-k * x) * math.cos(w * x + ph)) for x in t]
    p = osc(r * (1.0 + U(g, -0.01, 0.01)), U(g, 0, 0.3))
    md = osc(LU(g, -8, -6), U(g, 0, 0.3))
    u = [min(max(x, 0.0), 1.0) for x in osc(U(g, 0.1, 0.9), U(g, 0, 0.5))]
    xo = [("NaN" if P(g, 0.1) else min(max(x, 0.0), 1.0)) for x in osc(U(g, 0.2, 0.8), U(g, 0, 0.2))]
    kind = kind or pick(g, ["hold", "setpoint", "feed_path", "supply", "orbit"])
    return {"event": f"SYN-{kind}", "kind": kind, "t": t, "p": p, "mdot": md, "u": u, "xO": xo, "setpoint_Pa": r,
            "saturated_end": P(g, 0.2), "K_min": U(g, 0.999, 1.5), "K_over_K0_max": U(g, 0.5, 1.001),
            "p_stage_max_Pa": LU(g, -2, -0.9), "p_inlet_max_Pa": LU(g, -3, -0.9), "T_comp_max_K": U(g, 300, 800),
            "T_comp_limit_K": U(g, 500, 700)}


def py_segment(d):
    return {"event": d["event"], "kind": d["kind"], "t": np.array(d["t"]), "p": np.array(d["p"]),
            "mdot": np.array(d["mdot"]), "u": np.array(d["u"]), "xO": np.array([unj(x) for x in d["xO"]]),
            "setpoint_Pa": d["setpoint_Pa"], "saturated_end": d["saturated_end"], "K_min": d["K_min"],
            "K_over_K0_max": d["K_over_K0_max"], "p_stage_max_Pa": d["p_stage_max_Pa"],
            "p_inlet_max_Pa": d["p_inlet_max_Pa"], "T_comp_max_K": d["T_comp_max_K"],
            "T_comp_limit_K": d["T_comp_limit_K"]}


def gen_schedule(g, i, n_bp=None):
    n = n_bp or int(g.integers(1, 7))
    xs = sorted({round(U(g, 170, 240), 6) for _ in range(n)})
    return {"mode": "schedule", "schedule_id": f"SCH-SYN-{i}",
            "input": {"name": "nav:alt_km", "kind": "onboard_navigation_or_clock", "source": "navigation (" + SYN + ")"},
            "breakpoints": [[x, LU(g, -3, -0.5)] for x in xs],
            "label": "PARAMETRIC_SENSITIVITY / " + u13.SYNTHETIC, "basis": SYN, "status": u13.SCHEDULE_STATUS}


def py_control(d):
    if d["mode"] == "schedule":
        si = d["input"]
        return u13.SetpointSchedule(d["schedule_id"], u13.ScheduleInput(si["name"], si["kind"], si["source"]),
                                    tuple(tuple(unj(x) for x in b) for b in d["breakpoints"]), d["label"], d["basis"],
                                    d.get("status") or u13.SCHEDULE_STATUS)
    if d["mode"] == "fixed":
        return u13.FixedSetpoint(unj(d["setpoint_Pa"]), d["label"], d["basis"])
    return "BOGUS_CONTROL_OBJECT"


def gen_reservoir(g):
    mats = list(DB)
    return {"volume_m3": U(g, 5e-4, 1e-2), "wall_area_m2": U(g, 0.02, 0.3), "wall_material": pick(g, mats),
            "T_K": U(g, 250, 600), "anode_orifice_area_m2": LU(g, -7, -4), "anode_orifice_K": U(g, 0.2, 1),
            "leak_area_m2": LU(g, -9, -6), "upstream_collisions": int(g.integers(0, 201)),
            "upstream_material": pick(g, mats)}


def py_reservoir(d):
    return rmod.Reservoir(**d)


def gen_transient_args(g, entry, ref):
    """One P42 / P43 draw (v1 procedure; also the v3 refinement grid)."""
    D = design_records()
    rec = D[int(g.integers(len(D)))]
    args = {"filter": gen_filter_spec(g), "plant": {"design": f3_grid()[int(g.integers(len(f3_grid())))]},
            "plenum": gen_plenum_spec(g, -3.5, -1.5), "controller": gen_controller(g),
            "intake": intake_spec(rec), "r0": pick(g, [0.005, 0.01, 0.02, 0.05]), "window_s": 60.0}
    if ref:
        args.update({"rtol": pf.RTOL_REFERENCE, "method": pf.INTEGRATOR_REFERENCE})
    if entry == "plenum.transient_case":
        args["orbit_check"] = None if P(g, 0.5) else {"reasons": [r for r in (
            pf.R_SATURATED, pf.R_DEADHEAD, pf.R_STAGE_DOMAIN, pf.R_KN_FEED) if P(g, 0.3)]}
    return args


def gen_orbit_sim_args(g):
    """One P45 draw (v1 procedure; also the v3 refinement grid)."""
    D = design_records()
    des = D[int(g.integers(len(D)))]
    same = [r for r in pool() if r.candidate == des.candidate and r.scenario == des.scenario]
    st = same[int(g.integers(len(same)))]
    return {"filter": gen_filter_spec(g), "plant": {"design": f3_grid()[int(g.integers(len(f3_grid())))]},
            "plenum": gen_plenum_spec(g, -3.5, -1.5), "controller": gen_controller(g),
            "design": intake_spec(des), "state": intake_spec(st),
            "r0": pick(g, [0.005, 0.01, 0.02, 0.05]), "amplitude": U(g, 0.05, 0.2)}


def vectors_plenum(master: int) -> list:
    V = vectors_plenum_base(master)
    if v7_on():
        # transient_convergence_procedure_v7.stability_class: the class of every transient vector, both implementations
        V += [{"id": v["id"] + "#class", "entry": "plenum.stability_class", "args": v["args"]}
              for v in list(V) if v["entry"] in TRANSIENT_ENTRIES]
    return V


def vectors_plenum_base(master: int) -> list:
    V = []

    def add(vid, entry, args):
        V.append({"id": vid, "entry": entry, "args": args})
    P_ = pool()
    # P30
    g = rng(master, 30)
    for i in range(300):
        k = i % 3
        if k == 0:
            add(f"P30-{i:03d}", "plenum.orbital_period", {"alt_km": U(g, 150, 250)})
        else:
            add(f"P30-{i:03d}", "plenum.cbar" if k == 1 else "plenum.kt_over_m",
                {"species": pick(g, ["O", "N2", "O2", "Xe"]), "T_K": U(g, 150, 1500)})
    # P31
    g = rng(master, 31)
    for i in range(200):
        if i % 4 == 3:
            add(f"P31-{i:03d}", "plenum.f1_candidate_id", {"area_m2": pick(g, F1_AREAS) if P(g, 0.5) else U(g, 0.1, 2),
                                                           "L_over_d": pick(g, [1.0, 3.0, 5.0]) if P(g, 0.5)
                                                           else U(g, 1, 10), "phi": U(g, 0.1, 1)})
        else:
            add(f"P31-{i:03d}", "plenum.intake", {"intake": intake_spec(P_[int(g.integers(len(P_)))])})
    # P32
    for name, spec in (("none", {"factory": "none"}), ("t0.9", {"factory": "parametric", "tau": 0.9}),
                       ("t0.7", {"factory": "parametric", "tau": 0.7}), ("t0.5", {"factory": "parametric", "tau": 0.5}),
                       ("placeholder", {"factory": "placeholder"})):
        add(f"P32-G-{name}", "plenum.filter_case", {"filter": spec})
    add("P32-G-filter_cases", "plenum.filter_cases", {"taus": [0.9, 0.7, 0.5]})
    g = rng(master, 32)
    for i in range(10):
        if i < 7:
            add(f"P32-R-{i}", "plenum.filter_case", {"filter": gen_filter_spec(g) if P(g, 0.3) else
                                                     {"factory": "parametric", "tau": U(g, 0.05, 1)},
                                                     "a": [[s, U(g, 0, 1)] for s in SPECIES]})
        else:
            add(f"P32-R-{i}", "plenum.filter_cases", {"taus": [U(g, 0.05, 1) for _ in range(int(g.integers(1, 4)))]})
    # P33
    g = rng(master, 33)
    S3 = ["O", "N2", "O2"]
    for i in range(100):
        r = g.random()
        st = {"factory": "tbd", "species": S3, "stage_id": f"F4-SYN-{i}", "concept_id": "FC-SYN"}
        if r < 0.7:
            tf, tb, al = U(g, 0.05, 1), U(g, 0.05, 1), U(g, 0.05, 1)
            ov = [["face_area_m2", LU(g, -3, 0)], ["areal_mass_kg_m2", U(g, 0.1, 5)]]
            for s in S3:
                ov += [[f"tau_f.{s}", tf], [f"tau_b.{s}", tb], [f"alpha_conductance.{s}", al], [f"capture_f.{s}", 0.0],
                       [f"capture_b.{s}", 0.0], [f"conversion_f.{s}", 0.0], [f"conversion_b.{s}", 0.0]]
            cas = {"case_id": f"SC-F4-SYN-{i}", "label": "PARAMETRIC_SENSITIVITY (synthetic)", "overrides": ov,
                   "rationale": SYN, "regime_assumption": "free_molecular", "temperature_override_K": None}
        elif r < 0.8:
            st, cas = {"factory": "none", "species": S3}, None
        elif r < 0.9:
            cas = full_case(S3, cap=U(g, 0.01, 0.2))
        else:
            cas = gen_case(g, st)
        add(f"P33-{i:03d}", "plenum.filter_case", {"filter": {"factory": "stage", "case_id": f"F4-FIL-SYN-{i}",
                                                              "stage": st, "case": cas, "note": SYN}})
    add("P33-E-tbd-no-case", "plenum.filter_case", {"filter": {"factory": "stage", "case_id": "E", "case": None,
                                                               "stage": {"factory": "tbd", "species": S3,
                                                                         "stage_id": "E", "concept_id": "E"}}})
    add("P33-E-capture", "plenum.filter_case", {"filter": {"factory": "stage", "case_id": "E",
                                                           "case": full_case(S3, cap=0.1),
                                                           "stage": {"factory": "tbd", "species": S3,
                                                                     "stage_id": "E", "concept_id": "E"}}})
    # P34
    g = rng(master, 34)
    for i in range(100):
        add(f"P34-{i:03d}", "plenum.plenum", {"plenum": gen_plenum_spec(g)})
    base = {"volume_m3": 0.002, "gamma_wall": 0.01, "wall_case": "E", "leak_area_m2": 5e-8}
    for name, kw in (("V0", {"volume_m3": 0.0}), ("Vneg", {"volume_m3": -1.0}), ("Vnan", {"volume_m3": "NaN"}),
                     ("g1.5", {"gamma_wall": 1.5}), ("gneg", {"gamma_wall": -0.1}), ("leakneg", {"leak_area_m2": -1.0}),
                     ("T0", {"T_K": 0.0}), ("Vtrue", {"volume_m3": True})):
        add(f"P34-E-{name}", "plenum.plenum", {"plenum": {**base, **kw}})
    # P35
    g = rng(master, 35)
    for i in range(200):
        add(f"P35-{i:03d}", "plenum.plant", {"plant": {"design": f3_grid()[int(g.integers(len(f3_grid())))]},
                                             "p_in": [[s, LU(g, -4, -1.5)] for s in SPECIES],
                                             "Q": [[s, LU(g, -5, -1)] for s in SPECIES]})
    # P36
    g = rng(master, 36)
    for i in range(400):
        ch = gen_chain(g)
        if i % 2 == 0:
            add(f"P36-{i:03d}", "plenum.chain", {"chain": ch, "density_factor": U(g, 0.5, 1.5) if P(g, 0.3) else 1.0})
        else:
            add(f"P36-{i:03d}", "plenum.solve_pressures", {"chain": ch, "a_eq": LU(g, -9, -3)})
    # P37
    g = rng(master, 37)
    for i in range(500):
        ch = gen_chain(g)
        tgt = LU(g, -3.5, -0.7)
        if i < 400:
            add(f"P37-{i:03d}", "plenum.steady", {"chain": ch, "target": tgt,
                                                  "density_factor": U(g, 0.5, 1.5) if P(g, 0.3) else 1.0,
                                                  "feed_factor": U(g, 0.5, 1.5) if P(g, 0.3) else 1.0})
        else:
            add(f"P37-{i:03d}", "plenum.evaluate", {"chain": ch, "target": tgt,
                                                    "mode": pf.MODE_STRICT if i >= 480 else pf.MODE_PARAMETRIC})
    infeas = [r for r in P_ if r.f1_status != "FEASIBLE_AT_STATE"]
    zero_design = {**f3_grid()[0], "id": "ZERO-STAGE", "N_turbo": 0, "N_drag": 0}
    for i in range(40):
        ch = gen_chain(g)
        k = i // 10
        if k == 0:
            tgt = U(g, 0.1, 1.0) if i % 10 else 0.1000000001
            add(f"P37-E-above-{i}", "plenum.steady", {"chain": ch, "target": tgt})
        elif k == 1:
            co = py_chain(ch)
            pl = co.plenum
            leak = {s: pl.leak_m3_s(s) for s in SPECIES}
            fcd = {s: pl.feed_c(s) for s in SPECIES}
            p_dead = float(sum(pf.solve_pressures(co.node_coefficients(), 0.0, pl.k_rec_m3_s(), leak, fcd)[0].values()))
            tgt = min(p_dead * (1.0 if i % 2 else U(g, 1.0, 1.5)), 0.1)
            add(f"P37-E-deadhead-{i}", "plenum.steady", {"chain": ch, "target": tgt})
        elif k == 2:
            ch = gen_chain(g, infeas[int(g.integers(len(infeas)))])
            add(f"P37-E-f1-{i}", "plenum.steady", {"chain": ch, "target": LU(g, -3.5, -1.5)})
        else:
            ch["plant"] = {"design": zero_design}
            add(f"P37-E-zero-stage-{i}", "plenum.steady", {"chain": ch, "target": LU(g, -3.5, -1.5)})
    # P38
    g = rng(master, 38)
    for i in range(12):
        recs = [P_[int(k)] for k in g.integers(len(P_), size=20)]
        ff = gen_filter_spec(g)
        add(f"P38-{i:02d}", "plenum.sweep", {
            "intakes": [intake_spec(r) for r in recs], "filter": ff,
            "plant": {"design": f3_grid()[int(g.integers(len(f3_grid())))]}, "plenum": gen_plenum_spec(g),
            "targets": sorted(LU(g, -3.5, -0.7) for _ in range(8)),
            "f1_ok": [r.f1_status == "FEASIBLE_AT_STATE" for r in recs] if P(g, 0.5) else None})
    # P39
    g = rng(master, 39)
    for i in range(80):
        add(f"P39-{i:03d}", "plenum.area_for_pressure", {"chain": gen_chain(g), "target": LU(g, -3.5, -0.7)})
    ch = gen_chain(g)
    for name, tgt in (("t0", 0.0), ("tneg", -1.0), ("tnan", "NaN")):
        add(f"P39-E-{name}", "plenum.area_for_pressure", {"chain": ch, "target": tgt})
    lo, hi = pf.A_EQ_BRACKET_M2
    for name, a_eq, res in (("lo", lo, 1e-12), ("hi", hi, 1e-12), ("resid2e-6", 1e-5, 2e-6), ("residnan", 1e-5, "NaN")):
        add(f"P39-E-bis-{name}", "plenum.bisection_failed", {"a_eq": a_eq, "resid": res})
    for i in range(10):
        add(f"P39-B-{i}", "plenum.bisection_failed", {"a_eq": LU(g, -10, 0), "resid": LU(g, -12, -4)})
    for i in range(10):
        add(f"P39-L-{i}", "plenum.lambda_upper", {"p3": [[s, LU(g, -4, -1) if P(g, 0.9) else 0.0] for s in SPECIES],
                                                  "T_K": U(g, 250, 450)})
    # P40
    g = rng(master, 40)
    for i in range(200):
        if i < 150:
            add(f"P40-M-{i:03d}", "plenum.segment_metrics", {"segment": synth_segment(g),
                                                             "p_prev_final": LU(g, -3, -1)})
        elif i < 180:
            sg = synth_segment(g)
            add(f"P40-S-{i:03d}", "plenum.settling", {"t": sg["t"], "y": sg["p"], "final": sg["setpoint_Pa"],
                                                      "band": pick(g, [pf.SETTLE_BAND, 0.05, 0.001])})
        else:
            add(f"P40-D-{i:03d}", "plenum.domain_reasons", {"segments": [synth_segment(g)
                                                                         for _ in range(int(g.integers(1, 5)))]})
    # P41
    g = rng(master, 41)
    for i in range(20):
        ch = gen_chain(g)
        if i < 10:
            add(f"P41-{i:02d}", "plenum.ripple", {"chain": ch, "a_eq": LU(g, -7, -4), "f_hz": U(g, 1, 2000)})
        else:
            add(f"P41-{i:02d}", "plenum.inlet_tau", {"chain": ch})
    # P42 / P43
    D = design_records()
    for e_idx, entry in ((42, "plenum.transient_run"), (43, "plenum.transient_case")):
        if v7_on():
            # transient_convergence_procedure_v7.stratified_draws.held_out
            sp = v7_spec()["stratified_draws"]
            vs, _ = stratified_draw(master, e_idx, entry, sp["held_out"][f"P{e_idx}"], "P",
                                    sp["max_candidates_per_level"])
            for x in vs:
                add(x["id"], x["entry"], x["args"])
        else:
            g = rng(master, e_idx)
            for i in range(16):
                ref = i >= 12
                add(f"P{e_idx}-{'REF' if ref else 'PROD'}-{i:02d}", entry, gen_transient_args(g, entry, ref))
        args = {"filter": {"factory": "none"}, "plant": {"design": f3_grid()[0]},
                "plenum": {"volume_m3": 0.002, "gamma_wall": 0.0, "wall_case": "E", "leak_area_m2": 5e-8},
                "controller": {"Kp": 2.0, "Ti_s": 1.0, "f_valve_hz": 1.0, "authority": 2.0},
                "intake": intake_spec(D[0]), "r0": 0.0999, "window_s": 60.0}
        if entry == "plenum.transient_case":
            args["orbit_check"] = None
        add(f"P{e_idx}-E-deadhead", entry, args)
    g = rng(master, 142)
    for i in range(2):
        add(f"P42-ES-{i}", "plenum.event_sequence", {"intake": intake_spec(D[int(g.integers(len(D)))]),
                                                     "r0": pick(g, [0.005, 0.01, 0.02, 0.05]), "window_s": 60.0})
    # P44
    g = rng(master, 44)
    for i in range(10):
        des = D[int(g.integers(len(D)))]
        same = [r for r in P_ if r.candidate == des.candidate and r.scenario == des.scenario]
        sts = [same[int(k)] for k in g.choice(len(same), size=int(g.integers(3, 7)), replace=False)]
        fspec, plant = gen_filter_spec(g), {"design": f3_grid()[int(g.integers(len(f3_grid())))]}
        plen = gen_plenum_spec(g, -3.5, -1.5)
        r0 = pick(g, [0.005, 0.01, 0.02, 0.05])
        auth = U(g, 1.5, 4)
        co = pf.Chain(des, py_filter_case(fspec), py_plant(plant), py_plenum_obj(plen))
        pl = co.plenum
        a_d = pf.area_for_pressure(co.node_coefficients(), r0, pl.k_rec_m3_s(), {s: pl.leak_m3_s(s) for s in SPECIES},
                                   {s: pl.feed_c(s) for s in SPECIES})[0]
        add(f"P44-{i:02d}", "plenum.orbit_qs", {"filter": fspec, "plant": plant, "plenum": plen,
                                                "states": [intake_spec(s) for s in sts], "r0": r0,
                                                "amplitude": U(g, 0.05, 0.3), "a_max_m2": auth * float(a_d),
                                                "n_phase": int(g.integers(8, 33))})
    # P45
    if v7_on():
        sp = v7_spec()["stratified_draws"]
        vs, _ = stratified_draw(master, 45, "plenum.orbit_sim", sp["held_out"]["P45"], "P",
                                sp["max_candidates_per_level"])
        for x in vs:
            add(x["id"], x["entry"], x["args"])
    else:
        g = rng(master, 45)
        for i in range(4):
            add(f"P45-{i}", "plenum.orbit_sim", gen_orbit_sim_args(g))
    # P46
    add("P46-G-strict_blockers", "plenum.strict_blockers", {})
    g = rng(master, 46)
    for i in range(50):
        if i < 25:
            add(f"P46-S-{i:02d}", "plenum.status_from_reasons", {"reasons": [r for r in pf.REASONS if P(g, 0.15)]})
        else:
            add(f"P46-B-{i:02d}", "plenum.reasons_from_bits", {"bits": int(g.integers(0, 1 << len(pf.REASONS)))})
    # P47
    g = rng(master, 47)
    req = [s.id for s in isy.required_states()]
    for i in range(26):
        des = D[int(g.integers(len(D)))]
        same = [r for r in P_ if r.candidate == des.candidate and r.scenario == des.scenario]
        its = [same[int(k)] for k in g.choice(len(same), size=int(g.integers(3, 9)), replace=False)]
        base = {"filter": gen_filter_spec(g), "plant": {"design": f3_grid()[int(g.integers(len(f3_grid())))]},
                "plenum": gen_plenum_spec(g), "intakes": [intake_spec(r) for r in its], "required": req}
        cst = None
        if P(g, 0.4):
            cst = [[r.state, [["nav:alt_km", isy.state_alt_km(r.state)]]] for r in its]
        base["controller_states"] = cst
        sch = gen_schedule(g, i)
        fx = {"mode": "fixed", "setpoint_Pa": LU(g, -3, -0.5), "label": "PARAMETRIC_SENSITIVITY", "basis": SYN}
        if i < 20:
            add(f"P47-S-{i:02d}", "plenum.scheduled", {**base, "control": sch if P(g, 0.6) else fx})
        else:
            add(f"P47-C-{i:02d}", "plenum.compare_modes", {**base, "schedule": sch, "fixed": fx})
    add("P47-E-control", "plenum.scheduled", {**base, "control": {"mode": "bogus"}})
    add("P47-E-missing-state", "plenum.scheduled", {**base, "control": fx, "controller_states":
                                                    [[r["state"], [["nav:alt_km", r["alt_km"]]]]
                                                     for r in base["intakes"][1:]]})
    add("P47-E-swapped", "plenum.compare_modes", {**base, "schedule": fx, "fixed": sch})
    # P48
    g = rng(master, 48)
    for i in range(50):
        if i < 25:
            objs = list(pf.OBJECTIVES[:int(g.integers(2, len(pf.OBJECTIVES) + 1))])
            rows = []
            for j in range(int(g.integers(3, 15))):
                o = {k: U(g, 0, 10) for k in pf.OBJECTIVES}
                if P(g, 0.1):
                    o[pick(g, objs)] = pick(g, [None, "NaN", "+inf"])
                if rows and P(g, 0.15):
                    o = dict(rows[int(g.integers(len(rows)))]["objectives"])
                rows.append({"id": f"C{j:02d}", "status": pf.ST_FEASIBLE if P(g, 0.8) else pf.ST_INFEASIBLE,
                             "objectives": o})
            add(f"P48-P-{i:02d}", "plenum.pareto_ids", {"rows": rows, "objectives": objs})
        else:
            add(f"P48-C-{i:02d}", "plenum.controller_state", {"intake": intake_spec(P_[int(g.integers(len(P_)))])})
    # P49
    g = rng(master, 49)
    for i in range(100):
        add(f"P49-C-{i:03d}", "reservoir.conductance", {"res": gen_reservoir(g), "species": pick(g, ["O", "N2", "O2"]),
                                                        "area": LU(g, -8, -2), "K": U(g, 0.2, 1)})
    for i in range(300):
        add(f"P49-S-{i:03d}", "reservoir.steady", {"res": gen_reservoir(g), "mdot": gen_mdot(g, -8, -5.5)})
    add("P49-E-missing-N2", "reservoir.steady", {"res": gen_reservoir(g), "mdot": [["O", 1e-7], ["O2", 1e-8]]})
    for i in range(100):
        add(f"P49-O-{i:03d}", "reservoir.size_orifice", {"res": gen_reservoir(g), "mdot": gen_mdot(g, -8, -5.5),
                                                         "p_target": LU(g, -3, 0)})
    for i in range(60):
        add(f"P49-T-{i:02d}", "reservoir.startup", {"res": gen_reservoir(g), "mdot": gen_mdot(g, -8, -5.5),
                                                    "p_ignite": LU(g, -3, 0), "spinup_s": U(g, 0, 120),
                                                    "t_end_s": U(g, 50, 600), "dt_s": U(g, 0.01, 0.2)})
    # P50
    add("P50-G-plenum", "plenum.constants", {})
    add("P50-G-upstream", "upstream.constants", {})
    vectors_upstream(master, add)
    return V


def vectors_upstream(master, add):
    g = rng(master, 10)
    for i in range(60):
        p = LU(g, -3, 0.5) if P(g, 0.8) else pick(g, [0.1, 0.0, -1.0, "NaN", "+inf", "0.05"])
        add(f"P10-{i:02d}", "upstream.pressure_domain" if i % 2 == 0 else "upstream.classify", {"p": p})
    g = rng(master, 11)
    for i in range(60):
        if i % 2 == 0:
            sts = [pick(g, list(u13.VALUE_STATUSES) + ["BOGUS"], p=[0.19] * 5 + [0.05])
                   for _ in range(int(g.integers(0, 5)))]
            add(f"P11-{i:02d}", "upstream.combine", {"statuses": sts})
        else:
            add(f"P11-{i:02d}", "upstream.constraint", {"ok": pick(g, [True, False, None]),
                                                        "value_status": pick(g, list(u13.VALUE_STATUSES))})
    g = rng(master, 12)
    for i in range(40):
        sch = gen_schedule(g, i)
        add(f"P12-T-{i:02d}", "upstream.control", {"control": sch})
        xs = [b[0] for b in sch["breakpoints"]]
        for j in range(10):
            r = g.random()
            if r < 0.5:
                st = [["nav:alt_km", U(g, xs[0], xs[-1]) if len(xs) > 1 else xs[0]]]
            elif r < 0.65:
                st = [["nav:alt_km", U(g, 160, 250)]]
            elif r < 0.7:
                st = [["nav:alt_km", int(round(U(g, 170, 240)))]]
            elif r < 0.75:
                st = [["other", 200.0]]
            elif r < 0.8:
                st = [["nav:alt_km", "NaN"]]
            elif r < 0.85:
                st = [["nav:alt_km", "two hundred"]]
            elif r < 0.9:
                st = [["nav:alt_km", 200.0], ["rho_kg_m3", 1e-10]]
            else:
                st = [["nav:alt_km", xs[int(g.integers(len(xs)))]]]
            add(f"P12-S-{i:02d}-{j}", "upstream.setpoint", {"control": sch, "state": st})
    g = rng(master, 112)
    nav = {"name": "nav:alt_km", "kind": "onboard_navigation_or_clock", "source": "nav"}
    est = {"name": "est:rho_kg_m3", "kind": "onboard_estimate", "source": "estimator"}
    for i, (fs_, ins, mp) in enumerate((
            ([["alt_km", 200.0]], [nav], [["nav:alt_km", "alt_km"]]),
            ([["alt_km", 200.0], ["rho_kg_m3", 1e-10]], [nav, est], [["nav:alt_km", "alt_km"],
                                                                     ["est:rho_kg_m3", "rho_kg_m3"]]),
            ([["alt_km", 200.0]], [nav], []),
            ([["rho_kg_m3", 1e-10]], [nav], [["nav:alt_km", "rho_kg_m3"]]),
            ([["x", 1.0]], [nav], [["nav:alt_km", "alt_km"]]))):
        add(f"P12-V-{i}", "upstream.controller_view", {"full_state": fs_, "inputs": ins, "mapping": mp})
    g = rng(master, 13)
    for i in range(30):
        if i < 24:
            fx = {"mode": "fixed", "setpoint_Pa": LU(g, -3, 0), "label": pick(g, ["PARAMETRIC_SENSITIVITY",
                                                                                 "REFERENCE"]), "basis": SYN}
        else:
            fx = {"mode": "fixed", "setpoint_Pa": pick(g, [0.0, -0.01, "NaN", 0.01]), "label": "PARAMETRIC_SENSITIVITY",
                  "basis": pick(g, [" ", SYN])}
        if i % 2:
            add(f"P13-{i:02d}", "upstream.control", {"control": fx})
        else:
            add(f"P13-{i:02d}", "upstream.setpoint", {"control": fx, "state": [["nav:alt_km", 200.0]] if P(g, 0.8)
                                                      else [["f107", 150.0]]})
    g = rng(master, 14)
    for i in range(40):
        kind = pick(g, list(u13.INPUT_KINDS) + ["telepathy"], p=[0.22] * 4 + [0.12])
        name = pick(g, ["nav:alt_km", "est:rho_kg_m3", "rho_kg_m3", "clock:t", " ", "meas:p_plenum"])
        add(f"P14-{i:02d}", "upstream.schedule_input", {"input": {"name": name, "kind": kind,
                                                                  "source": SYN if P(g, 0.9) else " "}})
    g = rng(master, 15)
    Q = ["pressure", "mass_flow", "composition", "ripple"]
    for i in range(33):
        st = pick(g, [s for s in u13.VALUE_STATUSES if s != "TBD"] + ["TBD"])
        add(f"P15-{i:02d}", "upstream.h1_tolerance", {"quantity": pick(g, Q), "value_frac": None if st == "TBD" else
                                                      U(g, 0.001, 0.2), "status": st, "source": SYN})
    for i, kw in enumerate(({"quantity": "voltage"}, {"status": "BOGUS"}, {"status": "TBD", "value_frac": 0.01},
                            {"value_frac": 0.0}, {"value_frac": -0.01}, {"value_frac": "NaN"}, {"value_frac": None},
                            {"source": " "}, {"quantity": "Pressure"}, {"status": "evidence"},
                            {"value_frac": "+inf"}, {"status": "TBD", "value_frac": None, "source": " "},
                            {"quantity": ""}, {"status": ""}, {"value_frac": True})):
        add(f"P15-E-{i:02d}", "upstream.h1_tolerance", {**{"quantity": "pressure", "value_frac": 0.02,
                                                           "status": "EVIDENCE", "source": SYN}, **kw})
    g = rng(master, 16)
    for i in range(40):
        r = g.random()
        h1 = None if r < 0.3 else ({"tbd": True, "quantity": pick(g, Q)} if r < 0.5 else
                                   {"quantity": pick(g, Q), "value_frac": U(g, 0.001, 0.1),
                                    "status": pick(g, ["EVIDENCE", "PARAMETRIC_SENSITIVITY"]), "source": SYN})
        f4 = U(g, 0.001, 0.1) if P(g, 0.9) else pick(g, [0.0, "NaN", -0.01])
        add(f"P16-{i:02d}", "upstream.governing_band", {"quantity": pick(g, Q), "f4": f4, "h1": h1})
    g = rng(master, 17)
    for i in range(40):
        m = LU(g, -7.5, -5.5) if P(g, 0.85) else pick(g, ["NaN", "+inf", 3.8e-7, 3.2e-6, "x"])
        add(f"P17-{i:02d}", "upstream.coverage", {"mdot": m})
    for i, gate in enumerate((None, 0.38, "1.3 mg/s")):
        add(f"P18-{i}", "upstream.fixed_gate", {"gate": gate})
    for i, st in enumerate((None, "VALIDATED", "SYNTHETIC", "PENDING")):
        add(f"P19-{i}", "upstream.flight_requirement", {"status": st})
    add("P20-flow_gap", "upstream.flow_gap", {})
    g = rng(master, 21)
    bases = [u13.PERFORMANCE_DERIVED_BASIS] + list(u13.FORBIDDEN_FEED_REQUIREMENT_BASES) + ["OWNER_GUESS"]
    for i in range(20):
        b = bases[i] if i < len(bases) else pick(g, bases)
        val = None if i < len(bases) else pick(g, [None, 0.38, 0.38000000001, 1.3, "NaN", U(g, 0.1, 3)])
        add(f"P21-{i:02d}", "upstream.lowering", {"basis": b, "value_mgps": val})
    g = rng(master, 22)
    req = [s.id for s in isy.required_states()]
    for i in range(40):
        if i == 0:
            add("P22-E-empty", "upstream.state_coverage", {"used": req[:3], "required": []})
            continue
        r = g.random()
        used = list(req) if r < 0.3 else [req[int(k)] for k in g.choice(len(req), size=int(g.integers(1, len(req))),
                                                                        replace=False)]
        if P(g, 0.2):
            used = used + used[:3] + ["h200_f150"]
        add(f"P22-{i:02d}", "upstream.state_coverage", {"used": used, "required": req})
    g = rng(master, 23)
    for i in range(30):
        mem = [f"M{j}" for j in range(int(g.integers(1, 6)))]
        s = {"set_id": "RPS-SYN", "version": "v0", "members": mem, "objectives": ["P_el", "m"],
             "label": "ROBUST_PARETO_SET (synthetic)", "provenance": SYN, "regeneration_triggers": None,
             "regenerated_after": [t for t in u13.REGENERATION_TRIGGERS if P(g, 0.3)]}
        k = i % 6
        if i >= 24:
            s = {**s, **pick(g, [{"set_id": " "}, {"members": mem + mem[:1]}, {"label": "WINNER set"},
                                 {"provenance": ""}, {"version": " "}])}
        op = ["to_dict", "representative", "engineering_reference", "engineering_reference", "pending",
              "engineering_reference"][k]
        member = mem[0] if k == 2 else ("NOT-A-MEMBER" if k == 3 else mem[-1])
        purpose = " " if k == 5 and P(g, 0.5) else "synthetic downstream study"
        add(f"P23-{i:02d}", "upstream.robust_set", {"set": s, "op": op, "member": member, "purpose": purpose})
    add("P24-0", "upstream.candidate", {"obj": {"kind": "mapping", "evidence_status": "CANDIDATE_NOT_ADMITTED"}})
    add("P24-1", "upstream.candidate", {"obj": {"kind": "object", "evidence_status": None,
                                                "valid_design_evidence": False}})
    add("P25-0", "upstream.verify_decisions", {})
    add("P25-1", "upstream.cite", {"keys": ["A9.13"]})
    add("P25-2", "upstream.cite", {"keys": list(u13.DECISIONS)})
    add("P25-3", "upstream.dense", {"used": req, "required": req, "s615": u13.C_MET})


def py_constants_plenum():
    return {"REASONS": list(pf.REASONS), "OOD_REASONS": list(pf.OOD_REASONS),
            "MODEL_ERROR_REASONS": list(pf.MODEL_ERROR_REASONS), "P_DOMAIN_PA": pf.P_DOMAIN_PA, "KN_MIN": pf.KN_MIN,
            "K_TOL": pf.K_TOL, "SETTLE_BAND": pf.SETTLE_BAND, "RTOL": pf.RTOL, "RTOL_REFERENCE": pf.RTOL_REFERENCE,
            "ATOL_SCALED": pf.ATOL_SCALED, "MASS_TOL": pf.MASS_TOL, "BISECT_ITERS": pf.BISECT_ITERS,
            "A_EQ_BRACKET_M2": list(pf.A_EQ_BRACKET_M2), "BISECT_RTOL": pf.BISECT_RTOL,
            "INTEGRATOR_METHOD": pf.INTEGRATOR_METHOD, "INTEGRATOR_REFERENCE": pf.INTEGRATOR_REFERENCE,
            "T_CHAIN_K": pf.T_CHAIN_K, "RES_DEFAULT_LEAK_AREA_M2": pf.RES_DEFAULTS["leak_area_m2"],
            "WINDOW_S": pf.WINDOW_S, "SETPOINT_STEP": pf.SETPOINT_STEP, "FEED_PATH_STEP": pf.FEED_PATH_STEP,
            "SUPPLY_STEP": pf.SUPPLY_STEP, "OBJECTIVES": list(pf.OBJECTIVES),
            "REPORTED_NOT_OPTIMISED": list(pf.REPORTED_NOT_OPTIMISED), "TRANSIENT_FRAMEWORK": pf.TRANSIENT_FRAMEWORK,
            "SS_MAX_ITER": rmod.Reservoir.SS_MAX_ITER, "SS_RTOL": rmod.Reservoir.SS_RTOL,
            "ORIFICE_BRACKET_M2": list(rmod.ORIFICE_BRACKET_M2), "ORIFICE_BISECTION_STEPS": rmod.ORIFICE_BISECTION_STEPS,
            "ORIFICE_P_RTOL": rmod.ORIFICE_P_RTOL}


def py_constants_upstream():
    return {"DECISIONS": [[k, d["md"], d["json"], d["json_sha256"], list(d["ids"])] for k, d in u13.DECISIONS.items()],
            "RFP_CLAUSES": [[k, v] for k, v in u13.RFP_CLAUSES.items()], "VALUE_STATUSES": list(u13.VALUE_STATUSES),
            "P_FREE_MOLECULAR_LIMIT_PA": u13.P_FREE_MOLECULAR_LIMIT_PA, "TRANSITIONAL_MODEL": u13.TRANSITIONAL_MODEL,
            "DESIGN_DIRECTIONS": list(u13.DESIGN_DIRECTIONS), "INPUT_KINDS": list(u13.INPUT_KINDS),
            "ORACLE_KEYS": list(u13.ORACLE_KEYS), "F4_TRANSIENT_FRAMEWORK": u13.F4_TRANSIENT_FRAMEWORK,
            "CHARACTERIZATION_COVERAGE_MGPS": list(u13.CHARACTERIZATION_COVERAGE_MGPS),
            "FEED_STATE_FIELDS": list(u13.FEED_STATE_FIELDS), "FLOW_GAP_ORDER": list(u13.FLOW_GAP_ORDER),
            "FORBIDDEN_FEED_REQUIREMENT_BASES": list(u13.FORBIDDEN_FEED_REQUIREMENT_BASES),
            "REGENERATION_TRIGGERS": list(u13.REGENERATION_TRIGGERS)}


_ORIG_SEG = pf.TransientRun._segment_record


def _tap_segment_record(self, ev, t0, sol):
    """Harness instrumentation (outputs unchanged): records u_cmd at the segment end and the samples for the
    registered threshold-proximity rule (saturated_end, settling index)."""
    rec = _ORIG_SEG(self, ev, t0, sol)
    ucmd = self._u_cmd((rec["p"][-1] - ev.setpoint_Pa) / ev.setpoint_Pa, float(sol.y[4, -1]))
    TAP.setdefault(_CUR["vid"], []).append({"ucmd_end": float(ucmd), "kind": ev.kind, "setpoint": ev.setpoint_Pa,
                                            "p": [float(x) for x in rec["p"]], "mdot": [float(x) for x in rec["mdot"]],
                                            "p_max": float(np.max(rec["p"])),
                                            # contract v3 primitive image: the run's own states at the samples
                                            "tr": self, "ev": ev, "t0": t0, "t": np.array(sol.t, copy=True),
                                            "y": np.array(sol.y, copy=True),
                                            "diag": {n: rec[n] for n in ("K_min", "K_over_K0_max", "p_stage_max_Pa",
                                                                         "p_inlet_max_Pa", "P_el_max_W",
                                                                         "T_comp_max_K")}})
    return rec


pf.TransientRun._segment_record = _tap_segment_record


def scalar(x):
    return float(np.asarray(x))


def py_plenum(v):
    a = v["args"]
    e = v["entry"]
    _CUR["vid"] = v["id"]
    TAP.pop(v["id"], None)
    if e == "plenum.orbital_period":
        return py_call(lambda: pf.orbital_period_s(a["alt_km"]))
    if e == "plenum.cbar":
        return py_call(lambda: pf.cbar(a["species"], a["T_K"]))
    if e == "plenum.kt_over_m":
        return py_call(lambda: pf.kT_over_m(a["species"], a["T_K"]))
    if e == "plenum.f1_candidate_id":
        return py_call(lambda: pf.f1_candidate_id(a["area_m2"], a["L_over_d"], a["phi"]))
    if e == "plenum.status_from_reasons":
        return py_call(lambda: pf.status_from_reasons(a["reasons"]))
    if e == "plenum.reasons_from_bits":
        return py_call(lambda: pf.reasons_from_bits(a["bits"]))
    if e == "plenum.intake":
        def f():
            it = py_intake_state(a["intake"])
            return {"q_fwd": it.q_fwd(), "e_f1": it.e_f1(), "escape_probability": it.escape_probability()}
        return py_call(f)
    if e == "plenum.filter_case":
        def f():
            fc = py_filter_case(a["filter"])
            out = {"case": fc_dict(fc)}
            if "a" in a:
                D, E = fc.coefficients({k: x for k, x in a["a"]})
                out.update({"D": D, "E": E})
            return out
        return py_call(f)
    if e == "plenum.filter_cases":
        return py_call(lambda: [fc_dict(c) for c in pf.filter_cases(tuple(a["taus"]))])
    if e == "plenum.plant":
        def f():
            p = py_plant(a["plant"])
            try:
                cas = p.cascade({k: x for k, x in a["p_in"]}, {k: x for k, x in a["Q"]})
            except Exception as exc:  # noqa: BLE001
                cas = {"__error__": type(exc).__name__}
            return {"design_id": p.design_id, "stages": p.stages(),
                    "characteristic": {s: list(x) for s, x in p.characteristic().items()},
                    "leak_m3_s": p.leak_m3_s, "shaft_hz": p.shaft_hz, "cascade": cas}
        return py_call(f)
    if e == "plenum.plenum":
        def f():
            p = py_plenum_obj(a["plenum"])
            return {"wall_area_m2": p.wall_area_m2, "k_rec_m3_s": p.k_rec_m3_s(),
                    "leak_m3_s": {s: p.leak_m3_s(s) for s in SPECIES}, "feed_c": {s: p.feed_c(s) for s in SPECIES},
                    "reservoir": dataclasses.asdict(p.reservoir(1e-6))}
        return py_call(f)
    if e == "plenum.chain":
        return py_call(lambda: py_chain(a["chain"]).node_coefficients(a["density_factor"]))
    if e == "plenum.solve_pressures":
        def f():
            ch = py_chain(a["chain"])
            pl = ch.plenum
            p3, p2 = pf.solve_pressures(ch.node_coefficients(), a["a_eq"], pl.k_rec_m3_s(),
                                        {s: pl.leak_m3_s(s) for s in SPECIES}, {s: pl.feed_c(s) for s in SPECIES})
            return {"p3": {s: scalar(x) for s, x in p3.items()}, "p2": {s: scalar(x) for s, x in p2.items()}}
        return py_call(f)
    if e == "plenum.area_for_pressure":
        def f():
            ch = py_chain(a["chain"])
            pl = ch.plenum
            aa, pd, rr, ok = pf.area_for_pressure(ch.node_coefficients(), unj(a["target"]), pl.k_rec_m3_s(),
                                                  {s: pl.leak_m3_s(s) for s in SPECIES},
                                                  {s: pl.feed_c(s) for s in SPECIES})
            return {"a_eq": scalar(aa), "p_dead": scalar(pd), "resid": scalar(rr), "ok": bool(ok),
                    "bisection_failed": bool(pf.bisection_failed(aa, rr))}
        return py_call(f)
    if e == "plenum.bisection_failed":
        return py_call(lambda: bool(pf.bisection_failed(unj(a["a_eq"]), unj(a["resid"]))))
    if e == "plenum.lambda_upper":
        return py_call(lambda: pf.lambda_upper_m({k: x for k, x in a["p3"]}, a["T_K"]))
    if e in ("plenum.steady", "plenum.evaluate"):
        def f():
            ch = py_chain(a["chain"])
            df = a.get("density_factor", 1.0)
            try:
                FLOOR[v["id"]] = forward_source_kgps(ch, df)
            except Exception:  # noqa: BLE001 - the refusal itself is compared
                FLOOR[v["id"]] = 0.0
            if e == "plenum.steady":
                return pf.steady_operating_point(ch, a["target"], df, a.get("feed_factor", 1.0))
            return pf.evaluate(ch, a["target"], a["mode"])
        return py_call(f)
    if e == "plenum.sweep":
        def f():
            its = [py_intake_state(x) for x in a["intakes"]]
            fc = py_filter_case(a["filter"])
            side = pf.intake_side(its, fc)
            FLOOR[v["id"]] = max(sum(side["f"][s][j] / pf.kT_over_m(s, pf.T_CHAIN_K) for s in SPECIES)
                                 for j in range(len(its)))
            sw = pf.steady_sweep(side, py_plant(a["plant"]), py_plenum_obj(a["plenum"]), a["targets"], a["f1_ok"])
            sidev = {k: [{s: side[k][s][j] for s in SPECIES} for j in range(len(its))] for k in ("f", "e")}
            return {"side": sidev, "sweep": sw}
        return py_call(f)
    if e == "plenum.ripple":
        return py_call(lambda: pf.ripple_transfer(py_chain(a["chain"]), a["a_eq"], a["f_hz"]))
    if e == "plenum.inlet_tau":
        return py_call(lambda: pf.inlet_node_tau_per_m3(py_chain(a["chain"])))
    if e == "plenum.settling":
        return py_call(lambda: pf.settling_time(np.array(a["t"]), np.array(a["y"]), a["final"], a["band"]))
    if e == "plenum.segment_metrics":
        return py_call(lambda: pf.segment_metrics(py_segment(a["segment"]), a["p_prev_final"]))
    if e == "plenum.domain_reasons":
        return py_call(lambda: pf._domain_reasons([py_segment(s) for s in a["segments"]]))
    if e == "plenum.event_sequence":
        def f():
            return [{"name": x.name, "kind": x.kind, "duration_s": x.duration_s, "setpoint_Pa": x.setpoint_Pa,
                     "feed_factor": x.feed_factor, "intake_state": x.intake.state,
                     "orbit_amplitude": x.orbit_amplitude, "orbit_period_s": x.orbit_period_s, "density": x.density}
                    for x in pf.event_sequence(py_intake_state(a["intake"]), a["r0"], a["window_s"])]
        return py_call(f)
    if e in ("plenum.transient_run", "plenum.transient_case"):
        def f():
            fc, pl, pn = py_filter_case(a["filter"]), py_plant(a["plant"]), py_plenum_obj(a["plenum"])
            ct, des = py_controller(a["controller"]), py_intake_state(a["intake"])
            rtol, method = a.get("rtol", pf.RTOL), a.get("method")
            if e == "plenum.transient_run":
                tr = pf.TransientRun(fc, pl, pn, ct, des, a["r0"], rtol, method)
                out = tr.run(pf.event_sequence(des, a["r0"], a["window_s"]))
                taps = TAP.get(v["id"], [])
                for k, sg in enumerate(out.get("segments", [])):
                    sg["_ucmd_end"] = taps[k]["ucmd_end"] if k < len(taps) else None
                return out
            return pf.transient_case(fc, pl, pn, ct, des, a["r0"], a["orbit_check"], a["window_s"], rtol, method)
        return py_call(f)
    if e == "plenum.orbit_qs":
        return py_call(lambda: pf.orbit_quasi_static(py_filter_case(a["filter"]), py_plant(a["plant"]),
                                                     py_plenum_obj(a["plenum"]),
                                                     [py_intake_state(x) for x in a["states"]], a["r0"],
                                                     a["amplitude"], a["a_max_m2"], a["n_phase"]))
    if e == "plenum.orbit_sim":
        return py_call(lambda: pf.orbit_simulated(py_filter_case(a["filter"]), py_plant(a["plant"]),
                                                  py_plenum_obj(a["plenum"]), py_controller(a["controller"]),
                                                  py_intake_state(a["design"]), py_intake_state(a["state"]), a["r0"],
                                                  a["amplitude"]))
    if e == "plenum.strict_blockers":
        return py_call(pf.strict_blockers)
    if e == "plenum.pareto_ids":
        return py_call(lambda: pf.pareto_ids(py_args_obj(a["rows"]), a["objectives"]))
    if e == "plenum.controller_state":
        return py_call(lambda: [[k, x] for k, x in pf.intake_controller_state(py_intake_state(a["intake"])).items()])
    if e in ("plenum.scheduled", "plenum.compare_modes"):
        def f():
            fc, pl, pn = py_filter_case(a["filter"]), py_plant(a["plant"]), py_plenum_obj(a["plenum"])
            its = [py_intake_state(x) for x in a["intakes"]]
            cst = None if a["controller_states"] is None else {s: dict(py_args_obj(p)) for s, p in
                                                                a["controller_states"]}
            if e == "plenum.scheduled":
                return pf.scheduled_operation(fc, pl, pn, its, py_control(a["control"]), cst)
            return pf.compare_control_modes(fc, pl, pn, its, py_control(a["schedule"]), py_control(a["fixed"]), cst)
        return py_call(f)
    if e == "plenum.constants":
        return py_call(py_constants_plenum)
    if e == "reservoir.conductance":
        return py_call(lambda: py_reservoir(a["res"]).conductance(a["species"], a["area"], a["K"]))
    if e == "reservoir.steady":
        return py_call(lambda: py_reservoir(a["res"]).steady_state({k: x for k, x in a["mdot"]}))
    if e == "reservoir.size_orifice":
        def f():
            r = py_reservoir(a["res"])
            rec = rmod.size_orifice_for_pressure(r, {k: x for k, x in a["mdot"]}, a["p_target"], report=True)
            return {"report": rec, "area_after": r.anode_orifice_area_m2}
        return py_call(f)
    if e == "reservoir.startup":
        return py_call(lambda: rmod.startup_transient(py_reservoir(a["res"]), {k: x for k, x in a["mdot"]},
                                                      a["p_ignite"], a["spinup_s"], a["t_end_s"], a["dt_s"]))
    return py_upstream(v)


def py_upstream(v):
    a = v["args"]
    e = v["entry"]
    if e == "upstream.pressure_domain":
        p = a["p"]
        return py_call(lambda: u13.pressure_domain_status(unj(p) if p in ("NaN", "+inf", "-inf") else p))
    if e == "upstream.classify":
        return py_call(lambda: u13.classify_pressure_target(unj(a["p"])))
    if e == "upstream.schedule_input":
        def f():
            si = u13.ScheduleInput(a["input"]["name"], a["input"]["kind"], a["input"]["source"])
            return {"name": si.name, "kind": si.kind, "source": si.source}
        return py_call(f)
    if e == "upstream.control":
        def f():
            c = py_control(a["control"])
            return {"mode": c.mode, "to_dict": c.to_dict()}
        return py_call(f)
    if e == "upstream.setpoint":
        return py_call(lambda: py_control(a["control"]).setpoint({k: unj(x) for k, x in a["state"]}))
    if e == "upstream.controller_view":
        def f():
            ins = [u13.ScheduleInput(x["name"], x["kind"], x["source"]) for x in a["inputs"]]
            out = u13.controller_view({k: x for k, x in a["full_state"]}, ins, {k: x for k, x in a["mapping"]})
            return [[k, x] for k, x in out.items()]
        return py_call(f)
    if e == "upstream.combine":
        return py_call(lambda: u13.combine_value_status(a["statuses"]))
    if e == "upstream.constraint":
        return py_call(lambda: u13.constraint_status(a["ok"], a["value_status"]))
    if e == "upstream.h1_tolerance":
        def f():
            h = u13.H1Tolerance(a["quantity"], unj(a["value_frac"]), a["status"], a["source"])
            return {"quantity": h.quantity, "value_frac": h.value_frac, "status": h.status, "source": h.source}
        return py_call(f)
    if e == "upstream.governing_band":
        def f():
            h = a["h1"]
            if h is None:
                ho = None
            elif h.get("tbd"):
                ho = u13.h1_tolerance_tbd(h["quantity"])
            else:
                ho = u13.H1Tolerance(h["quantity"], unj(h["value_frac"]), h["status"], h["source"])
            return u13.governing_band(a["quantity"], unj(a["f4"]), ho)
        return py_call(f)
    if e == "upstream.coverage":
        return py_call(lambda: u13.characterization_coverage(unj(a["mdot"])))
    if e == "upstream.fixed_gate":
        def f():
            u13.refuse_fixed_mass_flow_gate(a["gate"])
            return "OK"
        return py_call(f)
    if e == "upstream.flight_requirement":
        return py_call(lambda: u13.flight_feed_requirement(None if a["status"] is None
                                                           else types.SimpleNamespace(status=a["status"])))
    if e == "upstream.flow_gap":
        return py_call(u13.flow_gap_record)
    if e == "upstream.lowering":
        def f():
            u13.refuse_feed_requirement_lowering(a["basis"], unj(a["value_mgps"]))
            return "OK"
        return py_call(f)
    if e == "upstream.state_coverage":
        return py_call(lambda: u13.state_coverage(a["used"], a["required"]))
    if e == "upstream.dense":
        return py_call(lambda: u13.dense_state_only_operation(a["used"], a["required"],
                                                              None if a["s615"] is None else {"status": a["s615"]}))
    if e == "upstream.robust_set":
        def f():
            s = a["set"]
            kw = {"set_id": s["set_id"], "version": s["version"], "members": tuple(s["members"]),
                  "objectives": tuple(s["objectives"]), "label": s["label"], "provenance": s["provenance"],
                  "regenerated_after": tuple(s.get("regenerated_after") or ())}
            if s.get("regeneration_triggers") is not None:
                kw["regeneration_triggers"] = tuple(s["regeneration_triggers"])
            rp = u13.RobustParetoSet(**kw)
            op = a["op"]
            if op == "to_dict":
                return rp.to_dict()
            if op == "representative":
                return rp.representative()
            if op == "engineering_reference":
                return rp.engineering_reference(a["member"], a["purpose"])
            return rp.pending_triggers()
        return py_call(f)
    if e == "upstream.cite":
        return py_call(lambda: u13.cite(*a["keys"]))
    if e == "upstream.verify_decisions":
        return py_call(lambda: u13.verify_decision_records(Path(ROOT)))
    if e == "upstream.candidate":
        def f():
            o = a["obj"]
            if o["kind"] == "mapping":
                obj = {"evidence_status": o.get("evidence_status")}
            else:
                obj = types.SimpleNamespace(**{k: o[k] for k in ("evidence_status", "valid_design_evidence")
                                               if o.get(k) is not None})
            u13.refuse_candidate_evidence(obj)
            return "OK"
        return py_call(f)
    if e == "upstream.constants":
        return py_call(py_constants_upstream)
    raise RuntimeError(e)


CF_PLENUM = {"plenum.orbital_period", "plenum.cbar", "plenum.kt_over_m", "plenum.f1_candidate_id", "plenum.intake",
             "plenum.filter_case", "plenum.filter_cases", "plenum.plenum", "plenum.strict_blockers",
             "plenum.status_from_reasons", "plenum.reasons_from_bits", "plenum.pareto_ids", "plenum.controller_state",
             "plenum.ripple", "plenum.inlet_tau", "plenum.constants", "plenum.settling", "plenum.segment_metrics",
             "plenum.domain_reasons", "plenum.event_sequence", "plenum.scheduled", "plenum.compare_modes",
             "reservoir.conductance"}
STEADY_ENTRIES = {"plenum.plant", "plenum.chain", "plenum.solve_pressures", "plenum.area_for_pressure",
                  "plenum.bisection_failed", "plenum.lambda_upper", "plenum.steady", "plenum.evaluate", "plenum.sweep",
                  "plenum.orbit_qs"}
TRANSIENT_ENTRIES = {"plenum.transient_run", "plenum.transient_case", "plenum.orbit_sim"}
TRAJ = {"p": "p", "mdot": "mdot", "u": "u", "xO": "xO", "t": "t"}


def transient_tol(ctx, path):
    ref = ctx["vector"]["args"].get("rtol") == pf.RTOL_REFERENCE
    leaf = path[-1] if path else ""
    keys = [c for c in path if isinstance(c, str)]
    last = keys[-1] if keys else ""
    if isinstance(leaf, int) and last in TRAJ:
        if last in ("p", "mdot"):
            return {"rel": 1e-5 if ref else 1e-3, "abs": 0.0}
        if last in ("u", "xO"):
            return {"rel": 0.0, "abs": 1e-5 if ref else 1e-3}
        return {"rel": 1e-12, "abs": 0.0}
    if last == "valve_travel":
        return {"rel": 1e-4 if ref else 1e-2, "abs": 1e-6 if ref else 1e-4}
    if last in ("settling_time_s", "flow_recovery_s", "settling_max_s"):
        return {"rel": 1e-12, "abs": 0.0}
    return {"rel": 1e-5 if ref else 1e-3, "abs": 1e-8 if ref else 1e-6}


def rule_plenum(ctx, path, py):
    e = ctx["entry"]
    keys = [c for c in path if isinstance(c, str)]
    last = keys[-1] if keys else ""
    if e in CF_PLENUM or e.startswith("upstream."):
        return ("ULP", CF)
    if e in STEADY_ENTRIES:
        tol = dict(STEADY)
        if e in ("plenum.steady", "plenum.evaluate", "plenum.sweep", "plenum.orbit_qs"):
            if any("kgps" in k for k in keys):
                fl = FLOOR.get(ctx["vector"]["id"])
                if fl is None and e == "plenum.orbit_qs":
                    fl = 0.0
                tol["a_abs"] = 1e-12 * (fl or 0.0)
            if last == "bisection_residual_rel":
                tol["a_abs"] = 1e-9
        if e == "plenum.chain" and last == "f":
            a = ctx["py"]
            tol["a_abs"] = 1e-12 * sum(abs(a[s]["f"]) for s in SPECIES if isinstance(a[s]["f"], float))
        if e == "plenum.area_for_pressure" and last == "resid":
            tol["a_abs"] = 1e-9
        return ("ULP", tol)
    if e == "plenum.stability_class":
        return ("UNSCORED", None)       # class and equilibrium kinds EXACT; Re lambda_max reported
    if e in TRANSIENT_ENTRIES:
        if v3_on():
            return rule_transient_v3(ctx, path, py)
        return ("SOLVER", transient_tol(ctx, path))
    if e in ("reservoir.steady", "reservoir.size_orifice"):
        tol = {"rel": 1e-10, "k_ulp": 4, "abs": 0.0}
        if last in ("residual", "balance_residual_rel", "p_residual_rel"):
            tol["abs"] = 1e-12
        return ("SOLVER", tol)
    if e == "reservoir.startup":
        if last == "t_ignite_s":
            r = ctx["py"]
            dt = min(ctx["vector"]["args"]["dt_s"], r["tau_s"] / 20.0) if isinstance(r.get("tau_s"), float) else 0.0
            return ("SOLVER", {"abs": 1.0001 * dt, "rel": 0.0})
        return ("ULP", {"k_ulp": 4, "r_rel": 1e-9})
    return ("ULP", CF)


def skip_plenum(entry, path):
    keys = [c for c in path if isinstance(c, str)]
    if not keys:
        return False
    if "conservation_residual_rel" in keys or keys[-1] == "_ucmd_end":
        return True
    if entry in TRANSIENT_ENTRIES and keys[-1] in ("nfev", "mass_residual_rel"):
        return True
    if CONTRACT_VERSION["plenum"] >= 5 and entry == "plenum.transient_run" and keys[-1] in V5_CASCADE:
        return True     # contract v5 ill_conditioned_diagnostics.rule_cascade: reported, scored through primitives
    if entry in ("reservoir.steady",) and keys[-1] == "iterations":
        return True
    return False


def pre_plenum(v, rust_value):
    """Rust-only diagnostics stripped before the comparison (kept for INV-P-02)."""
    if v["entry"] == "plenum.sweep" and isinstance(rust_value, dict):
        SCALAR[v["id"]] = rust_value.pop("_scalar", None)
    return rust_value


SCALAR: dict = {}
# Transient solutions can coincide with an input (the controlled pressure equals its setpoint at a sample): there the
# copied-float rule applies only to the leaves that are copied by construction.
TRANSIENT_COPIED = {"setpoint_Pa", "duration_s", "t_start_s", "V_m3", "T_comp_limit_K", "shaft_hz", "amplitude"}
COPIED_OK = {e: (lambda path: bool(path) and isinstance(path[-1], str) and path[-1] in TRANSIENT_COPIED)
             for e in TRANSIENT_ENTRIES}
DISCRETE_OBS = re.compile(r"(status|reasons|bits|offered|in_domain|ok|saturated_end|\{keys\}|\[len\]|outcome|"
                          r"settling|flow_recovery|objectives|summary|reason|label|role)")


def near(x, theta, tol_rel, tol_abs=0.0):
    return isinstance(x, (int, float)) and math.isfinite(x) and abs(x - theta) <= tol_rel * abs(x) + tol_abs \
        + 1e-12 * abs(theta)


def steady_flags(rec):
    """Quantities of a Python steady record within their tolerance of a registered threshold."""
    out = []
    if not isinstance(rec, dict):
        return out
    c = rec.get("compressor") or {}
    dd = rec.get("domain_diagnostics") or {}
    vals = {"K_min": c.get("K_min", dd.get("compressor_K_min")),
            "K_over_K0_max": c.get("K_over_K0_max", dd.get("compressor_K_over_K0_max")),
            "p_stage_max": c.get("p_stage_max_Pa", dd.get("compressor_p_stage_max_Pa")),
            "p_inlet": rec.get("compressor_inlet_P_Pa", dd.get("compressor_inlet_P_Pa")),
            "Kn": (rec.get("feed") or {}).get("Kn_upper_O_omitted", dd.get("feed_Kn_upper_O_omitted")),
            "T_comp": c.get("T_comp_K"), "target": rec.get("target_Pa"), "p_dead": rec.get("p_deadhead_Pa"),
            "resid": rec.get("bisection_residual_rel"), "a_eq": rec.get("a_eq_m2")}
    tol = 1e-9
    for q, theta in (("K_min", 1 - pf.K_TOL), ("K_over_K0_max", 1 + pf.K_TOL),
                     ("p_stage_max", pf.P_DOMAIN_PA * (1 + 1e-12)), ("p_inlet", pf.P_DOMAIN_PA), ("Kn", pf.KN_MIN)):
        if near(vals[q], theta, tol):
            out.append({"quantity": q, "theta": theta, "python": vals[q]})
    if isinstance(vals["target"], float) and near(vals["p_dead"], vals["target"], tol):
        out.append({"quantity": "target vs p_deadhead", "theta": vals["target"], "python": vals["p_dead"]})
    if near(vals["resid"], pf.BISECT_RTOL, 0.0, 1e-9):
        out.append({"quantity": "bisection_residual_rel", "theta": pf.BISECT_RTOL, "python": vals["resid"]})
    for b in pf.A_EQ_BRACKET_M2:
        if near(vals["a_eq"], b, 1e-9 + 1e-9):
            out.append({"quantity": "a_eq vs bracket", "theta": b, "python": vals["a_eq"]})
    if isinstance(vals["T_comp"], float):
        for m in DB.values():
            if near(vals["T_comp"], m.T_max_K, tol):
                out.append({"quantity": "T_comp vs T_max_K", "theta": m.T_max_K, "python": vals["T_comp"]})
    return out


def transient_flags(v, py):
    out = []
    ref = v["args"].get("rtol") == pf.RTOL_REFERENCE
    tr = 1e-5 if ref else 1e-3
    tu = 1e-5 if ref else 1e-3
    for k, seg in enumerate(TAP.get(v["id"], [])):
        if near(seg["p_max"], pf.P_DOMAIN_PA, tr):
            out.append({"quantity": "max trajectory p", "segment": k, "theta": pf.P_DOMAIN_PA, "python": seg["p_max"]})
        for theta in (1.0 + 1e-9, -1e-9):
            if abs(seg["ucmd_end"] - theta) <= tu:
                out.append({"quantity": "u_cmd end", "segment": k, "theta": theta, "python": seg["ucmd_end"]})
        for y, fin in ((seg["p"], seg["setpoint"]), (seg["mdot"], seg["mdot"][-1])):
            band = pf.SETTLE_BAND * abs(fin)
            if any(abs(abs(x - fin) - band) <= 2 * tr * abs(fin) for x in y):
                out.append({"quantity": "settling band", "segment": k, "theta": band})
                break
    return out


def proximity_plenum(v, rust, py, sub):
    """Threshold-proximity rule (registered): a discrete difference is NOT_SCORED_AT_THRESHOLD only where the Python
    value of the governing quantity lies within its tolerance of the threshold; continuous leaves stay scored."""
    if v3_on() and v["entry"] in TRANSIENT_ENTRIES:
        return proximity_transient_v3(v, rust, py, sub)
    if not sub.failures or v["entry"] not in ("plenum.steady", "plenum.evaluate", "plenum.sweep", "plenum.orbit_qs",
                                              "plenum.transient_run", "plenum.transient_case", "plenum.orbit_sim"):
        return None
    # discrete outcomes: statuses / reasons / bits / booleans / None-ness, and the settling / flow-recovery sample
    # index (scored through its sample time)
    discrete = all((f.get("class") is None and (DISCRETE_OBS.search(f["observable"]) or "None" in (f["rust"],
                                                                                                   f["python"])))
                   or f["observable"].endswith(("settling_time_s", "flow_recovery_s", "settling_max_s"))
                   for f in sub.failures)
    if not discrete:
        return None
    if v["entry"] in ("plenum.steady", "plenum.evaluate"):
        flags = steady_flags(py)
    elif v["entry"] in ("plenum.transient_run", "plenum.transient_case", "plenum.orbit_sim"):
        flags = transient_flags(v, py)
    else:
        flags = []
        if v["entry"] == "plenum.sweep":
            sc = SCALAR.get(v["id"]) or []
            for row in sc:
                for rec in row:
                    flags += steady_flags(rec)
        else:
            flags = [{"quantity": "u_max vs 1"} for r in (py.get("rows") or []) if near(r.get("u_max"), 1.0, 1e-9)]
    if not flags:
        return None
    t2 = Tally()
    ctx = {"vector": v, "entry": v["entry"], "inputs": input_floats(v["args"]), "py": py, "rust": rust,
           "skip": lambda entry, path: False}

    def walk(r, p, path=()):
        if isinstance(p, dict) and isinstance(r, dict):
            for k in p:
                if k in r:
                    walk(r[k], p[k], path + (k,))
        elif isinstance(p, list) and isinstance(r, list) and len(p) == len(r):
            for i, (x, y) in enumerate(zip(r, p)):
                walk(x, y, path + (i,))
        elif isinstance(p, float) and is_num(r) and not skip_plenum(v["entry"], path) and not (
                path and path[-1] in ("settling_time_s", "flow_recovery_s", "settling_max_s")):
            spec = rule_plenum(ctx, path, p)
            if spec[0] != "EXACT":
                t2.flt(v["entry"], norm_path(path), r, p, spec, v["id"], "/".join(map(str, path)))
    walk(rust, py)
    return {"vector": v["id"], "entry": v["entry"], "status": "NOT_SCORED_AT_THRESHOLD", "flags": flags[:10],
            "n_unscored_leaves": len(sub.failures),
            "unscored_discrete_differences": [{k: f[k] for k in ("observable", "path", "rust", "python") if k in f}
                                              for f in sub.failures][:10], "_tally": t2}


def checks_plenum(t, vectors, py_out, rres):
    cons1, cons2, cons3, cons4, inv2, inv4 = [], [], [], [], [], True
    for v in vectors:
        r = rres[v["id"]]
        if r["outcome"] != "OK":
            continue
        val = r["value"]
        e = v["entry"]
        if e in ("plenum.steady", "plenum.evaluate") and isinstance(val, dict):
            recs = [val]
        elif e in ("plenum.scheduled",):
            recs = val.get("rows") or []
        elif e == "plenum.compare_modes":
            recs = (val["baseline"].get("rows") or []) + (val["fallback_reference"].get("rows") or [])
        else:
            recs = []
        for rec in recs:
            off = rec.get("offered")
            c = rec.get("compressor") or {}
            tgt = rec.get("target_Pa", (rec.get("setpoint") or {}).get("setpoint_Pa"))
            touched = [x for x in (tgt, c.get("p_stage_max_Pa"), rec.get("compressor_inlet_P_Pa"))
                       if isinstance(x, float)]
            if off is not None and (any(x > pf.P_DOMAIN_PA * (1 + 1e-12) for x in touched)):
                inv4 = False
        if e in ("plenum.steady", "plenum.evaluate") and isinstance(val, dict) and "mdot_intake_net_kgps" in val:
            fl = FLOOR.get(v["id"], 0.0)
            net = sum(val["mdot_intake_net_kgps"].values())
            h1 = sum((val.get("offered") or {}).get("mdot_s_kgps", {}).values()) if val.get("offered") else None
            if h1 is not None:
                res = abs(net - (h1 + sum(val["mdot_plenum_leak_kgps"].values())))
                cons1.append({"vector": v["id"], "residual_kgps": res, "limit_kgps": 1e-12 * fl,
                              "ok": res <= 1e-12 * fl})
            cr = val.get("conservation_residual_rel") or {}
            worst = max(cr.get("inlet_node", 0.0), cr.get("plenum", 0.0))
            cons2.append({"vector": v["id"], "residual_rel": worst, "ok": worst <= pf.MASS_TOL})
        if e == "plenum.transient_run" and val.get("ok"):
            cons3.append({"vector": v["id"], "mass_residual_rel": val["mass_residual_rel"],
                          "ok": val["mass_residual_rel"] <= pf.MASS_TOL})
        if e == "plenum.transient_case" and isinstance(val.get("summary"), dict):
            m = val["summary"]["mass_residual_rel"]
            cons3.append({"vector": v["id"], "mass_residual_rel": m, "ok": m <= pf.MASS_TOL})
        if e == "plenum.orbit_sim" and val.get("ok"):
            cons3.append({"vector": v["id"], "mass_residual_rel": val["mass_residual_rel"],
                          "ok": val["mass_residual_rel"] <= pf.MASS_TOL})
        if e == "reservoir.steady" and val.get("converged"):
            cons4.append({"vector": v["id"], "balance_residual_rel": val["balance_residual_rel"],
                          "ok": val["balance_residual_rel"] <= 1e-12})
        if e == "plenum.sweep":
            sc = SCALAR.get(v["id"]) or []
            sw = val["sweep"]
            f1_given = v["args"]["f1_ok"] is not None
            for j, row in enumerate(sc):
                for k, rec in enumerate(row):
                    if "__error__" in rec:
                        inv2.append({"vector": v["id"], "point": [j, k], "ok": False, "why": "scalar error"})
                        continue
                    reasons = set(pf.reasons_from_bits(sw["bits"][j][k]))
                    sr = set(rec["reasons"])
                    if not f1_given:
                        sr.discard(pf.R_UPSTREAM_F1)
                    ok = reasons == sr
                    tt = Tally()
                    if sw["in_domain"][j][k] and rec.get("offered"):
                        for a_, b_ in ((sw["mdot_total_kgps"][j][k], rec["offered"]["mdot_total_kgps"]),
                                       (sw["a_eq_m2"][j][k], rec["a_eq_m2"]),
                                       (sw["P_el_W"][j][k], rec["compressor"]["P_el_W"]),
                                       (sw["T_comp_K"][j][k], rec["compressor"]["T_comp_K"]),
                                       (sw["m_compressor_kg"][j][k], rec["compressor"]["mass_kg"]),
                                       (sw["Kn_upper"][j][k], rec["feed"]["Kn_upper_O_omitted"])):
                            ok = tt.flt("INV-P-02", "v", a_, b_, ("ULP", dict(STEADY, a_abs=1e-12 * FLOOR.get(
                                v["id"], 0.0))), v["id"]) and ok
                    inv2.append({"vector": v["id"], "point": [j, k], "ok": ok})
    summ = lambda L: {"n": len(L), "n_fail": sum(1 for c in L if not c["ok"]),  # noqa: E731
                      "failures": [c for c in L if not c["ok"]][:20], "ok": all(c["ok"] for c in L)}
    out = {"CONS-P-01": summ(cons1), "CONS-P-02": summ(cons2), "CONS-P-03": summ(cons3), "CONS-P-04": summ(cons4),
           "INV-P-02": summ(inv2), "INV-P-04": {"ok": inv4}}
    if v3_on():
        out["CONS-P-03"]["python_recorded"] = cons3_python(vectors, py_out)
        out.update(checks_transient_v3(vectors, py_out, rres))
    out["CONS-P-01"]["max_residual_over_floor"] = max((c["residual_kgps"] / c["limit_kgps"] * 1e-12 for c in cons1
                                                       if c["limit_kgps"] > 0), default=0.0)
    out["CONS-P-02"]["max_residual_rel"] = max((c["residual_rel"] for c in cons2), default=0.0)
    out["CONS-P-03"]["max_mass_residual_rel"] = max((c["mass_residual_rel"] for c in cons3), default=0.0)
    out["CONS-P-04"]["max_balance_residual_rel"] = max((c["balance_residual_rel"] for c in cons4), default=0.0)
    return out


def cons3_python(vectors, py_out):
    """CONS-P-03 on the Python reference runs (recorded, not a Rust criterion)."""
    rows = []
    for v in vectors:
        po = py_out[v["id"]]
        if po[0] != "OK" or not isinstance(po[1], dict) or v["entry"] not in TRANSIENT_ENTRIES:
            continue
        val = po[1]
        m = (val.get("summary") or {}).get("mass_residual_rel") if v["entry"] == "plenum.transient_case" else \
            (val.get("mass_residual_rel") if val.get("ok") else None)
        if m is not None:
            rows.append({"vector": v["id"], "mass_residual_rel": unj(m), "ok": unj(m) <= pf.MASS_TOL})
    return {"n": len(rows), "n_fail": sum(1 for r in rows if not r["ok"]),
            "max_mass_residual_rel": max((r["mass_residual_rel"] for r in rows), default=0.0)}


# ======================================================================================================================
# Plenum contract v3: the A9.31 sec. 5 convergence-derived transient procedure (transient_convergence_procedure_v3)
# ======================================================================================================================
V3_DIAG = ("K_min", "K_over_K0_max", "p_stage_max_Pa", "p_inlet_max_Pa", "P_el_max_W", "T_comp_max_K")
V5_CASCADE = ("K_min", "K_over_K0_max", "p_stage_max_Pa", "P_el_max_W", "T_comp_max_K")   # reported (v5)
V3_FAMILY = {
    "plenum.transient_run": {("segments", "p"): "F42.p", ("segments", "u"): "F42.u", ("segments", "mdot"): "F42.mdot",
                             ("segments", "xO"): "F42.xO", ("segments", "_ucmd_end"): "F42.ucmd_end",
                             ("throughput_kg",): "F42.throughput"},
    "plenum.transient_case": {
        **{("metrics", k): "F43.p" for k in ("P_final_Pa", "P_min_Pa", "P_max_Pa")},
        **{("summary", k): "F43.p" for k in ("P_min_Pa", "P_max_Pa")},
        **{("metrics", k): "F43.setpoint_frac" for k in ("final_setpoint_error_frac", "peak_deviation_frac")},
        ("objectives", "peak_deviation_max"): "F43.setpoint_frac",
        ("metrics", "overshoot_frac"): "F43.overshoot", ("summary", "overshoot_max"): "F43.overshoot",
        **{("metrics", k): "F43.mdot" for k in ("mdot_final_kgps", "mdot_min_kgps", "mdot_max_kgps")},
        **{("summary", k): "F43.mdot" for k in ("mdot_min_kgps", "mdot_max_kgps")},
        **{("metrics", k): "F43.xO" for k in ("xO_min", "xO_max")},
        **{("summary", k): "F43.xO" for k in ("xO_flow_min", "xO_flow_max")},
        **{("metrics", k): "F43.u" for k in ("u_min", "u_max")},
        ("metrics", "valve_travel"): "F43.valve_travel", ("objectives", "valve_travel"): "F43.valve_travel_total"},
    "plenum.orbit_sim": {("P_dev_max_frac",): "F45.P_dev", ("mdot_min_kgps",): "F45.mdot",
                         ("mdot_max_kgps",): "F45.mdot"}}
V3_CODE = {"plenum.transient_run": "P42", "plenum.transient_case": "P43", "plenum.orbit_sim": "P45"}
V3_SAMPLE_TIME = {("metrics", "settling_time_s"), ("metrics", "flow_recovery_s"), ("objectives", "settling_max_s"),
                  ("segments", "t")}
V3_STEADY = {("summary", k) for k in ("a_eq_design_m2", "a_eq_max_m2", "plenum_tau_s", "shaft_hz", "inventory_kg",
                                      "ride_through_s")} | {("objectives", "ripple_transfer_shaft"),
                                                            ("objectives", "P_compressor_el_W")}
CF_T = {"k_ulp": 4, "r_rel": 1e-12}
V3_SCALE: dict = {}     # family -> registered scale kind (filled from the contract)
EPS = 2.0 ** -52
ENV: dict = {}          # the frozen envelope record (scoring) or a development draft (dev only)
IMG: dict = {}          # vector id -> per-segment primitive images of the cascade diagnostics
MDS: dict = {}          # vector id -> mdot_scale (design steady delivered flow of the reference)


def v3_on() -> bool:
    return CONTRACT_VERSION["plenum"] >= 3


def v3_families() -> dict:
    """family -> scale kind, from the registered contract (one source of truth)."""
    fams = load_contract("plenum")[0]["transient_convergence_procedure_v3"]["step_3_envelope_estimator"]["families"]
    out = {f: d["scale"] for code in fams.values() for f, d in code.items()}
    mapped = {f for m in V3_FAMILY.values() for f in m.values()}
    if mapped != set(out):
        raise RuntimeError(f"harness family map {sorted(mapped)} != contract families {sorted(out)}")
    return out


def level_of(v) -> str:
    return "REF" if v["args"].get("rtol") == pf.RTOL_REFERENCE else "PROD"


def keys_of(path) -> tuple:
    return tuple(c for c in path if isinstance(c, str))


def parse_path(s: str) -> tuple:
    return tuple(int(c) if c.isdigit() else c for c in s.split("/")) if s else ()


def get_path(tree, path):
    for c in path:
        if isinstance(tree, dict) and isinstance(c, str) and c in tree:
            tree = tree[c]
        elif isinstance(tree, list) and isinstance(c, int) and c < len(tree):
            tree = tree[c]
        else:
            return None
    return tree


def mdot_scale_of(v):
    """TransientRun(...).mdot_scale of the reference (registered family scale); None at / above dead-head."""
    if v["id"] not in MDS:
        a = v["args"]
        try:
            tr_ = pf.TransientRun(py_filter_case(a["filter"]), py_plant(a["plant"]), py_plenum_obj(a["plenum"]),
                                  py_controller(a["controller"]),
                                  py_intake_state(a["design"] if v["entry"] == "plenum.orbit_sim" else a["intake"]),
                                  a["r0"])
            MDS[v["id"]] = float(tr_.mdot_scale)
        except ValueError:
            MDS[v["id"]] = None
    return MDS[v["id"]]


def family_scale(kind, v, ref_value):
    if kind == "r0":
        return float(v["args"]["r0"])
    if kind == "mdot_scale":
        return mdot_scale_of(v)
    if kind == "1":
        return 1.0
    if kind == "relative":
        return abs(ref_value) if isinstance(ref_value, float) and math.isfinite(ref_value) else None
    raise RuntimeError(kind)


def env_of(impl, level, code, fam, v=None):
    if v7_on():
        return own_env_v7(impl, v, level, code, fam)
    e = ENV["envelopes"][impl].get(level, {}).get(code, {}).get(fam)
    return None if e is None else e["E"]


def env_sum(level, code, fam, v=None):
    if v7_on():
        return bound_of(v, level, code, fam)
    a, b = env_of("python", level, code, fam), env_of("rust", level, code, fam)
    return None if a is None or b is None else a + b


# ------------------------------------------------------------------------------------------------ primitive image
def diag_images(v) -> list:
    """Per segment and cascade diagnostic: the reference value f(y), the image half-width W over the 8 corners of the
    per-species box y_s +/- delta (delta = combined F42.p envelope at the vector's level), the image interval and
    kappa = W / (delta |f|) (contract v3 ill_conditioned_diagnostics)."""
    vid = v["id"]
    if vid in IMG:
        return IMG[vid]
    delta = env_sum(level_of(v), "P42", "F42.p", v)
    out = []
    for tp in TAP.get(vid, []):
        tr_, ev, t0, t, y = tp["tr"], tp["ev"], tp["t0"], tp["t"], tp["y"]
        base = _ORIG_SEG(tr_, ev, t0, types.SimpleNamespace(t=t, y=y))
        corners, rcorners = [], []
        for sig in itertools.product((-1.0, 1.0), repeat=3):
            yy = np.array(y, dtype=float, copy=True)
            yr = np.array(y, dtype=float, copy=True)
            for i in range(3):
                yy[i] = yy[i] + sig[i] * delta
                yr[i] = yr[i] * (1.0 + sig[i] * 4.0 * EPS)
            corners.append(_ORIG_SEG(tr_, ev, t0, types.SimpleNamespace(t=t, y=yy)))
            rcorners.append(_ORIG_SEG(tr_, ev, t0, types.SimpleNamespace(t=t, y=yr)))
        rec = {"T_comp_limit_K": base["T_comp_limit_K"], "base_equals_reported": all(
            struct.pack("<d", float(base[n])) == struct.pack("<d", float(tp["diag"][n])) for n in V3_DIAG)}
        for n in V3_DIAG:
            f0 = float(base[n])
            vals = [float(c[n]) for c in corners]
            if math.isfinite(f0) and all(math.isfinite(x) for x in vals):
                W = max(abs(x - f0) for x in vals)
                lo, hi = min(vals + [f0]), max(vals + [f0])
            else:
                W, lo, hi = math.inf, -math.inf, math.inf
            kappa = W / (delta * abs(f0)) if f0 != 0.0 and math.isfinite(f0) and delta > 0 else math.inf
            rv = [float(c[n]) for c in rcorners]
            Wr = max(abs(x - f0) for x in rv) if math.isfinite(f0) and all(math.isfinite(x) for x in rv) else math.inf
            kr = Wr / (4.0 * EPS * abs(f0)) if f0 != 0.0 and math.isfinite(f0) else math.inf
            rec[n] = {"f": f0, "W": W, "lo": lo, "hi": hi, "kappa": kappa, "W_round": Wr, "kappa_round": kr}
        out.append(rec)
    IMG[vid] = out
    return out


# ------------------------------------------------------------------------------------------------ scoring rule
def rule_transient_v3(ctx, path, py):
    v, e = ctx["vector"], ctx["entry"]
    keys = keys_of(path)
    fam = V3_FAMILY[e].get(keys)
    lvl = level_of(v)
    if fam is not None:
        E = env_sum(lvl, V3_CODE[e], fam, v)
        if v7_on():
            s = family_scale_v7(v, fam, py if isinstance(py, float) else None)
        else:
            s = family_scale(V3_SCALE[fam], v, py if isinstance(py, float) else None)
        if E is None or s is None:
            return ("ENV", {"abs_env": None, "family": fam, "level": lvl, "why": "envelope or scale NOT_EVALUATED"})
        return ("ENV", {"abs_env": E * s, "family": fam, "level": lvl})
    if e == "plenum.transient_run" and len(keys) == 2 and keys[0] == "segments" and keys[1] in V3_DIAG:
        imgs = diag_images(v)
        k = path[1]
        W = imgs[k][keys[1]]["W"] if k < len(imgs) else None
        return ("ENV", {"abs_env": W, "family": "image:" + keys[1], "level": lvl})
    if keys in V3_SAMPLE_TIME or (keys and keys[-1] in TRANSIENT_COPIED):
        return ("ULP", CF_T)
    if keys in V3_STEADY:
        return ("ULP", STEADY)
    raise RuntimeError(f"contract v3: unregistered transient leaf {e} {path}")


# ------------------------------------------------------------------------------------------------ proximity (v3)
def proximity_transient_v3(v, rust, py, sub):
    """threshold_proximity_rule.v3_transient: every differing discrete leaf must be attributed to a flagged governing
    quantity of the same segment; excused leaves are NOT_SCORED_AT_THRESHOLD (counted per leaf), the rest fail."""
    if not sub.failures or v["entry"] == "plenum.orbit_sim":
        return None
    e, vid, lvl = v["entry"], v["id"], level_of(v)
    taps = TAP.get(vid, [])
    r0, ms = float(v["args"]["r0"]), mdot_scale_of(v)
    tol_p = env_sum(lvl, "P42", "F42.p", v) * r0
    tol_md = env_sum(lvl, "P42", "F42.mdot", v) * ms
    tol_u = env_sum(lvl, "P42", "F42.u", v)
    tol_uc = env_sum(lvl, "P42", "F42.ucmd_end", v)
    flags = []

    def sat_flag(k):
        if k >= len(taps):
            return False
        hit = [th for th in (1.0 + 1e-9, -1e-9) if abs(taps[k]["ucmd_end"] - th) <= tol_uc]
        if hit:
            flags.append({"quantity": "u_cmd end", "segment": k, "theta": hit[0], "python": taps[k]["ucmd_end"],
                          "tol": tol_uc})
        return bool(hit)

    def settle_flag(k, which):
        if k >= len(taps):
            return False
        if which == "p":
            y, fin, tol = taps[k]["p"], taps[k]["setpoint"], tol_p
        else:
            y, fin, tol = taps[k]["mdot"], taps[k]["mdot"][-1], 2.0 * tol_md
        band = pf.SETTLE_BAND * abs(fin)
        hit = any(abs(abs(x - fin) - band) <= tol for x in y)
        if hit:
            flags.append({"quantity": f"settling band ({which})", "segment": k, "theta": band, "tol": tol})
        return hit

    def image_interval(name, agg):
        imgs = diag_images(v)
        if not imgs:
            return None
        lo = agg(r[name]["lo"] for r in imgs)
        hi = agg(r[name]["hi"] for r in imgs)
        return lo, hi

    def straddles(iv, theta):
        return iv is not None and iv[0] <= theta <= iv[1]

    def reason_flag(reason):
        n_seg = len(taps)
        if reason == pf.R_NOT_SETTLED:
            return any(settle_flag(k, "p") or settle_flag(k, "mdot") for k in range(1, n_seg))
        if reason == pf.R_SATURATED:
            return any(sat_flag(k) for k in range(1, n_seg))
        if reason == pf.R_TRAJ_DOMAIN:
            pm = max(tp["p_max"] for tp in taps) if taps else math.nan
            hit = abs(pm - pf.P_DOMAIN_PA) <= tol_p
            if hit:
                flags.append({"quantity": "max trajectory p", "theta": pf.P_DOMAIN_PA, "python": pm, "tol": tol_p})
            return hit
        if reason == pf.R_CHARACTERISTIC:
            hit = straddles(image_interval("K_min", min), 1.0 - pf.K_TOL) or \
                straddles(image_interval("K_over_K0_max", max), 1.0 + pf.K_TOL)
        elif reason == pf.R_STAGE_DOMAIN:
            hit = straddles(image_interval("p_stage_max_Pa", max), pf.P_DOMAIN_PA * (1 + 1e-12)) or \
                straddles(image_interval("p_inlet_max_Pa", max), pf.P_DOMAIN_PA)
        elif reason == pf.R_THERMAL:
            imgs = diag_images(v)
            hit = bool(imgs) and straddles(image_interval("T_comp_max_K", max), imgs[0]["T_comp_limit_K"])
        else:
            return False
        if hit:
            flags.append({"quantity": f"image interval ({reason})"})
        return hit

    rs_r, rs_p = set(rust.get("reasons") or []), set(py.get("reasons") or [])
    reasons_excused = bool(rs_r ^ rs_p) and all(reason_flag(r) for r in sorted(rs_r ^ rs_p))
    excused, unexcused = [], []
    for f in sub.failures:
        path = parse_path(f.get("path", ""))
        keys = keys_of(path)
        ok = False
        if e == "plenum.transient_run" and len(path) >= 3 and path[0] == "segments":
            k = path[1]
            if keys == ("segments", "saturated_end"):
                ok = sat_flag(k)
            elif keys == ("segments", "xO") and len(path) == 4:
                pr, rr = get_path(py, path), get_path(rust, path)
                if (pr == "NaN") != (rr == "NaN"):
                    u = get_path(py, ("segments", k, "u", path[3]))
                    ok = isinstance(u, float) and abs(u) <= tol_u
                    if ok:
                        flags.append({"quantity": "valve opening sign (xO None-ness)", "segment": k,
                                      "sample": path[3], "python_u": u, "tol": tol_u})
        elif e == "plenum.transient_case":
            k = path[1] if len(path) > 1 and isinstance(path[1], int) else None
            if keys == ("metrics", "saturated_end"):
                ok = sat_flag(k)
            elif keys == ("metrics", "settling_time_s"):
                ok = settle_flag(k, "p")
            elif keys == ("metrics", "flow_recovery_s"):
                ok = settle_flag(k, "mdot")
            elif keys == ("objectives", "settling_max_s"):
                ok = any(settle_flag(j, "p") or settle_flag(j, "mdot") for j in range(1, len(taps)))
            elif keys and keys[0] == "reasons":
                ok = reasons_excused
            elif keys == ("status",):
                ok = reasons_excused
        (excused if ok else unexcused).append(f)
    if not excused:
        return None
    for f in excused:
        sub.unfail(f)
    sub.failures = unexcused
    # contract v7 closing_valve_xO.proximity_counting: excused xO None-ness samples count once per (vector, segment) in
    # the proximity limit (one governing quantity: the sign of the segment's rounding-level valve opening); all are
    # reported
    n_count = len(excused)
    xo_none = [f for f in excused if keys_of(parse_path(f.get("path", ""))) == ("segments", "xO")]
    if v7_on() and xo_none:
        n_count = len(excused) - len(xo_none) + len({parse_path(f["path"])[1] for f in xo_none})
    return {"vector": vid, "entry": e, "status": "NOT_SCORED_AT_THRESHOLD", "n_unscored_leaves": n_count,
            "n_excused_leaves": len(excused), "n_xO_none_ness_leaves (v7: counted once per segment)": len(xo_none),
            "flags": flags[:20], "unscored_discrete_differences": [
                {k: f[k] for k in ("observable", "path", "rust", "python") if k in f} for f in excused][:20],
            "unexcused_failures": len(unexcused), "_tally": sub}


# ------------------------------------------------------------------------------------------------ integrity checks
def checks_transient_v3(vectors, py_out, rres):
    """NN-P-01, NN-P-02, VS-P-01, EV-P-01 (Rust required, own envelope; Python recorded) and the image check."""
    res = {c: {"rust": [], "python": []} for c in ("NN-P-01", "NN-P-02", "VS-P-01", "EV-P-01")}
    img_check = []
    for v in vectors:
        e = v["entry"]
        if e not in V3_CODE:
            continue
        lvl = level_of(v)
        ms = mdot_scale_of(v)
        evs = None
        if e != "plenum.orbit_sim":
            evs = [(x.name, x.kind, x.duration_s) for x in pf.event_sequence(
                py_intake_state(v["args"]["intake"]), v["args"]["r0"], v["args"]["window_s"])]
        for impl, val in (("rust", rres[v["id"]].get("value") if rres[v["id"]]["outcome"] == "OK" else None),
                          ("python", py_out[v["id"]][1] if py_out[v["id"]][0] == "OK" else None)):
            if not isinstance(val, dict):
                continue
            bad = {c: [] for c in res}

            def fnum_(x):
                return unj(x) if isinstance(x, str) else x
            if e == "plenum.transient_run" and val.get("ok"):
                Eu, Em = env_of(impl, lvl, "P42", "F42.u", v), env_of(impl, lvl, "P42", "F42.mdot", v)
                t_start = 0.0
                for k, sg in enumerate(val["segments"]):
                    if any(fnum_(x) < 0.0 for x in sg["p"]):
                        bad["NN-P-01"].append([k, "p"])
                    if ms is not None and any(fnum_(x) < -Em * ms for x in sg["mdot"]):
                        bad["NN-P-02"].append([k, "mdot"])
                    if any(not (-Eu <= fnum_(x) <= 1.0 + Eu) for x in sg["u"]):
                        bad["VS-P-01"].append([k, "u"])
                    t = [fnum_(x) for x in sg["t"]]
                    if (k >= len(evs) or (sg["event"], sg["kind"]) != evs[k][:2] or sg["t_start_s"] != t_start
                            or t[0] != 0.0 or t[-1] != sg["duration_s"] or any(b <= a for a, b in zip(t, t[1:]))):
                        bad["EV-P-01"].append(k)
                    t_start += sg["duration_s"]
                if len(val["segments"]) != len(evs):
                    bad["EV-P-01"].append("count")
                if not (fnum_(val["throughput_kg"]) >= 0.0):
                    bad["NN-P-02"].append("throughput_kg")
            if e == "plenum.transient_case" and val.get("metrics"):
                Eu, Em = env_of(impl, lvl, "P43", "F43.u", v), env_of(impl, lvl, "P43", "F43.mdot", v)
                for k, m in enumerate(val["metrics"]):
                    if not (fnum_(m["P_min_Pa"]) >= 0.0):
                        bad["NN-P-01"].append([k, "P_min_Pa"])
                    if ms is not None and not (fnum_(m["mdot_min_kgps"]) >= -Em * ms):
                        bad["NN-P-02"].append([k, "mdot_min_kgps"])
                    if not (fnum_(m["u_min"]) >= -Eu and fnum_(m["u_max"]) <= 1.0 + Eu):
                        bad["VS-P-01"].append([k, "u"])
                    if k >= len(evs) or (m["event"], m["kind"]) != evs[k][:2]:
                        bad["EV-P-01"].append(k)
                if len(val["metrics"]) != len(evs):
                    bad["EV-P-01"].append("count")
                inv = (val.get("summary") or {}).get("inventory_kg")
                if inv is not None and not (fnum_(inv) > 0.0):
                    bad["NN-P-02"].append("inventory_kg")
            if e == "plenum.orbit_sim" and val.get("ok"):
                Em = env_of(impl, lvl, "P45", "F45.mdot", v)
                if ms is not None and not (fnum_(val["mdot_min_kgps"]) >= -Em * ms):
                    bad["NN-P-02"].append("mdot_min_kgps")
            for c, b in bad.items():
                res[c][impl].append({"vector": v["id"], "ok": not b, "violations": b[:10]})
        if e in ("plenum.transient_run", "plenum.transient_case") and py_out[v["id"]][0] == "OK" and \
                rres[v["id"]]["outcome"] == "OK" and (e == "plenum.transient_run" or v["id"] in IMG):
            imgs = diag_images(v)
            img_check.append({"vector": v["id"], "ok": all(r["base_equals_reported"] for r in imgs)})
    out = {}
    for c, d in res.items():
        r_ = d["rust"]
        out[c] = {"n": len(r_), "n_fail": sum(1 for x in r_ if not x["ok"]), "ok": all(x["ok"] for x in r_),
                  "failures": [x for x in r_ if not x["ok"]][:20],
                  "python_recorded": {"n": len(d["python"]), "n_fail": sum(1 for x in d["python"] if not x["ok"]),
                                      "failures": [x for x in d["python"] if not x["ok"]][:20]}}
    out["IMG-CHECK (f(y) equals the Python reported diagnostic)"] = {
        "n": len(img_check), "ok": all(x["ok"] for x in img_check),
        "failures": [x for x in img_check if not x["ok"]][:20]}
    return out


def transient_v7_summary(vectors, py_out, rres) -> dict:
    """Report section of contract v7: strata, class agreement, reported-not-scored leaves by category, the unstable
    stratum against the converged reference (with the Python nominal error, DIV-P-REF-01 evidence) and the frozen
    non-vacuity check."""
    strata = {}
    for v in vectors:
        if v["entry"] in TRANSIENT_ENTRIES:
            k = f"{V3_CODE[v['entry']]}/{level_of(v)}/{cls_of(v)['class']}"
            strata[k] = strata.get(k, 0) + 1
    cls_rows = []
    for v in vectors:
        if v["entry"] != "plenum.stability_class":
            continue
        po, rr = py_out[v["id"]], rres[v["id"]]
        pc = po[1]["class"] if po[0] == "OK" else ("ERROR", po[1])
        rc = rr["value"]["class"] if rr["outcome"] == "OK" else ("ERROR", rr.get("error_class"))
        pk = [e["eq"] for e in po[1]["events"]] if po[0] == "OK" else None
        rk = [e["eq"] for e in rr["value"]["events"]] if rr["outcome"] == "OK" else None
        cls_rows.append({"vector": v["id"], "python": pc, "rust": rc, "equal": pc == rc and pk == rk})
    by_cat = {}
    rep_rows = []
    seen = set()
    vmap = {v["id"]: v for v in vectors}
    for x in REPORTED:
        key_ = (x["vector"], x["path"], x["category"])
        if key_ in seen:
            continue
        seen.add(key_)
        v = vmap[x["vector"]]
        c = by_cat.setdefault(x["category"], {})
        c[v["entry"]] = c.get(v["entry"], 0) + 1
        pth = parse_path(x["path"])
        pv = get_path(py_out[v["id"]][1], pth) if py_out[v["id"]][0] == "OK" else None
        rv = get_path(rres[v["id"]]["value"], pth) if rres[v["id"]]["outcome"] == "OK" else None
        rep_rows.append(dict(x, python=pv, rust=rv))
    unstable = []
    for v in vectors:
        if v["entry"] not in TRANSIENT_ENTRIES or cls_of(v)["class"] != "U" or v["id"] not in PYU:
            continue
        runs = PYU[v["id"]]
        rr = rres[v["id"]]
        row = {"vector": v["id"], "python_outcomes": {r: runs[r][0] for r in runs},
               "rust_outcome": rr["outcome"], "families": {}}
        if all(runs[r][0] == "OK" for r in runs) and rr["outcome"] == "OK":
            e = v["entry"]
            Lp = {r: family_leaves(e, runs[r][1]) for r in runs}
            Lr = family_leaves(e, rr["value"])
            for fam, d in Lp["T2"].items():
                f = row["families"].setdefault(fam, {"n_scored": 0, "n_not_convergent": 0, "max_rust_N_vs_py_T2": 0.0,
                                                     "max_python_N_vs_py_T2 (DIV-P-REF-01)": 0.0, "bound": None})
                f["bound"] = bound_of(v, level_of(v), V3_CODE[e], fam)
                for pth, x2 in d.items():
                    if is_closing_xo(v, pth):
                        continue
                    xN, x1 = Lp["N"].get(fam, {}).get(pth), Lp["T1"].get(fam, {}).get(pth)
                    if xN is None or x1 is None or rho_nc(xN, x1, x2):
                        f["n_not_convergent"] += 1
                        continue
                    sc = family_scale_v7(v, fam, x2)
                    y = Lr.get(fam, {}).get(pth)
                    if not sc or y is None:
                        continue
                    f["n_scored"] += 1
                    f["max_rust_N_vs_py_T2"] = max(f["max_rust_N_vs_py_T2"], abs(y - x2) / sc)
                    f["max_python_N_vs_py_T2 (DIV-P-REF-01)"] = max(f["max_python_N_vs_py_T2 (DIV-P-REF-01)"],
                                                                   abs(xN - x2) / sc)
            if e == "plenum.orbit_sim":
                row["P_dev_max_frac"] = {"python_N": runs["N"][1].get("P_dev_max_frac"),
                                         "python_T1": runs["T1"][1].get("P_dev_max_frac"),
                                         "python_T2": runs["T2"][1].get("P_dev_max_frac"),
                                         "rust_N": rr["value"].get("P_dev_max_frac")}
        unstable.append(row)
    nv = ENV.get("checks", {}).get("NON_VACUITY", {})
    return {"strata_scored": strata,
            "class_agreement": {"n": len(cls_rows), "n_disagree": sum(1 for x in cls_rows if not x["equal"]),
                                "disagreements": [x for x in cls_rows if not x["equal"]]},
            "reported_not_scored": {"counts": by_cat, "rows_first_300": rep_rows[:300]},
            "unstable_stratum (scored against the converged reference, DIV-P-REF-01)": unstable,
            "non_vacuity (frozen record)": {"ok": nv.get("ok"), "rows": nv.get("rows")},
            "divergence_record": "docs/rust_migration/contracts/C-ABEP_SIM_DESIGN_PLENUM_FEED_PY/"
                                 "div_p_ref_01_lsoda_unstable_loops.json"}


def transient_v3_summary(t, vectors):
    """Per family / image: the largest fraction of the allowed bound used, and the diagnostic conditioning."""
    fams = [o for o in t.obs.values() if o["tolerance_class"] == "CONVERGENCE_ENVELOPE"]
    cond = []
    for v in vectors:
        for k, r in enumerate(IMG.get(v["id"], [])):
            for n in V3_DIAG:
                cond.append({"vector": v["id"], "segment": k, "quantity": n, "f": r[n]["f"], "W": r[n]["W"],
                             "kappa": r[n]["kappa"], "W_round": r[n]["W_round"], "kappa_round": r[n]["kappa_round"],
                             "scored": n not in V5_CASCADE or CONTRACT_VERSION["plenum"] < 5})
    kap = [c["kappa"] for c in cond]
    kr = [c["kappa_round"] for c in cond]
    return {"families": [{k: o.get(k) for k in ("entry", "observable", "n", "n_fail", "max_abs_diff", "max_rel_diff",
                                               "max_used_frac", "family")} for o in fams],
            "diagnostic_conditioning": {
                "n": len(cond), "n_kappa_le_1e2": sum(1 for x in kap if x <= 1e2),
                "n_kappa_gt_1e6": sum(1 for x in kap if x > 1e6), "n_kappa_inf": sum(1 for x in kap if math.isinf(x)),
                "n_kappa_round_gt_1e6 (computed digits rounding noise)": sum(1 for x in kr if x > 1e6),
                "largest_20": sorted(cond, key=lambda c: -c["kappa"] if math.isfinite(c["kappa"]) else -math.inf)[:20],
                "all": cond}}


# ------------------------------------------------------------------------------------------------ contract v7
# transient_convergence_procedure_v7: input-only stability class, strata S / U / R, stratified draws, closing-valve
# xO extrema reported, unstable stratum scored against the converged reference (DIV-P-REF-01), non-vacuity check.
CLS: dict = {}          # vector id -> Python class record (reference Jacobian, numpy)
PYU: dict = {}          # U vector id -> {"N", "T1", "T2"} Python reference outcomes (comparison target: T2)
REPORTED: list = []     # v7 reported-not-scored leaves: {vector, path, category}


def v7_on() -> bool:
    return CONTRACT_VERSION["plenum"] >= 7


def v7_spec() -> dict:
    return load_contract("plenum")[0]["transient_convergence_procedure_v7"]


def _py_equilibrium(tr_, intake, setpoint, density, feed_factor, ev):
    """One equilibrium of the v7 stability class (the same steps as abep_gaspath TransientRun::event_equilibrium)."""
    co = pf.Chain(intake, tr_.filt, tr_.plant, tr_.plenum).node_coefficients(density)
    leak_d, fc_d = dict(zip(SPECIES, tr_.leak)), dict(zip(SPECIES, tr_.fc))
    a, _, _, ok = pf.area_for_pressure(co, setpoint, tr_.k_rec, leak_d, fc_d)
    if not bool(ok):
        return {"eq": "CLOSING", "re_max": None}
    u = float(a) / (tr_.a_max * feed_factor)
    if u > 1.0:
        return {"eq": "SAT_OPEN", "re_max": None}
    p3, _ = pf.solve_pressures(co, float(a), tr_.k_rec, leak_d, fc_d)
    i_int = (u / tr_.u_ff - 1.0) * tr_.ctrl.Ti_s / tr_.ctrl.Kp
    y = [float(p3[s]) / tr_.r0 for s in SPECIES] + [u, i_int, 0.0, 0.0, 0.0]
    _, jac = tr_._make(ev)
    lam = np.linalg.eigvals(np.asarray(jac(0.0, y), dtype=float)[:5, :5])
    return {"eq": "UNSAT", "re_max": float(max(lam.real))}


def stability_class_of(entry: str, a: dict) -> dict:
    """transient_convergence_procedure_v7.stability_class (Python side): P42 / P43 the equilibrium of every event of
    the fixed sequence; P45 the orbit event's quasi-static equilibria at density 1 + A sin(2 pi k / 24), k = 0..23.
    U: an UNSAT equilibrium has an eigenvalue with Re lambda > 0; R: refused (dead-head ValueError at the design
    setpoint; P45 also no steady start); S otherwise."""
    fc, pl, pn, ct = py_filter_case(a["filter"]), py_plant(a["plant"]), py_plenum_obj(a["plenum"]), \
        py_controller(a["controller"])
    refused = {"class": "R", "events": []}
    orbit = entry == "plenum.orbit_sim" or "state" in a
    des = py_intake_state(a["design"] if orbit else a["intake"])
    try:
        tr_ = pf.TransientRun(fc, pl, pn, ct, des, a["r0"])
    except ValueError:
        return refused
    if orbit:
        st = py_intake_state(a["state"])
        y0, u_ss = tr_.steady_start(st, a["r0"])
        if y0 is None or u_ss > 1.0:
            return refused
        T = pf.orbital_period_s(st.alt_km)
        ev = pf.Event(f"O_{st.state}", "orbit", T, a["r0"], 1.0, st, a["amplitude"], T)
        evs = [_py_equilibrium(tr_, st, a["r0"], 1.0 + a["amplitude"] * math.sin(2.0 * math.pi * k / 24), 1.0, ev)
               for k in range(24)]
    else:
        evs = [_py_equilibrium(tr_, x.intake, x.setpoint_Pa, x.density, x.feed_factor, x)
               for x in pf.event_sequence(des, a["r0"], a["window_s"])]
    unstable = any(x["eq"] == "UNSAT" and x["re_max"] > 0.0 for x in evs)
    return {"class": "U" if unstable else "S", "events": evs}


def cls_of(v) -> dict:
    if v["id"] not in CLS:
        CLS[v["id"]] = stability_class_of(v["entry"], v["args"])
    return CLS[v["id"]]


def closing_segments(v) -> set:
    """closing_valve_xO: segment k is a closing-valve segment when event k or event k - 1 has no reachable unsaturated
    equilibrium because the valve closes (CLOSING); the valve starts event k + 1 shut."""
    ks = [k for k, x in enumerate(cls_of(v)["events"]) if x["eq"] == "CLOSING"]
    return set(ks) | {k + 1 for k in ks}


def is_closing_xo(v, path) -> bool:
    """P43 xO extrema of a closing-valve segment (metrics[k].xO_min / xO_max) and the summary xO_flow_min / max of a
    vector with any closing-valve segment: reported, not scored (sign of a rounding-level valve opening)."""
    if v["entry"] != "plenum.transient_case" or not path:
        return False
    keys = keys_of(path)
    if keys in (("metrics", "xO_min"), ("metrics", "xO_max")):
        return isinstance(path[1], int) and path[1] in closing_segments(v)
    if keys in (("summary", "xO_flow_min"), ("summary", "xO_flow_max")):
        return bool(closing_segments(v))
    return False


def _is_container(x) -> bool:
    return isinstance(x, (dict, list))


def rho_nc(xn, x1, x2) -> bool:
    """not_convergent_reference for a float leaf of the Python reference: rho = |x_T1 - x_T2| / |x_N - x_T1| >= 1/2,
    with the floating allowance f = max(4 ulp(x_T2), 1e-9 |x_T2|): |x_N - x_T1| <= f and |x_T1 - x_T2| <= f is
    convergent (no change), |x_N - x_T1| <= f < |x_T1 - x_T2| is not."""
    fl = max(4.0 * math.ulp(x2), 1e-9 * abs(x2))
    a_, b_ = abs(xn - x1), abs(x1 - x2)
    if a_ <= fl:
        return b_ > fl
    return b_ / a_ >= V7_RHO_LIMIT


V7_RHO_LIMIT = 0.5


def nc_leaf(v, path) -> bool:
    """U stratum: a leaf of the Python reference that is not convergent (float: rho_nc; discrete: T1 != T2; any leaf
    missing or of another type in N / T1 / T2)."""
    runs = PYU.get(v["id"])
    if runs is None:
        return False
    vals = []
    for r in ("N", "T1", "T2"):
        o = runs[r]
        if o[0] != "OK":
            return True
        vals.append(get_path(o[1], path) if path else o[1])
    if any(_is_container(x) for x in vals):
        return False
    xn, x1, x2 = vals
    if all(isinstance(x, float) for x in (xn, x1, x2)) and all(math.isfinite(x) for x in (xn, x1, x2)):
        return rho_nc(xn, x1, x2)
    return not exact_equal(x1, x2)      # discrete / non-finite leaves on their JSON form ("NaN" == "NaN")


def skip_v7(entry, path, v) -> bool:
    """v7 reported-not-scored leaves (recorded with their category): closing-valve xO extrema (S and U) and, in the
    U stratum, leaves whose Python reference is not convergent (NOT_CONVERGENT_REFERENCE)."""
    if skip_plenum(entry, path):
        return True
    if v is None or entry not in TRANSIENT_ENTRIES or not path:
        return False
    if is_closing_xo(v, path):
        REPORTED.append({"vector": v["id"], "path": "/".join(map(str, path)), "category": "CLOSING_VALVE_XO"})
        return True
    if cls_of(v)["class"] == "U" and nc_leaf(v, path):
        REPORTED.append({"vector": v["id"], "path": "/".join(map(str, path)),
                         "category": "NOT_CONVERGENT_REFERENCE"})
        return True
    return False


def stratum_of(v) -> str:
    return cls_of(v)["class"] if v is not None and v.get("entry") in TRANSIENT_ENTRIES else "S"


def bound_of(v, level, code, fam):
    """The frozen v7 bound of the vector's stratum (family units): S: E_py^S + E_rust^S; U: E_rust^U + D_py^U."""
    st = "U" if stratum_of(v) == "U" else "S"
    return ENV["bounds"].get(st, {}).get(level, {}).get(code, {}).get(fam)


def own_env_v7(impl, v, level, code, fam):
    """Own-implementation envelope of the vector's stratum (NN / VS integrity checks): S E_impl^S; U: rust E_rust^U,
    python (its T2 is the compared output) D_py^U."""
    st = "U" if stratum_of(v) == "U" else "S"
    key = impl if st == "S" else ("rust" if impl == "rust" else "python_T1_T2")
    e = ENV["envelopes"].get(st, {}).get(key, {}).get(level, {}).get(code, {}).get(fam)
    return None if e is None else e["E"]


def family_scale_v7(v, fam, ref_value):
    """Registered family scale; in the U stratum F45.P_dev is scored relative to the converged reference (|py_T2|)."""
    if fam in V7_RELATIVE_U and stratum_of(v) == "U":
        return abs(ref_value) if isinstance(ref_value, float) and math.isfinite(ref_value) and ref_value else None
    return family_scale(V3_SCALE[fam], v, ref_value)


V7_RELATIVE_U = ("F45.P_dev",)


def py_plenum_v7(v):
    """Python reference of a scored vector; a U transient vector is compared with its converged T2 run (DIV-P-REF-01):
    N, T1 and T2 are evaluated in that order (the instrumentation keeps the T2 run) and recorded."""
    if v["entry"] in TRANSIENT_ENTRIES and cls_of(v)["class"] == "U":
        lv = v7_spec()["levels_from"]
        levels = load_contract("plenum")[0][lv]["tolerance_levels"][level_of(v)]
        runs = {"N": py_plenum(v), "T1": py_run_rtol(v, levels["T1_rtol"]), "T2": py_run_rtol(v, levels["T2_rtol"])}
        PYU[v["id"]] = runs
        return runs["T2"]
    if v["entry"] == "plenum.stability_class":
        return py_call(lambda: stability_class_of(v["entry"], v["args"]))
    return py_plenum(v)


def stratified_draw(master, e_idx, entry, sizes, prefix, max_candidates):
    """stratified_draws: per level a candidate stream default_rng(SeedSequence([master, entry_index, level_index]))
    (level_index 0 PROD, 1 REF) of the v1 generator; each candidate is classified (input-only, Python reference
    Jacobian) and accepted while its stratum is not full; ids <prefix><entry_index>-<level>-<class>-<nnn>."""
    out, stats = [], {}
    for li, lvl in enumerate(("PROD", "REF")):
        sz = sizes.get(lvl)
        if not sz:
            continue
        g = np.random.default_rng(np.random.SeedSequence([master, e_idx, li]))
        cnt = {k: 0 for k in sz}
        seen = {"S": 0, "U": 0, "R": 0}
        n = 0
        while any(cnt[k] < sz[k] for k in sz):
            n += 1
            if n > max_candidates:
                raise RuntimeError(f"stratified draw {prefix}{e_idx} {lvl}: strata not filled in {max_candidates}")
            args = gen_orbit_sim_args(g) if entry == "plenum.orbit_sim" else gen_transient_args(g, entry, lvl == "REF")
            c = stability_class_of(entry, args)
            seen[c["class"]] += 1
            k = c["class"]
            if k in sz and cnt[k] < sz[k]:
                vid = f"{prefix}{e_idx}-{lvl}-{k}-{cnt[k]:03d}"
                out.append({"id": vid, "entry": entry, "args": args})
                CLS[vid] = c
                cnt[k] += 1
        stats[lvl] = {"candidates": n, "classes_seen": seen, "accepted": cnt}
    return out, stats


def _py3_worker(item):
    v, rts = item
    _CUR["vid"] = v["id"]
    return v["id"], {r: py_run_rtol(v, rt) for r, rt in rts.items()}


def run_rust_parallel(reqs, workers=4):
    """Rust requests split over `workers` CLI processes (requests are independent; results merged by id)."""
    from concurrent.futures import ThreadPoolExecutor
    chunks = [reqs[i::workers] for i in range(workers)]
    with ThreadPoolExecutor(workers) as ex:
        outs = list(ex.map(lambda ch: run_rust(ch)[0] if ch else {"results": []}, chunks))
    return {"results": [x for o in outs for x in o["results"]]}


def py_runs_parallel(vectors, rts, workers=4):
    """The refinement's Python reference runs in a fork pool (each run is independent and deterministic)."""
    import multiprocessing as mp
    with mp.get_context("fork").Pool(workers) as p:
        return dict(p.imap_unordered(_py3_worker, [(v, rts[v["id"]]) for v in vectors], chunksize=2))


V7_RANGE_FAMILIES = ("F42.p", "F42.mdot", "F42.u", "F42.xO", "F42.ucmd_end", "F43.p", "F43.mdot", "F43.u", "F43.xO",
                     "F43.setpoint_frac", "F43.valve_travel", "F45.mdot")
V7_MAGNITUDE_FAMILIES = ("F42.throughput", "F43.overshoot", "F43.valve_travel_total", "F45.P_dev")


def refine_plenum_v7(dev_out=None, dev_sizes=None, dev_master=None):
    """transient_convergence_procedure_v7 refinement: stratified refinement grid (S, U), six runs per vector, S and U
    envelopes, closing-valve xO record, the non-vacuity check, the frozen record (once)."""
    contract, csha, cpath = load_contract("plenum")
    spec = contract["transient_convergence_procedure_v7"]
    proc = contract[spec["levels_from"]]
    seeds = contract["campaign_seeds"]
    if dev_out is None:
        rec_path = os.path.join(ROOT, spec["record"])
        if os.path.exists(rec_path):
            sys.exit(f"REFUSED: {rec_path} exists; the refinement grid is run once and frozen")
        dirty = git("status", "--porcelain", "--", "crates", "Cargo.toml", "Cargo.lock", "rust-toolchain.toml",
                    "scripts/rust_migration")
        if dirty:
            sys.exit("REFUSED: uncommitted Rust / harness sources:\n" + dirty)
        master, sizes, mode = seeds["refinement_master_seed"], spec["stratified_draws"]["refinement"], \
            "REFINEMENT_FROZEN"
    else:
        rec_path = os.path.abspath(dev_out)
        if rec_path.startswith(CDIR):
            sys.exit("a development draft must not be written into the contract directory")
        master, sizes, mode = dev_master, dev_sizes, "DEVELOPMENT_DRAFT_NOT_FROZEN"
    changed = [f["path"] for f in contract["reference_implementation"]["files"]
               if sha_file(os.path.join(ROOT, f["path"])) != f["sha256_at_registration"]]
    if changed:
        sys.exit(f"REFUSED_REFERENCE_CHANGED: {changed}")
    build_rust()
    fam_scale = v3_families()
    V3_SCALE.clear()
    V3_SCALE.update(fam_scale)
    levels = proc["tolerance_levels"]
    t0 = time.perf_counter()
    vectors, draw_stats = [], {}
    maxc = spec["stratified_draws"]["max_candidates_per_level"]
    for code, e_idx, entry in (("P42", 42, "plenum.transient_run"), ("P43", 43, "plenum.transient_case"),
                               ("P45", 45, "plenum.orbit_sim")):
        vs, st = stratified_draw(master, e_idx, entry, sizes[code], "R", maxc)
        vectors += vs
        draw_stats[code] = st
    t_draw = time.perf_counter() - t0
    inputs_sha = hashlib.sha256(json.dumps(vectors, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    lv = {v["id"]: level_of(v) for v in vectors}
    runs = ("N", "T1", "T2")
    rt = {v["id"]: {"N": None, "T1": levels[lv[v["id"]]]["T1_rtol"], "T2": levels[lv[v["id"]]]["T2_rtol"]}
          for v in vectors}
    t0 = time.perf_counter()
    py = py_runs_parallel(vectors, rt)
    t_py = time.perf_counter() - t0
    t0 = time.perf_counter()
    rs_ = {v["id"]: {} for v in vectors}
    for r in runs:
        out = run_rust_parallel([rust_req_rtol(v, rt[v["id"]][r]) for v in vectors])
        for x in out["results"]:
            rs_[x["id"]][r] = rust_outcome(x)
    p45 = [v for v in vectors if v["entry"] == "plenum.orbit_sim"]
    lib, raw_lib, _, _ = run_rust([rust_req_rtol(v, None) for v in p45])
    comp, _, _, _ = run_rust([rust_req_rtol(v, pf.RTOL) for v in p45])
    comp_ok = [json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
               for a, b in zip(lib["results"], comp["results"])]
    cl_out, _, _, _ = run_rust([{"id": v["id"], "entry": "plenum.stability_class", "args": v["args"]}
                                for v in vectors])
    cls_dis = []
    for x in cl_out["results"]:
        pyc = CLS[x["id"]]
        ok_ = x["outcome"] == "OK" and x["value"]["class"] == pyc["class"] and \
            [e["eq"] for e in x["value"]["events"]] == [e["eq"] for e in pyc["events"]]
        if not ok_:
            cls_dis.append({"vector": x["id"], "python": pyc["class"], "rust": x.get("value", {}).get("class")})
    t_rs = time.perf_counter() - t0
    # ---- estimators
    envS = {"python": {}, "rust": {}}
    envU = {"rust": {}, "python_T1_T2": {}, "python_nominal (DIV-P-REF-01 evidence, not used)": {}}
    excluded = {"python": [], "rust": []}
    nc_count, closing = {}, {}
    sig_leaves = {}         # (stratum, lvl, code, fam) -> per vector list of converged py_T2 values (family units)

    def upd(store, lvl, code, fam, ev, vid, pth, vals):
        a = store.setdefault(lvl, {}).setdefault(code, {}).setdefault(
            fam, {"E": None, "n_leaves": 0, "vectors": set(), "argmax": None})
        a["n_leaves"] += 1
        a["vectors"].add(vid)
        if a["E"] is None or ev > a["E"]:
            a["E"] = ev
            a["argmax"] = dict({"vector": vid, "path": "/".join(map(str, pth))}, **vals)
    for v in vectors:
        vid, e, lvl, code = v["id"], v["entry"], lv[v["id"]], V3_CODE[v["entry"]]
        st = CLS[vid]["class"]
        okp = all(run_ok(e, py[vid][r]) for r in runs)
        okr = all(run_ok(e, rs_[vid][r]) for r in runs)
        if not okp:
            excluded["python"].append({"vector": vid, "stratum": st})
        if not okr:
            excluded["rust"].append({"vector": vid, "stratum": st})
        Lp = {r: family_leaves(e, py[vid][r][1]) for r in runs} if okp else None
        Lr = {r: family_leaves(e, rs_[vid][r][1]) for r in runs} if okr else None
        per_vec = {}
        if st == "S":
            for impl, L in (("python", Lp), ("rust", Lr)):
                if L is None:
                    continue
                if {f: set(d) for f, d in L["N"].items()} != {f: set(d) for f, d in L["T2"].items()} or \
                        {f: set(d) for f, d in L["T1"].items()} != {f: set(d) for f, d in L["T2"].items()}:
                    excluded[impl].append({"vector": vid, "stratum": st, "why": "structure differs from T2"})
                    continue
                for fam, d in L["T2"].items():
                    for pth, x2 in d.items():
                        if is_closing_xo(v, pth):
                            c = closing.setdefault(lvl, {"n": 0, "max_e": {}, "max_cross_T2": 0.0, "argmax": None})
                            c["n"] += 1
                            ee = abs(L["N"][fam][pth] - x2) + abs(L["T1"][fam][pth] - x2)
                            c["max_e"][impl] = max(c["max_e"].get(impl, 0.0), ee)
                            continue
                        s = family_scale(fam_scale[fam], v, x2)
                        if not s:
                            continue
                        xN, x1 = L["N"][fam][pth], L["T1"][fam][pth]
                        upd(envS[impl], lvl, code, fam, (abs(xN - x2) + abs(x1 - x2)) / s, vid, pth,
                            {"N": xN, "T1": x1, "T2": x2, "scale": s})
                        if impl == "python":
                            per_vec.setdefault(fam, []).append(x2 / s)
            if Lp is not None and Lr is not None:
                for fam, d in Lp["T2"].items():
                    for pth, x2 in d.items():
                        y2 = Lr["T2"].get(fam, {}).get(pth)
                        if y2 is not None and is_closing_xo(v, pth):
                            c = closing[lvl]
                            if abs(x2 - y2) > c["max_cross_T2"]:
                                c["max_cross_T2"] = abs(x2 - y2)
                                c["argmax"] = {"vector": vid, "path": "/".join(map(str, pth)), "python_T2": x2,
                                               "rust_T2": y2}
        elif st == "U" and Lp is not None:
            PYU[vid] = py[vid]
            for fam, d in Lp["T2"].items():
                for pth, x2 in d.items():
                    if is_closing_xo(v, pth):
                        continue
                    xN, x1 = Lp["N"].get(fam, {}).get(pth), Lp["T1"].get(fam, {}).get(pth)
                    cnt = nc_count.setdefault(f"{lvl}/{code}/{fam}", {"scored": 0, "not_convergent": 0})
                    if xN is None or x1 is None or rho_nc(xN, x1, x2):
                        cnt["not_convergent"] += 1
                        continue
                    s = abs(x2) if fam in V7_RELATIVE_U else family_scale(fam_scale[fam], v, x2)
                    if not s:
                        continue
                    cnt["scored"] += 1
                    upd(envU["python_T1_T2"], lvl, code, fam, abs(x1 - x2) / s, vid, pth, {"T1": x1, "T2": x2,
                                                                                         "scale": s})
                    upd(envU["python_nominal (DIV-P-REF-01 evidence, not used)"], lvl, code, fam,
                        (abs(xN - x2) + abs(x1 - x2)) / s, vid, pth, {"N": xN, "T1": x1, "T2": x2, "scale": s})
                    per_vec.setdefault(fam, []).append(x2 / s)
                    if Lr is not None:
                        yN, y1, y2 = (Lr[r].get(fam, {}).get(pth) for r in runs)
                        if None not in (yN, y1, y2):
                            upd(envU["rust"], lvl, code, fam, (abs(yN - y2) + abs(y1 - y2)) / s, vid, pth,
                                {"N": yN, "T1": y1, "T2": y2, "python_T2": x2, "scale": s})
        for fam, xs in per_vec.items():
            sig_leaves.setdefault((st, lvl, code, fam), []).append(xs)

    def fin(store):
        for lvl_, codes in store.items():
            for code_, fams in codes.items():
                for fam_, a in fams.items():
                    a["n_vectors"] = len(a.pop("vectors"))
                    a["status"] = "EVALUATED" if a["E"] is not None else "NOT_EVALUATED"
    for x in list(envS.values()) + list(envU.values()):
        fin(x)
    bounds = {"S": {}, "U": {}}
    needed = spec["needed_envelopes"]
    missing = []
    for st, codes_by_lvl in needed.items():
        for lvl, codes in codes_by_lvl.items():
            for code in codes:
                for fam in [f for f in fam_scale if f.startswith("F" + code[1:])]:
                    if st == "S":
                        a = envS["python"].get(lvl, {}).get(code, {}).get(fam, {}).get("E")
                        b = envS["rust"].get(lvl, {}).get(code, {}).get(fam, {}).get("E")
                    else:
                        a = envU["rust"].get(lvl, {}).get(code, {}).get(fam, {}).get("E")
                        b = envU["python_T1_T2"].get(lvl, {}).get(code, {}).get(fam, {}).get("E")
                    if a is None or b is None:
                        missing.append(f"{st}/{lvl}/{code}/{fam}")
                        continue
                    bounds[st].setdefault(lvl, {}).setdefault(code, {})[fam] = a + b
    # ---- non-vacuity (step: before any held-out vector): bound < comparison scale, per stratum / level / family
    nv_rows = []
    for st, codes_by_lvl in needed.items():
        for lvl, codes in codes_by_lvl.items():
            for code in codes:
                for fam in [f for f in fam_scale if f.startswith("F" + code[1:])]:
                    B = bounds[st].get(lvl, {}).get(code, {}).get(fam)
                    per_v = sig_leaves.get((st, lvl, code, fam), [])
                    if st == "U" and fam in V7_RELATIVE_U:
                        sigma, kind = 1.0, "relative: bound x |py_T2| < |py_T2| for every U refinement vector"
                    elif fam in V7_MAGNITUDE_FAMILIES:
                        flat = [abs(x) for xs in per_v for x in xs]
                        sigma = float(np.median(flat)) if flat else None
                        kind = "median |converged value| over the stratum's refinement leaves"
                    else:
                        rngs = [max(xs) - min(xs) for xs in per_v if len(xs) >= 2]
                        sigma = float(np.median(rngs)) if rngs else None
                        kind = "median within-vector range of the converged values over the stratum's refinement " \
                               "vectors with >= 2 leaves"
                    ok_ = B is not None and sigma is not None and B < sigma
                    nv_rows.append({"stratum": st, "level": lvl, "entry": code, "family": fam, "bound": B,
                                    "comparison_scale": sigma, "scale_kind": kind, "ok": ok_,
                                    "n_vectors": len(per_v)})
    nv_ok = all(r["ok"] for r in nv_rows)
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rec = {
        "schema": "abep_plenum_transient_envelope_v7",
        "mode": mode,
        "contract": {"id": contract["id"], "path": os.path.relpath(cpath, ROOT), "sha256": csha,
                     "registration_commit": git("log", "-n1", "--format=%H", "--", os.path.relpath(cpath, ROOT))},
        "procedure": "transient_convergence_procedure_v7 (A9.31 sec. 5 estimator per stratum): S: e = (|x_N - x_T2| + "
                     "|x_T1 - x_T2|) / s_F per implementation, bound E_py^S + E_rust^S; U: E_rust^U (Rust "
                     "estimator) + D_py^U (max |x_T1 - x_T2| / s_F of the Python reference) over leaves whose "
                     "reference is convergent (rho < 1/2); no multiplier",
        "date_utc": now,
        "master_seed": master,
        "strata_sizes": sizes,
        "draw_statistics": draw_stats,
        "n_vectors": len(vectors),
        "inputs_sha256": inputs_sha,
        "python_commit": contract["reference_implementation"]["python_commit"],
        "reference_sha256_at_run": {f["path"]: sha_file(os.path.join(ROOT, f["path"]))
                                    for f in contract["reference_implementation"]["files"]},
        "head_commit": git("rev-parse", "HEAD"),
        "build_provenance": provenance(contract),
        "environment": dict(environment(), python_workers=4),
        "tolerance_levels": levels,
        "envelopes": {"S": envS, "U": envU},
        "bounds": bounds,
        "missing_envelopes": missing,
        "not_convergent_reference_leaves": nc_count,
        "closing_valve_xO (reported, not scored)": {
            "per_level": closing,
            "known_property": "converged cross-implementation disagreement of an ill-posed observable (the sign of a "
                              "rounding-level valve opening decides which samples have a defined xO); not resolved "
                              "by choosing one value; v6 grid instance R43-REF-809 segment 6 xO_min: Rust 0.51716, "
                              "Python 0.51607 (refinement_v6_p4243_note.md)"},
        "excluded_vectors": {impl: {"n": len(x), "list": x} for impl, x in excluded.items()},
        "class_agreement_refinement (Python reference Jacobian vs Rust, recorded)": {
            "n": len(vectors), "disagreements": cls_dis},
        "checks": {"COMP-P-01": {"n": len(comp_ok), "ok": all(comp_ok) and raw_lib is not None,
                                 "failures": [p45[i]["id"] for i, x in enumerate(comp_ok) if not x]},
                   "no_missing_envelope": not missing,
                   "NON_VACUITY": {"ok": nv_ok and not missing, "rows": nv_rows}},
        "timing_s": {"draw_and_classify": t_draw, "python": t_py, "rust": t_rs},
        "statement": "frozen before any held-out (scoring_master_seed) vector is generated or run; never edited "
                     "after the scoring run" if mode == "REFINEMENT_FROZEN" else
                     "DEVELOPMENT DRAFT (exploration / development seed): never a scoring input",
    }
    rec = sanitize(rec)
    with open(rec_path, "w") as f:
        json.dump(rec, f, indent=1, allow_nan=False)
        f.write("\n")
    with open(os.path.splitext(rec_path)[0] + ".md", "w") as f:
        f.write(render_envelope_md_v7(rec))
    return rec


def render_envelope_md_v7(r):
    L = [f"# Plenum / feed transient envelope record v7 ({r['mode']})", "",
         f"Contract `{r['contract']['path']}` sha256 `{r['contract']['sha256']}` (registered in "
         f"`{(r['contract']['registration_commit'] or '')[:12]}`). Generated from the JSON record next to this file.",
         "", f"* Procedure: {r['procedure']}.",
         f"* Seed {r['master_seed']}; {r['n_vectors']} refinement vectors, strata {json.dumps(r['strata_sizes'])}; "
         f"inputs sha256 `{r['inputs_sha256'][:16]}...`.",
         f"* Python reference commit `{r['python_commit'][:12]}`; code at `{r['head_commit'][:12]}`; "
         f"{r['build_provenance']['rustc']}; Python {r['environment']['python']}, numpy {r['environment']['numpy']}, "
         f"scipy {r['environment']['scipy']}.",
         f"* Checks: COMP-P-01 {r['checks']['COMP-P-01']['ok']}; no missing envelope {r['checks']['no_missing_envelope']}"
         f"; NON_VACUITY {r['checks']['NON_VACUITY']['ok']}; class disagreements (refinement, recorded) "
         f"{len(r['class_agreement_refinement (Python reference Jacobian vs Rust, recorded)']['disagreements'])}.",
         "", "## Draws", ""]
    for code, d in r["draw_statistics"].items():
        for lvl, s in d.items():
            L.append(f"* {code} {lvl}: {s['candidates']} candidates, classes seen {json.dumps(s['classes_seen'])}, "
                     f"accepted {json.dumps(s['accepted'])}")
    L += ["", "## Bounds and non-vacuity (family units; U F45.P_dev relative to the converged reference)", "",
          "| stratum | level | entry | family | bound | comparison scale | ok | vectors |", "|---|---|---|---|---|---|---|---|"]
    for x in r["checks"]["NON_VACUITY"]["rows"]:
        L.append(f"| {x['stratum']} | {x['level']} | {x['entry']} | {x['family']} | {fmt3(x['bound'])} | "
                 f"{fmt3(x['comparison_scale'])} | {'yes' if x['ok'] else '**NO**'} | {x['n_vectors']} |")
    L += ["", "## Envelopes", "", "| stratum | estimator | level | entry | family | E | n leaves | argmax vector |",
          "|---|---|---|---|---|---|---|---|"]
    for st, ests in r["envelopes"].items():
        for est, lvls in ests.items():
            for lvl, codes in lvls.items():
                for code, fams in codes.items():
                    for fam, a in fams.items():
                        L.append(f"| {st} | {est} | {lvl} | {code} | {fam} | {fmt3(a['E'])} | {a['n_leaves']} | "
                                 f"{(a.get('argmax') or {}).get('vector')} |")
    L += ["", "## Not-convergent reference leaves (U stratum)", ""]
    L += [f"* {k}: scored {x['scored']}, NOT_CONVERGENT_REFERENCE {x['not_convergent']}"
          for k, x in sorted(r["not_convergent_reference_leaves"].items())]
    L += ["", "## Closing-valve xO extrema (reported, not scored)", "",
          json.dumps(r["closing_valve_xO (reported, not scored)"], indent=1), "",
          f"Statement: {r['statement']}", ""]
    return "\n".join(L)


# ------------------------------------------------------------------------------------------------ envelope record
def envelope_path(contract) -> str:
    if "transient_convergence_procedure_v7" in contract:
        return os.path.join(ROOT, contract["transient_convergence_procedure_v7"]["record"])
    return os.path.join(ROOT, contract["transient_convergence_procedure_v3"]["step_4_freeze"]["record"])


def load_envelope(contract, contract_sha, mode) -> dict:
    """step_4_freeze: the scoring run reads the committed, unchanged record of this contract; development runs may
    read a development draft (ABEP_PLENUM_ENVELOPE_DEV)."""
    path = envelope_path(contract)
    dev = os.environ.get("ABEP_PLENUM_ENVELOPE_DEV")
    if mode != "score" and dev:
        path = dev
    if not os.path.exists(path):
        sys.exit(f"REFUSED: envelope record {path} missing (run 'refine plenum' first)")
    rec = json.load(open(path))
    meta = {"path": os.path.relpath(path, ROOT) if path.startswith(ROOT) else path, "sha256": sha_file(path)}
    if mode == "score":
        rel = os.path.relpath(path, ROOT)
        if subprocess.run(["git", "ls-files", "--error-unmatch", rel], cwd=ROOT, capture_output=True).returncode:
            sys.exit(f"REFUSED: envelope record {rel} is not committed")
        if git("status", "--porcelain", "--", rel):
            sys.exit(f"REFUSED: envelope record {rel} changed since its commit")
        meta["commit"] = git("log", "-n1", "--format=%H", "--", rel)
        if rec.get("mode") != "REFINEMENT_FROZEN":
            sys.exit("REFUSED: the envelope record is not a frozen refinement record")
    if rec["contract"]["sha256"] != contract_sha:
        sys.exit("REFUSED: the envelope record belongs to another contract version")
    if not rec["checks"]["COMP-P-01"]["ok"]:
        sys.exit("REFUSED: COMP-P-01 failed in the envelope record")
    if v7_on():
        if rec.get("schema") != "abep_plenum_transient_envelope_v7":
            sys.exit("REFUSED: not a v7 envelope record")
        if mode == "score" and not rec["checks"]["NON_VACUITY"]["ok"]:
            sys.exit("REFUSED: NON_VACUITY failed in the frozen record (stop before scoring and report)")
    rec["_meta"] = meta
    return rec


class _RtolDefault:
    """Tightened P45 Python runs: orbit_simulated has no rtol argument, so the default rtol of TransientRun.__init__
    is set in this process for the duration of the call (registered override mechanics; no file is changed)."""

    def __init__(self, rtol):
        self.rtol = rtol

    def __enter__(self):
        self.saved = pf.TransientRun.__init__.__defaults__
        if self.saved != (pf.RTOL, None):
            raise RuntimeError(f"unexpected TransientRun defaults {self.saved}")
        pf.TransientRun.__init__.__defaults__ = (self.rtol, None)

    def __exit__(self, *exc):
        pf.TransientRun.__init__.__defaults__ = self.saved


def refinement_vectors(contract, master, counts) -> list:
    """step_1_refinement_grid: the held-out draw procedure with the registered counts."""
    V = []
    for e_idx, entry in ((42, "plenum.transient_run"), (43, "plenum.transient_case")):
        g = rng(master, e_idx)
        n_p, n_r = counts[f"P{e_idx}"]["PROD"], counts[f"P{e_idx}"]["REF"]
        for i in range(n_p + n_r):
            ref = i >= n_p
            V.append({"id": f"R{e_idx}-{'REF' if ref else 'PROD'}-{i:03d}", "entry": entry,
                      "args": gen_transient_args(g, entry, ref)})
    g = rng(master, 45)
    for i in range(counts["P45"]["PROD"]):
        V.append({"id": f"R45-{i:03d}", "entry": "plenum.orbit_sim", "args": gen_orbit_sim_args(g)})
    return V


def py_run_rtol(v, rtol):
    if rtol is None:
        return py_plenum(v)
    if v["entry"] == "plenum.orbit_sim":
        with _RtolDefault(rtol):
            return py_plenum(v)
    return py_plenum({"id": v["id"], "entry": v["entry"], "args": dict(v["args"], rtol=rtol)})


def rust_req_rtol(v, rtol):
    return {"id": v["id"], "entry": v["entry"], "args": v["args"] if rtol is None else dict(v["args"], rtol=rtol)}


def tree_leaves(x, path=()):
    if isinstance(x, dict):
        for k, w in x.items():
            yield from tree_leaves(w, path + (k,))
    elif isinstance(x, list):
        for i, w in enumerate(x):
            yield from tree_leaves(w, path + (i,))
    else:
        yield path, x


def family_leaves(entry, val) -> dict:
    """family -> {path: finite float} of one run."""
    out = {}
    for path, x in tree_leaves(val):
        fam = V3_FAMILY[entry].get(keys_of(path))
        if fam is not None and isinstance(x, float) and math.isfinite(x):
            out.setdefault(fam, {})[path] = x
    return out


def discrete_leaves(entry, val) -> dict:
    """non-float leaves (statuses, reasons, booleans, None-ness, non-finite strings) and sample-time leaves."""
    out = {}
    for path, x in tree_leaves(val):
        k = keys_of(path)
        if k and k[-1] in ("nfev", "message"):
            continue
        if not isinstance(x, float) or (k in V3_SAMPLE_TIME and k != ("segments", "t")):
            out[path] = x
    return out


def run_ok(entry, out) -> bool:
    if out[0] != "OK" or not isinstance(out[1], dict):
        return False
    val = out[1]
    if entry == "plenum.transient_case":
        return val.get("summary") is not None
    return bool(val.get("ok"))


def refine_plenum(dev_out=None, dev_counts=None):
    """transient_convergence_procedure_v3 steps 1-4: the refinement-grid runs and the frozen envelope record (once).
    dev_out: a development draft from the development seed, written outside the contract directory."""
    contract, csha, cpath = load_contract("plenum")
    proc = contract["transient_convergence_procedure_v3"]
    seeds = contract["campaign_seeds"]
    if dev_out is None:
        rec_path = envelope_path(contract)
        if os.path.exists(rec_path):
            sys.exit(f"REFUSED: {rec_path} exists; the refinement grid is run once and frozen")
        dirty = git("status", "--porcelain", "--", "crates", "Cargo.toml", "Cargo.lock", "rust-toolchain.toml",
                    "scripts/rust_migration")
        if dirty:
            sys.exit("REFUSED: uncommitted Rust / harness sources:\n" + dirty)
        master, counts, mode = seeds["refinement_master_seed"], proc["step_1_refinement_grid"]["counts"], \
            "REFINEMENT_FROZEN"
    else:
        rec_path = os.path.abspath(dev_out)
        if rec_path.startswith(CDIR):
            sys.exit("a development draft must not be written into the contract directory")
        master, counts, mode = seeds["development_master_seed"], dev_counts, "DEVELOPMENT_DRAFT_NOT_FROZEN"
    changed = [f["path"] for f in contract["reference_implementation"]["files"]
               if sha_file(os.path.join(ROOT, f["path"])) != f["sha256_at_registration"]]
    if changed:
        sys.exit(f"REFUSED_REFERENCE_CHANGED: {changed}")
    build_rust()
    fam_scale = v3_families()
    levels = proc["tolerance_levels"]
    vectors = refinement_vectors(contract, master, counts)
    inputs_sha = hashlib.sha256(json.dumps(vectors, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    lv = {v["id"]: level_of(v) for v in vectors}
    runs = ("N", "T1", "T2")
    rt = {v["id"]: {"N": None, "T1": levels[lv[v["id"]]]["T1_rtol"], "T2": levels[lv[v["id"]]]["T2_rtol"]}
          for v in vectors}
    t0 = time.perf_counter()
    py = {v["id"]: {r: py_run_rtol(v, rt[v["id"]][r]) for r in runs} for v in vectors}
    TAP.clear()
    t_py = time.perf_counter() - t0
    t0 = time.perf_counter()
    rs_ = {v["id"]: {} for v in vectors}
    for r in runs:
        out, _, _, _ = run_rust([rust_req_rtol(v, rt[v["id"]][r]) for v in vectors])
        for x in out["results"]:
            rs_[x["id"]][r] = rust_outcome(x)
    # COMP-P-01: the composed P45 path at the nominal rtol equals the library orbit_simulated byte for byte
    p45 = [v for v in vectors if v["entry"] == "plenum.orbit_sim"]
    lib, raw_lib, _, _ = run_rust([rust_req_rtol(v, None) for v in p45])
    comp, raw_comp, _, _ = run_rust([rust_req_rtol(v, pf.RTOL) for v in p45])
    comp_ok = [json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
               for a, b in zip(lib["results"], comp["results"])]
    t_rs = time.perf_counter() - t0
    impl_out = {"python": py, "rust": rs_}
    env = {impl: {} for impl in impl_out}
    excluded = {impl: [] for impl in impl_out}
    discrete = {impl: {"n": 0, "first_50": []} for impl in impl_out}
    conv = {impl: {} for impl in impl_out}
    diag = {impl: {} for impl in impl_out}
    cons = {impl: {} for impl in impl_out}
    skipped_scale = {impl: 0 for impl in impl_out}
    for impl, O in impl_out.items():
        acc = {}
        for v in vectors:
            vid, e, lvl, code = v["id"], v["entry"], lv[v["id"]], V3_CODE[v["entry"]]
            outs = O[vid]
            for r in runs:
                if run_ok(e, outs[r]):
                    val = outs[r][1]
                    m = val["summary"]["mass_residual_rel"] if e == "plenum.transient_case" else val["mass_residual_rel"]
                    c = cons[impl].setdefault(f"{lvl}/{code}/{r}", {"n": 0, "max_mass_residual_rel": 0.0,
                                                                   "n_above_MASS_TOL": 0})
                    c["n"] += 1
                    c["max_mass_residual_rel"] = max(c["max_mass_residual_rel"], unj(m))
                    c["n_above_MASS_TOL"] += unj(m) > pf.MASS_TOL
            oks = [run_ok(e, outs[r]) for r in runs]
            if not all(oks):
                kinds = [outs[r][1] if outs[r][0] == "ERROR" else ("OK" if oks[i] else "NOT_OK")
                         for i, r in enumerate(runs)]
                excluded[impl].append({"vector": vid, "runs": dict(zip(runs, kinds))})
                continue
            vals = {r: outs[r][1] for r in runs}
            dN, dT = discrete_leaves(e, vals["N"]), discrete_leaves(e, vals["T2"])
            for pth in sorted(set(dN) | set(dT), key=str):
                if not exact_equal(dN.get(pth), dT.get(pth)):
                    discrete[impl]["n"] += 1
                    if len(discrete[impl]["first_50"]) < 50:
                        discrete[impl]["first_50"].append({"vector": vid, "path": "/".join(map(str, pth)),
                                                           "N": dN.get(pth), "T2": dT.get(pth)})
            L = {r: family_leaves(e, vals[r]) for r in runs}
            shape = {r: {f: set(d) for f, d in L[r].items()} for r in runs}
            if not (shape["N"] == shape["T1"] == shape["T2"]):
                excluded[impl].append({"vector": vid, "runs": "structure (family leaf set) differs from T2"})
                continue
            for fam in set(L["T2"]) | set(L["N"]):
                a = acc.setdefault((lvl, code, fam), {"E": None, "n_leaves": 0, "vectors": set(), "argmax": None,
                                                      "max_N_T2": 0.0, "max_T1_T2": 0.0})
                for pth, x2 in L["T2"].get(fam, {}).items():
                    xN, x1 = L["N"].get(fam, {}).get(pth), L["T1"].get(fam, {}).get(pth)
                    if xN is None or x1 is None:
                        continue
                    s = family_scale(fam_scale[fam], v, x2)
                    if not s:
                        skipped_scale[impl] += 1
                        continue
                    eN, e1 = abs(xN - x2) / s, abs(x1 - x2) / s
                    ev = eN + e1
                    a["n_leaves"] += 1
                    a["vectors"].add(vid)
                    a["max_N_T2"] = max(a["max_N_T2"], eN)
                    a["max_T1_T2"] = max(a["max_T1_T2"], e1)
                    if a["E"] is None or ev > a["E"]:
                        a["E"] = ev
                        a["argmax"] = {"vector": vid, "path": "/".join(map(str, pth)), "N": xN, "T1": x1, "T2": x2,
                                       "scale": s}
            if e == "plenum.transient_run":
                for k, (sN, s2) in enumerate(zip(vals["N"]["segments"], vals["T2"]["segments"])):
                    ind = unj(s2["K_min"]) >= 1 - pf.K_TOL and unj(s2["K_over_K0_max"]) <= 1 + pf.K_TOL
                    for n in V3_DIAG:
                        a_, b_ = unj(sN[n]), unj(s2[n])
                        rel = abs(a_ - b_) / abs(b_) if b_ not in (0.0,) and math.isfinite(a_) and math.isfinite(b_) \
                            else (0.0 if a_ == b_ else math.inf)
                        dd = diag[impl].setdefault(f"{lvl}/{n}/{'in_domain' if ind else 'out_of_domain'}",
                                                   {"n": 0, "max_rel_N_T2": 0.0})
                        dd["n"] += 1
                        dd["max_rel_N_T2"] = max(dd["max_rel_N_T2"], rel)
        for (lvl, code, fam), a in sorted(acc.items()):
            env[impl].setdefault(lvl, {}).setdefault(code, {})[fam] = {
                "E": a["E"], "status": "EVALUATED" if a["E"] is not None else "NOT_EVALUATED",
                "n_leaves": a["n_leaves"], "n_vectors": len(a["vectors"]), "argmax": a["argmax"],
                "scale": fam_scale[fam]}
            conv[impl][f"{lvl}/{code}/{fam}"] = {"max_N_T2": a["max_N_T2"], "max_T1_T2": a["max_T1_T2"],
                                                 "ratio": a["max_T1_T2"] / a["max_N_T2"] if a["max_N_T2"] else None}
    # model-equivalence diagnostic (development only, not a verdict): converged T2 vs T2 across implementations
    cross = {}
    for v in vectors:
        vid, e, lvl, code = v["id"], v["entry"], lv[v["id"]], V3_CODE[v["entry"]]
        if not (run_ok(e, py[vid]["T2"]) and run_ok(e, rs_[vid]["T2"])):
            continue
        Lp, Lr = family_leaves(e, py[vid]["T2"][1]), family_leaves(e, rs_[vid]["T2"][1])
        for fam, d in Lp.items():
            for pth, x in d.items():
                y = Lr.get(fam, {}).get(pth)
                s = family_scale(fam_scale[fam], v, x)
                if y is None or not s:
                    continue
                c = cross.setdefault(f"{lvl}/{code}/{fam}", {"n": 0, "max": 0.0, "argmax": None})
                c["n"] += 1
                if abs(x - y) / s > c["max"]:
                    c["max"] = abs(x - y) / s
                    c["argmax"] = {"vector": vid, "path": "/".join(map(str, pth)), "python": x, "rust": y}
    combined = {}
    for lvl in ("PROD", "REF"):
        for code in ("P42", "P43", "P45"):
            fams = set(env["python"].get(lvl, {}).get(code, {})) | set(env["rust"].get(lvl, {}).get(code, {}))
            for fam in sorted(fams):
                a = env["python"].get(lvl, {}).get(code, {}).get(fam, {}).get("E")
                b = env["rust"].get(lvl, {}).get(code, {}).get(fam, {}).get("E")
                combined.setdefault(lvl, {}).setdefault(code, {})[fam] = None if a is None or b is None else a + b
    needed = {"PROD": ("P42", "P43", "P45"), "REF": ("P42", "P43")}
    fam_codes = {"P42": [f for f in fam_scale if f.startswith("F42")], "P43": [f for f in fam_scale if
                                                                              f.startswith("F43")],
                 "P45": [f for f in fam_scale if f.startswith("F45")]}
    missing = [f"{impl}/{lvl}/{code}/{fam}" for impl in env for lvl, codes in needed.items() for code in codes
               for fam in fam_codes[code] if env[impl].get(lvl, {}).get(code, {}).get(fam, {}).get("E") is None]
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rec = {
        "schema": "abep_plenum_transient_envelope_v3",
        "mode": mode,
        "contract": {"id": contract["id"], "path": os.path.relpath(cpath, ROOT), "sha256": csha,
                     "registration_commit": git("log", "-n1", "--format=%H", "--", os.path.relpath(cpath, ROOT))},
        "procedure": "transient_convergence_procedure_v3 steps 1-4 (A9.31 sec. 5); estimator "
                     "e = (|x_N - x_T2| + |x_T1 - x_T2|) / s_F, E = max over the grid, no multiplier",
        "date_utc": now,
        "master_seed": master,
        "counts": counts,
        "n_vectors": len(vectors),
        "inputs_sha256": inputs_sha,
        "python_commit": contract["reference_implementation"]["python_commit"],
        "reference_sha256_at_run": {f["path"]: sha_file(os.path.join(ROOT, f["path"]))
                                    for f in contract["reference_implementation"]["files"]},
        "head_commit": git("rev-parse", "HEAD"),
        "build_provenance": provenance(contract),
        "environment": environment(),
        "tolerance_levels": proc["tolerance_levels"],
        "envelopes": env,
        "combined_E_py_plus_E_rust": combined,
        "missing_envelopes": missing,
        "excluded_vectors": {impl: {"n": len(x), "list": x} for impl, x in excluded.items()},
        "skipped_leaves_zero_scale": skipped_scale,
        "discrete_N_vs_T2_differences": discrete,
        "also_recorded_not_used": {
            "cross_implementation_T2_vs_T2 (model-equivalence diagnostic, not a verdict)": cross,
            "convergence_ratio max|T1-T2| / max|N-T2|": conv,
            "segment_cascade_diagnostics_N_vs_T2_relative": diag,
            "CONS-P-03 mass_residual_rel per run": cons},
        "checks": {"COMP-P-01": {"n": len(comp_ok), "ok": all(comp_ok) and raw_lib is not None,
                                 "failures": [p45[i]["id"] for i, x in enumerate(comp_ok) if not x]},
                   "no_missing_envelope": not missing},
        "timing_s": {"python": t_py, "rust": t_rs},
        "statement": "frozen before any held-out (scoring_master_seed) vector is generated or run; never edited "
                     "after the scoring run" if mode == "REFINEMENT_FROZEN" else
                     "DEVELOPMENT DRAFT from the development seed: never a scoring input",
    }
    rec = sanitize(rec)
    with open(rec_path, "w") as f:
        json.dump(rec, f, indent=1, allow_nan=False)
        f.write("\n")
    with open(os.path.splitext(rec_path)[0] + ".md", "w") as f:
        f.write(render_envelope_md(rec))
    return rec


def render_envelope_md(r):
    L = [f"# Plenum / feed transient envelope record v3 ({r['mode']})", "",
         f"Contract `{r['contract']['path']}` sha256 `{r['contract']['sha256']}` (registered in "
         f"`{r['contract']['registration_commit'][:12]}`). Generated from the JSON record next to this file.", "",
         f"* Procedure: {r['procedure']}.",
         f"* Seed {r['master_seed']}; {r['n_vectors']} refinement vectors {json.dumps(r['counts'])}; inputs sha256 "
         f"`{r['inputs_sha256'][:16]}...`.",
         f"* Python reference commit `{r['python_commit'][:12]}`; code at `{r['head_commit'][:12]}`; "
         f"{r['build_provenance']['rustc']}; Python {r['environment']['python']}, numpy {r['environment']['numpy']}, "
         f"scipy {r['environment']['scipy']}.",
         f"* Checks: {json.dumps({k: v.get('ok', v) if isinstance(v, dict) else v for k, v in r['checks'].items()})}; "
         f"missing envelopes: {r['missing_envelopes'] or 'none'}.", "",
         "## Envelopes (normalised by the family scale)", "",
         "| level | entry | family | scale | E python | E rust | combined | n leaves (py / rust) | worst vector (py) |",
         "|---|---|---|---|---|---|---|---|---|"]
    for lvl, codes in r["combined_E_py_plus_E_rust"].items():
        for code, fams in codes.items():
            for fam, comb in fams.items():
                p = r["envelopes"]["python"].get(lvl, {}).get(code, {}).get(fam, {})
                q = r["envelopes"]["rust"].get(lvl, {}).get(code, {}).get(fam, {})
                L.append(f"| {lvl} | {code} | {fam} | {p.get('scale')} | {fmt3(p.get('E'))} | {fmt3(q.get('E'))} | "
                         f"{fmt3(comb)} | {p.get('n_leaves')} / {q.get('n_leaves')} | "
                         f"{(p.get('argmax') or {}).get('vector')} |")
    L += ["", "## Recorded, not used", "", "Converged T2 vs T2 across implementations (model-equivalence diagnostic, "
          "not a verdict), max over the grid in family units:", ""]
    for k, c in r["also_recorded_not_used"]["cross_implementation_T2_vs_T2 (model-equivalence diagnostic, not a "
                                             "verdict)"].items():
        L.append(f"* {k}: {fmt3(c['max'])} (n {c['n']})")
    L += ["", "Convergence ratio max|T1 - T2| / max|N - T2|:", ""]
    for impl, d in r["also_recorded_not_used"]["convergence_ratio max|T1-T2| / max|N-T2|"].items():
        L.append(f"* {impl}: " + "; ".join(f"{k} {fmt3(x['ratio'])}" for k, x in d.items()))
    L += ["", "Segment cascade diagnostics, relative N - T2 difference (ill-conditioning; scored through the "
          "primitive image):", ""]
    for impl, d in r["also_recorded_not_used"]["segment_cascade_diagnostics_N_vs_T2_relative"].items():
        L.append(f"* {impl}: " + "; ".join(f"{k} {fmt3(x['max_rel_N_T2'])} (n {x['n']})" for k, x in d.items()))
    L += ["", "CONS-P-03 (mass residual) per run:", ""]
    for impl, d in r["also_recorded_not_used"]["CONS-P-03 mass_residual_rel per run"].items():
        L.append(f"* {impl}: " + "; ".join(f"{k} max {fmt3(x['max_mass_residual_rel'])} (above MASS_TOL "
                                           f"{x['n_above_MASS_TOL']})" for k, x in d.items()))
    L += ["", "## Excluded vectors and discrete differences", ""]
    for impl in ("python", "rust"):
        L.append(f"* {impl}: {r['excluded_vectors'][impl]['n']} vectors excluded (refused / failed run); "
                 f"{r['discrete_N_vs_T2_differences'][impl]['n']} discrete N-vs-T2 leaf differences; "
                 f"{r['skipped_leaves_zero_scale'][impl]} leaves with zero scale skipped.")
    L += ["", f"Statement: {r['statement']}.", ""]
    return "\n".join(L)


# ======================================================================================================================
# Registry
# ======================================================================================================================
SPEC = {"filter": (vectors_filter, py_filter, rule_filter, checks_filter),
        "compressor": (vectors_compressor, py_compressor, rule_compressor, checks_compressor),
        "plenum": (vectors_plenum, py_plenum_v7 if CONTRACT_VERSION["plenum"] >= 7 else py_plenum, rule_plenum,
                   checks_plenum)}
PROXIMITY = {"plenum": proximity_plenum}
PRE = {"plenum": pre_plenum}
# leaves reported, not scored (integrator / fixed-point statistics; registered in the contracts)
SKIP = {"compressor": lambda entry, path: entry in ITERATIVE and bool(path) and path[-1] == "iterations",
        "plenum": skip_plenum}
PERF = {"filter": [("PERF-F-01", r"F06-R-", "the 600 random F06 apply vectors; Rust = one CLI process incl. JSON")],
        "compressor": [("PERF-C-01", r"C19-G-0$", "synthesize() with the default grid (2160 designs), one inlet"),
                       ("PERF-C-02", r"C02-R-", "the 24 C02 size_for vectors")],
        "plenum": [("PERF-P-01", r"P38-", "the 12 P38 steady sweeps (Rust request also runs the scalar twin)"),
                   ("PERF-P-02", r"P43-PROD-S-" if CONTRACT_VERSION["plenum"] >= 7 else r"P43-PROD-",
                    "the 12 production (v7: stable-stratum) transient_case vectors"),
                   ("PERF-P-03", r"P49-S-", "the 300 P49 Reservoir.steady_state vectors")]}
LEDGER = {"filter": [{"component": "C-ABEP_SIM_DESIGN_FILTER_STAGE_PY", "requested_status": "ADMITTED",
                      "scope": "EV, cole_transmission_probability, perforated_plate_alpha, mean_speed_m_s, "
                               "ProtectionFunction, MaterialApplicability, SpeciesTransport, tbd_species_transport, "
                               "InletState, SensitivityCase, FilterResult (to_dict, species_transmission, to_f3_record, "
                               "to_f1_record), FilterStage (factories, parameters, apply, backflow_coupling, to_dict), "
                               "repository_placeholder_values, placeholder_sensitivity_case, retained_inventory_kg",
                      "authoritative_implementation": "rust: abep_gaspath::filter",
                      "sc_wp_02_gate": "filter species transport TBD -> INCOMPLETE_EVIDENCE (REFUSED_TBD)"}]}
LEDGER["compressor"] = [
    {"component": "C-ABEP_SIM_COMPRESSOR_PY", "requested_status": "ADMITTED",
     "scope": "DragCompressor (whole class: run, _run_once, Gaede domain records, rpm_limit, size_for, u_max, "
              "sizing_mode, ...)", "authoritative_implementation": "rust: abep_gaspath::compressor"},
    {"component": "C-ABEP_SIM_ROTOR_STRENGTH_PY", "requested_status": "ADMITTED",
     "scope": "whole module (REGISTRY as an explicit Registry value, DIV-C-01)",
     "authoritative_implementation": "rust: abep_gaspath::rotor_strength"},
    {"component": "C-ABEP_SIM_DESIGN_COMPRESSOR_SYNTHESIS_PY", "requested_status": "ADMITTED (computational subset, "
     "RM-R17)", "scope": "InletRecord, SearchGrid, material_admission, strict_blockers, validate_coefficient, "
     "validate_design, build_compressor, evaluate_design, stage_trace, drag_knudsen_upper, pareto_front, "
     "is_dominated_by, synthesize, size_for_comparison and the constants",
     "not_ported": "SOURCES, CITED_VALUES, coefficient_registry, search_variables (citation records, carried by the "
                   "committed F3 synthesis record): proposed FROZEN_AS_REFERENCE_EVIDENCE at module retirement",
     "authoritative_implementation": "rust: abep_gaspath::compressor_synthesis"},
    {"component": "SC-WP-02 gate 'compressor load (ICD row 22) not supplied'", "requested_status": "PORTED "
     "(NOT_EVALUATED slot; architecture_optimizer.official_ledger compressor branch only)",
     "authoritative_implementation": "rust: abep_gaspath::compressor_synthesis::compressor_ledger_slot"}]
LEDGER_FAIL = {"filter": [{"component": "C-ABEP_SIM_DESIGN_FILTER_STAGE_PY", "requested_status": "PARITY_FAILED "
                           "(stays PYTHON_REFERENCE; a code fix needs a new contract version with a fresh seed)"}],
               "compressor": [{"component": c, "requested_status": "PARITY_FAILED (stays PYTHON_REFERENCE; a code fix "
                               "needs a new contract version with a fresh seed)"}
                              for c in ("C-ABEP_SIM_COMPRESSOR_PY", "C-ABEP_SIM_ROTOR_STRENGTH_PY",
                                        "C-ABEP_SIM_DESIGN_COMPRESSOR_SYNTHESIS_PY")]}
LEDGER["plenum"] = [
    {"component": "C-ABEP_SIM_DESIGN_PLENUM_FEED_PY", "requested_status": "ADMITTED (computational subset, RM-R17)",
     "scope": "status vocabulary, IntakeState, FilterCase and the filter-case factories, CompressorPlant, Plenum, "
              "Chain, solve_pressures, area_for_pressure, bisection_failed, lambda_upper_m, steady_operating_point, "
              "intake_side, cascade_arrays, steady_sweep, Controller, Event, TransientRun (Rust Radau IIA, DIV-P-01), "
              "settling_time, segment_metrics, ripple_transfer, inlet_node_tau_per_m3, event_sequence, orbit checks, "
              "transient_case, strict_blockers, evaluate, pareto_ids, intake_controller_state, scheduled_operation, "
              "compare_control_modes",
     "not_ported": "parameter_registry / REFERENCES / QUASI_STEADY_NOTE (documentation records); load_f1 / "
                   "f1_state_infeasibility / load_f1_records (F1 readers: lane B2 intake response layer)",
     "authoritative_implementation": "rust: abep_gaspath::{plenum_feed, transient}"},
    {"component": "C-ABEP_SIM_RESERVOIR_PY", "requested_status": "ADMITTED",
     "scope": "Reservoir (conductance, steady_state), size_orifice_for_pressure (report form), startup_transient",
     "authoritative_implementation": "rust: abep_gaspath::reservoir"},
    {"component": "C-ABEP_SIM_DESIGN_UPSTREAM_A9_13_PY", "requested_status": "PARTIAL (A9.13 setpoint / domain / "
     "flow-gap / robust-set rules admitted)",
     "pending": "statewise_envelope / _quantify / reference_drag_fn (SC-WP-04), require_all_admitted_scenarios / "
                "robust_over_scenarios (SC-WP-09), verify_state_set_decision_records, PROPELLANT_POLICY / AIR_PATH / "
                "XE_PATH (SC-WP-12), assessment-layer comparison helpers",
     "authoritative_implementation": "rust: abep_gaspath::upstream"}]
# v2 (scope reduction): the group minus the transient entries P42 / P43, a partial admission of the coupled group
LEDGER_V = {("plenum", 2): [
    {"component": "C-ABEP_SIM_DESIGN_PLENUM_FEED_PY", "requested_status": "PARTIAL_ADMISSION (ADMITTED for the scope "
     "below; the row stays PYTHON_REFERENCE)",
     "scope": "status vocabulary (status_from_reasons, reasons_from_bits, REASON_BITS and the module constants), "
              "orbital_period_s, cbar, kT_over_m, IntakeState, f1_candidate_id, FilterCase and the filter-case "
              "factories (filter_case_from_stage, filter_none / parametric / placeholder, filter_cases), "
              "CompressorPlant, Plenum, Chain, solve_pressures, area_for_pressure, bisection_failed, lambda_upper_m, "
              "steady_operating_point, evaluate, intake_side, cascade_arrays, steady_sweep, settling_time, "
              "segment_metrics, _domain_reasons, ripple_transfer, inlet_node_tau_per_m3, event_sequence, "
              "orbit_quasi_static, orbit_simulated (incl. the TransientRun / Controller it constructs, Rust Radau "
              "IIA, DIV-P-01), strict_blockers, pareto_ids, intake_controller_state, scheduled_operation, "
              "compare_control_modes",
     "excluded_stays_python_reference": "TransientRun.run as a direct entry (P42 transient_run) and transient_case "
                                        "(P43): v1 CONTRACT_DEFECT, transient re-specification is a pending owner "
                                        "decision; they stay PYTHON_REFERENCE until an owner-ruled transient contract "
                                        "exists",
     "not_ported": "parameter_registry / REFERENCES / QUASI_STEADY_NOTE (documentation records); load_f1 / "
                   "f1_state_infeasibility / load_f1_records (F1 readers: lane B2 intake response layer)",
     "authoritative_implementation": "rust: abep_gaspath::{plenum_feed, transient} for the scope above"},
    {"component": "C-ABEP_SIM_RESERVOIR_PY", "requested_status": "ADMITTED (whole registered module; no reservoir entry "
     "is excluded by the v2 scope reduction; part of the coupled group's partial admission)",
     "scope": "Reservoir (conductance, steady_state), size_orifice_for_pressure (report form), startup_transient",
     "authoritative_implementation": "rust: abep_gaspath::reservoir"},
    {"component": "C-ABEP_SIM_DESIGN_UPSTREAM_A9_13_PY", "requested_status": "PARTIAL_ADMISSION (A9.13 setpoint / "
     "domain / flow-gap / robust-set rules admitted; the row stays PYTHON_REFERENCE)",
     "scope": "every upstream_a9_13 entry of the contract (P10-P25): pressure_domain_status, classify_pressure_target, "
              "combine_value_status, constraint_status, ScheduleInput, SetpointSchedule, FixedSetpoint, "
              "controller_view, H1Tolerance, governing_band, characterization_coverage, refuse_fixed_mass_flow_gate, "
              "flight_feed_requirement, flow_gap_record, refuse_feed_requirement_lowering, state_coverage, "
              "RobustParetoSet, refuse_candidate_evidence, verify_decision_records, cite, dense_state_only_operation "
              "and the constants",
     "pending": "statewise_envelope / _quantify / reference_drag_fn (SC-WP-04), require_all_admitted_scenarios / "
                "robust_over_scenarios (SC-WP-09), verify_state_set_decision_records, PROPELLANT_POLICY / AIR_PATH / "
                "XE_PATH (SC-WP-12), assessment-layer comparison helpers",
     "authoritative_implementation": "rust: abep_gaspath::upstream"}]}
# v3 (A9.31 sec. 5 transient procedure): the full v1 scope, transients included
LEDGER_V[("plenum", 3)] = [
    {"component": "C-ABEP_SIM_DESIGN_PLENUM_FEED_PY", "requested_status": "PARTIAL_ADMISSION (ADMITTED for the full "
     "contract v3 scope below, transients included; the row stays PYTHON_REFERENCE while the not_ported items are "
     "neither ported nor formally retired)",
     "scope": LEDGER_V[("plenum", 2)][0]["scope"] + "; TransientRun.run (P42 transient_run) and transient_case (P43) "
              "under the A9.31 sec. 5 convergence-derived envelopes (transient_envelope_v4.json); Rust transient "
              "integrator with the switching-point fix a9dc2f5",
     "supersedes_request": "the v2 request (transients excluded) is superseded: P42 / P43 are admitted by v3",
     "not_ported": LEDGER_V[("plenum", 2)][0]["not_ported"],
     "authoritative_implementation": "rust: abep_gaspath::{plenum_feed, transient} for the scope above"},
    {"component": "C-ABEP_SIM_RESERVOIR_PY", "requested_status": "ADMITTED (whole registered module)",
     "scope": "Reservoir (conductance, steady_state), size_orifice_for_pressure (report form), startup_transient",
     "authoritative_implementation": "rust: abep_gaspath::reservoir"},
    dict(LEDGER_V[("plenum", 2)][2])]
LEDGER_V[("plenum", 4)] = copy.deepcopy(LEDGER_V[("plenum", 3)])
LEDGER_V[("plenum", 5)] = copy.deepcopy(LEDGER_V[("plenum", 3)])
LEDGER_V[("plenum", 5)][0]["scope"] = LEDGER_V[("plenum", 5)][0]["scope"].replace(
    "transient_envelope_v4.json", "transient_envelope_v5.json") + (
    "; the segment cascade diagnostics K_min / K_over_K0_max / p_stage_max_Pa / P_el_max_W / T_comp_max_K of a "
    "transient segment are rounding-dominated outside the Gaede domain and carry no admitted value beyond their "
    "primitives (contract v5 rule_cascade)")
LEDGER_V[("plenum", 6)] = copy.deepcopy(LEDGER_V[("plenum", 5)])
LEDGER_V[("plenum", 6)][0]["scope"] = LEDGER_V[("plenum", 6)][0]["scope"].replace(
    "transient_envelope_v5.json", "transient_envelope_v6.json").replace(
    "Rust transient integrator with the switching-point fix a9dc2f5",
    "Rust transient integrator with the switching-point fix a9dc2f5 and the growing-mode guard 361a197")
assert "361a197" in LEDGER_V[("plenum", 6)][0]["scope"] and "transient_envelope_v6" in LEDGER_V[("plenum", 6)][0]["scope"]
LEDGER_V[("plenum", 7)] = copy.deepcopy(LEDGER_V[("plenum", 6)])
LEDGER_V[("plenum", 7)][0]["scope"] = LEDGER_V[("plenum", 7)][0]["scope"].replace(
    "transient_envelope_v6.json", "transient_envelope_v7.json") + (
    "; transients by input-only stability stratum (contract v7): stable loops against the stable-stratum envelopes, "
    "unstable loops against the converged reference (DIV-P-REF-01: the Python nominal transient is not trustworthy on "
    "unstable loops), xO extrema of closing-valve segments carry no admitted value")
assert "transient_envelope_v7" in LEDGER_V[("plenum", 7)][0]["scope"]
LEDGER_FAIL["plenum"] = [{"component": c, "requested_status": "PARITY_FAILED (stays PYTHON_REFERENCE; a code fix needs "
                          "a new contract version with a fresh seed)"}
                         for c in ("C-ABEP_SIM_DESIGN_PLENUM_FEED_PY", "C-ABEP_SIM_RESERVOIR_PY",
                                   "C-ABEP_SIM_DESIGN_UPSTREAM_A9_13_PY")]
NOTES_V = {}
NOTES = {"plenum": [
    "entry indices: the contract registers vector counts per P-number; the function assigned to each index is fixed "
    "in the harness docstring (written before the scoring run); P40 (synthetic-segment metrics) is not named in any "
    "float group of the contract and takes the strictest closed-form class (k_ulp 4 / r_rel 1e-12)",
    "harness instrumentation: TransientRun._segment_record is wrapped in the harness process to record u_cmd at the "
    "segment end and the samples (threshold-proximity rule); the record it returns is unchanged and no reference file "
    "is modified. The Rust transient_run request returns the same u_cmd as '_ucmd_end' (reported, not scored)",
    "the Rust steady_sweep request also returns the scalar twin of every point ('_scalar', stripped before the "
    "comparison) for INV-P-02",
    "nfev and mass_residual_rel of the transients, iterations of the reservoir fixed point and every "
    "conservation_residual_rel leaf are reported, not scored (registered); CONS-P-02 / -03 gate them",
    "pre-scoring disclosure (written before this scoring run, from development-seed comparisons only): every "
    "development difference was in the transient entries (P42 / P43) and was classified CONTRACT_DEFECT, not "
    "RUST_DEFECT: (i) mdot samples are registered with a relative tolerance only, but mdot is linear in the valve "
    "opening u, which is registered with an absolute tolerance; where the valve is (nearly) closed (|u| within 10 x "
    "its tolerance) the relative mdot difference is unbounded (all development mdot differences were there); (ii) "
    "xO is NaN in the reference where the integrator's u noise around 0 is negative, so the None-ness of xO at a "
    "closed valve is the sign of rounding noise (all development xO differences were there); (iii) the cascade "
    "diagnostics of a transient segment (K_min, p_stage_max_Pa, P_el_max_W, T_comp_max_K) on trajectories outside "
    "the Gaede domain evaluate K0 - (K0 - 1) x with K0 up to 1e20, i.e. rounding noise of size ulp(K0) in the "
    "reference itself; (iv) final_setpoint_error_frac is a small difference quantity whose registered absolute "
    "floor (1e-6) is below the production integrator tolerance (rtol 1e-5); (v) with 17 transient_case vectors one "
    "isolated settling-index coincidence exceeds the 1 % proximity limit. Trajectories p, u and t agreed within "
    "their registered tolerances in both the production and the reference-tolerance sets. PROGRAMME.md sec. 7 "
    "rule 11: a contract defect needs a new contract version and is never resolved by changing a tolerance; the "
    "re-specification of these transient observables is an owner / coordinator decision (reported as a blocker)"],
         "filter": [],
         "compressor": ["spec_formats.coeffs: DragCompressor has 27 dataclass fields (v1 said 30; corrected in v2); "
                        "the vectors carry all 27 plus rotor_strength_basis_id and rotor_stock_thickness_m",
                        "vector counts: C01 carries the golden defaults vector plus the three registered edges "
                        "(E-C-01..03) next to the 300 random vectors; C06 carries all 11 listed E-C-04 edges (the "
                        "count '+ 10' of the contract under-counts the listed items); every listed vector is scored",
                        "C22 compares the compressor slot of architecture_optimizer.official_ledger "
                        "('hall_icp_neutralizer'): P_W, evidence_class, source and the ledger label; the slot status "
                        "is NOT_EVALUATED in both (row 22 not supplied, INV-C-03)"]}


# ======================================================================================================================
# Campaign
# ======================================================================================================================
def environment():
    from numpy._core._multiarray_umath import __cpu_baseline__, __cpu_dispatch__, __cpu_features__
    import pandas
    import scipy
    cpu = ""
    try:
        cpu = next(line.split(":", 1)[1].strip() for line in open("/proc/cpuinfo") if line.startswith("model name"))
    except (OSError, StopIteration):
        pass
    cfg = np.show_config(mode="dicts")
    return {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__,
            "pandas": pandas.__version__, "numpy_simd_baseline": list(__cpu_baseline__),
            "numpy_simd_dispatch": list(__cpu_dispatch__),
            "numpy_simd_avx512f_enabled": bool(__cpu_features__.get("AVX512F")),
            "blas": cfg.get("Build Dependencies", {}).get("blas", {}).get("name", "") + " "
            + str(cfg.get("Build Dependencies", {}).get("blas", {}).get("version", "")),
            "cpu": cpu, "platform": platform.platform(),
            "thread_env": {k: os.environ.get(k) for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS")},
            "requirements_lock_sha256": sha_file(os.path.join(ROOT, "requirements-lock.txt"))}


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def provenance(contract):
    files = []
    for pat in contract["rust_implementation"]["provenance_sources"]:
        base = pat.replace("/**", "")
        p = os.path.join(ROOT, base)
        if os.path.isdir(p):
            for dp, _, fns in sorted(os.walk(p)):
                files += [os.path.relpath(os.path.join(dp, f), ROOT) for f in sorted(fns)]
        elif os.path.isfile(p):
            files.append(base)
    rustc = subprocess.run(["/root/.cargo/bin/rustc", "-V"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    cargo = subprocess.run(["/root/.cargo/bin/cargo", "-V"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    return {"rustc": rustc, "cargo": cargo, "cargo_lock_sha256": sha_file(os.path.join(ROOT, "Cargo.lock")),
            "source_sha256": {f: sha_file(os.path.join(ROOT, f)) for f in sorted(set(files))},
            "harness": {"path": "scripts/rust_migration/es3_gaspath_parity.py",
                        "sha256": sha_file(os.path.abspath(__file__))},
            "binary": "target/release/abep-gaspath-parity (cargo build --release --locked)"}


def equal_values(a, b) -> bool:
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    return exact_equal(a, b)


def captured(key):
    """The reference outputs captured by the single scoring execution of the active version (gz JSON)."""
    rdir = os.path.join(os.path.dirname(load_contract(key)[2]), ref_dir_name(version_of(key)))
    rd = {}
    for name in ("inputs", "python_outputs", "rust_outputs_at_scoring"):
        with gzip.open(os.path.join(rdir, f"{name}.json.gz")) as f:
            rd[name] = json.loads(f.read())
    return rd


def run_campaign(key: str, mode: str, capture: bool = False, only=None, replay: bool = False) -> dict:
    """replay=True (mode 'rerender-score'): rebuild the report of the single scoring execution of the active version
    from its captured outputs when the report writer failed (truncated report). The scoring vectors, the Python
    reference outputs and the Rust outputs must equal the captured ones; nothing is re-scored with another seed."""
    contract, contract_sha, cpath = load_contract(key)
    cdir = os.path.dirname(cpath)
    report_path = os.path.join(cdir, f"parity_report_v{version_of(key)}.json")
    cap0 = None
    if replay:
        try:
            json.load(open(report_path))
            sys.exit(f"REFUSED: {report_path} is a complete report; rerender-score only rebuilds a truncated one")
        except (OSError, ValueError):
            pass
        cap0 = captured(key)
        mode = "score"
    elif mode == "score" and os.path.exists(report_path):
        sys.exit(f"REFUSED: {report_path} exists; the scoring comparison runs once per contract version")
    changed = [f["path"] for f in contract["reference_implementation"]["files"]
               if sha_file(os.path.join(ROOT, f["path"])) != f["sha256_at_registration"]]
    changed += [p for p, h in contract.get("pinned_inputs_sha256", {}).items()
                if isinstance(h, str) and len(h) == 64 and sha_file(os.path.join(ROOT, p)) != h and p not in changed]
    if changed:
        return {"verdict": "REFUSED_REFERENCE_CHANGED", "changed": changed}
    if mode == "score":
        dirty = git("status", "--porcelain", "--", "crates", "Cargo.toml", "Cargo.lock", "rust-toolchain.toml",
                    "scripts/rust_migration")
        if dirty:
            sys.exit("REFUSED: uncommitted Rust / harness sources (would be an UNRECORDED_SOURCE_CHANGE):\n" + dirty)
    seeds = contract["campaign_seeds"]
    master = seeds["scoring_master_seed" if mode == "score" else "development_master_seed"]
    v3 = key == "plenum" and version_of(key) >= 3
    if v3:
        # transient_convergence_procedure_v3 step 4: the frozen envelope record is read before any held-out vector
        ENV.clear()
        ENV.update(load_envelope(contract, contract_sha, mode))
        V3_SCALE.clear()
        V3_SCALE.update(v3_families())
        IMG.clear()
        MDS.clear()
        CLS.clear()
        PYU.clear()
        REPORTED.clear()
    build_rust()
    gen, pyf, rule, checks = SPEC[key]
    vectors = gen(master)
    excl = excluded_entries(contract, key)
    vectors = [v for v in vectors if v["entry"] not in excl]
    replay_checks = {}
    if cap0 is not None:
        replay_checks["vectors_equal_captured"] = json.loads(json.dumps(vectors)) == cap0["inputs"]
        if not replay_checks["vectors_equal_captured"]:
            sys.exit("REFUSED: regenerated scoring vectors differ from the captured inputs")
    if only:
        vectors = [v for v in vectors if re.match(only, v["id"])]
    # INV-C-05 / DIV-P-03: the materials sent to Rust are materials.DB at python_commit
    mats_ok = all(MATERIALS[k] == {"density": m.density, "yield_MPa": m.yield_MPa, "T_max_K": m.T_max_K,
                                   "gamma_min": m.gamma_min, "gamma0": m.gamma0, "gamma_Ea_eV": m.gamma_Ea_eV}
                  for k, m in DB.items())
    t_py0 = time.perf_counter()
    py_out = {v["id"]: pyf(v) for v in vectors}
    t_py = time.perf_counter() - t_py0
    py_out2 = {v["id"]: pyf(v) for v in vectors}
    py_det = all(py_out[k][0] == py_out2[k][0] and equal_values(py_out[k][1], py_out2[k][1]) for k in py_out)
    if cap0 is not None:
        replay_checks["python_outputs_equal_captured"] = json.loads(json.dumps(
            {k: list(v) for k, v in py_out.items()})) == cap0["python_outputs"]
        if not replay_checks["python_outputs_equal_captured"]:
            sys.exit("REFUSED: re-evaluated Python reference outputs differ from the captured ones")
    reqs = [{"id": v["id"], "entry": v["entry"], "args": v["args"]} for v in vectors]
    try:
        rust, raw1, timing, wall = run_rust(reqs)
        _, raw2, _, _ = run_rust(reqs)
    except subprocess.CalledProcessError as exc:
        if mode != "score":
            raise
        diag = {"rust_exit_status": exc.returncode,
                "rust_stderr_tail": [ln for ln in exc.stderr.decode(errors="replace").splitlines()
                                     if not ln.startswith("{")][:12]}
        rep = write_failed_execution(key, version_of(key), master, len(vectors), git("rev-parse", "HEAD"), diag,
                                     ["the Rust CLI exited before writing any result; no comparison was made"])
        sys.exit(f"{rep['parity_verdict']}: Rust CLI exited with status {exc.returncode} (report written)")
    rres = {r["id"]: r for r in rust["results"]}
    if cap0 is not None:
        replay_checks["rust_outputs_equal_captured"] = json.loads(raw1) == cap0["rust_outputs_at_scoring"]
        if not replay_checks["rust_outputs_equal_captured"]:
            sys.exit("REFUSED: the Rust CLI output on the captured inputs differs from the captured scoring output")

    t = Tally()
    errors = []
    per_entry = {}
    proximity = []
    for v in vectors:
        po = py_out[v["id"]]
        ro = rust_outcome(rres[v["id"]])
        if ro[0] == "OK" and key in PRE:
            ro = (ro[0], PRE[key](v, copy.deepcopy(ro[1])), ro[2])
        pe = per_entry.setdefault(v["entry"], {"n": 0, "python_errors": 0, "rust_errors": 0})
        pe["n"] += 1
        pe["python_errors"] += po[0] == "ERROR"
        pe["rust_errors"] += ro[0] == "ERROR"
        ok_outcome = t.exact(v["entry"], "outcome", [ro[0], ro[1] if ro[0] == "ERROR" else None],
                             [po[0], po[1] if po[0] == "ERROR" else None], v["id"])
        if po[0] == "ERROR" or ro[0] == "ERROR":
            errors.append({"vector": v["id"], "entry": v["entry"], "python": po[1] if po[0] == "ERROR" else "OK",
                           "rust": ro[1] if ro[0] == "ERROR" else "OK", "python_message": (po[2] or "")[:200],
                           "rust_message": (ro[2] or "")[:200], "ok": ok_outcome})
        if po[0] == "OK" and ro[0] == "OK":
            sk = SKIP.get(key)
            if key == "plenum" and v7_on():
                sk = (lambda e_, p_, v_=v: skip_v7(e_, p_, v_))  # noqa: E731
            ctx = {"vector": v, "entry": v["entry"], "inputs": input_floats(v["args"]), "py": po[1], "rust": ro[1],
                   "skip": sk}
            sub = Tally()
            compare_tree(sub, v["entry"], v["id"], ro[1], po[1], rule, ctx)
            prox = PROXIMITY.get(key, lambda *a: None)(v, ro[1], po[1], sub)
            if prox is not None:
                proximity.append(prox)
                sub = prox.pop("_tally")
            merge(t, sub)
    extra = checks(t, vectors, py_out, rres) if checks else {}
    summ = t.summary()
    prox_fail = []
    for ent, pe in per_entry.items():
        n_at = sum(1 for p in proximity if p["entry"] == ent)
        pe["not_scored_at_threshold"] = n_at
        if v3:
            # contract v3 decision_rules.proximity_limit: NOT_SCORED_AT_THRESHOLD leaves over the discrete leaves
            # compared (EXACT_VALUE leaves and the sample-time settling leaves)
            n_lv = sum(p.get("n_unscored_leaves", 0) for p in proximity if p["entry"] == ent)
            n_disc = sum(o["n"] for o in summ["observables"] if o["entry"] == ent and (
                o["tolerance_class"] == "EXACT_VALUE" or any(k in o["observable"] for k in (
                    "settling_time_s", "flow_recovery_s", "settling_max_s"))))
            pe["not_scored_at_threshold_leaves"] = n_lv
            pe["discrete_leaves_compared"] = n_disc
            if n_lv > 0.01 * n_disc:
                prox_fail.append(ent)
        elif n_at > 0.01 * pe["n"]:
            prox_fail.append(ent)
    det_ok = raw1 == raw2 and py_det
    extra_ok = all(x.get("ok", True) for x in extra.values())
    per_test_ok = summ["n_failures"] == 0
    verdict_ok = per_test_ok and det_ok and extra_ok and mats_ok and not prox_fail
    out = {
        "contract_id": contract["id"], "contract_sha256": contract_sha, "mode": mode, "master_seed": master,
        "n_vectors": len(vectors), "per_entry": per_entry, "per_test": summ, "errors": errors,
        "threshold_proximity": {"records": proximity, "entries_over_proximity_limit": prox_fail},
        "checks_extra": extra,
        "determinism": {"rust_two_processes_byte_identical": raw1 == raw2,
                        "rust_stdout_sha256": hashlib.sha256(raw1).hexdigest(), "python_two_evaluations_equal": py_det},
        "materials_equal_db": mats_ok,
        "replay": replay_checks or None,
        "timing": {"python_reference_s": t_py, "rust_cli_wall_s": wall,
                   "rust_per_request_s_sum": sum(x["elapsed_s"] for x in timing)},
        "pass": {"per_test": per_test_ok, "determinism": det_ok, "invariants_and_conservation": extra_ok,
                 "materials_equal_db": mats_ok, "threshold_proximity_limit": not prox_fail, "all": verdict_ok},
    }
    if v3:
        out["transient_v3"] = transient_v3_summary(t, vectors)
        out["envelope_record"] = ENV.get("_meta")
    if key == "plenum" and v7_on():
        out["transient_v7"] = transient_v7_summary(vectors, py_out, rres)
    if mode == "score" or capture:
        out["_capture"] = {"vectors": vectors, "python": {k: list(v) for k, v in py_out.items()},
                           "rust_raw": raw1.decode()}
        out["_timing_detail"] = timing
    return out


def merge(t: Tally, sub: Tally):
    for k, o in sub.obs.items():
        if k not in t.obs:
            t.obs[k] = dict(o)
        else:
            d = t.obs[k]
            for f in ("n", "n_fail", "n_bit_identical"):
                d[f] += o[f]
            for f in ("max_abs_diff", "max_rel_diff", "max_ulp"):
                d[f] = max(d[f], o[f])
            if "max_used_frac" in o:
                d["max_used_frac"] = max(d.get("max_used_frac", 0.0), o["max_used_frac"])
            if "family" in o:
                d["family"] = o["family"]
            if "tolerance" in o:
                d["tolerance"] = o["tolerance"]
    t.failures += sub.failures
    for k, u in sub.unscored.items():
        if k not in t.unscored:
            t.unscored[k] = dict(u)
        else:
            d = t.unscored[k]
            d["n"] += u["n"]
            d["max_abs_diff"] = max(d["max_abs_diff"], u["max_abs_diff"])
            d["max_rel_diff"] = max(d["max_rel_diff"], u["max_rel_diff"])


def write_gz_json(path, obj):
    raw = json.dumps(obj, separators=(",", ":"), allow_nan=True).encode()
    with open(path, "wb") as f:
        with gzip.GzipFile(fileobj=f, mode="wb", mtime=0, filename="") as g:
            g.write(raw)
    return sha_file(path)


def perf(key, vectors):
    """Performance workloads (reported, never a criterion)."""
    res = []

    def med(fn, n=3):
        ts = []
        for _ in range(n):
            t0 = time.perf_counter()
            fn()
            ts.append(time.perf_counter() - t0)
        return statistics.median(ts), ts
    _, pyf, _, _ = SPEC[key]
    for wid, pat, note in PERF[key]:
        vs = [v for v in vectors if re.match(pat, v["id"])]
        if not vs:
            continue
        py_m, py_t = med(lambda: [pyf(v) for v in vs])
        rs_m, rs_t = med(lambda: run_rust([{"id": v["id"], "entry": v["entry"], "args": v["args"]} for v in vs]))
        res.append({"id": wid, "n_vectors": len(vs), "python_median_s": py_m, "rust_median_s": rs_m,
                    "python_s": py_t, "rust_s": rs_t, "speedup": py_m / rs_m, "note": note})
    return res


NOTES_V[("plenum", 2)] = [x for x in NOTES["plenum"] if not x.startswith("pre-scoring disclosure")]
VERSION_NOTES = {
    ("filter", 2): ["v2 re-binds the build provenance after the shared abep-gaspath source change c3a41fb (compressor "
                    "RUST_DEFECT fix, CLI panic isolation; filter.rs unchanged); v1 (PARITY_PASS) stays; generators, "
                    "tolerances and decision rules are those of v1, with fresh seeds"],
    ("compressor", 2): ["v2 follows the NOT_ADMITTED v1 execution (RUST_DEFECT: the Rust CLI panicked in "
                        "rotor_strength::basis_problems on a NaN allowable temperature; fix c3a41fb); generators, "
                        "tolerances and decision rules are those of v1, with fresh seeds. The CLI now records a panic "
                        "as the request's outcome (error_class RUST_PANIC, never equal to a Python class)"],
    ("plenum", 2): ["v2 is v1 minus the transient entries plenum.transient_run (P42) and plenum.transient_case (P43) "
                    "(scope_reduction_v2); v1 (PARITY_FAIL, all 247 failures in P42 / P43, classified CONTRACT_DEFECT) "
                    "stays. Every other observable, tolerance, generator, n and decision rule is v1's, with fresh "
                    "seeds. The re-specification of the transient observables is a pending owner decision; "
                    "transient_run / transient_case stay PYTHON_REFERENCE until an owner-ruled transient contract "
                    "exists. The harness generates the P42 / P43 vectors from their own streams and drops them before "
                    "any call; CONS-P-03 is evaluated on P45 only; PERF-P-02 (transient_case) is not measured"],
}
VERSION_NOTES[("plenum", 7)] = [
    "v7 is contract v6 (registered aca62b3; REGISTERED_NEVER_SCORED, superseded: P45 envelope dominated by an "
    "unstable-start stratum and a silent reference defect) with transient_convergence_procedure_v7: input-only "
    "stability class (both implementations; a disagreement is a scored failure), strata S / U / R with registered "
    "stratified held-out and refinement draws, the unstable stratum scored against the converged Python reference "
    "(DIV-P-REF-01) with NOT_CONVERGENT_REFERENCE leaves reported, closing-valve xO extrema reported, and the "
    "non-vacuity check of every scored family and stratum on the frozen record before the scoring run",
    "order of commits: ..., contract v6, the v6 frozen record (not scored), the v6 analyses and DIV-P-REF-01, the "
    "merge of the integration line, the Rust stability-class addition b4de97d, contract v7 (alone), the v7 harness, "
    "the frozen v7 envelope record (refinement run incl. the non-vacuity check), the captured scoring run, the reports"]
VERSION_NOTES[("plenum", 6)] = [
    "v6 is contract v5 (registered f44dbfe; REGISTERED_NEVER_SCORED, superseded: Rust integrator accepts damped steps "
    "on unstable modes) with the growing-mode guard 361a197 registered and fresh seeds. The frozen v5 refinement "
    "record (3eeb574) showed Rust P45 envelopes of 0.782 (F45.mdot) and 0.0311 (F45.P_dev) from R45-192 / R45-331, "
    "whose closed loops are unstable at the steady start: Radau IIA damped the mode at large steps and the "
    "step-doubling estimate did not see it, so the nominal Rust run held the setpoint where both implementations "
    "converge to a 3 % saturating limit cycle. v5 was not scored (near-vacuous P45 bounds, A9.29 sec. 14); its "
    "record and the defect note rust_defect_v5_growing_mode_damping.md stay as evidence. v5 itself is v4 with the "
    "cascade diagnostics scored through their primitives and a four-times larger grid; v4 is v3 with the switching-"
    "point fix a9dc2f5",
    "order of commits: contract v3, fix a9dc2f5, contract v4, contract v5, the harness / CLI refinement and scoring "
    "code, the frozen v5 record (not scored), fix 361a197, the defect note, contract v6 (each contract alone), the "
    "harness version bump, the frozen v6 envelope record (refinement run), the captured scoring run, the reports. "
    "The parity CLI gained one request option (orbit_sim with an explicit rtol, composed from library calls; "
    "COMP-P-01 in the record)"]
VERSION_NOTES[("plenum", 5)] = [
    "v5 is contract v4 (registered 0aec5a1, superseded before any scored run) with the five segment cascade "
    "diagnostics scored through their primitives (reported with conditioning; rounding-dominated at and outside the "
    "edge of the Gaede domain, K quantised in steps of K0 eps) and a four-times larger refinement grid (exceedance "
    "probability of the grid maximum <= 1.5 % per family and level); fresh seeds. v4 itself is v3 (539f3fe, "
    "superseded before any scored run) with the transient RUST_DEFECT fix a9dc2f5 (valve-command saturation switch). "
    "Both supersessions were found in development runs on the development seeds only",
    "order of commits: contract v3, the RUST_DEFECT fix, contract v4, contract v5 (each alone), the harness / CLI "
    "refinement and scoring code, the frozen envelope record (refinement run), the captured scoring run, the reports. "
    "The parity CLI gained one request option (orbit_sim with an explicit rtol, composed from library calls; "
    "COMP-P-01 in the record)"]
VERSION_NOTES[("plenum", 4)] = [
    "v4 is contract v3 (registered 539f3fe, superseded before any scored run: no envelope record, no held-out "
    "vector) with the transient RUST_DEFECT fix a9dc2f5 registered and fresh seeds. The v3 development draft of the "
    "refinement procedure (development seed only) exposed an rtol-independent Rust error up to ~6e-7 at the "
    "valve-command saturation switch; four independent scipy integrations of the reference right-hand side agreed "
    "with the Python reference to 1.5e-11 there. The fix bisects any step whose end changes the saturation state"]
VERSION_NOTES[("plenum", 3)] = [
    "v3 is the full v1 scope with the transients P42 / P43 / P45 under the A9.31 sec. 5 convergence-derived "
    "procedure (transient_convergence_procedure_v3); v1 (PARITY_FAIL, P42 / P43) and v2 (PARITY_FAIL, P45) stay. "
    "Every non-transient observable, tolerance, generator, n and rule is v1's, with fresh seeds. The transient "
    "bounds are the frozen envelope record's E_py + E_rust per family (estimated on the independent refinement grid "
    "before any held-out vector ran) plus the STEADY floating allowance; nfev / step decomposition / iteration "
    "counts are not scored; the segment cascade diagnostics are scored through the primitive image with their "
    "conditioning recorded; proximity is attributed leaf by leaf and counted per leaf",
    "order of commits: contract v3 (alone), then the harness / CLI refinement and scoring code (the record must cite "
    "committed code), then the frozen envelope record (refinement run), then the single scoring run and the "
    "reports. The parity CLI gained one request option (orbit_sim with an explicit rtol, composed from library "
    "calls; COMP-P-01 in the record); no abep-gaspath library source changed"]
NOTES_V[("plenum", 7)] = NOTES_V[("plenum", 6)] = NOTES_V[("plenum", 5)] = NOTES_V[("plenum", 4)] = NOTES_V[("plenum", 3)] = [x for x in NOTES["plenum"]
                                                  if not x.startswith("pre-scoring disclosure")] + [
    "harness instrumentation (v3): the tap of TransientRun._segment_record also keeps the run's states at the "
    "samples (for the primitive image of the cascade diagnostics and the per-segment proximity flags); the reference "
    "record is unchanged (IMG-CHECK: f(y) equals the reported value bit for bit)"]
HARNESS_NOTE = ("harness: the contract says the harness is committed 'after this contract and before the scoring run'. "
                "It was developed with development-seed comparisons (never scored, no report) and committed before "
                "the single scoring run; every scored generator, tolerance and decision rule is the registered one. "
                "Leaf classification (copied floats = non-zero Python floats that occur among the vector's inputs, "
                "EXACT_VALUE; every other float the entry's class; in the transient entries only the leaves copied "
                "by construction) is fixed in the harness docstring")


def write_report(key, res, perf_rows, out_dir=None):
    contract, contract_sha, cpath = load_contract(key)
    cdir = out_dir or os.path.dirname(cpath)
    cap = res.pop("_capture")
    timing_detail = res.pop("_timing_detail")
    n = version_of(key)
    rdir = os.path.join(cdir, ref_dir_name(n))
    os.makedirs(rdir, exist_ok=True)
    if res.get("replay"):
        # the captured outputs of the scoring execution stay as written by it; they must match their manifest
        man = json.load(open(os.path.join(rdir, "MANIFEST.json")))
        for fn, h in man["files"].items():
            if sha_file(os.path.join(rdir, fn)) != h:
                sys.exit(f"REFUSED: captured {fn} does not match its MANIFEST sha256")
    else:
        man = {"schema": "abep_rust_parity_reference_outputs_v1", "contract_id": contract["id"],
               "captured_at_python_commit": contract["reference_implementation"]["python_commit"],
               "captured_at_head": git("rev-parse", "HEAD"), "files": {}}
        man["files"]["inputs.json.gz"] = write_gz_json(os.path.join(rdir, "inputs.json.gz"), cap["vectors"])
        man["files"]["python_outputs.json.gz"] = write_gz_json(os.path.join(rdir, "python_outputs.json.gz"),
                                                               cap["python"])
        man["files"]["rust_outputs_at_scoring.json.gz"] = write_gz_json(
            os.path.join(rdir, "rust_outputs_at_scoring.json.gz"), json.loads(cap["rust_raw"]))
        man["format"] = ("deterministic gzip (mtime 0) of compact JSON; python_outputs: id -> [outcome, value | "
                         "exception class, message]; non-finite floats as the strings 'NaN', '+inf', '-inf'")
        with open(os.path.join(rdir, "MANIFEST.json"), "w") as f:
            json.dump(man, f, indent=1)
            f.write("\n")
    passed = res["pass"]["all"]
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report = {
        "schema": "abep_rust_parity_report_v1",
        "contract": {"id": contract["id"], "path": os.path.relpath(cpath, ROOT), "sha256": contract_sha,
                     "registration_commit": git("log", "-n1", "--format=%H", "--", os.path.relpath(cpath, ROOT))},
        "date_utc": now,
        "python_commit": contract["reference_implementation"]["python_commit"],
        "reference_sha256": {f["path"]: {"registered": f["sha256_at_registration"],
                                         "at_scoring": sha_file(os.path.join(ROOT, f["path"]))}
                             for f in contract["reference_implementation"]["files"]},
        "rust_commit": git("rev-parse", "HEAD"),
        "build_provenance": provenance(contract),
        "environment": environment(),
        "mode": "scoring" if res["mode"] == "score" else "DEVELOPMENT (not a verdict)",
        "scoring_master_seed": res["master_seed"],
        "n_vectors": res["n_vectors"],
        "vectors_per_entry": res["per_entry"],
        "per_test": res["per_test"],
        "aggregates": "NOT_APPLICABLE (no STATISTICAL entry point)",
        "domain_error": {"vectors": res["errors"]},
        "threshold_proximity": res["threshold_proximity"],
        "invariants": {"determinism": res["determinism"], "materials_equal_db (INV-C-05 / DIV-P-03)":
                       res["materials_equal_db"],
                       **{k: v for k, v in res["checks_extra"].items() if k.startswith("INV")}},
        "conservation": {k: v for k, v in res["checks_extra"].items() if k.startswith("CONS")},
        **({"transient_integrity": {k: v for k, v in res["checks_extra"].items()
                                    if k.startswith(("NN", "VS", "EV", "IMG"))},
            "envelope_record": res["envelope_record"], "transient_v3": res["transient_v3"]}
           if "transient_v3" in res else {}),
        **({"transient_v7": res["transient_v7"]} if "transient_v7" in res else {}),
        "schema_parity": [o for o in res["per_test"]["observables"]
                          if o["observable"].endswith("{keys}") or o["observable"].endswith("[len]")],
        "performance": {"status": "reported, never a decision criterion", "workloads": perf_rows,
                        "campaign_timing": res["timing"], "rust_per_request_timing_top10": sorted(
                            timing_detail, key=lambda x: -x["elapsed_s"])[:10]},
        "checks": res["pass"],
        "verdict": "ADMITTED" if passed else "NOT_ADMITTED",
        "parity_verdict": "PARITY_PASS" if passed else "PARITY_FAIL",
        "campaign_history": [{"date_utc": now, "mode": "scoring", "seed": res["master_seed"],
                              "verdict": "PARITY_PASS" if passed else "PARITY_FAIL", "executions": 1}],
        "reference_outputs": {"path": os.path.relpath(rdir, ROOT), "manifest_sha256": sha_file(
            os.path.join(rdir, "MANIFEST.json"))},
        "supersedes": contract.get("supersedes"),
        "ledger_update_requested": LEDGER_V.get((key, n), LEDGER[key]) if passed else LEDGER_FAIL[key],
        "notes": [HARNESS_NOTE] + NOTES_V.get((key, n), NOTES[key]) + VERSION_NOTES.get((key, n), []),
        "what_this_is_not": contract["what_this_is_not"],
    }
    if res.get("replay"):
        report["campaign_history"][0].update({
            "report_regenerated_from_captured_outputs": True,
            "scoring_execution_head": man.get("captured_at_head"),
            "regeneration_checks": res["replay"],
            "why": "the report writer of the scoring execution stopped on a non-finite max_ulp (json allow_nan=False; "
                   "harness defect, fixed by writing non-finite floats as strings); the comparison was rebuilt from "
                   "the captured outputs of that single execution"})
    report = sanitize(report)
    with open(os.path.join(cdir, f"parity_report_v{n}.json"), "w") as f:
        json.dump(report, f, indent=1, allow_nan=False)
        f.write("\n")
    with open(os.path.join(cdir, f"parity_report_v{n}.md"), "w") as f:
        f.write(render_md(report))
    return report


def provenance_at(contract, commit):
    """Build provenance of an execution recorded after the fact: the sources as committed at `commit`."""
    files = []
    for pat in contract["rust_implementation"]["provenance_sources"]:
        base = pat.replace("/**", "")
        out = git("ls-tree", "-r", "--name-only", commit, "--", base)
        files += [f for f in out.splitlines() if f]

    def sha_at(path):
        blob = subprocess.run(["git", "show", f"{commit}:{path}"], cwd=ROOT, capture_output=True, check=True).stdout
        return hashlib.sha256(blob).hexdigest()
    prov = provenance(contract)
    prov.update({"source_sha256": {f: sha_at(f) for f in sorted(set(files))},
                 "cargo_lock_sha256": sha_at("Cargo.lock"),
                 "harness": {"path": "scripts/rust_migration/es3_gaspath_parity.py",
                             "sha256": sha_at("scripts/rust_migration/es3_gaspath_parity.py"),
                             "recorded_at_commit": commit},
                 "recorded_from_commit": commit})
    return prov


def write_failed_execution(key, n, master, n_vectors, commit, diagnosis, notes):
    """Report of a scoring execution that produced no comparison (the Rust CLI exited): NOT_ADMITTED / PARITY_FAIL,
    committed like any other report (no execution is discarded)."""
    contract, contract_sha, cpath = load_contract(key, n)
    cdir = os.path.dirname(cpath)
    path = os.path.join(cdir, f"parity_report_v{n}.json")
    if os.path.exists(path):
        sys.exit(f"REFUSED: {path} exists")
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report = {
        "schema": "abep_rust_parity_report_v1",
        "contract": {"id": contract["id"], "path": os.path.relpath(cpath, ROOT), "sha256": contract_sha,
                     "registration_commit": git("log", "-n1", "--format=%H", "--", os.path.relpath(cpath, ROOT))},
        "date_utc": now,
        "python_commit": contract["reference_implementation"]["python_commit"],
        "reference_sha256": {f["path"]: {"registered": f["sha256_at_registration"],
                                         "at_scoring": sha_file(os.path.join(ROOT, f["path"]))}
                             for f in contract["reference_implementation"]["files"]},
        "rust_commit": commit,
        "build_provenance": provenance_at(contract, commit),
        "environment": environment(),
        "mode": "scoring",
        "scoring_master_seed": master,
        "n_vectors": n_vectors,
        "execution": {"status": "RUST_CLI_EXITED_NO_RESULTS", **diagnosis},
        "per_test": "NOT_EVALUATED (no Rust result was produced; every registered vector counts as failed)",
        "checks": {"per_test": False, "determinism": False, "invariants_and_conservation": False, "all": False},
        "verdict": "NOT_ADMITTED",
        "parity_verdict": "PARITY_FAIL",
        "campaign_history": [{"date_utc": now, "mode": "scoring", "seed": master, "verdict": "PARITY_FAIL",
                              "executions": 1, "outcome": "Rust CLI exited before writing results"}],
        "reference_outputs": "NOT_CAPTURED (the execution produced no comparison)",
        "supersedes": contract.get("supersedes"),
        "ledger_update_requested": LEDGER_FAIL[key],
        "notes": notes,
        "what_this_is_not": contract["what_this_is_not"],
    }
    with open(path, "w") as f:
        json.dump(report, f, indent=1, allow_nan=False)
        f.write("\n")
    md = [f"# Parity report v{n} - {contract['id']}", "",
          "Verdict: **PARITY_FAIL** (NOT_ADMITTED). Generated from `" + os.path.basename(path) + "`.", "",
          f"* Contract: `{report['contract']['path']}` sha256 `{contract_sha}`, registered in "
          f"`{report['contract']['registration_commit'][:12]}`.",
          f"* Python reference commit `{report['python_commit'][:12]}`; Rust commit `{commit[:12]}`.",
          f"* Master seed {master} (scoring); {n_vectors} vectors generated; the Rust CLI exited with status "
          f"{diagnosis.get('rust_exit_status')} before writing any result, so no comparison was made.", "",
          "## Diagnosis", ""] + [f"* `{json.dumps(x)[:400]}`" for x in diagnosis.get("rust_stderr_tail", [])] + \
         [f"* {k}: `{json.dumps(v)[:600]}`" for k, v in diagnosis.items()
          if k not in ("rust_stderr_tail", "rust_exit_status")] + \
         ["", "## Notes", ""] + [f"* {x}" for x in notes] + \
         ["", "## Ledger update requested", ""] + [f"* {x['component']}: {x['requested_status']}"
                                                   for x in LEDGER_FAIL[key]] + \
         ["", "Parity is not physics validation, not a gate PASS and not a change of any frozen dataset.", ""]
    with open(os.path.join(cdir, f"parity_report_v{n}.md"), "w") as f:
        f.write("\n".join(md))
    return report


def sanitize(x):
    """Non-finite floats of a report as the registered strings (JSON has no inf / NaN)."""
    if isinstance(x, dict):
        return {k: sanitize(v) for k, v in x.items()}
    if isinstance(x, list):
        return [sanitize(v) for v in x]
    if isinstance(x, float) and not math.isfinite(x):
        return jnum(x)
    return x


def fmt3(x):
    return f"{x:.3g}" if isinstance(x, (int, float)) else str(x)


def render_md(r):
    nv = re.search(r"_v(\d+)\.json$", r["contract"]["path"])
    L = [f"# Parity report v{nv.group(1) if nv else 1} - {r['contract']['id']}", "",
         f"Verdict: **{r['parity_verdict']}** ({r['verdict']}). Generated from the JSON report next to this file.", "",
         f"* Contract: `{r['contract']['path']}` sha256 `{r['contract']['sha256']}`, registered in "
         f"`{r['contract']['registration_commit'][:12]}`.",
         f"* Python reference commit `{r['python_commit'][:12]}`; Rust commit `{r['rust_commit'][:12]}`; "
         f"{r['build_provenance']['rustc']}.",
         f"* Environment: Python {r['environment']['python']}, numpy {r['environment']['numpy']}, scipy "
         f"{r['environment']['scipy']}, {r['environment']['blas'].strip()}, {r['environment']['cpu']}.",
         f"* Master seed {r['scoring_master_seed']} ({r['mode']}); {r['n_vectors']} vectors; "
         f"{r['per_test']['n_failures']} per-test failures.", "",
         "## Checks", ""]
    L += [f"* {k}: {'pass' if v else 'FAIL'}" for k, v in r["checks"].items()]
    L += ["", "## Vectors per entry", "", "| entry | n | Python refusals | Rust refusals | not scored at threshold |",
          "|---|---|---|---|---|"]
    for e, pe in r["vectors_per_entry"].items():
        L.append(f"| {e} | {pe['n']} | {pe['python_errors']} | {pe['rust_errors']} | "
                 f"{pe.get('not_scored_at_threshold', 0)} |")
    L += ["", "## Float observables (non-bit-identical leaves only; every scored leaf is in the JSON report)", "",
          "| entry | observable | class | n | fail | bit-identical | max abs diff | max rel diff | max ulp |",
          "|---|---|---|---|---|---|---|---|---|"]
    for o in r["per_test"]["observables"]:
        if o["tolerance_class"] != "EXACT_VALUE" and (o["n_bit_identical"] < o["n"] or o["n_fail"]):
            L.append(f"| {o['entry']} | {o['observable'].replace('|', '/')[:90]} | {o['tolerance_class']} | {o['n']} | "
                     f"{o['n_fail']} | {o['n_bit_identical']} | {fmt3(o['max_abs_diff'])} | "
                     f"{fmt3(o['max_rel_diff'])} | {fmt3(o['max_ulp'])} |")
    nfl = sum(o["n"] for o in r["per_test"]["observables"] if o["tolerance_class"] != "EXACT_VALUE")
    nbi = sum(o["n_bit_identical"] for o in r["per_test"]["observables"] if o["tolerance_class"] != "EXACT_VALUE")
    nex = sum(o["n"] for o in r["per_test"]["observables"] if o["tolerance_class"] == "EXACT_VALUE")
    L += ["", f"Scored float leaves: {nfl} ({nbi} bit-identical); EXACT_VALUE leaves: {nex}.", ""]
    if r["per_test"]["reported_not_scored"]:
        L += ["Reported, not scored:", ""]
        for u in r["per_test"]["reported_not_scored"]:
            L.append(f"* {u['entry']} {u['observable']}: n {u['n']}, max abs diff {fmt3(u['max_abs_diff'])}, max rel "
                     f"diff {fmt3(u['max_rel_diff'])}")
        L.append("")
    L += ["## Domain / error parity", ""]
    bad = [x for x in r["domain_error"]["vectors"] if not x["ok"]]
    L.append(f"{len(r['domain_error']['vectors'])} vectors with a refusal on either side, {len(bad)} mismatches.")
    classes = {}
    for x in r["domain_error"]["vectors"]:
        k = (x["entry"], x["python"], x["rust"])
        classes[k] = classes.get(k, 0) + 1
    L += ["", "| entry | Python | Rust | n |", "|---|---|---|---|"]
    for (e, p, q), n in sorted(classes.items()):
        L.append(f"| {e} | {p} | {q} | {n} |")
    tp = r["threshold_proximity"]
    L += ["", "## Threshold proximity", "", f"{len(tp['records'])} vectors NOT_SCORED_AT_THRESHOLD; entries over the 1 % "
          f"limit: {tp['entries_over_proximity_limit'] or 'none'}."]
    for e, pe in r["vectors_per_entry"].items():
        if "discrete_leaves_compared" in pe and pe["not_scored_at_threshold_leaves"]:
            L.append(f"* {e}: {pe['not_scored_at_threshold_leaves']} of {pe['discrete_leaves_compared']} discrete "
                     f"leaves NOT_SCORED_AT_THRESHOLD (limit 1 %).")
    for p in tp["records"][:20]:
        L.append(f"* `{json.dumps(p)[:300]}`")
    L += ["", "## Invariants and conservation", ""]
    d = r["invariants"]["determinism"]
    L.append(f"* Rust two processes byte-identical: {d['rust_two_processes_byte_identical']} (stdout sha256 "
             f"`{d['rust_stdout_sha256'][:16]}...`); Python two evaluations equal: {d['python_two_evaluations_equal']}.")
    for k, v in r["invariants"].items():
        if k != "determinism":
            L.append(f"* {k}: {json.dumps(v)[:300]}")
    for k, v in r["conservation"].items():
        L.append(f"* {k}: {json.dumps({kk: vv for kk, vv in v.items() if kk != 'failures'})[:300]}")
    if "transient_v7" in r:
        t7 = r["transient_v7"]
        L += ["", "## Contract v7: strata, class, unstable stratum, reported leaves", "",
              f"* Scored strata: {json.dumps(t7['strata_scored'])}.",
              f"* Stability class (both implementations; a disagreement is a scored failure): "
              f"{t7['class_agreement']['n']} vectors, {t7['class_agreement']['n_disagree']} disagreements.",
              f"* Reported, not scored: {json.dumps(t7['reported_not_scored']['counts'])} (NOT_CONVERGENT_REFERENCE is "
              "neither scored nor a pass; CLOSING_VALVE_XO: sign of a rounding-level valve opening).",
              f"* Non-vacuity (frozen record): {t7['non_vacuity (frozen record)']['ok']}.",
              f"* Unstable stratum scored against the converged Python reference (T2), "
              f"`{t7['divergence_record']}`:", ""]
        for u in t7["unstable_stratum (scored against the converged reference, DIV-P-REF-01)"]:
            fams = "; ".join(f"{f}: scored {d['n_scored']}, NC {d['n_not_convergent']}, max |rust N - py T2| "
                             f"{fmt3(d['max_rust_N_vs_py_T2'])} (bound {fmt3(d['bound'])}), python N "
                             f"{fmt3(d['max_python_N_vs_py_T2 (DIV-P-REF-01)'])}"
                             for f, d in u["families"].items())
            extra = f" P_dev {json.dumps(u['P_dev_max_frac'])}" if "P_dev_max_frac" in u else ""
            L.append(f"  * {u['vector']}: {fams}.{extra}")
        L.append("")
    if "transient_v3" in r:
        er = r["envelope_record"] or {}
        L += ["", "## Transient procedure v3 (A9.31 sec. 5)", "",
              f"* Frozen envelope record `{er.get('path')}` sha256 `{er.get('sha256')}`, committed in "
              f"`{(er.get('commit') or 'NOT COMMITTED')[:12]}` (before any held-out vector was run).",
              "* Bound per leaf: (E_py + E_rust) x s_F + max(4 ulp, 1e-9 |py|); p_inlet_max_Pa: primitive image W + "
              "the same floating allowance; K_min, K_over_K0_max, p_stage_max_Pa, P_el_max_W, T_comp_max_K: reported "
              "with conditioning, scored through their primitives (contract v5).", "",
              "| entry | observable | family | n | fail | max abs diff | max used fraction of the bound |",
              "|---|---|---|---|---|---|---|"]
        for o in r["transient_v3"]["families"]:
            L.append(f"| {o['entry']} | {o['observable'][:70]} | {o['family']} | {o['n']} | {o['n_fail']} | "
                     f"{fmt3(o['max_abs_diff'])} | {fmt3(o.get('max_used_frac'))} |")
        dc = r["transient_v3"]["diagnostic_conditioning"]
        L += ["", f"Cascade diagnostics conditioning kappa = W / (delta |f|): {dc['n']} values, {dc['n_kappa_le_1e2']} "
              f"with kappa <= 1e2, {dc['n_kappa_gt_1e6']} with kappa > 1e6 ({dc['n_kappa_inf']} infinite); "
              f"{dc['n_kappa_round_gt_1e6 (computed digits rounding noise)']} with kappa_round > 1e6 (a 4-ulp change "
              "of the states moves the computed value by more than 1e6 x its 4-ulp scale: the computed digits are "
              "rounding noise). Recorded, no tolerance invented.", ""]
        rep_ = [u for u in r["per_test"]["reported_not_scored"] if any(n in u["observable"] for n in V5_CASCADE)]
        if rep_:
            L += ["Reported with conditioning, scored through their primitives (v5):", ""]
            L += [f"* {u['observable']}: n {u['n']}, max abs diff {fmt3(u['max_abs_diff'])}, max rel diff "
                  f"{fmt3(u['max_rel_diff'])}" for u in rep_]
            L.append("")
        for k, v in r["transient_integrity"].items():
            L.append(f"* {k}: {json.dumps({kk: vv for kk, vv in v.items() if kk != 'failures'})[:300]}")
    L += ["", "## Performance (reported, never a criterion)", ""]
    for w in r["performance"]["workloads"]:
        L.append(f"* {w['id']} ({w['n_vectors']} vectors): Python {w['python_median_s']:.3f} s, Rust "
                 f"{w['rust_median_s']:.3f} s (median of 3; speed-up {w['speedup']:.1f}x; {w['note']}).")
    if r["per_test"]["failures_first_50"]:
        L += ["", "## Failures (first 50)", ""] + [f"* `{json.dumps(x)[:300]}`" for x in r["per_test"]["failures_first_50"]]
    L += ["", "## Notes", ""] + [f"* {n}" for n in r["notes"]]
    L += ["", "## Ledger update requested", ""]
    L += [f"* {x['component']}: {x['requested_status']}" for x in r["ledger_update_requested"]] or ["* none"]
    L += ["", "Parity is not physics validation, not a gate PASS and not a change of any frozen dataset.", ""]
    return "\n".join(L)


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "record-failed-score":
        # record-failed-score <key> <version> <commit> <diagnosis.json>: an execution that crashed before this guard
        key, n, commit, dpath = sys.argv[2], int(sys.argv[3]), sys.argv[4], sys.argv[5]
        contract = load_contract(key, n)[0]
        d = json.load(open(dpath))
        rep = write_failed_execution(key, n, contract["campaign_seeds"]["scoring_master_seed"], d.pop("n_vectors"),
                                     commit, d.pop("diagnosis"), d.pop("notes"))
        print(rep["parity_verdict"], rep["contract"]["id"], "(failed execution recorded)")
        return
    if len(sys.argv) == 3 and sys.argv[1] == "rerender-score" and sys.argv[2] in SPEC:
        key = sys.argv[2]
        res = run_campaign(key, "score", replay=True)
        rep = write_report(key, res, perf(key, res["_capture"]["vectors"]))
        print(rep["parity_verdict"], rep["contract"]["id"], "failures:", rep["per_test"]["n_failures"],
              "(report rebuilt from the captured outputs)")
        return
    if len(sys.argv) == 3 and sys.argv[1:] == ["refine", "plenum"] and v7_on():
        rec = refine_plenum_v7()
        print("ENVELOPE RECORD v7 (frozen):", envelope_path(load_contract("plenum")[0]), "missing:",
              rec["missing_envelopes"], "COMP-P-01:", rec["checks"]["COMP-P-01"]["ok"], "NON_VACUITY:",
              rec["checks"]["NON_VACUITY"]["ok"])
        return
    if len(sys.argv) in (5, 6) and sys.argv[1:3] == ["refine-dev", "plenum"] and v7_on():
        n = int(sys.argv[4])
        seed = int(sys.argv[5]) if len(sys.argv) == 6 else load_contract("plenum")[0]["campaign_seeds"][
            "development_master_seed"]
        u = max(2, n // 4)
        rec = refine_plenum_v7(dev_out=sys.argv[3], dev_master=seed,
                               dev_sizes={"P42": {"PROD": {"S": n, "U": u}, "REF": {"S": max(1, n // 3), "U": 2}},
                                          "P43": {"PROD": {"S": n, "U": u}, "REF": {"S": max(1, n // 3), "U": 2}},
                                          "P45": {"PROD": {"S": n, "U": u}}})
        print("DEVELOPMENT DRAFT v7 (not frozen):", sys.argv[3], "missing:", rec["missing_envelopes"],
              "NON_VACUITY:", rec["checks"]["NON_VACUITY"]["ok"])
        return
    if len(sys.argv) == 3 and sys.argv[1:] == ["refine", "plenum"]:
        rec = refine_plenum()
        print("ENVELOPE RECORD (frozen):", envelope_path(load_contract("plenum")[0]),
              "missing:", rec["missing_envelopes"], "COMP-P-01:", rec["checks"]["COMP-P-01"]["ok"])
        return
    if len(sys.argv) == 5 and sys.argv[1:3] == ["refine-dev", "plenum"]:
        n = int(sys.argv[4])
        rec = refine_plenum(dev_out=sys.argv[3], dev_counts={"P42": {"PROD": n, "REF": max(1, n // 3)},
                                                             "P43": {"PROD": n, "REF": max(1, n // 3)},
                                                             "P45": {"PROD": n}})
        print("DEVELOPMENT DRAFT (not frozen):", sys.argv[3], "missing:", rec["missing_envelopes"])
        return
    if len(sys.argv) < 3 or sys.argv[1] not in ("dev", "dev-report", "score") or sys.argv[2] not in SPEC:
        sys.exit(__doc__)
    mode, key = sys.argv[1], sys.argv[2]
    if mode == "dev-report":
        out_dir = os.path.abspath(sys.argv[3])
        if out_dir.startswith(CDIR):
            sys.exit("dev-report must not write into the contract directory")
        os.makedirs(out_dir, exist_ok=True)
        res = run_campaign(key, "dev", capture=True)
        rep = write_report(key, res, perf(key, res["_capture"]["vectors"]), out_dir)
        print("DEVELOPMENT REPORT (not a verdict):", rep["parity_verdict"], rep["per_test"]["n_failures"], out_dir)
        return
    only = sys.argv[3] if len(sys.argv) > 3 and mode == "dev" else None
    res = run_campaign(key, mode, only=only)
    if res.get("verdict") == "REFUSED_REFERENCE_CHANGED":
        print(json.dumps(res, indent=1))
        sys.exit(2)
    if mode == "dev":
        for o in res["per_test"]["observables"]:
            if o["n_fail"] or (o["tolerance_class"] != "EXACT_VALUE" and o["n_bit_identical"] < o["n"]):
                print(f"{o['entry']:26s} {o['observable'][:70]:70s} {o['tolerance_class'][:6]} n={o['n']:5d} "
                      f"fail={o['n_fail']:3d} bitid={o['n_bit_identical']:5d} max_ulp={o['max_ulp']:.3g} "
                      f"max_rel={o['max_rel_diff']:.3g}")
        for f in res["per_test"]["failures_first_50"][:25]:
            print("FAIL", json.dumps(f)[:500])
        for x in res["errors"]:
            if not x["ok"]:
                print("ERR MISMATCH", json.dumps(x)[:500])
        print(json.dumps({"per_entry": res["per_entry"], "checks": res["checks_extra"],
                          "proximity": res["threshold_proximity"]["entries_over_proximity_limit"],
                          "n_prox": len(res["threshold_proximity"]["records"])}, indent=None)[:3000])
        print(json.dumps({k: res[k] for k in ("determinism", "timing", "pass")}, indent=1))
        print("DEVELOPMENT RUN - not a verdict")
        return
    perf_rows = perf(key, res["_capture"]["vectors"])
    rep = write_report(key, res, perf_rows)
    print(rep["parity_verdict"], rep["contract"]["id"], "failures:", rep["per_test"]["n_failures"])


if __name__ == "__main__":
    main()
