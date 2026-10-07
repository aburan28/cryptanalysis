/*
 * f4_gf2_echelon.cuh - forward elimination of one large Boolean Macaulay
 * matrix over its high columns, one 64-column panel at a time.
 *
 * The device half of `f4_gpu::CudaDecider::echelon`, and the same contract
 * as `f4_gf2`'s host `echelon`: every row either becomes the pivot of a
 * high column or is reduced to zero there, and what the reduced rows keep
 * of the linear block (at most 65 columns from `low_start`) is returned.
 * The pivot rows of a panel are the lexicographically first basis of its
 * candidates' words -- a row is a pivot when its word is independent of the
 * lower-numbered candidates' -- so the elimination and its word count are
 * deterministic, but they are not the host kernel's: only the row space,
 * hence the rank, the refutation and the pinned variables, is the same.
 *
 * Panel w (word w of every row) runs four steps:
 *   local        a thread per chunk of consecutive rows gathers the chunk's
 *                active rows with a high bit in word w and keeps, as the
 *                chunk's basis, those independent of its earlier ones;
 *   merge        one block merges adjacent bases pairwise, log2(chunks)
 *                rounds, into the panel's; one thread then puts it in
 *                reduced echelon form, each pivot a combination of the basis
 *                rows, with a pivot column no other pivot has;
 *   materialise  a thread per word: each pivot row becomes its combination
 *                of the original basis rows, across the rest of the row, and
 *                leaves the active set;
 *   update       a warp per remaining candidate reads which pivots it needs
 *                off its own word's pivot columns and XORs them into the
 *                rest of its row.
 * Rows without a high bit in word w are untouched by panel w.  The only
 * sequential work is merging bases of at most 64 words, so a panel with
 * many candidates is spread over the whole grid rather than one block.
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
    /* The basis rows, by index into row[], whose original words XOR to
     * pivot k. */
    f4_u64 comb[64];
    f4_u64 cols;     /* the panel's pivot columns */
    f4_u32 slot[64]; /* the pivot whose column is c, for each c in cols */
} F4ePivots;

/* A basis is up to 64 slots at chunk * 64: the row, its word in the panel,
 * and that word reduced by the slots before it, so that no two slots'
 * reduced words share a lowest bit. */

/* x reduced by the echelon whose element with lowest bit b is ech[b], for
 * each b in have: zero when x is in its span, else x's lowest bit is a
 * column the echelon has no element for. */
F4_FN f4_u64 f4e_reduce(f4_u64 x, const f4_u64 *ech, f4_u64 have)
{
    while (x != 0ull) {
        const f4_u32 b = F4_CTZ(x);
        if (((have >> b) & 1ull) == 0ull) break;
        x ^= ech[b];
    }
    return x;
}

/* Local: per chunk of chunk_rows consecutive rows, its candidates -- the
 * active rows with a high bit in word w -- appended to cand/pw for the
 * update, and its basis, kept in row order. */
F4_FN void f4e_local_thread(f4_u64 gid, f4_u64 total, const f4_u64 *mat, f4_u64 stride, f4_u32 w,
                            f4_u64 mask, const f4_u32 *active, f4_u32 rows, f4_u32 chunk_rows,
                            f4_u32 *cand, f4_u64 *pw, f4_u32 *count, f4_u32 *brow, f4_u64 *bword,
                            f4_u64 *bred, f4_u32 *bn)
{
    const f4_u64 chunks = ((f4_u64)rows + chunk_rows - 1u) / chunk_rows;
    for (f4_u64 c = gid; c < chunks; c += total) {
        f4_u64 ech[64];
        f4_u64 have = 0ull;
        f4_u32 n = 0u;
        const f4_u64 end = (c + 1u) * chunk_rows < rows ? (c + 1u) * chunk_rows : rows;
        for (f4_u64 r = c * chunk_rows; r < end; ++r) {
            if (!active[r]) continue;
            const f4_u64 word = mat[r * stride + w] & mask;
            if (word == 0ull) continue;
            const f4_u32 i = F4_ATOMIC_ADD32(count, 1u);
            cand[i] = (f4_u32)r;
            pw[i] = word;
            if (n == 64u) continue;
            const f4_u64 x = f4e_reduce(word, ech, have);
            if (x == 0ull) continue;
            const f4_u32 b = F4_CTZ(x);
            ech[b] = x;
            have |= 1ull << b;
            brow[c * 64u + n] = (f4_u32)r;
            bword[c * 64u + n] = word;
            bred[c * 64u + n] = x;
            ++n;
        }
        bn[c] = n;
    }
}

/* The basis of chunk `right` appended to that of chunk `left`, keeping only
 * the words independent of everything before them. */
F4_FN void f4e_merge_pair(f4_u32 *brow, f4_u64 *bword, f4_u64 *bred, f4_u32 *bn, f4_u32 left,
                          f4_u32 right)
{
    f4_u64 ech[64];
    f4_u64 have = 0ull;
    f4_u32 n = bn[left];
    for (f4_u32 s = 0; s < n; ++s) {
        const f4_u64 x = bred[(f4_u64)left * 64u + s];
        ech[F4_CTZ(x)] = x;
        have |= 1ull << F4_CTZ(x);
    }
    const f4_u32 m = bn[right];
    for (f4_u32 s = 0; s < m && n < 64u; ++s) {
        const f4_u64 at = (f4_u64)right * 64u + s;
        const f4_u64 x = f4e_reduce(bword[at], ech, have);
        if (x == 0ull) continue;
        ech[F4_CTZ(x)] = x;
        have |= 1ull << F4_CTZ(x);
        const f4_u64 to = (f4_u64)left * 64u + n;
        brow[to] = brow[at];
        bword[to] = bword[at];
        bred[to] = x;
        ++n;
    }
    bn[left] = n;
}

