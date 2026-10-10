"""DBF-1.2: the approved successor of DBF-1.1 (DCR-DBF1-001, owner approval A9.41; build directions A9.42 / A9.43).

DBF-1.2 — RFP-CONFORMING PRELIMINARY DESIGN BASELINE / COMPLIANCE VERIFICATION ON EM/QM.

Content:
- the DBF-1.1 items are copied programmatically from the sha256-verified DBF-1.1 record, which is never edited. Each copy names its
  source. Items replaced by DCR-DBF1-001 (upstream design vector, intake, compressor, plenum, controller, F7 performance, reference
  host drag) are marked SUPERSEDED_BY_DCR-DBF1-001 and point to their DBF-1.2 successor;
- the DBF-1.2 items (intake, AIR design point, compressor, plenum / feed, mass, power, operating modes, host interface) read their
  values from the pinned DCR-001 v5 / v6 records, the P6 power ledger and the owner decisions. Nothing is retyped where a pinned
  source holds the value;
- power is recomputed here from the authoritative P6 ledger (A9.43): AIR 12 mN at the DBF1-H1-06 lower bound P_d = 650 W plus the
  DBF-1.2 compressor loads; Xe 25 mN discharge allocations from the P-XE non-discharge load, chain 0.850725 and the P6 RF trade line.

Usage: python3 docs/baseline/DBF-1.2/build_dbf1_2.py            write the DBF-1.2 files
       python3 docs/baseline/DBF-1.2/build_dbf1_2.py --check    regenerate in memory, compare byte for byte
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
REL_OUT = "docs/baseline/DBF-1.2"
STATUS = "DBF-1.2 — RFP-CONFORMING PRELIMINARY DESIGN BASELINE / COMPLIANCE VERIFICATION ON EM/QM"
SOURCE_CHECKPOINT = "6f4e3bb7025ec387143865fb737cbaaa841404fa"
DATE = "2026-10-10"
FILES = {"json": "dbf1_2_v1.json", "md": "DBF1_2_v1.md", "config": "dbf1_2_config_v1.json", "trace": "dbf1_2_requirement_trace_v1.json",
         "risks": "dbf1_2_risk_register_v1.json", "manifest": "dbf1_2_source_manifest_v1.json", "lock": "dbf1_2_lock_v1.json"}

PINS = {
    "dbf1_1_lock": ("docs/baseline/DBF-1.1/dbf1_1_lock_v1.json", "257e141ca252c3015b5bbd2fc953a1de688bc1606be36ebdf9fff8889307cfb8"),
    "dbf1_1": ("docs/baseline/DBF-1.1/dbf1_1_v1.json", "b8daa5bd5bb18b4fc92d6f65b0d93d0e70b33cd80d0f222cb9957ced3075c22b"),
    "dbf1_1_config": ("docs/baseline/DBF-1.1/dbf1_1_config_v1.json", "f16e07ba5b0c80e724dd53bb8d8a9b02298d8fb20ddac85a4f49ee799949d092"),
    "dbf1_lock": ("docs/baseline/DBF-1/dbf1_lock_v1.json", "517e0cf693712ec6d355c4b23791b9ae8626577fd338e3030563eb027e86b907"),
    "dcr_process": ("docs/baseline/DBF-1/DCR_PROCESS.md", "14f05a7b64968acf9b2a3bc53e5ff33bc83b4304ad284d58f35f27fcc5a04a91"),
    "dcr_register": ("docs/baseline/DBF-1/dcr_register_v5.json", "432bb04a981dac1e415ddd36a28e41d0b230edfa7f4cef34a2016a2d6d901368"),
    "dcr_approval": ("docs/baseline/DCR-001/dcr001_approval_v1.json", "b3d0c3074c4dee3228af98f417d8d005b71a835ce79df8190db1de70eff4ed29"),
    "a9_40": ("docs/decisions/OD_2026_10_10_A9_40_dbf_1_2_freeze_gates_air_operating_concept_host_drag.json", "d915ad0a57ebde0975d4ddba1412937a78798d39a475a7ad72ab9ef54d20078a"),
    "a9_41": ("docs/decisions/OD_2026_10_10_A9_41_dcr_dbf1_001_approval_mass_risk.json", "3482cd6e945a479233ed5374ebeeb74bdf87d61c8fb86967d0afe25c589d3c49"),
    "a9_42": ("docs/decisions/OD_2026_10_10_A9_42_build_and_freeze_dbf_1_2.json", "2928f44a66705708d75e6f56ad175536f41489e4c7437fd46f0e480415c65a24"),
    "a9_43": ("docs/decisions/OD_2026_10_10_A9_43_power_reconciliation_and_dbf_1_2_freeze.json", "79754cc5b7350c6e0ad82a055fa7ae5fefc7eb359860710fd5ae9da35a58312a"),
    "dcr001_v4": ("docs/baseline/DCR-001/preliminary/dcr001_pressure_domain_closure_v4.json", "3872fa1869e4dd280c7a095ae00193b356f2b62015a0ad35c9374983d74737b6"),
    "dcr001_v5": ("docs/baseline/DCR-001/preliminary/dcr001_mass_closure_v5.json", "97a69b6df496f6bce21ebfc21df4dd98f362d640993a4a559f78dff135150ef1"),
    "dcr001_v6": ("docs/baseline/DCR-001/preliminary/dcr001_system_mass_closure_v6.json", "8074c0b72b3b8f187a2a348f7f761481de7d8645e563e3e5ae93361695303ab7"),
    "p6_ledger": ("docs/closure/power/power_ledger_v1.json", "23e3366967f3d04d332564f95e6f4ddb3f4aa3b3d774cb6e09b5aa6a9138472a"),
    "mass_power_v5": ("docs/budgets/mass_power_a9_v5/mass_power_a9_v5.json", "3ff23429f5225a8a8363a784281b2f32b1df9ad69ec9934320306b080436b73a"),
    "rfp": ("docs/requirements/rfp_official/rfp_registration_v1.json", "c126be5eef7b9ec6340776ed035eeaa0ced1c4dd2ec585383f3d3a5977d174a0"),
    "rvm": ("docs/requirements/rvm_a9/rvm_a9_v1.json", "f91a00b40e24a66ceec8fd16dba3ad5ecb249ae186cc39bf717efe083223a5c4"),
    "xe_ledger": ("docs/budgets/xe_ledger_a9/xe_ledger_a9_v1.json", "37c32cda9fb04200f6e9041b0e790ca700e270866f29e7c10f8a298034ddacfd"),
    "states_196": ("docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/conservation_bounds_v1.json", "5146fe583343bf5de090a8baeecb812640754b7e579f0df69c78e54dd642689f"),
    "hall_diag": ("docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/hall_numerics_diagnosis_v1.json", "519a7063e6680e920e0b79bdebe2e10b767272cef78a7d5319d1d076f010997d"),
    "closure_board": ("docs/closure/closure_board_v1.json", "56bd9f12c4f613a131b4f12300770db509f88e964b7f8e5a6b04de9bb5e5be4b"),
    "p3_bz": ("docs/closure/P3_h1_magnetic_field_closure_v1.json", "7cafce78307e0376fa3aacbdddeb083a1b671ddc97040a22affe540006735631"),
    "icp_closure": ("docs/closure/icp/icp_closure_v1.json", "3ddf55039b4f682983cfd728ded3bec6bb6e7e1cb73551ccee32521815b1016c"),
    "materials": ("docs/closure/materials/materials_gates_v1.json", "f3b6e04507429db87b3f94a3a355bb6e87cb78d97ca9bd1f902a766ea667fee1"),
    "thermal": ("docs/closure/thermal/thermal_closure_v2.json", "06b26333b265a706e0c9bfcdbee1567fe800dbd19b3a05d9f4922ef85eb9dc4d"),
    "conclusion_v2": ("docs/closure/conclusion/ARCHITECTURE_CLOSURE_CONCLUSION_v2.md", "4ef4573e346eac88ed87610b569f1eedb9f7107a6ebc9ebe56a42ac2080babf9"),
}
FORBIDDEN_STATUS = ["fully RFP-qualified", "demonstrated compliant", "flight-qualified", "performance validated", "final flight design"]
RFP_P_BUS_W, DESIGN_ALLOC_W, XE_CEILING_W, MASS_LIMIT_KG = 1500.0, 1350.0, 1450.0, 40.0


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def read_pinned(key: str) -> bytes:
    rel, want = PINS[key]
    b = (ROOT / rel).read_bytes()
    if sha_bytes(b) != want:
        raise SystemExit(f"REFUSED: {rel} sha256 {sha_bytes(b)} != pinned {want}")
    return b


def js(key: str):
    return json.loads(read_pinned(key))


def src(key: str, pointer: str | None = None) -> dict:
    d = {"path": PINS[key][0], "sha256": PINS[key][1]}
    if pointer:
        d["pointer"] = pointer
    return d


def refuse(msg: str):
    raise SystemExit(f"REFUSED (factual inconsistency, A9.42 stop rule): {msg}")


def item(id_, group, name, value, units, sources, evidence_class, qtype, level, uncertainty, status, rationale, **extra):
    d = {"id": id_, "group": group, "name": name, "value": value, "units": units, "sources": sources,
         "evidence_class": evidence_class, "quantity_type": qtype, "evidence_level": level, "uncertainty": uncertainty,
         "status": status, "rationale": rationale}
    d.update(extra)
    return d


# ------------------------------------------------------------------------------------------------------------------- power
def power(p6, v5):
    pts = {p["id"]: p for p in p6["points"]}
    p12, pxe = pts["P-12"], pts["P-XE"]
    slots12 = {it["slot"]: it for it in p12["ledger"]["items"]}
    hd = slots12["hall_discharge"]
    if hd["P_W"] != 650.0 or p12["P_d_basis"].split(":")[0] != "PD-LOW":
        refuse("P6 P-12 discharge is not the PD-LOW 650 W allocation")
    k_d = hd["P_bus_W"] / hd["P_W"]                                   # bus W per W discharge (= 1 / 0.850725)
    eta_chain = p12["discharge_chain_eta"]
    if abs(eta_chain - 1 / k_d) > 1e-9 or abs(eta_chain - pxe["discharge_chain_eta"]) > 1e-12:
        refuse("P6 discharge-chain efficiency inconsistent between slot ledger and point records")
    comp = slots12["compressor"]
    k_c = comp["P_bus_W"] / comp["P_W"]                               # bus W per W at the compressor load plane
    nd_wo_comp = p12["P_bus_non_discharge_W"] - comp["P_bus_W"]
    if abs(sum(i["P_bus_W"] for i in p12["ledger"]["items"]) - p12["P_bus_W"]) > 1e-6:
        refuse("P6 P-12 slot sum != P_bus")
    c_est = v5["compressor"]["power_W"]["estimate"]
    c_allow = 77.0                                                    # owner-frozen allowance (A9.42 sec. 2; v5 computed 76.9 W)
    if c_allow < v5["compressor"]["power_W"]["allowance"]:
        refuse("frozen compressor allowance below the v5 computed allowance")
    P_D_AIR = 650.0                                                   # DBF1-H1-06 lower bound = P6 PD-LOW (A9.43 item 1)
    air = {}
    for case, cw in (("reference", c_est), ("conservative", c_allow)):
        pb = P_D_AIR * k_d + nd_wo_comp + cw * k_c
        air[case] = {"P_d_W": P_D_AIR, "compressor_load_W": cw, "P_bus_discharge_W": P_D_AIR * k_d, "P_bus_non_discharge_excl_compressor_W": nd_wo_comp,
                     "P_bus_compressor_W": cw * k_c, "P_bus_W": pb, "margin_to_1350_W": DESIGN_ALLOC_W - pb, "margin_to_1500_W": RFP_P_BUS_W - pb}
        if not (pb < DESIGN_ALLOC_W and pb < RFP_P_BUS_W):
            refuse(f"AIR {case} bus {pb:.1f} W not below 1350 / 1500 W")
    # P6 conservative non-discharge corner with the DBF-1.2 compressor allowance (sensitivity, carried as a power risk)
    nd_cons = p12["corners"]["conservative"]["P_bus_non_discharge_W"] - comp["P_bus_W"] + c_allow * k_c
    air_corner = {"P_bus_W": P_D_AIR * k_d + nd_cons, "basis": "P6 P-12 conservative non-discharge corner (all non-discharge loads at their conservative values) with the old compressor bus term replaced by the 77 W allowance (approximation: the corner's compressor term is taken at the reference bus conversion)"}
    # model-derived thrust at the 650 W point (NOT VALIDATED)
    md = 12e-3 / 26.8e3
    t_model = math.sqrt(2 * 0.27 * md * P_D_AIR)
    # Xe 25 mN discharge allocations (P6 P-XE + RF trade line)
    nd_xe = pxe["P_bus_non_discharge_W"]
    rft = {r["P_fwd_W"]: r for r in p6["rf_trade_line"]}
    d_rf_bus = rft[300.0]["P_bus_icp_W"] - rft[200.0]["P_bus_icp_W"]                 # +100 W forward power around the 200 W reference
    slot_rf = {it["slot"]: it for it in pxe["ledger"]["items"]}["icp_rf_source"]
    if abs(slot_rf["P_W"] * 0.7 - 200.0) > 1e-6 and abs(rft[200.0]["P_bus_icp_W"] - p12["P_bus_by_group_W"]["icp"]) > 1e-6:
        refuse("P6 reference RF point is not the 200 W forward-power row of the trade line")
    xe = {}
    for lim, lab in ((XE_CEILING_W, "1450W_design_ceiling_le"), (RFP_P_BUS_W, "1500W_rfp_supremum_lt")):
        xe[lab] = {"nominal_ICP_P_d_max_W": (lim - nd_xe) * eta_chain, "RF_plus_100W_P_d_max_W": (lim - nd_xe - d_rf_bus) * eta_chain}
    return dict(
        basis={"ledger": src("p6_ledger"), "discharge_chain_eta": eta_chain, "bus_per_W_discharge": k_d, "bus_per_W_compressor": k_c,
               "P12_non_discharge_W": p12["P_bus_non_discharge_W"], "P12_compressor_bus_W_replaced": comp["P_bus_W"],
               "PXE_non_discharge_W": nd_xe, "rf_plus_100W_bus_W": d_rf_bus,
               "superseded_dcr001_v4_terms": {"xe_non_discharge_W": 412.5176470588235, "chain_eta": 0.855, "rf_plus_100W_bus_W": 129.0},
               "superseded_dcr001_v5_air_P_d_W": {"reference_prediction": 12e-3 * 26.8e3 / (2 * 0.27), "conservative_prediction": 12e-3 * 22e3 / (2 * 0.22),
                                                   "status": "historical model predictions; not governing (A9.43 item 2)"}},
        air_12mN=air, air_12mN_p6_conservative_corner=air_corner,
        air_12mN_model_thrust_at_650W={"value_mN": t_model * 1e3, "label": "MODEL-DERIVED / NOT VALIDATED (T = sqrt(2 eta m_dot P_d), eta 0.27, m_dot 0.448 mg/s); never demonstrated thrust"},
        xe_25mN=xe,
        xe_25mN_statement=("Xe 25 mN is a design capability requirement. The Hall discharge-power allocation is <= %.0f W at the 1,450 W design "
                           "ceiling under the nominal ICP case and <= %.0f W under the +100 W RF sensitivity case. Performance is to be verified "
                           "on EM/QM hardware." % (xe["1450W_design_ceiling_le"]["nominal_ICP_P_d_max_W"], xe["1450W_design_ceiling_le"]["RF_plus_100W_P_d_max_W"])),
        xe_25mN_parametric={"P_d_W": 658.0, "label": "PARAMETRIC / NOT_VALIDATED (RP-1 Xe A7 runs; feasibility support only, never demonstration)", "source": src("hall_diag")},
        compressor_off_in_xe=True)


# -------------------------------------------------------------------------------------------------------------------- mass
def mass(v6):
    sub = v6["subtotals_new_mev_kg"]
    nonh = sum(sub.values())
    harness = 0.05 / 0.95 * nonh
    nominal = nonh + harness
    dry = 1.10 * nominal
    wet = dry + 2.0
    r = v6["rollup_new"]
    for k, v in (("nonharness_kg", nonh), ("harness_kg", harness), ("nominal_dry_kg", nominal), ("dry_10pct_kg", dry), ("wet_2kgXe_kg", wet)):
        if abs(r[k] - v) > 5e-4:
            refuse(f"v6 roll-up {k} {r[k]} != recomputed {v}")
    if not wet < MASS_LIMIT_KG:
        refuse("wet mass not below 40 kg")
    return dict(convention="mass_power_a9_v5 / A9.26: harness = 0.05/0.95 x non-harness; nominal = non-harness + harness; dry = 1.10 x nominal; wet = dry + 2 kg Xe (planning reference)",
                lines_mev_kg=sub, nonharness_kg=nonh, harness_kg=harness, nominal_dry_kg=nominal, system_margin_kg=dry - nominal, dry_10pct_kg=dry,
                xe_reference_kg=2.0, wet_kg=wet, numerical_headroom_to_40_kg=MASS_LIMIT_KG - wet, gap_to_39_4_target_kg=39.4 - wet,
                nominal_dry_target_34_gap_kg=34.0 - nominal,
                headroom_status="OPEN MASS RISK MR-DCR001-01: not usable design margin (A9.41)",
                bid_wording="Preliminary roll-up ≈39.95 kg wet (<40 kg); approximately 0.05 kg numerical headroom is carried as open mass risk MR-DCR001-01 and shall not be consumed as design margin.",
                ppu={"AL-07_governing_mev_kg": sub["AL-07 PPU"], "cbe_kg": v6["ppu"]["cbe_kg"], "status": "PRELIMINARY CBE / NOT MEASURED / REQUIRES EARLY CONFIRMATION",
                     "historical_floor": {"mev_kg": 6.0, "record": src("mass_power_v5", "/lines/hall_icp_neutralizer/6"), "status": "preserved history; superseded for the active DBF-1.2 baseline only (A9.41)"}},
                icp_mount_correction="ICP open-frame support / spacer counted once (AL-10, MQ-02); duplicate removed from AL-05 (v6)",
                compressor_booking={"compressor_governing_mev_kg": 7.767, "AL-02_line_mev_kg": sub["AL-02 compressor"], "AL-01_line_mev_kg": sub["AL-01 intake"],
                                    "note": "7.767 kg is the governing compressor-design mass (v5 machine). The AL-02 line of the approved v6 roll-up is 7.843 kg because the v6 intake-compressor integration books the shared joint, assembly mount feet and reinforcement in AL-02 and removes the bolted flange pair and duplicate mounts from AL-01 / AL-02 (net -0.284 kg on AL-01 + AL-02 = 12.112 kg); bookkeeping between lines, totals unchanged"})


# ------------------------------------------------------------------------------------------------------------------- build
def build():
    lock11 = js("dbf1_1_lock")
    for k, f in (("dbf1_1", "dbf1_1_v1.json"), ("dbf1_1_config", "dbf1_1_config_v1.json")):
        if lock11["files"][f] != PINS[k][1]:
            refuse(f"DBF-1.1 lock files.{f} != pinned")
    js("dbf1_lock")
    parent, pcfg = js("dbf1_1"), js("dbf1_1_config")
    appr, reg, a41, a40, a43 = js("dcr_approval"), js("dcr_register"), js("a9_41"), js("a9_40"), js("a9_43")
    v4, v5, v6, p6 = js("dcr001_v4"), js("dcr001_v5"), js("dcr001_v6"), js("p6_ledger")
    js("a9_42"); read_pinned("dcr_process")
    rfp, rvm, xel = js("rfp"), js("rvm"), js("xe_ledger")
    for k in ("states_196", "hall_diag", "closure_board", "p3_bz", "icp_closure", "materials", "thermal", "conclusion_v2", "mass_power_v5"):
        read_pinned(k)
    # --- DCR consistency
    if appr["dcr"] != "DCR-DBF1-001" or appr["approved_by"] != "owner" or appr["owner_record"]["sha256"] != PINS["a9_41"][1]:
        refuse("dcr001_approval_v1 does not name DCR-DBF1-001 approved by the owner under the pinned A9.41 record")
    ev = {e["path"]: e["sha256"] for e in appr["evidence"]}
    for k in ("dcr001_v4", "dcr001_v5", "dcr001_v6"):
        if ev.get(PINS[k][0]) != PINS[k][1]:
            refuse(f"approval evidence pin for {PINS[k][0]} != pinned")
    d001 = [d for d in reg["dcrs"] if d["id"] == "DCR-DBF1-001"]
    if len(d001) != 1 or d001[0]["status"] != "APPROVED_OWNER_WITH_MASS_RISK" or d001[0]["approval_record"]["sha256"] != PINS["dcr_approval"][1]:
        refuse("dcr_register_v5 DCR-DBF1-001 not APPROVED_OWNER_WITH_MASS_RISK with the pinned approval record")
    open_dcrs = [{"id": d["id"], "status": d["status"]} for d in reg["dcrs"] if not d["status"].startswith("APPROVED")]
    # --- engineering values from the pinned records
    sz = v5["sizing"]
    md_siz = v5["flows_mg_s"]["SIZING_AIR_12mN_design_basis"]
    md_22 = v5["flows_mg_s"]["AIR_12mN_22kms_sensitivity"]
    if abs(md_siz - 12e-3 / 26.8e3 * 1e6) > 1e-9:
        refuse("v5 sizing flow != 12 mN / 26.8 km/s")
    fd, comp = v5["feed_design"], v5["compressor"]
    rows, holw = comp["rows"], comp["holweck"]
    if len(rows) != 7 or abs(comp["rpm_both_shafts"] - 8602.97) > 0.5 or abs(v5["compressor"]["mev_kg"] - 7.767) > 1e-9:
        refuse("v5 compressor is not the approved 7-row, ~8,603 rpm, 7.767 kg design")
    if fd["outlet"]["n_holes"] != 186:
        refuse("v5 distributor is not 186 holes")
    p_set, band, vol = v5["plenum_setpoint_Pa"], v5["plenum_band_Pa"], v5["plenum_V_L"]
    p22 = v5["compressor"]["recheck"]["AIR_12mN_22kms_sensitivity"]["p_plenum_required_min_controllable_Pa"] / 0.95
    adm = []
    for r in rows:
        cls = ("ADMITTED_FREE_MOLECULAR" if r["p_out_Pa"] <= 0.1 * 1.0001 else
               "EM_VERIFICATION_RISK_CROSSES_0.1_Pa" if r["p_in_Pa"] < 0.1 else "EM_VERIFICATION_RISK_TRANSITIONAL")
        adm.append({"row": r["row"], "shaft": r["shaft"], "r_tip_m": r["r_tip_m"], "r_hub_m": r["r_hub_m"], "blade_height_mm": r["blade_height_mm"],
                    "rpm": r["rpm"], "u_tip_m_s": r["u_tip_m_s"], "u_rel_m_s": r["u_rel_m_s"], "p_in_Pa": r["p_in_Pa"], "p_out_Pa": r["p_out_Pa"],
                    "K": r["K"], "Kn_out": r["Kn_out"], "classification": cls})
    expected = ["ADMITTED_FREE_MOLECULAR"] * 5 + ["EM_VERIFICATION_RISK_CROSSES_0.1_Pa", "EM_VERIFICATION_RISK_TRANSITIONAL"]
    if [a["classification"] for a in adm] != expected:
        refuse(f"pressure-domain classification differs from the approved F1-F5 / F6 / B7 split: {[a['classification'] for a in adm]}")
    pw, ms = power(p6, v5), mass(v6)
    mr = a41["mass_risk"]
    if mr["id"] != "MR-DCR001-01":
        refuse("A9.41 mass risk id")
    # --- items
    v5s = lambda ptr: src("dcr001_v5", ptr)
    new_items = [
        item("DBF12-IN-01", "INTAKE", "intake physical aperture / collimator", {"aperture_m2": 0.70, "equivalent_diameter_m": math.sqrt(4 * 0.70 / math.pi), "collimator_L_over_D": 20.0,
             "retention_design": "S_eff = 2 C_back (2/3 retention)", "S_eff_inlet_m3_s": comp["S_eff_inlet_m3_s"]},
             "m2; m; -; m3/s", [src("a9_40"), v5s("/compressor/S_eff_inlet_m3_s"), src("dcr001_v6", "/subtotals_new_mev_kg")],
             "owner-fixed (A9.40: retain 0.70 m2) / model-derived retention", "owner-allocation", "OWNER_DECISION",
             "TPMC surface-scenario basis inherited (DBF1-IN-03); delivered flow verified on EM", "FROZEN",
             "A9.40 retains 0.70 m2; DCR-DBF1-001 approved (A9.41); supersedes DBF1-IN-02 (0.25 m2)", supersedes=["DBF1-IN-01", "DBF1-IN-02"]),
        item("DBF12-IN-02", "INTAKE", "delivered-flow regulation concept", "ACTIVE_COMPRESSOR_RETENTION_CONTROL_WITH_DENSITY_AWARE_ALTITUDE_SCHEDULING", "-",
             [src("a9_40"), src("a9_41")], "owner decision", "owner-allocation", "OWNER_DECISION",
             "control gains TBD at EM design", "FROZEN",
             "delivered flow is regulated by compressor speed / retention control and the metering valve; exposed frontal drag is NOT controlled by compressor speed (never 'variable frontal area')",
             supersedes=["DBF1-IN-07"]),
        item("DBF12-AIR-01", "AIR_DESIGN_POINT", "guaranteed AIR proposal sizing point",
             {"thrust_mN": 12.0, "v_eff_km_s": 26.8, "hall_feed_mg_s": md_siz, "icp_dedicated_flow_mg_s": 0.0, "P_d_W": 650.0,
              "window": "only inside the approved AIR density / altitude window (A9.40)"},
             "mN; km/s; mg/s; mg/s; W", [v5s("/sizing"), src("a9_43"), src("p6_ledger", "/points/1")],
             "owner decision / model-derived flow", "owner-allocation", "OWNER_DECISION",
             "26.8 km/s is the design / reference air-Hall basis (not validated); 12 mN at 650 W is a design point pending EM verification; model thrust at 650 W %.2f mN is MODEL-DERIVED / NOT VALIDATED" % pw["air_12mN_model_thrust_at_650W"]["value_mN"],
             "FROZEN_ASSUMPTION", "A9.40 / A9.41 / A9.43 item 1 (P_d = DBF1-H1-06 lower bound = P6 PD-LOW)"),
        item("DBF12-AIR-02", "AIR_DESIGN_POINT", "22 km/s sensitivity (carried, not guaranteed)", {"v_eff_km_s": 22.0, "hall_feed_mg_s": md_22, "plenum_setpoint_required_Pa": p22},
             "km/s; mg/s; Pa", [v5s("/compressor/recheck/AIR_12mN_22kms_sensitivity")], "model-derived", "model-derived", "6",
             "sensitivity / risk case (A9.40)", "FROZEN_ASSUMPTION", "carried as sensitivity; needs the ~6.1 Pa setpoint inside the Holweck Kn domain (6.8 Pa)"),
        item("DBF12-AIR-03", "AIR_DESIGN_POINT", "1.33 mg/s AIR capability point", "NOT_SUPPORTED_BY_DBF-1.2", "-",
             [v5s("/compressor/recheck/AIR_high_capability_1.33")], "model-derived", "model-derived", "6",
             "requires ~14.2 Pa plenum, above the 6.8 Pa Holweck Kn >= 0.5 domain", "FROZEN", "no 25 mN atmospheric operation is claimed"),
        item("DBF12-CMP-01", "COMPRESSOR", "integrated contra-rotating molecular compressor",
             {"blade_rows": 7, "rear_section": "shared Holweck (outer skin of the shaft-A drum, stationary grooved Al band)", "shafts": "two coaxial counter-rotating",
              "rpm": comp["rpm_both_shafts"], "tip_speed_m_s": rows[0]["u_tip_m_s"], "front_section": "full aperture (tip radius 0.333 m)",
              "separate_finishing_pump": False, "governing_mev_kg": 7.767, "power_allowance_W": 77.0, "power_estimate_W": comp["power_W"]["estimate"]},
             "-; rpm; m/s; kg; W", [v5s("/compressor"), src("a9_41")], "model-derived (repository row / drag model; coefficients T-1, uncited)", "model-derived", "6",
             "component masses partly assumed; actual mass and power verified on EM", "FROZEN_ASSUMPTION",
             "DCR-DBF1-001 approved (A9.41); supersedes DBF1-IN-05", supersedes=["DBF1-IN-05"]),
        item("DBF12-CMP-02", "COMPRESSOR", "pressure-domain classification", {"rows": adm, "holweck": {
             "p_in_Pa": holw["p_in_Pa"], "p_out_Pa": holw["p_out_required_Pa"], "Kn_out": holw["Kn_out"], "groove_depth_mm": holw["groove_depth_mm"],
             "classification": "PRELIMINARY_MOLECULAR_DRAG_DESIGN_WITHIN_Kn_CRITERION_COEFFICIENTS_REQUIRE_VERIFICATION"}},
             "Pa; -", [v5s("/compressor/rows"), v5s("/compressor/holweck")], "model-derived", "model-derived", "6",
             "F6 / B7 are NOT admitted (transitional derating assumed); never upgraded to validated", "FROZEN_ASSUMPTION",
             "F1-F5 inside the admitted 0.1 Pa free-molecular domain; F6 crosses 0.1 Pa and B7 is transitional: EM-verification risks"),
        item("DBF12-FEED-01", "PLENUM_FEED", "plenum setpoint / band / volume", {"setpoint_Pa": p_set, "band_Pa": band, "volume_L": vol, "sensitivity_setpoint_22kms_Pa": p22},
             "Pa; Pa; L; Pa", [v5s("/plenum_setpoint_Pa"), v5s("/plenum_band_Pa"), v5s("/plenum_V_L")], "model-derived (molecular conductances)", "model-derived", "6",
             "conductances molecular lower bounds; controllability verified on EM", "FROZEN_ASSUMPTION",
             "co-designed plenum -> isolation valve -> metering valve -> manifold -> 2/4/8 branch tree -> distributor -> H1; supersedes DBF1-IN-06",
             supersedes=["DBF1-IN-06"]),
        item("DBF12-FEED-02", "PLENUM_FEED", "H1 distributor / manifold concept", {"outlet_holes": fd["outlet"]["n_holes"], "hole_d_mm": fd["outlet"]["d_mm"],
             "open_fraction": fd["outlet"]["open_fraction_of_channel_base"], "ring_mm": [fd["ring"]["radial_mm"], fd["ring"]["axial_mm"]], "inlets": fd["ring"]["n_inlets"],
             "uniformity_requirement": "+/-5 % azimuthal flow (preliminary H1 interface / design requirement, not demonstrated)"},
             "-; mm; -; mm; -", [v5s("/feed_design")], "model-derived / assumed requirement", "model-derived", "6",
             "uniformity rule and 50 % open-area cap are assumptions", "FROZEN_ASSUMPTION", "high-conductance annular distributor compatible with the frozen H1 channel"),
        item("DBF12-MASS-05", "MASS", "preliminary system mass roll-up (A9.41)", {k: ms[k] for k in ("nonharness_kg", "harness_kg", "nominal_dry_kg", "dry_10pct_kg", "xe_reference_kg", "wet_kg")},
             "kg", [src("dcr001_v6", "/rollup_new"), src("a9_41")], "preliminary component BOM (mixed measured / model-derived / assumed)", "model-derived", "6",
             "MR-DCR001-01 OPEN: the ~0.05 kg numerical headroom to 40 kg is NOT design margin", "FROZEN_ASSUMPTION", ms["bid_wording"]),
        item("DBF12-PWR-05", "POWER", "AIR 12 mN bus power (P6 ledger + DBF-1.2 compressor)", {k: v["P_bus_W"] for k, v in pw["air_12mN"].items()},
             "W", [src("p6_ledger", "/points/1"), v5s("/compressor/power_W"), src("a9_43")], "design ledger (allocation-based)", "owner-allocation", "OWNER_DECISION",
             "P_d is a design allocation (DESIGN_ALLOCATION_NOT_PREDICTED); compressor estimate / 77 W allowance", "FROZEN",
             "A9.43: 650 W discharge (DBF1-H1-06 lower bound); both cases below 1,350 W and below 1,500 W"),
        item("DBF12-PWR-06", "POWER", "Xe 25 mN Hall discharge-power allocation (design capability requirement)", pw["xe_25mN"],
             "W", [src("p6_ledger", "/points/4"), src("p6_ledger", "/rf_trade_line"), src("a9_43")], "design ledger (allocation-based)", "owner-allocation", "OWNER_DECISION",
             "allocation, not demonstrated performance; the ~658 W RP-1 Xe result is PARAMETRIC / NOT_VALIDATED", "FROZEN", pw["xe_25mN_statement"]),
        item("DBF12-OPS-01", "OPERATING_CONCEPT", "AIR mode", "PRIMARY_NOMINAL: density-aware altitude scheduling within 180-230 km; 12 mN sizing point; only inside the admissible AIR density / thrust / drag window",
             "-", [src("a9_40")], "owner decision", "owner-allocation", "OWNER_DECISION", "-", "FROZEN", "A9.40 requirement interpretation"),
        item("DBF12-OPS-02", "OPERATING_CONCEPT", "Xe mode", "REQUIRED_SECONDARY: contingency / off-nominal / upper-envelope (25 mN capability); atmospheric compressor OFF; used when AIR does not give adequate thrust / drag margin",
             "-", [src("a9_40"), src("rfp")], "owner decision / RFP-P17-05, P18-08", "owner-allocation", "OWNER_DECISION", "-", "FROZEN", "A9.40"),
        item("DBF12-OPS-03", "OPERATING_CONCEPT", "196-state set", "CONSERVATIVE_VERIFICATION_DATASET (retained, not weakened; not 196 mandatory independent AIR propulsion points)",
             "-", [src("states_196"), src("a9_40")], "frozen dataset / owner interpretation", "model-derived", "OWNER_DECISION", "-", "FROZEN", "A9.40"),
        item("DBF12-HOST-01", "HOST_INTERFACE", "IR-HOST-DRAG-01", {"requirement": "host spacecraft C_D*A supplied at PDR and within the propulsion drag-compensation envelope",
             "reference_proposal_sizing_CdA_m2": 0.50, "scope": "reference sizing only; not a universal spacecraft requirement"},
             "m2", [src("a9_40")], "owner decision", "owner-allocation", "OWNER_DECISION", "actual host C_D*A open until PDR", "REFERENCE_PENDING_ICD",
             "supersedes the DBF-1 RC-DIAMANT literature reference (DBF1-DRAG-01)", supersedes=["DBF1-DRAG-01"]),
    ]
    successor = {s: it["id"] for it in new_items for s in it.get("supersedes", [])}
    successor.setdefault("DBF1-IN-08", "DBF12-CMP-01 / DBF12-FEED-01 (F7 performance of the superseded DBF-1 upstream design)")
    items = []
    for k, it in enumerate(parent["items"]):
        c = copy.deepcopy(it)
        c["inherited_from"] = src("dbf1_1", f"/items/{k}")
        if c["id"] in successor:
            c["status_dbf1_2"] = "SUPERSEDED_BY_DCR-DBF1-001"
            c["successor"] = successor[c["id"]]
        else:
            c["status_dbf1_2"] = "INHERITED_UNCHANGED"
        items.append(c)
    items += new_items
    ids = [i["id"] for i in items]
    if len(ids) != len(set(ids)):
        refuse("duplicate item ids")
    # --- deficiencies
    bd = []
    for d in parent["baseline_deficiencies"]:
        c = copy.deepcopy(d)
        if c["id"] in ("DBF1-BD-01", "DBF1-BD-02", "DBF1-BD-03"):
            c["status"] = "SUPERSEDED_BY_DCR-DBF1-001"
            c["note_dbf1_2"] = "the DBF-1 upstream design vector is replaced (DBF12-IN-01 / CMP-01 / FEED-01); the 196 states are a conservative verification set under A9.40; residual flow / compressor risks are in the DBF-1.2 risk register"
        elif c["id"] == "DBF1-BD-04":
            c["status"] = "OPEN_AS_MASS_RISK_MR-DCR001-01"
            c["note_dbf1_2"] = "wet %.3f kg < 40 kg at the preliminary roll-up; the 34.0 kg nominal-dry target is missed by %.3f kg and the 39.4 kg wet target by %.3f kg" % (ms["wet_kg"], -ms["nominal_dry_target_34_gap_kg"], -ms["gap_to_39_4_target_kg"])
        bd.append(c)
    risks = risk_register(ms, pw, mr)
    lineage = {"parent": "DBF-1.1", "parent_lock": src("dbf1_1_lock"), "parent_record": src("dbf1_1"), "grandparent_lock": src("dbf1_lock"),
               "change_authority": "DCR-DBF1-001 (approved)", "dcr_approval": src("dcr_approval"), "dcr_register": src("dcr_register"),
               "approval": "A9.41", "approval_record": src("a9_41"), "build_directions": [src("a9_42"), src("a9_43")], "operating_concept": src("a9_40"),
               "source_checkpoint": SOURCE_CHECKPOINT, "engineering_records": [src("dcr001_v4"), src("dcr001_v5"), src("dcr001_v6")],
               "approval_conditions": appr["conditions"], "open_dcrs_not_applied": open_dcrs,
               "rule": "DBF-1 and DBF-1.1 stay immutable history; DBF-1.2 supersedes DBF-1.1 only as the active integrated preliminary-design baseline"}
    doc = {"schema": parent["schema"], "id": "DBF-1.2", "version": "1.2", "status": STATUS,
           "title": "DBF-1.2 Design Baseline Freeze 1.2 - hall_icp_neutralizer (DCR-DBF1-001: intake / compressor / plenum-feed, mass and power closure)",
           "date": DATE, "architecture": parent["architecture"], "lineage": lineage,
           "status_semantics": {"meaning": "architecture / design parameters frozen at preliminary-design level; measured compliance open to EM / QM testing; open verification items do not unfreeze the baseline",
                                "never_label_as": FORBIDDEN_STATUS},
           "authority_rule": "this JSON is authoritative; DBF1_2_v1.md restates it; dbf1_2_config_v1.json is the machine-readable subset; all pinned by dbf1_2_lock_v1.json",
           "source_rule": parent["source_rule"] + "; DBF-1.2 values are read from pinned records by the builder, not retyped",
           "status_vocabulary": dict(parent["status_vocabulary"], SUPERSEDED_BY_DCR_DBF1_001="a DBF-1.1 item replaced by its DBF-1.2 successor (kept for traceability)",
                                     INHERITED_UNCHANGED="a DBF-1.1 item carried unchanged (value copied from the pinned DBF-1.1 record)"),
           "evidence_attributes": parent["evidence_attributes"], "hardware_configuration": dict(parent["hardware_configuration"], upstream="DCR-DBF1-001 integrated intake / compressor / plenum-feed"),
           "operating_modes": {i["id"]: i["value"] for i in new_items if i["group"] == "OPERATING_CONCEPT"},
           "intake_compressor_feed": {i["id"]: i["value"] for i in new_items if i["group"] in ("INTAKE", "COMPRESSOR", "PLENUM_FEED")},
           "air_design_point": {i["id"]: i["value"] for i in new_items if i["group"] == "AIR_DESIGN_POINT"},
           "mass_rollup": ms, "power_rollup": pw, "items": items, "baseline_deficiencies": bd,
           "risk_register": {"file": FILES["risks"], "count": len(risks["risks"])}, "requirement_trace": {"file": FILES["trace"]},
           "subsystem_references": {"h1_bz": [src("p3_bz")], "icp": [src("icp_closure")], "materials": [src("materials")], "thermal": [src("thermal")],
                                    "power": [src("p6_ledger")], "closure_board": [src("closure_board")], "architecture_conclusion": [src("conclusion_v2")],
                                    "xe_ledger": [src("xe_ledger")], "rule": "inherited subsystems are governed by the DBF-1.1 items and these pinned records; values are not duplicated here"},
           "change_control": dict(parent["change_control"], register=PINS["dcr_register"][0],
                                  rule="DBF-1.2 is immutable except through a new DCR (DCR_PROCESS.md); a new approved DCR creates a new baseline version"),
           "not": parent["not"] + ["not fully RFP-qualified, not demonstrated compliant, not flight-qualified, not performance validated, not a final flight design",
                                    "not a proposal / technical-annexure / bid-package regeneration"],
           "generated_by": f"{REL_OUT}/build_dbf1_2.py"}
    for f in FORBIDDEN_STATUS:
        if f.lower() in STATUS.lower():
            refuse("forbidden status wording")
    cfg = config(pcfg, doc, md_siz)
    trace = requirement_trace(rfp, rvm, doc)
    manifest = {"id": "dbf1_2_source_manifest_v1", "baseline": "DBF-1.2", "source_checkpoint": SOURCE_CHECKPOINT,
                "pins": {k: {"path": p, "sha256": h} for k, (p, h) in sorted(PINS.items())}}
    return doc, cfg, trace, risks, manifest


def risk_register(ms, pw, mr):
    R = lambda id_, t, basis, verif: {"id": id_, "title": t, "basis": basis, "verification": verif, "status": "OPEN"}
    corner = pw["air_12mN_p6_conservative_corner"]["P_bus_W"]
    risks = [
        dict(R("MR-DCR001-01", "mass closure: preliminary roll-up %.3f kg wet; ~%.3f kg numerical headroom is NOT design margin" % (ms["wet_kg"], ms["numerical_headroom_to_40_kg"]),
               "A9.41 mass risk", "CBE / quotation / EM mass measurement; any mass growth needs a DCR before acceptance"), drivers=mr["drivers"], mitigation=mr["mitigation"]),
        R("VR-PPU-01", "AL-07 PPU preliminary CBE 4.55 kg (5.46 kg MEV) confirmation", "v6 component estimate, mostly assumed", "early PPU design / quotation (RFQ3-HALLEL); revert to 6.0 kg floor gives ~40.57 kg wet"),
        R("VR-XE-01", "Xe tank MEOP / burst factor / quotation", "XA9-28 / XA9-29 TBD; 1.25 L Ti sphere sized at 150 bar, burst factor 2", "tank quotation with MEOP at 323 K"),
        R("VR-CMP-01", "compressor actual mass (7.767 kg MEV governing)", "component estimates partly assumed", "EM mass measurement"),
        R("VR-CMP-02", "compressor F6 / B7 transitional performance", "F6 crosses 0.1 Pa, B7 transitional; not admitted", "EM compressor characterisation"),
        R("VR-CMP-03", "Holweck coefficients", "drag-channel form, coefficients uncited", "EM test"),
        R("VR-CMP-04", "rotor growth / running clearance", "drum growth 0.34-0.36 mm vs 0.3 mm running clearance", "EM spin test, clearance design"),
        R("VR-FEED-01", "H1 distributor flow uniformity (+/-5 %)", "preliminary interface requirement", "EM flow-uniformity test"),
        R("VR-HALL-01", "air-Hall 26.8 km/s design-performance basis", "PARAMETRIC / NOT_VALIDATED; Hall credible set empty", "EM thrust measurement on N2 / air"),
        R("VR-HALL-02", "22 km/s sensitivity (0.545 mg/s, ~6.1 Pa setpoint)", "sensitivity case", "EM verification"),
        R("VR-XE-02", "Xe 25 mN power / performance", "allocation <= %.1f W (nominal ICP) / <= %.1f W (+100 W RF) at 1,450 W; ~658 W RP-1 Xe result PARAMETRIC / NOT_VALIDATED" % (
            pw["xe_25mN"]["1450W_design_ceiling_le"]["nominal_ICP_P_d_max_W"], pw["xe_25mN"]["1450W_design_ceiling_le"]["RF_plus_100W_P_d_max_W"]), "EM / QM thrust and power measurement"),
        R("VR-PWR-01", "AIR 12 mN bus under the P6 conservative non-discharge corner", "P-12 conservative corner + 77 W compressor allowance = %.1f W (%s the 1,500 W RFP limit; reference / conservative design values %.1f / %.1f W)" % (
            corner, "ABOVE" if corner >= RFP_P_BUS_W else "below", pw["air_12mN"]["reference"]["P_bus_W"], pw["air_12mN"]["conservative"]["P_bus_W"]),
          "measured non-discharge loads (RF generator efficiency, ICP, magnets, housekeeping) on EM; corner exceedance managed by RF / altitude schedule"),
        R("VR-HAR-01", "routed harness mass", "5/95 rule until routed", "routed harness design"),
        R("VR-AL09-01", "AL-09 control-electronics CBE", "1.0 kg owner allocation", "controller design CBE"),
        R("VR-AL10-01", "AL-10 structural / thermal CBE", "2.5 kg owner allocation", "structural / thermal design CBE"),
        R("VR-HOST-01", "actual host C_D*A", "IR-HOST-DRAG-01 reference 0.50 m2", "host ICD at PDR"),
        R("VR-EMQM-01", "EM / QM AO, thermal, life and qualification tests", "RFP-P19-04 / P19-06", "EM / QM programme"),
    ]
    return {"id": "dbf1_2_risk_register_v1", "baseline": "DBF-1.2",
            "rule": "an open verification item does not unfreeze the preliminary baseline; it is verified during the funded EM / QM programme", "risks": risks}


def requirement_trace(rfp, rvm, doc):
    rows = {r["id"]: r for r in rvm["rows"]}
    clauses = {c["id"] if "id" in c else c.get("clause_id"): c for c in rfp.get("clauses", [])}
    T = lambda req, rv, rfp_ids, items, state, note: {"requirement": req, "rvm": rv, "rfp_clauses": rfp_ids, "dbf1_2_items": items, "state": state, "note": note}
    pr = doc["power_rollup"]
    trace = [
        T("altitude 180-230 km", "RVM-01", ["RFP-P18-08"], ["DBF12-OPS-01"], "CONFORMING_BY_DESIGN / VERIFY_EM_QM", "density-aware altitude scheduling"),
        T(">= 12 mN sustained atmospheric", "RVM-02", ["RFP-P18-06"], ["DBF12-AIR-01", "DBF12-PWR-05"], "CONFORMING_BY_DESIGN_ALLOCATION / VERIFY_EM_QM", "12 mN at P_d 650 W inside the AIR window; not demonstrated"),
        T("25 mN capability", "RVM-03", ["RFP-P18-06"], ["DBF12-OPS-02", "DBF12-PWR-06"], "CONFORMING_BY_DESIGN_ALLOCATION / VERIFY_EM_QM", "Xe mode (A9.40); Xe use booked; not atmospheric"),
        T("P_bus < 1500 W", "RVM-04", ["RFP-P18-10"], ["DBF12-PWR-05", "DBF12-PWR-06"], "CONFORMING_BY_DESIGN_ALLOCATION / VERIFY_EM_QM",
          "AIR %.1f / %.1f W; Xe 25 mN at <= 1450 W design ceiling" % (pr["air_12mN"]["reference"]["P_bus_W"], pr["air_12mN"]["conservative"]["P_bus_W"])),
        T("internal 1350 W allocation", "RVM-05", [], ["DBF1-PWR-01", "DBF12-PWR-05"], "WITHIN_ALLOCATION (AIR nominal)", "Xe 25 mN capability uses the 1350-1450 W band (non-nominal, A9.40)"),
        T("mass < 40 kg", "RVM-06", ["RFP-P18-11"], ["DBF12-MASS-05"], "CONFORMING_BY_PRELIMINARY_ROLLUP / OPEN_MASS_RISK", "%.3f kg wet; MR-DCR001-01" % doc["mass_rollup"]["wet_kg"]),
        T("internal 34 / 36 kg allocation", "RVM-07", [], ["DBF1-MASS-02", "DBF12-MASS-05"], "TARGET_NOT_MET (nominal dry %.3f kg)" % doc["mass_rollup"]["nominal_dry_kg"], "DBF1-BD-04 open as mass risk"),
        T("atmospheric propellant", "RVM-08", ["RFP-P18-08", "RFP-P17-03", "RFP-P17-04"], ["DBF12-IN-01", "DBF12-CMP-01", "DBF12-FEED-01"], "CONFORMING_BY_DESIGN / VERIFY_EM_QM", "intake + compressor + plenum / feed"),
        T("Xe capability, two separate tanks", "RVM-10 / RVM-29", ["RFP-P18-08", "RFP-P17-05"], ["DBF12-OPS-02"], "CONFORMING_BY_DESIGN", "AL-08 Xe branch 2 kg reference"),
        T("Hall preferred", "RVM-11", ["RFP-P18-07"], ["DBF1-H1-01"], "CONFORMING_BY_DESIGN", "H1 inherited unchanged"),
        T("neutralization (cathodeless)", "RVM-15 / RVM-28", [], ["DBF1-ICP-01"], "CONFORMING_BY_DESIGN / VERIFY_EM_QM", "ICP inherited unchanged"),
        T("AO material compatibility", "RVM-16", ["RFP-P19-04"], ["DBF1-MAT-01"], "VERIFY_EM_QM", "materials inherited"),
        T("thermal closure", "RVM-17", [], ["DBF1-TH-01"], "VERIFY_EM_QM", "thermal inherited; anode / coupled thermal UNRESOLVED"),
        T("electronics redundancy (no SPF)", "RVM-19", ["RFP-P18-09", "RFP-P18-02"], ["DBF12-MASS-05"], "CONFORMING_BY_DESIGN (PPU N+1) / VERIFY_FMEA", "v6 PPU CBE carries N+1 / redundant electronics"),
        T("MIL-1553B interface", "RVM-20", ["RFP-P18-12"], [], "ALLOCATED_TO_AL-09", "controls allocation"),
        T("environmental qualification", "RVM-21", ["RFP-P19-04"], [], "VERIFY_EM_QM", "EM / QM programme"),
        T("mission life / firing hours", "RVM-12 / RVM-13", [], [], "VERIFY_EM_QM", "life tests"),
    ]
    missing = [t["rvm"] for t in trace for r in t["rvm"].split(" / ") if r not in rows]
    if missing:
        refuse(f"RVM rows not found: {missing}")
    for t in trace:
        for i in t["dbf1_2_items"]:
            if i not in {x["id"] for x in doc["items"]}:
                refuse(f"trace names unknown item {i}")
    return {"id": "dbf1_2_requirement_trace_v1", "baseline": "DBF-1.2", "rvm": src("rvm"), "rfp": src("rfp"), "trace": trace,
            "rule": "CONFORMING_BY_DESIGN / ALLOCATION means the frozen design meets the requirement by specification and allocation; measured compliance is verified on EM / QM"}


def config(pcfg, doc, md_siz):
    ms, pw = doc["mass_rollup"], doc["power_rollup"]
    up = doc["intake_compressor_feed"]
    return {"schema": "abep_dbf1_2_config_v1", "id": "dbf1_2_config_v1", "baseline": "DBF-1.2", "status": STATUS,
            "authoritative_record": f"{REL_OUT}/{FILES['json']}",
            "h1": pcfg["h1"], "rf": pcfg["rf"], "icp": pcfg["icp"], "thermal": pcfg["thermal"], "materials": pcfg["materials"],
            "upstream": {"aperture_m2": 0.70, "collimator_L_over_D": 20.0, "S_eff_inlet_m3_s": up["DBF12-IN-01"]["S_eff_inlet_m3_s"],
                         "compressor": {k: up["DBF12-CMP-01"][k] for k in ("blade_rows", "rpm", "tip_speed_m_s", "governing_mev_kg", "power_allowance_W", "power_estimate_W")},
                         "plenum_setpoint_Pa": up["DBF12-FEED-01"]["setpoint_Pa"], "plenum_band_Pa": up["DBF12-FEED-01"]["band_Pa"], "plenum_V_L": up["DBF12-FEED-01"]["volume_L"],
                         "distributor_holes": up["DBF12-FEED-02"]["outlet_holes"]},
            "air_design_point": {"thrust_mN": 12.0, "v_eff_km_s": 26.8, "hall_feed_mg_s": md_siz, "P_d_W": 650.0},
            "power": {"air_12mN_P_bus_W": {k: v["P_bus_W"] for k, v in pw["air_12mN"].items()}, "xe_25mN_P_d_max_W": pw["xe_25mN"],
                      "rfp_P_bus_lt_W": RFP_P_BUS_W, "design_allocation_W": DESIGN_ALLOC_W, "xe_design_ceiling_W": XE_CEILING_W},
            "mass": {k: ms[k] for k in ("nonharness_kg", "harness_kg", "nominal_dry_kg", "dry_10pct_kg", "xe_reference_kg", "wet_kg")} | {"open_mass_risk": "MR-DCR001-01"},
            "host_drag": {"requirement": "IR-HOST-DRAG-01", "reference_CdA_m2": 0.50, "label": "REFERENCE_PENDING_ICD"},
            "lineage": {"parent": "DBF-1.1", "parent_lock_sha256": PINS["dbf1_1_lock"][1], "dcr": "DCR-DBF1-001", "dcr_approval_sha256": PINS["dcr_approval"][1],
                        "source_checkpoint": SOURCE_CHECKPOINT}}


def dumps(o) -> bytes:
    return (json.dumps(o, indent=1, ensure_ascii=False) + "\n").encode("utf-8")


def fmt(v) -> str:
    s = json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)
    s = s.replace("|", "\\|")
    return s if len(s) <= 160 else s[:157] + "..."


def render_md(doc, trace, risks) -> bytes:
    lin, ms, pw = doc["lineage"], doc["mass_rollup"], doc["power_rollup"]
    a, x = pw["air_12mN"], pw["xe_25mN"]
    L = [f"# {doc['status']}", "", f"{doc['title']}", "",
         f"Authoritative record: `{FILES['json']}` (this page restates it). Machine-readable subset: `{FILES['config']}`. Requirement trace: "
         f"`{FILES['trace']}`. Risk register: `{FILES['risks']}`. Source manifest: `{FILES['manifest']}`. Hash lock: `{FILES['lock']}`. "
         "Change control: `docs/baseline/DBF-1/DCR_PROCESS.md` (DBF-1.2 is immutable except through a new DCR).", "",
         "Status meaning: architecture and design parameters are frozen at preliminary-design level; measured compliance is open to EM / QM "
         "testing. It is not fully RFP-qualified, not demonstrated compliant, not flight-qualified, not performance validated, not a final flight design.", "",
         "## Lineage", "",
         f"- parent: DBF-1.1, lock `{lin['parent_lock']['sha256']}` (immutable); DBF-1 lock `{lin['grandparent_lock']['sha256']}` (immutable)",
         f"- change authority: {lin['change_authority']}; approval A9.41 `{lin['approval_record']['path']}`; approval record `{lin['dcr_approval']['path']}`; register `{lin['dcr_register']['path']}`",
         f"- build directions: A9.42, A9.43 (power reconciliation); operating concept A9.40; source checkpoint `{lin['source_checkpoint']}`",
         f"- open DCRs not applied: {', '.join(d['id'] + ' (' + d['status'] + ')' for d in lin['open_dcrs_not_applied']) or 'none'}", "",
         "## Intake / compressor / plenum-feed (DCR-DBF1-001)", ""]
    up = doc["intake_compressor_feed"]
    i1, c1, f1, f2 = up["DBF12-IN-01"], up["DBF12-CMP-01"], up["DBF12-FEED-01"], up["DBF12-FEED-02"]
    L += [f"- intake: aperture {i1['aperture_m2']} m² (equivalent diameter {i1['equivalent_diameter_m']:.3f} m), collimator L/D {i1['collimator_L_over_D']:.0f}, "
          f"retention S_eff {i1['S_eff_inlet_m3_s']:.3f} m³/s; delivered flow regulated by active compressor / retention control with density-aware altitude scheduling; "
          "exposed frontal drag is NOT controlled by compressor speed",
          f"- compressor: integrated contra-rotating molecular compressor, {c1['blade_rows']} blade rows + shared Holweck rear section, two coaxial counter-rotating shafts, "
          f"{c1['rpm']:.0f} rpm, tip speed {c1['tip_speed_m_s']:.0f} m/s, full-aperture front section, no separate finishing pump; governing mass {c1['governing_mev_kg']} kg MEV; "
          f"power estimate {c1['power_estimate_W']} W, allowance {c1['power_allowance_W']:.0f} W",
          f"- plenum: setpoint {f1['setpoint_Pa']:.3f} Pa (band {f1['band_Pa'][0]:.2f}-{f1['band_Pa'][1]:.2f} Pa), volume {f1['volume_L']:.2f} L; "
          f"22 km/s sensitivity needs {f1['sensitivity_setpoint_22kms_Pa']:.2f} Pa",
          f"- distributor: {f2['outlet_holes']} x {f2['hole_d_mm']:.0f} mm holes, ring {f2['ring_mm'][0]:.0f} x {f2['ring_mm'][1]:.0f} mm, {f2['inlets']} inlets; {f2['uniformity_requirement']}", "",
          "| row | shaft | r_tip / r_hub (m) | blade (mm) | u_rel (m/s) | p_in -> p_out (Pa) | K | Kn out | classification |", "|---|---|---|---|---|---|---|---|---|"]
    cmp2 = next(i for i in doc["items"] if i["id"] == "DBF12-CMP-02")["value"]
    for r in cmp2["rows"]:
        L.append(f"| {r['row']} | {r['shaft']} | {r['r_tip_m']:.3f} / {r['r_hub_m']:.3f} | {r['blade_height_mm']:.1f} | {r['u_rel_m_s']:.0f} | {r['p_in_Pa']:.4f} -> {r['p_out_Pa']:.4f} | {r['K']:.2f} | {r['Kn_out']:.1f} | {r['classification']} |")
    h = cmp2["holweck"]
    L += [f"| H | A (drum skin) | - | groove {h['groove_depth_mm']:.1f} | - | {h['p_in_Pa']:.3f} -> {h['p_out_Pa']:.3f} | - | {h['Kn_out']:.2f} | {h['classification']} |", "",
          "## AIR design point and operating modes", ""]
    ad = doc["air_design_point"]
    L += [f"- {k}: {fmt(v)}" for k, v in ad.items()]
    L += [f"- {k}: {v}" for k, v in doc["operating_modes"].items()]
    L += ["", "## Power (P6 ledger + DBF-1.2 compressor; A9.43)", "",
          "| case | P_d (W) | compressor (W) | P_bus (W) | margin to 1,350 W | margin to 1,500 W |", "|---|---|---|---|---|---|"]
    for k, v in a.items():
        L.append(f"| AIR 12 mN {k} | {v['P_d_W']:.1f} | {v['compressor_load_W']:.1f} | {v['P_bus_W']:.3f} | {v['margin_to_1350_W']:.3f} | {v['margin_to_1500_W']:.3f} |")
    L += ["", f"Model thrust at P_d 650 W: {pw['air_12mN_model_thrust_at_650W']['value_mN']:.3f} mN — {pw['air_12mN_model_thrust_at_650W']['label']}.", "",
          "| Xe 25 mN Hall discharge allocation | nominal ICP (W) | +100 W RF (W) |", "|---|---|---|",
          f"| ≤ 1,450 W design ceiling | ≤ {x['1450W_design_ceiling_le']['nominal_ICP_P_d_max_W']:.3f} | ≤ {x['1450W_design_ceiling_le']['RF_plus_100W_P_d_max_W']:.3f} |",
          f"| < 1,500 W RFP | < {x['1500W_rfp_supremum_lt']['nominal_ICP_P_d_max_W']:.3f} | < {x['1500W_rfp_supremum_lt']['RF_plus_100W_P_d_max_W']:.3f} |", "",
          pw["xe_25mN_statement"] + " The ~658 W RP-1 Xe result is PARAMETRIC / NOT_VALIDATED. Atmospheric compressor OFF in Xe mode.", "",
          f"Basis: chain efficiency {pw['basis']['discharge_chain_eta']}, P-XE non-discharge {pw['basis']['PXE_non_discharge_W']:.4f} W, +100 W RF = +{pw['basis']['rf_plus_100W_bus_W']:.4f} W bus "
          "(DCR-001 v4 terms 412.5 W / 0.855 / +129 W superseded); DCR-001 596 / 600 W discharge figures are historical model predictions, not governing.", "",
          "## Mass (A9.41, approved v6 roll-up)", "", "| line | MEV (kg) |", "|---|---|"]
    for k, v in ms["lines_mev_kg"].items():
        L.append(f"| {k} | {v:.4f} |")
    L += [f"| non-harness | {ms['nonharness_kg']:.4f} |", f"| harness (5/95) | {ms['harness_kg']:.4f} |", f"| nominal dry | {ms['nominal_dry_kg']:.4f} |",
          f"| + 10 % system margin | {ms['dry_10pct_kg']:.4f} |", f"| + Xe reference | {ms['xe_reference_kg']:.4f} |", f"| **preliminary wet** | **{ms['wet_kg']:.4f}** |", "",
          ms["bid_wording"], "", f"PPU: {ms['ppu']['AL-07_governing_mev_kg']} kg MEV ({ms['ppu']['status']}); historical 6.0 kg floor preserved in history. {ms['icp_mount_correction']}. {ms['compressor_booking']['note']}.", "",
          "## Host interface", "", f"- IR-HOST-DRAG-01: {fmt(next(i for i in doc['items'] if i['id'] == 'DBF12-HOST-01')['value'])}", "",
          "## Open risks / verification (do not unfreeze the baseline)", "", "| id | item | basis | verification |", "|---|---|---|---|"]
    for r in risks["risks"]:
        L.append(f"| {r['id']} | {fmt(r['title'])} | {fmt(r['basis'])} | {fmt(r['verification'])} |")
    L += ["", "## Requirement trace", "", "| requirement | RVM | RFP | DBF-1.2 items | state |", "|---|---|---|---|---|"]
    for t in trace["trace"]:
        L.append(f"| {t['requirement']} | {t['rvm']} | {', '.join(t['rfp_clauses'])} | {', '.join(t['dbf1_2_items'])} | {t['state']} |")
    L += ["", "## Items", "", "| id | item | value | status (DBF-1.2) |", "|---|---|---|---|"]
    for it in doc["items"]:
        L.append(f"| {it['id']} | {fmt(it['name'])} | {fmt(it['value'])} | {it.get('status_dbf1_2', it['status'])}{' -> ' + it['successor'] if it.get('successor') else ''} |")
    L += ["", "## Baseline deficiencies", "", "| id | category | status |", "|---|---|---|"]
    for d in doc["baseline_deficiencies"]:
        L.append(f"| {d['id']} | {d['category']} | {d.get('status', 'OPEN')} |")
    L += ["", "## Not", ""] + [f"- {x_}" for x_ in doc["not"]]
    return ("\n".join(L) + "\n").encode("utf-8")


def outputs() -> dict:
    doc, cfg, trace, risks, manifest = build()
    out = {FILES["json"]: dumps(doc), FILES["md"]: render_md(doc, trace, risks), FILES["config"]: dumps(cfg),
           FILES["trace"]: dumps(trace), FILES["risks"]: dumps(risks), FILES["manifest"]: dumps(manifest)}
    lock = {"id": "dbf1_2_lock_v1", "baseline": "DBF-1.2", "status": STATUS, "locked": DATE,
            "note": "sha256 of the DBF-1.2 files (successor of DBF-1.1 by the approved DCR-DBF1-001, A9.41); any change after this lock is a DCR with a new baseline version, never an edit",
            "files_relative_to": REL_OUT + "/",
            "files": {k: sha_bytes(v) for k, v in sorted(list(out.items()) + [("build_dbf1_2.py", Path(__file__).read_bytes())])},
            "lineage": {"parent_lock": PINS["dbf1_1_lock"][0], "parent_lock_sha256": PINS["dbf1_1_lock"][1], "dcr": "DCR-DBF1-001",
                        "dcr_approval": PINS["dcr_approval"][0], "dcr_approval_sha256": PINS["dcr_approval"][1], "approval": "A9.41",
                        "source_checkpoint": SOURCE_CHECKPOINT},
            "pinned_sources": {PINS[k][0]: PINS[k][1] for k in sorted(PINS)}}
    out[FILES["lock"]] = dumps(lock)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    out = outputs()
    if a.check:
        stale = [k for k, v in out.items() if not (OUT / k).is_file() or (OUT / k).read_bytes() != v]
        if stale:
            print(f"STALE: {stale}")
            return 1
        print(f"OK: {len(out)} DBF-1.2 files current")
        return 0
    for k, v in out.items():
        (OUT / k).write_bytes(v)
    print(f"wrote {len(out)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
