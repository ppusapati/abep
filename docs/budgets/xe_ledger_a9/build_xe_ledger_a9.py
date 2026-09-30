#!/usr/bin/env python3
"""A9-08 Xe ledger update for the Hall + downstream RF-ICP neutralizer investigation (xe_ledger_a9_v1).

Follow-on ``fo_a9_08_xe_ledger_update`` (trigger ``T_A9_08_XE_LEDGER_UPDATE``; owner decision A9 and the A9.1 follow-up
decisions, step 2). Deterministic, standard library only, no Julia, well under a second.

What it does
  * verifies the sha256 of every pinned immutable input (A4..A7, A9, the 147 owner answers and their verbatim pack,
    the A9.1 follow-up decisions and their verbatim pack, the verified deliverables it reads, and the two NIST WebBook
    isotherm snapshots stored next to this script) and refuses to run on any mismatch (no fallback);
  * checks that the v1 Xe ledger (the pure module in abep_sim and the docs/budgets v1 deliverable) is byte-identical to
    the base: it is imported read-only and never edited;
  * books every Xe use per configuration (``hall_c1_reference`` / ``hall_icp_neutralizer``), per ICP gas mode (G-REUSE
    primary; G-ATM and G-XE declared contingency variants) and per ledger (FLIGHT / GROUND_TEST) under the owner's
    PHASE_TOTAL_FLOW convention (row 42), evaluating each product term with the v1 module's unit/validation functions;
  * refuses every total that still has a TBD input (no hidden defaults, CLAUDE.md rule 3) and reports floors on the
    closed terms only, labelled as floors;
  * evaluates the owner's 2 / 5 / 10 kg design cases (row 48) for tank volume at 323.15 K from the NIST WebBook
    (Lemmon & Span 2006 equation of state) over an explicit MEOP axis, and for the head-room each case leaves after the
    closed terms, the 20 % reserve (row 43) and the single 2 % residual line (row 45);
  * writes xe_ledger_a9_v1.json and XE_LEDGER_A9.md (generated from the JSON).

What it is not: a Xe allocation (row 48: no single mission load is frozen), a prediction of any Hall, neutralizer or
plasma quantity (no Hall transport closure is admitted; the superseded 0-D Hall model and the withdrawn v1.2-v1.6
numbers are never used), an architecture ranking or a winner. It is not wired into archengine (goldens do not move).

    python docs/budgets/xe_ledger_a9/build_xe_ledger_a9.py          # (re)write the JSON and the Markdown
    python docs/budgets/xe_ledger_a9/build_xe_ledger_a9.py --check  # exit 1 unless both are reproduced byte for byte
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from abep_sim import xe_ledger as xl  # noqa: E402  (v1 pure module, imported read-only)

LANE_REL = "docs/budgets/xe_ledger_a9"
SCRIPT_REL = f"{LANE_REL}/build_xe_ledger_a9.py"
JSON_NAME = "xe_ledger_a9_v1.json"
MD_NAME = "XE_LEDGER_A9.md"
TEST_REL = "tests/test_xe_ledger_a9.py"
SCHEMA_ID = "xe_ledger_a9_v1"
BASE_COMMIT = "2625fe567b48c581232bbaf33a057f352f6963e6"
DATE = "2026-09-30"
CONFIGS = ("hall_c1_reference", "hall_icp_neutralizer")
GAS_MODES = ("G-REUSE", "G-ATM", "G-XE")
LEDGERS = ("FLIGHT", "GROUND_TEST")
FREEZE_POINTS = ("NOW", "LOCK-1", "LOCK-2", "after-evidence")
# The v1 module's vocabulary plus the owner-allocation class used by the A9 lanes (docs/EVIDENCE.md discipline).
EVIDENCE_CLASSES = tuple(xl.EVIDENCE_CLASSES) + ("owner-allocation",)

# ------------------------------------------------------------------------------------------------ pinned inputs
DECISIONS = {
    "A9": ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer.json",
           "74ef1a727c3656841ef115122c6d60865f7d2d93cfa29f7fb0081886484d2a1f", "governing owner decision A9"),
    "ANS": ("docs/decisions/OD_2026_09_29_owner_answers_147.json",
            "50e39a4deac7d4ada4710b2f641d717f1c4febd59366cbc04d8c66de6b4532b1", "147 owner answers (machine-readable)"),
    "PACK": ("docs/decisions/OD_2026_09_29_OWNER_DECISION_PACK_147.md",
             "8736d88a64bf26bd06a332a68c2450a780f175fffafe5aca0625759133666976", "147 owner answers (verbatim pack)"),
    "A91": ("docs/decisions/OD_2026_09_30_A9_1_followup_owner_decisions.json",
            "7a8f93dbc2487de90ebba0b2801fc5d3f5d983fc96ba418b55c492f1f9e851a4", "A9.1 follow-up owner decisions"),
    "A91MD": ("docs/decisions/OD_2026_09_30_A9_1_FOLLOWUP_OWNER_DECISIONS.md",
              "2587ca6931f6c9dac865005db9dc518dab0fcb829d789293467dc4179879c46e", "A9.1 follow-up (verbatim)"),
    "A4": ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A4_owner_decisions.json",
           "beec91f9eca3ca0257c5ee88dcd193c87481660b9368b65c6d10b3b3bdae23b4", "A4 (immutable, still binding)"),
    "A5": ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_architecture.json",
           "0554136751f5ffc7bd7f62c1c4723acce946ef4f523f43687b95710cc8ace621",
           "A5 xe_mass_allocation (C1 cathode design target 0.10 mg/s; 0.15 mg/s test point only)"),
    "A6": ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A6_a5_followon_authorization.json",
           "aaeb7c503c3791f81d4c589e8e25289befa6fcb3b16ce6f962b153715c883180",
           "A6 (Xe ledger formulas; no total Xe mass frozen)"),
    "A7": ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A7_execution_model.json",
           "dae69983d9aeeb4838d9ff973a5f824c973219f8cc528adfb12717c4bb92c925", "A7 execution model (M16 scheduler)"),
}
DELIVERABLES = {
    "XEMOD": ("abep_sim/xe_ledger.py", "8a89fa7da7e7eb7f786a7327e1721ea29c59db7c0721ea64646f812bd4afedf0",
              "v1 parametric Xe ledger module (imported read-only; must stay byte-identical)"),
    "XEV1": ("docs/budgets/xe_ledger/xe_ledger_v1.json",
             "965fdafa60ae9c3ee1e36189f22ef00198ae3f8a906696213bec13bdcbfb09ad", "v1 Xe ledger (must stay byte-identical)"),
    "XEV1MD": ("docs/budgets/xe_ledger/XE_LEDGER.md",
               "7fdded2baffa39a2cabc9ecdb746cca71dcea9ca80b841f05b5e94a6eb0af6a2", "v1 Xe ledger document"),
    "XEV1PY": ("docs/budgets/xe_ledger/build_xe_ledger.py",
               "cae5911429cf1131e75fde67217ceedbb87cfd103ef11be06625e007d73100df", "v1 Xe ledger builder"),
    "H22": ("docs/hardware/h2/h2_2_cathode_integration/h2_2_cathode_integration_v1.json",
            "8436008ac458d4e7467a9c7c9592d5312b3912b918d584ceaf3ac8cb2745a971", "H2-2 C-1 integration (verified)"),
    "H23": ("docs/hardware/h2/h2_3_gas_path_plenum/h2_3_gas_path_plenum_v1.json",
            "f32b05bd03aad2a09a1d9b90ee5f9423e733e6ea4cb94814c92b500590d43a7b", "H2-3 gas path / plenum (verified)"),
    "H27": ("docs/hardware/h2/h2_7_mechanical_bom/h2_7_mechanical_bom_v1.json",
            "d1813e153af37ebd45cb2ead964ead6c53c756d1a82f93ea89346a83168d0630", "H2-7 mechanical / mass BOM (verified)"),
    "BPB": ("docs/architecture_comparison/power_boundary_a9/bus_power_boundary_a9_v1.json",
            "1a3c8d29404d464816f0e306e2883993a52f3094a26656937203a816dd6701df", "A9-02 bus-power boundary (verified)"),
    "ICD": ("schemas/interfaces/icp_neutralizer_icd_v1.json",
            "1cdab3d71377443d41f128398159ba5ac0203d9daaca8c77840cea6fcd9a353c", "A9-03 ICP-neutralizer ICD (verified)"),
    "PRE": ("docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json",
            "f3e6069a4c78c49822f9248d9b9bc34a157a349bf601f7065e5e182645fbd245", "A9-01 prereg framework (verified)"),
    "UB": ("docs/experiments/hall_icp/uncertainty_budget/hall_icp_uncertainty_budget_v1.json",
           "d1cf5aba0a813c676d48c3ac8741ddb3c00c31700428fbff1c0217a5ee2d92d1", "A9-04 uncertainty budget (verified)"),
    "VI": ("docs/experiments/hall_icp/validation_inputs/hall_icp_validation_inputs_v1.json",
           "1de411c5f09d96698e87ec22bdba796b5c2010ad4f0362afb5a4fd2eec9b9527", "A9-05 validation inputs (verified)"),
    "INT": ("docs/experiments/hall_icp/integration/a9_core_integration_v1.json",
            "20c222d9b8a65930789c767ed45127041c7b1cd06e21a715101761036bb5f2ca", "A9 core integration (verified)"),
    "M16": ("docs/budgets/subsystem_maturity/subsystem_maturity_v2.json",
            "a82b1acd118b26e89edd4fa467bec778fa410470cca5eb6f684e6553eadaf23c", "M16 v2 subsystem maturity (verified)"),
    "R6": ("docs/procurement/web_track_v1/threads/R6_xe_inputs.json",
           "f8eda3db0419d56497a9e35b11e643d87549a1942e2d4677f53446a7c7c228cd", "web track R6 Xe inputs (verified)"),
    "MBOM": ("docs/architecture_comparison/mass_bom/mass_bom_v1.json",
             "8ab97ff93f507899508374d4ce8116e7066c31e3fbe2c79300f5b55372ba7313",
             "mass BOM v1 (residual policy 0.02 x xe_load, ESA R-M1-6)"),
}
NIST_URL_T = ("https://webbook.nist.gov/cgi/fluid.cgi?Action=Data&Wide=on&ID=C7440633&Type=IsoTherm&Digits=5&PLow=70"
              "&PHigh=200&PInc=1&T={T}&RefState=DEF&TUnit=K&PUnit=bar&DUnit=kg%2Fm3&HUnit=kJ%2Fkg&WUnit=m%2Fs"
              "&VisUnit=uPa*s&STUnit=N%2Fm")
SNAPSHOTS = {
    "NIST323": (f"{LANE_REL}/sources/nist_webbook_xe_isotherm_323.15K_70-200bar.tsv",
                "190f8d574000a3e023677d17c7275e3498ca8a324955365b1205f6e40af9e376",
                "NIST WebBook SRD 69 xenon isotherm 323.15 K, 70-200 bar (1 bar steps); accessed 2026-09-30",
                NIST_URL_T.format(T="323.15")),
    "NIST300": (f"{LANE_REL}/sources/nist_webbook_xe_isotherm_300K_70-200bar.tsv",
                "0406d76581db0476ceaea74a8f8c9179c3b07b31f0f8ad90db42154008930633",
                "NIST WebBook SRD 69 xenon isotherm 300 K, 70-200 bar (contrast only; never used for sizing, row 50); "
                "accessed 2026-09-30", NIST_URL_T.format(T="300")),
}
NIST_EOS = {
    "citation": "Lemmon, E.W.; Span, R., Short Fundamental Equations of State for 20 Industrial Fluids, J. Chem. Eng. "
                "Data 51(3), 785-850 (2006), doi:10.1021/je050186n (as cited on the NIST WebBook xenon fluid page, "
                "accessed 2026-09-30)",
    "stated_uncertainty": "'The uncertainties in the equation of state are 0.2% in density up to 100 MPa, rising to 1% at "
                          "higher pressures' (NIST WebBook xenon fluid page, 'Equation of state' note, accessed 2026-09-30)",
    "evidence_class": "model-derived",
}
NEVER_PINNED = ("docs/orchestration/lane_registry_v1.json", "docs/orchestration/trigger_registry_v1.json",
                "docs/orchestration/trigger_ledger_v2.jsonl", "docs/orchestration/fired_triggers.jsonl",
                "docs/orchestration/runtime_state.json")
PENDING = {
    "A9-06": "PENDING docs/budgets/mass_a9/ (A9-06 mass reconciliation; parallel lane, not in the base)",
    "A9-07": "PENDING docs/hardware/h2_a9_revisions/ (A9-07 H2 revisions; parallel lane, not in the base)",
    "A9-09": "PENDING docs/procurement/rfq_a9/ (A9-09 RFQ packages; parallel lane, not in the base)",
    "A9-10": "PENDING A9-10 reconciliation / M16 refresh (after A9-06..09; no path yet)",
}
HISTORICAL = {
    "phase1_prereg_framework": ("docs/experiments/phase1_prereg_framework/phase1_prereg_framework_v1.json",
                                "84ba1c382dc609b3e83ad9803a57ba471dd892fd10a6a6149285701a45a65a28"),
    "preionizer_module_icd": ("schemas/interfaces/preionizer_module_icd_v1.json",
                              "2470718e1decbde874d2362a997d1e2aaae54eb855d1ed179b930c3be6e7130e"),
    "bus_power_boundary_v1": ("abep_sim/arch_boundary.py",
                              "8dfc309a5d2c717913fd4961bc660f8bab92ed2c59356f5a78bff3ef4392eeae"),
}


def sha256(rel: str) -> str:
    return hashlib.sha256((REPO / rel).read_bytes()).hexdigest()


def verify_pins() -> None:
    for table in (DECISIONS, DELIVERABLES, HISTORICAL):
        for key, entry in table.items():
            rel, want = entry[0], entry[1]
            if not (REPO / rel).is_file():
                raise RuntimeError(f"pinned input missing: {rel}")
            got = sha256(rel)
            if got != want:
                raise RuntimeError(f"pinned input changed: {rel} sha256 {got} != {want}")
    for key, (rel, want, _d, _u) in SNAPSHOTS.items():
        got = sha256(rel)
        if got != want:
            raise RuntimeError(f"source snapshot changed: {rel} sha256 {got} != {want}")


def load(key: str) -> dict:
    table = DECISIONS if key in DECISIONS else DELIVERABLES
    return json.loads((REPO / table[key][0]).read_text(encoding="utf-8"))


def r6(x):
    return None if x is None else float(f"{x:.6g}")


# ------------------------------------------------------------------------------------------------ owner basis
class Basis:
    """Owner answers (verbatim, by row), A9.1 decisions (by id) and the verified values this lane reads."""

    def __init__(self):
        ans = load("ANS")
        self.rows = {r["row"]: r for r in ans["answers"]}
        if len(self.rows) != 147:
            raise RuntimeError("owner answers file does not hold 147 rows")
        a91 = load("A91")
        self.a91 = a91["decisions"]
        self.a91_exec = a91["execution"]
        if a91["verbatim"]["sha256"] != DECISIONS["A91MD"][1]:
            raise RuntimeError("A9.1 json does not pin the verbatim md this lane pins")
        a9 = load("A9")
        if a9["status"] != "OWNER_AUTHORIZED_INVESTIGATION_HYPOTHESIS_NOT_FLIGHT_BASELINE":
            raise RuntimeError("A9 status changed")
        self.a9 = a9
        a5 = load("A5")
        xa = a5["xe_mass_allocation"]
        self.c1_target = xa["cathode_flow_design_target_mg_s"]
        self.c1_upper = xa["cathode_flow_experimental_upper_test_point_mg_s"]
        if (self.c1_target, self.c1_upper) != (0.10, 0.15):
            raise RuntimeError("A5 cathode flows changed")
        h22 = load("H22")
        self.h22 = {p["id"]: p for p in h22["design_parameters"]}
        if self.h22["H22-43"]["value"] != 0.2 or self.h22["H22-44"]["value"] != 1.0:
            raise RuntimeError("H2-2 controller full-scale values changed")
        self.h22_preheat = h22["derived"]["preheat_purge_xe"]["cases"]
        h27 = load("H27")
        self.h27_an = h27["analog_data"]
        self.h27_params = {p["id"]: p for p in h27["design_parameters"]}
        r6 = load("R6")
        getter = [e for p in r6["parameters"] for e in p.get("evidence", [])
                  if isinstance(e, dict) and "filter-getter" in str(e.get("conditions", ""))]
        if len(getter) < 1:
            raise RuntimeError("R6 filter-getter analog record not found")
        self.getter = getter[0]
        self.m16 = {r["row"]: r for r in load("M16")["rows"]}
        for row in (6, 7, 8, 11):
            if row not in self.m16:
                raise RuntimeError(f"M16 row {row} missing")
        pre = load("PRE")
        self.pre_dq = {q["id"]: q for q in pre["decision_quantities"]}
        if "DQ-HI-DXE" not in self.pre_dq:
            raise RuntimeError("A9-01 decision quantity DQ-HI-DXE missing")
        self.pre_stages = [s["id"] for s in pre["stage_map"]]
        if pre["configurations"]["ids"] != list(CONFIGS):
            raise RuntimeError("A9-01 configuration ids changed")

    def row(self, n: int) -> dict:
        return self.rows[n]

    def verbatim(self, n: int) -> str:
        return self.rows[n]["owner_answer_verbatim"]


ANS_REL = DECISIONS["ANS"][0]
A91_REL = DECISIONS["A91"][0]
A5_REL = DECISIONS["A5"][0]
H22_REL = DELIVERABLES["H22"][0]
H27_REL = DELIVERABLES["H27"][0]


def R(*rows) -> str:
    return f"{ANS_REL} row{'s' if len(rows) > 1 else ''} " + ", ".join(str(r) for r in rows)


def D(*ids) -> str:
    return f"{A91_REL} decisions." + ", decisions.".join(ids)


# ------------------------------------------------------------------------------------------------ items (a)
def P(pid, name, value, unit, kind, basis, source, ev, status, freeze, applies, requires=None, note=None):
    if value is None and not requires:
        raise ValueError(f"{pid}: a TBD item must name what closes it")
    if value is not None and ev not in EVIDENCE_CLASSES:
        raise ValueError(f"{pid}: evidence class {ev!r}")
    if freeze not in FREEZE_POINTS:
        raise ValueError(f"{pid}: freeze point {freeze!r}")
    d = {"id": pid, "name": name, "value": value, "unit": unit, "kind": kind, "basis": basis, "source": source,
         "evidence_class": ev if value is not None else "none", "status": status, "freeze_point": freeze,
         "applies_to": applies}
    if value is None:
        d["value_display"] = f"TBD - requires {requires}"
        d["requires"] = requires
    if note:
        d["note"] = note
    return d


def items(b: Basis) -> list:
    c1 = ["hall_c1_reference"]
    both = list(CONFIGS)
    it = [
        # --- C1 reference cathode (flight hall_c1_reference; ground hall_c1_reference installations)
        P("XA9-01", "C1 cathode firing-hours basis (flight cathode term)", 15000.0, "h", "time", "owner answer",
          f"{R(46)} ('15,000 h for the conventional C1 reference/fallback term'); {R(3)} (> 15,000 h firing kept as a "
          "provisional hard requirement until the official RFP confirms it)", "owner-allocation",
          "OWNER_BASIS (provisional per row 3)", "NOW", {"configs": c1, "ledgers": ["FLIGHT"]}),
        P("XA9-02", "C1 cathode Xe design flow", b.c1_target, "mg/s", "mass_flow", "owner allocation (A5)",
          f"{A5_REL} xe_mass_allocation.cathode_flow_design_target_mg_s; copied in {H22_REL} H22-42", "owner-allocation",
          "FIXED_DESIGN_TERM (A5 design target, not a demonstrated flow)", "after-evidence",
          {"configs": c1, "ledgers": ["FLIGHT"]},
          note="closes with the C1 measured spot-mode minimum flow (H22-50); the flow step of that search is row 92"),
        P("XA9-03", "C1 cathode Xe upper test point (sensitivity only)", b.c1_upper, "mg/s", "mass_flow",
          "owner allocation (A5)", f"{A5_REL} xe_mass_allocation.cathode_flow_experimental_upper_test_point_mg_s",
          "owner-allocation", "SENSITIVITY_ONLY (A5: experimental upper test point, never the allocation)",
          "after-evidence", {"configs": c1, "ledgers": ["FLIGHT"]}),
        P("XA9-04", "C1 steady-flow controller accuracy class (flow-uncertainty term)", 0.02, "1", "fraction",
          "owner answer", f"{R(96)} (conservative +-2 % FS class accepted as the Xe-ledger uncertainty term until S1a "
          f"demonstrates a better calibrated class on Xe); {H22_REL} H22-45", "owner-allocation",
          "OWNER_BASIS until S1a demonstrates a better class on Xe", "after-evidence",
          {"configs": c1, "ledgers": LEDGERS}),
        P("XA9-05", "C1 steady-flow controller full scale", b.h22["H22-43"]["value"], "mg/s", "mass_flow",
          "owner answer + H2-2 proposal", f"{R(125)} ('one high-accuracy 0.05-0.2 mg/s-class C1 steady-flow "
          f"controller'); {H22_REL} H22-43 (PROPOSED FS 0.2 mg/s Xe)", "owner-allocation",
          "OWNER_BASIS (class); instrument selection PENDING A9-09 RFQ", "LOCK-1", {"configs": c1, "ledgers": LEDGERS}),
        P("XA9-06", "C1 start/diode-flow controller full scale (only if 0.6-0.8 mg/s start flows are retained)",
          b.h22["H22-44"]["value"], "mg/s", "mass_flow", "owner answer + H2-2 proposal",
          f"{R(125)} ('a separate start/diode-flow controller if 0.6-0.8 mg/s is retained'); {H22_REL} H22-44 "
          "(PROPOSED FS 1.0 mg/s)", "owner-allocation", "CONDITIONAL (row 125)", "LOCK-1",
          {"configs": c1, "ledgers": LEDGERS}),
        P("XA9-07", "C1 ignition dwell bound per attempt", 120.0, "s", "time", "owner answer",
          f"{R(93)} ('cap each ignition dwell at 120 s ... in the preliminary protocol, then freeze the final bound "
          "before score-bearing C1 testing')", "owner-allocation", "PRELIMINARY_PROTOCOL_BOUND", "LOCK-2",
          {"configs": c1, "ledgers": LEDGERS}),
        P("XA9-08", "C1 ignition attempts per start (1 initial + at most 2 retries)", 3.0, "1", "count",
          "owner answer (reading PROPOSED, XA9Q-02)", f"{R(93)} ('allow at most two retries')", "owner-allocation",
          "PRELIMINARY_PROTOCOL_BOUND (conservative reading; XA9Q-02)", "LOCK-2", {"configs": c1, "ledgers": LEDGERS}),
        P("XA9-09", "C1 ignition Xe flow (vendor/design-qualified)", None, "mg/s", "mass_flow", "pending",
          f"{R(93)} ('Use the selected cathode vendor/design-qualified purge and ignition flow'); analog context "
          f"{H22_REL} H22-44 (heated starts 0.1-0.8 mg/s, analogs only)", None, "TBD", "after-evidence",
          {"configs": c1, "ledgers": LEDGERS}, requires="the selected C1 vendor/design-qualified ignition flow "
          f"(row 93; {PENDING['A9-07']}; {PENDING['A9-09']})"),
        P("XA9-10", "C1 purge Xe flow and purge duration per start", None, "mg/s; s", "mass_flow", "pending",
          f"{R(93)}; {H22_REL} H22-06 S2 (Xe purge before heating)", None, "TBD", "after-evidence",
          {"configs": c1, "ledgers": LEDGERS}, requires="the selected C1 vendor/design-qualified purge flow and "
          f"duration (row 93; {PENDING['A9-07']})"),
        P("XA9-11", "C1 preheat duration and Xe flow while the heater is on", None, "s; mg/s", "time", "pending",
          f"{H22_REL} derived.preheat_purge_xe (relation Xe per start = t_preheat x mdot_purge; analog t_preheat "
          f"200-1200 s, analogs only); {D('SEQ-heater')}", None, "TBD", "after-evidence",
          {"configs": c1, "ledgers": LEDGERS}, requires="the selected C1 heater procedure and the H-1/C-1 start "
          f"sequence with Xe logged per phase ({PENDING['A9-07']})"),
        P("XA9-12", "C1 spot-mode minimum-flow search step", 0.005, "mg/s", "mass_flow", "owner answer",
          f"{R(92)} ('ADOPT 0.005 mg/s flow-step resolution ... with preregistered stopping criteria')",
          "owner-allocation", "OWNER_BASIS", "NOW", {"configs": c1, "ledgers": ["GROUND_TEST"]}),
        P("XA9-13", "C1 spot-mode search: steps, dwell per step, searches per campaign", None, "1; s; 1", "count",
          "pending", f"{R(92)} (stopping criteria preregistered)", None, "TBD", "LOCK-1",
          {"configs": c1, "ledgers": ["GROUND_TEST"]},
          requires="the preregistered stopping rule (LOCK-1) and the campaign schedule (LOCK-2)"),
        # --- starts, transitions, Hall Xe operation (both configurations)
        P("XA9-14", "flight starts N_starts", None, "1", "count", "pending", f"{R(24)} (restart / cycle count recorded)",
          None, "TBD", "after-evidence", {"configs": both, "ledgers": ["FLIGHT"]},
          requires="the mission operations concept (eclipse/duty cycling, anomaly restarts) and FDIR restart policy"),
        P("XA9-15", "Hall discharge ignition gas and its Xe flow x dwell (if the Hall is ignited on Xe)", None,
          "mg/s; s", "mass_flow", "pending", f"{DELIVERABLES['BPB'][0]} start-up templates C-S5 / I-S5 (gas not "
          "stated)", None, "TBD", "after-evidence", {"configs": both, "ledgers": LEDGERS},
          requires=f"the revised start sequence stating whether the Hall discharge ignites on Xe ({PENDING['A9-07']}) "
          "and H-1 start measurements with Xe logged per phase"),
        P("XA9-16", "Xe-to-atmosphere transitions: count, duration, total Xe flow", None, "1; s; mg/s", "count",
          "pending", "v1 Xe ledger m_transition (N_transitions x t_transition x mdot_transition)", None, "TBD",
          "after-evidence", {"configs": both, "ledgers": LEDGERS},
          requires="H-1 transition measurement with Xe logged per phase and the operations concept"),
        P("XA9-17", "Xe fallback operation (Hall on Xe when the atmospheric path is unavailable): hours and flow",
          None, "h; mg/s", "time", "pending", "v1 Xe ledger m_fallback (t_fallback_max x mdot_fallback)", None, "TBD",
          "after-evidence", {"configs": both, "ledgers": ["FLIGHT"]},
          requires="the FDIR fallback policy and an H-1 Xe operating point measured on the actual H-1"),
        P("XA9-18", "bounded functional Xe-capable mode (row 6): events, duration, total Xe flow", None,
          "1; h; mg/s", "count", "owner answer (existence) / pending (size)",
          f"{R(6)} ('bounded functional Xe mode ... need not be continuous nominal operation; book every Xe use "
          "explicitly')", None, "TBD", "after-evidence", {"configs": both, "ledgers": ["FLIGHT"]},
          requires="the official RFP wording (row 1) and an owner bound on the Xe-mode duration, plus an H-1 Xe "
          "operating point measured on the actual H-1"),
        P("XA9-19", "Xe-augmented peak operation in flight (only if the RFP permits)", None, "1; h; mg/s", "count",
          "owner answer (conditional)", f"{R(4, 26)}", None, "TBD (CONDITIONAL_ON_RFP)", "after-evidence",
          {"configs": both, "ledgers": ["FLIGHT"]},
          requires="the official RFP (row 1) permitting Xe for the 25 mN capability, and a measured H-1 Xe peak point"),
        P("XA9-20", "flow-control accuracy class for the non-C1 Xe flows (Hall Xe modes, G-XE ICP feed)", None, "1",
          "fraction", "pending", f"{R(96)} covers the C1 steady controller only", None, "TBD", "LOCK-1",
          {"configs": both, "ledgers": LEDGERS},
          requires=f"the anode-side / ICP-feed Xe flow controller selection and its Xe calibration ({PENDING['A9-09']})"),
        # --- ICP gas (HIQ-06 / OQ-A902-05)
        P("XA9-21", "ICP dedicated Xe flow in the primary gas mode G-REUSE", 0.0, "mg/s", "mass_flow",
          "owner decision", f"{D('HIQ-06', 'HIQ-06_accounting', 'OQ-A902-05')}; A9.1 step_2_parallel.A9-08 "
          "('G-REUSE: m_Xe,ICP = 0, no dedicated atmospheric feed')", "owner-allocation",
          "OWNER_DECISION (exact zero; Hall exhaust is never counted again as ICP propellant)", "NOW",
          {"configs": ["hall_icp_neutralizer"], "ledgers": LEDGERS, "gas_modes": ["G-REUSE"]}),
        P("XA9-22", "ICP dedicated Xe (G-XE contingency variant): events, duration, flow", None, "1; s; mg/s",
          "count", "owner decision (variant exists) / pending (size)", f"{D('HIQ-06', 'HIQ-06_accounting')} "
          "('mdot_ICP,Xe booked explicitly in the Xe ledger under PHASE_TOTAL_FLOW')", None, "TBD", "after-evidence",
          {"configs": ["hall_icp_neutralizer"], "ledgers": LEDGERS, "gas_modes": ["G-XE"]},
          requires="a G-XE variant actually installed/used after the preregistered ICP-capacity gate fails in G-REUSE "
          "(HIQ-06), with the ICP feed flow measured (ICP-45 records gas state)"),
        # --- reserve, residual
        P("XA9-23", "reserve fraction of planned non-reserve mission Xe", 0.20, "1", "fraction",
          "ASSUMED_ENGINEERING_ALLOCATION", f"{R(43)}", "owner-allocation",
          "ASSUMED_ENGINEERING_ALLOCATION (revisit after the mission mode profile is measured)", "after-evidence",
          {"configs": both, "ledgers": ["FLIGHT"]}),
        P("XA9-24", "residual (unusable) Xe fraction of the usable load (one separate ledger line)", 0.02, "1",
          "fraction", "owner answer + mass-BOM convention", f"{R(45)}; base convention 0.02 x xe_load "
          f"({DELIVERABLES['MBOM'][0]}, ESA R-M1-6)", "owner-allocation",
          "OWNER_BASIS (single line, exported to the mass BOM)", "NOW", {"configs": both, "ledgers": ["FLIGHT"]}),
        # --- tank sizing
        P("XA9-25", "maximum storage temperature for tank sizing", 323.0, "K", "temperature", "owner answer",
          f"{R(50)}; evaluated on the 323.15 K NIST isotherm (0.15 K above 323 K: slightly lower density, "
          "conservative for volume)", "owner-allocation", "OWNER_BASIS", "NOW", {"configs": both, "ledgers": ["FLIGHT"]}),
        P("XA9-26", "Xe equation of state (density at 323.15 K)", "NIST WebBook SRD 69 isotherm snapshot", "kg m^-3",
          "density", "published reference EOS", f"{SNAPSHOTS['NIST323'][0]} ({NIST_EOS['citation']})",
          "model-derived", "VERIFIED_SOURCE (snapshot sha256-pinned)", "NOW", {"configs": both, "ledgers": ["FLIGHT"]}),
        P("XA9-27", "EOS density relative uncertainty (<= 100 MPa)", 0.002, "1", "fraction", "published statement",
          NIST_EOS["stated_uncertainty"], "model-derived", "VERIFIED_SOURCE", "NOW",
          {"configs": both, "ledgers": ["FLIGHT"]}),
        P("XA9-28", "tank MEOP", None, "bar", "pressure", "pending", f"{R(50)} (MEOP explicit input); H2-7 H27-34 "
          "(PROPOSED >= 75 bar was a 293.15 K capacity check)", None, "TBD", "LOCK-1",
          {"configs": both, "ledgers": ["FLIGHT"]},
          requires=f"tank quotation/selection ({PENDING['A9-09']}) and the owner's MEOP choice; the design-case tables "
          "carry an explicit MEOP axis meanwhile"),
        P("XA9-29", "tank proof and burst pressure factors", None, "1", "fraction", "pending",
          f"{R(50)} (safety factors explicit inputs)", None, "TBD", "LOCK-1", {"configs": both, "ledgers": ["FLIGHT"]},
          requires="the owner's choice of the applicable pressure-vessel standard (e.g. ECSS-E-ST-32-02 - verify; "
          "not accessed in this lane) and the launcher requirements"),
        P("XA9-30", "Xe design cases for tank/interface sizing (loaded Xe mass)", [2.0, 5.0, 10.0], "kg", "mass",
          "owner answer", f"{R(48)} ('Run explicit 2 kg / 5 kg / 10 kg design cases ... freeze the mission load only "
          "after the required Xe operating modes and duty cycle are established')", "owner-allocation",
          "DESIGN_CASES (no single mission load frozen)", "after-evidence", {"configs": both, "ledgers": ["FLIGHT"]}),
        # --- filter/getter
        P("XA9-31", "C1-line filter/getter heater power class (C1/Xe branch only)", None, "W", "power",
          "owner answer (scope) / pending (value)", f"{R(51)}; analog '{b.getter['value']}' "
          f"({DELIVERABLES['R6'][0]} source {b.getter['source_id']}, {b.getter['locator']}; analog, developer spec)",
          None, "TBD (<= 17 W class only after vendor/spec verification)", "after-evidence",
          {"configs": c1, "ledgers": LEDGERS},
          requires=f"vendor/spec verification of the selected filter/getter (row 51; {PENDING['A9-09']})"),
        P("XA9-32", "C1-line filter/getter mass and pressure drop", None, "kg; bar", "mass", "pending", f"{R(51)}",
          None, "TBD", "after-evidence", {"configs": c1, "ledgers": LEDGERS},
          requires=f"vendor/spec verification ({PENDING['A9-09']}); mass booked by A9-06 ({PENDING['A9-06']})"),
        # --- ground-test ledger
        P("XA9-33", "XE_REFERENCE health check per installation: duration and total Xe flow", None, "s; mg/s", "time",
          "owner decision (existence, placement) / pending (size)", f"{D('HIQ-03')}; {R(26)}", None, "TBD", "LOCK-2",
          {"configs": both, "ledgers": ["GROUND_TEST"]},
          requires="the bounded Xe reference procedure (rule at LOCK-1, values at LOCK-2) and the measured H-1 Xe "
          "reference flow"),
        P("XA9-34", "installations with an XE_REFERENCE check (count)", None, "1", "count", "pending",
          f"{R(19)} (min. three complete engineering replicate sets; n at LOCK-2); {D('HIQ-02')}", None, "TBD",
          "LOCK-2", {"configs": both, "ledgers": ["GROUND_TEST"]},
          requires="the LOCK-2 block count n and the installation schedule (HIQ-02: >= 6 blocks before any larger n)"),
        P("XA9-35", "XE_AUGMENTED_PEAK test points: count, dwell, flow", None, "1; s; mg/s", "count",
          "owner answer (conditional)", f"{R(26)}", None, "TBD (CONDITIONAL_ON_RFP)", "LOCK-2",
          {"configs": both, "ledgers": ["GROUND_TEST"]},
          requires="RFP permission (row 26 'if permitted by the RFP') and the preregistered point list"),
        P("XA9-36", "C1 ground starts and C1 Xe-on hours per campaign", None, "1; h", "count", "pending",
          f"{D('HIQ-01')} (hall_c1_reference in every block)", None, "TBD", "LOCK-2",
          {"configs": c1, "ledgers": ["GROUND_TEST"]}, requires="the LOCK-2 schedule (installations, blocks, retries)"),
        P("XA9-37", "ground-test Xe supply margin", None, "1", "fraction", "owner call", "no owner answer covers it",
          None, "TBD (owner call XA9Q-04)", "LOCK-2", {"configs": both, "ledgers": ["GROUND_TEST"]},
          requires="owner decision XA9Q-04"),
        # --- context gates
        P("XA9-38", "system mass gate (wet, incl. Xe load and tank)", 40.0, "kg", "mass", "RFP + owner reading",
          f"{R(5)} ('INCLUDES Xe + tank')", "owner-allocation", "HARD_GATE (full system; A9-06 books it)", "NOW",
          {"configs": both, "ledgers": ["FLIGHT"]}),
        P("XA9-39", "screening cap: share of 40 kg taken by the stored-Xe subsystem", 0.25, "1", "fraction",
          "owner answer", f"{R(44)} ('0.25 only as a screening cap, not an entitlement')", "owner-allocation",
          "SCREENING_CAP (not an entitlement)", "NOW", {"configs": both, "ledgers": ["FLIGHT"]}),
        P("XA9-40", "mission life basis (context; the C1 cathode term uses firing hours, XA9-01)", 26280.0, "h",
          "time", "owner answer", f"{R(3)}", "owner-allocation", "ENGINEERING_BASIS until the RFP wording is verified",
          "NOW", {"configs": both, "ledgers": ["FLIGHT"]}),
        P("XA9-41", "C1 ground cathode-flow setpoints (booking flow over the C1 Xe-on hours)", None, "mg/s",
          "mass_flow", "pending", f"{D('HIQ-01')}; {R(92)}", None, "TBD", "LOCK-2",
          {"configs": c1, "ledgers": ["GROUND_TEST"]},
          requires="the C1 test procedure setpoints and the LOCK-2 schedule (flows under test, not the A5 flight "
                   "design flow)"),
    ]
    ids = [x["id"] for x in it]
    if len(ids) != len(set(ids)):
        raise RuntimeError("duplicate item id")
    return it


# ------------------------------------------------------------------------------------------------ terms
# field record: (name, kind, item id). A field value is taken from the item unless the scenario overrides it.
PRESENT, ZERO, ABSENT, COND = "PRESENT", "ZERO_BY_OWNER_DECISION", "ABSENT_BY_OWNER_DECISION", "CONDITIONAL"


def T(tid, name, ledger, phase, formula, fields, configs, rows, decisions=(), gas=None, kind="product", label=None,
      note=None):
    return {"id": tid, "name": name, "ledger": ledger, "phase": phase, "formula": formula,
            "fields": [{"name": f[0], "kind": f[1], "item": f[2]} for f in fields], "configs": configs,
            "gas_mode_rule": gas, "kind": kind, "owner_rows": list(rows), "a9_1_decisions": list(decisions),
            "label": label, "note": note}


C1_ONLY = {"hall_c1_reference": PRESENT, "hall_icp_neutralizer": ABSENT}
BOTH = {"hall_c1_reference": PRESENT, "hall_icp_neutralizer": PRESENT}
BOTH_COND = {"hall_c1_reference": COND, "hall_icp_neutralizer": COND}
ICP_ONLY = {"hall_c1_reference": ABSENT, "hall_icp_neutralizer": PRESENT}
C1_ABSENT_WHY = ("OQ-A902-04: no combined flight C1 + ICP installation in primary A9; row 46: the ICP-neutralizer "
                 "architecture has no continuous C1-Xe cathode term")


def terms() -> list:
    f_start = ("N_starts", "count", "XA9-14")
    return [
        # ---------------- FLIGHT
        T("F-C1-PURGE", "C1 Xe purge before heating", "FLIGHT", "purge",
          "N_starts x t_purge x mdot_purge", [f_start, ("t_purge", "time", "XA9-10"),
                                               ("mdot_purge", "mass_flow", "XA9-10")], C1_ONLY, (42, 93)),
        T("F-C1-PREHEAT", "C1 preheat under Xe flow (heater on)", "FLIGHT", "preheat",
          "N_starts x t_preheat x mdot_preheat", [f_start, ("t_preheat", "time", "XA9-11"),
                                                   ("mdot_preheat", "mass_flow", "XA9-11")], C1_ONLY, (42,),
          ("SEQ-heater",)),
        T("F-C1-IGN", "C1 keeper ignition dwell (bounded: <= 120 s per attempt, <= 2 retries)", "FLIGHT",
          "ignition", "N_starts x n_attempts_max x t_dwell_max x mdot_ign",
          [f_start, ("n_attempts_max", "count", "XA9-08"), ("t_dwell_max", "time", "XA9-07"),
           ("mdot_ign", "mass_flow", "XA9-09")], C1_ONLY, (42, 93),
          label="booked at the protocol bound (upper bound per start), not an expected dwell"),
        T("F-C1-CATHODE", "C1 keeper/cathode steady flow over the firing hours", "FLIGHT", "keeper_cathode",
          "mdot_cathode x t_firing", [("mdot_cathode", "mass_flow", "XA9-02"), ("t_firing", "time", "XA9-01")],
          C1_ONLY, (42, 46), note="identical to the v1 m_cathode term (A5/A6); evaluated with the v1 module"),
        T("F-C1-FLOWUNC", "C1 steady-flow controller uncertainty term (+-2 % FS class, booked additively)", "FLIGHT",
          "keeper_cathode", "u_FS x FS x t_firing", [("u_FS", "fraction", "XA9-04"), ("FS", "mass_flow", "XA9-05"),
                                                      ("t_firing", "time", "XA9-01")], C1_ONLY, (96, 125),
          label="conservative booking of the flow-class bound (XA9Q-03)"),
        T("F-HALL-XE-START", "Hall discharge ignition on Xe (anode-side + electron-source Xe, if Xe is used)",
          "FLIGHT", "ignition", "N_starts x t_hall_ign x mdot_hall_ign",
          [f_start, ("t_hall_ign", "time", "XA9-15"), ("mdot_hall_ign", "mass_flow", "XA9-15")], BOTH_COND, (42,),
          label="CONDITIONAL on the Hall being ignited on Xe (start sequence PENDING A9-07)"),
        T("F-TRANSITION", "Xe-to-atmosphere transition (total Xe flow during the phase)", "FLIGHT", "transition",
          "N_transitions x t_transition x mdot_transition",
          [("N_transitions", "count", "XA9-16"), ("t_transition", "time", "XA9-16"),
           ("mdot_transition", "mass_flow", "XA9-16")], BOTH, (42,)),
        T("F-XE-FALLBACK-OP", "Xe fallback operation of the Hall (atmospheric path unavailable)", "FLIGHT", "fallback",
          "t_fallback_max x mdot_fallback", [("t_fallback_max", "time", "XA9-17"),
                                              ("mdot_fallback", "mass_flow", "XA9-17")], BOTH, (42,),
          note="the C1 *configuration* as fallback to the ICP is an architecture choice, not an in-flight term "
               "(OQ-A902-04)"),
        T("F-XE-FUNCTIONAL", "bounded functional Xe-capable mode (row 6)", "FLIGHT", "xe_mode",
          "N_xe_mode x t_xe_mode x mdot_xe_mode", [("N_xe_mode", "count", "XA9-18"), ("t_xe_mode", "time", "XA9-18"),
                                                   ("mdot_xe_mode", "mass_flow", "XA9-18")], BOTH, (6,),
          note="G-REUSE: while the Hall runs on Xe the ICP runs on that Xe exhaust; nothing is added for the ICP"),
        T("F-XE-PEAK", "Xe-augmented peak operation in flight (only if the RFP permits)", "FLIGHT", "xe_peak",
          "N_peak x t_peak x mdot_peak", [("N_peak", "count", "XA9-19"), ("t_peak", "time", "XA9-19"),
                                          ("mdot_peak", "mass_flow", "XA9-19")], BOTH_COND, (4, 26)),
        T("F-XE-FLOWUNC-OTHER", "flow-class uncertainty of the non-C1 Xe flows", "FLIGHT", "uncertainty",
          "u_class x (sum of the non-C1 Xe product terms)", [("u_class", "fraction", "XA9-20")], BOTH, (96,),
          kind="fraction_of_terms", note="applies to F-HALL-XE-START, F-TRANSITION, F-XE-FALLBACK-OP, "
                                         "F-XE-FUNCTIONAL, F-XE-PEAK, F-ICP-XE"),
        T("F-ICP-XE", "ICP neutralizer dedicated Xe feed", "FLIGHT", "icp_feed",
          "G-REUSE: 0 (exact); G-ATM: 0 Xe (dedicated feed is atmospheric, booked on the feed path); "
          "G-XE: N_icp x t_icp x mdot_icp_xe",
          [("N_icp", "count", "XA9-22"), ("t_icp", "time", "XA9-22"), ("mdot_icp_xe", "mass_flow", "XA9-22")],
          ICP_ONLY, (46,), ("HIQ-06", "HIQ-06_accounting", "OQ-A902-05"),
          gas={"G-REUSE": ZERO, "G-ATM": ZERO, "G-XE": PRESENT},
          note="G-REUSE: mdot_ICP,dedicated = 0 (no double counting of the Hall feed); G-ATM: mdot_atm,total = "
               "mdot_Hall + mdot_ICP,dedicated (actual routing) - outside this Xe ledger"),
        T("F-RESERVE", "reserve = 20 % of planned non-reserve mission Xe (ASSUMED_ENGINEERING_ALLOCATION)", "FLIGHT",
          "reserve", "f_reserve x (sum of all non-reserve FLIGHT terms)", [("f_reserve", "fraction", "XA9-23")],
          BOTH, (43,), kind="reserve"),
        T("F-RESIDUAL", "residual (unusable) Xe - ONE line, exported to the mass BOM", "FLIGHT", "residual",
          "f_residual x (non-reserve + reserve)", [("f_residual", "fraction", "XA9-24")], BOTH, (45,),
          kind="residual", note="A9-06 imports this line; it never books its own residual (row 45)"),
        # ---------------- GROUND_TEST
        T("G-XE-REFERENCE", "XE_REFERENCE bounded Xe health/reference check at the start of each installation",
          "GROUND_TEST", "xe_reference", "N_installations x t_ref x mdot_ref",
          [("N_installations", "count", "XA9-34"), ("t_ref", "time", "XA9-33"), ("mdot_ref", "mass_flow", "XA9-33")],
          BOTH, (26,), ("HIQ-03",), note="before the N2 slices and therefore before any O2-bearing exposure (HIQ-03)"),
        T("G-XE-AUGMENTED-PEAK", "XE_AUGMENTED_PEAK bounded Xe peak points (only if the RFP permits)", "GROUND_TEST",
          "xe_peak", "N_points x t_point x mdot_point",
          [("N_points", "count", "XA9-35"), ("t_point", "time", "XA9-35"), ("mdot_point", "mass_flow", "XA9-35")],
          BOTH_COND, (26,)),
        T("G-C1-PURGE", "C1 purge (ground starts)", "GROUND_TEST", "purge", "N_c1_starts x t_purge x mdot_purge",
          [("N_c1_starts", "count", "XA9-36"), ("t_purge", "time", "XA9-10"), ("mdot_purge", "mass_flow", "XA9-10")],
          C1_ONLY, (42, 93)),
        T("G-C1-PREHEAT", "C1 preheat under Xe flow (ground starts)", "GROUND_TEST", "preheat",
          "N_c1_starts x t_preheat x mdot_preheat",
          [("N_c1_starts", "count", "XA9-36"), ("t_preheat", "time", "XA9-11"),
           ("mdot_preheat", "mass_flow", "XA9-11")], C1_ONLY, (42,), ("SEQ-heater",)),
        T("G-C1-IGN", "C1 ignition dwell bound (ground starts)", "GROUND_TEST", "ignition",
          "N_c1_starts x n_attempts_max x t_dwell_max x mdot_ign",
          [("N_c1_starts", "count", "XA9-36"), ("n_attempts_max", "count", "XA9-08"),
           ("t_dwell_max", "time", "XA9-07"), ("mdot_ign", "mass_flow", "XA9-09")], C1_ONLY, (42, 93)),
        T("G-C1-CATHODE", "C1 keeper/cathode flow over the C1 Xe-on hours", "GROUND_TEST", "keeper_cathode",
          "t_c1_on x mdot_c1_ground", [("t_c1_on", "time", "XA9-36"), ("mdot_c1_ground", "mass_flow", "XA9-41")],
          C1_ONLY, (42,), ("HIQ-01",), note="ground flows are setpoints under test (not the A5 flight design flow)"),
        T("G-C1-MINFLOW-SEARCH", "C1 spot-mode minimum-flow search (0.005 mg/s steps)", "GROUND_TEST",
          "keeper_cathode", "N_searches x n_steps x t_step x mdot_step_mean",
          [("N_searches", "count", "XA9-13"), ("n_steps", "count", "XA9-13"), ("t_step", "time", "XA9-13"),
           ("mdot_step_mean", "mass_flow", "XA9-13")], C1_ONLY, (92,)),
        T("G-C1-FLOWUNC", "C1 steady-flow controller uncertainty term (ground)", "GROUND_TEST", "uncertainty",
          "u_FS x FS x t_c1_on", [("u_FS", "fraction", "XA9-04"), ("FS", "mass_flow", "XA9-05"),
                                  ("t_c1_on", "time", "XA9-36")], C1_ONLY, (96,)),
        T("G-HALL-XE-START", "Hall discharge ignition on Xe (ground, if used)", "GROUND_TEST", "ignition",
          "N_hall_xe_starts x t_hall_ign x mdot_hall_ign",
          [("N_hall_xe_starts", "count", "XA9-36"), ("t_hall_ign", "time", "XA9-15"),
           ("mdot_hall_ign", "mass_flow", "XA9-15")], BOTH_COND, (42,)),
        T("G-TRANSITION", "Xe-to-atmospheric-surrogate transition (ground)", "GROUND_TEST", "transition",
          "N_transitions x t_transition x mdot_transition",
          [("N_transitions", "count", "XA9-16"), ("t_transition", "time", "XA9-16"),
           ("mdot_transition", "mass_flow", "XA9-16")], BOTH, (42,)),
        T("G-ICP-XE", "ICP dedicated Xe feed (ground)", "GROUND_TEST", "icp_feed",
          "G-REUSE: 0 (exact); G-ATM: 0 Xe; G-XE: N_icp x t_icp x mdot_icp_xe",
          [("N_icp", "count", "XA9-22"), ("t_icp", "time", "XA9-22"), ("mdot_icp_xe", "mass_flow", "XA9-22")],
          ICP_ONLY, (46,), ("HIQ-06", "HIQ-06_accounting", "OQ-A902-05"),
          gas={"G-REUSE": ZERO, "G-ATM": ZERO, "G-XE": PRESENT}),
    ]


def scenarios() -> list:
    out = []
    for ledger in LEDGERS:
        p = "FL" if ledger == "FLIGHT" else "GT"
        out.append({"id": f"{p}-C1", "ledger": ledger, "configuration": "hall_c1_reference", "gas_mode": None,
                    "role": "control / fallback configuration (A9); conventional Hall + heated Xe-fed LaB6 C1 "
                            "(rows 46, 49, 88)"})
        for g in GAS_MODES:
            out.append({"id": f"{p}-ICP-{g.split('-')[1]}", "ledger": ledger, "configuration": "hall_icp_neutralizer",
                        "gas_mode": g,
                        "role": ("PRIMARY ICP gas mode (HIQ-06)" if g == "G-REUSE" else
                                 "declared CONTINGENCY variant (HIQ-06); only if G-REUSE fails the preregistered "
                                 "ICP-capacity gate")})
    return out


NOT_PRIMARY_VARIANTS = [
    {"id": "combined_flight_c1_plus_icp", "status": "NOT_A_PRIMARY_A9_VARIANT",
     "basis": "OQ-A902-04 'no combined flight C1 + ICP installation in primary A9 (would be a new variant with its own "
              "closures)'", "ledger_consequence": "no flight scenario books C1 terms and ICP terms together"},
]


def term_status(term: dict, scen: dict) -> str:
    if term["ledger"] != scen["ledger"]:
        return "NOT_IN_LEDGER"
    st = term["configs"][scen["configuration"]]
    if st == PRESENT and term["gas_mode_rule"] is not None:
        st = term["gas_mode_rule"][scen["gas_mode"]]
    return st


# ------------------------------------------------------------------------------------------------ evaluation
def _quantity(item: dict, kind: str):
    """Item -> xl.Quantity / xl.TBD. owner-allocation is mapped to 'assumed' only for the v1 validator."""
    if item["value"] is None or isinstance(item["value"], (list, str)):
        return xl.TBD(item.get("requires", f"item {item['id']} has no scalar value"))
    ev = "assumed" if item["evidence_class"] == "owner-allocation" else item["evidence_class"]
    return xl.Quantity(item["value"], item["unit"], f"{item['id']}: {item['source']}", ev)


def eval_product(term: dict, it: dict):
    """Return (kg or None, missing list). Uses the v1 module's validator and unit table (to_si)."""
    missing, vals = [], []
    for f in term["fields"]:
        q = _quantity(it[f["item"]], f["kind"])
        if isinstance(q, xl.TBD):
            missing.append({"field": f["name"], "item": f["item"], "requires": q.requires})
            continue
        vals.append(xl.to_si(q, f["kind"], f["name"]))
    if missing:
        return None, missing
    out = 1.0
    for v in vals:
        out *= v
    return out, []


