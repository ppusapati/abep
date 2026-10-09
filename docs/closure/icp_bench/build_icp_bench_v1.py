"""A9.39 scope item 3: RF/ICP neutralizer bench-design closure (lane L-ICP-BENCH).

Writes, from sha256-pinned repository records only:
  icp_bench_design_v1.json      bench design (hardware, RF chain, collector / bias, gas, facility, diagnostics, safety)
  icp_bench_test_plan_v1.json   preregistrable test matrix and pass / fail criteria (ICP-45 / HC-05 / GNG-ICP-01)
  icp_bench_test_plan_lock_v1.json  sha256 of the test plan
  ICP_BENCH_DESIGN_v1.md        human-readable page (the JSON governs)

The only computations are arithmetic on registered values (current targets, collector-bias ranges, RF planning envelope,
pumping need, margin detectability, power-budget ceilings). Nothing here is a model result, a measurement or a verdict.
No physics, admitted contract or frozen record is changed.

Usage: python3 docs/closure/icp_bench/build_icp_bench_v1.py [--check]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent

# In-tree inputs, verified on every run (a mismatch refuses the build).
PIN = {
    "A939_JSON": ("docs/decisions/OD_2026_10_09_A9_39_architecture_closed_owner_decisions.json",
                  "dd17ada07ab660187d8c762483a340299470d6e04e60f24f06938b9e450ea857"),
    "CONCLUSION_V2": ("docs/closure/conclusion/ARCHITECTURE_CLOSURE_CONCLUSION_v2.md",
                      "4ef4573e346eac88ed87610b569f1eedb9f7107a6ebc9ebe56a42ac2080babf9"),
    "DBF11": ("docs/baseline/DBF-1.1/dbf1_1_v1.json",
              "b8daa5bd5bb18b4fc92d6f65b0d93d0e70b33cd80d0f222cb9957ced3075c22b"),
    "DBF11_LOCK": ("docs/baseline/DBF-1.1/dbf1_1_lock_v1.json",
                   "257e141ca252c3015b5bbd2fc953a1de688bc1606be36ebdf9fff8889307cfb8"),
    "ICP_CLOSURE": ("docs/closure/icp/icp_closure_v1.json",
                    "3ddf55039b4f682983cfd728ded3bec6bb6e7e1cb73551ccee32521815b1016c"),
    "ICP_REG": ("docs/closure/icp/icp_closure_registration_v1.json",
                "41ce4d17a58e0ba6896fd4cfb815856f69c06271ae50b0d602575d5606802d51"),
    "ICP_A1": ("docs/closure/icp/icp_collector_window_a1_v1.json",
               "c414954b13c7e54475d8732de82f37051f07e4bd9e7cc273ccd56fac7098eee6"),
    "P1": ("docs/experiments/hall_icp/p1_icp_bench/p1_icp_bench_v1.json",
           "d0a696c597c839802a405d6607abe03a1dc5e5bb917cd11405a86aa3be9e4f08"),
    "P2": ("docs/experiments/hall_icp/p2_impedance_map/p2_impedance_prep_v1.json",
           "cdd4b04d79fbee4e22d76d2734bb170ce5e8a8eab54b47e93c0b6e15dd8a0a87"),
    "ICD": ("schemas/interfaces/icp_neutralizer_icd_v1.json",
            "8ec092f284505e7a538d17f568c0d9d763155f9a2ce4541223ddd114169a452c"),
    "RVM": ("docs/requirements/rvm_a9/rvm_a9_v1.json",
            "f91a00b40e24a66ceec8fd16dba3ad5ecb249ae186cc39bf717efe083223a5c4"),
    "THRESHOLDS": ("config/assessment/gate_thresholds_v1.json",
                   "504af5968d692286770ff89a3800b04ff83b6f96aff8e1fe21ee779e9cef3a3b"),
    "POWER": ("docs/closure/power/power_ledger_v1.json",
              "23e3366967f3d04d332564f95e6f4ddb3f4aa3b3d774cb6e09b5aa6a9138472a"),
    "MATERIALS": ("docs/closure/materials/materials_gates_v1.json",
                  "f3b6e04507429db87b3f94a3a355bb6e87cb78d97ca9bd1f902a766ea667fee1"),
    "THERMAL_PREREG": ("docs/closure/thermal/thermal_cases_prereg_v1.json",
                       "5666c528486f8cb7935863b3826c66e60271242637b31826468adde09394ecba"),
    "R5": ("docs/procurement/web_track_v1/threads/R5_facilities.json",
           "338132594ceb561992af03d93200e108924f54894f3ebbc3ca041472febc986a"),
    "CHEM_ADD01": ("docs/rust_migration/new_physics/NP-ICP-CHEM-AIR/addendum_01_build_rules_xe_v1.json",
                   "5dfd1c5928bcc7fe7a06b701a6c5ad53ef83cd1563577494d688bde9085c6f61"),
    "VALIDATION_RS": ("crates/abep-icp/src/v2/validation.rs",
                      "b151ada6ab0db7f7539f36bba67f3bc8c24fb9eb33b488cd4dc4123c1fdae590"),
}

# Out-of-tree evidence read by this lane (not verifiable from this tree; recorded as read, values carried with labels).
EXTERNAL = {
    "DCR003_PREREG": {
        "path": "docs/baseline/DCR-003/dcr003_eval_prereg_v1.json",
        "branch": "lane-dcr003-match", "commit": "99af82a (committed alone before evaluation)",
        "sha256": "13b27c04265660c08a457bab0d03d86d1798028f5672fda008d19bc455f77b9b",
        "use": "assumed antenna impedance planning ranges (R_A 0.5-5 ohm, X_A 164.1 ohm x 0.7-1.3, Wheeler, P7 antenna "
               "geometry) for the RF planning envelope; remote-match line-loss relation",
    },
    "DCR003_EVALUATION": {
        "path": "docs/closure/thermal/dcr003_evaluation_v1.json",
        "branch": "lane-dcr003-match", "commit": "not committed when read (2026-10-09); Rust harness 1849fef",
        "sha256": "1a2773df5b8f5586cce9833001b1eb02b7024c72b9d1dd50c31af185bc534ee9",
        "use": "route R-1 (co-located match isolated from the ICP bracket, own radiator A_MA 0.15 m^2) admissible; "
               "R-2 (remote match) not admissible: eta_line 0.022 / 0.228 / 0.933 at the conservative / reference / "
               "favourable corners; DCR-DBF1-003 resolution WITHDRAWN proposed to the coordinator",
    },
}

LABELS = ["BENCH_DESIGN_NOT_A_MEASUREMENT", "NOT_A_PERFORMANCE_PREDICTION", "ARITHMETIC_ON_REGISTERED_VALUES"]
K_B = 1.380649e-23
R_GAS = 8.314462618
E = 1.602176634e-19
T_G_K = 300.0  # registration RI-06
SPECIES_MOLAR_KG = {"N2": 0.0280134, "O": 0.015999, "O2": 0.031998, "Xe": 0.131293, "Ar": 0.039948}
K_ONE_SIDED = 1.6448536269514722  # Phi^-1(0.95), abep_assess::neutralization::MARGIN_K_MIN


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_pins() -> dict:
    out = {}
    for key, (rel, want) in PIN.items():
        p = ROOT / rel
        got = sha(p)
        if got != want:
            sys.exit(f"REFUSED: {rel} sha256 {got} != pinned {want}")
        out[key] = json.loads(p.read_text()) if rel.endswith(".json") else None
    return out


def pin_list() -> list:
    return [{"key": k, "path": r, "sha256": s} for k, (r, s) in PIN.items()]


def item(items: list, iid: str) -> dict:
    for it in items:
        if it.get("id") == iid:
            return it
    sys.exit(f"REFUSED: id {iid} not found")


def r(x: float, n: int = 4) -> float:
    return float(f"{x:.{n}g}")


# ---------------------------------------------------------------- derived arithmetic
def current_targets(cl: dict) -> list:
    rows = []
    for mode, d in cl["bounds_M_B"]["per_mode"].items():
        for tp in d["thrust_points"]:
            rows.append({"mode": mode, "T_mN": round(tp["T_N"] * 1e3, 3), "I_e_req_LB_A": r(tp["I_e_req_LB_A"]),
                         "heaviest_ion_u": d["m_heaviest_u"],
                         "P_abs_min_conservation_W": {k: r(v) for k, v in tp["P_abs_min_cons_W"].items()}})
    return rows


def bias_ranges(a1: dict) -> dict:
    rows = [x for x in a1["window_N_plus_AIR"] if x["window"] == "OPEN"]
    dphi_max = max(x["dPhi_max_V"] for x in rows)
    dphi_max_min = min(x["dPhi_max_V"] for x in rows)
    vfl = [x["dPhi_floating_V"] for x in rows]
    xe_floor = a1["floors"]["Xe+"]["E_floor_eV_on_T_e_grid"]
    t_e_grid = [2.0, 3.0, 4.0, 5.0, 6.0]
    xe_vfl = [f - t / 2.0 for f, t in zip(xe_floor, t_e_grid)]
    need = max(dphi_max, max(xe_vfl))
    fine_range = math.ceil(need / 10.0) * 10.0
    return {
        "N_plus_dPhi_max_V": [r(dphi_max_min), r(dphi_max)],
        "N_plus_V_floating_V": [r(min(vfl)), r(max(vfl))],
        "Xe_plus_V_floating_V_on_T_e_grid_2_6_eV": [r(v) for v in xe_vfl],
        "fine_range_requirement_V": r(need),
        "fine_range_selected_V": fine_range,
        "fine_resolution_selected_V": 0.1,
        "fine_resolution_basis": "<= T_e,min / 20 of the A1 T_e grid (2 eV): resolves the few-T_e window between V_fl and "
                                 "dPhi_max (selected engineering value)",
        "n_s_required_m3": [r(min(x["n_s_req_m3"] for x in rows)), r(max(x["n_s_req_m3"] for x in rows))],
        "collector_ion_flux_A_equiv": [r(min(x["collector_ion_flux_current_min_A"] for x in rows)),
                                       r(max(x["collector_ion_flux_current_min_A"] for x in rows))],
        "A_coll_m2": r(a1["A_coll_m2"]),
        "T_e_max_open": a1["window_summary_N_plus"],
    }


def rf_envelope() -> list:
    """Planning envelope only: the DCR-003 prereg corners (assumed impedance), P_del = 500 W (DBF1-RF-02 end)."""
    corners = {"CONSERVATIVE": (0.5, 213.3), "REFERENCE": (1.0, 164.1), "FAVOURABLE": (5.0, 114.8)}
    out = []
    for name, (ra, xa) in corners.items():
        for p in (200.0, 500.0):
            i_rms = math.sqrt(p / ra)
            zmag = math.hypot(ra, xa)
            v_pk = math.sqrt(2.0) * i_rms * zmag
            out.append({"corner": name, "R_A_ohm": ra, "X_A_ohm": xa, "P_delivered_W": p, "I_ant_rms_A": r(i_rms),
                        "V_ant_peak_V": r(v_pk), "rating_candidate_k_RF_1p5_V": r(1.5 * v_pk)})
    return out


def pumping(cl: dict) -> list:
    flows = [(f["flow"], f["mdot_kg_s"]) for f in cl["bounds_M_B"]["B5_greuse_pressure_information"][1:]]
    flows.append(("TK-31 Ar anchor (P1 F2, 70 sccm)", 2.079e-6))
    out = []
    for name, mdot in flows:
        for sp, m in SPECIES_MOLAR_KG.items():
            if ("Ar" in name) != (sp == "Ar"):
                continue
            q = mdot / m * R_GAS * T_G_K  # Pa m^3 / s
            out.append({"flow": name, "species": sp, "mdot_mg_s": r(mdot * 1e6), "Q_Pa_m3_s": r(q),
                        "S_eff_L_s_at_p_b": {f"{p:g} Pa": r(q / p * 1e3) for p in (1e-3, 1e-2, 0.028)}})
    return out


def margin_detectability() -> list:
    out = []
    for rel in (0.005, 0.01, 0.02, 0.05):
        c = K_ONE_SIDED * math.sqrt(2.0) * rel
        out.append({"u_rel_I_e_equals_u_rel_I_d": rel, "minimum_M_n_for_M_n_LB_gt_0": r(c / (1.0 - c)),
                    "relation": "M_n,LB = M_n - k u_M, u_M = (1 + M_n) sqrt(2) u_rel, k = 1.6449"})
    return out


def eta_p_resolution() -> dict:
    # eta = 1 - R_ant / R_tot ; u(eta) = (1 - eta) sqrt(2) u_rel(R) for equal relative R uncertainties
    target_u = 0.02
    rows = []
    for eta in (0.05, 0.1, 0.18, 0.35):
        rows.append({"eta_p": eta, "u_rel_R_each_for_u_eta_0p02": r(target_u / ((1 - eta) * math.sqrt(2.0)))})
    return {"u_eta_p_target_k1": target_u,
            "basis": "half the gap between the published anchor eta_p 0.1 (TK-26) and the lowest analog-needed Xe value "
                     "0.18 (closure M-C), at k = 2: separates them (selected engineering value, proposed for registration)",
            "relation": "eta_p = R_p / (R_p + R_ant) = 1 - R_cold / R_hot (P2 ZM-C, anchor Eq. (1)); "
                        "u(eta_p) = (1 - eta_p) sqrt(u_rel(R_cold)^2 + u_rel(R_hot)^2)",
            "rows": rows}


def power_budget(pl: dict, targets: list) -> dict:
    line = pl["rf_trade_line"]
    a, b = line[1], line[2]
    slope = (b["P_bus_icp_W"] - a["P_bus_icp_W"]) / (b["P_fwd_W"] - a["P_fwd_W"])
    icpt = a["P_bus_icp_W"] - slope * a["P_fwd_W"]
    pts = []
    for p in pl["points"]:
        av = p["icp_power_allocation_check"]["P_ICP_available_W"]
        pf = (av - icpt) / slope if av > icpt else None
        pts.append({"point": p["id"], "mode": p["mode"], "P_ICP_available_W": r(av),
                    "P_fwd_ceiling_W": r(pf) if pf is not None else "NO_ROOM_AT_THE_REGISTERED_P_d",
                    "verdict_in_P6": p["icp_power_allocation_check"]["verdict"]})
    return {"relation": f"P_bus,ICP = {r(icpt)} W + {r(slope)} x P_fwd (P6 rf_trade_line, linear between 100 and 200 W)",
            "P6_reference_P_fwd_W": 200.0, "points": pts,
            "note": "P-25 / P-WORST have no ICP room at the registered P_d = 1,350 W band end (P6: a sizing band, not the "
                    "flight ceiling); the derived Hall requirement P_d,max governs there. Ceilings are information for "
                    "the owner's GNG-ICP-01 criterion (b), not criteria."}


# ---------------------------------------------------------------- documents
def design(pins: dict) -> dict:
    p1, p2, icd, dbf, cl, a1 = pins["P1"], pins["P2"], pins["ICD"], pins["DBF11"], pins["ICP_CLOSURE"], pins["ICP_A1"]
    it = lambda iid: item(dbf["items"], iid)  # noqa: E731
    p1i = lambda iid: item(p1["items"], iid)  # noqa: E731
    icdi = lambda iid: item(icd["items"], iid)  # noqa: E731
    br = bias_ranges(a1)
    targets = current_targets(cl)
    g = it("DBF1-ICP-02")["value"]

    def fa(iid, name, value, units, ev, unc, src, state="FROZEN FOR EM"):
        return {"id": iid, "name": name, "value": value, "units": units, "evidence_class": ev, "uncertainty": unc,
                "source": src, "closure_state": state}

    hardware = [
        fa("BD-01", "ICP topology", it("DBF1-ICP-01")["value"], "-", "owner decision", "categorical",
           "DBF1-ICP-01"),
        fa("BD-02", "dielectric bore (vessel)", f"borosilicate (pyrex class) tube, inner radius {g['r_aperture']} m, "
           f"length {g['L_module']} m, wall 3 mm", "m", "literature topology precedent (bore material, level 3); "
           "geometry engineering assumption (level 7); wall thickness assumed (P7 N_VESSEL)",
           "flight dielectric not selected (P3-R-03); bench uses the DBF-1.1 geometry exactly",
           "DBF1-ICP-02, DBF1-ICP-07; thermal_cases_prereg_v1 N_VESSEL"),
        fa("BD-03", "module envelope", g, "m; -", "engineering assumption (level 7)", "F6 search not run",
           "DBF1-ICP-02"),
        fa("BD-04", "antenna (bench baseline)", "external helical coil, 3 turns, 6 x 1 mm copper tube, coil radius "
           "75 mm, pitch 12 mm (L_A ~ 1.93 uH, X_A ~ 164 ohm cold, Wheeler)", "-",
           "assumed (level 7): P7 N_ANTENNA geometry; pitch and L_A from the DCR-003 preregistration (verify)",
           "N_ant / d_ant not frozen (F6-X-06, F6-X-09); X_A planning range x0.7-1.3",
           "thermal_cases_prereg_v1 /nodes N_ANTENNA; DCR003_PREREG (external); P1-IT-61 geometry variant matrix",
           "FROZEN FOR EM (bench variant matrix P1-IT-61 registered before use)"),
        fa("BD-05", "ion collector (C-type)", "C-type electrode on the bore inner wall, 0.10 m axial, axial slit for RF "
           f"penetration, area {br['A_coll_m2']} m^2; separately biased and metered; ICP body floating",
           "m, m^2", "literature topology precedent (level 3)", "flight collector detail ICD ICP-21 at LOCK-1",
           "DBF1-ICP-04; A1 A_coll_m2"),
        fa("BD-06", "collector material", "Ar engineering runs: 316L permitted (P1-IT-19). N2, O2-bearing and Xe runs: "
           "INCONEL 600 from the procured lot (DBF1-MAT-03 primary; IN601 backup), serialized replaceable collector "
           "with pre / post profilometry", "-", "owner decision / P8 selection",
           "sputter yields of the procured lot by TP-04", "P1-IT-19; DBF1-MAT-03; materials_gates_v1 IN600-CO-SPUTTER"),
        fa("BD-07", "electron-collecting electrode (CFG-CAP-OFF capacity sink)",
           f"dedicated, isolated, instrumented electrode across the downstream aperture (RI-02 representation: "
           f"pi R^2 = {r(math.pi * g['r_aperture'] ** 2)} m^2), perforated / mesh with a registered open-area fraction "
           "so the G-REUSE outflow is not blocked; actively cooled for the PS-EC supply corner (350 V x 8.33 A)", "m^2",
           "owner decision (A9.4 P1Q-10 option A) + engineering selection", "geometry, position and reference "
           "registered at P1-G0 (P1-IT-36); measured p_ICP carries the blockage effect", "P1-IT-36, P1-IT-38; RI-02"),
        fa("BD-08", "magnetic configuration", "unmagnetized ICP; CFG-CAP-OFF records with H-1 coils off (B_ICP,max 0 "
           "T, RI-04) and, as a registered factor, at the registered H-1 coil setting (P1 F6)", "T",
           "owner decision (ICD ICP-32) / registration RI-04", "geomagnetic and remanent fields recorded",
           "ICD ICP-32; RI-04; P1 run_matrix F6"),
        fa("BD-09", "module interface", "IP-NEU datum of the KC-1 carrier; controlled interim harness drawing "
           "(id at P1-G0); LOCK-1 ICD revision", "-", "owner decision", "categorical",
           "P1-IT-62; ICD ICP-01, ICP-06"),
    ]

    rf_chain = {
        "topology": icdi("ICP-13")["value"],
        "frequency_MHz": it("DBF1-RF-01")["value"],
        "forward_power_envelope_W": it("DBF1-RF-02")["value"],
        "measurement_plane": p1i("P1-IT-04")["value"],
        "match": {
            "value": it("DBF1-RF-03")["value"],
            "location_evidence": "DCR-DBF1-003 evaluation (lane-dcr003-match, external, read 2026-10-09): R-1 co-located "
                                 "match isolated from the ICP bracket with its own radiator is admissible; R-2 remote "
                                 "match is not (matched-line loss into the unmatched antenna leaves eta_line 0.02-0.93). "
                                 "The bench therefore keeps the match local (DBF1-RF-03 unchanged) and builds the R-1 "
                                 "isolation as the bench mount (Ti standoffs, plated RF lead), so the bench match thermal "
                                 "state is flight-representative.",
            "tuning": "two adjustable elements re-tuned per set point to minimum reflection (TK-23 practice); position "
                      "encoders logged (INS-P2-12)",
        },
        "instruments": [{"id": x["id"], "name": x["name"]} for x in p2["instrument_list"]],
        "impedance_methods": [{"id": x["id"], "name": x["name"]} for x in p2["z_antenna_methods"]],
        "ratings": {
            "status": "TBD_AFTER_IMPEDANCE_MAP (owner A9.2): final ratings = k_RF 1.5 x V_ant,peak at the worst measured "
                      "P2 mismatch / operating point (ICPQ-11, ICD ICP-44)",
            "planning_envelope": rf_envelope(),
            "planning_rule": "bench procurement quotes match capacitors, RF feedthrough and antenna leads against the "
                             "CONSERVATIVE corner at 500 W (planning only, assumed impedance); the power ladder ascends "
                             "with the V/I probe reading V_ant and a provisional trip at rated / 1.5 until P2 freezes the "
                             "ratings. The published analog R_total 0.4 ohm (TK-25) lies below the 0.5 ohm planning "
                             "corner: the conservative corner is not a proven bound, so V_ant is measured, not assumed.",
            "evidence_class": "assumed (DCR-003 planning ranges, level 7); never a rating",
        },
        "protection": [p1["safety_interlocks"][i]["function"] for i in (0, 1, 2)],
        "calorimetric_cross_check_k_x": p1i("P1-IT-24")["value"],
        "at_power_loss_model_k_loss": p1i("P1-IT-58")["value"],
    }

    collector_bias = {
        "window_requirement": a1["requirement"],
        "derived": br,
        "supplies": [
            {"id": "PS-EC", "terminal": "electron_collector vs ion collector (CFG-CAP-OFF, RI-03 reference)",
             "range_V": [0.0, 350.0], "current_limit_A": p1i("P1-IT-06")["value"],
             "fine_range_V": [0.0, br["fine_range_selected_V"]], "fine_resolution_V": br["fine_resolution_selected_V"],
             "basis": "RI-03 grid 25-350 V (DBF1-ICP-06 class); P1-IT-06 8.33 A stand ceiling; fine range covers the A1 "
                      "window (N+ dPhi_max <= 36.9 V; Xe+ V_fl <= 31.6 V at T_e 6 eV)",
             "corner_power_W": r(350.0 * p1i("P1-IT-06")["value"]),
             "evidence_class": "registered ranges + selected engineering values"},
            {"id": "PS-CB", "terminal": "ICP_COLLECTOR_BIAS: ion collector vs ICP body (floating network)",
             "range_V": [-350.0, br["fine_range_selected_V"]], "current_limit_A": p1i("P1-IT-06")["value"],
             "fine_range_V": [-br["fine_range_selected_V"], br["fine_range_selected_V"]],
             "fine_resolution_V": br["fine_resolution_selected_V"],
             "basis": "bipolar: the collector must be set a few T_e below floating (A1) and swept through floating for "
                      "the collector I-V; the negative extension to the 350 V class reproduces the analog cathodic "
                      "sheath (ICD ICP-21: about -100 V; P8 TP-04 energies 100 / 140 / 220 eV) for yield cross-checks "
                      "only, never as an operating point",
             "evidence_class": "registered ranges + selected engineering values"},
        ],
        "flight_ledger_cross_check": "P6 term ICP-BIAS 10 W [0, 20] W is an assumption flagged VERIFY / UPDATE_FROM_P1_IT_18. "
                                     "The bench logs P_bias = V_bias I_bias per point; a measured value outside [0, 20] W "
                                     "updates P6 (not this design).",
        "collector_range_registration": "P1-IT-18 values registered at P1-G0 from these ranges",
    }

    gas = {
        "mode": it("DBF1-ICP-05")["value"],
        "evidence_order": icdi("ICP-30")["value"],
        "blocks": [
            {"gas": "Ar", "label": "ENGINEERING_ONLY_NON_SCORING", "gate": "ICP-45A",
             "note": "never counts toward the atmospheric requirement"},
            {"gas": "N2", "label": "EM-N2 / ICP-45N", "gate": "ICP-45N",
             "note": "first record class usable for an atmospheric neutralization claim"},
            {"gas": "N2 + O2 mixtures", "label": "NO_ATOMIC_O",
             "composition": "O-nuclei fraction chi_O spanning the frozen-state corners 0.0794 and 0.8399 (RI-06); "
                            "mixture certified by the gas supplier",
             "note": "molecular O2 only; never atomic-O or AO-life evidence (owner rows 36, 132)"},
            {"gas": "Xe", "label": "XE_CONTINGENCY bench", "gate": "ICP-45X",
             "note": "same module (A9.19: one ICP serves both modes); dedicated capped port available as the declared "
                     "G-XE variant"},
        ],
        "atomic_O": "not produced or claimed on this bench; the separate AO programme (P8 TP-03, DEGROH2006 Kapton witness "
                    "method) covers atomic-O materials and life",
        "O2_service": "wetted parts cleaned to ASTM G93 Level C; no silver (ICD ICP-30, owner rows 103, 107)",
        "flow_control": "flow set through the H-1 gas path (G-REUSE) to reach the registered p_ICP nodes; MFC traceability "
                        "by rate-of-rise / transfer calibration (P1-IT-11); dedicated ICP feed only as a declared "
                        "DIAGNOSTIC variable (P1-IT-14)",
        "p_ICP_nodes_Pa": [0.001, 0.003, 0.01, 0.03, 0.1],
        "p_ICP_basis": "RI-06 registered grid; covers the flight G-REUSE values (<= 0.0021 Pa O at 12 mN, <= 0.0091 Pa at "
                       "25 mN, closure B5) and the analog 0.028 Pa (TK-34)",
    }

    facility = {
        "chambers": "a smaller chamber is allowed for ICP-only engineering stages S0-S5 (P1-IT-34); one qualified "
                    "facility for score-bearing and Hall-ON stages",
        "pumping_need": pumping(cl),
        "criteria": [
            {"id": "FAC-01", "text": "base pressure <= 1e-4 Pa (10 % of the lowest registered p_ICP node, so background "
                                     "gas is a minor share at every node; selected engineering value)"},
            {"id": "FAC-02", "text": "effective pumping speed S_eff >= Q / p_b for the stage flow at the record's p_b "
                                     "(table pumping_need); supplier states speed per gas, range, compatibility (Ar, N2, "
                                     "O2-bearing, Xe), instrumentation and interface conductance (RFQ3-VAC-N01)"},
            {"id": "FAC-03", "text": "base background pressure plus two elevated p_b levels per configuration (ICD "
                                     "ICP-28, owner row 23); T-PB-MAX frozen at LOCK-1"},
            {"id": "FAC-04", "text": "p_ICP measured at the source volume for every record (VC-07 / DOM-15: a record "
                                     "without measured p_ICP is NOT_EVALUATED); chamber gauge position and calibration "
                                     "per the REG-PB practice (REF-DANKANICH2017, as referenced in the Hall transport v2 "
                                     "draft)"},
            {"id": "FAC-05", "text": "residual-gas analysis with differential pumping at base and both elevated p_b "
                                     "(RFQ2-VAC-R02)"},
        ],
        "hall_on_stages": "Hall-ON stages (S6, S7H) use the REQ-FAC-01 planning numbers (model-derived): S_eff 66,818 "
                          "(N2) / 58,466 (O2) L/s per mg/s at 1.0e-5 Torr; 13,364 / 11,693 at 5.0e-5 Torr",
    }

    diagnostics = [
        {"id": "DG-01", "quantity": "eta_p (RF coupling)", "method": "P2 ZM-A (V/I probe), ZM-B (de-embedded reflection, "
         "VNA), ZM-C (antenna current + delivered power, R_p = R_hot - R_cold at equal antenna temperature)",
         "requirement": eta_p_resolution(), "source": "P2 z_antenna_methods; TK-26"},
        {"id": "DG-02", "quantity": "RF forward / reflected / delivered power", "method": "dual directional coupler at "
         "RP-CPL, calibrated sensors, calorimetric dummy load cross-check (k_x 2), two-port line / match loss",
         "source": "P1-M-01..04; P1-IT-24"},
        {"id": "DG-03", "quantity": "collector I-V and electron-collector current", "method": "4-wire V and calibrated "
         "shunt I per reading (ICD ICP-21), every floating channel isolated to the 350 V class; RF-ON / matched RF-OFF "
         "pairs", "source": "P1-M-10, P1-M-11, P1-M-27; P1-IT-47..50"},
        {"id": "DG-04", "quantity": "Kirchhoff closure channels", "method": "ion collector, electron collector, ICP body, "
         "H-1 body single metered return, facility return, floating-anode potential", "source": "P1-IT-39, P1-IT-47"},
        {"id": "DG-05", "quantity": "T_e and n_e at the collector sheath edge", "method": "RF-compensated Langmuir probe "
         "(13.56 MHz and harmonics); u(T_e) <= 0.5 eV (half the A1 T_e grid step, selected)",
         "why": "the A1 window and DCR trigger are stated as T_e_max_open (5-6 eV) and n_s,req "
                f"{br['n_s_required_m3']} m^-3", "source": "P1-M-30; A1 dcr.trigger_condition"},
        {"id": "DG-06", "quantity": "plasma potential phi_p", "method": "emissive probe (floating-point / inflection), "
         "with the Langmuir probe as cross-check", "why": "dPhi = phi_p - V_c is the window variable",
         "source": "A1 requirement; P1-M-30"},
        {"id": "DG-07", "quantity": "ion energy distribution at the collector", "method": "retarding-field energy "
         "analyser flush with the collector, referenced to the collector potential, discriminator 0-250 V, energy "
         "resolution <= 2.5 eV (half the TP-04 5 eV yield step, selected); mean impact energy E_mean with u",
         "why": "E* = 26-38 eV ceiling (P8 DA-03) and TP-04 energies 15-60 eV + 100 / 140 / 220 eV",
         "source": "materials_gates_v1 IN600-CO-SPUTTER TP-04; A1 dcr"},
        {"id": "DG-08", "quantity": "plasma state", "method": "optical-emission photodiode (required; unlit threshold "
         "from S2 / S3 records)", "source": "INS-P2-10; P1-IT-54"},
        {"id": "DG-09", "quantity": "temperatures", "method": "antenna, dielectric, collector, match, RF source (ICD "
         "ICP-34); thermal abort at limit - 50 K (P1-IT-25)", "source": "ICD ICP-34"},
        {"id": "DG-10", "quantity": "collector recession and deposition", "method": "serialized replaceable collector, "
         "pre / post profilometry and mass; witness coupons on the bore and H-1 exit (ICD ICP-29)",
         "source": "TP-04; ICD ICP-29"},
        {"id": "DG-11", "quantity": "pressure and gas", "method": "p_ICP gauge at the source volume, chamber gauge, RGA",
         "source": "P1-M-16..20; FAC-04, FAC-05"},
    ]

    safety = {
        "isolation_class_V": it("DBF1-ICP-06")["value"],
        "design_withstand_V": p1i("P1-IT-43")["value"],
        "initial_DWV": p1i("P1-IT-44")["value"],
        "reverification": p1i("P1-IT-45")["value"],
        "gas_line_isolation": p1i("P1-IT-20")["value"],
        "rf_insulation": "separate from the 350 V DC class: k_RF 1.5 x V_ant,peak plus the collector / body DC "
                         "potential for antenna-to-collector clearance, creepage and Paschen (ICD ICP-44); planning "
                         "envelope in rf_chain.ratings",
        "interlocks": [x["id"] + ": " + x["hazard"] for x in p1["safety_interlocks"]],
        "rf_permissives": icdi("ICP-16")["requirement"],
        "personnel": "shielded antenna and enclosure, RF leakage survey before first power (P1-SI-04); HV hipot current "
                     "limited (P1-SI-11); oxygen-deficiency assessment for Ar / N2 / Xe release (P1-SI-07)",
    }

    return {
        "schema": "abep_icp_bench_design_v1",
        "id": "ICP-BENCH-DESIGN-v1",
        "item": "A9.39 scope item 3: ICP bench-design closure (closure board P4)",
        "lane": "L-ICP-BENCH",
        "labels": LABELS,
        "baseline": {"DBF-1.1_lock": PIN["DBF11_LOCK"][1], "architecture": "PHYSICS ARCHITECTURE CLOSED - DETAILED "
                     "DESIGN / EM VERIFICATION OPEN (A9.39)"},
        "pins": pin_list(),
        "external_evidence": EXTERNAL,
        "evidence_needed": {
            "eta_p": "RF coupling efficiency (DG-01)",
            "I_e_cap": "electron-current capacity CFG-CAP-OFF, I_e,cap = I_on - I_off (P1-IT-38, A9.5 P1Q-16)",
            "bias_window_and_ion_energy": "collector dPhi in (V_fl, E*/e - T_e/2], E_mean <= E* (A1; P8 DA-03)",
            "neutralization_margin": "M_n = I_e,cap / I_d,max,H1 - 1, M_n,LB > 0 (HC-05)",
            "validated_bench_cell": "VC-01..VC-08 (abep_icp::v2::validation)",
        },
        "current_targets": {
            "governing": "I_d,max,H1 (RVM-IT-19, TBD_AFTER_EVIDENCE: registered from measured H-1 operation)",
            "necessary_lower_bounds": targets,
            "stand_ceiling_A": p1i("P1-IT-06")["value"],
            "power_envelope_bound_A": p1i("P1-IT-08")["value"],
            "label": "CONSERVATION_BOUND / NOT_A_PERFORMANCE_PREDICTION (closure B1 / B2)",
        },
        "hardware": hardware,
        "rf_chain": rf_chain,
        "collector_bias": collector_bias,
        "gas": gas,
        "facility": facility,
        "diagnostics": diagnostics,
        "safety_isolation": safety,
        "power_budget_information": power_budget(pins["POWER"], targets),
        "margin_detectability": margin_detectability(),
        "analysis_updates": xe_status(),
        "closure": closure_state(),
    }


def xe_status() -> dict:
    return {
        "question": "Xe rate-set admission from GK2008: quick and source-backed?",
        "answer": "NOT QUICK: not done in this lane (no broad chemistry campaign, A9.39 scope). The method is registered "
                  "(NP-ICP-CHEM-AIR addendum_01, sha256 5dfd1c59..., committed 6fba18d and merged here); none of its "
                  "build steps is complete.",
        "state": "abep-icp-xe-0.0 NOT_ADMITTED (registry 074daff9; snapshot pin d4749e7 merged here)",
        "remaining": [
            "XE-ION-01: sigma(Xe+) from Mukundan & Bhardwaj 2016 Table 2 (arXiv:1604.08449, sha256 352c3233...) with the "
            "two-dataset unit cross-check (Stephan & Maerk sigma(Xe+) and GK2008 Table D-1 Rapp & Englander-Golden, "
            "<= 10 % at 35-100 eV) - a draft table exists only as uncommitted work on lane-icp-closure; the Stephan & "
            "Maerk source has not been read",
            "XE-EXC-01: GK2008 Table D-1 Hayashi column transcribed by pdftotext -bbox, onset 8.315 eV, header 10.0 eV, "
            "checked against GK2008 Table E-1 (<= 10 % at 1-10 eV)",
            "XE-EL-01: sigma_m by trapezoid integration of the Mukundan & Bhardwaj Table 1 DCS (5-1000 eV), zero below "
            "5 eV (rate a lower bound below T_e ~ 5 eV)",
            "XE-WALL-01: structural record naming parent EQ-03 / EQ-09 / EQ-18 (VER-12 stays a parent verify item)",
            "A1-STATUS evidence records E1..E9 per process, own_tables.json, ICP_CHEM_PINNED.toml bump (one table per "
            "commit, A1-OWN byte-for-byte regeneration test)",
            "A1-CLASS class_address rows for Xe / Xe+",
            "A1-CA12: ca12_xe_v1.json (XE-ION-02 direct route F_ion; XE-ION-03 bound B-XE-ION3-SAT; registered "
            "assumptions B-XE-ION2-ION and B-XE-REC; XE-EXC-02 envelope); OQ-CHEM-15 stays with the owner",
            "A1-XE-ADMIT: registry label abep-icp-xe-0.1 ADMITTED with conditions (CONDITIONAL_ON_REGISTERED_ASSUMPTIONS)",
            "A1-XE-PATH: registry-backed Xe set path in abep-icp (RegisteredSet 'registry:XE/<scenario>')",
            "A1-SNAPSHOT: a new ICP closure record version (v2) evaluated on the new registry; v1 stays on the 0.0 snapshot",
        ],
        "bench_link": "the bench does not wait for admission: HC-05 accepts a MEASURED I_e,cap at the registered point "
                      "(abep_assess::neutralization, CapacityBasis::Measured). Admission is needed for model I_e,cap "
                      "outside measured points, which then needs a VALIDATED_BENCH cell (TM-7).",
    }


def closure_state() -> dict:
    return {
        "item": "P4 RF/ICP neutralizer (A9.39 scope item 3: bench-design closure)",
        "state": "FROZEN FOR EM",
        "meaning": "the bench / EM neutralizer configuration, its test configuration, measurement plan and pass / fail "
                   "criteria are frozen on registered evidence; coupling efficiency, electron-current capacity, collector "
                   "ion energy and the neutralization margin are verification-by-test items (A9.39 conclusion v2 "
                   "sec. 5)",
        "sub_items": [
            {"id": "P4-BENCH-HW", "state": "FROZEN FOR EM", "note": "hardware, gas, facility, diagnostics, safety"},
            {"id": "P4-BENCH-RF-RATINGS", "state": "FROZEN FOR EM",
             "note": "rating rule frozen (k_RF 1.5 x V_ant,peak at the worst P2 point); values set by the P2 map by "
                     "owner rule A9.2 (TBD_AFTER_IMPEDANCE_MAP), planning envelope registered"},
            {"id": "P4-TEST-PLAN", "state": "FROZEN FOR EM",
             "note": "icp_bench_test_plan_v1.json locked; LOCK-1 registration slots listed in it"},
            {"id": "P4-ANALYSIS-CAPACITY", "state": "BLOCKED BY SPECIFIC MISSING EVIDENCE",
             "note": "unchanged from icp_closure_v1.json (model I_e,cap withheld: AIR / Xe rate sets not admitted; "
                     "I_d,max,H1 not registered); now carried as a bench-verification item, not a design blocker"},
            {"id": "GNG-ICP-01", "state": "NOT_EVALUATED",
             "note": "criteria PENDING_OWNER_ACCEPTANCE (owner item; the test plan maps the recorder proposal onto "
                     "measurable criteria for review)"},
        ],
        "governing_evidence": [
            {"path": "docs/closure/icp_bench/icp_bench_design_v1.json", "sha256": "see icp_bench_test_plan_lock_v1.json"},
            {"path": PIN["ICP_CLOSURE"][0], "sha256": PIN["ICP_CLOSURE"][1]},
            {"path": PIN["ICP_A1"][0], "sha256": PIN["ICP_A1"][1]},
            {"path": PIN["P1"][0], "sha256": PIN["P1"][1]},
            {"path": PIN["P2"][0], "sha256": PIN["P2"][1]},
        ],
        "dcr": "none: no DBF-1 / DBF-1.1 value changes (DBF1-ICP-04 DCR trigger pre-declared in A1, fires only on a "
               "measured window closure)",
    }


def test_plan(pins: dict, des: dict) -> dict:
    tgt = des["current_targets"]["necessary_lower_bounds"]
    pf = [100.0, 200.0, 300.0, 400.0, 500.0]
    blocks = [
        {"id": "TM-0", "stage": "P1-S0..S2", "what": "readiness: DWV 1.05 kV DC / 60 s per insulation path, interlock "
         "functional test, RF cold checkout into the calorimetric load (k_x 2), line / match two-port loss, cold "
         "antenna impedance by VNA, unlit heating and pickup, photodiode dark / unlit records",
         "exit": "P1-G0..G2; RF trip thresholds frozen from S2 (A9.2)", "gas": "none / Ar"},
        {"id": "TM-1", "stage": "P1-S3", "what": "ignition map: ascending P_fwd ladder at each p_ICP node; ignition, "
         "extinction, delay, match setting, photodiode state", "gas": "Ar, N2, N2+O2 (NO_ATOMIC_O), Xe",
         "levels": {"P_fwd_W": pf, "p_ICP_Pa": des["gas"]["p_ICP_nodes_Pa"]}, "repeats": ">= 3 independent ignitions per "
         "point (P1Q-05 form)"},
        {"id": "TM-2", "stage": "P2 hot map", "what": "eta_p: R_cold (unlit, same antenna temperature) and R_hot at every "
         "lit TM-1 point; ZM-A / ZM-B / ZM-C with the k_loss 2 agreement rule", "gas": "Ar, N2, N2+O2, Xe",
         "levels": {"P_fwd_W": pf, "p_ICP_Pa": des["gas"]["p_ICP_nodes_Pa"]}},
        {"id": "TM-3", "stage": "P1-S4 / S7 (CFG-CAP-OFF, ICP-45A / -45N / -45O / -45X)",
         "what": "capacity surface I_e = f(P_RF, p_ICP, Z, V_ec) with the Hall discharge supply physically disconnected "
                 "(anode floating), electrons to the dedicated electron collector; matched RF-OFF record at every point; "
                 "Kirchhoff closure; ascending current limit with hold points to the 8.33 A stand ceiling",
         "levels": {"P_fwd_W": pf, "p_ICP_Pa": des["gas"]["p_ICP_nodes_Pa"],
                    "V_ec_V": {"fine": "0-40 V in 0.5 V steps", "coarse": [25.0, 50.0, 100.0, 200.0, 350.0]},
                    "H1_coils": ["OFF (RI-04)", "registered H-1 setting (h1_point_id)"]},
         "gas": "Ar (ICP-45A), N2 (ICP-45N), N2+O2 at chi_O 0.0794 and 0.8399 (NO_ATOMIC_O), Xe (ICP-45X)"},
        {"id": "TM-4", "stage": "collector window", "what": "at each TM-3 point with I_e,cap,LB >= the mode's I_e,req,LB: "
         "PS-CB sweep through floating in the fine range; RFEA ion-energy distribution, emissive-probe phi_p, Langmuir "
         "T_e and n_s at the sheath edge; collector I-V", "gas": "N2, N2+O2, Xe"},
        {"id": "TM-5", "stage": "P1-S5", "what": "stability dwells and re-ignitions at candidate points; drift, step, "
         "ignition fraction (P1-IT-30 criteria)", "gas": "N2, Xe"},
        {"id": "TM-6", "stage": "P1-S6 / S7H (Hall-ON)", "what": "OQ-VI-05 topology control, then the NEUTRALIZATION_"
         "CONSISTENCY record at each registered H-1 point: I_d, I_e,ICP, current closure incl. hall_anode, coupling "
         "voltage, collector potentials, RF power; descriptive only", "gas": "Ar, N2, Xe"},
        {"id": "TM-7", "stage": "model validation partition", "what": "CAL / VAL partition of TM-2..TM-4 records frozen "
         "(sha256) before any value is examined (VC-06 / IN-27), one role per operating point; VAL cells for EM-N2 and "
         "Xe compared with NP-ICP v2 once its chemistry is admitted (VC-01 |z| <= 2)", "gas": "N2, Xe"},
        {"id": "TM-8", "stage": "facility effects", "what": "selected TM-3 / TM-4 points at base p_b and two elevated p_b "
         "levels (ICD ICP-28)", "gas": "N2, Xe"},
        {"id": "TM-9", "stage": "collector life witness", "what": "long dwell at the selected TM-4 operating point on a "
         "serialized IN600 collector; profilometry, mass, deposition witnesses; with P8 TP-04 yields of the same lot",
         "gas": "N2, N2+O2"},
    ]
    criteria = [
        {"id": "C-01", "name": "capacity-record admission", "rule": "Kirchhoff |R_I| <= 3 u_R AND |R_I| / max(I_e, "
         "I_scale,min) <= 0.02; instrument adequacy 3 u_R <= 0.02 |I_e| else NOT_EVALUATED_INSTRUMENT; matched RF-OFF; "
         "measured p_ICP; anode physically disconnected", "authority": "A9.5 P1Q-15 (owner); P1-IT-47..51; VC-07",
         "status": "OWNER_DECIDED"},
        {"id": "C-02", "name": "capacity definition", "rule": "I_e,cap = I_e,collector,RFON - I_e,collector,RFOFF, signed, "
         "no clipping", "authority": "A9.5 P1Q-16", "status": "OWNER_CONFIRMED"},
        {"id": "C-03", "name": "ICP-45 / HC-05 neutralization margin", "rule": "per gas block and registered H-1 point: "
         "M_n = I_e,cap / I_d,max,H1 - 1, M_n,LB = M_n - k u_M > 0 with alpha 0.05 one-sided, k >= 1.6449; NOT_EVALUATED "
         "until I_d,max,H1 and its uncertainty are registered",
         "authority": "HC-05 (config/assessment/gate_thresholds_v1.json); P1-IT-29; A9.1 ICP-45",
         "status": "REGISTERED", "basis_options": ["MEASURED at the point (supersedes the model)",
                                                   "MODEL inside a VALIDATED_BENCH cell (C-07)"]},
        {"id": "C-03N", "name": "necessary-condition screen before I_d,max,H1 exists", "rule": "report I_e,cap,LB >= "
         "I_e,req,LB per mode / thrust; never PASS", "targets": tgt, "label": "NECESSARY_CONDITION_NOT_A_GATE",
         "status": "REGISTERED"},
        {"id": "C-04", "name": "eta_p measurement adequacy", "rule": "u(eta_p) <= 0.02 (k = 1) at every TM-2 point used for "
         "a decision, else NOT_EVALUATED_INSTRUMENT; eta_p carries no pass / fail threshold (an input, not a "
         "requirement)", "status": "PROPOSED_FOR_LOCK-1_REGISTRATION"},
        {"id": "C-04B", "name": "power budget (GNG-ICP-01 (b) mapping)", "rule": "the P_fwd at which C-03 is met <= the P6 "
         "P_fwd ceiling of the matching ledger point (power_budget_information); excess reported as a P6 trade-line "
         "change", "status": "PROPOSED_FOR_OWNER_ACCEPTANCE"},
        {"id": "C-05", "name": "collector ion energy / bias window", "rule": "at the C-03 operating point: measured E_mean + "
         "k u(E_mean) <= E*(allowance) from the TP-04 yields of the procured lot (until TP-04: the P8 prior E* 26.1-37.9 "
         "eV, PROVISIONAL); measured T_e <= T_e_max_open of the A1 row; failure fires the pre-declared DCR trigger on "
         "DBF1-ICP-04 (collector area / topology / replaceability), never a material swap",
         "authority": "A1 dcr; P8 DA-03 / IN600-CO-SPUTTER", "status": "REGISTERED (E* value PROVISIONAL until TP-04)"},
        {"id": "C-06", "name": "neutralization consistency (Hall-ON)", "rule": "descriptive: current closure, sustained "
         "discharge per P1-IT-32, coupling voltage; never PASS / FAIL and never I_e,cap", "authority": "A9.4 P1Q-10",
         "status": "OWNER_DECIDED"},
        {"id": "C-07", "name": "VALIDATED_BENCH cell", "rule": "partition frozen before data; every VAL point CONSISTENT "
         "(|z| <= 2), none NOT_EVALUATED; calibration records never validate their own measurand",
         "authority": "NP-ICP v2 VC-01..VC-08 (abep_icp::v2::validation)", "status": "REGISTERED"},
        {"id": "C-08", "name": "stability", "rule": "P1-IT-30 form (ignition repeatability, drift of I_e and P_refl, "
         "dwell); values frozen and hashed before the first S5 classification", "status": "OWNER_DECIDED_FORM"},
        {"id": "C-09", "name": "GNG-ICP-01", "rule": "NOT_EVALUATED until the owner accepts criteria; recorder proposal "
         "RP-A919-01 (a) I_e,cap >= I_d,max with a preregistered margin -> C-03; (b) RF W/A within the power budget -> "
         "C-04B; (c) repeatable ignition on N2 and Xe -> TM-1 / C-08", "status": "PENDING_OWNER_ACCEPTANCE (owner item)"},
    ]
    return {
        "schema": "abep_icp_bench_test_plan_v1",
        "id": "ICP-BENCH-TEST-PLAN-v1",
        "status": "PREREGISTRABLE_TEST_PLAN (no data exists; LOCK-1 slots listed)",
        "labels": ["NOT_SCORE_BEARING_UNTIL_LOCK-1", "NO_DATA_EXAMINED"],
        "design": "docs/closure/icp_bench/icp_bench_design_v1.json",
        "blocks": blocks,
        "ordering": pins["P1"]["run_matrix"]["ordering_rule"],
        "criteria": criteria,
        "registration_slots_before_score_bearing_data": [
            "I_d,max,H1 and u (RVM-IT-19; P1-IT-07)", "I_scale,min and u(I_k) (P1-IT-48 / -49)",
            "electron-collector geometry, position, reference (P1-IT-36)", "pressure-match tolerance (P1-IT-37)",
            "stage operating domains (P1-IT-52)", "stability values (P1-IT-30)", "RF trip thresholds (P1-IT-05)",
            "DWV leakage limits (P1-IT-55)", "TP-04 yields of the procured collector lot (E*)",
            "VC-06 partition record", "GNG-ICP-01 criteria (owner)",
        ],
        "margin_detectability": des["margin_detectability"],
    }


def md(des: dict, plan: dict, plan_sha: str) -> str:
    L = []
    a = L.append
    a("# ICP neutralizer bench-design closure v1 (A9.39 scope item 3)")
    a("")
    a("Generated by `build_icp_bench_v1.py` (`--check` reproduces it). The JSON files govern: "
      "`icp_bench_design_v1.json` and `icp_bench_test_plan_v1.json` (sha256 `" + plan_sha + "`, lock "
      "`icp_bench_test_plan_lock_v1.json`). Lane L-ICP-BENCH. Baseline DBF-1.1 (lock `257e141c…`). Nothing here is a "
      "measurement or a model prediction. All numbers are registered values or arithmetic on them.")
    a("")
    a(f"**Closure state: {des['closure']['state']}.** {des['closure']['meaning']}.")
    a("")
    a("| sub-item | state | note |")
    a("|---|---|---|")
    for s in des["closure"]["sub_items"]:
        a(f"| {s['id']} | {s['state']} | {s['note']} |")
    a("")
    a("## 1. Evidence the bench produces")
    a("")
    for k, v in des["evidence_needed"].items():
        a(f"- **{k}**: {v}")
    a("")
    a("Electron-current targets (CONSERVATION_BOUND, not predictions). The governing target is I_d,max,H1, measured on "
      "H-1 (RVM-IT-19):")
    a("")
    a("| mode | T mN | I_e,req,LB A | P_abs,min (conservation) W |")
    a("|---|---|---|---|")
    for t in des["current_targets"]["necessary_lower_bounds"]:
        a(f"| {t['mode']} | {t['T_mN']:g} | {t['I_e_req_LB_A']} | "
          + ", ".join(f"{v}" for v in t["P_abs_min_conservation_W"].values()) + " |")
    a("")
    a(f"Bench electrical sizing: stand ceiling {des['current_targets']['stand_ceiling_A']} A (P1-IT-06). The "
      f"{des['current_targets']['power_envelope_bound_A']} A power-envelope bound (P1-IT-08) is not a requirement.")
    a("")
    a("## 2. Hardware")
    a("")
    a("| id | item | value | evidence class | uncertainty | source |")
    a("|---|---|---|---|---|---|")
    for h in des["hardware"]:
        v = h["value"] if isinstance(h["value"], str) else json.dumps(h["value"])
        a(f"| {h['id']} | {h['name']} | {v} | {h['evidence_class']} | {h['uncertainty']} | {h['source']} |")
    a("")
    rf = des["rf_chain"]
    a("## 3. RF chain")
    a("")
    a(f"- Topology: {rf['topology']}")
    a(f"- Frequency {rf['frequency_MHz']} MHz; forward-power envelope {rf['forward_power_envelope_W']} W at the "
      f"reference plane ({rf['measurement_plane']}).")
    a(f"- Match: {rf['match']['value']}. {rf['match']['location_evidence']}")
    a(f"- Tuning: {rf['match']['tuning']}.")
    a("- Instruments: " + "; ".join(f"{x['id']} {x['name']}" for x in rf["instruments"]) + ".")
    a(f"- Ratings: {rf['ratings']['status']}. {rf['ratings']['planning_rule']}")
    a("")
    a("Planning envelope (assumed impedance from the DCR-003 preregistration; **not a rating**):")
    a("")
    a("| corner | R_A Ω | X_A Ω | P_del W | I_ant,rms A | V_ant,peak V | 1.5 × V_ant,peak V |")
    a("|---|---|---|---|---|---|---|")
    for e in rf["ratings"]["planning_envelope"]:
        a(f"| {e['corner']} | {e['R_A_ohm']} | {e['X_A_ohm']} | {e['P_delivered_W']:g} | {e['I_ant_rms_A']} | "
          f"{e['V_ant_peak_V']} | {e['rating_candidate_k_RF_1p5_V']} |")
    a("")
    cb = des["collector_bias"]
    d = cb["derived"]
    a("## 4. Collector and bias supplies")
    a("")
    a(f"Window (A1): {cb['window_requirement']}.")
    a("")
    a(f"- N⁺ ΔΦ_max {d['N_plus_dPhi_max_V'][0]}–{d['N_plus_dPhi_max_V'][1]} V; V_fl "
      f"{d['N_plus_V_floating_V'][0]}–{d['N_plus_V_floating_V'][1]} V (T_e 2–6 eV).")
    a(f"- Xe⁺ V_fl on the T_e grid: {d['Xe_plus_V_floating_V_on_T_e_grid_2_6_eV']} V.")
    a(f"- Fine range needed ≥ {d['fine_range_requirement_V']} V → selected {d['fine_range_selected_V']:g} V at "
      f"{d['fine_resolution_selected_V']} V resolution ({d['fine_resolution_basis']}).")
    a(f"- Required sheath-edge density {d['n_s_required_m3']} m⁻³; collector ion flux "
      f"{d['collector_ion_flux_A_equiv']} A-equivalent (A1).")
    a("")
    a("| supply | terminal | range V | fine range V | current limit A | basis |")
    a("|---|---|---|---|---|---|")
    for s in cb["supplies"]:
        a(f"| {s['id']} | {s['terminal']} | {s['range_V']} | {s['fine_range_V']} | {s['current_limit_A']} | "
          f"{s['basis']} |")
    a("")
    a(f"P6 cross-check: {cb['flight_ledger_cross_check']}")
    a("")
    g = des["gas"]
    a("## 5. Gas")
    a("")
    a(f"Mode {g['mode']}. Evidence order {g['evidence_order']}.")
    a("")
    for b in g["blocks"]:
        a(f"- **{b['gas']}** ({b['label']}): {b['note']}" + (f" {b['composition']}." if "composition" in b else ""))
    a(f"- Atomic O: {g['atomic_O']}.")
    a(f"- O₂ service: {g['O2_service']}.")
    a(f"- Flow: {g['flow_control']}.")
    a(f"- p_ICP nodes {g['p_ICP_nodes_Pa']} Pa: {g['p_ICP_basis']}.")
    a("")
    f = des["facility"]
    a("## 6. Vacuum facility")
    a("")
    a(f"{f['chambers']}.")
    a("")
    for c in f["criteria"]:
        a(f"- **{c['id']}** {c['text']}.")
    a(f"- Hall-ON: {f['hall_on_stages']}.")
    a("")
    a("Pumping need S_eff = Q / p_b at T_g 300 K (arithmetic on registered flows):")
    a("")
    a("| flow | species | ṁ mg/s | S_eff at 1e-3 Pa L/s | at 1e-2 Pa | at 0.028 Pa |")
    a("|---|---|---|---|---|---|")
    for p in f["pumping_need"]:
        s = p["S_eff_L_s_at_p_b"]
        a(f"| {p['flow']} | {p['species']} | {p['mdot_mg_s']} | {s['0.001 Pa']} | {s['0.01 Pa']} | {s['0.028 Pa']} |")
    a("")
    a("## 7. Diagnostics")
    a("")
    a("| id | quantity | method | source |")
    a("|---|---|---|---|")
    for x in des["diagnostics"]:
        a(f"| {x['id']} | {x['quantity']} | {x['method']} | {x['source']} |")
    er = des["diagnostics"][0]["requirement"]
    a("")
    a(f"η_p resolution: u(η_p) ≤ {er['u_eta_p_target_k1']} ({er['basis']}). {er['relation']}. Required relative "
      "resistance uncertainty: " + ", ".join(f"η_p {x['eta_p']}: {x['u_rel_R_each_for_u_eta_0p02']}" for x in er["rows"])
      + ".")
    a("")
    s = des["safety_isolation"]
    a("## 8. Safety and isolation")
    a("")
    a(f"- Isolation class {s['isolation_class_V']} V; design withstand ≥ {s['design_withstand_V']} V; initial DWV "
      f"{json.dumps(s['initial_DWV'])}; reverification {s['reverification']}.")
    a(f"- Gas-line isolation: {s['gas_line_isolation']}.")
    a(f"- RF insulation: {s['rf_insulation']}.")
    a(f"- RF permissives (ICD ICP-16): {s['rf_permissives']}")
    a("- Interlocks: " + "; ".join(s["interlocks"]) + ".")
    a(f"- Personnel: {s['personnel']}.")
    a("")
    a("## 9. Test matrix and criteria (`icp_bench_test_plan_v1.json`)")
    a("")
    a("| block | stage | what | gas |")
    a("|---|---|---|---|")
    for b in plan["blocks"]:
        a(f"| {b['id']} | {b['stage']} | {b['what']} | {b['gas']} |")
    a("")
    a("| id | criterion | rule | status |")
    a("|---|---|---|---|")
    for c in plan["criteria"]:
        a(f"| {c['id']} | {c['name']} | {c['rule']} | {c['status']} |")
    a("")
    a("Margin detectability (HC-05 needs M_n,LB > 0):")
    a("")
    a("| u_rel(I_e) = u_rel(I_d) | minimum M_n |")
    a("|---|---|")
    for m in plan["margin_detectability"]:
        a(f"| {m['u_rel_I_e_equals_u_rel_I_d']} | {m['minimum_M_n_for_M_n_LB_gt_0']} |")
    a("")
    pb = des["power_budget_information"]
    a(f"Power-budget information ({pb['relation']}):")
    a("")
    a("| point | mode | P_ICP,available W | P_fwd ceiling W |")
    a("|---|---|---|---|")
    for p in pb["points"]:
        a(f"| {p['point']} | {p['mode']} | {p['P_ICP_available_W']} | {p['P_fwd_ceiling_W']} |")
    a("")
    a(pb["note"])
    a("")
    a("Registration slots that must be filled before score-bearing data: "
      + "; ".join(plan["registration_slots_before_score_bearing_data"]) + ".")
    a("")
    x = des["analysis_updates"]
    a("## 10. Analysis update: Xe rate-set admission")
    a("")
    a(f"{x['answer']} State: {x['state']}.")
    a("")
    a("What remains (addendum_01 order):")
    a("")
    for i, s in enumerate(x["remaining"], 1):
        a(f"{i}. {s}")
    a("")
    a(x["bench_link"])
    a("")
    a("## 11. External evidence read (other lanes, not in this tree)")
    a("")
    for k, v in des["external_evidence"].items():
        a(f"- {k}: `{v['path']}` on `{v['branch']}` ({v['commit']}), sha256 `{v['sha256']}`: {v['use']}.")
    a("")
    return "\n".join(L)


def dump(o) -> str:
    return json.dumps(o, indent=1, ensure_ascii=False) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    pins = load_pins()
    des = design(pins)
    plan = test_plan(pins, des)
    plan_txt = dump(plan)
    plan_sha = hashlib.sha256(plan_txt.encode()).hexdigest()
    des_txt = dump(des)
    lock = {"schema": "abep_icp_bench_test_plan_lock_v1", "plan": "docs/closure/icp_bench/icp_bench_test_plan_v1.json",
            "plan_sha256": plan_sha,
            "design": "docs/closure/icp_bench/icp_bench_design_v1.json",
            "design_sha256": hashlib.sha256(des_txt.encode()).hexdigest(),
            "rule": "the plan is frozen at commit; any change is a new plan version; score-bearing data only after "
                    "the listed registration slots are filled at LOCK-1"}
    outs = {
        "icp_bench_design_v1.json": des_txt,
        "icp_bench_test_plan_v1.json": plan_txt,
        "icp_bench_test_plan_lock_v1.json": dump(lock),
        "ICP_BENCH_DESIGN_v1.md": md(des, plan, plan_sha) + "\n",
    }
    bad = []
    for name, txt in outs.items():
        p = HERE / name
        if args.check:
            if not p.exists() or p.read_text() != txt:
                bad.append(name)
        else:
            p.write_text(txt)
    if bad:
        print("MISMATCH: " + ", ".join(bad))
        return 1
    print("OK" if args.check else "written: " + ", ".join(outs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
