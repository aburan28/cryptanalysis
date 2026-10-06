//! Probe the secp256k1 LLL-degeneracy phenomenon observed during
//! the GLV-HNP Phase 1.5 work.
//!
//! ## Observation
//!
//! With k_bits = 192 (64-bit nonce bias) and m = 8 signatures:
//!
//! - On NIST P-256: LLL converges to the correct key in ~1 second.
//! - On secp256k1: LLL hits its iteration cap across every random
//!   seed we tried.
//!
//! This probe runs a small, fast head-to-head comparison so the
//! difference is empirically documented.  Full BKZ/parameter
//! sweeps are deferred to the longer-running `#[ignore]`'d probe
//! version (commented out at the bottom).
//!
//! Run with:
//!   cargo test --test lll_degeneracy_probe -- --nocapture

use std::time::Instant;

use cryptanalysis_suite::cryptanalysis::hnp_ecdsa::{
    hnp_recover_key_with_reduction, BiasedSignature, HnpReduction,
};
use cryptanalysis_suite::ecc::curve::CurveParams;
use cryptanalysis_suite::ecc::keys::EccKeyPair;
use cryptanalysis_suite::ecc::point::Point;
use cryptanalysis_suite::utils::mod_inverse;
use num_bigint::{BigUint, RandBigInt};
use num_traits::Zero;
use rand::rngs::StdRng;
use rand::{RngCore, SeedableRng};

fn generate_biased_sigs(
    curve: &CurveParams,
    d: &BigUint,
    k_bits: u32,
    count: usize,
    k_seed: u64,
) -> Vec<BiasedSignature> {
    let n = &curve.n;
    let mut rng = StdRng::seed_from_u64(k_seed);
    let mut z_seed: u64 = 0xDEAD_BEEF;
    let mut sigs = Vec::with_capacity(count);

    while sigs.len() < count {
        let bytes_count = k_bits.div_ceil(8) as usize;
        let mut buf = vec![0u8; bytes_count];
        rng.fill_bytes(&mut buf);
        let extra = (bytes_count as u32) * 8 - k_bits;
        if extra > 0 {
            buf[0] &= 0xff >> extra;
        }
        let k = BigUint::from_bytes_be(&buf);
        if k.is_zero() {
            continue;
        }

        let z = BigUint::from(z_seed) % n;
        z_seed = z_seed.wrapping_add(0x9E37_79B9_7F4A_7C15);

        let g = curve.generator();
        let a_fe = curve.a_fe();
        let kg = g.scalar_mul(&k, &a_fe);
        let x1 = match &kg {
            Point::Affine { x, .. } => x.value.clone(),
            Point::Infinity => continue,
        };
        let r = &x1 % n;
        if r.is_zero() {
            continue;
        }
        let rd = (&r * d) % n;
        let z_plus_rd = (&z + &rd) % n;
        let k_inv = match mod_inverse(&k, n) {
            Some(v) => v,
            None => continue,
        };
        let s = (&k_inv * &z_plus_rd) % n;
        if s.is_zero() {
            continue;
        }

        sigs.push(BiasedSignature { r, s, z, k_bits });
    }
    sigs
}

fn probe_once_ext(
    curve: &CurveParams,
    curve_name: &str,
    k_bits: u32,
    m: usize,
    d_seed: u64,
    k_seed: u64,
    reduction: HnpReduction,
) -> (String, u128) {
    let n = curve.n.clone();
    let mut d_rng = StdRng::seed_from_u64(d_seed);
    let d = d_rng.gen_biguint_below(&n);
    let kp = EccKeyPair::from_private(d.clone(), curve);

    let sigs = generate_biased_sigs(curve, &d, k_bits, m, k_seed);

    let reduction_label = match &reduction {
        HnpReduction::Lll => "LLL".to_string(),
        HnpReduction::LllHp => "LLL-HP".to_string(),
        HnpReduction::Bkz(b) => format!("BKZ-{}", b),
    };

    let t0 = Instant::now();
    let result = hnp_recover_key_with_reduction(curve, &kp.public, &sigs, reduction);
    let elapsed = t0.elapsed().as_millis();

    let outcome = match result {
        Ok(recovered) if recovered == d => "✓ RECOVERED".to_string(),
        Ok(_) => "✗ WRONG KEY".to_string(),
        Err(e) => format!("✗ {}", e),
    };
    eprintln!(
        "{:<10} k_bits={:>3} m={:>2} reduction={:<8} d_seed=0x{:08X}  →  {:<40}  ({} ms)",
        curve_name, k_bits, m, reduction_label, d_seed, outcome, elapsed
    );
    (outcome, elapsed)
}

