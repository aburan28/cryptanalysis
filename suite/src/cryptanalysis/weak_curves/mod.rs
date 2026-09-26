//! **Weak-curve ECDLP attacks** over prime fields `F_p`, with an
//! auto-dispatcher that explains which weakness applies and runs the
//! cheapest attack that does.
//!
//! | weakness | test | attack | cost |
//! |---|---|---|---|
//! | singular cubic | `4a³ + 27b² ≡ 0` | map to `(F_p,+)`, `F_p*` or `F_{p²}*` ([`singular`]) | division / Pohlig–Hellman on `p ∓ 1` |
//! | anomalous | `ord(G) = p` | Smart's `p`-adic lift ([`smart`]) | `O(log p)` operations mod `p²` |
//! | smooth order | largest prime `ℓ \| ord(G)` small | Pohlig–Hellman + BSGS / Pollard rho ([`smooth_order`]) | `Σ eᵢ√qᵢ` |
//! | small embedding degree | `ℓ \| p^k − 1`, `k ≤ 12` | MOV/Frey–Rück with the reduced Tate pairing ([`mov`]) | pairing + DLP in `F_{p^k}*` |
//!
//! Supporting pieces are public: number theory and fast affine curve
//! arithmetic ([`arith`], including [`factor_order`]), generic DLP
//! solvers over any [`dlp::DlpGroup`] ([`dlp`]), and `F_{p^k}`
//! arithmetic ([`fpk`]).
//!
//! # Dispatcher
//!
//! [`analyze`] runs every check and returns a [`WeakCurveReport`] that
//! says, for each method, whether it applies, why, and an estimated
//! cost in group operations (log₂).  [`attack`] then runs the
//! recommended method (or the one forced in [`AttackOptions`]) and
//! returns an [`AttackOutcome`] whose scalar has been verified by scalar
//! multiplication with the crate's [`Point::scalar_mul`].  Nothing in
//! this module prints.
//!
//! The recommendation order is singular → anomalous → Pohlig–Hellman
//! (when its estimated cost is within [`AttackOptions::max_log2_ops`]).
//! MOV is *reported* whenever the embedding degree is small — it moves
//! the DLP into a finite field where index calculus/NFS would be
//! subexponential — but the finite-field solver here is generic
//! (Pohlig–Hellman + BSGS/rho; index calculus in `F_{p^k}` is out of
//! scope), so the transferred DLP costs the same `√ℓ` as rho on the
//! curve and MOV is only run when forced.
//!
//! # Scope
//!
//! Prime fields only (anomalous binary curves, Weil descent/GHS and
//! other characteristic-2 attacks are out of scope).  Scalars are
//! recovered modulo the exact order of `G`.
//!
//! # References
//!
//! - S. Pohlig, M. Hellman, *An improved algorithm for computing
//!   logarithms over GF(p)*, IEEE Trans. IT 24 (1978).
//! - J. M. Pollard, *Monte Carlo methods for index computation (mod p)*,
//!   Math. Comp. 32 (1978); E. Teske, Math. Comp. 70 (2001).
//! - N. P. Smart, *The discrete logarithm problem on elliptic curves of
//!   trace one*, J. Cryptology 12 (1999).
//! - A. Menezes, T. Okamoto, S. Vanstone, IEEE Trans. IT 39 (1993);
//!   G. Frey, H.-G. Rück, Math. Comp. 62 (1994); V. S. Miller,
//!   J. Cryptology 17 (2004).
//! - L. C. Washington, *Elliptic Curves: Number Theory and
//!   Cryptography*, 2nd ed., §2.9 (singular cubics).

pub mod arith;
pub mod dlp;
pub mod fpk;
pub mod mov;
pub mod singular;
pub mod smart;
pub mod smooth_order;

pub use arith::{factor, factor_order, is_probable_prime, FactorOptions, Factorization};
pub use dlp::{DlpGroup, PrimeSolver, SolverOptions};
pub use mov::{embedding_degree, mov_attack, MovOptions, MovOutcome};
pub use singular::{classify_singular, singular_attack, SingularKind, SingularOutcome};
pub use smart::{anomalous_curve_cm, smart_attack, AnomalousCurve, SmartOptions, SmartOutcome};
pub use smooth_order::{pohlig_hellman_attack, PohligHellmanOptions, PohligHellmanOutcome};

