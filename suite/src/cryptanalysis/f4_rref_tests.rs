//! Exact reference checks and opt-in, paired kernel measurements.
use super::*;
use serde_json::json;
use std::{hint::black_box, time::Instant};

// Frozen verbatim from 466e8b651002ad11e5de996619f9aaaedb5ac551,
// except for the name. Keep the old indexing and full-width XOR loop.
fn reference(matrix: &mut [Vec<u64>], n_cols: usize, word_ops: &mut u64) -> usize {
    let words = n_cols.div_ceil(64);
    let mut pivot_row = 0usize;
    for c in 0..n_cols {
        let (w, bit) = (c / 64, 1u64 << (c % 64));
        let piv = (pivot_row..matrix.len()).find(|&r| matrix[r][w] & bit != 0);
        let piv = match piv {
            Some(p) => p,
            None => continue,
        };
        matrix.swap(pivot_row, piv);
        for r in 0..matrix.len() {
            if r != pivot_row && matrix[r][w] & bit != 0 {
                for k in 0..words {
                    matrix[r][k] ^= matrix[pivot_row][k];
                }
                *word_ops += words as u64;
            }
        }
        pivot_row += 1;
        if pivot_row == matrix.len() {
            break;
        }
    }
    pivot_row
}

fn next(state: &mut u64) -> u64 {
    // SplitMix64 output mixing avoids the rank-64 cap of a linear xorshift
    // stream when successive output words are arranged as matrix rows.
    *state = state.wrapping_add(0x9e3779b97f4a7c15);
    let mut z = *state;
    z = (z ^ (z >> 30)).wrapping_mul(0xbf58476d1ce4e5b9);
    z = (z ^ (z >> 27)).wrapping_mul(0x94d049bb133111eb);
    z ^ (z >> 31)
}

fn synthetic(rows: usize, cols: usize, kind: &str, mut seed: u64) -> Vec<Vec<u64>> {
    let mut out = vec![vec![0; cols.div_ceil(64)]; rows];
    for row in &mut out {
        for word in row.iter_mut() {
            *word = next(&mut seed);
            if kind == "sparse" {
                *word &= next(&mut seed) & next(&mut seed) & next(&mut seed);
            }
        }
        if !cols.is_multiple_of(64) {
            *row.last_mut().unwrap() &= (1u64 << (cols % 64)) - 1;
        }
    }
    if kind == "deficient" {
        for r in rows / 2..rows {
            out[r] = out[r - rows / 2].clone();
        }
    }
    out
}

fn check(matrix: &[Vec<u64>], cols: usize) {
    let mut a = matrix.to_vec();
    let mut b = matrix.to_vec();
    // The counted API accumulates rather than replacing a caller's counter.
    let (mut old_ops, mut new_ops) = (7, 7);
    let rank = reference(&mut a, cols, &mut old_ops);
    assert_eq!(rank, rref_f2_counted(&mut b, cols, &mut new_ops));
    assert_eq!(a, b, "full RREF, including nonpivot rows and padding");
    assert!(new_ops <= old_ops);
    let mut previous = None;
    for r in 0..rank {
        let pivot = (0..cols)
            .find(|&c| b[r][c / 64] & (1 << (c % 64)) != 0)
            .unwrap();
        assert!(previous.is_none_or(|p| p < pivot));
        assert!((0..b.len()).all(|s| s == r || b[s][pivot / 64] & (1 << (pivot % 64)) == 0));
        previous = Some(pivot);
    }
    assert!(b[rank..]
        .iter()
        .all(|row| (0..cols).all(|c| row[c / 64] & (1 << (c % 64)) == 0)));
}

#[test]
fn rref_matches_reference_across_shapes_and_word_boundaries() {
    for rows in [0, 1, 2, 7, 65, 129] {
        for cols in [0usize, 1, 2, 63, 64, 65, 127, 128, 129, 257] {
            check(&vec![vec![0; cols.div_ceil(64)]; rows], cols);
            for kind in ["dense", "sparse", "deficient"] {
                for seed in [17, 937, 20260914] {
                    check(&synthetic(rows, cols, kind, seed), cols);
                }
            }
        }
    }
}

