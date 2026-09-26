//! What does the cached preprocessing actually cost?
//!
//! `algebra_cache` memoizes `DecompositionTemplate::build` on the
//! `Preprocessing` layer. Whether that is worth a Redis round trip -- let
//! alone a durable S3 tier under it -- depends on how the build compares with
//! what a cache hit itself has to pay, which is not nothing: the envelope is
//! `serde_json` with a blake3 checksum over a JSON payload, so a hit decodes
//! twice and hashes once before it can return.
//!
//! So this times four things per parameter point, in the same unit:
//!
//!   build      `DecompositionTemplate::build` -- what a miss recomputes
//!   encode     payload + blake3 + envelope -- what a miss then stores
//!   decode     envelope parse + blake3 verify + payload parse -- what a HIT pays
//!   instantiate `template.instantiate(x_r)` -- per target, never cached
//!
//! `decode` is the whole hit path and not just the payload parse, because
//! `AlgebraCache::memoize` runs it on a REDIS hit: those bytes crossed a wire,
//! so the envelope and its checksum still apply. A local hit no longer pays it
//! -- the in-process layer holds decoded values and clones them. The envelope is
//! also measured as stored -- a JSON object holding the payload as an escaped
//! JSON string -- since that escaping, not the payload, is what `max_value`
//! actually compares against.
//!
//! A cache is worth having when build >> decode + the network hop. A durable
//! tier under Redis is worth having when build is expensive enough that
//! refilling a flushed cluster from S3 beats recomputing.
//!
//! Wall-clock is the right unit here and only here: the question is about
//! cache-tier engineering, not about an attack's cost. No operation counts,
//! no ratio to a boundary, and nothing this prints is a speedup claim.
//!
//! With `--features redis-cache` and `IC_TEST_REDIS_URL` set (the same
//! variable `.github/workflows/polynomial-reuse.yml` uses), it also times the
//! real `AlgebraCache::memoize` on a miss, a local hit and a Redis hit, so the
//! network hop is measured rather than assumed. A loopback Redis is the best
//! case for that hop -- a cross-AZ ElastiCache is strictly worse -- so treat
//! those figures as a lower bound on what the remote tier costs in production.
//!
//!     cargo run --release --example preprocessing_cost
//!     cargo run --release --example preprocessing_cost -- --json
//!     IC_TEST_REDIS_URL=redis://127.0.0.1:6399/0 \
//!       cargo run --release --features redis-cache --example preprocessing_cost
//!
//! Measured 2026-09-21, release, rustc 1.90.0, against a loopback Redis, on a
//! 4-core x86_64 container; three runs, medians of 11 within each. Every figure
//! is scoped to these parameters on that machine:
//!
//!   * build spans 69 us (n=9) to 9.4 ms (n=61) over the whole feasible space.
//!     Nothing here is expensive in absolute terms. Per point it is steady --
//!     n=9/ell=9 gave 338, 339, 342 us across the three runs -- so the spread
//!     below is between machines, not between runs.
//!   * A local hit costs 3.7 us (n=9) to 167 us (n=61), which is 54x-91x
//!     cheaper than rebuilding. Before the in-process layer held decoded
//!     values it stored bytes and re-parsed on every hit, costing 266 us to
//!     3.8 ms -- only about 1x-3x cheaper than a rebuild, so it returned most
//!     of what it saved.
//!   * Against loopback Redis, over a held connection, a remote hit runs
//!     1.1x-1.4x the cost of just rebuilding at n=9/ell=9, about break-even at
//!     n=31/ell=11 (1.03x-1.13x), 0.8x-1.0x at n=41/ell=7, and 0.43x-0.47x at
//!     n=61/ell=1. Cross-AZ is strictly worse than loopback.
//!   * The largest artifact stored is 1.92 MB against a 4 MB `max_value`.
//!
//! So a durable tier under Redis is not warranted for this layer: an S3 GET is
//! tens of milliseconds and the whole build is at most 9.4 ms. The one
//! artifact that was expensive, a full parametric Gröbner basis, is priced by
//! `gb_probe.rs`; its `Parameterized` cache was removed after it cost more to
//! build than solving every target it could replace.
//!
//! Superseded figures, kept because deleting them hides how much the method
//! mattered. Two bugs were found in review, both fixed above:
//!
//!   * Remote hits were sampled on a fresh `AlgebraCache` each time, so every
//!     sample paid a TCP handshake a production hit never pays. n=9/ell=9 read
//!     1.92x the cost of rebuilding; over a held connection it is 1.1x-1.4x.
//!     The handshake was most of that column at the small end.
//!   * An n=9/ell=18 row was reported that cannot exist: `z^k` vanishes for
//!     k >= n, so nine of those eighteen basis elements were the zero element
//!     and the layout was degenerate. `ell` is now capped at `n` as well.
//!
//! A third correction is about provenance rather than method: 45 us-6.2 ms was
//! recorded here from a different container than the header named. The numbers
//! above are this machine's. Between the two, build moves by about half while
//! the ordering and the conclusion do not -- which is the reason to quote a
//! machine with every figure.

