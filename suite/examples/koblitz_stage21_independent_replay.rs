//! Independent finite replay of the Stage-21 factor base and exact pair oracle.

use serde_json::{json, Value};
use std::collections::{HashMap, HashSet};
use std::env;
use std::fs;

const N: u32 = 23;
const MASK: u32 = (1 << N) - 1;
const MOD_LOW: u32 = (1 << 5) | 1;
const FACTOR_DOMAIN: &[u8] = b"koblitz-stage21-factor-base-v1\0";
const PAIR_DOMAIN: &[u8] = b"koblitz-stage21-canonical-pairs-v1\0";

#[derive(Clone, Copy, Debug, Eq, Hash, PartialEq)]
struct Point {
    x: u32,
    y: u32,
}

fn fadd(a: u32, b: u32) -> u32 {
    a ^ b
}

fn fmul(mut a: u32, mut b: u32) -> u32 {
    let mut out = 0u32;
    while b != 0 {
        if b & 1 == 1 {
            out ^= a;
        }
        b >>= 1;
        let carry = a >> (N - 1);
        a = (a << 1) & MASK;
        if carry != 0 {
            a ^= MOD_LOW;
        }
    }
    out & MASK
}

fn fsquare(a: u32) -> u32 {
    fmul(a, a)
}

fn fpow(mut a: u32, mut exponent: u32) -> u32 {
    let mut out = 1u32;
    while exponent != 0 {
        if exponent & 1 == 1 {
            out = fmul(out, a);
        }
        a = fsquare(a);
        exponent >>= 1;
    }
    out
}

fn finv(a: u32) -> u32 {
    assert_ne!(a, 0);
    let inverse = fpow(a, (1 << N) - 2);
    assert_eq!(fmul(a, inverse), 1);
    inverse
}

fn ftrace(a: u32) -> u32 {
    let mut current = a;
    let mut out = a;
    for _ in 1..N {
        current = fsquare(current);
        out ^= current;
    }
    assert!(out <= 1);
    out
}

fn artin_schreier(a: u32) -> Option<u32> {
    if ftrace(a) != 0 {
        return None;
    }
    let mut current = a;
    let mut out = a;
    for _ in 0..((N - 1) / 2) {
        current = fsquare(fsquare(current));
        out ^= current;
    }
    assert_eq!(fsquare(out) ^ out, a);
    Some(out)
}

fn on_curve(point: Point) -> bool {
    fadd(fsquare(point.y), fmul(point.x, point.y)) == fadd(fmul(fsquare(point.x), point.x), 1)
}

fn pneg(point: Point) -> Point {
    Point {
        x: point.x,
        y: point.y ^ point.x,
    }
}

fn padd(left: Option<Point>, right: Option<Point>) -> Option<Point> {
    let (Some(left), Some(right)) = (left, right) else {
        return left.or(right);
    };
    let result = if left.x == right.x {
        if left.y ^ right.y == left.x || left.x == 0 {
            return None;
        }
        let slope = left.x ^ fmul(left.y, finv(left.x));
        let x = fsquare(slope) ^ slope;
        let y = fsquare(left.x) ^ fmul(slope ^ 1, x);
        Point { x, y }
    } else {
        let slope = fmul(left.y ^ right.y, finv(left.x ^ right.x));
        let x = fsquare(slope) ^ slope ^ left.x ^ right.x;
        let y = fmul(slope, left.x ^ x) ^ x ^ left.y;
        Point { x, y }
    };
    assert!(on_curve(result));
    Some(result)
}

fn points_with_x(x: u32) -> Vec<Point> {
    if x == 0 {
        return vec![Point { x: 0, y: 1 }];
    }
    let inverse = finv(x);
    let rhs = x ^ fsquare(inverse);
    let Some(z) = artin_schreier(rhs) else {
        return Vec::new();
    };
    let point = Point { x, y: fmul(x, z) };
    let other = pneg(point);
    assert!(point != other && on_curve(point) && on_curve(other));
    vec![point, other]
}

fn frobenius_power(mut value: u32, exponent: u32) -> u32 {
    for _ in 0..exponent {
        value = fsquare(value);
    }
    value
}

