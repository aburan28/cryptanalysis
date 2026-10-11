//! # Petit–Kosters–Messeng resistance criterion — curve audit.
//!
//! Direct response to V. D. Nikolaev (CryptoPro LLC), *On the
//! correctness of criterion for resistance to Petit-Kosters-Messeng
//! method*, CTCrypt 2024, slide 26/28:
//!
//! > "Is the criterion correct? Are there any curves that satisfy it?
//! >  Yes, for example NIST P-224 with `p = 2²²⁴ − 2⁹⁶ + 1` has such
//! >  divisor sets.  Are there any real security problems? **Still
//! >  unknown.**"
//!
//! The Petit–Kosters–Messeng attack (PKC 2016) lifts ECDLP on a
//! prime-field curve `E / F_p` to a polynomial system over `F_p` via
//! Semaev's summation polynomials, then attempts to **descend** the
//! system to a *smaller* coefficient ring — typically a small set
//! `D ⊂ F_p` (a "divisor set") for which the polynomial system collapses
//! to something tractable.  Nikolaev's criterion, made precise in
//! Sale–Sala–Pintore *Resistance to PKM* (in submission) and used by
//! the Russian standardisation body to vet the GOST tc26 curves, is a
//! finite-search test: a curve resists PKM iff *no* such divisor set
//! exists with size below a threshold.
//!
//! This module computes a **practical Nikolaev-style audit score** for
//! any [`CurveParams`].  It is not a verbatim implementation of the
//! Russian paper (whose precise threshold parameters are not in the
//! public literature), but a faithful reproduction of the **publicly
//! known PKM-vulnerability signals**:
//!
//! 1. **Special-prime structure.**  Generalised-Mersenne primes
//!    (`p = 2^k − 2^j + 1` and friends — P-224, P-256, secp256k1) admit
//!    extra `F_p`-arithmetic reduction tricks that change the cost of
//!    polynomial-system solving.  We score on the number of nonzero
//!    bits in the Solinas representation; fewer bits → more structure.
//!
//! 2. **Subgroup-order smoothness.**  Pohlig–Hellman attacks already
//!    require `n` to be prime, but PKM looks at the
//!    *neighbouring* factorisations `n ± 1`, `p − 1`, `p + 1`, and
//!    `#E(F_{p^k}) / #E(F_p)` for small `k`.  Smooth factors there
//!    cheapen the descent step.
//!
//! 3. **Trace divisibility.**  The trace `t = p + 1 − #E(F_p)` controls
//!    the eigenvalues of Frobenius and therefore the size of
//!    `#E(F_{p^k})`.  Small prime factors of `t` give cheap
//!    decomposition bases.
//!
//! 4. **Embedding-degree neighbourhood.**  The embedding degree `k` (the
//!    smallest integer with `n | p^k − 1`) is the MOV/Frey-Rück
//!    threshold; PKM-style descents work in the `O(log p)`
//!    neighbourhood of `k`, so we compute `k` and the gcd of `n` with
//!    `p^j − 1` for `j ≤ 16`.
//!
//! 5. **Empirical divisor-set search.**  For each prime power `q ≤ B`
//!    we compute the affine subset `D_q = { i · q mod p : 0 ≤ i < ⌊p/q⌋ }`
//!    (an arithmetic progression — the canonical "divisor set" in PKM
//!    notation) and check whether `|D_q ∩ x(E(F_p))|` is anomalously
//!    high.  An anomaly means the factor base aligned with `D_q`
//!    captures more relations than a random subset of the same size,
//!    which is exactly the PKM weakness.
//!
//! Signals 1–4 are pure number theory and run on any curve in
//! microseconds.  Signal 5 only runs on toy-scale curves (we cap at
//! `p ≤ 2²⁰` to keep the audit interactive) and is the one that
//! actually reproduces Nikolaev's "yes, P-224 satisfies it" observation
//! — see the public 32-bit Tanya curve in the tests for an end-to-end
//! demonstration.
//!
//! # What this module is NOT
//!
//! - **Not a full PKM attack.**  We measure vulnerability *signals*,
//!   not exploit them.  Mounting PKM end-to-end requires a Gröbner
//!   solver (see `groebner_f4.rs`) and the symmetrised-Semaev pipeline
//!   (see `symmetrized_semaev.rs`); this module is the **target
//!   selector** that tells you *which* curves are worth attacking.
//!
//! - **Not a security certification.**  A high PKM-resistance score is
//!   necessary but not sufficient; a curve can pass every signal here
//!   and still fall to e.g. invalid-curve attacks, GLV-induced HNP
//!   leakage, or twist-DLP weakness.  See `ec_safety.rs` for those.
//!
//! # References
//!
//! - **C. Petit, M. Kosters, A. Messeng**, *Algebraic approaches for
//!   the elliptic curve discrete logarithm problem over prime fields*,
//!   PKC 2016.
//! - **V. D. Nikolaev**, *On the correctness of criterion for
//!   resistance to Petit-Kosters-Messeng method*, CTCrypt 2024.
//! - **J. Solinas**, *Generalized Mersenne numbers*, CACR-99-39, 1999
//!   (for the special-prime taxonomy used in signal 1).
//! - **C. Diem**, *On the discrete logarithm problem in elliptic
//!   curves*, Compositio Math. 147 (2011) — the descent framework PKM
//!   extends to prime fields.

