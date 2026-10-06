//! Temperature-dependent property forms (prereg `nodes.thermal_mass_representation`, E-03, E-05, E-09, D-01).
//!
//! A form is evaluated only inside its registered [T_min, T_max]: no extrapolation and no clamping (D-01). Integrals are
//! exact for the registered form (enthalpy H(T) = integral of C, Kirchhoff Theta = integral of k).

use serde::{Deserialize, Serialize};

/// Registered property form. Polynomials are in (T - T0_K); tables are piecewise linear in T.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "form", rename_all = "SCREAMING_SNAKE_CASE", deny_unknown_fields)]
pub enum PropertyForm {
    Constant {
        value: f64,
    },
    Polynomial {
        #[serde(rename = "T0_K")]
        t0_k: f64,
        coefficients: Vec<f64>,
    },
    PiecewiseLinear {
        #[serde(rename = "T_K")]
        t_k: Vec<f64>,
        values: Vec<f64>,
    },
}

/// A property form bound to its record id and validity range.
#[derive(Debug, Clone)]
pub struct Prop {
    pub record_id: String,
    pub form: PropertyForm,
    pub t_min: f64,
    pub t_max: f64,
}

/// An evaluation outside the registered validity range (D-01).
#[derive(Debug, Clone, PartialEq)]
pub struct DomainViolation {
    pub record_id: String,
    pub t_k: f64,
    pub t_min_k: f64,
    pub t_max_k: f64,
}

impl PropertyForm {
    /// Structural check of the form against [t_min, t_max]: finite numbers, a strictly increasing table covering the
    /// range. Returns a description of the defect.
    pub fn check(&self, t_min: f64, t_max: f64) -> Result<(), String> {
        if !(t_min.is_finite() && t_max.is_finite() && t_min < t_max) {
            return Err(format!("invalid validity range [{t_min}, {t_max}] K"));
        }
        match self {
            PropertyForm::Constant { value } => {
                if !value.is_finite() {
                    return Err("non-finite constant".into());
                }
            }
            PropertyForm::Polynomial { t0_k, coefficients } => {
                if !t0_k.is_finite() || coefficients.is_empty() || coefficients.iter().any(|c| !c.is_finite()) {
                    return Err("polynomial needs a finite T0_K and at least one finite coefficient".into());
                }
            }
            PropertyForm::PiecewiseLinear { t_k, values } => {
                if t_k.len() < 2 || t_k.len() != values.len() {
                    return Err("table needs >= 2 points and equal T_K / values lengths".into());
                }
                if t_k.iter().chain(values.iter()).any(|x| !x.is_finite()) {
                    return Err("non-finite table entry".into());
                }
                if t_k.windows(2).any(|w| w[1] <= w[0]) {
                    return Err("table T_K must be strictly increasing".into());
                }
                if t_k[0] > t_min || t_k[t_k.len() - 1] < t_max {
                    return Err(format!(
                        "table range [{}, {}] K does not cover the validity range [{t_min}, {t_max}] K",
                        t_k[0],
                        t_k[t_k.len() - 1]
                    ));
                }
            }
        }
        Ok(())
    }

    /// Value at T (caller guarantees T inside the validity range).
    pub fn value(&self, t: f64) -> f64 {
        match self {
            PropertyForm::Constant { value } => *value,
            PropertyForm::Polynomial { t0_k, coefficients } => {
                let x = t - t0_k;
                coefficients.iter().rev().fold(0.0, |acc, c| acc * x + c)
            }
            PropertyForm::PiecewiseLinear { t_k, values } => {
                let j = segment(t_k, t);
                let f = (t - t_k[j]) / (t_k[j + 1] - t_k[j]);
                values[j] + f * (values[j + 1] - values[j])
            }
        }
    }

    /// dvalue/dT at T. On a table knot the right-hand segment slope is used.
    pub fn derivative(&self, t: f64) -> f64 {
        match self {
            PropertyForm::Constant { .. } => 0.0,
            PropertyForm::Polynomial { t0_k, coefficients } => {
                let x = t - t0_k;
                let mut acc = 0.0;
                for (n, c) in coefficients.iter().enumerate().skip(1).rev() {
                    acc = acc * x + (n as f64) * c;
                }
                acc
            }
            PropertyForm::PiecewiseLinear { t_k, values } => {
                let j = segment(t_k, t);
                (values[j + 1] - values[j]) / (t_k[j + 1] - t_k[j])
            }
        }
    }

