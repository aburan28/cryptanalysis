//! Fixed-width research kernel for Fp = Z[omega]/(pi), p = secp256k1 prime.
//!
//! The hot field operations use only fixed-size limb arrays. Decimal parsing
//! and printing at this diagnostic binary's boundary use num-bigint.

#[path = "../../../../suite/src/ct_bignum.rs"]
mod ct_bignum;
#[path = "eisenstein_fixed/unit_orbit_windows.rs"]
mod unit_orbit_windows;

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

use ct_bignum::{MontgomeryContext, Uint, U256};
use num_bigint::{BigInt, Sign};
use num_traits::{Signed as NumSigned, ToPrimitive, Zero};
use serde_json::{json, Value};
use std::collections::HashMap;
use std::fs;
use std::io::{self, BufRead};
use std::sync::LazyLock;
use std::time::Instant;

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
const GENERATOR_X_HEX: &str = "79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798";
const GENERATOR_Y_HEX: &str = "483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8";
static DECODE_CONSTANTS: LazyLock<(BigInt, BigInt, BigInt)> = LazyLock::new(|| {
    let p = BigInt::from(P_SIGNED.magnitude.to_biguint());
    let beta = BigInt::parse_bytes(
        b"7ae96a2b657c07106e64479eac3434e99cf0497512f58995c1396c28719501ee",
        16,
    )
    .unwrap();
    let r_inverse = BigInt::parse_bytes(
        b"bcb223fedc24a059d838091dd2253530ffffffffffffffffffffffff434dd931",
        16,
    )
    .unwrap();
    let radix: BigInt = BigInt::from(1u8) << 128usize;
    assert_eq!((&radix * &r_inverse) % &p, BigInt::from(1u8));
    (p, beta, r_inverse)
});

// The Eisenstein kernel stores z*2^128 as a+b*beta. The conventional
// Montgomery kernel stores z*2^256. These constants map the former to the
// latter using one fixed-width product per signed coefficient.
static HYBRID_FIELD: LazyLock<(MontgomeryContext<4>, U256, U256)> = LazyLock::new(|| {
    let p = Uint([P_SIGNED.magnitude.0[0], P_SIGNED.magnitude.0[1],
                  P_SIGNED.magnitude.0[2], P_SIGNED.magnitude.0[3]]);
    let ctx = MontgomeryContext::new(p).expect("odd field prime");
    let radix = num_bigint::BigUint::from(1u8) << 128usize;
    let beta = DECODE_CONSTANTS.1.to_biguint().expect("positive beta");
    let modulus = p.to_biguint();
    let c0 = ctx.to_montgomery(&U256::from_biguint(&radix));
    let c1 = ctx.to_montgomery(&U256::from_biguint(&((beta * radix) % modulus)));
    (ctx, c0, c1)
});

fn hybrid_pair_mont(value: Pair) -> U256 {
    let (ctx, c0, c1) = &*HYBRID_FIELD;
    let term = |coefficient: Signed, constant: &U256| {
        let words = coefficient.magnitude.0;
        assert_eq!(words[4..], [0; 4], "hybrid input exceeds four limbs");
        let magnitude = Uint([words[0], words[1], words[2], words[3]]);
        let product = ctx.mont_mul(&magnitude, constant);
        if coefficient.negative { U256::ZERO.sub_mod(&product, &ctx.n) } else { product }
    };
    term(value.a, c0).add_mod(&term(value.b, c1), &ctx.n)
}

