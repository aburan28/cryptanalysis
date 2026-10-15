//! Derived for cryptanalysis experiments/koblitz-s23-tuned-rho-20261015 from
//! crypto 770f6a69 examples/n83_rho_optimization_eval.rs (A's tuned rho worker,
//! rT770). The only changes: the Koblitz curve is KoblitzCurve::new(a, n) for a
//! degree n <= 127 given on the command line (n = 83 still asserts the exact
//! legacy curve), the receipt reports that curve, and the unit tests are
//! dropped. The `fold` backend is the parent's Gf2_128 fold kernel, which
//! exists only for 64 < n <= 127; for n <= 64 it is the library's single-word
//! field `Gf2` (u64 words; pclmulqdq with fold reduction where the modulus
//! allows, else table reduction), the walk's own one-word field. The receipt's
//! `field_type` names which ran. The jump derivation, walk, configs and timer
//! boundaries are the parent's, so at n = 83 this worker takes rT770's steps.
//!
//! Usage: s23_strong_rho_eval <a> <n> <point.jsonl> <walk-seed> <config.json> [receipt.json]
//! The input must contain exactly one JSON array of two decimal coordinate
//! strings. No known-answer scalar or validation sidecar is accepted or opened.
//!
//! Curve/normal-basis/G-only-jump preparation is target independent. Online time
//! includes target membership/subgroup checks, Q-dependent walk starts, the
//! distinguished-point solve and a separate generic arithmetic scalar replay.
//! A strict config selects wide or fold field kernels and a bounded walk policy.
//! The production StrongRhoG algorithm is unchanged. All boundaries are explicit.
//! This worker does not certify hardware isolation or infer a speedup by itself.
#![recursion_limit = "256"]

use std::fs;
use std::io::Write;
use std::time::{Instant, SystemTime, UNIX_EPOCH};

use crypto_lib::binary_ecc::{BinaryPoint, F2mElement};
use crypto_lib::cryptanalysis::koblitz_index_calculus::KoblitzCurve;
use crypto_lib::cryptanalysis::koblitz_strong_rho::{
    RawPointG, RhoField, StrongRhoCharges, StrongRhoG, StrongRhoParams,
};
use crypto_lib::cryptanalysis::semaev_decomp::{Gf2, Gf2_128};
use crypto_lib::cryptanalysis::wide_gf2m::WideGf2;
use num_bigint::BigUint;
use num_traits::ToPrimitive;
use rand::{rngs::StdRng, SeedableRng};
use serde::Deserialize;
use serde_json::{json, Value};

#[derive(Clone, Copy, Debug, Deserialize)]
#[serde(rename_all = "lowercase")]
enum Backend {
    Wide,
    Fold,
}

impl Backend {
    fn name(self) -> &'static str {
        match self {
            Self::Wide => "wide",
            Self::Fold => "fold",
        }
    }
}

#[derive(Clone, Copy, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct Config {
    backend: Backend,
    lanes: usize,
    dp_bits: u32,
    escape_fruitless: bool,
    step_cap_factor: u64,
}

impl Config {
    fn parse(bytes: &[u8]) -> Result<Self, String> {
        let config: Self = serde_json::from_slice(bytes)
            .map_err(|error| format!("invalid strict config: {error}"))?;
        if ![16, 32, 64].contains(&config.lanes)
            || ![4, 6].contains(&config.dp_bits)
            || config.step_cap_factor != 2_000
        {
            return Err(
                "config requires lanes 16|32|64, dp_bits 4|6 and step_cap_factor 2000".into(),
            );
        }
        Ok(config)
    }

    fn params(self) -> StrongRhoParams {
        StrongRhoParams {
            lanes: self.lanes,
            dp_bits: self.dp_bits,
            escape_fruitless: self.escape_fruitless,
            step_cap_factor: self.step_cap_factor,
        }
    }

    fn as_json(self) -> Value {
        json!({
            "backend": self.backend.name(),
            "lanes": self.lanes,
            "dp_bits": self.dp_bits,
            "escape_fruitless": self.escape_fruitless,
            "step_cap_factor": self.step_cap_factor,
        })
    }
}

/// The IC producer's existing wide-field implementation, behind the same
/// RhoField contract. In particular, zeros remain zero in Montgomery inversion
/// and no replacement walk, canonicalization or scalar arithmetic is introduced.
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

