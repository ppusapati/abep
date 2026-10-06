//! Time-varying inputs: constants or zero-order-hold series with registered breakpoints (A-07, E-11, E-12).

/// A constant or a ZOH series: `values[k]` holds on [breakpoints_s[k], breakpoints_s[k+1]); the last value holds to the
/// end of the run (or of the orbit period).
#[derive(Debug, Clone, PartialEq)]
pub enum TimeValue {
    Constant(f64),
    Zoh { t: Vec<f64>, v: Vec<f64> },
}

impl TimeValue {
    /// Structural check: equal lengths, >= 1 point, strictly increasing finite breakpoints, finite values.
    pub fn check(&self) -> Result<(), String> {
        match self {
            TimeValue::Constant(v) => {
                if v.is_finite() {
                    Ok(())
                } else {
                    Err("non-finite value".into())
                }
            }
            TimeValue::Zoh { t, v } => {
                if t.is_empty() || t.len() != v.len() {
                    return Err("ZOH series needs >= 1 breakpoint and equal breakpoints_s / values lengths".into());
                }
                if t.iter().chain(v.iter()).any(|x| !x.is_finite()) {
                    return Err("non-finite ZOH entry".into());
                }
                if t.windows(2).any(|w| w[1] <= w[0]) {
                    return Err("ZOH breakpoints_s must be strictly increasing".into());
                }
                Ok(())
            }
        }
    }

    pub fn is_constant(&self) -> bool {
        matches!(self, TimeValue::Constant(_))
    }

    pub fn breakpoints(&self) -> &[f64] {
        match self {
            TimeValue::Constant(_) => &[],
            TimeValue::Zoh { t, .. } => t,
        }
    }

    pub fn first_breakpoint(&self) -> Option<f64> {
        self.breakpoints().first().copied()
    }

    /// Every value (for sign / range checks).
    pub fn values(&self) -> Vec<f64> {
        match self {
            TimeValue::Constant(v) => vec![*v],
            TimeValue::Zoh { v, .. } => v.clone(),
        }
    }

    /// The held value at time `t` (the caller aligns step boundaries with breakpoints and passes an interval midpoint).
    pub fn at(&self, t: f64) -> f64 {
        match self {
            TimeValue::Constant(v) => *v,
            TimeValue::Zoh { t: bp, v } => {
                let mut k = 0;
                for (i, b) in bp.iter().enumerate() {
                    if *b <= t {
                        k = i;
                    } else {
                        break;
                    }
                }
                v[k]
            }
        }
    }
}
