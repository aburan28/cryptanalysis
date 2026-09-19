//! Run parameters and the auto-tuning that turns them into a launch plan.

use crate::arith::{ilog2u, isqrt};
use crate::WALKS_PER_THREAD;

/// Knobs for one `solve` run, mirroring `ca_gpu_rho_params` from
/// `include/cryptanalysis/ca_gpu.h`.
///
/// `Default` matches `ca_gpu_rho_params_default`: everything auto, the
/// negation map on, device 0.
///
/// ```
/// use cryptanalysis_cuda::Params;
/// let p = Params::default();
/// assert_eq!(p.device, 0);
/// assert_eq!(p.dp_bits, -1);
/// assert!(p.negation_map);
/// ```
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Params {
    /// CUDA device ordinal.
    pub device: usize,
    /// Threads per block (0 => 128).
    pub threads_per_block: u32,
    /// Blocks per launch (0 => auto from the group size).
    pub blocks: u32,
    /// Walk steps each thread takes per launch (0 => auto).
    pub steps_per_launch: u32,
    /// Number of adding-walk multipliers (0 => auto).
    pub r: u32,
    /// Distinguished-point bits, i.e. `log2` of the DP density (-1 => auto).
    pub dp_bits: i32,
    /// Use the negation map (curves only; ignored for `Z_p^*`).
    pub negation_map: bool,
    /// RNG seed for the multipliers and walk starts (0 => from the OS).
    pub seed: u64,
    /// Work limit in group operations; exceeding it yields
    /// [`Error::Limit`](crate::Error::Limit).  0 => unlimited.
    pub max_ops: u64,
}

impl Default for Params {
    fn default() -> Params {
        Params {
            device: 0,
            threads_per_block: 0,
            blocks: 0,
            steps_per_launch: 0,
            r: 0,
            dp_bits: -1,
            negation_map: true,
            seed: 0,
            max_ops: 0,
        }
    }
}

/// The speed-up the negation map gives, as the C driver writes it.  It is the
/// literal `1.4142` rather than `SQRT_2`, and it is kept exactly so that the
/// two implementations pick identical parameters.
#[allow(clippy::approx_constant)]
const NEGMAP_SPEEDUP: f64 = 1.4142;

/// The concrete launch geometry and DP protocol derived from [`Params`].
///
/// This is a direct port of the parameter-selection block of
/// `ca_gpu_rho_solve` (`src/gpu_rho.c`), kept as a pure function so that it
/// can be unit tested without a device.
#[derive(Debug, Clone, Copy, PartialEq)]
pub(crate) struct Plan {
    /// Multiplier count.
    pub r: u32,
    /// Threads per block actually used.
    pub threads_per_block: u32,
    /// Blocks per launch.
    pub blocks: u32,
    /// Live threads (threads beyond this exit immediately).
    pub nthreads: u32,
    /// `nthreads * CA_GPU_W`.
    pub nwalks: u64,
    /// Chosen distinguished-point bits.
    pub dp_bits: u32,
    /// `2^dp_bits - 1`, or 0 when `dp_bits == 0`.
    pub dp_mask: u64,
    /// Steps per thread per launch.
    pub steps: u32,
    /// Capacity of the device DP buffer, in records.
    pub dp_cap: u32,
    /// `abandon_shift`: a walk is re-seeded after `24 << abandon_shift` steps
    /// without producing a distinguished point.
    pub abandon_shift: u32,
    /// Expected total walk steps for the whole run (used to size the table).
    pub expected: f64,
}

