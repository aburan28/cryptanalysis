// Included in a disposable copy of unit_orbit_windows.rs.

const SPLIT671_BASE: usize = 671;
const SPLIT671_WINDOWS: usize = 12;
const SPLIT671_CHUNK: i32 = 256;
const SPLIT671_CAP: i64 = 1_668_628_670;
const SPLIT671_HIGH_A: i32 = 184;
const SPLIT671_HIGH_B: i32 = 106;

fn split671_rectangle(a_lo: i32, a_hi: i32, b_lo: i32, b_hi: i32) -> Vec<(i16, i16)> {
    let mut digits = vec![(0i16, 0i16)];
    for a in a_lo..=a_hi {
        for b in b_lo..=b_hi {
            if a != 0 || b != 0 {
                digits.push((i16::try_from(a).unwrap(), i16::try_from(b).unwrap()));
            }
        }
    }
    digits
}

fn split671_rectangle_rank(a: i32, b: i32,
                           a_lo: i32, a_hi: i32, b_lo: i32, b_hi: i32) -> usize {
    assert!((a_lo..=a_hi).contains(&a) && (b_lo..=b_hi).contains(&b));
    if a == 0 && b == 0 { return 0; }
    let width = usize::try_from(b_hi - b_lo + 1).unwrap();
    let flat = usize::try_from(a - a_lo).unwrap() * width
        + usize::try_from(b - b_lo).unwrap();
    let zero = usize::try_from(-a_lo).unwrap() * width
        + usize::try_from(-b_lo).unwrap();
    if flat < zero { flat + 1 } else { flat }
}

struct Split671Tables {
    atlas: OrbitAtlas,
    windows: Vec<Box<[U256Affine]>>,
    retained_bytes: usize,
}

impl Split671Tables {
    fn new() -> Self {
        assert_eq!(size_of::<U256Affine>(), 64);
        let atlas = OrbitAtlas::with_base(0, SPLIT671_BASE);
        assert_eq!(atlas.digits.len(), 75_041);
        let low = split671_rectangle(-128, 127, -128, 127);
        let high = split671_rectangle(-SPLIT671_HIGH_A, SPLIT671_HIGH_A,
                                      -SPLIT671_HIGH_B, SPLIT671_HIGH_B);
        assert_eq!(low.len(), 65_536);
        assert_eq!(high.len(), 78_597);
        let mut windows = Vec::with_capacity(SPLIT671_WINDOWS + 2);
        let mut base = Jacobian::generator();
        for _ in 0..SPLIT671_WINDOWS {
            windows.push(build_u256_window_encoded(&atlas.digits, base, true));
            base = affine_multiples(base, SPLIT671_BASE).pop().unwrap();
        }
        windows.push(build_u256_window_encoded(&low, base, true));
        let high_base = affine_multiples(base, SPLIT671_CHUNK as usize).pop().unwrap();
        windows.push(build_u256_window_encoded(&high, high_base, true));
        let entries = windows.iter().map(|row| row.len()).sum::<usize>();
        assert_eq!(entries, 1_044_625);
        let retained_bytes = entries * size_of::<U256Affine>()
            + atlas.codes.len() * size_of::<u32>()
            + atlas.digits.len() * size_of::<(i16, i16)>()
            + size_of::<Self>()
            + windows.capacity() * size_of::<Box<[U256Affine]>>()
            + SOLINAS_UNIT_CONSTANT_BYTES
            + size_of::<[GaugeTreePlan; GAUGE_PLAN_COUNT]>();
        assert!(retained_bytes < RADIX13_CAP_BYTES);
        Self { atlas, windows, retained_bytes }
    }
}

static SPLIT671_TABLES: LazyLock<Split671Tables> = LazyLock::new(Split671Tables::new);

pub(super) fn split671_warm() -> usize {
    LazyLock::force(&PARETO_GAUGE_PLANS);
    LazyLock::force(&U256_BETA_CANONICAL);
    SPLIT671_TABLES.retained_bytes
}