#[test]
fn rref_skips_zero_prefix_words_and_preserves_padding() {
    // Pivots start beyond a full empty word, including a skipped-column gap.
    let input = vec![vec![0, 2, u64::MAX], vec![0, 2, 6], vec![0, 0, 4]];
    check(&input, 131);
    let mut a = input.clone();
    let mut b = input;
    let (mut old, mut new) = (0, 0);
    reference(&mut a, 131, &mut old);
    rref_f2_counted(&mut b, 131, &mut new);
    assert!(new < old);
}

#[test]
fn macaulay_row_count_matches_the_materialised_rows() {
    // includes products that cancel to zero (`x0·(x0x1 + x1)` = 0), which
    // neither count may include
    let mut x = 0x2545_f491_4f6c_dd1du64;
    let mut next = move || {
        x ^= x << 13;
        x ^= x >> 7;
        x ^= x << 17;
        x
    };
    for n_vars in [4usize, 7, 10] {
        let mut polys: Vec<F2BoolPoly> = (0..n_vars)
            .map(|_| {
                let monos: Vec<F2BoolMono> = (0..6)
                    .map(|_| F2BoolMono::from_mask(next() & next() & ((1 << n_vars) - 1)))
                    .collect();
                F2BoolPoly::from_monos(monos, n_vars)
            })
            .filter(|p| !p.is_zero())
            .collect();
        polys.push(F2BoolPoly::from_monos(
            vec![F2BoolMono::from_mask(0b11), F2BoolMono::from_mask(0b10)],
            n_vars,
        ));
        for degree in 1..=4 {
            let rows = macaulay_rows_monos(&polys, n_vars, degree).map(|r| r.len());
            assert_eq!(macaulay_row_count(&polys, n_vars, degree), rows);
        }
    }
}

#[test]
fn m4ri_parallel_table_application_matches_the_serial_one() {
    // threshold 0 sends every block through the parallel path; the rows,
    // the rank and the word count must be the serial implementation's
    let mut scratch = F4M4riScratch::default();
    for (rows, cols) in [(129usize, 257usize), (300, 700)] {
        for kind in ["dense", "sparse", "deficient"] {
            for seed in [17, 937] {
                let input = synthetic(rows, cols, kind, seed);
                for reduce_above in [false, true] {
                    let mut allocating = input.clone();
                    let mut parallel = input.clone();
                    let (mut allocating_ops, mut parallel_ops) = (0, 0);
                    let allocating_rank = echelon_f2_m4ri_allocating_counted(
                        &mut allocating,
                        cols,
                        &mut allocating_ops,
                        4,
                        reduce_above,
                    );
                    let parallel_rank = echelon_f2_m4ri_arena_counted_with(
                        &mut parallel,
                        cols,
                        &mut parallel_ops,
                        4,
                        reduce_above,
                        &mut scratch,
                        0,
                    );
                    assert_eq!(parallel_rank, allocating_rank);
                    assert_eq!(parallel_ops, allocating_ops);
                    assert_eq!(parallel, allocating);
                }
            }
        }
    }
}

#[test]
fn m4ri_arena_matches_the_allocating_implementation() {
    let mut scratch = F4M4riScratch::default();
    for (rows, cols) in [(129usize, 257usize), (257, 511)] {
        for kind in ["dense", "sparse", "deficient"] {
            for seed in [17, 937] {
                let input = synthetic(rows, cols, kind, seed);
                for block_width in [2, 3, 4, 5] {
                    for reduce_above in [false, true] {
                        let mut allocating = input.clone();
                        let mut arena = input.clone();
                        let mut allocating_ops = 0;
                        let mut arena_ops = 0;
                        let allocating_rank = echelon_f2_m4ri_allocating_counted(
                            &mut allocating,
                            cols,
                            &mut allocating_ops,
                            block_width,
                            reduce_above,
                        );
                        let arena_rank = echelon_f2_m4ri_arena_counted(
                            &mut arena,
                            cols,
                            &mut arena_ops,
                            block_width,
                            reduce_above,
                            &mut scratch,
                        );
                        assert_eq!(arena_rank, allocating_rank);
                        assert_eq!(arena_ops, allocating_ops);
                        assert_eq!(arena, allocating);
                    }
                }
            }
        }
    }
}