use cryptanalysis_suite::binary_ecc::F2mElement;
use cryptanalysis_suite::cryptanalysis::koblitz_groebner::{FieldStructure, MAX_VARS};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::find_irreducible;
use cryptanalysis_suite::cryptanalysis::polynomial_reuse::DecompositionTemplate;
use num_bigint::BigUint;
use std::hint::black_box;
use std::time::Instant;

/// The repository's own paired-repetition count, from
/// `research/f4_linear_algebra_20260914/contract.json`.
const REPS: usize = 11;
const WARMUP: usize = 3;

fn fe(x: u64, n: u32) -> F2mElement {
    F2mElement::from_biguint(&BigUint::from(x), n)
}

/// Median of a sample, plus its extremes. Median rather than mean: one
/// scheduler interruption should not become the headline number.
fn summarize(mut ns: Vec<u128>) -> (u128, u128, u128) {
    ns.sort_unstable();
    (ns[ns.len() / 2], ns[0], ns[ns.len() - 1])
}

fn time<T>(reps: usize, mut f: impl FnMut() -> T) -> (u128, u128, u128) {
    for _ in 0..WARMUP {
        black_box(f());
    }
    let mut samples = Vec::with_capacity(reps);
    for _ in 0..reps {
        let start = Instant::now();
        black_box(f());
        samples.push(start.elapsed().as_nanos());
    }
    summarize(samples)
}

/// Same shape as the private `algebra_cache::Envelope`, so the bytes match.
#[derive(serde::Serialize, serde::Deserialize)]
struct Envelope {
    key: String,
    payload: String,
    checksum: String,
}

/// `AlgebraCache::local` default.
const MAX_VALUE: usize = 4 * 1024 * 1024;

struct Row {
    n: u32,
    ell: usize,
    m: usize,
    n_vars: usize,
    bytes: usize,
    envelope_bytes: usize,
    build_ns: (u128, u128, u128),
    encode_ns: (u128, u128, u128),
    decode_ns: (u128, u128, u128),
    inst_ns: (u128, u128, u128),
}

fn measure(n: u32, ell: usize, m: usize) -> Option<Row> {
    let irr = find_irreducible(n)?;
    let st = FieldStructure::new(n, &irr);
    let basis: Vec<_> = (0..ell).map(|k| fe(1u64 << k, n)).collect();
    let b = fe(1, n);

    // Feasibility first: build returns None past MAX_VARS or n > 64.
    let template = DecompositionTemplate::build(&basis, &b, m, &st)?;
    let n_vars = template.n_vars;

    let payload = serde_json::to_string(&template).ok()?;
    let bytes = payload.len();
    let key = format!(
        "ic:v3:index-calculus:preprocessing:fingerprint:{}",
        "0".repeat(64)
    );
    let stored = serde_json::to_vec(&Envelope {
        key: key.clone(),
        payload: payload.clone(),
        checksum: blake3::hash(payload.as_bytes()).to_hex().to_string(),
    })
    .ok()?;
    let envelope_bytes = stored.len();
    let x_r = fe(0x5555_5555_5555_5555 & ((1u128 << n) - 1) as u64, n);

    let build_ns = time(REPS, || DecompositionTemplate::build(&basis, &b, m, &st));
    let encode_ns = time(REPS, || {
        // Exactly what a miss stores.
        let p = serde_json::to_string(&template).unwrap();
        let c = blake3::hash(p.as_bytes()).to_hex().to_string();
        serde_json::to_vec(&Envelope {
            key: key.clone(),
            payload: p,
            checksum: c,
        })
        .unwrap()
    });
    let decode_ns = time(REPS, || {
        // Exactly what a hit does -- local or remote -- before returning.
        let e: Envelope = serde_json::from_slice(&stored).unwrap();
        assert!(e.checksum == blake3::hash(e.payload.as_bytes()).to_hex().to_string());
        serde_json::from_str::<DecompositionTemplate>(&e.payload).unwrap()
    });
    let inst_ns = time(REPS, || template.instantiate(&x_r));

    Some(Row {
        n,
        ell,
        m,
        n_vars,
        bytes,
        envelope_bytes,
        build_ns,
        encode_ns,
        decode_ns,
        inst_ns,
    })
}

