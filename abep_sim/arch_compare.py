"""System-level architecture comparison harness (arch_compare_v1) — drop-in for ADMITTED Hall closures, not wired.

Compares the three Hall-accelerated architectures of the RFP chain ('hall_only', 'rf_hall', 'ecr_hall') on ONE common
electrical boundary (a bus-power ledger, ``bus_power_boundary_v1``) across EVERY admitted transport-ensemble member, and
reports per-member results plus min/max envelopes. Design and drop-in procedure:
docs/architecture_comparison/harness/HARNESS.md.

Pure orchestration. The module computes no physics of its own, does not modify or wire ``archengine``, ``hall_map`` or
``hall_ensemble``, and moves no golden benchmark. Everything it reports comes from four explicit sources:
  * the transport ensemble (``abep_sim.hall_ensemble``): the member set, admission gate (``require_admitted``) and the
    layer-1 calibration-nuisance names it must never use as an axis;
  * one ``abep_sim.hall_map.HallMap`` per (admitted member, architecture): Hall-discharge performance only;
  * an ``UpstreamState`` (intake -> filter -> compressor -> gas chamber -> valve), computed ONCE and identical for every
    member (built from ``archengine.gas_path_state`` or given explicitly);
  * a bus-power ledger ``ledger(arch, loads, efficiencies) -> {'boundary_version', 'architecture', 'P_bus_W', 'items',
    'residual_W'}``, by default ``abep_sim.arch_boundary.bus_power_ledger``, resolved lazily at call time.

Refusals (a HarnessError is raised; there is never a fallback):
  * zero admitted members — the state on 2026-09-26 (credible set = empty set, gate 3 FAIL);
  * any screening-candidate or unknown member id, a map filed under another member's id, a facility (non-flight) map;
  * a missing ledger module / wrong boundary version / ledger output that breaks the contract;
  * an energy-ledger residual >= 2 % of the bus power (CLAUDE.md rule 4), reported or independently recomputed;
  * any layer-1 calibration-nuisance name used as a Hall-map axis, operating-point key, feed or upstream quantity;
  * a Hall output name used as an upstream/feed quantity (Hall-closure uncertainty must never leak upstream).

Output: per-member, per-architecture results; per-architecture min/max envelopes over the members (unweighted scenario
set: no mean, no probability, no weighting); min/max envelopes of paired per-member differences between architectures.
There is deliberately no field that names a single preferred architecture.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import inspect
import json
import math
import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from numbers import Real
from types import MappingProxyType

from . import hall_ensemble, hall_map
from .constants import RFP

HARNESS_VERSION = "arch_compare_v1"
ARCHITECTURES = ("hall_only", "rf_hall", "ecr_hall")
EXPECTED_BOUNDARY_VERSION = "bus_power_boundary_v1"
LEDGER_MODULE = "abep_sim.arch_boundary"
LEDGER_FUNCTION = "bus_power_ledger"
LEDGER_PARAMETERS = ("arch", "loads", "efficiencies")
LEDGER_KEYS = ("boundary_version", "architecture", "P_bus_W", "items", "residual_W")
LEDGER_RESIDUAL_MAX_FRAC = 0.02          # CLAUDE.md rule 4: architecture energy-ledger residual < 2 %
MASS_CLOSURE_REL_TOL = 1e-9              # CLAUDE.md rule 4: source mass balance closes exactly (float rounding only)
HALL_MAP_INDEX_SCHEMA = "arch_compare_hall_map_index_v1"
SPECS_SCHEMA = "arch_compare_specs_v1"
UPSTREAM_SCHEMA = "arch_compare_upstream_v1"
# Naming conventions only (which ledger component receives which quantity); never numeric defaults.
DEFAULT_HALL_LOAD_FIELDS = {"hall_discharge": "discharge_power_W"}      # hall_map_schema_v1 field, unit W
DEFAULT_UPSTREAM_LOAD_FIELDS = {"compressor": "comp_power"}             # archengine.gas_path_state key (compressor P_el)
STATUS_OK = "OK"
STATUS_OUT_OF_MAP_DOMAIN = "OUT_OF_MAP_DOMAIN"
STATUS_UNTRUSTWORTHY = "UNTRUSTWORTHY_HALL_POINT"
STATUS_MODEL_ERROR = "MODEL_ERROR"
HALL_OUTPUTS_USED = ("thrust_N", "discharge_power_W", "discharge_current_A", "anode_eff")
PAIRED_METRICS = ("thrust_mN", "P_bus_W", "thrust_per_P_bus_mN_per_kW", "bus_to_anode_jet_efficiency",
                  "thrust_minus_drag_mN")


class HarnessError(RuntimeError):
    """The harness refuses instead of falling back."""


class NoAdmittedMembersError(HarnessError):
    """The transport ensemble has no admitted member (credible set empty): there is nothing to compare."""


class MemberRefusedError(HarnessError):
    """A screening candidate, an unknown id, or a map filed under the wrong member."""


class HallMapRefusedError(HarnessError):
    """A Hall map that HallMap or the harness refuses (schema, pin, facility, axes, reaction set)."""


class LedgerUnavailableError(HarnessError):
    """The bus-power ledger module is missing or does not implement the expected boundary version."""


class LedgerContractError(HarnessError):
    """Ledger output that breaks the {'boundary_version','architecture','P_bus_W','items','residual_W'} contract."""


class LedgerResidualError(LedgerContractError):
    """Energy-ledger residual >= 2 % of the bus power (CLAUDE.md rule 4)."""


class ScopeViolationError(HarnessError):
    """Layer-1 nuisance used as an axis/quantity, or Hall-closure quantities leaking upstream."""


class SpecError(HarnessError):
    """An architecture specification or upstream state that is incomplete or inconsistent."""


# ------------------------------------------------------------------------------------------------------ helpers
def _real(value, what: str, err=SpecError) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise err(f"{what} must be a real number, got {type(value).__name__} {value!r}")
    x = float(value)
    if not math.isfinite(x):
        raise err(f"{what} must be finite, got {x!r}")
    return x + 0.0


def _name(key, what: str) -> str:
    if not isinstance(key, str) or not key.strip():
        raise SpecError(f"{what}: names must be non-empty strings, got {key!r}")
    return key


def _real_map(m, what: str, *, lo: float | None = None, hi: float | None = None, lo_open: bool = False) -> Mapping:
    if not isinstance(m, Mapping):
        raise SpecError(f"{what} must be a mapping, got {type(m).__name__}")
    out = {}
    for k, v in m.items():
        x = _real(v, f"{what}[{_name(k, what)!r}]")
        if lo is not None and (x < lo or (lo_open and x == lo)):
            raise SpecError(f"{what}[{k!r}] = {x!r} below its allowed range")
        if hi is not None and x > hi:
            raise SpecError(f"{what}[{k!r}] = {x!r} above its allowed range")
        out[k] = x
    return MappingProxyType(out)


def _str_map(m, what: str) -> Mapping:
    if not isinstance(m, Mapping):
        raise SpecError(f"{what} must be a mapping, got {type(m).__name__}")
    return MappingProxyType({_name(k, what): _name(v, what) for k, v in m.items()})


def _plain(x):
    """JSON-ready deep copy (mappings -> dict, sequences -> list)."""
    if isinstance(x, Mapping):
        return {str(k): _plain(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_plain(v) for v in x]
    if isinstance(x, bool) or x is None or isinstance(x, str):
        return x
    if isinstance(x, Real):
        return float(x) if not isinstance(x, int) else int(x)
    raise HarnessError(f"value of type {type(x).__name__} is not reportable")


def _canonical_sha256(obj) -> str:
    return hashlib.sha256(json.dumps(_plain(obj), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _file_sha256(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _is_sha256(s) -> bool:
    return isinstance(s, str) and len(s) == 64 and all(c in "0123456789abcdef" for c in s)


# ------------------------------------------------------------------------------------------------------ inputs
@dataclass(frozen=True)
class UpstreamState:
    """Member-independent gas-path state (atmospheric path: intake -> filter -> compressor -> gas chamber -> valve).

    Computed once per comparison and used unchanged for every member and architecture: Hall-closure uncertainty never
    reaches it. ``source`` records how the numbers were obtained (a module call or a cited source). ``drag_N`` is the
    optional spacecraft drag at the same atmospheric state; without it the thrust-minus-drag metrics are not reported."""
    quantities: Mapping
    source: str
    labels: Mapping = field(default_factory=dict)
    drag_N: float | None = None
    drag_source: str | None = None

    def __post_init__(self):
        q = _real_map(self.quantities, "upstream quantities")
        if not q:
            raise SpecError("upstream quantities are empty")
        object.__setattr__(self, "quantities", q)
        object.__setattr__(self, "labels", _str_map(self.labels, "upstream labels"))
        if not isinstance(self.source, str) or not self.source.strip():
            raise SpecError("upstream source (provenance of the gas-path numbers) is required")
        if self.drag_N is not None:
            d = _real(self.drag_N, "drag_N")
            if d <= 0.0:
                raise SpecError(f"drag_N must be > 0, got {d!r}")
            if not isinstance(self.drag_source, str) or not self.drag_source.strip():
                raise SpecError("drag_N needs drag_source (how the drag was obtained)")
            object.__setattr__(self, "drag_N", d)
        elif self.drag_source is not None:
            raise SpecError("drag_source given without drag_N")

    def to_dict(self) -> dict:
        return {"quantities": dict(self.quantities), "labels": dict(self.labels), "source": self.source,
                "drag_N": self.drag_N, "drag_source": self.drag_source}

    def fingerprint(self) -> str:
        return _canonical_sha256(self.to_dict())

    @classmethod
    def from_gas_path(cls, gas: Mapping, source: str, drag_N: float | None = None,
                      drag_source: str | None = None) -> "UpstreamState":
        """From an ``archengine.gas_path_state`` dict: numbers become quantities, strings become labels, and any other
        type is refused (nothing is dropped silently)."""
        if not isinstance(gas, Mapping):
            raise SpecError("gas-path state must be a mapping")
        # G-03..G-05 (A9.9 S2.4): a non-converged gas-path state is refused (fail closed). The convergence labels
        # are consumed here and not carried into the upstream state, so converged fingerprints are unchanged.
        status = gas.get("gaspath_status", "CONVERGED")
        if status != "CONVERGED":
            raise SpecError(f"gas-path state not admissible: gaspath_status={status!r} "
                            f"(not converged: {gas.get('gaspath_not_converged', '')!r})")
        gas = {k: v for k, v in gas.items() if k not in ("gaspath_status", "gaspath_not_converged")}
        q = {k: v for k, v in gas.items() if isinstance(v, Real) and not isinstance(v, bool)}
        labels = {k: v for k, v in gas.items() if isinstance(v, str)}
        other = sorted(str(k) for k in gas if k not in q and k not in labels)
        if other:
            raise SpecError(f"gas-path fields of unsupported type (not dropped silently): {other}")
        return cls(q, source, labels, drag_N, drag_source)


def upstream_from_archengine(*, area_m2: float, alpha: float, L_over_d: float, alt_km: float, solar: str,
                             blade_coating_um: float, p_target_Pa: float | None = None,
                             p_margin_over_pmin: float | None = None, drag_N: float | None = None,
                             drag_source: str | None = None) -> UpstreamState:
    """Run the existing gas-path entry point ``abep_sim.archengine.gas_path_state`` (Phases 1-2: frozen NRLMSIS,
    TPMC intake, drag compressor, reservoir) once. No argument has a default: the caller names the design point.
    Exactly one of ``p_target_Pa`` (absolute reservoir pressure, architecture-neutral) or ``p_margin_over_pmin``."""
    if (p_target_Pa is None) == (p_margin_over_pmin is None):
        raise SpecError("give exactly one of p_target_Pa or p_margin_over_pmin")
    from .archengine import gas_path_state
    args = dict(area_m2=_real(area_m2, "area_m2"), alpha=_real(alpha, "alpha"), L_over_d=_real(L_over_d, "L_over_d"),
                alt=_real(alt_km, "alt_km"), solar=_name(solar, "solar"),
                blade_coating_um=_real(blade_coating_um, "blade_coating_um"))
    if p_target_Pa is not None:
        args["p_target"] = _real(p_target_Pa, "p_target_Pa")
    else:
        args["p_margin"] = _real(p_margin_over_pmin, "p_margin_over_pmin")
    gas = gas_path_state(**args)
    src = "abep_sim.archengine.gas_path_state(" + ", ".join(f"{k}={v!r}" for k, v in args.items()) + ")"
    return UpstreamState.from_gas_path(gas, src, drag_N, drag_source)


@dataclass(frozen=True)
class ArchitectureSpec:
    """One architecture's design point on the common boundary. Everything here is member-independent.

    hall_operating_point  design values of Hall-map axes (e.g. a discharge voltage), axis -> value
    hall_axis_bindings    Hall-map axes taken from the member-independent state, axis -> quantity name in
                          UpstreamState.quantities or in ``feed`` (e.g. the anode mass flow)
    feed                  architecture-specific member-independent quantities upstream of the Hall channel (e.g. a
                          pre-ionizer output or a flow split); names must not repeat an upstream quantity
    fixed_loads_W         every ledger component load not taken from the Hall map or the upstream state [W]
    efficiencies          bus-to-load efficiency of every ledger component, in (0, 1]
    hall_load_fields      ledger component -> Hall-map field (unit W) supplying its load
    upstream_load_fields  ledger component -> upstream quantity supplying its load (compressor electrical input)
    mass_closure          optional {'supply': [...], 'hall_axes': [...], 'other_sinks': [...]}: sum(supply) must equal
                          sum(hall axes) + sum(other sinks) exactly (names: upstream/feed quantities; Hall-map axes)
    source                provenance of every number in this spec (cited, or 'TBD'-free explicit statement)"""
    arch: str
    hall_operating_point: Mapping
    hall_axis_bindings: Mapping
    fixed_loads_W: Mapping
    efficiencies: Mapping
    source: str
    feed: Mapping = field(default_factory=dict)
    hall_load_fields: Mapping = field(default_factory=lambda: dict(DEFAULT_HALL_LOAD_FIELDS))
    upstream_load_fields: Mapping = field(default_factory=lambda: dict(DEFAULT_UPSTREAM_LOAD_FIELDS))
    mass_closure: Mapping | None = None

    def __post_init__(self):
        if self.arch not in ARCHITECTURES:
            raise SpecError(f"unknown architecture {self.arch!r}; the harness compares {list(ARCHITECTURES)}")
        a = self.arch
        set_ = lambda k, v: object.__setattr__(self, k, v)
        set_("hall_operating_point", _real_map(self.hall_operating_point, f"{a}: hall_operating_point"))
        set_("hall_axis_bindings", _str_map(self.hall_axis_bindings, f"{a}: hall_axis_bindings"))
        set_("fixed_loads_W", _real_map(self.fixed_loads_W, f"{a}: fixed_loads_W", lo=0.0))
        set_("efficiencies", _real_map(self.efficiencies, f"{a}: efficiencies", lo=0.0, hi=1.0, lo_open=True))
        set_("feed", _real_map(self.feed, f"{a}: feed"))
        set_("hall_load_fields", _str_map(self.hall_load_fields, f"{a}: hall_load_fields"))
        set_("upstream_load_fields", _str_map(self.upstream_load_fields, f"{a}: upstream_load_fields"))
        if not isinstance(self.source, str) or not self.source.strip():
            raise SpecError(f"{a}: source (provenance of loads, efficiencies and design point) is required")
        both = set(self.hall_operating_point) & set(self.hall_axis_bindings)
        if both:
            raise SpecError(f"{a}: axes {sorted(both)} given both as design values and as bindings")
        if not self.hall_load_fields:
            raise SpecError(f"{a}: at least one ledger component must take its load from the Hall map")
        for comp, f in self.hall_load_fields.items():
            fs = hall_map.SCHEMA["fields"].get(f)
            if fs is None or fs["type"] != "float" or fs["unit"] != "W":
                raise SpecError(f"{a}: hall_load_fields[{comp!r}] = {f!r} is not a hall_map_schema_v1 power field (W)")
        groups = {"fixed_loads_W": set(self.fixed_loads_W), "hall_load_fields": set(self.hall_load_fields),
                  "upstream_load_fields": set(self.upstream_load_fields)}
        names = list(groups)
        for i, g1 in enumerate(names):
            for g2 in names[i + 1:]:
                dup = groups[g1] & groups[g2]
                if dup:
                    raise SpecError(f"{a}: ledger components {sorted(dup)} supplied by both {g1} and {g2}")
        if self.mass_closure is not None:
            mc = self.mass_closure
            if not isinstance(mc, Mapping) or set(mc) != {"supply", "hall_axes", "other_sinks"}:
                raise SpecError(f"{a}: mass_closure needs exactly the keys supply, hall_axes, other_sinks")
            frozen = {}
            for k in ("supply", "hall_axes", "other_sinks"):
                v = mc[k]
                if isinstance(v, str) or not isinstance(v, Sequence):
                    raise SpecError(f"{a}: mass_closure[{k!r}] must be a list of names")
                frozen[k] = tuple(_name(n, f"{a}: mass_closure[{k!r}]") for n in v)
            if not frozen["supply"] or not frozen["hall_axes"]:
                raise SpecError(f"{a}: mass_closure needs at least one supply and one Hall-map axis")
            set_("mass_closure", MappingProxyType(frozen))

    def to_dict(self) -> dict:
        return _plain({"arch": self.arch, "hall_operating_point": self.hall_operating_point,
                       "hall_axis_bindings": self.hall_axis_bindings, "feed": self.feed,
                       "fixed_loads_W": self.fixed_loads_W, "efficiencies": self.efficiencies,
                       "hall_load_fields": self.hall_load_fields, "upstream_load_fields": self.upstream_load_fields,
                       "mass_closure": self.mass_closure, "source": self.source})


# ------------------------------------------------------------------------------------------------------ gates
def resolve_ensemble(ensemble: Mapping | None = None) -> tuple[Mapping, dict]:
    """The frozen ensemble file (full admission verification by ``hall_ensemble.load_ensemble``), or an injected one
    (tests only; recorded as such and never on the production path)."""
    if ensemble is None:
        e = hall_ensemble.load_ensemble()
        path = hall_ensemble.ENSEMBLE_FILE
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        info = {"origin": "frozen_file", "path": os.path.relpath(path, root), "sha256": _file_sha256(path)}
    else:
        if not isinstance(ensemble, Mapping) or "members" not in ensemble or "calibration_nuisance" not in ensemble:
            raise HarnessError("an injected ensemble must be a transport-ensemble mapping (members, calibration_nuisance)")
        e = ensemble
        info = {"origin": "injected", "path": None, "sha256": None}
    if e.get("weighting") != "unweighted":
        raise HarnessError("the transport ensemble must be an unweighted scenario set (CLAUDE.md next-work 1)")
    return e, info


def admitted_members(ensemble: Mapping) -> list[str]:
    """Every admitted member, each passed through ``hall_ensemble.require_admitted``; refuses when there is none."""
    ids = sorted(hall_ensemble.member_ids(ensemble))
    if not ids:
        n_screen = len(hall_ensemble.screening_ids(ensemble))
        raise NoAdmittedMembersError(
            "architecture comparison refused: the transport ensemble has zero ADMITTED members (credible set is empty; "
            f"{n_screen} screening candidates exist, and screening candidates never produce design Hall maps and never "
            "enter the architecture trade). There is no fallback: members enter only through the evidence-based "
            "admission path (hall_ensemble admission record + O4 dispositions), see "
            "docs/architecture_comparison/harness/HARNESS.md.")
    for mid in ids:
        _require_admitted(mid, ensemble, "admitted member")
    return ids


def _require_admitted(mid, ensemble: Mapping, where: str) -> None:
    if not isinstance(mid, str):
        raise MemberRefusedError(f"{where}: member id must be a string, got {mid!r}")
    try:
        hall_ensemble.require_admitted(mid, ensemble)
    except ValueError as e:
        raise MemberRefusedError(f"{where} {mid!r} refused: {e}") from None


def resolve_ledger(ledger=None, expected_boundary_version: str = EXPECTED_BOUNDARY_VERSION):
    """Injected ledger, or ``abep_sim.arch_boundary.bus_power_ledger`` imported now (lazily). A missing module or a
    module declaring another BOUNDARY_VERSION raises LedgerUnavailableError; there is no built-in substitute."""
    module_version = None
    if ledger is None:
        try:
            mod = importlib.import_module(LEDGER_MODULE)
        except ModuleNotFoundError as e:
            if e.name != LEDGER_MODULE:
                raise                                       # a dependency of the module is missing: surface it as is
            raise LedgerUnavailableError(
                f"bus-power ledger unavailable: {LEDGER_MODULE} is not installed in this checkout ({e}). The harness "
                f"has no substitute ledger; merge the {expected_boundary_version} boundary module or inject a ledger "
                "with the signature ledger(arch, loads, efficiencies) -> dict.") from None
        fn = getattr(mod, LEDGER_FUNCTION, None)
        if not callable(fn):
            raise LedgerUnavailableError(f"{LEDGER_MODULE} has no callable {LEDGER_FUNCTION}")
        module_version = getattr(mod, "BOUNDARY_VERSION", None)
        if module_version != expected_boundary_version:
            raise LedgerUnavailableError(f"{LEDGER_MODULE}.BOUNDARY_VERSION is {module_version!r}, the harness expects "
                                         f"{expected_boundary_version!r}")
        origin = f"{LEDGER_MODULE}.{LEDGER_FUNCTION}"
    else:
        fn, origin = ledger, "injected"
        if not callable(fn):
            raise LedgerContractError("the injected ledger is not callable")
    try:
        params = list(inspect.signature(fn).parameters.values())
    except (TypeError, ValueError) as e:
        raise LedgerContractError(f"ledger signature cannot be inspected: {e}") from None
    if tuple(p.name for p in params) != LEDGER_PARAMETERS or \
            any(p.kind is not inspect.Parameter.POSITIONAL_OR_KEYWORD for p in params):
        raise LedgerContractError(f"ledger signature must be exactly ledger{LEDGER_PARAMETERS}, got "
                                  f"{inspect.signature(fn)}")
    return fn, {"origin": origin, "expected_boundary_version": expected_boundary_version,
                "module_boundary_version": module_version}


def _scope_checks(specs, upstream: UpstreamState, nuisance: set) -> None:
    """Layer-1 nuisance is never an axis or input; Hall outputs never enter the upstream/feed state."""
    hall_fields = set(hall_map.REQUIRED_FIELDS)
    for k in list(upstream.quantities) + list(upstream.labels):
        if k in nuisance:
            raise ScopeViolationError(f"upstream quantity {k!r} is a layer-1 calibration-nuisance variable")
        if k in hall_fields:
            raise ScopeViolationError(f"upstream quantity {k!r} is a Hall-map output: Hall-closure results must never "
                                      "feed the intake/compressor/gas-chamber/valve state")
    for s in specs:
        named = {"hall_operating_point": set(s.hall_operating_point), "hall_axis_bindings": set(s.hall_axis_bindings),
                 "feed": set(s.feed)}
        for what, keys in named.items():
            bad = keys & nuisance
            if bad:
                raise ScopeViolationError(f"{s.arch}: {what} uses layer-1 calibration-nuisance variables {sorted(bad)}")
        bad = set(s.feed) & hall_fields
        if bad:
            raise ScopeViolationError(f"{s.arch}: feed quantities {sorted(bad)} are Hall-map outputs")
        dup = set(s.feed) & set(upstream.quantities)
        if dup:
            raise SpecError(f"{s.arch}: feed quantities {sorted(dup)} repeat upstream quantities (ambiguous source)")
        state = set(upstream.quantities) | set(s.feed)
        unknown = sorted(v for v in s.hall_axis_bindings.values() if v not in state)
        if unknown:
            raise SpecError(f"{s.arch}: hall_axis_bindings reference unknown quantities {unknown}")
        unknown = sorted(v for v in s.upstream_load_fields.values() if v not in upstream.quantities)
        if unknown:
            raise SpecError(f"{s.arch}: upstream_load_fields reference unknown upstream quantities {unknown}")
        for comp, qname in s.upstream_load_fields.items():
            if upstream.quantities[qname] < 0.0:
                raise SpecError(f"{s.arch}: upstream load {comp!r} <- {qname!r} is negative")
        if s.mass_closure is not None:
            for k in ("supply", "other_sinks"):
                unknown = sorted(n for n in s.mass_closure[k] if n not in state)
                if unknown:
                    raise SpecError(f"{s.arch}: mass_closure[{k!r}] references unknown quantities {unknown}")
            unknown = sorted(n for n in s.mass_closure["hall_axes"]
                             if n not in s.hall_operating_point and n not in s.hall_axis_bindings)
            if unknown:
                raise SpecError(f"{s.arch}: mass_closure['hall_axes'] names axes the spec does not set: {unknown}")


def _hall_query(spec: ArchitectureSpec, upstream: UpstreamState) -> dict:
    """The Hall-map query is member-independent: design values plus bound upstream/feed quantities."""
    state = {**upstream.quantities, **spec.feed}
    q = dict(spec.hall_operating_point)
    q.update({axis: state[name] for axis, name in spec.hall_axis_bindings.items()})
    return q


def _mass_closure(spec: ArchitectureSpec, upstream: UpstreamState, query: dict) -> dict:
    if spec.mass_closure is None:
        return {"declared": False, "note": "no mass closure declared for this architecture; not checked"}
    state = {**upstream.quantities, **spec.feed}
    supply = math.fsum(state[n] for n in spec.mass_closure["supply"])
    consumed = math.fsum(query[a] for a in spec.mass_closure["hall_axes"]) + \
        math.fsum(state[n] for n in spec.mass_closure["other_sinks"])
    resid = supply - consumed
    scale = max(abs(supply), abs(consumed))
    if scale <= 0.0 or abs(resid) > MASS_CLOSURE_REL_TOL * scale:
        raise SpecError(f"{spec.arch}: mass closure fails: supply {supply!r} vs Hall axes + other sinks {consumed!r} "
                        f"(residual {resid!r}; CLAUDE.md rule 4)")
    return {"declared": True, "supply": supply, "consumed": consumed, "residual": resid,
            "names": _plain(spec.mass_closure)}


# ------------------------------------------------------------------------------------------------------ Hall maps
def _map_entry(entry, where: str) -> tuple[str, str | None]:
    if isinstance(entry, Mapping):
        if set(entry) != {"path", "sha256"} or not _is_sha256(entry["sha256"]):
            raise HallMapRefusedError(f"{where}: a map entry is a path or {{'path', 'sha256'}} with a hex sha256")
        return os.fspath(entry["path"]), entry["sha256"]
    if isinstance(entry, (str, os.PathLike)):
        return os.fspath(entry), None
    raise HallMapRefusedError(f"{where}: Hall maps are given as file paths (HallMap is constructed by the harness)")


def _load_map(mid: str, arch: str, entry, ensemble: Mapping):
    where = f"Hall map for member {mid!r}, architecture {arch!r}"
    path, expected = _map_entry(entry, where)
    if not os.path.isfile(path):
        raise HallMapRefusedError(f"{where}: file {path!r} not found")
    sha = _file_sha256(path)
    if expected is not None and sha != expected:
        raise HallMapRefusedError(f"{where}: sha256 {sha} differs from the recorded {expected}")
    try:
        hm = hall_map.HallMap(path, ensemble=ensemble)
    except ValueError as e:
        raise HallMapRefusedError(f"{where}: {e}") from None
    meta = hm.meta
    if meta["ensemble_member_id"] != mid:
        raise MemberRefusedError(f"{where}: map was produced by member {meta['ensemble_member_id']!r}, not {mid!r}")
    _require_admitted(meta["ensemble_member_id"], ensemble, f"{where}: meta.ensemble_member_id")
    if meta.get("facility_ingestion") is not False:
        raise HallMapRefusedError(f"{where}: meta.facility_ingestion must be false (flight map), got "
                                  f"{meta.get('facility_ingestion')!r}")
    prov = {"path": path, "sha256": sha, "sha256_verified_against_record": expected is not None,
            "ensemble_member_id": mid, "transport": str(meta["transport"]), "reaction_set": str(meta["reaction_set"]),
            "hallthruster_commit": str(meta["hallthruster_commit"]), "axes": list(hm.names)}
    return hm, prov


def _check_maps(maps: dict, specs, ids) -> str:
    """Every member's map of an architecture has exactly the axes the spec sets (hence the same query for every
    member), and the whole comparison uses one reaction set."""
    reaction_sets = set()
    for s in specs:
        wanted = set(s.hall_operating_point) | set(s.hall_axis_bindings)
        for mid in ids:
            hm, prov = maps[mid][s.arch]
            reaction_sets.add(prov["reaction_set"])
            if set(hm.names) != wanted:
                raise HallMapRefusedError(
                    f"member {mid!r}, {s.arch}: map axes {sorted(hm.names)} differ from the axes the spec sets "
                    f"{sorted(wanted)} (every axis needs exactly one design value or binding; no extra keys)")
    if len(reaction_sets) != 1:
        raise HallMapRefusedError(f"maps use different reaction sets {sorted(reaction_sets)}: one comparison uses one "
                                  "chemistry basis")
    return reaction_sets.pop()


# ------------------------------------------------------------------------------------------------------ ledger
def _ledger_items(items, arch: str) -> dict:
    rows = []
    if isinstance(items, Mapping):
        for comp, it in items.items():
            if not isinstance(it, Mapping):
                raise LedgerContractError(f"{arch}: ledger item {comp!r} is not a mapping")
            rows.append((comp, it))
    elif isinstance(items, Sequence) and not isinstance(items, str):
        for it in items:
            if not isinstance(it, Mapping) or "component" not in it:
                raise LedgerContractError(f"{arch}: ledger items must be mappings carrying 'component'")
            rows.append((it["component"], it))
    else:
        raise LedgerContractError(f"{arch}: ledger 'items' must itemize the bus draw per component")
    out = {}
    for comp, it in rows:
        if not isinstance(comp, str) or comp in out:
            raise LedgerContractError(f"{arch}: ledger item component {comp!r} invalid or repeated")
        if "P_bus_W" not in it:
            raise LedgerContractError(f"{arch}: ledger item {comp!r} has no P_bus_W")
        p = _real(it["P_bus_W"], f"{arch}: ledger item {comp!r} P_bus_W", LedgerContractError)
        if p < 0.0:
            raise LedgerContractError(f"{arch}: ledger item {comp!r} has a negative bus draw")
        out[comp] = p
    return out


def _run_ledger(fn, arch: str, loads: dict, efficiencies: dict, expected_version: str, mid: str) -> dict:
    try:
        out = fn(arch, dict(loads), dict(efficiencies))
    except Exception as e:                   # the ledger's own refusal, with the harness context attached
        raise LedgerContractError(f"ledger refused {arch!r} for member {mid!r}: {type(e).__name__}: {e}") from e
    if not isinstance(out, Mapping):
        raise LedgerContractError(f"{arch}: ledger returned {type(out).__name__}, not a mapping")
    missing = [k for k in LEDGER_KEYS if k not in out]
    if missing:
        raise LedgerContractError(f"{arch}: ledger output missing {missing}")
    if out["boundary_version"] != expected_version:
        raise LedgerContractError(f"{arch}: ledger boundary_version {out['boundary_version']!r} is not the common "
                                  f"boundary {expected_version!r}")
    if out["architecture"] != arch:
        raise LedgerContractError(f"ledger answered for {out['architecture']!r} when asked for {arch!r}")
    P_bus = _real(out["P_bus_W"], f"{arch}: ledger P_bus_W", LedgerContractError)
    resid = _real(out["residual_W"], f"{arch}: ledger residual_W", LedgerContractError)
    if P_bus <= 0.0:
        raise LedgerContractError(f"{arch}: ledger P_bus_W must be > 0, got {P_bus!r}")
    items = _ledger_items(out["items"], arch)
    if set(items) != set(loads):
        raise LedgerContractError(f"{arch}: ledger items {sorted(items)} do not book exactly the supplied loads "
                                  f"{sorted(loads)}")
    delivered = math.fsum(loads.values())
    if P_bus < delivered * (1.0 - 1e-12):
        raise LedgerContractError(f"{arch}: bus power {P_bus!r} W below the delivered load {delivered!r} W")
    resid_re = P_bus - math.fsum(items.values())          # independent: bus total minus the itemized bus draws
    frac, frac_re = resid / P_bus, resid_re / P_bus
    if not (abs(frac) < LEDGER_RESIDUAL_MAX_FRAC and abs(frac_re) < LEDGER_RESIDUAL_MAX_FRAC):
        raise LedgerResidualError(
            f"{arch} (member {mid!r}): energy-ledger residual {frac:+.3%} reported, {frac_re:+.3%} recomputed from the "
            f"items; the gate is < {LEDGER_RESIDUAL_MAX_FRAC:.0%} of P_bus (CLAUDE.md rule 4)")
    return {"ledger": _plain(out), "P_bus_W": P_bus, "residual_W": resid, "residual_frac": frac,
            "residual_recomputed_W": resid_re, "residual_recomputed_frac": frac_re, "components": sorted(items),
            "residual_gate_frac": LEDGER_RESIDUAL_MAX_FRAC}


# ------------------------------------------------------------------------------------------------------ evaluation
def _evaluate(mid: str, spec: ArchitectureSpec, hm, prov: dict, query: dict, upstream: UpstreamState, fn,
              expected_version: str) -> dict:
    res = {"status": None, "reason": None, "hall_query": dict(query), "hall_map": prov,
           "upstream_fingerprint": upstream.fingerprint()}
    outside = {k: [float(hm.axes[k][0]), float(hm.axes[k][-1])] for k in hm.names
               if not (hm.axes[k][0] - 1e-12 <= query[k] <= hm.axes[k][-1] + 1e-12)}
    if outside:
        res.update(status=STATUS_OUT_OF_MAP_DOMAIN, reason=f"query outside the map axes {outside} (no extrapolation)")
        return res
    out = hm(**query)
    res["trust"] = {"trustworthy": bool(out["trustworthy"]), "wall_life_trustworthy": bool(out["wall_life_trustworthy"])}
    if not out["trustworthy"]:
        res.update(status=STATUS_UNTRUSTWORTHY, reason="HallMap marks the point untrustworthy (unconverged, not "
                   "sustained or chemistry outside its validity domain at a surrounding node); no numbers reported")
        return res
    used = set(HALL_OUTPUTS_USED) | set(spec.hall_load_fields.values())
    bad = sorted(k for k in used if not math.isfinite(out[k]))
    T, Pd, eta_a = out["thrust_N"], out["discharge_power_W"], out["anode_eff"]
    if bad or T < 0.0 or Pd <= 0.0 or not (0.0 <= eta_a <= 1.0) or \
            any(out[f] < 0.0 for f in spec.hall_load_fields.values()):
        res.update(status=STATUS_MODEL_ERROR, reason=f"map values violate physical bounds (non-finite {bad}, thrust "
                   f"{T!r} N, discharge power {Pd!r} W, anode efficiency {eta_a!r}); anode jet power T^2/(2 mdot_a) "
                   "cannot exceed the discharge power")
        return res
    hall_loads = {comp: out[f] for comp, f in spec.hall_load_fields.items()}
    upstream_loads = {comp: upstream.quantities[q] for comp, q in spec.upstream_load_fields.items()}
    loads = {**spec.fixed_loads_W, **upstream_loads, **hall_loads}
    led = _run_ledger(fn, spec.arch, loads, dict(spec.efficiencies), expected_version, mid)
    P_bus = led["P_bus_W"]
    metrics = {"thrust_mN": T * 1e3, "discharge_power_W": Pd, "discharge_current_A": out["discharge_current_A"],
               "anode_eff": eta_a, "anode_jet_power_W": eta_a * Pd, "P_bus_W": P_bus,
               "thrust_per_P_bus_mN_per_kW": T * 1e3 / (P_bus / 1e3), "bus_to_anode_jet_efficiency": eta_a * Pd / P_bus}
    flags = {"thrust_within_rfp_range": RFP.thrust_min_mN <= T * 1e3 <= RFP.thrust_max_mN,
             "P_bus_within_rfp_cap": P_bus <= RFP.power_max_W}
    if upstream.drag_N is not None:
        metrics["thrust_minus_drag_mN"] = (T - upstream.drag_N) * 1e3
        metrics["thrust_to_drag"] = T / upstream.drag_N
        flags["thrust_exceeds_drag"] = T > upstream.drag_N
    res.update(status=STATUS_OK, hall={k: v for k, v in out.items()}, member_independent_loads_W=_plain(
        {**spec.fixed_loads_W, **upstream_loads}), hall_loads_W=hall_loads, efficiencies=dict(spec.efficiencies),
        bus_ledger=led, metrics=metrics, rfp_flags=flags)
    return res


def _envelope(arch: str, ids: list, results: dict) -> dict:
    rows = {mid: results[mid][arch] for mid in ids}
    counts = {}
    for r in rows.values():
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    not_ok = {mid: r["status"] for mid, r in rows.items() if r["status"] != STATUS_OK}
    env = {"n_members": len(ids), "status_counts": counts, "not_ok_members": not_ok}
    if not_ok:
        env.update(status="INCOMPLETE", metrics=None, constraint_robustness=None,
                   note="at least one admitted member has no OK result: no envelope is reported over a subset")
        return env
    keys = set.intersection(*(set(r["metrics"]) for r in rows.values()))
    env["metrics"] = {k: {"min": min(r["metrics"][k] for r in rows.values()),
                          "max": max(r["metrics"][k] for r in rows.values())} for k in sorted(keys)}
    flags = set.intersection(*(set(r["rfp_flags"]) for r in rows.values()))
    env["constraint_robustness"] = {
        f: {"n_true": sum(bool(r["rfp_flags"][f]) for r in rows.values()), "n_members": len(ids),
            "holds_for_all_members": all(bool(r["rfp_flags"][f]) for r in rows.values())} for f in sorted(flags)}
    env["status"] = "COMPLETE"
    return env


def _paired(archs: list, ids: list, results: dict, envelopes: dict) -> dict:
    """Min/max over members of the per-member difference (a - b); same member, same upstream state on both sides."""
    out = {}
    for i, a in enumerate(archs):
        for b in archs[i + 1:]:
            key = f"{a}_minus_{b}"
            if envelopes[a]["status"] != "COMPLETE" or envelopes[b]["status"] != "COMPLETE":
                out[key] = {"status": "INCOMPLETE", "metrics": None}
                continue
            m = {}
            for k in PAIRED_METRICS:
                if all(k in results[mid][a]["metrics"] and k in results[mid][b]["metrics"] for mid in ids):
                    d = [results[mid][a]["metrics"][k] - results[mid][b]["metrics"][k] for mid in ids]
                    m[k] = {"min": min(d), "max": max(d)}
            out[key] = {"status": "COMPLETE", "n_members": len(ids), "metrics": m}
    return out


def compare_architectures(specs, upstream: UpstreamState, hall_maps: Mapping, *, ledger=None,
                          ensemble: Mapping | None = None,
                          expected_boundary_version: str = EXPECTED_BOUNDARY_VERSION) -> dict:
    """Evaluate every spec'd architecture for EVERY admitted member on the common bus boundary.

    specs      ArchitectureSpec per architecture (subset of ARCHITECTURES, no repeats)
    upstream   UpstreamState, identical for all members and architectures
    hall_maps  {member_id: {arch: path | {'path', 'sha256'}}}; keys must be exactly the admitted members
    ledger     None -> abep_sim.arch_boundary.bus_power_ledger (imported now); or an injected callable
    ensemble   None -> the frozen ensemble file via hall_ensemble.load_ensemble(); an injected mapping is for tests
    """
    ens, ens_info = resolve_ensemble(ensemble)
    ids = admitted_members(ens)                                       # refuses on an empty credible set
    if not isinstance(specs, Sequence) or isinstance(specs, str) or not specs:
        raise SpecError("specs must be a non-empty list of ArchitectureSpec")
    if not all(isinstance(s, ArchitectureSpec) for s in specs):
        raise SpecError("every spec must be an ArchitectureSpec")
    archs = [s.arch for s in specs]
    if len(set(archs)) != len(archs):
        raise SpecError(f"architectures repeated in specs: {archs}")
    specs = sorted(specs, key=lambda s: ARCHITECTURES.index(s.arch))
    archs = [s.arch for s in specs]
    if not isinstance(upstream, UpstreamState):
        raise SpecError("upstream must be an UpstreamState")
    nuisance = set(ens["calibration_nuisance"])
    _scope_checks(specs, upstream, nuisance)
    if not isinstance(hall_maps, Mapping):
        raise HallMapRefusedError("hall_maps must be a mapping {member_id: {arch: map path}}")
    for key in hall_maps:
        _require_admitted(key, ens, "hall_maps key")
    missing = [mid for mid in ids if mid not in hall_maps]
    if missing:
        raise MemberRefusedError(f"no Hall maps for admitted members {missing}: every admitted member enters the "
                                 "comparison (no subset, no cherry-picking)")
    fn, ledger_info = resolve_ledger(ledger, expected_boundary_version)
    fp0 = upstream.fingerprint()
    queries = {s.arch: _hall_query(s, upstream) for s in specs}
    closures = {s.arch: _mass_closure(s, upstream, queries[s.arch]) for s in specs}
    maps, unused = {}, {}
    for mid in ids:
        entries = hall_maps[mid]
        if not isinstance(entries, Mapping):
            raise HallMapRefusedError(f"hall_maps[{mid!r}] must map architecture -> map path")
        lacking = [a for a in archs if a not in entries]
        if lacking:
            raise HallMapRefusedError(f"member {mid!r} has no Hall map for {lacking}")
        unused[mid] = sorted(a for a in entries if a not in archs)
        maps[mid] = {a: _load_map(mid, a, entries[a], ens) for a in archs}
    reaction_set = _check_maps(maps, specs, ids)
    results = {}
    for mid in ids:
        results[mid] = {}
        for s in specs:
            hm, prov = maps[mid][s.arch]
            results[mid][s.arch] = _evaluate(mid, s, hm, prov, queries[s.arch], upstream, fn, expected_boundary_version)
            if upstream.fingerprint() != fp0:
                raise ScopeViolationError("the upstream state changed during the member loop")
    comps = {}
    for s in specs:
        seen = {tuple(results[mid][s.arch]["bus_ledger"]["components"]) for mid in ids
                if results[mid][s.arch]["status"] == STATUS_OK}
        if len(seen) > 1:
            raise LedgerContractError(f"{s.arch}: the ledger booked different components for different members")
        if seen:
            comps[s.arch] = set(seen.pop())
    if "hall_only" in comps:
        for a, c in comps.items():
            if not comps["hall_only"] <= c:
                raise LedgerContractError(f"{a}: boundary drops common components {sorted(comps['hall_only'] - c)} "
                                          "that hall_only books (the boundary is common to every architecture)")
    envelopes = {a: _envelope(a, ids, results) for a in archs}
    return {
        "harness_version": HARNESS_VERSION,
        "boundary_version": expected_boundary_version,
        "architectures": archs,
        "members": ids,
        "member_set": "all admitted transport-ensemble members",
        "weighting": "unweighted",
        "ensemble": ens_info,
        "ledger_resolution": ledger_info,
        "production_path": ens_info["origin"] == "frozen_file" and ledger_info["origin"] != "injected",
        "reaction_set": reaction_set,
        "upstream": {**_plain(upstream.to_dict()), "fingerprint": fp0},
        "specs": {s.arch: s.to_dict() for s in specs},
        "hall_queries": _plain(queries),
        "mass_closure": _plain(closures),
        "maps_not_used": {mid: v for mid, v in unused.items() if v},
        "ledger_residual_gate_frac": LEDGER_RESIDUAL_MAX_FRAC,
        "rfp_limits": {"thrust_min_mN": RFP.thrust_min_mN, "thrust_max_mN": RFP.thrust_max_mN,
                       "power_max_W": RFP.power_max_W, "source": "abep_sim.constants.RFP"},
        "results": results,
        "envelopes": envelopes,
        "paired_differences": _paired(archs, ids, results, envelopes),
    }


# ------------------------------------------------------------------------------------------------------ files / CLI
def _read_json(path: str) -> dict:
    with open(path) as fh:
        return json.load(fh)


def load_hall_map_index(path: str, ensemble: Mapping | None = None) -> dict:
    """Read a hall-map index (HARNESS.md): {'schema': 'arch_compare_hall_map_index_v1', 'members': {id:
    {'admission_decision_sha256': hex, 'maps': {arch: {'path', 'sha256'}}}}}. Each member's admission_decision_sha256
    must equal the decision_sha256 of its admission record in the ensemble (binds the maps to the admission). Relative
    map paths resolve against the index's directory. Returns {member_id: {arch: {'path', 'sha256'}}}."""
    d = _read_json(path)
    if d.get("schema") != HALL_MAP_INDEX_SCHEMA or not isinstance(d.get("members"), Mapping):
        raise HallMapRefusedError(f"{path} is not an {HALL_MAP_INDEX_SCHEMA} index")
    ens, _ = resolve_ensemble(ensemble)
    by_id = {m["ensemble_member_id"]: m for m in ens["members"]}
    base = os.path.dirname(os.path.abspath(path))
    out = {}
    for mid, rec in d["members"].items():
        _require_admitted(mid, ens, "index member")
        adm = by_id[mid].get("admission")
        if not isinstance(rec, Mapping) or set(rec) != {"admission_decision_sha256", "maps"}:
            raise HallMapRefusedError(f"index member {mid!r} needs exactly admission_decision_sha256 and maps")
        if not isinstance(adm, Mapping) or rec["admission_decision_sha256"] != adm.get("decision_sha256"):
            raise MemberRefusedError(f"index member {mid!r}: admission_decision_sha256 does not match its admission record")
        if not isinstance(rec["maps"], Mapping):
            raise HallMapRefusedError(f"index member {mid!r}: maps must map architecture -> entry")
        out[mid] = {}
        for arch, e in rec["maps"].items():
            if arch not in ARCHITECTURES:
                raise HallMapRefusedError(f"index member {mid!r}: unknown architecture {arch!r}")
            p, sha = _map_entry(e, f"index member {mid!r}, {arch!r}")
            if sha is None:
                raise HallMapRefusedError(f"index member {mid!r}, {arch!r}: the index must record each map's sha256")
            out[mid][arch] = {"path": p if os.path.isabs(p) else os.path.join(base, p), "sha256": sha}
    return out


