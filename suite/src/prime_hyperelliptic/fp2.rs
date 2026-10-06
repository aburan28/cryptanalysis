//! **`F_{p²}` arithmetic** — quadratic-extension support for
//! point-counting `#C(F_{p²})` of a hyperelliptic curve `C/F_p`.
//!
//! Representation: `F_{p²} = F_p[t]/(t² − δ)` where `δ` is a fixed
//! non-residue in `F_p`.  An element is `a + b·t` with `a, b ∈
//! F_p`, stored as a pair of `u64` (sufficient for `p ≤ 2^{31}` —
//! we don't need cryptographic sizes here, only enough to sweep
//! small primes and run sampling at moderate sizes).
//!
//! Operations: addition, multiplication, squaring, exponentiation,
//! inversion (via Frobenius `(a + bt)^{-1} = (a − bt)/(a² − δ·b²)`),
//! and quadratic-residue test via Euler's criterion.

/// `F_{p²}` element `a + b·t`, where `t² = δ` in `F_p`.
#[derive(Copy, Clone, Debug, PartialEq, Eq)]
pub struct Fp2 {
    pub a: u64,
    pub b: u64,
}

/// `F_{p²}` context carrying the prime `p` and the non-residue `δ`.
#[derive(Copy, Clone, Debug)]
pub struct Fp2Ctx {
    pub p: u64,
    pub delta: u64,
}

impl Fp2Ctx {
    /// Build the context: find any quadratic non-residue `δ ∈ F_p^*`
    /// and store it.  Panics for `p = 2` (binary field).
    pub fn new(p: u64) -> Self {
        assert!(p >= 3 && p % 2 == 1, "Fp2Ctx requires odd prime p");
        let exp = (p - 1) / 2;
        let mut delta = 2u64;
        loop {
            if powmod(delta, exp, p) == p - 1 {
                // chi(delta) = -1
                return Fp2Ctx { p, delta };
            }
            delta += 1;
        }
    }

    pub fn zero(&self) -> Fp2 {
        Fp2 { a: 0, b: 0 }
    }

    pub fn one(&self) -> Fp2 {
        Fp2 { a: 1, b: 0 }
    }

    pub fn from_fp(&self, x: u64) -> Fp2 {
        Fp2 {
            a: x % self.p,
            b: 0,
        }
    }

    pub fn is_zero(&self, x: Fp2) -> bool {
        x.a == 0 && x.b == 0
    }

    pub fn add(&self, x: Fp2, y: Fp2) -> Fp2 {
        Fp2 {
            a: (x.a + y.a) % self.p,
            b: (x.b + y.b) % self.p,
        }
    }

    pub fn sub(&self, x: Fp2, y: Fp2) -> Fp2 {
        Fp2 {
            a: (x.a + self.p - y.a) % self.p,
            b: (x.b + self.p - y.b) % self.p,
        }
    }

    pub fn neg(&self, x: Fp2) -> Fp2 {
        Fp2 {
            a: (self.p - x.a) % self.p,
            b: (self.p - x.b) % self.p,
        }
    }

    pub fn mul(&self, x: Fp2, y: Fp2) -> Fp2 {
        // (a + bt)(c + dt) = (ac + bd·δ) + (ad + bc)·t
        let p = self.p;
        let ac = mulmod(x.a, y.a, p);
        let bd = mulmod(x.b, y.b, p);
        let bd_delta = mulmod(bd, self.delta, p);
        let ad = mulmod(x.a, y.b, p);
        let bc = mulmod(x.b, y.a, p);
        Fp2 {
            a: (ac + bd_delta) % p,
            b: (ad + bc) % p,
        }
    }

    pub fn square(&self, x: Fp2) -> Fp2 {
        self.mul(x, x)
    }

    pub fn pow(&self, mut x: Fp2, mut e: u64) -> Fp2 {
        let mut acc = self.one();
        while e > 0 {
            if e & 1 == 1 {
                acc = self.mul(acc, x);
            }
            x = self.square(x);
            e >>= 1;
        }
        acc
    }

    pub fn inv(&self, x: Fp2) -> Option<Fp2> {
        if self.is_zero(x) {
            return None;
        }
        // (a + bt)^{-1} = (a − bt) / (a² − δ·b²)
        let p = self.p;
        let a_sq = mulmod(x.a, x.a, p);
        let b_sq = mulmod(x.b, x.b, p);
        let b_sq_delta = mulmod(b_sq, self.delta, p);
        let norm = (a_sq + p - b_sq_delta) % p;
        let norm_inv = powmod(norm, p - 2, p);
        let conj_a = x.a;
        let conj_b = (p - x.b) % p;
        Fp2 {
            a: mulmod(conj_a, norm_inv, p),
            b: mulmod(conj_b, norm_inv, p),
        }
        .into()
    }

