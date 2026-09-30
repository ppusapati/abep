#!/usr/bin/env python3
"""A9-02 bus-power boundary for A9 (bus_power_boundary_a9_v1) -- deterministic builder.

Follow-on ``fo_a9_02_bus_boundary_a9`` (trigger ``T_A9_02_BUS_BOUNDARY``, owner decision A9). Standard library only;
reads repository files; no simulation, no Julia, nothing wired into archengine. It

  * verifies the sha256 of every pinned immutable input (A9 decision, the 147 owner answers and their verbatim pack,
    A5, the verified H2 deliverables, the M16 v2 matrix, instrumentation v1, the historical bus_power_boundary_v1
    module and document) and refuses to run on a missing or changed input (no fallback);
  * checks that abep_sim/arch_boundary.py (bus_power_boundary_v1) is byte-identical to the base (rows 66, 108);
  * takes the owner-answer texts verbatim from the pinned answers file and the H2 values it cites from the pinned H2
    files (never retyped);
  * exports the slot table, configuration matrix and start-up templates from abep_sim/bus_boundary_a9.py (pure);
  * writes bus_power_boundary_a9_v1.json, BUS_POWER_BOUNDARY_A9.md (generated from the JSON) and the instance schema
    schemas/interfaces/bus_power_boundary_a9_v1.json.

Nothing here predicts a Hall, neutralizer or plasma quantity; every load is TBD, an owner allocation or a cited value.

    python docs/architecture_comparison/power_boundary_a9/build_bus_power_boundary_a9.py            # (re)write
    python docs/architecture_comparison/power_boundary_a9/build_bus_power_boundary_a9.py --check    # exit 1 on drift
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from abep_sim import bus_boundary_a9 as B  # noqa: E402  (pure module, no I/O)

OUT_JSON = os.path.join(HERE, "bus_power_boundary_a9_v1.json")
OUT_MD = os.path.join(HERE, "BUS_POWER_BOUNDARY_A9.md")
OUT_SCHEMA = os.path.join(ROOT, "schemas", "interfaces", "bus_power_boundary_a9_v1.json")
SCRIPT_REL = "docs/architecture_comparison/power_boundary_a9/build_bus_power_boundary_a9.py"
BASE_COMMIT = "0a430bb5588a438f7c8485c6d16f40ed0d402c4c"
DATE = "2026-09-29"
V1_MODULE_SHA256 = "8dfc309a5d2c717913fd4961bc660f8bab92ed2c59356f5a78bff3ef4392eeae"

INPUTS = {
    "A9": ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer.json",
           "74ef1a727c3656841ef115122c6d60865f7d2d93cfa29f7fb0081886484d2a1f", "governing owner decision A9"),
    "ANS": ("docs/decisions/OD_2026_09_29_owner_answers_147.json",
            "50e39a4deac7d4ada4710b2f641d717f1c4febd59366cbc04d8c66de6b4532b1", "owner answers (machine-readable)"),
    "PACK": ("docs/decisions/OD_2026_09_29_OWNER_DECISION_PACK_147.md",
             "8736d88a64bf26bd06a332a68c2450a780f175fffafe5aca0625759133666976", "owner decision pack (verbatim)"),
    "A5": ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_architecture.json",
           "0554136751f5ffc7bd7f62c1c4723acce946ef4f523f43687b95710cc8ace621",
           "A5 bus-power design allocation <= 1.30-1.35 kW (immutable, context)"),
    "V1MOD": ("abep_sim/arch_boundary.py", V1_MODULE_SHA256,
              "historical bus_power_boundary_v1 module (read only; must stay byte-identical)"),
    "V1DOC": ("docs/architecture_comparison/power_boundary/BUS_POWER_BOUNDARY.md",
              "2432edb7e9095fd630585768a62a811140b5230ba035afa3f0fc168636d11ca9",
              "historical bus_power_boundary_v1 document"),
    "H21": ("docs/hardware/h2/h2_1_hall_chamber_magnet/h2_1_hall_chamber_magnet_v1.json",
            "49b9a45e9347b141bf8bd1122ffba3ae038c9f088041e4410525e4ab8695b82d", "H2-1 verified deliverable"),
    "H22": ("docs/hardware/h2/h2_2_cathode_integration/h2_2_cathode_integration_v1.json",
            "8436008ac458d4e7467a9c7c9592d5312b3912b918d584ceaf3ac8cb2745a971", "H2-2 verified deliverable"),
    "H24": ("docs/hardware/h2/h2_4_ppu_bus/h2_4_ppu_bus_v1.json",
            "5c6623612ee9ec22899083201416f7b51a10a2d7e88456d372783ce2edde26ef", "H2-4 verified deliverable"),
    "H27": ("docs/hardware/h2/h2_7_mechanical_bom/h2_7_mechanical_bom_v1.json",
            "d1813e153af37ebd45cb2ead964ead6c53c756d1a82f93ea89346a83168d0630", "H2-7 verified deliverable"),
    "M16": ("docs/budgets/subsystem_maturity/subsystem_maturity_v2.json",
            "a82b1acd118b26e89edd4fa467bec778fa410470cca5eb6f684e6553eadaf23c", "M16 v2 subsystem maturity matrix"),
    "INS": ("docs/experiments/instrumentation/instrumentation_definition_v1.json",
            "7c6d37b00f38a44cded73d92d4366739eacbf013e73e98a7bfbc3fa5a5470d96",
            "instrumentation v1 (INS-02 DC metering, INS-03 RF power principle)"),
}
# Read via `git show` on 2026-09-29, cited only (not in the base tree, not re-verified by this builder).
HISTORICAL_V2 = {"commit": "7335dcd8bd1f64d2967b96134a0a37e00abfb770", "branch": "feature/rf-hall-parallel-v2",
                 "path": "docs/parallel_architecture/POWER_BOUNDARY_V2.md",
                 "sha256": "7b696a0bc977ef558ce6faa973f7a874dbaa5b5845942eeb9057ee953d6957e8"}
BANNED_PINS = ("lane_registry", "trigger_registry", "trigger_ledger", "fired_triggers", "runtime_state")

LANES = {
    "A9-01": "docs/experiments/hall_icp/prereg_framework/",
    "A9-03": "docs/interfaces/icp_neutralizer/",
    "A9-04": "docs/experiments/hall_icp/uncertainty_budget/",
    "A9-05": "docs/experiments/hall_icp/validation_inputs/ (+ docs/evidence/icp_neutralizer/)",
    "A9-06": "A9-06 mass BOM amendment (path not yet assigned)",
    "A9-07": "A9-07 H2 revisions (path not yet assigned)",
    "A9-08": "docs/budgets/xe_ledger/ (A9-08 update)",
    "A9-10": "A9-10 governance (path not yet assigned)",
    "H2-1": "docs/hardware/h2/h2_1_hall_chamber_magnet/",
    "H2-2": "docs/hardware/h2/h2_2_cathode_integration/",
    "H2-3": "docs/hardware/h2/h2_3_gas_path_plenum/",
    "H2-4": "docs/hardware/h2/h2_4_ppu_bus/",
    "H2-5": "docs/hardware/h2/h2_5_thermal_network/",
    "H2-6": "docs/hardware/h2/h2_6_diagnostics_fixture/",
    "H2-7": "docs/hardware/h2/h2_7_mechanical_bom/",
    "M16": "docs/budgets/subsystem_maturity/",
}
FREEZE_POINTS = ("NOW", "LOCK-1", "LOCK-2", "after-evidence")
EVIDENCE = B.EVIDENCE_CLASSES + ("n/a (rule)", "requirement-as-recorded", "TBD")  # item-level classes


def pend(lane: str, what: str = "") -> str:
    return f"PENDING {LANES[lane]}" + (f" ({what})" if what else "")


# A9_INT (fo_a9_int_core_integration): the A9-01/03/04/05 deliverables are merged in the base 88e4d47. A cross-reference
# whose target item the merged deliverable defines cites the concrete file + item id (never read here, never pinned
# here: the five A9 deliverables reference each other, so an in-file sha256 has no fixed point; the post-integration
# sha256 of every target is pinned in docs/experiments/hall_icp/integration/a9_core_integration_v1.json). References
# the target does not define keep pend().
RESOLVED = {
    "A9-03": "schemas/interfaces/icp_neutralizer_icd_v1.json",
    "A9-04": "docs/experiments/hall_icp/uncertainty_budget/hall_icp_uncertainty_budget_v1.json",
}


def ref(lane: str, item: str, what: str = "") -> str:
    """Resolved cross-reference (A9_INT): concrete file + item id(s)."""
    return f"{RESOLVED[lane]} {item}" + (f" ({what})" if what else "")


class A902InputError(RuntimeError):
    """A pinned input is missing, changed, or lacks an entry this build needs (no fallback)."""


def _sha(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def load_inputs() -> dict:
    out = {}
    for key, (rel, sha, _role) in INPUTS.items():
        if any(b in rel for b in BANNED_PINS):
            raise A902InputError(f"mutable governance file may not be pinned: {rel}")
        p = os.path.join(ROOT, rel)
        if not os.path.isfile(p):
            raise A902InputError(f"pinned input missing: {rel}")
        got = _sha(p)
        if got != sha:
            raise A902InputError(f"pinned input changed: {rel} sha256 {got} != {sha}")
        with open(p, encoding="utf-8") as f:
            out[key] = json.load(f) if rel.endswith(".json") else f.read()
    if 'BOUNDARY_VERSION = "bus_power_boundary_v1"' not in out["V1MOD"]:
        raise A902InputError("abep_sim/arch_boundary.py no longer declares bus_power_boundary_v1")
    return out


def answer(inp: dict, row: int) -> dict:
    for a in inp["ANS"]["answers"]:
        if a["row"] == row:
            return a
    raise A902InputError(f"owner answer row {row} not found")


def param(doc: dict, pid: str, key: str = "design_parameters") -> dict:
    for p in doc.get(key, []):
        if p.get("id") == pid:
            return p
    raise A902InputError(f"parameter {pid} not found in {key}")


def m16_row(inp: dict, key: str) -> dict:
    for r in inp["M16"]["rows"]:
        if r["key"] == key:
            return r
    raise A902InputError(f"M16 row {key} not found")


def I(iid, name, value, units, basis, source, ev, status, freeze, note=None):
    if ev not in EVIDENCE:
        raise A902InputError(f"{iid}: evidence class {ev!r}")
    if freeze not in FREEZE_POINTS:
        raise A902InputError(f"{iid}: freeze point {freeze!r}")
    d = {"id": iid, "name": name, "value": value, "units": units, "basis": basis, "source": source,
         "evidence_class": ev, "status": status, "freeze_point": freeze}
    if note:
        d["note"] = note
    return d


def R(n: int) -> str:
    return f"docs/decisions/OD_2026_09_29_owner_answers_147.json row {n}"


# ------------------------------------------------------------------------------------------------------ build
def build(inp: dict) -> dict:
    h21_18 = param(inp["H21"], "H21-18")
    h21_27 = param(inp["H21"], "H21-27")
    h22_16 = param(inp["H22"], "H22-16")
    h22_17 = param(inp["H22"], "H22-17")
    h22_22 = param(inp["H22"], "H22-22")
    h24 = inp["H24"]
    a5_alloc = next(x for x in inp["A5"]["allocations_and_requirements"]
                    if x["quantity"] == "bus-power design allocation")
    if a5_alloc["value"] != "<= 1.30-1.35 kW":
        raise A902InputError("A5 bus-power design allocation text changed")
    if list(B.A5_ALLOCATION_RANGE_W) != [1300.0, 1350.0]:
        raise A902InputError("module A5 range does not match the A5 text")

    margin_req = B.P_BUS_REQUIREMENT_W - B.DESIGN_ALLOCATION_W
    common_rest = B.COMMON_ALLOCATION_W - B.CONTROLS_THERMAL_ALLOWANCE_W
    non_common = B.DESIGN_ALLOCATION_W - B.COMMON_ALLOCATION_W
    i_alloc = B.DESIGN_ALLOCATION_W / B.INTERNAL_BUS_V
    i_req = B.P_BUS_REQUIREMENT_W / B.INTERNAL_BUS_V
    me = f"{SCRIPT_REL} :: build()"

    items = [
        I("A902-01", "RFP bus-power requirement (strict '<')", B.P_BUS_REQUIREMENT_W, "W", "requirement",
          f"A9 decision requirement_discipline; {R(108)}; RFP '< 1.5 kW' as recorded (official RFP not yet obtained, "
          f"rows 1-3: verify)", "requirement-as-recorded",
          "REQUIREMENT_AS_RECORDED", "NOW",
          "gate at the spacecraft-DC propulsion boundary; no discharge-only or RF-generator-only claim is sufficient"),
        I("A902-02", "gate scope: steady state AND start-up transients", "applies to both", "-", "owner decision",
          R(108), "n/a (rule)", "ADOPTED", "NOW",
          "unless the official RFP explicitly permits a transient exception"),
        I("A902-03", "averaging window / bandwidth defining 'start-up transient' power for the gate", "TBD",
          "s", "pending", "TBD - requires owner decision OQ-A902-01 (H2-4 H24-37 left it TBD)", "TBD", "OPEN",
          "LOCK-1", "until frozen, rfp_power_gate gives a start-up step PASS only when its ledger is declared "
          "power_basis='peak_sampled' (otherwise NOT_EVALUABLE) and always reports transient_window_frozen=False"),
        I("A902-04", "internal design allocation (ICP must fit inside it)", B.DESIGN_ALLOCATION_W, "W", "allocation",
          f"{R(109)} ('~1.35 kW'; do not plan to consume the 1.35 -> 1.5 kW margin nominally)", "owner-allocation",
          "ALLOCATION (not a prediction, not a gate)", "NOW"),
        I("A902-05", "A5 bus-power design allocation range (context)", list(B.A5_ALLOCATION_RANGE_W), "W",
          "allocation", f"{INPUTS['A5'][0]} :: allocations_and_requirements '{a5_alloc['value']}'",
          "owner-allocation", "CONTEXT (immutable A5)", "NOW"),
        I("A902-06", "allocation-to-requirement margin (not consumed nominally)", margin_req, "W", "derived",
          f"{me}: A902-01 - A902-04", "model-derived", "DERIVED", "NOW"),
        I("A902-07", "common allocation (upper design allocation, incl. controls/thermal)", B.COMMON_ALLOCATION_W,
          "W", "allocation", R(114), "owner-allocation", "ALLOCATION (not a measured load)", "NOW",
          "composition of the common group in A9 is PROPOSED (OQ-A902-02)"),
        I("A902-08", "controls/thermal allowance inside the common allocation", B.CONTROLS_THERMAL_ALLOWANCE_W, "W",
          "allocation", R(114), "owner-allocation", "ALLOCATION", "NOW"),
        I("A902-09", "common allocation left for the feed-side common slots", common_rest, "W", "derived",
          f"{me}: A902-07 - A902-08", "model-derived", "DERIVED", "NOW"),
        I("A902-10", "design allocation left for Hall + electron-source + reserved-port slots if the common group "
          "uses its full allocation", non_common, "W", "derived", f"{me}: A902-04 - A902-07", "model-derived",
          "DERIVED (allocation arithmetic, not a prediction)", "NOW"),
        I("A902-11", "regulated internal propulsion bus (breadboard / PPU architecture)", B.INTERNAL_BUS_V, "V",
          "owner decision", f"{R(111)} (not an RFP spacecraft interface requirement)", "owner-allocation",
          "ADOPTED", "NOW"),
        I("A902-12", "spacecraft input voltage at the front end", "TBD", "V", "pending",
          "TBD - requires the actual spacecraft bus specification (front end configurable, row 111)", "TBD", "OPEN",
          "after-evidence"),
        I("A902-13", "front-end efficiency (spacecraft input -> 100 V internal bus)", "TBD", "-", "pending",
          "TBD - requires a measured breadboard front end or converter data at the selected input and 100 V output",
          "TBD", "OPEN", "LOCK-2"),
        I("A902-14", "upper bound of internal-bus current at the design allocation (eta_front_end <= 1)", i_alloc,
          "A", "derived", f"{me}: A902-04 / A902-11", "model-derived", "DERIVED (harness sizing input)", "NOW"),
        I("A902-15", "upper bound of internal-bus current at the requirement (eta_front_end <= 1)", i_req, "A",
          "derived", f"{me}: A902-01 / A902-11", "model-derived", "DERIVED (protection sizing input)", "NOW"),
        I("A902-16", "ICP RF frequency", B.RF_FREQUENCY_HZ, "Hz", "owner decision",
          f"{R(72)}; A9 decision primary_hypothesis", "owner-allocation", "ADOPTED", "NOW"),
        I("A902-17", "laboratory RF source / inline chain forward-power range (GROUND/FACILITY-ONLY)",
          list(B.LAB_RF_FORWARD_W_RANGE), "W", "owner decision", R(72), "owner-allocation",
          "ADOPTED (lab sizing; not a flight allocation, not a prediction)", "NOW"),
        I("A902-18", "RF power measurement method", "directional coupler forward/reflected primary; calorimetry "
          "independent cross-check", "-", "owner decision", R(72), "n/a (rule)", "ADOPTED", "NOW"),
        I("A902-19", "RF quantity crossing the bus boundary", "generator DC input only", "-", "definition",
          f"{R(66)}; {R(72)}; A9 requirement_discipline", "n/a (rule)", "ADOPTED", "NOW",
          "forward/reflected/delivered RF power are measurement quantities (rf_power_planes)"),
        I("A902-20", "ICP electron-source sub-allocation inside A902-10", "TBD", "W", "pending",
          "TBD - owner call OQ-A902-03 (A8/v2 'rf <= 700 W' is a parallel-branch number and is not carried)", "TBD",
          "OPEN", "LOCK-1"),
        I("A902-21", "RF generator DC-input -> forward-power efficiency", "TBD", "-", "pending",
          "TBD - requires S1a measurement (generator DC input metered + coupler forward power); H2-4 H24-14 was a "
          "pre-ionizer chain analog and is not reused", "TBD", "OPEN", "LOCK-2"),
        I("A902-22", "matching-network DC draw (tuning actuators / controller)", "TBD", "W", "pending",
          pend("A9-03", "fixed vs auto-tuned match"), "TBD", "OPEN", "LOCK-1"),
        I("A902-23", "collector/bias supply V and I range", "TBD", "V / A", "pending",
          ref("A9-03", "ICP-20, ICP-21", "electron-extraction collector bias, floating body row 70"), "TBD", "OPEN", "LOCK-1"),
        I("A902-24", "ICP gas-feed valve/controller power and feed species", "TBD", "W", "pending",
          "TBD - A9 recorder flag row 46 (ICP gas feed not yet booked); " + ref("A9-03", "ICP-26"), "TBD", "OPEN", "LOCK-1"),
        I("A902-25", "C1 keeper pulsed ignition capability (current-limited; interlocks; pulse energy recorded)",
          list(B.C1_KEEPER_PULSE_IGNITION_CLASS_V), "V", "owner decision",
          f"{R(89)}; H2-2 H22-22 {h22_22['value']} {h22_22['units']} ({h22_22['evidence_class']})",
          "owner-allocation", "ADOPTED (capability, not a load)", "NOW",
          "its bus power is a start-up transient of slot c1_keeper, value TBD - requires measured peak draw "
          "(covered only by a peak_sampled step) and recorded pulse energy (a measurement record, PENDING A9-04; "
          "the ledger has no pulse-energy field); H2-4 H24-19 (DC ignition 10-30 W bracket) does not cover it"),
        I("A902-26", "C1 heater power during preheat", "TBD", "W", "pending",
          f"TBD - requires the C1 unit selection; analog envelope only: H2-2 H22-16 {h22_16['value']} "
          f"{h22_16['units']} ({h22_16['evidence_class']} analog, not a C1 value)", "TBD", "OPEN", "after-evidence"),
        I("A902-27", "C1 heater power in steady state", "TBD", "W", "pending",
          f"TBD - H2-2 H22-17: '{h22_17['value'][:80]}...' (conditional on self-heating)", "TBD", "OPEN",
          "after-evidence"),
        I("A902-28", "C1 cathode-common / bleeder tie", "TBD", "ohm / W", "pending",
          f"{R(91)}: isolated selectable topology with V/I measurement; value chosen after EMC/stability bench tests",
          "TBD", "OPEN", "after-evidence"),
        I("A902-29", "filter/getter load (C1/Xe branch only)", "TBD", "W", "pending",
          f"TBD - requires vendor/spec verification ({R(51)}: '<= 17 W-class' only after verification)", "TBD",
          "OPEN", "after-evidence"),
        I("A902-30", "compressor bus draw", "TBD", "W", "pending",
          f"{R(22)}: PARTIAL_BOUNDARY until measured / supplied by ICD; " + pend("H2-3"), "TBD",
          "PARTIAL_BOUNDARY", "after-evidence"),
        I("A902-31", "Hall magnet supplies: one slot per coil (inner, outer, trim)", h21_27["value"], "-",
          "H2-1", f"{INPUTS['H21'][0]} :: H21-27 ({h21_27['evidence_class']})", "n/a (rule)", "ADOPTED", "NOW",
          f"H2-1 H21-18 coil power (inner + outer, trim excluded) {h21_18['value']} {h21_18['units']} "
          f"({h21_18['evidence_class']}) is cited, never used as a default; revision pending (rows 77, 78; A9-07)"),
        I("A902-32", "Hall discharge load", "TBD", "W", "pending",
          "TBD - requires measured V_d x I_d on H-1 (no Hall transport closure is admitted; no prediction)", "TBD",
          "OPEN", "after-evidence"),
        I("A902-33", "ICP assist magnet", "not installed in the first build", "W", "owner decision",
          f"{R(69)}: unmagnetized first build; a magnetic variant is a new controlled variant with booked power/mass",
          "n/a (rule)", "ADOPTED", "NOW"),
        I("A902-34", "active cooling load", "TBD", "W", "pending",
          f"{R(66)}: slot present only in a declared variant; context {R(86)} (>= 50 K margin, +20 % heat load); "
          + pend("H2-5"), "TBD", "OPEN", "after-evidence"),
        I("A902-35", "supply efficiencies (internal bus -> load plane), one per slot", "TBD", "-", "pending",
          "explicit ledger inputs with evidence class. H2-4 candidate evidence: H24-05 is digitized at 25-34 V "
          "input (needs re-basing to the 100 V internal bus); H24-06..H24-11 are S-OSUGA05 (IEPC-2005-114) analogs "
          "on a regulated 100 V +/- 3 V bus (bus voltage matches) but for a 200 mN / 3 kW-class PPU and mostly "
          "minimum-efficiency specifications, so transfer to A9 load levels is not established (see "
          "h2_4_revision_flags)", "TBD", "OPEN", "LOCK-2"),
        I("A902-36", "P_bus measurement-chain uncertainty (DC channels + RF planes)", "TBD", "relative",
          "pending", ref("A9-04", "measurement_chains[dq=DQ-HI-PBUS]") + "; historical INS-02 numbers are not carried (row 18)", "TBD", "OPEN", "LOCK-1"),
        I("A902-37", "C1 ignition-flow dwell cap in the start-up sequence", "120 s per attempt, at most two retries",
          "s", "owner decision", f"{R(93)} (preliminary; final bound frozen before score-bearing C1 testing)",
          "owner-allocation", "ADOPTED (preliminary)", "LOCK-2"),
        I("A902-38", "reserved DC port", "stated explicitly per step (0 W when unused)", "W", "definition",
          f"{R(110)}; PROPOSED: any use must fit inside A902-10", "n/a (rule)", "PROPOSED", "LOCK-1"),
    ]

    # slot table and configuration matrix, exported from the pure module
    slots = []
    for s in B.ALL_SLOTS:
        d = B.SLOTS[s]
        per = {}
        for c in B.CONFIGURATIONS:
            if s in B.BASE_SLOTS[c]:
                per[c] = "INSTALLED"
            elif s in B.VARIANT_OPTIONS[c]:
                per[c] = "VARIANT_ONLY"
            else:
                per[c] = "NOT_INSTALLED"
        slots.append({"slot": s, "group": d["group"], "load_plane": d["load_plane"], "rows": d["rows"],
                      "common_allocation": bool(d.get("common_allocation")),
                      "controls_thermal": bool(d.get("controls_thermal")), "configurations": per})

    rf_planes = [
        {"plane": "generator_dc_input", "crosses_bus_boundary": True, "role": "ledger load of slot icp_rf_source",
         "measured_by": "DC channel (4-wire V + shunt / zero-flux CT) at the generator input", "row": 72},
        {"plane": "forward", "crosses_bus_boundary": False, "role": "measurement quantity",
         "measured_by": "directional coupler forward sensor (primary)", "row": 72},
        {"plane": "reflected", "crosses_bus_boundary": False, "role": "measurement quantity",
         "measured_by": "directional coupler reflected sensor (primary)", "row": 72},
        {"plane": "delivered_to_load", "crosses_bus_boundary": False,
         "role": "measurement quantity (<= forward - reflected)",
         "measured_by": "calorimetry independent cross-check (not the sole primary measurement)", "row": 72},
    ]

    ans_rows = {
        5: "40 kg is wet: H2-7 mass demands for PPU/RF electronics are booked against the wet-system limit",
        18: "no numeric decision margin is carried; allocation checks are owner allocations, not effect sizes",
        22: "compressor TBD -> ledger status PARTIAL_BOUNDARY; no guessed fixed load",
        37: "the ledger reports per-slot P_bus for Delta P_bus in NET_BENEFIT; no weighted scalar is formed",
        38: "NOT_EVALUABLE / OPEN are statuses, not outcomes",
        42: "sequence steps with Xe flow (purge, preheat, ignition) are flagged for PHASE_TOTAL_FLOW booking",
        46: "hall_icp_neutralizer has no C1 slots; its gas feed has its own flow_control_icp_feed slot",
        51: "filter_getter slot exists only in hall_c1_reference; value TBD until vendor/spec verification",
        54: "v0 dry allocations passed to H2-7 as allocations, not CBEs: electronics lines (RF generator/matching "
            "1.5 kg, Hall PPU 2.5 kg, controls/harness 1.0 kg) and, separately, the ICP neutralizer source head "
            "(2.0 kg, not electronics)",
        55: "H2-4 H24-35 (no single-point failure) flagged CONSTRAINED_BY_OWNER_ANSWER: limited redundancy, no "
            "full-PPU duplication; redundancy affects PPU mass, not the per-slot P_bus rule",
        56: "SBIR 2 kg PPU is not used as mass evidence",
        59: "new electronics lines (RF generator/matching, collector/bias supply) requested from H2-7",
        66: "new boundary version with explicit RF source/matching, collector/bias, assist-magnet and "
            "active-cooling slots; v1 untouched",
        69: "icp_assist_magnet is a variant-only slot; not installed in the first build",
        70: "icp_collector_bias is a separate metered slot; ICP body floating",
        72: "13.56 MHz; lab 0-500 W forward; coupler primary, calorimetry cross-check; only generator DC input "
            "crosses the boundary",
        79: "external C1: C1 slots belong to the swappable downstream module, the Hall slots are neutralizer-agnostic",
        86: "active_cooling variant slot provided for the >= 50 K margin rule if needed",
        89: "c1_keeper includes current-limited pulsed ignition 300-600 V class as a start-up transient; its peak "
            "is gate-covered only by a peak_sampled step; pulse energy is a measurement record (PENDING A9-04); "
            "H2-4 H24-19 flagged NEEDS_REVISION",
        90: "flow_control_xe covers the two series isolation valves",
        91: "c1_common_tie slot, value TBD, selectable and measured",
        93: "C1 ignition dwell cap 120 s x 2 retries recorded as a sequence constraint",
        105: "discharge-supply output isolation is coordinated with the 350 V continuous / ~1 kV withstand gas "
             "isolator (interface demand to H2-3)",
        108: "rfp_power_gate applies < 1500 W to steady state and every start-up step; empty start-up refused; a "
             "start-up step PASSes only if peak_sampled while the averaging window is TBD (A902-03)",
        109: "design allocation 1350 W check; ICP must fit inside; 150 W margin not planned nominally",
        110: "every active load has a slot (per-coil magnet, RF source/matching, collector/bias, C1 heater/keeper, "
             "flow/valve, housekeeping, reserved DC)",
        111: "100 V regulated internal bus; configurable spacecraft-input front end with explicit efficiency",
        112: "revised SEQ-1 templates: one peak event per step and at most one peak-class slot load rising per step; "
             "C1 heater reduced only after keeper/discharge stable (a TBD heater counts as ON; last known value "
             "kept across TBD steps); no ICP heater",
        113: "breadboard discharge supply demand (eta_d and transients before LOCK-2) passed to H3",
        114: "300 W common allocation incl. 50 W controls/thermal: allocation checks, not measured loads",
        117: "RF coax across the stand is a measurement-side item; the bus boundary is unaffected",
        122: "configurations differ only by the swappable downstream module's slots; H-1 slots identical",
        130: "ICP telemetry (forward/reflected, collector V/I, RF source temperature, interlock) demanded from H2-6",
        133: "matched sham service lines carry no power: sham/not-installed slots are exactly 0 W",
        145: "RF coupling, forward/reflected/absorbed power and collector potential planes defined for A9-05",
    }
    applied = []
    for row, how in ans_rows.items():
        a = answer(inp, row)
        applied.append({"row": row, "covers_ids": a["covers_ids"], "owner_answer_verbatim": a["owner_answer_verbatim"],
                        "classification_by_recorder": a["classification_by_recorder"], "how_applied": how})

    # H2-4 revision flags (each id verified to exist in the pinned H2-4 file)
    def h24_flag(pid, disp, why, key="design_parameters"):
        p = param(h24, pid, key)
        return {"h2_4_id": pid, "name": p.get("name") or p.get("question") or p.get("item"), "disposition": disp,
                "why": why}
    h24_flags = [
        h24_flag("H24-02", "RETAINED", "row 109: ~1.35 kW design allocation; the ICP must fit inside it"),
        h24_flag("H24-04", "NEEDS_REVISION", "row 111: regulated 100 V internal bus; spacecraft input configurable"),
        h24_flag("H24-05", "NEEDS_REVISION", "discharge-supply analog on a 25-34 V input; input is now the 100 V "
                 "internal bus; row 113 breadboard measures eta_d before LOCK-2"),
        h24_flag("H24-06", "RETAINED", "closest analog class (100 V bus) but 3 kW-class, not transferable"),
        h24_flag("H24-07", "RETAINED_AS_CANDIDATE", "S-OSUGA05 keeper conditioner on a 100 V +/- 3 V bus (same bus "
                 "voltage); steady keeper only at 25 W / 0.9-1.0 A; does not cover the row-89 pulsed 300-600 V "
                 "ignition mode; transfer to C1 levels needs breadboard data (A902-35)"),
        h24_flag("H24-08", "RETAINED_AS_CANDIDATE", "S-OSUGA05 heater specification on a 100 V bus; applies to "
                 "hall_c1_reference only (no ICP heater, row 112); specification, not a measurement"),
        h24_flag("H24-09", "NEEDS_REVISION", "per-coil magnet slots (inner/outer/trim)"),
        h24_flag("H24-10", "RETAINED_AS_CANDIDATE", "S-OSUGA05 valve-driver specification on a 100 V bus; now also "
                 "covers the ICP feed valve slot flow_control_icp_feed"),
        h24_flag("H24-11", "RETAINED_AS_CANDIDATE", "S-OSUGA05 auxiliary-supply specification on a 100 V bus; "
                 "housekeeping_controls must also book the no-load/quiescent draw of idle supplies explicitly"),
        h24_flag("H24-14", "SUPERSEDED_FOR_A9", "pre-ionizer RF chain; A9 icp_rf_source books the generator DC input"),
        h24_flag("H24-15", "SUPERSEDED_FOR_A9", "ECR slot (row 68)"),
        h24_flag("H24-16", "NEEDS_REVISION", "single magnet slot with a permanent-magnet 0 W option; H-1 is EM-only "
                 "(row 78) and has one slot per coil"),
        h24_flag("H24-17", "RETAINED", "applies to hall_c1_reference only"),
        h24_flag("H24-19", "NEEDS_REVISION", "DC-ignition bracket (JPL 2 A x 5-15 V, inferred) does not describe "
                 "the row-89 current-limited pulsed 300-600 V class ignition; its peak draw and pulse energy are "
                 "TBD (A902-25) and the start-up step must be peak_sampled to PASS the transient gate"),
        h24_flag("H24-21", "NEEDS_REVISION", "300 W compressor ceiling alone vs row 114: 300 W is the whole common "
                 "allocation incl. 50 W controls/thermal"),
        h24_flag("H24-22", "NEEDS_REVISION", "housekeeping envelope must fit the 50 W controls/thermal allowance "
                 "together with thermal_control (row 114)"),
        h24_flag("H24-23", "NEEDS_REVISION", "A_common envelope replaced by the row-114 common allocation"),
        h24_flag("H24-24", "NEEDS_REVISION", "discharge allocation depended on the v1 A_common; with the ICP "
                 "sub-allocation open (OQ-A902-03) no discharge allocation is derived here"),
        h24_flag("H24-26", "NEEDS_REVISION", "derived directly from H24-24 (P_d,alloc / V_d); inherits its "
                 "revision, not re-derived here"),
        h24_flag("H24-28", "ANSWERED", "row 89: pulsed 300-600 V class ignition required"),
        h24_flag("H24-35", "CONSTRAINED_BY_OWNER_ANSWER", "row 55: LIMITED redundancy - critical sensing/FDIR "
                 "redundancy, do not duplicate the full PPU or the ICP neutralizer at this stage; the RFP text "
                 "itself is still to be verified"),
        h24_flag("H24-33", "NEEDS_REVISION", "bus current at 24-34 V; spacecraft input configurable; internal-bus "
                 "bounds A902-14/15"),
        h24_flag("H24-36", "SUPERSEDED_FOR_A9", "row 112 revised SEQ-1"),
        h24_flag("H24-37", "ANSWERED", "row 108; averaging window still TBD (A902-03)"),
        h24_flag("H24-38", "NEEDS_REVISION", "one metering channel per A9 slot incl. RF generator DC input"),
        h24_flag("H24-40", "RETAINED", "floating outputs; add floating ICP body and separately metered collector "
                 "bias (row 70)"),
        h24_flag("OQ-H24-01", "ANSWERED", "row 108", key="owner_questions"),
        h24_flag("OQ-H24-02", "SUPERSEDED_FOR_A9", "row 109", key="owner_questions"),
        h24_flag("OQ-H24-03", "ANSWERED", "row 110 (partition adopted with revision)", key="owner_questions"),
        h24_flag("OQ-H24-04", "ANSWERED", "row 111", key="owner_questions"),
        h24_flag("OQ-H24-05", "SUPERSEDED_FOR_A9", "row 112 revised SEQ-1", key="owner_questions"),
        h24_flag("OQ-H24-06", "ANSWERED", "row 113", key="owner_questions"),
        h24_flag("H3-PPU-03", "NEEDS_REVISION", "add pulsed ignition 300-600 V, interlocks, pulse-energy record "
                 "(row 89)", key="h3_procurement_inputs"),
        h24_flag("H3-PPU-05", "NEEDS_REVISION", "breadboard discharge supply fed from the 100 V internal bus "
                 "(rows 111, 113)", key="h3_procurement_inputs"),
    ]

    d = lambda f, t, q, v, u, s: {"from": f, "to": t, "quantity": q, "value": v, "units": u, "status": s}  # noqa: E731
    ifd = [
        d("A9-02", "A9-01", "P_bus decision quantity per configuration and the gate rule (steady + start-up, strict "
          "< 1500 W); allocation checks labelled owner allocations", "rfp_power_gate / allocation_checks", "W",
          "PRELIMINARY"),
        d("A9-01", "A9-02", "stage map: which stages evaluate the full-boundary gate; LOCK-1 freeze of the transient "
          "averaging window", None, "-", pend("A9-01")),
        d("A9-02", "A9-03", "ICP supply interface: generator DC input plane, RF feed plane, matching-network DC "
          "port, collector/bias supply port (floating body), separate RF return, ICP feed valve driver",
          "slots icp_rf_source / icp_matching_network / icp_collector_bias / flow_control_icp_feed", "W / V / A",
          "PRELIMINARY"),
        d("A9-03", "A9-02", "generator DC input vs forward power, matching type (fixed/auto) and its DC draw, "
          "collector bias V/I range, assist magnet (none in first build), cooling (passive/active)", None,
          "W / V / A", pend("A9-03")),
        d("A9-02", "A9-04", "measurement chains to budget: one DC channel per installed slot + spacecraft-side "
          "front-end input; RF planes (coupler forward/reflected primary, calorimetry cross-check)",
          "rf_planes; slot list", "W", "PRELIMINARY"),
        d("A9-04", "A9-02", "u(P_bus) per slot and total; stop rules touching power", None, "relative",
          pend("A9-04")),
        d("A9-02", "A9-05", "plane definitions for forward/reflected/absorbed power and collector potential "
          "(row 145)", "rf_planes", "W / V", "PRELIMINARY"),
        d("A9-05", "A9-02", "published analog RF power/generator arrangement (Takahashi 2024) with page/figure "
          "provenance (published analog only)", None, "W", pend("A9-05")),
        d("A9-02", "H2-4", "supply partition revision (per-coil magnets, ICP RF source/matching, collector/bias, C1 "
          "heater/keeper reference supplies, flow/valve/housekeeping, reserved DC); 100 V internal bus; revision "
          "flags", "h2_4_revision_flags", "-", "PRELIMINARY"),
        d("H2-4", "A9-02", "revised converter efficiencies on the 100 V internal bus; front-end topology", None, "-",
          pend("H2-4", "revision under A9-07")),
        d("A9-02", "H2-7", "PPU/RF electronics mass lines: Hall PPU (v0 allocation 2.5 kg), RF generator/matching "
          "(1.5 kg), controls/harness (1.0 kg) [row 54 allocations, not CBEs]; new lines: collector/bias supply, "
          "front-end converter, C1 reference supplies, filter/getter",
          {"hall_ppu_kg": 2.5, "rf_generator_matching_kg": 1.5, "controls_harness_kg": 1.0}, "kg",
          "OWNER_ALLOCATION (row 54; recorder flag on PPU vs 6.1 kg analog)"),
        d("A9-02", "H2-7", "ICP neutralizer SOURCE-HEAD hardware allocation (not electronics; context for the "
          "same wet-mass ledger, row 5): ICP neutralizer 2.0 kg [row 54 allocation, not a CBE]",
          {"icp_neutralizer_kg": 2.0}, "kg", "OWNER_ALLOCATION (row 54)"),
        d("H2-7", "A9-02", "electronics CBE masses", None, "kg", pend("H2-7") + "; " + pend("A9-06")),
        d("H2-1", "A9-02", "coil V/I/P per coil at setpoint (hot), trim use", None, "V / A / W",
          pend("H2-1", "revision under A9-07")),
        d("H2-2", "A9-02", "C1 heater V/I/P and preheat duration; keeper ignition pulse energy; steady keeper "
          "policy; common-tie topology", None, "V / A / W / J", pend("H2-2")),
        d("A9-02", "H2-3", "compressor slot is PARTIAL_BOUNDARY until its bus draw is supplied; valve slots incl. "
          "two series Xe isolation valves and the ICP feed valve; discharge-supply isolation vs the 350 V / ~1 kV gas "
          "isolator (row 105)", None, "W / V", "PRELIMINARY"),
        d("H2-3", "A9-02", "compressor motor-drive input power (steady, spin-up); valve coil powers", None, "W",
          pend("H2-3")),
        d("A9-02", "H2-5", "PPU + RF generator dissipation = sum of per-slot P_loss (from the ledger when complete)",
          None, "W", "PRELIMINARY"),
        d("H2-5", "A9-02", "thermal_control load per step; need for active cooling (>= 50 K rule, row 86)", None,
          "W", pend("H2-5")),
        d("A9-02", "H2-6", "metering channel per slot; ICP telemetry (row 130)", None, "-", "PRELIMINARY"),
        d("A9-02", "Xe ledger", "start-up steps with Xe flow (purge, preheat, ignition <= 120 s x 2) for "
          "PHASE_TOTAL_FLOW booking", None, "s", pend("A9-08")),
        d("A9-02", "M16", "row impacts (m16_impact)", None, "-", pend("M16") + "; " + pend("A9-10")),
    ]

    oq = [
        {"id": "OQ-A902-01", "question": "Averaging window / bandwidth that defines start-up transient power for "
         "the < 1.5 kW gate (row 108)?", "proposed_answer": "PROPOSED: the maximum of the spacecraft-side bus "
         "power reconstructed from simultaneously sampled DC channels at the metering bandwidth, no averaging "
         "beyond it; window frozen as a LOCK-1 rule, bandwidth value at LOCK-2", "freeze_point": "LOCK-1"},
        {"id": "OQ-A902-02", "question": "Which slots make up the 300 W common allocation in A9 (row 114)?",
         "proposed_answer": "PROPOSED: compressor, all flow_control slots, filter_getter, thermal_control, "
         "housekeeping_controls (the latter two = the 50 W controls/thermal allowance); reserved DC port and "
         "active_cooling outside", "freeze_point": "LOCK-1"},
        {"id": "OQ-A902-03", "question": "Sub-allocation of the 1350 W design allocation between Hall discharge, "
         "magnets and the electron source (C1 reference supplies vs ICP RF/matching/collector)?",
         "proposed_answer": "owner call", "freeze_point": "LOCK-1"},
        {"id": "OQ-A902-04", "question": "Is a combined 'ICP + C1 backup' flight variant (both electron sources "
         "installed) in scope? Row 55 excludes duplicating the ICP, and says nothing on a C1 backup.",
         "proposed_answer": "owner call (not declared in bus_power_boundary_a9_v1; would be a new declared "
         "variant)", "freeze_point": "LOCK-1"},
        {"id": "OQ-A902-05", "question": "Which gas and source feed the ICP (Xe ledger or atmospheric feed), and "
         "does its valve sit in the common allocation (row 46 recorder flag)?",
         "proposed_answer": "PROPOSED: book the valve under flow_control_icp_feed inside the common allocation; "
         "species owner call", "freeze_point": "LOCK-1"},
        {"id": "OQ-A902-06", "question": "Are housekeeping/controls and thermal loads fed through the 100 V internal "
         "bus or directly from the spacecraft input?", "proposed_answer": "PROPOSED: through the internal bus "
         "unless the PPU design states otherwise; the path is an explicit ledger input either way",
         "freeze_point": "LOCK-1"},
        {"id": "OQ-A902-07", "question": "Should the design-allocation check also be reported at the A5 lower end "
         "(1300 W)?", "proposed_answer": "PROPOSED: yes, as context only; row 109's ~1.35 kW is the check limit",
         "freeze_point": "NOW"},
    ]

    hist = [
        {"artifact": INPUTS["V1MOD"][0], "sha256": INPUTS["V1MOD"][1],
         "reused": "load-plane / efficiency convention, no-default key checking, finite-real validation, "
                   "conservation (bookkeeping) residual gate",
         "not_reused": "component set and architecture ids (hall_only / rf_hall / ecr_hall); the module is not "
                       "imported and stays byte-identical"},
        {"artifact": INPUTS["V1DOC"][0], "sha256": INPUTS["V1DOC"][1],
         "reused": "definition of P_bus at the spacecraft DC input", "not_reused": "pre-ionizer slots"},
        {"artifact": INPUTS["H24"][0], "sha256": INPUTS["H24"][1],
         "reused": "supply-partition skeleton, start-up phase structure, per-component metering principle, "
                   "analog efficiency parameter ids as candidate evidence (not defaults)",
         "not_reused": "SEQ-1 (superseded, row 112), rf/ecr slot efficiencies, A_common envelope and the derived "
                       "discharge allocation"},
        {"artifact": f"{HISTORICAL_V2['path']} @ {HISTORICAL_V2['commit']} ({HISTORICAL_V2['branch']}; read via git "
                     f"show, not in the base tree)", "sha256": HISTORICAL_V2["sha256"],
         "reused": "TBD -> incomplete status with only a known lower bound; not-installed components exactly 0 W; "
                   "OFF-mode loads caller-stated; residual labelled a bookkeeping identity",
         "not_reused": "rf_only / rf_hall_parallel modes and the rf <= 700 W / hall <= 300 W allocations (branch "
                       "frozen, rows 11, 145, 147)"},
        {"artifact": INPUTS["INS"][0], "sha256": INPUTS["INS"][1],
         "reused": "INS-02 DC channel principle; INS-03 coupler forward/reflected principle",
         "not_reused": "the lane-25 uncertainty numbers (row 18; A9-04 owns the new budget); INS-03 treated the "
                       "RF net power as the load plane, A9 books the generator DC input"},
        {"artifact": "docs/interfaces/preionizer_module/ and docs/experiments/phase1_prereg_framework/",
         "sha256": None, "reused": "nothing", "not_reused": "historical pre-ionizer ICD and A5 Phase-1 framework "
                                                            "(rows 28, 61-65)"},
    ]

    m16_keys = [("ppu", "revised supply partition, 100 V internal bus, A9 ledger; proposed state RUNNING"),
                ("control_fdir", "revised SEQ-1 templates and sequence rules; stays BLOCKED on C1 selection and ICP "
                                 "ignition data"),
                ("cathode", "C1 reference supplies (heater, keeper incl. pulsed ignition, common tie, filter/getter) "
                            "as hall_c1_reference slots"),
                ("thermal_control", "thermal_control slot inside the 50 W allowance; active_cooling variant slot"),
                ("compressor", "PARTIAL_BOUNDARY until the compressor bus draw is supplied (row 22)"),
                ("atm_metering_valve", "flow_control_atmospheric slot"),
                ("xe_metering", "flow_control_xe slot (two series isolation valves)"),
                ("sensors_diagnostics", "one DC channel per slot + RF planes + ICP telemetry"),
                ("preionizer_interface", "not used for the primary line (historical); an ICP-neutralizer row is "
                                         "needed (A9-10), not created here")]
    m16 = []
    for key, how in m16_keys:
        r = m16_row(inp, key)
        m16.append({"m16_row": r["row"], "key": key, "name": r["name"], "how_touched": how})

    h3 = [
        {"id": "H3-A902-01", "item": "13.56 MHz laboratory RF generator, 0-500 W forward, DC input metered",
         "basis": "row 72", "note": "quotations only (row 8); no supplier contact by the lane"},
        {"id": "H3-A902-02", "item": "directional coupler + forward/reflected sensors; calorimetric cross-check "
         "load", "basis": "row 72"},
        {"id": "H3-A902-03", "item": "matching network (fixed or auto-tuned; DC draw metered)",
         "basis": pend("A9-03")},
        {"id": "H3-A902-04", "item": "collector/bias supply (floating, V/I metered)", "basis": "row 70; "
         + ref("A9-03", "ICP-21")},
        {"id": "H3-A902-05", "item": "C1 keeper supply with current-limited pulsed ignition 300-600 V class, "
         "interlocks, pulse-energy recording", "basis": "row 89"},
        {"id": "H3-A902-06", "item": "selectable cathode-common/bleeder network with V/I measurement",
         "basis": "row 91"},
        {"id": "H3-A902-07", "item": "regulated 100 V internal-bus breadboard supply + configurable front end",
         "basis": "row 111"},
        {"id": "H3-A902-08", "item": "flight-representative breadboard Hall discharge supply on the 100 V bus",
         "basis": "row 113"},
    ]
    h4 = [
        {"id": "H4-A902-01", "stage": "S1a", "measure": "RF generator DC input vs coupler forward/reflected into a "
         "dummy load over 0-500 W; calorimetric cross-check", "closes": "A902-21"},
        {"id": "H4-A902-02", "stage": "S1a", "measure": "DUMMY_LOAD_PICKUP of the RF generator on every DC channel",
         "closes": "A902-36 (with A9-04)"},
        {"id": "H4-A902-03", "stage": "S1", "measure": "time-resolved spacecraft-side bus power through both start-up "
         "sequences (transient gate)", "closes": "A902-03 (once frozen)"},
        {"id": "H4-A902-04", "stage": "S1", "measure": "C1 heater reduction timing vs keeper/discharge stability; "
         "keeper pulse energy", "closes": "A902-25..27"},
        {"id": "H4-A902-05", "stage": "S1", "measure": "common-tie / bleeder V and I per selectable setting",
         "closes": "A902-28"},
        {"id": "H4-A902-06", "stage": "S1", "measure": "front-end and per-supply efficiencies on the 100 V bus",
         "closes": "A902-13, A902-35"},
    ]

    templates = {c: [dict(s) for s in B.SEQUENCE_TEMPLATES[c]] for c in B.CONFIGURATIONS}

    return {
        "schema": "a9_lane_deliverable_v1",
        "id": "bus_power_boundary_a9_v1",
        "lane": "A9-02",
        "follow_on": "fo_a9_02_bus_boundary_a9",
        "trigger": "T_A9_02_BUS_BOUNDARY",
        "status": "PRELIMINARY_DRAFT_FOR_OWNER",
        "base_commit": BASE_COMMIT,
        "date": DATE,
        "generated_by": SCRIPT_REL,
        "regenerate": f"python {SCRIPT_REL}  (check: --check)",
        "boundary_version": B.BOUNDARY_VERSION,
        "historical_boundary_untouched": {"path": INPUTS["V1MOD"][0], "sha256": V1_MODULE_SHA256,
                                          "boundary_version": B.V1_BOUNDARY_VERSION},
        "module": "abep_sim/bus_boundary_a9.py",
        "schema_file": "schemas/interfaces/bus_power_boundary_a9_v1.json",
        "configurations": list(B.CONFIGURATIONS),
        "variant_options": {c: list(B.VARIANT_OPTIONS[c]) for c in B.CONFIGURATIONS},
        "what_this_is_not": [
            "not a performance prediction: no thrust, discharge current, neutralizer electron current or plasma state",
            "not an architecture selection: no winner between hall_c1_reference and hall_icp_neutralizer",
            "not a use of any Hall transport closure (credible set empty), of abep_sim/plasma_devices.py or of the "
            "withdrawn v1.2-v1.6 numbers",
            "not wired into archengine; goldens unaffected; bus_power_boundary_v1 unchanged",
            "allocation checks are owner allocations, never gates or measured loads",
        ],
        "decision_pins": [{"key": k, "path": INPUTS[k][0], "sha256": INPUTS[k][1], "role": INPUTS[k][2]}
                          for k in ("A9", "ANS", "PACK", "A5")],
        "pinned_inputs": [{"key": k, "path": INPUTS[k][0], "sha256": INPUTS[k][1], "role": INPUTS[k][2]}
                          for k in INPUTS if k not in ("A9", "ANS", "PACK", "A5")],
        "items": items,
        "slots": slots,
        "rf_power_planes": rf_planes,
        "bus_architecture": {
            "spacecraft_input": "configurable front end (voltage TBD, A902-12); P_bus is measured/booked here",
            "internal_bus": f"regulated {B.INTERNAL_BUS_V:g} V propulsion bus (breadboard/PPU, row 111)",
            "ledger_rule": "P_bus = sum over installed slots of P_W / (eta_slot x eta_front_end) (internal_bus path) "
                           "or P_W / eta_slot (direct path); every value explicit with evidence class",
            "statuses": ["COMPLETE", "PARTIAL_BOUNDARY", "INCOMPLETE_EVIDENCE"],
            "status_taxonomy": "PARTIAL_BOUNDARY whenever the compressor LOAD is TBD (row 22; takes precedence); "
                               "INCOMPLETE_EVIDENCE for any other TBD, including a known compressor load with a TBD "
                               "efficiency or a TBD front-end efficiency; COMPLETE otherwise",
            "power_basis": "each ledger declares what its step values represent: " + ", ".join(B.POWER_BASES)
                           + " or unstated (None)",
            "no_load_losses": "excluded from the per-slot P_W/eta model (a 0 W output draws exactly 0 W); the "
                              "no-load/quiescent draw of energised-but-idle supplies and of the front end must be "
                              "booked explicitly in housekeeping_controls",
            "residual_check": "bookkeeping identity sum(P_W + P_loss) - sum(P_bus); catches floating-point error "
                              "only; an independent closure needs measured spacecraft-side bus V and I",
            "not_installed_rule": "a slot not installed in the configuration/variant is omitted or exactly 0 W at "
                                  "efficiency 1, as full records (evidence_class + source, schema parity); anything "
                                  "else raises (matched shams carry no power)",
        },
        "gates_and_allocations": {
            "rfp_gate": {"limit_W": B.P_BUS_REQUIREMENT_W, "strict": True, "applies_to": ["steady", "startup"],
                         "verdicts": ["PASS", "FAIL", "NOT_EVALUABLE"], "row": 108,
                         "transient_window": dict(B.TRANSIENT_WINDOW),
                         "startup_pass_requires_power_basis": "peak_sampled"},
            "design_allocation": {"limit_W": B.DESIGN_ALLOCATION_W, "row": 109, "kind": "owner allocation"},
            "common_allocation": {"limit_W": B.COMMON_ALLOCATION_W,
                                  "controls_thermal_allowance_W": B.CONTROLS_THERMAL_ALLOWANCE_W, "row": 114,
                                  "kind": "owner allocation (upper design allocation)"},
        },
        "sequencing": {
            "rule_source": "row 112 (revised SEQ-1) and row 108 (transient gate)",
            "peak_events": dict(B.PEAK_EVENTS),
            "enforced_order": {c: [list(p) for p in B.ENFORCED_ORDER[c]] for c in B.CONFIGURATIONS},
            "rules": ["at most one peak-class event per step (PROPOSED reading of 'avoid simultaneous peaks')",
                      "at most one peak-class slot (" + ", ".join(sorted(set(B.PEAK_EVENTS.values())))
                      + ") whose load rises in a step, checked on the step loads independently of event labels "
                      "(PROPOSED; a TBD transition that may rise gives RULES_NOT_EVALUABLE)",
                      "C1 heater reduced/disabled only in a step flagged keeper_stable and discharge_stable; a TBD "
                      "heater counts as ON with unknown power (OFF = exactly 0 W); the last known value is kept "
                      "across TBD steps; an unclassifiable change gives RULES_NOT_EVALUABLE",
                      "sequence_status: SEQUENCE_RULE_VIOLATION > RULES_NOT_EVALUABLE > RULES_SATISFIED",
                      "a start-up step PASSes the transient gate only when declared power_basis='peak_sampled' "
                      "(averaging window TBD, A902-03)",
                      "hall_icp_neutralizer has no c1_heater slot (no thermionic heater)",
                      "the last step is the steady step; the gate is applied to it and to every earlier step"],
            "templates_PROPOSED": templates,
            "note": "templates carry no power numbers; all step loads are caller inputs (TBD until measured)",
        },
        "interface_demands": ifd,
        "h2_4_revision_flags": h24_flags,
        "owner_answers_applied": applied,
        "open_owner_questions": oq,
        "historical_reuse": hist,
        "m16_impact": m16,
        "h3_inputs": h3,
        "h4_inputs": h4,
        "compliance": {
            "allowed_paths": ["abep_sim/bus_boundary_a9.py", "docs/architecture_comparison/power_boundary_a9/**",
                              "schemas/interfaces/bus_power_boundary_a9_v1.json", "tests/test_bus_boundary_a9.py"],
            "no_hall_closure": True, "no_screening_candidate": True, "no_winner": True, "no_archengine_wiring": True,
            "pins_mutable_governance": False, "v1_module_byte_identical": True,
            "parallel_a9_lanes_read_at_build_time": False,
        },
    }


# ------------------------------------------------------------------------------------------------------ schema
def build_schema() -> dict:
    def _load(rf: bool) -> dict:
        extra = {"plane": {"const": "generator_dc_input"}} if rf else {}
        req = ["plane"] if rf else []
        return {"oneOf": [
            {"type": "object", "required": ["P_W", "evidence_class", "source"] + req,
             "properties": {"P_W": {"type": "number", "minimum": 0},
                            "evidence_class": {"enum": list(B.EVIDENCE_CLASSES)},
                            "source": {"type": "string", "minLength": 1}, **extra}, "additionalProperties": False},
            {"type": "object", "required": ["P_W", "tbd_requires"] + req,
             "properties": {"P_W": {"const": "TBD"}, "tbd_requires": {"type": "string", "minLength": 1}, **extra},
             "additionalProperties": False},
        ]}
    num_or_tbd_load, rf_load = _load(False), _load(True)
    eff = {
        "oneOf": [
            {"type": "object", "required": ["value", "evidence_class", "source", "path"],
             "properties": {"value": {"type": "number", "exclusiveMinimum": 0, "maximum": 1},
                            "evidence_class": {"enum": list(B.EVIDENCE_CLASSES)},
                            "source": {"type": "string", "minLength": 1}, "path": {"enum": list(B.PATHS)}},
             "additionalProperties": False},
            {"type": "object", "required": ["value", "tbd_requires", "path"],
             "properties": {"value": {"const": "TBD"}, "tbd_requires": {"type": "string", "minLength": 1},
                            "path": {"enum": list(B.PATHS)}}, "additionalProperties": False},
        ]}
    fe = {
        "oneOf": [
            {"type": "object", "required": ["value", "evidence_class", "source"],
             "properties": {"value": {"type": "number", "exclusiveMinimum": 0, "maximum": 1},
                            "evidence_class": {"enum": list(B.EVIDENCE_CLASSES)},
                            "source": {"type": "string", "minLength": 1}}, "additionalProperties": False},
            {"type": "object", "required": ["value", "tbd_requires"],
             "properties": {"value": {"const": "TBD"}, "tbd_requires": {"type": "string", "minLength": 1}},
             "additionalProperties": False},
        ]}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:abep:schemas:interfaces:bus_power_boundary_a9_v1",
        "title": "ABEP A9 spacecraft-DC propulsion bus-power boundary v1 (ledger input declaration)",
        "description": "Instance schema for one evaluated step of abep_sim.bus_boundary_a9.ledger. Installed-slot "
                       "completeness per configuration/variant and not-installed = exactly 0 W / efficiency 1 are "
                       "enforced by the module (record shapes, the icp_rf_source plane and 'plane' only on "
                       "icp_rf_source are enforced by both). Generated by " + SCRIPT_REL + ".",
        "type": "object",
        "required": ["boundary_version", "configuration", "variant", "front_end", "loads", "efficiencies"],
        "additionalProperties": False,
        "properties": {
            "boundary_version": {"const": B.BOUNDARY_VERSION},
            "configuration": {"enum": list(B.CONFIGURATIONS)},
            "variant": {"type": "array", "uniqueItems": True,
                        "items": {"enum": sorted({o for c in B.CONFIGURATIONS for o in B.VARIANT_OPTIONS[c]})}},
            "label": {"type": "string"},
            "power_basis": {"enum": list(B.POWER_BASES)},
            "front_end": {"$ref": "#/$defs/front_end"},
            "loads": {"type": "object", "propertyNames": {"enum": list(B.ALL_SLOTS)},
                      "properties": {"icp_rf_source": {"$ref": "#/$defs/rf_load"}},
                      "additionalProperties": {"$ref": "#/$defs/load"}},
            "efficiencies": {"type": "object", "propertyNames": {"enum": list(B.ALL_SLOTS)},
                             "additionalProperties": {"$ref": "#/$defs/efficiency"}},
        },
        "$defs": {"load": num_or_tbd_load, "rf_load": rf_load, "efficiency": eff, "front_end": fe},
        "x-bus-power-boundary-a9": {
            "installed_slots": {c: list(B.BASE_SLOTS[c]) for c in B.CONFIGURATIONS},
            "variant_options": {c: list(B.VARIANT_OPTIONS[c]) for c in B.CONFIGURATIONS},
            "internal_bus_V": B.INTERNAL_BUS_V,
            "rfp_limit_W": B.P_BUS_REQUIREMENT_W,
        },
    }


# ------------------------------------------------------------------------------------------------------ markdown
def _c(v) -> str:
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:g}"
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False)
    return str(v).replace("|", "\\|").replace("\n", " ")


def _table(rows, cols) -> list:
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        out.append("| " + " | ".join(_c(r.get(c)) for c in cols) + " |")
    return out


def render_md(d: dict) -> str:
    L = [f"# A9-02 bus-power boundary `{d['boundary_version']}`", "",
         f"<!-- GENERATED by {d['generated_by']} from bus_power_boundary_a9_v1.json; do not edit by hand -->", "",
         "| item | value |", "|---|---|",
         f"| follow-on | `{d['follow_on']}` (trigger `{d['trigger']}`, owner decision A9) |",
         f"| status | {d['status']} |", f"| base commit | `{d['base_commit']}` |",
         f"| module | `{d['module']}` (pure, not wired into archengine) |",
         f"| schema | `{d['schema_file']}` |", f"| regenerate | `{d['regenerate']}` |",
         f"| configurations | {', '.join('`' + c + '`' for c in d['configurations'])} |",
         f"| historical v1 (byte-identical) | `{d['historical_boundary_untouched']['path']}` "
         f"`{d['historical_boundary_untouched']['sha256']}` |", "",
         "**What this is not.** " + " ".join(f"({i + 1}) {t}." for i, t in enumerate(d["what_this_is_not"])), "",
         "Decision pins (immutable, sha256): " + "; ".join(f"`{p['path']}` `{p['sha256']}`" for p in d["decision_pins"]),
         "", "Other pinned inputs: " + "; ".join(f"`{p['path']}` `{p['sha256']}`" for p in d["pinned_inputs"]), "",
         "## (a) Items / parameters", ""]
    L += _table(d["items"], ["id", "name", "value", "units", "basis", "source", "evidence_class", "status",
                             "freeze_point"])
    L += ["", "## Slots and configuration matrix", ""]
    rows = [dict(s, **{c: s["configurations"][c] for c in d["configurations"]}) for s in d["slots"]]
    L += _table(rows, ["slot", "group"] + d["configurations"] + ["common_allocation", "controls_thermal", "rows",
                                                                   "load_plane"])
    L += ["", "## RF power planes (row 72)", ""]
    L += _table(d["rf_power_planes"], ["plane", "crosses_bus_boundary", "role", "measured_by"])
    ba = d["bus_architecture"]
    L += ["", "## Bus architecture and ledger rule", ""] + [f"- **{k}**: {_c(v)}" for k, v in ba.items()]
    g = d["gates_and_allocations"]
    L += ["", "## Gate and allocation checks", "",
          f"- RFP gate: P_bus < {g['rfp_gate']['limit_W']:g} W (strict), steady AND every start-up step (row 108); "
          f"verdicts {', '.join(g['rfp_gate']['verdicts'])}.",
          f"- Transient basis: averaging window {g['rfp_gate']['transient_window']['status']} "
          f"({g['rfp_gate']['transient_window']['item']}, {g['rfp_gate']['transient_window']['owner_question']}, "
          f"{g['rfp_gate']['transient_window']['freeze_point']}); a start-up step PASSes only when declared "
          f"`{g['rfp_gate']['startup_pass_requires_power_basis']}`, otherwise NOT_EVALUABLE; every gate result carries "
          f"`transient_window_frozen = False`.",
          f"- Design allocation {g['design_allocation']['limit_W']:g} W (row 109): owner allocation check.",
          f"- Common allocation {g['common_allocation']['limit_W']:g} W incl. "
          f"{g['common_allocation']['controls_thermal_allowance_W']:g} W controls/thermal (row 114): owner "
          f"allocation check.", "", "## Start-up sequencing (revised SEQ-1, row 112)", ""]
    L += [f"- {r}" for r in d["sequencing"]["rules"]]
    L += [f"- enforced order: " + "; ".join(f"`{c}`: " + ", ".join(f"{a} < {b}" for a, b in v)
                                             for c, v in d["sequencing"]["enforced_order"].items()), ""]
    for c, steps in d["sequencing"]["templates_PROPOSED"].items():
        L += [f"### `{c}` (PROPOSED template)", ""]
        L += _table(steps, ["step_id", "name", "event", "on", "requires_flags", "phase"]) + [""]
    L += ["## (b) Interface demands", ""]
    L += _table(d["interface_demands"], ["from", "to", "quantity", "value", "units", "status"])
    L += ["", "### H2-4 items superseded / needing revision", ""]
    L += _table(d["h2_4_revision_flags"], ["h2_4_id", "name", "disposition", "why"])
    L += ["", "## (c) Owner answers applied", ""]
    L += _table(d["owner_answers_applied"], ["row", "covers_ids", "how_applied", "owner_answer_verbatim"])
    L += ["", "## (d) Open owner questions (new)", ""]
    L += _table(d["open_owner_questions"], ["id", "question", "proposed_answer", "freeze_point"])
    L += ["", "## (e) Historical reuse", ""]
    L += _table(d["historical_reuse"], ["artifact", "sha256", "reused", "not_reused"])
    L += ["", "## (f) M16 impact", ""]
    L += _table(d["m16_impact"], ["m16_row", "key", "name", "how_touched"])
    L += ["", "## (g) H3 / H4 inputs", ""]
    L += _table(d["h3_inputs"], ["id", "item", "basis", "note"]) + [""]
    L += _table(d["h4_inputs"], ["id", "stage", "measure", "closes"])
    L += ["", "## Compliance", "", f"`{json.dumps(d['compliance'], sort_keys=True)}`", ""]
    return "\n".join(L)


def dumps(d: dict) -> str:
    return json.dumps(d, indent=1, ensure_ascii=False) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="verify the committed outputs reproduce byte-for-byte")
    a = ap.parse_args(argv)
    d = build(load_inputs())
    outs = {OUT_JSON: dumps(d), OUT_MD: render_md(d), OUT_SCHEMA: dumps(build_schema())}
    if a.check:
        bad = []
        for p, txt in outs.items():
            if not os.path.isfile(p) or open(p, encoding="utf-8").read() != txt:
                bad.append(os.path.relpath(p, ROOT))
        if bad:
            print("DRIFT: " + ", ".join(bad))
            return 1
        print("OK")
        return 0
    for p, txt in outs.items():
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(txt)
    print("wrote " + ", ".join(os.path.relpath(p, ROOT) for p in outs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