def evaluate(scen: dict, tl: list, it: dict) -> dict:
    rows, missing = [], []
    nonres_known, nonres_complete, non_c1 = 0.0, True, []
    fraction_terms = []
    for t in tl:
        st = term_status(t, scen)
        if st == "NOT_IN_LEDGER":
            continue
        rec = {"term": t["id"], "status": st, "kg": None, "missing": []}
        if st in (ABSENT,):
            rec["why"] = C1_ABSENT_WHY if t["id"].startswith(("F-C1", "G-C1")) else "configuration has no such item"
        elif st == ZERO:
            rec["kg"] = 0.0
            rec["why"] = ("HIQ-06_accounting G-REUSE: mdot_ICP,dedicated = 0" if scen["gas_mode"] == "G-REUSE" else
                          "HIQ-06_accounting G-ATM: dedicated ICP feed is atmospheric (outside the Xe ledger)")
        elif t["kind"] == "product":
            kg, miss = eval_product(t, it)
            rec["kg"], rec["missing"] = kg, miss
            if st == COND:
                rec["condition"] = t["label"]
        else:
            fraction_terms.append((t, rec))
        if t["kind"] == "product" and st in (PRESENT, COND, ZERO):
            if rec["kg"] is None:
                nonres_complete = False
                missing.extend({"term": t["id"], **m} for m in rec["missing"])
            else:
                nonres_known += rec["kg"]
            if not t["id"].startswith(("F-C1", "G-C1")):
                non_c1.append(rec)
        rows.append(rec)
    # fraction terms: flow uncertainty of non-C1 flows, then reserve, then residual
    unc = None
    for t, rec in fraction_terms:
        if t["kind"] == "fraction_of_terms":
            q = _quantity(it[t["fields"][0]["item"]], "fraction")
            base_ok = all(r["kg"] is not None for r in non_c1)
            if isinstance(q, xl.TBD):
                rec["missing"] = [{"field": t["fields"][0]["name"], "item": t["fields"][0]["item"],
                                   "requires": q.requires}]
                missing.extend({"term": t["id"], **m} for m in rec["missing"])
                nonres_complete = False
            elif base_ok:
                unc = xl.to_si(q, "fraction", "u_class") * sum(r["kg"] for r in non_c1)
                rec["kg"] = unc
                nonres_known += unc
            else:
                nonres_complete = False
    nonres = nonres_known if nonres_complete else None
    reserve = residual = usable = loaded = None
    f_res = f_resid = None
    for t, rec in fraction_terms:
        if t["kind"] == "reserve":
            f_res = xl.to_si(_quantity(it["XA9-23"], "fraction"), "fraction", "f_reserve")
            reserve = None if nonres is None else f_res * nonres
            rec["kg"] = reserve
            rec["label"] = "ASSUMED_ENGINEERING_ALLOCATION"
        if t["kind"] == "residual":
            f_resid = xl.to_si(_quantity(it["XA9-24"], "fraction"), "fraction", "f_residual")
    for t, rec in fraction_terms:
        if t["kind"] == "residual":
            usable = None if nonres is None else nonres + reserve
            residual = None if usable is None else f_resid * usable
            loaded = None if usable is None else usable + residual
            rec["kg"] = residual
    out = {"scenario": scen["id"], "terms": [{**r, "kg": r6(r["kg"])} for r in rows],
           "non_reserve_kg": r6(nonres), "missing": missing, "refused": nonres is None}
    if scen["ledger"] == "FLIGHT":
        out.update({"reserve_kg": r6(reserve), "residual_kg": r6(residual), "usable_kg": r6(usable),
                    "loaded_kg": r6(loaded)})
        fr = 1.0 + f_res
        fd = 1.0 + f_resid
        out["floor_known_terms_only"] = {
            "label": "FLOOR on the closed terms only (every TBD term set aside); not a total, not an allocation",
            "non_reserve_kg": r6(nonres_known), "reserve_kg": r6(f_res * nonres_known),
            "residual_kg": r6(f_resid * fr * nonres_known), "loaded_kg": r6(nonres_known * fr * fd)}
    else:
        out["ground_supply_margin"] = "TBD - requires owner decision XA9Q-04 (XA9-37)"
        out["floor_known_terms_only"] = {"label": "FLOOR on the closed terms only; not a total",
                                         "non_reserve_kg": r6(nonres_known)}
    xl.reject_forbidden_keys(out)
    return out


