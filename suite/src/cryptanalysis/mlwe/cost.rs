//! What lattice reduction costs, and what it delivers.
//!
//! Every attack in this module bottoms out in the same two questions:
//!
//! 1. **What does BKZ-β achieve?**  Answered by a *basis profile*: the
//!    predicted lengths `‖b*_i‖` of the Gram–Schmidt vectors after reduction.
//!    See [`Profile`].
//! 2. **What does BKZ-β cost?**  Answered by an *SVP model*: the price of one
//!    call to the shortest-vector oracle in dimension β, times how many calls
//!    BKZ makes. See [`SvpModel`] and [`Reps`].
//!
//! Separating the two matters, because almost every disagreement in the
//! literature about the security of ML-KEM and ML-DSA is a disagreement about
//! question 2 and not question 1. The profile predictions are stable and
//! experimentally well-supported; the cost models span a factor of `2^40` or
//! more between the most conservative ("core-SVP": count one sieve call and
//! nothing else) and the most realistic (count gates, count tours, subtract
//! dimensions for free). A claim that a parameter set is "N bits below its
//! requirement" is nearly always a claim about which of these to use.
//!
//! We implement several and make the caller name one. Nothing here picks a
//! default silently.
//!
//! # References
//!
//! * Y. Chen, *Réduction de réseau et sécurité concrète du chiffrement
//!   complètement homomorphe*, PhD thesis 2013 — the `δ(β)` fit.
//! * Chen and Nguyen, *BKZ 2.0: better lattice security estimates*,
//!   ASIACRYPT 2011 — the simulator this file's [`Profile::simulate_bkz`]
//!   follows (without its small-dimension HKZ head correction, see there).
//! * Becker, Ducas, Gama, Laarhoven, *New directions in nearest neighbor
//!   searching with applications to lattice sieving*, SODA 2016 — the `0.292d`
//!   classical sieving exponent.
//! * Laarhoven, *Search problems in cryptography*, PhD thesis 2015 — the
//!   `0.265d` quantum exponent.
//! * Alkim, Ducas, Pöppelmann, Schwabe, *Post-quantum key exchange — a New
//!   Hope*, USENIX 2016 — the "core-SVP" convention.
//! * Ducas, *Shortest vector from lattice sieving: a few dimensions for free*,
//!   EUROCRYPT 2018 — the `d4f` correction.
//! * Albrecht, Bai, Fouque, Kirchner, Stehlé, Wen and the MATZOV report
//!   (2022) — the gate-count conventions.

use std::f64::consts::{E, PI};

// ── Special functions ────────────────────────────────────────────────────────

/// `ln Γ(x)` for `x > 0`, by the Lanczos approximation (g = 7, n = 9).
///
/// Accurate to roughly 15 significant digits over the range we use it in
/// (`x` from 1 to a few thousand). `std` has no `lgamma`, and every profile
/// prediction needs one, so here it is.
pub fn ln_gamma(x: f64) -> f64 {
    const G: [f64; 9] = [
        0.999_999_999_999_809_9,
        676.520_368_121_885_1,
        -1_259.139_216_722_402_8,
        771.323_428_777_653_1,
        -176.615_029_162_140_6,
        12.507_343_278_686_9,
        -0.138_571_095_265_720_1,
        9.984_369_578_019_572e-6,
        1.505_632_735_149_311_6e-7,
    ];
    if x < 0.5 {
        // Reflection: Γ(x)Γ(1-x) = π / sin(πx).
        return (PI / (PI * x).sin()).ln() - ln_gamma(1.0 - x);
    }
    let x = x - 1.0;
    let mut a = G[0];
    let t = x + 7.5;
    for (i, g) in G.iter().enumerate().skip(1) {
        a += g / (x + i as f64);
    }
    0.5 * (2.0 * PI).ln() + (x + 0.5) * t.ln() - t + a.ln()
}

/// `log2` of the Gaussian-heuristic length in dimension `d` for a lattice of
/// `log2` volume `log2_vol`:
///
/// `gh(d) = (Γ(d/2+1))^{1/d} / √π · vol^{1/d} ≈ √(d/2πe) · vol^{1/d}`.
pub fn gaussian_heuristic_log2(d: usize, log2_vol: f64) -> f64 {
    let d = d as f64;
    ln_gamma(d / 2.0 + 1.0) / (d * std::f64::consts::LN_2) - 0.5 * PI.log2() + log2_vol / d
}

