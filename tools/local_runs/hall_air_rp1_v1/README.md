# hall_air_rp1_v1: local Hall AIR run package (A9.39 item 4)

This package runs 10 HallThruster.jl cases of the H1 Hall thruster on air, on your own machine, with one command. It
writes **one result file** for you to send back.

- **Physics:** DBF-1.1 RP-1 (d_mean 70 mm, h 12 mm, L 103.2 mm) with the FE-derived H1 B(z).
- **Rules:** registered in NP-HALL-PARAMETRIC-ENVELOPE addendum A9-LP
  (`docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/prereg_addendum_a9_local_air_rp1_v1.json`, lock
  `abb4f9f4…`).
- **Labels:** PARAMETRIC / NOT_VALIDATED.
  - AIR chemistry is BOUNDED, not complete (abep-air-0.7, BV-AIR-LL-NOM).
  - B(z) is FE-derived, not measured.
  - The transports are unadmitted screening candidates.
  - Nothing here is measured or demonstrated H1 performance; the Engineering Model verifies that.

## Prerequisites

- **OS.** Linux or macOS with bash. On Windows, use WSL2 (Ubuntu) and run everything inside WSL.
- **Julia 1.11.7 exactly.** The pinned `hallthruster_bridge/Manifest.toml` was resolved with it.
  - With juliaup: `juliaup add 1.11.7 && juliaup default 1.11.7`. You can switch the default back after the run.
  - Or take the tarball from https://julialang.org/downloads/oldreleases/ and run `export JULIA=/path/to/julia-1.11.7/bin/julia`.
  - `ABEP_ALLOW_OTHER_JULIA=1` lets another version run. It is recorded in the result file, and it is not recommended.
- **The repository checkout** containing this directory, unmodified. The preflight refuses to run if any package file
  or input file differs from `package_manifest_v1.json`.
- **Internet access on the first run only.** Julia downloads HallThruster.jl v0.23.1 (commit
  `bfb3019fc74ceaa2c70c9d3b19236a83a44ee3b5`) and its dependencies from the Julia General registry and GitHub.
- **Resources.** About 2.5 GB RAM per parallel job, 1 CPU core per job and about 50 MB of disk for the outputs.

## Run

```bash
cd tools/local_runs/hall_air_rp1_v1
./run_all.sh                 # all 10 cases x 2 levels; default jobs = min(CPU cores - 1, 6)
./run_all.sh --jobs 4        # choose the number of parallel runs
```

The script:
1. Checks the Julia version.
2. Instantiates and precompiles the pinned Manifest. This takes 5–15 min the first time and seconds afterwards.
3. Checks that `cases_v1.json` reproduces from the registered sources.
4. Runs the preflight: Julia version, HallThruster.jl pin and the sha256 of every package and input file.
5. Runs the 20 runs (10 cases × production level A7-P + check level A7-C) with N parallel jobs.
6. Writes and validates the result file.

**Resume.** If it is interrupted (Ctrl-C, reboot), run the same command again. Finished runs (`out/runs/*.json`) are
kept, and only the missing ones run.

Options:
- `--out DIR`: output directory (default `./out`).
- `--cases C01,C05`: run a subset.
- `--levels A7-P`: production level only.
- `--skip-instantiate`: skip step 2.

A partial run still produces a valid result file, with `complete: false` and NOT_RUN entries.

## Expected runtime

Measured in the authoring container (Linux x86-64, 4 vCPU, 3 parallel jobs; see the reference output):

| run | per run (single core) |
|---|---|
| A7-P (678 cells, 13.5 ms simulated) | RUNTIME_P |
| A7-C (1356 cells, 13.5 ms simulated) | RUNTIME_C |

- A case whose discharge collapses stops early, in seconds to minutes.
- The full package is about 20 runs ≈ RUNTIME_TOTAL CPU-hours. Wall time is that divided by the number of jobs, for
  example about RUNTIME_WALL6 h with 6 jobs.
- A faster desktop CPU is typically 1.5–2× quicker.

## What to send back

Send **one file**: `out/hall_air_rp1_v1_results.json`.

`out/hall_air_rp1_v1_results.csv` is a one-line-per-case summary for your own look. If a run fails in an unexpected
way, please also send `out/logs/`.

