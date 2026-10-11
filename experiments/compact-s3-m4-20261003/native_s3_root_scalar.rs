//! Bounded four-leaf S3 root-index search on the frozen Q1301/Q1325 inputs.
//!
//! This is a point-decomposition stage, not a complete index-calculus solve.
//! Index construction is target independent. The query samples one global
//! Frobenius orientation per indexed pair state and charges every attempt.

use crypto_lib::binary_ecc::IrreduciblePoly;
use crypto_lib::cryptanalysis::semaev_decomp::{Gf2, Gf2_128};
use serde_json::{json, Value};
use std::env;
use std::fs;
use std::time::Instant;

trait Field {
    fn degree(&self) -> u32;
    fn mul(&self, left: u128, right: u128) -> u128;
    fn sqr(&self, value: u128) -> u128;
    fn inv(&self, value: u128) -> u128;
}

impl Field for Gf2 {
    fn degree(&self) -> u32 { self.n }
    #[inline(always)]
    fn mul(&self, left: u128, right: u128) -> u128 {
        Gf2::mul(self, left as u64, right as u64) as u128
    }
    #[inline(always)]
    fn sqr(&self, value: u128) -> u128 {
        Gf2::sqr(self, value as u64) as u128
    }
    #[inline(always)]
    fn inv(&self, value: u128) -> u128 {
        Gf2::inv(self, value as u64) as u128
    }
}

impl Field for Gf2_128 {
    fn degree(&self) -> u32 { self.n }
    #[inline(always)]
    fn mul(&self, left: u128, right: u128) -> u128 {
        Gf2_128::mul(self, left, right)
    }
    #[inline(always)]
    fn sqr(&self, value: u128) -> u128 {
        Gf2_128::sqr(self, value)
    }
    #[inline(always)]
    fn inv(&self, value: u128) -> u128 {
        Gf2_128::inv(self, value)
    }
}

#[derive(Clone, Copy, Default)]
struct Ops {
    mul: u64,
    sqr: u64,
    inv: u64,
    s3_calls: u64,
    basis_conversions: u64,
    canonical_rotations: u64,
    point_lifts: u64,
    point_adds: u64,
    relation_candidates: u64,
}

impl Ops {
    fn minus(self, prior: Self) -> Self {
        Self {
            mul: self.mul - prior.mul,
            sqr: self.sqr - prior.sqr,
            inv: self.inv - prior.inv,
            s3_calls: self.s3_calls - prior.s3_calls,
            basis_conversions: self.basis_conversions - prior.basis_conversions,
            canonical_rotations: self.canonical_rotations - prior.canonical_rotations,
            point_lifts: self.point_lifts - prior.point_lifts,
            point_adds: self.point_adds - prior.point_adds,
            relation_candidates: self.relation_candidates - prior.relation_candidates,
        }
    }
    fn value(self) -> Value {
        json!({
            "field_mul_calls": self.mul,
            "field_sqr_calls": self.sqr,
            "field_inv_calls": self.inv,
            "s3_root_calls": self.s3_calls,
            "basis_conversions": self.basis_conversions,
            "canonical_rotation_steps": self.canonical_rotations,
            "point_lifts": self.point_lifts,
            "point_add_calls": self.point_adds,
            "relation_candidates_checked": self.relation_candidates,
        })
    }
}

struct Counted<F: Field> {
    field: F,
    ops: Ops,
}

impl<F: Field> Counted<F> {
    #[inline(always)]
    fn mul(&mut self, left: u128, right: u128) -> u128 {
        self.ops.mul += 1;
        self.field.mul(left, right)
    }
    #[inline(always)]
    fn sqr(&mut self, value: u128) -> u128 {
        self.ops.sqr += 1;
        self.field.sqr(value)
    }
    #[inline(always)]
    fn inv(&mut self, value: u128) -> u128 {
        self.ops.inv += 1;
        self.field.inv(value)
    }
}

/// F2-linear map; the byte tables keep per-call conversion work bounded.
struct Linear {
    tables: Vec<[u128; 256]>,
}

