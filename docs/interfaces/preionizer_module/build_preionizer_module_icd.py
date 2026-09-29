#!/usr/bin/env python3
"""Deterministic builder of the H-1 COMMON Pre-Ionizer Module ICD (fo_preionizer_module_icd, owner addendum A6).

Writes
  schemas/interfaces/preionizer_module_icd_v1.json          (machine-readable ICD; JSON Schema + x-preionizer-module-icd)
  docs/interfaces/preionizer_module/PREIONIZER_MODULE_ICD.md (companion document, rendered from the same data)

Every numeric value in the ICD is COPIED from a merged, verified repository deliverable, addressed by an RFC 6901 JSON
pointer into that file, with the file's sha256 at build time. This script computes no physics and invents no number:
a value that no deliverable supplies is written as ``null`` with "TBD - requires <what>" and the S1a/S1/procurement
step that closes it. Missing inputs raise (CLAUDE.md rule 3: no silent fallback).

Usage
  python docs/interfaces/preionizer_module/build_preionizer_module_icd.py          # write both files
  python docs/interfaces/preionizer_module/build_preionizer_module_icd.py --check  # exit 1 if either file differs

Standard library only. Pure: reads repository files, writes the two outputs; not wired into archengine.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
OUT_JSON = "schemas/interfaces/preionizer_module_icd_v1.json"
OUT_MD = "docs/interfaces/preionizer_module/PREIONIZER_MODULE_ICD.md"
THIS_SCRIPT = "docs/interfaces/preionizer_module/build_preionizer_module_icd.py"
BASE_COMMIT = "302e1c94b3bddeb005f17bb189407f2e4641519a"

ARCHS = ("hall_only", "rf_hall", "ecr_hall")
EVIDENCE_CLASSES = ("measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed")
TBD = "TBD - requires"

# ----------------------------------------------------------------------------------------------------------------------
# pinned inputs
# ----------------------------------------------------------------------------------------------------------------------
# Immutable owner decisions (sha256 must never change; the tests compare them with the files).
DECISIONS = {
    "A5": "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_architecture.json",
    "A6": "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A6_a5_followon_authorization.json",
    "A4": "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A4_owner_decisions.json",
    "G0": "docs/decisions/verification/A5_BASELINE_VERIFICATION.json",
}
# Verified, merged deliverables read by this lane (pinned at the base commit; a change needs a re-pin via this script).
# Mutable governance files (lane/trigger registries, trigger ledgers, runtime_state.json, *_status_current.json) are
# deliberately NOT pinned.
DELIVERABLES = {
    "HW": "docs/experiments/hardware/hardware_requirements_v1.json",
    "HWDOC": "docs/experiments/hardware/HARDWARE_DEFINITION.md",
    "INS": "docs/experiments/instrumentation/instrumentation_definition_v1.json",
    "MCQ": "docs/experiments/magnet_coil/magnet_coil_qualification_v1.json",
    "LANE25": "docs/architecture_comparison/minimum_decisive_experiment/experiment_draft.json",
    "LANE17": "docs/architecture_comparison/hall_reference/hall_reference_v1.json",
    "LANE06": "docs/architecture_comparison/experiment_protocol/protocol_draft.json",
    "INTERSTAGE": "docs/architecture_comparison/interstage/INTERSTAGE_MODEL.md",
    "BUSDOC": "docs/architecture_comparison/power_boundary/BUS_POWER_BOUNDARY.md",
    "BUSMOD": "abep_sim/arch_boundary.py",
    "THERMAL": "abep_sim/thermal_life.py",
    "CATHINT": "abep_sim/cathode_integration.py",
    "CONTROLS": "docs/controls/DUAL_FEED_STATES.md",
    "FSM": "schemas/controls/dual_feed_state_machine_v1.json",
    "ICD_UP": "schemas/interfaces/upstream_icd_v1.json",
    "ICD_UPDOC": "docs/interfaces/UPSTREAM_ICD.md",
    "RFEV": "docs/evidence/rf_source/rf_evidence_matrix.json",
    "ECREV": "docs/evidence/ecr_source/ecr_evidence_matrix.json",
    "S1A": "docs/experiments/s1a_readiness/s1a_readiness_conditions_v1.json",
    "S1": "docs/experiments/s1_readiness/s1_readiness_conditions_v1.json",
    "BUNDLE1": "docs/milestones/bundle1/bundle1_v5.json",
}


def _abs(rel: str) -> str:
    return os.path.join(ROOT, rel)


def sha256_of(rel: str) -> str:
    p = _abs(rel)
    if not os.path.isfile(p):
        raise FileNotFoundError(f"required input missing: {rel}")
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


_JSON_CACHE: dict = {}


def load(rel: str):
    if rel not in _JSON_CACHE:
        p = _abs(rel)
        if not os.path.isfile(p):
            raise FileNotFoundError(f"required input missing: {rel}")
        with open(p, encoding="utf-8") as f:
            _JSON_CACHE[rel] = json.load(f)
    return _JSON_CACHE[rel]


def resolve(doc, pointer: str):
    """RFC 6901 JSON pointer resolution; raises KeyError/IndexError on a dangling pointer."""
    if pointer == "":
        return doc
    if not pointer.startswith("/"):
        raise ValueError(f"not a JSON pointer: {pointer!r}")
    cur = doc
    for raw in pointer[1:].split("/"):
        tok = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(cur, list):
            cur = cur[int(tok)]
        elif isinstance(cur, dict):
            if tok not in cur:
                raise KeyError(f"pointer {pointer!r}: key {tok!r} not found")
            cur = cur[tok]
        else:
            raise KeyError(f"pointer {pointer!r}: cannot descend into {type(cur).__name__}")
    return cur


def index_of(rel: str, list_pointer: str, item_id: str) -> int:
    items = resolve(load(rel), list_pointer)
    hits = [i for i, x in enumerate(items) if isinstance(x, dict) and x.get("id") == item_id]
    if len(hits) != 1:
        raise KeyError(f"{rel}{list_pointer}: id {item_id!r} found {len(hits)} times")
    return hits[0]


def hw_req(req_id: str) -> str:
    return f"/requirements/{index_of(DELIVERABLES['HW'], '/requirements', req_id)}"


def ev_entry(key: str, entry_id: str) -> str:
    return f"/entries/{index_of(DELIVERABLES[key], '/entries', entry_id)}"


def instrument(ins_id: str) -> str:
    return f"/instruments/{index_of(DELIVERABLES['INS'], '/instruments', ins_id)}"


def lane25_threshold(t_id: str) -> str:
    return f"/thresholds/{index_of(DELIVERABLES['LANE25'], '/thresholds', t_id)}"


# ----------------------------------------------------------------------------------------------------------------------
# quantity records
# ----------------------------------------------------------------------------------------------------------------------
def _src(key: str, pointer: str) -> dict:
    rel = DELIVERABLES.get(key) or DECISIONS.get(key)
    if rel is None:
        raise KeyError(f"unknown input key {key!r}")
    resolve(load(rel), pointer)  # dangling pointers raise here
    return {"path": rel, "pointer": pointer, "sha256": sha256_of(rel)}


def sourced(name: str, key: str, pointer: str, *, note: str | None = None, role: str = "requirement_or_allocation",
            status: str | None = None, value=None, unit: str | None = None, evidence_class: str | None = None,
            as_published: bool = False, transformation: str | None = None) -> dict:
    """Copy a numeric value (and its unit, status and evidence class) from a sourced record in a deliverable.

    The record at ``pointer`` must be a dict carrying 'value' (hardware/instrumentation style) or an evidence-matrix
    entry ('value', 'units'). Overrides are allowed only together with ``as_published`` (the published value is then
    kept verbatim next to the transcription) or for a missing status/evidence class that the caller states.
    """
    rel = DELIVERABLES.get(key) or DECISIONS.get(key)
    rec = resolve(load(rel), pointer)
    if not isinstance(rec, dict) or "value" not in rec:
        raise ValueError(f"{rel}{pointer} is not a value record")
    q = {"name": name}
    if as_published:
        if value is None or unit is None or evidence_class is None or status is None or transformation is None:
            raise ValueError(f"{name}: as_published needs value, unit, status, evidence_class and transformation")
        q.update({"value": value, "unit": unit, "status": status, "evidence_class": evidence_class,
                  "value_as_published": rec["value"], "transformation": transformation})
    else:
        if value is not None:
            raise ValueError(f"{name}: a value override is only allowed with as_published")
        v = rec["value"]
        if isinstance(v, bool) or not isinstance(v, (int, float, list, dict)):
            raise ValueError(f"{name}: {rel}{pointer} value {v!r} is not numeric")
        q["value"] = v
        q["unit"] = unit if unit is not None else (rec.get("unit") or rec.get("units"))
        q["status"] = status if status is not None else (rec.get("status") or "SOURCED")
        q["evidence_class"] = evidence_class if evidence_class is not None else rec.get("evidence_class")
    if q["evidence_class"] not in EVIDENCE_CLASSES:
        raise ValueError(f"{name}: evidence class {q['evidence_class']!r} not in {EVIDENCE_CLASSES}")
    if not q.get("unit"):
        raise ValueError(f"{name}: no unit")
    q["source"] = _src(key, pointer)
    for k in ("locator",):
        if rec.get(k):
            q["source_locator"] = rec[k]
    up = rec.get("source")
    if isinstance(up, dict):
        q["upstream_source"] = {k: up[k] for k in ("citation", "doi_or_url", "access", "locator") if k in up}
    elif isinstance(up, (list, str)):
        q["upstream_source"] = up
    q["role"] = role
    if note:
        q["note"] = note
    return q


def tbd(name: str, unit: str, requires: str, closes_at: str, *, ref: tuple | None = None, note: str | None = None) -> dict:
    """A quantity with no sourced value: value null, 'TBD - requires <what>' and the step that closes it."""
    q = {"name": name, "value": None, "unit": unit, "status": "TBD", "tbd_requires": f"{TBD} {requires}",
         "closes_at": closes_at}
    if ref is not None:
        q["source_ref"] = _src(*ref)
        rec = resolve(load(q["source_ref"]["path"]), q["source_ref"]["pointer"])
        if isinstance(rec, dict) and rec.get("value") is not None:
            raise ValueError(f"{name}: {q['source_ref']} carries a value; use sourced()")
    if note:
        q["note"] = note
    return q


def sat(status: str, how: str) -> dict:
    if status not in SATISFIABILITY:
        raise ValueError(status)
    return {"status": status, "how": how}


SATISFIABILITY = {
    "BY_DESIGN": "the occupant meets the item by a design provision stated in 'how'",
    "TRIVIAL": "the occupant meets the item because it carries no hardware that could violate it (terminated/absent)",
    "IN_PRINCIPLE_OPEN_DESIGN_RISK": "meetable by known design measures, not yet shown; failure is a recorded, "
                                     "measured outcome (the arm is then reported non-comparable), never a waiver",
}


# ----------------------------------------------------------------------------------------------------------------------
# content
# ----------------------------------------------------------------------------------------------------------------------
def common_items() -> list:
    HW = "HW"
    items = []

    items.append({
        "id": "PMI-01",
        "boundary": "mechanical_envelope_and_mounting_datum",
        "title": "Mechanical envelope and mounting datum",
        "definition": "The module slot is the volume between IP-UP (module inlet plane: end of the common feed line, after "
                      "the single mixing point and the gas isolator, fixed in the thrust-stand frame) and IP-DN (module "
                      "outlet plane = the H-1 rear inlet flange, immediately upstream of the anode/gas-distributor plane "
                      "HALL_INLET_Z0). The mounting datum is the IP-DN flange face with its alignment features on H-1: "
                      "module z axis = H-1 thrust axis, registered to the drawing with z = 0 at the anode face (the B(z) "
                      "registration of HW-MC-03). Every occupant uses the same flange pattern, alignment features, seals "
                      "and torque specification at IP-UP and IP-DN; no occupant part protrudes downstream of IP-DN.",
        "common_requirement": "The common envelope (length, maximum diameter, keep-out zones for the B(z) probe path, the "
                              "witness holder and the service-line bundle) is sized to the LARGEST occupant, including the "
                              "ECR resonance magnet with its yoke and the microwave feed/coupling structure, and the RF "
                              "coil, Faraday shield and any on-module matching network. The envelope is therefore never "
                              "RF-sized. Module mass and centre of gravity are recorded per occupant serial.",
        "units": ["m", "kg", "N m"],
        "quantities": [
            tbd("interface_dimensions", "m", "the H-1 rear-flange design and the module designs (IP-UP/IP-DN flange, "
                "alignment features, seal grooves)", "procurement: H-1 rear-flange and module interface control drawing "
                "released before HRR (HWQ-15: interfaces frozen before Phase 1)",
                ref=(HW, hw_req("HW-PIM-01") + "/values/interface_dimensions")),
            tbd("envelope_length_max", "m", "the ECR and RF module designs (largest occupant incl. ECR magnet/yoke and "
                "microwave coupling structure)", "procurement: module design release (RF and ECR), before HRR"),
            tbd("envelope_diameter_max", "m", "the ECR and RF module designs (largest occupant)", "procurement: module "
                "design release (RF and ECR), before HRR"),
            tbd("module_mass_max", "kg", "the W4 thrust-stand load capacity and the module designs",
                "procurement: thrust-stand selection (W4) and module design release; checked at HRR"),
            tbd("flange_torque_spec", "N m", "the flange and seal selection", "procurement: interface control drawing, "
                "before HRR"),
        ],
        "satisfiability": {
            "PIM-RF": sat("BY_DESIGN", "RF source, interstage and Faraday shield fit inside the ECR-sized envelope; same "
                                       "flanges and alignment features."),
            "PIM-ECR": sat("BY_DESIGN", "the envelope is sized to the ECR module including magnet/yoke and microwave "
                                        "feed; same flanges and alignment features."),
            "PIM-0": sat("BY_DESIGN", "replicates the module mechanical envelope and gas path with no source hardware and "
                                      "no magnet (HW-PIM-02); same flanges and alignment features."),
        },
        "verification": {"method": "inspection; torque and alignment record at every configuration change",
                         "stage": "HRR; every configuration change"},
        "traces_to": ["HW-PIM-01", "HW-PIM-02", "HW-H1-06", "lane 17 INV-G3",
                      "A5 architecture.reserved_interface (location between feed/plenum and Hall ionization region)"],
    })

    items.append({
        "id": "PMI-02",
        "boundary": "gas_flow_path_and_pressure_boundary",
        "title": "Gas-flow path and pressure boundary",
        "definition": "The module gas path runs from IP-UP to IP-DN, i.e. between the feed/plenum (FS-C manifold and line) "
                      "and the Hall ionization region (H-1 distributor at HALL_INLET_Z0), the location A5 reserves for the "
                      "pre-ionizer interface. All anode gas (Xe at start, then N2 or N2/O2) enters at IP-UP and leaves at "
                      "IP-DN; in HW-RF and HW-ECR it therefore passes the source (HW-FS-02). The interstage duct belongs to "
                      "the module. The C-1 cathode gas line never passes the module.",
        "common_requirement": "(a) No occupant has a gas inlet or outlet other than IP-UP, IP-DN and the declared "
                              "source-chamber pressure port (PMI-07); any split of the IP-UP flow inside a module (e.g. "
                              "injection into an ECR resonance zone) is internal to the module. (b) The module wetted "
                              "volume is a sealed pressure boundary to the facility vacuum at both flanges and at every "
                              "penetration (RF window/feedthrough, microwave window/feedthrough, probe and OES ports). "
                              "(c) Every wetted part is oxygen-compatible and cleaned for O2 service. (d) The wetted "
                              "volume and internal surface area of each occupant are recorded (transients, residence "
                              "time, surface interaction), never equalised by adjustment.",
        "units": ["Pa m^3 s^-1", "Pa", "m^3", "m^2"],
        "quantities": [
            tbd("leak_rate_max", "Pa m^3 s^-1", "the leak-check method and the smallest grid flow (W1, W4)",
                "S1a leak check and cold-flow test, every configuration",
                ref=(HW, hw_req("HW-FS-05") + "/values/leak_rate_max")),
            tbd("P_feed_range", "Pa", "the W1 test points (fo_feed_state_closure)", "S1a cold flow (released ground-"
                "qualification feed points, S1A-C3)", ref=(HW, hw_req("HW-ENV-04") + "/values/P_feed_range")),
            tbd("wetted_volume_per_occupant", "m^3", "the RF, ECR and PIM-0 module designs", "procurement: module design "
                "release; recorded at HRR"),
            tbd("o2_cleaning_standard", "-", "the facility safety case (owner channel)", "HRR",
                ref=(HW, hw_req("HW-FS-07") + "/values/o2_cleaning_standard")),
        ],
        "satisfiability": {
            "PIM-RF": sat("BY_DESIGN", "dielectric discharge tube is part of the sealed wetted volume; RF feedthrough "
                                       "outside the gas path."),
            "PIM-ECR": sat("BY_DESIGN", "microwave window/feedthrough is a sealed penetration; any resonance-zone "
                                        "injection is an internal split of the IP-UP flow."),
            "PIM-0": sat("BY_DESIGN", "flow-equivalent duct with the same ports (HW-PIM-02, HW-FS-04)."),
        },
        "verification": {"method": "inspection + leak check + cold-flow manifold pressure", "stage": "HRR; S1a; every "
                         "configuration change"},
        "traces_to": ["HW-FS-02", "HW-FS-04", "HW-FS-05", "HW-FS-07", "HW-ENV-04", "lane 17 INV-F1",
                      "ICD IF-A5 (p_feed_Pa, pressure_loss_Pa gap)", "A5 architecture.reserved_interface"],
    })

    items.append({
        "id": "PMI-03",
        "boundary": "electrical_power_boundary",
        "title": "Electrical power boundary (bus_power_boundary_v1)",
        "definition": "Every electrical load of an occupant is supplied from the common spacecraft-side DC bus boundary "
                      "through exactly the pre-ionizer components that bus_power_boundary_v1 assigns to its architecture "
                      "(abep_sim/arch_boundary.py PREIONIZER_COMPONENTS): rf_hall -> rf_source (net RF power at the "
                      "coil/antenna feed terminals); ecr_hall -> ecr_source (net microwave power at the coupling-structure "
                      "input) and ecr_magnet (resonance-coil terminals; a permanent magnet is passed explicitly as 0 W with "
                      "efficiency 1); hall_only -> none. Module power therefore always lands in P_bus (P_bus = load / "
                      "ledger efficiency, summed by arch_boundary.bus_power_ledger with its conservation gate).",
        "common_requirement": "(a) No module load is booked under a common component or omitted. (b) A module load with no "
                              "v1 slot (an RF assist magnet, a powered interstage electrode or bias, an active coolant "
                              "pump) is NOT permitted under v1 until the owner and the bus-boundary lane define a slot in "
                              "a new boundary version (see annex deviations DEV-RF-01, DEV-RF-03). (c) The module's source "
                              "power is never assessed separately from P_bus (A5 discriminator_note).",
        "units": ["W", "-"],
        "bus_components": {"hall_only": [], "rf_hall": ["rf_source"], "ecr_hall": ["ecr_source", "ecr_magnet"]},
        "quantities": [
            sourced("P_bus_requirement_max", HW, "/rfp_basis/power_max_W", role="requirement",
                    note="RFP < 1.5 kW read as P_bus at bus_power_boundary_v1 (verify against the RFP text)"),
            sourced("P_bus_design_allocation", "A5", "/allocations_and_requirements/2", role="allocation",
                    as_published=True, value=[1300, 1350], unit="W", status="ALLOCATION", evidence_class="assumed",
                    transformation="'<= 1.30-1.35 kW' transcribed as the upper-allocation band [1300, 1350] W; an "
                                   "allocation, never a prediction (A5 what_this_is_not)"),
            tbd("P_hi_source", "W", "the source allocation in bus_power_boundary_v1 (owner, lane 11)",
                "LOCK-1 (source allocation); bench stage S3", ref=(HW, hw_req("HW-PIM-08") + "/values/P_hi")),
            tbd("ledger_efficiency_per_preionizer_component", "-", "the LOCK-1 ledger efficiencies of rf_source, "
                "ecr_source and ecr_magnet (DC-fed generator input metered as evidence, HW-PIM-12)", "LOCK-1"),
        ],
        "satisfiability": {
            "PIM-RF": sat("BY_DESIGN", "one slot rf_source; DC-fed RF generator off-module, net power at the load plane."),
            "PIM-ECR": sat("BY_DESIGN", "slots ecr_source and ecr_magnet (0 W / efficiency 1 if permanent)."),
            "PIM-0": sat("TRIVIAL", "empty component set; no electrical load exists to book."),
        },
        "verification": {"method": "INS-02 per component channel; INS-03 net RF/microwave power at the load plane; "
                                   "ledger via arch_boundary.bus_power_ledger", "stage": "S1a (channel and load-plane "
                                   "calibration); every reading"},
        "traces_to": ["abep_sim/arch_boundary.py PREIONIZER_COMPONENTS, COMPONENT_DEFINITIONS",
                      "docs/architecture_comparison/power_boundary/BUS_POWER_BOUNDARY.md", "HW-PIM-05", "HW-PIM-08",
                      "HW-PIM-12", "INS-02", "INS-03", "lane 17 INV-P1"],
    })

    items.append({
        "id": "PMI-04",
        "boundary": "control_enable_interlock_lines",
        "title": "Control, enable and interlock lines",
        "definition": "A common harness with the same connector, pin-out and routing on every occupant carries: "
                      "L1 MODULE_ID (identity/serial code of the installed occupant, logged with every reading); "
                      "L2 SOURCE_ENABLE (controller permit to the occupant's off-module generator chain); "
                      "L3 INTERLOCK_LOOP (hard-wired series loop through the occupant); "
                      "L4 PREIONIZER_LIT (status for the state-machine guard preionizer_lit); "
                      "L5 PREIONIZER_FAULT (status for the health guard preionizer_fault).",
        "common_requirement": "(a) The interlock loop is opened by each A4 S1a minimum interlock that applies at the "
                              "module (hardware E-stop; vacuum/background-pressure abort; loss-of-pumping/cooling abort; "
                              "magnet overcurrent/overtemperature, which includes an ECR electromagnet; gas/oxidizer-state "
                              "interlock; DAQ fault indication; explicit Hall-discharge inhibit during S1a). Interlock "
                              "limits come from real hardware/facility ratings, never invented thresholds (A4). "
                              "(b) Sequencing follows schemas/controls/dual_feed_state_machine_v1.json: the pre-ionizer "
                              "comes up on Xe before any atmosphere (PREIONIZER_SEED / PREIONIZER_IGNITION), a pre-ionizer "
                              "loss reverts to XE_FALLBACK, CONTROLLED_SHUTDOWN removes pre-ionizer power first, retries "
                              "are counter-bounded (n_preion_retry_max). (c) Source-type-specific trips (RF reflected "
                              "power, microwave reflected power/arc) are annex items feeding the same L3/L5 lines.",
        "units": ["-"],
        "quantities": [
            tbd("interlock_limits", "-", "real hardware/facility ratings of the installed units (A4 S1a_interlock_limits)",
                "S1A-C2 (safe operational limits owner-approved) and S1-C8"),
            tbd("n_preion_retry_max", "-", "owner FDIR policy and the pre-ionizer ignition test (controls lane parameter)",
                "S1b/S2 pre-ionizer ignition tests; owner FDIR decision"),
            tbd("preionizer_lit_detection_method", "-", "a pre-ionizer plasma-detection method from source design and "
                "test (docs/evidence/rf_source/, docs/evidence/ecr_source/)", "procurement: module design; demonstrated "
                "at bench stage S3"),
        ],
        "satisfiability": {
            "PIM-RF": sat("BY_DESIGN", "L1-L5 wired; RF reflected-power trip feeds L3/L5 (annex PMR-06)."),
            "PIM-ECR": sat("BY_DESIGN", "L1-L5 wired; ECR electromagnet overcurrent/overtemperature and microwave trips "
                                        "feed L3/L5 (annex PME-06)."),
            "PIM-0": sat("TRIVIAL", "L1 reports PIM-0; L2 terminated (no effect); L3 closed by a jumper so the loop "
                                    "topology is identical; L4/L5 report constant not-lit / no-fault."),
        },
        "verification": {"method": "inspection + interlock functional test (each input opens the loop)",
                         "stage": "S1a (before power is applied, S1A-C2); every configuration change (L1 record)"},
        "traces_to": ["A4 decisions.S1a_minimum_interlocks, S1a_interlock_limits", "docs/controls/DUAL_FEED_STATES.md",
                      "schemas/controls/dual_feed_state_machine_v1.json", "S1A-C2", "S1-C8"],
    })

    items.append({
        "id": "PMI-05",
        "boundary": "thermal_rejection_interface",
        "title": "Thermal rejection interface",
        "definition": "Each occupant rejects its own waste heat through a declared module thermal path (radiation to the "
                      "facility and/or conduction to a module-own sink on the stand frame), never through H-1 by an "
                      "unrecorded path. The IP-DN conductive path is either thermally isolated by design or instrumented "
                      "(HW-PIM-09), with the same isolator hardware in every occupant.",
        "common_requirement": "(a) Module thermocouples at fixed recorded positions (IP-DN flange, module body; source "
                              "structure and ECR magnet where present), identical positions on PIM-0; anode temperature "
                              "logged in every arm (HW-H1-07); thermal settling T-SETTLE before every reading. (b) Module "
                              "waste heat, magnet heating and any resulting anode-temperature difference are arm "
                              "consequences: recorded and reported with R_arch, never equalised (hardware identity_matrix "
                              "may_differ). (c) Active liquid cooling is not a common provision (annex deviation "
                              "DEV-RF-03).",
        "units": ["W K^-1", "s", "degC"],
        "quantities": [
            tbd("module_to_H1_thermal_conductance_max", "W K^-1", "the module and H-1 thermal designs (lane 15 "
                "thermal_life inputs)", "design analysis before HRR; checked S1a/S3"),
            tbd("T_SETTLE", "s", "the S1 thermal time constants (lane 25 T-SETTLE)", "S1b",
                ref=(HW, hw_req("HW-H1-07") + "/values/T_SETTLE")),
            tbd("module_structure_temperature_max", "degC", "the selected module materials and the thermal_life limit "
                "records", "procurement: module design release"),
        ],
        "satisfiability": {
            "PIM-RF": sat("BY_DESIGN", "coil/tube/shield heat rejected by the module path; flange instrumented."),
            "PIM-ECR": sat("BY_DESIGN", "coupling-structure and magnet heat rejected by the module path; magnet "
                                        "temperature measured (HW-PIM-15)."),
            "PIM-0": sat("TRIVIAL", "no dissipation; carries the same isolator hardware and thermocouple positions."),
        },
        "verification": {"method": "analysis + test", "stage": "design; S1a; S3"},
        "traces_to": ["HW-PIM-09", "HW-H1-07", "HW-PIM-15", "abep_sim/thermal_life.py THERMAL_COMPONENTS",
                      "hardware identity_matrix.may_differ"],
    })

    items.append({
        "id": "PMI-06",
        "boundary": "grounding_and_shielding",
        "title": "Grounding and shielding",
        "definition": "The module body and any interstage electrode sit at ONE declared potential (floating / anode / "
                      "cathode common / facility ground: owner decision HWQ-07), identical for PIM-0 at IP-DN "
                      "(HW-ELEC-02), through one declared bonding point on the module. The gas isolator (voltage break) is "
                      "upstream of IP-UP, so every occupant sees the same gas-line potential (HW-FS-06).",
        "common_requirement": "(a) Any interstage current is measured, because it enters the cathode budget I_emit = I_d "
                              "+ I_keeper + I_interstage (lane 19). (b) RF and microwave returns are separated from the "
                              "discharge return (HW-ELEC-03). (c) Source-specific electromagnetic containment (RF Faraday "
                              "shield/screen, microwave leakage containment) lies inside the PMI-01 envelope and is an "
                              "annex item. (d) Generator pickup on every common diagnostic is quantified with each "
                              "generator on a matched dummy load at each pre-registered power, every pump-down "
                              "(DUMMY_LOAD_PICKUP).",
        "units": ["V", "A"],
        "quantities": [
            tbd("module_potential", "V", "the module electrical design and an owner decision (HWQ-07)", "LOCK-1 input; "
                "verified S1a", ref=(HW, hw_req("HW-ELEC-02") + "/values/module_potential")),
            tbd("isolator_margin", "V", "the facility electrical safety case and the supply design", "S1a (hipot)",
                ref=(HW, hw_req("HW-FS-06") + "/values/isolator_margin")),
            tbd("ir_test_voltage", "V", "the MCQ-QT-08 procedure and an owner decision", "baseline before S1",
                ref=(HW, hw_req("HW-ELEC-05") + "/values/ir_test_voltage")),
        ],
        "satisfiability": {
            "PIM-RF": sat("BY_DESIGN", "body and Faraday shield bonded at the declared point; RF return separate."),
            "PIM-ECR": sat("BY_DESIGN", "body, waveguide/coax outer and magnet frame bonded at the declared point; "
                                        "microwave return separate."),
            "PIM-0": sat("BY_DESIGN", "body at the same declared potential and bonding point; no generator."),
        },
        "verification": {"method": "inspection + test", "stage": "S1a; every pump-down (dummy-load pickup)"},
        "traces_to": ["HW-ELEC-01", "HW-ELEC-02", "HW-ELEC-03", "HW-ELEC-05", "HW-FS-06", "lane 06 DUMMY_LOAD_PICKUP",
                      "lane 19 electron_current_budget"],
    })

    ins03 = instrument("INS-03") + "/required_uncertainty/source_scale_max"
    items.append({
        "id": "PMI-07",
        "boundary": "diagnostics",
        "title": "Diagnostics",
        "definition": "Common diagnostic provisions at identical positions on every occupant: (a) source-chamber pressure "
                      "port (blanked or connected identically on PIM-0, HW-FS-04); (b) source-exit ion-collector access "
                      "for I_src (INS-15 source-exit collector, HW-PIM-07), present on PIM-0 to confirm zero I_src; "
                      "(c) optional OES view port (INS-12): if any occupant has one, all carry it (blanked where unused); "
                      "(d) module thermocouples (PMI-05, INS-17); (e) the Hall-probe path for B(z) through the channel "
                      "with any occupant installed (HW-H1-08, INS-09); (f) a load-plane source-power channel slot for "
                      "the arm's pre-ionizer components (INS-03; empty in hall_only); (g) MODULE_ID in every DAQ record "
                      "(PMI-04 L1); (h) the interstage-current channel (PMI-06).",
        "common_requirement": "Delivered current I_del is measured across the Hall channel exit with the discharge off (S3) "
                              "and needs no module port. The load-plane source-power uncertainty must satisfy the lane 25 "
                              "source-scale bound at the LOCK-1 source fraction f_src; frequency-specific sensors are "
                              "annex items.",
        "units": ["Pa", "A", "relative (1 sigma)"],
        "quantities": [
            tbd("u_src_scale", "relative", "the f_src allocation at LOCK-1 (package REQ-HW-03 gives u_src,max(f_src))",
                "LOCK-1; calibrated S1a", ref=(HW, hw_req("HW-PIM-12") + "/values/u_src_scale")),
            sourced("u_src_scale_max_at_f_src_0.1", "INS", ins03 + "/0.1", role="requirement_bound",
                    status="SOURCED", note="lane 25 bound u_src <= G3 share / f_src; f_src not yet allocated"),
            sourced("u_src_scale_max_at_f_src_0.2", "INS", ins03 + "/0.2", role="requirement_bound", status="SOURCED"),
            sourced("u_src_scale_max_at_f_src_0.3", "INS", ins03 + "/0.3", role="requirement_bound", status="SOURCED"),
            sourced("u_src_scale_max_at_f_src_0.4", "INS", ins03 + "/0.4", role="requirement_bound", status="SOURCED"),
            tbd("I_src_collector_CEX_bound", "-", "a cited N2+ on N2 charge-exchange cross section (package REQ-HW-05)",
                "S1a probe calibration", note="INS-15 feasibility AT_RISK"),
        ],
        "satisfiability": {
            "PIM-RF": sat("BY_DESIGN", "ports (a)-(c) on the source chamber/interstage; INS-03 at the coil feed."),
            "PIM-ECR": sat("BY_DESIGN", "ports (a)-(c) on the source chamber/interstage; INS-03 at the coupling-"
                                        "structure input."),
            "PIM-0": sat("BY_DESIGN", "same ports at the same positions (blanked or connected identically); INS-03 slot "
                                      "empty (no component in hall_only)."),
        },
        "verification": {"method": "inspection + calibration", "stage": "HRR; S1a"},
        "traces_to": ["HW-FS-04", "HW-PIM-07", "HW-PIM-12", "HW-H1-08", "INS-03", "INS-09", "INS-12", "INS-15",
                      "INS-17"],
    })

    items.append({
        "id": "PMI-08",
        "boundary": "service_line_routing",
        "title": "Service-line routing",
        "definition": "The service-line set crossing the thrust stand is the UNION of all occupants' lines and is present "
                      "in every configuration (HW-SVC-01): RF coax; microwave feed (coax or waveguide, per the ECR "
                      "frequency selection); ECR magnet DC lead pair; module thermocouple bundle; PMI-04 harness; "
                      "source-chamber pressure line.",
        "common_requirement": "(a) Lines not used by the installed occupant are installed as shams with the same routing "
                              "and fixation, terminated off-stand. (b) Routing is fixed relative to the stand; in-chamber "
                              "cable/waveguide length is fixed per arm and characterised in S1a (HW-PIM-12). (c) End-to-"
                              "end in-situ thrust-stand calibration after every configuration change. (d) A coolant pair "
                              "enters the set only if an annex requires liquid cooling, and then as a sham in every other "
                              "configuration (DEV-RF-03).",
        "units": ["calibrations", "m"],
        "quantities": [
            sourced("calibrations_before_min", HW, hw_req("HW-SVC-02") + "/values/calibrations_before_min",
                    role="proposed_requirement"),
            sourced("calibrations_after_min", HW, hw_req("HW-SVC-02") + "/values/calibrations_after_min",
                    role="proposed_requirement"),
            tbd("in_chamber_line_lengths", "m", "the RF and ECR chain designs and the facility layout", "S1a "
                "(load-plane characterisation, M3)"),
            tbd("stand_magnetic_parts", "-", "the W4 thrust-stand definition (fo_instrumentation_definition)", "S1a",
                ref=(HW, hw_req("HW-SVC-05") + "/values/stand_magnetic_parts")),
        ],
        "satisfiability": {
            "PIM-RF": sat("BY_DESIGN", "RF coax live; microwave feed and ECR magnet leads as shams."),
            "PIM-ECR": sat("BY_DESIGN", "microwave feed and magnet leads live; RF coax as a sham."),
            "PIM-0": sat("BY_DESIGN", "all source lines as shams terminated off-stand; thermocouples and harness live."),
        },
        "verification": {"method": "inspection + in-situ calibration per configuration", "stage": "S1a; S1b; every "
                         "configuration change"},
        "traces_to": ["HW-SVC-01", "HW-SVC-02", "HW-SVC-05", "HW-PIM-12", "lane 06 SHAM_RF / SHAM_ECR", "lane 25 G5"],
    })

    items.append({
        "id": "PMI-09",
        "boundary": "permitted_magnetic_field_disturbance",
        "title": "Permitted magnetic-field disturbance at the Hall channel",
        "definition": "Reference: the H-1 B-field definition is the HW-0 (PIM-0 installed) centreline B(z) over "
                      "[0, domain_length] at the single pre-registered magnet_setting_schedule of MC-1 (lane 17 INV-B1, "
                      "INV-B2), mapped per HW-MC-03 with coil currents, probe calibration, registration (z = 0 at the anode "
                      "face) and sha256. With any occupant installed, in every control state (M0, M0b, and M0c where an "
                      "ECR electromagnet allows it), the combined B(z) (MC-1 plus any module magnet fringe plus any change "
                      "of the MC-1 working point) must equal the reference within the owner's INV-B3 tolerance epsilon_B.",
        "common_requirement": "(a) MC-1 is never modified between arms; a per-arm coil re-trim is only a separately pre-"
                              "registered sensitivity condition. (b) Module structures are non-ferromagnetic; the only "
                              "magnetic part of an occupant is its declared magnet (HW-PIM-03). (c) epsilon_B is admissible "
                              "only if |S_B| * epsilon_B stays within the owner-assigned variance share, S_B = d ln(T/P_bus) "
                              "/ d ln B from the S1 coil-current scan (HW-MC-05). (d) An occupant outside the tolerance "
                              "makes its arm non-comparable under this reference (INV-B3): recorded, never waived, never "
                              "compensated inside the primary comparison.",
        "units": ["T", "-", "m"],
        "quantities": [
            tbd("INV_B3_tolerance_epsilon_B", "-", "an owner decision (lane 17 Q5, HWQ-04) informed by the S1 sensitivity "
                "S_B", "LOCK-1 (tolerance form) / LOCK-2 (value after S1b)",
                ref=(HW, hw_req("HW-PIM-06") + "/values/INV_B3_tolerance")),
            tbd("S_B", "-", "the S1 coil-current scan on HW-0", "S1b", ref=(HW, hw_req("HW-MC-05") + "/values/S_B")),
            tbd("module_to_channel_distance", "m", "the module and H-1 designs and a magnetostatic computation of the "
                "combined circuit", "design (MCQ-QT-09) before HWQ-05; verified by S1a B(z) maps",
                ref=(HW, hw_req("HW-PIM-06") + "/values/module_to_channel_distance")),
            tbd("bz_uncertainty", "T", "the W4 instrumentation definition and the INV-B3 tolerance (HWQ-04)", "S1a",
                ref=(HW, hw_req("HW-MC-03") + "/values/bz_uncertainty")),
            sourced("B_hall_typical_xenon_database_context", HW, "/derived_numbers/inputs/B_hall_typical_xenon_database_G",
                    role="context_only", note="xenon-database typical Hall field (lane 17 EV-B4); NOT a Vyovrinda H-1 "
                                              "value and not a tolerance"),
        ],
        "satisfiability": {
            "PIM-RF": sat("BY_DESIGN", "v1 is an unmagnetized ICP (HW-PIM-05, PROPOSED) with non-ferromagnetic "
                                       "structure; an assist magnet would move it to an open design risk (DEV-RF-01)."),
            "PIM-ECR": sat("IN_PRINCIPLE_OPEN_DESIGN_RISK", "the resonance field is of order four times the xenon-database "
                           "typical Hall field (annex PME-02), so the magnet fringe at the channel is a first-order design "
                           "question; meetable by distance, magnet type and return yoke/shielding, to be shown by the "
                           "MCQ-QT-09 analysis and S1a M0/M0b/M0c maps (DEV-ECR-01)."),
            "PIM-0": sat("TRIVIAL", "no magnet, non-ferromagnetic (HW-PIM-02); defines the reference map."),
        },
        "verification": {"method": "magnetostatic analysis + B(z) maps per control state", "stage": "design; S1a; before "
                         "and after each configuration's block series"},
        "traces_to": ["lane 17 INV-B1, INV-B2, INV-B3", "HW-MC-01", "HW-MC-03", "HW-MC-05", "HW-PIM-03", "HW-PIM-06",
                      "HW-MC-12", "MCQ-QT-09"],
        "why_common_not_annex": "The item is a comparability condition on the Hall accelerator (lane 17 INV-B3) that every "
                                "occupant must meet, not a design preference; it is written occupant-agnostically. PIM-0 "
                                "and PIM-RF meet it trivially or by design; for PIM-ECR it is an open design risk whose "
                                "outcome is measured, so the item does not structurally exclude the ECR branch.",
    })

    items.append({
        "id": "PMI-10",
        "boundary": "allowable_pressure_drop",
        "title": "Allowable pressure drop (pressure-drop class)",
        "definition": "Pressure drop of an occupant at flow m_dot and composition x_s: dp_occ(m_dot, x_s) = p_man(occ) - "
                      "p_man(PIM-0) at the same MFC setpoints, cold (no plasma), where p_man is the capacitance-manometer "
                      "pressure at the manifold upstream of IP-UP (HW-FS-04, INS-06). IP-DN has no port (it would change "
                      "H-1). An occupant belongs to the common pressure-drop class if |dp_occ| <= dp_class at every grid "
                      "flow.",
        "common_requirement": "(a) dp_occ is measured in S1a at every grid flow in every configuration and reported as part "
                              "of R_install (lane 25 attribution split), never corrected (HW-FS-05). (b) Any conductance "
                              "prediction uses the interstage-model rules: free-molecular (Santeler/Chiggiato) only for "
                              "Kn > 0.5, otherwise an explicit sourced conductance (INTERSTAGE_MODEL section 4). (c) If an "
                              "occupant falls outside the class, the control is a passive matched PIM-0 insert (DEV-H0-03) "
                              "or reporting the difference; the MFC setpoints are never changed per arm.",
        "units": ["Pa"],
        "quantities": [
            tbd("dp_class", "Pa", "the S1a cold-flow manifold-pressure repeatability of PIM-0 re-installation, the W1 "
                "registered P_feed tolerance per test point and an owner decision", "S1a (measurement) -> LOCK-2 (value)"),
            tbd("dp_occ_per_grid_flow", "Pa", "S1a cold-flow measurements at the released ground-qualification feed "
                "points (S1A-C3)", "S1a"),
            tbd("pressure_loss_IF_A5", "Pa", "a valve/line flow model (upstream ICD IF-A5 pressure_loss_Pa is a gap)",
                "outside this lane (upstream ICD)"),
        ],
        "satisfiability": {
            "PIM-RF": sat("BY_DESIGN", "discharge-tube/interstage conductance chosen within the class, measured S1a."),
            "PIM-ECR": sat("BY_DESIGN", "coupling-structure/interstage conductance chosen within the class, measured S1a."),
            "PIM-0": sat("BY_DESIGN", "reference of the class; matched inserts if RF and ECR differ (DEV-H0-03)."),
        },
        "verification": {"method": "cold-flow test", "stage": "S1a; every configuration change"},
        "traces_to": ["HW-FS-04", "HW-FS-05", "INS-06", "INTERSTAGE_MODEL.md section 4", "lane 25 R_install",
                      "ICD IF-A5 pressure_loss_Pa"],
    })

    L25 = "LANE25"
    items.append({
        "id": "PMI-11",
        "boundary": "installation_removal_reproducibility",
        "title": "Installation/removal reproducibility",
        "definition": "Re-mount (installation) reproducibility u_inst of ln(T/P_bus) per installation, 1 sigma. "
                      "Requirement: u_inst <= u_inst,max at the n fixed at LOCK-2 (HW-SVC-03, package REQ-HW-04), unless "
                      "a no-vent switch (D-06-B) is adopted. PROPOSED hardware sub-allocation: five equal root-sum-square "
                      "contributors (c1 stand calibration and zero shift, c2 thrust-axis alignment, c3 magnetic-circuit / "
                      "B(z) change, c4 gas path, distributor and leak change, c5 service-line, thermal and electrical "
                      "environment change).",
        "common_requirement": "How S1/S1b measures it (lane 25 s1_plan.S1b_hall_on): K re-mount cycles on HW-0 at OP3; each "
                              "cycle vents, removes and re-installs the module slot occupant and mount exactly as a "
                              "configuration change does, pumps down, runs the pre-registered conditioning and T-SETTLE, "
                              "the in-situ calibration, then r readings; u_inst = sample SD of the K cycle means of "
                              "ln(T/P_bus) with K - 1 degrees of freedom. The procedure replicated must be the adopted "
                              "configuration-change procedure (HW-SVC-04, owner HWQ-01). Every exchange records: serials "
                              "and part log, torque and alignment, leak check and cold-flow manifold pressure, B(z) map, "
                              "in-situ calibration, dummy-load pickup, witness-set exchange (hardware "
                              "verification_per_configuration_change).",
        "units": ["ln-ratio (1 sigma, per installation)", "deg", "cycles (K)", "readings (r)", "-"],
        "quantities": [
            sourced("u_inst_max_n4", HW, "/derived_numbers/inputs/u_inst_max_n4", role="requirement_bound"),
            sourced("u_inst_max_n6", HW, "/derived_numbers/inputs/u_inst_max_n6", role="requirement_bound"),
            sourced("u_inst_max_n8", HW, "/derived_numbers/inputs/u_inst_max_n8", role="requirement_bound"),
            sourced("n_installation_contributors", HW, "/derived_numbers/inputs/n_installation_contributors",
                    role="proposed_allocation"),
            sourced("u_contributor_max_n4", HW, "/derived_numbers/outputs/u_contributor_max_n4", role="derived_allocation"),
            sourced("theta_align_max_n4_deg", HW, "/derived_numbers/outputs/theta_align_max_n4_deg",
                    role="derived_allocation", note="alignment change whose cosine loss alone uses one contributor share; "
                                                    "first-order geometry, not a claim that alignment dominates"),
            sourced("u_contributor_max_n6", HW, "/derived_numbers/outputs/u_contributor_max_n6", role="derived_allocation"),
            sourced("theta_align_max_n6_deg", HW, "/derived_numbers/outputs/theta_align_max_n6_deg",
                    role="derived_allocation"),
            sourced("u_contributor_max_n8", HW, "/derived_numbers/outputs/u_contributor_max_n8", role="derived_allocation"),
            sourced("theta_align_max_n8_deg", HW, "/derived_numbers/outputs/theta_align_max_n8_deg",
                    role="derived_allocation"),
            sourced("K_remount_cycles", L25, lane25_threshold("T-S1-REMOUNT-CYCLES"), role="proposed_plan"),
            sourced("r_readings_per_cycle", L25, lane25_threshold("T-S1-READINGS-PER-CYCLE"), role="proposed_plan"),
            tbd("u_inst_achieved", "ln-ratio (1 sigma, per installation)", "the S1b re-mount series on the delivered "
                "hardware", "S1b -> LOCK-2"),
        ],
        "satisfiability": {
            "PIM-RF": sat("BY_DESIGN", "same flanges, alignment features and torque spec; exchange reproducibility not "
                                       "directly measured by the HW-0 S1b series (DEV-RF-05)."),
            "PIM-ECR": sat("BY_DESIGN", "same flanges, alignment features and torque spec; magnet adds c3 exposure; not "
                                        "directly measured by S1b (DEV-ECR-07)."),
            "PIM-0": sat("BY_DESIGN", "the S1b series measures exactly this occupant's exchange."),
        },
        "verification": {"method": "test (re-mount series) + per-exchange records", "stage": "S1b (K re-mounts); S6 "
                         "check; every configuration change"},
        "traces_to": ["HW-SVC-03", "HW-SVC-04", "package REQ-HW-04, D-01, D-06", "lane 25 s1_plan.S1b_hall_on",
                      "lane 25 section 6.4 (G5)", "A6 fo_phase1_prereg_framework (S1/S1b establish remount "
                      "reproducibility)"],
    })
    return items


COMMON_IDS = [f"PMI-{i:02d}" for i in range(1, 12)]
BOUNDARY_KEYS = ["mechanical_envelope_and_mounting_datum", "gas_flow_path_and_pressure_boundary",
                 "electrical_power_boundary", "control_enable_interlock_lines", "thermal_rejection_interface",
                 "grounding_and_shielding", "diagnostics", "service_line_routing", "permitted_magnetic_field_disturbance",
                 "allowable_pressure_drop", "installation_removal_reproducibility"]


def annexes() -> dict:
    HW = "HW"
    rf = {
        "id": "ANNEX-RF",
        "module": "PIM-RF",
        "architecture": "rf_hall",
        "role": "PRIMARY_CONTINGENCY",
        "role_basis": "A5 architecture.reserved_interface ('RF pre-ionization module interface', baseline_flight_hardware "
                      "false) and decision_statement ('RF pre-ionization is retained as an interface-ready Phase-1 "
                      "contingency'); A6 fo_preionizer_module_icd ('RF stays the preferred contingency').",
        "scope": "RF source + interstage between IP-UP and IP-DN; off-module chain: DC-fed RF generator, matching network, "
                 "directional coupler at the load plane (hardware configuration item PIM-RF).",
        "uses_common_items": list(COMMON_IDS),
        "module_specific_items": [
            {"id": "PMR-01", "title": "RF frequency", "text": "Not selected. Feedthrough, coax, matching network and "
             "sensors follow the selection.",
             "quantities": [
                 tbd("f_rf", "Hz", "the RF module design (owner)", "procurement: RF module design decision",
                     ref=(HW, hw_req("HW-PIM-11") + "/values/f_rf")),
                 sourced("f_rf_evidence_IPG6S", "RFEV", ev_entry("RFEV", "RF-IPG6S-01"), role="context_only",
                         status="SOURCED", note="evidence span only (HW-PIM-11); not a selection"),
                 sourced("f_rf_evidence_IPT", "RFEV", ev_entry("RFEV", "RF-IPT20-01"), role="context_only",
                         status="SOURCED", note="evidence span only (HW-PIM-11); not a selection"),
             ]},
            {"id": "PMR-02", "title": "rf_source load plane and chain", "text": "Net RF power (forward minus reflected) at "
             "the coil/antenna feed terminals (bus_power_boundary_v1 rf_source). DC-fed generator preferred so its DC "
             "input is metered as efficiency evidence; coupler at the load plane or upstream with the matching-network "
             "and cable loss characterised in S1a (evidence class 'reconstructed'). Matching-network location (on- or "
             "off-module) is a design choice that changes module mass and heat (DEV-RF-06).",
             "quantities": [
                 sourced("reflected_fraction_evidence_auto_matched_ICP", "RFEV", ev_entry("RFEV", "RF-SCHU24-05"),
                         role="context_only", status="SOURCED", note="different device (planar-coil ICP, 80/20 N2/O2); "
                                                                      "shows the order achievable with auto-matching"),
                 sourced("reflected_fraction_evidence_unmatched_IPT", "RFEV", ev_entry("RFEV", "RF-IPT20-D1"),
                         role="context_only", status="SOURCED", note="no plasma, before any matching network"),
             ]},
            {"id": "PMR-03", "title": "RF source power range", "text": "Operable from P_lo to P_hi at the W1 grid flows on "
             "Xe (start) and the working gases; P_lo = max(lowest stable, 0.5 P_hi) (lane 25 T-PLO-FRACTION, PROPOSED).",
             "quantities": [tbd("P_hi_rf", "W", "the source allocation in bus_power_boundary_v1 (owner, lane 11)",
                                "LOCK-1; bench stage S3", ref=(HW, hw_req("HW-PIM-08") + "/values/P_hi"))]},
            {"id": "PMR-04", "title": "RF assist magnet", "text": "PROPOSED: PIM-RF v1 is an unmagnetized ICP (HW-PIM-05). "
             "Published air-species RF sources used an applied field to ignite at low flow; bus_power_boundary_v1 has no "
             "slot for an RF assist magnet (DEV-RF-01).",
             "quantities": [sourced("B_rf_ignition_assist_evidence", HW, hw_req("HW-PIM-05") +
                                    "/values/B_rf_ignition_assist_T", role="context_only",
                                    note="on the IPG6-S source axis, 'in most cases' for O2 and Ar; N2 ignited without "
                                         "it (RF-IAC18-01); not a field inside any Hall channel")]},
            {"id": "PMR-05", "title": "Plasma-facing materials", "text": "Dielectric tube, antenna and Faraday shield "
             "O2-compatible; no accessed source measures their erosion, sputtering or contamination (HW-PIM-10).",
             "quantities": [tbd("module_materials_rf", "-", "the RF module design and cited O2-compatibility evidence",
                                "procurement: RF module design; inspection at HRR and after the block series",
                                ref=(HW, hw_req("HW-PIM-10") + "/values/module_materials"))]},
            {"id": "PMR-06", "title": "RF-specific trips", "text": "Reflected-power trip (and generator fault) feeding "
             "PMI-04 L3/L5.", "quantities": [tbd("rf_reflected_power_trip", "W", "the selected generator's rating "
                                                  "(A4: limits from real hardware ratings)", "S1A-C2")]},
            {"id": "PMR-07", "title": "RF containment", "text": "Faraday shield/screen inside the PMI-01 envelope, bonded "
             "at the PMI-06 point.", "quantities": []},
            {"id": "PMR-08", "title": "Cooling", "text": "PROPOSED: passive/radiative module cooling within PMI-05. "
             "Evidence: the IPG6-S laboratory source had coil, quartz tube, injector and oscillator all water-cooled "
             "(RF-IPG6S-09, measured, qualitative); downscaling with passive cooling was named its biggest challenge. "
             "If liquid cooling is needed, DEV-RF-03 applies.", "quantities": []},
        ],
        "deviations": [
            {"id": "DEV-RF-01", "common_items": ["PMI-03", "PMI-09"], "deviation": "an RF assist magnet has no "
             "bus_power_boundary_v1 slot and adds a field disturbance", "confound_risk": "unbooked power (P_bus "
             "understated) and a B(z) change attributed to the ionization method",
             "proposed_control": "v1 unmagnetized (HW-PIM-05); if the owner adopts a magnet, a booking slot in a new "
                                 "boundary version before LOCK-1 (HWQ-06) and M0/M0b(/M0c) B(z) maps under PMI-09"},
            {"id": "DEV-RF-02", "common_items": ["PMI-06"], "deviation": "Faraday shield or interstage electrode "
             "potential and any interstage current", "confound_risk": "cathode current budget and plasma potential differ "
                                                                     "between arms", "proposed_control": "declared "
             "potential identical to PIM-0 (HW-ELEC-02); I_interstage measured every reading"},
            {"id": "DEV-RF-03", "common_items": ["PMI-05", "PMI-08", "PMI-03"], "deviation": "liquid cooling would add "
             "coolant lines on the stand and possibly a pump load", "confound_risk": "coolant-line stiffness and "
             "flow-induced forces change stand tare/drift; pump power without a v1 slot",
             "proposed_control": "prefer passive cooling; if unavoidable, a coolant pair in every configuration with the "
                                 "same flow through a bypass at the slot for PIM-0/PIM-ECR (PROPOSED), and a booking slot "
                                 "defined before LOCK-1"},
            {"id": "DEV-RF-04", "common_items": ["PMI-07"], "deviation": "RF pickup on common diagnostics",
             "confound_risk": "biased I_d, thrust-stand or probe readings in rf_hall only",
             "proposed_control": "DUMMY_LOAD_PICKUP at every pre-registered power, every pump-down (HW-ELEC-03)"},
            {"id": "DEV-RF-05", "common_items": ["PMI-11"], "deviation": "the S1b re-mount series measures the PIM-0 "
             "exchange only", "confound_risk": "an RF-module-specific installation term not covered by u_inst",
             "proposed_control": "PROPOSED S1a no-plasma module-exchange series with PIM-RF unpowered (cold-flow manifold "
                                 "pressure, in-situ calibration zero/tare, B(z)); no held-out H-1 observable exposed "
                                 "(S1A-FW)"},
            {"id": "DEV-RF-06", "common_items": ["PMI-01", "PMI-05"], "deviation": "an on-module matching network adds "
             "mass and heat", "confound_risk": "stand load and thermal drift", "proposed_control": "mass/CG recorded; "
                                                                                                  "per-configuration "
                                                                                                  "in-situ calibration "
                                                                                                  "(HW-SVC-02); heat "
                                                                                                  "recorded (PMI-05)"},
        ],
    }

    ecr = {
        "id": "ANNEX-ECR",
        "module": "PIM-ECR",
        "architecture": "ecr_hall",
        "role": "ALTERNATE",
        "alternate_not_equal_proposal_baseline": True,
        "role_statement": "This annex does NOT make ECR an equal proposal baseline. Per A5, ECR pre-ionization is an "
                          "alternate test module only, not baseline installed flight hardware, used only if RF fails the "
                          "common-boundary comparison (branch C_ecr_hall: Hall-only fails, RF fails its common-boundary "
                          "criterion and ECR passes it). Per A6, RF stays the preferred contingency, ECR is NOT elevated "
                          "to an equal proposal baseline, and the common interface only prevents the fixture from "
                          "structurally disadvantaging a Phase-1 branch before measurement.",
        "scope": "ECR source + interstage + ECR magnet between IP-UP and IP-DN; off-module chain: DC-fed microwave "
                 "generator, isolator, directional coupler, feed line to the coupling structure (PIM-ECR).",
        "uses_common_items": list(COMMON_IDS),
        "module_specific_items": [
            {"id": "PME-01", "title": "Microwave frequency", "text": "Not selected; candidates only.",
             "quantities": [
                 tbd("f_ecr", "Hz", "the ECR module design (owner)", "procurement: ECR module design decision",
                     ref=(HW, hw_req("HW-PIM-11") + "/values/f_ecr")),
                 sourced("f_ecr_candidate_2p45GHz", HW, "/derived_numbers/inputs/f_ecr_candidate_2p45GHz_Hz",
                         role="candidate"),
                 sourced("f_ecr_candidate_5p8GHz", HW, "/derived_numbers/inputs/f_ecr_candidate_5p8GHz_Hz",
                         role="candidate"),
             ]},
            {"id": "PME-02", "title": "Resonance field", "text": "B_res = 2 pi f m_e / e (identity) at the candidates.",
             "quantities": [
                 sourced("B_res_2p45GHz", HW, "/derived_numbers/outputs/B_res_ecr_2p45GHz_T", role="identity"),
                 sourced("B_res_5p8GHz", HW, "/derived_numbers/outputs/B_res_ecr_5p8GHz_T", role="identity"),
                 sourced("ratio_B_res_2p45GHz_to_B_hall_typical", HW,
                         "/derived_numbers/outputs/ratio_B_res_2p45GHz_to_B_hall_typical", role="context_only",
                         note="denominator is a xenon-database value, not a Vyovrinda value"),
             ]},
            {"id": "PME-03", "title": "ECR magnet type", "text": "Owner decision HWQ-05 (HW-PIM-04): an electromagnet "
             "allows the M0c state and is booked as ecr_magnet coil power; a permanent magnet makes M0b = M0c and is "
             "booked as 0 W with efficiency 1. The test magnet type matches the flight design intent, or the ecr_magnet "
             "ledger entry is the flight value (LOCK-1 input).", "quantities": []},
            {"id": "PME-04", "title": "Fringe field and magnet temperature", "text": "Fringe field in the Hall channel "
             "(MCQ-QT-09) and, for a permanent magnet, demagnetization exposure to the combined opposing field at the "
             "magnet temperature (HW-MC-09, HW-PIM-15); magnet temperature measured during operation.",
             "quantities": [
                 tbd("ecr_fringe_field_in_channel", "T", "the MCQ-QT-09 magnetostatic analysis of the selected ECR "
                     "magnet", "design before HWQ-05; S1a maps", ref=(HW, hw_req("HW-PIM-15") +
                                                                      "/values/ecr_fringe_field_in_channel")),
                 tbd("ecr_magnet_temperature", "degC", "the HW-ECR module thermal design (lane 15 ecr_magnet inputs; "
                     "MCQ ecr_magnet_C)", "design; measured S3/Phase 2",
                     ref=(HW, hw_req("HW-PIM-15") + "/values/ecr_magnet_temperature")),
             ]},
            {"id": "PME-05", "title": "Microwave chain and load plane", "text": "Net microwave power at the coupling-"
             "structure input (bus_power_boundary_v1 ecr_source): DC-fed generator, isolator, directional coupler, feed "
             "line; chain loss between coupler and load plane characterised in S1a where the coupler cannot sit at the "
             "load plane (HW-PIM-12).",
             "quantities": [sourced("chain_attenuation_evidence", "ECREV", ev_entry("ECREV", "ECR-E032"),
                                    role="context_only", status="SOURCED",
                                    note="another facility's coupler-to-thruster chain; shows why the S1a chain "
                                         "characterisation is needed, not a Vyovrinda value")]},
            {"id": "PME-06", "title": "Microwave-specific trips", "text": "Reflected-power / isolator-load and "
             "electromagnet overcurrent/overtemperature trips feeding PMI-04 L3/L5.",
             "quantities": [tbd("ecr_trip_limits", "-", "the selected generator, isolator and magnet ratings (A4)",
                                "S1A-C2")]},
            {"id": "PME-07", "title": "Microwave leakage containment", "text": "Inside the PMI-01 envelope, bonded at "
             "the PMI-06 point; feed-line penetration sealed (PMI-02).", "quantities": []},
            {"id": "PME-08", "title": "ECR source power range", "text": "As PMR-03 for the ECR source.",
             "quantities": [tbd("P_hi_ecr", "W", "the source allocation in bus_power_boundary_v1 (owner, lane 11)",
                                "LOCK-1; bench stage S3", ref=(HW, hw_req("HW-PIM-08") + "/values/P_hi"))]},
            {"id": "PME-09", "title": "Plasma-facing materials", "text": "Coupling structure and antenna O2-compatible "
             "(HW-PIM-10).", "quantities": [tbd("module_materials_ecr", "-", "the ECR module design and cited "
                                                 "O2-compatibility evidence", "procurement: ECR module design",
                                                 ref=(HW, hw_req("HW-PIM-10") + "/values/module_materials"))]},
        ],
        "deviations": [
            {"id": "DEV-ECR-01", "common_items": ["PMI-09"], "deviation": "the resonance magnet's fringe field reaches "
             "the Hall channel", "confound_risk": "a B(z) change attributed to the ionization method",
             "proposed_control": "MCQ-QT-09 analysis before the magnet selection; M0/M0b/M0c maps; INV-B3 tolerance; if "
                                 "exceeded the arm is reported non-comparable (no coil re-trim in the primary "
                                 "comparison)"},
            {"id": "DEV-ECR-02", "common_items": ["PMI-01", "PMI-08"], "deviation": "magnet mass and interaction with "
             "magnetic parts of the thrust stand", "confound_risk": "stand calibration shift in ecr_hall only",
             "proposed_control": "per-configuration in-situ calibration; calibration with the ECR module installed, "
                                 "magnet on and off where possible (HW-SVC-05)"},
            {"id": "DEV-ECR-03", "common_items": ["PMI-08"], "deviation": "a waveguide feed is stiffer than a coax",
             "confound_risk": "stand stiffness/tare change", "proposed_control": "the microwave feed is a sham in every "
                                                                                 "other configuration (same routing and "
                                                                                 "fixation); coax preferred where the "
                                                                                 "frequency permits (TBD)"},
            {"id": "DEV-ECR-04", "common_items": ["PMI-05"], "deviation": "magnet and coupling-structure heating",
             "confound_risk": "anode/gas temperature difference", "proposed_control": "recorded arm consequence; magnet "
                                                                                    "and anode temperatures logged"},
            {"id": "DEV-ECR-05", "common_items": ["PMI-03"], "deviation": "electromagnet coil power booked under "
             "ecr_magnet; lane 19 abep_sim/cathode_integration.py PREIONIZER_COMPONENTS['ecr_hall'] lists only "
             "ecr_source (its ARCH_EXTRA_BOUNDARY_COMPONENTS includes ecr_magnet), and abep_sim/thermal_life.py covers "
             "only a permanent ecr_magnet", "confound_risk": "an ECR magnet load unseen by the lane 19 on/off checks and "
                                                              "unchecked thermally if an electromagnet is chosen",
             "proposed_control": "this ICD follows bus_power_boundary_v1 (ecr_source + ecr_magnet); reconciliation "
                                 "belongs to the owning lanes (flagged, not fixed here)"},
            {"id": "DEV-ECR-06", "common_items": ["PMI-04", "PMI-09"], "deviation": "a permanent magnet cannot be "
             "switched off (M0b = M0c)", "confound_risk": "installation and energization effects of the magnet cannot "
                                                           "be separated (SHAM_ECR)",
             "proposed_control": "bound by M0 vs M0b B(z) maps and the re-trimmed-coil sensitivity condition (lane 37 "
                                 "section 3), reported"},
            {"id": "DEV-ECR-07", "common_items": ["PMI-11"], "deviation": "the S1b re-mount series measures the PIM-0 "
             "exchange only", "confound_risk": "an ECR-module-specific installation term (incl. magnet alignment)",
             "proposed_control": "PROPOSED S1a no-plasma module-exchange series with PIM-ECR unpowered (cold-flow "
                                 "manifold pressure, in-situ calibration zero/tare, B(z) incl. magnet); S1A-FW respected"},
        ],
    }

    hw0 = {
        "id": "ANNEX-HW0",
        "module": "PIM-0",
        "architecture": "hall_only",
        "role": "CONTROLLED_REFERENCE_BLANK",
        "role_statement": "HW-0 uses a blank/spacer module with equivalent interfaces and service-line presence so that "
                          "module exchange is the controlled variable in Phase 1 (A6). HW-0 is the only configuration "
                          "reported as hall_only; M0b (module installed, source unpowered) is a control state, never "
                          "reported as hall_only.",
        "scope": "flow-equivalent spacer between IP-UP and IP-DN; replicates the module mechanical envelope and gas path, "
                 "no source hardware, no magnet (HW-PIM-02).",
        "uses_common_items": list(COMMON_IDS),
        "module_specific_items": [
            {"id": "PM0-01", "title": "Flow-equivalent duct", "text": "Replicates the module gas path and ports; non-"
             "ferromagnetic; same body potential and bonding point.", "quantities": []},
            {"id": "PM0-02", "title": "Dummy/terminated lines", "text": "RF coax and microwave feed as shams terminated "
             "off-stand; ECR magnet lead pair terminated; PMI-04: L1 reports PIM-0, L2 terminated, L3 jumpered, L4/L5 "
             "constant; thermocouples live.", "quantities": []},
            {"id": "PM0-03", "title": "Ports", "text": "Source-chamber pressure port blanked or connected identically; "
             "I_src collector access present; OES port blanked if any occupant carries one.", "quantities": []},
            {"id": "PM0-04", "title": "Witness set", "text": "Carries the per-arm interstage witness set at the identical "
             "module-outlet position on the module side of IP-DN (HW-PIM-14).",
             "quantities": [tbd("witness_position", "-", "the module interface control drawing (HW-PIM-01)",
                                "procurement: interface control drawing",
                                ref=(HW, hw_req("HW-PIM-14") + "/values/witness_position"))]},
            {"id": "PM0-05", "title": "Thermal footprint", "text": "Same IP-DN isolator hardware and thermocouple "
             "positions; no heater emulation of module waste heat (PMI-05 b).", "quantities": []},
            {"id": "PM0-06", "title": "Pressure-drop class reference", "text": "Defines dp = 0 of PMI-10; matched "
             "passive inserts only if the RF and ECR modules fall in different classes (DEV-H0-03).", "quantities": []},
        ],
        "deviations": [
            {"id": "DEV-H0-01", "common_items": ["PMI-09"], "deviation": "PIM-0 cannot reproduce the ECR magnet's "
             "magnetic footprint without changing B(z)", "confound_risk": "field difference between HW-0 and HW-ECR",
             "proposed_control": "not emulated (a dummy magnet would itself disturb B); measured by M0/M0b/M0c maps "
                                 "against INV-B3"},
            {"id": "DEV-H0-02", "common_items": ["PMI-05"], "deviation": "PIM-0 dissipates nothing",
             "confound_risk": "gas and anode temperature differ between arms", "proposed_control": "recorded arm "
             "consequence, never equalised (hardware identity_matrix may_differ); anode temperature logged; a heated "
             "PIM-0 would not represent hall_only"},
            {"id": "DEV-H0-03", "common_items": ["PMI-10", "PMI-02"], "deviation": "one PIM-0 can match only one "
             "conductance if the RF and ECR modules differ", "confound_risk": "feed pressure at the distributor differs "
                                                                               "between arms",
             "proposed_control": "PROPOSED passive matched inserts (PIM-0 in the RF class and in the ECR class), each "
                                 "checked cold in S1a; otherwise the difference is reported in R_install"},
            {"id": "DEV-H0-04", "common_items": ["PMI-01"], "deviation": "PIM-0 mass and centre of gravity differ from "
             "the source modules", "confound_risk": "stand load", "proposed_control": "per-configuration in-situ "
                                                                                      "calibration (HW-SVC-02)"},
            {"id": "DEV-H0-05", "common_items": ["PMI-04"], "deviation": "HW-0 has no PREIONIZER_IGNITION dwell in its "
             "start sequence", "confound_risk": "different Xe exposure, conditioning and thermal history before the "
                                                "atmosphere transfer", "proposed_control": "PROPOSED time-matched Xe hold "
             "in WARM_UP equal to the pre-registered pre-ionizer dwell; Xe consumed recorded against the single Xe "
             "allocation (A5 xe_mass_allocation)"},
        ],
    }
    return {"ANNEX-RF": rf, "ANNEX-ECR": ecr, "ANNEX-HW0": hw0}


def confound_table() -> list:
    rows = [
        ("CF-01", "module mass and centre of gravity", "spacer mass", "source + interstage (+ on-module matching)",
         "source + interstage + magnet/yoke", "stand load, stiffness and tare", "per-configuration in-situ calibration "
         "(HW-SVC-02); mass/CG recorded", ["PMI-01", "PMI-08"], "MEASURED_AND_REPORTED"),
        ("CF-02", "mounting and thrust-axis alignment", "same flanges", "same flanges", "same flanges",
         "cosine loss, zero shift", "common datum and torque spec; torque/alignment record; S1b u_inst (+ PROPOSED S1a "
         "module-exchange series)", ["PMI-01", "PMI-11"], "REMOVED_BY_INTERFACE_AND_MEASURED"),
        ("CF-03", "gas-path conductance, volume and surface", "flow-equivalent duct", "tube + interstage",
         "coupling structure + interstage", "feed pressure at the distributor, transients, residence time",
         "pressure-drop class (PMI-10), cold-flow manifold pressure per configuration, wetted volume recorded; MFC "
         "setpoints identical", ["PMI-02", "PMI-10"], "MEASURED_AND_REPORTED"),
        ("CF-04", "module wall surfaces (O recombination, outgassing, erosion products)", "spacer walls",
         "dielectric tube", "coupling structure", "species at HALL_INLET_Z0, deposits on H-1",
         "M0b control state (installed, unpowered); per-arm witness set (HW-PIM-14); inspection before/after",
         ["PMI-02", "PMI-07"], "RECORDED_ARM_CONSEQUENCE"),
        ("CF-05", "magnetic field at the Hall channel", "none (reference)", "none in v1", "resonance magnet fringe",
         "B(z) change", "PMI-09 INV-B3 tolerance; M0/M0b/M0c maps; non-ferromagnetic structures", ["PMI-09"],
         "MEASURED_WITH_COMPARABILITY_GATE"),
        ("CF-06", "waste heat and thermal history", "none", "coil/tube/generator heat", "coupling/magnet heat",
         "anode and gas temperature, stand drift", "declared module thermal path; isolated/instrumented IP-DN; "
         "T-SETTLE; anode temperature logged; order-balanced execution (A6 clarification)", ["PMI-05"],
         "RECORDED_ARM_CONSEQUENCE"),
        ("CF-07", "electrical potential, interstage current, generator pickup", "declared potential", "same + RF "
         "return", "same + microwave return", "cathode current budget, diagnostic bias", "one declared potential "
         "(HWQ-07); I_interstage measured; separated returns; DUMMY_LOAD_PICKUP every pump-down", ["PMI-06", "PMI-07"],
         "REMOVED_BY_INTERFACE_AND_MEASURED"),
        ("CF-08", "service lines on the stand", "all lines as shams", "RF coax live, others shams", "microwave feed and "
         "magnet leads live, coax sham", "stand stiffness, tare, thermal drift", "union line set present in every "
         "configuration (HW-SVC-01)", ["PMI-08"], "REMOVED_BY_INTERFACE"),
        ("CF-09", "source power accounting", "no component", "rf_source", "ecr_source + ecr_magnet",
         "P_bus understated if a load is missed", "bus_power_boundary_v1 slots only; no slotless module load in v1; "
         "load-plane measurement", ["PMI-03", "PMI-07"], "REMOVED_BY_INTERFACE"),
        ("CF-10", "plume back-flow and extra atomic O at C-1", "baseline", "possible", "possible",
         "cathode condition", "recorded arm consequence; near-cathode RGA sampling (HW-C1-07)", ["PMI-07"],
         "RECORDED_ARM_CONSEQUENCE"),
        ("CF-11", "run order, conditioning, drift, hysteresis", "-", "-", "-", "architecture confounded with time",
         "order-balanced scheme with HW-0 reference points (A6 clarification_execution_order); XE_HEALTH_CHECK; "
         "MODULE_ID in every record", ["PMI-04", "PMI-11"], "PROTOCOL_CONTROL"),
        ("CF-12", "start sequence and Xe exposure", "no pre-ionizer dwell", "PREIONIZER_IGNITION on Xe",
         "PREIONIZER_IGNITION on Xe", "conditioning and thermal state at atmosphere transfer", "PROPOSED time-matched "
         "Xe hold in HW-0 (DEV-H0-05); Xe consumed against the single allocation", ["PMI-04"], "PROPOSED_CONTROL"),
        ("CF-13", "cooling provisions", "none", "passive (PROPOSED) or liquid", "passive", "coolant-line forces, pump "
         "load", "passive preferred; coolant sham pair with identical flow if liquid cooling is adopted (DEV-RF-03)",
         ["PMI-05", "PMI-08"], "PROPOSED_CONTROL"),
        ("CF-14", "configuration identity errors", "-", "-", "-", "a reading attributed to the wrong arm",
         "MODULE_ID line logged with every reading; configuration record", ["PMI-04", "PMI-07"],
         "REMOVED_BY_INTERFACE"),
    ]
    out = []
    for rid, factor, h0, rf, ecr, mech, ctl, items, st in rows:
        out.append({"id": rid, "factor": factor, "hw0": h0, "rf": rf, "ecr": ecr, "mechanism": mech,
                    "removed_or_measured_by": ctl, "common_items": items, "residual_status": st})
    return out


RESIDUAL_STATUSES = ["REMOVED_BY_INTERFACE", "REMOVED_BY_INTERFACE_AND_MEASURED", "MEASURED_AND_REPORTED",
                     "MEASURED_WITH_COMPARABILITY_GATE", "RECORDED_ARM_CONSEQUENCE", "PROTOCOL_CONTROL",
                     "PROPOSED_CONTROL"]


def build() -> dict:
    a5 = load(DECISIONS["A5"])
    g0 = load(DECISIONS["G0"])
    a6 = load(DECISIONS["A6"])
    if g0.get("verdict") != "CLEAN":
        raise RuntimeError("G0 baseline is not CLEAN; A5/A6 may not be pinned (A6 execution rule)")
    a5_sha = sha256_of(DECISIONS["A5"])
    if g0.get("a5_sha256") != a5_sha:
        raise RuntimeError("G0 a5_sha256 does not match the A5 file")
    if a6.get("follows_sha256") != a5_sha:
        raise RuntimeError("A6 follows_sha256 does not match the A5 file")
    # the bus boundary contract must match what this ICD states (read the module source, do not import it)
    with open(_abs(DELIVERABLES["BUSMOD"]), encoding="utf-8") as f:
        busmod = f.read()
    for needle in ('BOUNDARY_VERSION = "bus_power_boundary_v1"', '"rf_hall": ("rf_source",)',
                   '"ecr_hall": ("ecr_source", "ecr_magnet")', '"hall_only": ()'):
        if needle not in busmod:
            raise RuntimeError(f"abep_sim/arch_boundary.py no longer contains {needle!r}; ICD PMI-03 must be revised")

    content = {
        "id": "fo_preionizer_module_icd",
        "name": "H-1 common Pre-Ionizer Module Interface Control Document",
        "version": "1.0.0",
        "status": "DRAFT_PENDING_OWNER",
        "status_note": "Interface definition for owner review. Nothing here is approved, pre-registered, procured or "
                       "frozen; every threshold not in the RFP is PROPOSED; every numeric value is copied from a "
                       "repository deliverable with its evidence class, or is TBD.",
        "follow_on": "fo_preionizer_module_icd",
        "trigger": "T_A5_PREIONIZER_ICD",
        "lane_name_A6": "H1-ICD",
        "base_commit": BASE_COMMIT,
        "generated_by": THIS_SCRIPT,
        "companion_document": OUT_MD,
        "test": "tests/test_preionizer_module_icd.py",
        "owner_decisions": {
            "A5": {"path": DECISIONS["A5"], "sha256": a5_sha, "status": a5["status"]},
            "A6": {"path": DECISIONS["A6"], "sha256": sha256_of(DECISIONS["A6"]),
                   "authorization": "authorized_now.fo_preionizer_module_icd"},
            "A4": {"path": DECISIONS["A4"], "sha256": sha256_of(DECISIONS["A4"]),
                   "used_for": "S1a minimum interlocks and interlock-limit rule (PMI-04)"},
        },
        "g0_baseline": {
            "path": DECISIONS["G0"], "sha256": sha256_of(DECISIONS["G0"]), "verdict": g0["verdict"],
            "verified_commit": g0["verified_commit"], "a5_sha256": g0["a5_sha256"],
            "results": {k: v["outcome"] for k, v in g0["results"].items()},
            "consequence": g0["consequence"],
            "check": "the builder refuses to run unless G0 is CLEAN and its a5_sha256 and A6 follows_sha256 equal the A5 "
                     "file hash (A6: no deliverable pins A5/A6 until G0 passes)",
        },
        "pinned_inputs": {rel: sha256_of(rel) for rel in sorted(DELIVERABLES.values())},
        "not_pinned_mutable": ["lane_registry_v1.json", "trigger_registry_v1.json", "trigger ledgers "
                               "(fired_triggers.jsonl, trigger_ledger_v2.jsonl)", "docs/orchestration/runtime_state.json",
                               "docs/experiments/*/..._status_current.json"],
        "standing_facts": {
            "bundle1": "NO_BASELINE_YET (docs/milestones/bundle1/bundle1_v5.json; A6 not_authorized: changing Bundle 1)",
            "credible_hall_set": "EMPTY (A4 project_conclusion; no Hall closure admitted)",
            "a5_numbers": "A5 numbers are ALLOCATIONS or REQUIREMENTS, never predictions",
            "no_winner": "No architecture is ranked, preferred on performance or eliminated here; H-1 Phase 1 decides "
                         "among A hall_only / B rf_hall / C ecr_hall / NO_VIABLE_CASE.",
            "execution_order": "A5's per-point order names the configurations; the score-bearing order is order-balanced "
                               "(A6 clarification_execution_order).",
        },
        "architectures": list(ARCHS),
        "phase1_branch_outcomes": {"A": "hall_only", "B": "rf_hall", "C": "ecr_hall", "NO_VIABLE_CASE": None},
        "a5_reserved_interface": {
            "a5_name": a5["architecture"]["reserved_interface"]["name"],
            "a5_location": a5["architecture"]["reserved_interface"]["location"],
            "a5_requirement": a5["architecture"]["reserved_interface"]["requirement"],
            "mapping": "The A5 location is the slot IP-UP..IP-DN of the H-1 test article (W3 hardware definition). The "
                       "flight-relevant parts of this ICD are the IP-DN flange/datum on H-1 (PMI-01), the gas path and "
                       "pressure boundary (PMI-02), the bus_power_boundary_v1 slots (PMI-03) and the control lines "
                       "(PMI-04); the stand-related items (PMI-08, PMI-11) are ground-test items. A flight ICD is "
                       "Milestone C work.",
        },
        "module_slot": {
            "planes": {"IP-UP": "module inlet plane: end of the common feed line (after the mixing point and the gas "
                                "isolator); fixed in the thrust-stand frame",
                       "IP-DN": "module outlet plane = H-1 rear inlet flange, immediately upstream of HALL_INLET_Z0; "
                                "everything downstream is H-1 and identical in every configuration",
                       "HALL_INLET_Z0": "anode/gas-distributor plane; the inlet state here is the only allowed physical "
                                        "difference between arms (a result, not a setting)"},
            "occupants": {"PIM-0": "hall_only (HW-0)", "PIM-RF": "rf_hall (HW-RF)", "PIM-ECR": "ecr_hall (HW-ECR)"},
            "control_states": {"M0": "HW-0, hall_only reference", "M0b": "module installed, source unpowered (control "
                               "state; never reported as hall_only)", "M0c": "ECR module installed, microwaves off, ECR "
                               "electromagnet on (only with an electromagnet)"},
            "option": "DIV-1 in-vacuum diverter (package D-06-B) only if the owner selects it (HW-PIM-13); the slot "
                      "leaves space for it.",
        },
        "evidence_classes": list(EVIDENCE_CLASSES),
        "quantity_statuses": {"RFP": "RFP requirement", "SOURCED": "copied from a sourced record",
                              "PROPOSED": "proposed by a lane for owner decision (copied)",
                              "DERIVED": "derived by a committed deterministic script of the source lane (copied)",
                              "ALLOCATION": "A5 allocation (never a prediction)",
                              "TBD": "no value; 'TBD - requires <what>' plus closes_at"},
        "satisfiability_statuses": SATISFIABILITY,
        "hard_rule_not_rf_specific": "Every common item is written occupant-agnostically and carries a satisfiability "
                                     "entry for PIM-RF, PIM-ECR (incl. its magnet and microwave feed) and PIM-0; none is "
                                     "NOT_SATISFIABLE. Anything only one module can meet is an annex item.",
        "common_items": common_items(),
        "annexes": annexes(),
        "confound_table": confound_table(),
        "residual_statuses": RESIDUAL_STATUSES,
        "milestones": {
            "A": {"support": "YES (as a precondition)",
                  "statement": "Conditional selection now: the fixture no longer structurally disadvantages any Phase-1 "
                               "branch. 'Branch X is baseline provided H-1 Phase 1 shows ...' is measurable on one H-1 "
                               "with module exchange as the controlled variable; no branch is selected by this ICD."},
            "B": {"support": "NOT YET",
                  "blocked_by": ["module designs (RF, ECR, PIM-0) and the interface control drawing",
                                 "S1a values: dp_occ per grid flow, B(z) maps M0/M0b/M0c, load-plane calibration, "
                                 "dummy-load pickup",
                                 "S1b values: u_inst, S_B, T-SETTLE", "owner decisions HWQ-01/04/05/06/07/15 and PMQ-*",
                                 "an admitted Hall closure for any absolute performance claim (credible set empty)"]},
            "C": {"support": "NO (inputs only)",
                  "statement": "The flight pre-ionizer ICD (flight mass, thermal, EMC, qualification) is Milestone C "
                               "work; this ground-test ICD supplies its IP-DN datum, gas-path, bus-slot and control-line "
                               "structure."},
            "what_could_overturn": ["the ECR fringe field cannot meet INV-B3 at any practical distance/shielding "
                                    "(ecr_hall then non-comparable on H-1)",
                                    "an RF module that needs an assist magnet or liquid cooling without an owner-defined "
                                    "bus slot",
                                    "S1b u_inst above u_inst,max (module exchange then not a clean controlled variable; "
                                    "D-06-B diverter becomes the fallback)",
                                    "RF and ECR conductances in different pressure-drop classes with no matched PIM-0 "
                                    "insert"],
        },
        "owner_questions": [
            {"id": "PMQ-01", "question": "Approve sizing the common envelope (PMI-01) to the largest occupant (ECR module "
                                         "with magnet/yoke and microwave feed)?"},
            {"id": "PMQ-02", "question": "Approve the common control harness L1-L5 including the MODULE_ID line and the "
                                         "PIM-0 termination rules (PMI-04)?"},
            {"id": "PMQ-03", "question": "Approve the pressure-drop class definition (PMI-10) and, if needed, matched "
                                         "passive PIM-0 inserts per class (DEV-H0-03)?"},
            {"id": "PMQ-04", "question": "Add an S1a no-plasma module-exchange series for PIM-RF and PIM-ECR (unpowered; "
                                         "cold-flow, calibration zero/tare, B(z)) to cover DEV-RF-05 / DEV-ECR-07?"},
            {"id": "PMQ-05", "question": "Adopt a time-matched Xe hold in the HW-0 start sequence equal to the "
                                         "pre-ionizer dwell (DEV-H0-05)?"},
            {"id": "PMQ-06", "question": "Prohibit slotless module loads (RF assist magnet, powered interstage, coolant "
                                         "pump) in v1, or commission a new bus-boundary version before LOCK-1?"},
            {"id": "PMQ-07", "question": "Relay of open hardware questions this ICD depends on: HWQ-01 (configuration-"
                                         "change procedure), HWQ-04 (INV-B3 tolerance), HWQ-05 (ECR magnet type), HWQ-06 "
                                         "(RF magnetization), HWQ-07 (module potential), HWQ-15 (interfaces frozen before "
                                         "Phase 1)."},
        ],
        "consistency_notes": [
            "lane 19 abep_sim/cathode_integration.py PREIONIZER_COMPONENTS['ecr_hall'] = ('ecr_source',) omits ecr_magnet "
            "(already flagged in docs/controls/DUAL_FEED_STATES.md); this ICD follows bus_power_boundary_v1.",
            "abep_sim/thermal_life.py checks ecr_magnet for permanent magnets only (bus allocation must be 0 W); an "
            "electromagnet choice under HWQ-05 needs a thermal check elsewhere.",
            "bus_power_boundary_v1 has no slot for an RF assist magnet or a powered interstage (HW-PIM-05; "
            "INTERSTAGE_MODEL.md section 9 assumes an unpowered, floating interstage).",
            "the lane 25 S1b re-mount series is defined on HW-0 only; module-exchange reproducibility of PIM-RF/PIM-ECR "
            "is not measured by it (PMQ-04).",
        ],
        "compliance": {
            "no_hall_performance_source": "No Hall transport closure, screening candidate or withdrawn 0-D number is "
                                          "used; no performance is predicted.",
            "no_winner": "No architecture is ranked or eliminated; no hard-gate elimination is made here.",
            "nuisance": "P5 calibration nuisance is never a design variable, setting or grid axis.",
            "upstream": "Hall-closure uncertainty does not enter the feed side; IP-UP and everything upstream is "
                        "identical in every configuration.",
            "pure": "Pure data plus one standard-library builder; nothing wired into archengine; no frozen data, goldens "
                    "or existing modules touched.",
            "no_contact": "No supplier, facility or lab contact; published evidence is cited only through the merged "
                          "evidence matrices.",
            "numbers": "Every number is copied with source path, JSON pointer, sha256 and evidence class, or is TBD.",
        },
    }

    common_props = {pid: {"$ref": "#/$defs/conformance_entry"} for pid in COMMON_IDS}
    doc = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:abep:schemas:interfaces:preionizer_module_icd_v1",
        "title": "ABEP H-1 common Pre-Ionizer Module ICD v1",
        "description": "Instance schema: a module-slot occupant declaration (PIM-0 / PIM-RF / PIM-ECR) must give one "
                       "conformance entry for every common interface item PMI-01..PMI-11. The ICD content itself is in "
                       "x-preionizer-module-icd (generated by " + THIS_SCRIPT + ").",
        "type": "object",
        "required": ["icd", "icd_version", "module", "architecture", "conformance"],
        "additionalProperties": False,
        "properties": {
            "icd": {"const": "preionizer_module_icd"},
            "icd_version": {"const": "1.0.0"},
            "module": {"enum": ["PIM-0", "PIM-RF", "PIM-ECR"]},
            "architecture": {"enum": list(ARCHS)},
            "serial": {"type": "string"},
            "conformance": {"type": "object", "required": list(COMMON_IDS), "additionalProperties": False,
                            "properties": common_props},
            "annex_items": {"type": "object", "additionalProperties": {"$ref": "#/$defs/conformance_entry"}},
        },
        "$defs": {
            "evidence_class": {"enum": list(EVIDENCE_CLASSES)},
            "quantity": {
                "type": "object",
                "required": ["name", "value", "unit", "status"],
                "properties": {
                    "name": {"type": "string"}, "unit": {"type": "string"},
                    "status": {"enum": ["RFP", "SOURCED", "PROPOSED", "DERIVED", "ALLOCATION", "TBD"]},
                    "evidence_class": {"$ref": "#/$defs/evidence_class"},
                    "source": {"type": "object", "required": ["path", "pointer", "sha256"]},
                    "tbd_requires": {"type": "string", "pattern": "^TBD - requires "},
                    "closes_at": {"type": "string"},
                },
            },
            "conformance_entry": {
                "type": "object",
                "required": ["status", "evidence"],
                "properties": {
                    "status": {"enum": ["CONFORMS", "CONFORMS_BY_TERMINATION", "NONCONFORMING_RECORDED", "TBD"]},
                    "quantities": {"type": "array", "items": {"$ref": "#/$defs/quantity"}},
                    "evidence": {"type": "string"},
                },
            },
        },
        "x-preionizer-module-icd": content,
    }
    return doc


# ----------------------------------------------------------------------------------------------------------------------
# companion document
# ----------------------------------------------------------------------------------------------------------------------
def _fmt_q(q: dict) -> str:
    if q["status"] == "TBD":
        return f"`{q['name']}` [{q['unit']}]: **TBD** ({q['tbd_requires'][len(TBD) + 1:]}; closes at: {q['closes_at']})"
    v = q["value"]
    return (f"`{q['name']}` = {json.dumps(v)} {q['unit']} ({q['status']}, {q['evidence_class']}; "
            f"`{q['source']['path']}#{q['source']['pointer']}`)")


def render_md(doc: dict) -> str:
    c = doc["x-preionizer-module-icd"]
    L = []
    L.append("# H-1 common Pre-Ionizer Module ICD (`preionizer_module_icd_v1`)")
    L.append("")
    L.append("| item | value |")
    L.append("|---|---|")
    L.append(f"| follow-on / trigger | `{c['follow_on']}` / `{c['trigger']}` (owner addendum A6, lane {c['lane_name_A6']}) |")
    L.append(f"| status | {c['status']} |")
    L.append(f"| machine-readable | `{OUT_JSON}` (JSON Schema for occupant declarations + `x-preionizer-module-icd`) |")
    L.append(f"| builder | `{THIS_SCRIPT}` (`--check` verifies both files) |")
    L.append(f"| test | `{c['test']}` |")
    L.append(f"| base commit | `{c['base_commit']}` |")
    L.append("| A5 | `{}` sha256 `{}` |".format(c["owner_decisions"]["A5"]["path"], c["owner_decisions"]["A5"]["sha256"]))
    L.append("| A6 | `{}` sha256 `{}` |".format(c["owner_decisions"]["A6"]["path"], c["owner_decisions"]["A6"]["sha256"]))
    g = c["g0_baseline"]
    L.append(f"| G0 baseline | `{g['path']}` sha256 `{g['sha256']}`: verdict **{g['verdict']}** at "
             f"`{g['verified_commit']}` (pytest {g['results']['pytest']}; golden {g['results']['golden']}; "
             f"ci_checks {g['results']['integrity']}) |")
    L.append("")
    L.append(c["status_note"])
    L.append("")
    L.append("## Standing facts")
    L.append("")
    for k, v in c["standing_facts"].items():
        L.append(f"* **{k}**: {v}")
    L.append("")
    L.append("Architecture ids: `hall_only`, `rf_hall`, `ecr_hall`. Phase-1 outcomes: A hall_only / B rf_hall / C "
             "ecr_hall / NO_VIABLE_CASE.")
    L.append("")
    L.append("## 1. Module slot and A5 reserved interface")
    L.append("")
    for k, v in c["module_slot"]["planes"].items():
        L.append(f"* **{k}**: {v}")
    L.append("")
    L.append("Occupants: " + "; ".join(f"`{k}` = {v}" for k, v in c["module_slot"]["occupants"].items()) + ".")
    L.append("Control states: " + "; ".join(f"`{k}` = {v}" for k, v in c["module_slot"]["control_states"].items()) + ".")
    L.append("")
    r = c["a5_reserved_interface"]
    L.append(f"A5 reserves the **{r['a5_name']}** ({r['a5_location']}): \"{r['a5_requirement']}\". {r['mapping']}")
    L.append("")
    L.append("## 2. Common interface items (PMI-01 .. PMI-11)")
    L.append("")
    L.append(c["hard_rule_not_rf_specific"])
    L.append("")
    L.append("| id | boundary | PIM-RF | PIM-ECR | PIM-0 |")
    L.append("|---|---|---|---|---|")
    for it in c["common_items"]:
        s = it["satisfiability"]
        L.append(f"| {it['id']} | {it['title']} | {s['PIM-RF']['status']} | {s['PIM-ECR']['status']} | "
                 f"{s['PIM-0']['status']} |")
    L.append("")
    for it in c["common_items"]:
        L.append(f"### {it['id']} {it['title']} (`{it['boundary']}`)")
        L.append("")
        L.append(f"**Definition.** {it['definition']}")
        L.append("")
        L.append(f"**Common requirement.** {it['common_requirement']}")
        L.append("")
        if it.get("bus_components"):
            L.append("**Bus components.** " + "; ".join(f"`{a}`: {', '.join(v) if v else '(none)'}"
                                                         for a, v in it["bus_components"].items()))
            L.append("")
        L.append(f"**Units.** {', '.join(it['units'])}")
        L.append("")
        L.append("**Values.**")
        L.append("")
        for q in it["quantities"]:
            L.append(f"* {_fmt_q(q)}")
        L.append("")
        L.append("**Satisfiability.**")
        L.append("")
        for occ in ("PIM-RF", "PIM-ECR", "PIM-0"):
            L.append(f"* {occ}: {it['satisfiability'][occ]['status']} - {it['satisfiability'][occ]['how']}")
        if it.get("why_common_not_annex"):
            L.append(f"* Why common: {it['why_common_not_annex']}")
        L.append("")
        L.append(f"**Verification.** {it['verification']['method']} ({it['verification']['stage']}). "
                 f"Traces to: {'; '.join(it['traces_to'])}.")
        L.append("")
    L.append("## 3. Annexes")
    L.append("")
    for key in ("ANNEX-RF", "ANNEX-ECR", "ANNEX-HW0"):
        a = c["annexes"][key]
        L.append(f"### {a['id']}: `{a['module']}` ({a['architecture']}), role {a['role']}")
        L.append("")
        if a.get("alternate_not_equal_proposal_baseline"):
            L.append(f"**ALTERNATE - NOT AN EQUAL PROPOSAL BASELINE.** {a['role_statement']}")
            L.append("")
        elif a.get("role_statement"):
            L.append(a["role_statement"])
            L.append("")
        if a.get("role_basis"):
            L.append(f"Role basis: {a['role_basis']}")
            L.append("")
        L.append(f"Scope: {a['scope']}")
        L.append("")
        L.append(f"Uses common items: {', '.join(a['uses_common_items'])}.")
        L.append("")
        L.append("Module-specific items:")
        L.append("")
        for m in a["module_specific_items"]:
            L.append(f"* **{m['id']} {m['title']}.** {m['text']}")
            for q in m["quantities"]:
                L.append(f"  * {_fmt_q(q)}")
        L.append("")
        L.append("| deviation | common items | deviation | confound risk | proposed control |")
        L.append("|---|---|---|---|---|")
        for d in a["deviations"]:
            L.append(f"| {d['id']} | {', '.join(d['common_items'])} | {d['deviation']} | {d['confound_risk']} | "
                     f"{d['proposed_control']} |")
        L.append("")
    L.append("## 4. Confound table (what differs besides the ionization method)")
    L.append("")
    L.append("| id | factor | HW-0 | RF | ECR | mechanism | removed / measured by | items | residual |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for row in c["confound_table"]:
        L.append(f"| {row['id']} | {row['factor']} | {row['hw0']} | {row['rf']} | {row['ecr']} | {row['mechanism']} | "
                 f"{row['removed_or_measured_by']} | {', '.join(row['common_items'])} | {row['residual_status']} |")
    L.append("")
    L.append("## 5. Milestones")
    L.append("")
    m = c["milestones"]
    L.append(f"* **A (conditional selection)**: {m['A']['support']}. {m['A']['statement']}")
    L.append(f"* **B (physics-backed selection)**: {m['B']['support']}. Blocked by: " + "; ".join(m["B"]["blocked_by"]) + ".")
    L.append(f"* **C (proposal/PDR freeze)**: {m['C']['support']}. {m['C']['statement']}")
    L.append("* **What could overturn it**: " + "; ".join(m["what_could_overturn"]) + ".")
    L.append("")
    L.append("## 6. Owner questions")
    L.append("")
    for q in c["owner_questions"]:
        L.append(f"* **{q['id']}** {q['question']}")
    L.append("")
    L.append("## 7. Consistency notes (flagged, not fixed: outside this lane's paths)")
    L.append("")
    for n in c["consistency_notes"]:
        L.append(f"* {n}")
    L.append("")
    L.append("## 8. Compliance")
    L.append("")
    for k, v in c["compliance"].items():
        L.append(f"* **{k}**: {v}")
    L.append("")
    L.append("## 9. Pinned inputs (sha256 at the base commit; mutable governance files are not pinned)")
    L.append("")
    for rel, h in c["pinned_inputs"].items():
        L.append(f"* `{rel}` `{h}`")
    L.append("")
    return "\n".join(L)


def render_json(doc: dict) -> str:
    return json.dumps(doc, indent=1, ensure_ascii=False) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="verify the committed outputs instead of writing them")
    args = ap.parse_args(argv)
    doc = build()
    outputs = {OUT_JSON: render_json(doc), OUT_MD: render_md(doc)}
    if args.check:
        bad = []
        for rel, text in outputs.items():
            p = _abs(rel)
            if not os.path.isfile(p) or open(p, encoding="utf-8").read() != text:
                bad.append(rel)
        if bad:
            print("out of date: " + ", ".join(bad), file=sys.stderr)
            return 1
        print("OK")
        return 0
    for rel, text in outputs.items():
        p = _abs(rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"wrote {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