fn m4ri_bench_repeats() -> usize {
    std::env::var("KIC_F4_M4RI_BENCH_REPEATS")
        .ok()
        .and_then(|value| value.parse::<usize>().ok())
        .unwrap_or(20)
}

fn run_paired_m4ri_case(
    input: &[Vec<u64>],
    cols: usize,
    reduce_above: bool,
    phase: &str,
    case: &str,
    seed: u64,
    extra: serde_json::Value,
    scratch: &mut F4M4riScratch,
) {
    let input_hash = blake3::hash(&serde_json::to_vec(input).unwrap())
        .to_hex()
        .to_string();
    let mut allocating = input.to_vec();
    let mut arena = input.to_vec();
    let (mut allocating_ops, mut arena_ops) = (0, 0);
    let allocating_rank = echelon_f2_m4ri_allocating_counted(
        &mut allocating,
        cols,
        &mut allocating_ops,
        4,
        reduce_above,
    );
    let arena_rank =
        echelon_f2_m4ri_arena_counted(&mut arena, cols, &mut arena_ops, 4, reduce_above, scratch);
    assert_eq!(
        (arena_rank, arena_ops, &arena),
        (allocating_rank, allocating_ops, &allocating)
    );

    for rep in 0..m4ri_bench_repeats() {
        let mut allocating = input.to_vec();
        let mut arena = input.to_vec();
        let mut ns = [0u128; 2];
        let mut ops = [0u64; 2];
        let mut ranks = [0usize; 2];
        for variant in if rep % 2 == 0 { [0, 1] } else { [1, 0] } {
            let started = Instant::now();
            ranks[variant] = if variant == 0 {
                echelon_f2_m4ri_allocating_counted(
                    black_box(&mut allocating),
                    cols,
                    &mut ops[variant],
                    4,
                    reduce_above,
                )
            } else {
                echelon_f2_m4ri_arena_counted(
                    black_box(&mut arena),
                    cols,
                    &mut ops[variant],
                    4,
                    reduce_above,
                    scratch,
                )
            };
            ns[variant] = started.elapsed().as_nanos();
        }
        assert_eq!((ranks[0], ops[0], &allocating), (ranks[1], ops[1], &arena));
        let mut row = json!({
            "phase": phase, "case": case, "seed": seed, "rep": rep,
            "rows": input.len(), "cols": cols, "reduce_above": reduce_above,
            "input_hash": input_hash, "allocating_ns": ns[0], "arena_ns": ns[1],
            "word_ops": ops[0], "rank": ranks[0], "correct": true,
        });
        row.as_object_mut()
            .unwrap()
            .extend(extra.as_object().unwrap().clone());
        println!("{row}");
    }
}

#[test]
#[ignore = "paired release benchmark for M4RI allocation policies"]
fn paired_m4ri_arena_benchmark() {
    let mut scratch = F4M4riScratch::default();
    for (rows, cols, kind, seed) in [
        (129usize, 257usize, "sparse", 17u64),
        (257, 511, "dense", 937),
        (512, 768, "deficient", 20260914),
    ] {
        let input = synthetic(rows, cols, kind, seed);
        for reduce_above in [false, true] {
            run_paired_m4ri_case(
                &input,
                cols,
                reduce_above,
                "m4ri-arena-kernel",
                &format!("{kind}-{rows}x{cols}"),
                seed,
                json!({}),
                &mut scratch,
            );
        }
    }
}

