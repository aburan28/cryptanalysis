//! Read-only parameter inspection. This module never calls a DLP solver.
use cryptanalysis_suite::{
    binary_ecc::{curve::scalar_mul, BinaryCurve, BinaryPoint, F2mElement, IrreduciblePoly},
    ecc::{curve::CurveParams, field::FieldElement, point::Point},
};
use num_bigint::{BigInt, BigUint};
use num_traits::{One, Zero};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::{fs::File, io::Read, path::Path};

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum Field {
    Binary {
        degree: u32,
        polynomial_terms: Vec<u32>,
    },
    BinaryAbstract {
        degree: u32,
        representation: String,
    },
    Prime {
        modulus: String,
    },
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Coordinates {
    pub x: String,
    pub y: String,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Fixture {
    pub known_log: String,
    pub seed: u64,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Parameters {
    pub schema_version: u32,
    pub name: String,
    pub field: Field,
    pub a: String,
    pub b: String,
    pub subgroup_order: String,
    pub cofactor: String,
    #[serde(default)]
    pub generator: Option<Coordinates>,
    #[serde(default)]
    pub point: Option<Coordinates>,
    #[serde(default)]
    pub fixture: Option<Fixture>,
}
pub fn number(s: &str) -> Result<BigUint, String> {
    if s.is_empty() || s.len() > 320 {
        return Err("integer must contain 1..320 characters".into());
    }
    let (digits, radix) = s.strip_prefix("0x").map_or((s, 10), |v| (v, 16));
    if digits.is_empty()
        || !digits.bytes().all(|c| {
            if radix == 16 {
                c.is_ascii_hexdigit()
            } else {
                c.is_ascii_digit()
            }
        })
    {
        return Err("integers must be decimal or use a 0x hexadecimal prefix".into());
    }
    let n = BigUint::parse_bytes(digits.as_bytes(), radix).ok_or("invalid integer")?;
    if n.bits() > 1024 {
        return Err("integer exceeds the inspection limit of 1024 bits".into());
    }
    Ok(n)
}
pub fn hex(n: &BigUint) -> String {
    format!("0x{}", n.to_str_radix(16))
}
pub fn binary_coordinates(point: &BinaryPoint) -> Option<Coordinates> {
    match point {
        BinaryPoint::Infinity => None,
        BinaryPoint::Affine { x, y } => Some(Coordinates {
            x: hex(&x.to_biguint()),
            y: hex(&y.to_biguint()),
        }),
    }
}
pub const NAMES: &[&str] = &["ecc2k-130", "ecc2k-95", "sect163k1", "secp256k1"];
pub fn named(name: &str) -> Result<Parameters, String> {
    let profile = match name.to_ascii_lowercase().as_str() {
        "ecc2k-130" => Parameters {
            schema_version: 1,
            name: "ECC2K-130".into(),
            field: Field::BinaryAbstract {
                degree: 131,
                representation:
                    "permuted type-II optimal normal basis; point coordinates not imported".into(),
            },
            a: "0".into(),
            b: "1".into(),
            subgroup_order: "680564733841876926932320129493409985129".into(),
            cofactor: "4".into(),
            generator: None,
            point: None,
            fixture: None,
        },
        "ecc2k-95" => Parameters {
            schema_version: 1,
            name: "ECC2K-95".into(),
            field: Field::Binary {
                degree: 97,
                polynomial_terms: vec![97, 6, 0],
            },
            a: "0".into(),
            b: "1".into(),
            subgroup_order: "39614081257132074233778707191".into(),
            cofactor: "4".into(),
            generator: Some(Coordinates {
                x: "0x08A84FB02034F7771DC940097".into(),
                y: "0x1D2F10A471D48A720F18F6339".into(),
            }),
            point: Some(Coordinates {
                x: "0x0E0BC08AC5818F303E2B05E90".into(),
                y: "0x134C028FC3393124D673E6F8E".into(),
            }),
            fixture: None,
        },
        "sect163k1" => {
            let c = BinaryCurve::sect163k1();
            let mut terms = c.irreducible.low_terms.clone();
            terms.push(c.m);
            Parameters {
                schema_version: 1,
                name: "sect163k1".into(),
                field: Field::Binary {
                    degree: c.m,
                    polynomial_terms: terms,
                },
                a: hex(&c.a.to_biguint()),
                b: hex(&c.b.to_biguint()),
                subgroup_order: hex(&c.order),
                cofactor: hex(&c.cofactor),
                generator: binary_coordinates(&c.generator),
                point: None,
                fixture: None,
            }
        }
        "secp256k1" => {
            let c = CurveParams::secp256k1();
            Parameters {
                schema_version: 1,
                name: "secp256k1".into(),
                field: Field::Prime { modulus: hex(&c.p) },
                a: hex(&c.a),
                b: hex(&c.b),
                subgroup_order: hex(&c.n),
                cofactor: c.h.to_string(),
                generator: Some(Coordinates {
                    x: hex(&c.gx),
                    y: hex(&c.gy),
                }),
                point: None,
                fixture: None,
            }
        }
        _ => return Err(format!("unknown curve {name:?}; use ic list")),
    };
    Ok(profile)
}
pub fn load(path: &Path) -> Result<(Parameters, String), String> {
    let mut data = Vec::new();
    File::open(path)
        .map_err(|e| e.to_string())?
        .take(1_048_577)
        .read_to_end(&mut data)
        .map_err(|e| e.to_string())?;
    if data.len() > 1_048_576 {
        return Err("parameter file exceeds 1 MiB".into());
    }
    let p = serde_json::from_slice(&data).map_err(|e| format!("invalid parameter JSON: {e}"))?;
    Ok((p, blake3::hash(&data).to_hex().to_string()))
}
fn poly_rem(mut a: BigUint, b: &BigUint) -> BigUint {
    while !a.is_zero() && a.bits() >= b.bits() {
        let shift = a.bits() - b.bits();
        a ^= b << shift as usize;
    }
    a
}
fn poly_gcd(mut a: BigUint, mut b: BigUint) -> BigUint {
    while !b.is_zero() {
        let r = poly_rem(a, &b);
        a = b;
        b = r;
    }
    a
}
fn irreducible(m: u32, terms: &[u32]) -> Result<IrreduciblePoly, String> {
    let mut seen = std::collections::BTreeSet::new();
    if !terms.iter().all(|&i| i <= m && seen.insert(i)) || !seen.contains(&0) || !seen.contains(&m)
    {
        return Err(
            "polynomial terms must be unique, include 0 and degree, and stay within degree".into(),
        );
    }
    let mut f = BigUint::zero();
    for &i in terms {
        f.set_bit(i as u64, true);
    }
    let x = BigUint::from(2u8);
    let mut xp = x.clone();
    for i in 1..=m {
        let mut square = BigUint::zero();
        for bit in 0..xp.bits() {
            if xp.bit(bit) {
                square.set_bit(2 * bit, true);
            }
        }
        xp = poly_rem(square, &f);
        if i <= m / 2 && poly_gcd(&xp ^ &x, f.clone()) != BigUint::one() {
            return Err("reduction polynomial is reducible over GF(2)".into());
        }
    }
    if xp != x {
        return Err("reduction polynomial failed the Frobenius identity".into());
    }
    Ok(IrreduciblePoly {
        degree: m,
        low_terms: seen.into_iter().filter(|&v| v < m).collect(),
    })
}
// A reproducible compositeness screen, deliberately not labeled a primality proof.
fn probable_prime(n: &BigUint) -> bool {
    if n < &BigUint::from(2u8) {
        return false;
    }
    const BASES: [u32; 12] = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37];
    for base in BASES {
        let b = BigUint::from(base);
        if *n == b {
            return true;
        }
        if (n % &b).is_zero() {
            return false;
        }
    }
    let one = BigUint::one();
    let nm = n - &one;
    let mut d = nm.clone();
    let mut s = 0;
    while !d.bit(0) {
        d >>= 1usize;
        s += 1;
    }
    for base in BASES {
        let mut x = BigUint::from(base).modpow(&d, n);
        if x == one || x == nm {
            continue;
        }
        let mut pass = false;
        for _ in 1..s {
            x = (&x * &x) % n;
            if x == nm {
                pass = true;
                break;
            }
        }
        if !pass {
            return false;
        }
    }
    true
}
fn koblitz_order(a: u8, m: u32) -> BigUint {
    let t = BigInt::from(if a == 0 { -1 } else { 1 });
    let (mut prev, mut current) = (BigInt::from(2), t.clone());
    for _ in 1..m {
        let next = &t * &current - 2 * &prev;
        prev = current;
        current = next;
    }
    ((BigInt::one() << m as usize) + BigInt::one() - current)
        .to_biguint()
        .expect("positive Koblitz order")
}
fn check(checks: &mut Vec<Value>, name: &str, ok: bool, details: &str) {
    checks.push(json!({"name":name,"status":if ok{"pass"}else{"fail"},"details":details}));
}
fn skipped(checks: &mut Vec<Value>, name: &str, details: &str) {
    checks.push(json!({"name":name,"status":"not_checked","details":details}));
}
pub fn inspect(p: Parameters, source: String) -> Result<Value, String> {
    if p.schema_version != 1 {
        return Err("unsupported parameter schema_version".into());
    }
    if p.name.is_empty() || p.name.len() > 120 || p.name.chars().any(char::is_control) {
        return Err("name must contain 1..120 non-control characters".into());
    }
    let a = number(&p.a)?;
    let b = number(&p.b)?;
    let r = number(&p.subgroup_order)?;
    let h = number(&p.cofactor)?;
    let mut checks = Vec::new();
    let r_prime = probable_prime(&r);
    check(
        &mut checks,
        "subgroup_order_screen",
        r_prime,
        "fixed-base Miller-Rabin with bases 2..37; a pass is not a primality proof",
    );
    check(
        &mut checks,
        "positive_cofactor",
        !h.is_zero(),
        "cofactor must be positive",
    );
    let q;
    let mut points_checked = false;
    match &p.field {
        Field::Binary {
            degree,
            polynomial_terms,
        } => {
            if !(2..=571).contains(degree) {
                return Err("binary inspection degrees must be 2..=571".into());
            }
            q = BigUint::one() << *degree as usize;
            let canonical = a < q && b < q;
            check(
                &mut checks,
                "canonical_coefficients",
                canonical,
                "coefficients must fit the declared field without reduction",
            );
            check(
                &mut checks,
                "nonsingular_curve",
                !b.is_zero(),
                "binary Weierstrass form requires b != 0",
            );
            let poly = irreducible(*degree, polynomial_terms);
            check(
                &mut checks,
                "irreducible_polynomial",
                poly.is_ok(),
                poly.as_ref()
                    .err()
                    .map_or("exact Frobenius/GCD test", String::as_str),
            );
            if let Ok(irreducible) = poly {
                if canonical && !b.is_zero() && r_prime {
                    let curve = BinaryCurve {
                        m: *degree,
                        irreducible,
                        a: F2mElement::from_biguint(&a, *degree),
                        b: F2mElement::from_biguint(&b, *degree),
                        generator: BinaryPoint::Infinity,
                        order: r.clone(),
                        cofactor: h.clone(),
                    };
                    let mut parsed = Vec::new();
                    for (label, coords) in [("generator", &p.generator), ("point", &p.point)] {
                        if let Some(c) = coords {
                            let x = number(&c.x)?;
                            let y = number(&c.y)?;
                            if x >= q || y >= q {
                                check(&mut checks, label, false, "noncanonical point coordinate");
                                parsed.push(None);
                                continue;
                            }
                            let pt = BinaryPoint::Affine {
                                x: F2mElement::from_biguint(&x, *degree),
                                y: F2mElement::from_biguint(&y, *degree),
                            };
                            let on = curve.is_on_curve(&pt);
                            check(
                                &mut checks,
                                &format!("{label}_on_curve"),
                                on,
                                "direct curve-equation check",
                            );
                            if on {
                                check(&mut checks,&format!("{label}_subgroup"),scalar_mul(&curve,&pt,&r)==BinaryPoint::Infinity,"[r]P = O; exact-order interpretation remains conditional on primality");
                            }
                            parsed.push(if on { Some(pt) } else { None });
                        } else {
                            skipped(&mut checks, label, "coordinates not supplied");
                            parsed.push(None);
                        }
                    }
                    if let Some(f) = &p.fixture {
                        let k = number(&f.known_log)?;
                        if let (Some(g), Some(t)) = (&parsed[0], &parsed[1]) {
                            check(
                                &mut checks,
                                "known_answer",
                                !k.is_zero() && k < r && scalar_mul(&curve, g, &k) == *t,
                                "generated fixture identity [known_log]G = point",
                            );
                        } else {
                            skipped(
                                &mut checks,
                                "known_answer",
                                "both valid generator and point are required",
                            );
                        }
                    }
                    points_checked = p.generator.is_some() || p.point.is_some();
                } else {
                    skipped(
                        &mut checks,
                        "points",
                        "field, curve, or subgroup-order checks failed",
                    );
                }
            } else {
                skipped(&mut checks, "points", "invalid field polynomial");
            }
            if (a.is_zero() || a.is_one()) && b.is_one() {
                check(
                    &mut checks,
                    "koblitz_group_order",
                    &r * &h == koblitz_order(if a.is_zero() { 0 } else { 1 }, *degree),
                    "exact integer Frobenius trace recurrence",
                );
            } else {
                skipped(
                    &mut checks,
                    "group_cardinality",
                    "general binary-curve point counting is not implemented",
                );
            }
        }
        Field::BinaryAbstract {
            degree,
            representation,
        } => {
            if !(2..=571).contains(degree) {
                return Err("binary inspection degrees must be 2..=571".into());
            }
            if representation.len() > 200 || representation.chars().any(char::is_control) {
                return Err("invalid representation description".into());
            }
            q = BigUint::one() << *degree as usize;
            // Without a coordinate basis only base-field coefficients have an unambiguous meaning.
            let base_field = (a.is_zero() || a.is_one()) && b.is_one();
            check(
                &mut checks,
                "abstract_koblitz_form",
                base_field,
                "abstract profiles require a in {0,1}, b=1",
            );
            if base_field {
                check(
                    &mut checks,
                    "koblitz_group_order",
                    &r * &h == koblitz_order(if a.is_zero() { 0 } else { 1 }, *degree),
                    "exact integer Frobenius trace recurrence",
                );
            }
            check(
                &mut checks,
                "no_ambiguous_coordinates",
                p.generator.is_none() && p.point.is_none() && p.fixture.is_none(),
                "coordinates require an explicit supported field representation",
            );
            skipped(
                &mut checks,
                "field_representation",
                "normal/abstract basis is described but not implemented by this inspector",
            );
            skipped(
                &mut checks,
                "points",
                "generator and target coordinates have not been imported",
            );
        }
        Field::Prime { modulus } => {
            q = number(modulus)?;
            if q.bits() > 512 || q < BigUint::from(5u8) {
                return Err("prime-field modulus must be >=5 and at most 512 bits".into());
            }
            let prime = probable_prime(&q);
            check(
                &mut checks,
                "field_modulus_screen",
                prime,
                "fixed-base Miller-Rabin; not a primality proof",
            );
            let canonical = a < q && b < q;
            check(
                &mut checks,
                "canonical_coefficients",
                canonical,
                "coefficients must lie in [0,p)",
            );
            let nonsingular = (BigUint::from(4u8) * a.modpow(&BigUint::from(3u8), &q)
                + BigUint::from(27u8) * &b * &b)
                % &q
                != BigUint::zero();
            check(
                &mut checks,
                "nonsingular_curve",
                nonsingular,
                "4*a^3 + 27*b^2 != 0 mod p",
            );
            if prime && canonical && nonsingular && r_prime {
                let af = FieldElement::new(a.clone(), q.clone());
                let mut parsed = Vec::new();
                for (label, coords) in [("generator", &p.generator), ("point", &p.point)] {
                    if let Some(c) = coords {
                        let x = number(&c.x)?;
                        let y = number(&c.y)?;
                        if x >= q || y >= q {
                            check(&mut checks, label, false, "noncanonical point coordinate");
                            parsed.push(None);
                            continue;
                        }
                        let on = (&y * &y) % &q
                            == (x.modpow(&BigUint::from(3u8), &q) + &a * &x + &b) % &q;
                        check(
                            &mut checks,
                            &format!("{label}_on_curve"),
                            on,
                            "direct curve-equation check",
                        );
                        let pt = Point::Affine {
                            x: FieldElement::new(x, q.clone()),
                            y: FieldElement::new(y, q.clone()),
                        };
                        if on {
                            check(&mut checks,&format!("{label}_subgroup"),pt.scalar_mul(&r,&af)==Point::Infinity,"[r]P = O; exact-order interpretation remains conditional on primality");
                        }
                        parsed.push(if on { Some(pt) } else { None });
                    } else {
                        skipped(&mut checks, label, "coordinates not supplied");
                        parsed.push(None);
                    }
                }
                if let Some(f) = &p.fixture {
                    let k = number(&f.known_log)?;
                    if let (Some(g), Some(t)) = (&parsed[0], &parsed[1]) {
                        check(
                            &mut checks,
                            "known_answer",
                            !k.is_zero() && k < r && g.scalar_mul(&k, &af) == *t,
                            "generated fixture identity [known_log]G = point",
                        );
                    } else {
                        skipped(
                            &mut checks,
                            "known_answer",
                            "both valid generator and point are required",
                        );
                    }
                }
                points_checked = p.generator.is_some() || p.point.is_some();
            } else {
                skipped(
                    &mut checks,
                    "points",
                    "field, curve, or subgroup-order checks failed",
                );
            }
            skipped(
                &mut checks,
                "group_cardinality",
                "general prime-curve point counting is not implemented",
            );
        }
    }
    let declared = &r * &h;
    let center = &q + 1u8;
    let difference = if declared >= center {
        &declared - &center
    } else {
        &center - &declared
    };
    check(
        &mut checks,
        "hasse_necessary_bound",
        &difference * &difference <= (&q << 2usize),
        "necessary cardinality bound only; not a point-count certificate",
    );
    let valid = !checks.iter().any(|v| v["status"] == "fail");
    Ok(
        json!({"schema_version":1,"operation":"inspect","status":if valid{"checks_passed"}else{"invalid"},
        "evidence_scope":"parameter_validation_only","source":source,"parameters":p,"checks":checks,
        "capabilities":{"parameter_inspection":true,"point_checks_attempted":points_checked,
            "imported_target_solving":false,"factor_base_built":false,"relation_collection":false,"linear_algebra":false},
        "limitations":["Primality screens are not proofs.","Missing or unsupported checks are explicitly listed.","Imported parameters are never passed to the synthetic solver."]}),
    )
}
