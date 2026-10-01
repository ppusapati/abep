#!/usr/bin/env python3
"""F0 performance baseline: profile before porting (owner directive A9.7 sec. F0; lane fo_a9_7_f0_profiling).

Measures wall-clock (time.perf_counter) and CPU time (time.process_time) plus a cProfile breakdown for documented,
seeded workloads of the existing simulator entry points, unmodified:

  TPMC particle tracing          abep_sim.intake_tpmc.trace_channel / intake_response
  intake response surface        abep_sim.intake_tpmc.response_surface (reduced grid; frozen-build cost extrapolated,
                                 and measured once in full mode)
  compressor search              abep_sim.compressor.DragCompressor.size_for and .run
  whole-system evaluation        abep_sim.system.evaluate (golden case gas_path) and abep_sim.archengine.close_architecture
                                 (golden cases architecture_closure / mission)
  UQ Monte Carlo                 abep_sim.uq_modular.run_uq (one batch of paired mean / solar-min / solar-max samples)
  robust design search           abep_sim.uq6.robust_design (legacy routine; the A9.7 F8 robust optimizer is abep_sim/design/robust_optimizer.py)
  mission propagation            abep_sim.mission5.run_mission_generic -> abep_sim.mission_env.propagate
  P3 ray / view factors          docs/experiments/hall_icp/p3_coupled_thermal/p3_thermal_lib.view_factors at the
                                 builder's verification resolution RES_VERIFY

Nothing here is physics evidence. Timings are software-runtime measurements on the recorded machine; several workloads
drive the superseded 0-D Hall closure, whose absolute results are withdrawn (CLAUDE.md) - they are timed, never quoted.

Usage
  python scripts/perf/profile_baseline.py                 # full baseline (< 20 min), writes docs/performance/*_98fbbb9.*
  python scripts/perf/profile_baseline.py --quick --out-json X.json [--only id1,id2]   # smoke mode (< 2 min)
  python scripts/perf/profile_baseline.py --check          # committed JSON: schema, MD reproduces, specs/sources current
  python scripts/perf/profile_baseline.py --render-md      # regenerate the MD from the committed JSON
  python scripts/perf/profile_baseline.py --rederive       # recompute judgements/ranking from the committed measurements
"""
from __future__ import annotations

import argparse
import cProfile
import ast
import copy
import hashlib
import importlib.util
import json
import math
import os
import platform
import pstats
import statistics
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

SCHEMA = "abep_performance_baseline_v1"
LANE = "fo_a9_7_f0_profiling"
DIRECTIVE = "docs/decisions/OD_2026_10_01_A9_7_ARCHITECTURE_FREEZE_DESIGN_SYNTHESIS.md (sec. F0)"
BASE_COMMIT_LABEL = "98fbbb9"
BASE_COMMIT_NOTE = ("main 98fbbb9 = A9.7 protected baseline. Every profiled source file is byte-identical between 98fbbb9 "
                    "and the measured HEAD (checked at generation, recorded per file); later commits only add docs and "
                    "the empty abep_sim/design package, which is not profiled.")
SCRIPT_REL = "scripts/perf/profile_baseline.py"
OUT_DIR_REL = "docs/performance"
JSON_REL = f"{OUT_DIR_REL}/PERFORMANCE_BASELINE_98fbbb9.json"
MD_REL = f"{OUT_DIR_REL}/PERFORMANCE_BASELINE_98fbbb9.md"
# Historical source-drift record (A9.18 PERF_RERUN): profiled sources changed after measurement by authorised model
# changes; --check reports them as HISTORICAL_SOURCE_DRIFT instead of failing (timings are never re-measured).
DRIFT_REL = "docs/performance/dedicated_baseline_2026_10_01/DRIFT_AFTER_A9_9.json"
TEST_REL = "tests/test_perf_baseline.py"
P3_LIB_REL = "docs/experiments/hall_icp/p3_coupled_thermal/p3_thermal_lib.py"
P3_BUILDER_REL = "docs/experiments/hall_icp/p3_coupled_thermal/build_p3_coupled_thermal.py"

PROFILED_SOURCES = (
    "abep_sim/intake_tpmc.py", "abep_sim/intake.py", "abep_sim/compressor.py", "abep_sim/reservoir.py",
    "abep_sim/system.py", "abep_sim/archengine.py", "abep_sim/uq_modular.py", "abep_sim/uq6.py",
    "abep_sim/mission_env.py", "abep_sim/mission5.py", "abep_sim/atmosphere.py", "abep_sim/plasma_chem.py",
    "abep_sim/plasma_devices.py", "abep_sim/golden.py", P3_LIB_REL, P3_BUILDER_REL,
)

# ------------------------------------------------------------------------------------------------ harness parameters
# Harness choices (not evidence). Thresholds are preregistered here, before the full run, and are an owner question.
REPEATS_FULL = 3
REPEATS_QUICK = 1
PORT_THRESHOLD_S = 60.0       # addressable interpreter time of the reference workload above which a port is a candidate
MARGINAL_THRESHOLD_S = 10.0   # below: not a bottleneck
TOP_N = 15

COMMANDS = {
    "full": "python scripts/perf/profile_baseline.py",
    "quick": "python scripts/perf/profile_baseline.py --quick --out-json <path> [--only <ids>]",
    "check": "python scripts/perf/profile_baseline.py --check",
    "render_md": "python scripts/perf/profile_baseline.py --render-md",
    "rederive": "python scripts/perf/profile_baseline.py --rederive",
    "test": f"python -m pytest -q {TEST_REL}",
}

F0_CATEGORIES = ("tpmc_particle_tracing", "intake_response_surface", "compressor_search", "whole_system_evaluation",
                 "uq_monte_carlo", "robust_design_search", "mission_propagation", "p3_view_factor")

# A9.7 'Rust acceleration admission order' (verbatim list order) mapped to the F0 categories
A9_7_RUST_ORDER = [("TPMC particle-tracing kernel", "tpmc_particle_tracing"),
                   ("large intake geometry-grid generation", "intake_response_surface"),
                   ("compressor design-space search", "compressor_search"),
                   ("Monte-Carlo/full-chain UQ driver", "uq_monte_carlo"),
                   ("mission propagation", "mission_propagation"),
                   ("P3 ray/view-factor sampling", "p3_view_factor")]

SUPERSEDED_NOTE = ("drives the superseded 0-D Hall closure (plasma_devices / archengine Hall branch); absolute Hall "
                   "results are withdrawn (CLAUDE.md 'Superseded / withdrawn') - timed only, outputs never quoted")


def _load_path_module(name, rel):
    spec = importlib.util.spec_from_file_location(name, str(REPO / rel))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def p3_resolutions():
    """RES_VERIFY / RES_STUDY read from the P3 builder source by AST (the builder is not executed)."""
    tree = ast.parse((REPO / P3_BUILDER_REL).read_text())
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id in ("RES_VERIFY", "RES_STUDY"):
                out[node.targets[0].id] = tuple(ast.literal_eval(node.value))
    return out


def _clear_solver_caches():
    """archengine solver caches are pure functions of their keys (CLAUDE.md rule 5); clearing them changes timing only."""
    from abep_sim import archengine as AE
    AE._ION_CACHE.clear(); AE._NEUT_CACHE.clear(); AE._GAS_CACHE.clear()


def _warm_data_caches():
    """Frozen data files (NRLMSIS dataset, TPMC surface CSV) are loaded once, untimed: file I/O is not a compute kernel."""
    from abep_sim.atmosphere import atmosphere
    from abep_sim.intake import _tpmc_surface
    for alt in (180.0, 200.0, 230.0):
        for sol in ("low", "mean", "high"):
            atmosphere(alt, sol)
    _tpmc_surface(atmosphere(200.0, "mean"))


def _sig(x, n=12):
    if isinstance(x, bool) or x is None or isinstance(x, str):
        return x
    if isinstance(x, (int,)):
        return x
    x = float(x)
    if not math.isfinite(x) or x == 0.0:
        return x
    return float(f"{x:.{n}g}")


def _fp(d):
    return {k: _sig(v) for k, v in sorted(d.items())}


# ------------------------------------------------------------------------------------------------ workloads
_SHARED = {}


def _closure_result():
    """Golden case architecture_closure configuration (abep_sim/golden.py case_architecture_closure / case_mission)."""
    from abep_sim import archengine as AE
    from abep_sim.mission_env import Spacecraft
    gf = AE.make_gas_fn(); A = {AE.arch_name(x): x for x in AE.enumerate_architectures()}
    sc = Spacecraft(bus_frontal_m2=0.10, pointing_sigma_deg=0.5)
    r = AE.close_architecture(A["hall_internal+hall+lab6_xe"], gf, sc, AE.DesignConstraints(2500.0),
                              gas_vars={"area": [1.3], "p_level": [0.05]}, size_arrays=True, mission_envelope=True,
                              envelope_margin=1.0, keep_candidates=False)
    return r, gf, sc


def w_tpmc_trace(p):
    import numpy as np
    from abep_sim.atmosphere import atmosphere
    from abep_sim.intake_tpmc import IntakeGeometry, _flux_weighted_entry, trace_channel
    atm = atmosphere(200.0, "mean")
    g = IntakeGeometry(area_m2=0.5, L_over_d=p["L_over_d"], phi=0.85)
    R = g.d_mm * 1e-3 / 2; L = g.L_over_d * g.d_mm * 1e-3

    def run():
        rng = np.random.default_rng(p["seed"])
        v0 = _flux_weighted_entry(rng, p["n"], atm["V"], 0.0, atm["T"], atm["m_mean"])
        col, v, hits, back, unres = trace_channel(rng, v0, R, L, p["alpha"], g.T_wall_K, atm["m_mean"])
        return {"collected_frac": float(col.mean()), "mean_wall_hits": float(hits.mean()), "unresolved": unres}
    return run, p["n"]


