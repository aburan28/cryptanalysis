//! Mixed-radix fixed-base tables quotiented by the six Eisenstein units.

use super::{
    batch_to_affine, hexagonal_four_corner_choices, BigInt, CompactPairPoint, Jacobian,
    Signed192, SCALAR_LATTICE,
};
use num_traits::{ToPrimitive, Zero};
use std::mem::size_of;
use std::sync::LazyLock;

const WIDTHS: [u8; 14] = [10, 10, 10, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9];
const WIDTHS15: [u8; 15] = [8, 8, 8, 8, 8, 8, 9, 9, 9, 9, 9, 9, 9, 9, 9];
const WIDTHS16: [u8; 16] = [8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 9];
const CAP_BYTES: usize = 90 * (1 << 20);
const RADIX13: usize = 943;
const RADIX13_WINDOWS: usize = 13;
const RADIX13_CAP_BYTES: usize = 140 * (1 << 20);
const TAU_BUCKET_RADIX: usize = 1021;
const TAU_BUCKET_CAP_BYTES: usize = 90 * (1 << 20);
const TAU_BUCKET_ATLAS: &[u8] = include_bytes!(
    "../../../../prime-j0-tau-bucket-orbits-20261009/atlas.bin"
);
const TAU_PAIR_CAP_BYTES: usize = 90 * (1 << 20);
const TAU_PAIR_ATLAS: &[u8] = include_bytes!(
    "../../../../prime-j0-tau-pair-buckets-20261009/atlas.bin"
);

fn norm((a, b): (i32, i32)) -> i64 {
    let (a, b) = (i64::from(a), i64::from(b));
    a * a + 3 * a * b + 3 * b * b
}

fn omega((a, b): (i32, i32)) -> (i32, i32) {
    (a + 3 * b, -a - 2 * b)
}

fn unit_images(pair: (i32, i32)) -> [(i32, i32); 6] {
    let mut images = [(0, 0); 6];
    let mut value = pair;
    for power in 0..3 {
        images[2 * power] = value;
        images[2 * power + 1] = (-value.0, -value.1);
        value = omega(value);
    }
    debug_assert_eq!(value, pair);
    debug_assert!(images.iter().all(|&image| norm(image) == norm(pair)));
    images
}

impl Signed192 {
    fn from_i32(value: i32) -> Self {
        Self {
            negative: value < 0,
            limbs: [u64::from(value.unsigned_abs()), 0, 0],
        }
    }

    fn rem_euclid_power_of_two(self, width: u8) -> usize {
        assert!((8..=10).contains(&width));
        let base = 1u64 << width;
        let remainder = self.limbs[0] & (base - 1);
        if self.negative && remainder != 0 {
            (base - remainder) as usize
        } else {
            remainder as usize
        }
    }

    fn div_exact_power_of_two(self, width: u8) -> Self {
        assert!((8..=10).contains(&width));
        let shift = u32::from(width);
        assert_eq!(self.limbs[0] & ((1u64 << shift) - 1), 0);
        let limbs: [u64; 3] = std::array::from_fn(|index| {
            (self.limbs[index] >> shift)
                | (if index + 1 < 3 { self.limbs[index + 1] << (64 - shift) } else { 0 })
        });
        Self {
            negative: self.negative && limbs != [0; 3],
            limbs,
        }
    }

    fn div_rem_small_radix(self, radix: u64) -> (Self, i32, usize) {
        assert!((2..=i32::MAX as u64).contains(&radix));
        // A 32-bit chunk leaves the trial dividend below radix*2^32,
        // so each step uses constant 64-bit division instead of u128 division.
        let mut rem = 0u64;
        let mut limbs = [0u64; 3];
        for index in (0..3).rev() {
            let high = self.limbs[index] >> 32;
            let value_high = (rem << 32) | high;
            let quotient_high = value_high / radix;
            rem = value_high % radix;
            let low = self.limbs[index] & u64::from(u32::MAX);
            let value_low = (rem << 32) | low;
            let quotient_low = value_low / radix;
            rem = value_low % radix;
            limbs[index] = (quotient_high << 32) | quotient_low;
        }
        let signed_rem = if self.negative { -(rem as i32) } else { rem as i32 };
        let quotient = Self { negative: self.negative && limbs != [0; 3], limbs };
        (quotient, signed_rem, signed_rem.rem_euclid(radix as i32) as usize)
    }

    fn div_rem_radix13(self) -> (Self, i32, usize) {
        self.div_rem_small_radix(RADIX13 as u64)
    }

    #[cfg(test)]
    fn rem_euclid_radix13(self) -> usize {
        self.div_rem_radix13().2
    }

    #[cfg(test)]
    fn div_exact_radix13(self) -> Self {
        let (quotient, signed_rem, _) = self.div_rem_radix13();
        assert_eq!(signed_rem, 0, "radix-943 word quotient is not integral");
        quotient
    }

    fn adjust_radix13_quotient(self, signed_rem: i32, digit: i32) -> Self {
        self.adjust_small_radix_quotient(signed_rem, digit, RADIX13 as i32)
    }

    fn adjust_small_radix_quotient(self, signed_rem: i32, digit: i32, radix: i32) -> Self {
        let adjustment = signed_rem - digit;
        assert_eq!(adjustment % radix, 0);
        self.add(Self::from_i32(adjustment / radix))
    }
}

fn nearest_digit((a, b): (i32, i32), base: i32) -> (i16, i16) {
    // The coordinates (u,v)=(a+b,-b) have norm u²-uv+v².
    let (u, v) = (a + b, -b);
    let (floor_u, floor_v) = (u.div_euclid(base), v.div_euclid(base));
    let mut best: Option<(i64, i32, i32)> = None;
    for m in [floor_u, floor_u + 1] {
        for n in [floor_v, floor_v + 1] {
            let (x, y) = (u - m * base, v - n * base);
            let digit = (x + y, -y);
            let candidate = (norm(digit), digit.0, digit.1);
            if best.is_none_or(|old| candidate < old) {
                best = Some(candidate);
            }
        }
    }
    let (squared_norm, da, db) = best.expect("four equilateral corners");
    assert!(3 * squared_norm <= i64::from(base) * i64::from(base));
    assert_eq!((da.rem_euclid(base), db.rem_euclid(base)), (a, b));
    (i16::try_from(da).unwrap(), i16::try_from(db).unwrap())
}

struct OrbitAtlas {
    width: u8,
    base: usize,
    codes: Box<[u32]>,
    digits: Box<[(i16, i16)]>,
}

impl OrbitAtlas {
    fn new(width: u8) -> Self {
        Self::with_base(width, 1usize << width)
    }

    fn new_radix(base: usize) -> Self {
        assert_eq!(base, RADIX13);
        Self::with_base(0, base)
    }

    fn with_base(width: u8, base: usize) -> Self {
        let mut codes = vec![u32::MAX; base * base];
        let mut digits = Vec::with_capacity((base * base + 8) / 6);
        for index in 0..base * base {
            if codes[index] != u32::MAX {
                continue;
            }
            let residue = ((index / base) as i32, (index % base) as i32);
            let orbit = unit_images(residue).map(|(a, b)| {
                (
                    a.rem_euclid(base as i32) as usize,
                    b.rem_euclid(base as i32) as usize,
                )
            });
            debug_assert_eq!(
                orbit.iter().copied().min(),
                Some((index / base, index % base))
            );
            let orbit_id = digits.len();
            digits.push(nearest_digit(residue, base as i32));
            for (unit_code, (a, b)) in orbit.into_iter().enumerate() {
                let slot = a * base + b;
                if codes[slot] == u32::MAX {
                    codes[slot] = u32::try_from((orbit_id << 3) | unit_code).unwrap();
                }
            }
        }
        assert_eq!(digits.len(), (base * base + 8) / 6);
        assert!(codes.iter().all(|&code| code != u32::MAX));
        assert_eq!(digits[0], (0, 0));
        Self {
            width,
            base,
            codes: codes.into_boxed_slice(),
            digits: digits.into_boxed_slice(),
        }
    }

    fn base(&self) -> usize {
        self.base
    }

    fn digit(&self, a: &BigInt, b: &BigInt) -> ((i32, i32), usize, usize) {
        let base = BigInt::from(self.base());
        let ra = ((a % &base + &base) % &base).to_usize().unwrap();
        let rb = ((b % &base + &base) % &base).to_usize().unwrap();
        self.digit_residue(ra, rb)
    }

    fn digit_word(&self, a: Signed192, b: Signed192) -> ((i32, i32), usize, usize) {
        let ra = a.rem_euclid_power_of_two(self.width);
        let rb = b.rem_euclid_power_of_two(self.width);
        self.digit_residue(ra, rb)
    }

    #[cfg(test)]
    fn digit_word_radix13(&self, a: Signed192, b: Signed192) -> ((i32, i32), usize, usize) {
        assert_eq!(self.base(), RADIX13);
        self.digit_residue(a.rem_euclid_radix13(), b.rem_euclid_radix13())
    }

    fn digit_residue(&self, ra: usize, rb: usize) -> ((i32, i32), usize, usize) {
        let code = self.codes[ra * self.base() + rb] as usize;
        let (orbit_id, unit_code) = (code >> 3, code & 7);
        assert!(unit_code < 6);
        let (da, db) = self.digits[orbit_id];
        let digit = unit_images((i32::from(da), i32::from(db)))[unit_code];
        debug_assert_eq!(
            (
                digit.0.rem_euclid(self.base() as i32) as usize,
                digit.1.rem_euclid(self.base() as i32) as usize
            ),
            (ra, rb)
        );
        (digit, orbit_id, unit_code)
    }
}

// The lexicographically first member of each six-unit orbit occupies three
// contiguous intervals per nonzero row. Rank it without a residue-code array.
struct ArithmeticOrbitAtlas {
    width: u8,
    digits: Box<[(i16, i16)]>,
}

impl ArithmeticOrbitAtlas {
    fn new(width: u8) -> Self {
        assert!((8..=10).contains(&width));
        let base = 1usize << width;
        let (q, r) = (base / 3, base % 3);
        let mut digits = Vec::with_capacity((base * base + 8) / 6);
        for b in 0..=base / 2 {
            digits.push(nearest_digit((0, b as i32), base as i32));
        }
        for a in 1..=q {
            for b in 0..=q - a {
                digits.push(nearest_digit((a as i32, b as i32), base as i32));
            }
            for b in q + 1..=2 * q + r - 1 - a {
                digits.push(nearest_digit((a as i32, b as i32), base as i32));
            }
            for b in 2 * q + r..=base - 1 - a {
                digits.push(nearest_digit((a as i32, b as i32), base as i32));
            }
        }
        assert_eq!(digits.len(), (base * base + 8) / 6);
        assert_eq!(digits[0], (0, 0));
        Self { width, digits: digits.into_boxed_slice() }
    }

    fn rank(width: u8, a: usize, b: usize) -> usize {
        let base = 1usize << width;
        let (q, r) = (base / 3, base % 3);
        if a == 0 {
            assert!(b <= base / 2);
            return b;
        }
        assert!(a <= q);
        let mut rank = base / 2 + 1 + (a - 1) * base - 3 * (a - 1) * a / 2;
        if b <= q - a {
            return rank + b;
        }
        rank += q - a + 1;
        if (q + 1..=2 * q + r - 1 - a).contains(&b) {
            return rank + b - (q + 1);
        }
        rank += q + r - 1 - a;
        assert!((2 * q + r..=base - 1 - a).contains(&b));
        rank + b - (2 * q + r)
    }

    fn digit_word(&self, a: Signed192, b: Signed192) -> ((i32, i32), usize, usize) {
        let ra = a.rem_euclid_power_of_two(self.width);
        let rb = b.rem_euclid_power_of_two(self.width);
        self.digit_residue(ra, rb)
    }

    fn digit_residue(&self, ra: usize, rb: usize) -> ((i32, i32), usize, usize) {
        let base = 1i32 << self.width;
        let mut value = (ra as i32, rb as i32);
        let mut best = ((usize::MAX, usize::MAX), usize::MAX);
        for power in 0..3 {
            for sign in 0..2 {
                let image = if sign == 0 { value } else { (-value.0, -value.1) };
                let image = (image.0.rem_euclid(base) as usize,
                             image.1.rem_euclid(base) as usize);
                let inverse_code = 2 * ((3 - power) % 3) + sign;
                best = best.min((image, inverse_code));
            }
            let rotated = omega(value);
            value = (rotated.0.rem_euclid(base), rotated.1.rem_euclid(base));
        }
        let (canonical, unit_code) = best;
        let orbit_id = Self::rank(self.width, canonical.0, canonical.1);
        let (da, db) = self.digits[orbit_id];
        let digit = unit_images((i32::from(da), i32::from(db)))[unit_code];
        debug_assert_eq!((digit.0.rem_euclid(base) as usize,
                          digit.1.rem_euclid(base) as usize), (ra, rb));
        (digit, orbit_id, unit_code)
    }
}

fn formula_digit_residue(width: u8, ra: usize, rb: usize) -> ((i32, i32), usize, usize) {
    assert!((8..=10).contains(&width));
    let base = 1i32 << width;
    let mask = base - 1;
    let (a, b) = (ra as i32, rb as i32);
    let rotated = [
        (a, b),
        ((a + 3 * b) & mask, (-a - 2 * b) & mask),
        ((-2 * a - 3 * b) & mask, (a + b) & mask),
    ];
    let mut best = ((usize::MAX, usize::MAX), usize::MAX);
    for (power, &(x, y)) in rotated.iter().enumerate() {
        for sign in 0..2 {
            let image = if sign == 0 { (x, y) }
                        else { ((-x) & mask, (-y) & mask) };
            let inverse_code = 2 * ((3 - power) % 3) + sign;
            best = best.min(((image.0 as usize, image.1 as usize), inverse_code));
        }
    }
    let (canonical, unit_code) = best;
    let orbit_id = ArithmeticOrbitAtlas::rank(width, canonical.0, canonical.1);
    let canonical_digit = nearest_digit((canonical.0 as i32, canonical.1 as i32), base);
    let digit = unit_images((i32::from(canonical_digit.0),
                             i32::from(canonical_digit.1)))[unit_code];
    debug_assert_eq!((digit.0 & mask, digit.1 & mask), (a, b));
    (digit, orbit_id, unit_code)
}

fn formula_digit_word(width: u8, a: Signed192, b: Signed192) -> ((i32, i32), usize, usize) {
    formula_digit_residue(width, a.rem_euclid_power_of_two(width),
                          b.rem_euclid_power_of_two(width))
}

fn sector_canonical_digit(width: u8, a: usize, b: usize) -> (i16, i16) {
    let base = 1usize << width;
    let (q, r) = (base / 3, base % 3);
    let (da, db) = if a == 0 {
        if b <= q { (0, b as i32) } else { (-(base as i32), b as i32) }
    } else if b <= q - a {
        (a as i32, b as i32)
    } else if b <= 2 * q + r - 1 - a {
        (a as i32 - base as i32, b as i32)
    } else {
        (a as i32, b as i32 - base as i32)
    };
    (i16::try_from(da).unwrap(), i16::try_from(db).unwrap())
}

fn sector_digit_residue(width: u8, ra: usize, rb: usize) -> ((i32, i32), usize, usize) {
    assert!((8..=10).contains(&width));
    let base = 1i32 << width;
    let mask = base - 1;
    let (a, b) = (ra as i32, rb as i32);
    let rotated = [
        (a, b),
        ((a + 3 * b) & mask, (-a - 2 * b) & mask),
        ((-2 * a - 3 * b) & mask, (a + b) & mask),
    ];
    let mut best = ((usize::MAX, usize::MAX), usize::MAX);
    for (power, &(x, y)) in rotated.iter().enumerate() {
        for sign in 0..2 {
            let image = if sign == 0 { (x, y) }
                        else { ((-x) & mask, (-y) & mask) };
            let inverse_code = 2 * ((3 - power) % 3) + sign;
            best = best.min(((image.0 as usize, image.1 as usize), inverse_code));
        }
    }
    let (canonical, unit_code) = best;
    let orbit_id = ArithmeticOrbitAtlas::rank(width, canonical.0, canonical.1);
    let canonical_digit = sector_canonical_digit(width, canonical.0, canonical.1);
    let digit = unit_images((i32::from(canonical_digit.0),
                             i32::from(canonical_digit.1)))[unit_code];
    debug_assert_eq!((digit.0 & mask, digit.1 & mask), (a, b));
    (digit, orbit_id, unit_code)
}

fn sector_digit_word(width: u8, a: Signed192, b: Signed192) -> ((i32, i32), usize, usize) {
    sector_digit_residue(width, a.rem_euclid_power_of_two(width),
                         b.rem_euclid_power_of_two(width))
}

fn affine_multiples(base: Jacobian, max_abs: usize) -> Vec<Jacobian> {
    let base = base.into_affine();
    let mut projective = Vec::with_capacity(max_abs);
    let mut point = base;
    for index in 1..=max_abs {
        projective.push(point);
        if index != max_abs {
            point = point.add_mixed(base);
        }
    }
    let mut result = Vec::with_capacity(max_abs + 1);
    result.push(Jacobian::identity());
    result.extend(batch_to_affine(&projective));
    result
}

