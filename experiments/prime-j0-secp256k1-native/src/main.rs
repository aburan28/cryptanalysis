//! Native 256-bit replay of the cached-projective tau point path.
//!
//! Recompute the scalar representative and width-four digits natively,
//! then check them, every prepared seed, final point, and operation count
//! against the frozen Sage fixture. This is variable-time research code.

#[path = "../../../suite/src/ct_bignum.rs"]
mod ct_bignum;
#[path = "../../../suite/src/ecc/secp256k1_field.rs"]
mod secp256k1_field;
#[cfg(test)]
mod utils {
    // The imported bignum tests expect the suite's modular-inverse helper.
    // Keep this small test-only adapter instead of pulling in suite binaries.
    use num_bigint::{BigInt, BigUint};
    use num_integer::Integer;

    pub fn mod_inverse(a: &BigUint, modulus: &BigUint) -> Option<BigUint> {
        let modulus_i = BigInt::from(modulus.clone());
        let result = BigInt::from(a.clone()).extended_gcd(&modulus_i);
        if result.gcd != BigInt::from(1) {
            None
        } else {
            ((result.x % &modulus_i + &modulus_i) % &modulus_i).to_biguint()
        }
    }
}

use secp256k1_field::SecpFieldElement as F;
use num_bigint::BigInt;
use num_traits::{Signed, Zero};
use serde_json::Value;
use std::fs;
use std::path::PathBuf;
use std::sync::LazyLock;
use std::time::Instant;

mod selective;
mod mixed_radix;
mod coset;

#[derive(Clone, Copy)]
struct J {
    x: F,
    y: F,
    z: F,
}

impl J {
    const fn identity() -> Self {
        Self { x: F::ZERO, y: F::ONE, z: F::ZERO }
    }

    fn affine(x: F, y: F) -> Self {
        Self { x, y, z: F::ONE }
    }

    fn is_identity(self) -> bool {
        self.z == F::ZERO
    }

    fn neg(self) -> Self {
        Self { x: self.x, y: self.y.neg(), z: self.z }
    }

    fn omega(self, beta: F) -> Self {
        Self { x: beta.mul(&self.x), y: self.y, z: self.z }
    }

    fn double(self) -> Self {
        if self.is_identity() || self.y == F::ZERO {
            return Self::identity();
        }
        let a = self.x.sqr();
        let b = self.y.sqr();
        let c = b.sqr();
        let xb = self.x.add(&b);
        let d0 = xb.sqr().sub(&a).sub(&c);
        let d = twice(d0);
        let e = triple(a);
        let rx = e.sqr().sub(&twice(d));
        let ry = e.mul(&d.sub(&rx)).sub(&times_eight(c));
        let rz = twice(self.y.mul(&self.z));
        Self { x: rx, y: ry, z: rz }
    }

    fn add_mixed(self, qx: F, qy: F) -> Self {
        if self.is_identity() {
            return Self::affine(qx, qy);
        }
        let zz = self.z.sqr();
        let u = qx.mul(&zz);
        let s = qy.mul(&self.z).mul(&zz);
        let h = u.sub(&self.x);
        let v = s.sub(&self.y);
        if h == F::ZERO {
            return if v == F::ZERO { self.double() } else { Self::identity() };
        }
        let hh = h.sqr();
        let hhh = h.mul(&hh);
        let xhh = self.x.mul(&hh);
        let rx = v.sqr().sub(&hhh).sub(&twice(xhh));
        let ry = v.mul(&xhh.sub(&rx)).sub(&self.y.mul(&hhh));
        let rz = self.z.mul(&h);
        Self { x: rx, y: ry, z: rz }
    }

    fn add_cached(self, q: Self, qz2: F, qz3: F) -> (Self, bool) {
        assert!(!self.is_identity() && !q.is_identity());
        let z1_squared = self.z.sqr();
        let u1 = self.x.mul(&qz2);
        let u2 = q.x.mul(&z1_squared);
        let s1 = self.y.mul(&qz3);
        let s2 = q.y.mul(&self.z).mul(&z1_squared);
        let h = u2.sub(&u1);
        let r = s2.sub(&s1);
        if h == F::ZERO {
            return (if r == F::ZERO { self.double() } else { Self::identity() }, true);
        }
        let hh = h.sqr();
        let hhh = h.mul(&hh);
        let v = u1.mul(&hh);
        let rx = r.sqr().sub(&hhh).sub(&twice(v));
        let ry = r.mul(&v.sub(&rx)).sub(&s1.mul(&hhh));
        let rz = self.z.mul(&q.z).mul(&h);
        (Self { x: rx, y: ry, z: rz }, false)
    }

    fn tau(self, one_minus_beta: F) -> Self {
        if self.is_identity() || self.x == F::ZERO {
            return Self::identity();
        }
        let x3 = self.x.sqr().mul(&self.x);
        let rx = times_four(self.y.sqr()).sub(&triple(x3));
        let ry = self.y.mul(&triple(x3).sub(&twice(rx)));
        let rz = one_minus_beta.mul(&self.x).mul(&self.z);
        Self { x: rx, y: ry, z: rz }
    }

    fn tau_pair_cheap(self) -> Self {
        if self.is_identity() || self.x == F::ZERO {
            return Self::identity();
        }
        let x3 = self.x.sqr().mul(&self.x);
        let tx = times_four(self.y.sqr()).sub(&triple(x3));
        let ty = self.y.mul(&triple(x3).sub(&twice(tx)));
        let tx3 = tx.sqr().mul(&tx);
        let rx = times_four(ty.sqr()).sub(&triple(tx3));
        let ry = ty.mul(&triple(tx3).sub(&twice(rx)));
        let rz = triple(tx).mul(&self.x).mul(&self.z).neg();
        Self { x: rx, y: ry, z: rz }
    }

    fn to_affine(self) -> Option<(F, F)> {
        if self.is_identity() {
            return None;
        }
        let inverse = self.z.inv();
        let square = inverse.sqr();
        let cube = square.mul(&inverse);
        Some((self.x.mul(&square), self.y.mul(&cube)))
    }

    fn to_affine_fast(self) -> Option<(F, F)> {
        if self.is_identity() {
            return None;
        }
        let inverse = self.z.inv_chain();
        let square = inverse.sqr();
        let cube = square.mul(&inverse);
        Some((self.x.mul(&square), self.y.mul(&cube)))
    }
}

fn scaled(point: J, z: F) -> J {
    let z2 = z.sqr();
    J { x: point.x.mul(&z2), y: point.y.mul(&z2.mul(&z)), z }
}

fn check_exceptional_additions() {
    let generator = J::affine(
        fe_from_hex("79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"),
        fe_from_hex("483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8"));
    let seven = F::ONE.add(&F::ONE).add(&F::ONE).add(&F::ONE)
        .add(&F::ONE).add(&F::ONE).add(&F::ONE);
    assert_eq!(generator.y.sqr(), generator.x.sqr().mul(&generator.x).add(&seven));
    let twice_generator = generator.double();
    let thrice_generator = twice_generator.add_mixed(generator.x, generator.y);
    let bases = [generator, twice_generator, thrice_generator];
    let mut checks = 0usize;
    for base in bases {
        let (x, y) = base.to_affine().expect("nonidentity control point");
        let affine_base = J::affine(x, y);
        for left_z in [F::ONE, F::ONE.add(&F::ONE).add(&F::ONE)] {
            for right_z in [F::ONE, F::ONE.add(&F::ONE)] {
                let left = scaled(affine_base, left_z);
                let right = scaled(affine_base, right_z);
                let right_z2 = right.z.sqr();
                let right_z3 = right_z2.mul(&right.z);
                let (doubled, doubled_exception) =
                    left.add_cached(right, right_z2, right_z3);
                assert!(doubled_exception);
                assert_eq!(doubled.to_affine(), left.double().to_affine());
                checks += 1;
                let (canceled, canceled_exception) =
                    left.add_cached(right.neg(), right_z2, right_z3);
                assert!(canceled_exception);
                assert!(canceled.is_identity());
                checks += 1;
            }
        }
    }
    assert_eq!(checks, 24);
    println!("{{\"verified\":true,\"exception_cases\":24,\"cpu_speedup_claim\":null}}");
}

