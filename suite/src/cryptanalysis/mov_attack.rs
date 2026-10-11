//! **MOV / Frey-Rück attack** on ECDLP via pairing reduction.
//!
//! Menezes-Okamoto-Vanstone (IEEE Trans IT 1993) and Frey-Rück
//! (Math. Comp. 1994) independently showed that ECDLP on a curve
//! `E(F_p)` can be **reduced** to discrete log in the multiplicative
//! group `F_{p^k}*` via a pairing (Weil for MOV, Tate for Frey-Rück),
//! where `k` is the **embedding degree** — the smallest integer
//! such that `n | p^k − 1` where `n = ord(G)`.
//!
//! ## Threat model
//!
//! Given `Q = d·G` on `E(F_p)` with `ord(G) = n`:
//!
//! 1. Find an auxiliary point `R ∈ E[n]` such that `e_n(G, R) ≠ 1`,
//!    where `e_n` is the Weil pairing (a non-degenerate bilinear map
//!    `E[n] × E[n] → μ_n ⊂ F_{p^k}*`).
//! 2. Compute `α = e_n(G, R)` and `β = e_n(Q, R)`.
//! 3. By bilinearity, `β = α^d`, so `d` is the discrete log of `β`
//!    base `α` in `F_{p^k}*`.
//! 4. Solve that DLP using Pollard-rho or index calculus on `F_{p^k}*`.
//!
//! **The reduction is only useful when `k` is small.**  For random
//! curves over a typical prime `p`, the expected `k` is `≈ ord(G)`
//! itself — useless.  But for:
//!
//! - **Supersingular curves**: `k ∈ {1, 2, 3, 4, 6}` (Menezes 1993
//!   gave the classification).  `k = 2` is the most common.
//! - **Anomalous curves** (`#E = p`): different attack vector
//!   (`cryptanalysis::canonical_lift`).
//! - **Curves with small `k` by construction** (paired BLS12-381 has
//!   `k = 12` deliberately — but `p^12` is still huge, so the
//!   reduction is to a 2048-bit prime field where IC kicks in).
//!
//! ## What this module ships
//!
//! - [`embedding_degree`] — compute the smallest `k` with `n | p^k − 1`.
//! - [`mov_attack_supersingular_k2`] — MOV reduction on a curve with
//!   small embedding degree (`k ≤ 6`), returning the legacy
//!   [`MovAttackReport`].  It delegates to
//!   [`crate::cryptanalysis::weak_curves::mov::mov_attack`], which
//!   computes the **reduced Tate pairing by Miller's algorithm** over a
//!   genuine `F_{p^k} = F_p[t]/(f)` and solves the resulting DLP in the
//!   order-`n` subgroup of `F_{p^k}*` with BSGS / Pollard rho.
//! - [`MovAttackReport`] — structured outcome.
//! - [`format_visualization`] — Markdown attack report.
//!
//! Earlier versions used a "pseudo-pairing" `(x₁² + x₂) mod n`, which is
//! not bilinear, and a brute-force DLP in `(Z/n)*`; they could not
//! attack a real MOV-weak curve and have been removed.
//!
//! ## What this module does NOT ship
//!
//! - Index calculus / NFS in `F_{p^k}*`.  The transferred DLP is solved
//!   generically, so it costs `√n` just as Pollard rho on the curve
//!   does: the reduction is real, the speed-up needs a subexponential
//!   finite-field solver that is out of scope.
//!
//! ## References
//!
//! - **A. Menezes, T. Okamoto, S. A. Vanstone**, *Reducing elliptic
//!   curve logarithms to logarithms in a finite field*, IEEE Trans.
//!   IT 39 (1993).
//! - **G. Frey, H.-G. Rück**, *A remark concerning m-divisibility and
//!   the discrete logarithm in the divisor class group of curves*,
//!   Math. Comp. 62 (1994).
//! - **A. Menezes**, *An introduction to pairing-based cryptography*,
//!   2009 survey.

use crate::ecc::curve::CurveParams;
use crate::ecc::point::Point;
use num_bigint::BigUint;
use num_traits::Zero;

