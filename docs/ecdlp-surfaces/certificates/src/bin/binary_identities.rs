//! Integer lifts for characteristic-two identities; v1 itself evaluates over
//! 2^61-1. Reduction modulo 2 is explicit, including the normal-form correction.
use ecdlp_surfaces::binary::{n83_fixture, BinaryPoint, FIXTURE_SOURCE, PRIME_RECEIPT_SOURCE};
use serde_json::{json, Value};
use std::path::Path;
use surface_evidence::{
    exact_polynomial::expand,
    hash::sha256::sha256,
    identity_certificate::{check_with_extra, issue, Expr, IdentityStatement, Verdict},
};

fn v(name: &str) -> Expr {
    Expr::var(name)
}
fn c(value: i64) -> Expr {
    Expr::Const(value)
}
fn add(terms: Vec<Expr>) -> Expr {
    Expr::sum(terms)
}
fn mul(terms: Vec<Expr>) -> Expr {
    Expr::product(terms)
}
fn neg(value: Expr) -> Expr {
    Expr::minus(value)
}
fn square(value: Expr) -> Expr {
    mul(vec![value.clone(), value])
}

fn statement(
    name: &str,
    variables: &[&str],
    degree_bound: u32,
    lhs: Expr,
    rhs: Expr,
) -> IdentityStatement {
    IdentityStatement {
        name: name.into(),
        source:
            "tools/ecdlp-surfaces/src/binary.rs; signed integer lift followed by reduction modulo 2"
                .into(),
        variables: variables.iter().map(|s| (*s).to_owned()).collect(),
        degree_bound,
        lhs,
        rhs,
    }
}

fn embedding() -> IdentityStatement {
    let plane = || {
        add(vec![
            square(v("y")),
            mul(vec![v("x"), v("y")]),
            neg(mul(vec![v("x"), square(v("x"))])),
            neg(mul(vec![v("a"), square(v("x"))])),
            neg(v("b")),
        ])
    };
    statement(
        "Binary quartic embedding: exact integer lift",
        &["x", "y", "a", "b", "lambda"],
        4,
        add(vec![
            plane(),
            mul(vec![
                v("lambda"),
                add(vec![square(v("x")), neg(square(v("x")))]),
            ]),
        ]),
        plane(),
    )
}