## What is in the result file

Per case, the production level A7-P is reported in `result`, and the check level A7-C in `check_level_result`:

- **Inputs.** Atmospheric composition (corner id, y_O, f_O, f_N, mass fractions, per-species feed), mass flow, V_d, and
  the B operating point (profile id, B_peak, coil NI in A-turns, file sha256) with transport.
- **Thrust.** The true time-mean of the instantaneous thrust, ± batch-means SE. The averaged-state thrust is reported
  only for comparison.
- **I_d** ± SE, and the discharge power I_d·V_d.
- **Isp** = T / (ṁ g0).
- **Anode efficiency** η_a = T² / (2 ṁ V_d I_d), plus its decomposition (mass, current, voltage, divergence).
  **Total efficiency is NOT_EVALUATED**: it needs magnet, RF/ICP, PPU and gas-path power, which are outside a Hall
  discharge run.
- **Oscillations** of I_d and thrust: dominant frequency, RMS, peak-to-peak and autocorrelation time.
- **Convergence.** A7-P vs A7-C differences against the A7 rule, half-window means, stationarity and SE.
- **Runtime** per level.
- **Status** and failure / collapse diagnostics: retcode, error, collapse time, n_e,min, T_e,max, and the first
  non-finite variable with its location.
- **Provenance:** host, OS, CPU, Julia and HallThruster.jl versions and commit, thread / BLAS environment, and the
  sha256 of the case file, package and inputs.

Statuses, in order of precedence:
1. NUMERICAL_FAILURE
2. EXTINCT
3. OUT_OF_DOMAIN (AIR chemistry beyond its validity limits; numbers are still given, as information)
4. NOT_SUSTAINED
5. NON_STATIONARY
6. STATISTICALLY_UNRESOLVED
7. PASS

Case outcomes: CONVERGED_EVALUATED, PERSISTENT_UNKNOWN or NOT_CONVERGED.

## Cases

| id | ṁ [mg/s] | composition | V_d [V] | B | transport |
|---|---|---|---|---|---|
| C01 | 0.2 | CP-YLO-REC | 350 | BP-LO (69.93 G) | sgb-screen-01 |
| C02 | 0.2 | CP-YHI-DIS | 265 | BP-LO | sgb-screen-01 |
| C03 | 0.5 | CP-YLO-REC | 265 | BP-HI (268.6 G) | sgb-screen-01 |
| C04 | 0.5 | CP-YHI-DIS | 350 | BP-HI | sgb-screen-01 |
| C05 | 1.0 | CP-YLO-REC | 350 | BP-LO | sgb-screen-01 |
| C06 | 1.0 | CP-YHI-DIS | 350 | BP-HI | sgb-screen-01 |
| C07 | 2.0 | CP-YLO-REC | 265 | BP-HI | sgb-screen-01 |
| C08 | 2.0 | CP-YHI-DIS | 265 | BP-LO | sgb-screen-01 |
| C09 | 1.0 | CP-YLO-REC | 350 | BP-LO | sgb-screen-04 |
| C10 | 1.0 | CP-YHI-DIS | 350 | BP-HI | sgb-screen-04 |

- **CP-YLO-REC** is the low-O, molecular corner of the frozen 196-state design set (y_O 0.079, ECSS short-term high,
  180 km).
- **CP-YHI-DIS** is the O-dominated, dissociated corner (y_O 0.840, f_O 0.99, ECSS long-term low, 230 km).
- The selection rules SR-1..SR-6 are in the addendum.

## Files

| file | role |
|---|---|
| `run_all.sh` | the single entry point |
| `cases_v1.json` | the 10 registered cases (generated by `make_cases.jl`) |
| `hall_air_rp1_lib.jl` | AIR run with the A7 numerics |
| `worker.jl` | one parallel job |
| `preflight.jl` | version / pin / sha256 checks |
| `aggregate.jl` | status, convergence and the result file |
| `results_schema_v1.json`, `validate.jl` | result-file schema and validator (`julia --project=../../../hallthruster_bridge validate.jl <file>`) |
| `package_manifest_v1.json` | sha256 of every package and input file |
| `reference/` | the in-container reference output (registered subset C02, C05, C06; host-labelled; never merged with your results) |
