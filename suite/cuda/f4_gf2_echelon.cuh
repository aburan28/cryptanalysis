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
 *                record the pivots they took as a 64-bit mask; the rows
 *                are reduced lazily, as far as the pivot search reads;
 *   materialise  a thread per word: each pivot row becomes the
 *                combination of original pivot rows its expanded mask
 *                names, across the rest of the row, and leaves the active
 *                set;
 *   update       a block per 32-word tile of the rest of the rows (and per
 *                share of the candidates) loads the pivots' words of its
 *                tile into shared memory, then a warp per remaining row
 *                XORs in the pivots its mask names, a word per lane.
 * Rows without a high bit in word w are untouched by panel w.  The update
 * is most of the work: every remaining row takes about half the pivots,
 * and reading them from shared memory rather than global memory leaves
 * global traffic at one read and one write of each row's words.
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
    /* Earlier pivots of the panel XORed into pivot k; once the panel is
     * done, expanded to the original pivot rows it combines. */
    f4_u64 hist[64];
} F4ePivots;

/* Words per tile of the update: one per lane of a warp. */
#define F4E_TILE 32u

/* Block-shared pivot words of one update tile, pivot-major. */
typedef struct {
    f4_u64 p[64u * F4E_TILE];
} F4eUpdateShared;

/* A candidate's state flag once it is a pivot; until then its state is
 * how many of the panel's pivots it has taken. */
#define F4E_PIVOT 0x80000000u

/* Block-shared state of the panel step. */
typedef struct {
    f4_u64 cols;
    f4_u64 best[3];
    f4_u64 word[64]; /* pivot k's word */
    f4_u32 col[64];  /* and its column */
    f4_u32 scan[2][F4_MAX_THREADS];
} F4ePanelShared;

/* Gather: active rows with a high bit in word w, with that word, in any
 * order; and each row's word in prow, zero for the rest. */
F4_FN void f4e_gather_thread(f4_u64 gid, f4_u64 total, const f4_u64 *mat, f4_u64 stride, f4_u32 w,
                             f4_u64 mask, const f4_u32 *active, f4_u32 rows, f4_u32 *cand,
                             f4_u64 *pw, f4_u32 *count, f4_u64 *prow)
{
    for (f4_u64 r = gid; r < rows; r += total) {
        const f4_u64 word = active[r] ? mat[r * stride + w] & mask : 0ull;
        prow[r] = word;
        if (word == 0ull) continue;
        f4_u32 i = F4_ATOMIC_ADD32(count, 1u);
        cand[i] = (f4_u32)r;
        pw[i] = word;
    }
}

/* Brings a candidate's word and mask from pivot `from` up to pivot k:
 * each pivot is taken when the word has its column. */
F4_FN void f4e_catch_up(const F4ePanelShared *sh, f4_u32 from, f4_u32 k, f4_u64 *word, f4_u64 *mask)
{
    for (f4_u32 j = from; j < k; ++j) {
        if ((*word >> sh->col[j]) & 1ull) {
            *word ^= sh->word[j];
            *mask |= 1ull << j;
        }
    }
}

/* Panel: pivots of word w among the gathered rows, lowest row first per
 * column.  coeff[i] collects the pivot slots XORed into candidate i, and
 * is_piv[i] ends as 1 for the pivots, 0 for the rest.
 *
 * A column's pivot is its lowest candidate that has the column once
 * reduced by the earlier pivots, so the candidates are reduced lazily: per
 * column, a block-wide chunk at a time in row order, each brought up to
 * date as it is read, until a chunk has the column.  Most columns stop in
 * the first chunk, so a round costs a chunk, not every candidate; one pass
 * at the end brings the rest up to date.  Only a panel of more than one
 * chunk needs its candidates in row order, so only such a panel rebuilds
 * them from prow, a pass over every row.  Pivot histories are then
 * expanded to the original pivot rows they combine. */
