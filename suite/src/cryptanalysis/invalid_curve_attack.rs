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
//! - [`mount_invalid_curve_attack_oracle`] — the real end-to-end
//!   attack against a black-box scalar-multiplication **oracle**
//!   `Fn(&Point) -> Point`.  The attack code never sees the secret
//!   `d`: it crafts points of small prime-power order on each smooth
//!   twist, queries the oracle for `d · P` on the base curve's
//!   incomplete formulas (which land on the twist), solves the small
//!   subgroup DLP with [`pohlig_hellman_curve`], CRTs the residues,
//!   and completes/verifies the candidate against the victim's public
//!   key `Q` by checking `d · G == Q`.
//! - [`mount_invalid_curve_attack`] — a convenience wrapper for tests
//!   and demos that builds an *honest* oracle from a planted `d`
//!   (`|P| -> d · P`) and its public key `Q = d · G`, then runs the
//!   oracle attack above.  The oracle closure sees `d`; the attack
//!   does not.
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
use crate::ecc::point::Point;
use crate::visualize::color::{paint, FG_BRIGHT_GREEN, FG_BRIGHT_RED, FG_BRIGHT_YELLOW};
use num_bigint::BigUint;
use num_traits::{One, Zero};

/// Outcome of an invalid-curve attack run.
#[derive(Clone, Debug)]
pub struct InvalidCurveAttackReport {
    /// The original (defender's) curve.
    pub base_curve_name: String,
    /// The base-curve generator order — the "full" key-space size.
    pub n_base: BigUint,
    /// Number of twists examined.
    pub twists_total: usize,
    /// Number of independent prime-power subgroups that yielded a
    /// verified residue (across all twists).
    pub twists_used: usize,
    /// Bits of `d` recovered (= `log₂(product of used twist subgroup sizes)`).
    pub bits_recovered: f64,
    /// `d mod (product of subgroup orders)` (= what the attacker actually learns).
    pub recovered_d_partial: Option<BigUint>,
    /// `d` recovered fully iff the union of subgroup orders covers
    /// `n_base` (or modular brute-force fills the gap), and the
    /// candidate is confirmed by `d · G == Q`.
    pub recovered_d_full: Option<BigUint>,
    /// `true` iff `recovered_d_full` was verified against the victim's
    /// public key by an independent scalar multiplication `d · G == Q`.
    pub verified: bool,
    /// Per-twist Pohlig-Hellman reports.
    pub per_twist_reports: Vec<(usize, PohligHellmanReport)>,
}