def w_tpmc_intake_response(p):
    from abep_sim.atmosphere import atmosphere
    from abep_sim.intake_tpmc import IntakeGeometry, intake_response
    atm = atmosphere(200.0, "mean")

    def run():
        r = intake_response(IntakeGeometry(area_m2=0.5, L_over_d=p["L_over_d"], phi=0.85), atm, p["alpha"], 0.0,
                            n=p["n"], seed=p["seed"])
        return {k: r[k] for k in ("eta_c", "C_D", "K_back", "CR_passive", "mean_wall_hits", "unresolved_fraction")}
    return run, 1


def w_response_surface(p):
    from abep_sim.atmosphere import atmosphere
    from abep_sim.intake_tpmc import response_surface
    atm = atmosphere(200.0, "mean")
    npts = len(p["L_over_d"]) * len(p["phis"]) * len(p["alphas"]) * len(p["thetas"]) * len(p["species"])

    def run():
        df = response_surface(atm, L_over_d=tuple(p["L_over_d"]), phis=tuple(p["phis"]), alphas=tuple(p["alphas"]),
                              thetas=tuple(p["thetas"]), n=p["n"], species=tuple(p["species"]))
        return {"points": int(len(df)), "sum_eta_c": float(df.eta_c.sum()), "sum_C_D": float(df.C_D.sum()),
                "max_unresolved": float(df.unresolved_fraction.max())}
    return run, npts


def w_frozen_build(p):
    """The exact computation of build_frozen_surface (response_surface defaults, n=20000, species O/N2/O2), without
    writing any file."""
    from abep_sim.atmosphere import atmosphere
    from abep_sim.intake_tpmc import response_surface

    def run():
        df = response_surface(atmosphere(200.0, "mean"), n=p["n"], species=("O", "N2", "O2"))
        return {"points": int(len(df)), "sum_eta_c": float(df.eta_c.sum()), "sum_C_D": float(df.C_D.sum())}
    return run, 360


def _golden_compressor_args():
    """Capture the exact size_for inputs of golden case gas_path A0.7 (system.evaluate) by wrapping the method in this
    process only (the module file is not modified)."""
    if "comp_args" in _SHARED:
        return _SHARED["comp_args"]
    from abep_sim import compressor as C
    from abep_sim.system import Config, evaluate
    from abep_sim.intake import IntakeParams, CompressorParams
    orig = C.DragCompressor.size_for
    cap = {}

    def spy(self, p_in_Pa, mdot_species, CR_target, **kw):
        cap.update(p_in_Pa=p_in_Pa, mdot_species=dict(mdot_species), CR_target=CR_target, kw=dict(kw),
                   ctor={k: getattr(self, k) for k in ("turbo_area_m2", "turbo_radius_m", "rotor_material")})
        return orig(self, p_in_Pa, mdot_species, CR_target, **kw)
    C.DragCompressor.size_for = spy
    try:
        evaluate(Config("hall_1stage", 200, "mean", IntakeParams(area_m2=0.7, accommodation=0.8, use_tpmc=True, L_over_d=5),
                        CompressorParams(ratio=2000), vd_V=275, gaspath_physics=True))
    finally:
        C.DragCompressor.size_for = orig
    _SHARED["comp_args"] = cap
    return cap


def w_compressor_size_for(p):
    from abep_sim.compressor import DragCompressor
    a = _golden_compressor_args()

    def run():
        for _ in range(p["calls"]):
            c = DragCompressor(**a["ctor"])
            r = c.size_for(a["p_in_Pa"], a["mdot_species"], CR_target=a["CR_target"])
        return {"sized": r["sized"], "turbo_rows": r["turbo_rows"], "n_stages": r["n_stages"], "rpm": r["rpm"],
                "P_el_W": r["P_el_W"], "mass_kg": r["mass_kg"], "CR_active": r["CR_active"]}
    return run, p["calls"]


def w_compressor_run(p):
    from abep_sim.compressor import DragCompressor
    a = _golden_compressor_args()

    def run():
        c = DragCompressor(**a["ctor"])
        acc = 0.0
        for _ in range(p["calls"]):
            r = c.run(a["p_in_Pa"], a["mdot_species"])
            acc += r["CR_active"]
        return {"calls": p["calls"], "sum_CR_active": acc, "P_el_W": r["P_el_W"]}
    return run, p["calls"]


def w_system_evaluate(p):
    from abep_sim.system import Config, evaluate
    from abep_sim.intake import IntakeParams, CompressorParams

    def run():
        for _ in range(p["calls"]):
            r = evaluate(Config("hall_1stage", 200, "mean", IntakeParams(area_m2=p["area"], accommodation=0.8,
                                                                         use_tpmc=True, L_over_d=5),
                                CompressorParams(ratio=2000), vd_V=275, gaspath_physics=True))
        return {k: r[k] for k in ("eta_c", "C_D", "mdot_air_mgps", "p_in_Pa", "P_comp_W", "drag_mN") if k in r}
    return run, p["calls"]


def w_close_architecture(p):
    def run():
        r, _, _ = _closure_result()
        _SHARED["closure"] = r
        return {k: r.get(k) for k in ("status", "x_Vd", "x_L_ch", "T_mN", "P_bus_W", "ledger_resid")}
    return run, 1


def w_uq_modular(p):
    from abep_sim.uq_modular import run_uq

    def run():
        df, s = run_uq("hall_internal+hall+lab6_xe", {"Vd": 300.0, "L_ch": 0.20}, 1.0, 0.05, 6.0, 1500.0,
                       n=p["n"], seed=p["seed"])
        return {"n": int(len(df)), "P_close": s["P_close"], "P_ignite": s["P_ignite"],
                "ratio_q50": s["ratio_q"][0.5], "sum_T_mN": float(df.T_mN.sum())}
    return run, p["n"]


def w_robust_design(p):
    import pandas as pd
    from abep_sim.uq6 import robust_design
    cand = pd.DataFrame([{"area": 0.7, "L_ch": 0.20, "vd": 275.0, "xe_aug_h": 500.0, "arch": "hall_1stage"}])

    def run():
        df = robust_design(cand, n_mc=p["n_mc"], seed=p["seed"])
        return {"P_mission_ok": float(df.P_mission_ok.iloc[0]), "P_compliant": float(df.P_compliant.iloc[0]),
                "TD_sc_end_p10": float(df.TD_sc_end_p10.iloc[0])}
    return run, p["n_mc"]


def w_mission(p):
    from abep_sim import archengine as AE
    from abep_sim.mission5 import run_mission_generic
    r = _SHARED.get("closure")
    if r is None:
        r, _, _ = _closure_result(); _SHARED["closure"] = r
    from abep_sim.mission_env import Spacecraft
    gf = AE.make_gas_fn()
    sc = Spacecraft(bus_frontal_m2=0.10, pointing_sigma_deg=0.5)
    pm = AE.propulsion_map(r, gf)
    scm = copy.copy(sc); scm.array_area_m2 = r["A_array_m2"]
    gas = gf(r["x_area"], r["x_p_level"])
    steps = int(p["hours"] / p["dt_h"])

    def run():
        m = run_mission_generic(r, scm, gas, hours=p["hours"], dt_h=p["dt_h"], pmap=pm, P_bus_max_W=2500.0)
        return {k: m[k] for k in ("mission_closed", "min_alt_km", "D_mean_mN", "T_mean_mN", "fired_hours")}
    return run, steps


def w_p3_view_factors(p):
    lib = sys.modules.get("p3_thermal_lib_perf") or _load_path_module("p3_thermal_lib_perf", P3_LIB_REL)
    B = lib.Body
    res = tuple(p["res"])

    calls = p.get("calls", 1)

    def run():
        # the builder's full two-body enclosure of closed_form_verification() (SYNTHETIC geometry, method check only)
        for _ in range(calls):
            full = lib.view_factors([B("H", 0, 0.8, -0.5, 0), B("I", 0.5, 1.0, 0.3, 0.8)], res)
        summ = max(abs(sum(full["F"][i].values()) - 1.0) for i in full["surfaces"])
        return {"surfaces": len(full["surfaces"]), "F_H.down_I.up": full["F"]["H.down"]["I.up"],
                "reciprocity_max_rel": full["reciprocity_max_rel"], "summation_max_abs": summ,
                "rays_per_call": len(p["emitting_zones"]) * res[0] * res[1] * res[2]}
    return run, calls


