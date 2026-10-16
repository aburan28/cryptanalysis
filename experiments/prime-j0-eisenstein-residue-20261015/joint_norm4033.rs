// Included inside unit_orbit_windows. Both public scalar streams use the
// norm-4033 selector and one projective Horner chain. The Q table is built
// once for the fixed rho target and contains the same canonical digit order
// as ALT_HORNER_TABLES for G.

pub(super) struct JointQTables {
    digit_window: Box<[U256TwoXAffine]>,
    terminal_pairs: Box<[U256Affine]>,
    pub(super) retained_bytes: usize,
}

fn joint_parse_point(q_hex: &str) -> U256Jacobian {
    let (xh, yh) = q_hex.split_once(':').expect("Q x:y");
    let x = num_bigint::BigUint::parse_bytes(xh.as_bytes(), 16).expect("Q x hex");
    let y = num_bigint::BigUint::parse_bytes(yh.as_bytes(), 16).expect("Q y hex");
    let ctx = &super::HYBRID_FIELD.0;
    assert!(x < ctx.n.to_biguint() && y < ctx.n.to_biguint());
    let x = ctx.to_montgomery(&super::U256::from_biguint(&x));
    let y = ctx.to_montgomery(&super::U256::from_biguint(&y));
    let seven = ctx.to_montgomery(&super::U256::from_biguint(&num_bigint::BigUint::from(7u8)));
    assert_eq!(u256_square(y).0, u256_add(u256_mul(u256_square(x), x), seven).0,
               "Q lies on secp256k1");
    U256Jacobian::from_affine(U256Affine { x, y })
}

fn joint_into_affine(point: U256Jacobian) -> U256Affine {
    assert!(!point.is_identity());
    let ctx = &super::HYBRID_FIELD.0;
    let inverse = super::hybrid_binary_invert(point.z, ctx);
    let square = ctx.mont_sqr(&inverse);
    let cube = ctx.mont_mul(&square, &inverse);
    U256Affine { x: ctx.mont_mul(&point.x, &square),
                 y: ctx.mont_mul(&point.y, &cube) }
}

fn joint_seed_point(seed: (i16, i16),
                    a_powers: &[U256Jacobian; 8],
                    b_powers: &[U256Jacobian; 8]) -> U256Jacobian {
    let mut result = U256Jacobian::identity();
    for (value, powers) in [(seed.0, a_powers), (seed.1, b_powers)] {
        let magnitude = value.unsigned_abs() as usize;
        assert!(magnitude < 256);
        for bit in 0..8 {
            if magnitude & (1usize << bit) != 0 {
                let mut term = powers[bit];
                if value < 0 { term.y = u256_sub(super::U256::ZERO, term.y); }
                result = result.add_projective(term);
            }
        }
    }
    result
}

pub(super) fn prepare_joint_q(q_hex: &str) -> JointQTables {
    let q = joint_parse_point(q_hex);
    let tau_q = q.tau();
    let mut a_powers = [U256Jacobian::identity(); 8];
    let mut b_powers = [U256Jacobian::identity(); 8];
    a_powers[0] = q;
    b_powers[0] = tau_q;
    for bit in 1..8 {
        a_powers[bit] = a_powers[bit-1].double();
        b_powers[bit] = b_powers[bit-1].double();
    }
    let g_tables = &*ALT_HORNER_TABLES;
    let mut digit_seeds = g_tables.digit_pairs.iter().copied()
        .map(alt_orbit_canonical)
        .collect::<std::collections::BTreeSet<_>>()
        .into_iter().collect::<Vec<_>>();
    digit_seeds.retain(|&pair| pair != (0,0));
    digit_seeds.insert(0, (0,0));
    assert_eq!(digit_seeds.len(), g_tables.digit_window.len());
    let digit_window = digit_seeds.iter().copied().map(|seed| {
        if seed == (0,0) {
            U256TwoXAffine::from_affine(U256Affine {
                x: super::U256::ZERO, y: super::U256::ZERO })
        } else {
            U256TwoXAffine::from_affine(joint_into_affine(
                joint_seed_point(seed, &a_powers, &b_powers)))
        }
    }).collect::<Vec<_>>().into_boxed_slice();
    let mut terminal_seeds = (-100..=100i32).flat_map(|a| {
        (-100..=100i32).filter_map(move |b| {
            let norm = a*a+3*a*b+3*b*b;
            (norm < 5000).then_some((a as i16,b as i16))
        })
    }).map(alt_orbit_canonical)
      .collect::<std::collections::BTreeSet<_>>()
      .into_iter().collect::<Vec<_>>();
    terminal_seeds.retain(|&pair| pair != (0,0));
    terminal_seeds.insert(0, (0,0));
    assert_eq!(terminal_seeds.len(), g_tables.terminal_pairs.len());
    let terminal_pairs = terminal_seeds.iter().copied().map(|seed| {
        if seed == (0,0) {
            U256Affine { x: super::U256::ZERO, y: super::U256::ZERO }
        } else {
            joint_into_affine(joint_seed_point(seed, &a_powers, &b_powers))
        }
    }).collect::<Vec<_>>().into_boxed_slice();
    let retained_bytes = digit_window.len()*size_of::<U256TwoXAffine>()
        + terminal_pairs.len()*size_of::<U256Affine>()
        + size_of::<JointQTables>();
    JointQTables { digit_window, terminal_pairs, retained_bytes }
}