F4_BLOCK_FN void f4e_panel(F4ePanelShared *sh, f4_u32 nt, const f4_u64 *prow, f4_u32 rows,
                           f4_u32 *cand, f4_u64 *pw, f4_u64 *coeff, f4_u32 *is_piv,
                           const f4_u32 *count, F4ePivots *piv)
{
    const f4_u32 n_cand = *count;
    F4_SINGLE
    {
        sh->cols = 0ull;
        sh->best[0] = ~0ull;
        sh->best[1] = ~0ull;
        sh->best[2] = ~0ull;
    }
    if (n_cand > nt) {
        /* Thread t compacts rows [t * span, (t + 1) * span): count, scan,
         * write. */
        const f4_u32 span = (rows + nt - 1u) / nt;
        F4_FOR_THREADS(tid)
            const f4_u64 lo = (f4_u64)tid * span < rows ? (f4_u64)tid * span : rows;
            const f4_u64 hi = lo + span < rows ? lo + span : rows;
            f4_u32 n = 0u;
            for (f4_u64 r = lo; r < hi; ++r) n += prow[r] != 0ull;
            sh->scan[0][tid] = n;
        F4_END_THREADS
        F4_SYNC();
        f4_u32 src = 0u;
        for (f4_u32 d = 1u; d < nt; d <<= 1u) {
            F4_FOR_THREADS(tid)
                sh->scan[src ^ 1u][tid] =
                    sh->scan[src][tid] + (tid >= d ? sh->scan[src][tid - d] : 0u);
            F4_END_THREADS
            F4_SYNC();
            src ^= 1u;
        }
        F4_FOR_THREADS(tid)
            const f4_u64 lo = (f4_u64)tid * span < rows ? (f4_u64)tid * span : rows;
            const f4_u64 hi = lo + span < rows ? lo + span : rows;
            f4_u32 at = tid ? sh->scan[src][tid - 1u] : 0u;
            for (f4_u64 r = lo; r < hi; ++r) {
                const f4_u64 word = prow[r];
                if (word == 0ull) continue;
                cand[at] = (f4_u32)r;
                pw[at] = word;
                ++at;
            }
        F4_END_THREADS
    }
    F4_SYNC();
    F4_FOR_THREADS(tid)
        f4_u64 acc = 0ull;
        for (f4_u32 i = tid; i < n_cand; i += nt) {
            coeff[i] = 0ull;
            is_piv[i] = 0u;
            acc |= pw[i];
        }
        if (acc) F4_ATOMIC_OR64(&sh->cols, acc);
    F4_END_THREADS
    F4_SYNC();
    f4_u64 cols = sh->cols;
    f4_u32 k = 0u;
    /* Chunk g reduces into best[g % 3] and clears best[(g + 1) % 3], which
     * every thread read before the barrier that ended chunk g - 1. */
    f4_u32 g = 0u;
    while (cols != 0ull) {
        const f4_u32 c = F4_CTZ(cols);
        cols &= cols - 1ull;
        f4_u32 p = F4_NONE;
        for (f4_u32 s = 0u; s < n_cand && p == F4_NONE; s += nt, ++g) {
            F4_FOR_THREADS(tid)
                if (tid == 0u) sh->best[(g + 1u) % 3u] = ~0ull;
                const f4_u32 i = s + tid;
                if (i < n_cand) {
                    const f4_u32 st = is_piv[i];
                    if (!(st & F4E_PIVOT)) {
                        f4_u64 word = pw[i];
                        if (st < k) {
                            f4_u64 mask = coeff[i];
                            f4e_catch_up(sh, st, k, &word, &mask);
                            pw[i] = word;
                            coeff[i] = mask;
                            is_piv[i] = k;
                        }
                        if ((word >> c) & 1ull)
                            F4_ATOMIC_MIN64(&sh->best[g % 3u], ((f4_u64)cand[i] << 32) | i);
                    }
                }
            F4_END_THREADS
            F4_SYNC();
            const f4_u64 best = sh->best[g % 3u];
            if (best != ~0ull) p = (f4_u32)(best & 0xffffffffull);
        }
        if (p == F4_NONE) continue;
        F4_SINGLE
        {
            sh->word[k] = pw[p];
            sh->col[k] = c;
            piv->row[k] = cand[p];
            piv->hist[k] = coeff[p];
            is_piv[p] = F4E_PIVOT;
        }
        F4_SYNC();
        ++k;
    }
    F4_FOR_THREADS(tid)
        for (f4_u32 i = tid; i < n_cand; i += nt) {
            const f4_u32 st = is_piv[i];
            if (st & F4E_PIVOT) {
                is_piv[i] = 1u;
                continue;
            }
            if (st < k) {
                f4_u64 word = pw[i], mask = coeff[i];
                f4e_catch_up(sh, st, k, &word, &mask);
                coeff[i] = mask;
            }
            is_piv[i] = 0u;
        }
    F4_END_THREADS
    F4_SINGLE
    {
        piv->n = k;
        piv->total += k;
        /* Pivot k is its own row plus the final pivots its history names,
         * so over the original rows it is hist[k] plus their expansions. */
        for (f4_u32 j = 0; j < k; ++j) {
            f4_u64 h = piv->hist[j], full = h;
            while (h != 0ull) {
                const f4_u32 i = F4_CTZ(h);
                h &= h - 1ull;
                full ^= piv->hist[i];
            }
            piv->hist[j] = full;
        }
    }
    F4_SYNC();
}