fn build_window(digits: &[(i16, i16)], base: Jacobian) -> Box<[CompactPairPoint]> {
    let tau_base = base.tau();
    let max_a = digits
        .iter()
        .map(|d| d.0.unsigned_abs() as usize)
        .max()
        .unwrap();
    let max_b = digits
        .iter()
        .map(|d| d.1.unsigned_abs() as usize)
        .max()
        .unwrap();
    let a_multiples = affine_multiples(base, max_a);
    let b_multiples = affine_multiples(tau_base, max_b);
    let mut projective = Vec::with_capacity(digits.len() - 1);
    for &(a, b) in digits.iter().skip(1) {
        let first = if a >= 0 {
            a_multiples[a as usize]
        } else {
            a_multiples[a.unsigned_abs() as usize].neg()
        };
        let second = if b >= 0 {
            b_multiples[b as usize]
        } else {
            b_multiples[b.unsigned_abs() as usize].neg()
        };
        let point = if a == 0 {
            second
        } else if b == 0 {
            first
        } else {
            first.add_mixed(second)
        };
        assert!(!point.is_identity());
        projective.push(point);
    }
    let affine = batch_to_affine(&projective);
    let identity_slot = CompactPairPoint {
        limbs: [[0; 2]; 4],
        signs: 0,
    };
    let mut packed = Vec::with_capacity(digits.len());
    packed.push(identity_slot);
    packed.extend(affine.into_iter().map(CompactPairPoint::from_affine));
    packed.into_boxed_slice()
}

struct Tables {
    widths: &'static [u8],
    atlases: [Option<OrbitAtlas>; 3],
    windows: Vec<Box<[CompactPairPoint]>>,
    retained_bytes: usize,
}

impl Tables {
    fn new() -> Self {
        Self::with_widths(&WIDTHS)
    }

    fn with_widths(widths: &'static [u8]) -> Self {
        assert_eq!(size_of::<CompactPairPoint>(), 72);
        assert!(widths.iter().all(|width| (8..=10).contains(width)));
        assert_eq!(
            widths
                .iter()
                .map(|&width| usize::from(width))
                .sum::<usize>(),
            129
        );
        let atlases: [Option<OrbitAtlas>; 3] = std::array::from_fn(|index| {
            let width = 8 + index as u8;
            widths.contains(&width).then(|| OrbitAtlas::new(width))
        });
        let mut windows = Vec::with_capacity(widths.len());
        let mut base = Jacobian::generator();
        for &width in widths {
            let atlas = atlases[usize::from(width - 8)].as_ref().unwrap();
            windows.push(build_window(&atlas.digits, base));
            for _ in 0..width {
                base = base.double();
            }
        }
        let entries: usize = windows.iter().map(|row| row.len()).sum();
        assert_eq!(
            entries,
            widths
                .iter()
                .map(|&width| {
                    let base = 1usize << width;
                    (base * base + 8) / 6
                })
                .sum::<usize>()
        );
        let retained_bytes = entries * size_of::<CompactPairPoint>()
            + atlases
                .iter()
                .flatten()
                .map(|atlas| {
                    atlas.codes.len() * size_of::<u32>()
                        + atlas.digits.len() * size_of::<(i16, i16)>()
                })
                .sum::<usize>()
            + size_of::<Self>()
            + windows.capacity() * size_of::<Box<[CompactPairPoint]>>();
        assert!(retained_bytes < CAP_BYTES);
        Self {
            widths,
            atlases,
            windows,
            retained_bytes,
        }
    }

    fn atlas(&self, width: u8) -> &OrbitAtlas {
        self.atlases[usize::from(width - 8)].as_ref().unwrap()
    }
}

static TABLES: LazyLock<Tables> = LazyLock::new(Tables::new);
static TABLES15: LazyLock<Tables> = LazyLock::new(|| Tables::with_widths(&WIDTHS15));
static TABLES16: LazyLock<Tables> = LazyLock::new(|| Tables::with_widths(&WIDTHS16));

#[derive(Clone, Copy)]
struct U256Affine {
    x: super::U256,
    y: super::U256,
}

#[derive(Clone, Copy)]
struct U256Jacobian {
    x: super::U256,
    y: super::U256,
    z: super::U256,
}

fn u256_add(a: super::U256, b: super::U256) -> super::U256 {
    a.add_mod(&b, &super::HYBRID_FIELD.0.n)
}

fn u256_sub(a: super::U256, b: super::U256) -> super::U256 {
    a.sub_mod(&b, &super::HYBRID_FIELD.0.n)
}

fn u256_mul(a: super::U256, b: super::U256) -> super::U256 {
    super::HYBRID_FIELD.0.mont_mul(&a, &b)
}

fn u256_square(a: super::U256) -> super::U256 {
    super::HYBRID_FIELD.0.mont_sqr(&a)
}

static U256_BETA_UNITS: LazyLock<[super::U256; 3]> = LazyLock::new(|| {
    let ctx = &super::HYBRID_FIELD.0;
    let beta = super::U256::from_biguint(
        &super::DECODE_CONSTANTS.1.to_biguint().expect("positive cube root"));
    let omega = ctx.to_montgomery(&beta);
    [ctx.r_mod_n, omega, ctx.mont_sqr(&omega)]
});

impl U256Affine {
    fn unit(self, code: usize) -> Self {
        assert!(code < 6);
        let power = code / 2;
        let x = if power == 0 { self.x } else {
            u256_mul(self.x, U256_BETA_UNITS[power])
        };
        let y = if code & 1 == 0 { self.y } else {
            u256_sub(super::U256::ZERO, self.y)
        };
        Self { x, y }
    }
}

impl U256Jacobian {
    fn identity() -> Self {
        Self { x: super::U256::ZERO, y: super::HYBRID_FIELD.0.r_mod_n,
               z: super::U256::ZERO }
    }

    fn from_affine(point: U256Affine) -> Self {
        Self { x: point.x, y: point.y, z: super::HYBRID_FIELD.0.r_mod_n }
    }

    fn is_identity(self) -> bool {
        bool::from(self.z.ct_is_zero())
    }

    fn rotate_power(self, power: usize) -> Self {
        assert!(power < 3);
        if power == 0 || self.is_identity() {
            return self;
        }
        Self { x: u256_mul(self.x, U256_BETA_UNITS[power]), ..self }
    }

    fn double(self) -> Self {
        if self.is_identity() || bool::from(self.y.ct_is_zero()) {
            return Self::identity();
        }
        let a = u256_square(self.x);
        let b = u256_square(self.y);
        let c = u256_square(b);
        let d = u256_sub(u256_sub(u256_square(u256_add(self.x, b)), a), c);
        let d = u256_add(d, d);
        let e = u256_add(u256_add(a, a), a);
        let rx = u256_sub(u256_square(e), u256_add(d, d));
        let c2 = u256_add(c, c);
        let c4 = u256_add(c2, c2);
        let c8 = u256_add(c4, c4);
        let ry = u256_sub(u256_mul(e, u256_sub(d, rx)), c8);
        let yz = u256_mul(self.y, self.z);
        let rz = u256_add(yz, yz);
        Self { x: rx, y: ry, z: rz }
    }

    fn add_mixed(self, q: U256Affine) -> Self {
        if self.is_identity() {
            return Self::from_affine(q);
        }
        let zz = u256_square(self.z);
        let u = u256_mul(q.x, zz);
        let s = u256_mul(q.y, u256_mul(self.z, zz));
        let h = u256_sub(u, self.x);
        let v = u256_sub(s, self.y);
        if bool::from(h.ct_is_zero()) {
            return if bool::from(v.ct_is_zero()) { self.double() }
                   else { Self::identity() };
        }
        let hh = u256_square(h);
        let hhh = u256_mul(hh, h);
        let xhh = u256_mul(self.x, hh);
        let rx = u256_sub(u256_sub(u256_square(v), hhh), u256_add(xhh, xhh));
        let ry = u256_sub(u256_mul(v, u256_sub(xhh, rx)), u256_mul(self.y, hhh));
        let rz = u256_mul(self.z, h);
        Self { x: rx, y: ry, z: rz }
    }

    fn affine_hex_binary_inverse(self) -> String {
        if self.is_identity() { return "identity".to_owned(); }
        let ctx = &super::HYBRID_FIELD.0;
        let inverse = super::hybrid_binary_invert(self.z, ctx);
        let square = ctx.mont_sqr(&inverse);
        let cube = ctx.mont_mul(&square, &inverse);
        let x = ctx.mont_mul(&self.x, &square);
        let y = ctx.mont_mul(&self.y, &cube);
        format!("{}:{}", hex::encode(ctx.from_montgomery(&x).to_bytes_be()),
                hex::encode(ctx.from_montgomery(&y).to_bytes_be()))
    }
}

struct U256Tables {
    atlases: [Option<OrbitAtlas>; 3],
    windows: Vec<Box<[U256Affine]>>,
    retained_bytes: usize,
}

fn build_u256_window(digits: &[(i16, i16)], base: Jacobian) -> Box<[U256Affine]> {
    build_window(digits, base).iter().enumerate().map(|(index, &packed)| {
        if index == 0 {
            U256Affine { x: super::U256::ZERO, y: super::U256::ZERO }
        } else {
            let point = packed.into_affine();
            U256Affine { x: super::hybrid_pair_mont(point.x),
                         y: super::hybrid_pair_mont(point.y) }
        }
    }).collect::<Vec<_>>().into_boxed_slice()
}

impl U256Tables {
    fn new() -> Self {
        assert_eq!(size_of::<U256Affine>(), 64);
        let atlases: [Option<OrbitAtlas>; 3] = std::array::from_fn(|index| {
            let width = 8 + index as u8;
            WIDTHS.contains(&width).then(|| OrbitAtlas::new(width))
        });
        let mut windows = Vec::with_capacity(WIDTHS.len());
        let mut base = Jacobian::generator();
        for &width in &WIDTHS {
            let atlas = atlases[usize::from(width - 8)].as_ref().unwrap();
            windows.push(build_u256_window(&atlas.digits, base));
            for _ in 0..width { base = base.double(); }
        }
        let entries = windows.iter().map(|row| row.len()).sum::<usize>();
        assert_eq!(entries, WIDTHS.iter().map(|&width| {
            let radix = 1usize << width;
            (radix * radix + 8) / 6
        }).sum::<usize>());
        let retained_bytes = entries * size_of::<U256Affine>()
            + atlases.iter().flatten().map(|atlas| {
                atlas.codes.len() * size_of::<u32>()
                    + atlas.digits.len() * size_of::<(i16, i16)>()
            }).sum::<usize>()
            + size_of::<Self>()
            + windows.capacity() * size_of::<Box<[U256Affine]>>();
        assert!(retained_bytes < CAP_BYTES);
        Self { atlases, windows, retained_bytes }
    }

    fn atlas(&self, width: u8) -> &OrbitAtlas {
        self.atlases[usize::from(width - 8)].as_ref().unwrap()
    }
}

static U256_TABLES: LazyLock<U256Tables> = LazyLock::new(U256Tables::new);

struct ArithmeticU256Tables {
    atlases: [Option<ArithmeticOrbitAtlas>; 3],
    windows: Vec<Box<[U256Affine]>>,
    retained_bytes: usize,
}

impl ArithmeticU256Tables {
    fn new() -> Self {
        let atlases: [Option<ArithmeticOrbitAtlas>; 3] = std::array::from_fn(|index| {
            let width = 8 + index as u8;
            WIDTHS.contains(&width).then(|| ArithmeticOrbitAtlas::new(width))
        });
        let mut windows = Vec::with_capacity(WIDTHS.len());
        let mut base = Jacobian::generator();
        for &width in &WIDTHS {
            let atlas = atlases[usize::from(width - 8)].as_ref().unwrap();
            windows.push(build_u256_window(&atlas.digits, base));
            for _ in 0..width { base = base.double(); }
        }
        let entries = windows.iter().map(|row| row.len()).sum::<usize>();
        let retained_bytes = entries * size_of::<U256Affine>()
            + atlases.iter().flatten().map(|atlas| {
                atlas.digits.len() * size_of::<(i16, i16)>()
            }).sum::<usize>()
            + size_of::<Self>()
            + windows.capacity() * size_of::<Box<[U256Affine]>>();
        assert!(retained_bytes < CAP_BYTES);
        Self { atlases, windows, retained_bytes }
    }

    fn atlas(&self, width: u8) -> &ArithmeticOrbitAtlas {
        self.atlases[usize::from(width - 8)].as_ref().unwrap()
    }
}

static ARITHMETIC_U256_TABLES: LazyLock<ArithmeticU256Tables> =
    LazyLock::new(ArithmeticU256Tables::new);

struct FormulaU256Tables {
    windows: Vec<Box<[U256Affine]>>,
    retained_bytes: usize,
}

impl FormulaU256Tables {
    fn new() -> Self {
        Self::with_widths(&WIDTHS)
    }

    fn with_widths(widths: &[u8]) -> Self {
        let temporary_atlases: [Option<ArithmeticOrbitAtlas>; 3] =
            std::array::from_fn(|index| {
                let width = 8 + index as u8;
                widths.contains(&width).then(|| ArithmeticOrbitAtlas::new(width))
            });
        let mut windows = Vec::with_capacity(widths.len());
        let mut base = Jacobian::generator();
        for &width in widths {
            let atlas = temporary_atlases[usize::from(width - 8)].as_ref().unwrap();
            windows.push(build_u256_window(&atlas.digits, base));
            for _ in 0..width { base = base.double(); }
        }
        let entries = windows.iter().map(|row| row.len()).sum::<usize>();
        let retained_bytes = entries * size_of::<U256Affine>()
            + size_of::<Self>()
            + windows.capacity() * size_of::<Box<[U256Affine]>>();
        assert!(retained_bytes < CAP_BYTES);
        Self { windows, retained_bytes }
    }
}

static FORMULA_U256_TABLES: LazyLock<FormulaU256Tables> =
    LazyLock::new(FormulaU256Tables::new);
static SECTOR_U256_TABLES: LazyLock<FormulaU256Tables> =
    LazyLock::new(FormulaU256Tables::new);
static SECTOR15_U256_TABLES: LazyLock<FormulaU256Tables> =
    LazyLock::new(|| FormulaU256Tables::with_widths(&WIDTHS15));
static SECTOR16_U256_TABLES: LazyLock<FormulaU256Tables> =
    LazyLock::new(|| FormulaU256Tables::with_widths(&WIDTHS16));

struct Radix13Tables {
    atlas: OrbitAtlas,
    windows: Vec<Box<[CompactPairPoint]>>,
    retained_bytes: usize,
}

impl Radix13Tables {
    fn new() -> Self {
        let atlas = OrbitAtlas::new_radix(RADIX13);
        assert_eq!(atlas.digits.len(), 148_209);
        let mut windows = Vec::with_capacity(RADIX13_WINDOWS);
        let mut base = Jacobian::generator();
        for index in 0..RADIX13_WINDOWS {
            windows.push(build_window(&atlas.digits, base));
            if index + 1 < RADIX13_WINDOWS {
                base = affine_multiples(base, RADIX13).pop().unwrap();
            }
        }
        let entries = windows.iter().map(|row| row.len()).sum::<usize>();
        assert_eq!(entries, 1_926_717);
        let retained_bytes = entries * size_of::<CompactPairPoint>()
            + atlas.codes.len() * size_of::<u32>()
            + atlas.digits.len() * size_of::<(i16, i16)>()
            + size_of::<Self>()
            + windows.capacity() * size_of::<Box<[CompactPairPoint]>>();
        assert!(retained_bytes < RADIX13_CAP_BYTES);
        Self { atlas, windows, retained_bytes }
    }
}

static RADIX13_TABLES: LazyLock<Radix13Tables> = LazyLock::new(Radix13Tables::new);

struct TauBucketAtlas {
    codes: &'static [u8],
    digits: &'static [u8],
    seed_count: usize,
    max_exponent: usize,
}

impl TauBucketAtlas {
    fn from_bytes(bytes: &'static [u8], magic: &[u8; 4],
                  expected_seeds: usize, max_exponent: usize) -> Self {
        assert_eq!(&bytes[..4], magic);
        let read_u32 = |offset: usize| {
            u32::from_le_bytes(bytes[offset..offset + 4].try_into().unwrap()) as usize
        };
        assert_eq!(read_u32(4), TAU_BUCKET_RADIX);
        let code_count = read_u32(8);
        let seed_count = read_u32(12);
        assert_eq!(code_count, TAU_BUCKET_RADIX * TAU_BUCKET_RADIX);
        assert_eq!(seed_count, expected_seeds);
        assert_eq!(bytes.len(), 16 + 4 * code_count + 4 * seed_count);
        let codes = &bytes[16..16 + 4 * code_count];
        let digits = &bytes[16 + 4 * code_count..];
        assert_eq!(&digits[..4], &[0, 0, 0, 0]);
        let atlas = Self { codes, digits, seed_count, max_exponent };
        for residue in 0..code_count {
            let (digit, _, _, _) = atlas.digit_residue(residue / TAU_BUCKET_RADIX,
                                                        residue % TAU_BUCKET_RADIX);
            assert!(norm(digit) <= 840 * 840);
        }
        atlas
    }

