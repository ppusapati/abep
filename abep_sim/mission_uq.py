"""Mission-level closure probability (the number to trust).

P[ for all t in 0..26,000 h:  T(t) >= D(t)  and  P_bus(t) < 1500 W  and  T(t) <= 25 mN cap  and  altitude held
                              and  Xe not exhausted  and  m_MEV <= 40 kg  and  life margins >= 1 ]
sampled over the joint prior set (epistemic) and over solar-cycle launch phase (aleatory),
with the limiting mechanism identified per sample.
"""
from __future__ import annotations
import copy
import numpy as np
import pandas as pd
from .uncertainty import DEFAULT_PRIORS, _apply, _relevant, _sample_tri, _JOINT
from .intake import IntakeParams, CompressorParams
from .system import Config, Budgets, evaluate
from .transient import MissionParams, run_mission
from .thruster import CARDS
from .aochem import AOParams


def mission_closure(architecture="hall_ecr", alt_km=200.0, area_m2=0.5, cr=2000.0, vd=300.0, sc_mass_kg=150.0,
                    body_area_m2=0.0, xe_budget_kg=5.0, xe_policy="hold", n=200, seed=11, dt_h=3.0,
                    fixed: dict | None = None, priors=DEFAULT_PRIORS) -> tuple[pd.DataFrame, dict]:
    """fixed: {'eta_c_eff': x, 'ecr_gain': g} to impose measured drivers instead of sampling them."""
    rng = np.random.default_rng(seed)
    base = CARDS[architecture]
    fixed = fixed or {}
    skip = set()
    if "eta_c_eff" in fixed:
        skip |= {"eta_c_specular", "eta_c_diffuse", "surface_state"}
    if "ecr_gain" in fixed:
        skip |= {"s1_eta_u_boost", "s1_transport_eff"}
    pri = [p for p in priors if _relevant(p, base) and p.name not in skip]
    samples = {p.name: _sample_tri(rng, p, n) for p in pri}
    phases = rng.uniform(0.0, 11.0, size=n)         # aleatory: launch phase in the solar cycle
    from . import aochem
    g0 = aochem.RECOMB_GAMMA["stainless_steel"]
    rows = []
    for i in range(n):
        card = copy.deepcopy(base); CARDS[architecture] = card
        _JOINT.clear()
        intake = IntakeParams(area_m2=area_m2)
        comp = CompressorParams(ratio=cr)
        cfg = Config(architecture, alt_km, "mean", intake, comp, vd_V=vd, budgets=Budgets(), ao=AOParams(),
                     body_area_m2=body_area_m2)
        for p in pri:
            _apply(cfg, card, p, float(samples[p.name][i]))
        if "eta_c_eff" in fixed:
            cfg.intake.eta_c_specular = cfg.intake.eta_c_diffuse = fixed["eta_c_eff"]; cfg.intake.accommodation = 0.0
        if "ecr_gain" in fixed and card.stage1 is not None:
            card.stage1.eta_u_boost = fixed["ecr_gain"]; card.stage1.transport_eff = 1.0
        static = evaluate(cfg)                       # mass / life / IC at the design point (mean solar)
        mp = MissionParams(architecture, alt_km, alt_km, sc_mass_kg, body_area_m2, cfg.intake, cfg.compressor, vd,
                           dt_h=dt_h, cycle_phase_years=float(phases[i]), xe_budget_kg=xe_budget_kg, xe_policy=xe_policy,
                           ao=cfg.ao)
        df, s = run_mission(mp)
        held = s["alt_held"]
        power_ok = bool((df.P_bus_W <= 1500.0).all())
        td_ok = bool((df.T_over_D >= 1.0).all())
        xe_ok = not s["xe_topping_exhausted"]
        # Mass from the mission's actual Xe use (+20 % reserve), not the static "12 mN-on-air-else-Xe" rule
        b = cfg.budgets
        xe_kg = s["xe_used_total_kg"] * 1.2
        m_tank = b.m_xe_tank_base_kg + b.m_xe_tank_frac * xe_kg
        m_dry = static["m_thruster_kg"] + static["m_ppu_kg"] + static["m_intake_kg"] + static["m_comp_kg"] + m_tank
        m_struct = b.m_structure_frac * m_dry
        m_cbe = m_dry + m_struct + xe_kg
        m_mga = (b.mga_new_design * (static["m_intake_kg"] + static["m_comp_kg"] + (card.stage1.mass_kg if card.stage1 else 0.0))
                 + b.mga_modified * (card.mass_kg + static["m_ppu_kg"]) + b.mga_existing * (m_tank + m_struct))
        m_mev = m_cbe + m_mga
        mass_ok = m_mev <= 40.0
        life_ok = static["life_margin"] >= 1.0
        closed = held and power_ok and xe_ok and mass_ok and life_ok
        # limiting mechanism, first failing in priority order
        limit = ("reentry" if not held else "power_cap" if not power_ok else "xe_exhausted" if not xe_ok
                 else "mass_mev" if not mass_ok else "life" if not life_ok else "none")
        rows.append({"phase_yr": float(phases[i]), **{k: float(samples[k][i]) for k in samples},
                     "closed": closed, "held": held, "td_all_t": td_ok, "power_ok": power_ok, "xe_ok": xe_ok,
                     "mass_ok": mass_ok, "life_ok": life_ok, "limit": limit,
                     "min_TD": float(df.T_over_D.min()), "peak_P_W": float(df.P_bus_W.max()),
                     "mean_P_W": float((df.P_bus_W * df.duty).mean()), "xe_used_kg": s["xe_used_total_kg"],
                     "m_mev_kg": m_mev, "m_cbe_kg": m_cbe, "life_margin": static["life_margin"],
                     "rfp_12mN_on_air_at_mean_solar": bool(static["chk_thrust_air_ge_req"]),
                     "hours_TD_ge_1": s["hours_TD_ge_1"], "reentry_h": s["reentry_time_h"] or 0.0})
    CARDS[architecture] = base; aochem.RECOMB_GAMMA["stainless_steel"] = g0
    out = pd.DataFrame(rows)
    summary = {"architecture": architecture, "alt_km": alt_km, "area_m2": area_m2, "cr": cr, "vd": vd,
               "sc_mass_kg": sc_mass_kg, "body_area_m2": body_area_m2, "fixed": fixed, "n": n,
               "P_mission_closed": float(out.closed.mean()), "P_altitude_held": float(out.held.mean()),
               "P_TD_ge_1_all_t": float(out.td_all_t.mean()), "P_power_ok": float(out.power_ok.mean()),
               "P_xe_ok": float(out.xe_ok.mean()), "P_mass_mev_ok": float(out.mass_ok.mean()), "P_life_ok": float(out.life_ok.mean()),
               "limiting_mechanism_counts": out.limit.value_counts().to_dict(),
               "P_rfp_12mN_on_air_at_mean_solar": float(out.rfp_12mN_on_air_at_mean_solar.mean()),
               "m_cbe_p50": float(out.m_cbe_kg.median()), "m_mev_p50": float(out.m_mev_kg.median())}
    return out, summary


