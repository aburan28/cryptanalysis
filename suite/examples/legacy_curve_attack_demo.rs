use cryptanalysis_suite::cryptanalysis::{
    legacy_curve_attack_report, run_legacy_curve_attack_demos,
};

fn main() {
    let demos = run_legacy_curve_attack_demos();
    println!("{}", legacy_curve_attack_report(&demos));
}
