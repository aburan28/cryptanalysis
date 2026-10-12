//! Characteristic-two quartic models and the two pinned n=83 Koblitz fixtures.
//!
//! Arithmetic follows SEC 1 v2, sections 2.1.2 and 2.2.2. No field or subgroup
//! enumeration is performed at n=83. The wide fixture's primality proof is the
//! cited, existing Sage receipt; this module does not claim to replay that proof.

use crate::{
    json::{boolean, number, object, text, Json},
    Result,
};
use std::collections::HashSet;

#[derive(Clone, Copy, Debug)]
pub struct BinaryField {
    degree: u32,
    low_terms: u128,
    mask: u128,
}

fn polynomial_gcd(mut a: u128, mut b: u128) -> u128 {
    while b != 0 {
        let mut remainder = a;
        while remainder != 0 && remainder.leading_zeros() <= b.leading_zeros() {
            remainder ^= b << (b.leading_zeros() - remainder.leading_zeros());
        }
        a = b;
        b = remainder;
    }
    a
}

impl BinaryField {
    pub fn degree(self) -> u32 {
        self.degree
    }

    pub fn low_terms(self) -> u128 {
        self.low_terms
    }

    pub fn new(degree: u32, low_terms: u128) -> Result<Self> {
        if !(1..=83).contains(&degree) {
            return Err("Binary arithmetic supports degrees 1 through 83.".into());
        }
        let mask = (1_u128 << degree) - 1;
        if low_terms > mask || low_terms & 1 == 0 {
            return Err("Invalid binary reduction polynomial.".into());
        }
        let field = Self {
            degree,
            low_terms,
            mask,
        };
        let full_polynomial = (1_u128 << degree) | low_terms;
        let x = if degree == 1 { 1 } else { 2 };
        let mut checkpoints = Vec::new();
        let mut remaining = degree;
        let mut divisor = 2;
        while divisor * divisor <= remaining {
            if remaining % divisor == 0 {
                checkpoints.push(degree / divisor);
                while remaining % divisor == 0 {
                    remaining /= divisor;
                }
            }
            divisor += 1;
        }
        if remaining > 1 {
            checkpoints.push(degree / remaining);
        }
        let mut power = x;
        for step in 1..=degree {
            power = field.square(power);
            if checkpoints.contains(&step) && polynomial_gcd(power ^ x, full_polynomial) != 1 {
                return Err("The reduction polynomial is reducible.".into());
            }
        }
        if power != x {
            return Err("The reduction polynomial is reducible.".into());
        }
        Ok(field)
    }

    pub fn size(self) -> u128 {
        self.mask + 1
    }

    /// Inputs are canonical polynomial-basis masks below 2^degree.
    pub fn multiply(self, mut lhs: u128, mut rhs: u128) -> u128 {
        debug_assert!(lhs <= self.mask && rhs <= self.mask);
        let mut result = 0;
        while rhs != 0 {
            if rhs & 1 != 0 {
                result ^= lhs;
            }
            rhs >>= 1;
            let carry = lhs >> (self.degree - 1);
            lhs = (lhs << 1) & self.mask;
            if carry != 0 {
                lhs ^= self.low_terms;
            }
        }
        result
    }

    pub fn square(self, value: u128) -> u128 {
        self.multiply(value, value)
    }

    pub fn power(self, mut value: u128, mut exponent: u128) -> u128 {
        let mut result = 1;
        while exponent != 0 {
            if exponent & 1 != 0 {
                result = self.multiply(result, value);
            }
            exponent >>= 1;
            value = self.square(value);
        }
        result
    }

    pub fn inverse(self, value: u128) -> Option<u128> {
        (value != 0).then(|| self.power(value, self.size() - 2))
    }

    pub fn trace(self, mut value: u128) -> u8 {
        let mut trace = 0;
        for _ in 0..self.degree {
            trace ^= value;
            value = self.square(value);
        }
        assert!(trace <= 1, "irreducible-field trace must belong to GF(2)");
        trace as u8
    }
}