# ------------------------------------------------------------------------------------------------ design cases / tank
def read_isotherm(rel: str) -> dict:
    lines = (REPO / rel).read_text(encoding="utf-8").splitlines()
    head = lines[0].split("\t")
    if head[1] != "Pressure (bar)" or head[2] != "Density (kg/m3)":
        raise RuntimeError(f"unexpected NIST header in {rel}")
    out = {}
    for ln in lines[1:]:
        c = ln.split("\t")
        p, rho, phase = float(c[1]), float(c[2]), c[-1]
        if phase != "supercritical":
            raise RuntimeError(f"{rel}: non-supercritical row at {p} bar")
        if p in out and out[p] != rho:
            raise RuntimeError(f"{rel}: inconsistent duplicate row at {p} bar")
        out[p] = rho
    return out


MEOP_AXIS = [
    (75.0, "H2-7 H27-34 PROPOSED minimum MEOP for its 7 l capacity check (made at 293.15 K)"),
    (100.0, "axis value"),
    (150.0, "row 50 question reference point (1.67 g/cm3 at 323 K / 150 bar)"),
    (187.0, "H2-7 AN-MT-SXTA40: MT Aerospace S-XTA 40 l catalogue MEOP (analog)"),
]
LABEL_AXIS = "sensitivity axis over MEOP (not a MEOP choice; MEOP is XA9-28 TBD)"


