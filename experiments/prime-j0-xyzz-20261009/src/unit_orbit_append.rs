// Appended inside the upstream unit-orbit module by build.rs.

pub(super) fn multiply_xyzz_format(
    scalar: &BigInt,
    format: u8,
) -> (super::Xyzz, BigInt, BigInt, usize, usize) {
    let lattice = &*SCALAR_LATTICE;
    let residue = ((scalar % &lattice.n) + &lattice.n) % &lattice.n;
    let (mut a, mut b) = hexagonal_four_corner_choices(&residue).remove(0);
    let (start_a, start_b) = (a.clone(), b.clone());
    let tables = selected(format);
    let mut result = super::Xyzz::identity();
    let mut nonidentity = 0usize;
    for (index, &width) in tables.widths.iter().enumerate() {
        let atlas = tables.atlas(width);
        let (digit, orbit_id, unit_code) = atlas.digit(&a, &b);
        let base = BigInt::from(atlas.base());
        a = (a - digit.0) / &base;
        b = (b - digit.1) / &base;
        if orbit_id == 0 {
            continue;
        }
        let mut addend = tables.windows[index][orbit_id].into_affine();
        for _ in 0..(unit_code / 2) {
            addend = addend.omega();
        }
        if unit_code & 1 != 0 {
            addend = addend.neg();
        }
        result = result.add_mixed(addend);
        nonidentity += 1;
    }
    assert!(a.is_zero() && b.is_zero(), "XYZZ recoding did not terminate");
    (result, start_a, start_b, nonidentity.saturating_sub(1), tables.retained_bytes)
}

pub(super) fn multiply_xyzz_deferred_format(
    scalar: &BigInt,
    format: u8,
) -> (super::Xyzz, BigInt, BigInt, usize, usize) {
    let lattice = &*SCALAR_LATTICE;
    let residue = ((scalar % &lattice.n) + &lattice.n) % &lattice.n;
    let (mut a, mut b) = hexagonal_four_corner_choices(&residue).remove(0);
    let (start_a, start_b) = (a.clone(), b.clone());
    let tables = selected(format);
    let mut result = super::Xyzz::identity();
    let mut nonidentity = 0usize;
    for (index, &width) in tables.widths.iter().enumerate() {
        let atlas = tables.atlas(width);
        let (digit, orbit_id, unit_code) = atlas.digit(&a, &b);
        let base = BigInt::from(atlas.base());
        a = (a - digit.0) / &base;
        b = (b - digit.1) / &base;
        if orbit_id == 0 {
            continue;
        }
        let mut addend = tables.windows[index][orbit_id].into_affine();
        for _ in 0..(unit_code / 2) {
            addend = addend.omega();
        }
        if unit_code & 1 != 0 {
            addend = addend.neg();
        }
        result = result.add_mixed_deferred(addend);
        nonidentity += 1;
    }
    assert!(a.is_zero() && b.is_zero(), "deferred XYZZ recoding did not terminate");
    (result, start_a, start_b, nonidentity.saturating_sub(1), tables.retained_bytes)
}