def workload_specs(mode):
    q = mode == "quick"
    res = p3_resolutions()
    rs_full = {"L_over_d": [3, 5, 10, 20], "phis": [0.8], "alphas": [0.0, 0.5, 1.0], "thetas": [0.0], "species": ["N2"],
               "n": 20000}
    rs_quick = {"L_over_d": [3, 20], "phis": [0.8], "alphas": [0.0, 1.0], "thetas": [0.0], "species": ["N2"], "n": 1000}
    W = [
        {"id": "tpmc_trace_channel", "category": "tpmc_particle_tracing", "fn": w_tpmc_trace,
         "entry_point": "abep_sim.intake_tpmc.trace_channel (forward trace; entry from _flux_weighted_entry)",
         "description": "forward test-particle trace through one honeycomb channel, 200 km mean NRLMSIS (frozen), "
                        "mean molecular mass, L/d 5, d 10 mm, Maxwell alpha 0.8, theta 0",
         "params": {"n": 2000 if q else 20000, "L_over_d": 5.0, "alpha": 0.8, "seed": 11},
         "unit_of_work": "particles", "covered_by": "intake_response_surface_reduced",
         "reference": None,
         "scaling_probe": {"param": "n", "values": [1000, 4000] if q else [2000, 20000]}},
        {"id": "tpmc_intake_response", "category": "tpmc_particle_tracing", "fn": w_tpmc_intake_response,
         "entry_point": "abep_sim.intake_tpmc.intake_response",
         "description": "one response point = forward trace (n particles) + Clausing back-transmission (fixed n=20000 "
                       "in clausing_transmission) + momentum/mass bookkeeping; L/d 5, phi 0.85, alpha 0.8, theta 0",
         "params": {"n": 2000 if q else 20000, "L_over_d": 5.0, "alpha": 0.8, "seed": 0},
         "unit_of_work": "response points", "covered_by": "intake_response_surface_reduced", "reference": None},
        {"id": "intake_response_surface_reduced", "category": "intake_response_surface", "fn": w_response_surface,
         "entry_point": "abep_sim.intake_tpmc.response_surface",
         "description": "reduced product grid of the frozen-build axes (all four L/d, three alphas spanning 0..1, one "
                        "phi, theta 0, species N2) at the frozen-build particle count",
         "params": rs_quick if q else rs_full, "unit_of_work": "response points", "covered_by": None,
         "reference": {"id": "frozen_intake_surface_build", "units_of_work": 360,
                       "basis": "abep_sim/intake_tpmc.py build_frozen_surface: response_surface defaults 4 L/d x 2 phi x "
                                "5 alpha x 3 theta x 3 species = 360 points at n=20000 (python -m abep_sim.intake_tpmc build)",
                       "method": "EXTRAPOLATED: median seconds per reduced-grid point x 360 (per-point cost varies with "
                                 "L/d, alpha, theta and species mass; the reduced grid samples L/d and alpha only)" +
                                 ("" if q else "; checked against one direct measurement (frozen_intake_surface_build)")}},
        {"id": "compressor_size_for", "category": "compressor_search", "fn": w_compressor_size_for,
         "entry_point": "abep_sim.compressor.DragCompressor.size_for",
         "description": "exhaustive turbo-rows x drag-stages x rpm search (default bounds) with the exact inputs that "
                        "golden case gas_path A0.7 passes (captured in-process from system.evaluate)",
         "params": {"calls": 5 if q else 20}, "unit_of_work": "size_for calls", "covered_by": None,
         "reference": {"id": "uq6_pareto_default", "units_of_work": 200,
                       "basis": "abep_sim/uq6.py pareto(n_designs=200) and monte_carlo6(n=200) defaults: one "
                                "system.evaluate -> one size_for per design/sample; the F3 synthesis search is PENDING "
                                "abep_sim/design/compressor_synthesis.py",
                       "method": "EXTRAPOLATED: median seconds per call x 200"}},
        {"id": "compressor_run", "category": "compressor_search", "fn": w_compressor_run,
         "entry_point": "abep_sim.compressor.DragCompressor.run (self-consistent leak iteration)",
         "description": "repeated operating-point evaluations at the golden gas_path A0.7 inputs and default geometry",
         "params": {"calls": 50 if q else 500}, "unit_of_work": "run calls", "covered_by": "compressor_size_for",
         "reference": None},
        {"id": "system_evaluate_gas_path", "category": "whole_system_evaluation", "fn": w_system_evaluate,
         "entry_point": "abep_sim.system.evaluate (golden case gas_path A0.7)",
         "description": "Config('hall_1stage', 200 km, mean, TPMC intake A 0.7 m2 alpha 0.8 L/d 5, ratio 2000, Vd 275, "
                        "gaspath_physics=True) exactly as abep_sim/golden.py case_gas_path",
         "params": {"area": 0.7, "calls": 5 if q else 20}, "unit_of_work": "evaluations", "covered_by": None,
         "reference": {"id": "uq6_monte_carlo_default", "units_of_work": 200,
                       "basis": "abep_sim/uq6.py monte_carlo6(n=200) default (one system.evaluate per sample; that path "
                                "also enables plasma/engineering physics, so this is a lower bound per sample)",
                       "method": "EXTRAPOLATED: median seconds per evaluation x 200"}},
        {"id": "archengine_close_architecture", "category": "whole_system_evaluation", "fn": w_close_architecture,
         "entry_point": "abep_sim.archengine.close_architecture (golden cases architecture_closure and mission)",
         "description": "nested constrained closure of hall_internal+hall+lab6_xe at 2.5 kW, area 1.3, p_level 0.05, "
                        "arrays sized, mission envelope; solver caches cleared before every repeat (cold)",
         "params": {}, "unit_of_work": "closures", "covered_by": None, "physics_note": SUPERSEDED_NOTE,
         "reference": {"id": "golden_check", "units_of_work": 2,
                       "basis": "abep_sim/golden.py: case_architecture_closure and case_mission each run this closure "
                                "once per python -m abep_sim.golden check (CLAUDE.md rule 2 gate)",
                       "method": "EXTRAPOLATED: median seconds x 2 (the second call shares no cache in a cold process "
                                 "only if caches are cleared; in practice it is warm, so this is an upper bound)"}},
        {"id": "uq_modular_run_uq", "category": "uq_monte_carlo", "fn": w_uq_modular,
         "entry_point": "abep_sim.uq_modular.run_uq",
         "description": "one batch of paired samples (each sample re-runs propulsion at mean / solar-min / solar-max "
                        "captured flow with shared prior draws) for hall_internal+hall+lab6_xe, Vd 300, L_ch 0.20, "
                        "area 1.0, p_level 0.05, A_array 6, P_cap 1500 (tests/test_sim.py test_v131_modular_uq_runs)",
         "params": {"n": 2 if q else 6, "seed": 1}, "unit_of_work": "paired samples", "covered_by": None,
         "physics_note": SUPERSEDED_NOTE,
         "reference": {"id": "run_uq_default", "units_of_work": 200,
                       "basis": "abep_sim/uq_modular.py run_uq(n=200) default",
                       "method": "EXTRAPOLATED: median seconds per sample x 200"}},
        {"id": "uq6_robust_design", "category": "robust_design_search", "fn": w_robust_design,
         "entry_point": "abep_sim.uq6.robust_design (only robust-design routine in the base; A9.7 F7/F8 optimizer "
                        "not yet built)",
         "description": "one candidate design (area 0.7, L_ch 0.20, Vd 275, xe_aug_h 500, hall_1stage) through "
                        "monte_carlo6 (correlated priors, full chain + mission ROM)",
         "params": {"n_mc": 1 if q else 3, "seed": 5}, "unit_of_work": "MC samples", "covered_by": None,
         "physics_note": SUPERSEDED_NOTE,
         "reference": {"id": "robust_design_default_per_candidate", "units_of_work": 60,
                       "basis": "abep_sim/uq6.py robust_design(n_mc=60) default, per candidate (candidate count is "
                                "set by the caller; F8 robust optimisation is PENDING, lane fo_a9_7_f7_f8_coupled_optimizer)",
                       "method": "EXTRAPOLATED: median seconds per sample x 60 (one candidate)"}},
        {"id": "mission_run_generic", "category": "mission_propagation", "fn": w_mission,
         "entry_point": "abep_sim.mission5.run_mission_generic -> abep_sim.mission_env.propagate",
         "description": "secular J2 / energy-balance propagator (orbit-averaged: no intra-orbit resolution, so 'one "
                        "orbit-day' = 24 h / dt_h steps) with TPMC-ROM intake and AO ageing per step; golden case_mission "
                        "set-up (closure result reused, propulsion map, P_bus_max 2500 W)",
         "params": {"hours": 4000.0 if q else 26000.0, "dt_h": 6.0}, "unit_of_work": "propagator steps",
         "covered_by": None, "physics_note": SUPERSEDED_NOTE + " (the closure feeds the thrust map)",
         "reference": {"id": "rfp_mission_26000h", "units_of_work": int(26000.0 / 6.0),
                       "basis": "abep_sim/constants.py RFP.mission_hours = 26000 h at dt_h 6 (run_mission_generic default)",
                       "method": ("EXTRAPOLATED: median seconds per step x 4333" if q else
                                  "MEASURED directly (the full-mode workload is the 26000 h mission)")},
         "setup_note": "closure computed once in set-up (untimed) unless archengine_close_architecture ran first"},
        {"id": "p3_view_factors_verify", "category": "p3_view_factor", "fn": w_p3_view_factors,
         "entry_point": f"{P3_LIB_REL}::view_factors",
         "description": "full two-body enclosure of the P3 builder's closed_form_verification() (SYNTHETIC normalized "
                        "geometry, every zone emits; 7 zones) at the verification resolution RES_VERIFY read from "
                        f"{P3_BUILDER_REL}",
         "params": {"res": list((4, 8, 16) if q else res["RES_VERIFY"]), "res_source": "RES_VERIFY" if not q else
                    "quick smoke resolution (not the verification resolution)",
                    "emitting_zones": ["H.up", "H.down", "H.outer", "I.up", "I.down", "I.outer", "I.bore"]},
         "unit_of_work": "view_factors calls", "covered_by": None,
         "reference": {"id": "p3_closed_form_verification", "units_of_work": 1,
                       "basis": "build_p3_coupled_thermal.py closed_form_verification(): this full-enclosure call plus "
                                "six single-emitter calls (one emitting zone each) at RES_VERIFY; the parametric study "
                                "runs at RES_STUDY and is not extrapolated here",
                       "method": "EXTRAPOLATED: median seconds per full-enclosure call x 1 (the six single-emitter "
                                 "calls of the same function are not included)"},
         "scaling_probe": {"param": "res", "values": [[4, 8, 16], [8, 16, 32]] if q else
                           [list(res["RES_STUDY"]), list(res["RES_VERIFY"])]}},
    ]
    if not q:
        W.append({"id": "frozen_intake_surface_build", "category": "intake_response_surface", "fn": w_frozen_build,
                  "entry_point": "abep_sim.intake_tpmc.response_surface (exact computation of build_frozen_surface)",
                  "description": "the complete frozen intake-surface computation (360 points, n=20000, species O/N2/O2); "
                                 "no file is written; one repeat only (checks the reduced-grid extrapolation)",
                  "params": {"n": 20000}, "unit_of_work": "response points", "covered_by":
                  "intake_response_surface_reduced", "reference": None, "repeats_override": 1, "cprofile": False})
    return W


def spec_public(w):
    return {k: v for k, v in w.items() if k != "fn"}


def spec_hash(specs):
    return hashlib.sha256(json.dumps([spec_public(w) for w in specs], sort_keys=True).encode()).hexdigest()


