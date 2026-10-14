/*
 * linalg.c - structured Gaussian elimination + Lanczos modulo a prime.
 */
#include "linalg.h"
#include "ca_internal.h"

/* ---- sparse matrix ------------------------------------------------------ */

ca_status ca_spmat_init(ca_spmat *m, uint32_t cols, uint32_t expected_rows, uint32_t expected_nnz)
{
    memset(m, 0, sizeof(*m));
    m->cols = cols;
    m->row_cap = (size_t)expected_rows + 1;
    m->row_ptr = malloc(m->row_cap * sizeof(uint32_t));
    m->cap = expected_nnz ? expected_nnz : 1024;
    m->col = malloc(m->cap * sizeof(uint32_t));
    m->val = malloc(m->cap * sizeof(int32_t));
    if (!m->row_ptr || !m->col || !m->val) { ca_spmat_free(m); return CA_ERR_NOMEM; }
    m->row_ptr[0] = 0;
    m->rows = 0;
    m->nnz = 0;
    return CA_OK;
}

void ca_spmat_free(ca_spmat *m)
{
    free(m->row_ptr);
    free(m->col);
    free(m->val);
    memset(m, 0, sizeof(*m));
}

ca_status ca_spmat_add_row(ca_spmat *m, const uint32_t *cols, const int32_t *vals, uint32_t n)
{
    /* row_ptr needs rows + 2 slots once this row is appended.  The capacity
     * is per matrix: expected_rows at init is a hint, not a limit, and a
     * matrix must never grow into another matrix's bookkeeping. */
    size_t need = (size_t)m->rows + 2;
    if (m->row_cap < need) {
        size_t ncap = m->row_cap ? m->row_cap : 1024;
        while (ncap < need) ncap *= 2;
        uint32_t *np = realloc(m->row_ptr, ncap * sizeof(uint32_t));
        if (!np) return CA_ERR_NOMEM;
        m->row_ptr = np;
        m->row_cap = ncap;
    }
    if ((size_t)m->nnz + n > m->cap) {
        uint32_t ncap = m->cap;
        while ((size_t)m->nnz + n > ncap) ncap *= 2;
        uint32_t *nc = realloc(m->col, ncap * sizeof(uint32_t));
        if (!nc) return CA_ERR_NOMEM;
        m->col = nc;
        int32_t *nv = realloc(m->val, ncap * sizeof(int32_t));
        if (!nv) return CA_ERR_NOMEM;
        m->val = nv;
        m->cap = ncap;
    }
    uint32_t start = m->nnz;
    for (uint32_t i = 0; i < n; i++) {
        if (vals[i] == 0) continue;
        int merged = 0;
        for (uint32_t k = start; k < m->nnz; k++) {
            if (m->col[k] == cols[i]) { m->val[k] += vals[i]; merged = 1; break; }
        }
        if (!merged) {
            m->col[m->nnz] = cols[i];
            m->val[m->nnz] = vals[i];
            m->nnz++;
        }
    }
    /* drop zeros produced by merging */
    uint32_t w = start;
    for (uint32_t k = start; k < m->nnz; k++) {
        if (m->val[k] != 0) { m->col[w] = m->col[k]; m->val[w] = m->val[k]; w++; }
    }
    m->nnz = w;
    m->rows++;
    m->row_ptr[m->rows] = m->nnz;
    return CA_OK;
}

/* ---- multiplication by a fixed factor (Shoup) --------------------------- */

/* For a fixed w < q < 2^63, wp = floor(w * 2^64 / q) turns a * w mod q into
 * two multiplications and one conditional subtraction, for any a < 2^64:
 * a*w - floor(a*wp / 2^64)*q lies in [0, 2q) (Shoup; Harvey 2014).  The
 * result equals ca_mulmod(a, w, q). */
static inline uint64_t shoup_pre(uint64_t w, uint64_t q)
{
    return (uint64_t)(((ca_u128)w << 64) / q);
}

static inline uint64_t shoup_mul(uint64_t a, uint64_t w, uint64_t wp, uint64_t q)
{
    uint64_t qhat = (uint64_t)(((ca_u128)a * wp) >> 64);
    uint64_t r = a * w - qhat * q;
    return r >= q ? r - q : r;
}

