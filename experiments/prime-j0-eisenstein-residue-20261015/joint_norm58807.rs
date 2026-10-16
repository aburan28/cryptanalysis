// The conjugate pair (244-tau)(241+tau)=58807 permits sixteen fixed
// windows for certified secp256k1 representatives.
const TRIPLE243_NORM: i32 = 58807;
pub(super) const TRIPLE243_STEPS: usize = 16;
pub(super) type Triple243Choices = [(i16,i16); TRIPLE243_STEPS+1];

fn triple243_nearest_digit(residue: i32) -> (i16,i16) {
    if residue == 0 { return (0,0); }
    let mut best = (i32::MAX,i32::MAX,i32::MAX,i32::MAX,i32::MAX);
    for lift_number in -2..=2i32 {
        let lift = residue + lift_number*TRIPLE243_NORM;
        let center = (485*lift).div_euclid(2*TRIPLE243_NORM);
        for b in center-2..=center+2 {
            let a = lift-244*b;
            let norm = a*a+3*a*b+3*b*b;
            let score = (norm,b.abs(),a.abs(),a,b);
            if score < best { best = score; }
        }
    }
    (i16::try_from(best.3).unwrap(),i16::try_from(best.4).unwrap())
}

pub(super) fn triple243_choices_for_words(words: [u64;4]) -> Triple243Choices {
    let scalar = super::Uint(words);
    let residue = if bool::from(scalar.ct_lt(&super::SCALAR_ORDER_WORDS)) {
        scalar
    } else { super::U256::sbb(&scalar,&super::SCALAR_ORDER_WORDS).0 };
    let ((mut a,mut b),_,_) =
        super::hexagonal_certified_fixed_choice_words(residue.0);
    let mut digits = [(0i16,0i16);TRIPLE243_STEPS+1];
    for slot in digits.iter_mut().take(TRIPLE243_STEPS) {
        let residue_word = a.add(b.times_alt_split_prime_small(244));
        let (_,_,r) = residue_word.div_rem_small_radix(TRIPLE243_NORM as u64);
        let negative = r > (TRIPLE243_NORM/2) as usize;
        let index = if negative { TRIPLE243_NORM as usize-r } else { r };
        let (raw_a,raw_b) = triple243_nearest_digit(index as i32);
        let (da,db) = if negative { (-raw_a,-raw_b) } else { (raw_a,raw_b) };
        *slot = (da,db);
        let shifted_a = a.sub(Signed192::from_i32(i32::from(da)));
        let shifted_b = b.sub(Signed192::from_i32(i32::from(db)));
        let numerator_a = shifted_a.times_alt_split_prime_small(241)
            .add(shifted_b.times_alt_split_prime_small(-3));
        let numerator_b = shifted_a.add(shifted_b.times_alt_split_prime_small(244));
        let (next_a,rem_a,residue_a) =
            numerator_a.div_rem_small_radix(TRIPLE243_NORM as u64);
        let (next_b,rem_b,residue_b) =
            numerator_b.div_rem_small_radix(TRIPLE243_NORM as u64);
        assert_eq!((rem_a,residue_a,rem_b,residue_b),(0,0,0,0));
        a=next_a; b=next_b;
    }
    let (ai,aneg) = a.alt_split_prime_table_index(100);
    let (bi,bneg) = b.alt_split_prime_table_index(100);
    let terminal = (if aneg { -(ai as i16) } else { ai as i16 },
                    if bneg { -(bi as i16) } else { bi as i16 });
    let (ta,tb) = (i32::from(terminal.0),i32::from(terminal.1));
    assert!(ta*ta+3*ta*tb+3*tb*tb < 5000);
    digits[TRIPLE243_STEPS] = terminal;
    digits
}

fn triple243_horner(point: U256Jacobian) -> U256Jacobian {
    if point.is_identity() { return point; }
    let omega_point = point.rotate_power(1);
    let mut result = point;
    for _ in 0..5 { result = result.triple_j0(); }
    result.add_projective(omega_point)
}

pub(super) struct Triple243Table {
    values: std::collections::BTreeMap<(i16,i16),U256Affine>,
    pub(super) retained_bytes: usize,
}