def design_cases(b: Basis, it: dict, evals: dict) -> dict:
    rho323 = read_isotherm(SNAPSHOTS["NIST323"][0])
    rho300 = read_isotherm(SNAPSHOTS["NIST300"][0])
    u_rho = it["XA9-27"]["value"]
    cases = it["XA9-30"]["value"]
    f_res, f_resid = it["XA9-23"]["value"], it["XA9-24"]["value"]
    xs = b.h27_an["AN-MT-XSXTA"]
    sx = b.h27_an["AN-MT-SXTA40"]
    v_small_l = 7.0  # XS-XTA family upper volume, catalogue p. 11 (H2-7 AN-MT-XSXTA locator 'TOTAL VOLUME 1-7 l')
    if "TOTAL VOLUME 1-7 l" not in xs["locator"]:
        raise RuntimeError("H2-7 XS-XTA locator changed")
    density = [{"p_bar": p, "rho_323K_kg_m3": rho323[p], "rho_300K_kg_m3_contrast": rho300[p], "axis_basis": why}
               for p, why in MEOP_AXIS]
    vol = []
    for m in cases:
        for p, _why in MEOP_AXIS:
            v = m / (rho323[p] * (1.0 - u_rho)) * 1000.0
            v300 = m / rho300[p] * 1000.0
            vol.append({"case_kg": m, "p_bar": p, "V_min_323K_l": r6(v), "V_300K_l_contrast_not_used": r6(v300),
                        "fits_7l_small_family_volume": v <= v_small_l})
    cap7 = [{"p_bar": p, "Xe_capacity_7l_323K_kg": r6(v_small_l / 1000.0 * rho323[p] * (1.0 - u_rho))}
            for p, _w in MEOP_AXIS]
    refs = [{"id": "RFP_40kg_wet", "value_kg": it["XA9-38"]["value"], "kind": "requirement",
             "source": it["XA9-38"]["source"]}]
    shares = []
    for m in cases:
        s = xl.allocation_shares(m, refs)[0]
        shares.append({"case_kg": m, "share_of_40kg_xe_only": r6(s["share"]),
                       "screening_cap_row44": it["XA9-39"]["value"],
                       "xe_load_alone_reaches_screening_cap": s["share"] >= it["XA9-39"]["value"],
                       "note": "Xe load only; the stored-Xe subsystem share needs the hardware masses "
                               f"({PENDING['A9-06']})"})
    split = []
    for m in cases:
        usable = m / (1.0 + f_resid)
        nonres = usable / (1.0 + f_res)
        split.append({"case_kg": m, "residual_kg": r6(m - usable), "reserve_kg": r6(usable - nonres),
                      "non_reserve_cap_kg": r6(nonres)})
    headroom = []
    for sid in ("FL-C1", "FL-ICP-REUSE", "FL-ICP-ATM", "FL-ICP-XE"):
        known = evals[sid]["floor_known_terms_only"]["non_reserve_kg"]
        for s in split:
            h = s["non_reserve_cap_kg"] - known
            headroom.append({"scenario": sid, "case_kg": s["case_kg"], "closed_non_reserve_kg": known,
                             "headroom_for_TBD_terms_kg": r6(h) if h >= 0 else None,
                             "status": "HEADROOM" if h >= 0 else "EXCEEDED_BY_CLOSED_TERMS"})
    # C1 sensitivity: A5 upper test point and the C1 flow ceiling per case
    t_f = it["XA9-01"]["value"] * 3600.0
    unc_kg = it["XA9-04"]["value"] * it["XA9-05"]["value"] * 1e-6 * t_f
    c1_upper_kg = it["XA9-03"]["value"] * 1e-6 * t_f
    c1_sens = []
    for s in split:
        ceil = (s["non_reserve_cap_kg"] - unc_kg) / t_f / 1e-6
        known_up = c1_upper_kg + unc_kg
        c1_sens.append({"case_kg": s["case_kg"],
                        "c1_flow_ceiling_mg_s_all_other_terms_zero": r6(ceil) if ceil >= 0 else None,
                        "closed_non_reserve_at_upper_test_point_kg": r6(known_up),
                        "status_at_upper_test_point": ("HEADROOM" if s["non_reserve_cap_kg"] >= known_up
                                                       else "EXCEEDED_BY_CLOSED_TERMS")})
    return {
        "label": "owner design cases (row 48): loaded Xe mass for tank/interface sizing; no mission load is frozen",
        "case_convention": "case mass = LOADED Xe (usable + residual); usable = non-reserve + reserve "
                           "(PROPOSED reading, XA9Q-01)",
        "eos": {**NIST_EOS, "snapshot_323K": {"path": SNAPSHOTS["NIST323"][0], "sha256": SNAPSHOTS["NIST323"][1],
                                              "url": SNAPSHOTS["NIST323"][3], "accessed": DATE},
                "snapshot_300K_contrast": {"path": SNAPSHOTS["NIST300"][0], "sha256": SNAPSHOTS["NIST300"][1],
                                           "url": SNAPSHOTS["NIST300"][3], "accessed": DATE}},
        "density_axis": {"label": LABEL_AXIS, "rows": density},
        "tank_volume": {
            "relation": "V_min = m_case / (rho(323.15 K, MEOP) x (1 - u_rho)); u_rho = EOS density uncertainty "
                        "(XA9-27). Volume only: no tank mass is computed here; proof/burst factors (XA9-29) and "
                        "MEOP (XA9-28) are explicit TBD inputs",
            "label": LABEL_AXIS, "evidence_class": "model-derived", "rows": vol,
            "small_family_reference": {"volume_l": v_small_l, "dry_mass_kg": xs["value"], "evidence_class":
                                       xs["evidence_class"], "source": f"{H27_REL} analog_data.AN-MT-XSXTA "
                                       f"({xs['locator']})", "note": "catalogue MEOP blank; family under development"},
            "large_family_reference": {"volume_l": 40.0, "structural_mass_kg": sx["value"], "evidence_class":
                                       sx["evidence_class"], "source": f"{H27_REL} analog_data.AN-MT-SXTA40 "
                                       f"({sx['locator']})"},
            "xe_capacity_of_a_7l_tank_323K": cap7,
            "room_temperature_note": "300 K densities are listed only to show why room-temperature sizing is "
                                     "non-conservative (row 50); they are never used for sizing"},
        "reserve_residual_split": {"relation": "usable = case / (1 + f_residual); non-reserve cap = usable / "
                                               "(1 + f_reserve)", "evidence_class": "model-derived", "rows": split},
        "headroom": {"label": "arithmetic on owner allocations: what each design case leaves for the TBD terms after "
                              "the closed terms, the reserve and the residual; not a prediction, not an allocation",
                     "rows": headroom},
        "c1_sensitivity": {"label": "hall_c1_reference flight: C1 flow ceiling per design case with every other TBD "
                                    "term at zero (a ceiling, not an allowance), and the A5 upper test point 0.15 mg/s",
                           "flow_uncertainty_term_kg": r6(unc_kg), "c1_term_at_upper_test_point_kg": r6(c1_upper_kg),
                           "rows": c1_sens},
        "mass_share": {"label": "share of the 40 kg wet gate taken by the Xe load alone (row 5 reading); the 0.25 "
                                "screening cap applies to the whole stored-Xe subsystem (row 44)", "rows": shares},
    }