impl Linear {
    fn from_images(images: &[u128]) -> Self {
        let chunks = (images.len() + 7) / 8;
        let mut tables = vec![[0u128; 256]; chunks];
        for (chunk, table) in tables.iter_mut().enumerate() {
            for byte in 1usize..256 {
                let low = byte & (byte - 1);
                let bit = chunk * 8 + byte.trailing_zeros() as usize;
                table[byte] = table[low] ^ images.get(bit).copied().unwrap_or(0);
            }
        }
        Self { tables }
    }
    #[inline(always)]
    fn apply(&self, value: u128) -> u128 {
        let mut result = 0;
        for (chunk, table) in self.tables.iter().enumerate() {
            result ^= table[((value >> (8 * chunk)) & 255) as usize];
        }
        result
    }
}

struct Cycle {
    n: u32,
    mask: u128,
    to_cycle: Linear,
    to_poly: Linear,
}

impl Cycle {
    fn from_bridge(bridge: &Value, n: u32) -> Self {
        let forward: Vec<u128> = bridge["onb_to_poly_basis_images"]
            .as_array().unwrap().iter().map(exact_integer).collect();
        let inverse: Vec<u128> = bridge["poly_to_onb_basis_images"]
            .as_array().unwrap().iter().map(exact_integer).collect();
        let positions: Vec<usize> = bridge["onb_gamma_frobenius_coordinate_cycle"]
            .as_array().unwrap().iter().map(|v| v.as_u64().unwrap() as usize).collect();
        assert_eq!(forward.len(), n as usize);
        assert_eq!(inverse.len(), n as usize);
        assert_eq!(positions.len(), n as usize);
        let to_cycle_images: Vec<u128> = inverse.iter().map(|&image| {
            positions.iter().enumerate().fold(0u128, |acc, (i, &position)| {
                acc | (((image >> position) & 1) << i)
            })
        }).collect();
        let to_poly_images: Vec<u128> = positions.iter().map(|&p| forward[p]).collect();
        let result = Self {
            n,
            mask: (1u128 << n) - 1,
            to_cycle: Linear::from_images(&to_cycle_images),
            to_poly: Linear::from_images(&to_poly_images),
        };
        for i in 0..n {
            assert_eq!(result.to_poly.apply(result.to_cycle.apply(1u128 << i)), 1u128 << i);
            assert_eq!(result.to_cycle.apply(result.to_poly.apply(1u128 << i)), 1u128 << i);
        }
        result
    }
    #[inline(always)]
    fn rotate(&self, value: u128, steps: u32) -> u128 {
        if steps == 0 { value } else {
            ((value << steps) | (value >> (self.n - steps))) & self.mask
        }
    }
    fn canonical(&self, value: u128, ops: &mut Ops) -> (u128, u32) {
        let mut best = value;
        let mut best_shift = 0;
        let mut current = value;
        for shift in 1..self.n {
            current = self.rotate(current, 1);
            ops.canonical_rotations += 1;
            if current < best {
                best = current;
                best_shift = shift;
            }
        }
        (best, best_shift)
    }
}

/// Quadratic S3 root evaluator with precomputed F2-linear half-trace.
struct S3 {
    square: Linear,
    half_trace: Linear,
    trace_mask: u128,
}

