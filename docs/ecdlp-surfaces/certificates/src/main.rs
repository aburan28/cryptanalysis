use ecdlp_surfaces::curve::{Curve, Point};
use serde_json::{json, Value};
use std::collections::BTreeMap;
use std::path::PathBuf;
use surface_evidence::hash::sha256::sha256;
use surface_evidence::identity_certificate::{
    check_with_extra, issue, Expr, IdentityStatement, Verdict,
};

fn v(name: &str) -> Expr {
    Expr::var(name)
}
fn c(value: i64) -> Expr {
    Expr::Const(value)
}
fn mul(terms: Vec<Expr>) -> Expr {
    Expr::product(terms)
}
fn add(terms: Vec<Expr>) -> Expr {
    Expr::sum(terms)
}
fn neg(expr: Expr) -> Expr {
    Expr::minus(expr)
}

fn embedding_statement() -> IdentityStatement {
    let x2 = || mul(vec![v("x"), v("x")]);
    IdentityStatement {
        name: "Quartic embedding substitutes into the quadric pencil".into(),
        source: "tools/ecdlp-surfaces/src/curve.rs: encode and quadric_values".into(),
        variables: vec!["x", "y", "a", "b", "lambda"]
            .into_iter()
            .map(String::from)
            .collect(),
        degree_bound: 4,
        lhs: add(vec![
            mul(vec![v("y"), v("y")]),
            neg(mul(vec![v("x"), x2()])),
            neg(mul(vec![v("a"), v("x")])),
            neg(v("b")),
            mul(vec![v("lambda"), add(vec![x2(), neg(x2())])]),
        ]),
        rhs: add(vec![
            mul(vec![v("y"), v("y")]),
            neg(mul(vec![v("x"), v("x"), v("x")])),
            neg(mul(vec![v("a"), v("x")])),
            neg(v("b")),
        ]),
    }
}

fn determinant_statement() -> IdentityStatement {
    // Twice the symmetric matrix, so no rational constants are needed.
    let matrix = [
        [mul(vec![c(-2), v("b")]), neg(v("a")), c(0), v("lambda")],
        [neg(v("a")), mul(vec![c(-2), v("lambda")]), c(0), c(-1)],
        [c(0), c(0), c(2), c(0)],
        [v("lambda"), c(-1), c(0), c(0)],
    ];
    let mut terms = Vec::new();
    for i in 0..4 {
        for j in 0..4 {
            for k in 0..4 {
                for l in 0..4 {
                    let permutation = [i, j, k, l];
                    if (0..4).any(|a| (a + 1..4).any(|b| permutation[a] == permutation[b])) {
                        continue;
                    }
                    let inversions = (0..4)
                        .map(|a| {
                            (a + 1..4)
                                .filter(|&b| permutation[a] > permutation[b])
                                .count()
                        })
                        .sum::<usize>();
                    let term = mul((0..4)
                        .map(|row| matrix[row][permutation[row]].clone())
                        .collect());
                    terms.push(if inversions % 2 == 0 { term } else { neg(term) });
                }
            }
        }
    }
    IdentityStatement {
        name: "Determinant of twice the quadric-pencil matrix".into(),
        source: "tools/ecdlp-surfaces/src/curve.rs: quadric; det(2M)=16 det(M)".into(),
        variables: vec!["a".into(), "b".into(), "lambda".into()],
        degree_bound: 4,
        lhs: add(terms),
        rhs: mul(vec![
            c(4),
            add(vec![
                mul(vec![v("lambda"), v("lambda"), v("lambda")]),
                mul(vec![v("a"), v("lambda")]),
                v("b"),
            ]),
        ]),
    }
}

// Independent exact coefficient comparison over Z, separate from the
// upstream certificate evaluator's finite-field point checks.
type Polynomial = BTreeMap<Vec<u32>, i128>;
fn expand(expr: &Expr, variables: &[String]) -> Polynomial {
    let zero = vec![0; variables.len()];
    match expr {
        Expr::Const(value) => BTreeMap::from([(zero, i128::from(*value))]),
        Expr::Var(name) => {
            let mut exponents = zero;
            exponents[variables.iter().position(|v| v == name).unwrap()] = 1;
            BTreeMap::from([(exponents, 1)])
        }
        Expr::Neg(inner) => expand(inner, variables)
            .into_iter()
            .map(|(powers, coefficient)| (powers, -coefficient))
            .collect(),
        Expr::Add(terms) => {
            let mut sum = BTreeMap::new();
            for term in terms {
                for (powers, coefficient) in expand(term, variables) {
                    *sum.entry(powers).or_insert(0) += coefficient;
                }
            }
            sum.retain(|_, coefficient| *coefficient != 0);
            sum
        }
        Expr::Mul(terms) => {
            let mut product = BTreeMap::from([(zero, 1)]);
            for term in terms {
                let factor = expand(term, variables);
                let mut next = BTreeMap::new();
                for (a, ac) in &product {
                    for (b, bc) in &factor {
                        let powers = a.iter().zip(b).map(|(x, y)| x + y).collect();
                        *next.entry(powers).or_insert(0) += ac * bc;
                    }
                }
                next.retain(|_, coefficient| *coefficient != 0);
                product = next;
            }
            product
        }
    }
}

