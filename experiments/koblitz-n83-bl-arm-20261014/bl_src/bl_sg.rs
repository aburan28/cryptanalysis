#![recursion_limit = "256"]
//! Bernstein–Lange precomputation rho on the library walk `StrongRhoG<F, u64>`
//! (signed-Frobenius classes, normal-basis least-rotation canonicalization,
//! 32 G-only r-adding jumps, lockstep lanes with batched inversion), for the
//! cryptanalysis experiment `experiments/koblitz-n83-bl-arm-20261014/`.
//!
//! The walk is the library's: `sg` below is crypto 770f6a69's
//! `koblitz_strong_rho.rs` with `bl_precompute` and `solve_with_table`
//! appended (see the banner there and `restore_sources.py`). The field is a
//! parameter: `gf2` (library `Gf2`, `n <= 63`), `wide` (library `WideGf2`,
//! the walk of A's `n83_strong_point_eval`) or `fold` (library `Gf2_128`
//! behind the same contract, the field of A's tuned `n83_rho_optimization_eval`).
//! Jumps and walk starts are derived exactly as those two adapters derive
//! them: the jump table from BLAKE3("n83-exact-public-strong-jumps-v1\0" ||
//! seed), the walk starts from `StdRng::seed_from_u64(seed)`.
//!
//! Modes (`bl_sg <mode> --key value ...`):
//! * `precompute`: build a table from `--bl-jump-seed`'s jumps and
//!   `--precompute-seed`'s starts until `--budget-ms`, `--stop-steps` or
//!   `--stop-rounds`, write it to `--table-out`, print one summary line.
//! * `online`: solve one target (`--target x,y` public point, or `--scalar d`
//!   for a known-answer control) from `--walk-seed`, with `--table` loaded
//!   (BLAKE3 checked against `--table-blake3`) or with an empty table (plain
//!   rho). `--reference-jumps` draws the jumps from the walk seed instead, as
//!   the adapters do, so an empty-table run is the adapter's walk.
//!   The online interval starts at the first target-dependent operation (the
//!   walk start `[c]G + Q`, inside the solve) and stops when a collision gave
//!   `d` with `[d]G = Q` (checked inside the solve). Membership/subgroup check
//!   and a generic library replay of `[d]G = Q` are timed apart.
//! * `verify-table`: check every record: on the curve's walk, distinguished,
//!   canonical, and `[a]G = (x, y)`; `--threads` workers.

#[allow(dead_code, clippy::all)]
#[path = "sg_bl_module.rs"]
mod sg;

include!("bl_table_io.rs");

use crypto_lib::binary_ecc::{BinaryPoint, F2mElement};
use crypto_lib::cryptanalysis::koblitz_index_calculus::KoblitzCurve;
use crypto_lib::cryptanalysis::semaev_decomp::Gf2_128;
use crypto_lib::cryptanalysis::wide_gf2m::WideGf2;
use num_bigint::BigUint;
use num_traits::ToPrimitive;
use rand::rngs::StdRng;
use rand::SeedableRng;
use serde_json::{json, Value};
use sg::{RawPointG, RhoField, StrongRhoCharges, StrongRhoG, StrongRhoParams};
use std::collections::HashMap;
use std::time::Instant;

/// `Gf2_128` behind the walk's field contract (as in A's tuned worker).
struct FoldField(Gf2_128);

impl RhoField for FoldField {
    type E = u128;
    fn degree(&self) -> u32 {
        self.0.n
    }
    #[inline(always)]
    fn mul(&self, a: u128, b: u128) -> u128 {
        self.0.mul(a, b)
    }
    #[inline(always)]
    fn sqr(&self, a: u128) -> u128 {
        self.0.sqr(a)
    }
    fn batch_inv(&self, xs: &mut [u128], scratch: &mut Vec<u128>) {
        self.0.batch_inv(xs, scratch);
    }
}

struct Args(HashMap<String, String>);