impl Plan {
    /// Auto-tune for a group of order `n`.
    ///
    /// `negmap` is the *effective* negation-map flag (already ANDed with "the
    /// group is a curve"); `on_gpu` selects the larger thread budget the C
    /// driver uses for a real device rather than the emulator.
    pub fn new(n: u64, negmap: bool, p: &Params, on_gpu: bool) -> Plan {
        let sqrt_n = isqrt(n) + 1;
        let lg = ilog2u(n) + 1;

        // Multiplier count: large tables keep fruitless cycles rare, but stay
        // below sqrt(n)/64 so the host-side table build stays cheap.
        let mut r = if p.r != 0 {
            p.r
        } else {
            let budget = sqrt_n / 64;
            let cap: u64 = if negmap { 1024 } else { 64 };
            let mut r: u64 = 8;
            while r * 2 <= budget && r * 2 <= cap {
                r *= 2;
            }
            r as u32
        };
        if r < 4 {
            r = 4;
        }

        // Thread count: each walk start costs ~3*log2(n) operations, so keep
        // the total start-up work below sqrt(n)/8.
        let tpb = if p.threads_per_block != 0 {
            p.threads_per_block
        } else {
            128
        };
        let w = u64::from(WALKS_PER_THREAD);
        let (nthreads, blocks) = if p.blocks == 0 {
            let walks_cap = sqrt_n / (24 * lg as u64);
            let threads_cap = (walks_cap / w).max(1);
            let want = u64::from(tpb) * if on_gpu { 1024 } else { 4 };
            let nthreads = want.min(threads_cap);
            let blocks = nthreads.div_ceil(u64::from(tpb));
            (nthreads, blocks as u32)
        } else {
            (u64::from(p.blocks) * u64::from(tpb), p.blocks)
        };
        let nwalks = nthreads * w;

        // Distinguished points: ~32 per walk over the expected run.
        let expected = 1.25 * sqrt_n as f64 / if negmap { NEGMAP_SPEEDUP } else { 1.0 };
        let dp_bits = if p.dp_bits >= 0 {
            p.dp_bits.min(63) as u32
        } else {
            let per_walk = expected / (32.0 * nwalks as f64);
            let mut dp = if per_walk >= 2.0 {
                ilog2u(per_walk as u64)
            } else {
                0
            };
            let min_dp = ilog2u(expected as u64) - 24;
            if dp < min_dp {
                dp = min_dp;
            }
            dp.clamp(0, 48) as u32
        };
        let dp_mask = if dp_bits != 0 {
            (1u64 << dp_bits) - 1
        } else {
            0
        };

        // Aim at about 1/16 of the expected work per launch, but run at least
        // long enough that the herd is likely to report a distinguished point
        // (one per 2^dp steps, spread over nwalks walks).  A launch is not
        // interruptible and max_ops is only checked between launches, so it is
        // capped at the whole expected run, and at the work limit when one is
        // set; without that an unusual dp_bits makes a single launch dwarf the
        // entire search.
        let steps = if p.steps_per_launch != 0 {
            p.steps_per_launch
        } else {
            let mut per = expected / (16.0 * nwalks as f64);
            let dp_floor = (1u64 << dp_bits.min(40)) as f64 / nwalks as f64;
            per = per.max(dp_floor).max(64.0);
            let whole_run = expected / nwalks as f64 + 64.0;
            per = per.min(whole_run);
            if p.max_ops != 0 {
                per = per.min(p.max_ops as f64 / nwalks as f64 + 1.0);
            }
            per.clamp(1.0, 1e7) as u32
        };

        // DP buffer for one launch: twice the expected count plus slack, hard
        // capped.  Overflow is safe: the kernel drops records past dp_cap and
        // the host clamps the count, so it costs work, never correctness.
        let exp_dps = nwalks as f64 * steps as f64 / (1u64 << dp_bits) as f64;
        let dp_cap = ((exp_dps * 2.0) as u64 + 4096).min(1 << 20) as u32;

        Plan {
            r,
            threads_per_block: tpb,
            blocks,
            nthreads: nthreads as u32,
            nwalks,
            dp_bits,
            dp_mask,
            steps,
            dp_cap,
            abandon_shift: dp_bits,
            expected,
        }
    }