fn digest(value: &Value) -> String {
    // serde_json's default object map is sorted, matching EC1 canonical bytes.
    hex::encode(sha256(&serde_json::to_vec(value).unwrap()))
}
fn save(output: &std::path::Path, name: &str, value: &Value) {
    std::fs::write(
        output.join(name),
        format!("{}\n", serde_json::to_string_pretty(value).unwrap()),
    )
    .unwrap();
}

fn main() {
    let output = PathBuf::from(std::env::args().nth(1).expect("supply an output directory"));
    std::fs::create_dir_all(&output).unwrap();
    let mut receipts = Vec::new();
    for (name, statement) in [
        ("embedding_identity.json", embedding_statement()),
        ("quadric_determinant.json", determinant_statement()),
    ] {
        assert_eq!(
            expand(&statement.lhs, &statement.variables),
            expand(&statement.rhs, &statement.variables)
        );
        let certificate = issue(
            statement,
            20261011,
            32,
            "Issued and replayed on one Linux x86-64 host; shared upstream evaluator plus independent exact integer-coefficient expansion; no second-host replay.",
            None,
        )
        .unwrap();
        let verdict = check_with_extra(&certificate, Some((0x5A17_2026, 32))).unwrap();
        let Verdict::Accept {
            points,
            extra_points,
            false_accept_log2,
        } = verdict
        else {
            panic!("certificate did not replay: {verdict:?}");
        };
        receipts.push(json!({"id":certificate.id,"file":name,"certificate_points":points,"extra_points":extra_points,"integer_coefficients_equal":true,"verdict":"accept","finite_field_false_accept_log2":false_accept_log2}));
        save(&output, name, &serde_json::to_value(certificate).unwrap());
    }
    save(
        &output,
        "identity_replay.json",
        &json!({"identities":receipts,"formal_proof":false}),
    );

    let curve = Curve::new(101, 1, 46).unwrap();
    let subgroup = curve.select_subgroup().unwrap();
    assert_eq!(subgroup.curve_order, 109);
    assert_eq!(subgroup.order, 109);
    assert_eq!(subgroup.generator, Point::Affine(2, 37));
    let field = json!({"characteristic":101,"degree":1,"representation":"prime","element_encoding":"hex integer modulo the characteristic"});
    let model = json!({"model":"short Weierstrass","coefficients":[0,0,0,1,46],"subgroup_order":"109","cofactor":1,"generator":["0x2","0x25"],"target_group":"prime-order subgroup"});
    let fingerprint = digest(&json!({"field":field,"curve":model}));
    save(
        &output,
        "curve_record.json",
        &json!({
            "field":field,"curve":model,"curve_id":format!("EC1P7Cfph{}",&fingerprint[..12]),
            "curve_uid":format!("urn:ec-record:1:sha256:{fingerprint}"),
            "field_sha256":digest(&field),"curve_order":109,"trace":-7,
            "purpose":"public known-answer arithmetic fixture; no IC candidate or isogeny route"
        }),
    );
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn portable_hash_matches_standard_vectors() {
        assert_eq!(
            hex::encode(sha256(b"")),
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        );
        assert_eq!(
            hex::encode(sha256(b"abc")),
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        );
        assert_eq!(
            hex::encode(sha256(
                b"abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq"
            )),
            "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1"
        );
    }

    #[test]
    fn integer_expansion_matches_and_detects_a_false_identity() {
        for statement in [embedding_statement(), determinant_statement()] {
            assert_eq!(
                expand(&statement.lhs, &statement.variables),
                expand(&statement.rhs, &statement.variables)
            );
            let mut false_statement = statement.clone();
            false_statement.rhs = Expr::plus(false_statement.rhs, Expr::Const(1));
            assert_ne!(
                expand(&false_statement.lhs, &false_statement.variables),
                expand(&false_statement.rhs, &false_statement.variables)
            );
            assert!(issue(false_statement, 20261011, 32, "negative control", None).is_err());
        }
    }

    #[test]
    fn changed_certificate_digest_is_rejected() {
        let mut certificate = issue(determinant_statement(), 20261011, 32, "test", None).unwrap();
        certificate.value_digest = "0".repeat(64);
        assert!(matches!(
            check_with_extra(&certificate, Some((7, 8))).unwrap(),
            Verdict::DigestMismatch { .. }
        ));
    }
}