fn probe_once(
    curve: &CurveParams,
    curve_name: &str,
    k_bits: u32,
    m: usize,
    d_seed: u64,
    k_seed: u64,
) -> (String, u128) {
    let n = curve.n.clone();
    let mut d_rng = StdRng::seed_from_u64(d_seed);
    let d = d_rng.gen_biguint_below(&n);
    let kp = EccKeyPair::from_private(d.clone(), curve);

    let sigs = generate_biased_sigs(curve, &d, k_bits, m, k_seed);

    let t0 = Instant::now();
    let result = hnp_recover_key_with_reduction(curve, &kp.public, &sigs, HnpReduction::Lll);
    let elapsed = t0.elapsed().as_millis();

    let outcome = match result {
        Ok(recovered) if recovered == d => "✓ RECOVERED".to_string(),
        Ok(_) => "✗ WRONG KEY".to_string(),
        Err(e) => format!("✗ {}", e),
    };
    eprintln!(
        "{:<10} k_bits={:>3} m={:>2} d_seed=0x{:08X} k_seed=0x{:08X}  →  {:<40}  ({} ms)",
        curve_name, k_bits, m, d_seed, k_seed, outcome, elapsed
    );
    (outcome, elapsed)
}

#[test]
fn probe_lll_degeneracy_head_to_head() {
    let secp = CurveParams::secp256k1();
    let p256 = CurveParams::p256();

    eprintln!();
    eprintln!("=== LLL convergence: secp256k1 vs P-256 (k_bits=192, m=8) ===");

    let seeds: [(u64, u64); 3] = [
        (0xC0FFEE, 0xC0FFEE),
        (0xDEAD_BEEF, 0x0BAD_CAFE),
        (0x1234_5678, 0x9ABC_DEF0),
    ];

    let mut secp_pass = 0;
    let mut p256_pass = 0;

    for (d_seed, k_seed) in seeds {
        let (out_p, _) = probe_once(&p256, "P-256", 192, 8, d_seed, k_seed);
        if out_p.starts_with("✓") {
            p256_pass += 1;
        }
        let (out_s, _) = probe_once(&secp, "secp256k1", 192, 8, d_seed, k_seed);
        if out_s.starts_with("✓") {
            secp_pass += 1;
        }
    }

    eprintln!();
    eprintln!("=== Summary ===");
    eprintln!(
        "P-256:     {}/{} probes recovered key",
        p256_pass,
        seeds.len()
    );
    eprintln!(
        "secp256k1: {}/{} probes recovered key",
        secp_pass,
        seeds.len()
    );

    assert!(
        p256_pass + secp_pass > 0,
        "expected at least some LLL convergence; got 0 for both curves"
    );
}

