//! Host-side arithmetic helpers that mirror the C library.
//!
//! The kernel works entirely in Montgomery form (`R = 2^64`), and the C
//! driver simply hands it the internal words of `ca_elem`.  The safe
//! `cryptanalysis` crate only exposes the *public* element form, so this
//! module reconstructs the Montgomery context (`ca_mont_init`) and converts.
//! It also ports `ca_rng` so that the multiplier table is built from the same
//! stream of random exponents as `src/gpu_rho.c`.

/// Montgomery context for an odd modulus, mirroring `ca_mont`.
#[derive(Debug, Clone, Copy)]
pub(crate) struct Mont {
    /// The odd modulus.
    pub p: u64,
    /// `-p^-1 mod 2^64`.
    pub pinv: u64,
    /// `R mod p`, i.e. the Montgomery form of 1.
    pub r1: u64,
    /// `R^2 mod p`.
    pub r2: u64,
}

impl Mont {
    /// Mirrors `ca_mont_init`; `None` for an even or too-small modulus.
    pub fn new(p: u64) -> Option<Mont> {
        if p & 1 == 0 || p < 3 {
            return None;
        }
        // Newton iteration for p^-1 mod 2^64 (p odd => 3 bits correct).
        let mut inv = p;
        for _ in 0..6 {
            inv = inv.wrapping_mul(2u64.wrapping_sub(p.wrapping_mul(inv)));
        }
        let r1 = ((1u128 << 64) % p as u128) as u64;
        let r2 = ((r1 as u128 * r1 as u128) % p as u128) as u64;
        Some(Mont {
            p,
            pinv: inv.wrapping_neg(),
            r1,
            r2,
        })
    }

    fn redc(&self, t: u128) -> u64 {
        let u = (t as u64).wrapping_mul(self.pinv);
        let s = t.wrapping_add(u as u128 * self.p as u128);
        let mut r = (s >> 64) as u64;
        if s < t {
            // carry out of the 128-bit add: the true result is r + 2^64
            r = r.wrapping_sub(self.p);
        }
        if r >= self.p {
            r -= self.p;
        }
        r
    }

    /// `a * b * R^-1 mod p` (both operands in Montgomery form).
    pub fn mul(&self, a: u64, b: u64) -> u64 {
        self.redc(a as u128 * b as u128)
    }

    /// Convert a residue into Montgomery form.
    pub fn to(&self, a: u64) -> u64 {
        self.mul(a % self.p, self.r2)
    }

    /// Convert out of Montgomery form.
    #[cfg(test)]
    pub fn from(&self, a: u64) -> u64 {
        self.redc(a as u128)
    }
}

/// `xoshiro256**`, seeded exactly like `ca_rng_seed`.
#[derive(Debug, Clone)]
pub(crate) struct Rng {
    s: [u64; 4],
}

fn splitmix64(x: &mut u64) -> u64 {
    *x = x.wrapping_add(0x9E37_79B9_7F4A_7C15);
    let mut z = *x;
    z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
    z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
    z ^ (z >> 31)
}

impl Rng {
    /// Mirrors `ca_rng_seed`.
    pub fn new(seed: u64) -> Rng {
        let mut x = seed;
        let mut s = [0u64; 4];
        for slot in &mut s {
            *slot = splitmix64(&mut x);
        }
        if s == [0, 0, 0, 0] {
            s[0] = 1;
        }
        Rng { s }
    }

    /// Mirrors `ca_rng_next`.
    pub fn next_u64(&mut self) -> u64 {
        let s = &mut self.s;
        let result = s[1].wrapping_mul(5).rotate_left(7).wrapping_mul(9);
        let t = s[1] << 17;
        s[2] ^= s[0];
        s[3] ^= s[1];
        s[1] ^= s[2];
        s[0] ^= s[3];
        s[2] ^= t;
        s[3] = s[3].rotate_left(45);
        result
    }

    /// Uniform in `[0, n)`; mirrors `ca_rng_below` (Lemire's method).
    pub fn below(&mut self, n: u64) -> u64 {
        if n == 0 {
            return self.next_u64();
        }
        let mut m = self.next_u64() as u128 * n as u128;
        let mut l = m as u64;
        if l < n {
            let t = n.wrapping_neg() % n;
            while l < t {
                m = self.next_u64() as u128 * n as u128;
                l = m as u64;
            }
        }
        (m >> 64) as u64
    }
}

/// `ca_seed_or_random`: a non-zero seed is used as is, 0 asks the OS.
pub(crate) fn seed_or_random(seed: u64) -> u64 {
    if seed != 0 {
        return seed;
    }
    let mut s = read_urandom_word().unwrap_or(0);
    if s == 0 {
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default();
        s = now.subsec_nanos() as u64 ^ (now.as_secs() << 32) ^ (&s as *const u64 as usize as u64);
    }
    if s == 0 {
        s = 0x1234_5678_8765_4321;
    }
    s
}