    fn seed_digits(&self) -> Vec<(i16, i16)> {
        self.digits.chunks_exact(4).map(|chunk| {
            (i16::from_le_bytes(chunk[..2].try_into().unwrap()),
             i16::from_le_bytes(chunk[2..].try_into().unwrap()))
        }).collect()
    }

    fn digit_residue(&self, ra: usize, rb: usize) -> ((i32, i32), usize, usize, usize) {
        let offset = 4 * (ra * TAU_BUCKET_RADIX + rb);
        let code = u32::from_le_bytes(self.codes[offset..offset + 4].try_into().unwrap()) as usize;
        let (seed_id, exponent, unit_code) = (code >> 5, (code >> 3) & 3, code & 7);
        assert!(seed_id < self.seed_count && exponent <= self.max_exponent && unit_code < 6);
        let offset = 4 * seed_id;
        let seed = &self.digits[offset..offset + 4];
        let (a, b) = (i16::from_le_bytes(seed[..2].try_into().unwrap()),
                      i16::from_le_bytes(seed[2..].try_into().unwrap()));
        let mut digit = (i32::from(a), i32::from(b));
        for _ in 0..exponent {
            digit = (-3 * digit.1, digit.0 + 3 * digit.1);
        }
        digit = unit_images(digit)[unit_code];
        assert_eq!((digit.0.rem_euclid(TAU_BUCKET_RADIX as i32) as usize,
                    digit.1.rem_euclid(TAU_BUCKET_RADIX as i32) as usize),
                   (ra, rb));
        (digit, seed_id, exponent, unit_code)
    }
}

struct TauBucketTables {
    atlas: TauBucketAtlas,
    windows: Vec<Box<[CompactPairPoint]>>,
    retained_bytes: usize,
}

impl TauBucketTables {
    fn new() -> Self {
        Self::from_bytes(TAU_BUCKET_ATLAS, b"TBO1", 78_104, 2, TAU_BUCKET_CAP_BYTES)
    }

    fn new_pair() -> Self {
        Self::from_bytes(TAU_PAIR_ATLAS, b"TBP1", 93_777, 1, TAU_PAIR_CAP_BYTES)
    }

    fn from_bytes(bytes: &'static [u8], magic: &[u8; 4],
                  expected_seeds: usize, max_exponent: usize, cap: usize) -> Self {
        let atlas = TauBucketAtlas::from_bytes(bytes, magic, expected_seeds, max_exponent);
        let seed_digits = atlas.seed_digits();
        let mut windows = Vec::with_capacity(RADIX13_WINDOWS);
        let mut base = Jacobian::generator();
        for index in 0..RADIX13_WINDOWS {
            windows.push(build_window(&seed_digits, base));
            if index + 1 < RADIX13_WINDOWS {
                base = affine_multiples(base, TAU_BUCKET_RADIX).pop().unwrap();
            }
        }
        let entries = windows.iter().map(|row| row.len()).sum::<usize>();
        assert_eq!(entries, RADIX13_WINDOWS * expected_seeds);
        let retained_bytes = entries * size_of::<CompactPairPoint>()
            + bytes.len()
            + size_of::<Self>()
            + windows.capacity() * size_of::<Box<[CompactPairPoint]>>();
        assert!(retained_bytes < cap);
        Self { atlas, windows, retained_bytes }
    }
}

static TAU_BUCKET_TABLES: LazyLock<TauBucketTables> = LazyLock::new(TauBucketTables::new);
static TAU_PAIR_TABLES: LazyLock<TauBucketTables> = LazyLock::new(TauBucketTables::new_pair);

fn multiply_radix13(
    scalar: &BigInt,
) -> (Jacobian, BigInt, BigInt, usize, usize) {
    let lattice = &*SCALAR_LATTICE;
    let residue = ((scalar % &lattice.n) + &lattice.n) % &lattice.n;
    let (mut a, mut b) = hexagonal_four_corner_choices(&residue).remove(0);
    let (start_a, start_b) = (a.clone(), b.clone());
    let tables = &*RADIX13_TABLES;
    let base = BigInt::from(RADIX13);
    let mut result = Jacobian::identity();
    let mut nonidentity = 0usize;
    for row in &tables.windows {
        let (digit, orbit_id, unit_code) = tables.atlas.digit(&a, &b);
        a = (a - digit.0) / &base;
        b = (b - digit.1) / &base;
        if orbit_id == 0 {
            continue;
        }
        let mut addend = row[orbit_id].into_affine();
        for _ in 0..(unit_code / 2) {
            addend = addend.omega();
        }
        if unit_code & 1 != 0 {
            addend = addend.neg();
        }
        result = result.add_mixed(addend);
        nonidentity += 1;
    }
    assert!(a.is_zero() && b.is_zero(), "radix-943 recoding did not terminate");
    (result, start_a, start_b, nonidentity.saturating_sub(1), tables.retained_bytes)
}

fn multiply_word_radix13(
    scalar: &BigInt,
) -> (Jacobian, BigInt, BigInt, usize, usize) {
    let lattice = &*SCALAR_LATTICE;
    let residue = ((scalar % &lattice.n) + &lattice.n) % &lattice.n;
    let (start_a, start_b) = hexagonal_four_corner_choices(&residue).remove(0);
    let mut a = Signed192::from_bigint(&start_a);
    let mut b = Signed192::from_bigint(&start_b);
    let tables = &*RADIX13_TABLES;
    let mut result = Jacobian::identity();
    let mut nonidentity = 0usize;
    for row in &tables.windows {
        let (quotient_a, signed_rem_a, residue_a) = a.div_rem_radix13();
        let (quotient_b, signed_rem_b, residue_b) = b.div_rem_radix13();
        let (digit, orbit_id, unit_code) = tables.atlas.digit_residue(residue_a, residue_b);
        a = quotient_a.adjust_radix13_quotient(signed_rem_a, digit.0);
        b = quotient_b.adjust_radix13_quotient(signed_rem_b, digit.1);
        if orbit_id == 0 {
            continue;
        }
        let mut addend = row[orbit_id].into_affine();
        for _ in 0..(unit_code / 2) {
            addend = addend.omega();
        }
        if unit_code & 1 != 0 {
            addend = addend.neg();
        }
        result = result.add_mixed(addend);
        nonidentity += 1;
    }
    assert!(a.is_zero() && b.is_zero(), "word radix-943 recoding did not terminate");
    (result, start_a, start_b, nonidentity.saturating_sub(1), tables.retained_bytes)
}

fn multiply_tau_bucket(
    scalar: &BigInt,
) -> (Jacobian, BigInt, BigInt, usize, usize) {
    multiply_tau_orbit(scalar, &TAU_BUCKET_TABLES)
}

fn multiply_tau_pair(
    scalar: &BigInt,
) -> (Jacobian, BigInt, BigInt, usize, usize) {
    multiply_tau_orbit(scalar, &TAU_PAIR_TABLES)
}

fn multiply_tau_orbit(
    scalar: &BigInt,
    tables: &TauBucketTables,
) -> (Jacobian, BigInt, BigInt, usize, usize) {
    let lattice = &*SCALAR_LATTICE;
    let residue = ((scalar % &lattice.n) + &lattice.n) % &lattice.n;
    let (start_a, start_b) = hexagonal_four_corner_choices(&residue).remove(0);
    let mut a = Signed192::from_bigint(&start_a);
    let mut b = Signed192::from_bigint(&start_b);
    let mut buckets = [Jacobian::identity(); 3];
    let mut nonidentity = 0usize;
    for row in &tables.windows {
        let (quotient_a, signed_rem_a, residue_a) =
            a.div_rem_small_radix(TAU_BUCKET_RADIX as u64);
        let (quotient_b, signed_rem_b, residue_b) =
            b.div_rem_small_radix(TAU_BUCKET_RADIX as u64);
        let (digit, seed_id, exponent, unit_code) =
            tables.atlas.digit_residue(residue_a, residue_b);
        a = quotient_a.adjust_small_radix_quotient(
            signed_rem_a, digit.0, TAU_BUCKET_RADIX as i32);
        b = quotient_b.adjust_small_radix_quotient(
            signed_rem_b, digit.1, TAU_BUCKET_RADIX as i32);
        if seed_id == 0 {
            continue;
        }
        let mut addend = row[seed_id].into_affine();
        for _ in 0..(unit_code / 2) {
            addend = addend.omega();
        }
        if unit_code & 1 != 0 {
            addend = addend.neg();
        }
        buckets[exponent] = buckets[exponent].add_mixed(addend);
        nonidentity += 1;
    }
    assert!(a.is_zero() && b.is_zero(), "tau-bucket recoding did not terminate");
    let merge = |left: Jacobian, right: Jacobian| {
        if left.is_identity() {
            return right;
        }
        if right.is_identity() {
            return left;
        }
        let z_squared = right.z.mul(right.z);
        let z_cubed = z_squared.mul(right.z);
        left.add_cached(right, z_squared, z_cubed)
    };
    // The two-bucket format uses one tau map. The three-bucket format
    // folds B0 + tau*B1 + tau^2*B2 = B0 + tau*(B1 + tau*B2).
    let inner = if tables.atlas.max_exponent == 1 {
        buckets[1]
    } else {
        merge(buckets[1], buckets[2].tau())
    };
    let result = merge(buckets[0], inner.tau());
    (result, start_a, start_b, nonidentity.saturating_sub(1), tables.retained_bytes)
}

fn selected(format: u8) -> &'static Tables {
    match format {
        14 => &TABLES,
        15 => &TABLES15,
        16 => &TABLES16,
        _ => panic!("unsupported unit-orbit window format"),
    }
}

pub(super) fn warm_format(format: u8) -> usize {
    if format == 31 || format == 32 {
        std::sync::LazyLock::force(&super::EXACT_RECIPROCAL_CHECK);
        std::sync::LazyLock::force(&super::FIXED_SCALAR_LATTICE);
        std::sync::LazyLock::force(&U256_BETA_UNITS);
        return if format == 31 { SECTOR15_U256_TABLES.retained_bytes }
               else { SECTOR16_U256_TABLES.retained_bytes };
    }
    if format == 30 {
        std::sync::LazyLock::force(&super::EXACT_RECIPROCAL_CHECK);
        std::sync::LazyLock::force(&super::FIXED_SCALAR_LATTICE);
        std::sync::LazyLock::force(&U256_BETA_UNITS);
        return SECTOR_U256_TABLES.retained_bytes;
    }
    if format == 29 {
        std::sync::LazyLock::force(&super::EXACT_RECIPROCAL_CHECK);
        std::sync::LazyLock::force(&super::FIXED_SCALAR_LATTICE);
        std::sync::LazyLock::force(&U256_BETA_UNITS);
        return FORMULA_U256_TABLES.retained_bytes;
    }
    if format == 28 {
        std::sync::LazyLock::force(&super::EXACT_RECIPROCAL_CHECK);
        std::sync::LazyLock::force(&super::FIXED_SCALAR_LATTICE);
        std::sync::LazyLock::force(&U256_BETA_UNITS);
        return ARITHMETIC_U256_TABLES.retained_bytes;
    }
    if format == 26 || format == 27 {
        std::sync::LazyLock::force(&super::EXACT_RECIPROCAL_CHECK);
        std::sync::LazyLock::force(&super::FIXED_SCALAR_LATTICE);
        std::sync::LazyLock::force(&U256_BETA_UNITS);
        return U256_TABLES.retained_bytes;
    }
    if (20..=25).contains(&format) {
        std::sync::LazyLock::force(&super::EXACT_RECIPROCAL_CHECK);
        if (22..=25).contains(&format) {
            std::sync::LazyLock::force(&super::FIXED_SCALAR_LATTICE);
        }
        return TABLES.retained_bytes;
    }
    if format == 19 {
        return TABLES.retained_bytes;
    }
    if format == 18 {
        return TAU_PAIR_TABLES.retained_bytes;
    }
    if format == 17 {
        return TAU_BUCKET_TABLES.retained_bytes;
    }
    if format == 13 || format == 113 {
        return RADIX13_TABLES.retained_bytes;
    }
    selected(format).retained_bytes
}

pub(super) fn multiply_format(
    scalar: &BigInt,
    format: u8,
) -> (Jacobian, BigInt, BigInt, usize, usize) {
    if format == 13 {
        return multiply_radix13(scalar);
    }
    let lattice = &*SCALAR_LATTICE;
    let residue = ((scalar % &lattice.n) + &lattice.n) % &lattice.n;
    let (mut a, mut b) = hexagonal_four_corner_choices(&residue).remove(0);
    let (start_a, start_b) = (a.clone(), b.clone());
    let tables = selected(format);
    let mut result = Jacobian::identity();
    let mut nonidentity: usize = 0;
    for (index, &width) in tables.widths.iter().enumerate() {
        let atlas = tables.atlas(width);
        let (digit, orbit_id, unit_code) = atlas.digit(&a, &b);
        let base = BigInt::from(atlas.base());
        a = (a - digit.0) / &base;
        b = (b - digit.1) / &base;
        if orbit_id == 0 {
            continue;
        }
        let mut addend = tables.windows[index][orbit_id].into_affine();
        for _ in 0..(unit_code / 2) {
            addend = addend.omega();
        }
        if unit_code & 1 != 0 {
            addend = addend.neg();
        }
        result = result.add_mixed(addend);
        nonidentity += 1;
    }
    assert!(
        a.is_zero() && b.is_zero(),
        "unit-orbit window recoding did not terminate"
    );
    (
        result,
        start_a,
        start_b,
        nonidentity.saturating_sub(1),
        tables.retained_bytes,
    )
}

fn evaluate_word_representative(
    mut a: Signed192,
    mut b: Signed192,
    tables: &Tables,
) -> (Jacobian, usize) {
    let mut result = Jacobian::identity();
    let mut nonidentity: usize = 0;
    for (index, &width) in tables.widths.iter().enumerate() {
        let atlas = tables.atlas(width);
        let (digit, orbit_id, unit_code) = atlas.digit_word(a, b);
        a = a.sub(Signed192::from_i32(digit.0)).div_exact_power_of_two(width);
        b = b.sub(Signed192::from_i32(digit.1)).div_exact_power_of_two(width);
        if orbit_id == 0 {
            continue;
        }
        let mut addend = tables.windows[index][orbit_id].into_affine();
        for _ in 0..(unit_code / 2) {
            addend = addend.omega();
        }
        if unit_code & 1 != 0 {
            addend = addend.neg();
        }
        result = result.add_mixed(addend);
        nonidentity += 1;
    }
    assert!(a.is_zero() && b.is_zero(), "word unit-orbit recoding did not terminate");
    (result, nonidentity.saturating_sub(1))
}

pub(super) fn multiply_word_direct(
    scalar_words: [u64; 4],
) -> (Jacobian, (Signed192, Signed192), usize, usize, bool, usize) {
    let scalar = super::Uint(scalar_words);
    let residue = if bool::from(scalar.ct_lt(&super::SCALAR_ORDER_WORDS)) {
        scalar
    } else {
        super::U256::sbb(&scalar, &super::SCALAR_ORDER_WORDS).0
    };
    let (representative, fallback, corner) =
        super::hexagonal_certified_fixed_choice_words(residue.0);
    let (point, additions) =
        evaluate_word_representative(representative.0, representative.1, &TABLES);
    (point, representative, additions, TABLES.retained_bytes, fallback, corner)
}

pub(super) fn multiply_u256_direct(
    scalar_words: [u64; 4],
) -> (String, (Signed192, Signed192), usize, usize, bool, usize) {
    let scalar = super::Uint(scalar_words);
    let residue = if bool::from(scalar.ct_lt(&super::SCALAR_ORDER_WORDS)) {
        scalar
    } else {
        super::U256::sbb(&scalar, &super::SCALAR_ORDER_WORDS).0
    };
    let (representative, fallback, corner) =
        super::hexagonal_certified_fixed_choice_words(residue.0);
    let tables = &*U256_TABLES;
    let (mut a, mut b) = representative;
    let mut result = U256Jacobian::identity();
    let mut nonidentity = 0usize;
    for (index, &width) in WIDTHS.iter().enumerate() {
        let (digit, orbit_id, unit_code) = tables.atlas(width).digit_word(a, b);
        a = a.sub(Signed192::from_i32(digit.0)).div_exact_power_of_two(width);
        b = b.sub(Signed192::from_i32(digit.1)).div_exact_power_of_two(width);
        if orbit_id == 0 { continue; }
        result = result.add_mixed(tables.windows[index][orbit_id].unit(unit_code));
        nonidentity += 1;
    }
    assert!(a.is_zero() && b.is_zero(), "four-limb U14 recoding did not terminate");
    (result.affine_hex_binary_inverse(), representative,
     nonidentity.saturating_sub(1), tables.retained_bytes, fallback, corner)
}

fn u256_gauge_choices(
    representative: (Signed192, Signed192), tables: &U256Tables,
) -> ([(usize, usize); 14], usize) {
    let (mut a, mut b) = representative;
    let mut choices = [(0usize, 0usize); 14];
    let mut nonidentity = 0usize;
    for (index, &width) in WIDTHS.iter().enumerate() {
        let (digit, orbit_id, unit_code) = tables.atlas(width).digit_word(a, b);
        a = a.sub(Signed192::from_i32(digit.0)).div_exact_power_of_two(width);
        b = b.sub(Signed192::from_i32(digit.1)).div_exact_power_of_two(width);
        choices[index] = (orbit_id, unit_code);
        nonidentity += usize::from(orbit_id != 0);
    }
    assert!(a.is_zero() && b.is_zero(), "gauge U14 recoding did not terminate");
    (choices, nonidentity)
}