#[test]
#[ignore = "paired release benchmark on Semaev root matrices"]
fn paired_m4ri_semaev_root_benchmark() {
    let mut scratch = F4M4riScratch::default();
    for (n, ell, seed) in [
        (13u32, 12usize, 17u64),
        (19, 18, 937),
        (23, 11, 20260914),
        (31, 16, 66142),
    ] {
        let fe = |x| F2mElement::from_biguint(&num_bigint::BigUint::from(x), n);
        let structure = FieldStructure::new(
            n,
            &crate::cryptanalysis::koblitz_index_calculus::find_irreducible(n).unwrap(),
        );
        let basis: Vec<_> = (0..ell).map(|bit| fe(1u64 << bit)).collect();
        let system = build_decomposition_system(&basis, &fe(seed), &fe(1), 2, &structure).unwrap();
        let rows = macaulay_rows_monos_with_mask(
            &system.equations,
            system.n_vars,
            3,
            occurring_vars(&system.equations),
            None,
        )
        .unwrap();
        let columns = macaulay_columns(&rows).unwrap();
        let input = pack_rows(&rows, &columns);
        run_paired_m4ri_case(
            &input,
            columns.len(),
            system.n_vars < 24,
            "m4ri-arena-semaev-root",
            &format!("binary-n{n}-ell{ell}-m2-d3"),
            seed,
            json!({"variables":system.n_vars,"generators":system.equations.len()}),
            &mut scratch,
        );
    }
}

#[test]
fn solver_linear_tail_matches_full_rref_row_space_intersection() {
    for rows in [0, 1, 7, 65, 129] {
        for cols in [1usize, 63, 64, 65, 129, 257] {
            let low_width = cols.min(33);
            let low_start = cols - low_width;
            for kind in ["dense", "sparse", "deficient"] {
                for seed in [17, 937, 20260914] {
                    let input = synthetic(rows, cols, kind, seed);
                    let mut full = input.clone();
                    let mut candidate = input.clone();
                    let mut full_ops = 0;
                    let full_rank = rref_f2_counted(&mut full, cols, &mut full_ops);
                    let mut candidate_ops = 0;
                    let (low, low_rank) =
                        f4_solver_linear_tail(&mut candidate, cols, low_start, &mut candidate_ops);

                    let words_per_row = cols.div_ceil(64);
                    let mut flat = FlatF2Matrix {
                        data: input.iter().flatten().copied().collect(),
                        rows,
                        words: words_per_row,
                    };
                    let mut flat_ops = 0;
                    let (flat_low, flat_rank) =
                        f4_solver_linear_tail_flat(&mut flat, cols, low_start, &mut flat_ops);
                    assert_eq!(flat_rank, low_rank);
                    assert_eq!(&flat_low[..flat_rank], &low[..low_rank]);

                    let words = low_width.div_ceil(64).max(1);
                    let mut expected = Vec::new();
                    for source in full.iter().take(full_rank) {
                        let has_high = (0..low_start)
                            .any(|column| source[column / 64] & (1u64 << (column % 64)) != 0);
                        if has_high {
                            continue;
                        }
                        let mut row = vec![0u64; words];
                        for column in low_start..cols {
                            if source[column / 64] & (1u64 << (column % 64)) != 0 {
                                let target = column - low_start;
                                row[target / 64] |= 1u64 << (target % 64);
                            }
                        }
                        if row.iter().any(|&word| word != 0) {
                            expected.push(row);
                        }
                    }
                    assert_eq!(low_rank, expected.len());
                    assert_eq!(&low[..low_rank], expected.as_slice());
                }
            }
        }
    }
}

#[test]
fn masked_multiplier_schedule_matches_the_full_schedule() {
    for n_vars in 0..=12 {
        for degree in 0..=4 {
            assert_eq!(
                monomials_up_to_mask(all_variable_mask(n_vars), degree),
                monomials_up_to(n_vars, degree),
            );
        }
    }
}

#[test]
fn cached_layout_requires_exact_column_support() {
    let columns = vec![3u64, 2, 1, 0];
    let layout = F4ColumnLayout::new(columns);
    assert!(pack_rows_with_layout(&[vec![3, 0], vec![2, 1]], &layout, true).is_some());
    assert!(pack_rows_with_layout(&[vec![3, 0], vec![2]], &layout, true).is_none());
    assert!(pack_rows_with_layout(&[vec![4]], &layout, true).is_none());
}