fn kernel_basis(exponents: &[u32]) -> Vec<u32> {
    let mut pivots: [Option<(u32, u32)>; N as usize] = [None; N as usize];
    let mut kernel = Vec::new();
    for bit in 0..N {
        let preimage = 1u32 << bit;
        let mut image = exponents.iter().fold(0u32, |acc, exponent| {
            acc ^ frobenius_power(preimage, *exponent)
        });
        let mut preimage_row = preimage;
        loop {
            if image == 0 {
                kernel.push(preimage_row);
                break;
            }
            let lead = 31 - image.leading_zeros();
            if let Some((pivot_image, pivot_preimage)) = pivots[lead as usize] {
                image ^= pivot_image;
                preimage_row ^= pivot_preimage;
            } else {
                pivots[lead as usize] = Some((image, preimage_row));
                break;
            }
        }
    }
    kernel
}

fn pack(point: Option<Point>) -> u64 {
    match point {
        None => 0,
        Some(point) => (((point.x as u64) << N) | point.y as u64) + 1,
    }
}

fn materialize_factor_base() -> Vec<Point> {
    let exponents = [0, 1, 2, 3, 4, 7, 10, 12];
    let basis = kernel_basis(&exponents);
    assert_eq!(basis.len(), 12);
    let mut xs = HashSet::with_capacity(1 << basis.len());
    for mask in 0usize..(1 << basis.len()) {
        let mut x = 0u32;
        for (index, value) in basis.iter().enumerate() {
            if (mask >> index) & 1 == 1 {
                x ^= value;
            }
        }
        assert_eq!(
            exponents
                .iter()
                .fold(0u32, |acc, exponent| acc ^ frobenius_power(x, *exponent)),
            0
        );
        xs.insert(x);
    }
    assert_eq!(xs.len(), 4096);
    let mut points = xs.into_iter().flat_map(points_with_x).collect::<Vec<_>>();
    points.sort_by_key(|point| pack(Some(*point)));
    points.dedup();
    assert_eq!(points.len(), 4281);
    points
}

fn required_u64(value: &Value, field: &str) -> Result<u64, String> {
    value
        .get(field)
        .and_then(Value::as_u64)
        .ok_or_else(|| format!("missing integer {field}"))
}

fn required_str<'a>(value: &'a Value, field: &str) -> Result<&'a str, String> {
    value
        .get(field)
        .and_then(Value::as_str)
        .ok_or_else(|| format!("missing string {field}"))
}

