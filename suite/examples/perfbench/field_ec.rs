//! Area `field_ec`: field and elliptic-curve arithmetic: F_2^m, F_p, F_3^m,
//! point addition, scalar multiplication, batch inversion.
//!
//! Cells:
//!
//! - **Single-word `F_{2^n}`** (`semaev_decomp::Gf2`, `n ≤ 63`): the field
//!   under every Koblitz index-calculus hot loop.  `n = 53` with the
//!   reduction polynomial `KoblitzCurve::new(0, 53)` picks, as the `k0n53`
//!   pipeline runs it.
//! - **Koblitz scan kernels** (`koblitz_fast`): `FastCurve::add_many_lazy`
//!   (the decomposition scan's `R − P_k` block) and `FrobeniusCanon`
//!   (the folded table's orbit key), on that same curve.
//! - **Multi-word `F_{2^m}`** (`binary_ecc::F2mElement`, `m = 131, 163,
//!   233`) and the affine `binary_ecc::curve::scalar_mul` over it.
//! - **Prime fields**: ECDSA verification (`ecc::ecdsa::verify_hash`),
//!   the constant-time fixed-width ladders (`ct_scalar_mul_p256`,
//!   `secp256k1_point::ct_scalar_mul`), the `num-bigint` affine
//!   `Point::scalar_mul_ct` the `j = 0` index calculus calls, and the
//!   one-word Montgomery field of `bsgs_fast`.
//! - **`F_{3^m}`** (`gf3m::Gf3`) and genus-2 Cantor arithmetic
//!   (`prime_hyperelliptic::MumfordDivisorP`).
//!
//! Inputs are seeded; curves, points and scalars are built in the untimed
//! setup.  Every kernel fingerprints every element it computes.
//!
//! These are the crypto crate's `field_ec` kernels, same IDs and inputs.
//! This crate compiles the AVX-512 kernels of `koblitz_fast` only on a
//! toolchain where AVX-512 is stable (1.89+, the `suite_avx512` cfg of
//! `build.rs`); an older toolchain times the scalar path.

use crate::harness::{Closure, Fp, Fresh, Kernel, Tier, Workload};
use cryptanalysis_suite::binary_ecc::curve::scalar_mul as binary_scalar_mul;
use cryptanalysis_suite::binary_ecc::{BinaryCurve, BinaryPoint, F2mElement, IrreduciblePoly};
use cryptanalysis_suite::cryptanalysis::bsgs_fast::FastField;
use cryptanalysis_suite::cryptanalysis::gf3m::{Gf3, Gf3Elem};
use cryptanalysis_suite::cryptanalysis::koblitz_fast::{
    BatchScratch, FastCurve, FastPoint, FrobeniusCanon,
};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::KoblitzCurve;
use cryptanalysis_suite::cryptanalysis::semaev_decomp::Gf2;
use cryptanalysis_suite::ecc::curve::CurveParams;
use cryptanalysis_suite::ecc::ecdsa::{sign_hash, verify_hash};
use cryptanalysis_suite::ecc::keys::EccKeyPair;
use cryptanalysis_suite::ecc::p256_point::ct_scalar_mul_p256;
use cryptanalysis_suite::ecc::point::Point;
use cryptanalysis_suite::ecc::secp256k1_point::ct_scalar_mul as ct_scalar_mul_secp256k1;
use cryptanalysis_suite::prime_hyperelliptic::{FpPoly, HyperellipticCurveP, MumfordDivisorP};
use num_bigint::BigUint;
use rand::{rngs::StdRng, Rng, SeedableRng};

fn point_fp(fp: Fp, p: &Point) -> Fp {
    match p {
        Point::Infinity => fp.u64(0),
        Point::Affine { x, y } => fp
            .u64(1)
            .bytes(&x.value.to_bytes_le())
            .bytes(&y.value.to_bytes_le()),
    }
}

fn binary_point_fp(fp: Fp, p: &BinaryPoint) -> Fp {
    match p {
        BinaryPoint::Infinity => fp.u64(0),
        BinaryPoint::Affine { x, y } => fp.u64(1).words(x.raw_bits()).words(y.raw_bits()),
    }
}

