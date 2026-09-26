/*
 * f4_gf2_device.cuh - batched Boolean Macaulay decisions, one thread block
 * per system.
 *
 * This is the device half of `suite/src/cryptanalysis/f4_gpu.rs`, and the
 * same algorithm as `f4_gf2::decide` on the host: given a Boolean system
 * and a Macaulay degree D, build the degree-D Macaulay matrix over the
 * variables that occur, eliminate its high-degree columns, reduce the
 * linear block, and report whether the ideal contains 1 and which rows
 * pin a variable.  Row and column counts are reported in the reference
 * builder's units and checked against the same caps, so a system is
 * oversize here exactly when it is on the host.
 *
 * The file is written in the common subset of C11 and CUDA C++.  Every
 * block-level step is a phase between barriers in which each thread writes
 * only its own locations (or uses an atomic), so `f4_gf2_emulate.c` runs
 * this very source on the host by executing each phase as a loop over
 * thread indices.  That is how the kernel is tested on machines without a
 * GPU: the emulator and the host kernel must agree on every decision.
 *
 * Nothing here includes a header, so NVRTC compiles it as is.
 */
#ifndef F4_GF2_DEVICE_CUH
#define F4_GF2_DEVICE_CUH

typedef unsigned long long f4_u64;
typedef unsigned int f4_u32;

#define F4_DMAX        7u
#define F4_MAX_POLYS   256u
#define F4_MAX_THREADS 1024u
#define F4_NONE        0xffffffffu

#define F4_STATUS_DECIDED  0u
#define F4_STATUS_OVERSIZE 1u
#define F4_STATUS_EMPTY    2u
#define F4_STATUS_NO_POLYS 3u
#define F4_STATUS_FALLBACK 4u

/* Per-system result.  Layout mirrored by `F4Result` in f4_gpu.rs. */
typedef struct {
    f4_u32 status;
    f4_u32 refuted;
    f4_u64 forced_mask; /* variables pinned by a row v or v + 1 */
    f4_u64 forced_vals; /* their values (bit set: v + 1, i.e. v = 1) */
    f4_u64 ref_rows;    /* rows in reference units */
    f4_u64 ref_cols;    /* columns in reference units */
    f4_u64 word_ops;    /* 64-bit word XORs performed */
    f4_u32 rows;        /* nonempty rows eliminated */
    f4_u32 cols;        /* columns eliminated */
    f4_u32 f5_skipped;  /* nonempty rows the F5 mask left out */
    f4_u32 reserved;
} F4Result;

/* Block-shared state.  Scalars that one thread computes and the others
 * read live here, never in registers, so the host emulator sees them too. */
typedef struct {
    f4_u32 status;
    f4_u32 poly_lo, poly_hi, n_vars, degree;
    f4_u64 occ;
    f4_u32 v, missing, n_gen, n_cand;
    f4_u32 gen_poly[F4_MAX_POLYS];
    f4_u32 gen_k[F4_MAX_POLYS];
    f4_u32 cand_start[F4_MAX_POLYS + 1];
    f4_u64 base[F4_DMAX + 2];
    f4_u64 rank_space;
    f4_u32 pos[64];
    f4_u32 var_of[64];
    f4_u32 binom[65][F4_DMAX + 1];
    f4_u64 upto[F4_DMAX + 1];
    f4_u32 n_bitmap_words, n_cols, stride, low_start, low_width, const_present;
    f4_u32 low_var[65];
    f4_u64 off_prefix, off_mat, off_lead, off_meta, off_class, off_low, off_lmeta;
    f4_u64 ref_rows, ref_cols, word_ops, nonempty, skipped;
    /* Pivot reductions rotate through three slots: round r reduces into
     * slot r % 3 and clears slot (r + 1) % 3.  Every thread has read slot
     * r % 3 before the barrier of round r + 1, so clearing it in round
     * r + 2 is safe even when a round has no second phase. */
    f4_u64 best[3];
    f4_u32 n_low, lrank;
    f4_u32 lpivot[65];
    f4_u32 thread_sum[F4_MAX_THREADS];
} F4Shared;

