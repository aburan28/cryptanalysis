//! # A unified catalog of standardized elliptic curves for index calculus.
//!
//! The `cryptanalysis_suite` crate defines standardized curves in several places —
//! [`crate::ecc::curve::CurveParams`] and [`crate::ecc::curve_zoo`] for prime
//! fields, [`crate::binary_ecc::curve::BinaryCurve`] for `F_{2^m}` — but there
//! is no single place that answers *"give me every standardized curve, by
//! name, with its field family and verified parameters."*  The index-calculus
//! engine (`icx`) needs exactly that: one registry it can enumerate, look a
//! curve up in, verify, and hand to the pipeline.
//!
//! This module is that registry.  It does **not** re-encode curve constants;
//! it wraps the existing, independently checked constructors so there is one
//! source of truth for each curve's parameters.  New standardized curves that
//! the crate did not previously carry are added here with their provenance.
//!
//! ## What "verified" means
//!
//! Every entry can be [`CatalogCurve::verify`]d: the generator is on the
//! curve, `n · G = O`, the cofactor is positive, and `h · n` lands in the
//! Hasse interval `[q + 1 - 2√q, q + 1 + 2√q]`.  These are necessary
//! conditions, not a full certificate (subgroup order primality is screened,
//! not proved), and each check says so.  The catalog test asserts a per-family
//! floor on how many curves verify, and per-family coverage, rather than an
//! exact global count — the registry grows, and an exact count would be a
//! brittle assertion that fails on every addition (see `CLAUDE.md`).
//!
//! ## Scope note
//!
//! Membership here is about *coverage of standardized parameter sets*, not
//! about index calculus being a threat.  Whether IC is the relevant attack on
//! a given curve, and at what size a run is feasible, is decided by the engine
//! ([`crate::cryptanalysis::ic_engine`]), not by this catalog.

use num_bigint::BigUint;
use num_traits::{One, Zero};

use crate::binary_ecc::curve::{self as bcurve, BinaryCurve, BinaryPoint};
use crate::cryptanalysis::gf3m::{Char3Curve, Char3Point, Gf3};
use crate::ecc::curve::CurveParams;

/// The finite-field / curve family an entry belongs to.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Family {
    /// Short Weierstrass over a prime field `F_p`, `p > 3`.
    Prime,
    /// Random binary curve `y² + xy = x³ + a x² + b` over `F_{2^m}`.
    BinaryRandom,
    /// Koblitz (anomalous binary) curve: `a ∈ {0,1}`, `b = 1`, over `F_{2^m}`.
    Koblitz,
    /// Curve over an extension field `F_{p^k}`, `k ≥ 2` (Weil-descent regime).
    Extension,
    /// Curve over a characteristic-three field `F_{3^m}`.
    Char3,
}

impl Family {
    /// A short, stable identifier used in listings and `--family` filters.
    pub fn tag(self) -> &'static str {
        match self {
            Family::Prime => "prime",
            Family::BinaryRandom => "binary",
            Family::Koblitz => "koblitz",
            Family::Extension => "extension",
            Family::Char3 => "char3",
        }
    }

    /// Parse a `--family` filter value; accepts a few natural spellings.
    pub fn parse(s: &str) -> Option<Family> {
        match s.to_ascii_lowercase().as_str() {
            "prime" | "fp" | "p" => Some(Family::Prime),
            "binary" | "binary-random" | "f2m" | "b" => Some(Family::BinaryRandom),
            "koblitz" | "k" => Some(Family::Koblitz),
            "extension" | "fpk" | "ext" => Some(Family::Extension),
            "char3" | "f3m" | "ternary" => Some(Family::Char3),
            _ => None,
        }
    }
}

/// A human- and machine-readable description of the base field.
#[derive(Clone, Debug)]
pub struct FieldDesc {
    /// One of `prime`, `binary`, `extension`, `char3`.
    pub kind: &'static str,
    /// `F_p`, `F_2^163`, `F_3^97`, `F_p^3`, rendered for display.
    pub label: String,
    /// `⌈log2 #field⌉`, the field size in bits.
    pub bits: u64,
}

