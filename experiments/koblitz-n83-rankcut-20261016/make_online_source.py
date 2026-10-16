#!/usr/bin/env python3
"""Derive the rank-cut n=83 K600 producer from the stacked producer, exactly.

Input: `snapshots/r770/examples/koblitz_orbit_dlp_fast_online_logcache.rs`
(crypto 770f6a69 plus B's `ic_log_cache.patch`, restored and digest-checked
by `restore.py`).

1. `make_stacked_source.py` is `koblitz-n83-stacked-20261016`'s
   `make_online_source.py` (main, PR #938), verbatim, with its verbatim
   parents (`make_tablefilter_source.py`, `make_probepipe_source.py`,
   `make_combined_source.py`). Its derived text must hash to the stacked
   protocol's frozen `online_source_sha256` (`STACKED_SHA256` below). That is
   the stacked producer (arms cS / kS of run 38862448935, the current n = 83
   baseline).
2. `rankcut_edits`: counted, exact replacements in the wide module add one
   selector, `KIC_RANK_SOLVE`, read only by the rank stage:

   * `s3` (default): the stack's rank stage, unchanged (the compact loop,
     `PIPE_COMPACT`).
   * `padd`: the rank stage's probe loop gets each candidate's two partner
     roots by point addition instead of the S3 root solve. For a stored root
     with normal-basis x `xn` the loop recovers its y once per state (one
     inversion and one half-trace per root: `y = x * HT(x + a + b/x^2)`),
     then, for every Frobenius shift `s`, `R_s = (x^(2^s), y^(2^s))` (two
     table maps) and one batched inversion of `x(T) + x(R_s)` give both
     `x(T + R_s)` and `x(T - R_s)`: `lambda = (y(T) + y(R_s)) / D`,
     `lambda' = lambda + x(R_s) / D`, `x = lambda^2 + lambda + x(T) + x(R_s) + a`,
     written directly in the normal basis (squaring is a rotation there).
     These are the two roots of `S3(x(R_s), x(T), X)`, the S3 loop's partner
     pair, as a set. The keys are emitted in the order (T - R, T + R); at
     every root-table hit the candidate's exact S3 pair is recomputed with
     the S3 solver, the two emitted values are asserted equal to it as a
     set, and the pair is re-evaluated in the S3 order with the S3 loop's
     probe positions. So the probe count, the first hit, the lift and the
     relation are those of the S3 loop by construction, whatever the order
     rule. Inputs where the S3 solve itself is exceptional
     (`x(R_s) = x(T)`, `x(R_s) = 0` or `x(T) = 0`) are solved by the S3
     solver; a state whose root fails the curve check (never for a genuine
     state) falls back to the compact loop.
   * `padd_plant` (planted positive control): `padd`, plus the removed
     work redone: the S3 batch solve and both partners' normal-basis maps on
     every candidate, compared with the point-addition pair as a set on
     every input (a panic on any difference) and otherwise discarded.

   The summary records `rank_solve` and the loop's counters
   (`rank_padd_*`). Every other path (setup, index, online target scan) is
   the stacked producer's, byte for byte.

`--check` regenerates and requires byte identity with the existing output.
"""

import argparse
import hashlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_stacked_source as stacked  # noqa: E402  (koblitz-n83-stacked-20261016, verbatim)

EXAMPLES = HERE / "snapshots" / "r770" / "examples"
OUTPUT = EXAMPLES / "koblitz_orbit_dlp_fast_online_rankcut.rs"
# protocol.json "sources.online_source_sha256" of koblitz-n83-stacked-20261016 (main).
STACKED_SHA256 = "83b589880e5bbd80b2dcf0debf7d20ab268877d4de409c71cf5da17b2f62563c"
WIDE_START = stacked.WIDE_START
WIDE_END = stacked.WIDE_END
replace = stacked.replace

HEAD_OLD = """// KIC_RANK_PROBE) so the rank stage runs on the compact table in process.
"""
HEAD_NEW = HEAD_OLD + """// koblitz-n83-rankcut-20261016: derived from the stacked producer by
// make_online_source.py; adds KIC_RANK_SOLVE (s3 | padd | padd_plant), the
// rank stage's partner roots by point addition, exact to the S3 loop.
"""

