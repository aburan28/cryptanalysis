//! Concrete attack demonstrations for legacy low-security elliptic curves.
//!
//! These demos intentionally do **not** claim to solve a 56-, 64-, 76-,
//! 80-, or 96-bit generic ECDLP in a CI test.  Instead, they plant
//! deterministic reduced-size private scalars on the real legacy curve
//! parameters and recover them with baby-step giant-step (BSGS).  The
//! report records the successful recovery and the extrapolated generic
//! Pollard-rho cost for full-width uniformly random secrets.

use std::collections::HashMap;
use std::time::Instant;

use num_bigint::BigUint;

use crate::binary_ecc::curve::{
    point_add, point_neg, scalar_mul as binary_scalar_mul, BinaryCurve, BinaryPoint,
};
use crate::ecc::{CurveParams, Point};

/// Successful bounded discrete-log recovery on a real legacy curve.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct LegacyCurveAttackDemo {
    /// Human-readable curve/group name.
    pub curve: &'static str,
    /// Curve family, e.g. prime-field or binary-field.
    pub family: &'static str,
    /// Attack method used by this demo.
    pub attack: &'static str,
    /// Deterministic planted scalar.
    pub secret: u64,
    /// Scalar recovered by the attack.
    pub recovered: u64,
    /// Exclusive scalar search bound.
    pub bound: u64,
    /// Baby-step table size.
    pub baby_steps: u64,
    /// Giant steps attempted before success.
    pub giant_steps: u64,
    /// Number of point additions in the BSGS walk.
    pub point_additions: u64,
    /// Wall-clock runtime in microseconds.
    pub elapsed_us: u128,
    /// Nominal generic Pollard-rho security for full-width random scalars.
    pub generic_rho_bits: u64,
    /// Curve cofactor.
    pub cofactor: String,
    /// What this demo proves.
    pub proof_scope: &'static str,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct BoundedDlpSolution {
    pub x: u64,
    pub baby_steps: u64,
    pub giant_steps: u64,
    pub point_additions: u64,
}

/// Run the focused legacy-curve attack demonstration suite.
///
/// The first nine entries are the newly added low-security curves:
/// secp112r1/r2, sect113r1/r2, secp128r1/r2, sect131r1/r2, and
/// IKE/Oakley Group 3.  The remaining entries cover the prior legacy
/// batch where they are cheap enough to include.
pub fn run_legacy_curve_attack_demos() -> Vec<LegacyCurveAttackDemo> {
    let mut out = Vec::new();

    for (curve, secret, bound) in [
        (CurveParams::secp112r1(), 0x1234u64, 1u64 << 16),
        (CurveParams::secp112r2(), 0x2345u64, 1u64 << 16),
        (CurveParams::secp128r1(), 0x3456u64, 1u64 << 16),
        (CurveParams::secp128r2(), 0x4567u64, 1u64 << 16),
        (CurveParams::secp160k1(), 0x5678u64, 1u64 << 16),
        (CurveParams::secp160r1(), 0x6789u64, 1u64 << 16),
        (CurveParams::secp160r2(), 0x789au64, 1u64 << 16),
        (CurveParams::p192(), 0x89abu64, 1u64 << 16),
    ] {
        out.push(prime_curve_demo(curve, secret, bound));
    }

    for (name, curve, secret, bound) in [
        ("sect113r1", BinaryCurve::sect113r1(), 0x1357u64, 1u64 << 16),
        ("sect113r2", BinaryCurve::sect113r2(), 0x2468u64, 1u64 << 16),
        ("sect131r1", BinaryCurve::sect131r1(), 0x3579u64, 1u64 << 16),
        ("sect131r2", BinaryCurve::sect131r2(), 0x468au64, 1u64 << 16),
        (
            "ike-oakley-group3",
            BinaryCurve::ike_oakley_group3(),
            0x579bu64,
            1u64 << 16,
        ),
        ("sect163k1", BinaryCurve::sect163k1(), 0x68acu64, 1u64 << 16),
        ("sect163r1", BinaryCurve::sect163r1(), 0x79bdu64, 1u64 << 16),
        ("sect163r2", BinaryCurve::sect163r2(), 0x8aceu64, 1u64 << 16),
    ] {
        out.push(binary_curve_demo(name, curve, secret, bound));
    }

    out
}