/// The unit-volume Gaussian heuristic, `log2 gh(d)`. Shorthand for
/// `gaussian_heuristic_log2(d, 0.0)`.
pub fn gh_unit_log2(d: usize) -> f64 {
    gaussian_heuristic_log2(d, 0.0)
}

// ── What BKZ-β achieves ──────────────────────────────────────────────────────

/// The root Hermite factor `δ` that BKZ-β reaches, from Chen's fit
///
/// `δ(β) = ( β/(2πe) · (πβ)^{1/β} )^{1/(2(β-1))}`.
///
/// Below `β = 50` the fit is meaningless (BKZ-2 is LLL, whose `δ ≈ 1.0219`),
/// so we clamp the input. Estimates that land below 50 are reported as
/// "trivially broken" rather than trusted to two decimal places.
pub fn delta_from_beta(beta: f64) -> f64 {
    let b = beta.max(50.0);
    let inner = b / (2.0 * PI * E) * (PI * b).powf(1.0 / b);
    inner.powf(1.0 / (2.0 * (b - 1.0)))
}

/// Inverse of [`delta_from_beta`]: the smallest block size reaching `δ`.
///
/// Monotone in `β`, so bisection is exact to the tolerance given.
pub fn beta_from_delta(delta: f64) -> f64 {
    if delta >= delta_from_beta(50.0) {
        return 50.0;
    }
    let (mut lo, mut hi) = (50.0f64, 20_000.0f64);
    for _ in 0..200 {
        let mid = 0.5 * (lo + hi);
        if delta_from_beta(mid) > delta {
            lo = mid;
        } else {
            hi = mid;
        }
    }
    hi
}

/// The `log2` lengths of the Gram–Schmidt vectors of a reduced basis.
///
/// Index 0 is `‖b*_0‖`, the shortest vector the basis exposes. All lengths are
/// `log2`, because everything downstream is a comparison of exponents.
#[derive(Clone, Debug, PartialEq)]
pub struct Profile {
    /// `log2 ‖b*_i‖`, length `d`.
    pub log2_norms: Vec<f64>,
}

impl Profile {
    /// Dimension.
    pub fn dim(&self) -> usize {
        self.log2_norms.len()
    }

    /// `log2` of the lattice volume, i.e. the sum of the profile.
    pub fn log2_volume(&self) -> f64 {
        self.log2_norms.iter().sum()
    }

    /// The geometric-series-assumption profile: a straight line of slope
    /// `-2 log2 δ` through the volume constraint.
    ///
    /// `log2 ‖b*_i‖ = (d - 1 - 2i)·log2 δ + log2_vol / d`.
    ///
    /// This is the workhorse prediction and the one the closed-form primal and
    /// dual conditions assume. It is wrong for q-ary lattices at small block
    /// size — see [`Self::zgsa`].
    pub fn gsa(d: usize, log2_vol: f64, delta: f64) -> Self {
        let ld = delta.log2();
        let log2_norms = (0..d)
            .map(|i| (d as f64 - 1.0 - 2.0 * i as f64) * ld + log2_vol / d as f64)
            .collect();
        Profile { log2_norms }
    }

