//! Mirrors `tests/test_ffi.c` from the C library, exercising every solver on
//! the same instances through the safe API.

use cryptanalysis::index_calculus::{self, IcContext, IcMethod, IcParams};
use cryptanalysis::{
    cheon_best_divisor, factorize, invmod, is_prime, next_prime, powmod, primitive_root, Elem,
    Error, Group, Kind, Options, PrecompOptions, Solver,
};

const P: u64 = 2_000_000_579;
const Q: u64 = 1_000_000_289;
const X: u64 = 123_456_789;

fn zp_instance() -> (Group, Elem, Elem) {
    let g = Group::zp(P, Q).expect("Z_p^* context");
    let gen = g.find_generator(1).expect("generator");
    let h = g.mul(&gen, X).expect("mul");
    (g, gen, h)
}

fn seeded() -> Options {
    Options {
        seed: 7,
        ..Options::default()
    }
}

#[test]
fn version_matches_header() {
    assert_eq!(cryptanalysis::version(), "0.1.0");
}

#[test]
fn zp_construction_and_accessors() {
    let g = Group::zp(P, Q).unwrap();
    assert_eq!(g.kind(), Kind::Zp);
    assert_eq!(g.p(), P);
    assert_eq!(g.order(), Q);
    assert_eq!(g.cofactor(), 2);
    assert!(matches!(Group::zp(1000, 0), Err(Error::Invalid(_))));
    let dbg = format!("{g:?}");
    assert!(dbg.contains("Zp"), "{dbg}");
}

#[test]
fn zp_element_ops() {
    let (g, gen, _) = zp_instance();
    assert!(g.validate(&gen));
    assert!(!g.validate(&Elem::zp(0)));
    assert!(!g.validate(&Elem::zp(P)));

    let t = g.op(&gen, &gen).unwrap();
    let g2 = g.mul(&gen, 2).unwrap();
    assert!(g.equal(&t, &g2));
    assert_eq!(t, g2);

    let inv = g.inv(&gen).unwrap();
    let one = g.op(&inv, &gen).unwrap();
    assert!(g.is_identity(&one));
    assert_eq!(one, g.identity());
    assert_eq!(g.identity(), Elem::zp(1));

    assert_eq!(g.elem_order(&gen).unwrap(), Q);
    assert!(matches!(g.op(&Elem::zp(0), &gen), Err(Error::Invalid(_))));
    assert!(matches!(g.lift_x(5), Err(Error::Unsupported(_))));

    let r = g.random_element(11).unwrap();
    assert!(g.validate(&r));
    // random_element multiplies by the cofactor, so r lies in the subgroup.
    assert!(g.is_identity(&g.mul(&r, Q).unwrap()));
}

#[test]
fn zp_bsgs() {
    let (g, gen, h) = zp_instance();
    let (x, st) = g.bsgs(&gen, &h, 0, 0, &seeded()).unwrap();
    assert_eq!(x, X);
    assert!(st.group_ops > 0);
    assert!(st.table_entries > 0);
}

#[test]
fn zp_rho_single_and_multi_thread() {
    let (g, gen, h) = zp_instance();
    let (x, st) = g.rho(&gen, &h, &seeded()).unwrap();
    assert_eq!(x, X);
    assert!(st.group_ops > 0);
    assert_eq!(st.threads, 1);

    let opts = Options {
        threads: 2,
        ..seeded()
    };
    let (x, st) = g.rho(&gen, &h, &opts).unwrap();
    assert_eq!(x, X);
    assert_eq!(st.threads, 2);
}

#[test]
fn zp_kangaroo_interval() {
    let (g, gen, h) = zp_instance();
    let (x, st) = g
        .kangaroo(&gen, &h, 123_000_000, 124_000_000, &seeded())
        .unwrap();
    assert_eq!(x, X);
    assert!(st.group_ops > 0);
}

#[test]
fn zp_grumpy_interval() {
    let (g, gen, h) = zp_instance();
    let (x, st) = g
        .grumpy(&gen, &h, 123_000_000, 124_000_000, &seeded())
        .unwrap();
    assert_eq!(x, X);
    assert!(st.group_ops > 0);
}

