"""Frozen Hall-discharge response maps produced offline by HallThruster.jl (the authoritative Hall solver).

A map is a JSON file following hall_map_schema_v1 (hallthruster_bridge/hall_map_schema_v1.json, shared with the Julia
driver; field names, units and definitions live there, not here):
  meta.schema      — must be "hall_map_schema_v1"
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

SCHEMA_NAME = "hall_map_schema_v1"
SCHEMA_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "hallthruster_bridge", f"{SCHEMA_NAME}.json")


def load_schema(path: str = SCHEMA_FILE) -> dict:
    """The one interchange schema shared with hallthruster_bridge/run_cases.jl (field names, units, definitions)."""
    s = json.load(open(path))
    if s.get("schema") != SCHEMA_NAME:
        raise ValueError(f"{path} is not {SCHEMA_NAME}")
    return s


SCHEMA = load_schema()
REQUIRED_FIELDS = tuple(SCHEMA["fields"])
REQUIRED_META = tuple(SCHEMA["meta_required"])


def missing_fields(record: dict) -> list[str]:
    """Schema fields absent from one operating-point record (a record with any missing is not map-ready)."""
    return [f for f in REQUIRED_FIELDS if f not in record]


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
        if meta.get("schema") != SCHEMA_NAME:
            raise ValueError(f"Hall map {path} is not {SCHEMA_NAME} (meta.schema = {meta.get('schema')!r})")
        missing_meta = [k for k in REQUIRED_META if k not in meta]
        if missing_meta:
            raise ValueError(f"Hall map {path} missing required meta: {missing_meta}")
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