#[derive(Clone, Copy, Debug, Eq, Hash, PartialEq)]
pub enum BinaryPoint {
    Infinity,
    Affine(u128, u128),
}

pub type BinaryProjectivePoint = [u128; 4];

#[derive(Clone, Copy, Debug)]
pub struct BinaryCurve {
    field: BinaryField,
    a: u8,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct BinaryQuadric {
    pub lambda: u128,
    pub smooth: bool,
    pub split: Option<bool>,
    pub arf_trace: Option<u8>,
}

impl BinaryCurve {
    pub fn field(self) -> BinaryField {
        self.field
    }

    pub fn a(self) -> u8 {
        self.a
    }

    pub fn new(field: BinaryField, a: u8) -> Result<Self> {
        if a > 1 {
            return Err("This checker supports the Koblitz coefficients a=0 or 1, b=1.".into());
        }
        Ok(Self { field, a })
    }

    pub fn is_on_curve(self, point: BinaryPoint) -> bool {
        let BinaryPoint::Affine(x, y) = point else {
            return true;
        };
        if x >= self.field.size() || y >= self.field.size() {
            return false;
        }
        let x2 = self.field.square(x);
        let left = self.field.square(y) ^ self.field.multiply(x, y);
        let right = self.field.multiply(x2, x) ^ if self.a == 1 { x2 } else { 0 } ^ 1;
        left == right
    }

    pub fn negate(self, point: BinaryPoint) -> BinaryPoint {
        match point {
            BinaryPoint::Infinity => point,
            BinaryPoint::Affine(x, y) => BinaryPoint::Affine(x, x ^ y),
        }
    }

    fn add_valid(self, p: BinaryPoint, q: BinaryPoint) -> BinaryPoint {
        let (BinaryPoint::Affine(x1, y1), BinaryPoint::Affine(x2, y2)) = (p, q) else {
            return if p == BinaryPoint::Infinity { q } else { p };
        };
        let f = self.field;
        if x1 == x2 {
            if y1 != y2 || x1 == 0 {
                return BinaryPoint::Infinity;
            }
            let slope = x1 ^ f.multiply(y1, f.inverse(x1).unwrap());
            let x3 = f.square(slope) ^ slope ^ u128::from(self.a);
            let y3 = f.square(x1) ^ f.multiply(slope ^ 1, x3);
            return BinaryPoint::Affine(x3, y3);
        }
        let slope = f.multiply(y1 ^ y2, f.inverse(x1 ^ x2).unwrap());
        let x3 = f.square(slope) ^ slope ^ x1 ^ x2 ^ u128::from(self.a);
        let y3 = f.multiply(slope, x1 ^ x3) ^ x3 ^ y1;
        BinaryPoint::Affine(x3, y3)
    }

    pub fn add(self, p: BinaryPoint, q: BinaryPoint) -> Result<BinaryPoint> {
        if !self.is_on_curve(p) || !self.is_on_curve(q) {
            return Err("Point is outside the binary curve.".into());
        }
        Ok(self.add_valid(p, q))
    }

    pub fn multiply(self, mut scalar: u128, mut point: BinaryPoint) -> Result<BinaryPoint> {
        if !self.is_on_curve(point) {
            return Err("Point is outside the binary curve.".into());
        }
        let mut result = BinaryPoint::Infinity;
        while scalar != 0 {
            if scalar & 1 != 0 {
                result = self.add_valid(result, point);
            }
            scalar >>= 1;
            point = self.add_valid(point, point);
        }
        Ok(result)
    }

    pub fn frobenius(self, point: BinaryPoint) -> BinaryPoint {
        match point {
            BinaryPoint::Infinity => point,
            BinaryPoint::Affine(x, y) => {
                BinaryPoint::Affine(self.field.square(x), self.field.square(y))
            }
        }
    }

