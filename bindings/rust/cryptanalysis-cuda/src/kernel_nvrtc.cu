/*
 * kernel_nvrtc.cu - NVRTC-friendly entry point for the shared rho kernel.
 *
 * cuda/rho_kernel.cu cannot be handed to NVRTC because it includes
 * <cuda_runtime.h> (for the <<<>>> launch shim, which NVRTC has no use for).
 * This file is the same __global__ body without that include: the host
 * concatenates the *embedded text* of cuda/ca_device.cuh in front of it at
 * run time (see src/kernel.rs), so the device code compiled by NVRTC is
 * byte-for-byte the code the C library's kernel uses.  The header itself is
 * never modified; the only adjustment is that the host supplies the
 * fixed-width integer typedefs NVRTC has no <stdint.h> for.
 *
 * The entry point is extern "C" so that the module can be looked up by the
 * plain name `ca_rho_walk_kernel_c` (the build-time PTX path instead uses the
 * C++-mangled `_Z18ca_rho_walk_kernel15ca_gpu_rho_args` produced from
 * cuda/rho_kernel.cu).
 */
extern "C" __global__ void ca_rho_walk_kernel_c(ca_gpu_rho_args args)
{
    ca_dev_rho_thread(&args, blockIdx.x * blockDim.x + threadIdx.x);
}