fn polar_determinant() -> IdentityStatement {
    let matrix = [
        [c(0), c(0), c(0), v("c")],
        [c(0), c(0), c(1), c(-1)],
        [c(0), c(-1), c(0), c(0)],
        [neg(v("c")), c(1), c(0), c(0)],
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
    statement(
        "Determinant of the alternating lift of the binary polar matrix",
        &["c"],
        4,
        add(terms),
        square(v("c")),
    )
}

fn normal_form() -> IdentityStatement {
    let c2 = || square(v("c"));
    let lhs = add(vec![
        mul(vec![c2(), square(v("t"))]),
        mul(vec![c2(), v("s"), v("t")]),
        neg(mul(vec![v("c"), v("s"), v("v")])),
        mul(vec![c2(), v("u"), v("v")]),
        mul(vec![v("c"), v("s"), v("v")]),
        neg(mul(vec![v("lambda"), c2(), square(v("s"))])),
        neg(mul(vec![
            v("b"),
            square(add(vec![mul(vec![v("c"), v("u")]), v("s")])),
        ])),
    ]);
    let rhs = add(vec![
        mul(vec![
            c2(),
            add(vec![
                square(v("t")),
                mul(vec![v("s"), v("t")]),
                mul(vec![v("u"), v("v")]),
                neg(mul(vec![v("b"), square(v("u"))])),
                neg(mul(vec![v("lambda"), square(v("s"))])),
            ]),
        ]),
        neg(mul(vec![v("b"), square(v("s"))])),
        neg(mul(vec![c(2), v("b"), v("c"), v("u"), v("s")])),
    ]);
    statement(
        "Cleared-denominator binary normal form with the integer 2bcus correction",
        &["b", "c", "u", "v", "s", "t", "lambda"],
        5,
        lhs,
        rhs,
    )
}

fn counting_substitution() -> IdentityStatement {
    statement(
        "Binary point-count substitution y=xv: exact integer lift",
        &["x", "v", "a", "b"],
        4,
        add(vec![
            mul(vec![square(v("x")), square(v("v"))]),
            mul(vec![square(v("x")), v("v")]),
            neg(mul(vec![square(v("x")), v("x")])),
            neg(mul(vec![v("a"), square(v("x"))])),
            neg(v("b")),
        ]),
        add(vec![
            mul(vec![
                square(v("x")),
                add(vec![square(v("v")), v("v"), neg(v("x")), neg(v("a"))]),
            ]),
            neg(v("b")),
        ]),
    )
}

fn frobenius_difference() -> IdentityStatement {
    let source = || {
        add(vec![
            square(v("T")),
            neg(mul(vec![v("ts"), v("T")])),
            v("q"),
        ])
    };
    let target = || {
        add(vec![
            square(v("T")),
            neg(mul(vec![v("tt"), v("T")])),
            v("q"),
        ])
    };
    let mut identity = statement(
        "Difference of same-q Frobenius quadratics",
        &["T", "ts", "tt", "q"],
        2,
        add(vec![source(), neg(target())]),
        mul(vec![add(vec![v("tt"), neg(v("ts"))]), v("T")]),
    );
    identity.source = "tools/ecdlp-surfaces/src/binary.rs: opposite-product obstruction; Frobenius polynomial identity over integers, with no reduction modulo 2".into();
    identity
}

fn frobenius_product() -> IdentityStatement {
    let source = add(vec![
        square(v("T")),
        neg(mul(vec![v("ts"), v("T")])),
        v("q"),
    ]);
    let target = add(vec![
        square(v("T")),
        neg(mul(vec![v("tt"), v("T")])),
        v("q"),
    ]);
    let sum_trace = || add(vec![v("ts"), v("tt")]);
    let mut identity = statement(
        "Product of same-q Frobenius quadratics",
        &["T", "ts", "tt", "q"],
        4,
        mul(vec![source, target]),
        add(vec![
            square(square(v("T"))),
            neg(mul(vec![sum_trace(), v("T"), square(v("T"))])),
            mul(vec![
                add(vec![mul(vec![v("ts"), v("tt")]), mul(vec![c(2), v("q")])]),
                square(v("T")),
            ]),
            neg(mul(vec![sum_trace(), v("q"), v("T")])),
            square(v("q")),
        ]),
    );
    identity.source = "tools/ecdlp-surfaces/src/binary.rs: same and mixed abelian products; Frobenius polynomial identity over integers, with no reduction modulo 2".into();
    identity
}

fn statements() -> Vec<(&'static str, IdentityStatement)> {
    vec![
        ("binary_embedding.json", embedding()),
        ("binary_polar_determinant.json", polar_determinant()),
        ("binary_normal_form.json", normal_form()),
        ("binary_counting_substitution.json", counting_substitution()),
        ("frobenius_difference.json", frobenius_difference()),
        ("frobenius_product.json", frobenius_product()),
    ]
}

fn digest(value: &Value) -> String {
    hex::encode(sha256(&serde_json::to_vec(value).unwrap()))
}
fn save(output: &Path, name: &str, value: &Value) {
    std::fs::write(
        output.join(name),
        format!("{}\n", serde_json::to_string_pretty(value).unwrap()),
    )
    .unwrap();
}

fn main() {
    let args: Vec<_> = std::env::args().skip(1).collect();
    assert_eq!(
        args.len(),
        2,
        "supply the n=83 run JSON and a fresh output directory"
    );
    let run: Value = serde_json::from_slice(&std::fs::read(&args[0]).unwrap()).unwrap();
    assert_eq!(run["schema"], "ecdlp.binary-surface-run/v1");
    let output = Path::new(&args[1]);
    std::fs::create_dir_all(output).unwrap();
    let mut receipts = Vec::new();
    for (name, statement) in statements() {
        assert_eq!(
            expand(&statement.lhs, &statement.variables),
            expand(&statement.rhs, &statement.variables)
        );
        let cert = issue(statement,20261012,32,"Exact integer-coefficient expansion and the upstream v1 evaluator, issued and replayed on one Linux host. Integer lifts reduce to characteristic two; no second-host replay or formal proof.",None).unwrap();
        let verdict = check_with_extra(&cert, Some((0xB183_2026, 32))).unwrap();
        let Verdict::Accept {
            points,
            extra_points,
            false_accept_log2,
        } = verdict
        else {
            panic!("binary lift certificate failed: {verdict:?}");
        };
        receipts.push(json!({"id":cert.id,"file":name,"certificate_points":points,"extra_points":extra_points,"integer_coefficients_equal":true,"verdict":"accept","finite_field_false_accept_log2":false_accept_log2}));
        save(output, name, &serde_json::to_value(cert).unwrap());
    }
    save(
        output,
        "identity_replay.json",
        &json!({"identities":receipts,"formal_proof":false,"characteristic_two_reduction":"The four binary lifts reduce signs modulo 2 and the explicit 2bcus correction vanishes. The two Frobenius identities remain over the integers. The v1 random evaluator itself remains over 2^61-1."}),
    );
    for case in run["cases"].as_array().unwrap() {
        let a = u8::try_from(case["source"]["a"].as_u64().unwrap()).unwrap();
        let fixture = n83_fixture(a).unwrap();
        assert_eq!(case["field"]["degree"], 83);
        assert_eq!(case["field"]["polynomial"], "z^83+z^45+z^2+z+1");
        assert_eq!(
            case["source"]["subgroup_order"],
            fixture.subgroup_order.to_string()
        );
        assert_eq!(case["source"]["cofactor"], fixture.cofactor.to_string());
        let (trace, order) = fixture.curve.trace_and_order();
        assert_eq!(case["source"]["trace"], trace.to_string());
        assert_eq!(case["source"]["curve_order"], order.to_string());
        assert_eq!(case["source"]["fixture_source"], FIXTURE_SOURCE);
        assert_eq!(
            case["source"]["primality_receipt_source"],
            PRIME_RECEIPT_SOURCE
        );
        let BinaryPoint::Affine(x, y) = fixture.generator else {
            unreachable!()
        };
        assert_eq!(
            case["source"]["P"],
            json!([format!("0x{x:x}"), format!("0x{y:x}")])
        );
        let field = json!({"characteristic":2,"degree":83,"representation":"polynomial basis","irreducible_polynomial_exponents":[83,45,2,1,0],"element_encoding":"hex coefficient mask; constant coefficient is the least significant bit"});
        let curve = json!({"model":"binary Weierstrass","coefficients":["0x1",format!("0x{a:x}"),"0x0","0x0","0x1"],"subgroup_order":fixture.subgroup_order.to_string(),"cofactor":fixture.cofactor.to_string(),"generator":case["source"]["P"],"target_group":"prime-order subgroup"});
        let fingerprint = digest(&json!({"field":field,"curve":curve}));
        save(
            output,
            &format!("curve_record_a{a}.json"),
            &json!({"field":field,"curve":curve,"curve_id":format!("EC1N83Ckb{a}h{}",&fingerprint[..12]),"curve_uid":format!("urn:ec-record:1:sha256:{fingerprint}"),"field_sha256":digest(&field),"curve_order":case["source"]["curve_order"],"trace":case["source"]["trace"],"fixture_source":case["source"]["fixture_source"],"primality_receipt_source":case["source"]["primality_receipt_source"],"purpose":"Exact representation record for an existing public fixture; no IC candidate or isogeny-route promotion. Archived differently encoded identifiers are not reused."}),
        );
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn integer_lifts_expand_and_reject_false_statements() {
        for (_, statement) in statements() {
            assert_eq!(
                expand(&statement.lhs, &statement.variables),
                expand(&statement.rhs, &statement.variables)
            );
            let mut false_statement = statement.clone();
            false_statement.rhs = Expr::plus(false_statement.rhs, c(1));
            assert_ne!(
                expand(&false_statement.lhs, &false_statement.variables),
                expand(&false_statement.rhs, &false_statement.variables)
            );
            assert!(issue(false_statement, 20261012, 32, "negative control", None).is_err());
        }
    }

    #[test]
    fn omitting_the_mod_two_correction_is_not_an_integer_identity() {
        let mut wrong = normal_form();
        let Expr::Add(ref mut terms) = wrong.rhs else {
            panic!("expected sum");
        };
        terms.pop();
        assert_ne!(
            expand(&wrong.lhs, &wrong.variables),
            expand(&wrong.rhs, &wrong.variables)
        );
        assert!(issue(wrong, 20261012, 32, "wrong characteristic control", None).is_err());
    }
}