/// Confirm that the scaled-f64 GS overflow fix resolves LLL degeneracy for
/// 384-bit curves across 3 independent seeds.
///
/// Prior result (2026-05-22): P-384 and brainpoolP384r1 recovered with seed
/// 0xC0FFEE only (1-of-3). This test runs the remaining 2 seeds to confirm
/// 3-of-3 for each curve.
///
/// Run: `cargo test --test lll_degeneracy_probe probe_384bit -- --nocapture`
#[test]
fn probe_384bit_lll_multiseed() {
    let p384 = CurveParams::p384();
    let bp384 = CurveParams::brainpool_p384r1();

    eprintln!();
    eprintln!("=== 384-bit LLL convergence: P-384 and brainpoolP384r1 (k_bits=288, m=8) ===");

    // Three independent (d_seed, k_seed) pairs
    let seeds: [(u64, u64); 3] = [
        (0xC0FFEE, 0xC0FFEE),
        (0xDEAD_BEEF, 0x0BAD_CAFE),
        (0x1234_5678, 0x9ABC_DEF0),
    ];

    let mut p384_pass = 0usize;
    let mut bp384_pass = 0usize;

    for (d_seed, k_seed) in seeds {
        let (out_p, _) = probe_once(&p384, "P-384", 288, 8, d_seed, k_seed);
        if out_p.starts_with("✓") {
            p384_pass += 1;
        }
        let (out_b, _) = probe_once(&bp384, "brainpoolP384r1", 288, 8, d_seed, k_seed);
        if out_b.starts_with("✓") {
            bp384_pass += 1;
        }
    }

    eprintln!();
    eprintln!("=== Summary ===");
    eprintln!(
        "P-384:           {}/{} seeds recovered key",
        p384_pass,
        seeds.len()
    );
    eprintln!(
        "brainpoolP384r1: {}/{} seeds recovered key",
        bp384_pass,
        seeds.len()
    );

    assert_eq!(
        p384_pass,
        seeds.len(),
        "P-384 expected 3/3 LLL recoveries (scaled-GS fix); got {}/{}",
        p384_pass,
        seeds.len()
    );
    assert_eq!(
        bp384_pass,
        seeds.len(),
        "brainpoolP384r1 expected 3/3 LLL recoveries (scaled-GS fix); got {}/{}",
        bp384_pass,
        seeds.len()
    );
}

/// Extended bit-length sweep of LLL convergence across curves.
///
/// Test the refined hypothesis (after the cross-Koblitz refutation):
/// does **bit-length alone** predict LLL convergence among
/// generic-n curves?  Or is secp256k1 specifically the outlier?
///
/// Sweeps P-256, P-384, P-521, brainpoolP256r1, brainpoolP384r1 —
/// all generic-n curves — at parameters scaled to each curve's
/// bit-length.  Compares against secp256k1 (the known failure).
///
/// Run: `cargo test --test lll_degeneracy_probe sweep -- --ignored --nocapture`
#[test]
#[ignore = "slow: 7 curves × 1 seed = ~10 probes (~3-5 minutes)"]
fn probe_lll_sweep_by_bit_length() {
    use cryptanalysis_suite::ecc::curve::CurveParams;
    let curves: Vec<(CurveParams, &str, u32, u32)> = vec![
        // (curve, name, k_bits, n_bits)
        (CurveParams::secp192k1(), "secp192k1", 144, 192),
        (CurveParams::secp224k1(), "secp224k1", 168, 224),
        (CurveParams::secp256k1(), "secp256k1", 192, 256),
        (CurveParams::p256(), "P-256", 192, 256),
        (CurveParams::brainpool_p256r1(), "brainpoolP256r1", 192, 256),
        (CurveParams::p384(), "P-384", 288, 384),
        (CurveParams::brainpool_p384r1(), "brainpoolP384r1", 288, 384),
        (CurveParams::p521(), "P-521", 384, 521),
    ];

    eprintln!();
    eprintln!("=== Bit-length sweep: LLL convergence across deployed curves ===");
    eprintln!(
        "{:<20} {:>8} {:>10} {:>10} {:>15}",
        "curve", "n_bits", "k_bits", "elapsed", "outcome"
    );

    let mut results: Vec<(String, u32, String, u128)> = Vec::new();

    for (curve, name, k_bits, n_bits) in &curves {
        let (outcome, elapsed) = probe_once(curve, name, *k_bits, 8, 0xC0FFEE, 0xC0FFEE);
        eprintln!(
            "{:<20} {:>8} {:>10} {:>10} {:>15}",
            name, n_bits, k_bits, elapsed, outcome
        );
        results.push((name.to_string(), *n_bits, outcome, elapsed));
    }

    eprintln!();
    eprintln!("=== Analysis ===");
    let failures: Vec<&(String, u32, String, u128)> = results
        .iter()
        .filter(|(_, _, o, _)| !o.starts_with("✓"))
        .collect();
    eprintln!("Curves that FAILED LLL: {}", failures.len());
    for f in &failures {
        eprintln!("  - {} (n_bits = {})", f.0, f.1);
    }
    eprintln!();
    if failures.iter().all(|(name, _, _, _)| name == "secp256k1") {
        eprintln!("✓ secp256k1 is the SOLE failure across deployed curves.");
        eprintln!("  Hypotheses (2) bit-length cap and (3) generic 256-bit");
        eprintln!("  are REFUTED — P-384/P-521 (larger bit-length) succeed,");
        eprintln!("  and other 256-bit curves succeed.  The degeneracy is");
        eprintln!("  curve-specific to secp256k1, not bit-length or generic-n.");
    } else if failures.iter().all(|(_, b, _, _)| *b >= 256) {
        eprintln!("? Failures restricted to ≥256-bit curves; bit-length");
        eprintln!("  hypothesis remains plausible.");
    } else {
        eprintln!("? Mixed failures; need more data.");
    }
}

