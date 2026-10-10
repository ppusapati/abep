# Parity report v1 - PARITY-C-ABEP_SIM_ATMOSPHERE_ORBIT_PY-V1

Verdict: **PARITY_PASS** (ADMITTED). Generated from `parity_report_v1.json`.

* Contract: `docs/rust_migration/contracts/C-ABEP_SIM_ATMOSPHERE_ORBIT_PY/parity_prereg_v1.json` sha256 `fd7b9f750228939d4c768402abd13d1979b5b0b7f68df6ab27e12e4e40d40c46`, registered in `a5a84e6fbba0`.
* Python reference commit `96db5524ec91`; Rust commit `ace0a7aac3cf`; rustc 1.94.1 (e408947bf 2026-03-25).
* Environment: Python 3.11.15, numpy 2.4.4, scipy-openblas 0.3.31.188.0, Intel(R) Xeon(R) Processor @ 2.10GHz.
* Master seed 731905204 (scoring); 3749 vectors; 0 per-test failures.

## Checks

* per_test: pass
* refusal_trees: pass
* determinism: pass
* governing: pass
* all: pass

## Observables

| entry | observable | class | n | fail | bit-identical | max abs diff | max rel diff | max ulp |
|---|---|---|---|---|---|---|---|---|
| orbit_state | status | EXACT_VALUE | 1822 | 0 | 1822 | 0 | 0 | 0 |
| orbit_state | key order | EXACT_VALUE | 1808 | 0 | 1808 | 0 | 0 | 0 |
| orbit_state | alt_km | EXACT_VALUE | 1808 | 0 | 1808 | 0 | 0 | 0 |
| orbit_state | lat_deg | EXACT_VALUE | 1808 | 0 | 1808 | 0 | 0 | 0 |
| orbit_state | doy | EXACT_VALUE | 1808 | 0 | 1808 | 0 | 0 | 0 |
| orbit_state | scenario | EXACT_VALUE | 1808 | 0 | 1808 | 0 | 0 | 0 |
| orbit_state | f107 | EXACT_VALUE | 1808 | 0 | 1808 | 0 | 0 | 0 |
| orbit_state | f107a | EXACT_VALUE | 1808 | 0 | 1808 | 0 | 0 | 0 |
| orbit_state | ap | EXACT_VALUE | 1808 | 0 | 1808 | 0 | 0 | 0 |
| orbit_state | source | EXACT_VALUE | 1808 | 0 | 1808 | 0 | 0 | 0 |
| orbit_state | evaluation | EXACT_VALUE | 1808 | 0 | 1808 | 0 | 0 | 0 |
| orbit_state | interp_max_rel_err_rho | EXACT_VALUE | 1808 | 0 | 1808 | 0 | 0 | 0 |
| orbit_state | lst_h | EXACT_VALUE | 1808 | 0 | 1808 | 0 | 0 | 0 |
| orbit_state | lon_deg | EXACT_VALUE | 1808 | 0 | 1808 | 0 | 0 | 0 |
| orbit_state | rho_kg_m3 | ULP_BOUNDED | 1808 | 0 | 635 | 9.2e-24 | 1.77e-14 | 124 |
| orbit_state | n_N2_m3 | ULP_BOUNDED | 1808 | 0 | 677 | 262 | 3.56e-14 | 317 |
| orbit_state | n_O2_m3 | ULP_BOUNDED | 1808 | 0 | 658 | 13.1 | 3.55e-14 | 217 |
| orbit_state | n_O_m3 | ULP_BOUNDED | 1808 | 0 | 677 | 278 | 3.55e-14 | 236 |
| orbit_state | n_He_m3 | ULP_BOUNDED | 1808 | 0 | 546 | 0.695 | 2.49e-14 | 168 |
| orbit_state | n_Ar_m3 | ULP_BOUNDED | 1808 | 0 | 574 | 4.66 | 2.84e-14 | 180 |
| orbit_state | n_N_m3 | ULP_BOUNDED | 1808 | 0 | 583 | 15.9 | 3.54e-14 | 226 |
| orbit_state | n_total_m3 | ULP_BOUNDED | 1808 | 0 | 249 | 452 | 2.47e-14 | 221 |
| orbit_state | T_K | ULP_BOUNDED | 1808 | 0 | 556 | 8.64e-12 | 6.13e-15 | 38 |
| orbit_state | x_O | ULP_BOUNDED | 1808 | 0 | 273 | 1.03e-14 | 3.17e-14 | 240 |
| orbit_state | x_N2 | ULP_BOUNDED | 1808 | 0 | 278 | 1.03e-14 | 3.01e-14 | 266 |
| orbit_state | x_O2 | ULP_BOUNDED | 1808 | 0 | 239 | 2.3e-15 | 4.56e-14 | 332 |
| orbit_state | x_N | ULP_BOUNDED | 1808 | 0 | 191 | 8.74e-16 | 3.79e-14 | 228 |
| orbit_state | x_He | ULP_BOUNDED | 1808 | 0 | 179 | 6.07e-16 | 3.02e-14 | 252 |
| orbit_state | x_Ar | ULP_BOUNDED | 1808 | 0 | 180 | 4.68e-16 | 3.51e-14 | 261 |
| orbit_state | CONS-D-01 /sum x - 1/ (Rust) | ULP_BOUNDED | 1808 | 0 | 840 | 4.44e-16 | 4.44e-16 | 2 |
| orbit_state | CONS-D-02 n_total bits (Rust) | EXACT_VALUE | 1808 | 0 | 1808 | 0 | 0 | 0 |
| orbit_node_state | status | EXACT_VALUE | 211 | 0 | 211 | 0 | 0 | 0 |
| orbit_node_state | key order | EXACT_VALUE | 208 | 0 | 208 | 0 | 0 | 0 |
| orbit_node_state | alt_km | EXACT_VALUE | 208 | 0 | 208 | 0 | 0 | 0 |
| orbit_node_state | lat_deg | EXACT_VALUE | 208 | 0 | 208 | 0 | 0 | 0 |
| orbit_node_state | doy | EXACT_VALUE | 208 | 0 | 208 | 0 | 0 | 0 |
| orbit_node_state | scenario | EXACT_VALUE | 208 | 0 | 208 | 0 | 0 | 0 |
| orbit_node_state | f107 | EXACT_VALUE | 208 | 0 | 208 | 0 | 0 | 0 |
| orbit_node_state | f107a | EXACT_VALUE | 208 | 0 | 208 | 0 | 0 | 0 |
| orbit_node_state | ap | EXACT_VALUE | 208 | 0 | 208 | 0 | 0 | 0 |
| orbit_node_state | source | EXACT_VALUE | 208 | 0 | 208 | 0 | 0 | 0 |
| orbit_node_state | evaluation | EXACT_VALUE | 208 | 0 | 208 | 0 | 0 | 0 |
| orbit_node_state | interp_max_rel_err_rho | EXACT_VALUE | 208 | 0 | 208 | 0 | 0 | 0 |
| orbit_node_state | lst_h | EXACT_VALUE | 208 | 0 | 208 | 0 | 0 | 0 |
| orbit_node_state | lon_deg | EXACT_VALUE | 208 | 0 | 208 | 0 | 0 | 0 |
| orbit_node_state | rho_kg_m3 | ULP_BOUNDED | 208 | 0 | 208 | 0 | 0 | 0 |
| orbit_node_state | n_N2_m3 | ULP_BOUNDED | 208 | 0 | 208 | 0 | 0 | 0 |
| orbit_node_state | n_O2_m3 | ULP_BOUNDED | 208 | 0 | 208 | 0 | 0 | 0 |
| orbit_node_state | n_O_m3 | ULP_BOUNDED | 208 | 0 | 208 | 0 | 0 | 0 |
| orbit_node_state | n_He_m3 | ULP_BOUNDED | 208 | 0 | 208 | 0 | 0 | 0 |
| orbit_node_state | n_Ar_m3 | ULP_BOUNDED | 208 | 0 | 208 | 0 | 0 | 0 |
| orbit_node_state | n_N_m3 | ULP_BOUNDED | 208 | 0 | 208 | 0 | 0 | 0 |
| orbit_node_state | n_total_m3 | ULP_BOUNDED | 208 | 0 | 208 | 0 | 0 | 0 |
| orbit_node_state | T_K | ULP_BOUNDED | 208 | 0 | 208 | 0 | 0 | 0 |
| orbit_node_state | x_O | ULP_BOUNDED | 208 | 0 | 208 | 0 | 0 | 0 |
| orbit_node_state | x_N2 | ULP_BOUNDED | 208 | 0 | 208 | 0 | 0 | 0 |
| orbit_node_state | x_O2 | ULP_BOUNDED | 208 | 0 | 208 | 0 | 0 | 0 |
| orbit_node_state | x_N | ULP_BOUNDED | 208 | 0 | 208 | 0 | 0 | 0 |
| orbit_node_state | x_He | ULP_BOUNDED | 208 | 0 | 208 | 0 | 0 | 0 |
| orbit_node_state | x_Ar | ULP_BOUNDED | 208 | 0 | 208 | 0 | 0 | 0 |
| orbit_node_state | CONS-D-01 /sum x - 1/ (Rust) | ULP_BOUNDED | 208 | 0 | 151 | 2.22e-16 | 2.22e-16 | 1 |
| orbit_node_state | CONS-D-02 n_total bits (Rust) | EXACT_VALUE | 208 | 0 | 208 | 0 | 0 | 0 |
| orbit_states | status | EXACT_VALUE | 63 | 0 | 63 | 0 | 0 | 0 |
| orbit_states | number of states | EXACT_VALUE | 46 | 0 | 46 | 0 | 0 | 0 |
| orbit_states | key order | EXACT_VALUE | 951 | 0 | 951 | 0 | 0 | 0 |
| orbit_states | alt_km | EXACT_VALUE | 951 | 0 | 951 | 0 | 0 | 0 |
| orbit_states | lat_deg | ULP_BOUNDED | 951 | 0 | 951 | 0 | 0 | 0 |
| orbit_states | doy | EXACT_VALUE | 951 | 0 | 951 | 0 | 0 | 0 |
| orbit_states | scenario | EXACT_VALUE | 951 | 0 | 951 | 0 | 0 | 0 |
| orbit_states | f107 | EXACT_VALUE | 951 | 0 | 951 | 0 | 0 | 0 |
| orbit_states | f107a | EXACT_VALUE | 951 | 0 | 951 | 0 | 0 | 0 |
| orbit_states | ap | EXACT_VALUE | 951 | 0 | 951 | 0 | 0 | 0 |
| orbit_states | source | EXACT_VALUE | 951 | 0 | 951 | 0 | 0 | 0 |
| orbit_states | evaluation | EXACT_VALUE | 951 | 0 | 951 | 0 | 0 | 0 |
| orbit_states | interp_max_rel_err_rho | EXACT_VALUE | 951 | 0 | 951 | 0 | 0 | 0 |
| orbit_states | lst_h | ULP_BOUNDED | 951 | 0 | 951 | 0 | 0 | 0 |
| orbit_states | lon_deg | ULP_BOUNDED | 951 | 0 | 951 | 0 | 0 | 0 |
| orbit_states | rho_kg_m3 | ULP_BOUNDED | 951 | 0 | 265 | 8.27e-24 | 1.77e-14 | 119 |
| orbit_states | n_N2_m3 | ULP_BOUNDED | 951 | 0 | 298 | 290 | 3.56e-14 | 303 |
| orbit_states | n_O2_m3 | ULP_BOUNDED | 951 | 0 | 278 | 9.38 | 2.85e-14 | 256 |
| orbit_states | n_O_m3 | ULP_BOUNDED | 951 | 0 | 289 | 202 | 2.85e-14 | 243 |
| orbit_states | n_He_m3 | ULP_BOUNDED | 951 | 0 | 208 | 0.422 | 2.14e-14 | 176 |
| orbit_states | n_Ar_m3 | ULP_BOUNDED | 951 | 0 | 261 | 5 | 2.49e-14 | 160 |
| orbit_states | n_N_m3 | ULP_BOUNDED | 951 | 0 | 235 | 7.06 | 2.85e-14 | 226 |
| orbit_states | n_total_m3 | ULP_BOUNDED | 951 | 0 | 39 | 296 | 2.28e-14 | 177 |
| orbit_states | T_K | ULP_BOUNDED | 951 | 0 | 236 | 5.46e-12 | 4.55e-15 | 32 |
| orbit_states | x_O | ULP_BOUNDED | 951 | 0 | 67 | 1.22e-14 | 2.91e-14 | 219 |
| orbit_states | x_N2 | ULP_BOUNDED | 951 | 0 | 66 | 1.2e-14 | 3.03e-14 | 164 |
| orbit_states | x_O2 | ULP_BOUNDED | 951 | 0 | 31 | 9.16e-16 | 3.15e-14 | 243 |
| orbit_states | x_N | ULP_BOUNDED | 951 | 0 | 16 | 1.16e-15 | 3.55e-14 | 245 |
| orbit_states | x_He | ULP_BOUNDED | 951 | 0 | 17 | 3.4e-16 | 3.19e-14 | 223 |
| orbit_states | x_Ar | ULP_BOUNDED | 951 | 0 | 24 | 5.27e-16 | 3.36e-14 | 240 |
| orbit_states | inclination_deg | EXACT_VALUE | 951 | 0 | 951 | 0 | 0 | 0 |
| orbit_states | ltan_h | EXACT_VALUE | 951 | 0 | 951 | 0 | 0 | 0 |
| orbit_states | orbit_inputs_status | EXACT_VALUE | 951 | 0 | 951 | 0 | 0 | 0 |
| orbit_states | wind_included | EXACT_VALUE | 951 | 0 | 951 | 0 | 0 | 0 |
| orbit_states | wind_open_item | EXACT_VALUE | 951 | 0 | 951 | 0 | 0 | 0 |
| orbit_states | state_id | EXACT_VALUE | 951 | 0 | 951 | 0 | 0 | 0 |
| orbit_states | geometry | EXACT_VALUE | 951 | 0 | 951 | 0 | 0 | 0 |
| orbit_states | t_s | ULP_BOUNDED | 951 | 0 | 951 | 0 | 0 | 0 |
| orbit_states | u_deg | ULP_BOUNDED | 951 | 0 | 951 | 0 | 0 | 0 |
| orbit_states | ut_h | ULP_BOUNDED | 951 | 0 | 951 | 0 | 0 | 0 |
| orbit_states | v_orb_m_s | ULP_BOUNDED | 951 | 0 | 951 | 0 | 0 | 0 |
| orbit_states | v_rel_corot_m_s | ULP_BOUNDED | 951 | 0 | 871 | 1.82e-12 | 2.22e-16 | 1 |
| orbit_states | weight | ULP_BOUNDED | 951 | 0 | 951 | 0 | 0 | 0 |
| orbit_states | flux_corot_kg_m2_s | ULP_BOUNDED | 951 | 0 | 249 | 6.78e-20 | 1.77e-14 | 151 |
| wind | status | EXACT_VALUE | 1222 | 0 | 1222 | 0 | 0 | 0 |
| wind | key order | EXACT_VALUE | 1208 | 0 | 1208 | 0 | 0 | 0 |
| wind | u_mer_quiet_m_s | ULP_BOUNDED | 1208 | 0 | 323 | 1.14e-13 | 1.34e-14 | 88 |
| wind | u_zon_quiet_m_s | ULP_BOUNDED | 1208 | 0 | 328 | 8.53e-14 | 4.97e-14 | 224 |
| wind | u_mer_dist_m_s | ULP_BOUNDED | 1208 | 0 | 453 | 5.68e-14 | 1.83e-14 | 96 |
| wind | u_zon_dist_m_s | ULP_BOUNDED | 1208 | 0 | 435 | 1.14e-13 | 2.63e-14 | 192 |
| wind | u_mer_m_s | ULP_BOUNDED | 1208 | 0 | 361 | 1.14e-13 | 3e-14 | 256 |
| wind | u_zon_m_s | ULP_BOUNDED | 1208 | 0 | 339 | 1.14e-13 | 1.29e-13 | 1.02e+03 |
| wind | ap_hwm | EXACT_VALUE | 1208 | 0 | 1208 | 0 | 0 | 0 |
| wind | wind_model | EXACT_VALUE | 1208 | 0 | 1208 | 0 | 0 | 0 |
| wind | wind_source | EXACT_VALUE | 1208 | 0 | 1208 | 0 | 0 | 0 |
| wind | wind_interp_max_abs_err_m_s | EXACT_VALUE | 1208 | 0 | 1208 | 0 | 0 | 0 |
| wind | CONS-D-04 u_mer = quiet + dist bits (Rust) | EXACT_VALUE | 1208 | 0 | 1208 | 0 | 0 | 0 |
| wind | CONS-D-04 u_zon = quiet + dist bits (Rust) | EXACT_VALUE | 1208 | 0 | 1208 | 0 | 0 | 0 |
| state_v2 | status | EXACT_VALUE | 422 | 0 | 422 | 0 | 0 | 0 |
| state_v2 | key order | EXACT_VALUE | 408 | 0 | 408 | 0 | 0 | 0 |
| state_v2 | alt_km | EXACT_VALUE | 408 | 0 | 408 | 0 | 0 | 0 |
| state_v2 | lat_deg | EXACT_VALUE | 408 | 0 | 408 | 0 | 0 | 0 |
| state_v2 | doy | EXACT_VALUE | 408 | 0 | 408 | 0 | 0 | 0 |
| state_v2 | scenario | EXACT_VALUE | 408 | 0 | 408 | 0 | 0 | 0 |
| state_v2 | f107 | EXACT_VALUE | 408 | 0 | 408 | 0 | 0 | 0 |
| state_v2 | f107a | EXACT_VALUE | 408 | 0 | 408 | 0 | 0 | 0 |
| state_v2 | ap | EXACT_VALUE | 408 | 0 | 408 | 0 | 0 | 0 |
| state_v2 | source | EXACT_VALUE | 408 | 0 | 408 | 0 | 0 | 0 |
| state_v2 | evaluation | EXACT_VALUE | 408 | 0 | 408 | 0 | 0 | 0 |
| state_v2 | interp_max_rel_err_rho | EXACT_VALUE | 408 | 0 | 408 | 0 | 0 | 0 |
| state_v2 | lst_h | EXACT_VALUE | 408 | 0 | 408 | 0 | 0 | 0 |
| state_v2 | lon_deg | EXACT_VALUE | 408 | 0 | 408 | 0 | 0 | 0 |
| state_v2 | rho_kg_m3 | ULP_BOUNDED | 408 | 0 | 135 | 6.51e-24 | 2.12e-14 | 120 |
| state_v2 | n_N2_m3 | ULP_BOUNDED | 408 | 0 | 123 | 320 | 2.85e-14 | 202 |
| state_v2 | n_O2_m3 | ULP_BOUNDED | 408 | 0 | 117 | 12.6 | 2.85e-14 | 200 |
| state_v2 | n_O_m3 | ULP_BOUNDED | 408 | 0 | 122 | 176 | 2.85e-14 | 187 |
| state_v2 | n_He_m3 | ULP_BOUNDED | 408 | 0 | 96 | 0.531 | 2.13e-14 | 131 |
| state_v2 | n_Ar_m3 | ULP_BOUNDED | 408 | 0 | 103 | 1.58 | 2.13e-14 | 122 |
| state_v2 | n_N_m3 | ULP_BOUNDED | 408 | 0 | 105 | 7.56 | 2.84e-14 | 213 |
| state_v2 | n_total_m3 | ULP_BOUNDED | 408 | 0 | 18 | 288 | 1.85e-14 | 157 |
| state_v2 | T_K | ULP_BOUNDED | 408 | 0 | 102 | 5e-12 | 3.64e-15 | 30 |
| state_v2 | x_O | ULP_BOUNDED | 408 | 0 | 32 | 8.77e-15 | 2.94e-14 | 189 |
| state_v2 | x_N2 | ULP_BOUNDED | 408 | 0 | 29 | 8.66e-15 | 2.78e-14 | 202 |
| state_v2 | x_O2 | ULP_BOUNDED | 408 | 0 | 15 | 1.6e-15 | 3.29e-14 | 241 |
| state_v2 | x_N | ULP_BOUNDED | 408 | 0 | 10 | 6.04e-16 | 3.18e-14 | 271 |
| state_v2 | x_He | ULP_BOUNDED | 408 | 0 | 10 | 3.49e-16 | 2.97e-14 | 260 |
| state_v2 | x_Ar | ULP_BOUNDED | 408 | 0 | 11 | 1.7e-16 | 2.83e-14 | 196 |
| state_v2 | u_mer_quiet_m_s | ULP_BOUNDED | 408 | 0 | 108 | 8.53e-14 | 1.34e-14 | 88 |
| state_v2 | u_zon_quiet_m_s | ULP_BOUNDED | 408 | 0 | 107 | 8.53e-14 | 2.15e-14 | 160 |
| state_v2 | u_mer_dist_m_s | ULP_BOUNDED | 408 | 0 | 152 | 5.68e-14 | 1.83e-14 | 96 |
| state_v2 | u_zon_dist_m_s | ULP_BOUNDED | 408 | 0 | 148 | 5.68e-14 | 2.63e-14 | 192 |
| state_v2 | u_mer_m_s | ULP_BOUNDED | 408 | 0 | 119 | 8.53e-14 | 1.63e-14 | 128 |
| state_v2 | u_zon_m_s | ULP_BOUNDED | 408 | 0 | 128 | 1.14e-13 | 3.97e-14 | 320 |
| state_v2 | ap_hwm | EXACT_VALUE | 408 | 0 | 408 | 0 | 0 | 0 |
| state_v2 | wind_model | EXACT_VALUE | 408 | 0 | 408 | 0 | 0 | 0 |
| state_v2 | wind_source | EXACT_VALUE | 408 | 0 | 408 | 0 | 0 | 0 |
| state_v2 | wind_interp_max_abs_err_m_s | EXACT_VALUE | 408 | 0 | 408 | 0 | 0 | 0 |
| state_v2 | dataset_id | EXACT_VALUE | 408 | 0 | 408 | 0 | 0 | 0 |
| state_v2 | dataset_status | EXACT_VALUE | 408 | 0 | 408 | 0 | 0 | 0 |
| load_design_states | status | EXACT_VALUE | 4 | 0 | 4 | 0 | 0 | 0 |
| load_design_states | document (every leaf, key order) | EXACT_VALUE | 2 | 0 | 2 | 0 | 0 | 0 |
| design_state_set | status | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| design_state_set | n_states | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| design_state_set | required state ids in file order | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| design_state_set | selection lookup | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| design_state_set.state | key order | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| design_state_set.state | state_id | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| design_state_set.state | alt_km | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| design_state_set.state | scenario | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| design_state_set.state | f107 | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| design_state_set.state | f107a | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| design_state_set.state | ap | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| design_state_set.state | lat_deg | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| design_state_set.state | lst_h | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| design_state_set.state | lon_deg | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| design_state_set.state | doy | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| design_state_set.state | rho_kg_m3 | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| design_state_set.state | n_O_m3 | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| design_state_set.state | n_N2_m3 | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| design_state_set.state | n_O2_m3 | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| design_state_set.state | T_K | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| design_state_set.state | labels | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| design_state_set.state | evaluation | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| design_state_set.state | interp_max_rel_err_rho | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| design_state_set.state | nominal_mission_scenario | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| design_state_set.state | required | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| design_state_set.atm | key order | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| design_state_set.atm | fO | ULP_BOUNDED | 196 | 0 | 196 | 0 | 0 | 0 |
| design_state_set.atm | fN2 | ULP_BOUNDED | 196 | 0 | 196 | 0 | 0 | 0 |
| design_state_set.atm | fO2 | ULP_BOUNDED | 196 | 0 | 196 | 0 | 0 | 0 |
| design_state_set.atm | m_mean | ULP_BOUNDED | 196 | 0 | 196 | 0 | 0 | 0 |
| design_state_set.atm | n | ULP_BOUNDED | 196 | 0 | 196 | 0 | 0 | 0 |
| design_state_set.atm | V | ULP_BOUNDED | 196 | 0 | 196 | 0 | 0 | 0 |
| design_state_set.atm | flux_kg_m2_s | ULP_BOUNDED | 196 | 0 | 196 | 0 | 0 | 0 |
| design_state_set.atm | p_ambient_Pa | ULP_BOUNDED | 196 | 0 | 196 | 0 | 0 | 0 |
| design_state_set.atm | n_O | ULP_BOUNDED | 196 | 0 | 196 | 0 | 0 | 0 |
| design_state_set.atm | alt_km | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| design_state_set.atm | f107 | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| design_state_set.atm | f107a | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| design_state_set.atm | ap | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| design_state_set.atm | rho | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| design_state_set.atm | T | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| design_state_set.atm | state_id | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| design_state_set.atm | source | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| design_state_set.atm | V_basis | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| design_state_set.atm | orbit_basis | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| design_state_set.record | record() | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| design_state_set | CONS-D-03 /fO + fN2 + fO2 - 1/ (Rust) | ULP_BOUNDED | 196 | 0 | 118 | 2.22e-16 | 2.22e-16 | 1 |
| design_state_set | CONS-D-03 /n m_mean / rho - 1/ (Rust) | ULP_BOUNDED | 196 | 0 | 175 | 2.22e-16 | 2.22e-16 | 1 |
| orbit_load | status | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| orbit_load | dataset_sha256 | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| orbit_load | row_count | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| orbit_load | shape | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| orbit_load | scenario_order | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| orbit_load | grid | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| design_states_v2 | status | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| design_states_v2 | key order | EXACT_VALUE | 205 | 0 | 205 | 0 | 0 | 0 |
| design_states_v2 | design_state_set_id | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| design_states_v2 | version | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| design_states_v2 | dataset_id | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| design_states_v2 | dataset_sha256 | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| design_states_v2 | list length | EXACT_VALUE | 198 | 0 | 198 | 0 | 0 | 0 |
| design_states_v2 | latitude_band_deg | EXACT_VALUE | 2 | 0 | 2 | 0 | 0 | 0 |
| design_states_v2 | latitude_pool_step_deg | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| design_states_v2 | lat_refinement_sensitivity.fine_step_deg | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| design_states_v2 | lat_refinement_sensitivity.rho_kg_m3 | ULP_BOUNDED (display unit) | 1 | 0 | 1 | 0 | 0 | 0 |
| design_states_v2 | lat_refinement_sensitivity.x_O | ULP_BOUNDED (display unit) | 1 | 0 | 1 | 0 | 0 | 0 |
| design_states_v2 | lat_refinement_sensitivity.x_N2 | ULP_BOUNDED (display unit) | 1 | 0 | 1 | 0 | 0 | 0 |
| design_states_v2 | lat_refinement_sensitivity.x_O2 | ULP_BOUNDED (display unit) | 1 | 0 | 1 | 0 | 0 | 0 |
| design_states_v2 | lat_refinement_sensitivity.T_K | ULP_BOUNDED (display unit) | 1 | 0 | 1 | 0 | 0 | 0 |
| design_states_v2 | nominal_scenario | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| design_states_v2 | orbit_basis.status | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| design_states_v2 | orbit_basis.requirement_input | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| design_states_v2 | orbit_basis.inclination_deg | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| design_states_v2 | orbit_basis.local_time | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| design_states_v2 | orbit_basis.code_default_orbit | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| design_states_v2 | orbit_basis.real_orbit | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| design_states_v2 | supersedes.file | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| design_states_v2 | supersedes.sha256 | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| design_states_v2 | supersedes.relation | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| design_states_v2 | authority.A9.14 S9.8 OD3.path | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| design_states_v2 | authority.A9.14 S9.8 OD3.sha256 | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| design_states_v2 | authority.A9.17 ORBIT.path | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| design_states_v2 | authority.A9.17 ORBIT.sha256 | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| design_states_v2 | authority.A9.17 ORBIT.decision_key | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| design_states_v2 | authority.A9.17 ORBIT.answer | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| design_states_v2 | authority.A9.17 ORBIT.verbatim.path | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| design_states_v2 | authority.A9.17 ORBIT.verbatim.sha256 | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| design_states_v2 | authority.A9.17 ORBIT.verbatim.quote | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| design_states_v2 | producer | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| design_states_v2 | rule | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| design_states_v2 | n_states | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| design_states_v2 | states[*].alt_km | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| design_states_v2 | states[*].lat_deg | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| design_states_v2 | states[*].lst_h | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| design_states_v2 | states[*].lon_deg | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| design_states_v2 | states[*].doy | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| design_states_v2 | states[*].scenario | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| design_states_v2 | states[*].f107 | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| design_states_v2 | states[*].f107a | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| design_states_v2 | states[*].ap | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| design_states_v2 | states[*].rho_kg_m3 | ULP_BOUNDED | 196 | 0 | 133 | 3e-24 | 7.16e-15 | 59 |
| design_states_v2 | states[*].n_N2_m3 | ULP_BOUNDED | 196 | 0 | 137 | 88 | 1.42e-14 | 77 |
| design_states_v2 | states[*].n_O2_m3 | ULP_BOUNDED | 196 | 0 | 139 | 5.12 | 7.31e-15 | 62 |
| design_states_v2 | states[*].n_O_m3 | ULP_BOUNDED | 196 | 0 | 153 | 118 | 7.21e-15 | 61 |
| design_states_v2 | states[*].n_He_m3 | ULP_BOUNDED | 196 | 0 | 122 | 0.344 | 1.08e-14 | 87 |
| design_states_v2 | states[*].n_Ar_m3 | ULP_BOUNDED | 196 | 0 | 114 | 1.25 | 1.07e-14 | 59 |
| design_states_v2 | states[*].n_N_m3 | ULP_BOUNDED | 196 | 0 | 123 | 5.62 | 1.06e-14 | 63 |
| design_states_v2 | states[*].n_total_m3 | ULP_BOUNDED | 196 | 0 | 99 | 144 | 7.21e-15 | 58 |
| design_states_v2 | states[*].T_K | ULP_BOUNDED | 196 | 0 | 104 | 3.18e-12 | 1.94e-15 | 15 |
| design_states_v2 | states[*].x_O | ULP_BOUNDED | 196 | 0 | 103 | 3.44e-15 | 1.22e-14 | 71 |
| design_states_v2 | states[*].x_N2 | ULP_BOUNDED | 196 | 0 | 97 | 3.55e-15 | 1.09e-14 | 90 |
| design_states_v2 | states[*].x_O2 | ULP_BOUNDED | 196 | 0 | 90 | 7.01e-16 | 1.34e-14 | 113 |
| design_states_v2 | states[*].x_N | ULP_BOUNDED | 196 | 0 | 75 | 4.58e-16 | 1.35e-14 | 92 |
| design_states_v2 | states[*].x_He | ULP_BOUNDED | 196 | 0 | 80 | 3.89e-16 | 1.3e-14 | 107 |
| design_states_v2 | states[*].x_Ar | ULP_BOUNDED | 196 | 0 | 72 | 9.37e-17 | 1.14e-14 | 90 |
| design_states_v2 | states[*].source | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| design_states_v2 | states[*].evaluation | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| design_states_v2 | states[*].interp_max_rel_err_rho | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| design_states_v2 | states[*].labels | EXACT_VALUE | 218 | 0 | 218 | 0 | 0 | 0 |
| design_states_v2 | states[*].state_id | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| design_states_v2 | states[*].required | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| design_states_v2 | states[*].nominal_mission_scenario | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| design_states_v2 | INV-D-01 Rust vs frozen file within DESIGN_V2_REL_TOL | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| design_states_v2 | INV-D-01 Python re-derivation byte-identical to the frozen file | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| design_states_v2 | INV-D-01 frozen ids == Rust ids | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| execution | status | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| execution | n_states | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| execution | INV-D-02 n_states == 196 == records | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| execution | INV-D-02 hashes | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| execution | per-state state_id (file order) | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| execution | per-state status | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| execution | INV-D-02 every state EVALUATED | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| execution.environment | key order | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| execution.environment | fO | ULP_BOUNDED | 196 | 0 | 196 | 0 | 0 | 0 |
| execution.environment | fN2 | ULP_BOUNDED | 196 | 0 | 196 | 0 | 0 | 0 |
| execution.environment | fO2 | ULP_BOUNDED | 196 | 0 | 196 | 0 | 0 | 0 |
| execution.environment | m_mean | ULP_BOUNDED | 196 | 0 | 196 | 0 | 0 | 0 |
| execution.environment | n | ULP_BOUNDED | 196 | 0 | 196 | 0 | 0 | 0 |
| execution.environment | V | ULP_BOUNDED | 196 | 0 | 196 | 0 | 0 | 0 |
| execution.environment | flux_kg_m2_s | ULP_BOUNDED | 196 | 0 | 196 | 0 | 0 | 0 |
| execution.environment | p_ambient_Pa | ULP_BOUNDED | 196 | 0 | 196 | 0 | 0 | 0 |
| execution.environment | n_O | ULP_BOUNDED | 196 | 0 | 196 | 0 | 0 | 0 |
| execution.environment | alt_km | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| execution.environment | f107 | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| execution.environment | f107a | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| execution.environment | ap | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| execution.environment | rho | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| execution.environment | T | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| execution.environment | state_id | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| execution.environment | source | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| execution.environment | V_basis | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| execution.environment | orbit_basis | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| execution | reproduction.evaluation | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| execution | reproduction.reproduced | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| execution.wind | key order | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| execution.wind | u_mer_quiet_m_s | ULP_BOUNDED | 196 | 0 | 105 | 2.84e-14 | 5.53e-16 | 4 |
| execution.wind | u_zon_quiet_m_s | ULP_BOUNDED | 196 | 0 | 102 | 2.84e-14 | 5.8e-16 | 4 |
| execution.wind | u_mer_dist_m_s | ULP_BOUNDED | 196 | 0 | 150 | 2.84e-14 | 1.16e-15 | 8 |
| execution.wind | u_zon_dist_m_s | ULP_BOUNDED | 196 | 0 | 139 | 5.68e-14 | 3.5e-16 | 2 |
| execution.wind | u_mer_m_s | ULP_BOUNDED | 196 | 0 | 118 | 5.68e-14 | 1.63e-14 | 128 |
| execution.wind | u_zon_m_s | ULP_BOUNDED | 196 | 0 | 109 | 5.68e-14 | 2.43e-15 | 16 |
| execution.wind | ap_hwm | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| execution.wind | wind_model | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| execution.wind | wind_source | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| execution.wind | wind_interp_max_abs_err_m_s | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| execution | VS-D-04 wind labels (Rust) | EXACT_VALUE | 196 | 0 | 196 | 0 | 0 | 0 |
| check | status | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| check | ok | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |

