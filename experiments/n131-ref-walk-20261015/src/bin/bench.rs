//! Paired, alternating per-step timing of the walk arms at one degree.
//!
//!   bench <n> <inputs.json> <steps_per_lane> <rounds> <out.jsonl>
//!   bench <n> <inputs.json> <steps_per_lane> ir <arm>     (one untimed pass, for cachegrind)
//!
//! Every block starts from the same 64 public lane states (a clone of one
//! template walker), runs `steps_per_lane` lockstep steps and records the
//! wall time.  Round `k` runs the arms in the order rotated by `k`, so each
//! arm takes every position equally often.  No logarithms are tracked.
use n131_ref_walk::*;
use std::io::Write;
use std::time::Instant;

fn setup<F: Field>(text: &str, a: u64, dp_hw: u32) -> (Ctx<F>, Vec<Pt>, Pt) {
    let c = Curve::<F>::new(a);
    let starts = hex_points(text, "starts");
    let jumps = hex_points(text, "jumps");
    let extra = hex_points(text, "stride_cursor");
    for p in starts.iter().chain(jumps.iter()).chain(extra.iter()) {
        assert!(c.on_curve(p), "input point not on the curve");
    }
    assert_eq!(starts.len(), 64);
    assert_eq!(jumps.len(), 32);
    let ctx = Ctx::new(c, dp_hw, jumps, vec![0; 32], 0, 1, extra[0], 0, 4096);
    (ctx, starts, extra[1])
}

fn go<F: Field>(n: u32, ctx: Ctx<F>, starts: Vec<Pt>, cursor: Pt, step: fn(&str) -> StepFn<F>, args: &[String]) {
    let steps: u64 = args[3].parse().unwrap();
    let templates: Vec<(String, Walker)> = TIMING_ARMS
        .iter()
        .map(|a| (a.to_string(), Walker::new(&ctx, arm_code(a), &starts, &[], cursor, 0)))
        .collect();
    if args[4] == "ir" {
        let name = &args[5];
        let t = &templates.iter().find(|(a, _)| a == name).expect("arm").1;
        let mut w = t.clone();
        let mut s = Fold::default();
        step(name)(&mut w, &ctx, steps, &mut s);
        println!("{{\"n\":{n},\"arm\":\"{name}\",\"steps_per_lane\":{steps},\"lane_steps\":{},\"dps\":{},\"escapes\":{},\"restarts\":{},\"checksum\":{}}}",
                 w.st.steps, w.st.dps, w.st.escapes, w.st.restarts, w.state_hash() ^ s.h);
        return;
    }
    let rounds: usize = args[4].parse().unwrap();
    let mut out = std::fs::File::create(&args[5]).unwrap();
    let k = templates.len();
    for round in 0..=rounds {
        // round 0 is the warmup, recorded with "warmup": true
        for pos in 0..k {
            let (name, t) = &templates[(pos + round) % k];
            let mut w = t.clone();
            let mut s = Fold::default();
            let f = step(name);
            let t0 = Instant::now();
            f(&mut w, &ctx, steps, &mut s);
            let ns = t0.elapsed().as_nanos() as u64;
            let ck = w.state_hash() ^ s.h;
            writeln!(out, "{{\"n\":{n},\"arm\":\"{name}\",\"round\":{round},\"pos\":{pos},\"warmup\":{},\"steps_per_lane\":{steps},\"lane_steps\":{},\"ns\":{ns},\"ns_per_step\":{:.4},\"dps\":{},\"escapes\":{},\"restarts\":{},\"zero_den\":{},\"checksum\":{ck}}}",
                     round == 0, w.st.steps, ns as f64 / w.st.steps as f64, w.st.dps, w.st.escapes, w.st.restarts, w.st.zero_den).unwrap();
        }
        eprintln!("n={n} round {round}/{rounds}");
    }
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let n: u32 = args[1].parse().unwrap();
    let text = std::fs::read_to_string(&args[2]).unwrap();
    match n {
        131 => {
            let (ctx, starts, cursor) = setup::<F131>(&text, 0, 52);
            go(131, ctx, starts, cursor, step131, &args)
        }
        83 => {
            let (ctx, starts, cursor) = setup::<F83>(&text, 1, 31);
            go(83, ctx, starts, cursor, step83, &args)
        }
        _ => panic!("n must be 83 or 131"),
    }
}
