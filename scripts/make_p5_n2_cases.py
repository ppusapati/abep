"""Generate the P5-N2 scoring case set hallthruster_bridge/cases/p5_n2.json (pre-registration p5_n2_validation_criteria_v1).

Same machinery as scripts/make_p5_xenon_cases.py (layer-1 hypotheses, never selected point by point):
  registrations L38-hist / L32-anode / L32-exit  x  historical coil shapes 1.6 kW / 3.0 kW (Peterson 2001 centreline field),
  B at the model exit plane, channel centreline, scaled to Brabston Table 2's 130 G (the N2 field shape was not published:
  both shapes are field-shape HYPOTHESES). 5 points x 3 registrations x 2 coil shapes = 30 cases; each runs in both modes.
Targets come only from the frozen measurement audit (identification/brabston_p5_n2_measurement_audit_v1.json, PR #26):
  vacuum (primary, ingestion OFF):   I_d,corr (Eq. 14) and T_corr (Eq. 16, published);
  facility (secondary, ingestion ON): I_d raw = P_d/V_d and T raw (Eq. 16 inverted, zeta_en = 0.8).
Thrust is scored at N1-N3 only (no divergence data at N4/N5); tolerances and divergence readings per the pre-registration.
The chemistry config is set per run by the campaign driver; propellant_config here is the nominal set.
Usage: python scripts/make_p5_n2_cases.py
"""
import importlib.util, json, os

ROOT = os.path.join(os.path.dirname(__file__), "..")
BR = os.path.join(ROOT, "hallthruster_bridge")
_spec = importlib.util.spec_from_file_location("xe", os.path.join(os.path.dirname(__file__), "make_p5_xenon_cases.py"))
xe = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(xe)

AUDIT = os.path.join(BR, "identification", "brabston_p5_n2_measurement_audit_v1.json")
B_EXIT_T = 0.0130
SCORED_THRUST = ("N1", "N2", "N3")
T_TOL_MN = {"N1": 5.2, "N2": 5.6, "N3": 5.6}      # 2 sigma (2.6 mN); + 0.4 mN digitization where the value is digitized
SOURCE = ("Brabston et al., JPP 2025, doi:10.2514/1.B39623, Table 2 (anode N2 5.0/5.2/5.4 mg/s, cathode Xe 0.44 mg/s, peak radial "
          "B 130 G at channel centre / exit plane, chamber pressure per point), Table 5, Figs. 5, 8-10 via the frozen measurement "
          "audit (identification/brabston_p5_n2_measurement_audit_v1.json). Geometry, registrations and B(z) shapes as in "
          "cases/p5_xenon.json (Peterson 2001; channel depth 32 vs 38 mm unresolved).")
ASSUMPTIONS = ("N2 coil currents and field shape unpublished: historical 1.6 kW / 3.0 kW shapes scaled to 130 G are hypotheses. "
               "Xenon cathode flow (0.44 mg/s) not modelled (1-D). Ingested flow enters at the anode boundary (facility mode). "
               "Transport, chemistry config and divergence reading are set per run by the pre-registered campaign; nothing tuned.")


def cases():
    a = json.load(open(AUDIT))["points"]
    out = []
    for coil in ("1p6kW", "3p0kW"):
        for reg, (L, align, zref, hyp) in xe.REGISTRATIONS.items():
            for pid, v in a.items():
                t2 = v["table2"]
                m = {"Pd_W": t2["P_d_kW"] * 1e3, "Id_A": v["I_d_raw_A"], "Id_corr_A": v["I_d_corr_eq14_A"],
                     "T_corr_mN": v["T_corr_mN"], "T_corr_source": v["T_corr_source"], "T_sigma_mN": v["T_sigma_mN"],
                     "T_raw_mN": v["T_raw_eq16_inverted_mN"], "thrust_scored": pid in SCORED_THRUST}
                if pid in SCORED_THRUST:
                    c = v["consistency"]
                    m["T_tolerance_mN"] = T_TOL_MN[pid]
                    m["axial_factor"] = {"A": c["axial_factor_A"], "B": c["axial_factor_B"]}
                    m["ExB_Va_V_diagnostic"] = {"N2+": v["fig10"]["Va_N2plus_V"], "N+": v["fig10"]["Va_Nplus_V"],
                                                "sigma_V": 11.6, "role": "non-gating diagnostic"}
                out.append({
                    "id": f"{pid}-{reg}-{coil}", "point": pid, "registration": reg, "coil_shape": coil,
                    "geometry_hypothesis": hyp, "thruster": "P5", "gas": "N2",
                    "propellant_config": "propellants/n2_n.toml", "rate_dir": "propellants",
                    "Vd": t2["V_d"], "mdot_kgps": t2["mdot_anode_mg_s"] * 1e-6,
                    "r_in_m": 0.0615, "r_out_m": 0.0865, "L_m": L, "domain_m": 0.1, "B_ref_T": B_EXIT_T,
                    "B_profile": {"file": xe.COILS[coil], "align": align, "z_ref_in_file_mm": zref, "scale_to": "exit"},
                    "comparison_modes": ["vacuum", "facility"], "background_pressure_Torr": t2["p_chamber_Torr_N2"],
                    "background_temperature_K": 300.0, "entrainment_area_m2": 0.0488, "zeta_A": 1.0, "zeta_en": 0.8,
                    "cells": 200, "dt_s": 5e-9, "duration_s": 0.002, "average_start_s": 0.001,
                    "measured": m})
    return out


if __name__ == "__main__":
    d = {"source": SOURCE, "assumptions": ASSUMPTIONS, "preregistration": "prereg/p5_n2_validation_criteria_v1.json",
         "cases": cases()}
    json.dump(d, open(os.path.join(BR, "cases", "p5_n2.json"), "w"), indent=1)
    print("p5_n2.json", len(d["cases"]), "cases")
