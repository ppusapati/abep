//! abep_core - optional native kernels for the ABEP-VLEO simulator (owner directive A9.7, Rust admission order
//! item 1: TPMC particle-tracing kernel).
//!
//! Python remains authoritative. This crate ports `abep_sim/intake_tpmc.py` (trace_channel and the entry /
//! diffuse / CLL sampling it uses) with identical physics and I/O semantics; only the random stream differs.
//! A kernel is used only when explicitly requested through `abep_sim/design/tpmc_backend.py` (backend="rust"),
//! never by default, never by archengine, never for frozen data or goldens. Admission: the pre-registered parity
//! campaign docs/performance/abep_core/parity_prereg_v1.json, run by scripts/verify_abep_core.py.

pub mod rng;
pub mod tpmc;

#[cfg(feature = "python")]
mod python {
    use crate::rng::{Rng, RNG_ALGORITHM};
    use crate::tpmc::{self, Scattering, TpmcError, TraceParams, V3, K_B};
    use numpy::ndarray::Array2;
    use numpy::{IntoPyArray, PyArray1, PyArray2, PyReadonlyArray2, PyUntypedArrayMethods};
    use pyo3::exceptions::PyValueError;
    use pyo3::prelude::*;

    fn to_pyerr(e: TpmcError) -> PyErr {
        PyValueError::new_err(e.to_string())
    }

    fn rows(a: &PyReadonlyArray2<'_, f64>, name: &str) -> PyResult<Vec<V3>> {
        let shape = a.shape();
        if shape.len() != 2 || shape[1] != 3 {
            return Err(PyValueError::new_err(format!("abep_core: {} must have shape (n, 3), got {:?}", name, shape)));
        }
        let view = a.as_array();
        Ok(view.outer_iter().map(|r| [r[0], r[1], r[2]]).collect())
    }

    fn to_array2(v: &[V3]) -> Array2<f64> {
        let mut out = Array2::<f64>::zeros((v.len(), 3));
        for (i, r) in v.iter().enumerate() {
            out[[i, 0]] = r[0];
            out[[i, 1]] = r[1];
            out[[i, 2]] = r[2];
        }
        out
    }

