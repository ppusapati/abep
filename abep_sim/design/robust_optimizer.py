"""A9.7 F8 robust optimization (owner directive OD_2026_10_01_A9_7, lane fo_a9_7_f7_f8_coupled_optimizer).

For the upstream candidates that survive F7 (members of the F7 upstream Pareto sets, nominal context: filter 'none',
wall WALL-G0), F8 asks how their feasibility and objectives move under every uncertainty axis named by A9.7 F8:

  axis                         treatment here                          why
  atmosphere                   SCENARIO_SET (every F1 state)           design-case reference + every required state of
                                                                       the frozen design-state set v2 (A9.14 S9.8 OD3);
                                                                       no probability is attached to any state
  intake surface state         SCENARIO_SET (alpha 0..1 x kernel)      accommodation is TBD (F1-P-07): a set, no weights
  gas-surface interaction      SCENARIO_SET (Maxwell / CLL)            kernel TBD (F1-P-08), same axis as above
  TPMC statistics              SEEDED_MONTE_CARLO                      the only QUANTIFIED uncertainty: binomial SEs of
                                                                       the committed F1 records (mdot_fwd, p_passive)
                                                                       and the C_D replicate SE (drag)
  pointing (theta)             DETERMINISTIC_NODE (5 deg, design state) pointing budget TBD (F1-P-09); the 5 deg frozen
                                                                       surface node exists only at the design state
  wall O recombination         SCENARIO_SET (WALL-G0 / WALL-TI64-DB)   gamma TBD (F4-P-06)
  compressor performance       LOCAL_ELASTICITY                        F3 gives NO range for any coefficient (uncited
                                                                       code defaults): elasticities, not a distribution
  feed state                   NOT_EVALUATED                           H-1 inlet requirement TBD (F5 IFD-F4-01..05);
                                                                       P_set stays a requirement-level context axis
  Hall response                NOT_EVALUATED                           no admitted Hall response map
  RF efficiency                NOT_EVALUATED                           TBD (P2 / RFQ v3: no impedance map, no source)
  thermal parameters           NOT_EVALUATED                           P3 inputs TBD; chain temperature assumed

Probabilities (P_feasible, percentiles) are computed ONLY over the quantified TPMC statistics, conditional on each
scenario-set member; across a scenario set only counts and worst cases are reported (no invented weights). The robust
Pareto filter keeps candidates that are nominally feasible in EVERY surface scenario and compares worst-case objectives
plus the minimum TPMC P_feasible; it never changes any evidence-gate status (``gate_snapshot`` before == after, test).

Calls abep_sim.design.plenum_feed / architecture_optimizer; no existing module is modified; not wired into
archengine; deterministic (seeded generators derived from stable ids). Nothing here is a design, a selection, a
winner or a PASS.

A9.13 owner decisions applied (A9.16 step 3 design layer; rules in abep_sim/design/upstream_a9_13.py):
  * S6.16 / OQ-F78-02: ``scenario_robustness`` requires EVERY admitted Maxwell / CLL / accommodation scenario (the
    admitted set is the scenario set of the evaluated contexts unless given); a subset is refused unless a
    pre-registered DI-1.3 narrowing record is supplied (the full-range cases then stay as sensitivity records).
  * S6.20 / F9-OQ-01: ``carried_robust_set`` wraps the robust members in a versioned RobustParetoSet; no
    representative is selected.
  * S6.5: the nominal filter context 'F4-FIL-NONE' (FC-00) is a REFERENCE BOUND context (``NOMINAL_FILTER_ROLE``);
    its survivors bound the filter cost and are never an admissible flight architecture.
"""
from __future__ import annotations

import dataclasses
import math
import warnings
from typing import Mapping, Sequence

import numpy as np

from ..compressor import DragCompressor
from . import architecture_optimizer as ao
from . import compressor_synthesis as cs
from . import intake_synthesis as isy
from . import plenum_feed as pf
from . import upstream_a9_13 as u13

SCHEMA = "f8_robust_optimizer_v1"
SPECIES = ao.SPECIES
N_MC_DEFAULT = 100
SEED_BASE = 20261001
ELASTICITY_STEP = 1e-3            # relative central-difference step (numerical setting, not an uncertainty)
NOMINAL_FILTER = "F4-FIL-NONE"
NOMINAL_FILTER_ROLE = "REFERENCE_BOUND_FC00_NOT_ADMISSIBLE"     # A9.13 S6.5
NOMINAL_WALL = "WALL-G0"

