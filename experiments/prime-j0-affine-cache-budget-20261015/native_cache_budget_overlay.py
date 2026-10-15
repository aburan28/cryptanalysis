#!/usr/bin/env python3
"""Add a fixed 32 MiB-budget mixed affine/two-x scalar table."""

from hashlib import sha256
from pathlib import Path
import sys

WINDOWS_SHA256 = "50246c1c5174f4f38d37346118c92a1157fb2f72d98d10cec65ea549d52032ad"
FRONT_SHA256 = "abb8d153fe3d2956536a86f3d049cf4f783fd24ee6f7753d624b45cd6d96b416"


def main(root):
    windows = root / "src/bin/eisenstein_fixed/unit_orbit_windows.rs"
    front = root / "src/bin/eisenstein_fixed.rs"
    old_windows = windows.read_text()
    old_front = front.read_text()
    assert sha256(old_windows.encode()).hexdigest() == WINDOWS_SHA256
    assert sha256(old_front.encode()).hexdigest() == FRONT_SHA256

    tables = r'''
// The seven even-numbered digit windows use two-x rows. The remaining seven
// and the terminal row use ordinary affine entries. The fixed parity mask is
// independent of the benchmark fixture and keeps the retained table < 32 MiB.
struct SplitPrimeCacheBudgetTables {
    digit_pairs: Box<[(i16,i16)]>,
    digit_codes: Box<[(u16,u8)]>,
    digit_windows: Vec<Mixed640Column>,
    terminal_pairs: Box<[U256Affine]>,
    terminal_codes: Box<[(u16,u8)]>,
    retained_bytes: usize,
}

impl SplitPrimeCacheBudgetTables {
    fn new() -> Self {
        let ordinary = SplitPrimeTables::new();
        let SplitPrimeTables {
            digit_pairs,digit_codes,digit_windows,terminal_pairs,terminal_codes,
            retained_bytes: _,
        } = ordinary;
        let digit_windows = digit_windows.into_iter().enumerate().map(|(index,row)| {
            if index % 2 == 0 {
                Mixed640Column::Orbit(row.iter().copied()
                    .map(U256TwoXAffine::from_affine)
                    .collect::<Vec<_>>().into_boxed_slice())
            } else { Mixed640Column::Affine(row) }
        }).collect::<Vec<_>>();
        assert_eq!(digit_windows.len(), SPLIT_PRIME_STEPS);
        assert_eq!(digit_windows.iter().filter(|row|
            matches!(row,Mixed640Column::Orbit(_))).count(), 7);
        let retained_bytes = digit_windows.iter().map(Mixed640Column::payload_bytes)
            .sum::<usize>() + terminal_pairs.len()*size_of::<U256Affine>()
            + digit_pairs.len()*size_of::<(i16,i16)>()
            + (digit_codes.len()+terminal_codes.len())*size_of::<(u16,u8)>()
            + size_of::<[super::U256;3]>() + size_of::<Self>()
            + digit_windows.capacity()*size_of::<Mixed640Column>();
        assert!(retained_bytes < 32*1024*1024);
        Self { digit_pairs,digit_codes,digit_windows,terminal_pairs,
               terminal_codes,retained_bytes }
    }
}

static SPLIT_PRIME_CACHE_BUDGET_TABLES: LazyLock<SplitPrimeCacheBudgetTables> =
    LazyLock::new(SplitPrimeCacheBudgetTables::new);

pub(super) fn warm_split_prime_cache_budget_table() -> usize {
    std::sync::LazyLock::force(&super::EXACT_RECIPROCAL_CHECK);
    std::sync::LazyLock::force(&super::FIXED_SCALAR_LATTICE);
    SPLIT_PRIME_CACHE_BUDGET_TABLES.retained_bytes
}

fn split_prime_cache_budget_affine_leaves(scalar_words: [u64;4])
    -> [Option<U256Affine>; SPLIT_PRIME_STEPS+1] {
    let scalar = super::Uint(scalar_words);
    let residue = if bool::from(scalar.ct_lt(&super::SCALAR_ORDER_WORDS)) {
        scalar
    } else {
        super::U256::sbb(&scalar, &super::SCALAR_ORDER_WORDS).0
    };
    let (representative, fallback, corner) =
        super::hexagonal_certified_fixed_choice_words(residue.0);
    let tables = &*SPLIT_PRIME_CACHE_BUDGET_TABLES;
    let (mut a, mut b) = representative;
    let mut choices = [(0usize,0usize); SPLIT_PRIME_STEPS+1];
    for (window,_) in tables.digit_windows.iter().enumerate() {
        let (next_a,next_b,index,sign) = split_prime_unit_step(a,b,&tables.digit_pairs);
        a=next_a;
        b=next_b;
        if index != 0 {
            let (seed,code) = tables.digit_codes[index];
            choices[window]=(usize::from(seed),usize::from(code)^sign);
        }
    }
    let (ai,aneg) = a.split_prime_table_index(SPLIT_PRIME_TERMINAL_LIMIT);
    let (bi,bneg) = b.split_prime_table_index(SPLIT_PRIME_TERMINAL_LIMIT);
    let signed_a = if aneg { -(ai as i32) } else { ai as i32 };
    let signed_b = if bneg { -(bi as i32) } else { bi as i32 };
    let terminal_norm = signed_a*signed_a+3*signed_a*signed_b
        +3*signed_b*signed_b;
    assert!(terminal_norm < 49729,"nearest-digit norm-136531 terminal bound");
    if signed_a != 0 || signed_b != 0 {
        let index = ((signed_a+445)*891+signed_b+445) as usize;
        let (seed,code)=tables.terminal_codes[index];
        assert_ne!(seed,u16::MAX);
        choices[SPLIT_PRIME_STEPS]=(usize::from(seed),usize::from(code));
    }

    let mut leaves = [None;SPLIT_PRIME_STEPS+1];
    for (window,&(seed,unit)) in choices.iter().enumerate() {
        if seed == 0 { continue; }
        leaves[window] = Some(if window < SPLIT_PRIME_STEPS {
            tables.digit_windows[window].select(seed,unit)
        } else {
            tables.terminal_pairs[seed].unit_solinas(unit)
        });
    }
    leaves
}

pub(super) fn multiply_u256_tau_split_prime_cache_budget_affine_batch(
    scalar_words: &[[u64;4]],
) -> Vec<String> {
    let lanes = scalar_words.iter().map(|&words|
        split_prime_cache_budget_affine_leaves(words).into_iter().collect::<Vec<_>>())
        .collect::<Vec<_>>();
    affine_layer_reduce(lanes).into_iter().map(affine_layer_hex).collect()
}

'''
    test_start = old_windows.index("    #[test]\n    fn radix_136531_two_x_affine_batch_matches_independent_binary()")
    test_end = old_windows.index("\n    #[test]", test_start + 1)
    test = old_windows[test_start:test_end].replace("two_x_affine_batch", "cache_budget_affine_batch")
    test = test.replace("split_prime_two_x_affine_batch", "split_prime_cache_budget_affine_batch")
    test = test.replace("        assert_eq!(actual.len(),128);",
                        "        assert_eq!(actual.len(),128);\n"
                        "        assert!(warm_split_prime_cache_budget_table() < 32*1024*1024);")
    insertion = old_windows.index("#[cfg(test)]\nmod split_prime_tests")
    new_windows = old_windows[:insertion] + tables + old_windows[insertion:]
    needle = "mod split_prime_tests {\n    use super::*;"
    assert new_windows.count(needle) == 1
    new_windows = new_windows.replace(needle, needle + "\n\n" + test, 1)

    start = old_front.index("fn benchmark_mixed640_two_x_affine(")
    end = old_front.index("\nfn main()", start)
    benchmark = old_front[start:end]
    benchmark = benchmark.replace("two_x_affine", "cache_budget_affine")
    benchmark = benchmark.replace("two_x_table", "cache_budget_table")
    benchmark = benchmark.replace("affine_two_x_tree", "affine_cache_budget_tree")
    new_front = old_front[:end] + "\n" + benchmark + old_front[end:]
    dispatch = '''    if args.len() == 3 && args[0] == "--benchmark-split-prime-affine-cache-budget" {
        benchmark_mixed640_cache_budget_affine(
            args[2].parse().expect("batch repetitions"),
            args[1].parse().expect("batch size"));
        return;
    }
'''
    needle = "    let args: Vec<String> = std::env::args().skip(1).collect();\n"
    assert new_front.count(needle) == 1
    new_front = new_front.replace(needle, needle + dispatch, 1)
    windows.write_text(new_windows)
    front.write_text(new_front)
    print("windows_sha256=" + sha256(new_windows.encode()).hexdigest())
    print("front_sha256=" + sha256(new_front.encode()).hexdigest())


if __name__ == "__main__":
    main(Path(sys.argv[1]))
