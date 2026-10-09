//! Fixed-width research kernel for Fp = Z[omega]/(pi), p = secp256k1 prime.
//!
//! The hot field operations use only fixed-size limb arrays. Decimal parsing
//! and printing at this diagnostic binary's boundary use num-bigint.

#[path = "../../../../suite/src/ct_bignum.rs"]
mod ct_bignum;

#[cfg(test)]
mod utils {
    use num_bigint::{BigInt, BigUint};
    use num_integer::Integer;
    pub fn mod_inverse(a: &BigUint, modulus: &BigUint) -> Option<BigUint> {
        let m = BigInt::from(modulus.clone());
        let egcd = BigInt::from(a.clone()).extended_gcd(&m);
        if egcd.gcd != BigInt::from(1) {
            None
        } else {
            ((egcd.x % &m + &m) % &m).to_biguint()
        }
    }
}

use ct_bignum::{Uint, U256};
use num_bigint::{BigInt, Sign};
use num_traits::{Signed as NumSigned, ToPrimitive, Zero};
use serde_json::json;
use std::io::{self, BufRead};
use std::sync::LazyLock;

type U512 = Uint<8>;

const PI_A: u128 = 0x3086_d221_a7d4_6bcd_e86c_90e4_9284_eb16;
const PI_B_MAG: u128 = 0xe443_7ed6_010e_8828_6f54_7fa9_0abf_e4c3;
const INV_A: u128 = 0x6ada_d963_1dfe_0bc2_e092_294e_9a6f_4a77;
const INV_B: u128 = 0x0461_c2cb_62a4_16f6_8ab5_d4f0_30b9_d7ad;
const P_SIGNED: Signed = Signed {
    negative: false,
    magnitude: Uint([
        0xffff_fffe_ffff_fc2f,
        u64::MAX,
        u64::MAX,
        u64::MAX,
        0,
        0,
        0,
        0,
    ]),
};

#[derive(Clone, Copy, Debug)]
struct Signed {
    negative: bool,
    magnitude: U512,
}

impl Signed {
    const ZERO: Self = Self {
        negative: false,
        magnitude: U512::ZERO,
    };

    fn from_u128(value: u128) -> Self {
        let mut words = [0u64; 8];
        words[0] = value as u64;
        words[1] = (value >> 64) as u64;
        Self {
            negative: false,
            magnitude: Uint(words),
        }
    }

    fn from_decimal(value: &str) -> Self {
        let number = BigInt::parse_bytes(value.as_bytes(), 10).expect("decimal coefficient");
        let (sign, magnitude) = number.into_parts();
        assert!(
            magnitude.bits() <= 128,
            "input coefficient exceeds balanced width"
        );
        let low = U256::from_biguint(&magnitude);
        let mut words = [0u64; 8];
        words[..4].copy_from_slice(&low.0);
        Self {
            negative: sign == Sign::Minus,
            magnitude: Uint(words),
        }
        .normalized()
    }

    fn decimal(self) -> String {
        let magnitude = self.magnitude.to_biguint().to_string();
        if self.negative {
            format!("-{magnitude}")
        } else {
            magnitude
        }
    }

    fn normalized(mut self) -> Self {
        if bool::from(self.magnitude.ct_is_zero()) {
            self.negative = false;
        }
        self
    }

    fn neg(mut self) -> Self {
        if !bool::from(self.magnitude.ct_is_zero()) {
            self.negative = !self.negative;
        }
        self
    }

    fn add(self, rhs: Self) -> Self {
        if self.negative == rhs.negative {
            let (magnitude, carry) = U512::adc(&self.magnitude, &rhs.magnitude);
            assert_eq!(carry, 0, "fixed-width addition overflow");
            Self {
                negative: self.negative,
                magnitude,
            }
            .normalized()
        } else if bool::from(self.magnitude.ct_lt(&rhs.magnitude)) {
            let (magnitude, borrow) = U512::sbb(&rhs.magnitude, &self.magnitude);
            assert_eq!(borrow, 0);
            Self {
                negative: rhs.negative,
                magnitude,
            }
            .normalized()
        } else {
            let (magnitude, borrow) = U512::sbb(&self.magnitude, &rhs.magnitude);
            assert_eq!(borrow, 0);
            Self {
                negative: self.negative,
                magnitude,
            }
            .normalized()
        }
    }

    fn sub(self, rhs: Self) -> Self {
        self.add(rhs.neg())
    }