def _uq_axes() -> tuple:
    return ({"axis": "atmosphere", "treatment": "SCENARIO_SET", "quantified": False,
             "members": list(ao.states()), "design_state_set": isy.DESIGN_STATE_SET_ID,
             "design_state_set_sha256": isy.DESIGN_STATE_SET_SHA256, "orbit_basis": isy.ORBIT_BASIS_LABEL,
             "basis": "design-case reference point h200_f150 (orbit-averaged, surface build state) + every required "
             "state of the frozen design-state set v2 (nominal states and physical extrema of density, composition, "
             "temperature, local time and solar activity; A9.14 S9.8 OD3; F1 coverage_rule); no probability over "
             "the states is sourced; broad envelope, inclination / LTAN TBD (A9.21)",
             "source": ao.F1_REL + " coverage_rule"},) + _UQ_AXES_REST


def __getattr__(name):
    # UQ_AXES / STATES are resolved lazily (the design-state set is repository-only data)
    if name == "UQ_AXES":
        return _uq_axes()
    if name == "STATES":
        return ao.states()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


_UQ_AXES_REST = (
    {"axis": "intake_surface_state", "treatment": "SCENARIO_SET", "quantified": False,
     "basis": "alpha in {0, 0.2, 0.5, 0.8, 1} (TBD, F1-P-07); no measured accommodation", "source": ao.F1_REL},
    {"axis": "gas_surface_interaction", "treatment": "SCENARIO_SET", "quantified": False,
     "basis": "Maxwell / CLL kernels (TBD, F1-P-08); carried jointly with alpha (10 scenarios)", "source": ao.F1_REL},
    {"axis": "tpmc_statistics", "treatment": "SEEDED_MONTE_CARLO", "quantified": True,
     "basis": "1-sigma binomial SEs of the committed F1 IF-A1 records (mdot_fwd_s, p_passive_s, independent normal "
     "draws per species and state) and the replicate-calibrated C_D SE (drag); model-form uncertainty is NOT in "
     "these SEs (F1 conventions.uncertainty)", "source": ao.F1_REL + " if_a1_interface, species_table"},
    {"axis": "pointing_theta", "treatment": "DETERMINISTIC_NODE", "quantified": False,
     "basis": "theta = 5 deg frozen-surface node at the design-case reference point only (per-species eta_c and CR "
     "ratios vs theta 0); the AOCS pointing budget is TBD (F1-P-09); the required design states have no theta node",
     "source": ao.F1_REL + " species_table (theta_deg 5)"},
    {"axis": "wall_recombination", "treatment": "SCENARIO_SET", "quantified": False,
     "basis": "WALL-G0 (gamma 0 bound) vs WALL-TI64-DB (uncited DB prior), F4-P-06 TBD", "source": ao.F4_REL},
    {"axis": "compressor_performance", "treatment": "LOCAL_ELASTICITY", "quantified": False,
     "basis": "every DragCompressor coefficient is an uncited code default with NO sourced range (F3 coefficients, "
     "compressor_downselect CD-01): d ln(objective) / d ln(coefficient) by central difference; no distribution "
     "is invented", "source": ao.F3_REL + " coefficients"},
    {"axis": "feed_state", "treatment": "NOT_EVALUATED", "quantified": False,
     "basis": "H-1 required inlet state TBD (F4-P-10, F5 IFD-F4-01..05); P_set is a requirement-level context axis; "
     "feed-path conductance steps are in F4's transient study (E3/E4)", "source": ao.F4_REL},
    {"axis": "hall_response", "treatment": "NOT_EVALUATED", "quantified": False,
     "basis": "credible Hall set EMPTY; P5-N2 v1 INCONCLUSIVE; no admitted response map", "source": ao.ENS_REL},
    {"axis": "rf_efficiency", "treatment": "NOT_EVALUATED", "quantified": False,
     "basis": "flight RF source efficiency TBD (MPV2-P08); RF ratings TBD_AFTER_IMPEDANCE_MAP", "source": ao.MP_REL},
    {"axis": "thermal_parameters", "treatment": "NOT_EVALUATED", "quantified": False,
     "basis": "P3 geometry / emittance / conductance inputs TBD; chain gas temperature assumed 350 K (F4-P-01)",
     "source": ao.P3_REL},
    {"axis": "orbit_scale_density_modulation", "treatment": "NOT_EVALUATED", "quantified": False,
     "basis": "F4-P-11 TBD (a revolution through the orbit-resolved states needs the TBD inclination / LTAN, A9.21); "
     "F4 parametric amplitudes 0.1 / 0.2 are reported there", "source": ao.F4_REL},
)