def load_specs(path: str) -> list[ArchitectureSpec]:
    d = _read_json(path)
    if d.get("schema") != SPECS_SCHEMA or not isinstance(d.get("specs"), list):
        raise SpecError(f"{path} is not an {SPECS_SCHEMA} file")
    return [ArchitectureSpec(**s) for s in d["specs"]]


def load_upstream(path: str) -> UpstreamState:
    d = _read_json(path)
    if d.get("schema") != UPSTREAM_SCHEMA:
        raise SpecError(f"{path} is not an {UPSTREAM_SCHEMA} file")
    return UpstreamState(d["quantities"], d["source"], d.get("labels", {}), d.get("drag_N"), d.get("drag_source"))


def _write_new(path: str, obj) -> None:
    if os.path.exists(path):
        raise HarnessError(f"{path} exists; the harness never overwrites a result")
    with open(path, "x") as fh:
        json.dump(_plain(obj), fh, indent=1, sort_keys=True)
        fh.write("\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m abep_sim.arch_compare", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="admitted members of the frozen ensemble (refuses when there are none)")
    up = sub.add_parser("upstream", help="write an upstream-state file from archengine.gas_path_state")
    for a in ("area-m2", "alpha", "L-over-d", "alt-km", "blade-coating-um"):
        up.add_argument(f"--{a}", type=float, required=True)
    up.add_argument("--solar", required=True)
    g = up.add_mutually_exclusive_group(required=True)
    g.add_argument("--p-target-Pa", type=float)
    g.add_argument("--p-margin-over-pmin", type=float)
    up.add_argument("--out", required=True)
    run = sub.add_parser("run", help="run the comparison on the frozen ensemble and the arch_boundary ledger")
    run.add_argument("--specs", required=True)
    run.add_argument("--upstream", required=True)
    run.add_argument("--maps", required=True, help=f"{HALL_MAP_INDEX_SCHEMA} index")
    run.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    try:
        if a.cmd == "status":
            ens, info = resolve_ensemble()
            ids = admitted_members(ens)
            print(f"{len(ids)} admitted member(s) in {info['path']} (sha256 {info['sha256']}): {', '.join(ids)}")
        elif a.cmd == "upstream":
            u = upstream_from_archengine(area_m2=a.area_m2, alpha=a.alpha, L_over_d=a.L_over_d, alt_km=a.alt_km,
                                         solar=a.solar, blade_coating_um=a.blade_coating_um,
                                         p_target_Pa=a.p_target_Pa, p_margin_over_pmin=a.p_margin_over_pmin)
            _write_new(a.out, {"schema": UPSTREAM_SCHEMA, **u.to_dict()})
            print(f"wrote {a.out} (fingerprint {u.fingerprint()})")
        else:
            res = compare_architectures(load_specs(a.specs), load_upstream(a.upstream), load_hall_map_index(a.maps))
            _write_new(a.out, res)
            print(f"wrote {a.out}: {len(res['members'])} members x {len(res['architectures'])} architectures; "
                  + ", ".join(f"{k} envelope {v['status']}" for k, v in res["envelopes"].items()))
    except HarnessError as e:
        print(f"REFUSED ({type(e).__name__}): {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