fn replay(path: &str) -> Result<Value, String> {
    let source: Value = serde_json::from_slice(&fs::read(path).map_err(|error| error.to_string())?)
        .map_err(|error| error.to_string())?;
    if source.get("schema").and_then(Value::as_str) != Some("koblitz_relation_yield_bridge.v1")
        || source.get("status").and_then(Value::as_str) != Some("complete")
    {
        return Err("unexpected Stage-21 input schema or status".into());
    }
    let predicate_hash = required_str(
        source.get("factor_base").ok_or("missing factor_base")?,
        "predicate_blake3",
    )?;
    let points = materialize_factor_base();
    let mut factor_hasher = blake3::Hasher::new();
    factor_hasher.update(FACTOR_DOMAIN);
    factor_hasher.update(predicate_hash.as_bytes());
    for point in &points {
        factor_hasher.update(&pack(Some(*point)).to_le_bytes());
    }
    let factor_hash = factor_hasher.finalize().to_hex().to_string();

    let canonical_pairs = points.len() as u64 * (points.len() as u64 + 1) / 2;
    let mut table = HashMap::with_capacity(5_600_000);
    let mut pair_hasher = blake3::Hasher::new();
    pair_hasher.update(PAIR_DOMAIN);
    let mut enumerated = 0u64;
    for left in 0..points.len() {
        for right in left..points.len() {
            let packed = pack(padd(Some(points[left]), Some(points[right])));
            pair_hasher.update(&(left as u32).to_le_bytes());
            pair_hasher.update(&(right as u32).to_le_bytes());
            pair_hasher.update(&packed.to_le_bytes());
            table.entry(packed).or_insert((left as u32, right as u32));
            enumerated += 1;
        }
    }
    assert_eq!(enumerated, canonical_pairs);
    let pair_hash = pair_hasher.finalize().to_hex().to_string();

    let rows = source
        .get("ordered_covariate_rows")
        .and_then(Value::as_array)
        .ok_or("missing ordered_covariate_rows")?;
    let mut arms: HashMap<&str, (u64, u64, u64)> = HashMap::new();
    let mut checked_witnesses = 0u64;
    for row in rows {
        let arm = required_str(row, "arm")?;
        let target = required_u64(row, "packed_target")?;
        let hit = table.contains_key(&target);
        if row.get("exact_pair_table_hit").and_then(Value::as_bool) != Some(hit) {
            return Err(format!("pair-table hit mismatch for {arm} target {target}"));
        }
        let counters = arms.entry(arm).or_insert((0, 0, 0));
        counters.0 += 1;
        counters.1 += u64::from(hit);
        if let Some(witness) = row
            .get("verified_witness_indices")
            .and_then(Value::as_array)
        {
            if witness.len() != 2 {
                return Err("witness does not have two indices".into());
            }
            let left = witness[0].as_u64().ok_or("invalid left witness")? as usize;
            let right = witness[1].as_u64().ok_or("invalid right witness")? as usize;
            if left > right
                || right >= points.len()
                || pack(padd(Some(points[left]), Some(points[right]))) != target
                || row.get("point_witness_verified").and_then(Value::as_bool) != Some(true)
            {
                return Err(format!("witness replay failed for {arm} target {target}"));
            }
            counters.2 += 1;
            checked_witnesses += 1;
        } else if row.get("point_witness_verified").is_some()
            && !row.get("point_witness_verified").unwrap().is_null()
        {
            return Err("row claims witness verification without indices".into());
        }
    }
    let exact = source
        .get("exact_pair_table")
        .ok_or("missing exact_pair_table")?;
    let expected_factor = required_str(
        source.get("factor_base").ok_or("missing factor_base")?,
        "factor_base_blake3",
    )?;
    let expected_pair = required_str(exact, "canonical_pair_transcript_blake3")?;
    if factor_hash != expected_factor
        || pair_hash != expected_pair
        || canonical_pairs != required_u64(exact, "canonical_pairs")?
        || enumerated != required_u64(exact, "enumerated_pairs")?
        || table.len() as u64 != required_u64(exact, "unique_target_entries")?
    {
        return Err("factor-base or canonical-pair replay differs from Stage-21".into());
    }
    let duplicate_pairs = canonical_pairs - table.len() as u64;
    if duplicate_pairs != required_u64(exact, "duplicate_pair_sums")? {
        return Err("duplicate pair count differs from Stage-21".into());
    }
    let arm_json = arms
        .into_iter()
        .map(|(name, (targets, hits, witnesses))| {
            (
                name.to_string(),
                json!({"targets":targets,"hits":hits,"verified_witnesses":witnesses}),
            )
        })
        .collect::<serde_json::Map<_, _>>();
    Ok(json!({
        "schema":"koblitz_stage28_independent_relation_yield_replay.v1",
        "status":"PASS",
        "implementation":"separate fixed-width finite-field and binary-curve implementation",
        "field":{"n":N,"modulus_low_terms":[0,5]},
        "factor_base":{"dimension":12,"abscissae":4096,"rational_points":points.len(),"factor_base_blake3":factor_hash},
        "pair_oracle":{"canonical_pairs":canonical_pairs,"enumerated_pairs":enumerated,"unique_target_entries":table.len(),"duplicate_pair_sums":duplicate_pairs,"canonical_pair_transcript_blake3":pair_hash},
        "rows":rows.len(),
        "checked_witnesses":checked_witnesses,
        "arms":arm_json,
        "factor_base_materialization_replayed":true,
        "canonical_pair_oracle_replayed":true,
        "witness_curve_readdition_replayed":true,
        "target_subgroup_enumerated":false,
        "discrete_log_labels_used":false,
        "scientific_measurement_admitted":"finite_public_synthetic_internal_replay_complete",
        "independent_external_reproduction_satisfied":false,
        "full_cost_gate_passed":false,
        "koblitz_index_calculus_sota":false
    }))
}

fn main() {
    let args = env::args().collect::<Vec<_>>();
    if args.len() != 2 {
        eprintln!("usage: koblitz_stage21_independent_replay <yield-result.json>");
        std::process::exit(2);
    }
    match replay(&args[1]) {
        Ok(result) => println!("{}", serde_json::to_string_pretty(&result).unwrap()),
        Err(error) => {
            eprintln!("stage28 replay: {error}");
            std::process::exit(1);
        }
    }
}