#[test]
fn zp_dlog_every_solver() {
    let (g, gen, h) = zp_instance();
    for solver in [
        Solver::Auto,
        Solver::Bsgs,
        Solver::Rho,
        Solver::Kangaroo,
        Solver::Grumpy,
    ] {
        let opts = Options { solver, ..seeded() };
        let (x, st) = g
            .dlog(&gen, &h, &opts)
            .unwrap_or_else(|e| panic!("{solver:?}: {e}"));
        assert_eq!(x, X, "{solver:?}");
        assert!(st.group_ops > 0, "{solver:?}");
    }
}

#[test]
fn zp_bsgs_interval_miss_is_not_found() {
    let (g, gen, h) = zp_instance();
    // x = 123456789 is outside [1, 1000].
    let err = g.bsgs(&gen, &h, 1, 1000, &seeded()).unwrap_err();
    assert!(matches!(err, Error::NotFound(_)), "{err}");
    assert_eq!(err.status(), cryptanalysis::sys::CA_ERR_NOT_FOUND);
}

#[test]
fn zp_max_ops_limit() {
    let (g, gen, h) = zp_instance();
    let opts = Options {
        max_ops: 10,
        ..seeded()
    };
    let err = g.rho(&gen, &h, &opts).unwrap_err();
    assert!(matches!(err, Error::Limit(_)), "{err}");
}

#[test]
fn zp_cheon() {
    let (g, gen, _) = zp_instance();
    let (d, cost) = cheon_best_divisor(Q);
    assert!(d > 1);
    assert_eq!((Q - 1) % d, 0);
    assert!(cost > 0.0);
    let alpha = 987_654_321;
    let (ga, gad) = g.cheon_instance(&gen, alpha, d).unwrap();
    assert_eq!(ga, g.mul(&gen, alpha).unwrap());
    let (found, st) = g.cheon(&gen, &ga, &gad, d, 0).unwrap();
    assert_eq!(found, alpha);
    assert!(st.iterations > 0);

    // A tiny exponentiation budget must trip the limit.
    let err = g.cheon(&gen, &ga, &gad, d, 1).unwrap_err();
    assert!(matches!(err, Error::Limit(_)), "{err}");
}

#[test]
fn zp_precomp() {
    let (g, gen, h) = zp_instance();
    let opts = PrecompOptions {
        threads: 4,
        seed: 7,
        ..PrecompOptions::default()
    };
    let (x, st) = g.precomp(&gen, &h, &opts).unwrap();
    assert_eq!(x, X);
    // Stats cover the n^{2/3} build, so far more than one online walk.
    assert!(st.group_ops > 0);
    assert!(st.table_entries > 0);
}

#[test]
fn ec_curve_end_to_end() {
    let p = 1_000_003;
    let n = Group::ec_count_points(p, 1, 7).unwrap();
    // Hasse: |n - (p + 1)| <= 2 sqrt(p).
    assert!((n as i128 - (p as i128 + 1)).abs() <= 2 * 1001);

    let mut e = Group::ec(p, 1, 7, n).unwrap();
    assert_eq!(e.kind(), Kind::Ec);
    assert_eq!(e.p(), p);
    assert_eq!((e.curve_a(), e.curve_b()), (1, 7));
    assert_eq!(e.order(), n);
    assert!(matches!(Group::ec(97, 0, 0, 0), Err(Error::Invalid(_))));

    let pt = e.random_element(3).unwrap();
    assert!(!pt.is_infinity());
    assert!(e.validate(&pt));
    assert!(!e.validate(&Elem::ec(pt.x(), pt.y() ^ 1)));

    let ord = e.elem_order(&pt).unwrap();
    assert_eq!(n % ord, 0);
    e.set_order(ord, n / ord);
    assert_eq!(e.order(), ord);
    assert_eq!(e.cofactor(), n / ord);

    let q = e.mul(&pt, 4242).unwrap();
    let (x, st) = e.dlog(&pt, &q, &Options::default()).unwrap();
    assert_eq!(x, 4242 % ord);
    assert!(st.group_ops > 0);

    let inf = e.identity();
    assert!(inf.is_infinity());
    assert_eq!(inf, Elem::ec_infinity());
    assert!(e.is_identity(&inf));
    assert_eq!(e.op(&pt, &inf).unwrap(), pt);
    let neg = e.inv(&pt).unwrap();
    assert!(e.is_identity(&e.op(&pt, &neg).unwrap()));

    let lifted = e.lift_x(pt.x()).unwrap();
    assert_eq!(lifted.x(), pt.x());
    assert!(lifted.y() == pt.y() || lifted.y() == p - pt.y());

    // The whole-group and interval solvers work on curves as well.
    let (x, _) = e.bsgs(&pt, &q, 0, 0, &Options::default()).unwrap();
    assert_eq!(x, 4242 % ord);
    let (x, _) = e
        .kangaroo(&pt, &q, 4000, 5000, &Options::default())
        .unwrap();
    assert_eq!(x, 4242);
    let (x, _) = e.grumpy(&pt, &q, 4000, 5000, &Options::default()).unwrap();
    assert_eq!(x, 4242);
    let (x, _) = e
        .rho(
            &pt,
            &q,
            &Options {
                seed: 5,
                ..Options::default()
            },
        )
        .unwrap();
    assert_eq!(x, 4242 % ord);
    let (x, _) = e
        .precomp(
            &pt,
            &q,
            &PrecompOptions {
                seed: 5,
                ..PrecompOptions::default()
            },
        )
        .unwrap();
    assert_eq!(x, 4242 % ord);
}

