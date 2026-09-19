//! The host driver: a port of `ca_gpu_rho_solve` onto the CUDA driver API.

use std::collections::HashMap;
use std::sync::Arc;
use std::time::Instant;

use cryptanalysis::{Elem, Group, Kind};
use cudarc::driver::{
    CudaContext, CudaFunction, CudaModule, CudaStream, DevicePtr, DevicePtrMut, LaunchConfig,
    PushKernelArg,
};

use crate::args::{GpuRhoArgs, KIND_EC, KIND_ZP};
use crate::arith::{self, Mont, Rng};
use crate::error::{Error, Result};
use crate::kernel::{self, PtxSource};
use crate::plan::{Params, Plan};
use crate::{probe, Stats, WALKS_PER_THREAD};

/// The number of usable CUDA devices, or 0 when there is no driver.
///
/// Never panics and never fails: a machine without an NVIDIA driver simply
/// reports 0.  (`cudarc`'s dynamic loader aborts the process with a panic if
/// asked for a symbol from a missing `libcuda`, so the library is probed with
/// `dlopen` first.)
///
/// ```
/// // Safe to call anywhere, GPU or not.
/// let n = cryptanalysis_cuda::device_count();
/// println!("{n} CUDA devices");
/// ```
pub fn device_count() -> usize {
    if !probe::driver_available() {
        return 0;
    }
    match CudaContext::device_count() {
        Ok(n) if n > 0 => n as usize,
        _ => 0,
    }
}

/// The name of a CUDA device, e.g. `"NVIDIA A100-SXM4-40GB"`.
pub fn device_name(device: usize) -> Result<String> {
    Ok(open_context(device)?.name()?)
}

fn open_context(device: usize) -> Result<Arc<CudaContext>> {
    if !probe::driver_available() {
        return Err(Error::NoDriver);
    }
    let available = device_count();
    if device >= available {
        return Err(Error::NoDevice {
            requested: device,
            available,
        });
    }
    Ok(CudaContext::new(device)?)
}

/// A GPU context with our kernel loaded, ready to solve logarithms.
///
/// Creating one is the expensive part (context creation plus, on the NVRTC
/// path, compiling the kernel), so keep it alive across calls to
/// [`CudaRho::solve`].
///
/// ```no_run
/// use cryptanalysis::{Group, Elem};
/// use cryptanalysis_cuda::{CudaRho, Params};
///
/// let params = Params { seed: 7, ..Params::default() };
/// let rho = CudaRho::new(&params)?;
/// let g = Group::zp(2_000_000_579, 1_000_000_289)?;
/// let base = g.find_generator(1)?;
/// let target = g.mul(&base, 123_456_789)?;
/// let (x, stats) = rho.solve(&g, base, target, &params)?;
/// assert_eq!(x, 123_456_789);
/// println!("{} launches, {} DPs", stats.launches, stats.dps);
/// # Ok::<(), cryptanalysis_cuda::Error>(())
/// ```
pub struct CudaRho {
    ctx: Arc<CudaContext>,
    stream: Arc<CudaStream>,
    // Kept alive for as long as `func` refers into it (CudaFunction holds its
    // own Arc, but keeping it here makes the ownership obvious).
    _module: Arc<CudaModule>,
    func: CudaFunction,
    source: PtxSource,
    device: usize,
}

impl std::fmt::Debug for CudaRho {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("CudaRho")
            .field("device", &self.device)
            .field("ptx_source", &self.source)
            .finish_non_exhaustive()
    }
}

impl CudaRho {
    /// Open `params.device` and load `ca_rho_walk_kernel` onto it.
    ///
    /// Only [`Params::device`] is read here; every other field is taken from
    /// the [`Params`] passed to [`CudaRho::solve`].
    pub fn new(params: &Params) -> Result<CudaRho> {
        let ctx = open_context(params.device)?;
        let kernel = kernel::load(None)?;
        let module = ctx.load_module(kernel.ptx)?;
        let func = module.load_function(kernel.entry)?;
        let stream = ctx.default_stream();
        Ok(CudaRho {
            ctx,
            stream,
            _module: module,
            func,
            source: kernel.source,
            device: params.device,
        })
    }