    /// Reference _flux_weighted_entry. Returns float64 (n, 3).
    #[pyfunction]
    #[pyo3(signature = (seed, n, v_drift, theta, t, m))]
    fn flux_weighted_entry<'py>(
        py: Python<'py>,
        seed: u64,
        n: usize,
        v_drift: f64,
        theta: f64,
        t: f64,
        m: f64,
    ) -> PyResult<Bound<'py, PyArray2<f64>>> {
        let mut rng = Rng::new(seed);
        let v = tpmc::flux_weighted_entry(&mut rng, n, v_drift, theta, t, m).map_err(to_pyerr)?;
        Ok(to_array2(&v).into_pyarray(py))
    }

    /// Reference _diffuse: cosine-law re-emission about each row of `normal` (n, 3).
    #[pyfunction]
    #[pyo3(signature = (seed, normal, t_w, m))]
    fn diffuse<'py>(
        py: Python<'py>,
        seed: u64,
        normal: PyReadonlyArray2<'py, f64>,
        t_w: f64,
        m: f64,
    ) -> PyResult<Bound<'py, PyArray2<f64>>> {
        let nr = rows(&normal, "normal")?;
        let mut rng = Rng::new(seed);
        Ok(to_array2(&tpmc::diffuse(&mut rng, &nr, t_w, m)).into_pyarray(py))
    }

    /// Reference _cll (Cercignani-Lampis-Lord, Lord 1991 sampling).
    #[pyfunction]
    #[pyo3(signature = (seed, v_in, normal, t_w, m, alpha_n, alpha_t))]
    #[allow(clippy::too_many_arguments)]
    fn cll<'py>(
        py: Python<'py>,
        seed: u64,
        v_in: PyReadonlyArray2<'py, f64>,
        normal: PyReadonlyArray2<'py, f64>,
        t_w: f64,
        m: f64,
        alpha_n: f64,
        alpha_t: f64,
    ) -> PyResult<Bound<'py, PyArray2<f64>>> {
        let vi = rows(&v_in, "v_in")?;
        let nr = rows(&normal, "normal")?;
        let mut rng = Rng::new(seed);
        let out = tpmc::cll(&mut rng, &vi, &nr, t_w, m, alpha_n, alpha_t).map_err(to_pyerr)?;
        Ok(to_array2(&out).into_pyarray(py))
    }

    type TraceOut<'py> =
        (Bound<'py, PyArray1<bool>>, Bound<'py, PyArray2<f64>>, Bound<'py, PyArray1<i64>>, Bound<'py, PyArray1<bool>>, f64);

    /// Reference trace_channel. Returns (collected bool (n,), final velocities float64 (n,3), wall hits int64 (n,),
    /// back bool (n,), unresolved fraction float).
    #[pyfunction]
    #[pyo3(signature = (seed, v0, r, l, alpha, t_w, m, max_hits=200, scattering="maxwell", alpha_n=None, alpha_t=None,
                        unresolved_tol=1e-3, max_hits_cap=5000))]
    #[allow(clippy::too_many_arguments)]
    fn trace_channel<'py>(
        py: Python<'py>,
        seed: u64,
        v0: PyReadonlyArray2<'py, f64>,
        r: f64,
        l: f64,
        alpha: f64,
        t_w: f64,
        m: f64,
        max_hits: i64,
        scattering: &str,
        alpha_n: Option<f64>,
        alpha_t: Option<f64>,
        unresolved_tol: f64,
        max_hits_cap: i64,
    ) -> PyResult<TraceOut<'py>> {
        let v0r = rows(&v0, "v0")?;
        if max_hits < 1 || max_hits_cap < 1 {
            return Err(PyValueError::new_err(
                "abep_core.trace_channel: max_hits and max_hits_cap must be >= 1 (the reference never terminates for max_hits = 0)",
            ));
        }
        let p = TraceParams {
            r,
            l,
            alpha,
            t_w,
            m,
            max_hits: max_hits as usize,
            scattering: Scattering::parse(scattering).map_err(to_pyerr)?,
            alpha_n,
            alpha_t,
            unresolved_tol,
            max_hits_cap: max_hits_cap as usize,
        };
        let mut rng = Rng::new(seed);
        let res = tpmc::trace_channel(&mut rng, &v0r, &p).map_err(to_pyerr)?;
        Ok((
            res.collected.into_pyarray(py),
            to_array2(&res.v).into_pyarray(py),
            res.hits.into_pyarray(py),
            res.back.into_pyarray(py),
            res.unresolved,
        ))
    }

    /// Reference clausing_transmission: fraction of thermal molecules entering from the plenum side that leave the front.
    #[pyfunction]
    #[pyo3(signature = (seed, r, l, alpha, t_w, m, n=20000))]
    fn clausing_transmission(seed: u64, r: f64, l: f64, alpha: f64, t_w: f64, m: f64, n: usize) -> PyResult<f64> {
        let mut rng = Rng::new(seed);
        tpmc::clausing_transmission(&mut rng, r, l, alpha, t_w, m, n).map_err(to_pyerr)
    }

    #[pymodule]
    fn abep_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
        m.add("__version__", env!("CARGO_PKG_VERSION"))?;
        m.add("K_B", K_B)?;
        m.add("RNG_ALGORITHM", RNG_ALGORITHM)?;
        m.add(
            "REFERENCE",
            "abep_sim/intake_tpmc.py (authoritative); parity: docs/performance/abep_core/parity_prereg_v1.json",
        )?;
        m.add_function(wrap_pyfunction!(flux_weighted_entry, m)?)?;
        m.add_function(wrap_pyfunction!(diffuse, m)?)?;
        m.add_function(wrap_pyfunction!(cll, m)?)?;
        m.add_function(wrap_pyfunction!(trace_channel, m)?)?;
        m.add_function(wrap_pyfunction!(clausing_transmission, m)?)?;
        // maturin's package __init__ does `from .abep_core import *`; an explicit __all__ keeps __version__ visible.
        m.add(
            "__all__",
            vec![
                "__version__",
                "K_B",
                "RNG_ALGORITHM",
                "REFERENCE",
                "flux_weighted_entry",
                "diffuse",
                "cll",
                "trace_channel",
                "clausing_transmission",
            ],
        )?;
        Ok(())
    }
}
