"""Programme layer: the modular-architecture UQ runner (moved from abep_sim/uq_modular.py, A9.22 layer separation).

abep_sim.uq_modular keeps the priors and the per-sample physics (sample_closure); this module attaches the
evaluation-only success flag (abep_sim.assessment.arch_constraints.uq_success: closure ratio >= 1 and life >= the
firing-life requirement) and runs the Monte Carlo. Records and summaries are identical to the pre-move output (same
keys, order and values).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .. import operating_inputs as OI
from .. import uq_modular as UQ
from ..archengine import enumerate_architectures, arch_name


def evaluate_sample(a, x, area, p_level, A_array, P_cap, xs: dict, alt=200.0, eta_ppu=0.9, P_mag=25.0,
                    firing_hours: float | None = None) -> dict:
    """firing_hours: firing-life requirement for the success flag (caller-supplied, A9.22; None ->
    abep_sim.operating_inputs.FIRING_HOURS). The flag itself is evaluated in abep_sim.assessment.arch_constraints."""
    from ..assessment.arch_constraints import uq_success
    if firing_hours is None:
        firing_hours = OI.FIRING_HOURS
    r = UQ.sample_closure(a, x, area, p_level, A_array, P_cap, xs, alt, eta_ppu, P_mag)
    out = {k: v for k, v in r.items() if k != "limit"}
    out["success"] = uq_success(r["ratio_min"], r["life_h"], firing_hours)
    out["limit"] = r["limit"]
    return out


def run_uq(arch: str, x: dict, area: float, p_level: float, A_array: float, P_cap: float, n: int = 200, seed: int = 1,
           alt: float = 200.0, firing_hours: float | None = None) -> tuple[pd.DataFrame, dict]:
    if firing_hours is None:
        firing_hours = OI.FIRING_HOURS
    from scipy.stats import spearmanr
    a = {arch_name(z): z for z in enumerate_architectures()}[arch]
    rng = np.random.default_rng(seed)
    S = {k: UQ._tri(rng, lo, mo, hi, n) for k, (lo, mo, hi, _) in UQ.PRIORS.items()}
    rows = []
    for i in range(n):
        xs = {k: float(S[k][i]) for k in S}
        rows.append({**xs, **evaluate_sample(a, x, area, p_level, A_array, P_cap, xs, alt, firing_hours=firing_hours)})
    df = pd.DataFrame(rows)
    sens = {}
    for k in UQ.PRIORS:
        if df[k].std() > 0 and df.ratio_min.std() > 0:
            sens[k] = float(spearmanr(df[k], df.ratio_min).statistic)
    summ = {"arch": arch, "x": x, "area": area, "p_level": p_level, "A_array": A_array, "P_cap": P_cap, "n": n,
            "P_ignite": float(df.ignited.mean()), "P_close": float((df.ratio_min >= 1.0).mean()),
            "P_close_margin": float((df.ratio_min >= 1.1).mean()),
            "P_success": float(df.success.mean()), "P_life_ok": float((df.life_h >= firing_hours).mean()),
            "life_q": {q: float(df.life_h.quantile(q)) for q in (0.1, 0.5, 0.9)},
            "ratio_q": {q: float(df.ratio_min.quantile(q)) for q in (0.1, 0.5, 0.9)},
            "limit_counts": df.limit.value_counts().to_dict(),
            "spearman": dict(sorted(sens.items(), key=lambda kv: -abs(kv[1])))}
    return df, summ
