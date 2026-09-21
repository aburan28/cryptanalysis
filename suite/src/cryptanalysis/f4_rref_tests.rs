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
