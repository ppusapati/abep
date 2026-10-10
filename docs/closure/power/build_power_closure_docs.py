"""A9.38 P6 power closure: write the term register (power_closure_inputs_v1.json) and render the ledger page
(power_ledger_v1.md) from the Rust-evaluated ledger record (power_ledger_v1.json).

The arithmetic lives in Rust (abep_subsystems::power::closure_v1, example power_closure_v1); this script only registers
the closing values with their evidence and renders the result. Every source is sha256-pinned.

Usage:
  python3 docs/closure/power/build_power_closure_docs.py inputs [--check]   # term register
  python3 docs/closure/power/build_power_closure_docs.py md [--check]       # page from power_ledger_v1.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent

PIN = {
    "EC": ("docs/architecture_comparison/electrical_closure/electrical_closure_data_v1.json",
           "d56f700198a64a919d736c8659b6e0aaaa01cd56521885772d2f5a40de374501"),
    "H24": ("docs/hardware/h2/h2_4_ppu_bus/h2_4_ppu_bus_v1.json",
            "5c6623612ee9ec22899083201416f7b51a10a2d7e88456d372783ce2edde26ef"),
    "H21": ("docs/hardware/h2/h2_1_hall_chamber_magnet/h2_1_hall_chamber_magnet_v1.json",
            "49b9a45e9347b141bf8bd1122ffba3ae038c9f088041e4410525e4ab8695b82d"),
    "MP5": ("docs/budgets/mass_power_a9_v5/mass_power_a9_v5.json",
            "3ff23429f5225a8a8363a784281b2f32b1df9ad69ec9934320306b080436b73a"),
    "DBF1": ("docs/baseline/DBF-1/dbf1_v1.json", "d20f1e8aa95c2d6ee0b307669500d7aaa5ea6abf4d21ddb944b7999525943e4f"),
    "M2": ("docs/milestones/M2_196_state_rfp_closure/m2_closure_record_v1.json",
           "600cf229ecdb5f91f0471f03cfdd6d287486ad21e9d9ebadde3cdafa54a37394"),
    "OA147": ("docs/decisions/OD_2026_09_29_owner_answers_147.json",
              "50e39a4deac7d4ada4710b2f641d717f1c4febd59366cbc04d8c66de6b4532b1"),
    "ICD": ("docs/interfaces/icp_neutralizer/ICP_NEUTRALIZER_ICD.md",
            "d346bcc5a5edc4a4dfa289010c8e48371477a0f3548a5e9dcf8886b6f55dbe77"),
    "LEDGERS": ("docs/ledgers/LEDGERS.md", "aa6d0c964e1c25fc20f7ac513b2f97e0cc6cad38fd5546f220e5d9e72d23c631"),
    "A938": ("docs/decisions/OD_2026_10_08_A9_38_ARCHITECTURE_FROZEN_DESIGN_CLOSURE_PROGRAMME.md", None),
}

WORST_STATE = "ds2:ECSS_ST_HIGH:alt180:lat-73.0000:lst15:lon240:doy1"


class BuildError(RuntimeError):
    pass


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def src(key: str, pointer: str = "", note: str = "") -> dict:
    rel, digest = PIN[key]
    got = sha(ROOT / rel)
    if digest is not None and got != digest:
        raise BuildError(f"{rel}: sha256 {got} != pinned {digest}")
    d = {"path": rel, "sha256": got}
    if pointer:
        d["pointer"] = pointer
    if note:
        d["note"] = note
    return d


def load(key: str):
    rel, _ = PIN[key]
    src(key)
    return json.loads((ROOT / rel).read_bytes())


def r(x: float, n: int = 12) -> float:
    return float(f"{x:.{n}g}")


def m2_compressor() -> dict:
    rec = load("M2")
    state_max, state_min, worst = [], [], None
    for st in rec["states"]:
        if not st["required"]:
            continue
        vals = [k["P_compressor_el_W"] for k in st["air_dbf1"]["scenarios"] if k["P_compressor_el_W"] is not None]
        state_max.append(max(vals))
        state_min.append(min(vals))
        if st["state_id"] == WORST_STATE:
            worst = max(vals)
    if worst is None:
        raise BuildError("worst state missing from the M2 record")
    return {"median_state_max": statistics.median(state_max), "global_max": max(state_max),
            "global_min": min(state_min), "worst_state_max": worst}


def coils():
    h = load("H21")
    cases = h["coil_design"]["cases"]
    names = [c["name"] for c in cases]
    if names[:3] != ["RP-1 f_NI=1", "RP-1 f_NI=2", "RP-1 worst-case assumptions"]:
        raise BuildError(f"H2-1 coil cases changed: {names[:3]}")
    def pc(i, coil, key):
        return cases[i]["coils"][coil]["chosen"][key]
    return {
        "B_sized_G": cases[1]["B_gap_G"], "B_cap_G": cases[2]["B_gap_G"],
        "hot_fni2": {c: pc(1, c, "P_kulgrid_538C_W") for c in ("inner", "outer")},
        "cold_fni1": {c: pc(0, c, "P20_W") for c in ("inner", "outer")},
        "cap_hot": {c: pc(2, c, "P_kulgrid_538C_W") for c in ("inner", "outer")},
    }


def term(id_, quantity, kind, value, units, low, high, evidence_class, level, closure_class, sources, rationale,
         flags=()):
    if kind not in ("load", "efficiency", "operating"):
        raise BuildError(id_)
    if not (low <= value <= high) and kind != "operating":
        raise BuildError(f"{id_}: value outside its uncertainty bounds")
    return {"id": id_, "quantity": quantity, "kind": kind, "value": r(value), "units": units, "low": r(low),
            "high": r(high), "evidence_class": evidence_class, "evidence_level": level,
            "closure_class": closure_class, "sources": sources, "rationale": rationale, "flags": list(flags)}


def build_inputs() -> dict:
    cp = m2_compressor()
    co = coils()
    dbf = load("DBF1")
    items = {it["id"]: it for it in dbf["items"]}
    pd_band = items["DBF1-H1-06"]["value"]
    bz_band = items["DBF1-BZ-02"]["value"]
    if pd_band != [650.0, 1350.0] or bz_band[1] != 268.6:
        raise BuildError("DBF-1 bands changed")
    k = (bz_band[1] / co["B_sized_G"]) ** 2
    ec = load("EC")
    moog = next(e for e in ec["components"]["flow_control"]["entries"] if e["id"] == "FC-MOOG-SPEC")["value"]
    alpha = 0.00393  # NBS Handbook 100 annealed copper 20 degC temperature coefficient (H2-1 copper model source)
    r_hot = moog["R_coil_ohm"] + moog["R_tolerance_ohm"]
    coil_hot = (moog["I_max_sustained_mA"] * 1e-3) ** 2 * r_hot * (1 + alpha * (100.0 - 20.0)) / (
        1 + alpha * (moog["R_at_C"] - 20.0))
    coil_min = (moog["I_min_opening_mA"] * 1e-3) ** 2 * (moog["R_coil_ohm"] - moog["R_tolerance_ohm"])
    hk_bus_nominal = None  # computed in Rust (thermal residual)

    T = []
    # ---------------------------------------------------------------------------------------------- operating
    T.append(term("PD-LOW", "Hall discharge load-plane power at the 12 mN point (V_d x I_d)", "operating", pd_band[0],
                  "W", pd_band[0], pd_band[0], "owner-allocation", "OWNER_DECISION", "DESIGN_ALLOCATION_NOT_PREDICTED",
                  [src("DBF1", "/items (DBF1-H1-06)")],
                  "lower end of the DBF-1 discharge-power band; Hall discharge power at a thrust point comes from the "
                  "converged Hall envelope (P2, HALL_NUMERICS_NOT_CONVERGED); until then the registered allocation is "
                  "used and labelled", ["DESIGN_ALLOCATION_NOT_PREDICTED"]))
    T.append(term("PD-HIGH", "Hall discharge load-plane power at the 25 mN point (band upper end)", "operating",
                  pd_band[1], "W", pd_band[1], pd_band[1], "owner-allocation", "OWNER_DECISION",
                  "DESIGN_ALLOCATION_NOT_PREDICTED", [src("DBF1", "/items (DBF1-H1-06)")],
                  "upper end of the DBF-1 discharge-power band (H2-1 sizing band; its upper end was set equal to the "
                  "A5 bus allocation, H2_1 sec. 2); evaluated as registered, the ledger shows what fits",
                  ["DESIGN_ALLOCATION_NOT_PREDICTED"]))
    T.append(term("RF-PFWD", "ICP RF forward power at the generator / 50-ohm reference plane (reference value)",
                  "operating", 200.0, "W", 0.0, 500.0, "assumed", "7", "FROZEN_ENGINEERING_ASSUMPTION",
                  [src("DBF1", "/items (DBF1-RF-02)"), src("ICD", "annex TAK-04 (Takahashi 2024 p. 3: 13.56 MHz, "
                                                                  "generator 200 W, no reflection detected)")],
                  "reference forward power inside the frozen 0-500 W envelope (DBF1-RF-02), at the only published "
                  "operating point of the topology precedent (TAK-04, context only, never scaled to H-1); the "
                  "electron-current requirement (ICP-45 / I_e,cap, P4) sets the real value; no fixed Hall / ICP "
                  "split (A9.1 OQ-A902-03): the ledger reports the Hall discharge ceiling as a function of P_fwd",
                  ["OPERATING_VARIABLE", "UPDATE_FROM_P4_ICP45"]))
    # ---------------------------------------------------------------------------------------------- loads
    T.append(term("MAG-IN-REF", "inner coil terminal power at the B band upper end (268.6 G), hot", "load",
                  co["hot_fni2"]["inner"] * k, "W", co["cold_fni1"]["inner"], co["cap_hot"]["inner"],
                  "model-derived", "6", "MODEL_DERIVED",
                  [src("H21", "/coil_design/cases/1/coils/inner/chosen/P_kulgrid_538C_W"),
                   src("DBF1", "/items (DBF1-BZ-02)")],
                  f"H2-1 RP-1 lumped coil design at f_NI 2 sized for {co['B_sized_G']} G, Kulgrid conductor at its "
                  f"537.8 degC class temperature (hot bound), scaled by (268.6 / {co['B_sized_G']})^2 = {k:.6f} to the "
                  "DBF-1 peak-band upper end (P ~ NI^2 ~ B^2, linear circuit); low = RP-1 f_NI 1 copper 20 degC, "
                  "high = MC-1 capability case (403 G, worst-case assumptions)", ["FEMM_PENDING_P3"]))
    T.append(term("MAG-OUT-REF", "outer coil terminal power at the B band upper end (268.6 G), hot", "load",
                  co["hot_fni2"]["outer"] * k, "W", co["cold_fni1"]["outer"], co["cap_hot"]["outer"],
                  "model-derived", "6", "MODEL_DERIVED",
                  [src("H21", "/coil_design/cases/1/coils/outer/chosen/P_kulgrid_538C_W")],
                  "as MAG-IN-REF for the outer coil", ["FEMM_PENDING_P3"]))
    T.append(term("MAG-IN-CAP", "inner coil terminal power at the MC-1 capability (403 G), worst-case assumptions",
                  "load", co["cap_hot"]["inner"], "W", co["cold_fni1"]["inner"], co["cap_hot"]["inner"],
                  "model-derived", "6", "MODEL_DERIVED",
                  [src("H21", "/coil_design/cases/2/coils/inner/chosen/P_kulgrid_538C_W"),
                   src("DBF1", "/items (DBF1-BZ-05)")],
                  "H2-1 RP-1 worst-case-assumptions coil case at the 403 G MC-1 capability, Kulgrid hot: the bounding "
                  "magnet load used at the worst admitted state", ["FEMM_PENDING_P3"]))
    T.append(term("MAG-OUT-CAP", "outer coil terminal power at the MC-1 capability (403 G), worst-case assumptions",
                  "load", co["cap_hot"]["outer"], "W", co["cold_fni1"]["outer"], co["cap_hot"]["outer"],
                  "model-derived", "6", "MODEL_DERIVED",
                  [src("H21", "/coil_design/cases/2/coils/outer/chosen/P_kulgrid_538C_W")],
                  "as MAG-IN-CAP for the outer coil", ["FEMM_PENDING_P3"]))
    T.append(term("MAG-TRIM", "trim coil terminal power", "load", 0.0, "W", 0.0, 0.0, "assumed", "7",
                  "FROZEN_ENGINEERING_ASSUMPTION",
                  [src("H21", "/magnetic_topology_preliminary_choice"), src("MP5", "/power/configurations/"
                                                                                   "hall_icp_neutralizer/slots/3")],
                  "baseline topology T2 (single inner + single outer coil); the trim coil is a provision with an "
                  "unsized NI (H2-1: requires FEMM) and is booked unpowered (0 W explicit, the slot rule); a "
                  "FEMM-sized trim current enters by revision", ["FEMM_PENDING_P3"]))
    T.append(term("RF-MATCH-ACT", "adjustable local match: tuning actuators and controller DC input", "load", 5.0, "W",
                  0.0, 10.0, "assumed", "7", "FROZEN_ENGINEERING_ASSUMPTION",
                  [src("DBF1", "/items (DBF1-RF-03)"), src("MP5", "/power/configurations/hall_icp_neutralizer/"
                                                                  "slots/5")],
                  "two motorised variable capacitors (TAK-04 practice: two variable capacitors) plus their controller, "
                  "steady average; no sourced value in the repository (verify at the P2 matching design); 0 W only "
                  "for a fixed passive match", ["VERIFY", "UPDATE_FROM_P2_IMPEDANCE_MAP"]))
    T.append(term("ICP-BIAS", "collector / bias supply output (V_bias x I_bias)", "load", 10.0, "W", 0.0, 20.0,
                  "assumed", "7", "FROZEN_ENGINEERING_ASSUMPTION",
                  [src("ICD", "ICP-22 (V_d = V_anode - V_electron-source-reference); annex TAK-10 (V_K = -100 V)"),
                   src("DBF1", "/items (DBF1-ICP-04)")],
                  "V_bias,max 100 V (the only published collector potential, TAK-10) x I_bias,max 0.1 A: the Hall "
                  "discharge current closes through the discharge supply between anode and collector (ICP-22), so "
                  "its power is inside V_d x I_d; the bias supply carries the collector-reference control current "
                  "only (assumed); if the validated P1 circuit routes part of I_d through it, P_bias = V_bias x "
                  "I_route enters by revision", ["VERIFY", "UPDATE_FROM_P1_IT_18"]))
    T.append(term("VALVE-COIL", "proportional / isolation valve coil power per energised valve (hot)", "load",
                  coil_hot, "W", coil_min, coil_hot, "inferred", "3", "SOURCED_ANALOG",
                  [src("EC", "/components/flow_control/entries/0 (FC-MOOG-SPEC: 74.5 +/- 2 ohm at 21 degC, "
                                  "140 mA max sustained, 75 mA min opening, T_op -34..100 degC)")],
                  f"Moog PFCV 51E339 coil I^2 R at 140 mA, R = 76.5 ohm (tolerance high) raised to 100 degC with the "
                  f"NBS annealed-copper coefficient {alpha} /K (coil material not stated by Moog: verify) = "
                  f"{coil_hot:.4f} W; low = 75 mA at 72.5 ohm cold. The atmospheric metering valve and the isolation "
                  "valves are taken as PFCV-class coils (no repository data for them)", ["VERIFY_COIL_MATERIAL"]))
    T.append(term("HK-LOAD", "propulsion controller, PPU control, FDIR, sensors, TM/TC interface and quiescent draw",
                  "load", 30.0, "W", 12.0, 30.0, "assumed", "5", "SOURCED_ANALOG",
                  [src("H24", "/external_values/S-OSUGA05/rows/auxiliary (30 W: -15 V 0.5 A + 15 V 1.5 A, 'supplies "
                                "internal signal circuit')"),
                   src("EC", "/components/housekeeping/entries/0 (repository ppu.py controller 8 W + sensors 4 W, "
                             "unsourced)")],
                  "the auxiliary (internal signal circuit) supply rating of a flight-class Hall PPU (Osuga 2005 "
                  "Table 1) taken as the controls / FDIR / telemetry load incl. idle-supply quiescent draw "
                  "(conservative: a rating, not a measured consumption); low = repository code values 12 W",
                  ["RATING_USED_AS_LOAD"]))
    T.append(term("CP-NOM", "compressor motor-drive electrical input, nominal (median over required states of the "
                            "per-state maximum over admitted in-domain surface scenarios)", "load",
                  cp["median_state_max"], "W", cp["median_state_max"], cp["median_state_max"], "model-derived", "6",
                  "MODEL_DERIVED", [src("M2", "/states/*/air_dbf1/scenarios/*/P_compressor_el_W")],
                  "DBF-1 compressor T6-A1-U2-D0-Ti6Al4V-H0.5 through the F3/F4 DragCompressor model (P_el = (P_gas + "
                  "P_bear) / eta_motor + P_ctrl) with code-default coefficients (PARAMETRIC_SENSITIVITY, T-1 / T-2 "
                  "open); no sourced bound exists, so the ledger reports the compressor headroom instead",
                  ["UPDATE_FROM_DCR_001", "CODE_DEFAULT_COEFFICIENTS"]))
    T.append(term("CP-WORST", "compressor motor-drive electrical input, maximum over every required state and "
                              "admitted in-domain surface scenario (at the worst admitted state)", "load",
                  cp["worst_state_max"], "W", cp["worst_state_max"], cp["worst_state_max"], "model-derived", "6",
                  "MODEL_DERIVED", [src("M2", f"/states ({WORST_STATE}) scenario cll_a0.5"),
                                    src("DBF1", "/items (DBF1-IN-08)")],
                  f"as CP-NOM; the global maximum {cp['global_max']:.6f} W is reached at {WORST_STATE} (also the "
                  "maximum-T_required state)", ["UPDATE_FROM_DCR_001", "CODE_DEFAULT_COEFFICIENTS"]))
    if abs(cp["global_max"] - cp["worst_state_max"]) > 0:
        raise BuildError("worst compressor state is not the worst T_required state")
    # ---------------------------------------------------------------------------------------------- efficiencies
    T.append(term("ETA-FE", "front end: spacecraft DC bus -> regulated 100 V internal propulsion bus", "efficiency",
                  0.95, "-", 0.92, 0.97, "assumed", "7", "FROZEN_ENGINEERING_ASSUMPTION",
                  [src("OA147", "/answers (row 111)"), src("MP5", "/power/internal_bus_V")],
                  "row 111: regulated 100 V internal bus, spacecraft-input front end configurable until the spacecraft "
                  "bus is specified; one regulated DC-DC stage; no repository source (verify): bracketed by the "
                  "single-stage analogs (Osuga 2005 100 V-bus anode supply >= 0.92 spec; Rhodes 2024 measured "
                  "0.88-0.91). If the spacecraft supplies a regulated 100 V bus the stage is direct (1.0)",
                  ["VERIFY", "SPACECRAFT_ICD_DEPENDENT"]))
    T.append(term("ETA-HD", "Hall discharge supply (100 V internal bus -> V_d at the anode terminals)", "efficiency",
                  0.90, "-", 0.86, 0.92, "digitized", "3", "SOURCED_ANALOG",
                  [src("EC", "/components/hall_discharge/entries/1 (HD-RH24-250V-28Vin)"),
                   src("EC", "/components/hall_discharge/entries/4 (HD-RH24-400V-28Vin)"),
                   src("H24", "/converter_efficiency_parameters/0 (H24-05 0.8583-0.915)"),
                   src("H24", "/converter_efficiency_parameters/1 (H24-06 Osuga 2005 100 V bus 0.92 spec)")],
                  "NASA SSEP sub-kW LCC breadboard measured 0.8805-0.9063 at 600-1000 W out (28 V in, 250 / 400 V "
                  "out); a 100 V-input stage has a smaller step-up ratio (inferred: not worse); the 100 V-bus flight "
                  "specification analog is 0.92; low = the H24-05 lower end", ["UPDATE_FROM_ROW_113_BREADBOARD"]))
    T.append(term("ETA-MAG", "per-coil magnet supply (current-controlled, isolated)", "efficiency", 0.60, "-", 0.60,
                  0.85, "assumed", "5", "SOURCED_ANALOG",
                  [src("H24", "/converter_efficiency_parameters/4 (H24-09 Osuga 2005 Table 1 magnet 0.60)")],
                  "minimum-efficiency specification of a flight Hall PPU magnet supply (Osuga 2005 Table 1, 5 W "
                  "class, two-stage isolation + buck); applied as the conservative value", []))
    T.append(term("ETA-RFGEN", "13.56 MHz RF generator DC input -> forward RF power", "efficiency", 0.70, "-", 0.60,
                  0.92, "inferred", "6", "SOURCED_ANALOG",
                  [src("EC", "/components/rf_source/entries/0 (RF-NEWORBIT25 0.92, 1-5 MHz, measured nominal)"),
                   src("EC", "/components/rf_source/entries/1 (RF-VOLKMAR18 0.60-0.70 DC -> RF at the coil incl. "
                             "cables, inferred)"),
                   src("H24", "/converter_efficiency_parameters/9 (H24-14 0.60-0.92)")],
                  "the two repository analogs span 0.60-0.92 at 1-5 MHz; 13.56 MHz is above both (switching losses "
                  "grow with frequency, inferred), so the reference is the upper end of the conservative analog "
                  "(Volkmar 0.70); a measured FLIGHT_REPRESENTATIVE_DC_RF_SOURCE (A9.3 OQ-RFQ-06) replaces it",
                  ["UPDATE_FROM_RFQ_06"]))
    T.append(term("ETA-BIAS", "collector / bias supply", "efficiency", 0.80, "-", 0.80, 0.90, "measured", "3",
                  "SOURCED_ANALOG", [src("H24", "/converter_efficiency_parameters/2 (H24-07 Osuga 2005 keeper "
                                                "conditioner > 0.80 measured)")],
                  "a 25 W-class floating current-regulated conditioner of a flight Hall PPU (lower bound 'more than "
                  "80 %'), the closest analog of a floating ~10 W bias supply", []))
    T.append(term("ETA-DRV", "valve-driver / actuator-driver supply", "efficiency", 0.80, "-", 0.80, 0.90, "assumed",
                  "5", "SOURCED_ANALOG",
                  [src("H24", "/converter_efficiency_parameters/5 (H24-10 Osuga 2005 mass-flow PC 0.80)")],
                  "minimum-efficiency specification of a flight Hall PPU mass-flow (valve) conditioner; also used "
                  "for the match actuators", []))
    T.append(term("ETA-HK", "auxiliary / housekeeping supply", "efficiency", 0.70, "-", 0.70, 0.85, "assumed", "5",
                  "SOURCED_ANALOG", [src("H24", "/converter_efficiency_parameters/6 (H24-11 Osuga 2005 auxiliary "
                                                "0.70)")],
                  "minimum-efficiency specification of a flight Hall PPU auxiliary supply", []))
    T.append(term("ETA-TH", "heater switch (resistive heaters switched from the internal bus)", "efficiency", 0.98,
                  "-", 0.95, 0.99, "assumed", "7", "FROZEN_ENGINEERING_ASSUMPTION",
                  [src("H24", "/converter_efficiency_parameters/8 (H24-13 TBD)")],
                  "solid-state switch conduction loss only (no conversion stage); no repository source (verify)",
                  ["VERIFY"]))
    T.append(term("ETA-CPD", "compressor drive supply path (drive fed from the internal bus)", "efficiency", 1.0,
                  "-", 1.0, 1.0, "model-derived", "6", "MODEL_DERIVED",
                  [src("EC", "/components/compressor/entries/0 (CP-REPO-MODEL: P_el includes eta_motor and "
                                  "P_ctrl)")],
                  "the compressor load is the motor-drive electrical input of the F3 model, whose eta_motor already "
                  "carries the drive conversion; only the harness applies (no double counting, LEDGERS A1)",
                  ["UPDATE_FROM_DCR_001"]))
    T.append(term("ETA-H-HV", "harness, 100 V-class power lines (discharge, RF generator, bias, compressor drive)",
                  "efficiency", 0.995, "-", 0.99, 0.999, "assumed", "7", "FROZEN_ENGINEERING_ASSUMPTION",
                  [src("LEDGERS", "sec. 3.4 A2 (harness loss inside the component efficiency); G15")],
                  "0.5 % I^2 R allowance for 100 V-class lines at a few amperes; harness lengths and gauges are not "
                  "designed (LEDGERS G15, verify at harness design)", ["VERIFY"]))
    T.append(term("ETA-H-LV", "harness, low-voltage lines (magnets, valves, actuators, housekeeping, heaters)",
                  "efficiency", 0.98, "-", 0.97, 0.995, "assumed", "7", "FROZEN_ENGINEERING_ASSUMPTION",
                  [src("LEDGERS", "sec. 3.4 A2; G15")],
                  "2 % I^2 R allowance for low-voltage, ampere-class lines (coil leads at 1.5-5 A, 4-12 V); verify at "
                  "harness design", ["VERIFY"]))
    T.append(term("ETA-RES", "reserved DC port (unused, 0 W)", "efficiency", 1.0, "-", 1.0, 1.0, "assumed", "7",
                  "FROZEN_ENGINEERING_ASSUMPTION", [src("MP5", "/power/configurations/hall_icp_neutralizer/"
                                                               "slots/12")],
                  "declared unused (0 W explicit, row 110); a 0 W slot draws exactly 0 W whatever its efficiency", []))

    def L(*terms, div=()):
        return {"num": [[t, n] for t, n in terms], "div": list(div)}

    common_air = {
        "flow_control_atmospheric": L(("VALVE-COIL", 2)),
        "flow_control_xe": L(),
        "thermal_control": {"rule": "controls_thermal_residual"},
        "housekeeping_controls": L(("HK-LOAD", 1)),
    }
    icp = {
        "icp_rf_source": L(("RF-PFWD", 1), div=["ETA-RFGEN"]),
        "icp_matching_network": L(("RF-MATCH-ACT", 1)),
        "icp_collector_bias": L(("ICP-BIAS", 1)),
    }
    mag_ref = {"hall_magnet_inner": L(("MAG-IN-REF", 1)), "hall_magnet_outer": L(("MAG-OUT-REF", 1)),
               "hall_magnet_trim": L(("MAG-TRIM", 1))}
    mag_cap = {"hall_magnet_inner": L(("MAG-IN-CAP", 1)), "hall_magnet_outer": L(("MAG-OUT-CAP", 1)),
               "hall_magnet_trim": L(("MAG-TRIM", 1))}
    effs = {
        "hall_discharge": ["ETA-HD", "ETA-H-HV"],
        "hall_magnet_inner": ["ETA-MAG", "ETA-H-LV"], "hall_magnet_outer": ["ETA-MAG", "ETA-H-LV"],
        "hall_magnet_trim": ["ETA-MAG", "ETA-H-LV"],
        "icp_rf_source": ["ETA-H-HV"], "icp_matching_network": ["ETA-DRV", "ETA-H-LV"],
        "icp_collector_bias": ["ETA-BIAS", "ETA-H-HV"],
        "flow_control_atmospheric": ["ETA-DRV", "ETA-H-LV"], "flow_control_xe": ["ETA-DRV", "ETA-H-LV"],
        "compressor": ["ETA-CPD", "ETA-H-HV"], "thermal_control": ["ETA-TH", "ETA-H-LV"],
        "housekeeping_controls": ["ETA-HK", "ETA-H-LV"], "reserved_dc_port": ["ETA-RES"],
    }
    points = [
        {"id": "P-NOM", "name": "nominal reference operating point (AIR_PRIMARY; discharge at the design allocation)",
         "mode": "AIR_PRIMARY", "state": "envelope (compressor at the median state)", "thrust_label": "reference",
         "hall_discharge": {"rule": "close_design_allocation"},
         "loads": {**mag_ref, **icp, **common_air, "compressor": L(("CP-NOM", 1)), "reserved_dc_port": L()}},
        {"id": "P-12", "name": "12 mN point (AIR_PRIMARY; discharge at the DBF-1 band lower end)",
         "mode": "AIR_PRIMARY", "state": "envelope (compressor at the median state)", "thrust_label": "12 mN",
         "hall_discharge": {"rule": "fixed", "load": L(("PD-LOW", 1))},
         "loads": {**mag_ref, **icp, **common_air, "compressor": L(("CP-NOM", 1)), "reserved_dc_port": L()}},
        {"id": "P-25", "name": "25 mN point (AIR_PRIMARY; discharge at the DBF-1 band upper end)",
         "mode": "AIR_PRIMARY", "state": "envelope (compressor at its maximum)", "thrust_label": "25 mN",
         "hall_discharge": {"rule": "fixed", "load": L(("PD-HIGH", 1))},
         "loads": {**mag_ref, **icp, **common_air, "compressor": L(("CP-WORST", 1)), "reserved_dc_port": L()}},
        {"id": "P-WORST", "name": "worst admitted atmospheric state (AIR_PRIMARY; T_required 54.5 mN > 25 mN: "
                                  "propulsion at its 25 mN capability; magnets at the MC-1 capability)",
         "mode": "AIR_PRIMARY", "state": WORST_STATE, "thrust_label": "25 mN capability",
         "hall_discharge": {"rule": "fixed", "load": L(("PD-HIGH", 1))},
         "loads": {**mag_cap, **icp, **common_air, "compressor": L(("CP-WORST", 1)), "reserved_dc_port": L()}},
        {"id": "P-XE", "name": "Xe contingency point (XE_CONTINGENCY; compressor and atmospheric path off; discharge "
                               "at the DBF-1 band lower end)",
         "mode": "XE_CONTINGENCY", "state": "any (no atmospheric dependence)", "thrust_label": "Xe contingency",
         "hall_discharge": {"rule": "fixed", "load": L(("PD-LOW", 1))},
         "loads": {**mag_ref, **icp, "flow_control_atmospheric": L(), "flow_control_xe": L(("VALVE-COIL", 3)),
                   "thermal_control": {"rule": "controls_thermal_residual"},
                   "housekeeping_controls": L(("HK-LOAD", 1)), "compressor": L(), "reserved_dc_port": L()}},
    ]
    del hk_bus_nominal
    return {
        "schema": "abep_power_closure_inputs_v1",
        "id": "power_closure_inputs_v1",
        "item": "A9.38 P6 power closure",
        "date": "2026-10-08",
        "boundary": "bus_power_boundary_a9_v2",
        "configuration": "hall_icp_neutralizer",
        "rules": [
            "every installed slot carries a load and an efficiency with an evidence class; no TBD (A9.38 P6)",
            "slot efficiency = product of the converter term and the harness term (LEDGERS A1 / A2: converter and "
            "harness loss inside the component efficiency, never added on top); evidence class of the product = "
            "the weakest component class",
            "Hall discharge power is DESIGN_ALLOCATION_NOT_PREDICTED until the converged Hall envelope (P2) "
            "supplies it; the ledger then reports the discharge ceiling P_d,max that fits 1,350 W and 1,500 W",
            "thermal_control = the row-114 50 W controls / thermal allowance minus the housekeeping bus draw "
            "(owner-allocation residual) until the P7 flight thermal case supplies heater power",
            "corners: conservative = loads at their high bound and efficiencies at their low bound, favourable = "
            "the reverse; operating variables (P_d, P_fwd) are not corner variables (RF trade line instead)",
            "valves: AIR_PRIMARY energises the atmospheric metering + isolation valve (2 coils), the Xe path is "
            "de-energised closed; XE_CONTINGENCY energises the Xe PFCV + two series isolation valves (row 90, 3 "
            "coils) and de-energises the atmospheric path and the compressor",
        ],
        "worst_state": WORST_STATE,
        "compressor_statistics_W": {k2: r(v) for k2, v in cp.items()},
        "magnet_scale_factor_B": r(k),
        "rf_trade_line_P_fwd_W": [0.0, 100.0, 200.0, 300.0, 400.0, 500.0],
        "terms": T,
        "slot_efficiencies": effs,
        "points": points,
        "generated_by": "docs/closure/power/build_power_closure_docs.py inputs",
        "governing_decision": src("A938"),
    }


# ------------------------------------------------------------------------------------------------------------ page
def fw(x, nd=1):
    return "n/a" if x is None else f"{x:,.{nd}f}"


def render_md(led: dict) -> str:
    L = []
    L.append("# Bus-power closure ledger v1 (A9.38 P6)\n")
    L.append("Record `power_ledger_v1.json` (Rust `abep_subsystems::power::closure_v1` + `abep_assess::power_closure`, "
             "bin `abep-assess-power-closure`; this page restates it). Boundary `bus_power_boundary_a9_v2`, configuration `hall_icp_neutralizer`, "
             "inputs `power_closure_inputs_v1.json` (sha256 `" + led["inputs"]["sha256"][:12] + "...`).\n")
    L.append("Every installed slot carries a load and an efficiency with an evidence class: **0 TBD terms** (the "
             f"official A9-02 ledger has {led['official_ledger_tbd']['official']} and the M2 ledger "
             f"{led['official_ledger_tbd']['with_compressor']}). The Hall discharge power is "
             "**DESIGN_ALLOCATION_NOT_PREDICTED** at every point (no converged Hall envelope yet, "
             "HALL_NUMERICS_NOT_CONVERGED).\n")
    L.append("## Points\n")
    L.append("| point | mode | P_d [W] (basis) | P_bus non-discharge [W] | P_bus [W] | margin to 1,350 W | margin to "
             "1,500 W | P_d,max @1,350 W | P_d,max @1,500 W |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for p in led["points"]:
        L.append(f"| {p['id']} | {p['mode']} | {fw(p['P_d_W'])} ({p['P_d_basis']}) | {fw(p['P_bus_non_discharge_W'])} | "
                 f"{fw(p['P_bus_W'])} | {fw(p['margin_to_design_allocation_W'])} | {fw(p['margin_to_rfp_W'])} | "
                 f"{fw(p['P_d_max_W']['design_allocation_1350'])} | {fw(p['P_d_max_W']['rfp_1500_supremum'])} |")
    L.append("")
    L.append("Margins are allocation / requirement differences on a design ledger, not verified margins; the 1,500 W "
             "comparison is strict (<), so P_d,max @1,500 W is a supremum. Negative margin = the registered discharge "
             "allocation does not fit at that point.\n")
    L.append("## Uncertainty corners (non-discharge loads)\n")
    L.append("| point | P_bus non-discharge conservative / reference / favourable [W] | P_d,max @1,350 W conservative / "
             "favourable | P_d,max @1,500 W conservative / favourable |")
    L.append("|---|---|---|---|")
    for p in led["points"]:
        c, f = p["corners"]["conservative"], p["corners"]["favourable"]
        L.append(f"| {p['id']} | {fw(c['P_bus_non_discharge_W'])} / {fw(p['P_bus_non_discharge_W'])} / "
                 f"{fw(f['P_bus_non_discharge_W'])} | {fw(c['P_d_max_W']['design_allocation_1350'])} / "
                 f"{fw(f['P_d_max_W']['design_allocation_1350'])} | {fw(c['P_d_max_W']['rfp_1500_supremum'])} / "
                 f"{fw(f['P_d_max_W']['rfp_1500_supremum'])} |")
    L.append("")
    L.append("## Slot ledger per point (P_bus at the spacecraft DC boundary, W)\n")
    slots = [it["slot"] for it in led["points"][0]["ledger"]["items"] if it["state"] != "NOT_INSTALLED"]
    L.append("| slot | " + " | ".join(p["id"] for p in led["points"]) + " | load / efficiency terms |")
    L.append("|---|" + "---|" * len(led["points"]) + "---|")
    for s in slots:
        row = []
        for p in led["points"]:
            it = next(i for i in p["ledger"]["items"] if i["slot"] == s)
            row.append(fw(it["P_bus_W"]))
        terms = led["points"][0]["slot_terms"][s]
        L.append(f"| {s} | " + " | ".join(row) + f" | {terms} |")
    L.append("| **total** | " + " | ".join(f"**{fw(p['P_bus_W'])}**" for p in led["points"]) + " | |")
    L.append("")
    L.append("## Losses inside P_bus (W)\n")
    L.append("| point | conversion (PPU supplies) | harness | front end | RF generator (DC -> forward RF) |")
    L.append("|---|---|---|---|---|")
    for p in led["points"]:
        lo = p["losses_W"]
        L.append(f"| {p['id']} | {fw(lo['conversion'])} | {fw(lo['harness'])} | {fw(lo['front_end'])} | "
                 f"{fw(lo['rf_generator'])} |")
    L.append("")
    L.append("## Owner-allocation checks (admitted `allocation_checks` / `icp_power_allocation_check`)\n")
    L.append("| point | design 1,350 W | common 300 W (P_bus) | controls / thermal 50 W | P_ICP vs available |")
    L.append("|---|---|---|---|---|")
    for p in led["points"]:
        a, i = p["allocation_checks"], p["icp_power_allocation_check"]
        L.append(f"| {p['id']} | {a['design_allocation']['verdict']} | {a['common_allocation']['verdict']} "
                 f"({fw(a['common_allocation']['P_bus_W'])}) | {a['controls_thermal_allowance']['verdict']} "
                 f"({fw(a['controls_thermal_allowance']['P_bus_W'])}) | {i['verdict']} ({fw(i['P_ICP_W'])} vs "
                 f"{fw(i['P_ICP_available_W'])}) |")
    L.append("")
    L.append("## RF trade line (P-12 loads; no fixed Hall / ICP split, A9.1 OQ-A902-03)\n")
    L.append("| P_fwd [W] | ICP group P_bus [W] | P_d,max @1,350 W | P_d,max @1,500 W |")
    L.append("|---|---|---|---|")
    for t in led["rf_trade_line"]:
        L.append(f"| {fw(t['P_fwd_W'], 0)} | {fw(t['P_bus_icp_W'])} | {fw(t['P_d_max_W']['design_allocation_1350'])} | "
                 f"{fw(t['P_d_max_W']['rfp_1500_supremum'])} |")
    L.append("")
    h = led["compressor_headroom"]
    L.append("## Compressor headroom (for DCR-001)\n")
    L.append(f"At P-NOM the compressor motor-drive input may grow to **{fw(h['inside_common_300W_W'])} W** inside the "
             f"300 W common allocation; each extra watt of compressor input lowers P_d,max by "
             f"{h['dPd_max_per_W_compressor']:.4f} W. DCR-001 replaces CP-NOM / CP-WORST (model-derived, code-default "
             "coefficients).\n")
    L.append("## Derived requirement on the Hall discharge (input to P2)\n")
    d = led["derived_hall_requirement"]
    L.append(d["text"] + "\n")
    L.append("| point | thrust | P_d,max (reference) [W] | required T / P_d [mN/kW] | conservative corner P_d,max "
             "[W] | required T / P_d [mN/kW] |")
    L.append("|---|---|---|---|---|---|")
    for e in d["rows"]:
        L.append(f"| {e['point']} | {e['thrust_mN']:g} mN @ {e['limit']} | {fw(e['P_d_max_W'])} | {e['T_over_P_d_mN_per_kW']:.1f} | "
                 f"{fw(e['P_d_max_conservative_W'])} | {e['T_over_P_d_conservative_mN_per_kW']:.1f} |")
    L.append("")
    L.append("## Closed terms\n")
    L.append("| term | quantity | value | bounds | evidence class | closure class | flags |")
    L.append("|---|---|---|---|---|---|---|")
    for t in led["terms"]:
        L.append(f"| {t['id']} | {t['quantity']} | {t['value']:.6g} {t['units']} | [{t['low']:.6g}, {t['high']:.6g}] | "
                 f"{t['evidence_class']} (level {t['evidence_level']}) | {t['closure_class']} | "
                 f"{', '.join(t['flags']) or '-'} |")
    L.append("")
    s = led["summary"]
    L.append("## Summary\n")
    L.append(f"- Ledger terms closed: {s['ledger_terms_closed']} (the {led['official_ledger_tbd']['official']} TBD "
             "entries of the official ledger - 12 slot loads and 12 slot efficiencies - plus the front-end efficiency "
             f"and the two harness terms that every slot efficiency carries); TBD remaining: {s['tbd_remaining']}.")
    L.append(f"- By closure class: {', '.join(f'{k} {v}' for k, v in s['ledger_terms_by_closure_class'].items())}.")
    L.append(f"- By evidence class (efficiencies by their converter term): "
             f"{', '.join(f'{k} {v}' for k, v in s['ledger_terms_by_evidence_class'].items())}.")
    L.append(f"- Register terms: {', '.join(f'{k} {v}' for k, v in s['register_terms_by_closure_class'].items())}.")
    L.append("")
    L.append("## Not\n")
    for n in led["not"]:
        L.append(f"- {n}")
    L.append("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["inputs", "md"])
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.what == "inputs":
        out = HERE / "power_closure_inputs_v1.json"
        data = (json.dumps(build_inputs(), indent=1, ensure_ascii=False) + "\n").encode()
    else:
        out = HERE / "power_ledger_v1.md"
        data = render_md(json.loads((HERE / "power_ledger_v1.json").read_bytes())).encode()
    if a.check:
        ok = out.exists() and out.read_bytes() == data
        print("OK" if ok else f"STALE: {out}")
        sys.exit(0 if ok else 1)
    out.write_bytes(data)
    print("wrote", out.relative_to(ROOT), hashlib.sha256(data).hexdigest())


if __name__ == "__main__":
    main()