/// Cross-Koblitz LLL-degeneracy probe.
///
/// Tests the working hypothesis that **near-power-of-2 group order
/// `n` correlates with LLL failure** on the Boneh-Venkatesan
/// lattice.  We probe four curves:
///
///   - secp256k1  (Koblitz, n ≈ 2^256 − small, LLL-fails)
///   - secp192k1  (Koblitz, n ≈ 2^192 − small) ← prediction: fails
///   - secp224k1  (Koblitz, n ≈ 2^224 − small) ← prediction: fails
///   - P-256      (NIST, n more "generic") ← control: passes
///
/// At parameters scaled to the curve's bit-length (k_bits = 3·n_bits/4,
/// m = 8), LLL should systematically fail on the Koblitz family but
/// succeed on P-256.
///
/// Run: `cargo test --test lll_degeneracy_probe koblitz -- --nocapture`
#[test]
#[ignore = "slow: 4 curves × 2 seeds = 8 probes (~2-3 minutes)"]
fn probe_koblitz_lll_degeneracy_hypothesis() {
    let curves: Vec<(CurveParams, &str, u32, u32)> = vec![
        // (curve, name, k_bits, n_bits) — k_bits chosen as 3/4 of n_bits
        (CurveParams::secp192k1(), "secp192k1", 144, 192),
        (CurveParams::secp224k1(), "secp224k1", 168, 224),
        (CurveParams::secp256k1(), "secp256k1", 192, 256),
        (CurveParams::p256(), "P-256", 192, 256),
    ];

    let seeds: [(u64, u64); 2] = [(0xC0FFEE, 0xC0FFEE), (0xDEAD_BEEF, 0x0BAD_CAFE)];

    eprintln!();
    eprintln!("=== Koblitz vs NIST: LLL convergence by group-order shape ===");
    eprintln!(
        "{:<12} {:>8} {:>10} {:>8} {:>10}",
        "curve", "n_bits", "n-form", "passes", "total"
    );

    let mut results: Vec<(String, u32, &str, usize, usize, u128)> = Vec::new();

    for (curve, name, k_bits, n_bits) in &curves {
        // Classify the group-order shape: is n near 2^n_bits?
        let n_bits_actual = curve.n.bits() as u32;
        let two_to_n = num_bigint::BigUint::from(1u32) << n_bits_actual;
        let gap = if two_to_n > curve.n {
            &two_to_n - &curve.n
        } else {
            &curve.n - &two_to_n
        };
        let gap_bits = gap.bits() as u32;
        let form = if gap_bits < n_bits_actual / 2 {
            "near-2^k"
        } else {
            "generic"
        };

        let mut passes = 0usize;
        let mut total_elapsed: u128 = 0;
        for (d_seed, k_seed) in &seeds {
            let (outcome, elapsed) = probe_once(curve, name, *k_bits, 8, *d_seed, *k_seed);
            total_elapsed += elapsed;
            if outcome.starts_with("✓") {
                passes += 1;
            }
        }
        eprintln!(
            "{:<12} {:>8} {:>10} {:>8} {:>10}",
            name,
            n_bits,
            form,
            passes,
            seeds.len()
        );
        results.push((
            name.to_string(),
            *n_bits,
            form,
            passes,
            seeds.len(),
            total_elapsed,
        ));
    }

    eprintln!();
    eprintln!("=== Hypothesis: near-2^k group orders ⇒ LLL fails ===");
    let koblitz_total: usize = results
        .iter()
        .filter(|(_, _, f, _, _, _)| *f == "near-2^k")
        .map(|(_, _, _, p, _, _)| p)
        .sum();
    let koblitz_attempts: usize = results
        .iter()
        .filter(|(_, _, f, _, _, _)| *f == "near-2^k")
        .map(|(_, _, _, _, t, _)| t)
        .sum();
    let generic_total: usize = results
        .iter()
        .filter(|(_, _, f, _, _, _)| *f == "generic")
        .map(|(_, _, _, p, _, _)| p)
        .sum();
    let generic_attempts: usize = results
        .iter()
        .filter(|(_, _, f, _, _, _)| *f == "generic")
        .map(|(_, _, _, _, t, _)| t)
        .sum();
    eprintln!(
        "  near-2^k curves: {}/{} LLL successes",
        koblitz_total, koblitz_attempts
    );
    eprintln!(
        "  generic curves:  {}/{} LLL successes",
        generic_total, generic_attempts
    );
    eprintln!();
    if koblitz_total == 0 && generic_total == generic_attempts {
        eprintln!("✓ Hypothesis confirmed: near-power-of-2 n ⇒ LLL fails uniformly.");
    } else if koblitz_total > 0 && generic_total < generic_attempts {
        eprintln!("✗ Hypothesis refuted: outcomes do not correlate with n's form.");
    } else {
        eprintln!("? Hypothesis partially supported; more curves needed.");
    }
}