pub(super) struct Triple243Plan {
    graph: JointQGraphPlan,
    requested: Vec<((i16,i16),(i16,i16),u8)>,
    pub(super) retained_bytes: usize,
    pub(super) graph_edges: usize,
    pub(super) direct_seeds: usize,
}

pub(super) fn compile_triple243_plan(choices: &[Triple243Choices]) -> Triple243Plan {
    let requested = choices.iter().flat_map(|row| row.iter().copied())
        .filter(|&digit| digit!=(0,0))
        .collect::<std::collections::BTreeSet<_>>();
    let seeds = requested.iter().copied().map(alt_orbit_canonical)
        .collect::<std::collections::BTreeSet<_>>();
    let mut orbit = std::collections::BTreeMap::<(i16,i16),((i16,i16),usize)>::new();
    let mut nodes = Vec::with_capacity(seeds.len());
    let (mut graph_edges,mut direct_seeds) = (0usize,0usize);
    for &(a,b) in &seeds {
        let mut op = None;
        for ((da,db),base,step_unit) in [((1,0),0,0),((0,1),1,0),
                                         ((-1,0),0,1),((0,-1),1,1)] {
            if let Some(&(parent,parent_unit)) = orbit.get(&(a-da,b-db)) {
                op = Some(JointGraphOp::Step { parent,parent_unit,base,bit:0,step_unit });
                break;
            }
        }
        if op.is_none() {
            'power: for bit in 0..9 {
                for (base,base_pair) in [(0,(1i16 << bit,0i16)),
                                         (1,(0i16,1i16 << bit))] {
                    let mut coefficient = base_pair;
                    for rotation in 0..3 {
                        for sign in 0..2 {
                            let delta = if sign == 0 { coefficient }
                                else { (-coefficient.0,-coefficient.1) };
                            if let Some(&(parent,parent_unit)) =
                                orbit.get(&(a-delta.0,b-delta.1)) {
                                op = Some(JointGraphOp::Step { parent,parent_unit,
                                    base,bit,step_unit:2*rotation+sign });
                                break 'power;
                            }
                        }
                        coefficient = alt_orbit_omega_pair(coefficient);
                    }
                }
            }
        }
        if op.is_none() {
            for (&coefficient,&(left,left_unit)) in &orbit {
                if let Some(&(right,right_unit)) =
                    orbit.get(&(a-coefficient.0,b-coefficient.1)) {
                    op = Some(JointGraphOp::Sum { left,left_unit,right,right_unit });
                    break;
                }
            }
        }
        let op = if let Some(op) = op { graph_edges += 1; op }
            else { direct_seeds += 1; JointGraphOp::Direct };
        nodes.push(JointGraphNode { seed:(a,b),op });
        let mut coefficient = (a,b);
        for rotation in 0..3 {
            assert!(orbit.insert(coefficient,((a,b),2*rotation)).is_none());
            assert!(orbit.insert((-coefficient.0,-coefficient.1),
                                 ((a,b),2*rotation+1)).is_none());
            coefficient = alt_orbit_omega_pair(coefficient);
        }
    }
    let requested = requested.into_iter().map(|digit| {
        let seed = alt_orbit_canonical(digit);
        let code = alt_orbit_code(digit,seed);
        (digit,seed,code)
    }).collect::<Vec<_>>();
    let nodes = nodes.into_boxed_slice();
    let graph = JointQGraphPlan {
        digit_ids: Box::new([]),terminal_ids: Box::new([]),
        retained_bytes: nodes.len()*size_of::<JointGraphNode>()
            + size_of::<JointQGraphPlan>(),
        nodes,graph_edges,direct_seeds,
    };
    let retained_bytes = graph.retained_bytes
        + requested.capacity()*size_of::<((i16,i16),(i16,i16),u8)>()
        + size_of::<Triple243Plan>();
    Triple243Plan { graph,requested,retained_bytes,graph_edges,direct_seeds }
}

pub(super) fn prepare_triple243_table(point_hex: &str,
    plan: &Triple243Plan) -> Triple243Table {
    let graph = triple243_graph_points(point_hex,&plan.graph);
    let projective = plan.requested.iter().map(|&(_,seed,code)|
        joint_projective_unit(graph[&seed],usize::from(code))).collect::<Vec<_>>();
    let affine = joint_batch_into_affine(&projective);
    let values = plan.requested.iter().map(|&(digit,_,_)| digit)
        .zip(affine.into_iter())
        .collect::<std::collections::BTreeMap<_,_>>();
    let retained_bytes = values.len()*size_of::<((i16,i16),U256Affine)>()
        + size_of::<Triple243Table>();
    Triple243Table { values,retained_bytes }
}

