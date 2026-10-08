"""Build DBF-1 (Design Baseline Freeze 1) for hall_icp_neutralizer (owner decision A9.37, 2026-10-08).

Every frozen value is read from a sha256-pinned repository record (or is an owner-fixed A9.37 value checked against
its record); the three selections (intake / compressor, host drag basis, anode / electrode materials) are executed
here by the selection rules registered in the output, on registered candidates only. Nothing is evaluated on the
196 design states here: the selection reads committed records. A pin that does not verify, or a value that differs
from the record at its pointer, refuses the build (fail closed).

Usage: python3 docs/baseline/DBF-1/build_dbf1.py            write the DBF-1 files
       python3 docs/baseline/DBF-1/build_dbf1.py --check    regenerate in memory, compare byte for byte
"""
from __future__ import annotations

import argparse
import collections
import gzip
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
REL_OUT = "docs/baseline/DBF-1"
BUILDER = f"{REL_OUT}/build_dbf1.py"

PINS = {
    "A937_MD": ("docs/decisions/OD_2026_10_08_A9_37_DBF_1_DESIGN_BASELINE_FREEZE.md",
                "fbe62372e719daaabd41f3a65ae20b14e7909a28b46eed288488b42f3700cb43"),
    "A937_JSON": ("docs/decisions/OD_2026_10_08_A9_37_dbf_1_design_baseline_freeze.json",
                  "716f933c2f65cdf19fe5f872a8bb5aa6bb94531afd4d7931509f5eb82519cbb1"),
    "A926_MD": ("docs/decisions/OD_2026_10_05_A9_26_MASS_BUDGET_OWNER_DECISIONS.md",
                "5f40294de9ab736cedd7a24a393b0333823c2624e3469f6b1f775250a85803e5"),
    "A926_JSON": ("docs/decisions/OD_2026_10_05_A9_26_mass_budget_owner_decisions.json",
                  "18dada24a90fb1a5d17e903bf8eb9f77af622106f9ddfc59ea1f182054b80b76"),
    "A913_MD": ("docs/decisions/OD_2026_10_01_A9_13_S6_UPSTREAM_ARCHITECTURE_OWNER_DECISIONS.md",
                "adf11923c07f773276ee893d6ad01cd51c4988ba4bfb8865ec1d781a4978c8bf"),
    "H1F": ("docs/hardware/h1_freeze_candidate/h1_freeze_candidate_v1.json",
            "36aca79c1e515f6828f120d4b90174815e888780f4070e08cd70dff31b9ab1a8"),
    "H21": ("docs/hardware/h2/h2_1_hall_chamber_magnet/h2_1_hall_chamber_magnet_v1.json",
            "49b9a45e9347b141bf8bd1122ffba3ae038c9f088041e4410525e4ab8695b82d"),
    "ENV_PREREG": ("docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/prereg_v1.json",
                   "3275f85752fae258e4e4124cbe43d8756e8dfede70f560f8b2e7d66a40164b4d"),
    "A5_RECORD": ("docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/intake_closure_a5_v1.json",
                  "f971eecef6d7a5891aaced5880eeadd66dc796bbd07af619d12be46856546d89"),
    "F7_PARETO": ("docs/rust_migration/contracts/C-ABEP_SIM_DESIGN_ARCHITECTURE_OPTIMIZER_PY/reference_outputs/"
                  "f7_pareto_blocks_v1.json.gz",
                  "de6ee69f21d4e5b4daba6e1b8bed263598b950b19cae9da49d309ec4d7664f00"),
    "F3_DESIGNS": ("docs/design_synthesis/f3_compressor/f3_compressor_designs_v1.json",
                   "74a52aa749e1d071f76957e4f9ef4929c9d8ab302b183da3c5a5d9ba8d6d6923"),
    "F1_CORE": ("docs/design_synthesis/f1_intake/f1_intake_synthesis_v1_core.json",
                "d397cb9348d06eafbe2e7cc3ee9ca035f97e8f423d63df8f42286ce75bc20854"),
    "F4_FEED": ("docs/design_synthesis/f4_plenum/f4_plenum_feed_v1.json",
                "fffb223023f944f166112acf017af277a50ede84695cb78f933dd5ca918fd3a9"),
    "F4_BUILD": ("docs/design_synthesis/f4_plenum/build_f4_plenum.py", None),
    "F6_ICP": ("docs/design_synthesis/f6_icp_geometry/f6_icp_geometry_v1.json",
               "eace9c279f09ab25ba0d3c5c7f2d2c4e42da682a16e2f3bd474d7c3fef755450"),
    "P1_BENCH": ("docs/experiments/hall_icp/p1_icp_bench/p1_icp_bench_v1.json",
                 "d0a696c597c839802a405d6607abe03a1dc5e5bb917cd11405a86aa3be9e4f08"),
    "P4_MATERIALS": ("docs/experiments/hall_icp/p4_anode_materials/p4_anode_materials_v1.json",
                     "f0d8bbfa6d3ec59a30910ef2ae1fd61f96fc3f725e6859dc8c6617b1cf6dd96b"),
    "MP_V5": ("docs/budgets/mass_power_a9_v5/mass_power_a9_v5.json",
              "3ff23429f5225a8a8363a784281b2f32b1df9ad69ec9934320306b080436b73a"),
    "BUS_A9_V2": ("abep_sim/bus_boundary_a9_v2.py",
                  "8964520ffb55d97eeb93c4b8cc45250026e0c6a0b3082ea58fcfd834ba661e26"),
    "ICP_PREREG_V2": ("docs/rust_migration/new_physics/NP-ICP-NEUTRALIZER/prereg_v2.json",
                      "3f0df5b85286bfc82ce99ec9bfafb81ec785021b1668d5bc95fe0d29679631e9"),
    "ICP_LOCK_V2": ("docs/rust_migration/new_physics/NP-ICP-NEUTRALIZER/prereg_lock_v2.json",
                    "a180ceef37223467687d7d245ab790a172e8dad9ea4e90aa463d434383142287"),
    "THERMAL_PREREG_V1": ("docs/rust_migration/new_physics/NP-THERMAL-CATHODELESS/prereg_v1.json",
                          "e3e6859cf61703c27254e9c231ff4637f7d20ea743c8d881b9e55c8ba9d27c5c"),
    "THERMAL_PREREG_V2": ("docs/rust_migration/new_physics/NP-THERMAL-CATHODELESS/prereg_v2.json",
                          "6828f3e257e38a588c9513f2531658035fa904b6c51e3b28831681d871adfa78"),
    "THERMAL_LOCK_V2": ("docs/rust_migration/new_physics/NP-THERMAL-CATHODELESS/prereg_lock_v2.json",
                        "727689fee6bd003295c53abfbc4185c93fab80620329c75062a956dbbb9742de"),
    "H25": ("docs/hardware/h2/h2_5_thermal_network/h2_5_thermal_network_v1.json",
            "68c5be61443d0ef1c7308c4aba265426137292dcf9363e57903e0a1f6c8bc083"),
    "DRAG_RECORD": ("docs/design_synthesis/spacecraft_reference_drag/spacecraft_reference_drag_v1.json",
                    "5415f3f2cfdc403c7e23a80cde68eebc8f5bc66868793133094cf0670f9cb39f"),
    "DRAG_REGISTER": ("crates/abep-mission/data/spacecraft_reference_register_v1.json",
                      "4952eb745b201a57406dc6fe0513f6217f654ddb6d2ad7300c5334112a42ffa3"),
    "CONSTRAINTS": ("config/constraints/engineering_constraints_v1.json",
                    "5821cc439ba15b67776072a90d64bafca8be0740150acec51da5c59a238ae74e"),
    "GATES": ("config/assessment/gate_thresholds_v1.json",
              "504af5968d692286770ff89a3800b04ff83b6f96aff8e1fe21ee779e9cef3a3b"),
}
F7_JSON_SHA256 = "07d5335d4f020fa1fa9e2d91796669b2790383c74a486aa84d7e4de37889af3c"

FILES = {
    "json": "dbf1_v1.json",
    "md": "DBF1_v1.md",
    "config": "dbf1_config_v1.json",
    "dcr_register": "dcr_register_v1.json",
    "lock": "dbf1_lock_v1.json",
}
DCR_PROCESS = "DCR_PROCESS.md"   # hand-written, pinned by the lock

STATUSES = {
    "FROZEN": "the value is frozen as the design value; its evidence supports it at the stated class",
    "FROZEN_ASSUMPTION": "the value is frozen as the selected engineering assumption; the evidence is incomplete and "
                         "the class / uncertainty say how (A9.37: never left open)",
    "REFERENCE_PENDING_ICD": "a frozen reference value standing in for a customer / host ICD that does not exist; "
                             "replaced only by that ICD through a DCR",
    "BASELINE_DEFICIENCY": "the value is frozen (it is the design) and a registered closure condition is known not to be "
                           "met by it; the deficiency record gives the numbers. Not a reason to keep trading (A9.37)",
}


class BuildError(RuntimeError):
    pass


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def read_pinned(key: str) -> bytes:
    rel, want = PINS[key]
    b = (ROOT / rel).read_bytes()
    got = sha_bytes(b)
    if want is not None and got != want:
        raise BuildError(f"{rel}: sha256 {got} != pinned {want} (pinned record changed; refused)")
    return b


def js(key: str):
    return json.loads(read_pinned(key))


def ptr(doc, p: str):
    o = doc
    for k in p.strip("/").split("/"):
        o = o[int(k)] if isinstance(o, list) else o[k]
    return o


def src(key: str, pointer: str | None = None, note: str | None = None) -> dict:
    rel, _ = PINS[key]
    s = {"path": rel, "sha256": sha_bytes(read_pinned(key))}
    if pointer is not None:
        s["pointer"] = pointer
    if note:
        s["note"] = note
    return s


def expect(doc, pointer: str, want, what: str):
    got = ptr(doc, pointer)
    if got != want:
        raise BuildError(f"{what}: value at {pointer} is {got!r}, expected {want!r}")
    return got


