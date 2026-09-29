"""Shared helpers for the O/O2 v0 DRAFT rate-table builders (fo_o_o2_chemistry_v0).

Nothing here chooses a physical value. The builders pass every cross section, threshold, header energy and tail choice
explicitly; this module only (1) calls the repository's Maxwellian integrator and HallThruster.jl table writer
(abep_sim/rate_tables.py, read-only import, unchanged), (2) computes the source-support limit of a table the same way
hallthruster_bridge/propellants/rate_validity.toml defines it (highest mean energy at which the Maxwellian rate share
resting beyond the last cited cross-section point stays < 1 %, capped at 255 eV), and (3) writes / checks a manifest.

Tables are DRAFT and unused: no propellant configuration, campaign, HallMap or archengine path reads docs/chemistry/**.
Promotion into hallthruster_bridge/propellants/ is a later owner-approved model change.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
TABLES = os.path.join(HERE, "tables")
sys.path.insert(0, ROOT)
from abep_sim.rate_tables import maxwellian_rate, write_hallthruster_table  # noqa: E402

# Same grid and cap as the shipped N2/N tables (rate_validity.toml: HallThruster.jl interpolates tables on 0-255 eV).
EPS_MAX_TABLE = 300.0
SUPPORT_CAP_EV = 255.0
TAIL_SHARE_LIMIT = 0.01
# PROPOSED (owner decision OD-1 of o_o2_completeness_prereg_DRAFT.json): the project's pre-registered N2 domain
# convention, mean energy <= 45 eV (T_e <= 30 eV). Not an RFP value; not a decided O/O2 domain.
PROPOSED_DOMAIN_CAP_EV = 45.0
REPORT_EPS = [3.0, 15.0, 45.0, 100.0, 255.0]


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def tail_share(E_eV, sigma_m2, eps: float, tail: str) -> float:
    """Share of the rate resting beyond the last cited point: (k_hold - k_zero)/k_hold. With tail='zero' the table
    itself carries no extrapolated tail, so the returned value is the share the zero-tail ASSUMPTION removes relative to
    a held tail (reported, never hidden)."""
    a = maxwellian_rate(E_eV, sigma_m2, eps / 1.5, "hold")
    b = maxwellian_rate(E_eV, sigma_m2, eps / 1.5, "zero")
    return (a - b) / a if a > 0 else 0.0


def source_support_limit(E_eV, sigma_m2) -> float:
    """Highest integer mean energy (eV, <= 255) up to which the held-tail share stays < 1 % at every integer step."""
    last_ok = 0.0
    for eps in np.arange(1.0, SUPPORT_CAP_EV + 1.0, 1.0):
        if tail_share(E_eV, sigma_m2, float(eps), "hold") >= TAIL_SHARE_LIMIT:
            break
        last_ok = float(eps)
    return last_ok


def build_table(spec: dict, outdir: str) -> dict:
    """Write one HallThruster.jl-format table (+ .source) into outdir and return its manifest record."""
    E = np.asarray(spec["E_eV"], float)
    s = np.asarray(spec["sigma_m2"], float)
    if E.ndim != 1 or E.shape != s.shape or np.any(np.diff(E) <= 0) or np.any(s < 0):
        raise ValueError(f"{spec['file']}: energies must be strictly increasing and cross sections non-negative")
    for key in ("file", "header_energy_eV", "header_label", "tail", "source_text", "meta"):
        if key not in spec:
            raise KeyError(f"{spec.get('file', '?')}: missing required spec field {key!r} (no defaults)")
    path = os.path.join(outdir, spec["file"])
    write_hallthruster_table(path, E, s, spec["header_energy_eV"], eps_max=EPS_MAX_TABLE, source=spec["source_text"],
                             tail=spec["tail"], header_label=spec["header_label"])
    support = source_support_limit(E, s) if spec["tail"] == "hold" else None
    rec = {
        "file": f"tables/{spec['file']}",
        "sha256": sha256_file(path),
        "source_file": f"tables/{spec['file']}.source",
        "source_file_sha256": sha256_file(path + ".source"),
        "header": f"{spec['header_label']} (eV): {spec['header_energy_eV']}",
        "cross_section_points": int(E.size),
        "cross_section_energy_range_eV": [float(E[0]), float(E[-1])],
        "tail_beyond_last_point": spec["tail"],
        "tail_share_hold_vs_zero": {f"{eps:g}": round(tail_share(E, s, eps, spec["tail"]), 6) for eps in REPORT_EPS},
        "source_support_limit_mean_energy_eV": support,
        "source_support_rule": ("highest mean energy with held-tail rate share < 1 % (rate_validity.toml convention), "
                                "capped at 255 eV") if support is not None else
                               ("not applicable: tail = 'zero' (resonance table; the zero tail is an assumption, its "
                                "effect is tail_share_hold_vs_zero)"),
        "proposed_domain_cap_mean_energy_eV": PROPOSED_DOMAIN_CAP_EV,
        "draft_validity_limit_mean_energy_eV": (min(support, PROPOSED_DOMAIN_CAP_EV) if support is not None
                                                else PROPOSED_DOMAIN_CAP_EV),
        "draft_validity_basis": ("min(source-support limit, PROPOSED 45 eV mean-energy domain cap = N2 pre-registered "
                                 "convention, owner decision OD-1 pending)"),
    }
    rec.update(spec["meta"])
    return rec


def write_manifest(path: str, header: dict, records: list[dict]) -> None:
    doc = dict(header)
    doc["tables"] = records
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1, ensure_ascii=False)
        f.write("\n")


def run(specs: list[dict], manifest_name: str, manifest_header: dict, check: bool) -> int:
    """Build (default) or --check: rebuild into a temporary directory and compare bytes with the committed files."""
    if not check:
        os.makedirs(TABLES, exist_ok=True)
        recs = [build_table(sp, TABLES) for sp in specs]
        write_manifest(os.path.join(HERE, manifest_name), manifest_header, recs)
        for r in recs:
            print(f"wrote {r['file']}  support-limit {r['source_support_limit_mean_energy_eV']}  "
                  f"draft-limit {r['draft_validity_limit_mean_energy_eV']}")
        print("wrote", manifest_name)
        return 0
    bad = []
    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(os.path.join(tmp, "tables"))
        recs = [build_table(sp, os.path.join(tmp, "tables")) for sp in specs]
        write_manifest(os.path.join(tmp, manifest_name), manifest_header, recs)
        names = [manifest_name] + [r["file"] for r in recs] + [r["source_file"] for r in recs]
        for n in names:
            committed = os.path.join(HERE, n)
            if not os.path.exists(committed) or sha256_file(committed) != sha256_file(os.path.join(tmp, n)):
                bad.append(n)
    for n in bad:
        print("MISMATCH", n)
    print("check:", "OK" if not bad else f"FAILED ({len(bad)} file(s))")
    return 0 if not bad else 1
