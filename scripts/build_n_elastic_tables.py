"""Build the atomic-N elastic momentum-transfer tables (reaction set abep-n2n-0.8):
  elastic_N_ragimkhanov2026.dat          nominal  (n2_n.toml)
  elastic_N_wang2014_bsr.dat             variant  (n2_n_nel_wang.toml, generated)

Source: Ragimkhanov, Shorifuddoza, Khalikova, Shahmohammadi Beni, Haque, Watabe, Patoary, Haque & Uddin, "Scattering of
electron and positron by atomic nitrogen and its application in transport characteristics", Eur. Phys. J. D 80, 69 (2026),
doi:10.1140/epjd/s10053-026-01166-3, CC BY 4.0. Fig. 1b plots the electron momentum-transfer cross section (MTCS, in a0^2,
log-log, 1 eV - 1 MeV): the present OPM calculation (Dirac partial waves, complex optical potential; solid red) and, among
the comparison curves, Wang et al. (B-spline R-matrix) 2014 (green dashed; 0.95-128 eV). The paper gives these data
"in graphical form" only (its data statement). Both curves are VECTOR paths in the PDF: this script extracts the path
coordinates (no raster digitization) and calibrates them on the plot frame, whose edges are the 10^0 / 10^6 eV and
10^-7 / 10^2 a0^2 ticks (tick labels centre within 0.03 pt of the frame-derived positions: 0.1 % in E, 0.5 % in sigma).
The extracted points are committed in hallthruster_bridge/propellants/sources/ragimkhanov2026_fig1b_mtcs.csv (CC BY 4.0,
attribution above); re-extract with --pdf <file> (PDF sha256
47489e8a91da2f6563d582f791897b2391fed47ada9aa2704b25031295042f5a).

Evidence: level 4. OPM: model-derived (theory) + vector-extracted from a published figure. Wang BSR: model-derived (theory)
as re-plotted by Ragimkhanov et al., i.e. a SECONDARY reproduction of Wang et al. 2014 (the primary PRA paper is not open);
its fidelity to Wang's own numbers is unverified.
Why two tables: the curves disagree materially in the Hall-relevant 5-50 eV range (OPM/Wang = 0.52 at 5 eV, 0.59 at 10 eV,
~1.0 at 23 eV, 1.17 at 30-60 eV) and by up to 7x below 3 eV (BSR resolves the low-energy N- resonance structure; the
optical-potential model does not aim to). Owner rule: carry the disagreement as chemistry uncertainty, do not select.
Wang variant above 128 eV: spliced to OPM (the Wang curve ends there); at T_e = 30 eV about 7 % of the Maxwellian flux is
above 128 eV, so the variant is 'Wang below 128 eV, OPM above'.
Both: sigma = 0 below the first extracted point (~1 eV) - no low-energy extrapolation (the guard checks the upper limit
only; this truncation lowers the momentum-transfer rate at T_e < ~1 eV, outside the Hall domain).
Usage: python scripts/build_n_elastic_tables.py [--pdf ragimkhanov2026.pdf]
"""
import csv, os, sys
import numpy as np

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)
from abep_sim.rate_tables import maxwellian_rate, tail_sensitivity, write_hallthruster_table   # noqa: E402

PROP = os.path.join(ROOT, "hallthruster_bridge", "propellants")
CSV = os.path.join(PROP, "sources", "ragimkhanov2026_fig1b_mtcs.csv")
A0SQ = (5.29177210903e-11) ** 2                        # a0^2 in m^2 (CODATA 2018)
FRAME = dict(x0=313.93, x1=465.08, y_bottom=198.84, y_top=69.02, logE=(0.0, 6.0), logS=(-7.0, 2.0))
FILES = {"opm": "elastic_N_ragimkhanov2026.dat", "wang": "elastic_N_wang2014_bsr.dat"}
TAIL = "hold"