/// Find the **embedding degree** `k`: smallest `k ≥ 1` with
/// `n | p^k − 1`.  Capped at `max_k` (returns `None` if no `k ≤ max_k`
/// works — the curve is **MOV-secure** against attacks bounded by
/// `max_k`).
pub fn embedding_degree(p: &BigUint, n: &BigUint, max_k: u32) -> Option<u32> {
    crate::cryptanalysis::weak_curves::mov::embedding_degree(p, n, max_k)
}

/// Outcome of one MOV reduction.
#[derive(Clone, Debug)]
pub struct MovAttackReport {
    /// Curve name.
    pub curve_name: String,
    /// Embedding degree `k`.
    pub embedding_degree: u32,
    /// Subgroup order `n`.
    pub n: BigUint,
    /// Target field size `p^k`.
    pub target_field_size: BigUint,
    /// Recovered discrete log `d` (if successful).
    pub recovered_d: Option<BigUint>,
    /// Elapsed time in ms.
    pub elapsed_ms: u128,
    /// Whether the curve is MOV-secure under the chosen `max_k`.
    pub mov_secure_under_bound: bool,
}

/// **MOV attack** on a curve with small embedding degree (`k ≤ 6`;
/// supersingular curves over `F_p`, `p ≥ 5`, have `k = 2`).
///
/// Given `Q = d·G` with `ord(G) = n` prime, computes `α = t_n(G, R)` and
/// `β = t_n(Q, R)` with the reduced Tate pairing (Miller's algorithm,
/// real `F_{p^k}` arithmetic) for an independent `R ∈ E(F_{p^k})[n]`,
/// then solves `β = α^d` in the order-`n` subgroup of `F_{p^k}*`.  This
/// delegates to [`crate::cryptanalysis::weak_curves::mov::mov_attack`];
/// `recovered_d` is set only for a scalar verified by `d·G = Q`.
///
/// `#E(F_p)` (needed for `#E(F_{p^k})`) is taken from `curve.n ·
/// curve.h` when that is consistent, otherwise `p + 1` (the order of
/// every supersingular curve over `F_p`, `p ≥ 5`) is tried.  When
/// neither validates, or the DLP in `F_{p^k}*` is out of budget,
/// `recovered_d` is `None`.
pub fn mov_attack_supersingular_k2(
    curve: &CurveParams,
    g: &Point,
    q: &Point,
    n: &BigUint,
) -> MovAttackReport {
    use crate::cryptanalysis::weak_curves::mov::{mov_attack, MovOptions};
    let t0 = std::time::Instant::now();
    let p = &curve.p;
    let k = embedding_degree(p, n, 6).unwrap_or(0);
    let target = if k > 0 { p.pow(k) } else { BigUint::zero() };
    let mov_secure = k == 0;
    let mut found = None;
    if !mov_secure {
        let opts = MovOptions {
            max_k: 6,
            ..MovOptions::default()
        };
        let from_params = &curve.n * BigUint::from(curve.h);
        let candidates = [from_params, p + 1u32];
        for e_order in candidates.iter().filter(|c| !c.is_zero()) {
            if let Ok(out) = mov_attack(curve, g, q, n, e_order, &opts) {
                found = Some(out.scalar);
                break;
            }
        }
    }
    MovAttackReport {
        curve_name: curve.name.to_string(),
        embedding_degree: k,
        n: n.clone(),
        target_field_size: target,
        recovered_d: found,
        elapsed_ms: t0.elapsed().as_millis(),
        mov_secure_under_bound: mov_secure,
    }
}