fn fast_point_fp(fp: Fp, p: &FastPoint) -> Fp {
    fp.bool(p.infinity).u64(p.x).u64(p.y)
}

/// `count` fixed pseudo-random scalars below `n`.
fn scalars_below(n: &BigUint, count: usize, seed: u64) -> Vec<BigUint> {
    let mut k = BigUint::from(seed);
    (0..count)
        .map(|_| {
            k = (&k * &k + 0x1234_5677u32) % n;
            k.clone()
        })
        .collect()
}

// ── Prime-field scalar multiplication (variable time) ───────────────

/// `k·G` for eight fixed pseudo-random scalars below the order, through
/// the public-input `Point::scalar_mul` every verification in the crate
/// uses.
fn scalar_mul_on(curve: CurveParams) -> Box<dyn Workload> {
    let g = curve.generator();
    let a = curve.a_fe();
    let mut k = BigUint::from(0x9e37_79b9_7f4a_7c15u64);
    let scalars: Vec<BigUint> = (0..8)
        .map(|_| {
            k = (&k * &k + 0x1234_5677u32) % &curve.n;
            k.clone()
        })
        .collect();
    Box::new(Closure(move || {
        let mut fp = Fp::new();
        for k in &scalars {
            fp = point_fp(fp, &g.scalar_mul(k, &a));
        }
        fp.finish()
    }))
}

fn scalar_mul_p256() -> Box<dyn Workload> {
    scalar_mul_on(CurveParams::p256())
}

fn scalar_mul_secp256k1() -> Box<dyn Workload> {
    scalar_mul_on(CurveParams::secp256k1())
}

// ── Single-word F_{2^n}: semaev_decomp::Gf2 ─────────────────────────

/// The `k0n53` curve: `KoblitzCurve::new(0, 53)`.
fn koblitz_k0n53() -> KoblitzCurve {
    KoblitzCurve::new(0, 53).expect("K_0 over F_2^53")
}

fn gf2_n53() -> Gf2 {
    Gf2::new(&koblitz_k0n53().curve.irreducible)
}

fn random_words(rng: &mut StdRng, count: usize, mask: u64, nonzero: bool) -> Vec<u64> {
    (0..count)
        .map(|_| loop {
            let x = rng.gen::<u64>() & mask;
            if !nonzero || x != 0 {
                break x;
            }
        })
        .collect()
}

/// 256 rounds over 4096 elements of `x ← x·y ⊕ x²`: 1,048,576 `Gf2::mul`
/// and as many `Gf2::sqr`, independent across the row (throughput).
fn gf2_n53_mul_sqr() -> Box<dyn Workload> {
    let f = gf2_n53();
    let mask = (1u64 << f.n) - 1;
    let mut rng = StdRng::seed_from_u64(0x0047_4632_5f6d_756c);
    let xs = random_words(&mut rng, 4096, mask, false);
    let ys = random_words(&mut rng, 4096, mask, false);
    Box::new(Fresh::new(xs, move |xs: &mut Vec<u64>| {
        for _ in 0..256 {
            for (x, &y) in xs.iter_mut().zip(&ys) {
                *x = f.mul(*x, y) ^ f.sqr(*x);
            }
        }
        Fp::new().words(xs).finish()
    }))
}

/// `Gf2::inv` (Itoh–Tsujii) of 16,384 non-zero elements.
fn gf2_n53_inv() -> Box<dyn Workload> {
    let f = gf2_n53();
    let mask = (1u64 << f.n) - 1;
    let mut rng = StdRng::seed_from_u64(0x0047_4632_5f69_6e76);
    let xs = random_words(&mut rng, 16_384, mask, true);
    Box::new(Closure(move || {
        let mut fp = Fp::new();
        for &x in &xs {
            fp = fp.u64(f.inv(x));
        }
        fp.finish()
    }))
}

