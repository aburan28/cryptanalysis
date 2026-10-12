// Included in a disposable copy of unit_orbit_windows.rs by native_overlay.py.
// This keeps the shared native source untouched while T-546 owns it.

const RADIX569: usize = 569;
const RADIX569_WINDOWS: usize = 13;
const RADIX569_TOP_CAP: i64 = 270_666;
const RADIX569_MAX_ROW: usize = 600;

fn radix569_sector((a, b): (i32, i32)) -> bool {
    a < 0 && -a <= 3 * b && 3 * b < -2 * a
}

fn radix569_top_digits() -> (Vec<(i16, i16)>, Vec<u32>, Vec<i16>) {
    let mut digits = vec![(0i16, 0i16)];
    let mut prefix = vec![0u32; RADIX569_MAX_ROW + 1];
    let mut lows = vec![0i16; RADIX569_MAX_ROW + 1];
    for u in 1..=RADIX569_MAX_ROW {
        let mut last = None;
        let mut first = None;
        for b in ((u + 2) / 3)..=((2 * u - 1) / 3) {
            let pair = (-(u as i32), b as i32);
            if 3 * norm(pair) > RADIX569_TOP_CAP { continue; }
            assert!(radix569_sector(pair));
            if let Some(previous) = last { assert_eq!(b, previous + 1); }
            first.get_or_insert(b);
            last = Some(b);
            digits.push((pair.0 as i16, pair.1 as i16));
        }
        lows[u] = first.unwrap_or(0) as i16;
        prefix[u] = u32::try_from(digits.len() - 1).unwrap();
    }
    assert_eq!(digits.len(), 54_540);
    (digits, prefix, lows)
}

struct Radix569Tables {
    atlas: OrbitAtlas,
    windows: Vec<Box<[U256Affine]>>,
    prefix: Vec<u32>,
    lows: Vec<i16>,
    retained_bytes: usize,
}

impl Radix569Tables {
    fn new() -> Self {
        let atlas = OrbitAtlas::with_base(0, RADIX569);
        assert_eq!(atlas.digits.len(), 53_961);
        let (top_digits, prefix, lows) = radix569_top_digits();
        let mut windows = Vec::with_capacity(RADIX569_WINDOWS + 1);
        let mut base = Jacobian::generator();
        for _ in 0..RADIX569_WINDOWS {
            windows.push(build_u256_window_encoded(&atlas.digits, base, true));
            base = affine_multiples(base, RADIX569).pop().unwrap();
        }
        windows.push(build_u256_window_encoded(&top_digits, base, true));
        let entries = windows.iter().map(|row| row.len()).sum::<usize>();
        assert_eq!(entries, 756_033);
        let retained_bytes = entries * size_of::<U256Affine>()
            + atlas.codes.len() * size_of::<u32>()
            + atlas.digits.len() * size_of::<(i16, i16)>()
            + prefix.len() * size_of::<u32>()
            + lows.len() * size_of::<i16>()
            + size_of::<Self>()
            + windows.capacity() * size_of::<Box<[U256Affine]>>()
            + SOLINAS_UNIT_CONSTANT_BYTES
            + size_of::<[GaugeTreePlan; GAUGE_PLAN_COUNT]>();
        assert!(retained_bytes < RADIX13_CAP_BYTES);
        Self { atlas, windows, prefix, lows, retained_bytes }
    }

    fn top_choice(&self, a: Signed192, b: Signed192) -> (usize, usize) {
        if a.is_zero() && b.is_zero() { return (0, 0); }
        let pair = (a.to_bigint().to_i32().expect("bounded top a"),
                    b.to_bigint().to_i32().expect("bounded top b"));
        assert!(3 * norm(pair) <= RADIX569_TOP_CAP);
        let canonical = unit_images(pair).into_iter()
            .find(|&image| radix569_sector(image)).expect("top sector");
        let u = canonical.0.unsigned_abs() as usize;
        assert!((1..=RADIX569_MAX_ROW).contains(&u));
        let low = i32::from(self.lows[u]);
        let rank = 1 + self.prefix[u - 1] as usize
            + usize::try_from(canonical.1 - low).expect("top row lower bound");
        assert!(rank < self.windows[RADIX569_WINDOWS].len());
        let code = unit_images(canonical).into_iter()
            .position(|image| image == pair).expect("top unit image");
        (rank, code)
    }
}

static RADIX569_TABLES: LazyLock<Radix569Tables> = LazyLock::new(Radix569Tables::new);

pub(super) fn radix569_warm() -> usize {
    LazyLock::force(&PARETO_GAUGE_PLANS);
    LazyLock::force(&U256_BETA_CANONICAL);
    RADIX569_TABLES.retained_bytes
}

pub(super) fn radix569_audit() -> usize {
    let tables = &*RADIX569_TABLES;
    let (digits, prefix, lows) = radix569_top_digits();
    assert_eq!(tables.prefix, prefix);
    assert_eq!(tables.lows, lows);
    assert_eq!(tables.top_choice(Signed192::from_i32(0), Signed192::from_i32(0)),
               (0, 0));
    let mut checked = 1usize;
    for (rank, &(a, b)) in digits.iter().enumerate().skip(1) {
        let pair = (i32::from(a), i32::from(b));
        for (code, image) in unit_images(pair).into_iter().enumerate() {
            assert_eq!(tables.top_choice(Signed192::from_i32(image.0),
                                         Signed192::from_i32(image.1)), (rank, code));
            checked += 1;
        }
    }
    assert_eq!(checked, 327_235);
    checked
}

pub(super) fn radix569_atlas_bytes() -> Vec<u8> {
    let tables = &*RADIX569_TABLES;
    let (top_digits, _, _) = radix569_top_digits();
    let mut bytes = Vec::with_capacity((53_961 + 54_539) * 4);
    for &(a, b) in tables.atlas.digits.iter().chain(top_digits.iter().skip(1)) {
        bytes.extend_from_slice(&a.to_le_bytes());
        bytes.extend_from_slice(&b.to_le_bytes());
    }
    assert_eq!(bytes.len(), (53_961 + 54_539) * 4);
    bytes
}

pub(super) fn multiply_u256_radix569_gauge_tree_pareto(
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
    let tables = &*RADIX569_TABLES;
    let (mut a, mut b) = representative;
    let mut choices = [(0usize, 0usize); RADIX569_WINDOWS + 1];
    let mut nonidentity = 0usize;
    for choice in choices.iter_mut().take(RADIX569_WINDOWS) {
        let (qa, ra, resa) = a.div_rem_small_radix(RADIX569 as u64);
        let (qb, rb, resb) = b.div_rem_small_radix(RADIX569 as u64);
        let (digit, orbit_id, unit_code) = tables.atlas.digit_residue(resa, resb);
        a = qa.adjust_small_radix_quotient(ra, digit.0, RADIX569 as i32);
        b = qb.adjust_small_radix_quotient(rb, digit.1, RADIX569 as i32);
        *choice = (orbit_id, unit_code);
        nonidentity += usize::from(orbit_id != 0);
    }
    choices[RADIX569_WINDOWS] = tables.top_choice(a, b);
    nonidentity += usize::from(choices[RADIX569_WINDOWS].0 != 0);
    let (point, gauge_products, _) =
        evaluate_u256_gauge_tree_pareto(&choices, &tables.windows);
    (point, representative, nonidentity.saturating_sub(1),
     tables.retained_bytes, fallback, corner, gauge_products)
}