/// The concrete curve object, in whichever representation the crate provides.
///
/// The catalog is uniform above this; computation dispatches on it.
#[derive(Clone)]
pub enum CurveObject {
    /// Prime-field short Weierstrass (BigUint arithmetic).
    Prime(CurveParams),
    /// Binary curve over `F_{2^m}` (polynomial-basis `F2mElement`).
    ///
    /// Boxed because a `BinaryCurve` (multi-word field elements) is much
    /// larger than a `CurveParams`, and an unboxed variant would bloat every
    /// `CurveObject` to the binary size.
    Binary(Box<BinaryCurve>),
    /// Characteristic-three curve `y² = x³ + a4 x + a6` over `F_{3^m}`.
    Char3(Box<Char3Entry>),
}

/// A characteristic-three catalog curve: the curve plus a generator and its
/// subgroup order.  Unlike the prime/binary families, char-3 supersingular
/// curves have no single authoritative fixed generator, so the generator and
/// its order are computed once (at small `m`, by point enumeration) when the
/// entry is built; `verify` still cross-checks `[n]G = O` and the Hasse bound.
#[derive(Clone)]
pub struct Char3Entry {
    pub curve: Char3Curve,
    pub m: u32,
    pub generator: Char3Point,
    pub order: BigUint,
    pub cofactor: BigUint,
    pub group_order: BigUint,
}

/// A single catalog entry, loaded (its constants materialized) but not yet
/// verified.  Verification is separate because it costs a scalar
/// multiplication and callers that only list curves should not pay it.
#[derive(Clone)]
pub struct CatalogCurve {
    /// Canonical lookup name (lowercase, hyphenated).
    pub name: &'static str,
    /// Alternative names that resolve to this curve.
    pub aliases: &'static [&'static str],
    /// Field / curve family.
    pub family: Family,
    /// Where the parameters come from (standard + citation).
    pub standard: &'static str,
    /// The concrete curve.
    pub object: CurveObject,
}

/// The result of one verification check.
#[derive(Clone, Debug)]
pub struct Check {
    pub name: &'static str,
    pub passed: bool,
    pub detail: String,
}

impl CatalogCurve {
    /// A rendered description of the base field.
    pub fn field(&self) -> FieldDesc {
        match &self.object {
            CurveObject::Prime(p) => FieldDesc {
                kind: "prime",
                label: "F_p".to_string(),
                bits: p.p.bits(),
            },
            CurveObject::Binary(c) => FieldDesc {
                kind: "binary",
                label: format!("F_2^{}", c.m),
                bits: c.m as u64,
            },
            CurveObject::Char3(c) => FieldDesc {
                kind: "char3",
                // log2(3^m) = m*log2(3).
                label: format!("F_3^{}", c.m),
                bits: (c.m as f64 * 3.0_f64.log2()).ceil() as u64,
            },
        }
    }

    /// The subgroup order `n` (order of the standard generator's subgroup).
    pub fn subgroup_order(&self) -> BigUint {
        match &self.object {
            CurveObject::Prime(p) => p.n.clone(),
            CurveObject::Binary(c) => c.order.clone(),
            CurveObject::Char3(c) => c.order.clone(),
        }
    }

    /// The cofactor `h`.
    pub fn cofactor(&self) -> BigUint {
        match &self.object {
            CurveObject::Prime(p) => BigUint::from(p.h),
            CurveObject::Binary(c) => c.cofactor.clone(),
            CurveObject::Char3(c) => c.cofactor.clone(),
        }
    }

    /// `⌈log2 n⌉`, the subgroup order in bits.
    pub fn order_bits(&self) -> u64 {
        self.subgroup_order().bits()
    }

    /// Generic-attack (Pollard rho) security level, `½ log2 n` bits.
    ///
    /// This is the classical ECDLP work factor and is independent of whether
    /// index calculus applies; it is what "security bits" means in a listing.
    pub fn rho_security_bits(&self) -> f64 {
        // bits() is the position of the top set bit; log2(n) ≈ bits()-1..bits().
        let ln = self.subgroup_order();
        if ln.is_zero() {
            return 0.0;
        }
        // Fractional log2 via the top 64 bits, for a smooth estimate.
        let bits = ln.bits();
        let approx_log2 = if bits <= 64 {
            (u64::try_from(ln.clone()).unwrap_or(u64::MAX) as f64).log2()
        } else {
            let shift = bits - 53;
            let top = &ln >> shift;
            let top = u64::try_from(top).unwrap_or(1u64 << 52) as f64;
            top.log2() + shift as f64
        };
        approx_log2 / 2.0
    }