pub(super) fn triple243_joint_point(a: &Triple243Choices,b: &Triple243Choices,
    g: &Triple243Table,q: &Triple243Table) -> String {
    let mut point = U256Jacobian::identity();
    for index in (0..=TRIPLE243_STEPS).rev() {
        if index != TRIPLE243_STEPS { point = triple243_horner(point); }
        for (digit,table) in [(a[index],g),(b[index],q)] {
            if digit!=(0,0) { point=point.add_mixed(table.values[&digit]); }
        }
    }
    point.affine_hex_binary_inverse()
}


fn triple243_seed_point(seed: (i16,i16),
    a_powers: &[U256Jacobian;9], b_powers: &[U256Jacobian;9]) -> U256Jacobian {
    let mut result = U256Jacobian::identity();
    for (value,powers) in [(seed.0,a_powers),(seed.1,b_powers)] {
        let magnitude = value.unsigned_abs() as usize;
        assert!(magnitude < 512);
        for bit in 0..9 {
            if magnitude & (1usize << bit) != 0 {
                let mut term = powers[bit];
                if value < 0 { term.y = u256_sub(super::U256::ZERO,term.y); }
                result = result.add_projective(term);
            }
        }
    }
    result
}

fn triple243_q_powers(q_hex: &str) -> ([U256Jacobian;9],[U256Jacobian;9]) {
    let q = joint_parse_point(q_hex);
    let tau_q = q.tau();
    let mut a_powers = [U256Jacobian::identity();9];
    let mut b_powers = [U256Jacobian::identity();9];
    a_powers[0]=q;
    b_powers[0]=tau_q;
    for bit in 1..9 {
        a_powers[bit]=a_powers[bit-1].double();
        b_powers[bit]=b_powers[bit-1].double();
    }
    (a_powers,b_powers)
}

fn triple243_direct_orbit(seed: (i16,i16),
    a_powers: &[U256Jacobian;9], b_powers: &[U256Jacobian;9]) -> U256Jacobian {
    let mut representative = seed;
    let mut best_code = 0usize;
    let mut best_weight = u32::MAX;
    let mut rotated = seed;
    for power in 0..3usize {
        for sign in 0..2usize {
            let candidate = if sign == 0 { rotated }
                else { (-rotated.0,-rotated.1) };
            let weight = candidate.0.unsigned_abs().count_ones()
                + candidate.1.unsigned_abs().count_ones();
            if weight < best_weight {
                representative = candidate;
                best_code = 2*power+sign;
                best_weight = weight;
            }
        }
        rotated = alt_orbit_omega_pair(rotated);
    }
    let point = triple243_seed_point(representative,a_powers,b_powers);
    let inverse_code = 2*((3-best_code/2)%3)+best_code%2;
    joint_projective_unit(point,inverse_code)
}

fn triple243_graph_points(q_hex: &str,plan: &JointQGraphPlan)
    -> std::collections::BTreeMap<(i16,i16),U256Jacobian> {
    let (a_powers,b_powers)=triple243_q_powers(q_hex);
    let mut graph=std::collections::BTreeMap::new();
    for node in plan.nodes.iter() {
        let point=match node.op {
            JointGraphOp::Direct =>
                triple243_direct_orbit(node.seed,&a_powers,&b_powers),
            JointGraphOp::Step {parent,parent_unit,base,bit,step_unit} => {
                let parent=joint_projective_unit(graph[&parent],parent_unit);
                let power=if base==0 {a_powers[bit]} else {b_powers[bit]};
                joint_graph_add(parent,joint_projective_unit(power,step_unit))
            },
            JointGraphOp::Sum {left,left_unit,right,right_unit} => {
                let left=joint_projective_unit(graph[&left],left_unit);
                let right=joint_projective_unit(graph[&right],right_unit);
                joint_graph_add(left,right)
            },
        };
        assert!(!point.is_identity());
        graph.insert(node.seed,point);
    }
    graph
}
