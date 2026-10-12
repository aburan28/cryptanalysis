use crate::Result;

pub const MAX_PRIME: u64 = 10_000;
pub type ProjectivePoint = [u64; 4];

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Point {
    Infinity,
    Affine(u64, u64),
}

#[derive(Clone, Copy, Debug)]
pub struct Curve {
    p: u64,
    a: u64,
    b: u64,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Quadric {
    pub lambda: u64,
    pub determinant: u64,
    pub smooth: bool,
    pub split: bool,
}

#[derive(Clone, Copy, Debug)]
pub struct Subgroup {
    pub curve_order: u64,
    pub order: u64,
    pub generator: Point,
}

#[derive(Clone, Copy, Debug)]
pub struct Certificate {
    pub curve_order: u64,
    pub subgroup_order: u64,
    pub p: Point,
    pub q: Point,
    pub image_p: ProjectivePoint,
    pub image_q: ProjectivePoint,
    pub scalar: Option<u64>,
}

fn add_mod(a: u64, b: u64, p: u64) -> u64 {
    ((u128::from(a) + u128::from(b)) % u128::from(p)) as u64
}

fn sub_mod(a: u64, b: u64, p: u64) -> u64 {
    ((u128::from(a) + u128::from(p) - u128::from(b)) % u128::from(p)) as u64
}

fn mul_mod(a: u64, b: u64, p: u64) -> u64 {
    (u128::from(a) * u128::from(b) % u128::from(p)) as u64
}

fn pow_mod(mut a: u64, mut exponent: u64, p: u64) -> u64 {
    let mut value = 1;
    while exponent != 0 {
        if exponent & 1 != 0 {
            value = mul_mod(value, a, p);
        }
        a = mul_mod(a, a, p);
        exponent >>= 1;
    }
    value
}

pub fn is_prime(n: u64) -> bool {
    if n < 2 {
        return false;
    }
    let mut d = 2;
    while d <= n / d {
        if n % d == 0 {
            return false;
        }
        d += 1;
    }
    true
}

pub fn prime_factors(mut n: u64) -> Vec<u64> {
    let mut factors = Vec::new();
    let mut d = 2;
    while d <= n / d {
        if n % d == 0 {
            factors.push(d);
            while n % d == 0 {
                n /= d;
            }
        }
        d += 1;
    }
    if n > 1 {
        factors.push(n);
    }
    factors
}

impl Curve {
    pub fn new(p: u64, a: i128, b: i128) -> Result<Self> {
        if p > MAX_PRIME {
            return Err(format!(
                "Point enumeration supports primes at most {MAX_PRIME}."
            ));
        }
        if p <= 3 || !is_prime(p) {
            return Err("The characteristic must be a prime greater than three.".into());
        }
        let curve = Self {
            p,
            a: a.rem_euclid(i128::from(p)) as u64,
            b: b.rem_euclid(i128::from(p)) as u64,
        };
        let a3 = mul_mod(mul_mod(curve.a, curve.a, p), curve.a, p);
        let b2 = mul_mod(curve.b, curve.b, p);
        if add_mod(mul_mod(4, a3, p), mul_mod(27, b2, p), p) == 0 {
            return Err("The discriminant vanishes; the source is not an elliptic curve.".into());
        }
        Ok(curve)
    }

    pub fn prime(&self) -> u64 {
        self.p
    }
    pub fn a(&self) -> u64 {
        self.a
    }
    pub fn b(&self) -> u64 {
        self.b
    }

    pub fn rhs(&self, x: u64) -> u64 {
        let x = x % self.p;
        let x3 = mul_mod(mul_mod(x, x, self.p), x, self.p);
        add_mod(
            add_mod(x3, mul_mod(self.a, x, self.p), self.p),
            self.b,
            self.p,
        )
    }

    pub fn contains(&self, point: Point) -> bool {
        match point {
            Point::Infinity => true,
            Point::Affine(x, y) => x < self.p && y < self.p && mul_mod(y, y, self.p) == self.rhs(x),
        }
    }

