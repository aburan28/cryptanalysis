//! Elliptic-curve parameter safety checker.
//!
//! Given a candidate short-Weierstrass curve `y² = x³ + a·x + b (mod p)`
//! together with its claimed generator `G = (gx, gy)`, generator order
//! `n`, and cofactor `h`, this module runs the standard ECDH/ECDSA
//! parameter audit and reports which (if any) of the documented
//! attacks the curve is vulnerable to.
//!
//! Catalogue of attacks covered (corresponding to the elikaski/ECC_Attacks
//! survey):
//!
//! 1. **Order too small** — `bits(n) < min_security_level · 2`.  ECDLP
//!    is solvable in `O(√n)` via Pollard rho / BSGS, so an `n` that is
//!    only `2 · L` bits gives security level `L`.  SafeCurves
//!    recommends `n ≥ 2²⁰⁰`.
//!
//! 2. **Order is smooth** — Pohlig–Hellman reduces ECDLP in a
//!    composite-order subgroup to ECDLPs in its prime-power
//!    subgroups.  If the largest prime factor of `n` is small, the
//!    cipher is broken.  We trial-divide `n` up to a configurable
//!    smoothness bound and report the largest prime factor found.
//!
//! 3. **Order *almost* smooth + small private key** — variant of
//!    Pohlig–Hellman: even if `n` has a huge prime factor, an
//!    attacker with knowledge that the private key fits in `k` bits
//!    can ignore prime factors of `n` larger than `k` bits.  We
//!    report the *effective* security level given a private-key bit
//!    budget.
//!
//! 4. **Point not on curve** — runtime check, not a parameter check.
//!    Provided as [`CurveParams::is_point_on_curve`] so callers can
//!    apply it to every received public key in their ECDH / ECDSA
//!    code paths.
//!
//! 5. **Singular curve** — `4a³ + 27b² ≡ 0 (mod p)`.  A singular curve
//!    has a node or cusp; ECDLP collapses to a DLP in `F_p` or
//!    `F_p × F_p`, both of which are easy.
//!
//! 6. **Supersingular (small embedding degree)** — the smallest `k`
//!    with `p^k ≡ 1 (mod n)` is the *embedding degree*.  When `k` is
//!    small (typically `≤ 6`), the MOV/Frey–Rück reduction maps
//!    ECDLP into a DLP in `F_{p^k}*` where index calculus runs.
//!
//! 7. **Anomalous curve** — `#E(F_p) = p`.  Smart's attack runs in
//!    `O(1)` p-adic operations.  We check `n · h == p`.
//!
//! All checks are performed on **public** parameters and use
//! `num-bigint` for arbitrary precision; nothing here needs to be
//! constant-time.

use num_bigint::{BigInt, BigUint, Sign, ToBigInt};
use num_traits::{One, Zero};

use crate::asymmetric::rsa::is_prime;
use crate::utils::mod_pow;

// ── Public API types ─────────────────────────────────────────────────────────

/// Short-Weierstrass curve parameters: `y² = x³ + a·x + b (mod p)`,
/// generator `G = (gx, gy)` of order `n`, cofactor `h = #E / n`.
#[derive(Clone, Debug)]
pub struct CurveParams {
    pub p: BigUint,
    pub a: BigInt,
    pub b: BigInt,
    pub gx: BigUint,
    pub gy: BigUint,
    pub n: BigUint,
    pub h: BigUint,
}

/// Verdict for one of the documented attacks.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum SafetyCheck {
    /// Check passed — no evidence of vulnerability.
    Pass,
    /// Check failed — a concrete vulnerability is present.
    Fail(String),
    /// Result is inconclusive (e.g. partial factorisation hit the
    /// configured bound).  The caller should decide whether to
    /// treat this as pass or fail given their risk tolerance.
    Inconclusive(String),
}

impl SafetyCheck {
    pub fn is_pass(&self) -> bool {
        matches!(self, SafetyCheck::Pass)
    }
    pub fn is_fail(&self) -> bool {
        matches!(self, SafetyCheck::Fail(_))
    }
}

/// Aggregate report from [`CurveParams::analyse`].
#[derive(Clone, Debug)]
pub struct SafetyReport {
    pub order_size: SafetyCheck,
    pub order_smoothness: SafetyCheck,
    pub effective_security: SafetyCheck,
    pub generator_on_curve: SafetyCheck,
    pub non_singular: SafetyCheck,
    pub non_supersingular: SafetyCheck,
    pub non_anomalous: SafetyCheck,
    /// Multi-target / amortised-rho margin check.  `Pass` when no
    /// `expected_deployment_size` was provided, or when the
    /// per-key security level under Galbraith-Lin-Scott amortisation
    /// remains above the configured floor.
    pub multi_target_margin: SafetyCheck,
    /// Trace-zero / Weil-descent risk: relevant only when the
    /// caller declares `AnalysisOptions::extension_degree > 1`.
    /// `Pass` for prime fields and for prime extension-degree
    /// curves; `Fail` for composite extension-degree (Diem).
    pub no_weil_descent: SafetyCheck,
    /// **Experimental**: `Cl(O)`-orbit brittleness — measures the
    /// CRT-coverage of `d` from the curve's 2-isogeny orbit.  Only
    /// runs at sub-cryptographic curve sizes; returns
    /// [`SafetyCheck::Inconclusive`] for cryptographic-size `p`.  See
    /// [`crate::cryptanalysis::cga_hnc`] for the underlying research.
    pub orbit_brittleness: SafetyCheck,
}

impl SafetyReport {
    /// `true` only if every check returned [`SafetyCheck::Pass`].
    /// Inconclusive results count as not-passing (caller-must-decide).
    pub fn all_pass(&self) -> bool {
        [
            &self.order_size,
            &self.order_smoothness,
            &self.effective_security,
            &self.generator_on_curve,
            &self.non_singular,
            &self.non_supersingular,
            &self.non_anomalous,
            &self.multi_target_margin,
            &self.no_weil_descent,
            &self.orbit_brittleness,
        ]
        .iter()
        .all(|c| c.is_pass())
    }

