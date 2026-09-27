"""Parametric Xe mass ledger and stored-Xe subsystem ledger  (xe_ledger_v1; follow-on fo_xe_system_ledger).

Owner basis (immutable decision files, pinned by sha256 in docs/budgets/xe_ledger/xe_ledger_v1.json):
  * A5 docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_architecture.json, ``xe_mass_allocation``:
    one fixed Xe tank allocation; every Xe-consuming mode draws on it; cathode design target 0.10 mg/s, 0.15 mg/s is an
    experimental upper test point only.
  * A6 docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A6_a5_followon_authorization.json,
    ``authorized_now.fo_xe_system_ledger`` (this ledger) and ``not_authorized`` (no total Xe mass frozen; no
    startup/transition/fallback quantity frozen without evidence).

Implements exactly (A6):
    m_cathode      = mdot_cathode * t_firing
    m_startup      = N_starts * t_startup * mdot_startup
    m_transition   = N_transitions * t_transition * mdot_transition
    m_fallback     = t_fallback_max * mdot_fallback
    m_reserve      = explicit policy term (``RESERVE_FORMS``); never folded into another category
    m_Xe_total     = m_cathode + m_startup + m_transition + m_fallback + m_reserve
    m_Xe_subsystem = m_Xe_total + m_tank + m_regulator + m_valves + m_plumbing + m_mounting_thermal
with m_tank from an explicit tank model (``TANK_FORMS``).

What this module is not: a Xe allocation, a prediction, or a Hall model. It is pure (standard library, no I/O) and is
NOT wired into ``archengine`` (wiring would be a model change; the goldens must not move).

No hidden defaults (CLAUDE.md rule 3). No physical, efficiency, duration, count or hardware value lives in this module.
Every input is an explicit :class:`Quantity` (value, unit, source, evidence class) or a :class:`TBD` record that names
what closes it. Evaluation refuses with :class:`LedgerIncomplete` and lists every TBD or missing input, unless the
caller explicitly asks for a partial evaluation. A partial evaluation returns ``None`` for every total it cannot close.
The only constants here are exact unit definitions (mg -> kg, g -> kg, h -> s) and the allowed vocabularies.

The Xe path is upstream of the discharge. Hall-transport closures, ensemble members, screening candidates and P5
calibration-nuisance variables never enter it (CLAUDE.md two-layer Hall uncertainty, Scope): inputs carrying such keys
are rejected.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from numbers import Real

LEDGER_VERSION = "xe_ledger_v1"
ARCHITECTURES = ("hall_only", "rf_hall", "ecr_hall")
EVIDENCE_CLASSES = ("measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed")

# Exact unit definitions (SI definitions, not physical data).
_UNIT_FACTORS = {
    "mass_flow": {"mg/s": 1.0e-6, "g/s": 1.0e-3, "kg/s": 1.0},
    "time": {"s": 1.0, "min": 60.0, "h": 3600.0},
    "mass": {"g": 1.0e-3, "kg": 1.0},
    "count": {"1": 1.0},
    "fraction": {"1": 1.0},
}

# The ten product-term inputs and their kinds (A6 formulas).
FIELD_KINDS = {
    "mdot_cathode": "mass_flow",
    "t_firing": "time",
    "N_starts": "count",
    "t_startup": "time",
    "mdot_startup": "mass_flow",
    "N_transitions": "count",
    "t_transition": "time",
    "mdot_transition": "mass_flow",
    "t_fallback_max": "time",
    "mdot_fallback": "mass_flow",
}
TERM_FIELDS = {
    "m_cathode": ("mdot_cathode", "t_firing"),
    "m_startup": ("N_starts", "t_startup", "mdot_startup"),
    "m_transition": ("N_transitions", "t_transition", "mdot_transition"),
    "m_fallback": ("t_fallback_max", "mdot_fallback"),
}
PRODUCT_TERMS = tuple(TERM_FIELDS)
XE_TERMS = PRODUCT_TERMS + ("m_reserve",)
HARDWARE_ITEMS = ("m_regulator", "m_valves", "m_plumbing", "m_mounting_thermal")

# Reserve policy forms (the owner chooses the form and its value; neither has a default).
RESERVE_FORMS = {
    "fraction_of_other_terms": "m_reserve = f_reserve x (m_cathode + m_startup + m_transition + m_fallback); "
                               "f_reserve dimensionless ('1'), >= 0",
    "absolute_mass": "m_reserve = m_reserve_abs (mass unit), >= 0",
}
# Tank model forms (the tank mass is an explicit input with a source; nothing is sized here).
TANK_FORMS = {
    "tankage_fraction": "m_tank = f_tank x m_Xe_total (the loaded Xe, all five terms); f_tank dimensionless ('1'), "
                        ">= 0",
    "tank_mass": "m_tank = m_tank_abs (mass unit), >= 0, for the tank selected for the declared Xe load",
}

# Accounting conventions for the phase terms (PROPOSED; the owner chooses; no default).
ACCOUNTING_CONVENTIONS = {
    "PHASE_TOTAL_FLOW": (
        "Each phase term (startup, transition, fallback) carries the TOTAL Xe flow during that phase (anode-side Xe "
        "plus cathode Xe). m_cathode carries the cathode flow over t_firing only. Phase hours are booked in their own "
        "terms. Where a phase's hours are also counted inside t_firing, the cathode flow over those hours is booked twice, "
        "at most mdot_cathode x overlap hours (conservative)."),
    "CATHODE_CONTINUOUS_INCREMENTAL": (
        "m_cathode carries the cathode flow over every hour the cathode flows (t_firing must then include startup, "
        "transition and fallback hours). Each phase term carries only the Xe ABOVE that cathode flow (anode-side Xe "
        "plus any cathode flow above mdot_cathode). If t_firing is held at the RFP firing hours, the cathode flow "
        "during phases outside those hours is missing (non-conservative)."),
}

# Mirrors abep_sim/mass_bom.py (tests assert equality): keys that are never Xe-ledger inputs.
CALIBRATION_NUISANCE_KEYS = frozenset({
    "p5_registration", "registration", "coil_shape", "historical_coil_shape", "divergence_reading",
    "beam_efficiency_reading", "facility_interpretation", "facility_ingestion_interpretation"})
HALL_CLOSURE_KEYS = frozenset({"hall_closure_id", "ensemble_member_id", "screening_candidate_id", "transport_closure"})

REFERENCE_KINDS = ("requirement", "allocation")


class LedgerIncomplete(ValueError):
    """Raised when an evaluation needs an input that is TBD or missing. ``missing`` lists every such input."""

    def __init__(self, missing: list):
        self.missing = list(missing)
        lines = "; ".join(f"{m['field']}: {m['requires']}" for m in self.missing)
        super().__init__(f"Xe ledger refused: {len(self.missing)} input(s) TBD or missing -> {lines}")


@dataclass(frozen=True)
class Quantity:
    """An explicit input value with its provenance. ``evidence_class`` is one of ``EVIDENCE_CLASSES``."""
    value: float
    unit: str
    source: str
    evidence_class: str


@dataclass(frozen=True)
class TBD:
    """An input that is not yet available. ``requires`` names what closes it (measurement, procurement, owner)."""
    requires: str


# ----------------------------------------------------------------------------------------------------- validation
def coerce(obj, name: str):
    """Quantity | TBD | mapping -> Quantity | TBD. A mapping needs either ``tbd`` (str) or all four Quantity fields."""
    if isinstance(obj, (Quantity, TBD)):
        return obj
    if isinstance(obj, Mapping):
        if "tbd" in obj:
            req = obj["tbd"]
            if not isinstance(req, str) or not req.strip():
                raise ValueError(f"{name}: 'tbd' must name what closes it (non-empty string)")
            return TBD(req)
        keys = ("value", "unit", "source", "evidence_class")
        absent = [k for k in keys if k not in obj]
        if absent:
            raise ValueError(f"{name}: quantity record lacks {absent}; every value needs value, unit, source and "
                             "evidence_class (no defaults)")
        return Quantity(obj["value"], obj["unit"], obj["source"], obj["evidence_class"])
    raise ValueError(f"{name}: expected a Quantity, a TBD or a mapping, got {type(obj).__name__}")


def to_si(q, kind: str, name: str) -> float:
    """Validate a Quantity of the given kind and return it in SI (kg/s, s, kg, 1). Raises on any violation."""
    if isinstance(q, TBD):
        raise LedgerIncomplete([{"field": name, "requires": q.requires}])
    if not isinstance(q, Quantity):
        raise ValueError(f"{name}: expected a Quantity, got {type(q).__name__}")
    if kind not in _UNIT_FACTORS:
        raise ValueError(f"{name}: unknown quantity kind {kind!r}")
    if not isinstance(q.source, str) or not q.source.strip():
        raise ValueError(f"{name}: a source is required")
    if q.evidence_class not in EVIDENCE_CLASSES:
        raise ValueError(f"{name}: evidence_class {q.evidence_class!r} is not one of {EVIDENCE_CLASSES}")
    units = _UNIT_FACTORS[kind]
    if q.unit not in units:
        raise ValueError(f"{name}: unit {q.unit!r} is not a {kind} unit {tuple(units)}")
    v = q.value
    if isinstance(v, bool) or not isinstance(v, Real) or not math.isfinite(float(v)):
        raise ValueError(f"{name}: value must be a finite real number, got {v!r}")
    v = float(v)
    if v < 0.0:
        raise ValueError(f"{name}: value must be >= 0, got {v}")
    if kind == "count" and v != math.floor(v):
        raise ValueError(f"{name}: a count must be a whole number, got {v}")
    return v * units[q.unit]


def reject_forbidden_keys(obj, path: str = "inputs") -> None:
    """Refuse Hall-closure markers and P5 calibration-nuisance keys anywhere in a nested input structure."""
    if isinstance(obj, Mapping):
        for k, v in obj.items():
            here = f"{path}.{k}"
            if k in CALIBRATION_NUISANCE_KEYS:
                raise ValueError(f"{here}: P5 calibration nuisance (layer 1) is never a design variable or Xe input")
            if k in HALL_CLOSURE_KEYS or (k == "depends_on_hall_closure" and v):
                raise ValueError(f"{here}: Hall-transport closure markers never enter the Xe path (upstream of the "
                                 "discharge; credible set empty; screening candidates are never sources)")
            reject_forbidden_keys(v, here)
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            reject_forbidden_keys(v, f"{path}[{i}]")


def _check_header(inputs: Mapping) -> tuple:
    if not isinstance(inputs, Mapping):
        raise ValueError("inputs must be a mapping")
    reject_forbidden_keys(inputs)
    scope = inputs.get("architecture_scope")
    if (not isinstance(scope, (list, tuple)) or not scope or len(set(scope)) != len(scope)
            or any(a not in ARCHITECTURES for a in scope)):
        raise ValueError(f"architecture_scope must be a non-empty list of distinct ids from {ARCHITECTURES}")
    conv = inputs.get("accounting_convention")
    if conv not in ACCOUNTING_CONVENTIONS:
        raise ValueError(f"accounting_convention must be one of {tuple(ACCOUNTING_CONVENTIONS)} (explicit; no default)")
    return list(scope), conv


def _field(inputs: Mapping, name: str):
    if name not in inputs:
        return TBD(f"input '{name}' not supplied")
    return coerce(inputs[name], name)


def _policy(inputs: Mapping, key: str, forms: Mapping, kinds: Mapping) -> tuple:
    """Return (form, value_si) or raise LedgerIncomplete / ValueError."""
    if key not in inputs:
        raise LedgerIncomplete([{"field": key, "requires": f"input '{key}' not supplied"}])
    pol = inputs[key]
    if isinstance(pol, TBD) or (isinstance(pol, Mapping) and "tbd" in pol):
        raise LedgerIncomplete([{"field": key, "requires": coerce(pol, key).requires}])
    if not isinstance(pol, Mapping) or "form" not in pol or "value" not in pol:
        raise ValueError(f"{key}: expected {{'form': one of {tuple(forms)}, 'value': Quantity}} or a TBD")
    form = pol["form"]
    if form not in forms:
        raise ValueError(f"{key}: form {form!r} is not one of {tuple(forms)}")
    val = coerce(pol["value"], f"{key}.value")
    return form, to_si(val, kinds[form], f"{key}.value")


_RESERVE_KINDS = {"fraction_of_other_terms": "fraction", "absolute_mass": "mass"}
_TANK_KINDS = {"tankage_fraction": "fraction", "tank_mass": "mass"}


# ----------------------------------------------------------------------------------------------------- terms
def product_term_kg(inputs: Mapping, term: str) -> float:
    """One of m_cathode / m_startup / m_transition / m_fallback in kg. Raises LedgerIncomplete if an input is TBD."""
    if term not in TERM_FIELDS:
        raise ValueError(f"unknown term {term!r}; expected one of {PRODUCT_TERMS}")
    missing, vals = [], []
    for f in TERM_FIELDS[term]:
        q = _field(inputs, f)
        if isinstance(q, TBD):
            missing.append({"field": f, "requires": q.requires})
            continue
        vals.append(to_si(q, FIELD_KINDS[f], f))
    if missing:
        raise LedgerIncomplete(missing)
    out = 1.0
    for v in vals:
        out *= v
    return out


def reserve_kg(inputs: Mapping, other_terms_kg: float) -> float:
    """m_reserve from the explicit reserve policy.

    ``other_terms_kg`` = m_cathode + m_startup + m_transition + m_fallback (used by the fraction form only).
    """
    form, v = _policy(inputs, "reserve_policy", RESERVE_FORMS, _RESERVE_KINDS)
    return v * other_terms_kg if form == "fraction_of_other_terms" else v


def tank_kg(inputs: Mapping, m_xe_total_kg: float) -> float:
    """m_tank from the explicit tank model; a tankage fraction applies to the loaded Xe m_Xe_total (all five terms)."""
    form, v = _policy(inputs, "tank_model", TANK_FORMS, _TANK_KINDS)
    return v * m_xe_total_kg if form == "tankage_fraction" else v


def evaluate(inputs: Mapping, *, level: str, allow_partial: bool = False) -> dict:
    """Evaluate the Xe ledger (``level='xe_total'``) or the stored-Xe subsystem (``level='subsystem'``).

    Without ``allow_partial`` any TBD or missing input raises :class:`LedgerIncomplete` listing all of them. With it,
    every closed term is returned, every total that cannot be closed is ``None``, and ``missing`` lists what blocks it.
    """
    if level not in ("xe_total", "subsystem"):
        raise ValueError("level must be 'xe_total' or 'subsystem'")
    scope, conv = _check_header(inputs)
    missing: list = []
    terms: dict = {}
    for t in PRODUCT_TERMS:
        try:
            terms[t] = product_term_kg(inputs, t)
        except LedgerIncomplete as exc:
            terms[t] = None
            missing.extend(exc.missing)
    others = None if any(terms[t] is None for t in PRODUCT_TERMS) else sum(terms[t] for t in PRODUCT_TERMS)
    reserve_form = None
    try:
        reserve_form, _ = _policy(inputs, "reserve_policy", RESERVE_FORMS, _RESERVE_KINDS)
        if reserve_form == "fraction_of_other_terms" and others is None:
            terms["m_reserve"] = None
        else:
            terms["m_reserve"] = reserve_kg(inputs, others if others is not None else 0.0)
    except LedgerIncomplete as exc:
        terms["m_reserve"] = None
        missing.extend(exc.missing)
    m_total = None if any(terms[t] is None for t in XE_TERMS) else sum(terms[t] for t in XE_TERMS)
    out = {
        "ledger_version": LEDGER_VERSION,
        "architecture_scope": scope,
        "accounting_convention": conv,
        "reserve_form": reserve_form,
        "terms_kg": terms,
        "m_Xe_total_kg": m_total,
        "complete_xe_total": m_total is not None,
    }
    if level == "subsystem":
        tank_form, m_tank = None, None
        try:
            tank_form, _ = _policy(inputs, "tank_model", TANK_FORMS, _TANK_KINDS)
            if tank_form == "tankage_fraction" and m_total is None:
                m_tank = None
            else:
                m_tank = tank_kg(inputs, m_total if m_total is not None else 0.0)
        except LedgerIncomplete as exc:
            missing.extend(exc.missing)
        hw: dict = {}
        for h in HARDWARE_ITEMS:
            q = _field(inputs, h)
            if isinstance(q, TBD):
                hw[h] = None
                missing.append({"field": h, "requires": q.requires})
            else:
                hw[h] = to_si(q, "mass", h)
        parts = [m_total, m_tank] + [hw[h] for h in HARDWARE_ITEMS]
        m_sub = None if any(p is None for p in parts) else sum(parts)
        out.update({"tank_form": tank_form, "m_tank_kg": m_tank, "hardware_kg": hw,
                    "m_Xe_subsystem_kg": m_sub, "complete_subsystem": m_sub is not None})
    out["missing"] = missing
    if missing and not allow_partial:
        raise LedgerIncomplete(missing)
    return out


# ----------------------------------------------------------------------------------------------------- references
def allocation_shares(mass_kg: float, references: Sequence) -> list:
    """Share of each mass reference taken by ``mass_kg``. A share, never a prediction or a verdict.

    ``references``: explicit records {id, value_kg, kind ('requirement' | 'allocation'), source}. No default reference
    exists in this module (the RFP 40 kg and the A5 34-36 kg allocation are supplied by the caller with their source).
    """
    if isinstance(mass_kg, bool) or not isinstance(mass_kg, Real) or not math.isfinite(mass_kg) or mass_kg < 0:
        raise ValueError(f"mass_kg must be a finite non-negative number, got {mass_kg!r}")
    if not references:
        raise ValueError("at least one explicit mass reference is required")
    out = []
    for r in references:
        for k in ("id", "value_kg", "kind", "source"):
            if k not in r:
                raise ValueError(f"mass reference lacks {k!r}: {r!r}")
        if r["kind"] not in REFERENCE_KINDS:
            raise ValueError(f"reference kind must be one of {REFERENCE_KINDS}")
        m = r["value_kg"]
        if isinstance(m, bool) or not isinstance(m, Real) or not m > 0:
            raise ValueError(f"reference {r['id']!r}: value_kg must be > 0")
        out.append({"id": r["id"], "kind": r["kind"], "value_kg": float(m), "share": mass_kg / float(m),
                    "source": r["source"]})
    return out


def flow_consuming_mass_mg_s(mass_kg: float, t_firing) -> float:
    """Constant flow (mg/s) that consumes ``mass_kg`` over ``t_firing`` (explicit Quantity). Arithmetic only."""
    if isinstance(mass_kg, bool) or not isinstance(mass_kg, Real) or not math.isfinite(mass_kg) or mass_kg < 0:
        raise ValueError("mass_kg must be a finite non-negative number")
    t = to_si(coerce(t_firing, "t_firing"), "time", "t_firing")
    if t <= 0:
        raise ValueError("t_firing must be > 0")
    return mass_kg / t / 1.0e-6


# ----------------------------------------------------------------------------------------------------- inverse
def xe_sum_cap_kg(inputs: Mapping, cap_kg: float) -> float:
    """Largest S = m_cathode + m_startup + m_transition + m_fallback that keeps m_Xe_subsystem <= ``cap_kg``.

    Needs the reserve policy, the tank model and the four hardware masses explicitly (else LedgerIncomplete). The
    result can be negative: the fixed parts alone then exceed the cap.
    """
    if isinstance(cap_kg, bool) or not isinstance(cap_kg, Real) or not math.isfinite(cap_kg) or cap_kg <= 0:
        raise ValueError("cap_kg must be a finite positive number")
    missing = []
    hw = 0.0
    for h in HARDWARE_ITEMS:
        q = _field(inputs, h)
        if isinstance(q, TBD):
            missing.append({"field": h, "requires": q.requires})
        else:
            hw += to_si(q, "mass", h)
    try:
        r_form, r = _policy(inputs, "reserve_policy", RESERVE_FORMS, _RESERVE_KINDS)
    except LedgerIncomplete as exc:
        missing.extend(exc.missing)
    try:
        t_form, t = _policy(inputs, "tank_model", TANK_FORMS, _TANK_KINDS)
    except LedgerIncomplete as exc:
        missing.extend(exc.missing)
    if missing:
        raise LedgerIncomplete(missing)
    # m_sub = m_Xe * (1 + f_t) + hw            (tankage fraction)   or   m_Xe + T + hw   (tank mass)
    # m_Xe  = S * (1 + f_r)                    (reserve fraction)   or   S + R           (absolute reserve)
    xe_cap = (cap_kg - hw) / (1.0 + t) if t_form == "tankage_fraction" else cap_kg - hw - t
    return xe_cap / (1.0 + r) if r_form == "fraction_of_other_terms" else xe_cap - r


_OUTPUT_UNITS = {"count": ("1", 1.0), "time": ("h", 3600.0), "mass_flow": ("mg/s", 1.0e-6)}


def max_allowance(inputs: Mapping, solve_for: str, cap_kg: float) -> dict:
    """Largest value of one TBD product-term input that keeps m_Xe_subsystem <= ``cap_kg``, all else explicit.

    ``inputs[solve_for]`` must be TBD or absent (the value being solved for is never also supplied). Every other input
    (the other nine product-term inputs, reserve policy, tank model, hardware masses) must be explicit. Counts are
    floored to whole numbers; times are returned in h and flows in mg/s. Statuses: ``ALLOWANCE`` (value >= 0),
    ``EXCEEDED_WITHOUT_THIS_TERM`` (the other parts alone exceed the cap; value None), ``NOT_CONSTRAINED`` (a co-factor
    of the solved input is zero, so its term is zero at any value; value None).
    """
    if solve_for not in FIELD_KINDS:
        raise ValueError(f"solve_for must be one of {tuple(FIELD_KINDS)}")
    _check_header(inputs)
    if solve_for in inputs and not isinstance(coerce(inputs[solve_for], solve_for), TBD):
        raise ValueError(f"{solve_for} is being solved for; pass it as TBD (or omit it), not as a value")
    target_term = next(t for t, fs in TERM_FIELDS.items() if solve_for in fs)
    s_cap = xe_sum_cap_kg(inputs, cap_kg)
    others, missing = 0.0, []
    for t in PRODUCT_TERMS:
        if t == target_term:
            continue
        try:
            others += product_term_kg(inputs, t)
        except LedgerIncomplete as exc:
            missing.extend(exc.missing)
    cofactor = 1.0
    for f in TERM_FIELDS[target_term]:
        if f == solve_for:
            continue
        q = _field(inputs, f)
        if isinstance(q, TBD):
            missing.append({"field": f, "requires": q.requires})
            continue
        cofactor *= to_si(q, FIELD_KINDS[f], f)
    if missing:
        raise LedgerIncomplete(missing)
    allowance_kg = s_cap - others
    unit, factor = _OUTPUT_UNITS[FIELD_KINDS[solve_for]]
    out = {"field": solve_for, "term": target_term, "cap_kg": float(cap_kg), "xe_sum_cap_kg": s_cap,
           "other_terms_kg": others, "term_allowance_kg": allowance_kg, "unit": unit}
    if allowance_kg < 0.0:
        out.update({"status": "EXCEEDED_WITHOUT_THIS_TERM", "value": None})
    elif cofactor == 0.0:
        out.update({"status": "NOT_CONSTRAINED", "value": None})
    else:
        v = allowance_kg / cofactor / factor
        if FIELD_KINDS[solve_for] == "count":
            v = float(math.floor(v + 1e-9))
        out.update({"status": "ALLOWANCE", "value": v})
    return out
