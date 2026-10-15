//! Integer-lift IDC1 certificate and exact expansion for the binary map.
use serde_json::json;
use surface_evidence::{
    exact_polynomial::expand,
    identity_certificate::{check_with_extra, issue, Expr, IdentityStatement, Verdict},
};

fn v(s: &str) -> Expr {
    Expr::var(s)
}
fn add(xs: Vec<Expr>) -> Expr {
    Expr::sum(xs)
}
fn mul(xs: Vec<Expr>) -> Expr {
    Expr::product(xs)
}
fn pow(x: Expr, n: usize) -> Expr {
    mul(vec![x; n])
}

fn statement() -> Result<IdentityStatement, String> {
    let t = add(vec![v("u"), Expr::Const(1)]);
    let b = add(vec![
        mul(vec![v("u"), t.clone(), v("v")]),
        pow(v("u"), 2),
        v("u"),
        Expr::Const(1),
    ]);
    let lhs = add(vec![
        pow(b.clone(), 2),
        mul(vec![pow(v("u"), 3), t.clone(), b]),
        pow(v("u"), 9),
        mul(vec![v("a"), pow(v("u"), 6), pow(t.clone(), 2)]),
        pow(t.clone(), 6),
    ]);
    let factor = mul(vec![pow(v("u"), 2), pow(t, 2)]);
    let source = add(vec![
        pow(v("v"), 2),
        mul(vec![pow(v("u"), 2), v("v")]),
        pow(v("u"), 5),
        mul(vec![v("a"), pow(v("u"), 4)]),
        pow(v("u"), 3),
        v("u"),
    ]);
    let base_rhs = mul(vec![factor, source]);
    let variables = vec!["u".to_owned(), "v".to_owned(), "a".to_owned()];
    let difference = expand(
        &add(vec![lhs.clone(), Expr::minus(base_rhs.clone())]),
        &variables,
    );
    let mut correction = Vec::new();
    for (powers, coefficient) in difference {
        if coefficient % 2 != 0 {
            return Err("integer lift has an odd residual coefficient".into());
        }
        let coefficient = i64::try_from(coefficient / 2).map_err(|e| e.to_string())?;
        let mut term = vec![Expr::Const(coefficient)];
        for (variable, exponent) in variables.iter().zip(powers) {
            term.extend(vec![v(variable); exponent as usize]);
        }
        correction.push(mul(term));
    }
    Ok(IdentityStatement {
        name: "Genus-two binary degree-three map: integer lift with even correction".into(),
        source:
            "tools/binary-genus2-cover/src/lib.rs; reduce the exact integer identity modulo two"
                .into(),
        variables,
        degree_bound: 9,
        lhs,
        rhs: add(vec![base_rhs, mul(vec![Expr::Const(2), add(correction)])]),
    })
}

fn run() -> Result<(), String> {
    let mut args = std::env::args().skip(1);
    let directory = args
        .next()
        .ok_or("usage: genus2_identity FRESH_OUTPUT_DIRECTORY")?;
    if args.next().is_some() {
        return Err("expected exactly one output directory".into());
    }
    let dir = std::path::Path::new(&directory);
    std::fs::create_dir(dir).map_err(|e| e.to_string())?;
    let s = statement()?;
    if expand(&s.lhs, &s.variables) != expand(&s.rhs, &s.variables) {
        return Err("exact integer polynomial expansions differ".into());
    }
    let cert = issue(s.clone(),0x20261014,32,
        "Same host: native exact coefficient expansion and IDC1 evaluator with a distinct checker seed; no independent-host claim",None)
        .map_err(|e|e.to_string())?;
    let verdict = check_with_extra(&cert, Some((0x83c2, 32))).map_err(|e| e.to_string())?;
    if !matches!(verdict, Verdict::Accept { .. }) {
        return Err(format!("certificate rejected: {verdict:?}"));
    }
    let mut false_statement = s;
    false_statement.rhs = add(vec![false_statement.rhs, Expr::Const(1)]);
    if issue(false_statement, 17, 32, "negative control", None).is_ok() {
        return Err("false identity was accepted".into());
    }
    let mut tampered = cert.clone();
    tampered.value_digest = "0".repeat(64);
    if matches!(
        check_with_extra(&tampered, Some((0x83c2, 32))),
        Ok(Verdict::Accept { .. })
    ) {
        return Err("tampered digest was accepted".into());
    }
    let write = |name: &str, value: &serde_json::Value| -> Result<(), String> {
        std::fs::write(
            dir.join(name),
            serde_json::to_string_pretty(value).map_err(|e| e.to_string())? + "\n",
        )
        .map_err(|e| e.to_string())
    };
    write(
        "map_identity.json",
        &serde_json::to_value(&cert).map_err(|e| e.to_string())?,
    )?;
    write(
        "replay.json",
        &json!({"id":cert.id,"exact_integer_expansion_equal":true,
        "characteristic_two_bridge":"rhs equals the cleared source equation plus twice an integer polynomial",
        "certificate_points":32,"extra_checker_points":32,"distinct_checker_seed":"0x83c2",
        "false_identity_rejected":true,"tampered_digest_rejected":true,"formal_proof_pointer":null,
        "scope":"polynomial identity, not a genus or Picard-functor proof"}),
    )?;
    println!(
        "{}: exact integer expansion and 64 IDC1 points verified",
        cert.id
    );
    Ok(())
}

fn main() {
    if let Err(e) = run() {
        eprintln!("error: {e}");
        std::process::exit(2);
    }
}