pub(super) fn split671_audit() -> usize {
    let tables = &*SPLIT671_TABLES;
    let mut checked = 0usize;
    for ra in 0..SPLIT671_BASE {
        for rb in 0..SPLIT671_BASE {
            let (digit, _, _) = tables.atlas.digit_residue(ra, rb);
            assert_eq!((digit.0.rem_euclid(SPLIT671_BASE as i32) as usize,
                        digit.1.rem_euclid(SPLIT671_BASE as i32) as usize), (ra, rb));
            assert!(3 * norm(digit) <= (SPLIT671_BASE * SPLIT671_BASE) as i64);
            checked += 1;
        }
    }
    assert_eq!(checked, 450_241);
    for a in -128..=127 {
        for b in -128..=127 {
            let rank = split671_rectangle_rank(a, b, -128, 127, -128, 127);
            assert!(rank < tables.windows[SPLIT671_WINDOWS].len());
        }
    }
    for a in -SPLIT671_HIGH_A..=SPLIT671_HIGH_A {
        for b in -SPLIT671_HIGH_B..=SPLIT671_HIGH_B {
            let rank = split671_rectangle_rank(a, b, -SPLIT671_HIGH_A,
                                                SPLIT671_HIGH_A, -SPLIT671_HIGH_B,
                                                SPLIT671_HIGH_B);
            assert!(rank < tables.windows[SPLIT671_WINDOWS + 1].len());
        }
    }
    checked
}

pub(super) fn split671_atlas_bytes() -> Vec<u8> {
    let tables = &*SPLIT671_TABLES;
    let low = split671_rectangle(-128, 127, -128, 127);
    let high = split671_rectangle(-SPLIT671_HIGH_A, SPLIT671_HIGH_A,
                                   -SPLIT671_HIGH_B, SPLIT671_HIGH_B);
    let mut bytes = Vec::with_capacity((75_041 + 65_536 + 78_597) * 4);
    for &(a, b) in tables.atlas.digits.iter().chain(low.iter()).chain(high.iter()) {
        bytes.extend_from_slice(&a.to_le_bytes());
        bytes.extend_from_slice(&b.to_le_bytes());
    }
    bytes
}

pub(super) fn multiply_u256_split671(
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
    let tables = &*SPLIT671_TABLES;
    let (mut a, mut b) = representative;
    let mut choices = [(0usize, 0usize); SPLIT671_WINDOWS + 2];
    let mut nonidentity = 0usize;
    for choice in choices.iter_mut().take(SPLIT671_WINDOWS) {
        let (qa, ra, resa) = a.div_rem_small_radix(SPLIT671_BASE as u64);
        let (qb, rb, resb) = b.div_rem_small_radix(SPLIT671_BASE as u64);
        let (digit, orbit_id, unit_code) = tables.atlas.digit_residue(resa, resb);
        a = qa.adjust_small_radix_quotient(ra, digit.0, SPLIT671_BASE as i32);
        b = qb.adjust_small_radix_quotient(rb, digit.1, SPLIT671_BASE as i32);
        *choice = (orbit_id, unit_code);
        nonidentity += usize::from(orbit_id != 0);
    }
    let ta = a.to_bigint().to_i32().expect("bounded terminal a");
    let tb = b.to_bigint().to_i32().expect("bounded terminal b");
    assert!(3 * norm((ta, tb)) <= SPLIT671_CAP);
    let ha = (ta + 128).div_euclid(SPLIT671_CHUNK);
    let hb = (tb + 128).div_euclid(SPLIT671_CHUNK);
    let la = ta - SPLIT671_CHUNK * ha;
    let lb = tb - SPLIT671_CHUNK * hb;
    let low_rank = split671_rectangle_rank(la, lb, -128, 127, -128, 127);
    let high_rank = split671_rectangle_rank(ha, hb, -SPLIT671_HIGH_A,
                                            SPLIT671_HIGH_A, -SPLIT671_HIGH_B,
                                            SPLIT671_HIGH_B);
    choices[SPLIT671_WINDOWS] = (low_rank, 0);
    choices[SPLIT671_WINDOWS + 1] = (high_rank, 0);
    nonidentity += usize::from(low_rank != 0) + usize::from(high_rank != 0);
    let (point, gauge_products, _) =
        evaluate_u256_gauge_tree_pareto(&choices, &tables.windows);
    (point, representative, nonidentity.saturating_sub(1),
     tables.retained_bytes, fallback, corner, gauge_products)
}
