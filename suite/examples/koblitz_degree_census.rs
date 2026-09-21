//! Which Koblitz degrees this build offers, and the subgroup each gives.
//! cargo run --release --example koblitz_degree_census -- 53 67
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::KoblitzCurve;
use serde_json::json;

fn main() {
    let mut args = std::env::args().skip(1);
    let lo: u32 = args.next().map_or(31, |a| a.parse().unwrap());
    let hi: u32 = args.next().map_or(67, |a| a.parse().unwrap());
    for degree in lo..=hi {
        for a in [0u8, 1] {
            match KoblitzCurve::new(a, degree) {
                Some(kc) => println!(
                    "{}",
                    json!({
                        "degree": degree,
                        "curve_a": a,
                        "subgroup_order": kc.subgroup_order.to_string(),
                        "subgroup_bits": kc.subgroup_order.bits(),
                        "cofactor": kc.cofactor.to_string(),
                        "single_word": degree <= 62,
                    })
                ),
                None => println!(
                    "{}",
                    json!({"degree": degree, "curve_a": a, "available": false})
                ),
            }
        }
    }
}
