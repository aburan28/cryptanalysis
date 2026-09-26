//! # The `icx` engine: run-regime classification and honest cost estimates.
//!
//! This module decides, for a catalog curve, *what kind of index-calculus run
//! is meaningful* and *what it should be expected to cost*, without ever
//! overclaiming.  It is the piece that keeps "run `icx` against every curve"
//! honest: for each curve it produces exactly one of three outcomes, per
//! `docs/ic/ENGINE_AUDIT_AND_DESIGN.md` §1.
//!
//! - [`Regime::Attack`] — index calculus is the relevant sub-exponential
//!   attack on this family, and the instance is inside the size envelope this
//!   repository has actually solved end to end.  A run recovers a verified
//!   logarithm and prices it against Pollard rho.
//! - [`Regime::Scaled`] — the named curve is out of that envelope (or is a
//!   prime-field curve, where no sub-exponential IC is known).  A run executes
//!   the same pipeline on a same-family analogue at a feasible size and labels
//!   any statement about the named curve as an extrapolation.
//! - [`Regime::EstimateOnly`] — no run is attempted; the report carries the
//!   generic-attack cost and the family's asymptotic IC form, with heuristics
//!   named.
//!
//! Nothing here claims to break a curve, and the prime-field note is explicit:
//! index calculus is **not** a threat to prime-field ECDLP, and the CLI says
//! so per curve.

use crate::cryptanalysis::curve_catalog::{CatalogCurve, Family};

/// Largest subgroup-order bit length this repository has solved end to end
/// with the framework (a 48-bit subgroup of `K_0/F_{2^61}`; see
/// `docs/ic/runs/`).  Above this, a real curve is run as a scaled analogue.
pub const ATTACK_ENVELOPE_BITS: u64 = 48;

/// What sort of run is meaningful for a curve.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Regime {
    /// IC is relevant and the instance is in-envelope: solve and price it.
    Attack,
    /// Run a same-family analogue at feasible size; extrapolate, labelled.
    Scaled,
    /// Estimate only; no solve attempted.
    EstimateOnly,
}

impl Regime {
    pub fn tag(self) -> &'static str {
        match self {
            Regime::Attack => "attack",
            Regime::Scaled => "scaled",
            Regime::EstimateOnly => "estimate",
        }
    }
}

/// True when Weil-descent / summation-polynomial index calculus is the
/// relevant sub-exponential attack on this family.  Prime-field curves are
/// excluded: no sub-exponential IC is known for prime-field ECDLP.
pub fn ic_relevant(family: Family) -> bool {
    matches!(
        family,
        Family::BinaryRandom | Family::Koblitz | Family::Extension | Family::Char3
    )
}

/// The regime classification plus a human-readable rationale.
#[derive(Clone, Debug)]
pub struct RegimeReport {
    pub regime: Regime,
    pub ic_relevant: bool,
    pub rationale: String,
}

/// Classify a curve for a `run`.  `envelope_bits` defaults to
/// [`ATTACK_ENVELOPE_BITS`]; callers may lower it (e.g. for a quick CI run).
pub fn classify(curve: &CatalogCurve, envelope_bits: u64) -> RegimeReport {
    let relevant = ic_relevant(curve.family);
    let order_bits = curve.order_bits();
    if relevant && order_bits <= envelope_bits {
        RegimeReport {
            regime: Regime::Attack,
            ic_relevant: true,
            rationale: format!(
                "index calculus is the relevant sub-exponential attack on the \
                 {} family, and the {}-bit subgroup is within the end-to-end \
                 envelope ({} bits) demonstrated in this repository",
                curve.family.tag(),
                order_bits,
                envelope_bits
            ),
        }
    } else if relevant {
        RegimeReport {
            regime: Regime::Scaled,
            ic_relevant: true,
            rationale: format!(
                "index calculus applies to the {} family, but the {}-bit \
                 subgroup exceeds the {}-bit end-to-end envelope; a run uses a \
                 same-family analogue and any statement about {} is an \
                 extrapolation",
                curve.family.tag(),
                order_bits,
                envelope_bits,
                curve.name
            ),
        }
    } else {
        // Prime field: IC is not a threat.  A run is still possible on a small
        // prime analogue for study, so this is Scaled, not EstimateOnly, but
        // the rationale is explicit that IC does not beat rho here.
        RegimeReport {
            regime: Regime::Scaled,
            ic_relevant: false,
            rationale: format!(
                "no sub-exponential index calculus is known for prime-field \
                 ECDLP; Pollard rho is the best attack on {}. A run executes a \
                 small prime-field IC study instance and does not threaten the \
                 named curve",
                curve.name
            ),
        }
    }
}

