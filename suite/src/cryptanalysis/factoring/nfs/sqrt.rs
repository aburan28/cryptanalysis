//! The **algebraic square root** of the NFS, by exact product and
//! `p`-adic Newton lifting.
//!
//! Let `F` be the monic polynomial with root `β = c·α` (see
//! [`IntPoly::monic_transform`]).  A dependency `S` gives
//! `∏_{S} (c·a − b·β) = γ²` for some `γ ∈ O_K`, and `F'(β)·O_K ⊆ ℤ[β]`,
//! so `δ = F'(β)·γ ∈ ℤ[β]` with
//!
//! ```text
//! δ² = Γ := F'(β)² · ∏_{(a,b) ∈ S} (c·a − b·β)      (mod F, exactly over ℤ)
//! ```
//!
//! 1. `Γ` is computed **exactly** — coefficients of tens of thousands of
//!    bits — by a product tree of linear polynomials reduced mod `F`.
//! 2. Pick a prime `p` with `F` irreducible mod `p` (an *inert* prime),
//!    so `ℤ[β]/p = F_{p^d}`.  Take a square root of `Γ mod p` in
//!    `F_{p^d}` (Tonelli–Shanks; if `Γ` is not a square there, the
//!    dependency is not a square in `K` and is rejected — the quadratic
//!    characters make this rare).
//! 3. Newton-lift the **inverse** square root `s ← s(3 − Γs²)/2` from
//!    `p` to `p^{2^k}`; then `δ ≡ Γ·s`.  Quadratic convergence doubles
//!    the precision each step.
//! 4. Once `p^{2^k}` exceeds twice the expected coefficient size, take
//!    symmetric representatives and **check `δ² = Γ` exactly** in
//!    `ℤ[x]/F`.  If the check fails, keep doubling (up to a cap).
//!
//! Only the sign of `δ` is undetermined, and either sign yields a valid
//! congruence of squares.  This is the approach of Couveignes (1993) and
//! of Buhler–Lenstra–Pomerance §9 without the CRT; Montgomery's and
//! Nguyen's lattice methods, which avoid the huge exact product, are what
//! production NFS uses.  The limitation: `F` must have an inert prime,
//! i.e. its Galois group must contain a `d`-cycle.  Polynomial selection
//! rejects polynomials without one.
//!
//! References: J.-M. Couveignes, *Computing a square root for the number
//! field sieve* (1993); P. L. Montgomery, *Square roots of products of
//! algebraic numbers* (1994); P. Q. Nguyen, *A Montgomery-like square
//! root for the number field sieve*, ANTS-III (1998).

use num_bigint::{BigInt, BigUint};
use num_integer::Integer;
use num_traits::Zero;

use super::super::arith::bigint_mod;
use super::poly::{fp, IntPoly};

/// Multiply `a · b` in `ℤ[x]/F` for monic `F` (`f` = its coefficients).
pub fn mul_mod_monic(a: &[BigInt], b: &[BigInt], f: &[BigInt]) -> Vec<BigInt> {
    let d = f.len() - 1;
    if a.is_empty() || b.is_empty() {
        return vec![BigInt::zero(); d];
    }
    let mut prod = vec![BigInt::zero(); a.len() + b.len() - 1];
    for (i, x) in a.iter().enumerate() {
        if x.is_zero() {
            continue;
        }
        for (j, y) in b.iter().enumerate() {
            prod[i + j] += x * y;
        }
    }
    reduce_monic(prod, f)
}

/// Reduce modulo monic `F`, returning exactly `d` coefficients.
fn reduce_monic(mut prod: Vec<BigInt>, f: &[BigInt]) -> Vec<BigInt> {
    let d = f.len() - 1;
    for i in (d..prod.len()).rev() {
        let c = std::mem::take(&mut prod[i]);
        if c.is_zero() {
            continue;
        }
        for j in 0..d {
            prod[i - d + j] -= &c * &f[j];
        }
    }
    prod.resize(d, BigInt::zero());
    prod
}

fn reduce_coeffs(v: &mut [BigInt], modulus: &BigInt) {
    for c in v.iter_mut() {
        *c = c.mod_floor(modulus);
    }
}

fn mul_mod_pk(a: &[BigInt], b: &[BigInt], f: &[BigInt], pk: &BigInt) -> Vec<BigInt> {
    let mut r = mul_mod_monic(a, b, f);
    reduce_coeffs(&mut r, pk);
    r
}

