use num_bigint::{BigInt, BigUint, Sign};
use num_traits::{One, ToPrimitive, Zero};

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Point {
    Infinity,
    Affine { x: BigUint, y: BigUint },
}

pub struct Curve<'a> {
    pub p: &'a BigUint,
    pub a: &'a BigUint,
    pub b: &'a BigUint,
}

pub fn gcd(mut a: BigUint, mut b: BigUint) -> BigUint {
    while !b.is_zero() {
        let next = &a % &b;
        a = b;
        b = next;
    }
    a
}

fn sub_mod(a: &BigUint, b: &BigUint, p: &BigUint) -> BigUint {
    if a >= b {
        (a - b) % p
    } else {
        let d = (b - a) % p;
        if d.is_zero() {
            BigUint::zero()
        } else {
            p - d
        }
    }
}

fn inverse_mod(a: &BigUint, p: &BigUint) -> Option<BigUint> {
    let mut old_r = BigInt::from(p.clone());
    let mut r = BigInt::from(a.clone());
    let mut old_t = BigInt::zero();
    let mut t = BigInt::one();
    while !r.is_zero() {
        let q = &old_r / &r;
        (old_r, r) = (r.clone(), &old_r - &q * &r);
        (old_t, t) = (t.clone(), &old_t - q * &t);
    }
    if old_r != BigInt::one() {
        return None;
    }
    let modulus = BigInt::from(p.clone());
    let mut value = old_t % &modulus;
    if value.sign() == Sign::Minus {
        value += modulus;
    }
    value.to_biguint()
}

impl Curve<'_> {
    pub fn discriminant_factor(&self) -> BigUint {
        ((BigUint::from(4u32) * self.a.modpow(&BigUint::from(3u32), self.p))
            + (BigUint::from(27u32) * self.b.modpow(&BigUint::from(2u32), self.p)))
            % self.p
    }

    pub fn contains(&self, point: &Point) -> bool {
        match point {
            Point::Infinity => true,
            Point::Affine { x, y } => {
                if x >= self.p || y >= self.p {
                    return false;
                }
                let lhs = y.modpow(&BigUint::from(2u32), self.p);
                let rhs = ((x.modpow(&BigUint::from(3u32), self.p) + self.a * x) + self.b) % self.p;
                lhs == rhs
            }
        }
    }

    pub fn add(&self, left: &Point, right: &Point) -> Result<Point, &'static str> {
        match (left, right) {
            (Point::Infinity, _) => Ok(right.clone()),
            (_, Point::Infinity) => Ok(left.clone()),
            (Point::Affine { x: x1, y: y1 }, Point::Affine { x: x2, y: y2 }) => {
                let (numerator, denominator) = if x1 == x2 {
                    if (y1 + y2) % self.p == BigUint::zero() {
                        return Ok(Point::Infinity);
                    }
                    (
                        (BigUint::from(3u32) * x1 * x1 + self.a) % self.p,
                        (BigUint::from(2u32) * y1) % self.p,
                    )
                } else {
                    (sub_mod(y2, y1, self.p), sub_mod(x2, x1, self.p))
                };
                let inv = inverse_mod(&denominator, self.p)
                    .ok_or("noninvertible point-addition denominator")?;
                let slope = numerator * inv % self.p;
                let x3 = sub_mod(
                    &sub_mod(&(&slope * &slope % self.p), x1, self.p),
                    x2,
                    self.p,
                );
                let y3 = sub_mod(&(&slope * sub_mod(x1, &x3, self.p) % self.p), y1, self.p);
                Ok(Point::Affine { x: x3, y: y3 })
            }
        }
    }

    pub fn mul(&self, point: &Point, scalar: &BigUint) -> Result<Point, &'static str> {
        let mut k = scalar.clone();
        let mut result = Point::Infinity;
        let mut base = point.clone();
        while !k.is_zero() {
            if (&k & BigUint::one()) == BigUint::one() {
                result = self.add(&result, &base)?;
            }
            k >>= 1;
            if !k.is_zero() {
                base = self.add(&base, &base)?;
            }
        }
        Ok(result)
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Primality {
    ProvenPrime,
    ProvenComposite,
    ProbablePrime,
}