# ------------------------------------------------------------------------------------------------ sections b..g
def interface_demands(b: Basis) -> list:
    L = []

    def add(iid, frm, to, qty, value, units, status):
        L.append({"id": iid, "from": frm, "to": to, "quantity": qty, "value": value, "units": units,
                  "status": status})

    add("XA9-IF-01", "A9-08", f"A9-06 {PENDING['A9-06']}",
        "residual Xe: ONE line (F-RESIDUAL) to import; A9-06 books no residual of its own (row 45)",
        "per scenario residual_kg (REFUSED while TBD); per design case reserve_residual_split.residual_kg", "kg",
        "OFFERED")
    add("XA9-IF-02", "A9-08", f"A9-06 {PENDING['A9-06']}",
        "Xe totals per configuration/scenario (loaded, usable, reserve, residual) and the 2 / 5 / 10 kg design cases",
        "totals REFUSED (TBD inputs); floors and design cases offered", "kg", "OFFERED")
    add("XA9-IF-03", "A9-08", f"A9-06 {PENDING['A9-06']}",
        "tank volume per design case at 323 K over the MEOP axis; tank / regulator / valve mass analogs are NOT "
        f"re-booked here (pointer: {H27_REL} analog_data AN-MT-XSXTA, AN-MT-SXTA40, AN-MOOG-XFC, AN-XRFS, "
        "AN-MOOG-LATCH-18)", "design_cases.tank_volume", "l; kg", "OFFERED")
    add("XA9-IF-04", "A9-06", "A9-08",
        "stored-Xe hardware masses (tank, regulator/PMU, FCUs, two series isolation valves rows 55/90, filter/getter "
        "C1 branch only, mounting/thermal) and the share of 40 kg (row 44 screening cap)", "TBD", "kg",
        PENDING["A9-06"])
    add("XA9-IF-05", "A9-08", f"A9-06 {PENDING['A9-06']}",
        "flag: row 54 v0 'Xe hardware 1.5 kg' allocation vs the H2-7 analog range (A9 recorder flag, row 54)",
        "context only; reconciliation is A9-06's", "kg", "OFFERED")
    add("XA9-IF-06", "A9-08", f"A9-07 {PENDING['A9-07']}",
        "C1 start booking structure: purge, preheat, ignition bound (3 x 120 s per start, row 93, XA9Q-02), steady "
        "flow 0.10 mg/s over 15,000 h; which revised start-sequence steps flow Xe", "F-C1-* / G-C1-* terms",
        "mg/s; s", "OFFERED")
    add("XA9-IF-07", "A9-07", "A9-08",
        "vendor/design-qualified C1 purge and ignition flows and durations, preheat duration (XA9-09..11); Hall "
        "discharge ignition gas (XA9-15); tank thermal control keeping <= 323 K (H2-5 revision)", "TBD",
        "mg/s; s; K", PENDING["A9-07"])
    add("XA9-IF-08", "A9-08", f"A9-07 {PENDING['A9-07']}",
        "H2-7 H27-34 (PROPOSED >= 75 bar MEOP for a 7 l tank) was a 293.15 K check; at 323.15 K a 7 l tank at 75 bar "
        "holds the value in design_cases.tank_volume.xe_capacity_of_a_7l_tank_323K (XA9Q-06)",
        "see design_cases", "bar; kg", "OFFERED")
    add("XA9-IF-09", "A9-08", f"A9-09 {PENDING['A9-09']}",
        "Xe tank RFQ ranges: loaded 2 / 5 / 10 kg at 323 K; V_min per MEOP axis; MEOP, proof and burst factors to be "
        "quoted (XA9-28, XA9-29)", "design_cases.tank_volume", "kg; l; bar", "OFFERED")
    add("XA9-IF-10", "A9-08", f"A9-09 {PENDING['A9-09']}",
        "PMU/FCU RFQ ranges: C1 steady controller 0.05-0.2 mg/s class, +-2 % FS or better on Xe (rows 96, 125); "
        "C1 start/diode controller FS 1.0 mg/s only if 0.6-0.8 mg/s is retained (row 125); anode-side Xe-mode flow "
        "range TBD (XA9-18); G-XE ICP feed range TBD (XA9-22); two series isolation valves (row 90); filter/getter "
        "<= 17 W class C1 branch only after verification (row 51)", "XA9-04..06, XA9-18, XA9-22, XA9-31", "mg/s; W",
        "OFFERED")
    add("XA9-IF-11", "A9-09", "A9-08", "quoted MEOP, tank volume/mass, FCU accuracy classes on Xe (closes XA9-20, "
        "XA9-28, XA9-29, XA9-31/32)", "TBD", "bar; l; kg; 1", PENDING["A9-09"])
    add("XA9-IF-12", "A9-08", PENDING["A9-10"],
        "owner-question state (XA9Q-01..07), M16 impacts (rows 6, 7, 8, 11), cross-references to A9-06/07/09",
        "sections open_owner_questions / m16_impact", "-", "OFFERED")
    add("XA9-IF-13", "A9-08", f"A9-01 {DELIVERABLES['PRE'][0]}",
        "booking structure for DQ-HI-DXE (Xe per operating hour and per start, PHASE_TOTAL_FLOW; ICP gas by species)",
        "terms per phase", "mg/s; mg per start; kg", "OFFERED")
    add("XA9-IF-14", "A9-01 (verified)", "A9-08",
        "labels XE_REFERENCE / XE_AUGMENTED_PEAK, stage map, block count n at LOCK-2 (XA9-34)",
        "HI-CMP / HI-LOCK2", "-", "VERIFIED (read)")
    add("XA9-IF-15", "A9-02 (verified)", "A9-08",
        "start-up templates C-S2 (purge + preheat, filter_getter slot), C-S4 (ignition <= 120 s x 2 retries), I-S3 "
        "(flow_control_icp_feed, booked only when G-ATM/G-XE is installed, OQ-A902-05)", "templates", "s",
        "VERIFIED (read)")
    add("XA9-IF-16", "A9-08", f"A9-03 ICD {DELIVERABLES['ICD'][0]}",
        "ID-24 resolved by HIQ-06: G-REUSE books 0 Xe; G-XE booked as F-ICP-XE / G-ICP-XE; the ICP carries its own "
        "RF-neutralizer lifetime/cycle requirement instead of a C1 cathode term (row 46)", "0 (G-REUSE)", "kg",
        "OFFERED")
    add("XA9-IF-17", "A9-04 (verified)", "A9-08", "UB-F-05: the +-2 % FS class carries the Xe-ledger uncertainty "
        "term (row 96)", "XA9-04", "1", "VERIFIED (read)")
    add("XA9-IF-18", "A9-05 (verified)", "A9-08", "VI-GAS-01 gas_ICP booking; VI-SU-04/05 C1 start terms",
        "F-ICP-XE; F-C1-*", "mg/s; kg", "VERIFIED (read)")
    add("XA9-IF-19", "H2-2 (verified)", "A9-08", "H22-42/43/44/45 flows and classes; H22-50 measured cathode flow "
                                                 "(H4 output); IFD-15", "XA9-02..06", "mg/s", "VERIFIED (read)")
    add("XA9-IF-20", "H2-3 (verified)", "A9-08", "shared-line Xe hold-up 1.4e-09-1.8e-08 kg/Pa: not a material "
                                                 "ledger term (H2-3 finding)", "not booked", "kg/Pa", "VERIFIED (read)")
    add("XA9-IF-21", "A9-08", "H-1 / C-1 test (H4)", "log Xe flow x time per phase (purge, preheat, ignition "
        "attempts, keeper, transition, XE_REFERENCE, XE_AUGMENTED_PEAK, G-XE) per installation", "h4_inputs", "mg/s; s",
        "OFFERED")
    return L


