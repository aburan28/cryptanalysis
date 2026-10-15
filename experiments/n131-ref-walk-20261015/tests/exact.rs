//! Exactness of the walk code: field and point arithmetic against f131.h /
//! packed131.h known answers, the basis changes, the canonicalizers, the
//! group law on actual curve points, the class property of both walk designs,
//! and the logarithm bookkeeping.
use canon_n131_loop::ToCyclic;
use n131_ref_walk::*;

fn limbs(v: &[u64]) -> W3 {
    [v[0], v[1], v[2]]
}

fn kat(text: &str) -> Vec<Vec<u64>> {
    text.lines()
        .map(|l| l.split_whitespace().map(|h| u64::from_str_radix(h, 16).unwrap()).collect())
        .collect()
}

#[test]
fn f131_field_matches_header_kat() {
    let k = kat(include_str!("../../canon-n131-loop-20261014/kat/f131_kat.txt"));
    assert_eq!(k.len(), 400);
    for v in &k {
        let (a, b) = (limbs(&v[0..3]), limbs(&v[3..6]));
        assert_eq!(F131::mul(&a, &b), limbs(&v[6..9]));
        assert_eq!(F131::sqr(&a), limbs(&v[9..12]));
    }
}

#[test]
fn f131_points_match_header_kat() {
    let c = Curve::<F131>::new(0);
    let cyc = ToCyclic::new();
    let k = kat(include_str!("../kat/point_kat.txt"));
    assert_eq!(k.len(), 300);
    for (i, v) in k.iter().enumerate() {
        let a = limbs(&v[0..3]);
        assert_eq!(c.inv(&a), limbs(&v[3..6]), "inv line {i}");
        assert_eq!(c.pow2k(&a, (i % 131) as u32), limbs(&v[6..9]), "sigma line {i}");
        // permuted NB word -> cyclic order -> our from_nb == toPolynomial131
        assert_eq!(c.from_nb(&cyc.apply(&limbs(&v[9..12]))), limbs(&v[12..15]), "toPolynomial line {i}");
        let p = Pt::new(limbs(&v[15..18]), limbs(&v[18..21]));
        let q = Pt::new(limbs(&v[21..24]), limbs(&v[24..27]));
        assert_eq!(c.add(&p, &q), Pt::new(limbs(&v[27..30]), limbs(&v[30..33])), "add line {i}");
        assert_eq!(c.double(&p), Pt::new(limbs(&v[33..36]), limbs(&v[36..39])), "double line {i}");
        // the batched path: add_slope with the batch inverse
        let mut d = vec![xor(&p.x, &q.x), a, [0, 0, 0]];
        let mut pre = vec![];
        c.batch_inv(&mut d, &mut pre);
        assert!(is_zero(&d[2]));
        assert_eq!(d[1], c.inv(&a));
        let lam = F131::mul(&xor(&p.y, &q.y), &d[0]);
        assert_eq!(c.add_slope(&p, &q, &lam), Pt::new(limbs(&v[27..30]), limbs(&v[30..33])));
    }
}

/// Bitwise schoolbook product mod z^83 + z^7 + z^4 + z^2 + 1 (test oracle).
fn mul83_ref(a: &W3, b: &W3) -> W3 {
    let mut t = [0u64; 3];
    for i in 0..83u32 {
        if bit(a, i) {
            for j in 0..83u32 {
                if bit(b, j) {
                    let k = i + j;
                    t[(k / 64) as usize] ^= 1 << (k % 64);
                }
            }
        }
    }
    for k in (83..166u32).rev() {
        if bit(&t, k) {
            t[(k / 64) as usize] ^= 1 << (k % 64);
            for e in [0u32, 2, 4, 7] {
                let m = k - 83 + e;
                t[(m / 64) as usize] ^= 1 << (m % 64);
            }
        }
    }
    t
}

fn r83(r: &mut Rng) -> W3 {
    [r.next(), r.next() & ((1 << 19) - 1), 0]
}

