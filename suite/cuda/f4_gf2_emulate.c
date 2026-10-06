/*
 * f4_gf2_emulate.c - run the CUDA kernel's source on the host.
 *
 * f4_gf2_device.cuh is written so that every block-level phase is a loop
 * over thread indices when compiled as C, which makes this the device
 * kernel, not a model of it: one emulated block of `threads` threads
 * decides the systems one after another.  The suite links it with the
 * `gpu` feature and holds its decisions to `f4_gf2::decide` in its tests.
 */
#include <stdlib.h>

#include "f4_gf2_device.cuh"
#include "f4_gf2_echelon.cuh"

int f4_gf2_emulate_batch(const f4_u64 *terms, const f4_u32 *poly_start,
                         const f4_u32 *sys_poly_start, const f4_u32 *sys_meta,
                         const f4_u32 *skip_bits, const f4_u32 *skip_start, f4_u32 n_systems,
                         f4_u32 max_rows, f4_u32 max_cols, f4_u32 threads, f4_u64 scratch_words,
                         F4Result *results)
{
    if (threads == 0u || threads > F4_MAX_THREADS) return -1;
    F4Shared *sh = (F4Shared *)calloc(1, sizeof(F4Shared));
    f4_u64 *scratch = (f4_u64 *)calloc(scratch_words ? scratch_words : 1u, sizeof(f4_u64));
    if (sh == NULL || scratch == NULL) {
        free(sh);
        free(scratch);
        return -2;
    }
    const f4_u32 nt = threads;
    f4_block_init(sh, nt);
    for (f4_u32 sys = 0; sys < n_systems; ++sys)
        f4_decide_system(sh, nt, terms, poly_start, sys_poly_start, sys_meta, skip_bits, skip_start,
                         sys, max_rows, max_cols, scratch, scratch_words, &results[sys]);
    free(scratch);
    free(sh);
    return 0;
}

/* The large-matrix elimination of f4_gf2_echelon.cuh, panel by panel as
 * the CUDA driver launches it: single-block steps with `threads` emulated
 * threads, grid steps as one emulated warp.  `mat` is eliminated in place;
 * `low` receives up to `rows` (lo, hi) pairs. */
int f4_gf2_emulate_echelon(f4_u64 *mat, f4_u32 rows, f4_u64 stride, f4_u32 low_start, f4_u32 width,
                           f4_u32 *active, f4_u32 threads, f4_u64 *low, f4_u32 *n_low,
                           f4_u32 *pivots, f4_u64 *ops)
{
    if (threads == 0u || threads > F4_MAX_THREADS || width > 128u) return -1;
    const f4_u32 hw = (low_start + 63u) / 64u;
    const f4_u64 n = rows ? rows : 1u;
    f4_u32 *cand = (f4_u32 *)calloc(n, sizeof(f4_u32));
    f4_u64 *pw = (f4_u64 *)calloc(n, sizeof(f4_u64));
    f4_u64 *coeff = (f4_u64 *)calloc(n, sizeof(f4_u64));
    f4_u32 *is_piv = (f4_u32 *)calloc(n, sizeof(f4_u32));
    f4_u32 *counts = (f4_u32 *)calloc(hw ? hw : 1u, sizeof(f4_u32));
    F4ePivots *piv = (F4ePivots *)calloc(1, sizeof(F4ePivots));
    F4ePanelShared *sh = (F4ePanelShared *)calloc(1, sizeof(F4ePanelShared));
    int rc = 0;
    if (!cand || !pw || !coeff || !is_piv || !counts || !piv || !sh) {
        rc = -2;
        goto done;
    }
    *n_low = 0u;
    *ops = 0ull;
    for (f4_u32 w = 0; w < hw; ++w) {
        const f4_u32 high = low_start - 64u * w;
        const f4_u64 mask = high >= 64u ? ~0ull : ((1ull << high) - 1ull);
        f4e_gather_thread(0u, 1u, mat, stride, w, mask, active, rows, cand, pw, counts + w);
        f4e_panel(sh, threads, cand, pw, coeff, is_piv, counts + w, piv, ops);
        f4e_materialise(threads, mat, stride, w, active, piv, ops);
        for (f4_u64 gid = 0; gid < 32u; ++gid)
            f4e_update_thread(gid, 32u, mat, stride, w, cand, coeff, is_piv, counts + w, piv, ops);
    }
    f4e_low_thread(0u, 1u, mat, stride, low_start, width, active, rows, low, n_low);
    *pivots = piv->total;
done:
    free(cand);
    free(pw);
    free(coeff);
    free(is_piv);
    free(counts);
    free(piv);
    free(sh);
    return rc;
}

/* sizeof(F4Result) and sizeof(F4Shared), so the Rust side can check the
 * layout it mirrors and size a launch. */
unsigned long long f4_gf2_result_size(void) { return sizeof(F4Result); }
unsigned long long f4_gf2_shared_size(void) { return sizeof(F4Shared); }