/// P-521 reduction sweep: investigate whether LLL at m=16 or BKZ-β recovers key.
///
/// Previous result (2026-05-21): m=8 LLL terminates without NaN but no short
/// vector found after 126s.  Two hypotheses:
///   (a) insufficient samples: m=8 gives marginal lattice quality at 521 bits
///   (b) LLL is too weak: need BKZ for 521-bit dimension
///
/// This test probes: m=8/LLL, m=16/LLL, m=8/BKZ-20, m=16/BKZ-20, m=24/BKZ-20
///
/// Timeout warning: each P-521 LLL probe ~126s; BKZ-20 may be 3-5× longer.
/// Run: `cargo test --test lll_degeneracy_probe p521_reduction_sweep -- --ignored --nocapture`
#[test]
#[ignore = "slow: P-521 probes 300-600s each; run deliberately"]
fn probe_p521_reduction_sweep() {
    let p521 = CurveParams::p521();
    let d_seed = 0xC0FFEEu64;
    let k_seed = 0xC0FFEEu64;
    let k_bits = 384u32;

    eprintln!();
    eprintln!("=== P-521 reduction sweep (k_bits=384) ===");
    eprintln!(
        "{:<8} {:<10} {:<55} {:>12}",
        "m", "reduction", "outcome", "elapsed_ms"
    );

    let configs: Vec<(usize, HnpReduction)> = vec![
        (8, HnpReduction::Lll),
        (16, HnpReduction::Lll),
        (8, HnpReduction::Bkz(20)),
        (16, HnpReduction::Bkz(20)),
        (24, HnpReduction::Bkz(20)),
    ];

    let mut any_recovered = false;
    for (m, red) in configs {
        let red_label = match &red {
            HnpReduction::Lll => "LLL".to_string(),
            HnpReduction::LllHp => "LLL-HP".to_string(),
            HnpReduction::Bkz(b) => format!("BKZ-{}", b),
        };
        let (outcome, elapsed) = probe_once_ext(&p521, "P-521", k_bits, m, d_seed, k_seed, red);
        eprintln!("{:<8} {:<10} {:<55} {:>12}", m, red_label, outcome, elapsed);
        if outcome.starts_with("✓") {
            any_recovered = true;
        }
    }

    eprintln!();
    if any_recovered {
        eprintln!("✓ At least one configuration recovered the P-521 key.");
    } else {
        eprintln!("✗ No configuration recovered the key — genuine lattice dimension issue.");
        eprintln!("  Next step: larger m, BKZ-β>20, or true bigfloat GS (rug crate).");
    }
}