    /// The "z-shape" profile of a q-ary lattice under BKZ-β.
    ///
    /// A basis of `Λ_q(A) = {x : x ≡ A^T y mod q}` in dimension `d` with `n`
    /// "short" directions starts out with `d - n` vectors of length `q` and `n`
    /// of length 1. Reduction eats into that from both ends: the GSA line only
    /// holds in the middle, while a head of untouched length-`q` vectors and a
    /// tail of untouched length-1 vectors survive. Ignoring this — using
    /// [`Self::gsa`] on a q-ary lattice at low block size — overstates what
    /// reduction achieves, sometimes badly.
    ///
    /// The direction of GSA's error is worth being precise about, because it is
    /// easy to state backwards. At low block size the GSA line, extended over a
    /// q-ary lattice, predicts `‖b*_0‖ > q` at the head and `‖b*_i‖ < 1` at the
    /// tail. Both are impossible: the lattice contains `q·e_i` and it contains
    /// `e_i`-like unit directions. So GSA is not "optimistic" or "pessimistic"
    /// there, it is simply invalid, and the clamping below is what makes the
    /// prediction a possible basis at all.
    ///
    /// Construction: take the GSA line of slope `-2 log2 δ`, clamp it to
    /// `[0, log2 q]`, then shift it so the volume comes out right. The shift is
    /// found by bisection because the clamping makes the volume a nonlinear
    /// (but monotone) function of it.
    pub fn zgsa(d: usize, n: usize, q: u64, delta: f64) -> Self {
        let log2_q = (q as f64).log2();
        // Volume of the q-ary lattice: q^{d-n}.
        let target_vol = (d - n) as f64 * log2_q;
        let ld = delta.log2();
        let line = |i: usize, shift: f64| (d as f64 - 1.0 - 2.0 * i as f64) * ld + shift;
        let vol_at = |shift: f64| -> f64 {
            (0..d)
                .map(|i| line(i, shift).clamp(0.0, log2_q))
                .sum::<f64>()
        };
        // vol_at is nondecreasing in shift, from 0 (all clamped low) to d·log2 q.
        let (mut lo, mut hi) = (-(d as f64) * ld - log2_q, d as f64 * ld + log2_q);
        for _ in 0..200 {
            let mid = 0.5 * (lo + hi);
            if vol_at(mid) < target_vol {
                lo = mid;
            } else {
                hi = mid;
            }
        }
        let shift = 0.5 * (lo + hi);
        Profile {
            log2_norms: (0..d).map(|i| line(i, shift).clamp(0.0, log2_q)).collect(),
        }
    }

    /// Run the BKZ simulator: `tours` passes of a β-SVP oracle over the basis.
    ///
    /// For each window `[i, i+β)` the oracle is assumed to return a vector of
    /// exactly the Gaussian-heuristic length for that window's sublattice, and
    /// the profile is updated to put that length at position `i` while
    /// preserving the window's volume. This is Chen–Nguyen's BKZ 2.0 simulator
    /// with one omission, stated plainly because it matters:
    ///
    /// **We do not apply the HKZ head correction.** CN11 replaces the last
    /// `≈45` positions with the tabulated profile of an HKZ-reduced random
    /// unit-volume lattice, because the Gaussian heuristic is inaccurate in
    /// very small dimension. Without it the tail of the profile is somewhat
    /// off. That tail does not enter the primal condition (which reads
    /// `‖b*_0‖`) or the dual condition (which reads the head), so the omission
    /// does not move the estimates in this module; it would matter for a
    /// "pressed-down" or tail-reading attack.
    ///
    /// Returns the profile after the tours. Monotone: lengths at the head never
    /// increase.
    pub fn simulate_bkz(mut self, beta: usize, tours: usize) -> Self {
        let d = self.dim();
        if beta >= d {
            // One SVP call on the whole lattice: the Gaussian heuristic, and
            // then the rest of the profile flattened to preserve the volume.
            let vol = self.log2_volume();
            let head = gaussian_heuristic_log2(d, vol);
            let mut norms = vec![0.0; d];
            norms[0] = head;
            let rest = (vol - head) / (d - 1) as f64;
            for n in norms.iter_mut().skip(1) {
                *n = rest;
            }
            self.log2_norms = norms;
            return self;
        }
        let gh = gh_unit_log2(beta);
        for _ in 0..tours {
            let mut changed = false;
            for i in 0..=(d - beta) {
                let window: f64 = self.log2_norms[i..i + beta].iter().sum();
                let predicted = gh + window / beta as f64;
                if predicted < self.log2_norms[i] - 1e-12 {
                    // Put the shorter vector at i and spread the slack over
                    // the rest of the window, preserving its volume.
                    let slack = self.log2_norms[i] - predicted;
                    self.log2_norms[i] = predicted;
                    let share = slack / (beta - 1) as f64;
                    for j in i + 1..i + beta {
                        self.log2_norms[j] += share;
                    }
                    changed = true;
                }
            }
            if !changed {
                break;
            }
        }
        self
    }
}

// ── What BKZ-β costs ─────────────────────────────────────────────────────────