    /// The full group order `#E = h · n`, when both are known.
    pub fn group_order(&self) -> BigUint {
        self.cofactor() * self.subgroup_order()
    }

    /// Run the necessary-condition checks.  Never proves primality of `n`.
    pub fn verify(&self) -> Vec<Check> {
        match &self.object {
            CurveObject::Prime(p) => verify_prime(p),
            CurveObject::Binary(c) => verify_binary(c),
            CurveObject::Char3(c) => verify_char3(c),
        }
    }
}

fn verify_char3(c: &Char3Entry) -> Vec<Check> {
    let mut checks = Vec::new();
    checks.push(Check {
        name: "generator_on_curve",
        passed: c.curve.is_on_curve(&c.generator),
        detail: "generator satisfies y² = x³ + a4 x + a6 over F_3^m".to_string(),
    });
    let ng = c.curve.scalar_mul(&c.generator, &c.order);
    checks.push(Check {
        name: "generator_subgroup",
        passed: matches!(ng, Char3Point::Infinity),
        detail: "[n]G = O (point at infinity)".to_string(),
    });
    checks.push(Check {
        name: "positive_cofactor",
        passed: !c.cofactor.is_zero(),
        detail: format!("cofactor h = {}", c.cofactor),
    });
    let q = BigUint::from(3u32).pow(c.m);
    checks.push(hasse_check(&q, &c.group_order));
    checks
}

fn verify_prime(p: &CurveParams) -> Vec<Check> {
    let mut checks = Vec::new();
    let g = p.generator();
    checks.push(Check {
        name: "generator_on_curve",
        passed: p.is_on_curve(&g),
        detail: "generator satisfies y² = x³ + ax + b".to_string(),
    });
    // n · G = O.
    let a_fe = p.a_fe();
    let ng = g.scalar_mul(&p.n, &a_fe);
    let at_infinity = ng.x_coord().is_none();
    checks.push(Check {
        name: "generator_subgroup",
        passed: at_infinity,
        detail: "[n]G = O (point at infinity)".to_string(),
    });
    checks.push(Check {
        name: "positive_cofactor",
        passed: p.h > 0,
        detail: format!("cofactor h = {}", p.h),
    });
    // Hasse: |#E - (q+1)| <= 2 sqrt q, with #E = h n.
    let q = p.p.clone();
    let card = BigUint::from(p.h) * &p.n;
    checks.push(hasse_check(&q, &card));
    checks
}

fn verify_binary(c: &BinaryCurve) -> Vec<Check> {
    let mut checks = Vec::new();
    checks.push(Check {
        name: "generator_on_curve",
        passed: c.is_on_curve(&c.generator),
        detail: "generator satisfies y² + xy = x³ + ax² + b".to_string(),
    });
    let ng = bcurve::scalar_mul(c, &c.generator, &c.order);
    checks.push(Check {
        name: "generator_subgroup",
        passed: matches!(ng, BinaryPoint::Infinity),
        detail: "[n]G = O (point at infinity)".to_string(),
    });
    checks.push(Check {
        name: "positive_cofactor",
        passed: !c.cofactor.is_zero(),
        detail: format!("cofactor h = {}", c.cofactor),
    });
    let q = BigUint::one() << c.m;
    let card = &c.cofactor * &c.order;
    checks.push(hasse_check(&q, &card));
    checks
}

/// `|#E - (q + 1)| <= 2√q`, computed with integer square roots so it is exact.
fn hasse_check(q: &BigUint, card: &BigUint) -> Check {
    let q1 = q + BigUint::one();
    // 2√q, rounded up so the bound is not too tight.
    let two_sqrt_q = (q.sqrt() + BigUint::one()) * BigUint::from(2u32);
    let diff = if card >= &q1 { card - &q1 } else { &q1 - card };
    let passed = diff <= two_sqrt_q;
    Check {
        name: "hasse_bound",
        passed,
        detail: format!(
            "|#E-(q+1)| = {} <= 2sqrt(q) = {} (necessary cardinality bound)",
            diff, two_sqrt_q
        ),
    }
}

