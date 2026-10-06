//! The numpy 2.4.4 routines `rate_tables.py` calls, reproduced operation by operation (contract
//! `reference_implementation.reference_algorithm_read`). Every function gives the bits numpy gives for the same
//! float64 inputs; the float64 `exp` of an array is the one routine not reproduced here (numpy dispatches it to SVML on
//! AVX512_SKX hosts; the caller uses glibc `exp`, and the contract bounds the difference).

use abep_types::pyjson::{PyException, PyResult};
use std::cmp::Ordering;

/// `np.linspace(0, stop, num)` (endpoint=True, num >= 2), `numpy/_core/function_base.py`: `step = delta / div`,
/// `y = arange(num) * step` (when `step == 0`: `arange(num) / div * delta`), `y += 0`, `y[-1] = stop`.
pub fn linspace_from_zero(stop: f64, num: usize) -> Vec<f64> {
    assert!(num >= 2, "linspace_from_zero needs num >= 2");
    let div = (num - 1) as f64;
    let delta = stop - 0.0;
    let step = delta / div;
    let mut y: Vec<f64> = if step == 0.0 {
        (0..num).map(|i| i as f64 / div * delta + 0.0).collect()
    } else {
        (0..num).map(|i| i as f64 * step + 0.0).collect()
    };
    y[num - 1] = stop;
    y
}

/// numpy's sort order for float64: ascending, NaN after everything.
fn nan_last(a: &f64, b: &f64) -> Ordering {
    match (a.is_nan(), b.is_nan()) {
        (false, false) => a.partial_cmp(b).unwrap_or(Ordering::Equal),
        (false, true) => Ordering::Less,
        (true, false) => Ordering::Greater,
        (true, true) => Ordering::Equal,
    }
}

/// `np.unique` of a float64 array (`_unique1d`, sorting path: float64 has no hash path): sorted, equal values
/// collapsed (`aux[1:] != aux[:-1]`), all NaNs collapsed to one trailing NaN (`equal_nan=True`).
pub fn unique(mut v: Vec<f64>) -> Vec<f64> {
    v.sort_by(nan_last);
    let mut out: Vec<f64> = Vec::with_capacity(v.len());
    for x in v {
        match out.last() {
            Some(&last) if last == x || (last.is_nan() && x.is_nan()) => {}
            _ => out.push(x),
        }
    }
    out
}

const LIKELY_IN_CACHE_SIZE: usize = 8;

/// `binary_search_with_guess` of `numpy/_core/src/multiarray/compiled_base.c`: returns -1 for `key < arr[0]`, `len` for
/// `key > arr[len - 1]`, otherwise an index found from the guess window or by bisection. `arr` is not required to be
/// sorted (numpy does not check); the search is reproduced exactly, so unsorted input gives numpy's index.
pub fn binary_search_with_guess(key: f64, arr: &[f64], guess: isize) -> isize {
    let len = arr.len() as isize;
    let at = |i: isize| arr[i as usize];
    let mut imin: isize = 0;
    let mut imax: isize = len;
    if key > at(len - 1) {
        return len;
    } else if key < at(0) {
        return -1;
    }
    if len <= 4 {
        let mut i: isize = 1;
        while i < len && key >= at(i) {
            i += 1;
        }
        return i - 1;
    }
    let cache = LIKELY_IN_CACHE_SIZE as isize;
    let mut guess = guess;
    if guess > len - 3 {
        guess = len - 3;
    }
    if guess < 1 {
        guess = 1;
    }
    if key < at(guess) {
        if key < at(guess - 1) {
            imax = guess - 1;
            if guess > cache && key >= at(guess - cache) {
                imin = guess - cache;
            }
        } else {
            return guess - 1;
        }
    } else if key < at(guess + 1) {
        return guess;
    } else if key < at(guess + 2) {
        return guess + 1;
    } else {
        imin = guess + 2;
        if guess < len - cache - 1 && key < at(guess + cache) {
            imax = guess + cache;
        }
    }
    while imin < imax {
        let imid = imin + ((imax - imin) >> 1);
        if key >= at(imid) {
            imin = imid + 1;
        } else {
            imax = imid;
        }
    }
    imin - 1
}

