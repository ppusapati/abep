"""Mission integration of the parallel RF || Hall investigation (v2).

Reuses the mission_env physics (J2 secular RAAN drift, ``beta_angle``, ``eclipse_fraction`` and the secular
energy-balance altitude equation da/dt = 2 a^1.5 (T - D) / (m sqrt(mu)) of ``mission_env.propagate``) without
replacing that propagator: this loop exists because v2 must record the complete mode history, Xe by cause,
component hours, start counts and a battery state, and must take every spacecraft/environment input explicitly
(``mission_env.Spacecraft`` carries defaults that v2 may not use silently).

At each step the loop determines the atmospheric state, captured flow, drag, array power, required thrust, thermal
bookkeeping, remaining Xe and available modes, then records WHATEVER candidate the supplied mode policy requests. It
never chooses a mode itself.

Battery:  dE/dt = P_array - P_spacecraft - P_propulsion. The battery never bypasses the RFP instantaneous limit
(the system evaluator applies P_bus < 1500 W at every step); it only tracks eclipse/boost energy and recharge.

Stop conditions (reported, never papered over): a step whose thrust is not available (OUT_OF_DOMAIN, MODEL_ERROR,
NOT_SUSTAINED without thrust, TBD), battery exhaustion, re-entry below the stated floor.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from . import parallel_system
from .constants import MU_EARTH, R_EARTH
from .mission_env import J2, beta_angle, eclipse_fraction
from .parallel_contracts import ContractError, Quantity, TBD, nonneg, positive, real, serialise, value_of
from .propulsion_modes import InstalledArchitecture, mode_spec
from .xe_mission_v2 import XeMissionLedger


@dataclass(frozen=True)
class MissionInputs:
    """Every input explicit. Callables:
    atmosphere_fn(alt_km, t_s) -> dict with at least 'rho' [kg/m^3] (caller's atmosphere, e.g. the frozen dataset)
    intake_fn(atm) -> FeedState of the AVAILABLE atmospheric stream after intake/compressor
    drag_fn(alt_km, t_s, atm) -> total spacecraft drag [N] (e.g. via mission_env.spacecraft_drag)
    required_thrust_fn(drag_N, alt_km, t_s) -> required thrust [N] (the stated station-keeping law)
    array_power_fn(t_s, alt_km, beta_deg, eclipse_frac) -> array power available to the bus [W]
    policy_fn(state) -> mode_controller.Candidate  (the SUPPLIED mode policy; state is a dict)
    """
    spacecraft_mass_kg: Quantity
    inclination_deg: Quantity
    raan0_deg: Quantity
    epoch_day: Quantity
    alt0_km: float
    atmosphere_fn: object
    intake_fn: object
    drag_fn: object
    required_thrust_fn: object
    array_power_fn: object
    spacecraft_bus_power_W: Quantity          # spacecraft (non-propulsion) load
    battery_capacity_J: Quantity
    battery_initial_J: Quantity
    policy_fn: object
    hall_start_xe_kg: object                  # Quantity | TBD (per Hall start)
    rf_start_xe_kg: object                    # Quantity | TBD (per RF start on Xe)
    reentry_floor_km: float


def _active_components(o: dict) -> list:
    return list(o.get("active_components", []))


def run(architecture: InstalledArchitecture, inputs: MissionInputs, *, xe_supply, xe_loaded_kg: Quantity | None,
        common, constraints, duration_s: float, dt_s: float) -> dict:
    m_sc = value_of(inputs.spacecraft_mass_kg, "spacecraft mass", "kg")
    inc = value_of(inputs.inclination_deg, "inclination", "deg")
    raan = value_of(inputs.raan0_deg, "RAAN0", "deg")
    epoch = value_of(inputs.epoch_day, "epoch day", "day")
    P_sc = value_of(inputs.spacecraft_bus_power_W, "spacecraft bus power", "W")
    E_cap = value_of(inputs.battery_capacity_J, "battery capacity", "J")
    E = value_of(inputs.battery_initial_J, "battery initial energy", "J")
    if not 0.0 <= E <= E_cap:
        raise ContractError("battery initial energy must be within [0, capacity]")
    T_end, dt = positive(duration_s, "duration_s"), positive(dt_s, "dt_s")
    alt = real(inputs.alt0_km, "alt0_km")
    xe = XeMissionLedger(xe_loaded_kg)
    hours, starts = {}, {"rf": 0, "hall": 0}
    unbooked_starts = []
    history, prev_spec = [], None
    t, stop = 0.0, None
    while t < T_end - 1e-9:
        step = min(dt, T_end - t)
        a = R_EARTH + alt * 1e3
        nmo = math.sqrt(MU_EARTH / a ** 3)
        raan += math.degrees(-1.5 * nmo * J2 * (R_EARTH / a) ** 2 * math.cos(math.radians(inc)) * step)
        day = epoch + t / 86400.0
        sun_lon = (day / 365.25 * 360.0) % 360
        sun_dec = 23.44 * math.sin(math.radians(sun_lon))
        beta = beta_angle(inc, raan, sun_lon, sun_dec)
        f_ecl = eclipse_fraction(alt, beta)
        atm = inputs.atmosphere_fn(alt, t)
        feed = inputs.intake_fn(atm)
        D = real(inputs.drag_fn(alt, t, atm), "drag")
        T_req = real(inputs.required_thrust_fn(D, alt, t), "required thrust")
        P_arr = nonneg(inputs.array_power_fn(t, alt, beta, f_ecl), "array power")
        state = {"t_s": t, "alt_km": alt, "atm": atm, "feed": feed, "drag_N": D, "required_thrust_N": T_req,
                 "P_array_W": P_arr, "battery_J": E, "xe_consumed_kg": xe.consumed_kg, "beta_deg": beta,
                 "eclipse_frac": f_ecl, "allowed_modes": [m.value for m in architecture.allowed_modes()]}
        cand = inputs.policy_fn(state)
        spec = architecture.check_mode(cand.mode)
        o = parallel_system.evaluate(architecture, cand.mode, atm_feed=feed, xe_supply=xe_supply,
                                     request=cand.request, rf=cand.rf, hall=cand.hall, common=common,
                                     constraints=constraints, required_thrust_N=T_req)
        T = o.get("T_total_axial_N")
        P_prop = o.get("P_total_bus_W")
        if isinstance(T, TBD) or T is None or P_prop is None:
            stop = {"t_s": t, "reason": f"step status {o.get('status')}: thrust or bus power not available",
                    "statuses": o.get("statuses")}
            break
        # starts (transition into a branch-enabled mode)
        for b, on_now, on_before in (("rf", spec.rf_enabled, prev_spec.rf_enabled if prev_spec else False),
                                     ("hall", spec.hall_enabled, prev_spec.hall_enabled if prev_spec else False)):
            if on_now and not on_before:
                starts[b] += 1
                ev_mass = inputs.hall_start_xe_kg if b == "hall" else (
                    inputs.rf_start_xe_kg if spec.rf_xe_allowed else None)
                if ev_mass is None:
                    continue
                if isinstance(ev_mass, TBD):
                    unbooked_starts.append({"t_s": t, "branch": b, "requires": ev_mass.requires})
                else:
                    xe.add_event(t, "hall_startup" if b == "hall" else "rf_startup", ev_mass)
        # Xe flows by cause
        rt = o["routing"]
        flows = {}
        if spec.rf_xe_allowed and rt["rf_feed"]:
            flows["rf_xe_operation"] = rt["rf_feed"]["mdot_total_kg_s"]
        if spec.hall_xe_allowed and rt["hall_feed"]:
            flows["hall_xe_anode"] = rt["hall_feed"]["mdot_total_kg_s"]
        if spec.hall_cathode_required:
            flows["hall_cathode"] = rt["cathode_xe_kg_s"]
        xe.add_interval(t, step, cand.mode, flows)
        for c in _active_components(o):
            hours[c] = hours.get(c, 0.0) + step / 3600.0
        # battery and altitude
        dE = (P_arr - P_sc - P_prop) * step
        E = min(E + dE, E_cap)
        a_dot = 2.0 * a ** 1.5 * (T - D) / (m_sc * math.sqrt(MU_EARTH))
        history.append({
            "t_s": t, "dt_s": step, "alt_km": alt, "rho_kg_m3": atm.get("rho"),
            "composition": dict(feed.mass_fractions) if feed is not None else None, "drag_N": D,
            "available_atm_mdot_kg_s": feed.mdot_total_kg_s if feed is not None else 0.0, "mode": spec.mode.value,
            "P_RF_bus_W": o.get("P_RF_bus_W"), "P_H_bus_W": o.get("P_H_bus_W"),
            "P_common_bus_W": o.get("P_common_bus_W"), "P_total_bus_W": P_prop,
            "T_RF_N": serialise(o.get("T_RF_N")), "T_H_N": serialise(o.get("T_H_N")), "T_total_N": T,
            "required_thrust_N": T_req, "xe_rate_kg_s": sum(flows.values()),
            "xe_remaining_kg": None if xe.loaded is None else xe.loaded - xe.consumed_kg,
            "rf_starts": starts["rf"], "hall_starts": starts["hall"], "status": o.get("status"),
            "verdict": o.get("verdict"), "heat_loads_W": o.get("heat_loads_W"),
            "P_array_W": P_arr, "battery_J": E, "power_margin_W": P_arr - P_sc - P_prop,
            "beta_deg": beta, "eclipse_frac": f_ecl})
        if E < 0.0:
            stop = {"t_s": t + step, "reason": "battery exhausted (energy balance negative)"}
            break
        alt += a_dot * step / 1e3
        t += step
        prev_spec = spec
        if alt < inputs.reentry_floor_km:
            stop = {"t_s": t, "reason": f"altitude below the stated floor {inputs.reentry_floor_km} km"}
            break
    mission_t = sum(h["dt_s"] for h in history)
    hall_t = sum(h["dt_s"] for h in history if mode_spec(h["mode"]).hall_enabled)
    return {"architecture": architecture.kind.value, "completed": stop is None, "stop": stop,
            "mission_time_s": mission_t, "history": history, "component_hours": hours, "starts": starts,
            "unbooked_start_events": unbooked_starts, "xe_mission": xe,
            "hall_duty_fraction": (hall_t / mission_t) if mission_t > 0 else None,
            "propulsion_energy_J": sum(h["P_total_bus_W"] * h["dt_s"] for h in history),
            "score_bearing": bool(history) and all(h["verdict"] == "FEASIBLE" for h in history),
            "note": ("mission on non-admitted evidence is a hypothesis run, not a feasibility demonstration"
                     if not (history and all(h["verdict"] == "FEASIBLE" for h in history)) else "")}


def coverage(conditions, evaluate_rf_only, evaluate_rf_hall) -> dict:
    """Fraction of mission conditions in which RF alone closes, RF + Hall closes (RF alone does not), or neither.
    ``evaluate_*`` take a condition and return a parallel_system result dict; 'closes' means mode_feasible.
    Non-admitted evidence makes a 'closes' a hypothesis: the verdicts are counted separately."""
    n, rf_c, boost_c, none_c, admitted = 0, 0, 0, 0, 0
    for cond in conditions:
        n += 1
        r1 = evaluate_rf_only(cond)
        if r1.get("mode_feasible"):
            rf_c += 1
            admitted += r1.get("verdict") == "FEASIBLE"
            continue
        r2 = evaluate_rf_hall(cond)
        if r2.get("mode_feasible"):
            boost_c += 1
            admitted += r2.get("verdict") == "FEASIBLE"
        else:
            none_c += 1
    if n == 0:
        raise ContractError("no conditions")
    return {"n_conditions": n, "rf_alone_closes": rf_c / n, "rf_plus_hall_closes": boost_c / n,
            "neither_closes": none_c / n, "closing_on_admitted_evidence": admitted / n}