/// P-521 with high-precision (HP) Gram-Schmidt: verify the catastrophic-
/// cancellation hypothesis and that lll_reduce_hp recovers the key.
///
/// Hypothesis: f64 GS on the P-521 HNP basis produces phantom ~2^446 residuals
/// in b*_m[l] (should be 0) that swamp the true b*_m[m] = 2^384.  The 2048-bit
/// HP GS avoids this and LLL should recover d at m=8.
///
/// Run: `cargo test --test lll_degeneracy_probe p521_lll_hp -- --ignored --nocapture`
#[test]
#[ignore = "slow: P-521 HP LLL ~60-120s per probe"]
fn probe_p521_lll_hp() {
    let p521 = CurveParams::p521();
    let k_bits = 384u32;

    eprintln!();
    eprintln!("=== P-521 LLL-HP probe (k_bits=384, tests the bigfloat-GS fix) ===");

    let seeds: [(u64, u64, usize); 3] = [
        (0xC0FFEE, 0xC0FFEE, 8),
        (0xDEAD_BEEF, 0x0BAD_CAFE, 8),
        (0x1234_5678, 0x9ABC_DEF0, 8),
    ];

    let mut hp_pass = 0usize;
    let mut f64_pass = 0usize;

    for (d_seed, k_seed, m) in seeds {
        // f64 LLL (expected: fail due to catastrophic cancellation)
        let (out_f64, t_f64) = probe_once_ext(
            &p521,
            "P-521[f64]",
            k_bits,
            m,
            d_seed,
            k_seed,
            HnpReduction::Lll,
        );
        if out_f64.starts_with("✓") {
            f64_pass += 1;
        }
        // HP LLL (expected: recover key)
        let (out_hp, t_hp) = probe_once_ext(
            &p521,
            "P-521[HP]",
            k_bits,
            m,
            d_seed,
            k_seed,
            HnpReduction::LllHp,
        );
        if out_hp.starts_with("✓") {
            hp_pass += 1;
        }
        eprintln!(
            "  seed=0x{:08X} | f64={:<40} ({} ms) | HP={:<40} ({} ms)",
            d_seed, out_f64, t_f64, out_hp, t_hp
        );
    }

    eprintln!();
    eprintln!("f64 LLL: {}/{} recovered", f64_pass, seeds.len());
    eprintln!("HP  LLL: {}/{} recovered", hp_pass, seeds.len());

    if hp_pass > f64_pass {
        eprintln!("✓ HP GS fix improves P-521 recovery vs f64 GS.");
    }
    if hp_pass == seeds.len() {
        eprintln!("✓ P-521 HNP fully resolved: HP GS + LLL recovers key 3/3.");
    } else {
        eprintln!("? HP LLL still fails some seeds — may need larger m or BKZ.");
    }
    // The test passes as long as HP does at least as well as f64 on the same seeds.
    assert!(
        hp_pass >= f64_pass,
        "HP LLL ({}/{}) should be ≥ f64 LLL ({}/{}) for P-521",
        hp_pass,
        seeds.len(),
        f64_pass,
        seeds.len()
    );
}

/// Quick single-seed HP LLL timing probe for P-521.
///
/// Measures wall-clock time for one HP LLL recovery to benchmark the
/// incremental GS swap update (incremental O(n) per swap vs old full-recompute O(n³)).
///
/// Prior measurement (full-recompute, 2026-05-22): ~79s per probe.
/// Expected after incremental update: <10s per probe.
///
/// Run: `cargo test --test lll_degeneracy_probe p521_hp_timing -- --ignored --nocapture`
#[test]
#[ignore = "slow: ~14s per probe (down from ~79s with full-recompute; run to verify speedup"]
fn probe_p521_hp_timing() {
    let p521 = CurveParams::p521();
    let k_bits = 384u32;
    let m = 8usize;
    let d_seed = 0xC0FFEEu64;
    let k_seed = 0xC0FFEEu64;

    eprintln!();
    eprintln!("=== P-521 HP LLL single-seed timing (incremental GS swap) ===");
    eprintln!("  baseline (full-recompute, 2026-05-22): ~79s");

    let (outcome, elapsed_ms) = probe_once_ext(
        &p521,
        "P-521",
        k_bits,
        m,
        d_seed,
        k_seed,
        HnpReduction::LllHp,
    );

    eprintln!("  result: {} in {} ms", outcome, elapsed_ms);
    eprintln!();

    if elapsed_ms < 79_000 {
        eprintln!("✓ Incremental GS swap is faster than full-recompute baseline.");
    } else {
        eprintln!("? No speedup vs baseline — investigate.");
    }

    assert!(
        outcome.starts_with("✓"),
        "P-521 HP LLL should recover key; got: {}",
        outcome
    );
}

