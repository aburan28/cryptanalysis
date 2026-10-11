//! Instruction counts of the generic reference, for pricing a pipeline
//! measured in instructions in group-addition equivalents (GAE).
//!
//! Two modes, each with its work in one `#[inline(never)]` function so a
//! profiler can collect it alone:
//!
//! ```text
//! valgrind --tool=callgrind --toggle-collect='*add_loop*' \
//!     target/release/examples/ir_calibration add [a] [n] [samples]
//! valgrind --tool=callgrind --toggle-collect='*rho_solve*' \
//!     target/release/examples/ir_calibration rho [a] [n] [seed]
//! ```
//!
//! - `add` runs exactly the loop `ic_boundary::calibrate_group` times:
//!   additions of 64 random multiples of the generator, on the fast
//!   single-word arithmetic of `koblitz_instance(a, n)` — the arithmetic
//!   of the rho reference and of the oracle ladder's GAE.  Instructions /
//!   `samples` is the conversion.
//! - `rho` runs `ic_boundary::rho_reference` once on that instance, for a
//!   target `[k]G` with `k` drawn from `seed`, and prints its counted
//!   result; its instructions price the reference in the same unit as the
//!   pipeline it is compared with.
//!
//! Prints what it ran as JSON.

use cryptanalysis_suite::cryptanalysis::ic_boundary::{
    koblitz_instance, rho_reference, BinaryGroup, CountedGroup, GroupOps, RhoResult,
};
use rand::{rngs::StdRng, Rng, SeedableRng};

#[inline(never)]
fn add_loop<G: CountedGroup>(g: &G, points: &[G::Elt], samples: u64) -> G::Elt {
    let mut ops = GroupOps::default();
    let n = points.len();
    let mut acc = points[0];
    for i in 0..samples {
        acc = g.add(&mut ops, acc, points[(i as usize * 7 + 1) % n]);
        if g.is_identity(&acc) {
            acc = points[(i as usize + 3) % n];
        }
    }
    acc
}

#[inline(never)]
fn rho_solve<G: CountedGroup>(
    g: &G,
    generator: G::Elt,
    target: G::Elt,
    r: u64,
    seed: u64,
) -> RhoResult {
    rho_reference(g, generator, target, r, seed, u64::MAX)
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let mode = args.get(1).map(String::as_str).unwrap_or("add");
    let a: u8 = args.get(2).and_then(|s| s.parse().ok()).unwrap_or(0);
    let n: u32 = args.get(3).and_then(|s| s.parse().ok()).unwrap_or(13);
    let param: u64 = args.get(4).and_then(|s| s.parse().ok()).unwrap_or(200_000);
    let inst = koblitz_instance(a, n).expect("a Koblitz instance at this degree");
    let g = BinaryGroup(&inst.fast);
    let mut ops = GroupOps::default();
    match mode {
        "add" => {
            let mut rng = StdRng::seed_from_u64(inst.r ^ 0xB1);
            let points: Vec<_> = (0..64)
                .map(|_| g.mul(&mut ops, inst.generator, rng.gen_range(1..inst.r)))
                .collect();
            std::hint::black_box(add_loop(&g, &points, param));
            println!(
                "{}",
                serde_json::json!({ "mode": "add", "a": a, "n": n, "r": inst.r, "samples": param, "instance": inst.name })
            );
        }
        "rho" => {
            let mut rng = StdRng::seed_from_u64(param);
            let k = rng.gen_range(1..inst.r);
            let target = g.mul(&mut ops, inst.generator, k);
            let result = rho_solve(&g, inst.generator, target, inst.r, param);
            assert!(
                result.verified && result.recovered == Some(k),
                "rho must recover k"
            );
            println!(
                "{}",
                serde_json::json!({ "mode": "rho", "a": a, "n": n, "r": inst.r, "seed": param, "k": k, "instance": inst.name, "result": result })
            );
        }
        other => panic!("unknown mode {other}; use add or rho"),
    }
}
