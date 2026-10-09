//! Mixed-radix fixed-base tables quotiented by the six Eisenstein units.

use super::{
    batch_to_affine, hexagonal_four_corner_choices, BigInt, CompactPairPoint, Jacobian,
    SCALAR_LATTICE,
};
use num_traits::{ToPrimitive, Zero};
use std::mem::size_of;
use std::sync::LazyLock;

const WIDTHS: [u8; 14] = [10, 10, 10, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9];
const CAP_BYTES: usize = 90 * (1 << 20);

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
    codes: Box<[u32]>,
    digits: Box<[(i16, i16)]>,
}

impl OrbitAtlas {
    fn new(width: u8) -> Self {
        let base = 1usize << width;
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
            codes: codes.into_boxed_slice(),
            digits: digits.into_boxed_slice(),
        }
    }

    fn base(&self) -> usize {
        1usize << self.width
    }

    fn digit(&self, a: &BigInt, b: &BigInt) -> ((i32, i32), usize, usize) {
        let base = BigInt::from(self.base());
        let ra = ((a % &base + &base) % &base).to_usize().unwrap();
        let rb = ((b % &base + &base) % &base).to_usize().unwrap();
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

fn build_window(atlas: &OrbitAtlas, base: Jacobian) -> Box<[CompactPairPoint]> {
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
    let a_multiples = affine_multiples(base, max_a);
    let b_multiples = affine_multiples(tau_base, max_b);
    let mut projective = Vec::with_capacity(atlas.digits.len() - 1);
    for &(a, b) in atlas.digits.iter().skip(1) {
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
    let mut packed = Vec::with_capacity(atlas.digits.len());
    packed.push(identity_slot);
    packed.extend(affine.into_iter().map(CompactPairPoint::from_affine));
    packed.into_boxed_slice()
}

struct Tables {
    large: OrbitAtlas,
    small: OrbitAtlas,
    windows: Vec<Box<[CompactPairPoint]>>,
    retained_bytes: usize,
}

impl Tables {
    fn new() -> Self {
        assert_eq!(size_of::<CompactPairPoint>(), 72);
        let large = OrbitAtlas::new(10);
        let small = OrbitAtlas::new(9);
        let mut windows = Vec::with_capacity(WIDTHS.len());
        let mut base = Jacobian::generator();
        for width in WIDTHS {
            windows.push(build_window(
                if width == 10 { &large } else { &small },
                base,
            ));
            for _ in 0..width {
                base = base.double();
            }
        }
        let entries: usize = windows.iter().map(|row| row.len()).sum();
        assert_eq!(entries, 1_004_904);
        let retained_bytes = entries * size_of::<CompactPairPoint>()
            + (large.codes.len() + small.codes.len()) * size_of::<u32>()
            + (large.digits.len() + small.digits.len()) * size_of::<(i16, i16)>()
            + size_of::<Self>()
            + windows.capacity() * size_of::<Box<[CompactPairPoint]>>();
        assert!(retained_bytes < CAP_BYTES);
        Self {
            large,
            small,
            windows,
            retained_bytes,
        }
    }

    fn atlas(&self, width: u8) -> &OrbitAtlas {
        if width == 10 {
            &self.large
        } else {
            &self.small
        }
    }
}

static TABLES: LazyLock<Tables> = LazyLock::new(Tables::new);

pub(super) fn warm() -> usize {
    TABLES.retained_bytes
}

pub(super) fn multiply(scalar: &BigInt) -> (Jacobian, BigInt, BigInt, usize, usize) {
    let lattice = &*SCALAR_LATTICE;
    let residue = ((scalar % &lattice.n) + &lattice.n) % &lattice.n;
    let (mut a, mut b) = hexagonal_four_corner_choices(&residue).remove(0);
    let (start_a, start_b) = (a.clone(), b.clone());
    let tables = &*TABLES;
    let mut result = Jacobian::identity();
    let mut nonidentity: usize = 0;
    for (index, width) in WIDTHS.into_iter().enumerate() {
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

#[cfg(test)]
mod tests {
    use super::*;

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
        for width in [9, 10] {
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
    fn fourteen_windows_reconstruct_boundaries() {
        let large = OrbitAtlas::new(10);
        let small = OrbitAtlas::new(9);
        let n = &SCALAR_LATTICE.n;
        for scalar in [BigInt::ZERO, BigInt::from(1), BigInt::from(2), n - 2, n - 1] {
            let (mut a, mut b) = hexagonal_four_corner_choices(&scalar).remove(0);
            let start = (a.clone(), b.clone());
            let mut factor = BigInt::from(1);
            let mut rebuilt = (BigInt::ZERO, BigInt::ZERO);
            for width in WIDTHS {
                let atlas = if width == 10 { &large } else { &small };
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

    #[test]
    fn all_window_points_match_independent_group_sums() {
        let tables = &*TABLES;
        let mut base = Jacobian::generator();
        let mut checked = 0;
        for (window, width) in WIDTHS.into_iter().enumerate() {
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
        assert_eq!(checked, 1_004_904);
    }
}