fn u256_arithmetic_choices(
    representative: (Signed192, Signed192), tables: &ArithmeticU256Tables,
) -> ([(usize, usize); 14], usize) {
    let (mut a, mut b) = representative;
    let mut choices = [(0usize, 0usize); 14];
    let mut nonidentity = 0usize;
    for (index, &width) in WIDTHS.iter().enumerate() {
        let (digit, orbit_id, unit_code) = tables.atlas(width).digit_word(a, b);
        a = a.sub(Signed192::from_i32(digit.0)).div_exact_power_of_two(width);
        b = b.sub(Signed192::from_i32(digit.1)).div_exact_power_of_two(width);
        choices[index] = (orbit_id, unit_code);
        nonidentity += usize::from(orbit_id != 0);
    }
    assert!(a.is_zero() && b.is_zero(), "arithmetic U14 recoding did not terminate");
    (choices, nonidentity)
}

fn u256_formula_choices(
    representative: (Signed192, Signed192),
) -> ([(usize, usize); 14], usize) {
    let (mut a, mut b) = representative;
    let mut choices = [(0usize, 0usize); 14];
    let mut nonidentity = 0usize;
    for (index, &width) in WIDTHS.iter().enumerate() {
        let (digit, orbit_id, unit_code) = formula_digit_word(width, a, b);
        a = a.sub(Signed192::from_i32(digit.0)).div_exact_power_of_two(width);
        b = b.sub(Signed192::from_i32(digit.1)).div_exact_power_of_two(width);
        choices[index] = (orbit_id, unit_code);
        nonidentity += usize::from(orbit_id != 0);
    }
    assert!(a.is_zero() && b.is_zero(), "point-only U14 recoding did not terminate");
    (choices, nonidentity)
}

fn u256_sector_choices_with<const N: usize>(
    representative: (Signed192, Signed192),
    widths: &[u8; N],
) -> ([(usize, usize); N], usize) {
    let (mut a, mut b) = representative;
    let mut choices = [(0usize, 0usize); N];
    let mut nonidentity = 0usize;
    for (index, &width) in widths.iter().enumerate() {
        let (digit, orbit_id, unit_code) = sector_digit_word(width, a, b);
        a = a.sub(Signed192::from_i32(digit.0)).div_exact_power_of_two(width);
        b = b.sub(Signed192::from_i32(digit.1)).div_exact_power_of_two(width);
        choices[index] = (orbit_id, unit_code);
        nonidentity += usize::from(orbit_id != 0);
    }
    assert!(a.is_zero() && b.is_zero(), "sector recoding did not terminate");
    (choices, nonidentity)
}

fn u256_sector_choices(
    representative: (Signed192, Signed192),
) -> ([(usize, usize); 14], usize) {
    u256_sector_choices_with(representative, &WIDTHS)
}

fn evaluate_u256_gauge(
    choices: &[(usize, usize)], windows: &[Box<[U256Affine]>],
) -> (String, usize) {
    assert_eq!(choices.len(), windows.len());
    let mut result = U256Jacobian::identity();
    let mut gauge = None;
    let mut gauge_products = 0usize;
    for power in [1usize, 2, 0] {
        if !choices.iter().any(|&(orbit, code)| orbit != 0 && code / 2 == power) {
            continue;
        }
        if let Some(previous) = gauge {
            let delta = (previous + 3 - power) % 3;
            if delta != 0 && !result.is_identity() {
                result = result.rotate_power(delta);
                gauge_products += 1;
            }
        }
        gauge = Some(power);
        for (index, &(orbit_id, unit_code)) in choices.iter().enumerate() {
            if orbit_id == 0 || unit_code / 2 != power { continue; }
            result = result.add_mixed(windows[index][orbit_id].unit(unit_code & 1));
        }
    }
    if let Some(power) = gauge {
        if power != 0 && !result.is_identity() {
            result = result.rotate_power(power);
            gauge_products += 1;
        }
    }
    assert!(gauge_products <= 2);
    (result.affine_hex_binary_inverse(), gauge_products)
}

pub(super) fn multiply_u256_gauge(
    scalar_words: [u64; 4],
) -> (String, (Signed192, Signed192), usize, usize, bool, usize, usize) {
    let scalar = super::Uint(scalar_words);
    let residue = if bool::from(scalar.ct_lt(&super::SCALAR_ORDER_WORDS)) {
        scalar
    } else {
        super::U256::sbb(&scalar, &super::SCALAR_ORDER_WORDS).0
    };
    let (representative, fallback, corner) =
        super::hexagonal_certified_fixed_choice_words(residue.0);
    let tables = &*U256_TABLES;
    let (choices, nonidentity) = u256_gauge_choices(representative, tables);
    let (point, gauge_products) = evaluate_u256_gauge(&choices, &tables.windows);
    (point, representative,
     nonidentity.saturating_sub(1), tables.retained_bytes, fallback, corner,
     gauge_products)
}

pub(super) fn multiply_u256_arithmetic(
    scalar_words: [u64; 4],
) -> (String, (Signed192, Signed192), usize, usize, bool, usize, usize) {
    let scalar = super::Uint(scalar_words);
    let residue = if bool::from(scalar.ct_lt(&super::SCALAR_ORDER_WORDS)) {
        scalar
    } else {
        super::U256::sbb(&scalar, &super::SCALAR_ORDER_WORDS).0
    };
    let (representative, fallback, corner) =
        super::hexagonal_certified_fixed_choice_words(residue.0);
    let tables = &*ARITHMETIC_U256_TABLES;
    let (choices, nonidentity) = u256_arithmetic_choices(representative, tables);
    let (point, gauge_products) = evaluate_u256_gauge(&choices, &tables.windows);
    (point, representative, nonidentity.saturating_sub(1),
     tables.retained_bytes, fallback, corner, gauge_products)
}

pub(super) fn multiply_u256_formula(
    scalar_words: [u64; 4],
) -> (String, (Signed192, Signed192), usize, usize, bool, usize, usize) {
    let scalar = super::Uint(scalar_words);
    let residue = if bool::from(scalar.ct_lt(&super::SCALAR_ORDER_WORDS)) {
        scalar
    } else {
        super::U256::sbb(&scalar, &super::SCALAR_ORDER_WORDS).0
    };
    let (representative, fallback, corner) =
        super::hexagonal_certified_fixed_choice_words(residue.0);
    let tables = &*FORMULA_U256_TABLES;
    let (choices, nonidentity) = u256_formula_choices(representative);
    let (point, gauge_products) = evaluate_u256_gauge(&choices, &tables.windows);
    (point, representative, nonidentity.saturating_sub(1),
     tables.retained_bytes, fallback, corner, gauge_products)
}

pub(super) fn multiply_u256_sector(
    scalar_words: [u64; 4],
) -> (String, (Signed192, Signed192), usize, usize, bool, usize, usize) {
    multiply_u256_sector_with(scalar_words, &WIDTHS, &SECTOR_U256_TABLES)
}

pub(super) fn multiply_u256_sector15(
    scalar_words: [u64; 4],
) -> (String, (Signed192, Signed192), usize, usize, bool, usize, usize) {
    multiply_u256_sector_with(scalar_words, &WIDTHS15, &SECTOR15_U256_TABLES)
}

pub(super) fn multiply_u256_sector16(
    scalar_words: [u64; 4],
) -> (String, (Signed192, Signed192), usize, usize, bool, usize, usize) {
    multiply_u256_sector_with(scalar_words, &WIDTHS16, &SECTOR16_U256_TABLES)
}

fn multiply_u256_sector_with<const N: usize>(
    scalar_words: [u64; 4], widths: &[u8; N], tables: &FormulaU256Tables,
) -> (String, (Signed192, Signed192), usize, usize, bool, usize, usize) {
    let scalar = super::Uint(scalar_words);
    let residue = if bool::from(scalar.ct_lt(&super::SCALAR_ORDER_WORDS)) {
        scalar
    } else {
        super::U256::sbb(&scalar, &super::SCALAR_ORDER_WORDS).0
    };
    let (representative, fallback, corner) =
        super::hexagonal_certified_fixed_choice_words(residue.0);
    let (choices, nonidentity) = u256_sector_choices_with(representative, widths);
    let (point, gauge_products) = evaluate_u256_gauge(&choices, &tables.windows);
    (point, representative, nonidentity.saturating_sub(1),
     tables.retained_bytes, fallback, corner, gauge_products)
}

pub(super) fn multiply_word_format(
    scalar: &BigInt,
    format: u8,
) -> (Jacobian, BigInt, BigInt, usize, usize) {
    if format == 19 {
        return multiply_word_staged14(scalar);
    }
    if format == 18 {
        return multiply_tau_pair(scalar);
    }
    if format == 17 {
        return multiply_tau_bucket(scalar);
    }
    if format == 13 {
        return multiply_word_radix13(scalar);
    }
    let lattice = &*SCALAR_LATTICE;
    let residue = ((scalar % &lattice.n) + &lattice.n) % &lattice.n;
    let (a, b, original) = if (22..=24).contains(&format) {
        let (a, b) = super::hexagonal_certified_fixed_choice(&residue).0;
        (a, b, None)
    } else {
        let (start_a, start_b) = if format == 21 {
            super::hexagonal_certified_corner_choice(&residue).0
        } else if format == 20 {
            super::hexagonal_four_corner_choices_reciprocal(&residue).remove(0)
        } else {
            hexagonal_four_corner_choices(&residue).remove(0)
        };
        (Signed192::from_bigint(&start_a), Signed192::from_bigint(&start_b),
         Some((start_a, start_b)))
    };
    let start_fixed = (a, b);
    let tables = selected(if (20..=24).contains(&format) { 14 } else { format });
    let (result, additions) = evaluate_word_representative(a, b, tables);
    let (start_a, start_b) = original.unwrap_or_else(||
        (start_fixed.0.to_bigint(), start_fixed.1.to_bigint()));
    (result, start_a, start_b, additions, tables.retained_bytes)
}

#[inline(always)]
fn prefetch_compact_point(point: &CompactPairPoint) {
    debug_assert!(size_of::<CompactPairPoint>() > 64);
    let address = point as *const CompactPairPoint as *const i8;
    #[cfg(target_arch = "x86_64")]
    unsafe {
        use std::arch::x86_64::{_mm_prefetch, _MM_HINT_T0};
        _mm_prefetch::<{ _MM_HINT_T0 }>(address);
        _mm_prefetch::<{ _MM_HINT_T0 }>(address.wrapping_add(64));
    }
    #[cfg(target_arch = "aarch64")]
    unsafe {
        let first = address as usize;
        let second = first + 64;
        std::arch::asm!("prfm pldl1keep, [{ptr}]", ptr = in(reg) first,
                        options(nostack, readonly, preserves_flags));
        std::arch::asm!("prfm pldl1keep, [{ptr}]", ptr = in(reg) second,
                        options(nostack, readonly, preserves_flags));
    }
    #[cfg(not(any(target_arch = "x86_64", target_arch = "aarch64")))]
    let _ = address;
}

fn multiply_word_staged14(
    scalar: &BigInt,
) -> (Jacobian, BigInt, BigInt, usize, usize) {
    let lattice = &*SCALAR_LATTICE;
    let residue = ((scalar % &lattice.n) + &lattice.n) % &lattice.n;
    let (start_a, start_b) = hexagonal_four_corner_choices(&residue).remove(0);
    let mut a = Signed192::from_bigint(&start_a);
    let mut b = Signed192::from_bigint(&start_b);
    let tables = &*TABLES;
    assert!(tables.widths.len() <= 16);
    let mut choices = [(0usize, 0usize); 16];
    for (index, &width) in tables.widths.iter().enumerate() {
        let atlas = tables.atlas(width);
        let (digit, orbit_id, unit_code) = atlas.digit_word(a, b);
        a = a.sub(Signed192::from_i32(digit.0)).div_exact_power_of_two(width);
        b = b.sub(Signed192::from_i32(digit.1)).div_exact_power_of_two(width);
        choices[index] = (orbit_id, unit_code);
        if orbit_id != 0 {
            prefetch_compact_point(&tables.windows[index][orbit_id]);
        }
    }
    assert!(a.is_zero() && b.is_zero(), "staged word unit-orbit recoding did not terminate");
    let mut result = Jacobian::identity();
    let mut nonidentity = 0usize;
    for (index, &(orbit_id, unit_code)) in choices[..tables.widths.len()].iter().enumerate() {
        if orbit_id == 0 {
            continue;
        }
        let mut addend = tables.windows[index][orbit_id].into_affine();
        for _ in 0..(unit_code / 2) {
            addend = addend.omega();
        }
        if unit_code & 1 != 0 {
            addend = addend.neg();
        }
        result = result.add_mixed(addend);
        nonidentity += 1;
    }
    (result, start_a, start_b, nonidentity.saturating_sub(1), tables.retained_bytes)
}

#[cfg(test)]
mod tests {
    use super::*;
    use super::super::{Pair, Signed};

    fn word_as_bigint(word: Signed192) -> BigInt {
        BigInt::from_biguint(
            if word.negative { num_bigint::Sign::Minus } else { num_bigint::Sign::Plus },
            num_bigint::BigUint::from_bytes_le(&word.limbs.iter()
                .flat_map(|limb| limb.to_le_bytes()).collect::<Vec<_>>()),
        )
    }

    fn assert_word_radix13_matches(scalar: &BigInt, label: &str) -> Jacobian {
        let reference = multiply_radix13(scalar);
        let candidate = multiply_word_radix13(scalar);
        assert_eq!((&reference.1, &reference.2, reference.3, reference.4),
                   (&candidate.1, &candidate.2, candidate.3, candidate.4), "{label}");
        assert_eq!(reference.0.affine_hex(), candidate.0.affine_hex(), "{label}");
        let tables = &*RADIX13_TABLES;
        let base = BigInt::from(RADIX13);
        let (mut old_a, mut old_b) = (reference.1.clone(), reference.2.clone());
        let (mut word_a, mut word_b) =
            (Signed192::from_bigint(&old_a), Signed192::from_bigint(&old_b));
        for window in 0..RADIX13_WINDOWS {
            let digit = tables.atlas.digit(&old_a, &old_b);
            let (quotient_a, signed_rem_a, residue_a) = word_a.div_rem_radix13();
            let (quotient_b, signed_rem_b, residue_b) = word_b.div_rem_radix13();
            assert_eq!(tables.atlas.digit_residue(residue_a, residue_b), digit,
                       "{label}, fused window {window}");
            assert_eq!(tables.atlas.digit_word_radix13(word_a, word_b), digit,
                       "{label}, window {window}");
            old_a = (old_a - digit.0.0) / &base;
            old_b = (old_b - digit.0.1) / &base;
            word_a = quotient_a.adjust_radix13_quotient(signed_rem_a, digit.0.0);
            word_b = quotient_b.adjust_radix13_quotient(signed_rem_b, digit.0.1);
            assert_eq!(word_a, Signed192::from_bigint(&old_a), "{label}, window {window} a");
            assert_eq!(word_b, Signed192::from_bigint(&old_b), "{label}, window {window} b");
        }
        assert!(word_a.is_zero() && word_b.is_zero(), "{label}");
        candidate.0
    }

    fn independent_binary_point(scalar: &BigInt) -> Jacobian {
        let (_, bytes) = scalar.to_bytes_be();
        let generator = Jacobian::generator().into_affine();
        let mut point = Jacobian::identity();
        for byte in bytes {
            for bit in (0..8).rev() {
                point = point.double();
                if (byte >> bit) & 1 != 0 {
                    point = point.add_mixed(generator);
                }
            }
        }
        point
    }

    #[test]
    fn word_radix943_division_matches_bigint_at_limb_and_sign_boundaries() {
        let high = BigInt::from(1) << 191;
        let mid = BigInt::from(1) << 128;
        let low = BigInt::from(1) << 64;
        let base = BigInt::from(RADIX13);
        for value in [
            -&high - 1, -&high, -&mid - 1, -&mid, -&low - 1, -&low,
            -&base - 1, -&base, BigInt::from(-1), BigInt::ZERO,
            BigInt::from(1), &base - 1, base.clone(), &low - 1, low,
            &mid - 1, mid, &high - 1, high,
        ] {
            let word = Signed192::from_bigint(&value);
            let remainder = ((&value % &base + &base) % &base).to_usize().unwrap();
            assert_eq!(word.rem_euclid_radix13(), remainder);
            for digit in [remainder as i32, remainder as i32 - RADIX13 as i32] {
                let quotient = word.sub(Signed192::from_i32(digit)).div_exact_radix13();
                assert_eq!(word_as_bigint(quotient), (&value - digit) / &base);
                let (truncated, signed_rem, _) = word.div_rem_radix13();
                let fused = truncated.adjust_radix13_quotient(signed_rem, digit);
                assert_eq!(word_as_bigint(fused), (&value - digit) / &base);
            }
        }
    }

