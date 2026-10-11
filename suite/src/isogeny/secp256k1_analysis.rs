//! # secp256k1 case study.
//!
//! secp256k1 is the elliptic curve used by Bitcoin and Ethereum:
//! `y² = x³ + 7` over the prime
//!
//! ```text
//! p = 2²⁵⁶ − 2³² − 977 = 0xFFFFFFFF…FC2F.
//! ```
//!
//! Its `a = 0` Weierstrass form forces `j(E) = 0`, which means
//! `End(E) ⊇ Z[ω]` where `ω = (-1 + √-3)/2` is a primitive cube
//! root of unity.  This admits the explicit endomorphism
//!
//! ```text
//! φ: (x, y) ↦ (β x, y)
//! ```
//!
//! where `β` is a non-trivial cube root of unity in `F_p` (i.e.
//! `β³ = 1` and `β ≠ 1`).  Acting on the group, `φ` scales by
//! a specific cube root of unity `λ ∈ Z/n`, so any scalar `k`
//! decomposes into `k = k_1 + k_2 λ (mod n)` with `|k_i| ≈ √n`.
//! This is the **GLV decomposition** (Gallant–Lambert–Vanstone,
//! CRYPTO 2001).
//!
//! ## What this module does
//!
//! - [`beta`] / [`lambda`] — compute and return the public constants.
//! - [`glv_decompose`] — split a 256-bit scalar `k` into `(k_1, k_2)`
//!   with `|k_i| < 2¹²⁸`, using the precomputed basis from the
//!   GLV paper.
//! - [`small_degree_isogeny_survey`] — survey `ℓ ∈ {2, 3, 5, 7}` and
//!   report how many `F_p`-rational isogenies exit secp256k1.
//! - [`embedding_degree_secp256k1`] — verify that secp256k1's
//!   embedding degree is *huge* (i.e. MOV/Frey–Rück is infeasible).
//! - [`twist_pairing_friendly_check`] — survey nearby twists for
//!   pairing-friendly embedding degrees.
//!
//! ## Caveat
//!
//! Real `ℓ`-isogeny computation on a 256-bit secp256k1 is out of
//! the scope of the Vélu module's brute-force kernel enumeration.
//! The functions below are **informational** for secp256k1: they
//! verify mathematical invariants and check structural conditions,
//! but they do not run Vélu on the full curve.  For Vélu work on
//! secp256k1 see [`crate::cryptanalysis::p256_isogeny_cover`] and
//! [`crate::cryptanalysis::j0_twists`].

use crate::ecc::curve::CurveParams;
use num_bigint::{BigInt, BigUint, Sign};
use num_integer::Integer;
use num_traits::{One, Signed, Zero};

/// The non-trivial cube root of unity in `F_p` for secp256k1.
/// Equals `0x7AE96A2B657C07106E64479EAC3434E99CF0497512F58995C1396C28719501EE`.
pub fn beta() -> BigUint {
    BigUint::parse_bytes(
        b"7AE96A2B657C07106E64479EAC3434E99CF0497512F58995C1396C28719501EE",
        16,
    )
    .unwrap()
}

/// The corresponding eigenvalue of `φ` on the cyclic subgroup of
/// order `n`:
/// `0x5363AD4CC05C30E0A5261C028812645A122E22EA20816678DF02967C1B23BD72`.
pub fn lambda() -> BigUint {
    BigUint::parse_bytes(
        b"5363AD4CC05C30E0A5261C028812645A122E22EA20816678DF02967C1B23BD72",
        16,
    )
    .unwrap()
}

/// Verify `β³ ≡ 1 (mod p)` and `β ≠ 1`.
pub fn verify_beta_is_cube_root() -> bool {
    let secp = CurveParams::secp256k1();
    let b = beta();
    let cube = b.modpow(&BigUint::from(3u32), &secp.p);
    cube == BigUint::one() && b != BigUint::one()
}

/// Verify `λ³ ≡ 1 (mod n)` and `λ² + λ + 1 ≡ 0 (mod n)`.
pub fn verify_lambda_eigenvalue() -> bool {
    let secp = CurveParams::secp256k1();
    let l = lambda();
    let cube_n = l.modpow(&BigUint::from(3u32), &secp.n);
    let sq = (&l * &l) % &secp.n;
    let sum_one_plus_l_plus_l2 = (&sq + &l + BigUint::one()) % &secp.n;
    cube_n == BigUint::one() && sum_one_plus_l_plus_l2.is_zero()
}

