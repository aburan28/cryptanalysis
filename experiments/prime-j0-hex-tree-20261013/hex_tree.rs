// Included after hex_terminal.rs in a disposable unit_orbit_windows module.
// The scalar recoder and table are unchanged; only the group-sum schedule differs.
const HEX_TREE_PLAN_DATA: &[u8] = include_bytes!("plans.bin");
const HEX_TREE_PLAN_BYTES: usize = 48;
const HEX_TREE_PLAN_COUNT: usize = 969;

fn hex_tree_plan_index(counts: [usize; 3]) -> usize {
    let [a, b, c] = counts;
    let size = a + b + c;
    assert!(size <= 16);
    let before_size = size * (size + 1) * (size + 2) / 6;
    let before_a = a * (size + 1) - a * a.saturating_sub(1) / 2;
    let index = before_size + before_a + b;
    assert!(index < HEX_TREE_PLAN_COUNT);
    index
}

fn hex_terminal_evaluate_tree(selected: &[(U256Affine, usize)]) -> (String, usize, usize) {
    assert_eq!(HEX_TREE_PLAN_DATA.len(), HEX_TREE_PLAN_COUNT * HEX_TREE_PLAN_BYTES);
    let mut counts = [0usize; 3];
    for &(_, code) in selected {
        assert!(code < 6);
        counts[code / 2] += 1;
    }
    let count = selected.len();
    assert!(count <= 16);
    if count == 0 { return ("identity".to_owned(), 0, 0); }
    let offset = HEX_TREE_PLAN_BYTES * hex_tree_plan_index(counts);
    let plan = &HEX_TREE_PLAN_DATA[offset..offset + HEX_TREE_PLAN_BYTES];
    let joins = plan[45] as usize;
    assert_eq!(joins, count - 1);
    let empty = GaugeTreeNode {
        point: GaugeTreePoint::Projective(U256XYZZCanonical::<true>::identity()),
        gauge: 0, product_depth: 0,
    };
    let mut nodes = [empty; 16];
    let mut next = [0, counts[0], counts[0] + counts[1]];
    for &(point, code) in selected {
        let gauge = code / 2;
        let slot = next[gauge];
        next[gauge] += 1;
        nodes[slot] = GaugeTreeNode {
            point: GaugeTreePoint::Affine(point.unit_solinas(code & 1)),
            gauge, product_depth: 0,
        };
    }
    let mut active = count;
    let mut rotations = 0usize;
    for step in plan[..3 * joins].chunks_exact(3) {
        let (i, j, gauge) = (step[0] as usize, step[1] as usize, step[2] as usize);
        assert!(i < j && j < active && gauge < 3);
        rotations += usize::from(nodes[i].gauge != gauge)
                   + usize::from(nodes[j].gauge != gauge);
        let joined = gauge_tree_join(nodes[i], nodes[j], gauge);
        for slot in j..active - 1 { nodes[slot] = nodes[slot + 1]; }
        active -= 1;
        for slot in i..active - 1 { nodes[slot] = nodes[slot + 1]; }
        active -= 1;
        nodes[active] = joined;
        active += 1;
    }
    assert_eq!(active, 1);
    rotations += usize::from(nodes[0].gauge != 0);
    let last = nodes[0].rotate_to(0);
    assert_eq!(rotations, plan[46] as usize);
    assert_eq!(last.product_depth, plan[47] as usize);
    let point = match last.point {
        GaugeTreePoint::Affine(p) => U256XYZZCanonical::<true>::from_affine(p),
        GaugeTreePoint::Projective(p) => p,
    };
    (point.affine_hex_binary_inverse(), rotations, last.product_depth)
}

pub(super) fn multiply_u256_hex_tree(
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
    let (point, rotations, _) = hex_terminal_evaluate_tree(&selected);
    (point, representative, selected.len().saturating_sub(1),
     tables.retained_bytes + HEX_TREE_PLAN_DATA.len(), fallback, corner, rotations)
}
