//! Exact accumulation (prereg EQ EX-ACC): error-free two-sum expansions (J. R. Shewchuk, "Adaptive precision
//! floating-point arithmetic and fast robust geometric predicates", Discrete Comput. Geom. 18, 1997; verify). An
//! [`ExactSum`] holds a non-overlapping expansion with zero components eliminated, so it represents the exact sum of
//! every binary64 value added; it is zero exactly when it has no component.

use abep_types::{AbepError, AbepResult};

/// Exact running sum of binary64 values.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct ExactSum {
    /// Non-overlapping components in increasing magnitude, no zero component.
    comps: Vec<f64>,
}

#[inline]
fn two_sum(a: f64, b: f64) -> (f64, f64) {
    let s = a + b;
    let bv = s - a;
    let av = s - bv;
    (s, (a - av) + (b - bv))
}

fn overflow(what: &str) -> AbepError {
    AbepError::Model { message: format!("exact accumulation: non-finite {what} (Q-3)") }
}

impl ExactSum {
    pub fn new() -> Self {
        ExactSum { comps: Vec::new() }
    }

    /// Add `x` exactly (Grow-Expansion with zero elimination). A non-finite operand or partial sum is MODEL_ERROR.
    pub fn add(&mut self, x: f64) -> AbepResult<()> {
        if !x.is_finite() {
            return Err(overflow("operand"));
        }
        let mut q = x;
        let mut out = Vec::with_capacity(self.comps.len() + 1);
        for &e in &self.comps {
            let (s, h) = two_sum(q, e);
            if !s.is_finite() {
                return Err(overflow("partial sum"));
            }
            if h != 0.0 {
                out.push(h);
            }
            q = s;
        }
        if q != 0.0 {
            out.push(q);
        }
        self.comps = out;
        Ok(())
    }

    pub fn sub(&mut self, x: f64) -> AbepResult<()> {
        self.add(-x)
    }

    /// Add every component of `other` (exact).
    pub fn add_sum(&mut self, other: &ExactSum) -> AbepResult<()> {
        for &c in &other.comps {
            self.add(c)?;
        }
        Ok(())
    }

    /// Subtract every component of `other` (exact).
    pub fn sub_sum(&mut self, other: &ExactSum) -> AbepResult<()> {
        for &c in &other.comps {
            self.add(-c)?;
        }
        Ok(())
    }

    /// True when the represented value is exactly zero.
    pub fn is_zero(&self) -> bool {
        self.comps.is_empty()
    }

    /// The reported value: the components summed from the smallest to the largest magnitude (faithful rounding).
    pub fn value(&self) -> f64 {
        self.comps.iter().fold(0.0, |acc, c| acc + c)
    }

    pub fn components(&self) -> &[f64] {
        &self.comps
    }

    /// Exact sum of a slice.
    pub fn of(values: &[f64]) -> AbepResult<Self> {
        let mut s = ExactSum::new();
        for &v in values {
            s.add(v)?;
        }
        Ok(s)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn cancellation_is_exact() {
        let s = ExactSum::of(&[1e20 * 3600.0, -1e20 * 3600.0, 3600.0]).unwrap();
        assert_eq!(s.value(), 3600.0);
        let naive = 1e20 * 3600.0 + -1e20 * 3600.0;
        assert_eq!(naive + 3600.0, 3600.0);
        let t = ExactSum::of(&[1e20, 1.0, -1e20]).unwrap();
        assert_eq!(t.value(), 1.0);
        assert_eq!((1e20 + 1.0) - 1e20, 0.0);
    }

    #[test]
    fn zero_detection_is_exact() {
        let mut s = ExactSum::of(&[0.1, 0.2]).unwrap();
        s.sub(0.3).unwrap();
        assert!(!s.is_zero(), "0.1 + 0.2 - 0.3 is not zero in binary64 values");
        let mut t = ExactSum::of(&[0.1, 0.2]).unwrap();
        t.sub(0.1).unwrap();
        t.sub(0.2).unwrap();
        assert!(t.is_zero());
    }

    #[test]
    fn non_finite_is_refused() {
        assert!(ExactSum::new().add(f64::INFINITY).is_err());
        let mut s = ExactSum::of(&[f64::MAX]).unwrap();
        assert!(s.add(f64::MAX).is_err());
    }
}