def main(argv=None):
    import argparse, json
    from pathlib import Path
    ap = argparse.ArgumentParser(prog="abep-mission-uq")
    ap.add_argument("--arch", default="hall_ecr"); ap.add_argument("--alt", type=float, default=200)
    ap.add_argument("--area", type=float, default=0.5); ap.add_argument("--cr", type=float, default=2000)
    ap.add_argument("--vd", type=float, default=300); ap.add_argument("--sc-mass", type=float, default=150)
    ap.add_argument("--body-area", type=float, default=0.0); ap.add_argument("--xe", type=float, default=5.0)
    ap.add_argument("-n", type=int, default=200); ap.add_argument("--dt", type=float, default=3.0)
    ap.add_argument("--eta-c", type=float, default=None); ap.add_argument("--gain", type=float, default=None)
    ap.add_argument("-o", "--out", default="results/mission_uq")
    a = ap.parse_args(argv)
    fixed = {k: v for k, v in (("eta_c_eff", a.eta_c), ("ecr_gain", a.gain)) if v is not None}
    df, s = mission_closure(a.arch, a.alt, a.area, a.cr, a.vd, a.sc_mass, a.body_area, a.xe, n=a.n, dt_h=a.dt, fixed=fixed)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    tag = f"{a.arch}_{int(a.alt)}_A{a.area}_CR{int(a.cr)}_V{int(a.vd)}" + (f"_ec{a.eta_c}" if a.eta_c else "") + (f"_g{a.gain}" if a.gain else "")
    df.to_csv(out / f"{tag}.csv", index=False); (out / f"{tag}.json").write_text(json.dumps(s, indent=1))
    print(json.dumps(s, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