impl S3 {
    fn new<F: Field>(ctx: &mut Counted<F>, n: u32) -> Self {
        assert!(n % 2 == 1);
        let mut squares = Vec::with_capacity(n as usize);
        let mut traces = Vec::with_capacity(n as usize);
        let mut trace_mask = 0u128;
        for bit in 0..n {
            let e = 1u128 << bit;
            squares.push(ctx.sqr(e));
            let mut half = e;
            let mut power = e;
            for _ in 0..(n - 1) / 2 {
                let squared = ctx.sqr(power);
                power = ctx.sqr(squared);
                half ^= power;
            }
            traces.push(half);
            let mut tr = e;
            let mut p = e;
            for _ in 1..n {
                p = ctx.sqr(p);
                tr ^= p;
            }
            assert!(tr == 0 || tr == 1);
            if tr == 1 { trace_mask |= e; }
        }
        Self { square: Linear::from_images(&squares),
               half_trace: Linear::from_images(&traces), trace_mask }
    }
    #[inline(always)]
    fn roots<F: Field>(&self, ctx: &mut Counted<F>, left: u128,
                       right: u128) -> Option<[u128; 2]> {
        ctx.ops.s3_calls += 1;
        let a = self.square.apply(left ^ right);
        let p = ctx.mul(left, right);
        let ps = self.square.apply(p);
        if a == 0 {
            if left == 0 { return None; }
            let inverse = ctx.inv(p);
            let root = ctx.mul(ps ^ 1, inverse);
            return Some([root, root]);
        }
        if ps == 0 {
            let inverse = ctx.inv(a);
            let root = ctx.mul(1, inverse);
            let mut value = root;
            for _ in 0..(ctx.field_degree() - 1) { value = ctx.sqr(value); }
            return Some([value, value]);
        }
        let combined = ctx.mul(a, ps);
        let combined_inv = ctx.inv(combined);
        let ps_over_combined = ctx.mul(ps, combined_inv);
        let q = ctx.mul(p, ps_over_combined);
        let c = ps ^ 1;
        let ca = ctx.mul(c, a);
        let a_over_combined = ctx.mul(a, combined_inv);
        let d = ctx.mul(ca, a_over_combined);
        if (d & self.trace_mask).count_ones() & 1 == 1 { return None; }
        let first = ctx.mul(q, self.half_trace.apply(d));
        Some([first, first ^ q])
    }
}

impl<F: Field> Counted<F> {
    fn field_degree(&self) -> u32 { self.field.degree() }
}

type Point = Option<(u128, u128)>;

fn point_add<F: Field>(ctx: &mut Counted<F>, left: Point, right: Point) -> Point {
    ctx.ops.point_adds += 1;
    match (left, right) {
        (None, other) | (other, None) => other,
        (Some((x1, y1)), Some((x2, y2))) => {
            if x1 == x2 {
                if y1 ^ y2 == x1 { return None; }
                if x1 == 0 { return None; }
                let inverse = ctx.inv(x1);
                let lambda = x1 ^ ctx.mul(y1, inverse);
                let x3 = ctx.sqr(lambda) ^ lambda;
                let y3 = ctx.sqr(x1) ^ ctx.mul(lambda ^ 1, x3);
                return Some((x3, y3));
            }
            let inverse = ctx.inv(x1 ^ x2);
            let lambda = ctx.mul(y1 ^ y2, inverse);
            let x3 = ctx.sqr(lambda) ^ lambda ^ x1 ^ x2;
            let y3 = ctx.mul(lambda, x1 ^ x3) ^ x3 ^ y1;
            Some((x3, y3))
        }
    }
}

fn point_lifts<F: Field>(ctx: &mut Counted<F>, solver: &S3, x: u128) -> Option<[Point; 2]> {
    ctx.ops.point_lifts += 1;
    if x == 0 { return Some([Some((0, 1)), Some((0, 1))]); }
    let inverse = ctx.inv(x);
    let inverse_squared = ctx.sqr(inverse);
    let rhs = x ^ ctx.mul(1, inverse_squared);
    let u = solver.half_trace.apply(rhs);
    if (ctx.sqr(u) ^ u) != rhs { return None; }
    let y = ctx.mul(x, u);
    Some([Some((x, y)), Some((x, x ^ y))])
}

fn lift_relation<F: Field>(ctx: &mut Counted<F>, solver: &S3,
                           xs: [u128; 4], target: Point) -> Option<[Point; 4]> {
    ctx.ops.relation_candidates += 1;
    let p0 = point_lifts(ctx, solver, xs[0])?;
    let p1 = point_lifts(ctx, solver, xs[1])?;
    let p2 = point_lifts(ctx, solver, xs[2])?;
    let p3 = point_lifts(ctx, solver, xs[3])?;
    for a in p0 {
        for b in p1 {
            let ab = point_add(ctx, a, b);
            for c in p2 {
                let abc = point_add(ctx, ab, c);
                for d in p3 {
                    if point_add(ctx, abc, d) == target {
                        return Some([a, b, c, d]);
                    }
                }
            }
        }
    }
    None
}

#[derive(Clone)]
struct State {
    left: usize,
    right: usize,
    relative: usize,
    roots_cycle: [u128; 2],
}

/// Open-addressing root table. Separate key/value arrays avoid HashMap's
/// per-entry control bytes, padding, and randomized hasher on this hot path.
struct RootTable {
    keys: Vec<u128>,
    values: Vec<u64>,
    len: usize,
    insert_probes: u64,
    lookup_probes: u64,
    rehash_probes: u64,
}