/// Render a Markdown visualization of the MOV attack outcome.
pub fn format_visualization(report: &MovAttackReport) -> String {
    use crate::visualize::color::{paint, FG_BRIGHT_GREEN, FG_BRIGHT_YELLOW};
    let mut s = String::new();
    s.push_str("# MOV / Frey-Rück pairing reduction on ECDLP\n\n");
    s.push_str(&format!("**Curve**: `{}`\n\n", report.curve_name));
    s.push_str(&format!(
        "**Subgroup order `n`**: {} ({} bits)\n\n",
        report.n,
        report.n.bits()
    ));
    s.push_str(&format!(
        "**Embedding degree `k`** (smallest with `n | p^k − 1`): {}\n\n",
        report.embedding_degree
    ));
    if report.mov_secure_under_bound {
        s.push_str(&format!(
            "{} **MOV-secure**: no `k ≤ 6` satisfies the embedding condition; \
             pairing reduction does not give a usable smaller group.\n",
            paint("✓", FG_BRIGHT_GREEN)
        ));
        return s;
    }
    s.push_str(&format!(
        "**Target field `F_{{p^{}}}`**: order ≈ 2^{} bits — substantially smaller than `n` ⇒ MOV reduction is useful.\n\n",
        report.embedding_degree,
        report.target_field_size.bits()
    ));
    s.push_str("## Reduction chain\n\n");
    s.push_str("```\n");
    s.push_str("   ECDLP on E(F_p)                                       \n");
    s.push_str("        │                                                 \n");
    s.push_str("        │  pairing e_n(·, ·) : E[n] × E[n] → μ_n ⊂ F_{p^k}\n");
    s.push_str("        ▼                                                 \n");
    s.push_str("   DLP in the order-n subgroup of F_{p^k}*                \n");
    s.push_str("        │                                                 \n");
    s.push_str("        │  BSGS / Pollard rho (index calculus: not impl.) \n");
    s.push_str("        ▼                                                 \n");
    s.push_str("   recover d                                              \n");
    s.push_str("```\n\n");
    match &report.recovered_d {
        Some(d) => s.push_str(&format!(
            "  {} **`d = {}` recovered in {} ms**\n",
            paint("✓", FG_BRIGHT_GREEN),
            d,
            report.elapsed_ms
        )),
        None => s.push_str(&format!(
            "  {} **no verified `d`**: the pairing transfer or the `F_{{p^k}}*` DLP did not succeed within budget (or `#E(F_p)` could not be validated).\n",
            paint("⚠", FG_BRIGHT_YELLOW)
        )),
    }
    s
}

