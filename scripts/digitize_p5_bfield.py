"""Extract the P5 vacuum radial-field profiles from the vector figures of Peterson, Gallimore & Haas, AIAA 2001-3890
(https://pepl.engin.umich.edu/pdf/AIAA-2001-3890_Bdot.pdf), Figs. 11 (1.6 kW coils, I_in=2 A, I_out=1 A) and 12
(3.0 kW coils, I_in=3 A, I_out=2 A). The plots are vector graphics, so points are read from the PDF drawing commands
(no raster digitising). Axes are calibrated from the tick labels; check: the drawn pole mid-plane and exit-plane lines
read 25.4 mm and 38.0 mm. Output: NIST-traceable Hall-probe trace (red dashed), channel centreline (R=12.7 mm).
Usage: python scripts/digitize_p5_bfield.py AIAA-2001-3890_Bdot.pdf   (needs pymupdf; offline provenance tool)
"""
import sys, os
import numpy as np
import pymupdf as fitz

PANELS = {"1p6kW": 1, "3p0kW": 4}           # index of the centre-line panel among the six B-dot curves on page 8
OUT = os.path.join(os.path.dirname(__file__), "..", "hallthruster_bridge", "bfield")


def extract(pdf):
    p = fitz.open(pdf)[7]
    dr, words = p.get_drawings(), p.get_text("words")
    blue = [x for x in dr if x.get("color") == (0.0, 0.0, 1.0) and len(x["items"]) > 100]
    res = {}
    for name, i in PANELS.items():
        br = blue[i]["rect"]
        r100 = min((w for w in words if w[4] == "100" and w[1] > br.y1 - 5 and w[0] > br.x1 - 40), key=lambda w: w[1])
        xl = [w for w in words if abs(w[1] - r100[1]) < 1.5 and w[4] == "0" and br.x0 - 40 < w[0] < br.x1 + 40]
        x0, x100 = (xl[0][0] + xl[0][2]) / 2, (r100[0] + r100[2]) / 2
        yl = [w for w in words if w[4] in ("0", "200") and w[2] < x0 and x0 - 25 < w[0] and br.y0 - 60 < w[1] < br.y1 + 20]
        y0 = [(w[1] + w[3]) / 2 for w in yl if w[4] == "0"][-1]
        y200 = [(w[1] + w[3]) / 2 for w in yl if w[4] == "200"][0]
        X = lambda u: (u - x0) / (x100 - x0) * 100
        Y = lambda v: (v - y0) / (y200 - y0) * 200
        frame = fitz.Rect(x0 - 2, y200 - 0.12 * (y0 - y200), x100 + 2, y0 + 2)
        legend = [fitz.Rect(w[0] - 30, w[1] - 1, w[0], w[3] + 1) for w in words
                  if w[4] in ("Vacuum", "Hall") and frame.contains(fitz.Point(w[0], w[1]))]
        pts = set()
        for x in dr:
            mid = fitz.Point((x["rect"].x0 + x["rect"].x1) / 2, (x["rect"].y0 + x["rect"].y1) / 2)
            if x.get("color") == (1.0, 0.0, 0.0) and frame.contains(mid) and not any(mid in L for L in legend):
                for it in x["items"]:
                    if it[0] == "l":
                        pts |= {(round(X(q.x), 2), round(Y(q.y), 2)) for q in (it[1], it[2])}
        a = np.array(sorted(pts))
        _, keep = np.unique(a[:, 0], return_index=True)     # dash end/start points coincide
        res[name] = a[keep]
    return res


if __name__ == "__main__":
    for name, a in extract(sys.argv[1]).items():
        path = os.path.join(OUT, f"p5_vacuum_Br_centerline_{name}.csv")
        with open(path, "w") as f:
            f.write("# P5 vacuum radial magnetic field, channel centreline (R=12.7 mm), NIST-traceable Hall probe.\n"
                    "# Source: Peterson, Gallimore & Haas, AIAA 2001-3890, Fig. %s (%s coil setting), extracted from the\n"
                    "# PDF vector paths by scripts/digitize_p5_bfield.py. z from anode face (exit plane at 38.0 mm in\n"
                    "# this figure). Unscaled; the driver shifts/scales it (see cases/*.json 'B_profile').\n"
                    "z_from_anode_face_mm,Br_G\n" % ("11" if name == "1p6kW" else "12",
                                                     "1.6 kW, I_in=2 A, I_out=1 A" if name == "1p6kW" else "3.0 kW, I_in=3 A, I_out=2 A"))
            for z, b in a:
                f.write(f"{z:.2f},{b:.2f}\n")
        print(path, len(a), "points; max %.1f G at %.1f mm" % (a[:, 1].max(), a[a[:, 1].argmax(), 0]))