impl RootTable {
    fn new(expected_states: usize) -> Self {
        let slots = expected_states.saturating_mul(3).div_ceil(2)
            .max(16).next_power_of_two();
        Self {
            keys: vec![u128::MAX; slots],
            values: vec![0; slots],
            len: 0,
            insert_probes: 0,
            lookup_probes: 0,
            rehash_probes: 0,
        }
    }

    #[inline(always)]
    fn slot(key: u128, mask: usize) -> usize {
        let mut value = key as u64 ^ ((key >> 64) as u64).rotate_left(27);
        value ^= value >> 30;
        value = value.wrapping_mul(0xbf58_476d_1ce4_e5b9);
        value ^= value >> 27;
        value = value.wrapping_mul(0x94d0_49bb_1331_11eb);
        (value ^ (value >> 31)) as usize & mask
    }

    fn grow(&mut self) {
        let slots = self.keys.len() * 2;
        let old_keys = std::mem::replace(&mut self.keys, vec![u128::MAX; slots]);
        let old_values = std::mem::replace(&mut self.values, vec![0; slots]);
        let mask = slots - 1;
        for (key, value) in old_keys.into_iter().zip(old_values) {
            if key == u128::MAX { continue; }
            let mut slot = Self::slot(key, mask);
            loop {
                self.rehash_probes += 1;
                if self.keys[slot] == u128::MAX {
                    self.keys[slot] = key;
                    self.values[slot] = value;
                    break;
                }
                slot = (slot + 1) & mask;
            }
        }
    }

    fn insert_if_absent(&mut self, key: u128, value: u64) {
        assert_ne!(key, u128::MAX);
        if self.len * 4 >= self.keys.len() * 3 { self.grow(); }
        let mask = self.keys.len() - 1;
        let mut slot = Self::slot(key, mask);
        loop {
            self.insert_probes += 1;
            if self.keys[slot] == u128::MAX {
                self.keys[slot] = key;
                self.values[slot] = value;
                self.len += 1;
                return;
            }
            if self.keys[slot] == key { return; }
            slot = (slot + 1) & mask;
        }
    }

    #[inline(always)]
    fn get(&mut self, key: u128) -> Option<u64> {
        let mask = self.keys.len() - 1;
        let mut slot = Self::slot(key, mask);
        loop {
            self.lookup_probes += 1;
            if self.keys[slot] == key { return Some(self.values[slot]); }
            if self.keys[slot] == u128::MAX { return None; }
            slot = (slot + 1) & mask;
        }
    }
}

fn gcd(mut left: u64, mut right: u64) -> u64 {
    while right != 0 { (left, right) = (right, left % right); }
    left
}

fn state_id(position: u64, total: u64, sampled: bool,
            origin: u64, step: u64) -> u64 {
    if sampled { ((origin as u128 + position as u128 * step as u128)
                  % total as u128) as u64 } else { position }
}

fn decode_state(id: u64, k: usize, n: usize) -> (usize, usize, usize) {
    let relative = id as usize % n;
    let pair = id as usize / n;
    (pair / k, pair % k, relative)
}

fn peak_rss_bytes() -> u64 {
    unsafe {
        let mut use_data: libc::rusage = std::mem::zeroed();
        assert_eq!(libc::getrusage(libc::RUSAGE_SELF, &mut use_data), 0);
        #[cfg(target_os = "macos")]
        { use_data.ru_maxrss as u64 }
        #[cfg(not(target_os = "macos"))]
        { (use_data.ru_maxrss as u64) * 1024 }
    }
}

fn exact_integer(value: &Value) -> u128 {
    value.as_str().map(|s| s.parse::<u128>().unwrap())
        .or_else(|| value.as_u64().map(u128::from))
        .unwrap_or_else(|| value.to_string().parse::<u128>().unwrap())
}