fn hybrid_invert(value: U256, ctx: &MontgomeryContext<4>) -> U256 {
    assert!(!bool::from(value.ct_is_zero()), "cannot invert zero field element");
    let squares = |mut x: U256, count: usize| {
        for _ in 0..count { x = ctx.mont_sqr(&x); }
        x
    };
    let mul = |a: U256, b: U256| ctx.mont_mul(&a, &b);
    let t2 = mul(ctx.mont_sqr(&value), value);
    let t3 = mul(ctx.mont_sqr(&t2), value);
    let t4 = mul(squares(t2, 2), t2);
    let t8 = mul(squares(t4, 4), t4);
    let t11 = mul(squares(t8, 3), t3);
    let t22 = mul(squares(t11, 11), t11);
    let t44 = mul(squares(t22, 22), t22);
    let t88 = mul(squares(t44, 44), t44);
    let t176 = mul(squares(t88, 88), t88);
    let t220 = mul(squares(t176, 44), t44);
    let t223 = mul(squares(t220, 3), t3);
    let x45 = mul(mul(t4, t4), t4);
    let head = mul(squares(t223, 23), t22);
    mul(squares(head, 10), x45)
}

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
        let mut multiple = self;
        let mut bits = factor.unsigned_abs();
        while bits != 0 {
            if bits & 1 != 0 {
                result = result.add(multiple);
            }
            bits >>= 1;
            if bits != 0 {
                multiple = multiple.add(multiple);
            }
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
        self.mul_rect::<3, 3>(rhs)
    }

    fn mul_rect<const LEFT: usize, const RIGHT: usize>(self, rhs: Self) -> Self {
        // Widths are public properties of each formula stage. Assert them
        // before multiplying so a new schedule cannot silently truncate.
        assert!((1..=3).contains(&LEFT) && (1..=3).contains(&RIGHT));
        assert!(self.magnitude.0[LEFT..].iter().all(|&x| x == 0));
        assert!(rhs.magnitude.0[RIGHT..].iter().all(|&x| x == 0));
        let mut words = [0u64; 8];
        for i in 0..RIGHT {
            let mut carry = 0u64;
            for j in 0..LEFT {
                let index = i + j;
                let sum = (self.magnitude.0[j] as u128) * (rhs.magnitude.0[i] as u128)
                    + (words[index] as u128)
                    + (carry as u128);
                words[index] = sum as u64;
                carry = (sum >> 64) as u64;
            }
            let mut overflow = carry;
            for word in words.iter_mut().skip(i + LEFT) {
                let sum = (*word as u128) + (overflow as u128);
                *word = sum as u64;
                overflow = (sum >> 64) as u64;
            }
            assert_eq!(overflow, 0, "rectangular product overflow");
        }
        Self {
            negative: self.negative ^ rhs.negative,
            magnitude: Uint(words),
        }
        .normalized()
    }

    fn low_two_unsigned(self) -> Self {
        let mut words = [0u64; 8];
        words[..2].copy_from_slice(&self.magnitude.0[..2]);
        Self {
            negative: false,
            magnitude: Uint(words),
        }
    }

    fn shift_left_128_unsigned(self) -> Self {
        assert!(self.magnitude.0[6..].iter().all(|&x| x == 0));
        let mut words = [0u64; 8];
        words[2..].copy_from_slice(&self.magnitude.0[..6]);
        Self {
            negative: false,
            magnitude: Uint(words),
        }
    }

    fn mul_two_small_tops(self, rhs: Self) -> Self {
        // Each input is the signed sum of two coefficients below 2^128.
        // Its third limb is a carry bit, so only the low 2x2 needs products.
        assert!(self.magnitude.0[3..].iter().all(|&x| x == 0));
        assert!(rhs.magnitude.0[3..].iter().all(|&x| x == 0));
        assert!(self.magnitude.0[2] <= 1 && rhs.magnitude.0[2] <= 1);
        let left = self.low_two_unsigned();
        let right = rhs.low_two_unsigned();
        let mut result = left.mul_rect::<2, 2>(right);
        if self.magnitude.0[2] != 0 {
            result = result.add(right.shift_left_128_unsigned());
        }
        if rhs.magnitude.0[2] != 0 {
            result = result.add(left.shift_left_128_unsigned());
        }
        if self.magnitude.0[2] != 0 && rhs.magnitude.0[2] != 0 {
            let mut words = [0u64; 8];
            words[4] = 1;
            result = result.add(Self {
                negative: false,
                magnitude: Uint(words),
            });
        }
        result.negative = self.negative ^ rhs.negative;
        result.normalized()
    }

    fn mul_right_small_top<const LEFT: usize>(self, rhs: Self, max_top: u64) -> Self {
        // rhs = low_128 + top*2^128, where top is at most two.
        assert!((1..=3).contains(&LEFT) && max_top <= 2);
        assert!(self.magnitude.0[LEFT..].iter().all(|&x| x == 0));
        assert!(rhs.magnitude.0[3..].iter().all(|&x| x == 0));
        let top = rhs.magnitude.0[2];
        assert!(top <= max_top);
        let mut result = Self {
            negative: false,
            magnitude: self.magnitude,
        }
        .mul_rect::<LEFT, 2>(rhs.low_two_unsigned());
        if top != 0 {
            let shifted = self.shift_left_128_unsigned();
            result = result.add(shifted.times_i32(top as i32));
        }
        result.negative = self.negative ^ rhs.negative;
        result.normalized()
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

    fn floor_div_radix_squared_with_bound(self, max_high_word: u64) -> i32 {
        assert!(self.magnitude.0[5..].iter().all(|&x| x == 0));
        assert!(self.magnitude.0[4] < max_high_word);
        let whole = self.magnitude.0[4] as i32;
        if self.negative {
            let remainder = self.magnitude.0[..4].iter().any(|&x| x != 0);
            -whole - i32::from(remainder)
        } else {
            whole
        }
    }

    #[cfg(test)]
    fn floor_div_radix_squared(self) -> i32 {
        self.floor_div_radix_squared_with_bound(22)
    }

    fn floor_div_prime_near_radix_with_bound(self, max_high_word: u64) -> i32 {
        let mut quotient = self.floor_div_radix_squared_with_bound(max_high_word);
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

    #[cfg(test)]
    fn floor_div_prime_near_radix(self) -> i32 {
        // A tau output has |t_i| < 22*2^256.
        self.floor_div_prime_near_radix_with_bound(22)
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
        Self::from_ring_products(ac, bd, cross)
    }

    fn product_balanced(self, rhs: Self) -> Self {
        // Individual balanced coefficients fit two limbs; the top limb of
        // each coefficient sum is only one carry bit. Use 4+4+4 products.
        let ac = self.a.mul_rect::<2, 2>(rhs.a);
        let bd = self.b.mul_rect::<2, 2>(rhs.b);
        let cross = self.a.add(self.b).mul_two_small_tops(rhs.a.add(rhs.b));
        Self::from_ring_products(ac, bd, cross)
    }

    fn product_wide_balanced(self, rhs: Self) -> Self {
        // The deferred tau schedule keeps the left pair under three limbs
        // and the right pair balanced under two limbs.
        let ac = self.a.mul_rect::<3, 2>(rhs.a);
        let bd = self.b.mul_rect::<3, 2>(rhs.b);
        let cross = self
            .a
            .add(self.b)
            .mul_right_small_top::<3>(rhs.a.add(rhs.b), 1);
        Self::from_ring_products(ac, bd, cross)
    }

    fn product_conjugate_pi(self) -> Self {
        let pi = Self::pi();
        let conjugate_a = pi.a.sub(pi.b);
        let conjugate_b = pi.b.neg();
        // conjugate_a/R has top limb one, and the cross constant
        // (conjugate_a+conjugate_b)/R has top limb at most two.
        let ac = self.a.mul_right_small_top::<3>(conjugate_a, 1);
        let bd = self.b.mul_rect::<3, 2>(conjugate_b);
        let cross = self
            .a
            .add(self.b)
            .mul_right_small_top::<3>(conjugate_a.add(conjugate_b), 2);
        Self::from_ring_products(ac, bd, cross)
    }

    fn from_ring_products(ac: Signed, bd: Signed, cross: Signed) -> Self {
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
        let t = self.product_conjugate_pi();
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
        self.balance_corners(22)
    }

    fn balance_add_output(self) -> Self {
        // The deferred mixed-add schedule bounds the conjugate-pi product
        // coefficient by 38,020,959 * 2^256, below 2^26 * 2^256.
        self.balance_corners(1 << 26)
    }

    fn balance_corners(self, max_high_word: u64) -> Self {
        let pi = Self::pi();
        let t = self.product_conjugate_pi();
        let floor_a = t.a.floor_div_prime_near_radix_with_bound(max_high_word);
        let floor_b = t.b.floor_div_prime_near_radix_with_bound(max_high_word);
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
        panic!("field output has no nearest correction among its four corners")
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
        let numerator = self.add(q.product_balanced(Self::pi()));
        Self {
            a: numerator.a.exact_shr_128(),
            b: numerator.b.exact_shr_128(),
        }
    }

    fn montgomery_reduce(self) -> Self {
        self.montgomery_reduce_raw().balance()
    }

    fn mul(self, rhs: Self) -> Self {
        self.product_balanced(rhs).montgomery_reduce()
    }

    fn invert_chain(self) -> Self {
        assert!(!self.is_zero(), "cannot invert zero field element");
        fn squares(mut value: Pair, count: usize) -> Pair {
            for _ in 0..count {
                value = value.mul(value);
            }
            value
        }
        // The fixed chain evaluates p-2 with 257 squares and 14 products.
        let t2 = self.mul(self).mul(self);
        let t3 = t2.mul(t2).mul(self);
        let t4 = squares(t2, 2).mul(t2);
        let t8 = squares(t4, 4).mul(t4);
        let t11 = squares(t8, 3).mul(t3);
        let t22 = squares(t11, 11).mul(t11);
        let t44 = squares(t22, 22).mul(t22);
        let t88 = squares(t44, 44).mul(t44);
        let t176 = squares(t88, 88).mul(t88);
        let t220 = squares(t176, 44).mul(t44);
        let t223 = squares(t220, 3).mul(t3);
        let x45 = t4.mul(t4).mul(t4);
        let head = squares(t223, 23).mul(t22);
        squares(head, 10).mul(x45)
    }

    fn canonical_hex(self) -> String {
        let (p, beta, r_inverse) = &*DECODE_CONSTANTS;
        let a = BigInt::parse_bytes(self.a.decimal().as_bytes(), 10).unwrap();
        let b = BigInt::parse_bytes(self.b.decimal().as_bytes(), 10).unwrap();
        let value = (((a + b * beta) * r_inverse) % p + p) % p;
        format!("{:0>64}", value.to_str_radix(16))
    }

    fn mul_raw_balanced(self, rhs: Self) -> Self {
        self.product_balanced(rhs).montgomery_reduce_raw()
    }

    fn mul_raw_wide(self, rhs: Self) -> Self {
        self.product_wide_balanced(rhs).montgomery_reduce_raw()
    }

    fn mul_raw_wide_wide(self, rhs: Self) -> Self {
        self.product(rhs).montgomery_reduce_raw()
    }

    fn tau_step(x: Self, y: Self, z: Self) -> [Self; 3] {
        let x3 = x.mul_raw_balanced(x).mul_raw_wide(x);
        let rx = y.mul_raw_balanced(y).times_i32(4).sub(x3.times_i32(3));
        let inner = x3.times_i32(3).sub(rx.times_i32(2));
        let ry = inner.mul_raw_wide(y);
        let rz = x.sub(x.omega()).mul_raw_wide(z);
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

    fn generator_double_affine() -> Self {
        // Independently encoded affine [2]G, reusable for the fixed base.
        Self {
            x: Pair {
                a: Signed::from_u128(39571750039759320469005814233182742570),
                b: Signed::from_u128(23117704555952405709182437912065710380).neg(),
            },
            y: Pair {
                a: Signed::from_u128(109017640759474938754441562896770968623).neg(),
                b: Signed::from_u128(37092078001139422955848364496811764852).neg(),
            },
            z: Pair::one(),
        }
    }

    fn generator_degree_seven_affine() -> Self {
        // Independently encoded affine (1+tau)G = (2-omega)G.
        Self {
            x: Pair {
                a: Signed::from_u128(129987983644354379872830216152808785537),
                b: Signed::from_u128(13530545791547049079317607471229238394),
            },
            y: Pair {
                a: Signed::from_u128(156123508168863827064609719845496060777),
                b: Signed::from_u128(87739319779398525397782622722836580630),
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
        // Keep Montgomery quotients unbalanced through the projective
        // polynomial. Balance h to detect equal/inverse points and bound the
        // remaining products; then balance only the three output coordinates.
        let zz = self.z.mul_raw_balanced(self.z);
        let u = zz.mul_raw_wide(q.x);
        let yz = q.y.mul_raw_balanced(self.z);
        let s = yz.mul_raw_wide_wide(zz);
        let h = u.sub(self.x).balance_add_output();
        let v = s.sub(self.y);
        if h.is_zero() {
            return if v.balance_add_output().is_zero() {
                self.double()
            } else {
                Self::identity()
            };
        }
        let hh = h.mul_raw_balanced(h);
        let hhh = hh.mul_raw_wide(h);
        let xhh = hh.mul_raw_wide(self.x);
        let rx = v.mul_raw_wide_wide(v).sub(hhh).sub(xhh.times_i32(2));
        let ry = v
            .mul_raw_wide_wide(xhh.sub(rx))
            .sub(hhh.mul_raw_wide(self.y));
        let rz = h.mul_raw_balanced(self.z);
        Self {
            x: rx.balance_add_output(),
            y: ry.balance_add_output(),
            z: rz.balance_add_output(),
        }
    }

    fn add_cached(self, q: Self, qz2: Pair, qz3: Pair) -> Self {
        assert!(!q.is_identity());
        if self.is_identity() {
            return q;
        }
        let z1_squared = self.z.mul(self.z);
        let u1 = self.x.mul(qz2);
        let u2 = q.x.mul(z1_squared);
        let s1 = self.y.mul(qz3);
        let s2 = q.y.mul(self.z).mul(z1_squared);
        let h = u2.sub_field(u1);
        let r = s2.sub_field(s1);
        if h.is_zero() {
            return if r.is_zero() {
                self.double()
            } else {
                Self::identity()
            };
        }
        let hh = h.mul(h);
        let hhh = h.mul(hh);
        let v = u1.mul(hh);
        let rx = r.mul(r).sub_field(hhh).sub_field(v.times_field(2));
        let ry = r.mul(v.sub_field(rx)).sub_field(s1.mul(hhh));
        let rz = self.z.mul(q.z).mul(h);
        Self {
            x: rx,
            y: ry,
            z: rz,
        }
    }

    fn strings(self) -> [[String; 2]; 3] {
        [self.x.strings(), self.y.strings(), self.z.strings()]
    }

    fn affine_hex(self) -> String {
        if self.is_identity() {
            return "identity".to_owned();
        }
        let inverse = self.z.invert_chain();
        let square = inverse.mul(inverse);
        let cube = square.mul(inverse);
        let x = self.x.mul(square).canonical_hex();
        let y = self.y.mul(cube).canonical_hex();
        format!("{x}:{y}")
    }

    fn affine_hex_hybrid(self) -> String {
        if self.is_identity() { return "identity".to_owned(); }
        let (ctx, _, _) = &*HYBRID_FIELD;
        let z_inverse = hybrid_invert(hybrid_pair_mont(self.z), ctx);
        let z_square = ctx.mont_sqr(&z_inverse);
        let z_cube = ctx.mont_mul(&z_square, &z_inverse);
        let x = ctx.mont_mul(&hybrid_pair_mont(self.x), &z_square);
        let y = ctx.mont_mul(&hybrid_pair_mont(self.y), &z_cube);
        format!("{}:{}", hex::encode(ctx.from_montgomery(&x).to_bytes_be()),
                hex::encode(ctx.from_montgomery(&y).to_bytes_be()))
    }

    fn into_affine(self) -> Self {
        if self.is_identity() {
            return self;
        }
        let inverse = self.z.invert_chain();
        self.into_affine_with_inverse(inverse)
    }

    fn into_affine_with_inverse(self, inverse: Pair) -> Self {
        assert!(!self.is_identity());
        let square = inverse.mul(inverse);
        Self {
            x: self.x.mul(square),
            y: self.y.mul(square.mul(inverse)),
            z: Pair::one(),
        }
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

fn short_representative_choices(scalar: &BigInt, count: usize) -> Vec<(BigInt, BigInt)> {
    assert!((1..=25).contains(&count));
    let lattice = &*SCALAR_LATTICE;
    let center_u = round_div(scalar * &lattice.v1, lattice.det.clone());
    let center_v = round_div(-scalar * &lattice.u1, lattice.det.clone());
    let mut choices = Vec::with_capacity(count);
    for du in -2..=2 {
        for dv in -2..=2 {
            let u = &center_u + du;
            let v = &center_v + dv;
            let a = scalar - &u * &lattice.u0 - &v * &lattice.v0;
            let b = -&u * &lattice.u1 - &v * &lattice.v1;
            let candidate = (tau_norm(&a, &b), std::cmp::max(a.abs(), b.abs()), a, b);
            if choices.len() < count || candidate < *choices.last().unwrap() {
                choices.push(candidate);
                choices.sort();
                choices.truncate(count);
            }
        }
    }
    choices.into_iter().map(|(_, _, a, b)| (a, b)).collect()
}

// W = U - 2V gives an equilateral Eisenstein lattice basis:
// N(W) = N(V) = N(W+V) = n, so 2< W,V > = -n. The nearest point is among
// the four floor/ceiling corners in these coordinates; the centered
// 3-by-3 neighborhood also contains those four corners.
fn twice_eisenstein_inner(a: &BigInt, b: &BigInt, x: &BigInt, y: &BigInt) -> BigInt {
    a * (2 * x + 3 * y) + b * (3 * x + 6 * y)
}

fn hexagonal_grid_choices(
    scalar: &BigInt, first_w: BigInt, first_v: BigInt,
    side: usize, w0: &BigInt, w1: &BigInt,
) -> Vec<(BigInt, BigInt)> {
    assert!(side == 2 || side == 3);
    let lattice = &*SCALAR_LATTICE;
    let mut row_a = scalar - &first_w * w0 - &first_v * &lattice.v0;
    let mut row_b = -(&first_w * w1) - &first_v * &lattice.v1;
    let base_norm = tau_norm(&row_a, &row_b);
    let twice_w = twice_eisenstein_inner(&row_a, &row_b, w0, w1);
    let twice_v = twice_eisenstein_inner(&row_a, &row_b, &lattice.v0, &lattice.v1);
    let mut choices = Vec::with_capacity(side * side);
    for dw in 0..side {
        let mut a = row_a.clone();
        let mut b = row_b.clone();
        for dv in 0..side {
            let dw = dw as i64;
            let dv = dv as i64;
            let norm = &base_norm - dw * &twice_w - dv * &twice_v
                + (dw * dw + dv * dv - dw * dv) * &lattice.n;
            #[cfg(test)]
            assert_eq!(norm, tau_norm(&a, &b));
            choices.push((norm, std::cmp::max(a.abs(), b.abs()), a.clone(), b.clone()));
            a -= &lattice.v0;
            b -= &lattice.v1;
        }
        row_a -= w0;
        row_b -= w1;
    }
    choices.sort();
    choices.into_iter().map(|(_, _, a, b)| (a, b)).collect()
}

fn hexagonal_representative_choices(scalar: &BigInt) -> Vec<(BigInt, BigInt)> {
    let lattice = &*SCALAR_LATTICE;
    let w0 = &lattice.u0 - 2 * &lattice.v0;
    let w1 = &lattice.u1 - 2 * &lattice.v1;
    let center_w = round_div(scalar * &lattice.v1, lattice.det.clone());
    let center_v = round_div(-scalar * &w1, lattice.det.clone());
    hexagonal_grid_choices(scalar, center_w - 1, center_v - 1, 3, &w0, &w1)
}

fn hexagonal_four_corner_choices(scalar: &BigInt) -> Vec<(BigInt, BigInt)> {
    let lattice = &*SCALAR_LATTICE;
    let w0: BigInt = &lattice.u0 - 2 * &lattice.v0;
    let w1: BigInt = &lattice.u1 - 2 * &lattice.v1;
    assert!(scalar >= &BigInt::ZERO && lattice.v1 > BigInt::ZERO && w1 < BigInt::ZERO);
    // Both numerators are nonnegative for the reduced scalar and this basis.
    let floor_w = (scalar * &lattice.v1) / &lattice.det;
    let floor_v = (-(scalar * &w1)) / &lattice.det;
    hexagonal_grid_choices(scalar, floor_w, floor_v, 2, &w0, &w1)
}

// floor(2^512*c/n), little endian, for c=v1 and c=-(u1-2*v1).
// The proof in prime-j0-exact-reciprocal-20261010/PROTOCOL.md shows that
// floor(k*R/2^512)=floor(k*c/n) for every reduced 256-bit scalar k.
const RECIP_V1: [u64; 7] = [
    0x44180e526536385c, 0x46683369b37d7630, 0x1571b4ae8ac47f71,
    0x221208ac9df506c6, 0x6f547fa90abfe4c4, 0xe4437ed6010e8828, 0,
];
const RECIP_MINUS_W1: [u64; 7] = [
    0x06dfcbca80313b00, 0x30e98f407e1a0fa2, 0xfe04d548d0a02fa2,
    0x5fbc92c10fddd145, 0x57c1108d9d44cfd9, 0x14ca50f7a8e2f3f6, 1,
];

static EXACT_RECIPROCAL_CHECK: LazyLock<()> = LazyLock::new(|| {
    let lattice = &*SCALAR_LATTICE;
    let w1: BigInt = &lattice.u1 - 2 * &lattice.v1;
    let limbs_to_bigint = |limbs: &[u64; 7]| {
        let bytes: Vec<u8> = limbs.iter().flat_map(|limb| limb.to_le_bytes()).collect();
        BigInt::from_bytes_le(Sign::Plus, &bytes)
    };
    assert_eq!(limbs_to_bigint(&RECIP_V1),
               ((BigInt::from(1) << 512) * &lattice.v1) / &lattice.n);
    assert_eq!(limbs_to_bigint(&RECIP_MINUS_W1),
               ((BigInt::from(1) << 512) * -w1) / &lattice.n);
});

fn reciprocal_cell_limbs_from_words_512(k: [u64; 4], reciprocal: &[u64; 7])
    -> ([u64; 3], u64) {
    let mut product = [0u64; 11];
    for (i, &ki) in k.iter().enumerate() {
        let mut carry = 0u128;
        for (j, &rj) in reciprocal.iter().enumerate() {
            let sum = u128::from(ki) * u128::from(rj)
                + u128::from(product[i + j]) + carry;
            product[i + j] = sum as u64;
            carry = sum >> 64;
        }
        let mut index = i + reciprocal.len();
        while carry != 0 {
            assert!(index < product.len());
            let sum = u128::from(product[index]) + carry;
            product[index] = sum as u64;
            carry = sum >> 64;
            index += 1;
        }
    }
    ([product[8], product[9], product[10]], product[7])
}

fn reciprocal_cell_limbs_512(scalar: &BigInt, reciprocal: &[u64; 7]) -> ([u64; 3], u64) {
    reciprocal_cell_limbs_from_words_512(positive_limbs::<4>(scalar), reciprocal)
}

fn reciprocal_cell_512(scalar: &BigInt, reciprocal: &[u64; 7]) -> (BigInt, u64) {
    let (limbs, fraction) = reciprocal_cell_limbs_512(scalar, reciprocal);
    let mut quotient_bytes = [0u8; 24];
    for (index, limb) in limbs.iter().enumerate() {
        quotient_bytes[index * 8..(index + 1) * 8].copy_from_slice(&limb.to_le_bytes());
    }
    (BigInt::from_bytes_le(Sign::Plus, &quotient_bytes), fraction)
}

fn reciprocal_floor_512(scalar: &BigInt, reciprocal: &[u64; 7]) -> BigInt {
    reciprocal_cell_512(scalar, reciprocal).0
}

fn hexagonal_four_corner_choices_reciprocal(scalar: &BigInt) -> Vec<(BigInt, BigInt)> {
    LazyLock::force(&EXACT_RECIPROCAL_CHECK);
    let lattice = &*SCALAR_LATTICE;
    assert!(scalar >= &BigInt::ZERO && scalar < &lattice.n);
    let w0 = &lattice.u0 - 2 * &lattice.v0;
    let w1 = &lattice.u1 - 2 * &lattice.v1;
    let floor_w = reciprocal_floor_512(scalar, &RECIP_V1);
    let floor_v = reciprocal_floor_512(scalar, &RECIP_MINUS_W1);
    hexagonal_grid_choices(scalar, floor_w, floor_v, 2, &w0, &w1)
}

// The high fractional limb of each reciprocal product bounds the true
// Eisenstein cell coordinate within two units of 2^-64. A strict separation
// of the resulting norm intervals certifies the nearest of four corners.
fn certified_corner_from_fraction_limb(hw: u64, hv: u64) -> Option<usize> {
    let b = 1i128 << 64;
    let (hw, hv) = (i128::from(hw), i128::from(hv));
    let a10 = b - 2 * hw + hv;
    let a01 = b + hw - 2 * hv;
    let a11 = b - hw - hv;
    let bounds = [(0, 0), (a10 - 4, a10 + 2),
                  (a01 - 4, a01 + 2), (a11 - 4, a11)];
    let mut winner = None;
    for i in 0..bounds.len() {
        if (0..bounds.len()).all(|j| i == j || bounds[i].1 < bounds[j].0) {
            assert!(winner.replace(i).is_none());
        }
    }
    winner
}

fn hexagonal_certified_corner_choice(scalar: &BigInt) -> ((BigInt, BigInt), bool, usize) {
    LazyLock::force(&EXACT_RECIPROCAL_CHECK);
    let lattice = &*SCALAR_LATTICE;
    assert!(scalar >= &BigInt::ZERO && scalar < &lattice.n);
    let (qw, hw) = reciprocal_cell_512(scalar, &RECIP_V1);
    let (qv, hv) = reciprocal_cell_512(scalar, &RECIP_MINUS_W1);
    let Some(corner) = certified_corner_from_fraction_limb(hw, hv) else {
        // Exact norm and coordinate ordering also resolves boundary ties.
        return (hexagonal_four_corner_choices(scalar).remove(0), true, usize::MAX);
    };
    let (dw, dv) = [(0i32, 0i32), (1, 0), (0, 1), (1, 1)][corner];
    let w0 = &lattice.u0 - 2 * &lattice.v0;
    let w1 = &lattice.u1 - 2 * &lattice.v1;
    let coeff_w: BigInt = &qw + dw;
    let coeff_v: BigInt = &qv + dv;
    let a = scalar - &coeff_w * &w0 - &coeff_v * &lattice.v0;
    let b_first: BigInt = &coeff_w * &w1;
    let b_second: BigInt = &coeff_v * &lattice.v1;
    let b = -b_first - b_second;
    ((a, b), false, corner)
}

fn positive_limbs<const N: usize>(value: &BigInt) -> [u64; N] {
    let (sign, bytes) = value.to_bytes_le();
    assert!(sign != Sign::Minus && bytes.len() <= 8 * N);
    let mut limbs = [0u64; N];
    for (index, chunk) in bytes.chunks(8).enumerate() {
        let mut word = [0u8; 8];
        word[..chunk.len()].copy_from_slice(chunk);
        limbs[index] = u64::from_le_bytes(word);
    }
    limbs
}

struct FixedScalarLattice {
    u1: [u64; 3],
    w0: [u64; 3],
    minus_w1: [u64; 3],
    v1: [u64; 3],
}

static FIXED_SCALAR_LATTICE: LazyLock<FixedScalarLattice> = LazyLock::new(|| {
    let lattice = &*SCALAR_LATTICE;
    let w0: BigInt = &lattice.u0 - BigInt::from(2) * &lattice.v0;
    let minus_w1: BigInt = BigInt::from(2) * &lattice.v1 - &lattice.u1;
    FixedScalarLattice {
        u1: positive_limbs(&lattice.u1),
        w0: positive_limbs(&w0),
        minus_w1: positive_limbs(&minus_w1),
        v1: positive_limbs(&lattice.v1),
    }
});

fn add_one_192(mut value: [u64; 3], bit: i32) -> [u64; 3] {
    assert!((0..=1).contains(&bit));
    let mut carry = bit as u64;
    for limb in &mut value {
        let (sum, next) = limb.overflowing_add(carry);
        *limb = sum;
        carry = u64::from(next);
    }
    assert_eq!(carry, 0);
    value
}

fn mul_192(a: [u64; 3], b: [u64; 3]) -> [u64; 6] {
    let mut product = [0u64; 6];
    for (i, &ai) in a.iter().enumerate() {
        let mut carry = 0u128;
        for (j, &bj) in b.iter().enumerate() {
            let sum = u128::from(ai) * u128::from(bj)
                + u128::from(product[i + j]) + carry;
            product[i + j] = sum as u64;
            carry = sum >> 64;
        }
        assert_eq!(product[i + 3], 0);
        product[i + 3] = carry as u64;
    }
    product
}

fn add_384(mut left: [u64; 6], right: [u64; 6]) -> [u64; 6] {
    let mut carry = 0u128;
    for i in 0..6 {
        let sum = u128::from(left[i]) + u128::from(right[i]) + carry;
        left[i] = sum as u64;
        carry = sum >> 64;
    }
    assert_eq!(carry, 0);
    left
}

fn sub_384(mut left: [u64; 6], right: [u64; 6]) -> [u64; 6] {
    let mut borrow = 0u128;
    for i in 0..6 {
        let rhs = u128::from(right[i]) + borrow;
        let lhs = u128::from(left[i]);
        left[i] = lhs.wrapping_sub(rhs) as u64;
        borrow = u128::from(lhs < rhs);
    }
    left
}

fn signed_192_from_twos_complement(mut limbs: [u64; 6]) -> Signed192 {
    let negative = limbs[5] >> 63 == 1;
    if negative {
        let mut carry = 1u64;
        for limb in &mut limbs {
            let (sum, next) = (!*limb).overflowing_add(carry);
            *limb = sum;
            carry = u64::from(next);
        }
    }
    assert_eq!(&limbs[3..], &[0, 0, 0], "scalar representative exceeds 192 bits");
    let magnitude = [limbs[0], limbs[1], limbs[2]];
    Signed192 { negative: negative && magnitude != [0; 3], limbs: magnitude }
}

fn hexagonal_certified_fixed_choice(scalar: &BigInt) -> ((Signed192, Signed192), bool, usize) {
    LazyLock::force(&EXACT_RECIPROCAL_CHECK);
    let lattice = &*SCALAR_LATTICE;
    assert!(scalar >= &BigInt::ZERO && scalar < &lattice.n);
    let k = positive_limbs::<4>(scalar);
    let (qw, hw) = reciprocal_cell_limbs_from_words_512(k, &RECIP_V1);
    let (qv, hv) = reciprocal_cell_limbs_from_words_512(k, &RECIP_MINUS_W1);
    let Some(corner) = certified_corner_from_fraction_limb(hw, hv) else {
        let (a, b) = hexagonal_four_corner_choices(scalar).remove(0);
        return ((Signed192::from_bigint(&a), Signed192::from_bigint(&b)), true, usize::MAX);
    };
    let (dw, dv) = [(0i32, 0i32), (1, 0), (0, 1), (1, 1)][corner];
    let qw = add_one_192(qw, dw);
    let qv = add_one_192(qv, dv);
    let basis = &*FIXED_SCALAR_LATTICE;
    let a = add_384([k[0], k[1], k[2], k[3], 0, 0], mul_192(qv, basis.u1));
    let a = sub_384(a, mul_192(qw, basis.w0));
    let b = sub_384(mul_192(qw, basis.minus_w1), mul_192(qv, basis.v1));
    ((signed_192_from_twos_complement(a), signed_192_from_twos_complement(b)), false, corner)
}

// Nearby lattice representatives occupy at most 130 bits per coordinate.
// Keep each tau recoding in three stack limbs instead of repeated BigInt division.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct Signed192 {
    negative: bool,
    limbs: [u64; 3],
}

impl Signed192 {
    fn from_bigint(value: &BigInt) -> Self {
        let (sign, bytes) = value.to_bytes_le();
        assert!(bytes.len() <= 24, "scalar representative exceeds 192 bits");
        let mut limbs = [0u64; 3];
        for (index, chunk) in bytes.chunks(8).enumerate() {
            let mut word = [0u8; 8];
            word[..chunk.len()].copy_from_slice(chunk);
            limbs[index] = u64::from_le_bytes(word);
        }
        Self { negative: sign == Sign::Minus && limbs != [0; 3], limbs }
    }

    fn to_bigint(self) -> BigInt {
        let mut bytes = [0u8; 24];
        for (index, limb) in self.limbs.iter().enumerate() {
            bytes[8 * index..8 * (index + 1)].copy_from_slice(&limb.to_le_bytes());
        }
        BigInt::from_bytes_le(if self.negative { Sign::Minus } else { Sign::Plus }, &bytes)
    }

    fn from_i8(value: i8) -> Self {
        Self { negative: value < 0, limbs: [u64::from(value.unsigned_abs()), 0, 0] }
    }

    fn is_zero(self) -> bool { self.limbs == [0; 3] }

    fn neg(mut self) -> Self {
        if !self.is_zero() { self.negative = !self.negative; }
        self
    }

    fn magnitude_less(self, rhs: Self) -> bool {
        for index in (0..3).rev() {
            if self.limbs[index] != rhs.limbs[index] {
                return self.limbs[index] < rhs.limbs[index];
            }
        }
        false
    }

    fn add(self, rhs: Self) -> Self {
        let mut limbs = [0u64; 3];
        let negative;
        if self.negative == rhs.negative {
            let mut carry = 0u128;
            for (index, word) in limbs.iter_mut().enumerate() {
                let sum = u128::from(self.limbs[index]) + u128::from(rhs.limbs[index]) + carry;
                *word = sum as u64;
                carry = sum >> 64;
            }
            assert_eq!(carry, 0, "scalar recoding addition overflow");
            negative = self.negative;
        } else {
            let (larger, smaller) = if self.magnitude_less(rhs) { (rhs, self) } else { (self, rhs) };
            let mut borrow = 0u128;
            for (index, word) in limbs.iter_mut().enumerate() {
                let left = u128::from(larger.limbs[index]);
                let right = u128::from(smaller.limbs[index]) + borrow;
                *word = if left >= right { (left - right) as u64 }
                        else { ((1u128 << 64) + left - right) as u64 };
                borrow = u128::from(left < right);
            }
            assert_eq!(borrow, 0);
            negative = larger.negative;
        }
        Self { negative: negative && limbs != [0; 3], limbs }
    }

    fn sub(self, rhs: Self) -> Self { self.add(rhs.neg()) }

    fn rem_euclid_small(self, divisor: u8) -> u8 {
        let mut rem = 0u128;
        for &word in self.limbs.iter().rev() {
            rem = ((rem << 64) | u128::from(word)) % u128::from(divisor);
        }
        let rem = rem as u8;
        if self.negative && rem != 0 { divisor - rem } else { rem }
    }

    fn div_exact_small(self, divisor: u8) -> Self {
        let mut rem = 0u128;
        let mut limbs = [0u64; 3];
        for index in (0..3).rev() {
            let value = (rem << 64) | u128::from(self.limbs[index]);
            limbs[index] = (value / u128::from(divisor)) as u64;
            rem = value % u128::from(divisor);
        }
        assert_eq!(rem, 0, "scalar recoding quotient is not integral");
        Self { negative: self.negative && limbs != [0; 3], limbs }
    }
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

#[derive(Clone, Copy, Debug)]
struct WidthThreeDigit {
    orbit: usize,
    unit: Unit,
}

impl WidthThreeDigit {
    fn coefficients(self) -> (i8, i8) {
        let (a, b) = match self.orbit {
            0 => (1, 0),
            1 => (2, 0),
            2 => (1, 1),
            _ => unreachable!(),
        };
        let (a, b) = match self.unit.omega_power {
            0 => (a, b),
            1 => (a + 3 * b, -a - 2 * b),
            2 => (-2 * a - 3 * b, a + b),
            _ => unreachable!(),
        };
        (self.unit.sign * a, self.unit.sign * b)
    }
}

const WIDTH_FOUR_SEEDS: [(i8, i8); 18] = [
    (-1, 0),
    (-2, 0),
    (-1, -1),
    (-1, 2),
    (-2, -1),
    (-2, 3),
    (-4, 0),
    (-1, -2),
    (-1, 3),
    (8, 0),
    (7, 0),
    (8, -1),
    (8, -7),
    (7, -1),
    (7, -6),
    (5, 0),
    (8, -2),
    (8, -6),
];

#[derive(Clone, Copy, Debug)]
struct WidthFourDigit {
    orbit: usize,
    unit: Unit,
}

impl WidthFourDigit {
    fn coefficients(self) -> (i8, i8) {
        let (a, b) = WIDTH_FOUR_SEEDS[self.orbit];
        let (a, b) = match self.unit.omega_power {
            0 => (a, b),
            1 => (a + 3 * b, -a - 2 * b),
            2 => (-2 * a - 3 * b, a + b),
            _ => unreachable!(),
        };
        (self.unit.sign * a, self.unit.sign * b)
    }
}

static WIDTH_FOUR_DIGITS: LazyLock<[[Option<WidthFourDigit>; 2]; 81]> = LazyLock::new(|| {
    let mut table = [[None; 2]; 81];
    for orbit in 0..18 {
        for power in 0..3 {
            for sign in [1, -1] {
                let digit = WidthFourDigit {
                    orbit,
                    unit: Unit {
                        sign,
                        omega_power: power,
                    },
                };
                let (a, b) = digit.coefficients();
                let slot =
                    usize::from(a.rem_euclid(9) as u8) * 9 + usize::from(b.rem_euclid(9) as u8);
                let choice = usize::from(orbit >= 9);
                assert!(table[slot][choice].replace(digit).is_none());
            }
        }
    }
    for a in 0..9 {
        for b in 0..9 {
            assert_eq!(table[a * 9 + b][0].is_some(), a % 3 != 0);
            assert_eq!(table[a * 9 + b][1].is_some(), a % 3 != 0);
        }
    }
    table
});

static WIDTH_FOUR_POINTS: LazyLock<[[Jacobian; 3]; 18]> = LazyLock::new(|| {
    let generator = Jacobian::generator();
    let tau_generator = generator.tau().into_affine();
    std::array::from_fn(|orbit| {
        let (a, b) = WIDTH_FOUR_SEEDS[orbit];
        let mut point = Jacobian::identity();
        for _ in 0..a.unsigned_abs() {
            point = point.add_mixed(if a < 0 { generator.neg() } else { generator });
        }
        for _ in 0..b.unsigned_abs() {
            point = point.add_mixed(if b < 0 {
                tau_generator.neg()
            } else {
                tau_generator
            });
        }
        let point = point.into_affine();
        [point, point.omega(), point.omega().omega()]
    })
});

// Frozen minimum-norm representatives for the 81 signed unit orbits of
// Z[tau]/(tau^6), generated by width6_tau_screen.py.
const WIDTH_SIX_SEEDS: [(i8, i8); 81] = [
    (-2, 1),
    (-5, 2),
    (-8, 3),
    (-11, 4),
    (-14, 5),
    (-17, 6),
    (-20, 7),
    (-23, 8),
    (-26, 9),
    (-26, 10),
    (-26, 11),
    (-26, 12),
    (-26, 13),
    (-26, 14),
    (-26, 15),
    (-26, 16),
    (-26, 17),
    (-23, 15),
    (-20, 13),
    (-17, 11),
    (-14, 9),
    (-11, 7),
    (-8, 5),
    (-5, 3),
    (-4, 2),
    (-7, 3),
    (-10, 4),
    (-13, 5),
    (-16, 6),
    (-19, 7),
    (-22, 8),
    (-25, 9),
    (-25, 10),
    (-25, 11),
    (-25, 12),
    (-25, 13),
    (-25, 14),
    (-25, 15),
    (-25, 16),
    (-22, 14),
    (-19, 12),
    (-16, 10),
    (-13, 8),
    (-10, 6),
    (-7, 4),
    (-8, 4),
    (-11, 5),
    (-14, 6),
    (-17, 7),
    (-20, 8),
    (-23, 9),
    (-23, 10),
    (-23, 11),
    (-23, 12),
    (-23, 13),
    (-23, 14),
    (-20, 12),
    (-17, 10),
    (-14, 8),
    (-11, 6),
    (-10, 5),
    (-13, 6),
    (-16, 7),
    (-19, 8),
    (-22, 9),
    (-22, 10),
    (-22, 11),
    (-22, 12),
    (-22, 13),
    (-19, 11),
    (-16, 9),
    (-13, 7),
    (-14, 7),
    (-17, 8),
    (-20, 9),
    (-20, 10),
    (-20, 11),
    (-17, 9),
    (-16, 8),
    (-19, 9),
    (-19, 10),
];

#[derive(Clone, Copy, Debug)]
struct WidthSixDigit {
    orbit: usize,
    unit: Unit,
}

impl WidthSixDigit {
    fn coefficients(self) -> (i8, i8) {
        let (a, b) = WIDTH_SIX_SEEDS[self.orbit];
        let (a, b) = match self.unit.omega_power {
            0 => (a, b),
            1 => (a + 3 * b, -a - 2 * b),
            2 => (-2 * a - 3 * b, a + b),
            _ => unreachable!(),
        };
        (self.unit.sign * a, self.unit.sign * b)
    }
}

static WIDTH_SIX_DIGITS: LazyLock<[Option<WidthSixDigit>; 729]> = LazyLock::new(|| {
    let mut table = [None; 729];
    for orbit in 0..81 {
        for power in 0..3 {
            for sign in [1, -1] {
                let digit = WidthSixDigit {
                    orbit,
                    unit: Unit {
                        sign,
                        omega_power: power,
                    },
                };
                let (a, b) = digit.coefficients();
                let slot =
                    usize::from(a.rem_euclid(27) as u8) * 27 + usize::from(b.rem_euclid(27) as u8);
                assert!(table[slot].replace(digit).is_none());
            }
        }
    }
    for a in 0..27 {
        for b in 0..27 {
            assert_eq!(table[a * 27 + b].is_some(), a % 3 != 0);
        }
    }
    table
});

fn width_six_projective_row(generator: Jacobian) -> [Jacobian; 81] {
    assert_eq!(WIDTH_SIX_SEEDS[0], (-2, 1));
    assert_eq!(
        generator.z.strings(),
        Pair::one().strings(),
        "unit-edge seed graph requires an affine base"
    );
    let mut projective = [None; 81];
    projective[0] = Some(generator.omega().omega());
    let mut queue = vec![0usize];
    let mut head = 0;
    while head < queue.len() {
        let parent = queue[head];
        for next in 0..81 {
            if projective[next].is_some() {
                continue;
            }
            let da = i32::from(WIDTH_SIX_SEEDS[next].0 - WIDTH_SIX_SEEDS[parent].0);
            let db = i32::from(WIDTH_SIX_SEEDS[next].1 - WIDTH_SIX_SEEDS[parent].1);
            if da * da + 3 * da * db + 3 * db * db == 1 {
                let delta = unit(&BigInt::from(da), &BigInt::from(db)).expect("unit edge");
                projective[next] = Some(
                    projective[parent]
                        .expect("connected parent")
                        .add_mixed(unit_point(delta, generator)),
                );
                queue.push(next);
            }
        }
        head += 1;
    }
    assert_eq!(
        queue.len(),
        81,
        "width-six seeds must form a unit-edge tree"
    );
    projective.map(Option::unwrap)
}

fn batch_to_affine(points: &[Jacobian]) -> Vec<Jacobian> {
    let mut prefix = Vec::with_capacity(points.len() + 1);
    prefix.push(Pair::one());
    for point in points {
        assert!(!point.is_identity());
        prefix.push(prefix.last().expect("prefix").mul(point.z));
    }
    let mut suffix_inverse = prefix[points.len()].invert_chain();
    let mut affine = vec![Jacobian::identity(); points.len()];
    for flat in (0..points.len()).rev() {
        let point = points[flat];
        let inverse = suffix_inverse.mul(prefix[flat]);
        suffix_inverse = suffix_inverse.mul(point.z);
        affine[flat] = point.into_affine_with_inverse(inverse);
    }
    assert_eq!(suffix_inverse.strings(), Pair::one().strings());
    affine
}

fn width_six_affine_seed_rows(bases: &[Jacobian]) -> Vec<[Jacobian; 81]> {
    let projective: Vec<Jacobian> = bases
        .iter()
        .copied()
        .flat_map(width_six_projective_row)
        .collect();
    batch_to_affine(&projective)
        .chunks_exact(81)
        .map(|chunk| std::array::from_fn(|index| chunk[index]))
        .collect()
}

fn width_six_comb_tables(rows: usize, width: usize) -> Vec<[Jacobian; 81]> {
    let mut bases = Vec::with_capacity(rows);
    let mut point = Jacobian::generator();
    for row in 0..rows {
        bases.push(point);
        if row + 1 < rows {
            for _ in 0..width {
                point = point.tau();
            }
        }
    }
    width_six_affine_seed_rows(&batch_to_affine(&bases))
}

static WIDTH_SIX_POINTS: LazyLock<[[Jacobian; 3]; 81]> = LazyLock::new(|| {
    width_six_affine_seed_rows(&[Jacobian::generator()])
        .pop()
        .expect("one width-six row")
        .map(|point| [point, point.omega(), point.omega().omega()])
});

static WIDTH_SIX_COMB4_POINTS: LazyLock<Vec<[Jacobian; 81]>> =
    LazyLock::new(|| width_six_comb_tables(4, 41));

static WIDTH_SIX_COMB8_POINTS: LazyLock<Vec<[Jacobian; 81]>> =
    LazyLock::new(|| width_six_comb_tables(8, 21));

static WIDTH_SIX_COMB12_POINTS: LazyLock<Vec<[Jacobian; 81]>> =
    LazyLock::new(|| width_six_comb_tables(12, 14));

// Top-row orbit frequencies from 10,000 scalars drawn with seed 2026100922.
// Every other orbit has a complete row-zero fallback at lookup time.
const WIDTH_SIX_COMB13_TOP_ORBITS: [usize; 52] = [
    0, 1, 2, 3, 4, 5, 6, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 40, 41, 42, 43,
    44, 45, 46, 47, 48, 49, 50, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 69, 70, 71, 72, 73,
    74, 75, 76, 77, 78, 79, 80,
];

struct SparseComb13 {
    full_rows: Box<[[Jacobian; 81]]>,
    top_points: Box<[Jacobian]>,
    top_slots: [u8; 81],
    top_repair: [(u16, u16); 81],
}

const NO_TOP_REPAIR: (u16, u16) = (u16::MAX, u16::MAX);

fn pack_width_six_digit(digit: WidthSixDigit) -> u16 {
    assert!(digit.orbit < 81 && digit.unit.omega_power < 3);
    u16::try_from(digit.orbit * 6 + digit.unit.omega_power * 2
        + usize::from(digit.unit.sign < 0)).unwrap()
}

fn unpack_width_six_digit(code: u16) -> WidthSixDigit {
    assert!(code < 486);
    WidthSixDigit {
        orbit: usize::from(code / 6),
        unit: Unit { sign: if code % 2 == 0 { 1 } else { -1 },
                     omega_power: usize::from((code % 6) / 2) },
    }
}

fn apply_width_six_unit(digit: WidthSixDigit, unit: Unit) -> WidthSixDigit {
    WidthSixDigit {
        orbit: digit.orbit,
        unit: Unit { sign: digit.unit.sign * unit.sign,
                     omega_power: (digit.unit.omega_power + unit.omega_power) % 3 },
    }
}

static WIDTH_SIX_COMB13_POINTS: LazyLock<SparseComb13> = LazyLock::new(|| {
    let mut rows = width_six_comb_tables(13, 13).into_iter();
    let full_rows: Box<[[Jacobian; 81]]> = rows.by_ref().take(12).collect::<Vec<_>>().into_boxed_slice();
    let top_row = rows.next().expect("thirteenth comb row");
    assert!(rows.next().is_none());
    let mut top_slots = [u8::MAX; 81];
    let mut top_points = Vec::with_capacity(WIDTH_SIX_COMB13_TOP_ORBITS.len());
    for orbit in WIDTH_SIX_COMB13_TOP_ORBITS {
        assert!(orbit < 81 && top_slots[orbit] == u8::MAX);
        top_slots[orbit] = u8::try_from(top_points.len()).expect("top slot fits u8");
        top_points.push(top_row[orbit]);
    }
    assert_eq!(full_rows.len() * 81 + top_points.len(), 1024);
    let selected_images: Vec<_> = WIDTH_SIX_COMB13_TOP_ORBITS
        .into_iter()
        .flat_map(|orbit| {
            (0..3).flat_map(move |omega_power| {
                [1, -1].map(move |sign| WidthSixDigit {
                    orbit,
                    unit: Unit { sign, omega_power },
                })
            })
        })
        .collect();
    let mut repair_pairs: [Option<(WidthSixDigit, WidthSixDigit)>; 81] = [None; 81];
    for (index, &left) in selected_images.iter().enumerate() {
        for &right in &selected_images[index..] {
            let (la, lb) = left.coefficients();
            let (ra, rb) = right.coefficients();
            let (sum_a, sum_b) = (i16::from(la) + i16::from(ra),
                                  i16::from(lb) + i16::from(rb));
            let (Ok(sum_a8), Ok(sum_b8)) = (i8::try_from(sum_a), i8::try_from(sum_b)) else {
                continue;
            };
            let slot = usize::from(sum_a.rem_euclid(27) as u8) * 27
                + usize::from(sum_b.rem_euclid(27) as u8);
            let Some(target) = WIDTH_SIX_DIGITS[slot] else { continue };
            if target.coefficients() != (sum_a8, sum_b8)
                || target.unit.sign != 1 || target.unit.omega_power != 0
                || top_slots[target.orbit] != u8::MAX {
                continue;
            }
            let proposal = (left, right);
            let rank = |pair: (WidthSixDigit, WidthSixDigit)| {
                (pair.0.unit.omega_power + pair.1.unit.omega_power,
                 pair.0.orbit, pair.1.orbit,
                 pair.0.unit.omega_power, pair.1.unit.omega_power,
                 pair.0.unit.sign, pair.1.unit.sign)
            };
            if repair_pairs[target.orbit].is_none_or(|old| rank(proposal) < rank(old)) {
                repair_pairs[target.orbit] = Some(proposal);
            }
        }
    }
    let mut covered = 0;
    for digit in WIDTH_SIX_DIGITS.iter().flatten() {
        if top_slots[digit.orbit] == u8::MAX {
            let (left, right) = repair_pairs[digit.orbit].expect("uncovered top digit orbit");
            let left = apply_width_six_unit(left, digit.unit);
            let right = apply_width_six_unit(right, digit.unit);
            let (la, lb) = left.coefficients();
            let (ra, rb) = right.coefficients();
            let (a, b) = digit.coefficients();
            assert_eq!((i16::from(la) + i16::from(ra),
                        i16::from(lb) + i16::from(rb)),
                       (i16::from(a), i16::from(b)));
            covered += 1;
        }
    }
    assert_eq!(covered, 174);
    let top_repair = std::array::from_fn(|orbit| {
        repair_pairs[orbit].map_or(NO_TOP_REPAIR, |(left, right)| {
            (pack_width_six_digit(left), pack_width_six_digit(right))
        })
    });
    SparseComb13 {
        full_rows,
        top_points: top_points.into_boxed_slice(),
        top_slots,
        top_repair,
    }
});

const PAIR_COMB13_ENTRIES_PER_PAIR: usize = 81 * 81 * 6;

#[derive(Clone, Copy)]
struct CompactPairPoint {
    limbs: [[u64; 2]; 4],
    signs: u8,
}

impl CompactPairPoint {
    fn from_affine(point: Jacobian) -> Self {
        assert!(!point.is_identity());
        let coordinates = [point.x.a, point.x.b, point.y.a, point.y.b];
        let mut limbs = [[0u64; 2]; 4];
        let mut signs = 0u8;
        for (index, coordinate) in coordinates.into_iter().enumerate() {
            assert!(coordinate.magnitude.0[2..].iter().all(|&word| word == 0),
                    "balanced affine pair-table coefficient exceeds two limbs");
            limbs[index].copy_from_slice(&coordinate.magnitude.0[..2]);
            signs |= u8::from(coordinate.negative) << index;
        }
        Self { limbs, signs }
    }

    fn into_affine(self) -> Jacobian {
        let coordinates: [Signed; 4] = std::array::from_fn(|index| {
            let mut words = [0u64; 8];
            words[..2].copy_from_slice(&self.limbs[index]);
            Signed { negative: self.signs & (1 << index) != 0,
                     magnitude: Uint(words) }.normalized()
        });
        Jacobian { x: Pair { a: coordinates[0], b: coordinates[1] },
                   y: Pair { a: coordinates[2], b: coordinates[3] },
                   z: Pair::one() }
    }
}

struct PairComb13 {
    rows: Vec<Box<[CompactPairPoint]>>,
}

fn build_pair_comb13_edge(left_row: usize, right_row: usize) -> Box<[CompactPairPoint]> {
    let base = &*WIDTH_SIX_COMB13_POINTS;
    let left = &base.full_rows[left_row];
    let right = &base.full_rows[right_row];
    let mut projective = Vec::with_capacity(PAIR_COMB13_ENTRIES_PER_PAIR);
    for &first in left {
        for &second in right {
            for omega_power in 0..3 {
                for sign in [1, -1] {
                    let unit = Unit { sign, omega_power };
                    projective.push(first.add_mixed(unit_point(unit, second)));
                }
            }
        }
    }
    assert_eq!(projective.len(), PAIR_COMB13_ENTRIES_PER_PAIR);
    batch_to_affine(&projective).into_iter()
        .map(CompactPairPoint::from_affine).collect::<Vec<_>>().into_boxed_slice()
}

fn build_pair_comb13_rows(first_row: usize, count: usize) -> PairComb13 {
    let mut rows = Vec::with_capacity(count);
    for pair in 0..count {
        let left = first_row + 2 * pair;
        rows.push(build_pair_comb13_edge(left, left + 1));
    }
    PairComb13 { rows }
}

static PAIR_COMB13_POINTS: LazyLock<PairComb13> =
    LazyLock::new(|| build_pair_comb13_rows(0, 6));
static ODD_PAIR_COMB13_POINTS: LazyLock<PairComb13> =
    LazyLock::new(|| build_pair_comb13_rows(1, 5));
static DISTANCE_TWO_PAIR_COMB13_POINTS: LazyLock<PairComb13> = LazyLock::new(|| PairComb13 {
    rows: (0..10).map(|row| build_pair_comb13_edge(row, row + 2)).collect(),
});

#[derive(Clone, Copy, Default)]
struct RowMatching {
    edge_codes: [u8; 6],
    count: u8,
}

static RADIUS2_MATCHINGS: LazyLock<Box<[RowMatching]>> = LazyLock::new(|| {
    let mut entries = vec![RowMatching::default(); 1 << 12];
    for mask in 1usize..(1 << 12) {
        let first = mask.trailing_zeros() as usize;
        let rest = mask ^ (1 << first);
        let mut best = entries[rest];
        for second in first + 1..=(first + 2).min(11) {
            if rest & (1 << second) == 0 {
                continue;
            }
            let tail = entries[rest ^ (1 << second)];
            let mut proposal = RowMatching::default();
            proposal.edge_codes[0] = (first * 12 + second) as u8;
            proposal.edge_codes[1..1 + tail.count as usize]
                .copy_from_slice(&tail.edge_codes[..tail.count as usize]);
            proposal.count = tail.count + 1;
            if proposal.count > best.count ||
                (proposal.count == best.count &&
                 proposal.edge_codes[..proposal.count as usize]
                    < best.edge_codes[..best.count as usize]) {
                best = proposal;
            }
        }
        entries[mask] = best;
    }
    entries.into_boxed_slice()
});

// The three long edges were selected by the frozen design-panel greedy rule.
const GRAPH33_EDGES: [(usize, usize); 33] = [
    (0, 1), (0, 2), (0, 3), (0, 8), (0, 11),
    (1, 2), (1, 3), (1, 4), (1, 11),
    (2, 3), (2, 4), (2, 5),
    (3, 4), (3, 5), (3, 6),
    (4, 5), (4, 6), (4, 7),
    (5, 6), (5, 7), (5, 8),
    (6, 7), (6, 8), (6, 9),
    (7, 8), (7, 9), (7, 10),
    (8, 9), (8, 10), (8, 11),
    (9, 10), (9, 11), (10, 11),
];

static GRAPH33_EDGE_SLOTS: LazyLock<[[u8; 12]; 12]> = LazyLock::new(|| {
    let mut slots = [[u8::MAX; 12]; 12];
    for (index, &(left, right)) in GRAPH33_EDGES.iter().enumerate() {
        assert!(left < right && right < 12 && slots[left][right] == u8::MAX);
        slots[left][right] = u8::try_from(index).unwrap();
    }
    slots
});

static GRAPH33_PAIR_COMB13_POINTS: LazyLock<PairComb13> = LazyLock::new(|| PairComb13 {
    rows: GRAPH33_EDGES.iter()
        .map(|&(left, right)| build_pair_comb13_edge(left, right)).collect(),
});

static GRAPH33_MATCHINGS: LazyLock<Box<[RowMatching]>> = LazyLock::new(|| {
    let slots = &*GRAPH33_EDGE_SLOTS;
    let mut entries = vec![RowMatching::default(); 1 << 12];
    for mask in 1usize..(1 << 12) {
        let first = mask.trailing_zeros() as usize;
        let rest = mask ^ (1 << first);
        let mut best = entries[rest];
        for second in first + 1..12 {
            if rest & (1 << second) == 0 || slots[first][second] == u8::MAX {
                continue;
            }
            let tail = entries[rest ^ (1 << second)];
            let mut proposal = RowMatching::default();
            proposal.edge_codes[0] = (first * 12 + second) as u8;
            proposal.edge_codes[1..1 + tail.count as usize]
                .copy_from_slice(&tail.edge_codes[..tail.count as usize]);
            proposal.count = tail.count + 1;
            if proposal.count > best.count ||
                (proposal.count == best.count &&
                 proposal.edge_codes[..proposal.count as usize]
                    < best.edge_codes[..best.count as usize]) {
                best = proposal;
            }
        }
        entries[mask] = best;
    }
    entries.into_boxed_slice()
});

fn pair_comb13_point(table: &PairComb13, pair: usize,
                     first: WidthSixDigit, second: WidthSixDigit) -> Jacobian {
    let relative_sign = first.unit.sign * second.unit.sign;
    let relative_power = (second.unit.omega_power + 3 - first.unit.omega_power) % 3;
    let unit_code = relative_power * 2 + usize::from(relative_sign < 0);
    let index = (first.orbit * 81 + second.orbit) * 6 + unit_code;
    table.rows[pair][index].into_affine()
}

fn glv_comb_table(rows: usize, width: usize) -> Vec<Jacobian> {
    let mut bases = Vec::with_capacity(rows);
    let mut point = Jacobian::generator();
    for row in 0..rows {
        bases.push(point);
        if row + 1 < rows {
            for _ in 0..width {
                point = point.double();
            }
        }
    }
    let bases = batch_to_affine(&bases);
    let mut projective = vec![Jacobian::identity(); 1 << rows];
    for mask in 1usize..(1 << rows) {
        let bit = mask.trailing_zeros() as usize;
        let rest = mask & (mask - 1);
        projective[mask] = if rest == 0 {
            bases[bit]
        } else {
            projective[rest].add_mixed(bases[bit])
        };
    }
    let affine = batch_to_affine(&projective[1..]);
    projective[1..].copy_from_slice(&affine);
    projective
}

static GLV_COMB8_POINTS: LazyLock<Vec<Jacobian>> = LazyLock::new(|| glv_comb_table(8, 16));

static GLV_COMB10_POINTS: LazyLock<Vec<Jacobian>> = LazyLock::new(|| glv_comb_table(10, 13));

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

fn mod_nine(value: &BigInt) -> u8 {
    let residue: BigInt = ((value % 9) + 9) % 9;
    residue.to_u8().expect("residue in 0..9")
}

fn mod_twenty_seven(value: &BigInt) -> u8 {
    let residue: BigInt = ((value % 27) + 27) % 27;
    residue.to_u8().expect("residue in 0..27")
}

fn width_three_digit(a: &BigInt, b: &BigInt) -> Option<WidthThreeDigit> {
    let residue = (mod_nine(a), mod_three(b));
    let (orbit, sign, omega_power) = match residue {
        (0 | 3 | 6, _) => return None,
        (1, 0) => (0, 1, 0),
        (8, 0) => (0, -1, 0),
        (1, 2) => (0, 1, 1),
        (8, 1) => (0, -1, 1),
        (7, 1) => (0, 1, 2),
        (2, 2) => (0, -1, 2),
        (2, 0) => (1, 1, 0),
        (7, 0) => (1, -1, 0),
        (2, 1) => (1, 1, 1),
        (7, 2) => (1, -1, 1),
        (5, 2) => (1, 1, 2),
        (4, 1) => (1, -1, 2),
        (1, 1) => (2, 1, 0),
        (8, 2) => (2, -1, 0),
        (4, 0) => (2, 1, 1),
        (5, 0) => (2, -1, 1),
        (4, 2) => (2, 1, 2),
        (5, 1) => (2, -1, 2),
        _ => unreachable!(),
    };
    Some(WidthThreeDigit {
        orbit,
        unit: Unit { sign, omega_power },
    })
}

fn recode_tau_width_three(
    mut a: BigInt,
    mut b: BigInt,
) -> (Vec<Option<WidthThreeDigit>>, Option<WidthThreeDigit>) {
    let mut digits = Vec::new();
    while !a.is_zero() || !b.is_zero() {
        let digit = width_three_digit(&a, &b);
        if let Some(d) = digit {
            let (da, db) = d.coefficients();
            if a == BigInt::from(da) && b == BigInt::from(db) {
                return (digits, Some(d));
            }
        }
        let (da, db) = digit.map_or((0, 0), WidthThreeDigit::coefficients);
        let reduced_a = &a - BigInt::from(da);
        let reduced_b = &b - BigInt::from(db);
        assert_eq!(mod_three(&reduced_a), 0);
        if digit.is_some() {
            assert_eq!(mod_nine(&reduced_a), 0);
            assert_eq!(mod_three(&reduced_b), 0);
        }
        let next_a = &reduced_a + &reduced_b;
        let next_b = -reduced_a / 3;
        a = next_a;
        b = next_b;
        digits.push(digit);
        assert!(
            digits.len() <= 512,
            "width-three tau expansion did not terminate"
        );
    }
    (digits, None)
}

fn width_four_choices(a: &BigInt, b: &BigInt) -> Option<[WidthFourDigit; 2]> {
    if mod_three(a) == 0 {
        return None;
    }
    let slot = usize::from(mod_nine(a)) * 9 + usize::from(mod_nine(b));
    let entries = WIDTH_FOUR_DIGITS[slot];
    Some([
        entries[0].expect("primary digit"),
        entries[1].expect("alternate digit"),
    ])
}

fn width_four_terminal(a: &BigInt, b: &BigInt) -> Option<WidthFourDigit> {
    width_four_choices(a, b).and_then(|choices| {
        choices.into_iter().find(|digit| {
            let (da, db) = digit.coefficients();
            *a == BigInt::from(da) && *b == BigInt::from(db)
        })
    })
}

fn width_four_zero_quotient(a: &BigInt, b: &BigInt) -> (BigInt, BigInt) {
    assert_eq!(mod_three(a), 0);
    let result = (a + b, -a / 3);
    debug_assert!(tau_norm(&result.0, &result.1) < tau_norm(a, b));
    result
}

fn width_four_block_quotient(a: &BigInt, b: &BigInt, digit: WidthFourDigit) -> (BigInt, BigInt) {
    let (da, db) = digit.coefficients();
    let reduced_a = a - BigInt::from(da);
    let reduced_b = b - BigInt::from(db);
    assert_eq!(mod_nine(&reduced_a), 0);
    assert_eq!(mod_nine(&reduced_b), 0);
    let ra = reduced_a / 9;
    let rb = reduced_b / 9;
    let result = (&ra + 3 * &rb, -&ra - 2 * &rb);
    debug_assert!(tau_norm(&result.0, &result.1) < tau_norm(a, b));
    result
}

type EisensteinState = (BigInt, BigInt);

fn width_four_is_terminal(z: &EisensteinState) -> bool {
    z.0.is_zero() && z.1.is_zero() || width_four_terminal(&z.0, &z.1).is_some()
}

#[derive(Default)]
struct WidthFourPolicy {
    base: HashMap<EisensteinState, usize>,
    look: HashMap<(BigInt, BigInt, u8), usize>,
}

impl WidthFourPolicy {
    fn base_value(&mut self, a: &BigInt, b: &BigInt) -> usize {
        if a.is_zero() && b.is_zero() || width_four_terminal(a, b).is_some() {
            return 0;
        }
        let key = (a.clone(), b.clone());
        if let Some(&cost) = self.base.get(&key) {
            return cost;
        }
        let cost = if let Some(choices) = width_four_choices(a, b) {
            let (qa, qb) = width_four_block_quotient(a, b, choices[0]);
            31 + self.base_value(&qa, &qb)
        } else {
            let (qa, qb) = width_four_zero_quotient(a, b);
            5 + self.base_value(&qa, &qb)
        };
        self.base.insert(key, cost);
        cost
    }

    fn look_value(&mut self, a: &BigInt, b: &BigInt, horizon: u8) -> usize {
        if horizon == 0 || a.is_zero() && b.is_zero() || width_four_terminal(a, b).is_some() {
            return self.base_value(a, b);
        }
        let key = (a.clone(), b.clone(), horizon);
        if let Some(&cost) = self.look.get(&key) {
            return cost;
        }
        let cost = if let Some(choices) = width_four_choices(a, b) {
            31 + choices
                .into_iter()
                .map(|digit| {
                    let (qa, qb) = width_four_block_quotient(a, b, digit);
                    self.look_value(&qa, &qb, horizon - 1)
                })
                .min()
                .expect("two choices")
        } else {
            let (qa, qb) = width_four_zero_quotient(a, b);
            5 + self.look_value(&qa, &qb, horizon)
        };
        self.look.insert(key, cost);
        cost
    }
}

#[derive(Default, Clone, Copy)]
struct WidthFourCompareCounts {
    base_transitions: usize,
    look_zero_steps: usize,
    look_blocks: usize,
}

#[derive(Default)]
struct WidthFourComparator {
    counts: WidthFourCompareCounts,
}

impl WidthFourComparator {
    fn base_step(&mut self, z: &EisensteinState) -> (EisensteinState, i64) {
        self.counts.base_transitions += 1;
        if let Some(choices) = width_four_choices(&z.0, &z.1) {
            (width_four_block_quotient(&z.0, &z.1, choices[0]), 31)
        } else {
            (width_four_zero_quotient(&z.0, &z.1), 5)
        }
    }

    // B(u)-B(v) for the deterministic first-digit continuation. Its two
    // decreasing paths may meet before either reaches a terminal digit.
    fn base_delta(&mut self, mut u: EisensteinState, mut v: EisensteinState) -> i64 {
        if u == v {
            return 0;
        }
        let mut u_cost = 0i64;
        let mut v_cost = 0i64;
        let mut u_seen = vec![(u.clone(), u_cost)];
        let mut v_seen = vec![(v.clone(), v_cost)];
        loop {
            if width_four_is_terminal(&u) && width_four_is_terminal(&v) {
                return u_cost - v_cost;
            }
            if !width_four_is_terminal(&u) {
                let (next, step_cost) = self.base_step(&u);
                u = next;
                u_cost += step_cost;
                if let Some((_, seen_cost)) = v_seen.iter().find(|(state, _)| *state == u) {
                    return u_cost - seen_cost;
                }
                u_seen.push((u.clone(), u_cost));
            }
            if !width_four_is_terminal(&v) {
                let (next, step_cost) = self.base_step(&v);
                v = next;
                v_cost += step_cost;
                if let Some((_, seen_cost)) = u_seen.iter().find(|(state, _)| *state == v) {
                    return seen_cost - v_cost;
                }
                v_seen.push((v.clone(), v_cost));
            }
        }
    }

    // Expand through zero steps and one nonzero block. A terminal gives one
    // outcome; otherwise the two digit choices give two outcomes.
    fn one_block(&mut self, mut z: EisensteinState) -> Vec<(i64, EisensteinState)> {
        let mut prefix = 0;
        while !width_four_is_terminal(&z) && mod_three(&z.0) == 0 {
            z = width_four_zero_quotient(&z.0, &z.1);
            prefix += 5;
            self.counts.look_zero_steps += 1;
        }
        if width_four_is_terminal(&z) {
            return vec![(prefix, z)];
        }
        self.counts.look_blocks += 1;
        width_four_choices(&z.0, &z.1)
            .expect("nonterminal block")
            .map(|digit| (prefix + 31, width_four_block_quotient(&z.0, &z.1, digit)))
            .into_iter()
            .collect()
    }

    fn choose(&mut self, quotients: [EisensteinState; 2]) -> usize {
        let outcomes = quotients.map(|z| self.one_block(z));
        let reference = outcomes[0][0].1.clone();
        let scores = outcomes.map(|choices| {
            choices
                .into_iter()
                .map(|(prefix, z)| prefix + self.base_delta(z, reference.clone()))
                .min()
                .expect("one or two outcomes")
        });
        usize::from(scores[1] < scores[0])
    }
}

fn recode_tau_width_four_redundant(
    mut a: BigInt,
    mut b: BigInt,
    coalescent: bool,
) -> (
    Vec<Option<WidthFourDigit>>,
    Option<WidthFourDigit>,
    usize,
    WidthFourCompareCounts,
) {
    let mut comparator = WidthFourComparator::default();
    let mut policy = WidthFourPolicy::default();
    let mut digits = Vec::new();
    let mut alternate_uses = 0;
    while !a.is_zero() || !b.is_zero() {
        if let Some(terminal) = width_four_terminal(&a, &b) {
            return (digits, Some(terminal), alternate_uses, comparator.counts);
        }
        if let Some(choices) = width_four_choices(&a, &b) {
            let quotients = choices.map(|digit| width_four_block_quotient(&a, &b, digit));
            let choice = if coalescent {
                comparator.choose(quotients.clone())
            } else {
                let values = quotients
                    .clone()
                    .map(|(qa, qb)| policy.look_value(&qa, &qb, 1));
                usize::from(values[1] < values[0])
            };
            let digit = choices[choice];
            (a, b) = quotients[choice].clone();
            digits.extend([Some(digit), None, None, None]);
            alternate_uses += choice;
        } else {
            (a, b) = width_four_zero_quotient(&a, &b);
            digits.push(None);
        }
        assert!(
            digits.len() <= 512,
            "width-four expansion did not terminate"
        );
    }
    (digits, None, alternate_uses, comparator.counts)
}

fn width_six_digit(a: &BigInt, b: &BigInt) -> Option<WidthSixDigit> {
    if mod_three(a) == 0 {
        return None;
    }
    let slot = usize::from(mod_twenty_seven(a)) * 27 + usize::from(mod_twenty_seven(b));
    Some(WIDTH_SIX_DIGITS[slot].expect("nonzero width-six residue"))
}

fn recode_tau_width_six(
    mut a: BigInt,
    mut b: BigInt,
) -> (Vec<Option<WidthSixDigit>>, Option<WidthSixDigit>) {
    let mut digits = Vec::new();
    while !a.is_zero() || !b.is_zero() {
        if let Some(digit) = width_six_digit(&a, &b) {
            let (da, db) = digit.coefficients();
            if a == BigInt::from(da) && b == BigInt::from(db) {
                return (digits, Some(digit));
            }
            let reduced_a = &a - BigInt::from(da);
            let reduced_b = &b - BigInt::from(db);
            assert_eq!(mod_twenty_seven(&reduced_a), 0);
            assert_eq!(mod_twenty_seven(&reduced_b), 0);
            let next_a = -reduced_a / 27;
            let next_b = -reduced_b / 27;
            debug_assert!(tau_norm(&next_a, &next_b) < tau_norm(&a, &b));
            a = next_a;
            b = next_b;
            digits.extend([Some(digit), None, None, None, None, None]);
        } else {
            (a, b) = width_four_zero_quotient(&a, &b);
            digits.push(None);
        }
        assert!(digits.len() <= 512, "width-six expansion did not terminate");
    }
    (digits, None)
}

#[derive(Clone, Copy)]
struct PackedTauSixStream {
    codes: [u16; 162],
    len: usize,
}

impl PackedTauSixStream {
    fn digits(self) -> Vec<Option<WidthSixDigit>> {
        self.codes[..self.len].iter().map(|&code| {
            (code != u16::MAX).then(|| unpack_width_six_digit(code))
        }).collect()
    }

    fn cover_score(self, table: &SparseComb13) -> Option<usize> {
        let mut nonzero = 0usize;
        let mut max_column = 0usize;
        let mut top_count = 0usize;
        let mut repairs = 0usize;
        for (index, &code) in self.codes[..self.len].iter().enumerate() {
            if code == u16::MAX { continue; }
            nonzero += 1;
            max_column = max_column.max(index % 13);
            if index >= 156 {
                top_count += 1;
                repairs += usize::from(table.top_slots[unpack_width_six_digit(code).orbit] == u8::MAX);
            }
        }
        (top_count <= 1).then_some(5 * max_column + 11 * (nonzero.saturating_sub(1) + repairs))
    }

    fn graph33_score(self, table: &SparseComb13) -> Option<usize> {
        let mut nonzero = 0usize;
        let mut max_column = 0usize;
        let mut top_count = 0usize;
        let mut repairs = 0usize;
        let mut masks = [0usize; 13];
        for (index, &code) in self.codes[..self.len].iter().enumerate() {
            if code == u16::MAX { continue; }
            nonzero += 1;
            let column = index % 13;
            max_column = max_column.max(column);
            if index >= 156 {
                top_count += 1;
                repairs += usize::from(table.top_slots[unpack_width_six_digit(code).orbit] == u8::MAX);
            } else {
                masks[column] |= 1 << (index / 13);
            }
        }
        if top_count > 1 { return None; }
        let fusions: usize = masks.iter()
            .map(|&mask| usize::from(GRAPH33_MATCHINGS[mask].count)).sum();
        let additions = nonzero.saturating_sub(1) + repairs;
        assert!(fusions <= additions);
        Some(5 * max_column + 11 * (additions - fusions))
    }
}

fn recode_tau_width_six_packed(a: &BigInt, b: &BigInt) -> Option<PackedTauSixStream> {
    let mut a = Signed192::from_bigint(a);
    let mut b = Signed192::from_bigint(b);
    let mut stream = PackedTauSixStream { codes: [u16::MAX; 162], len: 0 };
    while !a.is_zero() || !b.is_zero() {
        if a.rem_euclid_small(3) != 0 {
            let slot = usize::from(a.rem_euclid_small(27)) * 27
                + usize::from(b.rem_euclid_small(27));
            let digit = WIDTH_SIX_DIGITS[slot].expect("nonzero width-six residue");
            if stream.len >= 162 { return None; }
            stream.codes[stream.len] = pack_width_six_digit(digit);
            let (da, db) = digit.coefficients();
            if a == Signed192::from_i8(da) && b == Signed192::from_i8(db) {
                stream.len += 1;
                return Some(stream);
            }
            if stream.len + 6 > 162 { return None; }
            a = a.sub(Signed192::from_i8(da)).div_exact_small(27).neg();
            b = b.sub(Signed192::from_i8(db)).div_exact_small(27).neg();
            stream.len += 6;
        } else {
            if stream.len >= 162 { return None; }
            let next_a = a.add(b);
            b = a.div_exact_small(3).neg();
            a = next_a;
            stream.len += 1;
        }
    }
    Some(stream)
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

fn scalar_multiply_width_three(
    scalar: &BigInt,
    affine_fixed: bool,
) -> (Jacobian, BigInt, BigInt, usize, [usize; 3]) {
    let lattice = &*SCALAR_LATTICE;
    let residue = ((scalar % &lattice.n) + &lattice.n) % &lattice.n;
    let (a, b) = short_representative(&residue);
    let (digits, terminal) = recode_tau_width_three(a.clone(), b.clone());
    let generator = Jacobian::generator();
    let (doubled, degree_seven) = if affine_fixed {
        (
            Jacobian::generator_double_affine(),
            Jacobian::generator_degree_seven_affine(),
        )
    } else {
        let doubled = generator.double();
        // (1+tau)G = (2-omega)G; one doubling and one mixed add prepare
        // all three width-three digit orbits for a one-use base.
        let degree_seven = doubled.add_mixed(generator.omega().neg());
        (doubled, degree_seven)
    };
    let bases = [generator, doubled, degree_seven];
    let orbits = bases.map(|base| [base, base.omega(), base.omega().omega()]);
    let caches = if affine_fixed {
        None
    } else {
        Some([doubled, degree_seven].map(|base| {
            let z2 = base.z.mul(base.z);
            (z2, z2.mul(base.z))
        }))
    };
    let point_for = |d: WidthThreeDigit| {
        let point = orbits[d.orbit][d.unit.omega_power];
        if d.unit.sign < 0 {
            point.neg()
        } else {
            point
        }
    };
    let mut point = terminal.map_or_else(Jacobian::identity, point_for);
    let mut orbit_counts = [0usize; 3];
    for &digit in digits.iter().rev() {
        point = point.tau();
        if let Some(d) = digit {
            let q = point_for(d);
            point = if d.orbit == 0 || affine_fixed {
                point.add_mixed(q)
            } else {
                let (z2, z3) = caches.expect("projective Z cache")[d.orbit - 1];
                point.add_cached(q, z2, z3)
            };
            orbit_counts[d.orbit] += 1;
        }
    }
    (point, a, b, digits.len(), orbit_counts)
}

fn scalar_multiply_width_four_redundant(
    scalar: &BigInt,
    coalescent: bool,
) -> (
    Jacobian,
    BigInt,
    BigInt,
    usize,
    [usize; 18],
    usize,
    WidthFourCompareCounts,
) {
    let lattice = &*SCALAR_LATTICE;
    let residue = ((scalar % &lattice.n) + &lattice.n) % &lattice.n;
    let (a, b) = short_representative(&residue);
    let (digits, terminal, alternate_uses, compare_counts) =
        recode_tau_width_four_redundant(a.clone(), b.clone(), coalescent);
    let point_for = |digit: WidthFourDigit| {
        let point = WIDTH_FOUR_POINTS[digit.orbit][digit.unit.omega_power];
        if digit.unit.sign < 0 {
            point.neg()
        } else {
            point
        }
    };
    let mut point = terminal.map_or_else(Jacobian::identity, point_for);
    let mut orbit_counts = [0usize; 18];
    for &digit in digits.iter().rev() {
        point = point.tau();
        if let Some(d) = digit {
            point = point.add_mixed(point_for(d));
            orbit_counts[d.orbit] += 1;
        }
    }
    (
        point,
        a,
        b,
        digits.len(),
        orbit_counts,
        alternate_uses,
        compare_counts,
    )
}

fn scalar_multiply_width_six(scalar: &BigInt) -> (Jacobian, BigInt, BigInt, usize, [usize; 81]) {
    let lattice = &*SCALAR_LATTICE;
    let residue = ((scalar % &lattice.n) + &lattice.n) % &lattice.n;
    let (a, b) = short_representative(&residue);
    let (digits, terminal) = recode_tau_width_six(a.clone(), b.clone());
    let point_for = |digit: WidthSixDigit| {
        let point = WIDTH_SIX_POINTS[digit.orbit][digit.unit.omega_power];
        if digit.unit.sign < 0 {
            point.neg()
        } else {
            point
        }
    };
    let mut point = terminal.map_or_else(Jacobian::identity, point_for);
    let mut orbit_counts = [0usize; 81];
    for &digit in digits.iter().rev() {
        point = point.tau();
        if let Some(d) = digit {
            point = point.add_mixed(point_for(d));
            orbit_counts[d.orbit] += 1;
        }
    }
    (point, a, b, digits.len(), orbit_counts)
}

fn scalar_multiply_width_six_comb(
    scalar: &BigInt,
    rows: usize,
) -> (Jacobian, BigInt, BigInt, usize, [usize; 81]) {
    let width = match rows {
        4 => 41,
        8 => 21,
        12 => 14,
        _ => panic!("unsupported width-six comb row count"),
    };
    let tables = match rows {
        4 => &*WIDTH_SIX_COMB4_POINTS,
        8 => &*WIDTH_SIX_COMB8_POINTS,
        12 => &*WIDTH_SIX_COMB12_POINTS,
        _ => unreachable!(),
    };
    let lattice = &*SCALAR_LATTICE;
    let residue = ((scalar % &lattice.n) + &lattice.n) % &lattice.n;
    let (a, b) = short_representative(&residue);
    let (mut digits, terminal) = recode_tau_width_six(a.clone(), b.clone());
    if let Some(digit) = terminal {
        digits.push(Some(digit));
    }
    assert!(digits.len() <= rows * width, "comb digit span exceeded");
    let mut point = Jacobian::identity();
    let mut started = false;
    let mut tau_steps = 0;
    let mut orbit_counts = [0usize; 81];
    for column in (0..width).rev() {
        if started {
            point = point.tau();
            tau_steps += 1;
        }
        for row in 0..rows {
            if let Some(Some(digit)) = digits.get(row * width + column) {
                let mut addend = tables[row][digit.orbit];
                for _ in 0..digit.unit.omega_power {
                    addend = addend.omega();
                }
                if digit.unit.sign < 0 {
                    addend = addend.neg();
                }
                if started {
                    point = point.add_mixed(addend);
                    orbit_counts[digit.orbit] += 1;
                } else {
                    point = addend;
                    started = true;
                }
            }
        }
    }
    (point, a, b, tau_steps, orbit_counts)
}

fn width_six_unit_image(mut point: Jacobian, digit: WidthSixDigit) -> Jacobian {
    for _ in 0..digit.unit.omega_power {
        point = point.omega();
    }
    if digit.unit.sign < 0 {
        point.neg()
    } else {
        point
    }
}

fn width_six_row_zero_fallback(
    digits: &[Option<WidthSixDigit>],
    row: &[Jacobian; 81],
) -> (Jacobian, usize, [usize; 81]) {
    let mut point = Jacobian::identity();
    let mut started = false;
    let mut tau_steps = 0;
    let mut orbit_counts = [0usize; 81];
    for &digit in digits.iter().rev() {
        if started {
            point = point.tau();
            tau_steps += 1;
        }
        if let Some(digit) = digit {
            let addend = width_six_unit_image(row[digit.orbit], digit);
            if started {
                point = point.add_mixed(addend);
                orbit_counts[digit.orbit] += 1;
            } else {
                point = addend;
                started = true;
            }
        }
    }
    (point, tau_steps, orbit_counts)
}

fn width_six_comb13_sparse_score(digits: &[Option<WidthSixDigit>], table: &SparseComb13) -> Option<usize> {
    if digits.len() > 162 {
        return None;
    }
    let mut top_count = 0;
    let mut fallback = false;
    let mut nonzero = 0usize;
    let mut last_index = 0;
    let mut max_column = 0;
    for (index, digit) in digits.iter().enumerate() {
        if let Some(digit) = digit {
            nonzero += 1;
            last_index = index;
            max_column = max_column.max(index % 13);
            if index >= 156 {
                top_count += 1;
                fallback |= table.top_slots[digit.orbit] == u8::MAX;
            }
        }
    }
    if top_count > 1 {
        return None;
    }
    let tau_steps = if fallback { last_index } else { max_column };
    Some(5 * tau_steps + 11 * nonzero.saturating_sub(1))
}

fn add_comb13_digit(
    point: &mut Jacobian,
    started: &mut bool,
    orbit_counts: &mut [usize; 81],
    digit: WidthSixDigit,
    seed: Jacobian,
) {
    let addend = width_six_unit_image(seed, digit);
    if *started {
        *point = point.add_mixed(addend);
        orbit_counts[digit.orbit] += 1;
    } else {
        *point = addend;
        *started = true;
    }
}

fn evaluate_width_six_comb13_sparse(
    a: BigInt,
    b: BigInt,
    digits: Vec<Option<WidthSixDigit>>,
    repair_top: bool,
) -> (Jacobian, BigInt, BigInt, usize, [usize; 81], bool) {
    let table = &*WIDTH_SIX_COMB13_POINTS;
    assert!(digits.len() <= 162, "comb digit span exceeded");
    let top_digits: Vec<_> = digits.iter().skip(156).flatten().collect();
    assert!(top_digits.len() <= 1, "top row must contain at most one terminal digit");
    if !repair_top && top_digits
        .iter()
        .any(|digit| table.top_slots[digit.orbit] == u8::MAX)
    {
        let (point, tau_steps, orbit_counts) =
            width_six_row_zero_fallback(&digits, &table.full_rows[0]);
        return (point, a, b, tau_steps, orbit_counts, true);
    }
    let mut point = Jacobian::identity();
    let mut started = false;
    let mut tau_steps = 0;
    let mut orbit_counts = [0usize; 81];
    let mut repaired = false;
    for column in (0..13).rev() {
        if started {
            point = point.tau();
            tau_steps += 1;
        }
        for row in 0..13 {
            if let Some(Some(digit)) = digits.get(row * 13 + column) {
                if row == 12 && table.top_slots[digit.orbit] == u8::MAX {
                    assert!(repair_top);
                    let (left_code, right_code) = table.top_repair[digit.orbit];
                    assert_ne!((left_code, right_code), NO_TOP_REPAIR);
                    let left = apply_width_six_unit(unpack_width_six_digit(left_code), digit.unit);
                    let right = apply_width_six_unit(unpack_width_six_digit(right_code), digit.unit);
                    for part in [left, right] {
                        let seed = table.top_points[usize::from(table.top_slots[part.orbit])];
                        add_comb13_digit(&mut point, &mut started, &mut orbit_counts, part, seed);
                    }
                    repaired = true;
                } else {
                    let seed = if row == 12 {
                        table.top_points[usize::from(table.top_slots[digit.orbit])]
                    } else {
                        table.full_rows[row][digit.orbit]
                    };
                    add_comb13_digit(&mut point, &mut started, &mut orbit_counts, *digit, seed);
                }
            }
        }
    }
    (point, a, b, tau_steps, orbit_counts, repaired)
}

fn evaluate_width_six_comb13_matched(
    a: BigInt,
    b: BigInt,
    digits: Vec<Option<WidthSixDigit>>,
    matching_radius: u8,
) -> (Jacobian, BigInt, BigInt, usize, [usize; 81], bool, usize) {
    assert!(matching_radius <= 3);
    let table = &*WIDTH_SIX_COMB13_POINTS;
    let pairs = (matching_radius < 3).then(|| &*PAIR_COMB13_POINTS);
    let odd_pairs = (matching_radius >= 1 && matching_radius < 3)
        .then(|| &*ODD_PAIR_COMB13_POINTS);
    let distance_two = (matching_radius == 2).then(|| &*DISTANCE_TWO_PAIR_COMB13_POINTS);
    let graph33 = (matching_radius == 3).then(|| &*GRAPH33_PAIR_COMB13_POINTS);
    assert!(digits.len() <= 162, "comb digit span exceeded");
    assert!(digits.iter().skip(156).flatten().count() <= 1);
    let mut point = Jacobian::identity();
    let mut started = false;
    let mut tau_steps = 0;
    let mut orbit_counts = [0usize; 81];
    let mut repaired = false;
    let mut fusions = 0;
    for column in (0..13).rev() {
        if started {
            point = point.tau();
            tau_steps += 1;
        }
        if matching_radius >= 2 {
            let mut active = 0usize;
            for row in 0..12 {
                if digits.get(row * 13 + column).copied().flatten().is_some() {
                    active |= 1 << row;
                }
            }
            let matching = if matching_radius == 3 {
                GRAPH33_MATCHINGS[active]
            } else {
                RADIUS2_MATCHINGS[active]
            };
            let mut matched = 0usize;
            for &code in &matching.edge_codes[..matching.count as usize] {
                let left_row = usize::from(code) / 12;
                let right_row = usize::from(code) % 12;
                let first = digits[left_row * 13 + column].unwrap();
                let second = digits[right_row * 13 + column].unwrap();
                let (edge_table, edge_index) = if matching_radius == 3 {
                    (graph33.unwrap(),
                     usize::from(GRAPH33_EDGE_SLOTS[left_row][right_row]))
                } else if right_row - left_row == 2 {
                    (distance_two.unwrap(), left_row)
                } else if left_row % 2 == 0 {
                    (pairs.unwrap(), left_row / 2)
                } else {
                    (odd_pairs.unwrap(), left_row / 2)
                };
                let addend = pair_comb13_point(edge_table, edge_index, first, second);
                add_comb13_digit(&mut point, &mut started, &mut orbit_counts, first, addend);
                matched |= (1 << left_row) | (1 << right_row);
                fusions += 1;
            }
            for row in 0..12 {
                if active & (1 << row) != 0 && matched & (1 << row) == 0 {
                    let digit = digits[row * 13 + column].unwrap();
                    let seed = table.full_rows[row][digit.orbit];
                    add_comb13_digit(&mut point, &mut started, &mut orbit_counts, digit, seed);
                }
            }
        } else {
            let mut row = 0;
            while row < 12 {
                let first = digits.get(row * 13 + column).copied().flatten();
                let second = (row < 11).then(|| {
                    digits.get((row + 1) * 13 + column).copied().flatten()
                }).flatten();
                if let (Some(first), Some(second)) = (first, second) {
                    if matching_radius == 1 || row % 2 == 0 {
                        let edge_table = if row % 2 == 0 { pairs.unwrap() } else { odd_pairs.unwrap() };
                        let addend = pair_comb13_point(edge_table, row / 2, first, second);
                        add_comb13_digit(&mut point, &mut started, &mut orbit_counts, first, addend);
                        fusions += 1;
                        row += 2;
                        continue;
                    }
                }
                if let Some(digit) = first {
                    let seed = table.full_rows[row][digit.orbit];
                    add_comb13_digit(&mut point, &mut started, &mut orbit_counts, digit, seed);
                }
                row += 1;
            }
        }
        if let Some(Some(digit)) = digits.get(12 * 13 + column) {
            if table.top_slots[digit.orbit] == u8::MAX {
                let (left_code, right_code) = table.top_repair[digit.orbit];
                assert_ne!((left_code, right_code), NO_TOP_REPAIR);
                for part in [left_code, right_code] {
                    let part = apply_width_six_unit(unpack_width_six_digit(part), digit.unit);
                    let seed = table.top_points[usize::from(table.top_slots[part.orbit])];
                    add_comb13_digit(&mut point, &mut started, &mut orbit_counts, part, seed);
                }
                repaired = true;
            } else {
                let seed = table.top_points[usize::from(table.top_slots[digit.orbit])];
                add_comb13_digit(&mut point, &mut started, &mut orbit_counts, *digit, seed);
            }
        }
    }
    (point, a, b, tau_steps, orbit_counts, repaired, fusions)
}

fn scalar_multiply_width_six_comb13_sparse(
    scalar: &BigInt,
) -> (Jacobian, BigInt, BigInt, usize, [usize; 81], bool) {
    let lattice = &*SCALAR_LATTICE;
    let residue = ((scalar % &lattice.n) + &lattice.n) % &lattice.n;
    let (a, b) = short_representative(&residue);
    let (mut digits, terminal) = recode_tau_width_six(a.clone(), b.clone());
    if let Some(digit) = terminal {
        digits.push(Some(digit));
    }
    evaluate_width_six_comb13_sparse(a, b, digits, false)
}

fn scalar_multiply_width_six_comb13_cover(
    scalar: &BigInt,
) -> (Jacobian, BigInt, BigInt, usize, [usize; 81], bool) {
    let lattice = &*SCALAR_LATTICE;
    let residue = ((scalar % &lattice.n) + &lattice.n) % &lattice.n;
    let (a, b) = short_representative(&residue);
    let (mut digits, terminal) = recode_tau_width_six(a.clone(), b.clone());
    if let Some(digit) = terminal {
        digits.push(Some(digit));
    }
    evaluate_width_six_comb13_sparse(a, b, digits, true)
}

fn scalar_multiply_width_six_comb13_cover25(
    scalar: &BigInt,
) -> (Jacobian, BigInt, BigInt, usize, [usize; 81], bool, usize, usize) {
    let lattice = &*SCALAR_LATTICE;
    let residue = ((scalar % &lattice.n) + &lattice.n) % &lattice.n;
    let table = &*WIDTH_SIX_COMB13_POINTS;
    let mut best: Option<(usize, usize, BigInt, BigInt, PackedTauSixStream)> = None;
    let mut valid = 0;
    for (rank, (a, b)) in short_representative_choices(&residue, 25).into_iter().enumerate() {
        let Some(stream) = recode_tau_width_six_packed(&a, &b) else { continue; };
        let Some(cost) = stream.cover_score(table) else { continue; };
        valid += 1;
        if best.as_ref().is_none_or(|entry| cost < entry.0) {
            best = Some((cost, rank, a, b, stream));
        }
    }
    let (_, rank, a, b, stream) = best.expect("nearest lattice representative is valid");
    let (point, a, b, tau_steps, orbit_counts, repaired) =
        evaluate_width_six_comb13_sparse(a, b, stream.digits(), true);
    (point, a, b, tau_steps, orbit_counts, repaired, rank, valid)
}

fn scalar_multiply_width_six_comb13_hex9(
    scalar: &BigInt,
) -> (Jacobian, BigInt, BigInt, usize, [usize; 81], bool, usize, usize) {
    let lattice = &*SCALAR_LATTICE;
    let residue = ((scalar % &lattice.n) + &lattice.n) % &lattice.n;
    let table = &*WIDTH_SIX_COMB13_POINTS;
    let mut best: Option<(usize, usize, BigInt, BigInt, PackedTauSixStream)> = None;
    let mut valid = 0;
    for (rank, (a, b)) in hexagonal_representative_choices(&residue).into_iter().enumerate() {
        let Some(stream) = recode_tau_width_six_packed(&a, &b) else { continue; };
        let Some(cost) = stream.cover_score(table) else { continue; };
        valid += 1;
        if best.as_ref().is_none_or(|entry| cost < entry.0) {
            best = Some((cost, rank, a, b, stream));
        }
    }
    let (_, rank, a, b, stream) = best.expect("nearest lattice representative is valid");
    let (point, a, b, tau_steps, orbit_counts, repaired) =
        evaluate_width_six_comb13_sparse(a, b, stream.digits(), true);
    (point, a, b, tau_steps, orbit_counts, repaired, rank, valid)
}

fn scalar_multiply_width_six_comb13_hex9_matched(
    scalar: &BigInt,
    matching_radius: u8,
    graph_aware: bool,
) -> (Jacobian, BigInt, BigInt, usize, [usize; 81], bool, usize, usize, usize) {
    assert!(!graph_aware || matching_radius == 3);
    let lattice = &*SCALAR_LATTICE;
    let residue = ((scalar % &lattice.n) + &lattice.n) % &lattice.n;
    let table = &*WIDTH_SIX_COMB13_POINTS;
    let mut best: Option<(usize, usize, BigInt, BigInt, PackedTauSixStream)> = None;
    let mut valid = 0;
    for (rank, (a, b)) in hexagonal_representative_choices(&residue).into_iter().enumerate() {
        let Some(stream) = recode_tau_width_six_packed(&a, &b) else { continue; };
        let Some(cost) = (if graph_aware { stream.graph33_score(table) }
                          else { stream.cover_score(table) }) else { continue; };
        valid += 1;
        if best.as_ref().is_none_or(|entry| cost < entry.0) {
            best = Some((cost, rank, a, b, stream));
        }
    }
    let (_, rank, a, b, stream) = best.expect("nearest lattice representative is valid");
    let (point, a, b, tau_steps, orbit_counts, repaired, fusions) =
        evaluate_width_six_comb13_matched(a, b, stream.digits(), matching_radius);
    (point, a, b, tau_steps, orbit_counts, repaired, rank, valid, fusions)
}

fn scalar_multiply_width_six_comb13_hex9_paired(
    scalar: &BigInt,
) -> (Jacobian, BigInt, BigInt, usize, [usize; 81], bool, usize, usize, usize) {
    scalar_multiply_width_six_comb13_hex9_matched(scalar, 0, false)
}

fn scalar_multiply_width_six_comb13_hex9_path(
    scalar: &BigInt,
) -> (Jacobian, BigInt, BigInt, usize, [usize; 81], bool, usize, usize, usize) {
    scalar_multiply_width_six_comb13_hex9_matched(scalar, 1, false)
}

fn scalar_multiply_width_six_comb13_hex9_radius2(
    scalar: &BigInt,
) -> (Jacobian, BigInt, BigInt, usize, [usize; 81], bool, usize, usize, usize) {
    scalar_multiply_width_six_comb13_hex9_matched(scalar, 2, false)
}

fn scalar_multiply_width_six_comb13_hex9_graph33(
    scalar: &BigInt,
) -> (Jacobian, BigInt, BigInt, usize, [usize; 81], bool, usize, usize, usize) {
    scalar_multiply_width_six_comb13_hex9_matched(scalar, 3, false)
}

fn scalar_multiply_width_six_comb13_hex9_graphaware33(
    scalar: &BigInt,
) -> (Jacobian, BigInt, BigInt, usize, [usize; 81], bool, usize, usize, usize) {
    scalar_multiply_width_six_comb13_hex9_matched(scalar, 3, true)
}

fn scalar_multiply_width_six_comb13_hex4(
    scalar: &BigInt,
) -> (Jacobian, BigInt, BigInt, usize, [usize; 81], bool, usize, usize) {
    let lattice = &*SCALAR_LATTICE;
    let residue = ((scalar % &lattice.n) + &lattice.n) % &lattice.n;
    let table = &*WIDTH_SIX_COMB13_POINTS;
    let mut best: Option<(usize, usize, BigInt, BigInt, PackedTauSixStream)> = None;
    let mut valid = 0;
    for (rank, (a, b)) in hexagonal_four_corner_choices(&residue).into_iter().enumerate() {
        let Some(stream) = recode_tau_width_six_packed(&a, &b) else { continue; };
        let Some(cost) = stream.cover_score(table) else { continue; };
        valid += 1;
        if best.as_ref().is_none_or(|entry| cost < entry.0) {
            best = Some((cost, rank, a, b, stream));
        }
    }
    let (_, rank, a, b, stream) = best.expect("nearest lattice representative is valid");
    let (point, a, b, tau_steps, orbit_counts, repaired) =
        evaluate_width_six_comb13_sparse(a, b, stream.digits(), true);
    (point, a, b, tau_steps, orbit_counts, repaired, rank, valid)
}

fn scalar_multiply_width_six_comb13_coset3(
    scalar: &BigInt,
) -> (Jacobian, BigInt, BigInt, usize, [usize; 81], bool, usize, usize) {
    let lattice = &*SCALAR_LATTICE;
    let residue = ((scalar % &lattice.n) + &lattice.n) % &lattice.n;
    let table = &*WIDTH_SIX_COMB13_POINTS;
    let mut best: Option<(usize, usize, BigInt, BigInt, Vec<Option<WidthSixDigit>>)> = None;
    let mut valid = 0;
    for (rank, (a, b)) in short_representative_choices(&residue, 3).into_iter().enumerate() {
        let (mut digits, terminal) = recode_tau_width_six(a.clone(), b.clone());
        if let Some(digit) = terminal {
            digits.push(Some(digit));
        }
        if let Some(cost) = width_six_comb13_sparse_score(&digits, table) {
            valid += 1;
            if best.as_ref().is_none_or(|entry| cost < entry.0) {
                best = Some((cost, rank, a, b, digits));
            }
        }
    }
    let (_, rank, a, b, digits) = best.expect("nearest lattice representative is valid");
    let (point, a, b, tau_steps, orbit_counts, fallback) =
        evaluate_width_six_comb13_sparse(a, b, digits, false);
    (point, a, b, tau_steps, orbit_counts, fallback, rank, valid)
}

fn scalar_multiply_glv_comb(
    scalar: &BigInt,
    rows: usize,
) -> (Jacobian, BigInt, BigInt, usize, usize) {
    let width = match rows {
        8 => 16,
        10 => 13,
        _ => panic!("unsupported GLV comb row count"),
    };
    let table = if rows == 8 {
        &*GLV_COMB8_POINTS
    } else {
        &*GLV_COMB10_POINTS
    };
    let lattice = &*SCALAR_LATTICE;
    let residue = ((scalar % &lattice.n) + &lattice.n) % &lattice.n;
    let (a, b) = short_representative(&residue);
    // tau = 1 - omega, hence a + b*tau = (a+b) - b*omega.
    let components = [&a + &b, -&b];
    let magnitudes: [u128; 2] = std::array::from_fn(|index| {
        let component = &components[index];
        component
            .abs()
            .to_u128()
            .expect("GLV components fit 128 bits")
    });
    let negative: [bool; 2] = std::array::from_fn(|index| components[index].is_negative());
    let mut point = Jacobian::identity();
    let mut started = false;
    let mut doublings = 0;
    let mut additions = 0;
    for column in (0..width).rev() {
        if started {
            point = point.double();
            doublings += 1;
        }
        for component in 0..2 {
            let mut mask = 0usize;
            for row in 0..rows {
                let position = row * width + column;
                if position < 128 && (magnitudes[component] >> position) & 1 != 0 {
                    mask |= 1 << row;
                }
            }
            if mask == 0 {
                continue;
            }
            let mut addend = table[mask];
            if component == 1 {
                addend = addend.omega();
            }
            if negative[component] {
                addend = addend.neg();
            }
            if started {
                point = point.add_mixed(addend);
                additions += 1;
            } else {
                point = addend;
                started = true;
            }
        }
    }
    (point, a, b, doublings, additions)
}

fn check_generator_case(
    fixture_path: &str,
    index: usize,
    timed: bool,
    width_three: bool,
    affine_fixed: bool,
    redundant_four: bool,
    coalescent_four: bool,
    width_six: bool,
    comb_rows: usize,
    glv_rows: usize,
    coset_three: bool,
    cover_top: bool,
    cover_twentyfive: bool,
    hex_nine: bool,
    hex_four: bool,
    hex_nine_paired: bool,
    hex_nine_path: bool,
    hex_nine_radius2: bool,
    hex_nine_graph33: bool,
    hex_nine_graphaware33: bool,
    unit_orbit_format: u8,
) {
    let fixture: Value = serde_json::from_slice(&fs::read(fixture_path).expect("read fixture"))
        .expect("parse fixture");
    assert_eq!(fixture["schema"].as_u64(), Some(1));
    let case = &fixture["cases"].as_array().expect("cases")[index];
    let base_x = case["base_x_hex"].as_str().expect("base x");
    let base_y = case["base_y_hex"].as_str().expect("base y");
    assert_eq!(base_x, GENERATOR_X_HEX);
    assert_eq!(base_y, GENERATOR_Y_HEX);
    let scalar_hex = case["scalar_hex"].as_str().expect("scalar");
    let expected = if case["expected_identity"].as_bool() == Some(true) {
        "identity".to_owned()
    } else {
        format!(
            "{}:{}",
            case["expected_x_hex"].as_str().expect("expected x"),
            case["expected_y_hex"].as_str().expect("expected y")
        )
    };
    let preparation_start = Instant::now();
    LazyLock::force(&SCALAR_LATTICE);
    LazyLock::force(&DECODE_CONSTANTS);
    if unit_orbit_format == 123 { LazyLock::force(&HYBRID_FIELD); }
    let retained_bytes = if unit_orbit_format != 0 {
        unit_orbit_windows::warm_format(unit_orbit_format % 100)
    } else {
        0
    };
    if redundant_four || coalescent_four {
        LazyLock::force(&WIDTH_FOUR_DIGITS);
        LazyLock::force(&WIDTH_FOUR_POINTS);
    }
    if width_six {
        LazyLock::force(&WIDTH_SIX_DIGITS);
        LazyLock::force(&WIDTH_SIX_POINTS);
    }
    if comb_rows != 0 {
        LazyLock::force(&WIDTH_SIX_DIGITS);
        match comb_rows {
            4 => { LazyLock::force(&WIDTH_SIX_COMB4_POINTS); }
            8 => { LazyLock::force(&WIDTH_SIX_COMB8_POINTS); }
            12 => { LazyLock::force(&WIDTH_SIX_COMB12_POINTS); }
            13 => { LazyLock::force(&WIDTH_SIX_COMB13_POINTS); }
            _ => unreachable!(),
        };
    }
    if hex_nine_paired || hex_nine_path || hex_nine_radius2 {
        LazyLock::force(&PAIR_COMB13_POINTS);
    }
    if hex_nine_path || hex_nine_radius2 {
        LazyLock::force(&ODD_PAIR_COMB13_POINTS);
    }
    if hex_nine_radius2 {
        LazyLock::force(&DISTANCE_TWO_PAIR_COMB13_POINTS);
        LazyLock::force(&RADIUS2_MATCHINGS);
    }
    if hex_nine_graph33 || hex_nine_graphaware33 {
        LazyLock::force(&GRAPH33_PAIR_COMB13_POINTS);
        LazyLock::force(&GRAPH33_MATCHINGS);
    }
    if glv_rows == 8 {
        LazyLock::force(&GLV_COMB8_POINTS);
    } else if glv_rows == 10 {
        LazyLock::force(&GLV_COMB10_POINTS);
    }
    let scalar = scalar_from_hex(scalar_hex);
    let preparation_ms = preparation_start.elapsed().as_secs_f64() * 1000.0;
    let start = Instant::now();
    let point = if unit_orbit_format >= 100 {
        unit_orbit_windows::multiply_word_format(&scalar, unit_orbit_format % 100).0
    } else if unit_orbit_format != 0 {
        unit_orbit_windows::multiply_format(&scalar, unit_orbit_format).0
    } else if hex_nine_graphaware33 {
        scalar_multiply_width_six_comb13_hex9_graphaware33(&scalar).0
    } else if hex_nine_graph33 {
        scalar_multiply_width_six_comb13_hex9_graph33(&scalar).0
    } else if hex_nine_radius2 {
        scalar_multiply_width_six_comb13_hex9_radius2(&scalar).0
    } else if hex_nine_path {
        scalar_multiply_width_six_comb13_hex9_path(&scalar).0
    } else if hex_nine_paired {
        scalar_multiply_width_six_comb13_hex9_paired(&scalar).0
    } else if hex_four {
        scalar_multiply_width_six_comb13_hex4(&scalar).0
    } else if hex_nine {
        scalar_multiply_width_six_comb13_hex9(&scalar).0
    } else if cover_twentyfive {
        scalar_multiply_width_six_comb13_cover25(&scalar).0
    } else if cover_top {
        scalar_multiply_width_six_comb13_cover(&scalar).0
    } else if coset_three {
        scalar_multiply_width_six_comb13_coset3(&scalar).0
    } else if glv_rows != 0 {
        scalar_multiply_glv_comb(&scalar, glv_rows).0
    } else if comb_rows == 13 {
        scalar_multiply_width_six_comb13_sparse(&scalar).0
    } else if comb_rows != 0 {
        scalar_multiply_width_six_comb(&scalar, comb_rows).0
    } else if width_six {
        scalar_multiply_width_six(&scalar).0
    } else if redundant_four || coalescent_four {
        scalar_multiply_width_four_redundant(&scalar, coalescent_four).0
    } else if width_three {
        scalar_multiply_width_three(&scalar, affine_fixed).0
    } else {
        scalar_multiply_width_two(&scalar).0
    };
    let actual = if unit_orbit_format == 123 {
        point.affine_hex_hybrid()
    } else {
        point.affine_hex()
    };
    assert_eq!(actual, expected, "benchmark output mismatch");
    let elapsed_ms = start.elapsed().as_secs_f64() * 1000.0;
    let mode = if unit_orbit_format == 123 {
        "unit_orbit_hybrid14_fixed"
    } else if unit_orbit_format == 122 {
        "unit_orbit_fixed_limb14_fixed"
    } else if unit_orbit_format == 121 {
        "unit_orbit_certified14_fixed"
    } else if unit_orbit_format == 120 {
        "unit_orbit_reciprocal14_fixed"
    } else if unit_orbit_format == 119 {
        "unit_orbit_staged14_fixed"
    } else if unit_orbit_format == 118 {
        "unit_orbit_tau_pair_fixed"
    } else if unit_orbit_format == 117 {
        "unit_orbit_tau_bucket_fixed"
    } else if unit_orbit_format == 113 {
        "unit_orbit_word943_fixed"
    } else if unit_orbit_format == 114 {
        "unit_orbit_word14_fixed"
    } else if unit_orbit_format == 115 {
        "unit_orbit_word15_fixed"
    } else if unit_orbit_format == 116 {
        "unit_orbit_word16_fixed"
    } else if unit_orbit_format == 13 {
        "unit_orbit_radix943_fixed"
    } else if unit_orbit_format == 14 {
        "unit_orbit_windows14_fixed"
    } else if unit_orbit_format == 15 {
        "unit_orbit_windows15_fixed"
    } else if unit_orbit_format == 16 {
        "unit_orbit_windows16_fixed"
    } else if hex_nine_graphaware33 {
        "eisenstein_w6_comb13_hex9_graphaware33_fixed"
    } else if hex_nine_graph33 {
        "eisenstein_w6_comb13_hex9_graph33_fixed"
    } else if hex_nine_radius2 {
        "eisenstein_w6_comb13_hex9_radius2_fixed"
    } else if hex_nine_path {
        "eisenstein_w6_comb13_hex9_path_fixed"
    } else if hex_nine_paired {
        "eisenstein_w6_comb13_hex9_paired_fixed"
    } else if hex_four {
        "eisenstein_w6_comb13_hex4_fixed"
    } else if hex_nine {
        "eisenstein_w6_comb13_hex9_fixed"
    } else if cover_twentyfive {
        "eisenstein_w6_comb13_cover25_fixed"
    } else if cover_top {
        "eisenstein_w6_comb13_cover_fixed"
    } else if coset_three {
        "eisenstein_w6_comb13_coset3_fixed"
    } else if glv_rows == 8 {
        "glv_comb8_fixed"
    } else if glv_rows == 10 {
        "glv_comb10_fixed"
    } else if comb_rows == 4 {
        "eisenstein_w6_comb4_fixed"
    } else if comb_rows == 8 {
        "eisenstein_w6_comb8_fixed"
    } else if comb_rows == 12 {
        "eisenstein_w6_comb12_fixed"
    } else if comb_rows == 13 {
        "eisenstein_w6_comb13_sparse_fixed"
    } else if width_six {
        "eisenstein_w6_fixed"
    } else if coalescent_four {
        "eisenstein_w4_coalescent"
    } else if redundant_four {
        "eisenstein_w4_redundant"
    } else if affine_fixed {
        "eisenstein_w3_fixed"
    } else if width_three {
        "eisenstein_w3"
    } else {
        "eisenstein_w2"
    };
    if timed && unit_orbit_format != 0 {
        println!("online_ms={elapsed_ms:.6} preparation_ms={preparation_ms:.6} retained_bytes={retained_bytes} verified=1 curve=secp256k1 base_x={base_x} base_y={base_y} scalar={scalar_hex} point={actual} mode={mode}");
    } else if timed {
        println!("online_ms={elapsed_ms:.6} verified=1 curve=secp256k1 base_x={base_x} base_y={base_y} scalar={scalar_hex} point={actual} mode={mode}");
    } else {
        println!("verified=1 curve=secp256k1 base_x={base_x} base_y={base_y} scalar={scalar_hex} point={actual} mode={mode}");
    }
}

fn check_all_unit_orbit_fixture_cases(fixture_path: &str, format: u8, timed: bool) {
    let fixture: Value = serde_json::from_slice(&fs::read(fixture_path).expect("read fixture"))
        .expect("parse fixture");
    let count = fixture["cases"].as_array().expect("cases").len();
    unit_orbit_windows::warm_format(format % 100);
    for index in 0..count {
        check_generator_case(
            fixture_path, index, timed, false, false, false, false, false, 0, 0, false,
            false, false, false, false, false, false, false, false, false, format,
        );
    }
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.len() == 2
        && (args[0].starts_with("--check-scalar-unit-orbit-windows")
            || args[0].starts_with("--benchmark-scalar-unit-orbit-windows")
            || args[0].starts_with("--check-scalar-unit-orbit-word")
            || args[0].starts_with("--benchmark-scalar-unit-orbit-word")
            || args[0].starts_with("--check-scalar-unit-orbit-tau-bucket")
            || args[0].starts_with("--benchmark-scalar-unit-orbit-tau-bucket")
            || args[0].starts_with("--check-scalar-unit-orbit-tau-pair")
            || args[0].starts_with("--benchmark-scalar-unit-orbit-tau-pair")
            || args[0].starts_with("--check-scalar-unit-orbit-staged")
            || args[0].starts_with("--benchmark-scalar-unit-orbit-staged")
            || args[0].starts_with("--check-scalar-unit-orbit-reciprocal")
            || args[0].starts_with("--benchmark-scalar-unit-orbit-reciprocal")
            || args[0].starts_with("--check-scalar-unit-orbit-certified")
            || args[0].starts_with("--benchmark-scalar-unit-orbit-certified")
            || args[0].starts_with("--check-scalar-unit-orbit-fixed-limb")
            || args[0].starts_with("--benchmark-scalar-unit-orbit-fixed-limb")
            || args[0].starts_with("--check-scalar-unit-orbit-hybrid")
            || args[0].starts_with("--benchmark-scalar-unit-orbit-hybrid")
            || args[0].starts_with("--check-scalar-unit-orbit-radix943")
            || args[0].starts_with("--benchmark-scalar-unit-orbit-radix943"))
        && args[0].ends_with("-fixed-fixture")
    {
        let format = if args[0].contains("unit-orbit-hybrid-fixed-fixture") {
            123
        } else if args[0].contains("unit-orbit-fixed-limb-fixed-fixture") {
            122
        } else if args[0].contains("unit-orbit-certified-fixed-fixture") {
            121
        } else if args[0].contains("unit-orbit-reciprocal-fixed-fixture") {
            120
        } else if args[0].contains("unit-orbit-staged-fixed-fixture") {
            119
        } else if args[0].contains("unit-orbit-tau-pair-fixed-fixture") {
            118
        } else if args[0].contains("unit-orbit-tau-bucket-fixed-fixture") {
            117
        } else if args[0].contains("unit-orbit-word943-fixed-fixture") {
            113
        } else if args[0].contains("unit-orbit-radix943-fixed-fixture") {
            13
        } else if args[0].contains("unit-orbit-word14-fixed-fixture") {
            114
        } else if args[0].contains("unit-orbit-word15-fixed-fixture") {
            115
        } else if args[0].contains("unit-orbit-word16-fixed-fixture") {
            116
        } else if args[0].contains("unit-orbit-windows14-fixed-fixture") {
            14
        } else if args[0].contains("unit-orbit-windows15-fixed-fixture") {
            15
        } else if args[0].contains("unit-orbit-windows16-fixed-fixture") {
            16
        } else {
            panic!("unsupported unit-orbit fixture mode")
        };
        check_all_unit_orbit_fixture_cases(&args[1], format, args[0].starts_with("--benchmark-"));
        return;
    }
    if args == ["--prepare-w6-comb13-hex9-paired"] {
        let start = Instant::now();
        let pairs = &*PAIR_COMB13_POINTS;
        println!("preparation_ms={:.6} entries={} table_bytes={}",
                 start.elapsed().as_secs_f64() * 1000.0,
                 pairs.rows.iter().map(|row| row.len()).sum::<usize>(),
                 pairs.rows.iter().map(|row| row.len()).sum::<usize>()
                     * std::mem::size_of::<CompactPairPoint>());
        return;
    }
    if args == ["--prepare-w6-comb13-hex9-path"] {
        let start = Instant::now();
        let even = &*PAIR_COMB13_POINTS;
        let odd = &*ODD_PAIR_COMB13_POINTS;
        let entries = even.rows.iter().chain(odd.rows.iter())
            .map(|row| row.len()).sum::<usize>();
        println!("preparation_ms={:.6} entries={} table_bytes={}",
                 start.elapsed().as_secs_f64() * 1000.0,
                 entries, entries * std::mem::size_of::<CompactPairPoint>());
        return;
    }
    if args == ["--prepare-w6-comb13-hex9-radius2"] {
        let start = Instant::now();
        let even = &*PAIR_COMB13_POINTS;
        let odd = &*ODD_PAIR_COMB13_POINTS;
        let distant = &*DISTANCE_TWO_PAIR_COMB13_POINTS;
        LazyLock::force(&RADIUS2_MATCHINGS);
        let entries = even.rows.iter().chain(odd.rows.iter()).chain(distant.rows.iter())
            .map(|row| row.len()).sum::<usize>();
        println!("preparation_ms={:.6} entries={} table_bytes={} atlas_bytes={}",
                 start.elapsed().as_secs_f64() * 1000.0,
                 entries, entries * std::mem::size_of::<CompactPairPoint>(),
                 RADIUS2_MATCHINGS.len() * std::mem::size_of::<RowMatching>());
        return;
    }
    if args == ["--prepare-w6-comb13-hex9-graph33"] {
        let start = Instant::now();
        let pairs = &*GRAPH33_PAIR_COMB13_POINTS;
        LazyLock::force(&GRAPH33_MATCHINGS);
        let entries = pairs.rows.iter().map(|row| row.len()).sum::<usize>();
        println!("preparation_ms={:.6} entries={} table_bytes={} atlas_bytes={}",
                 start.elapsed().as_secs_f64() * 1000.0, entries,
                 entries * std::mem::size_of::<CompactPairPoint>(),
                 GRAPH33_MATCHINGS.len() * std::mem::size_of::<RowMatching>());
        return;
    }
    if args.len() == 3
        && (args[0] == "--benchmark-scalar-w2-case"
            || args[0] == "--check-scalar-w2-case"
            || args[0] == "--benchmark-scalar-w3-case"
            || args[0] == "--check-scalar-w3-case"
            || args[0] == "--benchmark-scalar-w3-fixed-case"
            || args[0] == "--check-scalar-w3-fixed-case"
            || args[0] == "--benchmark-scalar-w4-redundant-case"
            || args[0] == "--check-scalar-w4-redundant-case"
            || args[0] == "--benchmark-scalar-w4-coalescent-case"
            || args[0] == "--check-scalar-w4-coalescent-case"
            || args[0] == "--benchmark-scalar-w6-fixed-case"
            || args[0] == "--check-scalar-w6-fixed-case"
            || args[0] == "--benchmark-scalar-w6-comb4-fixed-case"
            || args[0] == "--check-scalar-w6-comb4-fixed-case"
            || args[0] == "--benchmark-scalar-w6-comb8-fixed-case"
            || args[0] == "--check-scalar-w6-comb8-fixed-case"
            || args[0] == "--benchmark-scalar-w6-comb12-fixed-case"
            || args[0] == "--check-scalar-w6-comb12-fixed-case"
            || args[0] == "--benchmark-scalar-w6-comb13-sparse-fixed-case"
            || args[0] == "--check-scalar-w6-comb13-sparse-fixed-case"
            || args[0] == "--benchmark-scalar-w6-comb13-coset3-fixed-case"
            || args[0] == "--check-scalar-w6-comb13-coset3-fixed-case"
            || args[0] == "--benchmark-scalar-w6-comb13-cover-fixed-case"
            || args[0] == "--check-scalar-w6-comb13-cover-fixed-case"
            || args[0] == "--benchmark-scalar-w6-comb13-cover25-fixed-case"
            || args[0] == "--check-scalar-w6-comb13-cover25-fixed-case"
            || args[0] == "--benchmark-scalar-w6-comb13-hex9-fixed-case"
            || args[0] == "--check-scalar-w6-comb13-hex9-fixed-case"
            || args[0] == "--benchmark-scalar-w6-comb13-hex9-paired-fixed-case"
            || args[0] == "--check-scalar-w6-comb13-hex9-paired-fixed-case"
            || args[0] == "--benchmark-scalar-w6-comb13-hex9-path-fixed-case"
            || args[0] == "--check-scalar-w6-comb13-hex9-path-fixed-case"
            || args[0] == "--benchmark-scalar-w6-comb13-hex9-radius2-fixed-case"
            || args[0] == "--check-scalar-w6-comb13-hex9-radius2-fixed-case"
            || args[0] == "--benchmark-scalar-w6-comb13-hex9-graph33-fixed-case"
            || args[0] == "--check-scalar-w6-comb13-hex9-graph33-fixed-case"
            || args[0] == "--benchmark-scalar-w6-comb13-hex9-graphaware33-fixed-case"
            || args[0] == "--check-scalar-w6-comb13-hex9-graphaware33-fixed-case"
            || args[0] == "--benchmark-scalar-w6-comb13-hex4-fixed-case"
            || args[0] == "--check-scalar-w6-comb13-hex4-fixed-case"
            || args[0] == "--benchmark-scalar-glv-comb8-fixed-case"
            || args[0] == "--check-scalar-glv-comb8-fixed-case"
            || args[0] == "--benchmark-scalar-glv-comb10-fixed-case"
            || args[0] == "--check-scalar-glv-comb10-fixed-case"
            || args[0] == "--benchmark-scalar-unit-orbit-windows14-fixed-case"
            || args[0] == "--check-scalar-unit-orbit-windows14-fixed-case"
            || args[0] == "--benchmark-scalar-unit-orbit-windows15-fixed-case"
            || args[0] == "--check-scalar-unit-orbit-windows15-fixed-case"
            || args[0] == "--benchmark-scalar-unit-orbit-windows16-fixed-case"
            || args[0] == "--check-scalar-unit-orbit-windows16-fixed-case"
            || args[0] == "--benchmark-scalar-unit-orbit-word14-fixed-case"
            || args[0] == "--check-scalar-unit-orbit-word14-fixed-case"
            || args[0] == "--benchmark-scalar-unit-orbit-word15-fixed-case"
            || args[0] == "--check-scalar-unit-orbit-word15-fixed-case"
            || args[0] == "--benchmark-scalar-unit-orbit-word16-fixed-case"
            || args[0] == "--check-scalar-unit-orbit-word16-fixed-case"
            || args[0] == "--benchmark-scalar-unit-orbit-word943-fixed-case"
            || args[0] == "--check-scalar-unit-orbit-word943-fixed-case"
            || args[0] == "--benchmark-scalar-unit-orbit-tau-bucket-fixed-case"
            || args[0] == "--check-scalar-unit-orbit-tau-bucket-fixed-case"
            || args[0] == "--benchmark-scalar-unit-orbit-tau-pair-fixed-case"
            || args[0] == "--check-scalar-unit-orbit-tau-pair-fixed-case"
            || args[0] == "--benchmark-scalar-unit-orbit-staged-fixed-case"
            || args[0] == "--check-scalar-unit-orbit-staged-fixed-case"
            || args[0] == "--benchmark-scalar-unit-orbit-reciprocal-fixed-case"
            || args[0] == "--check-scalar-unit-orbit-reciprocal-fixed-case"
            || args[0] == "--benchmark-scalar-unit-orbit-certified-fixed-case"
            || args[0] == "--check-scalar-unit-orbit-certified-fixed-case"
            || args[0] == "--benchmark-scalar-unit-orbit-fixed-limb-fixed-case"
            || args[0] == "--check-scalar-unit-orbit-fixed-limb-fixed-case"
            || args[0] == "--benchmark-scalar-unit-orbit-hybrid-fixed-case"
            || args[0] == "--check-scalar-unit-orbit-hybrid-fixed-case"
            || args[0] == "--benchmark-scalar-unit-orbit-radix943-fixed-case"
            || args[0] == "--check-scalar-unit-orbit-radix943-fixed-case")
    {
        let index = args[2].parse::<usize>().expect("case index");
        check_generator_case(
            &args[1],
            index,
            args[0].starts_with("--benchmark-"),
            args[0].contains("w3-"),
            args[0].ends_with("w3-fixed-case"),
            args[0].ends_with("w4-redundant-case"),
            args[0].ends_with("w4-coalescent-case"),
            args[0].ends_with("w6-fixed-case"),
            if args[0].contains("w6-comb4") {
                4
            } else if args[0].contains("w6-comb8") {
                8
            } else if args[0].contains("w6-comb12") {
                12
            } else if args[0].contains("w6-comb13") {
                13
            } else {
                0
            },
            if args[0].contains("glv-comb8") {
                8
            } else if args[0].contains("glv-comb10") {
                10
            } else {
                0
            },
            args[0].contains("w6-comb13-coset3"),
            args[0].contains("w6-comb13-cover-fixed"),
            args[0].contains("w6-comb13-cover25"),
            args[0].contains("w6-comb13-hex9"),
            args[0].contains("w6-comb13-hex4"),
            args[0].contains("w6-comb13-hex9-paired"),
            args[0].contains("w6-comb13-hex9-path"),
            args[0].contains("w6-comb13-hex9-radius2"),
            args[0].contains("w6-comb13-hex9-graph33"),
            args[0].contains("w6-comb13-hex9-graphaware33"),
            if args[0].contains("unit-orbit-hybrid") {
                123
            } else if args[0].contains("unit-orbit-fixed-limb") {
                122
            } else if args[0].contains("unit-orbit-certified") {
                121
            } else if args[0].contains("unit-orbit-reciprocal") {
                120
            } else if args[0].contains("unit-orbit-staged") {
                119
            } else if args[0].contains("unit-orbit-tau-pair") {
                118
            } else if args[0].contains("unit-orbit-tau-bucket") {
                117
            } else if args[0].contains("unit-orbit-word943") {
                113
            } else if args[0].contains("unit-orbit-radix943") {
                13
            } else if args[0].contains("unit-orbit-word14") {
                114
            } else if args[0].contains("unit-orbit-word15") {
                115
            } else if args[0].contains("unit-orbit-word16") {
                116
            } else if args[0].contains("unit-orbit-windows14") {
                14
            } else if args[0].contains("unit-orbit-windows15") {
                15
            } else if args[0].contains("unit-orbit-windows16") {
                16
            } else {
                0
            },
        );
        return;
    }
    assert!(
        args.is_empty()
            || args == ["--tau"]
            || args == ["--scalar"]
            || args == ["--scalar-w2"]
            || args == ["--scalar-w3"]
            || args == ["--scalar-w3-fixed"]
            || args == ["--scalar-w4-redundant"]
            || args == ["--scalar-w4-coalescent"]
            || args == ["--scalar-w6-fixed"]
            || args == ["--scalar-w6-comb4-fixed"]
            || args == ["--scalar-w6-comb8-fixed"]
            || args == ["--scalar-w6-comb12-fixed"]
            || args == ["--scalar-w6-comb13-sparse-fixed"]
            || args == ["--scalar-w6-comb13-coset3-fixed"]
            || args == ["--scalar-w6-comb13-cover-fixed"]
            || args == ["--scalar-w6-comb13-cover25-fixed"]
            || args == ["--scalar-w6-comb13-hex9-fixed"]
            || args == ["--scalar-w6-comb13-hex9-paired-fixed"]
            || args == ["--scalar-w6-comb13-hex9-path-fixed"]
            || args == ["--scalar-w6-comb13-hex9-radius2-fixed"]
            || args == ["--scalar-w6-comb13-hex9-graph33-fixed"]
            || args == ["--scalar-w6-comb13-hex9-graphaware33-fixed"]
            || args == ["--scalar-unit-orbit-windows-fixed"]
            || args == ["--scalar-unit-orbit-windows15-fixed"]
            || args == ["--scalar-unit-orbit-windows16-fixed"]
            || args == ["--scalar-unit-orbit-radix943-fixed"]
            || args == ["--scalar-w6-comb13-hex4-fixed"]
            || args == ["--scalar-glv-comb8-fixed"]
            || args == ["--scalar-glv-comb10-fixed"],
        "usage: eisenstein_fixed [--tau|--scalar|--scalar-w2|--scalar-w3|--scalar-w3-fixed|--scalar-w4-redundant|--scalar-w4-coalescent|--scalar-w6-fixed|--scalar-w6-comb4-fixed|--scalar-w6-comb8-fixed|--scalar-w6-comb12-fixed|--scalar-w6-comb13-sparse-fixed|--scalar-w6-comb13-coset3-fixed|--scalar-w6-comb13-cover-fixed|--scalar-w6-comb13-cover25-fixed|--scalar-w6-comb13-hex4-fixed|--scalar-w6-comb13-hex9-fixed|--scalar-w6-comb13-hex9-paired-fixed|--scalar-unit-orbit-windows-fixed|--scalar-unit-orbit-windows15-fixed|--scalar-unit-orbit-windows16-fixed|--scalar-glv-comb8-fixed|--scalar-glv-comb10-fixed]"
    );
    let tau_mode = args == ["--tau"];
    let scalar_mode = args == ["--scalar"]
        || args == ["--scalar-w2"]
        || args == ["--scalar-w3"]
        || args == ["--scalar-w3-fixed"]
        || args == ["--scalar-w4-redundant"]
        || args == ["--scalar-w4-coalescent"]
        || args == ["--scalar-w6-fixed"]
        || args == ["--scalar-w6-comb4-fixed"]
        || args == ["--scalar-w6-comb8-fixed"]
        || args == ["--scalar-w6-comb12-fixed"]
        || args == ["--scalar-w6-comb13-sparse-fixed"]
        || args == ["--scalar-w6-comb13-coset3-fixed"]
        || args == ["--scalar-w6-comb13-cover-fixed"]
        || args == ["--scalar-w6-comb13-cover25-fixed"]
        || args == ["--scalar-w6-comb13-hex9-fixed"]
        || args == ["--scalar-w6-comb13-hex9-paired-fixed"]
        || args == ["--scalar-w6-comb13-hex9-path-fixed"]
        || args == ["--scalar-w6-comb13-hex9-radius2-fixed"]
        || args == ["--scalar-w6-comb13-hex9-graph33-fixed"]
        || args == ["--scalar-w6-comb13-hex9-graphaware33-fixed"]
        || args == ["--scalar-unit-orbit-windows-fixed"]
        || args == ["--scalar-unit-orbit-windows15-fixed"]
        || args == ["--scalar-unit-orbit-windows16-fixed"]
        || args == ["--scalar-unit-orbit-radix943-fixed"]
        || args == ["--scalar-w6-comb13-hex4-fixed"]
        || args == ["--scalar-glv-comb8-fixed"]
        || args == ["--scalar-glv-comb10-fixed"];
    let width_two = args == ["--scalar-w2"];
    let affine_fixed = args == ["--scalar-w3-fixed"];
    let width_three = args == ["--scalar-w3"] || affine_fixed;
    let redundant_four = args == ["--scalar-w4-redundant"];
    let coalescent_four = args == ["--scalar-w4-coalescent"];
    let width_six = args == ["--scalar-w6-fixed"];
    let comb_rows = if args == ["--scalar-w6-comb4-fixed"] {
        4
    } else if args == ["--scalar-w6-comb8-fixed"] {
        8
    } else if args == ["--scalar-w6-comb12-fixed"] {
        12
    } else if args == ["--scalar-w6-comb13-sparse-fixed"] || args == ["--scalar-w6-comb13-coset3-fixed"] || args == ["--scalar-w6-comb13-cover-fixed"] || args == ["--scalar-w6-comb13-cover25-fixed"] || args == ["--scalar-w6-comb13-hex9-fixed"] || args == ["--scalar-w6-comb13-hex9-paired-fixed"] || args == ["--scalar-w6-comb13-hex9-path-fixed"] || args == ["--scalar-w6-comb13-hex9-radius2-fixed"] || args == ["--scalar-w6-comb13-hex9-graph33-fixed"] || args == ["--scalar-w6-comb13-hex9-graphaware33-fixed"] || args == ["--scalar-w6-comb13-hex4-fixed"] {
        13
    } else {
        0
    };
    let glv_rows = if args == ["--scalar-glv-comb8-fixed"] {
        8
    } else if args == ["--scalar-glv-comb10-fixed"] {
        10
    } else {
        0
    };
    let unit_orbit_format = if args == ["--scalar-unit-orbit-radix943-fixed"] {
        13
    } else if args == ["--scalar-unit-orbit-windows-fixed"] {
        14
    } else if args == ["--scalar-unit-orbit-windows15-fixed"] {
        15
    } else if args == ["--scalar-unit-orbit-windows16-fixed"] {
        16
    } else {
        0
    };
    if unit_orbit_format != 0 {
        unit_orbit_windows::warm_format(unit_orbit_format);
    }
    for line in io::stdin().lock().lines() {
        let line = line.expect("input line");
        if line.trim().is_empty() {
            continue;
        }
        let fields: Vec<&str> = line.split_whitespace().collect();
        if scalar_mode {
            assert_eq!(fields.len(), 1, "expected one hexadecimal scalar");
            let scalar = scalar_from_hex(fields[0]);
            if unit_orbit_format != 0 {
                let (point, a, b, additions, retained_bytes) =
                    unit_orbit_windows::multiply_format(&scalar, unit_orbit_format);
                println!("{}", json!({
                    "point": if point.is_identity() { None } else { Some(point.strings()) },
                    "representative": [a.to_string(), b.to_string()],
                    "tau_steps": 0,
                    "nonzero_digits": additions,
                    "retained_bytes": retained_bytes,
                    "radix": if unit_orbit_format == 13 { "unit-orbit-radix943-fixed" }
                        else if unit_orbit_format == 14 { "unit-orbit-windows-fixed" }
                        else if unit_orbit_format == 15 { "unit-orbit-windows15-fixed" }
                        else { "unit-orbit-windows16-fixed" },
                }));
                continue;
            }
            if glv_rows != 0 {
                let (point, a, b, doublings, additions) =
                    scalar_multiply_glv_comb(&scalar, glv_rows);
                println!(
                    "{}",
                    json!({
                        "point": if point.is_identity() { None } else { Some(point.strings()) },
                        "representative": [a.to_string(), b.to_string()],
                        "glv_components": [(&a + &b).to_string(), (-&b).to_string()],
                        "doublings": doublings,
                        "tau_steps": 0,
                        "nonzero_digits": additions,
                        "radix": if glv_rows == 8 { "glv-comb8-fixed" } else { "glv-comb10-fixed" },
                    })
                );
                continue;
            }
            let (
                point,
                a,
                b,
                tau_steps,
                nonzero_digits,
                orbit_counts,
                alternate_uses,
                recoding_work,
            ) = if args == ["--scalar-w6-comb13-hex9-graphaware33-fixed"] || args == ["--scalar-w6-comb13-hex9-graph33-fixed"] || args == ["--scalar-w6-comb13-hex9-radius2-fixed"] || args == ["--scalar-w6-comb13-hex9-path-fixed"] || args == ["--scalar-w6-comb13-hex9-paired-fixed"] {
                let (point, a, b, tau_steps, orbit_counts, repaired, rank, valid, fusions) =
                    scalar_multiply_width_six_comb13_hex9_matched(
                        &scalar, if args == ["--scalar-w6-comb13-hex9-graphaware33-fixed"] || args == ["--scalar-w6-comb13-hex9-graph33-fixed"] { 3 }
                                 else if args == ["--scalar-w6-comb13-hex9-radius2-fixed"] { 2 }
                                 else if args == ["--scalar-w6-comb13-hex9-path-fixed"] { 1 }
                                 else { 0 },
                        args == ["--scalar-w6-comb13-hex9-graphaware33-fixed"]);
                (point, a, b, tau_steps, orbit_counts.iter().sum(),
                 Some(json!(orbit_counts.to_vec())), None,
                 Some(json!({"top_repaired": repaired, "coset_rank": rank,
                             "valid_representatives": valid, "attempted_representatives": 9,
                             "pair_fusions": fusions})))
            } else if args == ["--scalar-w6-comb13-hex4-fixed"] {
                let (point, a, b, tau_steps, orbit_counts, repaired, rank, valid) =
                    scalar_multiply_width_six_comb13_hex4(&scalar);
                (point, a, b, tau_steps, orbit_counts.iter().sum(),
                 Some(json!(orbit_counts.to_vec())), None,
                 Some(json!({"top_repaired": repaired, "coset_rank": rank,
                             "valid_representatives": valid, "attempted_representatives": 4})))
            } else if args == ["--scalar-w6-comb13-hex9-fixed"] {
                let (point, a, b, tau_steps, orbit_counts, repaired, rank, valid) =
                    scalar_multiply_width_six_comb13_hex9(&scalar);
                (point, a, b, tau_steps, orbit_counts.iter().sum(),
                 Some(json!(orbit_counts.to_vec())), None,
                 Some(json!({"top_repaired": repaired, "coset_rank": rank,
                             "valid_representatives": valid, "attempted_representatives": 9})))
            } else if args == ["--scalar-w6-comb13-cover25-fixed"] {
                let (point, a, b, tau_steps, orbit_counts, repaired, rank, valid) =
                    scalar_multiply_width_six_comb13_cover25(&scalar);
                (point, a, b, tau_steps, orbit_counts.iter().sum(),
                 Some(json!(orbit_counts.to_vec())), None,
                 Some(json!({"top_repaired": repaired, "coset_rank": rank,
                             "valid_representatives": valid, "attempted_representatives": 25})))
            } else if args == ["--scalar-w6-comb13-cover-fixed"] {
                let (point, a, b, tau_steps, orbit_counts, repaired) =
                    scalar_multiply_width_six_comb13_cover(&scalar);
                (
                    point,
                    a,
                    b,
                    tau_steps,
                    orbit_counts.iter().sum(),
                    Some(json!(orbit_counts.to_vec())),
                    None,
                    Some(json!({"top_repaired": repaired})),
                )
            } else if args == ["--scalar-w6-comb13-coset3-fixed"] {
                let (point, a, b, tau_steps, orbit_counts, fallback, rank, valid) =
                    scalar_multiply_width_six_comb13_coset3(&scalar);
                (
                    point,
                    a,
                    b,
                    tau_steps,
                    orbit_counts.iter().sum(),
                    Some(json!(orbit_counts.to_vec())),
                    None,
                    Some(json!({"sparse_fallback": fallback, "coset_rank": rank,
                                "valid_representatives": valid, "attempted_representatives": 3})),
                )
            } else if comb_rows == 13 {
                let (point, a, b, tau_steps, orbit_counts, fallback) =
                    scalar_multiply_width_six_comb13_sparse(&scalar);
                (
                    point,
                    a,
                    b,
                    tau_steps,
                    orbit_counts.iter().sum(),
                    Some(json!(orbit_counts.to_vec())),
                    None,
                    Some(json!({"sparse_fallback": fallback})),
                )
            } else if comb_rows != 0 {
                let (point, a, b, tau_steps, orbit_counts) =
                    scalar_multiply_width_six_comb(&scalar, comb_rows);
                (
                    point,
                    a,
                    b,
                    tau_steps,
                    orbit_counts.iter().sum(),
                    Some(json!(orbit_counts.to_vec())),
                    None,
                    None,
                )
            } else if width_six {
                let (point, a, b, tau_steps, orbit_counts) = scalar_multiply_width_six(&scalar);
                (
                    point,
                    a,
                    b,
                    tau_steps,
                    orbit_counts.iter().sum(),
                    Some(json!(orbit_counts.to_vec())),
                    None,
                    None,
                )
            } else if redundant_four || coalescent_four {
                let (point, a, b, tau_steps, orbit_counts, alternate_uses, work) =
                    scalar_multiply_width_four_redundant(&scalar, coalescent_four);
                (
                    point,
                    a,
                    b,
                    tau_steps,
                    orbit_counts.iter().sum(),
                    Some(json!(orbit_counts)),
                    Some(alternate_uses),
                    coalescent_four.then(|| {
                        json!({
                            "base_transitions": work.base_transitions,
                            "look_zero_steps": work.look_zero_steps,
                            "look_blocks": work.look_blocks,
                        })
                    }),
                )
            } else if width_three {
                let (point, a, b, tau_steps, orbit_counts) =
                    scalar_multiply_width_three(&scalar, affine_fixed);
                (
                    point,
                    a,
                    b,
                    tau_steps,
                    orbit_counts.iter().sum(),
                    Some(json!(orbit_counts)),
                    None,
                    None,
                )
            } else if width_two {
                let (point, a, b, tau_steps, nonzero_digits) = scalar_multiply_width_two(&scalar);
                (point, a, b, tau_steps, nonzero_digits, None, None, None)
            } else {
                let (point, a, b, tau_steps, nonzero_digits) = scalar_multiply(&scalar);
                (point, a, b, tau_steps, nonzero_digits, None, None, None)
            };
            println!(
                "{}",
                json!({
                    "point": if point.is_identity() { None } else { Some(point.strings()) },
                    "representative": [a.to_string(), b.to_string()],
                    "tau_steps": tau_steps,
                    "nonzero_digits": nonzero_digits,
                    "orbit_counts": orbit_counts,
                    "alternate_uses": alternate_uses,
                    "recoding_work": recoding_work,
                    "radix": if args == ["--scalar-w6-comb13-hex9-graphaware33-fixed"] { "orbit-w6-comb13-hex9-graphaware33-fixed" } else if args == ["--scalar-w6-comb13-hex9-graph33-fixed"] { "orbit-w6-comb13-hex9-graph33-fixed" } else if args == ["--scalar-w6-comb13-hex9-radius2-fixed"] { "orbit-w6-comb13-hex9-radius2-fixed" } else if args == ["--scalar-w6-comb13-hex9-path-fixed"] { "orbit-w6-comb13-hex9-path-fixed" } else if args == ["--scalar-w6-comb13-hex9-paired-fixed"] { "orbit-w6-comb13-hex9-paired-fixed" } else if args == ["--scalar-w6-comb13-hex4-fixed"] { "orbit-w6-comb13-hex4-fixed" } else if args == ["--scalar-w6-comb13-hex9-fixed"] { "orbit-w6-comb13-hex9-fixed" } else if args == ["--scalar-w6-comb13-cover25-fixed"] { "orbit-w6-comb13-cover25-fixed" } else if args == ["--scalar-w6-comb13-cover-fixed"] { "orbit-w6-comb13-cover-fixed" } else if args == ["--scalar-w6-comb13-coset3-fixed"] { "orbit-w6-comb13-coset3-fixed" } else if comb_rows == 4 { "orbit-w6-comb4-fixed" } else if comb_rows == 8 { "orbit-w6-comb8-fixed" } else if comb_rows == 12 { "orbit-w6-comb12-fixed" } else if comb_rows == 13 { "orbit-w6-comb13-sparse-fixed" } else if width_six { "orbit-w6-fixed" } else if coalescent_four { "orbit-w4-coalescent" } else if redundant_four { "orbit-w4-redundant" } else if affine_fixed { "orbit-w3-fixed" } else if width_three { "orbit-w3" } else if width_two { "unit-w2" } else { "signed-w1" },
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
    use num_bigint::BigUint;
    use num_integer::Integer;

    #[test]
    fn inversion_chain_and_affine_output_match_generator() {
        let generator = Jacobian::generator();
        assert_eq!(
            generator.affine_hex(),
            format!("{GENERATOR_X_HEX}:{GENERATOR_Y_HEX}")
        );
        for value in [generator.x, generator.y, generator.z] {
            assert_eq!(
                value.mul(value.invert_chain()).strings(),
                Pair::one().strings()
            );
        }
    }

    #[test]
    fn fixed_width_three_affine_seeds_match_projective_construction() {
        let generator = Jacobian::generator();
        let doubled = generator.double();
        let degree_seven = doubled.add_mixed(generator.omega().neg());
        let fixed_doubled = Jacobian::generator_double_affine();
        let fixed_degree_seven = Jacobian::generator_degree_seven_affine();
        assert!(same_point(doubled, fixed_doubled));
        assert!(same_point(degree_seven, fixed_degree_seven));
        assert_eq!(
            fixed_doubled.affine_hex(),
            concat!(
                "c6047f9441ed7d6d3045406e95c07cd85c778e4b8cef3ca7abac09b95c709ee5:",
                "1ae168fea63dc339a3c58419466ceaeef7f632653266d0e1236431a950cfe52a"
            )
        );
        assert_eq!(
            fixed_degree_seven.affine_hex(),
            concat!(
                "213ac9c75608233a9b7752aa91dc05355faf26913c5ce5b580610a0b6dcdcc9b:",
                "e2f2b16e9b1b736e2ef0ed95c84cadf3d2a4daa70efe4b15974e0dce288c3b8a"
            )
        );
    }

    #[test]
    fn rectangular_limb_products_match_big_integers_at_boundaries() {
        fn signed(value: &BigUint, negative: bool) -> Signed {
            Signed {
                negative,
                magnitude: U512::from_biguint(value),
            }
            .normalized()
        }
        let two_limbs = [
            BigUint::from(0u8),
            BigUint::from(1u8),
            (BigUint::from(1u8) << 64) - 1u8,
            (BigUint::from(1u8) << 128) - 1u8,
        ];
        let three_limbs = [
            BigUint::from(0u8),
            BigUint::from(1u8) << 128,
            (BigUint::from(1u8) << 133) - 1u8,
            (BigUint::from(1u8) << 192) - 1u8,
        ];
        for left in two_limbs.iter().chain(three_limbs.iter()) {
            for right in &two_limbs {
                for left_negative in [false, true] {
                    for right_negative in [false, true] {
                        let got = signed(left, left_negative)
                            .mul_rect::<3, 2>(signed(right, right_negative));
                        let mut expected = BigInt::from_biguint(Sign::Plus, left * right);
                        if left_negative ^ right_negative {
                            expected = -expected;
                        }
                        assert_eq!(got.decimal(), expected.to_string());
                    }
                }
            }
        }
        for left in &two_limbs {
            for right in &two_limbs {
                let got = signed(left, false).mul_rect::<2, 2>(signed(right, false));
                assert_eq!(got.decimal(), (left * right).to_string());
            }
        }
    }

    #[test]
    fn carry_bit_products_and_fixed_conjugate_match_big_integers() {
        fn signed(value: &BigUint, negative: bool) -> Signed {
            Signed {
                negative,
                magnitude: U512::from_biguint(value),
            }
            .normalized()
        }
        let radix: BigUint = BigUint::from(1u8) << 128usize;
        let sums = [
            BigUint::from(0u8),
            BigUint::from(1u8),
            &radix - 1u8,
            radix.clone(),
            &radix + 1u8,
            (&radix << 1) - 1u8,
        ];
        for left in &sums {
            for right in &sums {
                for left_negative in [false, true] {
                    for right_negative in [false, true] {
                        let got = signed(left, left_negative)
                            .mul_two_small_tops(signed(right, right_negative));
                        let mut expected = BigInt::from_biguint(Sign::Plus, left * right);
                        if left_negative ^ right_negative {
                            expected = -expected;
                        }
                        assert_eq!(got.decimal(), expected.to_string());
                    }
                }
            }
        }
        let wide = [
            BigUint::from(0u8),
            BigUint::from(1u8),
            &radix - 1u8,
            radix.clone(),
            (BigUint::from(1u8) << 154) - 1u8,
        ];
        let right = [
            BigUint::from(0u8),
            &radix - 1u8,
            radix.clone(),
            (&radix << 1) - 1u8,
            &radix << 1,
            (&radix * 3u8) - 1u8,
        ];
        for left in &wide {
            for right in &right {
                for left_negative in [false, true] {
                    for right_negative in [false, true] {
                        let got = signed(left, left_negative)
                            .mul_right_small_top::<3>(signed(right, right_negative), 2);
                        let mut expected = BigInt::from_biguint(Sign::Plus, left * right);
                        if left_negative ^ right_negative {
                            expected = -expected;
                        }
                        assert_eq!(got.decimal(), expected.to_string());
                    }
                }
            }
        }
        let pi = Pair::pi();
        let conjugate_pi = Pair {
            a: pi.a.sub(pi.b),
            b: pi.b.neg(),
        };
        for (a, b) in [
            (signed(&wide[4], false), signed(&wide[4], true)),
            (signed(&wide[4], true), signed(&radix, false)),
            (Signed::ZERO, signed(&wide[3], true)),
        ] {
            let value = Pair { a, b };
            assert_eq!(
                value.product_conjugate_pi().strings(),
                value.product(conjugate_pi).strings()
            );
        }
    }

    #[test]
    fn wide_add_output_balances_large_lattice_offsets() {
        let base = Pair::one();
        let pi = Pair::pi();
        for (a, b) in [
            (0, 0),
            (1, -1),
            (12_673_653, 0),
            (0, -12_673_653),
            (12_673_653, -12_673_653),
            (-12_673_653, 12_673_653),
        ] {
            let shifted = base.add(Pair::small_pi_multiple(a, b, pi));
            assert_eq!(shifted.balance_add_output().strings(), base.strings());
        }
    }

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
        let doubled = generator.double();
        let z2 = doubled.z.mul(doubled.z);
        let z3 = z2.mul(doubled.z);
        assert!(same_point(
            Jacobian::identity().add_cached(doubled, z2, z3),
            doubled
        ));
        assert!(same_point(
            doubled.add_cached(doubled, z2, z3),
            doubled.double()
        ));
        assert!(doubled.add_cached(doubled.neg(), z2, z3).is_identity());
        assert!(same_point(
            generator.add_cached(doubled, z2, z3),
            doubled.add_mixed(generator)
        ));
    }

    #[test]
    fn width_three_digits_cover_residues_and_reconstruct_small_pairs() {
        for a in -40..=40 {
            for b in -40..=40 {
                let (digits, terminal) = recode_tau_width_three(a.into(), b.into());
                for adjacent in digits.windows(3) {
                    assert!(
                        adjacent[0].is_none() || (adjacent[1].is_none() && adjacent[2].is_none())
                    );
                }
                let (mut x, mut y) = terminal.map_or((0i64, 0i64), |d| {
                    let (x, y) = d.coefficients();
                    (i64::from(x), i64::from(y))
                });
                for digit in digits.into_iter().rev() {
                    let (da, db) = digit.map_or((0, 0), WidthThreeDigit::coefficients);
                    (x, y) = (-3 * y + i64::from(da), x + 3 * y + i64::from(db));
                }
                assert_eq!((x, y), (a, b));
            }
        }
    }

    #[test]
    fn redundant_width_four_digits_reconstruct_small_pairs() {
        for a in -12..=12 {
            for b in -12..=12 {
                let (digits, terminal, alternate_uses, _) =
                    recode_tau_width_four_redundant(a.into(), b.into(), true);
                for chunk in digits.windows(4) {
                    if chunk[0].is_some() {
                        assert!(chunk[1..].iter().all(Option::is_none));
                    }
                }
                assert_eq!(
                    alternate_uses,
                    digits.iter().flatten().filter(|d| d.orbit >= 9).count()
                );
                let (mut x, mut y) = terminal.map_or((0i64, 0i64), |d| {
                    let (x, y) = d.coefficients();
                    (i64::from(x), i64::from(y))
                });
                for digit in digits.into_iter().rev() {
                    let (da, db) = digit.map_or((0, 0), WidthFourDigit::coefficients);
                    (x, y) = (-3 * y + i64::from(da), x + 3 * y + i64::from(db));
                }
                assert_eq!((x, y), (a, b));
            }
        }
    }

    #[test]
    fn coalescent_comparison_matches_full_continuation_on_small_pairs() {
        fn base_cost(mut z: EisensteinState) -> i64 {
            let mut cost = 0;
            while !width_four_is_terminal(&z) {
                if let Some(choices) = width_four_choices(&z.0, &z.1) {
                    z = width_four_block_quotient(&z.0, &z.1, choices[0]);
                    cost += 31;
                } else {
                    z = width_four_zero_quotient(&z.0, &z.1);
                    cost += 5;
                }
            }
            cost
        }
        fn one_block_cost(mut z: EisensteinState) -> i64 {
            let mut prefix = 0;
            while !width_four_is_terminal(&z) && mod_three(&z.0) == 0 {
                z = width_four_zero_quotient(&z.0, &z.1);
                prefix += 5;
            }
            if width_four_is_terminal(&z) {
                return prefix;
            }
            prefix
                + 31
                + width_four_choices(&z.0, &z.1)
                    .expect("nonterminal block")
                    .map(|digit| base_cost(width_four_block_quotient(&z.0, &z.1, digit)))
                    .into_iter()
                    .min()
                    .unwrap()
        }
        let sample = [-8, -4, -1, 0, 1, 3, 7];
        for &a in &sample {
            for &b in &sample {
                for &c in &sample {
                    for &d in &sample {
                        let left = (BigInt::from(a), BigInt::from(b));
                        let right = (BigInt::from(c), BigInt::from(d));
                        assert_eq!(
                            WidthFourComparator::default().base_delta(left.clone(), right.clone()),
                            base_cost(left) - base_cost(right)
                        );
                    }
                }
            }
        }
        for a in -12..=12 {
            for b in -12..=12 {
                let z = (BigInt::from(a), BigInt::from(b));
                if width_four_is_terminal(&z) {
                    continue;
                }
                if let Some(choices) = width_four_choices(&z.0, &z.1) {
                    let quotients = choices.map(|d| width_four_block_quotient(&z.0, &z.1, d));
                    let values = quotients.clone().map(one_block_cost);
                    assert_eq!(
                        WidthFourComparator::default().choose(quotients),
                        usize::from(values[1] < values[0]),
                        "state ({a},{b})"
                    );
                }
            }
        }
    }

    #[test]
    fn redundant_width_four_affine_table_matches_independent_scalar_path() {
        for (index, &(a, b)) in WIDTH_FOUR_SEEDS.iter().enumerate() {
            let scalar = BigInt::from(a) + BigInt::from(b) * &SCALAR_LATTICE.lambda_tau;
            assert!(same_point(
                WIDTH_FOUR_POINTS[index][0],
                scalar_multiply(&scalar).0
            ));
        }
    }

    #[test]
    fn width_six_seeds_match_frozen_atlas_and_reconstruct_small_pairs() {
        let record: Value = serde_json::from_str(include_str!("../../width6-tau-result.json"))
            .expect("frozen width-six result");
        let saved = record["width_six_seeds"].as_array().expect("seed array");
        assert_eq!(saved.len(), 81);
        for (index, &(a, b)) in WIDTH_SIX_SEEDS.iter().enumerate() {
            assert_eq!(saved[index][0].as_i64(), Some(i64::from(a)));
            assert_eq!(saved[index][1].as_i64(), Some(i64::from(b)));
        }
        for a in -12..=12 {
            for b in -12..=12 {
                let (digits, terminal) = recode_tau_width_six(a.into(), b.into());
                for window in digits.windows(6) {
                    if window[0].is_some() {
                        assert!(window[1..].iter().all(Option::is_none));
                    }
                }
                let (mut x, mut y) = terminal.map_or((0i64, 0i64), |d| {
                    let (x, y) = d.coefficients();
                    (i64::from(x), i64::from(y))
                });
                for digit in digits.into_iter().rev() {
                    let (da, db) = digit.map_or((0, 0), WidthSixDigit::coefficients);
                    (x, y) = (-3 * y + i64::from(da), x + 3 * y + i64::from(db));
                }
                assert_eq!((x, y), (a, b));
            }
        }
    }

    #[test]
    fn width_six_batch_affine_table_matches_independent_scalar_path() {
        for (index, &(a, b)) in WIDTH_SIX_SEEDS.iter().enumerate() {
            let scalar = BigInt::from(a) + BigInt::from(b) * &SCALAR_LATTICE.lambda_tau;
            assert!(same_point(
                WIDTH_SIX_POINTS[index][0],
                scalar_multiply(&scalar).0
            ));
        }
    }

    #[test]
    fn width_six_comb_shifted_tables_match_tau_images() {
        for (rows, width, tables) in [
            (4, 41, &*WIDTH_SIX_COMB4_POINTS),
            (8, 21, &*WIDTH_SIX_COMB8_POINTS),
            (12, 14, &*WIDTH_SIX_COMB12_POINTS),
        ] {
            assert_eq!(tables.len(), rows);
            for row in 0..rows {
                for seed in [0, 1, 17, 40, 80] {
                    let mut expected = WIDTH_SIX_POINTS[seed][0];
                    for _ in 0..row * width {
                        expected = expected.tau();
                    }
                    assert!(
                        same_point(tables[row][seed], expected),
                        "rows={rows} row={row} seed={seed}"
                    );
                }
            }
        }
    }

    #[test]
    fn sparse_comb13_reuses_1024_points_and_verifies_fallback() {
        let table = &*WIDTH_SIX_COMB13_POINTS;
        assert_eq!(table.full_rows.len() * 81 + table.top_points.len(), 1024);
        let selected = scalar_multiply_width_six_comb13_sparse(&BigInt::from(1));
        assert!(!selected.5);
        assert!(same_point(selected.0, Jacobian::generator()));
        let scalar = BigInt::parse_bytes(
            b"291a4b1cec292deb928a94385017b681693459cc424b1a9be19f9511ff968bc7",
            16,
        )
        .expect("frozen sparse miss scalar");
        let fallback = scalar_multiply_width_six_comb13_sparse(&scalar);
        assert!(fallback.5);
        assert!(same_point(fallback.0, scalar_multiply(&scalar).0));
    }

    #[test]
    fn additive_top_cover_reconstructs_every_missing_orbit() {
        let table = &*WIDTH_SIX_COMB13_POINTS;
        assert_eq!(table.full_rows.len() * 81 + table.top_points.len(), 1024);
        assert_eq!(std::mem::size_of_val(&table.top_repair), 324);
        let mut repaired_digits = 0;
        for digit in WIDTH_SIX_DIGITS.iter().flatten() {
            if table.top_slots[digit.orbit] != u8::MAX {
                continue;
            }
            let (left_code, right_code) = table.top_repair[digit.orbit];
            assert_ne!((left_code, right_code), NO_TOP_REPAIR);
            let left = apply_width_six_unit(unpack_width_six_digit(left_code), digit.unit);
            let right = apply_width_six_unit(unpack_width_six_digit(right_code), digit.unit);
            let (a, b) = digit.coefficients();
            assert!(table.top_slots[left.orbit] != u8::MAX);
            assert!(table.top_slots[right.orbit] != u8::MAX);
            let (la, lb) = left.coefficients();
            let (ra, rb) = right.coefficients();
            assert_eq!((i16::from(la) + i16::from(ra),
                        i16::from(lb) + i16::from(rb)),
                       (i16::from(a), i16::from(b)));
            repaired_digits += 1;
        }
        assert_eq!(repaired_digits, 174);
        let scalar = BigInt::parse_bytes(
            b"291a4b1cec292deb928a94385017b681693459cc424b1a9be19f9511ff968bc7",
            16,
        ).unwrap();
        let original = scalar_multiply_width_six_comb13_sparse(&scalar);
        let covered = scalar_multiply_width_six_comb13_cover(&scalar);
        assert!(original.5 && covered.5);
        assert!(same_point(original.0, covered.0));
        assert!(same_point(covered.0, scalar_multiply(&scalar).0));
        assert!(covered.3 <= 12);
    }

    #[test]
    fn fixed_width_tau_recode_matches_bigint_for_nearby_cosets() {
        for value in -100i64..=100 {
            let fixed = Signed192::from_bigint(&BigInt::from(value));
            assert_eq!(fixed.rem_euclid_small(3), value.rem_euclid(3) as u8);
            assert_eq!(fixed.rem_euclid_small(27), value.rem_euclid(27) as u8);
            for offset in [-37i64, 0, 43] {
                assert_eq!(fixed.add(Signed192::from_bigint(&BigInt::from(offset))),
                           Signed192::from_bigint(&BigInt::from(value + offset)));
            }
            if value % 27 == 0 {
                assert_eq!(fixed.div_exact_small(27),
                           Signed192::from_bigint(&BigInt::from(value / 27)));
            }
        }
        let n = SCALAR_LATTICE.n.clone();
        let miss = scalar_from_hex("291a4b1cec292deb928a94385017b681693459cc424b1a9be19f9511ff968bc7");
        for scalar in [BigInt::ZERO, BigInt::from(1), n.clone() - 1,
                       BigInt::from(1) << 255, miss] {
            let residue = ((&scalar % &n) + &n) % &n;
            for (a, b) in short_representative_choices(&residue, 25) {
                let (mut original, terminal) = recode_tau_width_six(a.clone(), b.clone());
                if let Some(digit) = terminal { original.push(Some(digit)); }
                let packed = recode_tau_width_six_packed(&a, &b);
                if original.len() > 162 {
                    assert!(packed.is_none());
                } else {
                    let packed = packed.expect("fitting stream");
                    let codes: Vec<_> = original.iter().map(|digit| {
                        digit.map_or(u16::MAX, pack_width_six_digit)
                    }).collect();
                    assert_eq!(&packed.codes[..packed.len], codes);
                }
            }
            let chosen = scalar_multiply_width_six_comb13_cover25(&scalar);
            let nearest = scalar_multiply_width_six_comb13_cover(&scalar);
            assert!(same_point(chosen.0, nearest.0));
            assert!(chosen.6 < 25 && (1..=25).contains(&chosen.7));
            let chosen_cost = 5 * chosen.3 + 11 * chosen.4.iter().sum::<usize>();
            let nearest_cost = 5 * nearest.3 + 11 * nearest.4.iter().sum::<usize>();
            assert!(chosen_cost <= nearest_cost);
        }
    }

    #[test]
    fn hexagonal_four_corners_contain_nearest_and_hex9_preserves_points() {
        use num_integer::Integer;
        let lattice = &*SCALAR_LATTICE;
        let w0 = &lattice.u0 - 2 * &lattice.v0;
        let w1 = &lattice.u1 - 2 * &lattice.v1;
        assert_eq!(tau_norm(&w0, &w1), lattice.n);
        assert_eq!(tau_norm(&lattice.v0, &lattice.v1), lattice.n);
        let w_plus_v = (&w0 + &lattice.v0, &w1 + &lattice.v1);
        assert_eq!(tau_norm(&w_plus_v.0, &w_plus_v.1), lattice.n);
        for scalar in [BigInt::ZERO, BigInt::from(1), &lattice.n - 1,
                       BigInt::from(1) << 255,
                       scalar_from_hex("291a4b1cec292deb928a94385017b681693459cc424b1a9be19f9511ff968bc7")] {
            let residue = ((&scalar % &lattice.n) + &lattice.n) % &lattice.n;
            let floor_w = (&residue * &lattice.v1).div_floor(&lattice.n);
            let floor_v = (-&residue * &w1).div_floor(&lattice.n);
            let old_nearest = short_representative(&residue);
            let corner_norm = (0..=1).flat_map(|di| (0..=1).map(move |dj| (di, dj)))
                .map(|(di, dj)| {
                    let i = &floor_w + di;
                    let j = &floor_v + dj;
                    let a = &residue - &i * &w0 - &j * &lattice.v0;
                    let b = -&i * &w1 - &j * &lattice.v1;
                    tau_norm(&a, &b)
                }).min().unwrap();
            assert_eq!(corner_norm, tau_norm(&old_nearest.0, &old_nearest.1));
            assert_eq!(hexagonal_four_corner_choices(&residue).len(), 4);
            assert_eq!(tau_norm(&hexagonal_four_corner_choices(&residue)[0].0,
                                &hexagonal_four_corner_choices(&residue)[0].1), corner_norm);
            assert_eq!(hexagonal_representative_choices(&residue).len(), 9);
            let four = scalar_multiply_width_six_comb13_hex4(&scalar);
            let chosen = scalar_multiply_width_six_comb13_hex9(&scalar);
            let nearest = scalar_multiply_width_six_comb13_cover(&scalar);
            assert!(same_point(four.0, nearest.0));
            assert!(same_point(chosen.0, nearest.0));
            assert!(four.6 < 4 && (1..=4).contains(&four.7));
            assert!(chosen.6 < 9 && (1..=9).contains(&chosen.7));
            assert!(5 * four.3 + 11 * four.4.iter().sum::<usize>()
                    <= 5 * nearest.3 + 11 * nearest.4.iter().sum::<usize>());
            assert!(5 * chosen.3 + 11 * chosen.4.iter().sum::<usize>()
                    <= 5 * four.3 + 11 * four.4.iter().sum::<usize>());
            assert!(5 * chosen.3 + 11 * chosen.4.iter().sum::<usize>()
                    <= 5 * nearest.3 + 11 * nearest.4.iter().sum::<usize>());
        }
    }

    #[test]
    fn incremental_hex_grid_matches_naive_candidates() {
        use num_integer::Integer;
        let lattice = &*SCALAR_LATTICE;
        let w0 = &lattice.u0 - 2 * &lattice.v0;
        let w1: BigInt = &lattice.u1 - 2 * &lattice.v1;
        let mut state = 0x9e3779b97f4a7c15u64;
        for _ in 0..128 {
            let mut scalar = BigInt::ZERO;
            for _ in 0..4 {
                state ^= state << 13;
                state ^= state >> 7;
                state ^= state << 17;
                scalar = (scalar << 64) + BigInt::from(state);
            }
            let scalar = scalar % &lattice.n;
            for side in [2, 3] {
                let (first_w, first_v) = if side == 2 {
                    ((&scalar * &lattice.v1).div_floor(&lattice.n),
                     (-(&scalar * &w1)).div_floor(&lattice.n))
                } else {
                    (round_div(&scalar * &lattice.v1, lattice.det.clone()) - 1,
                     round_div(-&scalar * &w1, lattice.det.clone()) - 1)
                };
                let mut naive = Vec::new();
                for dw in 0..side {
                    for dv in 0..side {
                        let i = &first_w + dw;
                        let j = &first_v + dv;
                        let a = &scalar - &i * &w0 - &j * &lattice.v0;
                        let b = -&i * &w1 - &j * &lattice.v1;
                        naive.push((tau_norm(&a, &b), std::cmp::max(a.abs(), b.abs()), a, b));
                    }
                }
                naive.sort();
                let expected: Vec<_> = naive.into_iter().map(|(_, _, a, b)| (a, b)).collect();
                let actual = if side == 2 {
                    hexagonal_four_corner_choices(&scalar)
                } else {
                    hexagonal_representative_choices(&scalar)
                };
                assert_eq!(actual, expected);
            }
        }
    }

    #[test]
    fn orbit_pair_comb_matches_direct_sums_and_hex9_points() {
        let pair_table = &*PAIR_COMB13_POINTS;
        let base = &*WIDTH_SIX_COMB13_POINTS;
        assert_eq!(std::mem::size_of::<CompactPairPoint>(), 72);
        assert_eq!(pair_table.rows.len(), 6);
        assert!(pair_table.rows.iter().all(|row| row.len() == PAIR_COMB13_ENTRIES_PER_PAIR));
        for pair in 0..6 {
            for first_orbit in [0, 40, 80] {
                for second_orbit in [0, 40, 80] {
                    let first = WidthSixDigit { orbit: first_orbit,
                        unit: Unit { sign: -1, omega_power: 2 } };
                    for second_power in 0..3 {
                        for second_sign in [1, -1] {
                            let second = WidthSixDigit { orbit: second_orbit,
                                unit: Unit { sign: second_sign, omega_power: second_power } };
                            let direct = width_six_unit_image(base.full_rows[2 * pair][first_orbit], first)
                                .add_mixed(width_six_unit_image(base.full_rows[2 * pair + 1][second_orbit], second));
                            let paired = width_six_unit_image(pair_comb13_point(pair_table, pair, first, second), first);
                            assert_eq!(direct.affine_hex(), paired.affine_hex());
                        }
                    }
                }
            }
        }
        let n = SCALAR_LATTICE.n.clone();
        let mut state = 0x8a5cd7890f2b34d1u64;
        for scalar in [BigInt::ZERO, BigInt::from(1), &n - 1]
            .into_iter().chain((0..16).map(|_| {
                let mut value = BigInt::ZERO;
                for _ in 0..4 {
                    state ^= state << 13;
                    state ^= state >> 7;
                    state ^= state << 17;
                    value = (value << 64) + BigInt::from(state);
                }
                value % &n
            })) {
            let old = scalar_multiply_width_six_comb13_hex9(&scalar);
            let new = scalar_multiply_width_six_comb13_hex9_paired(&scalar);
            assert_eq!(old.0.affine_hex(), new.0.affine_hex());
            assert_eq!((&old.1, &old.2, old.3, old.5, old.6, old.7),
                       (&new.1, &new.2, new.3, new.5, new.6, new.7));
            assert_eq!(old.4.iter().sum::<usize>(), new.4.iter().sum::<usize>() + new.8);
        }
    }

    #[test]
    fn adaptive_path_pairs_match_direct_sums_and_fixed_pair_points() {
        let odd = &*ODD_PAIR_COMB13_POINTS;
        let base = &*WIDTH_SIX_COMB13_POINTS;
        assert_eq!(odd.rows.len(), 5);
        assert!(odd.rows.iter().all(|row| row.len() == PAIR_COMB13_ENTRIES_PER_PAIR));
        for pair in 0..5 {
            for first_orbit in [0, 40, 80] {
                for second_orbit in [0, 40, 80] {
                    let first = WidthSixDigit { orbit: first_orbit,
                        unit: Unit { sign: -1, omega_power: 2 } };
                    for second_power in 0..3 {
                        for second_sign in [1, -1] {
                            let second = WidthSixDigit { orbit: second_orbit,
                                unit: Unit { sign: second_sign, omega_power: second_power } };
                            let direct = width_six_unit_image(base.full_rows[2 * pair + 1][first_orbit], first)
                                .add_mixed(width_six_unit_image(base.full_rows[2 * pair + 2][second_orbit], second));
                            let paired = width_six_unit_image(pair_comb13_point(odd, pair, first, second), first);
                            assert_eq!(direct.affine_hex(), paired.affine_hex());
                        }
                    }
                }
            }
        }
        let n = SCALAR_LATTICE.n.clone();
        let mut state = 0x7e4a91b2c3d4e5f6u64;
        for scalar in [BigInt::ZERO, BigInt::from(1), &n - 1, n.clone() + 1]
            .into_iter().chain((0..16).map(|_| {
                let mut value = BigInt::ZERO;
                for _ in 0..4 {
                    state ^= state << 13;
                    state ^= state >> 7;
                    state ^= state << 17;
                    value = (value << 64) + BigInt::from(state);
                }
                value % &n
            })) {
            let old = scalar_multiply_width_six_comb13_hex9_paired(&scalar);
            let new = scalar_multiply_width_six_comb13_hex9_path(&scalar);
            assert_eq!(old.0.affine_hex(), new.0.affine_hex());
            assert_eq!((&old.1, &old.2, old.3, old.5, old.6, old.7),
                       (&new.1, &new.2, new.3, new.5, new.6, new.7));
            assert!(new.8 >= old.8);
            assert_eq!(old.4.iter().sum::<usize>() + old.8,
                       new.4.iter().sum::<usize>() + new.8);
        }
    }

    #[test]
    fn radius_two_atlas_and_pair_tables_match_direct_group_sums() {
        let atlas = &*RADIUS2_MATCHINGS;
        assert_eq!(atlas.len(), 1 << 12);
        assert_eq!(std::mem::size_of::<RowMatching>(), 7);
        for (mask, entry) in atlas.iter().enumerate() {
            let mut used = 0usize;
            for &code in &entry.edge_codes[..entry.count as usize] {
                let left = usize::from(code) / 12;
                let right = usize::from(code) % 12;
                assert!(left < right && right - left <= 2);
                let bits = (1 << left) | (1 << right);
                assert_eq!(mask & bits, bits);
                assert_eq!(used & bits, 0);
                used |= bits;
            }
            assert!(usize::from(entry.count) <= mask.count_ones() as usize / 2);
        }
        let distant = &*DISTANCE_TWO_PAIR_COMB13_POINTS;
        let base = &*WIDTH_SIX_COMB13_POINTS;
        assert_eq!(distant.rows.len(), 10);
        assert!(distant.rows.iter().all(|row| row.len() == PAIR_COMB13_ENTRIES_PER_PAIR));
        for row in 0..10 {
            for first_orbit in [0, 40, 80] {
                for second_orbit in [0, 40, 80] {
                    let first = WidthSixDigit { orbit: first_orbit,
                        unit: Unit { sign: -1, omega_power: 2 } };
                    for second_power in 0..3 {
                        for second_sign in [1, -1] {
                            let second = WidthSixDigit { orbit: second_orbit,
                                unit: Unit { sign: second_sign, omega_power: second_power } };
                            let direct = width_six_unit_image(base.full_rows[row][first_orbit], first)
                                .add_mixed(width_six_unit_image(base.full_rows[row + 2][second_orbit], second));
                            let paired = width_six_unit_image(pair_comb13_point(distant, row, first, second), first);
                            assert_eq!(direct.affine_hex(), paired.affine_hex());
                        }
                    }
                }
            }
        }
        let n = SCALAR_LATTICE.n.clone();
        for scalar in [BigInt::ZERO, BigInt::from(1), &n - 1, n + 1] {
            let old = scalar_multiply_width_six_comb13_hex9_path(&scalar);
            let new = scalar_multiply_width_six_comb13_hex9_radius2(&scalar);
            assert_eq!(old.0.affine_hex(), new.0.affine_hex());
            assert_eq!((&old.1, &old.2, old.3, old.5, old.6, old.7),
                       (&new.1, &new.2, new.3, new.5, new.6, new.7));
            assert!(new.8 >= old.8);
            assert_eq!(old.4.iter().sum::<usize>() + old.8,
                       new.4.iter().sum::<usize>() + new.8);
        }
    }

    #[test]
    fn balanced_graph33_tables_and_matching_preserve_points() {
        assert_eq!(std::mem::size_of::<CompactPairPoint>(), 72);
        let atlas = &*GRAPH33_MATCHINGS;
        let slots = &*GRAPH33_EDGE_SLOTS;
        assert_eq!(atlas.len(), 1 << 12);
        assert_eq!(GRAPH33_EDGES.len(), 33);
        for (mask, entry) in atlas.iter().enumerate() {
            let mut used = 0usize;
            for &code in &entry.edge_codes[..entry.count as usize] {
                let left = usize::from(code) / 12;
                let right = usize::from(code) % 12;
                assert!(left < right && slots[left][right] != u8::MAX);
                let bits = (1 << left) | (1 << right);
                assert_eq!(mask & bits, bits);
                assert_eq!(used & bits, 0);
                used |= bits;
            }
        }
        let pairs = &*GRAPH33_PAIR_COMB13_POINTS;
        let base = &*WIDTH_SIX_COMB13_POINTS;
        assert_eq!(pairs.rows.len(), 33);
        assert!(pairs.rows.iter().all(|row| row.len() == PAIR_COMB13_ENTRIES_PER_PAIR));
        for (edge_index, &(left_row, right_row)) in GRAPH33_EDGES.iter().enumerate() {
            if right_row - left_row <= 2 { continue; }
            for first_orbit in [0, 40, 80] {
                for second_orbit in [0, 40, 80] {
                    let first = WidthSixDigit { orbit: first_orbit,
                        unit: Unit { sign: -1, omega_power: 2 } };
                    let second = WidthSixDigit { orbit: second_orbit,
                        unit: Unit { sign: 1, omega_power: 1 } };
                    let direct = width_six_unit_image(base.full_rows[left_row][first_orbit], first)
                        .add_mixed(width_six_unit_image(base.full_rows[right_row][second_orbit], second));
                    let paired = width_six_unit_image(
                        pair_comb13_point(pairs, edge_index, first, second), first);
                    assert_eq!(direct.affine_hex(), paired.affine_hex());
                }
            }
        }
        let n = SCALAR_LATTICE.n.clone();
        for scalar in [BigInt::ZERO, BigInt::from(1), &n - 1, n + 1] {
            let old = scalar_multiply_width_six_comb13_hex9_radius2(&scalar);
            let new = scalar_multiply_width_six_comb13_hex9_graph33(&scalar);
            assert_eq!(old.0.affine_hex(), new.0.affine_hex());
            assert_eq!((&old.1, &old.2, old.3, old.5, old.6, old.7),
                       (&new.1, &new.2, new.3, new.5, new.6, new.7));
            assert!(new.8 >= old.8);
            assert_eq!(old.4.iter().sum::<usize>() + old.8,
                       new.4.iter().sum::<usize>() + new.8);
        }
    }

    #[test]
    fn graph_aware_cover_preserves_points_and_selects_lower_matched_cost() {
        let n = SCALAR_LATTICE.n.clone();
        let holdout_case = BigInt::parse_bytes(
            b"c6fa5e337622dd0351b2e9870c3a2bcd375735e36465923be167bd17be625c9e", 16)
            .unwrap();
        for scalar in [BigInt::ZERO, BigInt::from(1), &n - 1, n + 1, holdout_case] {
            let baseline = scalar_multiply_width_six_comb13_hex9_graph33(&scalar);
            let candidate = scalar_multiply_width_six_comb13_hex9_graphaware33(&scalar);
            assert_eq!(baseline.0.affine_hex(), candidate.0.affine_hex());
            assert_eq!(baseline.7, candidate.7);
            let baseline_proxy = 5 * baseline.3 + 11 * baseline.4.iter().sum::<usize>();
            let candidate_proxy = 5 * candidate.3 + 11 * candidate.4.iter().sum::<usize>();
            assert!(candidate_proxy <= baseline_proxy);
            if scalar == BigInt::parse_bytes(
                b"c6fa5e337622dd0351b2e9870c3a2bcd375735e36465923be167bd17be625c9e", 16)
                .unwrap() {
                assert_eq!((baseline_proxy, candidate_proxy), (242, 236));
            }
        }
    }

    #[test]
    fn coset3_comb13_preserves_points_and_never_increases_point_proxy() {
        let n = SCALAR_LATTICE.n.clone();
        let miss = BigInt::parse_bytes(
            b"291a4b1cec292deb928a94385017b681693459cc424b1a9be19f9511ff968bc7",
            16,
        )
        .unwrap();
        for scalar in [BigInt::ZERO, BigInt::from(1), n.clone() - 1, n + 1,
                       BigInt::from(1) << 255, miss] {
            let original = scalar_multiply_width_six_comb13_sparse(&scalar);
            let chosen = scalar_multiply_width_six_comb13_coset3(&scalar);
            assert!(same_point(original.0, chosen.0));
            assert_eq!(
                (&chosen.1 + &chosen.2 * &SCALAR_LATTICE.lambda_tau - &scalar)
                    % &SCALAR_LATTICE.n,
                BigInt::ZERO
            );
            assert!(chosen.6 < 3 && (1..=3).contains(&chosen.7));
            let original_cost = 5 * original.3 + 11 * original.4.iter().sum::<usize>();
            let chosen_cost = 5 * chosen.3 + 11 * chosen.4.iter().sum::<usize>();
            assert!(chosen_cost <= original_cost);
        }
    }

    #[test]
    fn glv_comb_subset_tables_match_independent_scalar_path() {
        for (rows, width, table) in [(8, 16, &*GLV_COMB8_POINTS), (10, 13, &*GLV_COMB10_POINTS)] {
            assert_eq!(table.len(), 1 << rows);
            assert!(table[0].is_identity());
            for mask in [1usize, 2, 3, 1 << (rows - 1), (1 << rows) - 1] {
                let scalar = (0..rows)
                    .filter(|&bit| (mask >> bit) & 1 != 0)
                    .fold(0u128, |sum, bit| sum + (1u128 << (bit * width)));
                assert!(same_point(
                    table[mask],
                    scalar_multiply(&BigInt::from(scalar)).0
                ));
            }
        }
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
