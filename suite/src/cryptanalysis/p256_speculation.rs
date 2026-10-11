//! Public P-256 speculation map.
//!
//! This module turns the common public concerns about NIST P-256 into
//! explicit, auditable records.  Some concerns have direct probes
//! (ordinary MOV embedding-degree checks, Solinas-prime recognition,
//! simple scalar-output correlation tests).  Others are not publicly
//! testable: an unpublished generalized transfer attack or a future
//! prime-field index-calculus breakthrough cannot be ruled out by a
//! finite Rust test.
//!
//! The goal is not to claim that P-256 is broken.  It is to make the
//! residual concern precise: which parts are measurable today, which
//! parts are only adjacent evidence, and which parts remain conjectural.

use crate::cryptanalysis::p256_structural::{p256_n, p256_p};
use crate::ecc::curve::CurveParams;
use crate::ecc::p256_point::P256ProjectivePoint;
use num_bigint::{BigUint, RandBigInt};
use num_traits::One;
use rand::{rngs::SmallRng, SeedableRng};

/// The four public speculation categories this module tracks.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum SpeculationVector {
    /// MOV/Frey-Ruck-style transfer attacks, plus hypothetical
    /// unpublished generalizations.
    GeneralizedTransfer,
    /// Special structure in the P-256 field prime.
    SolinasPrimeStructure,
    /// Statistical leakage in the map `k -> [k]G`.
    ScalarMultiplicationBias,
    /// Summation-polynomial / index-calculus approaches to ECDLP.
    EllipticIndexCalculus,
}

/// How much public research or evidence exists for a speculation vector.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum PublicResearchStatus {
    /// A concrete public literature exists and is still being extended.
    Active,
    /// Adjacent attacks exist, but not against prime-field P-256 ECDLP.
    AdjacentOnly,
    /// No meaningful public research program appears to exist.
    NotPubliclyGrounded,
    /// The concern is inherently about unknown unpublished work.
    Conjectural,
}

/// What this codebase can say about P-256 for one vector.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ProbeVerdict {
    /// The public, finite check found no anomaly.
    NoPublicAnomaly,
    /// A structural property exists, but no public EC attack follows.
    StructurePresentNoKnownAttack,
    /// This is not meaningfully falsifiable by a public finite check.
    NotPubliclyTestable,
}

/// One row in the public speculation map.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SpeculationFinding {
    pub vector: SpeculationVector,
    pub public_status: PublicResearchStatus,
    pub p256_verdict: ProbeVerdict,
    pub summary: &'static str,
    pub implemented_probe: &'static str,
}

/// Return the four-row public speculation map for P-256.
pub fn p256_public_speculation_findings() -> Vec<SpeculationFinding> {
    vec![
        SpeculationFinding {
            vector: SpeculationVector::GeneralizedTransfer,
            public_status: PublicResearchStatus::Conjectural,
            p256_verdict: ProbeVerdict::NotPubliclyTestable,
            summary: "standard MOV/Frey-Ruck checks are public and pass; an unpublished transfer family is not falsifiable here",
            implemented_probe: "p256_embedding_degree_probe(max_k)",
        },
        SpeculationFinding {
            vector: SpeculationVector::SolinasPrimeStructure,
            public_status: PublicResearchStatus::AdjacentOnly,
            p256_verdict: ProbeVerdict::StructurePresentNoKnownAttack,
            summary: "P-256 uses a 5-term Solinas prime; hidden-SNFS trapdoors are known for finite-field DLP primes, not for P-256 ECDLP",
            implemented_probe: "p256_solinas_prime_profile() and solinas_correlations::run_correlation_experiment",
        },
        SpeculationFinding {
            vector: SpeculationVector::ScalarMultiplicationBias,
            public_status: PublicResearchStatus::NotPubliclyGrounded,
            p256_verdict: ProbeVerdict::NoPublicAnomaly,
            summary: "nonce-bias attacks on ECDSA are real, but no public attack exploits statistical bias in uniformly sampled kG outputs",
            implemented_probe: "p256_scalar_bit_correlation_report(options)",
        },
        SpeculationFinding {
            vector: SpeculationVector::EllipticIndexCalculus,
            public_status: PublicResearchStatus::Active,
            p256_verdict: ProbeVerdict::NoPublicAnomaly,
            summary: "summation-polynomial and index-calculus research is active, but published prime-field methods remain above generic rho for P-256 sizes",
            implemented_probe: "status record; prime-field P-256 has no known practical index-calculus probe",
        },
    ]
}