use crate::ecc::curve::CurveParams;
use crate::ecc::point::Point;
use arith::{AffinePoint, Ec};
use num_bigint::BigUint;
use num_traits::{ToPrimitive, Zero};
use serde::Serialize;
use std::fmt;
use std::time::Instant;

/// Serde helpers: big integers serialise as decimal strings.
pub(crate) mod ser {
    use num_bigint::BigUint;
    use serde::ser::SerializeSeq;
    use serde::Serializer;

    pub fn big<S: Serializer>(v: &BigUint, s: S) -> Result<S::Ok, S::Error> {
        s.serialize_str(&v.to_str_radix(10))
    }

    pub fn opt_big<S: Serializer>(v: &Option<BigUint>, s: S) -> Result<S::Ok, S::Error> {
        match v {
            Some(v) => s.serialize_some(&v.to_str_radix(10)),
            None => s.serialize_none(),
        }
    }

    pub fn big_vec<S: Serializer>(v: &[BigUint], s: S) -> Result<S::Ok, S::Error> {
        let mut seq = s.serialize_seq(Some(v.len()))?;
        for x in v {
            seq.serialize_element(&x.to_str_radix(10))?;
        }
        seq.end()
    }

    pub fn big_pairs<S: Serializer>(v: &[(BigUint, u32)], s: S) -> Result<S::Ok, S::Error> {
        let mut seq = s.serialize_seq(Some(v.len()))?;
        for (q, e) in v {
            seq.serialize_element(&(q.to_str_radix(10), *e))?;
        }
        seq.end()
    }
}

/// Errors from the weak-curve attacks.
#[derive(Clone, Debug, PartialEq, Serialize)]
pub enum WeakCurveError {
    /// The inputs are inconsistent (point off the curve, wrong order…).
    InvalidInput(String),
    /// The attack does not apply to this curve.
    NotApplicable(String),
    /// `Q` is not in the subgroup generated by `G`.
    NotInSubgroup,
    /// A solver or search ran out of budget.
    SolverFailed(String),
    /// A candidate scalar failed the final scalar-multiplication check.
    VerificationFailed,
    /// [`attack`] found no applicable, affordable method.
    NoApplicableAttack(String),
}

impl fmt::Display for WeakCurveError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            WeakCurveError::InvalidInput(s) => write!(f, "invalid input: {s}"),
            WeakCurveError::NotApplicable(s) => write!(f, "attack not applicable: {s}"),
            WeakCurveError::NotInSubgroup => write!(f, "Q is not in the subgroup generated by G"),
            WeakCurveError::SolverFailed(s) => write!(f, "solver failed: {s}"),
            WeakCurveError::VerificationFailed => {
                write!(f, "recovered scalar failed verification")
            }
            WeakCurveError::NoApplicableAttack(s) => write!(f, "no applicable attack: {s}"),
        }
    }
}

impl std::error::Error for WeakCurveError {}

/// An attack method.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
pub enum Method {
    /// Singular cubic: map to `(F_p,+)`, `F_p*` or the torus in `F_{p²}*`.
    Singular,
    /// Smart's attack on anomalous curves.
    Smart,
    /// Pohlig–Hellman with BSGS / Pollard rho.
    PohligHellman,
    /// MOV / Frey–Rück pairing transfer to `F_{p^k}*`.
    Mov,
}

/// One check of [`analyze`].
#[derive(Clone, Debug, Serialize)]
pub struct WeakCheck {
    /// The method this check gates.
    pub method: Method,
    /// Whether the weakness is present (the attack applies).
    pub applicable: bool,
    /// Why the check passed or failed.
    pub explanation: String,
    /// Estimated cost, log₂ of group operations, when meaningful.
    pub estimated_log2_ops: Option<f64>,
}