    /// Names of every check that returned [`SafetyCheck::Fail`].
    pub fn failed_checks(&self) -> Vec<&'static str> {
        let mut out = Vec::new();
        if self.order_size.is_fail() {
            out.push("order_size");
        }
        if self.order_smoothness.is_fail() {
            out.push("order_smoothness");
        }
        if self.effective_security.is_fail() {
            out.push("effective_security");
        }
        if self.generator_on_curve.is_fail() {
            out.push("generator_on_curve");
        }
        if self.non_singular.is_fail() {
            out.push("non_singular");
        }
        if self.non_supersingular.is_fail() {
            out.push("non_supersingular");
        }
        if self.non_anomalous.is_fail() {
            out.push("non_anomalous");
        }
        if self.multi_target_margin.is_fail() {
            out.push("multi_target_margin");
        }
        if self.no_weil_descent.is_fail() {
            out.push("no_weil_descent");
        }
        if self.orbit_brittleness.is_fail() {
            out.push("orbit_brittleness");
        }
        out
    }
}

/// Tunable thresholds for [`CurveParams::analyse`].
#[derive(Clone, Debug)]
pub struct AnalysisOptions {
    /// Minimum `bits(n)`.  SafeCurves recommends `≥ 200`; NIST P-curves
    /// use 256+.  Default: 200.
    pub min_order_bits: u32,
    /// Smoothness search bound for trial division of `n`.  Larger
    /// catches more vulnerabilities but takes longer.  Default: `2²²`
    /// (≈ 4 million), which catches every "stupid" small-factor case
    /// in milliseconds.
    pub smoothness_bound: u64,
    /// Minimum bit-length of the largest prime factor of `n`.  An
    /// attacker can solve ECDLP in the largest sub-group via
    /// Pollard-rho in `O(√q)` time.  Default: `160` (≈ 80-bit
    /// security).
    pub min_largest_prime_factor_bits: u32,
    /// Assumed minimum private-key size in bits.  Used by the
    /// "almost-smooth + small key" check.  Defaults to
    /// `min_order_bits`, i.e. assume full-size private keys.
    pub min_private_key_bits: u32,
    /// Embedding-degree cutoff: curves with embedding degree
    /// `≤ max_safe_embedding_degree` are flagged as MOV-vulnerable.
    /// Pairing-friendly curves (BLS12, BN) use embedding degrees
    /// 12+ deliberately and would pass with the default of `6`.
    /// Set to `1` if you want to disable this check.
    pub max_unsafe_embedding_degree: u32,
    /// Maximum embedding-degree to search for.  If the true `k` is
    /// larger than this, the check returns
    /// [`SafetyCheck::Pass`] (since the curve is then pairing-safe
    /// for our purposes).  Default: `100`.
    pub max_embedding_degree_search: u32,
    /// Expected deployment size: how many independent keys will
    /// share this curve.  Galbraith-Lin-Scott amortised Pollard rho
    /// reduces per-key ECDLP cost from `O(√n)` to `O(√(n/m))` when
    /// `m` keys share a common generator (the saving applies to a
    /// single attacker who wants any one key, not to per-key
    /// security against independent attackers).  Set this when
    /// auditing a deployment with `≥ 2³⁰` projected keys to surface
    /// the security-margin erosion.  `None` ⇒ check is skipped.
    pub expected_deployment_size: Option<u64>,
    /// Minimum per-key security floor in bits when amortised
    /// multi-target rho is the threat model.  Default: `100` bits
    /// (matches NIST SP 800-57 Cat. 3 minimum).
    pub min_amortised_security_bits: u32,
    /// Maximum prime modulus (in bits) for which the experimental
    /// `Cl(O)`-orbit-brittleness check is allowed to run.  The check
    /// uses brute-force point counting and 2-isogeny BFS, both
    /// infeasible at cryptographic sizes — set this conservatively.
    /// Default: 24 bits (`p < 2²⁴ ≈ 16 M`); above this the check
    /// returns [`SafetyCheck::Inconclusive`].
    pub max_orbit_check_bits: u32,
    /// Maximum CRT-coverage fraction (relative to `log₂(n)`) that
    /// is considered safe.  Coverage above this fraction means the
    /// `Cl(O)`-orbit alone exposes that fraction of the secret via
    /// Pohlig-Hellman + CRT, with the rest susceptible to HNP-residual
    /// cleanup.  Default: `0.25` (a quarter of the secret bits is the
    /// brittleness threshold).
    pub max_orbit_crt_fraction: f64,
    /// Smoothness bound used by the orbit auditor.  Pohlig-Hellman
    /// recovers `d` mod the smooth part with cost `√B`; sub-cryptanalytic
    /// `B` (e.g., 2¹⁵) reflects the realistic attacker.  Default: 2¹⁵.
    pub orbit_smoothness_bound: u64,
    /// Field-extension degree.  `1` (default) means the curve is
    /// over a prime field `F_p` — no Weil-descent / trace-zero
    /// concerns.  `n > 1` means the user is auditing a curve over
    /// `F_{p^n}` and the Gaudry-Schost / Diem index-calculus
    /// machinery becomes relevant: composite `n` is a hard fail
    /// (Frey-Rück + GHS Weil descent reduces ECDLP to a much
    /// smaller index calculus over the Jacobian of a covering
    /// curve), prime `n` ≥ 2 still triggers a warning about
    /// trace-zero subvariety attacks (Galbraith-Lin-Scott,
    /// Faugère-Gaudry-Huot-Joux-Renault summation polynomials).
    pub extension_degree: u32,
}

impl Default for AnalysisOptions {
    fn default() -> Self {
        Self {
            min_order_bits: 200,
            smoothness_bound: 1 << 22,
            min_largest_prime_factor_bits: 160,
            min_private_key_bits: 200,
            max_unsafe_embedding_degree: 6,
            max_embedding_degree_search: 100,
            expected_deployment_size: None,
            min_amortised_security_bits: 100,
            extension_degree: 1,
            max_orbit_check_bits: 24,
            max_orbit_crt_fraction: 0.25,
            orbit_smoothness_bound: 1 << 15,
        }
    }
}

// ── Implementation ───────────────────────────────────────────────────────────

impl CurveParams {
    /// Run the full ECDH/ECDSA parameter audit.
    pub fn analyse(&self, opts: &AnalysisOptions) -> SafetyReport {
        let (order_smoothness, effective_security) =
            self.check_order_smoothness_and_effective_security(opts);
        SafetyReport {
            order_size: self.check_order_size(opts),
            order_smoothness,
            effective_security,
            generator_on_curve: self.check_generator_on_curve(),
            non_singular: self.check_non_singular(),
            non_supersingular: self.check_non_supersingular(opts),
            non_anomalous: self.check_non_anomalous(),
            multi_target_margin: self.check_multi_target_margin(opts),
            no_weil_descent: self.check_no_weil_descent(opts),
            orbit_brittleness: self.check_cl_o_orbit_brittleness(opts),
        }
    }