SCRATCH_OLD = """        keys: Vec<ProbeKey128>,
        survivors: Vec<u32>,
    }
"""
SCRATCH_NEW = """        keys: Vec<ProbeKey128>,
        survivors: Vec<u32>,
        padd: PaddScratch128,
    }
"""

SCRATCH_INIT_OLD = """                survivors: Vec::with_capacity(2 * entries),
"""
SCRATCH_INIT_NEW = """                survivors: Vec::with_capacity(2 * entries),
                padd: PaddScratch128::with_capacity(entries),
"""

RANKCUT_CODE = r'''
    // koblitz-n83-rankcut-20261016: the rank stage's partner roots by point
    // addition (KIC_RANK_SOLVE). `PIPE_PADD_SWAPPED` emits each pair in the
    // other order; the tests use it to force the exact-order resolution.
    const PIPE_PADD: u8 = 5;
    const PIPE_PADD_PLANT: u8 = 6;
    const PIPE_PADD_SWAPPED: u8 = 7;

    static PADD_FALLBACK_STATES: AtomicU64 = AtomicU64::new(0);
    static PADD_IRREGULAR_INPUTS: AtomicU64 = AtomicU64::new(0);
    static PADD_RESOLVED_HITS: AtomicU64 = AtomicU64::new(0);
    static PADD_SWAPPED_PAIRS: AtomicU64 = AtomicU64::new(0);
    static PADD_PLANT_CHECKED: AtomicU64 = AtomicU64::new(0);

    /// `KIC_RANK_SOLVE`: the rank stage's partner-root solve.
    fn rank_solve_from_env() -> (u8, &'static str) {
        match std::env::var("KIC_RANK_SOLVE").as_deref() {
            Err(_) | Ok("") | Ok("s3") => (PIPE_COMPACT, "s3"),
            Ok("padd") => (PIPE_PADD, "padd"),
            Ok("padd_plant") => (PIPE_PADD_PLANT, "padd_plant"),
            Ok(other) => panic!("unknown KIC_RANK_SOLVE {other}"),
        }
    }

    /// Per-state scratch of [`scan_state128_padd`].
    struct PaddScratch128 {
        ys: Vec<u128>,
        prefix: Vec<u128>,
        inverse: Vec<u128>,
        regular: Vec<bool>,
        pair_start: Vec<u32>,
    }

    impl PaddScratch128 {
        fn with_capacity(entries: usize) -> Self {
            Self {
                ys: Vec::with_capacity(entries),
                prefix: Vec::with_capacity(entries),
                inverse: Vec::with_capacity(entries),
                regular: Vec::with_capacity(entries),
                pair_start: Vec::with_capacity(entries),
            }
        }
    }

    /// The normal-basis y of a point of E with normal-basis x `xn`
    /// (`y = x * HT(x + a + b / x^2)`), or `None` when `x = 0` or `x` is not
    /// the x of a point of E over the field.
    #[inline(always)]
    fn padd_root_y(
        gf: &Gf2_128,
        basis: &NormalBasis128,
        solver: &S3Solver128,
        a: u128,
        xn: u128,
    ) -> Option<u128> {
        let xp = basis.to_poly.apply(xn);
        if xp == 0 {
            return None;
        }
        let xi = invert128(gf, basis, xp);
        let rhs = xp ^ a ^ gf.mul(solver.b, gf.sqr(xi));
        if (rhs & solver.trace_mask).count_ones() & 1 == 1 {
            return None;
        }
        let u = solver.half_trace.apply(rhs);
        Some(basis.to_normal.apply(gf.mul(xp, u)))
    }

    /// [`scan_state128_filtered`] (`PIPE_COMPACT`) with the partner roots by
    /// point addition: the same candidates (shift outer, stored root inner),
    /// the same keys and probe positions, the same first hit and relation.
    /// At every root-table hit the candidate's S3 pair is recomputed and the
    /// pair is evaluated in the S3 order, so the result does not depend on
    /// the emission order.
    #[inline(always)]
    #[allow(clippy::too_many_arguments)]
    fn scan_state128_padd<const C: u8, const P: u8>(
        gf: &Gf2_128,
        fast: &FastBinaryCurve128,
        basis: &NormalBasis128,
        solver: &S3Solver128,
        index: &Index128,
        base: &Base128,
        target: FastPoint128,
        target_x: u128,
        state: &State128,
        scan: &mut StateScan128,
        probes: &mut u64,
        clock: &mut PhaseClock,
        split: &mut ExtractSplit,
    ) -> Option<Relation128> {
        let n = gf.n;
        let compact = index.compact.as_ref().expect("the compact root table");
        let (tx, ty) = target.expect("a target point");
        debug_assert_eq!(tx, target_x);
        let a = fast.a;
        let roots = state.normal_roots.len();
        let mut yn = [0u128; 2];
        for (k, &root) in state.normal_roots.iter().enumerate() {
            match padd_root_y(gf, basis, solver, a, root) {
                Some(y) => yn[k] = y,
                None => {
                    PADD_FALLBACK_STATES.fetch_add(1, Ordering::Relaxed);
                    return scan_state128_filtered::<C, PIPE_COMPACT>(
                        gf, fast, basis, solver, index, base, target, target_x, state, scan,
                        probes, clock, split,
                    );
                }
            }
        }
        scan.inputs.clear();
        let pad = &mut scan.padd;
        pad.ys.clear();
        pad.prefix.clear();
        pad.regular.clear();
        let mut product = 1u128;
        for shift in 0..n {
            for k in 0..roots {
                let xs = basis.to_poly.apply(basis.rotate(state.normal_roots[k], shift));
                let ys = basis.to_poly.apply(basis.rotate(yn[k], shift));
                // Exactly the S3 batch's exceptional inputs (zero denominator).
                let regular = xs != tx && xs != 0 && tx != 0;
                scan.inputs.push((xs, tx));
                pad.ys.push(ys);
                pad.prefix.push(product);
                pad.regular.push(regular);
                if regular {
                    product = gf.mul(product, xs ^ tx);
                }
            }
        }
        split.root_calls += scan.inputs.len() as u64;
        let count = scan.inputs.len();
        pad.inverse.clear();
        pad.inverse.resize(count, 0);
        // A product of non-zero field elements is non-zero.
        let mut inverse = invert128(gf, basis, product);
        for i in (0..count).rev() {
            if pad.regular[i] {
                pad.inverse[i] = gf.mul(inverse, pad.prefix[i]);
                inverse = gf.mul(inverse, scan.inputs[i].0 ^ tx);
            }
        }
        let normal_c = basis.to_normal.apply(tx ^ a);
        scan.keys.clear();
        pad.pair_start.clear();
        for i in 0..count {
            let xs = scan.inputs[i].0;
            let pair: [u128; 2] = if pad.regular[i] {
                let lambda = basis.to_normal.apply(gf.mul(ty ^ pad.ys[i], pad.inverse[i]));
                let lambda2 = lambda ^ basis.to_normal.apply(gf.mul(xs, pad.inverse[i]));
                let c = normal_c ^ basis.rotate(state.normal_roots[i % roots], (i / roots) as u32);
                let plus = basis.rotate(lambda, 1) ^ lambda ^ c;
                let minus = basis.rotate(lambda2, 1) ^ lambda2 ^ c;
                if P == PIPE_PADD_SWAPPED { [plus, minus] } else { [minus, plus] }
            } else {
                PADD_IRREGULAR_INPUTS.fetch_add(1, Ordering::Relaxed);
                match solver.roots(gf, basis, xs, tx) {
                    Some([first, second]) => {
                        [basis.to_normal.apply(first), basis.to_normal.apply(second)]
                    }
                    None => {
                        pad.pair_start.push(u32::MAX);
                        continue;
                    }
                }
            };
            pad.pair_start.push(scan.keys.len() as u32);
            for partner in pair {
                let (canonical, partner_shift) = target_canonical::<C>(basis, partner);
                compact.prefetch(canonical);
                scan.keys.push(ProbeKey128 {
                    canonical,
                    partner,
                    partner_shift,
                    candidate: i as u32,
                });
            }
        }
        if P == PIPE_PADD_PLANT {
            // The removed work, redone and discarded: the S3 batch solve and
            // both partners' normal-basis maps, compared with the pair.
            scan.batch.solve(gf, basis, solver, &scan.inputs);
            for (i, result) in scan.batch.results.iter().enumerate() {
                let start = pad.pair_start[i];
                match *result {
                    Some([first, second]) => {
                        let s3 = [
                            black_box(basis.to_normal.apply(first)),
                            black_box(basis.to_normal.apply(second)),
                        ];
                        assert_ne!(start, u32::MAX, "S3 found a pair the point addition did not");
                        let got = [scan.keys[start as usize].partner, scan.keys[start as usize + 1].partner];
                        assert!(
                            got == s3 || got == [s3[1], s3[0]],
                            "point-addition partners differ from the S3 roots"
                        );
                    }
                    None => assert_eq!(start, u32::MAX, "point addition found a pair S3 did not"),
                }
            }
            PADD_PLANT_CHECKED.fetch_add(count as u64, Ordering::Relaxed);
        }
        let first = *probes;
        let passes = split.filter_passes;
        let len = scan.keys.len();
        let mut position = 0usize;
        while position < len {
            *probes = first + position as u64 + 1;
            split.filter_passes = passes + position as u64 + 1;
            if compact.get(scan.keys[position].canonical).is_none() {
                position += 1;
                continue;
            }
            // First hit in this candidate's pair: evaluate the pair in the S3
            // order, at the S3 loop's probe positions.
            let candidate = scan.keys[position].candidate as usize;
            let start = pad.pair_start[candidate] as usize;
            let order = if pad.regular[candidate] {
                PADD_RESOLVED_HITS.fetch_add(1, Ordering::Relaxed);
                let exact = solver
                    .roots(gf, basis, scan.inputs[candidate].0, tx)
                    .expect("the S3 roots of a regular candidate");
                let emitted = [
                    basis.to_poly.apply(scan.keys[start].partner),
                    basis.to_poly.apply(scan.keys[start + 1].partner),
                ];
                if emitted == exact {
                    [start, start + 1]
                } else {
                    assert_eq!([emitted[1], emitted[0]], exact,
                               "point-addition partners differ from the S3 roots");
                    PADD_SWAPPED_PAIRS.fetch_add(1, Ordering::Relaxed);
                    [start + 1, start]
                }
            } else {
                [start, start + 1]
            };
            for (rank, &at) in order.iter().enumerate() {
                let exact_position = start + rank;
                if at < position {
                    // Emitted before this hit and already looked up: a miss.
                    continue;
                }
                *probes = first + exact_position as u64 + 1;
                split.filter_passes = passes + exact_position as u64 + 1;
                let key = scan.keys[at];
                let Some(value) = compact.get(key.canonical) else {
                    continue;
                };
                let shift = candidate / roots;
                let left_x = index.shifted[state.left as usize][shift];
                let right_x =
                    index.shifted[state.right as usize][(shift + state.relative as usize) % n as usize];
                let (left2, right2, relative2, stored_shift) = unpack(value);
                let left_shift2 = ((stored_shift + n - key.partner_shift) % n) as usize;
                let right_shift2 = (left_shift2 + relative2) % n as usize;
                let codes = [
                    left_x,
                    right_x,
                    index.shifted[left2][left_shift2],
                    index.shifted[right2][right_shift2],
                ];
                split.pdp += clock.lap();
                let lifted = lift128(fast, base, &codes, target);
                split.relation_check += clock.lap();
                split.relation_checks += 1;
                if let Some(point_indices) = lifted {
                    return Some(Relation128 {
                        point_indices,
                        x_codes: codes,
                        intermediates: [scan.inputs[candidate].0, basis.to_poly.apply(key.partner)],
                        probes: *probes,
                    });
                }
            }
            position = start + 2;
        }
        *probes = first + len as u64;
        split.filter_passes = passes + len as u64;
        None
    }

    #[cfg(test)]
    mod rankcut_tests {
        use super::*;

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
        fn point_addition_pairs_are_the_s3_roots() {
            let (fast, gf, basis, solver, base, _) = small_instance(9);
            let mut seed = 0x0123_4567_89AB_CDEFu64;
            let mut checked = 0u64;
            let mut first_is_minus = 0u64;
            for _ in 0..4000 {
                seed = digest_mix64(seed);
                let r = base.points[(seed % base.points.len() as u64) as usize];
                seed = digest_mix64(seed);
                let t = fast.add(r, base.points[(seed % base.points.len() as u64) as usize]);
                let (Some((rx, ry)), Some((tx, ty))) = (r, t) else { continue };
                if rx == tx {
                    continue;
                }
                let exact = solver.roots(&gf, &basis, rx, tx).expect("S3 roots of two points");
                let plus = fast.add(t, r).unwrap().0;
                let minus = fast.add(t, FastBinaryCurve128::neg(r)).unwrap().0;
                assert!(exact == [plus, minus] || exact == [minus, plus]);
                first_is_minus += (exact[0] == minus) as u64;
                // The recovered y gives the same pair (either sign of y).
                let y = basis.to_poly.apply(padd_root_y(&gf, &basis, &solver, fast.a, basis.to_normal.apply(rx)).unwrap());
                assert!(y == ry || y == (rx ^ ry));
                let _ = ty;
                checked += 1;
            }
            assert!(checked > 3000);
            eprintln!("first root is x(T - R) in {first_is_minus} of {checked}");
        }

        #[test]
        fn padd_loops_find_the_s3_relation_with_the_s3_probes() {
            let (fast, gf, basis, solver, base, reps) = small_instance(9);
            const FOLDED: IndexMode128 = IndexMode128 { fold: true, plant: false, canon: INDEX_CANON_SELECTED };
            let stack = build_index128_stacked(&gf, &basis, &solver, &reps, TABLE_COMPACT, 28, FOLDED);
            let unfolded =
                build_index128_stacked(&gf, &basis, &solver, &reps, TABLE_COMPACT, 28, IndexMode128::UNFOLDED);
            let mut seed = 0xA076_1D64_78BD_642Fu64;
            let mut solved = 0usize;
            let swapped_before = PADD_SWAPPED_PAIRS.load(Ordering::Relaxed);
            for trial in 0..40u64 {
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
                    ($o:expr, $p:expr, $index:expr) => {{
                        let mut clock = PhaseClock::start();
                        let mut split = ExtractSplit::default();
                        let relation = extract128::<CANON_LIFT, { $o }, { $p }>(
                            &gf, &fast, &basis, &solver, $index, &base, target, start, &mut clock,
                            &mut split,
                        );
                        (relation.map(|r| ((r.point_indices, r.x_codes, r.intermediates), r.probes)),
                         split.root_calls, split.relation_checks)
                    }};
                }
                for (order, index) in [(ORDER_FEISTEL, &stack), (ORDER_LEFT_MAJOR, &stack), (ORDER_FEISTEL, &unfolded)] {
                    macro_rules! compare {
                        ($o:expr) => {{
                            let want = run!($o, PIPE_COMPACT, index);
                            assert!(want.0.is_some(), "a planted four-point target decomposes");
                            for got in [run!($o, PIPE_PADD, index), run!($o, PIPE_PADD_PLANT, index),
                                        run!($o, PIPE_PADD_SWAPPED, index)] {
                                assert_eq!(got, want, "a point-addition loop differs from the S3 loop");
                            }
                            solved += 1;
                        }};
                    }
                    if order == ORDER_FEISTEL { compare!(ORDER_FEISTEL) } else { compare!(ORDER_LEFT_MAJOR) }
                }
            }
            assert!(solved >= 100);
            assert!(PADD_SWAPPED_PAIRS.load(Ordering::Relaxed) > swapped_before,
                    "the swapped loop must exercise the exact-order resolution");
            assert!(PADD_PLANT_CHECKED.load(Ordering::Relaxed) > 0);
        }
    }

'''