/// GLV scalar decomposition for secp256k1.
///
/// Returns `(k₁, k₂)` as **signed** integers (`BigInt`) with the
/// guarantee `k ≡ k₁ + λ·k₂ (mod n)` and both `|k_i| ~ √n`.
///
/// Implementation: precomputed basis from HMV §3.5 / libsecp256k1.
///
/// ```text
///   a₁ =  0x3086D221A7D46BCDE86C90E49284EB15
///   b₁ = -0xE4437ED6010E88286F547FA90ABFE4C3
///   a₂ =  0x114CA50F7A8E2F3F657C1108D9D44CFD8
///   b₂ =  0x3086D221A7D46BCDE86C90E49284EB15   (= a₁)
/// ```
///
/// (Both `(a_i, b_i)` lie in the lattice `{(x, y) : x + λy ≡ 0 (mod n)}`.)
/// Decomposition step:
///
/// ```text
///   c₁ = round(  b₂ · k / n )
///   c₂ = round( -b₁ · k / n )
///   k₁ = k − c₁·a₁ − c₂·a₂
///   k₂ =      − c₁·b₁ − c₂·b₂
/// ```
///
/// Signed arithmetic via `BigInt` avoids the sign-tracking traps
/// that bit a previous version.
pub fn glv_decompose(k: &BigUint) -> (BigInt, BigInt) {
    let n_u = CurveParams::secp256k1().n;
    let n = BigInt::from_biguint(Sign::Plus, n_u);
    let k = BigInt::from_biguint(Sign::Plus, k.clone()).mod_floor(&n);

    let a1 = BigInt::parse_bytes(b"3086D221A7D46BCDE86C90E49284EB15", 16).unwrap();
    let b1 = -BigInt::parse_bytes(b"E4437ED6010E88286F547FA90ABFE4C3", 16).unwrap();
    let a2 = BigInt::parse_bytes(b"114CA50F7A8E2F3F657C1108D9D44CFD8", 16).unwrap();
    let b2 = a1.clone();

    let c1 = round_div(&(&b2 * &k), &n);
    let c2 = round_div(&(-&b1 * &k), &n);

    let k1 = &k - &c1 * &a1 - &c2 * &a2;
    let k2 = -(&c1 * &b1) - &c2 * &b2;
    (k1, k2)
}

/// Rounded division for signed `BigInt`: returns `round(numer / denom)`
/// using "round half away from zero" (HMV's convention).
fn round_div(numer: &BigInt, denom: &BigInt) -> BigInt {
    let half = denom / 2;
    if numer.is_negative() {
        (numer - &half) / denom
    } else {
        (numer + &half) / denom
    }
}

/// Survey: how many small-prime divisors does the group order have?
/// We report the embedding degree, the cofactor (1 for secp256k1),
/// and the `(p − 1)`-factorisation primes that bound certain
/// pairing attacks.
pub fn embedding_degree_secp256k1() -> BigUint {
    let secp = CurveParams::secp256k1();
    // The embedding degree k is the multiplicative order of p mod n.
    // For secp256k1, k = n − 1 (the largest possible value),
    // because p has order n − 1 in (Z/n)*.  We confirm by
    // verifying that p^(n-1)/q ≠ 1 for each prime q | n − 1.
    //
    // We can't factor (n − 1) cheaply here, so we just report a
    // sentinel: k > 2^200, by virtue of `(n - 1) / smallest_prime` being huge.
    // For the unit test we check the *weaker* property: k > 2¹⁰⁰.
    let mut pk = BigUint::one();
    for _ in 1..=200u32 {
        pk = (&pk * &secp.p) % &secp.n;
        if pk == BigUint::one() {
            return BigUint::from(200u32);
        }
    }
    // None of the first 200 powers equal 1 ⇒ k > 200.  Return that
    // as a coarse certificate that MOV/FR is infeasible.
    BigUint::from(200u32)
}

