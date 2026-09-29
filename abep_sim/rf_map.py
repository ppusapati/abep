"""RF response maps (parallel RF || Hall investigation, v2).

An RF map is an immutable JSON document (schema rf_map_v1) holding measured (or externally solved, e.g. EM + PIC)
RF-thruster performance on a regular grid over (mdot_kg_s, P_dc_W, B0_T), plus the admitted domain in composition,
pressure and temperature. Its identity is the SHA-256 of its bytes; its admission state lives only in the RF
registry (``rf_registry``), never in the map itself.

Interpolation is multilinear, and ONLY inside the admitted domain: a query outside any axis range, outside the
composition / pressure / temperature ranges, on different hardware (frequency, magnetic or antenna geometry), or in a
cell with an unmeasured / unstable / unignited corner returns OUT_OF_DOMAIN. Nothing is clipped or extrapolated.

Score-bearing use requires registry state ADMITTED (owner decision, sha-pinned). A registered-but-not-admitted map
can support planning, never a score-bearing result.
"""
from __future__ import annotations

import itertools
import json
import math
import os

from . import rf_registry
from .constants import G0
from .parallel_contracts import (SPECIES, BranchResult, ContractError, FeedState, Status, TBD, value_of)

MAP_SCHEMA = "rf_map_v1"
AXES = ("mdot_kg_s", "P_dc_W", "B0_T")
REQUIRED_FIELDS = ("thrust_N", "P_bus_W", "P_magnet_bus_W", "P_forward_W", "P_reflected_W", "P_absorbed_W", "Te_eV",
                   "ne_m3", "utilization", "Isp_s", "plume_divergence_deg", "stable", "ignited")
UNCERTAINTY_FIELDS = ("thrust_N", "P_bus_W")
META_KEYS = ("schema", "map_id", "propellant_family", "frequency_Hz", "magnetic_geometry_id", "antenna_geometry_id",
             "facility", "test_article", "measurement_method", "evidence_class", "applicability_domain",
             "validation_status", "source", "created")


class RFMapError(ContractError):
    pass


def _range(r, what):
    if not (isinstance(r, list) and len(r) == 2 and all(isinstance(x, (int, float)) for x in r) and r[0] <= r[1]):
        raise RFMapError(f"{what} must be [lo, hi] with lo <= hi")
    return float(r[0]), float(r[1])