    fn times_i32(self, factor: i32) -> Self {
        let mut result = Self::ZERO;
        for _ in 0..factor.unsigned_abs() {
            result = result.add(self);
        }
        if factor < 0 {
            result.neg()
        } else {
            result
        }
    }

    fn abs_le(self, rhs: Self) -> bool {
        !bool::from(rhs.magnitude.ct_lt(&self.magnitude))
    }

    fn mul(self, rhs: Self) -> Self {
        // The balanced field inputs and one-step tau width bound keep every
        // multiplicand below 2^192. A fixed 3x3 schoolbook product uses nine
        // u64 multiplications rather than U256::mul_wide's sixteen.
        assert!(self.magnitude.0[3..].iter().all(|&x| x == 0));
        assert!(rhs.magnitude.0[3..].iter().all(|&x| x == 0));
        let mut words = [0u64; 8];
        for i in 0..3 {
            let mut carry = 0u64;
            for j in 0..3 {
                let index = i + j;
                let sum = (self.magnitude.0[j] as u128) * (rhs.magnitude.0[i] as u128)
                    + (words[index] as u128)
                    + (carry as u128);
                words[index] = sum as u64;
                carry = (sum >> 64) as u64;
            }
            let mut overflow = carry;
            for word in words.iter_mut().skip(i + 3) {
                let sum = (*word as u128) + (overflow as u128);
                *word = sum as u64;
                overflow = (sum >> 64) as u64;
            }
            assert_eq!(overflow, 0, "three-limb product overflow");
        }
        Self {
            negative: self.negative ^ rhs.negative,
            magnitude: Uint(words),
        }
        .normalized()
    }

    fn low_u128(self) -> u128 {
        let low = (self.magnitude.0[0] as u128) | ((self.magnitude.0[1] as u128) << 64);
        if self.negative {
            low.wrapping_neg()
        } else {
            low
        }
    }

    fn exact_shr_128(self) -> Self {
        assert_eq!(self.magnitude.0[0], 0, "Montgomery cancellation failed");
        assert_eq!(self.magnitude.0[1], 0, "Montgomery cancellation failed");
        let mut words = [0u64; 8];
        words[..6].copy_from_slice(&self.magnitude.0[2..]);
        Self {
            negative: self.negative,
            magnitude: Uint(words),
        }
        .normalized()
    }

    fn floor_div_radix_squared(self) -> i32 {
        // A tau output has |t_i| < 22*2^256.
        assert!(self.magnitude.0[5..].iter().all(|&x| x == 0));
        assert!(self.magnitude.0[4] < 22);
        let whole = self.magnitude.0[4] as i32;
        if self.negative {
            let remainder = self.magnitude.0[..4].iter().any(|&x| x != 0);
            -whole - i32::from(remainder)
        } else {
            whole
        }
    }

    fn floor_div_prime_near_radix(self) -> i32 {
        let mut quotient = self.floor_div_radix_squared();
        let residue = self.sub(P_SIGNED.times_i32(quotient));
        if residue.negative {
            quotient -= 1;
        } else if !bool::from(residue.magnitude.ct_lt(&P_SIGNED.magnitude)) {
            quotient += 1;
        }
        let exact_residue = self.sub(P_SIGNED.times_i32(quotient));
        assert!(!exact_residue.negative);
        assert!(bool::from(
            exact_residue.magnitude.ct_lt(&P_SIGNED.magnitude)
        ));
        quotient
    }
}

#[derive(Clone, Copy, Debug)]
struct Pair {
    a: Signed,
    b: Signed,
}

impl Pair {
    const ZERO: Self = Self {
        a: Signed::ZERO,
        b: Signed::ZERO,
    };

    fn one() -> Self {
        // The balanced Eisenstein representative of 2^128 mod pi.
        Self {
            a: Signed::from_u128(27635046095514636760461213597371256793).neg(),
            b: Signed::from_u128(64502973549206556628585045361533709078).neg(),
        }
    }

    fn is_zero(self) -> bool {
        bool::from(self.a.magnitude.ct_is_zero()) && bool::from(self.b.magnitude.ct_is_zero())
    }

    fn neg(self) -> Self {
        Self {
            a: self.a.neg(),
            b: self.b.neg(),
        }
    }

    fn add(self, rhs: Self) -> Self {
        Self {
            a: self.a.add(rhs.a),
            b: self.b.add(rhs.b),
        }
    }

    fn sub(self, rhs: Self) -> Self {
        Self {
            a: self.a.sub(rhs.a),
            b: self.b.sub(rhs.b),
        }
    }

