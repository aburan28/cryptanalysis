/*
 * Exact kernels for the PDP degree/yield profiler (loaded through ctypes).
 *
 *   - GF(2^n) arithmetic, n <= 63, polynomial basis (bit i = z^i);
 *   - affine arithmetic on y^2 + xy = x^3 + a2 x^2 + b (x = ~0 is infinity);
 *   - Boolean Macaulay rows over multilinear monomials (bitmask per monomial);
 *   - an incremental GF(2) echelon basis whose pivot is the HIGHEST set bit, so a
 *     column layout "ascending bit = ascending monomial order" makes every pivot a
 *     leading monomial, and appending a new degree block never moves old columns;
 *   - the binary Moebius transform (ANF -> values) for exact solution sets;
 *   - standard-monomial counting for the Groebner-basis completeness test.
 *
 * Every elimination reports the number of 64-bit word XORs it performed; that
 * count, not wall time, is the operation unit the profiler charges to the PDP.
 */
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

typedef uint64_t u64;
#define INF_X (~(u64)0)

typedef struct {
    int n;
    u64 mod;
    u64 a2;
    u64 b;
    u64 tmask;
    u64 htab[64];
    u64 stab[64];
} ctx_t;

size_t ctx_size(void) { return sizeof(ctx_t); }

static inline int deg64(u64 a) { return a ? 63 - __builtin_clzll(a) : -1; }

static inline u64 gf_mul(const ctx_t *c, u64 a, u64 b)
{
    u64 r = 0, top = (u64)1 << c->n;
    while (b) {
        if (b & 1) r ^= a;
        b >>= 1;
        a <<= 1;
        if (a & top) a ^= c->mod;
    }
    return r;
}

static inline u64 gf_sqr(const ctx_t *c, u64 a) { return gf_mul(c, a, a); }

static u64 gf_inv(const ctx_t *c, u64 a)
{
    u64 u = a, v = c->mod, g1 = 1, g2 = 0;
    if (!a) return 0;
    while (u != 1) {
        int j = deg64(u) - deg64(v);
        if (j < 0) {
            u64 t = u;
            u = v;
            v = t;
            t = g1;
            g1 = g2;
            g2 = t;
            j = -j;
        }
        u ^= v << j;
        g1 ^= g2 << j;
    }
    return g1;
}

static inline int gf_trace(const ctx_t *c, u64 a) { return __builtin_popcountll(a & c->tmask) & 1; }

static u64 lin_apply(const u64 *tab, u64 a)
{
    u64 r = 0;
    while (a) {
        int i = __builtin_ctzll(a);
        r ^= tab[i];
        a &= a - 1;
    }
    return r;
}

int ctx_init(ctx_t *c, int n, u64 mod, u64 a2, u64 b)
{
    if (n < 2 || n > 63 || deg64(mod) != n) return -1;
    memset(c, 0, sizeof(*c));
    c->n = n;
    c->mod = mod;
    c->a2 = a2;
    c->b = b;
    for (int i = 0; i < n; i++) {
        u64 x = (u64)1 << i, t = 0, y = x;
        for (int k = 0; k < n; k++) {
            t ^= y;
            y = gf_sqr(c, y);
        }
        if (t != 0 && t != 1) return -2;
        if (t) c->tmask |= (u64)1 << i;
        y = x;
        for (int k = 0; k < n - 1; k++) y = gf_sqr(c, y);
        c->stab[i] = y;
        if (n & 1) {
            u64 h = 0;
            y = x;
            for (int k = 0; k < (n + 1) / 2; k++) {
                h ^= y;
                y = gf_sqr(c, gf_sqr(c, y));
            }
            c->htab[i] = h;
        }
    }
    return 0;
}

u64 gf_mul_x(const ctx_t *c, u64 a, u64 b) { return gf_mul(c, a, b); }
u64 gf_inv_x(const ctx_t *c, u64 a) { return gf_inv(c, a); }
int gf_trace_x(const ctx_t *c, u64 a) { return gf_trace(c, a); }
u64 gf_halftrace_x(const ctx_t *c, u64 a) { return lin_apply(c->htab, a); }
u64 gf_sqrt_x(const ctx_t *c, u64 a) { return lin_apply(c->stab, a); }

void gf_mul_const_batch(const ctx_t *c, const u64 *a, int count, u64 k, u64 *out)
{
    for (int i = 0; i < count; i++) out[i] = gf_mul(c, a[i], k);
}

