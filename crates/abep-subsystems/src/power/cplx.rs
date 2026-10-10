//! Complex arithmetic with CPython 3.11 semantics (`Objects/complexobject.c`, `Modules/cmathmodule.c`): int and
//! float operands are promoted to complex(x, 0.0) before the operation, products and quotients use `_Py_c_prod` /
//! `_Py_c_quot`, `abs` is `hypot` with the infinity / NaN rules, and `cmath.rect` keeps its phi == 0 branch. The RF
//! kernels use these so that every result is the reference's, bit for bit.

use super::PowerError;

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct C {
    pub re: f64,
    pub im: f64,
}

// The method names mirror CPython's _Py_c_sum / _diff / _prod / _quot / _neg and keep the reference's evaluation
// order explicit at every call site; operator traits would hide it.
#[allow(clippy::should_implement_trait)]
impl C {
    pub const fn new(re: f64, im: f64) -> Self {
        C { re, im }
    }

    /// `complex(x)` of a real number.
    pub const fn real(x: f64) -> Self {
        C { re: x, im: 0.0 }
    }

    pub fn add(self, o: C) -> C {
        C::new(self.re + o.re, self.im + o.im)
    }

    pub fn sub(self, o: C) -> C {
        C::new(self.re - o.re, self.im - o.im)
    }

    /// `_Py_c_prod`.
    pub fn mul(self, o: C) -> C {
        C::new(self.re * o.re - self.im * o.im, self.re * o.im + self.im * o.re)
    }

    /// `_Py_c_quot`; a zero divisor raises `ZeroDivisionError('complex division by zero')` as `complex.__truediv__`.
    pub fn div(self, b: C) -> Result<C, PowerError> {
        let abs_br = b.re.abs();
        let abs_bi = b.im.abs();
        if abs_br >= abs_bi {
            if abs_br == 0.0 {
                return Err(PowerError::new("ZeroDivisionError", "complex division by zero"));
            }
            let ratio = b.im / b.re;
            let denom = b.re + b.im * ratio;
            Ok(C::new((self.re + self.im * ratio) / denom, (self.im - self.re * ratio) / denom))
        } else if abs_bi >= abs_br {
            let ratio = b.re / b.im;
            let denom = b.re * ratio + b.im;
            Ok(C::new((self.re * ratio + self.im) / denom, (self.im * ratio - self.re) / denom))
        } else {
            Ok(C::new(f64::NAN, f64::NAN))
        }
    }

    pub fn neg(self) -> C {
        C::new(-self.re, -self.im)
    }

    pub fn conj(self) -> C {
        C::new(self.re, -self.im)
    }

    /// `abs(z)` (`_Py_c_abs`).
    pub fn abs(self) -> f64 {
        if !self.re.is_finite() || !self.im.is_finite() {
            if self.re.is_infinite() || self.im.is_infinite() {
                return f64::INFINITY;
            }
            return f64::NAN;
        }
        self.re.hypot(self.im)
    }

    /// `z == 0` / `z == 1` style comparison with a real number.
    pub fn eq_real(self, x: f64) -> bool {
        self.re == x && self.im == 0.0
    }

    pub fn is_zero(self) -> bool {
        self.eq_real(0.0)
    }
}

/// `cmath.rect(r, phi)` for finite arguments (the parse path refuses non-finite values before calling it).
pub fn rect(r: f64, phi: f64) -> C {
    if !(r.is_finite() && phi.is_finite()) {
        return C::new(f64::NAN, f64::NAN);
    }
    if phi == 0.0 {
        C::new(r, r * phi)
    } else {
        C::new(r * phi.cos(), r * phi.sin())
    }
}

/// `math.radians(x)`.
pub fn radians(x: f64) -> f64 {
    x * (std::f64::consts::PI / 180.0)
}

/// Python's built-in `sum` of complex terms, starting at int 0 (3.11: plain left-to-right addition).
pub fn sum<I: IntoIterator<Item = C>>(terms: I) -> C {
    terms.into_iter().fold(C::new(0.0, 0.0), |acc, t| acc.add(t))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn division_follows_smith_branches() {
        let a = C::new(1.0, 2.0);
        let q = a.div(C::new(3.0, 4.0)).unwrap();
        assert!((q.re - 0.44).abs() < 1e-15 && (q.im - 0.08).abs() < 1e-15);
        assert_eq!(a.div(C::new(0.0, 0.0)).unwrap_err().class, "ZeroDivisionError");
        assert_eq!(C::real(1.0).div(C::new(0.0, 2.0)).unwrap(), C::new(0.0, -0.5));
    }

    #[test]
    fn rect_keeps_the_zero_angle_branch() {
        assert_eq!(rect(0.5, 0.0), C::new(0.5, 0.0));
        assert_eq!(rect(0.5, -0.0), C::new(0.5, -0.0));
    }
}