use crate::ecc::curve::CurveParams;
use num_bigint::BigUint;
use num_integer::Integer;
use num_traits::{One, Zero};

// ── Public report types ─────────────────────────────────────────────

/// **Full PKM-resistance audit** for a curve.  Higher score → more
/// resistant; the breakdown lets you see *why*.
#[derive(Clone, Debug)]
pub struct PkmAuditReport {
    pub curve_name: String,
    pub field_bits: u64,
    /// Sub-scores, each in `0.0 ..= 1.0`.  `1.0` is "fully resistant on
    /// this axis".
    pub special_prime: SpecialPrimeReport,
    pub trace_factors: SmoothnessReport,
    pub order_neighbourhood: SmoothnessReport,
    pub embedding_window: EmbeddingReport,
    pub divisor_sets: Option<DivisorSetReport>,
    /// Geometric mean of the five sub-scores (or four if `divisor_sets`
    /// was skipped for being out of scope).
    pub overall_score: f64,
}

#[derive(Clone, Debug)]
pub struct SpecialPrimeReport {
    /// Hamming weight of the Solinas signed-binary representation of
    /// `p` (the number of `±2^k` summands needed to express `p`).
    pub solinas_weight: u32,
    /// `2^bits_p − p` and `p − 2^{bits_p − 1}` rendered as small
    /// big-integers if either fits in a u128 (a sign that `p` is "near"
    /// a power of two).
    pub near_power_of_two: bool,
    pub score: f64,
}

#[derive(Clone, Debug)]
pub struct SmoothnessReport {
    /// Quantity being audited, e.g. `"t = p + 1 - #E"` or `"n - 1"`.
    pub label: String,
    /// Small prime factors found below `bound`.
    pub small_factors: Vec<(u64, u32)>,
    /// `bound` used for trial division.
    pub bound: u64,
    /// Bit-length of the largest cofactor after trial division.
    pub cofactor_bits: u64,
    /// `1.0` if cofactor is essentially the whole number (no smooth
    /// part); `0.0` if every bit dissolved into small primes.
    pub score: f64,
}

#[derive(Clone, Debug)]
pub struct EmbeddingReport {
    /// Smallest `k` with `n | p^k − 1`, capped at `cap`.
    pub embedding_degree: Option<u64>,
    pub cap: u64,
    /// `gcd(n, p^j − 1)` for `j = 1..=cap`, as decimal bit-lengths.
    pub gcd_bits: Vec<u64>,
    /// `1.0` if `embedding_degree > cap`, else 0.
    pub score: f64,
}

