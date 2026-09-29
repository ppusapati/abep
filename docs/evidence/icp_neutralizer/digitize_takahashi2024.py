#!/usr/bin/env python3
"""Pixel digitizer for Takahashi, Watanabe, Nakahama & Kikuchi (2024), J. Electr. Propuls. 3:18, Figs. 2 and 4.

Reproduction tool, NOT run by the tests and NOT needed by the builder: it regenerates the committed pixel record
`takahashi2024_fig_pixels_v1.json` from a locally held copy of the publisher PDF (the PDF is not committed; its licence
is CC BY-NC-ND 4.0 and the repository never redistributes it). The builder converts the committed pixel record to
physical values with the axis calibrations recorded here, so every digitized number is reproducible from
(PDF sha256, this script, poppler `pdfimages`).

Usage:
    python docs/evidence/icp_neutralizer/digitize_takahashi2024.py --pdf <path to s44205-024-00081-2.pdf> [--write]

Method (deterministic, no fitting):
  * the embedded raster figures are extracted with `pdfimages -png` (Fig. 2 = image on PDF page 4, Fig. 4 = image on
    PDF page 7; both 300 ppi, 1417 px wide);
  * axis frames / tick marks are located from dark-pixel row/column counts; which tick carries which printed value is
    stated explicitly below (read from the printed tick labels);
  * Fig. 4 markers: filled blue squares (I_D in b, V_A in a) = vertical blue run through the marker column; open blue
    triangles (V_K in a) = bounding box of blue pixels in the marker column window; open red circles (V_max in a,
    I_c60 in b) = the longest vertical run of red pixels in a band on the circle's left edge (error-bar caps are
    short runs and are recorded separately as the error-bar extent);
  * a marker partly hidden behind another symbol is flagged `occluded` and its centre is taken from the visible
    edge plus the half symbol height measured on unoccluded markers of the same kind.
Missing inputs raise; nothing is guessed.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "takahashi2024_fig_pixels_v1.json")
EXPECTED_PDF_SHA256 = "1e4778559d61509d520fac91798f7ed9ebb92d18a31a2e9b9f2598a8894d6e1f"
VD_NOMINAL = [0, 140, 160, 180, 200, 220, 240, 260]  # V; the V_D grid printed in Fig. 4 (marker columns)


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def _groups(idx):
    out, cur = [], []
    for i in idx:
        if cur and i != cur[-1] + 1:
            out.append(cur)
            cur = []
        cur.append(int(i))
    if cur:
        out.append(cur)
    return [(g[0], g[-1]) for g in out]


def _runs(mask_1d, offset):
    runs, s = [], None
    for i, v in enumerate(mask_1d):
        if v and s is None:
            s = i
        if not v and s is not None:
            runs.append((s + offset, i - 1 + offset))
            s = None
    if s is not None:
        runs.append((s + offset, len(mask_1d) - 1 + offset))
    return runs


def _extract(pdf, page, tmp):
    prefix = os.path.join(tmp, "p%d" % page)
    subprocess.run(["pdfimages", "-png", "-f", str(page), "-l", str(page), pdf, prefix], check=True)
    files = sorted(f for f in os.listdir(tmp) if f.startswith("p%d-" % page) and f.endswith(".png"))
    if not files:
        raise RuntimeError("no raster image on PDF page %d" % page)
    return os.path.join(tmp, files[0])


def digitize(pdf):
    import numpy as np
    from PIL import Image

    sha = _sha(pdf)
    if sha != EXPECTED_PDF_SHA256:
        raise RuntimeError("PDF sha256 %s != expected %s" % (sha, EXPECTED_PDF_SHA256))
    with tempfile.TemporaryDirectory() as tmp:
        f4 = _extract(pdf, 7, tmp)
        f2 = _extract(pdf, 4, tmp)
        im4 = np.array(Image.open(f4).convert("RGB")).astype(int)
        im2 = np.array(Image.open(f2).convert("RGB")).astype(int)
        sha_f4, sha_f2 = _sha(f4), _sha(f2)

    # ---------------- Fig. 4 ----------------
    r, g, b = im4[..., 0], im4[..., 1], im4[..., 2]
    dark = (r + g + b) < 300
    blue = (b > 180) & (r < 80) & (g < 80)
    red = (r > 180) & (g < 90) & (b < 90)
    frame_rows = _groups([i for i in range(im4.shape[0]) if dark[i, :].sum() > 600])
    if len(frame_rows) != 4:
        raise RuntimeError("Fig. 4: expected 4 frame edges (2 panels), found %s" % frame_rows)
    a_top, a_bot, b_top, b_bot = frame_rows
    left_cols = _groups([j for j in range(im4.shape[1]) if dark[:, j].sum() > 1000])
    x_left = left_cols[0]
    seg_x = dark[b_bot[0] - 19:b_bot[0] - 2, :].sum(0)
    xticks = _groups([j for j in range(x_left[1] + 2, im4.shape[1]) if seg_x[j] >= 10])
    seg_r = dark[:, 1255:1280].sum(1)
    rticks_b = _groups([i for i in range(b_top[1] + 2, b_bot[0] - 1) if seg_r[i] >= 15])
    seg_l = dark[:, x_left[1] + 2:x_left[1] + 22].sum(1)
    lticks_b = _groups([i for i in range(b_top[1] + 2, b_bot[0] - 1) if seg_l[i] >= 12])
    mid = lambda t: (t[0] + t[1]) / 2.0
    # printed tick labels: x ticks at V_D = 0, 50, 100, 150, 200, 250 V (the first is the dashed V_D = 0 line);
    # panel a frame top = 150 V, bottom = -100 V; panel b left axis 0 at the tick 1 minor below the bottom-most
    # labelled '0' (tick group whose centre equals the dashed zero line), right axis major '1' tick = 1.0 A.
    xt = [mid(t) for t in xticks]
    if len(xt) < 6:
        raise RuntimeError("Fig. 4: x ticks not found: %s" % xticks)
    x0, x200 = xt[0], xt[4]
    zero_b = [mid(t) for t in lticks_b][-1]  # lowest left tick above the frame bottom = 0 (dashed line)
    rt = [mid(t) for t in rticks_b]
    k0 = min(range(len(rt)), key=lambda k: abs(rt[k] - zero_b))  # right-axis tick on the dashed zero line
    one_amp = rt[k0 - 10]  # ten minor (0.1 A) intervals above the zero tick = the printed '1' tick
    cal = {
        "x_VD": {"px": [x0, x200], "value": [0.0, 200.0], "unit": "V"},
        "a_y_V": {"px": [mid(a_top), mid(a_bot)], "value": [150.0, -100.0], "unit": "V"},
        "b_y_Ic60": {"px": [zero_b, mid(b_top)], "value": [0.0, 1.0], "unit": "arb. units"},
        "b_y_ID": {"px": [rt[k0], one_amp], "value": [0.0, 1.0], "unit": "A"},
    }
    xpx = lambda v: x0 + (x200 - x0) * v / 200.0
    markers = []
    half_sq = []
    for vd in VD_NOMINAL:
        cx = int(round(xpx(vd)))
        rec = {"VD_nominal_V": vd, "x_px": cx}
        # red circles: longest run on left-edge band, per panel
        for key, (y0, y1) in (("Vmax_a", (a_top[1] + 2, a_bot[0] - 1)), ("Ic60_b", (b_top[1] + 2, b_bot[0] - 1))):
            col = red[y0:y1, cx - 19:cx - 13].any(1)
            runs = _runs(col, y0)
            if not runs:
                rec[key] = None
                continue
            body = max(runs, key=lambda t: t[1] - t[0])
            caps = [t for t in runs if t != body and (t[1] - t[0]) <= 6]
            rec[key] = {"centre_y_px": mid(body), "body_run_px": list(body), "cap_runs_px": [list(c) for c in caps]}
        # blue filled square, panel b (I_D)
        # sample the right half of the 31 px square, clear of the red error-bar line through the marker centre
        colb = blue[b_top[1] + 2:b_bot[0] - 1, cx + 6:cx + 12].mean(1) >= 0.5
        runs = [t for t in _runs(colb, b_top[1] + 2) if t[1] - t[0] >= 6]
        rec["ID_b"] = {"runs_px": [list(t) for t in runs]} if runs else None
        if runs and runs[-1][1] - runs[-1][0] >= 28:
            half_sq.append((runs[-1][1] - runs[-1][0]) / 2.0)
        # blue open triangle, panel a (V_K): bounding box of blue in the marker window below the V_A squares
        ya0 = int(round(mid(a_top) + (mid(a_bot) - mid(a_top)) * (150.0 - 30.0) / 250.0))  # below +30 V
        # the legend symbols (upper right of panel a) also fall in some marker windows; the data triangle is the
        # lowest blue group in the window
        win = blue[ya0:a_bot[1] + 1, cx - 20:cx + 21]
        grp = _groups(np.where(win.any(1))[0])
        rec["VK_a"] = {"bbox_y_px": [grp[-1][0] + ya0, grp[-1][1] + ya0]} if grp else None
        markers.append(rec)
    fig4 = {"image_sha256": sha_f4, "image_px": [int(im4.shape[1]), int(im4.shape[0])], "calibration": cal,
            "frame_rows_px": {"a": [list(a_top), list(a_bot)], "b": [list(b_top), list(b_bot)]},
            "square_half_height_px": (sum(half_sq) / len(half_sq)) if half_sq else None, "markers": markers}

    # ---------------- Fig. 2 ----------------
    r, g, b = im2[..., 0], im2[..., 1], im2[..., 2]
    dark = (r + g + b) < 150
    hax = _groups([i for i in range(im2.shape[0]) if dark[i, :].sum() > 900])
    vax = _groups([j for j in range(im2.shape[1]) if dark[:, j].sum() > 700])
    if len(hax) != 1 or len(vax) != 1:
        raise RuntimeError("Fig. 2: axes not found")
    segx = dark[hax[0][0] - 25:hax[0][0] - 2, :].sum(0)
    zt = [mid(t) for t in _groups([j for j in range(vax[0][1] + 2, im2.shape[1]) if segx[j] >= 15])]
    segy = dark[:, vax[0][1] + 2:vax[0][1] + 25].sum(1)
    rt2 = [mid(t) for t in _groups([i for i in range(0, hax[0][0] - 2) if segy[i] >= 15])]
    # printed tick labels: z = -30, -20, -10, 0 mm; r = 30, 20, 10, 0 mm (top to bottom)
    if len(zt) != 4 or len(rt2) != 4:
        raise RuntimeError("Fig. 2: tick marks %s %s" % (zt, rt2))
    bl = (b > 100) & (r < 80) & (g < 80) & ((b - r) > 50)
    chan_rows = _groups([i for i in range(im2.shape[0]) if bl[i, 400:840].sum() > 300])[:2]
    chan_back = _groups([j for j in range(im2.shape[1]) if bl[400:590, j].sum() > 150])[0]
    grey = (abs(r - g) < 8) & (abs(g - b) < 8) & (r > 110) & (r < 150)
    sub = grey[chan_rows[0][1] + 5:chan_rows[1][0], chan_back[1] + 2:840]
    ys = np.where(sub.sum(1) > 50)[0]
    xs = np.where(sub.sum(0) > 50)[0]
    white = (r > 245) & (g > 245) & (b > 245)
    wcols = _groups([j for j in range(600, im2.shape[1] - 200) if white[:, j].sum() > 500])
    fig2 = {"image_sha256": sha_f2, "image_px": [int(im2.shape[1]), int(im2.shape[0])],
            "calibration": {"z_mm": {"px": [zt[0], zt[3]], "value": [-30.0, 0.0], "unit": "mm"},
                            "r_mm": {"px": [rt2[3], rt2[0]], "value": [0.0, 30.0], "unit": "mm"}},
            "channel_wall_rows_px": [list(chan_rows[0]), list(chan_rows[1])],
            "channel_back_col_px": list(chan_back),
            "anode_bbox_px": {"x": [int(xs.min()) + chan_back[1] + 2, int(xs.max()) + chan_back[1] + 2],
                              "y": [int(ys.min()) + chan_rows[0][1] + 5, int(ys.max()) + chan_rows[0][1] + 5]},
            "al2o3_cols_px": list(wcols[0])}
    return {"schema": "takahashi2024_fig_pixels_v1", "source_pdf_sha256": sha, "tool": "pdfimages -png (poppler)",
            "fig4": fig4, "fig2": fig2}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    data = digitize(a.pdf)
    txt = json.dumps(data, indent=1, sort_keys=True) + "\n"
    if a.write:
        with open(OUT, "w", encoding="utf-8") as f:
            f.write(txt)
        print("wrote", OUT)
        return 0
    if not os.path.exists(OUT):
        print(txt)
        return 1
    with open(OUT, encoding="utf-8") as f:
        same = f.read() == txt
    print("pixel record reproduces" if same else "pixel record DIFFERS")
    return 0 if same else 1


if __name__ == "__main__":
    sys.exit(main())
