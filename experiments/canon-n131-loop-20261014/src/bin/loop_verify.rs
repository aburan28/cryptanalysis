//! Exactness of the loop, workload by workload, over every key of the
//! protocol's pass length (plant_span):
//!
//! * (key, shift, hit) identical at every index across the five arms and the
//!   A/A copy, in record mode;
//! * equal to canon-n131 `exhaustive` on the independently generated stream,
//!   and to canon-n131 `oracle` (Vec<bool>, no limb code) on the first 20000;
//! * hit positions equal to the planted positions;
//! * the timed entry point's summary equal to record mode's;
//! * Frobenius = rotation by one on every stream word.
//!
//! usage: loop_verify [protocol.json] [keys]   (keys < plant_span only for smoke)
//! Prints one JSON object; exits nonzero on any mismatch.

use canon_n131::{oracle, to_msb_first, F131};
use canon_n131_loop::*;

fn hex(w: &W3) -> String {
    format!("{:01x}{:016x}{:016x}", w[2], w[1], w[0])
}

fn main() {
    let a: Vec<String> = std::env::args().collect();
    let path = a.get(1).cloned().unwrap_or_else(|| "protocol.json".into());
    let text = std::fs::read_to_string(&path).expect("protocol.json");
    let override_keys: Option<usize> = a.get(2).map(|s| s.parse().unwrap());
    let c = Ctx { g: consts(), cyc: ToCyclic::new() };
    let mut ok = true;
    let mut rows = vec![];
    for wl in workloads_from_protocol(&text) {
        let n = override_keys.unwrap_or(wl.plant_span).min(wl.plant_span);
        let (t, pos) = wl.build(&c);
        // independent stream + Frobenius check from the polynomial-basis states
        let mut s = wl.s0();
        let mut frob_bad = 0usize;
        let mut xs = Vec::with_capacity(n);
        for _ in 0..n {
            s = if wl.work == 1 { step::<1>(&s, &c.g) } else { step::<5>(&s, &c.g) };
            let x = c.cyc.apply(&field::from_polynomial(&s));
            let y = c.cyc.apply(&field::from_polynomial(&field::sqr(&s)));
            if y != F131::rotl(x, 1) {
                frob_bad += 1;
            }
            xs.push(x);
        }
        let refs: Vec<(W3, u32)> = xs.iter().map(|x| F131::exhaustive(*x)).collect();
        let n_oracle = n.min(20000);
        let mut oracle_bad = 0usize;
        for i in 0..n_oracle {
            let (o, os) = oracle(&xs[i], 131, 64);
            if o != to_msb_first(&refs[i].0, 131, 64) || os != refs[i].1 {
                oracle_bad += 1;
            }
        }
        let planted: Vec<usize> = pos.iter().copied().filter(|&i| i < n).collect();
        let mut arm_rows = vec![];
        let mut first: Option<Vec<(W3, u32, bool)>> = None;
        let mut ref_summary = None;
        for arm in 0..7 {
            let (sum, v) = record(arm, wl.work, &t, &c, wl.s0(), n);
            let timed = loop_fn(arm, wl.work)(&t, &c, wl.s0(), n);
            let hits: Vec<usize> = v.iter().enumerate().filter(|(_, r)| r.2).map(|(i, _)| i).collect();
            let mut vs_ref = 0usize;
            let mut vs_first = 0usize;
            if arm != 0 {
                for i in 0..n {
                    if (v[i].0, v[i].1) != refs[i] {
                        vs_ref += 1;
                    }
                }
                match &first {
                    None => {
                        first = Some(v.clone());
                        ref_summary = Some(sum);
                    }
                    Some(f) => vs_first = (0..n).filter(|&i| f[i] != v[i]).count(),
                }
            }
            let hits_ok = arm == 0 || hits == planted;
            let arm_ok = arm == 0 || (vs_ref == 0 && vs_first == 0 && hits_ok && timed == sum);
            ok &= arm_ok && timed == sum;
            arm_rows.push(format!(
                "{{\"arm\":\"{}\",\"keys\":{n},\"mismatch_vs_exhaustive_reference\":{vs_ref},\
\"mismatch_vs_first_arm\":{vs_first},\"hits\":{},\"hits_equal_planted_positions\":{hits_ok},\
\"timed_summary_equals_record\":{},\"key_hash\":\"{:016x}\",\"shift_sum\":{},\"last_state\":\"{}\",\"pass\":{}}}",
                ARM_NAMES[arm], sum.hits, timed == sum, sum.key_hash, sum.shift_sum, hex(&sum.last_state),
                arm_ok
            ));
        }
        ok &= frob_bad == 0 && oracle_bad == 0;
        let rs = ref_summary.unwrap();
        rows.push(format!(
            "{{\"workload\":\"{}\",\"keys\":{n},\"table_records\":{},\"table_bytes\":{},\"planted_below_keys\":{},\
\"frobenius_rotation_failures\":{frob_bad},\"oracle_checked\":{n_oracle},\"oracle_mismatches\":{oracle_bad},\
\"reference_summary\":{{\"hits\":{},\"key_hash\":\"{:016x}\",\"shift_sum\":{}}},\"arms\":[{}]}}",
            wl.name, t.recs.len(), t.bytes(), planted.len(), rs.hits, rs.key_hash, rs.shift_sum,
            arm_rows.join(",")
        ));
        eprintln!("{}: keys {n}, planted {}, frob_bad {frob_bad}, oracle_bad {oracle_bad}", wl.name, planted.len());
    }
    println!("{{\"pass\":{ok},\"workloads\":[{}]}}", rows.join(","));
    if !ok {
        std::process::exit(1);
    }
}