/// `Gf2::batch_inv` (Montgomery's trick, four lanes) of 65,536 elements,
/// one in 64 of them zero (left as zero), four slices a run.
fn gf2_n53_batch_inv() -> Box<dyn Workload> {
    let f = gf2_n53();
    let mask = (1u64 << f.n) - 1;
    let mut rng = StdRng::seed_from_u64(0x4746_325f_6269_6e76);
    let rows: Vec<Vec<u64>> = (0..4)
        .map(|_| {
            let mut v = random_words(&mut rng, 65_536, mask, true);
            for x in v.iter_mut().step_by(64) {
                *x = 0;
            }
            v
        })
        .collect();
    let mut scratch = Vec::new();
    Box::new(Fresh::new(rows, move |rows: &mut Vec<Vec<u64>>| {
        let mut fp = Fp::new();
        for row in rows.iter_mut() {
            f.batch_inv(row, &mut scratch);
            fp = fp.words(row);
        }
        fp.finish()
    }))
}

// ── Koblitz scan kernels: koblitz_fast ──────────────────────────────

struct K53 {
    fc: FastCurve,
    g: FastPoint,
}

fn k53() -> K53 {
    let kc = koblitz_k0n53();
    let fc = FastCurve::new(&kc.curve).expect("n = 53 fits a word");
    let g = fc.lift(kc.generator());
    K53 { fc, g }
}

fn random_fast_points(k: &K53, rng: &mut StdRng, count: usize) -> Vec<FastPoint> {
    (0..count)
        .map(|_| k.fc.mul(k.g, &BigUint::from(rng.gen::<u64>() | 1)))
        .collect()
}

/// `FastCurve::add_many_lazy` of 64 targets against one block of 2048
/// summands (the decomposition scan's `R − P_k` row), then
/// `finish_lazy` on every eighth sum, as the filter would admit.
fn koblitz_n53_add_many_lazy() -> Box<dyn Workload> {
    let k = k53();
    let mut rng = StdRng::seed_from_u64(0x6b30_6e35_335f_6c7a);
    let summands = random_fast_points(&k, &mut rng, 2048);
    let targets = random_fast_points(&k, &mut rng, 64);
    let mut out = Vec::new();
    let mut lambdas = Vec::new();
    let mut scratch = BatchScratch::default();
    Box::new(Closure(move || {
        let mut fp = Fp::new();
        for &t in &targets {
            out.clear();
            lambdas.clear();
            k.fc.add_many_lazy(t, &summands, &mut out, &mut lambdas, &mut scratch);
            for (i, (s, &l)) in out.iter().zip(&lambdas).enumerate() {
                fp = fast_point_fp(fp, s).u64(l);
                if i % 8 == 0 {
                    fp = fast_point_fp(fp, &k.fc.finish_lazy(t, *s, l));
                }
            }
        }
        fp.finish()
    }))
}

/// `FrobeniusCanon::canon_in_place` over 262,144 abscissae (the folded
/// table's key, AVX-512 where the CPU has it and the toolchain is 1.89 or
/// newer, see the module note).
fn frobenius_canon_n53_bulk() -> Box<dyn Workload> {
    let k = k53();
    let canon = FrobeniusCanon::new(&k.fc.field, k.fc.n).expect("normal basis");
    let mask = (1u64 << k.fc.n) - 1;
    let mut rng = StdRng::seed_from_u64(0x6361_6e6f_6e5f_626b);
    let xs = random_words(&mut rng, 262_144, mask, false);
    Box::new(Fresh::new(xs, move |xs: &mut Vec<u64>| {
        canon.canon_in_place(xs);
        Fp::new().words(xs).finish()
    }))
}

/// `FrobeniusCanon::canon_with_shift` one abscissa at a time over 262,144
/// abscissae (the scalar key and the rotation the walks carry).
fn frobenius_canon_n53_shift() -> Box<dyn Workload> {
    let k = k53();
    let canon = FrobeniusCanon::new(&k.fc.field, k.fc.n).expect("normal basis");
    let mask = (1u64 << k.fc.n) - 1;
    let mut rng = StdRng::seed_from_u64(0x6361_6e6f_6e5f_7368);
    let xs = random_words(&mut rng, 262_144, mask, false);
    Box::new(Closure(move || {
        let mut fp = Fp::new();
        for &x in &xs {
            let (c, t) = canon.canon_with_shift(x);
            fp = fp.u64(c).u64(u64::from(t));
        }
        fp.finish()
    }))
}