    // ── Attack 10 (experimental): Cl(O)-orbit brittleness (CGA-HNC) ────
    //
    // See `crate::cryptanalysis::cga_hnc`.  Measures the CRT-coverage of
    // the secret `d` from the curve's 2-isogeny orbit; flags curves
    // whose orbit alone exposes a configurable fraction of `d` via
    // Pohlig-Hellman amortisation + CRT (with the residual recovered
    // by HNP lattice attack).  Only runs at sub-cryptographic curve
    // sizes (configurable via `max_orbit_check_bits`).

    /// `Cl(O)`-orbit brittleness check.  See module docs for
    /// [`crate::cryptanalysis::cga_hnc`].
    pub fn check_cl_o_orbit_brittleness(&self, opts: &AnalysisOptions) -> SafetyCheck {
        // Prime-order curves (cofactor 1, n prime) are immune to
        // CGA-HNC by design: PH has no smooth factors to amortise
        // into.  All standard NIST/secp/brainpool curves satisfy
        // this and trigger the fast `Pass`.
        if self.h == BigUint::from(1u32) && is_prime_big(&self.n) {
            return SafetyCheck::Pass;
        }
        if (self.p.bits() as u32) > opts.max_orbit_check_bits {
            return SafetyCheck::Inconclusive(format!(
                "field prime is {} bits; experimental orbit-brittleness \
                 check supports ≤ {} bits (it relies on brute-force point \
                 counting and 2-isogeny BFS, both infeasible at \
                 cryptographic sizes).  For cryptographic curves, this \
                 check requires offline pre-computation against a \
                 published curve-parameter generator.",
                self.p.bits(),
                opts.max_orbit_check_bits,
            ));
        }
        let p_bigint = self.p.to_bigint().unwrap_or_else(|| BigInt::from(0));
        let a_bigint = self.a.clone();
        let b_bigint = self.b.clone();
        let n_bits = self.n.bits() as f64;
        let report = crate::cryptanalysis::cga_hnc::orbit_smoothness_report(
            &a_bigint,
            &b_bigint,
            &p_bigint,
            opts.orbit_smoothness_bound,
            128,
        );
        let fraction = if n_bits > 0.0 {
            report.total_bits_crt / n_bits
        } else {
            0.0
        };
        if fraction > opts.max_orbit_crt_fraction {
            SafetyCheck::Fail(format!(
                "Cl(O)-orbit alone exposes {:.1}% of d's bits via CRT \
                 (orbit size {}, smoothness bound {}); the residual \
                 {:.1}% can be recovered via HNP-lattice cleanup at \
                 ~2^{:.0} cost — far below the {:.0}-bit nominal \
                 security floor.  Mitigation: use a curve whose \
                 endomorphism ring has class number ≤ 1 (Heegner CM) \
                 or use a curve far from any small-class-number CM \
                 family.",
                fraction * 100.0,
                report.rows.len(),
                opts.orbit_smoothness_bound,
                (1.0 - fraction) * 100.0,
                (1.0 - fraction) * n_bits / 2.0,
                n_bits / 2.0,
            ))
        } else {
            SafetyCheck::Pass
        }
    }

    // ── Attack 9: trace-zero / Weil-descent (extension fields) ──────────
    //
    // Diem 2011 ("On the discrete logarithm problem in elliptic curves
    // over non-prime finite fields"): for curves over `F_{p^n}` with
    // composite `n`, the Frey-Rück Weil descent + Gaudry-Schost-style
    // index calculus on the cover's Jacobian solves ECDLP in
    // subexponential time for moderate `n`.  Trace-zero subvarieties
    // (Frey 1998, Galbraith-Smart) are relevant even for prime `n`.
    //
    // This check only fires when the caller declares the curve as
    // an extension-field curve via `AnalysisOptions::extension_degree`.
    // For prime-field curves (the default, n = 1), it always passes.

    /// Trace-zero / Weil-descent risk check.  Fails for composite
    /// `extension_degree`; warns (passes-with-message in
    /// `Inconclusive`) for prime extension degrees ≥ 2.
    pub fn check_no_weil_descent(&self, opts: &AnalysisOptions) -> SafetyCheck {
        let n_ext = opts.extension_degree;
        if n_ext <= 1 {
            return SafetyCheck::Pass;
        }
        if !is_prime_small(n_ext as u64) {
            // Composite n: hard fail.
            let small_factor = smallest_prime_factor(n_ext as u64);
            return SafetyCheck::Fail(format!(
                "extension degree n = {} is composite (smallest prime \
                 factor = {}); Diem-style Weil descent reduces ECDLP \
                 to index calculus on a degree-{} Jacobian over \
                 F_{{p^{}}} — subexponential.  Use a prime-field \
                 curve (n = 1) or an extension of prime degree.",
                n_ext,
                small_factor,
                small_factor,
                (n_ext as u64) / small_factor,
            ));
        }
        // Prime n ≥ 2: warn but pass.  Trace-zero subvarieties
        // exist, summation polynomials apply, but no concrete
        // subexponential break is known for these at our parameter
        // sizes.  We surface this as `Inconclusive` so an audit
        // gate that requires `Pass` will catch attention.
        SafetyCheck::Inconclusive(format!(
            "extension degree n = {} is prime — no known \
             subexponential ECDLP attack, but trace-zero \
             subvariety techniques (Galbraith-Lin-Scott, \
             Faugère-Gaudry-Huot-Joux-Renault summation \
             polynomials) may give modest speedups.  Confirm the \
             choice is intentional; prime-field curves remain the \
             conservative default for any non-pairing application.",
            n_ext,
        ))
    }

    // ── Attack 8: multi-target / amortised Pollard rho ──────────────────
    //
    // Galbraith-Lin-Scott: when m keys share the same generator
    // and curve, a single rho walk can solve any one of them in
    // O(√(n/m)) operations rather than O(√n).  Per-key effective
    // security bits drop by ½·log₂(m).  Surface this to operators
    // running large deployments.

