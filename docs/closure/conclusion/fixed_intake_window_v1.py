"""Fixed-intake AIR-mode window: chemistry- and compressor-independent bounds (reproducible).
Inputs: A4 record (admitted free-stream flux over the 196 states), DBF-1 V_d band, RFP 12 / 25 mN.
Favourable assumptions throughout: capture efficiency 1, all delivered flow ionised singly to O+ (lightest
registered heavy species) and accelerated through the full V_d,max, no body drag, no losses."""
import json, math, hashlib, sys
from pathlib import Path
A4 = Path("docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/conservation_bounds_v1.json")
d = json.loads(A4.read_text()); s = json.dumps(d)
i = s.index('"Phi_adm_kg_m2_s": {"min"'); phi = json.loads(s[i+len('"Phi_adm_kg_m2_s": '): s.index('}', i)+1])
e, amu = 1.602176634e-19, 1.66053906660e-27
VD_MAX = 350.0                      # DBF1-H1-05 upper band end
U = 7.8e3                            # relative speed scale, m/s (180-230 km circular; A4 uses state values)
v_max = math.sqrt(2*e*VD_MAX/(16*amu))   # O+ at full V_d
out = {"inputs": {"A4_record": str(A4), "A4_sha256": hashlib.sha256(A4.read_bytes()).hexdigest(),
       "Phi_adm_min": phi["min"], "Phi_adm_max": phi["max"], "Phi_min_state": phi["min_state"], "Phi_max_state": phi["max_state"],
       "Vd_max_V": VD_MAX, "U_m_s": U, "v_ex_max_m_s": v_max},
       "span_Phi_max_over_min": phi["max"]/phi["min"]}
for T in (0.012, 0.025):
    mdot = T / v_max
    A_thin = mdot / phi["min"]
    D_dense = phi["max"] * A_thin * U
    window = 0.025 / (U * mdot)      # allowed Phi_max/Phi_min for one fixed area with D_capture <= 25 mN
    out[f"T_{int(T*1e3)}mN"] = {"mdot_req_min_kg_s": mdot, "A_req_at_thinnest_m2": A_thin,
        "capture_drag_at_densest_with_that_area_N": D_dense, "max_flux_window_ratio_for_fixed_area": window}
json.dump(out, sys.stdout, indent=1); print()