/// A field word the walk can be built on: the one-word (`u64`, n <= 64) or
/// the two-word (`u128`) packing of a library point.
trait Lift: Sized + Copy {
    fn lift(point: &BinaryPoint) -> RawPointG<Self>;
    fn from_a(a: u8) -> Self;
}

impl Lift for u64 {
    fn lift(point: &BinaryPoint) -> RawPointG<u64> {
        RawPointG::<u64>::from_binary(point)
    }
    fn from_a(a: u8) -> u64 {
        u64::from(a)
    }
}

impl Lift for u128 {
    fn lift(point: &BinaryPoint) -> RawPointG<u128> {
        RawPointG::<u128>::from_binary_wide(point)
    }
    fn from_a(a: u8) -> u128 {
        u128::from(a)
    }
}

fn sha256(bytes: &[u8]) -> String {
    hex::encode(crypto_lib::hash::sha256(bytes))
}

fn arithmetic_kernel(backend: Backend) -> Value {
    #[cfg(target_arch = "x86_64")]
    let hardware = std::arch::is_x86_feature_detected!("pclmulqdq").then_some("pclmulqdq");
    #[cfg(target_arch = "aarch64")]
    let hardware = std::arch::is_aarch64_feature_detected!("aes").then_some("pmull");
    #[cfg(not(any(target_arch = "x86_64", target_arch = "aarch64")))]
    let hardware: Option<&str> = None;
    json!({
        "backend": backend.name(),
        "carryless_multiply": hardware.unwrap_or("portable"),
        "reduction": match backend {
            Backend::Wide => "sparse_xor_fold_loop",
            Backend::Fold if hardware.is_some() => "two_clmul_tail_folds",
            Backend::Fold => "byte_table_reduction",
        },
        "squaring": match backend {
            Backend::Wide => "multiply_self",
            Backend::Fold => "bit_spread_then_reduce",
        },
    })
}
const BASE_SNAPSHOT: &str = "a8194d616ed8c04489ec46177d369f1b1670360a";
const LEGACY_R: u64 = 8_569_786_107_849_059;
const LEGACY_G: [u128; 2] = [
    6_614_244_651_398_184_860_292_015,
    8_868_260_410_029_249_391_539_529,
];

fn parse_public_point(text: &str, n: u32) -> Result<[u128; 2], String> {
    let mut rows = text.lines().filter(|line| !line.trim().is_empty());
    let row = rows.next().ok_or("public point input is empty")?;
    if rows.next().is_some() {
        return Err("exactly one public point is required".into());
    }
    let strings: [String; 2] = serde_json::from_str(row)
        .map_err(|_| "input must be a JSON array of two decimal strings".to_owned())?;
    let x = strings[0].parse::<u128>().map_err(|_| "bad x coordinate")?;
    let y = strings[1].parse::<u128>().map_err(|_| "bad y coordinate")?;
    let bound = 1u128 << n;
    if x >= bound || y >= bound {
        return Err("coordinate is not a canonical field word".into());
    }
    Ok([x, y])
}

fn point_strings(point: &BinaryPoint) -> Result<[String; 2], String> {
    match point {
        BinaryPoint::Infinity => Err("affine point required".into()),
        BinaryPoint::Affine { x, y } => {
            Ok([x.to_biguint().to_string(), y.to_biguint().to_string()])
        }
    }
}

fn make_strong<F: RhoField>(
    curve: &KoblitzCurve,
    field: F,
) -> Result<StrongRhoG<F, u64>, String>
where
    F::E: Lift,
{
    let r = curve
        .subgroup_order
        .to_u64()
        .ok_or("subgroup scalar does not fit u64")?;
    let lambda = curve.lambda.to_u64().ok_or("lambda does not fit u64")?;
    Ok(StrongRhoG::from_parts(
        field,
        <F::E as Lift>::from_a(curve.a),
        r,
        lambda,
        <F::E as Lift>::lift(curve.generator()),
    ))
}