    /// A reasonable initial capacity for the host distinguished-point table,
    /// matching the C driver's `ca_htab_init` sizing.
    pub fn table_hint(&self) -> usize {
        (self.expected / (1u64 << self.dp_bits) as f64) as usize + 4096
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// `tests/test_gpu.c` runs `fx_zp_safe(2000000579)`, whose subgroup order
    /// is 1000000289.  These numbers are the C selection worked through by
    /// hand: sqrt_n = isqrt(n)+1 = 31623, lg = 30, budget = 31623/64 = 494,
    /// walks_cap = 31623/720 = 43, threads_cap = 43/8 = 5.
    #[test]
    fn auto_plan_for_31_bit_zp() {
        let n = 1_000_000_289u64;
        let plan = Plan::new(n, false, &Params::default(), true);
        assert_eq!(plan.r, 64, "cap 64 without the negation map");
        assert_eq!(plan.threads_per_block, 128);
        assert_eq!(plan.nthreads, 5);
        assert_eq!(plan.blocks, 1);
        assert_eq!(plan.nwalks, 40);
        // expected = 1.25*31623 = 39528.75; per walk over 32 DPs => 30.88
        assert_eq!(plan.dp_bits, 4);
        assert_eq!(plan.dp_mask, 15);
        assert_eq!(plan.abandon_shift, 4);
        // 39528.75/(16*40) = 61.8 < 64 => the 64-step floor wins
        assert_eq!(plan.steps, 64);
        // exp_dps = 40*64/16 = 160 => 2*160 + 4096
        assert_eq!(plan.dp_cap, 4416);
    }

    /// Same group with the negation map on: only `r` and `expected` change
    /// (the walk count does not depend on the negation map).
    #[test]
    fn auto_plan_with_negation_map() {
        let plan = Plan::new(1_000_000_289, true, &Params::default(), true);
        assert_eq!(plan.r, 256, "cap 1024, budget 494");
        assert_eq!(plan.nwalks, 40);
        assert_eq!(plan.dp_bits, 4);
        assert_eq!(plan.steps, 64);
        assert!((plan.expected - 1.25 * 31623.0 / NEGMAP_SPEEDUP).abs() < 1e-6);
    }

    /// The emulator budget is 4*tpb rather than 1024*tpb; for this small group
    /// the walk cap dominates either way, so a big group shows the difference.
    #[test]
    fn thread_budget_depends_on_backend() {
        let n = u64::MAX / 4; // sqrt(n) ~ 2^31, so the cap is not binding
        let gpu = Plan::new(n, false, &Params::default(), true);
        let emu = Plan::new(n, false, &Params::default(), false);
        assert_eq!(gpu.nthreads, 128 * 1024);
        assert_eq!(emu.nthreads, 128 * 4);
    }

    /// The explicit small configuration from `tests/test_gpu.c`:
    /// 1 block of 4 threads, 2 dp bits, 16 steps.
    #[test]
    fn explicit_small_configuration() {
        let params = Params {
            blocks: 1,
            threads_per_block: 4,
            dp_bits: 2,
            steps_per_launch: 16,
            seed: 9,
            ..Params::default()
        };
        let plan = Plan::new(1_000_000_289, false, &params, true);
        assert_eq!(plan.nthreads, 4);
        assert_eq!(plan.nwalks, 32);
        assert_eq!(plan.dp_bits, 2);
        assert_eq!(plan.dp_mask, 3);
        assert_eq!(plan.steps, 16);
        // exp_dps = 32*16/4 = 128 => 2*128 + 4096
        assert_eq!(plan.dp_cap, 4352);
        assert_eq!(plan.r, 64);
    }

    #[test]
    fn r_is_never_below_four_and_dp_is_clamped() {
        let params = Params {
            r: 1,
            dp_bits: 99,
            ..Params::default()
        };
        let plan = Plan::new(1_000_000_289, false, &params, false);
        assert_eq!(plan.r, 4);
        assert_eq!(plan.dp_bits, 63);
        // A launch never exceeds the whole expected run, so an absurd dp_bits
        // no longer forces an enormous one (see matches_c_driver below).
        assert_eq!(plan.steps, 1052);
    }

    /// One row of [`matches_c_driver`]: the inputs, then what the C driver
    /// chose for them.
    struct Row {
        dp_bits_in: i32,
        r_in: u32,
        blocks_in: u32,
        tpb_in: u32,
        nthreads: u32,
        dp_bits: u32,
        steps: u32,
        dp_cap: u32,
    }

    /// The C driver is the reference: this crate promises to pick the same
    /// launch geometry, and nothing in Rust can check that by itself.  Every
    /// row below was read out of `ca_gpu_rho_solve` for the same inputs, so a
    /// change on either side that is not mirrored in the other fails here.
    ///
    /// Group of order 1000000289, negation map off, no work limit, and the
    /// emulator's `on_gpu = false` (at this size the thread cap binds either
    /// way, so the choice does not affect the result).
    #[test]
    fn matches_c_driver() {
        const ROWS: &[Row] = &[
            // An absurd dp_bits is clamped, and the launch is bounded by the
            // whole expected run rather than 2^20 steps per walk.
            Row {
                dp_bits_in: 99,
                r_in: 1,
                blocks_in: 0,
                tpb_in: 0,
                nthreads: 5,
                dp_bits: 63,
                steps: 1052,
                dp_cap: 4096,
            },
            // The ordinary automatic choice.
            Row {
                dp_bits_in: -1,
                r_in: 0,
                blocks_in: 0,
                tpb_in: 0,
                nthreads: 5,
                dp_bits: 4,
                steps: 64,
                dp_cap: 4416,
            },
            Row {
                dp_bits_in: 30,
                r_in: 0,
                blocks_in: 0,
                tpb_in: 0,
                nthreads: 5,
                dp_bits: 30,
                steps: 1052,
                dp_cap: 4096,
            },
            Row {
                dp_bits_in: 63,
                r_in: 0,
                blocks_in: 0,
                tpb_in: 0,
                nthreads: 5,
                dp_bits: 63,
                steps: 1052,
                dp_cap: 4096,
            },
            Row {
                dp_bits_in: 20,
                r_in: 0,
                blocks_in: 0,
                tpb_in: 0,
                nthreads: 5,
                dp_bits: 20,
                steps: 1052,
                dp_cap: 4096,
            },
            // Every point distinguished: the DP buffer is sized up instead.
            Row {
                dp_bits_in: 0,
                r_in: 0,
                blocks_in: 0,
                tpb_in: 0,
                nthreads: 5,
                dp_bits: 0,
                steps: 64,
                dp_cap: 9216,
            },
            // An explicit 1 block of 4 threads.
            Row {
                dp_bits_in: -1,
                r_in: 4,
                blocks_in: 1,
                tpb_in: 4,
                nthreads: 4,
                dp_bits: 5,
                steps: 77,
                dp_cap: 4250,
            },
        ];
        for row in ROWS {
            let params = Params {
                dp_bits: row.dp_bits_in,
                r: row.r_in,
                blocks: row.blocks_in,
                threads_per_block: row.tpb_in,
                negation_map: false,
                ..Params::default()
            };
            let plan = Plan::new(1_000_000_289, false, &params, false);
            let got = (plan.nthreads, plan.dp_bits, plan.steps, plan.dp_cap);
            let want = (row.nthreads, row.dp_bits, row.steps, row.dp_cap);
            assert_eq!(got, want, "dp_bits in = {}", row.dp_bits_in);
        }
    }

    #[test]
    fn tiny_groups_get_at_least_one_thread() {
        let plan = Plan::new(4099, false, &Params::default(), true);
        assert_eq!(plan.nthreads, 1);
        assert_eq!(plan.blocks, 1);
        assert_eq!(plan.dp_bits, 0);
        assert_eq!(plan.dp_mask, 0);
    }
}
