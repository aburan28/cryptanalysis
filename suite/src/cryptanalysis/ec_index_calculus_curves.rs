//! **Prime-field curve types for index calculus**, and the Semaev
//! reference solvers dispatched by type.
//!
//! The summation-polynomial literature treats three prime-field families
//! differently, and `a`, `b` alone decide which a curve is in:
//!
//! - **generic** — `y² = x³ + ax + b`, `a, b ≠ 0`: NIST P-192 … P-521, the
//!   SECG `r1` curves, Brainpool, SM2, GOST.  `Aut(E) = {±1}`.
//! - **`j = 0`** — `y² = x³ + b`: the SECG Koblitz curves `secp160k1` …
//!   `secp256k1`, BLS12-381 G1.  With `p ≡ 1 (3)` the GLV endomorphism
//!   `ψ(x, y) = (ζx, y)` makes `Aut(E) = μ₆`.
//! - **`j = 1728`** — `y² = x³ + ax`.  With `p ≡ 1 (4)`, `ι(x, y) = (−x, iy)`
//!   makes `Aut(E) = μ₄`; the rational 2-torsion point `(0, 0)` forces an
//!   even group order.
//!
//! This module holds the parts that work on curves of any size in the
//! general `num-bigint` arithmetic:
//!
//! 1. [`CurveKind`], [`classify`] and [`j_invariant`].
//! 2. [`endomorphism_facts`]: what the index calculus and the
//!    automorphism-folded rho exploit, computed and checked on the actual
//!    parameters — the cube root of unity `ζ`, the GLV eigenvalue `λ` with
//!    `ψ(G) = [λ]G`, the `ζ`-equivariance of Semaev's `S₃` on a `j = 0`
//!    curve, `|Aut(E)|`, and the `√|Aut(E)|` rho speed-up.  For secp256k1
//!    or P-224 this is exact and cheap; no logarithm is attempted.
//! 3. [`solve_scaled_instance`]: the reference Semaev solvers of
//!    [`crate::cryptanalysis::ec_index_calculus`] (`S₃` 2-decomposition)
//!    and [`crate::cryptanalysis::ec_index_calculus_j0`] (the `ζ`-orbit
//!    and Eisenstein-lattice bases) with the reference rho, on a
//!    [`ScaledInstance`].
//!
//! The fast pipeline — certified scaled-down curves up to 62 bits, factor
//! bases of full automorphism orbits, relation collection, exact
//! logarithms and descent, and a batched rho baseline — is
//! [`crate::cryptanalysis::prime_orbit_index_calculus`], whose
//! [`GeneratedInstance::scaled`](crate::cryptanalysis::prime_orbit_index_calculus::GeneratedInstance::scaled)
//! produces the instances this module solves.
//!
//! # What the reference solvers are for
//!
//! Cross-validation.  They decompose by solving Semaev's `S₃` rather than
//! by table lookup, in the general arithmetic, and are `O(p^{3/2})`, so
//! they are practical to about 24 bits.  Their `j = 0` variant keeps one
//! representative per `ζ`-orbit but accepts only decompositions through
//! the stored representatives, so it gains factor-base size, not relation
//! coverage — see the orbit engine for the variant that uses the whole
//! orbit.

use crate::cryptanalysis::ec_index_calculus::{ec_index_calculus_dlp, pollard_rho_ecdlp};
use crate::cryptanalysis::ec_index_calculus_j0::{
    cube_root_of_unity, eisenstein_smooth_ic_dlp, j0_index_calculus_dlp, psi_eigenvalue,
    verify_s3_zeta_equivariance,
};
use crate::ecc::curve::CurveParams;
use crate::ecc::point::Point;
use num_bigint::BigUint;
use num_traits::{ToPrimitive, Zero};
use rand::rngs::StdRng;
use rand::{Rng, SeedableRng};
use std::time::Instant;

/// Largest field the reference Semaev solvers are run at.  They are
/// `O(p^{3/2})` in the general arithmetic: 24 bits is a few minutes.
pub const MAX_SEMAEV_BITS: u32 = 24;

/// The three curve families the summation-polynomial literature treats
/// differently, decided by the short-Weierstrass coefficients alone.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum CurveKind {
    /// `y² = x³ + a x + b` with `a, b ≠ 0`: automorphism group `{±1}`.
    Generic,
    /// `y² = x³ + b` (`a = 0`), `j = 0`: the Koblitz-style prime curves
    /// (`secp256k1`, `secpXXXk1`).  Order-6 automorphisms when `p ≡ 1 (3)`.
    J0,
    /// `y² = x³ + a x` (`b = 0`), `j = 1728`: order-4 automorphisms when
    /// `p ≡ 1 (4)`.
    J1728,
}

