"""Core contracts of the parallel RF || Hall architecture investigation (v2).

This module defines immutable, validated value objects shared by every v2 module:

* ``Quantity``: a number that carries its evidence (source, evidence class, uncertainty, applicability, validation
  status). v2 has no bare physical defaults: every engineering input is a ``Quantity`` or an explicit ``TBD``.
* ``TBD``: an explicitly missing quantity. It is never silently replaced by zero.
* ``FeedState``: a propellant stream (mass flow, pressure, temperature, species mass fractions) with provenance.
* ``Status``: the v2 status taxonomy. Categories are never converted into one another (OUT_OF_DOMAIN is not
  FAIL_VALIDATION).
* ``Limit`` / ``SystemConstraints``: requirements and internal design allocations, kept distinguishable.

Scientific status: architecture-investigation infrastructure, not a flight-baseline update. The historical A5
decision (RF -> Hall pre-ionization) and every v1 artifact (bus_power_boundary_v1, mass_bom_v1, xe_ledger_v1) are
untouched; v2 represents the separate RF || Hall hypothesis.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from numbers import Real
from types import MappingProxyType
from typing import Mapping

CONTRACTS_VERSION = "parallel_contracts_v2"

EVIDENCE_CLASSES = ("measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed")
SPECIES = ("O", "O2", "N2", "N", "Xe")
ATMOSPHERIC_SPECIES = ("O", "O2", "N2", "N")

# Explicit numerical tolerance of the species mass-fraction sum and of mass/energy balances (relative).
FRACTION_SUM_TOL = 1e-9
BALANCE_REL_TOL = 1e-12


class ContractError(ValueError):
    """A v2 contract was violated (bad input, hidden default, illegal combination)."""


class Status(str, Enum):
    """v2 status taxonomy. Each category has its own meaning; they are never merged or converted."""
    PASS = "PASS"
    FAIL_VALIDATION = "FAIL_VALIDATION"
    OUT_OF_DOMAIN = "OUT_OF_DOMAIN"
    NUMERICAL_FAILURE = "NUMERICAL_FAILURE"
    INCOMPLETE_EVIDENCE = "INCOMPLETE_EVIDENCE"
    INFEASIBLE_POWER = "INFEASIBLE_POWER"
    INFEASIBLE_FLOW = "INFEASIBLE_FLOW"
    INFEASIBLE_THERMAL = "INFEASIBLE_THERMAL"
    INFEASIBLE_MASS = "INFEASIBLE_MASS"


class FeasibilityVerdict(str, Enum):
    """The only architecture-level verdicts v2 may return. There is deliberately no BEST_ARCHITECTURE."""
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    UNRESOLVED = "UNRESOLVED"
    OUT_OF_DOMAIN = "OUT_OF_DOMAIN"
    INCOMPLETE_EVIDENCE = "INCOMPLETE_EVIDENCE"


class InfeasibleError(ContractError):
    """A physically/budget-infeasible request (e.g. over-allocated propellant). Carries its Status category."""

    def __init__(self, status: Status, message: str):
        super().__init__(f"{status.value}: {message}")
        self.status = status


# --------------------------------------------------------------------------------------------------- primitives

def real(value, what: str) -> float:
    """A finite real number (bool refused); -0.0 normalised to 0.0."""
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ContractError(f"{what} must be a real number, got {type(value).__name__} {value!r}")
    x = float(value)
    if not math.isfinite(x):
        raise ContractError(f"{what} must be finite, got {x!r}")
    return x + 0.0


def nonneg(value, what: str) -> float:
    x = real(value, what)
    if x < 0.0:
        raise ContractError(f"{what} must be >= 0, got {x!r}")
    return x


def positive(value, what: str) -> float:
    x = real(value, what)
    if x <= 0.0:
        raise ContractError(f"{what} must be > 0, got {x!r}")
    return x


def nonempty(value, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{what} must be a non-empty string, got {value!r}")
    return value


def evidence_class(value, what: str) -> str:
    if value not in EVIDENCE_CLASSES:
        raise ContractError(f"{what} must be one of {EVIDENCE_CLASSES}, got {value!r}")
    return value


@dataclass(frozen=True)
class TBD:
    """An explicitly missing quantity. ``requires`` states what would close it. Never equal to zero."""
    name: str
    requires: str

    def __post_init__(self):
        nonempty(self.name, "TBD.name")
        nonempty(self.requires, "TBD.requires")

    def to_dict(self) -> dict:
        return {"TBD": True, "name": self.name, "requires": self.requires}


@dataclass(frozen=True)
class Quantity:
    """A value with its evidence. ``quantity_type`` is the evidence class (measured ... assumed)."""
    value: float
    unit: str
    quantity_type: str
    source: str
    uncertainty: str
    applicability_domain: str
    validation_status: str

    def __post_init__(self):
        object.__setattr__(self, "value", real(self.value, "Quantity.value"))
        nonempty(self.unit, "Quantity.unit")
        evidence_class(self.quantity_type, "Quantity.quantity_type")
        for f_ in ("source", "uncertainty", "applicability_domain", "validation_status"):
            nonempty(getattr(self, f_), f"Quantity.{f_}")

    def to_dict(self) -> dict:
        return {"value": self.value, "unit": self.unit, "quantity_type": self.quantity_type, "source": self.source,
                "uncertainty": self.uncertainty, "applicability_domain": self.applicability_domain,
                "validation_status": self.validation_status}


def value_of(q, what: str, unit: str | None = None) -> float:
    """Numeric value of a Quantity; a TBD (or anything else) raises. Unit is checked when given."""
    if isinstance(q, TBD):
        raise ContractError(f"{what} is TBD ({q.requires}); no default is substituted")
    if not isinstance(q, Quantity):
        raise ContractError(f"{what} must be a Quantity with evidence, got {type(q).__name__}")
    if unit is not None and q.unit != unit:
        raise ContractError(f"{what} must be in {unit!r}, got {q.unit!r}")
    return q.value


def serialise(v):
    """JSON-ready form of contract values (Quantity, TBD, Enum, FeedState, nested containers)."""
    if isinstance(v, (Quantity, TBD, FeedState)):
        return v.to_dict()
    if isinstance(v, Enum):
        return v.value
    if isinstance(v, Mapping):
        return {str(k): serialise(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [serialise(x) for x in v]
    return v


# ---------------------------------------------------------------------------------------------------- feed state

@dataclass(frozen=True)
class FeedState:
    """A propellant stream. ``mass_fractions`` must give every species in ``SPECIES`` explicitly (zeros allowed):
    there is no hidden default composition. Fractions are >= 0 and sum to 1 within ``FRACTION_SUM_TOL``."""
    mdot_total_kg_s: float
    pressure_Pa: float
    temperature_K: float
    mass_fractions: Mapping
    source: str
    evidence_class: str
    uncertainty: str
    applicability_domain: str
    validation_status: str

    def __post_init__(self):
        object.__setattr__(self, "mdot_total_kg_s", nonneg(self.mdot_total_kg_s, "FeedState.mdot_total_kg_s"))
        object.__setattr__(self, "pressure_Pa", positive(self.pressure_Pa, "FeedState.pressure_Pa"))
        object.__setattr__(self, "temperature_K", positive(self.temperature_K, "FeedState.temperature_K"))
        if not isinstance(self.mass_fractions, Mapping):
            raise ContractError("FeedState.mass_fractions must be a mapping species -> mass fraction")
        keys = set(self.mass_fractions)
        missing = [s for s in SPECIES if s not in keys]
        extra = sorted(str(k) for k in keys if k not in SPECIES)
        if missing or extra:
            raise ContractError(f"FeedState.mass_fractions must give exactly {SPECIES} (no hidden default "
                                f"composition); missing {missing}, extra {extra}")
        fr = {s: real(self.mass_fractions[s], f"mass fraction of {s}") for s in SPECIES}
        neg = [s for s, x in fr.items() if x < 0.0]
        if neg:
            raise ContractError(f"negative mass fractions for {neg}")
        total = math.fsum(fr.values())
        if abs(total - 1.0) > FRACTION_SUM_TOL:
            raise ContractError(f"mass fractions sum to {total!r}, not 1 (tolerance {FRACTION_SUM_TOL})")
        object.__setattr__(self, "mass_fractions", MappingProxyType(fr))
        nonempty(self.source, "FeedState.source")
        evidence_class(self.evidence_class, "FeedState.evidence_class")
        for f_ in ("uncertainty", "applicability_domain", "validation_status"):
            nonempty(getattr(self, f_), f"FeedState.{f_}")

    def species_mdot_kg_s(self) -> dict:
        return {s: self.mdot_total_kg_s * self.mass_fractions[s] for s in SPECIES}

    def is_pure_xe(self) -> bool:
        return self.mass_fractions["Xe"] == 1.0

    def has_xe(self) -> bool:
        return self.mass_fractions["Xe"] > 0.0

    def has_atmospheric(self) -> bool:
        return any(self.mass_fractions[s] > 0.0 for s in ATMOSPHERIC_SPECIES)

    def with_mdot(self, mdot_kg_s: float, *, source_suffix: str) -> "FeedState":
        """Same composition, pressure, temperature and evidence; a different mass flow (a split of this stream).
        The router uses this; it never changes composition (no implicit species separation)."""
        return FeedState(mdot_kg_s, self.pressure_Pa, self.temperature_K, dict(self.mass_fractions),
                         f"{self.source} | {source_suffix}", self.evidence_class, self.uncertainty,
                         self.applicability_domain, self.validation_status)

    def to_dict(self) -> dict:
        return {"mdot_total_kg_s": self.mdot_total_kg_s, "pressure_Pa": self.pressure_Pa,
                "temperature_K": self.temperature_K, "mass_fractions": dict(self.mass_fractions),
                "source": self.source, "evidence_class": self.evidence_class, "uncertainty": self.uncertainty,
                "applicability_domain": self.applicability_domain, "validation_status": self.validation_status}


def pure_xe_feed(mdot_kg_s: float, *, pressure_Pa: float, temperature_K: float, source: str, evidence_class_: str,
                 uncertainty: str, applicability_domain: str, validation_status: str) -> FeedState:
    """A pure-Xe stream; the composition is explicit (Xe = 1, others 0), not defaulted."""
    fr = {s: 0.0 for s in SPECIES}
    fr["Xe"] = 1.0
    return FeedState(mdot_kg_s, pressure_Pa, temperature_K, fr, source, evidence_class_, uncertainty,
                     applicability_domain, validation_status)


# ------------------------------------------------------------------------------------------- system constraints

LIMIT_ORIGINS = ("RFP_REQUIREMENT", "PROPOSED_ENGINEERING_ALLOCATION")


@dataclass(frozen=True)
class Limit:
    """A requirement or an internal allocation. ``origin`` keeps RFP requirements distinguishable from allocations."""
    value: float
    unit: str
    kind: str                     # "max" | "min"
    origin: str
    source: str
    verification_status: str

    def __post_init__(self):
        object.__setattr__(self, "value", real(self.value, "Limit.value"))
        nonempty(self.unit, "Limit.unit")
        if self.kind not in ("max", "min"):
            raise ContractError(f"Limit.kind must be 'max' or 'min', got {self.kind!r}")
        if self.origin not in LIMIT_ORIGINS:
            raise ContractError(f"Limit.origin must be one of {LIMIT_ORIGINS}, got {self.origin!r}")
        nonempty(self.source, "Limit.source")
        nonempty(self.verification_status, "Limit.verification_status")

    def satisfied_by(self, x: float) -> bool:
        """Strict for RFP '<' limits is handled by the caller's choice of kind; here max means x <= value."""
        return x <= self.value if self.kind == "max" else x >= self.value

    def to_dict(self) -> dict:
        return {"value": self.value, "unit": self.unit, "kind": self.kind, "origin": self.origin,
                "source": self.source, "verification_status": self.verification_status}


