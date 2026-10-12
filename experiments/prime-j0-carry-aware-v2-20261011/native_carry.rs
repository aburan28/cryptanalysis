// Injected into the direct-XYZZ-rho materialization by materialize_native.py.
#[repr(align(8))]
struct AlignedCarryOfferIndex([u8; 2_670_684]);

static CARRY_OFFER_BYTES: AlignedCarryOfferIndex =
    AlignedCarryOfferIndex(*include_bytes!(concat!(
        env!("CARGO_MANIFEST_DIR"), "/offers-r1024-dual-priority.bin")));

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq, Ord, PartialOrd)]
struct CarryDigit {
    a: i32,
    b: i32,
    seed: usize,
    map: usize,
    unit: usize,
}

struct CarryOfferIndex {
    offsets: &'static [u8],
    records: &'static [u8],
}

impl CarryOfferIndex {
    fn from_bytes(raw: &'static [u8]) -> Self {
        assert_eq!(&raw[..4], b"CA12");
        let radix = u32::from_le_bytes(raw[4..8].try_into().unwrap());
        let classes = u32::from_le_bytes(raw[8..12].try_into().unwrap()) as usize;
        let offers = u32::from_le_bytes(raw[12..16].try_into().unwrap()) as usize;
        assert_eq!((radix, classes, offers), (1024, 174_764, 246_451));
        let start = 16 + 4 * (classes + 1);
        assert_eq!(raw.len(), start + 8 * offers);
        let result = Self { offsets: &raw[16..start], records: &raw[start..] };
        assert_eq!(result.offset(0), 0);
        assert_eq!(result.offset(classes), offers);
        result
    }

    fn offset(&self, class: usize) -> usize {
        let start = 4 * class;
        u32::from_le_bytes(self.offsets[start..start + 4].try_into().unwrap()) as usize
    }

    fn candidates(&self, ra: usize, rb: usize) -> ([CarryDigit; 24], usize) {
        let (class, transform) = AdicOrbitFullAtlas::class_index(ra, rb);
        let first = self.offset(class);
        let last = self.offset(class + 1);
        assert!(first < last && last - first <= 24);
        let mut out = [CarryDigit::default(); 24];
        let inverse = 2 * ((3 - transform / 2) % 3) + (transform & 1);
        for (index, slot) in (first..last).enumerate() {
            let start = 8 * slot;
            let word = u64::from_le_bytes(
                self.records[start..start + 8].try_into().unwrap());
            let code = (word & 0xffff_ffff) as usize;
            let canonical_a = ((word >> 32) as u16) as i16 as i32;
            let canonical_b = ((word >> 48) as u16) as i16 as i32;
            let (seed, map, canonical_unit) =
                (code >> 5, (code >> 3) & 3, code & 7);
            assert!(seed < 67_338 && map < 4 && canonical_unit < 6);
            let unit = 2 * ((canonical_unit / 2 + 3 - transform / 2) % 3)
                + ((canonical_unit & 1) ^ (transform & 1));
            let (a, b) = unit_images((canonical_a, canonical_b))[inverse];
            debug_assert_eq!((a.rem_euclid(1024) as usize,
                              b.rem_euclid(1024) as usize), (ra, rb));
            out[index] = CarryDigit { a, b, seed, map, unit };
        }
        (out, last - first)
    }
}

static CARRY_OFFERS: LazyLock<CarryOfferIndex> =
    LazyLock::new(|| CarryOfferIndex::from_bytes(&CARRY_OFFER_BYTES.0));

#[derive(Clone, Copy)]
struct CarryState {
    a: Signed192,
    b: Signed192,
    rho: usize,
    terms: usize,
    path: [CarryDigit; 12],
}

// Two radix-1024 paths from one representative can differ by at most four
// in the first quotient coordinate and two in the second. Compare their
// Eisenstein norms through the exact difference formula in three limbs.
fn carry_mul_small(value: Signed192, factor: i32) -> Signed192 {
    let multiplier = u128::from(factor.unsigned_abs());
    let mut limbs = [0u64; 3];
    let mut carry = 0u128;
    for (index, limb) in limbs.iter_mut().enumerate() {
        let product = u128::from(value.limbs[index]) * multiplier + carry;
        *limb = product as u64;
        carry = product >> 64;
    }
    assert_eq!(carry, 0, "carry norm comparison overflow");
    Signed192 {
        negative: (value.negative ^ (factor < 0)) && limbs != [0; 3],
        limbs,
    }
}

