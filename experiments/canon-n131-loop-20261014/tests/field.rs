//! The field port against ecc2k130/src/f131.h (known-answer vectors written by
//! kat/f131_kat.cpp from the header itself), the normal-basis permutation, the
//! Frobenius-is-rotation property, and the table.

use canon_n131::F131;
use canon_n131_loop::*;

fn kat() -> Vec<[u64; 15]> {
    let text = include_str!("../kat/f131_kat.txt");
    text.lines()
        .map(|l| {
            let v: Vec<u64> = l.split_whitespace().map(|h| u64::from_str_radix(h, 16).unwrap()).collect();
            v.try_into().unwrap()
        })
        .collect()
}

#[test]
fn port_matches_f131_header() {
    let k = kat();
    assert_eq!(k.len(), 400);
    for v in &k {
        let a = [v[0], v[1], v[2]];
        let b = [v[3], v[4], v[5]];
        assert_eq!(field::mul(&a, &b), [v[6], v[7], v[8]], "mul");
        assert_eq!(field::sqr(&a), [v[9], v[10], v[11]], "sqr");
        assert_eq!(field::from_polynomial(&a), [v[12], v[13], v[14]], "fromPolynomial");
    }
}

#[test]
fn mul_matches_schoolbook_and_sqr() {
    let mut r = Rng(7);
    for _ in 0..2000 {
        let a = r.word131();
        let b = r.word131();
        assert_eq!(field::mul(&a, &b), field::mul_ref(&a, &b));
        assert_eq!(field::sqr(&a), field::mul(&a, &a));
    }
}

#[test]
fn one_is_all_ones_in_the_normal_basis() {
    assert_eq!(field::from_polynomial(&[1, 0, 0]), F131::MASK);
    let c = ToCyclic::new();
    assert_eq!(c.apply(&F131::MASK), F131::MASK);
}

#[test]
fn cyclic_order_is_a_bijection() {
    let src = cyc_src();
    let mut seen = [false; 131];
    for &s in &src {
        assert!(!seen[s as usize]);
        seen[s as usize] = true;
    }
}

#[test]
fn nibble_tables_match_bitwise_permutation() {
    let c = ToCyclic::new();
    let mut r = Rng(11);
    for _ in 0..20000 {
        let x = r.word131();
        assert_eq!(c.apply(&x), ToCyclic::apply_ref(&x));
    }
    for i in 0..131u32 {
        let mut x = [0u64; 3];
        x[(i / 64) as usize] = 1 << (i % 64);
        assert_eq!(c.apply(&x), ToCyclic::apply_ref(&x));
    }
}

/// The property the canonicalizers rely on: in the cyclic order, squaring
/// (Frobenius) is rotation left by one, so the Frobenius orbit of x is the
/// set of its rotations.
#[test]
fn frobenius_is_rotation_by_one() {
    let c = ToCyclic::new();
    let mut r = Rng(13);
    for _ in 0..20000 {
        let a = r.word131();
        let x = c.apply(&field::from_polynomial(&a));
        let y = c.apply(&field::from_polynomial(&field::sqr(&a)));
        assert_eq!(y, F131::rotl(x, 1));
    }
    // and the permuted basis itself is NOT rotation-ordered (the step matters)
    let a = Rng(17).word131();
    let x = field::from_polynomial(&a);
    let y = field::from_polynomial(&field::sqr(&a));
    assert_ne!(y, F131::rotl(x, 1));
}

#[test]
fn table_finds_exactly_its_keys() {
    let mut r = Rng(19);
    let keys: Vec<W3> = (0..5000).map(|_| r.word131()).collect();
    let t = Table::build(&keys, 10);
    assert_eq!(t.recs.len(), 5000);
    for k in &keys {
        assert!(t.probe(k));
    }
    for _ in 0..5000 {
        assert!(!t.probe(&r.word131()));
    }
    let mut k = keys[0];
    k[2] ^= 4; // differs only in the top limb
    assert!(!t.probe(&k));
}

#[test]
fn protocol_workloads_parse() {
    let w = workloads_from_protocol(include_str!("../protocol.json"));
    let names: Vec<&str> = w.iter().map(|w| w.name.as_str()).collect();
    assert_eq!(names, ["w1-small", "w1-large", "w5-small", "w5-large"]);
    assert_eq!(w[1].records_log2, 22);
    assert_eq!(w[3].work, 5);
    assert_eq!(w[0].seed, 1312026101410);
}

/// Small loop: every arm gives the same (key, shift, hit) sequence and the
/// planted positions are exactly the hits.
#[test]
fn loop_arms_agree_small() {
    let c = Ctx { g: consts(), cyc: ToCyclic::new() };
    for work in [1u8, 5] {
        let wl = Workload {
            name: "t".into(), work, records_log2: 12, dir_bits: 10,
            plant_span: 8192, plant_period: 16, seed: 99 + work as u64,
        };
        let (t, pos) = wl.build(&c);
        let (s_ref, v_ref) = record(ARM_EXHAUSTIVE as usize, work, &t, &c, wl.s0(), 8192);
        let hits: Vec<usize> = v_ref.iter().enumerate().filter(|(_, r)| r.2).map(|(i, _)| i).collect();
        assert_eq!(hits, pos);
        for arm in 1..7 {
            let (s, v) = record(arm, work, &t, &c, wl.s0(), 8192);
            assert_eq!(v, v_ref, "arm {arm}");
            assert_eq!(s, s_ref);
            assert_eq!(loop_fn(arm, work)(&t, &c, wl.s0(), 8192), s_ref);
        }
    }
}