def item(iid, group, name, value, units, sources, evidence_class, quantity_type, level, uncertainty, status,
         rationale, **extra):
    if status not in STATUSES:
        raise BuildError(f"{iid}: status {status}")
    d = {"id": iid, "group": group, "name": name, "value": value, "units": units, "sources": sources,
         "evidence_class": evidence_class, "quantity_type": quantity_type, "evidence_level": level,
         "uncertainty": uncertainty, "status": status, "rationale": rationale}
    d.update(extra)
    return d


# ================================================================================================ H1 geometry / B(z)
def h1_items():
    h1 = js("H1F")
    env = js("ENV_PREREG")
    probe = expect(h1, "/x_hall_design_space/probe_evaluations/16/probe", "RP-1 anchor (not a selection)", "RP-1 probe")
    del probe
    rp1 = ptr(h1, "/x_hall_design_space/probe_evaluations/16")
    if (rp1["d_mean_mm"], rp1["h_mm"], rp1["L_mm"]) != (70.0, 12.0, 103.2):
        raise BuildError(f"RP-1 probe {rp1}")
    grp = ptr(env, "/case_grid/geometry/points/6")
    if (grp["id"], grp["d_mean_mm"], grp["h_mm"], grp["L_mm"]) != ("G-RP1", 70.0, 12.0, 103.2):
        raise BuildError(f"G-RP1 {grp}")
    if rp1["status"] != "WITHIN_DECLARED_GEOMETRIC_WINDOWS":
        raise BuildError("RP-1 not within the declared windows")
    lh = round(rp1["L_mm"] / rp1["h_mm"], 6)
    geo_src = [src("H1F", "/x_hall_design_space/probe_evaluations/16"),
               src("H1F", "/parameters/10", "H1F-CH-11 note: RP-1 is the H2-1 coil-sizing anchor"),
               src("ENV_PREREG", "/case_grid/geometry/points/6", "envelope configuration G-RP1"),
               src("A937_MD", None, "owner-fixed: d_mean 70 mm, h 12 mm, L/h 8.6 (~103 mm)")]
    unc_geo = "design value (owner-fixed); manufacturing tolerance TBD with the design release (H1F-CH-11 'tolerance TBD')"
    items = [
        item("DBF1-H1-01", "H1_GEOMETRY", "channel mean diameter d_mean", 70.0, "mm", geo_src, "owner-fixed design value",
             "owner-allocation", "OWNER_DECISION", unc_geo, "FROZEN",
             "A9.37 fixes the RP-1 engineering point; inside the H1F-CH-05 window [45.37, 100.6] mm"),
        item("DBF1-H1-02", "H1_GEOMETRY", "channel width h", 12.0, "mm", geo_src, "owner-fixed design value",
             "owner-allocation", "OWNER_DECISION", unc_geo, "FROZEN",
             "A9.37 RP-1; inside the H1F-CH-04 window [7.758, 17.21] mm"),
        item("DBF1-H1-03", "H1_GEOMETRY", "channel length L (HALL_INLET_Z0 to IP-EXIT)", 103.2, "mm", geo_src,
             "owner-fixed design value", "owner-allocation", "OWNER_DECISION", unc_geo, "FROZEN",
             f"A9.37 'L/h 8.6 (~103 mm)': the G-RP1 / RP-1 probe length 103.2 mm, L/h = {lh} (inside the "
             "H1F-CH-08 / CH-09 window [8.603, 12])"),
        item("DBF1-H1-04", "H1_GEOMETRY", "derived radii r_in = (d_mean - h) / 2, r_out = (d_mean + h) / 2",
             {"r_in_mm": 29.0, "r_out_mm": 41.0, "A_channel_mm2": round(math.pi * 12.0 * 70.0, 6)}, "mm; mm^2",
             [src("ENV_PREREG", "/case_grid/geometry/rule")], "derived arithmetic", "model-derived", "DEFINITION",
             "exact arithmetic on DBF1-H1-01 / 02", "FROZEN", "the envelope rule r = (d_mean -/+ h) / 2 (no new number)"),
        item("DBF1-H1-05", "H1_GEOMETRY", "discharge-voltage operating band (operating variable, not a design value)",
             [180.0, 350.0], "V", [src("H21", "/channel/V_d_band_V"), src("H1F", "/parameters/22")],
             "owner allocation", "owner-allocation", "OWNER_DECISION", "band ends as registered",
             "FROZEN", "H2-1 V_d band (H1F-AN-10 350 V rating basis); used by the envelope grid VD-180..VD-350"),
        item("DBF1-H1-06", "H1_GEOMETRY", "discharge-power band (H2-1)", [650.0, 1350.0], "W",
             [src("H21", "/channel/P_d_band_W")], "owner allocation", "owner-allocation", "OWNER_DECISION",
             "band ends as registered", "FROZEN", "the registered H-1 P_d band; its upper end equals the 1,350 W design "
             "allocation (DBF1-PWR-01)"),
    ]
    bz02 = ptr(h1, "/parameters/35")
    bz03 = ptr(h1, "/parameters/36")
    if bz02["id"] != "H1F-BZ-02" or bz03["id"] != "H1F-BZ-03" or bz03["value"] != [69.93, 268.6]:
        raise BuildError("H1F-BZ-02 / 03 changed")
    bzf = ptr(env, "/bz_family")
    if bzf["label"] != "SOURCED_SURROGATE_P5_SHAPE_NOT_H1_BZ" or "0.201 for BZ-P5B16, 0.257 for BZ-P5B30" not in \
            bzf["what_stays_p5"]:
        raise BuildError("envelope bz_family changed")
    shapes = {s["id"]: s for s in ptr(env, "/case_grid/bz_shape")}
    ratios = {"BZ-P5B16": 0.201, "BZ-P5B30": 0.257}
    pick = min(sorted(ratios), key=lambda k: ratios[k])
    bp = ptr(env, "/case_grid/B_peak_G")
    items += [
        item("DBF1-BZ-01", "MAGNETIC_TARGET", "B_r(z) shape target (design target)", bz02["value"], "-",
             [src("H1F", "/parameters/35")], "inferred design target", "inferred", "5",
             "shape tolerance TBD (FEMM + owner tolerance, H1F-BZ-05)", "FROZEN_ASSUMPTION",
             "H1F-BZ-02 (published xenon practice): monotonic rise, peak at or just downstream of z = L, field near the "
             "anode as low as the circuit allows"),
        item("DBF1-BZ-02", "MAGNETIC_TARGET", "peak centreline B_r target band at / near IP-EXIT", [69.93, 268.6], "G",
             [src("H1F", "/parameters/36")], "model-derived design target", "model-derived", "6",
             "a window, not a point (r_Le <= 0.1 h over T_e 10-30 eV); point tolerance set at design release",
             "FROZEN_ASSUMPTION",
             "H1F-BZ-03 (A9.14 F5-OQ-05 ACCEPT_EXISTING_FEMM_FIELD_TARGET_BAND); B_peak inside the band is an "
             "operating variable (coil current), not a hardware variable (envelope prereg hall_specific_closure)"),
        item("DBF1-BZ-03", "MAGNETIC_TARGET", "B_peak operating levels used by the simulation",
             {x["id"]: x["value"] for x in bp}, "G", [src("ENV_PREREG", "/case_grid/B_peak_G")],
             "model-derived design target", "model-derived", "6", "the two band ends; no interior level registered",
             "FROZEN_ASSUMPTION", "the envelope's registered levels BP-LO / BP-HI (the H1F-BZ-03 band ends)"),
        item("DBF1-BZ-04", "MAGNETIC_TARGET", "simulation B(z) shape (surrogate)", pick, "-",
             [src("ENV_PREREG", "/case_grid/bz_shape"), src("ENV_PREREG", "/bz_family/what_stays_p5")],
             "digitized literature shape (surrogate)", "digitized", "3",
             "P5 shape, not an H-1 field: SOURCED_SURROGATE_P5_SHAPE_NOT_H1_BZ (H1F-BZ-01 TBD); gradient, width and "
             "anode-to-peak ratio are P5 properties", "FROZEN_ASSUMPTION",
             "selection rule SR-BZ-01: of the two registered surrogate shapes, the one with the lower anode-to-peak "
             f"ratio, which is the shape closer to the H1F-BZ-02 target 'field near the anode as low as the circuit "
             f"allows' ({ratios['BZ-P5B16']} for BZ-P5B16 vs {ratios['BZ-P5B30']} for BZ-P5B30): {pick} "
             f"({shapes[pick]['source']})",
             label="SOURCED_SURROGATE_P5_SHAPE_NOT_H1_BZ", rigid_registration=bzf["registration_rule"]),
        item("DBF1-BZ-05", "MAGNETIC_TARGET", "MC-1 field capability (necessary design capability)", 403.0, "G",
             [src("H1F", "/parameters/37")], "model-derived", "model-derived", "6",
             "B headroom 1.5 x the band upper end; FEMM pending", "FROZEN_ASSUMPTION", "H1F-BZ-04"),
    ]
    hw = ("G-RP1", pick)
    return items, hw