/// Output of [`analyze`].
#[derive(Clone, Debug, Serialize)]
pub struct WeakCurveReport {
    /// Curve name.
    pub curve_name: String,
    /// Bits of `p`.
    pub p_bits: u64,
    /// The order supplied for `G`.
    #[serde(serialize_with = "ser::big")]
    pub claimed_order: BigUint,
    /// Problems with the input (empty when consistent).
    pub input_problems: Vec<String>,
    /// Singular-cubic classification, if singular.
    pub singular: Option<singular::SingularInfo>,
    /// Factorisation of the claimed order (non-singular curves).
    pub order_factorization: Option<Factorization>,
    /// `#E(F_p)` used for the MOV check, if known and consistent.
    #[serde(serialize_with = "ser::opt_big")]
    pub curve_order: Option<BigUint>,
    /// Embedding degree of the largest prime factor of the order.
    pub embedding_degree: Option<u32>,
    /// Every check, in dispatch order.
    pub checks: Vec<WeakCheck>,
    /// The method [`attack`] would run.
    pub recommended: Option<Method>,
    /// Milliseconds spent analysing.
    pub analysis_ms: f64,
}

/// Options for [`analyze_with`] / [`attack_with`].
#[derive(Clone, Debug, Serialize)]
pub struct AttackOptions {
    /// Run this method instead of the recommendation.
    pub force: Option<Method>,
    /// `#E(F_p)` for the MOV check; defaults to `curve.n · curve.h` when
    /// that is consistent (Hasse bound, annihilates random points).
    #[serde(serialize_with = "ser::opt_big")]
    pub curve_order: Option<BigUint>,
    /// Complete factorisation of the claimed order, if known.
    #[serde(serialize_with = "ser::big_pairs")]
    pub order_factorization: Vec<(BigUint, u32)>,
    /// Pohlig–Hellman is recommended only when its estimated cost is at
    /// most `2^max_log2_ops` group operations.
    pub max_log2_ops: f64,
    /// Largest embedding degree examined.
    pub max_embedding_degree: u32,
    /// Factoring budget.
    pub factor: FactorOptions,
    /// DLP solver tuning (seed, BSGS/rho thresholds).
    pub solver: SolverOptions,
    /// Random lifts for Smart's attack.
    pub smart_max_lifts: usize,
}

impl Default for AttackOptions {
    fn default() -> Self {
        AttackOptions {
            force: None,
            curve_order: None,
            order_factorization: Vec::new(),
            max_log2_ops: 34.0,
            max_embedding_degree: 12,
            factor: FactorOptions::default(),
            solver: SolverOptions::default(),
            smart_max_lifts: 16,
        }
    }
}

/// Per-method result carried by [`AttackOutcome`].
#[derive(Clone, Debug, Serialize)]
pub enum AttackDetails {
    /// Singular-cubic attack.
    Singular(SingularOutcome),
    /// Smart's attack.
    Smart(SmartOutcome),
    /// Pohlig–Hellman.
    PohligHellman(PohligHellmanOutcome),
    /// MOV / Frey–Rück.
    Mov(MovOutcome),
}

/// Output of [`attack`].
#[derive(Clone, Debug, Serialize)]
pub struct AttackOutcome {
    /// The method that ran.
    pub method: Method,
    /// Recovered `d` with `Q = d·G` (modulo the order of `G`).
    #[serde(serialize_with = "ser::big")]
    pub scalar: BigUint,
    /// `true`: `d·G = Q` was checked with the crate's scalar
    /// multiplication.  (An unverified scalar is never returned.)
    pub verified: bool,
    /// The analysis that chose the method.
    pub report: WeakCurveReport,
    /// Method-specific details and timings.
    pub details: AttackDetails,
    /// Milliseconds in the attack itself.
    pub attack_ms: f64,
    /// Milliseconds including the analysis.
    pub total_ms: f64,
}

fn log2_f(n: &BigUint) -> f64 {
    let bits = n.bits();
    if bits <= 52 {
        return n.to_f64().unwrap_or(1.0).max(1.0).log2();
    }
    let shift = bits - 52;
    (n >> shift).to_f64().unwrap_or(1.0).log2() + shift as f64
}

/// `log₂ Σ eᵢ·√(π qᵢ / 2)` — expected Pohlig–Hellman work.
fn ph_log2_cost(factors: &[(BigUint, u32)]) -> f64 {
    let mut total = 0f64;
    for (q, e) in factors {
        let l = 0.5 * (log2_f(q) + (std::f64::consts::PI / 2.0).log2());
        total += f64::from(*e) * l.exp2();
    }
    total.max(1.0).log2()
}

