//! Dense LU factorization with partial pivoting (NUM-07). Row-major n x n; deterministic pivot choice (first maximum).

#[derive(Debug, Clone)]
pub struct Lu {
    n: usize,
    a: Vec<f64>,
    piv: Vec<usize>,
}

impl Lu {
    /// Factor `a` (row-major, n x n). Returns `None` for a singular or non-finite matrix.
    pub fn factor(mut a: Vec<f64>, n: usize) -> Option<Lu> {
        debug_assert_eq!(a.len(), n * n);
        if a.iter().any(|x| !x.is_finite()) {
            return None;
        }
        let mut piv: Vec<usize> = (0..n).collect();
        for k in 0..n {
            let mut p = k;
            let mut best = a[k * n + k].abs();
            for i in k + 1..n {
                let v = a[i * n + k].abs();
                if v > best {
                    best = v;
                    p = i;
                }
            }
            if best == 0.0 {
                return None;
            }
            if p != k {
                for j in 0..n {
                    a.swap(k * n + j, p * n + j);
                }
                piv.swap(k, p);
            }
            let d = a[k * n + k];
            for i in k + 1..n {
                let f = a[i * n + k] / d;
                a[i * n + k] = f;
                if f != 0.0 {
                    for j in k + 1..n {
                        a[i * n + j] -= f * a[k * n + j];
                    }
                }
            }
        }
        Some(Lu { n, a, piv })
    }

    /// Solve A x = b.
    #[allow(clippy::needless_range_loop)]
    pub fn solve(&self, b: &[f64]) -> Vec<f64> {
        let n = self.n;
        let mut x: Vec<f64> = self.piv.iter().map(|&p| b[p]).collect();
        for i in 0..n {
            let mut s = x[i];
            for j in 0..i {
                s -= self.a[i * n + j] * x[j];
            }
            x[i] = s;
        }
        for i in (0..n).rev() {
            let mut s = x[i];
            for j in i + 1..n {
                s -= self.a[i * n + j] * x[j];
            }
            x[i] = s / self.a[i * n + i];
        }
        x
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn solves_a_pivoting_system() {
        let a = vec![0.0, 2.0, 1.0, 1.0, 1.0, 1.0, 2.0, 1.0, 3.0];
        let lu = Lu::factor(a.clone(), 3).unwrap();
        let b = [3.0, 6.0, 13.0];
        let x = lu.solve(&b);
        for i in 0..3 {
            let r: f64 = (0..3).map(|j| a[i * 3 + j] * x[j]).sum();
            assert!((r - b[i]).abs() < 1e-12);
        }
        assert!(Lu::factor(vec![1.0, 2.0, 2.0, 4.0], 2).is_none());
    }
}
