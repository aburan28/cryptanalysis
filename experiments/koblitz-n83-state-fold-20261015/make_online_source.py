#!/usr/bin/env python3
"""Derive the state-fold online producer from the combined producer, exactly.

Input: `snapshots/r770/examples/koblitz_orbit_dlp_fast_online_logcache.rs`
(crypto 770f6a69 `koblitz_orbit_dlp_fast_online.rs` plus B's
`ic_log_cache.patch`, restored and digest-checked by `restore.py`).
Output: `snapshots/r770/examples/koblitz_orbit_dlp_fast_online_statefold.rs`.

Step 1 is the combined producer of `claude/n83-combined` @ 88e1929fb
(`combined_derivation.py`, that branch's `make_online_source.py`, verbatim):
lift_scan's `KIC_TARGET_CANON` and the scan order's `KIC_SCAN_ORDER`. Its
output must have the combined protocol's frozen digest `COMBINED_SHA256`.

Step 2 (`fold_edits`) adds, by exact counted string replacements inside the
wide (`u128`) module:

* `KIC_STATE_FOLD=1`: the root index stores each unordered state class once.
  State (l, r, rel) and its mate (r, l, (n - rel) % n) hold the same two
  root orbits (the mate's normal-basis roots are the representative's
  rotated by the mate's `rel`), so the fold keeps l < r, or l == r with
  2 rel <= n: 14,940,300 of 29,880,000 states at K600. The table is filled
  from the stored states in the baseline's insertion order, so it holds the
  same key -> value map (an inserted mate root was always already present).
  Its capacity follows the stored count, as the baseline's follows its own.
* The folded scan walks the logical (unfolded) state indices in exactly the
  baseline order (left-major from `start`, or the same keyed Feistel order
  on the logical count), rebuilding a mate on the fly, and skips a state
  whose mate came earlier in that order: the mate made the same probes
  (first two codes swapped) without a relation. The first relation, its
  codes, intermediates, point indices and scalar are therefore the
  baseline's; only the probe counter drops by the skipped states' probes.
* `KIC_FOLD_PLANT=1` (planted positive control, fold only): redoes and
  discards the S3 solve and both root canonicalizations of every mate state
  during the index build, and rescans every skipped state online into a
  separate counter (`fold_audit_probes`), asserting it finds nothing.
* `KIC_INDEX_CANON=lift` (secondary arm, fold only): the index build
  canonicalizes roots with `lift_scan` instead of the full scan; the same
  `(canonical, least shift)` values, so the same table.
* `KIC_RANK_CANON` / `KIC_RANK_ORDER`: the rank stage's canonicalizer and
  order (default `full` / `left_major`, B's), plus per-attempt probe and
  nanosecond arrays in the summary.
* `KIC_INDEX_DIGEST=1`: after the last target (outside every timed
  interval) a blake3 digest of all logical states in index order and an
  order-independent digest of the table's key -> value map.

`--check` regenerates and requires byte identity with the existing output.
"""

import argparse
import hashlib
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXAMPLES = HERE / "snapshots" / "r770" / "examples"
SOURCE = EXAMPLES / "koblitz_orbit_dlp_fast_online_logcache.rs"
OUTPUT = EXAMPLES / "koblitz_orbit_dlp_fast_online_statefold.rs"
COMBINED_SHA256 = "f65e518a1644962f7b20dcc718d47a0620b43871cd083523e6f827a6d9f56a7e"
WIDE_START = "mod wide {\n"
WIDE_END = "\nfn main() -> ExitCode {\n"