/// P-521 HP LLL at m=16 — tests efficiency after incremental GS swap (2026-05-28).
///
/// With 5.7× speedup: m=8 ~14s → m=16 estimated ~45-55s (O((m+2)²) scaling).
/// 3-seed run targets <180s total.  A pass closes §10.5 of research/notes/lattice-hnp/RESEARCH_LLL_GS_ANALYSIS.md.
///
/// Run: `cargo test --test lll_degeneracy_probe p521_hp_m16 -- --ignored --nocapture`
#[test]
#[ignore = "slow: P-521 HP LLL m=16 ~45-180s total"]
fn probe_p521_hp_m16() {
    let p521 = CurveParams::p521();
    let k_bits = 384u32;
    let m = 16usize;

    eprintln!();
    eprintln!("=== P-521 HP LLL m=16 (§10.5 efficiency check, incremental GS) ===");
    eprintln!("  lattice dim: {}×{}", m + 2, m + 2);
    eprintln!("  expected: 3/3 recovery, <180s total");

    let seeds: [(u64, u64); 3] = [
        (0xC0FFEE, 0xC0FFEE),
        (0xDEAD_BEEF, 0x0BAD_CAFE),
        (0x1234_5678, 0x9ABC_DEF0),
    ];

    let mut pass = 0usize;
    let mut total_ms = 0u128;

    for (d_seed, k_seed) in seeds {
        let (outcome, elapsed_ms) = probe_once_ext(
            &p521,
            "P-521",
            k_bits,
            m,
            d_seed,
            k_seed,
            HnpReduction::LllHp,
        );
        if outcome.starts_with("✓") {
            pass += 1;
        }
        total_ms += elapsed_ms;
    }

    eprintln!();
    eprintln!(
        "P-521 HP LLL m=16: {}/{} recovered in {} ms total",
        pass,
        seeds.len(),
        total_ms
    );
    if pass == seeds.len() {
        eprintln!("✓ §10.5 CLOSED: HP LLL scales to m=16 on P-521.");
    } else {
        eprintln!(
            "? Partial ({}/3) — try m=20 or BKZ; §10.5 remains open.",
            pass
        );
    }

    assert!(
        pass >= 1,
        "HP LLL m=16 should recover at least 1/3 P-521 keys; got 0"
    );
}

/// P-521 HP LLL single-seed timing probe for m=32.
///
/// Estimates feasibility of §10.5 at large m before committing to a 3-seed run.
/// Expected: ~162s (11.6× m=8 baseline of ~14s) based on O((m+2)²) scaling.
///
/// Run: `cargo test --test lll_degeneracy_probe p521_hp_m32_timing -- --ignored --nocapture`
#[test]
#[ignore = "slow: P-521 HP LLL m=32 single-seed ~100-200s"]
fn probe_p521_hp_m32_timing() {
    let p521 = CurveParams::p521();
    let k_bits = 384u32;
    let m = 32usize;
    let d_seed = 0xC0FFEEu64;
    let k_seed = 0xC0FFEEu64;

    eprintln!();
    eprintln!("=== P-521 HP LLL m=32 single-seed timing (§10.5) ===");
    eprintln!("  lattice dim: {}×{}", m + 2, m + 2);
    eprintln!("  baseline (m=8 incremental, 2026-05-28): ~14s");
    eprintln!("  O((m+2)²) estimate for m=32: ~162s");

    let (outcome, elapsed_ms) = probe_once_ext(
        &p521,
        "P-521",
        k_bits,
        m,
        d_seed,
        k_seed,
        HnpReduction::LllHp,
    );

    eprintln!();
    eprintln!("  m=32 result: {} in {} ms", outcome, elapsed_ms);

    let m8_baseline_ms = 14_000u128;
    let ratio = elapsed_ms as f64 / m8_baseline_ms as f64;
    let theoretical_ratio = ((m as f64 + 2.0) / 10.0f64).powi(2);
    eprintln!(
        "  scaling ratio: {:.1}× measured vs {:.1}× theoretical O((m+2)²)",
        ratio, theoretical_ratio
    );

    // Don't require recovery — m=32 may need BKZ; just measure timing.
    eprintln!("  (not asserting recovery at m=32 — timing probe only)");
}