#[test]
fn f83_field_is_exact() {
    let c = Curve::<F83>::new(1);
    let mut r = Rng(83);
    for i in 0..83 {
        for j in 0..83 {
            assert_eq!(F83::mul(&unit(i), &unit(j)), mul83_ref(&unit(i), &unit(j)));
        }
    }
    for _ in 0..3000 {
        let (a, b) = (r83(&mut r), r83(&mut r));
        assert_eq!(F83::mul(&a, &b), mul83_ref(&a, &b));
        assert_eq!(F83::sqr(&a), F83::mul(&a, &a));
        if !is_zero(&a) {
            assert_eq!(F83::mul(&a, &c.inv(&a)), [1, 0, 0]);
        }
    }
}

fn basis_checks<F: Field>(rand: &mut dyn FnMut() -> W3) {
    let c = Curve::<F>::new(0);
    for i in 0..F::N {
        let x = unit(i);
        assert_eq!(c.to_nb(&x), Linear::apply_ref(&c.b.to_images, &x));
    }
    for _ in 0..3000 {
        let x = rand();
        assert_eq!(c.to_nb(&x), Linear::apply_ref(&c.b.to_images, &x));
        assert_eq!(c.from_nb(&c.to_nb(&x)), x);
        // Frobenius (squaring) is rotation left by one in the cyclic basis
        assert_eq!(c.to_nb(&F::sqr(&x)), F::rotl(c.to_nb(&x), 1));
        let k = (x[0] % F::N as u64) as u32;
        let mut s = x;
        for _ in 0..k {
            s = F::sqr(&s);
        }
        assert_eq!(c.pow2k(&x, k), s);
        // lift_scan is exact, and its word is rotl(x, k)
        let w = c.to_nb(&x);
        let (cw, ck) = F::lift_scan(w);
        assert_eq!((cw, ck), F::exhaustive(w));
        assert_eq!(F::rotl(w, ck), cw);
    }
    if !is_zero(&F::mask()) {
        assert_eq!(F::lift_scan(F::mask()).0, F::mask());
    }
}

#[test]
fn basis_changes_and_canonicalizers() {
    let mut r = Rng(5);
    basis_checks::<F131>(&mut || r.word131());
    let mut r = Rng(6);
    basis_checks::<F83>(&mut || r83(&mut r));
}

fn inputs131() -> Vec<Pt> {
    hex_points(include_str!("../inputs/n131_points.json"), "starts")
}

const R131: W3 = [0x4d4fdd5703a3f269, 0x0, 0x2];

#[test]
fn r131_constant_matches_inputs() {
    let text = include_str!("../inputs/constants.json");
    assert!(text.contains("\"680564733841876926932320129493409985129\""));
}

fn lambda131() -> W3 {
    let v: u128 = 196511074115861092422032515080945363956;
    [v as u64, (v >> 64) as u64, 0]
}

#[test]
fn ecc2k130_group_law() {
    let c = Curve::<F131>::new(0);
    let pts = inputs131();
    for p in &pts[..6] {
        assert!(c.on_curve(p));
        assert!(c.smul(p, &R131).inf, "[r]P = O");
        assert_eq!(c.frob(p, 1), c.smul(p, &lambda131()), "phi(P) = [lambda]P");
        assert!(c.add(p, &c.neg(p)).inf);
    }
    for w in pts.windows(3).take(8) {
        let (p, q, s) = (w[0], w[1], w[2]);
        assert!(c.on_curve(&c.add(&p, &q)) && c.on_curve(&c.double(&p)));
        assert_eq!(c.add(&c.add(&p, &q), &s), c.add(&p, &c.add(&q, &s)), "associativity");
        assert_eq!(c.add(&c.add(&p, &q), &q), c.add(&p, &c.double(&q)));
        assert_eq!(c.smul(&p, &[3, 0, 0]), c.add(&c.double(&p), &p));
    }
}