/// Render a human-readable Markdown report for the legacy-curve demos.
pub fn legacy_curve_attack_report(demos: &[LegacyCurveAttackDemo]) -> String {
    let mut out = String::new();
    out.push_str("# Legacy Curve Attack Demonstrations\n\n");
    out.push_str(
        "This report demonstrates concrete secret recovery on the newly added legacy low-security curves. Each row uses the real curve parameters and generator, plants a deterministic reduced-size scalar, computes Q = d*G, and recovers d with bounded baby-step giant-step.\n\n",
    );
    out.push_str(
        "The result is a successful attack on implementations that use low-entropy or otherwise bounded private scalars on these curves. It does not pretend that a full 2^56, 2^64, 2^76, 2^80, or 2^96 generic ECDLP completes in a normal test run; the full-width estimate column gives the expected Pollard-rho scale.\n\n",
    );
    out.push_str("| curve/group | family | secret | recovered | bound | BSGS additions | time | full-width generic rho |\n");
    out.push_str("|---|---|---:|---:|---:|---:|---:|---|\n");
    for d in demos {
        out.push_str(&format!(
            "| {} | {} | {} | {} | 2^{} | {} | {} us | approx 2^{} group ops |\n",
            d.curve,
            d.family,
            d.secret,
            d.recovered,
            d.bound.ilog2(),
            d.point_additions,
            d.elapsed_us,
            d.generic_rho_bits
        ));
    }
    out.push_str("\n## Caveats\n\n");
    out.push_str(
        "- The BSGS runs are exact recoveries for the planted bounded scalars shown above.\n",
    );
    out.push_str("- Full-width uniformly random scalars on these curves remain generic-DLP problems at the listed Pollard-rho scale; that scale is too large for CI.\n");
    out.push_str("- Cofactor-bearing curves still require subgroup validation in protocols. This demo focuses on bounded-secret recovery because it is deterministic and applies uniformly across the added curve implementations.\n");
    out
}

/// Solve `target = x*G` for `x in [0, bound)` on a prime-field curve.
pub fn bounded_bsgs_prime(
    curve: &CurveParams,
    target: &Point,
    bound: u64,
) -> Option<BoundedDlpSolution> {
    if bound == 0 {
        return None;
    }

    let m = integer_sqrt_ceil(bound);
    let g = curve.generator();
    let a = curve.a_fe();
    let mut table = HashMap::with_capacity((m + 1) as usize);

    let mut baby = Point::Infinity;
    for j in 0..=m {
        table.entry(prime_point_key(&baby)).or_insert(j);
        baby = baby.add(&g, &a);
    }

    let giant = g.scalar_mul(&BigUint::from(m), &a).neg();
    let mut current = target.clone();
    for i in 0..=m {
        if let Some(&j) = table.get(&prime_point_key(&current)) {
            let candidate = i.checked_mul(m)?.checked_add(j)?;
            if candidate < bound {
                return Some(BoundedDlpSolution {
                    x: candidate,
                    baby_steps: m + 1,
                    giant_steps: i + 1,
                    point_additions: (m + 1) + i,
                });
            }
        }
        current = current.add(&giant, &a);
    }

    None
}

/// Solve `target = x*G` for `x in [0, bound)` on a binary-field curve.
pub fn bounded_bsgs_binary(
    curve: &BinaryCurve,
    target: &BinaryPoint,
    bound: u64,
) -> Option<BoundedDlpSolution> {
    if bound == 0 {
        return None;
    }

    let m = integer_sqrt_ceil(bound);
    let mut table = HashMap::with_capacity((m + 1) as usize);

    let mut baby = BinaryPoint::Infinity;
    for j in 0..=m {
        table.entry(binary_point_key(&baby)).or_insert(j);
        baby = point_add(curve, &baby, &curve.generator);
    }

    let step = binary_scalar_mul(curve, &curve.generator, &BigUint::from(m));
    let neg_step = point_neg(&step);
    let mut current = target.clone();
    for i in 0..=m {
        if let Some(&j) = table.get(&binary_point_key(&current)) {
            let candidate = i.checked_mul(m)?.checked_add(j)?;
            if candidate < bound {
                return Some(BoundedDlpSolution {
                    x: candidate,
                    baby_steps: m + 1,
                    giant_steps: i + 1,
                    point_additions: (m + 1) + i,
                });
            }
        }
        current = point_add(curve, &current, &neg_step);
    }

    None
}

fn prime_curve_demo(curve: CurveParams, secret: u64, bound: u64) -> LegacyCurveAttackDemo {
    let a = curve.a_fe();
    let target = curve.generator().scalar_mul(&BigUint::from(secret), &a);
    let t0 = Instant::now();
    let solution = bounded_bsgs_prime(&curve, &target, bound)
        .expect("bounded BSGS should recover planted scalar");
    let elapsed_us = t0.elapsed().as_micros();

    LegacyCurveAttackDemo {
        curve: curve.name,
        family: "prime-field",
        attack: "bounded BSGS",
        secret,
        recovered: solution.x,
        bound,
        baby_steps: solution.baby_steps,
        giant_steps: solution.giant_steps,
        point_additions: solution.point_additions,
        elapsed_us,
        generic_rho_bits: curve.n.bits() / 2,
        cofactor: curve.h.to_string(),
        proof_scope: "recovers bounded private scalars on the real curve",
    }
}