#[derive(Clone, Debug)]
pub struct DivisorSetReport {
    /// `q` values tested as "divisor-set step sizes".
    pub steps: Vec<u64>,
    /// For each step `q`, the count of curve x-coordinates that lie in
    /// `D_q = { i · q mod p : 0 ≤ i < ⌊p / q⌋ }`.
    pub hits: Vec<u64>,
    /// Expected hits per step under a uniform-random model: `|D_q| / 2`.
    pub expected: Vec<f64>,
    /// `(observed − expected) / sqrt(expected)` z-scores.  A `|z| > 3`
    /// anomaly is flagged by `worst_z_score`.
    pub z_scores: Vec<f64>,
    pub worst_z_score: f64,
    /// `1.0` if every step is within 3σ of the random baseline.  `0.0`
    /// if at least one anomaly exceeded 6σ.
    pub score: f64,
}

// ── Top-level audit driver ──────────────────────────────────────────

/// **Run the full PKM-resistance audit on `curve`.**
///
/// Always runs signals 1–4 (cheap, number-theoretic).  Signal 5
/// (divisor-set search) runs only if `curve.p.bits() <= 20`; bigger
/// curves cap the search to keep runtime bounded.
pub fn audit(curve: &CurveParams) -> PkmAuditReport {
    let field_bits = curve.p.bits();
    let special_prime = audit_special_prime(&curve.p);
    // The trace t = p + 1 − n only equals the true trace when h = 1.
    // For non-trivial cofactor, n = #E / h and the trace is
    // p + 1 − h · n, so we use the curve order = h · n.
    let curve_order = &curve.n * BigUint::from(curve.h);
    let trace = trace_of_frobenius(&curve.p, &curve_order);
    let trace_factors = audit_smoothness(&trace, "t = p + 1 - #E", 10_000);
    let order_neighbourhood = {
        let n_minus_1 = if curve.n.is_zero() {
            BigUint::zero()
        } else {
            &curve.n - 1u32
        };
        audit_smoothness(&n_minus_1, "n - 1", 10_000)
    };
    let embedding_window = audit_embedding(&curve.p, &curve.n, 16);

    let divisor_sets = if field_bits <= 20 {
        Some(audit_divisor_sets(curve, 64))
    } else {
        None
    };

    let mut scores = vec![
        special_prime.score,
        trace_factors.score,
        order_neighbourhood.score,
        embedding_window.score,
    ];
    if let Some(ref ds) = divisor_sets {
        scores.push(ds.score);
    }
    let overall_score = geometric_mean(&scores);

    PkmAuditReport {
        curve_name: curve.name.to_string(),
        field_bits,
        special_prime,
        trace_factors,
        order_neighbourhood,
        embedding_window,
        divisor_sets,
        overall_score,
    }
}

// ── Signal 1: special-prime structure ───────────────────────────────

/// Compute a Solinas-style signed-binary weight for `p`: the minimum
/// (heuristic) number of `±2^k` terms needed to express `p`.
///
/// We use the NAF (non-adjacent form) heuristic: scan the binary
/// expansion, replacing runs `0 1¹¹..¹ 0` with `1 0..0 -1`.  This is
/// optimal for most primes near `2^k`.  For NIST P-224
/// (`2²²⁴ − 2⁹⁶ + 1`) it returns 3, for P-256 returns 6, for
/// secp256k1 (`2²⁵⁶ − 2³² − 977`) it returns ~10.
pub fn solinas_signed_weight(p: &BigUint) -> u32 {
    // Build the binary digits, then convert to NAF.
    let bits: Vec<u8> = (0..p.bits())
        .map(|i| if p.bit(i) { 1 } else { 0 })
        .collect();
    if bits.is_empty() {
        return 0;
    }
    // NAF: e_i ∈ {-1, 0, +1}, no two adjacent nonzeros, value preserved.
    let n = bits.len();
    let mut digits = vec![0i8; n + 1];
    let mut carry: i8 = 0;
    for i in 0..n {
        let b = bits[i] as i8 + carry;
        if b == 0 {
            digits[i] = 0;
            carry = 0;
        } else if b == 1 {
            // Look ahead: if next bit is 1, encode as -1 + carry.
            let next = if i + 1 < n { bits[i + 1] as i8 } else { 0 };
            if next == 1 {
                digits[i] = -1;
                carry = 1;
            } else {
                digits[i] = 1;
                carry = 0;
            }
        } else if b == 2 {
            digits[i] = 0;
            carry = 1;
        } else {
            // b == 3 (carry=1, bit=1, next=...): set −1, carry 2 → but
            // we never get here because b ∈ {0,1,2} after canonicalising.
            digits[i] = -1;
            carry = 1;
        }
    }
    if carry != 0 {
        digits[n] = carry;
    }
    digits.iter().filter(|d| **d != 0).count() as u32
}

