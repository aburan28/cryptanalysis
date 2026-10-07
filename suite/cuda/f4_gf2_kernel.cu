/*
 * f4_gf2_kernel.cu - the CUDA entry points for batched Boolean Macaulay
 * decisions and for the elimination of one large matrix.  All of the
 * algorithm is in f4_gf2_device.cuh and f4_gf2_echelon.cuh; this file only
 * maps blocks and threads onto them.
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
#ifndef F4_GF2_ECHELON_CUH
#    include "f4_gf2_echelon.cuh"
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

/* One large matrix (f4_gf2_echelon.cuh): per panel, f4e_gather on a grid,
 * f4e_panel_block on one block, then f4e_materialise and f4e_update on
 * grids, the latter's size a multiple of 32; f4e_low at the end. */
#define F4E_GID   ((f4_u64)blockIdx.x * blockDim.x + threadIdx.x)
#define F4E_TOTAL ((f4_u64)gridDim.x * blockDim.x)

extern "C" __global__ void f4e_gather(const f4_u64 *mat, f4_u64 stride, f4_u32 w, f4_u64 mask,
                                      const f4_u32 *active, f4_u32 rows, f4_u32 *cand, f4_u64 *pw,
                                      f4_u32 *count)
{
    f4e_gather_thread(F4E_GID, F4E_TOTAL, mat, stride, w, mask, active, rows, cand, pw, count);
}

extern "C" __global__ void f4e_panel_block(const f4_u32 *cand, f4_u64 *pw, f4_u64 *coeff,
                                           f4_u32 *is_piv, const f4_u32 *count, F4ePivots *piv)
{
    __shared__ F4ePanelShared sh;
    f4e_panel(&sh, blockDim.x, cand, pw, coeff, is_piv, count, piv);
}

extern "C" __global__ void f4e_materialise(f4_u64 *mat, f4_u64 stride, f4_u32 w, f4_u32 *active,
                                           const F4ePivots *piv, f4_u64 *ops)
{
    f4e_materialise_thread(F4E_GID, F4E_TOTAL, mat, stride, w, active, piv, ops);
}

extern "C" __global__ void f4e_update(f4_u64 *mat, f4_u64 stride, f4_u32 w, const f4_u32 *cand,
                                      const f4_u64 *coeff, const f4_u32 *is_piv,
                                      const f4_u32 *count, const F4ePivots *piv, f4_u64 *ops)
{
    f4e_update_thread(F4E_GID, F4E_TOTAL, mat, stride, w, cand, coeff, is_piv, count, piv, ops);
}

extern "C" __global__ void f4e_low(const f4_u64 *mat, f4_u64 stride, f4_u32 low_start, f4_u32 width,
                                   const f4_u32 *active, f4_u32 rows, f4_u64 *low, f4_u32 *n_low)
{
    f4e_low_thread(F4E_GID, F4E_TOTAL, mat, stride, low_start, width, active, rows, low, n_low);
}
