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
use serde_json::json;
use std::io::{self, BufRead};

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
        assert!(self.magnitude.0[4..].iter().all(|&x| x == 0));
        assert!(rhs.magnitude.0[4..].iter().all(|&x| x == 0));
        let a = Uint(self.magnitude.0[..4].try_into().unwrap());
        let b = Uint(rhs.magnitude.0[..4].try_into().unwrap());
        let (low, high) = U256::mul_wide(&a, &b);
        let mut words = [0u64; 8];
        words[..4].copy_from_slice(&low.0);
        words[4..].copy_from_slice(&high.0);
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

    fn tau_constant(self) -> Self {
        self.sub(self.omega()).balance()
    }

    fn strings(self) -> [String; 2] {
        [self.a.decimal(), self.b.decimal()]
    }
}

fn main() {
    let tau_mode = std::env::args().any(|arg| arg == "--tau");
    for line in io::stdin().lock().lines() {
        let line = line.expect("input line");
        if line.trim().is_empty() {
            continue;
        }
        let fields: Vec<&str> = line.split_whitespace().collect();
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
}
