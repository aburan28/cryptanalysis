#!/usr/bin/env python3
"""Derive the stacked n=83 K600 online producer from the two-level root-table producer, exactly.

Input: `snapshots/r770/examples/koblitz_orbit_dlp_fast_online_logcache.rs`
(crypto 770f6a69 plus B's `ic_log_cache.patch`, restored and digest-checked
by `restore.py`).

1. `make_tablefilter_source.py` is `koblitz-n83-tablefilter-20261015`'s
   `make_online_source.py` (main, PR #934), verbatim; it imports
   `make_probepipe_source.py` and `make_combined_source.py`, also verbatim.
   Its text must hash to the table-filter protocol's frozen
   `online_source_sha256` (`TABLEFILTER_SHA256` below). That producer is the
   combined lift_scan x Feistel producer, plus the prefetched probe pipeline
   (`KIC_PROBE_PIPELINE`), plus the root-table layouts (`KIC_ROOT_TABLE`:
   `base` 32-byte slots, `compact` 16-byte slots, `filter`, `filter_plant`).
   With `KIC_ROOT_TABLE=base` and `KIC_PROBE_PIPELINE=prefetch` it is the
   probe-pipeline producer pP that run 38822490448 promoted.
2. `stack_edits`: counted, exact replacements in the wide module port the
   folded S3 root index of `koblitz-n83-state-fold-20261015` (PR #933, its
   `make_online_source.py` `FOLD_CODE` and `fold_edits`) onto every layout
   and probe loop, and give the rank stage the same probe loops:

   * `KIC_STATE_FOLD=1`: store one state per unordered class (14,940,300 of
     29,880,000), fill the selected root table from them in the baseline's
     insertion order (capacity follows the stored count, as in the state
     fold); the online scan walks the logical states in the baseline order
     and skips a state whose mate came earlier, rebuilding mates by two
     rotations. `KIC_FOLD_PLANT=1` (planted control) redoes and discards each
     mate's S3 solve and canonicalizations and rescans each skipped state
     into `fold_audit_probes`. `KIC_INDEX_CANON=lift` canonicalizes the
     index build with lift_scan (same values). These are the state fold's
     selectors with the same semantics; the folded scan now calls the
     layout's own probe loop (`scan_state128_select::<C, P>`), so the fold
     composes with the probe pipeline, the compact slots and the filter.
   * The rank stage: `KIC_RANK_CANON` (`full` | `lift`), `KIC_RANK_ORDER`
     (`left_major` | `feistel`) as in the state fold, and the new
     `KIC_RANK_PROBE`: `off` (default; B's sequential loop on the 32-byte
     table, `scan_state128`) or `target` (lift + Feistel only: the arm's own
     target loop, i.e. the prefetch pipeline on the base table, or the
     compact / filter loop of the selected layout). So the rank stage runs on
     the 16-byte table in the same process; the old requirement that a
     non-base layout needs the cached factor-log table now holds only for
     `KIC_RANK_PROBE=off`. Per attempt the summary records probes and ns, and
     `rank_relations_blake3`, a digest of every attempt's relation (attempt
     number and four point indices), which is layout- and fold-invariant.
   * `KIC_INDEX_DIGEST=1` writes, after the target and outside every
     interval, the state fold's digests (logical states in index order; the
     order-independent key -> value map), read from whichever table the
     index holds.

`--check` regenerates and requires byte identity with the existing output.
"""

import argparse
import hashlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_tablefilter_source as tablefilter  # noqa: E402  (koblitz-n83-tablefilter-20261015, verbatim)

EXAMPLES = HERE / "snapshots" / "r770" / "examples"
OUTPUT = EXAMPLES / "koblitz_orbit_dlp_fast_online_stacked.rs"
# protocol.json "sources.online_source_sha256" of koblitz-n83-tablefilter-20261015 (main).
TABLEFILTER_SHA256 = "70233510e07a9e1858793502ed85080711cd3d8a1b0fa3357861fe20a32dba0c"
WIDE_START = tablefilter.WIDE_START
WIDE_END = tablefilter.WIDE_END
replace = tablefilter.replace

