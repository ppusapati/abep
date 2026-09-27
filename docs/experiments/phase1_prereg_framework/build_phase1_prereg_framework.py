"""Build the H-1 Phase-1 pre-registration FRAMEWORK (follow-on fo_phase1_prereg_framework, trigger
T_A5_PHASE1_PREREG_FRAMEWORK, owner addendum A6).

Outputs (deterministic; `--check` verifies the committed files byte for byte):
  docs/experiments/phase1_prereg_framework/phase1_prereg_framework_v1.json   (authoritative)
  docs/experiments/phase1_prereg_framework/PHASE1_PREREG_FRAMEWORK.md       (rendered from the JSON)

What this is: the decision TOPOLOGY of the A5 H-1 Phase-1 branch decision (hall_only / rf_hall / ecr_hall /
NO_VIABLE_CASE): the nine decision quantities frozen by A6, their operational definitions and measurement chains, the
gating sequence S1a -> LOCK-1 -> W5 freeze -> S1/S1b -> LOCK-2 -> Phase 1, the test-matrix structure, the order-balanced
execution design, the case logic, the same-condition definition, missing-data and data-quality rules, the
repeatability/remount procedure and the LOCK-1 / LOCK-2 structure.

What this is not: no numeric pass/fail threshold, tolerance or limit is set here. Every such field carries the literal
status UNFROZEN (below) and names the S1/S1b quantity LOCK-2 converts into its numeric value (A6 not_authorized:
'freezing Phase-1 numeric thresholds'). No measurement exists; no outcome is evaluated; no architecture is preferred,
ranked or eliminated. The output JSON contains no numeric leaf at all.

The only computation is combinatorial: the Williams (1949) sequence set for the three configurations and its position /
first-order carryover balance, plus a seeded, deterministic sequence-to-block assignment function (exercised by the test
only with clearly synthetic seeds). Inputs are sha256-pinned; a changed or missing input raises InputChanged. Standard
library only; no simulator import, no Julia.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import re
import string
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]

SCRIPT_REL = "docs/experiments/phase1_prereg_framework/build_phase1_prereg_framework.py"
JSON_REL = "docs/experiments/phase1_prereg_framework/phase1_prereg_framework_v1.json"
MD_REL = "docs/experiments/phase1_prereg_framework/PHASE1_PREREG_FRAMEWORK.md"

#: literal status of every numeric threshold / tolerance / limit field in this framework (owner addendum A6)
UNFROZEN = "UNFROZEN - finalized at LOCK-2 from S1/S1b measured capability"

CONFIGS = ("hall_only", "rf_hall", "ecr_hall")
HW_LABEL = {"hall_only": "HW-0", "rf_hall": "HW-RF", "ecr_hall": "HW-ECR"}
#: the order in which A5 phase1_branch_decision.order_at_every_point NAMES the configurations (never the execution order)
A5_NAMING_ORDER = ("hall_only", "rf_hall", "ecr_hall")

OD_REL = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27.json"
A5_REL = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_architecture.json"
A6_REL = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A6_a5_followon_authorization.json"
G0_REL = "docs/decisions/verification/A5_BASELINE_VERIFICATION.json"
INS_REL = "docs/experiments/instrumentation/instrumentation_definition_v1.json"
MS_REL = "docs/experiments/instrumentation/metrology_spec/metrology_measurement_spec_v1.json"
LOCK1_REL = "docs/architecture_comparison/lock1/lock1_decision_brief_v1.json"
L25_REL = "docs/architecture_comparison/minimum_decisive_experiment/experiment_draft.json"
L06_REL = "docs/architecture_comparison/experiment_protocol/protocol_draft.json"
PKG_REL = "docs/architecture_comparison/experiment_package/experiment_package_v1.json"
W5_REL = "docs/validation/hall_transport_v2_prereg/hall_transport_v2_prereg_DRAFT.json"
S1A_REL = "docs/experiments/s1a_readiness/s1a_readiness_conditions_v1.json"
S1_REL = "docs/experiments/s1_readiness/s1_readiness_conditions_v1.json"
CAP_REL = "docs/experiments/capability_demo/capability_demo_prep_v1.json"
FEED_REL = "docs/architecture_comparison/feed_state_closure/feed_state_closure_v1.json"
HSO_REL = "docs/architecture_comparison/overlays/hall_sustainment/hall_sustainment_envelope_v1.json"
HSM_REL = "docs/evidence/hall_sustainment/hall_sustainment_matrix.json"
B1_REL = "docs/milestones/bundle1/bundle1_v5.json"

#: sha256 pins. Owner decision files and the G0 record are immutable; the deliverables are verified merges pinned at
#: base 302e1c94 (a regenerated deliverable breaks the pin: re-pin, never edit this framework's content silently).
PINNED = {
    OD_REL: "5a5adb8116eecee418992977c239f198a88835c739f357f13a8bddd51778c2ac",
    A5_REL: "0554136751f5ffc7bd7f62c1c4723acce946ef4f523f43687b95710cc8ace621",
    A6_REL: "aaeb7c503c3791f81d4c589e8e25289befa6fcb3b16ce6f962b153715c883180",
    G0_REL: "4bd0fb4312fba97b18bba92ca0726133947ea6d86327f5e1360ea6af2b163523",
    INS_REL: "7c6d37b00f38a44cded73d92d4366739eacbf013e73e98a7bfbc3fa5a5470d96",
    MS_REL: "55c11dc2d22fd92d95b498f72d60f2cdc0c62a45940da2446514049bd5130865",
    LOCK1_REL: "7ce17e1f9101d0832a164e453fd757a813f5e1e77f689cfb661bdc920f453920",
    L25_REL: "54b7b00a60134f2d92f2eb5c9fb49f18d23623a566e04a4b7d70325a0e332509",
    L06_REL: "287dd7ecd57087e46f2f3d786bfb2d64b01ac4fe29a29de21ef98b04c5ac96e3",
    PKG_REL: "9278dfffe43a37a2ea71c3215ce4a7eba022fa72e007ffa24f229371e1407e84",
    W5_REL: "24de36ed89b4455783d4f38becdcb97effbbd37dc28f93d90f54d3c8798a68d2",
    S1A_REL: "011808100ef38799668cb948324efa6492344d3b58ed3c436605ce5caf7025ac",
    S1_REL: "1d3388693191295f4c54ea9d1d38b36ca977193e0d9066aa40aac61776b27fd1",
    CAP_REL: "ba465206f3a9d7773e338e06dc9e98961c3a97d7f89357c2ed3a227f2a924e67",
    FEED_REL: "ff6e15db449151b5cf790088b4641504bd435a48de2d4c6235bf83625d508ef9",
    HSO_REL: "3381c88b81670c37836c04e1ee8dea78898718fa9219df12140f2dbe24f612bb",
    HSM_REL: "76bba594eb1175b2186a8066b38665a2ce5e4cf77487c90f4af2e187a0b82dcc",
    B1_REL: "b61807b10fcc23e989c356b08887d6c56993f4f659900f9595dd0bfc23d822d2",
}

PIN_ROLES = {
    OD_REL: ("owner disposition od_hardware_pivot (original)", "owner", "immutable owner decision"),
    A5_REL: ("owner addendum A5: proposal reference architecture / Phase-1 baseline (branch logic, test matrix, cases)",
             "owner", "immutable owner decision"),
    A6_REL: ("owner addendum A6: authorization of this framework, decision-quantity list, execution-order clarification",
             "owner", "immutable owner decision"),
    G0_REL: ("G0 governance baseline record (verdict CLEAN; downstream artifacts may pin A5)", "G0 lane (owner addendum A6)",
             "immutable verification record"),
    INS_REL: ("W4 instrumentation definition v1-r2 (INS-01..INS-24, INS-P-*, DQ-*, VO-*)", "fo_instrumentation_definition",
              "verified deliverable (DRAFT_PENDING_OWNER)"),
    MS_REL: ("W4 metrology measurement specification (MS-G-*, MS-M-*)", "fo_capability_demo_prep",
             "verified deliverable (DRAFT_PENDING_OWNER)"),
    LOCK1_REL: ("W2 LOCK-1 decision brief (D-01..D-15, P-01..P-04, phases, absolute gate, S1-01..S1-12 -> LOCK-2)",
                "fo_lock1_decision_brief", "verified deliverable (DRAFT_PENDING_OWNER_SIGNATURE)"),
    L25_REL: ("lane-25 minimum decisive experiment (stages S1..S6, OP1..OP5, S1b re-mount series, run matrix)",
              "lane_25_min_decisive_experiment", "verified deliverable (DRAFT)"),
    L06_REL: ("lane-06 common-condition protocol (INV-*, M1..M6, stability S1..S6, THR-EXTINCTION, run statuses)",
              "lane_06_experiment_protocol", "verified deliverable (DRAFT_PENDING_OWNER)"),
    PKG_REL: ("experiment package (D-01..D-15 options, lane-25/lane-06 reconciliation D-10)", "fo_experiment_package",
              "verified deliverable (DRAFT)"),
    W5_REL: ("W5 held-out Hall-transport validation pre-registration DRAFT (families F1..F7, VO-*, REG-*, K0..K6)",
             "fo_hall_validation_prereg_draft", "verified deliverable (DRAFT_PENDING_OWNER)"),
    S1A_REL: ("S1a engineering-readiness gate conditions (S1A-C1..C5, S1A-FW)", "fo_s1a_engineering_gate",
              "verified deliverable (DRAFT)"),
    S1_REL: ("S1-readiness gate conditions N4 (S1-C1..S1-C8)", "fo_s1_readiness_gate", "verified deliverable (DRAFT)"),
    CAP_REL: ("W4 capability-demonstration preparation (CD-01..CD-07, S1A-P-*)", "fo_capability_demo_prep",
              "verified deliverable (DRAFT_PENDING_OWNER)"),
    FEED_REL: ("W1 feed-state closure (valve-outlet test points, IF-A5 feed record)", "fo_feed_state_closure",
               "verified deliverable (DRAFT)"),
    HSO_REL: ("Hall sustainment envelope overlay (H_RAM delivered-flow bound, SC-REC O2 fraction, F-9)",
              "fo_hall_sustainment_envelope", "verified deliverable (DRAFT)"),
    HSM_REL: ("Hall sustainment evidence matrix (A5 evidence_basis)", "lane_09_hall_sustainment",
              "verified deliverable (evidence audit)"),
    B1_REL: ("Bundle 1 v5 (outcome NO_BASELINE_YET)", "fo_bundle1_conditional_selection",
             "verified deliverable (DRAFT_FOR_OWNER_REVIEW)"),
}

#: mutable governance files: referenced by name only, never pinned (task rule; OPERATING_MODEL)
GOVERNANCE_NEVER_PINNED = (
    "docs/orchestration/lane_registry_v1.json",
    "docs/orchestration/trigger_registry_v1.json",
    "docs/orchestration/fired_triggers.jsonl",
    "docs/orchestration/trigger_ledger_v2.jsonl",
    "docs/orchestration/runtime_state.json",
)

#: produced in parallel by fo_preionizer_module_icd (owner addendum A6); referenced by path only, never pinned
PREIONIZER_ICD_PATH = "docs/interfaces/preionizer_module/"

#: bus_power_boundary_v1 component ids as named in abep_sim/arch_boundary.py (referenced by name; the test cross-checks)
BUS_COMMON = ("hall_discharge", "hall_magnet", "cathode_keeper", "cathode_heater", "flow_control", "compressor",
              "thermal_control", "housekeeping")
BUS_PREION = {"hall_only": (), "rf_hall": ("rf_source",), "ecr_hall": ("ecr_source", "ecr_magnet")}


class InputChanged(RuntimeError):
    """A pinned input is missing or its sha256 differs from the pin."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_inputs() -> dict:
    """Check every pinned input against its sha256; raise InputChanged on a missing or changed file."""
    out = {}
    for rel, want in PINNED.items():
        p = ROOT / rel
        if not p.is_file():
            raise InputChanged(f"pinned input missing: {rel}")
        got = _sha256(p)
        if got != want:
            raise InputChanged(f"pinned input changed: {rel} sha256 {got} != pinned {want}")
        out[rel] = got
    for rel in GOVERNANCE_NEVER_PINNED:
        if rel in PINNED:
            raise RuntimeError(f"mutable governance file must never be pinned: {rel}")
    return out


