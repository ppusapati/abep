"""Vector-extract the discharge-supply efficiency curves from Rhodes, Benavides & Pinero, IEPC 2024 slides (slide 11).

Source (openly accessible, NASA NTRS 20240006846, accessed 2026-09-26):
  C. R. Rhodes, G. F. Benavides, L. R. Pinero, "Sub-kW Class Hall-Effect Thruster Power Processing Unit for Wide Output
  Range Applications", 38th IEPC, Toulouse, June 2024 -- presentation slides
  https://ntrs.nasa.gov/api/citations/20240006846/downloads/Rhodes%20-%20IEPC%202024%20Presentation_v2.pdf
  Slide 11, "LCC Discharge Power Supply Bench Testing": two vector charts, "Efficiency at 250 V Output" and
  "Efficiency at 400 V Output", efficiency [%] vs output power [W], series 25 / 28 / 34 Vin.

Transformation chain (docs/EVIDENCE.md): bench measurement by the authors -> plotted as a vector chart in the slides ->
this script reads the marker centres from the PDF drawing list and maps them to data coordinates with a least-squares
linear calibration of each axis against its own gridlines/axis line and tick labels. No smoothing, no interpolation, no
rounding beyond the CSV's printed precision. The script refuses any PDF whose sha256 differs from the pinned one.

Evidence class of the output: measured (by the source) -> digitized (vector-extracted here). Breadboard hardware; the
slide does not state the load type or the measurement instrumentation. The PDF is NOT redistributed; download it from
the URL above and pass its path.

Usage:  python extract_rhodes2024_discharge_efficiency.py --pdf <path to the slides PDF> [--out <csv>]
Needs PyMuPDF (tested with PyMuPDF 1.28.2); it is a documentation tool, not a simulator dependency.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import re
import sys
from pathlib import Path

PINNED_SHA256 = "9f5a6c7bb36ac2ffc45026e004150304a592dadb1419284917341623588e21d9"
PAGE_INDEX = 10                       # slide 11 (0-based page index 10)
CHART_TITLES = {"Efficiency at 250 V Output": 250, "Efficiency at 400 V Output": 400}
SERIES_LABELS = {"25 Vin": 25, "28 Vin": 28, "34 Vin": 34}
AXIS_GREY = (0.75, 0.75, 0.75)
GRID_GREY = (0.85, 0.85, 0.85)
DEFAULT_OUT = Path(__file__).resolve().parents[1] / "evidence" / "rhodes2024_lcc_discharge_supply_efficiency.csv"


def _close(a, b, tol=0.02):
    return a is not None and b is not None and len(a) == len(b) and all(abs(x - y) <= tol for x, y in zip(a, b))


def _fit(pairs):
    """Least-squares value = a + b * coord; returns (a, b, max |residual| in value units, n)."""
    n = len(pairs)
    if n < 3:
        raise SystemExit(f"axis calibration needs >= 3 reference lines, got {n}")
    sx = sum(c for c, _ in pairs); sy = sum(v for _, v in pairs)
    sxx = sum(c * c for c, _ in pairs); sxy = sum(c * v for c, v in pairs)
    b = (n * sxy - sx * sy) / (n * sxx - sx * sx)
    a = (sy - b * sx) / n
    res = max(abs(a + b * c - v) for c, v in pairs)
    return a, b, res, n


def _num(text):
    t = text.strip()
    return float(t) if re.fullmatch(r"\d+(\.\d+)?", t) else None


def extract(pdf_path: Path):
    import pymupdf  # documentation-tool dependency only
    data = pdf_path.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    if sha != PINNED_SHA256:
        raise SystemExit(f"sha256 mismatch: {sha} != pinned {PINNED_SHA256}; refusing to extract from a different file")
    page = pymupdf.open(stream=data, filetype="pdf")[PAGE_INDEX]
    spans = [s for b in page.get_text("dict")["blocks"] for l in b.get("lines", []) for s in l["spans"]]
    drawings = page.get_drawings()

    def col(d, key):
        c = d.get(key)
        return tuple(c) if c else None

    axes_v = [d for d in drawings if d["type"] == "s" and _close(col(d, "color"), AXIS_GREY) and len(d["items"]) == 1
              and abs(d["items"][0][1].x - d["items"][0][2].x) < 1e-6]
    axes_h = [d for d in drawings if d["type"] == "s" and _close(col(d, "color"), AXIS_GREY) and len(d["items"]) == 1
              and abs(d["items"][0][1].y - d["items"][0][2].y) < 1e-6]
    grids = [d for d in drawings if d["type"] == "s" and _close(col(d, "color"), GRID_GREY)]
    markers = [d for d in drawings if d["type"] in ("f", "fs") and col(d, "fill") is not None
               and 4.0 <= d["rect"].width <= 6.5 and 4.0 <= d["rect"].height <= 6.5]

    rows, calib = [], []
    for title, v_out in CHART_TITLES.items():
        tspan = [s for s in spans if s["text"].strip() == title]
        if len(tspan) != 1:
            raise SystemExit(f"chart title {title!r} not found exactly once")
        tx0, ty0, tx1, ty1 = tspan[0]["bbox"]
        tcx = 0.5 * (tx0 + tx1)
        # the chart's y axis is the nearest vertical axis line to the left of the title centre
        yaxis = min((d for d in axes_v if d["items"][0][1].x < tcx), key=lambda d: tcx - d["items"][0][1].x)
        x_ax = yaxis["items"][0][1].x
        y_top = min(yaxis["items"][0][1].y, yaxis["items"][0][2].y)
        y_bot = max(yaxis["items"][0][1].y, yaxis["items"][0][2].y)
        xaxis = [d for d in axes_h if abs(d["items"][0][1].y - y_bot) < 0.5 and min(d["items"][0][1].x, d["items"][0][2].x) >= x_ax - 0.5]
        if len(xaxis) != 1:
            raise SystemExit(f"{title}: x axis not identified")
        x_right = max(xaxis[0]["items"][0][1].x, xaxis[0]["items"][0][2].x)
        inside = lambda x, y: x_ax - 1 <= x <= x_right + 1 and y_top - 1 <= y <= y_bot + 1
        # reference lines: y axis/horizontal gridlines (value = y tick) and x axis/vertical gridlines (value = x tick)
        h_lines = [y_bot] + [it[1].y for d in grids for it in d["items"]
                             if abs(it[1].y - it[2].y) < 1e-6 and abs(it[1].x - x_ax) < 0.5]
        v_lines = [x_ax] + [it[1].x for d in grids for it in d["items"]
                            if abs(it[1].x - it[2].x) < 1e-6 and x_ax + 1 < it[1].x <= x_right + 0.5 and abs(max(it[1].y, it[2].y) - y_bot) < 0.5]
        y_ticks = [(0.5 * (s["bbox"][1] + s["bbox"][3]), _num(s["text"])) for s in spans
                   if _num(s["text"]) is not None and s["bbox"][2] <= x_ax and x_ax - s["bbox"][2] < 12 and y_top - 8 <= 0.5 * (s["bbox"][1] + s["bbox"][3]) <= y_bot + 8]
        x_ticks = [(0.5 * (s["bbox"][0] + s["bbox"][2]), _num(s["text"])) for s in spans
                   if _num(s["text"]) is not None and s["bbox"][1] >= y_bot and s["bbox"][1] - y_bot < 12 and x_ax - 15 <= 0.5 * (s["bbox"][0] + s["bbox"][2]) <= x_right + 15]
        ypairs = []
        for yl in h_lines:
            c, v = min(y_ticks, key=lambda t: abs(t[0] - yl))
            if abs(c - yl) > 3.0:
                raise SystemExit(f"{title}: no tick label within 3 pt of horizontal reference line y={yl:.2f}")
            ypairs.append((yl, v))
        xpairs = []
        for xl in v_lines:
            c, v = min(x_ticks, key=lambda t: abs(t[0] - xl))
            if abs(c - xl) > 3.0:
                raise SystemExit(f"{title}: no tick label within 3 pt of vertical reference line x={xl:.2f}")
            xpairs.append((xl, v))
        ay, by, ry, ny = _fit(ypairs)
        ax, bx, rx, nx = _fit(xpairs)
        calib.append((v_out, ny, ry, nx, rx))
        for label, v_in in SERIES_LABELS.items():
            lspan = [s for s in spans if s["text"].strip() == label and inside(s["bbox"][0], 0.5 * (s["bbox"][1] + s["bbox"][3]))]
            if len(lspan) != 1:
                raise SystemExit(f"{title}: legend entry {label!r} not found exactly once")
            lx0, ly0, lx1, ly1 = lspan[0]["bbox"]
            lmk = [m for m in markers if ly0 <= 0.5 * (m["rect"].y0 + m["rect"].y1) <= ly1 and lx0 - 30 <= 0.5 * (m["rect"].x0 + m["rect"].x1) <= lx0]
            if len(lmk) != 1:
                raise SystemExit(f"{title}: legend marker for {label!r} not identified ({len(lmk)} candidates)")
            fill = col(lmk[0], "fill")
            pts = []
            for m in markers:
                cx = 0.5 * (m["rect"].x0 + m["rect"].x1); cy = 0.5 * (m["rect"].y0 + m["rect"].y1)
                if m is lmk[0] or not _close(col(m, "fill"), fill) or not inside(cx, cy):
                    continue
                pts.append((cx, cy))
            pts.sort()
            if not pts:
                raise SystemExit(f"{title}: no data markers for {label!r}")
            for cx, cy in pts:
                rows.append({"chart_output_voltage_V": v_out, "input_bus_voltage_V": v_in,
                             "P_out_W": ax + bx * cx, "efficiency_pct": ay + by * cy,
                             "marker_x_pt": cx, "marker_y_pt": cy})
    return sha, rows, calib


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pdf", required=True, type=Path)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    a = ap.parse_args(argv)
    sha, rows, calib = extract(a.pdf)
    buf = io.StringIO()
    buf.write("# Rhodes, Benavides & Pinero, IEPC 2024 presentation (NASA NTRS 20240006846), slide 11, LCC discharge supply.\n")
    buf.write(f"# source sha256 {sha}; vector-extracted by tools/extract_rhodes2024_discharge_efficiency.py (PyMuPDF).\n")
    buf.write("# evidence class: measured (source, breadboard bench test) -> digitized (vector marker centres).\n")
    buf.write("# efficiency = supply output power / supply input power as plotted by the source (definition not stated on the slide).\n")
    for v_out, ny, ry, nx, rx in calib:
        buf.write(f"# calibration {v_out} V chart: y {ny} reference lines, max residual {ry:.4f} %-pt; "
                  f"x {nx} reference lines, max residual {rx:.4f} W\n")
    w = csv.DictWriter(buf, fieldnames=["chart_output_voltage_V", "input_bus_voltage_V", "P_out_W", "efficiency_pct",
                                        "marker_x_pt", "marker_y_pt"], lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({k: (f"{v:.2f}" if isinstance(v, float) else v) for k, v in r.items()})
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(buf.getvalue())
    print(f"wrote {len(rows)} points to {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