HEAD_OLD = """// (16-byte exact slots and a TLB-resident blocked filter in front of them).
"""
HEAD_NEW = HEAD_OLD + """// koblitz-n83-stacked-20261016: derived from the two-level root-table
// producer by make_online_source.py; ports the folded S3 root index of
// koblitz-n83-state-fold-20261015 (KIC_STATE_FOLD, KIC_FOLD_PLANT,
// KIC_INDEX_CANON, KIC_INDEX_DIGEST) onto every root-table layout and probe
// loop, and adds the rank-stage selectors (KIC_RANK_CANON, KIC_RANK_ORDER,
// KIC_RANK_PROBE) so the rank stage runs on the compact table in process.
"""

INVERT_OLD = """            (left << self.half) | right
        }
    }
"""
INVERT_NEW = """            (left << self.half) | right
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
"""

INDEX_OLD = """        filter: Option<RootFilter128>,
        filter_build_ms: f64,
    }
"""
INDEX_NEW = """        filter: Option<RootFilter128>,
        filter_build_ms: f64,
        // koblitz-n83-stacked-20261016 (from the state fold): the unfolded
        // state count, and the fold map when the index stores one state per
        // unordered class.
        logical_states: usize,
        fold: Option<Fold128>,
    }
"""

BUILD_OLD = """    fn build_index128(
        gf: &Gf2_128,
        basis: &NormalBasis128,
        solver: &S3Solver128,
        reps: &[u128],
    ) -> Index128 {
        build_index128_mode(
            gf,
            basis,
            solver,
            reps,
            root_table_from_env(),
            root_filter_log2_bits_from_env(),
        )
    }

    fn build_index128_mode(
        gf: &Gf2_128,
        basis: &NormalBasis128,
        solver: &S3Solver128,
        reps: &[u128],
        root_table: u8,
        filter_log2_bits: u32,
    ) -> Index128 {
        let n = gf.n as usize;
"""
BUILD_NEW = """    fn build_index128(
        gf: &Gf2_128,
        basis: &NormalBasis128,
        solver: &S3Solver128,
        reps: &[u128],
        mode: IndexMode128,
    ) -> Index128 {
        build_index128_stacked(
            gf,
            basis,
            solver,
            reps,
            root_table_from_env(),
            root_filter_log2_bits_from_env(),
            mode,
        )
    }

    #[allow(dead_code)]
    fn build_index128_mode(
        gf: &Gf2_128,
        basis: &NormalBasis128,
        solver: &S3Solver128,
        reps: &[u128],
        root_table: u8,
        filter_log2_bits: u32,
    ) -> Index128 {
        build_index128_stacked(
            gf,
            basis,
            solver,
            reps,
            root_table,
            filter_log2_bits,
            IndexMode128::UNFOLDED,
        )
    }

    fn build_index128_stacked(
        gf: &Gf2_128,
        basis: &NormalBasis128,
        solver: &S3Solver128,
        reps: &[u128],
        root_table: u8,
        filter_log2_bits: u32,
        mode: IndexMode128,
    ) -> Index128 {
        let n = gf.n as usize;
"""

STATES_OLD = """        let mut states = Vec::new();
        for left in 0..reps.len() {
            for right in 0..reps.len() {
"""
STATES_NEW = """        let fold = mode.fold.then(|| Fold128::new(reps.len(), n, mode.plant));
        let mut states = Vec::new();
        if let Some(fold) = &fold {
            states = folded_states128(gf, basis, solver, &shifted, fold, mode);
        } else {
        for left in 0..reps.len() {
            for right in 0..reps.len() {
"""

TABLE_OLD = """        let mut table = RootTable128::with_capacity(if root_table == TABLE_BASE {
"""
TABLE_NEW = """        }
        let mut table = RootTable128::with_capacity(if root_table == TABLE_BASE {
"""

CANON_OLD = """                    let (canonical, shift) = basis.canonical_selected(root);
"""
CANON_NEW = """                    let (canonical, shift) = index_canonical128(basis, mode.canon, root);
"""

LITERAL_OLD = """        Index128 {
            states,
            table,
            shifted,
            root_table,
            compact,
            filter,
            filter_build_ms,
        }
    }

    fn lift128(
"""
LITERAL_NEW = """        Index128 {
            logical_states: fold.as_ref().map_or(states.len(), Fold128::logical),
            states,
            table,
            shifted,
            root_table,
            compact,
            filter,
            filter_build_ms,
            fold,
        }
    }
"""  # + STACK_CODE + "\n    fn lift128(\n"

