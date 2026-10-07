//! Native 256-bit replay of the cached-projective tau point path.
//!
//! Scalar reduction and recoding come from the frozen Sage fixture. This
//! executable checks every prepared seed, final point, and operation count.

#[path = "../../../suite/src/ct_bignum.rs"]
mod ct_bignum;
#[path = "../../../suite/src/ecc/secp256k1_field.rs"]
mod secp256k1_field;

use secp256k1_field::SecpFieldElement as F;
use serde_json::Value;
use std::fs;
use std::path::PathBuf;

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

    fn add_cached(self, q: Self, qz2: F, qz3: F) -> Self {
        assert!(!self.is_identity() && !q.is_identity());
        let z1_squared = self.z.sqr();
        let u1 = self.x.mul(&qz2);
        let u2 = q.x.mul(&z1_squared);
        let s1 = self.y.mul(&qz3);
        let s2 = q.y.mul(&self.z).mul(&z1_squared);
        let h = u2.sub(&u1);
        let r = s2.sub(&s1);
        assert!(h != F::ZERO, "exceptional cached addition");
        let hh = h.sqr();
        let hhh = h.mul(&hh);
        let v = u1.mul(&hh);
        let rx = r.sqr().sub(&hhh).sub(&twice(v));
        let ry = r.mul(&v.sub(&rx)).sub(&s1.mul(&hhh));
        let rz = self.z.mul(&q.z).mul(&h);
        Self { x: rx, y: ry, z: rz }
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

fn orbit(seed: J, beta: F) -> [J; 3] {
    let x1 = beta.mul(&seed.x);
    let x2 = seed.x.neg().sub(&x1);
    [seed,
     J { x: x1, y: seed.y, z: seed.z },
     J { x: x2, y: seed.y, z: seed.z }]
}

#[derive(Clone, Copy)]
struct Digit { seed: usize, power: usize, sign: i64 }

fn digits_from_json(case: &Value) -> Vec<Option<Digit>> {
    case["digits"].as_array().expect("digits array").iter().map(|raw| {
        if raw.is_null() { return None; }
        let word = raw.as_array().expect("digit tuple");
        assert_eq!(word.len(), 5);
        let seed = word[2].as_u64().expect("seed") as usize;
        let power = word[3].as_u64().expect("power") as usize;
        let sign = word[4].as_i64().expect("sign");
        assert!(seed < 9 && power < 3 && (sign == 1 || sign == -1));
        Some(Digit { seed, power, sign })
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
    first_insertions: usize,
    cache_entries: usize,
}

fn evaluate(digits: &[Option<Digit>], seeds: &[J; 9], beta: F) -> (J, Counts) {
    let mut counts = Counts::default();
    if digits.is_empty() { return (J::identity(), counts); }
    let images: [[J; 3]; 9] = std::array::from_fn(|i| orbit(seeds[i], beta));
    let mut cache: [Option<(F, F)>; 9] = [None; 9];
    for digit in digits.iter().take(digits.len() - 1).flatten() {
        if digit.seed > 0 && cache[digit.seed].is_none() {
            let z = seeds[digit.seed].z;
            let z2 = z.sqr();
            cache[digit.seed] = Some((z2, z2.mul(&z)));
            counts.cache_entries += 1;
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
            } else if d.seed == 0 {
                assert_eq!(q.z, F::ONE);
                accumulator = accumulator.add_mixed(q.x, q.y);
                counts.mixed_adds += 1;
            } else {
                let (z2, z3) = cache[d.seed].expect("cached seed powers");
                accumulator = accumulator.add_cached(q, z2, z3);
                counts.general_adds += 1;
            }
        }
        index -= 1;
    }
    assert_eq!(counts.tau_pairs, pairs);
    assert_eq!(gauge, 0);
    assert_eq!(counts.first_insertions, 1);
    (accumulator, counts)
}

fn check_count(expected: &Value, key: &str, actual: usize) {
    let want = expected[key].as_u64().expect("expected count") as usize;
    assert_eq!(actual, want, "count {key}");
}

fn main() {
    let fixture_path = std::env::args_os().nth(1).map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("fixture.json"));
    let raw = fs::read(&fixture_path).expect("read frozen fixture");
    let fixture: Value = serde_json::from_slice(&raw).expect("parse fixture");
    assert_eq!(fixture["schema"].as_u64(), Some(1));
    let beta = fe_from_hex(fixture["beta_hex"].as_str().expect("beta"));
    assert_eq!(beta.mul(&beta).mul(&beta), F::ONE);
    let cases = fixture["cases"].as_array().expect("fixture cases");
    let mut seed_checks = 0usize;
    let mut output_checks = 0usize;
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
        let digits = digits_from_json(case);
        let (out, counts) = evaluate(&digits, &seeds, beta);
        let (x, y) = out.to_affine().expect("nonidentity output");
        assert_eq!(fe_hex(x), case["expected_x_hex"].as_str().expect("output x"));
        assert_eq!(fe_hex(y), case["expected_y_hex"].as_str().expect("output y"));
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
        output_checks += 1;
    }
    println!("{{\"verified\":true,\"cases\":{},\"seed_checks\":{},\"output_checks\":{},\"native_scope\":\"point_path_only\",\"cpu_speedup_claim\":null}}",
             cases.len(), seed_checks, output_checks);
}