# ================================================================================================= gate snapshot
def design_gate_snapshot(repo=ao.REPO, rvm_snapshot: dict | None = None) -> dict:
    """Evidence-gate statuses the robust filter must never change, read from their owning design deliverables (Hall
    credible set, mass/power statuses, H-1 freeze state). A9.22: the RVM-derived part is an assessment input; the
    caller passes it in (``rvm_snapshot``: abep_sim.assessment.design_gates.rvm_gate_snapshot), this module never
    reads the RVM."""
    mp = ao.read_json(ao.MP_REL, repo)
    f5 = ao.read_json(ao.F5_REL, repo)
    hall = ao.hall_response_status(repo)
    snap = {"hall_credible_set": hall["credible_set"], "hall_admitted_members": list(hall["admitted_members"]),
            "a9_2_statuses": dict(mp["statuses"]["a9_2_statuses"]),
            "a9_19_20_supersessions": dict(mp["statuses"].get("a9_19_20_supersessions", {})),
            # A9.24 item 13: the current statuses (C1 GROUND_REFERENCE_ONLY); a9_2_statuses is the A9.2 quote
            "current_statuses": dict(mp["statuses"].get("current_statuses", {})),
            "h1_article_freeze_state": f5["article_freeze_state"]}
    snap.update(rvm_snapshot or {})
    return snap


# A9.22: the full F8 evidence-gate snapshot (design part + RVM part) is abep_sim.assessment.design_gates.gate_snapshot
# (= design_gate_snapshot(repo, rvm_gate_snapshot(repo))); the deprecated no-argument gate_snapshot here was removed.


# ================================================================================================= helpers
def stable_seed(*parts) -> int:
    return isy.stable_seed(*parts, base=SEED_BASE)


def record_se_index(f1: dict) -> dict:
    """(Ld, phi, scenario, state) -> per-species (mdot_fwd_se per m^2, p_passive_se) from the committed IF-A1 records."""
    out = {}
    for r in f1["if_a1_interface"]["records_per_unit_area"]:
        Ld, phi = (float(x) for x in r["candidate"].replace("unit_area_Ld", "").split("_phi"))
        out[(Ld, phi, r["scenario"], r["state"])] = {
            s: (r["species"][s]["mdot_fwd_se_kgps"], r["species"][s]["p_passive_se_Pa"]) for s in SPECIES}
    return out


def theta_ratio_index(f1: dict) -> dict:
    """(scenario, Ld, phi, species) -> (eta_c(5 deg) / eta_c(0), CR(5 deg) / CR(0)) at the design state (frozen
    surface nodes)."""
    cols = f1["species_table"]["columns"]
    rows = [dict(zip(cols, r)) for r in f1["species_table"]["rows"] if r[0] == ao.DESIGN_STATE]
    base = {}
    for r in rows:
        k = (f"{r['scattering']}_a{r['alpha']:g}", float(r["L_over_d"]), float(r["phi"]), r["species"])
        base.setdefault(k, {})[float(r["theta_deg"])] = r
    out = {}
    for k, d in base.items():
        if 0.0 in d and 5.0 in d:
            out[k] = (d[5.0]["eta_c"] / d[0.0]["eta_c"], d[5.0]["CR_passive"] / d[0.0]["CR_passive"])
    return out


def perturbed(rec: pf.IntakeState, area: float, se: Mapping, z_m: Mapping, z_p: Mapping) -> pf.IntakeState:
    """IntakeState with mdot_fwd_s + z SE and p_passive_s + z SE (clipped at a tiny positive floor: never negative)."""
    md = {s: max(rec.mdot_fwd_kgps[s] + z_m[s] * se[s][0] * area, 1e-30) for s in SPECIES}
    pp = {s: max(rec.p_passive_Pa[s] + z_p[s] * se[s][1], 1e-30) for s in SPECIES}
    return dataclasses.replace(rec, mdot_fwd_kgps=md, p_passive_Pa=pp, source=rec.source + " [TPMC-SE draw]")