fn binary_curve_demo(
    name: &'static str,
    curve: BinaryCurve,
    secret: u64,
    bound: u64,
) -> LegacyCurveAttackDemo {
    let target = binary_scalar_mul(&curve, &curve.generator, &BigUint::from(secret));
    let t0 = Instant::now();
    let solution = bounded_bsgs_binary(&curve, &target, bound)
        .expect("bounded BSGS should recover planted scalar");
    let elapsed_us = t0.elapsed().as_micros();

    LegacyCurveAttackDemo {
        curve: name,
        family: "binary-field",
        attack: "bounded BSGS",
        secret,
        recovered: solution.x,
        bound,
        baby_steps: solution.baby_steps,
        giant_steps: solution.giant_steps,
        point_additions: solution.point_additions,
        elapsed_us,
        generic_rho_bits: curve.order.bits() / 2,
        cofactor: curve.cofactor.to_string(),
        proof_scope: "recovers bounded private scalars on the real curve",
    }
}

fn integer_sqrt_ceil(n: u64) -> u64 {
    if n <= 1 {
        return n;
    }
    let mut lo = 1u64;
    let mut hi = 1u64 << 32;
    while lo < hi {
        let mid = lo + (hi - lo) / 2;
        if mid >= n / mid && (n.is_multiple_of(mid) || mid > n / mid) {
            hi = mid;
        } else {
            lo = mid + 1;
        }
    }
    lo
}

fn prime_point_key(p: &Point) -> Vec<u8> {
    match p {
        Point::Infinity => vec![0],
        Point::Affine { x, y } => {
            let mut out = Vec::new();
            out.push(1);
            let xb = x.value.to_bytes_be();
            let yb = y.value.to_bytes_be();
            out.extend_from_slice(&(xb.len() as u32).to_be_bytes());
            out.extend_from_slice(&xb);
            out.extend_from_slice(&(yb.len() as u32).to_be_bytes());
            out.extend_from_slice(&yb);
            out
        }
    }
}

fn binary_point_key(p: &BinaryPoint) -> Vec<u8> {
    match p {
        BinaryPoint::Infinity => vec![0],
        BinaryPoint::Affine { x, y } => {
            let mut out = Vec::new();
            out.push(1);
            let xb = x.to_biguint().to_bytes_be();
            let yb = y.to_biguint().to_bytes_be();
            out.extend_from_slice(&(xb.len() as u32).to_be_bytes());
            out.extend_from_slice(&xb);
            out.extend_from_slice(&(yb.len() as u32).to_be_bytes());
            out.extend_from_slice(&yb);
            out
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn legacy_curve_attack_demo_recovers_latest_added_scalars() {
        let demos = run_legacy_curve_attack_demos();
        for name in [
            "secp112r1",
            "secp112r2",
            "secp128r1",
            "secp128r2",
            "sect113r1",
            "sect113r2",
            "sect131r1",
            "sect131r2",
            "ike-oakley-group3",
        ] {
            let demo = demos
                .iter()
                .find(|d| d.curve == name)
                .expect("missing demo");
            assert_eq!(demo.secret, demo.recovered, "{} recovery failed", name);
            assert!(
                demo.recovered < demo.bound,
                "{} recovered out of bound",
                name
            );
        }
    }

    #[test]
    fn legacy_curve_attack_demo_includes_prior_batch_when_cheap() {
        let demos = run_legacy_curve_attack_demos();
        for name in [
            "secp160k1",
            "secp160r1",
            "secp160r2",
            "P-192",
            "sect163k1",
            "sect163r1",
            "sect163r2",
        ] {
            let demo = demos
                .iter()
                .find(|d| d.curve == name)
                .expect("missing demo");
            assert_eq!(demo.secret, demo.recovered, "{} recovery failed", name);
        }
    }

    #[test]
    fn bounded_bsgs_rejects_missing_scalar() {
        let curve = CurveParams::secp112r1();
        let a = curve.a_fe();
        let target = curve.generator().scalar_mul(&BigUint::from(500u32), &a);
        assert!(bounded_bsgs_prime(&curve, &target, 128).is_none());
    }

    #[test]
    fn report_contains_successful_recovery_scope() {
        let demos = run_legacy_curve_attack_demos();
        let report = legacy_curve_attack_report(&demos);
        assert!(report.contains("secp112r1"));
        assert!(report.contains("ike-oakley-group3"));
        assert!(report.contains("bounded baby-step giant-step"));
        assert!(report.contains("does not pretend"));
    }
}
