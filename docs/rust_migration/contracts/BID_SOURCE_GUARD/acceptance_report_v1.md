# bid_source_guard acceptance v1: ACCEPTED

Generated from `acceptance_report_v1.json` (do not edit). Preregistration `docs/rust_migration/contracts/BID_SOURCE_GUARD/acceptance_v1.json` (sha256 `8d23e1f16d63dcbe2ce27f1ad48712d118808270d0ae5ab2ab2a2a6eb60ab1c6`), manifest sha256 `931ba34c2cd386bf5b64f291548b4cfc1de7f78ae824ae0a8aa9fcc8d4b87f11`.

* Run: 2026-10-05T11:23:49Z at `ec6879fe6c69431fe8e48c84f7258c0bacaaf6ed` (tracked tree dirty: false), rustc 1.94.1 (e408947bf 2026-03-25), Python 3.11.15.
* Current repository tree (BASE-00): **PASS**.
* Cases: 25 ; Rust meets expectation 25 ; Python meets expectation 25 ; implementations agree 25.

| case | title | expected (overall / files / history) | Rust | Python | agree |
|---|---|---|---|---|---|
| BASE-00 | the current repository tree itself (no copy), its own manifest, HEAD: the recorded lineage passes | PASS / PASS / PASS | PASS / PASS / PASS [] [] | PASS / PASS / PASS [] [] | yes |
| BASE-01 | untampered copy, repository history: the recorded lineage passes | PASS / PASS / PASS | PASS / PASS / PASS [] [] | PASS / PASS / PASS [] [] | yes |
| CTRL-01 | Python bytecode under __pycache__ (the one ignored generated-artifact pattern) is not a bid file | PASS / PASS / PASS | PASS / PASS / PASS [] [] | PASS / PASS / PASS [] [] | yes |
| CTRL-02 | a valid owner_change_authorizations entry admits exactly the authorized bytes (no history: the overall result stays NOT_EVALUATED, never PASS) | NOT_EVALUATED / PASS / NOT_EVALUATED | NOT_EVALUATED / PASS / NOT_EVALUATED [] [HISTORY_NOT_AVAILABLE] | NOT_EVALUATED / PASS / NOT_EVALUATED [] [HISTORY_NOT_AVAILABLE] | yes |
| TC-01 | modified protected text file (one LF appended) | FAIL / FAIL / PASS | FAIL / FAIL / PASS [BID_FILE_MODIFIED] [] | FAIL / FAIL / PASS [BID_FILE_MODIFIED] [] | yes |
| TC-02 | modified protected binary file (one NUL byte appended to a .docx) | FAIL / FAIL / PASS | FAIL / FAIL / PASS [BID_FILE_MODIFIED] [] | FAIL / FAIL / PASS [BID_FILE_MODIFIED] [] | yes |
| TC-03 | deleted protected file | FAIL / FAIL / PASS | FAIL / FAIL / PASS [BID_FILE_MISSING] [] | FAIL / FAIL / PASS [BID_FILE_MISSING] [] | yes |
| TC-04 | added unlisted file beside the protected files | FAIL / FAIL / PASS | FAIL / FAIL / PASS [BID_FILE_UNLISTED] [] | FAIL / FAIL / PASS [BID_FILE_UNLISTED] [] | yes |
| TC-05 | added unlisted file at docs/bid/ top level (a second manifest) | FAIL / FAIL / PASS | FAIL / FAIL / PASS [BID_FILE_UNLISTED] [] | FAIL / FAIL / PASS [BID_FILE_UNLISTED] [] | yes |
| TC-06 | added non-bytecode file inside __pycache__ (the ignore pattern covers *.pyc only) | FAIL / FAIL / PASS | FAIL / FAIL / PASS [BID_FILE_UNLISTED] [] | FAIL / FAIL / PASS [BID_FILE_UNLISTED] [] | yes |
| TC-07 | modified mission scenario v2 (one space appended) | FAIL / FAIL / PASS | FAIL / FAIL / PASS [MISSION_SCENARIO_CHANGED] [] | FAIL / FAIL / PASS [MISSION_SCENARIO_CHANGED] [] | yes |
| TC-08 | deleted mission scenario v2 | FAIL / FAIL / PASS | FAIL / FAIL / PASS [MISSION_SCENARIO_CHANGED] [] | FAIL / FAIL / PASS [MISSION_SCENARIO_CHANGED] [] | yes |
| TC-09 | technical-source pin changed in bid_technical_baseline_v2.json | FAIL / FAIL / PASS | FAIL / FAIL / PASS [BID_FILE_MODIFIED, TECHNICAL_SOURCE_PIN_CHANGED] [] | FAIL / FAIL / PASS [BID_FILE_MODIFIED, TECHNICAL_SOURCE_PIN_CHANGED] [] | yes |
| TC-10 | manifest tampered: a protected file's recorded sha256 altered | FAIL / FAIL / FAIL | FAIL / FAIL / FAIL [BID_FILE_MODIFIED] [BID_FILE_MODIFIED, LINEAGE_FILES_MISMATCH] | FAIL / FAIL / FAIL [BID_FILE_MODIFIED] [BID_FILE_MODIFIED, LINEAGE_FILES_MISMATCH] | yes |
| TC-11 | wrong lineage: package lineage recorded in reverse order (2de86ab -> b5849af) | FAIL / FAIL / FAIL | FAIL / FAIL / FAIL [BID_FILE_MODIFIED, BID_FILE_UNLISTED, LINEAGE_RECORD_MISMATCH] [BID_FILE_MODIFIED, BID_FILE_UNLISTED, LINEAGE_ANCESTRY_BROKEN] | FAIL / FAIL / FAIL [BID_FILE_MODIFIED, BID_FILE_UNLISTED, LINEAGE_RECORD_MISMATCH] [BID_FILE_MODIFIED, BID_FILE_UNLISTED, LINEAGE_ANCESTRY_BROKEN] | yes |
| TC-12 | wrong lineage: terminal package state recorded as b5849af | FAIL / FAIL / PASS | FAIL / FAIL / PASS [LINEAGE_RECORD_MISMATCH] [] | FAIL / FAIL / PASS [LINEAGE_RECORD_MISMATCH] [] | yes |
| TC-13 | wrong lineage: technical source recorded as 2de86ab | FAIL / FAIL / FAIL | FAIL / FAIL / FAIL [LINEAGE_RECORD_MISMATCH] [LINEAGE_ANCESTRY_BROKEN, TREE_HASH_MISMATCH] | FAIL / FAIL / FAIL [LINEAGE_RECORD_MISMATCH] [LINEAGE_ANCESTRY_BROKEN, TREE_HASH_MISMATCH] | yes |
| TC-14 | wrong lineage: the evaluated head (b5849af) does not descend from the terminal state 2de86ab | FAIL / PASS / FAIL | FAIL / PASS / FAIL [] [BID_FILE_MISSING, BID_FILE_MODIFIED, LINEAGE_ANCESTRY_BROKEN] | FAIL / PASS / FAIL [] [BID_FILE_MISSING, BID_FILE_MODIFIED, LINEAGE_ANCESTRY_BROKEN] | yes |
| TC-15 | wrong lineage: recorded docs/bid tree hash at 2de86ab altered | FAIL / PASS / FAIL | FAIL / PASS / FAIL [] [TREE_HASH_MISMATCH] | FAIL / PASS / FAIL [] [TREE_HASH_MISMATCH] | yes |
| TC-16 | wrong lineage: a lineage commit that is not in the history | FAIL / FAIL / FAIL | FAIL / FAIL / FAIL [LINEAGE_RECORD_MISMATCH] [LINEAGE_COMMIT_MISSING] | FAIL / FAIL / FAIL [LINEAGE_RECORD_MISMATCH] [LINEAGE_COMMIT_MISSING] | yes |
| TC-17 | owner authorization naming a decision record that does not exist grants nothing | FAIL / FAIL / PASS | FAIL / FAIL / PASS [AUTHORIZATION_INVALID, BID_FILE_MODIFIED] [] | FAIL / FAIL / PASS [AUTHORIZATION_INVALID, BID_FILE_MODIFIED] [] | yes |
| TC-18 | owner authorization whose decision-record sha256 does not match grants nothing | FAIL / FAIL / PASS | FAIL / FAIL / PASS [AUTHORIZATION_INVALID, BID_FILE_MODIFIED] [] | FAIL / FAIL / PASS [AUTHORIZATION_INVALID, BID_FILE_MODIFIED] [] | yes |
| TC-19 | no git history available: never a silent pass | NOT_EVALUATED / PASS / NOT_EVALUATED | NOT_EVALUATED / PASS / NOT_EVALUATED [] [HISTORY_NOT_AVAILABLE] | NOT_EVALUATED / PASS / NOT_EVALUATED [] [HISTORY_NOT_AVAILABLE] | yes |
| TC-20 | shallow clone: history NOT_EVALUATED, never a silent pass | NOT_EVALUATED / PASS / NOT_EVALUATED | NOT_EVALUATED / PASS / NOT_EVALUATED [] [HISTORY_NOT_AVAILABLE] | NOT_EVALUATED / PASS / NOT_EVALUATED [] [HISTORY_NOT_AVAILABLE] | yes |
| TC-21 | full-history repository that does not contain the bid lineage | FAIL / PASS / FAIL | FAIL / PASS / FAIL [] [LINEAGE_COMMIT_MISSING] | FAIL / PASS / FAIL [] [LINEAGE_COMMIT_MISSING] | yes |

Ledger: NI-BID-SOURCE-GUARD -> ADMITTED in docs/rust_migration/migration_state_v1.json (admission evidence: this report)