    fn times_i32(self, factor: i32) -> Self {
        Self {
            a: self.a.times_i32(factor),
            b: self.b.times_i32(factor),
        }
    }

    fn product(self, rhs: Self) -> Self {
        let ac = self.a.mul(rhs.a);
        let bd = self.b.mul(rhs.b);
        let cross = self.a.add(self.b).mul(rhs.a.add(rhs.b));
        Self {
            a: ac.sub(bd),
            b: cross.sub(ac).sub(bd.add(bd)),
        }
    }

    fn omega(self) -> Self {
        Self {
            a: self.b.neg(),
            b: self.a.sub(self.b),
        }
    }

    fn small_pi_multiple(a: i32, b: i32, pi: Self) -> Self {
        // (a+b*omega)*(pi.a+pi.b*omega), with small public a,b.
        Self {
            a: pi.a.times_i32(a).sub(pi.b.times_i32(b)),
            b: pi.b.times_i32(a).add(pi.a.sub(pi.b).times_i32(b)),
        }
    }

    fn balance(self) -> Self {
        // u/pi = t/p, t = u*conj(pi). The three pairs of parallel
        // Voronoi boundaries are |2c-d|, |2d-c|, |c+d| <= 1 for
        // c+d*omega = u/pi - q. Multiplying by p makes them integer tests.
        // The input bounds imply a correction q of norm 0, 1, or 3.
        // Lexicographic order resolves exact boundary ties identically to
        // the arbitrary-precision reference.
        const CORRECTIONS: [(i32, i32); 13] = [
            (-2, -1),
            (-1, -2),
            (-1, -1),
            (-1, 0),
            (-1, 1),
            (0, -1),
            (0, 0),
            (0, 1),
            (1, -1),
            (1, 0),
            (1, 1),
            (1, 2),
            (2, 1),
        ];
        let pi = Self::pi();
        let conjugate_pi = Self {
            a: pi.a.sub(pi.b),
            b: pi.b.neg(),
        };
        let t = self.product(conjugate_pi);
        let p = P_SIGNED;
        let twice_a_minus_b = t.a.add(t.a).sub(t.b);
        let twice_b_minus_a = t.b.add(t.b).sub(t.a);
        let a_plus_b = t.a.add(t.b);
        for (a, b) in CORRECTIONS {
            if twice_a_minus_b.sub(p.times_i32(2 * a - b)).abs_le(p)
                && twice_b_minus_a.sub(p.times_i32(2 * b - a)).abs_le(p)
                && a_plus_b.sub(p.times_i32(a + b)).abs_le(p)
            {
                return self.sub(Self::small_pi_multiple(a, b, pi));
            }
        }
        panic!("no Eisenstein correction inside the proved finite set")
    }

    fn balance_tau_output(self) -> Self {
        let pi = Self::pi();
        let t = self.product(Self {
            a: pi.a.sub(pi.b),
            b: pi.b.neg(),
        });
        let floor_a = t.a.floor_div_prime_near_radix();
        let floor_b = t.b.floor_div_prime_near_radix();
        let twice_a_minus_b = t.a.add(t.a).sub(t.b);
        let twice_b_minus_a = t.b.add(t.b).sub(t.a);
        let a_plus_b = t.a.add(t.b);
        for a in floor_a..=floor_a + 1 {
            for b in floor_b..=floor_b + 1 {
                if twice_a_minus_b
                    .sub(P_SIGNED.times_i32(2 * a - b))
                    .abs_le(P_SIGNED)
                    && twice_b_minus_a
                        .sub(P_SIGNED.times_i32(2 * b - a))
                        .abs_le(P_SIGNED)
                    && a_plus_b.sub(P_SIGNED.times_i32(a + b)).abs_le(P_SIGNED)
                {
                    return self.sub(Self::small_pi_multiple(a, b, pi));
                }
            }
        }
        panic!("tau output has no nearest correction among its four corners")
    }

    fn pi() -> Self {
        Self {
            a: Signed::from_u128(PI_A),
            b: Signed::from_u128(PI_B_MAG).neg(),
        }
    }