/// `FastCurve::mul` (López–Dahab ladder, one inversion) of the generator
/// by 2048 fixed 64-bit scalars: the probe `[a]G + [b]Q` of every trial.
fn koblitz_n53_fast_mul() -> Box<dyn Workload> {
    let k = k53();
    let mut rng = StdRng::seed_from_u64(0x006b_3533_5f6d_756c);
    let scalars: Vec<BigUint> = (0..2048).map(|_| BigUint::from(rng.gen::<u64>())).collect();
    Box::new(Closure(move || {
        let mut fp = Fp::new();
        for s in &scalars {
            fp = fast_point_fp(fp, &k.fc.mul(k.g, s));
        }
        fp.finish()
    }))
}

/// `KoblitzCurve::mul` (the entry point the Koblitz pipelines call for
/// targets, probes and cofactor clearing; `FastCurve` underneath for
/// `n ≤ 62`) of the `k0n53` generator by 1024 fixed scalars below `r`.
fn koblitz_curve_mul_n53() -> Box<dyn Workload> {
    let kc = koblitz_k0n53();
    let r = kc.subgroup_order.clone();
    let scalars = scalars_below(&r, 1024, 0x6b63_5f6d_756c);
    Box::new(Closure(move || {
        let mut fp = Fp::new();
        for k in &scalars {
            fp = binary_point_fp(fp, &kc.mul(kc.generator(), k));
        }
        fp.finish()
    }))
}

// ── Multi-word F_{2^m}: binary_ecc::F2mElement ──────────────────────

fn random_f2m(rng: &mut StdRng, m: u32, count: usize) -> Vec<F2mElement> {
    let digits = m.div_ceil(32) as usize;
    (0..count)
        .map(|_| loop {
            let v: Vec<u32> = (0..digits).map(|_| rng.gen()).collect();
            let e = F2mElement::from_biguint(&BigUint::from_slice(&v), m);
            if !e.is_zero() {
                break e;
            }
        })
        .collect()
}

/// 64 rounds over 1024 elements of `x ← x·y + x²`: 65,536
/// `F2mElement::mul` and as many `square`.
fn f2m_mul_sqr_on(irr: IrreduciblePoly, seed: u64) -> Box<dyn Workload> {
    let m = irr.degree;
    let mut rng = StdRng::seed_from_u64(seed);
    let xs = random_f2m(&mut rng, m, 1024);
    let ys = random_f2m(&mut rng, m, 1024);
    Box::new(Fresh::new(xs, move |xs: &mut Vec<F2mElement>| {
        for _ in 0..64 {
            for (x, y) in xs.iter_mut().zip(&ys) {
                *x = x.mul(y, &irr).add(&x.square(&irr));
            }
        }
        let mut fp = Fp::new();
        for x in xs.iter() {
            fp = fp.words(x.raw_bits());
        }
        fp.finish()
    }))
}

fn f2m_mul_sqr_m131() -> Box<dyn Workload> {
    f2m_mul_sqr_on(IrreduciblePoly::deg_131(), 0x0066_326d_5f31_3331)
}

fn f2m_mul_sqr_m163() -> Box<dyn Workload> {
    f2m_mul_sqr_on(IrreduciblePoly::deg_163(), 0x0066_326d_5f31_3633)
}

fn f2m_mul_sqr_m233() -> Box<dyn Workload> {
    f2m_mul_sqr_on(IrreduciblePoly::deg_233(), 0x0066_326d_5f32_3333)
}

/// `F2mElement::flt_inverse` (Itoh–Tsujii) of 2048 elements of `F_{2^163}`.
fn f2m_inv_m163() -> Box<dyn Workload> {
    let irr = IrreduciblePoly::deg_163();
    let mut rng = StdRng::seed_from_u64(0x0066_326d_5f69_6e76);
    let xs = random_f2m(&mut rng, 163, 2048);
    Box::new(Closure(move || {
        let mut fp = Fp::new();
        for x in &xs {
            fp = fp.words(x.flt_inverse(&irr).expect("non-zero").raw_bits());
        }
        fp.finish()
    }))
}

