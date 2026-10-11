//! Which Koblitz degrees this repository can attack, and with what `r`.
//!
//! Written because a degree sweep assumed `r ≈ 2^{n-2}` and was wrong.
//! On this family `n` does not determine the subgroup order: the
//! cofactor swings from 4 at `n = 41` to 57,284,756 at `n = 59`, so
//! `r` is not monotone in `n` and two neighbouring degrees can differ by
//! fourteen bits of group order.
//!
//! That matters for any measurement of the `m = 3` scan, because the
//! scan saturates once `C(|F| + 2, 3)` approaches `r` — every probe hits,
//! the never-stopping sink spends its time in the `O(|F|)` recovery a
//! hit pays, and the figure stops being a probing cost.  Choosing a base
//! size by degree rather than by `r` walks straight into that; choosing
//! it by `r` is what this table is for.
//!
//! Degrees absent from the output have no usable prime-order subgroup
//! recorded, which is why a sweep over "the odd primes" finds nothing at
//! 43 or 47.
//!
//!     cargo run --release --example koblitz_degree_census
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::KoblitzCurve;

fn main() {
    println!(
        "{:>3} {:>2} {:>18} {:>7} {:>14} {:>12}",
        "n", "a", "r", "log2 r", "cofactor", "scarce |F| <"
    );
    for n in 9..=62u32 {
        for a in [0u8, 1] {
            let Some(kc) = KoblitzCurve::new(a, n) else {
                continue;
            };
            let r = &kc.subgroup_order;
            let bits = r.bits();
            // `C(|F| + 2, 3) ≈ |F|³/6`, so the scan stays scarce while
            // `|F|` is well under `(6r)^{1/3}`; a tenth of that leaves
            // three orders of margin on the hit rate.
            let cube = (6.0 * r.to_string().parse::<f64>().unwrap_or(0.0)).cbrt();
            println!(
                "{:>3} {:>2} {:>18} {:>7} {:>14} {:>12.0}",
                n,
                a,
                r,
                bits,
                kc.cofactor,
                cube / 3.0
            );
        }
    }
    println!(
        "\nthe last column is a base size that keeps the m = 3 scan measurable;\n\
         above it the scan measures recovery rather than probing"
    );
}