    /// How the kernel was obtained for this instance.
    pub fn ptx_source(&self) -> PtxSource {
        self.source
    }

    /// The device ordinal this instance runs on.
    pub fn device(&self) -> usize {
        self.device
    }

    /// The device's name.
    pub fn device_name(&self) -> Result<String> {
        Ok(self.ctx.name()?)
    }

    /// Solve `base^x == target` (`x * base == target` on a curve) in the
    /// group, which must have a known order.
    ///
    /// This mirrors `ca_gpu_rho_solve`: the multiplier table is built on the
    /// host through the `cryptanalysis` crate, the walks live on the device,
    /// and distinguished points are drained into a host table after every
    /// launch.  A second arrival at the same distinguished point with a
    /// different `(a, b)` pair yields the logarithm; the same pair means the
    /// walk ran onto its own trail and it is re-seeded.  Every candidate
    /// exponent is verified with a scalar multiplication before it is
    /// returned, so a wrong answer is impossible.
    pub fn solve(
        &self,
        group: &Group,
        base: Elem,
        target: Elem,
        params: &Params,
    ) -> Result<(u64, Stats)> {
        let started = Instant::now();
        if let Some(done) = preflight(group, &base, &target, started) {
            return done;
        }
        let n = group.order();

        let mont = Mont::new(group.p())
            .ok_or_else(|| Error::Invalid(format!("modulus {} is not odd", group.p())))?;
        let kind = match group.kind() {
            Kind::Ec => KIND_EC,
            Kind::Zp => KIND_ZP,
        };
        let negmap = params.negation_map && kind == KIND_EC;
        let seed = arith::seed_or_random(params.seed);
        let plan = Plan::new(n, negmap, params, true);

        let mut args = GpuRhoArgs {
            p: mont.p,
            pinv: mont.pinv,
            one: mont.r1,
            a_mont: if kind == KIND_EC {
                mont.to(group.curve_a())
            } else {
                0
            },
            n,
            dp_mask: plan.dp_mask,
            seed,
            kind,
            negmap: u32::from(negmap),
            r: plan.r,
            steps: plan.steps,
            nthreads: plan.nthreads,
            dp_cap: plan.dp_cap,
            abandon_shift: plan.abandon_shift,
            ..GpuRhoArgs::default()
        };
        let (bx, by) = internal_words(&mont, kind, &base);
        let (tx, ty) = internal_words(&mont, kind, &target);
        args.base_x = bx;
        args.base_y = by;
        args.target_x = tx;
        args.target_y = ty;

        // ---- multipliers (host) -------------------------------------------
        let mut rng = Rng::new(seed);
        let mut mult = vec![0u64; plan.r as usize * 4];
        let mut setup_ops = 0u64;
        for i in 0..plan.r as usize {
            let al = rng.below(n);
            let be = rng.below(n);
            let t1 = group.mul(&base, al)?;
            let t2 = group.mul(&target, be)?;
            setup_ops += arith::mul_ops(al) + arith::mul_ops(be);
            let m = group.op(&t1, &t2)?;
            let (mx, my) = internal_words(&mont, kind, &m);
            mult[4 * i] = mx;
            mult[4 * i + 1] = my;
            mult[4 * i + 2] = al;
            mult[4 * i + 3] = be;
        }

        // ---- device buffers ----------------------------------------------
        let nwalks = plan.nwalks as usize;
        let stream = &self.stream;
        let d_mult = stream.memcpy_stod(&mult)?;
        let mut d_state = stream.alloc_zeros::<u64>(nwalks * 4)?;
        let mut d_aux = stream.alloc_zeros::<u64>(nwalks * crate::AUX_WORDS)?;
        let mut d_dp = stream.alloc_zeros::<u64>(plan.dp_cap as usize * 4)?;
        let mut d_count = stream.alloc_zeros::<u32>(1)?;
        let mut d_restart = stream.alloc_zeros::<u8>(nwalks)?;

        // Every walk is seeded on the first launch.
        let mut h_restart = vec![1u8; nwalks];
        let mut restart_dirty = true;
        let mut h_dp = vec![0u64; plan.dp_cap as usize * 4];

        let cfg = LaunchConfig {
            grid_dim: (plan.blocks, 1, 1),
            block_dim: (plan.threads_per_block, 1, 1),
            shared_mem_bytes: 0,
        };

        let mut table: HashMap<u64, (u64, u64)> = HashMap::with_capacity(plan.table_hint());
        let mut total_ops = setup_ops;
        let mut launches = 0u64;
        let mut dps_total = 0u64;
        let mut restarts = 0u64;
        let step_ops = plan.nwalks * u64::from(plan.steps);

        loop {
            if restart_dirty {
                stream.memcpy_htod(&h_restart, &mut d_restart)?;
                h_restart.fill(0);
                restart_dirty = false;
            }
            stream.memset_zeros(&mut d_count)?;

            {
                // Device pointers are stable for the lifetime of the
                // allocations, but they are re-read through the documented
                // accessors so that cudarc can insert any stream
                // synchronisation it deems necessary.
                let (a_mult, _g0) = d_mult.device_ptr(stream);
                let (a_state, _g1) = d_state.device_ptr_mut(stream);
                let (a_aux, _g2) = d_aux.device_ptr_mut(stream);
                let (a_dp, _g3) = d_dp.device_ptr_mut(stream);
                let (a_count, _g4) = d_count.device_ptr_mut(stream);
                let (a_restart, _g5) = d_restart.device_ptr_mut(stream);
                args.mult = a_mult;
                args.state = a_state;
                args.aux = a_aux;
                args.dp_out = a_dp;
                args.dp_count = a_count;
                args.restart = a_restart;

                let mut builder = stream.launch_builder(&self.func);
                builder.arg(&args);
                // SAFETY: `args` is the ABI-compatible mirror of
                // `ca_gpu_rho_args` (see src/args.rs) and every pointer in it
                // addresses a live allocation of at least the size the kernel
                // derives from `nthreads`, `r` and `dp_cap`.
                let _ = unsafe { builder.launch(cfg) }?;
            }

            launches += 1;
            total_ops += step_ops;

            // The copies below are enqueued on the stream, so synchronise
            // before touching the host buffers.
            let counts = stream.memcpy_dtov(&d_count)?;
            stream.synchronize()?;
            let mut count = counts[0];
            if count > plan.dp_cap {
                count = plan.dp_cap; // the kernel clamps its writes
            }
            let words = count as usize * 4;
            if words > 0 {
                let view = d_dp.slice(0..words);
                stream.memcpy_dtoh(&view, &mut h_dp[..words])?;
                stream.synchronize()?;
            }
            dps_total += u64::from(count);

            for rec in h_dp[..words].chunks_exact(4) {
                let (h, da, db, wid) = (rec[0], rec[1], rec[2], rec[3] as u32);
                match table.entry(h) {
                    std::collections::hash_map::Entry::Vacant(slot) => {
                        slot.insert((da, db));
                    }
                    std::collections::hash_map::Entry::Occupied(slot) => {
                        let (oa, ob) = *slot.get();
                        if (oa, ob) != (da, db) {
                            if let Some(x) =
                                try_solve(group, &base, &target, negmap, oa, ob, da, db)?
                            {
                                return Ok((
                                    x,
                                    Stats {
                                        group_ops: total_ops,
                                        launches,
                                        dps: dps_total,
                                        restarts,
                                        seconds: started.elapsed().as_secs_f64(),
                                        threads: plan.nthreads,
                                    },
                                ));
                            }
                        }
                        // Either the walk re-arrived with the same exponents
                        // (it cycled onto its own trail) or the relation was
                        // useless; either way, re-seed the walk.
                        if (wid as usize) < nwalks {
                            h_restart[wid as usize] = 1;
                            restart_dirty = true;
                        }
                        restarts += 1;
                    }
                }
            }

            if params.max_ops != 0 && total_ops > params.max_ops {
                return Err(Error::Limit { ops: total_ops });
            }
        }
    }
}