# ================================================================================================ RF / ICP
def icp_items():
    p1 = js("P1_BENCH")
    f6 = js("F6_ICP")
    icp = js("ICP_PREREG_V2")
    del icp
    it = {x["id"]: x for x in p1["items"]}
    if it["P1-IT-01"]["value"] != 13.56 or it["P1-IT-02"]["value"] != [0.0, 500.0]:
        raise BuildError("P1 RF items changed")
    st = p1["current_statuses"]
    if st["RF matching architecture"] != "LOCAL_MATCH_SELECTED_FOR_DEVELOPMENT" or \
            st["RF component ratings"] != "TBD_AFTER_IMPEDANCE_MAP":
        raise BuildError("P1 RF statuses changed")
    probe = ptr(f6, "/current_objective_state/probe_vector")
    if probe != {"geometry_id": "F6-STATE-PROBE", "L_standoff": 0.05, "r_aperture": 0.06, "r_module": 0.09,
                 "L_module": 0.15, "tau_support": 0.0}:
        raise BuildError(f"F6 probe {probe}")
    anchors = {a["id"]: a for a in p1["anchor_check"]}
    if "65 mm" not in anchors["TK-10"]["reported_value"] or "10 cm axial length" not in anchors["TK-13"]["reported_value"]:
        raise BuildError("Takahashi anchors changed")
    p1i = lambda i: src("P1_BENCH", f"/items/{[x['id'] for x in p1['items']].index(i)}")  # noqa: E731
    items = [
        item("DBF1-RF-01", "RF", "RF frequency", 13.56, "MHz", [p1i("P1-IT-01"), src("A937_MD")], "owner-fixed",
             "owner-allocation", "OWNER_DECISION", "exact (ISM frequency)", "FROZEN", "A9.37 'Freeze 13.56 MHz RF'"),
        item("DBF1-RF-02", "RF", "RF forward-power operating envelope at the generator / 50-ohm reference plane",
             [0.0, 500.0], "W", [p1i("P1-IT-02"), p1i("P1-IT-04")], "owner allocation (investigation capability)",
             "owner-allocation", "OWNER_DECISION",
             "envelope ends as registered; P_fwd is never P_plasma (A9.2; Takahashi eta_p ~ 0.1, TK-26)",
             "FROZEN_ASSUMPTION",
             "P1-IT-02 investigation capability adopted as the design operating envelope; the flight bus bound is "
             "P_ICP,available = 1350 W - P_common - P_Hall - P_other,active (DBF1-PWR-04)"),
        item("DBF1-RF-03", "RF", "matching architecture", "adjustable local match, on / immediately adjacent to the ICP "
             "module (match_colocated = true)", "-", [p1i("P1-IT-22"), src("P1_BENCH", "/current_statuses")],
             "owner decision", "owner-allocation", "OWNER_DECISION", "categorical", "FROZEN",
             "status LOCAL_MATCH_SELECTED_FOR_DEVELOPMENT (A9.2)"),
        item("DBF1-RF-04", "RF", "RF component ratings (generator, coupler, coax, match, feedthrough)",
             ">= the DBF1-RF-02 envelope upper end (500 W forward)", "W", [p1i("P1-IT-03"), p1i("P1-IT-02")],
             "engineering assumption", "assumed", "7",
             "ratings TBD_AFTER_IMPEDANCE_MAP (P2); RF peak voltage / current not registered (ICD ICP-44)",
             "FROZEN_ASSUMPTION", "rating basis tied to the frozen envelope until the P2 impedance map sets ratings"),
        item("DBF1-ICP-01", "ICP_GEOMETRY", "ICP topology", "open-tube coaxial downstream ICP, unmagnetized, "
             "CFG-CAP-OFF electron extraction topology per P1-IT-36 when registered", "-",
             [p1i("P1-IT-16"), src("P1_BENCH", "/scope")],
             "owner decision", "owner-allocation", "OWNER_DECISION", "categorical", "FROZEN",
             "A9.3 OQ-VI-03 first build (Takahashi et al. 2024 topology precedent)"),
        item("DBF1-ICP-02", "ICP_GEOMETRY", "module geometry vector (L_standoff, r_aperture, r_module, L_module, "
             "tau_support)", {k: v for k, v in probe.items() if k != "geometry_id"}, "m; -",
             [src("F6_ICP", "/current_objective_state/probe_vector")], "engineering assumption", "assumed", "7",
             "a P3 grid point registered as the F6 state probe; F6 search not run (P1 / P2 evidence absent)",
             "FROZEN_ASSUMPTION",
             "the only complete registered flight-module geometry vector; geometrically consistent with RP-1: "
             "r_aperture 60 mm > H-1 channel outer radius 41 mm (plume passage). The Takahashi 65 mm ID tube (TK-10) "
             "is rejected as the flight bore because its 32.5 mm radius is inside the RP-1 channel outer radius"),
        item("DBF1-ICP-03", "ICP_GEOMETRY", "NP-ICP v2 volume model", "ASSUMED_GEOMETRIC_TUBE (V = pi R^2 L with "
             "R = r_aperture 0.06 m, L = L_module 0.15 m)", "-",
             [src("ICP_PREREG_V2"), src("ICP_LOCK_V2"), src("F6_ICP", "/current_objective_state/probe_vector")],
             "declared unvalidated modelling assumption", "assumed", "7",
             "A9.31 sec. 10: not bench validation; a REGISTERED_EFFECTIVE volume supersedes it", "FROZEN_ASSUMPTION",
             "every NP-ICP v2 output at DBF-1 carries flag ASSUMED_GEOMETRIC_TUBE"),
        item("DBF1-ICP-04", "ICP_GEOMETRY", "ion-collecting electrode (collector)", "C-type electrode on the inner wall "
             "of the bore, 0.10 m axial length, axial slit for RF penetration; separately biased and metered, ICP body "
             "floating", "m",
             [src("P1_BENCH", "/anchor_check/%d" % [a["id"] for a in p1["anchor_check"]].index("TK-13")),
              p1i("P1-IT-17")],
             "literature topology precedent", "as-reported", "3",
             "anchor axial length as reported (Takahashi Fig. 1b); the flight collector (ICD ICP-21) is TBD",
             "FROZEN_ASSUMPTION",
             "the registered topology anchor; within L_module 0.15 m the collector covers 0.10 m of the bore wall and "
             "the dielectric vessel the remaining 0.05 m"),
        item("DBF1-ICP-05", "ICP_GEOMETRY", "ICP neutral source / gas routing", "G-REUSE (Hall exhaust -> ICP; "
             "mdot_ICP,dedicated = 0); capped dedicated port retained; declared variant G-XE", "-",
             [p1i("P1-IT-12"), p1i("P1-IT-13")], "owner decision", "owner-allocation", "OWNER_DECISION",
             "categorical", "FROZEN", "A9.1 HIQ-06 icp_feed_gas_baseline G-REUSE (config/architecture icp_feed_gas_baseline)"),
        item("DBF1-ICP-06", "ICP_GEOMETRY", "ICP body / collector isolation class", 350.0, "V",
             [p1i("P1-IT-21"), p1i("P1-IT-43")], "owner decision", "owner-allocation", "OWNER_DECISION",
             "design withstand >= 525 V (P1-IT-43)", "FROZEN", "A9.4 P1Q-14 ICP_350V_CLASS"),
        item("DBF1-ICP-07", "ICP_GEOMETRY", "dielectric bore (vessel) material", "borosilicate glass (pyrex class)",
             "-", [src("P1_BENCH", "/anchor_check/%d" % [a["id"] for a in p1["anchor_check"]].index("TK-10"))],
             "literature topology precedent", "as-reported", "3",
             "flight dielectric not selected (P3-R-03 emittance TBD); AO / sputter compatibility not evidenced",
             "FROZEN_ASSUMPTION", "the only registered ICP bore material (Takahashi anchor TK-10)"),
    ]
    return items, probe


# ================================================================================================ intake / compressor
def f7_members():
    gz = read_pinned("F7_PARETO")
    raw = gzip.decompress(gz)
    if sha_bytes(raw) != F7_JSON_SHA256:
        raise BuildError("F7 pareto json sha256 differs from the pinned decompressed sha256")
    return json.loads(raw)