/* ---- dense elimination -------------------------------------------------- */

ca_status ca_dense_solve_mod_prime(uint64_t *M, uint32_t n, uint64_t *rhs, uint64_t q, uint64_t *x)
{
#define A(i, j) M[(size_t)(i) * n + (j)]
    /* Reduce once: every entry the elimination writes is already in
     * [0, q), so the per-access % q of the loops below had nothing left to
     * do after the first touch.  Below 2^63 each row update multiplies by
     * a fixed factor, which Shoup's precomputation makes division-free. */
    for (size_t k = 0; k < (size_t)n * n; k++) M[k] %= q;
    for (uint32_t i = 0; i < n; i++) rhs[i] %= q;
    const int shoup = q < ((uint64_t)1 << 63);
    for (uint32_t c = 0; c < n; c++) {
        uint32_t piv = c;
        while (piv < n && A(piv, c) == 0) piv++;
        if (piv == n) return CA_ERR_SINGULAR;
        if (piv != c) {
            for (uint32_t j = 0; j < n; j++) { uint64_t t = A(c, j); A(c, j) = A(piv, j); A(piv, j) = t; }
            uint64_t t = rhs[c]; rhs[c] = rhs[piv]; rhs[piv] = t;
        }
        uint64_t inv = ca_invmod(A(c, c), q);
        for (uint32_t j = c; j < n; j++) A(c, j) = ca_mulmod(A(c, j), inv, q);
        rhs[c] = ca_mulmod(rhs[c], inv, q);
        for (uint32_t i = 0; i < n; i++) {
            if (i == c) continue;
            uint64_t f = A(i, c);
            if (!f) continue;
            if (shoup) {
                uint64_t fp = shoup_pre(f, q);
                for (uint32_t j = c; j < n; j++)
                    A(i, j) = ca_submod(A(i, j), shoup_mul(A(c, j), f, fp, q), q);
                rhs[i] = ca_submod(rhs[i], shoup_mul(rhs[c], f, fp, q), q);
            } else {
                for (uint32_t j = c; j < n; j++)
                    A(i, j) = ca_submod(A(i, j), ca_mulmod(f, A(c, j), q), q);
                rhs[i] = ca_submod(rhs[i], ca_mulmod(f, rhs[c], q), q);
            }
        }
    }
    for (uint32_t i = 0; i < n; i++) x[i] = rhs[i];
#undef A
    return CA_OK;
}

/* ---- modular vector helpers ------------------------------------------- */

/* small signed coefficient reduced into [0, q) */
static inline uint64_t coef_mod(int64_t v, uint64_t q)
{
    if (v >= 0) return (uint64_t)v % q;
    uint64_t m = (uint64_t)(-v) % q;
    return m ? q - m : 0;
}

/* sum a[i] b[i] (mod q): products below 2^128 are summed exactly in three
 * words and reduced once, instead of a 128-bit % every fourth term. */
/* sum a[i] b[i] (mod q): products below 2^128 are summed exactly in three
 * words and reduced once at the end, instead of a 128-bit % every fourth
 * term. */
static inline uint64_t vdot(const uint64_t *a, const uint64_t *b, uint32_t n, uint64_t q)
{
    ca_u128 acc = 0;
    uint64_t top = 0;
    for (uint32_t i = 0; i < n; i++) {
        ca_u128 p = (ca_u128)a[i] * b[i];
        acc += p;
        top += acc < p;
    }
    ca_u128 r = top % q;
    r = ((r << 64) | (uint64_t)(acc >> 64)) % q;
    return (uint64_t)(((r << 64) | (uint64_t)acc) % q);
}

/* v mod q for a signed 128-bit v, canonical. */
static inline uint64_t i128_mod(ca_i128 v, uint64_t q)
{
    if (v >= 0) return (uint64_t)((ca_u128)v % q);
    uint64_t m = (uint64_t)((ca_u128)(-v) % q);
    return m ? q - m : 0;
}

