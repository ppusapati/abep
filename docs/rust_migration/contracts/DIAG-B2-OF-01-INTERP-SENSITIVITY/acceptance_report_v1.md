# Acceptance report v1 - ACCEPT-DIAG-B2-OF-01-INTERP-SENSITIVITY-V1

Verdict: **NOT_ACCEPTED**.

* Preregistration `docs/rust_migration/contracts/DIAG-B2-OF-01-INTERP-SENSITIVITY/acceptance_prereg_v1.json` sha256 `c1855b3b32f74028c29851235d52e61694b49210b4e0623a4d3eaaab5e3f9314`, committed in `1f9248341a0f` before any diagnostic code.
* Rust commit `4bb79e79d083`.
* cargo test: exit 0; at01_grid_node_is_single_valued_and_equals_the_node_row ok, at02_survey_default_points_are_rounding_level ok, at03_survey_maxima_are_reproduced_and_non_conforming ok, at04_one_ulp_off_the_face_is_not_on_it ok, at05_cell_interior_and_outer_faces_are_single_valued ok, at06_out_of_domain_has_no_value ok, at07_grid_and_face_cross_checks_fail_closed ok, at08_f7_f8_candidate_points_are_grid_nodes_and_unused_by_the_chain ok, at10_records_are_deterministic ok, result: 0.53s

## Registered points (Rust classification vs an independent Python classification from the frozen CSV)