def intake_items():
    pareto = f7_members()
    a5 = js("A5_RECORD")
    adm = ptr(a5, "/summary/design_identification/DS-F1-ADMISSIBLE/candidates_by_scenario")
    scenarios = ptr(a5, "/summary/design_identification/DS-F1-GRID/scenarios")
    by: dict = collections.defaultdict(dict)
    n_all = 0
    for ctx, blocks in pareto.items():
        sc = ctx.split("|")[0]
        for b in blocks:
            for m in b["block"]["members"]:
                n_all += 1
                if m["context_role"] != "ARCHITECTURE_CONTEXT":
                    continue                       # FC00 contexts are reference bounds, never flight (A9.13 S6.5)
                if m["candidate"] not in adm[sc]:
                    continue                       # C-DRAG-RFP / C-CONV generation filter (DS-F1-ADMISSIBLE)
                by[m["design_id"]][sc] = m
    rows = []
    for k, v in by.items():
        rows.append({"design_id": k, "n_scenarios": len(v),
                     "worst_mdot": min(m["mdot_delivered_min_kgps"] for m in v.values()),
                     "p_comp_max": max(m["P_compressor_el_max_W"] for m in v.values()),
                     "m_comp_max": max(m["m_compressor_max_kg"] for m in v.values())})
    rows.sort(key=lambda r: (-r["n_scenarios"], -r["worst_mdot"], r["p_comp_max"], r["m_comp_max"], r["design_id"]))
    sel = rows[0]
    if rows[1]["n_scenarios"] == sel["n_scenarios"] and rows[1]["worst_mdot"] == sel["worst_mdot"]:
        raise BuildError("selection tie on the primary keys (tie-break rule reached)")
    sid = sel["design_id"]
    ms = by[sid]
    cand, filt, comp, vtag, ptag = sid.split("|")
    f3 = js("F3_DESIGNS")
    grid = {d["id"]: d for d in f3["design_grid"]}
    cd = grid[comp]
    idx_c = [d["id"] for d in f3["design_grid"]].index(comp)
    geo = {"area_m2": float(cand.split("_")[0][1:]), "L_over_d": float(cand.split("_")[1][2:]),
           "phi": float(cand.split("_")[2][3:])}
    twin = sid.replace(filt, "F4-FIL-NONE")
    f8 = ptr(a5, "/f8_survivors_carried_unchanged")
    if twin not in f8:
        raise BuildError(f"no F8 record of the FC00 twin {twin}")
    infeasible = f8[twin]["infeasible_in"]
    covered = sorted(ms)
    uncovered = [s for s in scenarios if s not in ms]
    if sorted(uncovered) != sorted(infeasible):
        raise BuildError(f"uncovered scenarios {uncovered} differ from the FC00 twin's F8 infeasibility {infeasible}")
    worst_sc = min(ms, key=lambda s: ms[s]["mdot_delivered_min_kgps"])
    best_sc = max(ms, key=lambda s: ms[s]["mdot_delivered_min_kgps"])
    drag_max = max(m["drag_intake_max_N"] for m in ms.values())
    cf = ptr(a5, "/summary/a9_35/carry_forward")
    k_t12 = cf["mdot_req_T12_kg_s"] / sel["worst_mdot"]
    k_t25 = cf["mdot_req_T25_kg_s"] / sel["worst_mdot"]
    k_area = cf["A_req_T12_m2"] / geo["area_m2"]
    pareto_src = src("F7_PARETO", None, f"decompressed json sha256 {F7_JSON_SHA256}; contexts {', '.join(covered)}")
    per_sc = {s: {"mdot_delivered_min_kg_s": ms[s]["mdot_delivered_min_kgps"],
                  "mdot_captured_min_kg_s": ms[s]["mdot_captured_min_kgps"],
                  "P_compressor_el_max_W": ms[s]["P_compressor_el_max_W"],
                  "drag_intake_max_N": ms[s]["drag_intake_max_N"],
                  "m_compressor_max_kg": ms[s]["m_compressor_max_kg"],
                  "xO_flow_min": ms[s]["xO_flow_min"], "xO_flow_max": ms[s]["xO_flow_max"]} for s in covered}
    rule = {
        "id": "SR-INTAKE-01",
        "pool": "DS-F7-PARETO members (admitted F7 Pareto blocks, f7_pareto_blocks_v1) with context_role "
                "ARCHITECTURE_CONTEXT (an actual filter element; FC00 contexts are reference bounds only, A9.13 S6.5) "
                "whose F1 intake candidate is in DS-F1-ADMISSIBLE for that context's surface scenario (FEASIBLE_AT_STATE "
                "at every required state under F1 C-CONV and the intake-face drag filter C-DRAG-RFP <= 25 mN)",
        "unit": "a design vector (intake candidate, filter case, compressor, plenum V, P_set); its admitted F7 Pareto "
                "memberships across surface scenarios",
        "keys_in_order": [
            "1. maximise n_s = the number of admitted surface scenarios in which the design vector is an F7 Pareto "
            "member (scenario robustness first: A9.13 S6.16, no favourable surface scenario is chosen)",
            "2. maximise the worst-state delivered flow in its worst covered scenario: min over covered scenarios of "
            "the committed statewise-minimum mdot_delivered_min_kgps",
            "3. tie-break: minimise the maximum compressor electrical power P_compressor_el_max_W",
            "4. tie-break: minimise the compressor mass m_compressor_max_kg",
            "5. tie-break: lexicographic design_id",
        ],
        "not_used": "mass, Hall performance and M2 results are not selection keys (A9.37: select by flow and drag; "
                    "mass is assessed against the frozen policy and its shortfall recorded as a deficiency)",
        "executed_by": BUILDER,
        "n_pareto_member_records": n_all,
        "n_design_vectors_in_pool": len(rows),
        "top_5": [{k: r[k] for k in ("design_id", "n_scenarios", "worst_mdot", "p_comp_max", "m_comp_max")}
                  for r in rows[:5]],
        "selected": sid,
    }
    a5i = src("A5_RECORD", "/summary/a9_35/carry_forward")
    items = [
        item("DBF1-IN-01", "INTAKE_COMPRESSOR", "upstream design vector (intake, filter, compressor, plenum, P_set)",
             sid, "-", [pareto_src, src("A5_RECORD", "/summary/design_identification")],
             "model-derived (F7 chain, PARAMETRIC_SENSITIVITY inputs)", "model-derived", "6",
             "compressor coefficients code-default (PARAMETRIC_SENSITIVITY); surface accommodation TBD (10-scenario "
             "set); see DBF1-BD-01 / BD-02", "BASELINE_DEFICIENCY",
             "selected by SR-INTAKE-01 on registered candidates; no registered candidate closes both flow and drag "
             "(A9.37: frozen anyway, deficiency recorded)", selection_rule_ref="SR-INTAKE-01",
             deficiencies=["DBF1-BD-01", "DBF1-BD-02", "DBF1-BD-03"]),
        item("DBF1-IN-02", "INTAKE_COMPRESSOR", "intake geometry (F1 candidate, d collapsed)",
             dict(geo, candidate=cand, channel_diameter="collapsed: every TPMC output is d-invariant at fixed L/d (F1-02); "
                  "d is set with the mechanical design inside the F1 grid", intake_wall_area_m2=ms[covered[0]].get(
                      "intake_wall_area_m2")),
             "m^2; -; -", [src("A5_RECORD", "/summary/design_identification/DS-F1-GRID"), src("F1_CORE")],
             "model-derived (F1 TPMC synthesis)", "model-derived", "6", "TPMC statistical SE per state (F1); surface "
             "scenario TBD", "FROZEN_ASSUMPTION", "A = 0.25 m^2 is the only F1 area passing C-DRAG-RFP at every "
             "required state in every scenario (DS-F1-ADMISSIBLE)"),
        item("DBF1-IN-03", "INTAKE_COMPRESSOR", "TPMC surface-scenario basis", scenarios, "-",
             [src("A5_RECORD", "/summary/design_identification/DS-F1-GRID/scenarios"), src("A913_MD")],
             "model-derived scenario set", "model-derived", "6",
             "accommodation unmeasured (DI-1.3); every admitted scenario is carried, none chosen (A9.13 S6.16)",
             "FROZEN_ASSUMPTION", "Maxwell and CLL, alpha in {0, 0.2, 0.5, 0.8, 1}; narrowing only by a "
                                  "preregistered DI-1.3 record"),
        item("DBF1-IN-04", "INTAKE_COMPRESSOR", "filter case", filt, "-", [pareto_src],
             "parametric sensitivity (loss-free species-independent screen, tau = 0.9)", "assumed", "7",
             "filter material / geometry undefined (F2-IF-08); tau 0.7 / 0.5 and the placeholder law are the registered "
             "alternatives", "FROZEN_ASSUMPTION", "selected with the design vector (SR-INTAKE-01 key 2); "
                                                  "baseline role INERT_LOW_RECOMBINATION (A9.13 S6.3)"),
        item("DBF1-IN-05", "INTAKE_COMPRESSOR", "compressor design (F3 design grid)", cd, "-; m^2; m; m/s; rpm",
             [src("F3_DESIGNS", f"/design_grid/{idx_c}")], "model-derived (F3)", "model-derived", "6",
             "turbo-row coefficients code-default (T-1 / T-2 open); hub geometry PARAMETRIC_SENSITIVITY",
             "BASELINE_DEFICIENCY", "selected with the design vector; F3 model mass exceeds the AL-02 line "
                                    "allocation (DBF1-BD-03)", deficiencies=["DBF1-BD-03"]),
        item("DBF1-IN-06", "INTAKE_COMPRESSOR", "plenum volume / wall / target pressure",
             {"V_m3": float(vtag[1:]), "wall_case": "WALL-G0", "P_set_Pa": float(ptag[1:])}, "m^3; -; Pa",
             [pareto_src], "parametric design value", "assumed", "7",
             "V from the F4 decade grid; WALL-G0 = inert lining bound (gamma = 0, owner H1F-IN-02)",
             "FROZEN_ASSUMPTION", "selected with the design vector (SR-INTAKE-01)"),
        item("DBF1-IN-07", "INTAKE_COMPRESSOR", "feed-loop controller (normalized PI on plenum pressure)",
             {"Kp": 0.3, "Ti_s": 3.0, "f_valve_hz": 1.0, "authority": 3.0}, "-; s; Hz; -",
             [src("F4_FEED", "/search_variables"), src("F4_BUILD", None, "KP / TI_S / F_VALVE_NOMINAL_HZ / AUTHORITY")],
             "definition / parametric", "assumed", "7",
             "Kp, Ti one-decade definition grid; f_valve, authority PARAMETRIC_SENSITIVITY (H2-3 H23-18 / H23-07)",
             "FROZEN_ASSUMPTION",
             "selection rule SR-CTRL-01: the lowest registered proportional gain and the slowest registered integral "
             "time (Kp 0.3, Ti 3 s), nominal valve bandwidth 1 Hz and authority 3 (the only registered values); the "
             "low-gain choice is made before any stability evaluation and is not revisited after it (DCR only)"),
        item("DBF1-IN-08", "INTAKE_COMPRESSOR", "registered F7 performance of the frozen design (per covered scenario)",
             per_sc, "kg/s; W; N; kg; -", [pareto_src], "model-derived", "model-derived", "6",
             "PARAMETRIC_SENSITIVITY", "FROZEN", "registered values; M2 re-evaluates the design in every admitted "
                                                "scenario at every state"),
    ]
    deficiencies = [
        {"id": "DBF1-BD-01", "items": ["DBF1-IN-01"], "closure_condition": "flow (A9.35 / A4 carry-forward): worst-state "
         "12 mN needs >= 0.251 m^2 effective collection area and >= 0.048 mg/s at the ideal 1.5 kW limit",
         "numbers": {"worst_state": cf["worst_state"], "A_req_T12_m2": cf["A_req_T12_m2"],
                     "A_eff_m2": geo["area_m2"], "k_area_T12": k_area,
                     "mdot_req_T12_kg_s": cf["mdot_req_T12_kg_s"], "mdot_req_T25_kg_s": cf["mdot_req_T25_kg_s"],
                     "mdot_delivered_worst_state_worst_covered_scenario_kg_s": sel["worst_mdot"],
                     "worst_covered_scenario": worst_sc,
                     "mdot_delivered_worst_state_best_covered_scenario_kg_s":
                         ms[best_sc]["mdot_delivered_min_kgps"], "best_covered_scenario": best_sc,
                     "k_del_T12 (required / delivered)": k_t12, "k_del_T25": k_t25},
         "drag": {"C-DRAG-RFP intake-face drag limit_mN": 25.0, "drag_intake_max_mN": drag_max * 1e3,
                  "status": "MET (generation filter)"},
         "finding": f"drag closes (intake-face drag <= {drag_max * 1e3:.4g} mN <= 25 mN) but flow does not: the "
                    f"frozen design delivers {sel['worst_mdot']:.4g} kg/s at its worst state in its worst covered "
                    f"scenario, {k_t12:.4g} x below the 12 mN necessary flow; A_eff 0.25 m^2 < A_req 0.2511 m^2",
         "category": "DESIGN_VARIABLE_LIMIT (A9.35: A4-REG-01 open, no registered envelope bound)",
         "sources": [a5i, pareto_src]},
        {"id": "DBF1-BD-02", "items": ["DBF1-IN-01"], "closure_condition": "robust feasibility in every admitted surface "
         "scenario (A2 NH-FLOW; A9.13 S6.16)",
         "numbers": {"covered_scenarios": covered, "not_covered": uncovered,
                     "fc00_twin": twin, "fc00_twin_f8_infeasible_in": infeasible,
                     "fc00_twin_reasons": {s: f8[twin]["per_scenario"][s].get("reasons") for s in infeasible},
                     "F8_robust_set": "EMPTY"},
         "finding": f"the design is an F7 Pareto member in {len(covered)} of {len(scenarios)} admitted scenarios; its "
                    "FC00 twin is infeasible in the other four (compressor characteristic / dead-head); no registered "
                    "candidate is robust (F8 robust set EMPTY)",
         "category": "DESIGN_VARIABLE_LIMIT", "sources": [src("A5_RECORD", "/f8_survivors_carried_unchanged")]},
    ]
    mp = js("MP_V5")
    al02 = [x for x in mp["lines"]["hall_icp_neutralizer"] if x["line"] == "AL-02"][0]
    deficiencies.append(
        {"id": "DBF1-BD-03", "items": ["DBF1-IN-05"], "closure_condition": "compressor + drive within its line "
         "allocation (AL-02, row 54)", "numbers": {"m_compressor_model_kg": sel["m_comp_max"],
                                                  "AL02_allocation_kg": al02["row54_allocation_kg"],
                                                  "excess_kg": sel["m_comp_max"] - al02["row54_allocation_kg"]},
         "finding": "the F3 model mass of the selected compressor exceeds the AL-02 allocation; the registered "
                    "candidates within 5.5 kg (T4 compressors) cover 2 scenarios at ~5x lower delivered flow",
         "category": "DESIGN_VARIABLE_LIMIT", "sources": [pareto_src, src("MP_V5", "/lines/hall_icp_neutralizer")]})
    cfg = {"design_id": sid, "candidate": cand, "area_m2": geo["area_m2"], "L_over_d": geo["L_over_d"],
           "phi": geo["phi"], "filter": filt, "compressor": comp, "V_m3": float(vtag[1:]), "P_set_Pa": float(ptag[1:]),
           "wall": "WALL-G0", "scenarios": scenarios,
           "controller": {"Kp": 0.3, "Ti_s": 3.0, "f_valve_hz": 1.0, "authority": 3.0}}
    return items, deficiencies, rule, cfg