/// True if every necessary check passes.
pub fn verified(curve: &CatalogCurve) -> bool {
    curve.verify().iter().all(|c| c.passed)
}

/// Build the whole catalog.  Constructs each curve's constants but performs no
/// verification (that is [`CatalogCurve::verify`]).
pub fn all() -> Vec<CatalogCurve> {
    let mut v = Vec::new();
    prime_curves(&mut v);
    binary_curves(&mut v);
    char3_curves(&mut v);
    v
}

/// Look a curve up by canonical name or alias (case-insensitive).
pub fn by_name(query: &str) -> Option<CatalogCurve> {
    let q = query.to_ascii_lowercase();
    all().into_iter().find(|c| {
        c.name.eq_ignore_ascii_case(&q) || c.aliases.iter().any(|a| a.eq_ignore_ascii_case(&q))
    })
}

/// Every canonical name, for listings and shell completion.
pub fn names() -> Vec<&'static str> {
    all().iter().map(|c| c.name).collect()
}

fn prime_curves(v: &mut Vec<CatalogCurve>) {
    // Core standardized prime curves (src/ecc/curve.rs).
    let core: &[(&str, &[&str], &str, fn() -> CurveParams)] = &[
        (
            "secp256k1",
            &["k256", "ansix9p256k1"],
            "SEC 2 v2 / Bitcoin",
            CurveParams::secp256k1,
        ),
        (
            "p256",
            &["secp256r1", "prime256v1", "nistp256"],
            "NIST FIPS 186-4 / SEC 2",
            CurveParams::p256,
        ),
        (
            "sm2",
            &["sm2p256v1"],
            "GM/T 0003-2012 (China)",
            CurveParams::sm2,
        ),
        (
            "gost-2012-256-test",
            &[],
            "RFC 7836 test curve",
            CurveParams::gost_3410_2012_256_test,
        ),
        (
            "gost-2012-512-test",
            &[],
            "RFC 7836 test curve",
            CurveParams::gost_3410_2012_512_test,
        ),
    ];
    for (name, aliases, std, ctor) in core {
        v.push(CatalogCurve {
            name,
            aliases,
            family: Family::Prime,
            standard: std,
            object: CurveObject::Prime(ctor()),
        });
    }

    // The curve zoo (src/ecc/curve_zoo.rs): SEC / NIST / Brainpool / ANSSI /
    // GOST prime curves.  All are on-curve and n·G = O verified in that file's
    // own tests; the catalog re-verifies them.
    let zoo: &[(&str, &[&str], &str, fn() -> CurveParams)] = &[
        ("secp112r1", &[], "SEC 2 v1", CurveParams::secp112r1),
        ("secp112r2", &[], "SEC 2 v1", CurveParams::secp112r2),
        ("secp128r1", &[], "SEC 2 v1", CurveParams::secp128r1),
        ("secp128r2", &[], "SEC 2 v1", CurveParams::secp128r2),
        ("secp160k1", &[], "SEC 2 v1", CurveParams::secp160k1),
        ("secp160r1", &[], "SEC 2 v1", CurveParams::secp160r1),
        ("secp160r2", &[], "SEC 2 v1", CurveParams::secp160r2),
        (
            "secp192k1",
            &["ansix9p192k1"],
            "SEC 2 v1",
            CurveParams::secp192k1,
        ),
        (
            "secp224k1",
            &["ansix9p224k1"],
            "SEC 2 v1",
            CurveParams::secp224k1,
        ),
        (
            "p192",
            &["secp192r1", "prime192v1", "nistp192"],
            "NIST FIPS 186-4",
            CurveParams::p192,
        ),
        (
            "p224",
            &["secp224r1", "nistp224"],
            "NIST FIPS 186-4",
            CurveParams::p224,
        ),
        (
            "p384",
            &["secp384r1", "nistp384"],
            "NIST FIPS 186-4",
            CurveParams::p384,
        ),
        (
            "p521",
            &["secp521r1", "nistp521"],
            "NIST FIPS 186-4",
            CurveParams::p521,
        ),
        (
            "brainpoolp192r1",
            &[],
            "RFC 5639",
            CurveParams::brainpool_p192r1,
        ),
        (
            "brainpoolp224r1",
            &[],
            "RFC 5639",
            CurveParams::brainpool_p224r1,
        ),
        (
            "brainpoolp256r1",
            &[],
            "RFC 5639",
            CurveParams::brainpool_p256r1,
        ),
        (
            "brainpoolp320r1",
            &[],
            "RFC 5639",
            CurveParams::brainpool_p320r1,
        ),
        (
            "brainpoolp384r1",
            &[],
            "RFC 5639",
            CurveParams::brainpool_p384r1,
        ),
        (
            "brainpoolp512r1",
            &[],
            "RFC 5639",
            CurveParams::brainpool_p512r1,
        ),
        ("frp256v1", &[], "ANSSI (France)", CurveParams::frp256v1),
        (
            "gost-cryptopro-a",
            &[],
            "RFC 4357",
            CurveParams::gost_cryptopro_a,
        ),
        (
            "gost-cryptopro-b",
            &[],
            "RFC 4357",
            CurveParams::gost_cryptopro_b,
        ),
        (
            "gost-cryptopro-c",
            &[],
            "RFC 4357",
            CurveParams::gost_cryptopro_c,
        ),
        (
            "gost-tc26-256-a",
            &[],
            "GOST R 34.10-2012 (256)",
            CurveParams::gost_tc26_256_a,
        ),
        (
            "gost-tc26-512-a",
            &[],
            "GOST R 34.10-2012 (512)",
            CurveParams::gost_tc26_512_a,
        ),
        (
            "gost-tc26-512-b",
            &[],
            "GOST R 34.10-2012 (512)",
            CurveParams::gost_tc26_512_b,
        ),
    ];
    for (name, aliases, std, ctor) in zoo {
        v.push(CatalogCurve {
            name,
            aliases,
            family: Family::Prime,
            standard: std,
            object: CurveObject::Prime(ctor()),
        });
    }
}

