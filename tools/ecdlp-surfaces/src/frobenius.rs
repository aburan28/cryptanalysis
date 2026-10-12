use crate::Result;

#[derive(Clone, Copy, Debug)]
pub struct Filter {
    pub q: u64,
    pub source_trace: i128,
    pub coefficients: [i128; 4],
    pub quotient: [i128; 3],
    pub remainder: [i128; 2],
    pub divides: bool,
    pub reciprocal: bool,
    pub quotient_elliptic_shape: bool,
    pub quotient_hasse_bound: bool,
}

impl Filter {
    pub fn passes_necessary_conditions(&self) -> bool {
        self.divides && self.reciprocal && self.quotient_elliptic_shape && self.quotient_hasse_bound
    }
}

fn plus(a: i128, b: i128) -> Result<i128> {
    a.checked_add(b)
        .ok_or_else(|| "Polynomial arithmetic exceeds i128.".into())
}
fn minus(a: i128, b: i128) -> Result<i128> {
    a.checked_sub(b)
        .ok_or_else(|| "Polynomial arithmetic exceeds i128.".into())
}
fn times(a: i128, b: i128) -> Result<i128> {
    a.checked_mul(b)
        .ok_or_else(|| "Polynomial arithmetic exceeds i128.".into())
}

/// Filter T^4+c1*T^3+c2*T^2+c3*T+c4 by T^2-trace*T+q.
/// Inputs are supplied field sizes and polynomials, not constructed varieties.
/// Passing does not construct a homomorphism or certify its action on a subgroup.
pub fn filter(q: u64, trace: i128, coefficients: [i128; 4]) -> Result<Filter> {
    if q < 2 || q > i64::MAX as u64 {
        return Err("q must be between 2 and i64::MAX.".into());
    }
    let qi = i128::from(q);
    let hasse = times(4, qi)?;
    if times(trace, trace)? > hasse {
        return Err("The source trace violates the elliptic Hasse bound.".into());
    }
    let [c1, c2, c3, c4] = coefficients;
    let u = plus(c1, trace)?;
    let v = minus(plus(c2, times(trace, u)?)?, qi)?;
    let r1 = minus(plus(c3, times(trace, v)?)?, times(qi, u)?)?;
    let r0 = minus(c4, times(qi, v)?)?;
    let square_u = u.checked_mul(u);
    Ok(Filter {
        q,
        source_trace: trace,
        coefficients,
        quotient: [1, u, v],
        remainder: [r1, r0],
        divides: r1 == 0 && r0 == 0,
        reciprocal: c3 == times(qi, c1)? && c4 == times(qi, qi)?,
        quotient_elliptic_shape: v == qi,
        quotient_hasse_bound: square_u.map(|square| square <= hasse).unwrap_or(false),
    })
}