impl Args {
    fn parse(raw: &[String]) -> Self {
        let mut map = HashMap::new();
        let mut i = 0;
        while i < raw.len() {
            let key = raw[i].strip_prefix("--").unwrap_or_else(|| panic!("unexpected argument {}", raw[i]));
            if key == "reference-jumps" {
                map.insert(key.to_owned(), "1".to_owned());
                i += 1;
                continue;
            }
            let value = raw.get(i + 1).unwrap_or_else(|| panic!("--{key} needs a value"));
            assert!(map.insert(key.to_owned(), value.clone()).is_none(), "--{key} given twice");
            i += 2;
        }
        Args(map)
    }
    fn get(&self, key: &str) -> Option<&str> {
        self.0.get(key).map(String::as_str)
    }
    fn req(&self, key: &str) -> &str {
        self.get(key).unwrap_or_else(|| panic!("--{key} is required"))
    }
    fn num<T: std::str::FromStr>(&self, key: &str) -> Option<T> {
        self.get(key).map(|v| v.parse().unwrap_or_else(|_| panic!("--{key} is not a number")))
    }
}

fn jump_seed_of(seed: u64) -> u64 {
    let mut material = b"n83-exact-public-strong-jumps-v1\0".to_vec();
    material.extend_from_slice(&seed.to_le_bytes());
    let digest = blake3::hash(&material);
    u64::from_le_bytes(digest.as_bytes()[..8].try_into().unwrap())
}

fn params(args: &Args) -> StrongRhoParams {
    StrongRhoParams {
        lanes: args.num("lanes").expect("--lanes is required"),
        dp_bits: args.num("dp-bits").expect("--dp-bits is required"),
        step_cap_factor: args.num("step-cap-factor").unwrap_or(2_000),
        escape_fruitless: args.get("escape").map(|v| v == "1").unwrap_or(false),
    }
}

fn params_json(p: &StrongRhoParams) -> Value {
    json!({"lanes": p.lanes, "dp_bits": p.dp_bits, "step_cap_factor": p.step_cap_factor,
           "escape_fruitless": p.escape_fruitless})
}

fn charges_json(c: StrongRhoCharges) -> Value {
    json!({
        "group_additions": c.group_additions,
        "scalar_multiplications": c.scalar_multiplications,
        "canonicalizations": c.canonicalizations,
        "partition_hashes": c.partition_hashes,
        "table_queries": c.table_queries,
        "table_inserts": c.table_inserts,
        "failed_collisions": c.failed_collisions,
    })
}

fn library_point(n: u32, x: u128, y: u128) -> BinaryPoint {
    BinaryPoint::Affine {
        x: F2mElement::from_biguint(&BigUint::from(x), n),
        y: F2mElement::from_biguint(&BigUint::from(y), n),
    }
}

fn point_words(point: &BinaryPoint) -> (u128, u128) {
    match point {
        BinaryPoint::Affine { x, y } => {
            let w = |bits: &[u64]| bits.first().copied().unwrap_or(0) as u128 | ((bits.get(1).copied().unwrap_or(0) as u128) << 64);
            (w(x.raw_bits()), w(y.raw_bits()))
        }
        BinaryPoint::Infinity => panic!("affine point required"),
    }
}

fn raw<E: TryFrom<u128>>(x: u128, y: u128) -> RawPointG<E> {
    RawPointG::Affine {
        x: E::try_from(x).ok().expect("coordinate does not fit the field word"),
        y: E::try_from(y).ok().expect("coordinate does not fit the field word"),
    }
}

fn words<E: Into<u128>>(point: RawPointG<E>) -> Option<(u128, u128)> {
    match point {
        RawPointG::Affine { x, y } => Some((x.into(), y.into())),
        RawPointG::Infinity => None,
    }
}