# ================================================================================================ power / mass
def power_mass_items():
    mp = js("MP_V5")
    al = ptr(mp, "/power/allocations")
    if al["design_allocation_W"]["value"] != 1350.0 or al["common_allocation_W"]["value"] != 300.0:
        raise BuildError("mass_power_a9_v5 power allocations changed")
    if ptr(mp, "/power/boundary_version") != "bus_power_boundary_a9_v2":
        raise BuildError("boundary version")
    slots = ptr(mp, "/power/configurations/hall_icp_neutralizer/slots")
    groups = collections.OrderedDict()
    for s in slots:
        groups.setdefault(s["group"], []).append(s["slot"])
    gates = js("GATES")
    cons = js("CONSTRAINTS")
    if ptr(cons, "/constraints/p_bus_max_W/value") != 1500:
        raise BuildError("p_bus_max_W")
    pdt = ptr(mp, "/proposal_design_target")
    if (pdt["nominal_dry_max_kg"], pdt["system_margin_fraction"], pdt["xe_reference_case_kg"]) != (34.0, 0.1, 2.0):
        raise BuildError("proposal design target changed")
    roll = ptr(mp, "/flight_rollup_vs_40kg/0")
    del gates
    items = [
        item("DBF1-PWR-01", "POWER", "design power allocation (all flight loads at the spacecraft-side DC boundary)",
             1350.0, "W", [src("MP_V5", "/power/allocations/design_allocation_W"), src("A937_MD")], "owner-fixed",
             "owner-allocation", "OWNER_DECISION", "allocation (not a gate, not a CBE)", "FROZEN",
             "A9.37; row 109: the ICP fits inside it; the 1350 -> 1500 W margin is not consumed nominally"),
        item("DBF1-PWR-02", "POWER", "RFP bus-power gate (assessment only)", 1500.0, "W",
             [src("CONSTRAINTS", "/constraints/p_bus_max_W"), src("GATES"), src("A937_MD")], "frozen requirement",
             "owner-allocation", "OWNER_DECISION",
             "strict '<' on P_bus,1ms,max (bus_power_boundary_a9_v2 gate)", "FROZEN",
             "A9.37; read by the harness only through abep-config (HC-03 assessment threshold); never a physics input "
             "(A9.30)"),
        item("DBF1-PWR-03", "POWER", "common-load allocation (compressor + flow control + filter/getter + thermal "
             "control + housekeeping)", 300.0, "W", [src("MP_V5", "/power/allocations/common_allocation_W"),
                                                     src("A937_MD")],
             "owner-fixed", "owner-allocation", "OWNER_DECISION", "upper design value (row 114); controls / thermal "
             "allowance 50 W inside it", "FROZEN", "A9.37 current 300 W common-load allocation"),
        item("DBF1-PWR-04", "POWER", "mapping to bus_power_boundary_a9_v2", {
            "boundary": "bus_power_boundary_a9_v2 (flight configuration hall_icp_neutralizer; flight C1 loads NONE)",
            "slots_by_group": groups,
            "HALL_AND_ELECTRON_SOURCE": "hall group + icp group inside 1350 W - P_common - P_other,active (no fixed "
                                        "Hall / ICP split, A9.1 OQ-A902-03); 1050 W at P_common = 300 W, P_other = 0",
            "COMMON_300W": "common group <= 300 W",
            "OTHER_ACTIVE": "reserved_dc_port, 0 W while unused",
            "gate": "P_bus,1ms,max < 1500 W (assessment only)"}, "-",
            [src("MP_V5", "/power/configurations/hall_icp_neutralizer/slots"),
             src("MP_V5", "/power/allocations"), src("BUS_A9_V2")], "owner allocation arithmetic", "owner-allocation",
            "OWNER_DECISION", "exact arithmetic on owner allocations", "FROZEN", "A9.30 bus boundary; no C1 slot"),
        item("DBF1-MASS-01", "MASS", "system mass-margin policy", 0.10, "fraction of nominal dry",
             [src("A926_JSON"), src("MP_V5", "/proposal_design_target/system_margin_fraction")], "owner-fixed",
             "owner-allocation", "OWNER_DECISION", "policy", "FROZEN",
             "A9.26 (20 % kept as historical / conservative sensitivity); 20 % line uplift on AL-04 / AL-07 / AL-08 kept"),
        item("DBF1-MASS-02", "MASS", "nominal-dry mass target", 34.0, "kg (<=)",
             [src("MP_V5", "/proposal_design_target/nominal_dry_max_kg"), src("A937_MD")], "owner-fixed design target",
             "owner-allocation", "OWNER_DECISION", "design target, not achieved evidence", "FROZEN",
             "A9.37 / A9.26 section 5 proposal design target", deficiencies=["DBF1-BD-04"]),
        item("DBF1-MASS-03", "MASS", "reference Xe load", 2.0, "kg",
             [src("MP_V5", "/proposal_design_target/xe_reference_case_kg"), src("A937_MD")], "owner-fixed reference",
             "owner-allocation", "OWNER_DECISION", "planning / reference case; 5 / 10 kg sensitivities carried; not the "
                                                   "selected flight Xe load", "FROZEN",
             "A9.37 '2 kg reference Xe load'; never selected to force mass closure (A9.31 sec. 18 Q6)"),
        item("DBF1-MASS-04", "MASS", "wet-mass target at the reference Xe load (arithmetic)", pdt["wet_target_at_reference_kg"],
             "kg", [src("MP_V5", "/proposal_design_target")], "arithmetic on owner values", "owner-allocation",
             "OWNER_DECISION", "34 x 1.10 + 2 = 39.4 kg", "FROZEN", "below the 40 kg RFP wet-mass limit by 0.6 kg"),
    ]
    deficiencies = [
        {"id": "DBF1-BD-04", "items": ["DBF1-MASS-02"], "closure_condition": "nominal dry <= 34.0 kg; wet < 40 kg at the "
         "2 kg reference Xe load", "numbers": {"nominal_dry_planning_kg": roll["nominal_dry_known_kg"],
                                                 "dry_planning_kg": roll["dry_known_kg"],
                                                 "wet_planning_kg_at_2kg": roll["wet_known_kg_by_loaded_case"]["2.0"],
                                                 "nominal_dry_excess_kg": roll["nominal_dry_known_kg"] - 34.0},
         "finding": "the current provisional planning roll-up (owner MEV lines + evidence floors; not a CBE) is above the "
                    "34 kg nominal-dry target and the 40 kg wet limit at 2 kg Xe (MASS INCOMPLETE_EVIDENCE / "
                    "NOT_YET_CLOSED); planning values are never eligible for a non-closure (HR-07)",
         "category": "MISSING_EVIDENCE (no CBE) / DESIGN_VARIABLE_LIMIT (mass-closure actions MCA)",
         "sources": [src("MP_V5", "/flight_rollup_vs_40kg/0"), src("MP_V5", "/closure_vs_40kg/0")]}]
    cfg = {"design_allocation_W": 1350.0, "common_allocation_W": 300.0, "rfp_gate_source": "abep-config HC-03",
           "mass_margin_fraction": 0.1, "nominal_dry_target_kg": 34.0, "xe_reference_load_kg": 2.0,
           "wet_target_at_reference_kg": pdt["wet_target_at_reference_kg"],
           "planning_rollup": {"nominal_dry_kg": roll["nominal_dry_known_kg"], "dry_kg": roll["dry_known_kg"],
                               "wet_kg_at_2kg": roll["wet_known_kg_by_loaded_case"]["2.0"]},
           "slots_by_group": groups}
    return items, deficiencies, cfg


