"""B-H input data for the H-1 / MC-1 magnetostatic FE (lane L-H1-BZ, A9.38 P3).

Reads the two supplier data sheets already registered as H2-1 sources (h2_1_hall_chamber_magnet_v1.json /sources;
the sha256 of each PDF must equal the registered value, otherwise the script refuses):
  SRC-HIPERCO50  Carpenter Electrification, HIPERCO 50 data sheet (E200), p. 3 'DC PROPERTIES' table (text, typed values)
  SRC-ARMCO      AK Steel / Cleveland-Cliffs, ARMCO Pure Iron Product Data Bulletin (Oct 2022), Figs. 7, 8, 9 (vector paths)

The ARMCO curves are vector Bezier paths, so points are read from the PDF drawing commands (no raster digitising; the same
method as scripts/digitize_p5_bfield.py). Axes are calibrated from the drawn tick marks and their labels.
Output: docs/hardware/h1_bz/bh_curves_v1.json (raw extracted points + the composed FE curves, every number with its locator).

Usage: python digitize_bh_sources.py HIPERCO50.pdf ARMCO.pdf [--check]   (needs pymupdf; offline provenance tool)
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sys

import pymupdf as fitz

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "bh_curves_v1.json")
H21 = "docs/hardware/h2/h2_1_hall_chamber_magnet/h2_1_hall_chamber_magnet_v1.json"
SHA = {"SRC-HIPERCO50": "cdbe75cee6f446971f64279e45fbb7834ce056f913e96fba9691241769757f1d",
       "SRC-ARMCO": "b3306c48e295f80ad1c63e93854d495338682906665850121159a7e4e4c8a0e9"}
MU0 = 4e-7 * math.pi
NB = 24  # samples per Bezier segment


def sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def bezier(items):
    pts = []
    for it in items:
        if it[0] == "c":
            p0, p1, p2, p3 = it[1:5]
            for k in range(NB + (1 if it is items[-1] else 0)):
                t = k / NB
                a, b, c, d = (1 - t) ** 3, 3 * t * (1 - t) ** 2, 3 * t * t * (1 - t), t ** 3
                pts.append((a * p0.x + b * p1.x + c * p2.x + d * p3.x, a * p0.y + b * p1.y + c * p2.y + d * p3.y))
        elif it[0] == "l":
            p0, p1 = it[1:3]
            for k in range(NB + (1 if it is items[-1] else 0)):
                t = k / NB
                pts.append((p0.x + t * (p1.x - p0.x), p0.y + t * (p1.y - p0.y)))
    return pts


def hiperco(pdf):
    lay = fitz.open(pdf)[2].get_text("text", sort=True)
    flat = " ".join(lay.split())
    m = re.search(r"0\.014 IN \(0\.355 MM\) STRIP(.*?)0\.006 IN", flat)
    if not m:
        raise SystemExit("REFUSED: HIPERCO 50 p. 3 0.355 mm table not found")
    blk = m.group(1)
    H = [400.0, 800.0, 1600.0, 4000.0, 8000.0, 16000.0]
    if not all(f" {int(h)} " in f" {blk} " for h in H):
        raise SystemExit("REFUSED: HIPERCO 50 p. 3 H header (400..16000 A/m) not found")
    rows = {}
    for name in ("Typical magnetic anneal", "Typical mechanical anneal"):
        mm = re.search(re.escape(name) + r"\s+(\d+)\s+(\d+)\s+((?:\d\.\d\d\s+){5}\d\.\d\d)", blk)
        if not mm:
            raise SystemExit(f"REFUSED: HIPERCO 50 row '{name}' not found")
        rows[name] = {"coercivity_A_per_m": float(mm.group(1)), "mu_max": float(mm.group(2)),
                      "B_T": [float(x) for x in mm.group(3).split()]}
    return {"H_A_per_m": H, "rows": rows,
            "locator": "SRC-HIPERCO50 p. 3 'DC PROPERTIES', 0.014 in (0.355 mm) strip: coercivity from 8 kA/m, DC relative "
                       "permeability mu max, B (tesla) at 400/800/1600/4000/8000/16000 A/m"}


def ticks(dr, vertical):
    """short tick marks: vertical ticks (x-axis) or horizontal ticks (y-axis), width < 1 pt, one line item."""
    out = []
    for x in dr:
        if len(x["items"]) != 1 or x["items"][0][0] != "l" or (x.get("width") or 0) > 1.0:
            continue
        p, q = x["items"][0][1], x["items"][0][2]
        if vertical and abs(p.x - q.x) < 0.01 and abs(p.y - q.y) > 1:
            out.append((p.x, abs(p.y - q.y)))
        if not vertical and abs(p.y - q.y) < 0.01 and abs(p.x - q.x) > 1:
            out.append((p.y, abs(p.x - q.x)))
    return out


def armco(pdf):
    doc = fitz.open(pdf)
    res = {}
    # Fig. 7 (pdf page index 7): log10 H (decades 1..10000 A/m) vs B (0..2.0 T, step 0.2)
    p = doc[7]
    dr = p.get_drawings()
    curve = [x for x in dr if len(x["items"]) == 6 and x["items"][0][0] == "c"]
    if len(curve) != 1:
        raise SystemExit("REFUSED: ARMCO Fig. 7 curve not unique")
    xt = sorted(t[0] for t in ticks(dr, True))
    yt = sorted(t[0] for t in ticks(dr, False))
    if len(xt) != 5 or len(yt) != 11:
        raise SystemExit(f"REFUSED: ARMCO Fig. 7 ticks {len(xt)} x / {len(yt)} y (expected 5 / 11)")
    dec = (xt[-1] - xt[0]) / 4.0
    X7 = lambda u: 10 ** ((u - xt[0]) / dec)                    # 1 A/m at the first tick
    Y7 = lambda v: (yt[-1] - v) / (yt[-1] - yt[0]) * 2.0       # 0.0 T at the lowest tick (largest y)
    f7 = [(X7(u), Y7(v)) for u, v in bezier(curve[0]["items"])]
    res["fig7"] = {"points_H_B": f7, "calibration": {"x_ticks_pt": xt, "y_ticks_pt": yt, "decade_pt": dec},
                   "locator": "SRC-ARMCO PDF p. 8 (printed p. 6) Fig. 7 'Representative low and medium induction values for "
                              "annealed ARMCO Pure Iron' (after recrystallization anneal); vector path, log H axis 1..10 000 "
                              "A/m, B axis 0..2.0 T"}
    # Fig. 8 (index 8): log10 H (500, 5000, 50 000, 500 000 A/m) vs intrinsic B_i = B - mu0 H (1.50..2.20 T, step 0.1)
    p = doc[8]
    dr = p.get_drawings()
    curve = [x for x in dr if len(x["items"]) == 6 and x["items"][0][0] == "c"]
    if len(curve) != 1:
        raise SystemExit("REFUSED: ARMCO Fig. 8 curve not unique")
    xt = sorted(t[0] for t in ticks(dr, True))
    yt = sorted(t[0] for t in ticks(dr, False))
    if len(xt) != 4 or len(yt) != 8:
        raise SystemExit(f"REFUSED: ARMCO Fig. 8 ticks {len(xt)} x / {len(yt)} y (expected 4 / 8)")
    dec = (xt[-1] - xt[0]) / 3.0
    X8 = lambda u: 500.0 * 10 ** ((u - xt[0]) / dec)
    Y8 = lambda v: 1.50 + (yt[-1] - v) / (yt[-1] - yt[0]) * 0.70
    f8 = [(X8(u), Y8(v)) for u, v in bezier(curve[0]["items"])]
    res["fig8"] = {"points_H_Bi": f8, "calibration": {"x_ticks_pt": xt, "y_ticks_pt": yt, "decade_pt": dec},
                   "locator": "SRC-ARMCO PDF p. 9 (printed p. 7) Fig. 8 'High induction magnetization curve for ARMCO Pure "
                              "Iron' (intrinsic flux density B - mu0 H); vector path, log H axis 500..500 000 A/m, B_i axis "
                              "1.50..2.20 T"}
    # Fig. 9 (index 9): log10 H (10 .. 10 000 A/m; major ticks are the long ones) vs log10 mu_r (100 .. 10 000)
    p = doc[9]
    dr = p.get_drawings()
    strokes = [x for x in dr if x["type"] == "s" and len(x["items"]) == 10]
    if len(strokes) != 2:
        raise SystemExit("REFUSED: ARMCO Fig. 9 envelope strokes not found (expected 2)")
    vt = ticks(dr, True)
    ht = ticks(dr, False)
    xmaj = sorted(t[0] for t in vt if t[1] > 7.0)
    ymaj = sorted(t[0] for t in ht if t[1] > 7.0)
    yminlen = sorted(t[0] for t in ht if t[1] <= 7.0)
    if len(xmaj) != 4:
        raise SystemExit(f"REFUSED: ARMCO Fig. 9 major x ticks {len(xmaj)} (expected 4: 10, 100, 1000, 10 000)")
    # y: the two long ticks are 10 000 (top) and 1000; 100 sits at the axis line (bottom tick row) - read from labels
    words = p.get_text("words")
    ylab = {}
    for w in words:
        if w[4] in ("1000", "100") and w[2] < 90:
            ylab[w[4]] = (w[1] + w[3]) / 2
        if w[4] == "000" and w[2] < 90 and w[0] > 60:
            ylab["10000"] = (w[1] + w[3]) / 2
    for k in ("100", "1000", "10000"):
        if k not in ylab:
            raise SystemExit(f"REFUSED: ARMCO Fig. 9 y label {k} not found")
    # snap the label centres to the nearest drawn horizontal tick
    allh = sorted(t[0] for t in ht)
    snap = {k: min(allh, key=lambda y: abs(y - v)) for k, v in ylab.items() if k != "100"}
    ydec = snap["1000"] - snap["10000"]
    y100 = snap["1000"] + ydec
    dec = (xmaj[-1] - xmaj[0]) / 3.0
    X9 = lambda u: 10.0 * 10 ** ((u - xmaj[0]) / dec)
    M9 = lambda v: 100.0 * 10 ** ((y100 - v) / ydec)
    env = []
    for s in strokes:
        pts = [(X9(u), M9(v)) for u, v in bezier(s["items"])]
        env.append(pts)
    # lower envelope = the stroke with the lower peak mu_r
    env.sort(key=lambda pts: max(m for _, m in pts))
    res["fig9"] = {"lower_envelope_H_mur": env[0], "upper_envelope_H_mur": env[1],
                   "calibration": {"x_major_ticks_pt": xmaj, "y_tick_snap_pt": snap, "y100_pt": y100, "x_decade_pt": dec,
                                   "y_decade_pt": ydec, "y_minor_ticks_n": len(yminlen)},
                   "locator": "SRC-ARMCO PDF p. 10 (printed p. 8) Fig. 9 'Relative permeability of ARMCO Pure Iron over a "
                              "range of magnetizing field strength': the two drawn boundary strokes of the shaded bands "
                              "(lower = lower edge of the SRA / recrystallization-anneal range, 700-900 C; upper = upper "
                              "edge of the normalization-anneal range, >= 927 C); log H 10..10 000 A/m, log mu_r 100..10 000"}
    return res


def monotone(pts):
    """sort by H and keep a strictly increasing (H, B) sequence."""
    pts = sorted(pts)
    out = []
    for h, b in pts:
        if h <= 0:
            continue
        if not out or (h > out[-1][0] * (1 + 1e-9) and b > out[-1][1] + 1e-9):
            out.append((h, b))
    return out


def compose(hip, arm):
    """FE B-H curves (normal induction B vs H). Composition rules are declared in the output, not hidden."""
    H = hip["H_A_per_m"]
    mag = hip["rows"]["Typical magnetic anneal"]
    mech = hip["rows"]["Typical mechanical anneal"]
    sat_ext = "above the last tabulated point B = B_last + mu0 (H - H_last) (saturated slope; FE-solver extrapolation rule)"
    hc = {
        "HC-NOM": {"points": [(0.0, 0.0)] + list(zip(H, mag["B_T"])),
                   "rule": "magnetic-anneal 0.355 mm row; 0 -> 400 A/m by the secant from the origin (relative permeability "
                           "2.10 / (mu0 400) = %.0f < mu_max %.0f, i.e. LOWER than the real knee: conservative)"
                           % (mag["B_T"][0] / (MU0 * 400.0), mag["mu_max"])},
        "HC-LO": {"points": [(0.0, 0.0)] + list(zip(H, mech["B_T"])),
                  "rule": "mechanical-anneal 0.355 mm row (lower curve); 0 -> 400 A/m by the secant"},
        "HC-HI": {"points": [(0.0, 0.0), (2.0 / (MU0 * mag["mu_max"]), 2.0)] + list(zip(H, mag["B_T"])),
                  "rule": "magnetic-anneal row with the low-field segment at the sourced mu_max (%.0f) up to 2.0 T, then the "
                          "table: B / (mu0 H) <= mu_max everywhere (upper permeability bound)" % mag["mu_max"]},
    }
    # ARMCO: Fig. 7 (normal B) for low / medium H; Fig. 8 (intrinsic) -> normal B = B_i + mu0 H for high H
    f7 = monotone(arm["fig7"]["points_H_B"])
    f8 = monotone([(h, bi + MU0 * h) for h, bi in arm["fig8"]["points_H_Bi"]])
    lo = monotone([(h, MU0 * m * h) for h, m in arm["fig9"]["lower_envelope_H_mur"]])
    hi = monotone([(h, MU0 * m * h) for h, m in arm["fig9"]["upper_envelope_H_mur"]])

    def interp(c, h):
        for (h0, b0), (h1, b1) in zip(c, c[1:]):
            if h0 <= h <= h1:
                return b0 + (b1 - b0) * (math.log(h) - math.log(h0)) / (math.log(h1) - math.log(h0))
        return None

    overlap = []
    for h in (1000.0, 2000.0, 5000.0, 10000.0, 15000.0):
        b7, b8 = interp(f7, h), interp(f8, h)
        if b7 is not None and b8 is not None:
            overlap.append({"H_A_per_m": h, "B_fig7_T": b7, "B_fig8_T": b8, "diff_T": b7 - b8})

    def join(low, label):
        """low/medium curve up to its last point, then Fig. 8 beyond it (only Fig. 8 points with larger H AND B)."""
        hj, bj = low[-1]
        tail = [(h, b) for h, b in f8 if h > hj * 1.0001 and b > bj + 1e-6]
        return {"points": [(0.0, 0.0)] + low + tail,
                "rule": f"{label} up to H = {hj:.4g} A/m (B = {bj:.4g} T), then Fig. 8 (B = B_i + mu0 H) for larger H "
                        "where it lies above; 0 -> first digitized point by the secant from the origin"}

    fe = {"FE-NOM": join(f7, "Fig. 7 representative curve"),
          "FE-LO": join(lo, "Fig. 9 lower envelope (SRA band lower edge), B = mu0 mu_r H"),
          "FE-HI": join(hi, "Fig. 9 upper envelope (normalization band upper edge), B = mu0 mu_r H")}
    sets = {"BH-NOM": {"hiperco": "HC-NOM", "iron": "FE-NOM"},
            "BH-LO": {"hiperco": "HC-LO", "iron": "FE-LO"},
            "BH-HI": {"hiperco": "HC-HI", "iron": "FE-HI"}}
    for d in list(hc.values()) + list(fe.values()):
        d["points"] = [[float(f"{h:.6g}"), float(f"{b:.6g}")] for h, b in d["points"]]
        d["extrapolation"] = sat_ext
    return hc, fe, sets, overlap


def build(hip_pdf, arm_pdf):
    for key, path in (("SRC-HIPERCO50", hip_pdf), ("SRC-ARMCO", arm_pdf)):
        if sha256(path) != SHA[key]:
            raise SystemExit(f"REFUSED: {key} sha256 {sha256(path)} != registered {SHA[key]} ({H21} /sources)")
    hip = hiperco(hip_pdf)
    arm = armco(arm_pdf)
    hc, fe, sets, overlap = compose(hip, arm)
    rnd = lambda pts: [[float(f"{a:.6g}"), float(f"{b:.6g}")] for a, b in pts]
    return {
        "schema": "abep_h1_bz_bh_curves_v1",
        "id": "h1_bz_bh_curves_v1",
        "lane": "L-H1-BZ (A9.38 P3)",
        "generated_by": "docs/hardware/h1_bz/digitize_bh_sources.py",
        "sources": {"SRC-HIPERCO50": {"registered_in": H21 + " /sources/SRC-HIPERCO50", "pdf_sha256": SHA["SRC-HIPERCO50"]},
                    "SRC-ARMCO": {"registered_in": H21 + " /sources/SRC-ARMCO", "pdf_sha256": SHA["SRC-ARMCO"]}},
        "evidence_class": {"hiperco": "measured (supplier-typical, strip specimens; typed table values)",
                           "armco": "digitized (supplier-typical curves; PDF vector paths, no raster digitising)"},
        "applicability": [
            "room-temperature DC normal magnetization curves; no temperature dependence (H1F-MA-03 / MA-04 hot-use limits "
            "TBD): the hot-pole B-H is NOT covered",
            "anhysteretic use of the normal curve; coercivity (Hiperco 45-125 A/m) and remanence are neglected",
            "strip (Hiperco) / bulletin-representative (ARMCO) specimens; machined bulk parts after the specified anneal "
            "are assumed to lie inside the LO..HI bracket (assumed; verify on the procured lot, HW-MC-13)",
        ],
        "raw": {"hiperco50_p3": hip,
                "armco_fig7": {"points_H_B": rnd(arm["fig7"]["points_H_B"]), "calibration": arm["fig7"]["calibration"],
                               "locator": arm["fig7"]["locator"]},
                "armco_fig8": {"points_H_Bi": rnd(arm["fig8"]["points_H_Bi"]), "calibration": arm["fig8"]["calibration"],
                               "locator": arm["fig8"]["locator"]},
                "armco_fig9": {"lower_envelope_H_mur": rnd(arm["fig9"]["lower_envelope_H_mur"]),
                               "upper_envelope_H_mur": rnd(arm["fig9"]["upper_envelope_H_mur"]),
                               "calibration": arm["fig9"]["calibration"], "locator": arm["fig9"]["locator"]}},
        "fig7_fig8_overlap_check": overlap,
        "curves": {"hiperco": hc, "iron": fe},
        "sets": sets,
        "set_roles": {"BH-NOM": "nominal", "BH-LO": "lower permeability bound (uncertainty envelope)",
                      "BH-HI": "upper permeability bound (uncertainty envelope)"},
    }


def dump(obj):
    return json.dumps(obj, indent=1, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 2:
        raise SystemExit(__doc__)
    text = dump(build(*args))
    if "--check" in sys.argv:
        with open(OUT, encoding="utf-8") as f:
            ok = f.read() == text
        print("OK" if ok else "DIFFERS")
        sys.exit(0 if ok else 1)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(text)
    print(OUT, hashlib.sha256(text.encode()).hexdigest())
