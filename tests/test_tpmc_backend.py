"""A9.7 Rust lane (fo_a9_7_rust_kernels): explicit TPMC backend switch and the abep_core parity record.

Never skips (CLAUDE.md rule 9: exactly 5 skips repo-wide). The Python backend is always tested through the wrapper
(identical to calling abep_sim.intake_tpmc with the same seed); the 'rust' request is tested in both states:
unavailable -> clear error (forced by monkeypatch, and for real when abep_core is not built), available -> a tiny
parity smoke. No Rust result is treated as authoritative here.
"""
import importlib.util
import json
import math
import os
import types

import numpy as np
import pytest

from abep_sim import intake_tpmc as REF
from abep_sim.atmosphere import atmosphere
from abep_sim.constants import K_B, M_SPECIES
from abep_sim.design import tpmc_backend as TB

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREREG = os.path.join(ROOT, "docs/performance/abep_core/parity_prereg_v1.json")
REPORT = os.path.join(ROOT, "docs/performance/abep_core/parity_report_v1.json")
ATM = atmosphere(200.0, "mean")
M = M_SPECIES["N2"]
R = 5e-3


def _load_verify():
    spec = importlib.util.spec_from_file_location("verify_abep_core", os.path.join(ROOT, "scripts/verify_abep_core.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _equal(a, b):
    if isinstance(a, tuple):
        return len(a) == len(b) and all(_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, np.ndarray):
        return a.dtype == b.dtype and a.shape == b.shape and np.array_equal(a, b)
    return a == b


# --------------------------------------------------------------------------------------------------- python backend
def test_default_backend_is_python():
    assert TB.DEFAULT_BACKEND == "python"
    import inspect
    for fn in (TB.flux_weighted_entry, TB.diffuse, TB.cll, TB.trace_channel, TB.clausing_transmission):
        assert inspect.signature(fn).parameters["backend"].default == "python"


@pytest.mark.parametrize("scattering,kw", [("maxwell", {}), ("cll", {}), ("cll", {"alpha_n": 0.3, "alpha_t": 0.9})])
def test_python_backend_identical_to_reference(scattering, kw):
    r1, r2 = np.random.default_rng(42), np.random.default_rng(42)
    v_a = REF._flux_weighted_entry(r1, 1500, ATM["V"], math.radians(3.0), ATM["T"], M)
    v_b = TB.flux_weighted_entry(r2, 1500, ATM["V"], math.radians(3.0), ATM["T"], M)
    assert _equal(v_a, v_b)
    a = REF.trace_channel(r1, v_a, R, 0.08, 0.6, 350.0, M, scattering=scattering, **kw)
    b = TB.trace_channel(r2, v_b, R, 0.08, 0.6, 350.0, M, scattering=scattering, **kw)
    assert _equal(a, b)
    assert REF.clausing_transmission(r1, R, 0.05, 0.6, 350.0, M, n=2000) == \
        TB.clausing_transmission(r2, R, 0.05, 0.6, 350.0, M, n=2000)
    nr = np.tile([0.0, 1.0, 0.0], (300, 1)); vin = np.tile([10.0, -400.0, 7000.0], (300, 1))
    assert _equal(REF._diffuse(r1, 300, 350.0, M, nr), TB.diffuse(r2, 300, 350.0, M, nr))
    assert _equal(REF._cll(r1, vin, nr, 350.0, M, 0.4, 0.7), TB.cll(r2, vin, nr, 350.0, M, 0.4, 0.7))


def test_unknown_backend_rejected():
    with pytest.raises(ValueError, match="backend must be one of"):
        TB.trace_channel(np.random.default_rng(0), np.zeros((1, 3)), R, 0.05, 0.5, 350.0, M, backend="numba")


# --------------------------------------------------------------------------------------------- rust unavailable path
def test_rust_request_raises_when_extension_missing(monkeypatch):
    def boom(name):
        raise ImportError(f"No module named {name!r}")
    monkeypatch.setattr(TB.importlib, "import_module", boom)
    assert not TB.rust_available()
    rng = np.random.default_rng(0)
    state = rng.bit_generator.state
    with pytest.raises(TB.RustBackendUnavailable, match="abep_core is unavailable.*No fallback"):
        TB.trace_channel(rng, np.ones((3, 3)), R, 0.05, 0.5, 350.0, M, backend="rust")
    assert rng.bit_generator.state == state            # refused before consuming the caller's stream
    for call in (lambda: TB.flux_weighted_entry(rng, 5, 7000.0, 0.0, 900.0, M, backend="rust"),
                 lambda: TB.clausing_transmission(rng, R, 0.05, 0.5, 350.0, M, n=10, backend="rust")):
        with pytest.raises(TB.RustBackendUnavailable):
            call()
    # the python backend is unaffected (no dependence on the extension)
    TB.clausing_transmission(rng, R, 0.05, 0.5, 350.0, M, n=50)


def test_namespace_package_is_not_the_extension(monkeypatch):
    """Run from the repo root, `import abep_core` can find the source directory as an empty namespace package."""
    fake = types.ModuleType("abep_core"); fake.__path__ = [os.path.join(ROOT, "abep_core")]
    monkeypatch.setattr(TB.importlib, "import_module", lambda name: fake)
    assert not TB.rust_available()
    assert "not the built extension" in TB.rust_unavailable_reason()
    with pytest.raises(TB.RustBackendUnavailable):
        TB.diffuse(np.random.default_rng(1), 2, 350.0, M, np.tile([0, 0, 1.0], (2, 1)), backend="rust")


def test_rust_state_real():
    """Without the built extension a rust request raises; with it, a tiny parity smoke (z = 5, as pre-registered)."""
    if not TB.rust_available():
        with pytest.raises(TB.RustBackendUnavailable, match="abep_core"):
            TB.trace_channel(np.random.default_rng(0), np.ones((2, 3)), R, 0.05, 0.5, 350.0, M, backend="rust")
        return
    import abep_core
    assert abep_core.K_B == K_B
    v0 = REF._flux_weighted_entry(np.random.default_rng(7), 3000, ATM["V"], math.radians(2.0), ATM["T"], M)
    a = TB.trace_channel(np.random.default_rng(8), v0, R, 0.1, 0.7, 350.0, M, backend="rust")
    b = TB.trace_channel(np.random.default_rng(8), v0, R, 0.1, 0.7, 350.0, M, backend="rust")
    assert _equal(a, b)                                           # deterministic seeding
    py = TB.trace_channel(np.random.default_rng(9), v0, R, 0.1, 0.7, 350.0, M)
    col, v, hits, back, unres = a
    assert col.dtype == np.bool_ and back.dtype == np.bool_ and v.shape == (3000, 3) and hits.dtype.kind == "i"
    assert isinstance(unres, float) and not np.any(col & back)
    n = len(v0)
    for x, y in ((a[0], py[0]), (a[3], py[3])):
        p1, p2 = x.mean(), y.mean()
        se = math.sqrt(p1 * (1 - p1) / n + p2 * (1 - p2) / n)
        assert abs(p1 - p2) <= 5.0 * se + 1e-15
    h1, h2 = a[2].astype(float), py[2].astype(float)
    assert abs(h1.mean() - h2.mean()) <= 5.0 * math.sqrt(h1.var(ddof=1) / n + h2.var(ddof=1) / n)
    with pytest.raises(ValueError):
        TB.trace_channel(np.random.default_rng(0), v0, R, 0.1, 0.7, 350.0, M, max_hits=0, backend="rust")
    with pytest.raises(ValueError):
        TB.trace_channel(np.random.default_rng(0), v0, R, 0.1, 0.7, 350.0, M, scattering="Maxwell", backend="rust")


# ----------------------------------------------------------------------------------------- prereg / report / wiring
def test_prereg_frozen_values():
    pre = json.load(open(PREREG))
    assert pre["status"] == "PRE_REGISTERED_BEFORE_ANY_COMPARISON"
    assert pre["decision_rules"]["z"] == 5.0 and pre["decision_rules"]["aggregate_threshold"] == 4.0
    assert pre["comparison_set"]["vector_totals"] == {"K1_entry": 30, "K2_diffuse": 18, "K3_cll": 45, "K4_trace": 425,
                                                      "K5_clausing": 75}
    import hashlib
    ref = hashlib.sha256(open(os.path.join(ROOT, "abep_sim/intake_tpmc.py"), "rb").read()).hexdigest()
    assert ref == pre["reference_implementation"]["sha256_at_registration"]


def test_report_rederives_and_is_consistent():
    V = _load_verify()
    assert V.check(0) == 0                                      # verdicts, counts, vector set, MD re-derived
    rep = json.load(open(REPORT))
    assert set(rep["verdicts"].values()) <= {"ADMITTED", "NOT_ADMITTED"}
    for sec in ("items", "parameters", "interface_demands", "open_owner_questions", "m16_impact"):
        assert rep[sec], sec
    for p in rep["parameters"] + rep["items"]:
        for f in ("id", "value", "units", "basis", "source", "evidence_class", "status"):
            assert f in p
    for d in rep["interface_demands"]:
        assert "->" in d["direction"] and d["counterparty"]
    assert rep["campaign_history"] and all(h["prereg_sha256"] == rep["prereg"]["sha256"] for h in rep["campaign_history"])
    assert not any(w in json.dumps(rep["verdicts"]) for w in ("PASS", "SELECTED", "WINNER", "QUALIFIED"))


def test_not_wired_into_production_paths():
    for rel in ("abep_sim/archengine.py", "abep_sim/intake.py", "abep_sim/intake_tpmc.py", "abep_sim/golden.py",
                "abep_sim/system.py", "abep_sim/design/intake_synthesis.py"):
        p = os.path.join(ROOT, rel)
        if os.path.exists(p):
            s = open(p).read()
            assert "tpmc_backend" not in s and "abep_core" not in s, rel


def test_lane_files_hygiene():
    for rel in ("abep_sim/design/tpmc_backend.py", "scripts/verify_abep_core.py", "abep_core/src/lib.rs",
                "abep_core/src/tpmc.rs", "abep_core/src/rng.rs"):
        assert "xe" + "_ledger" not in open(os.path.join(ROOT, rel)).read()
    gi = open(os.path.join(ROOT, "abep_core/.gitignore")).read().split()
    assert "target/" in gi
    assert os.path.exists(os.path.join(ROOT, "abep_core/Cargo.lock"))


# ------------------------------------------------------------------------- consolidated verification round 1
def _fake_extension(tmp_path):
    d = tmp_path / "abep_core"
    d.mkdir()
    (d / "abep_core.cpython-311-x86_64-linux-gnu.so").write_bytes(b"not the admitted build")
    fake = types.ModuleType("abep_core")
    fake.__file__ = str(d / "__init__.py")
    for a in TB.RUST_REQUIRED_ATTRS:
        setattr(fake, a, None)
    fake.clausing_transmission = lambda *a, **k: 0.25
    fake.__version__ = "0.0.0"
    fake.RNG_ALGORITHM = "fake"
    return fake


def test_unadmitted_build_is_refused(monkeypatch, tmp_path):
    """RUST-01: an importable abep_core whose extension sha256 differs from the parity report is never served."""
    fake = _fake_extension(tmp_path)
    monkeypatch.setattr(TB.importlib, "import_module", lambda name: fake)
    assert TB.rust_available()
    ok, why = TB.admission_status(fake, "K5_clausing")
    assert not ok and "sha256" in why
    rng = np.random.default_rng(0)
    state = rng.bit_generator.state
    with pytest.raises(TB.RustBackendNotAdmitted, match="NOT_ADMITTED_BUILD"):
        TB.clausing_transmission(rng, R, 0.05, 0.5, 350.0, M, n=10, backend="rust")
    assert rng.bit_generator.state == state            # refused before consuming the caller's stream
    with TB.parity_campaign_unadmitted():              # only the parity campaign may run an unadmitted build
        assert TB.clausing_transmission(rng, R, 0.05, 0.5, 350.0, M, n=10, backend="rust") == 0.25
    assert TB.backend_info()["build_admitted"] is False


def test_source_drift_breaks_admission(monkeypatch, tmp_path):
    """RUST-01: with the recorded extension hash, a changed source still refuses."""
    fake = _fake_extension(tmp_path)
    rep = json.load(open(REPORT))
    monkeypatch.setattr(TB, "extension_sha256", lambda mod: rep["build_provenance"]["extension_sha256"])
    real = TB._sha256
    monkeypatch.setattr(TB, "_sha256", lambda p: "0" * 64 if p.endswith("tpmc.rs") else real(p))
    ok, why = TB.admission_status(fake, "K4_trace")
    assert not ok and "abep_core/src/tpmc.rs" in why


def test_check_fails_on_source_drift(monkeypatch):
    """RUST-01 / STR-03: --check compares the current sources (and the reference) with the recorded build."""
    V = _load_verify()
    real = V.sha256_file
    monkeypatch.setattr(V, "sha256_file", lambda rel: "0" * 64 if rel.endswith("tpmc.rs") else real(rel))
    assert V.check(0) == 1
    assert "abep_sim/intake_tpmc.py" in V.PROVENANCE_SOURCES
    rep = json.load(open(REPORT))
    assert "abep_sim/intake_tpmc.py" in rep["build_provenance"]["source_sha256"]


def test_div04_max_hits_cap_documented_and_refused_for_rust():
    """RUST-02: max_hits_cap = 0 runs in the reference; backend='rust' refuses it with a correct message."""
    v0 = REF._flux_weighted_entry(np.random.default_rng(3), 50, ATM["V"], 0.0, ATM["T"], M)
    TB.trace_channel(np.random.default_rng(4), v0, R, 0.05, 0.5, 350.0, M, max_hits_cap=0)
    with pytest.raises(ValueError, match="DIV-04"):
        TB.trace_channel(np.random.default_rng(4), v0, R, 0.05, 0.5, 350.0, M, max_hits_cap=0, backend="rust")
    rep = json.load(open(REPORT))
    assert "DIV-04" in {d["id"] for d in rep["documented_divergence"]}


def test_admission_gate_cached_and_revalidated_on_change(monkeypatch, tmp_path):
    """RUST-R1-01: the full admission check (report load + sha256 of sources and extension) runs once per process and
    again only when the stat fingerprint of the report, the extension or a listed source changes."""
    repo = tmp_path / "repo"
    (repo / "docs/performance/abep_core").mkdir(parents=True)
    src = repo / "src.rs"
    src.write_text("fn main() {}\n")
    fake = _fake_extension(tmp_path)
    so = os.path.join(os.path.dirname(fake.__file__), "abep_core.cpython-311-x86_64-linux-gnu.so")
    rep = {"build_provenance": {"extension_sha256": TB._sha256(so), "source_sha256": {"src.rs": TB._sha256(str(src))}},
           "verdicts": {"K4_trace": "ADMITTED"}}
    (repo / TB.PARITY_REPORT).write_text(json.dumps(rep))
    monkeypatch.setattr(TB, "REPO", str(repo))
    TB.clear_admission_cache()
    calls = []
    real = TB.admission_status
    monkeypatch.setattr(TB, "admission_status", lambda m, k=None: calls.append(k) or real(m, k))
    for _ in range(5):
        assert TB.admission_status_cached(fake, "K4_trace")[0]
    assert len(calls) == 1                                   # validated once, then served from the cache
    src.write_text("fn main() { changed(); }\n")             # source drift on disk -> fingerprint changes
    ok, why = TB.admission_status_cached(fake, "K4_trace")
    assert not ok and "src.rs" in why and len(calls) == 2
    TB.clear_admission_cache()