impl CurveKind {
    /// The stable lowercase tag used in reports and on the command line.
    pub fn as_str(self) -> &'static str {
        match self {
            CurveKind::Generic => "generic",
            CurveKind::J0 => "j0",
            CurveKind::J1728 => "j1728",
        }
    }

    /// Parse a command-line / report tag; `koblitz` is an alias of `j0`.
    pub fn parse(s: &str) -> Option<CurveKind> {
        match s.to_ascii_lowercase().as_str() {
            "generic" => Some(CurveKind::Generic),
            "j0" | "j-0" | "koblitz" => Some(CurveKind::J0),
            "j1728" | "j-1728" => Some(CurveKind::J1728),
            _ => None,
        }
    }
}

/// Classify a curve by its coefficients: `a = 0` is `j = 0`, `b = 0` is
/// `j = 1728`, everything else generic.
pub fn classify(curve: &CurveParams) -> CurveKind {
    if curve.a.is_zero() {
        CurveKind::J0
    } else if curve.b.is_zero() {
        CurveKind::J1728
    } else {
        CurveKind::Generic
    }
}

/// The `j`-invariant `1728 · 4a³ / (4a³ + 27b²) (mod p)`, or `None` when
/// the curve is singular (`4a³ + 27b² ≡ 0`).
pub fn j_invariant(curve: &CurveParams) -> Option<BigUint> {
    let a = curve.a_fe();
    let b = curve.fe(curve.b.clone());
    let a3 = a.mul(&a).mul(&a);
    let four_a3 = curve.fe(BigUint::from(4u32)).mul(&a3);
    let disc = four_a3.add(&curve.fe(BigUint::from(27u32)).mul(&b).mul(&b));
    let inv = disc.inv()?;
    Some(
        curve
            .fe(BigUint::from(1728u32))
            .mul(&four_a3)
            .mul(&inv)
            .value,
    )
}

/// The index-calculus / GLV structure of a curve, computed on its actual
/// parameters.  An optional field is `Some` only when it is defined and
/// checked: a `j = 0` curve whose subgroup order admits no GLV eigenvalue
/// reports `glv_lambda: None`, not a wrong value.
#[derive(Clone, Debug)]
pub struct EndomorphismFacts {
    pub kind: CurveKind,
    /// `j`-invariant, or `None` for a singular curve.
    pub j_invariant: Option<BigUint>,
    /// `|Aut(E)|` acting on the group: 6 for a `j = 0` curve with
    /// `p ≡ 1 (3)`, 4 for `j = 1728` with `p ≡ 1 (4)`, else 2 (negation).
    pub automorphism_order: u32,
    /// `√(automorphism_order)`: the factor by which folding the walk into
    /// automorphism orbits shrinks the rho step count.
    pub rho_speedup: f64,
    /// Primitive cube root of unity `ζ ∈ F_p` (a `j = 0` curve with
    /// `p ≡ 1 (3)`).
    pub cube_root_of_unity: Option<BigUint>,
    /// GLV eigenvalue: `λ` with `ψ(G) = [λ]G`, verified on `G` (`j = 0`).
    pub glv_lambda: Option<BigUint>,
    /// Whether Semaev's `S₃` is `ζ`-equivariant, checked on samples
    /// (`j = 0`).  The identity an orbit factor base rests on.
    pub s3_zeta_equivariant: Option<bool>,
    pub cofactor: u32,
}

/// Compute [`EndomorphismFacts`] for a curve.  Structural only: no
/// discrete log is solved and no point count is attempted.
pub fn endomorphism_facts(curve: &CurveParams) -> EndomorphismFacts {
    let kind = classify(curve);
    let p_mod = |m: u32| (&curve.p % m).to_u32().unwrap_or(0);
    let mut facts = EndomorphismFacts {
        kind,
        j_invariant: j_invariant(curve),
        automorphism_order: 2,
        rho_speedup: 0.0,
        cube_root_of_unity: None,
        glv_lambda: None,
        s3_zeta_equivariant: None,
        cofactor: curve.h,
    };
    match kind {
        CurveKind::J0 if p_mod(3) == 1 => {
            facts.automorphism_order = 6;
            if let Some(z) = cube_root_of_unity(&curve.p) {
                let zfe = curve.fe(z.clone());
                facts.glv_lambda = psi_eigenvalue(curve, &zfe);
                facts.s3_zeta_equivariant = Some(verify_s3_zeta_equivariance(curve, &zfe, 16));
                facts.cube_root_of_unity = Some(z);
            }
        }
        CurveKind::J1728 if p_mod(4) == 1 => facts.automorphism_order = 4,
        _ => {}
    }
    facts.rho_speedup = f64::from(facts.automorphism_order).sqrt();
    facts
}