def owner_answers_applied(b: Basis) -> list:
    how = {
        1: "the RFP-dependent terms (F-XE-FUNCTIONAL size, F-XE-PEAK, G-XE-AUGMENTED-PEAK) stay TBD until the "
           "official RFP is held",
        3: "cathode term booked over 15,000 firing hours (provisional); mission life 26,280 h recorded as context "
           "(XA9-40)",
        4: "Xe for the 25 mN capability only if the RFP permits, then booked explicitly (F-XE-PEAK, CONDITIONAL)",
        5: "40 kg is a wet gate including the Xe load and tank (XA9-38); shares reported on that reading",
        6: "bounded functional Xe-capable mode booked as its own term F-XE-FUNCTIONAL in BOTH flight configurations",
        8: "tank/PMU/FCU ranges offered to the A9-09 RFQ packages (quotations only; this lane contacts no supplier)",
        19: "XE_REFERENCE count scales with the installation count fixed at LOCK-2 (XA9-34)",
        24: "restarts recorded; N_starts stays TBD until the operations concept",
        26: "XE_REFERENCE and XE_AUGMENTED_PEAK are separate labelled ground-test terms; never atmospheric evidence",
        36: "Ar engineering runs consume no Xe and are not in this ledger; the Xe reference follows the bounded plan",
        42: "PHASE_TOTAL_FLOW: purge, preheat, ignition, keeper/cathode, transition and fallback each booked as their "
            "own term with the total Xe flow of the phase; no unbooked preheat flow",
        43: "F-RESERVE = 0.20 x planned non-reserve FLIGHT Xe, labelled ASSUMED_ENGINEERING_ALLOCATION",
        44: "0.25 screening cap reported beside the design-case shares; never an entitlement",
        45: "F-RESIDUAL = 0.02 x usable load, ONE line exported to the mass BOM (A9-06 imports it)",
        46: "C1 cathode term (15,000 h) only in hall_c1_reference; hall_icp_neutralizer has none and carries the "
            "RF-neutralizer lifetime/cycle requirement (interface to A9-03/A9-07)",
        47: "Xe hardware mapping accepted for the C1/Xe branch; ICP/RF electronics are A9-06 items, not Xe items",
        48: "no mission load frozen; 2 / 5 / 10 kg design cases evaluated for tank volume and head-room",
        49: "heated C1: preheat under Xe flow booked (F-C1-PREHEAT); heaterless start penalty not booked",
        50: "tank volume sized at 323 K (323.15 K NIST isotherm, Lemmon & Span 2006 EOS) with MEOP and proof/burst "
            "factors as explicit TBD inputs; 300 K shown only as a non-conservative contrast",
        51: "filter/getter only on the C1/Xe branch; <= 17 W class, mass and pressure drop TBD until vendor/spec "
            "verification; not in the ICP-only flight branch",
        54: "v0 'Xe hardware 1.5 kg' allocation passed to A9-06 as context (recorder flag)",
        55: "dual series isolation on the high-pressure Xe path passed to A9-06/A9-09",
        90: "two independent series isolation valves on the flight Xe/cathode branch passed to A9-06/A9-09",
        92: "0.005 mg/s step recorded for the ground minimum-flow search term (G-C1-MINFLOW-SEARCH)",
        93: "ignition booked at the bound 120 s per attempt x (1 + 2 retries) per start; purge/ignition flows TBD "
            "(vendor-qualified); final bound frozen before score-bearing C1 testing (LOCK-2)",
        96: "+-2 % FS class booked as the explicit C1 flow-uncertainty term (0.216 kg over 15,000 h)",
        125: "two C1 controllers: steady 0.05-0.2 mg/s class (FS 0.2) and start/diode FS 1.0 only if retained",
    }
    return [{"row": r, "covers_ids": b.row(r)["covers_ids"], "owner_answer_verbatim": b.verbatim(r),
             "how_applied": how[r]} for r in sorted(how)]


def a91_applied(b: Basis) -> list:
    how = {
        "HIQ-01": "hall_c1_reference in every block: C1 ground terms scale with the block schedule (XA9-36)",
        "HIQ-02": "installation/block count from LOCK-2 (>= 6 blocks) drives the XE_REFERENCE count",
        "HIQ-03": "G-XE-REFERENCE booked once per installation at its start, before N2 and any O2-bearing exposure",
        "HIQ-06": "G-REUSE primary: no dedicated ICP Xe; G-ATM / G-XE only as declared contingency scenarios",
        "HIQ-06_accounting": "G-REUSE F-ICP-XE = 0 exactly; G-ATM books no Xe; G-XE booked under PHASE_TOTAL_FLOW",
        "HIQ-08": "Ar never enters this Xe ledger (Ar is not Xe) nor any LOCK-2 number",
        "OQ-A902-02": "filter/getter power sits in the 300 W common allocation when active (A9-02); mass/flow here",
        "OQ-A902-04": "no combined flight C1 + ICP scenario: C1 terms ABSENT in hall_icp_neutralizer flight",
        "OQ-A902-05": "flow_control_icp_feed and its Xe only when G-ATM / G-XE is installed/used",
        "SEQ-heater": "Xe flows whenever the C1 heater is on (preheat booked for the full heater-on time)",
        "ICP-45": "the ICP-capacity entry records gas state: the measurement that would close a G-XE term",
    }
    out = []
    for k in sorted(how):
        v = b.a91[k]
        out.append({"decision": k, "text": v if isinstance(v, str) else json.dumps(v, sort_keys=True),
                    "how_applied": how[k]})
    out.append({"decision": "execution.step_2_parallel.A9-08", "text": b.a91_exec["step_2_parallel"]["A9-08"],
                "how_applied": "this deliverable"})
    return out