#[test]
fn inherited_root_layout_cache_matches_uncached_builds() {
    let n_vars = 8;
    let systems = [
        vec![
            F2BoolPoly::from_monos(
                vec![
                    F2BoolMono::from_mask(0b0000_0011),
                    F2BoolMono::from_mask(0b0001_0100),
                    F2BoolMono::var(6),
                    F2BoolMono::one(),
                ],
                n_vars,
            ),
            F2BoolPoly::from_monos(
                vec![
                    F2BoolMono::from_mask(0b1010_0100),
                    F2BoolMono::from_mask(0b0100_1000),
                    F2BoolMono::var(1),
                ],
                n_vars,
            ),
        ],
        vec![
            F2BoolPoly::from_monos(
                vec![
                    F2BoolMono::from_mask(0b1000_0010),
                    F2BoolMono::from_mask(0b0001_0101),
                    F2BoolMono::var(6),
                ],
                n_vars,
            ),
            F2BoolPoly::from_monos(
                vec![
                    F2BoolMono::from_mask(0b0010_1100),
                    F2BoolMono::from_mask(0b0100_0001),
                    F2BoolMono::var(1),
                    F2BoolMono::one(),
                ],
                n_vars,
            ),
        ],
    ];
    F4_LAYOUTS.with(|layouts| layouts.borrow_mut().clear());
    for degree in [2, 3, 4] {
        for system in &systems {
            let mask = occurring_vars(system);
            assert_eq!(mask, 0xff);
            let uncached =
                build_inherited_macaulay_with_layout(system, n_vars, degree, mask, false).unwrap();
            let cached =
                build_inherited_macaulay_with_layout(system, n_vars, degree, mask, true).unwrap();
            assert_eq!(cached, uncached);
            let layout = cached_f4_layout((mask, degree, false));
            let hit =
                build_inherited_macaulay_with_layout(system, n_vars, degree, mask, true).unwrap();
            assert_eq!(hit, uncached);
            if !uncached.1.is_empty() {
                let before = layout.expect("nonempty build retains its layout");
                let after = cached_f4_layout((mask, degree, false)).unwrap();
                assert!(
                    std::rc::Rc::ptr_eq(&before, &after),
                    "exact hit rebuilt the layout"
                );
                assert_eq!(after.columns, uncached.0);
            }
        }
    }
}

#[test]
fn cached_layouts_obey_changed_matrix_caps() {
    // Each child runs only this test: changing process environment cannot
    // race with other tests or with a policy OnceLock initialized elsewhere.
    const CHILD: &str = "KIC_F4_CAP_TEST_CHILD";
    let Ok(mode) = std::env::var(CHILD) else {
        for mode in [
            "inherited-fused",
            "inherited-materialized",
            "flat-fused",
            "flat-materialized",
        ] {
            let output = std::process::Command::new(std::env::current_exe().unwrap())
                .args([
                    "--exact",
                    "cryptanalysis::koblitz_groebner::rref_tests::cached_layouts_obey_changed_matrix_caps",
                    "--test-threads=1",
                ])
                .env(CHILD, mode)
                .env("KIC_F4_DISABLE_INHERIT_FUSED_PACK", if mode.ends_with("materialized") { "1" } else { "0" })
                .env("KIC_F4_DISABLE_FUSED_PACK", if mode.ends_with("materialized") { "1" } else { "0" })
                .output()
                .unwrap();
            assert!(
                output.status.success(),
                "{mode}: {}{}",
                String::from_utf8_lossy(&output.stdout),
                String::from_utf8_lossy(&output.stderr)
            );
        }
        return;
    };
    let polynomial = |masks: &[u64]| {
        vec![F2BoolPoly::from_monos(
            masks.iter().copied().map(F2BoolMono::from_mask).collect(),
            2,
        )]
    };
    let wide = polynomial(&[0, 1, 2, 3]);
    let small = polynomial(&[1, 2, 3]);
    let build = |system: &[F2BoolPoly], reuse| {
        if mode.starts_with("inherited") {
            build_inherited_macaulay_with_layout(system, 2, 2, 3, reuse)
        } else {
            build_macaulay_flat_with_multiplier_mask(system, 2, 2, 3, reuse, RowCriterion::None)
                .map(|built| {
                    let rows = if built.matrix.words == 0 {
                        Vec::new()
                    } else {
                        built
                            .matrix
                            .data
                            .chunks_exact(built.matrix.words)
                            .map(<[u64]>::to_vec)
                            .collect()
                    };
                    (built.columns, rows)
                })
        }
    };
    std::env::set_var("F4_F2_MAX_ROWS", "1");
    std::env::set_var("F4_F2_MAX_COLS", "4");
    F4_LAYOUTS.with(|layouts| layouts.borrow_mut().clear());
    let expected = build(&wide, false).unwrap();
    assert_eq!(build(&wide, true).unwrap(), expected); // cold cache
    assert_eq!(build(&wide, true).unwrap(), expected); // exact-cap hit

    std::env::set_var("F4_F2_MAX_COLS", "3");
    assert!(build(&wide, false).is_none());
    assert!(
        build(&wide, true).is_none(),
        "warm cache bypassed the current column cap"
    );
    let smaller = build(&small, false).unwrap();
    assert_eq!(
        build(&small, true).unwrap(),
        smaller,
        "oversized old layout must allow a smaller rebuild"
    );
    assert_eq!(build(&small, true).unwrap(), smaller);

    std::env::set_var("F4_F2_MAX_ROWS", "0");
    assert!(build(&small, false).is_none());
    assert!(build(&small, true).is_none());
    std::env::set_var("F4_F2_MAX_ROWS", "1");
    std::env::set_var("F4_F2_MAX_COLS", "4");
    assert_eq!(
        build(&wide, true).unwrap(),
        expected,
        "raising caps must restore construction"
    );
}