/// Convenience wrapper: open the device, load the kernel and solve once.
///
/// Prefer [`CudaRho`] when solving several instances, so that the context and
/// the module are reused.  Requests that `ca_gpu_rho_solve` also settles
/// without touching a device (an unknown group order, an identity target, a
/// group too small to be worth a launch) are answered here, so they behave
/// the same with and without a GPU.
pub fn solve(group: &Group, base: Elem, target: Elem, params: &Params) -> Result<(u64, Stats)> {
    let started = Instant::now();
    if let Some(done) = preflight(group, &base, &target, started) {
        return done;
    }
    CudaRho::new(params)?.solve(group, base, target, params)
}

/// The checks `ca_gpu_rho_solve` makes before it selects a backend.  `Some`
/// means the request is already settled and no device is needed.
fn preflight(
    group: &Group,
    base: &Elem,
    target: &Elem,
    started: Instant,
) -> Option<Result<(u64, Stats)>> {
    let n = group.order();
    if n == 0 {
        return Some(Err(Error::Invalid(
            "GPU rho requires a known group order".into(),
        )));
    }
    if group.is_identity(target) {
        return Some(Ok((0, Stats::elapsed(started))));
    }
    if n < 4096 {
        // Not worth a kernel launch.
        return Some(brute_force(group, base, target, n, started));
    }
    None
}