/// A model for the cost of one call to a β-dimensional SVP oracle.
///
/// The variants differ in what they count, not in what they do, and the spread
/// between them is the single largest source of disagreement in published
/// estimates for these schemes.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum SvpModel {
    /// `2^{0.292β}` — classical sieving (BDGL16) with no additive term.
    ///
    /// The "core-SVP" convention of ADPS16: deliberately conservative, in that
    /// it charges the attacker for exactly one sieve call and for no memory
    /// access, no BKZ tours, and no polynomial factors. Kyber and Dilithium's
    /// headline security numbers are in this model. It is *not* comparable to
    /// NIST's gate-count floors; see [`super::params::Category`].
    CoreSvpClassical,
    /// `2^{0.265β}` — quantum sieving (Laarhoven's quantum random walks) under
    /// the same core-SVP convention. Note how little it buys: the entire known
    /// quantum advantage against these schemes is this exponent change.
    CoreSvpQuantum,
    /// `2^{0.292β + 16.4}` — classical sieving counted in logical gates, the
    /// convention of the round-3 Kyber and Dilithium documents. The `+16.4` is
    /// the measured overhead of BDGL's bucketing per sieve call.
    GateCount,
    /// `2^{0.349β}` — sieving charged for *memory access* as well as
    /// operations, on the view that a `2^{0.292β}`-sized database cannot be
    /// touched at unit cost. The exponent is the RAM-model-free "real cost of
    /// sieving" position; it raises security substantially and is the least
    /// attacker-friendly of the sieving models here.
    SieveWithMemoryAccess,
    /// Enumeration with extreme pruning: `2^{0.187 β log2 β - 1.019 β + 16.1}`.
    ///
    /// Superexponential, so it loses to sieving above `β ≈ 400`, but it uses
    /// *polynomial* memory, which sieving does not. Included so the comparison
    /// is visible. The three constants are the published quadratic fit of
    /// Albrecht–Bai–Fouque–Kirchner–Stehlé–Wen, not something derived here.
    Enumeration,
    /// A caller-supplied `a·β + b` in the exponent, for sweeping the model
    /// space or reproducing a paper's convention.
    Custom {
        /// Slope in the `log2` cost.
        a_millis: i64,
        /// Intercept in the `log2` cost, in thousandths (so the enum stays
        /// `Eq`, which the CLI's argument plumbing wants).
        b_millis: i64,
    },
}

impl SvpModel {
    /// `log2` of the cost of one SVP call in dimension `beta`.
    pub fn log2_cost(self, beta: f64) -> f64 {
        match self {
            SvpModel::CoreSvpClassical => 0.292 * beta,
            SvpModel::CoreSvpQuantum => 0.265 * beta,
            SvpModel::GateCount => 0.292 * beta + 16.4,
            SvpModel::SieveWithMemoryAccess => 0.349 * beta,
            SvpModel::Enumeration => {
                let b = beta.max(2.0);
                0.187 * b * b.log2() - 1.019 * b + 16.1
            }
            SvpModel::Custom { a_millis, b_millis } => {
                a_millis as f64 / 1000.0 * beta + b_millis as f64 / 1000.0
            }
        }
    }

    /// `log2` of the memory one SVP call needs.
    ///
    /// Sieving's database holds `2^{0.2075β}` vectors (the `(4/3)^{β/2}` list
    /// size); enumeration is polynomial, which we charge as `log2 β`.
    pub fn log2_memory(self, beta: f64) -> f64 {
        match self {
            SvpModel::Enumeration => beta.max(2.0).log2(),
            _ => 0.2075 * beta,
        }
    }

    /// Whether this model charges a quantum attacker.
    pub fn is_quantum(self) -> bool {
        matches!(self, SvpModel::CoreSvpQuantum)
    }

    /// A short label for reports.
    pub fn label(self) -> String {
        match self {
            SvpModel::CoreSvpClassical => "core-svp-classical".into(),
            SvpModel::CoreSvpQuantum => "core-svp-quantum".into(),
            SvpModel::GateCount => "gate-count".into(),
            SvpModel::SieveWithMemoryAccess => "sieve-memory".into(),
            SvpModel::Enumeration => "enumeration".into(),
            SvpModel::Custom { a_millis, b_millis } => format!(
                "custom({}β+{})",
                a_millis as f64 / 1000.0,
                b_millis as f64 / 1000.0
            ),
        }
    }