fn twice(a: F) -> F { a.add(&a) }
fn triple(a: F) -> F { twice(a).add(&a) }
fn times_four(a: F) -> F { twice(twice(a)) }
fn times_eight(a: F) -> F { twice(times_four(a)) }

fn fe_from_hex(text: &str) -> F {
    let bytes = hex::decode(text).expect("invalid hex field element");
    let raw: [u8; 32] = bytes.try_into().expect("field element must be 32 bytes");
    F::from_bytes_be(&raw)
}

fn fe_hex(value: F) -> String {
    hex::encode(value.to_bytes_be())
}

fn prepare(base: J, beta: F) -> [J; 9] {
    assert!(base.z == F::ONE);
    let twice_base = base.double();
    let four_base = twice_base.double();
    let omega_x = beta.mul(&base.x);
    let one_tau = twice_base.add_mixed(omega_x, base.y.neg());
    let two_two_tau = one_tau.double();
    let one_two_tau = two_two_tau.add_mixed(base.x, base.y.neg());
    let two_four_tau = one_two_tau.double();
    let two_tau = one_tau.add_mixed(base.x, base.y);
    let one_minus_two_tau = twice_base.omega(beta).add_mixed(base.x, base.y.neg());
    [base, twice_base, four_base, one_tau, two_two_tau, one_two_tau,
     two_four_tau, two_tau, one_minus_two_tau]
}

// Joint digit-atlas variant: slots 5 and 6 are 2 and 4 times slot 8.
// This uses five doubles and three mixed additions, versus four of each
// in prepare(), with the same two unit rotations.
fn prepare_alternate(base: J, beta: F) -> [J; 9] {
    assert!(base.z == F::ONE);
    let twice_base = base.double();
    let four_base = twice_base.double();
    let omega_x = beta.mul(&base.x);
    let one_tau = twice_base.add_mixed(omega_x, base.y.neg());
    let two_two_tau = one_tau.double();
    let two_tau = one_tau.add_mixed(base.x, base.y);
    let one_minus_two_tau = twice_base.omega(beta).add_mixed(base.x, base.y.neg());
    let two_minus_four_tau = one_minus_two_tau.double();
    let four_minus_eight_tau = two_minus_four_tau.double();
    [base, twice_base, four_base, one_tau, two_two_tau,
     two_minus_four_tau, four_minus_eight_tau, two_tau, one_minus_two_tau]
}

// Linked three-orbit atlas: two mixed additions and six doubles.
fn prepare_linked(base: J, beta: F) -> [J; 9] {
    assert!(base.z == F::ONE);
    let twice_base = base.double();
    let four_base = twice_base.double();
    let omega_x = beta.mul(&base.x);
    let one_tau = twice_base.add_mixed(omega_x, base.y.neg());
    let two_two_tau = one_tau.double();
    let one_minus_two_tau = twice_base.omega(beta).add_mixed(base.x, base.y.neg());
    let two_minus_four_tau = one_minus_two_tau.double();
    let four_minus_eight_tau = two_minus_four_tau.double();
    let four_four_tau = two_two_tau.double();
    [base, twice_base, four_base, one_tau, two_two_tau,
     two_minus_four_tau, four_minus_eight_tau, four_four_tau,
     one_minus_two_tau]
}

// Construct (2P - omega(P), omega(2P) - P) together. Both mixed additions
// have the same projective Z and Y input and the same affine addend Y, so
// Z^2, Z^3, the Y difference, and its square are computed only once.
fn prepare_linked_twinned(base: J, beta: F) -> [J; 9] {
    assert_eq!(base.z, F::ONE);
    let twice_base = base.double();
    let four_base = twice_base.double();
    let z2 = twice_base.z.sqr();
    let z3 = twice_base.z.mul(&z2);
    let v = base.y.neg().mul(&z3).sub(&twice_base.y);
    let v2 = v.sqr();
    let u = base.x.mul(&z2);
    let beta_u = beta.mul(&u);
    let beta_x = beta.mul(&twice_base.x);

    fn finish(x: F, y: F, z: F, u: F, v: F, v2: F) -> J {
        let h = u.sub(&x);
        // On the declared prime-order secp256k1 subgroup these additions
        // cannot be a doubling or cancellation: 2P != +/-omega(P) and
        // omega(2P) != +/-P for nonidentity P.
        assert_ne!(h, F::ZERO);
        let hh = h.sqr();
        let hhh = h.mul(&hh);
        let xhh = x.mul(&hh);
        let rx = v2.sub(&hhh).sub(&twice(xhh));
        let ry = v.mul(&xhh.sub(&rx)).sub(&y.mul(&hhh));
        let rz = z.mul(&h);
        J { x: rx, y: ry, z: rz }
    }

    let one_tau = finish(twice_base.x, twice_base.y, twice_base.z,
                         beta_u, v, v2);
    let one_minus_two_tau = finish(beta_x, twice_base.y, twice_base.z,
                                   u, v, v2);
    let two_two_tau = one_tau.double();
    let four_four_tau = two_two_tau.double();
    let two_minus_four_tau = one_minus_two_tau.double();
    let four_minus_eight_tau = two_minus_four_tau.double();
    [base, twice_base, four_base, one_tau, two_two_tau,
     two_minus_four_tau, four_minus_eight_tau, four_four_tau,
     one_minus_two_tau]
}

// Simultaneously form (2-omega)P, omega(2-omega^2)P, and 2P from the
// shared degree-seven inputs in Xu et al., Proposition 3.2. The two
// conjugates reuse X^3, Y^2, A^2, B^2, beta*A, and beta*B.
fn prepare_linked_conjugate_rho(base: J, beta: F) -> [J; 9] {
    assert_eq!(base.z, F::ONE);
    let x2 = base.x.sqr();
    let x3 = x2.mul(&base.x);
    let y2 = base.y.sqr();
    let a = triple(x3);
    let b = times_four(y2);
    let aa = a.sqr();
    let bb = b.sqr();
    let c = beta.mul(&a);
    let d = beta.mul(&b);

    fn rho(x: F, y: F, z: F, a: F, b: F, aa: F, bb: F,
           c: F, d: F) -> J {
        let x_term = triple(aa).neg().sub(
            &b.add(&triple(d)).mul(&twice(a).sub(&b).add(&c)));
        let y_left = triple(aa).mul(
            &a.sub(&times_four(c)).add(&times_eight(d).sub(&d)));
        let y_right = bb.mul(
            &b.sub(&triple(a)).sub(&times_eight(c).add(&c)));
        let z_term = twice(a).sub(&b).add(&c).sub(&d);
        J { x: x.mul(&x_term),
            y: y.mul(&y_left.add(&y_right)),
            z: z.mul(&z_term) }
    }

    let one_tau = rho(base.x, base.y, base.z, a, b, aa, bb, c, d);
    let c_conjugate = a.add(&c).neg();
    let d_conjugate = b.add(&d).neg();
    let conjugate = rho(base.x, base.y, base.z, a, b, aa, bb,
                        c_conjugate, d_conjugate);
    let one_minus_two_tau = conjugate.omega(beta);
    let y4 = y2.sqr();
    let twice_base = J {
        x: base.x.mul(&triple(a).sub(&twice(b))),
        y: triple(a).mul(&b.sub(&a)).sub(&times_eight(y4)),
        z: twice(base.y).mul(&base.z),
    };
    let four_base = twice_base.double();
    let two_two_tau = one_tau.double();
    let four_four_tau = two_two_tau.double();
    let two_minus_four_tau = one_minus_two_tau.double();
    let four_minus_eight_tau = two_minus_four_tau.double();
    [base, twice_base, four_base, one_tau, two_two_tau,
     two_minus_four_tau, four_minus_eight_tau, four_four_tau,
     one_minus_two_tau]
}

