"""A9.19 / A9.20 flight-architecture rules as executable design-layer code (design + experiments lane).

Owner decisions implemented here (immutable records; the verbatim .md governs; companion-JSON and verbatim-md sha256
pinned in ``DECISIONS`` and checked by ``verify_decision_records``):

  A9.19 (docs/decisions/OD_2026_10_01_A9_19_ARCHITECTURE_XE_CONTINGENCY_OWNER_DECISION.md), verbatim:
        "One Hall accelerator. One RF/ICP electron-source/neutralizer. Two propellant supply modes. No conventional
        hollow cathode." Xenon is "just a contigency and emergency gas" (owner wording): Xe capability stays required
        (RFP-P17-05 'an extra input system to take care any problems on board unforeseen problems'; RFP-P18-08 two
        separate propellant tanks), but its ROLE is contingency / emergency (amends A9.15 on the role of Xe only).
        The thruster architecture is cathodeless / electrodeless for BOTH the atmospheric gases and xenon.
  A9.20 (docs/decisions/OD_2026_10_01_A9_20_C1_GROUND_ONLY_OWNER_DECISION.md): C1 (heated Xe-fed LaB6) is a
        GROUND-ONLY laboratory reference: it registers I_d,max,H1,Ar on H-1 independently of the ICP (A9.10 S3.5) and is
        the bench control in the C1-vs-ICP comparison; never flight hardware; never in the flight mass / power / Xe
        budgets.

Consequences enforced here (fail closed, refuse rather than repair):
  * FLIGHT_CONFIGURATIONS = ("hall_icp_neutralizer",) only. ``hall_c1_reference`` is REFUSED as a flight configuration
    and is accepted only under the explicit label GROUND_REFERENCE (``ground_reference``) where a comparison needs it.
  * The flight configuration has exactly one Hall accelerator, one RF/ICP electron source / neutralizer serving both
    supply modes, and two supply modes AIR_PRIMARY and XE_CONTINGENCY with separate tanks / paths.
  * No hollow-cathode element (hollow cathode, LaB6 / BaO emitter, cathode heater / keeper, C1 / C-1, AL-C1, the C1
    Xe branch) may appear in a flight configuration (``refuse_hollow_cathode_elements``).
  * The A9.1 ICP feed-gas baseline (G-REUSE primary, G-XE declared variant) is UNCHANGED.

Nothing here invents a number, answers an owner question, or declares PASS / SELECTED / WINNER / QUALIFIED.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Iterable, Mapping, Sequence

REPO = Path(__file__).resolve().parents[2]

DECISIONS = {
    "A9.19": {"md": "docs/decisions/OD_2026_10_01_A9_19_ARCHITECTURE_XE_CONTINGENCY_OWNER_DECISION.md",
              "md_sha256": "d3eae1d65f9b679a8538ce4a7c701a40a3f5d3b07d72baae944b685256931749",
              "json": "docs/decisions/OD_2026_10_01_A9_19_architecture_xe_contingency_owner_decision.json",
              "json_sha256": "20364847febc240d06779d26dbca0236059ab4471754df4452401eb0ed050b16",
              "decision_code": "A9_19_SINGLE_HALL_ICP_NEUTRALIZER_NO_HOLLOW_CATHODE_XE_CONTINGENCY"},
    "A9.20": {"md": "docs/decisions/OD_2026_10_01_A9_20_C1_GROUND_ONLY_OWNER_DECISION.md",
              "md_sha256": "2b90a7a7f851ac571791ea6ba2fbafac8cf69a086a4a3724e2f66196b6b4d60c",
              "json": "docs/decisions/OD_2026_10_01_A9_20_c1_ground_only_owner_decision.json",
              "json_sha256": "9b88e441b5c3454a20c4696897c525ef5818f0cfd9f32c7a3b4fa8e1a204dcc6",
              "decision_code": "C1_GROUND_ONLY_LABORATORY_REFERENCE"},
    # A9.15 is amended by A9.19 on the ROLE of Xe only (capability and two separate tanks / paths stay)
    "A9.15": {"md": "docs/decisions/OD_2026_10_01_A9_15_RFP_PROPELLANT_POLICY_OWNER_DECISION.md",
              "md_sha256": "edcf3019124084066501863ee314acc570e41f3b09757bcc8f8919b6295e3903",
              "json": "docs/decisions/OD_2026_10_01_A9_15_rfp_propellant_policy_owner_decision.json",
              "json_sha256": "a928e87fa37aa6ad875fa1505041f21ea145919ebb86286df0e34629c966e309",
              "decision_code": "A9_15_RFP_COMPLIANT_PROPELLANT_POLICY"},
}
RFP_REGISTRATION = "docs/requirements/rfp_official/rfp_registration_v1.json"
RFP_CLAUSES = {"xe_extra_input": "RFP-P17-05", "two_tanks": "RFP-P18-08"}
VERBATIM_A9_19 = ("One Hall accelerator.", "One RF/ICP electron-source/neutralizer.", "Two propellant supply modes.",
                  "No conventional hollow cathode.")


class ArchitectureRuleError(ValueError):
    """A request that A9.19 / A9.20 forbids (refused, never repaired)."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_decision_records(repo: Path = REPO) -> dict:
    """Re-hash every cited decision record (json and verbatim md); {decision: True/False}."""
    return {k: _sha256(Path(repo) / d["json"]) == d["json_sha256"] and _sha256(Path(repo) / d["md"]) == d["md_sha256"]
            for k, d in DECISIONS.items()}