    fn montgomery_reduce_raw(self) -> Self {
        let za = self.a.low_u128();
        let zb = self.b.low_u128();
        let ac = za.wrapping_mul(INV_A);
        let bd = zb.wrapping_mul(INV_B);
        let qa = ac.wrapping_sub(bd).wrapping_neg();
        let cross = za.wrapping_add(zb).wrapping_mul(INV_A.wrapping_add(INV_B));
        let qb = cross
            .wrapping_sub(ac)
            .wrapping_sub(bd.wrapping_mul(2))
            .wrapping_neg();
        let q = Self {
            a: Signed::from_u128(qa),
            b: Signed::from_u128(qb),
        };
        let numerator = self.add(q.product(Self::pi()));
        Self {
            a: numerator.a.exact_shr_128(),
            b: numerator.b.exact_shr_128(),
        }
    }

    fn montgomery_reduce(self) -> Self {
        self.montgomery_reduce_raw().balance()
    }

    fn mul(self, rhs: Self) -> Self {
        self.product(rhs).montgomery_reduce()
    }

    fn mul_raw(self, rhs: Self) -> Self {
        self.product(rhs).montgomery_reduce_raw()
    }

    fn tau_step(x: Self, y: Self, z: Self) -> [Self; 3] {
        let x3 = x.mul_raw(x).mul_raw(x);
        let rx = y.mul_raw(y).times_i32(4).sub(x3.times_i32(3));
        let inner = x3.times_i32(3).sub(rx.times_i32(2));
        let ry = y.mul_raw(inner);
        let rz = x.sub(x.omega()).mul_raw(z);
        [
            rx.balance_tau_output(),
            ry.balance_tau_output(),
            rz.balance_tau_output(),
        ]
    }

    fn add_field(self, rhs: Self) -> Self {
        self.add(rhs).balance()
    }

    fn sub_field(self, rhs: Self) -> Self {
        self.sub(rhs).balance()
    }

    fn times_field(self, factor: i32) -> Self {
        let mut result = Self::ZERO;
        let mut multiple = self;
        let mut bits = factor.unsigned_abs();
        while bits != 0 {
            if bits & 1 != 0 {
                result = result.add_field(multiple);
            }
            bits >>= 1;
            if bits != 0 {
                multiple = multiple.add_field(multiple);
            }
        }
        if factor < 0 {
            result.neg()
        } else {
            result
        }
    }

    fn tau_constant(self) -> Self {
        self.sub(self.omega()).balance()
    }

    fn strings(self) -> [String; 2] {
        [self.a.decimal(), self.b.decimal()]
    }
}

#[derive(Clone, Copy)]
struct Jacobian {
    x: Pair,
    y: Pair,
    z: Pair,
}

impl Jacobian {
    fn identity() -> Self {
        Self {
            x: Pair::ZERO,
            y: Pair::one(),
            z: Pair::ZERO,
        }
    }

    fn generator() -> Self {
        // Balanced Montgomery images of the standard secp256k1 generator.
        Self {
            x: Pair {
                a: Signed::from_u128(36713677126845979282297855717777403654),
                b: Signed::from_u128(87079531165150581469645078969800828225),
            },
            y: Pair {
                a: Signed::from_u128(83247705229065749111051759197514429994).neg(),
                b: Signed::from_u128(151881601418534134653426678717536693985).neg(),
            },
            z: Pair::one(),
        }
    }

    fn is_identity(self) -> bool {
        self.z.is_zero()
    }

    fn neg(self) -> Self {
        Self {
            x: self.x,
            y: self.y.neg(),
            z: self.z,
        }
    }

    fn omega(self) -> Self {
        Self {
            x: self.x.omega().balance(),
            y: self.y,
            z: self.z,
        }
    }

    fn tau(self) -> Self {
        if self.is_identity() || self.x.is_zero() {
            return Self::identity();
        }
        let [x, y, z] = Pair::tau_step(self.x, self.y, self.z);
        Self { x, y, z }
    }

    fn double(self) -> Self {
        if self.is_identity() || self.y.is_zero() {
            return Self::identity();
        }
        let a = self.x.mul(self.x);
        let b = self.y.mul(self.y);
        let c = b.mul(b);
        let xb = self.x.add_field(b);
        let d = xb.mul(xb).sub_field(a).sub_field(c).times_field(2);
        let e = a.times_field(3);
        let rx = e.mul(e).sub_field(d.times_field(2));
        let ry = e.mul(d.sub_field(rx)).sub_field(c.times_field(8));
        let rz = self.y.mul(self.z).times_field(2);
        Self {
            x: rx,
            y: ry,
            z: rz,
        }
    }

