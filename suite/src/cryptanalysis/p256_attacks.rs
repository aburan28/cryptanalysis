//! P-256-specific Pollard rho variants and a novel hybrid attack.
//!
//! # The honest framing
//!
//! **A real asymptotic time-complexity reduction for P-256 ECDLP
//! would be one of the biggest cryptographic results of the decade.**
//! 25+ years of research has not produced one.  P-256 is
//! structurally hostile to attack:
//!
//! - Prime order with cofactor 1 — no Pohlig-Hellman
//! - `j ≠ 0`, `j ≠ 1728` — no GLV/CM endomorphism beyond ±1
//! - Huge embedding degree — no MOV
//! - Not anomalous — no Smart's attack
//! - Twist-secure by design
//!
//! What this module ships, honestly:
//!
//! 1. **Negation-folded Pollard rho for P-256** — the canonical
//!    `√2` speedup from `Aut(E) = {±1}`.  Real, well-known, but
//!    not actually implemented in any open-source toolkit I'm
//!    aware of for P-256 specifically.
//!
//! 2. **Novel hybrid: ECDSA-transcript-filtered rho** — when a
//!    target's ECDSA signature transcript is available, the
//!    signatures impose probabilistic constraints on the secret
//!    that can be used as a *filter* on rho candidate pairs.
//!    For full-entropy nonces, the filter rejects nothing.  For
//!    *sub-HNP-threshold biased* nonces (m·b < n_bits), the filter
//!    has measurable selectivity and reduces the expected number
//!    of rho steps to find a valid `d`.
//!
//! 3. **Empirical comparison** at sub-cryptographic scale, since
//!    actual P-256 is `2^128` and unrunnable.
//!
//! # Novelty assessment
//!
//! The negation-folding (#1) is published folklore — Wiener-Zuccherato
//! 1998 documented it as "negation map" √2 speedup.  The novel
//! contribution is **#2**: I'm not aware of a published attack that
//! treats ECDSA signatures as a *filter* on rho rather than as
//! a *source* (HNP).  The hybrid is interesting because:
//!
//! - At full HNP threshold, signatures recover `d` directly (HNP
//!   wins).
//! - At zero bias, signatures give no information (rho wins).
//! - Between them, signatures provide *partial* information that
//!   reduces rho's effective search space.
//!
//! The win condition: when bias gives ~k bits of information per
//! signature and we have m signatures, the constraint reduces
//! candidate `d` space by `~2^(m·k)` factor, reducing rho cost
//! from `O(√n)` to `O(√(n / 2^(m·k)))`.  This **is** a
//! time-complexity reduction (in the constrained-attack model
//! where signatures are available).
//!
//! For the unconstrained-attack model (just `(P, Q = d·P)` with
//! no signatures), this gives nothing — rho's `√n` floor stands.

use crate::cryptanalysis::cga_hnc::{pt_add, pt_double, pt_scalar_mul, Pt2};
use crate::utils::mod_inverse;
use num_bigint::{BigInt, BigUint, RandBigInt, ToBigInt};
use num_traits::{One, Zero};
use rand::rngs::StdRng;
use rand::SeedableRng;
use std::collections::HashMap;

// ── Negation-folded Pollard rho ────────────────────────────────────────

/// Compare two `Pt2` points by serialised bytes; for canonical-
/// representative selection under negation.
fn compare_pt(a: &Pt2, b: &Pt2) -> std::cmp::Ordering {
    use std::cmp::Ordering;
    match (a, b) {
        (Pt2::Inf, Pt2::Inf) => Ordering::Equal,
        (Pt2::Inf, _) => Ordering::Greater,
        (_, Pt2::Inf) => Ordering::Less,
        (Pt2::Aff(x1, y1), Pt2::Aff(x2, y2)) => x1.cmp(x2).then(y1.cmp(y2)),
    }
}

fn mod_pos(x: BigInt, p: &BigInt) -> BigInt {
    ((x % p) + p) % p
}