def require_decision_records(repo: Path = REPO) -> None:
    bad = [k for k, ok in verify_decision_records(repo).items() if not ok]
    if bad:
        raise ArchitectureRuleError(f"REFUSED: pinned owner decision record(s) changed: {bad}")


def cite(*keys: str) -> list[dict]:
    return [{"decision": k, "md": DECISIONS[k]["md"], "md_sha256": DECISIONS[k]["md_sha256"],
             "json": DECISIONS[k]["json"], "json_sha256": DECISIONS[k]["json_sha256"],
             "decision_code": DECISIONS[k]["decision_code"]} for k in keys]


# ================================================================================================= architecture
FLIGHT_CONFIGURATION = "hall_icp_neutralizer"
FLIGHT_CONFIGURATIONS = (FLIGHT_CONFIGURATION,)
GROUND_REFERENCE_CONFIGURATION = "hall_c1_reference"
GROUND_REFERENCE_LABEL = "GROUND_REFERENCE"
GROUND_ONLY_LAB_EQUIPMENT = "GROUND_ONLY_LAB_EQUIPMENT"
C1_ROLE = {
    "status": GROUND_ONLY_LAB_EQUIPMENT,
    "uses": ["H-1 I_d,max,H1,Ar characterization (A9.10 S3.5, independent of the ICP)",
             "bench control in the C1-vs-ICP comparison"],
    "never": ["flight hardware", "flight mass budget", "flight power budget", "flight Xe budget",
              "flight fallback / candidate flight configuration"],
    "authority": "A9.20 (C1_GROUND_ONLY_LABORATORY_REFERENCE); A9.19 amends 'A9 C1 CONTROL_FALLBACK'",
}
SUPPLY_MODE_AIR = "AIR_PRIMARY"
SUPPLY_MODE_XE = "XE_CONTINGENCY"
SUPPLY_MODES = (SUPPLY_MODE_AIR, SUPPLY_MODE_XE)
XE_PATH_ROLE = "CONTINGENCY_EMERGENCY"
AIR_PATH_ROLE = "PRIMARY"
# gas families each flight supply mode delivers to the ONE Hall + ONE ICP (N2-family = the atmospheric gases;
# O-bearing gases belong to the atmospheric mode too; the A9 evidence order Ar -> N2 -> O2 -> atomic O is unchanged)
SUPPLY_MODE_GASES = {SUPPLY_MODE_AIR: ("N2", "NITROGEN", "O2", "OXYGEN", "O", "AIR", "N2/O2", "N2+O2", "N2_O2",
                                       "AMBIENT_AIR", "ATMOSPHERIC"),
                     SUPPLY_MODE_XE: ("XE", "XENON")}
BENCH_ENGINEERING_GAS = ("AR", "ARGON")         # A9: Ar is engineering-only; not a flight supply mode
BENCH_SUPPLY_MODE = "BENCH_AR_ENGINEERING_GROUND_ONLY"
ICP_FEED_GAS_BASELINE = {"primary": "G-REUSE", "declared_variant": "G-XE",
                         "status": "UNCHANGED (A9.1; A9.19 does not alter the ICP feed-gas baseline)"}

