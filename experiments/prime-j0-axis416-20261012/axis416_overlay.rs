// Included in a disposable copy of unit_orbit_windows.rs by native_overlay.py.

const AXIS416: usize = 416;
const AXIS416_WINDOWS: usize = 13;
const AXIS416_TOP_CAP: i64 = 927_429_454;
const AXIS416_U_MAX: usize = 35_164;
const AXIS416_B_MAX: usize = 23_442;

fn axis416_sector((a, b): (i32, i32)) -> bool {
    a < 0 && -a <= 3 * b && 3 * b < -2 * a
}

fn axis416_encode(point: Jacobian) -> U256Affine {
    let point = point.into_affine();
    let x = super::hybrid_pair_mont(point.x);
    let y = super::hybrid_pair_mont(point.y);
    U256Affine { x, y }
}

struct Axis416Tables {
    atlas: OrbitAtlas,
    ordinary: Vec<Box<[U256Affine]>>,
    axis_a: Box<[U256Affine]>,
    axis_b: Box<[U256Affine]>,
    retained_bytes: usize,
}

impl Axis416Tables {
    fn new() -> Self {
        assert_eq!(size_of::<U256Affine>(), 64);
        let atlas = OrbitAtlas::with_base(0, AXIS416);
        assert_eq!(atlas.digits.len(), 28_844);
        let mut ordinary = Vec::with_capacity(AXIS416_WINDOWS);
        let mut base = Jacobian::generator();
        for _ in 0..AXIS416_WINDOWS {
            ordinary.push(build_u256_window_encoded(&atlas.digits, base, false));
            base = affine_multiples(base, AXIS416).pop().unwrap();
        }
        let axis_a = affine_multiples(base, AXIS416_U_MAX).into_iter().skip(1)
            .map(|point| axis416_encode(point.neg())).collect::<Vec<_>>().into_boxed_slice();
        let axis_b = affine_multiples(base.tau(), AXIS416_B_MAX).into_iter().skip(1)
            .map(axis416_encode).collect::<Vec<_>>().into_boxed_slice();
        assert_eq!(axis_a.len(), AXIS416_U_MAX);
        assert_eq!(axis_b.len(), AXIS416_B_MAX);
        let entries = ordinary.iter().map(|row| row.len()).sum::<usize>()
            + axis_a.len() + axis_b.len();
        assert_eq!(entries, 433_578);
        let retained_bytes = entries * size_of::<U256Affine>()
            + atlas.codes.len() * size_of::<u32>()
            + atlas.digits.len() * size_of::<(i16, i16)>()
            + size_of::<Self>()
            + ordinary.capacity() * size_of::<Box<[U256Affine]>>()
            + SOLINAS_UNIT_CONSTANT_BYTES;
        Self { atlas, ordinary, axis_a, axis_b, retained_bytes }
    }

    fn top_choice(&self, a: Signed192, b: Signed192) -> Option<(usize, usize, usize)> {
        if a.is_zero() && b.is_zero() { return None; }
        let pair = (a.to_bigint().to_i32().expect("bounded top a"),
                    b.to_bigint().to_i32().expect("bounded top b"));
        assert!(3 * norm(pair) <= AXIS416_TOP_CAP);
        let canonical = unit_images(pair).into_iter()
            .find(|&image| axis416_sector(image)).expect("top sector");
        let u = canonical.0.unsigned_abs() as usize;
        let v = canonical.1 as usize;
        assert!((1..=AXIS416_U_MAX).contains(&u));
        assert!((1..=AXIS416_B_MAX).contains(&v));
        let code = unit_images(canonical).into_iter()
            .position(|image| image == pair).expect("inverse unit image");
        Some((u, v, code))
    }
}

static AXIS416_TABLES: LazyLock<Axis416Tables> = LazyLock::new(Axis416Tables::new);

pub(super) fn axis416_warm() -> usize {
    LazyLock::force(&U256_BETA_CANONICAL);
    AXIS416_TABLES.retained_bytes
}

pub(super) fn axis416_audit() -> usize {
    let tables = &*AXIS416_TABLES;
    for index in 0..AXIS416 * AXIS416 {
        let a = index / AXIS416;
        let b = index % AXIS416;
        let (digit, _, _) = tables.atlas.digit_residue(a, b);
        assert_eq!((digit.0.rem_euclid(AXIS416 as i32) as usize,
                    digit.1.rem_euclid(AXIS416 as i32) as usize), (a, b));
        assert!(3 * norm(digit) <= (AXIS416 * AXIS416) as i64);
    }
    assert!(tables.top_choice(Signed192::from_i32(0), Signed192::from_i32(0)).is_none());
    AXIS416 * AXIS416
}

pub(super) fn axis416_atlas_bytes() -> Vec<u8> {
    let tables = &*AXIS416_TABLES;
    let mut bytes = Vec::with_capacity(tables.atlas.digits.len() * 4);
    for &(a, b) in tables.atlas.digits.iter() {
        bytes.extend_from_slice(&a.to_le_bytes());
        bytes.extend_from_slice(&b.to_le_bytes());
    }
    bytes
}

fn axis416_evaluate(selected: &[(U256Affine, usize)]) -> (String, usize) {
    let mut result = U256Jacobian::identity();
    let mut gauge = None;
    let mut rotations = 0usize;
    for power in [1usize, 2, 0] {
        if !selected.iter().any(|&(_, code)| code / 2 == power) { continue; }
        if let Some(previous) = gauge {
            let delta = (previous + 3 - power) % 3;
            if delta != 0 && !result.is_identity() {
                result = result.rotate_power(delta);
                rotations += 1;
            }
        }
        gauge = Some(power);
        for &(point, code) in selected {
            if code / 2 == power {
                result = result.add_mixed(point.unit(code & 1));
            }
        }
    }
    if let Some(power) = gauge {
        if power != 0 && !result.is_identity() {
            result = result.rotate_power(power);
            rotations += 1;
        }
    }
    assert!(rotations <= 2);
    (result.affine_hex_binary_inverse(), rotations)
}

pub(super) fn multiply_u256_axis416(
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
    let tables = &*AXIS416_TABLES;
    let (mut a, mut b) = representative;
    let mut selected = Vec::with_capacity(AXIS416_WINDOWS + 2);
    for index in 0..AXIS416_WINDOWS {
        let (qa, ra, resa) = a.div_rem_small_radix(AXIS416 as u64);
        let (qb, rb, resb) = b.div_rem_small_radix(AXIS416 as u64);
        let (digit, orbit_id, unit_code) = tables.atlas.digit_residue(resa, resb);
        a = qa.adjust_small_radix_quotient(ra, digit.0, AXIS416 as i32);
        b = qb.adjust_small_radix_quotient(rb, digit.1, AXIS416 as i32);
        if orbit_id != 0 {
            selected.push((tables.ordinary[index][orbit_id], unit_code));
        }
    }
    if let Some((u, v, code)) = tables.top_choice(a, b) {
        selected.push((tables.axis_a[u - 1], code));
        selected.push((tables.axis_b[v - 1], code));
    }
    let (point, rotations) = axis416_evaluate(&selected);
    (point, representative, selected.len().saturating_sub(1),
     tables.retained_bytes, fallback, corner, rotations)
}