# ================================================================================================ thermal
def thermal_items():
    t1 = js("THERMAL_PREREG_V1")
    js("THERMAL_PREREG_V2")
    js("THERMAL_LOCK_V2")
    js("H25")
    solved = [n["id"] for n in t1["nodes"]["solved"]]
    bounds = [n["id"] for n in t1["nodes"]["boundaries"]]
    want = ["H1_ANODE", "H1_WALL_IN", "H1_WALL_OUT", "H1_POLE_IN", "H1_POLE_OUT", "H1_BACKPLATE", "H1_COIL_IN",
            "H1_COIL_OUT", "H1_COIL_TRIM", "N_VESSEL", "N_ANTENNA", "N_COLLECTOR", "N_HOUSING", "N_MATCH", "N_MOUNT",
            "R_HALL", "R_ICP"]
    if solved != want:
        raise BuildError(f"thermal v1 node set changed: {solved}")
    present = [n for n in want if n != "R_ICP"]
    conditional = {
        "H1_COIL_TRIM": "PRESENT: H1F-MC-02 trim-coil provision (winding space + reserved supply channel); bus slot "
                        "hall_magnet_trim installed",
        "N_COLLECTOR": "PRESENT: Takahashi-type collector frozen (DBF1-ICP-04)",
        "N_HOUSING": "PRESENT: module housing / RF shield / feedthrough body of the frozen module envelope r_module "
                     "0.09 m (DBF1-ICP-02)",
        "N_MATCH": "PRESENT: match_colocated = true (DBF1-RF-03)",
        "R_HALL": "PRESENT: A9.12 OQ-A907-06 thermally isolated H-1 mount + dedicated radiator / rejection path",
        "R_ICP": "ABSENT: the ICP outward surfaces belong to N_HOUSING / N_VESSEL (no separate ICP radiator registered)",
    }
    items = [
        item("DBF1-TH-01", "THERMAL", "thermal network topology (NP-THERMAL-CATHODELESS 2.0.0)",
             {"solved_nodes": present, "absent_conditional_nodes": ["R_ICP"], "boundaries": bounds,
              "conditional_node_dispositions": conditional,
              "excluded": "C-1 nodes CB / CE / CK (AFI-03; no cathode node)"}, "-",
             [src("THERMAL_PREREG_V1", "/nodes"), src("THERMAL_PREREG_V2"), src("THERMAL_LOCK_V2"), src("H25")],
             "registered model topology", "model-derived", "6",
             "lumped isothermal nodes (Biot check D-02); property / conductance / view-factor records TBD",
             "FROZEN_ASSUMPTION", "the v1 node set inherited by 2.0.0, with the conditional nodes decided by the "
                                  "frozen H-1 / ICP design"),
        item("DBF1-TH-02", "THERMAL", "spacecraft interface form", "SCI-A conductance to a fixed spacecraft temperature "
             "at H1_BACKPLATE (isolated mount), N_MOUNT and R_HALL; values from the host thermal ICD", "-",
             [src("THERMAL_PREREG_V1", "/spacecraft_interface")], "reference pending ICD", "assumed", "7",
             "G_sc,a and T_sc not registered (OQ-NPT-01 open; no spacecraft thermal ICD)", "REFERENCE_PENDING_ICD",
             "the conductance form is the one the owner mount cases would use; FLIGHT_CONDITIONAL thermal stays "
             "NOT_EVALUATED until the ICD values exist"),
        item("DBF1-TH-03", "THERMAL", "thermal design margin rule", {"margin_K": 50.0, "heat_load_factor": 1.2},
             "K; -", [src("H1F", "/parameters/62")], "owner decision", "owner-allocation", "OWNER_DECISION",
             "rule", "FROZEN", "owner row 86 (H1F-TH-01): >= 50 K below each validated continuous-use limit + 20 % "
                               "heat-load margin (HC-06 in the assessment config)"),
    ]
    return items


# ================================================================================================ materials
def material_items():
    p4 = js("P4_MATERIALS")
    if p4["fixed_statuses"]["316L_FLIGHT_ANODE"]["status"] != "REJECTED_AS_CURRENT_BASELINE":
        raise BuildError("316L status changed")
    cov = p4["evidence_coverage"]
    pool = []
    for i, c in enumerate(p4["candidates"]):
        q0 = c["q0_disposition"]
        bulk = "coating" not in c["family"]
        if q0["role"] != "CANDIDATE" or not bulk or not c.get("r8_coupon_id"):
            continue
        pool.append({"idx": i, "id": c["id"], "name": c["name"], "family": c["family"],
                     "r8_role": c["r8_coupon_role"], "r8_status": c["r8_matrix_status_research_only"],
                     "n_props": len(cov.get(c["id"], {}).get("datasheet_properties_populated", []))})
    # SR-MAT-01: insulating-scale hypothesis-control families rank after the others (electron / ion collection)
    rank = lambda r: (-r["n_props"], r["r8_status"].startswith("test only as hypothesis-control"), r["id"])  # noqa
    pool.sort(key=rank)
    primary = pool[0]
    backup = [r for r in pool if r["family"] != primary["family"]][0]
    rule = {
        "id": "SR-MAT-01",
        "pool": "P4 candidate register (p4_anode_materials_v1 candidates) with Q0-matrix role CANDIDATE, a bulk "
                "(uncoated) material and an assigned R8 coupon; 316L excluded (REJECTED_AS_CURRENT_BASELINE for the "
                "flight anode; Q0 role ENGINEERING_REFERENCE_CONTROL_ONLY); reference / negative controls, reserve "
                "and non-Q0 entries excluded; coatings excluded (coating thickness / record TBD)",
        "keys_in_order": [
            "1. maximise the number of populated datasheet properties (P4 evidence_coverage)",
            "2. a family whose R8 status is 'test only as hypothesis-control' (alumina formers: possible insulating "
            "scale on an electron- / ion-collecting electrode) ranks after the others",
            "3. lexicographic candidate id",
            "backup: the highest-ranked candidate of a different oxide-former family than the primary (common-mode "
            "independence)"],
        "pool_ranked": [{k: r[k] for k in ("id", "name", "family", "n_props", "r8_status")} for r in pool],
        "primary": primary["id"], "backup": backup["id"],
        "applies_to": ["APP-ANODE (H-1 anode / gas distributor)", "APP-COLLECTOR (ICP ion-collecting electrode, ICD "
                                                                   "ICP-21)"],
    }
    gate = "every P4 gate cell INCOMPLETE_EVIDENCE (no gate-admissible property; no plasma / O exposure evidence)"
    msrc = lambda r: src("P4_MATERIALS", f"/candidates/{r['idx']}")  # noqa: E731
    h1 = js("H1F")
    expect(h1, "/parameters/58/id", "H1F-MA-05", "wall grade item")
    env = js("ENV_PREREG")
    if "WallSheath(BNSiO2" not in ptr(env, "/numerical_settings/wall_and_ions"):
        raise BuildError("envelope wall material changed")
    items = [
        item("DBF1-MAT-01", "MATERIALS", "H-1 anode / gas distributor material (primary)", primary["name"], "-",
             [msrc(primary), src("P4_MATERIALS", "/a9_16_owner_rules/q0_matrix")], "datasheet bulk properties only",
             "as-reported", "5", gate, "FROZEN_ASSUMPTION",
             f"SR-MAT-01 primary ({primary['family']}; R8 role '{primary['r8_role']}')"),
        item("DBF1-MAT-02", "MATERIALS", "H-1 anode / gas distributor material (backup)", backup["name"], "-",
             [msrc(backup)], "datasheet bulk properties only", "as-reported", "5", gate, "FROZEN_ASSUMPTION",
             f"SR-MAT-01 backup (different family: {backup['family']}; alumina scale may insulate: Q0 hypothesis-control "
             "coupon decides)"),
        item("DBF1-MAT-03", "MATERIALS", "ICP ion-collecting electrode material (primary / backup)",
             {"primary": primary["name"], "backup": backup["name"]}, "-",
             [msrc(primary), msrc(backup), src("P4_MATERIALS", "/applications/APP-COLLECTOR"),
              src("P1_BENCH", "/items/%d" % [x["id"] for x in js("P1_BENCH")["items"]].index("P1-IT-19"))],
             "datasheet bulk properties only", "as-reported", "5",
             gate + "; 316L permitted only for the Ar engineering reproduction (P1-IT-19)", "FROZEN_ASSUMPTION",
             "SR-MAT-01 applied to APP-COLLECTOR (same register; sputtering / deposition under negative bias, TK-71)"),
        item("DBF1-MAT-04", "MATERIALS", "H-1 channel wall ceramic (primary / backup)",
             {"primary": "BN-SiO2 (borosil class)", "backup": "BN"}, "-",
             [src("H1F", "/parameters/58"), src("ENV_PREREG", "/numerical_settings/wall_and_ions")],
             "flight practice (literature) / model setting", "as-reported", "5",
             "no N+/N2+/O+/O2+ sputter yield on BN or BN-SiO2 in open sources; BN inner wall thermal UNRESOLVED against "
             "the 850 degC ceiling", "FROZEN_ASSUMPTION",
             "H1F-MA-05 flight practice is BN or BN-SiO2; BN-SiO2 primary because the envelope runs use WallSheath "
             "(BNSiO2) (one consistent wall model), BN backup"),
    ]
    return items, rule, {"anode_primary": primary["id"], "anode_backup": backup["id"],
                         "collector_primary": primary["id"], "collector_backup": backup["id"],
                         "anode_primary_name": primary["name"], "wall_primary": "BN-SiO2", "wall_backup": "BN"}


