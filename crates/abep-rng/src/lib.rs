//! Registered numpy random-stream semantics for the design / UQ sampling stream (A9.29 sec. 7, RM-OQ-03:
//! EXACT_STREAM; contract PARITY-C-ABEP_SIM_DESIGN_ROBUST_OPTIMIZER_PY-V1, `rng_stream_roles`).
//!
//! `numpy.random.default_rng(seed)` with a non-negative integer seed is reproduced bit for bit:
//! * [`SeedSequence`]: entropy -> uint32 words (`_coerce_to_uint32_array`), pool of 4 words mixed by `hashmix` / `mix`,
//!   `generate_state(4, uint64)` (numpy `bit_generator.pyx`);
//! * [`Pcg64`]: 128-bit LCG with the default multiplier, XSL-RR 64-bit output, `pcg64_set_seed` initialisation and
//!   `next_double = (next_uint64 >> 11) * 2^-53` (numpy `src/pcg64/pcg64.{h,c}`);
//! * [`Generator::standard_normal`]: numpy's 256-layer ziggurat (`random_standard_normal`, `distributions.c`, tables in
//!   [`ziggurat`]), filling arrays in C order like `Generator.standard_normal(size)`.
//!
//! The source of every algorithm is numpy v2.4.4 (the registered reference environment). The TPMC particle-tracing
//! kernel keeps its own admitted STATISTICAL contract and RNG (Kernel-1, xoshiro256++); it never draws from here.
//! [`stable_seed`] is the seed derivation from stable ids of `abep_sim/design/intake_synthesis.py::stable_seed`
//! (zlib CRC-32 of the '|'-joined parts plus a base, mod 2^31 - 1).

pub mod ziggurat;

use ziggurat::{FI_DOUBLE, KI_DOUBLE, WI_DOUBLE, ZIGGURAT_NOR_INV_R, ZIGGURAT_NOR_R};

const INIT_A: u32 = 0x43b0_d7e5;
const MULT_A: u32 = 0x931e_8875;
const INIT_B: u32 = 0x8b51_f9dd;
const MULT_B: u32 = 0x58f3_8ded;
const MIX_MULT_L: u32 = 0xca01_f9dd;
const MIX_MULT_R: u32 = 0x4973_f715;
const XSHIFT: u32 = 16;
/// numpy `DEFAULT_POOL_SIZE`.
pub const POOL_SIZE: usize = 4;

/// PCG default 128-bit multiplier (`PCG_DEFAULT_MULTIPLIER_HIGH << 64 | PCG_DEFAULT_MULTIPLIER_LOW`).
const PCG_MULT: u128 = (2_549_297_995_355_413_924u128 << 64) | 4_865_540_595_714_422_341u128;

fn hashmix(value: u32, hash_const: &mut u32) -> u32 {
    let mut v = value ^ *hash_const;
    *hash_const = hash_const.wrapping_mul(MULT_A);
    v = v.wrapping_mul(*hash_const);
    v ^ (v >> XSHIFT)
}

fn mix(x: u32, y: u32) -> u32 {
    let r = MIX_MULT_L.wrapping_mul(x).wrapping_sub(MIX_MULT_R.wrapping_mul(y));
    r ^ (r >> XSHIFT)
}

/// `_int_to_uint32_array(n)`: little-endian 32-bit words of a non-negative integer (0 -> [0]).
pub fn int_to_u32_words(n: u128) -> Vec<u32> {
    if n == 0 {
        return vec![0];
    }
    let mut out = vec![];
    let mut m = n;
    while m > 0 {
        out.push((m & 0xffff_ffff) as u32);
        m >>= 32;
    }
    out
}

/// `_int_to_uint32_array` of a non-negative decimal integer of any size (little-endian 32-bit words); None for a
/// string that is not a plain decimal integer.
pub fn decimal_to_u32_words(text: &str) -> Option<Vec<u32>> {
    if text.is_empty() || !text.bytes().all(|b| b.is_ascii_digit()) {
        return None;
    }
    let mut digits: Vec<u32> = text.bytes().map(|b| u32::from(b - b'0')).collect();
    let mut out = vec![];
    loop {
        // divide the decimal digit string by 2^32, collecting the remainder
        let mut rem: u64 = 0;
        let mut q = Vec::with_capacity(digits.len());
        for d in &digits {
            let cur = rem * 10 + u64::from(*d);
            let qd = cur >> 32;
            rem = cur & 0xffff_ffff;
            if !(q.is_empty() && qd == 0) {
                q.push(qd as u32);
            }
        }
        out.push(rem as u32);
        if q.is_empty() {
            break;
        }
        digits = q;
    }
    while out.len() > 1 && *out.last().expect("non-empty") == 0 {
        out.pop();
    }
    Some(out)
}