def load_document(path: str) -> dict:
    """Load and validate a map document (structure, axes, field lengths, domain inside the grid)."""
    doc = json.load(open(path))
    meta = doc.get("meta", {})
    miss = [k for k in META_KEYS if k not in meta]
    if miss:
        raise RFMapError(f"RF map {path}: missing meta {miss}")
    if meta["schema"] != MAP_SCHEMA:
        raise RFMapError(f"RF map {path}: schema is {meta['schema']!r}, not {MAP_SCHEMA}")
    if meta["propellant_family"] not in ("atmospheric", "xe"):
        raise RFMapError("propellant_family must be 'atmospheric' or 'xe'")
    axes = doc.get("axes", {})
    if tuple(axes) != AXES:
        raise RFMapError(f"axes must be exactly {AXES} in that order")
    for a in AXES:
        v = axes[a]
        if not v or any(not isinstance(x, (int, float)) for x in v) or any(b <= c for c, b in zip(v, v[1:])):
            raise RFMapError(f"axis {a} must be a non-empty strictly increasing list of numbers")
    n = math.prod(len(axes[a]) for a in AXES)
    fields = doc.get("fields", {})
    missf = [f for f in REQUIRED_FIELDS if f not in fields]
    if missf:
        raise RFMapError(f"RF map {path}: missing fields {missf}")
    for f, vals in fields.items():
        if len(vals) != n:
            raise RFMapError(f"field {f} has {len(vals)} values, grid has {n}")
    NONNEG = ("thrust_N", "P_bus_W", "P_magnet_bus_W", "P_forward_W", "P_reflected_W", "P_absorbed_W", "Te_eV",
              "ne_m3", "utilization", "Isp_s", "plume_divergence_deg")
    for f in NONNEG:
        for i, x in enumerate(fields[f]):
            if x is None:
                continue
            if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or x < 0:
                raise RFMapError(f"field {f}[{i}] = {x!r} must be a finite number >= 0 or null")
    for f in ("stable", "ignited"):
        if any(x not in (0, 1) for x in fields[f]):
            raise RFMapError(f"field {f} must contain only 0 or 1")
    unc = doc.get("uncertainty_1sigma", {})
    for f in UNCERTAINTY_FIELDS:
        if f not in unc or len(unc[f]) != n:
            raise RFMapError(f"uncertainty_1sigma.{f} is required on every grid point")
    for f in UNCERTAINTY_FIELDS:
        for i, x in enumerate(unc[f]):
            if fields[f][i] is not None and (x is None or isinstance(x, bool) or not isinstance(x, (int, float))
                                             or not math.isfinite(x) or x < 0):
                raise RFMapError(f"uncertainty_1sigma.{f}[{i}] must be a finite number >= 0 where {f} is measured")
    dom = doc.get("domain", {})
    for a in AXES:
        lo, hi = _range(dom.get(a), f"domain.{a}")
        if lo < axes[a][0] or hi > axes[a][-1]:
            raise RFMapError(f"domain.{a} extends beyond the measured grid")
    for k in ("pressure_Pa", "temperature_K"):
        _range(dom.get(k), f"domain.{k}")
    comp = dom.get("composition_mass_fraction", {})
    if set(comp) != set(SPECIES):
        raise RFMapError(f"domain.composition_mass_fraction must give a range for every species {SPECIES}")
    for s in SPECIES:
        _range(comp[s], f"composition range of {s}")
    grid = list(itertools.product(*(axes[a] for a in AXES)))
    for i in range(n):
        pb, pm, sig = fields["P_bus_W"][i], fields["P_magnet_bus_W"][i], unc["P_bus_W"][i]
        if pb is None or pm is None:
            continue
        expect = grid[i][1] + pm                      # P_dc axis (rf_source bus draw) + magnet bus draw
        if abs(pb - expect) > 3.0 * (sig or 0.0) + 1e-9 * max(expect, 1.0):
            raise RFMapError(f"grid point {i}: measured P_bus_W {pb!r} != P_dc {grid[i][1]!r} + P_magnet_bus "
                             f"{pm!r} beyond 3 sigma; the RF branch bus boundary is inconsistent")
    if "discharge_mode" in fields and any(not isinstance(x, (str, type(None))) for x in fields["discharge_mode"]):
        raise RFMapError("discharge_mode values must be strings (e.g. capacitive / inductive / helicon) or null")
    return doc


