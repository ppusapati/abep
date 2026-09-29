"""Mission Xe ledger v2 (parallel RF || Hall investigation).

``xe_ledger_v1`` (abep_sim/xe_ledger.py, the A6 parametric ledger) is untouched. v2 books Xe by CAUSE from the
actual mode history of a mission:

    m_Xe = sum_i mdot_Xe,i t_i  +  sum_events m_event  +  m_reserve  (+ m_residual)

Causes: rf_xe_operation, hall_xe_anode, hall_cathode, hall_startup, rf_startup, transition, fallback, reserve,
residual. Continuous flows are booked per interval, start-up/transition masses per event. The Hall duty cycle is not
assumed: it is computed from the recorded history. Intervals must be contiguous, so the total mode time equals the
propagated mission time. Remaining Xe can only decrease. Reserve and residual are explicit policies (a Quantity
fraction of consumption, a Quantity mass, or TBD, in which case the total is reported incomplete).
"""
from __future__ import annotations

import math

from .parallel_contracts import (ContractError, Quantity, Status, TBD, nonneg, real, serialise, value_of)
from .propulsion_modes import Mode, mode_spec

LEDGER_VERSION = "xe_mission_v2"
CONTINUOUS_CAUSES = ("rf_xe_operation", "hall_xe_anode", "hall_cathode", "transition", "fallback")
EVENT_CAUSES = ("hall_startup", "rf_startup", "transition")
POLICY_CAUSES = ("reserve", "residual")
CAUSES = ("rf_xe_operation", "hall_xe_anode", "hall_cathode", "hall_startup", "rf_startup", "transition",
          "fallback", "reserve", "residual")


def _cause_allowed(cause: str, mode: Mode) -> bool:
    s = mode_spec(mode)
    return {"rf_xe_operation": s.rf_xe_allowed, "hall_xe_anode": s.hall_xe_allowed,
            "hall_cathode": s.hall_cathode_required,
            "transition": True, "fallback": s.rf_xe_allowed or s.hall_xe_allowed}[cause]