/// numpy `SeedSequence` without spawn key (the only form `default_rng(int)` builds).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SeedSequence {
    pool: [u32; POOL_SIZE],
}

impl SeedSequence {
    /// `SeedSequence(entropy)` for a non-negative integer entropy.
    pub fn new(entropy: u128) -> Self {
        Self::from_words(&int_to_u32_words(entropy))
    }

    /// `SeedSequence` over an already coerced uint32 entropy array (`mix_entropy`).
    pub fn from_words(entropy: &[u32]) -> Self {
        let mut pool = [0u32; POOL_SIZE];
        let mut hc = INIT_A;
        for (i, p) in pool.iter_mut().enumerate() {
            *p = hashmix(entropy.get(i).copied().unwrap_or(0), &mut hc);
        }
        for i_src in 0..POOL_SIZE {
            for i_dst in 0..POOL_SIZE {
                if i_src != i_dst {
                    let h = hashmix(pool[i_src], &mut hc);
                    pool[i_dst] = mix(pool[i_dst], h);
                }
            }
        }
        for &e in entropy.iter().skip(POOL_SIZE) {
            for p in pool.iter_mut() {
                let h = hashmix(e, &mut hc);
                *p = mix(*p, h);
            }
        }
        SeedSequence { pool }
    }

    pub fn pool(&self) -> [u32; POOL_SIZE] {
        self.pool
    }

    /// `generate_state(n_words, uint32)`.
    pub fn generate_state_u32(&self, n_words: usize) -> Vec<u32> {
        let mut hc = INIT_B;
        (0..n_words)
            .map(|i| {
                let mut v = self.pool[i % POOL_SIZE] ^ hc;
                hc = hc.wrapping_mul(MULT_B);
                v = v.wrapping_mul(hc);
                v ^ (v >> XSHIFT)
            })
            .collect()
    }

    /// `generate_state(n_words, uint64)`: twice as many uint32 words, read as little-endian uint64.
    pub fn generate_state_u64(&self, n_words: usize) -> Vec<u64> {
        let w = self.generate_state_u32(2 * n_words);
        w.chunks(2).map(|c| u64::from(c[0]) | (u64::from(c[1]) << 32)).collect()
    }
}

/// numpy `PCG64` (PCG XSL-RR 128/64).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Pcg64 {
    state: u128,
    inc: u128,
}

impl Pcg64 {
    /// `pcg64_set_seed(seed[0..2], inc[0..2])` = `pcg_setseq_128_srandom_r(seed, inc)`.
    pub fn from_words(words: [u64; 4]) -> Self {
        let initstate = (u128::from(words[0]) << 64) | u128::from(words[1]);
        let initseq = (u128::from(words[2]) << 64) | u128::from(words[3]);
        let mut g = Pcg64 { state: 0, inc: (initseq << 1) | 1 };
        g.step();
        g.state = g.state.wrapping_add(initstate);
        g.step();
        g
    }

    /// `PCG64(SeedSequence(entropy))`.
    pub fn from_seed_sequence(ss: &SeedSequence) -> Self {
        let w = ss.generate_state_u64(4);
        Self::from_words([w[0], w[1], w[2], w[3]])
    }

    /// The numpy `bit_generator.state` view: (state, inc) as 128-bit integers.
    pub fn state(&self) -> (u128, u128) {
        (self.state, self.inc)
    }

    #[inline]
    fn step(&mut self) {
        self.state = self.state.wrapping_mul(PCG_MULT).wrapping_add(self.inc);
    }

    /// `pcg64_next64`: step, then XSL-RR output.
    #[inline]
    pub fn next_u64(&mut self) -> u64 {
        self.step();
        let hi = (self.state >> 64) as u64;
        let lo = self.state as u64;
        (hi ^ lo).rotate_right((self.state >> 122) as u32)
    }

    /// `pcg64_next_double`: (next_uint64 >> 11) * (1.0 / 9007199254740992.0).
    #[inline]
    pub fn next_double(&mut self) -> f64 {
        (self.next_u64() >> 11) as f64 * (1.0 / 9_007_199_254_740_992.0)
    }
}

/// numpy `Generator` over `PCG64` (the subset the active design / UQ stream uses).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Generator {
    bit: Pcg64,
}

impl Generator {
    /// `numpy.random.default_rng(seed)` for a non-negative integer seed.
    pub fn default_rng(seed: u128) -> Self {
        Generator { bit: Pcg64::from_seed_sequence(&SeedSequence::new(seed)) }
    }