void gf_mul_vec(const ctx_t *c, const u64 *a, const u64 *b, int count, u64 *out)
{
    for (int i = 0; i < count; i++) out[i] = gf_mul(c, a[i], b[i]);
}

/* ---------------------------------------------------------------- curve */

static void ec_add(const ctx_t *c, u64 x1, u64 y1, u64 x2, u64 y2, u64 *xo, u64 *yo)
{
    if (x1 == INF_X) {
        *xo = x2;
        *yo = y2;
        return;
    }
    if (x2 == INF_X) {
        *xo = x1;
        *yo = y1;
        return;
    }
    u64 lam, x3;
    if (x1 == x2) {
        if (y1 != y2 || x1 == 0) {
            *xo = INF_X;
            *yo = 0;
            return;
        }
        lam = x1 ^ gf_mul(c, y1, gf_inv(c, x1));
        x3 = gf_sqr(c, lam) ^ lam ^ c->a2;
        *yo = gf_sqr(c, x1) ^ gf_mul(c, lam ^ 1, x3);
        *xo = x3;
        return;
    }
    lam = gf_mul(c, y1 ^ y2, gf_inv(c, x1 ^ x2));
    x3 = gf_sqr(c, lam) ^ lam ^ x1 ^ x2 ^ c->a2;
    *yo = gf_mul(c, lam, x1 ^ x3) ^ x3 ^ y1;
    *xo = x3;
}

static void ec_mul(const ctx_t *c, u64 x, u64 y, u64 k, u64 *xo, u64 *yo)
{
    u64 rx = INF_X, ry = 0;
    int top = deg64(k);
    for (int i = top; i >= 0; i--) {
        ec_add(c, rx, ry, rx, ry, &rx, &ry);
        if ((k >> i) & 1) ec_add(c, rx, ry, x, y, &rx, &ry);
    }
    *xo = rx;
    *yo = ry;
}

void ec_add_x(const ctx_t *c, u64 x1, u64 y1, u64 x2, u64 y2, u64 *out)
{
    ec_add(c, x1, y1, x2, y2, &out[0], &out[1]);
}

void ec_mul_x(const ctx_t *c, u64 x, u64 y, u64 k, u64 *out)
{
    ec_mul(c, x, y, k, &out[0], &out[1]);
}

void ec_mul_batch(const ctx_t *c, const u64 *xs, const u64 *ys, int count, u64 k, u64 *ox, u64 *oy)
{
    for (int i = 0; i < count; i++) ec_mul(c, xs[i], ys[i], k, &ox[i], &oy[i]);
}

/* y for each x (the root y = x*t of t^2 + t = x + a2 + b/x^2), ok[i] = 0 if x does not lift. */
void ec_lift_batch(const ctx_t *c, const u64 *xs, int count, u64 *ys, uint8_t *ok)
{
    for (int i = 0; i < count; i++) {
        u64 x = xs[i];
        if (x == 0) {
            ys[i] = lin_apply(c->stab, c->b);
            ok[i] = 1;
            continue;
        }
        u64 rhs = x ^ c->a2 ^ gf_mul(c, c->b, gf_inv(c, gf_sqr(c, x)));
        if (gf_trace(c, rhs)) {
            ok[i] = 0;
            ys[i] = 0;
            continue;
        }
        ys[i] = gf_mul(c, x, lin_apply(c->htab, rhs));
        ok[i] = 1;
    }
}

/* All sums P_i + P_j with i <= j, in row-major order. */
void ec_pair_sums(const ctx_t *c, const u64 *xs, const u64 *ys, int count, u64 *ox, u64 *oy)
{
    long long k = 0;
    for (int i = 0; i < count; i++)
        for (int j = i; j < count; j++, k++) ec_add(c, xs[i], ys[i], xs[j], ys[j], &ox[k], &oy[k]);
}

/* R - P_i for every i (negation is (x, x + y)). */
void ec_sub_from(const ctx_t *c, u64 rx, u64 ry, const u64 *xs, const u64 *ys, int count, u64 *ox,
                 u64 *oy)
{
    for (int i = 0; i < count; i++) {
        u64 nx = xs[i], ny = xs[i] == INF_X ? 0 : xs[i] ^ ys[i];
        ec_add(c, rx, ry, nx, ny, &ox[i], &oy[i]);
    }
}

/* ------------------------------------------------------ Macaulay rows */

