"""Finding B2-OF-01: interior-face survey of the frozen Python reference IntakeSurface (Python only, read only).

The reference interpolant (scipy LinearNDInterpolator(rescale=True) over the Qhull triangulation of the degenerate v1
tensor grid, as built by abep_sim.intake._tpmc_surface / IntakeSurface) is non-conforming across some interior grid
faces. For points ON an interior face (one axis at an interior grid value, the others uniform) this script evaluates
every non-degenerate simplex that contains the point (scipy's eps = 100 DBL_EPSILON) and reports the spread of the
linearly interpolated row values, (max - min) / |mean|, per field, species and scattering table. A spread above
rounding means the reference value there depends on which containing simplex scipy's walk reaches.

This is a property of the frozen Python reference (data abep_sim/data/intake_surface_v1.csv + scipy/Qhull), not of
the Rust port. Writes docs/rust_migration/contracts/C-ABEP_SIM_INTAKE_TPMC_PY/finding_B2-OF-01_face_survey_v1.json.

    OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python3 scripts/rust_migration/survey_intake_surface_faces.py
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd
import scipy
from scipy.interpolate import LinearNDInterpolator

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, ROOT)
from abep_sim.intake_tpmc import frozen_surface_path  # noqa: E402

OUT = os.path.join(ROOT, "docs", "rust_migration", "contracts", "C-ABEP_SIM_INTAKE_TPMC_PY",
                   "finding_B2-OF-01_face_survey_v1.json")
AXES = ["L_over_d", "phi", "alpha", "theta_deg"]
COLS = ["eta_c", "C_D", "CR_passive", "K_back", "mass_kg"]
GRID = {"L_over_d": [3.0, 5.0, 10.0, 20.0], "phi": [0.8, 0.9], "alpha": [0.0, 0.2, 0.5, 0.8, 1.0],
        "theta_deg": [0.0, 2.0, 5.0]}
LO = {"L_over_d": 3.0, "phi": 0.8, "alpha": 0.0, "theta_deg": 0.0}
HI = {"L_over_d": 20.0, "phi": 0.9, "alpha": 1.0, "theta_deg": 5.0}
N_PER_FACE = 60
SEED = 0
RTOL = 1e-12                     # spreads at or below this are rounding
CHECK_POINTS = [(10.0, 0.85, 0.5, 0.0), (5.0, 0.85, 0.8, 0.0), (10.0, 0.85, 0.95, 0.0), (3.0, 0.85, 0.5, 0.0),
                (5.0, 0.85, 0.8, 2.0)]


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def main() -> None:
    df = pd.read_csv(frozen_surface_path())
    eps = 100 * np.finfo(float).eps
    out = {"schema": "abep_finding_face_survey_v1", "id": "B2-OF-01",
           "property_of": "the frozen Python reference abep_sim.intake_tpmc.IntakeSurface over "
                          "abep_sim/data/intake_surface_v1.csv (scipy LinearNDInterpolator / Qhull); NOT a property "
                          "of the Rust port, which replicates scipy's simplex search and reproduces it",
           "frozen_surface": {"csv": "abep_sim/data/intake_surface_v1.csv", "csv_sha256": sha(frozen_surface_path())},
           "reference_module_sha256": sha(os.path.join(ROOT, "abep_sim", "intake_tpmc.py")),
           "environment": {"python": sys.version.split()[0], "numpy": np.__version__, "scipy": scipy.__version__,
                           "pandas": pd.__version__},
           "generator": {"path": "scripts/rust_migration/survey_intake_surface_faces.py",
                         "command": "OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python3 "
                                    "scripts/rust_migration/survey_intake_surface_faces.py"},
           "method": f"per scattering table and interior face (axis at an interior grid value), {N_PER_FACE} points "
                     f"with the other axes uniform in the table range (numpy default_rng({SEED}), draws in axis "
                     "order); every non-degenerate reference simplex containing the rescaled point within eps = 100 "
                     "DBL_EPSILON is evaluated; spread = (max - min) / |mean| of the interpolated row value per field "
                     f"and species; a point is non-conforming when any spread exceeds {RTOL}. phi has no interior "
                     "grid value (2 values), hence no interior face",
           "tables": {}}
    worst = {c: {"spread": 0.0} for c in COLS}
    for scat in ("maxwell", "cll"):
        sdf = df[df.scattering == scat].reset_index(drop=True)
        species = sorted(sdf["species"].unique())
        ips = {(sp, c): LinearNDInterpolator(sdf[sdf.species == sp][AXES].values, sdf[sdf.species == sp][c].values,
                                             rescale=True) for sp in species for c in COLS}
        ip0 = ips[(species[0], COLS[0])]
        tri = ip0.tri
        valid = ~np.isnan(tri.transform[:, 0, 0])

        def spreads(x):
            xr = (np.asarray(x, float) - ip0.offset) / ip0.scale
            vals = {(sp, c): [] for sp in species for c in COLS}
            for i in np.nonzero(valid)[0]:
                t = tri.transform[i]
                cc = t[:4].dot(xr - t[4])
                cc = np.append(cc, 1 - cc.sum())
                if (cc >= -eps).all() and (cc <= 1 + eps).all():
                    smp = tri.simplices[i]
                    for key in vals:
                        vals[key].append(float(np.dot(cc, ips[key].values[smp, 0])))
            return {k: (max(v) - min(v)) / abs(np.mean(v)) for k, v in vals.items()}

        rng = np.random.default_rng(SEED)
        faces = []
        for ax in AXES:
            for gv in GRID[ax][1:-1]:
                worst_f = {sp: {c: 0.0 for c in COLS} for sp in species}
                n_nc = 0
                for _ in range(N_PER_FACE):
                    x = [float(rng.uniform(LO[a], HI[a])) for a in AXES]
                    x[AXES.index(ax)] = gv
                    sp_ = spreads(x)
                    n_nc += max(sp_.values()) > RTOL
                    for (sp, c), v in sp_.items():
                        if v > worst_f[sp][c]:
                            worst_f[sp][c] = v
                        if v > worst[c]["spread"]:
                            worst[c] = {"spread": v, "scattering": scat, "species": sp, "face": f"{ax} = {gv:g}",
                                        "point": x}
                faces.append({"face": f"{ax} = {gv:g}", "points": N_PER_FACE, "non_conforming_points": int(n_nc),
                              "max_relative_spread": worst_f})
        checks = []
        for x in CHECK_POINTS:
            sp_ = spreads(x)
            checks.append({"point": list(x), "max_relative_spread": max(sp_.values())})
        out["tables"][scat] = {"faces": faces, "default_points_checked": checks}
    out["max_relative_spread_per_field"] = worst
    out["affected_faces"] = sorted({f["face"] for t in out["tables"].values() for f in t["faces"]
                                    if f["non_conforming_points"] > 0})
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1)
        f.write("\n")
    print(OUT, sha(OUT))
    print(json.dumps({c: {k: v for k, v in w.items() if k != "point"} for c, w in worst.items()}, indent=1))
    print(out["affected_faces"])


if __name__ == "__main__":
    main()