OPEN_QUESTIONS = [
    {"id": "XA9Q-01", "question": "Are the row-48 design cases (2 / 5 / 10 kg) LOADED Xe (usable + residual) or usable "
                                  "Xe?", "proposed": "LOADED Xe (tank sizing needs the loaded mass); the reserve and "
                                                     "residual are carved out of each case", "freeze_point": "NOW"},
    {"id": "XA9Q-02", "question": "Row 93 'at most two retries': is the per-start bound 3 dwells (1 + 2 retries, "
                                  "360 s) or 2 dwells (240 s)?", "proposed": "3 dwells, 360 s per start (conservative); "
                                                                             "freeze at LOCK-2 with the final bound",
     "freeze_point": "LOCK-2"},
    {"id": "XA9Q-03", "question": "Is the row-96 flow-class term booked additively (conservative) and inside the "
                                  "reserve base?", "proposed": "yes, additive and inside the non-reserve sum until S1a "
                                                               "demonstrates a better class", "freeze_point": "NOW"},
    {"id": "XA9Q-04", "question": "Ground-test Xe supply margin over the booked ground-test Xe?",
     "proposed": "owner call", "freeze_point": "LOCK-2"},
    {"id": "XA9Q-05", "question": "Does a G-XE ICP feed need a filter/getter?",
     "proposed": "owner call; inferred proposal: not unless the ICP vendor/spec requires Xe purity beyond the "
                 "supply (row 51 ties the getter to the LaB6 C1 line; the ICP has no thermionic emitter)",
     "freeze_point": "after-evidence"},
    {"id": "XA9Q-06", "question": "Retire H2-7 H27-34 (PROPOSED >= 75 bar MEOP, a 293.15 K check) in favour of a MEOP "
                                  "chosen from quotations against the 323 K volume table?",
     "proposed": "yes; route through A9-07 / A9-09", "freeze_point": "LOCK-1"},
    {"id": "XA9Q-07", "question": "Does the row-6 functional Xe mode apply to the hall_icp_neutralizer flight "
                                  "configuration (so it also carries a Xe tank and Xe flow control)?",
     "proposed": "yes: row 6 reads the RFP 'air + Xe' independently of the electron source", "freeze_point": "NOW"},
]


def historical_reuse() -> list:
    return [
        {"artifact": DELIVERABLES["XEMOD"][0], "sha256": DELIVERABLES["XEMOD"][1], "kind": "verified v1 (not "
         "historical, reused read-only)", "reused": "Quantity/TBD records, to_si unit validation, "
         "reject_forbidden_keys, allocation_shares, product_term_kg (C1 term cross-check), PHASE_TOTAL_FLOW text",
         "not_reused": "architecture scope hall_only / rf_hall / ecr_hall (row 28 superseded); the v1 reserve/tank "
                       "policy forms (row 43/50 now fix them differently)"},
        {"artifact": DELIVERABLES["XEV1"][0], "sha256": DELIVERABLES["XEV1"][1], "kind": "verified v1",
         "reused": "cathode term 5.4 kg, mass-reference wording, OD-XE-1..8 question lineage (answered by rows 42-48)",
         "not_reused": "SC-* illustrative scenarios (A5 three-architecture topology); no v1 value is overwritten"},
        {"artifact": HISTORICAL["phase1_prereg_framework"][0], "sha256": HISTORICAL["phase1_prereg_framework"][1],
         "kind": "HISTORICAL (A5 Phase-1)", "reused": "nothing numeric; the labelled-Xe idea is taken from A9-01 "
                                                      "instead", "not_reused": "hall_only/rf_hall/ecr_hall arms, "
                                                                               "pre-ionizer dwell matching (row 65)"},
        {"artifact": HISTORICAL["preionizer_module_icd"][0], "sha256": HISTORICAL["preionizer_module_icd"][1],
         "kind": "HISTORICAL (A5 pre-ionizer ICD)", "reused": "nothing",
         "not_reused": "pre-ionizer Xe seed (PREIONIZER_SEED) terms: the upstream pre-ionizer is not the primary line"},
        {"artifact": HISTORICAL["bus_power_boundary_v1"][0], "sha256": HISTORICAL["bus_power_boundary_v1"][1],
         "kind": "HISTORICAL (bus_power_boundary_v1)", "reused": "nothing (A9-02 boundary read instead)",
         "not_reused": "v1 slots"},
    ]


def m16_impact(b: Basis) -> list:
    how = {
        6: "tank sized per design case at 323 K (volume only) over a MEOP axis; the Xe ledger stays REFUSED per "
           "configuration (A7 blocker 3 unchanged); no single mission load frozen",
        7: "regulator inlet range = MEOP (TBD, XA9-28); ranges offered to A9-09",
        8: "two C1 controllers (row 125) with the +-2 % FS term (row 96); ICP feed metering only in G-ATM/G-XE "
           "(OQ-A902-05); anode-side Xe-mode flow range TBD",
        11: "C1 is the reference/fallback: flight cathode term only in hall_c1_reference (15,000 h); absent in "
            "hall_icp_neutralizer flight (OQ-A902-04, row 46)",
    }
    return [{"m16_row": r, "key": b.m16[r]["key"], "name": b.m16[r]["name"], "impact": how[r],
             "cell_edit": f"none here (M16 v2 is a verified deliverable); routed through {PENDING['A9-10']}"}
            for r in sorted(how)]


H3_INPUTS = [
    {"id": "XA9-H3-01", "item": "Xe tank", "spec_inputs": "loaded 2 / 5 / 10 kg cases at 323 K; V_min per MEOP axis; "
                                                           "MEOP, proof, burst TBD; ullage/fill accuracy TBD",
     "status": "OFFERED to A9-09"},
    {"id": "XA9-H3-02", "item": "Xe regulator / PMU", "spec_inputs": "inlet up to MEOP (TBD); outlet to the FCUs",
     "status": "OFFERED to A9-09"},
    {"id": "XA9-H3-03", "item": "C1 steady FCU", "spec_inputs": "0.05-0.2 mg/s class, +-2 % FS or better on Xe",
     "status": "OFFERED to A9-09"},
    {"id": "XA9-H3-04", "item": "C1 start/diode FCU", "spec_inputs": "FS 1.0 mg/s, only if 0.6-0.8 mg/s is retained",
     "status": "CONDITIONAL"},
    {"id": "XA9-H3-05", "item": "filter/getter (C1 branch only)", "spec_inputs": "<= 17 W class after verification",
     "status": "CONDITIONAL on the C1/Xe branch"},
    {"id": "XA9-H3-06", "item": "ICP feed valve / FCU", "spec_inputs": "only when G-ATM or G-XE is installed; port "
                                                                       "capped in G-REUSE", "status": "CONTINGENCY"},
    {"id": "XA9-H3-07", "item": "laboratory Xe supply", "spec_inputs": "ground-test ledger total x (1 + XA9-37) - "
                                                                       "REFUSED until LOCK-2", "status": "TBD"},
]
H4_INPUTS = [
    {"id": "XA9-H4-01", "measurement": "Xe flow x time per phase and per start (purge, preheat, each ignition "
                                       "attempt, keeper, transition), per installation", "closes": "XA9-09..11, XA9-15, "
                                                                                                   "XA9-16"},
    {"id": "XA9-H4-02", "measurement": "XE_REFERENCE and XE_AUGMENTED_PEAK flow x duration, labelled",
     "closes": "XA9-33, XA9-35"},
    {"id": "XA9-H4-03", "measurement": "C1 spot-mode minimum flow at the required emission current (0.005 mg/s "
                                       "steps)", "closes": "XA9-02 (after-evidence)"},
    {"id": "XA9-H4-04", "measurement": "installed zero check per block and MFC body-temperature band (row 97)",
     "closes": "flow-term validity"},
    {"id": "XA9-H4-05", "measurement": "Xe calibration of each FCU (S1a) demonstrating a class better than +-2 % FS",
     "closes": "XA9-04, XA9-20"},
    {"id": "XA9-H4-06", "measurement": "ICP gas state in G-REUSE; ICP feed flow if G-XE is ever used (ICP-45)",
     "closes": "XA9-22"},
]


# ------------------------------------------------------------------------------------------------ assemble
def build() -> dict:
    verify_pins()
    b = Basis()
    it_list = items(b)
    it = {x["id"]: x for x in it_list}
    tl = terms()
    for t in tl:
        for f in t["fields"]:
            if f["item"] not in it:
                raise RuntimeError(f"{t['id']}: unknown item {f['item']}")
    scens = scenarios()
    evals = {s["id"]: evaluate(s, tl, it) for s in scens}
    # cross-check the C1 term against the v1 module
    c1 = next(r for r in evals["FL-C1"]["terms"] if r["term"] == "F-C1-CATHODE")["kg"]
    v1 = xl.product_term_kg({"mdot_cathode": xl.Quantity(b.c1_target, "mg/s", "A5", "assumed"),
                             "t_firing": xl.Quantity(15000.0, "h", "row 46", "assumed")}, "m_cathode")
    if abs(c1 - v1) > 1e-12 or abs(c1 - 5.4) > 1e-9:
        raise RuntimeError("C1 cathode term disagrees with the v1 module")
    xe_v1 = load("XEV1")
    if xe_v1["cathode_term"]["design_term"]["m_cathode_kg"] != 5.4:
        raise RuntimeError("v1 ledger cathode term changed")
    ledger_presence = []
    for t in tl:
        ledger_presence.append({"term": t["id"], "ledger": t["ledger"],
                                **{c: t["configs"][c] for c in CONFIGS},
                                "gas_mode_rule": t["gas_mode_rule"]})
    out = {
        "schema": SCHEMA_ID, "id": "xe_ledger_a9_v1", "version": "1.0.0",
        "lane": "fo_a9_08_xe_ledger_update", "trigger": "T_A9_08_XE_LEDGER_UPDATE",
        "authorization": f"{A91_REL} execution.step_2_parallel.A9-08; {DECISIONS['A9'][0]} "
                         "derived_execution_backlog A9-08",
        "status": "PARAMETRIC_LEDGER_A9 - every total REFUSED while TBD inputs remain; nothing frozen; no winner",
        "a9_status": "OWNER_AUTHORIZED_INVESTIGATION_HYPOTHESIS_NOT_FLIGHT_BASELINE",
        "date": DATE, "base_commit": BASE_COMMIT, "generated_by": SCRIPT_REL,
        "companion_document": f"{LANE_REL}/{MD_NAME}", "test": TEST_REL,
        "what_this_is_not": [
            "not a Xe allocation: no mission Xe load is frozen (row 48)",
            "not a prediction of thrust, discharge current, neutralizer current, efficiency or plasma state (no Hall "
            "closure admitted; credible set EMPTY; 0-D Hall superseded; v1.2-v1.6 withdrawn)",
            "not a ranking: NET_BENEFIT is hard gates + Pareto (row 37); no winner is declared; outcome vocabulary "
            "includes NO_VIABLE_CASE and OPEN is a status (row 38)",
            "not wired into archengine; the v1 module and the v1 deliverable are byte-identical to the base",
        ],
        "binding_context": {"p5_n2_v1": "INCONCLUSIVE (permanent)", "credible_hall_set": "EMPTY",
                            "bundle_1": "NO_BASELINE_YET", "decisions_A4_A7": "immutable, still binding"},
        "decision_pins": [{"path": v[0], "sha256": v[1], "role": v[2]} for v in DECISIONS.values()],
        "deliverable_pins": [{"path": v[0], "sha256": v[1], "role": v[2]} for v in DELIVERABLES.values()],
        "source_snapshots": [{"path": v[0], "sha256": v[1], "description": v[2], "url": v[3]}
                             for v in SNAPSHOTS.values()],
        "never_pinned": list(NEVER_PINNED),
        "configurations": list(CONFIGS), "icp_gas_modes": {
            "G-REUSE": "PRIMARY (HIQ-06): ICP runs on Hall exhaust/residual; m_Xe,ICP = 0; no dedicated atmospheric "
                       "feed; the Hall exhaust is never counted again as ICP propellant",
            "G-ATM": "declared CONTINGENCY variant: dedicated atmospheric ICP feed; 0 Xe; booked on the atmospheric "
                     "feed path as mdot_atm,total = mdot_Hall + mdot_ICP,dedicated",
            "G-XE": "declared CONTINGENCY variant: dedicated Xe ICP feed booked as an explicit term under "
                    "PHASE_TOTAL_FLOW (F-ICP-XE / G-ICP-XE)"},
        "ledgers": {"FLIGHT": "primary A9 flight Xe ledger per configuration (reserve and residual apply)",
                    "GROUND_TEST": "H-1 campaign Xe (XE_REFERENCE, XE_AUGMENTED_PEAK, C1 ground starts, searches); no "
                                   "reserve/residual rule from the owner; supply margin XA9Q-04"},
        "not_primary_variants": NOT_PRIMARY_VARIANTS,
        "accounting_convention": {"id": "PHASE_TOTAL_FLOW", "owner_row": 42, "owner_answer_verbatim": b.verbatim(42),
                                  "v1_definition": xl.ACCOUNTING_CONVENTIONS["PHASE_TOTAL_FLOW"],
                                  "phases_booked": ["purge", "preheat", "ignition", "keeper_cathode", "transition",
                                                    "fallback", "xe_mode", "xe_peak", "xe_reference", "icp_feed",
                                                    "uncertainty", "reserve", "residual"],
                                  "overlap_rule": "phase hours also counted in t_firing book the cathode flow twice "
                                                  "(conservative, v1 rule)"},
        "hall_closure_isolation": "the Xe path is upstream of the discharge: no Hall closure, screening candidate, "
                                  "ensemble member or P5 nuisance key enters (checked with the v1 "
                                  "reject_forbidden_keys on every scenario)",
        "items": it_list,
        "terms": tl,
        "term_presence": ledger_presence,
        "scenarios": scens,
        "evaluations": [evals[s["id"]] for s in scens],
        "design_cases": design_cases(b, it, evals),
        "filter_getter": {"branch": "C1/Xe only (row 51)", "flight_hall_c1_reference": "INSTALLED",
                          "flight_hall_icp_neutralizer": "NOT_INSTALLED (ICP-only flight branch, row 51)",
                          "ground_hall_c1_reference": "INSTALLED", "items": ["XA9-31", "XA9-32"],
                          "g_xe_icp_feed": "owner call XA9Q-05",
                          "analog": {"value": b.getter["value"], "source_id": b.getter["source_id"],
                                     "locator": b.getter["locator"], "evidence_class": b.getter["evidence_class"],
                                     "pointer": DELIVERABLES["R6"][0], "label": "analog; not the selected unit"}},
        "non_xe_obligations": [{"configuration": "hall_icp_neutralizer", "item": "RF-neutralizer lifetime/cycle "
                                "requirement in place of the C1 cathode term", "basis": "row 46", "owner":
                                "A9-03 ICD / A9-07 (not a Xe quantity)"}],
        "interface_demands": interface_demands(b),
        "owner_answers_applied": owner_answers_applied(b),
        "a9_1_decisions_applied": a91_applied(b),
        "open_owner_questions": OPEN_QUESTIONS,
        "historical_reuse": historical_reuse(),
        "m16_impact": m16_impact(b),
        "h3_inputs": H3_INPUTS, "h4_inputs": H4_INPUTS,
        "parallel_lanes": {k: v for k, v in PENDING.items()},
    }
    xl.reject_forbidden_keys(out)
    return out