#[test]
fn fused_flat_packing_matches_materialized_rows() {
    let n_vars = 8;
    let polynomials = vec![
        F2BoolPoly::from_monos(
            vec![
                F2BoolMono::from_mask(0b0000_0011),
                F2BoolMono::from_mask(0b0001_0100),
                F2BoolMono::var(6),
                F2BoolMono::one(),
            ],
            n_vars,
        ),
        F2BoolPoly::from_monos(
            vec![
                F2BoolMono::from_mask(0b0010_0100),
                F2BoolMono::from_mask(0b0100_1000),
                F2BoolMono::var(1),
            ],
            n_vars,
        ),
    ];
    let multiplier_mask = occurring_vars(&polynomials);
    for degree in [2, 3, 4] {
        let rows =
            macaulay_rows_monos_with_mask(&polynomials, n_vars, degree, multiplier_mask, None)
                .unwrap();
        let columns = macaulay_columns(&rows).unwrap();
        let layout = F4ColumnLayout::new(columns);
        let materialized_nested = pack_rows_with_layout(&rows, &layout, true).unwrap();
        let fused_nested =
            pack_polynomials_nested_fused(&polynomials, n_vars, degree, multiplier_mask, &layout)
                .unwrap();
        assert_eq!(fused_nested, materialized_nested);
        let materialized = pack_rows_flat_with_layout(&rows, &layout, true).unwrap();
        let fused =
            pack_polynomials_flat_fused(&polynomials, n_vars, degree, multiplier_mask, &layout)
                .unwrap();
        assert_eq!(fused.rows, materialized.rows);
        assert_eq!(fused.words, materialized.words);
        assert_eq!(fused.data, materialized.data);

        let mut missing_columns = layout.columns.clone();
        missing_columns.pop();
        let missing = F4ColumnLayout::new(missing_columns);
        assert!(pack_polynomials_nested_fused(
            &polynomials,
            n_vars,
            degree,
            multiplier_mask,
            &missing,
        )
        .is_none());
        assert!(pack_polynomials_flat_fused(
            &polynomials,
            n_vars,
            degree,
            multiplier_mask,
            &missing,
        )
        .is_none());

        let mut extra_columns = layout.columns.clone();
        extra_columns.push(1u64 << 63);
        let extra = F4ColumnLayout::new(extra_columns);
        assert!(pack_polynomials_nested_fused(
            &polynomials,
            n_vars,
            degree,
            multiplier_mask,
            &extra,
        )
        .is_none());
        assert!(
            pack_polynomials_flat_fused(&polynomials, n_vars, degree, multiplier_mask, &extra,)
                .is_none()
        );
    }
}