fn us(ns: u128) -> f64 {
    ns as f64 / 1000.0
}

/// The real cache path, end to end, at one parameter point.
#[cfg(feature = "redis-cache")]
fn redis_round_trip(n: u32, ell: usize, m: usize, url: &str) -> Option<(u128, u128, u128, usize)> {
    use cryptanalysis_suite::cryptanalysis::algebra_cache::{AlgebraCache, Layer};
    use cryptanalysis_suite::cryptanalysis::polynomial_reuse::template_key;

    let irr = find_irreducible(n)?;
    let st = FieldStructure::new(n, &irr);
    let basis: Vec<_> = (0..ell).map(|k| fe(1u64 << k, n)).collect();
    let b = fe(1, n);
    let key = template_key(&basis, &b, m, &st);
    let build = || DecompositionTemplate::build(&basis, &b, m, &st);

    // Miss: builds, encodes, and writes through to Redis. The connection is
    // opened first for the same reason the hit loop below does it: `remote`
    // connects lazily, so an unwarmed first call folds a handshake into this
    // column too, and a production miss reuses the connection like any other.
    let mut c = AlgebraCache::local(256 * 1024 * 1024)
        .with_redis(url)
        .ok()?;
    black_box(c.memoize::<u8>(
        Layer::Preprocessing,
        format!("warm:{n}:{ell}:{m}").as_bytes(),
        || Some(0u8),
    ));
    let miss = {
        let start = Instant::now();
        black_box(c.memoize::<DecompositionTemplate>(Layer::Preprocessing, &key, build));
        start.elapsed().as_nanos()
    };

    // Local hit: same instance, value already in the in-process layer.
    let mut local = Vec::new();
    for _ in 0..REPS {
        let start = Instant::now();
        black_box(c.memoize::<DecompositionTemplate>(Layer::Preprocessing, &key, build));
        local.push(start.elapsed().as_nanos());
    }

    // Redis hit: empty local layer, value in Redis. A zero-byte local layer
    // retains nothing, so every lookup on this instance is served by Redis, and
    // the one untimed lookup opens the connection `remote` makes lazily -- the
    // production cache is thread-local and keeps it, so a steady-state hit is
    // GETRANGE plus decode, not a handshake.
    let mut cold = AlgebraCache::local(0).with_redis(url).ok()?;
    black_box(cold.memoize::<DecompositionTemplate>(Layer::Preprocessing, &key, build));
    let mut remote = Vec::new();
    for _ in 0..REPS {
        let before = cold.stats[0].redis_hits;
        let start = Instant::now();
        black_box(cold.memoize::<DecompositionTemplate>(Layer::Preprocessing, &key, build));
        remote.push(start.elapsed().as_nanos());
        if cold.stats[0].redis_hits == before {
            return None; // not actually served from Redis; do not report it
        }
    }
    let stored = serde_json::to_string(&build()?).ok()?.len();
    Some((miss, summarize(local).0, summarize(remote).0, stored))
}