STACK_CODE = r'''
    // ── koblitz-n83-stacked-20261016: the folded root index on every layout ──
    //
    // From koblitz-n83-state-fold-20261015 (FOLD_CODE): state (l, r, rel)
    // holds the roots x(A ± τ^rel B) of S3(x(A), x(τ^rel B), X), A = reps[l],
    // B = reps[r]. Its mate (r, l, (n - rel) % n) holds x(B ± τ^-rel A) =
    // Frob^-rel of the same roots, in the same root order, so over all n shifts
    // it makes exactly the representative's probes with the first two codes
    // swapped. The fold stores l < r, or l == r with 2·rel ≤ n. The only
    // change here: the folded scan calls the layout's probe loop
    // (`scan_state128_select::<C, P>`) instead of `scan_state128::<C>`.
    const INDEX_CANON_SELECTED: u8 = 0;
    const INDEX_CANON_LIFT: u8 = 1;
    static FOLD_AUDIT_PROBES: AtomicU64 = AtomicU64::new(0);

    #[derive(Clone, Copy)]
    struct IndexMode128 {
        fold: bool,
        plant: bool,
        canon: u8,
    }

    impl IndexMode128 {
        const UNFOLDED: Self = Self { fold: false, plant: false, canon: INDEX_CANON_SELECTED };
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

    /// The rank stage's canonicalizer, state order and probe loop.
    fn rank_selectors_from_env() -> (&'static str, &'static str, &'static str) {
        let canon = match std::env::var("KIC_RANK_CANON").as_deref() {
            Err(_) | Ok("") | Ok("full") => "full",
            Ok("lift") => "lift",
            Ok(other) => panic!("unknown KIC_RANK_CANON {other}"),
        };
        let order = match std::env::var("KIC_RANK_ORDER").as_deref() {
            Err(_) | Ok("") | Ok("left_major") => "left_major",
            Ok("feistel") => "feistel",
            Ok(other) => panic!("unknown KIC_RANK_ORDER {other}"),
        };
        let probe = match std::env::var("KIC_RANK_PROBE").as_deref() {
            Err(_) | Ok("") | Ok("off") => "off",
            Ok("target") => "target",
            Ok(other) => panic!("unknown KIC_RANK_PROBE {other}"),
        };
        assert!(probe == "off" || (canon == "lift" && order == "feistel"),
                "KIC_RANK_PROBE=target runs with KIC_RANK_CANON=lift and KIC_RANK_ORDER=feistel");
        (canon, order, probe)
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

    /// The fold's stored representatives (the state fold's
    /// `build_index128_folded` state loop and planted work, unchanged); the
    /// caller fills the selected root table from them.
    fn folded_states128(
        gf: &Gf2_128,
        basis: &NormalBasis128,
        solver: &S3Solver128,
        shifted: &[Vec<u128>],
        fold: &Fold128,
        mode: IndexMode128,
    ) -> Vec<State128> {
        let n = gf.n as usize;
        let width = shifted.len();
        let mut states = Vec::new();
        for left in 0..width {
            for right in left..width {
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
            for left in 0..width {
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
        states
    }

    /// The baseline scan over the logical states (same order, same `start`
    /// or Feistel key), each class scanned once at its first occurrence, with
    /// the layout's probe loop `P`.
    #[allow(clippy::too_many_arguments)]
    fn extract128_folded<const C: u8, const O: u8, const P: u8>(
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
                        let found = scan_state128_select::<C, P>(
                            gf, fast, basis, solver, index, base, target, target_x, &state, scan,
                            &mut audit, clock, split,
                        );
                        assert!(found.is_none(), "a skipped mate state found a relation");
                        FOLD_AUDIT_PROBES.fetch_add(audit, Ordering::Relaxed);
                    } else if let Some(relation) = scan_state128_select::<C, P>(
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

    /// The state fold's digests: every logical state in index order, and an
    /// order-independent digest of the root table's key -> value map, read
    /// from whichever table this index holds (equal for every arm iff the
    /// arm reproduces B's states and B's table map).
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
        let mut add = |key: u128, value: u64| {
            let h = digest_mix64(
                digest_mix64(key as u64 ^ 0x243F_6A88_85A3_08D3)
                    ^ digest_mix64((key >> 64) as u64 ^ 0x1319_8A2E_0370_7344)
                    ^ digest_mix64(value ^ 0xA409_3822_299F_31D0).rotate_left(1),
            );
            sum = sum.wrapping_add(h);
            xor ^= h.rotate_left(23);
            entries += 1;
        };
        match &index.compact {
            Some(compact) => {
                for &word in &compact.slots {
                    if word != 0 {
                        add(word & COMPACT_KEY_MASK, CompactRootTable128::expand(word));
                    }
                }
            }
            None => {
                for &(key, value) in &index.table.slots {
                    if key != u128::MAX {
                        add(key, value);
                    }
                }
            }
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
    mod stacked_tests {
        use super::*;

        const FOLDED: IndexMode128 = IndexMode128 { fold: true, plant: false, canon: INDEX_CANON_SELECTED };
        const PLANTED: IndexMode128 = IndexMode128 { fold: true, plant: true, canon: INDEX_CANON_SELECTED };
        const FOLDED_LIFT: IndexMode128 = IndexMode128 { fold: true, plant: false, canon: INDEX_CANON_LIFT };

        fn small_instance(
            columns: usize,
        ) -> (FastBinaryCurve128, Gf2_128, NormalBasis128, S3Solver128, Base128, Vec<u128>) {
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
            let base = Base128 { points, labels, by_x, columns };
            let basis = NormalBasis128::new(&gf);
            let solver = S3Solver128::new(&gf, b);
            (fast, gf, basis, solver, base, reps)
        }

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

        #[test]
        fn every_stacked_index_holds_the_reference_states_and_map() {
            let (_, gf, basis, solver, _, reps) = small_instance(9);
            let reference =
                build_index128_stacked(&gf, &basis, &solver, &reps, TABLE_BASE, 28, IndexMode128::UNFOLDED);
            let want = index_digest128(&reference, &basis);
            for (table, mode) in [
                (TABLE_BASE, FOLDED),
                (TABLE_BASE, PLANTED),
                (TABLE_COMPACT, IndexMode128::UNFOLDED),
                (TABLE_COMPACT, FOLDED),
                (TABLE_COMPACT, PLANTED),
                (TABLE_COMPACT, FOLDED_LIFT),
                (TABLE_FILTER, FOLDED),
            ] {
                let index = build_index128_stacked(&gf, &basis, &solver, &reps, table, 28, mode);
                assert_eq!(index.logical_states, reference.states.len());
                assert_eq!(index.root_entries(), reference.table.len);
                if mode.fold {
                    assert_eq!(index.states.len(), (9 * 9 * 83 - 9 * 83) / 2 + 9 * 42);
                }
                for logical in 0..reference.states.len() {
                    let a = &reference.states[logical];
                    let b = match &index.fold {
                        Some(fold) => fold_state128(&index, fold, &basis, logical),
                        None => {
                            let s = &index.states[logical];
                            State128 { left: s.left, right: s.right, relative: s.relative, normal_roots: s.normal_roots }
                        }
                    };
                    assert_eq!((a.left, a.right, a.relative, a.normal_roots),
                               (b.left, b.right, b.relative, b.normal_roots), "state {logical}");
                }
                for &(key, value) in &reference.table.slots {
                    if key != u128::MAX {
                        let got = match &index.compact {
                            Some(compact) => compact.get(key),
                            None => index.table.get(key),
                        };
                        assert_eq!(got, Some(value));
                        if let Some(filter) = &index.filter {
                            assert!(filter.contains(key), "filter false negative");
                        }
                    }
                }
                assert_eq!(index_digest128(&index, &basis), want);
            }
        }

        #[test]
        fn every_stacked_arm_finds_the_reference_relation() {
            let (fast, gf, basis, solver, base, reps) = small_instance(9);
            let build = |table, mode| build_index128_stacked(&gf, &basis, &solver, &reps, table, 28, mode);
            let reference = build(TABLE_BASE, IndexMode128::UNFOLDED);
            let base_fold = build(TABLE_BASE, FOLDED);
            let compact = build(TABLE_COMPACT, IndexMode128::UNFOLDED);
            let stack = build(TABLE_COMPACT, FOLDED);
            let planted = build(TABLE_COMPACT, PLANTED);
            let stack_lift = build(TABLE_COMPACT, FOLDED_LIFT);
            let filtered = build(TABLE_FILTER, FOLDED);
            let mut seed = 0x9E37_79B9_7F4A_7C15u64;
            let mut skipped_total = 0u64;
            let mut solved = 0usize;
            for trial in 0..24u64 {
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
                    ($c:expr, $o:expr, $p:expr, $index:expr) => {{
                        let mut clock = PhaseClock::start();
                        let mut split = ExtractSplit::default();
                        FOLD_AUDIT_PROBES.store(0, Ordering::Relaxed);
                        let relation = extract128::<{ $c }, { $o }, { $p }>(
                            &gf, &fast, &basis, &solver, $index, &base, target, start, &mut clock,
                            &mut split,
                        );
                        (relation.map(|r| ((r.point_indices, r.x_codes, r.intermediates), r.probes)),
                         split.skipped_symmetric_states, FOLD_AUDIT_PROBES.load(Ordering::Relaxed))
                    }};
                }
                macro_rules! compare {
                    ($c:expr, $o:expr) => {{
                        let (want, skipped, _) = run!($c, $o, PIPE_OFF, &reference);
                        assert_eq!(skipped, 0);
                        let (want, want_probes) = want.expect("a planted four-point target decomposes");
                        for (got, skipped, audit) in [
                            run!($c, $o, PIPE_PREFETCH, &reference),
                            run!($c, $o, PIPE_COMPACT, &compact),
                        ] {
                            assert_eq!(got, Some((want, want_probes)), "unfolded layout differs");
                            assert_eq!((skipped, audit), (0, 0));
                        }
                        let (folded, skipped, audit) = run!($c, $o, PIPE_COMPACT, &stack);
                        let (folded, folded_probes) = folded.unwrap();
                        assert_eq!(folded, want, "the stack's relation differs");
                        assert!(folded_probes <= want_probes);
                        assert_eq!(audit, 0);
                        skipped_total += skipped;
                        for (got, _, audit) in [
                            run!($c, $o, PIPE_OFF, &base_fold),
                            run!($c, $o, PIPE_PREFETCH, &base_fold),
                            run!($c, $o, PIPE_COMPACT, &stack_lift),
                            run!($c, $o, PIPE_FILTER, &filtered),
                        ] {
                            assert_eq!(got, Some((want, folded_probes)), "a folded arm differs");
                            assert_eq!(audit, 0);
                        }
                        let (got, _, audit) = run!($c, $o, PIPE_COMPACT, &planted);
                        assert_eq!(got, Some((want, folded_probes)));
                        assert_eq!(folded_probes + audit, want_probes, "planted probe identity");
                        solved += 1;
                    }};
                }
                compare!(CANON_LIFT, ORDER_FEISTEL);
                compare!(CANON_LIFT, ORDER_LEFT_MAJOR);
                compare!(CANON_FULL, ORDER_FEISTEL);
                compare!(CANON_FULL, ORDER_LEFT_MAJOR);
            }
            assert!(solved >= 80);
            assert!(skipped_total > 0, "the small instance should exercise the skip");
        }
    }
'''