#[test]
#[ignore = "paired release benchmark for inherited-root fused packing"]
fn paired_inherited_root_fused_packing_benchmark() {
    let repeats = std::env::var("KIC_F4_FUSED_BENCH_REPEATS")
        .ok()
        .and_then(|value| value.parse::<usize>().ok())
        .unwrap_or(50);
    for (n, ell, seed) in [
        (13u32, 12usize, 17u64),
        (19, 18, 937),
        (23, 11, 20260914),
        (31, 16, 66142),
    ] {
        let fe = |x| F2mElement::from_biguint(&num_bigint::BigUint::from(x), n);
        let structure = FieldStructure::new(
            n,
            &crate::cryptanalysis::koblitz_index_calculus::find_irreducible(n).unwrap(),
        );
        let basis: Vec<_> = (0..ell).map(|bit| fe(1u64 << bit)).collect();
        let system = build_decomposition_system(&basis, &fe(seed), &fe(1), 2, &structure).unwrap();
        let mask = occurring_vars(&system.equations);
        let rows =
            macaulay_rows_monos_with_mask(&system.equations, system.n_vars, 3, mask, None).unwrap();
        let layout = F4ColumnLayout::new(macaulay_columns(&rows).unwrap());
        let fixture_hash =
            blake3::hash(&serde_json::to_vec(&(&system.equations, &layout.columns)).unwrap())
                .to_hex()
                .to_string();
        for rep in 0..repeats {
            let mut elapsed = [0u128; 2];
            let mut matrices = [None, None];
            for variant in if rep % 2 == 0 { [0, 1] } else { [1, 0] } {
                let started = Instant::now();
                matrices[variant] = Some(if variant == 0 {
                    let rows = macaulay_rows_monos_with_mask(
                        black_box(&system.equations),
                        system.n_vars,
                        3,
                        mask,
                        None,
                    )
                    .unwrap();
                    pack_rows_with_layout(&rows, &layout, true).unwrap()
                } else {
                    pack_polynomials_nested_fused(
                        black_box(&system.equations),
                        system.n_vars,
                        3,
                        mask,
                        &layout,
                    )
                    .unwrap()
                });
                elapsed[variant] = started.elapsed().as_nanos();
            }
            assert_eq!(matrices[0], matrices[1]);
            println!(
                "{}",
                json!({
                    "phase":"inherited-root-fused-pack",
                    "case":format!("binary-n{n}-ell{ell}-m2-d3"),
                    "seed":seed,
                    "rep":rep,
                    "variables":system.n_vars,
                    "generators":system.equations.len(),
                    "rows":matrices[0].as_ref().unwrap().len(),
                    "cols":layout.columns.len(),
                    "fixture_hash":fixture_hash,
                    "materialized_ns":elapsed[0],
                    "fused_ns":elapsed[1],
                    "correct":true,
                })
            );
        }
    }
}

#[test]
fn fast_column_index_matches_standard_hashing() {
    let mut columns = Vec::new();
    let mut state = 0x9e3779b97f4a7c15u64;
    for _ in 0..2048 {
        state = state.wrapping_add(0x9e3779b97f4a7c15);
        let mut value = state;
        value = (value ^ (value >> 30)).wrapping_mul(0xbf58476d1ce4e5b9);
        value = (value ^ (value >> 27)).wrapping_mul(0x94d049bb133111eb);
        columns.push(value ^ (value >> 31));
    }
    columns.sort_unstable();
    columns.dedup();
    let standard: std::collections::HashMap<u64, usize> = columns
        .iter()
        .enumerate()
        .map(|(column, &monomial)| (monomial, column))
        .collect();
    let mut fast = FastColumnMap::with_capacity_and_hasher(
        columns.len(),
        std::hash::BuildHasherDefault::default(),
    );
    fast.extend(
        columns
            .iter()
            .enumerate()
            .map(|(column, &monomial)| (monomial, column)),
    );
    for monomial in &columns {
        assert_eq!(fast.get(monomial), standard.get(monomial));
    }
    assert_eq!(fast.get(&0xDEADBEEF), standard.get(&0xDEADBEEF));
}