def plant_with_overrides(design: Mapping, overrides: Mapping | None = None) -> pf.CompressorPlant:
    """CompressorPlant exactly as plenum_feed.CompressorPlant.from_design builds it, with FIXED coefficients overridden
    (identical to from_design when overrides is empty: test)."""
    cs.validate_design(design)
    kw = cs.module_defaults()
    for f, v in (overrides or {}).items():
        if cs.FIELD_ROLES.get(f, (None,))[0] != cs.FIXED:
            raise ao.OptimizerError(f"only FIXED compressor coefficients can be perturbed, not {f}")
        kw[f] = cs.validate_coefficient(f, v)
    kw.update({"turbo_rows": int(design["N_turbo"]), "turbo_area_m2": float(design["A_turbo_m2"]),
               "turbo_radius_m": float(design.get("R_turbo_m", cs.r_turbo_from_area(float(design["A_turbo_m2"])))),
               "n_stages": int(design["N_drag"]), "rpm": float(design["rpm"]),
               "rotor_material": design["rotor_material"], "T_gas_K": float(pf.T_CHAIN_K)})
    return pf.CompressorPlant(design_id=str(design["id"]), design=dict(design), comp=DragCompressor(**kw))


def fixed_coefficients() -> list[str]:
    return [k for k, v in cs.FIELD_ROLES.items() if v[0] == cs.FIXED]


def _state_eval(states: list, filt: pf.FilterCase, plant: pf.CompressorPlant, pl: pf.Plenum, P: float,
                side: Mapping | None = None) -> dict:
    """Gated steady points of a list of IntakeStates (multiple of 5, state order) at one set pressure (``side``: the
    precomputed plenum_feed.intake_side of the same states and filter, reused across compressors)."""
    side = side if side is not None else pf.intake_side(states, filt)
    f1ok = np.array([r.f1_status == "FEASIBLE_AT_STATE" for r in states])
    sw = pf.steady_sweep(side, plant, pl, [P], f1ok)
    nst = len(ao.states())
    if len(states) % nst:
        raise ao.OptimizerError(f"{len(states)} intake states are not whole groups of the {nst} F1 states")
    n = len(states) // nst
    bits = sw["bits"][:, 0].reshape(n, nst)
    ok = (bits == 0)
    allok = ok.all(axis=1)
    with np.errstate(all="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        md = np.where(allok, np.nanmin(np.where(ok, sw["mdot_total_kgps"][:, 0].reshape(n, -1), np.nan), axis=1),
                      np.nan)
        pel = np.where(allok, np.nanmax(np.where(ok, sw["P_el_W"][:, 0].reshape(n, -1), np.nan), axis=1), np.nan)
        mc = np.where(allok, np.nanmax(np.where(ok, sw["m_compressor_kg"][:, 0].reshape(n, -1), np.nan), axis=1),
                      np.nan)
        dm = np.where(allok, np.nanmin((sw["p_deadhead_Pa"][:, 0].reshape(n, -1) - P) / P, axis=1), np.nan)
    return {"bits": bits, "all_ok": allok, "mdot_min": md, "P_el_max": pel, "m_comp_max": mc, "deadhead_margin": dm}


# ================================================================================================= survivors
def survivors(pareto_by_context: Mapping, filt: str = NOMINAL_FILTER, wall: str = NOMINAL_WALL) -> list[dict]:
    """Unique upstream design vectors on any F7 Pareto set of the nominal (filter, wall) context, over every surface
    scenario and set pressure. pareto_by_context: {(scenario, filter, wall): context_pareto(...)}."""
    seen = {}
    for (sc, f, w), par in pareto_by_context.items():
        if f != filt or w != wall:
            continue
        for P, block in par.items():
            for m in block["members"]:
                seen.setdefault(m["design_id"], {"design_id": m["design_id"], "candidate": m["candidate"],
                                                 "compressor": m["compressor"], "V_m3": m["V_m3"], "P_set_Pa": P,
                                                 "filter": filt, "pareto_in": [],
                                                 "filter_context_role": NOMINAL_FILTER_ROLE if filt == NOMINAL_FILTER
                                                 else "ARCHITECTURE_CONTEXT"})["pareto_in"].append(sc)
    out = sorted(seen.values(), key=lambda r: r["design_id"])
    for r in out:
        r["pareto_in"] = sorted(set(r["pareto_in"]))
    return out