/*
 * Row r of `out` (stride `words`) is mult[r] * f_{mult_eq[r]} over the Boolean
 * ring: every monomial of the equation is OR-ed with the multiplier and its column
 * bit toggled, so repeated products cancel mod 2.  With homog_degree >= 0 only
 * products of exactly that degree are kept (the top-degree part in the graded
 * ring F_2[x]/(x_i^2)), and col_offset is subtracted from every column.
 * Returns the number of monomial insertions.
 */
long long mac_build_rows(int words, const uint32_t *eq_masks, const int32_t *eq_off,
                         const uint32_t *mult, const int32_t *mult_eq, int nrows,
                         const int32_t *colidx, int col_offset, int homog_degree, u64 *out)
{
    long long ops = 0;
    for (int r = 0; r < nrows; r++) {
        u64 *row = out + (size_t)r * words;
        int e = mult_eq[r];
        uint32_t a = mult[r];
        for (int t = eq_off[e]; t < eq_off[e + 1]; t++) {
            uint32_t m = eq_masks[t];
            if (homog_degree >= 0 && ((m & a) || __builtin_popcount(m | a) != homog_degree))
                continue;
            int col = colidx[m | a] - col_offset;
            row[col >> 6] ^= (u64)1 << (col & 63);
            ops++;
        }
    }
    return ops;
}

/* ----------------------------------------------------------- echelon */

typedef struct {
    int ncols, words, nrows, cap;
    u64 *rows;
    int32_t *pivot;
    u64 *work;
} ech_t;

void *ech_new(int ncols)
{
    ech_t *e = calloc(1, sizeof(ech_t));
    if (!e) return NULL;
    e->ncols = ncols;
    e->words = (ncols + 63) / 64;
    e->cap = 64;
    e->rows = calloc((size_t)e->cap * e->words, sizeof(u64));
    e->pivot = malloc(sizeof(int32_t) * (size_t)(ncols > 0 ? ncols : 1));
    e->work = calloc((size_t)e->words, sizeof(u64));
    if (!e->rows || !e->pivot || !e->work) return NULL;
    for (int i = 0; i < ncols; i++) e->pivot[i] = -1;
    return e;
}

void ech_free(void *p)
{
    ech_t *e = p;
    if (!e) return;
    free(e->rows);
    free(e->pivot);
    free(e->work);
    free(e);
}

int ech_extend(void *p, int ncols)
{
    ech_t *e = p;
    if (ncols <= e->ncols) return 0;
    int words = (ncols + 63) / 64;
    if (words != e->words) {
        u64 *rows = calloc((size_t)e->cap * words, sizeof(u64));
        u64 *work = calloc((size_t)words, sizeof(u64));
        if (!rows || !work) return -1;
        for (int r = 0; r < e->nrows; r++)
            memcpy(rows + (size_t)r * words, e->rows + (size_t)r * e->words,
                   sizeof(u64) * e->words);
        free(e->rows);
        free(e->work);
        e->rows = rows;
        e->work = work;
        e->words = words;
    }
    int32_t *pivot = realloc(e->pivot, sizeof(int32_t) * (size_t)ncols);
    if (!pivot) return -1;
    for (int i = e->ncols; i < ncols; i++) pivot[i] = -1;
    e->pivot = pivot;
    e->ncols = ncols;
    return 0;
}

int ech_words(void *p) { return ((ech_t *)p)->words; }
int ech_rank(void *p) { return ((ech_t *)p)->nrows; }
int ech_has_unit(void *p) { return ((ech_t *)p)->ncols > 0 && ((ech_t *)p)->pivot[0] >= 0; }

/*
 * Reduce k rows (stride = current words) against the basis and append the
 * independent ones.  Stops early once the constant monomial (column 0) is a pivot
 * if stop_on_unit is set.  Returns rows consumed; *xors accumulates word XORs.
 */