#[test]
fn index_calculus_one_shot() {
    let params = IcParams {
        seed: 3,
        ..IcParams::default()
    };
    assert_eq!(params.method, IcMethod::LinearSieve);
    let (x, st) = index_calculus::solve(1_000_003, 2, 424_242, &params).unwrap();
    assert_eq!(powmod(2, x, 1_000_003), 424_242);
    assert!(st.factor_base_size > 0);
    assert!(st.relations >= st.unknowns);
    assert_eq!(st.verified_logs, st.factor_base_size);
}

#[test]
fn index_calculus_random_exponent_method() {
    let params = IcParams {
        seed: 3,
        method: IcMethod::RandomExponent,
        ..IcParams::default()
    };
    let (x, st) = index_calculus::solve(1_000_003, 2, 424_242, &params).unwrap();
    assert_eq!(powmod(2, x, 1_000_003), 424_242);
    assert!(st.smooth_tests > 0);
}

#[test]
fn index_calculus_context_reuse() {
    let params = IcParams {
        seed: 3,
        ..IcParams::default()
    };
    let (mut ctx, st) = IcContext::precompute(1_000_003, 2, &params).unwrap();
    assert_eq!(ctx.modulus(), 1_000_003);
    assert_eq!(ctx.primitive_root(), 2);
    assert_eq!(ctx.factor_base_size(), st.factor_base_size);
    // Every factor-base log is verified, so each must be known and correct.
    for i in 0..ctx.factor_base_size() {
        let (prime, log) = ctx.factor_base_log(i).expect("known log");
        assert_eq!(
            powmod(ctx.primitive_root(), log, 1_000_003),
            u64::from(prime)
        );
    }
    assert!(ctx.factor_base_log(ctx.factor_base_size()).is_none());
    for h in [424_242u64, 3, 999_999, 500_000] {
        let (x, st) = ctx.log(h).unwrap();
        assert_eq!(powmod(2, x, 1_000_003), h);
        assert!(st.group_ops > 0 || st.iterations > 0 || x < 1_000_003);
    }
    let (b, c) = index_calculus::auto_params(20);
    assert!(b > 0 && c > 0);
}

#[test]
fn number_theory_helpers() {
    assert!(is_prime(1_000_003));
    assert!(!is_prime(1_000_002));
    assert_eq!(next_prime(1_000_003), 1_000_033);
    assert_eq!(primitive_root(1_000_003), 2);
    assert_eq!(powmod(2, 10, 1_000_003), 1024);
    let inv = invmod(3, 1_000_003);
    assert_eq!((3 * inv) % 1_000_003, 1);
    assert_eq!(factorize(1_000_002), vec![(2, 1), (3, 1), (166_667, 1)]);
    assert_eq!(factorize(1), vec![]);
    assert_eq!(factorize(1 << 20), vec![(2, 20)]);
}

#[test]
fn group_usable_from_multiple_threads() {
    let (g, gen, h) = zp_instance();
    std::thread::scope(|s| {
        for seed in 1..=4u64 {
            let (g, gen, h) = (&g, &gen, &h);
            s.spawn(move || {
                let opts = Options {
                    seed,
                    ..Options::default()
                };
                let (x, _) = g.dlog(gen, h, &opts).unwrap();
                assert_eq!(x, X);
            });
        }
    });
}
