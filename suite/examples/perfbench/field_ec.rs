//! Area `field_ec`: field and elliptic-curve arithmetic: F_2^m, F_p, F_3^m,
//! point addition, scalar multiplication, batch inversion.

use crate::harness::{Closure, Fp, Kernel, Tier, Workload};
use cryptanalysis_suite::ecc::curve::CurveParams;
use cryptanalysis_suite::ecc::point::Point;
use num_bigint::BigUint;

fn point_fp(fp: Fp, p: &Point) -> Fp {
    match p {
        Point::Infinity => fp.u64(0),
        Point::Affine { x, y } => fp
            .u64(1)
            .bytes(&x.value.to_bytes_le())
            .bytes(&y.value.to_bytes_le()),
    }
}

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

pub fn register(kernels: &mut Vec<Kernel>) {
    kernels.push(Kernel {
        id: "field_ec/point_scalar_mul_p256_x8",
        area: "field_ec",
        desc: "ecc::point::Point::scalar_mul of the P-256 generator by 8 fixed scalars",
        tier: Tier::Quick,
        setup: scalar_mul_p256,
    });
    kernels.push(Kernel {
        id: "field_ec/point_scalar_mul_secp256k1_x8",
        area: "field_ec",
        desc: "ecc::point::Point::scalar_mul of the secp256k1 generator by 8 fixed scalars",
        tier: Tier::Quick,
        setup: scalar_mul_secp256k1,
    });
}