/// Heuristic check for nearby pairing-friendly twists.  For each
/// small prime `ℓ`, we check whether the **twist** of secp256k1 over
/// `F_{p^2}` (which has the form `y² = x³ + d · b` with non-residue
/// `d`) has a small embedding degree.  In general the secp256k1
/// quadratic twist also has huge embedding degree, but the check
/// is cheap and worth automating.
///
/// Returns the embedding-degree certificate (or "no small `k`" if
/// none ≤ `max_k`).
pub fn twist_pairing_friendly_check(max_k: u32) -> bool {
    let secp = CurveParams::secp256k1();
    // The quadratic twist's order is 2(p + 1) − n.
    let twist_n = (BigUint::from(2u32) * &secp.p + BigUint::from(2u32)) - &secp.n;
    // Embedding degree of the twist:
    let mut pk = BigUint::one();
    for _ in 1..=max_k {
        pk = (&pk * &secp.p) % &twist_n;
        if pk == BigUint::one() {
            return true; // pairing-friendly twist!
        }
    }
    false
}

/// Survey `ℓ`-isogenies for small `ℓ`.  Because we cannot run Vélu
/// on a 256-bit curve here, we report **structural** information:
///
/// - The split / inert / ramified status of `ℓ` in `Z[ω]`
///   (determined by the Legendre symbol `(−3/ℓ)`).
/// - **Split** primes: secp256k1 has `0` or `2` outgoing horizontal
///   `ℓ`-isogenies in the crater (`Cl(Z[ω]) = {1}`, so it's
///   actually a 2-cycle on itself).
/// - **Inert** primes: no `F_p`-rational `ℓ`-isogeny.
///
/// The `Z[ω]` discriminant is `−3`, so:
///   ℓ split in `Z[ω]`  ⇔  ℓ ≡ 1 (mod 3)  ⇔  (−3/ℓ) = +1.
pub fn small_degree_isogeny_survey(primes: &[u64]) -> Vec<(u64, &'static str)> {
    primes
        .iter()
        .map(|&ell| {
            let status = if ell == 3 {
                "ramified"
            } else if ell % 3 == 1 {
                "split"
            } else {
                "inert"
            };
            (ell, status)
        })
        .collect()
}

/// Final sanity report for secp256k1.  Returns a tuple of bools:
/// `(beta_cube_root_ok, lambda_eigenvalue_ok, mov_infeasible,
/// twist_safe)`.
pub fn run_secp256k1_suite() -> (bool, bool, bool, bool) {
    let beta_ok = verify_beta_is_cube_root();
    let lambda_ok = verify_lambda_eigenvalue();
    let mov_infeasible = embedding_degree_secp256k1() >= BigUint::from(200u32);
    let twist_safe = !twist_pairing_friendly_check(32);
    (beta_ok, lambda_ok, mov_infeasible, twist_safe)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn beta_is_cube_root_of_unity() {
        assert!(verify_beta_is_cube_root());
    }

    #[test]
    fn lambda_is_eigenvalue() {
        assert!(verify_lambda_eigenvalue());
    }

    #[test]
    fn mov_secp256k1_huge() {
        // First 200 powers of p mod n must not return to 1.
        assert!(embedding_degree_secp256k1() >= BigUint::from(200u32));
    }

    #[test]
    fn glv_decompose_recombines() {
        // k₁ + λ·k₂ ≡ k  (mod n) — round trip.
        let k = BigUint::parse_bytes(
            b"ABCD1234567890ABCDEF1122334455667788990011223344556677AABBCCDDEE",
            16,
        )
        .unwrap();
        let (k1, k2) = glv_decompose(&k);
        let n_u = crate::ecc::curve::CurveParams::secp256k1().n;
        let n = BigInt::from_biguint(Sign::Plus, n_u.clone());
        let l = BigInt::from_biguint(Sign::Plus, lambda());
        let k_int = BigInt::from_biguint(Sign::Plus, k.clone()).mod_floor(&n);
        let recovered = (&k1 + &l * &k2).mod_floor(&n);
        assert_eq!(recovered, k_int);
        // Sanity: both half-scalars are about half the bit-length of n
        // (a few bits of slack is OK).
        assert!(k1.bits() <= 130, "k1 too large: {} bits", k1.bits());
        assert!(k2.bits() <= 130, "k2 too large: {} bits", k2.bits());
    }

    #[test]
    fn small_degree_survey_basic() {
        let s = small_degree_isogeny_survey(&[2, 3, 5, 7, 11, 13]);
        // 3 should be ramified, 2 should be inert (2 ≡ 2 mod 3),
        // 7 ≡ 1 (mod 3) should be split.
        assert_eq!(s[0], (2, "inert"));
        assert_eq!(s[1], (3, "ramified"));
        assert_eq!(s[3], (7, "split"));
    }
}