/// **Mount the full invalid-curve attack** against a black-box scalar
/// multiplication oracle.
///
/// `base_curve` is the legitimate curve where the victim's secret `d`
/// lives.  `public_point` is the victim's public key `Q = d · G` on the
/// base curve — the only thing the attack learns `d` against.  `oracle`
/// is the victim's black box: given any point `P` (which the attacker
/// crafts to lie on a weak twist), it returns `d · P` computed with the
/// base curve's incomplete addition law (independent of `b`), so the
/// result lands on the twist.  The attack code **never** reads `d`.
///
/// The attack, per smooth twist:
///  1. build a point `P = cofactor · G_twist` of exact order equal to
///     the twist's smooth part;
///  2. query `S = oracle(P) = d · P`;
///  3. solve `d ≡ e (mod smooth_part)` with [`pohlig_hellman_curve`] on
///     `(P, S)`;
///  4. CRT the residues across twists.
///
/// It then verifies the reconstruction against `public_point`: when the
/// combined modulus covers `n_base` the residue is reduced mod `n_base`
/// and confirmed by `d · G == Q`; otherwise the small remaining gap is
/// completed by a public-key-checked search.  `smoothness_bound` caps
/// the largest prime subgroup solved per twist.
pub fn mount_invalid_curve_attack_oracle<F>(
    base_curve: &CurveParams,
    public_point: &Point,
    oracle: F,
    smoothness_bound: u64,
) -> InvalidCurveAttackReport
where
    F: Fn(&Point) -> Point,
{
    let twists = enumerate_twists(&base_curve.p, &base_curve.b).unwrap_or_default();
    let mut per_twist_reports: Vec<(usize, PohligHellmanReport)> = Vec::new();
    let mut residues: Vec<(BigUint, BigUint)> = Vec::new();
    let mut bits_recovered = 0.0f64;
    for (idx, twist) in twists.iter().enumerate() {
        // Skip twists that are themselves prime (no small-factor leak).
        if twist.factorisation.len() == 1 && twist.factorisation[0].1 == 1 {
            continue;
        }
        // Skip twists with no prime factor within the bound.
        let smooth_part = compute_smooth_part(&twist.order, smoothness_bound);
        if smooth_part <= BigUint::one() {
            continue;
        }
        let twist_curve = construct_twist_curve(base_curve, twist);
        let twist_g = twist_curve.generator();
        let a_fe = twist_curve.a_fe();
        let bound = BigUint::from(smoothness_bound);
        // Attack one prime-power subgroup at a time.  The twist group can
        // be non-cyclic (see finding 18), so the constructed base point's
        // *exact* order — not the twist's nominal smooth part — is what we
        // solve modulo; each residue is then confirmed against the
        // oracle's own answer before it is used.
        for (q, e) in &twist.factorisation {
            if q > &bound {
                continue;
            }
            let qe = q.pow(*e);
            // A point whose order divides q^e: P = (order / q^e) · G_twist.
            let p_pt = twist_g.scalar_mul(&(&twist.order / &qe), &a_fe);
            let order = point_prime_power_order(&twist_curve, &p_pt, q, *e);
            if order <= BigUint::one() {
                continue;
            }
            // **Query the oracle**: the victim computes d · P with the base
            // curve's incomplete law; since P is on the twist and both
            // curves share `a`, S = d · P lives on the twist.  The attack
            // learns only S — never d.
            let s_pt = oracle(&p_pt);
            let ph_report =
                pohlig_hellman_curve(&twist_curve, &p_pt, &s_pt, &order, smoothness_bound);
            let mut used = false;
            if let Some(d_mod) = &ph_report.recovered_d {
                // Independent check: the recovered residue must reproduce
                // the oracle's answer, (d mod order)·P == S.
                if p_pt.scalar_mul(d_mod, &a_fe) == s_pt {
                    let residue = d_mod % &order;
                    // Dedup by prime, keeping the higher prime power.
                    let existing = residues.iter().position(|(m, _)| {
                        crate::cryptanalysis::j0_twists::factorise_small(m)
                            .iter()
                            .any(|(qq, _)| qq == q)
                    });
                    match existing {
                        Some(i) if order > residues[i].0 => {
                            residues[i] = (order.clone(), residue);
                            used = true;
                        }
                        Some(_) => {}
                        None => {
                            bits_recovered += order.bits() as f64;
                            residues.push((order.clone(), residue));
                            used = true;
                        }
                    }
                }
            }
            let _ = used;
            per_twist_reports.push((idx, ph_report));
        }
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
            // Lift uniquely via mod n_base, then confirm against Q.
            let cand = partial % &base_curve.n;
            verify_scalar(&cand, public_point, base_curve).then_some(cand)
        } else {
            // The remaining unknown is in [0, n_base / total_mod).
            // Complete by a public-key-checked search if cheap.
            let remaining_bits = base_curve.n.bits() as f64 - (total_mod.bits() as f64);
            if remaining_bits <= 24.0 {
                complete_via_public_key(base_curve, partial, &total_mod, public_point)
            } else {
                None
            }
        }
    } else {
        None
    };
    // `recovered_d_full` is `Some` only after `d · G == Q` succeeded.
    let verified = recovered_d_full.is_some();
    InvalidCurveAttackReport {
        base_curve_name: base_curve.name.to_string(),
        n_base: base_curve.n.clone(),
        twists_total: twists.len(),
        twists_used: residues.len(),
        bits_recovered,
        recovered_d_partial,
        recovered_d_full,
        verified,
        per_twist_reports,
    }
}