/// Statistics of one square-root attempt.
#[derive(Clone, Debug, Default, serde::Serialize)]
pub struct SqrtStats {
    /// Relations in the dependency.
    pub relations: usize,
    /// Bits of the largest coefficient of `Γ`.
    pub gamma_bits: u64,
    /// `p`-adic precision in bits at which `δ² = Γ` was verified.
    pub precision_bits: u64,
    /// Outcome: `"ok"`, `"not a square mod p"`, `"no convergence"`.
    pub outcome: String,
}

/// Square root in `F_{p^d} = F_p[x]/(F mod p)` by Tonelli–Shanks.
fn sqrt_fpd(g: &[u64], fmod: &[u64], p: u64, d: usize) -> Option<Vec<u64>> {
    let q = num_traits::pow(BigUint::from(p), d);
    let qm1 = &q - 1u32;
    let half = &qm1 >> 1;
    let one = vec![1u64];
    if fp::powmod(g, &half, fmod, p) != one {
        return None;
    }
    let s = qm1.trailing_zeros().unwrap_or(0);
    let t = &qm1 >> s;
    // A non-residue z = x + k.
    let mut z = Vec::new();
    for k in 1..10_000u64 {
        let cand = fp::trim(vec![k % p, 1]);
        if fp::powmod(&cand, &half, fmod, p) != one {
            z = cand;
            break;
        }
    }
    if z.is_empty() {
        return None;
    }
    let mut x = fp::powmod(g, &((&t + 1u32) >> 1), fmod, p);
    let mut bb = fp::powmod(g, &t, fmod, p);
    let mut gg = fp::powmod(&z, &t, fmod, p);
    let mut r = s;
    while bb != one {
        let mut m = 0u64;
        let mut tmp = bb.clone();
        while tmp != one {
            tmp = fp::rem(&fp::mul(&tmp, &tmp, p), fmod, p);
            m += 1;
            if m >= r {
                return None;
            }
        }
        let mut gs = gg.clone();
        for _ in 0..(r - m - 1) {
            gs = fp::rem(&fp::mul(&gs, &gs, p), fmod, p);
        }
        x = fp::rem(&fp::mul(&x, &gs, p), fmod, p);
        gg = fp::rem(&fp::mul(&gs, &gs, p), fmod, p);
        bb = fp::rem(&fp::mul(&bb, &gg, p), fmod, p);
        r = m;
    }
    Some(x)
}

/// `Γ = F'(β)² · ∏ (c·a − b·β)` in `ℤ[β]/F`, as `d` coefficients.
pub fn gamma(fmonic: &IntPoly, c: &BigInt, pairs: &[(i64, u64)]) -> Vec<BigInt> {
    let f = &fmonic.coeffs;
    let d = fmonic.degree();
    assert!(d >= 2, "the NFS needs degree ≥ 2");
    let mut layer: Vec<Vec<BigInt>> = pairs
        .iter()
        .map(|&(a, b)| {
            let mut v = vec![BigInt::zero(); d];
            v[0] = c * a;
            v[1] = -BigInt::from(b);
            v
        })
        .collect();
    let fprime: Vec<BigInt> = {
        let mut v = fmonic.derivative().coeffs;
        v.resize(d, BigInt::zero());
        v
    };
    layer.push(fprime.clone());
    layer.push(fprime);
    while layer.len() > 1 {
        let mut next = Vec::with_capacity(layer.len().div_ceil(2));
        let mut it = layer.into_iter();
        while let Some(x) = it.next() {
            match it.next() {
                Some(y) => next.push(mul_mod_monic(&x, &y, f)),
                None => next.push(x),
            }
        }
        layer = next;
    }
    layer.pop().unwrap_or_default()
}

