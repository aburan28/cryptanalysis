//! Exact, bounded integer-coefficient expansion, independent of the certificate
//! evaluator's finite-field point checks. Used for the fixed identities here.
use crate::identity_certificate::Expr;
use std::collections::BTreeMap;

pub type Polynomial = BTreeMap<Vec<u32>, i128>;

pub fn expand(expr: &Expr, variables: &[String]) -> Polynomial {
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