    /// Multi-target margin check.  Skipped (returns `Pass`) when
    /// `opts.expected_deployment_size` is `None`.  Otherwise the
    /// effective security level is `½·log₂(n) − ½·log₂(m)` bits;
    /// fails if this drops below `opts.min_amortised_security_bits`.
    pub fn check_multi_target_margin(&self, opts: &AnalysisOptions) -> SafetyCheck {
        let m = match opts.expected_deployment_size {
            Some(v) if v >= 1 => v,
            _ => return SafetyCheck::Pass,
        };
        // Effective per-key security bits under amortised rho:
        //   bits = ½·(bits(n) − log₂(m))
        let n_bits = self.n.bits() as f64;
        let m_log2 = (m as f64).log2();
        let effective_bits = 0.5 * (n_bits - m_log2);
        if effective_bits < opts.min_amortised_security_bits as f64 {
            SafetyCheck::Fail(format!(
                "amortised Pollard-rho across {} keys reduces per-key \
                 security from {} bits to {:.1} bits — below the {}-bit \
                 floor.  Mitigation: per-key generator randomisation \
                 (a fresh base point for every key) restores full \
                 √n security.",
                m,
                (n_bits / 2.0).round() as u32,
                effective_bits,
                opts.min_amortised_security_bits,
            ))
        } else {
            SafetyCheck::Pass
        }
    }

    // ── Attack 1: order too small ────────────────────────────────────────

    pub fn check_order_size(&self, opts: &AnalysisOptions) -> SafetyCheck {
        let bits = self.n.bits() as u32;
        if bits < opts.min_order_bits {
            SafetyCheck::Fail(format!(
                "generator order is {} bits; minimum is {} bits — \
                 ECDLP solvable in O(2^{}) via Pollard-rho / BSGS",
                bits,
                opts.min_order_bits,
                bits / 2
            ))
        } else {
            SafetyCheck::Pass
        }
    }

    // ── Attack 2 + 3: order smoothness and effective security ────────────

    /// Returns `(order_smoothness, effective_security)`.  Both checks
    /// share the trial-division work, so we run them together.
    pub fn check_order_smoothness_and_effective_security(
        &self,
        opts: &AnalysisOptions,
    ) -> (SafetyCheck, SafetyCheck) {
        let factors = trial_factor(&self.n, opts.smoothness_bound);

        // Attack 2: largest prime factor of n.
        // Distinguish "fully factored" (no residue) from
        // "trial-divided up to bound; residue may or may not be
        // prime".
        let (smoothness, largest_known_prime) = if let Some(residue) = &factors.residue {
            // Couldn't fully factor.  Check whether the residue is prime.
            if is_prime(residue) {
                let largest = factors
                    .prime_factors
                    .iter()
                    .map(|(p, _)| p)
                    .chain(std::iter::once(residue))
                    .max()
                    .unwrap()
                    .clone();
                (SafetyCheck::Pass, largest)
            } else {
                let largest_small = factors
                    .prime_factors
                    .iter()
                    .map(|(p, _)| p.clone())
                    .max()
                    .unwrap_or(BigUint::zero());
                let msg = format!(
                    "trial division up to 2^{} did not finish; residue \
                     of {} bits is composite — partial smoothness \
                     evidence: largest small prime factor = {}",
                    opts.smoothness_bound.next_power_of_two().trailing_zeros(),
                    residue.bits(),
                    largest_small,
                );
                return (
                    SafetyCheck::Inconclusive(msg.clone()),
                    SafetyCheck::Inconclusive(msg),
                );
            }
        } else {
            // Fully factored.
            let largest = factors
                .prime_factors
                .iter()
                .map(|(p, _)| p.clone())
                .max()
                .unwrap_or(BigUint::zero());
            (SafetyCheck::Pass, largest)
        };

        let smoothness = if let SafetyCheck::Inconclusive(_) = smoothness {
            smoothness
        } else {
            let lpf_bits = largest_known_prime.bits() as u32;
            if lpf_bits < opts.min_largest_prime_factor_bits {
                SafetyCheck::Fail(format!(
                    "largest prime factor of order is {} bits; minimum \
                     is {} bits — Pohlig–Hellman reduces ECDLP to \
                     O(2^{}) via prime-factor decomposition",
                    lpf_bits,
                    opts.min_largest_prime_factor_bits,
                    lpf_bits / 2
                ))
            } else {
                SafetyCheck::Pass
            }
        };

        // Attack 3: effective security given private-key bit budget.
        // An attacker can use prime factors of n whose product fits
        // within the private-key range.  The "effective" sub-group
        // size is the product of the smallest factors covering
        // `min_private_key_bits` bits.
        let mut sorted_factors: Vec<(BigUint, u32)> = factors.prime_factors.clone();
        sorted_factors.sort_by_key(|(p, _)| p.clone());
        let mut covered_bits: u32 = 0;
        let mut largest_used_factor_bits: u32 = 0;
        for (p, e) in &sorted_factors {
            let factor_bits = p.bits() as u32;
            for _ in 0..*e {
                covered_bits = covered_bits.saturating_add(factor_bits);
                if largest_used_factor_bits < factor_bits {
                    largest_used_factor_bits = factor_bits;
                }
                if covered_bits >= opts.min_private_key_bits {
                    break;
                }
            }
            if covered_bits >= opts.min_private_key_bits {
                break;
            }
        }
        let effective_security = if covered_bits >= opts.min_private_key_bits {
            // Attack would need to solve ECDLP in the largest factor used.
            let attack_cost_bits = largest_used_factor_bits / 2;
            if attack_cost_bits < opts.min_largest_prime_factor_bits / 2 {
                SafetyCheck::Fail(format!(
                    "private keys of {} bits are recoverable in O(2^{}) \
                     via Pohlig–Hellman + CRT using only small prime \
                     factors of n (largest required = 2^{})",
                    opts.min_private_key_bits, attack_cost_bits, largest_used_factor_bits
                ))
            } else {
                SafetyCheck::Pass
            }
        } else {
            SafetyCheck::Pass
        };

        (smoothness, effective_security)
    }

    // ── Attack 4: point-on-curve helper ──────────────────────────────────

    /// True iff `(x, y)` satisfies `y² ≡ x³ + a·x + b (mod p)` and both
    /// coordinates are in `[0, p)`.
    pub fn is_point_on_curve(&self, x: &BigUint, y: &BigUint) -> bool {
        if x >= &self.p || y >= &self.p {
            return false;
        }
        let lhs = (y * y) % &self.p;
        let xs = BigInt::from(x.clone());
        let cube = (&xs * &xs * &xs) % BigInt::from(self.p.clone());
        let rhs = (&cube + &self.a * &xs + &self.b) % BigInt::from(self.p.clone());
        let rhs = match rhs.sign() {
            Sign::Minus => (rhs + BigInt::from(self.p.clone())).to_biguint().unwrap(),
            _ => rhs.to_biguint().unwrap(),
        };
        lhs == rhs
    }