/// Result of the public embedding-degree check for MOV/Frey-Ruck style
/// transfers.  If `first_k` is `None`, no `k <= max_k` satisfied
/// `p^k == 1 mod n`.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct EmbeddingDegreeProbe {
    pub max_k: u32,
    pub first_k: Option<u32>,
}

impl EmbeddingDegreeProbe {
    /// True if the public MOV-style check found no embedding degree at
    /// or below the unsafe cutoff.
    pub fn passes_public_mov_cutoff(&self, max_unsafe_k: u32) -> bool {
        self.first_k.map_or(true, |k| k > max_unsafe_k)
    }
}

/// Search for the smallest `k <= max_k` such that `p^k == 1 mod n`
/// for the P-256 subgroup order `n`.
pub fn p256_embedding_degree_probe(max_k: u32) -> EmbeddingDegreeProbe {
    let p = p256_p();
    let n = p256_n();
    let one = BigUint::one();
    let mut pk = BigUint::one();

    for k in 1..=max_k {
        pk = (&pk * &p) % &n;
        if pk == one {
            return EmbeddingDegreeProbe {
                max_k,
                first_k: Some(k),
            };
        }
    }

    EmbeddingDegreeProbe {
        max_k,
        first_k: None,
    }
}

/// A signed power-of-two term in a low-weight prime representation.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SignedPowerTerm {
    pub sign: i8,
    pub exponent: u16,
}

/// P-256's Solinas-prime profile.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SolinasPrimeProfile {
    pub terms: Vec<SignedPowerTerm>,
    pub signed_weight: usize,
    pub equals_p256_prime: bool,
}

/// Verify the public Solinas representation
/// `p = 2^256 - 2^224 + 2^192 + 2^96 - 1`.
pub fn p256_solinas_prime_profile() -> SolinasPrimeProfile {
    let terms = vec![
        SignedPowerTerm {
            sign: 1,
            exponent: 256,
        },
        SignedPowerTerm {
            sign: -1,
            exponent: 224,
        },
        SignedPowerTerm {
            sign: 1,
            exponent: 192,
        },
        SignedPowerTerm {
            sign: 1,
            exponent: 96,
        },
        SignedPowerTerm {
            sign: -1,
            exponent: 0,
        },
    ];

    let one = BigUint::one();
    let candidate =
        ((&one << 256usize) + (&one << 192usize) + (&one << 96usize)) - (&one << 224usize) - &one;

    SolinasPrimeProfile {
        signed_weight: terms.len(),
        terms,
        equals_p256_prime: candidate == p256_p(),
    }
}

/// Options for a lightweight scalar-output correlation probe.
#[derive(Clone, Debug)]
pub struct ScalarBiasOptions {
    /// Number of random non-zero scalars to sample.
    pub samples: u64,
    /// Deterministic seed for reproducible research runs.
    pub seed: u64,
    /// Number of low scalar bits to compare.
    pub scalar_bits: usize,
    /// Number of low x-coordinate bits to compare.
    pub x_bits: usize,
}

impl Default for ScalarBiasOptions {
    fn default() -> Self {
        Self {
            samples: 128,
            seed: 0x5032_3536,
            scalar_bits: 64,
            x_bits: 64,
        }
    }
}

/// One high-correlation bit pair from the scalar-output probe.
#[derive(Clone, Debug, PartialEq)]
pub struct ScalarBitCorrelation {
    pub z_score: f64,
    pub x_bit: usize,
    pub scalar_bit: usize,
}

/// Summary of the scalar-output correlation probe.
#[derive(Clone, Debug, PartialEq)]
pub struct ScalarBitCorrelationReport {
    pub samples: u64,
    pub scalar_bits: usize,
    pub x_bits: usize,
    pub max_abs_z: f64,
    pub strongest_pair: Option<ScalarBitCorrelation>,
}