fn joint_choices(words: [u64; 4], tables: &AltHornerTables)
    -> [(usize,usize); ALT_SPLIT_PRIME_STEPS+1] {
    let scalar = super::Uint(words);
    let residue = if bool::from(scalar.ct_lt(&super::SCALAR_ORDER_WORDS)) {
        scalar
    } else {
        super::U256::sbb(&scalar, &super::SCALAR_ORDER_WORDS).0
    };
    let (representative, _, _) =
        super::hexagonal_certified_fixed_choice_words(residue.0);
    let (mut a, mut b) = representative;
    let mut choices = [(0usize,0usize); ALT_SPLIT_PRIME_STEPS+1];
    for window in 0..ALT_SPLIT_PRIME_STEPS {
        let (next_a,next_b,index,sign) =
            alt_split_prime_unit_step(a,b,&tables.digit_pairs);
        a = next_a;
        b = next_b;
        if index != 0 {
            let (seed,code) = tables.digit_codes[index];
            choices[window] = (usize::from(seed),usize::from(code)^sign);
        }
    }
    let (ai,aneg) = a.alt_split_prime_table_index(ALT_SPLIT_PRIME_TERMINAL_LIMIT);
    let (bi,bneg) = b.alt_split_prime_table_index(ALT_SPLIT_PRIME_TERMINAL_LIMIT);
    let signed_a = if aneg { -(ai as i32) } else { ai as i32 };
    let signed_b = if bneg { -(bi as i32) } else { bi as i32 };
    let terminal_norm = signed_a*signed_a+3*signed_a*signed_b+3*signed_b*signed_b;
    assert!(terminal_norm < 5000);
    if signed_a != 0 || signed_b != 0 {
        let index = ((signed_a+100)*201+signed_b+100) as usize;
        let (seed,code) = tables.terminal_codes[index];
        assert_ne!(seed,u16::MAX);
        choices[ALT_SPLIT_PRIME_STEPS] = (usize::from(seed),usize::from(code));
    }
    choices
}

pub(super) fn multiply_u256_tau_joint(a_words: [u64; 4], b_words: [u64; 4],
                                      q_tables: &JointQTables) -> String {
    let g_tables = &*ALT_HORNER_TABLES;
    let a = joint_choices(a_words, g_tables);
    let b = joint_choices(b_words, g_tables);
    let (ga, gu) = a[ALT_SPLIT_PRIME_STEPS];
    let (qb, qu) = b[ALT_SPLIT_PRIME_STEPS];
    let mut point = if ga == 0 { U256Jacobian::identity() } else {
        U256Jacobian::from_affine(g_tables.terminal_pairs[ga].unit(gu))
    };
    if qb != 0 { point = point.add_mixed(q_tables.terminal_pairs[qb].unit(qu)); }
    for index in (0..ALT_SPLIT_PRIME_STEPS).rev() {
        point = alt_horner_mul_pi(point);
        let (ga,gu) = a[index];
        let (qb,qu) = b[index];
        if ga != 0 { point = point.add_mixed(g_tables.digit_window[ga].unit(gu)); }
        if qb != 0 { point = point.add_mixed(q_tables.digit_window[qb].unit(qu)); }
    }
    point.affine_hex_binary_inverse()
}