FLIGHT_ARCHITECTURE = {
    "configuration": FLIGHT_CONFIGURATION,
    "hall_accelerators": 1,
    "electron_source_neutralizer": {"count": 1, "kind": "RF/ICP (13.56 MHz) electron source / neutralizer, "
                                    "cathodeless / electrodeless", "serves_supply_modes": list(SUPPLY_MODES)},
    "supply_modes": [
        {"mode": SUPPLY_MODE_AIR, "role": AIR_PATH_ROLE, "propellant": "ambient atmospheric propellant (180-230 km)",
         "path": ["intake", "filter", "compressor", "atmospheric_gas_chamber", "valve"]},
        {"mode": SUPPLY_MODE_XE, "role": XE_PATH_ROLE, "propellant": "xenon",
         "path": ["xe_tank", "valve"],
         "note": "capability required by the RFP (RFP-P17-05 extra input system; RFP-P18-08 separate tank); role "
                 "contingency / emergency, not a parallel co-equal propellant (A9.19)"}],
    "separate_tanks": True,
    "conventional_hollow_cathode": "NONE",
    "icp_feed_gas_baseline": ICP_FEED_GAS_BASELINE,
    "c1": C1_ROLE,
    "verbatim": list(VERBATIM_A9_19),
    "status": "OWNER_DECIDED_ARCHITECTURE_DEFINITION (A9 investigation; not a flight baseline, not a PASS)",
}


def require_flight_configuration(config: str) -> str:
    """Refuse anything but the A9.19 flight configuration. hall_c1_reference is refused with the A9.20 reason."""
    if config == GROUND_REFERENCE_CONFIGURATION:
        raise ArchitectureRuleError(
            "REFUSED: hall_c1_reference is not a flight configuration (A9.19: no conventional hollow cathode; A9.20: C1 "
            "is a GROUND-ONLY laboratory reference, never flight hardware, never in the flight mass / power / Xe "
            "budgets); use ground_reference() where a comparison needs it")
    if config not in FLIGHT_CONFIGURATIONS:
        raise ArchitectureRuleError(f"unknown configuration {config!r}; flight configurations {FLIGHT_CONFIGURATIONS}")
    return config


def ground_reference(config: str, purpose: str) -> dict:
    """The C1 configuration as an explicitly labelled GROUND / laboratory reference (never a flight candidate)."""
    if config != GROUND_REFERENCE_CONFIGURATION:
        raise ArchitectureRuleError(f"only {GROUND_REFERENCE_CONFIGURATION!r} is a ground reference")
    if not isinstance(purpose, str) or not purpose.strip():
        raise ArchitectureRuleError("state the ground / laboratory comparison that needs the reference")
    return {"configuration": config, "label": GROUND_REFERENCE_LABEL, "c1_status": GROUND_ONLY_LAB_EQUIPMENT,
            "flight_candidate": False, "in_flight_budgets": False, "purpose": purpose.strip(),
            "authority": cite("A9.19", "A9.20")}


# names that mark a hollow-cathode element (normalised: lower case, separators -> '_')
_HC_PATTERNS = (r"hollow_?cathode", r"\blab6\b", r"lab6", r"\bbao\b", r"cathode_heater", r"cathode_keeper",
                r"(^|_)keeper(_|$)", r"(^|_)heater_keeper", r"(^|_)c_?1($|_)", r"al_c1", r"c1_xe", r"c1_heater",
                r"c1_keeper", r"conventional_cathode", r"thermionic_cathode")


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(name).lower()).strip("_")


def hollow_cathode_elements(elements: Iterable) -> list[str]:
    """Elements (names / ids, or dicts with 'id' / 'name' / 'kind') that denote a hollow-cathode element."""
    hits = []
    for e in elements:
        names = [e.get(k) for k in ("id", "name", "kind", "line", "slot") if isinstance(e, Mapping) and e.get(k)] \
            if isinstance(e, Mapping) else [e]
        for n in names:
            s = _norm(n)
            if any(re.search(p, s) for p in _HC_PATTERNS):
                hits.append(str(n))
                break
    return hits


