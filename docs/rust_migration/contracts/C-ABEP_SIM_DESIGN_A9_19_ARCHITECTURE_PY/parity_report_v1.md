# Parity report — C-ABEP_SIM_DESIGN_A9_19_ARCHITECTURE_PY v1

**Verdict: ADMITTED (PARITY_PASS)** under the preregistered decision rules of
`parity_prereg_v1.json` (sha256 `ddec7a18646d07fbb082aaf9c5d88ebf4ab89d2cdb6d179c007e813ea07c6ed2`, committed in `a620365`).

The active-architecture invariant: flight conventional hollow cathode **NONE**; C1 **ground test / reference only**;
`config/architecture/hall_icp_neutralizer_v1.json` pinned in Rust (sha256 `7ab04af49340bf24…`).

| item | value |
|---|---|
| Python reference | `96db552`; reference files unchanged at scoring |
| Rust source at scoring | `b249a58` (crate commit `e26c18f`), worktree clean: True |
| toolchain | rustc 1.94.1 (e408947bf 2026-03-25) |
| environment | Python 3.11.15, numpy 2.4.4 (unused) |
| scoring seed | 3907715266 (run once, 2026-10-05T13:33:59Z) |

## Results

| part | count |
|---|---|
| registered element cases (R-01..R-10) | 428 |
| seeded element lists | 400 |
| configurations / ground-reference requests | 17 / 12 |
| decision-record trees / definition trees | 6 / 4 |
| calls compared (EXACT_VALUE) | 1712 |
| Python refusals (ArchitectureRuleError) | 638 |
| mismatches | 0 |

Definition trees: A-00 and A-03 equal to Python; A-01 / A-02 equal to the registered DIV-A01 Rust refusal (Python
accepts a manifest-consistent edited architecture; Rust refuses it by the hash pin).

## Invariants

| id | pass | statement |
|---|---|---|
| INV-A1 | True | FLIGHT_ARCHITECTURE.conventional_hollow_cathode == NONE, FLIGHT_CONFIGURATIONS == [hall_icp_neutralizer] (both) |
| INV-A2 | True | hall_c1_reference refused as flight configuration; ground_reference flight_candidate / in_flight_budgets false, label GROUND_REFERENCE (both) |
| INV-A3 | True | R-01 (mass_power_a9_v5 flight elements) check NO_HOLLOW_CATHODE_ELEMENT_LISTED, no flagged provisions (both) |
| INV-A4 | True | Rust eval twice byte-identical |
| INV-A5 | True | Rust pin accepted on the reference tree; architecture sha256 == MANIFEST entry == registered pin |

## Performance (reported, not a criterion)

PERF-ARCH-01 (1000 refusals of R-01): Python 0.977 s, Rust
0.967 s (includes one definition load per call through `abep-config eval`).

## Ledger update requested

- `C-ABEP_SIM_DESIGN_A9_19_ARCHITECTURE_PY` → ADMITTED (PARITY_PASS) for the named function subset; authoritative
  implementation `crates/abep-config` (`abep_config::architecture`). Out-of-scope functions stay PYTHON_REFERENCE.

Note: the CI_PLAN principle-6 forbidden-identifier scan must allow-list `crates/abep-config/src/architecture.rs` (the
refusal-guard vocabulary lives there, not in `abep-design`).

Admission is software parity, not physics validation and not a gate PASS.
