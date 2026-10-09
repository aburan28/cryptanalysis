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

pub(super) fn multiply_word_format(
    scalar: &BigInt,
    format: u8,
) -> (Jacobian, BigInt, BigInt, usize, usize) {
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
    let (start_a, start_b) = hexagonal_four_corner_choices(&residue).remove(0);
    let mut a = Signed192::from_bigint(&start_a);
    let mut b = Signed192::from_bigint(&start_b);
    let tables = selected(format);
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
    (result, start_a, start_b, nonidentity.saturating_sub(1), tables.retained_bytes)
}

#[cfg(test)]
mod tests {
    use super::*;

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