SCAN_OLD = """        let mut probes = 0u64;
        let mut scan = StateScan128::new(gf.n);
"""
SCAN_NEW = """        let mut probes = 0u64;
        let mut scan = StateScan128::new(gf.n);
        if let Some(fold) = &index.fold {
            return extract128_folded::<C, O, P>(
                gf, fast, basis, solver, index, fold, base, target, target_x, start, &mut probes,
                &mut scan, clock, split,
            );
        }
"""

RUN_INDEX_OLD = """        let index = build_index128(&gf, &basis, &solver, &reps);
"""
RUN_INDEX_NEW = """        let (index_mode, index_canon_name) = index_mode_from_env();
        let index = build_index128(&gf, &basis, &solver, &reps, index_mode);
"""

RANK_GUARD_OLD = """        let cached_log_table = super::log_cache::input_path();
        assert!(
            index.root_table == TABLE_BASE || cached_log_table.is_some(),
            "KIC_ROOT_TABLE other than base needs the verified cached factor-log table"
        );
"""
RANK_GUARD_NEW = """        let cached_log_table = super::log_cache::input_path();
        // koblitz-n83-stacked-20261016: the rank stage's canonicalizer, order
        // and probe loop; `target` runs the arm's own layout loop.
        let (rank_canon_name, rank_order_name, rank_probe_name) = rank_selectors_from_env();
        let rank_loop = if rank_probe_name == "off" {
            PIPE_OFF
        } else {
            match index.root_table {
                TABLE_COMPACT => PIPE_COMPACT,
                TABLE_FILTER => PIPE_FILTER,
                TABLE_FILTER_PLANT => PIPE_FILTER_PLANT,
                _ => PIPE_PREFETCH,
            }
        };
        assert!(
            index.root_table == TABLE_BASE || rank_loop != PIPE_OFF || cached_log_table.is_some(),
            "KIC_ROOT_TABLE other than base needs KIC_RANK_PROBE=target or the verified cached factor-log table"
        );
"""

