//! Exactness of the two-limb `lift_scan` against the pipelines' full scan.
//!
//! * every word at every small `N` (3..=20) and every two-limb split
//!   `ceil(N/2) <= B < N` (so a one-bit top limb, equal limbs and every
//!   cross-limb carry and wrap are covered), including the composite `N`
//!   whose periodic words have tied rotations;
//! * at the production geometry `N = 83, B = 64`: the exceptional words (0,
//!   all ones, every weight-1 and weight-82 word), every word with one zero
//!   run of each length at each position, runs that cross the limb boundary
//!   or wrap past bit 82, two- and three-way ties of longest runs, and
//!   2,000,000 fixed-seed words of mixed density;
//! * every other wide degree the dispatcher accepts, on fixed-seed words.
//!
//! The reference is `full_scan_u128`, written independently on `u128`
//! exactly as the pipelines' `canonical` (one-bit rotations, first minimum).

use lift2::{full_scan_u128, lift_scan_wide, L2, F83};

fn check<const N: u32, const B: u32>(v: u128) {
    let expected = full_scan_u128(v, N);
    let got = L2::<N, B>::canonical_u128(v);
    assert_eq!(got, expected, "N={N} B={B} v={v:#x}");
    let mut rotations = 0;
    assert_eq!(L2::<N, B>::canonical_u128_counted(v, &mut rotations), expected);
    let (w, s) = L2::<N, B>::full_scan(L2::<N, B>::from_u128(v));
    assert_eq!((L2::<N, B>::to_u128(w), s), expected, "W2 full scan N={N} B={B}");
    assert_eq!(L2::<N, B>::to_u128(L2::<N, B>::from_u128(v)), v);
}

fn all_words<const N: u32, const B: u32>() -> u64 {
    let mut count = 0;
    for v in 0..(1u128 << N) {
        check::<N, B>(v);
        count += 1;
    }
    count
}

macro_rules! exhaustive {
    ($name:ident, $n:literal, [$($b:literal),*]) => {
        #[test]
        fn $name() {
            let mut words = 0;
            $( words += all_words::<$n, $b>(); )*
            assert!(words > 0);
        }
    };
}

exhaustive!(all_n3, 3, [2]);
exhaustive!(all_n4, 4, [2, 3]);
exhaustive!(all_n5, 5, [3, 4]);
exhaustive!(all_n6, 6, [3, 4, 5]);
exhaustive!(all_n7, 7, [4, 5, 6]);
exhaustive!(all_n8, 8, [4, 5, 6, 7]);
exhaustive!(all_n9, 9, [5, 6, 7, 8]);
exhaustive!(all_n10, 10, [5, 6, 7, 8, 9]);
exhaustive!(all_n11, 11, [6, 7, 8, 9, 10]);
exhaustive!(all_n12, 12, [6, 7, 8, 9, 10, 11]);
exhaustive!(all_n13, 13, [7, 8, 9, 10, 11, 12]);
exhaustive!(all_n14, 14, [7, 8, 9, 10, 11, 12, 13]);
exhaustive!(all_n15, 15, [8, 9, 10, 11, 12, 13, 14]);
exhaustive!(all_n16, 16, [8, 9, 10, 11, 12, 13, 14, 15]);
exhaustive!(all_n17, 17, [9, 10, 12, 16]);
exhaustive!(all_n18, 18, [9, 11, 14, 17]);
exhaustive!(all_n19, 19, [10, 13, 18]);
exhaustive!(all_n20, 20, [10, 15, 19]);

struct SplitMix(u64);

impl SplitMix {
    fn next(&mut self) -> u64 {
        self.0 = self.0.wrapping_add(0x9E37_79B9_7F4A_7C15);
        let mut z = self.0;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
        z ^ (z >> 31)
    }
    fn word(&mut self, n: u32) -> u128 {
        let v = (u128::from(self.next()) << 64) | u128::from(self.next());
        v & ((1u128 << n) - 1)
    }
    /// Mixed density: AND/OR of several words gives long zero or one runs.
    fn mixed(&mut self, n: u32) -> u128 {
        let mask = (1u128 << n) - 1;
        let a = self.word(n);
        match self.next() % 6 {
            0 => a,
            1 => a & self.word(n),
            2 => a & self.word(n) & self.word(n),
            3 => a & self.word(n) & self.word(n) & self.word(n) & self.word(n),
            4 => (a | self.word(n)) & mask,
            _ => (a | self.word(n) | self.word(n) | self.word(n)) & mask,
        }
    }
}