fn carry_norm_cmp(left: &CarryState, right: &CarryState) -> std::cmp::Ordering {
    let da = left.a.sub(right.a).to_small_i32();
    let db = left.b.sub(right.b).to_small_i32();
    assert!(da.abs() <= 4 && db.abs() <= 2, "carry-state difference bound");
    let quadratic = da * da + 3 * da * db + 3 * db * db;
    let difference = carry_mul_small(right.a, 2 * da + 3 * db)
        .add(carry_mul_small(right.b, 3 * da + 6 * db))
        .add(Signed192::from_i32(quadratic));
    if difference.is_zero() { std::cmp::Ordering::Equal }
    else if difference.negative { std::cmp::Ordering::Less }
    else { std::cmp::Ordering::Greater }
}

impl CarryState {
    fn new(pair: (Signed192, Signed192)) -> Self {
        Self { a: pair.0, b: pair.1, rho: 0, terms: 0,
               path: [CarryDigit::default(); 12] }
    }

    fn compare(&self, other: &Self, used: usize) -> std::cmp::Ordering {
        (self.rho != 0).cmp(&(other.rho != 0))
            .then_with(|| self.rho.cmp(&other.rho))
            .then_with(|| self.terms.cmp(&other.terms))
            .then_with(|| carry_norm_cmp(self, other))
            .then_with(|| self.path[..used].cmp(&other.path[..used]))
    }

    fn step(mut self, digit: CarryDigit, window: usize) -> Self {
        self.a = self.a.sub(Signed192::from_i32(digit.a))
            .div_exact_power_of_two(10);
        self.b = self.b.sub(Signed192::from_i32(digit.b))
            .div_exact_power_of_two(10);
        self.rho += usize::from(digit.seed != 0 && digit.map == 3);
        self.terms += usize::from(digit.seed != 0);
        self.path[window] = digit;
        self
    }

    fn terminal(&self) -> (i32, i32) {
        (self.a.to_small_i32(), self.b.to_small_i32())
    }
}

fn carry_recode(
    representative: (Signed192, Signed192),
    full: &DualRhoFullAtlas,
    terminal: &Tau2TerminalResidualAtlas,
) -> ([(usize, usize, usize); 13], usize, usize) {
    let mut fixed = CarryState::new(representative);
    for window in 0..12 {
        let ra = fixed.a.rem_euclid_power_of_two(10);
        let rb = fixed.b.rem_euclid_power_of_two(10);
        let (pair, seed, map, unit) = full.digit_residue(ra, rb);
        fixed = fixed.step(CarryDigit {
            a: pair.0, b: pair.1, seed, map, unit,
        }, window);
    }
    assert!(norm(fixed.terminal()) < 149 * 149);

    let mut beam = vec![CarryState::new(representative)];
    let mut examined = 0usize;
    for window in 0..12 {
        let mut expanded = Vec::<CarryState>::with_capacity(48);
        for state in &beam {
            let ra = state.a.rem_euclid_power_of_two(10);
            let rb = state.b.rem_euclid_power_of_two(10);
            let (digits, length) = CARRY_OFFERS.candidates(ra, rb);
            examined += length;
            for digit in digits.into_iter().take(length) {
                let next = state.step(digit, window);
                if let Some(old) = expanded.iter_mut().find(|old|
                    old.a == next.a && old.b == next.b && old.rho == next.rho) {
                    if next.compare(old, window + 1).is_lt() { *old = next; }
                } else {
                    expanded.push(next);
                }
            }
        }
        expanded.sort_by(|left, right| left.compare(right, window + 1));
        expanded.truncate(2);
        assert!(!expanded.is_empty());
        beam = expanded;
    }
    let mut chosen = fixed;
    for state in beam {
        if norm(state.terminal()) < 149 * 149
            && state.compare(&chosen, 12).is_lt() {
            chosen = state;
        }
    }
    let mut choices = [(0usize, 0usize, 0usize); 13];
    for (index, digit) in chosen.path.iter().enumerate() {
        choices[index] = (digit.seed, digit.map, digit.unit);
    }
    let pair = chosen.terminal();
    let (digit, seed, map, unit) = terminal.digit_exact(pair.0, pair.1);
    assert_eq!(digit, pair);
    choices[12] = (seed, map, unit);
    (choices, chosen.terms + usize::from(seed != 0), examined)
}
