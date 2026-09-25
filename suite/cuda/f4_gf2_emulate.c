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

int f4_gf2_emulate_batch(const f4_u64 *terms, const f4_u32 *poly_start,
                         const f4_u32 *sys_poly_start, const f4_u32 *sys_meta,
                         f4_u32 n_systems, f4_u32 max_rows, f4_u32 max_cols, f4_u32 threads,
                         f4_u64 scratch_words, F4Result *results)
{
    if (threads == 0u || threads > F4_MAX_THREADS)
        return -1;
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
        f4_decide_system(sh, nt, terms, poly_start, sys_poly_start, sys_meta, sys, max_rows,
                         max_cols, scratch, scratch_words, &results[sys]);
    free(scratch);
    free(sh);
    return 0;
}

/* sizeof(F4Result) and sizeof(F4Shared), so the Rust side can check the
 * layout it mirrors and size a launch. */
unsigned long long f4_gf2_result_size(void) { return sizeof(F4Result); }
unsigned long long f4_gf2_shared_size(void) { return sizeof(F4Shared); }