    /// Parse a CLI spelling.
    pub fn parse(s: &str) -> Option<Self> {
        match s.to_ascii_lowercase().replace('_', "-").as_str() {
            "core-svp-classical" | "classical" | "core-svp" => Some(SvpModel::CoreSvpClassical),
            "core-svp-quantum" | "quantum" => Some(SvpModel::CoreSvpQuantum),
            "gate-count" | "gates" => Some(SvpModel::GateCount),
            "sieve-memory" | "memory" => Some(SvpModel::SieveWithMemoryAccess),
            "enumeration" | "enum" => Some(SvpModel::Enumeration),
            _ => None,
        }
    }

    /// Every named model, for sweeps and the report table.
    pub fn all() -> Vec<Self> {
        vec![
            SvpModel::CoreSvpClassical,
            SvpModel::CoreSvpQuantum,
            SvpModel::GateCount,
            SvpModel::SieveWithMemoryAccess,
            SvpModel::Enumeration,
        ]
    }
}

/// How many SVP calls BKZ is charged for.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Reps {
    /// One. The core-SVP convention: charge for the last block and nothing
    /// else. Conservative by construction.
    CoreSvpOnly,
    /// `tours · (d - β)` calls, the honest count for a BKZ implementation.
    /// Eight tours is the usual choice and what BKZ 2.0's auto-abort reaches.
    Tours(usize),
}

/// Dimensions for free (Ducas 2018): a sieve in dimension `β` also solves SVP
/// in dimension `β + d4f(β)`, so the block size that has to be *paid for* is
/// smaller than the block size achieved.
///
/// `d4f(β) = β·ln(4/3) / ln(β / 2πe)`, floored at 0.
pub fn dimensions_for_free(beta: f64) -> f64 {
    let denom = (beta / (2.0 * PI * E)).ln();
    if denom <= 0.0 {
        return 0.0;
    }
    (beta * (4.0f64 / 3.0).ln() / denom).max(0.0)
}

/// A fully specified reduction cost model: an SVP oracle, a call count, and
/// whether to subtract dimensions for free.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct BkzModel {
    pub svp: SvpModel,
    pub reps: Reps,
    /// Subtract [`dimensions_for_free`] from the paid block size.
    pub d4f: bool,
}

impl BkzModel {
    /// The bare core-SVP model, classical. What Kyber's and Dilithium's
    /// headline numbers use.
    pub fn core_svp_classical() -> Self {
        BkzModel {
            svp: SvpModel::CoreSvpClassical,
            reps: Reps::CoreSvpOnly,
            d4f: false,
        }
    }

    /// The bare core-SVP model, quantum.
    pub fn core_svp_quantum() -> Self {
        BkzModel {
            svp: SvpModel::CoreSvpQuantum,
            reps: Reps::CoreSvpOnly,
            d4f: false,
        }
    }

    /// A gate-count model with eight tours and dimensions for free — the most
    /// attacker-friendly combination in this file, and the one to use when
    /// comparing against NIST's gate floors.
    pub fn gate_count_realistic() -> Self {
        BkzModel {
            svp: SvpModel::GateCount,
            reps: Reps::Tours(8),
            d4f: true,
        }
    }

    /// Build from an SVP model, keeping core-SVP conventions.
    pub fn from_svp(svp: SvpModel) -> Self {
        BkzModel {
            svp,
            reps: Reps::CoreSvpOnly,
            d4f: false,
        }
    }

    /// `log2` cost of BKZ-`beta` on a dimension-`d` basis.
    pub fn log2_cost(&self, beta: f64, d: usize) -> f64 {
        let paid = if self.d4f {
            (beta - dimensions_for_free(beta)).max(2.0)
        } else {
            beta
        };
        let one = self.svp.log2_cost(paid);
        match self.reps {
            Reps::CoreSvpOnly => one,
            Reps::Tours(t) => {
                let calls = (t as f64 * (d as f64 - beta).max(1.0)).max(1.0);
                one + calls.log2()
            }
        }
    }