fn normalize_all(seeds: &[J; 9]) -> [J; 9] {
    let mut normalized = *seeds;
    let mut prefix = [F::ONE; 8];
    let mut product = seeds[1].z;
    assert!(product != F::ZERO);
    for index in 2..9 {
        assert!(seeds[index].z != F::ZERO);
        prefix[index - 1] = product;
        product = product.mul(&seeds[index].z);
    }
    let mut inverse_product = product.inv();
    let mut inverse_z = [F::ZERO; 8];
    for index in (2..9).rev() {
        inverse_z[index - 1] = inverse_product.mul(&prefix[index - 1]);
        inverse_product = inverse_product.mul(&seeds[index].z);
    }
    inverse_z[0] = inverse_product;
    for index in 1..9 {
        let square = inverse_z[index - 1].sqr();
        let cube = square.mul(&inverse_z[index - 1]);
        normalized[index] = J::affine(seeds[index].x.mul(&square),
                                      seeds[index].y.mul(&cube));
    }
    normalized
}

// Represent all nine seeds with one Jacobian Z without a field inversion.
// The returned Z maps a point (X,Y,z) on the scaled curve back to
// (X,Y,common_z*z) on the original curve. All point formulas used here
// are independent of b, so evaluation can use mixed additions on the
// scaled curve and multiply the final Z by common_z once.
fn align_common_z(seeds: &[J; 9]) -> (F, [J; 9]) {
    assert_eq!(seeds[0].z, F::ONE);
    let mut prefix = [F::ONE; 8];
    prefix[0] = seeds[1].z;
    assert_ne!(prefix[0], F::ZERO);
    for index in 1..8 {
        assert_ne!(seeds[index + 1].z, F::ZERO);
        prefix[index] = prefix[index - 1].mul(&seeds[index + 1].z);
    }
    let common_z = prefix[7];
    let mut complements = [F::ONE; 8];
    let mut suffix = F::ONE;
    for index in (1..8).rev() {
        complements[index] = prefix[index - 1].mul(&suffix);
        suffix = suffix.mul(&seeds[index + 1].z);
    }
    complements[0] = suffix;
    let mut aligned = *seeds;
    for index in 0..9 {
        let scale = if index == 0 { common_z } else { complements[index - 1] };
        let square = scale.sqr();
        let cube = square.mul(&scale);
        aligned[index] = J::affine(seeds[index].x.mul(&square),
                                   seeds[index].y.mul(&cube));
    }
    (common_z, aligned)
}