# ------------------------------------------------------------------------------------------------ measurement
def _classify(filename, funcname):
    if filename == "~":
        low = funcname.lower()
        if any(s in low for s in ("numpy", "ufunc", "ndarray", "pandas", "scipy", "_multiarray", "generator")):
            return "native_array_call"
        return "interpreter_builtin"
    f = filename.replace("\\", "/")
    for lib in ("/numpy/", "/pandas/", "/scipy/"):
        if lib in f:
            return "library_python_wrapper"
    if f.startswith(str(REPO)):
        return "project_python"
    return "stdlib_python"


def _short(filename):
    f = filename.replace("\\", "/")
    if f.startswith(str(REPO)):
        return os.path.relpath(f, REPO)
    if "site-packages/" in f:
        return "site-packages/" + f.split("site-packages/", 1)[1]
    return f


def profile_once(run):
    prof = cProfile.Profile()
    t0 = time.perf_counter()
    prof.enable(); run(); prof.disable()
    wall = time.perf_counter() - t0
    st = pstats.Stats(prof)
    me = os.path.abspath(__file__)
    cats = {k: 0.0 for k in ("project_python", "interpreter_builtin", "stdlib_python", "library_python_wrapper",
                             "native_array_call")}
    rows = []
    total_calls = 0
    for (fn, line, name), (cc, nc, tt, ct, callers) in st.stats.items():
        if os.path.abspath(fn) == me:
            continue
        cats[_classify(fn, name)] += tt
        total_calls += nc
        rows.append({"function": f"{_short(fn)}:{line}({name})" if fn != "~" else name, "ncalls": nc,
                     "tottime_s": tt, "cumtime_s": ct, "class": _classify(fn, name)})
    tot = sum(cats.values()) or 1e-30
    frac = {k: round(v / tot, 4) for k, v in cats.items()}
    top_cum = sorted(rows, key=lambda r: -r["cumtime_s"])[:TOP_N]
    top_tot = sorted(rows, key=lambda r: -r["tottime_s"])[:TOP_N]
    for r in top_cum + top_tot:
        r["tottime_s"] = round(r["tottime_s"], 4); r["cumtime_s"] = round(r["cumtime_s"], 4)
    hot = [r["function"] for r in sorted(rows, key=lambda r: -r["tottime_s"]) if r["class"] == "project_python"][:5]
    interp = frac["project_python"] + frac["interpreter_builtin"] + frac["stdlib_python"]
    return {"profiled_wall_s": round(wall, 4), "total_function_calls": total_calls,
            "function_calls_per_profiled_s": round(total_calls / max(wall, 1e-9), 1),
            "tottime_fractions": frac, "interpreter_level_fraction": round(interp, 4),
            "numpy_level_fraction": round(frac["native_array_call"] + frac["library_python_wrapper"], 4),
            "top_by_cumulative": top_cum, "top_by_tottime": top_tot, "project_hotspots_by_tottime": hot}


def _git(*args):
    try:
        return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return None


def measure(w, repeats, do_profile=True):
    run, units = w["fn"](w["params"])
    walls, cpus, fps = [], [], []
    load0 = os.getloadavg()
    for _ in range(w.get("repeats_override", repeats)):
        _clear_solver_caches()
        t0, c0 = time.perf_counter(), time.process_time()
        out = run()
        walls.append(time.perf_counter() - t0); cpus.append(time.process_time() - c0)
        fps.append(_fp(out))
    load1 = os.getloadavg()
    rec = {"repeats": len(walls), "wall_s": [round(x, 4) for x in walls], "cpu_s": [round(x, 4) for x in cpus],
           "median_wall_s": round(statistics.median(walls), 4), "median_cpu_s": round(statistics.median(cpus), 4),
           "cpu_over_wall": round(statistics.median(cpus) / max(statistics.median(walls), 1e-9), 3),
           "units_of_work": units,
           "median_wall_s_per_unit": (round(statistics.median(walls) / units, 7) if units else None),
           "loadavg_1min_before_after": [round(load0[0], 2), round(load1[0], 2)],
           "output_fingerprint": fps[0], "deterministic_across_repeats": all(f == fps[0] for f in fps)}
    if do_profile and w.get("cprofile", True):
        _clear_solver_caches()
        pr = profile_once(run)
        pr["cprofile_overhead_ratio"] = round(pr["profiled_wall_s"] / max(rec["median_wall_s"], 1e-9), 3)
        rec["profile"] = pr
    if w.get("scaling_probe"):
        sp = w["scaling_probe"]; pts = []
        for val in sp["values"]:
            p2 = dict(w["params"]); p2[sp["param"]] = val
            r2, _ = w["fn"](p2)
            ts = []
            for _ in range(max(1, min(repeats, 3))):
                t0 = time.perf_counter(); r2(); ts.append(time.perf_counter() - t0)
            pts.append({sp["param"]: val, "median_wall_s": round(statistics.median(ts), 4)})
        size = [(v if isinstance(v, (int, float)) else v[0] * v[1] * v[2]) for v in sp["values"]]
        work_ratio = size[-1] / size[0]; time_ratio = pts[-1]["median_wall_s"] / max(pts[0]["median_wall_s"], 1e-9)
        rec["scaling_probe"] = {"points": pts, "work_ratio": round(work_ratio, 3), "time_ratio": round(time_ratio, 3),
                                "time_ratio_over_work_ratio": round(time_ratio / work_ratio, 3),
                                "reading": "close to 1: cost scales with array size (numpy-level work dominates); "
                                           "well below 1: fixed per-call / per-step interpreter overhead dominates"}
    return rec


# ------------------------------------------------------------------------------------------------ judgement
def judge(w, rec, by_id):
    """Port-candidate judgement from measured quantities only. Gain x usage = interpreter-level share (cProfile tottime)
    x extrapolated/measured seconds of the stated reference workload.

    Basis correction (consolidated verification round 1, F0-01): the interpreter-level share is project + builtin +
    stdlib only; it EXCLUDES library_python_wrapper (numpy / pandas / scipy Python wrappers), which a native kernel
    also removes. The value stored under the historical key 'addressable_interpreter_s_upper_bound' is therefore an
    interpreter-only ESTIMATE, not an upper bound (the measured Rust speed-ups exceed it). The key and the committed
    JSON are kept unchanged because docs/performance/abep_core/parity_prereg_v1.json pins the JSON's sha256; the
    rendered MD states the correction and the wrapper-inclusive estimate (render_md, basis_correction_lines)."""
    if w.get("covered_by"):
        return {"judgement": "COVERED_BY", "covered_by": w["covered_by"],
                "basis": "kernel-level measurement; ranked through the workload that calls it (avoids double counting)"}
    ref = w.get("reference")
    prof = rec.get("profile")
    if ref is None or prof is None:
        return {"judgement": "NOT_RANKED", "basis": "no reference workload or no profile"}
    units = ref["units_of_work"]
    per = rec["median_wall_s_per_unit"]
    if units is None or per is None:
        ref_s = rec["median_wall_s"]
    elif ref["method"].startswith("MEASURED"):
        ref_s = rec["median_wall_s"]
    else:
        ref_s = per * units
    if w["id"] == "intake_response_surface_reduced" and "frozen_intake_surface_build" in by_id:
        ref_s_meas = by_id["frozen_intake_surface_build"]["median_wall_s"]
    else:
        ref_s_meas = None
    interp = prof["interpreter_level_fraction"]
    addr = ref_s * interp
    if addr >= PORT_THRESHOLD_S:
        j = "PORT_CANDIDATE"
    elif addr >= MARGINAL_THRESHOLD_S:
        j = "MARGINAL"
    else:
        j = "NOT_A_BOTTLENECK"
    out = {"reference_workload_id": ref["id"], "reference_workload_s": round(ref_s, 2),
           "reference_workload_s_measured": (round(ref_s_meas, 2) if ref_s_meas is not None else None),
           "interpreter_level_fraction": interp,
           "addressable_interpreter_s_upper_bound": round(addr, 2), "judgement": j,
           "thresholds_s": {"port": PORT_THRESHOLD_S, "marginal": MARGINAL_THRESHOLD_S}}
    if w.get("physics_note"):
        out["qualifier"] = ("DEFER_PORT: " + w["physics_note"] + "; porting a driver of withdrawn physics adds no "
                            "decision value - re-profile the F7/F8 driver once it exists")
    sp = rec.get("scaling_probe")
    if sp:
        out["scaling_time_over_work"] = sp["time_ratio_over_work_ratio"]
    return out


def ranking(workloads, by_id):
    rows = []
    for w in workloads:
        j = by_id[w["id"]]["port_judgement"]
        if "addressable_interpreter_s_upper_bound" in j:
            rows.append({"id": w["id"], "category": w["category"],
                         "addressable_interpreter_s_upper_bound": j["addressable_interpreter_s_upper_bound"],
                         "reference_workload_s": j["reference_workload_s"], "judgement": j["judgement"],
                         "deferred": "qualifier" in j})
    rows.sort(key=lambda r: -r["addressable_interpreter_s_upper_bound"])
    for i, r in enumerate(rows):
        r["rank"] = i + 1
    return rows


def rust_order_comparison(rank_rows, workloads=()):
    pos, by_id = {}, {r["id"]: r for r in rank_rows}
    for r in rank_rows:
        pos.setdefault(r["category"], r)
    via = {}
    for w in workloads:   # kernel-level categories are ranked through the workload that calls them
        if w["category"] not in pos and w.get("covered_by") in by_id:
            via.setdefault(w["category"], (w["id"], by_id[w["covered_by"]]))
    out = []
    for i, (name, cat) in enumerate(A9_7_RUST_ORDER):
        r = pos.get(cat); note = None
        if r is None and cat in via:
            kid, r = via[cat]
            note = f"{kid} is a kernel of {r['id']} (COVERED_BY); rank shown is that workload's"
        out.append({"a9_7_position": i + 1, "a9_7_item": name, "f0_category": cat,
                    "f0_rank": r["rank"] if r else None, "f0_judgement": r["judgement"] if r else None,
                    "f0_deferred": r["deferred"] if r else None, "via": note})
    return out