fn run<F: RhoField>(mode: &str, args: &Args, curve: KoblitzCurve, rho: StrongRhoG<F, u64>, field: &str, process_started: Instant)
where
    F::E: Into<u128> + TryFrom<u128>,
{
    let n = curve.n;
    let a = curve.a;
    let r = rho.modulus();
    let automorphisms = rho.automorphisms();
    let p = params(args);
    let identity = json!({"n": n, "a": a, "subgroup_order": r.to_string(), "lambda": rho.lambda().to_string(),
        "automorphism_size": automorphisms, "field": field, "walk": "StrongRhoG<F,u64> (library koblitz_strong_rho, crypto 770f6a69)",
        "rho_params": params_json(&p)});
    match mode {
        "precompute" => {
            let bl_jump_seed: u64 = args.num("bl-jump-seed").expect("--bl-jump-seed is required");
            let precompute_seed: u64 = args.num("precompute-seed").expect("--precompute-seed is required");
            let mut setup = StrongRhoCharges::default();
            let jumps = rho.jumps(jump_seed_of(bl_jump_seed), &mut setup);
            let setup_ms = process_started.elapsed().as_secs_f64() * 1000.0;
            let mut stopper = BlStop::from_env_or_args(args.num("budget-ms"), args.num("stop-steps"), args.num("stop-rounds"));
            let mut start_rng = StdRng::seed_from_u64(precompute_seed);
            let mut table: HashMap<(u8, F::E, F::E), (u64, u64)> = HashMap::new();
            // The budget clock and the reported precompute interval are one clock.
            stopper.started = Instant::now();
            let started = stopper.started;
            let stats = rho.bl_precompute(&jumps, &mut start_rng, &p, &mut table,
                &mut |st, _entries| stopper.reached(st.rounds, st.steps));
            let precompute_ms = started.elapsed().as_secs_f64() * 1000.0;
            let rows: Vec<(u128, u128, u64)> = table
                .iter()
                .map(|(&(_, x, y), &(log, b))| {
                    assert_eq!(b, 0, "a precomputed entry has b != 0");
                    (x.into(), y.into(), log)
                })
                .collect();
            drop(table);
            let write_started = Instant::now();
            let (entries, blake3_hex) = bl_write_table(args.req("table-out"), rows);
            let write_ms = write_started.elapsed().as_secs_f64() * 1000.0;
            println!("{}", json!({
                "kind": "bl_precompute", "family": "sg", "identity": identity,
                "bl_jump_seed": bl_jump_seed, "jump_seed_derived": jump_seed_of(bl_jump_seed),
                "precompute_seed": precompute_seed,
                "stop_rule": {"budget_ms": stopper.budget_ms, "stop_steps": stopper.stop_steps, "stop_rounds": stopper.stop_rounds},
                "setup_ms_excluded": setup_ms, "precompute_ms": precompute_ms, "table_write_ms": write_ms,
                "rounds": stats.rounds, "steps": stats.steps, "walks": stats.walks,
                "fruitless": stats.fruitless, "escapes": stats.escapes, "capped": stats.capped,
                "new_points": stats.new_points, "duplicate_points": stats.duplicate_points,
                "covered_points": stats.covered_points, "duplicate_walk_steps": stats.duplicate_walk_steps,
                "abandoned_walk_steps": stats.abandoned_walk_steps, "group_additions": stats.group_additions,
                "scalar_multiplications": stats.scalar_multiplications, "infinity_points": stats.infinity_points,
                "table_entries": entries, "table_blake3": blake3_hex, "record_bytes": BL_RECORD_BYTES,
                "ns_per_step": if stats.steps > 0 { precompute_ms * 1e6 / stats.steps as f64 } else { 0.0 },
                "peak_rss_bytes": bl_peak_rss_bytes(),
            }));
        }
        "online" => {
            let walk_seed: u64 = args.num("walk-seed").expect("--walk-seed is required");
            let reference_jumps = args.get("reference-jumps").is_some();
            let jump_seed = if reference_jumps {
                assert!(args.get("bl-jump-seed").is_none(), "--reference-jumps excludes --bl-jump-seed");
                jump_seed_of(walk_seed)
            } else {
                jump_seed_of(args.num("bl-jump-seed").expect("--bl-jump-seed or --reference-jumps is required"))
            };
            let mut setup = StrongRhoCharges::default();
            let jumps = rho.jumps(jump_seed, &mut setup);
            // Target: a public point, or a known-answer control built from d
            // (fixture construction, outside every interval).
            let (q_words, planted) = match (args.get("target"), args.num::<u64>("scalar")) {
                (Some(text), None) => {
                    let (x, y) = text.split_once(',').expect("--target must be x,y");
                    ((x.trim().parse::<u128>().unwrap(), y.trim().parse::<u128>().unwrap()), None)
                }
                (None, Some(d)) => {
                    assert!(d > 0 && d < r, "--scalar must lie in [1, r)");
                    (words(rho.scalar_mul(rho.generator(), d)).expect("planted point is affine"), Some(d))
                }
                _ => panic!("give exactly one of --target and --scalar"),
            };
            let mut table: HashMap<(u8, F::E, F::E), (u64, u64)> = HashMap::new();
            let mut table_info = json!(null);
            if let Some(path) = args.get("table") {
                let (rows, digest, read_ms) = bl_read_table(path, Some(args.req("table-blake3")));
                let insert_started = Instant::now();
                table.reserve(rows.len() + (1 << 16));
                for (x, y, log) in &rows {
                    let RawPointG::Affine { x: ex, y: ey } = raw::<F::E>(*x, *y) else { unreachable!() };
                    table.insert((1, ex, ey), (*log, 0));
                }
                table_info = json!({"path": path, "entries": rows.len(), "blake3": digest, "read_ms": read_ms,
                    "insert_ms": insert_started.elapsed().as_secs_f64() * 1000.0});
            }
            let entries_loaded = table.len();
            let membership_started = Instant::now();
            let q_lib = library_point(n, q_words.0, q_words.1);
            let in_subgroup = curve.curve.is_on_curve(&q_lib)
                && curve.mul(&q_lib, &curve.subgroup_order) == BinaryPoint::Infinity;
            let membership_ns = membership_started.elapsed().as_nanos() as u64;
            assert!(in_subgroup, "target is not in the prime-order subgroup");
            let q = raw::<F::E>(q_words.0, q_words.1);
            let mut start_rng = StdRng::seed_from_u64(walk_seed);
            let mut precomputed_hit = false;
            let online_start_ns = process_started.elapsed().as_nanos() as u64;
            let online_started = Instant::now();
            let outcome = rho.solve_with_table(q, &jumps, &mut start_rng, &p, StrongRhoCharges::default(),
                &mut table, &mut precomputed_hit);
            let online_ns = online_started.elapsed().as_nanos() as u64;
            let outcome = outcome.expect("step cap reached without a verified collision");
            let replay_started = Instant::now();
            let replay = curve.mul(curve.generator(), &BigUint::from(outcome.scalar)) == q_lib;
            let replay_ns = replay_started.elapsed().as_nanos() as u64;
            assert!(replay, "generic replay of [d]G = Q failed");
            if let Some(d) = planted {
                assert_eq!(outcome.scalar, d, "recovered scalar differs from the planted one");
            }
            println!("{}", json!({
                "kind": "bl_online", "family": "sg", "identity": identity,
                "mode": if entries_loaded > 0 { "bl" } else { "plain" },
                "jumps": if reference_jumps { "reference (from the walk seed, as the adapters)" } else { "bl (from --bl-jump-seed)" },
                "jump_seed_derived": jump_seed, "walk_seed": walk_seed,
                "target_source": if planted.is_some() { "known_scalar_control" } else { "public_point" },
                "published_q": [q_words.0.to_string(), q_words.1.to_string()],
                "planted_scalar": planted, "recovered_scalar": outcome.scalar, "verified": true,
                "solved_by": if precomputed_hit { "precomputed_table" } else { "online_self_collision" },
                "table": table_info, "table_entries_loaded": entries_loaded,
                "table_entries_after": outcome.table_entries,
                "walk_steps": outcome.walk_steps, "walks": outcome.walks, "fruitless": outcome.fruitless,
                "escapes": outcome.escapes, "capped": outcome.capped, "wasted_merges": outcome.wasted_merges,
                "ideal_steps": outcome.ideal_steps, "charges": charges_json(outcome.charges),
                "setup_ms_excluded": online_start_ns as f64 / 1e6,
                "online_start_event": "first walk start [c]G+Q (inside the solve)",
                "online_stop_event": "collision with [d]G = Q (checked inside the solve)",
                "online_ns": online_ns, "online_ms": online_ns as f64 / 1e6,
                "membership_check_ns_excluded": membership_ns, "generic_replay_ns_excluded": replay_ns,
                "online_ms_at_A_boundary": (membership_ns + online_ns + replay_ns) as f64 / 1e6,
                "peak_rss_bytes": bl_peak_rss_bytes(),
            }));
        }
        "verify-table" => {
            let dp_bits: u32 = args.num("dp-bits").expect("--dp-bits is required");
            let threads: usize = args.num("threads").unwrap_or(1).max(1);
            let (rows, digest, read_ms) = bl_read_table(args.req("table"), args.get("table-blake3"));
            let started = Instant::now();
            let chunk = rows.len().div_ceil(threads).max(1);
            let rho = &rho;
            let bad: Vec<(usize, &'static str)> = std::thread::scope(|scope| {
                let handles: Vec<_> = rows
                    .chunks(chunk)
                    .enumerate()
                    .map(|(c, part)| {
                        scope.spawn(move || {
                            let mut bad = Vec::new();
                            for (i, &(x, y, log)) in part.iter().enumerate() {
                                let index = c * chunk + i;
                                let point = raw::<F::E>(x, y);
                                if !(log > 0 && log < r) {
                                    bad.push((index, "log out of range"));
                                } else if !rho.bl_is_distinguished(point, dp_bits) {
                                    bad.push((index, "not distinguished"));
                                } else if !rho.bl_is_canonical(point) {
                                    bad.push((index, "not canonical"));
                                } else if rho.scalar_mul(rho.generator(), log) != point {
                                    bad.push((index, "[a]G differs from the point"));
                                }
                            }
                            bad
                        })
                    })
                    .collect();
                handles.into_iter().flat_map(|h| h.join().unwrap()).collect()
            });
            let ok = bad.is_empty();
            println!("{}", json!({
                "kind": "bl_table_verification", "family": "sg", "identity": identity, "dp_bits": dp_bits,
                "entries": rows.len(), "blake3": digest, "read_ms": read_ms, "threads": threads,
                "verify_ms": started.elapsed().as_secs_f64() * 1000.0,
                "checks": ["log in [1, r)", "distinguished under the walk's dp_hash", "own signed-Frobenius representative", "[a]G equals the stored point"],
                "bad": bad.len(), "bad_first": bad.iter().take(20).map(|(i, why)| json!([i, why])).collect::<Vec<_>>(),
                "status": if ok { "PASS" } else { "FAIL" },
            }));
            if !ok {
                std::process::exit(3);
            }
        }
        other => panic!("unknown mode {other}"),
    }
}