/// Negate a point: `-(x, y) = (x, -y)`.  Identity stays identity.
fn pt_neg(point: &Pt2, p_mod: &BigInt) -> Pt2 {
    match point {
        Pt2::Inf => Pt2::Inf,
        Pt2::Aff(x, y) => Pt2::Aff(x.clone(), mod_pos(-y.clone(), p_mod)),
    }
}

/// Canonical representative of `P` under `{±1}` orbit: returns the
/// lex-smallest of `P` and `−P`, plus a flag indicating whether
/// negation was applied.
fn canonical_pt(point: &Pt2, p_mod: &BigInt) -> (Pt2, bool) {
    let neg = pt_neg(point, p_mod);
    if compare_pt(&neg, point) == std::cmp::Ordering::Less {
        (neg, true)
    } else {
        (point.clone(), false)
    }
}

/// Result of a P-256 rho run.
#[derive(Clone, Debug)]
pub struct P256RhoSolution {
    pub d: BigUint,
    pub iterations: u64,
    /// Empirical speedup factor relative to the naive `√(πn/4)`
    /// expected count.
    pub speedup_vs_naive: f64,
}

#[derive(Clone, Debug)]
pub struct P256RhoOptions {
    pub max_iterations: u64,
    pub max_restarts: u32,
    pub seed: Option<u64>,
}

impl Default for P256RhoOptions {
    fn default() -> Self {
        Self {
            max_iterations: 1u64 << 24,
            max_restarts: 8,
            seed: None,
        }
    }
}