/// Sample random non-zero P-256 scalars, compute `[k]G`, and test for
/// simple bit-pair correlations between low scalar bits and low
/// x-coordinate bits.
///
/// This is deliberately modest: it is a sanity probe for the speculative
/// "statistical bias in kG outputs" concern, not a proof of uniformity.
/// A serious run should raise `samples` substantially and treat any
/// candidate outlier with multiple-comparison correction.
pub fn p256_scalar_bit_correlation_report(
    opts: &ScalarBiasOptions,
) -> Result<ScalarBitCorrelationReport, &'static str> {
    if opts.samples == 0 {
        return Err("samples must be non-zero");
    }
    if opts.scalar_bits == 0 || opts.scalar_bits > 256 {
        return Err("scalar_bits must be in 1..=256");
    }
    if opts.x_bits == 0 || opts.x_bits > 256 {
        return Err("x_bits must be in 1..=256");
    }

    let curve = CurveParams::p256();
    let generator = P256ProjectivePoint::from_textbook(&curve.generator());
    let mut rng = SmallRng::seed_from_u64(opts.seed);
    let mut scalar_marginal = vec![0u64; opts.scalar_bits];
    let mut x_marginal = vec![0u64; opts.x_bits];
    let mut joint = vec![0u64; opts.scalar_bits * opts.x_bits];

    for _ in 0..opts.samples {
        let mut k = rng.gen_biguint_below(&curve.n);
        if k == BigUint::from(0u8) {
            k = BigUint::one();
        }

        let point = generator.scalar_mul_ct(&k, curve.order_bits());
        let (x, _) = point
            .to_affine()
            .ok_or("non-zero scalar produced identity")?;
        let x = x.to_biguint();

        let mut scalar_bits_set = vec![false; opts.scalar_bits];
        for (bit, slot) in scalar_bits_set.iter_mut().enumerate() {
            if k.bit(bit as u64) {
                *slot = true;
                scalar_marginal[bit] += 1;
            }
        }

        for x_bit in 0..opts.x_bits {
            if x.bit(x_bit as u64) {
                x_marginal[x_bit] += 1;
                for scalar_bit in 0..opts.scalar_bits {
                    if scalar_bits_set[scalar_bit] {
                        joint[x_bit * opts.scalar_bits + scalar_bit] += 1;
                    }
                }
            }
        }
    }

    let n = opts.samples as f64;
    let mut strongest_pair = None;
    let mut max_abs_z = 0.0f64;

    for x_bit in 0..opts.x_bits {
        let p_x = x_marginal[x_bit] as f64 / n;
        for scalar_bit in 0..opts.scalar_bits {
            let p_s = scalar_marginal[scalar_bit] as f64 / n;
            let expected = p_x * p_s;
            let variance = expected * (1.0 - expected) / n;
            if variance == 0.0 {
                continue;
            }
            let observed = joint[x_bit * opts.scalar_bits + scalar_bit] as f64 / n;
            let z = (observed - expected) / variance.sqrt();
            if z.abs() > max_abs_z {
                max_abs_z = z.abs();
                strongest_pair = Some(ScalarBitCorrelation {
                    z_score: z,
                    x_bit,
                    scalar_bit,
                });
            }
        }
    }

    Ok(ScalarBitCorrelationReport {
        samples: opts.samples,
        scalar_bits: opts.scalar_bits,
        x_bits: opts.x_bits,
        max_abs_z,
        strongest_pair,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn speculation_map_has_the_four_public_vectors() {
        let rows = p256_public_speculation_findings();
        assert_eq!(rows.len(), 4);
        assert!(rows
            .iter()
            .any(|r| r.vector == SpeculationVector::GeneralizedTransfer));
        assert!(rows
            .iter()
            .any(|r| r.vector == SpeculationVector::SolinasPrimeStructure));
        assert!(rows
            .iter()
            .any(|r| r.vector == SpeculationVector::ScalarMultiplicationBias));
        assert!(rows
            .iter()
            .any(|r| r.vector == SpeculationVector::EllipticIndexCalculus));
    }

    #[test]
    fn p256_has_no_small_public_embedding_degree() {
        let probe = p256_embedding_degree_probe(100);
        assert_eq!(probe.first_k, None);
        assert!(probe.passes_public_mov_cutoff(6));
    }

    #[test]
    fn p256_solinas_profile_matches_the_field_prime() {
        let profile = p256_solinas_prime_profile();
        assert!(profile.equals_p256_prime);
        assert_eq!(profile.signed_weight, 5);
        assert_eq!(
            profile.terms[0],
            SignedPowerTerm {
                sign: 1,
                exponent: 256
            }
        );
        assert_eq!(
            profile.terms[4],
            SignedPowerTerm {
                sign: -1,
                exponent: 0
            }
        );
    }

    #[test]
    fn scalar_bit_correlation_probe_smoke_test() {
        let opts = ScalarBiasOptions {
            samples: 4,
            seed: 7,
            scalar_bits: 4,
            x_bits: 4,
        };
        let report = p256_scalar_bit_correlation_report(&opts).unwrap();
        assert_eq!(report.samples, 4);
        assert_eq!(report.scalar_bits, 4);
        assert_eq!(report.x_bits, 4);
        assert!(report.max_abs_z.is_finite());
    }

    #[test]
    fn scalar_bit_correlation_rejects_empty_sample() {
        let opts = ScalarBiasOptions {
            samples: 0,
            ..ScalarBiasOptions::default()
        };
        assert!(p256_scalar_bit_correlation_report(&opts).is_err());
    }
}