/* x mod q for a signed 64-bit x, canonical. */
static inline uint64_t i64_mod(int64_t x, uint64_t q)
{
    if (x >= 0) return (uint64_t)x % q;
    uint64_t m = ((uint64_t)0 - (uint64_t)x) % q;
    return m ? q - m : 0;
}

/* How y = A v (mod q) may accumulate a row, decided once per matrix:
 *   SPMV_I64   every partial row sum fits an int64_t (max|a| * (q-1) * the
 *              longest row < 2^63): one 64-bit multiply-add a term;
 *   SPMV_I128S q < 2^63, so each v fits an int64_t: one signed 64x64->128
 *              multiply a term into a 128-bit accumulator;
 *   SPMV_I128U anything else: 128x128 products.
 * All three compute the exact integer row sum, so the residue is the same. */
enum { SPMV_I64, SPMV_I128S, SPMV_I128U };

static uint64_t spmat_maxabs(const ca_spmat *A)
{
    uint64_t maxabs = 0;
    for (uint32_t k = 0; k < A->nnz; k++) {
        int64_t v = A->val[k];
        uint64_t a = (uint64_t)(v < 0 ? -v : v);
        if (a > maxabs) maxabs = a;
    }
    return maxabs;
}

/* The accumulator for sums of at most MAXLEN terms a * v, |a| <= MAXABS,
 * 0 <= v < q. */
static int sum_mode(uint64_t maxabs, uint64_t maxlen, uint64_t q)
{
    ca_u128 bound = (ca_u128)maxabs * (q - 1);
    if ((bound >> 64) == 0 && (ca_u128)(uint64_t)bound * maxlen < ((ca_u128)1 << 63)) return SPMV_I64;
    return q < ((uint64_t)1 << 63) ? SPMV_I128S : SPMV_I128U;
}

/* for A v: the sums run along rows */
static int spmv_mode(const ca_spmat *A, uint64_t q)
{
    uint32_t maxlen = 0;
    for (uint32_t i = 0; i < A->rows; i++) {
        uint32_t len = A->row_ptr[i + 1] - A->row_ptr[i];
        if (len > maxlen) maxlen = len;
    }
    return sum_mode(spmat_maxabs(A), maxlen, q);
}

/* for A^T w: the sums run down columns */
static int spmtv_mode(const ca_spmat *A, uint64_t q)
{
    uint32_t *colw = calloc(A->cols ? A->cols : 1, sizeof(uint32_t));
    if (!colw) return q < ((uint64_t)1 << 63) ? SPMV_I128S : SPMV_I128U;
    uint32_t maxlen = 0;
    for (uint32_t k = 0; k < A->nnz; k++) {
        uint32_t c = ++colw[A->col[k]];
        if (c > maxlen) maxlen = c;
    }
    free(colw);
    return sum_mode(spmat_maxabs(A), maxlen, q);
}

/* y = A v (mod q).  In the 128-bit modes each term is below 2^31 * 2^64 =
 * 2^95 in size, so 2^31 of them cannot overflow, and a row is flushed every
 * 2^30 terms regardless.  One reduction a row. */
static inline void spmv_impl(const ca_spmat *A, const uint64_t *v, uint64_t *y, uint64_t q,
                             int mode)
{
    const uint32_t *rp = A->row_ptr, *col = A->col;
    const int32_t *val = A->val;
    for (uint32_t i = 0; i < A->rows; i++) {
        uint32_t k = rp[i], end = rp[i + 1];
        if (mode == SPMV_I64) {
            int64_t acc = 0;
            for (; k < end; k++) acc += (int64_t)val[k] * (int64_t)v[col[k]];
            y[i] = i64_mod(acc, q);
            continue;
        }
        ca_i128 acc = 0;
        uint64_t r = 0;
        while (k < end) {
            uint32_t stop = end - k > (1u << 30) ? k + (1u << 30) : end;
            if (mode == SPMV_I128S) {
                /* two accumulators: long (transposed) rows otherwise wait
                 * on one add/adc chain */
                ca_i128 acc2 = 0;
                for (; k + 1 < stop; k += 2) {
                    acc += (ca_i128)(int64_t)val[k] * (int64_t)v[col[k]];
                    acc2 += (ca_i128)(int64_t)val[k + 1] * (int64_t)v[col[k + 1]];
                }
                if (k < stop) { acc += (ca_i128)(int64_t)val[k] * (int64_t)v[col[k]]; k++; }
                acc += acc2;
            } else {
                for (; k < stop; k++) acc += (ca_i128)val[k] * (ca_i128)v[col[k]];
            }
            if (k < end) {
                r = ca_addmod(r, i128_mod(acc, q), q);
                acc = 0;
            }
        }
        y[i] = ca_addmod(r, i128_mod(acc, q), q);
    }
}