    #[test]
    fn word_radix943_replays_fixture_and_fresh_points() {
        let fixture: serde_json::Value = serde_json::from_str(include_str!(
            "../../../tau6-comb13-bench-fixture.json"
        )).unwrap();
        let cases = fixture["cases"].as_array().unwrap();
        assert_eq!(cases.len(), 129);
        for (index, case) in cases.iter().enumerate() {
            let scalar = BigInt::parse_bytes(case["scalar_hex"].as_str().unwrap().as_bytes(), 16)
                .unwrap();
            let point = assert_word_radix13_matches(&scalar, &format!("fixture {index}"));
            let expected = if case["expected_identity"].as_bool() == Some(true) {
                "identity".to_owned()
            } else {
                format!("{}:{}", case["expected_x_hex"].as_str().unwrap(),
                        case["expected_y_hex"].as_str().unwrap())
            };
            assert_eq!(point.affine_hex(), expected, "fixture {index}");
        }
        let input: serde_json::Value = serde_json::from_str(include_str!(
            "../../../../prime-j0-radix943-word-20261009/inputs.json"
        )).unwrap();
        let scalars = input["scalars_hex"].as_array().unwrap();
        assert_eq!(scalars.len(), 519);
        for (index, hex) in scalars.iter().enumerate() {
            let scalar = BigInt::parse_bytes(hex.as_str().unwrap().as_bytes(), 16).unwrap();
            let point = assert_word_radix13_matches(&scalar, &format!("fresh {index}"));
            if (7..135).contains(&index) {
                let reduced = &scalar % &SCALAR_LATTICE.n;
                assert_eq!(point.affine_hex(), independent_binary_point(&reduced).affine_hex(),
                           "independent fresh {index}");
            }
        }
    }

    #[test]
    fn tau_bucket_replays_fixture_and_fresh_points() {
        let fixture: serde_json::Value = serde_json::from_str(include_str!(
            "../../../tau6-comb13-bench-fixture.json"
        )).unwrap();
        let cases = fixture["cases"].as_array().unwrap();
        assert_eq!(cases.len(), 129);
        for (index, case) in cases.iter().enumerate() {
            let scalar = BigInt::parse_bytes(case["scalar_hex"].as_str().unwrap().as_bytes(), 16)
                .unwrap();
            let candidate = multiply_tau_bucket(&scalar);
            let expected = if case["expected_identity"].as_bool() == Some(true) {
                "identity".to_owned()
            } else {
                format!("{}:{}", case["expected_x_hex"].as_str().unwrap(),
                        case["expected_y_hex"].as_str().unwrap())
            };
            assert_eq!(candidate.0.affine_hex(), expected, "fixture {index}");
            assert!(candidate.4 < TAU_BUCKET_CAP_BYTES);
        }
        let input: serde_json::Value = serde_json::from_str(include_str!(
            "../../../../prime-j0-radix943-word-20261009/inputs.json"
        )).unwrap();
        let scalars = input["scalars_hex"].as_array().unwrap();
        assert_eq!(scalars.len(), 519);
        for (index, hex) in scalars.iter().enumerate() {
            let scalar = BigInt::parse_bytes(hex.as_str().unwrap().as_bytes(), 16).unwrap();
            let candidate = multiply_tau_bucket(&scalar);
            let reference = multiply_word_radix13(&scalar);
            assert_eq!(candidate.0.affine_hex(), reference.0.affine_hex(), "fresh {index}");
            if (7..135).contains(&index) {
                let reduced = &scalar % &SCALAR_LATTICE.n;
                assert_eq!(candidate.0.affine_hex(),
                           independent_binary_point(&reduced).affine_hex(),
                           "independent fresh {index}");
            }
        }
    }

    #[test]
    fn tau_pair_replays_fixture_and_fresh_points() {
        let fixture: serde_json::Value = serde_json::from_str(include_str!(
            "../../../tau6-comb13-bench-fixture.json"
        )).unwrap();
        let cases = fixture["cases"].as_array().unwrap();
        assert_eq!(cases.len(), 129);
        for (index, case) in cases.iter().enumerate() {
            let scalar = BigInt::parse_bytes(case["scalar_hex"].as_str().unwrap().as_bytes(), 16)
                .unwrap();
            let candidate = multiply_tau_pair(&scalar);
            let expected = if case["expected_identity"].as_bool() == Some(true) {
                "identity".to_owned()
            } else {
                format!("{}:{}", case["expected_x_hex"].as_str().unwrap(),
                        case["expected_y_hex"].as_str().unwrap())
            };
            assert_eq!(candidate.0.affine_hex(), expected, "fixture {index}");
            assert!(candidate.3 <= 12 && candidate.4 < TAU_PAIR_CAP_BYTES);
        }
        let input: serde_json::Value = serde_json::from_str(include_str!(
            "../../../../prime-j0-radix943-word-20261009/inputs.json"
        )).unwrap();
        let scalars = input["scalars_hex"].as_array().unwrap();
        assert_eq!(scalars.len(), 519);
        for (index, hex) in scalars.iter().enumerate() {
            let scalar = BigInt::parse_bytes(hex.as_str().unwrap().as_bytes(), 16).unwrap();
            let candidate = multiply_tau_pair(&scalar);
            let reference = multiply_format(&scalar, 14);
            let three_bucket = multiply_tau_bucket(&scalar);
            assert_eq!(candidate.0.affine_hex(), reference.0.affine_hex(), "U14 fresh {index}");
            assert_eq!(candidate.0.affine_hex(), three_bucket.0.affine_hex(),
                       "three-bucket fresh {index}");
            if (7..135).contains(&index) {
                let reduced = &scalar % &SCALAR_LATTICE.n;
                assert_eq!(candidate.0.affine_hex(),
                           independent_binary_point(&reduced).affine_hex(),
                           "independent fresh {index}");
            }
        }
    }

    #[test]
    fn staged_word14_matches_reference_and_independent_points() {
        let input: serde_json::Value = serde_json::from_str(include_str!(
            "../../../../prime-j0-radix943-word-20261009/inputs.json"
        )).unwrap();
        let scalars = input["scalars_hex"].as_array().unwrap();
        assert_eq!(scalars.len(), 519);
        for (index, hex) in scalars.iter().enumerate() {
            let scalar = BigInt::parse_bytes(hex.as_str().unwrap().as_bytes(), 16).unwrap();
            let reference = multiply_word_format(&scalar, 14);
            let staged = multiply_word_staged14(&scalar);
            assert_eq!((&staged.1, &staged.2, staged.3, staged.4),
                       (&reference.1, &reference.2, reference.3, reference.4),
                       "same scalar and table accounting {index}");
            assert_eq!(staged.0.affine_hex(), reference.0.affine_hex(),
                       "staged output {index}");
            if (7..135).contains(&index) {
                let reduced = &scalar % &SCALAR_LATTICE.n;
                assert_eq!(staged.0.affine_hex(),
                           independent_binary_point(&reduced).affine_hex(),
                           "independent fresh {index}");
            }
        }
    }

    #[test]
    fn exact_reciprocal_selector_matches_all_frozen_and_fresh_scalars() {
        let frozen: serde_json::Value = serde_json::from_str(include_str!(
            "../../../../prime-j0-radix943-word-20261009/inputs.json"
        )).unwrap();
        let fresh: serde_json::Value = serde_json::from_str(include_str!(
            "../../../../prime-j0-exact-reciprocal-20261010/fresh-inputs.json"
        )).unwrap();
        let frozen_scalars = frozen["scalars_hex"].as_array().unwrap();
        let fresh_scalars = fresh["scalars_hex"].as_array().unwrap();
        assert_eq!(frozen_scalars.len(), 519);
        assert_eq!(fresh_scalars.len(), 4096);
        let lattice = &*SCALAR_LATTICE;
        let w1 = &lattice.u1 - 2 * &lattice.v1;
        for (index, hex) in frozen_scalars.iter().chain(fresh_scalars).enumerate() {
            let scalar = BigInt::parse_bytes(hex.as_str().unwrap().as_bytes(), 16).unwrap();
            let reduced = &scalar % &lattice.n;
            assert_eq!(super::super::reciprocal_floor_512(&reduced, &super::super::RECIP_V1),
                       (&reduced * &lattice.v1) / &lattice.n, "v1 floor {index}");
            assert_eq!(super::super::reciprocal_floor_512(
                           &reduced, &super::super::RECIP_MINUS_W1),
                       (&reduced * -&w1) / &lattice.n, "w1 floor {index}");
            assert_eq!(super::super::hexagonal_four_corner_choices_reciprocal(&reduced),
                       hexagonal_four_corner_choices(&reduced), "ordered corners {index}");
            let reference = multiply_word_format(&scalar, 14);
            let candidate = multiply_word_format(&scalar, 20);
            assert_eq!((&candidate.1, &candidate.2, candidate.3, candidate.4),
                       (&reference.1, &reference.2, reference.3, reference.4),
                       "representative and accounting {index}");
            assert_eq!(candidate.0.affine_hex(), reference.0.affine_hex(),
                       "point {index}");
            if (519..647).contains(&index) {
                assert_eq!(candidate.0.affine_hex(),
                           independent_binary_point(&reduced).affine_hex(),
                           "independent fresh point {index}");
            }
        }
    }

    #[test]
    fn certified_voronoi_selector_matches_complete_scalar_outputs() {
        let frozen: serde_json::Value = serde_json::from_str(include_str!(
            "../../../../prime-j0-radix943-word-20261009/inputs.json"
        )).unwrap();
        let prior: serde_json::Value = serde_json::from_str(include_str!(
            "../../../../prime-j0-exact-reciprocal-20261010/fresh-inputs.json"
        )).unwrap();
        let holdout: serde_json::Value = serde_json::from_str(include_str!(
            "../../../../prime-j0-certified-voronoi-20261010/fresh-inputs.json"
        )).unwrap();
        let boundary: [String; 4] = ["0".to_owned(),
                        (&SCALAR_LATTICE.n - BigInt::from(1)).to_str_radix(16),
                        SCALAR_LATTICE.n.to_str_radix(16),
                        ((BigInt::from(1) << 256usize) - BigInt::from(1)).to_str_radix(16)];
        let lists: [Vec<&str>; 4] = [
            boundary.iter().map(String::as_str).collect::<Vec<_>>(),
            frozen["scalars_hex"].as_array().unwrap().iter()
                .map(|x| x.as_str().unwrap()).collect(),
            prior["scalars_hex"].as_array().unwrap().iter()
                .map(|x| x.as_str().unwrap()).collect(),
            holdout["scalars_hex"].as_array().unwrap().iter()
                .map(|x| x.as_str().unwrap()).collect(),
        ];
        assert_eq!(lists.iter().map(Vec::len).collect::<Vec<_>>(), [4, 519, 4096, 4096]);
        assert_eq!(super::super::certified_corner_from_fraction_limb(1 << 63, 0), None);
        let mut counts = [0usize; 4];
        let mut fallback = 0usize;
        for (panel, values) in lists.iter().enumerate() {
            for (index, &hex) in values.iter().enumerate() {
                let scalar = BigInt::parse_bytes(hex.as_bytes(), 16).unwrap();
                let reduced = &scalar % &SCALAR_LATTICE.n;
                let (chosen, did_fallback, corner) =
                    super::super::hexagonal_certified_corner_choice(&reduced);
                assert_eq!(chosen, hexagonal_four_corner_choices(&reduced)[0],
                           "corner panel {panel} index {index}");
                fallback += usize::from(did_fallback);
                if !did_fallback { counts[corner] += 1; }
                let reference = multiply_word_format(&scalar, 20);
                let candidate = multiply_word_format(&scalar, 21);
                assert_eq!((&candidate.1, &candidate.2, candidate.3, candidate.4),
                           (&reference.1, &reference.2, reference.3, reference.4),
                           "accounting panel {panel} index {index}");
                assert_eq!(candidate.0.affine_hex(), reference.0.affine_hex(),
                           "point panel {panel} index {index}");
                if panel == 3 && index < 128 {
                    assert_eq!(candidate.0.affine_hex(),
                               independent_binary_point(&reduced).affine_hex(),
                               "independent holdout {index}");
                }
            }
        }
        assert_eq!(fallback, 0);
        assert_eq!(counts, [2983, 1414, 1455, 2863]);
    }

    #[test]
    fn fixed_limb_voronoi_matches_certified_representative_and_points() {
        let panels = [
            include_str!("../../../../prime-j0-radix943-word-20261009/inputs.json"),
            include_str!("../../../../prime-j0-exact-reciprocal-20261010/fresh-inputs.json"),
            include_str!("../../../../prime-j0-certified-voronoi-20261010/fresh-inputs.json"),
            include_str!("../../../../prime-j0-fixed-limb-voronoi-20261010/fresh-inputs.json"),
        ];
        let mut cases = vec![BigInt::ZERO, &SCALAR_LATTICE.n - BigInt::from(1),
                             SCALAR_LATTICE.n.clone(),
                             (BigInt::from(1) << 256usize) - BigInt::from(1)];
        for panel in panels {
            let data: serde_json::Value = serde_json::from_str(panel).unwrap();
            cases.extend(data["scalars_hex"].as_array().unwrap().iter().map(|value|
                BigInt::parse_bytes(value.as_str().unwrap().as_bytes(), 16).unwrap()));
        }
        assert_eq!(cases.len(), 4 + 519 + 3 * 4096);
        let fresh_start = 4 + 519 + 2 * 4096;
        let mut fallbacks = 0usize;
        for (index, scalar) in cases.iter().enumerate() {
            let reduced = scalar % &SCALAR_LATTICE.n;
            let ((a, b), fallback, corner) =
                super::super::hexagonal_certified_fixed_choice(&reduced);
            let (parent, parent_fallback, parent_corner) =
                super::super::hexagonal_certified_corner_choice(&reduced);
            assert_eq!((fallback, corner), (parent_fallback, parent_corner),
                       "certificate {index}");
            assert_eq!((a.to_bigint(), b.to_bigint()), parent,
                       "coordinates {index}");
            fallbacks += usize::from(fallback);
            let expected = multiply_word_format(scalar, 21);
            let actual = multiply_word_format(scalar, 22);
            assert_eq!((&actual.1, &actual.2, actual.3, actual.4),
                       (&expected.1, &expected.2, expected.3, expected.4),
                       "accounting {index}");
            assert_eq!(actual.0.affine_hex(), expected.0.affine_hex(), "point {index}");
            if (fresh_start..fresh_start + 128).contains(&index) {
                assert_eq!(actual.0.affine_hex(), independent_binary_point(&reduced).affine_hex(),
                           "independent point {index}");
            }
        }
        assert_eq!(fallbacks, 0);
    }

    #[test]
    fn hybrid_pair_conversion_matches_bigint_mapping() {
        let (ctx, _, _) = &*super::super::HYBRID_FIELD;
        let edge = [0u128, 1, u128::MAX, super::super::PI_A,
                    super::super::PI_B_MAG, 1u128 << 127];
        let mut values = Vec::new();
        for &a in &edge {
            for &b in &edge {
                for negative_a in [false, true] {
                    for negative_b in [false, true] {
                        values.push((a, b, negative_a, negative_b));
                    }
                }
            }
        }
        let mut state = 0x8d1a_d574_1f33_e91cu128;
        for _ in 0..256 {
            state ^= state << 13;
            state ^= state >> 7;
            state ^= state << 17;
            let a = state;
            state ^= state << 13;
            state ^= state >> 7;
            state ^= state << 17;
            values.push((a, state, a & 1 != 0, state & 1 != 0));
        }
        for (index, (a, b, negative_a, negative_b)) in values.into_iter().enumerate() {
            let pair = Pair {
                a: if negative_a { Signed::from_u128(a).neg() } else { Signed::from_u128(a) },
                b: if negative_b { Signed::from_u128(b).neg() } else { Signed::from_u128(b) },
            };
            let converted = ctx.from_montgomery(&super::super::hybrid_pair_mont(pair));
            assert_eq!(hex::encode(converted.to_bytes_be()), pair.canonical_hex(),
                       "pair {index}");
        }
    }

    #[test]
    fn hybrid_finalizer_matches_parent_and_fresh_points() {
        let panels = [
            include_str!("../../../../prime-j0-radix943-word-20261009/inputs.json"),
            include_str!("../../../../prime-j0-exact-reciprocal-20261010/fresh-inputs.json"),
            include_str!("../../../../prime-j0-certified-voronoi-20261010/fresh-inputs.json"),
            include_str!("../../../../prime-j0-fixed-limb-voronoi-20261010/fresh-inputs.json"),
            include_str!("../../../../prime-j0-hybrid-finalize-20261010/fresh-inputs.json"),
        ];
        let mut cases = vec![BigInt::ZERO, BigInt::from(1),
                             &SCALAR_LATTICE.n - BigInt::from(1),
                             SCALAR_LATTICE.n.clone(),
                             (BigInt::from(1) << 256usize) - BigInt::from(1)];
        for panel in panels {
            let data: serde_json::Value = serde_json::from_str(panel).unwrap();
            cases.extend(data["scalars_hex"].as_array().unwrap().iter().map(|value|
                BigInt::parse_bytes(value.as_str().unwrap().as_bytes(), 16).unwrap()));
        }
        assert_eq!(cases.len(), 5 + 519 + 4 * 4096);
        let fresh_start = cases.len() - 4096;
        for (index, scalar) in cases.iter().enumerate() {
            let point = multiply_word_format(scalar, 23).0;
            assert_eq!(point.affine_hex_hybrid(), point.affine_hex(),
                       "finalizer point {index}");
            if (fresh_start..fresh_start + 128).contains(&index) {
                let reduced = scalar % &SCALAR_LATTICE.n;
                assert_eq!(point.affine_hex_hybrid(),
                           independent_binary_point(&reduced).affine_hex(),
                           "independent point {index}");
            }
        }
    }

