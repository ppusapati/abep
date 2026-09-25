"""Frozen Hall-discharge response maps produced offline by HallThruster.jl (the authoritative Hall solver).

A map is a JSON file with:
  meta.pinned      — must contain the pinned commit of hallthruster_bridge/PINNED.toml
  meta.reaction_set, meta.grid, meta.dt_s, meta.duration_s
  axes             — names and values of the regular grid (e.g. Vd, mdot_kgps, x_O, ...)
  fields           — arrays over the grid for every REQUIRED output (below)
The loader refuses maps from another commit, maps missing required fields, and flags points that did not converge.
Interpolation is multilinear on the regular grid; queries outside the axes raise (no silent extrapolation).
"""
from __future__ import annotations
import json, os
import numpy as np

REQUIRED_FIELDS = ("thrust_N", "discharge_current_A", "ion_current_A", "discharge_power_W", "anode_eff", "mass_eff",
                   "Te_max_eV", "ne_max_m3", "divergence_eff", "wall_ion_flux_m2s", "wall_ion_energy_eV",
                   "ion_species_fraction_atomic", "Id_osc_rel", "sustained", "converged")


def pinned_commit(bridge_dir: str | None = None) -> str:
    bridge_dir = bridge_dir or os.path.join(os.path.dirname(os.path.dirname(__file__)), "hallthruster_bridge")
    for line in open(os.path.join(bridge_dir, "PINNED.toml")):
        if line.strip().startswith("commit"):
            return line.split("=")[1].split("#")[0].strip().strip('"')
    raise ValueError("no pinned commit")


class HallMap:
    def __init__(self, path: str, bridge_dir: str | None = None):
        d = json.load(open(path))
        meta = d["meta"]
        if pinned_commit(bridge_dir) not in meta.get("pinned", ""):
            raise ValueError(f"Hall map {path} was not produced with the pinned HallThruster.jl commit")
        missing = [f for f in REQUIRED_FIELDS if f not in d["fields"]]
        if missing:
            raise ValueError(f"Hall map {path} missing required fields: {missing}")
        self.meta = meta
        self.axes = {k: np.asarray(v, float) for k, v in d["axes"].items()}
        self.names = list(d["axes"].keys())
        shape = tuple(len(self.axes[k]) for k in self.names)
        self.fields = {k: np.asarray(v, float).reshape(shape) for k, v in d["fields"].items()}
        self.bad = ~(self.fields["converged"].astype(bool))

    def __call__(self, **q) -> dict:
        from scipy.interpolate import RegularGridInterpolator
        pt = []
        for k in self.names:
            v = float(q[k]); a = self.axes[k]
            if not (a[0] - 1e-12 <= v <= a[-1] + 1e-12):
                raise ValueError(f"Hall map query {k}={v} outside [{a[0]}, {a[-1]}] — no extrapolation")
            pt.append(v)
        out = {}
        for k, arr in self.fields.items():
            out[k] = float(RegularGridInterpolator([self.axes[n] for n in self.names], arr)(pt)[0])
        # a query is trustworthy only if every surrounding grid node converged and sustained
        idx = [np.clip(np.searchsorted(self.axes[n], v) - 1, 0, len(self.axes[n]) - 2) for n, v in zip(self.names, pt)]
        cube = self.bad[tuple(slice(i, i + 2) for i in idx)]
        out["trustworthy"] = bool(not cube.any()) and out["sustained"] > 0.999
        out["hallthruster_commit"] = pinned_commit()
        return out