fn orbit(seed: J, beta: F) -> [J; 3] {
    let x1 = beta.mul(&seed.x);
    let x2 = seed.x.neg().sub(&x1);
    [seed,
     J { x: x1, y: seed.y, z: seed.z },
     J { x: x2, y: seed.y, z: seed.z }]
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
struct Digit { a: i64, b: i64, seed: usize, power: usize, sign: i64 }

fn big_from_hex(value: &str) -> BigInt {
    let (negative, unsigned) = if let Some(rest) = value.strip_prefix('-') {
        (true, rest)
    } else {
        (false, value)
    };
    let hex = unsigned.strip_prefix("0x").unwrap_or(unsigned);
    let number = BigInt::parse_bytes(hex.as_bytes(), 16).expect("valid scalar hex");
    if negative { -number } else { number }
}

fn round_div(numerator: BigInt, denominator: BigInt) -> BigInt {
    assert!(!denominator.is_zero());
    let (top, bottom) = if denominator < BigInt::ZERO {
        (-numerator, -denominator)
    } else {
        (numerator, denominator)
    };
    let half: BigInt = &bottom / BigInt::from(2);
    if top < BigInt::ZERO {
        -((-top + half) / bottom)
    } else {
        (top + half) / bottom
    }
}

fn eisenstein_norm(a: &BigInt, b: &BigInt) -> BigInt {
    a * a + 3 * a * b + 3 * b * b
}

struct Lattice {
    n: BigInt, lambda: BigInt,
    u0: BigInt, u1: BigInt, v0: BigInt, v1: BigInt, det: BigInt,
}

static LATTICE: LazyLock<Lattice> = LazyLock::new(|| {
    // Frozen from the checked Sage result.json: Gauss-reduced kernel of
    // (a+b*lambda_tau) mod n. The fixture comparison audits the choice.
    let n = big_from_hex("fffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141");
    let lambda = big_from_hex("ac9c52b33fa3cf1f5ad9e3fd77ed9ba4a880b9fc8ec739c2e0cfc810b51283d0");
    let u0 = BigInt::parse_bytes(b"193508920647619669885755136084601127231", 10).unwrap();
    let u1 = BigInt::parse_bytes(b"238911465918039986966665730306072050094", 10).unwrap();
    let v0 = -u1.clone();
    let v1 = BigInt::parse_bytes(b"303414439467246543595250775667605759171", 10).unwrap();
    let det = &u0 * &v1 - &u1 * &v0;
    assert_eq!(det.abs(), n);
    Lattice { n, lambda, u0, u1, v0, v1, det }
});

fn short_representative(scalar: &BigInt) -> (BigInt, BigInt) {
    let lattice = &*LATTICE;
    let center_u = round_div(scalar * &lattice.v1, lattice.det.clone());
    let center_v = round_div(-scalar * &lattice.u1, lattice.det.clone());
    let mut best: Option<(BigInt, BigInt, BigInt, BigInt)> = None;
    for du in -2..=2 {
        for dv in -2..=2 {
            let u = &center_u + du;
            let v = &center_v + dv;
            let a: BigInt = scalar - &u * &lattice.u0 - &v * &lattice.v0;
            let b: BigInt = -&u * &lattice.u1 - &v * &lattice.v1;
            debug_assert_eq!((&a + &b * &lattice.lambda - scalar) % &lattice.n,
                             BigInt::ZERO);
            let magnitude = std::cmp::max(a.abs(), b.abs());
            let option = (eisenstein_norm(&a, &b), magnitude, a, b);
            if best.as_ref().is_none_or(|old| option < *old) {
                best = Some(option);
            }
        }
    }
    let (_, _, a, b) = best.expect("25 representative choices");
    (a, b)
}

fn ranked_representatives(scalar: &BigInt) -> Vec<(BigInt, BigInt)> {
    let lattice = &*LATTICE;
    let center_u = round_div(scalar * &lattice.v1, lattice.det.clone());
    let center_v = round_div(-scalar * &lattice.u1, lattice.det.clone());
    let mut ranked = Vec::with_capacity(25);
    for du in -2..=2 {
        for dv in -2..=2 {
            let u = &center_u + du;
            let v = &center_v + dv;
            let a: BigInt = scalar - &u * &lattice.u0 - &v * &lattice.v0;
            let b: BigInt = -&u * &lattice.u1 - &v * &lattice.v1;
            debug_assert_eq!((&a + &b * &lattice.lambda - scalar) % &lattice.n,
                             BigInt::ZERO);
            let magnitude = std::cmp::max(a.abs(), b.abs());
            ranked.push((eisenstein_norm(&a, &b), magnitude, a, b));
        }
    }
    ranked.sort();
    ranked.into_iter().take(3).map(|(_, _, a, b)| (a, b)).collect()
}

fn signed_residue(value: &BigInt, modulus: i64) -> usize {
    let base = BigInt::from(modulus);
    let residue = (value % &base + &base) % &base;
    usize::try_from(residue).expect("small nonnegative residue")
}

fn digit_table_for(mode: u8) -> [[Option<Digit>; 9]; 9] {
    let seeds: [(i64, i64); 9] = if mode == 2 {
        [(1, 0), (2, 0), (4, 0), (1, 1), (2, 2),
         (2, -4), (4, -8), (4, 4), (1, -2)]
    } else if mode == 1 {
        [(1, 0), (2, 0), (4, 0), (1, 1), (2, 2),
         (2, -4), (4, -8), (2, 1), (1, -2)]
    } else {
        assert_eq!(mode, 0);
        [(1, 0), (2, 0), (4, 0), (1, 1), (2, 2),
         (1, 2), (2, 4), (2, 1), (1, -2)]
    };
    let mut table = [[None; 9]; 9];
    let mut entries = 0;
    for (seed, (a0, b0)) in seeds.into_iter().enumerate() {
        let (mut a, mut b) = (a0, b0);
        for power in 0..3 {
            for sign in [-1, 1] {
                let x = sign * a;
                let y = sign * b;
                let row = x.rem_euclid(9) as usize;
                let col = y.rem_euclid(9) as usize;
                assert_ne!(row % 3, 0);
                assert!(table[row][col].is_none(), "duplicate width-four residue");
                table[row][col] = Some(Digit { a: x, b: y, seed, power, sign });
                entries += 1;
            }
            (a, b) = (a + 3 * b, -a - 2 * b);
        }
    }
    assert_eq!(entries, 54);
    table
}

static DIGIT_TABLE: LazyLock<[[Option<Digit>; 9]; 9]> =
    LazyLock::new(|| digit_table_for(0));
static ALTERNATE_DIGIT_TABLE: LazyLock<[[Option<Digit>; 9]; 9]> =
    LazyLock::new(|| digit_table_for(1));
static LINKED_DIGIT_TABLE: LazyLock<[[Option<Digit>; 9]; 9]> =
    LazyLock::new(|| digit_table_for(2));

fn recode_with_table(mut a: BigInt, mut b: BigInt,
                     table: &[[Option<Digit>; 9]; 9]) -> Vec<Option<Digit>> {
    #[cfg(debug_assertions)]
    let original = (a.clone(), b.clone());
    let mut digits = Vec::new();
    while !a.is_zero() || !b.is_zero() {
        assert!(digits.len() < 256, "tau expansion did not terminate");
        let digit = if signed_residue(&a, 3) != 0 {
            let entry = table[signed_residue(&a, 9)][signed_residue(&b, 9)]
                .expect("covered width-four residue");
            a -= entry.a;
            b -= entry.b;
            Some(entry)
        } else {
            None
        };
        debug_assert_eq!(signed_residue(&a, 3), 0);
        digits.push(digit);
        (a, b) = (&a + &b, -a / 3);
    }
    #[cfg(debug_assertions)]
    {
        for pair in digits.chunks(2) {
            if pair.len() == 2 {
                assert!(pair[0].is_none() || pair[1].is_none());
            }
        }
        let (mut rebuilt_a, mut rebuilt_b) = (BigInt::ZERO, BigInt::ZERO);
        for digit in digits.iter().rev() {
            let next_a = -3 * &rebuilt_b;
            let next_b = &rebuilt_a + 3 * &rebuilt_b;
            rebuilt_a = next_a;
            rebuilt_b = next_b;
            if let Some(d) = digit {
                rebuilt_a += d.a;
                rebuilt_b += d.b;
            }
        }
        assert_eq!((rebuilt_a, rebuilt_b), original);
    }
    digits
}

fn recode(a: BigInt, b: BigInt) -> Vec<Option<Digit>> {
    recode_with_table(a, b, &DIGIT_TABLE)
}

fn recode_alternate(a: BigInt, b: BigInt) -> Vec<Option<Digit>> {
    recode_with_table(a, b, &ALTERNATE_DIGIT_TABLE)
}

fn recode_linked(a: BigInt, b: BigInt) -> Vec<Option<Digit>> {
    recode_with_table(a, b, &LINKED_DIGIT_TABLE)
}

type ResidueStep = (usize, usize, Option<Digit>);

struct PortfolioPlan {
    streams: [Vec<Option<Digit>>; 3],
    costs: [usize; 3],
    choice: usize,
    active_steps: usize,
    peak_carry_norm: i64,
}

fn baseline_residue_scan(mut a: BigInt, mut b: BigInt) -> Vec<ResidueStep> {
    let mut states = Vec::new();
    while !a.is_zero() || !b.is_zero() {
        assert!(states.len() < 256, "tau expansion did not terminate");
        let ra = signed_residue(&a, 9);
        let rb = signed_residue(&b, 9);
        let digit = if ra % 3 != 0 {
            let selected = DIGIT_TABLE[ra][rb].expect("covered width-four residue");
            a -= selected.a;
            b -= selected.b;
            Some(selected)
        } else {
            None
        };
        debug_assert_eq!(signed_residue(&a, 3), 0);
        states.push((ra, rb, digit));
        (a, b) = (&a + &b, -a / 3);
    }
    states
}

fn small_carry_norm((a, b): (i64, i64)) -> i64 {
    a * a + 3 * a * b + 3 * b * b
}

fn translate_residue_stream(
    states: &[ResidueStep], table: &[[Option<Digit>; 9]; 9],
    changed: &[bool; 9],
) -> (Vec<Option<Digit>>, usize, i64) {
    let mut digits = Vec::with_capacity(states.len() + 8);
    let mut carry = (0i64, 0i64);
    let mut active_steps = 0usize;
    let mut peak_norm = 0i64;
    for &(ra, rb, old) in states {
        if carry == (0, 0) && old.is_none_or(|digit| !changed[digit.seed]) {
            digits.push(old);
            continue;
        }
        active_steps += 1;
        let row = (ra as i64 + carry.0).rem_euclid(9) as usize;
        let col = (rb as i64 + carry.1).rem_euclid(9) as usize;
        let new = if row % 3 != 0 { table[row][col] } else { None };
        digits.push(new);
        let (da, db) = old.map_or((0, 0), |digit| (digit.a, digit.b));
        let (ea, eb) = new.map_or((0, 0), |digit| (digit.a, digit.b));
        let delta_a = da + carry.0 - ea;
        let delta_b = db + carry.1 - eb;
        assert_eq!(delta_a % 3, 0);
        carry = (delta_a + delta_b, -delta_a / 3);
        peak_norm = peak_norm.max(small_carry_norm(carry));
        assert!(peak_norm <= 896);
    }
    let mut tail = 0;
    while carry != (0, 0) {
        assert!(tail < 64, "bounded carry tail did not terminate");
        let row = carry.0.rem_euclid(9) as usize;
        let col = carry.1.rem_euclid(9) as usize;
        let new = if row % 3 != 0 { table[row][col] } else { None };
        digits.push(new);
        let (ea, eb) = new.map_or((0, 0), |digit| (digit.a, digit.b));
        let x = carry.0 - ea;
        let y = carry.1 - eb;
        assert_eq!(x % 3, 0);
        carry = (x + y, -x / 3);
        peak_norm = peak_norm.max(small_carry_norm(carry));
        assert!(peak_norm <= 896);
        tail += 1;
    }
    while digits.last().is_some_and(Option::is_none) { digits.pop(); }
    (digits, active_steps, peak_norm)
}

fn source_cost(digits: &[Option<Digit>], preparation: usize) -> usize {
    if digits.is_empty() { return preparation; }
    let pairs = planned_pairs(digits);
    let steps = digits.len() - 1;
    assert!(steps >= 2 * pairs);
    let mut nonzero = Vec::new();
    for digit in digits.iter().flatten() { nonzero.push(digit.seed); }
    nonzero.pop(); // Highest digit initializes the accumulator.
    let mixed = nonzero.iter().filter(|&&seed| seed == 0).count();
    let general = nonzero.len() - mixed;
    let mut used = [false; 12];
    for &seed in &nonzero {
        assert!(seed < used.len());
        if seed > 0 { used[seed] = true; }
    }
    let cache = used.into_iter().filter(|used| *used).count();
    preparation + 10 * pairs + 6 * (steps - 2 * pairs)
        + 11 * mixed + 14 * general + 2 * cache
}

fn recode_portfolio(a: BigInt, b: BigInt) -> PortfolioPlan {
    let states = baseline_residue_scan(a, b);
    let original = states.iter().map(|state| state.2).collect::<Vec<_>>();
    let mut two_changed = [false; 9];
    two_changed[5] = true;
    two_changed[6] = true;
    let mut three_changed = two_changed;
    three_changed[7] = true;
    let (two, active_two, norm_two) =
        translate_residue_stream(&states, &ALTERNATE_DIGIT_TABLE, &two_changed);
    let (three, active_three, norm_three) =
        translate_residue_stream(&states, &LINKED_DIGIT_TABLE, &three_changed);
    let streams = [original, two, three];
    let costs = [source_cost(&streams[0], 83), source_cost(&streams[1], 79),
                 source_cost(&streams[2], 75)];
    let mut choice = 0;
    for index in 1..3 {
        if costs[index] < costs[choice] { choice = index; }
    }
    PortfolioPlan { streams, costs, choice,
                    active_steps: active_two + active_three,
                    peak_carry_norm: norm_two.max(norm_three) }
}

fn prepare_choice(base: J, beta: F, choice: usize) -> [J; 9] {
    match choice {
        0 => prepare(base, beta),
        1 => prepare_alternate(base, beta),
        2 => prepare_linked(base, beta),
        _ => panic!("invalid atlas choice"),
    }
}

fn digits_from_json(case: &Value) -> Vec<Option<Digit>> {
    case["digits"].as_array().expect("digits array").iter().map(|raw| {
        if raw.is_null() { return None; }
        let word = raw.as_array().expect("digit tuple");
        assert_eq!(word.len(), 5);
        let seed = word[2].as_u64().expect("seed") as usize;
        let power = word[3].as_u64().expect("power") as usize;
        let sign = word[4].as_i64().expect("sign");
        assert!(seed < 9 && power < 3 && (sign == 1 || sign == -1));
        let a = word[0].as_i64().expect("digit a");
        let b = word[1].as_i64().expect("digit b");
        Some(Digit { a, b, seed, power, sign })
    }).collect()
}

fn planned_pairs(digits: &[Option<Digit>]) -> usize {
    if digits.is_empty() { return 0; }
    assert!(digits.last().expect("nonempty").is_some());
    let mut index = digits.len() as isize - 1;
    let (mut started, mut pairs) = (false, 0);
    while index >= 0 {
        if started && digits[index as usize].is_none() && index > 0 {
            pairs += 1;
            index -= 2;
        } else {
            started |= digits[index as usize].is_some();
            index -= 1;
        }
    }
    pairs
}

#[derive(Default)]
struct Counts {
    tau_steps: usize,
    tau_pairs: usize,
    cheap_z_pairs: usize,
    mixed_adds: usize,
    general_adds: usize,
    exceptional_cached_adds: usize,
    first_insertions: usize,
    cache_entries: usize,
}

fn evaluate_mode<const N: usize>(digits: &[Option<Digit>], seeds: &[J; N], beta: F,
                                 all_affine: bool, used_orbits_only: bool) -> (J, Counts) {
    let mut counts = Counts::default();
    if digits.is_empty() { return (J::identity(), counts); }
    let mut images = [[J::identity(); 3]; N];
    let mut orbit_ready = [false; N];
    if used_orbits_only {
        for digit in digits.iter().flatten() {
            if !orbit_ready[digit.seed] {
                images[digit.seed] = orbit(seeds[digit.seed], beta);
                orbit_ready[digit.seed] = true;
            }
        }
    } else {
        for seed in 0..N {
            images[seed] = orbit(seeds[seed], beta);
        }
    }
    let mut cache: [Option<(F, F)>; N] = [None; N];
    if !all_affine {
        for digit in digits.iter().take(digits.len() - 1).flatten() {
            if digit.seed > 0 && cache[digit.seed].is_none() {
                let z = seeds[digit.seed].z;
                let z2 = z.sqr();
                cache[digit.seed] = Some((z2, z2.mul(&z)));
                counts.cache_entries += 1;
            }
        }
    }
    let pairs = planned_pairs(digits);
    let mut gauge = (3 - (2 * pairs) % 3) % 3;
    let one_minus_beta = F::ONE.sub(&beta);
    let mut accumulator = J::identity();
    let mut index = digits.len() as isize - 1;
    while index >= 0 {
        let mut digit = digits[index as usize];
        let pair = !accumulator.is_identity() && digit.is_none() && index > 0;
        if pair {
            index -= 1;
            digit = digits[index as usize];
        }
        if !accumulator.is_identity() {
            if pair {
                accumulator = accumulator.tau_pair_cheap();
                gauge = (gauge + 2) % 3;
                counts.tau_steps += 2;
                counts.tau_pairs += 1;
                counts.cheap_z_pairs += 1;
            } else {
                accumulator = accumulator.tau(one_minus_beta);
                counts.tau_steps += 1;
            }
        }
        if let Some(d) = digit {
            let mut q = images[d.seed][(d.power + gauge) % 3];
            if d.sign < 0 { q = q.neg(); }
            if accumulator.is_identity() {
                accumulator = q;
                counts.first_insertions += 1;
            } else if all_affine || d.seed == 0 {
                assert_eq!(q.z, F::ONE);
                accumulator = accumulator.add_mixed(q.x, q.y);
                counts.mixed_adds += 1;
            } else {
                let (z2, z3) = cache[d.seed].expect("cached seed powers");
                let (sum, exceptional) = accumulator.add_cached(q, z2, z3);
                accumulator = sum;
                counts.general_adds += 1;
                counts.exceptional_cached_adds += usize::from(exceptional);
            }
        }
        index -= 1;
    }
    assert_eq!(counts.tau_pairs, pairs);
    assert_eq!(gauge, 0);
    assert_eq!(counts.first_insertions, 1);
    (accumulator, counts)
}

fn evaluate(digits: &[Option<Digit>], seeds: &[J; 9], beta: F) -> (J, Counts) {
    evaluate_mode(digits, seeds, beta, false, false)
}

fn check_benchmark_case(mode: &str, fixture_path: &str, index: usize,
                        timed: bool) {
    assert!(mode == "cached_projective" || mode == "all_affine" ||
            mode == "shared_z" ||
            mode == "joint_atlas" || mode == "linked_atlas" ||
            mode == "linked_twin" || mode == "linked_rho" ||
            mode == "portfolio");
    let raw = fs::read(fixture_path).expect("read benchmark fixture");
    let fixture: Value = serde_json::from_slice(&raw).expect("parse benchmark fixture");
    assert_eq!(fixture["schema"].as_u64(), Some(1));
    let case = &fixture["cases"].as_array().expect("benchmark cases")[index];
    let base_x = case["base_x_hex"].as_str().expect("base x");
    let base_y = case["base_y_hex"].as_str().expect("base y");
    let scalar_hex = case["scalar_hex"].as_str().expect("scalar");
    let expected_identity = case["expected_identity"].as_bool().unwrap_or(false);
    let expected_point = if expected_identity {
        "identity".to_owned()
    } else {
        format!("{}:{}", case["expected_x_hex"].as_str().expect("output x"),
                case["expected_y_hex"].as_str().expect("output y"))
    };
    let beta = fe_from_hex(fixture["beta_hex"].as_str().expect("beta"));
    LazyLock::force(&LATTICE);
    if mode == "portfolio" {
        LazyLock::force(&DIGIT_TABLE);
        LazyLock::force(&ALTERNATE_DIGIT_TABLE);
        LazyLock::force(&LINKED_DIGIT_TABLE);
    } else if mode == "linked_atlas" || mode == "linked_twin" ||
              mode == "linked_rho" {
        LazyLock::force(&LINKED_DIGIT_TABLE);
    } else if mode == "joint_atlas" {
        LazyLock::force(&ALTERNATE_DIGIT_TABLE);
    } else {
        LazyLock::force(&DIGIT_TABLE);
    }
    let start = Instant::now();
    let scalar = big_from_hex(scalar_hex);
    let base = J::affine(fe_from_hex(base_x), fe_from_hex(base_y));
    let (a, b) = short_representative(&scalar);
    let (digits, atlas_choice) = if mode == "portfolio" {
        let plan = recode_portfolio(a.clone(), b.clone());
        let choice = plan.choice;
        (plan.streams.into_iter().nth(choice).expect("selected stream"), choice)
    } else if mode == "linked_atlas" || mode == "linked_twin" ||
              mode == "linked_rho" {
        (recode_linked(a.clone(), b.clone()), 2)
    } else if mode == "joint_atlas" {
        (recode_alternate(a.clone(), b.clone()), 1)
    } else {
        (recode(a.clone(), b.clone()), 0)
    };
    let prepared = if mode == "linked_rho" {
        prepare_linked_conjugate_rho(base, beta)
    } else if mode == "linked_twin" {
        prepare_linked_twinned(base, beta)
    } else {
        prepare_choice(base, beta, atlas_choice)
    };
    let (common_z, seeds) = if mode == "shared_z" {
        let (z, aligned) = align_common_z(&prepared);
        (Some(z), aligned)
    } else if mode == "all_affine" {
        (None, normalize_all(&prepared))
    } else {
        (None, prepared)
    };
    let (mut point, counts) = evaluate_mode(&digits, &seeds, beta,
                                            mode == "all_affine" || mode == "shared_z", false);
    if let Some(z) = common_z {
        point.z = point.z.mul(&z);
    }
    let actual_point = match point.to_affine() {
        None => "identity".to_owned(),
        Some((x, y)) => format!("{}:{}", fe_hex(x), fe_hex(y)),
    };
    assert_eq!(actual_point, expected_point, "benchmark output mismatch");
    let elapsed_ms = start.elapsed().as_secs_f64() * 1000.0;
    if !timed {
        assert_eq!(a, big_from_hex(case["short_a_hex"].as_str().expect("short a")));
        assert_eq!(b, big_from_hex(case["short_b_hex"].as_str().expect("short b")));
        if mode == "shared_z" {
            let z = common_z.expect("shared projective Z");
            for (seed, expected) in seeds.iter().zip(
                case["seed_affine"].as_array().expect("expected seeds")) {
                let original = J { x: seed.x, y: seed.y, z };
                let (x, y) = original.to_affine().expect("nonidentity aligned seed");
                assert_eq!(fe_hex(x), expected[0].as_str().expect("seed x"));
                assert_eq!(fe_hex(y), expected[1].as_str().expect("seed y"));
            }
        }
        if mode != "shared_z" && mode != "joint_atlas" && mode != "linked_atlas" &&
           mode != "linked_twin" && mode != "linked_rho" &&
           mode != "portfolio" {
            assert_eq!(digits, digits_from_json(case));
            let expected_seeds = case["seed_affine"].as_array().expect("seeds");
            for (seed, expected) in seeds.iter().zip(expected_seeds) {
                let (x, y) = seed.to_affine().expect("prepared seed");
                assert_eq!(fe_hex(x), expected[0].as_str().expect("seed x"));
                assert_eq!(fe_hex(y), expected[1].as_str().expect("seed y"));
            }
        }
        if mode == "cached_projective" {
            let expected = &case["expected_counts"];
            for (key, actual) in [
                ("tau_steps", counts.tau_steps),
                ("tau_pairs", counts.tau_pairs),
                ("cheap_z_pairs", counts.cheap_z_pairs),
                ("mixed_adds", counts.mixed_adds),
                ("general_adds", counts.general_adds),
                ("first_insertions", counts.first_insertions),
                ("cache_entries", counts.cache_entries),
            ] {
                check_count(expected, key, actual);
            }
        }
    }
    if timed {
        println!("online_ms={elapsed_ms:.6} verified=1 curve=secp256k1 base_x={base_x} base_y={base_y} scalar={scalar_hex} point={actual_point} mode={mode}");
    } else {
        println!("verified=1 curve=secp256k1 base_x={base_x} base_y={base_y} scalar={scalar_hex} point={actual_point} mode={mode}");
    }
}

fn check_count(expected: &Value, key: &str, actual: usize) {
    let want = expected[key].as_u64().expect("expected count") as usize;
    assert_eq!(actual, want, "count {key}");
}

fn check_atlas_fixture(fixture_path: &str, seed_path: &str,
                       linked: bool, twin: bool, conjugate_rho: bool) {
    assert!(!(twin && conjugate_rho));
    assert!((!twin && !conjugate_rho) || linked);
    let raw = fs::read(fixture_path).expect("read scalar fixture");
    let fixture: Value = serde_json::from_slice(&raw).expect("parse scalar fixture");
    let seed_raw = fs::read(seed_path).expect("read alternate Sage seed fixture");
    let seed_fixture: Value = serde_json::from_slice(&seed_raw)
        .expect("parse alternate Sage seed fixture");
    let name = PathBuf::from(fixture_path).file_name().expect("fixture name")
        .to_str().expect("UTF-8 fixture name").to_owned();
    let seed_cases = seed_fixture["fixtures"][&name]["cases"].as_array()
        .expect("Sage alternate seeds for this fixture");
    let cases = fixture["cases"].as_array().expect("scalar cases");
    assert_eq!(cases.len(), seed_cases.len());
    assert_eq!(fixture["beta_hex"], seed_fixture["beta_hex"]);
    let beta = fe_from_hex(fixture["beta_hex"].as_str().expect("beta"));
    LazyLock::force(&LATTICE);
    if linked {
        LazyLock::force(&LINKED_DIGIT_TABLE);
    } else {
        LazyLock::force(&ALTERNATE_DIGIT_TABLE);
    }
    let mut total_m_plus_s = 0usize;
    let mut exceptional_adds = 0usize;
    for (case, seed_case) in cases.iter().zip(seed_cases) {
        assert_eq!(case["base_x_hex"], seed_case["base_x_hex"]);
        assert_eq!(case["scalar_hex"], seed_case["scalar_hex"]);
        let base = J::affine(
            fe_from_hex(case["base_x_hex"].as_str().expect("base x")),
            fe_from_hex(case["base_y_hex"].as_str().expect("base y")));
        let seeds = if conjugate_rho { prepare_linked_conjugate_rho(base, beta) }
                    else if twin { prepare_linked_twinned(base, beta) }
                    else if linked { prepare_linked(base, beta) }
                    else { prepare_alternate(base, beta) };
        let old_seeds = case["seed_affine"].as_array().expect("Sage old seeds");
        for (index, seed) in seeds.iter().enumerate() {
            let expected = if index == 5 {
                &seed_case["seed5"]
            } else if index == 6 {
                &seed_case["seed6"]
            } else if linked && index == 7 {
                &seed_case["seed7"]
            } else {
                &old_seeds[index]
            };
            let (x, y) = seed.to_affine().expect("nonidentity seed");
            assert_eq!(fe_hex(x), expected[0].as_str().expect("seed x"));
            assert_eq!(fe_hex(y), expected[1].as_str().expect("seed y"));
        }
        let scalar = big_from_hex(case["scalar_hex"].as_str().expect("scalar"));
        let (a, b) = short_representative(&scalar);
        assert_eq!(a, big_from_hex(case["short_a_hex"].as_str().expect("short a")));
        assert_eq!(b, big_from_hex(case["short_b_hex"].as_str().expect("short b")));
        let digits = if linked { recode_linked(a, b) }
                     else { recode_alternate(a, b) };
        let (point, counts) = evaluate(&digits, &seeds, beta);
        if case["expected_identity"].as_bool().unwrap_or(false) {
            assert!(point.is_identity());
        } else {
            let (x, y) = point.to_affine().expect("nonidentity output");
            assert_eq!(fe_hex(x), case["expected_x_hex"].as_str().expect("output x"));
            assert_eq!(fe_hex(y), case["expected_y_hex"].as_str().expect("output y"));
        }
        assert_eq!(counts.tau_steps + usize::from(!digits.is_empty()), digits.len());
        let solo = counts.tau_steps - 2 * counts.tau_pairs;
        total_m_plus_s += (if conjugate_rho { 68 } else if twin { 70 }
                           else if linked { 75 } else { 79 })
            + 10 * counts.tau_pairs + 6 * solo
            + 11 * counts.mixed_adds + 14 * counts.general_adds
            + 2 * counts.cache_entries;
        exceptional_adds += counts.exceptional_cached_adds;
    }
    println!("{{\"verified\":true,\"fixture\":\"{name}\",\"cases\":{},\"seed_checks\":{},\"output_checks\":{},\"source_M_plus_S\":{},\"exceptional_cached_adds\":{},\"cpu_speedup_claim\":null}}",
             cases.len(), 9 * cases.len(), cases.len(), total_m_plus_s,
             exceptional_adds);
}

#[cfg(test)]
mod shared_z_tests {
    use super::*;

    #[test]
    fn shared_z_matches_frozen_scalar_outputs() {
        let fixture = concat!(env!("CARGO_MANIFEST_DIR"), "/fresh-fixture.json");
        for index in [0, 31, 255] {
            check_benchmark_case("shared_z", fixture, index, false);
            mixed_radix::benchmark_zero_tau_case(fixture, index, false, true);
        }
    }
}

fn check_portfolio_fixture(fixture_path: &str, seed_path: &str,
                           score_path: &str) {
    let fixture: Value = serde_json::from_slice(&fs::read(fixture_path)
        .expect("read portfolio scalar fixture")).expect("parse scalar fixture");
    let seed_fixture: Value = serde_json::from_slice(&fs::read(seed_path)
        .expect("read portfolio Sage seed fixture")).expect("parse seed fixture");
    let scores: Value = serde_json::from_slice(&fs::read(score_path)
        .expect("read portfolio score fixture")).expect("parse score fixture");
    let name = PathBuf::from(fixture_path).file_name().expect("fixture name")
        .to_str().expect("UTF-8 fixture name").to_owned();
    let cases = fixture["cases"].as_array().expect("scalar cases");
    let seed_cases = seed_fixture["fixtures"][&name]["cases"].as_array()
        .expect("Sage seeds for fixture");
    assert_eq!(cases.len(), seed_cases.len());
    assert_eq!(fixture["beta_hex"], seed_fixture["beta_hex"]);
    let score_panel = scores["panels"].as_array().expect("score panels")
        .iter().find(|panel| panel["fixture"] == name);
    if let Some(panel) = score_panel {
        assert_eq!(panel["cases"].as_u64(), Some(cases.len() as u64));
    }
    let beta = fe_from_hex(fixture["beta_hex"].as_str().expect("beta"));
    LazyLock::force(&LATTICE);
    LazyLock::force(&DIGIT_TABLE);
    LazyLock::force(&ALTERNATE_DIGIT_TABLE);
    LazyLock::force(&LINKED_DIGIT_TABLE);
    let mut choices = [0usize; 3];
    let mut total_cost = 0usize;
    let mut active_steps = 0usize;
    let mut peak_carry_norm = 0i64;
    let mut exceptional_adds = 0usize;
    for (index, (case, seed_case)) in cases.iter().zip(seed_cases).enumerate() {
        assert_eq!(case["base_x_hex"], seed_case["base_x_hex"]);
        assert_eq!(case["scalar_hex"], seed_case["scalar_hex"]);
        let scalar = big_from_hex(case["scalar_hex"].as_str().expect("scalar"));
        let (a, b) = short_representative(&scalar);
        assert_eq!(a, big_from_hex(case["short_a_hex"].as_str().expect("short a")));
        assert_eq!(b, big_from_hex(case["short_b_hex"].as_str().expect("short b")));
        let plan = recode_portfolio(a.clone(), b.clone());
        assert_eq!(plan.streams[0], recode(a.clone(), b.clone()));
        assert_eq!(plan.streams[1], recode_alternate(a.clone(), b.clone()));
        assert_eq!(plan.streams[2], recode_linked(a, b));
        if let Some(panel) = score_panel {
            let expected = &panel["rows"][index];
            assert_eq!(expected["index"].as_u64(), Some(index as u64));
            for choice in 0..3 {
                assert_eq!(expected["costs"][choice].as_u64(),
                           Some(plan.costs[choice] as u64));
            }
            let chosen_name = ["original", "two_orbit", "three_orbit"][plan.choice];
            assert_eq!(expected["selected"].as_str(), Some(chosen_name));
        }
        choices[plan.choice] += 1;
        total_cost += plan.costs[plan.choice];
        active_steps += plan.active_steps;
        peak_carry_norm = peak_carry_norm.max(plan.peak_carry_norm);
        let base = J::affine(
            fe_from_hex(case["base_x_hex"].as_str().expect("base x")),
            fe_from_hex(case["base_y_hex"].as_str().expect("base y")));
        let seeds = prepare_choice(base, beta, plan.choice);
        let old_seeds = case["seed_affine"].as_array().expect("old Sage seeds");
        for (slot, seed) in seeds.iter().enumerate() {
            let expected = if plan.choice > 0 && slot == 5 {
                &seed_case["seed5"]
            } else if plan.choice > 0 && slot == 6 {
                &seed_case["seed6"]
            } else if plan.choice == 2 && slot == 7 {
                &seed_case["seed7"]
            } else {
                &old_seeds[slot]
            };
            let (x, y) = seed.to_affine().expect("nonidentity seed");
            assert_eq!(fe_hex(x), expected[0].as_str().expect("seed x"));
            assert_eq!(fe_hex(y), expected[1].as_str().expect("seed y"));
        }
        let digits = &plan.streams[plan.choice];
        let (point, counts) = evaluate(digits, &seeds, beta);
        exceptional_adds += counts.exceptional_cached_adds;
        if case["expected_identity"].as_bool().unwrap_or(false) {
            assert!(point.is_identity());
        } else {
            let (x, y) = point.to_affine().expect("nonidentity output");
            assert_eq!(fe_hex(x), case["expected_x_hex"].as_str().expect("output x"));
            assert_eq!(fe_hex(y), case["expected_y_hex"].as_str().expect("output y"));
        }
        if !digits.is_empty() {
            let prep = [83usize, 79, 75][plan.choice];
            let solo = counts.tau_steps - 2 * counts.tau_pairs;
            let charged = prep + 10 * counts.tau_pairs + 6 * solo
                + 11 * counts.mixed_adds + 14 * counts.general_adds
                + 2 * counts.cache_entries;
            assert_eq!(charged, plan.costs[plan.choice]);
        }
    }
    if let Some(panel) = score_panel {
        assert_eq!(panel["selected_total"].as_u64(), Some(total_cost as u64));
    }
    println!("{{\"verified\":true,\"fixture\":\"{name}\",\"cases\":{},\"digit_stream_checks\":{},\"seed_checks\":{},\"output_checks\":{},\"choices\":[{},{},{}],\"selected_M_plus_S\":{},\"active_carry_steps\":{},\"peak_carry_norm\":{},\"exceptional_cached_adds\":{},\"cpu_speedup_claim\":null}}",
             cases.len(), 3 * cases.len(), 9 * cases.len(), cases.len(),
             choices[0], choices[1], choices[2], total_cost, active_steps,
             peak_carry_norm, exceptional_adds);
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() == 3 && args[1] == "--check-coset-fastinv-fixture" {
        coset::check_fastinv_fixture(&args[2]);
        return;
    }
    if args.len() == 4 && (args[1] == "--benchmark-coset-fastinv-case" ||
                           args[1] == "--check-coset-fastinv-case") {
        coset::benchmark_case(&args[2], args[3].parse().expect("case index"),
                              args[1] == "--benchmark-coset-fastinv-case", true);
        return;
    }
    if args.len() == 4 && (args[1] == "--benchmark-coset-case" ||
                           args[1] == "--check-coset-case") {
        coset::benchmark_case(&args[2], args[3].parse().expect("case index"),
                              args[1] == "--benchmark-coset-case", false);
        return;
    }
    if args.len() == 5 && args[1] == "--check-coset-fixture" {
        coset::check_fixture(&args[2], &args[3], &args[4]);
        return;
    }
    if args.len() == 4 && args[1] == "--check-coset-streams" {
        coset::check_streams(&args[2], &args[3]);
        return;
    }
    if args.len() == 4 && (args[1] == "--benchmark-zero-tau-case" ||
                           args[1] == "--check-zero-tau-case" ||
                           args[1] == "--benchmark-shared-z-zero-tau-case" ||
                           args[1] == "--check-shared-z-zero-tau-case") {
        let index = args[3].parse::<usize>().expect("case index");
        mixed_radix::benchmark_zero_tau_case(&args[2], index,
            args[1] == "--benchmark-zero-tau-case" ||
            args[1] == "--benchmark-shared-z-zero-tau-case",
            args[1] == "--benchmark-shared-z-zero-tau-case" ||
            args[1] == "--check-shared-z-zero-tau-case");
        return;
    }
    if args.len() == 4 && args[1] == "--check-zero-tau-actions" {
        mixed_radix::check_zero_tau_action_fingerprints(&args[2], &args[3]);
        return;
    }
    if args.len() == 5 && args[1] == "--check-zero-tau-fixture" {
        mixed_radix::check_zero_tau_fixture(&args[2], &args[3], &args[4]);
        return;
    }
    if args.len() == 4 && (args[1] == "--benchmark-mixed-radix-case" ||
                           args[1] == "--check-mixed-radix-case") {
        let index = args[3].parse::<usize>().expect("case index");
        mixed_radix::benchmark_case(&args[2], index,
                                    args[1] == "--benchmark-mixed-radix-case");
        return;
    }
    if args.len() == 4 && args[1] == "--check-mixed-radix-actions" {
        mixed_radix::check_action_fingerprints(&args[2], &args[3]);
        return;
    }
    if args.len() == 5 && args[1] == "--check-mixed-radix-fixture" {
        mixed_radix::check_fixture(&args[2], &args[3], &args[4]);
        return;
    }
    if args.len() == 5 && args[1] == "--check-selective-fixture" {
        selective::check_fixture(&args[2], &args[3], &args[4]);
        return;
    }
    if args.len() == 4 && (args[1] == "--benchmark-selective-case" ||
                           args[1] == "--check-selective-case") {
        let index = args[3].parse::<usize>().expect("case index");
        selective::benchmark_case(&args[2], index,
                                  args[1] == "--benchmark-selective-case");
        return;
    }
    if args.len() == 5 && args[1] == "--check-portfolio-fixture" {
        check_portfolio_fixture(&args[2], &args[3], &args[4]);
        return;
    }
    if args.len() == 4 && (args[1] == "--check-alternate-fixture" ||
                           args[1] == "--check-linked-fixture" ||
                           args[1] == "--check-linked-twin-fixture" ||
                           args[1] == "--check-linked-rho-fixture") {
        check_atlas_fixture(&args[2], &args[3],
                            args[1] != "--check-alternate-fixture",
                            args[1] == "--check-linked-twin-fixture",
                            args[1] == "--check-linked-rho-fixture");
        return;
    }
    if args.len() == 5 && (args[1] == "--benchmark-case" ||
                           args[1] == "--check-benchmark-case") {
        let index = args[4].parse::<usize>().expect("case index");
        check_benchmark_case(&args[2], &args[3], index,
                             args[1] == "--benchmark-case");
        return;
    }
    if std::env::args().nth(1).as_deref() == Some("--check-exceptions") {
        check_exceptional_additions();
        return;
    }
    let fixture_path = std::env::args_os().nth(1).map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("fixture.json"));
    let raw = fs::read(&fixture_path).expect("read frozen fixture");
    let fixture: Value = serde_json::from_slice(&raw).expect("parse fixture");
    assert_eq!(fixture["schema"].as_u64(), Some(1));
    let beta = fe_from_hex(fixture["beta_hex"].as_str().expect("beta"));
    assert_eq!(beta.mul(&beta).mul(&beta), F::ONE);
    let cases = fixture["cases"].as_array().expect("fixture cases");
    let mut representative_checks = 0usize;
    let mut digit_checks = 0usize;
    let mut seed_checks = 0usize;
    let mut output_checks = 0usize;
    let mut exceptional_cached_adds = 0usize;
    for case in cases {
        let base = J::affine(
            fe_from_hex(case["base_x_hex"].as_str().expect("base x")),
            fe_from_hex(case["base_y_hex"].as_str().expect("base y")));
        let seeds = prepare(base, beta);
        let expected_seeds = case["seed_affine"].as_array().expect("seeds");
        assert_eq!(expected_seeds.len(), 9);
        for (seed, expected) in seeds.iter().zip(expected_seeds) {
            let (x, y) = seed.to_affine().expect("nonidentity seed");
            assert_eq!(fe_hex(x), expected[0].as_str().expect("seed x"));
            assert_eq!(fe_hex(y), expected[1].as_str().expect("seed y"));
            seed_checks += 1;
        }
        let scalar = big_from_hex(case["scalar_hex"].as_str().expect("scalar"));
        let (a, b) = short_representative(&scalar);
        assert_eq!(a, big_from_hex(case["short_a_hex"].as_str().expect("short a")));
        assert_eq!(b, big_from_hex(case["short_b_hex"].as_str().expect("short b")));
        representative_checks += 1;
        let digits = recode(a, b);
        assert_eq!(digits, digits_from_json(case));
        digit_checks += 1;
        let (out, counts) = evaluate(&digits, &seeds, beta);
        if case["expected_identity"].as_bool().unwrap_or(false) {
            assert!(out.is_identity(), "expected the curve identity");
            assert!(case["expected_x_hex"].is_null());
            assert!(case["expected_y_hex"].is_null());
        } else {
            let (x, y) = out.to_affine().expect("nonidentity output");
            assert_eq!(fe_hex(x), case["expected_x_hex"].as_str().expect("output x"));
            assert_eq!(fe_hex(y), case["expected_y_hex"].as_str().expect("output y"));
        }
        let expected_counts = &case["expected_counts"];
        for (key, value) in [
            ("tau_steps", counts.tau_steps),
            ("tau_pairs", counts.tau_pairs),
            ("cheap_z_pairs", counts.cheap_z_pairs),
            ("mixed_adds", counts.mixed_adds),
            ("general_adds", counts.general_adds),
            ("first_insertions", counts.first_insertions),
            ("cache_entries", counts.cache_entries),
        ] {
            check_count(expected_counts, key, value);
        }
        assert_eq!(counts.exceptional_cached_adds,
                   expected_counts["exceptional_cached_adds"].as_u64().unwrap_or(0) as usize);
        exceptional_cached_adds += counts.exceptional_cached_adds;
        output_checks += 1;
    }
    println!("{{\"verified\":true,\"cases\":{},\"representative_checks\":{},\"digit_checks\":{},\"seed_checks\":{},\"output_checks\":{},\"exceptional_cached_adds\":{},\"native_scope\":\"variable_time_scalar_input\",\"cpu_speedup_claim\":null}}",
             cases.len(), representative_checks, digit_checks, seed_checks, output_checks,
             exceptional_cached_adds);
}
