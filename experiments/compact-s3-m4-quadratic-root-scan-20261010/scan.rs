//! Sparse-quadratic fixed-output S3 root scan over a normal-basis weight domain.
//!
//! The fixed-output S3 denominator and root numerators are quadratic
//! polynomials in the Boolean mask bits. Precomputing their diagonal and
//! two-bit coefficients replaces field products per scanned mask with XORs.
//! Every eligible first coordinate is still enumerated once.

#![recursion_limit = "256"]

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
            to_cycle: Linear::from_images(&to_cycle_images),
            to_poly: Linear::from_images(&to_poly_images),
        };
        for i in 0..n {
            assert_eq!(result.to_poly.apply(result.to_cycle.apply(1u128 << i)), 1u128 << i);
            assert_eq!(result.to_cycle.apply(result.to_poly.apply(1u128 << i)), 1u128 << i);
        }
        result
    }
}

/// Quadratic S3 root evaluator with precomputed F2-linear half-trace.
struct S3 {
    square: Linear,
    half_trace: Linear,
    trace_mask: u128,
}

enum PreparedS3 {
    NoRoot,
    EqualInputs { ps: u128 },
    ZeroProduct,
    Regular { a: u128, p: u128, ps: u128 },
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

    /// Evaluate independent S3 quadratics with one inversion per batch.
    /// Every field multiplication inside Montgomery's trick is charged.
    fn roots_batch<F: Field>(&self, ctx: &mut Counted<F>,
                             inputs: &[(u128, u128)]) -> Vec<Option<[u128; 2]>> {
        let mut prepared = Vec::with_capacity(inputs.len());
        let mut denoms = Vec::with_capacity(inputs.len());
        for &(left, right) in inputs {
            ctx.ops.s3_calls += 1;
            let a = self.square.apply(left ^ right);
            let p = ctx.mul(left, right);
            let ps = self.square.apply(p);
            if a == 0 {
                if left == 0 {
                    prepared.push(PreparedS3::NoRoot);
                    denoms.push(0);
                } else {
                    prepared.push(PreparedS3::EqualInputs { ps });
                    denoms.push(p);
                }
            } else if ps == 0 {
                prepared.push(PreparedS3::ZeroProduct);
                denoms.push(a);
            } else {
                prepared.push(PreparedS3::Regular { a, p, ps });
                denoms.push(ctx.mul(a, ps));
            }
        }
        let mut prefix = Vec::with_capacity(denoms.len());
        let mut acc = 1u128;
        let mut first_nonzero = None;
        for (index, &denom) in denoms.iter().enumerate() {
            prefix.push(acc);
            if denom != 0 {
                if first_nonzero.is_none() {
                    first_nonzero = Some(index);
                    acc = denom;
                } else {
                    acc = ctx.mul(acc, denom);
                }
            }
        }
        let mut inverses = vec![0u128; denoms.len()];
        if let Some(first) = first_nonzero {
            let mut inverse_acc = ctx.inv(acc);
            for index in (first..denoms.len()).rev() {
                let denom = denoms[index];
                if denom == 0 { continue; }
                if index == first {
                    inverses[index] = inverse_acc;
                } else {
                    inverses[index] = ctx.mul(inverse_acc, prefix[index]);
                    inverse_acc = ctx.mul(inverse_acc, denom);
                }
            }
        }
        prepared.into_iter().zip(inverses).map(|(state, inverse)| {
            match state {
                PreparedS3::NoRoot => None,
                PreparedS3::EqualInputs { ps } => {
                    let root = ctx.mul(ps ^ 1, inverse);
                    Some([root, root])
                }
                PreparedS3::ZeroProduct => {
                    let mut root = ctx.mul(1, inverse);
                    for _ in 0..(ctx.field_degree() - 1) {
                        root = ctx.sqr(root);
                    }
                    Some([root, root])
                }
                PreparedS3::Regular { a, p, ps } => {
                    let ps_over_combined = ctx.mul(ps, inverse);
                    let q = ctx.mul(p, ps_over_combined);
                    let c = ps ^ 1;
                    let ca = ctx.mul(c, a);
                    let a_over_combined = ctx.mul(a, inverse);
                    let d = ctx.mul(ca, a_over_combined);
                    if (d & self.trace_mask).count_ones() & 1 == 1 {
                        return None;
                    }
                    let first = ctx.mul(q, self.half_trace.apply(d));
                    Some([first, first ^ q])
                }
            }
        }).collect()
    }
}