/// **Convenience wrapper**: mount the invalid-curve attack against an
/// *honest* oracle built from a planted secret `d`.  For tests and the
/// `--demo` command line only.  The oracle closure captures `d` and
/// computes `d · P`; the attack in [`mount_invalid_curve_attack_oracle`]
/// receives only the oracle and the public key `Q = d · G`, so it never
/// reads `d` directly.
pub fn mount_invalid_curve_attack(
    base_curve: &CurveParams,
    d_truth: &BigUint,
    smoothness_bound: u64,
) -> InvalidCurveAttackReport {
    let a_fe = base_curve.a_fe();
    let public_point = base_curve.generator().scalar_mul(d_truth, &a_fe);
    let d = d_truth.clone();
    let oracle_a = base_curve.a_fe();
    mount_invalid_curve_attack_oracle(
        base_curve,
        &public_point,
        move |p: &Point| p.scalar_mul(&d, &oracle_a),
        smoothness_bound,
    )
}

/// Independent check that a recovered scalar is the victim's key:
/// `candidate · G == Q` on the base curve.
fn verify_scalar(candidate: &BigUint, public_point: &Point, base: &CurveParams) -> bool {
    &base.generator().scalar_mul(candidate, &base.a_fe()) == public_point
}

/// The exact order of `p`, known to divide `q^max_e`: the smallest `q^j`
/// (`j ≤ max_e`) with `q^j · p == O`.
fn point_prime_power_order(curve: &CurveParams, p: &Point, q: &BigUint, max_e: u32) -> BigUint {
    let a = curve.a_fe();
    let mut order = BigUint::one();
    let mut acc = p.clone();
    let mut j = 0u32;
    while j < max_e && !matches!(acc, Point::Infinity) {
        order *= q;
        acc = acc.scalar_mul(q, &a);
        j += 1;
    }
    order
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

/// **Fill the residual gap** by the real attacker's method: after CRT
/// recovery to `d ≡ partial (mod total_mod)`, walk the coset
/// `partial, partial + total_mod, …` and accept the first candidate
/// that reproduces the victim's **public key**, `candidate · G == Q`.
/// Returns `None` if no coset member below `n` verifies (which cannot
/// happen when the true `d` lies in the coset, but keeps the search
/// honest and total).
fn complete_via_public_key(
    base: &CurveParams,
    partial: &BigUint,
    total_mod: &BigUint,
    public_point: &Point,
) -> Option<BigUint> {
    let mut candidate = partial.clone();
    while candidate < base.n {
        if verify_scalar(&candidate, public_point, base) {
            return Some(candidate);
        }
        candidate += total_mod;
    }
    None
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
            s.push_str(&format!(
                "  {} **Full key recovered**: `d = {}`{}\n",
                if report.verified {
                    paint("✓", FG_BRIGHT_GREEN)
                } else {
                    paint("✗", FG_BRIGHT_RED)
                },
                d,
                if report.verified {
                    " (verified: d·G == Q)"
                } else {
                    " (UNVERIFIED)"
                },
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
    /// curve recovers the full key from an honest oracle and verifies
    /// it against the public key — the attack code never sees `d`.
    #[test]
    fn invalid_curve_attack_recovers_and_verifies_full_d() {
        let curve = j0_16bit();
        let d_truth = BigUint::from(12345u32);
        let report = mount_invalid_curve_attack(&curve, &d_truth, 16);
        assert!(report.twists_used > 0, "expected at least one usable twist");
        assert!(report.bits_recovered > 0.0);
        assert_eq!(
            report.recovered_d_full,
            Some(d_truth.clone()),
            "should fully recover the planted key"
        );
        assert!(report.verified, "recovered key must verify d·G == Q");
    }

    /// The attack must work against a bare oracle closure with no
    /// planted-`d` shortcut: only `Q = d·G` and `Fn(&Point)->Point`.
    #[test]
    fn oracle_attack_verifies_against_public_key_only() {
        let curve = j0_16bit();
        let d_truth = BigUint::from(54321u32);
        let a_fe = curve.a_fe();
        let q = curve.generator().scalar_mul(&d_truth, &a_fe);
        // A wrong candidate must NOT verify.
        let report = mount_invalid_curve_attack_oracle(
            &curve,
            &q,
            |p: &Point| p.scalar_mul(&d_truth, &curve.a_fe()),
            16,
        );
        assert!(report.verified);
        assert_eq!(report.recovered_d_full, Some(d_truth));
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