    #[test]
    fn binary_inverse_modular_halves_and_inverses_match_reference() {
        let (ctx, _, _) = &*super::super::HYBRID_FIELD;
        let (p_minus_one, _) = super::super::U256::sbb(&ctx.n, &super::super::U256::ONE);
        let (p_minus_two, _) = super::super::U256::sbb(
            &p_minus_one, &super::super::U256::ONE);
        let mut values = vec![super::super::U256::ZERO, super::super::U256::ONE,
                              super::super::Uint([2, 0, 0, 0]), p_minus_one,
                              p_minus_two, super::super::Uint([0, 0, 0, 1u64 << 63])];
        let mut state = 0xced7_22b5_0a41_b3d9u64;
        for _ in 0..512 {
            let mut limbs = [0u64; 4];
            for limb in &mut limbs {
                state ^= state << 13;
                state ^= state >> 7;
                state ^= state << 17;
                *limb = state;
            }
            let mut value = super::super::Uint(limbs);
            if !bool::from(value.ct_lt(&ctx.n)) {
                value = super::super::U256::sbb(&value, &ctx.n).0;
            }
            values.push(value);
        }
        for (index, value) in values.into_iter().enumerate() {
            let expected_half = {
                let mut whole = value.to_biguint();
                if value.0[0] & 1 != 0 { whole += ctx.n.to_biguint(); }
                super::super::U256::from_biguint(&(whole >> 1usize))
            };
            assert_eq!(super::super::binary_mod_half(value, &ctx.n).0,
                       expected_half.0, "half {index}");
            if bool::from(value.ct_is_zero()) { continue; }
            let mont = ctx.to_montgomery(&value);
            let binary = super::super::hybrid_binary_invert(mont, ctx);
            let chain = super::super::hybrid_invert(mont, ctx);
            assert_eq!(binary.0, chain.0, "inverse {index}");
            assert_eq!(ctx.mont_mul(&mont, &binary).0, ctx.r_mod_n.0,
                       "inverse product {index}");
        }
    }

    #[test]
    fn binary_inverse_finalizer_matches_complete_prior_and_fresh_points() {
        let panels = [
            include_str!("../../../../prime-j0-radix943-word-20261009/inputs.json"),
            include_str!("../../../../prime-j0-exact-reciprocal-20261010/fresh-inputs.json"),
            include_str!("../../../../prime-j0-certified-voronoi-20261010/fresh-inputs.json"),
            include_str!("../../../../prime-j0-fixed-limb-voronoi-20261010/fresh-inputs.json"),
            include_str!("../../../../prime-j0-hybrid-finalize-20261010/fresh-inputs.json"),
            include_str!("../../../../prime-j0-binary-inverse-20261010/fresh-inputs.json"),
        ];
        let mut cases = vec![BigInt::ZERO, BigInt::from(1),
                             &SCALAR_LATTICE.n - BigInt::from(1),
                             SCALAR_LATTICE.n.clone(),
                             (BigInt::from(1) << 256usize) - BigInt::from(1)];
        for panel in panels {
            let data: serde_json::Value = serde_json::from_str(panel).unwrap();
            cases.extend(data["scalars_hex"].as_array().unwrap().iter().map(|value|
                BigInt::parse_bytes(value.as_str().unwrap().as_bytes(), 16).unwrap()));
        }
        assert_eq!(cases.len(), 5 + 519 + 5 * 4096);
        let fresh_start = cases.len() - 4096;
        for (index, scalar) in cases.iter().enumerate() {
            let reference = multiply_word_format(scalar, 23);
            let candidate = multiply_word_format(scalar, 24);
            assert_eq!((&reference.1, &reference.2, reference.3, reference.4),
                       (&candidate.1, &candidate.2, candidate.3, candidate.4),
                       "scalar path {index}");
            assert_eq!(candidate.0.affine_hex_binary_inverse(),
                       reference.0.affine_hex_hybrid(), "point {index}");
            if (fresh_start..fresh_start + 128).contains(&index) {
                let reduced = scalar % &SCALAR_LATTICE.n;
                assert_eq!(candidate.0.affine_hex_binary_inverse(),
                           independent_binary_point(&reduced).affine_hex(),
                           "independent point {index}");
            }
        }
    }

    #[test]
    fn direct_limb_reduction_matches_bigint_and_preserves_fallback_contract() {
        let n = SCALAR_LATTICE.n.to_biguint().unwrap();
        assert_eq!(super::super::SCALAR_ORDER_WORDS.to_biguint(), n);
        let mut values = vec![0u128.into(), 1u128.into(), &n - 1u8, n.clone(),
                              (num_bigint::BigUint::from(1u8) << 256usize) - 1u8];
        let mut state = 0x8d8c_2109_f1a7_33e9u64;
        for _ in 0..512 {
            let mut words = [0u64; 4];
            for word in &mut words {
                state ^= state << 13;
                state ^= state >> 7;
                state ^= state << 17;
                *word = state;
            }
            values.push(super::super::Uint(words).to_biguint());
        }
        for (index, value) in values.iter().enumerate() {
            let scalar = BigInt::from_biguint(num_bigint::Sign::Plus, value.clone());
            let words = super::super::scalar_words_256(&scalar).unwrap();
            let direct = multiply_word_direct(words);
            let residue = BigInt::from_biguint(num_bigint::Sign::Plus, value % &n);
            let (expected, fallback, corner) =
                super::super::hexagonal_certified_fixed_choice(&residue);
            assert_eq!(direct.1, expected, "representative {index}");
            assert_eq!((direct.4, direct.5), (fallback, corner),
                       "certificate {index}");
            let parent = multiply_word_format(&scalar, 24);
            assert_eq!(direct.2, parent.3, "additions {index}");
            assert_eq!(direct.3, parent.4, "table bytes {index}");
        }
        for scalar in [-BigInt::from(1), BigInt::from(1) << 256usize,
                       -(BigInt::from(1) << 300usize)] {
            assert!(super::super::scalar_words_256(&scalar).is_none());
            let reduced = ((&scalar % &SCALAR_LATTICE.n) + &SCALAR_LATTICE.n)
                % &SCALAR_LATTICE.n;
            assert_eq!(multiply_word_format(&scalar, 24).0.affine_hex_binary_inverse(),
                       independent_binary_point(&reduced).affine_hex(),
                       "wide or signed fallback");
        }
    }

    #[test]
    fn direct_limb_mode_matches_complete_prior_and_fresh_points() {
        let panels = [
            include_str!("../../../../prime-j0-radix943-word-20261009/inputs.json"),
            include_str!("../../../../prime-j0-exact-reciprocal-20261010/fresh-inputs.json"),
            include_str!("../../../../prime-j0-certified-voronoi-20261010/fresh-inputs.json"),
            include_str!("../../../../prime-j0-fixed-limb-voronoi-20261010/fresh-inputs.json"),
            include_str!("../../../../prime-j0-hybrid-finalize-20261010/fresh-inputs.json"),
            include_str!("../../../../prime-j0-binary-inverse-20261010/fresh-inputs.json"),
            include_str!("../../../../prime-j0-direct-limb-scalar-20261010/fresh-inputs.json"),
        ];
        let mut cases = vec![BigInt::ZERO, BigInt::from(1),
                             &SCALAR_LATTICE.n - BigInt::from(1),
                             SCALAR_LATTICE.n.clone(),
                             (BigInt::from(1) << 256usize) - BigInt::from(1)];
        for panel in panels {
            let data: serde_json::Value = serde_json::from_str(panel).unwrap();
            cases.extend(data["scalars_hex"].as_array().unwrap().iter().map(|value|
                BigInt::parse_bytes(value.as_str().unwrap().as_bytes(), 16).unwrap()));
        }
        assert_eq!(cases.len(), 5 + 519 + 6 * 4096);
        let fresh_start = cases.len() - 4096;
        for (index, scalar) in cases.iter().enumerate() {
            let parent = multiply_word_format(scalar, 24);
            let direct = multiply_word_direct(super::super::scalar_words_256(scalar).unwrap());
            assert_eq!((direct.1.0.to_bigint(), direct.1.1.to_bigint()),
                       (parent.1, parent.2), "representative {index}");
            assert_eq!((direct.2, direct.3), (parent.3, parent.4),
                       "accounting {index}");
            assert_eq!(direct.0.affine_hex_binary_inverse(),
                       parent.0.affine_hex_binary_inverse(), "point {index}");
            if (fresh_start..fresh_start + 128).contains(&index) {
                let reduced = scalar % &SCALAR_LATTICE.n;
                assert_eq!(direct.0.affine_hex_binary_inverse(),
                           independent_binary_point(&reduced).affine_hex(),
                           "independent point {index}");
            }
        }
    }

    #[test]
    fn arithmetic_atlas_matches_every_u14_residue() {
        for width in [9u8, 10] {
            let stored = OrbitAtlas::new(width);
            let arithmetic = ArithmeticOrbitAtlas::new(width);
            assert_eq!(&*arithmetic.digits, &*stored.digits, "digit list width {width}");
            let base = 1usize << width;
            for ra in 0..base {
                for rb in 0..base {
                    assert_eq!(arithmetic.digit_residue(ra, rb),
                               stored.digit_residue(ra, rb),
                               "width {width} residue ({ra},{rb})");
                }
            }
        }
    }

    #[test]
    fn point_only_formula_matches_every_u14_residue() {
        for width in [9u8, 10] {
            let reference = ArithmeticOrbitAtlas::new(width);
            let base = 1usize << width;
            for ra in 0..base {
                for rb in 0..base {
                    assert_eq!(formula_digit_residue(width, ra, rb),
                               reference.digit_residue(ra, rb),
                               "width {width} residue ({ra},{rb})");
                }
            }
        }
    }

    #[test]
    fn canonical_sector_matches_every_u14_residue() {
        for width in [9u8, 10] {
            let base = 1usize << width;
            for ra in 0..base {
                for rb in 0..base {
                    assert_eq!(sector_digit_residue(width, ra, rb),
                               formula_digit_residue(width, ra, rb),
                               "width {width} residue ({ra},{rb})");
                }
            }
        }
    }

    #[test]
    fn canonical_sector_matches_every_radix256_residue() {
        let reference = OrbitAtlas::new(8);
        let arithmetic = ArithmeticOrbitAtlas::new(8);
        assert_eq!(reference.digits.len(), 10_924);
        assert_eq!(&*reference.digits, &*arithmetic.digits);
        for ra in 0..256 {
            for rb in 0..256 {
                assert_eq!(sector_digit_residue(8, ra, rb),
                           reference.digit_residue(ra, rb),
                           "radix256 residue ({ra},{rb})");
            }
        }
    }

    #[test]
    fn cache_sized_tables_match_independent_group_sums() {
        for (widths, tables, expected_slots, expected_bytes) in [
            (&WIDTHS15[..], &*SECTOR15_U256_TABLES, 458_772, 29_361_680),
            (&WIDTHS16[..], &*SECTOR16_U256_TABLES, 207_552, 13_283_616),
        ] {
            assert_eq!(tables.windows.len(), widths.len());
            assert_eq!(tables.retained_bytes, expected_bytes);
            let mut base = Jacobian::generator();
            let mut checked = 0usize;
            for (window, &width) in widths.iter().enumerate() {
                let atlas = ArithmeticOrbitAtlas::new(width);
                let tau_base = base.tau();
                let max_a = atlas.digits.iter().map(|d| d.0.unsigned_abs() as usize)
                    .max().unwrap();
                let max_b = atlas.digits.iter().map(|d| d.1.unsigned_abs() as usize)
                    .max().unwrap();
                let a_points = binary_multiples(base, max_a);
                let b_projective = binary_multiples(tau_base, max_b);
                let mut b_points = vec![Jacobian::identity()];
                b_points.extend(batch_to_affine(&b_projective[1..]));
                let expected = atlas.digits.iter().skip(1).map(|&(a, b)| {
                    let first = if a < 0 { a_points[a.unsigned_abs() as usize].neg() }
                                else { a_points[a as usize] };
                    let second = if b < 0 { b_points[b.unsigned_abs() as usize].neg() }
                                 else { b_points[b as usize] };
                    if first.is_identity() { second }
                    else if second.is_identity() { first }
                    else { first.add_mixed(second) }
                }).collect::<Vec<_>>();
                let expected = batch_to_affine(&expected);
                assert_eq!(tables.windows[window].len(), atlas.digits.len());
                for (orbit, point) in expected.iter().enumerate() {
                    let stored = tables.windows[window][orbit + 1];
                    assert_eq!(stored.x.0, super::super::hybrid_pair_mont(point.x).0,
                               "window {window} orbit {} x", orbit + 1);
                    assert_eq!(stored.y.0, super::super::hybrid_pair_mont(point.y).0,
                               "window {window} orbit {} y", orbit + 1);
                    checked += 1;
                }
                checked += 1;
                for _ in 0..width { base = base.double(); }
            }
            assert_eq!(checked, expected_slots);
        }
    }

    #[test]
    fn u256_table_points_and_unit_images_match_eisenstein_field() {
        let compact = &*TABLES;
        let converted = &*U256_TABLES;
        let ctx = &super::super::HYBRID_FIELD.0;
        let seven = ctx.to_montgomery(&super::super::Uint([7, 0, 0, 0]));
        assert!(converted.retained_bytes < compact.retained_bytes);
        assert_eq!(compact.windows.len(), converted.windows.len());
        let mut checked = 0usize;
        for (old_row, new_row) in compact.windows.iter().zip(&converted.windows) {
            assert_eq!(old_row.len(), new_row.len());
            for &point in new_row.iter().skip(1) {
                let left = u256_square(point.y);
                let right = u256_add(u256_mul(u256_square(point.x), point.x), seven);
                assert!(bool::from(left.ct_eq_full(&right)),
                        "converted table point {checked} is off curve");
                checked += 1;
            }
        }
        assert!(checked > 1_000_000);
        let mut state = 0xd19a_7d26_4ce2_831bu64;
        for sample in 0..512 {
            state ^= state << 13;
            state ^= state >> 7;
            state ^= state << 17;
            let row = state as usize % compact.windows.len();
            let index = 1 + ((state >> 16) as usize % (compact.windows[row].len() - 1));
            let source = compact.windows[row][index].into_affine();
            for code in 0..6 {
                let mut expected = source;
                for _ in 0..(code / 2) { expected = expected.omega(); }
                if code & 1 != 0 { expected = expected.neg(); }
                let actual = converted.windows[row][index].unit(code);
                assert_eq!(hex::encode(ctx.from_montgomery(&actual.x).to_bytes_be()),
                           expected.x.canonical_hex(), "x sample {sample}, unit {code}");
                assert_eq!(hex::encode(ctx.from_montgomery(&actual.y).to_bytes_be()),
                           expected.y.canonical_hex(), "y sample {sample}, unit {code}");
            }
        }
    }

    #[test]
    fn u256_jacobian_group_law_matches_pair_backend() {
        let source = &*TABLES;
        let converted = &*U256_TABLES;
        let old_q = source.windows[0][1].into_affine();
        let new_q = converted.windows[0][1];
        assert_eq!(U256Jacobian::identity().add_mixed(new_q).affine_hex_binary_inverse(),
                   old_q.affine_hex_binary_inverse());
        assert!(U256Jacobian::from_affine(new_q).add_mixed(new_q.unit(1)).is_identity());
        assert_eq!(U256Jacobian::from_affine(new_q).add_mixed(new_q)
                       .affine_hex_binary_inverse(),
                   old_q.double().affine_hex_binary_inverse());
        let fresh: serde_json::Value = serde_json::from_str(include_str!(
            "../../../../prime-j0-u256-point-20261010/fresh-inputs.json"
        )).unwrap();
        for (sample, value) in fresh["scalars_hex"].as_array().unwrap().iter().take(512).enumerate() {
            let scalar = BigInt::parse_bytes(value.as_str().unwrap().as_bytes(), 16).unwrap();
            let parent = multiply_word_direct(super::super::scalar_words_256(&scalar).unwrap()).0;
            let new_parent = U256Jacobian {
                x: super::super::hybrid_pair_mont(parent.x),
                y: super::super::hybrid_pair_mont(parent.y),
                z: super::super::hybrid_pair_mont(parent.z),
            };
            let row = sample % WIDTHS.len();
            let slot = 1 + ((sample * 7919) % (source.windows[row].len() - 1));
            let expected = parent.add_mixed(source.windows[row][slot].into_affine());
            let actual = new_parent.add_mixed(converted.windows[row][slot]);
            assert_eq!(actual.affine_hex_binary_inverse(),
                       expected.affine_hex_binary_inverse(), "addition {sample}");
        }
    }