@dataclass(frozen=True)
class SystemConstraints:
    """Explicit constraint set (no scattered constants). ``power_hard_max_W`` etc. are RFP requirements;
    ``power_design_max_W`` / ``mass_design_max_kg`` are internal allocations (PROPOSED_ENGINEERING_ALLOCATION)."""
    thrust_min_N: Limit
    thrust_max_N: Limit
    power_hard_max_W: Limit
    power_design_max_W: Limit
    mass_hard_max_kg: Limit
    mass_design_max_kg: Limit
    firing_life_h: Limit
    mission_life_h: Limit
    allowed_modes: tuple
    power_hard_strict: bool = True        # RFP wording is '< 1.5 kW': equality fails
    mass_hard_strict: bool = True         # RFP wording is '< 40 kg'

    def __post_init__(self):
        for f_ in ("thrust_min_N", "thrust_max_N", "power_hard_max_W", "power_design_max_W", "mass_hard_max_kg",
                   "mass_design_max_kg", "firing_life_h", "mission_life_h"):
            if not isinstance(getattr(self, f_), Limit):
                raise ContractError(f"SystemConstraints.{f_} must be a Limit")
        for f_ in ("power_hard_max_W", "mass_hard_max_kg", "thrust_min_N", "thrust_max_N"):
            if getattr(self, f_).origin != "RFP_REQUIREMENT":
                raise ContractError(f"SystemConstraints.{f_} must be an RFP_REQUIREMENT")
        for f_ in ("power_design_max_W", "mass_design_max_kg"):
            if getattr(self, f_).origin != "PROPOSED_ENGINEERING_ALLOCATION":
                raise ContractError(f"SystemConstraints.{f_} must be a PROPOSED_ENGINEERING_ALLOCATION")
        if not self.allowed_modes:
            raise ContractError("SystemConstraints.allowed_modes must not be empty")

    def power_hard_ok(self, P_W: float) -> bool:
        v = self.power_hard_max_W.value
        return P_W < v if self.power_hard_strict else P_W <= v

    def mass_hard_ok(self, m_kg: float) -> bool:
        v = self.mass_hard_max_kg.value
        return m_kg < v if self.mass_hard_strict else m_kg <= v

    def to_dict(self) -> dict:
        d = {f_: getattr(self, f_).to_dict() for f_ in ("thrust_min_N", "thrust_max_N", "power_hard_max_W",
                                                        "power_design_max_W", "mass_hard_max_kg",
                                                        "mass_design_max_kg", "firing_life_h", "mission_life_h")}
        d["allowed_modes"] = [serialise(m) for m in self.allowed_modes]
        d["power_hard_strict"] = self.power_hard_strict
        d["mass_hard_strict"] = self.mass_hard_strict
        return d