/* Merge: the chunks' bases pairwise until chunk 0 holds the panel's, then
 * its reduced echelon form as the panel's pivots.  Basis word k is reduced
 * by the earlier ones (comb[k] records which), then, highest pivot column
 * first, each pivot column is cleared from every other pivot. */
F4_BLOCK_FN void f4e_merge(f4_u32 nt, f4_u32 chunks, f4_u32 *brow, f4_u64 *bword, f4_u64 *bred,
                           f4_u32 *bn, F4ePivots *piv)
{
    for (f4_u32 step = 1u; step < chunks; step *= 2u) {
        F4_FOR_THREADS(tid)
            for (f4_u64 left = 2ull * step * tid; left < chunks; left += 2ull * step * nt) {
                if (left + step < chunks)
                    f4e_merge_pair(brow, bword, bred, bn, (f4_u32)left, (f4_u32)(left + step));
            }
        F4_END_THREADS
        F4_SYNC();
    }
    F4_SINGLE
    {
        const f4_u32 n = chunks ? bn[0] : 0u;
        f4_u64 red[64], comb[64];
        f4_u32 at[64];
        f4_u64 have = 0ull;
        for (f4_u32 k = 0; k < n; ++k) {
            f4_u64 x = bword[k], t = 1ull << k;
            while (x != 0ull && ((have >> F4_CTZ(x)) & 1ull) != 0ull) {
                const f4_u32 j = at[F4_CTZ(x)];
                x ^= red[j];
                t ^= comb[j];
            }
            red[k] = x;
            comb[k] = t;
            at[F4_CTZ(x)] = k;
            have |= 1ull << F4_CTZ(x);
        }
        for (f4_u32 c = 64u; c-- > 0u;) {
            if (((have >> c) & 1ull) == 0ull) continue;
            const f4_u32 k = at[c];
            for (f4_u32 j = 0; j < n; ++j) {
                if (j != k && ((red[j] >> c) & 1ull) != 0ull) {
                    red[j] ^= red[k];
                    comb[j] ^= comb[k];
                }
            }
        }
        piv->n = n;
        piv->total += n;
        piv->cols = have;
        for (f4_u32 k = 0; k < n; ++k) {
            piv->row[k] = brow[k];
            piv->comb[k] = comb[k];
            piv->slot[F4_CTZ(red[k])] = k;
        }
    }
    F4_SYNC();
}

/* Materialise, a thread per word: every pivot row becomes the combination
 * of original basis rows its comb names, over words w .. stride; the
 * originals are read before any is written.  Then the pivots leave the
 * active set. */
F4_FN void f4e_materialise_thread(f4_u64 gid, f4_u64 total, f4_u64 *mat, f4_u64 stride, f4_u32 w,
                                  f4_u32 *active, const F4ePivots *piv, f4_u64 *ops)
{
    const f4_u32 n = piv->n;
    for (f4_u64 x = w + gid; x < stride; x += total) {
        f4_u64 orig[64];
        for (f4_u32 k = 0; k < n; ++k) orig[k] = mat[(f4_u64)piv->row[k] * stride + x];
        for (f4_u32 k = 0; k < n; ++k) {
            f4_u64 acc = 0ull, h = piv->comb[k];
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
        for (f4_u32 k = 0; k < n; ++k) xors += F4_POPC(piv->comb[k]) - 1u;
        if (xors) F4_ATOMIC_ADD64(ops, xors * (stride - w));
    }
}

/* Update: a warp per candidate that is not a pivot.  Its word is in the
 * span of the reduced pivots, so it is the sum of those whose pivot column
 * it has; XORing them into words w .. stride clears the panel.  Pivot rows
 * are only read. */
F4_FN void f4e_update_thread(f4_u64 gid, f4_u64 total, f4_u64 *mat, f4_u64 stride, f4_u32 w,
                             const f4_u32 *cand, const f4_u64 *pw, const f4_u32 *count,
                             const f4_u32 *active, const F4ePivots *piv, f4_u64 *ops)
{
    const f4_u32 n = *count;
    const f4_u64 lane = gid & 31ull, warp = gid >> 5, warps = total >> 5;
    f4_u64 ops_here = 0ull;
    for (f4_u64 i = warp; i < n; i += warps) {
        if (!active[cand[i]]) continue;
        f4_u64 m = 0ull, h = pw[i] & piv->cols;
        while (h != 0ull) {
            m |= 1ull << piv->slot[F4_CTZ(h)];
            h &= h - 1ull;
        }
        f4_u64 *dst = mat + (f4_u64)cand[i] * stride;
        for (f4_u64 x = w + lane; x < stride; x += 32ull) {
            f4_u64 acc = 0ull, b = m;
            while (b != 0ull) {
                const f4_u32 j = F4_CTZ(b);
                b &= b - 1ull;
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
