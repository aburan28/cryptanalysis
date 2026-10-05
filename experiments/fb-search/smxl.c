/*
 * Sparse-column MutantXL (MXL closure) over GF(2) with x_i^2 = x_i, for up to 64 variables.
 *
 * Columns are the multilinear monomials of degree <= D (64-bit masks), ordered by degree so that
 * the constant is column 0 and a row's pivot (its highest set column) is a highest-degree monomial.
 * At degree D the closure multiplies every basis row of degree < D by every variable until no new
 * row appears; then D grows.  1 in the row space (pivot at column 0) is a refutation.  This is the
 * same closure as pdp-degree-heuristics/macaulay.py (mode "mxl") without its 2^N dense layout.
 *
 * cc -O3 -march=native -shared -fPIC -o libsmxl.so smxl.c
 */
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

typedef uint64_t u64;

typedef struct {
    int ncols, words, nrows, cap;
    u64 *rows;
    int32_t *pivot;   /* pivot[col] = row index or -1 */
    int32_t *rpiv;    /* rpiv[row] = pivot column */
    uint8_t *mult;    /* mult[row] = already multiplied by every variable */
    u64 *work;
} ech_t;

static int deg64(u64 x) { return 63 - __builtin_clzll(x); }

static int ech_init(ech_t *e, int ncols)
{
    memset(e, 0, sizeof *e);
    e->ncols = ncols;
    e->words = (ncols + 63) / 64;
    e->cap = 256;
    e->rows = calloc((size_t)e->cap * e->words, sizeof(u64));
    e->pivot = malloc(sizeof(int32_t) * (size_t)ncols);
    e->rpiv = malloc(sizeof(int32_t) * (size_t)e->cap);
    e->mult = calloc((size_t)e->cap, 1);
    e->work = calloc((size_t)e->words, sizeof(u64));
    if (!e->rows || !e->pivot || !e->rpiv || !e->mult || !e->work) return -1;
    for (int i = 0; i < ncols; i++) e->pivot[i] = -1;
    return 0;
}

static void ech_free(ech_t *e)
{
    free(e->rows); free(e->pivot); free(e->rpiv); free(e->mult); free(e->work);
}

static int ech_extend(ech_t *e, int ncols)
{
    if (ncols <= e->ncols) return 0;
    int words = (ncols + 63) / 64;
    if (words != e->words) {
        u64 *rows = calloc((size_t)e->cap * words, sizeof(u64));
        u64 *work = calloc((size_t)words, sizeof(u64));
        if (!rows || !work) return -1;
        for (int r = 0; r < e->nrows; r++)
            memcpy(rows + (size_t)r * words, e->rows + (size_t)r * e->words, sizeof(u64) * e->words);
        free(e->rows); free(e->work);
        e->rows = rows; e->work = work; e->words = words;
    }
    int32_t *pivot = realloc(e->pivot, sizeof(int32_t) * (size_t)ncols);
    if (!pivot) return -1;
    for (int i = e->ncols; i < ncols; i++) pivot[i] = -1;
    e->pivot = pivot;
    e->ncols = ncols;
    return 0;
}

/* Reduce one row in e->work against the basis; append if independent.  Returns 1 if appended. */
static int ech_add_work(ech_t *e, long long *xors)
{
    int W = e->words;
    u64 *w = e->work;
    int top = W - 1;
    for (;;) {
        while (top >= 0 && !w[top]) top--;
        if (top < 0) return 0;
        int h = top * 64 + deg64(w[top]);
        int pr = e->pivot[h];
        if (pr < 0) {
            if (e->nrows == e->cap) {
                int cap = e->cap * 2;
                u64 *rows = realloc(e->rows, sizeof(u64) * (size_t)cap * W);
                int32_t *rp = realloc(e->rpiv, sizeof(int32_t) * (size_t)cap);
                uint8_t *mu = realloc(e->mult, (size_t)cap);
                if (!rows || !rp || !mu) return -1;
                memset(mu + e->cap, 0, (size_t)(cap - e->cap));
                e->rows = rows; e->rpiv = rp; e->mult = mu; e->cap = cap;
            }
            memcpy(e->rows + (size_t)e->nrows * W, w, sizeof(u64) * (top + 1));
            memset(e->rows + (size_t)e->nrows * W + top + 1, 0, sizeof(u64) * (W - top - 1));
            e->pivot[h] = e->nrows;
            e->rpiv[e->nrows] = h;
            e->mult[e->nrows] = 0;
            e->nrows++;
            return 1;
        }
        const u64 *b = e->rows + (size_t)pr * W;
        for (int i = 0; i <= top; i++) w[i] ^= b[i];
        *xors += top + 1;
    }
}