    #[test]
    fn u256_backend_matches_complete_prior_and_fresh_points() {
        let panels = [
            include_str!("../../../../prime-j0-radix943-word-20261009/inputs.json"),
            include_str!("../../../../prime-j0-exact-reciprocal-20261010/fresh-inputs.json"),
            include_str!("../../../../prime-j0-certified-voronoi-20261010/fresh-inputs.json"),
            include_str!("../../../../prime-j0-fixed-limb-voronoi-20261010/fresh-inputs.json"),
            include_str!("../../../../prime-j0-hybrid-finalize-20261010/fresh-inputs.json"),
            include_str!("../../../../prime-j0-binary-inverse-20261010/fresh-inputs.json"),
            include_str!("../../../../prime-j0-direct-limb-scalar-20261010/fresh-inputs.json"),
            include_str!("../../../../prime-j0-u256-point-20261010/fresh-inputs.json"),
        ];
        let mut cases = vec![BigInt::ZERO, BigInt::from(1),
                             &SCALAR_LATTICE.n - BigInt::from(1),
                             SCALAR_LATTICE.n.clone(),
                             (BigInt::from(1) << 256usize) - BigInt::from(1)];
        for panel in panels {
            let data: serde_json::Value = serde_json::from_str(panel).unwrap();
            cases.extend(data["scalars_hex"].as_array().unwrap().iter().map(|value|
                BigInt::parse_bytes(value.as_str().unwrap().as_bytes(), 16).unwrap()));
        }
        assert_eq!(cases.len(), 5 + 519 + 7 * 4096);
        let fresh_start = cases.len() - 4096;
        for (index, scalar) in cases.iter().enumerate() {
            let words = super::super::scalar_words_256(scalar).unwrap();
            let parent = multiply_word_direct(words);
            let candidate = multiply_u256_direct(words);
            assert_eq!(candidate.1, parent.1, "representative {index}");
            assert_eq!((candidate.2, candidate.4, candidate.5),
                       (parent.2, parent.4, parent.5), "accounting {index}");
            assert_eq!(candidate.3, U256_TABLES.retained_bytes);
            assert_eq!(candidate.0, parent.0.affine_hex_binary_inverse(),
                       "point {index}");
            if (fresh_start..fresh_start + 128).contains(&index) {
                let reduced = scalar % &SCALAR_LATTICE.n;
                assert_eq!(candidate.0, independent_binary_point(&reduced).affine_hex(),
                           "independent point {index}");
            }
            let (mut a, mut b) = parent.1;
            let (mut ca, mut cb) = candidate.1;
            for &width in &WIDTHS {
                let lhs = TABLES.atlas(width).digit_word(a, b);
                let rhs = U256_TABLES.atlas(width).digit_word(ca, cb);
                assert_eq!(lhs, rhs, "orbit and unit {index}");
                a = a.sub(Signed192::from_i32(lhs.0.0)).div_exact_power_of_two(width);
                b = b.sub(Signed192::from_i32(lhs.0.1)).div_exact_power_of_two(width);
                ca = ca.sub(Signed192::from_i32(rhs.0.0)).div_exact_power_of_two(width);
                cb = cb.sub(Signed192::from_i32(rhs.0.1)).div_exact_power_of_two(width);
            }
        }
    }

    #[test]
    fn u256_gauge_rotation_commutes_with_mixed_group_law() {
        let tables = &*U256_TABLES;
        let q = tables.windows[0][1];
        assert!(U256Jacobian::identity().rotate_power(1).is_identity());
        assert!(U256Jacobian::from_affine(q).add_mixed(q.unit(1))
                .rotate_power(2).is_identity());
        let doubled = U256Jacobian::from_affine(q).add_mixed(q);
        for power in 1..=2 {
            let rotated = q.unit(2 * power);
            assert_eq!(doubled.rotate_power(power).affine_hex_binary_inverse(),
                       U256Jacobian::from_affine(rotated).add_mixed(rotated)
                           .affine_hex_binary_inverse(), "equal addend, power {power}");
        }
        for sample in 0..512 {
            let row = sample % WIDTHS.len();
            let first = tables.windows[row][1 + ((sample * 7919) %
                                (tables.windows[row].len() - 1))];
            let second = tables.windows[row][1 + ((sample * 4001 + 17) %
                                 (tables.windows[row].len() - 1))];
            let parent = U256Jacobian::from_affine(first).add_mixed(second);
            for power in 1..=2 {
                let expected = U256Jacobian::from_affine(first.unit(2 * power))
                    .add_mixed(second.unit(2 * power));
                assert_eq!(parent.rotate_power(power).affine_hex_binary_inverse(),
                           expected.affine_hex_binary_inverse(),
                           "rotation {sample}, power {power}");
            }
        }
    }

    #[test]
    fn u256_grouped_gauge_matches_complete_prior_and_fresh_points() {
        let panels = [
            include_str!("../../../../prime-j0-radix943-word-20261009/inputs.json"),
            include_str!("../../../../prime-j0-exact-reciprocal-20261010/fresh-inputs.json"),
            include_str!("../../../../prime-j0-certified-voronoi-20261010/fresh-inputs.json"),
            include_str!("../../../../prime-j0-fixed-limb-voronoi-20261010/fresh-inputs.json"),
            include_str!("../../../../prime-j0-hybrid-finalize-20261010/fresh-inputs.json"),
            include_str!("../../../../prime-j0-binary-inverse-20261010/fresh-inputs.json"),
            include_str!("../../../../prime-j0-direct-limb-scalar-20261010/fresh-inputs.json"),
            include_str!("../../../../prime-j0-u256-point-20261010/fresh-inputs.json"),
            include_str!("../../../../prime-j0-u14-gauge-20261010/fresh-inputs.json"),
        ];
        let mut scalars = vec![BigInt::ZERO, BigInt::from(1),
                               &SCALAR_LATTICE.n - BigInt::from(1),
                               SCALAR_LATTICE.n.clone(),
                               (BigInt::from(1) << 256usize) - BigInt::from(1)];
        for panel in panels {
            let data: serde_json::Value = serde_json::from_str(panel).unwrap();
            scalars.extend(data["scalars_hex"].as_array().unwrap().iter().map(|value|
                BigInt::parse_bytes(value.as_str().unwrap().as_bytes(), 16).unwrap()));
        }
        assert_eq!(scalars.len(), 5 + 519 + 8 * 4096);
        let fresh_start = scalars.len() - 4096;
        let mut reference_products = 0usize;
        let mut gauge_products = 0usize;
        let mut per_scalar_counts = Vec::with_capacity(2 * scalars.len());
        for (index, scalar) in scalars.iter().enumerate() {
            let words = super::super::scalar_words_256(scalar).unwrap();
            let reference = multiply_u256_direct(words);
            let candidate = multiply_u256_gauge(words);
            assert_eq!(candidate.0, reference.0, "point {index}");
            assert_eq!(candidate.1, reference.1, "representative {index}");
            assert_eq!((candidate.2, candidate.3, candidate.4, candidate.5),
                       (reference.2, reference.3, reference.4, reference.5),
                       "accounting {index}");
            assert!(candidate.6 <= 2, "gauge products {index}");
            let (choices, count) = u256_gauge_choices(candidate.1, &U256_TABLES);
            assert_eq!(count.saturating_sub(1), candidate.2);
            let original_products = choices.iter()
                .filter(|&&(orbit, code)| orbit != 0 && code / 2 != 0).count();
            reference_products += original_products;
            gauge_products += candidate.6;
            per_scalar_counts.push(original_products as u8);
            per_scalar_counts.push(candidate.6 as u8);
            let (mut a, mut b) = reference.1;
            for (window, &width) in WIDTHS.iter().enumerate() {
                let (digit, orbit, code) = TABLES.atlas(width).digit_word(a, b);
                assert_eq!(choices[window], (orbit, code), "orbit/unit {index}/{window}");
                a = a.sub(Signed192::from_i32(digit.0)).div_exact_power_of_two(width);
                b = b.sub(Signed192::from_i32(digit.1)).div_exact_power_of_two(width);
            }
            if (fresh_start..fresh_start + 128).contains(&index) {
                let reduced = scalar % &SCALAR_LATTICE.n;
                assert_eq!(candidate.0, independent_binary_point(&reduced).affine_hex(),
                           "independent point {index}");
            }
        }
        println!("gauge_panel_cases={} reference_beta_products={} gauge_beta_products={} counts_hex={}",
                 scalars.len(), reference_products, gauge_products, hex::encode(per_scalar_counts));
    }

    #[test]
    fn u256_arithmetic_atlas_matches_new_holdout_and_gauge_table() {
        let old = &*U256_TABLES;
        let new = &*ARITHMETIC_U256_TABLES;
        let saved = old.retained_bytes - new.retained_bytes;
        assert!((5_242_880..5_243_000).contains(&saved), "saved bytes {saved}");
        for (window, (left, right)) in old.windows.iter().zip(&new.windows).enumerate() {
            assert_eq!(left.len(), right.len(), "window size {window}");
            for (index, (a, b)) in left.iter().zip(right).enumerate() {
                assert_eq!(a.x.0, b.x.0, "window {window} point {index} x");
                assert_eq!(a.y.0, b.y.0, "window {window} point {index} y");
            }
        }
        let panel: serde_json::Value = serde_json::from_str(include_str!(
            "../../../../prime-j0-arithmetic-atlas-20261010/fresh-inputs.json"
        )).unwrap();
        let scalars = panel["scalars_hex"].as_array().unwrap();
        assert_eq!(scalars.len(), 4096);
        let mut per_scalar_counts = Vec::with_capacity(2 * scalars.len());
        for (index, text) in scalars.iter().enumerate() {
            let scalar = BigInt::parse_bytes(text.as_str().unwrap().as_bytes(), 16).unwrap();
            let words = super::super::scalar_words_256(&scalar).unwrap();
            let reference = multiply_u256_gauge(words);
            let candidate = multiply_u256_arithmetic(words);
            assert_eq!(reference.0, candidate.0, "point {index}");
            assert_eq!(reference.1, candidate.1, "representative {index}");
            assert_eq!((reference.2, reference.4, reference.5, reference.6),
                       (candidate.2, candidate.4, candidate.5, candidate.6),
                       "scalar accounting {index}");
            let old_choices = u256_gauge_choices(reference.1, old);
            let new_choices = u256_arithmetic_choices(candidate.1, new);
            assert_eq!(old_choices, new_choices, "all fourteen choices {index}");
            per_scalar_counts.push(reference.6 as u8);
            per_scalar_counts.push(candidate.6 as u8);
            if index < 128 {
                let reduced = &scalar % &SCALAR_LATTICE.n;
                assert_eq!(candidate.0, independent_binary_point(&reduced).affine_hex(),
                           "independent point {index}");
            }
        }
        println!("arithmetic_panel_cases={} retained_reference={} retained_candidate={} counts_hex={}",
                 scalars.len(), old.retained_bytes, new.retained_bytes,
                 hex::encode(per_scalar_counts));
    }

    #[test]
    fn u256_point_only_table_matches_new_holdout_and_arithmetic_table() {
        let old = &*ARITHMETIC_U256_TABLES;
        let new = &*FORMULA_U256_TABLES;
        let saved = old.retained_bytes - new.retained_bytes;
        assert!((873_824..873_940).contains(&saved), "saved bytes {saved}");
        for (window, (left, right)) in old.windows.iter().zip(&new.windows).enumerate() {
            assert_eq!(left.len(), right.len(), "window size {window}");
            for (index, (a, b)) in left.iter().zip(right).enumerate() {
                assert_eq!(a.x.0, b.x.0, "window {window} point {index} x");
                assert_eq!(a.y.0, b.y.0, "window {window} point {index} y");
            }
        }
        let panel: serde_json::Value = serde_json::from_str(include_str!(
            "../../../../prime-j0-formula-atlas-20261010/fresh-inputs.json"
        )).unwrap();
        let scalars = panel["scalars_hex"].as_array().unwrap();
        assert_eq!(scalars.len(), 4096);
        let mut per_scalar_counts = Vec::with_capacity(2 * scalars.len());
        for (index, text) in scalars.iter().enumerate() {
            let scalar = BigInt::parse_bytes(text.as_str().unwrap().as_bytes(), 16).unwrap();
            let words = super::super::scalar_words_256(&scalar).unwrap();
            let reference = multiply_u256_arithmetic(words);
            let candidate = multiply_u256_formula(words);
            assert_eq!(reference.0, candidate.0, "point {index}");
            assert_eq!(reference.1, candidate.1, "representative {index}");
            assert_eq!((reference.2, reference.4, reference.5, reference.6),
                       (candidate.2, candidate.4, candidate.5, candidate.6),
                       "scalar accounting {index}");
            let old_choices = u256_arithmetic_choices(reference.1, old);
            let new_choices = u256_formula_choices(candidate.1);
            assert_eq!(old_choices, new_choices, "all fourteen choices {index}");
            per_scalar_counts.push(reference.6 as u8);
            per_scalar_counts.push(candidate.6 as u8);
            if index < 128 {
                let reduced = &scalar % &SCALAR_LATTICE.n;
                assert_eq!(candidate.0, independent_binary_point(&reduced).affine_hex(),
                           "independent point {index}");
            }
        }
        println!("formula_panel_cases={} retained_reference={} retained_candidate={} counts_hex={}",
                 scalars.len(), old.retained_bytes, new.retained_bytes,
                 hex::encode(per_scalar_counts));
    }

    #[test]
    fn u256_sector_digit_matches_new_holdout_and_point_table() {
        let old = &*FORMULA_U256_TABLES;
        let new = &*SECTOR_U256_TABLES;
        assert_eq!(old.retained_bytes, 64_314_112);
        assert_eq!(new.retained_bytes, old.retained_bytes);
        for (window, (left, right)) in old.windows.iter().zip(&new.windows).enumerate() {
            assert_eq!(left.len(), right.len(), "window size {window}");
            for (index, (a, b)) in left.iter().zip(right).enumerate() {
                assert_eq!(a.x.0, b.x.0, "window {window} point {index} x");
                assert_eq!(a.y.0, b.y.0, "window {window} point {index} y");
            }
        }
        let panel: serde_json::Value = serde_json::from_str(include_str!(
            "../../../../prime-j0-sector-digit-20261010/fresh-inputs.json"
        )).unwrap();
        let scalars = panel["scalars_hex"].as_array().unwrap();
        assert_eq!(scalars.len(), 4096);
        let mut per_scalar_counts = Vec::with_capacity(2 * scalars.len());
        for (index, text) in scalars.iter().enumerate() {
            let scalar = BigInt::parse_bytes(text.as_str().unwrap().as_bytes(), 16).unwrap();
            let words = super::super::scalar_words_256(&scalar).unwrap();
            let reference = multiply_u256_formula(words);
            let candidate = multiply_u256_sector(words);
            assert_eq!(reference.0, candidate.0, "point {index}");
            assert_eq!(reference.1, candidate.1, "representative {index}");
            assert_eq!((reference.2, reference.3, reference.4, reference.5, reference.6),
                       (candidate.2, candidate.3, candidate.4, candidate.5, candidate.6),
                       "scalar accounting {index}");
            assert_eq!(u256_formula_choices(reference.1),
                       u256_sector_choices(candidate.1),
                       "all fourteen choices {index}");
            per_scalar_counts.push(reference.6 as u8);
            per_scalar_counts.push(candidate.6 as u8);
            if index < 128 {
                let reduced = &scalar % &SCALAR_LATTICE.n;
                assert_eq!(candidate.0, independent_binary_point(&reduced).affine_hex(),
                           "independent point {index}");
            }
        }
        println!("sector_panel_cases={} retained_reference={} retained_candidate={} counts_hex={}",
                 scalars.len(), old.retained_bytes, new.retained_bytes,
                 hex::encode(per_scalar_counts));
    }

