"""Build the O2 DRAFT rate tables transcribed from SONG2026 (fo_o_o2_chemistry_v0, W7 of od_hardware_pivot).

Source: M.-Y. Song, H. Cho, G. P. Karwasz, V. Kokoouline, J. Tennyson and K. Bartschat, "Cross Sections for Electron
Collisions with Molecular and Atomic Oxygen", J. Phys. Chem. Ref. Data 55, 013102 (2026), doi:10.1063/5.0287254.
Read from the accepted manuscript ("Revised 26 November 2025") on UCL Discovery,
https://discovery.ucl.ac.uk/id/eprint/10222954/1/JPCRD25-AR-00038-revised.pdf, fetched 2026-09-27,
sha256 32d163a3af584ce48b672a4dd49d3eafa182ae234161773b1e9fa44376d9f88b (identical to the copy audited by lane 13,
docs/chemistry/o_o2/o_o2_source_matrix_v1.json). The PDF is not committed. The version of record and the supplementary
datasets were NOT accessed: every transcribed value must be re-checked against the version of record before promotion
(precondition 1 of o_o2_completeness_prereg_DRAFT.json).

Extraction: numeric tables transcribed by hand from `pdftotext -layout` output (no figure digitization), then
cross-checked (i) against a second text extraction (PyMuPDF, printed by --verify-pdf PATH) and (ii) for Table VII by the
row sum of partials vs the printed total (printed on every build).

Tables (all DRAFT, unused by any campaign; see manifest_song2026_v0.json for per-table metadata):
  ionization_O2_song2026.dat                         e + O2 -> O2+ + 2e          Table VII col. O2+        (5 %)
  dissociative_ionization_O2_upper_song2026.dat      e + O2 -> O+ + O + 2e       Table VII col. O+ (+O2^2+) (7 %)
  dissociative_ionization_O2_lower_song2026.dat      same, column / 1.1 (statement-derived O2^2+ removal, see below)
  dissociative_ionization_O2_to_O_Z2plus_song2026.dat e + O2 -> O^2+ + O + 3e    Table VII col. O^2+       (10 %)
  dissociation_O2_song2026.dat                       e + O2 -> O + O + e         Table VI (Cosby 1993)     (+-35 %)
  elastic_O2_song2026.dat                            e + O2 momentum transfer    Table V                   (see meta)
  attachment_O2_song2026.dat                         e + O2 -> O- + O            Table VIII (Rapp & Briglia 1965) (<= 20 %)

Energies used for headers / thresholds (each cited; derived sums are labelled inferred):
  12.2 eV   O2 ionization threshold to O2+(X), SONG2026 Sec. II.H (text layer prints "X 2Pi_u"; conventionally X2Pi_g; verify)
  5.12 eV   O2 dissociation energy, SONG2026 Sec. II.G
  13.618 eV O ionization energy, Itikawa & Ichimura, JPCRD 19, 637 (1990), Table 2.1 (NIST reprint
            https://srd.nist.gov/jpcrdreprint/1.555857.pdf, sha256 299e5a24...; SONG2026 Sec. III.D gives 13.62 eV)
  48.77 eV  O^2+(3P) above O ground state, Itikawa & Ichimura 1990 Table 2.1 (OCR text layer of a scanned reprint; verify)
  1.967 eV  O(1D) excitation energy, Itikawa & Ichimura 1990 Table 2.1 (used only for the dissociation energy-loss range)
  18.738 eV = 5.12 + 13.618: thermochemical minimum for O+(4S) + O(3P) from O2 (inferred; not a measured appearance energy)
  53.888 eV = 5.12 + 48.77:  thermochemical minimum for O^2+ + O from O2 (inferred)

Choices (explicit; PROPOSED where not decided by the owner):
  * O2+ and O2 dissociation: sigma = 0 below the first tabulated point (13.0 / 13.5 eV); no threshold curve constructed
    (same convention as ionization_N2_song2023.dat / dissociation_N2.dat).
  * Dissociative ionization (both O+ and O^2+ channels): linear ramp from 0 at the inferred thermochemical minimum to the
    first tabulated point, mirroring the owner-decided N2 DI convention (abep-n2n-0.4); PROPOSED for O2. The
    'table' (sigma = 0 below the first point) and 'envelope' (first value held down to the minimum) bounds are printed.
  * O+ / O2^2+ ambiguity (same m/q): SONG2026 "unable to recommend" O2^2+ values; it states that at 100 eV the separately
    measured O2^2+ yield "amounts to roughly 10 % of the O+ signal". upper = column as published; lower = column / 1.1,
    i.e. that single-energy statement applied at every energy (statement-derived, approximate; a bound, not physics).
    The double-dissociative channel O+ + O+ (two ions per event) is also inside this column and is NOT separated
    (Tian & Vidal 1998 paywalled; SONG2026 Fig. 16 is figure-only) - unresolved.
  * Table V row printed "0.008 eV | 2.30" between 0.060 and 0.090 eV is out of order in the manuscript. It is OMITTED
    (nominal), not re-interpreted as 0.080 eV; the rate effect of the 0.080 eV reading is printed (it lies far below
    the proposed domain T_e >= 2 eV / the low-energy window T_e >= 0.2 eV).
  * Held tail ("hold") beyond the last point for all but attachment; attachment uses a ZERO tail beyond 9.9 eV (the
    resonance table ends at 3.51e-20 cm^2; holding it to 10 keV would invent a plateau). The hold-vs-zero share is
    recorded either way.
  * Dissociation header 5.12 eV = the O(3P)+O(3P) minimum sink; O(1D)+O(3P) = 7.087 eV is the channel Cosby assigns to
    the B, B', 2 3Pi_u states. A single representative loss would need an owner decision (OD-4); the range
    5.12-7.087 eV is recorded as model uncertainty on the energy loss. The table is Cosby's channel-summed total above
    13.5 eV ONLY: dissociation through the Herzberg (about 5-7 eV) and Schumann-Runge (about 7-9.5 eV) states below
    13.5 eV is MISSING, and above 13.5 eV it would double-count with any dissociative-excitation table (CC-4 / OD-4).
Usage:
  python docs/chemistry/o_o2/v0/build_tables_song2026.py            # build tables + manifest
  python docs/chemistry/o_o2/v0/build_tables_song2026.py --check    # rebuild in a temp dir, byte-compare (exit 1 on diff)
  python docs/chemistry/o_o2/v0/build_tables_song2026.py --verify-pdf song2026.pdf   # token cross-check (needs PyMuPDF)
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from o_o2_v0_common import maxwellian_rate, run, sha256_file  # noqa: E402

DOC = {
    "key": "SONG2026",
    "citation": ("M.-Y. Song, H. Cho, G. P. Karwasz, V. Kokoouline, J. Tennyson and K. Bartschat, 'Cross Sections for "
                 "Electron Collisions with Molecular and Atomic Oxygen', J. Phys. Chem. Ref. Data 55, 013102 (2026)"),
    "doi": "10.1063/5.0287254",
    "url_accessed": "https://discovery.ucl.ac.uk/id/eprint/10222954/1/JPCRD25-AR-00038-revised.pdf",
    "accessed": "2026-09-27",
    "document_sha256": "32d163a3af584ce48b672a4dd49d3eafa182ae234161773b1e9fa44376d9f88b",
    "document_version": "accepted manuscript 'Revised 26 November 2025'; version of record and supplement NOT accessed",
    "access": "open (accepted manuscript); no paywall bypass",
}
II1990 = {
    "key": "II1990",
    "citation": "Y. Itikawa and A. Ichimura, J. Phys. Chem. Ref. Data 19, 637-651 (1990), Table 2.1",
    "doi": "10.1063/1.555857",
    "url_accessed": "https://srd.nist.gov/jpcrdreprint/1.555857.pdf",
    "document_sha256": "299e5a24f5309d22c7383523088525cb56c017e5f6352afee6a076f2462c5f25",
}
M2_PER_1E16CM2 = 1e-20

E_IZ_O2 = 12.2                 # SONG2026 Sec. II.H
D0_O2 = 5.12                   # SONG2026 Sec. II.G
IE_O = 13.618                  # II1990 Table 2.1
E_O2PLUS_FROM_O = 48.77        # II1990 Table 2.1 (O^2+ 3P above O ground; OCR text layer, verify)
E_O1D = 1.967                  # II1990 Table 2.1
E_TH_DI = round(D0_O2 + IE_O, 3)              # 18.738 eV, inferred
E_TH_DI2 = round(D0_O2 + E_O2PLUS_FROM_O, 3)  # 53.888 eV, inferred
O2PP_OVER_OPLUS_AT_100EV = 0.10               # SONG2026 Sec. II.H: "roughly 10 % of the O+ signal" (at 100 eV)

# SONG2026 Table V: electron energy [eV], O2 elastic MTCS [1e-16 cm^2]. The manuscript row "0.008 | 2.30" (printed
# between 0.060 and 0.090) is kept separately in TABLE_V_OUT_OF_ORDER_ROW and omitted from the nominal table.
TABLE_V = [
    (0.001, 0.35), (0.002, 0.35), (0.003, 0.40), (0.005, 0.50), (0.007, 0.59), (0.010, 0.70), (0.012, 0.77),
    (0.015, 0.87), (0.020, 1.01), (0.025, 1.15), (0.030, 1.27), (0.040, 1.49), (0.050, 1.70), (0.060, 1.88),
    (0.090, 2.50), (0.10, 2.68), (0.12, 3.00), (0.15, 3.36), (0.20, 3.90), (0.25, 4.40), (0.30, 4.90), (0.33, 5.15),
    (0.37, 5.46), (0.40, 5.62), (0.50, 6.06), (0.54, 6.18), (0.57, 6.26), (0.60, 6.34), (0.71, 6.56), (0.80, 6.68),
    (1.0, 6.70), (2.0, 6.50), (3.0, 6.10), (4.0, 6.00), (5.0, 5.70), (7.0, 6.22), (10, 6.72), (20, 7.01), (30, 6.00),
    (40, 4.50), (50, 3.50), (70, 2.50), (100, 1.50), (150, 0.95), (200, 0.62), (300, 0.45), (400, 0.37), (500, 0.26),
    (1000, 0.10)]
TABLE_V_OUT_OF_ORDER_ROW = (0.008, 2.30)

# SONG2026 Table VI (data of Cosby 1993): electron energy [eV], dissociation into neutrals [1e-16 cm^2]; +-35 %.
TABLE_VI = [(13.5, 0.220), (18.5, 0.529), (21.0, 0.565), (23.5, 0.525), (28.5, 0.587), (33.5, 0.663), (38.5, 0.610),
            (48.5, 0.534), (58.5, 0.444), (73.5, 0.366), (98.5, 0.331), (148.5, 0.296), (198.5, 0.291)]

# SONG2026 Table VII (Lindsay & Mangan evaluation): E [eV], sigma(O2+), sigma(O+ (+O2^2+)), sigma(O^2+), total
# [1e-16 cm^2]; blank cells = None (no value printed).
TABLE_VII = [
    (13.0, 0.0117, None, None, 0.0117), (15.5, 0.0730, None, None, 0.0730), (18.0, 0.164, None, None, 0.164),
    (23, 0.366, 0.0167, None, 0.383), (28, 0.563, 0.0781, None, 0.641), (33, 0.758, 0.169, None, 0.927),
    (38, 0.929, 0.258, None, 1.19), (43, 1.08, 0.333, None, 1.42), (48, 1.19, 0.419, None, 1.61),
    (53, 1.29, 0.490, None, 1.78), (58, 1.36, 0.553, None, 1.91), (63, 1.42, 0.621, None, 2.04),
    (68, 1.47, 0.679, None, 2.15), (73, 1.50, 0.717, 0.00118, 2.22), (78, 1.51, 0.751, 0.00189, 2.26),
    (83, 1.53, 0.801, 0.00241, 2.34), (88, 1.55, 0.827, 0.00352, 2.38), (93, 1.56, 0.855, 0.00438, 2.42),
    (98, 1.56, 0.871, 0.00610, 2.43), (108, 1.54, 0.900, 0.00808, 2.45), (118, 1.53, 0.910, 0.00956, 2.45),
    (138, 1.50, 0.913, 0.0137, 2.42), (158, 1.48, 0.905, 0.0180, 2.40), (178, 1.43, 0.891, 0.0200, 2.34),
    (198, 1.39, 0.864, 0.0211, 2.28), (223, 1.34, 0.830, 0.0230, 2.19), (248, 1.31, 0.794, 0.0226, 2.12),
    (273, 1.24, 0.755, 0.0213, 2.01), (298, 1.20, 0.721, 0.0207, 1.94), (348, 1.13, 0.659, 0.0189, 1.80),
    (398, 1.05, 0.611, 0.0171, 1.68), (448, 0.983, 0.562, 0.0153, 1.56), (498, 0.923, 0.526, 0.0136, 1.46),
    (548, 0.882, 0.487, 0.0123, 1.38), (598, 0.827, 0.457, 0.0111, 1.30), (648, 0.800, 0.432, 0.0108, 1.24),
    (698, 0.761, 0.415, 0.00987, 1.19), (748, 0.720, 0.388, 0.00977, 1.12), (798, 0.686, 0.369, 0.00837, 1.06),
    (848, 0.671, 0.355, 0.00799, 1.03), (898, 0.643, 0.336, 0.00770, 0.987), (948, 0.617, 0.326, 0.00740, 0.950),
    (998, 0.597, 0.317, 0.00743, 0.922)]

# SONG2026 Table VIII (data of Rapp & Briglia 1965): E [eV], DEA cross section [1e-16 cm^2]; "no more than 20 %".
# The manuscript prints no 6.4 eV and no 9.7 eV row; linear interpolation spans both gaps.
TABLE_VIII = [
    (4.2, 0.0), (4.3, 8.79e-05), (4.4, 2.64e-04), (4.5, 4.39e-04), (4.6, 7.03e-04), (4.7, 9.67e-04), (4.8, 1.32e-03),
    (4.9, 1.76e-03), (5.0, 2.20e-03), (5.1, 2.90e-03), (5.2, 3.60e-03), (5.3, 4.48e-03), (5.4, 5.36e-03),
    (5.5, 6.33e-03), (5.6, 7.47e-03), (5.7, 8.52e-03), (5.8, 9.58e-03), (5.9, 1.05e-02), (6.0, 1.14e-02),
    (6.1, 1.23e-02), (6.2, 1.31e-02), (6.3, 1.36e-02), (6.5, 1.41e-02), (6.6, 1.40e-02), (6.7, 1.37e-02),
    (6.8, 1.34e-02), (6.9, 1.28e-02), (7.0, 1.22e-02), (7.1, 1.14e-02), (7.2, 1.06e-02), (7.3, 9.84e-03),
    (7.4, 8.96e-03), (7.5, 8.17e-03), (7.6, 7.38e-03), (7.7, 6.41e-03), (7.8, 5.71e-03), (7.9, 5.01e-03),
    (8.0, 4.48e-03), (8.1, 3.87e-03), (8.2, 3.34e-03), (8.3, 2.81e-03), (8.4, 2.37e-03), (8.5, 2.02e-03),
    (8.6, 1.67e-03), (8.7, 1.41e-03), (8.8, 1.23e-03), (8.9, 1.05e-03), (9.0, 8.79e-04), (9.1, 7.03e-04),
    (9.2, 7.03e-04), (9.3, 6.15e-04), (9.4, 5.27e-04), (9.5, 4.39e-04), (9.6, 4.39e-04), (9.8, 3.51e-04),
    (9.9, 3.51e-04)]

COMMON_META = {
    "status": "DRAFT_UNUSED",
    "status_meaning": ("Provenance-backed DRAFT table for owner review. Not in any propellant configuration, campaign, "
                       "HallMap or architecture trade. Promotion into hallthruster_bridge/propellants/ (with a "
                       "rate_validity.toml entry and a separate O/O2 reaction-set label) is a later owner-approved model "
                       "change."),
    "sources": [DOC],
    "evidence_level": 4,
    "evidence_level_basis": "docs/EVIDENCE.md level 4: evaluated-data literature (JPCRD recommended set)",
    "extraction_method": ("numeric table transcribed by hand from pdftotext -layout of the accepted manuscript; "
                          "second-extraction token check (PyMuPDF); no figure digitization"),
    "verify": ["re-check every transcribed value against the version of record (not accessed)"],
    "milestones_supported": ["A (conditional: shows the O/O2 chemistry path is source-backed, not a gate)"],
    "rfp_thresholds_used": "none",
}


def col(table, idx):
    """(E, sigma) arrays for rows where column idx is printed."""
    rows = [(r[0], r[idx]) for r in table if r[idx] is not None]
    return np.array([r[0] for r in rows], float), np.array([r[1] for r in rows], float) * M2_PER_1E16CM2


def ramp(E, s, E_th, mode):
    if mode == "ramp":
        return np.concatenate([[E_th], E]), np.concatenate([[0.0], s])
    if mode == "envelope":
        return np.concatenate([[E_th], E]), np.concatenate([[s[0]], s])
    if mode == "table":
        return E, s
    raise ValueError(mode)


def threshold_bounds(E, s, E_th, Te_list=(2.0, 5.0, 10.0, 30.0)):
    out = {}
    for Te in Te_list:
        k = {m: maxwellian_rate(*ramp(E, s, E_th, m), Te, "hold") for m in ("table", "ramp", "envelope")}
        out[f"{Te:g}"] = {"table_over_ramp_minus_1": round(k["table"] / k["ramp"] - 1, 4),
                          "envelope_over_ramp_minus_1": round(k["envelope"] / k["ramp"] - 1, 4)}
    return out


def table_vii_row_sums():
    worst = 0.0
    for E, a, b, c, tot in TABLE_VII:
        ssum = a + (b or 0.0) + (c or 0.0)
        worst = max(worst, abs(ssum - tot) / tot)
    return worst


def specs():
    E_io, s_io = col(TABLE_VII, 1)
    E_di, s_di = col(TABLE_VII, 2)
    E_d2, s_d2 = col(TABLE_VII, 3)
    E_ds = np.array([r[0] for r in TABLE_VI], float); s_ds = np.array([r[1] for r in TABLE_VI], float) * M2_PER_1E16CM2
    E_el = np.array([r[0] for r in TABLE_V], float); s_el = np.array([r[1] for r in TABLE_V], float) * M2_PER_1E16CM2
    E_at = np.array([r[0] for r in TABLE_VIII], float); s_at = np.array([r[1] for r in TABLE_VIII], float) * M2_PER_1E16CM2

    # sensitivity of the omitted Table V row read as 0.080 eV (printed, recorded in the manifest)
    E_alt = np.array(sorted([r[0] for r in TABLE_V] + [0.080]))
    s_alt = np.interp(E_alt, E_el, s_el); s_alt[np.argmin(abs(E_alt - 0.080))] = TABLE_V_OUT_OF_ORDER_ROW[1] * M2_PER_1E16CM2
    row_sens = {f"{Te:g}": round(maxwellian_rate(E_alt, s_alt, Te, "hold") / maxwellian_rate(E_el, s_el, Te, "hold") - 1, 8)
                for Te in (0.2, 2.0)}

    diu_E, diu_s = ramp(E_di, s_di, E_TH_DI, "ramp")
    dil_E, dil_s = ramp(E_di, s_di / (1.0 + O2PP_OVER_OPLUS_AT_100EV), E_TH_DI, "ramp")
    d2_E, d2_s = ramp(E_d2, s_d2, E_TH_DI2, "ramp")
    di_bounds = threshold_bounds(E_di, s_di, E_TH_DI)
    d2_bounds = threshold_bounds(E_d2, s_d2, E_TH_DI2, (10.0, 30.0))

    def src(reaction, detail):
        return (f"DRAFT, unused by any campaign (fo_o_o2_chemistry_v0). {reaction}. Cross section: Song et al., J. Phys. "
                f"Chem. Ref. Data 55, 013102 (2026), doi:10.1063/5.0287254, {detail}. Accepted manuscript (UCL Discovery, "
                "sha256 32d163a3...), version of record not accessed: verify before promotion. Maxwellian-integrated by "
                "abep_sim/rate_tables.py (docs/chemistry/o_o2/v0/build_tables_song2026.py). Energy column = mean electron "
                "energy 3/2 Te. Evidence level 4 (docs/EVIDENCE.md).")

    out = []
    out.append({
        "file": "ionization_O2_song2026.dat", "E_eV": E_io, "sigma_m2": s_io, "header_energy_eV": E_IZ_O2,
        "header_label": "Ionization energy", "tail": "hold",
        "source_text": src("e + O2 -> O2+ + 2e (non-dissociative)", "Table VII column sigma(O2+) (+-5 %), transcribed; "
                           "sigma = 0 below 13.0 eV; held above 998 eV; header 12.2 eV = O2+(X) threshold (Sec. II.H)"),
        "meta": dict(COMMON_META, **{
            "id": "OO2-05", "reaction": "e + O2 -> O2+ + 2e", "solver_reaction_type": "ionization (electron_impact)",
            "role": "nominal", "source_location": "SONG2026 Table VII, column O2+",
            "stated_uncertainty": "5 % (SONG2026 Table VII caption)",
            "quantity_type": "measured (evaluated), transcribed",
            "transformation_chain": ("Straub et al. 1996 (+ earlier) -> Lindsay & Mangan 2003 evaluation -> SONG2026 "
                                     "Table VII -> transcribed -> Maxwellian integration"),
            "header_basis": "12.2 eV O2+(X) ionization threshold, SONG2026 Sec. II.H (text layer 'X 2Pi_u'; verify)",
            "choices": ["sigma = 0 below 13.0 eV (first tabulated point), no constructed threshold curve",
                        "held tail above 998 eV"],
            "channel_split": ("partial O2+ column only; O+ (+O2^2+) and O^2+ columns are separate tables; the total "
                              "column is NOT used (it would put dissociative/double ionization into this channel)")})})
    for variant, E_v, s_v in (("upper", diu_E, diu_s), ("lower", dil_E, dil_s)):
        extra = ("" if variant == "upper" else
                 f" divided by {1.0 + O2PP_OVER_OPLUS_AT_100EV:.1f} (SONG2026 Sec. II.H: O2^2+ 'roughly 10 % of the O+ "
                 "signal' at 100 eV, applied at every energy; statement-derived, approximate)")
        out.append({
            "file": f"dissociative_ionization_O2_{variant}_song2026.dat", "E_eV": E_v, "sigma_m2": s_v,
            "header_energy_eV": E_TH_DI, "header_label": "Ionization energy", "tail": "hold",
            "source_text": src(f"e + O2 -> O+ + O + 2e ({variant} variant)",
                               "Table VII column sigma(O+ (+O2^2+)) (+-7 %)" + extra + f"; linear ramp from 0 at "
                               f"{E_TH_DI} eV (= D0(O2) 5.12 eV, SONG2026 + IE(O) 13.618 eV, Itikawa & Ichimura 1990; "
                               "inferred thermochemical minimum) to the 23 eV point; held above 998 eV"),
            "meta": dict(COMMON_META, **{
                "id": "OO2-06", "reaction": "e + O2 -> O+ + O + 2e", "solver_reaction_type": "ionization (electron_impact, dissociative)",
                "role": "uncertainty variant: upper (published column)" if variant == "upper" else
                        "uncertainty variant: lower (O2^2+ removed by a single-energy statement)",
                "sources": [DOC, II1990], "source_location": "SONG2026 Table VII, column O+ (+O2^2+)",
                "stated_uncertainty": "7 % (SONG2026 Table VII caption) + O+/O2^2+ ambiguity (upper/lower pair)",
                "quantity_type": ("measured (evaluated), transcribed; threshold segment assumed (linear ramp)"
                                  + ("" if variant == "upper" else "; O2^2+ removal inferred from a text statement")),
                "transformation_chain": ("Straub et al. 1996 -> Lindsay & Mangan 2003 -> SONG2026 Table VII -> transcribed"
                                         + ("" if variant == "upper" else " -> / 1.1") +
                                         " -> linear threshold ramp -> Maxwellian integration"),
                "header_basis": ("18.738 eV = D0(O2) 5.12 eV (SONG2026 Sec. II.G) + IE(O) 13.618 eV (II1990 Table 2.1): "
                                 "inferred minimum fixed sink, mirrors the owner-decided N2 DI header (abep-n2n-0.4); "
                                 "fragment kinetic energy not added; PROPOSED"),
                "threshold_bounds_vs_ramp": di_bounds,
                "choices": ["linear ramp 18.738 -> 23 eV (PROPOSED, mirrors N2 DI owner decision)",
                            "held tail above 998 eV"],
                "unresolved_inside": ["O2^2+ share of the column (SONG2026: no recommendation)",
                                      "double dissociative ionization O+ + O+ (two ions per event) not separated; "
                                      "whether the partial cross section counts it once or twice per event: verify"]})})
    out.append({
        "file": "dissociative_ionization_O2_to_O_Z2plus_song2026.dat", "E_eV": d2_E, "sigma_m2": d2_s,
        "header_energy_eV": E_TH_DI2, "header_label": "Ionization energy", "tail": "hold",
        "source_text": src("e + O2 -> O^2+ + O + 3e (tier 3 candidate)",
                           f"Table VII column sigma(O^2+) (+-10 %); linear ramp from 0 at {E_TH_DI2} eV (= 5.12 + 48.77 "
                           "eV, Itikawa & Ichimura 1990 Table 2.1; inferred) to the 73 eV point; held above 998 eV"),
        "meta": dict(COMMON_META, **{
            "id": "OO2-07", "reaction": "e + O2 -> O^2+ + O + 3e",
            "solver_reaction_type": "ionization (electron_impact, dissociative; needs O max_charge 2 and an O+ -> O^2+ link)",
            "role": "tier-3 candidate (DRAFT tier), built because it is tabulated; inclusion only via a frozen completeness audit",
            "sources": [DOC, II1990], "source_location": "SONG2026 Table VII, column O^2+",
            "stated_uncertainty": "10 % (SONG2026 Table VII caption)",
            "quantity_type": "measured (evaluated), transcribed; threshold segment assumed (linear ramp)",
            "transformation_chain": "Straub et al. 1996 -> Lindsay & Mangan 2003 -> SONG2026 Table VII -> transcribed -> ramp -> Maxwellian integration",
            "header_basis": ("53.888 eV = 5.12 eV + 48.77 eV (O^2+ above O ground, II1990 Table 2.1, OCR text layer; "
                             "verify); inferred minimum; PROPOSED"),
            "threshold_bounds_vs_ramp": d2_bounds,
            "verify": COMMON_META["verify"] + ["48.77 eV read from the OCR text layer of a scanned reprint"]})})
    out.append({
        "file": "dissociation_O2_song2026.dat", "E_eV": E_ds, "sigma_m2": s_ds, "header_energy_eV": D0_O2,
        "header_label": "Dissociation energy loss", "tail": "hold",
        "source_text": src("e + O2 -> O + O + e (dissociation into neutrals, channel-summed, >= 13.5 eV only)",
                           "Table VI (data of Cosby 1993, about +-35 %), transcribed; sigma = 0 below 13.5 eV (dissociation "
                           "via Herzberg / Schumann-Runge excitation below 13.5 eV MISSING, OD-4); held above 198.5 eV; "
                           "header 5.12 eV = D0(O2) minimum sink (O(1D)+O(3P) 7.087 eV = energy-loss model uncertainty)"),
        "meta": dict(COMMON_META, **{
            "id": "OO2-08", "reaction": "e + O2 -> O + O + e", "solver_reaction_type": "ionization-type electron_impact table used as dissociation (as dissociation_N2.dat)",
            "role": "nominal DRAFT, INCOMPLETE below 13.5 eV (owner decision OD-4 open)",
            "sources": [DOC, II1990], "source_location": "SONG2026 Table VI",
            "stated_uncertainty": "about +-35 % (SONG2026 Table VI caption)",
            "quantity_type": "measured (evaluated), transcribed",
            "transformation_chain": "Cosby 1993 measurement -> SONG2026 Table VI -> transcribed -> Maxwellian integration",
            "header_basis": ("5.12 eV D0(O2) (SONG2026 Sec. II.G): minimum fixed sink; the O(1D)+O(3P) channel "
                             "(5.12 + 1.967 = 7.087 eV, II1990 Table 2.1) bounds the representative loss; owner decision OD-4"),
            "energy_loss_model_uncertainty_eV": [D0_O2, round(D0_O2 + E_O1D, 3)],
            "known_defects": ["no cross section below 13.5 eV although the dissociation threshold is 5.12 eV and the "
                              "dissociative Herzberg (about 5-7 eV) and Schumann-Runge (about 7-9.5 eV) excitations lie below "
                              "it (SONG2026 Sec. II.F/G): the low-T_e rate is an UNDER-estimate of unknown size",
                              "double counting with any dissociative-excitation table above 13.5 eV (CC-4)"]})})
    out.append({
        "file": "elastic_O2_song2026.dat", "E_eV": E_el, "sigma_m2": s_el, "header_energy_eV": 0.0,
        "header_label": "Momentum transfer, no inelastic energy loss", "tail": "hold",
        "source_text": src("e + O2 elastic momentum transfer", "Table V (MTCS), transcribed; out-of-order manuscript row "
                           "'0.008 eV 2.30' omitted; held above 1000 eV; header 0 (no inelastic loss)"),
        "meta": dict(COMMON_META, **{
            "id": "OO2-09", "reaction": "e + O2 -> e + O2 (momentum transfer)", "solver_reaction_type": "elastic",
            "role": "nominal", "source_location": "SONG2026 Table V",
            "stated_uncertainty": "about 20 % for 1-10 eV, 10-15 % for 10-1000 eV, none below 1 eV (SONG2026 Table V caption)",
            "quantity_type": "measured (evaluated: beam DCS-derived above 1 eV) / inferred (swarm unfolding below 0.8 eV), transcribed",
            "transformation_chain": "beam DCS (Sullivan et al.) + Jeon 2003 swarm -> SONG2026 Table V -> transcribed -> Maxwellian integration",
            "header_basis": "0 eV: momentum transfer carries no inelastic loss (same convention as elastic_N2_song2023.dat)",
            "omitted_row": {"printed": list(TABLE_V_OUT_OF_ORDER_ROW),
                            "reason": "printed between 0.060 and 0.090 eV; energy ambiguous (0.080 eV likely); not re-interpreted",
                            "rate_change_if_read_as_0.080_eV_by_Te": row_sens}})})
    out.append({
        "file": "attachment_O2_song2026.dat", "E_eV": E_at, "sigma_m2": s_at, "header_energy_eV": 4.2,
        "header_label": "Dissociative attachment tabulated onset, NOT a solver input", "tail": "zero",
        "source_text": src("e + O2 -> O- + O (dissociative electron attachment)", "Table VIII (data of Rapp & Briglia "
                           "1965; 'no more than 20 %'), transcribed; no 6.4 / 9.7 eV rows printed (interpolated); ZERO "
                           "tail above 9.9 eV (assumption, share recorded). NOT usable by the pinned solver (no attachment "
                           "reaction type; uncited negative-ion constants, CC-2); O- admission is owner decision OD-5"),
        "meta": dict(COMMON_META, **{
            "id": "OO2-16", "reaction": "e + O2 -> O- + O", "solver_reaction_type": "none in the pinned HallThruster.jl (CC-2)",
            "role": "assessment input only (F_att, OD-5); never a propellant table while O- is not admitted",
            "source_location": "SONG2026 Table VIII",
            "stated_uncertainty": "'no more than 20 %' (SONG2026 suggestion; Rapp & Briglia gave none)",
            "quantity_type": "measured (evaluated), transcribed; zero tail beyond 9.9 eV assumed",
            "transformation_chain": "Rapp & Briglia 1965 -> SONG2026 Table VIII -> transcribed -> Maxwellian integration (zero tail)",
            "header_basis": "4.2 eV = first tabulated row (sigma = 0 there); the electron itself is lost, no energy-loss meaning",
            "applicability": "ground vibrational state; hot / metastable O2 excluded by SONG2026"})})
    return out


MANIFEST_HEADER = {
    "id": "o_o2_tables_song2026_v0",
    "lane": "fo_o_o2_chemistry_v0 (trigger T_PIVOT_O_O2_CHEMISTRY_V0, owner disposition od_hardware_pivot, W7)",
    "status": "DRAFT_FOR_OWNER_REVIEW",
    "builder": "docs/chemistry/o_o2/v0/build_tables_song2026.py",
    "integrator": "abep_sim/rate_tables.py (unchanged; read-only import)",
    "format": ("HallThruster.jl rate table as hallthruster_bridge/propellants/*.dat: header '<label> (eV): <E>', column "
               "header, then mean energy 0-300 eV step 1 and rate coefficient (m^3/s)"),
    "precedence_note": ("o_o2_completeness_prereg_DRAFT.json (lane 13) asks to be frozen before any O/O2 table is built. It "
                        "is DRAFT_PENDING_OWNER and binds nothing; the owner's od_hardware_pivot W7 disposition "
                        "(2026-09-27) registered this lane to build first DRAFT tables. No F_P / F_ion / F_S value and no "
                        "cross-channel comparison is computed here, so no completeness verdict is pre-empted."),
}


def _interleave(tab, split):
    """Row order of a two-column printed table as the PDF text stream emits it (left row i, then right row i)."""
    left, right, out = tab[:split], tab[split:], []
    for i in range(max(len(left), len(right))):
        if i < len(left):
            out += [v for v in left[i] if v is not None]
        if i < len(right):
            out += [v for v in right[i] if v is not None]
    return out


def verify_pdf(path: str) -> int:
    """Second-extraction check (PyMuPDF): each transcribed table must occur as one contiguous, ordered run of numeric
    tokens in the manuscript text stream (value-exact), including the omitted Table V row at its printed position."""
    import re
    try:
        import pymupdf  # type: ignore
    except ImportError:
        import fitz as pymupdf  # type: ignore
    if sha256_file(path) != DOC["document_sha256"]:
        print("PDF sha256 differs from the pinned manuscript"); return 1
    text = " ".join(page.get_text() for page in pymupdf.open(path))
    toks = [float(t) for t in re.findall(r"[0-9]+(?:\.[0-9]+)?(?:E[-+][0-9]+)?", text)]

    def longest_run(seq):
        best = 0
        for i in range(len(toks)):
            k = 0
            while k < len(seq) and i + k < len(toks) and abs(toks[i + k] - seq[k]) < 1e-12:
                k += 1
            best = max(best, k)
        return best

    table_v_printed = TABLE_V[:14] + [TABLE_V_OUT_OF_ORDER_ROW] + TABLE_V[14:]
    checks = {"V": _interleave(table_v_printed, 25), "VI": _interleave(TABLE_VI, 7),
              "VII": [v for r in TABLE_VII for v in r if v is not None], "VIII": _interleave(TABLE_VIII, 28)}
    bad = 0
    for name, seq in checks.items():
        n = longest_run(seq)
        print(f"Table {name}: {n}/{len(seq)} values matched in printed order")
        bad += n != len(seq)
    print("verify-pdf:", "OK" if not bad else "FAILED")
    return 0 if not bad else 1


def main(argv):
    if "--verify-pdf" in argv:
        return verify_pdf(argv[argv.index("--verify-pdf") + 1])
    print(f"Table VII transcription check: max |sum(partials) - total| / total = {100 * table_vii_row_sums():.2f} %")
    return run(specs(), "manifest_song2026_v0.json", MANIFEST_HEADER, check="--check" in argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