fn read_urandom_word() -> Option<u64> {
    use std::io::Read;
    let mut buf = [0u8; 8];
    let mut f = std::fs::File::open("/dev/urandom").ok()?;
    f.read_exact(&mut buf).ok()?;
    Some(u64::from_le_bytes(buf))
}

/// `a + b mod m` for `a, b < m`.
pub(crate) fn addmod(a: u64, b: u64, m: u64) -> u64 {
    let (s, carry) = a.overflowing_add(b);
    if carry || s >= m {
        s.wrapping_sub(m)
    } else {
        s
    }
}

/// `a - b mod m` for `a, b < m`.
pub(crate) fn submod(a: u64, b: u64, m: u64) -> u64 {
    if a >= b {
        a - b
    } else {
        a + (m - b)
    }
}

/// `a * b mod m`.
pub(crate) fn mulmod(a: u64, b: u64, m: u64) -> u64 {
    ((a as u128 * b as u128) % m as u128) as u64
}

/// Euclidean gcd; mirrors `ca_gcd`.
pub(crate) fn gcd(mut a: u64, mut b: u64) -> u64 {
    while b != 0 {
        let t = a % b;
        a = b;
        b = t;
    }
    a
}

/// `floor(sqrt(n))`; mirrors `ca_isqrt` exactly (its fix-up loops make the
/// floating-point start irrelevant).
pub(crate) fn isqrt(n: u64) -> u64 {
    if n == 0 {
        return 0;
    }
    let mut x = (n as f64).sqrt() as u64;
    while (x as u128) * (x as u128) > n as u128 {
        x -= 1;
    }
    while ((x + 1) as u128) * ((x + 1) as u128) <= n as u128 {
        x += 1;
    }
    x
}

/// `ilog2u` from `src/gpu_rho.c`: `-1` for 0, else `floor(log2(v))`.
pub(crate) fn ilog2u(v: u64) -> i32 {
    if v == 0 {
        -1
    } else {
        63 - v.leading_zeros() as i32
    }
}

/// Group operations charged by `ca_group_mul` for the scalar `k`
/// (right-to-left double-and-add: one add per set bit, one doubling per
/// shift that leaves a non-zero remainder).
pub(crate) fn mul_ops(k: u64) -> u64 {
    if k == 0 {
        0
    } else {
        k.count_ones() as u64 + 64 - k.leading_zeros() as u64 - 1
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The moduli `tests/test_gpu.c::test_device_arith` uses, checked the same
    /// way: Montgomery multiplication against the 128-bit definition.
    #[test]
    fn montgomery_matches_reference() {
        let mods = [
            1_000_003u64,
            4_294_967_311,
            1_099_511_627_791,
            9_223_372_036_854_775_837,
            18_446_744_073_709_551_557,
        ];
        for m in mods {
            let mont = Mont::new(m).expect("odd modulus");
            assert_eq!(mont.from(mont.r1), 1);
            let mut rng = Rng::new(4);
            for _ in 0..2000 {
                let a = rng.below(m);
                let b = rng.below(m);
                // Montgomery multiplication of the *forms* of a and b must be
                // the form of a*b mod m.
                let want = mont.to(mulmod(a, b, m));
                assert_eq!(mont.mul(mont.to(a), mont.to(b)), want, "m={m} a={a} b={b}");
                assert_eq!(mont.from(mont.to(a)), a);
                assert_eq!(
                    addmod(a, b, m),
                    ((a as u128 + b as u128) % m as u128) as u64
                );
                assert_eq!(
                    submod(a, b, m),
                    ((a as u128 + m as u128 - b as u128) % m as u128) as u64
                );
            }
        }
    }

    #[test]
    fn rng_is_deterministic_and_in_range() {
        let mut a = Rng::new(31);
        let mut b = Rng::new(31);
        for _ in 0..100 {
            let x = a.below(1_000_000_289);
            assert_eq!(x, b.below(1_000_000_289));
            assert!(x < 1_000_000_289);
        }
        assert_ne!(Rng::new(1).next_u64(), Rng::new(2).next_u64());
    }

    #[test]
    fn integer_helpers() {
        assert_eq!(isqrt(0), 0);
        assert_eq!(isqrt(1_000_000_289), 31_622);
        assert_eq!(isqrt(u64::MAX), 4_294_967_295);
        assert_eq!(ilog2u(0), -1);
        assert_eq!(ilog2u(1), 0);
        assert_eq!(ilog2u(1_000_000_289), 29);
        assert_eq!(gcd(12, 18), 6);
        assert_eq!(gcd(0, 7), 7);
        // 0b1011 -> 3 adds + 3 doublings
        assert_eq!(mul_ops(0b1011), 6);
        assert_eq!(mul_ops(1), 1);
        assert_eq!(mul_ops(0), 0);
    }

    #[test]
    fn seed_or_random_is_non_zero() {
        assert_eq!(seed_or_random(7), 7);
        assert_ne!(seed_or_random(0), 0);
    }
}