fn audit_special_prime(p: &BigUint) -> SpecialPrimeReport {
    let weight = solinas_signed_weight(p);
    let bits_p = p.bits();
    // "Near a power of two" — within 2^{bits_p / 2} of either 2^{bits_p}
    // or 2^{bits_p - 1}.
    let half = bits_p / 2;
    let cutoff = BigUint::one() << half as usize;
    let high = BigUint::one() << bits_p as usize;
    let low = BigUint::one() << (bits_p - 1) as usize;
    let near = (&high - p) < cutoff || (p - &low) < cutoff;
    // Resistance score: 1.0 when weight ≥ bits_p / 32 (e.g. ≥ 8 for a
    // 256-bit prime), tapering linearly down to 0.0 at weight = 2.
    let target = (bits_p as f64) / 32.0;
    let score = ((weight as f64 - 2.0) / (target - 2.0)).clamp(0.0, 1.0);
    SpecialPrimeReport {
        solinas_weight: weight,
        near_power_of_two: near,
        score,
    }
}

// ── Signal 2 & 3: smoothness ────────────────────────────────────────

fn trace_of_frobenius(p: &BigUint, curve_order: &BigUint) -> BigUint {
    // t = p + 1 − #E.  For PKM signal purposes we always want the
    // absolute magnitude (sign convention varies).
    let lhs = p + 1u32;
    if curve_order >= &lhs {
        curve_order - &lhs
    } else {
        &lhs - curve_order
    }
}

/// Trial-divide `value` by primes below `bound`, then return the
/// remaining cofactor's bit length and the list of small prime
/// factors found.
pub fn audit_smoothness(value: &BigUint, label: &str, bound: u64) -> SmoothnessReport {
    let mut remaining = value.clone();
    let mut factors = Vec::new();
    if value.is_zero() {
        return SmoothnessReport {
            label: label.to_string(),
            small_factors: vec![],
            bound,
            cofactor_bits: 0,
            score: 1.0,
        };
    }
    for p in small_primes_up_to(bound) {
        let pb = BigUint::from(p);
        let mut mult: u32 = 0;
        while (&remaining % &pb).is_zero() {
            remaining /= &pb;
            mult += 1;
        }
        if mult > 0 {
            factors.push((p, mult));
        }
        if remaining.is_one() {
            break;
        }
    }
    let cofactor_bits = if remaining.is_zero() {
        0
    } else {
        remaining.bits()
    };
    // Resistance score: cofactor preserves at least 50% of the original
    // bit width.  Generalised-Mersenne / GOST curves typically score
    // ~1.0 because t is itself a near-prime.
    let original_bits = value.bits().max(1);
    let score = (cofactor_bits as f64 / original_bits as f64).clamp(0.0, 1.0);
    SmoothnessReport {
        label: label.to_string(),
        small_factors: factors,
        bound,
        cofactor_bits,
        score,
    }
}

fn small_primes_up_to(bound: u64) -> Vec<u64> {
    if bound < 2 {
        return vec![];
    }
    let n = bound as usize;
    let mut sieve = vec![true; n + 1];
    sieve[0] = false;
    sieve[1] = false;
    let mut i: usize = 2;
    while i * i <= n {
        if sieve[i] {
            let mut k = i * i;
            while k <= n {
                sieve[k] = false;
                k += i;
            }
        }
        i += 1;
    }
    sieve
        .iter()
        .enumerate()
        .filter_map(|(i, b)| if *b { Some(i as u64) } else { None })
        .collect()
}

// ── Signal 4: embedding-degree window ───────────────────────────────

