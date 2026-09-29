"""Operating modes and installed architectures of the parallel RF || Hall investigation (v2).

Installed architecture and operating mode are separate concepts:

* ``InstalledArchitecture`` fixes the hardware carried (and therefore the installed dry mass): rf_only, hall_only or
  rf_hall_parallel, and whether a stored-Xe system is installed.
* ``Mode`` fixes what is powered and which propellant each branch may consume at a given instant.

Exactly seven initial modes exist. No automatic hybrid modes: a new combination (e.g. a Hall anode fed by an
atmosphere + Xe blend) needs a new, explicitly specified mode. Illegal propellant/mode combinations raise
``IllegalModeError``; nothing is silently corrected.

The v2 ids are deliberately distinct from the v1 ids ('rf_hall' in bus_power_boundary_v1 means RF -> Hall
pre-ionization, A5). v2 never reuses 'rf_hall'.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .parallel_contracts import ContractError


class IllegalModeError(ContractError):
    """A mode / propellant / architecture combination that the v2 mode table does not permit."""


class Mode(str, Enum):
    OFF = "OFF"
    RF_ATM = "RF_ATM"
    RF_XE = "RF_XE"
    HALL_ATM = "HALL_ATM"
    HALL_XE = "HALL_XE"
    RF_ATM_HALL_ATM = "RF_ATM_HALL_ATM"
    RF_ATM_HALL_XE = "RF_ATM_HALL_XE"


# propellant streams a request may name
STREAMS = ("rf_atm", "rf_xe", "hall_atm", "hall_xe", "cathode_xe")


@dataclass(frozen=True)
class ModeSpec:
    mode: Mode
    rf_enabled: bool
    hall_enabled: bool
    rf_atm_allowed: bool
    rf_xe_allowed: bool
    hall_atm_allowed: bool
    hall_xe_allowed: bool
    hall_cathode_required: bool
    feed_sources: tuple            # "atmosphere" and/or "xe_tank"
    branches: tuple                # enabled branch ids

    def allowed_streams(self) -> tuple:
        out = []
        for s, ok in (("rf_atm", self.rf_atm_allowed), ("rf_xe", self.rf_xe_allowed),
                      ("hall_atm", self.hall_atm_allowed), ("hall_xe", self.hall_xe_allowed),
                      ("cathode_xe", self.hall_cathode_required)):
            if ok:
                out.append(s)
        return tuple(out)

    def to_dict(self) -> dict:
        return {"mode": self.mode.value, "rf_enabled": self.rf_enabled, "hall_enabled": self.hall_enabled,
                "rf_atm_allowed": self.rf_atm_allowed, "rf_xe_allowed": self.rf_xe_allowed,
                "hall_atm_allowed": self.hall_atm_allowed, "hall_xe_allowed": self.hall_xe_allowed,
                "hall_cathode_required": self.hall_cathode_required, "feed_sources": list(self.feed_sources),
                "branches": list(self.branches), "allowed_streams": list(self.allowed_streams())}


def _spec(mode, rf, hall, rf_atm, rf_xe, hall_atm, hall_xe, cathode):
    sources = []
    if rf_atm or hall_atm:
        sources.append("atmosphere")
    if rf_xe or hall_xe or cathode:
        sources.append("xe_tank")
    branches = tuple(b for b, on in (("rf", rf), ("hall", hall)) if on)
    return ModeSpec(mode, rf, hall, rf_atm, rf_xe, hall_atm, hall_xe, cathode, tuple(sources), branches)


# The Hall branch always needs its Xe-fed cathode (A5: shielded Xe-fed LaB6 cathode), whatever feeds the anode.
MODE_TABLE = {
    Mode.OFF: _spec(Mode.OFF, False, False, False, False, False, False, False),
    Mode.RF_ATM: _spec(Mode.RF_ATM, True, False, True, False, False, False, False),
    Mode.RF_XE: _spec(Mode.RF_XE, True, False, False, True, False, False, False),
    Mode.HALL_ATM: _spec(Mode.HALL_ATM, False, True, False, False, True, False, True),
    Mode.HALL_XE: _spec(Mode.HALL_XE, False, True, False, False, False, True, True),
    Mode.RF_ATM_HALL_ATM: _spec(Mode.RF_ATM_HALL_ATM, True, True, True, False, True, False, True),
    Mode.RF_ATM_HALL_XE: _spec(Mode.RF_ATM_HALL_XE, True, True, True, False, False, True, True),
}


def mode_spec(mode) -> ModeSpec:
    if not isinstance(mode, Mode):
        try:
            mode = Mode(mode)
        except ValueError:
            raise IllegalModeError(f"unknown operating mode {mode!r}; v2 defines {[m.value for m in Mode]}") from None
    return MODE_TABLE[mode]


# ------------------------------------------------------------------------------------------ installed architecture

class ArchitectureKind(str, Enum):
    RF_ONLY = "rf_only"
    HALL_ONLY = "hall_only"
    RF_HALL_PARALLEL = "rf_hall_parallel"


_KIND_MODES = {
    ArchitectureKind.RF_ONLY: (Mode.OFF, Mode.RF_ATM, Mode.RF_XE),
    ArchitectureKind.HALL_ONLY: (Mode.OFF, Mode.HALL_ATM, Mode.HALL_XE),
    ArchitectureKind.RF_HALL_PARALLEL: tuple(Mode),
}
_XE_MODES = frozenset(m for m, s in MODE_TABLE.items() if "xe_tank" in s.feed_sources)


@dataclass(frozen=True)
class InstalledArchitecture:
    """Installed hardware. ``xe_system_installed`` must be stated explicitly (no default). Any architecture with a
    Hall branch requires the Xe system (the cathode is Xe-fed); rf_only may be built with or without it, and without
    it RF_XE is not an allowed mode."""
    kind: ArchitectureKind
    xe_system_installed: bool

    def __post_init__(self):
        if not isinstance(self.kind, ArchitectureKind):
            try:
                object.__setattr__(self, "kind", ArchitectureKind(self.kind))
            except ValueError:
                raise ContractError(f"unknown installed architecture {self.kind!r}; v2 defines "
                                    f"{[k.value for k in ArchitectureKind]}") from None
        if not isinstance(self.xe_system_installed, bool):
            raise ContractError("xe_system_installed must be stated explicitly as a bool")
        if self.kind in (ArchitectureKind.HALL_ONLY, ArchitectureKind.RF_HALL_PARALLEL) and not self.xe_system_installed:
            raise ContractError(f"{self.kind.value} carries a Xe-fed Hall cathode; xe_system_installed must be True")

    @property
    def has_rf(self) -> bool:
        return self.kind in (ArchitectureKind.RF_ONLY, ArchitectureKind.RF_HALL_PARALLEL)

    @property
    def has_hall(self) -> bool:
        return self.kind in (ArchitectureKind.HALL_ONLY, ArchitectureKind.RF_HALL_PARALLEL)

    def allowed_modes(self) -> tuple:
        modes = _KIND_MODES[self.kind]
        if not self.xe_system_installed:
            modes = tuple(m for m in modes if m not in _XE_MODES)
        return modes

    def check_mode(self, mode) -> ModeSpec:
        spec = mode_spec(mode)
        if spec.mode not in self.allowed_modes():
            raise IllegalModeError(f"mode {spec.mode.value} is not available on installed architecture "
                                   f"{self.kind.value} (xe_system_installed={self.xe_system_installed}); "
                                   f"allowed {[m.value for m in self.allowed_modes()]}")
        return spec

    def to_dict(self) -> dict:
        return {"kind": self.kind.value, "xe_system_installed": self.xe_system_installed,
                "has_rf": self.has_rf, "has_hall": self.has_hall,
                "allowed_modes": [m.value for m in self.allowed_modes()]}