/// Run every weak-curve check with default options.  See
/// [`analyze_with`].
pub fn analyze(curve: &CurveParams, g: &Point, q: &Point, order: &BigUint) -> WeakCurveReport {
    analyze_with(curve, g, q, order, &AttackOptions::default())
}

/// Run every weak-curve check: singular? anomalous? smooth order?
/// small embedding degree?  Explains each outcome and picks the
/// cheapest applicable attack.  `order` is the claimed order of `G`
/// (ignored for singular cubics, whose group order is derived).
pub fn analyze_with(
    curve: &CurveParams,
    g: &Point,
    q: &Point,
    order: &BigUint,
    opts: &AttackOptions,
) -> WeakCurveReport {
    let t0 = Instant::now();
    let ec = Ec::from_params(curve);
    let p = &ec.p;
    let mut report = WeakCurveReport {
        curve_name: curve.name.to_string(),
        p_bits: p.bits(),
        claimed_order: order.clone(),
        input_problems: Vec::new(),
        singular: None,
        order_factorization: None,
        curve_order: None,
        embedding_degree: None,
        checks: Vec::new(),
        recommended: None,
        analysis_ms: 0.0,
    };
    let finish = |mut r: WeakCurveReport| {
        r.analysis_ms = t0.elapsed().as_secs_f64() * 1e3;
        r
    };
    if p <= &BigUint::from(3u32) || !is_probable_prime(p) {
        report
            .input_problems
            .push("p is not a prime greater than 3".into());
        return finish(report);
    }
    let gl = ec.import(g);
    let ql = ec.import(q);
    if gl == AffinePoint::Infinity {
        report.input_problems.push("G is the identity".into());
    }
    if !ec.is_on_curve(&gl) {
        report.input_problems.push("G is not on the curve".into());
    }
    if !ec.is_on_curve(&ql) {
        report.input_problems.push("Q is not on the curve".into());
    }
    if !report.input_problems.is_empty() {
        return finish(report);
    }

    // 1. Singular cubic.
    if let Some(info) = classify_singular(p, &ec.a, &ec.b) {
        let (expl, cost) = match info.kind {
            SingularKind::Cusp => (
                "4a³ + 27b² ≡ 0 and a ≡ b ≡ 0: cusp y² = x³; (x, y) ↦ x/y is an \
                 isomorphism onto (F_p, +), so the DLP is one division"
                    .to_string(),
                Some(1.0),
            ),
            kind => {
                let target = if kind == SingularKind::SplitNode {
                    "F_p* (order p − 1)"
                } else {
                    "the norm-one subgroup of F_{p²}* (order p + 1)"
                };
                let f = factor(&info.group_order, &opts.factor);
                let cost = f.is_complete().then(|| ph_log2_cost(&f.factors));
                (
                    format!(
                        "4a³ + 27b² ≡ 0: node at x₀ = {}; tangent slopes ±√{} {} F_p, so \
                         the non-singular points map isomorphically onto {target}; \
                         Pohlig–Hellman there (largest prime factor {} bits{})",
                        info.singular_x,
                        info.beta,
                        if kind == SingularKind::SplitNode {
                            "lie in"
                        } else {
                            "are not in"
                        },
                        f.largest_prime().map(|q| q.bits()).unwrap_or(0),
                        if f.is_complete() {
                            ""
                        } else {
                            ", order not fully factored"
                        }
                    ),
                    cost,
                )
            }
        };
        report.checks.push(WeakCheck {
            method: Method::Singular,
            applicable: true,
            explanation: expl,
            estimated_log2_ops: cost,
        });
        report.singular = Some(info);
        report.recommended = Some(Method::Singular);
        return finish(report);
    }
    report.checks.push(WeakCheck {
        method: Method::Singular,
        applicable: false,
        explanation: "4a³ + 27b² ≢ 0 (mod p): the curve is non-singular".into(),
        estimated_log2_ops: None,
    });

    if order.is_zero() || ec.mul(&gl, order) != AffinePoint::Infinity {
        report
            .input_problems
            .push("the claimed order does not annihilate G".into());
        return finish(report);
    }

    // 2. Anomalous.
    let anomalous = order == p;
    report.checks.push(WeakCheck {
        method: Method::Smart,
        applicable: anomalous,
        explanation: if anomalous {
            "ord(G) = p, so #E(F_p) = p (Hasse: p | #E < 2p): anomalous; Smart's p-adic \
             lift solves the DLP in polynomial time"
                .into()
        } else {
            "ord(G) ≠ p: not anomalous".into()
        },
        estimated_log2_ops: anomalous.then(|| (4.0 * p.bits() as f64).log2()),
    });

    // 3. Smooth order.
    let fac = if opts.order_factorization.is_empty() {
        factor(order, &opts.factor)
    } else {
        match smooth_order::check_factorization(order, &opts.order_factorization) {
            Ok(()) => Factorization {
                factors: opts.order_factorization.clone(),
                unfactored: Vec::new(),
                rho_iterations: 0,
            },
            Err(e) => {
                report.input_problems.push(e.to_string());
                factor(order, &opts.factor)
            }
        }
    };
    let ph_cost = fac.is_complete().then(|| ph_log2_cost(&fac.factors));
    let largest = fac.largest_prime().cloned();
    let ph_ok = ph_cost.is_some_and(|c| c <= opts.max_log2_ops);
    report.checks.push(WeakCheck {
        method: Method::PohligHellman,
        applicable: ph_ok,
        explanation: match (&ph_cost, &largest) {
            (Some(c), Some(l)) => format!(
                "order = {}; largest prime factor {} bits; Pohlig–Hellman needs ≈2^{:.1} \
                 group operations ({} the 2^{} budget)",
                fac.factors
                    .iter()
                    .map(|(q, e)| if *e == 1 {
                        q.to_string()
                    } else {
                        format!("{q}^{e}")
                    })
                    .collect::<Vec<_>>()
                    .join(" · "),
                l.bits(),
                c,
                if ph_ok { "within" } else { "exceeds" },
                opts.max_log2_ops
            ),
            _ => format!(
                "order not fully factored within the budget ({} composite part(s) left)",
                fac.unfactored.len()
            ),
        },
        estimated_log2_ops: ph_cost,
    });

    // 4. Embedding degree of the largest prime factor.
    let mut mov_check = WeakCheck {
        method: Method::Mov,
        applicable: false,
        explanation: String::new(),
        estimated_log2_ops: None,
    };
    match &largest {
        Some(l) if l == p => {
            mov_check.explanation = "the order is p: no embedding degree (see Smart)".into();
        }
        Some(l) => match embedding_degree(p, l, opts.max_embedding_degree) {
            None => {
                mov_check.explanation = format!(
                    "embedding degree of the largest prime factor exceeds {}: MOV/Frey–Rück \
                     gives no usable transfer",
                    opts.max_embedding_degree
                );
            }
            Some(k) => {
                report.embedding_degree = Some(k);
                let mut rng = arith::seeded_rng(opts.solver.seed ^ 0xe0);
                let from_params = &curve.n * BigUint::from(curve.h);
                let e_order = opts
                    .curve_order
                    .clone()
                    .or_else(|| (!from_params.is_zero()).then_some(from_params));
                let checked = e_order
                    .as_ref()
                    .map(|e| mov::check_curve_order(&ec, e, l, &mut rng));
                let prime_order = order == l;
                let bits = p.bits() * u64::from(k);
                let base = format!(
                    "embedding degree k = {k} for the {}-bit prime factor: the Tate pairing \
                     maps the DLP into F_{{p^{k}}}* ({bits}-bit field), where index \
                     calculus / NFS would be subexponential (not implemented here); with the \
                     generic solver here the transferred DLP still costs ≈√ℓ",
                    l.bits()
                );
                match checked {
                    Some(Ok(())) => {
                        report.curve_order = e_order.clone();
                        mov_check.applicable = prime_order;
                        mov_check.explanation = if prime_order {
                            base
                        } else {
                            format!(
                                "{base}; mov_attack needs a prime-order G (Pohlig–Hellman \
                                 handles the composite order)"
                            )
                        };
                        mov_check.estimated_log2_ops =
                            Some(0.5 * (log2_f(l) + (std::f64::consts::PI / 2.0).log2()));
                    }
                    Some(Err(e)) => {
                        mov_check.explanation = format!("{base}; #E(F_p) unusable: {e}");
                    }
                    None => {
                        mov_check.explanation =
                            format!("{base}; #E(F_p) unknown (set AttackOptions::curve_order)");
                    }
                }
            }
        },
        None => {
            mov_check.explanation = "no prime factor of the order known".into();
        }
    }
    report.checks.push(mov_check);
    report.order_factorization = Some(fac);

    report.recommended = if anomalous {
        Some(Method::Smart)
    } else if ph_ok {
        Some(Method::PohligHellman)
    } else {
        None
    };
    finish(report)
}