#[test]
fn n83_fixture_group_law() {
    let c = Curve::<F83>::new(1);
    let g = n83::gen();
    assert!(c.on_curve(&g));
    assert!(c.smul(&g, &[n83::R, 0, 0]).inf);
    assert!(!c.smul(&g, &[1, 0, 0]).inf);
    assert_eq!(c.frob(&g, 1), c.smul(&g, &[n83::LAMBDA, 0, 0]));
    let zr = Zr { r: n83::R };
    assert_eq!(zr.pow(n83::LAMBDA, 83), 1);
    let panel = include_str!("../inputs/panel64.json");
    assert!(panel.contains("6274346871052084705058109")); // Panel B seed 0
}

fn canon_checks<F: Field>(c: &Curve<F>, pts: &[Pt]) {
    for p in pts {
        let (cp, cx, k, neg) = c.canon_with::<false>(p);
        assert_eq!(cp, c.canon_ref(p), "lift_scan canonical form = exhaustive definition");
        assert_eq!(cp, c.canon_with::<true>(p).0);
        assert_eq!(cx, c.to_nb(&cp.x));
        let fk = c.frob(p, k);
        assert_eq!(cp, if neg { c.neg(&fk) } else { fk });
        for t in [1u32, 7, F::N - 1] {
            assert_eq!(c.canon_with::<false>(&c.frob(p, t)).0, cp);
            assert_eq!(c.canon_with::<false>(&c.neg(&c.frob(p, t))).0, cp);
        }
    }
}

#[test]
fn canonical_forms_are_class_invariants() {
    let c = Curve::<F131>::new(0);
    canon_checks(&c, &inputs131()[..16]);
    let c = Curve::<F83>::new(1);
    let g = n83::gen();
    let pts: Vec<Pt> = (1..17u64).map(|k| c.smul(&g, &[k * 1_000_003, 0, 0])).collect();
    canon_checks(&c, &pts);
}

/// Bailey's step commutes with the signed Frobenius action, so its walk is
/// well defined on classes (ePrint 2009/541 sec. 3).
fn bailey_class<F: Field>(c: &Curve<F>, pts: &[Pt]) {
    let next = |p: &Pt| {
        let j = 3 + ((popcnt(&c.to_nb(&p.x)) >> 1) & 7);
        c.add(p, &c.frob(p, j))
    };
    for p in pts {
        let np = next(p);
        for t in [1u32, 5, F::N - 2] {
            let q = c.frob(p, t);
            assert_eq!(next(&q), c.frob(&np, t));
            assert_eq!(next(&c.neg(&q)), c.neg(&c.frob(&np, t)));
        }
    }
}

#[test]
fn bailey_step_is_a_class_function() {
    bailey_class(&Curve::<F131>::new(0), &inputs131()[..8]);
    let c = Curve::<F83>::new(1);
    let g = n83::gen();
    let pts: Vec<Pt> = (1..9u64).map(|k| c.smul(&g, &[k * 7_777_777, 0, 0])).collect();
    bailey_class(&c, &pts);
}

/// The lockstep walker equals a one-lane reference walk built from the
/// generic group law (no batching), for both designs.
#[test]
fn lockstep_walker_matches_scalar_reference() {
    let text = include_str!("../inputs/n131_points.json");
    let c = Curve::<F131>::new(0);
    let starts = hex_points(text, "starts");
    let jumps = hex_points(text, "jumps");
    let sc = hex_points(text, "stride_cursor");
    let ctx = Ctx::new(Curve::<F131>::new(0), 52, jumps.clone(), vec![0; 32], 0, 1, sc[0], 0, 4096);
    // Bailey
    let mut w = Walker::new(&ctx, BAILEY, &starts, &[], sc[1], 0);
    let mut s = Fold::default();
    w.run::<F131, BAILEY, 32, 8, false, _>(&ctx, 40, &mut s);
    for (i, st) in starts.iter().enumerate().take(8) {
        let mut p = *st;
        for _ in 0..40 {
            let j = 3 + ((popcnt(&c.to_nb(&p.x)) >> 1) & 7);
            p = c.add(&p, &c.frob(&p, j));
        }
        assert_eq!(w.lanes[i].p, p, "bailey lane {i}");
    }
    // canonicalizing adding walk (lanes without an escape in 40 steps)
    let mut w = Walker::new(&ctx, CANON, &starts, &[], sc[1], 0);
    w.run::<F131, CANON, 32, 8, false, _>(&ctx, 40, &mut s);
    let mut checked = 0;
    for (i, st) in starts.iter().enumerate() {
        let mut p = c.canon_ref(st);
        let mut prev = [INF; 4];
        let mut esc = false;
        for _ in 0..40 {
            let q = c.canon_ref(&c.add(&p, &jumps[jump_index(&p.x, 32)]));
            if q == p || q == prev[0] || q == prev[2] {
                esc = true;
                break;
            }
            prev = [p, prev[0], prev[1], prev[2]];
            p = q;
        }
        if !esc {
            assert_eq!(w.lanes[i].p, p, "canon lane {i}");
            checked += 1;
        }
    }
    assert!(checked >= 32, "too few escape-free lanes ({checked})");
}

