//! Integration tests that must pass with *and* without an NVIDIA device.
//!
//! Everything that needs a real GPU is gated behind a runtime
//! `device_count() == 0` skip, so the same binary is meaningful on a GPU box.

use cryptanalysis::{Elem, Group};
use cryptanalysis_cuda::{
    device_count, device_name, embedded_ptx, ptx_source, solve, CudaRho, Error, Params, PtxSource,
    WALKS_PER_THREAD,
};

fn zp_instance(x: u64) -> (Group, Elem, Elem) {
    let g = Group::zp(2_000_000_579, 1_000_000_289).expect("safe-prime fixture");
    let base = g.find_generator(1).expect("generator");
    let target = g.mul(&base, x).expect("scalar multiplication");
    (g, base, target)
}

/// The headline property of this crate on a GPU-less machine: nothing panics.
#[test]
fn device_count_is_safe_without_a_driver() {
    let n = device_count();
    // Calling it twice exercises the cached probe as well.
    assert_eq!(n, device_count());
    eprintln!("device_count() = {n}");
}

#[test]
fn ptx_source_is_reported() {
    let s = ptx_source();
    eprintln!("ptx_source() = {s}");
    match s {
        PtxSource::Embedded => assert!(embedded_ptx().is_some()),
        PtxSource::Nvrtc | PtxSource::Unavailable => assert!(embedded_ptx().is_none()),
    }
}

/// When `build.rs` found a CUDA compiler (e.g. `CUDA_PATH=... cargo test`),
/// the embedded PTX must be the real thing.
#[test]
fn embedded_ptx_is_well_formed() {
    let Some(ptx) = embedded_ptx() else {
        eprintln!("skipping: no CUDA compiler at build time, nothing embedded");
        return;
    };
    assert!(!ptx.is_empty());
    assert!(
        ptx.contains(".target sm_"),
        "PTX names a target architecture"
    );
    assert!(
        ptx.contains("ca_rho_walk_kernel"),
        "PTX contains our kernel's entry point"
    );
    assert!(
        ptx.contains(".visible .entry"),
        "the kernel is externally visible"
    );
    assert_eq!(ptx_source(), PtxSource::Embedded);
}

/// `solve` must fail cleanly - not panic - when there is no device.
#[test]
fn solve_without_a_device_returns_an_error() {
    if device_count() != 0 {
        eprintln!("skipping: this machine has a CUDA device");
        return;
    }
    let (g, base, target) = zp_instance(123_456_789);
    let params = Params {
        seed: 7,
        ..Params::default()
    };
    match solve(&g, base, target, &params) {
        Err(Error::NoDriver) | Err(Error::NoDevice { .. }) | Err(Error::PtxUnavailable(_)) => {}
        Err(other) => panic!("unexpected error: {other}"),
        Ok((x, _)) => panic!("solved {x} without a device?"),
    }
    assert!(CudaRho::new(&params).is_err());
    assert!(device_name(0).is_err());
}

/// An out-of-range device ordinal is rejected with `NoDevice`, on every machine.
#[test]
fn absurd_device_ordinal_is_rejected() {
    let params = Params {
        device: 4096,
        ..Params::default()
    };
    match CudaRho::new(&params) {
        Err(Error::NoDevice {
            requested,
            available,
        }) => {
            assert_eq!(requested, 4096);
            assert_eq!(available, device_count());
        }
        Err(Error::NoDriver) => assert_eq!(device_count(), 0),
        Err(other) => panic!("unexpected error: {other}"),
        Ok(_) => panic!("device 4096 exists?"),
    }
}

/// Tiny groups never reach the GPU: `ca_gpu_rho_solve` brute-forces anything
/// below 4096, and so do we.  This runs everywhere.
#[test]
fn tiny_groups_are_solved_on_the_host() {
    // Z_p^* of order 1000 (p = 1009 has p - 1 = 1008 = 2^4 * 3^2 * 7).
    let g = Group::zp(1009, 1008).expect("small prime");
    let base = g.find_generator(3).expect("generator");
    let params = Params::default();
    for x in [0u64, 1, 2, 17, 1007] {
        let target = g.mul(&base, x).expect("scalar multiplication");
        let (got, stats) = solve(&g, base, target, &params).expect("brute force");
        assert!(
            g.equal(&g.mul(&base, got).unwrap(), &target),
            "x={x} got={got}"
        );
        assert_eq!(stats.launches, 0, "no kernel launch for a tiny group");
    }
}

/// A group without a known order cannot be attacked this way.
#[test]
fn unknown_order_is_rejected() {
    let g = Group::ec(1_000_003, 1, 7, 0).expect("curve with unknown order");
    assert_eq!(g.order(), 0);
    let base = Elem::ec_infinity();
    let target = Elem::ec(1, 1);
    match solve(&g, base, target, &Params::default()) {
        Err(Error::Invalid(msg)) => assert!(msg.contains("order"), "{msg}"),
        other => panic!("expected Error::Invalid, got {other:?}"),
    }
}

/// The real thing, on hardware only.
#[test]
fn solves_a_31_bit_zp_instance_on_the_gpu() {
    if device_count() == 0 {
        eprintln!("skipping: no CUDA device on this machine");
        return;
    }
    let params = Params {
        seed: 500,
        ..Params::default()
    };
    let rho = CudaRho::new(&params).expect("device 0");
    eprintln!(
        "device 0: {} (PTX: {})",
        rho.device_name().unwrap_or_default(),
        rho.ptx_source()
    );
    for x in [1u64, 123_456_789, 999_999_999] {
        let (g, base, target) = zp_instance(x);
        let (got, stats) = rho.solve(&g, base, target, &params).expect("solve");
        assert_eq!(got, x);
        assert!(stats.launches >= 1);
        assert_eq!(
            stats.walks(),
            u64::from(stats.threads) * u64::from(WALKS_PER_THREAD)
        );
    }
}

/// The negation map path, on hardware only: a curve fixture from
/// `tests/test_gpu.c` (`y^2 = x^3 + 3x + 11` over `F_1000000007`).
#[test]
fn solves_an_elliptic_curve_instance_on_the_gpu() {
    if device_count() == 0 {
        eprintln!("skipping: no CUDA device on this machine");
        return;
    }
    let (p, a, b) = (1_000_000_007u64, 3u64, 11u64);
    let order = Group::ec_count_points(p, a, b).expect("point count");
    let g = Group::ec(p, a, b, order).expect("curve");
    let base = g.find_generator(1).expect("generator");
    let x = 777_777 % order;
    let target = g.mul(&base, x).expect("scalar multiplication");
    for negation_map in [true, false] {
        let params = Params {
            seed: 500,
            negation_map,
            ..Params::default()
        };
        let (got, _stats) = solve(&g, base, target, &params).expect("solve");
        assert_eq!(got, x, "negation_map={negation_map}");
    }
}

/// `max_ops` must stop the search, on hardware only (the limit is only
/// checked between launches).
#[test]
fn max_ops_is_honoured_on_the_gpu() {
    if device_count() == 0 {
        eprintln!("skipping: no CUDA device on this machine");
        return;
    }
    let (g, base, target) = zp_instance(123_456_789);
    let params = Params {
        blocks: 1,
        threads_per_block: 4,
        dp_bits: 2,
        steps_per_launch: 16,
        seed: 9,
        max_ops: 1000,
        ..Params::default()
    };
    match solve(&g, base, target, &params) {
        Err(Error::Limit { ops }) => assert!(ops > 1000),
        Ok((x, st)) => panic!("solved {x} within the limit ({} ops)", st.group_ops),
        Err(other) => panic!("unexpected error: {other}"),
    }
}
