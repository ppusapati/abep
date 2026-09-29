"""Build the atomic-O ionization DRAFT rate tables (e + O(3P) -> O+ + 2e) from NIST SRD 107 (fo_o_o2_chemistry_v0).

Source table: NIST Standard Reference Database 107 ("Electron-Impact Cross Sections for Ionization and Excitation"),
atomic O, ASCII mode: https://physics.nist.gov/cgi-bin/Ionization/merge.php?file=OI--&mode=ASCII, fetched 2026-09-27,
raw sha256 pinned below (RAW_SHA256). Same access route as hallthruster_bridge/propellants/ionization_N.dat
(scripts/build_n_ionization_table.py). The NIST table itself is NOT committed (NIST SRD terms; repository precedent); only
the Maxwellian-integrated rate tables derived from it are. Columns used:
  * "Total{kim02}": BEB direct + excitation-autoionization of Y.-K. Kim and J.-P. Desclaux, Phys. Rev. A 66, 012708
    (2002), doi:10.1103/PhysRevA.66.012708 (paper not accessed; paywalled). 129 energies, 13.62-5000 eV.
    -> ionization_O_beb_kd2002.dat   (quantity type: model-derived)
  * "{thomp95}": W. R. Thompson, M. B. Shah and H. B. Gilbody, J. Phys. B 28, 1321 (1995),
    doi:10.1088/0953-4075/28/7/023 (paper not accessed; paywalled; points as tabulated by NIST). 47 points, 14.1-2000 eV.
    SONG2026 (JPCRD 55, 013102, Sec. III.D) recommends the experimental data and states BEB "agrees well" with them.
    -> ionization_O_thompson1995.dat (quantity type: measured, as tabulated by NIST)
    Whether the NIST {thomp95} column is the single-ionization O+ partial or the counting total is not stated on the
    fetched page: verify (SONG2026: O^2+ formation is about 3 % of O+ at 200-2000 eV, so the difference is small in the
    proposed domain but not zero).
Which of the two is nominal is an OWNER DECISION (lane 13 matrix row OO2-01 open issue); both are DRAFT alternatives.

Header 13.618 eV = O ionization energy (Itikawa & Ichimura, JPCRD 19, 637 (1990), Table 2.1; NIST SRD 107 atom page
13.6181 eV; SONG2026 13.62 eV). sigma(13.618 eV) = 0 is prepended to both tables (for Thompson this makes a linear ramp to
the 14.1 eV point: assumed segment). Held tail above the last point (share recorded).
Evidence level 4 (docs/EVIDENCE.md: evaluated / validated-model literature via NIST SRD compilation).
Usage:
  python docs/chemistry/o_o2/v0/build_tables_nist107_o.py [--from-file RAW.txt]            # build
  python docs/chemistry/o_o2/v0/build_tables_nist107_o.py --check [--from-file RAW.txt]    # rebuild + byte-compare
Without --from-file the NIST page is fetched. The raw bytes must match RAW_SHA256 or the build stops (a changed NIST
table is a new source version that needs re-audit, never a silent update).
"""
from __future__ import annotations

import hashlib
import os
import re
import sys
import urllib.request

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from o_o2_v0_common import run  # noqa: E402

URL = "https://physics.nist.gov/cgi-bin/Ionization/merge.php?file=OI--&mode=ASCII"
RAW_SHA256 = "76df7f7a223a803ab5902eeae0b557ffb2d3317ba692a37676851781a1d225d8"
IE_O = 13.618
M2_PER_1E16CM2 = 1e-20


def load_raw(path: str | None) -> bytes:
    if path:
        with open(path, "rb") as f:
            raw = f.read()
    else:
        req = urllib.request.Request(URL, headers={"User-Agent": "abep-sim O/O2 v0 DRAFT table build"})
        raw = urllib.request.urlopen(req, timeout=60).read()
    got = hashlib.sha256(raw).hexdigest()
    if got != RAW_SHA256:
        raise SystemExit(f"NIST SRD 107 O table sha256 {got} != pinned {RAW_SHA256}: source changed; re-audit required")
    return raw


def parse(raw: bytes):
    lines = [re.sub(r"<[^>]+>", "", l) for l in raw.decode("utf-8", "ignore").splitlines()]
    header = next(l for l in lines if l.startswith("T (eV)")).split("\t")
    col = {name.strip(): i for i, name in enumerate(header)}
    i_tot, i_th = col["Total{kim02}"], col["{thomp95}"]
    rows = [l.split("\t") for l in lines if l[:1].isdigit()]

    def column(i):
        pts = [(float(r[0]), float(r[i])) for r in rows if len(r) > i and r[i].strip()]
        E = np.array([IE_O] + [e for e, _ in pts if e > IE_O])
        s = np.array([0.0] + [v for e, v in pts if e > IE_O]) * M2_PER_1E16CM2
        return E, s
    return column(i_tot), column(i_th)


COMMON = {
    "status": "DRAFT_UNUSED",
    "status_meaning": ("Provenance-backed DRAFT table for owner review. Not in any propellant configuration, campaign, "
                       "HallMap or architecture trade. Promotion is a later owner-approved model change."),
    "id": "OO2-01", "reaction": "e + O(3P) -> O+ + 2e", "solver_reaction_type": "ionization (electron_impact)",
    "evidence_level": 4,
    "header_basis": "13.618 eV O ionization energy (II1990 Table 2.1; NIST SRD 107 atom page 13.6181 eV; SONG2026 13.62 eV)",
    "extraction_method": "machine-parsed from the NIST SRD 107 ASCII table (raw sha256 pinned; raw not committed)",
    "raw_source": {"url_accessed": URL, "accessed": "2026-09-27", "raw_sha256": RAW_SHA256,
                   "committed": False, "reason": "NIST SRD terms; same precedent as scripts/build_n_ionization_table.py"},
    "applicability": ("ground-state O(3P) target; Brook et al. 1978 saw signal from 12.9 eV possibly from O(1D) in the beam "
                      "(SONG2026 Sec. III.D); metastable O(1D) ionization not included"),
    "milestones_supported": ["A (conditional: shows the O/O2 chemistry path is source-backed, not a gate)"],
    "rfp_thresholds_used": "none",
    "nominal_choice": "OWNER DECISION (BEB vs Thompson 1995; lane 13 row OO2-01)",
}