// ── Tests ────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    /// `embedding_degree` for a curve with `n | p − 1` returns 1
    /// (degenerate case — pairing reduces to F_p).
    #[test]
    fn embedding_degree_k1() {
        // p = 19, n = 6: 6 | 18 = p - 1, so k = 1.
        let p = BigUint::from(19u32);
        let n = BigUint::from(6u32);
        assert_eq!(embedding_degree(&p, &n, 6), Some(1));
    }

    /// Generic curve with `k > 6`: function returns `None` (MOV-secure
    /// for the chosen bound).
    #[test]
    fn embedding_degree_none_for_large_k() {
        // n a large prime that doesn't divide p^k - 1 for small k.
        let p = BigUint::from(101u32);
        let n = BigUint::from(97u32);
        assert!(embedding_degree(&p, &n, 6).is_none());
    }

    /// **Real curve** with a small embedding degree — the canonical
    /// supersingular example `p = 23`, curve `y² = x³ + 1`, `n = 4`.
    #[test]
    fn embedding_degree_supersingular_p23() {
        let p = BigUint::from(23u32);
        let n = BigUint::from(4u32);
        // 4 | 23 - 1 = 22?  22 / 4 = 5.5, no.
        // 4 | 23² - 1 = 528?  528 / 4 = 132, yes.  So k = 2.
        assert_eq!(embedding_degree(&p, &n, 6), Some(2));
    }

    /// **MOV report renders** with all the structural sections.
    #[test]
    fn mov_report_renders() {
        // Synthetic report.
        let report = MovAttackReport {
            curve_name: "test".into(),
            embedding_degree: 2,
            n: BigUint::from(199u32),
            target_field_size: BigUint::from(44521u32),
            recovered_d: Some(BigUint::from(42u32)),
            elapsed_ms: 5,
            mov_secure_under_bound: false,
        };
        let s = format_visualization(&report);
        assert!(s.contains("MOV"));
        assert!(s.contains("k = 2") || s.contains("Embedding degree `k`"));
        assert!(s.contains("d = 42"));
    }

    /// **MOV-secure curve renders the secure banner**.
    #[test]
    fn mov_secure_curve_emits_warning() {
        let report = MovAttackReport {
            curve_name: "test".into(),
            embedding_degree: 0,
            n: BigUint::from(199u32),
            target_field_size: BigUint::zero(),
            recovered_d: None,
            elapsed_ms: 1,
            mov_secure_under_bound: true,
        };
        let s = format_visualization(&report);
        assert!(s.contains("MOV-secure"));
    }

    /// The 199-order curve `y² = x³ + 2` over `F_211` is *ordinary*
    /// with a large embedding degree (199 ∤ 211^k − 1 for k ≤ 6), so the
    /// MOV reduction does not apply and nothing is recovered.  (This
    /// test used to run a surrogate "pairing" and assert nothing.)
    #[test]
    fn mov_attack_runs_on_test_curve() {
        let curve = CurveParams {
            name: "mov-test-199",
            p: BigUint::from(211u32),
            a: BigUint::zero(),
            b: BigUint::from(2u32),
            gx: BigUint::from(4u32),
            gy: BigUint::from(53u32),
            n: BigUint::from(199u32),
            h: 1,
        };
        let g = curve.generator();
        let a_fe = curve.a_fe();
        let d_truth = BigUint::from(13u32);
        let q = g.scalar_mul(&d_truth, &a_fe);
        let report = mov_attack_supersingular_k2(&curve, &g, &q, &curve.n);
        assert!(report.mov_secure_under_bound);
        assert_eq!(report.recovered_d, None);
    }

    /// **Real MOV reduction** on the supersingular curve `y² = x³ + x`
    /// over `p = 4·h·n − 1 ≡ 3 (mod 4)` (so `#E = p + 1`, `k = 2`) with
    /// a 20-bit prime `n`: the Tate pairing moves the DLP to `F_{p²}*`
    /// and the recovered `d` is checked.
    #[test]
    fn mov_attack_recovers_d_on_supersingular_curve() {
        use crate::cryptanalysis::weak_curves::arith::{is_probable_prime, AffinePoint, Ec};
        use num_traits::One;
        let n = BigUint::from(1_048_583u32); // prime
        assert!(is_probable_prime(&n));
        let (p, h) = (1u32..)
            .map(|h| (&n * BigUint::from(4 * h) - 1u32, h))
            .find(|(p, _)| p.bits() > 40 && is_probable_prime(p))
            .unwrap();
        let ec = Ec::new(&p, &BigUint::one(), &BigUint::zero());
        let mut rng = crate::cryptanalysis::weak_curves::arith::seeded_rng(1);
        let g = loop {
            let r = ec.mul(&ec.random_point(&mut rng), &BigUint::from(4 * h));
            if r != AffinePoint::Infinity {
                break r;
            }
        };
        let AffinePoint::Affine(gx, gy) = g else {
            unreachable!()
        };
        let curve = CurveParams {
            name: "supersingular-k2",
            p: p.clone(),
            a: BigUint::one(),
            b: BigUint::zero(),
            gx,
            gy,
            n: n.clone(),
            h: 4 * h,
        };
        let g = curve.generator();
        let d_truth = BigUint::from(777_777u32);
        let q = g.scalar_mul(&d_truth, &curve.a_fe());
        let report = mov_attack_supersingular_k2(&curve, &g, &q, &n);
        assert_eq!(report.embedding_degree, 2);
        assert!(!report.mov_secure_under_bound);
        assert_eq!(report.recovered_d, Some(d_truth));
    }

    /// **Demo emission**: visualize the report under `--nocapture`.
    #[test]
    #[ignore]
    fn demo_mov_visualization() {
        let report = MovAttackReport {
            curve_name: "mov-demo".into(),
            embedding_degree: 2,
            n: BigUint::from(199u32),
            target_field_size: BigUint::from(44521u32),
            recovered_d: Some(BigUint::from(13u32)),
            elapsed_ms: 3,
            mov_secure_under_bound: false,
        };
        println!("{}", format_visualization(&report));
    }
}