static void spmv(const ca_spmat *A, const uint64_t *v, uint64_t *y, uint64_t q, int mode)
{
    switch (mode) {
    case SPMV_I64: spmv_impl(A, v, y, q, SPMV_I64); break;
    case SPMV_I128S: spmv_impl(A, v, y, q, SPMV_I128S); break;
    default: spmv_impl(A, v, y, q, SPMV_I128U); break;
    }
}

/* z = A^T w (mod q) by scattering each row into per-column accumulators.
 * MODE as for spmv, decided on A^T (column length bounds the sums).
 * acc must hold A->cols ca_i128. */
static void spmtv(const ca_spmat *A, const uint64_t *w, uint64_t *z, uint64_t q, int mode,
                  void *accbuf)
{
    const uint32_t *rp = A->row_ptr, *col = A->col;
    const int32_t *val = A->val;
    if (mode == SPMV_I64) {
        int64_t *acc = accbuf;
        memset(acc, 0, A->cols * sizeof(int64_t));
        for (uint32_t i = 0; i < A->rows; i++) {
            int64_t wi = (int64_t)w[i];
            if (!wi) continue;
            for (uint32_t k = rp[i]; k < rp[i + 1]; k++) acc[col[k]] += (int64_t)val[k] * wi;
        }
        for (uint32_t j = 0; j < A->cols; j++) z[j] = i64_mod(acc[j], q);
        return;
    }
    ca_i128 *acc = accbuf;
    memset(acc, 0, A->cols * sizeof(ca_i128));
    for (uint32_t i = 0; i < A->rows; i++) {
        uint64_t wi = w[i];
        if (!wi) continue;
        if (mode == SPMV_I128S) {
            for (uint32_t k = rp[i]; k < rp[i + 1]; k++)
                acc[col[k]] += (ca_i128)(int64_t)val[k] * (int64_t)wi;
        } else {
            for (uint32_t k = rp[i]; k < rp[i + 1]; k++)
                acc[col[k]] += (ca_i128)val[k] * (ca_i128)wi;
        }
    }
    for (uint32_t j = 0; j < A->cols; j++) z[j] = i128_mod(acc[j], q);
}

/*
 * Lanczos on B = A^T D A with random diagonal D, solving B x = A^T D b.
 * Returns CA_OK if A x == b verified, CA_ERR_SINGULAR on breakdown.
 */