fn main() {
    let process_started = Instant::now();
    let raw_args: Vec<String> = std::env::args().collect();
    assert!(raw_args.len() >= 2, "usage: bl_sg <precompute|online|verify-table> --key value ...");
    let mode = raw_args[1].clone();
    let args = Args::parse(&raw_args[2..]);
    let (n, a) = args.req("curve").split_once(',').expect("--curve must be n,a");
    let (n, a): (u32, u8) = (n.parse().unwrap(), a.parse().unwrap());
    let curve = KoblitzCurve::new(a, n).expect("Koblitz curve must construct");
    let r = curve.subgroup_order.to_u64().expect("subgroup order must fit u64");
    let lambda = curve.lambda.to_u64().expect("lambda must fit u64");
    let field = args.req("field").to_owned();
    match field.as_str() {
        "gf2" => {
            let rho = sg::StrongRho::new(&curve);
            run(&mode, &args, curve, rho, "gf2", process_started);
        }
        "wide" => {
            let g = RawPointG::<u128>::from_binary_wide(curve.generator());
            let rho = StrongRhoG::<WideGf2, u64>::from_parts(WideGf2::new(&curve.curve.irreducible), u128::from(curve.a), r, lambda, g);
            run(&mode, &args, curve, rho, "wide", process_started);
        }
        "fold" => {
            let g = RawPointG::<u128>::from_binary_wide(curve.generator());
            let rho = StrongRhoG::<FoldField, u64>::from_parts(FoldField(Gf2_128::new(&curve.curve.irreducible)), u128::from(curve.a), r, lambda, g);
            run(&mode, &args, curve, rho, "fold", process_started);
        }
        other => panic!("unknown field {other}"),
    }
    let _ = point_words;
}