impl<F: Field> Counted<F> {
    fn field_degree(&self) -> u32 { self.field.degree() }
}

struct Quadratic {
    n: usize,
    a0: u128,
    t0: u128,
    a: Vec<u128>,
    p: Vec<u128>,
    s: Vec<u128>,
    d_diag: Vec<u128>,
    q_diag: Vec<u128>,
    t_diag: Vec<u128>,
    d_pair: Vec<u128>,
    q_pair: Vec<u128>,
    t_pair: Vec<u128>,
}

enum QuadraticPrepared {
    Equal { p: u128, ps: u128 },
    Regular { denominator: u128, d_numerator: u128,
              q_numerator: u128 },
}

impl Quadratic {
    fn new<F: Field>(ctx: &mut Counted<F>, solver: &S3,
                     images: &[u128], output: u128) -> Self {
        let n = images.len();
        let a0 = solver.square.apply(output);
        let t0 = solver.square.apply(a0);
        let mut a = Vec::with_capacity(n);
        let mut a2 = Vec::with_capacity(n);
        let mut p = Vec::with_capacity(n);
        let mut s = Vec::with_capacity(n);
        for &image in images {
            let product = ctx.mul(image, output);
            let square = solver.square.apply(image);
            a.push(square);
            a2.push(solver.square.apply(square));
            p.push(product);
            s.push(solver.square.apply(product));
        }
        let mut d_diag = Vec::with_capacity(n);
        let mut q_diag = Vec::with_capacity(n);
        let mut t_diag = Vec::with_capacity(n);
        for i in 0..n {
            d_diag.push(ctx.mul(a0 ^ a[i], s[i]));
            q_diag.push(ctx.mul(p[i], s[i]));
            t_diag.push(a2[i] ^ ctx.mul(t0 ^ a2[i], s[i]));
        }
        let mut d_pair = vec![0u128; n * n];
        let mut q_pair = vec![0u128; n * n];
        let mut t_pair = vec![0u128; n * n];
        for i in 0..n {
            for j in (i + 1)..n {
                let d = ctx.mul(a[i], s[j]) ^ ctx.mul(a[j], s[i]);
                let q = ctx.mul(p[i], s[j]) ^ ctx.mul(p[j], s[i]);
                let t = ctx.mul(a2[i], s[j]) ^ ctx.mul(a2[j], s[i]);
                d_pair[i * n + j] = d;
                d_pair[j * n + i] = d;
                q_pair[i * n + j] = q;
                q_pair[j * n + i] = q;
                t_pair[i * n + j] = t;
                t_pair[j * n + i] = t;
            }
        }
        Self { n, a0, t0, a, p, s, d_diag, q_diag, t_diag,
               d_pair, q_pair, t_pair }
    }

    #[inline(always)]
    fn prepare(&self, mut mask: u128) -> QuadraticPrepared {
        let mut positions = [0usize; 6];
        let mut count = 0usize;
        let mut a = self.a0;
        let mut p = 0u128;
        let mut ps = 0u128;
        let mut denominator = 0u128;
        let mut q_numerator = 0u128;
        let mut d_numerator = self.t0;
        while mask != 0 {
            let bit = mask.trailing_zeros() as usize;
            assert!(bit < self.n && count < positions.len());
            mask &= mask - 1;
            a ^= self.a[bit];
            p ^= self.p[bit];
            ps ^= self.s[bit];
            denominator ^= self.d_diag[bit];
            q_numerator ^= self.q_diag[bit];
            d_numerator ^= self.t_diag[bit];
            for &prior in &positions[..count] {
                denominator ^= self.d_pair[prior * self.n + bit];
                q_numerator ^= self.q_pair[prior * self.n + bit];
                d_numerator ^= self.t_pair[prior * self.n + bit];
            }
            positions[count] = bit;
            count += 1;
        }
        assert!(p != 0);
        if a == 0 {
            QuadraticPrepared::Equal { p, ps }
        } else {
            assert!(ps != 0 && denominator != 0);
            QuadraticPrepared::Regular { denominator,
                                         d_numerator,
                                         q_numerator }
        }
    }

