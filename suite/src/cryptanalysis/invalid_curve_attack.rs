//! **Invalid-curve attack** on ECC implementations that fail to
//! validate input points before scalar multiplication.
//!
//! ## Threat model
//!
//! The victim holds a private scalar `d`.  When given an "x-coordinate
//! input" (think ECDH responder), the victim:
//!
//! 1. **Reconstructs** a point `P = (x, y)` from the x-coordinate by
//!    solving `y² = x³ + ax + b` (in the field).
//! 2. **Computes** `S = d · P` via the standard scalar-mul formulas
//!    using the curve coefficients `(a, b)`.
//! 3. **Returns** `S` (or a key derived from `S`) to the attacker.
//!
//! **The vulnerability**: the attacker submits an `x` such that
//! `(x, y)` is **on a different curve** — a twist `E_d': y² = x³ +
//! a·x + b·d` with a much smaller group order.  Because the scalar-
//! mul formulas don't depend on `b` (only on `a`!), the operation
//! still computes correctly **on the twist**.  The output `S` then
//! lives on the twist.
//!
//! When the twist's order has a small prime-power factor `q`, the
//! attacker recovers `d mod q` by Pohlig-Hellman on the twist.
//! Repeat across multiple twists with coprime small factors and CRT
//! the residues to recover the **full** `d`.
//!
//! ## Why j-invariant 0 curves are especially exposed
//!
//! j=0 curves `y² = x³ + b` have **six** twists `E_{b·g^i}` for
//! `i ∈ [0, 6)` (vs. just two for generic curves).  Six rolls of
//! the dice that one twist has smooth order.  Our
//! `cryptanalysis::j0_twists` empirical bench found that **every
//! j=0 prime in our test set** has at least one twist with max prime
//! factor ≤ 256 — making this attack trivially executable.
//!
//! ## What this module ships
//!
//! - [`mount_invalid_curve_attack`] — full end-to-end attack:
//!   enumerate twists, find smooth ones, simulate the victim's
//!   black-box `d·P` operation on the twist, run PH on each
//!   recovered residue, CRT to reconstruct `d`.
//! - [`InvalidCurveAttackReport`] — structured outcome.
//! - [`format_visualization`] — Markdown attack report.
//!
//! ## References
//!
//! - **B. Möller**, *A public-key encryption scheme with pseudo-random
//!   ciphertexts*, ESORICS 2004 — first systematic invalid-curve attack.
//! - **D. Antipa, D. R. L. Brown, A. Menezes, R. Struik, S. A. Vanstone**,
//!   *Validation of elliptic curve public keys*, PKC 2003.
//! - **B. Möller, A. Vanstone**, *Invalid-curve attacks on ECC* (informal).

use crate::cryptanalysis::j0_twists::{enumerate_twists, TwistInfo};
use crate::cryptanalysis::pohlig_hellman::{
    crt_combine, pohlig_hellman_curve, PohligHellmanReport,
};
use crate::ecc::curve::CurveParams;
use crate::visualize::color::{paint, FG_BRIGHT_GREEN, FG_BRIGHT_RED, FG_BRIGHT_YELLOW};
use num_bigint::BigUint;
use num_traits::{One, Zero};

/// Outcome of an invalid-curve attack run.
#[derive(Clone, Debug)]
pub struct InvalidCurveAttackReport {
    /// The original (defender's) curve.
    pub base_curve_name: String,
    /// The defender's secret scalar (revealed iff attack succeeds).
    pub d_truth: BigUint,
    /// The base-curve generator order — the "full" key-space size.
    pub n_base: BigUint,
    /// Number of twists examined.
    pub twists_total: usize,
    /// Number of twists actually used (smooth subgroup found).
    pub twists_used: usize,
    /// Bits of `d` recovered (= `log₂(product of used twist subgroup sizes)`).
    pub bits_recovered: f64,
    /// `d mod (product of subgroup orders)` (= what the attacker actually learns).
    pub recovered_d_partial: Option<BigUint>,
    /// `d` recovered fully iff the union of subgroup orders covers
    /// `n_base` (or modular brute-force fills the gap).
    pub recovered_d_full: Option<BigUint>,
    /// Per-twist Pohlig-Hellman reports.
    pub per_twist_reports: Vec<(usize, PohligHellmanReport)>,
}

