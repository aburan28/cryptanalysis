// Included inside unit_orbit_windows. Both public scalar streams use the
// norm-4033 selector and one projective Horner chain. The Q table is built
// once for the fixed rho target and contains the same canonical digit order
// as ALT_HORNER_TABLES for G.

pub(super) struct JointQTables {
    digit_window: Box<[U256TwoXAffine]>,
    terminal_pairs: Box<[U256Affine]>,
    pub(super) retained_bytes: usize,
}

pub(super) struct SparseJointQTables {
    digit_window: Box<[(usize, U256TwoXAffine)]>,
    terminal_pairs: Box<[(usize, U256Affine)]>,
    pub(super) retained_bytes: usize,
    pub(super) constructed_points: usize,
}

impl SparseJointQTables {
    fn digit(&self, index: usize, unit: usize) -> U256Affine {
        let position = self.digit_window.binary_search_by_key(&index, |&(id,_)| id)
            .expect("Q digit was prepared");
        self.digit_window[position].1.unit(unit)
    }

    fn terminal(&self, index: usize, unit: usize) -> U256Affine {
        let position = self.terminal_pairs.binary_search_by_key(&index, |&(id,_)| id)
            .expect("Q terminal was prepared");
        self.terminal_pairs[position].1.unit(unit)
    }
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

// Montgomery's trick converts both Q tables using one field inversion.
// Every input is a finite nonidentity point; seed zero is inserted afterward.
fn joint_batch_into_affine(points: &[U256Jacobian]) -> Vec<U256Affine> {
    if points.is_empty() { return Vec::new(); }
    let ctx = &super::HYBRID_FIELD.0;
    let mut prefix = Vec::with_capacity(points.len());
    let mut product = ctx.r_mod_n;
    for point in points {
        assert!(!point.is_identity());
        prefix.push(product);
        product = ctx.mont_mul(&product, &point.z);
    }
    let mut inverse = super::hybrid_binary_invert(product, ctx);
    let mut affine = vec![U256Affine { x: super::U256::ZERO,
                                       y: super::U256::ZERO }; points.len()];
    for index in (0..points.len()).rev() {
        let z_inverse = ctx.mont_mul(&inverse, &prefix[index]);
        inverse = ctx.mont_mul(&inverse, &points[index].z);
        let square = ctx.mont_sqr(&z_inverse);
        let cube = ctx.mont_mul(&square, &z_inverse);
        affine[index] = U256Affine {
            x: ctx.mont_mul(&points[index].x, &square),
            y: ctx.mont_mul(&points[index].y, &cube),
        };
    }
    assert_eq!(inverse.0, ctx.r_mod_n.0, "batch inverse product check");
    affine
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

fn joint_q_powers(q_hex: &str) -> ([U256Jacobian; 8], [U256Jacobian; 8]) {
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
    (a_powers, b_powers)
}

fn joint_seed_sets(g_tables: &AltHornerTables) -> (Vec<(i16,i16)>, Vec<(i16,i16)>) {
    let mut digit_seeds = g_tables.digit_pairs.iter().copied()
        .map(alt_orbit_canonical)
        .collect::<std::collections::BTreeSet<_>>()
        .into_iter().collect::<Vec<_>>();
    digit_seeds.retain(|&pair| pair != (0,0));
    digit_seeds.insert(0, (0,0));
    assert_eq!(digit_seeds.len(), g_tables.digit_window.len());
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
    (digit_seeds, terminal_seeds)
}

static JOINT_SEED_SETS: LazyLock<(Vec<(i16,i16)>, Vec<(i16,i16)>)> =
    LazyLock::new(|| joint_seed_sets(&ALT_HORNER_TABLES));

pub(super) fn warm_joint_seed_sets() -> usize {
    let (digit, terminal) = &*JOINT_SEED_SETS;
    (digit.capacity() + terminal.capacity())*size_of::<(i16,i16)>()
        + size_of::<(Vec<(i16,i16)>, Vec<(i16,i16)>)>()
}

pub(super) fn prepare_joint_q(q_hex: &str) -> JointQTables {
    let (a_powers, b_powers) = joint_q_powers(q_hex);
    let (digit_seeds, terminal_seeds) = &*JOINT_SEED_SETS;
    let digit_count = digit_seeds.len()-1;
    let projective = digit_seeds.iter().chain(terminal_seeds.iter())
        .copied().filter(|&seed| seed != (0,0))
        .map(|seed| joint_seed_point(seed, &a_powers, &b_powers))
        .collect::<Vec<_>>();
    let affine = joint_batch_into_affine(&projective);
    assert_eq!(affine.len(), digit_count + terminal_seeds.len()-1);
    let zero = U256Affine { x: super::U256::ZERO, y: super::U256::ZERO };
    let digit_window = std::iter::once(U256TwoXAffine::from_affine(zero))
        .chain(affine[..digit_count].iter().copied().map(U256TwoXAffine::from_affine))
        .collect::<Vec<_>>().into_boxed_slice();
    let terminal_pairs = std::iter::once(zero)
        .chain(affine[digit_count..].iter().copied())
        .collect::<Vec<_>>().into_boxed_slice();
    let retained_bytes = digit_window.len()*size_of::<U256TwoXAffine>()
        + terminal_pairs.len()*size_of::<U256Affine>()
        + size_of::<JointQTables>();
    JointQTables { digit_window, terminal_pairs, retained_bytes }
}

pub(super) fn prepare_joint_q_sparse(
    q_hex: &str,
    b_choices: &[[(usize,usize); ALT_SPLIT_PRIME_STEPS+1]],
) -> SparseJointQTables {
    let (digit_seeds, terminal_seeds) = &*JOINT_SEED_SETS;
    let digit_ids = b_choices.iter().flat_map(|choices| choices[..ALT_SPLIT_PRIME_STEPS]
        .iter().map(|&(index,_)| index)).filter(|&index| index != 0)
        .collect::<std::collections::BTreeSet<_>>();
    let terminal_ids = b_choices.iter().map(|choices| choices[ALT_SPLIT_PRIME_STEPS].0)
        .filter(|&index| index != 0)
        .collect::<std::collections::BTreeSet<_>>();
    let (a_powers, b_powers) = joint_q_powers(q_hex);
    let projective = digit_ids.iter().map(|&index| {
        joint_seed_point(digit_seeds[index], &a_powers, &b_powers)
    }).chain(terminal_ids.iter().map(|&index| {
        joint_seed_point(terminal_seeds[index], &a_powers, &b_powers)
    })).collect::<Vec<_>>();
    let affine = joint_batch_into_affine(&projective);
    let digit_count = digit_ids.len();
    let digit_window = digit_ids.into_iter().zip(affine[..digit_count].iter().copied())
        .map(|(index, point)| (index, U256TwoXAffine::from_affine(point)))
        .collect::<Vec<_>>().into_boxed_slice();
    let terminal_pairs = terminal_ids.into_iter().zip(affine[digit_count..].iter().copied())
        .collect::<Vec<_>>().into_boxed_slice();
    let retained_bytes = digit_window.len()*size_of::<(usize,U256TwoXAffine)>()
        + terminal_pairs.len()*size_of::<(usize,U256Affine)>()
        + size_of::<SparseJointQTables>();
    SparseJointQTables { digit_window, terminal_pairs, retained_bytes,
                         constructed_points: projective.len() }
}

fn joint_projective_unit(mut point: U256Jacobian, code: usize) -> U256Jacobian {
    assert!(code < 6);
    point = point.rotate_power(code/2);
    if code & 1 != 0 { point.y = u256_sub(super::U256::ZERO,point.y); }
    point
}

// Build requested Q digits as a shared graph in the Eisenstein coefficient
// lattice. Unit rotations of earlier vertices and shared binary powers of
// Q and tau(Q) supply one-addition edges; two earlier rotated vertices can
// also supply an edge. Isolated vertices use the direct binary-power path.
pub(super) fn prepare_joint_q_sparse_graph(
    q_hex: &str,
    b_choices: &[[(usize,usize); ALT_SPLIT_PRIME_STEPS+1]],
) -> (SparseJointQTables,usize,usize) {
    let (digit_seeds,terminal_seeds) = &*JOINT_SEED_SETS;
    let digit_ids = b_choices.iter().flat_map(|choices| choices[..ALT_SPLIT_PRIME_STEPS]
        .iter().map(|&(index,_)| index)).filter(|&index| index != 0)
        .collect::<std::collections::BTreeSet<_>>();
    let terminal_ids = b_choices.iter().map(|choices| choices[ALT_SPLIT_PRIME_STEPS].0)
        .filter(|&index| index != 0)
        .collect::<std::collections::BTreeSet<_>>();
    let seeds = digit_ids.iter().map(|&id| digit_seeds[id])
        .chain(terminal_ids.iter().map(|&id| terminal_seeds[id]))
        .collect::<std::collections::BTreeSet<_>>();
    let (a_powers,b_powers) = joint_q_powers(q_hex);
    let q = a_powers[0];
    let tau_q = b_powers[0];
    let mut negative_q = q;
    negative_q.y = u256_sub(super::U256::ZERO,negative_q.y);
    let mut negative_tau_q = tau_q;
    negative_tau_q.y = u256_sub(super::U256::ZERO,negative_tau_q.y);
    let mut graph = std::collections::BTreeMap::<(i16,i16),U256Jacobian>::new();
    let mut orbit = std::collections::BTreeMap::<(i16,i16),((i16,i16),usize)>::new();
    let (mut graph_edges,mut direct_seeds) = (0usize,0usize);
    for &(a,b) in &seeds {
        let mut constructed = None;
        for ((da,db),step) in [((1,0),q),((0,1),tau_q),
                               ((-1,0),negative_q),((0,-1),negative_tau_q)] {
            if let Some(&(source,code)) = orbit.get(&(a-da,b-db)) {
                constructed = Some(joint_projective_unit(graph[&source],code)
                    .add_projective(step));
                break;
            }
        }
        if constructed.is_none() {
            'power: for bit in 0..8 {
                for (base,power_point) in [((1i16 << bit,0i16),a_powers[bit]),
                                           ((0i16,1i16 << bit),b_powers[bit])] {
                    let mut coefficient = base;
                    for rotation in 0..3 {
                        for sign in 0..2 {
                            let step_pair = if sign == 0 { coefficient }
                                else { (-coefficient.0,-coefficient.1) };
                            if let Some(&(source,source_code)) =
                                orbit.get(&(a-step_pair.0,b-step_pair.1)) {
                                let parent = joint_projective_unit(graph[&source],source_code);
                                let step = joint_projective_unit(power_point,2*rotation+sign);
                                constructed = Some(parent.add_projective(step));
                                break 'power;
                            }
                        }
                        coefficient = alt_orbit_omega_pair(coefficient);
                    }
                }
            }
        }
        if constructed.is_none() {
            for (&coefficient,&(left_seed,left_code)) in &orbit {
                if let Some(&(right_seed,right_code)) =
                    orbit.get(&(a-coefficient.0,b-coefficient.1)) {
                    let left = joint_projective_unit(graph[&left_seed],left_code);
                    let right = joint_projective_unit(graph[&right_seed],right_code);
                    constructed = Some(left.add_projective(right));
                    break;
                }
            }
        }
        let point = if let Some(point) = constructed {
            graph_edges += 1;
            point
        } else {
            direct_seeds += 1;
            joint_seed_point((a,b),&a_powers,&b_powers)
        };
        assert!(!point.is_identity());
        graph.insert((a,b),point);
        let mut coefficient = (a,b);
        for rotation in 0..3 {
            assert!(orbit.insert(coefficient,((a,b),2*rotation)).is_none());
            assert!(orbit.insert((-coefficient.0,-coefficient.1),
                                 ((a,b),2*rotation+1)).is_none());
            coefficient = alt_orbit_omega_pair(coefficient);
        }
    }
    let projective = seeds.iter().map(|seed| graph[seed]).collect::<Vec<_>>();
    let affine = joint_batch_into_affine(&projective);
    let lookup = seeds.into_iter().zip(affine.into_iter())
        .collect::<std::collections::BTreeMap<_,_>>();
    let digit_window = digit_ids.into_iter().map(|id| {
        (id,U256TwoXAffine::from_affine(lookup[&digit_seeds[id]]))
    }).collect::<Vec<_>>().into_boxed_slice();
    let terminal_pairs = terminal_ids.into_iter().map(|id| {
        (id,lookup[&terminal_seeds[id]])
    }).collect::<Vec<_>>().into_boxed_slice();
    let retained_bytes = digit_window.len()*size_of::<(usize,U256TwoXAffine)>()
        + terminal_pairs.len()*size_of::<(usize,U256Affine)>()
        + size_of::<SparseJointQTables>();
    (SparseJointQTables { digit_window,terminal_pairs,retained_bytes,
                          constructed_points: projective.len() },
     graph_edges,direct_seeds)
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

pub(super) fn joint_choices_for_words(words: [u64; 4])
    -> [(usize,usize); ALT_SPLIT_PRIME_STEPS+1] {
    joint_choices(words, &ALT_HORNER_TABLES)
}

pub(super) fn joint_q_seed_pairs_for_choices(
    b_choices: &[[(usize,usize);ALT_SPLIT_PRIME_STEPS+1]],
) -> (Vec<(i16,i16)>,Vec<(i16,i16)>) {
    let (digit_seeds,terminal_seeds) = &*JOINT_SEED_SETS;
    let digit_ids = b_choices.iter().flat_map(|choices|
        choices[..ALT_SPLIT_PRIME_STEPS].iter().map(|&(id,_)| id))
        .filter(|&id| id != 0).collect::<std::collections::BTreeSet<_>>();
    let terminal_ids = b_choices.iter().map(|choices| choices[ALT_SPLIT_PRIME_STEPS].0)
        .filter(|&id| id != 0).collect::<std::collections::BTreeSet<_>>();
    (digit_ids.into_iter().map(|id| digit_seeds[id]).collect(),
     terminal_ids.into_iter().map(|id| terminal_seeds[id]).collect())
}

fn joint_evaluate_choices<Digit, Terminal>(
    a: [(usize,usize); ALT_SPLIT_PRIME_STEPS+1],
    b: [(usize,usize); ALT_SPLIT_PRIME_STEPS+1],
    q_digit: Digit, q_terminal: Terminal,
) -> String where Digit: Fn(usize,usize) -> U256Affine,
                  Terminal: Fn(usize,usize) -> U256Affine {
    let g_tables = &*ALT_HORNER_TABLES;
    let (ga, gu) = a[ALT_SPLIT_PRIME_STEPS];
    let (qb, qu) = b[ALT_SPLIT_PRIME_STEPS];
    let mut point = if ga == 0 { U256Jacobian::identity() } else {
        U256Jacobian::from_affine(g_tables.terminal_pairs[ga].unit(gu))
    };
    if qb != 0 { point = point.add_mixed(q_terminal(qb,qu)); }
    for index in (0..ALT_SPLIT_PRIME_STEPS).rev() {
        point = alt_horner_mul_pi(point);
        let (ga,gu) = a[index];
        let (qb,qu) = b[index];
        if ga != 0 { point = point.add_mixed(g_tables.digit_window[ga].unit(gu)); }
        if qb != 0 { point = point.add_mixed(q_digit(qb,qu)); }
    }
    point.affine_hex_binary_inverse()
}

pub(super) fn multiply_u256_tau_joint(a_words: [u64; 4], b_words: [u64; 4],
                                      q_tables: &JointQTables) -> String {
    let g_tables = &*ALT_HORNER_TABLES;
    let a = joint_choices(a_words, g_tables);
    let b = joint_choices(b_words, g_tables);
    joint_evaluate_choices(a, b,
        |index,unit| q_tables.digit_window[index].unit(unit),
        |index,unit| q_tables.terminal_pairs[index].unit(unit))
}

pub(super) fn multiply_u256_tau_joint_sparse(
    a_words: [u64; 4],
    b: [(usize,usize); ALT_SPLIT_PRIME_STEPS+1],
    q_tables: &SparseJointQTables,
) -> String {
    let a = joint_choices_for_words(a_words);
    joint_evaluate_choices(a, b,
        |index,unit| q_tables.digit(index,unit),
        |index,unit| q_tables.terminal(index,unit))
}

struct JointPairPending {
    position: usize,
    left: U256Affine,
    right: U256Affine,
    numerator: super::U256,
    denominator: super::U256,
}

fn joint_batch_invert(values: &[super::U256]) -> Vec<super::U256> {
    if values.is_empty() { return Vec::new(); }
    let ctx = &super::HYBRID_FIELD.0;
    let mut prefix = Vec::with_capacity(values.len());
    let mut product = ctx.r_mod_n;
    for &value in values {
        assert!(!bool::from(value.ct_is_zero()));
        prefix.push(product);
        product = ctx.mont_mul(&product, &value);
    }
    let mut inverse = super::hybrid_binary_invert(product,ctx);
    let mut result = vec![super::U256::ZERO;values.len()];
    for index in (0..values.len()).rev() {
        result[index] = ctx.mont_mul(&inverse,&prefix[index]);
        inverse = ctx.mont_mul(&inverse,&values[index]);
    }
    assert_eq!(inverse.0,ctx.r_mod_n.0,"pair denominator product check");
    result
}

pub(super) fn multiply_u256_tau_joint_fused_batch(
    a_words: &[[u64;4]],
    b_choices: &[[(usize,usize);ALT_SPLIT_PRIME_STEPS+1]],
    q_tables: &SparseJointQTables,
) -> (Vec<String>,usize) {
    assert_eq!(a_words.len(),b_choices.len());
    let g_tables = &*ALT_HORNER_TABLES;
    let slots = ALT_SPLIT_PRIME_STEPS+1;
    let mut pairs = vec![None;slots*a_words.len()];
    let mut pending = Vec::<JointPairPending>::new();
    for (case,(&a_words,b)) in a_words.iter().zip(b_choices.iter()).enumerate() {
        let a = joint_choices_for_words(a_words);
        for index in 0..slots {
            let (ga,gu) = a[index];
            let (qb,qu) = b[index];
            let g = if ga == 0 { None } else if index == ALT_SPLIT_PRIME_STEPS {
                Some(g_tables.terminal_pairs[ga].unit(gu))
            } else {
                Some(g_tables.digit_window[ga].unit(gu))
            };
            let q = if qb == 0 { None } else if index == ALT_SPLIT_PRIME_STEPS {
                Some(q_tables.terminal(qb,qu))
            } else {
                Some(q_tables.digit(qb,qu))
            };
            let position = case*slots+index;
            match (g,q) {
                (None,None) => {},
                (Some(point),None) | (None,Some(point)) => pairs[position] = Some(point),
                (Some(left),Some(right)) => {
                    let (numerator,denominator) = if left.x.0 == right.x.0 {
                        if left.y.0 != right.y.0 {
                            assert_eq!(u256_add(left.y,right.y).0,
                                       super::U256::ZERO.0,"opposite pair");
                            continue;
                        }
                        let xx = u256_square(left.x);
                        (u256_add(u256_add(xx,xx),xx),u256_add(left.y,left.y))
                    } else {
                        (u256_sub(right.y,left.y),u256_sub(right.x,left.x))
                    };
                    if bool::from(denominator.ct_is_zero()) { continue; }
                    pending.push(JointPairPending {
                        position,left,right,numerator,denominator,
                    });
                }
            }
        }
    }
    let denominators = pending.iter().map(|item| item.denominator).collect::<Vec<_>>();
    let inverses = joint_batch_invert(&denominators);
    for (item,inverse) in pending.iter().zip(inverses.into_iter()) {
        let slope = u256_mul(item.numerator,inverse);
        let x = u256_sub(u256_sub(u256_square(slope),item.left.x),item.right.x);
        let y = u256_sub(u256_mul(slope,u256_sub(item.left.x,x)),item.left.y);
        pairs[item.position] = Some(U256Affine {x,y});
    }
    let mut accumulators = Vec::with_capacity(a_words.len());
    for case in 0..a_words.len() {
        let base = case*slots;
        let mut point = pairs[base+ALT_SPLIT_PRIME_STEPS]
            .map(U256Jacobian::from_affine).unwrap_or_else(U256Jacobian::identity);
        for index in (0..ALT_SPLIT_PRIME_STEPS).rev() {
            point = alt_horner_mul_pi(point);
            if let Some(digit) = pairs[base+index] {
                point = point.add_mixed(digit);
            }
        }
        accumulators.push(point);
    }
    let finite = accumulators.iter().copied().filter(|point| !point.is_identity())
        .collect::<Vec<_>>();
    let affine = joint_batch_into_affine(&finite);
    let mut affine_iter = affine.into_iter();
    let answers = accumulators.iter().map(|point| {
        if point.is_identity() { "identity".to_owned() }
        else { affine_layer_hex(Some(affine_iter.next().expect("normalized output"))) }
    }).collect::<Vec<_>>();
    assert!(affine_iter.next().is_none());
    (answers,pending.len())
}