/// `binary_ecc::curve::scalar_mul` (affine double-and-add, one Fermat
/// inversion per step) of a curve's generator by eight scalars below its
/// order.
fn binary_scalar_mul_on(curve: BinaryCurve, count: usize) -> Box<dyn Workload> {
    let g = curve.generator.clone();
    let scalars = scalars_below(&curve.order, count, 0x6269_6e5f_736d);
    Box::new(Closure(move || {
        let mut fp = Fp::new();
        for k in &scalars {
            fp = binary_point_fp(fp, &binary_scalar_mul(&curve, &g, k));
        }
        fp.finish()
    }))
}

fn binary_scalar_mul_sect163k1() -> Box<dyn Workload> {
    binary_scalar_mul_on(BinaryCurve::sect163k1(), 8)
}

fn binary_scalar_mul_sect233k1() -> Box<dyn Workload> {
    binary_scalar_mul_on(BinaryCurve::sect233k1(), 4)
}

// ── Prime fields: verification and constant-time ladders ────────────

/// `ecdsa::verify_hash` of four RFC 6979 signatures, each also checked
/// against a tampered hash (the rejecting path does the same work).
fn ecdsa_verify_on(curve: CurveParams) -> Box<dyn Workload> {
    let keys = scalars_below(&curve.n, 4, 0x0065_6364_7361_5f6b);
    let cases: Vec<_> = keys
        .into_iter()
        .enumerate()
        .map(|(i, d)| {
            let kp = EccKeyPair::from_private(d, &curve);
            let hash: Vec<u8> = (0..32u8).map(|b| b.wrapping_mul(31) ^ i as u8).collect();
            let sig = sign_hash(&hash, &kp.private, &curve);
            let mut bad = hash.clone();
            bad[0] ^= 1;
            (kp.public, hash, bad, sig)
        })
        .collect();
    Box::new(Closure(move || {
        let mut fp = Fp::new();
        for (public, hash, bad, sig) in &cases {
            fp = fp
                .bool(verify_hash(hash, public, sig, &curve))
                .bool(verify_hash(bad, public, sig, &curve));
        }
        fp.finish()
    }))
}

fn ecdsa_verify_p256() -> Box<dyn Workload> {
    ecdsa_verify_on(CurveParams::p256())
}

fn ecdsa_verify_secp256k1() -> Box<dyn Workload> {
    ecdsa_verify_on(CurveParams::secp256k1())
}

/// The fixed-width constant-time ladders (`ct_bignum::U256` Montgomery
/// arithmetic, complete projective formulas): `k·G` for sixteen scalars.
fn ct_scalar_mul_on(curve: CurveParams, p256: bool) -> Box<dyn Workload> {
    let g = curve.generator();
    let scalars = scalars_below(&curve.n, 16, 0x0063_745f_736d);
    Box::new(Closure(move || {
        let mut fp = Fp::new();
        for k in &scalars {
            let r = if p256 {
                ct_scalar_mul_p256(&g, k, &curve)
            } else {
                ct_scalar_mul_secp256k1(&g, k, &curve)
            };
            fp = point_fp(fp, &r);
        }
        fp.finish()
    }))
}

fn ct_scalar_mul_p256_x16() -> Box<dyn Workload> {
    ct_scalar_mul_on(CurveParams::p256(), true)
}

fn ct_scalar_mul_secp256k1_x16() -> Box<dyn Workload> {
    ct_scalar_mul_on(CurveParams::secp256k1(), false)
}