/* Materialise, a thread per word: every pivot row becomes its original
 * plus the original pivot rows its expanded history names, over words
 * w .. stride; the originals are read before any is written.  Then the
 * pivots leave the active set. */
F4_FN void f4e_materialise_thread(f4_u64 gid, f4_u64 total, f4_u64 *mat, f4_u64 stride, f4_u32 w,
                                  f4_u32 *active, const F4ePivots *piv, f4_u64 *ops)
{
    const f4_u32 n = piv->n;
    for (f4_u64 x = w + gid; x < stride; x += total) {
        f4_u64 orig[64];
        for (f4_u32 k = 0; k < n; ++k) orig[k] = mat[(f4_u64)piv->row[k] * stride + x];
        for (f4_u32 k = 0; k < n; ++k) {
            f4_u64 acc = orig[k], h = piv->hist[k];
            while (h != 0ull) {
                const f4_u32 j = F4_CTZ(h);
                h &= h - 1ull;
                acc ^= orig[j];
            }
            mat[(f4_u64)piv->row[k] * stride + x] = acc;
        }
    }
    for (f4_u64 k = gid; k < n; k += total) active[piv->row[k]] = 0u;
    if (gid == 0ull) {
        f4_u64 xors = 0ull;
        for (f4_u32 k = 0; k < n; ++k) xors += F4_POPC(piv->hist[k]);
        if (xors) F4_ATOMIC_ADD64(ops, xors * (stride - w));
    }
}

/* Update, block `block` of a grid of tiles × parts: tile block / parts
 * covers words w + 32 * tile .. of every row, and part block % parts takes
 * every parts-th warp's share of the candidates.  The tile's pivot words
 * are loaded once; then a warp per remaining candidate XORs the pivots its
 * mask names into its row, lane l on word l of the tile.  Pivot rows are
 * only read, so blocks never write what another reads.  nt is a multiple
 * of 32. */
F4_BLOCK_FN void f4e_update_block(F4eUpdateShared *sh, f4_u32 nt, f4_u64 block, f4_u64 parts,
                                  f4_u64 *mat, f4_u64 stride, f4_u32 w, const f4_u32 *cand,
                                  const f4_u64 *coeff, const f4_u32 *is_piv, const f4_u32 *count,
                                  const F4ePivots *piv, f4_u64 *ops)
{
    const f4_u32 n = *count, k = piv->n;
    const f4_u64 tile = block / parts, part = block % parts;
    const f4_u64 x0 = w + tile * F4E_TILE;
    const f4_u64 width = stride - x0 < F4E_TILE ? stride - x0 : F4E_TILE;
    F4_FOR_THREADS(tid)
        for (f4_u32 e = tid; e < k * F4E_TILE; e += nt) {
            const f4_u32 j = e / F4E_TILE, x = e % F4E_TILE;
            sh->p[e] = x < width ? mat[(f4_u64)piv->row[j] * stride + x0 + x] : 0ull;
        }
    F4_END_THREADS
    F4_SYNC();
    F4_FOR_THREADS(tid)
        const f4_u32 lane = tid & 31u, warps = nt >> 5;
        f4_u64 ops_here = 0ull;
        for (f4_u64 i = part * warps + (tid >> 5); i < n; i += parts * warps) {
            if (is_piv[i]) continue;
            const f4_u64 m = coeff[i];
            if (lane < width) {
                f4_u64 acc = 0ull, h = m;
                while (h != 0ull) {
                    const f4_u32 j = F4_CTZ(h);
                    h &= h - 1ull;
                    acc ^= sh->p[j * F4E_TILE + lane];
                }
                mat[(f4_u64)cand[i] * stride + x0 + lane] ^= acc;
            }
            if (lane == 0u && tile == 0u) ops_here += (f4_u64)F4_POPC(m) * (stride - w);
        }
        if (ops_here) F4_ATOMIC_ADD64(ops, ops_here);
    F4_END_THREADS
    F4_SYNC();
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
