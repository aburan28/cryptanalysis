//! Exactness at n = 131: every arm against the exhaustive arm on uniform
//! random words, edge cases and structured families; the exhaustive arm
//! against the independent bit-string oracle on a subset; and uniqueness of
//! the minimizing shift (Corollary cor:unique) on every nonconstant word the
//! oracle sees.  Prints one JSON object.
//!
//! usage: verify <uniform_words> <uniform_seed> <oracle_words>

use canon_n131::*;

type T = F131;

struct Tally {
    name: &'static str,
    words: u64,
    mismatches: u64,
}

fn arms(x: W3) -> [(W3, u32); 4] {
    [T::gap_scan(x), T::refine_bf(x), T::exhaustive_bf(x), T::lift_scan(x)]
}

fn check(t: &mut Tally, x: W3, mism: &mut Vec<String>) {
    let want = T::exhaustive(x);
    for (i, got) in arms(x).into_iter().enumerate() {
        if got != want {
            t.mismatches += 1;
            if mism.len() < 20 {
                mism.push(format!("{}:arm{}:{:x?}", t.name, i, x));
            }
        }
    }
    t.words += 1;
}

fn words_with_exactly(c: u32, z: u32, rng: &mut Rng) -> Option<W3> {
    // Build run-length blocks 0^len 1^ones; c blocks have len = z, the
    // others len < z.  Accept only if the result has exactly c longest runs
    // of length z.
    let mut lens: Vec<u32> = (0..c).map(|_| z).collect();
    let mut used: u32 = c * (z + 1);
    if used > 131 {
        return None;
    }
    while used < 131 - (z.max(1)) {
        let l = if z > 1 { rng.below(z as u64) as u32 } else { 0 };
        lens.push(l);
        used += l + 1;
    }
    // shuffle
    for i in (1..lens.len()).rev() {
        let j = rng.below(i as u64 + 1) as usize;
        lens.swap(i, j);
    }
    let mut x = [0u64; 3];
    let mut pos = 0u32;
    for (k, &l) in lens.iter().enumerate() {
        pos += l; // zeros
        let ones = if k + 1 == lens.len() { 131 - pos } else { 1 + rng.below(2) as u32 };
        for _ in 0..ones {
            if pos >= 131 {
                break;
            }
            set_bit(&mut x, pos);
            pos += 1;
        }
        if pos >= 131 {
            break;
        }
    }
    let rot = rng.below(131) as u32;
    let x = T::rotl(T::mask(x), rot);
    let (zz, cc, _) = T::stats(x);
    (zz == z && cc == c).then_some(x)
}