def _load(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


# ------------------------------------------------------------------------------------------ order-balanced design
def williams_sequences(treatments: tuple) -> list:
    """Williams (1949) sequence set balanced for first-order residual (carryover) effects.

    Standard construction: first row 0, 1, t-1, 2, t-2, ...; row r adds r (mod t); for an odd number of treatments the
    mirror-image square is appended (Williams 1949: n replications for even n, 2n for odd n)."""
    t = len(treatments)
    if t < 2 or len(set(treatments)) != t:
        raise ValueError("need at least two distinct treatments")
    first, lo, hi, take_lo = [0], 1, t - 1, True
    while len(first) < t:
        if take_lo:
            first.append(lo)
            lo += 1
        else:
            first.append(hi)
            hi -= 1
        take_lo = not take_lo
    square = [[(x + r) % t for x in first] for r in range(t)]
    rows = square + ([list(reversed(row)) for row in square] if t % 2 == 1 else [])
    return [tuple(treatments[i] for i in row) for row in rows]


def position_counts(seqs: list) -> dict:
    counts = {}
    for s in seqs:
        for pos, trt in enumerate(s):
            counts[(pos, trt)] = counts.get((pos, trt), 0) + 1
    return counts


def carryover_counts(seqs: list) -> dict:
    counts = {}
    for s in seqs:
        for a, b in zip(s, s[1:]):
            counts[(a, b)] = counts.get((a, b), 0) + 1
    return counts


def is_position_balanced(seqs: list, treatments: tuple) -> bool:
    c = position_counts(seqs)
    vals = [c.get((p, t), 0) for p in range(len(treatments)) for t in treatments]
    return len(set(vals)) == 1 and vals[0] > 0


def is_carryover_balanced(seqs: list, treatments: tuple) -> bool:
    c = carryover_counts(seqs)
    vals = [c.get((a, b), 0) for a in treatments for b in treatments if a != b]
    return len(set(vals)) == 1 and vals[0] > 0 and all(c.get((a, a), 0) == 0 for a in treatments)


SEQUENCES = williams_sequences(CONFIGS)


def _uniform_below(seed_hex: str, counter: int, bound: int) -> int:
    """Unbiased integer in [0, bound) from sha256(seed || counter || attempt) by rejection sampling."""
    if bound <= 0:
        raise ValueError("bound must be positive")
    limit = (1 << 256) - ((1 << 256) % bound)
    attempt = 0
    while True:
        h = hashlib.sha256(f"{seed_hex}:{counter}:{attempt}".encode("ascii")).digest()
        v = int.from_bytes(h, "big")
        if v < limit:
            return v % bound
        attempt += 1


def assign_sequences(n_blocks: int, seed_hex: str) -> list:
    """Seeded, deterministic assignment of the Williams sequences to blocks (Fisher-Yates on complete replicates).

    Raises (no silent fallback) unless n_blocks is a positive multiple of the sequence-set size: an incomplete design
    needs an owner-registered selection rule (reconciliation item R-03). The seed is drawn and recorded at LOCK-2."""
    if isinstance(n_blocks, bool) or not isinstance(n_blocks, int) or n_blocks <= 0:
        raise ValueError("n_blocks must be a positive integer (fixed at LOCK-2)")
    if n_blocks % len(SEQUENCES):
        raise ValueError("n_blocks is not a multiple of the Williams sequence-set size: complete first-order carryover "
                         "balance is impossible; an incomplete design needs an owner-registered rule (R-03)")
    if not isinstance(seed_hex, str) or not seed_hex or any(c not in string.hexdigits for c in seed_hex):
        raise ValueError("seed_hex must be a non-empty hexadecimal string recorded at LOCK-2")
    pool = list(SEQUENCES) * (n_blocks // len(SEQUENCES))
    for i in range(len(pool) - 1, 0, -1):
        j = _uniform_below(seed_hex.lower(), i, i + 1)
        pool[i], pool[j] = pool[j], pool[i]
    return pool


# ---------------------------------------------------------------------------------------------------- content
def _a6_decision_quantity_names(a6: dict) -> list:
    text = a6["authorized_now"]["fo_phase1_prereg_framework"]
    m = re.search(r"the list of decision quantities \(([^)]*)\)", text)
    if not m:
        raise InputChanged("A6 authorized_now.fo_phase1_prereg_framework no longer lists the decision quantities")
    return [s.strip() for s in m.group(1).split(";")]


def _dq(key, name, a6_name, definition, per_config, chain, units, uncertainty, depends, lock1_fixes, refs, roles):
    return {
        "id": f"P1DQ-{key}",
        "name": name,
        "a6_name": a6_name,
        "frozen_by": "owner addendum A6 (authorized_now.fo_phase1_prereg_framework): the decision-quantity list",
        "operational_definition": definition,
        "per_configuration": per_config,
        "measurement_chain": [{"ins_id": i, "role": r, "quantity": q} for i, r, q in chain],
        "units": units,
        "uncertainty_sources": uncertainty,
        "threshold": UNFROZEN,
        "threshold_depends_on": [{"stage": s, "quantity": q, "source": src} for s, q, src in depends],
        "fixed_at_lock1": lock1_fixes,
        "existing_rule_references": refs,
        "a5_role": roles,
    }


def decision_quantities(names: list) -> list:
    n = dict(zip(("SUST", "TPBUS", "ETAU", "ENVW", "IGN", "STAB", "TABS", "PBUS", "NOXE"), names))
    all3 = "measured for hall_only, rf_hall and ecr_hall at the same conditions"
    return [
        _dq("SUST", "sustainment", n["SUST"],
            "Per reading: SUSTAINED iff the discharge runs for the whole pre-registered dwell at the condition with no "
            "uncommanded extinction and no automatic restart. Uncommanded extinction is decided by the THR-EXTINCTION "
            "rule form (lane-06 protocol_draft.json sustainment_and_extinction.extinction; same functional form as the "
            "P5-N2 simulation rule O1) applied to the I_d(t) record; a low but steady discharge is sustained and a "
            "single deep breathing trough is not an extinction. Per condition and configuration over the blocks: "
            "SUSTAINED if every block's reading is sustained, NOT_SUSTAINED if none is, SUSTAINMENT_MIXED otherwise "
            "(lane 25 Sec. 9). Per condition and configuration pair (X vs hall_only): ENABLES / DISABLES / "
            "NEITHER_SUSTAINED (lane 25 Sec. 9). A reading that stays lit only with Xe added to the discharge feed is "
            "XE_DEPENDENT (P1DQ-NOXE), never SUSTAINED on atmospheric propellant. Flow scans are run down then up; a "
            "level counts as sustained for the envelope only if sustained in both directions (LOCK-1 brief phase_1).",
            all3,
            [("INS-04", "DECISIVE", "I_d mean and I_d(t), V_d"),
             ("INS-10", "DECISIVE", "per-dwell extinction flag, restarts"),
             ("INS-18", "CONDITION", "common time base of I_d, flow and valve-state channels"),
             ("INS-05", "CONDITION", "anode / pre-ionizer / cathode flow per species"),
             ("INS-08", "CONDITION", "background pressure p_b"),
             ("INS-17", "CONDITION", "thermal settling before the dwell")],
            "class (SUSTAINED / NOT_SUSTAINED / SUSTAINMENT_MIXED; pair classes ENABLES / DISABLES / NEITHER_SUSTAINED); "
            "I_d in A; dwell in s",
            ["I_d offset and noise floor inside the extinction window (INS-04; instrumentation I-U-ID-FLOOR, PROPOSED)",
             "extinction-window length and sampling (ext_window TBD from the S1b oscillation band)",
             "flow-setpoint uncertainty at low flow (INS-05; relative uncertainty grows at a small fraction of full "
             "scale)", "background pressure at the reading (INS-08)", "hysteresis / approach direction"],
            [("S1b", "I_d oscillation band on HW-0 (sets ext_window and the discharge sampling rate)", "LOCK-1 brief S1-09"),
             ("S1b", "thermal time constants (sets the dwell / T-SUSTAIN hold time)", "LOCK-1 brief S1-08"),
             ("S1a", "I_d channel noise floor", "capability demo CD-03 (S1A-P-PC-02 NOISE)"),
             ("S1a", "MFC resolution in the final configuration (sets min_flow_step)", "LOCK-1 brief S1-05")],
            ["THR-EXTINCTION rule form and its parameter names", "per-condition aggregation T-SUSTAIN",
             "both-directions rule for flow scans (P-01)", "XE_DEPENDENT precedence over SUSTAINED"],
            ["instrumentation DQ-SUST, DQ-KNEE", "lane-06 THR-EXTINCTION", "lane-25 Sec. 9 per-condition classes",
             "W5 VO-IGNEXT (held out for hall_only N2 families F1/F2)"],
            "A5 discriminator 'sustainment'; Case A requirement; Case B/C 'restores operation' test"),
        _dq("TPBUS", "T/P_bus", n["TPBUS"],
            "Thrust per bus power at a reading: T / P_bus, with T the axial thrust from the thrust stand and P_bus the sum "
            "over every bus_power_boundary_v1 component of the configuration of load-plane power divided by its "
            "pre-registered ledger efficiency (contract basis, D-10-A; abep_sim/arch_boundary.py bus_power_ledger, "
            "referenced by name). Two labelled bases: PARTIAL_BOUNDARY (compressor ABSENT_IN_LAB) and V1 (compressor "
            "draw reconstructed from the upstream ICD, D-11). The discriminator is the paired ratio R_arch = "
            "(T/P_bus)_X / (T/P_bus)_hall_only for X in {rf_hall, ecr_hall}, at the same condition and in the same "
            "block, analysed as ln R_arch (lane 25 Sec. 6). Source power is never assessed separately: it enters only "
            "through P_bus (A5 discriminator_note). R_arch is undefined where either configuration is not sustained "
            "(then the P1DQ-SUST pair class applies).",
            all3,
            [("INS-01", "DECISIVE", "thrust T"),
             ("INS-02", "DECISIVE", "load-plane DC power of every bus_power_boundary_v1 component present in the lab"),
             ("INS-03", "SUPPORTING", "net RF / microwave power at the source load plane (never substitutes the DC input)"),
             ("INS-17", "CONDITION", "stand and thruster temperatures (drift)"),
             ("INS-18", "CONDITION", "simultaneous sampling of T and P channels")],
            "T/P_bus in mN/kW; R_arch dimensionless (analysed as ln R_arch)",
            ["per-reading thrust repeatability u_T (Type A)", "per-reading power repeatability u_P (Type A)",
             "installation reproducibility u_inst (module exchange, lane-25 G5)",
             "source load-plane uncertainty u_src (lane-25 G3)", "common-consumer meter scale (lane-25 G4)",
             "ledger efficiencies (LOCK-1 inputs with T-LEDGER-SENSITIVITY bounds)",
             "compressor draw reconstruction (PARTIAL_BOUNDARY vs V1)", "facility p_b sensitivity (S5)"],
            [("S1b", "u_T and u_P from the within-cycle readings of the re-mount series", "LOCK-1 brief S1-07"),
             ("S1b", "u_inst from the K re-installation cycle means", "LOCK-1 brief S1-07"),
             ("S1a", "power-channel scale per common consumer", "LOCK-1 brief S1-02"),
             ("S1a", "RF / microwave load-plane characterisation (u_src)", "LOCK-1 brief S1-03"),
             ("S1b", "block count n from readiness_n", "LOCK-1 brief s1_to_lock2 d0 (T-READINESS)")],
            ["interval form on ln R_arch (Welch-Satterthwaite / Student-t, lane 25 Sec. 6)",
             "stop-rule form (D-02) and the multiplicity family", "bases PARTIAL_BOUNDARY / V1 and their labels",
             "ledger efficiencies and unmeasured-load bounds (D-11)"],
            ["instrumentation DQ-RARCH", "lane-06 M1", "lane-25 Sec. 6 and 9", "LOCK-1 brief phases.phase_2"],
            "A5 discriminator 'T/P_bus'; the net system-level benefit test of Cases B and C"),
        _dq("ETAU", "eta_u", n["ETAU"],
            "Propellant (mass) utilization per lane-06 metric M3: eta_m,tot = sum_j (m_j / (q_j e)) I_b,j / m_dot_tot "
            "with I_b,j = I_b x Omega_j (E x B current fraction of species j, charge state q_j, mass m_j from standard "
            "atomic weights) and m_dot_tot = m_dot_prop + m_dot_c (cathode Xe included in the denominator); "
            "eta_m,prop over m_dot_prop reported alongside. Per configuration at every condition where it is "
            "sustained; the paired utilization gain of X over hall_only (break-even lane X-gain) is reported with it.",
            all3 + " (where sustained)",
            [("INS-15", "DECISIVE", "far-field Faraday beam current I_b and divergence"),
             ("INS-13", "DECISIVE", "species / charge-state current fractions Omega_j, q_j"),
             ("INS-05", "DECISIVE", "m_dot_prop (anode and pre-ionizer lines) and m_dot_c"),
             ("INS-14", "SUPPORTING", "ion energy distribution (separates voltage from mass utilization)"),
             ("INS-08", "CONDITION", "p_b for the charge-exchange correction")],
            "dimensionless",
            ["Faraday-probe corrections (secondary electrons, charge exchange, gap, alignment; instrumentation INS-15)",
             "E x B species resolution for low-energy air ions (instrumentation INS-13: AT_RISK)",
             "charge-exchange correction driven by the background-density uncertainty (INS-08 / INS-13 notes)",
             "flow uncertainty of every line (INS-05)"],
            [("S1a", "Faraday probe area, bias sweep and collector zero (INS-15 calibration)", "instrumentation INS-15"),
             ("S1a", "MFC calibration on each working gas", "LOCK-1 brief S1-05"),
             ("S1b", "repeatability of I_b and Omega_j at the S1b point: NOT in the lane-25 S1b plan (M1, M2, M3, "
                     "M9, M10, M11 only); without it eta_u has no statistical boundary (reconciliation item R-05)",
              "lane-25 s1_plan; this framework R-05")],
            ["the M3 definition and the denominator convention (m_dot_tot with cathode Xe)",
             "the species set j and the E x B analysis method (same code for all configurations)",
             "whether eta_u carries a statistical boundary (needs R-05) or is reported descriptively"],
            ["lane-06 M3", "break-even lane X-gain (docs/architecture_comparison/breakeven/)",
             "Bundle 1 mandatory field eta_u"],
            "A5 discriminator 'eta_u'; Case A 'utilization criteria'"),
        _dq("ENVW", "operating-envelope width", n["ENVW"],
            "For each configuration, the set of tested (m_dot_atm, x_O2, V_d) grid conditions at which it is SUSTAINED "
            "(P1DQ-SUST), stable (P1DQ-STAB) and XE_FREE (P1DQ-NOXE). Two summaries: (a) per (x_O2, V_d) slice, the "
            "bracketed low-flow knee = [lowest level sustained in both scan directions, next lower level], both ends "
            "measured, never an interpolated flow (LOCK-1 brief phase_1 bracket; P-01); (b) coverage of the required "
            "envelope = which grid conditions of the required low-flow / composition envelope (fixed at LOCK-1 from the "
            "W1 / DI-1 delivered-feed region) lie inside the set. Width is stated on the tested grid only; nothing is "
            "extrapolated outside the tested flow range (LOCK-1 brief P1-S4).",
            all3,
            [("INS-05", "DECISIVE", "anode flow and composition from two pure-gas MFCs"),
             ("INS-04", "DECISIVE", "V_d at the terminals; I_d(t) through P1DQ-SUST"),
             ("INS-10", "DECISIVE", "sustainment / extinction flag per level and direction"),
             ("INS-06", "CONDITION", "feed pressure at the IF-A5 plane"),
             ("INS-07", "CONDITION", "feed temperature at the IF-A5 plane")],
            "set of grid conditions; knee-bracket ends in mg/s; x_O2 as mass fraction; V_d in V",
            ["flow-step resolution (min_flow_step)", "MFC uncertainty at a low fraction of full scale",
             "composition uncertainty of the two-MFC surrogate (instrumentation derived.mixture_mass_fraction_u)",
             "hysteresis between scan directions", "background pressure"],
            [("S1a", "MFC resolution and zero drift in the final configuration (min_flow_step)",
              "LOCK-1 brief S1-05; capability demo CD-04"),
             ("S1b", "sustainment noise quantities as for P1DQ-SUST (ext_window, dwell)", "LOCK-1 brief S1-08, S1-09")],
            ["grid levels and the required-envelope subset (from W1 / DI-1; TBD)", "bracket-refinement rule (P-01)",
             "direction rule and HYSTERETIC reporting"],
            ["instrumentation DQ-KNEE", "lane-06 M6 (minimum sustained flow)", "LOCK-1 brief P-01, P1-S1..P1-S5"],
            "A5 discriminator 'operating-envelope width'; Case A 'across the required low-flow/composition envelope'"),
        _dq("IGN", "ignition/restart behaviour", n["IGN"],
            "Per attempt under the pre-registered start sequence along the A5 operating modes (OFF -> Xe "
            "ignition/startup -> brief transition support -> atmospheric Hall + Xe cathode): IGNITED iff I_d reaches the "
            "steady window within the ignition timeout and stays sustained for the hold time (lane-06 "
            "sustainment_and_extinction.ignition); TRANSITIONED iff, after the transition window, the discharge-feed Xe "
            "is zero (P1DQ-NOXE) and the discharge stays SUSTAINED on atmospheric propellant; RESTARTED iff a re-start "
            "after a commanded shutdown, or after an uncommanded extinction, meets the same criteria. Recorded per "
            "attempt: outcome, time to the steady window, Xe consumed in startup and in transition (inputs to the "
            "symbolic m_startup and m_transition terms of fo_xe_system_ledger), and air-only start attempts if D-13 "
            "includes them. Aggregated per configuration and propellant as successes / attempts with a one-sided "
            "Clopper-Pearson bound form (lane-06 M5).",
            all3,
            [("INS-10", "DECISIVE", "ignition success within timeout, restarts"),
             ("INS-04", "DECISIVE", "I_d(t) during start and transition"),
             ("INS-05", "DECISIVE", "Xe startup / transition flows and their durations; cathode Xe flow"),
             ("INS-02", "CONDITION", "heater, keeper and discharge power during the start sequence"),
             ("INS-23", "CONDITION", "C-1 cathode-tube temperature at start"),
             ("INS-18", "CONDITION", "time stamps of valve states and I_d")],
            "successes / attempts (count); time in s; Xe consumed in mg",
            ["binomial sampling (number of attempts)", "timing resolution of the start record (INS-18)",
             "integration uncertainty of transient Xe flow (INS-05)"],
            [("S1b", "start sequences on HW-0 (sets ignition_timeout and the steady-window definition)",
              "LOCK-1 brief S1-12"),
             ("S1b", "I_d oscillation band (steady-window detection)", "LOCK-1 brief S1-09")],
            ["start-sequence definition per configuration (identical cathode steps)", "attempt count and the owner's "
             "minimum reliability as rule inputs (lane-06 THR-M5 parameters; D-13; owner start-cycle budget)",
             "restart cases to be attempted"],
            ["lane-06 M5 and sustainment_and_extinction.ignition", "LOCK-1 brief D-13", "instrumentation INS-P-08 start log",
             "W5 VO-IGNEXT (ignition recorded only; not modelled)"],
            "A5 minimum measurement 'ignition/restart behaviour'; case constraint for every branch"),
        _dq("STAB", "stability/oscillation", n["STAB"],
            "Lane-06 stability metrics over the steady window in the pre-registered band: S1 = sigma(I_d) / mean(I_d); "
            "S2 = peak-to-peak(I_d) / mean(I_d); S3 = dominant frequency of the I_d power spectral density; S4 = thrust "
            "noise after drift correction; S5 = reflected / forward power ratio mean and spread (source configurations, "
            "diagnostic); S6 = uncommanded extinctions and mode transitions per hour. Per condition: an oscillation "
            "class from one threshold applied identically to every configuration (W5 C-OSC form), and the paired "
            "non-inferiority of S1 against hall_only (lane-06 THR-M4 form).",
            all3,
            [("INS-04", "DECISIVE", "wide-band I_d(t)"),
             ("INS-01", "DECISIVE", "thrust signal for S4"),
             ("INS-10", "DECISIVE", "extinctions and mode transitions for S6"),
             ("INS-03", "SUPPORTING", "forward / reflected power for S5"),
             ("INS-18", "CONDITION", "sampling and time base")],
            "fraction (S1, S2); Hz (S3); mN (S4); ratio (S5); count per hour (S6)",
            ["acquisition bandwidth and sampling (set from the measured spectrum, not assumed; INS-04)",
             "I_d noise floor", "window length", "thrust-stand dynamic response and drift correction"],
            [("S1b", "HW-0 I_d spectrum at the S1b point (band, sampling rate)", "LOCK-1 brief S1-09"),
             ("S1b", "thrust noise within the re-mount readings", "LOCK-1 brief S1-07"),
             ("S1a", "DAQ channel performance (skew, gain / phase of fast chains)", "capability demo CD-06"),
             ("S1a", "RF / microwave pickup bound on common diagnostics", "LOCK-1 brief S1-04")],
            ["metric definitions S1..S6 and the band", "class form (one threshold for measured data, applied "
             "identically to all configurations)", "non-inferiority form (THR-M4)"],
            ["lane-06 stability_metrics S1..S6, M4", "W5 C-OSC (non-gating for validation)"],
            "A5 minimum measurement 'oscillation/stability'; Case A 'stability criteria'; common constraint"),
        _dq("TABS", "absolute thrust compatibility", n["TABS"],
            "Sustained thrust per configuration at the delivered-feed test points (W1 / DI-1 points reproduced with MFCs), "
            "decided against the RFP thrust envelope as a requirement (abep_sim/constants.py RFPConstraints.thrust_min_mN "
            "and thrust_max_mN, RFP DTDF/06/13516/DSP/ABEP/X/L/M/01 Part III Para 2 as transcribed; verify) on one-sided "
            "confidence bounds T_LB / T_UB of the LOCK-1 brief absolute_thrust_gate form, never on point estimates; the "
            "upper (capability) condition of the envelope follows the owner's P-04 reading. Reported alongside, never merged into, R_arch. Qualifiers "
            "COMPOSITION_SURROGATE (no atomic O), FACILITY_UNCHECKED where S5 did not run, and the flow rule "
            "I-FLOW-CONSERVATIVE (delivered flow not above the registered point). Xe-augmented peak points (P-04-ii with "
            "D-15-C), if the owner adopts them, are a time-limited non-nominal mode recorded as XE_AUGMENTED_PEAK: reported "
            "separately, drawn on the single Xe allocation, and never used for a nominal classification or for Case A "
            "(P1DQ-NOXE; R-14). The A5 thrust operating target is an allocation and is not a Phase-1 pass criterion.",
            all3,
            [("INS-01", "DECISIVE", "absolute, calibration-traceable thrust"),
             ("INS-05", "CONDITION", "delivered anode flow against the registered point (I-FLOW-CONSERVATIVE)"),
             ("INS-08", "CONDITION", "p_b and the S5 p_b slope"),
             ("INS-10", "CONDITION", "every visit SUSTAINED"),
             ("INS-17", "CONDITION", "stand temperatures and zero drift over the dwell")],
            "mN",
            ["Type B thrust-stand scale u_Tscale from in-situ calibration", "Type A over the visits",
             "zero drift over the dwell (bounded by pre- and post-dwell zeros)", "delivered-flow uncertainty",
             "facility p_b sensitivity"],
            [("S1a", "in-situ thrust-stand calibrations (u_Tscale)", "LOCK-1 brief S1-01"),
             ("S1b", "per-reading thrust repeatability u_T", "LOCK-1 brief S1-07"),
             ("S1b", "D0-ABS record (predicted u_c(T) against the P-02 requirement)", "LOCK-1 brief S1-11"),
             ("S1b", "thermal time constants and dwell", "LOCK-1 brief S1-08"),
             ("S1b", "p_b at the S1b point and cold-flow p_b", "LOCK-1 brief S1-10")],
            ["bound form and coverage-factor rule (P-02)", "the owner's reading of the RFP upper-thrust condition (P-04)",
             "qualifier set", "facility treatment (smaller of base and elevated p_b lower bounds)"],
            ["instrumentation DQ-TABS, I-ALPHA-ABS, I-U-ABS-T, I-FLOW-CONSERVATIVE (all PROPOSED)",
             "LOCK-1 brief absolute_thrust_gate, P-02, P-04", "lane-24 G1 criteria (hard_gate_matrix_v1.json)"],
            "A5 NO_VIABLE_CASE common 'thrust' constraint; applies to every branch"),
        _dq("PBUS", "full bus-power compatibility", n["PBUS"],
            "P_bus of the configuration at the same readings as P1DQ-TABS, summed over EVERY bus_power_boundary_v1 "
            "component of that configuration (common: " + ", ".join(BUS_COMMON) + "; rf_hall adds rf_source; ecr_hall "
            "adds ecr_source and ecr_magnet), load-plane power divided by the pre-registered ledger efficiency. 'Full' "
            "means the V1 basis: the compressor row is ABSENT_IN_LAB and its draw is reconstructed from the upstream "
            "ICD; a lab-subset result is PARTIAL_BOUNDARY and is a necessary condition only. Decided on the upper "
            "bound P_UB against the RFP power requirement (abep_sim/constants.py RFPConstraints.power_max_W; verify) and "
            "reported against the A5 bus-power design allocation (A5 allocations_and_requirements; an allocation, not a "
            "Phase-1 pass criterion unless the owner decides so at LOCK-1).",
            all3,
            [("INS-02", "DECISIVE", "one DC channel per bus_power_boundary_v1 component present in the lab"),
             ("INS-03", "SUPPORTING", "source load-plane power (efficiency evidence only)"),
             ("INS-18", "CONDITION", "simultaneous sampling of all channels")],
            "W",
            ["channel calibration scale", "ledger efficiency bounds", "compressor draw reconstruction from the ICD",
             "Type A over the visits"],
            [("S1a", "power-channel calibration per component", "LOCK-1 brief S1-02"),
             ("S1a", "DUMMY_LOAD_PICKUP bound on DC channels", "LOCK-1 brief S1-04"),
             ("S1b", "per-reading power repeatability u_P", "LOCK-1 brief S1-07")],
            ["bound form (P_UB, P-02)", "ledger efficiencies and their evidence class (D-10-A, D-11)",
             "PARTIAL_BOUNDARY / V1 labelling"],
            ["instrumentation DQ-PBUS, I-U-ABS-P (PROPOSED)", "lane-06 bus_power_boundary.laboratory_subset",
             "lane-24 G2.bus_power_max"],
            "A5 NO_VIABLE_CASE common 'bus-power' constraint; the P_bus basis of the Case B/C net benefit"),
        _dq("NOXE", "no continuous Xe augmentation", n["NOXE"],
            "At every reading used for a nominal-mode decision, the Xe flow into the discharge (anode / distributor line "
            "and any pre-ionizer line) is zero - its valve closed with the state logged and its MFC reading inside the "
            "zero band of that controller - for the whole dwell, and the discharge is SUSTAINED. The only Xe flow is the "
            "C-1 cathode feed at its pre-registered setpoint (A5 xe_mass_allocation.cathode_flow_design_target_mg_s), "
            "identical in every configuration (same-condition variable SC-CATH-FLOW) and never raised to support the "
            "discharge. Xe in the discharge is permitted only in the Xe ignition/startup and brief transition modes, "
            "within a pre-registered maximum transition duration (A5 rule: every Xe-consuming mode carries an explicit "
            "maximum duration). A condition that stays lit only with discharge-feed Xe beyond that window, or only with "
            "a raised cathode Xe flow, is XE_DEPENDENT. Deliberate Xe-augmented peak or contingency readings (P-04-ii / "
            "D-15-C, A5 time-limited Xe contingency) carry the separate label XE_AUGMENTED_PEAK and never enter a "
            "nominal-mode classification (R-14).",
            all3,
            [("INS-05", "DECISIVE", "Xe anode / pre-ionizer line flow with valve state; cathode Xe flow"),
             ("INS-04", "DECISIVE", "I_d(t) after the Xe cut-off"),
             ("INS-10", "DECISIVE", "sustainment after the cut-off"),
             ("INS-18", "CONDITION", "alignment of valve-state and I_d time stamps")],
            "class (XE_FREE / XE_DEPENDENT); Xe flows in mg/s; transition duration in s",
            ["MFC zero offset and zero drift with the valve closed", "valve seat leakage (TBD - requires the valve "
             "specification, W3)", "time alignment of valve state and discharge record"],
            [("S1a", "Xe MFC zero drift with the valve closed (sets the zero band)",
              "capability demo CD-04 (S1A-P-MFC-02 DRIFT)"),
             ("S1b", "start / transition sequences (sets the maximum transition window)", "LOCK-1 brief S1-12")],
            ["the XE_FREE / XE_DEPENDENT rule itself (frozen topology)", "cathode-flow setpoint as a same-condition "
             "variable", "whether the transition window is a requirement input (A5 operating_modes.rules)"],
            ["A5 decision_statement and operating_modes.rules", "A6 fo_xe_system_ledger (m_transition, m_fallback "
             "symbolic)", "instrumentation INS-P-08 C-1 logs"],
            "A5 necessary condition for Case A; also required of rf_hall / ecr_hall for Cases B / C"),
    ]


def gating_sequence() -> list:
    return [
        {"order": "first", "step": "S1a",
         "what": "non-score-bearing engineering qualification; never a Hall-on H-1 reading; may begin before LOCK-1 (A3)",
         "contributes_to_thresholds": ["Type B calibration uncertainties: thrust-stand in-situ calibration (INS-01), "
                                       "power channels (INS-02), RF / microwave load plane (INS-03), MFCs on each gas "
                                       "incl. zero drift (INS-05), gauges (INS-06..INS-08)",
                                       "instrument noise floors and the DUMMY_LOAD_PICKUP bound",
                                       "no-plasma installation / re-installation reproducibility (CD-02a)",
                                       "B(z) per configuration at actual coil currents (REG-BZ, custody-held)",
                                       "DAQ channel performance (CD-06)"],
         "gate": "S1A_READY from scripts/experiments/s1a_readiness.py (S1A-C1..S1A-C5 and the firewall S1A-FW)",
         "deliverables": ["docs/experiments/s1a_readiness/", "docs/experiments/capability_demo/",
                          "docs/experiments/instrumentation/"],
         "score_bearing": False},
        {"order": "second", "step": "LOCK-1",
         "what": "owner signature of D-01..D-15 and P-01..P-04 (LOCK-1 brief) together with this framework's topology: "
                 "decision-quantity definitions, same-condition list, counterbalancing algorithm, missing-data and "
                 "data-quality rule forms, remount procedure, case logic, threshold FORMS and the rules by which LOCK-2 "
                 "computes their numeric values; grid levels from W1 / DI-1; frozen analysis and schedule scripts (sha256)",
         "contributes_to_thresholds": ["no data-derived number: the forms and the computation rules only"],
         "gate": "S1-C1 (LOCK-1 signed; LOCK1_DRAFT.json never counts)",
         "deliverables": ["docs/architecture_comparison/lock1/", "docs/architecture_comparison/experiment_package/",
                          "docs/experiments/phase1_prereg_framework/"],
         "score_bearing": False},
        {"order": "third", "step": "W5 freeze",
         "what": "LOCK-H1 of the held-out Hall-transport validation pre-registration with the frozen custody / blinding "
                 "plan (S1-C6). The S1a data firewall S1A-FW, frozen before S1a, already partitions the S1a data (A1 "
                 "control C1); LOCK-H1 fixes the full registration vs held-out partition before any S1a registration "
                 "input is released to the physics track and before any Hall-on H-1 reading (W5 K1)",
         "contributes_to_thresholds": ["no numeric Phase-1 threshold; it fixes which Phase-1 values are held out, "
                                       "who may see them and when (publication embargo option VP-17)"],
         "gate": "W5 lock files at the owner's VP-15 location; S1-C6 custody plan frozen",
         "deliverables": ["docs/validation/hall_transport_v2_prereg/"],
         "score_bearing": False},
        {"order": "fourth", "step": "S1/S1b",
         "what": "S1 qualification scheduled only when the N4 gate returns S1_READY; S1b = Hall-on re-mount series on "
                 "HW-0 at the S1b point (K re-installations x r readings, lane 25 Sec. 6.4); the custodian releases "
                 "dispersion statistics only (W5 K4)",
         "contributes_to_thresholds": ["thrust uncertainty (u_T Type A; with S1a u_Tscale)",
                                       "power uncertainty (u_P Type A; with S1a channel scale)",
                                       "remount reproducibility (u_inst, nu_rm = K - 1)",
                                       "drift and thermal time constants (dwell, settling)",
                                       "stability / noise (I_d band, noise floor, thrust noise)",
                                       "pressure behaviour (p_b at the S1b point, cold-flow p_b against flow)",
                                       "start sequences (ignition timeout, transition window)",
                                       "D0 / D0-ABS records"],
         "gate": "S1_READY from scripts/experiments/s1_readiness.py (S1-C1..S1-C8); D0 T-READINESS after S1",
         "deliverables": ["docs/experiments/s1_readiness/", "docs/experiments/capability_demo/"],
         "score_bearing": False},
        {"order": "fifth", "step": "LOCK-2",
         "what": "records the sha256 of LOCK-1 and inserts the numeric decision boundaries computed from the S1/S1b values "
                 "by the LOCK-1 rules, without discretion; fixes the block count n and draws / records the randomization "
                 "seed and the realized schedule; any change to a LOCK-1 item voids LOCK-1",
         "contributes_to_thresholds": ["every field of this framework whose value is the UNFROZEN literal"],
         "gate": "LOCK-2 filed at the D-05 location after D0 passes",
         "deliverables": ["LOCK-2 file (future; location per D-05)"],
         "score_bearing": False},
        {"order": "sixth", "step": "Phase 1",
         "what": "A5 H-1 Phase-1 branch decision: score-bearing, order-balanced readings over the pre-registered grid; "
                 "raw dataset frozen (sha256) and scored once by the frozen script; the mechanical case record goes to "
                 "the owner",
         "contributes_to_thresholds": ["none: thresholds are fixed before its first reading; score-bearing data taken "
                                       "before LOCK-2 are excluded"],
         "gate": "LOCK-2 filed",
         "deliverables": ["future Phase-1 dataset and case record"],
         "score_bearing": True},
    ]


def test_matrix(a5: dict) -> dict:
    tm = a5["phase1_branch_decision"]["test_matrix"]
    for frag in ("mdot_atm x x_O2 x V_d", "low-flow knee", "0.42-0.60", "3.2 mg/s"):
        if frag not in tm:
            raise InputChanged(f"A5 phase1_branch_decision.test_matrix no longer contains {frag!r}")
    return {
        "source": "A5 phase1_branch_decision.test_matrix (verbatim check of its fragments at build time)",
        "factors": [
            {"id": "TM-MDOT", "symbol": "m_dot_atm", "name": "anode atmospheric-surrogate mass flow", "kind": "set",
             "levels": "TBD - requires the W1 registered valve-outlet test points (DI-1 frozen or GROUND_QUALIFICATION_POINT "
                       "release, S1-C3) and LOCK-1"},
            {"id": "TM-XO2", "symbol": "x_O2", "name": "delivered O2 mass fraction of the bottled N2/O2 surrogate",
             "kind": "set",
             "levels": "TBD - requires W1 / DI-1 and LOCK-1; the pure-N2 slice is run first (od_hardware_pivot: N2 first)"},
            {"id": "TM-VD", "symbol": "V_d", "name": "discharge voltage at the terminals", "kind": "set",
             "levels": "TBD - requires the Hall design point and the bus allocation (lane-25 Sec. 4)"},
        ],
        "grid": "joint sweep m_dot_atm x x_O2 x V_d; grid levels TBD; every configuration visits every grid condition of "
                "a block (same condition for all three, A5 common_condition)",
        "density_rule": {
            "statement": "point density concentrated near the anticipated low-flow knee around the delivered-flow region, "
                         "and across the delivered O2 mass fraction range (A5)",
            "provenance": [
                {"what": "delivered-flow region: up to about 3.2 mg/s under H_RAM (A5 wording)",
                 "underlying": "overlay hall_sustainment_envelope_v1: delivered air flow bounded by RFP thrust ceiling / "
                               "orbital speed under H_RAM (3.205-3.217 mg/s across the nine cases)",
                 "evidence_class": "model-derived",
                 "status": "H_RAM is PROPOSED (owner to confirm, overlay open question HS-Q1)"},
                {"what": "delivered O2 mass fraction range 0.42-0.60 (A5 wording)",
                 "underlying": "overlay hall_sustainment_envelope_v1: SC-REC (complete recombination) O2 mass fraction "
                               "0.4165-0.6042 across the nine cases; largest O2 mass fraction tested in a comparable "
                               "published item 0.4737 (PPS1350)",
                 "evidence_class": "model-derived (SC-REC); the 0.4737 comparison value is the overlay's reading of a "
                                   "published item",
                 "status": "composition surrogate: no atomic O (qualifier COMPOSITION_SURROGATE)"},
                {"what": "published air / N2-O2 points lie at higher flows than the delivered region (A5 "
                         "architecture_closing_risks rank 1)",
                 "underlying": "A5 evidence text and docs/evidence/hall_sustainment/hall_sustainment_matrix.json",
                 "evidence_class": "as recorded there (literature items, not Vyovrinda hardware)",
                 "status": "context for the density rule only; never a prediction"},
            ],
        },
        "within_arm_levels": "pre-ionizer source power levels (off, lo, hi) inside rf_hall / ecr_hall visits (lane-25 "
                             "Sec. 4); values TBD - requires the source allocation in bus_power_boundary_v1",
        "covariates_not_axes": ["background pressure p_b (facility; S5 elevated-p_b check is separate)",
                                "P_feed and T_feed (follow flow and conductance with fixed hardware; recorded at IF-A5)",
                                "cathode Xe flow (fixed same-condition variable)",
                                "coil currents (fixed per V_d level by the pre-registered magnet setting)"],
        "never_axes": ["P5 calibration nuisance (registration, coil shape, divergence reading, facility "
                       "interpretation)", "Hall-closure uncertainty (never enters the feed state)"],
        "scan_rule": "per (x_O2, V_d) slice the flow is scanned down then up; the knee bracket is refined by the same "
                     "rule in every configuration (P-01); grid levels are fixed before the first score-bearing block, so "
                     "no configuration's condition set depends on another configuration's data (R-04)",
        "o2_rule": "O2-bearing slices are run last within every installation visit (D-10-A contamination control)",
        "qualifiers": ["COMPOSITION_SURROGATE", "PARTIAL_BOUNDARY until the ICD compressor draw exists"],
    }


def same_condition() -> dict:
    def v(i, group, name, role, ins, rule_ref, depends):
        return {"id": i, "group": group, "variable": name, "role": role, "instruments": ins, "rule_reference": rule_ref,
                "matching_tolerance": UNFROZEN, "tolerance_depends_on": depends}
    return {
        "definition": "Two or three readings are at the SAME CONDITION only if every variable below with role SET_MATCHED "
                      "or PROTOCOL_MATCHED matches its registered value within its matching tolerance, and every "
                      "MEASURED_COVARIATE is inside its admissibility tolerance. OUTCOME_NOT_MATCHED variables are "
                      "consequences of the configuration and are never matched away. The configuration (module exchange "
                      "through the common pre-ionizer interface) is the only controlled difference.",
        "roles": {"SET_MATCHED": "setpoint identical across configurations, verified at every reading",
                  "PROTOCOL_MATCHED": "same hardware / procedure, verified per installation",
                  "MEASURED_COVARIATE": "not settable independently; recorded and required inside a tolerance",
                  "OUTCOME_NOT_MATCHED": "a response of the configuration; recorded, never used to reject a reading"},
        "variables": [
            v("SC-FEED-MDOT", "feed state", "discharge propellant flow m_dot_prop = m_dot_a + m_dot_p (split fixed per "
              "configuration and pre-registered)", "SET_MATCHED", ["INS-05"], "lane-06 INV-FLOW",
              "S1a MFC calibration uncertainty on the working gas (S1-05)"),
            v("SC-FEED-COMP", "feed state", "per-species composition x_O2 of the surrogate", "SET_MATCHED", ["INS-05"],
              "lane-06 INV-PROP", "S1a MFC calibration (S1-05); instrumentation derived.mixture_mass_fraction_u"),
            v("SC-FEED-PFEED", "feed state", "feed pressure at the IF-A5 plane", "MEASURED_COVARIATE", ["INS-06"],
              "lane-25 Sec. 4 (p follows m_dot and conductance)", "S1a gauge calibration; S1b cold-flow behaviour"),
            v("SC-FEED-TFEED", "feed state", "feed temperature at the IF-A5 plane", "MEASURED_COVARIATE", ["INS-07"],
              "instrumentation INS-07", "S1a sensor calibration; S1b thermal time constants (S1-08)"),
            v("SC-ACC-HW", "accelerator", "same serial-numbered H-1 channel, anode, distributor; HW-0 uses the "
              "blank/spacer module with equivalent interfaces and service-line presence (A6)", "PROTOCOL_MATCHED",
              ["configuration log (serial numbers per pump-down)", "INS-20 channel dimensional inspection before and after "
               "the campaign"], "lane-06 INV-CHANNEL; A6 fo_preionizer_module_icd",
              "S1a as-built metrology and the ICD installation checks"),
            v("SC-ACC-VD", "accelerator", "discharge voltage at the thruster terminals (constant-voltage mode)",
              "SET_MATCHED", ["INS-04", "INS-02"], "lane-06 INV-VD", "S1a V_d channel calibration (S1-02)"),
            v("SC-ACC-ELEC", "accelerator", "grounding / floating scheme, cabling, filters, supplies", "PROTOCOL_MATCHED",
              ["INS-21"], "lane-06 INV-ELEC", "S1a insulation / resistance schedule (INS-P-06)"),
            v("SC-MAG-I", "magnet", "Hall coil currents", "SET_MATCHED", ["INS-04", "INS-24"], "lane-06 INV-MAG",
              "S1a coil-current channel calibration (S1-02)"),
            v("SC-MAG-BZ", "magnet", "B(z) peak and its axial location per configuration (ECR magnet perturbation)",
              "MEASURED_COVARIATE", ["INS-09"], "lane-06 INV-MAG / THR-INV-MAG",
              "S1a B(z) map-to-map repeatability (S1-06; CD-05)"),
            v("SC-MAG-T", "magnet", "coil winding temperature", "MEASURED_COVARIATE", ["INS-24"],
              "instrumentation INS-24", "S1b thermal time constants (S1-08)"),
            v("SC-CATH-UNIT", "cathode", "same C-1 serial number and position", "PROTOCOL_MATCHED",
              ["configuration log (serial number and position per pump-down)"],
              "lane-06 INV-CATH", "none (identity check)"),
            v("SC-CATH-FLOW", "cathode", "cathode Xe flow setpoint", "SET_MATCHED", ["INS-05"], "lane-06 INV-FLOW (m_dot_c)",
              "S1a Xe MFC calibration (S1-05)"),
            v("SC-CATH-SUPPLY", "cathode", "keeper and heater settings", "SET_MATCHED", ["INS-02"], "lane-06 INV-CATH",
              "S1a channel calibration (S1-02)"),
            v("SC-CATH-STATE", "cathode", "cathode-to-ground and keeper voltage (health indicators)", "MEASURED_COVARIATE",
              ["INS-04", "INS-02"], "lane-06 INV-CATH / THR-INV-CATH",
              "S1b dispersion of the cathode-to-ground voltage; HW-0 reference repeats"),
            v("SC-FAC-SAME", "facility pressure", "same chamber, pumps, thruster position and gauges", "PROTOCOL_MATCHED",
              ["INS-08"], "lane-06 INV-FAC", "none (identity check)"),
            v("SC-FAC-PB", "facility pressure", "reference background pressure of paired readings", "MEASURED_COVARIATE",
              ["INS-08"], "lane-06 THR-INV-FAC", "S1b p_b at the S1b point and cold-flow p_b (S1-10)"),
            v("SC-THERM-SETTLE", "thermal state", "settling criterion met before a reading (rate of change of every "
              "monitored temperature)", "PROTOCOL_MATCHED", ["INS-17", "INS-23"], "lane-06 INV-THERM / THR-INV-THERM",
              "S1b thermal time constants (S1-08)"),
            v("SC-THERM-HISTORY", "thermal state", "same conditioning and warm-up protocol after every installation",
              "PROTOCOL_MATCHED", ["INS-17", "INS-18"], "lane-06 design.conditioning", "S1b thermal time constants (S1-08)"),
            v("SC-DIAG", "diagnostics", "same instruments, positions, calibrations and reduction code", "PROTOCOL_MATCHED",
              ["INS-01", "INS-02", "INS-13", "INS-15"], "lane-06 INV-DIAG", "S1a pickup bound (S1-04)"),
        ],
        "outcomes_not_matched": ["I_d, T, P_bus, oscillation metrics", "steady-state wall and channel temperatures "
                                 "(INS-23) reached under the configuration", "source-induced heating of the channel"],
        "mismatch_consequence": "a reading outside a matching tolerance is CONDITION_MISMATCH: it enters no paired contrast "
                                "of that block, it is reported, and it is re-run under the pre-registered re-run rule "
                                "(MD-08); for W5 the separate condition-match rule TH-COND applies",
    }


def execution_design() -> dict:
    seqs = SEQUENCES
    if not (is_position_balanced(seqs, CONFIGS) and is_carryover_balanced(seqs, CONFIGS)):
        raise RuntimeError("Williams sequence set is not balanced")
    if set(seqs) != set(itertools.permutations(CONFIGS)):
        raise RuntimeError("for three configurations the Williams set must be all permutations")
    return {
        "clarification": "A5 phase1_branch_decision.order_at_every_point (Hall-only -> RF+Hall -> ECR+Hall) NAMES the "
                         "three configurations; it is NOT the score-bearing execution order (A6 "
                         "clarification_execution_order). Execution is order-balanced so that configuration is not "
                         "confounded with chamber conditioning, wall temperature, cathode history, magnet heating, facility "
                         "drift, contamination or hysteresis.",
        "a5_naming_order_is_execution_order": False,
        "unit": "block = one installation of each configuration, in the order of the block's sequence, each visiting the "
                "block's full condition set once; HW-0 reference installations sit between blocks",
        "scheme": "Williams design balanced for first-order carryover (REF-WILLIAMS1949): for an odd number of "
                  "treatments two mirror Latin squares are needed; for the three configurations the set is all six "
                  "permutations. Each configuration appears equally often in each position and each ordered pair of "
                  "consecutive configurations appears equally often.",
        "sequences": [{"id": f"SEQ-{chr(65 + i)}", "order": list(s),
                       "hardware": [HW_LABEL[c] for c in s]} for i, s in enumerate(seqs)],
        "balance_checked_by_script": {"position_balanced": True, "first_order_carryover_balanced": True,
                                      "no_self_carryover": True, "equals_all_permutations": True},
        "block_count_rule": "the block count n (fixed at LOCK-2) is a whole multiple of the sequence-set size for complete "
                            "balance; assign_sequences() raises otherwise; an incomplete design needs an owner-registered "
                            "rule (R-03)",
        "block_template": [
            {"slot": "HW0-REF-OPEN", "configuration": "hall_only",
             "role": "HW-0 reference repeat at REF-COND (drift and remount tracking); shared with the previous block's "
                     "closing reference", "scored_for_branch_decision": False},
            {"slot": "POSITION-1", "configuration": "sequence position 1", "role": "scored installation",
             "scored_for_branch_decision": True},
            {"slot": "POSITION-2", "configuration": "sequence position 2", "role": "scored installation",
             "scored_for_branch_decision": True},
            {"slot": "POSITION-3", "configuration": "sequence position 3", "role": "scored installation",
             "scored_for_branch_decision": True},
            {"slot": "HW0-REF-CLOSE", "configuration": "hall_only",
             "role": "HW-0 reference repeat at REF-COND; becomes the next block's HW0-REF-OPEN",
             "scored_for_branch_decision": False},
        ],
        "hw0_reference_repeats": {
            "present_in_every_block": True,
            "configuration": "hall_only",
            "reference_condition": "REF-COND = the S1b re-mount point (lane-25 OP3: m_dot_nom, V_nom, N2) so that the "
                                   "S1b dispersion statistics are the direct baseline of the drift check (PROPOSED)",
            "readings": "r readings per reference installation (r from the S1b plan, lane-25 T-S1-READINGS-PER-CYCLE)",
            "use": ["drift check DQR-03 against the S1b dispersion", "running check of installation reproducibility "
                    "against u_inst", "cathode-state tracking (SC-CATH-STATE)"],
            "not_used_for": "R_arch or any branch-decision classification (keeps the balanced estimator clean; PROPOSED)",
            "w5_class": "held under custody as held-out until W5 classifies them (fail closed; R-09)",
            "campaign_bracket": "S1b precedes the first block; the lane-25 S6 end-of-campaign HW-0 re-installation check "
                                "(D6 T-REMOUNT-CHECK) follows the last closing reference",
            "cost_note": "each block adds one reference installation (module exchange) to the three scored ones; the owner "
                         "may instead take the reference inside an adjacent HW-0 installation (REF-MERGED), which saves an "
                         "exchange but ties the reference to that installation's position (open item)",
        },
        "module_exchange": {
            "mechanism": "every installation, including HW-0, exchanges the module through the common H-1 Pre-Ionizer "
                         "Module Interface (fo_preionizer_module_icd); HW-0 uses the blank / spacer module with "
                         "equivalent interfaces and service-line presence, so module exchange is the controlled variable "
                         "(A6)",
            "interface_reference": PREIONIZER_ICD_PATH + " (built in parallel by fo_preionizer_module_icd; referenced by "
                                   "path only, not pinned; the interface must not be secretly RF-specific, A6)",
            "installation_procedure": "RR-02",
        },
        "randomization": {
            "sequence_assignment": "seeded random permutation of complete replicates of the six sequences over the n blocks "
                                   "(assign_sequences in this script; sha256-driven Fisher-Yates, unbiased rejection "
                                   "sampling); the frozen schedule script's sha256 is fixed at LOCK-1",
            "seed": "drawn and recorded at LOCK-2, after n is fixed and before the first score-bearing reading; option: a "
                    "sha256 commitment of the seed published at LOCK-1 and revealed at LOCK-2 (R-02)",
            "within_installation": "the order of (x_O2, V_d) slices is a seeded permutation re-drawn per installation with "
                                   "the pure-N2 slices first and O2-bearing slices last; within a slice the flow scan is "
                                   "down then up; in source configurations every condition is bracketed off, lo, hi, off "
                                   "in odd blocks and off, hi, lo, off in even blocks (lane-25 Sec. 7)",
            "independent_start": "shutdown and restart between consecutive visits of a condition (lane-06 replication "
                                 "definition, D-10-A)",
        },
        "analysis_note": "configuration effects are estimated within blocks; because of the balance, position and "
                         "first-order carryover terms are estimable and are reported; the exact model is fixed at LOCK-1 "
                         "in the frozen analysis script (PROPOSED)",
        "arm_stop_interaction": "if an arm stops under a pre-registered stop rule (lane-25 G-SRC, D3), its remaining slots "
                                "are recorded NOT_TESTED and skipped; the other configurations keep their pre-drawn "
                                "order; the realized loss of balance is reported (PROPOSED; R-13)",
        "confounds": [
            {"id": "CF-CHAMBER", "confound": "chamber conditioning (time since pump-down, outgassing, wall coverage)",
             "control": "identical post-vent conditioning sequence for every installation; counterbalanced positions",
             "measured_by": ["INS-08 base p_b before ignition", "INS-11 RGA background", "INS-18 time since pump-down"]},
            {"id": "CF-WALLTEMP", "confound": "wall / thruster temperature",
             "control": "settling criterion before every reading (SC-THERM-SETTLE); same warm-up protocol",
             "measured_by": ["INS-17 thruster and stand temperatures", "INS-23 anode and exit-region wall rings",
                             "INS-08 chamber wall temperature"]},
            {"id": "CF-CATHODE", "confound": "cathode history (cumulative hours, starts, oxygen exposure)",
             "control": "counterbalancing spreads cathode age evenly over configurations; daily Xe reference; same "
                        "start sequence", "measured_by": ["INS-P-08 C-1 logs (daily Xe reference, start log, hot-emitter "
                                                          "O-exposure log)", "INS-04 / INS-02 cathode-to-ground and keeper "
                                                          "voltage", "INS-23 cathode-tube temperature",
                                                          "HW-0 reference repeats"]},
            {"id": "CF-MAGNET", "confound": "magnet heating (coil resistance rise; field drift; ECR magnet perturbation)",
             "control": "coil currents set and logged identically; B(z) mapped per configuration before and after",
             "measured_by": ["INS-24 winding temperature and coil electrical record", "INS-09 B(z) maps (INS-P-07)"]},
            {"id": "CF-FACILITY", "confound": "facility and instrument drift (stand zero and scale, pumping, gauges, "
                                              "power channels)",
             "control": "HW-0 reference repeats between blocks; thrust zero before and after every visit; in-situ "
                        "calibration after every configuration change; counterbalancing",
             "measured_by": ["HW0-REF readings", "INS-01 zero and calibration records", "INS-08 p_b",
                             "INS-02 channel checks"]},
            {"id": "CF-CONTAMINATION", "confound": "contamination (oxygen exposure of cathode, anode and walls; deposits "
                                                   "from source modules)",
             "control": "pure-N2 slices first and O2-bearing slices last in every installation; identical conditioning",
             "measured_by": ["INS-11 RGA", "INS-22 near-cathode sampling", "INS-21 anode resistance",
                             "INS-19 / INS-20 witness coupons and post-test metrology (MS-M-01, MS-M-03, MS-M-04)"]},
            {"id": "CF-HYSTERESIS", "confound": "hysteresis / path dependence",
             "control": "flow scans down then up with the approach direction recorded; independent start between visits; "
                        "counterbalanced configuration order",
             "measured_by": ["direction-resolved sustainment classes (HYSTERETIC flag)", "INS-04 I_d at matched setpoints "
                                                                                          "in both directions"]},
            {"id": "CF-INSTALL", "confound": "installation effect of the module exchange itself",
             "control": "common interface and the RR-02 procedure for every module including the HW-0 spacer",
             "measured_by": ["RR-03 post-installation checks", "S1b u_inst", "HW0-REF readings"]},
        ],
    }


def case_logic(a5: dict) -> dict:
    cases = a5["phase1_branch_decision"]["cases"]
    if set(cases) != {"A_extended_hall", "B_rf_hall", "C_ecr_hall", "NO_VIABLE_CASE"}:
        raise InputChanged("A5 phase1_branch_decision.cases changed")
    common = ["P1DQ-TABS demonstrated", "P1DQ-PBUS demonstrated on the V1 basis (PARTIAL_BOUNDARY is necessary only)",
              "P1DQ-STAB criterion met", "P1DQ-IGN criterion met"]
    return {
        "outcomes": ["A", "B", "C", "NO_VIABLE_CASE"],
        "branch_of_outcome": {"A": "hall_only", "B": "rf_hall", "C": "ecr_hall", "NO_VIABLE_CASE": None},
        "a5_case_ids": {"A": "A_extended_hall", "B": "B_rf_hall", "C": "C_ecr_hall", "NO_VIABLE_CASE": "NO_VIABLE_CASE"},
        "frozen_by": "A5 phase1_branch_decision.cases and A6 (four outcomes frozen now)",
        "definitions": {
            "PASS(X)": {"meaning": "configuration X meets every Phase-1 criterion on the required envelope",
                        "all_of": ["P1DQ-SUST: SUSTAINED at every required-envelope condition (P1DQ-ENVW coverage complete)",
                                   "P1DQ-NOXE: XE_FREE at every such condition (necessary)",
                                   "P1DQ-ETAU utilization criterion met"] + common},
            "FAILS_REQUIRED_POINT(hall_only)": "hall_only is NOT_SUSTAINED, XE_DEPENDENT or fails the stability criterion "
                                               "at one or more required atmospheric points",
            "RESTORES(X)": "at every required point where hall_only fails, X is SUSTAINED, XE_FREE and stable (pair class "
                           "ENABLES where hall_only is NOT_SUSTAINED)",
            "NET_BENEFIT(X)": "on bus_power_boundary_v1 (V1 basis) with the source, its matching and its PPU losses inside "
                              "P_bus, X meets P1DQ-TABS and P1DQ-PBUS at every required point, and the mass of its module, "
                              "matching and PPU fits the system mass allocation (external input); where both X and "
                              "hall_only sustain, the paired P1DQ-TPBUS classification is reported and enters by the form "
                              "the owner fixes at LOCK-1 (R-11)",
            "COMMON_BOUNDARY_CRITERION(X)": "FAILS_REQUIRED_POINT(hall_only) AND RESTORES(X) AND PASS(X) AND NET_BENEFIT(X)",
        },
        "rules": [
            {"outcome": "A", "a5": cases["A_extended_hall"],
             "condition": "PASS(hall_only), which includes P1DQ-NOXE as a necessary condition",
             "necessary": ["P1DQ-NOXE"]},
            {"outcome": "B", "a5": cases["B_rf_hall"],
             "condition": "NOT PASS(hall_only) with FAILS_REQUIRED_POINT(hall_only) AND COMMON_BOUNDARY_CRITERION(rf_hall)",
             "necessary": ["net system-level benefit at P_bus (NET_BENEFIT)", "P1DQ-NOXE for rf_hall"]},
            {"outcome": "C", "a5": cases["C_ecr_hall"],
             "condition": "NOT PASS(hall_only) with FAILS_REQUIRED_POINT(hall_only) AND NOT "
                          "COMMON_BOUNDARY_CRITERION(rf_hall) AND COMMON_BOUNDARY_CRITERION(ecr_hall)",
             "necessary": ["net system-level benefit at P_bus (NET_BENEFIT)", "P1DQ-NOXE for ecr_hall"]},
            {"outcome": "NO_VIABLE_CASE", "a5": cases["NO_VIABLE_CASE"],
             "condition": "every configuration is established to fail its criterion: NOT PASS(hall_only) AND NOT "
                          "COMMON_BOUNDARY_CRITERION(rf_hall) AND NOT COMMON_BOUNDARY_CRITERION(ecr_hall), with the "
                          "failing criteria resolved (not UNRESOLVED)",
             "necessary": ["no case is forced to win"]},
        ],
        "evaluation_precedence": "A, then B, then C, then NO_VIABLE_CASE: A5's contingency order (RF primary contingency, "
                                 "ECR alternate). It is a decision rule applied to complete data, never an execution order",
        "decision_status_open": "PROPOSED: if a required classification is UNRESOLVED, SUSTAINMENT_MIXED, "
                                "NOT_SCOREABLE_FACILITY or missing so that none of the four outcomes is established, the "
                                "decision stays OPEN (not an outcome); the blocking decision quantities go to the owner; "
                                "NO_VIABLE_CASE is never a default for missing evidence (R-12)",
        "external_constraints": {
            "mass": "system mass against the RFP mass requirement and the A5 mass allocation: from the mass ledger "
                    "(fo_subsystem_maturity_matrix, docs/architecture_comparison/mass_bom/, fo_xe_system_ledger), not a "
                    "Phase-1 measurement",
            "life": "firing and non-consumable life: from the life evidence (docs/experiments/lifetime_ao/, "
                    "docs/thermal_life/), not a Phase-1 measurement",
        },
        "current_outcome": "NOT_EVALUATED - no Phase-1 data exist; this framework evaluates nothing and prefers no branch",
    }


def missing_data() -> list:
    return [
        {"id": "MD-01", "event": "uncommanded extinction", "classification": "OBSERVATION (NOT_SUSTAINED reading)",
         "rule": "a sustainment observation, never missing data: it enters P1DQ-SUST, P1DQ-ENVW and P1DQ-STAB (S6); never "
                 "excluded and never re-run to obtain a sustained reading"},
        {"id": "MD-02", "event": "failed ignition or restart", "classification": "OBSERVATION (NOT_IGNITED)",
         "rule": "enters P1DQ-IGN; never missing, never excluded"},
        {"id": "MD-03", "event": "discharge stays lit only with discharge-feed Xe or raised cathode Xe",
         "classification": "OBSERVATION (XE_DEPENDENT)", "rule": "enters P1DQ-NOXE and P1DQ-SUST; never missing"},
        {"id": "MD-04", "event": "abort on a limit of a thruster / configuration quantity (discharge current or voltage, "
                                 "component temperature, reflected power)",
         "classification": "OBSERVATION (ABORTED_AT_LIMIT)",
         "rule": "PROPOSED: treated as not sustained within limits for that reading; reported with the limit that fired; "
                 "limits come from the approved S1-C8 safety / operational limits"},
        {"id": "MD-05", "event": "facility-caused interruption (p_b excursion above the limit, pump or facility fault, "
                                 "facility power loss)",
         "classification": "MISSING (NOT_SCOREABLE_FACILITY)",
         "rule": "not evidence for or against any configuration; re-run under MD-08"},
        {"id": "MD-06", "event": "instrument failure or invalid calibration (thrust stand, power channel, flow, gauge, "
                                 "E x B / Faraday probe)",
         "classification": "MISSING for the dependent decision quantities only (EXCLUDED_INSTRUMENT)",
         "rule": "missingness is per decision quantity through its measurement chain: a thrust-stand failure leaves "
                 "P1DQ-SUST observable from INS-04; a missing bus_power_boundary_v1 row makes P_bus undefined "
                 "(EXCLUDED_MISSING_BOUNDARY_COMPONENT)"},
        {"id": "MD-07", "event": "instrument failure correlated with a configuration (for example source pickup)",
         "classification": "OBSERVATION (INSTRUMENT_INCOMPATIBLE_WITH_CONFIGURATION)",
         "rule": "counted per configuration and reported; never silently dropped"},
        {"id": "MD-08", "event": "re-run of a MISSING reading",
         "classification": "RE-RUN RULE",
         "rule": "only MD-05 / MD-06 readings are re-run: inside the same installation at its end where possible, "
                 "otherwise at the end of the block with the same randomization rule; the re-run cap is the field re_run_cap "
                 "(lane-06 re-run cap TBD); observations (MD-01..MD-04, MD-07) are never re-run", "re_run_cap": UNFROZEN},
        {"id": "MD-09", "event": "lost configuration visit (incomplete block)",
         "classification": "MISSING (block-level)",
         "rule": "paired contrasts needing the lost visit are missing; the rest of the block is kept; balance loss is "
                 "reported; a replacement block, if any, follows the replacement rule fixed at LOCK-1 (never chosen after "
                 "seeing data)"},
        {"id": "MD-10", "event": "any exclusion",
         "classification": "NO POST HOC EXCLUSION",
         "rule": "every exclusion follows mechanically from a pre-registered status evaluated by the frozen script on "
                 "logged data, with coded configuration labels; excluded readings are reported, never deleted; a deviation "
                 "is a dated addendum that discloses what data had been seen (lane-06 PR-5); missingness decisions never "
                 "depend on the outcome values T, I_d or P_bus except through these status rules"},
    ]


def data_quality() -> list:
    def r(i, check, ins, consequence, depends):
        return {"id": i, "check": check, "instruments": ins, "limit": UNFROZEN, "limit_depends_on": depends,
                "consequence": consequence}
    return [
        r("DQR-01", "instrument health: self-test, zero and reference-source checks before and after every visit",
          ["INS-01", "INS-02", "INS-04", "INS-05", "INS-08"], "EXCLUDED_INSTRUMENT for the dependent quantities (MD-06)",
          "S1a noise floors and channel checks (CD-01, CD-03)"),
        r("DQR-02", "calibration currency: every instrument inside its calibration interval on the reading date per the "
          "frozen calibration plan (S1-C5); certificate id logged; lab metrology traceable with GUM uncertainty and "
          "coverage factor (MS-G-02, MS-G-03)", ["all INS"], "EXCLUDED_INSTRUMENT (MD-06)",
          "the frozen S1-C5 calibration plan (interval values are set there, not here)"),
        r("DQR-03", "drift against the HW-0 reference repeats: each HW0-REF reading compared with the S1b dispersion at "
          "REF-COND", ["INS-01", "INS-02", "INS-04"], "block flagged DRIFT_EXCEEDED; its contrasts are handled by the rule "
          "fixed at LOCK-1 (kept with flag or excluded), never chosen after scoring",
          "S1b within-cycle and cycle-to-cycle dispersion (S1-07)"),
        r("DQR-04", "thrust-stand zero drift over a dwell and in-situ calibration shift after each configuration change",
          ["INS-01", "INS-17"], "EXCLUDED_INSTRUMENT for thrust-dependent quantities",
          "S1a in-situ calibrations (S1-01); S1b thermal drift (S1-08)"),
        r("DQR-05", "background pressure below the facility limit T-PB-MAX", ["INS-08"], "NOT_SCOREABLE_FACILITY (MD-05)",
          "S1b p_b at the S1b point and cold-flow p_b (S1-10); facility specification at LOCK-1 (D-12)"),
        r("DQR-06", "paired background-pressure match between configurations", ["INS-08"], "CONDITION_MISMATCH",
          "S1b p_b behaviour (S1-10)"),
        r("DQR-07", "thermal settling criterion met before the reading", ["INS-17", "INS-23", "INS-24"],
          "reading not taken until met; a forced reading is CONDITION_MISMATCH", "S1b thermal time constants (S1-08)"),
        r("DQR-08", "RF / microwave pickup on common diagnostics within the DUMMY_LOAD_PICKUP bound",
          ["INS-02", "INS-04", "INS-01"], "source-on readings of the affected channels invalid until fixed (MD-07)",
          "S1a DUMMY_LOAD_PICKUP (S1-04)"),
        r("DQR-09", "bus-power completeness: every bus_power_boundary_v1 row of the configuration present (compressor "
          "with its ABSENT_IN_LAB disposition)", ["INS-02"], "EXCLUDED_MISSING_BOUNDARY_COMPONENT",
          "none numeric (completeness); ledger residual per the arch_boundary conservation gate"),
        r("DQR-10", "common time base: channel skew within the synchronization limit", ["INS-18"],
          "EXCLUDED_INSTRUMENT for time-resolved quantities", "S1a DAQ channel performance (CD-06)"),
        r("DQR-11", "magnetic invariance: B(z) peak and location per configuration within tolerance", ["INS-09"],
          "CONFOUNDED_MAGNETIC (lane-06 status)", "S1a B(z) repeatability (S1-06; CD-05)"),
        r("DQR-12", "raw-data integrity: raw files hashed at acquisition; dataset frozen by sha256 before scoring; coded "
          "configuration labels", ["INS-18"], "unhashed data are not score-bearing", "none numeric"),
    ]


def repeatability_remount() -> list:
    return [
        {"id": "RR-01", "what": "one installation per configuration visit",
         "rule": "every scored configuration visit and every HW-0 reference is its own installation through the common "
                 "pre-ionizer module interface, so every configuration carries the same installation variance"},
        {"id": "RR-02", "what": "installation procedure (identical for the RF module, the ECR module and the HW-0 spacer)",
         "rule": "vent; remove the module; install at the mounting datum; reconnect service lines along the ICD routing; "
                 "pressure-boundary and leak check; pump down; identical conditioning; settle; in-situ thrust calibration "
                 "and tares (mass on the stand changes with the module, INS-01); power-channel check (INS-02); B(z) check "
                 "at operating coil currents (INS-09); electrical isolation check (INS-21)",
         "interface_items": ["mechanical envelope and mounting datum", "gas-flow path and pressure boundary",
                             "allowable pressure drop", "permitted magnetic-field disturbance", "service-line routing",
                             "installation/removal reproducibility"],
         "interface_reference": PREIONIZER_ICD_PATH},
        {"id": "RR-03", "what": "post-installation acceptance checks",
         "rule": "each RR-02 check compared with its acceptance limit before the first reading of the installation; a "
                 "failed check means re-installation, logged; never a reading taken on a failed installation",
         "limit": UNFROZEN,
         "limit_depends_on": "S1a no-plasma re-installation reproducibility (CD-02a) and the ICD "
                             "installation/removal-reproducibility item; S1b u_inst"},
        {"id": "RR-04", "what": "within-installation repeats",
         "rule": "source configurations: off, lo, hi, off bracket (off, hi, lo, off in even blocks, lane-25 Sec. 7); all "
                 "configurations including HW-0: the first condition of the installation is repeated at its end "
                 "(PROPOSED)"},
        {"id": "RR-05", "what": "HW-0 reference repeats", "rule": "HW0-REF installation at REF-COND before the first "
                 "block, between consecutive blocks and after the last block (execution_design.hw0_reference_repeats)"},
        {"id": "RR-06", "what": "S1b re-mount series before LOCK-2",
         "rule": "K HW-0 re-installations x r readings at the S1b point (lane-25 Sec. 6.4) give u_inst with K - 1 degrees "
                 "of freedom; K and r are LOCK-1 items (lane-25 T-S1-REMOUNT-CYCLES, T-S1-READINGS-PER-CYCLE)"},
        {"id": "RR-07", "what": "module-exchange remount check (PROPOSED extension)",
         "rule": "before LOCK-2, the RF and ECR modules are each installed and removed through the common interface with "
                 "the source off at the S1b point, to verify the ICD installation/removal reproducibility per module; not "
                 "in the lane-25 S1b plan (R-06)"},
        {"id": "RR-08", "what": "end-of-campaign check",
         "rule": "lane-25 S6 HW-0 re-installation check (D6 T-REMOUNT-CHECK); a failure flags every cross-installation "
                 "class REMOUNT_CHECK_FAILED"},
        {"id": "RR-09", "what": "campaign-level magnetic and witness records",
         "rule": "B(z) maps per configuration before and after the campaign (INS-P-07); witness items per INS-P-01..04"},
    ]


def locks() -> dict:
    return {
        "lock1_fixes": [
            "D-01..D-15 and P-01..P-04 owner choices (LOCK-1 brief)",
            "this framework's topology: decision-quantity definitions, same-condition variables and roles, the Williams "
            "sequence set and the assignment algorithm, missing-data and data-quality rule forms, the remount procedure, "
            "the case logic and the OPEN status",
            "every threshold FORM and the rule by which LOCK-2 computes its numeric value from S1/S1b",
            "grid levels and the required-envelope subset (from W1 / DI-1)", "REF-COND",
            "S1 plan (K, r, S1b point) and the instrument list", "frozen analysis and schedule scripts (sha256)",
            "ledger inputs, unmeasured-load bounds and their evidence classes (D-11)",
        ],
        "lock2_converts": [
            {"s1_quantity": "thrust uncertainty", "from": "S1a u_Tscale (S1-01) and S1b u_T (S1-07)",
             "becomes": "absolute-thrust bounds (P1DQ-TABS) and the ln R_arch half-width (P1DQ-TPBUS)"},
            {"s1_quantity": "power uncertainty", "from": "S1a channel scale (S1-02), u_src (S1-03) and S1b u_P (S1-07)",
             "becomes": "P_bus bounds (P1DQ-PBUS) and the ln R_arch half-width (P1DQ-TPBUS)"},
            {"s1_quantity": "remount reproducibility", "from": "S1b u_inst (S1-07); RR-07 if adopted",
             "becomes": "coverage factor and block count n, RR-03 acceptance limits"},
            {"s1_quantity": "drift", "from": "S1b dispersion at REF-COND, stand zero drift (S1-07, S1-08)",
             "becomes": "DQR-03 and DQR-04 limits"},
            {"s1_quantity": "stability / noise", "from": "S1b I_d band and thrust noise (S1-09, S1-07); S1a noise floors",
             "becomes": "ext_window, sampling rate, oscillation class threshold, I_d floor (P1DQ-SUST, P1DQ-STAB)"},
            {"s1_quantity": "pressure behaviour", "from": "S1b p_b at the S1b point and cold-flow p_b (S1-10)",
             "becomes": "DQR-05 / DQR-06 limits and the SC-FAC-PB tolerance"},
            {"s1_quantity": "thermal time constants", "from": "S1b (S1-08)",
             "becomes": "dwell / hold time and the SC-THERM-SETTLE criterion"},
            {"s1_quantity": "flow resolution and zero drift", "from": "S1a MFC calibration (S1-05; CD-04)",
             "becomes": "min_flow_step, SC-FEED-* tolerances, the Xe zero band (P1DQ-NOXE)"},
            {"s1_quantity": "start sequences", "from": "S1b / pilot (S1-12)",
             "becomes": "ignition timeout (P1DQ-IGN) and the maximum transition window (P1DQ-NOXE)"},
            {"s1_quantity": "schedule", "from": "n from readiness_n",
             "becomes": "seed drawn and recorded; realized sequence-to-block assignment"},
        ],
        "rule": "LOCK-2 adds only S1/S1b values and what the LOCK-1 rules compute from them, without discretion; any change "
                "to a LOCK-1 item voids LOCK-1; score-bearing data taken before LOCK-2 are excluded (lane 25 Sec. 10)",
    }


def relation_to_w5() -> dict:
    return {
        "w5_path": "docs/validation/hall_transport_v2_prereg/",
        "held_out_from_phase1": [
            {"family": "F1", "phase1_data": "hall_only N2 flow scans down and up (pure-N2 slices of HW-0 installations)",
             "w5_role": "HELD_OUT mandatory"},
            {"family": "F2", "phase1_data": "hall_only N2 grid conditions (HW-0 installations, pure-N2 slices)",
             "w5_role": "HELD_OUT mandatory"},
            {"family": "F3", "phase1_data": "rf_hall / ecr_hall source-off readings on N2 (module installed)",
             "w5_role": "HELD_OUT secondary (VP-11)"},
        ],
        "not_held_out": [
            {"family": "F4", "phase1_data": "source-on readings", "w5_role": "SEQUESTERED_FOR_FUTURE_PREREG (inflow gap RG-03)"},
            {"family": "F5", "phase1_data": "O2-bearing slices (x_O2 above zero)",
             "w5_role": "SEQUESTERED_FOR_FUTURE_PREREG (no O/O2 chemistry)"},
            {"family": "F6", "phase1_data": "hall_only on Xe (D-15-B health check) if adopted; Xe startup / transition "
                                            "readings of P1DQ-IGN are not F6", "w5_role": "OPTIONAL held-out family (VP-12)"},
            {"family": "F7", "phase1_data": "S5 elevated-p_b readings",
             "w5_role": "FACILITY evidence (TH-FAC admissibility and the secondary mode only)"},
        ],
        "grid_enumeration": "W5 enumerates its finite condition grid at LOCK-H1 from the LOCK-1 grid of this framework "
                            "(W5 condition_families.rule), so every held-out condition is predicted before it is measured",
        "open": "classification of the HW0-REF readings (F2 or a drift family) is W5's decision; until then they stay under "
                "custody as held-out (R-09)",
        "observables": "VO-ID, VO-T and VO-IGNEXT are gating for validation; VO-OSC, VO-SPECIES, VO-IEDF, VO-TENE are "
                       "non-gating; REG-* are registration inputs (W5 draft)",
        "modes_never_crossed": [
            "the Phase-1 branch decision and the Hall-transport validation are separate decision processes fed from one "
            "custody-controlled raw dataset; no model output enters a Phase-1 classification and no Phase-1 outcome "
            "changes a W5 criterion",
            "vacuum-mode and facility-mode validation are never crossed (W5 Sec. 7)",
            "no screening candidate or unadmitted closure is a performance source for any decision quantity",
        ],
        "embargo": "under W5 VP-17 RELEASE_GATED, HW-0 held-out values in a Phase-1 record are disclosed outside the custody "
                   "circle only after PF-1 is hash-frozen; an earlier disclosure flags the affected W5 conditions "
                   "OUTPUTS_SEEN (validation side only; the Phase-1 decision is unaffected)",
    }


def reconciliation_items() -> list:
    return [
        {"id": "R-01", "with": "lane-25 Sec. 7 / LOCK-1 brief phases.phase_2 (HW-0 first in S2 and last in S6; a seeded "
                              "coin orders HW-RF and HW-ECR between them)",
         "issue": "campaign-level configuration order confounds configuration with time (A6 clarification)",
         "proposal": "the order-balanced design here governs the A5 Phase-1 readings; lane-25 S2-first / S6-last become "
                     "the HW0-REF and S6 checks"},
        {"id": "R-02", "with": "lane-25 Sec. 10 (seed recorded at LOCK-1)", "issue": "seed timing",
         "proposal": "seed drawn and recorded at LOCK-2 after n is fixed; optional sha256 commitment at LOCK-1"},
        {"id": "R-03", "with": "LOCK-1 brief D-08 (even n fixed at LOCK-2 by readiness_n)",
         "issue": "complete position and carryover balance needs whole replicates of the six sequences",
         "proposal": "restrict admissible n to whole replicates, or register an incomplete-design rule at LOCK-1"},
        {"id": "R-04", "with": "lane-25 knee-derived OP2 (S2 before S4)",
         "issue": "under counterbalancing a condition set must not depend on another configuration's data",
         "proposal": "grid fixed at LOCK-1 from W1 and the anticipated knee region; the knee is an output per "
                     "configuration (P1DQ-ENVW)"},
        {"id": "R-05", "with": "lane-25 s1_plan (S1b measures M1, M2, M3, M9, M10, M11)",
         "issue": "eta_u has no S1b repeatability, hence no statistical boundary",
         "proposal": "add Faraday / E x B repeatability at the S1b point, or report eta_u descriptively and state how "
                     "Case A's utilization criterion is then judged"},
        {"id": "R-06", "with": "lane-25 Sec. 6.4 (S1b re-mounts HW-0 only)",
         "issue": "the ICD installation/removal reproducibility of the RF and ECR modules is unmeasured before LOCK-2",
         "proposal": "RR-07 module-exchange remount check"},
        {"id": "R-07", "with": "od_hardware_pivot phases (Phase 1 knee, Phase 2 comparison, Phase 3 absolute)",
         "issue": "A5 'Phase 1' (H-1 branch decision) spans the pivot's Phase-1 knee, Phase-2 comparison and Phase-3-type "
                  "absolute gates", "proposal": "the owner confirms the mapping at LOCK-1"},
        {"id": "R-08", "with": "LOCK-1 brief D-07 (delta at LOCK-1)",
         "issue": "A6 forbids freezing Phase-1 numeric thresholds now",
         "proposal": "the owner states whether an effect-size level is a LOCK-1 rule input or a LOCK-2 value; this "
                     "framework fixes neither"},
        {"id": "R-09", "with": "W5 families", "issue": "W5 class of the HW0-REF readings",
         "proposal": "held-out custody until W5 decides"},
        {"id": "R-10", "with": "lane-06 design.randomisation (fixed propellant blocks Xe reference -> N2 -> O2/N2)",
         "issue": "within-installation ordering", "proposal": "pure-N2 first, O2-bearing last within every installation "
                                                              "(D-10-A); an Xe reference, if any, per D-15"},
        {"id": "R-11", "with": "A5 case B wording", "issue": "form of the net system-level benefit where both sustain",
         "proposal": "owner fixes the form at LOCK-1 (NET_BENEFIT)"},
        {"id": "R-12", "with": "A5 cases", "issue": "evidence that establishes no outcome",
         "proposal": "decision status OPEN (not an outcome)"},
        {"id": "R-13", "with": "lane-25 stop rules (G-SRC, D2, D3)", "issue": "an arm stop breaks the schedule balance",
         "proposal": "skip the stopped arm's slots (NOT_TESTED); keep the other configurations' pre-drawn order; report "
                     "the balance loss"},
        {"id": "R-14", "with": "LOCK-1 brief P-04-ii and D-15-C (Xe-augmented peak points)",
         "issue": "an Xe-augmented reading must not be read as atmospheric sustainment (A5 rule on continuous Xe)",
         "proposal": "label XE_AUGMENTED_PEAK; reported separately; never a nominal classification; never Case A "
                     "evidence; Xe consumed is booked to the single Xe allocation (fo_xe_system_ledger)"},
    ]


def a5_minimum_measurements(a5: dict) -> list:
    mm = a5["phase1_branch_decision"]["minimum_measurements"]
    mapping = {
        "discharge current": ["INS-04"], "thrust": ["INS-01"], "bus power": ["INS-02"], "source power": ["INS-03", "INS-02"],
        "cathode flow and power": ["INS-05", "INS-02"], "oscillation/stability": ["INS-04", "INS-10"],
        "ignition/restart behaviour": ["INS-10", "INS-04", "INS-05"],
        "species/acceleration diagnostics where available": ["INS-13", "INS-14", "INS-15"],
    }
    if list(mapping) != list(mm):
        raise InputChanged("A5 phase1_branch_decision.minimum_measurements changed")
    return [{"a5_measurement": k, "instruments": v} for k, v in mapping.items()]


REFERENCES = [
    {"id": "REF-WILLIAMS1949",
     "citation": "E. J. Williams, 'Experimental Designs Balanced for the Estimation of Residual Effects of Treatments', "
                 "Australian Journal of Scientific Research Series A: Physical Sciences 2(2), 149-168, 1949",
     "doi": "10.1071/CH9490149", "url": "https://connectsci.au/ch/article-lookup/doi/10.1071/CH9490149",
     "access": "abstract page read 2026-09-27 (bibliographic data and abstract; full text not read)",
     "used_for": "balance for first-order residual effects: n sequences for an even number of treatments, 2n for an odd "
                 "number (abstract); the construction in williams_sequences() is the standard one and its balance is "
                 "checked by this script, not taken from the paper"},
    {"id": "REF-INSTRUMENTATION-REFS",
     "citation": "REF-POLK2017, REF-DANKANICH2017, REF-SNYDER2017, REF-BROWN2017, REF-GUM2008 and the other references "
                 "exactly as recorded (with their access notes) in the pinned instrumentation definition, lane-06 protocol "
                 "and metrology specification",
     "access": "not re-read by this lane", "used_for": "only through the pinned deliverables' rules"},
]


def content() -> dict:
    verify_inputs()
    a5, a6, g0 = _load(A5_REL), _load(A6_REL), _load(G0_REL)
    if g0.get("verdict") != "CLEAN" or g0.get("a5_sha256") != PINNED[A5_REL]:
        raise InputChanged("G0 record does not certify the pinned A5")
    if a6.get("follows_sha256") != PINNED[A5_REL]:
        raise InputChanged("A6 does not follow the pinned A5")
    names = _a6_decision_quantity_names(a6)
    if len(names) != 9:
        raise InputChanged(f"A6 lists {len(names)} decision quantities, expected nine")
    ins_ids = {i["id"] for i in _load(INS_REL)["instruments"]} | {p["id"] for p in _load(INS_REL)["procedures"]}
    ms = _load(MS_REL)
    ms_ids = {g["id"] for g in ms["general_requirements"]} | {m["id"] for m in ms["measurands"]}
    s1_rows = {r["id"] for r in _load(LOCK1_REL)["s1_to_lock2"]["rows"]}
    w5_fams = {f["id"] for f in _load(W5_REL)["condition_families"]["families"]}
    s1a_ids = {c["id"] for c in _load(S1A_REL)["conditions"]}
    s1_ids = {c["id"] for c in _load(S1_REL)["conditions"]}
    b1 = _load(B1_REL)
    if b1["outcome"]["form"] != "NO_BASELINE_YET":
        raise InputChanged("Bundle 1 v5 outcome is no longer NO_BASELINE_YET")

    doc = {
        "schema": "abep_phase1_prereg_framework_v1",
        "id": "phase1_prereg_framework_v1",
        "follow_on": "fo_phase1_prereg_framework",
        "trigger": "T_A5_PHASE1_PREREG_FRAMEWORK",
        "owner_disposition": "od_hardware_pivot",
        "authorization": "owner addendum A6 authorized_now.fo_phase1_prereg_framework (lane name P1-PREG)",
        "status": "DRAFT_FOR_OWNER_ACCEPTANCE: decision topology; every numeric threshold UNFROZEN until LOCK-2",
        "base_commit": "302e1c94b3bddeb005f17bb189407f2e4641519a",
        "generated_by": SCRIPT_REL,
        "companion_document": MD_REL,
        "threshold_status_literal": UNFROZEN,
        "not_locked": True,
        "score_bearing": False,
        "measurements_existing": False,
        "context": {
            "a5_status": a5["status"],
            "a5_numbers": "allocations or requirements, never predictions (A5 what_this_is_not)",
            "bundle1_outcome": b1["outcome"]["form"],
            "credible_hall_set": "EMPTY (gate 3 FAIL; no admitted closure)",
            "open_branch": "hall_only / rf_hall / ecr_hall / NO_VIABLE_CASE, resolved by H-1 Phase 1 (A5)",
            "a6_not_authorized": a6["not_authorized"],
        },
        "pinned_inputs": [{"path": rel, "sha256": sha, "role": PIN_ROLES[rel][0], "producer": PIN_ROLES[rel][1],
                           "immutability": PIN_ROLES[rel][2]} for rel, sha in PINNED.items()],
        "referenced_by_path_only": [
            {"path": PREIONIZER_ICD_PATH, "why": "common H-1 Pre-Ionizer Module Interface, built in parallel by "
                                                 "fo_preionizer_module_icd (A6); not pinned"},
            {"path": "abep_sim/arch_boundary.py", "why": "bus_power_boundary_v1 component names (referenced by name, never "
                                                         "imported by this script)"},
        ] + [{"path": rel, "why": "mutable governance file: named, never pinned"} for rel in GOVERNANCE_NEVER_PINNED],
        "milestones": {
            "supports": "A",
            "statement": "Supports milestone A (conditional selection): it fixes, before any data, the topology by which "
                         "H-1 Phase 1 resolves the single open A5 branch, so that a later statement 'branch X is the "
                         "baseline provided ...' rests on pre-registered quantities, rules and outcomes. It outputs no "
                         "outcome now. It does not by itself support B (needs an admitted Hall closure through the W5 "
                         "PROMOTABLE path, O4-equivalent dispositions and an admission record) or C (needs integrated "
                         "mass, power, thermal, life, startup, cathode and mission closure).",
            "three_questions": {
                "conditional_selection_now": "nothing: no Phase-1 data exist; Bundle 1 stays NO_BASELINE_YET; A5 remains "
                                             "the proposal reference with the branch open",
                "blocks_physics_backed_selection": "empty credible Hall set; W5 not locked; no H-1 / C-1 hardware; S1a and "
                                                   "S1 gates not ready; no O / O2 chemistry",
                "could_overturn": "S1/S1b capability so poor that LOCK-2 boundaries leave most classifications UNRESOLVED "
                                  "(decision OPEN); configuration-correlated instrument incompatibility; carryover beyond "
                                  "first order (for example cumulative oxygen exposure); a common interface that is not "
                                  "configuration-neutral",
            },
        },
        "frozen_vs_proposed": {
            "owner_frozen": ["the nine decision quantities (A6)", "the four outcomes A / B / C / NO_VIABLE_CASE (A5, A6)",
                             "no continuous Xe augmentation as a necessary condition of Case A (A5)",
                             "the execution-order clarification (A6)", "the gating sequence S1a -> LOCK-1 -> W5 freeze -> "
                             "S1/S1b -> LOCK-2 -> Phase 1 (A6)"],
            "proposed_topology": "every definition, rule, role and procedure composed by this lane is PROPOSED topology "
                                 "until the owner accepts it at LOCK-1 (or amends it by a dated addendum before any S1 "
                                 "data)",
            "unfrozen_numbers": "every threshold, tolerance and limit: the UNFROZEN literal until LOCK-2",
        },
        "metrology_spec_relation": "the W4 metrology specification (MS-M-01..MS-M-05) covers witness-coupon and part "
                                   "metrology for life evidence (milestone C); no MS item enters a Phase-1 decision "
                                   "quantity directly. MS-G-02 (traceability) and MS-G-03 (GUM uncertainty with its "
                                   "coverage factor) apply through DQR-02; MS-M-01, MS-M-03 and MS-M-04 measure the "
                                   "contamination confound CF-CONTAMINATION after the campaign",
        "phase_terminology": "A5 'Phase 1' = the H-1 branch decision. It draws on the pivot's Phase-1 knee scan, its "
                             "Phase-2 common-condition comparison and Phase-3-type absolute gates at the delivered feed "
                             "(R-07)",
        "decision_quantities": decision_quantities(names),
        "a5_minimum_measurements_coverage": a5_minimum_measurements(a5),
        "gating_sequence": gating_sequence(),
        "test_matrix_structure": test_matrix(a5),
        "execution_design": execution_design(),
        "case_logic": case_logic(a5),
        "same_condition": same_condition(),
        "missing_data": missing_data(),
        "data_quality": data_quality(),
        "repeatability_remount": repeatability_remount(),
        "locks": locks(),
        "relation_to_w5": relation_to_w5(),
        "reconciliation_items": reconciliation_items(),
        "open_owner_decisions": [
            "accept this topology at LOCK-1 (or amend it by a dated addendum before any S1 data)",
            "R-01..R-14 (reconciliation with the lane-25 / lane-06 / LOCK-1 drafts and W5)",
            "REF-COND and the REF-MERGED option", "MD-04 treatment of configuration-caused limit aborts",
            "OPEN decision status (R-12)",
        ],
        "compliance": [
            "no numeric pass/fail threshold, tolerance or limit: every such field is the UNFROZEN literal; the JSON has no "
            "numeric leaf",
            "no measurement, prediction or outcome; current_outcome NOT_EVALUATED; no branch preferred, ranked or "
            "eliminated; Bundle 1 unchanged (NO_BASELINE_YET)",
            "no Hall transport closure, screening candidate or withdrawn 0-D number used; no retuning",
            "P5 calibration nuisance is never an axis or design variable; Hall-closure uncertainty never reaches the "
            "feed state, intake, compressor, gas chambers or valves",
            "owner decisions A5, A6 and the G0 record pinned by sha256; mutable governance files never pinned",
            "no simulator module modified or imported; not wired into archengine",
        ],
        "references": REFERENCES,
        "tbd_register": [
            {"item": "grid levels (m_dot_atm, x_O2, V_d) and the required-envelope subset", "requires": "W1 / DI-1, Hall "
             "design point, LOCK-1"},
            {"item": "REF-COND values", "requires": "LOCK-1 (S1b point)"},
            {"item": "every UNFROZEN field", "requires": "S1/S1b values and LOCK-2"},
            {"item": "block count n and seed", "requires": "LOCK-2"},
            {"item": "valve seat leakage for the Xe zero band", "requires": "valve specification (W3)"},
            {"item": "common pre-ionizer interface limits used by RR-03", "requires": "fo_preionizer_module_icd"},
        ],
    }

    # cross-check every referenced identifier against the pinned inputs (fail loudly, never silently)
    text = json.dumps(doc)
    for m in set(re.findall(r"\bINS-(?:P-)?\d\d\b", text)):
        if m not in ins_ids:
            raise InputChanged(f"{m} not in the pinned instrumentation definition")
    for m in set(re.findall(r"\bMS-[GM]-\d\d\b", text)):
        if m not in ms_ids:
            raise InputChanged(f"{m} not in the pinned metrology specification")
    for m in set(re.findall(r"\bS1-(?:0\d|1\d)\b", text)):
        if m not in s1_rows:
            raise InputChanged(f"{m} not in the LOCK-1 brief s1_to_lock2 rows")
    for m in set(re.findall(r"\bS1-C\d\b", text)):
        if m not in s1_ids:
            raise InputChanged(f"{m} not in the S1 readiness conditions")
    for m in set(re.findall(r"\bS1A-(?:C\d|FW)\b", text)):
        if m not in s1a_ids:
            raise InputChanged(f"{m} not in the S1a readiness conditions")
    for fam in doc["relation_to_w5"]["held_out_from_phase1"] + doc["relation_to_w5"]["not_held_out"]:
        if fam["family"] not in w5_fams:
            raise InputChanged(f"W5 family {fam['family']} not in the pinned W5 draft")
    _assert_no_numbers(doc)
    return doc


def _assert_no_numbers(obj, path="$"):
    if isinstance(obj, bool) or obj is None or isinstance(obj, str):
        return
    if isinstance(obj, (int, float)):
        raise RuntimeError(f"numeric leaf at {path}: the framework carries no numeric value")
    if isinstance(obj, dict):
        for k, v in obj.items():
            _assert_no_numbers(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _assert_no_numbers(v, f"{path}[{i}]")
    else:
        raise TypeError(f"unexpected type at {path}: {type(obj)}")


# --------------------------------------------------------------------------------------------------- markdown
def _cell(s) -> str:
    if isinstance(s, list):
        s = "; ".join(str(x) for x in s)
    return str(s).replace("|", "/").replace("\n", " ")


def render_md(doc: dict) -> str:
    L = []
    a = L.append
    a("# H-1 Phase-1 pre-registration framework (decision topology)")
    a("")
    a(f"**Status: {doc['status']}.** Follow-on `{doc['follow_on']}` (trigger `{doc['trigger']}`, owner disposition "
      f"`{doc['owner_disposition']}`, {doc['authorization']}), base commit `{doc['base_commit'][:10]}`. Generated by "
      f"`{doc['generated_by']}` from the authoritative `phase1_prereg_framework_v1.json`; `--check` reproduces both files "
      f"byte for byte and `tests/test_phase1_prereg_framework.py` checks them.")
    a("")
    a(f"Every numeric threshold, tolerance and limit in this framework has the literal value **`{UNFROZEN}`** and names "
      "the S1/S1b quantity from which LOCK-2 computes it. The JSON carries no numeric value at all. No measurement exists, "
      "no outcome is evaluated, and no branch is preferred, ranked or eliminated.")
    a("")
    a("## 0. Context")
    a("")
    c = doc["context"]
    a(f"- A5 status: `{c['a5_status']}`; A5 numbers are {c['a5_numbers']}.")
    a(f"- Bundle 1 outcome: `{c['bundle1_outcome']}`. Credible Hall set: {c['credible_hall_set']}.")
    a(f"- Open branch: {c['open_branch']}.")
    a(f"- A6 not authorized: {'; '.join(c['a6_not_authorized'])}.")
    a(f"- Terminology: {doc['phase_terminology']}.")
    fv = doc["frozen_vs_proposed"]
    a("- Owner-frozen: " + "; ".join(fv["owner_frozen"]) + ".")
    a(f"- Proposed topology: {fv['proposed_topology']}.")
    a(f"- Unfrozen numbers: {fv['unfrozen_numbers']}.")
    a(f"- Metrology specification: {doc['metrology_spec_relation']}.")
    a("")
    a("## 1. Milestone statement")
    a("")
    m = doc["milestones"]
    a(m["statement"])
    a("")
    for k, v in m["three_questions"].items():
        a(f"- **{k.replace('_', ' ')}:** {v}.")
    a("")
    a("## 2. Decision quantities (list frozen by A6)")
    a("")
    a("| id | A6 name | units | measurement chain | threshold | LOCK-2 derives it from |")
    a("|---|---|---|---|---|---|")
    for q in doc["decision_quantities"]:
        chain = ", ".join(f"{x['ins_id']} ({x['role'][0]})" for x in q["measurement_chain"])
        dep = "; ".join(f"{d['stage']}: {d['quantity']}" for d in q["threshold_depends_on"])
        a(f"| {q['id']} | {q['a6_name']} | {_cell(q['units'])} | {chain} | `{q['threshold']}` | {_cell(dep)} |")
    a("")
    a("Roles: D = decisive, C = condition, S = supporting (instrumentation `roles`).")
    a("")
    for q in doc["decision_quantities"]:
        a(f"### {q['id']}: {q['a6_name']}")
        a("")
        a(f"- **Operational definition.** {q['operational_definition']}")
        a(f"- **Configurations.** {q['per_configuration']}.")
        a("- **Measurement chain.** " + "; ".join(f"{x['ins_id']} {x['role'].lower()}: {x['quantity']}"
                                             for x in q["measurement_chain"]) + ".")
        a(f"- **Units.** {q['units']}.")
        a("- **Uncertainty sources.** " + "; ".join(q["uncertainty_sources"]) + ".")
        a(f"- **Threshold.** `{q['threshold']}`. Depends on: " + "; ".join(
            f"{d['stage']} {d['quantity']} ({d['source']})" for d in q["threshold_depends_on"]) + ".")
        a("- **Fixed at LOCK-1.** " + "; ".join(q["fixed_at_lock1"]) + ".")
        a("- **Existing rules.** " + "; ".join(q["existing_rule_references"]) + ".")
        a(f"- **A5 role.** {q['a5_role']}.")
        a("")
    a("A5 minimum measurements and their instruments: " + "; ".join(
        f"{x['a5_measurement']} ({', '.join(x['instruments'])})" for x in doc["a5_minimum_measurements_coverage"]) + ".")
    a("")
    a("## 3. Gating sequence")
    a("")
    a(" -> ".join(s["step"] for s in doc["gating_sequence"]))
    a("")
    a("| order | step | what | contributes to the thresholds | gate | deliverables | score-bearing |")
    a("|---|---|---|---|---|---|---|")
    for s in doc["gating_sequence"]:
        a(f"| {s['order']} | **{s['step']}** | {_cell(s['what'])} | {_cell(s['contributes_to_thresholds'])} | "
          f"{_cell(s['gate'])} | {_cell(s['deliverables'])} | {'yes' if s['score_bearing'] else 'no'} |")
    a("")
    a("## 4. Test-matrix structure")
    a("")
    t = doc["test_matrix_structure"]
    a(f"Source: {t['source']}. Grid: {t['grid']}.")
    a("")
    a("| factor | symbol | name | kind | levels |")
    a("|---|---|---|---|---|")
    for f in t["factors"]:
        a(f"| {f['id']} | {f['symbol']} | {f['name']} | {f['kind']} | {_cell(f['levels'])} |")
    a("")
    a(f"**Density rule.** {t['density_rule']['statement']}.")
    a("")
    a("| what | underlying source | evidence class | status |")
    a("|---|---|---|---|")
    for p in t["density_rule"]["provenance"]:
        a(f"| {_cell(p['what'])} | {_cell(p['underlying'])} | {_cell(p['evidence_class'])} | {_cell(p['status'])} |")
    a("")
    a(f"- Within-arm levels: {t['within_arm_levels']}.")
    a("- Covariates, not axes: " + "; ".join(t["covariates_not_axes"]) + ".")
    a("- Never axes: " + "; ".join(t["never_axes"]) + ".")
    a(f"- Scan rule: {t['scan_rule']}.")
    a(f"- Oxygen rule: {t['o2_rule']}.")
    a("- Qualifiers: " + ", ".join(t["qualifiers"]) + ".")
    a("")
    a("## 5. Order-balanced execution design")
    a("")
    e = doc["execution_design"]
    a(e["clarification"])
    a("")
    a(f"- Unit: {e['unit']}.")
    a(f"- Scheme: {e['scheme']}")
    a(f"- Block count: {e['block_count_rule']}.")
    a("")
    a("| sequence | position 1 | position 2 | position 3 |")
    a("|---|---|---|---|")
    for s in e["sequences"]:
        a(f"| {s['id']} | " + " | ".join(f"{c} ({h})" for c, h in zip(s["order"], s["hardware"])) + " |")
    a("")
    a("Balance checked by this script: " + ", ".join(k.replace("_", " ") for k, v in
                                                     e["balance_checked_by_script"].items() if v) + ".")
    a("")
    a("Block template:")
    a("")
    a("| slot | configuration | role | scored for the branch decision |")
    a("|---|---|---|---|")
    for s in e["block_template"]:
        a(f"| {s['slot']} | {s['configuration']} | {_cell(s['role'])} | "
          f"{'yes' if s['scored_for_branch_decision'] else 'no'} |")
    a("")
    h = e["hw0_reference_repeats"]
    a(f"**HW-0 reference repeats** (every block, `{h['configuration']}`): {h['reference_condition']}. Readings: "
      f"{h['readings']}. Used for: " + "; ".join(h["use"]) + f". Not used for {h['not_used_for']}. W5: {h['w5_class']}. "
      f"{h['campaign_bracket']}. Cost: {h['cost_note']}.")
    a("")
    me = e["module_exchange"]
    a(f"**Module exchange.** {me['mechanism']}. Interface: `{me['interface_reference']}`. Procedure: {me['installation_procedure']}.")
    a("")
    rz = e["randomization"]
    a("**Randomization.**")
    a("")
    for k in ("sequence_assignment", "seed", "within_installation", "independent_start"):
        a(f"- {k.replace('_', ' ')}: {rz[k]}.")
    a(f"- analysis: {e['analysis_note']}.")
    a(f"- arm stop: {e['arm_stop_interaction']}.")
    a("")
    a("**Confounds controlled and how each is measured.**")
    a("")
    a("| id | confound | control | measured by |")
    a("|---|---|---|---|")
    for cf in e["confounds"]:
        a(f"| {cf['id']} | {_cell(cf['confound'])} | {_cell(cf['control'])} | {_cell(cf['measured_by'])} |")
    a("")
    a("## 6. Case logic (A / B / C / NO_VIABLE_CASE)")
    a("")
    cl = doc["case_logic"]
    a(f"Frozen by: {cl['frozen_by']}. Branch per outcome: " + ", ".join(
        f"{k} -> `{v}`" for k, v in cl["branch_of_outcome"].items() if v) + ", NO_VIABLE_CASE -> none.")
    a("")
    for k, v in cl["definitions"].items():
        if isinstance(v, dict):
            a(f"- **{k}**: {v['meaning']}; all of: " + "; ".join(v["all_of"]) + ".")
        else:
            a(f"- **{k}**: {v}.")
    a("")
    a("| outcome | A5 text | condition | necessary |")
    a("|---|---|---|---|")
    for r in cl["rules"]:
        a(f"| {r['outcome']} | {_cell(r['a5'])} | {_cell(r['condition'])} | {_cell(r['necessary'])} |")
    a("")
    a(f"- Precedence: {cl['evaluation_precedence']}.")
    a(f"- Decision status OPEN: {cl['decision_status_open']}.")
    a(f"- External constraints: mass: {cl['external_constraints']['mass']}; life: {cl['external_constraints']['life']}.")
    a(f"- Current outcome: **{cl['current_outcome']}**.")
    a("")
    a("## 7. Same-condition definition")
    a("")
    sc = doc["same_condition"]
    a(sc["definition"])
    a("")
    a("Roles: " + "; ".join(f"`{k}` = {v}" for k, v in sc["roles"].items()) + ".")
    a("")
    a("| id | group | variable | role | instruments | rule | matching tolerance | from |")
    a("|---|---|---|---|---|---|---|---|")
    for v in sc["variables"]:
        a(f"| {v['id']} | {v['group']} | {_cell(v['variable'])} | {v['role']} | {_cell(v['instruments'])} | "
          f"{_cell(v['rule_reference'])} | `{v['matching_tolerance']}` | {_cell(v['tolerance_depends_on'])} |")
    a("")
    a("Not matched (outcomes): " + "; ".join(sc["outcomes_not_matched"]) + ".")
    a(f"Mismatch: {sc['mismatch_consequence']}.")
    a("")
    a("## 8. Missing-data rules")
    a("")
    a("| id | event | classification | rule |")
    a("|---|---|---|---|")
    for r in doc["missing_data"]:
        a(f"| {r['id']} | {_cell(r['event'])} | {_cell(r['classification'])} | {_cell(r['rule'])} |")
    a("")
    a("## 9. Data-quality rules")
    a("")
    a("| id | check | instruments | limit | limit from | consequence |")
    a("|---|---|---|---|---|---|")
    for r in doc["data_quality"]:
        a(f"| {r['id']} | {_cell(r['check'])} | {_cell(r['instruments'])} | `{r['limit']}` | "
          f"{_cell(r['limit_depends_on'])} | {_cell(r['consequence'])} |")
    a("")
    a("## 10. Repeatability and remount procedure")
    a("")
    for r in doc["repeatability_remount"]:
        extra = ""
        if "limit" in r:
            extra = f" Limit: `{r['limit']}` (from {r['limit_depends_on']})."
        if "interface_items" in r:
            extra += " Common-interface items: " + "; ".join(r["interface_items"]) + f" (`{r['interface_reference']}`)."
        a(f"- **{r['id']} {r['what']}.** {r['rule']}.{extra}")
    a("")
    a("## 11. LOCK-1 and LOCK-2")
    a("")
    lk = doc["locks"]
    a("**LOCK-1 fixes:**")
    a("")
    for x in lk["lock1_fixes"]:
        a(f"- {x}")
    a("")
    a("**LOCK-2 converts S1/S1b quantities into numeric boundaries:**")
    a("")
    a("| S1/S1b quantity | from | becomes |")
    a("|---|---|---|")
    for r in lk["lock2_converts"]:
        a(f"| {r['s1_quantity']} | {_cell(r['from'])} | {_cell(r['becomes'])} |")
    a("")
    a(f"Rule: {lk['rule']}.")
    a("")
    a("## 12. Relation to the W5 Hall-transport v2 pre-registration draft")
    a("")
    w = doc["relation_to_w5"]
    a(f"Path: `{w['w5_path']}`.")
    a("")
    a("| family | Phase-1 data | W5 role |")
    a("|---|---|---|")
    for f in w["held_out_from_phase1"] + w["not_held_out"]:
        a(f"| {f['family']} | {_cell(f['phase1_data'])} | {_cell(f['w5_role'])} |")
    a("")
    a(f"- Grid: {w['grid_enumeration']}.")
    a(f"- Open: {w['open']}.")
    a(f"- Observables: {w['observables']}.")
    a("- Modes never crossed: " + "; ".join(w["modes_never_crossed"]) + ".")
    a(f"- Embargo: {w['embargo']}.")
    a("")
    a("## 13. Reconciliation items for LOCK-1 (owner)")
    a("")
    a("| id | with | issue | proposal |")
    a("|---|---|---|---|")
    for r in doc["reconciliation_items"]:
        a(f"| {r['id']} | {_cell(r['with'])} | {_cell(r['issue'])} | {_cell(r['proposal'])} |")
    a("")
    a("Open owner decisions: " + "; ".join(doc["open_owner_decisions"]) + ".")
    a("")
    a("## 14. Compliance")
    a("")
    for x in doc["compliance"]:
        a(f"- {x}")
    a("")
    a("## 15. TBD register")
    a("")
    for x in doc["tbd_register"]:
        a(f"- {x['item']}: TBD - requires {x['requires']}.")
    a("")
    a("## 16. References")
    a("")
    for r in doc["references"]:
        doi = f" doi:{r['doi']} <{r['url']}>." if r.get("doi") else ""
        a(f"- **{r['id']}**: {r['citation']}.{doi} Access: {r['access']}. Used for: {r['used_for']}.")
    a("")
    a("## 17. Pinned inputs (sha256)")
    a("")
    a("| path | role | producer | sha256 |")
    a("|---|---|---|---|")
    for p in doc["pinned_inputs"]:
        a(f"| `{p['path']}` | {_cell(p['role'])} | {_cell(p['producer'])} | `{p['sha256']}` |")
    a("")
    a("Referenced by path only (never pinned): " + "; ".join(f"`{r['path']}` ({r['why']})"
                                                           for r in doc["referenced_by_path_only"]) + ".")
    a("")
    return "\n".join(L)


def build_all() -> dict:
    doc = content()
    js = json.dumps(doc, indent=1, ensure_ascii=False) + "\n"
    md = render_md(doc)
    return {ROOT / JSON_REL: js, ROOT / MD_REL: md}


def main(argv: list) -> int:
    outs = build_all()
    if "--check" in argv:
        bad = [str(p.relative_to(ROOT)) for p, s in outs.items()
               if not p.is_file() or p.read_text(encoding="utf-8") != s]
        if bad:
            print("DIFFERS: " + ", ".join(bad))
            return 1
        print("OK: outputs reproduce byte for byte")
        return 0
    for p, s in outs.items():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(s, encoding="utf-8")
        print(f"wrote {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