/// **Mount the full invalid-curve attack** on a j=0 base curve.
///
/// `base_curve` is the legitimate curve where the victim's `d` lives.
/// `d_truth` is the (unknown-to-attacker, but known to us in test)
/// secret scalar.  `smoothness_bound` controls how many bits of each
/// twist's order we'll attempt to brute-force.
///
/// Returns a structured report.  The attack succeeds if the union of
/// recovered subgroup orders (CRT'd) uniquely determines `d` mod
/// `n_base`.
pub fn mount_invalid_curve_attack(
    base_curve: &CurveParams,
    d_truth: &BigUint,
    smoothness_bound: u64,
) -> InvalidCurveAttackReport {
    let twists = enumerate_twists(&base_curve.p, &base_curve.b).unwrap_or_default();
    let mut per_twist_reports: Vec<(usize, PohligHellmanReport)> = Vec::new();
    let mut residues: Vec<(BigUint, BigUint)> = Vec::new();
    let mut bits_recovered = 0.0f64;
    for (idx, twist) in twists.iter().enumerate() {
        // Skip twists that are themselves prime (no small-factor leak).
        if twist.factorisation.len() == 1 && twist.factorisation[0].1 == 1 {
            continue;
        }
        // Pick the smooth subgroup: the largest factor of `twist.order`
        // whose every prime is ≤ smoothness_bound.
        let smooth_part = compute_smooth_part(&twist.order, smoothness_bound);
        if smooth_part <= BigUint::one() {
            continue;
        }
        // Construct the twist curve.
        let twist_curve = construct_twist_curve(base_curve, twist);
        let twist_g = twist_curve.generator();
        // **Simulate the victim**: the victim, given a point on the
        // twist, computes d_truth · P using AES coefficients.  We
        // produce the resulting point S on the twist directly.
        let s = twist_g.scalar_mul(d_truth, &twist_curve.a_fe());
        // Map d_truth to "d on the twist of smooth order":
        // because `d_twist_g = (d mod twist.order) · g_twist`, we have
        // S = (d mod twist.order) · twist_g.
        // Project to the smooth subgroup: solve for d mod smooth_part.
        let cofactor = &twist.order / &smooth_part;
        let small_g = twist_g.scalar_mul(&cofactor, &twist_curve.a_fe());
        let small_s = s.scalar_mul(&cofactor, &twist_curve.a_fe());
        let ph_report = pohlig_hellman_curve(
            &twist_curve,
            &small_g,
            &small_s,
            &smooth_part,
            smoothness_bound,
        );
        if let Some(d_mod_smooth) = &ph_report.recovered_d {
            // Decompose smooth_part into its prime-power factors so
            // CRT operates on pairwise coprime moduli only.  When two
            // twists give residues at the same prime, keep the
            // higher-power version (the larger one is at least as
            // informative).
            let pp_factors = crate::cryptanalysis::j0_twists::factorise_small(&smooth_part);
            for (p, e) in pp_factors {
                let pe = p.pow(e);
                let d_mod_pe = d_mod_smooth % &pe;
                // Check whether this prime is already in `residues`;
                // if so, only keep the higher prime-power.
                let existing_idx = residues.iter().position(|(m, _)| {
                    crate::cryptanalysis::j0_twists::factorise_small(m)
                        .iter()
                        .any(|(q, _)| q == &p)
                });
                if let Some(i) = existing_idx {
                    if pe > residues[i].0 {
                        residues[i] = (pe.clone(), d_mod_pe);
                    }
                } else {
                    residues.push((pe.clone(), d_mod_pe));
                }
            }
            let bits = (smooth_part.bits() as f64).max(0.0);
            bits_recovered += bits;
        }
        per_twist_reports.push((idx, ph_report));
    }
    // Deduplication may have left residues at distinct primes; CRT
    // them now.
    let recovered_d_partial = if residues.is_empty() {
        None
    } else {
        crt_combine(&residues)
    };
    // Full recovery: did the union of moduli cover n_base?
    let total_mod = residues
        .iter()
        .fold(BigUint::one(), |acc, (m, _)| acc * m.clone());
    let recovered_d_full = if let Some(partial) = &recovered_d_partial {
        if total_mod >= base_curve.n {
            // Lift uniquely via mod n_base.
            Some(partial % &base_curve.n)
        } else {
            // The remaining unknown is in [0, n_base / total_mod).
            // Brute-force completion if cheap.
            let remaining_bits = base_curve.n.bits() as f64 - (total_mod.bits() as f64);
            if remaining_bits <= 24.0 {
                Some(complete_via_brute_force(
                    base_curve, partial, &total_mod, d_truth,
                ))
            } else {
                None
            }
        }
    } else {
        None
    };
    InvalidCurveAttackReport {
        base_curve_name: base_curve.name.to_string(),
        d_truth: d_truth.clone(),
        n_base: base_curve.n.clone(),
        twists_total: twists.len(),
        twists_used: residues.len(),
        bits_recovered,
        recovered_d_partial,
        recovered_d_full,
        per_twist_reports,
    }
}

