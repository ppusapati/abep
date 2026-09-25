"""Generate the P5-xenon HallThruster.jl case files (cited inputs only; see 'source' in each file).

Geometry is unresolved: Brabston et al. (JPP 2025) state a 32 mm channel; Peterson/Gallimore/Haas (AIAA 2001-3890),
Hofer (PhD 2004, Sec. 5.3.1) give a 38 mm channel depth (anode at z = -38 mm), and the 2001 field map puts the exit
plane at 38.0 mm from the anode face. Each hypothesis is a separate case, with the measured field placed rigidly
(never stretched):
  L38-hist   38 mm channel, field in its original coordinates (anode face = anode, exit at 38.0 mm)
  L32-anode  32 mm channel, same anode/magnetic circuit, ceramic ends 6 mm earlier: anode face = anode
  L32-exit   32 mm channel, anode moved 6 mm downstream: file exit plane (38.0 mm) = model exit
In every case B at the model exit plane, channel centreline, is scaled to Table 4's 162.5 G (Brabston: "peak radial
B-field ... measured in the center of the discharge channel at the thruster exit plane").
Usage: python scripts/make_p5_xenon_cases.py
"""
import json, os

HERE = os.path.join(os.path.dirname(__file__), "..", "hallthruster_bridge", "cases")
SOURCE = ("Brabston et al., JPP 2025, doi:10.2514/1.B39623, Table 4 (anode Xe 5 mg/s, cathode Xe 0.44 mg/s, peak radial B "
          "162.5 G at channel centre / exit plane, all constant across Xe1-Xe3; chamber pressure varies); Eq. (13)-(14) "
          "ingestion model (A_en = 488 cm2, T0 = 300 K, zeta_A = 1.0). Channel radii: OD 173 mm, width 25 mm (Hofer 2004 "
          "Sec. 5.3.1; J. Electr. Propuls. 2026, doi:10.1007/s44205-026-00179-9). Channel depth: 32 mm (Brabston) vs 38 mm "
          "(Peterson 2001, Hofer 2004) - UNRESOLVED, both carried. B(z) shape: Peterson, Gallimore & Haas, AIAA 2001-3890, "
          "Figs. 11/12 centreline vacuum field (hallthruster_bridge/bfield/)")
ASSUMPTIONS = ("Brabston coil currents not published; coil shape from Peterson 2001 (1.6 kW or 3.0 kW setting). Measured "
               "Id_A = Pd/Vd (Table 4). Cathode flow not modelled (1-D domain). Ingested flow enters at the anode boundary "
               "in HallThruster.jl; Eq. (13) is a plume-entrainment estimate. Transport: HallThruster.jl defaults "
               "(TwoZoneBohm(1/160, 1/16), transition length 0.1 L), deliberately not tuned.")
POINTS = [("Xe1", 230.8, 1750.0, 4.49e-5), ("Xe2", 250.3, 2150.0, 3.94e-5), ("Xe3", 274.3, 2030.0, 3.28e-5)]
# Eq. (16)-corrected thrust per setpoint [mN]. Xe1 and Xe3 are the range end-points stated in the Brabston abstract
# (72.8-86.8 mN); Xe2 is read from Fig. 5 (raster; extraction in docs/HISTORY.md: axis residuals < 0.25 mN, and the
# Xe1/Xe3 readings 72.85/87.04 reproduce the text values; the markers' x-positions reproduce the Eq. (14) powers to 0.004 kW).
# Uncertainty +-4.9 mN (Table 5, xenon).
THRUST_CORR_MN = {"Xe1": (72.8, "abstract"), "Xe2": (83.4, "Fig. 5, digitized"), "Xe3": (86.8, "abstract")}
T_SIGMA_MN = 4.9
ZETA_EN = 0.8    # Brabston thrust entrainment factor (Eq. 16)
REGISTRATIONS = {   # name: (L_m, align, z_ref_in_file_mm, hypothesis)
    "L38-hist":  (0.038, "anode", 0.0, "historical 38 mm P5 (Peterson 2001 / Hofer 2004); field in original coordinates"),
    "L32-anode": (0.032, "anode", 0.0, "32 mm channel (Brabston 2025), anode and magnetic circuit unchanged"),
    "L32-exit":  (0.032, "exit", 38.0, "32 mm channel (Brabston 2025), anode 6 mm downstream, exit planes aligned"),
}
COILS = {"1p6kW": "bfield/p5_vacuum_Br_centerline_1p6kW.csv", "3p0kW": "bfield/p5_vacuum_Br_centerline_3p0kW.csv"}


def cases(coil, role):
    out = []
    for reg, (L, align, zref, hyp) in REGISTRATIONS.items():
        for pid, Vd, Pd, P in POINTS:
            out.append({
                "id": f"{pid}-{reg}", "point": pid, "registration": reg, "geometry_hypothesis": hyp, "role": role,
                "thruster": "P5", "gas": "Xe", "Vd": Vd, "mdot_kgps": 5e-6,
                "r_in_m": 0.0615, "r_out_m": 0.0865, "L_m": L, "domain_m": 0.1,
                "B_ref_T": 0.01625,
                "B_profile": {"file": COILS[coil], "align": align, "z_ref_in_file_mm": zref, "scale_to": "exit"},
                "comparison_modes": ["facility", "vacuum"], "background_pressure_Torr": P, "background_temperature_K": 300.0,
                "entrainment_area_m2": 0.0488, "zeta_A": 1.0,
                "cells": 200, "dt_s": 5e-9, "duration_s": 0.002, "average_start_s": 0.001,
                "zeta_en": ZETA_EN,
                "measured": {"Pd_W": Pd, "Id_A": Pd / Vd, "T_corr_mN": THRUST_CORR_MN[pid][0],
                             "T_corr_source": THRUST_CORR_MN[pid][1], "T_sigma_mN": T_SIGMA_MN},
            })
    return out


if __name__ == "__main__":
    for fname, coil, role in (("p5_xenon.json", "1p6kW", "geometry-registration candidates (1.6 kW coil shape)"),
                              ("p5_xenon_coil_sensitivity.json", "3p0kW", "sensitivity: 3.0 kW coil shape")):
        d = {"source": SOURCE, "assumptions": ASSUMPTIONS, "role": role, "cases": cases(coil, role)}
        json.dump(d, open(os.path.join(HERE, fname), "w"), indent=1)
        print(fname, len(d["cases"]), "cases")