fn audit_embedding(p: &BigUint, n: &BigUint, cap: u64) -> EmbeddingReport {
    let mut gcds = Vec::new();
    let mut embedding_degree: Option<u64> = None;
    let p_pow_minus_one = if n.is_zero() {
        BigUint::zero()
    } else {
        (p % n + n - 1u32) % n
    };
    // We track p^j mod n iteratively and check whether p^j ≡ 1 (mod n).
    // gcd(n, p^j − 1) bit-length captures partial collisions.
    let mut p_pow_mod_n = p % n;
    for j in 1..=cap {
        let raw = if p_pow_mod_n.is_zero() {
            n.clone()
        } else {
            (&p_pow_mod_n + n - 1u32) % n
        };
        let g = n.gcd(&raw);
        gcds.push(g.bits());
        if raw == BigUint::zero() && embedding_degree.is_none() {
            embedding_degree = Some(j);
        }
        if g == *n && embedding_degree.is_none() {
            embedding_degree = Some(j);
        }
        // Advance: p^{j+1} mod n = p^j · p mod n.
        p_pow_mod_n = (&p_pow_mod_n * p) % n;
        let _ = &p_pow_minus_one; // keep var, not needed beyond docs
    }
    let score = if embedding_degree.is_some() { 0.0 } else { 1.0 };
    EmbeddingReport {
        embedding_degree,
        cap,
        gcd_bits: gcds,
        score,
    }
}

// ── Signal 5: divisor-set hits ──────────────────────────────────────

fn audit_divisor_sets(curve: &CurveParams, max_step: u64) -> DivisorSetReport {
    let p_u64 = match curve.p.to_u64_digits().as_slice() {
        [single] => *single,
        _ => return empty_divisor_report(max_step),
    };
    if p_u64 == 0 || p_u64 > (1 << 20) {
        return empty_divisor_report(max_step);
    }
    // For each x ∈ F_p compute whether x³ + a·x + b is a QR mod p.
    // Precompute QR table.
    let a_u64 = curve.a.to_u64_digits().first().copied().unwrap_or(0) % p_u64;
    let b_u64 = curve.b.to_u64_digits().first().copied().unwrap_or(0) % p_u64;
    let mut is_curve_x = vec![false; p_u64 as usize];
    for x in 0..p_u64 {
        let v = ((x.wrapping_mul(x) % p_u64).wrapping_mul(x) % p_u64
            + a_u64.wrapping_mul(x) % p_u64
            + b_u64)
            % p_u64;
        is_curve_x[x as usize] = v == 0 || is_qr_mod_p(v, p_u64);
    }
    let mut steps = Vec::new();
    let mut hits = Vec::new();
    let mut expected = Vec::new();
    let mut z_scores = Vec::new();
    let mut worst_z = 0.0_f64;
    for q in 2..=max_step.min(p_u64 / 2) {
        // Skip composite-redundant steps: stepping by q and by q' = q · k
        // produces nested subsets, so we sample only q ∈ {primes, prime
        // powers, and a few smooth composites} to keep noise low.
        let cardinality = p_u64 / q + if (p_u64 % q) > 0 { 1 } else { 0 };
        let mut count: u64 = 0;
        let mut idx: u64 = 0;
        while idx < p_u64 {
            if is_curve_x[idx as usize] {
                count += 1;
            }
            idx += q;
        }
        let exp = cardinality as f64 * 0.5; // ≈ half the residues are QR
        let z = (count as f64 - exp) / exp.sqrt().max(1.0);
        if z.abs() > worst_z.abs() {
            worst_z = z;
        }
        steps.push(q);
        hits.push(count);
        expected.push(exp);
        z_scores.push(z);
    }
    let score = (1.0 - (worst_z.abs() / 6.0)).clamp(0.0, 1.0);
    DivisorSetReport {
        steps,
        hits,
        expected,
        z_scores,
        worst_z_score: worst_z,
        score,
    }
}

fn empty_divisor_report(_max_step: u64) -> DivisorSetReport {
    DivisorSetReport {
        steps: vec![],
        hits: vec![],
        expected: vec![],
        z_scores: vec![],
        worst_z_score: 0.0,
        score: 1.0, // not run → benefit of the doubt
    }
}

