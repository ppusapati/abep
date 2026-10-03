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

A9.22 layer separation, Phase A: the architecture DEFINITION (decision-record pins, configuration names, supply modes,
gases, C1 role, FLIGHT_ARCHITECTURE) lives in config/architecture/hall_icp_neutralizer_v1.json, generated from the
owner decision records by scripts/config/build_config.py and sha256-checked against config/MANIFEST.json by
abep_sim.configuration (fail closed). This module is its loader plus the rule logic; every constant keeps its value.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from ..configuration import load_architecture as _load_architecture

REPO = Path(__file__).resolve().parents[2]

class ArchitectureRuleError(ValueError):
    """A request that A9.19 / A9.20 forbids (refused, never repaired)."""


_ARCH = _load_architecture()          # config/architecture/hall_icp_neutralizer_v1.json (manifest-verified)
_C = _ARCH["constants"]

DECISIONS = {k: dict(v) for k, v in _ARCH["decision_records"].items()}
RFP_REGISTRATION = _ARCH["rfp_registration"]
RFP_CLAUSES = dict(_ARCH["rfp_clauses"])
VERBATIM_A9_19 = tuple(_ARCH["verbatim_a9_19"])


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
FLIGHT_CONFIGURATION = _C["flight_configuration"]
FLIGHT_CONFIGURATIONS = (FLIGHT_CONFIGURATION,)
GROUND_REFERENCE_CONFIGURATION = _C["ground_reference_configuration"]
GROUND_REFERENCE_LABEL = _C["ground_reference_label"]
GROUND_ONLY_LAB_EQUIPMENT = _C["ground_only_lab_equipment"]
C1_ROLE = _C["c1_role"]
SUPPLY_MODE_AIR = _C["supply_mode_air"]
SUPPLY_MODE_XE = _C["supply_mode_xe"]
SUPPLY_MODES = tuple(_C["supply_modes"])
XE_PATH_ROLE = _C["xe_path_role"]
AIR_PATH_ROLE = _C["air_path_role"]
# gas families each flight supply mode delivers to the ONE Hall + ONE ICP (N2-family = the atmospheric gases;
# O-bearing gases belong to the atmospheric mode too; the A9 evidence order Ar -> N2 -> O2 -> atomic O is unchanged)
SUPPLY_MODE_GASES = {k: tuple(v) for k, v in _C["supply_mode_gases"].items()}
BENCH_ENGINEERING_GAS = tuple(_C["bench_engineering_gas"])     # A9: Ar is engineering-only; not a flight supply mode
BENCH_SUPPLY_MODE = _C["bench_supply_mode"]
ICP_FEED_GAS_BASELINE = _C["icp_feed_gas_baseline"]
FLIGHT_ARCHITECTURE = _C["flight_architecture"]


def _check_loaded_architecture() -> None:
    """Internal consistency of the loaded definition (fail closed; the config builder enforces the same)."""
    problems = []
    if tuple(_C["flight_configurations"]) != FLIGHT_CONFIGURATIONS:
        problems.append("config flight_configurations must be exactly (flight_configuration,)")
    if GROUND_REFERENCE_CONFIGURATION in FLIGHT_CONFIGURATIONS:
        problems.append("the ground reference is not a flight configuration")
    if SUPPLY_MODES != (SUPPLY_MODE_AIR, SUPPLY_MODE_XE) or set(SUPPLY_MODE_GASES) != set(SUPPLY_MODES):
        problems.append("supply modes / gases inconsistent")
    if FLIGHT_ARCHITECTURE.get("configuration") != FLIGHT_CONFIGURATION or FLIGHT_ARCHITECTURE.get("c1") != C1_ROLE \
            or FLIGHT_ARCHITECTURE.get("icp_feed_gas_baseline") != ICP_FEED_GAS_BASELINE \
            or FLIGHT_ARCHITECTURE.get("verbatim") != list(VERBATIM_A9_19) \
            or FLIGHT_ARCHITECTURE.get("conventional_hollow_cathode") != "NONE":
        problems.append("FLIGHT_ARCHITECTURE inconsistent with the loaded constants")
    if problems:
        raise ArchitectureRuleError(f"REFUSED: config/architecture definition inconsistent: {problems}")


_check_loaded_architecture()
# the flight architecture shares the C1-role and ICP-feed objects (as when they were defined inline)
FLIGHT_ARCHITECTURE["c1"] = C1_ROLE
FLIGHT_ARCHITECTURE["icp_feed_gas_baseline"] = ICP_FEED_GAS_BASELINE


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