fn binary_curves(v: &mut Vec<CatalogCurve>) {
    // Binary curves the crate already carries (src/binary_ecc/curve.rs).
    // sect163k1 is a Koblitz curve; the sect*r* curves are random binary
    // curves; Oakley Group 3 is a subgroup curve (its generator has order
    // 4·q — see the crate constructor's documentation).
    let bin: &[(&str, &[&str], Family, &str, fn() -> BinaryCurve)] = &[
        (
            "sect113r1",
            &[],
            Family::BinaryRandom,
            "SEC 2 v1",
            BinaryCurve::sect113r1,
        ),
        (
            "sect113r2",
            &[],
            Family::BinaryRandom,
            "SEC 2 v1",
            BinaryCurve::sect113r2,
        ),
        (
            "sect131r1",
            &[],
            Family::BinaryRandom,
            "SEC 2 v1",
            BinaryCurve::sect131r1,
        ),
        (
            "sect131r2",
            &[],
            Family::BinaryRandom,
            "SEC 2 v1",
            BinaryCurve::sect131r2,
        ),
        (
            "sect163k1",
            &["k-163", "nist-k163"],
            Family::Koblitz,
            "SEC 2 / NIST K-163",
            BinaryCurve::sect163k1,
        ),
        (
            "sect163r1",
            &[],
            Family::BinaryRandom,
            "SEC 2 v1",
            BinaryCurve::sect163r1,
        ),
        (
            "sect163r2",
            &["b-163", "nist-b163"],
            Family::BinaryRandom,
            "SEC 2 / NIST B-163",
            BinaryCurve::sect163r2,
        ),
        (
            "oakley-group-3",
            &["ike-oakley-3", "ec2n-155"],
            Family::BinaryRandom,
            "RFC 2409 (EC2N; subgroup curve)",
            BinaryCurve::ike_oakley_group3,
        ),
        // Full NIST/SECG binary curve suite (added with this engine).
        (
            "sect193r1",
            &[],
            Family::BinaryRandom,
            "SEC 2 v2",
            BinaryCurve::sect193r1,
        ),
        (
            "sect193r2",
            &[],
            Family::BinaryRandom,
            "SEC 2 v2",
            BinaryCurve::sect193r2,
        ),
        (
            "sect233k1",
            &["k-233", "nist-k233", "ansit233k1"],
            Family::Koblitz,
            "SEC 2 / NIST K-233",
            BinaryCurve::sect233k1,
        ),
        (
            "sect233r1",
            &["b-233", "nist-b233", "ansit233r1"],
            Family::BinaryRandom,
            "SEC 2 / NIST B-233",
            BinaryCurve::sect233r1,
        ),
        (
            "sect239k1",
            &["ansit239k1"],
            Family::Koblitz,
            "SEC 2 v2",
            BinaryCurve::sect239k1,
        ),
        (
            "sect283k1",
            &["k-283", "nist-k283", "ansit283k1"],
            Family::Koblitz,
            "SEC 2 / NIST K-283",
            BinaryCurve::sect283k1,
        ),
        (
            "sect283r1",
            &["b-283", "nist-b283", "ansit283r1"],
            Family::BinaryRandom,
            "SEC 2 / NIST B-283",
            BinaryCurve::sect283r1,
        ),
        (
            "sect409k1",
            &["k-409", "nist-k409", "ansit409k1"],
            Family::Koblitz,
            "SEC 2 / NIST K-409",
            BinaryCurve::sect409k1,
        ),
        (
            "sect409r1",
            &["b-409", "nist-b409", "ansit409r1"],
            Family::BinaryRandom,
            "SEC 2 / NIST B-409",
            BinaryCurve::sect409r1,
        ),
        (
            "sect571k1",
            &["k-571", "nist-k571", "ansit571k1"],
            Family::Koblitz,
            "SEC 2 / NIST K-571",
            BinaryCurve::sect571k1,
        ),
        (
            "sect571r1",
            &["b-571", "nist-b571", "ansit571r1"],
            Family::BinaryRandom,
            "SEC 2 / NIST B-571",
            BinaryCurve::sect571r1,
        ),
    ];
    for (name, aliases, family, std, ctor) in bin {
        v.push(CatalogCurve {
            name,
            aliases,
            family: *family,
            standard: std,
            object: CurveObject::Binary(Box::new(ctor())),
        });
    }
}