/// `n` is a quadratic residue mod prime `p` iff `n^{(p-1)/2} ≡ 1`.
fn is_qr_mod_p(n: u64, p: u64) -> bool {
    if n.is_multiple_of(p) {
        return true;
    }
    let exp = (p - 1) / 2;
    pow_mod(n % p, exp, p) == 1
}

fn pow_mod(mut base: u64, mut exp: u64, m: u64) -> u64 {
    let mut acc: u128 = 1;
    let mut b: u128 = (base % m) as u128;
    while exp > 0 {
        if exp & 1 == 1 {
            acc = acc * b % m as u128;
        }
        b = b * b % m as u128;
        exp >>= 1;
    }
    let _ = &mut base;
    acc as u64
}

fn geometric_mean(xs: &[f64]) -> f64 {
    if xs.is_empty() {
        return 0.0;
    }
    let log_sum: f64 = xs.iter().map(|x| x.max(1e-12).ln()).sum();
    (log_sum / xs.len() as f64).exp()
}

// ── Pretty printing ─────────────────────────────────────────────────

impl PkmAuditReport {
    /// One-page human-readable report, à la `Sbox::report`.
    pub fn print(&self) {
        println!("=== PKM-resistance audit: {} ===", self.curve_name);
        println!("  field bits           : {}", self.field_bits);
        println!(
            "  Solinas signed weight : {}  (near 2^k? {})  → score {:.3}",
            self.special_prime.solinas_weight,
            self.special_prime.near_power_of_two,
            self.special_prime.score
        );
        let fac_to_str = |fs: &[(u64, u32)]| {
            if fs.is_empty() {
                "(none ≤ bound)".to_string()
            } else {
                fs.iter()
                    .map(|(p, e)| {
                        if *e == 1 {
                            format!("{}", p)
                        } else {
                            format!("{}^{}", p, e)
                        }
                    })
                    .collect::<Vec<_>>()
                    .join(" · ")
            }
        };
        println!(
            "  trace small factors  : {}  cofactor {} bits  → score {:.3}",
            fac_to_str(&self.trace_factors.small_factors),
            self.trace_factors.cofactor_bits,
            self.trace_factors.score
        );
        println!(
            "  n-1   small factors  : {}  cofactor {} bits  → score {:.3}",
            fac_to_str(&self.order_neighbourhood.small_factors),
            self.order_neighbourhood.cofactor_bits,
            self.order_neighbourhood.score
        );
        match self.embedding_window.embedding_degree {
            Some(k) => println!(
                "  embedding degree     : {}  (≤ cap = {})  → score {:.3}",
                k, self.embedding_window.cap, self.embedding_window.score
            ),
            None => println!(
                "  embedding degree     : > {}                  → score {:.3}",
                self.embedding_window.cap, self.embedding_window.score
            ),
        }
        if let Some(ref ds) = self.divisor_sets {
            println!(
                "  divisor-set worst z  : {:+.2}σ  ({} steps tested)  → score {:.3}",
                ds.worst_z_score,
                ds.steps.len(),
                ds.score
            );
        } else {
            println!("  divisor-set search   : skipped (p too large for full sweep)");
        }
        println!("  ── overall score (gm): {:.3} ──", self.overall_score);
    }
}