def scenario_robustness(cands: Sequence[Mapping], contexts: Mapping, scenarios: Sequence[str],
                        wall: str = NOMINAL_WALL, admitted: Sequence[str] | None = None,
                        narrowing_record: Mapping | None = None) -> dict:
    """Per candidate: nominal feasibility and objectives in every surface scenario (from F7 context arrays), count of
    feasible scenarios and worst cases. contexts: {(scenario, filter, wall): upstream_context(...)}.

    A9.13 S6.16: ``scenarios`` must cover every admitted scenario (default: every scenario present in ``contexts``)
    unless a pre-registered DI-1.3 ``narrowing_record`` is supplied (upstream_a9_13.require_all_admitted_scenarios)."""
    adm = list(admitted) if admitted is not None else sorted({k[0] for k in contexts})
    u13.require_all_admitted_scenarios(list(scenarios), adm, narrowing_record)
    out = {}
    for c in cands:
        per = {}
        for sc in scenarios:
            ctx = contexts[(sc, c["filter"], wall)]
            g = (ctx["candidates"].index(c["candidate"]), ctx["compressors"].index(c["compressor"]),
                 ctx["volumes"].index(c["V_m3"]), ctx["targets"].index(c["P_set_Pa"]))
            feas = bool(ctx["feasible"][g])
            rec = {"feasible": feas, "reasons": pf.reasons_from_bits(int(ctx["bits"][g]))}
            if feas:
                for k in ao.OBJ_KEYS:
                    rec[k] = float(ctx["arrays"][k][g])
            per[sc] = rec
        feas_sc = [sc for sc in scenarios if per[sc]["feasible"]]
        worst = None
        if len(feas_sc) == len(scenarios):
            worst = {k: (min if ao.OBJ_SENSE[k] == "max" else max)(per[sc][k] for sc in scenarios)
                     for k in ao.OBJ_KEYS}
        out[c["design_id"]] = {"n_scenarios_feasible": len(feas_sc), "n_scenarios": len(scenarios),
                               "infeasible_in": [sc for sc in scenarios if sc not in feas_sc],
                               "worst_case_all_scenarios": worst, "per_scenario": per}
    return out