// ── The reference Semaev solvers on a scaled instance ───────────────────

/// A toy instance in the general representation, with a planted,
/// verified discrete logarithm: `target = [known_log] generator`.
#[derive(Clone, Debug)]
pub struct ScaledInstance {
    pub kind: CurveKind,
    pub curve: CurveParams,
    pub known_log: BigUint,
    pub generator: Point,
    pub target: Point,
}

impl ScaledInstance {
    /// Field size in bits.
    pub fn field_bits(&self) -> u64 {
        self.curve.p.bits()
    }
}

/// Knobs for [`solve_scaled_instance`].  Zero means "size it from the
/// group order".
#[derive(Clone, Copy, Debug)]
pub struct PrimeIcOptions {
    /// Factor-base size (generic) or orbit count (`j = 0`).  0 → auto.
    pub factor_base: usize,
    /// Relations to collect beyond the factor-base size.
    pub extra_relations: usize,
    /// Trial bound per relation.
    pub max_trials_per_relation: usize,
    /// Independent attempts each solver gets before it is reported as
    /// failed.  The index-calculus drivers draw fresh relations on every
    /// attempt; rho is re-randomised by solving for `Q + [s]G`.
    pub attempts: usize,
    /// Rho step bound.  0 → auto from the group order.
    pub rho_max_steps: usize,
    /// On a `j = 0` curve, run the Eisenstein-lattice factor base instead
    /// of the orbit-reduced one.
    pub eisenstein: bool,
    /// Seeds the rho re-randomisation.
    pub seed: u64,
}

impl Default for PrimeIcOptions {
    fn default() -> Self {
        Self {
            factor_base: 0,
            extra_relations: 6,
            max_trials_per_relation: 20_000,
            attempts: 3,
            rho_max_steps: 0,
            eisenstein: false,
            seed: 1,
        }
    }
}

/// One solver's result on the instance.
#[derive(Clone, Debug)]
pub struct SolverRun {
    /// `"semaev-s3"`, `"j0-orbit-reduced"`, `"j0-eisenstein"` or
    /// `"pollard-rho"`.
    pub method: &'static str,
    pub recovered: Option<BigUint>,
    /// `recovered` reproduces the target: `[recovered]G == Q`.
    pub verified: bool,
    /// Attempts used, including the successful one.
    pub attempts: usize,
    /// Wall time over every attempt.
    pub seconds: f64,
}

/// Index calculus versus rho on one scaled instance.
#[derive(Clone, Debug)]
pub struct PrimeIcReport {
    pub kind: CurveKind,
    pub known_log: BigUint,
    pub subgroup_order: BigUint,
    /// Factor-base points (generic) or orbits (`j = 0`) requested.
    pub factor_base: usize,
    pub ic: SolverRun,
    pub rho: SolverRun,
    /// `|Aut(E)|` on the instance.
    pub automorphism_order: u32,
    /// `√(π r / 2)`: expected steps of the plain walk that was run.
    pub rho_expected_steps: f64,
    /// `√(π r / 2) / √|Aut(E)|`: expected steps of a walk folded by the
    /// automorphism group, the stronger opponent.  The measured baseline
    /// does not fold, so a comparison against it is generous to index
    /// calculus.
    pub rho_expected_steps_folded: f64,
}

fn biguint_to_f64(n: &BigUint) -> f64 {
    n.to_f64().unwrap_or(f64::INFINITY)
}

/// Auto factor-base size: `≈ √r` points for a generic curve, and `≈ √r/3`
/// orbits for a `j = 0` curve.
fn auto_factor_base(kind: CurveKind, n: &BigUint) -> usize {
    let root = n.sqrt().to_usize().unwrap_or(usize::MAX);
    match kind {
        CurveKind::J0 => (root / 3).max(10),
        _ => ((root * 9) / 10).max(8),
    }
}