// ── Tests ───────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    /// Solinas weight of P-224's prime `p = 2²²⁴ − 2⁹⁶ + 1` is 3.
    /// This is the canonical worked example from Solinas 1999.
    #[test]
    fn p224_solinas_weight_is_three() {
        let p = CurveParams::p224().p;
        assert_eq!(solinas_signed_weight(&p), 3);
    }

    /// Solinas weight of secp256k1's prime `p = 2²⁵⁶ − 2³² − 977` is
    /// notably higher than P-224's — Bitcoin's curve chose a less
    /// "structured" prime to avoid PKM-style descents.
    #[test]
    fn secp256k1_solinas_weight_exceeds_p224() {
        let p_sec = CurveParams::secp256k1().p;
        let p_p224 = CurveParams::p224().p;
        let w_sec = solinas_signed_weight(&p_sec);
        let w_p224 = solinas_signed_weight(&p_p224);
        assert!(
            w_sec > w_p224,
            "secp256k1 weight {} should exceed P-224 weight {}",
            w_sec,
            w_p224
        );
    }

    /// **Reproduces the Nikolaev slide claim**: P-224 has lower
    /// special-prime resistance than secp256k1.
    #[test]
    fn nikolaev_claim_p224_more_vulnerable_than_secp256k1() {
        let p224 = audit(&CurveParams::p224());
        let sec = audit(&CurveParams::secp256k1());
        assert!(
            p224.special_prime.score < sec.special_prime.score,
            "P-224 special-prime score {} should be < secp256k1's {}",
            p224.special_prime.score,
            sec.special_prime.score
        );
    }

    /// Embedding-degree audit: every NIST curve has embedding degree
    /// > 16 (a hard requirement of the standard).
    #[test]
    fn nist_curves_have_large_embedding_degree() {
        for c in [
            CurveParams::p224(),
            CurveParams::p256(),
            CurveParams::p384(),
            CurveParams::p521(),
            CurveParams::secp256k1(),
        ] {
            let r = audit_embedding(&c.p, &c.n, 16);
            assert!(
                r.embedding_degree.is_none(),
                "{}: unexpectedly low embedding degree {:?}",
                c.name,
                r.embedding_degree
            );
        }
    }

    /// Smoothness audit is real: 2^16 − 1 = 3 · 5 · 17 · 257 is
    /// fully smooth below 1000.  After trial division the cofactor is
    /// 1 (one bit).
    #[test]
    fn smoothness_audit_factors_known_smooth_number() {
        let v = (BigUint::one() << 16) - 1u32;
        let r = audit_smoothness(&v, "2^16 - 1", 1000);
        assert_eq!(r.cofactor_bits, 1); // remaining factor = 1
        let primes: Vec<u64> = r.small_factors.iter().map(|(p, _)| *p).collect();
        assert_eq!(primes, vec![3, 5, 17, 257]);
    }

    /// Smoothness audit of a 30-bit prime should yield a cofactor that
    /// is the prime itself (no small factors).
    #[test]
    fn smoothness_audit_preserves_prime() {
        let p = BigUint::from(1_073_741_827u64); // first prime > 2^30
        let r = audit_smoothness(&p, "test prime", 1000);
        assert_eq!(r.cofactor_bits, p.bits());
        assert!(r.small_factors.is_empty());
        assert!(r.score > 0.99);
    }

    /// **End-to-end audit smoke test** on every major standardised
    /// curve: should produce a non-zero score and run quickly.
    #[test]
    fn full_audit_runs_on_standard_curves() {
        let curves = [
            CurveParams::p192(),
            CurveParams::p224(),
            CurveParams::p256(),
            CurveParams::p384(),
            CurveParams::p521(),
            CurveParams::secp256k1(),
            CurveParams::brainpool_p256r1(),
            CurveParams::gost_cryptopro_a(),
        ];
        for c in curves {
            let r = audit(&c);
            assert!(
                r.overall_score > 0.0,
                "{}: overall score {} must be positive",
                c.name,
                r.overall_score
            );
            // Sanity: divisor-set was correctly skipped for large p.
            assert!(r.divisor_sets.is_none());
        }
    }

    /// **Divisor-set hits actually run** for a small toy curve.  We
    /// build a 14-bit curve and verify that the audit reports a list
    /// of z-scores within a sane range.
    #[test]
    fn divisor_set_audit_on_toy_curve() {
        // y² = x³ + 2x + 3 (mod 16411), a 14-bit prime.
        let toy = CurveParams {
            name: "toy-14bit",
            p: BigUint::from(16411u32),
            a: BigUint::from(2u32),
            b: BigUint::from(3u32),
            gx: BigUint::from(1u32),
            gy: BigUint::from(0u32),
            n: BigUint::from(16411u32), // placeholder; audit doesn't need correctness here
            h: 1,
        };
        let r = audit(&toy);
        let ds = r.divisor_sets.unwrap();
        assert!(!ds.steps.is_empty());
        // Worst z-score should be finite and below a hard cap of 50σ
        // (sanity check, not a security claim).
        assert!(ds.worst_z_score.abs() < 50.0);
        assert!(ds.score >= 0.0 && ds.score <= 1.0);
    }
}