# ================================================================================================= TPMC Monte Carlo
def tpmc_monte_carlo(inp: ao.UpstreamInputs, cands: Sequence[Mapping], scenarios: Sequence[str], n: int = N_MC_DEFAULT,
                     wall: str = NOMINAL_WALL) -> dict:
    """Seeded MC over the quantified TPMC statistics, per (candidate, scenario). One batch per (scenario, filter,
    compressor): every intake candidate on the survivor list draws n samples of every F1 state (one generator
    per (candidate, scenario), seeded from stable ids, so results do not depend on batching). Returns, per design id
    and scenario: P_feasible (k / n), percentiles of the delivered minimum flow, compressor power and drag, and the
    dead-head margin. WALL-G0 steady states are volume-independent, so V does not enter the draws."""
    se_idx = record_se_index(inp.f1)
    STATES = ao.states()
    groups: dict = {}
    for c in cands:
        groups.setdefault((c["filter"], c["compressor"]), {}).setdefault(c["candidate"], set()).add(c["P_set_Pa"])
    draws: dict = {}
    sides: dict = {}

    def draw(cand, sc):
        if (cand, sc) not in draws:
            A, Ld, phi = inp.geometry[cand]
            rng = np.random.default_rng(stable_seed("tpmc", cand, sc))
            z = rng.standard_normal((n, len(STATES), 3, 3))   # [sample, state, (mdot, p, cd), species]
            states, drag = [], np.zeros((n, len(STATES)))
            for i in range(n):
                for j, st in enumerate(STATES):
                    rec = inp.records[(cand, sc, st)]
                    se = se_idx[(Ld, phi, sc, st)]
                    states.append(perturbed(rec, A, se, dict(zip(SPECIES, z[i, j, 0])),
                                            dict(zip(SPECIES, z[i, j, 1]))))
                    d0, dse = inp.drag_per_area[(sc, Ld, phi, st)]
                    drag[i, j] = A * (d0 + z[i, j, 2, 0] * dse)
            draws[(cand, sc)] = (states, drag.max(axis=1))
        return draws[(cand, sc)]

    res: dict = {}
    for sc in scenarios:
        for (filt, comp), cdict in sorted(groups.items()):
            plant = inp.plants[comp]
            pl = ao.plenum(1e-2, wall)
            fc = inp.filters[filt]
            for cand in sorted(cdict):
                states, dmax = draw(cand, sc)
                if (cand, sc, filt) not in sides:
                    sides[(cand, sc, filt)] = pf.intake_side(states, fc)
                for P in sorted(cdict[cand]):
                    ev = _state_eval(states, fc, plant, pl, P, sides[(cand, sc, filt)])
                    k = int(ev["all_ok"].sum())
                    ok = ev["all_ok"]

                    def pct(a, q):
                        a = a[ok]
                        return float(np.percentile(a, q)) if len(a) else None
                    res.setdefault((cand, filt, comp, P), {})[sc] = {
                        "n": n, "k_feasible": k, "P_feasible": k / n,
                        "mdot_delivered_min_p05_kgps": pct(ev["mdot_min"], 5),
                        "mdot_delivered_min_p50_kgps": pct(ev["mdot_min"], 50),
                        "P_compressor_el_max_p95_W": pct(ev["P_el_max"], 95),
                        "deadhead_margin_p05": pct(ev["deadhead_margin"], 5),
                        "drag_intake_max_p95_N": float(np.percentile(dmax, 95)),
                        "reasons_in_draws": sorted({r for b in ev["bits"].ravel() for r in pf.reasons_from_bits(int(b))})}
    return res


# ================================================================================================= pointing node
def pointing_sensitivity(inp: ao.UpstreamInputs, cands: Sequence[Mapping], scenarios: Sequence[str],
                         wall: str = NOMINAL_WALL) -> dict:
    """theta = 5 deg node at the design-case reference point only (per-species eta_c and CR ratios from the frozen
    surface): status and delivered flow there vs theta 0. The required design states have no theta node
    (NOT_EVALUATED)."""
    tr = theta_ratio_index(inp.f1)
    out = {}
    for c in cands:
        A, Ld, phi = inp.geometry[c["candidate"]]
        plant = inp.plants[c["compressor"]]
        pl = ao.plenum(c["V_m3"], wall)
        fc = inp.filters[c["filter"]]
        per = {}
        for sc in scenarios:
            rec0 = inp.records[(c["candidate"], sc, ao.DESIGN_STATE)]
            r = {s: tr[(sc, Ld, phi, s)] for s in SPECIES}
            rec5 = dataclasses.replace(rec0, mdot_fwd_kgps={s: rec0.mdot_fwd_kgps[s] * r[s][0] for s in SPECIES},
                                       p_passive_Pa={s: rec0.p_passive_Pa[s] * r[s][1] for s in SPECIES})
            vals = []
            for rec in (rec0, rec5):
                op = pf.steady_operating_point(pf.Chain(rec, fc, plant, pl), c["P_set_Pa"])
                vals.append((op["status"], op["offered"]["mdot_total_kgps"] if op.get("offered") else None))
            per[sc] = {"status_theta0": vals[0][0], "status_theta5": vals[1][0],
                       "mdot_theta0_kgps": vals[0][1], "mdot_theta5_kgps": vals[1][1],
                       "rel_change": (vals[1][1] / vals[0][1] - 1.0) if vals[0][1] and vals[1][1] else None}
        out[c["design_id"]] = per
    return out