/* columns: sorted by (degree, mask); binary search inside the degree block */
typedef struct {
    int N, D;
    u64 *mask;        /* mask[col] */
    int *deg_lo;      /* deg_lo[k] = first column of degree k, k = 0..D+1 */
} cols_t;

static long long binom(int n, int k)
{
    if (k < 0 || k > n) return 0;
    long long r = 1;
    for (int i = 1; i <= k; i++) r = r * (n - k + i) / i;
    return r;
}

static int cmp_u64(const void *a, const void *b)
{
    u64 x = *(const u64 *)a, y = *(const u64 *)b;
    return x < y ? -1 : x > y;
}

static u64 *g_lin_out = NULL;  /* if set: (variable mask, constant) of every basis row of degree <= 1 */
static int g_lin_cap = 0;
static u64 g_xmask = 0;     /* variables whose degree is bounded by g_xdeg in every column */
static int g_xdeg = 64;

static int cols_build(cols_t *c, int N, int D)
{
    long long total = 0;
    for (int k = 0; k <= D; k++) total += binom(N, k);
    c->N = N; c->D = D;
    c->mask = malloc(sizeof(u64) * (size_t)total);
    c->deg_lo = malloc(sizeof(int) * (size_t)(D + 2));
    if (!c->mask || !c->deg_lo) return -1;
    long long pos = 0;
    for (int k = 0; k <= D; k++) {
        c->deg_lo[k] = (int)pos;
        /* enumerate k-subsets of N via Gosper's hack */
        if (k == 0) { c->mask[pos++] = 0; continue; }
        if (k > N) continue;
        u64 s = (k == 64) ? ~(u64)0 : (((u64)1 << k) - 1);
        u64 lim = (N == 64) ? 0 : ((u64)1 << N);
        while (1) {
            if (__builtin_popcountll(s & g_xmask) <= g_xdeg) c->mask[pos++] = s;
            u64 cc = s & -s, r = s + cc;
            if (r == 0) break;
            s = (((r ^ s) >> 2) / cc) | r;
            if (N < 64 && s >= lim) break;
        }
        qsort(c->mask + c->deg_lo[k], (size_t)(pos - c->deg_lo[k]), sizeof(u64), cmp_u64);
    }
    c->deg_lo[D + 1] = (int)pos;
    return 0;
}

static int col_of(const cols_t *c, u64 m)
{
    int k = __builtin_popcountll(m);
    if (k > c->D) return -1;
    int lo = c->deg_lo[k], hi = c->deg_lo[k + 1] - 1;
    while (lo <= hi) {
        int mid = (lo + hi) >> 1;
        if (c->mask[mid] == m) return mid;
        if (c->mask[mid] < m) lo = mid + 1; else hi = mid - 1;
    }
    return -1;
}

static int col_deg(const cols_t *c, int col)
{
    int k = 0;
    while (k <= c->D && c->deg_lo[k + 1] <= col) k++;
    return k;
}

/*
 * eq_masks/eq_off: equations as monomial lists (eq i = eq_masks[eq_off[i] .. eq_off[i+1]-1]).
 * Runs the closure from D0 = max equation degree up to d_max while columns stay <= max_cols.
 * out[0] = status (1 refuted, 0 degree limit, -1 budget, -2 memory), out[1] = degree reached,
 * out[2] = columns, out[3] = rank, out[4] = word xors, out[5] = rows added (incl. dependent),
 * out[6] = number of linear (degree <= 1) pivots at the end.
 */
long long smxl_run_masked(int N, const u64 *eq_masks, const int32_t *eq_off, int neq, int d_max,
                          long long max_cols, u64 mult_vars, long long *out);

long long smxl_run(int N, const u64 *eq_masks, const int32_t *eq_off, int neq, int d_max,
                   long long max_cols, long long *out)
{
    return smxl_run_masked(N, eq_masks, eq_off, neq, d_max, max_cols, ~(u64)0, out);
}

long long smxl_run_restricted(int N, const u64 *eq_masks, const int32_t *eq_off, int neq, int d_max,
                              long long max_cols, u64 mult_vars, u64 xmask, int xdeg, long long *out,
                              u64 *lin_out, int lin_cap)
{
    g_lin_out = lin_out;
    g_lin_cap = lin_cap;
    g_xmask = xmask;
    g_xdeg = xdeg;
    long long r = smxl_run_masked(N, eq_masks, eq_off, neq, d_max, max_cols, mult_vars, out);
    g_xmask = 0;
    g_xdeg = 64;
    g_lin_out = NULL;
    g_lin_cap = 0;
    return r;
}