/// `np.interp(x, xp, fp, left, right)` for float64 (`arr_interp`): the `len(xp) == 1` branch, then per key the
/// guessed search (the guess is the previous index), `fp[j]` at the last point or an exact hit, otherwise
/// `slope * (x - xp[j]) + fp[j]` with `slope = (fp[j+1] - fp[j]) / (xp[j+1] - xp[j])` and numpy's NaN fallback.
pub fn interp(x: &[f64], xp: &[f64], fp: &[f64], left: f64, right: f64) -> PyResult<Vec<f64>> {
    let lenxp = xp.len();
    if lenxp == 0 {
        return Err(PyException::new("ValueError", "array of sample points is empty"));
    }
    if fp.len() != lenxp {
        return Err(PyException::new("ValueError", "fp and xp are not of the same length."));
    }
    if lenxp == 1 {
        let (xp0, fp0) = (xp[0], fp[0]);
        return Ok(x
            .iter()
            .map(|&xv| {
                if xv < xp0 {
                    left
                } else if xv > xp0 {
                    right
                } else {
                    fp0
                }
            })
            .collect());
    }
    let len = lenxp as isize;
    // numpy precomputes the slopes when len(xp) <= len(x) and otherwise evaluates the same expression per key: the
    // same bits either way.
    let slopes: Vec<f64> = (0..lenxp - 1).map(|i| (fp[i + 1] - fp[i]) / (xp[i + 1] - xp[i])).collect();
    let mut out = Vec::with_capacity(x.len());
    let mut j: isize = 0;
    for &xv in x {
        if xv.is_nan() {
            out.push(xv);
            continue;
        }
        j = binary_search_with_guess(xv, xp, j);
        let v = if j == -1 {
            left
        } else if j == len {
            right
        } else if j == len - 1 {
            fp[j as usize]
        } else {
            let ju = j as usize;
            if xp[ju] == xv {
                fp[ju]
            } else {
                let slope = slopes[ju];
                let mut r = slope * (xv - xp[ju]) + fp[ju];
                if r.is_nan() {
                    r = slope * (xv - xp[ju + 1]) + fp[ju + 1];
                    if r.is_nan() && fp[ju] == fp[ju + 1] {
                        r = fp[ju];
                    }
                }
                r
            }
        };
        out.push(v);
    }
    Ok(out)
}

const PW_BLOCKSIZE: usize = 128;

/// `DOUBLE_pairwise_sum` of `numpy/_core/src/umath/loops_utils.h.src`.
pub fn pairwise_sum(a: &[f64]) -> f64 {
    let n = a.len();
    if n < 8 {
        let mut res = -0.0;
        for &v in a {
            res += v;
        }
        res
    } else if n <= PW_BLOCKSIZE {
        let mut r = [a[0], a[1], a[2], a[3], a[4], a[5], a[6], a[7]];
        let mut i = 8;
        while i < n - (n % 8) {
            for (k, rk) in r.iter_mut().enumerate() {
                *rk += a[i + k];
            }
            i += 8;
        }
        let mut res = ((r[0] + r[1]) + (r[2] + r[3])) + ((r[4] + r[5]) + (r[6] + r[7]));
        while i < n {
            res += a[i];
            i += 1;
        }
        res
    } else {
        let mut n2 = n / 2;
        n2 -= n2 % 8;
        pairwise_sum(&a[..n2]) + pairwise_sum(&a[n2..])
    }
}

/// `np.add.reduce` of a contiguous 1-D float64 array: the identity 0.0 plus the pairwise sum of all elements.
pub fn sum(a: &[f64]) -> f64 {
    0.0 + pairwise_sum(a)
}

/// `np.trapezoid(y, x)` for 1-D float64: `(diff(x) * (y[1:] + y[:-1]) / 2.0).sum()`.
pub fn trapezoid(y: &[f64], x: &[f64]) -> f64 {
    assert_eq!(y.len(), x.len(), "trapezoid needs equal lengths");
    let terms: Vec<f64> = (1..x.len()).map(|i| ((x[i] - x[i - 1]) * (y[i] + y[i - 1])) / 2.0).collect();
    sum(&terms)
}

/// Length of `np.arange(start, stop, step)` for float arguments (`_calc_length` in `ctors.c`): NaN ->
/// `ValueError('arange: cannot compute length')`; a ceiling outside the intp range -> numpy's OverflowError, re-raised
/// by `PyArray_ArangeObj` as `ValueError('Maximum allowed size exceeded')`; a non-positive length is 0.
pub fn arange_len(start: f64, stop: f64, step: f64) -> PyResult<usize> {
    let next = stop - start;
    let val = next / step;
    let len = if val == 0.0 && next != 0.0 {
        if val.is_sign_negative() {
            0
        } else {
            1
        }
    } else {
        let c = val.ceil();
        if c.is_nan() {
            return Err(PyException::new("ValueError", "arange: cannot compute length"));
        }
        if !((i64::MIN as f64) <= c && c <= (i64::MAX as f64)) {
            return Err(PyException::new("ValueError", "Maximum allowed size exceeded"));
        }
        c as i64
    };
    Ok(if len <= 0 { 0 } else { len as usize })
}

