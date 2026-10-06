//! Which pair-table representation a byte budget actually selects.
//!
//! The workflow report does not record the tier, and a measurement that
//! assumes which one ran is worth nothing — the tiers differ by an order
//! of magnitude in cost and the run that picked the wrong one looks
//! exactly like the run that picked the right one.

use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::*;

fn main() {
    let degree: u32 = std::env::args()
        .nth(1)
        .and_then(|s| s.parse().ok())
        .unwrap_or(61);
    let points: usize = std::env::args()
        .nth(2)
        .and_then(|s| s.parse().ok())
        .unwrap_or(12000);
    let budget: u128 = std::env::args()
        .nth(3)
        .and_then(|s| s.parse().ok())
        .unwrap_or(PairSumTable::DEFAULT_BYTE_BUDGET);
    let kc = KoblitzCurve::new(0, degree).expect("curve");
    let fb = build_subgroup_orbit_factor_base(&kc, 1, points).expect("factor base");
    let n = fb.points.len();
    let orbits = fb.signed_orbits.len();
    println!("base {n} points, {orbits} signed orbits at degree {degree}");
    println!(
        "  full    would want {:>12} bytes ({:.2} GiB)",
        PairSumTable::byte_size(n),
        PairSumTable::byte_size(n) as f64 / (1u128 << 30) as f64
    );
    println!(
        "  compact would want {:>12} bytes ({:.2} GiB)",
        PairSumTable::compact_byte_size(n, degree),
        PairSumTable::compact_byte_size(n, degree) as f64 / (1u128 << 30) as f64
    );
    println!(
        "  folded  would want {:>12} bytes ({:.2} GiB)",
        PairSumTable::folded_byte_size(orbits, n, degree),
        PairSumTable::folded_byte_size(orbits, n, degree) as f64 / (1u128 << 30) as f64
    );
    println!(
        "  budget             {:>12} bytes ({:.2} GiB)",
        budget,
        budget as f64 / (1u128 << 30) as f64
    );
    let t = PairSumTable::build_within(&kc, &fb, budget).expect("a tier fits the budget");
    let tier = if t.is_folded() {
        "folded"
    } else if t.is_compact() {
        "compact"
    } else {
        "full (summands stored)"
    };
    println!(
        "  -> build_within selected: {tier}, {} stored pairs",
        t.len()
    );
}