# ------------------------------------------------------------------------------------------------ environment
def environment():
    import numpy, scipy, pandas
    cpu = None
    try:
        for line in open("/proc/cpuinfo"):
            if line.startswith("model name"):
                cpu = line.split(":", 1)[1].strip(); break
    except OSError:
        pass
    blas = {}
    try:
        cfg = numpy.show_config(mode="dicts")
        bd = cfg.get("Build Dependencies", {})
        for k in ("blas", "lapack"):
            if k in bd:
                blas[k] = {kk: bd[k].get(kk) for kk in ("name", "version", "openblas configuration") if bd[k].get(kk)}
    except Exception as e:   # noqa: BLE001 - record, never fail the measurement on metadata
        blas = {"error": str(e)[:120]}
    try:
        aff = len(os.sched_getaffinity(0))
    except AttributeError:
        aff = None
    return {"cpu_model": cpu or platform.processor() or "unknown", "logical_cpus": os.cpu_count(),
            "cpus_available_to_process": aff, "machine": platform.machine(), "os": platform.system() + " " +
            platform.release(), "python": sys.version.split()[0], "python_implementation": platform.python_implementation(),
            "numpy": numpy.__version__, "scipy": scipy.__version__, "pandas": pandas.__version__, "blas": blas,
            "thread_env": {k: os.environ.get(k) for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")},
            "loadavg_at_start": [round(x, 2) for x in os.getloadavg()],
            "concurrency_note": "measured on a shared machine; other A9.7 lane worktrees may run concurrently - per-workload "
                                "1-minute load averages are recorded; treat timings as +-tens of percent, ranking as "
                                "order-of-magnitude"}


def sources_record():
    out = []
    for rel in PROFILED_SOURCES:
        b = (REPO / rel).read_bytes()
        at_base = _git("rev-parse", f"{BASE_COMMIT_LABEL}:{rel}")
        blob = _git("hash-object", rel)
        out.append({"path": rel, "sha256": hashlib.sha256(b).hexdigest(), "git_blob": blob,
                    "identical_to_98fbbb9": (blob == at_base) if (blob and at_base) else None})
    return out


# ------------------------------------------------------------------------------------------------ document sections
def parameters_section(mode):
    def P(i, v, u, basis):
        return {"id": i, "value": v, "units": u, "basis": basis, "source": SCRIPT_REL,
                "evidence_class": "assumed (harness choice, not physics evidence)", "status": "DEFINED"}
    return [P("F0-P-01", REPEATS_FULL if mode == "full" else REPEATS_QUICK, "repeats",
              "A9.7 F0 lane brief: median of >= 3 repeats (full mode); quick mode is a smoke run"),
            P("F0-P-02", PORT_THRESHOLD_S, "s", "addressable interpreter time of the reference workload above which a "
              "native port is a candidate (preregistered before the full run)"),
            P("F0-P-03", MARGINAL_THRESHOLD_S, "s", "below: not a bottleneck"),
            P("F0-P-04", TOP_N, "functions", "cProfile rows kept per list"),
            P("F0-P-05", "cleared before every repeat", "-", "archengine _ION_CACHE/_NEUT_CACHE/_GAS_CACHE (pure functions of "
              "their keys, rule 5): cold-solver timing; frozen data files warmed once untimed")]


def interface_demands():
    return [
        {"id": "F0-ID-01", "direction": "F0 -> rust", "counterparty": "fo_a9_7_rust_kernels (PENDING abep_core/)",
         "demand": "port only workloads ranked PORT_CANDIDATE without a DEFER qualifier; keep a Python wrapper with "
                   "identical I/O; re-run this harness (same commands) on the Rust-enabled tree and report the same keys",
         "status": "OPEN"},
        {"id": "F0-ID-02", "direction": "rust -> F0", "counterparty": "fo_a9_7_rust_kernels (PENDING abep_core/)",
         "demand": "for every admitted kernel: the preregistered numerical tolerance and the Python-reference vs Rust "
                   "parity record, so the post-port baseline can cite them", "status": "PENDING"},
        {"id": "F0-ID-03", "direction": "F1 -> F0", "counterparty": "fo_a9_7_f1_intake_synthesis (PENDING "
         "abep_sim/design/intake_synthesis.py)",
         "demand": "the number of intake_response / response_surface points and the particle count per candidate of the "
                   "F1 Pareto search, so the TPMC usage weight can be replaced by the real F1 call count",
         "status": "PENDING"},
        {"id": "F0-ID-04", "direction": "F3 -> F0", "counterparty": "fo_a9_7_f3_compressor_synthesis (PENDING "
         "abep_sim/design/compressor_synthesis.py)",
         "demand": "the number of DragCompressor.run evaluations per F3 design search", "status": "PENDING"},
        {"id": "F0-ID-05", "direction": "F7/F8 -> F0", "counterparty": "fo_a9_7_f7_f8_coupled_optimizer (path not yet "
         "registered)", "demand": "the F7/F8 driver entry point and sample counts; the UQ / robust-design workloads here "
                                  "time legacy drivers of withdrawn 0-D Hall physics and must be re-profiled on the new "
                                  "driver before any port decision", "status": "PENDING"},
        {"id": "F0-ID-06", "direction": "F6 -> F0", "counterparty": "fo_a9_7_f6_icp_geometry (PENDING "
         "abep_sim/design/icp_geometry_synthesis.py)",
         "demand": "view-factor calls per ICP geometry candidate and their resolution (the F6 search waits for P1/P2 "
                   "evidence)", "status": "PENDING"},
        {"id": "F0-ID-07", "direction": "F0 -> F1/F3/F6/F7", "counterparty": "all A9.7 synthesis lanes",
         "demand": "measured per-call costs (median_wall_s_per_unit) for budgeting search sizes; values are machine-"
                   "specific runtimes, never physics inputs", "status": "SUPPLIED"},
    ]


def open_owner_questions():
    return [{"id": "F0-OQ-01",
             "question": "Accept the preregistered port thresholds (PORT_CANDIDATE >= 60 s, MARGINAL >= 10 s of "
                         "addressable interpreter time per reference workload) or set others before the Rust lane "
                         "selects kernels?", "default_if_unanswered": "thresholds as registered; Rust lane may not port "
                         "a NOT_A_BOTTLENECK workload"},
            {"id": "F0-OQ-02",
             "question": "Should the baseline be re-measured on a dedicated (unloaded) machine before a Rust kernel is "
                         "admitted, given that this run shared the CPU with other A9.7 lanes?",
             "default_if_unanswered": "rankings are used as order-of-magnitude only; the Rust lane re-measures "
                                      "Python vs Rust on the same machine in one session"}]


def m16_impact():
    return [{"m16_row": None, "state_change": "none - F0 measures software runtime only; no requirement, evidence or "
                                              "gate status changes"}]


# ------------------------------------------------------------------------------------------------ build
REQUIRED_TOP = ("schema", "lane", "directive", "mode", "base_commit_label", "base_commit_note", "measured_head",
                "generated_utc_date", "commands", "environment", "profiled_sources", "workload_spec_sha256", "parameters",
                "workloads", "ranking", "rust_order_comparison", "robust_design_search_status", "findings",
                "interface_demands", "open_owner_questions", "m16_impact", "what_this_is_not", "total_harness_wall_s")
REQUIRED_WORKLOAD = ("id", "category", "entry_point", "description", "params", "unit_of_work", "repeats", "wall_s",
                     "cpu_s", "median_wall_s", "median_cpu_s", "output_fingerprint", "deterministic_across_repeats",
                     "port_judgement")
REQUIRED_PROFILE = ("tottime_fractions", "interpreter_level_fraction", "numpy_level_fraction", "top_by_cumulative",
                    "project_hotspots_by_tottime", "total_function_calls")


def build(mode, only=None):
    t_start = time.perf_counter()
    _warm_data_caches()
    specs = workload_specs(mode)
    if only:
        unknown = set(only) - {w["id"] for w in specs}
        if unknown:
            raise SystemExit(f"unknown workload ids {sorted(unknown)}")
        specs = [w for w in specs if w["id"] in only]
    repeats = REPEATS_FULL if mode == "full" else REPEATS_QUICK
    by_id = {}
    for w in specs:
        t0 = time.perf_counter()
        rec = measure(w, repeats)
        by_id[w["id"]] = {**spec_public(w), **rec}
        print(f"[F0] {w['id']}: median wall {rec['median_wall_s']} s ({time.perf_counter() - t0:.1f} s incl. profile)",
              flush=True)
    head = _git("rev-parse", "HEAD")
    doc = {
        "schema": SCHEMA, "lane": LANE, "directive": DIRECTIVE, "mode": mode,
        "base_commit_label": BASE_COMMIT_LABEL, "base_commit_note": BASE_COMMIT_NOTE, "measured_head": head,
        "generated_utc_date": time.strftime("%Y-%m-%d", time.gmtime()),
        "commands": COMMANDS, "environment": environment(), "profiled_sources": sources_record(),
        "workload_spec_sha256": spec_hash(workload_specs(mode)), "parameters": parameters_section(mode),
        "workloads": [by_id[w["id"]] for w in specs], "ranking": None, "rust_order_comparison": None,
        "robust_design_search_status": {
            "exists_in_base": True, "routine": "abep_sim.uq6.robust_design (legacy phase-6 routine over the superseded "
            "0-D Hall chain)", "a9_7_f8_robust_optimizer": "PENDING (lane fo_a9_7_f7_f8_coupled_optimizer; not in base)"},
        "findings": None,
        "interface_demands": interface_demands(), "open_owner_questions": open_owner_questions(),
        "m16_impact": m16_impact(),
        "what_this_is_not": ["physics evidence of any kind", "a performance requirement or acceptance criterion",
                             "a quotation of any Hall, thrust or mission result (several workloads drive withdrawn 0-D "
                             "Hall physics; outputs appear only as determinism fingerprints)",
                             "a port decision (the Rust lane decides within the A9.7 admission rules)"],
        "total_harness_wall_s": None,
    }
    derive(doc)
    doc["total_harness_wall_s"] = round(time.perf_counter() - t_start, 1)
    return doc


def derive(doc):
    """Judgements, ranking, Rust-order comparison and findings are pure functions of the measured workload records
    (recomputed by --check to prove the committed derived sections follow from the committed measurements)."""
    ws = doc["workloads"]
    by_id = {w["id"]: w for w in ws}
    for w in ws:
        w["port_judgement"] = judge(w, w, by_id)
    rk = ranking(ws, by_id)
    doc["ranking"] = rk
    doc["rust_order_comparison"] = rust_order_comparison(rk, ws)
    doc["findings"] = findings(ws, by_id, rk)
    return doc


def findings(specs, by_id, rk):
    out = []
    for r in rk:
        w = by_id[r["id"]]; j = w["port_judgement"]; pr = w.get("profile", {})
        out.append(f"{r['rank']}. {r['id']}: reference workload {j['reference_workload_id']} ~ {j['reference_workload_s']} s; "
                   f"interpreter-level share {j['interpreter_level_fraction']}; addressable <= "
                   f"{j['addressable_interpreter_s_upper_bound']} s -> {j['judgement']}"
                   + (" (DEFER: legacy driver of withdrawn physics)" if "qualifier" in j else "")
                   + (f"; hotspots {', '.join(pr.get('project_hotspots_by_tottime', [])[:3])}" if pr else ""))
    fz = by_id.get("frozen_intake_surface_build"); rs = by_id.get("intake_response_surface_reduced")
    if fz and rs:
        ext = rs["port_judgement"]["reference_workload_s"]
        out.append(f"Frozen intake-surface build measured once at {fz['median_wall_s']} s vs {ext} s extrapolated from "
                   f"the reduced grid (ratio {round(fz['median_wall_s'] / max(ext, 1e-9), 2)}).")
    for wid in ("tpmc_trace_channel", "p3_view_factors_verify"):
        w = by_id.get(wid)
        if w and w.get("scaling_probe"):
            sp = w["scaling_probe"]
            kind = ("array work dominates" if sp["time_ratio_over_work_ratio"] >= 0.7 else
                    "fixed per-step / per-call interpreter overhead is a large share at the smaller size")
            out.append(f"Scaling probe {wid}: {sp['work_ratio']}x more work cost {sp['time_ratio']}x more time "
                       f"(time/work {sp['time_ratio_over_work_ratio']}): {kind}.")
    per = [f"{w['id']} {w['median_wall_s_per_unit']} s per {w['unit_of_work'].rstrip('s')}" for w in specs
           if w.get("median_wall_s_per_unit") is not None and w["id"] in ("tpmc_intake_response", "compressor_size_for",
                                                                       "compressor_run", "system_evaluate_gas_path",
                                                                       "uq_modular_run_uq", "uq6_robust_design")]
    if per:
        out.append("Per-call costs for budgeting the A9.7 synthesis searches (machine-specific runtimes, not physics): "
                   + "; ".join(per) + ".")
    return out


# ------------------------------------------------------------------------------------------------ markdown
def _f(x):
    return "-" if x is None else (f"{x:.4g}" if isinstance(x, float) else str(x))


PARITY_REPORT_REL = "docs/performance/abep_core/parity_report_v1.json"
F1_JSON_REL = "docs/design_synthesis/f1_intake/f1_intake_synthesis_v1.json"
F3_JSON_REL = "docs/design_synthesis/f3_compressor/f3_compressor_synthesis_v1.json"
F6_JSON_REL = "docs/design_synthesis/f6_icp_geometry/f6_icp_geometry_v1.json"
F78_JSON_REL = "docs/design_synthesis/f7_f8_optimizer/f7_f8_optimizer_v1.json"
RESOLUTION_HEAD = "Cross-lane resolution (consolidated verification round 2)"


def _lane_json(rel):
    try:
        return json.loads((REPO / rel).read_text())
    except (OSError, ValueError):
        return None


def rust_speedup_example(by_id):
    """F0-R1-01: the speed-up example is read from the current parity report at render time (never hard-coded), so it
    cannot dangle when the campaign is re-run; the historical first-campaign value is cited by commit."""
    rep = _lane_json(PARITY_REPORT_REL)
    fr = ((by_id.get("tpmc_trace_channel") or {}).get("profile") or {}).get("tottime_fractions") or {}
    io = fr.get("project_python", 0.0) + fr.get("interpreter_builtin", 0.0) + fr.get("stdlib_python", 0.0)
    if not rep or "speedup" not in rep:
        return f"The measured Rust wall speed-ups are not available ({PARITY_REPORT_REL} missing or without a speedup section)."
    sp = rep["speedup"].get("W1_tpmc_trace_channel", {}).get("speedup_wall")
    ss = (rep.get("speedup_served_path") or {}).get("W1_tpmc_trace_channel", {}).get("speedup_wall")
    utc = (rep.get("campaign_history") or [{}])[-1].get("utc")
    txt = (f"The measured Rust wall speed-ups are in {PARITY_REPORT_REL} (sections speedup and speedup_served_path; "
           f"time removed = 1 - 1/speed-up). Latest campaign {utc}: W1 = tpmc_trace_channel {sp:.2f}x kernel-only "
           f"(admission gate bypassed; {100 * (1 - 1 / sp):.1f} % removed)")
    if ss:
        txt += f", {ss:.2f}x through the served, admission-gated backend ({100 * (1 - 1 / ss):.1f} % removed)"
    else:
        txt += "; the served-path speed-up is not recorded"
    txt += (f", against an interpreter-only share of {io:.4f}. (The first campaign, 2026-10-01T04:52:48Z, recorded 5.44x "
            "kernel-only on W1; that report version is at commit e2aeb3f, the current report keeps only verdicts and "
            "source hashes of earlier campaigns.)")
    return txt


def cross_lane_resolution():
    """F0-ID-01..06 resolved against the merged lanes at render time (the pinned F0 JSON keeps the as-measured PENDING
    counterparties; the parity pre-registration pins its sha256). Counts are read from the lane deliverables."""
    rep, f1, f3, f6, f78 = (_lane_json(r) for r in (PARITY_REPORT_REL, F1_JSON_REL, F3_JSON_REL, F6_JSON_REL, F78_JSON_REL))
    out = {}
    if rep:
        rid = {d["id"]: d for d in rep.get("interface_demands", [])}
        verd = ", ".join(f"{k} {v}" for k, v in rep.get("verdicts", {}).items())
        out["F0-ID-01"] = ("abep_core/ + abep_sim/design/tpmc_backend.py (fo_a9_7_rust_kernels, merged)",
                           f"PARTIAL: TPMC kernels ported behind the explicit Python wrapper ({verd}); re-running this "
                           f"harness on the Rust-enabled tree is RUST-ID-02 {rid.get('RUST-ID-02', {}).get('status')}")
        out["F0-ID-02"] = ("docs/performance/abep_core/parity_prereg_v1.json; " + PARITY_REPORT_REL,
                           f"SUPPLIED (RUST-ID-01 {rid.get('RUST-ID-01', {}).get('status')}): pre-registered tolerance "
                           "and per-kernel parity verdicts")
    if f1:
        n_part = next((i.get("value") for i in f1.get("items", []) if i.get("id") == "F1-P-12"), None)
        out["F0-ID-03"] = ("abep_sim/design/intake_synthesis.py; " + F1_JSON_REL,
                           f"PARTIAL: {f1.get('direct_runs')} direct intake_response runs per F1 build (direct_runs) at "
                           f"{n_part} particles each (F1-P-12), {f1.get('design_space', {}).get('n_candidates')} geometry "
                           "candidates; the frozen-surface point count per candidate is not recorded by F1 (OPEN); F1 "
                           "does not opt in to the Rust backend (RUST-ID-03)")
    if f3:
        cases = f3.get("cases", [])
        n_des = sum(c.get("n_designs", 0) for c in cases)
        n_sf = sum(len(c.get("size_for_comparison", [])) for c in cases)
        out["F0-ID-04"] = ("abep_sim/design/compressor_synthesis.py; " + F3_JSON_REL,
                           f"SUPPLIED: {n_des} design evaluations over {len(cases)} cases (one "
                           "DragCompressor.run(self_consistent=True) plus one _run_once re-check each, evaluate_design), "
                           f"plus {n_sf} size_for comparisons")
    if f78:
        rows = f78.get("upstream_pareto_summary", {}).get("rows", [])
        cols = f78.get("upstream_pareto_summary", {}).get("columns", [])
        n_ev = sum(r[cols.index("n_evaluated")] for r in rows) if "n_evaluated" in cols else None
        n_mc = next((i.get("value") for i in f78.get("items", []) if i.get("id") == "F78-P-08"), None)
        out["F0-ID-05"] = ("abep_sim/design/architecture_optimizer.py + robust_optimizer.py (driver "
                           "docs/design_synthesis/f7_f8_optimizer/build_f7_f8_optimizer.py)",
                           f"PARTIAL: entry points and counts supplied ({len(rows)} upstream contexts, {n_ev} upstream "
                           f"design evaluations, {f78.get('robust', {}).get('survivors')} robust survivors, {n_mc} TPMC-"
                           "statistics MC draws per (candidate, scenario), tpmc_invoked_by_f7_f8 = "
                           f"{f78.get('tpmc_backend_policy', {}).get('tpmc_invoked_by_f7_f8')}); re-profiling the new "
                           "driver is OPEN")
    if f6:
        s05 = next((d for d in f6.get("interface_demands", {}).get("f6_supplies", []) if d.get("id") == "F6-IF-S05"), None)
        if s05:
            out["F0-ID-06"] = ("abep_sim/design/icp_geometry_synthesis.py; " + F6_JSON_REL + " (F6-IF-S05)",
                               f"PARTIAL: F6 supplies {s05.get('what')} [{s05.get('status')}]; not profiled by F0 (OPEN)")
    return out


def basis_correction_lines(doc):
    """F0-01 / F0-02 / F0-03 corrections, derived only from the committed measured records (no new timing)."""
    by_id = {w["id"]: w for w in doc["workloads"]}
    L = ["", "## Basis correction (consolidated verification round 1)", "",
         "F0-01: the 'addressable' column and the findings' 'addressable <= X s' are interpreter-only estimates "
         "(project + builtin + stdlib tottime share), not upper bounds: the share excludes library_python_wrapper "
         "(numpy cross / moveaxis / norm wrappers, about 21-25 % of tottime in the TPMC workloads), which a native "
         "kernel also removes. The measured Rust speed-ups (parity report) exceed the interpreter-only share. Even the "
         "wrapper-inclusive share below is an estimate, not a bound (operator arithmetic booked as project_python and "
         "native calls a port can fuse also move). Rankings and PORT_CANDIDATE judgements do not change (the order "
         "and thresholds hold under either share). The committed JSON is unchanged because the parity pre-registration "
         "pins its sha256.", "",
         "| rank | workload | interpreter-only share (stored fractions summed once) | incl. library wrappers | "
         "reference workload s | estimate incl. wrappers s |", "|---|---|---|---|---|---|"]
    for r in doc["ranking"]:
        w = by_id[r["id"]]
        fr = (w.get("profile") or {}).get("tottime_fractions") or {}
        io = fr.get("project_python", 0.0) + fr.get("interpreter_builtin", 0.0) + fr.get("stdlib_python", 0.0)
        iw = io + fr.get("library_python_wrapper", 0.0)
        L.append(f"| {r['rank']} | {r['id']} | {_f(round(io, 4))} | {_f(round(iw, 4))} | "
                 f"{_f(r['reference_workload_s'])} | {_f(round(r['reference_workload_s'] * iw, 2))} |")
    L += [""] + [rust_speedup_example(by_id)]
    L += ["", "F0-02: the 'usage' of the TPMC PORT_CANDIDATE is the frozen_intake_surface_build reference workload, which "
          "CLAUDE.md rule 1 and RUST-ID-06 forbid running with the Rust backend, and no current consumer opts in to the "
          "Rust backend (F1 calls intake_tpmc.intake_response directly, RUST-ID-03 OPEN; F7 / F8 run no TPMC). The "
          "admitted kernels therefore have no consumer today; the F1 synthesis search (the real use) is not quantified "
          "here. A re-based judgement needs the F1 / F7 search point counts x the measured per-point cost.", "",
          "F0-03: the per-workload 'interpreter share' in the workload table is the sum of individually rounded "
          "fractions and can exceed 1 by rounding (e.g. 1.0001); the table above sums the stored fractions once. "
          "Workloads with CPU above wall reflect library / BLAS threads or background contention, not speed-up (see "
          "Method notes): " + "; ".join(
              f"{w['id']} CPU/wall {w['cpu_over_wall']} (repeats CPU s {w['cpu_s']} vs wall s {w['wall_s']})"
              for w in doc["workloads"] if (w.get("cpu_over_wall") or 0) > 1.05) + "."]
    return L


def render_md(doc):
    e = doc["environment"]
    L = [f"# Performance baseline {doc['base_commit_label']} (A9.7 F0: profile before porting)", "",
         f"Generated by `{SCRIPT_REL}` from `{os.path.basename(JSON_REL)}` (mode `{doc['mode']}`); do not edit by hand. "
         f"Lane `{doc['lane']}`, directive {doc['directive']}.", "",
         f"Base commit label **{doc['base_commit_label']}**; measured HEAD `{doc['measured_head']}`. {doc['base_commit_note']}",
         "", "**What this is not:** " + "; ".join(doc["what_this_is_not"]) + ".", "",
         "## Commands", ""]
    L += [f"- {k}: `{v}`" for k, v in doc["commands"].items()]
    L += ["", "## Environment", "",
          f"- CPU: {e['cpu_model']} ({e['logical_cpus']} logical CPUs, {e['cpus_available_to_process']} available)",
          f"- OS: {e['os']} ({e['machine']}); Python {e['python']} ({e['python_implementation']})",
          f"- numpy {e['numpy']}, scipy {e['scipy']}, pandas {e['pandas']}; BLAS: "
          + "; ".join(f"{k}: {v.get('name')} {v.get('version')}" for k, v in e["blas"].items() if isinstance(v, dict)),
          f"- thread env: {e['thread_env']}; load average at start {e['loadavg_at_start']}",
          f"- {e['concurrency_note']}", f"- total harness wall time: {doc['total_harness_wall_s']} s", "",
          "## Ranking (expected gain x usage)", "",
          "Gain x usage = interpreter-level share of cProfile tottime x seconds of the stated reference workload. The "
          "interpreter-level share excludes the library Python wrappers, so the 'addressable' figure is an "
          "interpreter-only estimate, NOT an upper bound of what a native kernel can remove (see 'Basis correction' "
          "below; the JSON key keeps its historical name '..._upper_bound'). Thresholds: PORT_CANDIDATE >= "
          f"{PORT_THRESHOLD_S:g} s, MARGINAL >= {MARGINAL_THRESHOLD_S:g} s (harness choices, owner question F0-OQ-01).", "",
          "| rank | workload | category | reference workload s | addressable s (interpreter-only estimate, not an "
          "upper bound) | judgement | deferred |",
          "|---|---|---|---|---|---|---|"]
    for r in doc["ranking"]:
        L.append(f"| {r['rank']} | {r['id']} | {r['category']} | {_f(r['reference_workload_s'])} | "
                 f"{_f(r['addressable_interpreter_s_upper_bound'])} | {r['judgement']} | {'yes' if r['deferred'] else 'no'} |")
    L += basis_correction_lines(doc)
    L += ["", "## A9.7 Rust admission order vs measured rank", "",
          "| A9.7 position | item | F0 rank | F0 judgement | deferred | note |", "|---|---|---|---|---|---|"]
    for r in doc["rust_order_comparison"]:
        L.append(f"| {r['a9_7_position']} | {r['a9_7_item']} | {_f(r['f0_rank'])} | {_f(r['f0_judgement'])} | "
                 f"{_f(r['f0_deferred'])} | {_f(r.get('via'))} |")
    L += ["", "## Findings", ""] + [f"- {x}" for x in doc["findings"]]
    rd = doc["robust_design_search_status"]
    L += ["", f"Robust design search: {rd['routine']}; A9.7 F8 robust optimizer: {rd['a9_7_f8_robust_optimizer']} "
          f"(as measured; now merged: abep_sim/design/robust_optimizer.py, see '{RESOLUTION_HEAD}').", "",
          "## Workloads", "",
          "| workload | units | repeats | median wall s | median CPU s | CPU/wall | s per unit | interpreter share | numpy share | deterministic |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for w in doc["workloads"]:
        pr = w.get("profile") or {}
        L.append(f"| {w['id']} | {_f(w['units_of_work'])} {w['unit_of_work']} | {w['repeats']} | {_f(w['median_wall_s'])} | "
                 f"{_f(w['median_cpu_s'])} | {_f(w['cpu_over_wall'])} | {_f(w['median_wall_s_per_unit'])} | "
                 f"{_f(pr.get('interpreter_level_fraction'))} | {_f(pr.get('numpy_level_fraction'))} | "
                 f"{w['deterministic_across_repeats']} |")
    for w in doc["workloads"]:
        pr = w.get("profile") or {}
        L += ["", f"### {w['id']}", "", f"- entry point: `{w['entry_point']}`", f"- workload: {w['description']}",
              f"- params: `{json.dumps(w['params'], sort_keys=True)}`",
              f"- wall s per repeat {w['wall_s']}; CPU s {w['cpu_s']}; load avg before/after {w['loadavg_1min_before_after']}"]
        if w.get("physics_note"):
            L.append(f"- physics note: {w['physics_note']}")
        if w.get("reference"):
            ref = w["reference"]
            L.append(f"- reference workload `{ref['id']}` ({_f(ref['units_of_work'])} units): {ref['basis']}. {ref['method']}."
                     + (f" (PENDING as measured; the named lane is merged, see '{RESOLUTION_HEAD}'.)"
                        if "PENDING" in ref["basis"] else ""))
        j = w["port_judgement"]
        L.append(f"- port judgement: **{j['judgement']}**" + (f" ({j.get('covered_by')})" if j.get("covered_by") else "")
                 + (f"; {j['qualifier']}" if j.get("qualifier") else "") + (f"; {j['basis']}" if j.get("basis") else ""))
        if w.get("scaling_probe"):
            sp = w["scaling_probe"]
            L.append(f"- scaling probe: {sp['points']}; work ratio {sp['work_ratio']}, time ratio {sp['time_ratio']} "
                     f"(time/work {sp['time_ratio_over_work_ratio']}; {sp['reading']})")
        if pr:
            L.append(f"- cProfile: {pr['total_function_calls']} calls, overhead ratio {pr.get('cprofile_overhead_ratio')}; "
                     f"tottime fractions {json.dumps(pr['tottime_fractions'], sort_keys=True)}")
            L += ["", "| top by cumulative | ncalls | tottime s | cumtime s | class |", "|---|---|---|---|---|"]
            for r in pr["top_by_cumulative"][:10]:
                L.append(f"| `{r['function']}` | {r['ncalls']} | {r['tottime_s']} | {r['cumtime_s']} | {r['class']} |")
    L += ["", "## Method notes", "",
          "- Timing: `time.perf_counter` (wall) and `time.process_time` (CPU of all process threads; CPU/wall > 1 means "
          "BLAS / library threads). Median over the stated repeats; one extra run under cProfile.",
          "- Classes of cProfile tottime: project_python (repository .py), interpreter_builtin (non-array builtins such as "
          "math.*, dict methods), stdlib_python, library_python_wrapper (numpy/pandas/scipy Python code), "
          "native_array_call (numpy/pandas/scipy C entry points). Interpreter share = project + builtin + stdlib.",
          "- Caveat: numpy arithmetic written as operators (a * b) runs inside the calling Python frame and is booked as "
          "project_python tottime, so the interpreter share overstates the Python-loop fraction of vectorized kernels; "
          "the scaling probe (time ratio vs work ratio) is the measured cross-check for those.",
          "- cProfile adds per-call overhead, largest for scalar Python loops (see overhead ratio).",
          "- CPU/wall well above 1 in a pure-Python workload is not parallel speed-up: OpenBLAS worker threads left "
          "spinning after an earlier numpy call are charged to the process; read CPU/wall only as a threading flag.",
          "- Extrapolations are labelled EXTRAPOLATED; they assume cost proportional to the unit of work.", "",
          "## Parameters", "", "| id | value | units | basis | evidence class |", "|---|---|---|---|---|"]
    for p in doc["parameters"]:
        L.append(f"| {p['id']} | {p['value']} | {p['units']} | {p['basis']} | {p['evidence_class']} |")
    res = cross_lane_resolution()
    L += ["", "## Interface demands", "",
          "Counterparty and status as recorded in the pinned JSON at measurement time; the last column resolves them "
          f"against the merged lanes (section '{RESOLUTION_HEAD}').", "",
          "| id | direction | counterparty (as measured) | demand | status (as measured) | resolution (round 2) |",
          "|---|---|---|---|---|---|"]
    for d in doc["interface_demands"]:
        r = res.get(d["id"])
        rtxt = f"{r[0]}: {r[1]}" if r else "unchanged"
        L.append(f"| {d['id']} | {d['direction']} | {d['counterparty']} | {d['demand']} | {d['status']} | {rtxt} |")
    L += ["", f"## {RESOLUTION_HEAD}", "",
          "The JSON is pinned by the parity pre-registration, so its PENDING counterparties and the PENDING notes in the "
          "robust-design line and the uq6 / robust-design reference-workload texts stay as measured. They are superseded "
          "here: every named lane is merged. Counts are read at render time from the lane deliverables (machine-specific "
          "call counts, never physics inputs).", ""]
    for i in sorted(res):
        L.append(f"- {i}: {res[i][0]} -> {res[i][1]}")
    L += ["", "## Open owner questions (new)", ""]
    L += [f"- **{q['id']}**: {q['question']} Default if unanswered: {q['default_if_unanswered']}." for q in
          doc["open_owner_questions"]]
    L += ["", "## M16 impact", ""] + [f"- {m['state_change']}" for m in doc["m16_impact"]]
    L += ["", "## Profiled sources", "", "| path | sha256 | identical to 98fbbb9 |", "|---|---|---|"]
    for s in doc["profiled_sources"]:
        L.append(f"| `{s['path']}` | `{s['sha256'][:16]}...` | {s['identical_to_98fbbb9']} |")
    return "\n".join(L) + "\n"


# ------------------------------------------------------------------------------------------------ validation / check
def validate(doc, require_all=True):
    errs = []
    for k in REQUIRED_TOP:
        if k not in doc:
            errs.append(f"missing top-level key {k}")
    if errs:
        return errs
    if doc["schema"] != SCHEMA:
        errs.append("schema id mismatch")
    ids = [w.get("id") for w in doc["workloads"]]
    cats = {w.get("category") for w in doc["workloads"]}
    if require_all and not set(F0_CATEGORIES) <= cats:
        errs.append(f"categories missing: {sorted(set(F0_CATEGORIES) - cats)}")
    for w in doc["workloads"]:
        for k in REQUIRED_WORKLOAD:
            if k not in w:
                errs.append(f"{w.get('id')}: missing {k}")
        if w.get("profile", None) is not None:
            for k in REQUIRED_PROFILE:
                if k not in w["profile"]:
                    errs.append(f"{w.get('id')}: profile missing {k}")
        if doc["mode"] == "full" and w.get("repeats_override") is None and w.get("repeats", 0) < 3:
            errs.append(f"{w.get('id')}: full mode needs >= 3 repeats")
    for r in doc["ranking"]:
        if r["id"] not in ids:
            errs.append(f"ranking id {r['id']} not a workload")
        if r["judgement"] not in ("PORT_CANDIDATE", "MARGINAL", "NOT_A_BOTTLENECK"):
            errs.append(f"bad judgement {r['judgement']}")
    txt = json.dumps(doc)
    if '"PASS"' in txt:
        errs.append('forbidden status token "PASS"')
    return errs


def check():
    jp, mp = REPO / JSON_REL, REPO / MD_REL
    doc = json.loads(jp.read_text())
    errs = validate(doc)
    if doc.get("mode") != "full":
        errs.append("committed baseline must be full mode")
    if derive(copy.deepcopy(doc)) != doc:
        errs.append("derived sections (judgements, ranking, Rust-order comparison, findings) do not follow from the "
                    "measured records (run --rederive)")
    if mp.read_text() != render_md(doc):
        errs.append("MD does not reproduce from JSON (run --render-md)")
    if doc.get("workload_spec_sha256") != spec_hash(workload_specs("full")):
        errs.append("workload specs changed since the baseline was measured (re-run the full baseline)")
    if doc.get("commands") != COMMANDS:
        errs.append("commands changed")
    for s in doc.get("profiled_sources", []):
        if s.get("identical_to_98fbbb9") is False:
            errs.append(f"{s['path']} differed from 98fbbb9 at measurement time")
    errs += [d["error"] for d in source_drift(doc) if d.get("error")]
    return errs


def source_drift(doc=None):
    """Profiled sources whose bytes changed since the baseline was measured (historical source drift).

    The committed timings are never re-measured or altered here. A drift is acceptable for --check only when it is
    recorded in DRIFT_REL with the baseline's old sha256 (an authorised model change after the measurement; the owner
    rerun, A9.18 PERF_RERUN, is required before any Rust performance admission). An unrecorded drift, or a record whose
    old sha256 does not match the baseline, carries an ``error``."""
    if doc is None:
        doc = json.loads((REPO / JSON_REL).read_text())
    rp = REPO / DRIFT_REL
    rec = {}
    if rp.exists():
        rec = {d["path"]: d for d in json.loads(rp.read_text()).get("drifted_files", [])}
    out = []
    for s in doc.get("profiled_sources", []):
        cur = hashlib.sha256((REPO / s["path"]).read_bytes()).hexdigest()
        if cur == s["sha256"]:
            continue
        d = {"status": "HISTORICAL_SOURCE_DRIFT", "path": s["path"], "old_sha256": s["sha256"], "new_sha256": cur}
        r = rec.get(s["path"])
        if r is None:
            d["error"] = (f"profiled source changed since the baseline and the drift is not recorded in {DRIFT_REL}: "
                          f"{s['path']} (old {s['sha256']}, new {cur})")
        elif r.get("old_sha256_a9_7") != s["sha256"]:
            d["error"] = f"drift record {DRIFT_REL} has a wrong old sha256 for {s['path']}"
        out.append(d)
    return out


def drift_report_lines(doc=None):
    """Explicit HISTORICAL_SOURCE_DRIFT report lines (printed by --check; never silent)."""
    drift = source_drift(doc)
    lines = [f"HISTORICAL_SOURCE_DRIFT {d['path']} old_sha256={d['old_sha256']} new_sha256={d['new_sha256']}"
             for d in drift]
    if drift:
        lines.append(f"HISTORICAL_SOURCE_DRIFT: {len(drift)} profiled source(s) changed after measurement (record "
                     f"{DRIFT_REL}); recorded timings are historical for the measured code state; owner rerun "
                     "(A9.18 PERF_RERUN) required before any Rust performance admission")
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--only", default=None, help="comma-separated workload ids (quick mode)")
    ap.add_argument("--out-json", default=None)
    ap.add_argument("--out-md", default=None)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--render-md", action="store_true")
    ap.add_argument("--rederive", action="store_true",
                    help="recompute the derived sections of the committed JSON from its measured records (no timing)")
    a = ap.parse_args(argv)
    if a.check:
        errs = check()
        for line in drift_report_lines():
            print(line)
        print("OK" if not errs else "\n".join(errs))
        return 1 if errs else 0
    if a.rederive:
        doc = derive(json.loads((REPO / JSON_REL).read_text()))
        errs = validate(doc)
        if errs:
            print("\n".join(errs)); return 1
        (REPO / JSON_REL).write_text(json.dumps(doc, indent=1, sort_keys=False) + "\n")
        (REPO / MD_REL).write_text(render_md(doc))
        print("re-derived", JSON_REL, MD_REL, "(measurements unchanged)")
        return 0
    if a.render_md:
        doc = json.loads((REPO / JSON_REL).read_text())
        (REPO / MD_REL).write_text(render_md(doc))
        print("written", MD_REL)
        return 0
    mode = "quick" if a.quick else "full"
    only = [x for x in a.only.split(",") if x] if a.only else None
    if mode == "full" and only:
        raise SystemExit("--only is a quick-mode option (the committed baseline covers every workload)")
    if mode == "quick" and not a.out_json:
        raise SystemExit("quick mode needs --out-json (it never overwrites the committed baseline)")
    out_json = Path(a.out_json) if a.out_json else REPO / JSON_REL
    out_md = Path(a.out_md) if a.out_md else (REPO / MD_REL if mode == "full" else out_json.with_suffix(".md"))
    doc = build(mode, only)
    errs = validate(doc, require_all=not only)
    if errs:
        rej = out_json.with_suffix(".rejected.json")
        rej.write_text(json.dumps(doc, indent=1) + "\n")
        print("\n".join(errs) + f"\n(rejected document kept at {rej})"); return 1
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(doc, indent=1, sort_keys=False) + "\n")
    out_md.write_text(render_md(doc))
    print("written", out_json, out_md, f"total {doc['total_harness_wall_s']} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