static ca_status lanczos(const ca_spmat *A, const uint64_t *b, uint64_t q, uint64_t *x,
                         ca_rng *rng, uint32_t *iters_out)
{
    uint32_t n = A->cols, m = A->rows;
    uint64_t *D = malloc(m * sizeof(uint64_t));
    uint64_t *Dp = malloc(m * sizeof(uint64_t)); /* Shoup constants of D */
    const int shoup = q < ((uint64_t)1 << 63);
    uint64_t *tmp_m = malloc(m * sizeof(uint64_t));
    uint64_t *bp = malloc(n * sizeof(uint64_t));      /* A^T D b */
    uint64_t *w0 = calloc(n, sizeof(uint64_t));
    uint64_t *w1 = calloc(n, sizeof(uint64_t));
    uint64_t *w2 = calloc(n, sizeof(uint64_t));
    uint64_t *Bw = calloc(n, sizeof(uint64_t));
    void *accbuf = NULL;
    const int mode_a = spmv_mode(A, q);
    int mode_t = SPMV_I128U;
    ca_status rc = CA_ERR_SINGULAR;
    if (!D || !Dp || !tmp_m || !bp || !w0 || !w1 || !w2 || !Bw) {
        rc = CA_ERR_NOMEM;
        goto out;
    }
    mode_t = spmtv_mode(A, q);
    accbuf = malloc((n ? n : 1) * sizeof(ca_i128));
    if (!accbuf) { rc = CA_ERR_NOMEM; goto out; }
    for (uint32_t i = 0; i < m; i++) {
        D[i] = 1 + ca_rng_below(rng, q - 1);
        Dp[i] = shoup ? shoup_pre(D[i], q) : 0;
    }
    for (uint32_t i = 0; i < m; i++) tmp_m[i] = ca_mulmod(D[i], b[i] % q, q);
    spmtv(A, tmp_m, bp, q, mode_t, accbuf);
    memset(x, 0, n * sizeof(uint64_t));
    /* w_prev = w0 (i-1), w_cur = w1 (i) */
    uint64_t *w_prev = w0, *w_cur = w1, *w_next = w2;
    memcpy(w_cur, bp, n * sizeof(uint64_t));
    uint64_t prev_wBw = 0;
    uint32_t it = 0;
    for (it = 0; it < n + 8; it++) {
        /* Bw = A^T D A w_cur */
        spmv(A, w_cur, tmp_m, q, mode_a);
        if (shoup) {
            for (uint32_t i = 0; i < m; i++) tmp_m[i] = shoup_mul(tmp_m[i], D[i], Dp[i], q);
        } else {
            for (uint32_t i = 0; i < m; i++) tmp_m[i] = ca_mulmod(tmp_m[i], D[i], q);
        }
        spmtv(A, tmp_m, Bw, q, mode_t, accbuf);
        uint64_t wBw = vdot(w_cur, Bw, n, q);
        int zero = 1;
        for (uint32_t j = 0; j < n; j++) if (w_cur[j]) { zero = 0; break; }
        if (zero) { rc = CA_OK; break; }
        if (wBw == 0) { rc = CA_ERR_SINGULAR; break; } /* breakdown */
        uint64_t inv = ca_invmod(wBw, q);
        /* x += (w . bp) / (w . Bw) * w */
        uint64_t coef = ca_mulmod(vdot(w_cur, bp, n, q), inv, q);
        /* w_next = Bw - c1 w_cur - c2 w_prev */
        uint64_t c1 = ca_mulmod(vdot(Bw, Bw, n, q), inv, q);
        uint64_t c2 = prev_wBw ? ca_mulmod(wBw, ca_invmod(prev_wBw, q), q) : 0;
        if (shoup) {
            /* coef, c1 and c2 are fixed for the whole vector update */
            const uint64_t coefp = shoup_pre(coef, q), c1p = shoup_pre(c1, q),
                           c2p = shoup_pre(c2, q);
            for (uint32_t j = 0; j < n; j++)
                x[j] = ca_addmod(x[j], shoup_mul(w_cur[j], coef, coefp, q), q);
            for (uint32_t j = 0; j < n; j++) {
                uint64_t t = ca_submod(Bw[j], shoup_mul(w_cur[j], c1, c1p, q), q);
                if (c2) t = ca_submod(t, shoup_mul(w_prev[j], c2, c2p, q), q);
                w_next[j] = t;
            }
        } else {
            for (uint32_t j = 0; j < n; j++)
                x[j] = ca_addmod(x[j], ca_mulmod(coef, w_cur[j], q), q);
            for (uint32_t j = 0; j < n; j++) {
                uint64_t t = ca_submod(Bw[j], ca_mulmod(c1, w_cur[j], q), q);
                if (c2) t = ca_submod(t, ca_mulmod(c2, w_prev[j], q), q);
                w_next[j] = t;
            }
        }
        prev_wBw = wBw;
        uint64_t *t = w_prev; w_prev = w_cur; w_cur = w_next; w_next = t;
    }
    if (rc == CA_OK) {
        /* verify A x == b */
        spmv(A, x, tmp_m, q, mode_a);
        for (uint32_t i = 0; i < m; i++) {
            if (tmp_m[i] != b[i] % q) { rc = CA_ERR_SINGULAR; break; }
        }
    }
    if (iters_out) *iters_out = it;
out:
    free(D);
    free(Dp);
    free(tmp_m);
    free(bp);
    free(w0);
    free(w1);
    free(w2);
    free(Bw);
    free(accbuf);
    return rc;
}