def extract(pdf):
    """Vector paths of Fig. 1b (page 2): red solid = OPM, green line segments inside the plot (not the legend) = Wang BSR."""
    import pymupdf
    page = pymupdf.open(pdf)[1]
    f = FRAME

    def conv(x, y):
        lE = f["logE"][0] + (f["logE"][1] - f["logE"][0]) * (x - f["x0"]) / (f["x1"] - f["x0"])
        lS = f["logS"][0] + (f["logS"][1] - f["logS"][0]) * (f["y_bottom"] - y) / (f["y_bottom"] - f["y_top"])
        return 10 ** lE, 10 ** lS

    out = {"opm": set(), "wang": set()}
    for d in page.get_drawings():
        c = tuple(round(v, 2) for v in d["color"]) if d.get("color") else None
        r = d["rect"]
        if not (f["x0"] - 1 <= r.x0 and r.x1 <= f["x1"] + 1 and f["y_top"] - 1 <= r.y0 and r.y1 <= f["y_bottom"] + 1):
            continue
        key = "opm" if (c == (1.0, 0.0, 0.0) and len(d["items"]) > 100) else "wang" if (c == (0.0, 1.0, 0.0) and r.y0 < 165) else None
        if key is None:
            continue
        for it in d["items"]:
            if it[0] == "l":
                for pnt in (it[1], it[2]):
                    out[key].add(conv(round(pnt.x, 4), round(pnt.y, 4)))
    rows = [(k, e, s) for k in ("opm", "wang") for e, s in sorted(out[k])]
    os.makedirs(os.path.dirname(CSV), exist_ok=True)
    with open(CSV, "w", newline="") as fh:
        fh.write("# Ragimkhanov et al., Eur. Phys. J. D 80, 69 (2026), CC BY 4.0, Fig. 1b electron MTCS, vector-path extraction "
                 "(scripts/build_n_elastic_tables.py). curve: opm = present OPM calculation; wang = Wang et al. 2014 BSR as "
                 "re-plotted in that figure. E in eV, sigma in a0^2.\n")
        w = csv.writer(fh); w.writerow(["curve", "E_eV", "sigma_a0sq"])
        for k, e, s in rows:
            w.writerow([k, f"{e:.6g}", f"{s:.6g}"])
    return rows


def load():
    rows = [r for r in csv.reader(open(CSV)) if r and not r[0].startswith("#") and r[0] != "curve"]
    data = {}
    for k, e, s in rows:
        data.setdefault(k, []).append((float(e), float(s)))
    # duplicate abscissae (vertical path steps) are averaged so the curve is single-valued
    for k, pts in data.items():
        E = np.array([p[0] for p in pts]); S = np.array([p[1] for p in pts])
        u = np.unique(E)
        data[k] = (u, np.array([S[E == x].mean() for x in u]))
    return data


def cross_section(variant):
    d = load()
    Eo, So = d["opm"]
    if variant == "opm":
        return Eo, So * A0SQ
    Ew, Sw = d["wang"]
    above = Eo > Ew.max()
    return np.concatenate([Ew, Eo[above]]), np.concatenate([Sw, So[above]]) * A0SQ


def main():
    if "--pdf" in sys.argv:
        rows = extract(sys.argv[sys.argv.index("--pdf") + 1])
        print(f"extracted {sum(r[0] == 'opm' for r in rows)} OPM and {sum(r[0] == 'wang' for r in rows)} Wang points -> {CSV}")
    for v, f in FILES.items():
        E, s = cross_section(v)
        sens = tail_sensitivity(E, s, [45, 150, 255])
        ratio = [(T, maxwellian_rate(*cross_section("opm"), T, TAIL) / maxwellian_rate(*cross_section("wang"), T, TAIL))
                 for T in (2, 5, 10, 20, 30)]
        src = (f"e + N elastic momentum transfer ({v}). Ragimkhanov et al., Eur. Phys. J. D 80, 69 (2026) (CC BY 4.0), Fig. 1b "
               + ("present OPM curve" if v == "opm" else "Wang et al. 2014 B-spline R-matrix curve as re-plotted there (secondary), "
                  "spliced to the OPM curve above its last point (128 eV)")
               + f", vector-path extraction; {E[0]:.3g}-{E[-1]:.3g} eV, sigma = 0 below; held above (tail share "
               + ", ".join(f"{100 * dd:.4f} % at {e:.0f} eV" for e, dd in sens) + "). Rate ratio OPM/Wang-variant: "
               + ", ".join(f"T_e {T} eV {r:.2f}" for T, r in ratio)
               + ". Maxwellian-integrated by abep_sim/rate_tables.py (scripts/build_n_elastic_tables.py). Reaction set abep-n2n-0.8.")
        write_hallthruster_table(os.path.join(PROP, f), E, s, 0.0, source=src, tail=TAIL,
                                 header_label="Momentum transfer, no inelastic energy loss")
        print(f"wrote {f}: {len(E)} points {E[0]:.3g}-{E[-1]:.3g} eV; OPM/Wang rate ratio " + ", ".join(f"{T}:{r:.2f}" for T, r in ratio))


if __name__ == "__main__":
    main()