_RFP_SRC = ("RFP DTDF/06/13516 envelope as transcribed in CLAUDE.md 'What this is'; the RFP document itself is not in "
            "the repository (docs/traceability/rtm_v1.json source_policy). News-text corroboration: "
            "docs/procurement/web_track_v1/threads/R2_rfp.md")
_RFP_STATUS = "SECONDARY_TRANSCRIPTION_VERIFY_AGAINST_RFP_DOCUMENT"
_ALLOC_SRC = "ABEP Parallel RF-Hall Simulation v2 specification sec. 18 / 23 (owner-supplied investigation targets)"


def investigation_constraints(allowed_modes: tuple) -> SystemConstraints:
    """The v2 investigation constraint set. RFP values carry their (secondary) provenance; the >15,000 h firing life is
    not found in any first-hand text (R2) and is flagged; the internal allocations are PROPOSED, not evidence."""
    return SystemConstraints(
        thrust_min_N=Limit(0.012, "N", "min", "RFP_REQUIREMENT", _RFP_SRC, _RFP_STATUS),
        thrust_max_N=Limit(0.025, "N", "max", "RFP_REQUIREMENT", _RFP_SRC,
                           _RFP_STATUS + "; meaning of the 12-25 mN range is owner decision OD1"),
        power_hard_max_W=Limit(1500.0, "W", "max", "RFP_REQUIREMENT", _RFP_SRC, _RFP_STATUS),
        power_design_max_W=Limit(1350.0, "W", "max", "PROPOSED_ENGINEERING_ALLOCATION", _ALLOC_SRC,
                                 "PROPOSED_ENGINEERING_ALLOCATION"),
        mass_hard_max_kg=Limit(40.0, "kg", "max", "RFP_REQUIREMENT", _RFP_SRC,
                               _RFP_STATUS + "; whether Xe is included is owner decision OD-XE-8"),
        mass_design_max_kg=Limit(35.0, "kg", "max", "PROPOSED_ENGINEERING_ALLOCATION", _ALLOC_SRC,
                                 "PROPOSED_ENGINEERING_ALLOCATION (wet design target; dry target 28 kg)"),
        firing_life_h=Limit(15000.0, "h", "min", "RFP_REQUIREMENT", _RFP_SRC,
                            _RFP_STATUS + "; NOT found in first-hand text (R2) - unverified"),
        mission_life_h=Limit(26000.0, "h", "min", "RFP_REQUIREMENT", _RFP_SRC,
                             _RFP_STATUS + "; news text says 'three years' (26,280 h)"),
        allowed_modes=tuple(allowed_modes),
    )
