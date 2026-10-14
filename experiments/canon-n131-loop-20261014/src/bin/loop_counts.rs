//! One pass of every arm's loop symbol on one workload, for cachegrind
//! (`--cache-sim=no --branch-sim=yes`).  The table build and the reference
//! are outside the `loop_*` symbols, whose counts run.py divides by `keys`.
//!
//! usage: loop_counts <protocol.json> <workload> <keys>

use canon_n131_loop::*;

fn main() {
    let a: Vec<String> = std::env::args().collect();
    let text = std::fs::read_to_string(&a[1]).expect("protocol");
    let wl = workloads_from_protocol(&text).into_iter().find(|w| w.name == a[2]).expect("workload");
    let keys: usize = a[3].parse().unwrap();
    let c = Ctx { g: consts(), cyc: ToCyclic::new() };
    let (t, _) = wl.build(&c);
    let mut sums = vec![];
    for arm in 0..7 {
        let s = std::hint::black_box(loop_fn(arm, wl.work))(&t, &c, wl.s0(), keys);
        sums.push(s);
        println!("{} {} hits={} key_hash={:016x} shift_sum={}", wl.name, ARM_NAMES[arm], s.hits, s.key_hash, s.shift_sum);
    }
    for arm in 2..7 {
        assert_eq!(sums[arm], sums[1], "arm {} differs", ARM_NAMES[arm]);
    }
}