SELECT_DOC_OLD = """    /// `P` picks the target scan's probe loop at compile time.
"""
SELECT_DOC_NEW = RANKCUT_CODE + SELECT_DOC_OLD

SELECT_OLD = """        if P >= PIPE_COMPACT {
            scan_state128_filtered::<C, P>(
"""
SELECT_NEW = """        if P >= PIPE_PADD {
            return scan_state128_padd::<C, P>(
                gf, fast, basis, solver, index, base, target, target_x, state, scan, probes, clock,
                split,
            );
        }
        if P >= PIPE_COMPACT {
            scan_state128_filtered::<C, P>(
"""

RANK_SOLVE_OLD = """            "KIC_ROOT_TABLE other than base needs KIC_RANK_PROBE=target or the verified cached factor-log table"
        );
"""
RANK_SOLVE_NEW = RANK_SOLVE_OLD + """        // koblitz-n83-rankcut-20261016: the rank stage's partner-root solve.
        let (rank_solve, rank_solve_name) = rank_solve_from_env();
        assert!(
            rank_solve == PIPE_COMPACT || rank_loop == PIPE_COMPACT,
            "KIC_RANK_SOLVE=padd runs with KIC_ROOT_TABLE=compact and KIC_RANK_PROBE=target"
        );
        let rank_loop = if rank_solve == PIPE_COMPACT { rank_loop } else { rank_solve };
        for counter in [&PADD_FALLBACK_STATES, &PADD_IRREGULAR_INPUTS, &PADD_RESOLVED_HITS,
                        &PADD_SWAPPED_PAIRS, &PADD_PLANT_CHECKED] {
            counter.store(0, Ordering::Relaxed);
        }
"""

