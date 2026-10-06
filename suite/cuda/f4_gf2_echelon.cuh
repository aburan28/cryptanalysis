/*
 * f4_gf2_echelon.cuh - forward elimination of one large Boolean Macaulay
 * matrix over its high columns, one 64-column panel at a time.
 *
 * The device half of `f4_gpu::CudaDecider::echelon`, and the same contract
 * as `f4_gf2`'s host `echelon`: every row either becomes the pivot of a
 * high column or is reduced to zero there, and what the reduced rows keep
 * of the linear block (at most 65 columns from `low_start`) is returned.
 * The pivot of a column is the lowest-numbered row leading there, so the
 * elimination and its word count are deterministic, but they are not the
 * host kernel's: only the row space, hence the rank, the refutation and
 * the pinned variables, is the same.
 *
 * Panel w (word w of every row) runs four steps:
 *   gather       rows still active with a high bit in word w;
 *   panel        one block: per column of the word, the lowest such row is
 *                the pivot and its word is XORed into the others, which
 *                record the pivots they took as a 64-bit mask;
 *   materialise  one block: each pivot row takes the earlier pivots its
 *                mask names, across the rest of the row, and leaves the
 *                active set;
 *   update       a warp per remaining row XORs the pivots its mask names
 *                into the rest of the row.
 * Rows without a high bit in word w are untouched by panel w.
 *
 * Written in the common subset of C11 and CUDA, after f4_gf2_device.cuh:
 * single-block steps are barrier-separated phases, and grid steps are
 * per-thread functions over a grid-stride loop, so f4_gf2_emulate.c runs
 * this very source on the host.
 */
#ifndef F4_GF2_ECHELON_CUH
#define F4_GF2_ECHELON_CUH

/* Pivots of the current panel, kept in device memory between steps. */
typedef struct {
    f4_u32 n;
    f4_u32 total; /* pivots of every panel so far */
    f4_u32 row[64];
    f4_u64 hist[64]; /* earlier pivots of the panel XORed into pivot k */
} F4ePivots;

/* Block-shared state of the panel step. */
typedef struct {
    f4_u64 cols;
    f4_u64 best[3];
    f4_u32 n_cand;
    f4_u32 n_piv;
} F4ePanelShared;

/* Gather: active rows with a high bit in word w, with that word. */
F4_FN void f4e_gather_thread(f4_u64 gid, f4_u64 total, const f4_u64 *mat, f4_u64 stride, f4_u32 w,
                             f4_u64 mask, const f4_u32 *active, f4_u32 rows, f4_u32 *cand,
                             f4_u64 *pw, f4_u32 *count)
{
    for (f4_u64 r = gid; r < rows; r += total) {
        if (!active[r]) continue;
        f4_u64 word = mat[r * stride + w] & mask;
        if (word == 0ull) continue;
        f4_u32 i = F4_ATOMIC_ADD32(count, 1u);
        cand[i] = (f4_u32)r;
        pw[i] = word;
    }
}

/* Panel: pivots of word w among the gathered rows, lowest row first per
 * column.  coeff[i] collects the pivot slots XORed into candidate i;
 * is_piv[i] marks the pivots. */
F4_BLOCK_FN void f4e_panel(F4ePanelShared *sh, f4_u32 nt, const f4_u32 *cand, f4_u64 *pw,
                           f4_u64 *coeff, f4_u32 *is_piv, const f4_u32 *count, F4ePivots *piv,
                           f4_u64 *ops)
{
    F4_SINGLE
    {
        sh->n_cand = *count;
        sh->n_piv = 0u;
        sh->cols = 0ull;
        sh->best[0] = ~0ull;
        sh->best[1] = ~0ull;
        sh->best[2] = ~0ull;
    }
    F4_SYNC();
    F4_FOR_THREADS(tid)
        f4_u64 acc = 0ull;
        for (f4_u32 i = tid; i < sh->n_cand; i += nt) {
            coeff[i] = 0ull;
            is_piv[i] = 0u;
            acc |= pw[i];
        }
        if (acc) F4_ATOMIC_OR64(&sh->cols, acc);
    F4_END_THREADS
    F4_SYNC();
    f4_u64 cols = sh->cols;
    f4_u32 round = 0u;
    while (cols != 0ull) {
        const f4_u32 c = F4_CTZ(cols);
        cols &= cols - 1ull;
        const f4_u32 slot = round % 3u;
        F4_FOR_THREADS(tid)
            if (tid == 0u) sh->best[(slot + 1u) % 3u] = ~0ull;
            f4_u64 mine = ~0ull;
            for (f4_u32 i = tid; i < sh->n_cand; i += nt) {
                if (!is_piv[i] && ((pw[i] >> c) & 1ull)) {
                    f4_u64 key = ((f4_u64)cand[i] << 32) | i;
                    mine = key < mine ? key : mine;
                }
            }
            if (mine != ~0ull) F4_ATOMIC_MIN64(&sh->best[slot], mine);
        F4_END_THREADS
        F4_SYNC();
        ++round;
        const f4_u64 best = sh->best[slot];
        if (best == ~0ull) continue;
        const f4_u32 p = (f4_u32)(best & 0xffffffffull);
        const f4_u32 k = sh->n_piv;
        F4_FOR_THREADS(tid)
            if (tid == 0u) {
                piv->row[k] = cand[p];
                piv->hist[k] = coeff[p];
                is_piv[p] = 1u;
            }
            for (f4_u32 i = tid; i < sh->n_cand; i += nt) {
                if (i == p || is_piv[i] || !((pw[i] >> c) & 1ull)) continue;
                pw[i] ^= pw[p];
                coeff[i] |= 1ull << k;
            }
        F4_END_THREADS
        F4_SYNC();
        F4_SINGLE { sh->n_piv = k + 1u; }
        F4_SYNC();
    }
    F4_SINGLE
    {
        piv->n = sh->n_piv;
        piv->total += sh->n_piv;
        (void)ops;
    }
    F4_SYNC();
}