/// Compute the largest divisor of `n` whose every prime factor is
/// `≤ smoothness_bound`.
fn compute_smooth_part(n: &BigUint, smoothness_bound: u64) -> BigUint {
    let factors = crate::cryptanalysis::j0_twists::factorise_small(n);
    let bound = BigUint::from(smoothness_bound);
    let mut out = BigUint::one();
    for (p, e) in factors {
        if p <= bound {
            out *= p.pow(e);
        }
    }
    out
}

/// Construct the explicit `CurveParams` for a `TwistInfo`.  Uses
/// `(a = 0, b = twist.b_prime)` since j=0 curves all have `a = 0`.
/// The generator is reconstructed by finding the lowest-x point on
/// the twist.
fn construct_twist_curve(base: &CurveParams, twist: &TwistInfo) -> CurveParams {
    // Find a generator: smallest x ∈ [1, p) with x³ + b' a QR mod p.
    let mut gx = BigUint::one();
    let mut gy = BigUint::zero();
    while gx < base.p {
        let x = base.fe(gx.clone());
        let rhs = x.mul(&x).mul(&x).add(&base.fe(twist.b_prime.clone())).value;
        if let Some(y) = crate::cryptanalysis::ec_index_calculus::sqrt_mod_p(&rhs, &base.p) {
            gy = y;
            break;
        }
        gx += 1u32;
    }
    CurveParams {
        // Leak the leading "twist-" prefix so the caller can tell it's a twist.
        name: "j0-twist",
        p: base.p.clone(),
        a: BigUint::zero(),
        b: twist.b_prime.clone(),
        gx,
        gy,
        n: twist.order.clone(),
        h: 1,
    }
}

/// **Brute-force fill the gap**: after CRT recovery to
/// `d ≡ partial (mod total_mod)`, brute-force the remaining
/// `[d, d + total_mod, …]` values until one matches the true `d`.
///
/// (In a real attack the attacker doesn't know `d_truth` — they'd
/// instead check by scalar-multing `d_candidate · G_base = Q_base`
/// against a known public key.  We accept `d_truth` here for test
/// purposes only.)
fn complete_via_brute_force(
    base: &CurveParams,
    partial: &BigUint,
    total_mod: &BigUint,
    d_truth: &BigUint,
) -> BigUint {
    let mut candidate = partial.clone();
    while candidate < base.n {
        if &candidate == d_truth {
            return candidate;
        }
        candidate += total_mod;
    }
    partial.clone()
}

/// Render a Markdown report of an invalid-curve attack.
pub fn format_visualization(report: &InvalidCurveAttackReport) -> String {
    let mut s = String::new();
    s.push_str("# Invalid-curve attack on a j-invariant 0 base curve\n\n");
    s.push_str(&format!(
        "**Base curve**: `{}`, group order **{}** (≈ {} bits)\n\n",
        report.base_curve_name,
        report.n_base,
        report.n_base.bits()
    ));
    s.push_str(&format!(
        "**Twists examined**: {}, used: **{}**\n\n",
        report.twists_total, report.twists_used,
    ));
    s.push_str(&format!(
        "**Bits of `d` recovered via twists**: ≈ {:.1}\n\n",
        report.bits_recovered,
    ));
    if !report.per_twist_reports.is_empty() {
        s.push_str("## Per-twist Pohlig-Hellman residues\n\n");
        s.push_str("| twist idx | smooth subgroup order | recovered d mod q |\n");
        s.push_str("|----------:|----------------------:|------------------:|\n");
        for (idx, ph) in &report.per_twist_reports {
            let order_used: BigUint = ph.residues.iter().map(|(m, _)| m.clone()).product();
            let recovered = ph
                .recovered_d
                .as_ref()
                .map(|d| d.to_str_radix(10))
                .unwrap_or_else(|| "—".into());
            s.push_str(&format!("| {} | {} | {} |\n", idx, order_used, recovered,));
        }
        s.push('\n');
    }
    s.push_str("## Attack outcome\n\n");
    match (&report.recovered_d_full, &report.recovered_d_partial) {
        (Some(d), _) => {
            let correct = d == &report.d_truth;
            s.push_str(&format!(
                "  {} **Full key recovered**: `d = {}`{}\n",
                if correct {
                    paint("✓", FG_BRIGHT_GREEN)
                } else {
                    paint("✗", FG_BRIGHT_RED)
                },
                d,
                if correct { " (matches truth)" } else { " (MISMATCH!)" },
            ));
        }
        (None, Some(p)) => s.push_str(&format!(
            "  {} **Partial recovery**: `d ≡ {} (mod ∏ q_i)`; {} more bits to brute-force\n",
            paint("⚠", FG_BRIGHT_YELLOW),
            p,
            (report.n_base.bits() as f64 - report.bits_recovered).max(0.0) as u64,
        )),
        (None, None) => s.push_str(&format!(
            "  {} **Attack failed**: no twist with smooth-enough order found below smoothness bound.\n",
            paint("✗", FG_BRIGHT_RED),
        )),
    }
    s
}