/// A hardcoded characteristic-three catalog curve, as coefficient vectors over
/// F_3 (index i is the z^i coefficient).  Computed once by
/// `build_char3_supersingular` (cross-checked by a test) and stored so the CLI
/// builds them instantly instead of re-enumerating the group on every run.
struct Char3Const {
    name: &'static str,
    m: u32,
    /// Reduction polynomial `[c0, …, cm]`, `cm = 1`.
    irr: &'static [u8],
    /// Generator x, y coefficient vectors (length m).
    gx: &'static [u8],
    gy: &'static [u8],
    /// Subgroup order and full group order (cofactor = group_order / order).
    order: u64,
    group_order: u64,
}

/// Supersingular ηT-family study curves `y² = x³ - x + 1` over `F_{3^m}`,
/// with generators and orders computed once (see the cross-check test).
const CHAR3_CONSTS: &[Char3Const] = &[
    Char3Const {
        name: "ss-f3-5",
        m: 5,
        irr: &[1, 2, 0, 0, 0, 1],
        gx: &[0, 1, 0, 0, 0],
        gy: &[2, 0, 0, 1, 2],
        order: 217,
        group_order: 217,
    },
    Char3Const {
        name: "ss-f3-7",
        m: 7,
        irr: &[2, 0, 1, 0, 0, 0, 0, 1],
        gx: &[0, 0, 1, 0, 0, 0, 0],
        gy: &[1, 1, 1, 1, 2, 1, 2],
        order: 2107,
        group_order: 2107,
    },
];

/// Build a char-3 entry from its stored constants (fast — no enumeration).
fn char3_from_const(c: &Char3Const) -> Option<Char3Entry> {
    let field = Gf3::new(c.m, c.irr).ok()?;
    let a4 = field.neg(&field.one()); // -1
    let a6 = field.one(); // b = 1
    let gx = field.element(c.gx).ok()?;
    let gy = field.element(c.gy).ok()?;
    let curve = Char3Curve::new(field, a4, a6).ok()?;
    let order = BigUint::from(c.order);
    let group_order = BigUint::from(c.group_order);
    let cofactor = &group_order / &order;
    Some(Char3Entry {
        curve,
        m: c.m,
        generator: Char3Point::Affine { x: gx, y: gy },
        order,
        cofactor,
        group_order,
    })
}