    fn add_mixed(self, q: Self) -> Self {
        debug_assert!(
            !q.is_identity()
                && q.z.a.decimal() == Pair::one().a.decimal()
                && q.z.b.decimal() == Pair::one().b.decimal()
        );
        if self.is_identity() {
            return q;
        }
        let zz = self.z.mul(self.z);
        let u = q.x.mul(zz);
        let s = q.y.mul(self.z).mul(zz);
        let h = u.sub_field(self.x);
        let v = s.sub_field(self.y);
        if h.is_zero() {
            return if v.is_zero() {
                self.double()
            } else {
                Self::identity()
            };
        }
        let hh = h.mul(h);
        let hhh = h.mul(hh);
        let xhh = self.x.mul(hh);
        let rx = v.mul(v).sub_field(hhh).sub_field(xhh.times_field(2));
        let ry = v.mul(xhh.sub_field(rx)).sub_field(self.y.mul(hhh));
        let rz = self.z.mul(h);
        Self {
            x: rx,
            y: ry,
            z: rz,
        }
    }

    fn strings(self) -> [[String; 2]; 3] {
        [self.x.strings(), self.y.strings(), self.z.strings()]
    }
}

fn scalar_from_hex(value: &str) -> BigInt {
    let (negative, unsigned) = value
        .strip_prefix('-')
        .map_or((false, value), |s| (true, s));
    let hex = unsigned.strip_prefix("0x").unwrap_or(unsigned);
    let scalar = BigInt::parse_bytes(hex.as_bytes(), 16).expect("valid scalar hex");
    if negative {
        -scalar
    } else {
        scalar
    }
}

fn round_div(numerator: BigInt, denominator: BigInt) -> BigInt {
    assert!(!denominator.is_zero());
    let (top, bottom) = if denominator < BigInt::ZERO {
        (-numerator, -denominator)
    } else {
        (numerator, denominator)
    };
    let half = &bottom / BigInt::from(2);
    if top < BigInt::ZERO {
        -((-top + half) / bottom)
    } else {
        (top + half) / bottom
    }
}

fn tau_norm(a: &BigInt, b: &BigInt) -> BigInt {
    a * a + 3 * a * b + 3 * b * b
}

struct ScalarLattice {
    n: BigInt,
    lambda_tau: BigInt,
    u0: BigInt,
    u1: BigInt,
    v0: BigInt,
    v1: BigInt,
    det: BigInt,
}

static SCALAR_LATTICE: LazyLock<ScalarLattice> = LazyLock::new(|| {
    let n = scalar_from_hex("fffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141");
    let lambda_tau =
        scalar_from_hex("ac9c52b33fa3cf1f5ad9e3fd77ed9ba4a880b9fc8ec739c2e0cfc810b51283d0");
    let u0 = BigInt::parse_bytes(b"193508920647619669885755136084601127231", 10).unwrap();
    let u1 = BigInt::parse_bytes(b"238911465918039986966665730306072050094", 10).unwrap();
    let v0 = -u1.clone();
    let v1 = BigInt::parse_bytes(b"303414439467246543595250775667605759171", 10).unwrap();
    let det = &u0 * &v1 - &u1 * &v0;
    assert_eq!(det.abs(), n);
    for (x, y) in [(&u0, &u1), (&v0, &v1)] {
        assert_eq!((x + y * &lambda_tau) % &n, BigInt::ZERO);
    }
    ScalarLattice {
        n,
        lambda_tau,
        u0,
        u1,
        v0,
        v1,
        det,
    }
});

fn short_representative(scalar: &BigInt) -> (BigInt, BigInt) {
    let lattice = &*SCALAR_LATTICE;
    let center_u = round_div(scalar * &lattice.v1, lattice.det.clone());
    let center_v = round_div(-scalar * &lattice.u1, lattice.det.clone());
    let mut best: Option<(BigInt, BigInt, BigInt, BigInt)> = None;
    for du in -2..=2 {
        for dv in -2..=2 {
            let u = &center_u + du;
            let v = &center_v + dv;
            let a = scalar - &u * &lattice.u0 - &v * &lattice.v0;
            let b = -&u * &lattice.u1 - &v * &lattice.v1;
            let candidate = (tau_norm(&a, &b), std::cmp::max(a.abs(), b.abs()), a, b);
            if best.as_ref().is_none_or(|old| candidate < *old) {
                best = Some(candidate);
            }
        }
    }
    let (_, _, a, b) = best.expect("25 lattice candidates");
    assert_eq!(
        (&a + &b * &lattice.lambda_tau - scalar) % &lattice.n,
        BigInt::ZERO
    );
    (a, b)
}