#[cfg(test)]
mod tests {
    use super::*;

    fn small_curves() -> Vec<KoblitzCurve> {
        [(0u8, 41u32), (1, 37), (0, 37)].iter().filter_map(|&(a, n)| KoblitzCurve::new(a, n)).collect()
    }

    /// With an empty table the generated solve is the library solve: same
    /// scalar, steps, walks and charges.
    #[test]
    fn empty_table_solve_is_the_library_solve() {
        for curve in small_curves() {
            let rho = sg::StrongRho::new(&curve);
            let r = rho.modulus();
            for (seed, d) in [(1u64, 12345u64), (2, r / 3), (3, r - 7)] {
                let q = rho.scalar_mul(rho.generator(), d);
                let mut c = StrongRhoCharges::default();
                let jumps = rho.jumps(jump_seed_of(seed), &mut c);
                let p = StrongRhoParams::default();
                let lib = rho.solve(q, &jumps, &mut StdRng::seed_from_u64(seed), &p, c).unwrap();
                let mut table = HashMap::new();
                let mut hit = true;
                let gen = rho
                    .solve_with_table(q, &jumps, &mut StdRng::seed_from_u64(seed), &p, c, &mut table, &mut hit)
                    .unwrap();
                assert_eq!((lib.scalar, lib.walk_steps, lib.walks, lib.charges), (gen.scalar, gen.walk_steps, gen.walks, gen.charges));
                assert!(!hit, "an empty table cannot give a precomputed hit");
                assert_eq!(gen.scalar, d);
            }
        }
    }