class RFMap:
    def __init__(self, path: str, registry_dir: str | None = None):
        self.doc = load_document(path)
        self.sha256 = rf_registry.sha256_file(path)
        if registry_dir:
            self.registry_state = rf_registry.state(registry_dir, self.sha256)
            if self.registry_state == "ADMITTED":
                rf_registry.verify(registry_dir, self._root(registry_dir, path))   # re-hash map + decision files
        else:
            self.registry_state = "UNREGISTERED"
        self.meta, self.axes, self.fields = self.doc["meta"], self.doc["axes"], self.doc["fields"]
        self.unc, self.domain = self.doc["uncertainty_1sigma"], self.doc["domain"]
        self.shape = tuple(len(self.axes[a]) for a in AXES)

    @staticmethod
    def _root(registry_dir: str, path: str) -> str:
        """The repository root the registry records are relative to: the REGISTER record's map_file must resolve
        to this map file."""
        for rec in rf_registry.records(registry_dir):
            if rec["action"] == "REGISTER" and os.path.abspath(path).endswith(os.sep + rec["map_file"]):
                return os.path.abspath(path)[: -len(rec["map_file"]) - 1] or os.sep
        raise RFMapError("map file is not the registered file of any REGISTER record")

    @property
    def admitted(self) -> bool:
        return self.registry_state == "ADMITTED"

    def _flat(self, idx):
        i = 0
        for k, n in zip(idx, self.shape):
            i = i * n + k
        return i

    def out_of_domain_reasons(self, feed: FeedState, P_dc_W: float, B0_T: float, frequency_Hz: float,
                              magnetic_geometry_id: str, antenna_geometry_id: str) -> list:
        r = []
        fam = "xe" if feed.is_pure_xe() else ("atmospheric" if not feed.has_xe() else "mixed")
        if fam != self.meta["propellant_family"]:
            r.append(f"propellant family {fam} != map {self.meta['propellant_family']}")
        if frequency_Hz != self.meta["frequency_Hz"]:
            r.append("RF frequency differs from the mapped hardware")
        if magnetic_geometry_id != self.meta["magnetic_geometry_id"]:
            r.append("magnetic geometry differs from the mapped hardware")
        if antenna_geometry_id != self.meta["antenna_geometry_id"]:
            r.append("antenna geometry differs from the mapped hardware")
        q = {"mdot_kg_s": feed.mdot_total_kg_s, "P_dc_W": P_dc_W, "B0_T": B0_T,
             "pressure_Pa": feed.pressure_Pa, "temperature_K": feed.temperature_K}
        for k, v in q.items():
            lo, hi = self.domain[k]
            if not lo <= v <= hi:
                r.append(f"{k} = {v!r} outside admitted [{lo!r}, {hi!r}]")
        for s in SPECIES:
            lo, hi = self.domain["composition_mass_fraction"][s]
            x = feed.mass_fractions[s]
            if not lo <= x <= hi:
                r.append(f"mass fraction of {s} = {x!r} outside admitted [{lo!r}, {hi!r}]")
        return r

    def interpolate(self, mdot_kg_s: float, P_dc_W: float, B0_T: float):
        """Multilinear interpolation of every field; returns (values, sigmas) or a list of reasons (OUT_OF_DOMAIN)."""
        q = (mdot_kg_s, P_dc_W, B0_T)
        lo_idx, w = [], []
        for a, x in zip(AXES, q):
            ax = self.axes[a]
            if len(ax) == 1:
                if x != ax[0]:
                    return [f"{a} not on the single-valued axis"]
                lo_idx.append(0); w.append(0.0)
                continue
            if not ax[0] <= x <= ax[-1]:
                return [f"{a} outside the grid"]
            k = max(i for i in range(len(ax) - 1) if ax[i] <= x) if x < ax[-1] else len(ax) - 2
            lo_idx.append(k); w.append((x - ax[k]) / (ax[k + 1] - ax[k]))
        corners = []
        for bits in itertools.product((0, 1), repeat=3):
            idx, wt = [], 1.0
            for d, b in enumerate(bits):
                if len(self.axes[AXES[d]]) == 1:
                    if b:
                        wt = 0.0
                    idx.append(0)
                    continue
                idx.append(lo_idx[d] + b)
                wt *= w[d] if b else (1 - w[d])
            if wt > 0.0:
                corners.append((self._flat(idx), wt))
        bad = [i for i, _ in corners if self.fields["thrust_N"][i] is None or not self.fields["stable"][i]
               or not self.fields["ignited"][i]]
        if bad:
            return [f"cell has unmeasured / unstable / unignited grid points {sorted(set(bad))}"]
        if "discharge_mode" in self.fields:
            modes = {self.fields["discharge_mode"][i] for i, _ in corners}
            if len(modes) != 1 or None in modes:
                return [f"cell spans discharge modes {sorted(map(str, modes))}; no interpolation across a mode jump"]
        vals = {}
        for f in REQUIRED_FIELDS:   # Isp is re-derived from interpolated thrust (not interpolated independently)
            if any(self.fields[f][i] is None for i, _ in corners):
                vals[f] = TBD(f, "not measured at every corner of this cell")
            else:
                vals[f] = math.fsum(self.fields[f][i] * wt for i, wt in corners)
        sig = {f: math.fsum(self.unc[f][i] * wt for i, wt in corners) for f in UNCERTAINTY_FIELDS}
        return vals, sig

    def branch_result(self, feed, spec, P_dc_W, config, axis, *, score_bearing: bool) -> BranchResult:
        from .rf_branch import ScoreBearingError
        if score_bearing and not self.admitted:
            raise ScoreBearingError(f"RF map {self.meta['map_id']} ({self.sha256[:12]}) is {self.registry_state}; "
                                    "score-bearing use needs an ADMITTED map")
        B0 = value_of(config.nozzle.B0_T, "B0", "T")
        f_Hz = value_of(config.coupling.frequency_Hz, "frequency", "Hz")
        reasons = self.out_of_domain_reasons(feed, P_dc_W, B0, f_Hz, config.nozzle.magnetic_geometry_id,
                                             config.coupling.antenna_geometry_id)
        res = None if reasons else self.interpolate(feed.mdot_total_kg_s, P_dc_W, B0)
        if res is not None and isinstance(res, list):
            reasons, res = res, None
        common = dict(branch_id="rf", operating_mode=spec.mode.value,
                      propellant_source="atmosphere" if spec.rf_atm_allowed else "xe_tank",
                      mdot_atm_kg_s=feed.mdot_total_kg_s if spec.rf_atm_allowed else 0.0,
                      mdot_xe_kg_s=feed.mdot_total_kg_s if spec.rf_xe_allowed else 0.0, mdot_cathode_xe_kg_s=0.0,
                      evidence_class=self.meta["evidence_class"],
                      applicability_domain=self.meta["applicability_domain"],
                      validation_status=f"RF_MAP_{self.registry_state}; {self.meta['validation_status']}",
                      score_bearing=bool(score_bearing and self.admitted and not reasons),
                      startup_energy_J=getattr(config.startup_energy_J, "value", config.startup_energy_J),
                      startup_time_s=getattr(config.startup_time_s, "value", config.startup_time_s),
                      limitations=("interpolation inside the admitted domain only",))
        prov = {"source": "ADMITTED_RF_MAP" if self.admitted else "REGISTERED_RF_MAP", "map_id": self.meta["map_id"],
                "map_sha256": self.sha256, "registry_state": self.registry_state}
        if reasons:
            t = TBD("thrust_N", "OUT_OF_DOMAIN: " + "; ".join(reasons))
            return BranchResult(thrust_vector_N=t, thrust_axial_N=t, P_loads={}, P_bus_W=TBD("P_bus_W", "out of domain"),
                                Isp_s=TBD("Isp_s", "out of domain"), utilization=TBD("utilization", "out of domain"),
                                heat_loads_W={}, plume_divergence_deg=TBD("plume_divergence_deg", "out of domain"),
                                status=Status.OUT_OF_DOMAIN, provenance={**prov, "reasons": reasons}, **common)
        v, sig = res
        T = v["thrust_N"]
        eta_mag = value_of(config.eta_magnet_supply, "eta_magnet_supply", "1")
        net = (v["P_forward_W"] - v["P_reflected_W"]) if not any(isinstance(v[k], TBD) for k in
                                                                  ("P_forward_W", "P_reflected_W")) else None
        loads = {"rf_source": {"P_load_W": net if net is not None else TBD("P_net_feed_W", "not measured"),
                               "efficiency": (net / P_dc_W) if net is not None and P_dc_W > 0 else
                               TBD("eta_rf_source", "not measured")},
                 "rf_magnet": {"P_load_W": v["P_magnet_bus_W"] * eta_mag, "efficiency": config.eta_magnet_supply.to_dict()}}
        return BranchResult(thrust_vector_N=tuple(T * a for a in axis), thrust_axial_N=T * axis[0], P_loads=loads,
                            P_bus_W=P_dc_W + v["P_magnet_bus_W"], Isp_s=T / (feed.mdot_total_kg_s * G0),
                            utilization=v["utilization"],
                            heat_loads_W={}, plume_divergence_deg=v["plume_divergence_deg"], status=Status.PASS,
                            provenance={**prov, "interpolated": {k: (x if not isinstance(x, TBD) else x.to_dict())
                                                                 for k, x in v.items()}, "sigma_1": sig,
                                        "P_bus_basis": "P_dc + P_magnet_bus (ledger identity); the measured P_bus_W "
                                                       "is in 'interpolated' and agrees within 3 sigma (load check)"},
                            **common)