fn run<F: Field>(field: F, manifest: &Value, bridge: &Value,
                 reps: &[u128], state_cap: u64, memory_cap_bytes: u64) -> Value {
    let n = manifest["field_degree"].as_u64().unwrap() as u32;
    let k = reps.len();
    let total = (k as u64).checked_mul(k as u64).unwrap()
        .checked_mul(n as u64).unwrap();
    let state_cap = state_cap.min(total);
    let sampled = state_cap < total;
    let origin = 0x7e52_18ac_2026_1003u64 % total;
    let mut step = 0x9e37_79b9_7f4a_7c15u64 % total;
    if step == 0 { step = 1; }
    while gcd(step, total) != 1 { step += 1; }
    let target_array = manifest["target_poly_xy"].as_array().unwrap();
    let target_xy = (exact_integer(&target_array[0]), exact_integer(&target_array[1]));
    let target: Point = Some(target_xy);
    let orientations_per_state = manifest["orientations_per_state"]
        .as_u64().unwrap_or(1) as u32;
    assert!((1..=n).contains(&orientations_per_state));
    let mut ctx = Counted { field, ops: Ops::default() };
    let start = Instant::now();
    let cycle = Cycle::from_bridge(bridge, n);
    let solver = S3::new(&mut ctx, n);
    let generator_words = bridge["mapped_generator_poly"].as_array().unwrap();
    let generator_xy = (exact_integer(&generator_words[0]),
                        exact_integer(&generator_words[1]));
    let generator: Point = Some(generator_xy);
    for &(x, y) in &[generator_xy, target_xy] {
        let lhs = ctx.sqr(y) ^ ctx.mul(x, y);
        let x2 = ctx.sqr(x);
        let rhs = ctx.mul(x2, x) ^ 1;
        assert_eq!(lhs, rhs);
    }
    let control_sum = point_add(&mut ctx, generator, target);
    let control_x = control_sum.unwrap().0;
    let control_roots = solver.roots(&mut ctx, generator_xy.0, target_xy.0).unwrap();
    assert!(control_roots.contains(&control_x));
    let generator_lifts = point_lifts(&mut ctx, &solver, generator_xy.0).unwrap();
    assert!(generator_lifts.contains(&generator));
    let mut shifted = Vec::with_capacity(k * n as usize);
    for &rep in reps {
        let mut value = rep;
        for _ in 0..n {
            shifted.push(value);
            value = ctx.sqr(value);
        }
        assert_eq!(value, rep);
    }
    let setup_ns = start.elapsed().as_nanos();
    let setup_ops = ctx.ops;
    let mut states = Vec::with_capacity((state_cap / 2) as usize);
    let mut table = RootTable::new(state_cap as usize);
    let index_start = Instant::now();
    let mut examined = 0u64;
    let mut memory_exceeded = false;
    for position in 0..state_cap {
        let id = state_id(position, total, sampled, origin, step);
        let (left, right, relative) = decode_state(id, k, n as usize);
        let left_x = shifted[left * n as usize];
        let right_x = shifted[right * n as usize + relative];
        examined += 1;
        if let Some(roots) = solver.roots(&mut ctx, left_x, right_x) {
            let roots_cycle = roots.map(|root| {
                ctx.ops.basis_conversions += 1;
                cycle.to_cycle.apply(root)
            });
            let index = states.len();
            states.push(State { left, right, relative, roots_cycle });
            for &root_cycle in &roots_cycle {
                let (key, shift) = cycle.canonical(root_cycle, &mut ctx.ops);
                table.insert_if_absent(key, ((index as u64) << 7) | shift as u64);
            }
        }
        if position % 10_000 == 0 && peak_rss_bytes() > memory_cap_bytes {
            memory_exceeded = true;
            break;
        }
    }
    let index_ns = index_start.elapsed().as_nanos();
    let after_index_ops = ctx.ops;
    let index_ops = after_index_ops.minus(setup_ops);
    let after_index_rss = peak_rss_bytes();
    let index_table_probes = table.insert_probes + table.rehash_probes;
    let online_start = Instant::now();
    let mut scanned = 0u64;
    let mut oriented_states = 0u64;
    let mut partner_roots = 0u64;
    let mut table_hits = 0u64;
    let mut relation: Option<[Point; 4]> = None;
    let mut relation_xs = [0u128; 4];
    if !memory_exceeded {
        let target_seed = (target_xy.0 as u64) ^ ((target_xy.1 >> 64) as u64)
            ^ (target_xy.1 as u64).rotate_left(29) ^ 0xd6e8_feb8_6659_fd93;
        for (offset, state) in states.iter().enumerate() {
            scanned += 1;
            let mut seed = target_seed
                ^ (offset as u64).wrapping_mul(0x9e37_79b9_7f4a_7c15)
                ^ ((state.left as u64) << 32)
                ^ ((state.right as u64) << 16)
                ^ state.relative as u64;
            let first_shift = (splitmix64(&mut seed) % n as u64) as usize;
            for orientation in 0..orientations_per_state as usize {
                oriented_states += 1;
                let shift = (first_shift + orientation) % n as usize;
                let left_x = shifted[state.left * n as usize + shift];
                let right_x = shifted[state.right * n as usize
                    + (shift + state.relative) % n as usize];
                for &root_cycle in &state.roots_cycle {
                    let absolute = cycle.to_poly.apply(cycle.rotate(root_cycle, shift as u32));
                    ctx.ops.basis_conversions += 1;
                    if let Some(partners) = solver.roots(&mut ctx, absolute, target_xy.0) {
                        for partner in partners {
                            partner_roots += 1;
                            let partner_cycle = cycle.to_cycle.apply(partner);
                            ctx.ops.basis_conversions += 1;
                            let (key, partner_shift) =
                                cycle.canonical(partner_cycle, &mut ctx.ops);
                            if let Some(value) = table.get(key) {
                                table_hits += 1;
                                let other_index = (value >> 7) as usize;
                                let stored_shift = (value & 127) as u32;
                                let other = &states[other_index];
                                let shift2 = ((stored_shift + n - partner_shift) % n) as usize;
                                let xs = [left_x, right_x,
                                    shifted[other.left * n as usize + shift2],
                                    shifted[other.right * n as usize
                                        + (shift2 + other.relative) % n as usize]];
                                if let Some(points) = lift_relation(&mut ctx, &solver, xs, target) {
                                    relation = Some(points);
                                    relation_xs = xs;
                                    break;
                                }
                            }
                        }
                    }
                    if relation.is_some() { break; }
                }
                if relation.is_some() { break; }
            }
            if relation.is_some() { break; }
            if offset % 10_000 == 0 && peak_rss_bytes() > memory_cap_bytes {
                memory_exceeded = true;
                break;
            }
        }
    }
    let online_ns = online_start.elapsed().as_nanos();
    let target_ops = ctx.ops.minus(after_index_ops);
    let relation_json = relation.map(|points| {
        json!({
            "poly_points_xy_decimal": points.map(|p| {
                let (x, y) = p.unwrap();
                [x.to_string(), y.to_string()]
            }),
            "poly_x_words_decimal": relation_xs.map(|v| v.to_string()),
            "native_group_sum_verified": true,
        })
    });
    let (control_sum_x, control_sum_y) = control_sum.unwrap();
    let control_json = json!({
        "status": "PASS",
        "sum_poly_xy_decimal": [control_sum_x.to_string(), control_sum_y.to_string()],
        "sum_x_is_s3_root": true,
        "generator_lift_recovered": true,
    });
    json!({
        "kind": "bounded_native_s3_root_stage_run",
        "native_source_sha256": env!("NATIVE_S3_SOURCE_SHA256"),
        "cargo_manifest_sha256": env!("NATIVE_S3_BUILD_MANIFEST_SHA256"),
        "proposal_id": manifest["proposal_id"],
        "parent_factor_base_proposal_id": manifest["parent_factor_base_proposal_id"],
        "stage_protocol_sha256": manifest["stage_protocol_sha256"],
        "candidate_id": null,
        "run_id": null,
        "curve_id": manifest["curve_id"],
        "workload_id": manifest["workload_id"],
        "isogeny": "none",
        "field_degree": n,
        "actual_usable_points_B": manifest["actual_usable_points_B"],
        "folded_columns_K": k,
        "factor_base_enumerated_set_sha256": manifest["factor_base_enumerated_set_sha256"],
        "input_representatives_sha256": manifest["representatives_file_sha256"],
        "status": if relation_json.is_some() { "native_relation_found" }
                  else if memory_exceeded { "memory_cap_exceeded" }
                  else { "state_cap_no_relation" },
        "relation": relation_json,
        "limits": { "pair_state_cap": state_cap, "peak_rss_cap_bytes": memory_cap_bytes },
        "sampling": { "kind": if sampled { "coprime_stride_without_replacement" }
                             else { "complete_lexicographic" },
                      "origin": if sampled { origin } else { 0 },
                      "step": if sampled { step } else { 1 },
                      "orientations_per_state": orientations_per_state },
        "total_quotient_pair_states": total,
        "index_pair_states_examined": examined,
        "index_satisfiable_s3_states": states.len(),
        "index_distinct_root_keys": table.len,
        "root_table_slots": table.keys.len(),
        "root_table_hash_probes": {
            "index_insert_and_rehash": index_table_probes,
            "target_lookup": table.lookup_probes,
        },
        "target_states_scanned": scanned,
        "target_state_orientations_tested": oriented_states,
        "target_partner_roots": partner_roots,
        "target_table_hits": table_hits,
        "native_s3_generator_target_control": control_json,
        "timing_ns": { "setup": setup_ns.to_string(), "index_build": index_ns.to_string(),
                       "target_pdp_and_native_check": online_ns.to_string() },
        "operation_counts": { "setup": setup_ops.value(), "index_build": index_ops.value(),
                              "target_pdp_and_native_check": target_ops.value() },
        "peak_rss_bytes": peak_rss_bytes(),
        "rss_after_index_bytes": after_index_rss,
        "verified_single_target_dlp": false,
        "complete_work_log2": null,
    })
}

