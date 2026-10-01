# abep_core — optional Rust kernels (A9.7 Rust lane)

Lane `fo_a9_7_rust_kernels`, owner directive
`docs/decisions/OD_2026_10_01_A9_7_ARCHITECTURE_FREEZE_DESIGN_SYNTHESIS.md` ("Computational-language decision",
"Rust acceleration admission order" item 1). F0 (`docs/performance/PERFORMANCE_BASELINE_98fbbb9.json`) ranks the
TPMC trace (`intake_response_surface` / `trace_channel`) as the only non-deferred PORT_CANDIDATE, so this crate ports
exactly that kernel and nothing else.

## What it is

A PyO3 / maturin extension module `abep_core` that re-implements, line by line, the TPMC channel trace of
`abep_sim/intake_tpmc.py`:

| abep_core function | reference |
|---|---|
| `flux_weighted_entry(seed, n, v_drift, theta, t, m)` | `_flux_weighted_entry` (+ `_drifting_maxwellian`) |
| `diffuse(seed, normal, t_w, m)` | `_diffuse` |
| `cll(seed, v_in, normal, t_w, m, alpha_n, alpha_t)` | `_cll` |
| `trace_channel(seed, v0, r, l, alpha, t_w, m, max_hits=200, scattering="maxwell", alpha_n=None, alpha_t=None, unresolved_tol=1e-3, max_hits_cap=5000)` | `trace_channel` |
| `clausing_transmission(seed, r, l, alpha, t_w, m, n=20000)` | `clausing_transmission` |

Same physics, same flight / tie / hit-budget-doubling rules, same outputs and dtypes. Only the random stream differs
(xoshiro256++ seeded by SplitMix64, implemented in `src/rng.rs` without external RNG crates, so a seed always gives the
same stream).

## What it is not

* Not authoritative. `abep_sim/intake_tpmc.py` is the reference; every Rust result is reproducible with it.
* Not wired anywhere. Python code reaches it only through `abep_sim/design/tpmc_backend.py` with an explicit
  `backend="rust"`; the default is `"python"`. Requesting `"rust"` when the extension is missing raises
  `RustBackendUnavailable` (no silent fallback). archengine, `intake.py`, the frozen intake surface, the goldens and every
  existing study keep calling the Python reference.
* Not admitted by being fast. Admission is decided only by the pre-registered statistical parity campaign
  (`docs/performance/abep_core/parity_prereg_v1.json`, committed before any comparison; run by
  `scripts/verify_abep_core.py`; result in `docs/performance/abep_core/parity_report_v1.json` / `.md`).

## Build (outside the repository environment)

Never install into the repository's Python environment and never change `requirements-lock.txt`. Use a scratch
virtual environment that can see the repository's dependencies:

```bash
python -m venv --system-site-packages <scratch>/venv_rust
<scratch>/venv_rust/bin/pip install "maturin>=1.5,<2"
cd abep_core
VIRTUAL_ENV=<scratch>/venv_rust PATH=$HOME/.cargo/bin:$PATH <scratch>/venv_rust/bin/maturin develop --release
```

Toolchain used for the recorded campaign: see `build_provenance` in the parity report (rustc / cargo versions, source
and extension sha256). Dependencies are pinned by the committed `Cargo.lock` (pyo3 0.29, numpy 0.29).

Pure-Rust unit tests (no Python needed): `cargo test --release` in `abep_core/`.

Note: run from the repository root, `import abep_core` can resolve the source directory `abep_core/` as an empty
namespace package. `tpmc_backend` checks for the extension's functions and reports that case as unavailable.

## Parity campaign

```bash
<scratch>/venv_rust/bin/python scripts/verify_abep_core.py            # scoring campaign (appends to campaign history)
python scripts/verify_abep_core.py --check                            # re-derive every verdict from the stored numbers
<scratch>/venv_rust/bin/python scripts/verify_abep_core.py --check --recompute 3   # bitwise reproduction (same build)
<scratch>/venv_rust/bin/python scripts/verify_abep_core.py --dev --limit 5         # development seed, never scored
```

`tests/test_tpmc_backend.py` always tests the Python backend through the wrapper and the unavailable-Rust error path;
when the extension is importable it also runs a tiny parity smoke. It never skips.

## Documented divergences (inputs the reference does not handle)

* `max_hits < 1`: the reference never terminates; Rust refuses (`ValueError`).
* `scattering` other than `"maxwell"` / `"cll"`: the reference silently traces Maxwell; Rust refuses.
* CLL `alpha_n` / `alpha_t` outside [0, 1]: the reference raises or returns NaN; Rust refuses.