#[derive(Clone, Copy, Debug)]
struct Unit {
    sign: i8,
    omega_power: usize,
}

impl Unit {
    fn coefficients(self) -> (i8, i8) {
        let (a, b) = match self.omega_power {
            0 => (1, 0),
            1 => (1, -1),
            2 => (-2, 1),
            _ => unreachable!(),
        };
        (self.sign * a, self.sign * b)
    }
}

fn unit(a: &BigInt, b: &BigInt) -> Option<Unit> {
    match (a.to_i64(), b.to_i64()) {
        (Some(1), Some(0)) => Some(Unit {
            sign: 1,
            omega_power: 0,
        }),
        (Some(1), Some(-1)) => Some(Unit {
            sign: 1,
            omega_power: 1,
        }),
        (Some(-2), Some(1)) => Some(Unit {
            sign: 1,
            omega_power: 2,
        }),
        (Some(-1), Some(0)) => Some(Unit {
            sign: -1,
            omega_power: 0,
        }),
        (Some(-1), Some(1)) => Some(Unit {
            sign: -1,
            omega_power: 1,
        }),
        (Some(2), Some(-1)) => Some(Unit {
            sign: -1,
            omega_power: 2,
        }),
        _ => None,
    }
}

fn recode_tau(mut a: BigInt, mut b: BigInt) -> (Vec<i8>, Option<Unit>) {
    let mut digits = Vec::new();
    while !a.is_zero() || !b.is_zero() {
        if let Some(terminal) = unit(&a, &b) {
            return (digits, Some(terminal));
        }
        // In the basis (1,tau), divisibility by tau is exactly a=0 mod 3.
        let residue: BigInt = ((&a % 3) + 3) % 3;
        let digit: i8 = if residue.is_zero() {
            0
        } else if residue == BigInt::from(1) {
            1
        } else {
            -1
        };
        let reduced_a: BigInt = &a - BigInt::from(digit);
        let next_a = &reduced_a + &b;
        let next_b = -reduced_a / 3;
        debug_assert!(tau_norm(&next_a, &next_b) < tau_norm(&a, &b));
        a = next_a;
        b = next_b;
        digits.push(digit);
        assert!(digits.len() <= 512, "tau expansion did not terminate");
    }
    (digits, None)
}

fn mod_three(value: &BigInt) -> u8 {
    let residue: BigInt = ((value % 3) + 3) % 3;
    residue.to_u8().expect("residue in 0..3")
}

fn width_two_unit(a: &BigInt, b: &BigInt) -> Option<Unit> {
    let residue = (mod_three(a), mod_three(b));
    match residue {
        (0, _) => None,
        (1, 0) => Some(Unit {
            sign: 1,
            omega_power: 0,
        }),
        (2, 0) => Some(Unit {
            sign: -1,
            omega_power: 0,
        }),
        (1, 2) => Some(Unit {
            sign: 1,
            omega_power: 1,
        }),
        (2, 1) => Some(Unit {
            sign: -1,
            omega_power: 1,
        }),
        (1, 1) => Some(Unit {
            sign: 1,
            omega_power: 2,
        }),
        (2, 2) => Some(Unit {
            sign: -1,
            omega_power: 2,
        }),
        _ => unreachable!(),
    }
}

fn recode_tau_width_two(mut a: BigInt, mut b: BigInt) -> (Vec<Option<Unit>>, Option<Unit>) {
    let mut digits = Vec::new();
    while !a.is_zero() || !b.is_zero() {
        if let Some(terminal) = unit(&a, &b) {
            return (digits, Some(terminal));
        }
        let digit = width_two_unit(&a, &b);
        let (da, db) = digit.map_or((0, 0), Unit::coefficients);
        let reduced_a = &a - BigInt::from(da);
        let reduced_b = &b - BigInt::from(db);
        assert_eq!(mod_three(&reduced_a), 0);
        if digit.is_some() {
            // Matching both coefficients modulo 3 makes the next digit zero.
            assert_eq!(mod_three(&reduced_b), 0);
        }
        let next_a = &reduced_a + &reduced_b;
        let next_b = -reduced_a / 3;
        debug_assert!(tau_norm(&next_a, &next_b) < tau_norm(&a, &b));
        a = next_a;
        b = next_b;
        digits.push(digit);
        assert!(
            digits.len() <= 512,
            "width-two tau expansion did not terminate"
        );
    }
    (digits, None)
}