    pub fn trace_and_order(self) -> (i128, u128) {
        let trace_one = if self.a == 0 { -1_i128 } else { 1_i128 };
        let (mut previous, mut trace) = (2_i128, trace_one);
        for _ in 2..=self.field.degree {
            let next = trace_one * trace - 2 * previous;
            previous = trace;
            trace = next;
        }
        let order = (self.field.size() as i128 + 1 - trace) as u128;
        (trace, order)
    }

    pub fn quadric_values(self, point: BinaryProjectivePoint) -> Result<[u128; 2]> {
        if point.iter().any(|&v| v >= self.field.size()) {
            return Err("Projective coordinates exceed the recorded field.".into());
        }
        let [w, x, y, z] = point;
        let f = self.field;
        let wz = f.multiply(w, z);
        Ok([
            wz ^ f.square(x),
            f.square(y)
                ^ f.multiply(x, y)
                ^ f.multiply(x, z)
                ^ if self.a == 1 { wz } else { 0 }
                ^ f.square(w),
        ])
    }

    pub fn encode(self, point: BinaryPoint) -> Result<BinaryProjectivePoint> {
        if !self.is_on_curve(point) {
            return Err("Point is outside the binary curve.".into());
        }
        Ok(match point {
            BinaryPoint::Infinity => [0, 0, 0, 1],
            BinaryPoint::Affine(x, y) => [1, x, y, self.field.square(x)],
        })
    }

    pub fn decode(self, point: BinaryProjectivePoint) -> Result<BinaryPoint> {
        if point == [0; 4] || self.quadric_values(point)? != [0, 0] {
            return Err("Point is outside the quartic curve image.".into());
        }
        let [w, x, y, _] = point;
        if w == 0 {
            return Ok(BinaryPoint::Infinity);
        }
        let inv_w = self.field.inverse(w).unwrap();
        let decoded =
            BinaryPoint::Affine(self.field.multiply(x, inv_w), self.field.multiply(y, inv_w));
        if !self.is_on_curve(decoded) {
            return Err("Decoded point is outside the binary curve.".into());
        }
        Ok(decoded)
    }

    pub fn image_add(
        self,
        p: BinaryProjectivePoint,
        q: BinaryProjectivePoint,
    ) -> Result<BinaryProjectivePoint> {
        self.encode(self.add(self.decode(p)?, self.decode(q)?)?)
    }

    pub fn image_multiply(
        self,
        scalar: u128,
        point: BinaryProjectivePoint,
    ) -> Result<BinaryProjectivePoint> {
        self.encode(self.multiply(scalar, self.decode(point)?)?)
    }

    pub fn quadric(self, lambda: u128) -> Result<BinaryQuadric> {
        if lambda >= self.field.size() {
            return Err("Pencil parameter exceeds the recorded field.".into());
        }
        let c = lambda ^ u128::from(self.a);
        let Some(inv_c) = self.field.inverse(c) else {
            return Ok(BinaryQuadric {
                lambda,
                smooth: false,
                split: None,
                arf_trace: None,
            });
        };
        let arf_trace = self.field.trace(lambda ^ self.field.square(inv_c));
        Ok(BinaryQuadric {
            lambda,
            smooth: true,
            split: Some(arf_trace == 0),
            arf_trace: Some(arf_trace),
        })
    }

