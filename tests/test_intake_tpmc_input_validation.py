"""A9.9 S2.5 (MCC-05 / MCC-06 / MCC-07): intake_tpmc input validation before tracing.

Invalid hit budgets, unknown wall-scattering models and non-finite / out-of-range accommodation coefficients are
rejected explicitly (ValueError) before any particle is sampled; valid inputs are unchanged."""
import math

import numpy as np
import pytest

from abep_sim import intake_tpmc as T
from abep_sim.atmosphere import atmosphere

ATM = atmosphere(200.0, "mean")
M = ATM["m_mean"]
R, L = 0.005, 0.05


def _v0(n=200):
    return T._flux_weighted_entry(np.random.default_rng(3), n, ATM["V"], 0.0, ATM["T"], M)


# MCC-05 -------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("bad", [0, -1, -200, 1.5, 2.0, "10", None, True, float("nan")])
@pytest.mark.parametrize("name", ["max_hits", "max_hits_cap"])
def test_mcc05_hit_budgets_must_be_positive_integers(name, bad):
    rng = np.random.default_rng(0)
    state = rng.bit_generator.state
    with pytest.raises(ValueError, match=name):
        T.trace_channel(rng, _v0(), R, L, 0.5, 350.0, M, **{name: bad})
    assert rng.bit_generator.state == state                 # refused before the RNG stream is consumed


def test_mcc05_max_hits_zero_terminates_with_error_not_hang():
    with pytest.raises(ValueError, match="max_hits"):
        T.trace_channel(np.random.default_rng(0), _v0(), R, L, 0.5, 350.0, M, max_hits=0)


@pytest.mark.parametrize("bad", [-1e-3, float("nan"), float("inf")])
def test_mcc05_unresolved_tol_validated(bad):
    with pytest.raises(ValueError, match="unresolved_tol"):
        T.trace_channel(np.random.default_rng(0), _v0(), R, L, 0.5, 350.0, M, unresolved_tol=bad)


def test_mcc05_numpy_integer_budgets_accepted():
    a = T.trace_channel(np.random.default_rng(1), _v0(), R, L, 0.5, 350.0, M,
                        max_hits=np.int64(1), max_hits_cap=np.int32(1))
    b = T.trace_channel(np.random.default_rng(1), _v0(), R, L, 0.5, 350.0, M, max_hits=1, max_hits_cap=1)
    assert all(np.array_equal(x, y) for x, y in zip(a, b))


# MCC-06 -------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("bad", ["Maxwell", "MAXWELL", "CLL", "specular", "", None, "diffuse"])
def test_mcc06_unknown_scattering_raises_everywhere(bad):
    rng = np.random.default_rng(0)
    state = rng.bit_generator.state
    with pytest.raises(ValueError, match="scattering"):
        T.trace_channel(rng, _v0(), R, L, 0.5, 350.0, M, scattering=bad)
    assert rng.bit_generator.state == state
    with pytest.raises(ValueError, match="scattering"):
        T.intake_response(T.IntakeGeometry(), ATM, 0.5, 0.0, n=100, scattering=bad)
    with pytest.raises(ValueError, match="scattering"):
        T.response_surface(ATM, L_over_d=(3,), phis=(0.8,), alphas=(0.5,), thetas=(0.0,), n=100, scattering=bad)


@pytest.mark.parametrize("sc", ["maxwell", "cll"])
def test_mcc06_scattering_recorded(sc):
    r = T.intake_response(T.IntakeGeometry(L_over_d=3), ATM, 0.5, 0.0, n=500, scattering=sc)
    assert r["scattering"] == sc
    assert r["K_back_scattering"] == "maxwell"               # thermal back-trace kernel, explicit and recorded


# MCC-07 -------------------------------------------------------------------------------------------------------------
BAD_ALPHAS = [-0.01, 1.01, -1.0, 2.0, float("nan"), float("inf"), -float("inf"), "0.5", True]


@pytest.mark.parametrize("bad", BAD_ALPHAS)
@pytest.mark.parametrize("which", ["alpha_n", "alpha_t"])
def test_mcc07_cll_coefficients_rejected_before_kernel(which, bad):
    rng = np.random.default_rng(0)
    state = rng.bit_generator.state
    with pytest.raises(ValueError, match="alpha"):
        T.trace_channel(rng, _v0(), R, L, 0.5, 350.0, M, scattering="cll", **{which: bad})
    assert rng.bit_generator.state == state
    v_in = np.array([[0.0, 100.0, -7000.0]])
    normal = np.array([[0.0, 0.0, 1.0]])
    kw = {"alpha_n": 0.5, "alpha_t": 0.5, which: bad}
    with pytest.raises(ValueError, match="alpha"):
        T._cll(np.random.default_rng(0), v_in, normal, 350.0, M, kw["alpha_n"], kw["alpha_t"])


@pytest.mark.parametrize("bad", BAD_ALPHAS)
@pytest.mark.parametrize("sc", ["maxwell", "cll"])
def test_mcc07_alpha_rejected_for_both_kernels(sc, bad):
    with pytest.raises(ValueError, match="alpha"):
        T.trace_channel(np.random.default_rng(0), _v0(), R, L, bad, 350.0, M, scattering=sc)
    with pytest.raises(ValueError, match="alpha"):
        T.intake_response(T.IntakeGeometry(), ATM, bad, 0.0, n=100, scattering=sc)
    with pytest.raises(ValueError, match="alpha"):
        T.clausing_transmission(np.random.default_rng(0), R, L, bad, 350.0, M, n=100)


@pytest.mark.parametrize("a_n,a_t", [(0.0, 0.0), (1.0, 1.0), (0.0, 1.0), (1.0, 0.0), (0.3, 0.9)])
def test_mcc07_boundary_values_admitted_and_finite(a_n, a_t):
    col, v, hits, back, unres = T.trace_channel(np.random.default_rng(5), _v0(), R, L, 0.5, 350.0, M,
                                                scattering="cll", alpha_n=a_n, alpha_t=a_t)
    assert np.all(np.isfinite(v)) and math.isfinite(unres)
