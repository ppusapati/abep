"""Build the A9 Hall -> downstream RF-ICP neutralizer PRE-REGISTRATION FRAMEWORK and campaign stage map
(follow-on fo_a9_01_hall_icp_prereg_framework, trigger T_A9_01_PREREG_FRAMEWORK, owner decision A9).

Outputs (deterministic; `--check` verifies the committed files byte for byte):
  docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json   (authoritative)
  docs/experiments/hall_icp/prereg_framework/HALL_ICP_PREREG_FRAMEWORK.md       (rendered from the JSON)

What this is: the A9 campaign stage map (its own terminology, not the A5 'Phase 1'), the two configurations
'hall_c1_reference' and 'hall_icp_neutralizer' on the same H-1, the decision topology (hard gates first, then a Pareto
report; outcomes hall_c1_reference / hall_icp_neutralizer / NO_VIABLE_CASE; OPEN is a status), the decision-quantity list
(DQ-HI-*) with definitions, units, measurement chains and freeze points, and the design rules (order balance, replicate
sets, seed procedure, grid, stopped arms, limit aborts, ignition records, background pressure levels, held-out
validation subset, custody, missing-data and data-quality classes).

What this is not: NOT a lock (signed LOCK files will live in docs/experiments/hall_icp/prereg/, owner row 16). No
decision margin, effect size, stop-rule number or block count is frozen here; owner-given values are cited by row. No
performance is predicted: no Hall-transport closure is admitted, the 0-D Hall model is superseded and the withdrawn
v1.2-v1.6 numbers are never used. No outcome is evaluated and no configuration is preferred.

The only computations are (i) combinatorial: the complete order-balanced sequence set for the two configurations with
its position / first-order carryover balance, the minimum block count implied by owner row 19, and a seeded,
deterministic sequence-to-block assignment function (exercised by the test only with synthetic seeds); (ii) the ratio
check of the owner-stated full-system floor in row 27. Inputs are sha256-pinned; a changed or missing input raises
InputChanged. Standard library only; no simulator import, no Julia.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import re
import sys
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]

LANE_DIR = "docs/experiments/hall_icp/prereg_framework"
SCRIPT_REL = f"{LANE_DIR}/build_hall_icp_prereg_framework.py"
JSON_REL = f"{LANE_DIR}/hall_icp_prereg_framework_v1.json"
MD_REL = f"{LANE_DIR}/HALL_ICP_PREREG_FRAMEWORK.md"
TEST_REL = "tests/test_hall_icp_prereg_framework.py"
BASE_COMMIT = "0a430bb5588a438f7c8485c6d16f40ed0d402c4c"

C1 = "hall_c1_reference"
ICP = "hall_icp_neutralizer"
CONFIGS = (C1, ICP)
OUTCOMES = (C1, ICP, "NO_VIABLE_CASE")
STATUS_OPEN = "OPEN"

#: literal used wherever a decision margin / effect size / stop-rule number would go (owner row 18)
MARGIN_NOT_SET = ("NOT SET - defined here as a quantity only; its form is frozen at LOCK-1 and its value is computed at "
                  "LOCK-2 by the LOCK-1 rule from measured uncertainty (row 18)")
PENDING_A9_02 = "PENDING docs/architecture_comparison/power_boundary_a9/ (A9-02)"
PENDING_A9_03 = "PENDING docs/interfaces/icp_neutralizer/ (A9-03)"
PENDING_A9_04 = "PENDING docs/experiments/hall_icp/uncertainty_budget/ (A9-04)"
PENDING_A9_05 = "PENDING docs/evidence/icp_neutralizer/ and docs/experiments/hall_icp/validation_inputs/ (A9-05)"
PENDING_A9_06 = "PENDING A9-06 mass BOM A9 amendment (backlog item in the A9 decision; no path yet)"
PENDING_A9_07 = "PENDING A9-07 H2 revisions (backlog item in the A9 decision; no path yet)"
PENDING_A9_08 = "PENDING A9-08 Xe ledger updates (backlog item in the A9 decision; no path yet)"
PENDING_A9_10 = "PENDING A9-10 governance (backlog item in the A9 decision; no path yet)"

EVIDENCE_CLASSES = ("measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed",
                    "owner-allocation", "none (TBD)")
FREEZE_POINTS = ("NOW", "LOCK-1", "LOCK-2", "after-evidence")

A9_REL = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer.json"
ANS_REL = "docs/decisions/OD_2026_09_29_owner_answers_147.json"
PACK_REL = "docs/decisions/OD_2026_09_29_OWNER_DECISION_PACK_147.md"
A4_REL = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A4_owner_decisions.json"
A5_REL = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_architecture.json"
A6_REL = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A6_a5_followon_authorization.json"
A7_REL = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A7_execution_model.json"
HIST_JSON_REL = "docs/experiments/phase1_prereg_framework/phase1_prereg_framework_v1.json"
HIST_MD_REL = "docs/experiments/phase1_prereg_framework/PHASE1_PREREG_FRAMEWORK.md"
HIST_PY_REL = "docs/experiments/phase1_prereg_framework/build_phase1_prereg_framework.py"
PIM_MD_REL = "docs/interfaces/preionizer_module/PREIONIZER_MODULE_ICD.md"
PIM_PY_REL = "docs/interfaces/preionizer_module/build_preionizer_module_icd.py"
PIM_SCHEMA_REL = "schemas/interfaces/preionizer_module_icd_v1.json"
LOCK1_JSON_REL = "docs/architecture_comparison/lock1/lock1_decision_brief_v1.json"
LOCK1_DRAFT_REL = "docs/architecture_comparison/lock1/LOCK1_DRAFT.json"
HWREQ_REL = "docs/experiments/hardware/hardware_requirements_v1.json"
INS_REL = "docs/experiments/instrumentation/instrumentation_definition_v1.json"
MS_REL = "docs/experiments/instrumentation/metrology_spec/metrology_measurement_spec_v1.json"
H21_REL = "docs/hardware/h2/h2_1_hall_chamber_magnet/h2_1_hall_chamber_magnet_v1.json"
H22_REL = "docs/hardware/h2/h2_2_cathode_integration/h2_2_cathode_integration_v1.json"
H23_REL = "docs/hardware/h2/h2_3_gas_path_plenum/h2_3_gas_path_plenum_v1.json"
H24_REL = "docs/hardware/h2/h2_4_ppu_bus/h2_4_ppu_bus_v1.json"
H25_REL = "docs/hardware/h2/h2_5_thermal_network/h2_5_thermal_network_v1.json"
H26_REL = "docs/hardware/h2/h2_6_diagnostics_fixture/h2_6_diagnostics_fixture_v1.json"
H27_REL = "docs/hardware/h2/h2_7_mechanical_bom/h2_7_mechanical_bom_v1.json"
M16_REL = "docs/budgets/subsystem_maturity/subsystem_maturity_v2.json"
CATH_REL = "docs/evidence/cathode/cathode_evidence_v1.json"
S1A_REL = "docs/experiments/s1a_readiness/s1a_readiness_conditions_v1.json"
S1_REL = "docs/experiments/s1_readiness/s1_readiness_conditions_v1.json"

#: sha256 pins of IMMUTABLE inputs only (owner decisions, verified deliverables, historical artifacts). Mutable governance
#: (lane_registry_v1.json, trigger_registry_v1.json, trigger ledgers, runtime_state.json) is never pinned.
PINNED = {
    A9_REL: "74ef1a727c3656841ef115122c6d60865f7d2d93cfa29f7fb0081886484d2a1f",
    ANS_REL: "50e39a4deac7d4ada4710b2f641d717f1c4febd59366cbc04d8c66de6b4532b1",
    PACK_REL: "8736d88a64bf26bd06a332a68c2450a780f175fffafe5aca0625759133666976",
    A4_REL: "beec91f9eca3ca0257c5ee88dcd193c87481660b9368b65c6d10b3b3bdae23b4",
    A5_REL: "0554136751f5ffc7bd7f62c1c4723acce946ef4f523f43687b95710cc8ace621",
    A6_REL: "aaeb7c503c3791f81d4c589e8e25289befa6fcb3b16ce6f962b153715c883180",
    A7_REL: "dae69983d9aeeb4838d9ff973a5f824c973219f8cc528adfb12717c4bb92c925",
    HIST_JSON_REL: "84ba1c382dc609b3e83ad9803a57ba471dd892fd10a6a6149285701a45a65a28",
    HIST_MD_REL: "703e5a4e37904c2d6dfe1ca8a83c9de9818f33e7af8b75d416865e2db12f3c93",
    HIST_PY_REL: "00896a4a0d0fcb6345734e1ef2d39de974579f45500b5fe83204cbbc06606545",
    PIM_MD_REL: "afc639ef772b1d12664688c7f9bd3443598a024ad9a7e7270d29d55c89c9dcb0",
    PIM_PY_REL: "166ead5c33407dfc1e359c032ce3f0305ec3fbe7f3faeab8e2cb77ed619aeab5",
    PIM_SCHEMA_REL: "2470718e1decbde874d2362a997d1e2aaae54eb855d1ed179b930c3be6e7130e",
    LOCK1_JSON_REL: "7ce17e1f9101d0832a164e453fd757a813f5e1e77f689cfb661bdc920f453920",
    LOCK1_DRAFT_REL: "ece91920699c20358dc3e3d1348666460d6adf64addaa134a6fe11cdba499693",
    HWREQ_REL: "0b75be0a0ddc4888eb157c20e2b22dd4fce2a4bb94c4d6402cbe716ec73b0aa0",
    INS_REL: "7c6d37b00f38a44cded73d92d4366739eacbf013e73e98a7bfbc3fa5a5470d96",
    MS_REL: "55c11dc2d22fd92d95b498f72d60f2cdc0c62a45940da2446514049bd5130865",
    H21_REL: "49b9a45e9347b141bf8bd1122ffba3ae038c9f088041e4410525e4ab8695b82d",
    H22_REL: "8436008ac458d4e7467a9c7c9592d5312b3912b918d584ceaf3ac8cb2745a971",
    H23_REL: "f32b05bd03aad2a09a1d9b90ee5f9423e733e6ea4cb94814c92b500590d43a7b",
    H24_REL: "5c6623612ee9ec22899083201416f7b51a10a2d7e88456d372783ce2edde26ef",
    H25_REL: "68c5be61443d0ef1c7308c4aba265426137292dcf9363e57903e0a1f6c8bc083",
    H26_REL: "bc7d6b049067c6fbd5489bda32ee9c8c1af36508576db4619b08d2c4ec196a56",
    H27_REL: "d1813e153af37ebd45cb2ead964ead6c53c756d1a82f93ea89346a83168d0630",
    M16_REL: "a82b1acd118b26e89edd4fa467bec778fa410470cca5eb6f684e6553eadaf23c",
    CATH_REL: "050060204e443d5583c307becadaab55a9f213d406ff4454be856bca21249110",
    S1A_REL: "011808100ef38799668cb948324efa6492344d3b58ed3c436605ce5caf7025ac",
    S1_REL: "1d3388693191295f4c54ea9d1d38b36ca977193e0d9066aa40aac61776b27fd1",
}
PIN_CLASS = {
    A9_REL: "immutable owner decision (governing)", ANS_REL: "immutable owner answers (147 rows)",
    PACK_REL: "immutable owner decision pack (verbatim)", A4_REL: "immutable owner decision",
    A5_REL: "immutable owner decision", A6_REL: "immutable owner decision", A7_REL: "immutable owner decision",
    HIST_JSON_REL: "historical artifact (read-only; preserved byte-for-byte)",
    HIST_MD_REL: "historical artifact (read-only; preserved byte-for-byte)",
    HIST_PY_REL: "historical artifact (read-only; preserved byte-for-byte)",
    PIM_MD_REL: "historical artifact (read-only; preserved byte-for-byte)",
    PIM_PY_REL: "historical artifact (read-only; preserved byte-for-byte)",
    PIM_SCHEMA_REL: "historical artifact (read-only; preserved byte-for-byte)",
    LOCK1_JSON_REL: "historical artifact (read-only; preserved byte-for-byte)",
    LOCK1_DRAFT_REL: "historical artifact (read-only; preserved byte-for-byte)",
    HWREQ_REL: "verified deliverable (H-1/C-1 configuration items and planes)",
    INS_REL: "verified deliverable (instrumentation)", MS_REL: "verified deliverable (metrology spec)",
    H21_REL: "verified deliverable (H2-1)", H22_REL: "verified deliverable (H2-2)", H23_REL: "verified deliverable (H2-3)",
    H24_REL: "verified deliverable (H2-4)", H25_REL: "verified deliverable (H2-5)", H26_REL: "verified deliverable (H2-6)",
    H27_REL: "verified deliverable (H2-7)", M16_REL: "verified deliverable (M16 v2)",
    CATH_REL: "verified deliverable (cathode evidence)", S1A_REL: "verified deliverable (S1a readiness conditions)",
    S1_REL: "verified deliverable (S1 readiness conditions)",
}

REFERENCED_NOT_PINNED = [
    {"path": "docs/orchestration/lane_registry_v1.json", "why": "mutable governance: never pinned"},
    {"path": "docs/orchestration/trigger_registry_v1.json", "why": "mutable governance: never pinned"},
    {"path": "docs/orchestration/trigger_ledger_v2.jsonl", "why": "mutable governance: never pinned"},
    {"path": "docs/orchestration/runtime_state.json", "why": "mutable governance: never pinned"},
    {"path": "docs/validation/hall_transport_v2_prereg/", "why": "W5 held-out Hall-transport draft (DRAFT, mutable); referenced by path only"},
    {"path": "docs/architecture_comparison/power_boundary_a9/", "why": "parallel lane A9-02, not in the base; PENDING"},
    {"path": "abep_sim/bus_boundary_a9.py", "why": "parallel lane A9-02, not in the base; PENDING; never imported here"},
    {"path": "docs/interfaces/icp_neutralizer/", "why": "parallel lane A9-03, not in the base; PENDING"},
    {"path": "docs/experiments/hall_icp/uncertainty_budget/", "why": "parallel lane A9-04, not in the base; PENDING"},
    {"path": "docs/evidence/icp_neutralizer/", "why": "parallel lane A9-05, not in the base; PENDING"},
    {"path": "docs/experiments/hall_icp/validation_inputs/", "why": "parallel lane A9-05, not in the base; PENDING"},
    {"path": "docs/experiments/hall_icp/prereg/", "why": "future signed LOCK-1 / LOCK-2 location (row 16); not created here"},
]


class InputChanged(RuntimeError):
    """A pinned input is missing or its sha256 differs from the pin."""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_pins(root: Path, pins: dict) -> None:
    for rel, want in pins.items():
        p = root / rel
        if not p.is_file():
            raise InputChanged(f"pinned input missing: {rel}")
        got = sha256_file(p)
        if got != want:
            raise InputChanged(f"pinned input changed: {rel} sha256 {got} != pin {want}")


def _load(root: Path, rel: str):
    return json.loads((root / rel).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------------------------------------------------
# combinatorics: complete order-balanced sequence set for the two configurations
# ---------------------------------------------------------------------------------------------------------------------

def sequence_set(configs=CONFIGS) -> list:
    """All permutations of the configurations; for two configurations this is {AB, BA} (the Williams set for t = 2)."""
    return [list(p) for p in itertools.permutations(configs)]


def balance_report(seqs: list, configs=CONFIGS) -> dict:
    t = len(configs)
    pos = {c: [0] * t for c in configs}
    pairs = {(a, b): 0 for a in configs for b in configs if a != b}
    self_carry = 0
    for s in seqs:
        for i, c in enumerate(s):
            pos[c][i] += 1
        for a, b in zip(s, s[1:]):
            if a == b:
                self_carry += 1
            else:
                pairs[(a, b)] += 1
    return {
        "position_balanced": len({v for c in configs for v in pos[c]}) == 1,
        "first_order_carryover_balanced": len(set(pairs.values())) == 1,
        "no_self_carryover": self_carry == 0,
        "equals_all_permutations": sorted(map(tuple, seqs)) == sorted(itertools.permutations(configs)),
    }


def reference_carryover(seqs: list, ref_config: str) -> dict:
    """Predecessor counts when every block is bracketed by a reference installation of `ref_config` (row 40).

    Reported, not hidden: with a reference installation of one configuration the predecessor distribution of the scored
    installations is no longer symmetric (open owner question HIQ-01)."""
    pred, mod = {}, {}
    for s in seqs:
        prev, prev_mod = f"REF({ref_config})", ref_config
        for c in s:
            pred.setdefault(c, {}).setdefault(prev, 0)
            pred[c][prev] += 1
            mod.setdefault(c, {}).setdefault(prev_mod, 0)
            mod[c][prev_mod] += 1
            prev, prev_mod = c, c
    return {"by_installation": {c: dict(sorted(v.items())) for c, v in sorted(pred.items())},
            "by_module_on_carrier": {c: dict(sorted(v.items())) for c, v in sorted(mod.items())}}


def minimum_blocks(min_complete_sets: int, seqs: list) -> int:
    """Owner row 19: complete balanced replicate sets; minimum three complete engineering replicates."""
    if not isinstance(min_complete_sets, int) or min_complete_sets < 1:
        raise ValueError("min_complete_sets must be a positive integer")
    return min_complete_sets * len(seqs)


def assign_sequences(n_blocks: int, seed_hex: str, seqs: list) -> list:
    """Deterministic sequence-to-block assignment from a published seed (row 30).

    n_blocks must be a whole multiple of the sequence-set size (complete balanced replicate sets, row 19). Within each
    replicate set the order of the sequences is a permutation drawn by ranking sha256(seed || set index || sequence id).
    Used only with synthetic seeds by the test; the real seed is drawn at LOCK-2 after n is fixed."""
    if not re.fullmatch(r"[0-9a-f]{64}", seed_hex or ""):
        raise ValueError("seed_hex must be 64 lowercase hex characters (256 bit)")
    k = len(seqs)
    if n_blocks <= 0 or n_blocks % k != 0:
        raise ValueError(f"n_blocks={n_blocks} is not a whole multiple of the sequence-set size {k} (row 19)")
    out = []
    for r in range(n_blocks // k):
        keyed = []
        for j, s in enumerate(seqs):
            key = hashlib.sha256(f"{seed_hex}|set{r}|seq{j}".encode()).hexdigest()
            keyed.append((key, j))
        for _, j in sorted(keyed):
            out.append({"block": len(out) + 1, "replicate_set": r + 1, "sequence_id": f"SEQ-{chr(65 + j)}",
                        "order": list(seqs[j])})
    return out


# ---------------------------------------------------------------------------------------------------------------------
# content
# ---------------------------------------------------------------------------------------------------------------------

LABELS = {
    "AR_ENGINEERING_ONLY": "Ar data: engineering-only topology reproduction; never counts toward DRDO atmospheric requirements (row 36)",
    "SURROGATE_SHAKEDOWN": "surrogate hardware, non-scoring shakedown only (row 20)",
    "NO_ATOMIC_O": "N2 + O2 surrogate data: performance surrogate only, never atomic-O life proof (row 132)",
    "XE_REFERENCE": "bounded Xe health / reference check; never evidence for atmospheric-only performance (row 26)",
    "XE_AUGMENTED_PEAK": "bounded Xe peak point, only if the RFP permits; booked in the Xe ledger; never atmospheric evidence (rows 4, 26)",
    "PARTIAL_BOUNDARY": "P_bus basis while compressor bus draw / valve-outlet feed state are not measured or provided by ICD (row 22)",
    "NOT_TESTED": "scheduled slot of a stopped arm; order of the remaining slots kept; balance loss reported (row 39)",
}

STAGE_EVIDENCE_CLASSES = {
    "ENGINEERING_ONLY_NON_SCORING": "engineering information only; never enters a decision quantity or a LOCK-2 number",
    "METROLOGY_QUALIFICATION": "no-plasma Type B calibration and installation reproducibility; feeds LOCK-2 numbers",
    "QUALIFICATION_CAPABILITY": "Hall-on / module-on dispersion statistics on the actual hardware; feeds LOCK-2 numbers only (non-scoring)",
    "SCORE_BEARING_MEASURED": "in-house measurement on the actual Vyovrinda hardware (docs/EVIDENCE.md level 1), scored once by the frozen script",
    "HELD_OUT_VALIDATION_EVIDENCE": "custody-controlled readings pre-registered as held-out Hall-transport validation evidence",
    "FACILITY_EFFECT_CHARACTERIZATION": "background-pressure sensitivity; facility-mode evidence only",
    "LABELLED_XE": "XE_REFERENCE / XE_AUGMENTED_PEAK labelled readings, booked in the Xe ledger",
    "ABSOLUTE_DEMONSTRATION": "measured full-system gate demonstration inside the A9 spacecraft-DC propulsion boundary",
    "MATERIALS_LIFE_AO": "atomic-O materials / lifetime evidence from a dedicated AO source",
}


def stage_map() -> list:
    return [
        {"id": "HI-ENG", "order": 1, "name": "engineering shakedown",
         "what": "surrogate or development hardware may be used for shakedown of procedures, DAQ, RF chain, interlocks and fixtures; label SURROGATE_SHAKEDOWN (row 20); adjustable-anode development insert and alternative wall-sector inserts only here or before score-bearing freeze (rows 75, 135)",
         "entry": ["A9 decision recorded (pinned)", "facility and safety readiness for the gases used (O2 only after the named oxygen-safety owner and ASTM G93 Level C cleaning, row 107)"],
         "exit": ["shakedown log filed; no reading carried into any decision quantity or LOCK-2 value"],
         "gases": ["Ar", "N2", "Xe (bounded, booked)"], "configurations": list(CONFIGS) + ["surrogate hardware"],
         "hardware": "surrogate allowed (non-scoring only)",
         "can_produce": ["ENGINEERING_ONLY_NON_SCORING"],
         "cannot_produce": ["SCORE_BEARING_MEASURED", "QUALIFICATION_CAPABILITY", "HELD_OUT_VALIDATION_EVIDENCE"],
         "score_bearing": False},
        {"id": "HI-S1A", "order": 2, "name": "S1a analog - no-plasma metrology and module-exchange qualification",
         "what": "no Hall-on reading. Thrust-stand in-situ calibration (SI-traceable, pre/post block, drift and hysteresis, row 119) and the preregistered u_T acceptance test at 12 mN with maximum representative moving payload and all service lines installed (row 120) against the 1 % target (row 121); power channels per A9 bus slot; RF chain 13.56 MHz, 0-500 W forward, directional-coupler forward/reflected into a dummy load with calorimetric cross-check (row 72); MFC calibration (rows 96, 97, 98, 124, 126); cold-flow uniformity (row 101); RGA (row 127); C1<->ICP exchange checks: cold/tare, service-line parasitic, B(z) perturbation, electrical isolation and RF pickup (row 64); RR-HI-07 no-plasma leg (row 33); C1 standalone conditioning and ICP standalone (no Hall) ignition / forward-reflected / collector current may be run here as module bench checks, non-scoring",
         "entry": ["HI-ENG procedures available", "instrument set per docs/experiments/instrumentation/ plus ICP channels (" + PENDING_A9_03 + ")"],
         "exit": ["S1a-analog capability record: Type B uncertainties, noise floors, RF pickup bound, installation reproducibility per module, B(z) sensitivity with each module installed and energized (row 67)",
                  "u_T acceptance result at 12 mN filed; if 1 % is shown unattainable by metrology-only evidence, the target is revised before LOCK-2 (row 121)"],
         "gases": ["none (cold flow: N2, O2 after row 107 readiness, Xe, Ar)"], "configurations": list(CONFIGS),
         "hardware": "actual H-1 (D-09-A, row 20) for exchange checks; may run in a smaller domestic chamber (row 139)",
         "can_produce": ["METROLOGY_QUALIFICATION", "ENGINEERING_ONLY_NON_SCORING"],
         "cannot_produce": ["SCORE_BEARING_MEASURED", "HELD_OUT_VALIDATION_EVIDENCE"],
         "score_bearing": False},
        {"id": "HI-HOLDOUT-A", "order": 3, "name": "held-out partition rule frozen (validation custody, part A)",
         "what": "before ANY Hall-on reading on the actual H-1 (any gas), freeze which reading families are held out as Hall-transport validation evidence and the custody plan (rows 25, 35); see held_out_validation",
         "entry": ["HI-S1A exit"], "exit": ["partition rule and custody plan signed; no data reclassification after exposure (row 25)"],
         "gases": [], "configurations": [], "hardware": "-",
         "can_produce": [], "cannot_produce": ["any reading"], "score_bearing": False},
        {"id": "HI-AR", "order": 4, "name": "Ar topology reproduction (engineering-only)",
         "what": "reproduce the Takahashi/Watanabe-type Hall + downstream ICP topology on Ar on the actual H-1 with both modules (row 36; A9 evidence_sequence item 1); reproduction targets and any published analog operating points " + PENDING_A9_05 + "; label AR_ENGINEERING_ONLY",
         "entry": ["HI-HOLDOUT-A signed", "ICP module interfaces for this build available (" + PENDING_A9_03 + ")"],
         "exit": ["topology reproduced or not reproduced, recorded descriptively; Ar data never satisfy DRDO atmospheric requirements (row 36)"],
         "gases": ["Ar"], "configurations": list(CONFIGS), "hardware": "actual H-1 (D-09-A, row 20)",
         "can_produce": ["ENGINEERING_ONLY_NON_SCORING"],
         "cannot_produce": ["SCORE_BEARING_MEASURED", "ABSOLUTE_DEMONSTRATION", "HELD_OUT_VALIDATION_EVIDENCE"],
         "score_bearing": False},
        {"id": "HI-LOCK1", "order": 5, "name": "LOCK-1 (Hall->ICP)",
         "what": "owner signature of this framework's forms: decision-quantity definitions, hard-gate and Pareto forms, outcome rules, same-condition list, sequence set and assignment algorithm, seed-generation procedure (row 30), condition grid from W1 plus the anticipated knee (row 31), REF-COND, missing-data and data-quality rule forms, remount procedure, stop-rule forms (" + PENDING_A9_04 + ", row 13), the rules that compute every LOCK-2 number, frozen analysis/schedule scripts (sha256); filed under docs/experiments/hall_icp/prereg/ (row 16)",
         "entry": ["HI-S1A exit", "A9 bus boundary slots defined (" + PENDING_A9_02 + ")", "uncertainty budget forms (" + PENDING_A9_04 + ")"],
         "exit": ["LOCK-1 signed; any later change to a LOCK-1 item voids it"],
         "gases": [], "configurations": [], "hardware": "-",
         "can_produce": [], "cannot_produce": ["any data-derived number"], "score_bearing": False},
        {"id": "HI-HOLDOUT-B", "order": 6, "name": "held-out condition enumeration frozen (validation custody, part B)",
         "what": "enumerate the held-out conditions from the LOCK-1 grid before S1 (row 25), so every held-out condition is predicted before it is measured",
         "entry": ["HI-LOCK1 signed"], "exit": ["held-out enumeration frozen (sha256) before the first HI-S1 N2 reading"],
         "gases": [], "configurations": [], "hardware": "-",
         "can_produce": [], "cannot_produce": ["any reading"], "score_bearing": False},
        {"id": "HI-S1", "order": 7, "name": "S1 analog - module and Hall-on qualification on N2",
         "what": "first N2 Hall-on operation of the actual H-1 with each module: start sequences (C1 heater/keeper with pulsed keeper ignition 300-600 V class, row 89; ignition dwell cap and retries per row 93; ICP ignition; Hall ignition with ICP electrons, row 24), thermal time constants, I_d(t) oscillation band with the declared bandwidth (row 129), noise, stand drift, p_b behaviour; C1 spot-mode minimum-flow search at 0.005 mg/s steps with preregistered stopping criteria (row 92); breadboard discharge supply eta_d and transients measured before LOCK-2 (row 113); anode geometry and wall configuration already frozen (rows 75, 135)",
         "entry": ["HI-HOLDOUT-B frozen", "HI-LOCK1 signed", "downstream ICP interfaces frozen before score-bearing work (row 71; " + PENDING_A9_03 + ")"],
         "exit": ["S1-analog capability record released as dispersion statistics only (custody rule)"],
         "gases": ["N2", "Xe (C1 cathode flow, booked PHASE_TOTAL_FLOW, row 42)"], "configurations": list(CONFIGS),
         "hardware": "actual H-1 (D-09-A)",
         "can_produce": ["QUALIFICATION_CAPABILITY"], "cannot_produce": ["SCORE_BEARING_MEASURED"],
         "score_bearing": False},
        {"id": "HI-S1B", "order": 8, "name": "S1b analog - Hall-on re-mount series per module",
         "what": "K module re-installations x r readings at the REF-COND point for each configuration (RR-HI-06) and the Hall-on leg of RR-HI-07 (row 33); Faraday/ExB repeatability if eta_u enters any decision quantity (row 32); per-configuration u_inst",
         "entry": ["HI-S1 exit"], "exit": ["u_inst per configuration, drift, repeatability records filed for LOCK-2"],
         "gases": ["N2"], "configurations": list(CONFIGS), "hardware": "actual H-1 (D-09-A)",
         "can_produce": ["QUALIFICATION_CAPABILITY"], "cannot_produce": ["SCORE_BEARING_MEASURED"],
         "score_bearing": False},
        {"id": "HI-LOCK2", "order": 9, "name": "LOCK-2 (Hall->ICP)",
         "what": "records the LOCK-1 sha256 and inserts, without discretion, every number the LOCK-1 rules compute from S1a/S1/S1b: decision margins and effect sizes (row 18), block count n from measured uncertainty (row 19), stop-rule numbers, tolerances, B(z) field-change tolerance from measured H-1 sensitivity (row 67), T-PB-MAX once the knee and facility capability are known (row 23); draws the seed after n is fixed and publishes seed and hash before execution (row 30)",
         "entry": ["HI-S1B exit", "facility meets the registered requirements (row 139); foreign facility only with written approvals (row 136)"],
         "exit": ["LOCK-2 filed under docs/experiments/hall_icp/prereg/ (row 16)"],
         "gases": [], "configurations": [], "hardware": "-",
         "can_produce": [], "cannot_produce": ["any reading"], "score_bearing": False},
        {"id": "HI-CMP", "order": 10, "name": "score-bearing C1-vs-ICP comparison (atmospheric surrogates)",
         "what": "order-balanced blocks of complete replicate sets; each block = REF installation at REF-COND (own installation, row 40) plus one installation of each configuration; inside every installation pure N2 slices first and O2-bearing slices last (row 36), O2-bearing labelled NO_ATOMIC_O (row 132); bounded XE_REFERENCE checks and, only if the RFP permits, bounded XE_AUGMENTED_PEAK points, labelled and booked (rows 6, 26); raw dataset frozen by sha256 and scored once by the frozen script",
         "entry": ["HI-LOCK2 filed", "the realized schedule published with seed and hash (row 30)"],
         "exit": ["scored dataset and mechanical outcome record (or OPEN status with the next discriminating test, row 38) to the owner"],
         "gases": ["N2", "N2 + O2 (NO_ATOMIC_O)", "Xe (labelled, bounded)"], "configurations": list(CONFIGS),
         "hardware": "actual H-1 (D-09-A)",
         "can_produce": ["SCORE_BEARING_MEASURED", "HELD_OUT_VALIDATION_EVIDENCE", "LABELLED_XE"],
         "cannot_produce": ["MATERIALS_LIFE_AO", "AR_ENGINEERING_ONLY evidence"],
         "score_bearing": True},
        {"id": "HI-PB", "order": 11, "name": "facility-effect characterization at two elevated background-pressure levels",
         "what": "the comparison conditions repeated at two elevated p_b levels (row 23); 5e-5 Torr may be used for engineering characterization but never silently substituted for a stricter score-bearing requirement (row 23)",
         "entry": ["HI-LOCK2 filed (levels registered there)"], "exit": ["p_b sensitivity per configuration reported"],
         "gases": ["N2", "N2 + O2 (NO_ATOMIC_O)"], "configurations": list(CONFIGS), "hardware": "actual H-1 (D-09-A)",
         "can_produce": ["FACILITY_EFFECT_CHARACTERIZATION"], "cannot_produce": ["SCORE_BEARING_MEASURED at the registered p_b limit"],
         "score_bearing": False},
        {"id": "HI-ABS", "order": 12, "name": "absolute demonstration",
         "what": ">= 12 mN sustained atmospheric operation and demonstrated 25 mN system capability (row 4), both inside the same full spacecraft-DC propulsion boundary with P_bus < 1.5 kW (rows 27, 108), start-up transients included unless the official RFP permits otherwise (row 108); the ICP power inside the internal ~1.35 kW design allocation without nominally consuming the 1.35->1.5 kW margin (row 109); 25 mN need not use Xe, and any Xe use is booked (row 4); PARTIAL_BOUNDARY reported while compressor draw and valve-outlet feed state are unmeasured (row 22)",
         "entry": ["HI-LOCK2 filed", "A9 boundary with every active load in a bus slot (row 110; " + PENDING_A9_02 + ")"],
         "exit": ["gate demonstrations recorded per configuration with their boundary basis"],
         "gases": ["N2", "N2 + O2 (NO_ATOMIC_O)", "Xe only if booked and permitted"], "configurations": list(CONFIGS),
         "hardware": "actual H-1 (D-09-A)",
         "can_produce": ["ABSOLUTE_DEMONSTRATION", "SCORE_BEARING_MEASURED"], "cannot_produce": ["MATERIALS_LIFE_AO"],
         "score_bearing": True},
        {"id": "HI-AO", "order": 13, "name": "separate atomic-O materials / life programme",
         "what": "dedicated AO source for materials and lifetime qualification (row 132); ground-only heated-emitter exposure (row 99); keeper-material and anode coupons biased and floating (rows 94, 106); runs in parallel, never inside the comparison; no N2 + O2 test is called an AO-life test",
         "entry": ["AO source and coupon plan (outside this framework)"], "exit": ["materials / life evidence for the life burden reported in DQ-HI-LIFE"],
         "gases": ["atomic O (dedicated source)"], "configurations": ["coupons / components, not the comparison configurations"],
         "hardware": "coupons, ground-only emitters, components",
         "can_produce": ["MATERIALS_LIFE_AO"], "cannot_produce": ["SCORE_BEARING_MEASURED for the comparison"],
         "score_bearing": False},
    ]


def gate_deadlines() -> list:
    """Row 144: every blocker that can invalidate score-bearing work gets a stated latest decision point."""
    return [
        {"id": "GD-01", "blocker": "downstream ICP mechanical, RF, electrical, gas/plume and diagnostic interfaces frozen", "latest": "before HI-S1 (score-bearing Phase-1 analog work)", "source": "row 71", "owner_lane": PENDING_A9_03},
        {"id": "GD-02", "blocker": "anode position / geometry frozen", "latest": "before HI-S1", "source": "row 75", "owner_lane": "H-1 (H2-1)"},
        {"id": "GD-03", "blocker": "one design-representative wall configuration frozen", "latest": "before HI-S1", "source": "row 135", "owner_lane": "H-1 (H2-1)"},
        {"id": "GD-04", "blocker": "held-out Hall-transport validation subset preregistered", "latest": "HI-HOLDOUT-A before any Hall-on H-1 reading; HI-HOLDOUT-B before HI-S1", "source": "row 25", "owner_lane": "W5 (docs/validation/hall_transport_v2_prereg/)"},
        {"id": "GD-05", "blocker": "seed-generation procedure frozen", "latest": "LOCK-1", "source": "row 30", "owner_lane": "this framework"},
        {"id": "GD-06", "blocker": "condition grid frozen from W1 plus the anticipated knee", "latest": "LOCK-1", "source": "row 31", "owner_lane": "this framework"},
        {"id": "GD-07", "blocker": "stop rules defined", "latest": "LOCK-1 (forms); numbers at LOCK-2; always before any Hall->ICP score-bearing data", "source": "row 13", "owner_lane": PENDING_A9_04},
        {"id": "GD-08", "blocker": "effect-size / decision margins frozen", "latest": "LOCK-2 (value), LOCK-1 (form)", "source": "row 18", "owner_lane": PENDING_A9_04},
        {"id": "GD-09", "blocker": "block count n", "latest": "LOCK-2 from measured uncertainty", "source": "row 19", "owner_lane": PENDING_A9_04},
        {"id": "GD-10", "blocker": "1 % thrust-uncertainty target confirmed or revised on metrology-only evidence", "latest": "before LOCK-2 and before any score-bearing physics data", "source": "row 121", "owner_lane": "instrumentation / thrust stand"},
        {"id": "GD-11", "blocker": "allowable B(z) field-change tolerance from measured H-1 sensitivity with the ICP module installed/energized", "latest": "before score-bearing comparison (HI-LOCK2)", "source": "row 67", "owner_lane": "H-1 / MC-1"},
        {"id": "GD-12", "blocker": "T-PB-MAX", "latest": "after the low-flow knee and facility capability are known; at the latest HI-LOCK2", "source": "row 23", "owner_lane": "facility"},
        {"id": "GD-13", "blocker": "C1 ignition-dwell bound final value", "latest": "before score-bearing C1 testing (HI-LOCK2)", "source": "row 93", "owner_lane": "C1 (H2-2)"},
        {"id": "GD-14", "blocker": "breadboard discharge supply eta_d and transients measured", "latest": "before HI-LOCK2", "source": "row 113", "owner_lane": "PPU (H2-4)"},
        {"id": "GD-15", "blocker": "oxygen-safety owner named and ASTM G93 Level C cleaning", "latest": "before any O2 gas operation (S1a-analog cold flow included)", "source": "row 107", "owner_lane": "owner"},
        {"id": "GD-16", "blocker": "interpolation uncertainty (if any interpolation is used instead of measured midpoint / iso-power points)", "latest": "LOCK-1", "source": "row 15", "owner_lane": PENDING_A9_04},
        {"id": "GD-17", "blocker": "equivalent startup-state and thermal-state handling for C1 vs ICP", "latest": "LOCK-1", "source": "row 65", "owner_lane": "this framework"},
    ]


def configurations() -> dict:
    return {
        "ids": list(CONFIGS),
        "common_article": {
            "hall_head": "the actual Vyovrinda H-1 design-representative unit (D-09-A, row 20); stays bolted on the stand for the whole comparison (rows 17, 122)",
            "magnetic_circuit": "MC-1, electromagnet only (row 78); B(z) traceable to coil current and temperature with a hot-state reference sensor (rows 78, 82)",
            "feed": "same delivered atmospheric-surrogate feed state (SC-* same-condition list)",
            "settings": "same V_d and B settings (A9 governing decision 6)",
            "stand_and_metrology": "same torsional stand (row 115) and metrology in both configurations",
            "service_lines": "matched sham service lines in every compared configuration (row 133): the lines of the absent module are present as shams with matched routing; flexible RF coax with matched sham routing, no uncompensated hard RF line across the moving stage (row 117)",
            "carrier": "kinematic module carrier with repeatable datum control; H-1 is never unbolted (row 122); carrier datum and envelope " + PENDING_A9_03,
            "serialization": "a repaired or replaced H-1, C1 or ICP score-bearing module is a new serialized unit and needs a new reference / reinstallation sequence before score-bearing use (row 83)",
            "witness_items": "witness coupons / holders are non-functional exchangeable items while B(z), geometry and the reference stay inside the frozen tolerances (row 134)",
        },
        "configurations": [
            {"id": C1, "role": "reference / control and fallback (A9 control_fallback)",
             "module": "MOD-C1: conventional heated Xe-fed LaB6 hollow cathode C1 (rows 49, 88), external location (row 79), on the kinematic carrier",
             "configuration_defining_settings": ["heater power and heater-off transition per the cathode procedure (row 112)", "keeper current; pulsed keeper ignition 300-600 V class with recorded pulse energy (row 89)", "cathode Xe flow, all phases booked PHASE_TOTAL_FLOW (row 42)", "cathode-common / bleeder topology selectable and measured (row 91)"],
             "shams_present": ["RF coax (sham)", "ICP gas line (sham)", "collector / bias leads (sham)", "ICP telemetry harness (sham or terminated) - " + PENDING_A9_03],
             "not_a_flight_claim": "C1 is not automatically the final flight neutralizer (rows 49, 88)"},
            {"id": ICP, "role": "primary investigation hypothesis (A9 status OWNER_AUTHORIZED_INVESTIGATION_HYPOTHESIS_NOT_FLIGHT_BASELINE)",
             "module": "MOD-ICP: downstream 13.56 MHz unmagnetized RF inductively coupled plasma electron source / neutralizer (rows 69, 72), dielectric/body floating unless the validated circuit requires otherwise, electron-extraction collector biased and measured separately (row 70), on the kinematic carrier",
             "configuration_defining_settings": ["RF forward power (laboratory 0-500 W range, row 72) and matching state", "collector bias V / I (row 70)", "ICP gas species and flow - owner question HIQ-06 (A9 recorder flag row 46: unbooked)", "RF interlock state (row 62)"],
             "shams_present": ["C1 heater / keeper leads (sham)", "C1 Xe line (sham)", "C1 telemetry (sham or terminated) - " + PENDING_A9_03],
             "not_a_flight_claim": "an investigation hypothesis, not a flight baseline or a validated architecture (A9)"},
        ],
        "controlled_difference": "the downstream electron-source module on the kinematic carrier (and its configuration-defining settings) is the only controlled difference; everything in the same-condition list is matched or recorded",
        "topology_precedent": {
            "citation": "K. Takahashi, H. Watanabe, Y. Nakahama, K. Kikuchi, J. Electr. Propuls. 3, 18 (2024)",
            "doi": "10.1007/s44205-024-00081-2",
            "license": "CC BY-NC-ND 4.0",
            "evidence_class": "published analog (topology precedent only); no operating point is used here",
            "extraction": PENDING_A9_05,
        },
    }


def module_exchange() -> list:
    return [
        {"id": "RR-HI-01", "what": "one installation per configuration visit", "reuses": "RR-01",
         "rule": "every scored configuration visit and every reference installation is its own module installation on the kinematic carrier, so every configuration carries the same installation variance; H-1 stays bolted (rows 17, 122)"},
        {"id": "RR-HI-02", "what": "installation procedure (identical for MOD-C1 and MOD-ICP)", "reuses": "RR-02 (adapted: downstream module, no upstream IP-UP/IP-DN insertion)",
         "rule": "vent; exchange the module on the kinematic carrier at its datum; reconnect the live service lines and the matched shams along the registered routing (row 133); leak check; pump down; identical conditioning; startup-state and thermal-state handling per the LOCK-1 equivalence rule (row 65); settle; in-situ thrust calibration and tare pre-block (row 119); power-channel check per A9 bus slot; B(z) check with the module installed and energized (row 67); electrical isolation and RF pickup checks (row 64)",
         "interface_items": ["carrier datum and envelope", "downstream Hall-exhaust-to-ICP pressure / conductance interface (row 63)", "RF feedthrough and coax routing", "collector / bias leads", "module ID and telemetry harness (row 62)"],
         "interface_reference": PENDING_A9_03},
        {"id": "RR-HI-03", "what": "post-installation acceptance checks", "reuses": "RR-03",
         "rule": "each RR-HI-02 check compared with its acceptance limit before the first reading; a failed check means re-installation, logged; never a reading on a failed installation",
         "limit": MARGIN_NOT_SET, "limit_depends_on": "HI-S1A module-exchange reproducibility and HI-S1B u_inst per configuration"},
        {"id": "RR-HI-04", "what": "within-installation gas order and repeats", "reuses": "RR-04 (gas order replaced)",
         "rule": "inside every installation: pure N2 slices first, O2-bearing slices (NO_ATOMIC_O) last (row 36); bounded Xe reference per the bounded Xe plan (position: HIQ-03); the first N2 condition of the installation is repeated at the end of its N2 slices (PROPOSED)"},
        {"id": "RR-HI-05", "what": "reference installation per block", "reuses": "RR-05 (REF-MERGED option removed)",
         "rule": "REF-COND is taken in its own installation per block, never merged into an adjacent scored installation unless a later preregistered equivalence test supports it (row 40); reference readings are held under custody until W5 classifies them (row 35); module used for the reference: HIQ-01"},
        {"id": "RR-HI-06", "what": "S1b-analog re-mount series", "reuses": "RR-06",
         "rule": "K re-installations x r readings at REF-COND for EACH configuration give u_inst per configuration with K - 1 degrees of freedom; K and r are LOCK-1 items"},
        {"id": "RR-HI-07", "what": "C1 <-> ICP module-exchange remount check", "reuses": "RR-07 (adapted to C1 <-> ICP, row 33)",
         "rule": "before LOCK-2: MOD-C1 and MOD-ICP are each exchanged on the carrier (a) with no plasma at HI-S1A (cold/tare, service-line parasitic, B(z) perturbation, isolation, RF pickup; row 64) and (b) Hall-on at REF-COND at HI-S1B; H-1 remains fixed (row 33)"},
        {"id": "RR-HI-08", "what": "end-of-campaign check", "reuses": "RR-08",
         "rule": "a final reference installation after the last block; a failure flags every cross-installation class REMOUNT_CHECK_FAILED"},
        {"id": "RR-HI-09", "what": "campaign-level magnetic and witness records", "reuses": "RR-09",
         "rule": "B(z) maps with each module installed and energized before and after the campaign; witness items per INS-P-01..04 and row 134"},
    ]


def same_condition() -> dict:
    tol = MARGIN_NOT_SET
    return {
        "definition": "Readings of the two configurations are at the SAME CONDITION only if every SET_MATCHED / PROTOCOL_MATCHED variable matches its registered value within its matching tolerance and every MEASURED_COVARIATE is inside its admissibility tolerance. CONFIGURATION_DEFINING settings belong to the electron-source module and are pre-registered recipes; OUTCOME_NOT_MATCHED variables are responses and never matched away.",
        "roles": {"SET_MATCHED": "setpoint identical across configurations", "PROTOCOL_MATCHED": "same hardware / procedure, verified per installation",
                  "MEASURED_COVARIATE": "recorded, required inside a tolerance", "CONFIGURATION_DEFINING": "pre-registered per-configuration electron-source recipe, frozen at LOCK-1",
                  "OUTCOME_NOT_MATCHED": "a response of the configuration; recorded, never used to reject a reading"},
        "reuses": "historical same_condition roles (phase1_prereg_framework_v1.json#same_condition); CONFIGURATION_DEFINING added",
        "variables": [
            {"id": "SC-HI-MDOT", "variable": "anode (discharge) propellant mass flow and species", "role": "SET_MATCHED", "instruments": ["INS-05"], "tolerance": tol},
            {"id": "SC-HI-COMP", "variable": "O2 fraction of the surrogate in O2-bearing slices", "role": "SET_MATCHED", "instruments": ["INS-05", "INS-11"], "tolerance": tol},
            {"id": "SC-HI-VD", "variable": "discharge voltage V_d", "role": "SET_MATCHED", "instruments": ["INS-04"], "tolerance": tol},
            {"id": "SC-HI-B", "variable": "coil currents and B(z) (field change with the module installed/energized inside the row-67 tolerance)", "role": "SET_MATCHED", "instruments": ["INS-09", "INS-24"], "tolerance": tol},
            {"id": "SC-HI-HW", "variable": "H-1 serial unit, anode and wall configuration, stand, metrology chain", "role": "PROTOCOL_MATCHED", "instruments": ["INS-01", "INS-21"], "tolerance": "identity (serial numbers; row 83)"},
            {"id": "SC-HI-SVC", "variable": "service lines incl. matched shams, routing, moving payload", "role": "PROTOCOL_MATCHED", "instruments": ["INS-01"], "tolerance": tol},
            {"id": "SC-HI-START", "variable": "startup-state and thermal-state handling", "role": "PROTOCOL_MATCHED", "instruments": ["INS-17", "INS-18"], "tolerance": "LOCK-1 equivalence rule (row 65)"},
            {"id": "SC-HI-PFEED", "variable": "feed pressure at the valve outlet", "role": "MEASURED_COVARIATE", "instruments": ["INS-06"], "tolerance": tol},
            {"id": "SC-HI-TFEED", "variable": "feed temperature at the valve outlet", "role": "MEASURED_COVARIATE", "instruments": ["INS-07"], "tolerance": tol},
            {"id": "SC-HI-PB", "variable": "background pressure p_b (paired match between configurations)", "role": "MEASURED_COVARIATE", "instruments": ["INS-08"], "tolerance": tol},
            {"id": "SC-HI-SINK", "variable": "facility wall / cryopanel radiative sink temperature, measured per run", "role": "MEASURED_COVARIATE", "instruments": ["INS-17"], "tolerance": tol, "note": "300 K only as a planning case (row 131)"},
            {"id": "SC-HI-THERM", "variable": "thermal settling before the reading", "role": "MEASURED_COVARIATE", "instruments": ["INS-17"], "tolerance": tol},
            {"id": "SC-HI-SRC-C1", "variable": "C1 heater / keeper / cathode Xe flow recipe", "role": "CONFIGURATION_DEFINING", "instruments": ["INS-02", "INS-05", "INS-23"], "tolerance": "recipe frozen at LOCK-1"},
            {"id": "SC-HI-SRC-ICP", "variable": "ICP RF forward power, matching state, collector bias, ICP gas species / flow", "role": "CONFIGURATION_DEFINING", "instruments": ["INS-03", "INS-05", "ICP channels " + PENDING_A9_03], "tolerance": "recipe frozen at LOCK-1"},
            {"id": "SC-HI-OUT", "variable": "I_d, T, P_bus, electron current, coupling potential, oscillation band", "role": "OUTCOME_NOT_MATCHED", "instruments": ["INS-01", "INS-02", "INS-04", "INS-10"], "tolerance": "not applicable"},
        ],
    }


def _dq(id_, name, role, definition, units, chain, per_config=True, extra=None):
    d = {"id": id_, "name": name, "role": role, "operational_definition": definition, "units": units,
         "per_configuration": "measured for both configurations at the same conditions" if per_config else "external input (not a comparison measurement)",
         "measurement_chain": chain,
         "measurement_chain_uncertainty_owner": PENDING_A9_04,
         "margin": MARGIN_NOT_SET,
         "freeze_points": {"definition_form": "LOCK-1", "margin_value": "LOCK-2"}}
    if extra:
        d.update(extra)
    return d


def decision_quantities() -> list:
    return [
        _dq("DQ-HI-SUST", "Hall discharge sustainment with the configuration's electron source", "HARD_GATE",
            "Per reading: SUSTAINED iff the Hall discharge runs for the whole registered dwell with no uncommanded extinction and no automatic restart (extinction rule form from the historical THR-EXTINCTION form, parameters at LOCK-2). Per condition and configuration: SUSTAINED / NOT_SUSTAINED / SUSTAINMENT_MIXED over the blocks. An abort on a registered limit is 'not sustained within registered limits' with the limit recorded (row 41).",
            "class; I_d in A; dwell in s", ["INS-04", "INS-10", "INS-18", "INS-05", "INS-08", "INS-17"]),
        _dq("DQ-HI-ECAP", "electron-current capacity / neutralization current", "HARD_GATE",
            "Electron current delivered by the configuration's electron source to the discharge / beam at the reading, compared with the Hall current demand at the same condition (row 145: electron extraction current, Hall current demand, neutralization margin); for the ICP including the separately measured collector current and bias (row 70). The gate form (e.g. delivered current covers the demand with a registered margin) is frozen at LOCK-1; no margin value now.",
            "A (electron current, Hall current demand); dimensionless ratio", ["INS-04", "INS-02", "ICP collector V/I channel " + PENDING_A9_03, "C1 keeper / emission channels (HW-C1-05)"]),
        _dq("DQ-HI-VCPL", "coupling / neutralizer potential and beam neutralization", "HARD_GATE",
            "Potential of the electron source (C1 cathode common or ICP body / collector) relative to facility ground and spacecraft common during the reading, with plume neutralization evidence (row 145: collector potential, neutralization margin); floating ICP body potential recorded (row 70).",
            "V", ["INS-04", "ICP body / collector potential channels " + PENDING_A9_03, "INS-15", "INS-16 (where feasible)"]),
        _dq("DQ-HI-TABS", "absolute thrust compatibility", "HARD_GATE",
            ">= 12 mN sustained atmospheric operation and demonstrated 25 mN system capability (row 4) inside the same full-system boundary (row 27); measured axial thrust from the calibrated stand; the uncertainty allowance of the gate is a LOCK-2 number.",
            "mN", ["INS-01", "INS-05", "INS-06", "INS-07", "INS-08"]),
        _dq("DQ-HI-PBUS", "full bus-power compatibility", "HARD_GATE",
            "P_bus = all electrical power crossing the spacecraft-DC propulsion-system boundary for the configuration, every active load in its own bus slot (Hall discharge, per-coil magnet, ICP RF source/matching, ICP collector/bias, C1 heater/keeper, flow/valve/housekeeping, reserved DC; row 110) on the A9 boundary (" + PENDING_A9_02 + "; bus_power_boundary_v1 untouched, row 108); < 1.5 kW including start-up transients unless the official RFP explicitly permits a transient exception (row 108); PARTIAL_BOUNDARY basis reported until compressor draw and valve-outlet feed state are provided (row 22). No discharge-only or RF-generator-only power claim is sufficient (A9 governing decision 8).",
            "W (steady and transient peak)", ["INS-02", "INS-03", "INS-18"]),
        _dq("DQ-HI-PALLOC", "ICP power inside the internal design allocation", "HARD_GATE",
            "Full-system P_bus of " + ICP + " inside the internal ~1.35 kW design allocation without nominally consuming the 1.35->1.5 kW margin (row 109).",
            "W", ["INS-02", "INS-03"], extra={"applies_to": [ICP]}),
        _dq("DQ-HI-STAB", "stability / oscillation", "HARD_GATE",
            "I_d(t) oscillation class over the dwell from the exploratory chain to ~60 MHz or the declared measured bandwidth with its transfer function (row 129); the class threshold form at LOCK-1, numbers at LOCK-2 from the HI-S1 band.",
            "A (band), Hz, class", ["INS-04", "INS-10", "INS-18"]),
        _dq("DQ-HI-SAFE", "safety / operating-limit gate", "HARD_GATE",
            "No registered safety limit exceeded during the reading: RF interlock and reflected power (row 62), temperatures with >= 50 K margin below validated continuous-use limits (row 86), isolation / arcing, collector bias limits, C1 poisoning protection (HW-C1-03); any limit hit is recorded with the exact limit and state (row 41).",
            "class; W; K; V", ["INS-03", "INS-17", "INS-21", "INS-23", "INS-24", "RF interlock channel " + PENDING_A9_03]),
        _dq("DQ-HI-IGN", "ignition / start / restart", "HARD_GATE",
            "Per start: attempts and outcome for C1 ignition (dwell cap and retries of row 93), ICP ignition, Hall ignition with ICP electrons, restart success and cycle count (row 24); each classified per the preregistration, never hidden as a setup event.",
            "count; s; class", ["INS-10", "INS-04", "INS-03", "INS-05", "INS-18"]),
        _dq("DQ-HI-DXE", "Xe burden relative to C1 (dXe)", "PARETO_REPORTED",
            "Xe mass per operating hour and per start of each configuration at the same condition, booked PHASE_TOTAL_FLOW (row 42) including purge, preheat, ignition, keeper, transition and fallback; ICP gas feed booked by species (HIQ-06, A9 recorder flag row 46); dXe = ICP minus C1.",
            "mg/s; mg per start; kg per mission case", ["INS-05", "INS-18"]),
        _dq("DQ-HI-DPBUS", "bus-power difference relative to C1 (dP_bus)", "PARETO_REPORTED",
            "P_bus(ICP) minus P_bus(C1) at the same condition and in the same block, both on the A9 boundary.",
            "W", ["INS-02", "INS-03"]),
        _dq("DQ-HI-TPBUS", "thrust per bus power and its paired ratio", "PARETO_REPORTED",
            "T/P_bus per configuration and the paired ratio (T/P_bus)_ICP / (T/P_bus)_C1 at the same condition and block, reported with its interval; never a scalar selection unless preregistered (row 37); undefined where either configuration is not sustained.",
            "mN/kW; dimensionless", ["INS-01", "INS-02", "INS-03"]),
        _dq("DQ-HI-DMASS", "mass difference relative to C1 (dmass)", "PARETO_REPORTED",
            "Module, RF generator / matching / feedthrough, collector/bias hardware and Xe hardware mass differences from the A9 mass BOM (row 59), against the < 40 kg wet gate (row 5).",
            "kg", ["mass BOM " + PENDING_A9_06], per_config=False),
        _dq("DQ-HI-RESTART", "restart burden", "PARETO_REPORTED",
            "Per restart: energy, gas (by species) and time to sustained discharge, success fraction and cycle count per configuration (rows 24, 46).",
            "J; mg; s; count", ["INS-02", "INS-05", "INS-10", "INS-18"]),
        _dq("DQ-HI-LIFE", "life burden", "PARETO_REPORTED",
            "Life-limiting evidence per electron source: C1 on the 15,000 h basis (row 46); ICP-neutralizer lifetime / cycle requirement (row 46) from erosion witnesses and the separate AO programme (row 132); never extrapolated from an unadmitted Hall closure (INS-P-11).",
            "h; cycles; class", ["INS-19", "INS-20", "INS-23", "HI-AO programme"], per_config=False),
        _dq("DQ-HI-KNEE", "sustainment knee and envelope width per configuration", "DESCRIPTIVE_OUTPUT",
            "Low-flow sustainment knee location for each configuration as an OUTPUT (row 31), from down and up flow scans over the LOCK-1 grid; envelope width reported.",
            "mg/s", ["INS-05", "INS-04", "INS-10"]),
        _dq("DQ-HI-ETAU", "utilization / beam current (conditional)", "CONDITIONAL",
            "Used in a gate or Pareto quantity only if pre-registered at LOCK-1; then Faraday / ExB repeatability at HI-S1B is mandatory (row 32); otherwise descriptive only and not gating.",
            "dimensionless; A", ["INS-13", "INS-15"]),
    ]


def decision_topology() -> dict:
    hard = [d["id"] for d in decision_quantities() if d["role"] == "HARD_GATE"]
    pareto = [d["id"] for d in decision_quantities() if d["role"] == "PARETO_REPORTED"]
    return {
        "outcomes": list(OUTCOMES),
        "statuses": [STATUS_OPEN, "NOT_EVALUATED"],
        "open_is_status_not_outcome": "OPEN is a status, not an outcome; if evidence cannot decide, report unresolved and identify the next discriminating test (row 38)",
        "hard_gates": hard,
        "pareto_reported": pareto,
        "net_benefit_form": "NET_BENEFIT = hard gates first, then a Pareto report of dXe, dP_bus, dmass, T/P_bus, restart and life burden relative to C1; no weighted scalar and no single-scalar selection unless preregistered at LOCK-1 (row 37)",
        "definitions": {
            "PASS_GATES(X)": "configuration X meets every hard gate (" + ", ".join(hard) + ") at every required-envelope condition, each classification RESOLVED (DQ-HI-PALLOC applies to " + ICP + " only)",
            "FAILS_GATES(X)": "at least one hard gate of X is RESOLVED as failed at a required condition",
            "PARETO_REPORT": "for configurations passing the gates, each Pareto quantity with its interval relative to C1; relation classes NO_WORSE_ON_ALL(ICP) / NO_WORSE_ON_ALL(C1) / TRADE_OFF / UNRESOLVED are descriptive, never a ranking",
        },
        "rules": [
            {"outcome": ICP, "condition": "PASS_GATES(" + ICP + ")", "attached": "PARETO_REPORT (mandatory) relative to " + C1, "meaning": "the downstream ICP neutralizer met every hard gate in this campaign; C1 remains the reference / fallback until the ICP also demonstrates restart and life (A9 control_fallback); not a flight baseline, not a selection"},
            {"outcome": C1, "condition": "FAILS_GATES(" + ICP + ") AND PASS_GATES(" + C1 + ")", "attached": "the failing ICP gates and their limits", "meaning": "the conventional C1 reference stays the reference / fallback; the ICP failure mode is reported"},
            {"outcome": "NO_VIABLE_CASE", "condition": "FAILS_GATES(" + ICP + ") AND FAILS_GATES(" + C1 + ")", "attached": "failing gates per configuration", "meaning": "no configuration met the full-system gates; no case is forced to pass"},
        ],
        "status_rule": "if any classification needed by the rules is UNRESOLVED, SUSTAINMENT_MIXED, NOT_SCOREABLE_FACILITY, NOT_TESTED or missing, the decision status is OPEN (never NO_VIABLE_CASE by default) and the next discriminating test is named (row 38)",
        "no_winner": "the framework never declares a winner and never ranks configurations; outcomes are pre-registered classifications handed to the owner",
        "current_status": "NOT_EVALUATED - no Hall->ICP data exist; this framework evaluates nothing and prefers no configuration",
        "external_inputs": {"mass": "A9 mass BOM (" + PENDING_A9_06 + ")", "life": "HI-AO programme and life evidence (INS-P-10, INS-P-11)", "boundary": PENDING_A9_02},
    }


def execution_design(seqs, bal, refc, min_blocks) -> dict:
    return {
        "unit": "block = reference installation at REF-COND (own installation, row 40) + one installation of each configuration in the order of the block's sequence, each visiting the block's full condition set once",
        "scheme": "complete order-balanced replicate sets: for two configurations the Williams set (REF-WILLIAMS1949, cited from the historical framework) is both orders {AB, BA}; one replicate set = one block of each sequence (rows 19, 29)",
        "sequences": [{"id": f"SEQ-{chr(65 + i)}", "order": s} for i, s in enumerate(seqs)],
        "balance_checked_by_script": bal,
        "reference_predecessor_counts_with_reference_module_" + C1: refc,
        "reference_asymmetry_note": "per installation the predecessors are balanced, but counted by the module on the carrier the configuration that does not carry the reference is always preceded by the reference module while the reference configuration is preceded by itself once and by the other module once per replicate set (by_module_on_carrier); reported, not hidden (HIQ-01)",
        "min_complete_replicate_sets": {"value": 3, "source": "row 19", "evidence_class": "owner-allocation", "interpretation": "PROPOSED: one 'complete engineering replicate' = one complete balanced replicate set (HIQ-02)"},
        "min_blocks_if_interpretation_accepted": {"value": min_blocks, "derivation": "3 complete replicate sets x 2 sequences (computed by minimum_blocks())", "evidence_class": "model-derived"},
        "final_n": "LOCK-2 from measured uncertainty; whole multiple of the sequence-set size (row 19); assign_sequences() raises otherwise",
        "seed_procedure_frozen_at_lock1": [
            "the seed is drawn only at LOCK-2, after n is fixed (row 30)",
            "PROPOSED procedure: 256-bit seed from an operating-system CSPRNG by the custodian, in the presence of a second signatory; recorded as 64 lowercase hex characters",
            "the realized schedule = assign_sequences(n, seed, sequence set) of the LOCK-1-frozen script (sha256 recorded at LOCK-1)",
            "seed, sha256(seed) and sha256 of the realized schedule JSON published in the LOCK-2 file before the first score-bearing reading (row 30)",
        ],
        "condition_grid": "frozen at LOCK-1 from W1 plus the anticipated knee; the knee is an output per configuration (row 31); flow range covers ~0.38 to ~3.2 mg/s characterization with nominal sizing near ~1.3 mg/s (row 73)",
        "interpolation": "measured midpoint / iso-power points preferred over interpolation; any interpolation uncertainty preregistered (row 15)",
        "stopped_arm": "if an arm / configuration stops (stop rules " + PENDING_A9_04 + "), its scheduled slots become NOT_TESTED, all remaining order is kept, and the balance loss is reported (row 39)",
        "reference_checks": "reference checks remain reference checks, not a substitute for balancing (row 29)",
        "protocol_basis": "one reconciled protocol basis; no competing protocol definitions against the same score-bearing campaign (row 21)",
        "block_template": [
            {"slot": "REF-OPEN", "configuration": "REF-COND reference installation (module: HIQ-01)", "scored_for_decision": False},
            {"slot": "POSITION-1", "configuration": "sequence position 1", "scored_for_decision": True},
            {"slot": "POSITION-2", "configuration": "sequence position 2", "scored_for_decision": True},
            {"slot": "REF-CLOSE", "configuration": "REF-COND reference installation; becomes the next block's REF-OPEN", "scored_for_decision": False},
        ],
    }


def design_rules() -> list:
    return [
        {"id": "DR-01", "rule": "order-balanced design governs; reference checks are not a substitute for balancing", "source": "row 29"},
        {"id": "DR-02", "rule": "complete balanced replicate sets; minimum three complete engineering replicates; final n at LOCK-2 from measured uncertainty (R-03 analog)", "source": "row 19"},
        {"id": "DR-03", "rule": "seed-generation procedure frozen at LOCK-1; seed drawn at LOCK-2 after n is fixed; seed and hash published at LOCK-2 before execution", "source": "row 30"},
        {"id": "DR-04", "rule": "condition grid frozen at LOCK-1 from W1 plus the anticipated knee; knee location is an output per configuration", "source": "row 31"},
        {"id": "DR-05", "rule": "stopped arm -> NOT_TESTED slots, remaining order kept, balance loss reported", "source": "row 39"},
        {"id": "DR-06", "rule": "abort / limit hit = not sustained within registered limits, with the exact limit and state recorded", "source": "row 41"},
        {"id": "DR-07", "rule": "ignition / start attempts recorded, incl. ICP ignition, Hall ignition with ICP electrons, restart success and cycle count, classified per the preregistration", "source": "row 24"},
        {"id": "DR-08", "rule": "two elevated background-pressure levels for facility-effect characterization; T-PB-MAX frozen only after the knee and facility capability are known", "source": "row 23"},
        {"id": "DR-09", "rule": "held-out Hall-transport validation subset preregistered before S1; no reclassification after exposure", "source": "row 25"},
        {"id": "DR-10", "rule": "reference readings stay in held-out custody until W5 decides; no exposure-driven reclassification", "source": "row 35"},
        {"id": "DR-11", "rule": "if eta_u / beam current enters any decision quantity, Faraday / ExB repeatability at S1b is required", "source": "row 32"},
        {"id": "DR-12", "rule": "REF-COND in its own installation per block", "source": "row 40"},
        {"id": "DR-13", "rule": "within every installation: pure N2 first, O2-bearing last; Ar engineering-only topology replication first in the campaign", "source": "row 36"},
        {"id": "DR-14", "rule": "Xe used only as bounded, labelled reference / peak points, booked; never evidence for atmospheric-only performance", "source": "rows 6, 26, 42"},
        {"id": "DR-15", "rule": "no pre-ionizer dwell matching; equivalent startup-state and thermal-state handling for C1 vs ICP preregistered", "source": "row 65"},
        {"id": "DR-16", "rule": "matched sham service lines in every compared configuration", "source": "row 133"},
        {"id": "DR-17", "rule": "the actual Vyovrinda H-1 is the scored article; surrogate hardware only as non-scoring shakedown", "source": "row 20"},
        {"id": "DR-18", "rule": "thrust-stand calibration pre/post block with drift and hysteresis recorded", "source": "row 119"},
        {"id": "DR-19", "rule": "installed MFC zero check per block and a declared MFC body-temperature band", "source": "row 97"},
        {"id": "DR-20", "rule": "facility radiative sink temperature measured per run", "source": "row 131"},
        {"id": "DR-21", "rule": "no score-bearing data before LOCK-2; score-bearing data taken before LOCK-2 are excluded", "source": "historical locks.rule (phase1_prereg_framework_v1.json#locks)"},
        {"id": "DR-22", "rule": "no performance prediction from any Hall-transport closure (none admitted), the superseded 0-D Hall model or the withdrawn v1.2-v1.6 numbers; published analogs only with page / figure / table provenance and evidence class", "source": "CLAUDE.md gate 3 and superseded list; A9 evidence_anchor"},
        {"id": "DR-23", "rule": "no hypothesis surfaces from manufactured ASSUMED_SCREENING_VALUE inputs", "source": "row 146"},
    ]


def missing_data() -> list:
    return [
        {"id": "MD-HI-01", "reuses": "MD-01", "event": "uncommanded Hall extinction", "classification": "OBSERVATION (NOT_SUSTAINED)", "rule": "enters DQ-HI-SUST and DQ-HI-KNEE; never missing, never re-run for a sustained reading"},
        {"id": "MD-HI-02", "reuses": "MD-02", "event": "failed C1 ignition, failed ICP ignition, failed Hall ignition with ICP electrons, or failed restart", "classification": "OBSERVATION (NOT_IGNITED)", "rule": "enters DQ-HI-IGN and DQ-HI-RESTART (row 24); never missing"},
        {"id": "MD-HI-03", "reuses": "MD-03 (adapted)", "event": "discharge stays lit only with Xe added to the discharge feed or raised C1 Xe beyond the registered recipe", "classification": "OBSERVATION (XE_DEPENDENT)", "rule": "never counted as atmospheric sustainment; enters DQ-HI-SUST and DQ-HI-DXE"},
        {"id": "MD-HI-04", "reuses": "MD-04", "event": "abort on a registered limit (I_d, V_d, temperature, RF reflected power / interlock, collector bias, isolation)", "classification": "OBSERVATION (ABORTED_AT_LIMIT)", "rule": "not sustained within registered limits, with the exact limit and state recorded (row 41)"},
        {"id": "MD-HI-05", "reuses": "MD-05", "event": "facility-caused interruption (p_b excursion, pump fault, facility power loss)", "classification": "MISSING (NOT_SCOREABLE_FACILITY)", "rule": "not evidence for or against a configuration; re-run under MD-HI-08"},
        {"id": "MD-HI-06", "reuses": "MD-06", "event": "instrument failure or invalid calibration", "classification": "MISSING for the dependent decision quantities only (EXCLUDED_INSTRUMENT)", "rule": "missingness per decision quantity through its measurement chain; a missing A9 bus slot makes P_bus undefined (EXCLUDED_MISSING_BOUNDARY_COMPONENT)"},
        {"id": "MD-HI-07", "reuses": "MD-07", "event": "instrument failure correlated with a configuration (e.g. RF pickup on common diagnostics with the ICP energized)", "classification": "OBSERVATION (INSTRUMENT_INCOMPATIBLE_WITH_CONFIGURATION)", "rule": "counted per configuration and reported; never silently dropped"},
        {"id": "MD-HI-08", "reuses": "MD-08", "event": "re-run of a MISSING reading", "classification": "RE-RUN RULE", "rule": "only MD-HI-05 / MD-HI-06 readings are re-run, inside the same installation at its end where possible, else at the end of the block; the re-run cap is a LOCK-2 number; observations are never re-run", "re_run_cap": MARGIN_NOT_SET},
        {"id": "MD-HI-09", "reuses": "MD-09", "event": "lost configuration visit (incomplete block)", "classification": "MISSING (block-level)", "rule": "paired contrasts needing the lost visit are missing; balance loss reported; any replacement follows a LOCK-1 rule"},
        {"id": "MD-HI-10", "reuses": "none (new, row 39)", "event": "arm / configuration stopped by a stop rule", "classification": "NOT_TESTED (slot-level)", "rule": "all later slots of the arm are NOT_TESTED; the remaining order is kept; balance loss reported"},
        {"id": "MD-HI-11", "reuses": "none (new)", "event": "reading taken on hardware later found to be a different serial unit (repair / replacement)", "classification": "MISSING (UNREGISTERED_UNIT)", "rule": "a repaired / replaced unit is a new serialized unit needing a new reference / reinstallation sequence (row 83)"},
        {"id": "MD-HI-12", "reuses": "MD-10", "event": "any exclusion", "classification": "NO POST HOC EXCLUSION", "rule": "every exclusion follows mechanically from a pre-registered status evaluated by the frozen script on logged data with coded configuration labels; excluded readings are reported, never deleted"},
    ]


def data_quality() -> list:
    return [
        {"id": "DQR-HI-01", "reuses": "DQR-01", "check": "instrument health: self-test, zero and reference checks before and after every visit"},
        {"id": "DQR-HI-02", "reuses": "DQR-02", "check": "calibration currency (NABL / ISO-17025 primary references, rows 119, 126)"},
        {"id": "DQR-HI-03", "reuses": "DQR-03", "check": "drift against the REF-COND reference installations"},
        {"id": "DQR-HI-04", "reuses": "DQR-04", "check": "stand zero drift and in-situ calibration shift pre/post block (row 119)"},
        {"id": "DQR-HI-05", "reuses": "DQR-05", "check": "p_b below T-PB-MAX (frozen per row 23)"},
        {"id": "DQR-HI-06", "reuses": "DQR-06", "check": "paired background-pressure match between configurations"},
        {"id": "DQR-HI-07", "reuses": "DQR-07", "check": "thermal settling and measured facility sink temperature (row 131)"},
        {"id": "DQR-HI-08", "reuses": "DQR-08 (adapted)", "check": "RF pickup on common diagnostics with the ICP energized and with the matched sham, within the S1a-analog bound (row 64)"},
        {"id": "DQR-HI-09", "reuses": "DQR-09 (adapted)", "check": "bus-power completeness: every A9 bus slot of the configuration present (row 110; " + PENDING_A9_02 + ")"},
        {"id": "DQR-HI-10", "reuses": "DQR-10", "check": "common time base: channel skew within the synchronization limit"},
        {"id": "DQR-HI-11", "reuses": "DQR-11 (adapted)", "check": "B(z) with the downstream module installed and energized within the tolerance frozen from measured H-1 sensitivity (row 67)"},
        {"id": "DQR-HI-12", "reuses": "DQR-12", "check": "raw-data integrity: files hashed at acquisition, dataset frozen by sha256 before scoring, coded configuration labels"},
        {"id": "DQR-HI-13", "reuses": "none (new)", "check": "matched sham service lines present and routed as registered (row 133)"},
        {"id": "DQR-HI-14", "reuses": "none (new)", "check": "MFC installed zero per block and body temperature inside the declared band (row 97)"},
        {"id": "DQR-HI-15", "reuses": "none (new)", "check": "RF forward / reflected via the directional coupler inside the registered chain; calorimetry as independent cross-check (row 72)"},
    ]


def held_out_validation() -> dict:
    return {
        "w5_path": "docs/validation/hall_transport_v2_prereg/ (DRAFT; referenced by path only)",
        "rule": "part of the new data is preregistered, before any Hall-on H-1 reading, as held-out Hall-transport validation evidence; no reclassification after exposure (row 25); P5-N2 v1 stays INCONCLUSIVE and is unchanged",
        "proposed_families": [
            {"family": "HF-1", "data": f"{C1} pure-N2 flow scans (down and up) and grid conditions", "role": "HELD_OUT (PROPOSED; analog of historical F1/F2)"},
            {"family": "HF-2", "data": f"{ICP} pure-N2 readings", "role": "SEQUESTERED_FOR_FUTURE_PREREG (PROPOSED): the downstream ICP electron source changes the cathode boundary condition of any transport model; owner / W5 call (HIQ-07)"},
            {"family": "HF-3", "data": "O2-bearing slices (NO_ATOMIC_O)", "role": "SEQUESTERED_FOR_FUTURE_PREREG (no O/O2 chemistry admitted)"},
            {"family": "HF-4", "data": "REF-COND reference installations", "role": "HELD-OUT custody until W5 decides (row 35)"},
            {"family": "HF-5", "data": "HI-PB elevated-p_b readings", "role": "FACILITY evidence only"},
            {"family": "HF-6", "data": "HI-AR Ar readings", "role": "not validation evidence (engineering-only)"},
        ],
        "modes_never_crossed": "the C1-vs-ICP decision and Hall-transport validation are separate processes fed from one custody-controlled raw dataset; no model output enters a decision classification and no decision outcome changes a validation criterion",
    }


def items(floor: Fraction) -> list:
    """Section (a): parameters with value or TBD, units, basis, source, evidence class, status and freeze point."""
    T = "none (TBD)"
    return [
        {"id": "ITM-01", "name": "RF frequency of the ICP neutralizer", "value": 13.56, "units": "MHz", "basis": "owner answer", "source": "row 72", "evidence_class": "owner-allocation", "status": "OWNER_DECIDED", "freeze_point": "NOW"},
        {"id": "ITM-02", "name": "laboratory RF forward-power range (source and inline chain sizing)", "value": "0-500", "units": "W", "basis": "owner answer", "source": "row 72", "evidence_class": "owner-allocation", "status": "OWNER_DECIDED (initial sizing)", "freeze_point": "NOW"},
        {"id": "ITM-03", "name": "ICP magnetization (first build)", "value": "unmagnetized", "units": "-", "basis": "owner answer", "source": "row 69", "evidence_class": "owner-allocation", "status": "OWNER_DECIDED", "freeze_point": "NOW"},
        {"id": "ITM-04", "name": "sustained atmospheric thrust gate", "value": 12, "units": "mN", "basis": "owner engineering basis of the RFP '12-25 mN' (official RFP not yet obtained)", "source": "row 4", "evidence_class": "owner-allocation", "status": "OWNER_DECIDED (provisional until the official RFP)", "freeze_point": "NOW"},
        {"id": "ITM-05", "name": "system thrust capability gate", "value": 25, "units": "mN", "basis": "owner engineering basis", "source": "rows 4, 27", "evidence_class": "owner-allocation", "status": "OWNER_DECIDED (provisional until the official RFP)", "freeze_point": "NOW"},
        {"id": "ITM-06", "name": "full-system P_bus limit incl. start-up transients", "value": 1.5, "units": "kW", "basis": "owner engineering basis at the spacecraft-DC propulsion boundary", "source": "rows 27, 108", "evidence_class": "owner-allocation", "status": "OWNER_DECIDED (provisional until the official RFP)", "freeze_point": "NOW"},
        {"id": "ITM-07", "name": "internal design allocation that must contain the ICP power", "value": "~1.35", "units": "kW", "basis": "owner answer", "source": "row 109", "evidence_class": "owner-allocation", "status": "OWNER_DECIDED", "freeze_point": "NOW"},
        {"id": "ITM-08", "name": "absolute full-system floor at the 25 mN point", "value": 16.67, "units": "mN/kW", "basis": "owner-stated; ratio checked by this script", "source": "row 27", "evidence_class": "owner-allocation", "status": "OWNER_DECIDED", "freeze_point": "NOW",
         "check": {"computed": f"{floor.numerator}/{floor.denominator} mN/kW (25 mN / 1.5 kW)", "rounded_2dp": f"{float(floor):.2f}", "evidence_class": "model-derived"}},
        {"id": "ITM-09", "name": "system mass gate (wet, incl. Xe and tank)", "value": 40, "units": "kg", "basis": "owner conservative interpretation", "source": "row 5", "evidence_class": "owner-allocation", "status": "OWNER_DECIDED (provisional until the official RFP)", "freeze_point": "NOW"},
        {"id": "ITM-10", "name": "mission-life engineering basis", "value": 26280, "units": "h", "basis": "owner engineering basis", "source": "row 3", "evidence_class": "owner-allocation", "status": "OWNER_DECIDED (provisional until the official RFP)", "freeze_point": "NOW"},
        {"id": "ITM-11", "name": "firing-life requirement (C1 cathode term basis)", "value": 15000, "units": "h", "basis": "owner provisional hard requirement", "source": "rows 3, 46", "evidence_class": "owner-allocation", "status": "OWNER_DECIDED (provisional)", "freeze_point": "NOW"},
        {"id": "ITM-12", "name": "absolute thrust-uncertainty design / acceptance target", "value": 1, "units": "%", "basis": "owner answer; revised only before LOCK-2 on metrology-only evidence", "source": "row 121", "evidence_class": "owner-allocation", "status": "OWNER_DECIDED (target)", "freeze_point": "LOCK-2"},
        {"id": "ITM-13", "name": "S1a-analog u_T acceptance test thrust level", "value": 12, "units": "mN", "basis": "owner answer (max moving payload, all service lines)", "source": "row 120", "evidence_class": "owner-allocation", "status": "OWNER_DECIDED", "freeze_point": "NOW"},
        {"id": "ITM-14", "name": "thermal margin below validated continuous-use limits", "value": 50, "units": "K", "basis": "owner answer (plus 20 % heat-load design margin)", "source": "row 86", "evidence_class": "owner-allocation", "status": "OWNER_DECIDED", "freeze_point": "NOW"},
        {"id": "ITM-15", "name": "heat-load design margin", "value": 20, "units": "%", "basis": "owner answer", "source": "row 86", "evidence_class": "owner-allocation", "status": "OWNER_DECIDED", "freeze_point": "NOW"},
        {"id": "ITM-16", "name": "C1 spot-mode minimum-flow search step", "value": 0.005, "units": "mg/s", "basis": "owner answer (stopping criteria preregistered)", "source": "row 92", "evidence_class": "owner-allocation", "status": "OWNER_DECIDED", "freeze_point": "NOW"},
        {"id": "ITM-17", "name": "C1 ignition-dwell cap per attempt (preliminary protocol)", "value": 120, "units": "s", "basis": "owner answer; final bound frozen before score-bearing C1 testing", "source": "row 93", "evidence_class": "owner-allocation", "status": "OWNER_DECIDED (preliminary)", "freeze_point": "LOCK-2"},
        {"id": "ITM-18", "name": "C1 ignition retries allowed (preliminary protocol)", "value": 2, "units": "count", "basis": "owner answer", "source": "row 93", "evidence_class": "owner-allocation", "status": "OWNER_DECIDED (preliminary)", "freeze_point": "LOCK-2"},
        {"id": "ITM-19", "name": "C1 pulsed keeper ignition class", "value": "300-600", "units": "V", "basis": "owner answer (current-limited, interlocked, pulse energy recorded)", "source": "row 89", "evidence_class": "owner-allocation", "status": "OWNER_DECIDED", "freeze_point": "NOW"},
        {"id": "ITM-20", "name": "number of elevated background-pressure levels", "value": 2, "units": "count", "basis": "owner answer", "source": "row 23", "evidence_class": "owner-allocation", "status": "OWNER_DECIDED", "freeze_point": "NOW"},
        {"id": "ITM-21", "name": "minimum complete engineering replicates", "value": 3, "units": "count", "basis": "owner answer (interpretation HIQ-02)", "source": "row 19", "evidence_class": "owner-allocation", "status": "OWNER_DECIDED", "freeze_point": "NOW"},
        {"id": "ITM-22", "name": "V_d rating end for H-1, C1, supply, isolation and diagnostics", "value": 350, "units": "V", "basis": "owner answer", "source": "row 81", "evidence_class": "owner-allocation", "status": "OWNER_DECIDED", "freeze_point": "NOW"},
        {"id": "ITM-23", "name": "exploratory I_d(t) chain bandwidth", "value": "~60 (or declared measured bandwidth)", "units": "MHz", "basis": "owner answer", "source": "row 129", "evidence_class": "owner-allocation", "status": "OWNER_DECIDED", "freeze_point": "LOCK-1"},
        {"id": "ITM-24", "name": "thrust-stand moving payload design minimum", "value": 25, "units": "kg", "basis": "owner answer", "source": "row 116", "evidence_class": "owner-allocation", "status": "OWNER_DECIDED", "freeze_point": "NOW"},
        {"id": "ITM-25", "name": "low-flow cathode MFC resolution", "value": 0.0005, "units": "mg/s", "basis": "owner answer", "source": "row 98", "evidence_class": "owner-allocation", "status": "OWNER_DECIDED", "freeze_point": "NOW"},
        {"id": "ITM-26", "name": "C1 emitter temperature floor during O-bearing operation (experimental)", "value": 1843, "units": "K", "basis": "owner answer; not a demonstrated lifetime solution", "source": "row 95", "evidence_class": "owner-allocation", "status": "OWNER_DECIDED", "freeze_point": "NOW"},
        {"id": "ITM-27", "name": "delivered-flow characterization range and nominal sizing point", "value": "~0.38 to ~3.2 (nominal ~1.3)", "units": "mg/s", "basis": "owner answer; not flight-qualified until measured", "source": "row 73", "evidence_class": "owner-allocation", "status": "OWNER_DECIDED", "freeze_point": "NOW"},
        {"id": "ITM-28", "name": "gas isolator continuous rating / withstand qualification", "value": "350 continuous / ~1000 DC withstand", "units": "V", "basis": "owner answer", "source": "row 105", "evidence_class": "owner-allocation", "status": "OWNER_DECIDED", "freeze_point": "NOW"},
        {"id": "ITM-29", "name": "cold-flow uniformity S1a criterion", "value": "+-5 mean / 10 peak-to-peak", "units": "%", "basis": "owner answer", "source": "row 101", "evidence_class": "owner-allocation", "status": "OWNER_DECIDED", "freeze_point": "NOW"},
        {"id": "ITM-30", "name": "decision margins / effect sizes of every DQ-HI-*", "value": "TBD - requires S1a/S1/S1b measured uncertainty and the A9-04 budget", "units": "per DQ", "basis": "row 18", "source": PENDING_A9_04, "evidence_class": T, "status": "NOT SET", "freeze_point": "LOCK-2"},
        {"id": "ITM-31", "name": "block count n", "value": "TBD - requires measured uncertainty (S1b u_inst, u_T, u_P)", "units": "blocks", "basis": "row 19", "source": PENDING_A9_04, "evidence_class": T, "status": "NOT SET", "freeze_point": "LOCK-2"},
        {"id": "ITM-32", "name": "randomization seed", "value": "TBD - requires n fixed at LOCK-2", "units": "256-bit hex", "basis": "row 30", "source": "this framework (procedure)", "evidence_class": T, "status": "NOT SET", "freeze_point": "LOCK-2"},
        {"id": "ITM-33", "name": "stop-rule numbers", "value": "TBD - requires the A9-04 stop-rule forms and S1b capability", "units": "per rule", "basis": "row 13", "source": PENDING_A9_04, "evidence_class": T, "status": "NOT SET", "freeze_point": "LOCK-2"},
        {"id": "ITM-34", "name": "T-PB-MAX", "value": "TBD - requires the low-flow knee and facility capability", "units": "Torr", "basis": "row 23", "source": "facility (R5)", "evidence_class": T, "status": "NOT SET", "freeze_point": "LOCK-2"},
        {"id": "ITM-35", "name": "the two elevated p_b level values", "value": "TBD - requires facility capability", "units": "Torr", "basis": "row 23", "source": "facility (R5)", "evidence_class": T, "status": "NOT SET", "freeze_point": "LOCK-2"},
        {"id": "ITM-36", "name": "allowable B(z) field change with the ICP module installed / energized", "value": "TBD - requires measured H-1 sensitivity (HI-S1A / HI-S1)", "units": "G or %", "basis": "row 67", "source": "H-1 / MC-1", "evidence_class": T, "status": "NOT SET", "freeze_point": "LOCK-2"},
        {"id": "ITM-37", "name": "REF-COND (flow, V_d, B, gas)", "value": "TBD - requires W1 grid and the anticipated knee", "units": "mg/s; V; A", "basis": "row 40", "source": "this framework", "evidence_class": T, "status": "NOT SET", "freeze_point": "LOCK-1"},
        {"id": "ITM-38", "name": "condition grid", "value": "TBD - requires W1 plus the anticipated knee", "units": "mg/s; V; composition", "basis": "row 31", "source": "this framework", "evidence_class": T, "status": "NOT SET", "freeze_point": "LOCK-1"},
        {"id": "ITM-39", "name": "re-mount series K and readings per cycle r", "value": "TBD - requires the A9-04 budget", "units": "count", "basis": "RR-HI-06", "source": PENDING_A9_04, "evidence_class": T, "status": "NOT SET", "freeze_point": "LOCK-1"},
        {"id": "ITM-40", "name": "ICP gas feed species and flow", "value": "TBD - requires owner decision HIQ-06 and ICP ICD", "units": "species; mg/s", "basis": "A9 recorder flag (row 46)", "source": PENDING_A9_03, "evidence_class": T, "status": "OPEN (unbooked)", "freeze_point": "LOCK-1"},
        {"id": "ITM-41", "name": "published analog operating points for the Ar topology reproduction", "value": "TBD - requires the Takahashi 2024 full-text extraction with page / figure / table provenance", "units": "various", "basis": "row 7", "source": PENDING_A9_05, "evidence_class": T, "status": "PENDING", "freeze_point": "after-evidence"},
        {"id": "ITM-42", "name": "extinction window, dwell, sampling rate, oscillation class threshold", "value": "TBD - requires HI-S1 I_d band and thermal time constants", "units": "s; Hz; A", "basis": "historical lock2_converts", "source": "this framework", "evidence_class": T, "status": "NOT SET", "freeze_point": "LOCK-2"},
    ]


def interface_demands(ledger_path: str) -> list:
    return [
        {"id": "IF-HI-01", "direction": "from this lane to A9-02", "counterpart": PENDING_A9_02, "demand": "one bus slot per active load of each configuration: Hall discharge, per-coil magnet, ICP RF source/matching, ICP collector/bias, C1 heater and keeper (reference supplies), flow/valve/housekeeping, reserved DC; start-up transient metering; PARTIAL_BOUNDARY flag (rows 22, 108, 110)", "units": "W per slot (steady, transient peak)", "status": "PENDING"},
        {"id": "IF-HI-02", "direction": "from A9-02 to this lane", "counterpart": PENDING_A9_02, "demand": "slot ids used by DQ-HI-PBUS / DQ-HI-DPBUS / DQR-HI-09", "units": "-", "status": "PENDING"},
        {"id": "IF-HI-03", "direction": "from this lane to A9-03", "counterpart": PENDING_A9_03, "demand": "kinematic-carrier datum and repeatability item for downstream module exchange (row 122); module ID; matched-sham definitions (row 133); RF forward/reflected, RF interlock, collector/bias V/I, temperatures and telemetry channels (rows 62, 130); floating body with separately biased collector (row 70); Hall-exhaust-to-ICP pressure/conductance interface (row 63); ICP gas feed port", "units": "mm; W; V; A; K; Pa", "status": "PENDING"},
        {"id": "IF-HI-04", "direction": "from A9-03 to this lane", "counterpart": PENDING_A9_03, "demand": "frozen interface ids for RR-HI-02 and SC-HI-SRC-ICP; interfaces frozen before HI-S1 (row 71)", "units": "-", "status": "PENDING"},
        {"id": "IF-HI-05", "direction": "from this lane to A9-04", "counterpart": PENDING_A9_04, "demand": "decision-quantity list DQ-HI-* with measurement chains, for the uncertainty budget, stop-rule forms and the n computation (rows 12, 13, 18, 19)", "units": "per DQ", "status": "SUPPLIED (this deliverable)"},
        {"id": "IF-HI-06", "direction": "from A9-04 to this lane", "counterpart": PENDING_A9_04, "demand": "uncertainty per DQ-HI-*, stop-rule forms, the LOCK-2 computation rules for margins and n", "units": "per DQ", "status": "PENDING"},
        {"id": "IF-HI-07", "direction": "from A9-05 to this lane", "counterpart": PENDING_A9_05, "demand": "Takahashi 2024 extraction (topology precedent, Ar operating points with provenance) for HI-AR; validation-input list (row 145) mapped to DQ-HI-ECAP / DQ-HI-VCPL / DQ-HI-IGN", "units": "various", "status": "PENDING"},
        {"id": "IF-HI-08", "direction": "from this lane to A9-05", "counterpart": PENDING_A9_05, "demand": "which validation inputs become decision quantities and which stay descriptive", "units": "-", "status": "SUPPLIED (decision_quantities)"},
        {"id": "IF-HI-09", "direction": "from this lane to H2-6 / fixture", "counterpart": "docs/hardware/h2/h2_6_diagnostics_fixture/ (H26-40..H26-42 upstream-module concept) and " + PENDING_A9_07, "demand": "carrier re-derived for a DOWNSTREAM module (H2-6 concept was between IP-UP and IP-DN upstream); harp / slack-loop service routing with matched sham RF coax (row 117); >= 25 kg moving payload (row 116)", "units": "kg; N", "status": "OPEN (revision needed)"},
        {"id": "IF-HI-10", "direction": "from this lane to H2-1 / H2-2", "counterpart": "docs/hardware/h2/h2_1_hall_chamber_magnet/, docs/hardware/h2/h2_2_cathode_integration/ and " + PENDING_A9_07, "demand": "external C1 (row 79) replaces the preliminary L-CENTRAL choice; H-1 neutralizer-agnostic with a downstream / coaxial ICP interface", "units": "-", "status": "OPEN (revision needed)"},
        {"id": "IF-HI-11", "direction": "from this lane to H2-4", "counterpart": "docs/hardware/h2/h2_4_ppu_bus/ and " + PENDING_A9_07, "demand": "flight-representative breadboard discharge supply with eta_d and transients measured before LOCK-2 (row 113); 100 V internal bus (row 111)", "units": "W; V", "status": "OPEN"},
        {"id": "IF-HI-12", "direction": "from this lane to H2-5", "counterpart": "docs/hardware/h2/h2_5_thermal_network/ and " + PENDING_A9_07, "demand": ">= 50 K margin rule (row 86) as a DQ-HI-SAFE limit source; current 11.2 K BN wall margin not acceptable", "units": "K", "status": "OPEN (revision needed)"},
        {"id": "IF-HI-13", "direction": "from this lane to instrumentation", "counterpart": "docs/experiments/instrumentation/ (INS-01..INS-24)", "demand": "INS ids used in measurement chains; new ICP channels (RF forward/reflected via directional coupler, collector V/I, body potential, RF interlock) added by A9-03 / instrumentation", "units": "per channel", "status": "PARTIAL (existing INS ids verified; ICP channels PENDING)"},
        {"id": "IF-HI-14", "direction": "from this lane to the Xe ledger", "counterpart": ledger_path + " and " + PENDING_A9_08, "demand": "bookings: C1 PHASE_TOTAL_FLOW (row 42), XE_REFERENCE and XE_AUGMENTED_PEAK points (row 26), ICP gas if Xe (HIQ-06), 120 s x 2 ignition dwell bound (row 93)", "units": "mg/s; kg", "status": "OPEN"},
        {"id": "IF-HI-15", "direction": "from this lane to W5", "counterpart": "docs/validation/hall_transport_v2_prereg/", "demand": "held-out families HF-1..HF-6 (proposed) and the two-part freeze HI-HOLDOUT-A / -B", "units": "-", "status": "PROPOSED"},
        {"id": "IF-HI-16", "direction": "from H-1 to this lane", "counterpart": "docs/experiments/hardware/ (H-1, MC-1, C-1 configuration items)", "demand": "H-1 serial identity, anode and wall configuration frozen before HI-S1 (rows 75, 135), B(z) sensitivity for ITM-36", "units": "-; G/A", "status": "PENDING (hardware not built)"},
        {"id": "IF-HI-17", "direction": "from this lane to A9-06", "counterpart": PENDING_A9_06, "demand": "mass differences for DQ-HI-DMASS (ICP module, RF generator/matching/feedthrough, collector/bias hardware vs C1 and Xe hardware; row 59)", "units": "kg", "status": "PENDING"},
    ]


APPLIED = [
    (1, "RFP not yet obtained; no RFP interpretation frozen here"), (2, "tender id used for tracking only"),
    (3, "ITM-10, ITM-11 engineering bases"), (4, "ITM-04/05 and DQ-HI-TABS; HI-ABS; Xe for 25 mN only if booked"),
    (5, "ITM-09 wet mass gate; DQ-HI-DMASS"), (6, "bounded functional Xe mode: XE_REFERENCE / XE_AUGMENTED_PEAK labels (DR-14)"),
    (7, "ITM-41 analog points only after lawful acquisition and A9-05 extraction"),
    (8, "H3 inputs are quotation specifications only"),
    (12, "old D-01 budget not reused; new budget PENDING A9-04 (IF-HI-05/06)"),
    (14, "historical D-03-B not carried; no new work"), (13, "stop rules defined before score-bearing data (GD-07, ITM-33)"), (15, "interpolation rule (GD-16)"),
    (16, "not a lock; LOCK files later under docs/experiments/hall_icp/prereg/"),
    (17, "module-only swap on the carrier; H-1 fixed"), (18, "no numeric margins; MARGIN_NOT_SET literal"),
    (19, "replicate sets, minimum three, n at LOCK-2 (DR-02, execution_design)"), (20, "D-09-A actual H-1; surrogate only HI-ENG"),
    (21, "one reconciled protocol basis"), (22, "PARTIAL_BOUNDARY label"), (23, "two elevated p_b levels, T-PB-MAX timing (HI-PB, DR-08)"),
    (24, "ignition records incl. ICP (DQ-HI-IGN, DR-07)"), (25, "held-out subset before S1 (HI-HOLDOUT-A/B)"),
    (26, "bounded Xe reference and labelled peak points"), (27, "25 mN within P_bus < 1.5 kW; 16.67 mN/kW floor (ITM-08)"),
    (28, "outcomes hall_c1_reference / hall_icp_neutralizer / NO_VIABLE_CASE"), (29, "order balance governs (DR-01)"),
    (30, "seed procedure at LOCK-1, seed at LOCK-2 (DR-03)"), (31, "grid at LOCK-1, knee an output (DR-04, DQ-HI-KNEE)"),
    (32, "Faraday/ExB repeatability if eta_u gates (DQ-HI-ETAU)"), (33, "RR-HI-07 C1 <-> ICP"),
    (34, "own A9 stage map, not A5 'Phase 1'"), (35, "reference readings in held-out custody (DR-10)"),
    (36, "gas order Ar -> N2 -> O2-bearing (DR-13, RR-HI-04)"), (37, "NET_BENEFIT = hard gates + Pareto"),
    (38, "OPEN is a status; next discriminating test named"), (39, "NOT_TESTED slots (DR-05, MD-HI-10)"),
    (40, "REF-COND own installation per block (DR-12, RR-HI-05)"), (41, "limit abort classification (DR-06, MD-HI-04)"),
    (42, "PHASE_TOTAL_FLOW booking in DQ-HI-DXE"), (46, "C1 15,000 h basis; ICP lifetime / cycle requirement in DQ-HI-LIFE; ICP gas booking (HIQ-06)"),
    (49, "C1 = heated Xe-fed LaB6 reference"), (59, "dmass from the A9 BOM amendment"), (61, "no pre-ionizer common envelope reused"),
    (62, "ICP harness channels in IF-HI-03"), (63, "downstream pressure/conductance interface; mechanical sham for stand parasitics only"),
    (64, "C1 <-> ICP exchange checks at HI-S1A"), (65, "startup/thermal-state equivalence instead of dwell matching (DR-15)"),
    (67, "B(z) perturbation tolerance from measured sensitivity (ITM-36, DQR-HI-11)"), (69, "unmagnetized ICP (ITM-03)"),
    (70, "floating body, separately biased collector"), (71, "interfaces frozen before score-bearing work (GD-01)"),
    (72, "13.56 MHz, 0-500 W, coupler + calorimetric cross-check"), (73, "flow characterization range (ITM-27)"),
    (75, "anode frozen before S1 (GD-02)"), (78, "EM-only MC-1"), (79, "external C1; neutralizer-agnostic H-1"),
    (81, "350 V rating (ITM-22)"), (82, "hot-state B reference"), (83, "repaired/replaced unit = new serial unit (MD-HI-11)"),
    (86, ">= 50 K margin, 20 % heat load (ITM-14/15)"), (88, "C1 is reference/fallback only"), (89, "keeper ignition class (ITM-19)"),
    (91, "cathode-common topology selectable/measured"), (92, "0.005 mg/s step (ITM-16)"), (93, "120 s x 2 (ITM-17/18, GD-13)"),
    (94, "keeper coupons in HI-AO"), (95, "1843 K floor (ITM-26)"), (96, "flow class during S1a analog"), (97, "MFC zero per block (DR-19)"),
    (98, "MFC resolution (ITM-25)"), (99, "ground-only heated emitter in HI-AO"), (101, "cold-flow uniformity (ITM-29)"),
    (105, "isolator rating (ITM-28)"), (106, "anode coupons biased and floating in HI-AO"), (107, "O2 readiness gate (GD-15)"),
    (108, "P_bus incl. transients; new A9 boundary"), (109, "ICP inside ~1.35 kW (DQ-HI-PALLOC)"), (110, "every load gets a bus slot"),
    (111, "100 V internal bus (IF-HI-11)"), (112, "C1 heater sequencing in the C1 recipe"), (113, "breadboard supply eta_d before LOCK-2 (GD-14)"),
    (115, "torsional stand"), (116, ">= 25 kg payload (ITM-24)"), (117, "flexible RF coax with matched sham routing"),
    (119, "calibration pre/post block (DR-18)"), (120, "u_T test at 12 mN (ITM-13)"), (121, "1 % target (ITM-12, GD-10)"),
    (122, "kinematic carrier, H-1 bolted"), (124, "own-gas MFCs"), (126, "NABL/ISO-17025 primary references"), (127, "RGA ~200 amu"),
    (129, "I_d(t) bandwidth (ITM-23)"), (130, "ICP telemetry"), (131, "sink temperature measured per run (DR-20)"),
    (132, "NO_ATOMIC_O and separate HI-AO"), (133, "matched shams (DR-16)"), (134, "witness items non-functional"),
    (135, "wall configuration frozen before S1 (GD-03)"), (136, "foreign facility only with written approvals"),
    (139, "S1a analog in a smaller domestic chamber"), (140, "M16 row owners (functional roles)"), (142, "A9 lanes added to M16 mapping without rewriting H2 provenance"),
    (144, "gate deadlines GD-01..GD-17"), (145, "validation inputs mapped to DQ-HI-ECAP / VCPL / IGN"), (146, "no manufactured screening surfaces (DR-23)"),
]


def open_owner_questions() -> list:
    return [
        {"id": "HIQ-01", "question": "Which module occupies the REF-COND reference installation of each block?", "proposed_answer": f"{C1} (the control, analog of the historical HW-0 reference); the resulting predecessor asymmetry is computed and reported (execution_design); alternative: alternate the reference module between blocks", "status": "OPEN - owner call"},
        {"id": "HIQ-02", "question": "Does 'minimum three complete engineering replicates' (row 19) mean three complete balanced replicate sets (both sequences each, i.e. at least six blocks)?", "proposed_answer": "yes", "status": "OPEN"},
        {"id": "HIQ-03", "question": "Where inside an installation does the bounded Xe reference check sit relative to the pure-N2-first / O2-last order (row 36)?", "proposed_answer": "owner call; PROPOSED: at the start of the installation, before the N2 slices, so O2 exposure within the installation cannot bias the health reading", "status": "OPEN - owner call"},
        {"id": "HIQ-04", "question": "Must the held-out partition rule be frozen before the Ar topology reproduction (the first Hall-on reading on the actual H-1), with the condition enumeration completed after LOCK-1 but before S1?", "proposed_answer": "yes (two-part freeze HI-HOLDOUT-A / HI-HOLDOUT-B)", "status": "OPEN"},
        {"id": "HIQ-05", "question": "Should any Pareto relation be a necessary condition of the hall_icp_neutralizer outcome?", "proposed_answer": "no; Pareto report only, unless a condition is preregistered at LOCK-1 (row 37)", "status": "OPEN"},
        {"id": "HIQ-06", "question": "ICP neutralizer gas species and feed (Xe from the Xe ledger, Ar, or atmospheric surrogate) for the comparison?", "proposed_answer": "owner call; whatever is chosen is CONFIGURATION_DEFINING, frozen at LOCK-1 and fully booked (A9 recorder flag row 46)", "status": "OPEN - owner call"},
        {"id": "HIQ-07", "question": "Are hall_icp_neutralizer pure-N2 readings held out as Hall-transport validation evidence or sequestered for a future pre-registration?", "proposed_answer": "sequestered (the downstream ICP changes the electron-source boundary condition); W5 owner call", "status": "OPEN - owner call"},
        {"id": "HIQ-08", "question": "Is the Ar topology reproduction (HI-AR) run before LOCK-1 so its engineering findings can shape the ICP recipe frozen at LOCK-1?", "proposed_answer": "yes, after HI-HOLDOUT-A; Ar data never feed a LOCK-2 number or a decision quantity", "status": "OPEN"},
    ]


def historical_reuse(root: Path) -> dict:
    arts = [HIST_JSON_REL, HIST_MD_REL, HIST_PY_REL, PIM_MD_REL, PIM_PY_REL, PIM_SCHEMA_REL, LOCK1_JSON_REL, LOCK1_DRAFT_REL]
    return {
        "artifacts": [{"path": p, "sha256": sha256_file(root / p), "treatment": "read-only; preserved byte-for-byte; not edited"} for p in arts],
        "reused": [
            {"what": "gating order S1a -> LOCK-1 -> held-out freeze -> S1/S1b -> LOCK-2 -> score-bearing", "from": HIST_JSON_REL + "#gating_sequence", "how": "re-expressed as the A9 stage map with its own ids (HI-*); held-out freeze split into parts A and B"},
            {"what": "LOCK-1 fixes forms, LOCK-2 converts S1/S1b values without discretion", "from": HIST_JSON_REL + "#locks", "how": "HI-LOCK1 / HI-LOCK2"},
            {"what": "missing-data vocabulary MD-01..MD-10", "from": HIST_JSON_REL + "#missing_data", "how": "MD-HI-* with 'reuses' pointers; MD-HI-10/11 new"},
            {"what": "data-quality rules DQR-01..DQR-12", "from": HIST_JSON_REL + "#data_quality", "how": "DQR-HI-* with 'reuses' pointers; DQR-HI-13..15 new"},
            {"what": "same-condition roles", "from": HIST_JSON_REL + "#same_condition", "how": "roles kept; CONFIGURATION_DEFINING added"},
            {"what": "remount procedure RR-01..RR-09 incl. RR-07", "from": HIST_JSON_REL + "#repeatability_remount", "how": "RR-HI-* adapted to a downstream module on the kinematic carrier; RR-HI-07 = C1 <-> ICP (row 33)"},
            {"what": "Williams balance check and seeded assignment function pattern", "from": HIST_PY_REL, "how": "re-implemented for two configurations with a hash-ranked permutation per replicate set"},
            {"what": "OPEN as a status, NO_VIABLE_CASE never a default for missing evidence", "from": HIST_JSON_REL + "#case_logic", "how": "decision_topology.status_rule"},
            {"what": "held-out family structure F1..F7", "from": HIST_JSON_REL + "#relation_to_w5", "how": "HF-1..HF-6 (proposed)"},
        ],
        "not_reused": [
            {"what": "hall_only / rf_hall / ecr_hall topology, cases A / B / C and the evaluation precedence", "why": "superseded for the primary campaign (row 28; A9 supersession)"},
            {"what": "P1DQ-* decision quantities and R_arch as the discriminator", "why": "replaced by DQ-HI-* with hard gates + Pareto (row 37); the paired T/P_bus ratio is reported only"},
            {"what": "HW-0 flow-equivalent spacer PIM-0, PIM-RF, PIM-ECR, OPTION-DIVERTER and upstream IP-UP/IP-DN insertion", "why": "no upstream pre-ionizer; the module is a downstream electron source (rows 17, 63)"},
            {"what": "pre-ionizer dwell matching / time-matched Xe hold (PMQ-05)", "why": "superseded (row 65)"},
            {"what": "common module envelope sized to the largest occupant (PMQ-01) and L1-L5 harness (PMQ-02)", "why": "superseded (rows 61, 62)"},
            {"what": "matched pressure-drop blank module (PMQ-03)", "why": "superseded (row 63)"},
            {"what": "REF-MERGED option", "why": "rejected (row 40)"},
            {"what": "LOCK-1 decisions D-01..D-04 and the D-07 numeric delta", "why": "superseded (rows 12, 13, 14, 15, 18); preserved historically"},
        ],
    }


def m16_impact() -> list:
    note = "no M16 cell is edited here (M16 v2 is a verified deliverable); changes route through " + PENDING_A9_10
    return [
        {"row": 9, "key": "hall_chamber", "how": "H-1 stays bolted as the common scored article (D-09-A); anode / wall frozen before HI-S1 (GD-02, GD-03)", "note": note},
        {"row": 10, "key": "magnetic_circuit", "how": "B(z) perturbation scan with the downstream module installed/energized; tolerance from measured sensitivity (GD-11)", "note": note},
        {"row": 11, "key": "cathode", "how": "C1 becomes the reference/control module hall_c1_reference on the carrier, external location (row 79)", "note": note},
        {"row": 8, "key": "xe_metering", "how": "C1 steady and start flows, XE_REFERENCE / XE_AUGMENTED_PEAK bookings, ICP gas if Xe", "note": note},
        {"row": 12, "key": "ppu", "how": "bus slots for ICP RF/matching and collector/bias; breadboard discharge supply before LOCK-2 (GD-14)", "note": note},
        {"row": 13, "key": "thermal_control", "how": ">= 50 K margin enters DQ-HI-SAFE; sink temperature measured per run", "note": note},
        {"row": 14, "key": "control_fdir", "how": "RF interlock, restart and cycle counting (DQ-HI-IGN, DQ-HI-RESTART)", "note": note},
        {"row": 15, "key": "sensors_diagnostics", "how": "ICP channels (forward/reflected, collector V/I, body potential) join the measurement chains", "note": note},
        {"row": 16, "key": "mechanical_structural", "how": "kinematic carrier for a downstream module; matched shams; >= 25 kg payload", "note": note},
        {"row": 17, "key": "preionizer_interface", "how": "superseded for the primary line; an ICP-neutralizer row is needed (owner / A9-10 decision); historical row untouched", "note": note},
    ]


def h3_h4_inputs() -> dict:
    return {
        "h3_procurement_inputs_quotations_only": [
            "13.56 MHz RF generator sized for 0-500 W forward, matching network, directional coupler, RF feedthroughs, ICP chamber components (rows 8, 72)",
            "kinematic module carrier for a downstream module with repeatable datum (row 122; " + PENDING_A9_03 + ")",
            "matched sham service lines incl. flexible RF coax (rows 117, 133)",
            "torsional stand for >= 25 kg moving payload (rows 115, 116)",
            "collector / bias supply and ICP telemetry channels (rows 62, 110)",
            "no purchase order before H3 / A9 interfaces are frozen (row 8; A9 not_authorized)",
        ],
        "h4_test_inputs": [
            "stage map HI-ENG .. HI-AO with entry/exit conditions and producible evidence classes",
            "gate deadlines GD-01..GD-17",
            "block template, sequence set, seed procedure and remount procedure RR-HI-01..09",
            "missing-data MD-HI-* and data-quality DQR-HI-* rule forms",
        ],
    }


def build_doc(root: Path) -> dict:
    verify_pins(root, PINNED)
    answers = {r["row"]: r for r in _load(root, ANS_REL)["answers"]}
    a9 = _load(root, A9_REL)
    ins_ids = {x["id"] for x in _load(root, INS_REL)["instruments"]}
    m16 = {r["row"]: r["key"] for r in _load(root, M16_REL)["rows"]}
    ledger_path = _load(root, H27_REL)["xe_subsystem"]["linked_ledger"]["path"]

    seqs = sequence_set()
    bal = balance_report(seqs)
    if not all(bal.values()):
        raise AssertionError(f"sequence set not balanced: {bal}")
    refc = reference_carryover(seqs, C1)
    min_blocks = minimum_blocks(3, seqs)
    floor = Fraction(25) / Fraction(3, 2)

    dqs = decision_quantities()
    for d in dqs:
        for c in d["measurement_chain"]:
            if c.startswith("INS-") and c.split()[0] not in ins_ids:
                raise AssertionError(f"{d['id']}: unknown instrument {c}")
    for m in m16_impact():
        if m16.get(m["row"]) != m["key"]:
            raise AssertionError(f"M16 row mismatch {m}")

    applied = []
    if len({r for r, _ in APPLIED}) != len(APPLIED):
        raise AssertionError("duplicate owner-answer row in APPLIED")
    for row, how in sorted(APPLIED):
        if row not in answers:
            raise AssertionError(f"owner answer row {row} missing")
        r = answers[row]
        applied.append({"row": row, "covers_ids": r["covers_ids"], "owner_answer_verbatim": r["owner_answer_verbatim"],
                        "applied_as": how})

    doc = {
        "schema": "hall_icp_prereg_framework_v1",
        "id": "A9_01_hall_icp_prereg_framework_v1",
        "follow_on": "fo_a9_01_hall_icp_prereg_framework",
        "trigger": "T_A9_01_PREREG_FRAMEWORK",
        "owner_decision": {"path": A9_REL, "sha256": PINNED[A9_REL], "status": a9["status"]},
        "owner_answers": {"path": ANS_REL, "sha256": PINNED[ANS_REL], "verbatim_pack": {"path": PACK_REL, "sha256": PINNED[PACK_REL]}},
        "status": "PROPOSED_FRAMEWORK_NOT_A_LOCK",
        "not_locked": True, "score_bearing": False, "measurements_existing": False,
        "lock_file_location": "docs/experiments/hall_icp/prereg/ (future signed LOCK-1 / LOCK-2; row 16; not created here)",
        "base_commit": BASE_COMMIT,
        "generated_by": SCRIPT_REL,
        "companion_document": MD_REL,
        "test": TEST_REL,
        "literals": {"margin_not_set": MARGIN_NOT_SET, "tbd_form": "TBD - requires <what>",
                     "pending_form": "PENDING <lane path>"},
        "context": {
            "rfp": "DRDO TDF, tender 2026_DRDO_788433_1; official RFP not yet obtained (rows 1, 2); envelope 180-230 km, 12-25 mN, < 1.5 kW, < 40 kg, air + Xe, Hall preferred",
            "binding_immutable": ["A4-A7 owner decisions (pinned)", "P5-N2 v1 INCONCLUSIVE (permanent)", "credible Hall set EMPTY", "Bundle 1 NO_BASELINE_YET"],
            "no_performance_prediction": "no thrust, efficiency, discharge current, neutralizer electron current or plasma state is predicted from any Hall-transport closure, the superseded 0-D Hall model or the withdrawn v1.2-v1.6 numbers",
            "Xe ledger path (read from the pinned H2-7 linked_ledger)": ledger_path,
        },
        "pinned_inputs": [{"path": p, "sha256": s, "class": PIN_CLASS[p]} for p, s in PINNED.items()],
        "referenced_not_pinned": REFERENCED_NOT_PINNED,
        "terminology": {
            "campaign": "A9 Hall->ICP campaign; stage ids HI-*; the A5 'Phase 1' term is not stretched to this campaign (row 34)",
            "configurations": list(CONFIGS),
            "labels": LABELS,
            "stage_evidence_classes": STAGE_EVIDENCE_CLASSES,
        },
        "stage_map": stage_map(),
        "gate_deadlines": gate_deadlines(),
        "configurations": configurations(),
        "module_exchange": module_exchange(),
        "same_condition": same_condition(),
        "decision_topology": decision_topology(),
        "decision_quantities": dqs,
        "design_rules": design_rules(),
        "execution_design": execution_design(seqs, bal, refc, min_blocks),
        "missing_data": missing_data(),
        "data_quality": data_quality(),
        "held_out_validation": held_out_validation(),
        "items": items(floor),
        "interface_demands": interface_demands(ledger_path),
        "owner_answers_applied": applied,
        "open_owner_questions": open_owner_questions(),
        "historical_reuse": historical_reuse(root),
        "m16_impact": m16_impact(),
        "h3_h4_inputs": h3_h4_inputs(),
        "milestones": {
            "supports": "A (conditional selection) only as pre-registered topology; outputs no outcome now",
            "three_questions": {
                "conditional_selection_now": "nothing: no Hall->ICP data exist; Bundle 1 stays NO_BASELINE_YET",
                "blocks_physics_backed_selection": "empty credible Hall set; no H-1 / C1 / ICP hardware; A9-02..A9-05 pending; LOCK-1 not signed",
                "could_overturn": "RF pickup or B(z) perturbation that makes the swap non-neutral; ICP gas feed that changes the delivered feed state; S1b capability too poor to resolve the gates (status OPEN)",
            },
        },
        "compliance": [
            "not a lock; no numeric decision margin, effect size, stop-rule number or n frozen (row 18)",
            "owner-given values cited by row; all other values TBD or PENDING",
            "no performance prediction; no screening candidate or unadmitted closure used",
            "historical artifacts read-only, pinned by sha256",
            "mutable governance never pinned",
            "no winner declared; outcomes are pre-registered classifications",
        ],
    }
    return doc


# ---------------------------------------------------------------------------------------------------------------------
# markdown rendering
# ---------------------------------------------------------------------------------------------------------------------

def _cell(v) -> str:
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, list):
        return "; ".join(_cell(x) for x in v)
    if isinstance(v, dict):
        return "; ".join(f"{k}: {_cell(x)}" for k, x in v.items())
    return str(v).replace("|", "\\|").replace("\n", " ")


def _table(rows: list, cols: list) -> list:
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        out.append("| " + " | ".join(_cell(r.get(c, "")) for c in cols) + " |")
    return out


def render_md(doc: dict) -> str:
    L = [f"# Hall -> ICP pre-registration framework (A9-01)", "",
         f"Generated by `{doc['generated_by']}` from the authoritative `hall_icp_prereg_framework_v1.json`; `--check` "
         "reproduces both files byte for byte. **Status: " + doc["status"] + "** - this is not a lock; signed LOCK files "
         f"will live in {doc['lock_file_location']}.", "",
         f"Governing owner decision: `{doc['owner_decision']['path']}` (sha256 `{doc['owner_decision']['sha256']}`, "
         f"status `{doc['owner_decision']['status']}`). Owner answers: `{doc['owner_answers']['path']}` "
         f"(sha256 `{doc['owner_answers']['sha256']}`), cited by row.", "",
         "No performance is predicted. No decision margin, effect size, stop-rule number or block count is frozen here. "
         "No configuration is preferred and no winner is declared.", ""]
    L += ["## Context", ""] + [f"- **{k}**: {_cell(v)}" for k, v in doc["context"].items()] + [""]
    L += ["## Terminology and labels", "", doc["terminology"]["campaign"], ""]
    L += _table([{"label": k, "meaning": v} for k, v in doc["terminology"]["labels"].items()], ["label", "meaning"]) + [""]
    L += _table([{"evidence class": k, "meaning": v} for k, v in doc["terminology"]["stage_evidence_classes"].items()], ["evidence class", "meaning"]) + [""]
    L += ["## 1. Campaign stage map", ""]
    L += _table(doc["stage_map"], ["order", "id", "name", "what", "entry", "exit", "gases", "configurations", "hardware", "can_produce", "cannot_produce", "score_bearing"]) + [""]
    L += ["### Gate deadlines (row 144)", ""] + _table(doc["gate_deadlines"], ["id", "blocker", "latest", "source", "owner_lane"]) + [""]
    cfg = doc["configurations"]
    L += ["## 2. Configurations", ""] + [f"- **{k}**: {v}" for k, v in cfg["common_article"].items()] + [""]
    L += _table(cfg["configurations"], ["id", "role", "module", "configuration_defining_settings", "shams_present", "not_a_flight_claim"]) + [""]
    L += [f"Controlled difference: {cfg['controlled_difference']}", "", f"Topology precedent: {_cell(cfg['topology_precedent'])}", ""]
    L += ["### Module exchange and remount", ""] + _table(doc["module_exchange"], ["id", "what", "reuses", "rule"]) + [""]
    sc = doc["same_condition"]
    L += ["### Same condition", "", sc["definition"], ""] + _table(sc["variables"], ["id", "variable", "role", "instruments", "tolerance"]) + [""]
    dt = doc["decision_topology"]
    L += ["## 3. Decision topology", "", f"Outcomes: {', '.join('`'+o+'`' for o in dt['outcomes'])}. Statuses: {', '.join('`'+s+'`' for s in dt['statuses'])}.", "",
          dt["open_is_status_not_outcome"], "", dt["net_benefit_form"], ""]
    L += [f"- **{k}**: {v}" for k, v in dt["definitions"].items()] + [""]
    L += _table(dt["rules"], ["outcome", "condition", "attached", "meaning"]) + ["", dt["status_rule"], "", dt["no_winner"], "",
                                                                                f"Current status: {dt['current_status']}", ""]
    L += ["### Decision quantities", ""] + _table(doc["decision_quantities"], ["id", "name", "role", "operational_definition", "units", "measurement_chain", "measurement_chain_uncertainty_owner", "margin", "freeze_points"]) + [""]
    L += ["## 4. Design rules", ""] + _table(doc["design_rules"], ["id", "rule", "source"]) + [""]
    ed = doc["execution_design"]
    L += ["### Execution design", ""] + [f"- **{k}**: {_cell(v)}" for k, v in ed.items() if k != "block_template"] + [""]
    L += _table(ed["block_template"], ["slot", "configuration", "scored_for_decision"]) + [""]
    L += ["### Missing data", ""] + _table(doc["missing_data"], ["id", "reuses", "event", "classification", "rule"]) + [""]
    L += ["### Data quality", ""] + _table(doc["data_quality"], ["id", "reuses", "check"]) + [""]
    hv = doc["held_out_validation"]
    L += ["### Held-out validation", "", hv["rule"], ""] + _table(hv["proposed_families"], ["family", "data", "role"]) + ["", hv["modes_never_crossed"], ""]
    L += ["## (a) Items / parameters", ""] + _table(doc["items"], ["id", "name", "value", "units", "basis", "source", "evidence_class", "status", "freeze_point"]) + [""]
    L += ["## (b) Interface demands", ""] + _table(doc["interface_demands"], ["id", "direction", "counterpart", "demand", "units", "status"]) + [""]
    L += ["## (c) Owner answers applied", ""] + _table(doc["owner_answers_applied"], ["row", "covers_ids", "applied_as", "owner_answer_verbatim"]) + [""]
    L += ["## (d) Open owner questions", ""] + _table(doc["open_owner_questions"], ["id", "question", "proposed_answer", "status"]) + [""]
    hr = doc["historical_reuse"]
    L += ["## (e) Historical reuse", ""] + _table(hr["artifacts"], ["path", "sha256", "treatment"]) + [""]
    L += ["Reused:", ""] + _table(hr["reused"], ["what", "from", "how"]) + ["", "Deliberately not reused:", ""] + _table(hr["not_reused"], ["what", "why"]) + [""]
    L += ["## (f) M16 impact", ""] + _table(doc["m16_impact"], ["row", "key", "how", "note"]) + [""]
    h = doc["h3_h4_inputs"]
    L += ["## (g) H3 / H4 inputs", "", "H3 (quotations only):", ""] + [f"- {x}" for x in h["h3_procurement_inputs_quotations_only"]] + ["", "H4:", ""] + [f"- {x}" for x in h["h4_test_inputs"]] + [""]
    L += ["## Milestones", "", doc["milestones"]["supports"], ""] + [f"- **{k}**: {v}" for k, v in doc["milestones"]["three_questions"].items()] + [""]
    L += ["## Pinned inputs", ""] + _table(doc["pinned_inputs"], ["path", "sha256", "class"]) + [""]
    L += ["## Referenced, not pinned", ""] + _table(doc["referenced_not_pinned"], ["path", "why"]) + [""]
    L += ["## Compliance", ""] + [f"- {c}" for c in doc["compliance"]] + [""]
    return "\n".join(L)


def render(root: Path) -> tuple:
    doc = build_doc(root)
    js = json.dumps(doc, indent=1, ensure_ascii=False) + "\n"
    return js, render_md(doc)


def main(argv: list) -> int:
    js, md = render(ROOT)
    jp, mp = ROOT / JSON_REL, ROOT / MD_REL
    if "--check" in argv:
        ok = jp.is_file() and mp.is_file() and jp.read_text(encoding="utf-8") == js and mp.read_text(encoding="utf-8") == md
        print("OK" if ok else "MISMATCH: regenerate with build_hall_icp_prereg_framework.py")
        return 0 if ok else 1
    jp.write_text(js, encoding="utf-8")
    mp.write_text(md, encoding="utf-8")
    print(f"wrote {JSON_REL} and {MD_REL}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