/// The internal (Montgomery) words the kernel expects for an element:
/// `(x, y)` with the point at infinity encoded as `x == p`.
fn internal_words(mont: &Mont, kind: u32, e: &Elem) -> (u64, u64) {
    if kind == KIND_ZP {
        (mont.to(e.residue()), 0)
    } else if e.is_infinity() {
        (mont.p, 0)
    } else {
        (mont.to(e.x()), mont.to(e.y()))
    }
}

/// Exhaustive search for the groups that are too small to bother the GPU with
/// (mirrors the `n < 4096` branch of `ca_gpu_rho_solve`).
fn brute_force(
    group: &Group,
    base: &Elem,
    target: &Elem,
    n: u64,
    started: Instant,
) -> Result<(u64, Stats)> {
    let mut cur = group.identity();
    for k in 0..n {
        if group.equal(&cur, target) {
            return Ok((
                k,
                Stats {
                    group_ops: k,
                    ..Stats::elapsed(started)
                },
            ));
        }
        cur = group.op(&cur, base)?;
    }
    Err(Error::NotFound)
}

/// Turn one collision into a logarithm; a port of `gpu_try_solve`.
///
/// Two walks met at the same canonical point with exponent pairs `(a1, b1)`
/// and `(a2, b2)`, so `a1 + b1*x == a2 + b2*x (mod n)`.  With the negation map
/// the second point may be the *negative* of the first, which gives the second
/// sign case.  `c` and `n` need not be coprime, so the linear congruence is
/// solved over `n / gcd(c, n)` and the `gcd` candidate lifts are tried in
/// turn; every candidate is verified against the group before it is accepted.
#[allow(clippy::too_many_arguments)]
fn try_solve(
    group: &Group,
    base: &Elem,
    target: &Elem,
    negmap: bool,
    a1: u64,
    b1: u64,
    a2: u64,
    b2: u64,
) -> Result<Option<u64>> {
    let n = group.order();
    let signs = if negmap { 2 } else { 1 };
    for sign in 0..signs {
        let (c, d) = if sign == 0 {
            (arith::submod(b1, b2, n), arith::submod(a2, a1, n))
        } else {
            let c = arith::addmod(b1, b2, n);
            let mut d = n - arith::addmod(a1, a2, n);
            if d == n {
                d = 0;
            }
            (c, d)
        };
        if c == 0 {
            continue;
        }
        let g = arith::gcd(c, n);
        if d % g != 0 {
            continue;
        }
        let nn = n / g;
        let x0 = arith::mulmod((d / g) % nn, cryptanalysis::invmod((c / g) % nn, nn), nn);
        for k in 0..g.min(65536) {
            let cand = x0 as u128 + k as u128 * nn as u128;
            if cand >= n as u128 {
                break;
            }
            let cand = cand as u64;
            if group.equal(&group.mul(base, cand)?, target) {
                return Ok(Some(cand));
            }
        }
    }
    Ok(None)
}

/// Compile-time reminder that the walk count is dictated by the kernel.
const _: () = assert!(WALKS_PER_THREAD > 0);

#[cfg(test)]
mod tests {
    use super::*;

    fn zp() -> (Group, Elem) {
        let g = Group::zp(2_000_000_579, 1_000_000_289).expect("safe prime fixture");
        let gen = g.find_generator(1).expect("generator");
        (g, gen)
    }