    fn roots_batch<F: Field>(&self, ctx: &mut Counted<F>, solver: &S3,
                             masks: &[u128]) -> Vec<Option<[u128; 2]>> {
        let prepared: Vec<_> = masks.iter().map(|&mask| self.prepare(mask)).collect();
        ctx.ops.s3_calls += masks.len() as u64;
        let denominators: Vec<u128> = prepared.iter().map(|state| match state {
            QuadraticPrepared::Equal { p, .. } => *p,
            QuadraticPrepared::Regular { denominator, .. } => *denominator,
        }).collect();
        let mut prefix = Vec::with_capacity(masks.len());
        let mut acc = 1u128;
        for (index, &denominator) in denominators.iter().enumerate() {
            prefix.push(acc);
            if index == 0 { acc = denominator; }
            else { acc = ctx.mul(acc, denominator); }
        }
        let mut inverse_acc = ctx.inv(acc);
        let mut inverses = vec![0u128; masks.len()];
        for index in (0..masks.len()).rev() {
            if index == 0 {
                inverses[index] = inverse_acc;
            } else {
                inverses[index] = ctx.mul(inverse_acc, prefix[index]);
                inverse_acc = ctx.mul(inverse_acc, denominators[index]);
            }
        }
        prepared.into_iter().zip(inverses).map(|(state, inverse)| {
            match state {
                QuadraticPrepared::Equal { ps, .. } => {
                    let root = ctx.mul(ps ^ 1, inverse);
                    Some([root, root])
                }
                QuadraticPrepared::Regular { d_numerator,
                                             q_numerator, .. } => {
                    let d = ctx.mul(d_numerator, inverse);
                    if (d & solver.trace_mask).count_ones() & 1 == 1 {
                        return None;
                    }
                    let q = ctx.mul(q_numerator, inverse);
                    let first = ctx.mul(q, solver.half_trace.apply(d));
                    Some([first, first ^ q])
                }
            }
        }).collect()
    }
}

fn exact_integer(value: &Value) -> u128 {
    value.as_str().map(|s| s.parse::<u128>().unwrap())
        .or_else(|| value.as_u64().map(u128::from))
        .unwrap_or_else(|| value.to_string().parse::<u128>().unwrap())
}

fn peak_rss_bytes() -> u64 {
    unsafe {
        let mut data: libc::rusage = std::mem::zeroed();
        assert_eq!(libc::getrusage(libc::RUSAGE_SELF, &mut data), 0);
        #[cfg(target_os = "macos")]
        { data.ru_maxrss as u64 }
        #[cfg(not(target_os = "macos"))]
        { (data.ru_maxrss as u64) * 1024 }
    }
}

fn choose(n: u32, k: u32) -> u64 {
    let mut result = 1u128;
    for i in 0..k {
        result = result * u128::from(n - i) / u128::from(i + 1);
    }
    result.try_into().unwrap()
}

fn next_combination(value: u128) -> u128 {
    let low = value & value.wrapping_neg();
    let bumped = value + low;
    (((bumped ^ value) >> 2) / low) | bumped
}

