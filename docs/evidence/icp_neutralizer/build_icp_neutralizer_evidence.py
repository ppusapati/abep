#!/usr/bin/env python3
"""A9-05 part 1 - evidence extraction for the downstream RF-ICP neutralizer (fo_a9_05_hall_icp_validation_inputs).

Builds `icp_neutralizer_evidence_v1.json` and its companion `ICP_NEUTRALIZER_EVIDENCE.md` deterministically from:
  * the transcriptions below (reported values, each with page / figure / equation locator, read from the publisher
    PDF of Takahashi, Watanabe, Nakahama & Kikuchi 2024, sha256 recorded, not committed: CC BY-NC-ND 4.0), and
  * the committed pixel record `takahashi2024_fig_pixels_v1.json` (regenerable with `digitize_takahashi2024.py`
    from the same PDF), converted to physical values here with the axis calibrations it carries, and
  * a bounded open-literature survey (8 primary sources; full text where openly served, otherwise abstract- or
    metadata-only and labelled so).

Nothing here is a prediction for Vyovrinda hardware. All values are 'published analog' evidence (topology precedent,
different geometry / gas / facility); no Hall transport closure, no abep_sim/plasma_devices.py and no withdrawn
v1.2-v1.6 number is used.

Usage:  python docs/evidence/icp_neutralizer/build_icp_neutralizer_evidence.py [--check]
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
JSON_OUT = os.path.join(HERE, "icp_neutralizer_evidence_v1.json")
MD_OUT = os.path.join(HERE, "ICP_NEUTRALIZER_EVIDENCE.md")
PIXELS = os.path.join(HERE, "takahashi2024_fig_pixels_v1.json")
REL = "docs/evidence/icp_neutralizer"

LANE = "fo_a9_05_hall_icp_validation_inputs"
TRIGGER = "T_A9_05_VALIDATION_INPUTS"
BASE_COMMIT = "0a430bb5588a438f7c8485c6d16f40ed0d402c4c"
RETRIEVED_ON = "2026-09-29"
CONFIG_IDS = ["hall_c1_reference", "hall_icp_neutralizer"]

A9 = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer.json"
ANSWERS = "docs/decisions/OD_2026_09_29_owner_answers_147.json"
PACK = "docs/decisions/OD_2026_09_29_OWNER_DECISION_PACK_147.md"

AUTHORITY_PINS = [
    {"path": A9, "sha256": "74ef1a727c3656841ef115122c6d60865f7d2d93cfa29f7fb0081886484d2a1f",
     "role": "governing owner decision A9 (status OWNER_AUTHORIZED_INVESTIGATION_HYPOTHESIS_NOT_FLIGHT_BASELINE)"},
    {"path": ANSWERS, "sha256": "50e39a4deac7d4ada4710b2f641d717f1c4febd59366cbc04d8c66de6b4532b1",
     "role": "owner's 147 answers, machine-readable (cited by row)"},
    {"path": PACK, "sha256": "8736d88a64bf26bd06a332a68c2450a780f175fffafe5aca0625759133666976",
     "role": "owner decision pack, verbatim"},
]

# verified, read-only inputs this lane consumes (immutable deliverables, pinned by sha256)
DELIVERABLE_PINS = [
    {"path": "docs/evidence/cathode/cathode_evidence_v1.json",
     "sha256": "050060204e443d5583c307becadaab55a9f213d406ff4454be856bca21249110",
     "role": "cathode / neutralizer dossier: rf_plasma_cathode entries (watanabe_2015, schwertheim_2025) cross-referenced"},
    {"path": "docs/experiments/instrumentation/instrumentation_definition_v1.json",
     "sha256": "7c6d37b00f38a44cded73d92d4366739eacbf013e73e98a7bfbc3fa5a5470d96",
     "role": "measurement-chain ids (INS-xx) that analog quantities map onto"},
]

GOVERNANCE_NOT_PINNED = [
    "docs/orchestration/lane_registry_v1.json",
    "docs/orchestration/trigger_registry_v1.json",
    "docs/orchestration/trigger_ledger_v2.jsonl",
    "docs/orchestration/fired_triggers.jsonl",
    "docs/orchestration/runtime_state.json",
]

ANCHOR = {
    "id": "takahashi_2024",
    "citation": "K. Takahashi, H. Watanabe, Y. Nakahama, K. Kikuchi, 'Hall thruster ion acceleration neutralized by a "
                "radiofrequency inductively coupled plasma', Journal of Electric Propulsion 3, 18 (2024). Brief "
                "Communication; received 21 March 2024, accepted 3 September 2024, published 2024-09-27.",
    "doi": "10.1007/s44205-024-00081-2",
    "license": "CC BY-NC-ND 4.0 (stated on PDF p. 1)",
    "access": "open access, publisher PDF",
    "retrieval": {"url": "https://link.springer.com/content/pdf/10.1007/s44205-024-00081-2.pdf",
                  "method": "curl via the session proxy (no bypass, no login)", "http_status": 200,
                  "content_type": "application/pdf", "retrieved_on": RETRIEVED_ON, "bytes": 2457280, "pages": 10,
                  "sha256": "1e4778559d61509d520fac91798f7ed9ebb92d18a31a2e9b9f2598a8894d6e1f",
                  "crossref_metadata": "https://api.crossref.org/works/10.1007/s44205-024-00081-2 (title, authors, "
                                       "volume 3, article 18, licence CC BY-NC-ND 4.0) checked " + RETRIEVED_ON},
    "redistribution": "the PDF is NOT committed (NC-ND licence; the repository stores only locators, reported values, "
                      "a pixel record of Figs. 2 and 4 and this lane's derived numbers, each attributed)",
    "evidence_class": "published analog (topology precedent), not validation of Vyovrinda hardware",
    "data_availability_statement": "'available from the corresponding author upon reasonable request' (PDF p. 9). "
                                   "Not requested: the standing rules forbid contact with authors or labs "
                                   "(owner answer row 7: no author-contact shortcuts unless separately authorized).",
}

# value_basis: reported | digitized | derived | authors_estimate | not_reported
# epistemic (docs/EVIDENCE.md vocabulary): measured | digitized | inferred | model-derived | assumed
EXTRACTION = [
    # ---- device: Hall thruster (HET) ----
    ("TK-01", "HET", "Hall thruster type and magnetic circuit",
     "annular-cavity HET; cylindrical SmCo permanent magnet at the radial centre and annular SmCo magnet at the "
     "periphery, iron (labelled SC45C) behind the magnets forming the circuit; no electromagnet coil", None,
     "p. 4 text; Fig. 2 labels", "reported", "measured",
     "Permanent-magnet circuit: no coil-current B(z) control (contrast owner answer row 78, H-1 EM only)."),
    ("TK-02", "HET", "discharge-cavity walls and anode material",
     "stainless-steel (SUS304) cavity, inner wall coated with an insulator (silicone resin) against short circuit; "
     "SUS304 anode located behind the peak-field region; Al2O3 parts at the exit face (Fig. 2)", None,
     "p. 4 text; Fig. 2 labels", "reported", "measured", ""),
    ("TK-03", "HET", "peak radial magnetic field in the cavity (calculated)", "0.1-0.15 at z ~ -10 mm", "T",
     "Abstract p. 1; p. 4 text; Fig. 2", "reported", "model-derived",
     "Authors' magnetostatic calculation, not a measured map."),
    ("TK-04", "HET", "propellant injection", "four small holes on the anode electrode", None, "p. 2-3 text",
     "reported", "measured", ""),
    ("TK-05", "HET", "thrust-class / power-class designation", None, None, "whole paper", "not_reported", None,
     "No thrust, mass, power class or name of the HET is given."),
    # ---- device: ICP neutralizer ----
    ("TK-10", "ICP", "ICP source tube", "pyrex tube, 6.5 cm inner diameter (65 mm, p. 6)", "cm", "p. 2 text; p. 6 text",
     "reported", "measured", ""),
    ("TK-11", "ICP", "antenna", "double-turn loop antenna wound on the tube; antenna covered by insulator and grounded "
     "metallic structures to minimize parasitic discharge outside the source (ref. [21])", None, "p. 2 text; Fig. 1b",
     "reported", "measured", "Antenna axial position along the tube is shown only schematically (Fig. 1a/1b)."),
    ("TK-12", "ICP", "position relative to the thruster exit",
     "the upstream side of the source tube is terminated by the HET structure; z = 0 is the HET exit and the tube / "
     "ion collector extends to z = 10 cm (Fig. 1a annotations)", "cm", "p. 2 text; p. 3 text (z = 0 definition); "
     "Fig. 1a", "reported", "measured", "Coaxial downstream topology: the Hall exhaust passes through the ICP tube."),
    ("TK-13", "ICP", "ion collector ('cathode electrode')",
     "C-type stainless-steel electrode, 10 cm axial length, on the inner wall of the source tube, with an axial slit "
     "so that the RF fields can penetrate; collects ions to keep charge neutrality while electrons are extracted",
     "cm", "p. 3 text; Fig. 1b", "reported", "measured",
     "The discharge voltage V_D is applied between the HET anode and this electrode."),
    ("TK-14", "ICP", "applied magnetic field of the ICP source", None, None, "p. 2-4",
     "not_reported", None, "No ICP magnet is described (unmagnetized ICP); the HET permanent-magnet fringe field in "
     "the tube is shown only up to z ~ +10 mm in Fig. 2."),
    # ---- RF ----
    ("TK-20", "RF", "RF frequency", 13.56, "MHz", "Abstract p. 1; p. 3 text", "reported", "measured", ""),
    ("TK-21", "RF", "RF generator rating and forward power used", 200, "W", "Abstract p. 1; p. 3 text", "reported",
     "measured", "Forward power 200 W; 'no power reflection is detected; the input power P_rf to the load is equal to "
     "the forward power of 200 W' (p. 3)."),
    ("TK-22", "RF", "reflected power", 0, "W", "p. 3 text", "reported", "measured",
     "Reported as 'not detected' by the generator power meters (resolution not stated)."),
    ("TK-23", "RF", "matching network", "two variable capacitors tuned to minimize reflection; forward/reflected "
     "power from the generator's power meters; vacuum feedthrough to the antenna", None, "p. 3 text", "reported",
     "measured", ""),
    ("TK-24", "RF", "antenna resistance without plasma R_ant", 0.36, "ohm", "p. 8 text", "reported", "measured",
     "From the RF antenna current measured with a high-frequency current sensor (p. 3)."),
    ("TK-25", "RF", "total resistance during discharge R_total at P_rf = 200 W", 0.4, "ohm", "p. 8 text ('about')",
     "reported", "measured", ""),
    ("TK-26", "RF", "RF power transfer efficiency eta_p = R_p / (R_p + R_ant)", 0.1, "-", "p. 7-8 text, Eq. (1)",
     "reported", "inferred", "Authors' evaluation of Eq. (1) with R_p = R_total - R_ant."),
    ("TK-27", "RF", "RF power absorbed by the plasma", 20, "W", "p. 8 text", "authors_estimate", "inferred",
     "= eta_p x 200 W; 'most of the rf power is considered to be consumed for heating the electrode' (eddy currents "
     "in the ion-collecting electrode; heating visible even without plasma)."),
    ("TK-28", "RF", "authors' projection: RF power needed at eta_p = 80 %", "25-30", "W", "p. 8 text",
     "authors_estimate", "assumed", "A projection, not a measurement; not usable as a Vyovrinda power value."),
    # ---- gas / facility ----
    ("TK-30", "gas", "propellant", "argon only (proof of principle)", None, "Abstract; p. 2 text", "reported",
     "measured", "Single gas feed through the HET anode; the ICP re-uses the gas ejected from the HET (no separate "
     "ICP feed)."),
    ("TK-31", "gas", "total gas flow rate", "70 sccm (2.1 mg/s)", "sccm", "p. 3 text", "reported", "measured",
     "Shared by HET and ICP; the ICP share is not separable."),
    ("TK-32", "facility", "vacuum chamber", "1 m diameter x 2 m long, three turbomolecular pumping systems", None,
     "p. 2 text; Fig. 1a", "reported", "measured", ""),
    ("TK-33", "facility", "base pressure", 1e-4, "Pa", "p. 2 text", "reported", "measured", ""),
    ("TK-34", "facility", "chamber pressure at 70 sccm Ar", 0.028, "Pa", "p. 3 text ('about 28 mPa')", "reported",
     "measured", "Gauge type / location not stated."),
    ("TK-35", "gas", "neutral density estimate in the 65 mm tube", 2e19, "m^-3", "p. 6 text", "authors_estimate",
     "inferred", "From mdot = M n v S with an assumed v_n ~ 400 m/s."),
    ("TK-36", "gas", "CEX mean free path estimate in the tube", 4, "cm", "p. 6 text", "authors_estimate", "inferred",
     "Assumed CEX cross-section 1e-18 m^2; shorter than the 10 cm source length."),
    # ---- circuit ----
    ("TK-40", "circuit", "discharge circuit",
     "DC supply V_D between HET anode and the ICP ion-collecting electrode; isolation transformer isolates the supply "
     "from the grounded chamber ('ensuring the zero net current to the chamber'); 50 ohm series resistor (arc "
     "limiting) and a 13.56 MHz L-C resonance circuit (RF interference) in series", None, "p. 3 text; Fig. 1a",
     "reported", "measured", "There is no separate collector-bias supply: the collector sits at the negative end of "
     "V_D and floats relative to ground (V_K in Fig. 4a)."),
    ("TK-41", "circuit", "effective anode-cathode voltage reduced by the 50 ohm resistor drop",
     "qualitative: 'the effectively applied voltage between the cathode and anode is reduced by the voltage drop at "
     "the 50 ohm resistor'", None,
     "p. 6 text", "reported", "measured", "Stated qualitatively; see derived ID-R drop in the digitized table."),
    # ---- discharge / neutralization ----
    ("TK-50", "discharge", "annular discharge onset (visual)", "V_D > 140", "V", "p. 3 text; p. 6 text", "reported",
     "measured", ""),
    ("TK-51", "discharge", "annular discharge without RF power", "not induced for any V_D", None, "p. 3 text",
     "reported", "measured", "Authors: implies the electrons extracted from the ICP sustain the HET discharge."),
    ("TK-52", "discharge", "discharge current I_D (order)", "about 1", "A", "p. 8 text; Fig. 4b", "reported",
     "measured", "Digitized series: see digitized_fig4."),
    ("TK-53", "discharge", "I_D and I_c60 trend", "both increase with V_D and are fairly constant for V_D > ~200 V; "
     "the current limit 'seems to be decided by the rf power of the ICP neutralizer'", None, "p. 7 text; Fig. 4b",
     "reported", "measured", "The RF-power attribution is the authors' interpretation (no RF-power scan shown)."),
    ("TK-54", "discharge", "anode potential V_A and V_max", "V_max saturates at about 120-130 V and agrees with V_A",
     "V", "p. 6 text; Fig. 4a", "reported", "measured", "V_A squares are largely hidden behind the V_max circles "
     "in Fig. 4a and are not digitized here."),
    ("TK-55", "discharge", "ion-collector potential V_K", "decreases to about -100 V with increasing V_D", "V",
     "p. 6 text; Fig. 4a", "reported", "measured", "Digitized series: see digitized_fig4."),
    ("TK-56", "neutralization", "evidence of beam neutralization",
     "qualitative: RFEA IEDF at z = 25 cm shows ions with maximum energy close to the anode potential with the "
     "supply isolated from ground (zero net current to the chamber); no electron-current or beam-current balance is "
     "reported", None, "Abstract; p. 6 text; Summary p. 9", "reported", "measured",
     "No separate measurement of the electron current emitted into the beam versus drawn to the anode."),
    ("TK-57", "diagnostics", "RFEA", "four grids + collector at z = 25 cm on axis; 10 mm entrance orifice in a grounded "
     "cover (G1); G2 and G4 at -80 V; G3 swept 0 to ~400 V; collector to ground through a resistor, isolation "
     "amplifier gain 100, 1 kHz low-pass; 14-bit DAQ", None, "p. 3-4 text; Fig. 1c", "reported", "measured", ""),
    ("TK-58", "diagnostics", "IEDF features", "V_D = 0: peaks at V_G3 ~ 20 V (local plasma potential) and ~ 40 V "
     "(ions from the source, plasma potential inside the tube ~40 V); V_D on: broadened component ~50-120 V",
     "V", "p. 5-6 text; Fig. 3", "reported", "measured", ""),
    ("TK-59", "diagnostics", "I_c60 metric", "RFEA collector current at V_G3 = 60 V (zero at V_D = 0), a qualitative "
     "local flux of ions accelerated from the HET", "arb. units", "p. 6-7 text; Fig. 4b", "reported", "measured", ""),
    ("TK-60", "neutralization", "thrust measurement", None, None, "whole paper", "not_reported", None,
     "No thrust stand, no thrust, no Faraday-probe beam current, no divergence, no efficiency."),
    ("TK-61", "discharge", "Hall discharge power", None, None, "whole paper", "not_reported", None,
     "Only V_D and I_D are shown; the products computed in digitized_fig4 are this lane's arithmetic."),
    ("TK-62", "discharge", "repeatability", "error bars from several repeated shots, attributed to thermal issues of "
     "the HET and the ICP neutralizer", None, "p. 7 text; Fig. 4 caption", "reported", "measured", ""),
    # ---- erosion / life / startup ----
    ("TK-70", "erosion", "ion energy at the ion-collecting electrode", "V_ICP - V_K ~ 140 (ICP ions); V_A - V_K ~ 220 "
     "(HET ions lost to the electrode)", "V", "p. 6 text", "reported", "inferred",
     "Authors' sheath-energy estimates at the largest V_D."),
    ("TK-71", "erosion", "sputtering / deposition observed",
     "the stainless-steel electrode is sputtered; metallic films found after the experiment on part of the glass "
     "tube (at the electrode slit) and on the insulators at the HET front", None, "p. 6 text; Fig. 5", "reported",
     "measured", "Authors: the negative cathode potential 'has to be minimized in future research and development'."),
    ("TK-72", "life", "operating duration, lifetime or erosion rate", None, None, "whole paper", "not_reported", None,
     "No run duration, no mass-loss, no life test."),
    ("TK-73", "startup", "ignition sequence", "RF plasma turned on first, then V_D applied", None,
     "Abstract; p. 3 text", "reported", "measured", "No ignition statistics, restart count or cycle data reported."),
    ("TK-74", "chemistry", "operation with reactive gases",
     "authors state the ICP neutralizer 'is operational for various gas species including chemically active gases "
     "such as water, carbon dioxide, and iodine'", None, "Summary p. 9", "reported", "assumed",
     "A claim in the summary, not demonstrated in this paper (argon only); no N2/O2 data."),
]

LIMITATIONS = [
    ("LIM-01", "argon only; proof of principle of ion acceleration (p. 2)", "p. 2 text"),
    ("LIM-02", "poor RF power transfer efficiency (~10 %) caused by eddy-current heating of the ion-collecting "
               "electrode; proper electrode design required (p. 8)", "p. 8 text"),
    ("LIM-03", "enhanced cathodic sheath voltage at large V_D: significant energy loss to ions accelerated by the "
               "cathodic sheath; sputtering of the electrode and metallic coating of glass and HET insulators "
               "(p. 6, p. 9)", "p. 6 text; Summary p. 9"),
    ("LIM-04", "the physics of the broadened IEDF (CEX vs ionization in the potential gradient) is not resolved; "
               "'more detailed measurements will be required' (p. 6)", "p. 6 text"),
    ("LIM-05", "'more detailed physical studies and development are required to optimize the thruster design and "
               "performance' (p. 9)", "Summary p. 9"),
    ("LIM-06", "thermal issues of the HET and ICP neutralizer cause shot-to-shot scatter (p. 7)", "p. 7 text"),
]


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def _lin(cal, px):
    (p0, p1), (v0, v1) = cal["px"], cal["value"]
    return v0 + (v1 - v0) * (px - p0) / (p1 - p0)


def _per_px(cal):
    (p0, p1), (v0, v1) = cal["px"], cal["value"]
    return abs((v1 - v0) / (p1 - p0))


def _r(x, n=3):
    return None if x is None else round(float(x), n)


READ_PX = 2.0      # reading uncertainty of an unoccluded marker centre, px (symbol edge anti-aliasing + width)
OCCL_PX = 8.0      # reading uncertainty of an occluded marker centre, px
R_SERIES_OHM = 50.0  # the series resistor stated on p. 3 (reported)


def digitized_fig4(pix):
    f4 = pix["fig4"]
    cal = f4["calibration"]
    half_sq = f4["square_half_height_px"]
    rows = []
    for m in f4["markers"]:
        vd_px = _lin(cal["x_VD"], m["x_px"])
        row = {"VD_nominal_V": m["VD_nominal_V"], "VD_digitized_V": _r(vd_px, 1)}
        # I_D (panel b, filled squares)
        if m["ID_b"] is None:
            row["ID_A"] = None
            row["ID_note"] = "square hidden behind the circle on the zero line; not digitized"
        else:
            top, bot = m["ID_b"]["runs_px"][-1]
            occluded = (bot - top) < 2 * half_sq - 2
            cy = (bot - half_sq) if occluded else (top + bot) / 2.0
            row["ID_A"] = _r(_lin(cal["b_y_ID"], cy))
            row["ID_reading_u_A"] = _r((OCCL_PX if occluded else READ_PX) * _per_px(cal["b_y_ID"]))
            row["ID_occluded"] = occluded
        # V_K (panel a, open triangles)
        if m["VK_a"] is not None and m["VD_nominal_V"] != 0:
            y0, y1 = m["VK_a"]["bbox_y_px"]
            row["VK_V"] = _r(_lin(cal["a_y_V"], (y0 + y1) / 2.0), 1)
            row["VK_reading_u_V"] = _r(READ_PX * _per_px(cal["a_y_V"]), 1)
        else:
            row["VK_V"] = None
            row["VK_note"] = "V_A square and V_K triangle overlap at V_D = 0 (both ~0 V); not digitized"
        # V_max (panel a) and I_c60 (panel b), open circles with error-bar caps
        for key, calkey, out, nd in (("Vmax_a", "a_y_V", "Vmax_V", 1), ("Ic60_b", "b_y_Ic60", "Ic60_arb", 3)):
            rec = m[key]
            row[out] = _r(_lin(cal[calkey], rec["centre_y_px"]), nd)
            caps = rec["cap_runs_px"]
            if len(caps) == 2:
                c = sorted((a + b) / 2.0 for a, b in caps)
                row[out + "_errbar_half"] = _r((c[1] - c[0]) / 2.0 * _per_px(cal[calkey]), nd)
            else:
                row[out + "_errbar_half"] = None
        # this lane's arithmetic on digitized values (analog only)
        if row["ID_A"] is not None:
            row["VD_x_ID_W"] = _r(m["VD_nominal_V"] * row["ID_A"], 1)
            row["ID2_x_50ohm_W"] = _r(row["ID_A"] ** 2 * R_SERIES_OHM, 1)
            row["VD_minus_ID_x_50ohm_V"] = _r(m["VD_nominal_V"] - row["ID_A"] * R_SERIES_OHM, 1)
        rows.append(row)
    return rows


def geometry_fig2(pix):
    f2 = pix["fig2"]
    cz, cr = f2["calibration"]["z_mm"], f2["calibration"]["r_mm"]
    mid = lambda t: (t[0] + t[1]) / 2.0
    outer, inner = f2["channel_wall_rows_px"]
    an = f2["anode_bbox_px"]
    al = f2["al2o3_cols_px"]
    u = _r(READ_PX * _per_px(cz), 2)
    items = [
        ("TK-G1", "channel outer radius (insulator-coated wall line)", _lin(cr, mid(outer))),
        ("TK-G2", "channel inner radius (insulator-coated wall line)", _lin(cr, mid(inner))),
        ("TK-G3", "channel back wall axial position", _lin(cz, mid(f2["channel_back_col_px"]))),
        ("TK-G4", "exit-face Al2O3 parts, upstream face axial position", _lin(cz, al[0] - 0.5)),
        ("TK-G5", "exit-face Al2O3 parts, downstream face axial position", _lin(cz, al[1] + 0.5)),
        ("TK-G6", "anode block axial start", _lin(cz, an["x"][0])),
        ("TK-G7", "anode block axial end", _lin(cz, an["x"][1])),
        ("TK-G8", "anode block outer radius", _lin(cr, an["y"][0])),
        ("TK-G9", "anode block inner radius", _lin(cr, an["y"][1])),
    ]
    out = []
    for i, q, v in items:
        out.append({"id": i, "quantity": q, "value": _r(v, 1), "unit": "mm", "reading_u": u,
                    "locator": "Fig. 2 (PDF p. 4), calculation cross-section", "value_basis": "digitized",
                    "epistemic": "digitized", "evidence_class": "published analog",
                    "note": "read from the magnetostatic-calculation cross-section; its fidelity to the built "
                            "hardware is not stated; schematic-level geometry"})
    w = out[0]["value"] - out[1]["value"]
    out.append({"id": "TK-G10", "quantity": "channel width (TK-G1 - TK-G2)", "value": _r(w, 1), "unit": "mm",
                "reading_u": _r(2 * u, 2), "locator": "derived from TK-G1, TK-G2", "value_basis": "derived",
                "epistemic": "inferred", "evidence_class": "published analog", "note": "this lane's arithmetic"})
    return out


SURVEY = [
    {"id": "S-01", "source_id": "watanabe_2016_tastj",
     "citation": "H. Watanabe, T. Deguchi, S. Takeda, Y. Miura, M. Ichimura, H. Takegahara, 'Performance Evaluation "
                 "of Radio Frequency Plasma Cathodes for Hall Thrusters', Trans. JSASS Aerospace Tech. Japan 14 "
                 "(ists30), Pb_77-Pb_82 (2016)",
     "doi": "10.2322/tastj.14.Pb_77", "url": "https://www.jstage.jst.go.jp/article/tastj/14/ists30/14_Pb_77/_pdf",
     "access": "full text (J-STAGE publisher PDF, openly served)", "retrieved_on": RETRIEVED_ON,
     "sha256": "3165e5eec05681a63624ba6446bac78fc57956d9c6e0e231efa810064925a092",
     "device": "stand-alone RF (ICP) plasma cathodes, outer-coil (alumina vessel 40 mm ID x 80 mm, Cu coil, graphite "
               "orifice plate with 2 mm orifice, graphite ion collector) and inner-coil (Mo vessel 58 x 67 mm, W coil); "
               "diode test to a plate anode 50 mm downstream; Xe; 13.56 MHz; 1.6 m x 3.2 m chamber, ~6.3e-4 Pa at "
               "0.4 mg/s Xe",
     "establishes": [
         {"q": "saturation anode (electron) current, outer-coil", "value": 3.3, "unit": "A",
          "conditions": "RF 140 W (net, no reflection), Xe 0.3 mg/s, anode voltage 58 V", "locator": "Abstract p. Pb_77; "
          "Sec. 3.2 p. Pb_79", "value_basis": "reported"},
         {"q": "saturation current proportional to RF power; weak flow dependence", "value": None, "unit": None,
          "conditions": "outer-coil, Fig. 5", "locator": "Sec. 3.2 p. Pb_79", "value_basis": "reported"},
         {"q": "inner-coil transition from < 1 A to > 12 A with anode voltage, unstable", "value": None, "unit": None,
          "conditions": "RF 200 W, Xe 2.0 mg/s", "locator": "Sec. 4 (3) p. Pb_81; Fig. 9", "value_basis": "reported"},
         {"q": "gas utilization comparable to a dispenser hollow cathode; electron production cost four times higher",
          "value": None, "unit": None, "conditions": "vs HCN-252 hollow cathode data (2-10 A)",
          "locator": "Abstract; Sec. 3.4 p. Pb_81, Eqs. (1)-(3), Fig. 10", "value_basis": "reported"},
     ],
     "derived": [
         {"q": "gas utilization factor U_e = I_a / (0.073 A per mg/s x mdot) at the 3.3 A point",
          "formula": "3.3 / (0.073 * 0.3)", "value_fn": "watanabe_ue", "unit": "-",
          "locator": "Eq. (1) p. Pb_81 applied to the reported point"},
         {"q": "electron production cost C_e = (I_a V_a + P_rf) / I_a at the 3.3 A point",
          "formula": "(3.3 * 58 + 140) / 3.3", "value_fn": "watanabe_ce", "unit": "W/A",
          "locator": "Eq. (2) p. Pb_81 applied to the reported point"},
         {"q": "RF power per ampere at the 3.3 A point", "formula": "140 / 3.3", "value_fn": "watanabe_wpa",
          "unit": "W/A", "locator": "reported point"},
     ],
     "limits": "diode test, not coupled to a Hall thruster; Xe only; no life or restart data; orifice-type cathode "
               "(not the open-tube downstream topology of A9)",
     "relation": "same group as watanabe_2015 (IEPC-2015-194) in docs/evidence/cathode/cathode_evidence_v1.json; "
                 "same 3.3 A / 140 W / 0.3 mg/s point (likely the journal version of the conference paper - verify)"},
    {"id": "S-02", "source_id": "xu_2022_pst",
     "citation": "Z. Xu, P. Wang, Z. Hua, S. Cong, S. Yu, 'Numerical simulation and experimental research on an "
                 "inductively coupled RF plasma cathode', Plasma Sci. Technol. 24, 015404 (2022)",
     "doi": "10.1088/2058-6272/ac337a", "url": "http://pst.hfcas.ac.cn/cn/article/pdf/preview/10.1088/2058-6272/ac337a.pdf",
     "access": "full text served publicly by the journal's own website (copyright IOP/HIPS, not an open licence)",
     "retrieved_on": RETRIEVED_ON, "sha256": "084b1b175e23d2b5366700a6615c5daceccb8476db8ef9ccdb5310e0934d20e2",
     "device": "stand-alone ICP cathode: alumina chamber 40 mm ID x 76 mm, graphite orifice plate with 2 mm orifice, "
               "5 mm Cu-tube coil, graphite axial ion collector; anode target 10 mm downstream; Xe; 13.56 MHz; "
               "0.6 m x 1.2 m chamber, ~1.0e-4 Pa base",
     "establishes": [
         {"q": "extracted electron current", "value": 1.03, "unit": "A",
          "conditions": "Xe 2.766 sccm (MFC reading 2.0 sccm), RF input 270 W at 13.56 MHz, 50 V target bias",
          "locator": "Sec. 4.3 p. 8; Fig. 11", "value_basis": "reported"},
         {"q": "extracted electron current at 50 W RF", "value": 0.18, "unit": "A", "conditions": "50 V bias, "
          "same flow", "locator": "Sec. 4.3 p. 8", "value_basis": "reported"},
         {"q": "stability: constant electron current for over one hour after initial automatic matching adjustment",
          "value": None, "unit": None, "conditions": "Fig. 11 conditions", "locator": "Sec. 4.3 p. 8",
          "value_basis": "reported"},
         {"q": "RF input power mainly determines the extracted current; current approaches a limit",
          "value": None, "unit": None, "conditions": "50-300 W, 2.0-4.0 sccm reading", "locator": "Abstract; p. 8",
          "value_basis": "reported"},
     ],
     "derived": [
         {"q": "RF input power per ampere at the 1.03 A point", "formula": "270 / 1.03", "value_fn": "xu_wpa",
          "unit": "W/A", "locator": "reported point"},
     ],
     "limits": "diode test, not coupled to a Hall thruster; Xe only; one-hour stability only, no life, no restart "
               "statistics; the paper's secondary citations (Scholze 1.6 A at 0.2 sccm / 300 W; Watanabe 2.1 A at "
               "100 W / 2 sccm) are NOT used here as primary values (verify against the primary sources)"},
    {"id": "S-03", "source_id": "scholze_2008_rsi",
     "citation": "F. Scholze, M. Tartz, H. Neumann, 'Inductive coupled radio frequency plasma bridge neutralizer', "
                 "Rev. Sci. Instrum. 79, 02B724 (2008)",
     "doi": "10.1063/1.2802587", "url": "https://api.crossref.org/works/10.1063/1.2802587",
     "access": "ABSTRACT-ONLY (Crossref abstract; publisher PDF returned HTTP 403 to this agent - not bypassed)",
     "retrieved_on": RETRIEVED_ON, "sha256": None,
     "device": "13.56 MHz inductively coupled RF plasma bridge neutralizer for ion thrusters / ion-beam processing",
     "establishes": [
         {"q": "maximum extracted electron current", "value": 1.6, "unit": "A", "conditions": "not given in the "
          "abstract", "locator": "Abstract", "value_basis": "reported"},
         {"q": "no components inside the plasma, so lifetime 'expected to be very long'; electron current "
               "controllable over a wide range by RF power", "value": None, "unit": None, "conditions": "",
          "locator": "Abstract", "value_basis": "reported"},
     ],
     "derived": [],
     "limits": "abstract only; the lifetime statement is an expectation, not a life test"},
    {"id": "S-04", "source_id": "longmier_2008_rsi",
     "citation": "B. Longmier, N. Hershkowitz, 'Improved operation of the nonambipolar electron source', Rev. Sci. "
                 "Instrum. 79, 093506 (2008)",
     "doi": "10.1063/1.2979012", "url": "https://api.crossref.org/works/10.1063/1.2979012",
     "access": "ABSTRACT-ONLY (Crossref abstract)", "retrieved_on": RETRIEVED_ON, "sha256": None,
     "device": "nonambipolar electron source (NES), RF plasma electron source without cathode-surface emission",
     "establishes": [
         {"q": "continuous electron current", "value": 30, "unit": "A",
          "conditions": "2 sccm Xe, 1300 W RF at 13.56 MHz", "locator": "Abstract", "value_basis": "reported"},
         {"q": "gas utilization factor", "value": 180, "unit": "-", "conditions": "same point",
          "locator": "Abstract", "value_basis": "reported"},
         {"q": "helicon mode transition", "value": None, "unit": None,
          "conditions": "15 sccm Ar, 1000 W RF, 100 G magnetic field", "locator": "Abstract", "value_basis": "reported"},
     ],
     "derived": [
         {"q": "RF power per ampere at the 30 A point", "formula": "1300 / 30", "value_fn": "longmier_wpa",
          "unit": "W/A", "locator": "reported point"},
     ],
     "limits": "abstract only; high-power class; the device may use an applied magnetic field (100 G stated for the "
               "helicon transition) - owner answer row 69 fixes an UNMAGNETIZED first build, so magnetized data are "
               "context only"},
    {"id": "S-05", "source_id": "dietz_2020_epjap",
     "citation": "P. Dietz, F. Becker, K. Keil, K. Holste, P. J. Klar, 'Performance of a rf neutralizer operating with "
                 "noble gases and iodine', Eur. Phys. J. Appl. Phys. 91, 10901 (2020)",
     "doi": "10.1051/epjap/2020190213", "url": "https://api.crossref.org/works/10.1051/epjap/2020190213",
     "access": "ABSTRACT-ONLY (Crossref abstract; publisher PDF https://www.epjap.org/10.1051/epjap/2020190213/pdf "
               "returned HTTP 403 - not bypassed)", "retrieved_on": RETRIEVED_ON, "sha256": None,
     "device": "inductively coupled RF neutralizer, prototypical, operated on iodine, xenon and krypton; compared with "
               "global modelling",
     "establishes": [
         {"q": "an ICP RF neutralizer has been operated on a chemically reactive propellant (iodine) as well as Xe/Kr",
          "value": None, "unit": None, "conditions": "", "locator": "Abstract", "value_basis": "reported"},
         {"q": "stated requirement context: neutralizer lifetimes of the order of ten thousand hours",
          "value": None, "unit": None, "conditions": "", "locator": "Abstract", "value_basis": "reported"},
     ],
     "derived": [],
     "limits": "abstract only: no current, power, flow or life numbers available to this lane"},
    {"id": "S-06", "source_id": "watanabe_2016_aiaa",
     "citation": "H. Watanabe, M. Ichimura, H. Takegahara, 'Performance of a Hall Thruster Operating with a Radio "
                 "Frequency Plasma Cathode', 52nd AIAA/SAE/ASEE Joint Propulsion Conference, AIAA 2016-4947",
     "doi": "10.2514/6.2016-4947", "url": "https://api.crossref.org/works/10.2514/6.2016-4947",
     "access": "METADATA-ONLY (Crossref; no abstract; AIAA full text not open)", "retrieved_on": RETRIEVED_ON,
     "sha256": None, "device": "Hall thruster operated with an RF plasma cathode (title)",
     "establishes": [
         {"q": "a coupled Hall thruster + RF plasma cathode test exists in the literature (title only)", "value": None,
          "unit": None, "conditions": "", "locator": "Crossref record", "value_basis": "reported"},
     ],
     "derived": [],
     "limits": "no values used: numbers seen only in a search-engine snippet are NOT transcribed (verify on the "
               "full text); on the lawful-acquisition list"},
    {"id": "S-07", "source_id": "georgin_2023_aiaa",
     "citation": "M. P. Georgin, M. S. McDonald, J. W. Brooks, 'Theory of RF Plasma Cathodes and Supporting Experiments "
                 "for Electric Propulsion Applications', AIAA SciTech 2023 Forum, AIAA 2023-0844",
     "doi": "10.2514/6.2023-0844", "url": "https://api.crossref.org/works/10.2514/6.2023-0844",
     "access": "METADATA-ONLY (Crossref; no abstract; AIAA full text not open)", "retrieved_on": RETRIEVED_ON,
     "sha256": None, "device": "RF plasma cathode theory + experiments (title); cited by Takahashi 2024 as ref. [17]",
     "establishes": [
         {"q": "a theory of RF plasma cathodes for EP exists (title only)", "value": None, "unit": None,
          "conditions": "", "locator": "Crossref record", "value_basis": "reported"},
     ],
     "derived": [], "limits": "no values; on the lawful-acquisition list"},
    {"id": "S-08", "source_id": "scholze_2017_proeng",
     "citation": "F. Scholze, C. Eichhorn, C. Bundesmann, M. Spemann, H. Neumann, M. Bulit, D. Feili, J. G. del Amo, "
                 "'Modelling of a radio frequency plasma bridge neutralizer (RFPBN)', Procedia Engineering 185, 9-16 "
                 "(2017)",
     "doi": "10.1016/j.proeng.2017.03.284", "url": "https://api.crossref.org/works/10.1016/j.proeng.2017.03.284",
     "access": "METADATA-ONLY (Crossref lists a CC BY-NC-ND 4.0 version-of-record licence, but the ScienceDirect page "
               "returned HTTP 403 to this agent - not bypassed)", "retrieved_on": RETRIEVED_ON, "sha256": None,
     "device": "RF plasma bridge neutralizer performance model (title)",
     "establishes": [
         {"q": "a published performance model for an RF plasma bridge neutralizer exists (title only)", "value": None,
          "unit": None, "conditions": "", "locator": "Crossref record", "value_basis": "reported"},
     ],
     "derived": [], "limits": "no values; open licence, so the owner can obtain the full text lawfully"},
]

DERIVED_FNS = {
    "watanabe_ue": lambda: 3.3 / (0.073 * 0.3),
    "watanabe_ce": lambda: (3.3 * 58 + 140) / 3.3,
    "watanabe_wpa": lambda: 140 / 3.3,
    "xu_wpa": lambda: 270 / 1.03,
    "longmier_wpa": lambda: 1300 / 30,
}

REUSED_DOSSIER = [
    {"id": "D-01", "path": "docs/evidence/cathode/cathode_evidence_v1.json", "entry": "rf.i.neworbit_max / "
     "rf.p.neworbit_air / rf.flow.neworbit_air (source schwertheim_2025, IEPC-2025-378 preprint, CC BY 4.0)",
     "values": "up to 0.45 A; 90 W RF on 0.8 sccm 50:50 N2/O2 (0.018 mg/s); 25 W on 0.15 sccm Xe",
     "use": "the only atmospheric-gas (N2/O2) RF-cathode operating point in the repository; reused by reference, not "
            "re-fetched; non-peer-reviewed preprint; gridded-ion context"},
    {"id": "D-02", "path": "docs/evidence/cathode/cathode_evidence_v1.json", "entry": "rf.life.none_demonstrated, "
     "rf.recovery.none", "values": "no demonstrated life of an air-fed RF cathode; planned 300 h / 100 cycles (future "
     "work, schwertheim_2025 pdf p. 22)", "use": "confirms the life/restart gap is not closed by open literature"},
]

TOPIC_SUMMARY = {
    "electron_current_per_rf_watt": {
        "analog_points": ["TK-21/TK-52 (Takahashi: ~1 A discharge current with 200 W forward, ~20 W absorbed "
                          "(authors' estimate), Ar, coupled to a HET)", "S-01 (3.3 A at 140 W, Xe, diode)",
                          "S-02 (1.03 A at 270 W, Xe, diode)", "S-04 (30 A at 1300 W, Xe, abstract)",
                          "D-01 (0.45 A at 90 W, N2/O2, preprint)"],
        "reading": "spread of roughly an order of magnitude in W/A across devices, gases and power transfer "
                   "efficiencies; forward/net RF power is not absorbed power (Takahashi eta_p ~0.1). Context only; "
                   "no Vyovrinda value can be taken from it."},
    "gas_flow_per_ampere": {
        "analog_points": ["S-01 (0.3 mg/s Xe for 3.3 A; U_e ~150)", "S-04 (2 sccm Xe for 30 A; U_e 180)",
                          "S-02 (2.766 sccm Xe for 1.03 A)", "D-01 (0.018 mg/s N2/O2 for up to 0.45 A)",
                          "TK-31 (Takahashi: no separate ICP feed; 2.1 mg/s Ar shared with the HET)"],
        "reading": "orifice-type RF cathodes run on a dedicated low flow; the Takahashi topology re-uses Hall "
                   "exhaust, so its ICP gas share is not separable. The ICP gas feed of A9 is UNBOOKED (A9 row-46 "
                   "flag) and must be measured."},
    "lifetime_erosion": {
        "analog_points": ["TK-70/TK-71 (sputtering of the ion-collecting electrode at 140-220 eV, metallic films "
                          "on the glass tube and HET insulators)", "S-03 (lifetime 'expected' long, no test)",
                          "D-02 (no demonstrated life of an air-fed RF cathode)"],
        "reading": "no open life test of an RF/ICP neutralizer was found; the only erosion evidence for the A9 "
                   "topology is a qualitative deposition observation. Life can only come from H-1 / ICP hardware "
                   "and the separate atomic-O materials/life programme (owner answer row 132)."},
    "restart": {
        "analog_points": ["TK-73 (RF first, then V_D; no statistics)", "S-02 (one-hour stability after matching "
                          "settles)", "D-02 (100 on/off cycles planned, not reported)"],
        "reading": "no restart/cycle statistics in the open sources read; hardware only (owner answer row 24)."},
}

LAWFUL_ACQUISITION = [
    {"id": "LA-01", "item": "Watanabe, Ichimura, Takegahara, AIAA 2016-4947 (DOI 10.2514/6.2016-4947)",
     "why": "only located coupled Hall thruster + RF plasma cathode performance paper besides Takahashi 2024",
     "access_seen": "metadata only (AIAA)", "priority": "P1 (PROPOSED)"},
    {"id": "LA-02", "item": "Georgin & McDonald, IEPC-2022-100, 'Inductively Coupled Plasma Cathodes Enabling In-situ "
     "Resource Utilization for Hall Thrusters' (Takahashi ref. [24])",
     "why": "ICP cathode for Hall thrusters on ISRU (reactive) gases", "access_seen": "not located at an open URL "
     "(electricrocket.org guess returned 404)", "priority": "P1 (PROPOSED)"},
    {"id": "LA-03", "item": "Georgin, McDonald, Brooks, AIAA 2023-0844 (DOI 10.2514/6.2023-0844)",
     "why": "RF plasma cathode theory + experiments (Takahashi ref. [17])", "access_seen": "metadata only (AIAA)",
     "priority": "P1 (PROPOSED)"},
    {"id": "LA-04", "item": "Scholze, Tartz, Neumann, Rev. Sci. Instrum. 79, 02B724 (2008) (DOI 10.1063/1.2802587)",
     "why": "ICP plasma bridge neutralizer operating conditions behind the 1.6 A abstract figure",
     "access_seen": "abstract only (publisher PDF HTTP 403)", "priority": "P2 (PROPOSED)"},
    {"id": "LA-05", "item": "Longmier & Hershkowitz, Rev. Sci. Instrum. 79, 093506 (2008) (DOI 10.1063/1.2979012)",
     "why": "magnetized/unmagnetized operating conditions of the NES 30 A point", "access_seen": "abstract only",
     "priority": "P3 (PROPOSED)"},
    {"id": "LA-06", "item": "Dietz et al., Eur. Phys. J. Appl. Phys. 91, 10901 (2020) (DOI 10.1051/epjap/2020190213)",
     "why": "ICP neutralizer on a reactive propellant (iodine): current, power, flow values",
     "access_seen": "abstract only (publisher PDF HTTP 403)", "priority": "P2 (PROPOSED)"},
    {"id": "LA-07", "item": "Scholze et al., Procedia Engineering 185, 9-16 (2017) (DOI 10.1016/j.proeng.2017.03.284)",
     "why": "RF plasma bridge neutralizer performance model", "access_seen": "metadata only; Crossref lists CC BY-NC-ND "
     "4.0 (ScienceDirect HTTP 403 to this agent)", "priority": "P2 (PROPOSED)"},
    {"id": "LA-08", "item": "H. Watanabe, Vacuum 167, 514-519 (2019) (DOI 10.1016/j.vacuum.2018.06.030), 'Effect of "
     "vessel diameter on ignition and electron emission characteristics in radio frequency plasma cathodes'",
     "why": "ignition vs vessel diameter (startup/restart input)", "access_seen": "metadata only (Crossref)",
     "priority": "P2 (PROPOSED)"},
    {"id": "LA-09", "item": "K. Takahashi, Rev. Sci. Instrum. 83, 083508 (2012) (DOI as cited in Takahashi 2024 ref. "
     "[21]: 10.1063/1.4748271), antenna for suppression of parasitic discharges",
     "why": "antenna shielding design used in the A9 anchor topology", "access_seen": "not accessed (DOI from the "
     "reference list of the anchor - verify)", "priority": "P3 (PROPOSED)"},
]


def build():
    pix = _load(PIXELS)
    if pix["source_pdf_sha256"] != ANCHOR["retrieval"]["sha256"]:
        raise RuntimeError("pixel record does not come from the pinned anchor PDF")
    extraction = []
    for (i, grp, q, val, unit, loc, basis, epi, note) in EXTRACTION:
        extraction.append({"id": i, "group": grp, "quantity": q, "value": val, "unit": unit, "locator": loc,
                           "value_basis": basis, "epistemic": epi,
                           "evidence_class": "published analog" if basis != "not_reported" else "not reported",
                           "note": note})
    survey = []
    for s in SURVEY:
        s2 = dict(s)
        s2["derived"] = [dict(d, value=_r(DERIVED_FNS[d["value_fn"]](), 1), value_basis="derived",
                              epistemic="inferred") for d in s["derived"]]
        for d in s2["derived"]:
            del d["value_fn"]
        s2["evidence_class"] = "published analog (not Vyovrinda hardware)"
        survey.append(s2)
    fig4 = digitized_fig4(pix)
    id_vals = [r["ID_A"] for r in fig4 if r.get("ID_A") is not None]
    ratios = [
        {"id": "TK-R1", "quantity": "largest digitized I_D per forward RF watt (Takahashi, Ar, coupled HET)",
         "value": _r(max(id_vals) / 200.0, 4), "unit": "A/W",
         "formula": "max(digitized I_D) / 200 W forward (TK-21)", "value_basis": "derived", "epistemic": "inferred"},
        {"id": "TK-R2", "quantity": "largest digitized I_D per absorbed RF watt using the authors' ~20 W estimate",
         "value": _r(max(id_vals) / 20.0, 3), "unit": "A/W",
         "formula": "max(digitized I_D) / 20 W (TK-27, authors' estimate)", "value_basis": "derived",
         "epistemic": "inferred"},
    ]
    doc = {
        "schema": "icp_neutralizer_evidence_v1",
        "title": "Downstream RF-ICP neutralizer - published-analog evidence extraction (A9-05 part 1)",
        "lane": LANE, "trigger": TRIGGER, "status": "DRAFT_FOR_OWNER_REVIEW", "base_commit": BASE_COMMIT,
        "generated_by": REL + "/build_icp_neutralizer_evidence.py (--check reproduces JSON and MD exactly)",
        "authority_pins": AUTHORITY_PINS, "deliverable_pins": DELIVERABLE_PINS,
        "governance_read_never_pinned": GOVERNANCE_NOT_PINNED,
        "configuration_ids": CONFIG_IDS,
        "what_this_is_not": [
            "not a performance prediction for Vyovrinda hardware (H-1, C1 or the A9 ICP module): every value is a "
            "published analog on different geometry, gas and facility",
            "not a use of any Hall transport closure (credible set EMPTY), of abep_sim/plasma_devices.py or of the "
            "withdrawn v1.2-v1.6 numbers",
            "not a winner declaration between hall_c1_reference and hall_icp_neutralizer; not a change of Bundle 1 "
            "(NO_BASELINE_YET) or of P5-N2 v1 (INCONCLUSIVE)",
            "not a numeric threshold: no margin, effect size or stop-rule number is set here",
        ],
        "anchor": ANCHOR,
        "pixel_record": {"path": REL + "/takahashi2024_fig_pixels_v1.json", "sha256": _sha(PIXELS),
                         "regenerate": "python " + REL + "/digitize_takahashi2024.py --pdf <anchor PDF> --write",
                         "reading_uncertainty_px": {"unoccluded": READ_PX, "occluded": OCCL_PX}},
        "extraction": extraction,
        "geometry_fig2": geometry_fig2(pix),
        "digitized_fig4": {
            "locator": "Fig. 4a/4b (PDF p. 7)", "value_basis": "digitized", "epistemic": "digitized",
            "evidence_class": "published analog",
            "columns": {"VD_nominal_V": "printed V_D grid", "ID_A": "discharge current (Fig. 4b, right axis)",
                        "VK_V": "ion-collector potential (Fig. 4a)", "Vmax_V": "max ion potential from RFEA (Fig. 4a)",
                        "Ic60_arb": "RFEA collector current at V_G3 = 60 V (Fig. 4b, left axis, arb. units)",
                        "*_errbar_half": "half-length of the printed error bar (several repeated shots)",
                        "VD_x_ID_W": "this lane's product V_D x I_D (supply-side power incl. the 50 ohm resistor; "
                                     "NOT a Hall discharge power reported by the authors)",
                        "ID2_x_50ohm_W": "this lane's I_D^2 x 50 ohm (series-resistor dissipation)",
                        "VD_minus_ID_x_50ohm_V": "this lane's V_D - I_D x 50 ohm (voltage left across anode-"
                                                 "collector)"},
            "rows": fig4},
        "derived_ratios": ratios,
        "stated_limitations": [{"id": i, "text": t, "locator": l} for i, t, l in LIMITATIONS],
        "survey": {"bound": "max ~8 primary sources (task scope); 8 used", "sources": survey,
                   "reused_from_repository": REUSED_DOSSIER, "by_topic": TOPIC_SUMMARY},
        "lawful_acquisition_list": {"owner_answer_row": 7, "items": LAWFUL_ACQUISITION,
                                    "note": "priorities are PROPOSED; acquisition is an owner action outside the "
                                            "repository (A9 owner_actions_outside_the_repository)"},
        "analog_can_bound_vs_hardware_only": {
            "analog_can_bound": ["existence of the topology (Hall discharge sustained by electrons from a downstream "
                                 "ICP, Ar)", "order of magnitude of RF watts per extracted ampere across RF cathodes",
                                 "presence of a cathodic-sheath sputtering / deposition mechanism",
                                 "measurement methods (R_ant / R_total eta_p method, RFEA, directional coupler)"],
            "hardware_only": ["electron-current capacity and neutralization margin of the Vyovrinda ICP module with "
                              "H-1", "Hall current demand of H-1", "absorbed RF power and eta_p of the A9 module",
                              "N2 and O2-bearing operation (no analog data for the A9 topology)",
                              "thrust, P_bus, restart statistics, erosion rates and life"]},
        "owner_answers_applied": [
            {"row": 7, "how": "Takahashi 2024 full text read (open access) and pinned by sha256; primary RF-cathode "
                              "papers surveyed; lawful-acquisition list LA-01..LA-09 produced; no bypass, no author "
                              "contact (data-availability request NOT made)"},
            {"row": 36, "how": "Takahashi Ar data are labelled engineering-topology precedent; they never count "
                               "toward DRDO atmospheric requirements"},
            {"row": 69, "how": "magnetized-source analog data (S-04 helicon mode) marked context-only against the "
                               "UNMAGNETIZED first build"},
            {"row": 70, "how": "TK-40 records that the anchor's ion collector floats at the negative end of V_D with "
                               "no separate bias; A9 requires a floating body and separately controlled collector "
                               "bias - the analog circuit is NOT the A9 circuit"},
            {"row": 72, "how": "analog RF chains (13.56 MHz, forward/reflected via generator meters, R_ant method) "
                               "recorded as measurement-method precedent for the 0-500 W lab chain"},
            {"row": 132, "how": "no analog life data exist; life/erosion routed to hardware and the separate "
                                "atomic-O programme"},
            {"row": 145, "how": "this extraction feeds the new Hall->ICP validation-input list "
                                "(docs/experiments/hall_icp/validation_inputs/)"},
            {"row": 146, "how": "no screening or hypothesis values are manufactured from the analog"},
        ],
        "interface_demands": [
            {"id": "EV-IF-01", "direction": "to", "to": "A9-05 part 2 docs/experiments/hall_icp/validation_inputs/",
             "what": "analog bounds per validation input (extraction ids)", "units": "per item",
             "status": "DELIVERED (this lane)"},
            {"id": "EV-IF-02", "direction": "to", "to": "A9-03 docs/interfaces/icp_neutralizer/",
             "what": "anchor geometry (TK-10..TK-14, TK-G1..TK-G10) and circuit (TK-40) as topology precedent; the "
                     "anchor circuit differs from the A9 floating-body + separately biased collector (row 70)",
             "units": "mm, cm, ohm", "status": "OFFERED (read-only; A9-03 decides use)"},
            {"id": "EV-IF-03", "direction": "to", "to": "A9-04 docs/experiments/hall_icp/uncertainty_budget/",
             "what": "measurement-method precedent: eta_p from R_ant/R_total (Eq. 1), directional-coupler "
                     "forward/reflected, RFEA I_c60 metric", "units": "ohm, W, A", "status": "OFFERED"},
            {"id": "EV-IF-04", "direction": "from", "to": "owner",
             "what": "lawful acquisition of LA-01..LA-09 (row 7)", "units": "-", "status": "OPEN (owner action)"},
        ],
        "open_owner_questions": [
            {"id": "OQ-EV-01", "question": "Authorize a formal data request to the Takahashi 2024 corresponding "
                                           "author (the paper offers data 'upon reasonable request')?",
             "proposed_answer": "NO - standing rule: no contact with authors/labs; digitized values suffice for a "
                                "topology precedent", "status": "owner call"},
            {"id": "OQ-EV-02", "question": "Acquisition priority for LA-01..LA-09",
             "proposed_answer": "P1: LA-01, LA-02, LA-03 (coupled Hall + RF-cathode data); P2: LA-04, LA-06, LA-07, "
                                "LA-08; P3: LA-05, LA-09", "status": "owner call"},
        ],
        "historical_reuse": [
            {"path": "docs/evidence/cathode/cathode_evidence_v1.json",
             "sha256": "050060204e443d5583c307becadaab55a9f213d406ff4454be856bca21249110",
             "reused": "rf_plasma_cathode entries (watanabe_2015, schwertheim_2025) by reference (D-01, D-02)",
             "not_reused": "the dossier's 'not baseline' status statement (A9 changes the role of the ICP; the "
                           "dossier stays byte-identical)"},
            {"path": "docs/experiments/instrumentation/instrumentation_definition_v1.json",
             "sha256": "7c6d37b00f38a44cded73d92d4366739eacbf013e73e98a7bfbc3fa5a5470d96",
             "reused": "INS-03 (net RF at the load plane), INS-14 (RPA) as the method names the analog maps onto",
             "not_reused": "DQ-RARCH (rf_hall / hall_only ratio; superseded for the primary line, row 28)"},
        ],
        "m16_impact": [
            {"m16_row": 11, "subsystem": "shielded Xe-fed LaB6 hollow cathode",
             "how": "evidence only: the RF-cathode analog set now sits beside the C1 dossier; C1 stays reference/"
                    "fallback (row 88); no change to the M16 file"},
            {"m16_row": 17, "subsystem": "RF pre-ionization module interface",
             "how": "the anchor topology supports re-scoping this row to the downstream ICP neutralizer (A9); "
                    "re-scoping is for the M16 owner lane (A9-10), not done here"},
        ],
        "h3_h4_inputs": {
            "h3_procurement_rfq": ["13.56 MHz generator with forward/reflected metering (anchor: 200 W class; owner "
                                   "row 72: size 0-500 W)", "two-variable-capacitor matching network (anchor TK-23)",
                                   "high-frequency antenna current sensor (anchor R_ant method, TK-24)",
                                   "isolation transformer / isolated supply and series protection (anchor TK-40)",
                                   "RFEA (anchor TK-57)"],
            "h4_measurement": ["reproduce 'no Hall discharge without ICP electrons' on Ar as an engineering-only "
                               "topology check (TK-51) - criterion PENDING A9-01 preregistration",
                               "witness coupons for sputter deposition on the ICP tube and H-1 exit insulators "
                               "(TK-71)"]},
    }
    return doc


def render_md(doc):
    L = []
    a = L.append
    a("# Downstream RF-ICP neutralizer - published-analog evidence (A9-05 part 1)")
    a("")
    a("| | |")
    a("|---|---|")
    a("| lane | `%s` (trigger `%s`) |" % (doc["lane"], doc["trigger"]))
    a("| status | **%s** |" % doc["status"])
    a("| generated by | `%s` |" % doc["generated_by"])
    a("| machine-readable | `%s/icp_neutralizer_evidence_v1.json` |" % REL)
    a("| base commit | `%s` |" % doc["base_commit"])
    a("| configuration ids | %s |" % ", ".join("`%s`" % c for c in doc["configuration_ids"]))
    a("")
    a("**Authority pins (sha256, verified at build):**")
    a("")
    for p in doc["authority_pins"] + doc["deliverable_pins"]:
        a("- `%s` - `%s` (%s)" % (p["path"], p["sha256"], p["role"]))
    a("")
    a("Read but never pinned (mutable governance): " + "; ".join("`%s`" % g for g in doc["governance_read_never_pinned"]))
    a("")
    a("**What this is not:**")
    a("")
    for w in doc["what_this_is_not"]:
        a("- " + w)
    a("")
    an = doc["anchor"]
    a("## 1. Anchor source")
    a("")
    a("- %s" % an["citation"])
    a("- DOI `%s`; licence %s; %s" % (an["doi"], an["license"], an["access"]))
    r = an["retrieval"]
    a("- retrieved %s from %s (HTTP %d, %s, %d bytes, %d pages); sha256 `%s`" % (
        r["retrieved_on"], r["url"], r["http_status"], r["content_type"], r["bytes"], r["pages"], r["sha256"]))
    a("- " + an["redistribution"])
    a("- data availability: " + an["data_availability_statement"])
    a("- evidence class: **%s**" % an["evidence_class"])
    a("")
    a("## 2. Extraction (reported values, page/figure locators)")
    a("")
    a("| id | group | quantity | value | unit | locator | basis | epistemic | note |")
    a("|---|---|---|---|---|---|---|---|---|")
    for e in doc["extraction"]:
        v = "not reported" if e["value"] is None else e["value"]
        a("| %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (e["id"], e["group"], e["quantity"], v, e["unit"] or "-",
                                                             e["locator"], e["value_basis"], e["epistemic"] or "-",
                                                             e["note"] or ""))
    a("")
    a("## 3. Digitized geometry (Fig. 2)")
    a("")
    a("Pixel record `%s` (sha256 `%s`); regenerate with `%s`." % (doc["pixel_record"]["path"],
                                                                  doc["pixel_record"]["sha256"],
                                                                  doc["pixel_record"]["regenerate"]))
    a("")
    a("| id | quantity | value | unit | reading u | basis | note |")
    a("|---|---|---|---|---|---|---|")
    for g in doc["geometry_fig2"]:
        a("| %s | %s | %s | %s | +/-%s | %s | %s |" % (g["id"], g["quantity"], g["value"], g["unit"], g["reading_u"],
                                                       g["value_basis"], g["note"]))
    a("")
    a("## 4. Digitized Fig. 4 series (published analog, Ar)")
    a("")
    d4 = doc["digitized_fig4"]
    for k, v in d4["columns"].items():
        a("- `%s`: %s" % (k, v))
    a("")
    cols = ["VD_nominal_V", "ID_A", "ID_reading_u_A", "ID_occluded", "VK_V", "Vmax_V", "Vmax_V_errbar_half",
            "Ic60_arb", "Ic60_arb_errbar_half", "VD_x_ID_W", "ID2_x_50ohm_W", "VD_minus_ID_x_50ohm_V"]
    a("| " + " | ".join(cols) + " |")
    a("|" + "---|" * len(cols))
    for row in d4["rows"]:
        a("| " + " | ".join("-" if row.get(c) is None else str(row.get(c)) for c in cols) + " |")
    a("")
    a("Derived ratios (this lane's arithmetic, analog only):")
    a("")
    for r_ in doc["derived_ratios"]:
        a("- %s `%s`: %s %s (%s)" % (r_["id"], r_["quantity"], r_["value"], r_["unit"], r_["formula"]))
    a("")
    a("## 5. Limitations stated by the authors")
    a("")
    for l_ in doc["stated_limitations"]:
        a("- %s: %s (%s)" % (l_["id"], l_["text"], l_["locator"]))
    a("")
    a("## 6. Bounded open-literature survey (%s)" % doc["survey"]["bound"])
    a("")
    for s in doc["survey"]["sources"]:
        a("### %s `%s`" % (s["id"], s["source_id"]))
        a("")
        a("- %s; DOI `%s`" % (s["citation"], s["doi"]))
        a("- access: **%s**; URL %s; retrieved %s%s" % (s["access"], s["url"], s["retrieved_on"],
                                                        "; sha256 `%s`" % s["sha256"] if s["sha256"] else ""))
        a("- device: %s" % s["device"])
        for e in s["establishes"]:
            val = "" if e["value"] is None else " = %s %s" % (e["value"], e["unit"] or "")
            a("- establishes: %s%s%s (%s; %s)" % (e["q"], val, (" [" + e["conditions"] + "]") if e["conditions"] else "",
                                                  e["locator"], e["value_basis"]))
        for d in s["derived"]:
            a("- derived (this lane): %s = %s %s (`%s`; %s)" % (d["q"], d["value"], d["unit"], d["formula"],
                                                                 d["locator"]))
        a("- limits: %s" % s["limits"])
        if s.get("relation"):
            a("- relation: %s" % s["relation"])
        a("")
    a("Reused from the repository (by reference, not re-fetched):")
    a("")
    for d in doc["survey"]["reused_from_repository"]:
        a("- %s `%s` %s: %s - %s" % (d["id"], d["path"], d["entry"], d["values"], d["use"]))
    a("")
    a("### Survey by topic")
    a("")
    for k, v in doc["survey"]["by_topic"].items():
        a("- **%s**: %s Points: %s" % (k, v["reading"], "; ".join(v["analog_points"])))
    a("")
    a("## 7. Lawful-acquisition list (owner answer row %d)" % doc["lawful_acquisition_list"]["owner_answer_row"])
    a("")
    a("| id | item | why | access seen | priority |")
    a("|---|---|---|---|---|")
    for x in doc["lawful_acquisition_list"]["items"]:
        a("| %s | %s | %s | %s | %s |" % (x["id"], x["item"], x["why"], x["access_seen"], x["priority"]))
    a("")
    a(doc["lawful_acquisition_list"]["note"])
    a("")
    a("## 8. What the analog can bound vs what only hardware can supply")
    a("")
    ab = doc["analog_can_bound_vs_hardware_only"]
    a("- analog can bound: " + "; ".join(ab["analog_can_bound"]))
    a("- hardware only: " + "; ".join(ab["hardware_only"]))
    a("")
    a("## 9. Owner answers applied")
    a("")
    for o in doc["owner_answers_applied"]:
        a("- row %d: %s" % (o["row"], o["how"]))
    a("")
    a("## 10. Interface demands")
    a("")
    a("| id | direction | counterpart | what | units | status |")
    a("|---|---|---|---|---|---|")
    for i in doc["interface_demands"]:
        a("| %s | %s | %s | %s | %s | %s |" % (i["id"], i["direction"], i["to"], i["what"], i["units"], i["status"]))
    a("")
    a("## 11. Open owner questions (new)")
    a("")
    for q in doc["open_owner_questions"]:
        a("- %s: %s - proposed: %s (%s)" % (q["id"], q["question"], q["proposed_answer"], q["status"]))
    a("")
    a("## 12. Historical reuse")
    a("")
    for h in doc["historical_reuse"]:
        a("- `%s` (`%s`): reused %s; not reused: %s" % (h["path"], h["sha256"], h["reused"], h["not_reused"]))
    a("")
    a("## 13. M16 impact")
    a("")
    for m in doc["m16_impact"]:
        a("- row %d (%s): %s" % (m["m16_row"], m["subsystem"], m["how"]))
    a("")
    a("## 14. H3 / H4 inputs")
    a("")
    for k, v in doc["h3_h4_inputs"].items():
        a("- **%s**: %s" % (k, "; ".join(v)))
    a("")
    return "\n".join(L)


def outputs():
    doc = build()
    return (json.dumps(doc, indent=1, ensure_ascii=False) + "\n", render_md(doc))


def verify_pins():
    bad = []
    for p in AUTHORITY_PINS + DELIVERABLE_PINS:
        fp = os.path.join(ROOT, p["path"])
        if not os.path.exists(fp) or _sha(fp) != p["sha256"]:
            bad.append(p["path"])
    return bad


def check():
    j, m = outputs()
    diffs = []
    for path, txt in ((JSON_OUT, j), (MD_OUT, m)):
        if not os.path.exists(path):
            diffs.append(path + " missing")
            continue
        with open(path, encoding="utf-8") as f:
            if f.read() != txt:
                diffs.append(path + " differs")
    return diffs


def main(argv):
    bad = verify_pins()
    if bad:
        print("PIN MISMATCH:", bad)
        return 2
    if "--check" in argv:
        d = check()
        print("OK" if not d else "\n".join(d))
        return 0 if not d else 1
    j, m = outputs()
    with open(JSON_OUT, "w", encoding="utf-8") as f:
        f.write(j)
    with open(MD_OUT, "w", encoding="utf-8") as f:
        f.write(m)
    print("wrote", JSON_OUT, MD_OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
