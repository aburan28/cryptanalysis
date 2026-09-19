//! The kernel's by-value argument struct.

use cudarc::driver::DeviceRepr;

/// `kind` value for a subgroup of `Z_p^*` (`CA_GPU_KIND_ZP`).
pub(crate) const KIND_ZP: u32 = 1;
/// `kind` value for an elliptic curve over `F_p` (`CA_GPU_KIND_EC`).
pub(crate) const KIND_EC: u32 = 2;

/// Rust mirror of `struct ca_gpu_rho_args` from `cuda/ca_device.cuh`.
///
/// This is the crate's ABI contract with the kernel: the field order, the
/// `uint32_t` block and the trailing `pad` word must match the C declaration
/// exactly, because `ca_rho_walk_kernel` takes the struct **by value** as its
/// only parameter.  The device pointers are `u64` here because that is what
/// `CUdeviceptr` is and what a 64-bit device pointer occupies.
///
/// ```text
/// offset  field                         C type
///      0  p                             uint64_t
///      8  pinv                          uint64_t   (-p^-1 mod 2^64)
///     16  one                           uint64_t   (R mod p)
///     24  a_mont                        uint64_t   (curve a, Montgomery form)
///     32  n                             uint64_t   (subgroup order)
///     40  dp_mask                       uint64_t
///     48  seed                          uint64_t
///     56  base_x    64  base_y          uint64_t
///     72  target_x  80  target_y        uint64_t
///     88  kind      92  negmap          uint32_t
///     96  r        100  steps           uint32_t
///    104  nthreads 108  dp_cap          uint32_t
///    112  abandon_shift                 uint32_t
///    116  pad                           uint32_t
///    120  mult                          const uint64_t *
///    128  state    136  aux             uint64_t *
///    144  dp_out                        uint64_t *
///    152  dp_count                      uint32_t *
///    160  restart                       uint8_t *
///    168  (total size, alignment 8)
/// ```
#[repr(C)]
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub(crate) struct GpuRhoArgs {
    pub p: u64,
    pub pinv: u64,
    pub one: u64,
    pub a_mont: u64,
    pub n: u64,
    pub dp_mask: u64,
    pub seed: u64,
    pub base_x: u64,
    pub base_y: u64,
    pub target_x: u64,
    pub target_y: u64,
    pub kind: u32,
    pub negmap: u32,
    pub r: u32,
    pub steps: u32,
    pub nthreads: u32,
    pub dp_cap: u32,
    pub abandon_shift: u32,
    pub pad: u32,
    pub mult: u64,
    pub state: u64,
    pub aux: u64,
    pub dp_out: u64,
    pub dp_count: u64,
    pub restart: u64,
}

// SAFETY: `#[repr(C)]` with the exact field order and types of
// `ca_gpu_rho_args`; every field is a plain integer, so the struct is valid
// for any bit pattern and can be handed to the driver as a kernel parameter.
unsafe impl DeviceRepr for GpuRhoArgs {}

/// The byte size `cc -I cuda` reports for `ca_gpu_rho_args` on a 64-bit host.
pub(crate) const ARGS_SIZE: usize = 168;

const _: () = assert!(std::mem::size_of::<GpuRhoArgs>() == ARGS_SIZE);
const _: () = assert!(std::mem::align_of::<GpuRhoArgs>() == 8);

#[cfg(test)]
mod tests {
    use super::*;

    /// Offsets as printed by a C program that includes `cuda/ca_device.cuh`.
    #[test]
    fn layout_matches_c() {
        let a = GpuRhoArgs::default();
        let base = &a as *const _ as usize;
        let off = |p: *const u8| p as usize - base;
        macro_rules! check {
            ($field:ident, $want:expr) => {
                assert_eq!(
                    off(std::ptr::addr_of!(a.$field) as *const u8),
                    $want,
                    concat!("offset of ", stringify!($field))
                );
            };
        }
        check!(p, 0);
        check!(pinv, 8);
        check!(one, 16);
        check!(a_mont, 24);
        check!(n, 32);
        check!(dp_mask, 40);
        check!(seed, 48);
        check!(base_x, 56);
        check!(base_y, 64);
        check!(target_x, 72);
        check!(target_y, 80);
        check!(kind, 88);
        check!(negmap, 92);
        check!(r, 96);
        check!(steps, 100);
        check!(nthreads, 104);
        check!(dp_cap, 108);
        check!(abandon_shift, 112);
        check!(pad, 116);
        check!(mult, 120);
        check!(state, 128);
        check!(aux, 136);
        check!(dp_out, 144);
        check!(dp_count, 152);
        check!(restart, 160);
        assert_eq!(std::mem::size_of::<GpuRhoArgs>(), 168);
    }
}