RANK_COUNTERS_OLD = """        let mut rank_root_calls = 0u64;
"""
RANK_COUNTERS_NEW = """        let mut rank_root_calls = 0u64;
        let mut rank_skipped_symmetric_states = 0u64;
        let mut rank_attempt_probes: Vec<Option<u64>> = Vec::new();
        let mut rank_attempt_ns: Vec<u64> = Vec::new();
        let mut rank_relations_hasher = blake3::Hasher::new();
        rank_relations_hasher.update(b"n83-stacked-rank-relations-v1");
"""

RANK_EXTRACT_OLD = """            let relation = extract128::<CANON_FULL, ORDER_LEFT_MAJOR, PIPE_OFF>(
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
"""
RANK_EXTRACT_NEW = """            macro_rules! rank_extract {
                ($c:expr, $o:expr, $p:expr) => {
                    extract128::<{ $c }, { $o }, { $p }>(
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
            let relation = match (rank_canon_name, rank_order_name, rank_loop) {
                ("full", "left_major", _) => rank_extract!(CANON_FULL, ORDER_LEFT_MAJOR, PIPE_OFF),
                ("full", _, _) => rank_extract!(CANON_FULL, ORDER_FEISTEL, PIPE_OFF),
                (_, "left_major", _) => rank_extract!(CANON_LIFT, ORDER_LEFT_MAJOR, PIPE_OFF),
                (_, _, PIPE_OFF) => rank_extract!(CANON_LIFT, ORDER_FEISTEL, PIPE_OFF),
                (_, _, PIPE_PREFETCH) => rank_extract!(CANON_LIFT, ORDER_FEISTEL, PIPE_PREFETCH),
                (_, _, PIPE_COMPACT) => rank_extract!(CANON_LIFT, ORDER_FEISTEL, PIPE_COMPACT),
                (_, _, PIPE_FILTER) => rank_extract!(CANON_LIFT, ORDER_FEISTEL, PIPE_FILTER),
                _ => rank_extract!(CANON_LIFT, ORDER_FEISTEL, PIPE_FILTER_PLANT),
            };
            rank_pdp_elapsed += rank_split.pdp;
            rank_relation_check_elapsed += rank_split.relation_check;
            rank_root_calls += rank_split.root_calls;
            rank_skipped_symmetric_states += rank_split.skipped_symmetric_states;
            rank_attempt_probes.push(relation.as_ref().map(|relation| relation.probes));
            rank_attempt_ns.push(
                (query_elapsed + rank_split.pdp + rank_split.relation_check).as_nanos() as u64,
            );
            if let Some(relation) = &relation {
                rank_relations_hasher.update(&rank_attempts.to_le_bytes());
                for &point_index in &relation.point_indices {
                    rank_relations_hasher.update(&(point_index as u64).to_le_bytes());
                }
            }
"""

