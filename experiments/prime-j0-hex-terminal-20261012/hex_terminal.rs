// Included in a disposable copy of unit_orbit_windows.rs by native_overlay.py.

const HEX_TERMINAL: usize = 256;
const HEX_TERMINAL_WINDOWS: usize = 15;
const HEX_TERMINAL_TOP_CAP: i64 = 66_051;
const HEX_TERMINAL_U_MAX: usize = 296;
const HEX_TERMINAL_B_MAX: usize = 197;
const HEX_TERMINAL_LIMIT_DECIMAL: &[u8] = b"87506751043387112747509266240600930742795";

fn hex_terminal_domain(
    pair: (i32, i32), neighbors: &[(BigInt, BigInt); 3], limit: &BigInt,
) -> bool {
    use num_traits::Signed;
    if 3 * norm(pair) > HEX_TERMINAL_TOP_CAP { return false; }
    let a = BigInt::from(pair.0);
    let b = BigInt::from(pair.1);
    neighbors.iter().all(|(x, y)| {
        let inner: BigInt = &a * (2i32 * x + 3i32 * y)
            + &b * (3i32 * x + 6i32 * y);
        inner.abs() <= *limit
    })
}

fn hex_terminal_sector((a, b): (i32, i32)) -> bool {
    a < 0 && -a <= 3 * b && 3 * b < -2 * a
}

fn hex_terminal_encode(point: Jacobian) -> U256Affine {
    let point = point.into_affine();
    let x = super::hybrid_pair_mont(point.x);
    let y = super::hybrid_pair_mont(point.y);
    let ctx = &super::HYBRID_FIELD.0;
    U256Affine { x: ctx.from_montgomery(&x),
                 y: ctx.from_montgomery(&y) }
}

struct HexTerminalTables {
    atlas: OrbitAtlas,
    ordinary: Vec<Box<[U256Affine]>>,
    top: Box<[U256Affine]>,
    top_rows: Vec<(usize, usize, usize)>,
    retained_bytes: usize,
}

impl HexTerminalTables {
    fn new() -> Self {
        assert_eq!(size_of::<U256Affine>(), 64);
        let atlas = OrbitAtlas::with_base(0, HEX_TERMINAL);
        assert_eq!(atlas.digits.len(), 10_924);
        let mut ordinary = Vec::with_capacity(HEX_TERMINAL_WINDOWS);
        let mut base = Jacobian::generator();
        for _ in 0..HEX_TERMINAL_WINDOWS {
            ordinary.push(build_u256_window_encoded(&atlas.digits, base, true));
            base = affine_multiples(base, HEX_TERMINAL).pop().unwrap();
        }
        let a_multiples = affine_multiples(base, HEX_TERMINAL_U_MAX);
        let b_multiples = affine_multiples(base.tau(), HEX_TERMINAL_B_MAX);
        let parse = |decimal: &[u8]| BigInt::parse_bytes(decimal, 10).expect("decimal integer");
        let neighbors = [
            (parse(b"671331852483699643819086596696745227419"),
             parse(b"-367917413016453100223835821029139468248")),
            (parse(b"-238911465918039986966665730306072050094"),
             parse(b"303414439467246543595250775667605759171")),
            (parse(b"432420386565659656852420866390673177325"),
             parse(b"-64502973549206556628585045361533709077")),
        ];
        let limit = parse(HEX_TERMINAL_LIMIT_DECIMAL);
        let mut top_projective = Vec::with_capacity(11_022);
        let mut top_rows = Vec::with_capacity(HEX_TERMINAL_U_MAX + 1);
        top_rows.push((0, 0, 0));
        for u in 1..=HEX_TERMINAL_U_MAX {
            let mut first = 0usize;
            let mut stop = 0usize;
            let offset = top_projective.len() + 1;
            for v in (u + 2) / 3..=(2 * u - 1) / 3 {
                if !hex_terminal_domain((-(u as i32), v as i32), &neighbors, &limit) {
                    continue;
                }
                if first == 0 { first = v; }
                assert!(stop == 0 || stop == v);
                stop = v + 1;
                let point = a_multiples[u].neg().add_mixed(b_multiples[v]);
                assert!(!point.is_identity());
                top_projective.push(point);
            }
            top_rows.push((first, stop, offset));
        }
        assert_eq!(top_projective.len(), 11_022);
        let mut top_points = Vec::with_capacity(11_023);
        top_points.push(U256Affine { x: super::U256::ZERO, y: super::U256::ZERO });
        top_points.extend(batch_to_affine(&top_projective).into_iter().map(hex_terminal_encode));
        let top = top_points.into_boxed_slice();
        let entries = ordinary.iter().map(|row| row.len()).sum::<usize>()
            + top.len();
        assert_eq!(entries, 174_883);
        let retained_bytes = entries * size_of::<U256Affine>()
            + atlas.codes.len() * size_of::<u32>()
            + atlas.digits.len() * size_of::<(i16, i16)>()
            + size_of::<Self>()
            + ordinary.capacity() * size_of::<Box<[U256Affine]>>()
            + top_rows.capacity() * size_of::<(usize, usize, usize)>()
            + SOLINAS_UNIT_CONSTANT_BYTES;
        Self { atlas, ordinary, top, top_rows, retained_bytes }
    }

