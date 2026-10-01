"""A9.7 Rust lane - explicit backend switch for the TPMC channel trace (Python reference authoritative).

Lane fo_a9_7_rust_kernels (owner directive OD_2026_10_01_A9_7, "Computational-language decision" and "Rust
acceleration admission order" item 1). This wrapper exposes the TPMC channel-trace kernels of
``abep_sim/intake_tpmc.py`` with the reference call signatures plus one keyword, ``backend``:

  * ``backend="python"`` (default) calls the reference functions in ``abep_sim.intake_tpmc`` directly, with the
    caller's numpy Generator, so results are identical to calling the reference with the same seed;
  * ``backend="rust"`` calls the optional native extension ``abep_core`` (source ``abep_core/``, built with maturin,
    see abep_core/README.md). It is used only when explicitly requested. If ``abep_core`` is not importable the call
    RAISES ``RustBackendUnavailable`` - there is no silent fallback to Python (CLAUDE.md rule 3).

Random streams: the Rust kernels use their own generator (xoshiro256++). The wrapper seeds it with ONE 64-bit draw
from the caller's numpy Generator (``rng.integers(0, 2**64, dtype=np.uint64)``), so the same Generator state gives the
same Rust result (deterministic seeding), but Python and Rust results differ draw by draw. Equivalence is therefore
statistical and is decided only by the pre-registered parity campaign
(docs/performance/abep_core/parity_prereg_v1.json, scripts/verify_abep_core.py,
docs/performance/abep_core/parity_report_v1.json).

What this module is not: it is not wired into archengine, intake.py, the frozen intake surface build or any golden
benchmark; nothing in the repository selects the Rust backend by default; no Rust result is authoritative.
Documented divergences of the Rust backend (refusals for inputs the reference does not handle): max_hits < 1 (the
reference never terminates), scattering other than 'maxwell' / 'cll' (the reference silently treats it as Maxwell),
CLL accommodation outside [0, 1] (the reference raises or returns NaN). DIV-04 (recorded after registration, consolidated
verification round 1, RUST-02; outside the registered comparison set): the Rust trace_channel refuses max_hits_cap < 1,
whereas the reference accepts max_hits_cap = 0 (its hit-budget doubling then stops after max_hits steps). This wrapper
refuses that input for backend='rust' with a correct message before the extension is called; the Python backend keeps
the reference behaviour.

Admission gate (consolidated verification round 1, RUST-01): backend='rust' is served only when (1) the parity report
exists, (2) the importable extension's sha256 equals the report's build_provenance.extension_sha256, (3) every source
file recorded in build_provenance.source_sha256 (abep_core sources, this wrapper, the Python reference) is unchanged,
and (4) the called kernel's verdict is ADMITTED. Otherwise the call RAISES ``RustBackendNotAdmitted`` (label
NOT_ADMITTED_BUILD); there is no fallback. The pre-registered parity campaign itself (scripts/verify_abep_core.py) runs
the unadmitted build inside ``parity_campaign_unadmitted()``, which is its only legitimate use.
"""
from __future__ import annotations

import contextlib
import hashlib
import importlib
import json
import os

import numpy as np

from .. import intake_tpmc as _ref

BACKENDS = ("python", "rust")
DEFAULT_BACKEND = "python"
RUST_MODULE = "abep_core"
RUST_REQUIRED_ATTRS = ("flux_weighted_entry", "diffuse", "cll", "trace_channel", "clausing_transmission", "K_B",
                       "RNG_ALGORITHM", "__version__")
PARITY_PREREG = "docs/performance/abep_core/parity_prereg_v1.json"
PARITY_REPORT = "docs/performance/abep_core/parity_report_v1.json"


REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KERNEL_IDS = {"flux_weighted_entry": "K1_entry", "diffuse": "K2_diffuse", "cll": "K3_cll",
              "trace_channel": "K4_trace", "clausing_transmission": "K5_clausing"}
NOT_ADMITTED_BUILD = "NOT_ADMITTED_BUILD"
_UNADMITTED_ALLOWED = False


class RustBackendUnavailable(RuntimeError):
    """backend='rust' was requested but the abep_core extension is not importable (never silently replaced)."""


class RustBackendNotAdmitted(RuntimeError):
    """backend='rust' was requested but the importable build / sources / kernel verdict do not match the parity report
    (NOT_ADMITTED_BUILD; never silently replaced)."""