/* ---- structured elimination + driver ----------------------------------- */

ca_status ca_linsolve_mod_prime(const ca_spmat *A, const uint64_t *b, uint64_t q, uint64_t *x,
                                uint8_t *known, uint64_t seed, ca_linsolve_report *rep)
{
    double t0 = ca_now();
    uint32_t R = A->rows, C = A->cols;
    ca_linsolve_report lrep = {0};
    uint8_t *row_alive = malloc(R);
    uint8_t *col_alive = malloc(C);
    uint32_t *colw = calloc(C, sizeof(uint32_t));
    uint32_t *stack = malloc(R * sizeof(uint32_t)); /* dropped singleton rows in order */
    uint32_t *stack_col = malloc(R * sizeof(uint32_t));
    uint32_t nstack = 0;
    ca_status rc = CA_OK;
    if (!row_alive || !col_alive || !colw || !stack || !stack_col) { rc = CA_ERR_NOMEM; goto out; }
    memset(row_alive, 1, R);
    memset(col_alive, 1, C);
    memset(known, 0, C);
    memset(x, 0, C * sizeof(uint64_t));
    ca_rng rng;
    ca_rng_seed(&rng, ca_seed_or_random(seed));

    uint32_t maxlen = 0; /* longest row: bounds the per-row scratch below */
    for (uint32_t i = 0; i < R; i++) {
        uint32_t len = A->row_ptr[i + 1] - A->row_ptr[i];
        if (len > maxlen) maxlen = len;
        for (uint32_t k = A->row_ptr[i]; k < A->row_ptr[i + 1]; k++) colw[A->col[k]]++;
    }
    /* iterate singleton removal to a fixed point */
    int changed = 1;
    while (changed) {
        changed = 0;
        for (uint32_t i = 0; i < R; i++) {
            if (!row_alive[i]) continue;
            for (uint32_t k = A->row_ptr[i]; k < A->row_ptr[i + 1]; k++) {
                uint32_t j = A->col[k];
                if (col_alive[j] && colw[j] == 1) {
                    /* row i is the only row containing j: remove both, and
                     * solve for j later by back substitution */
                    row_alive[i] = 0;
                    col_alive[j] = 0;
                    stack[nstack] = i;
                    stack_col[nstack] = j;
                    nstack++;
                    for (uint32_t k2 = A->row_ptr[i]; k2 < A->row_ptr[i + 1]; k2++) colw[A->col[k2]]--;
                    changed = 1;
                    break;
                }
            }
        }
    }
    for (uint32_t j = 0; j < C; j++) if (colw[j] == 0) col_alive[j] = 0;

    /* build the reduced system */
    uint32_t *cmap = malloc(C * sizeof(uint32_t));
    uint32_t nc = 0;
    if (!cmap) { rc = CA_ERR_NOMEM; goto out; }
    for (uint32_t j = 0; j < C; j++) cmap[j] = col_alive[j] ? nc++ : UINT32_MAX;
    ca_spmat Ared;
    uint32_t nr = 0;
    for (uint32_t i = 0; i < R; i++) nr += row_alive[i];
    if (ca_spmat_init(&Ared, nc, nr, A->nnz) != CA_OK) { free(cmap); rc = CA_ERR_NOMEM; goto out; }
    uint64_t *bred = malloc((nr ? nr : 1) * sizeof(uint64_t));
    uint32_t *tc = malloc((maxlen ? maxlen : 1) * sizeof(uint32_t));
    int32_t *tv = malloc((maxlen ? maxlen : 1) * sizeof(int32_t));
    uint64_t *xred = calloc(nc ? nc : 1, sizeof(uint64_t));
    if (!bred || !tc || !tv || !xred) { rc = CA_ERR_NOMEM; goto out2; }
    {
        uint32_t ri = 0;
        for (uint32_t i = 0; i < R; i++) {
            if (!row_alive[i]) continue;
            uint32_t n = 0;
            for (uint32_t k = A->row_ptr[i]; k < A->row_ptr[i + 1]; k++) {
                if (cmap[A->col[k]] == UINT32_MAX) continue; /* cannot happen: dropped cols only in dropped rows */
                /* n < maxlen by construction; checked anyway so an
                 * inconsistent row_ptr cannot run off the scratch row. */
                if (n >= maxlen) {
                    rc = CA_ERR_INTERNAL;
                    goto out2;
                }
                tc[n] = cmap[A->col[k]];
                tv[n] = A->val[k];
                n++;
            }
            if (n == 0) continue;
            if (ca_spmat_add_row(&Ared, tc, tv, n) != CA_OK) { rc = CA_ERR_NOMEM; goto out2; }
            bred[ri++] = b[i] % q;
        }
        nr = ri;
    }
    lrep.active_rows = nr;
    lrep.active_cols = nc;
    if (nc > 0) {
        if (nr < nc) { rc = CA_ERR_SINGULAR; goto out2; }
        rc = CA_ERR_SINGULAR;
        for (int attempt = 0; attempt < 4 && rc != CA_OK; attempt++) {
            lrep.attempts++;
            rc = lanczos(&Ared, bred, q, xred, &rng, &lrep.lanczos_iters);
            if (rc == CA_ERR_NOMEM) goto out2;
        }
        if (rc != CA_OK && nc <= 1200) {
            /* dense fallback on the normal equations */
            lrep.used_dense = 1;
            uint64_t *M = calloc((size_t)nc * nc, sizeof(uint64_t));
            uint64_t *rhs = calloc(nc, sizeof(uint64_t));
            if (M && rhs) {
                /* M = A^T A, rhs = A^T b (mod q) */
                for (uint32_t i = 0; i < Ared.rows; i++) {
                    for (uint32_t k = Ared.row_ptr[i]; k < Ared.row_ptr[i + 1]; k++) {
                        uint64_t a = coef_mod(Ared.val[k], q);
                        uint32_t ja = Ared.col[k];
                        for (uint32_t l = Ared.row_ptr[i]; l < Ared.row_ptr[i + 1]; l++) {
                            uint64_t c = coef_mod(Ared.val[l], q);
                            M[(size_t)ja * nc + Ared.col[l]] =
                                ca_addmod(M[(size_t)ja * nc + Ared.col[l]], ca_mulmod(a, c, q), q);
                        }
                        rhs[ja] = ca_addmod(rhs[ja], ca_mulmod(a, bred[i], q), q);
                    }
                }
                rc = ca_dense_solve_mod_prime(M, nc, rhs, q, xred);
            } else rc = CA_ERR_NOMEM;
            free(M); free(rhs);
        }
        if (rc != CA_OK) goto out2;
    } else rc = CA_OK;
    for (uint32_t j = 0; j < C; j++) {
        if (cmap[j] != UINT32_MAX) { x[j] = xred[cmap[j]]; known[j] = 1; }
    }
    /* back-substitute singleton rows in reverse order */
    for (uint32_t s = nstack; s-- > 0;) {
        uint32_t i = stack[s], j = stack_col[s];
        uint64_t acc = b[i] % q;
        int64_t coef_j = 0;
        int ok = 1;
        for (uint32_t k = A->row_ptr[i]; k < A->row_ptr[i + 1]; k++) {
            uint32_t jj = A->col[k];
            if (jj == j) { coef_j = A->val[k]; continue; }
            if (!known[jj]) { ok = 0; break; }
            uint64_t c = coef_mod(A->val[k], q);
            acc = ca_submod(acc, ca_mulmod(c, x[jj], q), q);
        }
        if (!ok || coef_j == 0) continue;
        uint64_t cj = coef_mod(coef_j, q);
        uint64_t inv = ca_invmod(cj, q);
        if (!inv) continue;
        x[j] = ca_mulmod(acc, inv, q);
        known[j] = 1;
    }
out2:
    ca_spmat_free(&Ared);
    free(bred); free(tc); free(tv); free(xred); free(cmap);
out:
    free(row_alive); free(col_alive); free(colw); free(stack); free(stack_col);
    lrep.seconds = ca_now() - t0;
    if (rep) *rep = lrep;
    return rc;
}