fn main() {
    let json = std::env::args().any(|a| a == "--json");

    // m = 3 everywhere in docs/ic/params; n from the same files. n_vars is
    // m*ell + (m-2)*n and must stay within MAX_VARS, which is what bounds ell
    // -- except at n=9, where the field does: a basis of F_{2^n} has at most n
    // elements, and `fe(1 << k, n)` masks anything at or above bit n to zero.
    let degrees = [9u32, 31, 37, 39, 41, 53, 61];
    let mut rows = Vec::new();

    for &n in &degrees {
        let m = 3usize;
        let max_ell = ((MAX_VARS.saturating_sub(n as usize)) / m).min(n as usize);
        if max_ell == 0 {
            continue;
        }
        // Smallest, midpoint and the largest ell the layout allows.
        let mut ells = vec![1usize, max_ell.div_ceil(2), max_ell];
        ells.sort_unstable();
        ells.dedup();
        for ell in ells {
            if let Some(row) = measure(n, ell, m) {
                rows.push(row);
            }
        }
    }

    // Summand count, held at one field, for the shape of the m dependence.
    for m in [2usize, 3, 4, 5] {
        let n = 31u32;
        let max_ell = (MAX_VARS.saturating_sub((m - 2) * n as usize)) / m;
        if max_ell == 0 {
            continue;
        }
        if let Some(row) = measure(n, max_ell.min(4), m) {
            rows.push(row);
        }
    }

    if json {
        let out: Vec<_> = rows
            .iter()
            .map(|r| {
                serde_json::json!({
                    "n": r.n, "ell": r.ell, "m": r.m, "n_vars": r.n_vars,
                    "payload_bytes": r.bytes,
                    "envelope_bytes": r.envelope_bytes,
                    "over_max_value": r.envelope_bytes > MAX_VALUE,
                    "build_ns_median": r.build_ns.0,
                    "build_ns_min": r.build_ns.1, "build_ns_max": r.build_ns.2,
                    "encode_ns_median": r.encode_ns.0,
                    "decode_ns_median": r.decode_ns.0,
                    "instantiate_ns_median": r.inst_ns.0,
                })
            })
            .collect();
        println!(
            "{}",
            serde_json::to_string_pretty(&serde_json::json!({
                "reps": REPS,
                "max_vars": MAX_VARS,
                "rows": out,
            }))
            .unwrap()
        );
        return;
    }

    println!(
        "DecompositionTemplate::build and one cache round trip, medians of {REPS} \
         (min-max in brackets), microseconds\n"
    );
    println!(
        "{:>4} {:>4} {:>3} {:>7} {:>9} {:>10}  {:>22} {:>12} {:>22} {:>12}",
        "n",
        "ell",
        "m",
        "n_vars",
        "payload",
        "stored",
        "build",
        "encode",
        "decode (a HIT pays)",
        "instantiate"
    );
    for r in &rows {
        println!(
            "{:>4} {:>4} {:>3} {:>7} {:>9} {:>10}  {:>10.1} [{:>5.1}-{:>5.1}] {:>12.1} {:>10.1} [{:>5.1}-{:>5.1}] {:>12.1}{}",
            r.n, r.ell, r.m, r.n_vars, r.bytes, r.envelope_bytes,
            us(r.build_ns.0), us(r.build_ns.1), us(r.build_ns.2),
            us(r.encode_ns.0),
            us(r.decode_ns.0), us(r.decode_ns.1), us(r.decode_ns.2),
            us(r.inst_ns.0),
            if r.envelope_bytes > MAX_VALUE { "  OVER max_value: never cached" } else { "" },
        );
    }

    println!("\nbuild / decode -- above 1, the cache saves work; below 1, a hit costs more than recomputing:");
    for r in &rows {
        println!(
            "  n={:<3} ell={:<3} m={}  {:>8.2}x",
            r.n,
            r.ell,
            r.m,
            r.build_ns.0 as f64 / r.decode_ns.0.max(1) as f64
        );
    }

    #[cfg(feature = "redis-cache")]
    if let Ok(url) = std::env::var("IC_TEST_REDIS_URL") {
        println!(
            "\nThe real AlgebraCache::memoize against {} -- medians of {REPS}, microseconds.",
            url.split('@').next_back().unwrap_or("redis")
        );
        println!("Loopback, so the remote column is a LOWER BOUND on a cross-AZ ElastiCache.\n");
        println!(
            "{:>4} {:>4} {:>3} {:>10}  {:>12} {:>12} {:>12}   {:>16}",
            "n", "ell", "m", "payload", "miss", "local hit", "redis hit", "redis hit / build"
        );
        for &(n, ell, m) in &[
            (9u32, 9usize, 3usize),
            (31, 11, 3),
            (41, 7, 3),
            (53, 3, 3),
            (61, 1, 3),
        ] {
            let built = rows.iter().find(|r| r.n == n && r.ell == ell && r.m == m);
            match redis_round_trip(n, ell, m, &url) {
                Some((miss, local, remote, bytes)) => println!(
                    "{:>4} {:>4} {:>3} {:>10}  {:>12.1} {:>12.1} {:>12.1}   {:>15.2}x",
                    n,
                    ell,
                    m,
                    bytes,
                    us(miss),
                    us(local),
                    us(remote),
                    built
                        .map(|r| remote as f64 / r.build_ns.0.max(1) as f64)
                        .unwrap_or(f64::NAN),
                ),
                None => println!("{n:>4} {ell:>4} {m:>3}  not served from Redis; not reported"),
            }
        }
    }

    // n = 131 is the ECC2K-130 field and is outside this path entirely.
    let unreachable = find_irreducible(131)
        .map(|irr| {
            let st = FieldStructure::new(131, &irr);
            DecompositionTemplate::build(&[fe(1, 131)], &fe(1, 131), 3, &st).is_none()
        })
        .unwrap_or(true);
    println!(
        "\nn=131 (ECC2K-130) rejected by this path: {unreachable} \
         (build refuses n > 64; MAX_VARS = {MAX_VARS})"
    );
}