    /// `log2` memory of BKZ-`beta`. Tours do not add memory — the database is
    /// reused — so this is the SVP model's figure at the paid block size.
    pub fn log2_memory(&self, beta: f64) -> f64 {
        let paid = if self.d4f {
            (beta - dimensions_for_free(beta)).max(2.0)
        } else {
            beta
        };
        self.svp.log2_memory(paid)
    }

    /// A short label for reports.
    pub fn label(&self) -> String {
        let mut s = self.svp.label();
        if let Reps::Tours(t) = self.reps {
            s.push_str(&format!("+{t}tours"));
        }
        if self.d4f {
            s.push_str("+d4f");
        }
        s
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ln_gamma_matches_known_values() {
        // Γ(1) = Γ(2) = 1.
        assert!(ln_gamma(1.0).abs() < 1e-12);
        assert!(ln_gamma(2.0).abs() < 1e-12);
        // Γ(1/2) = √π.
        assert!((ln_gamma(0.5) - PI.sqrt().ln()).abs() < 1e-12);
        // Γ(n+1) = n! for small n.
        let mut fact = 1.0f64;
        for n in 1..=20u32 {
            fact *= n as f64;
            assert!(
                (ln_gamma(n as f64 + 1.0) - fact.ln()).abs() < 1e-9,
                "n = {n}"
            );
        }
        // Γ(6.5) = 5.5·4.5·3.5·2.5·1.5·0.5·√π.
        let expect: f64 = [5.5, 4.5, 3.5, 2.5, 1.5, 0.5].iter().product::<f64>() * PI.sqrt();
        assert!((ln_gamma(6.5) - expect.ln()).abs() < 1e-10);
    }

    #[test]
    fn gaussian_heuristic_grows_like_sqrt_dim() {
        // gh(d) ≈ √(d/2πe) for unit volume. The approximation drops the
        // Stirling correction, which is worth about 0.06 bits at d = 64 and
        // shrinks as 1/d — so we check both the size of the gap and that it
        // closes.
        let mut prev_gap = f64::INFINITY;
        for d in [64usize, 256, 1024, 4096] {
            let approx = (d as f64 / (2.0 * PI * E)).sqrt().log2();
            let exact = gh_unit_log2(d);
            let gap = (exact - approx).abs();
            assert!(gap < 0.07, "d = {d}: {exact} vs {approx}");
            assert!(gap < prev_gap, "gap did not shrink at d = {d}");
            prev_gap = gap;
        }
        // Volume scaling is exactly vol^{1/d}.
        let a = gaussian_heuristic_log2(100, 0.0);
        let b = gaussian_heuristic_log2(100, 100.0);
        assert!((b - a - 1.0).abs() < 1e-12);
    }

    #[test]
    fn delta_is_decreasing_and_hits_the_known_landmarks() {
        // δ decreases as β grows: more reduction, shorter vectors.
        let mut prev = delta_from_beta(50.0);
        for beta in (60..1500).step_by(10) {
            let d = delta_from_beta(beta as f64);
            assert!(d < prev, "δ rose at β = {beta}");
            prev = d;
        }
        // BKZ-60 sits near δ ≈ 1.01, BKZ-500 near 1.0034 — the values quoted
        // throughout the literature. Loose bounds: this is a fit, not a law.
        assert!((delta_from_beta(60.0) - 1.0100).abs() < 0.002);
        assert!((delta_from_beta(500.0) - 1.0034).abs() < 0.001);
        // δ → 1 from above, always.
        assert!(delta_from_beta(10_000.0) > 1.0);
        assert!(delta_from_beta(10_000.0) < 1.001);
    }

    #[test]
    fn beta_from_delta_inverts_delta_from_beta() {
        for beta in [60.0f64, 100.0, 250.0, 400.0, 873.0, 1500.0] {
            let d = delta_from_beta(beta);
            let back = beta_from_delta(d);
            assert!((back - beta).abs() < 0.5, "β = {beta} → {back}");
        }
    }

    #[test]
    fn gsa_profile_respects_the_volume_and_slopes_down() {
        let (d, vol) = (200usize, 300.0f64);
        let p = Profile::gsa(d, vol, delta_from_beta(80.0));
        assert!((p.log2_volume() - vol).abs() < 1e-9);
        for w in p.log2_norms.windows(2) {
            assert!(w[1] < w[0]);
        }
        // Slope is exactly -2 log2 δ.
        let slope = p.log2_norms[1] - p.log2_norms[0];
        assert!((slope + 2.0 * delta_from_beta(80.0).log2()).abs() < 1e-12);
    }

    #[test]
    fn zgsa_respects_the_qary_volume_and_the_clamps() {
        let (d, n, q) = (600usize, 256usize, 3329u64);
        let p = Profile::zgsa(d, n, q, delta_from_beta(400.0));
        let target = (d - n) as f64 * (q as f64).log2();
        assert!(
            (p.log2_volume() - target).abs() < 1e-6,
            "volume {} vs {}",
            p.log2_volume(),
            target
        );
        let log2q = (q as f64).log2();
        for &v in &p.log2_norms {
            assert!(v >= -1e-9 && v <= log2q + 1e-9);
        }
        // Non-increasing.
        for w in p.log2_norms.windows(2) {
            assert!(w[1] <= w[0] + 1e-9);
        }
    }

    #[test]
    fn gsa_is_invalid_on_a_qary_lattice_at_small_block_size() {
        // The whole point of the z-shape. At β = 60 on this lattice the GSA
        // line predicts a head *longer than q* and a tail *shorter than 1*,
        // neither of which any basis of a q-ary lattice can have. The z-shape
        // clamps to the possible.
        let (d, n, q) = (700usize, 256usize, 3329u64);
        let log2_q = (q as f64).log2();
        let delta = delta_from_beta(60.0);
        let z = Profile::zgsa(d, n, q, delta);
        let g = Profile::gsa(d, (d - n) as f64 * log2_q, delta);
        assert!(
            g.log2_norms[0] > log2_q,
            "GSA head {} should exceed log2 q = {log2_q} here",
            g.log2_norms[0]
        );
        assert!(
            g.log2_norms[d - 1] < 0.0,
            "GSA tail should fall below 1 here"
        );
        assert!(z.log2_norms[0] <= log2_q + 1e-9);
        assert!(z.log2_norms[d - 1] >= -1e-9);
        // At a block size large enough that GSA is valid, the two agree.
        let delta = delta_from_beta(700.0);
        let z = Profile::zgsa(d, n, q, delta);
        let g = Profile::gsa(d, (d - n) as f64 * log2_q, delta);
        assert!(
            (z.log2_norms[0] - g.log2_norms[0]).abs() < 1.0,
            "z-shape {} vs GSA {} at β = 700",
            z.log2_norms[0],
            g.log2_norms[0]
        );
    }

    #[test]
    fn bkz_simulation_shortens_the_head_and_keeps_the_volume() {
        let (d, vol) = (180usize, 400.0f64);
        let start = Profile::gsa(d, vol, delta_from_beta(50.0));
        let head0 = start.log2_norms[0];
        let after = start.clone().simulate_bkz(60, 8);
        assert!(after.log2_norms[0] < head0, "head did not shorten");
        assert!(
            (after.log2_volume() - vol).abs() < 1e-6,
            "volume moved: {} vs {vol}",
            after.log2_volume()
        );
        // A bigger block size must not do worse.
        let bigger = start.clone().simulate_bkz(100, 8);
        assert!(bigger.log2_norms[0] <= after.log2_norms[0] + 1e-9);
    }

    #[test]
    fn bkz_simulation_agrees_with_gsa_to_within_a_few_bits() {
        // The simulator and the closed-form δ fit are independent predictions
        // of the same quantity. They should not disagree wildly.
        let (d, n, q) = (500usize, 200usize, 3329u64);
        let vol = (d - n) as f64 * (q as f64).log2();
        for beta in [60usize, 100, 200] {
            let sim = Profile::zgsa(d, n, q, delta_from_beta(50.0))
                .simulate_bkz(beta, 20)
                .log2_norms[0];
            let closed = Profile::gsa(d, vol, delta_from_beta(beta as f64)).log2_norms[0];
            assert!(
                (sim - closed).abs() < 6.0,
                "β = {beta}: simulator {sim}, δ-fit {closed}"
            );
        }
    }

    #[test]
    fn beta_at_least_dim_collapses_to_one_svp_call() {
        let p = Profile::gsa(40, 80.0, delta_from_beta(50.0)).simulate_bkz(40, 1);
        assert!((p.log2_volume() - 80.0).abs() < 1e-9);
        assert!((p.log2_norms[0] - gaussian_heuristic_log2(40, 80.0)).abs() < 1e-9);
    }

    #[test]
    fn svp_models_are_ordered_as_expected() {
        let beta = 400.0;
        let q = SvpModel::CoreSvpQuantum.log2_cost(beta);
        let c = SvpModel::CoreSvpClassical.log2_cost(beta);
        let g = SvpModel::GateCount.log2_cost(beta);
        let m = SvpModel::SieveWithMemoryAccess.log2_cost(beta);
        assert!(q < c, "quantum should be cheaper than classical");
        assert!(c < g, "gate count adds overhead");
        assert!(
            g < m,
            "charging for memory access should dominate at β = 400"
        );
        // The entire quantum advantage: about 10% of the exponent.
        assert!((1.0 - q / c - 0.0925).abs() < 0.01);
    }

    #[test]
    fn enumeration_loses_to_sieving_in_high_dimension() {
        // Superexponential vs exponential: enumeration wins small, loses big.
        // The comparison has to be against GateCount, not CoreSvpClassical:
        // the enumeration fit carries a +16.1 constant and core-SVP carries
        // none, so comparing those two is comparing a gate count against an
        // operation count and enumeration would appear to lose everywhere.
        assert!(SvpModel::Enumeration.log2_cost(100.0) < SvpModel::GateCount.log2_cost(100.0));
        assert!(SvpModel::Enumeration.log2_cost(600.0) > SvpModel::GateCount.log2_cost(600.0));
        // The crossover is somewhere in between, and it is unique because the
        // difference is convex in β.
        let crossing: Vec<usize> = (100..600)
            .filter(|&b| {
                let lhs = SvpModel::Enumeration.log2_cost(b as f64)
                    - SvpModel::GateCount.log2_cost(b as f64);
                let prev = SvpModel::Enumeration.log2_cost(b as f64 - 1.0)
                    - SvpModel::GateCount.log2_cost(b as f64 - 1.0);
                prev < 0.0 && lhs >= 0.0
            })
            .collect();
        assert_eq!(crossing.len(), 1, "crossover not unique: {crossing:?}");
        // …but with polynomial memory, which is its whole point.
        assert!(SvpModel::Enumeration.log2_memory(600.0) < 20.0);
        assert!(SvpModel::CoreSvpClassical.log2_memory(600.0) > 100.0);
    }

    #[test]
    fn dimensions_for_free_is_a_modest_discount() {
        // d4f(β) is roughly β/ln β · 0.288: tens of dimensions, not hundreds.
        for beta in [200.0f64, 400.0, 800.0] {
            let d = dimensions_for_free(beta);
            assert!(d > 0.0 && d < beta / 3.0, "β = {beta}: d4f = {d}");
        }
        // It is worthless below the sieve's own dimension threshold.
        assert_eq!(dimensions_for_free(10.0), 0.0);
    }

    #[test]
    fn tours_and_d4f_move_the_cost_in_the_expected_directions() {
        let (beta, d) = (400.0, 800usize);
        let bare = BkzModel::from_svp(SvpModel::CoreSvpClassical);
        let with_tours = BkzModel {
            svp: SvpModel::CoreSvpClassical,
            reps: Reps::Tours(8),
            d4f: false,
        };
        let with_d4f = BkzModel {
            svp: SvpModel::CoreSvpClassical,
            reps: Reps::CoreSvpOnly,
            d4f: true,
        };
        assert!(with_tours.log2_cost(beta, d) > bare.log2_cost(beta, d));
        assert!(with_d4f.log2_cost(beta, d) < bare.log2_cost(beta, d));
        // Tours add only log2(8·(d-β)) ≈ 15 bits: the reason core-SVP's
        // "charge for one call" is not as generous as it sounds.
        assert!(with_tours.log2_cost(beta, d) - bare.log2_cost(beta, d) < 16.0);
    }

    #[test]
    fn model_labels_round_trip_through_the_parser() {
        for m in SvpModel::all() {
            assert_eq!(SvpModel::parse(&m.label()), Some(m), "{}", m.label());
        }
        assert!(SvpModel::parse("nonsense").is_none());
    }
}