/// Detect the weakness and run the cheapest applicable attack with
/// default options.  See [`attack_with`].
pub fn attack(
    curve: &CurveParams,
    g: &Point,
    q: &Point,
    order: &BigUint,
) -> Result<AttackOutcome, WeakCurveError> {
    attack_with(curve, g, q, order, &AttackOptions::default())
}

/// Analyse, then run the recommended (or forced) attack.  The returned
/// scalar is always verified: `scalar·G = Q`.
pub fn attack_with(
    curve: &CurveParams,
    g: &Point,
    q: &Point,
    order: &BigUint,
    opts: &AttackOptions,
) -> Result<AttackOutcome, WeakCurveError> {
    let t0 = Instant::now();
    let report = analyze_with(curve, g, q, order, opts);
    if !report.input_problems.is_empty() {
        return Err(WeakCurveError::InvalidInput(
            report.input_problems.join("; "),
        ));
    }
    let method = match opts.force.or(report.recommended) {
        Some(m) => m,
        None => {
            let why = report
                .checks
                .iter()
                .map(|c| format!("{:?}: {}", c.method, c.explanation))
                .collect::<Vec<_>>()
                .join(" | ");
            return Err(WeakCurveError::NoApplicableAttack(why));
        }
    };
    let t1 = Instant::now();
    let (scalar, details) = match method {
        Method::Singular => {
            let out = singular_attack(curve, g, q, &opts.solver)?;
            (out.scalar.clone(), AttackDetails::Singular(out))
        }
        Method::Smart => {
            let sopts = SmartOptions {
                max_lifts: opts.smart_max_lifts,
                seed: opts.solver.seed,
            };
            let out = smart_attack(curve, g, q, &sopts)?;
            (out.scalar.clone(), AttackDetails::Smart(out))
        }
        Method::PohligHellman => {
            let popts = PohligHellmanOptions {
                factor: opts.factor.clone(),
                solver: opts.solver.clone(),
            };
            let supplied = report
                .order_factorization
                .as_ref()
                .filter(|f| f.is_complete())
                .map(|f| f.factors.clone());
            let out = pohlig_hellman_attack(curve, g, q, order, supplied.as_deref(), &popts)?;
            (out.scalar.clone(), AttackDetails::PohligHellman(out))
        }
        Method::Mov => {
            let e_order = report.curve_order.clone().ok_or_else(|| {
                WeakCurveError::NotApplicable(
                    "MOV needs a validated #E(F_p) (AttackOptions::curve_order)".into(),
                )
            })?;
            let mopts = MovOptions {
                max_k: opts.max_embedding_degree,
                solver: opts.solver.clone(),
                ..MovOptions::default()
            };
            let out = mov_attack(curve, g, q, order, &e_order, &mopts)?;
            (out.scalar.clone(), AttackDetails::Mov(out))
        }
    };
    let attack_ms = t1.elapsed().as_secs_f64() * 1e3;
    if g.scalar_mul(&scalar, &curve.a_fe()) != *q {
        return Err(WeakCurveError::VerificationFailed);
    }
    Ok(AttackOutcome {
        method,
        scalar,
        verified: true,
        report,
        details,
        attack_ms,
        total_ms: t0.elapsed().as_secs_f64() * 1e3,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use num_bigint::RandBigInt;

    #[test]
    fn dispatch_anomalous_256() {
        let mut rng = arith::seeded_rng(99);
        let ac = anomalous_curve_cm(256, 19, &mut rng).unwrap();
        let curve = ac.to_curve_params();
        let g = curve.generator();
        let d = rng.gen_biguint_below(&curve.p);
        let q = g.scalar_mul(&d, &curve.a_fe());
        let report = analyze(&curve, &g, &q, &curve.n);
        assert_eq!(report.recommended, Some(Method::Smart));
        let out = attack(&curve, &g, &q, &curve.n).unwrap();
        assert_eq!(out.method, Method::Smart);
        assert_eq!(out.scalar, d);
        assert!(out.verified);
        // The report serialises.
        let json = serde_json::to_string(&out).unwrap();
        assert!(json.contains("\"Smart\""));
    }

    #[test]
    fn dispatch_smooth_order_128() {
        let (curve, full_order) = smooth_order::tests::curve128();
        let g = curve.generator();
        let d = BigUint::from(0xdead_beef_cafe_f00d_u64);
        let q = g.scalar_mul(&d, &curve.a_fe());
        let out = attack(&curve, &g, &q, &full_order).unwrap();
        assert_eq!(out.method, Method::PohligHellman);
        assert_eq!(out.scalar, d);
        let mov = out
            .report
            .checks
            .iter()
            .find(|c| c.method == Method::Mov)
            .unwrap();
        assert!(!mov.applicable);
    }

    #[test]
    fn dispatch_singular_cusp_and_node() {
        let p = BigUint::from(1_000_000_007u64);
        // Node: x₀ = 5  ⇒  a = −75, b = 250.
        let a = &p - 75u32;
        let b = BigUint::from(250u32);
        let ec = Ec::new(&p, &a, &b);
        let mut rng = arith::seeded_rng(4);
        let AffinePoint::Affine(gx, gy) = ec.random_point(&mut rng) else {
            unreachable!()
        };
        let curve = CurveParams {
            name: "ctf-node",
            p: p.clone(),
            a,
            b,
            gx,
            gy,
            n: BigUint::zero(),
            h: 1,
        };
        let g = curve.generator();
        let d = BigUint::from(123_456u32);
        let q = g.scalar_mul(&d, &curve.a_fe());
        let out = attack(&curve, &g, &q, &BigUint::zero()).unwrap();
        assert_eq!(out.method, Method::Singular);
        assert_eq!(g.scalar_mul(&out.scalar, &curve.a_fe()), q);
    }

    #[test]
    fn dispatch_forced_mov_on_mnt_k6() {
        let curve = CurveParams {
            name: "mnt-k6",
            p: BigUint::from(1_074_135_077u64),
            a: BigUint::from(591_694_560u64),
            b: BigUint::from(1_006_828_055u64),
            gx: BigUint::from(896_518_891u64),
            gy: BigUint::from(410_619_860u64),
            n: BigUint::from(1_074_167_851u64),
            h: 1,
        };
        let g = curve.generator();
        let d = BigUint::from(99_999_999u32);
        let q = g.scalar_mul(&d, &curve.a_fe());
        let report = analyze(&curve, &g, &q, &curve.n);
        assert_eq!(report.embedding_degree, Some(6));
        assert!(report
            .checks
            .iter()
            .any(|c| c.method == Method::Mov && c.applicable));
        // Unforced, the generic Pohlig–Hellman is (honestly) no worse.
        assert_eq!(report.recommended, Some(Method::PohligHellman));
        let opts = AttackOptions {
            force: Some(Method::Mov),
            ..AttackOptions::default()
        };
        let out = attack_with(&curve, &g, &q, &curve.n, &opts).unwrap();
        assert_eq!(out.method, Method::Mov);
        assert_eq!(out.scalar, d);
    }

    #[test]
    fn dispatch_refuses_strong_curve() {
        let curve = CurveParams::p256();
        let g = curve.generator();
        let q = g.scalar_mul(&BigUint::from(5u32), &curve.a_fe());
        let report = analyze(&curve, &g, &q, &curve.n);
        assert!(report.input_problems.is_empty());
        assert_eq!(report.recommended, None);
        assert!(report.checks.iter().all(|c| !c.applicable));
        let err = attack(&curve, &g, &q, &curve.n).unwrap_err();
        assert!(matches!(err, WeakCurveError::NoApplicableAttack(_)));
    }

    #[test]
    fn dispatch_rejects_bad_input() {
        let curve = CurveParams::p256();
        let g = curve.generator();
        let wrong = &curve.n - 1u32;
        let report = analyze(&curve, &g, &g, &wrong);
        assert!(!report.input_problems.is_empty());
    }
}
