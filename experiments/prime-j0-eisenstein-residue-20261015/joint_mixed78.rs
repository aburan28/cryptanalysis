// Two norm-6481 quotient steps followed by fourteen norm-58807 steps.
// The point evaluator runs the reverse Horner schedule: fourteen 243 steps,
// then two 81 steps. Q-table construction is reused from joint_norm58807.rs.
pub(super) const MIXED78_STEPS: usize = 16;
pub(super) type Mixed78Choices = [(i16,i16); MIXED78_STEPS+1];

pub(super) fn mixed78_choices_for_words(words: [u64;4]) -> Mixed78Choices {
    let scalar = super::Uint(words);
    let residue = if bool::from(scalar.ct_lt(&super::SCALAR_ORDER_WORDS)) {
        scalar
    } else { super::U256::sbb(&scalar,&super::SCALAR_ORDER_WORDS).0 };
    let ((mut a,mut b),_,_) =
        super::hexagonal_certified_fixed_choice_words(residue.0);
    let mut digits = [(0i16,0i16);MIXED78_STEPS+1];
    for (index,slot) in digits.iter_mut().take(MIXED78_STEPS).enumerate() {
        let first = index < 2;
        let (t,norm) = if first { (82i32,TRIPLE81_NORM) }
            else { (244i32,TRIPLE243_NORM) };
        let residue_word = a.add(b.times_alt_split_prime_small(t));
        let (_,_,r) = residue_word.div_rem_small_radix(norm as u64);
        let negative = r > (norm/2) as usize;
        let centered = if negative { norm as usize-r } else { r };
        let (raw_a,raw_b) = if first {
            triple81_nearest_digit(centered as i32)
        } else { triple243_nearest_digit(centered as i32) };
        let (da,db) = if negative { (-raw_a,-raw_b) } else { (raw_a,raw_b) };
        *slot = (da,db);
        let shifted_a = a.sub(Signed192::from_i32(i32::from(da)));
        let shifted_b = b.sub(Signed192::from_i32(i32::from(db)));
        let numerator_a = shifted_a.times_alt_split_prime_small(t-3)
            .add(shifted_b.times_alt_split_prime_small(-3));
        let numerator_b = shifted_a.add(shifted_b.times_alt_split_prime_small(t));
        let (next_a,rem_a,residue_a) =
            numerator_a.div_rem_small_radix(norm as u64);
        let (next_b,rem_b,residue_b) =
            numerator_b.div_rem_small_radix(norm as u64);
        assert_eq!((rem_a,residue_a,rem_b,residue_b),(0,0,0,0));
        a=next_a; b=next_b;
    }
    let (ai,aneg) = a.alt_split_prime_table_index(100);
    let (bi,bneg) = b.alt_split_prime_table_index(100);
    let terminal = (if aneg { -(ai as i16) } else { ai as i16 },
                    if bneg { -(bi as i16) } else { bi as i16 });
    let (ta,tb) = (i32::from(terminal.0),i32::from(terminal.1));
    assert!(ta*ta+3*ta*tb+3*tb*tb < 5000);
    digits[MIXED78_STEPS] = terminal;
    digits
}

pub(super) fn mixed78_joint_point(a: &Mixed78Choices,b: &Mixed78Choices,
    g: &Triple243Table,q: &Triple243Table) -> String {
    let mut point = U256Jacobian::identity();
    for index in (0..=MIXED78_STEPS).rev() {
        if index != MIXED78_STEPS {
            point = if index < 2 { triple81_horner(point) }
                else { triple243_horner(point) };
        }
        for (digit,table) in [(a[index],g),(b[index],q)] {
            if digit!=(0,0) { point=point.add_mixed(table.values[&digit]); }
        }
    }
    point.affine_hex_binary_inverse()
}