    pub fn point(&self, x: i128, y: i128) -> Result<Point> {
        let point = Point::Affine(
            x.rem_euclid(i128::from(self.p)) as u64,
            y.rem_euclid(i128::from(self.p)) as u64,
        );
        self.require_point(point)?;
        Ok(point)
    }

    fn require_point(&self, point: Point) -> Result<()> {
        if self.contains(point) {
            Ok(())
        } else {
            Err("The point is not a normalized point on the source curve.".into())
        }
    }

    pub fn points(&self) -> Vec<Point> {
        let mut roots = vec![Vec::new(); self.p as usize];
        for y in 0..self.p {
            roots[mul_mod(y, y, self.p) as usize].push(y);
        }
        let mut points = vec![Point::Infinity];
        for x in 0..self.p {
            for &y in &roots[self.rhs(x) as usize] {
                points.push(Point::Affine(x, y));
            }
        }
        points
    }

    fn inverse(&self, n: u64) -> u64 {
        debug_assert_ne!(n, 0);
        pow_mod(n, self.p - 2, self.p)
    }

    fn add_valid(&self, left: Point, right: Point) -> Point {
        let (x1, y1, x2, y2) = match (left, right) {
            (Point::Infinity, _) => return right,
            (_, Point::Infinity) => return left,
            (Point::Affine(x1, y1), Point::Affine(x2, y2)) => (x1, y1, x2, y2),
        };
        if x1 == x2 && add_mod(y1, y2, self.p) == 0 {
            return Point::Infinity;
        }
        let (numerator, denominator) = if left == right {
            (
                add_mod(mul_mod(3, mul_mod(x1, x1, self.p), self.p), self.a, self.p),
                mul_mod(2, y1, self.p),
            )
        } else {
            (sub_mod(y2, y1, self.p), sub_mod(x2, x1, self.p))
        };
        let slope = mul_mod(numerator, self.inverse(denominator), self.p);
        let x3 = sub_mod(
            sub_mod(mul_mod(slope, slope, self.p), x1, self.p),
            x2,
            self.p,
        );
        let y3 = sub_mod(mul_mod(slope, sub_mod(x1, x3, self.p), self.p), y1, self.p);
        Point::Affine(x3, y3)
    }

    pub fn add(&self, left: Point, right: Point) -> Result<Point> {
        self.require_point(left)?;
        self.require_point(right)?;
        Ok(self.add_valid(left, right))
    }

    pub fn negate(&self, point: Point) -> Result<Point> {
        self.require_point(point)?;
        Ok(match point {
            Point::Infinity => Point::Infinity,
            Point::Affine(x, y) => Point::Affine(x, sub_mod(0, y, self.p)),
        })
    }

    pub fn multiply(&self, mut scalar: u64, mut point: Point) -> Result<Point> {
        self.require_point(point)?;
        let mut result = Point::Infinity;
        while scalar != 0 {
            if scalar & 1 != 0 {
                result = self.add_valid(result, point);
            }
            point = self.add_valid(point, point);
            scalar >>= 1;
        }
        Ok(result)
    }

    pub fn point_order(&self, point: Point, curve_order: u64) -> Result<u64> {
        if curve_order == 0 || curve_order > 2 * self.p + 2 {
            return Err("The supplied curve order is outside the small-field bound.".into());
        }
        if self.multiply(curve_order, point)? != Point::Infinity {
            return Err("The supplied curve order does not annihilate the point.".into());
        }
        let mut order = curve_order;
        for ell in prime_factors(curve_order) {
            while order % ell == 0 && self.multiply(order / ell, point)? == Point::Infinity {
                order /= ell;
            }
        }
        Ok(order)
    }

    pub fn select_subgroup(&self) -> Result<Subgroup> {
        let points = self.points();
        let curve_order = points.len() as u64;
        let order = *prime_factors(curve_order)
            .last()
            .ok_or("The source has no nontrivial prime subgroup.")?;
        for &point in &points[1..] {
            let point_order = self.point_order(point, curve_order)?;
            if point_order % order == 0 {
                return Ok(Subgroup {
                    curve_order,
                    order,
                    generator: self.multiply(point_order / order, point)?,
                });
            }
        }
        Err("Could not select the prime subgroup.".into())
    }