/* As smxl_run, but the closure multiplies only by the variables in mult_vars. */
long long smxl_run_masked(int N, const u64 *eq_masks, const int32_t *eq_off, int neq, int d_max,
                          long long max_cols, u64 mult_vars, long long *out)
{
    int D0 = 0;
    for (int i = 0; i < neq; i++)
        for (int j = eq_off[i]; j < eq_off[i + 1]; j++) {
            int k = __builtin_popcountll(eq_masks[j]);
            if (k > D0) D0 = k;
        }
    long long xors = 0, rows_in = 0;
    ech_t e;
    cols_t c = {0};
    int status = 0, D = D0;
    if (cols_build(&c, N, D0)) { out[0] = -2; return 0; }
    if (c.deg_lo[D0 + 1] > max_cols) { out[0] = -1; out[1] = D0; out[2] = c.deg_lo[D0 + 1]; free(c.mask); free(c.deg_lo); return 0; }
    if (ech_init(&e, c.deg_lo[D0 + 1])) { out[0] = -2; return 0; }
    for (int i = 0; i < neq; i++) {
        memset(e.work, 0, sizeof(u64) * e.words);
        for (int j = eq_off[i]; j < eq_off[i + 1]; j++) {
            int col = col_of(&c, eq_masks[j]);
            e.work[col >> 6] ^= (u64)1 << (col & 63);
        }
        rows_in++;
        if (ech_add_work(&e, &xors) < 0) { status = -2; goto done; }
    }
    for (D = D0; D <= d_max; D++) {
        if (D > D0) {
            cols_t c2;
            if (cols_build(&c2, N, D)) { status = -2; goto done; }
            if (c2.deg_lo[D + 1] > max_cols) { status = -1; D--; free(c2.mask); free(c2.deg_lo); break; }
            /* the degree <= D-1 prefix of c2 equals c: same enumeration and sort */
            free(c.mask); free(c.deg_lo);
            c = c2;
            if (ech_extend(&e, c.deg_lo[D + 1])) { status = -2; goto done; }
        }
        u64 *src = malloc(sizeof(u64) * (size_t)e.words);
        if (!src) { status = -2; goto done; }
        int changed = 1;
        while (changed && e.pivot[0] < 0) {
            changed = 0;
            int nr = e.nrows;
            for (int r = 0; r < nr && e.pivot[0] < 0; r++) {
                if (e.mult[r] || col_deg(&c, e.rpiv[r]) >= D) continue;
                e.mult[r] = 1;
                /* ech_add_work may realloc e.rows: multiply a private copy */
                memcpy(src, e.rows + (size_t)r * e.words, sizeof(u64) * e.words);
                for (int v = 0; v < N && e.pivot[0] < 0; v++) {
                    u64 bit = (u64)1 << v;
                    if (!(mult_vars & bit)) continue;
                    memset(e.work, 0, sizeof(u64) * e.words);
                    for (int w = 0; w < e.words; w++) {
                        u64 x = src[w];
                        while (x) {
                            int col = w * 64 + __builtin_ctzll(x);
                            x &= x - 1;
                            int nc = col_of(&c, c.mask[col] | bit);
                            e.work[nc >> 6] ^= (u64)1 << (nc & 63);
                        }
                    }
                    rows_in++;
                    int a = ech_add_work(&e, &xors);
                    if (a < 0) { status = -2; free(src); goto done; }
                    if (a) changed = 1;
                }
            }
        }
        free(src);
        if (e.pivot[0] >= 0) { status = 1; break; }
    }
    if (D > d_max) D = d_max;
done:
    {
        int lin = 0;
        int lo2 = c.deg_lo[2 <= c.D + 1 ? 2 : c.D + 1];
        for (int col = 0; col < lo2; col++) {
            int r = e.pivot[col];
            if (r < 0) continue;
            if (g_lin_out && lin < g_lin_cap) {
                const u64 *row = e.rows + (size_t)r * e.words;
                u64 vm = 0, cst = 0;
                for (int cc = 0; cc < lo2; cc++)
                    if ((row[cc >> 6] >> (cc & 63)) & 1) {
                        if (c.mask[cc] == 0) cst = 1; else vm |= c.mask[cc];
                    }
                g_lin_out[2 * lin] = vm;
                g_lin_out[2 * lin + 1] = cst;
            }
            lin++;
        }
        out[0] = status; out[1] = D; out[2] = e.ncols; out[3] = e.nrows; out[4] = xors; out[5] = rows_in;
        out[6] = lin;
    }
    ech_free(&e);
    free(c.mask); free(c.deg_lo);
    return 0;
}