fn splitmix64(state: &mut u64) -> u64 {
    *state = state.wrapping_add(0x9e37_79b9_7f4a_7c15);
    let mut value = *state;
    value = (value ^ (value >> 30)).wrapping_mul(0xbf58_476d_1ce4_e5b9);
    value = (value ^ (value >> 27)).wrapping_mul(0x94d0_49bb_1331_11eb);
    value ^ (value >> 31)
}

fn main() {
    let args: Vec<String> = env::args().collect();
    assert_eq!(args.len(), 7,
        "usage: native_s3_root manifest.json bridge.json reps.bin state_cap memory_cap_mib output.json");
    let manifest: Value = serde_json::from_slice(&fs::read(&args[1]).unwrap()).unwrap();
    let bridge: Value = serde_json::from_slice(&fs::read(&args[2]).unwrap()).unwrap();
    let data = fs::read(&args[3]).unwrap();
    assert_eq!(data.len() % 16, 0);
    let reps: Vec<u128> = data.chunks_exact(16)
        .map(|chunk| u128::from_le_bytes(chunk.try_into().unwrap())).collect();
    let n = manifest["field_degree"].as_u64().unwrap() as u32;
    assert_eq!(manifest["representative_count_K"].as_u64().unwrap() as usize, reps.len());
    assert_eq!(bridge["field_degree"].as_u64().unwrap() as u32, n);
    assert_eq!(manifest["curve_id"], bridge["curve_id"]);
    let cap = args[4].parse::<u64>().unwrap();
    let memory_mib = args[5].parse::<u64>().unwrap();
    assert_eq!(cap, manifest["pair_state_cap"].as_u64().unwrap());
    assert_eq!(memory_mib, manifest["peak_rss_cap_mib"].as_u64().unwrap());
    let memory_bytes = memory_mib.checked_mul(1024 * 1024).unwrap();
    let low_terms: Vec<u32> = manifest["polynomial_low_terms"].as_array().unwrap()
        .iter().map(|v| v.as_u64().unwrap() as u32).collect();
    let irr = IrreduciblePoly { degree: n, low_terms };
    let report = if n == 53 {
        run(Gf2::new(&irr), &manifest, &bridge, &reps, cap, memory_bytes)
    } else if n == 83 {
        run(Gf2_128::new(&irr), &manifest, &bridge, &reps, cap, memory_bytes)
    } else { panic!("unsupported field degree") };
    fs::write(&args[6], serde_json::to_vec_pretty(&report).unwrap()).unwrap();
    println!("{}", json!({"status": report["status"], "field_degree": n,
                          "index_states": report["index_pair_states_examined"],
                          "target_states": report["target_states_scanned"],
                          "peak_rss_bytes": report["peak_rss_bytes"]}));
}