/// `ecc::point::Point::scalar_mul_ct` (affine `num-bigint` Montgomery
/// ladder, three affine operations and three Fermat inversions a bit) on
/// secp256k1 at the full 256-bit width, as `ec_index_calculus_j0::
/// psi_eigenvalue` calls it.
fn point_scalar_mul_ct_secp256k1() -> Box<dyn Workload> {
    let curve = CurveParams::secp256k1();
    let g = curve.generator();
    let a = curve.a_fe();
    let bits = curve.order_bits();
    let k = scalars_below(&curve.n, 1, 0x6a30_5f6c_616d)
        .pop()
        .expect("one scalar");
    Box::new(Closure(move || {
        point_fp(Fp::new(), &g.scalar_mul_ct(&k, &a, bits)).finish()
    }))
}

/// `bsgs_fast::FastField` (one-word Montgomery, `p = 2^61 − 1`):
/// `batch_inv` of sixteen 16,384-element slices and `inv` (Fermat) of
/// 4096 elements.
fn fastfield_p61_inv() -> Box<dyn Workload> {
    let p = (1u64 << 61) - 1;
    let f = FastField::new(p).expect("odd prime below 2^63");
    let mut rng = StdRng::seed_from_u64(0x6666_5f70_3631);
    let rows: Vec<Vec<u64>> = (0..16)
        .map(|_| {
            (0..16_384)
                .map(|_| f.to_mont(rng.gen_range(1..p)))
                .collect()
        })
        .collect();
    let singles: Vec<u64> = (0..4096).map(|_| f.to_mont(rng.gen_range(1..p))).collect();
    let mut scratch = vec![0u64; 16_384];
    Box::new(Fresh::new(rows, move |rows: &mut Vec<Vec<u64>>| {
        let mut fp = Fp::new();
        for row in rows.iter_mut() {
            f.batch_inv(row, &mut scratch);
            fp = fp.words(row);
        }
        for &x in &singles {
            fp = fp.u64(f.inv(x));
        }
        fp.finish()
    }))
}

// ── F_{3^m}: gf3m::Gf3 ──────────────────────────────────────────────

/// The first irreducible trinomial `z^m + c₁ z^k + c₀` over `F_3`.
fn gf3_field(m: u32) -> Gf3 {
    let md = m as usize;
    for k in 1..md {
        for c1 in 1..=2u8 {
            for c0 in 1..=2u8 {
                let mut irr = vec![0u8; md + 1];
                irr[0] = c0;
                irr[k] = c1;
                irr[md] = 1;
                if let Ok(f) = Gf3::new(m, &irr) {
                    return f;
                }
            }
        }
    }
    panic!("no irreducible trinomial of degree {m}");
}

/// `Gf3::mul` and `Gf3::sqr` over `F_{3^97}`: 128 rounds of
/// `x ← x·y + x²` over four elements, then one `Gf3::inv`.
fn gf3m_mul_m97() -> Box<dyn Workload> {
    let f = gf3_field(97);
    let mut rng = StdRng::seed_from_u64(0x0067_6633_6d5f_3937);
    let mut elem = || -> Gf3Elem {
        let c: Vec<u8> = (0..97).map(|_| rng.gen_range(0..3u8)).collect();
        f.element(&c).expect("97 trits")
    };
    let xs: Vec<Gf3Elem> = (0..4).map(|_| elem()).collect();
    let ys: Vec<Gf3Elem> = (0..4).map(|_| elem()).collect();
    Box::new(Fresh::new(xs, move |xs: &mut Vec<Gf3Elem>| {
        for _ in 0..128 {
            for (x, y) in xs.iter_mut().zip(&ys) {
                *x = f.add(&f.mul(x, y), &f.sqr(x));
            }
        }
        let mut fp = Fp::new();
        for x in xs.iter() {
            fp = fp.bytes(x.coeffs());
        }
        if !f.is_zero(&xs[0]) {
            fp = fp.bytes(f.inv(&xs[0]).coeffs());
        }
        fp.finish()
    }))
}

// ── Genus-2 Jacobian: prime_hyperelliptic ───────────────────────────

fn poly_fp(fp: Fp, f: &FpPoly) -> Fp {
    f.coeffs
        .iter()
        .fold(fp.usize(f.coeffs.len()), |fp, c| fp.bytes(&c.to_bytes_le()))
}

