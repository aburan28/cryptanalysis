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

/* ---- dense elimination -------------------------------------------------- */

ca_status ca_dense_solve_mod_prime(uint64_t *M, uint32_t n, uint64_t *rhs, uint64_t q, uint64_t *x)
{
#define A(i, j) M[(size_t)(i) * n + (j)]
    for (uint32_t c = 0; c < n; c++) {
        uint32_t piv = c;
        while (piv < n && A(piv, c) % q == 0) piv++;
        if (piv == n) return CA_ERR_SINGULAR;
        if (piv != c) {
            for (uint32_t j = 0; j < n; j++) { uint64_t t = A(c, j); A(c, j) = A(piv, j); A(piv, j) = t; }
            uint64_t t = rhs[c]; rhs[c] = rhs[piv]; rhs[piv] = t;
        }
        uint64_t inv = ca_invmod(A(c, c) % q, q);
        for (uint32_t j = c; j < n; j++) A(c, j) = ca_mulmod(A(c, j) % q, inv, q);
        rhs[c] = ca_mulmod(rhs[c] % q, inv, q);
        for (uint32_t i = 0; i < n; i++) {
            if (i == c) continue;
            uint64_t f = A(i, c) % q;
            if (!f) continue;
            for (uint32_t j = c; j < n; j++)
                A(i, j) = ca_submod(A(i, j) % q, ca_mulmod(f, A(c, j), q), q);
            rhs[i] = ca_submod(rhs[i] % q, ca_mulmod(f, rhs[c], q), q);
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

static inline uint64_t vdot(const uint64_t *a, const uint64_t *b, uint32_t n, uint64_t q)
{
    /* each product < 2^128; four of them fit in 128 bits only if q < 2^62 */
    ca_u128 acc = 0;
    uint64_t r = 0;
    uint32_t chunk_mask = (q >> 62) ? 0u : 3u;
    for (uint32_t i = 0; i < n; i++) {
        acc += (ca_u128)a[i] * b[i];
        if ((i & chunk_mask) == chunk_mask || i + 1 == n) { r = ca_addmod(r, (uint64_t)(acc % q), q); acc = 0; }
    }
    return r;
}

/* y = A v (mod q) using 128-bit accumulation; entries |val| < 2^31 */
static void spmv(const ca_spmat *A, const uint64_t *v, uint64_t *y, uint64_t q)
{
    for (uint32_t i = 0; i < A->rows; i++) {
        ca_u128 pos = 0, neg = 0;
        uint32_t cnt = 0;
        uint64_t rp = 0, rn = 0;
        for (uint32_t k = A->row_ptr[i]; k < A->row_ptr[i + 1]; k++) {
            int32_t c = A->val[k];
            if (c > 0) pos += (ca_u128)(uint32_t)c * v[A->col[k]];
            else neg += (ca_u128)(uint32_t)(-c) * v[A->col[k]];
            if (++cnt == 1u << 30) { /* never in practice */
                rp = ca_addmod(rp, (uint64_t)(pos % q), q); pos = 0;
                rn = ca_addmod(rn, (uint64_t)(neg % q), q); neg = 0;
                cnt = 0;
            }
        }
        rp = ca_addmod(rp, (uint64_t)(pos % q), q);
        rn = ca_addmod(rn, (uint64_t)(neg % q), q);
        y[i] = ca_submod(rp, rn, q);
    }
}

/* z = A^T w (mod q) */
static void spmtv(const ca_spmat *A, const uint64_t *w, uint64_t *z, uint64_t q, ca_u128 *accp,
                  ca_u128 *accn)
{
    memset(accp, 0, A->cols * sizeof(ca_u128));
    memset(accn, 0, A->cols * sizeof(ca_u128));
    /* each term < 2^31 * 2^64 = 2^95; up to 2^33 terms per column fit */
    for (uint32_t i = 0; i < A->rows; i++) {
        uint64_t wi = w[i];
        if (!wi) continue;
        for (uint32_t k = A->row_ptr[i]; k < A->row_ptr[i + 1]; k++) {
            int32_t c = A->val[k];
            if (c > 0) accp[A->col[k]] += (ca_u128)(uint32_t)c * wi;
            else accn[A->col[k]] += (ca_u128)(uint32_t)(-c) * wi;
        }
    }
    for (uint32_t j = 0; j < A->cols; j++)
        z[j] = ca_submod((uint64_t)(accp[j] % q), (uint64_t)(accn[j] % q), q);
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
    uint64_t *tmp_m = malloc(m * sizeof(uint64_t));
    uint64_t *bp = malloc(n * sizeof(uint64_t));      /* A^T D b */
    uint64_t *w0 = calloc(n, sizeof(uint64_t));
    uint64_t *w1 = calloc(n, sizeof(uint64_t));
    uint64_t *w2 = calloc(n, sizeof(uint64_t));
    uint64_t *Bw = calloc(n, sizeof(uint64_t));
    ca_u128 *accp = malloc(n * sizeof(ca_u128));
    ca_u128 *accn = malloc(n * sizeof(ca_u128));
    ca_status rc = CA_ERR_SINGULAR;
    if (!D || !tmp_m || !bp || !w0 || !w1 || !w2 || !Bw || !accp || !accn) { rc = CA_ERR_NOMEM; goto out; }
    for (uint32_t i = 0; i < m; i++) D[i] = 1 + ca_rng_below(rng, q - 1);
    for (uint32_t i = 0; i < m; i++) tmp_m[i] = ca_mulmod(D[i], b[i] % q, q);
    spmtv(A, tmp_m, bp, q, accp, accn);
    memset(x, 0, n * sizeof(uint64_t));
    /* w_prev = w0 (i-1), w_cur = w1 (i) */
    uint64_t *w_prev = w0, *w_cur = w1, *w_next = w2;
    memcpy(w_cur, bp, n * sizeof(uint64_t));
    uint64_t prev_wBw = 0;
    uint32_t it = 0;
    for (it = 0; it < n + 8; it++) {
        /* Bw = A^T D A w_cur */
        spmv(A, w_cur, tmp_m, q);
        for (uint32_t i = 0; i < m; i++) tmp_m[i] = ca_mulmod(tmp_m[i], D[i], q);
        spmtv(A, tmp_m, Bw, q, accp, accn);
        uint64_t wBw = vdot(w_cur, Bw, n, q);
        int zero = 1;
        for (uint32_t j = 0; j < n; j++) if (w_cur[j]) { zero = 0; break; }
        if (zero) { rc = CA_OK; break; }
        if (wBw == 0) { rc = CA_ERR_SINGULAR; break; } /* breakdown */
        uint64_t inv = ca_invmod(wBw, q);
        /* x += (w . bp) / (w . Bw) * w */
        uint64_t coef = ca_mulmod(vdot(w_cur, bp, n, q), inv, q);
        for (uint32_t j = 0; j < n; j++) x[j] = ca_addmod(x[j], ca_mulmod(coef, w_cur[j], q), q);
        /* w_next = Bw - c1 w_cur - c2 w_prev */
        uint64_t c1 = ca_mulmod(vdot(Bw, Bw, n, q), inv, q);
        uint64_t c2 = prev_wBw ? ca_mulmod(wBw, ca_invmod(prev_wBw, q), q) : 0;
        for (uint32_t j = 0; j < n; j++) {
            uint64_t t = ca_submod(Bw[j], ca_mulmod(c1, w_cur[j], q), q);
            if (c2) t = ca_submod(t, ca_mulmod(c2, w_prev[j], q), q);
            w_next[j] = t;
        }
        prev_wBw = wBw;
        uint64_t *t = w_prev; w_prev = w_cur; w_cur = w_next; w_next = t;
    }
    if (rc == CA_OK) {
        /* verify A x == b */
        spmv(A, x, tmp_m, q);
        for (uint32_t i = 0; i < m; i++) {
            if (tmp_m[i] != b[i] % q) { rc = CA_ERR_SINGULAR; break; }
        }
    }
    if (iters_out) *iters_out = it;
out:
    free(D); free(tmp_m); free(bp); free(w0); free(w1); free(w2); free(Bw); free(accp); free(accn);
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

    for (uint32_t i = 0; i < R; i++)
        for (uint32_t k = A->row_ptr[i]; k < A->row_ptr[i + 1]; k++) colw[A->col[k]]++;
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
    uint32_t *tc = malloc((C ? C : 1) * sizeof(uint32_t));
    int32_t *tv = malloc((C ? C : 1) * sizeof(int32_t));
    uint64_t *xred = calloc(nc ? nc : 1, sizeof(uint64_t));
    if (!bred || !tc || !tv || !xred) { rc = CA_ERR_NOMEM; goto out2; }
    {
        uint32_t ri = 0;
        for (uint32_t i = 0; i < R; i++) {
            if (!row_alive[i]) continue;
            uint32_t n = 0;
            for (uint32_t k = A->row_ptr[i]; k < A->row_ptr[i + 1]; k++) {
                if (cmap[A->col[k]] == UINT32_MAX) continue; /* cannot happen: dropped cols only in dropped rows */
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