    #[test]
    fn cache_sized_sector_formats_match_fresh_panel() {
        let panel: serde_json::Value = serde_json::from_str(include_str!(
            "../../../../prime-j0-cache-window-20261010/fresh-inputs.json"
        )).unwrap();
        let scalars = panel["scalars_hex"].as_array().unwrap();
        assert_eq!(scalars.len(), 4096);
        let atlases = [OrbitAtlas::new(8), OrbitAtlas::new(9), OrbitAtlas::new(10)];
        let reference_choices = |representative: (Signed192, Signed192), widths: &[u8]| {
            let (mut a, mut b) = representative;
            let mut choices = Vec::with_capacity(widths.len());
            for &width in widths {
                let (digit, orbit, unit) = atlases[usize::from(width - 8)].digit_word(a, b);
                choices.push((orbit, unit));
                a = a.sub(Signed192::from_i32(digit.0)).div_exact_power_of_two(width);
                b = b.sub(Signed192::from_i32(digit.1)).div_exact_power_of_two(width);
            }
            assert!(a.is_zero() && b.is_zero());
            choices
        };
        let mut counts = Vec::with_capacity(6 * scalars.len());
        for (index, text) in scalars.iter().enumerate() {
            let scalar = BigInt::parse_bytes(text.as_str().unwrap().as_bytes(), 16).unwrap();
            let words = super::super::scalar_words_256(&scalar).unwrap();
            let u14 = multiply_u256_sector(words);
            let u15 = multiply_u256_sector15(words);
            let u16 = multiply_u256_sector16(words);
            assert_eq!(u14.3, 64_314_112);
            for (label, candidate, widths, bytes) in [
                ("U14", &u14, &WIDTHS[..], 64_314_112),
                ("U15", &u15, &WIDTHS15[..], 29_361_680),
                ("U16", &u16, &WIDTHS16[..], 13_283_616),
            ] {
                assert_eq!(candidate.0, u14.0, "{label} point {index}");
                assert_eq!(candidate.1, u14.1, "{label} representative {index}");
                assert_eq!((candidate.4, candidate.5), (u14.4, u14.5),
                           "{label} scalar selector {index}");
                assert_eq!(candidate.3, bytes, "{label} retained bytes {index}");
                let choices = reference_choices(candidate.1, widths);
                let actual = if widths.len() == 14 {
                    u256_sector_choices(candidate.1).0.to_vec()
                } else if widths.len() == 15 {
                    u256_sector_choices_with(candidate.1, &WIDTHS15).0.to_vec()
                } else {
                    u256_sector_choices_with(candidate.1, &WIDTHS16).0.to_vec()
                };
                assert_eq!(actual, choices, "{label} choices {index}");
                assert_eq!(candidate.2,
                           choices.iter().filter(|&&(orbit, _)| orbit != 0)
                               .count().saturating_sub(1),
                           "{label} additions {index}");
                assert!(candidate.6 <= 2, "{label} gauge products {index}");
                counts.extend([candidate.2 as u8, candidate.6 as u8]);
            }
            if index < 128 {
                let reduced = &scalar % &SCALAR_LATTICE.n;
                assert_eq!(u14.0, independent_binary_point(&reduced).affine_hex(),
                           "independent point {index}");
            }
        }
        println!("cache_panel_cases={} bytes_u14={} bytes_u15={} bytes_u16={} counts_hex={}",
                 scalars.len(), SECTOR_U256_TABLES.retained_bytes,
                 SECTOR15_U256_TABLES.retained_bytes,
                 SECTOR16_U256_TABLES.retained_bytes, hex::encode(counts));
    }

    #[test]
    fn radix943_atlas_covers_all_residues_and_fixture_points() {
        let tables = &*RADIX13_TABLES;
        assert_eq!(tables.windows.len(), RADIX13_WINDOWS);
        assert!(tables.retained_bytes >= 1_926_717 * size_of::<CompactPairPoint>());
        assert!(tables.retained_bytes < RADIX13_CAP_BYTES);
        for ra in 0..RADIX13 {
            for rb in 0..RADIX13 {
                let (digit, orbit_id, unit_code) = tables.atlas.digit_residue(ra, rb);
                assert_eq!((digit.0.rem_euclid(RADIX13 as i32) as usize,
                            digit.1.rem_euclid(RADIX13 as i32) as usize), (ra, rb));
                assert!(3 * norm(digit) <= (RADIX13 * RADIX13) as i64);
                assert!(orbit_id < tables.atlas.digits.len() && unit_code < 6);
            }
        }
        let fixture: serde_json::Value = serde_json::from_str(include_str!(
            "../../../tau6-comb13-bench-fixture.json"
        )).unwrap();
        for (case_index, case) in fixture["cases"].as_array().unwrap().iter().enumerate() {
            let scalar = BigInt::parse_bytes(case["scalar_hex"].as_str().unwrap().as_bytes(), 16)
                .unwrap();
            let (point, a, b, additions, retained) = multiply_radix13(&scalar);
            assert_eq!(retained, tables.retained_bytes);
            assert!(additions <= 12);
            assert_eq!((&a + &b * &SCALAR_LATTICE.lambda_tau - &scalar) % &SCALAR_LATTICE.n,
                       BigInt::ZERO);
            let expected = if case["expected_identity"].as_bool() == Some(true) {
                "identity".to_owned()
            } else {
                format!("{}:{}", case["expected_x_hex"].as_str().unwrap(),
                        case["expected_y_hex"].as_str().unwrap())
            };
            assert_eq!(point.affine_hex(), expected, "case {case_index}");
        }
    }

    fn binary_multiples(base: Jacobian, max: usize) -> Vec<Jacobian> {
        let mut powers = Vec::new();
        let mut power = base;
        while (1usize << powers.len()) <= max {
            powers.push(power.into_affine());
            power = power.double();
        }
        (0..=max)
            .map(|scalar| {
                let mut result = Jacobian::identity();
                for (bit, point) in powers.iter().enumerate() {
                    if scalar & (1 << bit) != 0 {
                        result = result.add_mixed(*point);
                    }
                }
                result
            })
            .collect()
    }

    fn same_point(projective: Jacobian, affine: Jacobian) -> bool {
        if projective.is_identity() || affine.is_identity() {
            return projective.is_identity() && affine.is_identity();
        }
        let z2 = projective.z.mul(projective.z);
        let z3 = z2.mul(projective.z);
        projective.x.sub_field(affine.x.mul(z2)).is_zero()
            && projective.y.sub_field(affine.y.mul(z3)).is_zero()
    }

    #[test]
    fn unit_orbit_maps_cover_every_residue_with_bounded_digits() {
        for width in [8, 9, 10] {
            let atlas = OrbitAtlas::new(width);
            let base = atlas.base() as i32;
            for a in 0..base {
                for b in 0..base {
                    let ((da, db), _, _) = atlas.digit(&BigInt::from(a), &BigInt::from(b));
                    assert_eq!((da.rem_euclid(base), db.rem_euclid(base)), (a, b));
                    assert!(3 * norm((da, db)) <= i64::from(base) * i64::from(base));
                }
            }
        }
    }

    #[test]
    fn all_schedules_reconstruct_boundaries() {
        let large = OrbitAtlas::new(10);
        let small = OrbitAtlas::new(9);
        let tiny = OrbitAtlas::new(8);
        let n = &SCALAR_LATTICE.n;
        for widths in [&WIDTHS[..], &WIDTHS15[..], &WIDTHS16[..]] {
            for scalar in [BigInt::ZERO, BigInt::from(1), BigInt::from(2), n - 2, n - 1] {
                let (mut a, mut b) = hexagonal_four_corner_choices(&scalar).remove(0);
                let start = (a.clone(), b.clone());
                let mut factor = BigInt::from(1);
                let mut rebuilt = (BigInt::ZERO, BigInt::ZERO);
                for &width in widths {
                    let atlas = match width {
                        8 => &tiny,
                        9 => &small,
                        10 => &large,
                        _ => unreachable!(),
                    };
                    let ((da, db), _, _) = atlas.digit(&a, &b);
                    rebuilt.0 += &factor * da;
                    rebuilt.1 += &factor * db;
                    let base = BigInt::from(atlas.base());
                    a = (a - da) / &base;
                    b = (b - db) / &base;
                    factor *= base;
                }
                assert_eq!((a, b), (BigInt::ZERO, BigInt::ZERO));
                assert_eq!(rebuilt, start);
            }
        }
    }

    #[test]
    fn word_power_of_two_updates_match_bigint_at_sign_and_limb_boundaries() {
        let high: BigInt = BigInt::from(1) << 129;
        for width in [8u8, 9, 10] {
            let base = BigInt::from(1) << width;
            for value in [
                -&high - 1, -&high, -&base - 1, -&base, BigInt::from(-1),
                BigInt::ZERO, BigInt::from(1), &base - 1, base.clone(),
                &high - 1, high.clone(), &high + 1,
            ] {
                let word = Signed192::from_bigint(&value);
                let remainder = ((&value % &base + &base) % &base).to_usize().unwrap();
                assert_eq!(word.rem_euclid_power_of_two(width), remainder);
                let quotient = word
                    .sub(Signed192::from_i32(remainder as i32))
                    .div_exact_power_of_two(width);
                let expected = (&value - remainder) / &base;
                assert_eq!(BigInt::from_biguint(
                    if quotient.negative { num_bigint::Sign::Minus } else { num_bigint::Sign::Plus },
                    num_bigint::BigUint::from_bytes_le(&quotient.limbs.iter()
                        .flat_map(|word| word.to_le_bytes()).collect::<Vec<_>>()),
                ), expected);
            }
        }
    }

    #[test]
    fn word_recoder_matches_bigint_and_independent_fixture_points() {
        let fixture: serde_json::Value = serde_json::from_str(include_str!(
            "../../../tau6-comb13-bench-fixture.json"
        )).unwrap();
        for format in [14, 15, 16] {
            for (case_index, case) in fixture["cases"].as_array().unwrap().iter().enumerate() {
                let scalar = BigInt::parse_bytes(case["scalar_hex"].as_str().unwrap().as_bytes(), 16)
                    .unwrap();
                let old = multiply_format(&scalar, format);
                let word = multiply_word_format(&scalar, format);
                assert_eq!((&word.1, &word.2, word.3, word.4),
                           (&old.1, &old.2, old.3, old.4));
                let tables = selected(format);
                let (mut old_a, mut old_b) = (old.1.clone(), old.2.clone());
                let (mut word_a, mut word_b) =
                    (Signed192::from_bigint(&old_a), Signed192::from_bigint(&old_b));
                for (window, &width) in tables.widths.iter().enumerate() {
                    let atlas = tables.atlas(width);
                    let digit = atlas.digit(&old_a, &old_b);
                    assert_eq!(atlas.digit_word(word_a, word_b), digit,
                               "format {format}, case {case_index}, window {window}");
                    let base = BigInt::from(atlas.base());
                    old_a = (old_a - digit.0.0) / &base;
                    old_b = (old_b - digit.0.1) / &base;
                    word_a = word_a.sub(Signed192::from_i32(digit.0.0))
                        .div_exact_power_of_two(width);
                    word_b = word_b.sub(Signed192::from_i32(digit.0.1))
                        .div_exact_power_of_two(width);
                    assert_eq!(word_a, Signed192::from_bigint(&old_a),
                               "format {format}, case {case_index}, window {window} a");
                    assert_eq!(word_b, Signed192::from_bigint(&old_b),
                               "format {format}, case {case_index}, window {window} b");
                }
                assert_eq!(word.0.affine_hex(), old.0.affine_hex(),
                           "format {format}, case {case_index}");
                let expected = if case["expected_identity"].as_bool() == Some(true) {
                    "identity".to_owned()
                } else {
                    format!("{}:{}", case["expected_x_hex"].as_str().unwrap(),
                            case["expected_y_hex"].as_str().unwrap())
                };
                assert_eq!(word.0.affine_hex(), expected);
            }
        }
    }

    #[test]
    fn word_recoder_matches_bigint_on_fresh_full_range_scalars() {
        let mut state = 0x58bd_0c71_9a46_e253u64;
        for case_index in 0..256 {
            let mut bytes = [0u8; 32];
            for chunk in bytes.chunks_exact_mut(8) {
                state ^= state >> 12;
                state ^= state << 25;
                state ^= state >> 27;
                chunk.copy_from_slice(&state.wrapping_mul(0x2545_f491_4f6c_dd1d).to_be_bytes());
            }
            let scalar = BigInt::from_bytes_be(num_bigint::Sign::Plus, &bytes)
                % &SCALAR_LATTICE.n;
            for format in [14, 15, 16] {
                let old = multiply_format(&scalar, format);
                let word = multiply_word_format(&scalar, format);
                assert_eq!((&word.1, &word.2, word.3, word.4),
                           (&old.1, &old.2, old.3, old.4),
                           "format {format}, case {case_index}");
                assert_eq!(word.0.affine_hex(), old.0.affine_hex(),
                           "format {format}, case {case_index}");
            }
        }
    }

    #[test]
    fn all_window_points_match_independent_group_sums() {
        for (format, expected_slots) in [(14, 1_004_904), (15, 458_772), (16, 207_552)] {
            let tables = selected(format);
            let mut base = Jacobian::generator();
            let mut checked = 0;
            for (window, &width) in tables.widths.iter().enumerate() {
                let atlas = tables.atlas(width);
                let tau_base = base.tau();
                let max_a = atlas
                    .digits
                    .iter()
                    .map(|d| d.0.unsigned_abs() as usize)
                    .max()
                    .unwrap();
                let max_b = atlas
                    .digits
                    .iter()
                    .map(|d| d.1.unsigned_abs() as usize)
                    .max()
                    .unwrap();
                let a_points = binary_multiples(base, max_a);
                let b_projective = binary_multiples(tau_base, max_b);
                let mut b_points = vec![Jacobian::identity()];
                b_points.extend(batch_to_affine(&b_projective[1..]));
                for (orbit, &(a, b)) in atlas.digits.iter().enumerate() {
                    let first = if a < 0 {
                        a_points[a.unsigned_abs() as usize].neg()
                    } else {
                        a_points[a as usize]
                    };
                    let second = if b < 0 {
                        b_points[b.unsigned_abs() as usize].neg()
                    } else {
                        b_points[b as usize]
                    };
                    let expected = if first.is_identity() {
                        second
                    } else if second.is_identity() {
                        first
                    } else {
                        first.add_mixed(second)
                    };
                    let packed = tables.windows[window][orbit];
                    if orbit == 0 {
                        assert_eq!((a, b), (0, 0));
                        assert!(expected.is_identity());
                        assert_eq!(packed.limbs, [[0; 2]; 4]);
                        assert_eq!(packed.signs, 0);
                    } else {
                        let stored = packed.into_affine();
                        assert!(
                            same_point(expected, stored),
                            "window {window}, orbit {orbit}"
                        );
                    }
                    checked += 1;
                }
                for _ in 0..width {
                    base = base.double();
                }
            }
            assert_eq!(checked, expected_slots);
        }
    }

    #[test]
    fn radix943_all_window_points_match_independent_group_sums() {
        let tables = &*RADIX13_TABLES;
        let atlas = &tables.atlas;
        let mut base = Jacobian::generator();
        let mut checked = 0usize;
        for (window, row) in tables.windows.iter().enumerate() {
            let tau_base = base.tau();
            let max_a = atlas.digits.iter()
                .map(|d| d.0.unsigned_abs() as usize).max().unwrap();
            let max_b = atlas.digits.iter()
                .map(|d| d.1.unsigned_abs() as usize).max().unwrap();
            let a_points = binary_multiples(base, max_a);
            let b_projective = binary_multiples(tau_base, max_b);
            let mut b_points = vec![Jacobian::identity()];
            b_points.extend(batch_to_affine(&b_projective[1..]));
            for (orbit, &(a, b)) in atlas.digits.iter().enumerate() {
                let first = if a < 0 {
                    a_points[a.unsigned_abs() as usize].neg()
                } else {
                    a_points[a as usize]
                };
                let second = if b < 0 {
                    b_points[b.unsigned_abs() as usize].neg()
                } else {
                    b_points[b as usize]
                };
                let expected = if first.is_identity() {
                    second
                } else if second.is_identity() {
                    first
                } else {
                    first.add_mixed(second)
                };
                let packed = row[orbit];
                if orbit == 0 {
                    assert_eq!((a, b), (0, 0));
                    assert!(expected.is_identity());
                    assert_eq!(packed.limbs, [[0; 2]; 4]);
                    assert_eq!(packed.signs, 0);
                } else {
                    assert!(same_point(expected, packed.into_affine()),
                            "window {window}, orbit {orbit}");
                }
                checked += 1;
            }
            if window + 1 < RADIX13_WINDOWS {
                base = affine_multiples(base, RADIX13).pop().unwrap();
            }
        }
        assert_eq!(checked, 1_926_717);
    }

    fn check_tau_orbit_window_points(tables: &TauBucketTables, expected_entries: usize) {
        let digits = tables.atlas.seed_digits();
        let mut base = Jacobian::generator();
        let mut checked = 0usize;
        for (window, row) in tables.windows.iter().enumerate() {
            let tau_base = base.tau();
            let max_a = digits.iter().map(|d| d.0.unsigned_abs() as usize).max().unwrap();
            let max_b = digits.iter().map(|d| d.1.unsigned_abs() as usize).max().unwrap();
            let a_points = binary_multiples(base, max_a);
            let b_projective = binary_multiples(tau_base, max_b);
            let mut b_points = vec![Jacobian::identity()];
            b_points.extend(batch_to_affine(&b_projective[1..]));
            for (seed_id, &(a, b)) in digits.iter().enumerate() {
                let first = if a < 0 {
                    a_points[a.unsigned_abs() as usize].neg()
                } else {
                    a_points[a as usize]
                };
                let second = if b < 0 {
                    b_points[b.unsigned_abs() as usize].neg()
                } else {
                    b_points[b as usize]
                };
                let expected = if first.is_identity() {
                    second
                } else if second.is_identity() {
                    first
                } else {
                    first.add_mixed(second)
                };
                if seed_id == 0 {
                    assert_eq!((a, b), (0, 0));
                    assert!(expected.is_identity());
                } else {
                    assert!(same_point(expected, row[seed_id].into_affine()),
                            "window {window}, seed {seed_id}");
                }
                checked += 1;
            }
            if window + 1 < RADIX13_WINDOWS {
                base = affine_multiples(base, TAU_BUCKET_RADIX).pop().unwrap();
            }
        }
        assert_eq!(checked, expected_entries);
    }

    #[test]
    fn tau_bucket_all_window_points_match_independent_group_sums() {
        check_tau_orbit_window_points(&TAU_BUCKET_TABLES, 1_015_352);
    }

    #[test]
    fn tau_pair_all_window_points_match_independent_group_sums() {
        check_tau_orbit_window_points(&TAU_PAIR_TABLES, 1_219_101);
    }
}