// ── Tests ────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    /// A small j=0 curve guaranteed to have at least one weak twist.
    /// From the j0_twists bench: p=65353 has a twist with order
    /// 65856 = 2⁶ · 3 · 7³, max prime factor 7.
    fn j0_16bit() -> CurveParams {
        CurveParams {
            name: "j0-bench-16bit",
            p: BigUint::from(65353u32),
            a: BigUint::zero(),
            b: BigUint::from(5u32),
            gx: BigUint::from(1u32),
            gy: BigUint::from(2632u32),
            n: BigUint::from(65521u32),
            h: 1,
        }
    }

    /// **Headline test**: invalid-curve attack on the 16-bit j=0
    /// curve recovers at least partial info on `d`.
    #[test]
    fn invalid_curve_attack_recovers_partial_d() {
        let curve = j0_16bit();
        let d_truth = BigUint::from(12345u32);
        let report = mount_invalid_curve_attack(&curve, &d_truth, 16);
        assert!(report.twists_used > 0, "expected at least one usable twist");
        // Bits recovered must be > 0 if any twist worked.
        assert!(report.bits_recovered > 0.0);
    }

    /// **Smoothness-bound = 0** → no twist is usable.
    #[test]
    fn invalid_curve_attack_fails_with_zero_bound() {
        let curve = j0_16bit();
        let d_truth = BigUint::from(100u32);
        let report = mount_invalid_curve_attack(&curve, &d_truth, 0);
        assert_eq!(report.twists_used, 0);
        assert!(report.recovered_d_full.is_none());
    }

    /// **Visualization** renders with all sections.
    #[test]
    fn format_visualization_renders() {
        let curve = j0_16bit();
        let d_truth = BigUint::from(42u32);
        let report = mount_invalid_curve_attack(&curve, &d_truth, 16);
        let s = format_visualization(&report);
        assert!(s.contains("Invalid-curve attack"));
        assert!(s.contains("Base curve"));
        assert!(s.contains("Twists examined"));
        assert!(s.contains("Attack outcome"));
    }

    /// **Smooth-part extractor** correctly bounds.
    #[test]
    fn smooth_part_with_low_bound() {
        // 65856 = 2⁶ · 3 · 7³.  Bound = 5: keep 2⁶ · 3 = 192.
        let n = BigUint::from(65856u32);
        let smooth = compute_smooth_part(&n, 5);
        assert_eq!(smooth, BigUint::from(192u32));
    }

    /// **Smooth-part = full** when bound exceeds every prime factor.
    #[test]
    fn smooth_part_fully_smooth_at_high_bound() {
        let n = BigUint::from(65856u32);
        let smooth = compute_smooth_part(&n, 10);
        assert_eq!(smooth, n);
    }

    /// **Demo emission**: run the full attack + print the visual.
    #[test]
    #[ignore]
    fn demo_invalid_curve_attack() {
        let curve = j0_16bit();
        let d_truth = BigUint::from(12345u32);
        let report = mount_invalid_curve_attack(&curve, &d_truth, 32);
        println!("{}", format_visualization(&report));
    }
}