/* Materialise: pivot k takes the earlier pivots its history names over
 * words w .. stride, in order, so each is final when a later one reads
 * it; then it leaves the active set. */
F4_BLOCK_FN void f4e_materialise(f4_u32 nt, f4_u64 *mat, f4_u64 stride, f4_u32 w, f4_u32 *active,
                                 const F4ePivots *piv, f4_u64 *ops)
{
    const f4_u32 n = piv->n;
    for (f4_u32 k = 0; k < n; ++k) {
        f4_u64 h = piv->hist[k];
        f4_u64 *dst = mat + (f4_u64)piv->row[k] * stride;
        while (h != 0ull) {
            const f4_u32 j = F4_CTZ(h);
            h &= h - 1ull;
            const f4_u64 *src = mat + (f4_u64)piv->row[j] * stride;
            F4_FOR_THREADS(tid)
                for (f4_u64 x = w + tid; x < stride; x += nt) dst[x] ^= src[x];
                if (tid == 0u) F4_ATOMIC_ADD64(ops, stride - w);
            F4_END_THREADS
            F4_SYNC();
        }
    }
    F4_FOR_THREADS(tid)
        for (f4_u32 k = tid; k < n; k += nt) active[piv->row[k]] = 0u;
    F4_END_THREADS
    F4_SYNC();
}

/* Update: a warp per remaining candidate XORs the pivots its mask names
 * into words w .. stride of its row.  Pivot rows are only read. */
F4_FN void f4e_update_thread(f4_u64 gid, f4_u64 total, f4_u64 *mat, f4_u64 stride, f4_u32 w,
                             const f4_u32 *cand, const f4_u64 *coeff, const f4_u32 *is_piv,
                             const f4_u32 *count, const F4ePivots *piv, f4_u64 *ops)
{
    const f4_u32 n = *count;
    const f4_u64 lane = gid & 31ull, warp = gid >> 5, warps = total >> 5;
    f4_u64 ops_here = 0ull;
    for (f4_u64 i = warp; i < n; i += warps) {
        if (is_piv[i]) continue;
        const f4_u64 m = coeff[i];
        f4_u64 *dst = mat + (f4_u64)cand[i] * stride;
        for (f4_u64 x = w + lane; x < stride; x += 32ull) {
            f4_u64 acc = 0ull, h = m;
            while (h != 0ull) {
                const f4_u32 j = F4_CTZ(h);
                h &= h - 1ull;
                acc ^= mat[(f4_u64)piv->row[j] * stride + x];
            }
            dst[x] ^= acc;
        }
        if (lane == 0ull) ops_here += (f4_u64)F4_POPC(m) * (stride - w);
    }
    if (ops_here) F4_ATOMIC_ADD64(ops, ops_here);
}

/* Linear blocks of the active rows: bits low_start .. low_start + width
 * (width <= 128), the nonzero ones appended to `low` as (lo, hi) pairs. */
F4_FN void f4e_low_thread(f4_u64 gid, f4_u64 total, const f4_u64 *mat, f4_u64 stride,
                          f4_u32 low_start, f4_u32 width, const f4_u32 *active, f4_u32 rows,
                          f4_u64 *low, f4_u32 *n_low)
{
    for (f4_u64 r = gid; r < rows; r += total) {
        if (!active[r]) continue;
        const f4_u64 *row = mat + r * stride;
        f4_u64 lo = 0ull, hi = 0ull;
        for (f4_u32 j = 0; j < width; ++j) {
            const f4_u32 b = low_start + j;
            if ((row[b >> 6] >> (b & 63u)) & 1ull) {
                if (j < 64u)
                    lo |= 1ull << j;
                else
                    hi |= 1ull << (j - 64u);
            }
        }
        if (lo == 0ull && hi == 0ull) continue;
        const f4_u32 at = F4_ATOMIC_ADD32(n_low, 1u);
        low[2u * at] = lo;
        low[2u * at + 1u] = hi;
    }
}

#endif /* F4_GF2_ECHELON_CUH */
