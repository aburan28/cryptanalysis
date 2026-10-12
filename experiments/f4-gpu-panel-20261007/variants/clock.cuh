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

/* Panels with at most this many candidates keep everything the pivot
 * search touches -- words, rows, masks, pivot flags -- in shared memory:
 * each column's pass is a barrier apart from the next, so a global read in
 * it is latency every candidate waits for.  24 bytes a candidate, within
 * the 48 KiB a block may declare statically; most panels of the matrices
 * measured have fewer (experiments/f4-gpu-panel-20261007). */
#define F4E_SMEM_CAND 1920u

/* Words per tile of the update: one per lane of a warp. */
#define F4E_TILE 32u

/* Block-shared pivot words of one update tile, pivot-major. */
typedef struct {
    f4_u64 p[64u * F4E_TILE];
} F4eUpdateShared;

/* Block-shared state of the panel step. */
typedef struct {
    f4_u64 cols;
    f4_u64 best[3];
    f4_u32 n_cand;
    f4_u64 pw[F4E_SMEM_CAND];
    f4_u64 coeff[F4E_SMEM_CAND];
    f4_u32 cand[F4E_SMEM_CAND];
    f4_u32 is_piv[F4E_SMEM_CAND];
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
 * is_piv[i] marks the pivots.  One pass per column eliminates it and
 * looks for the next column's pivot.  At the end each pivot's history is
 * expanded to the original pivot rows it combines. */
F4_BLOCK_FN void f4e_panel(F4ePanelShared *sh, f4_u32 nt, const f4_u32 *cand_global,
                           f4_u64 *pw_global, f4_u64 *coeff_global, f4_u32 *is_piv_global,
                           const f4_u32 *count, F4ePivots *piv)
{
    const long long t0 = clock64();
    F4_SINGLE
    {
        sh->n_cand = *count;
        sh->cols = 0ull;
        sh->best[0] = ~0ull;
        sh->best[1] = ~0ull;
        sh->best[2] = ~0ull;
    }
    F4_SYNC();
    const long long t1 = clock64();
    const int staged = sh->n_cand <= F4E_SMEM_CAND;
    f4_u64 *pw = staged ? sh->pw : pw_global;
    f4_u64 *coeff = staged ? sh->coeff : coeff_global;
    f4_u32 *is_piv = staged ? sh->is_piv : is_piv_global;
    const f4_u32 *cand = staged ? sh->cand : cand_global;
    F4_FOR_THREADS(tid)
        f4_u64 acc = 0ull;
        for (f4_u32 i = tid; i < sh->n_cand; i += nt) {
            coeff[i] = 0ull;
            is_piv[i] = 0u;
            if (staged) {
                sh->cand[i] = cand_global[i];
                sh->pw[i] = pw_global[i];
            }
            acc |= pw[i];
        }
        if (acc) F4_ATOMIC_OR64(&sh->cols, acc);
    F4_END_THREADS
    F4_SYNC();
    const long long t2 = clock64();
    long long t3 = t2;
    f4_u32 rounds = 0u;
    f4_u64 cols = sh->cols;
    f4_u32 n_piv = 0u;
    if (cols != 0ull) {
        f4_u32 c = F4_CTZ(cols);
        F4_FOR_THREADS(tid)
            f4_u64 mine = ~0ull;
            for (f4_u32 i = tid; i < sh->n_cand; i += nt) {
                if ((pw[i] >> c) & 1ull) {
                    f4_u64 key = ((f4_u64)cand[i] << 32) | i;
                    mine = key < mine ? key : mine;
                }
            }
            if (mine != ~0ull) F4_ATOMIC_MIN64(&sh->best[0], mine);
        F4_END_THREADS
        F4_SYNC();
        t3 = clock64();
        /* Round r reads slot r % 3, reduces column r + 1 into slot
         * (r + 1) % 3 and clears slot (r + 2) % 3, which every thread read
         * before the barrier that ended round r - 1. */
        for (f4_u32 round = 0;; ++round) {
            const f4_u64 best = sh->best[round % 3u];
            const f4_u32 p = best == ~0ull ? F4_NONE : (f4_u32)(best & 0xffffffffull);
            const f4_u64 rest = cols & (cols - 1ull);
            const f4_u32 next = rest ? F4_CTZ(rest) : 64u;
            const f4_u32 k = n_piv;
            F4_FOR_THREADS(tid)
                if (tid == 0u) {
                    sh->best[(round + 2u) % 3u] = ~0ull;
                    if (p != F4_NONE) {
                        piv->row[k] = cand[p];
                        piv->hist[k] = coeff[p];
                        is_piv[p] = 1u;
                    }
                }
                f4_u64 mine = ~0ull;
                for (f4_u32 i = tid; i < sh->n_cand; i += nt) {
                    if (i == p || is_piv[i]) continue;
                    f4_u64 word = pw[i];
                    if (p != F4_NONE && ((word >> c) & 1ull)) {
                        word ^= pw[p];
                        pw[i] = word;
                        coeff[i] |= 1ull << k;
                    }
                    if (next < 64u && ((word >> next) & 1ull)) {
                        f4_u64 key = ((f4_u64)cand[i] << 32) | i;
                        mine = key < mine ? key : mine;
                    }
                }
                if (mine != ~0ull) F4_ATOMIC_MIN64(&sh->best[(round + 1u) % 3u], mine);
            F4_END_THREADS
            F4_SYNC();
            if (p != F4_NONE) ++n_piv;
            ++rounds;
            if (next == 64u) break;
            cols = rest;
            c = next;
        }
    }
    const long long t4 = clock64();
    if (staged) {
        /* The update reads them from global memory. */
        F4_FOR_THREADS(tid)
            for (f4_u32 i = tid; i < sh->n_cand; i += nt) {
                coeff_global[i] = sh->coeff[i];
                is_piv_global[i] = sh->is_piv[i];
            }
        F4_END_THREADS
    }
    const long long t5 = clock64();
    F4_SINGLE
    {
        piv->n = n_piv;
        piv->total += n_piv;
        /* Pivot k is its own row plus the final pivots its history names,
         * so over the original rows it is hist[k] plus their expansions. */
        for (f4_u32 k = 0; k < n_piv; ++k) {
            f4_u64 h = piv->hist[k], full = h;
            while (h != 0ull) {
                const f4_u32 j = F4_CTZ(h);
                h &= h - 1ull;
                full ^= piv->hist[j];
            }
            piv->hist[k] = full;
        }
        printf("F4E_CLK %u %u %u %lld %lld %lld %lld %lld %lld\n", sh->n_cand, rounds, n_piv,
               t1 - t0, t2 - t1, t3 - t2, t4 - t3, t5 - t4, clock64() - t5);
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
