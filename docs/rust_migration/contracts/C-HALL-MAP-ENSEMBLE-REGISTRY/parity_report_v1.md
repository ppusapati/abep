# C-HALL-MAP-ENSEMBLE-REGISTRY parity report v1

Generated from `parity_report_v1.json` (contract `docs/rust_migration/contracts/C-HALL-MAP-ENSEMBLE-REGISTRY/parity_prereg_v1.json`, sha256 `aa0910d9aaf32964efbdf7c25a5a92d3ae87a4a91ef7ea70cddd3344f680c88e`).

**Verdict: PARITY_PASS. Admission: ADMITTED** (cargo fmt / clippy / test gate: pass, 255 tests passed, 2 ignored = registered platform tests).

## What was compared

The unmodified Python reference (`abep_sim/hall_map.py`, `hall_ensemble.py`, `hallmap_registry.py`, `design/architecture_optimizer.py::hall_response_status`) and the Rust crate `abep-hall` (binary `abep-hall-cases`) executed every registered step on byte-identical case trees.

* Commit: `a8f906c9f721427feb7646cef6414779800bc093` (Python reference and Rust).
* Cases: 404 (164 registered + 240 random maps, scoring seed 3030373969277244664); steps compared: 522; cases agreeing: 404.
* Interpolated floats compared (ULP_BOUNDED): 30061; bitwise identical: 30061 (information only).
* Disagreements: none.

## Decision rule

| rule | holds |
|---|---|
| D1_every_step_agrees | True |
| INV-01_rust_deterministic | True |
| INV-02_records_read_only_no_tmp | True |
| INV-03_scoring_tree_unchanged | True |
| INV-04_governed_state | True |
| INV-05_synthetic_label | True |
| cargo_gate | True |
| reference_files_match | True |

## By group

| group | cases | agree | steps | Python refusal steps |
|---|---|---|---|---|
| SCHEMA | 7 | 7 | 11 | 3 |
| PIN | 12 | 12 | 13 | 4 |
| MAP | 66 | 66 | 67 | 33 |
| ENS | 51 | 51 | 66 | 57 |
| STATUS | 4 | 4 | 4 | 1 |
| REG | 24 | 24 | 121 | 66 |
| RANDOM | 240 | 240 | 240 | 0 |

## Governed state (credible transport set EMPTY)

* E-01_member_ids_empty: True
* E-70_credible_set_EMPTY: True
* E-63_nine_screening_refused: True

## Ledger update requested

* {"component": "C-ABEP_SIM_HALL_MAP_PY", "status": "ADMITTED", "scope": "whole module", "authoritative_implementation": "rust: abep_hall", "contract": "docs/rust_migration/contracts/C-HALL-MAP-ENSEMBLE-REGISTRY/parity_prereg_v1.json", "contract_sha256": "aa0910d9aaf32964efbdf7c25a5a92d3ae87a4a91ef7ea70cddd3344f680c88e", "report": "docs/rust_migration/contracts/C-HALL-MAP-ENSEMBLE-REGISTRY/parity_report_v1.json"}
* {"component": "C-ABEP_SIM_HALL_ENSEMBLE_PY", "status": "ADMITTED", "scope": "whole module", "authoritative_implementation": "rust: abep_hall", "contract": "docs/rust_migration/contracts/C-HALL-MAP-ENSEMBLE-REGISTRY/parity_prereg_v1.json", "contract_sha256": "aa0910d9aaf32964efbdf7c25a5a92d3ae87a4a91ef7ea70cddd3344f680c88e", "report": "docs/rust_migration/contracts/C-HALL-MAP-ENSEMBLE-REGISTRY/parity_report_v1.json"}
* {"component": "C-ABEP_SIM_HALLMAP_REGISTRY_PY", "status": "ADMITTED", "scope": "whole module", "authoritative_implementation": "rust: abep_hall", "contract": "docs/rust_migration/contracts/C-HALL-MAP-ENSEMBLE-REGISTRY/parity_prereg_v1.json", "contract_sha256": "aa0910d9aaf32964efbdf7c25a5a92d3ae87a4a91ef7ea70cddd3344f680c88e", "report": "docs/rust_migration/contracts/C-HALL-MAP-ENSEMBLE-REGISTRY/parity_report_v1.json"}
* {"component": "C-ABEP_SIM_DESIGN_ARCHITECTURE_OPTIMIZER_PY", "status": "ADMITTED", "scope": "function subset hall_response_status only; the rest stays PYTHON_REFERENCE (SC-WP-10)", "authoritative_implementation": "rust: abep_hall", "contract": "docs/rust_migration/contracts/C-HALL-MAP-ENSEMBLE-REGISTRY/parity_prereg_v1.json", "contract_sha256": "aa0910d9aaf32964efbdf7c25a5a92d3ae87a4a91ef7ea70cddd3344f680c88e", "report": "docs/rust_migration/contracts/C-HALL-MAP-ENSEMBLE-REGISTRY/parity_report_v1.json"}

## Performance (reported, not a decision criterion)

* Python step time 4.42 s, Rust step time (process per step) 1.71 s.