const N83: u32 = 83;
const M83: u128 = (1u128 << 83) - 1;

fn rotl83(v: u128, s: u32) -> u128 {
    if s == 0 {
        v
    } else {
        ((v << s) | (v >> (N83 - s))) & M83
    }
}

#[test]
fn n83_exceptional_words() {
    check::<83, 64>(0);
    check::<83, 64>(M83);
    assert_eq!(F83::canonical_u128(0), (0, 0));
    assert_eq!(F83::canonical_u128(M83), (M83, 0));
    for i in 0..N83 {
        check::<83, 64>(1u128 << i);
        check::<83, 64>(M83 ^ (1u128 << i));
    }
}

#[test]
fn n83_single_zero_runs_at_every_position() {
    // A zero run of length `len` with top bit `top` (wrapping), all else ones,
    // plus the same with extra sparse ones/zeros elsewhere.
    let mut rng = SplitMix(20261015);
    for len in 1..N83 {
        for top in 0..N83 {
            let mut run = 0u128;
            for j in 0..len {
                run |= 1u128 << ((top + N83 - j) % N83);
            }
            let v = M83 ^ run;
            check::<83, 64>(v);
            check::<83, 64>(v & (rng.word(N83) | run));
        }
    }
}

#[test]
fn n83_limb_boundary_and_wrap_runs() {
    // Longest run crossing bit 63/64, ending at bit 82, starting at bit 0,
    // and wrapping from bit 82 to bit 0, against a background with shorter runs.
    let mut rng = SplitMix(83_64);
    let background = 0x5555_5555_5555_5555_5555u128 & M83 | 1;
    for (lo, hi) in [(58u32, 70u32), (60, 64), (63, 64), (64, 66), (40, 82), (0, 11), (75, 82)] {
        let mut v = background;
        for b in lo..=hi {
            v &= !(1u128 << b);
        }
        check::<83, 64>(v);
        for _ in 0..200 {
            check::<83, 64>(v | (rng.word(N83) & rng.word(N83) & !(((1u128 << (hi + 1)) - 1) ^ ((1u128 << lo) - 1))));
        }
    }
    for wrap in 1..40u32 {
        // zeros at 82-wrap+1 ..= 82 and 0 ..= wrap
        let mut v = background | (1u128 << 41);
        for j in 0..wrap {
            v &= !(1u128 << (82 - j));
            v &= !(1u128 << j);
        }
        check::<83, 64>(v);
    }
}

#[test]
fn n83_tied_longest_runs() {
    // Two or three longest zero runs of equal length; the rotation winner is
    // decided by the bits after the run (and by the least shift when equal).
    let mut rng = SplitMix(7_331);
    for _ in 0..200_000 {
        let len = 1 + (rng.next() % 12) as u32;
        let copies = 2 + (rng.next() % 2) as u32;
        let mut v = rng.word(N83) | rng.word(N83); // dense ones: short zero runs
        let mut run = (1u128 << len) - 1;
        run = rotl83(run, (rng.next() % 83) as u32);
        for c in 0..copies {
            let pos = (rng.next() % 83) as u32 + c * 29;
            v &= !rotl83(run, pos % 83);
        }
        check::<83, 64>(v);
    }
}

#[test]
fn n83_two_million_fixed_seed_words() {
    let mut rng = SplitMix(0x83_2026_1015);
    for _ in 0..2_000_000 {
        let v = rng.mixed(N83);
        check::<83, 64>(v);
        assert_eq!(lift_scan_wide(v, 83), full_scan_u128(v, 83));
    }
}

#[test]
fn every_dispatched_wide_degree() {
    let mut rng = SplitMix(0x65_127);
    for n in [65u32, 67, 71, 73, 79, 83, 89, 97, 101, 103, 107, 109, 113, 127] {
        let mask = (1u128 << n) - 1;
        for v in [0, mask, 1, mask ^ 1, 1u128 << (n - 1)] {
            assert_eq!(lift_scan_wide(v, n), full_scan_u128(v, n), "n={n} v={v:#x}");
        }
        for _ in 0..50_000 {
            let v = rng.mixed(n);
            assert_eq!(lift_scan_wide(v, n), full_scan_u128(v, n), "n={n} v={v:#x}");
        }
    }
}