## Domain / error parity

64 status-relevant vectors, 0 mismatches.
* DE-D-01-orbit_state (orbit_state): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-01-wind (wind): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-01-state_v2 (state_v2): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-02-orbit_state (orbit_state): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-02-wind (wind): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-02-state_v2 (state_v2): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-03-orbit_state (orbit_state): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-03-wind (wind): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-03-state_v2 (state_v2): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-04-orbit_state (orbit_state): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-04-wind (wind): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-04-state_v2 (state_v2): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-05-orbit_state (orbit_state): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-05-wind (wind): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-05-state_v2 (state_v2): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-06-orbit_state (orbit_state): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-06-wind (wind): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-06-state_v2 (state_v2): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-07-orbit_state (orbit_state): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-07-wind (wind): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-07-state_v2 (state_v2): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-08-orbit_state (orbit_state): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-08-wind (wind): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-08-state_v2 (state_v2): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-09-orbit_state (orbit_state): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-09-wind (wind): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-09-state_v2 (state_v2): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-10-orbit_state (orbit_state): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-10-wind (wind): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-10-state_v2 (state_v2): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-11-orbit_state (orbit_state): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-11-wind (wind): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-11-state_v2 (state_v2): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-12-orbit_state (orbit_state): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-12-wind (wind): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-12-state_v2 (state_v2): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-13-orbit_state (orbit_state): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-13-wind (wind): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-13-state_v2 (state_v2): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-14-orbit_state (orbit_state): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-14-wind (wind): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-14-state_v2 (state_v2): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-15 (orbit_node_state): Python OUT_OF_DOMAIN (IndexError), Rust OUT_OF_DOMAIN - ok
* DE-D-16 (orbit_node_state): Python OUT_OF_DOMAIN (IndexError), Rust OUT_OF_DOMAIN - ok
* DE-D-17 (orbit_node_state): Python OUT_OF_DOMAIN (KeyError), Rust OUT_OF_DOMAIN - ok
* DE-D-18 (orbit_states): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-19 (orbit_states): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-20 (orbit_states): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-21 (orbit_states): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-22 (orbit_states): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-23 (orbit_states): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-24 (orbit_states): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-25 (orbit_states): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-26 (orbit_states): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-27 (orbit_states): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-28 (orbit_states): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-29 (orbit_states): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-30 (orbit_states): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-31 (orbit_states): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-32 (orbit_states): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-33 (orbit_states): Python OUT_OF_DOMAIN (OverflowError), Rust OUT_OF_DOMAIN - ok
* DE-D-34 (orbit_states): Python OUT_OF_DOMAIN (OverflowError), Rust OUT_OF_DOMAIN - ok
* DE-D-35 (load_design_states): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-D-36 (load_design_states): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok

| tree | entry | Python | Rust | registered Python | registered Rust | ok |
|---|---|---|---|---|---|---|
| RF-D-01 | orbit_load | FileNotFoundError | MODEL_ERROR | FileNotFoundError | MODEL_ERROR | yes |
| RF-D-01 | wind_load | FileNotFoundError | MODEL_ERROR | FileNotFoundError | MODEL_ERROR | yes |
| RF-D-01 | load_design_states(v2) | FileNotFoundError | MODEL_ERROR | FileNotFoundError | MODEL_ERROR | yes |
| RF-D-01 | design_state_set | returns | EVALUATED | returns | EVALUATED | yes |
| RF-D-01 | execution | FileNotFoundError | MODEL_ERROR | FileNotFoundError | MODEL_ERROR | yes |
| RF-D-01 | check | FileNotFoundError | MODEL_ERROR | FileNotFoundError | MODEL_ERROR | yes |
| RF-D-02 | orbit_load | RuntimeError | MODEL_ERROR | RuntimeError | MODEL_ERROR | yes |
| RF-D-02 | wind_load | RuntimeError | MODEL_ERROR | RuntimeError | MODEL_ERROR | yes |
| RF-D-02 | load_design_states(v2) | RuntimeError | MODEL_ERROR | RuntimeError | MODEL_ERROR | yes |
| RF-D-02 | design_state_set | returns | EVALUATED | returns | EVALUATED | yes |
| RF-D-02 | execution | RuntimeError | MODEL_ERROR | RuntimeError | MODEL_ERROR | yes |
| RF-D-02 | check | ok=False | ok=False | returns ok=False | ok=False | yes |
| RF-D-03 | orbit_load | FileNotFoundError | MODEL_ERROR | FileNotFoundError | MODEL_ERROR | yes |
| RF-D-03 | wind_load | FileNotFoundError | MODEL_ERROR | FileNotFoundError | MODEL_ERROR | yes |
| RF-D-03 | load_design_states(v2) | FileNotFoundError | MODEL_ERROR | FileNotFoundError | MODEL_ERROR | yes |
| RF-D-03 | design_state_set | DesignStateSetError | MODEL_ERROR | DesignStateSetError | MODEL_ERROR | yes |
| RF-D-03 | execution | DesignStateSetError | MODEL_ERROR | DesignStateSetError | MODEL_ERROR | yes |
| RF-D-03 | check | FileNotFoundError | MODEL_ERROR | FileNotFoundError | MODEL_ERROR | yes |
| RF-D-04 | orbit_load | returns | EVALUATED | returns | EVALUATED | yes |
| RF-D-04 | wind_load | returns | EVALUATED | returns | EVALUATED | yes |
| RF-D-04 | load_design_states(v2) | RuntimeError | MODEL_ERROR | RuntimeError | MODEL_ERROR | yes |
| RF-D-04 | design_state_set | DesignStateSetError | MODEL_ERROR | DesignStateSetError | MODEL_ERROR | yes |
| RF-D-04 | execution | DesignStateSetError | MODEL_ERROR | DesignStateSetError | MODEL_ERROR | yes |
| RF-D-04 | check | ok=False | ok=False | returns ok=False | ok=False | yes |
| RF-D-05 | orbit_load | returns | EVALUATED | returns | EVALUATED | yes |
| RF-D-05 | wind_load | returns | EVALUATED | returns | EVALUATED | yes |
| RF-D-05 | load_design_states(v2) | FileNotFoundError | MODEL_ERROR | FileNotFoundError | MODEL_ERROR | yes |
| RF-D-05 | design_state_set | DesignStateSetError | MODEL_ERROR | DesignStateSetError | MODEL_ERROR | yes |
| RF-D-05 | execution | DesignStateSetError | MODEL_ERROR | DesignStateSetError | MODEL_ERROR | yes |
| RF-D-05 | check | ok=False | ok=False | returns ok=False | ok=False | yes |
| RF-D-06 | orbit_load | returns | EVALUATED | returns | EVALUATED | yes |
| RF-D-06 | wind_load | FileNotFoundError | MODEL_ERROR | FileNotFoundError | MODEL_ERROR | yes |
| RF-D-06 | load_design_states(v2) | returns | EVALUATED | returns | EVALUATED | yes |
| RF-D-06 | design_state_set | returns | EVALUATED | returns | EVALUATED | yes |
| RF-D-06 | execution | FileNotFoundError | MODEL_ERROR | FileNotFoundError | MODEL_ERROR | yes |
| RF-D-06 | check | ok=True | ok=True | returns ok=True | ok=True | yes |
| RF-D-07 | orbit_load | returns | EVALUATED | returns | EVALUATED | yes |
| RF-D-07 | wind_load | RuntimeError | MODEL_ERROR | RuntimeError | MODEL_ERROR | yes |
| RF-D-07 | load_design_states(v2) | returns | EVALUATED | returns | EVALUATED | yes |
| RF-D-07 | design_state_set | returns | EVALUATED | returns | EVALUATED | yes |
| RF-D-07 | execution | RuntimeError | MODEL_ERROR | RuntimeError | MODEL_ERROR | yes |
| RF-D-07 | check | ok=True | ok=True | returns ok=True | ok=True | yes |
| RF-D-08 | orbit_load | returns | EVALUATED | returns | EVALUATED | yes |
| RF-D-08 | wind_load | FileNotFoundError | MODEL_ERROR | FileNotFoundError | MODEL_ERROR | yes |
| RF-D-08 | load_design_states(v2) | returns | EVALUATED | returns | EVALUATED | yes |
| RF-D-08 | design_state_set | returns | EVALUATED | returns | EVALUATED | yes |
| RF-D-08 | execution | FileNotFoundError | MODEL_ERROR | FileNotFoundError | MODEL_ERROR | yes |
| RF-D-08 | check | ok=True | ok=True | returns ok=True | ok=True | yes |
| RF-D-09 | orbit_load | returns | MODEL_ERROR | returns (sidecar not hash-checked) | MODEL_ERROR | yes |
| RF-D-09 | wind_load | returns | MODEL_ERROR | returns | MODEL_ERROR | yes |
| RF-D-09 | load_design_states(v2) | returns | MODEL_ERROR | returns (record matches) | MODEL_ERROR | yes |
| RF-D-09 | design_state_set | DesignStateSetError | MODEL_ERROR | DesignStateSetError | MODEL_ERROR | yes |
| RF-D-09 | execution | DesignStateSetError | MODEL_ERROR | DesignStateSetError | MODEL_ERROR | yes |
| RF-D-09 | check | ok=False | MODEL_ERROR | returns ok=False | MODEL_ERROR | yes |
| RF-D-10 | orbit_load | returns | MODEL_ERROR | returns (the reference reads no model set) | MODEL_ERROR | yes |
| RF-D-10 | wind_load | returns | MODEL_ERROR | returns | MODEL_ERROR | yes |
| RF-D-10 | load_design_states(v2) | returns | MODEL_ERROR | returns | MODEL_ERROR | yes |
| RF-D-10 | design_state_set | returns | MODEL_ERROR | returns | MODEL_ERROR | yes |
| RF-D-10 | execution | returns | MODEL_ERROR | returns | MODEL_ERROR | yes |
| RF-D-10 | check | ok=True | MODEL_ERROR | returns ok=True | MODEL_ERROR | yes |