    /// Is `x` a non-zero quadratic residue in `F_{p²}`?  Equivalent
    /// to `Norm_{F_{p²}/F_p}(x) = a² − δ·b²` being a square in `F_p`,
    /// AND … no actually the precise criterion: `x` is a QR in
    /// `F_{p²}` iff `x^{(p²-1)/2} = 1`.  For `p odd` and `x ∈ F_p`
    /// non-zero, `x` is *always* a square in `F_{p²}` (every element
    /// of `F_p^*` lifts to a square since `F_p^*` ⊂ `F_{p²}^*` and
    /// the index is `(p²-1)/(p-1) = p+1`, even).  More generally for
    /// `x = a + bt`, compute `x^{(p²-1)/2}` and compare to `1`.
    pub fn is_qr(&self, x: Fp2) -> Option<bool> {
        if self.is_zero(x) {
            return None; // distinguishes zero
        }
        // Compute (p² − 1) / 2 via 64-bit (assumes p < 2^{32}).
        let p_sq_minus_1 = (self.p as u128) * (self.p as u128) - 1;
        let exp = p_sq_minus_1 / 2;
        // Power via repeated squaring on Fp2 with 128-bit exponent.
        let res = self.pow_u128(x, exp);
        Some(res == self.one())
    }

    fn pow_u128(&self, mut x: Fp2, mut e: u128) -> Fp2 {
        let mut acc = self.one();
        while e > 0 {
            if e & 1 == 1 {
                acc = self.mul(acc, x);
            }
            x = self.square(x);
            e >>= 1;
        }
        acc
    }
}

fn mulmod(a: u64, b: u64, p: u64) -> u64 {
    ((a as u128 * b as u128) % p as u128) as u64
}

fn powmod(base: u64, exp: u64, p: u64) -> u64 {
    let mut acc = 1u64;
    let mut b = base % p;
    let mut e = exp;
    while e > 0 {
        if e & 1 == 1 {
            acc = mulmod(acc, b, p);
        }
        b = mulmod(b, b, p);
        e >>= 1;
    }
    acc
}

/// Enumerate every `(a, b) ∈ F_p × F_p` and yield the corresponding
/// `Fp2` element.  There are `p²` of them.
pub fn enumerate_fp2(ctx: &Fp2Ctx) -> impl Iterator<Item = Fp2> + '_ {
    let p = ctx.p;
    (0..p).flat_map(move |a| (0..p).map(move |b| Fp2 { a, b }))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fp2_basic_arithmetic() {
        let ctx = Fp2Ctx::new(7);
        let one = ctx.one();
        let zero = ctx.zero();
        // x² = δ for some t ⇒ t·t = (a=0, b=1)² = δ + 0t in F_p
        let t = Fp2 { a: 0, b: 1 };
        let t_sq = ctx.square(t);
        assert_eq!(t_sq, Fp2 { a: ctx.delta, b: 0 });
        // 1 + 0 = 1
        assert_eq!(ctx.add(one, zero), one);
        // x · 0 = 0
        let any = Fp2 { a: 3, b: 5 };
        assert_eq!(ctx.mul(any, zero), zero);
    }

    #[test]
    fn fp2_inv_roundtrip() {
        let ctx = Fp2Ctx::new(11);
        for a in 0..11u64 {
            for b in 0..11u64 {
                let x = Fp2 { a, b };
                if ctx.is_zero(x) {
                    assert!(ctx.inv(x).is_none());
                    continue;
                }
                let inv = ctx.inv(x).unwrap();
                let prod = ctx.mul(x, inv);
                assert_eq!(prod, ctx.one(), "x·x⁻¹ ≠ 1 for x = {:?}", x);
            }
        }
    }

    #[test]
    fn fp2_qr_test_consistency() {
        // Every element of F_p^* embeds in F_{p²} and is a QR there
        // (since [F_{p²}^* : F_p^*] = p+1 is even).
        let ctx = Fp2Ctx::new(13);
        for a in 1..13u64 {
            let x = Fp2 { a, b: 0 };
            assert_eq!(ctx.is_qr(x), Some(true), "F_p element should be QR");
        }
    }

    #[test]
    fn fp2_qr_half_split() {
        // Among non-zero F_{p²} elements, exactly half are QRs.
        let ctx = Fp2Ctx::new(11);
        let mut qr = 0u32;
        let mut nqr = 0u32;
        for x in enumerate_fp2(&ctx) {
            match ctx.is_qr(x) {
                None => {}
                Some(true) => qr += 1,
                Some(false) => nqr += 1,
            }
        }
        // |F_{p²}^*| = p² - 1 = 120.  Half = 60.
        assert_eq!(qr, 60);
        assert_eq!(nqr, 60);
    }
}