    pub fn encode(&self, point: Point) -> Result<ProjectivePoint> {
        self.require_point(point)?;
        Ok(match point {
            Point::Infinity => [0, 0, 0, 1],
            Point::Affine(x, y) => [1, x, y, mul_mod(x, x, self.p)],
        })
    }

    pub fn quadric_values(&self, coordinates: ProjectivePoint) -> (u64, u64) {
        let [w, x, y, z] = coordinates.map(|c| c % self.p);
        let q1 = sub_mod(mul_mod(w, z, self.p), mul_mod(x, x, self.p), self.p);
        let q2 = sub_mod(
            sub_mod(
                sub_mod(mul_mod(y, y, self.p), mul_mod(x, z, self.p), self.p),
                mul_mod(self.a, mul_mod(w, x, self.p), self.p),
                self.p,
            ),
            mul_mod(self.b, mul_mod(w, w, self.p), self.p),
            self.p,
        );
        (q1, q2)
    }

    pub fn decode(&self, coordinates: ProjectivePoint) -> Result<Point> {
        let normalized = coordinates.map(|c| c % self.p);
        if normalized == [0, 0, 0, 0] {
            return Err("Zero coordinates do not define a projective point.".into());
        }
        if self.quadric_values(normalized) != (0, 0) {
            return Err(
                "The point is not on the embedded elliptic curve; both quadrics must vanish."
                    .into(),
            );
        }
        let [w, x, y, _] = normalized;
        if w == 0 {
            return Ok(Point::Infinity);
        }
        let inv = self.inverse(w);
        self.point(
            i128::from(mul_mod(x, inv, self.p)),
            i128::from(mul_mod(y, inv, self.p)),
        )
    }

    pub fn image_add(
        &self,
        left: ProjectivePoint,
        right: ProjectivePoint,
    ) -> Result<ProjectivePoint> {
        self.encode(self.add(self.decode(left)?, self.decode(right)?)?)
    }

    pub fn image_multiply(&self, scalar: u64, point: ProjectivePoint) -> Result<ProjectivePoint> {
        self.encode(self.multiply(scalar, self.decode(point)?)?)
    }

    pub fn quadric(&self, lambda: u64) -> Quadric {
        let lambda = lambda % self.p;
        let value = self.rhs(lambda);
        Quadric {
            lambda,
            determinant: mul_mod(value, self.inverse(4), self.p),
            smooth: value != 0,
            split: value != 0 && pow_mod(value, (self.p - 1) / 2, self.p) == 1,
        }
    }

    pub fn certify_transfer(
        &self,
        p: Point,
        q: Point,
        r: u64,
        scalar: Option<i128>,
    ) -> Result<Certificate> {
        self.require_point(p)?;
        self.require_point(q)?;
        let curve_order = self.points().len() as u64;
        if r > curve_order || !is_prime(r) || curve_order % r != 0 {
            return Err("r must be a prime divisor of the source group order.".into());
        }
        if p == Point::Infinity || self.multiply(r, p)? != Point::Infinity {
            return Err("P does not have the requested prime order r.".into());
        }
        // r*Q = O alone is insufficient when the rational r-torsion has rank two.
        let mut cursor = Point::Infinity;
        let mut member = false;
        for _ in 0..r {
            member |= cursor == q;
            cursor = self.add_valid(cursor, p);
        }
        if !member {
            return Err("Q is not in the cyclic subgroup generated by P.".into());
        }
        let scalar = scalar.map(|n| n.rem_euclid(i128::from(r)) as u64);
        if let Some(n) = scalar {
            if self.multiply(n, p)? != q {
                return Err("The supplied scalar does not satisfy Q = nP.".into());
            }
        }
        let image_p = self.encode(p)?;
        let image_q = self.encode(q)?;
        if self.decode(image_p)? != p
            || self.decode(image_q)? != q
            || self.image_multiply(r, image_p)? != [0, 0, 0, 1]
        {
            return Err("The image failed its inverse or subgroup-order check.".into());
        }
        Ok(Certificate {
            curve_order,
            subgroup_order: r,
            p,
            q,
            image_p,
            image_q,
            scalar,
        })
    }
}