## Invariants

* Rust two processes byte-identical: True (stdout sha256 `3e4c757a4da6dc34...`); Python two evaluations equal: True.
* Governing hashes equal and registered: True.

## Performance (reported, never a criterion)

* PERF-D-01: Python 1.423 s, Rust 0.871 s (median of 3; speed-up 1.6x; Python: dataset loaded; Rust: CLI process including the verified load).
* PERF-D-02: Python 2.081 s, Rust 1.086 s (median of 3; speed-up 1.9x; both include the verified loads).
* PERF-D-03: Python 0.452 s, Rust 0.470 s (median of 3; speed-up 1.0x; Python: dataset loaded; Rust: CLI process including the verified load).

## Notes

* harness: the contracts say the harness is committed 'after this contract and before any comparison'. It was developed with development-seed comparisons (never scored, no report) and committed before the single scoring run; every scored generator, tolerance and decision rule is the registered one. Recorded as a disclosure, not a change of the contract
* out of scope and still PYTHON_REFERENCE: atmosphere_orbit_v2 relative_flow / flow_state / orbit_states (not needed by the 196-state execution); SC-WP-01 admission needs their own contract or an owner retirement

## Ledger update requested

* C-ABEP_SIM_ATMOSPHERE_ORBIT_PY: ADMITTED
* C-ABEP_SIM_ATMOSPHERE_ORBIT_V2_PY: PARTIAL (load, wind, state admitted)
* C-ABEP_SIM_DESIGN_INTAKE_SYNTHESIS_PY: KERNEL_ADMITTED (RM-R17) for load_design_state_set, DesignState.atm / record, required_states; module stays PYTHON_REFERENCE (SC-WP-02)

Parity is not physics validation, not a gate PASS and not a change of any frozen dataset.
