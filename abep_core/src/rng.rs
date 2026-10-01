//! Deterministic random stream for abep_core.
//!
//! xoshiro256++ (D. Blackman and S. Vigna, "Scrambled linear pseudorandom number generators", ACM TOMS 47(4), 2021;
//! reference code at https://prng.di.unimi.it/xoshiro256plusplus.c), seeded through SplitMix64 as the authors
//! recommend. Uniform doubles use the top 53 bits; standard normal deviates use the Marsaglia polar method.
//! Implemented here (no external RNG crate) so the stream for a given seed never changes with crate versions.
//! The stream differs from numpy's PCG64 by construction: parity with the Python reference is statistical
//! (docs/performance/abep_core/parity_prereg_v1.json).

pub const RNG_ALGORITHM: &str = "xoshiro256++ seeded by SplitMix64; uniform = top 53 bits * 2^-53; normal = Marsaglia polar";

#[inline]
fn splitmix64(state: &mut u64) -> u64 {
    *state = state.wrapping_add(0x9E37_79B9_7F4A_7C15);
    let mut z = *state;
    z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
    z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
    z ^ (z >> 31)
}

pub struct Rng {
    s: [u64; 4],
    cached_normal: Option<f64>,
}

impl Rng {
    pub fn new(seed: u64) -> Rng {
        let mut sm = seed;
        let s = [splitmix64(&mut sm), splitmix64(&mut sm), splitmix64(&mut sm), splitmix64(&mut sm)];
        Rng { s, cached_normal: None }
    }

    #[inline]
    pub fn next_u64(&mut self) -> u64 {
        let result = (self.s[0].wrapping_add(self.s[3])).rotate_left(23).wrapping_add(self.s[0]);
        let t = self.s[1] << 17;
        self.s[2] ^= self.s[0];
        self.s[3] ^= self.s[1];
        self.s[1] ^= self.s[2];
        self.s[0] ^= self.s[3];
        self.s[2] ^= t;
        self.s[3] = self.s[3].rotate_left(45);
        result
    }

    /// Uniform on [0, 1).
    #[inline]
    pub fn uniform(&mut self) -> f64 {
        (self.next_u64() >> 11) as f64 * (1.0 / 9_007_199_254_740_992.0)
    }

    /// Uniform on [a, b) (same affine form as numpy Generator.uniform: a + (b - a) U).
    #[inline]
    pub fn uniform_range(&mut self, a: f64, b: f64) -> f64 {
        a + (b - a) * self.uniform()
    }

    /// Standard normal deviate (Marsaglia polar method, pairs cached).
    #[inline]
    pub fn standard_normal(&mut self) -> f64 {
        if let Some(z) = self.cached_normal.take() {
            return z;
        }
        loop {
            let u = 2.0 * self.uniform() - 1.0;
            let v = 2.0 * self.uniform() - 1.0;
            let s = u * u + v * v;
            if s > 0.0 && s < 1.0 {
                let f = (-2.0 * s.ln() / s).sqrt();
                self.cached_normal = Some(v * f);
                return u * f;
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn same_seed_same_stream() {
        let mut a = Rng::new(42);
        let mut b = Rng::new(42);
        for _ in 0..1000 {
            assert_eq!(a.next_u64(), b.next_u64());
        }
        let mut c = Rng::new(43);
        let mut a = Rng::new(42);
        let differs = (0..16).any(|_| a.next_u64() != c.next_u64());
        assert!(differs);
    }

    #[test]
    fn uniform_in_unit_interval_and_normal_moments() {
        let mut r = Rng::new(7);
        let n = 200_000;
        let (mut s1, mut s2) = (0.0, 0.0);
        for _ in 0..n {
            let u = r.uniform();
            assert!((0.0..1.0).contains(&u));
            let z = r.standard_normal();
            s1 += z;
            s2 += z * z;
        }
        let mean = s1 / n as f64;
        let var = s2 / n as f64 - mean * mean;
        // 5-sigma bounds for the sample mean (sd 1/sqrt(n)) and sample variance (sd sqrt(2/n))
        assert!(mean.abs() < 5.0 / (n as f64).sqrt());
        assert!((var - 1.0).abs() < 5.0 * (2.0 / n as f64).sqrt());
    }
}