fn main() {
    let a: Vec<String> = std::env::args().collect();
    let n_uniform: u64 = a.get(1).map(|s| s.parse().unwrap()).unwrap_or(10_000_000);
    let seed: u64 = a.get(2).map(|s| s.parse().unwrap()).unwrap_or(131_2026_1014);
    let n_oracle: u64 = a.get(3).map(|s| s.parse().unwrap()).unwrap_or(200_000);
    let mut mism = Vec::new();
    let mut tallies = Vec::new();

    // 1. uniform
    let mut t = Tally { name: "uniform", words: 0, mismatches: 0 };
    let mut rng = Rng(seed);
    for _ in 0..n_uniform {
        check(&mut t, rng.word131(), &mut mism);
    }
    tallies.push(t);

    // 2. edge cases
    let mut t = Tally { name: "edge_constant_x_in_F2", words: 0, mismatches: 0 };
    for x in [[0u64; 3], MASK131] {
        check(&mut t, x, &mut mism);
        let want = (x, 0u32);
        for got in arms(x).into_iter().chain([T::exhaustive(x)]) {
            if got != want {
                t.mismatches += 1;
                mism.push(format!("constant:{:x?}", x));
            }
        }
    }
    tallies.push(t);

    let mut t = Tally { name: "edge_weight_le3_and_ge128", words: 0, mismatches: 0 };
    for i in 0..131u32 {
        for j in i..131u32 {
            for k in j..131u32 {
                let mut x = [0u64; 3];
                set_bit(&mut x, i);
                set_bit(&mut x, j);
                set_bit(&mut x, k);
                // (i,j,k) with repeats covers weights 1, 2 and 3
                check(&mut t, x, &mut mism);
                let y = T::mask([!x[0], !x[1], !x[2]]);
                check(&mut t, y, &mut mism);
            }
        }
    }
    tallies.push(t);

    // zero runs straddling the limb boundaries 64, 128 and the wrap 131 -> 0
    let mut t = Tally { name: "edge_runs_straddling_limbs", words: 0, mismatches: 0 };
    let mut rng = Rng(seed ^ 0x5157_4ADD);
    for &bd in &[64u32, 128, 131] {
        for len in 1..=60u32 {
            for off in 0..=len {
                let start = (bd + 131 - off) % 131;
                let mut one_bg = MASK131;
                for q in 0..len {
                    clear_bit(&mut one_bg, (start + q) % 131);
                }
                check(&mut t, one_bg, &mut mism);
                // second, equal run elsewhere (a tie) when it fits
                if 2 * (len + 1) <= 131 {
                    let mut tie = one_bg;
                    let s2 = (start + len + 1 + rng.below((131 - 2 * (len + 1) + 1) as u64) as u32) % 131;
                    for q in 0..len {
                        clear_bit(&mut tie, (s2 + q) % 131);
                    }
                    check(&mut t, tie, &mut mism);
                }
                // random backgrounds with the run planted
                for _ in 0..4 {
                    let mut x = rng.word131();
                    for q in 0..len {
                        clear_bit(&mut x, (start + q) % 131);
                    }
                    set_bit(&mut x, (start + len) % 131);
                    set_bit(&mut x, (start + 130) % 131);
                    check(&mut t, x, &mut mism);
                }
            }
        }
    }
    tallies.push(t);

    // exactly c tied longest runs of length z
    let mut t = Tally { name: "edge_tied_longest_runs", words: 0, mismatches: 0 };
    let mut built = vec![];
    for c in 2..=12u32 {
        for z in 1..=12u32 {
            let mut got = 0;
            let mut tries = 0;
            while got < 200 && tries < 20_000 {
                tries += 1;
                if let Some(x) = words_with_exactly(c, z, &mut rng) {
                    check(&mut t, x, &mut mism);
                    got += 1;
                }
            }
            built.push(format!("[{c},{z},{got}]"));
        }
    }
    tallies.push(t);

    // near-periodic words (period 2..=40, random pattern, 0/1/2 flips)
    let mut t = Tally { name: "structured_near_periodic", words: 0, mismatches: 0 };
    for d in 2..=40u32 {
        for _ in 0..1000 {
            let pat = rng.next() & ((1u64 << d.min(63)) - 1);
            let mut x = [0u64; 3];
            for i in 0..131 {
                if (pat >> (i % d)) & 1 == 1 {
                    set_bit(&mut x, i);
                }
            }
            for _ in 0..rng.below(3) {
                flip_bit(&mut x, rng.below(131) as u32);
            }
            check(&mut t, x, &mut mism);
        }
    }
    tallies.push(t);

    // 3. oracle + uniqueness
    let mut rng = Rng(seed ^ 0x0EAC1E);
    let (mut o_words, mut o_mism, mut nonunique) = (0u64, 0u64, 0u64);
    let mut src = Rng(seed ^ 0x57A7);
    for i in 0..n_oracle {
        let x = if i % 2 == 0 { rng.word131() } else { structured131(&mut src) };
        let (ow, os) = oracle(&x, 131, 64);
        let (ew, es) = T::exhaustive(x);
        if to_msb_first(&ew, 131, 64) != ow || es != os {
            o_mism += 1;
        }
        if x != [0; 3] && x != MASK131 {
            let mut eq = 0;
            for s in 0..131 {
                if T::rotl(x, s) == ew {
                    eq += 1;
                }
            }
            if eq != 1 {
                nonunique += 1;
            }
        }
        o_words += 1;
    }

    let total_words: u64 = tallies.iter().map(|t| t.words).sum();
    let total_mism: u64 = tallies.iter().map(|t| t.mismatches).sum();
    print!("{{\"n\":131,\"limbs\":\"[u64;3] 64/64/3\",\"uniform_seed\":{seed},");
    print!("\"arms_vs_exhaustive\":[");
    for (i, t) in tallies.iter().enumerate() {
        print!(
            "{}{{\"family\":\"{}\",\"words\":{},\"arm_mismatches\":{}}}",
            if i > 0 { "," } else { "" },
            t.name,
            t.words,
            t.mismatches
        );
    }
    print!("],\"total_words\":{total_words},\"total_arm_mismatches\":{total_mism},");
    print!("\"tied_family_built_c_z_count\":[{}],", built.join(","));
    print!(
        "\"oracle\":{{\"words\":{o_words},\"exhaustive_vs_oracle_mismatches\":{o_mism},\"nonunique_minimizers\":{nonunique}}},"
    );
    print!("\"first_mismatches\":{:?}}}", mism);
    println!();
    if total_mism != 0 || o_mism != 0 || nonunique != 0 {
        std::process::exit(1);
    }
}