    /// `numpy.random.default_rng(seed)` for a seed already coerced to its uint32 entropy words.
    pub fn from_entropy_words(words: &[u32]) -> Self {
        Generator { bit: Pcg64::from_seed_sequence(&SeedSequence::from_words(words)) }
    }

    pub fn bit_generator(&self) -> &Pcg64 {
        &self.bit
    }

    /// `Generator.random()` (one double in [0, 1)).
    pub fn random(&mut self) -> f64 {
        self.bit.next_double()
    }

    /// `random_standard_normal` (numpy 256-layer ziggurat).
    pub fn standard_normal(&mut self) -> f64 {
        loop {
            let mut r = self.bit.next_u64();
            let idx = (r & 0xff) as usize;
            r >>= 8;
            let sign = r & 0x1;
            let rabs = (r >> 1) & 0x000f_ffff_ffff_ffff;
            let mut x = rabs as f64 * WI_DOUBLE[idx];
            if sign & 0x1 == 1 {
                x = -x;
            }
            if rabs < KI_DOUBLE[idx] {
                return x;
            }
            if idx == 0 {
                loop {
                    let xx = -ZIGGURAT_NOR_INV_R * (-self.bit.next_double()).ln_1p();
                    let yy = -(-self.bit.next_double()).ln_1p();
                    if yy + yy > xx * xx {
                        return if (rabs >> 8) & 0x1 == 1 { -(ZIGGURAT_NOR_R + xx) } else { ZIGGURAT_NOR_R + xx };
                    }
                }
            } else if (FI_DOUBLE[idx - 1] - FI_DOUBLE[idx]) * self.bit.next_double() + FI_DOUBLE[idx]
                < (-0.5 * x * x).exp()
            {
                return x;
            }
        }
    }

    /// `Generator.standard_normal(size)`: `n` draws in C order (`random_standard_normal_fill`).
    pub fn standard_normal_fill(&mut self, n: usize) -> Vec<f64> {
        (0..n).map(|_| self.standard_normal()).collect()
    }
}

/// zlib CRC-32 (IEEE 802.3, reflected, init / xorout 0xFFFFFFFF), as `zlib.crc32(data)`.
pub fn crc32(data: &[u8]) -> u32 {
    let mut crc = 0xffff_ffffu32;
    for &b in data {
        crc ^= u32::from(b);
        for _ in 0..8 {
            let mask = (crc & 1).wrapping_neg();
            crc = (crc >> 1) ^ (0xedb8_8320 & mask);
        }
    }
    !crc
}

/// `intake_synthesis.stable_seed(*parts, base=base)` = (crc32('|'.join(map(str, parts))) + base) % (2^31 - 1). The
/// parts are passed already rendered as Python `str(p)`.
pub fn stable_seed(parts: &[&str], base: i64) -> i64 {
    let joined = parts.join("|");
    (i64::from(crc32(joined.as_bytes())) + base).rem_euclid((1i64 << 31) - 1)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn crc32_check_value() {
        // the CRC-32 check value of the ASCII string "123456789"
        assert_eq!(crc32(b"123456789"), 0xcbf4_3926);
        assert_eq!(crc32(b""), 0);
    }

    #[test]
    fn decimal_words() {
        assert_eq!(decimal_to_u32_words("0"), Some(vec![0]));
        assert_eq!(decimal_to_u32_words("12345"), Some(vec![12345]));
        assert_eq!(decimal_to_u32_words("72455405295"), Some(vec![0xdead_beef, 0x10]));
        assert_eq!(decimal_to_u32_words(&u128::MAX.to_string()), Some(int_to_u32_words(u128::MAX)));
        assert_eq!(decimal_to_u32_words("1x"), None);
    }

    #[test]
    fn int_words() {
        assert_eq!(int_to_u32_words(0), vec![0]);
        assert_eq!(int_to_u32_words(12345), vec![12345]);
        assert_eq!(int_to_u32_words(0x10_dead_beef), vec![0xdead_beef, 0x10]);
    }

    #[test]
    fn deterministic_and_seed_sensitive() {
        let mut a = Generator::default_rng(20261001);
        let mut b = Generator::default_rng(20261001);
        let mut c = Generator::default_rng(20261002);
        let va = a.standard_normal_fill(1000);
        assert_eq!(va, b.standard_normal_fill(1000));
        assert_ne!(va, c.standard_normal_fill(1000));
        let mean = va.iter().sum::<f64>() / 1000.0;
        assert!(mean.abs() < 0.2);
    }
}