/// Run the reference Semaev solver for the instance's type and the
/// reference rho, verifying every recovered logarithm.
///
/// The solver is Semaev's `S₃` 2-decomposition over a small-abscissa base
/// ([`ec_index_calculus_dlp`]) for a generic curve, and for a `j = 0`
/// curve the `ζ`-orbit base ([`j0_index_calculus_dlp`]) or, with
/// [`PrimeIcOptions::eisenstein`], the Eisenstein-lattice base
/// ([`eisenstein_smooth_ic_dlp`]).  A logarithm counts only once
/// `[d]G == Q` has been checked.
///
/// Those solvers take the whole group as `⟨G⟩`, so the curve must have
/// prime order; a cofactor (every `j = 1728` curve has one) is refused.
pub fn solve_scaled_instance(
    inst: &ScaledInstance,
    opts: &PrimeIcOptions,
) -> Result<PrimeIcReport, String> {
    let curve = &inst.curve;
    if curve.h != 1 {
        return Err(format!(
            "the Semaev reference solvers need a prime-order curve; this one has cofactor {}",
            curve.h
        ));
    }
    let a_fe = curve.a_fe();
    let n = curve.n.clone();
    let fb = if opts.factor_base == 0 {
        auto_factor_base(inst.kind, &n)
    } else {
        opts.factor_base
    };
    let attempts = opts.attempts.max(1);
    let verify = |d: &BigUint| inst.generator.scalar_mul(d, &a_fe) == inst.target;

    let method = match inst.kind {
        CurveKind::J0 if opts.eisenstein => "j0-eisenstein",
        CurveKind::J0 => "j0-orbit-reduced",
        CurveKind::Generic | CurveKind::J1728 => "semaev-s3",
    };
    let start = Instant::now();
    let mut ic = SolverRun {
        method,
        recovered: None,
        verified: false,
        attempts: 0,
        seconds: 0.0,
    };
    for attempt in 1..=attempts {
        ic.attempts = attempt;
        let (g, q, extra, trials) = (
            &inst.generator,
            &inst.target,
            opts.extra_relations,
            opts.max_trials_per_relation,
        );
        let got = match method {
            "j0-eisenstein" => {
                // Norm bound so the lattice yields about `fb` points.
                let norm_bound = ((fb as f64).sqrt().ceil() as u32).max(4);
                eisenstein_smooth_ic_dlp(curve, g, q, norm_bound, extra, trials)
            }
            "j0-orbit-reduced" => j0_index_calculus_dlp(curve, g, q, fb, extra, trials),
            _ => ec_index_calculus_dlp(curve, g, q, fb, extra, trials),
        };
        if let Some(d) = got.filter(|d| verify(d)) {
            ic.recovered = Some(d);
            ic.verified = true;
            break;
        }
    }
    ic.seconds = start.elapsed().as_secs_f64();

    // `pollard_rho_ecdlp` walks from the fixed start G + Q, so each attempt
    // solves for Q' = Q + [s]G with a fresh s and subtracts it again: a
    // failed (degenerate) collision is then not repeated verbatim.
    let automorphism_order = endomorphism_facts(curve).automorphism_order;
    let expected = (std::f64::consts::PI * biguint_to_f64(&n) / 2.0).sqrt();
    let rho_steps = if opts.rho_max_steps == 0 {
        ((expected * 64.0) as usize).max(200_000)
    } else {
        opts.rho_max_steps
    };
    let mut rng = StdRng::seed_from_u64(opts.seed ^ 0x7268_6f5f_7261_6e64);
    let start = Instant::now();
    let mut rho = SolverRun {
        method: "pollard-rho",
        recovered: None,
        verified: false,
        attempts: 0,
        seconds: 0.0,
    };
    for attempt in 1..=attempts {
        rho.attempts = attempt;
        let s = if attempt == 1 {
            BigUint::zero()
        } else {
            BigUint::from(rng.gen_range(1..u64::MAX)) % &n
        };
        let shifted = inst
            .target
            .add(&inst.generator.scalar_mul(&s, &a_fe), &a_fe);
        let got = pollard_rho_ecdlp(curve, &inst.generator, &shifted, rho_steps)
            .map(|d| (&d + &n - &s % &n) % &n);
        if let Some(d) = got.filter(|d| verify(d)) {
            rho.recovered = Some(d);
            rho.verified = true;
            break;
        }
    }
    rho.seconds = start.elapsed().as_secs_f64();

    Ok(PrimeIcReport {
        kind: inst.kind,
        known_log: inst.known_log.clone(),
        subgroup_order: n,
        factor_base: fb,
        ic,
        rho,
        automorphism_order,
        rho_expected_steps: expected,
        rho_expected_steps_folded: expected / f64::from(automorphism_order).sqrt(),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cryptanalysis::ec_index_calculus_j0::psi;
    use crate::cryptanalysis::prime_orbit_index_calculus::{generate_instance, ScaledShape};
    use num_traits::One;

    fn scaled(kind: CurveKind, bits: u32, seed: u64) -> ScaledInstance {
        generate_instance(ScaledShape::of_kind(kind), bits, None, seed)
            .unwrap()
            .scaled()
    }

    #[test]
    fn classify_by_coefficients() {
        assert_eq!(classify(&CurveParams::secp256k1()), CurveKind::J0);
        assert_eq!(classify(&CurveParams::p256()), CurveKind::Generic);
        assert_eq!(classify(&CurveParams::secp192k1()), CurveKind::J0);
        let j1728 = CurveParams {
            name: "t",
            p: BigUint::from(101u32),
            a: BigUint::from(1u32),
            b: BigUint::zero(),
            gx: BigUint::zero(),
            gy: BigUint::zero(),
            n: BigUint::from(101u32),
            h: 1,
        };
        assert_eq!(classify(&j1728), CurveKind::J1728);
        assert_eq!(CurveKind::parse("koblitz"), Some(CurveKind::J0));
    }

    #[test]
    fn j_invariant_of_the_named_families() {
        assert!(j_invariant(&CurveParams::secp256k1()).unwrap().is_zero());
        assert!(j_invariant(&CurveParams::secp224k1()).unwrap().is_zero());
        assert!(!j_invariant(&CurveParams::p256()).unwrap().is_zero());
    }

    #[test]
    fn secp256k1_has_the_order_six_automorphism_and_glv_lambda() {
        let facts = endomorphism_facts(&CurveParams::secp256k1());
        assert_eq!(facts.kind, CurveKind::J0);
        assert_eq!(facts.automorphism_order, 6);
        assert!((facts.rho_speedup - 6f64.sqrt()).abs() < 1e-12);
        let zeta = facts.cube_root_of_unity.expect("p ≡ 1 (3)");
        assert_eq!(
            zeta.modpow(&BigUint::from(3u32), &CurveParams::secp256k1().p),
            BigUint::one()
        );
        // λ² + λ + 1 ≡ 0 (mod n), the GLV relation on secp256k1.
        let lambda = facts.glv_lambda.expect("GLV eigenvalue");
        let n = CurveParams::secp256k1().n;
        assert!(((&lambda * &lambda + &lambda + BigUint::one()) % &n).is_zero());
        assert_eq!(facts.s3_zeta_equivariant, Some(true));
    }

    #[test]
    fn generic_curve_has_only_negation() {
        let facts = endomorphism_facts(&CurveParams::p256());
        assert_eq!(facts.automorphism_order, 2);
        assert!(facts.glv_lambda.is_none());
        assert!(facts.s3_zeta_equivariant.is_none());
    }

    #[test]
    fn scaled_j0_instance_has_the_endomorphism() {
        let inst = scaled(CurveKind::J0, 14, 7);
        let facts = endomorphism_facts(&inst.curve);
        assert_eq!(facts.automorphism_order, 6);
        assert_eq!(facts.s3_zeta_equivariant, Some(true));
        let zeta = inst.curve.fe(facts.cube_root_of_unity.unwrap());
        let psi_g = psi(&inst.generator, &zeta);
        let lambda_g = inst
            .generator
            .scalar_mul(&facts.glv_lambda.unwrap(), &inst.curve.a_fe());
        assert_eq!(psi_g, lambda_g);
    }

    #[test]
    fn semaev_refuses_a_cofactor() {
        let inst = scaled(CurveKind::J1728, 14, 1);
        assert!(inst.curve.h >= 2);
        let err = solve_scaled_instance(&inst, &PrimeIcOptions::default()).unwrap_err();
        assert!(err.contains("cofactor"), "{err}");
    }

    #[test]
    fn generic_semaev_and_rho_agree() {
        let inst = scaled(CurveKind::Generic, 12, 3);
        let report = solve_scaled_instance(&inst, &PrimeIcOptions::default()).unwrap();
        assert!(report.ic.verified, "IC failed: {:?}", report.ic);
        assert!(report.rho.verified, "rho failed: {:?}", report.rho);
        assert_eq!(report.ic.method, "semaev-s3");
        assert_eq!(report.ic.recovered.as_ref(), Some(&inst.known_log));
        assert_eq!(report.rho.recovered.as_ref(), Some(&inst.known_log));
    }

    #[test]
    fn j0_semaev_variants_and_rho_agree() {
        let inst = scaled(CurveKind::J0, 12, 5);
        for eisenstein in [false, true] {
            let opts = PrimeIcOptions {
                eisenstein,
                ..PrimeIcOptions::default()
            };
            let report = solve_scaled_instance(&inst, &opts).unwrap();
            assert!(report.ic.verified, "IC failed: {:?}", report.ic);
            assert!(report.rho.verified, "rho failed: {:?}", report.rho);
            assert_eq!(report.ic.recovered.as_ref(), Some(&inst.known_log));
        }
    }
}
