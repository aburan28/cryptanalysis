//! n = 83, a = 1: walks to a verified logarithm.
//!
//!   solve <targets.json> <arm> <seed_base> <seeds> <lanes> <dp_hw> <lo> <hi> <out.jsonl>
//!
//! Targets `lo..hi` of the JSON list (each `{"id": .., "x": "<dec>", "y": "<dec>"}`,
//! optionally `"known_d"`), each with walk seeds `seed_base + 1000*id + s`,
//! `s < seeds`.  A row is written for every solve, verified or not.
use n131_ref_walk::n83::*;
use n131_ref_walk::*;
use std::io::Write;
use std::time::Instant;

fn field(obj: &str, key: &str) -> Option<String> {
    let pat = format!("\"{key}\":");
    let i = obj.find(&pat)? + pat.len();
    let rest = obj[i..].trim_start().trim_start_matches('"');
    let end = rest.find(|c: char| !c.is_ascii_alphanumeric() && c != '_').unwrap_or(rest.len());
    Some(rest[..end].to_string())
}

fn main() {
    let a: Vec<String> = std::env::args().collect();
    let text = std::fs::read_to_string(&a[1]).unwrap();
    let arm = &a[2];
    let seed_base: u64 = a[3].parse().unwrap();
    let seeds: u64 = a[4].parse().unwrap();
    let lanes: usize = a[5].parse().unwrap();
    let dp_hw: u32 = a[6].parse().unwrap();
    let lo: usize = a[7].parse().unwrap();
    let hi: usize = a[8].parse().unwrap();
    let mut out = std::fs::OpenOptions::new().create(true).append(true).open(&a[9]).unwrap();
    let c = Curve::<F83>::new(1);
    let g = gen();
    assert!(c.on_curve(&g) && c.smul(&g, &[R, 0, 0]).inf, "generator");
    let objs: Vec<&str> = text.split('{').skip(1).filter(|o| o.contains("\"id\"")).collect();
    for obj in &objs[lo..hi.min(objs.len())] {
        let id: u64 = field(obj, "id").unwrap().parse().unwrap();
        let x: u128 = field(obj, "x").unwrap().parse().unwrap();
        let y: u128 = field(obj, "y").unwrap().parse().unwrap();
        let known: Option<u64> = field(obj, "known_d").map(|s| s.parse().unwrap());
        let q = pt(x, y);
        assert!(c.on_curve(&q) && c.smul(&q, &[R, 0, 0]).inf, "target {id} not in the subgroup");
        for s in 0..seeds {
            let seed = seed_base + 1000 * id + s;
            let t0 = Instant::now();
            let o = solve(&c, arm, q, seed, lanes, dp_hw, 400 * floor() as u64);
            let ms = t0.elapsed().as_secs_f64() * 1e3;
            let verified = o.d.map(|d| c.smul(&g, &[d, 0, 0]) == q).unwrap_or(false);
            let known_ok = match (known, o.d) {
                (Some(k), Some(d)) => (k == d).to_string(),
                (Some(_), None) => "false".into(),
                _ => "null".into(),
            };
            writeln!(out, "{{\"arm\":\"{arm}\",\"target\":{id},\"seed\":{seed},\"seed_index\":{s},\"d\":{},\"verified\":{verified},\"known_match\":{known_ok},\"steps\":{},\"floor\":{:.3},\"steps_over_floor\":{:.6},\"dps\":{},\"escapes\":{},\"restarts\":{},\"zero_den\":{},\"failed_collisions\":{},\"wasted\":{},\"self_hits\":{},\"table\":{},\"wall_ms\":{:.1}}}",
                     o.d.map(|d| d.to_string()).unwrap_or("null".into()), o.st.steps, floor(), o.st.steps as f64 / floor(),
                     o.st.dps, o.st.escapes, o.st.restarts, o.st.zero_den, o.failed, o.wasted, o.self_hits, o.table, ms).unwrap();
            out.flush().unwrap();
        }
    }
}