# ================================================================================================= compressor elasticities
def compressor_elasticities(inp: ao.UpstreamInputs, cand: Mapping, scenarios: Sequence[str],
                            wall: str = NOMINAL_WALL, step: float = ELASTICITY_STEP) -> dict:
    """d ln(obj) / d ln(c) for every FIXED DragCompressor coefficient (central difference), objectives: delivered
    minimum flow, compressor power and mass (max over states); max |elasticity| over the scenarios. A coefficient whose
    perturbation changes the feasibility status is flagged (STATUS_FLIP). No coefficient range is implied."""
    design = inp.designs[cand["compressor"]]
    STATES = ao.states()
    pl = ao.plenum(cand["V_m3"], wall)
    fc = inp.filters[cand["filter"]]
    base_kw = cs.module_defaults()
    out = {}
    nominal_ok: dict = {}
    sides: dict = {}
    for coef in fixed_coefficients():
        c0 = float(base_kw[coef])
        worst = {"mdot_min": 0.0, "P_el_max": 0.0, "m_comp_max": 0.0}
        flip = False
        for sc in scenarios:
            states = [inp.records[(cand["candidate"], sc, st)] for st in STATES]
            if sc not in sides:          # the intake side does not depend on the compressor coefficients: reuse it
                sides[sc] = pf.intake_side(states, fc)
            if sc not in nominal_ok:
                nominal_ok[sc] = bool(_state_eval(states, fc, plant_with_overrides(design), pl,
                                                  cand["P_set_Pa"], sides[sc])["all_ok"][0])
            evs = [_state_eval(states, fc, plant_with_overrides(design, {coef: c0 * f}), pl, cand["P_set_Pa"],
                               sides[sc]) for f in (1.0 - step, 1.0 + step)]
            oks = [bool(e["all_ok"][0]) for e in evs]
            # OPT-06: a flip is any perturbed status that differs from the NOMINAL status (both-infeasible around a
            # feasible nominal point is a knife edge and is flagged too)
            flip = flip or any(o != nominal_ok[sc] for o in oks)
            if not all(oks):
                continue
            for k in worst:
                lo, hi = evs[0][k][0], evs[1][k][0]
                if lo > 0 and hi > 0:
                    e = (math.log(hi) - math.log(lo)) / (math.log(1 + step) - math.log(1 - step))
                    worst[k] = max(worst[k], abs(e))
        out[coef] = {"code_default": c0, "max_abs_elasticity": worst, "status_flip_within_step": flip}
    return out


# ================================================================================================= robust Pareto
ROBUST_OBJECTIVES = tuple(ao.OBJ_KEYS) + ("P_feasible_tpmc_min",)
ROBUST_SENSE = dict(ao.OBJ_SENSE, P_feasible_tpmc_min="max")


def robust_pareto(cands: Sequence[Mapping], scen: Mapping, mc: Mapping) -> dict:
    """Robust filter per set pressure: candidates nominally feasible in EVERY surface scenario (fail closed: one
    infeasible scenario removes it), compared on worst-case objectives over the scenario set plus the minimum TPMC
    P_feasible over the scenarios. Returns members per P_set (a set, never a winner)."""
    by_p: dict = {}
    for c in cands:
        s = scen[c["design_id"]]
        if s["worst_case_all_scenarios"] is None:
            continue
        m = mc.get((c["candidate"], c["filter"], c["compressor"], c["P_set_Pa"]))
        if m is None:
            continue
        row = dict(s["worst_case_all_scenarios"])
        row["P_feasible_tpmc_min"] = min(v["P_feasible"] for v in m.values())
        by_p.setdefault(c["P_set_Pa"], []).append((c["design_id"], row))
    out = {}
    for P, items in sorted(by_p.items()):
        F = np.array([[r[k] for k in ROBUST_OBJECTIVES] for _, r in items], dtype=float)
        mask = ao.pareto_mask(F, [ROBUST_SENSE[k] for k in ROBUST_OBJECTIVES])
        out[P] = {"n_all_scenario_feasible": len(items),
                  "members": sorted(([{"design_id": d, **r} for (d, r), k in zip(items, mask) if k]),
                                    key=lambda r: r["design_id"])}
    return out


def carried_robust_set(robust: Mapping, version: str, provenance: str, regenerated_after=()) -> "u13.RobustParetoSet":
    """A9.13 S6.20: the union of the robust members over the set pressures, carried as a versioned set (no
    representative; downstream single-point studies evaluate every member or label one an engineering reference)."""
    ids = sorted({m["design_id"] for blk in robust.values() for m in blk["members"]})
    return ao.robust_pareto_set(ids, version, provenance, regenerated_after)