# ================================================================================================ host drag
def drag_items(intake_cfg):
    rec = js("DRAG_RECORD")
    reg = js("DRAG_REGISTER")
    del reg
    records = {r["id"]: r for r in rec["records"]}
    band = (180.0, 230.0)
    pool = []
    for i, c in enumerate(rec["cases"]):
        r = records[c["record_id"]]
        if c["a_ref_scope"] == "includes_intake":
            continue                                   # SRD-04: the DBF-1 intake term is added separately
        alt = r["altitude_km"]["value"]
        lo, hi = (alt, alt) if isinstance(alt, (int, float)) else (min(alt), max(alt))
        pw = (r.get("power_kW") or {}).get("value")
        pwr = None if pw is None else (pw if isinstance(pw, (int, float)) else max(pw))
        app_alt = hi >= band[0] and lo <= band[1]
        app_pwr = pwr is not None and pwr <= 1.5
        pool.append({"idx": i, "case_id": c["case_id"], "record_id": c["record_id"], "cd": c["cd"],
                     "a_ref_m2": c["a_ref_m2"], "cd_a_m2": c["cd"] * c["a_ref_m2"], "alt_km": alt, "power_kW": pw,
                     "applicable_altitude": app_alt, "applicable_power_class": app_pwr})
    app = [p for p in pool if p["applicable_altitude"] and p["applicable_power_class"]]
    app.sort(key=lambda p: (-p["cd_a_m2"], p["case_id"]))
    sel = app[0]
    r = records[sel["record_id"]]
    rule = {
        "id": "SR-DRAG-01",
        "pool": "the declared reference drag cases of spacecraft_reference_drag_v1 (register "
                "crates/abep-mission/data/spacecraft_reference_register_v1.json) whose reference area does not already "
                "include the intake (SRD-04: the DBF-1 intake-face drag is a separate term)",
        "keys_in_order": [
            "1. applicability: the source spacecraft's altitude range overlaps 180-230 km AND its stated propulsion "
            "power class is <= 1.5 kW (cases without a stated power are not applicable)",
            "2. among applicable cases the largest C_D A_ref (conservative: the frozen reference never favours T - D)",
            "3. lexicographic case id"],
        "candidates": pool, "applicable": [p["case_id"] for p in app], "selected": sel["case_id"],
        "sensitivity": "every pool case is reported by M2 as a drag sensitivity (SRD-03: no case is representative); "
                       "the classification uses the frozen case only",
    }
    items = [
        item("DBF1-DRAG-01", "HOST_DRAG", "reference host-spacecraft body (drag case)",
             {"case_id": sel["case_id"], "record_id": sel["record_id"], "a_ref_m2": sel["a_ref_m2"], "cd": sel["cd"],
              "cd_a_m2": sel["cd_a_m2"], "shape": "not stated by the source (body frontal area only)",
              "source_spacecraft": {"altitude_km": sel["alt_km"], "power_kW": sel["power_kW"],
                                    "mass_kg": r["mass_kg"]["value"]}}, "m^2; -",
             [src("DRAG_RECORD", f"/cases/{sel['idx']}"), src("DRAG_RECORD", "/records"), src("DRAG_REGISTER")],
             "reference pending customer ICD (secondary literature)", "as-reported", "5",
             "C_D as reported (secondary; GSI / accommodation basis not stated); SRD-03 spread C_D A 0.32-3.7 m^2 across "
             "declared cases; A_ref scope 'unstated' -> INTAKE_OVERLAP_UNRESOLVED flag", "REFERENCE_PENDING_ICD",
             "SR-DRAG-01; REFERENCE/PARAMETRIC, not the host spacecraft (A9.13 S6.18); replaced only by the host ICD",
             label="REFERENCE_PENDING_CUSTOMER_ICD"),
        item("DBF1-DRAG-02", "HOST_DRAG", "drag model", "D(state) = q (C_D A_ref)_body + D_intake(state, scenario), "
             "q = 1/2 rho v^2 at the frozen orbit-resolved state (F1 envelope atmospheres); D_intake = F1 intake-face "
             "drag per unit frontal area (TPMC, theta 0, per surface scenario) x A_intake 0.25 m^2; "
             "intake_accounting separate_term", "-",
             [src("DRAG_RECORD", "/scope"), src("F1_CORE")], "model-derived (Romano 2018 Eq. 1 form + F1 TPMC)",
             "model-derived", "5", "body term C_D constant (no GSI); intake term per scenario (10 admitted, none "
                                    "chosen); attitude: flow-aligned, arrays parallel to flight (not stated by the "
                                    "body source)", "REFERENCE_PENDING_ICD",
             "the admitted abep_mission::reference_drag function with the F1 drag table; T_required(state) = D(state) "
             "for T - D >= 0 (A9.13 S6.15)", label="REFERENCE_PENDING_CUSTOMER_ICD"),
        item("DBF1-DRAG-03", "HOST_DRAG", "surface accommodation basis", "body: as stated by the case source (not "
             "stated: C_D 2.2 is a literature-typical value); intake: the 10 admitted TPMC scenarios (Maxwell / CLL, "
             "alpha 0-1), reported fav / unfav, never chosen", "-",
             [src("DRAG_RECORD", "/findings"), src("A5_RECORD", "/summary/design_identification/DS-F1-GRID/scenarios")],
             "reference pending ICD", "assumed", "7", "accommodation unmeasured (DI-1.3)", "REFERENCE_PENDING_ICD",
             "A9.13 S6.18 lists the accommodation / surface state among the host ICD items",
             label="REFERENCE_PENDING_CUSTOMER_ICD"),
    ]
    cfg = {"case_id": sel["case_id"], "a_ref_m2": sel["a_ref_m2"], "cd": sel["cd"], "intake_accounting": "separate_term",
           "intake_area_m2": intake_cfg["area_m2"], "intake_L_over_d": intake_cfg["L_over_d"],
           "intake_phi": intake_cfg["phi"], "sensitivity_cases": [p["case_id"] for p in pool]}
    return items, rule, cfg