    /// Every stored point is distinguished, canonical and has the stored log;
    /// a rerun to the same round count gives the same table; online solves
    /// with the table recover planted scalars, mostly through table hits.
    #[test]
    fn precompute_is_exact_reproducible_and_online_uses_it() {
        let curve = KoblitzCurve::new(0, 41).unwrap();
        let rho = sg::StrongRho::new(&curve);
        let p = StrongRhoParams { lanes: 32, dp_bits: 4, ..StrongRhoParams::default() };
        let mut c = StrongRhoCharges::default();
        let jumps = rho.jumps(jump_seed_of(99), &mut c);
        let build = |rounds: u64| {
            let mut table = HashMap::new();
            let st = rho.bl_precompute(&jumps, &mut StdRng::seed_from_u64(5), &p, &mut table, &mut |st, _| st.rounds >= rounds);
            (table, st)
        };
        let (table, st) = build(65536);
        assert_eq!(st.rounds, 65536);
        assert_eq!(table.len() as u64, st.new_points);
        let (again, _) = build(65536);
        assert_eq!(table, again);
        for (&(tag, x, y), &(log, b)) in &table {
            let point = RawPointG::Affine { x, y };
            assert_eq!((tag, b), (1, 0));
            assert!(rho.bl_is_distinguished(point, 4) && rho.bl_is_canonical(point));
            assert_eq!(rho.scalar_mul(rho.generator(), log), point);
        }
        let mut hits = 0;
        let r = rho.modulus();
        for i in 0..64u64 {
            let d = (i * 7_919_993 + 11) % (r - 1) + 1;
            let q = rho.scalar_mul(rho.generator(), d);
            let mut t = table.clone();
            let mut hit = false;
            let out = rho.solve_with_table(q, &jumps, &mut StdRng::seed_from_u64(1000 + i), &p, c, &mut t, &mut hit).unwrap();
            assert_eq!(out.scalar, d);
            hits += hit as u32;
        }
        assert!(hits >= 62, "only {hits} of 64 online solves used the table");
    }
}