SELFTEST_OLD = """            .all(|&key| scan_permutation_selftest(index.states.len(), key));
"""
SELFTEST_NEW = """            .all(|&key| {
                scan_permutation_selftest(index.logical_states, key)
                    && (index.fold.is_none() || scan_inverse_selftest(index.logical_states, key))
            });
"""

AUDIT_RESET_OLD = """            VERIFY_LIFT_MISMATCHES.store(0, Ordering::Relaxed);
"""
AUDIT_RESET_NEW = """            VERIFY_LIFT_MISMATCHES.store(0, Ordering::Relaxed);
            FOLD_AUDIT_PROBES.store(0, Ordering::Relaxed);
"""

RECORD_OLD = """                "skipped_symmetric_states":split.skipped_symmetric_states,
"""
RECORD_NEW = """                "skipped_symmetric_states":split.skipped_symmetric_states,
                "fold_audit_probes":FOLD_AUDIT_PROBES.load(Ordering::Relaxed),
"""

DIGEST_OLD = """        let mut summary = json!({
"""
DIGEST_NEW = """        let index_digest = (std::env::var("KIC_INDEX_DIGEST").as_deref() == Ok("1"))
            .then(|| index_digest128(&index, &basis));
        let mut summary = json!({
"""

SUMMARY_OLD = """            "regular_states":index.states.len(),
"""
SUMMARY_NEW = """            "regular_states":index.logical_states,
            "stored_states":index.states.len(),
            "state_fold":index.fold.is_some(),
            "fold_plant":index.fold.as_ref().is_some_and(|fold| fold.plant),
            "index_canonicalizer":index_canon_name,
            "index_digest":index_digest,
            "rank_canonicalizer":rank_canon_name,
            "rank_order":rank_order_name,
            "rank_probe":rank_probe_name,
            "rank_skipped_symmetric_states":rank_skipped_symmetric_states,
            "rank_attempt_probes":rank_attempt_probes,
            "rank_attempt_ns":rank_attempt_ns,
            "rank_relations_blake3":rank_relations_hasher.finalize().to_hex().to_string(),
"""

