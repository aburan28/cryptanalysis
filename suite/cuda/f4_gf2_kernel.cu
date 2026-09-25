/*
 * f4_gf2_kernel.cu - the CUDA entry point for batched Boolean Macaulay
 * decisions.  All of the algorithm is in f4_gf2_device.cuh; this file only
 * maps blocks to systems.
 *
 * Launch with any grid and a block of at most 1024 threads.  Block b
 * decides systems b, b + gridDim.x, ..., each in its own
 * `scratch_words`-word slice of `scratch`.  System s may carry an F5 row
 * mask in skip_bits[skip_start[s] .. skip_start[s + 1]] (see
 * `f4_gf2::f5_row_mask`); an empty range means no mask.  A system that needs more
 * scratch, a degree above 7 or more than 256 equations is returned with
 * status F4_STATUS_FALLBACK and decided on the host instead.
 *
 * The host driver (f4_gpu.rs) compiles this file with NVRTC at run time,
 * with the header prepended, so the #include below is for nvcc builds.
 */
#ifndef F4_GF2_DEVICE_CUH
#    include "f4_gf2_device.cuh"
#endif

extern "C" __global__ void f4_gf2_decide_batch(const f4_u64 *terms, const f4_u32 *poly_start,
                                               const f4_u32 *sys_poly_start, const f4_u32 *sys_meta,
                                               const f4_u32 *skip_bits, const f4_u32 *skip_start,
                                               f4_u32 n_systems, f4_u32 max_rows, f4_u32 max_cols,
                                               f4_u64 *scratch, f4_u64 scratch_words,
                                               F4Result *results)
{
    __shared__ F4Shared sh;
    const f4_u32 nt = blockDim.x;
    f4_block_init(&sh, nt);
    f4_u64 *mine = scratch + (f4_u64)blockIdx.x * scratch_words;
    for (f4_u32 sys = blockIdx.x; sys < n_systems; sys += gridDim.x)
        f4_decide_system(&sh, nt, terms, poly_start, sys_poly_start, sys_meta, skip_bits,
                         skip_start, sys, max_rows, max_cols, mine, scratch_words, &results[sys]);
}