class XeMissionLedger:
    def __init__(self, loaded_kg: Quantity | None):
        """``loaded_kg``: the Xe loaded at mission start (Quantity), or None when the loaded mass is what is being
        sized (then remaining is not tracked, only consumption)."""
        self.loaded = None if loaded_kg is None else value_of(loaded_kg, "loaded Xe", "kg")
        self.loaded_q = loaded_kg
        self.t_end = 0.0
        self.by_cause = {c: 0.0 for c in CAUSES if c not in POLICY_CAUSES}
        self.time_by_mode = {m.value: 0.0 for m in Mode}
        self.starts = {"hall_startup": 0, "rf_startup": 0, "transition": 0}
        self.event_evidence = []
        self.remaining_trace = []
        self.depleted_at_s = None

    @property
    def consumed_kg(self) -> float:
        return math.fsum(self.by_cause.values())

    def _consume(self, t_s: float, kg: float):
        if self.loaded is None:
            return
        before = self.loaded - (self.consumed_kg - kg)
        after = self.loaded - self.consumed_kg
        if after > before + 1e-15:
            raise RuntimeError("remaining Xe increased")          # cannot happen with non-negative bookings
        if after < 0 and self.depleted_at_s is None:
            self.depleted_at_s = t_s
        self.remaining_trace.append((t_s, after))

    def add_interval(self, t0_s: float, dt_s: float, mode, flows_kg_s: dict) -> None:
        """Book a contiguous interval [t0, t0+dt) in ``mode`` with continuous Xe flows per cause (kg/s)."""
        t0, dt = real(t0_s, "t0_s"), nonneg(dt_s, "dt_s")
        if abs(t0 - self.t_end) > 1e-9 * max(1.0, self.t_end):
            raise ContractError(f"intervals must be contiguous: t0 {t0!r} != previous end {self.t_end!r}")
        m = mode_spec(mode).mode
        bad = [c for c in flows_kg_s if c not in CONTINUOUS_CAUSES]
        if bad:
            raise ContractError(f"not continuous Xe causes: {bad}; use add_event for start-ups")
        booked = 0.0
        for c, rate in flows_kg_s.items():
            r = nonneg(rate, f"{c} flow")
            if r > 0 and not _cause_allowed(c, m):
                raise ContractError(f"cause {c!r} is not possible in mode {m.value}")
            self.by_cause[c] += r * dt
            booked += r * dt
        self.time_by_mode[m.value] += dt
        self.t_end = t0 + dt
        self._consume(self.t_end, booked)

    def add_event(self, t_s: float, cause: str, mass_kg: Quantity, count: int = 1) -> None:
        """Book a start-up / transition event mass (per event, with evidence)."""
        if cause not in EVENT_CAUSES:
            raise ContractError(f"event cause must be one of {EVENT_CAUSES}")
        if not isinstance(count, int) or count < 1:
            raise ContractError("count must be a positive int")
        m = value_of(mass_kg, f"{cause} event mass", "kg")
        if m < 0:
            raise ContractError("event mass must be >= 0")
        self.by_cause[cause] += m * count
        self.starts[cause] += count
        self.event_evidence.append({"t_s": real(t_s, "t_s"), "cause": cause, "count": count,
                                    "mass_kg_each": mass_kg.to_dict()})
        self._consume(t_s, m * count)

    def summary(self, reserve, residual) -> dict:
        """``reserve``/``residual``: Quantity with unit '1' (fraction of consumption) or 'kg', or TBD."""
        consumed = self.consumed_kg
        pol = {}
        for name, p in (("reserve", reserve), ("residual", residual)):
            if isinstance(p, TBD):
                pol[name] = p
            elif isinstance(p, Quantity) and p.unit == "1":
                pol[name] = consumed * p.value
            elif isinstance(p, Quantity) and p.unit == "kg":
                pol[name] = p.value
            else:
                raise ContractError(f"{name} policy must be a Quantity in '1' or 'kg', or TBD (never implicit)")
        complete = not any(isinstance(v, TBD) for v in pol.values())
        total = consumed + math.fsum(v for v in pol.values() if not isinstance(v, TBD))
        T = self.t_end
        hall_t = sum(t for m, t in self.time_by_mode.items() if mode_spec(m).hall_enabled)
        rf_t = sum(t for m, t in self.time_by_mode.items() if mode_spec(m).rf_enabled)
        out = {
            "ledger_version": LEDGER_VERSION,
            "status": Status.PASS.value if complete else Status.INCOMPLETE_EVIDENCE.value,
            "mission_time_s": T, "time_by_mode_s": dict(self.time_by_mode),
            "mode_time_sum_s": math.fsum(self.time_by_mode.values()),
            "xe_by_cause_kg": {**dict(self.by_cause), **{k: serialise(v) for k, v in pol.items()}},
            "xe_consumed_kg": consumed,
            "xe_total_required_kg": total if complete else None,
            "xe_total_known_lower_bound_kg": total,
            "hall_time_fraction": (hall_t / T) if T > 0 else None,
            "rf_time_fraction": (rf_t / T) if T > 0 else None,
            "hall_starts": self.starts["hall_startup"], "rf_starts": self.starts["rf_startup"],
            "transitions": self.starts["transition"],
            "answers": {"fraction_of_mission_time_using_hall": (hall_t / T) if T > 0 else None,
                        "hall_starts": self.starts["hall_startup"],
                        "xe_to_hall_anode_kg": self.by_cause["hall_xe_anode"],
                        "xe_to_cathode_kg": self.by_cause["hall_cathode"],
                        "xe_consumed_by_fallback_kg": self.by_cause["fallback"]},
            "event_evidence": self.event_evidence,
            "loaded_kg": None if self.loaded is None else self.loaded,
            "remaining_kg": None if self.loaded is None else self.loaded - consumed,
            "depleted_at_s": self.depleted_at_s,
        }
        if self.loaded is not None and self.loaded - consumed < 0:
            out["status"] = Status.INFEASIBLE_FLOW.value
        return out