SELFTEST_SUMMARY_OLD = """            "scan_order_selftest":{"states":index.states.len(), "keys":scan_selftest_keys.len(),
"""
SELFTEST_SUMMARY_NEW = """            "scan_order_selftest":{"states":index.logical_states, "keys":scan_selftest_keys.len(),
"""


def stack_edits(head, wide):
    head = replace(head, HEAD_OLD, HEAD_NEW)
    wide = replace(wide, INVERT_OLD, INVERT_NEW)
    wide = replace(wide, INDEX_OLD, INDEX_NEW)
    wide = replace(wide, BUILD_OLD, BUILD_NEW)
    wide = replace(wide, STATES_OLD, STATES_NEW)
    wide = replace(wide, TABLE_OLD, TABLE_NEW)
    wide = replace(wide, CANON_OLD, CANON_NEW, count=2)
    wide = replace(wide, LITERAL_OLD, LITERAL_NEW + STACK_CODE + "\n    fn lift128(\n")
    wide = replace(wide, SCAN_OLD, SCAN_NEW)
    wide = replace(wide, RUN_INDEX_OLD, RUN_INDEX_NEW)
    wide = replace(wide, RANK_GUARD_OLD, RANK_GUARD_NEW)
    wide = replace(wide, RANK_COUNTERS_OLD, RANK_COUNTERS_NEW)
    wide = replace(wide, RANK_EXTRACT_OLD, RANK_EXTRACT_NEW)
    wide = replace(wide, SELFTEST_OLD, SELFTEST_NEW)
    wide = replace(wide, AUDIT_RESET_OLD, AUDIT_RESET_NEW)
    wide = replace(wide, RECORD_OLD, RECORD_NEW)
    wide = replace(wide, DIGEST_OLD, DIGEST_NEW)
    wide = replace(wide, SUMMARY_OLD, SUMMARY_NEW)
    wide = replace(wide, SELFTEST_SUMMARY_OLD, SELFTEST_SUMMARY_NEW)
    return head, wide


def tablefilter_text():
    text = tablefilter.derive(tablefilter.probepipe_text())
    digest = hashlib.sha256(text.encode()).hexdigest()
    if digest != TABLEFILTER_SHA256:
        raise ValueError("table-filter derivation differs from koblitz-n83-tablefilter-20261015's frozen producer: "
                         + digest)
    return text


def derive(text):
    head, rest = text.split(WIDE_START, 1)
    wide, tail = rest.split(WIDE_END, 1)
    head, wide = stack_edits(head, wide)
    return head + WIDE_START + wide + WIDE_END + tail


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = derive(tablefilter_text())
    if args.check:
        if OUTPUT.read_text() != text:
            raise SystemExit("derived online source differs from " + str(OUTPUT))
    else:
        OUTPUT.write_text(text)
    print("online_source_sha256=" + hashlib.sha256(text.encode()).hexdigest())


if __name__ == "__main__":
    sys.exit(main())