@contextlib.contextmanager
def parity_campaign_unadmitted():
    """Allow the unadmitted extension ONLY inside the pre-registered parity campaign / its --recompute check."""
    global _UNADMITTED_ALLOWED
    prev = _UNADMITTED_ALLOWED
    _UNADMITTED_ALLOWED = True
    try:
        yield
    finally:
        _UNADMITTED_ALLOWED = prev


def _sha256(path: str) -> str | None:
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    except OSError:
        return None


def extension_sha256(mod) -> str | None:
    """sha256 of the compiled extension file of an imported abep_core (None if it cannot be located)."""
    d = os.path.dirname(getattr(mod, "__file__", "") or "")
    if not d or not os.path.isdir(d):
        return None
    so = sorted(f for f in os.listdir(d) if f.endswith((".so", ".pyd")))
    return _sha256(os.path.join(d, so[0])) if so else None


def admission_status(mod, kernel: str | None = None) -> tuple[bool, str]:
    """(admitted, reason) for serving ``kernel`` (a KERNEL_IDS value) from the imported extension ``mod``."""
    try:
        with open(os.path.join(REPO, PARITY_REPORT)) as fh:
            rep = json.load(fh)
    except (OSError, ValueError) as exc:
        return False, f"parity report unavailable ({exc})"
    bp = rep.get("build_provenance", {})
    want = bp.get("extension_sha256")
    got = extension_sha256(mod)
    if not want or got != want:
        return False, f"extension sha256 {got} != parity-report build {want}"
    changed = [rel for rel, h in bp.get("source_sha256", {}).items() if _sha256(os.path.join(REPO, rel)) != h]
    if changed:
        return False, f"sources differ from the parity-report build: {changed}"
    if kernel is not None and rep.get("verdicts", {}).get(kernel) != "ADMITTED":
        return False, f"kernel {kernel} verdict {rep.get('verdicts', {}).get(kernel)!r} is not ADMITTED"
    return True, "ADMITTED build (extension and sources match the parity report)"


def _load_rust():
    """Return (module, None) when a built abep_core extension is importable, else (None, reason).

    The source directory ``abep_core/`` at the repository root has no ``__init__.py``; run from the repository root it
    can be imported as an empty namespace package. That is NOT the extension, so the required attributes are checked."""
    try:
        mod = importlib.import_module(RUST_MODULE)
    except ImportError as exc:                      # not built / not installed
        return None, f"import {RUST_MODULE} failed: {exc}"
    missing = [a for a in RUST_REQUIRED_ATTRS if not hasattr(mod, a)]
    if missing:
        where = list(getattr(mod, "__path__", [])) or getattr(mod, "__file__", None)
        return None, (f"'{RUST_MODULE}' imported from {where} is not the built extension (missing {missing}); "
                      "build it with maturin (abep_core/README.md)")
    return mod, None


def rust_available() -> bool:
    return _load_rust()[0] is not None


def rust_unavailable_reason() -> str | None:
    return _load_rust()[1]


def _check_backend(backend: str, fn: str | None = None):
    if backend not in BACKENDS:
        raise ValueError(f"tpmc_backend: backend must be one of {BACKENDS}, got {backend!r}")
    if backend == "rust":
        mod, why = _load_rust()
        if mod is None:
            raise RustBackendUnavailable(
                f"tpmc_backend: backend='rust' requested but abep_core is unavailable ({why}). No fallback to the "
                "Python reference is made; call with backend='python' to use the reference.")
        if not _UNADMITTED_ALLOWED:
            ok, why = admission_status(mod, KERNEL_IDS.get(fn) if fn else None)
            if not ok:
                raise RustBackendNotAdmitted(
                    f"tpmc_backend: backend='rust' refused ({NOT_ADMITTED_BUILD}: {why}). No fallback to the Python "
                    "reference is made; call with backend='python' to use the reference.")
        return mod
    return None


def rust_seed(rng: np.random.Generator) -> int:
    """The single 64-bit draw that seeds the Rust stream (advances the caller's Generator by one draw)."""
    return int(rng.integers(0, 2 ** 64, dtype=np.uint64))


def _as_rows(a, name):
    a = np.ascontiguousarray(np.asarray(a, dtype=np.float64))
    if a.ndim != 2 or a.shape[1] != 3:
        raise ValueError(f"tpmc_backend: {name} must have shape (n, 3), got {a.shape}")
    return a