RANK_MATCH_OLD = """                (_, _, PIPE_COMPACT) => rank_extract!(CANON_LIFT, ORDER_FEISTEL, PIPE_COMPACT),
"""
RANK_MATCH_NEW = RANK_MATCH_OLD + """                (_, _, PIPE_PADD) => rank_extract!(CANON_LIFT, ORDER_FEISTEL, PIPE_PADD),
                (_, _, PIPE_PADD_PLANT) => rank_extract!(CANON_LIFT, ORDER_FEISTEL, PIPE_PADD_PLANT),
"""

SUMMARY_OLD = """            "rank_probe":rank_probe_name,
"""
SUMMARY_NEW = SUMMARY_OLD + """            "rank_solve":rank_solve_name,
            "rank_padd_fallback_states":PADD_FALLBACK_STATES.load(Ordering::Relaxed),
            "rank_padd_irregular_inputs":PADD_IRREGULAR_INPUTS.load(Ordering::Relaxed),
            "rank_padd_resolved_hits":PADD_RESOLVED_HITS.load(Ordering::Relaxed),
            "rank_padd_swapped_pairs":PADD_SWAPPED_PAIRS.load(Ordering::Relaxed),
            "rank_padd_plant_checked_inputs":PADD_PLANT_CHECKED.load(Ordering::Relaxed),
"""