/// Compute `δ` with `δ² = Γ` in `ℤ[x]/F` by lifting from the inert prime
/// `p`.  Returns `None` if `Γ` is not a square.
pub fn sqrt_gamma(
    fmonic: &IntPoly,
    g: &[BigInt],
    p: u64,
    stats: &mut SqrtStats,
) -> Option<Vec<BigInt>> {
    let f = &fmonic.coeffs;
    let d = fmonic.degree();
    let gamma_bits = g.iter().map(|c| c.bits()).max().unwrap_or(0);
    stats.gamma_bits = gamma_bits;
    let fmod = fp::trim(fmonic.mod_p(p));
    let pb = BigUint::from(p);
    let gp: Vec<u64> = fp::trim(
        g.iter()
            .map(|c| super::super::arith::bigint_mod_u64(c, p))
            .collect(),
    );
    let Some(r0) = sqrt_fpd(&gp, &fmod, p, d) else {
        stats.outcome = "not a square mod p".into();
        return None;
    };
    // s0 = r0⁻¹ = r0^{q−2}.
    let q = num_traits::pow(pb.clone(), d);
    let s0 = fp::powmod(&r0, &(&q - 2u32), &fmod, p);
    let mut s: Vec<BigInt> = (0..d)
        .map(|i| BigInt::from(s0.get(i).copied().unwrap_or(0)))
        .collect();
    let target = gamma_bits / 2 + 32 * d as u64 + 64;
    let cap = 4 * target + 1024;
    let p_int = BigInt::from(p);
    let mut pk = p_int.clone();
    let mut bits = (p as f64).log2() as u64;
    loop {
        // Double the precision: s ← s(3 − Γs²)/2 mod p^{2k}.
        pk = &pk * &pk;
        bits *= 2;
        let mut gk = g.to_vec();
        reduce_coeffs(&mut gk, &pk);
        let s2 = mul_mod_pk(&s, &s, f, &pk);
        let gs2 = mul_mod_pk(&gk, &s2, f, &pk);
        let mut t: Vec<BigInt> = gs2.iter().map(|x| -x).collect();
        t[0] += 3;
        reduce_coeffs(&mut t, &pk);
        let inv2 = (&pk + 1u32) / 2u32;
        s = mul_mod_pk(&s, &t, f, &pk);
        for x in s.iter_mut() {
            *x = (&*x * &inv2).mod_floor(&pk);
        }
        if bits >= target {
            let half = &pk / 2u32;
            let delta: Vec<BigInt> = mul_mod_pk(&gk, &s, f, &pk)
                .into_iter()
                .map(|x| if x > half { x - &pk } else { x })
                .collect();
            let sq = mul_mod_monic(&delta, &delta, f);
            if sq.iter().zip(g).all(|(x, y)| x == y) {
                stats.precision_bits = bits;
                stats.outcome = "ok".into();
                return Some(delta);
            }
            if bits > cap {
                stats.outcome = "no convergence".into();
                return None;
            }
        }
    }
}

/// Evaluate `δ(M) mod n`.
pub fn eval_mod(delta: &[BigInt], mm: &BigUint, n: &BigUint) -> BigUint {
    let mut acc = BigUint::zero();
    for c in delta.iter().rev() {
        acc = (acc * mm + bigint_mod(c, n)) % n;
    }
    acc
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn square_root_of_a_known_square() {
        // F = x³ − 2 (inert mod 7 since 2 is not a cube mod 7; use a larger
        // inert prime from the search), δ = 5 − 3x + 7x², Γ = δ².
        let f = IntPoly::from_i64(&[-2, 0, 0, 1]);
        let delta = vec![BigInt::from(5), BigInt::from(-3), BigInt::from(7)];
        let mut g = mul_mod_monic(&delta, &delta, &f.coeffs);
        // Make it big: multiply by a large square to exercise lifting.
        let big = vec![
            BigInt::from(123_456_789_012_345i64),
            BigInt::from(-987_654_321i64),
            BigInt::from(42),
        ];
        let big2 = mul_mod_monic(&big, &big, &f.coeffs);
        g = mul_mod_monic(&g, &big2, &f.coeffs);
        let want = mul_mod_monic(&delta, &big, &f.coeffs);
        let p = super::super::polysel::find_inert_prime(&f, 1 << 20, 100).unwrap();
        let mut st = SqrtStats::default();
        let r = sqrt_gamma(&f, &g, p, &mut st).expect("square");
        let neg: Vec<BigInt> = want.iter().map(|x| -x).collect();
        assert!(r == want || r == neg, "{r:?} vs {want:?}");
        assert!(r[0].bits() < 64);
    }

    #[test]
    fn non_square_is_rejected() {
        let f = IntPoly::from_i64(&[-2, 0, 0, 1]);
        let p = super::super::polysel::find_inert_prime(&f, 1 << 20, 100).unwrap();
        // 3 is not a square in Q(2^{1/3}) (odd degree field: 3 is a square
        // iff it is a square in Q).
        let g = vec![BigInt::from(3), BigInt::zero(), BigInt::zero()];
        let mut st = SqrtStats::default();
        assert!(sqrt_gamma(&f, &g, p, &mut st).is_none());
    }
}