int ech_add(void *p, const u64 *in, int k, int stop_on_unit, long long *xors)
{
    ech_t *e = p;
    int W = e->words;
    long long x = 0;
    int consumed = 0;
    for (int r = 0; r < k; r++) {
        consumed++;
        u64 *w = e->work;
        memcpy(w, in + (size_t)r * W, sizeof(u64) * W);
        int top = W - 1;
        for (;;) {
            while (top >= 0 && !w[top]) top--;
            if (top < 0) break;
            int h = top * 64 + deg64(w[top]);
            int pr = e->pivot[h];
            if (pr < 0) {
                if (e->nrows == e->cap) {
                    int cap = e->cap * 2;
                    u64 *rows = realloc(e->rows, sizeof(u64) * (size_t)cap * W);
                    if (!rows) return -1;
                    e->rows = rows;
                    e->cap = cap;
                }
                memcpy(e->rows + (size_t)e->nrows * W, w, sizeof(u64) * (top + 1));
                memset(e->rows + (size_t)e->nrows * W + top + 1, 0, sizeof(u64) * (W - top - 1));
                e->pivot[h] = e->nrows++;
                break;
            }
            const u64 *b = e->rows + (size_t)pr * W;
            for (int i = 0; i <= top; i++) w[i] ^= b[i];
            x += top + 1;
        }
        if (stop_on_unit && e->pivot[0] >= 0) break;
    }
    *xors += x;
    return consumed;
}

int ech_count_pivots_from(void *p, int col_lo)
{
    ech_t *e = p;
    int c = 0;
    for (int i = col_lo < 0 ? 0 : col_lo; i < e->ncols; i++) c += e->pivot[i] >= 0;
    return c;
}

int ech_pivots(void *p, int32_t *out)
{
    ech_t *e = p;
    int c = 0;
    for (int i = 0; i < e->ncols; i++)
        if (e->pivot[i] >= 0) out[c++] = i;
    return c;
}

/* out[i] = pivot column of basis row i (rows are kept in insertion order). */
int ech_row_pivots(void *p, int32_t *out)
{
    ech_t *e = p;
    for (int c = 0; c < e->ncols; c++)
        if (e->pivot[c] >= 0) out[e->pivot[c]] = c;
    return e->nrows;
}

/*
 * The products x_j * b for basis rows b = rows[idx[i]] and every variable j < nvars, in
 * the current column layout (pos2mask maps a column to its monomial, colidx back).
 * Output row (i * nvars + j) has the basis stride; `out` must be zeroed.  This is the
 * closure step of a mutant/F4-style scan: polynomials that fell below the current
 * degree are multiplied again instead of waiting for the next Macaulay degree.
 */
long long mac_mul_rows(void *p, const int32_t *idx, int k, int nvars, const uint32_t *pos2mask,
                       const int32_t *colidx, u64 *out)
{
    ech_t *e = p;
    int W = e->words;
    long long ops = 0;
    for (int i = 0; i < k; i++) {
        const u64 *src = e->rows + (size_t)idx[i] * W;
        for (int j = 0; j < nvars; j++) {
            u64 *dst = out + ((size_t)i * nvars + j) * W;
            uint32_t bit = (uint32_t)1 << j;
            for (int w = 0; w < W; w++) {
                u64 x = src[w];
                while (x) {
                    int c = w * 64 + __builtin_ctzll(x);
                    x &= x - 1;
                    int col = colidx[pos2mask[c] | bit];
                    dst[col >> 6] ^= (u64)1 << (col & 63);
                    ops++;
                }
            }
        }
    }
    return ops;
}

/* --------------------------------------------- exact solution counting */

/* In-place binary Moebius transform of a 2^nv table of F_2^n-valued ANF
 * coefficients into function values; writes up to max_out zero positions.
 * Returns the number of zeros. */
long long anf_zeros(u64 *a, int nv, uint32_t *out, long long max_out)
{
    size_t size = (size_t)1 << nv;
    for (int i = 0; i < nv; i++) {
        size_t bit = (size_t)1 << i;
        for (size_t base = 0; base < size; base += bit << 1)
            for (size_t x = base; x < base + bit; x++) a[x | bit] ^= a[x];
    }
    long long z = 0;
    for (size_t x = 0; x < size; x++)
        if (!a[x]) {
            if (z < max_out) out[z] = (uint32_t)x;
            z++;
        }
    return z;
}

/* Number of multilinear monomials over nv variables divisible by none of lm[]. */
long long count_standard(const uint32_t *lm, int k, int nv)
{
    size_t size = (size_t)1 << nv;
    uint8_t *cl = calloc(size, 1);
    if (!cl) return -1;
    for (int i = 0; i < k; i++) cl[lm[i]] = 1;
    for (int i = 0; i < nv; i++) {
        size_t bit = (size_t)1 << i;
        for (size_t base = 0; base < size; base += bit << 1)
            for (size_t x = base; x < base + bit; x++) cl[x | bit] |= cl[x];
    }
    long long s = 0;
    for (size_t x = 0; x < size; x++) s += !cl[x];
    free(cl);
    return s;
}
