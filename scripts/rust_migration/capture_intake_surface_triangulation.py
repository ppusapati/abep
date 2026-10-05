"""Capture the reference triangulation of the frozen intake surface v1 (contract C-ABEP_SIM_INTAKE_TPMC_PY).

abep_sim.intake_tpmc.IntakeSurface interpolates with scipy.interpolate.LinearNDInterpolator(rescale=True): points are
rescaled to (p - mean) / ptp, triangulated by scipy.spatial.Delaunay (Qhull, options "Qbb Qc Qz Q12" + "Qt"), and a
query is interpolated linearly in the simplex that contains it. The v1 grid is a full tensor product, so the Delaunay
problem is degenerate (all 16 corners of a grid cell are cospherical) and the interpolant depends on the particular
simplices Qhull returns; any other triangulation (or multilinear interpolation) differs by up to ~10 % (CR_passive).
The Rust IntakeSurface therefore reads this capture of the reference's own triangulation instead of re-triangulating.

This reads the reference; it computes no TPMC, does not touch intake_surface_v1.* and creates no reference values.
Every one of the 6 (scattering, species) tables x 5 interpolated columns builds its own LinearNDInterpolator exactly as
intake._tpmc_surface / IntakeSurface do; the capture is written only if all 30 triangulations, offsets and scales are
identical. Run in the reference environment:

    python3 scripts/rust_migration/capture_intake_surface_triangulation.py
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys

import numpy as np
import pandas as pd
import scipy
from scipy.interpolate import LinearNDInterpolator
import scipy.spatial._qhull as _qhull

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, ROOT)
from abep_sim.intake_tpmc import frozen_surface_path  # noqa: E402

OUT = os.path.join(ROOT, "crates", "abep-intake", "data", "intake_surface_v1_delaunay_v1.json")
AXES = ["L_over_d", "phi", "alpha", "theta_deg"]
COLUMNS = ["eta_c", "C_D", "CR_passive", "K_back", "mass_kg"]


def sha(p: str) -> str:
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def main() -> None:
    csv = frozen_surface_path()
    df = pd.read_csv(csv)
    ref = None
    n_checked = 0
    for scat in ("maxwell", "cll"):
        sdf = df[df.scattering == scat].reset_index(drop=True)
        for sp in sorted(sdf["species"].unique()):
            d = sdf[sdf["species"] == sp]
            pts = d[AXES].values
            for col in COLUMNS:
                ip = LinearNDInterpolator(pts, d[col].values, rescale=True)
                cur = {"points": np.asarray(pts, dtype=np.float64), "offset": ip.offset, "scale": ip.scale,
                       "simplices": ip.tri.simplices, "degenerate": np.isnan(ip.tri.transform[:, 0, 0])}
                if ref is None:
                    ref = cur
                else:
                    for k in cur:
                        if not np.array_equal(cur[k], ref[k]):
                            raise SystemExit(f"triangulation input/output {k} differs for {scat}/{sp}/{col}")
                n_checked += 1
    so = open(_qhull.__file__, "rb").read()
    m = re.search(rb"qhull_r [0-9.]+ \([^)]*\)", so)
    doc = {
        "schema": "abep_intake_surface_triangulation_v1",
        "id": "INTAKE-SURFACE-V1-DELAUNAY-V1",
        "what": "reference triangulation of abep_sim/data/intake_surface_v1.csv as built by IntakeSurface "
                "(scipy LinearNDInterpolator(rescale=True)); captured from the reference, not computed by Rust",
        "frozen_surface": {"csv": "abep_sim/data/intake_surface_v1.csv", "csv_sha256": sha(csv),
                           "json": "abep_sim/data/intake_surface_v1.json",
                           "json_sha256": sha(csv.replace(".csv", ".json"))},
        "reference": {"module": "abep_sim/intake_tpmc.py",
                      "module_sha256": sha(os.path.join(ROOT, "abep_sim", "intake_tpmc.py")),
                      "construction": "intake._tpmc_surface: pandas.read_csv(frozen) -> rows of one scattering -> "
                                      "IntakeSurface -> per species LinearNDInterpolator(rows[L_over_d, phi, alpha, "
                                      "theta_deg], column, rescale=True)",
                      "python": sys.version.split()[0], "numpy": np.__version__, "scipy": scipy.__version__,
                      "pandas": pd.__version__, "qhull": m.group(0).decode() if m else None,
                      "qhull_options": "scipy.spatial.Delaunay default for ndim <= 4: 'Qbb Qc Qz Q12' + required 'Qt'"},
        "identical_across": f"{n_checked} interpolators (2 scattering x 3 species x 5 columns): points, offset, scale, "
                            "simplices and degenerate flags bitwise identical",
        "axes": AXES,
        "point_rule": "point k = row k of each (scattering, species) table in CSV row order; all 6 tables list the same "
                      "120 points in the same order",
        "points": ref["points"].tolist(),
        "rescale": {"offset": ref["offset"].tolist(), "scale": ref["scale"].tolist(),
                    "rule": "offset = numpy.mean(points, axis=0) (sequential row sum / 120), scale = numpy.ptp(points, "
                            "axis=0); rescaled = (p - offset) / scale, query likewise"},
        "simplices": ref["simplices"].tolist(),
        "degenerate": ref["degenerate"].tolist(),
        "degenerate_rule": "scipy marks a simplex degenerate (NaN barycentric transform) when its LU fails or its "
                           "reciprocal condition number is below the scipy limit; a degenerate simplex is never "
                           "selected",
        "counts": {"points": int(len(ref["points"])), "simplices": int(len(ref["simplices"])),
                   "degenerate": int(ref["degenerate"].sum())},
        "find_simplex_eps": "100 * DBL_EPSILON (scipy _qhull eps); a query is inside a simplex when every barycentric "
                            "coordinate lies in [-eps, 1 + eps]",
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(doc, f, indent=1)
        f.write("\n")
    print(OUT, doc["counts"], sha(OUT))


if __name__ == "__main__":
    main()
