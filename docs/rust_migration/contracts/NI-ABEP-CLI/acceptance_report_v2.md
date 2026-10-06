# abep CLI acceptance v2: ACCEPTED

Generated from `acceptance_report_v2.json` (do not edit). Preregistration `docs/rust_migration/contracts/NI-ABEP-CLI/acceptance_v2.json` (sha256 `9d0c778def95ff2779a2fdf3f923a1e8ee697349198b716a0ee3049fff563f85`).

* Run: 2026-10-06T14:06:14Z at `58477abe3159cd4e727e9e5c6ac71c310a7a1185` (tracked tree dirty: false), rustc 1.94.1 (e408947bf 2026-03-25), binary `abep` (dev profile, sha256 `c76186bac4c73c97d2bbae7f6be51b286071a3a5103a1cc94f66285c36f4d97a`).
* Cases: 26 ; meeting expectation 26 ; process runs 59.
* Determinism: DET-RUN 11 / DET-THREADS 11 command cases hold; DET-ENV-CRATE true.
* Static: STATIC-DEP true (48 packages in the closure; forbidden []; dependents []); STATIC-NOPY true.

| case | argv | expected (status / exit / reason) | runs: exit, status, reason | meets |
|---|---|---|---|---|
| CMD-01 | `config check` | EVALUATED / 0 / null | R1 0 EVALUATED null; R2 0 EVALUATED null; R3 0 EVALUATED null; R4 0 EVALUATED null | yes |
| CMD-02 | `provenance verify` | EVALUATED / 0 / null | R1 0 EVALUATED null; R2 0 EVALUATED null; R3 0 EVALUATED null; R4 0 EVALUATED null | yes |
| CMD-03 | `env run-design-states` | EVALUATED / 0 / null | R1 0 EVALUATED null; R2 0 EVALUATED null; R3 0 EVALUATED null; R4 0 EVALUATED null | yes |
| CMD-04 | `intake surface-v1 --state ds2:ECSS_LT_HIGH:alt180:lat+37.0000:lst21:lon240:doy47 --scattering maxwell --l-over-d 10 --phi 0.9 --alpha 0.5 --theta-deg 0` | EVALUATED / 0 / null | R1 0 EVALUATED null; R2 0 EVALUATED null; R3 0 EVALUATED null; R4 0 EVALUATED null | yes |
| CMD-05 | `drag statewise --area-m2 0.5 --l-over-d 10 --phi 0.9 --scenario maxwell_a0.5` | NOT_EVALUATED / 10 / null | R1 10 NOT_EVALUATED CRATE_STATUS; R2 10 NOT_EVALUATED CRATE_STATUS; R3 10 NOT_EVALUATED CRATE_STATUS; R4 10 NOT_EVALUATED CRATE_STATUS | yes |
| CMD-06 | `mass rollup` | INCOMPLETE_EVIDENCE / 11 / null | R1 11 INCOMPLETE_EVIDENCE CRATE_STATUS; R2 11 INCOMPLETE_EVIDENCE CRATE_STATUS; R3 11 INCOMPLETE_EVIDENCE CRATE_STATUS; R4 11 INCOMPLETE_EVIDENCE CRATE_STATUS | yes |
| CMD-07 | `power ledger` | INCOMPLETE_EVIDENCE / 11 / null | R1 11 INCOMPLETE_EVIDENCE CRATE_STATUS; R2 11 INCOMPLETE_EVIDENCE CRATE_STATUS; R3 11 INCOMPLETE_EVIDENCE CRATE_STATUS; R4 11 INCOMPLETE_EVIDENCE CRATE_STATUS | yes |
| CMD-08 | `hall status` | NOT_EVALUATED / 10 / null | R1 10 NOT_EVALUATED CRATE_STATUS; R2 10 NOT_EVALUATED CRATE_STATUS; R3 10 NOT_EVALUATED CRATE_STATUS; R4 10 NOT_EVALUATED CRATE_STATUS | yes |
| CMD-09 | `hall pin-check` | EVALUATED / 0 / null | R1 0 EVALUATED null; R2 0 EVALUATED null; R3 0 EVALUATED null; R4 0 EVALUATED null | yes |
| CMD-10 | `icp status --supply-mode AIR_PRIMARY` | INCOMPLETE_EVIDENCE / 11 / null | R1 11 INCOMPLETE_EVIDENCE CRATE_STATUS; R2 11 INCOMPLETE_EVIDENCE CRATE_STATUS; R3 11 INCOMPLETE_EVIDENCE CRATE_STATUS; R4 11 INCOMPLETE_EVIDENCE CRATE_STATUS | yes |
| CMD-11 | `icp status --supply-mode XE_CONTINGENCY` | INCOMPLETE_EVIDENCE / 11 / null | R1 11 INCOMPLETE_EVIDENCE CRATE_STATUS; R2 11 INCOMPLETE_EVIDENCE CRATE_STATUS; R3 11 INCOMPLETE_EVIDENCE CRATE_STATUS; R4 11 INCOMPLETE_EVIDENCE CRATE_STATUS | yes |
| REF-01 | `env run-design-states` | MODEL_ERROR / 4 / CONFIG_MANIFEST_UNVERIFIED | R1 4 MODEL_ERROR CONFIG_MANIFEST_UNVERIFIED | yes |
| REF-02 | `config check` | MODEL_ERROR / 13 / CONFIG_BUILD_STALE | R1 13 MODEL_ERROR CONFIG_BUILD_STALE | yes |
| REF-03 | `env run-design-states` | MODEL_ERROR / 13 / CRATE_ERROR | R1 13 MODEL_ERROR CRATE_ERROR | yes |
| REF-04 | `hall status` | MODEL_ERROR / 4 / RUN_RECORD_UNAVAILABLE | R1 4 MODEL_ERROR RUN_RECORD_UNAVAILABLE | yes |
| REF-05 | `intake surface-v1 --state ds2:ECSS_LT_HIGH:alt180:lat+37.0000:lst21:lon240:doy47 --scattering maxwell --l-over-d 10 --phi 0.9 --alpha 0.5 --theta-deg 0` | MODEL_ERROR / 13 / CRATE_ERROR | R1 13 MODEL_ERROR CRATE_ERROR | yes |
| REF-06 | `intake surface-v1 --state ds2:NOT_A_REGISTERED_STATE --scattering maxwell --l-over-d 10 --phi 0.9 --alpha 0.5 --theta-deg 0` | NOT_EVALUATED / 3 / UNREGISTERED_INPUT | R1 3 NOT_EVALUATED UNREGISTERED_INPUT | yes |
| REF-07 | `icp status --supply-mode EM_N2` | NOT_EVALUATED / 3 / UNREGISTERED_INPUT | R1 3 NOT_EVALUATED UNREGISTERED_INPUT | yes |
| REF-08 | `intake surface-v1 --state ds2:ECSS_LT_HIGH:alt180:lat+37.0000:lst21:lon240:doy47 --scattering maxwell --l-over-d 25 --phi 0.9 --alpha 0.5 --theta-deg 0` | OUT_OF_DOMAIN / 12 / CRATE_ERROR | R1 12 OUT_OF_DOMAIN CRATE_ERROR | yes |
| REF-09 | `drag statewise --area-m2 0.5 --l-over-d 7 --phi 0.9 --scenario maxwell_a0.5` | OUT_OF_DOMAIN / 12 / CRATE_ERROR | R1 12 OUT_OF_DOMAIN CRATE_ERROR | yes |
| REF-10 | `hall pin-check` | NOT_EVALUATED / 10 / COMPONENT_ADMISSION_UNVERIFIED | R1 10 NOT_EVALUATED COMPONENT_ADMISSION_UNVERIFIED | yes |
| REF-11 | `hall status` | MODEL_ERROR / 4 / REPOSITORY_NOT_FOUND | R1 4 MODEL_ERROR REPOSITORY_NOT_FOUND | yes |
| REF-12 | `sweep` | null / 2 / null | R1 2 null null | yes |
| REF-13 | `drag statewise --area-m2 abc --l-over-d 10 --phi 0.9 --scenario maxwell_a0.5` | null / 2 / null | R1 2 null null | yes |
| REF-14 | `hall status` | null / 2 / null | R1 2 null null | yes |
| REF-15 | `hall status` | null / 5 / null | R1 5 null null | yes |

Ledger update requested: NI-ABEP-CLI -> ACCEPTED in docs/rust_migration/migration_state_v1.json (evidence: this report); ADMITTED after the CI determinism job (CI_PLAN § 5) lands