# ================================================================================================ assemble
def build():
    h1, hw = h1_items()
    icp, probe = icp_items()
    intake, bd_in, sr_in, cfg_in = intake_items()
    pm, bd_pm, cfg_pm = power_mass_items()
    th = thermal_items()
    mat, sr_mat, cfg_mat = material_items()
    drag, sr_drag, cfg_drag = drag_items(cfg_in)
    items = h1 + icp + intake + pm + th + mat + drag
    ids = [x["id"] for x in items]
    if len(ids) != len(set(ids)):
        raise BuildError("duplicate item id")
    deficiencies = bd_in + bd_pm + [
        {"id": "DBF1-BD-05", "items": ["DBF1-BZ-04"], "closure_condition": "an H-1 B(z) from FEMM of MC-1 or a "
         "measured map (H1F-BZ-01)", "numbers": {"H1F-BZ-01": "TBD_AFTER_EVIDENCE"},
         "finding": "the simulated field is a P5-shape surrogate scaled into the H1F-BZ-03 band: a Hall non-closure "
                    "under it is never eligible (envelope prereg bz_family classification_effect)",
         "category": "MISSING_EVIDENCE", "sources": [src("ENV_PREREG", "/bz_family"), src("H1F", "/parameters/34")]},
        {"id": "DBF1-BD-06", "items": ["DBF1-ICP-02", "DBF1-ICP-04"], "closure_condition": "ICP I_e,cap evaluable "
         "(NP-ICP v2 inputs registered and the AIR / Xe rate sets admitted)",
         "numbers": {"registered_by_DBF1": ["f_RF", "geometry (ASSUMED_GEOMETRIC_TUBE)", "collector", "gas routing"],
                     "not_registered": ["absorbed RF power / P2 coupling evidence", "electrode potentials and bias "
                                        "range (P1-IT-36 / P1-IT-18)", "edge-factor source", "NP-ICP-CHEM-AIR / Xe "
                                        "rate sets (not admitted)"]},
         "finding": "with the frozen geometry and RF, I_e,cap stays NOT_EVALUATED: the remaining inputs are operating "
                    "points or evidence, not design values",
         "category": "MISSING_EVIDENCE", "sources": [src("ICP_LOCK_V2"), src("P1_BENCH", "/current_statuses")]},
    ]
    a937 = js("A937_JSON")
    doc = {
        "schema": "abep_design_baseline_freeze_v1",
        "id": "DBF-1",
        "version": 1,
        "title": "DBF-1 Design Baseline Freeze 1 - hall_icp_neutralizer",
        "date": "2026-10-08",
        "architecture": "hall_icp_neutralizer",
        "governing_decision": {"id": a937["id"], "json": src("A937_JSON"), "md": src("A937_MD"),
                               "owner_decision_summary": a937["owner_decision_summary"]},
        "authority_rule": "this JSON is authoritative; DBF1_v1.md restates it; dbf1_config_v1.json is the machine-readable "
                          "subset the closure harness reads through abep-config (abep_config::baseline), pinned by "
                          "dbf1_lock_v1.json",
        "source_rule": "only values or candidates already in the repository (A9.37); no invented physics; where evidence "
                       "is incomplete the selected engineering assumption is frozen with its evidence class and "
                       "uncertainty",
        "status_vocabulary": STATUSES,
        "evidence_attributes": {"evidence_class": "plain-language class (owner-fixed / literature / model-derived / "
                                                  "engineering assumption / reference pending ICD)",
                                "quantity_type": "docs/EVIDENCE.md quantity type (measured, digitized, inferred, "
                                                 "reconstructed, model-derived, assumed) or owner-allocation / "
                                                 "as-reported",
                                "evidence_level": "docs/EVIDENCE.md hierarchy 1-7, OWNER_DECISION or DEFINITION"},
        "hardware_configuration": {"geometry_id": hw[0], "bz_shape_id": hw[1],
                                   "meaning": "the envelope hardware configuration (geometry, bz_shape) of DBF-1; "
                                              "B_peak, V_d and mdot are operating variables"},
        "selection_rules": [sr_in, sr_mat, sr_drag],
        "items": items,
        "baseline_deficiencies": deficiencies,
        "change_control": {"process": f"{REL_OUT}/{DCR_PROCESS}", "register": f"{REL_OUT}/{FILES['dcr_register']}",
                           "rule": "after DBF-1 no design value changes merely to improve M2 performance; any change "
                                   "needs a formal DCR naming the physical / evidence reason, approved before rerun "
                                   "(A9.37). Supplying converged Hall envelope data is an input completion, not a "
                                   "design change, and needs no DCR"},
        "not": ["not a performance prediction", "not a PASS / qualification / flight baseline approval",
                "not a change to any RFP requirement, owner decision or admitted / scored record",
                "not an M2 or M3 result"],
        "config_registration": {
            "file": f"{REL_OUT}/{FILES['config']}",
            "loader": "abep_config::baseline::load_dbf1 (sha256 pin DBF1_CONFIG_SHA256 + lock DBF1_LOCK_SHA256, fail "
                      "closed)",
            "why_not_config_manifest": "config/MANIFEST.json is pinned (sha256 3a85581e...) inside immutable committed "
                                       "records that tests regenerate byte for byte (NP-HALL-PARAMETRIC-ENVELOPE "
                                       "closure_run_today_v1.json, closure_run_m1_dryrun_v1.json, "
                                       "closure_run_m1_dryrun_v2.json); listing a "
                                       "new file there would change that pin and break their reproduction. DBF-1 is "
                                       "therefore pinned like the operating scenario (a code pin in abep-config), not "
                                       "through config/MANIFEST.json"},
        "generated_by": BUILDER,
    }
    cfg = {
        "schema": "abep_dbf1_config_v1",
        "id": "dbf1_config_v1",
        "baseline": "DBF-1",
        "authoritative_record": f"{REL_OUT}/{FILES['json']}",
        "note": "machine-readable subset of dbf1_v1.json read by the closure harness (abep_config::baseline); every "
                "value is copied from an item of dbf1_v1.json (item ids given)",
        "h1": {"geometry_id": hw[0], "d_mean_mm": 70.0, "h_mm": 12.0, "L_mm": 103.2, "bz_shape_id": hw[1],
               "B_peak_band_G": [69.93, 268.6], "V_d_band_V": [180.0, 350.0],
               "items": ["DBF1-H1-01", "DBF1-H1-02", "DBF1-H1-03", "DBF1-BZ-02", "DBF1-BZ-04", "DBF1-H1-05"]},
        "rf": {"f_rf_hz": 13.56e6, "p_fwd_envelope_W": [0.0, 500.0], "match_colocated": True,
               "items": ["DBF1-RF-01", "DBF1-RF-02", "DBF1-RF-03"]},
        "icp": {"topology": "OPEN_TUBE_COAXIAL_UNMAGNETIZED", "volume_mode": "ASSUMED_GEOMETRIC_TUBE",
                "radius_m": probe["r_aperture"], "length_m": probe["L_module"], "collector_axial_length_m": 0.10,
                "L_standoff_m": probe["L_standoff"], "r_module_m": probe["r_module"],
                "vessel_material": "borosilicate glass (pyrex class)", "collector_material": cfg_mat["anode_primary_name"],
                "gas_mode": "G-REUSE",
                "items": ["DBF1-ICP-01", "DBF1-ICP-02", "DBF1-ICP-03", "DBF1-ICP-04", "DBF1-ICP-05", "DBF1-ICP-07",
                          "DBF1-MAT-03"]},
        "upstream": dict(cfg_in, items=["DBF1-IN-01", "DBF1-IN-02", "DBF1-IN-03", "DBF1-IN-04", "DBF1-IN-05",
                                        "DBF1-IN-06", "DBF1-IN-07"]),
        "power_mass": dict(cfg_pm, items=["DBF1-PWR-01", "DBF1-PWR-02", "DBF1-PWR-03", "DBF1-PWR-04", "DBF1-MASS-01",
                                          "DBF1-MASS-02", "DBF1-MASS-03"]),
        "thermal": {"topology_item": "DBF1-TH-01", "spacecraft_interface": "SCI-A (REFERENCE_PENDING_ICD)"},
        "materials": dict(cfg_mat, items=["DBF1-MAT-01", "DBF1-MAT-02", "DBF1-MAT-03", "DBF1-MAT-04"]),
        "host_drag": dict(cfg_drag, items=["DBF1-DRAG-01", "DBF1-DRAG-02", "DBF1-DRAG-03"],
                          label="REFERENCE_PENDING_CUSTOMER_ICD"),
        "baseline_deficiencies": [d["id"] for d in deficiencies],
    }
    reg = {"schema": "abep_dcr_register_v1", "id": "dcr_register_v1", "baseline": "DBF-1",
           "process": f"{REL_OUT}/{DCR_PROCESS}", "dcrs": [],
           "rule": "append-only by new register versions (dcr_register_v2.json, ...); this v1 file is the empty "
                   "register at the freeze and is pinned by the DBF-1 lock"}
    return doc, cfg, reg


def dumps(o) -> bytes:
    return (json.dumps(o, indent=1, ensure_ascii=False) + "\n").encode("utf-8")


def fmt(v) -> str:
    if isinstance(v, (dict, list)):
        s = json.dumps(v, ensure_ascii=False)
    else:
        s = str(v)
    s = s.replace("|", "\\|")
    return s if len(s) <= 160 else s[:157] + "..."


def render_md(doc) -> bytes:
    L = [f"# {doc['title']}", "",
         f"Authoritative record: `{FILES['json']}` (this page restates it). Governing decision A9.37 "
         f"(`{doc['governing_decision']['md']['path']}`). Machine-readable subset: `{FILES['config']}` "
         "(read by the closure harness through `abep_config::baseline`). Hash lock: `dbf1_lock_v1.json`. Change control: "
         f"`{DCR_PROCESS}`.", "",
         "Every value comes from a sha256-pinned repository record. Where the evidence is incomplete, the selected "
         "engineering assumption is frozen with its evidence class and uncertainty; nothing is left open.", "",
         "## Statuses", ""]
    for k, v in doc["status_vocabulary"].items():
        L.append(f"- **{k}**: {v}")
    L += ["", f"Hardware configuration (envelope terms): geometry `{doc['hardware_configuration']['geometry_id']}`, "
              f"B shape `{doc['hardware_configuration']['bz_shape_id']}`.", "", "## Frozen items", "",
          "| id | item | value | units | evidence (class / type / level) | uncertainty | status |",
          "|---|---|---|---|---|---|---|"]
    for it in doc["items"]:
        L.append(f"| {it['id']} | {fmt(it['name'])} | {fmt(it['value'])} | {fmt(it['units'])} | "
                 f"{fmt(it['evidence_class'])} / {it['quantity_type']} / {it['evidence_level']} | "
                 f"{fmt(it['uncertainty'])} | {it['status']} |")
    L += ["", "Sources (path, sha256, pointer) and the rationale of every item are in the JSON.", "",
          "## Selection rules (executed by the builder on registered candidates)", ""]
    for r in doc["selection_rules"]:
        L.append(f"### {r['id']} -> `{r.get('selected') or r.get('primary')}`")
        L.append("")
        L.append(f"Pool: {r['pool'] if isinstance(r['pool'], str) else 'declared reference drag cases (see JSON)'}")
        L.append("")
        for k in r["keys_in_order"]:
            L.append(f"- {k}")
        if "backup" in r:
            L.append(f"- result: primary `{r['primary']}`, backup `{r['backup']}`")
        L.append("")
    L += ["## Baseline deficiencies", "", "| id | items | closure condition | finding | category |",
          "|---|---|---|---|---|"]
    for d in doc["baseline_deficiencies"]:
        L.append(f"| {d['id']} | {', '.join(d['items'])} | {fmt(d['closure_condition'])} | {fmt(d['finding'])} | "
                 f"{d['category']} |")
    L += ["", "Numbers of each deficiency are in the JSON (`baseline_deficiencies[].numbers`).", "",
          "## Change control", "", doc["change_control"]["rule"] + ".", "",
          "## Configuration registration", "", doc["config_registration"]["why_not_config_manifest"] + ".", "",
          "## Not", ""]
    L += [f"- {x}" for x in doc["not"]]
    return ("\n".join(L) + "\n").encode("utf-8")


def outputs() -> dict:
    doc, cfg, reg = build()
    out = {FILES["json"]: dumps(doc), FILES["md"]: render_md(doc), FILES["config"]: dumps(cfg),
           FILES["dcr_register"]: dumps(reg)}
    dcr = (OUT / DCR_PROCESS).read_bytes()
    lock = {"id": "dbf1_lock_v1", "baseline": "DBF-1", "locked": "2026-10-08",
            "note": "sha256 of the DBF-1 files, committed alone before any M2 work (A9.37); any change after this lock "
                    "is a DCR with a new baseline version, never an edit",
            "files_relative_to": REL_OUT + "/",
            "files": {k: sha_bytes(v) for k, v in sorted(list(out.items()) + [(DCR_PROCESS, dcr),
                                                                             ("build_dbf1.py",
                                                                              Path(__file__).read_bytes())])},
            "pinned_sources": {PINS[k][0]: sha_bytes(read_pinned(k)) for k in sorted(PINS)}}
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
        print(f"OK: {len(out)} DBF-1 files current")
        return 0
    for k, v in out.items():
        (OUT / k).write_bytes(v)
    print(f"wrote {len(out)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