fn scan<F: Field>(field: F, manifest: &Value, bridge: &Value) -> Value {
    let n = manifest["field_degree"].as_u64().unwrap() as u32;
    let weight = manifest["normal_basis_weight_bound"].as_u64().unwrap() as u32;
    let window = manifest["scan_window_size"].as_u64().unwrap() as usize;
    let memory_cap = manifest["peak_rss_cap_mib"].as_u64().unwrap() * 1024 * 1024;
    let wall_cap = manifest["scan_wall_cap_seconds"].as_u64().unwrap();
    let max_hits = manifest["max_recorded_hits"].as_u64().unwrap() as usize;
    assert!(n == 53 || n == 83);
    assert!((1..=6).contains(&weight));
    assert!((1..=65_536).contains(&window));
    assert!(max_hits > 0);
    assert_eq!(bridge["field_degree"].as_u64().unwrap() as u32, n);
    assert_eq!(bridge["curve_id"], manifest["curve_id"]);
    let full_masks: u64 = (1..=weight).map(|k| choose(n, k)).sum();
    let limit = manifest["scan_mask_cap"].as_u64().unwrap();
    assert!(limit > 0 && limit <= full_masks);
    let output = exact_integer(&manifest["right_output_x_poly_decimal"]);
    assert!(output != 0 && output < (1u128 << n));

    let started = Instant::now();
    let mut ctx = Counted { field, ops: Ops::default() };
    let cycle = Cycle::from_bridge(bridge, n);
    let solver = S3::new(&mut ctx, n);
    let setup_ns = started.elapsed().as_nanos();
    let setup_ops = ctx.ops;
    let scan_started = Instant::now();
    let images: Vec<u128> = (0..n).map(|bit| {
        ctx.ops.basis_conversions += 1;
        cycle.to_poly.apply(1u128 << bit)
    }).collect();
    let quadratic = Quadratic::new(&mut ctx, &solver, &images, output);
    let mut scanned = 0u64;
    let mut windows = 0u64;
    let mut pairs = 0u64;
    let mut rejected_weight = 0u64;
    let mut hits = Vec::new();
    let mut stop = "complete";
    let bound = 1u128 << n;
    'all_weights: for k in 1..=weight {
        let mut mask = (1u128 << k) - 1;
        while mask < bound {
            if scanned == limit { break 'all_weights; }
            let mut masks = Vec::with_capacity(window);
            while masks.len() < window && mask < bound &&
                  scanned + (masks.len() as u64) < limit {
                masks.push(mask);
                mask = next_combination(mask);
            }
            let roots = quadratic.roots_batch(&mut ctx, &solver, &masks);
            assert_eq!(roots.len(), masks.len());
            windows += 1;
            for (mask, roots) in masks.into_iter().zip(roots) {
                scanned += 1;
                if let Some(roots) = roots {
                    let mut previous = u128::MAX;
                    for right in roots {
                        if right == previous { continue; }
                        previous = right;
                        ctx.ops.basis_conversions += 1;
                        let right_mask = cycle.to_cycle.apply(right);
                        if right_mask == 0 || right_mask.count_ones() > weight {
                            rejected_weight += 1;
                            continue;
                        }
                        if mask <= right_mask {
                            pairs += 1;
                            if hits.len() < max_hits {
                                let left = cycle.to_poly.apply(mask);
                                ctx.ops.basis_conversions += 1;
                                hits.push(json!({
                                    "left_x_poly_decimal": left.to_string(),
                                    "right_x_poly_decimal": right.to_string(),
                                    "left_cycle_mask_decimal": mask.to_string(),
                                    "right_cycle_mask_decimal": right_mask.to_string(),
                                }));
                            }
                        }
                    }
                }
            }
            if peak_rss_bytes() > memory_cap {
                stop = "memory_cap_exceeded";
                break 'all_weights;
            }
            if scan_started.elapsed().as_secs() >= wall_cap {
                stop = "wall_cap_exceeded";
                break 'all_weights;
            }
        }
    }
    if stop == "complete" { assert_eq!(scanned, limit); }
    let scan_ns = scan_started.elapsed().as_nanos();
    let scan_ops = ctx.ops.minus(setup_ops);
    let status = if stop != "complete" { "BOUNDED_UNKNOWN" }
        else if limit < full_masks { "BOUNDED_PREFIX" }
        else if pairs == 0 { "EXHAUSTIVE_NO_WEIGHT_PAIR" }
        else { "WEIGHT_PAIR_FOUND" };
    json!({
        "schema": "q20261010111900-quadratic-root-scan-v1",
        "proposal_id": "Q20261010111900", "candidate_id": null, "run_id": null,
        "isogeny": "none", "field_degree": n,
        "curve_id": manifest["curve_id"],
        "workload_id": manifest["workload_id"],
        "kind": manifest["kind"],
        "normal_basis_weight_bound": weight,
        "right_output_x_poly_decimal": output.to_string(),
        "eligible_nonzero_masks": full_masks,
        "scanned_masks": scanned, "scan_windows": windows,
        "scan_window_size": window, "scan_mask_cap": limit,
        "status": status, "stop_reason": stop,
        "unique_unordered_weight_pairs": pairs,
        "recorded_hits": hits,
        "rejected_weight_roots": rejected_weight,
        "timing_ns": {"setup": setup_ns.to_string(),
                        "scan": scan_ns.to_string()},
        "operation_counts": {"setup": setup_ops.value(),
                             "scan": scan_ops.value()},
        "peak_rss_bytes": peak_rss_bytes(),
        "factor_base_actual_B": manifest["factor_base_actual_B"],
        "factor_base_folded_columns_K": manifest["factor_base_folded_columns_K"],
        "factor_base_enumerated_set_sha256": manifest["factor_base_enumerated_set_sha256"],
        "n131_complete_cold_work_log2": null,
        "n131_complete_online_one_target_work_log2": null,
    })
}