fn assert_legacy_curve(curve: &KoblitzCurve) -> Result<(), String> {
    if curve.n != 83
        || curve.a != 1
        || curve.curve.irreducible.low_terms != [0, 2, 4, 7]
        || curve.subgroup_order.to_u64() != Some(LEGACY_R)
        || curve.cofactor.to_u64() != Some(1_128_547_018)
        || point_strings(curve.generator())? != [LEGACY_G[0].to_string(), LEGACY_G[1].to_string()]
    {
        return Err("constructor does not match the exact legacy K600 curve and generator".into());
    }
    Ok(())
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

fn peak_rss_bytes() -> Option<u64> {
    // SAFETY: getrusage fills the initialized plain-data structure for this process.
    let mut usage: libc::rusage = unsafe { std::mem::zeroed() };
    if unsafe { libc::getrusage(libc::RUSAGE_SELF, &mut usage) } != 0 {
        return None;
    }
    let raw = u64::try_from(usage.ru_maxrss).ok()?;
    #[cfg(target_os = "macos")]
    {
        Some(raw)
    }
    #[cfg(not(target_os = "macos"))]
    {
        Some(raw.saturating_mul(1024))
    }
}

fn evaluate_backend<F: RhoField>(
    a: u8,
    n: u32,
    input: &str,
    seed: u64,
    config: Config,
    config_bytes: &[u8],
    field_type: &str,
    make_field: impl FnOnce(&KoblitzCurve) -> F,
) -> Result<(Value, bool), String>
where
    F::E: Lift,
{
    let process_started = Instant::now();
    let started_unix_ms = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|e| e.to_string())?
        .as_millis();
    let input_bytes = fs::read(input).map_err(|e| format!("read public point: {e}"))?;
    let input_text = std::str::from_utf8(&input_bytes).map_err(|_| "input is not UTF-8")?;
    let coordinates = parse_public_point(input_text, n)?;
    let input_blake3 = blake3::hash(&input_bytes).to_hex().to_string();

    let prepare_started = Instant::now();
    // This constructor is deliberately different from known_n83_k1(): that
    // helper uses modulus [0,1,2,45] and a different generator.
    let curve = KoblitzCurve::new(a, n).ok_or("curve construction failed")?;
    if n == 83 {
        assert_legacy_curve(&curve)?;
    }
    let exact_id = curve.curve_id();
    let field = make_field(&curve);
    let kernel = arithmetic_kernel(config.backend);
    let rho = make_strong(&curve, field)?;
    let mut setup_charges = StrongRhoCharges::default();
    // G-only jumps can be prepared before Q arrives. Walk-start RNG and jump
    // RNG domains are separate, both derived only from the declared seed.
    let mut jump_material = b"n83-exact-public-strong-jumps-v1\0".to_vec();
    jump_material.extend_from_slice(&seed.to_le_bytes());
    let digest = blake3::hash(&jump_material);
    let jump_seed = u64::from_le_bytes(digest.as_bytes()[..8].try_into().unwrap());
    let jumps = rho.jumps(jump_seed, &mut setup_charges);
    let prepare_ns = prepare_started.elapsed().as_nanos();
    let params = config.params();
    let mut rng = StdRng::seed_from_u64(seed);
    let predicted_step_cap = (rho.ideal_steps().ceil() as u64)
        .saturating_mul(params.step_cap_factor)
        .max(1_000_000);

    let online_started = Instant::now();
    let query_started = Instant::now();
    let q = BinaryPoint::Affine {
        x: F2mElement::from_biguint(&BigUint::from(coordinates[0]), n),
        y: F2mElement::from_biguint(&BigUint::from(coordinates[1]), n),
    };
    let on_curve = curve.curve.is_on_curve(&q);
    let in_subgroup = on_curve && curve.mul(&q, &curve.subgroup_order) == BinaryPoint::Infinity;
    let raw_q = <F::E as Lift>::lift(&q);
    let query_ns = query_started.elapsed().as_nanos();

    let walk_started = Instant::now();
    let outcome = if in_subgroup {
        rho.solve(raw_q, &jumps, &mut rng, &params, setup_charges)
    } else {
        None
    };
    let walk_ns = walk_started.elapsed().as_nanos();
    let validation_started = Instant::now();
    let recovered = outcome.as_ref().map(|value| value.scalar);
    let replay_verified =
        recovered.is_some_and(|d| curve.mul(curve.generator(), &BigUint::from(d)) == q);
    let validation_ns = validation_started.elapsed().as_nanos();
    let online_ns = online_started.elapsed().as_nanos();
    let phase_sum_ns = query_ns + walk_ns + validation_ns;
    let outcome_json = outcome.as_ref().map(|out| {
        json!({
            "walk_steps": out.walk_steps,
            "walks": out.walks,
            "fruitless_cycles": out.fruitless,
            "fruitless_escapes": out.escapes,
            "capped_walks": out.capped,
            "wasted_merges": out.wasted_merges,
            "table_entries": out.table_entries,
            "table_payload_lower_bound_bytes": out.table_entries * (1 + 2 * 16 + 2 * 8),
            "ideal_steps": out.ideal_steps,
            "automorphism_size": out.automorphisms,
            "charges_setup_and_solve": charges_json(out.charges),
        })
    });
    let status = if !in_subgroup {
        "REJECTED_PUBLIC_POINT"
    } else if outcome.is_none() {
        "UNKNOWN_STEP_CAP"
    } else if !replay_verified {
        "FAILED_SCALAR_REPLAY"
    } else {
        "PASS_VERIFIED_PUBLIC_TARGET"
    };
    let executable = std::env::current_exe().ok().and_then(|p| fs::read(p).ok());
    let source = include_bytes!("s23_strong_rho_eval.rs");
    let receipt = json!({
        "schema": "s23-strong-rho-evaluation/v1",
        "status": status,
        "run_id": format!("S23K{a}N{n}RhoOpt{}L{}DP{}E{}W{seed}Q{}", config.backend.name(), config.lanes, config.dp_bits, u8::from(config.escape_fruitless), &input_blake3[..12]),
        "canonical_candidate_id": null,
        "canonical_workload_id": null,
        "started_unix_ms": started_unix_ms,
        "record_class": "verified_answer_exploratory_wall",
        "host_isolation_receipt": null,
        "controlled_speedup": null,
        "worker_count": 1,
        "target_count": 1,
        "known_answer_input": false,
        "validation_sidecar_opened": false,
        "base_snapshot": BASE_SNAPSHOT,
        "compiled_source_revision": option_env!("N83_SOURCE_COMMIT"),
        "worker_source_blake3": blake3::hash(source).to_hex().to_string(),
        "worker_source_sha256": sha256(source),
        "compiled_source_sha256": {
            "examples/s23_strong_rho_eval.rs": sha256(source),
            "src/cryptanalysis/koblitz_strong_rho.rs": sha256(include_bytes!("../src/cryptanalysis/koblitz_strong_rho.rs")),
            "src/cryptanalysis/wide_gf2m.rs": sha256(include_bytes!("../src/cryptanalysis/wide_gf2m.rs")),
            "src/cryptanalysis/semaev_decomp.rs": sha256(include_bytes!("../src/cryptanalysis/semaev_decomp.rs")),
        },
        "optimization_backend": config.backend.name(),
        "optimization_config": config.as_json(),
        "config_input_sha256": sha256(config_bytes),
        "config_input_blake3": blake3::hash(config_bytes).to_hex().to_string(),
        "executable_blake3": executable.as_deref().map(|b| blake3::hash(b).to_hex().to_string()),
        "public_input_blake3": input_blake3,
        "public_input_sha256": sha256(&input_bytes),
        "reference_grade": "strong_configured_field_u64_scalar",
        "curve_id": exact_id.icv1,
        "curve_slug": exact_id.slug,
        "n": n,
        "a": a,
        "b": 1,
        "field_modulus_low_terms": curve.curve.irreducible.low_terms.clone(),
        "field_encoding": "polynomial words as canonical decimal strings",
        "subgroup_order": curve.subgroup_order.to_string(),
        "cofactor": curve.cofactor.to_string(),
        "lambda": rho.lambda().to_string(),
        "generator": point_strings(curve.generator())?,
        "public_target_q": [coordinates[0].to_string(), coordinates[1].to_string()],
        "published_q": [coordinates[0].to_string(), coordinates[1].to_string()],
        "target_on_curve": on_curve,
        "target_in_subgroup": in_subgroup,
        "recovered_scalar": recovered.map(|d| d.to_string()),
        "generic_scalar_replay_verified": replay_verified,
        "group_verified": replay_verified,
        "reference_group_validation": replay_verified,
        "arithmetic_kernel": kernel,
        "field_type": field_type,
        "walk_seed": seed,
        "jump_seed": jump_seed,
        "rho_policy": {
            "quotient": "signed_frobenius",
            "lanes": params.lanes,
            "distinguished_bits": params.dp_bits,
            "step_cap_factor": params.step_cap_factor,
            "step_cap": predicted_step_cap,
            "escape_fruitless": params.escape_fruitless,
            "jump_count": jumps.len(),
            "G_only_jumps_target_independent": true,
        },
        "preparation_ns_excluded": prepare_ns,
        "preparation_charges": charges_json(setup_charges),
        "online_interval": {
            "start_event": "before_public_target_membership_and_subgroup_validation",
            "stop_event": "after_generic_scalar_replay",
            "included_stages": ["target_validation", "walk_starts", "walk_and_collision", "generic_scalar_replay"],
            "excluded_stages": ["input_and_config_loading", "curve_normal_basis_G_only_jumps", "receipt_hashing", "receipt_serialization", "receipt_io"],
        },
        "online_phase_ns": {
            "target_query_and_validation": query_ns,
            "walk_and_collision": walk_ns,
            "generic_scalar_replay": validation_ns,
        },
        "online_phase_sum_ns": phase_sum_ns,
        "online_interval_ns": online_ns,
        "online_timer_boundary_residual_ns": online_ns.saturating_sub(phase_sum_ns),
        "online_ms": online_ns as f64 / 1_000_000.0,
        "online_total_ms": online_ns as f64 / 1_000_000.0,
        "target_ms": online_ns as f64 / 1_000_000.0,
        "outcome": outcome_json,
        "failure_counter_note": if outcome.is_none() {
            Some("library solve returns no outcome on cap; actual steps/charges are unavailable, not zero")
        } else { None },
        "peak_rss_bytes": peak_rss_bytes(),
        "peak_rss_source": "getrusage RUSAGE_SELF ru_maxrss; platform-scaled bytes",
        "process_ns_before_receipt_io": process_started.elapsed().as_nanos(),
        "claim_boundary": "one public synthetic target on K_a over GF(2^n); answer correctness and the online interval of this worker; no admitted speedup by itself",
    });
    Ok((receipt, replay_verified))
}

