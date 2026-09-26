//! The machine's random-access cost against working-set size, which is
//! what a decomposition probe actually pays.
//!
//! A probe is one random read of the presence filter, and the filter is
//! quadratic in the factor base: 32 MB at 9760 points, 128 MB at 18544,
//! 512 MB at 36112. The descent measured 0.148, 0.214 and 0.249 µs a
//! probe across those three, an exponent of `|F|^0.40` that the cost
//! model does not have. If that exponent is just this curve, it is not a
//! property of the code at all, and it can be extrapolated honestly.
//!
//! Two numbers per size, because a probe sits between them:
//!   * dependent — a pointer chase, every load waiting on the last, so
//!     the full latency including any page-table walk;
//!   * independent — random gathers with no dependency between them, so
//!     what the memory system delivers when the CPU can overlap.
//!
//! cargo run --release --example koblitz_memory_curve
use serde_json::json;
use std::time::Instant;

/// Sattolo's algorithm: one cycle through every slot.
fn single_cycle(n: usize, seed: u64) -> Vec<u64> {
    let mut order: Vec<u32> = (0..n as u32).collect();
    let mut state = seed | 1;
    let mut next = || {
        state ^= state << 13;
        state ^= state >> 7;
        state ^= state << 17;
        state
    };
    for i in (1..n).rev() {
        let j = (next() % i as u64) as usize;
        order.swap(i, j);
    }
    // order[k] -> order[k+1], closing the loop.
    let mut chase = vec![0u64; n];
    for k in 0..n {
        chase[order[k] as usize] = order[(k + 1) % n] as u64;
    }
    chase
}

fn main() {
    let steps: u64 = std::env::args()
        .nth(1)
        .map_or(20_000_000, |a| a.parse().unwrap());
    for megabytes in [1usize, 4, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096] {
        let n = megabytes * 1024 * 1024 / 8;
        let chase = single_cycle(n, 0x9e37_79b9_7f4a_7c15);

        // Dependent: each load's address comes from the last.
        let started = Instant::now();
        let mut at = 0usize;
        for _ in 0..steps {
            at = chase[at] as usize;
        }
        std::hint::black_box(at);
        let dependent = started.elapsed().as_secs_f64() * 1e9 / steps as f64;

        // Independent: addresses from a cheap generator, no dependency.
        let mask = n - 1;
        let usable = n.is_power_of_two();
        let started = Instant::now();
        let mut acc = 0u64;
        let mut x = 0x243f_6a88_85a3_08d3u64;
        for _ in 0..steps {
            x ^= x << 13;
            x ^= x >> 7;
            x ^= x << 17;
            let i = if usable {
                x as usize & mask
            } else {
                x as usize % n
            };
            acc = acc.wrapping_add(chase[i]);
        }
        std::hint::black_box(acc);
        let independent = started.elapsed().as_secs_f64() * 1e9 / steps as f64;

        println!(
            "{}",
            json!({
                "megabytes": megabytes,
                "dependent_nanoseconds": (dependent * 1000.0).round() / 1000.0,
                "independent_nanoseconds": (independent * 1000.0).round() / 1000.0,
            })
        );
    }
}