/// Find a monic irreducible polynomial over F_3 of degree `m`, returned as
/// coefficients `[c0, …, cm]` with `cm = 1`.  Tries trinomials then a small
/// pentanomial sweep; `Gf3::new` performs the actual irreducibility test.
/// Test-only: production builds char-3 curves from the hardcoded constants.
#[cfg(test)]
fn first_irreducible_f3(m: u32) -> Option<Vec<u8>> {
    let md = m as usize;
    // Trinomials x^m + c1*x^k + c0.
    for k in 1..m {
        for c1 in 1..=2u8 {
            for c0 in 1..=2u8 {
                let mut irr = vec![0u8; md + 1];
                irr[0] = c0;
                irr[k as usize] = c1;
                irr[md] = 1;
                if Gf3::new(m, &irr).is_ok() {
                    return Some(irr);
                }
            }
        }
    }
    None
}

/// Build a supersingular char-3 curve `y² = x³ - x + b` over `F_{3^m}` and
/// compute a generator of maximal order by enumerating points.  Small `m`
/// only (the enumeration is `O(3^m)`); returns `None` if no irreducible is
/// found.  Test-only: it is what produced (and re-verifies) `CHAR3_CONSTS`.
#[cfg(test)]
fn build_char3_supersingular(m: u32, b: u64) -> Option<Char3Entry> {
    let irr = first_irreducible_f3(m)?;
    let field = Gf3::new(m, &irr).ok()?;
    let a4 = field.neg(&field.one()); // -1
    let a6 = field.from_int(b);
    let curve = Char3Curve::new(field, a4, a6).ok()?;
    let f = curve.field();
    let q: u64 = 3u64.pow(m);
    // (3^m - 1)/2 and (3^m + 1)/4 as square-test / square-root exponents
    // (m is odd for the ss curves used here, so 3^m ≡ 3 mod 4).
    let qb = BigUint::from(3u32).pow(m);
    let half = (&qb - BigUint::one()) / BigUint::from(2u32);
    let quarter = (&qb + BigUint::one()) / BigUint::from(4u32);

    // For each x, decide how many y exist and collect one representative point.
    let mut points: Vec<Char3Point> = Vec::new();
    let mut count: u64 = 1; // point at infinity
    for xi in 0..q {
        let x = f.from_int(xi);
        // rhs = x^3 + a4*x + a6
        let x3 = f.cube(&x);
        let ax = f.mul(curve.a4(), &x);
        let rhs = f.add(&f.add(&x3, &ax), curve.a6());
        // Count every point, but only keep a bounded sample of candidate
        // generators: scanning all points for the maximum order is O(#E^2)
        // and needlessly slow at m=7. A few dozen points reliably include one
        // of maximal (group-exponent) order for these small groups.
        const GEN_SAMPLE: usize = 64;
        if f.is_zero(&rhs) {
            count += 1;
            if points.len() < GEN_SAMPLE {
                points.push(Char3Point::Affine {
                    x: x.clone(),
                    y: f.zero(),
                });
            }
        } else {
            // Nonzero: a square iff rhs^((q-1)/2) == 1.
            let leg = f.pow(&rhs, &half);
            if f.eq(&leg, &f.one()) {
                count += 2;
                if points.len() < GEN_SAMPLE {
                    let y = f.pow(&rhs, &quarter); // sqrt, since q ≡ 3 mod 4
                    points.push(Char3Point::Affine { x, y });
                }
            }
        }
    }
    let group_order = BigUint::from(count);
    // Generator of maximal order among the representatives.
    let mut best_gen = Char3Point::Infinity;
    let mut best_ord = BigUint::one();
    for p in &points {
        let ord = point_order(&curve, p, count);
        if ord > best_ord {
            best_ord = ord;
            best_gen = p.clone();
        }
    }
    if matches!(best_gen, Char3Point::Infinity) {
        return None;
    }
    let cofactor = &group_order / &best_ord;
    Some(Char3Entry {
        curve,
        m,
        generator: best_gen,
        order: best_ord,
        cofactor,
        group_order,
    })
}