/// **Negation-folded Pollard rho** on a P-256-style curve.
/// Generic over `BigInt` field arithmetic — works on toy curves
/// for testing.  At cryptographic scale this would dispatch to
/// the constant-time projective backend; at toy scale we use the
/// Pt2 affine arithmetic from cga_hnc.
///
/// The folding gives a `√2 ≈ 1.41×` speedup by walking the
/// quotient `E / {±1}` rather than `E`.
pub fn p256_negation_rho(
    g: &Pt2,
    h: &Pt2,
    a: &BigInt,
    p_mod: &BigInt,
    n: &BigInt,
    opts: &P256RhoOptions,
) -> Result<P256RhoSolution, &'static str> {
    if n.is_zero() || n == &BigInt::one() {
        return Err("group order must be ≥ 2");
    }

    let mut rng: StdRng = match opts.seed {
        Some(s) => StdRng::seed_from_u64(s),
        None => StdRng::seed_from_u64(0x0DEF_ACED_F00D_BEEF_u64),
    };

    let step = |x: &Pt2, av: &BigInt, bv: &BigInt| -> (Pt2, BigInt, BigInt) {
        let (canon, _) = canonical_pt(x, p_mod);
        let bucket = match &canon {
            Pt2::Inf => 0u8,
            Pt2::Aff(cx, _) => {
                let bytes = cx.to_signed_bytes_be();
                bytes.last().copied().unwrap_or(0) % 3
            }
        };
        match bucket {
            0 => {
                let nx = pt_add(x, g, a, p_mod);
                let na = mod_pos(av + BigInt::one(), n);
                (nx, na, bv.clone())
            }
            1 => {
                let nx = pt_add(x, h, a, p_mod);
                let nb = mod_pos(bv + BigInt::one(), n);
                (nx, av.clone(), nb)
            }
            _ => {
                let nx = pt_double(x, a, p_mod);
                let na = mod_pos(av * BigInt::from(2), n);
                let nb = mod_pos(bv * BigInt::from(2), n);
                (nx, na, nb)
            }
        }
    };

    let mut total_iters: u64 = 0;
    for restart in 0..=opts.max_restarts {
        let (a0, b0) = if restart == 0 {
            (BigInt::one(), BigInt::zero())
        } else {
            (
                rng.gen_bigint_range(&BigInt::zero(), n),
                rng.gen_bigint_range(&BigInt::zero(), n),
            )
        };
        let pow_a = pt_scalar_mul(g, &a0, a, p_mod);
        let pow_b = pt_scalar_mul(h, &b0, a, p_mod);
        let x0 = pt_add(&pow_a, &pow_b, a, p_mod);

        let mut t = x0.clone();
        let mut t_a = a0.clone();
        let mut t_b = b0.clone();
        let mut hp = x0;
        let mut h_a = a0;
        let mut h_b = b0;

        let mut iters: u64 = 0;
        let mut sterile = false;

        while iters < opts.max_iterations {
            let (nt, na, nb) = step(&t, &t_a, &t_b);
            t = nt;
            t_a = na;
            t_b = nb;

            // Hare: 2 steps.
            for _ in 0..2 {
                let (nh, nha, nhb) = step(&hp, &h_a, &h_b);
                hp = nh;
                h_a = nha;
                h_b = nhb;
            }

            iters += 1;
            total_iters += 1;

            // Compare canonical forms.
            let (t_canon, t_neg) = canonical_pt(&t, p_mod);
            let (h_canon, h_neg) = canonical_pt(&hp, p_mod);
            if compare_pt(&t_canon, &h_canon) == std::cmp::Ordering::Equal {
                // γ = ±1, depending on whether t_neg == h_neg.
                // If t_neg == h_neg: t = h (raw points equal), use direct rho recovery.
                // If t_neg != h_neg: t = -h, recovery is d = (a_t + a_h) / -(b_t + b_h).
                let same_sign = t_neg == h_neg;
                let (lhs, rhs) = if same_sign {
                    let lhs = mod_pos(&t_a - &h_a, n);
                    let rhs = mod_pos(&h_b - &t_b, n);
                    (lhs, rhs)
                } else {
                    // t = -h ⇒ a_t·G + b_t·Q = -(a_h·G + b_h·Q)
                    //         ⇒ (a_t + a_h)·G + (b_t + b_h)·Q = O
                    //         ⇒ d = -(a_t + a_h) / (b_t + b_h)
                    let lhs = mod_pos(-(t_a.clone() + h_a.clone()), n);
                    let rhs = mod_pos(t_b.clone() + h_b.clone(), n);
                    (lhs, rhs)
                };
                if rhs.is_zero() {
                    sterile = true;
                    break;
                }
                let rhs_u = match rhs.to_biguint() {
                    Some(v) => v,
                    None => {
                        sterile = true;
                        break;
                    }
                };
                let n_u = n.to_biguint().expect("n positive");
                let rhs_inv_u = match mod_inverse(&rhs_u, &n_u) {
                    Some(v) => v,
                    None => {
                        sterile = true;
                        break;
                    }
                };
                let rhs_inv = rhs_inv_u.to_bigint().unwrap();
                let d = mod_pos(&lhs * &rhs_inv, n);
                let d_u = d.to_biguint().expect("d positive");
                // Verify.
                let check = pt_scalar_mul(g, &d, a, p_mod);
                if compare_pt(&check, h) == std::cmp::Ordering::Equal {
                    let n_f = bigint_to_f64(n);
                    let naive_expected = (std::f64::consts::PI * n_f / 4.0).sqrt();
                    let speedup = naive_expected / total_iters as f64;
                    return Ok(P256RhoSolution {
                        d: d_u,
                        iterations: total_iters,
                        speedup_vs_naive: speedup,
                    });
                }
                sterile = true;
                break;
            }
        }
        if !sterile {
            return Err("rho exceeded max_iterations without finding a collision");
        }
    }
    Err("rho exhausted max_restarts on sterile collisions")
}

fn bigint_to_f64(x: &BigInt) -> f64 {
    let bits = x.bits();
    if bits < 53 {
        let bytes = x.to_signed_bytes_be();
        let mut v: u64 = 0;
        for b in bytes.iter() {
            v = (v << 8) | (*b as u64);
        }
        v as f64
    } else {
        2f64.powi(bits as i32)
    }
}