fn evaluate(a: u8, n: u32, input: &str, seed: u64, config_path: &str) -> Result<(Value, bool), String> {
    let config_bytes = fs::read(config_path).map_err(|error| format!("read config: {error}"))?;
    let config = Config::parse(&config_bytes)?;
    match config.backend {
        Backend::Wide => evaluate_backend(a, n, input, seed, config, &config_bytes, "WideGf2", |curve| {
            WideGf2::new(&curve.curve.irreducible)
        }),
        Backend::Fold if n > 64 => {
            evaluate_backend(a, n, input, seed, config, &config_bytes, "Gf2_128 fold", |curve| {
                FoldField(Gf2_128::new(&curve.curve.irreducible))
            })
        }
        Backend::Fold => evaluate_backend(a, n, input, seed, config, &config_bytes, "Gf2 one-word", |curve| {
            Gf2::new(&curve.curve.irreducible)
        }),
    }
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if !(6..=7).contains(&args.len()) {
        eprintln!("usage: s23_strong_rho_eval <a> <n> <one-point.jsonl> <walk-seed> <config.json> [receipt.json]");
        std::process::exit(2);
    }
    let curve_args = args[1]
        .parse::<u8>()
        .map_err(|_| "a must be 0 or 1".to_owned())
        .and_then(|a| {
            let n = args[2].parse::<u32>().map_err(|_| "n must be a degree".to_owned())?;
            if a > 1 || !(3..=127).contains(&n) {
                return Err("need a in {0, 1} and 3 <= n <= 127".to_owned());
            }
            Ok((a, n))
        });
    let result = curve_args.and_then(|(a, n)| {
        args[4]
            .parse::<u64>()
            .map_err(|_| "walk seed must be u64".to_owned())
            .and_then(|seed| evaluate(a, n, &args[3], seed, &args[5]))
    });
    let (receipt, success) = match result {
        Ok(value) => value,
        Err(message) => (
            json!({"schema":"s23-strong-rho-evaluation/v1", "status":"INPUT_OR_SETUP_FAILURE", "error":message}),
            false,
        ),
    };
    let bytes = format!("{}\n", serde_json::to_string(&receipt).unwrap());
    if let Some(path) = args.get(6) {
        let write_result = fs::OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(path)
            .and_then(|mut file| file.write_all(bytes.as_bytes()));
        if let Err(error) = write_result {
            eprintln!("receipt write failed: {error}");
            std::process::exit(2);
        }
    }
    print!("{bytes}");
    if !success {
        std::process::exit(1);
    }
}
