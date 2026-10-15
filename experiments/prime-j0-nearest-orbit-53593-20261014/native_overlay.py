#!/usr/bin/env python3
"""Apply the norm-53593 radix to the pinned 12211 rolling native source."""
from hashlib import sha256
from pathlib import Path
import sys

PARENT_SHA256 = '764ac0231f1cb08c4367536af26064b4bfce895f0444366f3c0540de958eaad4'


def once(source, old, new):
    assert source.count(old) == 1, (old[:70], source.count(old))
    return source.replace(old, new)


def splice(source, start, end, new):
    i = source.index(start)
    j = source.index(end, i)
    return source[:i] + new + source[j:]


def main(root):
    path = root / 'src/bin/eisenstein_fixed/unit_orbit_windows.rs'
    source = path.read_text()
    assert sha256(source.encode()).hexdigest() == PARENT_SHA256
    for old, new in [
        ('const SPLIT_PRIME_NORM: i32 = 12211;', 'const SPLIT_PRIME_NORM: i32 = 53593;'),
        ('const SPLIT_PRIME_TAU_RESIDUE: i32 = 112;', 'const SPLIT_PRIME_TAU_RESIDUE: i32 = 233;'),
        ('const SPLIT_PRIME_STEPS: usize = 18;', 'const SPLIT_PRIME_STEPS: usize = 16;'),
        ('const SPLIT_PRIME_DIGIT_LIMIT: usize = 6105;', 'const SPLIT_PRIME_DIGIT_LIMIT: usize = 26796;'),
        ('const SPLIT_PRIME_TERMINAL_LIMIT: usize = 68;', 'const SPLIT_PRIME_TERMINAL_LIMIT: usize = 7;'),
        ('let center = (2*lift+110).div_euclid(221);',
         'let center = (463*lift+53593).div_euclid(107186);'),
        ('let a = lift-112*b;', 'let a = lift-233*b;'),
        ('k.times_split_prime_small(109)', 'k.times_split_prime_small(230)'),
        ('affine_multiples(base, 112)', 'affine_multiples(base, 233)'),
        ('assert_eq!(digit_pairs.len(), 6106);', 'assert_eq!(digit_pairs.len(), 26797);'),
        ('assert_eq!(max_norm, 3997);', 'assert_eq!(max_norm, 17787);'),
        ('assert_eq!(digit_seeds.len(),2036);', 'assert_eq!(digit_seeds.len(),8933);'),
        ('assert_eq!(entries, 18*2036);', 'assert_eq!(entries, 16*8933);'),
        ('assert!(terminal_norm < 1156,"nearest-digit norm-12211 terminal bound");',
         'assert!(terminal_norm < 16,"nearest-digit norm-53593 terminal bound");'),
    ]:
        source = once(source, old, new) if old != 'affine_multiples(base, 112)' else source.replace(old, new)
    source = splice(source, '    terminal_row_start: [u16; 69],', '    retained_bytes: usize,', '')
    source = splice(source, '        let mut pair_digits = Vec::new();',
                    '        let entries = digit_windows.iter()', '''        let mut terminal_pairs_full = Vec::new();
        for a in -7..=7i32 {
            for b in -7..=7i32 {
                let norm = a*a+3*a*b+3*b*b;
                if norm < 16 { terminal_pairs_full.push((a as i16,b as i16)); }
            }
        }
        assert_eq!(terminal_pairs_full.len(),55);
        let terminal_set = terminal_pairs_full.iter().copied().map(orbit_canonical)
            .collect::<std::collections::BTreeSet<_>>();
        let mut terminal_seeds = terminal_set.into_iter().collect::<Vec<_>>();
        terminal_seeds.retain(|&pair| pair != (0,0));
        terminal_seeds.insert(0,(0,0));
        assert_eq!(terminal_seeds.len(),10);
        let terminal_ids = terminal_seeds.iter().enumerate()
            .map(|(index,&pair)| (pair,index as u16))
            .collect::<std::collections::BTreeMap<_,_>>();
        let terminal_codes = terminal_pairs_full.iter().copied().map(|pair| {
            let seed = orbit_canonical(pair);
            (terminal_ids[&seed],orbit_code(pair,seed))
        }).collect::<Vec<_>>().into_boxed_slice();
        let terminal_pairs = build_u256_window(&terminal_seeds, base);
''')
    source = once(source, '''        Self { digit_pairs,digit_codes,digit_windows,terminal_pairs,terminal_codes,
               terminal_row_start,terminal_row_min,retained_bytes }''',
                  '''        Self { digit_pairs,digit_codes,digit_windows,terminal_pairs,
               terminal_codes,retained_bytes }''')
    source = splice(source, '    let (ai,aneg) = a.split_prime_table_index(',
                    '\n    let mut bucket=U256XYZZ::identity();', '''    let (ai,aneg) = a.split_prime_table_index(SPLIT_PRIME_TERMINAL_LIMIT);
    let (bi,bneg) = b.split_prime_table_index(SPLIT_PRIME_TERMINAL_LIMIT);
    let signed_a = if aneg { -(ai as i32) } else { ai as i32 };
    let signed_b = if bneg { -(bi as i32) } else { bi as i32 };
    let terminal_norm = signed_a*signed_a+3*signed_a*signed_b
        +3*signed_b*signed_b;
    assert!(terminal_norm < 16,"nearest-digit norm-53593 terminal bound");
    if signed_a != 0 || signed_b != 0 {
        let mut index=0usize;
        'find_terminal: for aa in -7..=7i32 {
            for bb in -7..=7i32 {
                if aa*aa+3*aa*bb+3*bb*bb >= 16 { continue; }
                if (aa,bb)==(signed_a,signed_b) { break 'find_terminal; }
                index+=1;
            }
        }
        assert!(index < tables.terminal_codes.len());
        let (seed,code)=tables.terminal_codes[index];
        choices[SPLIT_PRIME_STEPS]=(usize::from(seed),usize::from(code));
    }
''')
    source = splice(source, '#[cfg(test)]\nmod split_prime_tests {',
                    '\npub(super) fn warm_mixed640_pretau_table()', '''#[cfg(test)]
mod split_prime_tests {
    use super::*;

    fn independent_binary_point(scalar: &BigInt) -> Jacobian {
        let (_, bytes) = scalar.to_bytes_be();
        let generator = Jacobian::generator().into_affine();
        let mut point = Jacobian::identity();
        for byte in bytes {
            for bit in (0..8).rev() {
                point = point.double();
                if (byte >> bit) & 1 != 0 { point = point.add_mixed(generator); }
            }
        }
        point
    }

    #[test]
    fn radix_53593_digit_residues_exhaustive() {
        let tables=&*SPLIT_PRIME_TABLES;
        for residue in 0..SPLIT_PRIME_NORM {
            let negative=residue > SPLIT_PRIME_DIGIT_LIMIT as i32;
            let index=if negative { (SPLIT_PRIME_NORM-residue) as usize }
                      else { residue as usize };
            let (a,b)=tables.digit_pairs[index];
            let (a,b)=if negative { (-i32::from(a),-i32::from(b)) }
                      else { (i32::from(a),i32::from(b)) };
            assert_eq!((a+233*b-residue).rem_euclid(53593),0);
            assert!(a*a+3*a*b+3*b*b <= 17787);
        }
        println!("radix_53593_residues={}",SPLIT_PRIME_NORM);
    }

    #[test]
    fn radix_53593_holdout_matches_independent_binary() {
        let panel: serde_json::Value = serde_json::from_str(include_str!(concat!(
            env!("CARGO_MANIFEST_DIR"), "/src/bin/mixed640_bench_fixture.json"
        ))).unwrap();
        let cases=panel["cases"].as_array().unwrap();
        assert_eq!(cases.len(),128);
        for (index,case) in cases.iter().enumerate() {
            let scalar=BigInt::parse_bytes(
                case["scalar_hex"].as_str().unwrap().as_bytes(),16).unwrap();
            let words=super::super::scalar_words_256(&scalar).unwrap();
            let candidate=multiply_u256_tau_split_prime_radix(words);
            assert_eq!(candidate.0,case["point_hex"].as_str().unwrap(),"fixture {index}");
            let reduced=&scalar % &SCALAR_LATTICE.n;
            assert_eq!(candidate.0,independent_binary_point(&reduced).affine_hex(),
                       "independent binary {index}");
        }
        println!("radix_53593_holdout_cases={} retained_bytes={}",
                 cases.len(),warm_split_prime_table());
    }
}
''')
    path.write_text(source)
    print(sha256(path.read_bytes()).hexdigest())


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('usage: native_overlay.py CARGO_ROOT')
    main(Path(sys.argv[1]))
