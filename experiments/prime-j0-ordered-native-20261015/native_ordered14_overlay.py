#!/usr/bin/env python3
"""Build the ordered prime-norm radix-14 Rust candidate from a pinned parent."""

from hashlib import sha256
from pathlib import Path
import sys

PARENT_SHA256 = "aff42df465e44e2f3fe1d10c524b6a336a76c5091791894cac5cba618cc441ee"


def replace_span(source, start, end, replacement):
    assert source.count(start) == 1, (start, source.count(start))
    left = source.index(start)
    right = source.index(end, left)
    return source[:left] + replacement + source[right:]


def once(source, old, new):
    assert source.count(old) == 1, (old[:80], source.count(old))
    return source.replace(old, new)


def main(root):
    path = root / "src/bin/eisenstein_fixed/unit_orbit_windows.rs"
    original = path.read_text()
    assert sha256(original.encode()).hexdigest() == PARENT_SHA256
    start = original.index("const SPLIT_PRIME_NORM: i32 = 71023;")
    end = original.index("\npub(super) fn warm_mixed640_pretau_table()", start)
    section = original[start:end]

    section = replace_span(section, "const SPLIT_PRIME_NORM: i32 = 71023;",
        "\nimpl Signed192 {", """const SPLIT_PRIME_STEPS: usize = 14;
const SPLIT_PRIME_RADICES: [i32; 14] =
    [394, 380, 380, 371, 371, 371, 371, 371, 371, 371, 371, 371, 371, 371];
const SPLIT_PRIME_ATLAS_FOR_WINDOW: [usize; 14] =
    [0, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2];
const SPLIT_PRIME_TERMINAL_LIMIT: usize = 399;
""")

    section = replace_span(section, "fn nearest_split_prime_digit(residue: i32)",
        "\nfn orbit_omega_pair", """fn nearest_split_prime_digit(residue: i32, radix: i32, norm: i32) -> (i16, i16) {
    if residue == 0 { return (0, 0); }
    let mut best = (i32::MAX, i32::MAX, i32::MAX, i32::MAX, i32::MAX);
    for lift in [residue, residue-norm] {
        let center = ((2*radix-3)*lift+norm).div_euclid(2*norm);
        for b in [center-1, center, center+1] {
            let a = lift-radix*b;
            let value = a*a+3*a*b+3*b*b;
            let score = (value,b.abs(),a.abs(),a,b);
            if score < best { best = score; }
        }
    }
    (i16::try_from(best.3).unwrap(), i16::try_from(best.4).unwrap())
}

fn split_prime_unit_step(
    a: Signed192, b: Signed192, window: usize, tables: &SplitPrimeTables,
) -> (Signed192, Signed192, usize, usize) {
    let atlas = &tables.digit_atlases[SPLIT_PRIME_ATLAS_FOR_WINDOW[window]];
    let radix = atlas.radix;
    let norm = atlas.norm;
    let residue_word = a.add(b.times_split_prime_small(radix));
    let (quotient, signed_rem, residue) = residue_word.div_rem_small_radix(norm as u64);
    let negative = residue > (norm as usize)/2;
    let index = if negative { norm as usize - residue as usize } else { residue as usize };
    let (raw_da, raw_db) = atlas.digit_pairs[index];
    let da = if negative { -i32::from(raw_da) } else { i32::from(raw_da) };
    let db = if negative { -i32::from(raw_db) } else { i32::from(raw_db) };
    let digit_residue = da + radix*db;
    let t = (digit_residue - residue as i32) / norm;
    assert_eq!((digit_residue - residue as i32) % norm, 0);
    let adjustment = if signed_rem < 0 { -1 } else { 0 } - t;
    let k = quotient.add(Signed192::from_i32(adjustment));
    let shifted_b = b.sub(Signed192::from_i32(db));
    let next_a = k.times_split_prime_small(radix-3).sub(shifted_b);
    (next_a, k, index, usize::from(negative))
}
""")

    section = replace_span(section, "struct SplitPrimeTables {",
        "\nstatic SPLIT_PRIME_TABLES:", """struct SplitPrimeDigitAtlas {
    radix: i32,
    norm: i32,
    max_norm: i32,
    digit_pairs: Box<[(i16, i16)]>,
    digit_codes: Box<[(u16, u8)]>,
}

struct SplitPrimeTables {
    digit_atlases: Vec<SplitPrimeDigitAtlas>,
    digit_windows: Vec<Box<[U256Affine]>>,
    terminal_pairs: Box<[U256Affine]>,
    terminal_codes: Box<[(u16,u8)]>,
    retained_bytes: usize,
}

impl SplitPrimeTables {
    fn new() -> Self {
        let specs = [(394, 154057, 51091, 25677),
                     (380, 143263, 47628, 23878),
                     (371, 136531, 45387, 22756)];
        let mut digit_atlases = Vec::with_capacity(specs.len());
        let mut seed_rows = Vec::with_capacity(specs.len());
        for (radix,norm,expected_max_norm,expected_seeds) in specs {
            let digit_pairs = (0..=norm/2)
                .map(|r| nearest_split_prime_digit(r,radix,norm))
                .collect::<Vec<_>>().into_boxed_slice();
            assert_eq!(digit_pairs.len(), (norm as usize+1)/2);
            let max_norm = digit_pairs.iter().map(|&(a,b)| {
                let a = i32::from(a); let b = i32::from(b);
                a*a+3*a*b+3*b*b
            }).max().unwrap();
            assert_eq!(max_norm,expected_max_norm);
            let digit_set = digit_pairs.iter().copied().map(orbit_canonical)
                .collect::<std::collections::BTreeSet<_>>();
            let mut digit_seeds = digit_set.into_iter().collect::<Vec<_>>();
            digit_seeds.retain(|&pair| pair != (0,0));
            digit_seeds.insert(0,(0,0));
            assert_eq!(digit_seeds.len(),expected_seeds);
            let digit_ids = digit_seeds.iter().enumerate()
                .map(|(index,&pair)| (pair,index as u16))
                .collect::<std::collections::BTreeMap<_,_>>();
            let digit_codes = digit_pairs.iter().copied().map(|pair| {
                let seed = orbit_canonical(pair);
                (digit_ids[&seed],orbit_code(pair,seed))
            }).collect::<Vec<_>>().into_boxed_slice();
            digit_atlases.push(SplitPrimeDigitAtlas {
                radix,norm,max_norm,digit_pairs,digit_codes
            });
            seed_rows.push(digit_seeds);
        }
        let mut base = Jacobian::generator();
        let mut digit_windows = Vec::with_capacity(SPLIT_PRIME_STEPS);
        for window in 0..SPLIT_PRIME_STEPS {
            let atlas = SPLIT_PRIME_ATLAS_FOR_WINDOW[window];
            digit_windows.push(build_u256_window(&seed_rows[atlas],base));
            let radix = SPLIT_PRIME_RADICES[window];
            assert_eq!(radix,digit_atlases[atlas].radix);
            let ordinary = affine_multiples(base,radix as usize).pop().unwrap();
            let tau = base.tau().neg().into_affine();
            base = ordinary.add_mixed(tau).into_affine();
        }
        let mut terminal_pairs_full = Vec::new();
        for a in -399..=399i32 {
            for b in -399..=399i32 {
                let norm = a*a+3*a*b+3*b*b;
                if norm < 40000 { terminal_pairs_full.push((a as i16,b as i16)); }
            }
        }
        assert_eq!(terminal_pairs_full.len(),145045);
        let terminal_set = terminal_pairs_full.iter().copied().map(orbit_canonical)
            .collect::<std::collections::BTreeSet<_>>();
        let mut terminal_seeds = terminal_set.into_iter().collect::<Vec<_>>();
        terminal_seeds.retain(|&pair| pair != (0,0));
        terminal_seeds.insert(0,(0,0));
        assert_eq!(terminal_seeds.len(),24175);
        let terminal_ids = terminal_seeds.iter().enumerate()
            .map(|(index,&pair)| (pair,index as u16))
            .collect::<std::collections::BTreeMap<_,_>>();
        let mut terminal_codes = vec![(u16::MAX,0u8);799*799];
        for pair in terminal_pairs_full.iter().copied() {
            let seed = orbit_canonical(pair);
            let index = ((i32::from(pair.0)+399)*799+i32::from(pair.1)+399) as usize;
            terminal_codes[index]=(terminal_ids[&seed],orbit_code(pair,seed));
        }
        let terminal_codes = terminal_codes.into_boxed_slice();
        let terminal_pairs = build_u256_window(&terminal_seeds,base);
        let entries = digit_windows.iter().map(|row| row.len()).sum::<usize>();
        assert_eq!(entries,323749);
        assert_eq!(size_of::<U256Affine>(),64);
        let retained_bytes = (entries+terminal_pairs.len())*size_of::<U256Affine>()
            + digit_atlases.iter().map(|atlas|
                atlas.digit_pairs.len()*size_of::<(i16,i16)>()
                + atlas.digit_codes.len()*size_of::<(u16,u8)>()).sum::<usize>()
            + terminal_codes.len()*size_of::<(u16,u8)>()
            + size_of::<[super::U256;3]>() + size_of::<Self>()
            + digit_windows.capacity()*size_of::<Box<[U256Affine]>>()
            + digit_atlases.capacity()*size_of::<SplitPrimeDigitAtlas>();
        Self { digit_atlases,digit_windows,terminal_pairs,
               terminal_codes,retained_bytes }
    }
}
""")

    section = once(section, "split_prime_unit_step(a,b,tables)",
                   "split_prime_unit_step(a,b,window,tables)")
    section = once(section, "let (seed,code) = tables.digit_codes[index];",
        "let (seed,code) = tables.digit_atlases[SPLIT_PRIME_ATLAS_FOR_WINDOW[window]].digit_codes[index];")
    section = once(section, "assert!(terminal_norm < 6724,\"nearest-digit norm-71023 terminal bound\");",
                   "assert!(terminal_norm < 40000,\"ordered prime-norm terminal bound\");")
    section = once(section, "((signed_a+163)*327+signed_b+163)",
                   "((signed_a+399)*799+signed_b+399)")
    section = replace_span(section,
        "    #[test]\n    fn radix_71023_digit_residues_exhaustive()",
        "\n    #[test]\n    fn radix_71023_holdout_matches_independent_binary()", """    #[test]
    fn ordered14_digit_residues_exhaustive() {
        let tables=&*SPLIT_PRIME_TABLES;
        for atlas in &tables.digit_atlases {
            for residue in 0..atlas.norm {
                let negative=residue > atlas.norm/2;
                let index=if negative { (atlas.norm-residue) as usize }
                          else { residue as usize };
                let (a,b)=atlas.digit_pairs[index];
                let (a,b)=if negative { (-i32::from(a),-i32::from(b)) }
                          else { (i32::from(a),i32::from(b)) };
                assert_eq!((a+atlas.radix*b-residue).rem_euclid(atlas.norm),0);
                assert!(a*a+3*a*b+3*b*b <= atlas.max_norm);
            }
        }
        println!("ordered14_residues={}",
                 tables.digit_atlases.iter().map(|a| a.norm).sum::<i32>());
    }
""")
    section = once(section, "fn radix_71023_holdout_matches_independent_binary()",
                   "fn ordered14_holdout_matches_independent_binary()")
    section = once(section, "radix_71023_holdout_cases={}", "ordered14_holdout_cases={}")
    output = original[:start]+section+original[end:]
    path.write_text(output)
    print(sha256(output.encode()).hexdigest())


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: native_ordered14_overlay.py CARGO_ROOT")
    main(Path(sys.argv[1]))