/// A cost estimate for a curve, in the repository's honest terms.
#[derive(Clone, Debug)]
pub struct CostEstimate {
    pub curve: String,
    pub family: &'static str,
    pub field_label: String,
    pub field_bits: u64,
    pub order_bits: u64,
    /// `log2` of the expected Pollard-rho operation count (the generic floor).
    pub rho_log2_ops: f64,
    /// Generic-attack security level in bits (`½ log2 n`, with family speedups
    /// noted separately in `notes`).
    pub rho_security_bits: f64,
    pub ic_relevant: bool,
    pub regime: Regime,
    /// Plain-language notes: applicability, family speedups, heuristics.
    pub notes: Vec<String>,
}

/// Produce a cost estimate.  This is deliberately conservative: it reports the
/// generic-attack floor exactly and describes the IC picture qualitatively
/// with its heuristics named, rather than fabricating an IC operation count
/// for a size no one has run.
pub fn estimate(curve: &CatalogCurve, envelope_bits: u64) -> CostEstimate {
    let field = curve.field();
    let order_bits = curve.order_bits();
    // log2 n from the security estimate (which is ½ log2 n).
    let log2_n = curve.rho_security_bits() * 2.0;
    // Generic rho: ~sqrt(pi/4 * n) = 0.886 * sqrt(n) group operations.
    let rho_log2_ops = 0.5 * log2_n + (std::f64::consts::PI / 4.0).sqrt().log2();
    let cls = classify(curve, envelope_bits);

    let mut notes = Vec::new();
    match curve.family {
        Family::Prime => {
            notes.push(
                "Prime-field ECDLP has no known sub-exponential index calculus; \
                 rho is the best attack. IC is included here only as a scaled \
                 study instance."
                    .to_string(),
            );
        }
        Family::Koblitz => {
            notes.push(
                "Koblitz curves admit both a rho speedup (negation + Frobenius, \
                 ~1/sqrt(2n)) and Weil-descent index calculus (Gaudry, \
                 Semaev, GGMP). In this repository IC's whole-pipeline S has \
                 not dropped below rho at any measured size; see the scoreboard."
                    .to_string(),
            );
        }
        Family::BinaryRandom => {
            notes.push(
                "Binary curves admit Weil-descent / summation-polynomial index \
                 calculus (Diem, FGHR). Sub-exponential in theory; not below \
                 rho end-to-end at the sizes measured here."
                    .to_string(),
            );
        }
        Family::Extension => {
            notes.push(
                "Extension-field curves F_{p^k}, k>=3, are the Gaudry/Diem \
                 index-calculus regime; the crossover with rho depends on k and \
                 field size."
                    .to_string(),
            );
        }
        Family::Char3 => {
            notes.push(
                "Characteristic-three curves are covered for parameter \
                 completeness; descent-based IC applies at descent-feasible \
                 sizes only."
                    .to_string(),
            );
        }
    }
    notes.push(format!(
        "Run regime for this size: {} — {}",
        cls.regime.tag(),
        cls.rationale
    ));

    CostEstimate {
        curve: curve.name.to_string(),
        family: curve.family.tag(),
        field_label: field.label,
        field_bits: field.bits,
        order_bits,
        rho_log2_ops,
        rho_security_bits: curve.rho_security_bits(),
        ic_relevant: cls.ic_relevant,
        regime: cls.regime,
        notes,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cryptanalysis::curve_catalog::by_name;

    #[test]
    fn prime_curves_are_not_ic_relevant() {
        let p256 = by_name("p256").unwrap();
        let r = classify(&p256, ATTACK_ENVELOPE_BITS);
        assert!(!r.ic_relevant);
        assert_eq!(r.regime, Regime::Scaled);
        let est = estimate(&p256, ATTACK_ENVELOPE_BITS);
        assert!(!est.ic_relevant);
        // ~128-bit rho security for P-256.
        assert!((120.0..132.0).contains(&est.rho_security_bits));
        // rho op count ~2^127.8.
        assert!((120.0..132.0).contains(&est.rho_log2_ops));
    }

    #[test]
    fn koblitz_is_ic_relevant_and_out_of_envelope_when_large() {
        let k163 = by_name("sect163k1").unwrap();
        let r = classify(&k163, ATTACK_ENVELOPE_BITS);
        assert!(r.ic_relevant);
        // 163-bit curve is far above the 48-bit envelope.
        assert_eq!(r.regime, Regime::Scaled);
    }

    #[test]
    fn small_koblitz_analogue_is_attack_regime() {
        // Use a tiny synthetic envelope to exercise the Attack branch on a
        // real catalog curve: pretend the envelope is 200 bits.
        let k163 = by_name("sect163k1").unwrap();
        let r = classify(&k163, 200);
        assert_eq!(r.regime, Regime::Attack);
    }
}
