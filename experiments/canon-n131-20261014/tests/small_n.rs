//! Exhaustive equality on every word for 2 <= n <= 20, in two geometries per
//! n: three small limbs (B = ceil(n/3), so carries cross two limb boundaries
//! and the wrap leaves a partial top limb) and one 64-bit limb.  Composite n
//! is included: periodic words tie and the smallest shift must win.  Every
//! arm is compared with the exhaustive arm and both with an independent
//! integer oracle (u64 rotations, no limb code).

use canon_n131::{G, W3};

fn pack(v: u64, b: u32) -> W3 {
    let m = if b == 64 { u64::MAX } else { (1u64 << b) - 1 };
    if b == 64 {
        [v, 0, 0]
    } else {
        [v & m, (v >> b) & m, (v >> (2 * b)) & m]
    }
}

fn oracle_u64(v: u64, n: u32) -> (u64, u32) {
    let mask = (1u64 << n) - 1;
    let mut best = v;
    let mut bs = 0;
    for s in 1..n {
        let r = ((v << s) | (v >> (n - s))) & mask;
        if r < best {
            best = r;
            bs = s;
        }
    }
    (best, bs)
}

macro_rules! check {
    ($n:expr, $b:expr) => {{
        type T = G<$n, $b>;
        let mut words = 0u64;
        for v in 0u64..(1u64 << $n) {
            let x = pack(v, $b);
            let (ow, os) = oracle_u64(v, $n);
            let want = (pack(ow, $b), os);
            let arms: [(&str, (W3, u32)); 5] = [
                ("exhaustive", T::exhaustive(x)),
                ("gap_scan", T::gap_scan(x)),
                ("refine_bf", T::refine_bf(x)),
                ("exhaustive_bf", T::exhaustive_bf(x)),
                ("lift_scan", T::lift_scan(x)),
            ];
            for (name, got) in arms {
                assert_eq!(got, want, "arm {name} n={} B={} v={v:#x}", $n, $b);
            }
            words += 1;
        }
        words
    }};
}

macro_rules! small {
    ($($n:literal / $b:literal),* $(,)?) => {
        #[test]
        fn exhaustive_small_n() {
            let mut total = 0u64;
            $( total += check!($n, $b); )*
            eprintln!("small-n exhaustive: {total} words checked");
        }
    };
}

small!(
    2/1, 3/1, 4/2, 5/2, 6/2, 7/3, 8/3, 9/3, 10/4, 11/4, 12/4, 13/5, 14/5,
    15/5, 16/6, 17/6, 18/6, 19/7, 20/7,
    2/64, 3/64, 4/64, 5/64, 6/64, 7/64, 8/64, 9/64, 10/64, 11/64, 12/64,
    13/64, 14/64, 15/64, 16/64, 17/64, 18/64, 19/64, 20/64,
    // two-limb geometries where the top limb is empty
    8/4, 12/6, 20/10,
);

#[test]
fn fmul_matches_schoolbook() {
    let mut r = canon_n131::Rng(7);
    for _ in 0..2000 {
        let a = r.word131();
        let b = r.word131();
        let want = canon_n131::fmul::mul_ref(&a, &b);
        let got = unsafe { canon_n131::fmul::mul_clmul(&a, &b) };
        assert_eq!(got, want);
    }
}