/// `MumfordDivisorP::scalar_mul` (Cantor over `num-bigint` polynomials)
/// on `y² = x⁵ + 3x³ + 7x + 11` over `F_p`, `p = 2^31 − 1`: a weight-two
/// divisor times four 62-bit scalars.
fn hyperelliptic_g2_scalar_mul() -> Box<dyn Workload> {
    let p = BigUint::from((1u64 << 31) - 1);
    let coeffs: Vec<BigUint> = [11u32, 7, 0, 3, 0, 1].iter().map(|&c| c.into()).collect();
    let curve = HyperellipticCurveP::new(p.clone(), FpPoly::from_coeffs(coeffs, p.clone()), 2);
    // p ≡ 3 (mod 4): a square root is one exponentiation.
    let quarter = (&p + 1u32) >> 2;
    let mut points = (1u32..).filter_map(|x| {
        let x = BigUint::from(x);
        let rhs = curve.f.eval(&x);
        let y = rhs.modpow(&quarter, &p);
        (y != BigUint::from(0u32) && (&y * &y) % &p == rhs).then_some((x, y))
    });
    let mut divisor = || {
        let (x, y) = points.next().expect("a point");
        MumfordDivisorP::from_point(&curve, &x, &y).expect("not Weierstrass")
    };
    let d = divisor().add(&divisor(), &curve);
    let mut rng = StdRng::seed_from_u64(0x6879_705f_6732);
    let scalars: Vec<BigUint> = (0..4)
        .map(|_| BigUint::from(rng.gen::<u64>() >> 2))
        .collect();
    Box::new(Closure(move || {
        let mut fp = Fp::new();
        for k in &scalars {
            let r = d.scalar_mul(k, &curve);
            fp = poly_fp(poly_fp(fp, &r.u), &r.v);
        }
        fp.finish()
    }))
}

