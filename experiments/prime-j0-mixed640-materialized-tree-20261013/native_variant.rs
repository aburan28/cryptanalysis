// Inserted into the pinned mixed-radix 640 module by native_overlay.py.
struct Mixed640PreTauTables {
    full9: FrontierAtlas,
    full640: Radix640Atlas,
    final640: Radix640Atlas,
    windows: Vec<Box<[U256TwoXOrbitTauPair]>>,
    retained_bytes: usize,
}

fn mixed640_materialize(point: U256Affine) -> U256TwoXAffine {
    U256TwoXAffine::from_affine(point)
}

impl Mixed640PreTauTables {
    fn new() -> Self {
        let full9 = FrontierAtlas::from_bytes(FRONTIER9_FULL_ATLAS, 9, 512, 21_847);
        let full640 = Radix640Atlas::from_bytes(RADIX640_FULL_ATLAS, 640, 34_135);
        let final640 = Radix640Atlas::from_bytes(RADIX640_FINAL_ATLAS, 391, 45_163);
        let mut windows = Vec::with_capacity(RADIX640_SCHEDULE.len());
        let mut base = Jacobian::generator();
        for (index, &radix) in RADIX640_SCHEDULE.iter().enumerate() {
            let seeds = if index < 6 { full9.seed_digits() }
                        else if index == 13 { final640.seed_digits() }
                        else { full640.seed_digits() };
            let plain = build_u256_window(&seeds, base);
            let tau = build_u256_window(&seeds, base.tau());
            assert_eq!(plain.len(), tau.len());
            windows.push(plain.iter().copied().zip(tau.iter().copied())
                .map(|(plain, tau)| U256TwoXOrbitTauPair {
                    plain: mixed640_materialize(plain),
                    tau: mixed640_materialize(tau),
                }).collect::<Vec<_>>().into_boxed_slice());
            if index + 1 < RADIX640_SCHEDULE.len() {
                if radix == 512 {
                    for _ in 0..9 { base = base.double(); }
                } else {
                    base = affine_multiples(base, radix).pop().unwrap();
                }
            }
        }
        let entries = windows.iter().map(|row| row.len()).sum::<usize>();
        assert_eq!(entries, 415_190);
        assert_eq!(size_of::<U256TwoXOrbitTauPair>(), 192);
        let retained_bytes = entries * size_of::<U256TwoXOrbitTauPair>()
            + FRONTIER9_FULL_ATLAS.len() + RADIX640_FULL_ATLAS.len()
            + RADIX640_FINAL_ATLAS.len() + size_of::<Self>()
            + windows.capacity() * size_of::<Box<[U256TwoXOrbitTauPair]>>();
        Self { full9, full640, final640, windows, retained_bytes }
    }
}

static MIXED640_PRETAU_TABLES: LazyLock<Mixed640PreTauTables> =
    LazyLock::new(Mixed640PreTauTables::new);

#[derive(Clone, Copy)]
enum Mixed640TreeNode {
    Affine(U256Affine),
    Projective(U256XYZZ),
}

fn mixed640_add_affine_pair(a: U256Affine, b: U256Affine) -> U256XYZZ {
    let p = u256_sub(b.x, a.x);
    let r = u256_sub(b.y, a.y);
    if bool::from(p.ct_is_zero()) {
        return if bool::from(r.ct_is_zero()) { U256XYZZ::from_affine(a).double() }
               else { U256XYZZ::identity() };
    }
    let pp = u256_square(p);
    let ppp = u256_mul(p, pp);
    let axpp = u256_mul(a.x, pp);
    let x = u256_sub(u256_sub(u256_square(r), ppp), u256_add(axpp, axpp));
    let y = u256_sub(u256_mul(r, u256_sub(axpp, x)), u256_mul(a.y, ppp));
    U256XYZZ { x, y, zz: pp, zzz: ppp }
}

fn mixed640_tree_join(a: Mixed640TreeNode, b: Mixed640TreeNode) -> Mixed640TreeNode {
    match (a, b) {
        (Mixed640TreeNode::Affine(a), Mixed640TreeNode::Affine(b)) =>
            Mixed640TreeNode::Projective(mixed640_add_affine_pair(a, b)),
        (Mixed640TreeNode::Projective(a), Mixed640TreeNode::Affine(b)) |
        (Mixed640TreeNode::Affine(b), Mixed640TreeNode::Projective(a)) =>
            Mixed640TreeNode::Projective(a.add_mixed(b)),
        (Mixed640TreeNode::Projective(a), Mixed640TreeNode::Projective(b)) =>
            Mixed640TreeNode::Projective(a.add_xyzz(b)),
    }
}