pub fn primality(n: &BigUint) -> Primality {
    let two = BigUint::from(2u32);
    if n < &two {
        return Primality::ProvenComposite;
    }
    if let Some(small) = n.to_u64() {
        if small <= 1_000_000_000_000 {
            if small % 2 == 0 {
                return if small == 2 {
                    Primality::ProvenPrime
                } else {
                    Primality::ProvenComposite
                };
            }
            let mut d = 3u64;
            while d <= small / d {
                if small % d == 0 {
                    return Primality::ProvenComposite;
                }
                d += 2;
            }
            return Primality::ProvenPrime;
        }
    }
    for base in [2u64, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37] {
        let b = BigUint::from(base);
        if n == &b {
            return Primality::ProvenPrime;
        }
        if n % &b == BigUint::zero() {
            return Primality::ProvenComposite;
        }
    }
    let one = BigUint::one();
    let n_minus_one = n - &one;
    let mut d = n_minus_one.clone();
    let mut s = 0u32;
    while (&d & &one).is_zero() {
        d >>= 1;
        s += 1;
    }
    for base in [2u64, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37] {
        let mut x = BigUint::from(base).modpow(&d, n);
        if x == one || x == n_minus_one {
            continue;
        }
        let mut passed = false;
        for _ in 1..s {
            x = (&x * &x) % n;
            if x == n_minus_one {
                passed = true;
                break;
            }
        }
        if !passed {
            return Primality::ProvenComposite;
        }
    }
    Primality::ProbablePrime
}

pub fn small_factorization(n: &BigUint, trial_limit: u64) -> (Vec<(BigUint, u32)>, BigUint, bool) {
    let mut remainder = n.clone();
    let mut factors = Vec::new();
    for d in 2..=trial_limit {
        let divisor = BigUint::from(d);
        if &divisor * &divisor > remainder {
            break;
        }
        let mut exponent = 0u32;
        while &remainder % &divisor == BigUint::zero() {
            remainder /= &divisor;
            exponent += 1;
        }
        if exponent > 0 {
            factors.push((divisor, exponent));
        }
    }
    if remainder > BigUint::one() && primality(&remainder) == Primality::ProvenPrime {
        factors.push((remainder.clone(), 1));
        remainder = BigUint::one();
    }
    let complete = remainder == BigUint::one();
    (factors, remainder, complete)
}

pub fn embedding_degree(q: &BigUint, r: &BigUint, max_k: u32) -> Option<u32> {
    if r <= &BigUint::one() || gcd(q.clone(), r.clone()) != BigUint::one() {
        return None;
    }
    let residue = q % r;
    let mut power = BigUint::one();
    for k in 1..=max_k {
        power = (power * &residue) % r;
        if power.is_one() {
            return Some(k);
        }
    }
    None
}

fn pow_mod_u64(mut base: u64, mut exponent: u64, modulus: u64) -> u64 {
    let mut result = 1u64;
    base %= modulus;
    while exponent > 0 {
        if exponent & 1 == 1 {
            result = ((result as u128 * base as u128) % modulus as u128) as u64;
        }
        base = ((base as u128 * base as u128) % modulus as u128) as u64;
        exponent >>= 1;
    }
    result
}

pub fn count_points(p: u64, a: u64, b: u64) -> u64 {
    let mut count = 1u64;
    for x in 0..p {
        let rhs = ((x as u128 * x as u128 * x as u128 + a as u128 * x as u128 + b as u128)
            % p as u128) as u64;
        if rhs == 0 {
            count += 1;
        } else if pow_mod_u64(rhs, (p - 1) / 2, p) == 1 {
            count += 2;
        }
    }
    count
}
