"""Build hallthruster_bridge/propellants/ionization_N.dat (e + N(4S) -> N+ + 2e) for HallThruster.jl.

Cross section: Kim & Desclaux, Phys. Rev. A 66, 012708 (2002), BEB total ionization cross section of ground-state
N(4S), as tabulated by NIST Standard Reference Database 107 ("Electron-Impact Cross Sections for Ionization and
Excitation", https://physics.nist.gov/ionxsec), fetched at build time. The NIST table itself is NOT committed (NIST SRD
copyright); only the Maxwellian-integrated rate table derived from it (abep_sim/rate_tables.py) is.

Cross-check (same NIST page): the Kim & Desclaux curve for a 30 % 2D / 70 % 4S beam agrees with the measurement of
Brook, Harrison & Smith, J. Phys. B 11, 3115 (1978), whose beam contained metastables. The script prints that comparison.
Note: a plain Kim-Rudd BEB evaluation with the NIST-listed orbital constants does NOT reproduce the NIST 4S values
(+6 % at 1 keV, larger near threshold); Kim & Desclaux's open-shell prescription is not re-implemented here, so the
tabulated values are used as published.
Usage: python scripts/build_n_ionization_table.py [--from-file saved_nist_ascii.txt]
"""
import os, re, sys, urllib.request
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from abep_sim.rate_tables import write_hallthruster_table   # noqa: E402

URL = "https://physics.nist.gov/cgi-bin/Ionization/merge.php?file=NI--&mode=ASCII"
OUT = os.path.join(os.path.dirname(__file__), "..", "hallthruster_bridge", "propellants", "ionization_N.dat")
THRESHOLD_EV = 14.534          # N(4S) ionization energy, 2p3/2 binding energy on the same NIST page (NIST ASD: 14.5341 eV)


def fetch(path=None):
    if path:
        raw = open(path, encoding="utf-8", errors="ignore").read()
    else:
        req = urllib.request.Request(URL, headers={"User-Agent": "abep-sim rate-table build (scripts/build_n_ionization_table.py)"})
        raw = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "ignore")
    lines = [re.sub(r"<[^>]+>", "", l) for l in raw.splitlines()]
    header = next(l for l in lines if l.startswith("T (eV)")).split("\t")
    col = {name: i for i, name in enumerate(header)}
    i4s = next(i for n, i in col.items() if n.startswith("Total (4S)"))
    imix = next(i for n, i in col.items() if n.startswith("Total From Mix"))
    ibrook = [i for n, i in col.items() if "brook78" in n]
    rows = [l.split("\t") for l in lines if l[:1].isdigit()]
    return rows, i4s, imix, ibrook


def main():
    path = sys.argv[sys.argv.index("--from-file") + 1] if "--from-file" in sys.argv else None
    rows, i4s, imix, ibrook = fetch(path)
    E, sig = [THRESHOLD_EV], [0.0]
    for r in rows:
        if len(r) > i4s and r[i4s].strip():
            e, s = float(r[0]), float(r[i4s]) * 1e-20          # NIST unit: 1e-16 cm^2 = 1e-20 m^2
            if e > THRESHOLD_EV:
                E.append(e); sig.append(s)
    E, sig = np.array(E), np.array(sig)
    print(f"N(4S) BEB: {len(E)} points, {E[1]:.2f}-{E[-1]:.0f} eV, max {sig.max():.3e} m^2 at {E[sig.argmax()]:.0f} eV")
    print("cross-check vs Brook et al. 1978 (metastable-containing beam) - Kim & Desclaux 30 % 2D mix:")
    for r in rows:
        meas = [r[i] for i in ibrook if len(r) > i and r[i].strip()]
        if meas and len(r) > imix and r[imix].strip():
            print(f"  {float(r[0]):7.1f} eV  mix {float(r[imix]):.3f}  Brook {', '.join(meas)}  (1e-16 cm^2)")
    src = ("e + N(4S) -> N+ + 2e. Cross section: Kim & Desclaux, Phys. Rev. A 66, 012708 (2002), BEB total, ground state "
           "4S, via NIST SRD 107 (" + URL + "). Maxwellian-integrated by abep_sim/rate_tables.py "
           "(scripts/build_n_ionization_table.py). Energy column = mean electron energy 3/2 Te.")
    write_hallthruster_table(OUT, E, sig, THRESHOLD_EV, source=src)
    print("wrote", os.path.normpath(OUT))


if __name__ == "__main__":
    main()