| case | table | point | Rust | Python | status | class | max spread |
|---|---|---|---|---|---|---|---|
| AT-01 | maxwell | [5.0, 0.8, 0.5, 2.0] | GRID_NODE | GRID_NODE | NUMERICAL_INTERPOLATION_SENSITIVITY | ROUNDING_LEVEL | 3.3633053428405635e-16 |
| AT-01 | cll | [5.0, 0.8, 0.5, 2.0] | GRID_NODE | GRID_NODE | NUMERICAL_INTERPOLATION_SENSITIVITY | ROUNDING_LEVEL | 3.4512156270559026e-16 |
| AT-02 | maxwell | [10.0, 0.85, 0.5, 0.0] | GRID_EDGE | GRID_EDGE | NUMERICAL_INTERPOLATION_SENSITIVITY | ROUNDING_LEVEL | 3.2349481898836653e-16 |
| AT-02 | cll | [10.0, 0.85, 0.5, 0.0] | GRID_EDGE | GRID_EDGE | NUMERICAL_INTERPOLATION_SENSITIVITY | ROUNDING_LEVEL | 3.2714909654049795e-16 |
| AT-02 | maxwell | [5.0, 0.85, 0.8, 0.0] | GRID_EDGE | GRID_EDGE | NUMERICAL_INTERPOLATION_SENSITIVITY | ROUNDING_LEVEL | 2.6808826124934727e-16 |
| AT-02 | cll | [5.0, 0.85, 0.8, 0.0] | GRID_EDGE | GRID_EDGE | NUMERICAL_INTERPOLATION_SENSITIVITY | ROUNDING_LEVEL | 3.0903217232691373e-16 |
| AT-02 | maxwell | [10.0, 0.85, 0.95, 0.0] | FACE_INTERIOR | FACE_INTERIOR | NUMERICAL_INTERPOLATION_SENSITIVITY | ROUNDING_LEVEL | 1.8894056475075712e-16 |
| AT-02 | cll | [10.0, 0.85, 0.95, 0.0] | FACE_INTERIOR | FACE_INTERIOR | NUMERICAL_INTERPOLATION_SENSITIVITY | ROUNDING_LEVEL | 1.8894056475075712e-16 |
| AT-02 | maxwell | [3.0, 0.85, 0.5, 0.0] | GRID_EDGE | GRID_EDGE | NUMERICAL_INTERPOLATION_SENSITIVITY | ROUNDING_LEVEL | 1.5721869784992192e-16 |
| AT-02 | cll | [3.0, 0.85, 0.5, 0.0] | GRID_EDGE | GRID_EDGE | NUMERICAL_INTERPOLATION_SENSITIVITY | ROUNDING_LEVEL | 1.5721869784992192e-16 |
| AT-02 | maxwell | [5.0, 0.85, 0.8, 2.0] | GRID_EDGE | GRID_EDGE | NUMERICAL_INTERPOLATION_SENSITIVITY | ROUNDING_LEVEL | 0.0 |
| AT-02 | cll | [5.0, 0.85, 0.8, 2.0] | GRID_EDGE | GRID_EDGE | NUMERICAL_INTERPOLATION_SENSITIVITY | ROUNDING_LEVEL | 0.0 |
| AT-03 | maxwell | [8.227784022690075, 0.8374126887937825, 0.6952669150405878, 2.0] | FACE_INTERIOR | FACE_INTERIOR | NUMERICAL_INTERPOLATION_SENSITIVITY | NON_CONFORMING | 0.047272324792362125 |
| AT-03 | cll | [8.227784022690075, 0.8374126887937825, 0.6952669150405878, 2.0] | FACE_INTERIOR | FACE_INTERIOR | NUMERICAL_INTERPOLATION_SENSITIVITY | NON_CONFORMING | 0.09016358632032051 |
| AT-03 | cll | [14.915437578732714, 0.8108001576950183, 0.048672246638759575, 2.0] | FACE_INTERIOR | FACE_INTERIOR | NUMERICAL_INTERPOLATION_SENSITIVITY | NON_CONFORMING | 0.1733934754224051 |
| AT-03 | cll | [13.642166426737925, 0.8551641047390511, 0.38885151921681604, 2.0] | FACE_INTERIOR | FACE_INTERIOR | NUMERICAL_INTERPOLATION_SENSITIVITY | NON_CONFORMING | 0.13383912101555542 |
| AT-03 | maxwell | [15.193095968023385, 0.8484514633109874, 0.2, 3.880158262223903] | FACE_INTERIOR | FACE_INTERIOR | NUMERICAL_INTERPOLATION_SENSITIVITY | NON_CONFORMING | 0.03729597039010955 |
| AT-05 | maxwell | [4.0, 0.85, 0.35, 1.0] | NOT_ON_KNOWN_FACE | NOT_ON_KNOWN_FACE | NOT_APPLICABLE | None | None |
| AT-05 | cll | [4.0, 0.85, 0.35, 1.0] | NOT_ON_KNOWN_FACE | NOT_ON_KNOWN_FACE | NOT_APPLICABLE | None | None |
| AT-05 | maxwell | [4.0, 0.8, 0.35, 1.0] | NOT_ON_KNOWN_FACE | NOT_ON_KNOWN_FACE | NOT_APPLICABLE | None | None |
| AT-05 | cll | [4.0, 0.8, 0.35, 1.0] | NOT_ON_KNOWN_FACE | NOT_ON_KNOWN_FACE | NOT_APPLICABLE | None | None |
| AT-05 | maxwell | [20.0, 0.9, 1.0, 5.0] | NOT_ON_KNOWN_FACE | NOT_ON_KNOWN_FACE | NOT_APPLICABLE | None | None |
| AT-05 | cll | [20.0, 0.9, 1.0, 5.0] | NOT_ON_KNOWN_FACE | NOT_ON_KNOWN_FACE | NOT_APPLICABLE | None | None |
| AT-06 | maxwell | [2.0, 0.85, 0.5, 0.0] | OUT_OF_DOMAIN | OUT_OF_DOMAIN | OUT_OF_DOMAIN | None | None |
| AT-06 | maxwell | [20.0000001, 0.85, 0.5, 0.0] | OUT_OF_DOMAIN | OUT_OF_DOMAIN | OUT_OF_DOMAIN | None | None |
| AT-06 | maxwell | ['NaN', 0.85, 0.5, 0.0] | OUT_OF_DOMAIN | OUT_OF_DOMAIN | OUT_OF_DOMAIN | None | None |
| AT-04 | cll | [14.915437578732714, 0.8108001576950183, 0.048672246638759575, 2.0000000000000004] | NOT_ON_KNOWN_FACE | NOT_ON_KNOWN_FACE | NOT_APPLICABLE | None | None |

## Survey maxima (finding B2-OF-01)

| field | table | species | survey | Rust | abs diff |
|---|---|---|---|---|---|
| eta_c | maxwell | N2 | 0.03768632268222069 | 0.03768632268222089 | 2.01e-16 |
| C_D | cll | O | 0.002217463318732964 | 0.002217463318732822 | 1.42e-16 |
| CR_passive | cll | N2 | 0.1733934754224049 | 0.1733934754224051 | 1.94e-16 |
| K_back | cll | O2 | 0.061172634747115436 | 0.06117263474711523 | 2.08e-16 |
| mass_kg | maxwell | N2 | 0.03729597039010955 | 0.03729597039010955 | 0.00e+00 |

AT-10 determinism (two evaluations of every registered point identical): True


## F7 / F8 chain application (AT-08)

* {'interpolant_used_by_chain': False, 'face_geometry_counts': {'GRID_NODE': 128, 'NOT_ON_KNOWN_FACE': 32}, 'n_points': 160, 'n_non_conforming': 0, 'grid_node_sensitivity_classes': ['ROUNDING_LEVEL']}
* prediction holds: True

Software verification of a numerical diagnostic, not physics validation, not a change of the frozen surface and not a gate PASS.