fn main() {
    let args: Vec<String> = env::args().collect();
    assert_eq!(args.len(), 4,
        "usage: fixed_output_scan manifest.json bridge.json output.json");
    let manifest: Value = serde_json::from_slice(&fs::read(&args[1]).unwrap()).unwrap();
    let bridge: Value = serde_json::from_slice(&fs::read(&args[2]).unwrap()).unwrap();
    let n = manifest["field_degree"].as_u64().unwrap() as u32;
    let low_terms: Vec<u32> = manifest["polynomial_low_terms"].as_array().unwrap()
        .iter().map(|v| v.as_u64().unwrap() as u32).collect();
    let modulus = IrreduciblePoly { degree: n, low_terms };
    let result = if n == 53 {
        scan(Gf2::new(&modulus), &manifest, &bridge)
    } else if n == 83 {
        scan(Gf2_128::new(&modulus), &manifest, &bridge)
    } else { panic!("unsupported degree") };
    fs::write(&args[3], serde_json::to_vec_pretty(&result).unwrap()).unwrap();
    println!("{}", json!({"status": result["status"],
                          "n": n, "masks": result["scanned_masks"],
                          "pairs": result["unique_unordered_weight_pairs"],
                          "window": result["scan_window_size"]}));
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn combination_counts_and_order() {
        for n in [5u32, 11, 17] {
            for weight in 1..=3 {
                let mut mask = (1u128 << weight) - 1;
                let mut count = 0u64;
                let mut last = 0;
                while mask < (1u128 << n) {
                    assert!(mask > last && mask.count_ones() == weight);
                    count += 1;
                    last = mask;
                    mask = next_combination(mask);
                }
                assert_eq!(count, choose(n, weight));
            }
        }
    }

    #[test]
    fn batched_roots_match_direct_gf32() {
        let modulus = IrreduciblePoly { degree: 5, low_terms: vec![0, 2] };
        let mut ctx = Counted { field: Gf2::new(&modulus), ops: Ops::default() };
        let solver = S3::new(&mut ctx, 5);
        let inputs: Vec<(u128, u128)> = (1..32).flat_map(
            |a| (1..32).map(move |b| (a, b))).collect();
        let batch = solver.roots_batch(&mut ctx, &inputs);
        for ((a, b), roots) in inputs.into_iter().zip(batch) {
            assert_eq!(roots, solver.roots(&mut ctx, a, b));
        }
    }

    #[test]
    fn sparse_quadratic_roots_match_direct_gf32() {
        let modulus = IrreduciblePoly { degree: 5, low_terms: vec![0, 2] };
        let mut ctx = Counted { field: Gf2::new(&modulus), ops: Ops::default() };
        let solver = S3::new(&mut ctx, 5);
        let masks: Vec<u128> = (1..32).collect();
        let images: Vec<u128> = (0..5).map(|bit| 1u128 << bit).collect();
        for output in 1..32 {
            let quadratic = Quadratic::new(&mut ctx, &solver, &images, output);
            let batched = quadratic.roots_batch(&mut ctx, &solver, &masks);
            for (&mask, roots) in masks.iter().zip(batched) {
                assert_eq!(roots, solver.roots(&mut ctx, mask, output),
                           "mask={mask} output={output}");
            }
        }
    }
}
