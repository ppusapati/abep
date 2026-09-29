#!/usr/bin/env python3
"""Vector extraction of the LCC discharge-supply efficiency plots (Rhodes, Benavides, Pinero, IEPC-2024-331, slide 11).

Source (openly accessible, NASA NTRS 20240006846, accessed 2026-09-26):
  https://ntrs.nasa.gov/api/citations/20240006846/downloads/Rhodes%20-%20IEPC%202024%20Presentation_v2.pdf
The slides are NOT redistributed. This script refuses any PDF whose sha256 differs from the accessed file.

Method (deterministic, no raster step):
  * page 11 (index 10) carries two vector scatter plots: "Efficiency at 250 V Output" (left) and
    "Efficiency at 400 V Output" (right), three series each (25 / 28 / 34 Vin, told apart by marker fill colour as in
    the in-plot legend: blue = 25 Vin, orange = 28 Vin, green = 34 Vin; legend order matched by the legend text rows);
  * marker centre = centre of the marker path's bounding box; legend markers (inside the white legend box) are dropped;
  * axis calibration = least-squares line through the light-grey grid lines and the axis lines, each paired with the
    tick label whose text centre is nearest to it; the calibration residual is reported;
  * output: CSV (plot, V_in_V, V_out_V, P_out_W, efficiency_pct), sorted, fixed decimals.

Quantity type: measured (by the source) -> graphically published (vector) -> vector-extracted (this script).
Usage:  python digitize_rhodes2024_slide11.py --pdf <slides.pdf> [--out <csv>]
Needs PyMuPDF (tested with 1.28.2).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from pathlib import Path

EXPECTED_SHA256 = "9f5a6c7bb36ac2ffc45026e004150304a592dadb1419284917341623588e21d9"
PAGE_INDEX = 10
# marker fill colours (rounded to 2 decimals) -> input bus voltage, per plot (legend rows: 25, 28, 34 Vin)
SERIES = {
    "left": {(0.31, 0.51, 0.74): 25, (0.93, 0.49, 0.19): 28, (0.0, 0.69, 0.31): 34},
    "right": {(0.27, 0.45, 0.77): 25, (0.93, 0.49, 0.19): 28, (0.0, 0.69, 0.31): 34},
}
V_OUT = {"left": 250, "right": 400}
GRID_GREY = (0.85, 0.85, 0.85)
AXIS_GREY = (0.75, 0.75, 0.75)
DEFAULT_OUT = Path(__file__).resolve().parent.parent / "sources" / "rhodes2024_slide11_discharge_efficiency.csv"


def _rgb(c):
    return tuple(round(float(x), 2) for x in (c or ()))


def _fit(pairs):
    """least-squares value = a + b*coord; returns (a, b, max |residual| in value units)."""
    n = len(pairs)
    sx = sum(p for p, _ in pairs); sy = sum(v for _, v in pairs)
    sxx = sum(p * p for p, _ in pairs); sxy = sum(p * v for p, v in pairs)
    b = (n * sxy - sx * sy) / (n * sxx - sx * sx)
    a = (sy - b * sx) / n
    res = max(abs(a + b * p - v) for p, v in pairs)
    return a, b, res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args(argv)
    data = Path(args.pdf).read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    if sha != EXPECTED_SHA256:
        print(f"refused: sha256 {sha} is not the accessed file {EXPECTED_SHA256}", file=sys.stderr)
        return 2
    import pymupdf  # noqa: PLC0415  (only needed when actually digitizing)

    page = pymupdf.open(stream=data, filetype="pdf")[PAGE_INDEX]
    words = page.get_text("words")
    drawings = page.get_drawings()

    # plot frames from the axis lines (x-axis: horizontal, y-axis: vertical, both AXIS_GREY)
    vlines, hlines = [], []
    for d in drawings:
        if d["type"] != "s":
            continue
        col = _rgb(d.get("color"))
        for it in d["items"]:
            if it[0] != "l":
                continue
            p, q = it[1], it[2]
            if abs(p.x - q.x) < 1e-6:
                vlines.append((col, p.x, min(p.y, q.y), max(p.y, q.y)))
            elif abs(p.y - q.y) < 1e-6:
                hlines.append((col, p.y, min(p.x, q.x), max(p.x, q.x)))
    y_axes = sorted([v for v in vlines if v[0] == AXIS_GREY], key=lambda v: v[1])
    x_axes = sorted([h for h in hlines if h[0] == AXIS_GREY], key=lambda h: h[2])
    if len(y_axes) != 2 or len(x_axes) != 2:
        print("refused: unexpected axis structure", file=sys.stderr)
        return 3
    rows, report = [], []
    for side, yax, xax in (("left", y_axes[0], x_axes[0]), ("right", y_axes[1], x_axes[1])):
        x0, x1 = xax[2], xax[3]
        y_top, y_bot = yax[2], yax[3]
        grid_h = sorted({round(h[1], 4) for h in hlines if h[0] == GRID_GREY and abs(h[2] - x0) < 0.5} | {round(xax[1], 4)})
        grid_v = sorted({round(v[1], 4) for v in vlines if v[0] == GRID_GREY and abs(v[3] - y_bot) < 0.5} | {round(yax[1], 4)})

        def num(w):
            try:
                return float(w[4])
            except ValueError:
                return None
        ylab = [((w[1] + w[3]) / 2, num(w)) for w in words if num(w) is not None and w[2] <= x0 + 1 and w[2] > x0 - 40]
        xlab = [((w[0] + w[2]) / 2, num(w)) for w in words if num(w) is not None and w[1] >= y_bot and w[1] < y_bot + 20
                and x0 - 20 <= (w[0] + w[2]) / 2 <= x1 + 20]
        ypairs = [(g, min(ylab, key=lambda t: abs(t[0] - g))[1]) for g in grid_h]
        xpairs = [(g, min(xlab, key=lambda t: abs(t[0] - g))[1]) for g in grid_v]
        ay, by, ry = _fit(ypairs)
        ax_, bx, rx = _fit(xpairs)
        report.append(f"{side}: y-grid {len(ypairs)} lines, max residual {ry:.4f} %-pt; x-grid {len(xpairs)} lines, max residual {rx:.3f} W")
        legend = [d["rect"] for d in drawings if d["type"] in ("f", "fs") and _rgb(d.get("fill")) == (1.0, 1.0, 1.0)
                  and x0 < d["rect"].x0 < x1 and y_top < d["rect"].y0 < y_bot]
        for d in drawings:
            if d["type"] not in ("f", "fs"):
                continue
            fill = _rgb(d.get("fill"))
            if fill not in SERIES[side]:
                continue
            r = d["rect"]
            if r.width > 8 or r.height > 8:
                continue
            cx, cy = (r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2
            if not (x0 - 3 <= cx <= x1 + 3 and y_top - 3 <= cy <= y_bot + 3):
                continue
            if any(L.x0 <= cx <= L.x1 and L.y0 <= cy <= L.y1 for L in legend):
                continue
            rows.append((side, SERIES[side][fill], V_OUT[side], ax_ + bx * cx, ay + by * cy))
    rows.sort(key=lambda t: (t[2], t[1], t[3]))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["plot", "V_in_V", "V_out_V", "P_out_W", "efficiency_pct"])
        for side, vin, vout, p, e in rows:
            w.writerow([side, vin, vout, f"{p:.1f}", f"{e:.2f}"])
    for line in report:
        print(line)
    print(f"{len(rows)} points -> {out}")
    return 0 if len(rows) == 54 else 4


if __name__ == "__main__":
    sys.exit(main())