fn mixed640_single_tree(mut selected: Vec<Mixed640TreeNode>) -> U256XYZZ {
    if selected.is_empty() { return U256XYZZ::identity(); }
    while selected.len() > 1 {
        let mut next = Vec::with_capacity((selected.len() + 1) / 2);
        let mut chunks = selected.chunks_exact(2);
        for pair in &mut chunks { next.push(mixed640_tree_join(pair[0], pair[1])); }
        if let Some(&last) = chunks.remainder().first() { next.push(last); }
        selected = next;
    }
    match selected[0] {
        Mixed640TreeNode::Affine(p) => U256XYZZ::from_affine(p),
        Mixed640TreeNode::Projective(p) => p,
    }
}

pub(super) fn multiply_u256_tau_mixed640_pretau_tree(
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
    let tables = &*MIXED640_PRETAU_TABLES;
    let (mut a, mut b) = representative;
    let mut selected = Vec::with_capacity(RADIX640_SCHEDULE.len());
    for index in 0..RADIX640_SCHEDULE.len() {
        let (_, seed_id, exponent, unit_code) = if index < 6 {
            let ra = a.rem_euclid_power_of_two(9);
            let rb = b.rem_euclid_power_of_two(9);
            let choice = tables.full9.digit_residue(ra, rb);
            a = a.sub(Signed192::from_i32(choice.0.0)).div_exact_power_of_two(9);
            b = b.sub(Signed192::from_i32(choice.0.1)).div_exact_power_of_two(9);
            choice
        } else {
            let (qa, signed_ra, ra) = a.div_rem_radix640_fast();
            let (qb, signed_rb, rb) = b.div_rem_radix640_fast();
            let atlas = if index == 13 { &tables.final640 } else { &tables.full640 };
            let choice = atlas.digit_residue(ra, rb);
            a = qa.adjust_small_radix_quotient(signed_ra, choice.0.0, 640);
            b = qb.adjust_small_radix_quotient(signed_rb, choice.0.1, 640);
            choice
        };
        if seed_id != 0 {
            selected.push(Mixed640TreeNode::Affine(
                tables.windows[index][seed_id].select(exponent, unit_code)));
        }
    }
    assert!(a.is_zero() && b.is_zero(), "mixed-radix 640 recoding did not terminate");
    let additions = selected.len().saturating_sub(1);
    let point = mixed640_single_tree(selected).affine_hex_binary_inverse();
    (point, representative, additions, tables.retained_bytes,
     fallback, corner, 0)
}

#[cfg(test)]
mod mixed640_pretau_tests {
    use super::*;

    fn independent_binary_point(scalar: &BigInt) -> Jacobian {
        let (_, bytes) = scalar.to_bytes_be();
        let generator = Jacobian::generator().into_affine();
        let mut point = Jacobian::identity();
        for byte in bytes {
            for bit in (0..8).rev() {
                point = point.double();
                if (byte >> bit) & 1 != 0 { point = point.add_mixed(generator); }
            }
        }
        point
    }

    #[test]
    fn fresh_64_matches_independent_binary() {
        let panel: serde_json::Value = serde_json::from_str(include_str!(
            "__MIXED640_PANEL__"
        )).unwrap();
        let scalars = panel["scalars_hex"].as_array().unwrap();
        for (index, text) in scalars.iter().take(64).enumerate() {
            let scalar = BigInt::parse_bytes(text.as_str().unwrap().as_bytes(), 16).unwrap();
            let words = super::super::scalar_words_256(&scalar).unwrap();
            let candidate = multiply_u256_tau_mixed640_pretau_tree(words);
            let reference = multiply_u256_tau_mixed_radix640_gauge_xyzz_tau(words);
            assert_eq!(candidate.0, reference.0, "point {index}");
            assert_eq!(candidate.1, reference.1, "representative {index}");
            let reduced = &scalar % &SCALAR_LATTICE.n;
            assert_eq!(candidate.0, independent_binary_point(&reduced).affine_hex(),
                       "independent binary {index}");
        }
    }

    #[test]
    fn source_frozen_holdout_matches_independent_binary() {
        let path = std::env::var("MIXED640_HOLDOUT").expect("MIXED640_HOLDOUT is required");
        let raw = std::fs::read_to_string(path).unwrap();
        let panel: serde_json::Value = serde_json::from_str(&raw).unwrap();
        let cases = panel["cases"].as_array().unwrap();
        assert_eq!(cases.len(), 128);
        for (index, case) in cases.iter().enumerate() {
            let text = case["scalar_hex"].as_str().unwrap();
            let scalar = BigInt::parse_bytes(text.as_bytes(), 16).unwrap();
            let words = super::super::scalar_words_256(&scalar).unwrap();
            let candidate = multiply_u256_tau_mixed640_pretau_tree(words);
            assert_eq!(candidate.0, case["point_hex"].as_str().unwrap(),
                       "frozen affine point {index}");
            let reduced = &scalar % &SCALAR_LATTICE.n;
            assert_eq!(candidate.0, independent_binary_point(&reduced).affine_hex(),
                       "independent native binary {index}");
        }
        println!("mixed640_pretau_holdout_cases={} status=verified", cases.len());
    }
}