def refuse_hollow_cathode_elements(config: str, elements: Iterable) -> dict:
    """A9.19: no conventional hollow cathode in the flight architecture. Refuses a flight configuration that lists any
    hollow-cathode element; returns the checked record otherwise."""
    require_flight_configuration(config)
    els = list(elements)
    hits = hollow_cathode_elements(els)
    if hits:
        raise ArchitectureRuleError(f"REFUSED: hollow-cathode element(s) {hits} in flight configuration {config!r} "
                                    "(A9.19: no conventional hollow cathode; A9.20: C1 ground-only)")
    return {"configuration": config, "n_elements": len(els), "hollow_cathode_elements": [],
            "check": "NO_HOLLOW_CATHODE_ELEMENT_LISTED", "authority": cite("A9.19", "A9.20")}


def classify_gas(gas) -> str:
    """Supply mode of a gas name: AIR_PRIMARY (N2-family / O-bearing atmospheric gases), XE_CONTINGENCY (Xe), the
    ground-only Ar bench mode, or refuse."""
    if not isinstance(gas, str) or not gas.strip():
        raise ArchitectureRuleError(f"gas must be a non-empty string, got {gas!r}")
    g = gas.strip().upper().replace(" ", "")
    if g in BENCH_ENGINEERING_GAS:
        return BENCH_SUPPLY_MODE
    for mode, names in SUPPLY_MODE_GASES.items():
        if g in names:
            return mode
    raise ArchitectureRuleError(f"gas {gas!r} belongs to no A9.19 supply mode (AIR_PRIMARY: N2-family / atmospheric; "
                                "XE_CONTINGENCY: Xe) and is not the Ar bench gas")


def check_supply_mode(gas, supply_mode) -> dict:
    """ICP ignition / operation record consistency between its gas and its declared supply mode (both flight modes are
    allowed; the ONE ICP serves both, A9.19)."""
    want = classify_gas(gas)
    if supply_mode not in SUPPLY_MODES + (BENCH_SUPPLY_MODE,):
        raise ArchitectureRuleError(f"supply_mode {supply_mode!r} not in {SUPPLY_MODES + (BENCH_SUPPLY_MODE,)}")
    if supply_mode != want:
        raise ArchitectureRuleError(f"gas {gas!r} is supply mode {want}, record declares {supply_mode}")
    return {"gas": gas, "supply_mode": supply_mode,
            "role": {SUPPLY_MODE_AIR: AIR_PATH_ROLE, SUPPLY_MODE_XE: XE_PATH_ROLE}.get(supply_mode,
                                                                                     "GROUND_BENCH_ENGINEERING_ONLY")}


def propellant_path_roles(paths: Mapping[str, Sequence[str]]) -> dict:
    """HC-10 role record: separate air and Xe paths; the Xe path role is CONTINGENCY_EMERGENCY (A9.19)."""
    air, xe = list(paths.get("air", ())), list(paths.get("xe", ()))
    if not air or not xe:
        raise ArchitectureRuleError("A9.19 / RFP-P18-08: both the air path and the separate Xe path are required")
    return {"air": {"path": air, "supply_mode": SUPPLY_MODE_AIR, "role": AIR_PATH_ROLE},
            "xe": {"path": xe, "supply_mode": SUPPLY_MODE_XE, "role": XE_PATH_ROLE},
            "rule": "two separate supply modes / tanks / paths (RFP-P18-08); Xe = contingency / emergency mode, "
                    "capability still required (RFP-P17-05; A9.19 amends A9.15 on the role of Xe)",
            "authority": cite("A9.19", "A9.15")}


# ================================================================================================= application rows
def applied_row(decision: str, artifact: str, record_ids, how_applied: str, tests=None, item: str = "") -> dict:
    """One 'owner_answers_applied' entry citing A9.19 / A9.20 (path + json sha256 + md sha256)."""
    if decision not in ("A9.19", "A9.20"):
        raise ArchitectureRuleError("only A9.19 / A9.20 rows are recorded here")
    d = DECISIONS[decision]
    return {"decision": decision, "question_id": item or decision, "decision_code": d["decision_code"],
            "decision_json": d["json"], "decision_json_sha256": d["json_sha256"], "decision_md": d["md"],
            "decision_md_sha256": d["md_sha256"], "artifact": artifact,
            "record_ids": list(record_ids) if isinstance(record_ids, (list, tuple)) else [record_ids],
            "how_applied": how_applied, "tests": list(tests or [])}