# ------------------------------------------------------------------------------------------------ markdown
def _v(x):
    if x is None:
        return "TBD"
    if isinstance(x, bool):
        return "yes" if x else "no"
    if isinstance(x, float):
        return f"{x:g}"
    if isinstance(x, list):
        return " / ".join(_v(y) for y in x)
    return str(x)


def _esc(s) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")


def table(head, rows) -> list:
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    out += ["| " + " | ".join(_esc(c) for c in r) + " |" for r in rows]
    return out


def markdown(d: dict) -> str:
    L = [f"# A9 Xe ledger update ({d['id']})", "",
         f"- lane `{d['lane']}` (trigger `{d['trigger']}`); authorization: {d['authorization']}",
         f"- status: **{d['status']}**; A9 status `{d['a9_status']}`",
         f"- generated by `{d['generated_by']}` from `{JSON_NAME}` (do not edit by hand); test `{d['test']}`",
         f"- base commit `{d['base_commit']}`; date {d['date']}", "", "What this is not:"]
    L += [f"- {x}" for x in d["what_this_is_not"]]
    L += ["", "Binding context: " + "; ".join(f"{k} = {v}" for k, v in d["binding_context"].items()), "",
          "## Pinned inputs (immutable; sha256 verified by the builder)", ""]
    L += table(["path", "sha256", "role"], [[p["path"], p["sha256"], p["role"]] for p in
                                            d["decision_pins"] + d["deliverable_pins"]])
    L += ["", "Source snapshots:", ""]
    L += table(["path", "sha256", "description", "url"],
               [[s["path"], s["sha256"], s["description"], s["url"]] for s in d["source_snapshots"]])
    L += ["", "Never pinned (mutable governance): " + ", ".join(f"`{p}`" for p in d["never_pinned"]), "",
          "## Configurations, ICP gas modes and ledgers", "",
          "Configurations: " + ", ".join(f"`{c}`" for c in d["configurations"]), ""]
    L += [f"- **{k}**: {v}" for k, v in d["icp_gas_modes"].items()]
    L += [f"- ledger **{k}**: {v}" for k, v in d["ledgers"].items()]
    L += [f"- `{v['id']}`: {v['status']} ({v['basis']})" for v in d["not_primary_variants"]]
    ac = d["accounting_convention"]
    L += ["", f"Accounting convention **{ac['id']}** (row {ac['owner_row']}): \"{ac['owner_answer_verbatim']}\"",
          "", f"v1 definition: {ac['v1_definition']}", "", f"Phases booked: {', '.join(ac['phases_booked'])}.", "",
          d["hall_closure_isolation"], "",
          "## (a) Items / parameters", ""]
    L += table(["id", "name", "value", "unit", "basis", "source", "evidence class", "status", "freeze point"],
               [[i["id"], i["name"], i.get("value_display", _v(i["value"])), i["unit"], i["basis"], i["source"],
                 i["evidence_class"], i["status"], i["freeze_point"]] for i in d["items"]])
    L += ["", "### Terms and where they exist", ""]
    L += table(["term", "name", "ledger", "phase", "formula", "hall_c1_reference", "hall_icp_neutralizer",
                "gas-mode rule", "rows"],
               [[t["id"], t["name"], t["ledger"], t["phase"], t["formula"], t["configs"]["hall_c1_reference"],
                 t["configs"]["hall_icp_neutralizer"],
                 "-" if not t["gas_mode_rule"] else ", ".join(f"{k}: {v}" for k, v in t["gas_mode_rule"].items()),
                 ", ".join(str(r) for r in t["owner_rows"])] for t in d["terms"]])
    L += ["", "### Evaluation per configuration and scenario", "",
          "Totals are REFUSED while any TBD input remains. The floor sets every TBD term aside and is not a total.", ""]
    for s, e in zip(d["scenarios"], d["evaluations"]):
        L += [f"#### {s['id']} - {s['ledger']} / `{s['configuration']}`" +
              (f" / {s['gas_mode']}" if s["gas_mode"] else ""), "", f"Role: {s['role']}", ""]
        L += table(["term", "status", "kg", "missing inputs"],
                   [[r["term"], r["status"], "n/a" if r["status"] == "ABSENT_BY_OWNER_DECISION" else _v(r["kg"]),
                     "; ".join(f"{m['field']} ({m['item']})" for m in r.get("missing", [])) or "-"]
                    for r in e["terms"]])
        f = e["floor_known_terms_only"]
        tot = ("REFUSED" if e["refused"] else _v(e.get("loaded_kg", e["non_reserve_kg"])))
        L += ["", f"Total: **{tot}**; missing inputs: {len(e['missing'])}. "
                  f"Floor (closed terms only): " + ", ".join(f"{k} {_v(v)}" for k, v in f.items() if k != "label"), ""]
    dc = d["design_cases"]
    L += ["### Design cases (row 48) and tank sizing at 323 K (row 50)", "", dc["label"] + ".",
          f"Case convention: {dc['case_convention']}.", "",
          f"EOS: {dc['eos']['citation']}. {dc['eos']['stated_uncertainty']}.", ""]
    L += table(["MEOP axis (bar)", "rho 323.15 K (kg/m3)", "rho 300 K contrast", "axis basis"],
               [[r["p_bar"], r["rho_323K_kg_m3"], r["rho_300K_kg_m3_contrast"], r["axis_basis"]]
                for r in dc["density_axis"]["rows"]])
    L += ["", dc["tank_volume"]["relation"] + ".", ""]
    L += table(["case (kg)", "MEOP (bar)", "V_min 323 K (l)", "V 300 K (l, contrast, not used)", "<= 7 l"],
               [[r["case_kg"], r["p_bar"], r["V_min_323K_l"], r["V_300K_l_contrast_not_used"],
                 _v(r["fits_7l_small_family_volume"])] for r in dc["tank_volume"]["rows"]])
    L += ["", "Xe capacity of a 7 l tank at 323.15 K: " +
          "; ".join(f"{r['p_bar']:g} bar -> {r['Xe_capacity_7l_323K_kg']:g} kg"
                    for r in dc["tank_volume"]["xe_capacity_of_a_7l_tank_323K"]) + ".", "",
          f"Analog tanks: {dc['tank_volume']['small_family_reference']['source']}; "
          f"{dc['tank_volume']['large_family_reference']['source']}.", ""]
    L += table(["case (kg)", "residual (kg)", "reserve (kg)", "non-reserve cap (kg)"],
               [[r["case_kg"], r["residual_kg"], r["reserve_kg"], r["non_reserve_cap_kg"]]
                for r in dc["reserve_residual_split"]["rows"]])
    L += ["", dc["headroom"]["label"] + ".", ""]
    L += table(["scenario", "case (kg)", "closed non-reserve (kg)", "head-room for TBD terms (kg)", "status"],
               [[r["scenario"], r["case_kg"], r["closed_non_reserve_kg"], _v(r["headroom_for_TBD_terms_kg"]),
                 r["status"]] for r in dc["headroom"]["rows"]])
    cs = dc["c1_sensitivity"]
    L += ["", cs["label"] + f". Flow-uncertainty term {cs['flow_uncertainty_term_kg']:g} kg; C1 term at 0.15 mg/s "
                            f"{cs['c1_term_at_upper_test_point_kg']:g} kg.", ""]
    L += table(["case (kg)", "C1 flow ceiling (mg/s)", "closed at 0.15 mg/s (kg)", "status at 0.15 mg/s"],
               [[r["case_kg"], _v(r["c1_flow_ceiling_mg_s_all_other_terms_zero"]),
                 r["closed_non_reserve_at_upper_test_point_kg"], r["status_at_upper_test_point"]] for r in cs["rows"]])
    L += ["", dc["mass_share"]["label"] + ".", ""]
    L += table(["case (kg)", "share of 40 kg (Xe only)", "screening cap (row 44)", "Xe alone reaches the cap"],
               [[r["case_kg"], r["share_of_40kg_xe_only"], r["screening_cap_row44"],
                 _v(r["xe_load_alone_reaches_screening_cap"])] for r in dc["mass_share"]["rows"]])
    fg = d["filter_getter"]
    L += ["", "### Filter/getter (row 51)", "",
          f"Branch: {fg['branch']}; flight hall_c1_reference {fg['flight_hall_c1_reference']}; flight "
          f"hall_icp_neutralizer {fg['flight_hall_icp_neutralizer']}; ground hall_c1_reference "
          f"{fg['ground_hall_c1_reference']}; G-XE ICP feed: {fg['g_xe_icp_feed']}. Analog: {fg['analog']['value']} "
          f"({fg['analog']['source_id']}, {fg['analog']['locator']}; {fg['analog']['label']}).", "",
          "Non-Xe obligation: " + "; ".join(f"{o['configuration']}: {o['item']} ({o['basis']}; {o['owner']})"
                                           for o in d["non_xe_obligations"]), "",
          "## (b) Interface demands", ""]
    L += table(["id", "from", "to", "quantity", "value", "units", "status"],
               [[x["id"], x["from"], x["to"], x["quantity"], x["value"], x["units"], x["status"]]
                for x in d["interface_demands"]])
    L += ["", "## (c) Owner answers applied", ""]
    L += table(["row", "ids", "owner answer (verbatim)", "how applied"],
               [[a["row"], ", ".join(a["covers_ids"]), a["owner_answer_verbatim"], a["how_applied"]]
                for a in d["owner_answers_applied"]])
    L += ["", "A9.1 follow-up decisions applied:", ""]
    L += table(["decision", "text", "how applied"],
               [[a["decision"], a["text"], a["how_applied"]] for a in d["a9_1_decisions_applied"]])
    L += ["", "## (d) Open owner questions (new)", ""]
    L += table(["id", "question", "proposed", "freeze point"],
               [[q["id"], q["question"], q["proposed"], q["freeze_point"]] for q in d["open_owner_questions"]])
    L += ["", "## (e) Historical reuse", ""]
    L += table(["artifact", "sha256", "kind", "reused", "not reused"],
               [[h["artifact"], h["sha256"], h["kind"], h["reused"], h["not_reused"]] for h in d["historical_reuse"]])
    L += ["", "## (f) M16 impact", ""]
    L += table(["M16 row", "key", "name", "impact", "cell edit"],
               [[m["m16_row"], m["key"], m["name"], m["impact"], m["cell_edit"]] for m in d["m16_impact"]])
    L += ["", "## (g) H3 / H4 inputs", ""]
    L += table(["id", "item", "spec inputs", "status"],
               [[h["id"], h["item"], h["spec_inputs"], h["status"]] for h in d["h3_inputs"]])
    L += [""]
    L += table(["id", "measurement", "closes"], [[h["id"], h["measurement"], h["closes"]] for h in d["h4_inputs"]])
    L += ["", "Parallel lanes: " + "; ".join(f"{k}: {v}" for k, v in d["parallel_lanes"].items()), ""]
    return "\n".join(L)


def render() -> tuple:
    d = build()
    js = json.dumps(d, indent=1, ensure_ascii=False) + "\n"
    md = markdown(json.loads(js))
    return js, md


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="exit 1 unless the outputs are reproduced byte for byte")
    a = ap.parse_args(argv)
    js, md = render()
    pj, pm = HERE / JSON_NAME, HERE / MD_NAME
    if a.check:
        ok = (pj.is_file() and pj.read_text(encoding="utf-8") == js and pm.is_file()
              and pm.read_text(encoding="utf-8") == md)
        print("OK" if ok else "DRIFT: outputs differ from the builder")
        return 0 if ok else 1
    pj.write_text(js, encoding="utf-8")
    pm.write_text(md, encoding="utf-8")
    print(f"wrote {pj.relative_to(REPO)} and {pm.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