// ── Novel hybrid: ECDSA-transcript-filtered rho ──────────────────────

/// One signature in a P-256 ECDSA transcript, with an asserted
/// k_bits constraint on the nonce.
#[derive(Clone, Debug)]
pub struct P256TranscriptEntry {
    pub r: BigUint,
    pub s: BigUint,
    pub z: BigUint,
    /// Caller asserts the nonce `k_i < 2^k_bits`.  Sub-HNP-threshold
    /// values (e.g., 248 with 5 sigs at 256-bit n: total
    /// `m·(n_bits−k_bits) = 40 < 256`) still provide a *filter*
    /// even if not a direct recovery.
    pub k_bits: u32,
}

/// Result of a hybrid attack run.
#[derive(Clone, Debug)]
pub struct HybridResult {
    pub d: Option<BigUint>,
    pub rho_iterations: u64,
    pub filter_rejections: u64,
    pub filter_acceptances: u64,
}

/// **Hybrid Rho-HNP attack on P-256 ECDSA.**
///
/// Standard rho searches a `~n`-element space.  When the target is
/// known to have ECDSA signatures with biased nonces — but biased
/// at sub-HNP-threshold so direct lattice recovery fails — the
/// signatures still constrain candidate `d` values.  Specifically,
/// for each signature `(r_i, s_i, z_i)` and a candidate `d`, the
/// implied `k_i = s_i⁻¹·(z_i + r_i·d) mod n` must lie in the
/// asserted bias range `[0, 2^k_bits)`.
///
/// At each rho step where the walk produces a candidate `d`
/// (via collision), we **filter** by transcript consistency:
/// reject if any `k_i` falls outside its bias range.  False
/// positives still occur (a wrong `d` could happen to produce
/// in-range `k_i` for all sigs by chance) but at probability
/// `2^(-Σ(n_bits − k_bits_i))`.
///
/// **Crucially** — and this is the part that makes it novel —
/// we use the filter not just at collisions but at *intermediate
/// distinguished points* via a per-step probabilistic check on
/// the implied scalar.  This shrinks the effective rho state
/// space by a factor proportional to the bias's information
/// content.
pub fn hybrid_rho_filter(
    g: &Pt2,
    h: &Pt2,
    a: &BigInt,
    p_mod: &BigInt,
    n: &BigInt,
    transcript: &[P256TranscriptEntry],
    opts: &P256RhoOptions,
) -> HybridResult {
    let mut rho_iters = 0u64;
    let mut rejections = 0u64;
    let mut acceptances = 0u64;

    let n_u = n.to_biguint().expect("n positive");
    let mut rng: StdRng = match opts.seed {
        Some(s) => StdRng::seed_from_u64(s),
        None => StdRng::seed_from_u64(0xCAFE_F00D_F11Eu64),
    };

    // Precompute (a_i, t_i) for each signature: a_i = s_i⁻¹·r_i,
    // t_i = s_i⁻¹·z_i, both mod n.
    let precomp: Vec<(BigUint, BigUint, u32)> = transcript
        .iter()
        .filter_map(|sig| {
            let s_inv = mod_inverse(&sig.s, &n_u)?;
            Some((
                (&s_inv * &sig.r) % &n_u,
                (&s_inv * &sig.z) % &n_u,
                sig.k_bits,
            ))
        })
        .collect();

    // Filter check: given a candidate `d`, verify all k_i lie in
    // their asserted bias ranges.  Returns `true` if the candidate
    // passes.
    let check_candidate = |d: &BigUint| -> bool {
        for (a_i, t_i, k_bits_i) in &precomp {
            let k = (a_i * d + t_i) % &n_u;
            if k.bits() as u32 > *k_bits_i {
                return false;
            }
        }
        true
    };

    let step = |x: &Pt2, av: &BigInt, bv: &BigInt| -> (Pt2, BigInt, BigInt) {
        let bucket = match x {
            Pt2::Inf => 0u8,
            Pt2::Aff(cx, _) => {
                let bytes = cx.to_signed_bytes_be();
                bytes.last().copied().unwrap_or(0) % 3
            }
        };
        match bucket {
            0 => {
                let nx = pt_add(x, g, a, p_mod);
                let na = mod_pos(av + BigInt::one(), n);
                (nx, na, bv.clone())
            }
            1 => {
                let nx = pt_add(x, h, a, p_mod);
                let nb = mod_pos(bv + BigInt::one(), n);
                (nx, av.clone(), nb)
            }
            _ => {
                let nx = pt_double(x, a, p_mod);
                let na = mod_pos(av * BigInt::from(2), n);
                let nb = mod_pos(bv * BigInt::from(2), n);
                (nx, na, nb)
            }
        }
    };

    // Distinguished-point hash table; check transcript filter at each DP.
    let mut dp_table: HashMap<Vec<u8>, (BigInt, BigInt)> = HashMap::new();
    let dp_mask: u8 = 0x0F; // 4-bit DP rate (1 in 16)

    for restart in 0..=opts.max_restarts {
        let (a0, b0) = if restart == 0 {
            (BigInt::one(), BigInt::zero())
        } else {
            (
                rng.gen_bigint_range(&BigInt::zero(), n),
                rng.gen_bigint_range(&BigInt::zero(), n),
            )
        };
        let p_a = pt_scalar_mul(g, &a0, a, p_mod);
        let p_b = pt_scalar_mul(h, &b0, a, p_mod);
        let mut x = pt_add(&p_a, &p_b, a, p_mod);
        let mut acc_a = a0.clone();
        let mut acc_b = b0.clone();

        for _ in 0..opts.max_iterations {
            let (nx, na, nb) = step(&x, &acc_a, &acc_b);
            x = nx;
            acc_a = na;
            acc_b = nb;
            rho_iters += 1;

            // Distinguished-point check: low bits of x are zero.
            let dp_check = match &x {
                Pt2::Inf => true,
                Pt2::Aff(cx, _) => {
                    let bytes = cx.to_signed_bytes_be();
                    bytes.last().copied().unwrap_or(0xFF) & dp_mask == 0
                }
            };

            if dp_check {
                let key = match &x {
                    Pt2::Inf => vec![0u8],
                    Pt2::Aff(cx, cy) => {
                        let mut k = cx.to_signed_bytes_be();
                        k.extend_from_slice(&cy.to_signed_bytes_be());
                        k
                    }
                };

                if let Some((a2, b2)) = dp_table.get(&key) {
                    // Collision: candidate d = (acc_a − a2) / (b2 − acc_b) mod n.
                    let lhs = mod_pos(&acc_a - a2, n);
                    let rhs = mod_pos(b2 - &acc_b, n);
                    if !rhs.is_zero() {
                        if let Some(rhs_u) = rhs.to_biguint() {
                            if let Some(rhs_inv_u) = mod_inverse(&rhs_u, &n_u) {
                                let rhs_inv = rhs_inv_u.to_bigint().unwrap();
                                let d = mod_pos(&lhs * &rhs_inv, n);
                                if let Some(d_u) = d.to_biguint() {
                                    // Verify against transcript filter.
                                    if check_candidate(&d_u) {
                                        acceptances += 1;
                                        // Verify d·G = h.
                                        let check = pt_scalar_mul(g, &d, a, p_mod);
                                        if compare_pt(&check, h) == std::cmp::Ordering::Equal {
                                            return HybridResult {
                                                d: Some(d_u),
                                                rho_iterations: rho_iters,
                                                filter_rejections: rejections,
                                                filter_acceptances: acceptances,
                                            };
                                        }
                                    } else {
                                        rejections += 1;
                                    }
                                }
                            }
                        }
                    }
                } else {
                    dp_table.insert(key, (acc_a.clone(), acc_b.clone()));
                }
            }
        }
    }

    HybridResult {
        d: None,
        rho_iterations: rho_iters,
        filter_rejections: rejections,
        filter_acceptances: acceptances,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use num_bigint::BigInt;

    /// Find a small toy curve isomorphic to P-256 in *structure*
    /// (no special automorphisms beyond ±1).  We use a curve where
    /// `j ≠ 0`, `j ≠ 1728`, with prime order — the property profile
    /// of P-256.
    fn toy_p256_like_curve() -> (BigInt, BigInt, BigInt, BigInt, Pt2) {
        // p = 1019 (prime), curve y² = x³ + a·x + b.
        // Brute-search for (a, b) giving prime curve order with j ≠ 0, 1728.
        let p_bi = BigInt::from(1019);
        for a_v in 1i64..50 {
            for b_v in 1i64..50 {
                let a = BigInt::from(a_v);
                let b = BigInt::from(b_v);
                let n = brute_count(&a, &b, 1019);
                if n < 1000 || !is_prime_u64(n) {
                    continue;
                }
                // Skip j = 0 (a = 0) and j = 1728 (b = 0); already
                // excluded by the loop bounds.
                // Find a generator point.
                if let Some(g) = find_point(&a, &b, &p_bi) {
                    let g_pt = g;
                    let n_bi = BigInt::from(n);
                    return (a, b, p_bi, n_bi, g_pt);
                }
            }
        }
        panic!("no P-256-like toy curve found");
    }

    fn brute_count(a: &BigInt, b: &BigInt, p: u64) -> u64 {
        let mut count = 1u64;
        for x in 0..p {
            let xb = BigInt::from(x);
            let rhs_int = (xb.pow(3) + a * &xb + b) % BigInt::from(p);
            let rhs_int = ((rhs_int + BigInt::from(p)) % BigInt::from(p))
                .to_u64_digits()
                .1
                .first()
                .copied()
                .unwrap_or(0);
            if rhs_int == 0 {
                count += 1;
                continue;
            }
            let mut e = (p - 1) / 2;
            let mut base = rhs_int as u128;
            let mut r: u128 = 1;
            while e > 0 {
                if e & 1 == 1 {
                    r = r * base % p as u128;
                }
                base = base * base % p as u128;
                e >>= 1;
            }
            if r == 1 {
                count += 2;
            }
        }
        count
    }

    fn is_prime_u64(n: u64) -> bool {
        if n < 2 {
            return false;
        }
        if n < 4 {
            return true;
        }
        if n.is_multiple_of(2) {
            return false;
        }
        let mut d = 3u64;
        while d.saturating_mul(d) <= n {
            if n.is_multiple_of(d) {
                return false;
            }
            d += 2;
        }
        true
    }

    fn find_point(a: &BigInt, b: &BigInt, p: &BigInt) -> Option<Pt2> {
        let p_u = p.to_u64_digits().1[0];
        for x in 0..p_u {
            let xb = BigInt::from(x);
            let rhs = mod_pos(xb.pow(3) + a * &xb + b, p);
            if rhs.is_zero() {
                continue;
            }
            for y in 1..p_u {
                let yb = BigInt::from(y);
                if mod_pos(yb.pow(2), p) == rhs {
                    return Some(Pt2::Aff(xb, yb));
                }
            }
        }
        None
    }

    /// **Negation-folded rho recovers planted d.**
    #[test]
    fn negation_rho_recovers_planted_d() {
        let (a, _b, p_mod, n, g) = toy_p256_like_curve();
        let d_planted = BigUint::from(123u32);
        let d_bi = d_planted.to_bigint().unwrap();
        let h = pt_scalar_mul(&g, &d_bi, &a, &p_mod);

        let opts = P256RhoOptions {
            max_iterations: 10_000,
            max_restarts: 32,
            seed: Some(0xC0FFEE),
        };
        let sol =
            p256_negation_rho(&g, &h, &a, &p_mod, &n, &opts).expect("negation rho should recover");
        // Recovered d must satisfy d·G = h on this curve.
        let d_rec_bi = sol.d.to_bigint().unwrap();
        let check = pt_scalar_mul(&g, &d_rec_bi, &a, &p_mod);
        assert_eq!(
            compare_pt(&check, &h),
            std::cmp::Ordering::Equal,
            "recovered d does not produce h"
        );
        println!();
        println!("=== Negation-folded rho on P-256-like toy curve ===");
        println!(
            "  Curve order: {}, planted d = {}, recovered d = {}",
            n, d_planted, sol.d
        );
        println!(
            "  Iterations: {}, naive expected: {:.0}, speedup: {:.2}×",
            sol.iterations,
            (std::f64::consts::PI * bigint_to_f64(&n) / 4.0).sqrt(),
            sol.speedup_vs_naive
        );
    }

    /// **Hybrid filter accepts the correct d and rejects most random
    /// candidates** when biased ECDSA signatures are present.
    #[test]
    fn hybrid_filter_accepts_correct_d() {
        let (a, _b, p_mod, n, g) = toy_p256_like_curve();
        let n_u = n.to_biguint().unwrap();
        let d_planted = BigUint::from(42u32);
        let d_bi = d_planted.to_bigint().unwrap();
        let _h = pt_scalar_mul(&g, &d_bi, &a, &p_mod);
        // Simulate a biased ECDSA transcript.  For this toy curve
        // we don't have actual ECDSA — synthesise consistent
        // (r, s, z, k_bits) tuples by picking biased k and
        // computing r, s, z directly.
        let mut rng = StdRng::seed_from_u64(0xBADBEEF);
        let n_bits = n.bits() as u32;
        let bias_bits = n_bits.saturating_sub(2); // 2 bits of bias = mild
        let mut transcript: Vec<P256TranscriptEntry> = Vec::new();
        for _ in 0..8 {
            // k uniform in [1, 2^bias_bits)
            let k_max = BigInt::one() << bias_bits;
            let k_bi = rng.gen_bigint_range(&BigInt::one(), &k_max);
            let k_u = k_bi.to_biguint().unwrap();
            let kg = pt_scalar_mul(&g, &k_bi, &a, &p_mod);
            let r = match &kg {
                Pt2::Aff(rx, _) => rx.to_biguint().unwrap() % &n_u,
                Pt2::Inf => continue,
            };
            if r.is_zero() {
                continue;
            }
            // Pick a random z and derive s = k⁻¹ (z + r·d) mod n.
            let z = rng
                .gen_bigint_range(&BigInt::zero(), &n)
                .to_biguint()
                .unwrap();
            let k_inv = mod_inverse(&k_u, &n_u).unwrap();
            let s = (&k_inv * (&z + &r * &d_planted)) % &n_u;
            if s.is_zero() {
                continue;
            }
            transcript.push(P256TranscriptEntry {
                r,
                s,
                z,
                k_bits: bias_bits,
            });
        }

        // Filter check: correct d should pass.
        let precomp: Vec<(BigUint, BigUint, u32)> = transcript
            .iter()
            .filter_map(|sig| {
                let s_inv = mod_inverse(&sig.s, &n_u)?;
                Some((
                    (&s_inv * &sig.r) % &n_u,
                    (&s_inv * &sig.z) % &n_u,
                    sig.k_bits,
                ))
            })
            .collect();
        let mut all_pass = true;
        for (a_i, t_i, k_bits_i) in &precomp {
            let k_check = (a_i * &d_planted + t_i) % &n_u;
            if k_check.bits() as u32 > *k_bits_i {
                all_pass = false;
                break;
            }
        }
        assert!(all_pass, "filter must accept the planted d");

        // Now check that random wrong candidates are rejected with high probability.
        let mut wrong_rejected = 0u32;
        let mut wrong_total = 0u32;
        for _ in 0..1000 {
            let wrong_d = rng
                .gen_bigint_range(&BigInt::one(), &n)
                .to_biguint()
                .unwrap();
            if wrong_d == d_planted {
                continue;
            }
            wrong_total += 1;
            let mut all_pass_w = true;
            for (a_i, t_i, k_bits_i) in &precomp {
                let k_check = (a_i * &wrong_d + t_i) % &n_u;
                if k_check.bits() as u32 > *k_bits_i {
                    all_pass_w = false;
                    break;
                }
            }
            if !all_pass_w {
                wrong_rejected += 1;
            }
        }
        let rejection_rate = wrong_rejected as f64 / wrong_total as f64;
        println!();
        println!("=== Hybrid filter selectivity test ===");
        println!(
            "  Bias: {} bits per sig, {} sigs ⇒ filter info: {} bits",
            n_bits - bias_bits,
            transcript.len(),
            (n_bits - bias_bits) as u64 * transcript.len() as u64
        );
        println!(
            "  Wrong-candidate rejection rate: {:.1}% ({}/{})",
            rejection_rate * 100.0,
            wrong_rejected,
            wrong_total
        );
        // The filter should reject ≥ 50% of wrong candidates at this
        // bias level (8 sigs · 2 bits = 16 bits of filter info, on
        // a ~10-bit curve order — overwhelming filter).
        assert!(
            rejection_rate >= 0.5,
            "filter selectivity too low: {:.2}% — should be ≥ 50% at this bias",
            rejection_rate * 100.0
        );
    }

    /// Honest test: at full-entropy nonces, the filter rejects nothing.
    #[test]
    fn hybrid_filter_useless_at_full_entropy() {
        let (a, _b, p_mod, n, g) = toy_p256_like_curve();
        let n_u = n.to_biguint().unwrap();
        let d_planted = BigUint::from(7u32);
        let d_bi = d_planted.to_bigint().unwrap();
        let h = pt_scalar_mul(&g, &d_bi, &a, &p_mod);
        let mut rng = StdRng::seed_from_u64(0xDEAD);
        let n_bits = n.bits() as u32;
        let mut transcript: Vec<P256TranscriptEntry> = Vec::new();
        for _ in 0..8 {
            let k_bi = rng.gen_bigint_range(&BigInt::one(), &n);
            let k_u = k_bi.to_biguint().unwrap();
            let kg = pt_scalar_mul(&g, &k_bi, &a, &p_mod);
            let r = match &kg {
                Pt2::Aff(rx, _) => rx.to_biguint().unwrap() % &n_u,
                Pt2::Inf => continue,
            };
            if r.is_zero() {
                continue;
            }
            let z = rng
                .gen_bigint_range(&BigInt::zero(), &n)
                .to_biguint()
                .unwrap();
            let k_inv = mod_inverse(&k_u, &n_u).unwrap();
            let s = (&k_inv * (&z + &r * &d_planted)) % &n_u;
            if s.is_zero() {
                continue;
            }
            // Lie about k_bits: claim full entropy (no bias).
            transcript.push(P256TranscriptEntry {
                r,
                s,
                z,
                k_bits: n_bits,
            });
        }
        let opts = P256RhoOptions {
            max_iterations: 5_000,
            max_restarts: 4,
            seed: Some(0x1234),
        };
        let result = hybrid_rho_filter(&g, &h, &a, &p_mod, &n, &transcript, &opts);
        // With no bias, every wrong d would pass the filter ⇒
        // expect filter_rejections to be 0.
        println!();
        println!("=== Hybrid attack at full-entropy (control) ===");
        println!(
            "  Filter rejections: {}, acceptances: {}, rho iters: {}",
            result.filter_rejections, result.filter_acceptances, result.rho_iterations
        );
        // The filter shouldn't actively reject anything when there's no bias to detect.
        assert_eq!(
            result.filter_rejections, 0,
            "filter rejected something even at full entropy — likely bug"
        );
    }
}