    fn top_choice(&self, a: Signed192, b: Signed192) -> Option<(usize, usize)> {
        if a.is_zero() && b.is_zero() { return None; }
        let pair = (a.to_bigint().to_i32().expect("bounded top a"),
                    b.to_bigint().to_i32().expect("bounded top b"));
        assert!(3 * norm(pair) <= HEX_TERMINAL_TOP_CAP);
        let canonical = unit_images(pair).into_iter()
            .find(|&image| hex_terminal_sector(image)).expect("top sector");
        let u = canonical.0.unsigned_abs() as usize;
        let v = canonical.1 as usize;
        assert!((1..=HEX_TERMINAL_U_MAX).contains(&u));
        assert!((1..=HEX_TERMINAL_B_MAX).contains(&v));
        let code = unit_images(canonical).into_iter()
            .position(|image| image == pair).expect("inverse unit image");
        let (first, stop, offset) = self.top_rows[u];
        assert!(first <= v && v < stop);
        Some((offset + v - first, code))
    }
}

static HEX_TERMINAL_TABLES: LazyLock<HexTerminalTables> = LazyLock::new(HexTerminalTables::new);

pub(super) fn hex_terminal_warm() -> usize {
    LazyLock::force(&U256_BETA_CANONICAL);
    HEX_TERMINAL_TABLES.retained_bytes
}

pub(super) fn hex_terminal_audit() -> usize {
    let tables = &*HEX_TERMINAL_TABLES;
    for index in 0..HEX_TERMINAL * HEX_TERMINAL {
        let a = index / HEX_TERMINAL;
        let b = index % HEX_TERMINAL;
        let (digit, _, _) = tables.atlas.digit_residue(a, b);
        assert_eq!((digit.0.rem_euclid(HEX_TERMINAL as i32) as usize,
                    digit.1.rem_euclid(HEX_TERMINAL as i32) as usize), (a, b));
        assert!(3 * norm(digit) <= (HEX_TERMINAL * HEX_TERMINAL) as i64);
    }
    assert!(tables.top_choice(Signed192::from_i32(0), Signed192::from_i32(0)).is_none());
    HEX_TERMINAL * HEX_TERMINAL
}

pub(super) fn hex_terminal_atlas_bytes() -> Vec<u8> {
    let tables = &*HEX_TERMINAL_TABLES;
    let mut bytes = Vec::with_capacity(tables.atlas.digits.len() * 4);
    for &(a, b) in tables.atlas.digits.iter() {
        bytes.extend_from_slice(&a.to_le_bytes());
        bytes.extend_from_slice(&b.to_le_bytes());
    }
    bytes
}

fn hex_terminal_evaluate(selected: &[(U256Affine, usize)]) -> (String, usize) {
    let mut result = U256XYZZCanonical::<true>::identity();
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
                result = result.add_mixed(point.unit_solinas(code & 1));
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

pub(super) fn multiply_u256_hex_terminal(
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
    let tables = &*HEX_TERMINAL_TABLES;
    let (mut a, mut b) = representative;
    let mut selected = Vec::with_capacity(HEX_TERMINAL_WINDOWS + 1);
    for index in 0..HEX_TERMINAL_WINDOWS {
        let (qa, ra, resa) = a.div_rem_small_radix(HEX_TERMINAL as u64);
        let (qb, rb, resb) = b.div_rem_small_radix(HEX_TERMINAL as u64);
        let (digit, orbit_id, unit_code) = tables.atlas.digit_residue(resa, resb);
        a = qa.adjust_small_radix_quotient(ra, digit.0, HEX_TERMINAL as i32);
        b = qb.adjust_small_radix_quotient(rb, digit.1, HEX_TERMINAL as i32);
        if orbit_id != 0 {
            selected.push((tables.ordinary[index][orbit_id], unit_code));
        }
    }
    if let Some((top_id, code)) = tables.top_choice(a, b) {
        selected.push((tables.top[top_id], code));
    }
    let (point, rotations) = hex_terminal_evaluate(&selected);
    (point, representative, selected.len().saturating_sub(1),
     tables.retained_bytes, fallback, corner, rotations)
}
