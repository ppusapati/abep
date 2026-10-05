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
SEARCH_OUT = os.path.join(ROOT, "crates", "abep-intake", "data", "intake_surface_v1_delaunay_v1_search.json")
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
                t = ip.tri
                cur = {"points": np.asarray(pts, dtype=np.float64), "offset": ip.offset, "scale": ip.scale,
                       "simplices": t.simplices, "degenerate": np.isnan(t.transform[:, 0, 0]),
                       "transform": t.transform, "neighbors": t.neighbors, "equations": t.equations,
                       "paraboloid": np.array([t.paraboloid_scale, t.paraboloid_shift]),
                       "min_bound": t.min_bound, "max_bound": t.max_bound}
                if ref is None:
                    ref = cur
                else:
                    for k in cur:
                        if not np.array_equal(cur[k], ref[k], equal_nan=k == "transform"):
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
    # Search structures of scipy's simplex location (Delaunay.find_simplex / LinearNDInterpolator): the reference
    # triangulation is non-conforming across some interior grid faces (Qhull 'Qt' on cospherical cells), so the value
    # at a face point depends on which containing simplex scipy's walk reaches; Rust replicates that walk with these.
    search = {
        "schema": "abep_intake_surface_delaunay_search_v1",
        "id": "INTAKE-SURFACE-V1-DELAUNAY-SEARCH-V1",
        "what": "scipy Delaunay search structures of the triangulation in intake_surface_v1_delaunay_v1.json, captured "
                "from the reference; used by the Rust surface to replicate scipy's _find_simplex walk",
        "triangulation": {"path": os.path.relpath(OUT, ROOT), "sha256": sha(OUT)},
        "reference": doc["reference"],
        "identical_across": doc["identical_across"].replace("simplices and degenerate flags",
                                                            "simplices, degenerate flags, transform, neighbors, "
                                                            "equations, paraboloid scale / shift, min / max bound"),
        "transform": [None if np.isnan(tr[0, 0]) else tr.tolist() for tr in ref["transform"]],
        "transform_layout": "per simplex (ndim + 1) x ndim: rows 0..3 = inverse of T[i][j] = p[s_j][i] - p[s_4][i], "
                            "row 4 = rescaled vertex s_4; null = degenerate (scipy NaN)",
        "neighbors": ref["neighbors"].tolist(),
        "equations": ref["equations"].tolist(),
        "paraboloid_scale": float(ref["paraboloid"][0]),
        "paraboloid_shift": float(ref["paraboloid"][1]),
        "min_bound": ref["min_bound"].tolist(),
        "max_bound": ref["max_bound"].tolist(),
        "eps": "100 * DBL_EPSILON", "eps_broad": "sqrt(DBL_EPSILON)",
        "algorithm": "scipy.spatial._qhull _find_simplex (start 0: lifted-paraboloid walk with _distplane, then "
                     "_find_simplex_directed, brute-force fallback with the degenerate-neighbour rule), as used by "
                     "LinearNDInterpolator._evaluate_double with one query per call",
    }
    with open(SEARCH_OUT, "w") as f:
        json.dump(search, f, indent=None, separators=(",", ":"))
        f.write("\n")
    print(SEARCH_OUT, sha(SEARCH_OUT))


if __name__ == "__main__":
    main()