pub fn register(kernels: &mut Vec<Kernel>) {
    let mut k =
        |id: &'static str, desc: &'static str, tier: Tier, setup: fn() -> Box<dyn Workload>| {
            kernels.push(Kernel {
                id,
                area: "field_ec",
                desc,
                tier,
                setup,
            });
        };
    k(
        "field_ec/point_scalar_mul_p256_x8",
        "ecc::point::Point::scalar_mul of the P-256 generator by 8 fixed scalars",
        Tier::Quick,
        scalar_mul_p256,
    );
    k(
        "field_ec/point_scalar_mul_secp256k1_x8",
        "ecc::point::Point::scalar_mul of the secp256k1 generator by 8 fixed scalars",
        Tier::Quick,
        scalar_mul_secp256k1,
    );
    k(
        "field_ec/gf2_n53_mul_sqr_1m",
        "semaev_decomp::Gf2 mul + sqr, n = 53 (k0n53 field), 1,048,576 of each",
        Tier::Quick,
        gf2_n53_mul_sqr,
    );
    k(
        "field_ec/gf2_n53_inv_16k",
        "semaev_decomp::Gf2::inv (Itoh-Tsujii), n = 53, 16,384 elements",
        Tier::Quick,
        gf2_n53_inv,
    );
    k(
        "field_ec/gf2_n53_batch_inv_4x64k",
        "semaev_decomp::Gf2::batch_inv, n = 53, four slices of 65,536",
        Tier::Quick,
        gf2_n53_batch_inv,
    );
    k(
        "field_ec/koblitz_n53_add_many_lazy_64x2k",
        "koblitz_fast::FastCurve::add_many_lazy + finish_lazy, k0n53, 64 targets x 2048 summands",
        Tier::Quick,
        koblitz_n53_add_many_lazy,
    );
    k(
        "field_ec/frobenius_canon_n53_bulk_256k",
        "koblitz_fast::FrobeniusCanon::canon_in_place, k0n53, 262,144 abscissae",
        Tier::Quick,
        frobenius_canon_n53_bulk,
    );
    k(
        "field_ec/frobenius_canon_n53_shift_256k",
        "koblitz_fast::FrobeniusCanon::canon_with_shift, k0n53, 262,144 abscissae",
        Tier::Quick,
        frobenius_canon_n53_shift,
    );
    k(
        "field_ec/koblitz_n53_fast_mul_2k",
        "koblitz_fast::FastCurve::mul (Lopez-Dahab ladder), k0n53, 2048 64-bit scalars",
        Tier::Quick,
        koblitz_n53_fast_mul,
    );
    k(
        "field_ec/koblitz_curve_mul_n53_1k",
        "koblitz_index_calculus::KoblitzCurve::mul, k0n53 generator, 1024 scalars below r",
        Tier::Quick,
        koblitz_curve_mul_n53,
    );
    k(
        "field_ec/f2m_mul_sqr_m131_64k",
        "binary_ecc::F2mElement mul + square, m = 131, 65,536 of each",
        Tier::Quick,
        f2m_mul_sqr_m131,
    );
    k(
        "field_ec/f2m_mul_sqr_m163_64k",
        "binary_ecc::F2mElement mul + square, m = 163, 65,536 of each",
        Tier::Quick,
        f2m_mul_sqr_m163,
    );
    k(
        "field_ec/f2m_mul_sqr_m233_64k",
        "binary_ecc::F2mElement mul + square, m = 233, 65,536 of each",
        Tier::Quick,
        f2m_mul_sqr_m233,
    );
    k(
        "field_ec/f2m_inv_m163_2k",
        "binary_ecc::F2mElement::flt_inverse, m = 163, 2048 elements",
        Tier::Quick,
        f2m_inv_m163,
    );
    k(
        "field_ec/binary_scalar_mul_sect163k1_x8",
        "binary_ecc::curve::scalar_mul (affine) of the sect163k1 generator by 8 scalars",
        Tier::Quick,
        binary_scalar_mul_sect163k1,
    );
    k(
        "field_ec/binary_scalar_mul_sect233k1_x4",
        "binary_ecc::curve::scalar_mul (affine) of the sect233k1 generator by 4 scalars",
        Tier::Quick,
        binary_scalar_mul_sect233k1,
    );
    k(
        "field_ec/ecdsa_verify_p256_x4",
        "ecc::ecdsa::verify_hash, P-256, 4 signatures, each also against a tampered hash",
        Tier::Quick,
        ecdsa_verify_p256,
    );
    k(
        "field_ec/ecdsa_verify_secp256k1_x4",
        "ecc::ecdsa::verify_hash, secp256k1, 4 signatures, each also against a tampered hash",
        Tier::Quick,
        ecdsa_verify_secp256k1,
    );
    k(
        "field_ec/ct_scalar_mul_p256_x16",
        "ecc::p256_point::ct_scalar_mul_p256 (U256 Montgomery ladder), 16 scalars",
        Tier::Quick,
        ct_scalar_mul_p256_x16,
    );
    k(
        "field_ec/ct_scalar_mul_secp256k1_x16",
        "ecc::secp256k1_point::ct_scalar_mul (U256 Montgomery ladder), 16 scalars",
        Tier::Quick,
        ct_scalar_mul_secp256k1_x16,
    );
    k(
        "field_ec/point_scalar_mul_ct_secp256k1_x1",
        "ecc::point::Point::scalar_mul_ct (affine num-bigint ladder), secp256k1, 1 scalar",
        Tier::Quick,
        point_scalar_mul_ct_secp256k1,
    );
    k(
        "field_ec/fastfield_p61_inv",
        "bsgs_fast::FastField batch_inv (16 x 16,384) and inv (4096), p = 2^61 - 1",
        Tier::Quick,
        fastfield_p61_inv,
    );
    k(
        "field_ec/gf3m_mul_m97",
        "gf3m::Gf3 mul + sqr over F_3^97, 512 of each, and one inv",
        Tier::Quick,
        gf3m_mul_m97,
    );
    k(
        "field_ec/hyperelliptic_g2_scalar_mul_x4",
        "prime_hyperelliptic::MumfordDivisorP::scalar_mul, genus 2, p = 2^31 - 1, 4 scalars",
        Tier::Quick,
        hyperelliptic_g2_scalar_mul,
    );
}