    fn check_generator_on_curve(&self) -> SafetyCheck {
        if self.is_point_on_curve(&self.gx, &self.gy) {
            SafetyCheck::Pass
        } else {
            SafetyCheck::Fail(
                "generator (gx, gy) does NOT satisfy y² = x³ + a·x + b (mod p)".to_string(),
            )
        }
    }

    // ── Attack 5: singular curve ─────────────────────────────────────────

    /// True iff `4a³ + 27b² ≡ 0 (mod p)` — the curve has a node or cusp.
    pub fn is_singular(&self) -> bool {
        let p_int = BigInt::from(self.p.clone());
        let a = &self.a % &p_int;
        let b = &self.b % &p_int;
        let four = BigInt::from(4u32);
        let twenty_seven = BigInt::from(27u32);
        let disc = (&four * &a * &a * &a + &twenty_seven * &b * &b) % &p_int;
        let disc = match disc.sign() {
            Sign::Minus => disc + &p_int,
            _ => disc,
        };
        disc.is_zero()
    }

    fn check_non_singular(&self) -> SafetyCheck {
        if self.is_singular() {
            SafetyCheck::Fail(
                "curve is singular: 4a³ + 27b² ≡ 0 (mod p) — ECDLP \
                 collapses to a DLP in F_p (node) or F_p × F_p (cusp)"
                    .to_string(),
            )
        } else {
            SafetyCheck::Pass
        }
    }

    // ── Attack 6: supersingular / small embedding degree ────────────────

    /// Smallest `k ≥ 1` with `p^k ≡ 1 (mod n)`, or `None` if no such
    /// `k ≤ max_k` exists.  This is the embedding degree of the curve
    /// with respect to the chosen generator subgroup.
    pub fn embedding_degree(&self, max_k: u32) -> Option<u32> {
        let one = BigUint::one();
        let mut pk = self.p.clone() % &self.n;
        if pk == one {
            return Some(1);
        }
        for k in 2..=max_k {
            pk = (&pk * &self.p) % &self.n;
            if pk == one {
                return Some(k);
            }
        }
        None
    }

    fn check_non_supersingular(&self, opts: &AnalysisOptions) -> SafetyCheck {
        match self.embedding_degree(opts.max_embedding_degree_search) {
            Some(k) if k <= opts.max_unsafe_embedding_degree => SafetyCheck::Fail(format!(
                "embedding degree k = {} ≤ {} — MOV/Frey–Rück reduces \
                 ECDLP to DLP in F_{{p^{}}}, solvable by index calculus",
                k, opts.max_unsafe_embedding_degree, k
            )),
            Some(_) => SafetyCheck::Pass,
            None => SafetyCheck::Pass,
        }
    }

    // ── Attack 7: anomalous curve (Smart's attack) ───────────────────────

    /// True iff `#E(F_p) = p`, i.e. `n · h == p`.
    pub fn is_anomalous(&self) -> bool {
        &self.n * &self.h == self.p
    }

    fn check_non_anomalous(&self) -> SafetyCheck {
        if self.is_anomalous() {
            SafetyCheck::Fail(
                "curve is anomalous: #E(F_p) = p — Smart's attack solves \
                 ECDLP in O(1) p-adic operations"
                    .to_string(),
            )
        } else {
            SafetyCheck::Pass
        }
    }
}

// ── Helpers ──────────────────────────────────────────────────────────────────

#[derive(Clone, Debug)]
struct FactorResult {
    /// Prime factors found by trial division, with multiplicities.
    prime_factors: Vec<(BigUint, u32)>,
    /// The remaining cofactor if trial division did not finish.
    /// `None` means `n` was fully factored.
    residue: Option<BigUint>,
}

/// Trial-divide `n` by every prime up to `bound`.  Returns the prime
/// factorisation of the smooth part and the remaining cofactor (if
/// any).  Uses a 6k±1 wheel for speed.
fn trial_factor(n: &BigUint, bound: u64) -> FactorResult {
    let mut residue = n.clone();
    let mut factors: Vec<(BigUint, u32)> = Vec::new();
    let one = BigUint::one();

    // Special-case 2 and 3 so the wheel below can start at 5.
    for p in [2u64, 3u64] {
        let pb = BigUint::from(p);
        let mut e = 0u32;
        while &residue % &pb == BigUint::zero() {
            residue /= &pb;
            e += 1;
        }
        if e > 0 {
            factors.push((pb, e));
        }
    }

    let mut p = 5u64;
    let mut step = 2u64;
    while p <= bound {
        let pb = BigUint::from(p);
        if &pb * &pb > residue {
            // Anything left in `residue` is prime if > 1.
            if residue > one {
                factors.push((residue.clone(), 1));
                residue = one.clone();
            }
            break;
        }
        let mut e = 0u32;
        while &residue % &pb == BigUint::zero() {
            residue /= &pb;
            e += 1;
        }
        if e > 0 {
            factors.push((pb, e));
        }
        p += step;
        step = 6 - step; // alternate 2, 4 → 5, 7, 11, 13, 17, 19, …
    }

    let residue_opt = if residue == one { None } else { Some(residue) };
    FactorResult {
        prime_factors: factors,
        residue: residue_opt,
    }
}

// We touch `mod_pow` only through doc-link sanity; pull it in to keep
// re-exports tidy if/when we extend with multiplicative-order checks.
#[allow(dead_code)]
fn _link_mod_pow() {
    let _ = mod_pow;
}