def specs(raw: bytes):
    (E_b, s_b), (E_t, s_t) = parse(raw)
    # cross-check (not a fit, not a selection): Thompson points / BEB interpolated at the same energy, 20-200 eV
    sel = (E_t >= 20.0) & (E_t <= 200.0)
    r = s_t[sel] / np.interp(E_t[sel], E_b, s_b)
    xcheck = {"method": "Thompson 1995 point / BEB total linearly interpolated at the same energy",
              "energy_window_eV": [20.0, 200.0], "n_points": int(sel.sum()),
              "ratio_min": round(float(r.min()), 4), "ratio_max": round(float(r.max()), 4)}
    note = ("DRAFT, unused by any campaign (fo_o_o2_chemistry_v0). e + O(3P) -> O+ + 2e. Cross section: {what}, via NIST "
            "SRD 107 (" + URL + ", raw sha256 " + RAW_SHA256[:12] + "..., not committed); sigma(13.618 eV) = 0 prepended; "
            "held above the last point. Header 13.618 eV = O ionization energy (Itikawa & Ichimura JPCRD 19, 637 (1990) "
            "Table 2.1). Maxwellian-integrated by abep_sim/rate_tables.py (docs/chemistry/o_o2/v0/build_tables_nist107_o.py). "
            "Energy column = mean electron energy 3/2 Te. Evidence level 4. Nominal choice BEB vs Thompson = owner decision.")
    return [
        {"file": "ionization_O_beb_kd2002.dat", "E_eV": E_b, "sigma_m2": s_b, "header_energy_eV": IE_O,
         "header_label": "Ionization energy", "tail": "hold",
         "source_text": note.format(what="Kim & Desclaux, Phys. Rev. A 66, 012708 (2002), BEB direct + "
                                         "excitation-autoionization total, O(3P)"),
         "meta": dict(COMMON, **{
             "role": "alternative A (theory)",
             "sources": [{"key": "KD2002", "citation": "Y.-K. Kim and J.-P. Desclaux, Phys. Rev. A 66, 012708 (2002)",
                          "doi": "10.1103/PhysRevA.66.012708", "access": "paper paywalled, not accessed; values via NIST SRD 107"}],
             "source_location": "NIST SRD 107 O table, column Total{kim02}",
             "stated_uncertainty": ("none stated in the NIST table; SONG2026 Sec. IV: recommended O cross sections expected "
                                    "accurate to at least 20 % where they matter"),
             "quantity_type": "model-derived (BEB + excitation-autoionization)",
             "transformation_chain": "KD2002 BEB -> NIST SRD 107 tabulation -> parsed -> Maxwellian integration",
             "cross_check_thompson1995": xcheck})},
        {"file": "ionization_O_thompson1995.dat", "E_eV": E_t, "sigma_m2": s_t, "header_energy_eV": IE_O,
         "header_label": "Ionization energy", "tail": "hold",
         "source_text": note.format(what="Thompson, Shah & Gilbody, J. Phys. B 28, 1321 (1995), measured points as "
                                         "tabulated by NIST (linear ramp 13.618 -> 14.1 eV assumed)"),
         "meta": dict(COMMON, **{
             "role": "alternative B (measurement recommended by SONG2026)",
             "sources": [{"key": "THOMPSON1995", "citation": "W. R. Thompson, M. B. Shah and H. B. Gilbody, J. Phys. B 28, 1321 (1995)",
                          "doi": "10.1088/0953-4075/28/7/023", "access": "paper paywalled, not accessed; points via NIST SRD 107"},
                         {"key": "SONG2026", "doi": "10.1063/5.0287254", "role": "recommendation (Sec. III.D)"}],
             "source_location": "NIST SRD 107 O table, column {thomp95}",
             "stated_uncertainty": "not read (paper paywalled); SONG2026 Sec. IV overall 'at least 20 %' statement",
             "quantity_type": "measured (as tabulated by NIST); threshold segment 13.618-14.1 eV assumed (linear ramp)",
             "transformation_chain": "Thompson 1995 measurement -> NIST SRD 107 tabulation -> parsed -> ramp -> Maxwellian integration",
             "verify": ["whether the {thomp95} column is sigma(O+) single ionization or the counting total"]})},
    ]


MANIFEST_HEADER = {
    "id": "o_o2_tables_nist107_o_v0",
    "lane": "fo_o_o2_chemistry_v0 (trigger T_PIVOT_O_O2_CHEMISTRY_V0, owner disposition od_hardware_pivot, W7)",
    "status": "DRAFT_FOR_OWNER_REVIEW",
    "builder": "docs/chemistry/o_o2/v0/build_tables_nist107_o.py",
    "integrator": "abep_sim/rate_tables.py (unchanged; read-only import)",
    "format": ("HallThruster.jl rate table as hallthruster_bridge/propellants/*.dat: header '<label> (eV): <E>', column "
               "header, then mean energy 0-300 eV step 1 and rate coefficient (m^3/s)"),
}


def main(argv):
    path = argv[argv.index("--from-file") + 1] if "--from-file" in argv else None
    raw = load_raw(path)
    return run(specs(raw), "manifest_nist107_o_v0.json", MANIFEST_HEADER, check="--check" in argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