#[test]
#[ignore = "paired release benchmark; run via research/f4_linear_algebra_20260914/run.py"]
fn paired_kernel_benchmark() {
    let contract: serde_json::Value = serde_json::from_str(include_str!(
        "../../fixtures/f4_linear_algebra_contract.json"
    ))
    .unwrap();
    let repeats = contract["kernel"]["paired_repetitions"].as_u64().unwrap();
    for seed in [17, 937] {
        let mut cases = Vec::new();
        for spec in contract["kernel"]["synthetic"].as_array().unwrap() {
            let rows = spec[0].as_u64().unwrap() as usize;
            let cols = spec[1].as_u64().unwrap() as usize;
            let kind = spec[2].as_str().unwrap();
            let start = Instant::now();
            let matrix = synthetic(rows, cols, kind, seed);
            cases.push((
                format!("{kind}-{rows}x{cols}"),
                cols,
                matrix,
                start.elapsed().as_nanos(),
            ));
        }
        for spec in contract["kernel"]["macaulay"].as_array().unwrap() {
            let n = spec[0].as_u64().unwrap() as u32;
            let ell = spec[1].as_u64().unwrap() as usize;
            let m = spec[2].as_u64().unwrap() as usize;
            let degree = spec[3].as_u64().unwrap() as u32;
            let start = Instant::now();
            let fe = |x| F2mElement::from_biguint(&num_bigint::BigUint::from(x), n);
            let st = FieldStructure::new(
                n,
                &crate::cryptanalysis::koblitz_index_calculus::find_irreducible(n).unwrap(),
            );
            let basis: Vec<_> = (0..ell).map(|k| fe(1u64 << k)).collect();
            let sys =
                build_decomposition_system(&basis, &fe(seed % (1 << n)), &fe(1), m, &st).unwrap();
            let (columns, matrix) = build_macaulay(&sys.equations, sys.n_vars, degree).unwrap();
            cases.push((
                format!("macaulay-n{n}-l{ell}-m{m}-d{degree}"),
                columns.len(),
                matrix,
                start.elapsed().as_nanos(),
            ));
        }
        for (name, cols, input, setup_ns) in cases {
            let input_hash = blake3::hash(&serde_json::to_vec(&input).unwrap())
                .to_hex()
                .to_string();
            check(&input, cols); // correctness and one untimed warmup per kernel
            for rep in 0..repeats {
                let start = Instant::now();
                let mut a = input.clone();
                let mut b = input.clone();
                let copy_ns = start.elapsed().as_nanos();
                let mut ns = [0, 0];
                let mut ops = [0, 0];
                let mut ranks = [0, 0];
                for variant in if rep % 2 == 0 { [0, 1] } else { [1, 0] } {
                    let start = Instant::now();
                    ranks[variant] = if variant == 0 {
                        reference(black_box(&mut a), cols, &mut ops[variant])
                    } else {
                        rref_f2_counted(black_box(&mut b), cols, &mut ops[variant])
                    };
                    ns[variant] = start.elapsed().as_nanos();
                }
                let start = Instant::now();
                assert_eq!(ranks[0], ranks[1]);
                assert_eq!(a, b);
                let verification_ns = start.elapsed().as_nanos();
                println!(
                    "{}",
                    json!({"phase":"kernel","case":name,"seed":seed,"rep":rep,
                    "rows":input.len(),"cols":cols,"rank":ranks[0],"input_hash":input_hash,
                    "setup_ns":setup_ns,"copy_ns":copy_ns,"verification_ns":verification_ns,
                    "reference_ns":ns[0],"candidate_ns":ns[1],"reference_xors":ops[0],
                    "candidate_xors":ops[1],"correct":true})
                );
            }
        }
    }
}