    /// Exact counts from #E = 2 + 2*(number of smooth split finite members).
    pub fn pencil_counts(self) -> (u128, u128, u128) {
        let (_, order) = self.trace_and_order();
        let smooth = self.field.size() - 1;
        let split = (order - 2) / 2;
        (smooth, split, smooth - split)
    }
}

#[derive(Clone, Copy, Debug)]
pub struct BinaryFixture {
    pub curve: BinaryCurve,
    pub generator: BinaryPoint,
    pub subgroup_order: u128,
    pub cofactor: u128,
}

pub const FIXTURE_SOURCE: &str = "https://github.com/aburan28/crypto/blob/8f7f796d694fd41b4db81b25c1aff3632d012c65/src/cryptanalysis/koblitz_index_calculus.rs#L975";
pub const PRIME_RECEIPT_SOURCE: &str = "https://github.com/aburan28/crypto/blob/8f7f796d694fd41b4db81b25c1aff3632d012c65/research/f6_wide_n83_20261004/prime-check.txt";

pub fn n83_fixture(a: u8) -> Result<BinaryFixture> {
    let field = BinaryField::new(83, (1_u128 << 45) | 7)?;
    let curve = BinaryCurve::new(field, a)?;
    let (subgroup_order, cofactor, gx, gy) = match a {
        0 => (
            2_417_851_639_230_796_216_685_689_u128,
            4,
            "477f77103dfad59850800",
            "2fa5e737d542c4e4fd5c3",
        ),
        1 => (
            8_569_786_107_849_059_u128,
            1_128_547_018,
            "68a212cfe19a809fe0598",
            "244a245ea0b17d8cc8297",
        ),
        _ => return Err("Choose the pinned a=0 or a=1 fixture.".into()),
    };
    let generator = BinaryPoint::Affine(
        u128::from_str_radix(gx, 16).unwrap(),
        u128::from_str_radix(gy, 16).unwrap(),
    );
    if curve.trace_and_order().1 != subgroup_order * cofactor
        || !curve.is_on_curve(generator)
        || curve.multiply(subgroup_order, generator)? != BinaryPoint::Infinity
    {
        return Err("Pinned binary fixture failed its order or generator checks.".into());
    }
    Ok(BinaryFixture {
        curve,
        generator,
        subgroup_order,
        cofactor,
    })
}

fn gcd(mut a: u128, mut b: u128) -> u128 {
    while b != 0 {
        (a, b) = (b, a % b);
    }
    a
}

/// Deterministic Miller-Rabin on u64 using the established seven-base set.
pub fn is_prime_u64(n: u64) -> bool {
    if n < 2 {
        return false;
    }
    for prime in [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37] {
        if n % prime == 0 {
            return n == prime;
        }
    }
    let s = (n - 1).trailing_zeros();
    let d = (n - 1) >> s;
    for base in [2_u64, 325, 9375, 28178, 450775, 9780504, 1795265022] {
        let mut value = 1_u64;
        let mut factor = base % n;
        if factor == 0 {
            continue;
        }
        let mut exponent = d;
        while exponent != 0 {
            if exponent & 1 != 0 {
                value = (u128::from(value) * u128::from(factor) % u128::from(n)) as u64;
            }
            exponent >>= 1;
            factor = (u128::from(factor) * u128::from(factor) % u128::from(n)) as u64;
        }
        if value == 1 || value == n - 1 {
            continue;
        }
        let mut passed = false;
        for _ in 1..s {
            value = (u128::from(value) * u128::from(value) % u128::from(n)) as u64;
            if value == n - 1 {
                passed = true;
                break;
            }
        }
        if !passed {
            return false;
        }
    }
    true
}

fn field_element(value: u128) -> Json {
    text(format!("0x{value:x}"))
}

fn point_json(point: BinaryPoint) -> Json {
    match point {
        BinaryPoint::Infinity => Json::Null,
        BinaryPoint::Affine(x, y) => Json::Array(vec![field_element(x), field_element(y)]),
    }
}

fn projective_json(point: BinaryProjectivePoint) -> Json {
    Json::Array(point.into_iter().map(field_element).collect())
}

/// Decimal rendering of the exact power 2^exponent, without a big-integer crate.
pub fn power_of_two_decimal(exponent: u32) -> String {
    let mut digits = vec![1_u8];
    for _ in 0..exponent {
        let mut carry = 0;
        for digit in &mut digits {
            let value = 2 * *digit + carry;
            *digit = value % 10;
            carry = value / 10;
        }
        if carry != 0 {
            digits.push(carry);
        }
    }
    digits.iter().rev().map(|d| char::from(b'0' + d)).collect()
}

fn orbit_roundtrips(curve: BinaryCurve, start: BinaryPoint) -> Result<usize> {
    let mut seen = HashSet::new();
    let mut point = start;
    for _ in 0..curve.field.degree {
        if !seen.insert(point) {
            break;
        }
        let image = curve.encode(point)?;
        if curve.decode(image)? != point {
            return Err("Binary model round trip failed.".into());
        }
        let scaled = image.map(|v| curve.field.multiply(v, 2));
        if curve.decode(scaled)? != point {
            return Err("Projectively scaled binary round trip failed.".into());
        }
        point = curve.frobenius(point);
    }
    if point != start {
        return Err("Frobenius orbit did not close over the recorded field.".into());
    }
    Ok(seen.len())
}

pub fn parse_binary_point(value: &str) -> Result<BinaryPoint> {
    if value.eq_ignore_ascii_case("O") {
        return Ok(BinaryPoint::Infinity);
    }
    let (x, y) = value
        .split_once(',')
        .ok_or("Supply a binary point as x,y or O.")?;
    fn coordinate(value: &str) -> Result<u128> {
        let value = value.trim();
        if let Some(hex) = value.strip_prefix("0x") {
            u128::from_str_radix(hex, 16).map_err(|_| "Invalid hexadecimal field element.".into())
        } else {
            value
                .parse()
                .map_err(|_| "Invalid decimal field element.".into())
        }
    }
    Ok(BinaryPoint::Affine(coordinate(x)?, coordinate(y)?))
}

pub fn check_n83(
    a: u8,
    scalar: Option<u128>,
    supplied_target: Option<BinaryPoint>,
) -> Result<Json> {
    let fixture = n83_fixture(a)?;
    let BinaryFixture {
        curve,
        generator: p,
        subgroup_order: r,
        cofactor: h,
    } = fixture;
    if gcd(r, h) != 1 || p == BinaryPoint::Infinity {
        return Err("Pinned subgroup separation failed.".into());
    }
    let (q, witness, target_kind) = if let Some(q) = supplied_target {
        (q, scalar.map(|s| s % r), "supplied public point")
    } else {
        let witness = scalar.unwrap_or(37) % r;
        (
            curve.multiply(witness, p)?,
            Some(witness),
            "public known-answer demonstration",
        )
    };
    if !curve.is_on_curve(q) || curve.multiply(r, q)? != BinaryPoint::Infinity {
        return Err("Target is outside the pinned prime-order subgroup.".into());
    }
    if let Some(witness) = witness {
        if curve.multiply(witness, p)? != q {
            return Err("The supplied scalar witness does not match Q.".into());
        }
    }
    let local_prime_check = u64::try_from(r).ok().map(is_prime_u64);
    if local_prime_check == Some(false) {
        return Err("Pinned subgroup order failed deterministic primality checking.".into());
    }
    let image_p = curve.encode(p)?;
    let image_q = curve.encode(q)?;
    if curve.image_multiply(r, image_p)? != [0, 0, 0, 1] {
        return Err("Mapped generator was not annihilated by r.".into());
    }
    let orbit_p = orbit_roundtrips(curve, p)?;
    let orbit_q = orbit_roundtrips(curve, q)?;
    let scalars = [0, 1, 2, 3, 5, 7, 11, 37, r - 1];
    for pair in scalars.windows(2) {
        let left = curve.multiply(pair[0], p)?;
        let right = curve.multiply(pair[1], p)?;
        let sum = curve.add(left, right)?;
        if curve.decode(curve.image_add(curve.encode(left)?, curve.encode(right)?)?)? != sum {
            return Err("Transported addition failed.".into());
        }
    }
    let surface_only = [1, 0, 0, 1];
    let control_lambda = u128::from(a) ^ 1;
    let [q1, q2] = curve.quadric_values(surface_only)?;
    if q2 ^ curve.field.multiply(control_lambda, q1) != 0
        || !curve.quadric(control_lambda)?.smooth
        || curve.decode(surface_only).is_ok()
    {
        return Err("Surface-only negative control failed.".into());
    }
    let (trace, order) = curve.trace_and_order();
    let (smooth, split, nonsplit) = curve.pencil_counts();
    let samples = [
        0,
        1,
        2,
        3,
        4,
        5,
        7,
        11,
        17,
        1_u128 << 82,
        (1_u128 << 82) | 1,
        curve.field.size() - 1,
    ];
    let sample_reports = samples
        .into_iter()
        .map(|lambda| {
            let member = curve.quadric(lambda).unwrap();
            object([
                ("lambda", field_element(lambda)),
                ("smooth", boolean(member.smooth)),
                ("split", member.split.map(boolean).unwrap_or(Json::Null)),
                (
                    "arf_trace",
                    member.arf_trace.map(number).unwrap_or(Json::Null),
                ),
            ])
        })
        .collect();
    let field_size = curve.field.size() as i128;
    let other = BinaryCurve::new(curve.field, a ^ 1)?;
    let (other_trace, other_order) = other.trace_and_order();
    if trace == other_trace || other_order % r == 0 {
        return Err("The opposite-product obstruction did not match these pinned fixtures.".into());
    }
    let coefficients = [
        "1".to_owned(),
        (-2 * trace).to_string(),
        (trace * trace + 2 * field_size).to_string(),
        (-2 * trace * field_size).to_string(),
        power_of_two_decimal(166),
    ];
    let mixed_coefficients = [
        "1".to_owned(),
        (-(trace + other_trace)).to_string(),
        (trace * other_trace + 2 * field_size).to_string(),
        (-(trace + other_trace) * field_size).to_string(),
        power_of_two_decimal(166),
    ];
    Ok(object([
        ("schema", text("ecdlp.binary-surface-check/v1")),
        ("encoding", text("Exact integers are decimal strings; field elements are hexadecimal polynomial-basis masks.")),
        ("field", object([
            ("characteristic", number(2)), ("degree", number(83)),
            ("size", text(curve.field.size().to_string())),
            ("polynomial", text("z^83+z^45+z^2+z+1")),
            ("irreducibility_rabin_verified", boolean(true)),
        ])),
        ("source", object([
            ("equation", text(format!("y^2+x*y=x^3+{a}*x^2+1"))),
            ("a", number(a)), ("b", number(1)),
            ("curve_order", text(order.to_string())), ("trace", text(trace.to_string())),
            ("subgroup_order", text(r.to_string())), ("cofactor", text(h.to_string())),
            ("P", point_json(p)), ("Q", point_json(q)),
            ("target_kind", text(target_kind)), ("fixture_source", text(FIXTURE_SOURCE)),
            ("primality_receipt_source", text(PRIME_RECEIPT_SOURCE)),
            ("primality_proof_receipt_reused", boolean(true)),
            ("primality_deterministic_u64_verified_in_run", local_prime_check.map(boolean).unwrap_or(Json::Null)),
        ])),
        ("quadric_family", object([
            ("Q1", text("W*Z+X^2")),
            ("Q2", text(format!("Y^2+X*Y+X*Z+{a}*W*Z+W^2"))),
            ("pencil", text("Q2+lambda*Q1")),
            ("smooth_condition", text("lambda != a")),
            ("split_condition", text("Tr(lambda+1/(lambda+a)^2)=0, when lambda != a")),
            ("smooth_count", text(smooth.to_string())),
            ("smooth_split_count", text(split.to_string())),
            ("smooth_nonsplit_count", text(nonsplit.to_string())),
            ("count_method", text("Exact classification: smooth=q-1; split=(#E-2)/2; #E from the Koblitz Frobenius recurrence.")),
            ("field_wide_enumeration_performed", boolean(false)),
            ("singular_finite_lambda", field_element(u128::from(a))),
            ("infinite_pencil_member_singular", boolean(true)),
            ("parameter_samples", Json::Array(sample_reports)),
        ])),
        ("transfer", object([
            ("map", text("(x,y)->[1:x:y:x^2]; O->[0:0:0:1]")),
            ("inverse", text("[W:X:Y:Z]->(X/W,Y/W) when W!=0; the unique W=0 curve point maps to O")),
            ("law", text("encode(decode(U)+decode(V))")),
            ("image_P", projective_json(image_p)), ("image_Q", projective_json(image_q)),
            ("r_P_is_identity", boolean(true)), ("r_Q_is_identity", boolean(true)),
            ("P_nonidentity", boolean(true)),
            ("Q_in_generated_subgroup", boolean(true)),
            ("membership_basis", text("The cited prime r, #E=r*h, and gcd(r,h)=1 give a unique order-r subgroup; check rQ=O. No subgroup enumeration.")),
            ("image_P_order", text(r.to_string())),
            ("order_basis", text("Nonidentity P, rP=O, injective inverse, and the cited primality proof; a=1 also has a fresh deterministic u64 check.")),
            ("scalar_mod_r", witness.map(|s| text(s.to_string())).unwrap_or(Json::Null)),
            ("scalar_relation_verified", witness.map(|_| boolean(true)).unwrap_or(Json::Null)),
            ("P_frobenius_orbit_period", number(orbit_p as i128)),
            ("Q_frobenius_orbit_period", number(orbit_q as i128)),
            ("projective_roundtrip_points_checked", number((orbit_p + orbit_q) as i128)),
            ("transported_addition_pairs_checked", number(scalars.len() as i128 - 1)),
            ("ambient_quadric_group_law", boolean(false)),
        ])),
        ("negative_control", object([
            ("point", projective_json(surface_only)),
            ("smooth_surface_lambda", field_element(control_lambda)),
            ("lies_on_smooth_surface", boolean(true)),
            ("curve_image_decode_rejected", boolean(true)),
        ])),
        ("abelian_surface", object([
            ("surface", text("E x E")), ("map", text("P -> (P,O)")),
            ("ambient_law", text("componentwise elliptic addition")),
            ("source_factor", text("T^2-trace*T+q")),
            ("frobenius_polynomial_coefficients", Json::Array(coefficients.into_iter().map(text).collect())),
            ("elliptic_factor_by_construction", boolean(true)),
            ("general_large_q_frobenius_filter_run", boolean(false)),
        ])),
        ("mixed_abelian_surface", object([
            ("surface", text("E_0 x E_1 over the same GF(2^83)")),
            ("map", text(if a == 0 { "P -> (P,O)" } else { "P -> (O,P)" })),
            ("source_factor_index", number(a)),
            ("ambient_law", text("componentwise elliptic addition")),
            ("image_P_order", text(r.to_string())),
            ("frobenius_polynomial_coefficients", Json::Array(mixed_coefficients.into_iter().map(text).collect())),
            ("source_factor_by_construction", boolean(true)),
        ])),
        ("rejected_abelian_surface", object([
            ("surface", text(format!("E_{} x E_{} over the same GF(2^83)", a ^ 1, a ^ 1))),
            ("target_elliptic_trace", text(other_trace.to_string())),
            ("target_elliptic_order", text(other_order.to_string())),
            ("source_target_frobenius_polynomials_coprime", boolean(true)),
            ("source_factor_divides_target_surface_polynomial", boolean(false)),
            ("source_prime_divides_target_elliptic_order", boolean(false)),
            ("target_elliptic_order_mod_source_prime", text((other_order % r).to_string())),
            ("injective_source_subgroup_transfer_possible", boolean(false)),
            ("reason", text("The two traces differ, so their same-q Frobenius quadratics are coprime. The cited prime r also does not divide #E_other and therefore cannot divide #E_other squared.")),
        ])),
        ("interpretation", text("Faithful representations of the pinned n=83 ECDLP. No new solver, unknown-log recovery, destination-solver advantage, or arbitrary abelian-surface homomorphism is established.")),
    ]))
}