/// Trial-division primality test for small `u64` values — used by
/// the trace-zero check on the (small) extension degree, not on
/// the curve modulus.  At u64 scale this completes in microseconds.
fn is_prime_small(n: u64) -> bool {
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

/// Miller-Rabin-style probabilistic primality test for `BigUint` —
/// used for the prime-order check in
/// [`CurveParams::check_cl_o_orbit_brittleness`].  Delegates to the
/// existing RSA `is_prime` which already handles cryptographic-size
/// inputs.
fn is_prime_big(n: &BigUint) -> bool {
    crate::asymmetric::rsa::is_prime(n)
}

fn smallest_prime_factor(n: u64) -> u64 {
    if n.is_multiple_of(2) {
        return 2;
    }
    let mut d = 3u64;
    while d.saturating_mul(d) <= n {
        if n.is_multiple_of(d) {
            return d;
        }
        d += 2;
    }
    n
}

#[cfg(test)]
mod tests {
    use super::*;
    use num_bigint::BigInt;

    /// secp256k1 — should be safe across every check.
    fn secp256k1() -> CurveParams {
        let p = BigUint::parse_bytes(
            b"FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F",
            16,
        )
        .unwrap();
        let n = BigUint::parse_bytes(
            b"FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141",
            16,
        )
        .unwrap();
        let gx = BigUint::parse_bytes(
            b"79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798",
            16,
        )
        .unwrap();
        let gy = BigUint::parse_bytes(
            b"483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8",
            16,
        )
        .unwrap();
        CurveParams {
            p,
            a: BigInt::from(0),
            b: BigInt::from(7),
            gx,
            gy,
            n,
            h: BigUint::from(1u32),
        }
    }

    #[test]
    fn secp256k1_passes_full_audit() {
        let curve = secp256k1();
        let report = curve.analyse(&AnalysisOptions::default());
        // Use the "no demonstrated failure" semantic, not strict
        // `all_pass`: the experimental orbit-brittleness check
        // returns `Inconclusive` for cryptographic-size curves
        // because it relies on brute-force point counting (gated to
        // ≤ 24-bit `p` by default).  That's the correct posture —
        // the check shouldn't claim "verified safe" when it didn't
        // actually run.
        assert!(
            report.failed_checks().is_empty(),
            "secp256k1 should have no failed checks; got: {:?}",
            report.failed_checks()
        );
    }

    #[test]
    fn secp256k1_generator_is_on_curve() {
        let curve = secp256k1();
        assert!(curve.is_point_on_curve(&curve.gx, &curve.gy));
        // Off-curve point: just bump y by 1.
        let bad_y = (&curve.gy + 1u32) % &curve.p;
        assert!(!curve.is_point_on_curve(&curve.gx, &bad_y));
    }

    #[test]
    fn secp256k1_is_not_anomalous() {
        let curve = secp256k1();
        assert!(!curve.is_anomalous());
    }

    #[test]
    fn secp256k1_is_not_singular() {
        let curve = secp256k1();
        assert!(!curve.is_singular());
    }

    #[test]
    fn secp256k1_embedding_degree_is_high() {
        // For secp256k1 we don't expect to find k ≤ 100 (it's actually
        // ≈ n/2, astronomically large).
        let curve = secp256k1();
        let k = curve.embedding_degree(100);
        assert!(
            k.is_none(),
            "secp256k1 embedding degree should be > 100, got {:?}",
            k
        );
    }

    // ── Failure-case fixtures: deliberately weak curves ────────────────────

    /// Singular curve: choose `a, b` so that `4a³ + 27b² ≡ 0 (mod p)`.
    /// `a = -3, b = 2, p = 7`: 4·(-27) + 27·4 = -108 + 108 = 0.
    #[test]
    fn singular_curve_is_flagged() {
        let curve = CurveParams {
            p: BigUint::from(7u32),
            a: BigInt::from(-3),
            b: BigInt::from(2),
            gx: BigUint::from(0u32),
            gy: BigUint::from(0u32),
            n: BigUint::from(7u32),
            h: BigUint::from(1u32),
        };
        assert!(curve.is_singular());
        let r = curve.check_non_singular();
        assert!(r.is_fail());
    }

    /// Order-too-small curve.  We use real secp256k1's `a, b, p` but
    /// claim a tiny `n` (this is artificial — for testing only).
    #[test]
    fn small_order_is_flagged() {
        let mut curve = secp256k1();
        curve.n = BigUint::from(1_000_003u32); // 20-bit prime
        curve.h = BigUint::from(1u32);
        let r = curve.check_order_size(&AnalysisOptions::default());
        assert!(r.is_fail(), "20-bit order should fail order_size check");
    }

    /// Smooth-order curve: `n = 2 * 3 * 5 * 7 * ... * 257` (primorial-like).
    /// All factors small ⇒ Pohlig–Hellman trivial.
    #[test]
    fn smooth_order_is_flagged() {
        let mut curve = secp256k1();
        // Build a smooth n: 2 × 3 × 5 × 7 × 11 × 13 × 17 × 19 × 23 × 29 × 31 × 37
        let small_primes: Vec<u64> = vec![2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47];
        let mut n = BigUint::one();
        for p in &small_primes {
            n *= BigUint::from(*p);
        }
        curve.n = n;
        let opts = AnalysisOptions {
            min_order_bits: 1, // disable size check for this fixture
            ..AnalysisOptions::default()
        };
        let (smooth, _) = curve.check_order_smoothness_and_effective_security(&opts);
        assert!(smooth.is_fail(), "smooth n should fail smoothness check");
    }

    /// Anomalous curve fixture: pick a small prime and force `n · h = p`.
    #[test]
    fn anomalous_curve_is_flagged() {
        let curve = CurveParams {
            p: BigUint::from(13u32),
            a: BigInt::from(1),
            b: BigInt::from(1),
            gx: BigUint::from(0u32),
            gy: BigUint::from(1u32),
            n: BigUint::from(13u32),
            h: BigUint::from(1u32),
        };
        assert!(curve.is_anomalous());
        let r = curve.check_non_anomalous();
        assert!(r.is_fail());
    }

    /// Supersingular fixture: tiny prime `p` and a curve with embedding
    /// degree 1 (i.e. `n | p − 1`).  We construct one synthetically
    /// without needing to know the exact #E.
    #[test]
    fn small_embedding_degree_is_flagged() {
        // p = 23, n = 11.  p ≡ 1 (mod 11) directly (since 11 | p−1),
        // so embedding degree is 1 — well within the unsafe threshold.
        // For k = 2 specifically: pick p, n with p ≢ 1 (mod n) but
        // p² ≡ 1 (mod n).  E.g. n = 5, p = 4 — but p must be prime.
        // n = 5, p = 19: 19 mod 5 = 4, 4² = 16 mod 5 = 1.  Use that.
        let curve = CurveParams {
            p: BigUint::from(19u32),
            a: BigInt::from(1),
            b: BigInt::from(1),
            gx: BigUint::from(0u32),
            gy: BigUint::from(1u32),
            n: BigUint::from(5u32),
            h: BigUint::from(2u32),
        };
        let k = curve.embedding_degree(10);
        assert_eq!(k, Some(2), "expected embedding degree 2");
        let r = curve.check_non_supersingular(&AnalysisOptions::default());
        assert!(r.is_fail(), "k=2 must trigger MOV warning");
    }

    /// Effective-security check: large n with one big prime factor and
    /// many small ones, but small private keys make small factors
    /// sufficient for Pohlig-Hellman.
    #[test]
    fn small_private_key_with_smooth_subgroup_is_flagged() {
        let mut curve = secp256k1();
        // Build n = (small smooth) * (big prime) artificially.
        let smooth: BigUint = [2u64, 3, 5, 7, 11, 13, 17, 19]
            .iter()
            .map(|p| BigUint::from(*p))
            .product();
        // A 200-bit prime to be the "large" factor.
        let big = BigUint::parse_bytes(b"FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFD", 16)
            .unwrap();
        curve.n = &smooth * &big;
        // If private keys are 32 bits, the smooth product (~32 bits)
        // is enough for Pohlig-Hellman, and effective security ≈ 9 bits
        // (largest small prime = 19, attack cost = √19 < 2^3).
        let opts = AnalysisOptions {
            min_private_key_bits: 32,
            min_order_bits: 1,
            min_largest_prime_factor_bits: 160,
            ..AnalysisOptions::default()
        };
        let (_, eff) = curve.check_order_smoothness_and_effective_security(&opts);
        assert!(eff.is_fail(), "small-key + smooth-subgroup must be flagged");
    }

    /// Trial-division correctness on a known composite.
    #[test]
    fn trial_factor_works() {
        // n = 2^3 · 3 · 5^2 · 7 · 13 = 8·3·25·7·13 = 54600.
        let n = BigUint::from(54600u32);
        let r = trial_factor(&n, 1000);
        assert!(r.residue.is_none(), "fully factored");
        let mut got: Vec<(u64, u32)> = r
            .prime_factors
            .iter()
            .map(|(p, e)| (p.iter_u64_digits().next().unwrap_or(0), *e))
            .collect();
        got.sort();
        assert_eq!(got, vec![(2, 3), (3, 1), (5, 2), (7, 1), (13, 1)]);
    }

    #[test]
    fn report_lists_all_failures() {
        // A maximally bad curve: small singular anomalous everything.
        let curve = CurveParams {
            p: BigUint::from(7u32),
            a: BigInt::from(-3),
            b: BigInt::from(2),
            gx: BigUint::from(99u32), // not on curve
            gy: BigUint::from(99u32),
            n: BigUint::from(7u32),
            h: BigUint::from(1u32),
        };
        let report = curve.analyse(&AnalysisOptions::default());
        assert!(!report.all_pass());
        let failed = report.failed_checks();
        // Must catch at least: small order, generator-off-curve, singular, anomalous.
        for must in &[
            "order_size",
            "generator_on_curve",
            "non_singular",
            "non_anomalous",
        ] {
            assert!(
                failed.contains(must),
                "expected `{}` in failed list, got {:?}",
                must,
                failed
            );
        }
    }

    /// Multi-target: when `expected_deployment_size = None`, the
    /// check is `Pass` regardless of curve size.
    #[test]
    fn multi_target_check_skipped_when_no_deployment_size() {
        let curve = secp256k1();
        let opts = AnalysisOptions::default(); // expected_deployment_size: None
        let r = curve.check_multi_target_margin(&opts);
        assert!(r.is_pass());
    }

    /// secp256k1's 256-bit n gives 128-bit raw rho security.
    /// At deployment size 2³⁰ shared keys, amortised rho per-key
    /// security drops to ½·(256 − 30) = 113 bits — still safely
    /// above the 100-bit floor → Pass.
    #[test]
    fn secp256k1_passes_multi_target_at_2p30_keys() {
        let curve = secp256k1();
        let opts = AnalysisOptions {
            expected_deployment_size: Some(1u64 << 30),
            ..AnalysisOptions::default()
        };
        let r = curve.check_multi_target_margin(&opts);
        assert!(
            r.is_pass(),
            "256-bit curve at 2^30 keys should pass 100-bit floor; got {:?}",
            r
        );
    }

    /// At 2⁶⁰ shared keys, amortised security drops to
    /// ½·(256 − 60) = 98 bits — below the 100-bit floor → Fail.
    #[test]
    fn secp256k1_fails_multi_target_at_2p60_keys() {
        let curve = secp256k1();
        let opts = AnalysisOptions {
            expected_deployment_size: Some(1u64 << 60),
            ..AnalysisOptions::default()
        };
        let r = curve.check_multi_target_margin(&opts);
        assert!(
            r.is_fail(),
            "256-bit curve at 2^60 keys should fail 100-bit floor; got {:?}",
            r
        );
    }

    /// `failed_checks()` must include `multi_target_margin` when it fires.
    #[test]
    fn multi_target_failure_appears_in_report() {
        let curve = secp256k1();
        let opts = AnalysisOptions {
            expected_deployment_size: Some(1u64 << 60),
            ..AnalysisOptions::default()
        };
        let report = curve.analyse(&opts);
        assert!(report.failed_checks().contains(&"multi_target_margin"));
    }

    /// Default (extension_degree = 1, prime field) ⇒ Weil descent check passes.
    #[test]
    fn weil_descent_passes_for_prime_field() {
        let curve = secp256k1();
        let r = curve.check_no_weil_descent(&AnalysisOptions::default());
        assert!(
            r.is_pass(),
            "F_p curve must pass Weil descent check; got {:?}",
            r
        );
    }

    /// Composite extension degree ⇒ hard fail (Diem).
    #[test]
    fn weil_descent_fails_for_composite_extension() {
        let curve = secp256k1();
        let opts = AnalysisOptions {
            extension_degree: 6, // 6 = 2·3, composite
            ..AnalysisOptions::default()
        };
        let r = curve.check_no_weil_descent(&opts);
        assert!(r.is_fail(), "n=6 (composite) must fail; got {:?}", r);
    }

    /// Prime extension degree ⇒ Inconclusive (warn but not hard fail).
    #[test]
    fn weil_descent_inconclusive_for_prime_extension() {
        let curve = secp256k1();
        let opts = AnalysisOptions {
            extension_degree: 5, // prime
            ..AnalysisOptions::default()
        };
        let r = curve.check_no_weil_descent(&opts);
        assert!(
            matches!(r, SafetyCheck::Inconclusive(_)),
            "n=5 must be Inconclusive"
        );
    }

    /// Composite-degree failure surfaces in `failed_checks()`.
    #[test]
    fn weil_descent_failure_appears_in_report() {
        let curve = secp256k1();
        let opts = AnalysisOptions {
            extension_degree: 4,
            ..AnalysisOptions::default()
        };
        let report = curve.analyse(&opts);
        assert!(report.failed_checks().contains(&"no_weil_descent"));
    }

    /// **The cryptographic-curve immunity check.**  CGA-HNC is
    /// structurally inapplicable to prime-order curves with
    /// cofactor 1 — Pohlig-Hellman has no smooth factors of `#E(F_p)`
    /// to amortise into, so no orbit cooperation can recover any
    /// bits of `d`.  All standard cryptographic curves (secp256k1,
    /// P-256, P-224, P-384, P-521, brainpoolP-*) satisfy this and
    /// must return `Pass` immediately, not `Inconclusive`.
    #[test]
    fn orbit_brittleness_passes_secp256k1_immediately() {
        let curve = secp256k1();
        let r = curve.check_cl_o_orbit_brittleness(&AnalysisOptions::default());
        assert!(
            r.is_pass(),
            "secp256k1 has prime order with cofactor 1; must Pass, got {:?}",
            r
        );
    }

    /// Same for any prime-order curve constructed inline.  Verifies
    /// the check doesn't depend on the curve being secp256k1
    /// specifically, only on the cofactor=1 + prime-order property.
    #[test]
    fn orbit_brittleness_passes_any_prime_order_curve() {
        // Synthesise a prime-order curve (small): pick a, b, p and
        // verify n is prime; then run the check.
        let curve = CurveParams {
            // p = 65537 (Fermat prime), a curve we know.  Need to
            // compute n, but for this test we skip — just assert
            // that ANY curve with cofactor 1 and prime n passes.
            p: BigUint::from(65537u32),
            a: BigInt::from(0),
            b: BigInt::from(1),
            gx: BigUint::from(0u32),
            gy: BigUint::from(0u32),
            n: BigUint::from(65521u32), // 65521 is prime
            h: BigUint::from(1u32),
        };
        let r = curve.check_cl_o_orbit_brittleness(&AnalysisOptions::default());
        assert!(r.is_pass(), "prime-order curve must Pass; got {:?}", r);
    }

    /// Composite-order curves are NOT immune.  At toy size, this
    /// hits the brute-force orbit walk and may Fail or Pass
    /// depending on actual brittleness.  We assert only that the
    /// check actually runs (does not return the immunity-Pass
    /// short-circuit).
    #[test]
    fn orbit_brittleness_runs_for_composite_order() {
        let p_bi = BigInt::from(1009);
        let n = crate::cryptanalysis::cga_hnc::count_points_brute(
            &BigInt::from(1),
            &BigInt::from(2),
            &p_bi,
        );
        let curve = CurveParams {
            p: BigUint::from(1009u32),
            a: BigInt::from(1),
            b: BigInt::from(2),
            gx: BigUint::from(0u32),
            gy: BigUint::from(0u32),
            n: BigUint::from(n),
            h: BigUint::from(1u32),
        };
        let opts = AnalysisOptions {
            max_orbit_check_bits: 32,
            max_orbit_crt_fraction: 0.25,
            orbit_smoothness_bound: 50,
            ..AnalysisOptions::default()
        };
        // n_curve = 1008 = 2^4 · 3^2 · 7, NOT prime, so the
        // immunity short-circuit does NOT fire — full brute-force
        // orbit walk runs.  Result is Fail (curve is brittle) or
        // Pass (it isn't); either is acceptable here, just not the
        // immunity-Pass which would imply we never ran the check.
        let r = curve.check_cl_o_orbit_brittleness(&opts);
        // Verify the check actually ran (Fail or Pass with detail).
        // It will be Fail for this curve (it's brittle empirically).
        assert!(
            r.is_fail(),
            "(a=1, b=2)/F_1009 should be flagged brittle; got {:?}",
            r
        );
    }

    /// At toy size: a curve from the experimental sample where the
    /// orbit is large + smooth (a=1, b=2 over F_1009) should fail
    /// the brittleness check at the default 25% threshold.
    /// Verified empirically via the `experiment_p1` driver: this
    /// curve gave CRT/log₂(p) ≈ 1.796 — almost twice over.
    #[test]
    fn orbit_brittleness_flags_brittle_toy_curve() {
        // (a=1, b=2) over F_1009.  We need n (curve order) — compute
        // it brute-force.
        let p_bi = BigInt::from(1009);
        let n = crate::cryptanalysis::cga_hnc::count_points_brute(
            &BigInt::from(1),
            &BigInt::from(2),
            &p_bi,
        );
        let curve = CurveParams {
            p: BigUint::from(1009u32),
            a: BigInt::from(1),
            b: BigInt::from(2),
            gx: BigUint::from(0u32), // not on curve, but irrelevant for orbit check
            gy: BigUint::from(0u32),
            n: BigUint::from(n),
            h: BigUint::from(1u32),
        };
        let opts = AnalysisOptions {
            max_orbit_check_bits: 32,
            max_orbit_crt_fraction: 0.25,
            orbit_smoothness_bound: 50,
            ..AnalysisOptions::default()
        };
        let r = curve.check_cl_o_orbit_brittleness(&opts);
        assert!(
            r.is_fail(),
            "(a=1, b=2)/F_1009 orbit should expose >25% of d via CRT; got {:?}",
            r
        );
    }

    /// At toy size: a Heegner-CM-like curve where the orbit collapses
    /// to size 1 (no neighbours) should pass the brittleness check.
    /// Empirically: (a=17, b=1)/F_1009 had orbit size 1 and CRT = 0.
    #[test]
    fn orbit_brittleness_passes_for_heegner_like_toy() {
        let p_bi = BigInt::from(1009);
        let n = crate::cryptanalysis::cga_hnc::count_points_brute(
            &BigInt::from(17),
            &BigInt::from(1),
            &p_bi,
        );
        let curve = CurveParams {
            p: BigUint::from(1009u32),
            a: BigInt::from(17),
            b: BigInt::from(1),
            gx: BigUint::from(0u32),
            gy: BigUint::from(0u32),
            n: BigUint::from(n),
            h: BigUint::from(1u32),
        };
        let opts = AnalysisOptions {
            max_orbit_check_bits: 32,
            max_orbit_crt_fraction: 0.25,
            orbit_smoothness_bound: 50,
            ..AnalysisOptions::default()
        };
        let r = curve.check_cl_o_orbit_brittleness(&opts);
        // Either Pass or some Inconclusive variant — must NOT Fail.
        assert!(
            !r.is_fail(),
            "(a=17, b=1)/F_1009 orbit is small; should not fail brittleness; got {:?}",
            r
        );
    }

    /// `is_prime_small` smoke test.
    #[test]
    fn is_prime_small_works() {
        for &p in &[
            2u64, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 97, 101, 8191, 65537,
        ] {
            assert!(is_prime_small(p), "expected {} prime", p);
        }
        for &c in &[0u64, 1, 4, 6, 8, 9, 15, 21, 25, 100, 1000] {
            assert!(!is_prime_small(c), "expected {} composite", c);
        }
    }
}
