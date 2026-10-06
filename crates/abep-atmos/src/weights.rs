//! Separable interpolation weights of the orbit datasets (`atmosphere_orbit._trig_weights`, `_lagrange_weights`,
//! `_axis_weights`; `atmosphere_orbit_v2._periodic_cubic_weights`, `_dist_weights`), evaluated with the reference's
//! operation order.

use crate::pyfloat::{np_interp, py_mod, searchsorted_left, TWO_PI};
use abep_data::orbit_v1::{ALT_KM, DOY, DOY_M, DOY_PERIOD, LAT_DEG, LON_DEG, LST_H};

/// Trigonometric interpolation weights on m equispaced periodic nodes k * period / m (m even; Nyquist term as cosine).
pub fn trig_weights(x: f64, period: f64, m: usize) -> Vec<f64> {
    let th: Vec<f64> = (0..m).map(|k| TWO_PI * (x - (k as f64 * period) / m as f64) / period).collect();
    let mut w = vec![1.0; m];
    for k in 1..m / 2 {
        for (wi, t) in w.iter_mut().zip(&th) {
            *wi += 2.0 * (k as f64 * t).cos();
        }
    }
    let h = (m / 2) as f64;
    for (wi, t) in w.iter_mut().zip(&th) {
        *wi += (h * t).cos();
        *wi /= m as f64;
    }
    w
}

/// Local cubic Lagrange weights on the 4 nearest nodes (window clipped at the ends); exact (one-hot) at nodes.
pub fn lagrange_weights(x: f64, nodes: &[f64]) -> Vec<f64> {
    let n = nodes.len();
    let mut w = vec![0.0; n];
    if let Some(hit) = nodes.iter().position(|v| *v == x) {
        w[hit] = 1.0;
        return w;
    }
    let i0 = (searchsorted_left(nodes, x) as i64 - 2).clamp(0, n as i64 - 4) as usize;
    for j in i0..i0 + 4 {
        let mut wj = 1.0;
        for k in i0..i0 + 4 {
            if k != j {
                wj *= (x - nodes[k]) / (nodes[j] - nodes[k]);
            }
        }
        w[j] = wj;
    }
    w
}

/// Position of a day of year on the equispaced doy axis: the integer node days are warped piecewise-linearly onto
/// k * 365/8 (|shift| <= 0.5 d), doy 366 closing the period.
pub fn doy_position(x: f64) -> f64 {
    let mut xp = DOY.to_vec();
    xp.push(DOY[0] + DOY_PERIOD);
    let fp: Vec<f64> = (0..=DOY_M).map(|k| k as f64 * DOY_PERIOD / DOY_M as f64).collect();
    np_interp(x, &xp, &fp)
}

/// Axis of the orbit-v1 grid.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Axis {
    Doy,
    Alt,
    Lat,
    Lon,
    Lst,
}

/// `atmosphere_orbit._axis_weights(name, x)`.
pub fn axis_weights(axis: Axis, x: f64) -> Vec<f64> {
    match axis {
        Axis::Doy => trig_weights(doy_position(x), DOY_PERIOD, DOY_M),
        Axis::Lst => trig_weights(py_mod(x, 24.0), 24.0, LST_H.len()),
        Axis::Lon => trig_weights(py_mod(x, 360.0), 360.0, LON_DEG.len()),
        Axis::Alt => lagrange_weights(x, &ALT_KM),
        Axis::Lat => lagrange_weights(x, &LAT_DEG),
    }
}

/// Local cubic Lagrange weights on m equispaced periodic nodes k * period / m (nodes k-1..k+2); exact at nodes.
pub fn periodic_cubic_weights(x: f64, period: f64, m: usize) -> Vec<f64> {
    let t = py_mod(x, period) / (period / m as f64);
    let i = t.floor() as i64;
    let f = t - i as f64;
    let mut w = vec![0.0; m];
    if f == 0.0 {
        w[i.rem_euclid(m as i64) as usize] = 1.0;
        return w;
    }
    for j in [-1_i64, 0, 1, 2] {
        let mut c = 1.0;
        for k in [-1_i64, 0, 1, 2] {
            if k != j {
                c *= (f - k as f64) / ((j - k) as f64);
            }
        }
        w[(i + j).rem_euclid(m as i64) as usize] += c;
    }
    w
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn weights_sum_to_one_and_are_exact_at_nodes() {
        for x in [1.0, 47.0, 100.3, 364.9] {
            let w = axis_weights(Axis::Doy, x);
            assert!((w.iter().sum::<f64>() - 1.0).abs() < 1e-14);
        }
        assert_eq!(axis_weights(Axis::Doy, 47.0)[1], 1.0);
        assert_eq!(axis_weights(Axis::Lst, 24.0)[0], 1.0);
        let w = axis_weights(Axis::Lat, 37.0);
        assert!((w.iter().sum::<f64>() - 1.0).abs() < 1e-14);
        assert_eq!(axis_weights(Axis::Alt, 195.0), vec![0.0, 1.0, 0.0, 0.0]);
        let p = periodic_cubic_weights(359.5, 360.0, 24);
        assert!((p.iter().sum::<f64>() - 1.0).abs() < 1e-14);
        assert_eq!(periodic_cubic_weights(15.0, 360.0, 24)[1], 1.0);
    }
}