def combined():
    spec = importlib.util.spec_from_file_location("combined_derivation", HERE / "combined_derivation.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def replace(text, old, new, count=1):
    found = text.count(old)
    if found != count:
        raise ValueError("expected %d occurrence(s), found %d: %r" % (count, found, old[:80]))
    return text.replace(old, new)


FOLD_CODE = r'''
    // ── koblitz-n83-state-fold-20261015: the folded root index ──
    //
    // State (l, r, rel) holds the roots x(A ± τ^rel B) of S3(x(A), x(τ^rel B), X),
    // A = reps[l], B = reps[r]. Its mate (r, l, (n - rel) % n) holds
    // x(B ± τ^-rel A) = Frob^-rel of the same roots, in the same root order (the
    // solver is symmetric in its inputs and Frobenius-equivariant), so over all
    // n shifts it makes exactly the representative's probes with the first two
    // codes swapped. The fold stores l < r, or l == r with 2·rel ≤ n.
    const INDEX_CANON_SELECTED: u8 = 0;
    const INDEX_CANON_LIFT: u8 = 1;
    static FOLD_AUDIT_PROBES: AtomicU64 = AtomicU64::new(0);

    #[derive(Clone, Copy)]
    struct IndexMode128 {
        fold: bool,
        plant: bool,
        canon: u8,
    }

    fn index_mode_from_env() -> (IndexMode128, &'static str) {
        let fold = match std::env::var("KIC_STATE_FOLD").as_deref() {
            Err(_) | Ok("") | Ok("0") => false,
            Ok("1") => true,
            Ok(other) => panic!("unknown KIC_STATE_FOLD {other}"),
        };
        let plant = match std::env::var("KIC_FOLD_PLANT").as_deref() {
            Err(_) | Ok("") | Ok("0") => false,
            Ok("1") => true,
            Ok(other) => panic!("unknown KIC_FOLD_PLANT {other}"),
        };
        let (canon, canon_name) = match std::env::var("KIC_INDEX_CANON").as_deref() {
            Err(_) | Ok("") | Ok("selected") => (INDEX_CANON_SELECTED, "selected"),
            Ok("lift") => (INDEX_CANON_LIFT, "lift"),
            Ok(other) => panic!("unknown KIC_INDEX_CANON {other}"),
        };
        assert!(fold || (!plant && canon == INDEX_CANON_SELECTED),
                "KIC_FOLD_PLANT and KIC_INDEX_CANON need KIC_STATE_FOLD=1");
        (IndexMode128 { fold, plant, canon }, canon_name)
    }

    #[inline(always)]
    fn index_canonical128(basis: &NormalBasis128, canon: u8, v: u128) -> (u128, u32) {
        if canon == INDEX_CANON_LIFT {
            super::lift2::lift_scan_wide(v, basis.n)
        } else {
            basis.canonical_selected(v)
        }
    }

    struct Fold128 {
        width: usize,
        n: usize,
        selfs: usize,
        offsets: Vec<usize>,
        plant: bool,
    }

    impl Fold128 {
        fn new(width: usize, n: usize, plant: bool) -> Self {
            let selfs = (0..n).filter(|&relative| 2 * relative <= n).count();
            let mut offsets = Vec::with_capacity(width + 1);
            let mut total = 0usize;
            for left in 0..width {
                offsets.push(total);
                total += selfs + (width - 1 - left) * n;
            }
            offsets.push(total);
            Self { width, n, selfs, offsets, plant }
        }

        fn stored(&self) -> usize {
            self.offsets[self.width]
        }

        fn logical(&self) -> usize {
            self.width * self.width * self.n
        }

        #[inline(always)]
        fn decompose(&self, index: usize) -> (usize, usize, usize) {
            let pair = index / self.n;
            (pair / self.width, pair % self.width, index % self.n)
        }

        #[inline(always)]
        fn compose(&self, left: usize, right: usize, relative: usize) -> usize {
            (left * self.width + right) * self.n + relative
        }

        #[inline(always)]
        fn is_representative(&self, left: usize, right: usize, relative: usize) -> bool {
            left < right || (left == right && 2 * relative <= self.n)
        }

        #[inline(always)]
        fn mate_index(&self, index: usize) -> usize {
            let (left, right, relative) = self.decompose(index);
            self.compose(right, left, (self.n - relative) % self.n)
        }

        #[inline(always)]
        fn slot(&self, left: usize, right: usize, relative: usize) -> usize {
            self.offsets[left]
                + if left == right {
                    relative
                } else {
                    self.selfs + (right - left - 1) * self.n + relative
                }
        }
    }

    /// The unfolded state at logical index `index`: the stored representative,
    /// or its mate rebuilt by rotating the representative's normal roots.
    #[inline(always)]
    fn fold_state128(index: &Index128, fold: &Fold128, basis: &NormalBasis128, logical: usize) -> State128 {
        let (left, right, relative) = fold.decompose(logical);
        if fold.is_representative(left, right, relative) {
            let stored = &index.states[fold.slot(left, right, relative)];
            return State128 {
                left: stored.left,
                right: stored.right,
                relative: stored.relative,
                normal_roots: stored.normal_roots,
            };
        }
        let stored = &index.states[fold.slot(right, left, (fold.n - relative) % fold.n)];
        let k = relative as u32;
        State128 {
            left: left as u16,
            right: right as u16,
            relative: relative as u16,
            normal_roots: [
                basis.rotate(stored.normal_roots[0], k),
                basis.rotate(stored.normal_roots[1], k),
            ],
        }
    }

    fn build_index128_folded(
        gf: &Gf2_128,
        basis: &NormalBasis128,
        solver: &S3Solver128,
        reps: &[u128],
        mode: IndexMode128,
    ) -> Index128 {
        let n = gf.n as usize;
        let shifted: Vec<Vec<u128>> = reps
            .iter()
            .map(|&code| {
                let mut row = Vec::with_capacity(n);
                let mut value = code;
                for _ in 0..n {
                    row.push(value);
                    value = gf.sqr(value);
                }
                row
            })
            .collect();
        let fold = Fold128::new(reps.len(), n, mode.plant);
        let mut states = Vec::new();
        for left in 0..reps.len() {
            for right in left..reps.len() {
                for relative in 0..n {
                    if left == right && 2 * relative > n {
                        continue;
                    }
                    let roots = solver
                        .roots(gf, basis, shifted[left][0], shifted[right][relative])
                        .expect("the state fold needs every state regular");
                    states.push(State128 {
                        left: left as u16,
                        right: right as u16,
                        relative: relative as u16,
                        normal_roots: [
                            basis.to_normal.apply(roots[0]),
                            basis.to_normal.apply(roots[1]),
                        ],
                    });
                }
            }
        }
        assert_eq!(states.len(), fold.stored());
        if mode.plant {
            // Planted control: redo, and discard, the S3 solve and both root
            // canonicalizations of every mate state the fold does not store.
            for left in 0..reps.len() {
                for right in 0..=left {
                    for relative in 0..n {
                        if fold.is_representative(left, right, relative) {
                            continue;
                        }
                        let roots = solver
                            .roots(gf, basis, shifted[left][0], shifted[right][relative])
                            .expect("the state fold needs every state regular");
                        for root in roots {
                            black_box(index_canonical128(
                                basis,
                                mode.canon,
                                basis.to_normal.apply(black_box(root)),
                            ));
                        }
                    }
                }
            }
        }
        let mut table = RootTable128::with_capacity(states.len() * 2);
        for state in &states {
            for &root in &state.normal_roots {
                let (canonical, shift) = index_canonical128(basis, mode.canon, root);
                table.insert_if_absent(
                    canonical,
                    pack(state.left, state.right, state.relative, shift),
                );
            }
        }
        Index128 {
            logical_states: fold.logical(),
            states,
            table,
            shifted,
            fold: Some(fold),
        }
    }

    /// The baseline scan over the logical states (same order, same `start`
    /// or Feistel key), each class scanned once at its first occurrence.
    #[allow(clippy::too_many_arguments)]
    fn extract128_folded<const C: u8, const O: u8>(
        gf: &Gf2_128,
        fast: &FastBinaryCurve128,
        basis: &NormalBasis128,
        solver: &S3Solver128,
        index: &Index128,
        fold: &Fold128,
        base: &Base128,
        target: FastPoint128,
        target_x: u128,
        start: usize,
        probes: &mut u64,
        scan: &mut StateScan128,
        clock: &mut PhaseClock,
        split: &mut ExtractSplit,
    ) -> Option<Relation128> {
        let len = index.logical_states;
        macro_rules! visit {
            ($logical:expr, $skip:expr) => {{
                let logical = $logical;
                let skip = $skip;
                if skip {
                    split.skipped_symmetric_states += 1;
                }
                if !skip || fold.plant {
                    let state = fold_state128(index, fold, basis, logical);
                    if skip {
                        let mut audit = 0u64;
                        let found = scan_state128::<C>(
                            gf, fast, basis, solver, index, base, target, target_x, &state, scan,
                            &mut audit, clock, split,
                        );
                        assert!(found.is_none(), "a skipped mate state found a relation");
                        FOLD_AUDIT_PROBES.fetch_add(audit, Ordering::Relaxed);
                    } else if let Some(relation) = scan_state128::<C>(
                        gf, fast, basis, solver, index, base, target, target_x, &state, scan,
                        probes, clock, split,
                    ) {
                        return Some(relation);
                    }
                }
            }};
        }
        if O == ORDER_FEISTEL {
            let permutation = ScanPermutation::new(len, start as u64);
            for position in 0..permutation.domain {
                let logical = permutation.apply(position);
                if logical >= len as u64 {
                    continue;
                }
                let logical = logical as usize;
                let mate = fold.mate_index(logical);
                visit!(logical, mate != logical && permutation.invert(mate as u64) < position);
            }
            return None;
        }
        let start = start % len.max(1);
        for offset in 0..len {
            let logical = if start + offset < len { start + offset } else { start + offset - len };
            let mate = fold.mate_index(logical);
            let mate_offset = if mate >= start { mate - start } else { mate + len - start };
            visit!(logical, mate != logical && mate_offset < offset);
        }
        None
    }

    /// Sampled check that `invert` undoes `apply` (the crate tests check the
    /// whole domain).
    fn scan_inverse_selftest(len: usize, key: u64) -> bool {
        let permutation = ScanPermutation::new(len, key);
        let mut x = key | 1;
        (0..65_536).all(|_| {
            x ^= x << 13;
            x ^= x >> 7;
            x ^= x << 17;
            let position = x % permutation.domain;
            permutation.invert(permutation.apply(position)) == position
        })
    }

    #[inline(always)]
    fn digest_mix64(mut z: u64) -> u64 {
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
        z ^ (z >> 31)
    }

    /// Digest of every logical state in index order and an order-independent
    /// digest of the table's key -> value map (equal for every arm iff the
    /// fold reproduces B's states and B's table map).
    fn index_digest128(index: &Index128, basis: &NormalBasis128) -> Value {
        let mut hasher = blake3::Hasher::new();
        hasher.update(b"n83-state-fold-logical-states-v1");
        let mut buffer = Vec::with_capacity(1 << 16);
        for logical in 0..index.logical_states {
            let rebuilt;
            let state = match &index.fold {
                Some(fold) => {
                    rebuilt = fold_state128(index, fold, basis, logical);
                    &rebuilt
                }
                None => &index.states[logical],
            };
            buffer.extend_from_slice(&state.left.to_le_bytes());
            buffer.extend_from_slice(&state.right.to_le_bytes());
            buffer.extend_from_slice(&state.relative.to_le_bytes());
            buffer.extend_from_slice(&state.normal_roots[0].to_le_bytes());
            buffer.extend_from_slice(&state.normal_roots[1].to_le_bytes());
            if buffer.len() >= (1 << 16) - 64 {
                hasher.update(&buffer);
                buffer.clear();
            }
        }
        hasher.update(&buffer);
        let (mut sum, mut xor, mut entries) = (0u64, 0u64, 0u64);
        for &(key, value) in &index.table.slots {
            if key == u128::MAX {
                continue;
            }
            let h = digest_mix64(
                digest_mix64(key as u64 ^ 0x243F_6A88_85A3_08D3)
                    ^ digest_mix64((key >> 64) as u64 ^ 0x1319_8A2E_0370_7344)
                    ^ digest_mix64(value ^ 0xA409_3822_299F_31D0).rotate_left(1),
            );
            sum = sum.wrapping_add(h);
            xor ^= h.rotate_left(23);
            entries += 1;
        }
        json!({
            "logical_states": index.logical_states,
            "logical_states_blake3": hasher.finalize().to_hex().to_string(),
            "table_entries": entries,
            "table_map_sum64": format!("{sum:016x}"),
            "table_map_xor64": format!("{xor:016x}"),
            "accounting": "after the last target; outside setup and every online interval",
        })
    }

    #[cfg(test)]
    mod state_fold_tests {
        use super::*;

        #[test]
        fn feistel_invert_undoes_apply_on_the_whole_domain() {
            for (len, key) in [(1usize, 3u64), (2, 0), (97, 5), (2100, 0xDEAD_BEEF), (29_880_000, 0x0123_4567_89AB_CDEF)] {
                let permutation = ScanPermutation::new(len, key);
                let step = if permutation.domain > 1 << 20 { 7919 } else { 1 };
                let mut position = 0u64;
                while position < permutation.domain {
                    assert_eq!(permutation.invert(permutation.apply(position)), position);
                    position += step;
                }
            }
        }

        #[test]
        fn fold_counts_match_the_unordered_classes() {
            let fold = Fold128::new(600, 83, false);
            assert_eq!(fold.logical(), 29_880_000);
            assert_eq!(fold.stored(), 14_940_300);
            let small = Fold128::new(7, 5, false);
            let mut seen = vec![false; small.stored()];
            for logical in 0..small.logical() {
                let (l, r, rel) = small.decompose(logical);
                assert_eq!(small.compose(l, r, rel), logical);
                let mate = small.mate_index(logical);
                assert_eq!(small.mate_index(mate), logical);
                let rep = small.is_representative(l, r, rel);
                let (ml, mr, mrel) = small.decompose(mate);
                assert!(rep || small.is_representative(ml, mr, mrel));
                if rep {
                    assert!(!seen[small.slot(l, r, rel)]);
                    seen[small.slot(l, r, rel)] = true;
                }
            }
            assert!(seen.iter().all(|&s| s));
        }

        fn small_instance(columns: usize) -> (FastBinaryCurve128, Gf2_128, NormalBasis128, S3Solver128, Base128, Vec<u128>, FastPoint128) {
            let curve = KoblitzCurve::new(1, 83).unwrap();
            let fast = FastBinaryCurve128::new(&curve.curve.irreducible, 1).unwrap();
            let gf = Gf2_128::new(&curve.curve.irreducible);
            let b = gf.from_element(&curve.curve.b);
            let r = curve.subgroup_order.to_u64().unwrap();
            let (points, labels, reps, _) = construct_base128(&fast, &curve, b, columns, r);
            let mut by_x: HashMap<u128, Vec<usize>> = HashMap::new();
            for (i, point) in points.iter().enumerate() {
                by_x.entry(point.unwrap().0).or_default().push(i);
            }
            let reps: Vec<u128> = reps.iter().map(|p| p.unwrap()[0]).collect();
            let generator = points[0];
            let base = Base128 { points, labels, by_x, columns };
            let basis = NormalBasis128::new(&gf);
            let solver = S3Solver128::new(&gf, b);
            (fast, gf, basis, solver, base, reps, generator)
        }

        #[test]
        fn folded_index_reproduces_states_table_and_first_relation() {
            let (fast, gf, basis, solver, base, reps, _) = small_instance(9);
            let full = build_index128(&gf, &basis, &solver, &reps,
                IndexMode128 { fold: false, plant: false, canon: INDEX_CANON_SELECTED });
            let folded = build_index128(&gf, &basis, &solver, &reps,
                IndexMode128 { fold: true, plant: false, canon: INDEX_CANON_SELECTED });
            let planted = build_index128(&gf, &basis, &solver, &reps,
                IndexMode128 { fold: true, plant: true, canon: INDEX_CANON_LIFT });
            assert_eq!(full.states.len(), 9 * 9 * 83);
            assert_eq!(folded.states.len(), (9 * 9 * 83 - 9 * 83) / 2 + 9 * 42);
            let fold = folded.fold.as_ref().unwrap();
            for logical in 0..full.states.len() {
                let a = &full.states[logical];
                let b = fold_state128(&folded, fold, &basis, logical);
                assert_eq!((a.left, a.right, a.relative, a.normal_roots),
                           (b.left, b.right, b.relative, b.normal_roots), "state {logical}");
            }
            assert_eq!(full.table.len, folded.table.len);
            assert_eq!(full.table.len, planted.table.len);
            for &(key, value) in &full.table.slots {
                if key != u128::MAX {
                    assert_eq!(folded.table.get(key), Some(value));
                    assert_eq!(planted.table.get(key), Some(value));
                }
            }
            assert_eq!(index_digest128(&full, &basis), index_digest128(&folded, &basis));
            assert_eq!(index_digest128(&full, &basis), index_digest128(&planted, &basis));
            // Planted targets: sums of four base points, so every scan finds a relation.
            let mut seed = 0x9E37_79B9_7F4A_7C15u64;
            let mut skipped_total = 0u64;
            for trial in 0..24 {
                let mut pick = || {
                    seed = digest_mix64(seed.wrapping_add(trial));
                    (seed % base.points.len() as u64) as usize
                };
                let mut target = base.points[pick()];
                for _ in 0..3 {
                    target = fast.add(target, base.points[pick()]);
                }
                let Some((tx, ty)) = target else { continue };
                let start = digest_mix64((tx ^ ty.rotate_left(29)) as u64) as usize;
                macro_rules! run {
                    ($o:expr, $index:expr) => {{
                        let mut clock = PhaseClock::start();
                        let mut split = ExtractSplit::default();
                        FOLD_AUDIT_PROBES.store(0, Ordering::Relaxed);
                        let relation = extract128::<CANON_LIFT, { $o }>(
                            &gf, &fast, &basis, &solver, $index, &base, target, start, &mut clock, &mut split,
                        );
                        (relation, split.skipped_symmetric_states, FOLD_AUDIT_PROBES.load(Ordering::Relaxed))
                    }};
                }
                for order in [ORDER_LEFT_MAJOR, ORDER_FEISTEL] {
                    let ((b, _, _), (f, skipped, _), (p, _, audit)) = if order == ORDER_FEISTEL {
                        (run!(ORDER_FEISTEL, &full), run!(ORDER_FEISTEL, &folded), run!(ORDER_FEISTEL, &planted))
                    } else {
                        (run!(ORDER_LEFT_MAJOR, &full), run!(ORDER_LEFT_MAJOR, &folded), run!(ORDER_LEFT_MAJOR, &planted))
                    };
                    let b = b.expect("the unfolded scan finds a planted relation");
                    for other in [f.as_ref().unwrap(), p.as_ref().unwrap()] {
                        assert_eq!(b.point_indices, other.point_indices);
                        assert_eq!(b.x_codes, other.x_codes);
                        assert_eq!(b.intermediates, other.intermediates);
                    }
                    let f = f.unwrap();
                    assert!(f.probes <= b.probes);
                    assert_eq!(p.unwrap().probes, f.probes);
                    assert_eq!(f.probes + audit, b.probes, "probes identity, order {order}");
                    skipped_total += skipped;
                }
            }
            assert!(skipped_total > 0, "the small instance should exercise the skip");
        }
    }
'''


def fold_edits(head, wide):
    head = replace(head, "// (Feistel, claude/n83-scan-order).\n",
                   "// (Feistel, claude/n83-scan-order).\n"
                   "// koblitz-n83-state-fold-20261015: plus the folded root index\n"
                   "// (KIC_STATE_FOLD, KIC_FOLD_PLANT, KIC_INDEX_CANON), the rank-stage\n"
                   "// selectors (KIC_RANK_CANON, KIC_RANK_ORDER) and KIC_INDEX_DIGEST.\n")
    # Feistel inverse.
    wide = replace(wide, """            (left << self.half) | right
        }
    }
""", """            (left << self.half) | right
        }

        /// Inverse of `apply` (koblitz-n83-state-fold-20261015): the rounds
        /// undone in reverse key order.
        #[inline(always)]
        fn invert(&self, image: u64) -> u64 {
            let mut left = image >> self.half;
            let mut right = image & self.mask;
            for &key in self.keys.iter().rev() {
                let previous_right = left;
                let previous_left = (right ^ self.round(previous_right, key)) & self.mask;
                left = previous_left;
                right = previous_right;
            }
            (left << self.half) | right
        }
    }
""")
    wide = replace(wide, """    struct Index128 {
        states: Vec<State128>,
        table: RootTable128,
        shifted: Vec<Vec<u128>>,
    }
""", """    struct Index128 {
        states: Vec<State128>,
        table: RootTable128,
        shifted: Vec<Vec<u128>>,
        // koblitz-n83-state-fold-20261015: the unfolded state count, and the
        // fold map when the index stores one state per unordered class.
        logical_states: usize,
        fold: Option<Fold128>,
    }
""")
    wide = replace(wide, """    fn build_index128(
        gf: &Gf2_128,
        basis: &NormalBasis128,
        solver: &S3Solver128,
        reps: &[u128],
    ) -> Index128 {
        let n = gf.n as usize;
""", """    fn build_index128(
        gf: &Gf2_128,
        basis: &NormalBasis128,
        solver: &S3Solver128,
        reps: &[u128],
        mode: IndexMode128,
    ) -> Index128 {
        if mode.fold {
            return build_index128_folded(gf, basis, solver, reps, mode);
        }
        let n = gf.n as usize;
""")
    wide = replace(wide, """        Index128 {
            states,
            table,
            shifted,
        }
    }

    fn lift128(
""", """        Index128 {
            logical_states: states.len(),
            states,
            table,
            shifted,
            fold: None,
        }
    }
""" + FOLD_CODE + """
    fn lift128(
""")
    wide = replace(wide, """        let mut scan = StateScan128::new(gf.n);
""", """        let mut scan = StateScan128::new(gf.n);
        if let Some(fold) = &index.fold {
            return extract128_folded::<C, O>(
                gf, fast, basis, solver, index, fold, base, target, target_x, start, &mut probes,
                &mut scan, clock, split,
            );
        }
""")
    wide = replace(wide, """        let index = build_index128(&gf, &basis, &solver, &reps);
""", """        let (index_mode, index_canon_name) = index_mode_from_env();
        let index = build_index128(&gf, &basis, &solver, &reps, index_mode);
""")
    wide = replace(wide, """        let mut rank_root_calls = 0u64;
""", """        let mut rank_root_calls = 0u64;
        let mut rank_skipped_symmetric_states = 0u64;
        let mut rank_attempt_probes: Vec<Option<u64>> = Vec::new();
        let mut rank_attempt_ns: Vec<u64> = Vec::new();
        let (rank_canon_name, rank_order_name) = (
            match std::env::var("KIC_RANK_CANON").as_deref() {
                Err(_) | Ok("") | Ok("full") => "full",
                Ok("lift") => "lift",
                Ok(other) => panic!("unknown KIC_RANK_CANON {other}"),
            },
            match std::env::var("KIC_RANK_ORDER").as_deref() {
                Err(_) | Ok("") | Ok("left_major") => "left_major",
                Ok("feistel") => "feistel",
                Ok(other) => panic!("unknown KIC_RANK_ORDER {other}"),
            },
        );
""")
    wide = replace(wide, """            let relation = extract128::<CANON_FULL, ORDER_LEFT_MAJOR>(
                &gf,
                &fast,
                &basis,
                &solver,
                &index,
                &base,
                point,
                (rank_seed >> 20) as usize,
                &mut rank_clock,
                &mut rank_split,
            );
            rank_pdp_elapsed += rank_split.pdp;
            rank_relation_check_elapsed += rank_split.relation_check;
            rank_root_calls += rank_split.root_calls;
""", """            macro_rules! rank_extract {
                ($c:expr, $o:expr) => {
                    extract128::<{ $c }, { $o }>(
                        &gf,
                        &fast,
                        &basis,
                        &solver,
                        &index,
                        &base,
                        point,
                        (rank_seed >> 20) as usize,
                        &mut rank_clock,
                        &mut rank_split,
                    )
                };
            }
            let relation = match (rank_canon_name, rank_order_name) {
                ("full", "left_major") => rank_extract!(CANON_FULL, ORDER_LEFT_MAJOR),
                ("full", _) => rank_extract!(CANON_FULL, ORDER_FEISTEL),
                (_, "left_major") => rank_extract!(CANON_LIFT, ORDER_LEFT_MAJOR),
                _ => rank_extract!(CANON_LIFT, ORDER_FEISTEL),
            };
            rank_pdp_elapsed += rank_split.pdp;
            rank_relation_check_elapsed += rank_split.relation_check;
            rank_root_calls += rank_split.root_calls;
            rank_skipped_symmetric_states += rank_split.skipped_symmetric_states;
            rank_attempt_probes.push(relation.as_ref().map(|relation| relation.probes));
            rank_attempt_ns.push(
                (query_elapsed + rank_split.pdp + rank_split.relation_check).as_nanos() as u64,
            );
""")
    wide = replace(wide, """            .all(|&key| scan_permutation_selftest(index.states.len(), key));
""", """            .all(|&key| {
                scan_permutation_selftest(index.logical_states, key)
                    && (index.fold.is_none() || scan_inverse_selftest(index.logical_states, key))
            });
""")
    wide = replace(wide, """            VERIFY_LIFT_MISMATCHES.store(0, Ordering::Relaxed);
""", """            VERIFY_LIFT_MISMATCHES.store(0, Ordering::Relaxed);
            FOLD_AUDIT_PROBES.store(0, Ordering::Relaxed);
""")
    wide = replace(wide, """                "skipped_symmetric_states":split.skipped_symmetric_states,
""", """                "skipped_symmetric_states":split.skipped_symmetric_states,
                "fold_audit_probes":FOLD_AUDIT_PROBES.load(Ordering::Relaxed),
""")
    wide = replace(wide, """        let mut summary = json!({
""", """        let index_digest = (std::env::var("KIC_INDEX_DIGEST").as_deref() == Ok("1"))
            .then(|| index_digest128(&index, &basis));
        let mut summary = json!({
""")
    wide = replace(wide, """            "regular_states":index.states.len(),
""", """            "regular_states":index.logical_states,
            "stored_states":index.states.len(),
            "state_fold":index.fold.is_some(),
            "fold_plant":index.fold.as_ref().is_some_and(|fold| fold.plant),
            "index_canonicalizer":index_canon_name,
            "root_table_slots":index.table.slots.len(),
            "index_digest":index_digest,
            "rank_canonicalizer":rank_canon_name,
            "rank_order":rank_order_name,
            "rank_skipped_symmetric_states":rank_skipped_symmetric_states,
            "rank_attempt_probes":rank_attempt_probes,
            "rank_attempt_ns":rank_attempt_ns,
""")
    wide = replace(wide, """            "scan_order_selftest":{"states":index.states.len(), "keys":scan_selftest_keys.len(),
""", """            "scan_order_selftest":{"states":index.logical_states, "keys":scan_selftest_keys.len(),
""")
    return head, wide


def derive(text):
    staged = combined().derive(text)
    if hashlib.sha256(staged.encode()).hexdigest() != COMBINED_SHA256:
        raise ValueError("step 1 differs from the combined producer's frozen digest")
    head, rest = staged.split(WIDE_START, 1)
    wide, tail = rest.split(WIDE_END, 1)
    head, wide = fold_edits(head, wide)
    return head + WIDE_START + wide + WIDE_END + tail


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = derive(SOURCE.read_text())
    if args.check:
        if OUTPUT.read_text() != text:
            raise SystemExit("derived online source differs from " + str(OUTPUT))
    else:
        OUTPUT.write_text(text)
    print("online_source_sha256=" + hashlib.sha256(text.encode()).hexdigest())


if __name__ == "__main__":
    sys.exit(main())