    /// Exact integral of the form from `a` to `b` (signed; both inside the validity range).
    pub fn integral(&self, a: f64, b: f64) -> f64 {
        if a == b {
            return 0.0;
        }
        match self {
            PropertyForm::Constant { value } => value * (b - a),
            PropertyForm::Polynomial { t0_k, coefficients } => {
                // sum_n c_n (x^(n+1) - y^(n+1)) / (n+1), with x^(n+1) - y^(n+1) = (x - y) sum_k x^k y^(n-k)
                // (no cancellation for b close to a).
                let x = b - t0_k;
                let y = a - t0_k;
                let d = b - a;
                let mut total = 0.0;
                for (n, c) in coefficients.iter().enumerate() {
                    let mut s = 0.0;
                    let mut xp = 1.0;
                    for k in 0..=n {
                        s += xp * y.powi((n - k) as i32);
                        xp *= x;
                    }
                    total += c * d * s / ((n + 1) as f64);
                }
                total
            }
            PropertyForm::PiecewiseLinear { t_k, values } => {
                let (lo, hi, sign) = if a < b { (a, b, 1.0) } else { (b, a, -1.0) };
                let mut total = 0.0;
                for j in 0..t_k.len() - 1 {
                    let l = lo.max(t_k[j]);
                    let u = hi.min(t_k[j + 1]);
                    if u > l {
                        let s = (values[j + 1] - values[j]) / (t_k[j + 1] - t_k[j]);
                        let vl = values[j] + s * (l - t_k[j]);
                        let vu = values[j] + s * (u - t_k[j]);
                        total += (u - l) * 0.5 * (vl + vu);
                    }
                }
                sign * total
            }
        }
    }
}

fn segment(t_k: &[f64], t: f64) -> usize {
    let n = t_k.len();
    match t_k.binary_search_by(|x| x.partial_cmp(&t).unwrap_or(std::cmp::Ordering::Less)) {
        Ok(i) => i.min(n - 2),
        Err(i) => i.saturating_sub(1).min(n - 2),
    }
}

impl Prop {
    pub fn in_domain(&self, t: f64) -> bool {
        t >= self.t_min && t <= self.t_max
    }

    fn check_domain(&self, t: f64) -> Result<(), DomainViolation> {
        if self.in_domain(t) {
            Ok(())
        } else {
            Err(DomainViolation { record_id: self.record_id.clone(), t_k: t, t_min_k: self.t_min, t_max_k: self.t_max })
        }
    }

    pub fn value(&self, t: f64) -> Result<f64, DomainViolation> {
        self.check_domain(t)?;
        Ok(self.form.value(t))
    }

    pub fn derivative(&self, t: f64) -> Result<f64, DomainViolation> {
        self.check_domain(t)?;
        Ok(self.form.derivative(t))
    }

    pub fn integral(&self, a: f64, b: f64) -> Result<f64, DomainViolation> {
        self.check_domain(a)?;
        self.check_domain(b)?;
        Ok(self.form.integral(a, b))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn polynomial_integral_is_exact_and_antisymmetric() {
        let f = PropertyForm::Polynomial { t0_k: 300.0, coefficients: vec![10.0, 0.01, 1e-5] };
        // closed form: 10 x + 0.005 x^2 + 1e-5 x^3 / 3 from x = -100 to 200
        let p = |x: f64| 10.0 * x + 0.005 * x * x + 1e-5 * x * x * x / 3.0;
        let exact = p(200.0) - p(-100.0);
        let got = f.integral(200.0, 500.0);
        assert!((got - exact).abs() <= 1e-12 * exact.abs());
        assert_eq!(f.integral(500.0, 200.0), -got);
        assert!((f.derivative(400.0) - (0.01 + 2.0 * 1e-5 * 100.0)).abs() < 1e-15);
    }

    #[test]
    fn table_integral_matches_trapezoids() {
        let f = PropertyForm::PiecewiseLinear { t_k: vec![100.0, 200.0, 400.0], values: vec![1.0, 3.0, 4.0] };
        assert!(f.check(100.0, 400.0).is_ok());
        assert!(f.check(50.0, 400.0).is_err());
        let exact = 0.5 * (2.0 + 3.0) * 50.0 + 0.5 * (3.0 + 3.5) * 100.0;
        assert!((f.integral(150.0, 300.0) - exact).abs() < 1e-12);
        assert_eq!(f.value(200.0), 3.0);
        assert_eq!(f.derivative(200.0), 0.005);
    }

    #[test]
    fn evaluation_outside_range_is_refused() {
        let p = Prop { record_id: "r".into(), form: PropertyForm::Constant { value: 1.0 }, t_min: 200.0, t_max: 300.0 };
        assert!(p.value(300.0).is_ok());
        let e = p.value(300.000001).unwrap_err();
        assert_eq!(e.record_id, "r");
        assert!(p.integral(250.0, 199.0).is_err());
    }
}