# --------------------------------------------------------------------------------------------------------------------
# kernels (reference signatures + backend keyword)
# --------------------------------------------------------------------------------------------------------------------
def flux_weighted_entry(rng, n, V, theta, T, m, *, backend: str = DEFAULT_BACKEND):
    """Reference ``_flux_weighted_entry(rng, n, V, theta, T, m)``: float64 (n, 3) entry velocities."""
    mod = _check_backend(backend, "flux_weighted_entry")
    if mod is None:
        return _ref._flux_weighted_entry(rng, n, V, theta, T, m)
    return mod.flux_weighted_entry(rust_seed(rng), int(n), float(V), float(theta), float(T), float(m))


def diffuse(rng, n, T_w, m, normal, *, backend: str = DEFAULT_BACKEND):
    """Reference ``_diffuse(rng, n, T_w, m, normal)``: cosine-law re-emission about the (n, 3) unit normals."""
    mod = _check_backend(backend, "diffuse")
    if mod is None:
        return _ref._diffuse(rng, n, T_w, m, normal)
    nr = _as_rows(normal, "normal")
    if nr.shape[0] != n:
        raise ValueError(f"tpmc_backend.diffuse: n={n} but normal has {nr.shape[0]} rows")
    return mod.diffuse(rust_seed(rng), nr, float(T_w), float(m))


def cll(rng, v_in, normal, T_w, m, alpha_n, alpha_t, *, backend: str = DEFAULT_BACKEND):
    """Reference ``_cll(rng, v_in, normal, T_w, m, alpha_n, alpha_t)`` (normal points into the gas)."""
    mod = _check_backend(backend, "cll")
    if mod is None:
        return _ref._cll(rng, v_in, normal, T_w, m, alpha_n, alpha_t)
    return mod.cll(rust_seed(rng), _as_rows(v_in, "v_in"), _as_rows(normal, "normal"), float(T_w), float(m),
                   float(alpha_n), float(alpha_t))


def trace_channel(rng, v0, R, L, alpha, T_w, m, max_hits=200, scattering="maxwell", alpha_n=None, alpha_t=None,
                  unresolved_tol=1e-3, max_hits_cap=5000, *, backend: str = DEFAULT_BACKEND):
    """Reference ``trace_channel``: returns (collected mask, final velocities, wall hits, back mask, unresolved
    fraction) with the reference dtypes (bool, float64 (n,3), int64, bool, float)."""
    if backend == "rust" and int(max_hits_cap) < 1:
        raise ValueError("tpmc_backend.trace_channel: backend='rust' refuses max_hits_cap < 1 (documented divergence "
                         "DIV-04: the reference accepts max_hits_cap = 0 and stops after max_hits steps); use "
                         "backend='python' for that input")
    mod = _check_backend(backend, "trace_channel")
    if mod is None:
        return _ref.trace_channel(rng, v0, R, L, alpha, T_w, m, max_hits=max_hits, scattering=scattering,
                                  alpha_n=alpha_n, alpha_t=alpha_t, unresolved_tol=unresolved_tol,
                                  max_hits_cap=max_hits_cap)
    col, v, hits, back, unres = mod.trace_channel(
        rust_seed(rng), _as_rows(v0, "v0"), float(R), float(L), float(alpha), float(T_w), float(m),
        max_hits=int(max_hits), scattering=str(scattering),
        alpha_n=None if alpha_n is None else float(alpha_n), alpha_t=None if alpha_t is None else float(alpha_t),
        unresolved_tol=float(unresolved_tol), max_hits_cap=int(max_hits_cap))
    return col, v, hits, back, float(unres)


def clausing_transmission(rng, R, L, alpha, T_w, m, n=20000, *, backend: str = DEFAULT_BACKEND):
    """Reference ``clausing_transmission``: K_back for thermal molecules entering from the plenum side."""
    mod = _check_backend(backend, "clausing_transmission")
    if mod is None:
        return _ref.clausing_transmission(rng, R, L, alpha, T_w, m, n=n)
    return float(mod.clausing_transmission(rust_seed(rng), float(R), float(L), float(alpha), float(T_w), float(m),
                                           int(n)))


def backend_info() -> dict:
    """Provenance of what a 'rust' call would use (for reports); never changes behaviour."""
    mod, why = _load_rust()
    info = {"default_backend": DEFAULT_BACKEND, "rust_available": mod is not None, "reference": "abep_sim/intake_tpmc.py",
            "parity_prereg": PARITY_PREREG, "parity_report": PARITY_REPORT}
    if mod is None:
        info["rust_unavailable_reason"] = why
    else:
        ok, reason = admission_status(mod)
        info.update({"abep_core_version": mod.__version__, "rng_algorithm": mod.RNG_ALGORITHM,
                     "abep_core_file": getattr(mod, "__file__", None), "build_admitted": ok,
                     "build_admission_reason": reason})
    return info