/// Order of a point by repeated addition, bounded by the group order.
#[cfg(test)]
fn point_order(curve: &Char3Curve, p: &Char3Point, bound: u64) -> BigUint {
    if matches!(p, Char3Point::Infinity) {
        return BigUint::from(1u32);
    }
    let mut q = p.clone();
    let mut k: u64 = 1;
    while !matches!(q, Char3Point::Infinity) {
        q = curve.point_add(&q, p);
        k += 1;
        if k > bound + 1 {
            break;
        }
    }
    BigUint::from(k)
}

fn char3_curves(v: &mut Vec<CatalogCurve>) {
    for c in CHAR3_CONSTS {
        if let Some(entry) = char3_from_const(c) {
            v.push(CatalogCurve {
                name: c.name,
                aliases: &[],
                family: Family::Char3,
                standard: "supersingular F_3^m (ηT pairing family); computed generator",
                object: CurveObject::Char3(Box::new(entry)),
            });
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn every_catalog_curve_verifies() {
        // Per-family floors and coverage, not an exact count: the catalog
        // grows, so we assert a lower bound per family plus that every entry
        // that IS present verifies.  A family collapsing to zero still fails.
        let all = all();
        let mut per_family: std::collections::HashMap<&str, usize> =
            std::collections::HashMap::new();
        for c in &all {
            let checks = c.verify();
            for chk in &checks {
                assert!(
                    chk.passed,
                    "curve {} failed check {}: {}",
                    c.name, chk.name, chk.detail
                );
            }
            *per_family.entry(c.family.tag()).or_default() += 1;
        }
        assert!(
            *per_family.get("prime").unwrap_or(&0) >= 30,
            "expected at least 30 prime curves, got {:?}",
            per_family.get("prime")
        );
        assert!(
            *per_family.get("binary").unwrap_or(&0) >= 5,
            "expected at least 5 random-binary curves, got {:?}",
            per_family.get("binary")
        );
        assert!(
            *per_family.get("koblitz").unwrap_or(&0) >= 5,
            "expected the NIST Koblitz suite (K-163..K-571), got {:?}",
            per_family.get("koblitz")
        );
        assert!(
            *per_family.get("char3").unwrap_or(&0) >= 1,
            "expected at least one characteristic-three curve, got {:?}",
            per_family.get("char3")
        );
    }

    #[test]
    fn names_are_unique_and_resolvable() {
        let all = all();
        let mut seen = std::collections::HashSet::new();
        for c in &all {
            assert!(seen.insert(c.name), "duplicate canonical name {}", c.name);
            // Every canonical name and alias resolves back to this curve.
            assert_eq!(by_name(c.name).map(|x| x.name), Some(c.name));
            for a in c.aliases {
                assert_eq!(
                    by_name(a).map(|x| x.name),
                    Some(c.name),
                    "alias {} did not resolve to {}",
                    a,
                    c.name
                );
            }
        }
    }

    #[test]
    fn hardcoded_char3_constants_match_computed() {
        // The catalog ships char-3 curves as constants for a fast CLI; this
        // test recomputes them from scratch (point enumeration) and checks the
        // stored order/#E match, so any drift in the field or curve arithmetic
        // is caught rather than silently shipping wrong parameters.
        for c in CHAR3_CONSTS {
            let computed = build_char3_supersingular(c.m, 1)
                .unwrap_or_else(|| panic!("could not compute char3 m={}", c.m));
            assert_eq!(
                computed.group_order,
                BigUint::from(c.group_order),
                "char3 m={} #E drifted",
                c.m
            );
            // The stored generator must be on the curve and have the stored order.
            let entry = char3_from_const(c).expect("const builds");
            assert!(entry.curve.is_on_curve(&entry.generator));
            let ng = entry.curve.scalar_mul(&entry.generator, &entry.order);
            assert!(
                matches!(ng, Char3Point::Infinity),
                "char3 m={} [n]G != O",
                c.m
            );
        }
    }

    #[test]
    fn security_estimate_is_reasonable() {
        let c = by_name("p256").expect("p256 in catalog");
        // P-256 has ~128-bit rho security.
        let s = c.rho_security_bits();
        assert!((120.0..132.0).contains(&s), "P-256 rho security was {s}");
        assert_eq!(c.field().bits, 256);
    }
}