/// Values of `np.arange(start, stop, step)` of length `n` (`DOUBLE_fill`): `start`, `start + step`, then
/// `start + i * delta` with `delta = (start + step) - start`.
pub fn arange_values(start: f64, step: f64, n: usize) -> Vec<f64> {
    let mut out = Vec::with_capacity(n);
    if n >= 1 {
        out.push(start);
    }
    if n >= 2 {
        let next = start + step;
        out.push(next);
        let delta = next - start;
        for i in 2..n {
            out.push(start + i as f64 * delta);
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn linspace_endpoints_and_step() {
        let y = linspace_from_zero(1000.0, 20000);
        assert_eq!(y.len(), 20000);
        assert_eq!(y[0], 0.0);
        assert_eq!(y[19999], 1000.0);
        assert_eq!(y[1], 1000.0 / 19999.0);
        assert_eq!(y[12345], 12345.0 * (1000.0 / 19999.0));
    }

    #[test]
    fn unique_sorts_dedups_and_collapses_nan() {
        let u = unique(vec![3.0, f64::NAN, 1.0, 3.0, f64::NAN, 2.0, 1.0]);
        assert_eq!(u.len(), 4);
        assert_eq!(&u[..3], &[1.0, 2.0, 3.0]);
        assert!(u[3].is_nan());
    }

    #[test]
    fn interp_brackets_and_extrapolation_values() {
        let xp = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0];
        let fp = [0.0, 10.0, 20.0, 30.0, 40.0, 50.0];
        let r = interp(&[-1.0, 0.5, 2.0, 4.5, 5.0, 6.0, f64::NAN], &xp, &fp, -7.0, 99.0).unwrap();
        assert_eq!(&r[..6], &[-7.0, 5.0, 20.0, 45.0, 50.0, 99.0]);
        assert!(r[6].is_nan());
        assert_eq!(interp(&[1.0], &[1.0, 2.0], &[1.0], 0.0, 0.0).unwrap_err().class, "ValueError");
        assert_eq!(interp(&[0.0, 1.0, 2.0], &[1.0], &[7.0], -1.0, 9.0).unwrap(), vec![-1.0, 7.0, 9.0]);
    }

    #[test]
    fn search_returns_a_bracketing_segment_for_unsorted_input() {
        let arr = [10.0, 30.0, 20.0, 40.0, 35.0, 50.0, 45.0, 60.0];
        let mut guess = 0;
        for k in 0..600 {
            let key = 10.0 + k as f64 * 0.1;
            let j = binary_search_with_guess(key, &arr, guess);
            guess = j;
            if (0..arr.len() as isize - 1).contains(&j) {
                assert!(arr[j as usize] <= key && key < arr[j as usize + 1], "key {key} j {j}");
            }
        }
    }

    #[test]
    fn pairwise_sum_structure() {
        assert_eq!(pairwise_sum(&[]).to_bits(), (-0.0f64).to_bits());
        assert_eq!(sum(&[]).to_bits(), 0.0f64.to_bits());
        let a: Vec<f64> = (0..1000).map(|i| 1.0 / (1.0 + i as f64)).collect();
        let naive: f64 = a.iter().sum();
        assert!((pairwise_sum(&a) - naive).abs() < 1e-12);
        assert_eq!(trapezoid(&[1.0, 1.0, 1.0], &[0.0, 1.0, 3.0]), 3.0);
    }

    #[test]
    fn arange_lengths_and_errors() {
        assert_eq!(arange_len(0.0, 301.0, 1.0).unwrap(), 301);
        assert_eq!(arange_len(0.0, 11.5, 1.0).unwrap(), 12);
        assert_eq!(arange_len(0.0, 0.0, 1.0).unwrap(), 0);
        assert_eq!(arange_len(0.0, -4.0, 1.0).unwrap(), 0);
        assert_eq!(arange_len(0.0, f64::NAN, 1.0).unwrap_err().message, "arange: cannot compute length");
        for stop in [f64::INFINITY, f64::NEG_INFINITY, -1e300, 1e19] {
            assert_eq!(arange_len(0.0, stop, 1.0).unwrap_err().message, "Maximum allowed size exceeded");
        }
        assert_eq!(arange_values(0.0, 1.0, 4), vec![0.0, 1.0, 2.0, 3.0]);
    }
}