fn unit_point(unit: Unit, generator: Jacobian) -> Jacobian {
    let mut point = generator;
    for _ in 0..unit.omega_power {
        point = point.omega();
    }
    if unit.sign < 0 {
        point.neg()
    } else {
        point
    }
}

fn scalar_multiply(scalar: &BigInt) -> (Jacobian, BigInt, BigInt, usize, usize) {
    let lattice = &*SCALAR_LATTICE;
    let residue = ((scalar % &lattice.n) + &lattice.n) % &lattice.n;
    let (a, b) = short_representative(&residue);
    let (digits, terminal) = recode_tau(a.clone(), b.clone());
    let generator = Jacobian::generator();
    let mut point = terminal.map_or_else(Jacobian::identity, |u| unit_point(u, generator));
    for &digit in digits.iter().rev() {
        point = point.tau();
        if digit != 0 {
            point = point.add_mixed(if digit > 0 {
                generator
            } else {
                generator.neg()
            });
        }
    }
    let nonzero_digits = digits.iter().filter(|&&digit| digit != 0).count();
    (point, a, b, digits.len(), nonzero_digits)
}

fn scalar_multiply_width_two(scalar: &BigInt) -> (Jacobian, BigInt, BigInt, usize, usize) {
    let lattice = &*SCALAR_LATTICE;
    let residue = ((scalar % &lattice.n) + &lattice.n) % &lattice.n;
    let (a, b) = short_representative(&residue);
    let (digits, terminal) = recode_tau_width_two(a.clone(), b.clone());
    let generator = Jacobian::generator();
    let orbit = [generator, generator.omega(), generator.omega().omega()];
    let point_for = |u: Unit| {
        let point = orbit[u.omega_power];
        if u.sign < 0 {
            point.neg()
        } else {
            point
        }
    };
    let mut point = terminal.map_or_else(Jacobian::identity, point_for);
    for &digit in digits.iter().rev() {
        point = point.tau();
        if let Some(u) = digit {
            point = point.add_mixed(point_for(u));
        }
    }
    let nonzero_digits = digits.iter().filter(|digit| digit.is_some()).count();
    (point, a, b, digits.len(), nonzero_digits)
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    assert!(
        args.is_empty() || args == ["--tau"] || args == ["--scalar"] || args == ["--scalar-w2"],
        "usage: eisenstein_fixed [--tau|--scalar|--scalar-w2]"
    );
    let tau_mode = args == ["--tau"];
    let scalar_mode = args == ["--scalar"] || args == ["--scalar-w2"];
    let width_two = args == ["--scalar-w2"];
    for line in io::stdin().lock().lines() {
        let line = line.expect("input line");
        if line.trim().is_empty() {
            continue;
        }
        let fields: Vec<&str> = line.split_whitespace().collect();
        if scalar_mode {
            assert_eq!(fields.len(), 1, "expected one hexadecimal scalar");
            let scalar = scalar_from_hex(fields[0]);
            let (point, a, b, tau_steps, nonzero_digits) = if width_two {
                scalar_multiply_width_two(&scalar)
            } else {
                scalar_multiply(&scalar)
            };
            println!(
                "{}",
                json!({
                    "point": if point.is_identity() { None } else { Some(point.strings()) },
                    "representative": [a.to_string(), b.to_string()],
                    "tau_steps": tau_steps,
                    "nonzero_digits": nonzero_digits,
                    "radix": if width_two { "unit-w2" } else { "signed-w1" },
                })
            );
            continue;
        }
        if tau_mode {
            assert_eq!(fields.len(), 6, "expected six Jacobian coefficients");
            let coordinates: Vec<Signed> = fields.iter().map(|x| Signed::from_decimal(x)).collect();
            let x = Pair {
                a: coordinates[0],
                b: coordinates[1],
            };
            let y = Pair {
                a: coordinates[2],
                b: coordinates[3],
            };
            let z = Pair {
                a: coordinates[4],
                b: coordinates[5],
            };
            let tau = Pair::tau_step(x, y, z);
            println!(
                "{}",
                json!({"tau": [tau[0].strings(), tau[1].strings(), tau[2].strings()]})
            );
            continue;
        }
        assert_eq!(fields.len(), 4, "expected four decimal coefficients");
        let x = Pair {
            a: Signed::from_decimal(fields[0]),
            b: Signed::from_decimal(fields[1]),
        };
        let y = Pair {
            a: Signed::from_decimal(fields[2]),
            b: Signed::from_decimal(fields[3]),
        };
        println!(
            "{}",
            json!({
                "mul": x.mul(y).strings(),
                "add": x.add_field(y).strings(),
                "sub": x.sub_field(y).strings(),
                "omega": x.omega().strings(),
                "tau_constant": x.tau_constant().strings(),
            })
        );
    }
}