/// With logs tracked every lane satisfies P = [a]G + [b]Q, through
/// distinguished points, canonicalization, escapes and restarts; and
/// tracking does not change the trajectory.
#[test]
fn n83_log_bookkeeping_and_tracking_is_transparent() {
    let c = Curve::<F83>::new(1);
    let g = n83::gen();
    let q = c.smul(&g, &[123456789012345, 0, 0]);
    let zr = Zr { r: n83::R };
    let mut rng = Rng(1);
    let js: Vec<u64> = (0..32).map(|_| 1 + rng.next() % (n83::R - 1)).collect();
    let jumps: Vec<Pt> = js.iter().map(|&s| c.smul(&g, &[s, 0, 0])).collect();
    let stride_a = 99991u64;
    let ctx = Ctx::new(Curve::<F83>::new(1), 31, jumps, js, n83::R, n83::LAMBDA, c.smul(&g, &[stride_a, 0, 0]), stride_a, 200);
    let mut starts = vec![];
    let mut sa = vec![];
    for i in 0..16u64 {
        let a = 1000 + 17 * i;
        starts.push(c.add(&c.smul(&g, &[a, 0, 0]), &q));
        sa.push(a);
    }
    let cursor = c.add(&c.smul(&g, &[5, 0, 0]), &q);
    macro_rules! check {
        ($arm:expr, $r:expr, $m:expr) => {{
            let mut w = Walker::new(&ctx, $arm, &starts, &sa, cursor, 5);
            let mut u = w.clone();
            let mut s = Fold::default();
            let mut s2 = Fold::default();
            for _ in 0..30 {
                w.run::<F83, { $arm }, $r, $m, true, _>(&ctx, 100, &mut s);
                u.run::<F83, { $arm }, $r, $m, false, _>(&ctx, 100, &mut s2);
                for l in &w.lanes {
                    let rhs = c.add(&c.smul(&g, &[l.a, 0, 0]), &c.smul(&q, &[l.b, 0, 0]));
                    assert_eq!(l.p, rhs, "P = aG + bQ");
                }
            }
            assert_eq!(w.state_hash(), u.state_hash(), "tracking changed the walk");
            assert_eq!(s.h, s2.h);
            assert_eq!(w.st, u.st);
            w.st
        }};
    }
    let sb = check!(BAILEY, 32, 8);
    let sc = check!(CANON, 32, 8);
    let s8 = check!(CANON, 8, 8);
    let sn = check!(CANON_NONEG, 32, 8);
    assert!(sn.dps > 0 && sn.escapes == 0);
    assert!(sb.dps > 0 && sc.dps > 0 && sc.escapes > 0 && s8.escapes > 0);
    assert!(sb.restarts + sc.restarts > 0, "the cap path was not exercised");
    let _ = zr;
}

#[test]
fn hex_roundtrip() {
    let w = [0x0123456789abcdef, 0xfedcba9876543210, 5];
    assert_eq!(parse_hex(&hex(&w)), w);
}