def rankcut_edits(head, wide):
    head = replace(head, HEAD_OLD, HEAD_NEW)
    wide = replace(wide, SCRATCH_OLD, SCRATCH_NEW)
    wide = replace(wide, SCRATCH_INIT_OLD, SCRATCH_INIT_NEW)
    wide = replace(wide, SELECT_DOC_OLD, SELECT_DOC_NEW)
    wide = replace(wide, SELECT_OLD, SELECT_NEW)
    wide = replace(wide, RANK_SOLVE_OLD, RANK_SOLVE_NEW)
    wide = replace(wide, RANK_MATCH_OLD, RANK_MATCH_NEW)
    wide = replace(wide, SUMMARY_OLD, SUMMARY_NEW)
    return head, wide


def stacked_text():
    text = stacked.derive(stacked.tablefilter_text())
    digest = hashlib.sha256(text.encode()).hexdigest()
    if digest != STACKED_SHA256:
        raise ValueError("stacked derivation differs from koblitz-n83-stacked-20261016's frozen producer: "
                         + digest)
    return text


def derive(text):
    head, rest = text.split(WIDE_START, 1)
    wide, tail = rest.split(WIDE_END, 1)
    head, wide = rankcut_edits(head, wide)
    return head + WIDE_START + wide + WIDE_END + tail


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = derive(stacked_text())
    if args.check:
        if OUTPUT.read_text() != text:
            raise SystemExit("derived online source differs from " + str(OUTPUT))
    else:
        OUTPUT.write_text(text)
    print("online_source_sha256=" + hashlib.sha256(text.encode()).hexdigest())


if __name__ == "__main__":
    sys.exit(main())