#if defined(__CUDACC__)
#    define F4_FN       static __device__ __forceinline__
#    define F4_BLOCK_FN static __device__
#    define F4_FOR_THREADS(tid)                                                                    \
        {                                                                                          \
            const f4_u32 tid = threadIdx.x;
#    define F4_END_THREADS        }
#    define F4_SINGLE             if (threadIdx.x == 0)
#    define F4_SYNC()             __syncthreads()
#    define F4_POPC(x)            ((f4_u32)__popcll(x))
#    define F4_CTZ(x)             ((f4_u32)(__ffsll((long long)(x)) - 1))
#    define F4_ATOMIC_OR64(p, x)  atomicOr((p), (x))
#    define F4_ATOMIC_ADD64(p, x) atomicAdd((p), (x))
#    define F4_ATOMIC_MIN64(p, x) atomicMin((p), (x))
#    define F4_ATOMIC_ADD32(p, x) atomicAdd((p), (x))
#else
/* Host emulation: a phase is a loop over thread indices, a barrier is a
 * no-op, and an atomic is the plain operation with CUDA's return value. */
#    define F4_FN               static inline
#    define F4_BLOCK_FN         static
#    define F4_FOR_THREADS(tid) for (f4_u32 tid = 0; tid < nt; ++tid) {
#    define F4_END_THREADS      }
#    define F4_SINGLE
#    define F4_SYNC()             ((void)0)
#    define F4_POPC(x)            ((f4_u32)__builtin_popcountll(x))
#    define F4_CTZ(x)             ((f4_u32)__builtin_ctzll(x))
static inline f4_u64 f4_host_or64(f4_u64 *p, f4_u64 x)
{
    f4_u64 old = *p;
    *p = old | x;
    return old;
}
static inline f4_u64 f4_host_add64(f4_u64 *p, f4_u64 x)
{
    f4_u64 old = *p;
    *p = old + x;
    return old;
}
static inline f4_u64 f4_host_min64(f4_u64 *p, f4_u64 x)
{
    f4_u64 old = *p;
    *p = old < x ? old : x;
    return old;
}
static inline f4_u32 f4_host_add32(f4_u32 *p, f4_u32 x)
{
    f4_u32 old = *p;
    *p = old + x;
    return old;
}
#    define F4_ATOMIC_OR64(p, x)  f4_host_or64((p), (x))
#    define F4_ATOMIC_ADD64(p, x) f4_host_add64((p), (x))
#    define F4_ATOMIC_MIN64(p, x) f4_host_min64((p), (x))
#    define F4_ATOMIC_ADD32(p, x) f4_host_add32((p), (x))
#endif

F4_FN f4_u64 f4_all_vars(f4_u32 n_vars)
{
    return n_vars >= 64u ? ~0ull : ((1ull << n_vars) - 1ull);
}

/* Column rank of monomial x (a subset of the occurring variables):
 * degree-major, colex within a degree, which is descending DegRevLex. */
F4_FN f4_u64 f4_rank(const F4Shared *sh, f4_u64 x)
{
    f4_u32 d = F4_POPC(x);
    f4_u64 r = sh->base[d];
    f4_u32 k = 1u;
    while (x != 0ull) {
        f4_u32 b = F4_CTZ(x);
        r += sh->binom[sh->pos[b]][k];
        ++k;
        x &= x - 1ull;
    }
    return r;
}

/* Dense column of rank r: the set ranks below it. */
F4_FN f4_u32 f4_dense(const f4_u64 *bitmap, const f4_u32 *prefix, f4_u64 r)
{
    f4_u64 w = r >> 6;
    f4_u64 below = (r & 63ull) ? (bitmap[w] & ((1ull << (r & 63ull)) - 1ull)) : 0ull;
    return prefix[w] + F4_POPC(below);
}

/* Multiplier of candidate row `local` of a poly with k = D - deg p:
 * degree-major, colex within a degree.  Returns the mask; *deg its size. */
F4_FN f4_u64 f4_multiplier(const F4Shared *sh, f4_u32 local, f4_u32 k, f4_u32 *deg)
{
    f4_u32 j = 0u;
    while (j < k && local >= sh->binom[sh->v][j]) {
        local -= sh->binom[sh->v][j];
        ++j;
    }
    *deg = j;
    f4_u64 u = 0ull;
    f4_u32 c = sh->v;
    for (f4_u32 i = j; i >= 1u; --i) {
        /* largest element c' < c with C(c', i) <= local */
        do {
            --c;
        } while (sh->binom[c][i] > local);
        local -= sh->binom[c][i];
        u |= 1ull << sh->var_of[c];
    }
    return u;
}

/* Leading column of `row` at or after word `from`, or F4_NONE. */
F4_FN f4_u32 f4_lead(const f4_u64 *row, f4_u32 from, f4_u32 stride)
{
    for (f4_u32 w = from; w < stride; ++w)
        if (row[w] != 0ull) return w * 64u + F4_CTZ(row[w]);
    return F4_NONE;
}

/* One-time table setup, shared by every system a block decides. */
F4_BLOCK_FN void f4_block_init(F4Shared *sh, f4_u32 nt)
{
    F4_FOR_THREADS(tid)
        for (f4_u32 n = tid; n <= 64u; n += nt) {
            /* C(n, k) = n! / (k! (n-k)!), exact in 64 bits for k <= 7 */
            for (f4_u32 k = 0; k <= F4_DMAX; ++k) {
                f4_u64 c = 1ull;
                if (k > n) {
                    c = 0ull;
                } else {
                    for (f4_u32 i = 1; i <= k; ++i) c = c * (f4_u64)(n - k + i) / (f4_u64)i;
                }
                sh->binom[n][k] = (f4_u32)c;
            }
        }
    F4_END_THREADS
    F4_SYNC();
}

/* Stage 1: read the system, find the occurring variables and the
 * generating equations, and lay out rank space and scratch. */
F4_BLOCK_FN void f4_stage_layout(F4Shared *sh, f4_u32 nt, const f4_u64 *terms,
                                 const f4_u32 *poly_start, const f4_u32 *sys_poly_start,
                                 const f4_u32 *sys_meta, f4_u32 sys, f4_u64 scratch_words)
{
    (void)nt;
    F4_SINGLE
    {
        sh->status = F4_STATUS_DECIDED;
        sh->poly_lo = sys_poly_start[sys];
        sh->poly_hi = sys_poly_start[sys + 1];
        sh->n_vars = sys_meta[sys] & 0xffu;
        sh->degree = (sys_meta[sys] >> 8) & 0xffu;
        sh->occ = 0ull;
        sh->ref_rows = 0ull;
        sh->ref_cols = 0ull;
        sh->word_ops = 0ull;
        sh->nonempty = 0ull;
        sh->skipped = 0ull;
        sh->n_low = 0u;
        sh->n_gen = 0u;
        if (sh->poly_hi == sh->poly_lo)
            sh->status = F4_STATUS_NO_POLYS;
        else if (sh->degree > F4_DMAX || sh->poly_hi - sh->poly_lo > F4_MAX_POLYS ||
                 sh->n_vars > 64u)
            sh->status = F4_STATUS_FALLBACK;
    }
    F4_SYNC();
    if (sh->status != F4_STATUS_DECIDED) return;
    F4_SINGLE
    {
        /* Generating equations: nonzero, degree at most D. */
        for (f4_u32 p = sh->poly_lo; p < sh->poly_hi; ++p) {
            f4_u32 lo = poly_start[p], hi = poly_start[p + 1];
            if (lo == hi) continue;
            f4_u32 pdeg = 0u;
            f4_u64 vars = 0ull;
            for (f4_u32 t = lo; t < hi; ++t) {
                f4_u32 d = F4_POPC(terms[t]);
                pdeg = d > pdeg ? d : pdeg;
                vars |= terms[t];
            }
            if (pdeg > sh->degree) continue;
            sh->gen_poly[sh->n_gen] = p;
            sh->gen_k[sh->n_gen] = sh->degree - pdeg;
            sh->n_gen += 1u;
            sh->occ |= vars;
        }
        f4_u32 v = 0u;
        for (f4_u32 b = 0; b < 64u; ++b) {
            if ((sh->occ >> b) & 1ull) {
                sh->pos[b] = v;
                sh->var_of[v] = b;
                ++v;
            }
        }
        sh->v = v;
        sh->missing = F4_POPC(f4_all_vars(sh->n_vars) & ~sh->occ);
        /* Rank offsets, highest degree first. */
        f4_u32 dm = sh->degree < v ? sh->degree : v;
        for (f4_u32 d = 0; d <= F4_DMAX + 1u; ++d) sh->base[d] = 0ull;
        for (f4_u32 d = dm; d-- > 0u;) sh->base[d] = sh->base[d + 1u] + sh->binom[v][d + 1u];
        sh->rank_space = sh->base[0] + 1ull;
        for (f4_u32 s = 0; s <= F4_DMAX; ++s) {
            f4_u64 acc = 0ull;
            for (f4_u32 j = 0; j <= s && j <= sh->missing; ++j) acc += sh->binom[sh->missing][j];
            sh->upto[s] = acc;
        }
        /* Candidate rows: every multiplier of degree <= k per equation. */
        f4_u64 total = 0ull;
        for (f4_u32 g = 0; g < sh->n_gen; ++g) {
            sh->cand_start[g] = (f4_u32)total;
            for (f4_u32 j = 0; j <= sh->gen_k[g] && j <= v; ++j) total += sh->binom[v][j];
        }
        sh->cand_start[sh->n_gen] = (f4_u32)total;
        sh->n_bitmap_words = (f4_u32)((sh->rank_space + 63ull) >> 6);
        sh->off_prefix = sh->n_bitmap_words;
        sh->off_mat = sh->off_prefix + ((sh->n_bitmap_words + 1ull) >> 1);
        if (sh->n_gen == 0u) {
            sh->status = F4_STATUS_EMPTY;
        } else if (total > 0x7fffffffull || sh->rank_space > 0x7fffffffull ||
                   sh->off_mat > scratch_words) {
            sh->status = F4_STATUS_FALLBACK;
        } else {
            sh->n_cand = (f4_u32)total;
        }
    }
    F4_SYNC();
}

/* Stage 2: mark every product monomial's rank, then prefix-count the
 * bitmap into dense column indices. */
F4_BLOCK_FN void f4_stage_columns(F4Shared *sh, f4_u32 nt, const f4_u64 *terms,
                                  const f4_u32 *poly_start, f4_u64 *scratch, f4_u64 scratch_words)
{
    f4_u64 *bitmap = scratch;
    f4_u32 *prefix = (f4_u32 *)(scratch + sh->off_prefix);
    F4_FOR_THREADS(tid)
        for (f4_u32 w = tid; w < sh->n_bitmap_words; w += nt) bitmap[w] = 0ull;
    F4_END_THREADS
    F4_SYNC();
    F4_FOR_THREADS(tid)
        f4_u32 g = 0u;
        for (f4_u32 row = tid; row < sh->n_cand; row += nt) {
            while (row >= sh->cand_start[g + 1u]) ++g;
            f4_u32 deg;
            f4_u64 u = f4_multiplier(sh, row - sh->cand_start[g], sh->gen_k[g], &deg);
            f4_u32 p = sh->gen_poly[g];
            for (f4_u32 t = poly_start[p]; t < poly_start[p + 1u]; ++t) {
                f4_u64 r = f4_rank(sh, terms[t] | u);
                F4_ATOMIC_OR64(&bitmap[r >> 6], 1ull << (r & 63ull));
            }
        }
    F4_END_THREADS
    F4_SYNC();
    /* Exclusive block scan of the bitmap's popcounts. */
    F4_FOR_THREADS(tid)
        f4_u32 chunk = (sh->n_bitmap_words + nt - 1u) / nt;
        f4_u32 lo = tid * chunk, hi = lo + chunk;
        if (hi > sh->n_bitmap_words) hi = sh->n_bitmap_words;
        f4_u32 sum = 0u;
        for (f4_u32 w = lo; w < hi; ++w) sum += F4_POPC(bitmap[w]);
        sh->thread_sum[tid] = sum;
    F4_END_THREADS
    F4_SYNC();
    F4_SINGLE
    {
        f4_u32 run = 0u;
        for (f4_u32 i = 0; i < nt; ++i) {
            f4_u32 s = sh->thread_sum[i];
            sh->thread_sum[i] = run;
            run += s;
        }
        sh->n_cols = run;
    }
    F4_SYNC();
    F4_FOR_THREADS(tid)
        f4_u32 chunk = (sh->n_bitmap_words + nt - 1u) / nt;
        f4_u32 lo = tid * chunk, hi = lo + chunk;
        if (hi > sh->n_bitmap_words) hi = sh->n_bitmap_words;
        f4_u32 run = sh->thread_sum[tid];
        for (f4_u32 w = lo; w < hi; ++w) {
            prefix[w] = run;
            run += F4_POPC(bitmap[w]);
        }
    F4_END_THREADS
    F4_SYNC();
    F4_SINGLE
    {
        sh->stride = (sh->n_cols + 63u) / 64u;
        /* Degree <= 1 ranks start at base[1]; the constant is base[0]. */
        f4_u64 b1 = sh->v >= 1u && sh->degree >= 1u ? sh->base[1] : sh->base[0];
        sh->low_start = f4_dense(bitmap, prefix, b1);
        sh->low_width = sh->n_cols - sh->low_start;
        f4_u32 j = 0u;
        for (f4_u64 r = b1; r < sh->rank_space; ++r) {
            if ((bitmap[r >> 6] >> (r & 63ull)) & 1ull) {
                sh->low_var[j] = r == sh->base[0] ? F4_NONE : sh->var_of[r - b1];
                ++j;
            }
        }
        sh->const_present = (bitmap[sh->base[0] >> 6] >> (sh->base[0] & 63ull)) & 1ull;
        f4_u64 n = sh->n_cand, s = sh->stride, half = (n + 1ull) >> 1;
        sh->off_lead = sh->off_mat + n * s;
        sh->off_meta = sh->off_lead + half;
        sh->off_class = sh->off_meta + half;
        sh->off_low = sh->off_class + (f4_u64)(sh->degree + 1u) * s;
        sh->off_lmeta = sh->off_low + 2ull * n;
        if (sh->off_lmeta + half > scratch_words || sh->low_width > 65u)
            sh->status = F4_STATUS_FALLBACK;
    }
    F4_SYNC();
}

/* Stage 3: write every candidate row by XOR, and count rows and columns in
 * reference units.  Rows set in the F5 mask (words skip_lo .. skip_hi of
 * skip_bits, in candidate order) are counted like any other, then marked
 * used so that no later stage eliminates them. */
F4_BLOCK_FN void f4_stage_fill(F4Shared *sh, f4_u32 nt, const f4_u64 *terms,
                               const f4_u32 *poly_start, f4_u64 *scratch, f4_u32 max_rows,
                               f4_u32 max_cols, const f4_u32 *skip_bits, f4_u32 skip_lo,
                               f4_u32 skip_hi)
{
    const f4_u64 *bitmap = scratch;
    const f4_u32 *prefix = (const f4_u32 *)(scratch + sh->off_prefix);
    f4_u64 *mat = scratch + sh->off_mat;
    f4_u32 *lead = (f4_u32 *)(scratch + sh->off_lead);
    f4_u32 *meta = (f4_u32 *)(scratch + sh->off_meta);
    f4_u64 *cls = scratch + sh->off_class;
    const f4_u32 stride = sh->stride;
    F4_FOR_THREADS(tid)
        f4_u32 g = 0u;
        f4_u64 rows_here = 0ull, nonempty_here = 0ull, skipped_here = 0ull;
        for (f4_u32 row = tid; row < sh->n_cand; row += nt) {
            while (row >= sh->cand_start[g + 1u]) ++g;
            f4_u32 deg;
            f4_u64 u = f4_multiplier(sh, row - sh->cand_start[g], sh->gen_k[g], &deg);
            f4_u64 *dst = mat + (f4_u64)row * stride;
            for (f4_u32 w = 0; w < stride; ++w) dst[w] = 0ull;
            f4_u32 p = sh->gen_poly[g];
            for (f4_u32 t = poly_start[p]; t < poly_start[p + 1u]; ++t) {
                f4_u32 c = f4_dense(bitmap, prefix, f4_rank(sh, terms[t] | u));
                dst[c >> 6] ^= 1ull << (c & 63u);
            }
            f4_u32 slack = sh->gen_k[g] - deg;
            f4_u32 l = f4_lead(dst, 0u, stride);
            lead[row] = l;
            meta[row] = slack | (l != F4_NONE ? 0x100u : 0u);
            if (l != F4_NONE) {
                rows_here += sh->upto[slack];
                nonempty_here += 1ull;
                f4_u32 w = row >> 5;
                if (skip_lo + w < skip_hi && ((skip_bits[skip_lo + w] >> (row & 31u)) & 1u)) {
                    meta[row] |= 0x200u;
                    skipped_here += 1ull;
                }
            }
        }
        if (rows_here) F4_ATOMIC_ADD64(&sh->ref_rows, rows_here);
        if (nonempty_here) F4_ATOMIC_ADD64(&sh->nonempty, nonempty_here);
        if (skipped_here) F4_ATOMIC_ADD64(&sh->skipped, skipped_here);
    F4_END_THREADS
    F4_SYNC();
    /* Per word: OR the nonempty rows by slack class, then count each
     * surviving monomial once per multiplier its largest slack admits. */
    F4_FOR_THREADS(tid)
        f4_u64 cols_here = 0ull;
        for (f4_u32 w = tid; w < stride; w += nt) {
            for (f4_u32 s = 0; s <= sh->degree; ++s) cls[(f4_u64)s * stride + w] = 0ull;
            for (f4_u32 row = 0; row < sh->n_cand; ++row)
                if (meta[row] & 0x100u)
                    cls[(f4_u64)(meta[row] & 0xffu) * stride + w] |= mat[(f4_u64)row * stride + w];
            f4_u64 covered = 0ull;
            for (f4_u32 s = sh->degree + 1u; s-- > 0u;) {
                f4_u64 m = cls[(f4_u64)s * stride + w];
                cols_here += (f4_u64)F4_POPC(m & ~covered) * sh->upto[s];
                covered |= m;
            }
        }
        if (cols_here) F4_ATOMIC_ADD64(&sh->ref_cols, cols_here);
    F4_END_THREADS
    F4_SYNC();
    F4_SINGLE
    {
        if (sh->nonempty == 0ull)
            sh->status = F4_STATUS_EMPTY;
        else if (sh->ref_rows > (f4_u64)max_rows || sh->ref_cols > (f4_u64)max_cols)
            sh->status = F4_STATUS_OVERSIZE;
        sh->best[0] = ~0ull;
        sh->best[1] = ~0ull;
        sh->best[2] = ~0ull;
    }
    F4_SYNC();
}

/* Stage 4: forward elimination over the high columns.  Each round takes
 * the unused row with the smallest (leading column, index) as the pivot, so
 * columns without a pivot cost nothing, and clears that column from every
 * other unused row that leads there. */
F4_BLOCK_FN void f4_stage_echelon(F4Shared *sh, f4_u32 nt, f4_u64 *scratch)
{
    f4_u64 *mat = scratch + sh->off_mat;
    f4_u32 *lead = (f4_u32 *)(scratch + sh->off_lead);
    f4_u32 *meta = (f4_u32 *)(scratch + sh->off_meta);
    const f4_u32 stride = sh->stride;
    for (f4_u32 round = 0;; ++round) {
        f4_u32 slot = round % 3u;
        F4_FOR_THREADS(tid)
            if (tid == 0u) sh->best[(slot + 1u) % 3u] = ~0ull;
            f4_u64 mine = ~0ull;
            for (f4_u32 row = tid; row < sh->n_cand; row += nt) {
                f4_u32 l = lead[row];
                if (!(meta[row] & 0x200u) && l < sh->low_start) {
                    f4_u64 key = ((f4_u64)l << 32) | row;
                    mine = key < mine ? key : mine;
                }
            }
            if (mine != ~0ull) F4_ATOMIC_MIN64(&sh->best[slot], mine);
        F4_END_THREADS
        F4_SYNC();
        f4_u64 best = sh->best[slot];
        if (best == ~0ull) break;
        const f4_u32 prow = (f4_u32)(best & 0xffffffffull);
        const f4_u32 pcol = (f4_u32)(best >> 32);
        const f4_u32 from = pcol >> 6;
        F4_FOR_THREADS(tid)
            f4_u64 ops_here = 0ull;
            for (f4_u32 row = tid; row < sh->n_cand; row += nt) {
                if (row == prow) {
                    meta[row] |= 0x200u;
                    continue;
                }
                if ((meta[row] & 0x200u) || lead[row] != pcol) continue;
                f4_u64 *dst = mat + (f4_u64)row * stride;
                const f4_u64 *src = mat + (f4_u64)prow * stride;
                for (f4_u32 w = from; w < stride; ++w) dst[w] ^= src[w];
                ops_here += stride - from;
                lead[row] = f4_lead(dst, from, stride);
            }
            if (ops_here) F4_ATOMIC_ADD64(&sh->word_ops, ops_here);
        F4_END_THREADS
        F4_SYNC();
    }
}

/* Stage 5: gather the rows left in the linear block and reduce them;
 * read off the refutation and the forced variables. */
F4_BLOCK_FN void f4_stage_linear(F4Shared *sh, f4_u32 nt, f4_u64 *scratch, F4Result *out)
{
    const f4_u64 *mat = scratch + sh->off_mat;
    const f4_u32 *lead = (const f4_u32 *)(scratch + sh->off_lead);
    const f4_u32 *meta = (const f4_u32 *)(scratch + sh->off_meta);
    f4_u64 *low = scratch + sh->off_low;
    f4_u32 *lmeta = (f4_u32 *)(scratch + sh->off_lmeta);
    const f4_u32 stride = sh->stride, start = sh->low_start, width = sh->low_width;
    F4_FOR_THREADS(tid)
        for (f4_u32 row = tid; row < sh->n_cand; row += nt) {
            if ((meta[row] & 0x200u) || lead[row] == F4_NONE) continue;
            f4_u64 lo = 0ull, hi = 0ull;
            for (f4_u32 j = 0; j < width; ++j) {
                f4_u32 c = start + j;
                if ((mat[(f4_u64)row * stride + (c >> 6)] >> (c & 63u)) & 1ull) {
                    if (j < 64u)
                        lo |= 1ull << j;
                    else
                        hi |= 1ull << (j - 64u);
                }
            }
            f4_u32 at = F4_ATOMIC_ADD32(&sh->n_low, 1u);
            low[2u * at] = lo;
            low[2u * at + 1u] = hi;
            lmeta[at] = 0u;
        }
    F4_END_THREADS
    F4_SYNC();
    F4_SINGLE
    {
        sh->lrank = 0u;
        sh->best[0] = ~0ull;
        sh->best[1] = ~0ull;
        sh->best[2] = ~0ull;
    }
    F4_SYNC();
    for (f4_u32 col = 0; col < width; ++col) {
        f4_u32 slot = col % 3u;
        F4_FOR_THREADS(tid)
            if (tid == 0u) sh->best[(slot + 1u) % 3u] = ~0ull;
            f4_u64 mine = ~0ull;
            for (f4_u32 i = tid; i < sh->n_low; i += nt) {
                f4_u64 word = col < 64u ? low[2u * i] : low[2u * i + 1u];
                if (!lmeta[i] && ((word >> (col & 63u)) & 1ull))
                    mine = (f4_u64)i < mine ? (f4_u64)i : mine;
            }
            if (mine != ~0ull) F4_ATOMIC_MIN64(&sh->best[slot], mine);
        F4_END_THREADS
        F4_SYNC();
        f4_u64 best = sh->best[slot];
        if (best == ~0ull) continue;
        const f4_u32 piv = (f4_u32)best;
        F4_FOR_THREADS(tid)
            if (tid == 0u) {
                sh->lpivot[sh->lrank] = piv;
                sh->lrank += 1u;
            }
            for (f4_u32 i = tid; i < sh->n_low; i += nt) {
                if (i == piv) {
                    lmeta[i] = 1u;
                    continue;
                }
                f4_u64 word = col < 64u ? low[2u * i] : low[2u * i + 1u];
                if ((word >> (col & 63u)) & 1ull) {
                    low[2u * i] ^= low[2u * piv];
                    low[2u * i + 1u] ^= low[2u * piv + 1u];
                }
            }
        F4_END_THREADS
        F4_SYNC();
    }
    F4_SINGLE
    {
        f4_u32 refuted = 0u;
        f4_u64 fmask = 0ull, fvals = 0ull;
        f4_u32 cbit = sh->const_present ? width - 1u : F4_NONE;
        for (f4_u32 k = 0; k < sh->lrank; ++k) {
            f4_u32 i = sh->lpivot[k];
            f4_u64 lo = low[2u * i], hi = low[2u * i + 1u];
            f4_u32 has_const = 0u;
            if (cbit != F4_NONE) {
                if (cbit < 64u) {
                    has_const = (f4_u32)((lo >> cbit) & 1ull);
                    lo &= ~(1ull << cbit);
                } else {
                    has_const = (f4_u32)((hi >> (cbit - 64u)) & 1ull);
                    hi &= ~(1ull << (cbit - 64u));
                }
            }
            f4_u32 nvars = F4_POPC(lo) + F4_POPC(hi);
            if (nvars == 0u && has_const) {
                refuted = 1u;
            } else if (nvars == 1u) {
                f4_u32 j = lo ? F4_CTZ(lo) : 64u + F4_CTZ(hi);
                f4_u32 var = sh->low_var[j];
                fmask |= 1ull << var;
                if (has_const) fvals |= 1ull << var;
            }
        }
        out->refuted = refuted;
        out->forced_mask = refuted ? 0ull : fmask;
        out->forced_vals = refuted ? 0ull : fvals;
    }
    F4_SYNC();
}

/* Decide system `sys` with the calling block. */
F4_BLOCK_FN void f4_decide_system(F4Shared *sh, f4_u32 nt, const f4_u64 *terms,
                                  const f4_u32 *poly_start, const f4_u32 *sys_poly_start,
                                  const f4_u32 *sys_meta, const f4_u32 *skip_bits,
                                  const f4_u32 *skip_start, f4_u32 sys, f4_u32 max_rows,
                                  f4_u32 max_cols, f4_u64 *scratch, f4_u64 scratch_words,
                                  F4Result *out)
{
    f4_stage_layout(sh, nt, terms, poly_start, sys_poly_start, sys_meta, sys, scratch_words);
    if (sh->status == F4_STATUS_DECIDED)
        f4_stage_columns(sh, nt, terms, poly_start, scratch, scratch_words);
    if (sh->status == F4_STATUS_DECIDED)
        f4_stage_fill(sh, nt, terms, poly_start, scratch, max_rows, max_cols, skip_bits,
                      skip_start[sys], skip_start[sys + 1u]);
    if (sh->status == F4_STATUS_DECIDED) f4_stage_echelon(sh, nt, scratch);
    F4_SINGLE
    {
        out->status = sh->status;
        out->refuted = 0u;
        out->forced_mask = 0ull;
        out->forced_vals = 0ull;
        out->ref_rows = sh->status == F4_STATUS_DECIDED || sh->status == F4_STATUS_OVERSIZE
                            ? sh->ref_rows
                            : 0ull;
        out->ref_cols = sh->status == F4_STATUS_DECIDED || sh->status == F4_STATUS_OVERSIZE
                            ? sh->ref_cols
                            : 0ull;
        out->word_ops = sh->word_ops;
        out->rows = sh->status == F4_STATUS_DECIDED ? (f4_u32)(sh->nonempty - sh->skipped) : 0u;
        out->cols = sh->status == F4_STATUS_DECIDED ? sh->n_cols : 0u;
        out->f5_skipped = sh->status == F4_STATUS_DECIDED ? (f4_u32)sh->skipped : 0u;
        out->reserved = 0u;
    }
    F4_SYNC();
    if (sh->status == F4_STATUS_DECIDED) f4_stage_linear(sh, nt, scratch, out);
}

#endif /* F4_GF2_DEVICE_CUH */