# RV19-11: content a flight budget line carries that is C1-related but NOT a listed hollow-cathode element. These are
# made visible (never silently passed) and reported in a non-clean check state; the budgets lane owns their removal.
#   CONDITIONAL_NOT_BOOKED: a provision worded "if C1 selected" (A9.20: C1 is never selected for flight -> books nothing)
#                           or a c1_branch record whose state is *NOT_SELECTED with nothing in the line.
#   EMBEDDED_IN_FLOOR:      the budget states elsewhere that a C1 cathode Xe branch mass is already inside a flight line's
#                           evidence floor (an inferred analog floor, not a listed element): needs re-attribution.
C1_BOOKING_CONDITIONAL = "CONDITIONAL_NOT_BOOKED"
C1_BOOKING_EMBEDDED = "EMBEDDED_IN_FLOOR"
C1_FLAGGED_BOOKINGS = (C1_BOOKING_CONDITIONAL, C1_BOOKING_EMBEDDED)
CHECK_CLEAN = "NO_HOLLOW_CATHODE_ELEMENT_LISTED"
CHECK_FLAGGED = "NO_HOLLOW_CATHODE_ELEMENT_LISTED_C1_PROVISIONS_FLAGGED_PENDING_BUDGET_REFRESH"
_C1_CONDITIONAL_RE = re.compile(r"if\s+c-?1\s+(is\s+)?selected", re.I)
# A9.19 budget refresh: a flight line may state the ABSENCE of C1 content explicitly ('no C1 electronics - C1 is
# ground-only'; a c1_branch record whose state is NO_C1_... with nothing in the line). Such a statement is not a listed
# element: it is reported (c1_absence_statements) and keeps the check clean only when the text left after removing the
# negated / ground-only clauses carries no hollow-cathode marker at all (a booked C1 item is still refused).
C1_DECLARED_ABSENT = "DECLARED_ABSENT"
_C1_ABSENCE_RES = (re.compile(r"\bno\s+c-?1\b[^;,()\-]*", re.I),
                   re.compile(r"\bc-?1\s+is\s+ground-?\s*only\b", re.I))


def is_c1_absence_text(text) -> bool:
    """True when ``text`` mentions C1 only inside explicit absence clauses ('no C1 ...', 'C1 is ground-only')."""
    if not isinstance(text, str) or not any(r.search(text) for r in _C1_ABSENCE_RES):
        return False
    rest = text
    for r in _C1_ABSENCE_RES:
        rest = r.sub(" ", rest)
    return bool(hollow_cathode_elements([text])) and not hollow_cathode_elements([rest])


def is_c1_absent_branch_state(state, in_line) -> bool:
    """A c1_branch record that declares no C1 branch in flight (state NO_C1_..., nothing booked in the line)."""
    return str(state).upper().startswith("NO_C1") and not in_line


def is_conditional_c1_text(text) -> bool:
    return isinstance(text, str) and bool(_C1_CONDITIONAL_RE.search(text))


def refuse_hollow_cathode_elements(config: str, elements: Iterable) -> dict:
    """A9.19: no conventional hollow cathode in the flight architecture. Refuses a flight configuration that lists any
    hollow-cathode element; returns the checked record otherwise. Elements carrying ``booking`` in C1_FLAGGED_BOOKINGS
    (conditional / embedded C1 provisions, RV19-11) are not refusals but are reported and make the check non-clean.
    Elements booked C1_DECLARED_ABSENT (explicit 'no C1' statements, re-verified here) are reported in
    ``c1_absence_statements`` and do not make the check non-clean."""
    require_flight_configuration(config)
    els = list(elements)

    def _flagged(e):
        return isinstance(e, Mapping) and e.get("booking") in C1_FLAGGED_BOOKINGS

    def _absent(e):
        # the label is re-verified here: a DECLARED_ABSENT booking on content that books C1 is still refused
        if not (isinstance(e, Mapping) and e.get("booking") == C1_DECLARED_ABSENT):
            return False
        if e.get("kind") == "c1_branch":
            return is_c1_absent_branch_state(e.get("state"), e.get("in_line"))
        return is_c1_absence_text(e.get("name"))

    flagged = [e for e in els if _flagged(e)]
    absent = [e for e in els if _absent(e)]
    hits = hollow_cathode_elements([e for e in els if not _flagged(e) and not _absent(e)])
    if hits:
        raise ArchitectureRuleError(f"REFUSED: hollow-cathode element(s) {hits} in flight configuration {config!r} "
                                    "(A9.19: no conventional hollow cathode; A9.20: C1 ground-only)")
    return {"configuration": config, "n_elements": len(els), "hollow_cathode_elements": [],
            "c1_provisions_flagged": [dict(e) for e in flagged],
            "c1_absence_statements": [dict(e) for e in absent],
            "check": CHECK_FLAGGED if flagged else CHECK_CLEAN, "authority": cite("A9.19", "A9.20")}


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