#[cfg(test)]
mod eisenstein_tau_tests {
    use super::*;
    use num_integer::Integer;

    #[test]
    fn radix_floor_one_correction_matches_prime_division_at_boundaries() {
        let p = BigInt::from(P_SIGNED.magnitude.to_biguint());
        let offsets = [
            -p.clone(),
            BigInt::from(-1),
            BigInt::from(0),
            BigInt::from(1),
            &p - 1,
            p.clone(),
        ];
        let mut adjusted = 0;
        for multiple in -20..=20 {
            for offset in &offsets {
                let value: BigInt = &p * BigInt::from(multiple) + offset;
                let (sign, magnitude) = value.clone().into_parts();
                let signed = Signed {
                    negative: sign == Sign::Minus,
                    magnitude: U512::from_biguint(&magnitude),
                }
                .normalized();
                let shifted = signed.floor_div_radix_squared();
                let exact = signed.floor_div_prime_near_radix();
                assert_eq!(
                    exact,
                    value.div_floor(&p).to_string().parse::<i32>().unwrap()
                );
                adjusted += usize::from(shifted != exact);
            }
        }
        assert_eq!(adjusted, 119);
    }

    fn same_point(left: Jacobian, right: Jacobian) -> bool {
        if left.is_identity() || right.is_identity() {
            return left.is_identity() && right.is_identity();
        }
        let lz2 = left.z.mul(left.z);
        let rz2 = right.z.mul(right.z);
        let x_equal = left.x.mul(rz2).sub_field(right.x.mul(lz2)).is_zero();
        let y_equal = left
            .y
            .mul(rz2.mul(right.z))
            .sub_field(right.y.mul(lz2.mul(left.z)))
            .is_zero();
        x_equal && y_equal
    }

    #[test]
    fn point_addition_handles_equal_inverse_and_tau_unit_cases() {
        let generator = Jacobian::generator();
        assert!(same_point(
            Jacobian::identity().add_mixed(generator),
            generator
        ));
        assert!(same_point(
            generator.add_mixed(generator),
            generator.double()
        ));
        assert!(generator.add_mixed(generator.neg()).is_identity());
        assert!(same_point(
            generator.tau().add_mixed(generator.omega()),
            generator
        ));
    }

    #[test]
    fn signed_tau_digits_reconstruct_small_eisenstein_pairs() {
        for a in -40..=40 {
            for b in -40..=40 {
                let (digits, terminal) = recode_tau(a.into(), b.into());
                let (mut x, mut y) = match terminal {
                    None => (0i64, 0i64),
                    Some(Unit {
                        sign,
                        omega_power: 0,
                    }) => (i64::from(sign), 0),
                    Some(Unit {
                        sign,
                        omega_power: 1,
                    }) => (i64::from(sign), -i64::from(sign)),
                    Some(Unit {
                        sign,
                        omega_power: 2,
                    }) => (-2 * i64::from(sign), i64::from(sign)),
                    _ => unreachable!(),
                };
                for digit in digits.into_iter().rev() {
                    (x, y) = (-3 * y + i64::from(digit), x + 3 * y);
                }
                assert_eq!((x, y), (a, b));
            }
        }
    }

    #[test]
    fn unit_width_two_digits_are_sparse_and_reconstruct_small_pairs() {
        for a in -40..=40 {
            for b in -40..=40 {
                let (digits, terminal) = recode_tau_width_two(a.into(), b.into());
                for adjacent in digits.windows(2) {
                    assert!(adjacent[0].is_none() || adjacent[1].is_none());
                }
                if terminal.is_some() {
                    assert!(digits.last().is_none_or(Option::is_none));
                }
                let (mut x, mut y) = terminal.map_or((0i64, 0i64), |u| {
                    let (x, y) = u.coefficients();
                    (i64::from(x), i64::from(y))
                });
                for digit in digits.into_iter().rev() {
                    let (da, db) = digit.map_or((0, 0), Unit::coefficients);
                    (x, y) = (-3 * y + i64::from(da), x + 3 * y + i64::from(db));
                }
                assert_eq!((x, y), (a, b));
            }
        }
    }
}