    /// The straightforward collision: two walks meet with different exponents
    /// and `c` is invertible mod `n`.
    #[test]
    fn collision_solves_prime_order_group() {
        let (g, base) = zp();
        let n = g.order();
        for x in [1u64, 2, 123_456_789, n - 1] {
            let target = g.mul(&base, x).unwrap();
            // a1 + b1*x == a2 + b2*x (mod n) with a2 = 0
            let (b1, b2) = (11u64, 4u64);
            let a1 = arith::mulmod(arith::submod(b2, b1, n), x, n);
            let got = try_solve(&g, &base, &target, false, a1, b1, 0, b2).unwrap();
            assert_eq!(got, Some(x), "x={x}");
        }
    }

    /// The negation-map sign case: the two walks met at `P` and `-P`, so
    /// `a1 + b1*x == -(a2 + b2*x)`.  Exercised over `Z_p^*` (where the
    /// arithmetic of the solver is identical) with `negmap` forced on.
    #[test]
    fn collision_solves_negated_case() {
        let (g, base) = zp();
        let n = g.order();
        let x = 424_242u64;
        let target = g.mul(&base, x).unwrap();
        let (b1, b2) = (7u64, 9u64);
        // a1 + a2 == -(b1 + b2)*x  (mod n), with a2 = 0
        let a1 = n - arith::mulmod(arith::addmod(b1, b2, n), x, n) % n;
        let a1 = if a1 == n { 0 } else { a1 };
        // sign 0 cannot work here, so this only succeeds via the second case
        assert_eq!(
            try_solve(&g, &base, &target, false, a1, b1, 0, b2).unwrap(),
            None
        );
        assert_eq!(
            try_solve(&g, &base, &target, true, a1, b1, 0, b2).unwrap(),
            Some(x)
        );
    }

    /// A composite order (`tests/test_gpu.c` uses `Z_1000003^*` with the full
    /// order `p - 1`), where `gcd(c, n) > 1` forces the lifting branch.
    #[test]
    fn collision_solves_through_the_gcd_branch() {
        let g = Group::zp(1_000_003, 0).expect("Z_p^* with full order");
        let n = g.order();
        assert_eq!(n, 1_000_002);
        assert_eq!(n % 2, 0);
        let base = Elem::zp(2);
        let x = 500_001u64; // 2 | gcd(c, n) cases need the lift loop
        let target = g.mul(&base, x).unwrap();
        // c = b1 - b2 shares the factor 2 with n
        let (b1, b2) = (10u64, 4u64);
        let c = arith::submod(b1, b2, n);
        assert!(arith::gcd(c, n) > 1);
        let a1 = arith::mulmod(arith::submod(b2, b1, n), x, n);
        let got = try_solve(&g, &base, &target, false, a1, b1, 0, b2).unwrap();
        // The verified answer need not be `x` itself: `base` generates a
        // proper subgroup, so any congruent exponent is correct.
        let got = got.expect("a candidate must verify");
        assert!(g.equal(&g.mul(&base, got).unwrap(), &target));
    }

    /// A useless relation (same exponents on both sides) must not produce an
    /// answer; the driver re-seeds the walk instead.
    #[test]
    fn useless_collision_yields_none() {
        let (g, base) = zp();
        let target = g.mul(&base, 99).unwrap();
        assert_eq!(
            try_solve(&g, &base, &target, false, 5, 5, 5, 5).unwrap(),
            None
        );
        assert_eq!(
            try_solve(&g, &base, &target, true, 5, 5, 5, 5).unwrap(),
            None
        );
    }

    #[test]
    fn internal_words_encode_infinity_as_p() {
        let mont = Mont::new(1_000_003).unwrap();
        assert_eq!(
            internal_words(&mont, KIND_EC, &Elem::ec_infinity()),
            (1_000_003, 0)
        );
        assert_eq!(
            internal_words(&mont, KIND_ZP, &Elem::zp(5)),
            (mont.to(5), 0)
        );
        let (x, y) = internal_words(&mont, KIND_EC, &Elem::ec(7, 9));
        assert_eq!((x, y), (mont.to(7), mont.to(9)));
    }
}
