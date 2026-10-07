/*
 * Batched PDP2ht attempts, the factor-base walk and a parallel-collision rho, in one C arithmetic.
 *
 * Curve y^2 + xy = x^3 + a2 x^2 + b over F_2[z]/(f), n <= 63 odd.  For a target x-coordinate S the
 * two-point decomposition over an F_2-subspace V = span(v_j) is the half-trace projection of
 * ../pdp-degree-heuristics/htsolver.py: with u = X + Y and c0 = sqrt(b)/S,
 *
 *     X^2 + u X + p = 0,   p = S (HT(u^2) + HT(c0^2) + eps),
 *
 * and pi(p) = 0, Tr(u) = Tr(c0), where pi is the projection onto F / V^(2).  The unknowns are the l
 * coordinates of u and eps.  Each solution with Tr(p / u^2) = 0 gives X = u HT(p / u^2); it is a
 * decomposition abscissa iff X lies in V, and the signed lifts must sum to R.
 *
 * v1 (htf_run): W walks advance together.  One Montgomery inversion per round serves the walk
 * denominators and every 1/S.  The l + 1 columns pi(S HT(v_j^2)), pi(S) are linear in S and are read
 * from byte tables, so building the system takes no field multiplication.  One elimination over
 * l + 1 unknowns (eps included) replaces the two per-eps eliminations, and the candidates of all W
 * attempts share one Montgomery inversion of their u^2.
 *
 * v0 (htf_run_v0): the repository's previous C oracle (fb-search/htenum.c ht_attempt_batch) for one
 * target at a time, after a single affine walk step: l field multiplications and nchk * l parities to
 * build the matrix, one elimination per eps, a separate batch inversion per eps branch.
 *
 * Both write the same verified hits: the attempt index and P1, P2 with P1 + P2 = R exactly.
 */
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <x86intrin.h>

typedef uint64_t u64;
typedef unsigned __int128 u128;

static int g_n, g_nt, g_sparse;
static int g_e[8];
static u64 g_mod, g_mask;

static inline u128 clmul(u64 a, u64 b)
{
    __m128i P = _mm_clmulepi64_si128(_mm_set_epi64x(0, (long long)a), _mm_set_epi64x(0, (long long)b), 0);
    return ((u128)(u64)_mm_extract_epi64(P, 1) << 64) | (u64)_mm_cvtsi128_si64(P);
}

/*
 * f = x^n + sum_t x^(e_t) with e_0 = 0 < ... < e_(nt-1) = k.  When n - 1 + k <= 63 and 2k <= n, two
 * shift-and-XOR folds reduce any product; otherwise fold with carry-less multiplications.
 */
static inline u64 gf_mul(u64 a, u64 b)
{
    u128 x = clmul(a, b);
    if (g_sparse) {
        u64 hi = (u64)(x >> g_n), r = (u64)x & g_mask;
        if (g_nt == 2) {
            r ^= hi ^ (hi << g_e[1]);
            hi = r >> g_n; r &= g_mask;
            return r ^ hi ^ (hi << g_e[1]);
        }
        for (int t = 0; t < g_nt; t++) r ^= hi << g_e[t];
        hi = r >> g_n; r &= g_mask;
        for (int t = 0; t < g_nt; t++) r ^= hi << g_e[t];
        return r;
    }
    u128 t;
    while ((t = x >> g_n) != 0)
        x = (x & g_mask) ^ clmul((u64)t, g_mod);
    return (u64)x;
}

static inline u64 gf_sqr(u64 a) { return gf_mul(a, a); }

static u64 gf_sqr_k(u64 a, int k)
{
    while (k-- > 0) a = gf_sqr(a);
    return a;
}

/* Itoh-Tsujii: beta_k = a^(2^k - 1), a^-1 = beta_(n-1)^2 */
static u64 gf_inv(u64 a)
{
    int e = g_n - 1, top = 63 - __builtin_clzll((u64)e);
    u64 beta = a;
    int k = 1;
    for (int i = top - 1; i >= 0; i--) {
        beta = gf_mul(gf_sqr_k(beta, k), beta);
        k *= 2;
        if ((e >> i) & 1) {
            beta = gf_mul(gf_sqr(beta), a);
            k += 1;
        }
    }
    return gf_sqr(beta);
}

static inline u64 apply_tab(const u64 *tab, int nb, u64 z)
{
    u64 r = 0;
    for (int j = 0; j < nb; j++) r ^= tab[j * 256 + ((z >> (8 * j)) & 255)];
    return r;
}

typedef struct {
    int n, nb, l, nchk;
    u64 mod, a2, b, sqrt_b, trmask, trrow;
    u64 basis[64], sq[64], hsq[64], checks[64];
    u64 *ht_tab, *syn_tab, *pi_tab, *sqrt_tab, *col_tab;
    u64 *cu, *cs, *cp, *ci, *pre;
    int *cw;
    int cap;
} ctx_t;

static void use(const ctx_t *c)
{
    g_n = c->n;
    g_mask = ((u64)1 << c->n) - 1;
    g_mod = c->mod & g_mask;
    g_nt = 0;
    for (int i = 0; i < c->n && g_nt < 8; i++)
        if ((g_mod >> i) & 1) g_e[g_nt++] = i;
    int k = 63 - __builtin_clzll(g_mod | 1);
    g_sparse = __builtin_popcountll(g_mod) <= 8 && (g_mod & 1) && c->n - 1 + k <= 63 && 2 * k <= c->n;
}

/* out[i] = 1 / in[i] (every in[i] != 0) with one inversion; four interleaved product chains */
static void batch_inv(const u64 *in, u64 *out, int m, u64 *pre)
{
    if (m <= 0) return;
    u64 acc[4] = {1, 1, 1, 1};
    for (int i = 0; i < m; i++) {
        acc[i & 3] = gf_mul(acc[i & 3], in[i]);
        pre[i] = acc[i & 3];
    }
    u64 a01 = gf_mul(acc[0], acc[1]), a23 = gf_mul(acc[2], acc[3]);
    u64 it = gf_inv(gf_mul(a01, a23));
    u64 iv[4] = {gf_mul(it, gf_mul(a23, acc[1])), gf_mul(it, gf_mul(a23, acc[0])),
                 gf_mul(it, gf_mul(a01, acc[3])), gf_mul(it, gf_mul(a01, acc[2]))};
    for (int i = m - 1; i >= 0; i--) {
        int q = i & 3;
        if (i >= 4) {
            out[i] = gf_mul(iv[q], pre[i - 4]);
            iv[q] = gf_mul(iv[q], in[i]);
        } else {
            out[i] = iv[q];
        }
    }
}

static u64 half_trace(u64 z)
{
    u64 r = z, w = z;
    for (int i = 1; i <= (g_n - 1) / 2; i++) {
        w = gf_sqr(gf_sqr(w));
        r ^= w;
    }
    return r;
}

static inline int tr(const ctx_t *c, u64 z) { return __builtin_parityll(z & c->trmask); }

static u64 pi_slow(const ctx_t *c, u64 z)
{
    u64 r = 0;
    for (int k = 0; k < c->nchk; k++) r |= (u64)__builtin_parityll(c->checks[k] & z) << k;
    return r;
}

void *htf_init(int n, u64 mod, u64 a2, u64 b, u64 sqrt_b, int l, const u64 *basis, int nchk, const u64 *checks,
               u64 trmask, const u64 *ht_tab, const u64 *syn_tab, int cap)
{
    if (n > 63 || n % 2 == 0 || l + 1 > 32 || nchk + 1 > 32) return NULL;
    ctx_t *c = calloc(1, sizeof(ctx_t));
    c->n = n; c->nb = (n + 7) / 8; c->l = l; c->nchk = nchk;
    c->mod = mod; c->a2 = a2; c->b = b; c->sqrt_b = sqrt_b; c->trmask = trmask;
    use(c);
    memcpy(c->basis, basis, sizeof(u64) * (size_t)l);
    memcpy(c->checks, checks, sizeof(u64) * (size_t)nchk);
    size_t T = (size_t)c->nb * 256;
    c->ht_tab = malloc(sizeof(u64) * T); memcpy(c->ht_tab, ht_tab, sizeof(u64) * T);
    c->syn_tab = malloc(sizeof(u64) * T); memcpy(c->syn_tab, syn_tab, sizeof(u64) * T);
    c->pi_tab = malloc(sizeof(u64) * T);
    c->sqrt_tab = malloc(sizeof(u64) * T);
    c->col_tab = malloc(sizeof(u64) * T * (size_t)(l + 1));
    c->trrow = 0;
    for (int j = 0; j < l; j++) {
        c->sq[j] = gf_sqr(basis[j]);
        c->hsq[j] = apply_tab(c->ht_tab, c->nb, c->sq[j]);
        c->trrow |= (u64)tr(c, basis[j]) << j;
    }
    for (int q = 0; q < c->nb; q++)
        for (int v = 0; v < 256; v++) {
            u64 z = ((u64)v << (8 * q)) & g_mask;
            size_t e = (size_t)q * 256 + (size_t)v;
            c->pi_tab[e] = pi_slow(c, z);
            c->sqrt_tab[e] = gf_sqr_k(z, n - 1);
            for (int j = 0; j < l; j++) c->col_tab[e * (size_t)(l + 1) + (size_t)j] = pi_slow(c, gf_mul(z, c->hsq[j]));
            c->col_tab[e * (size_t)(l + 1) + (size_t)l] = c->pi_tab[e];
        }
    c->cap = cap;
    c->cu = malloc(sizeof(u64) * (size_t)cap); c->cs = malloc(sizeof(u64) * (size_t)cap);
    c->cp = malloc(sizeof(u64) * (size_t)cap); c->pre = malloc(sizeof(u64) * (size_t)cap);
    c->ci = malloc(sizeof(u64) * (size_t)cap);
    c->cw = malloc(sizeof(int) * (size_t)cap);
    return c;
}

void htf_free(void *p)
{
    ctx_t *c = p;
    if (!c) return;
    free(c->ht_tab); free(c->syn_tab); free(c->pi_tab); free(c->sqrt_tab); free(c->col_tab);
    free(c->cu); free(c->cs); free(c->cp); free(c->ci); free(c->pre); free(c->cw);
    free(c);
}

/* ------------------------------------------------------------------ affine curve arithmetic */

typedef struct { u64 x, y; int inf; } pt;

static pt ec_dbl(const ctx_t *c, pt P)
{
    if (P.inf || P.x == 0) return (pt){0, 0, 1};
    u64 lam = P.x ^ gf_mul(P.y, gf_inv(P.x));
    u64 x = gf_sqr(lam) ^ lam ^ c->a2;
    u64 y = gf_sqr(P.x) ^ gf_mul(lam ^ 1, x);
    return (pt){x, y, 0};
}

static pt ec_add(const ctx_t *c, pt P, pt Q)
{
    if (P.inf) return Q;
    if (Q.inf) return P;
    if (P.x == Q.x) return P.y == Q.y ? ec_dbl(c, P) : (pt){0, 0, 1};
    u64 lam = gf_mul(P.y ^ Q.y, gf_inv(P.x ^ Q.x));
    u64 x = gf_sqr(lam) ^ lam ^ P.x ^ Q.x ^ c->a2;
    u64 y = gf_mul(lam, P.x ^ x) ^ x ^ P.y;
    return (pt){x, y, 0};
}

static inline pt ec_neg(pt P) { return P.inf ? P : (pt){P.x, P.x ^ P.y, 0}; }

static int ec_eq(pt P, pt Q) { return P.inf ? Q.inf : (!Q.inf && P.x == Q.x && P.y == Q.y); }

void htf_smul(void *p, u64 x, u64 y, int inf, const u64 *k_words, int nwords, u64 *out)
{
    const ctx_t *c = p;
    use(c);
    pt P = {x, y, inf}, R = {0, 0, 1};
    for (int w = nwords - 1; w >= 0; w--)
        for (int i = 63; i >= 0; i--) {
            R = ec_dbl(c, R);
            if ((k_words[w] >> i) & 1) R = ec_add(c, R, P);
        }
    out[0] = R.x; out[1] = R.y; out[2] = (u64)R.inf;
}

void htf_add(void *p, const u64 *P, const u64 *Q, u64 *out)
{
    const ctx_t *c = p;
    use(c);
    pt R = ec_add(c, (pt){P[0], P[1], (int)P[2]}, (pt){Q[0], Q[1], (int)Q[2]});
    out[0] = R.x; out[1] = R.y; out[2] = (u64)R.inf;
}

/* out_w = P + (w + 1) step for w < W */
void htf_chain(void *p, const u64 *P, const u64 *step, int W, u64 *X, u64 *Y, unsigned char *inf)
{
    const ctx_t *c = p;
    use(c);
    pt R = {P[0], P[1], (int)P[2]}, S = {step[0], step[1], (int)step[2]};
    for (int w = 0; w < W; w++) {
        R = ec_add(c, R, S);
        X[w] = R.x; Y[w] = R.y; inf[w] = (unsigned char)R.inf;
    }
}

/* y with y^2 + xy = x^3 + a2 x^2 + b, or 0 */
static int lift(const ctx_t *c, u64 x, u64 *y)
{
    if (!x) { *y = c->sqrt_b; return 1; }
    u64 cc = x ^ c->a2 ^ gf_mul(c->b, gf_inv(gf_sqr(x)));
    if (tr(c, cc)) return 0;
    *y = gf_mul(x, apply_tab(c->ht_tab, c->nb, cc));
    return 1;
}

/* signed lifts of X, Y = X + u summing to R exactly */
static int relation_check(const ctx_t *c, pt R, u64 X, u64 u, pt *P1, pt *P2)
{
    u64 Y = X ^ u, yx, yy;
    if (!lift(c, X, &yx) || !lift(c, Y, &yy)) return 0;
    pt A = {X, yx, 0}, B = {Y, yy, 0};
    if (!u) {
        pt D = ec_dbl(c, A);
        if (ec_eq(D, R)) { *P1 = A; *P2 = A; return 1; }
        if (ec_eq(D, ec_neg(R))) { *P1 = ec_neg(A); *P2 = ec_neg(A); return 1; }
        return 0;
    }
    pt S1 = ec_add(c, A, B), S2 = ec_add(c, A, ec_neg(B));
    if (ec_eq(S1, R)) { *P1 = A; *P2 = B; return 1; }
    if (ec_eq(S1, ec_neg(R))) { *P1 = ec_neg(A); *P2 = ec_neg(B); return 1; }
    if (ec_eq(S2, R)) { *P1 = A; *P2 = ec_neg(B); return 1; }
    if (ec_eq(S2, ec_neg(R))) { *P1 = ec_neg(A); *P2 = B; return 1; }
    return 0;
}

/* ------------------------------------------------------------------ hits and phase clocks */

/* hit record: attempt index (int64 as u64), R.x, R.y, P1.x, P1.y, P2.x, P2.y */
enum { HIT_WORDS = 7 };

typedef struct {
    u64 t0_tick;
    struct timespec t0;
    u64 ticks[3];  /* walk, pdp, relation check */
} clocks;

static void clk_start(clocks *k) { clock_gettime(CLOCK_MONOTONIC, &k->t0); k->t0_tick = __rdtsc(); memset(k->ticks, 0, sizeof k->ticks); }

static void clk_stop(clocks *k, long long *stats)
{
    struct timespec t1;
    u64 t1_tick = __rdtsc();
    clock_gettime(CLOCK_MONOTONIC, &t1);
    double ns = (double)(t1.tv_sec - k->t0.tv_sec) * 1e9 + (double)(t1.tv_nsec - k->t0.tv_nsec);
    double per = (t1_tick > k->t0_tick) ? ns / (double)(t1_tick - k->t0_tick) : 0.0;
    for (int i = 0; i < 3; i++) stats[i] += (long long)((double)k->ticks[i] * per);
    stats[3] += (long long)ns;
}

static int emit(u64 *hits, int nh, int max_hits, long long idx, pt R, pt P1, pt P2)
{
    if (nh < max_hits) {
        u64 *h = hits + (size_t)nh * HIT_WORDS;
        h[0] = (u64)idx; h[1] = R.x; h[2] = R.y; h[3] = P1.x; h[4] = P1.y; h[5] = P2.x; h[6] = P2.y;
    }
    return nh + 1;
}

/* ------------------------------------------------------------------ v1 */

typedef struct { int w; u64 X, u; } cand_hit;

/* the candidate stage of a block: batch-invert u^2, Tr(z) = 0, X = u HT(z), X in V */
static int flush(ctx_t *c, int m, cand_hit *out, int nout, int max_out)
{
    if (!m) return nout;
    batch_inv(c->cs, c->ci, m, c->pre);
    for (int i = 0; i < m; i++) {
        u64 z = gf_mul(c->cp[i], c->ci[i]);
        if (tr(c, z)) continue;
        u64 X = gf_mul(c->cu[i], apply_tab(c->ht_tab, c->nb, z));
        if (apply_tab(c->syn_tab, c->nb, X)) continue;
        if (nout < max_out) out[nout] = (cand_hit){c->cw[i], X, c->cu[i]};
        nout++;
    }
    return nout;
}

static inline void expand(const ctx_t *c, u64 mask, u64 *u, u64 *s, u64 *h)
{
    u64 a = 0, b = 0, d = 0;
    mask &= ((u64)1 << c->l) - 1;
    while (mask) {
        int j = __builtin_ctzll(mask);
        mask &= mask - 1;
        a ^= c->basis[j]; b ^= c->sq[j]; d ^= c->hsq[j];
    }
    *u = a; *s = b; *h = d;
}

/*
 * Runs up to `rounds` rounds of W walk points R_w (state Rx, Ry, Rinf; *round counts completed
 * rounds; *pending = 1 means the walk must advance before the next PDP).  Attempt index of walk w in
 * round t: t W + w + 1.  stop_on_hit: return after the first round with a verified hit.
 * stats[0..3] += walk, PDP, relation-check and total ns; stats[4] += attempts, stats[5] += candidates,
 * stats[6] += consistent systems, stats[7] += candidate hits before the relation check.
 */
int htf_run(void *p, int W, u64 *Rx, u64 *Ry, unsigned char *Rinf, u64 sx, u64 sy, long long *round,
            int *pending, int rounds, int stop_on_hit, u64 *hits, int max_hits, long long *stats)
{
    ctx_t *c = p;
    use(c);
    const int l = c->l, nb = c->nb, nchk = c->nchk;
    clocks k;
    clk_start(&k);
    u64 *den = malloc(sizeof(u64) * 2 * (size_t)W), *pre = malloc(sizeof(u64) * 2 * (size_t)W);
    u64 *inv = malloc(sizeof(u64) * 2 * (size_t)W);
    cand_hit *ch = malloc(sizeof(cand_hit) * (size_t)(4 * W + 64));
    int max_ch = 4 * W + 64;
    int nh = 0;
    pt stride = {sx, sy, 0};
    for (int it = 0; it < rounds; it++) {
        u64 t_a = __rdtsc();
        if (*pending) {
            /* advance R_w += stride, batch-inverting the denominators of the regular additions */
            for (int w = 0; w < W; w++) den[w] = (Rinf[w] || Rx[w] == sx) ? 1 : (Rx[w] ^ sx);
            batch_inv(den, inv, W, pre);
            for (int w = 0; w < W; w++) {
                u64 ivw = inv[w];
                if (Rinf[w] || Rx[w] == sx) {
                    pt R = ec_add(c, (pt){Rx[w], Ry[w], Rinf[w]}, stride);
                    Rx[w] = R.x; Ry[w] = R.y; Rinf[w] = (unsigned char)R.inf;
                    continue;
                }
                u64 lam = gf_mul(Ry[w] ^ sy, ivw);
                u64 x = gf_sqr(lam) ^ lam ^ Rx[w] ^ sx ^ c->a2;
                Ry[w] = gf_mul(lam, Rx[w] ^ x) ^ x ^ Ry[w];
                Rx[w] = x;
            }
            (*round)++;
        }
        *pending = 1;
        u64 t_b = __rdtsc();
        k.ticks[0] += t_b - t_a;

        /* 1/S for every attempt in one inversion */
        for (int w = 0; w < W; w++) den[w] = (Rinf[w] || !Rx[w]) ? 1 : Rx[w];
        batch_inv(den, inv, W, pre);
        int m = 0, nch = 0;
        for (int w = 0; w < W; w++) {
            if (Rinf[w] || !Rx[w]) continue;
            stats[4]++;
            u64 S = Rx[w];
            u64 c0 = gf_mul(c->sqrt_b, inv[w]);
            /* V in ker Tr forces Tr(u) = 0, so Tr(c0) = 1 has no solution: reject before the system */
            if (!c->trrow && tr(c, c0)) continue;
            u64 rf = gf_mul(S, apply_tab(c->ht_tab, nb, gf_sqr(c0)));
            u64 rhs = apply_tab(c->pi_tab, nb, rf) | ((u64)tr(c, c0) << nchk);
            u64 col[64];
            for (int j = 0; j <= l; j++) col[j] = 0;
            for (int q = 0; q < nb; q++) {
                const u64 *e = c->col_tab + ((size_t)q * 256 + ((S >> (8 * q)) & 255)) * (size_t)(l + 1);
                for (int j = 0; j <= l; j++) col[j] ^= e[j];
            }
            for (int j = 0; j < l; j++) col[j] |= ((c->trrow >> j) & 1) << nchk;
            /* column elimination kept in reduced echelon form (each pivot vector is zero at the other
             * pivot bits), so reductions are branch-free passes over the pivots; combination masks
             * over the l + 1 unknowns */
            /* each word holds the column bits (low 32) and its combination mask (high 32) */
            u64 pv[64], ker[64];
            int ph[64], np = 0, nk = 0;
            for (int j = 0; j <= l; j++) {
                u64 v = col[j] | ((u64)1 << (32 + j));
                u64 orig = v;
                for (int q = 0; q < np; q++) v ^= pv[q] & -((orig >> ph[q]) & 1);
                u64 lo = v & 0xffffffffu;
                if (!lo) { ker[nk++] = v >> 32; continue; }
                int h = 63 - __builtin_clzll(lo);
                for (int q = 0; q < np; q++) pv[q] ^= v & -((pv[q] >> h) & 1);
                pv[np] = v; ph[np] = h; np++;
            }
            u64 v = rhs;
            for (int q = 0; q < np; q++) v ^= pv[q] & -((rhs >> ph[q]) & 1);
            if (v & 0xffffffffu) continue;
            u64 sol = v >> 32;
            stats[6]++;
            u64 u, s, hs, du[64], ds[64], dp[64];
            expand(c, sol, &u, &s, &hs);
            u64 pp = gf_mul(S, hs) ^ rf ^ (((sol >> l) & 1) ? S : 0);
            for (int i = 0; i < nk; i++) {
                expand(c, ker[i], &du[i], &ds[i], &hs);
                dp[i] = gf_mul(S, hs) ^ (((ker[i] >> l) & 1) ? S : 0);
            }
            long long total = 1LL << nk;
            for (long long i = 0; i < total; i++) {
                if (i) {
                    int b = __builtin_ctzll((u64)i);
                    u ^= du[b]; s ^= ds[b]; pp ^= dp[b];
                }
                stats[5]++;
                if (!u) {
                    u64 X = apply_tab(c->sqrt_tab, nb, pp);
                    if (X && !apply_tab(c->syn_tab, nb, X)) {
                        if (nch < max_ch) ch[nch] = (cand_hit){w, X, 0};
                        nch++;
                    }
                    continue;
                }
                c->cu[m] = u; c->cs[m] = s; c->cp[m] = pp; c->cw[m] = w; m++;
                if (m == c->cap) { nch = flush(c, m, ch, nch, max_ch); m = 0; }
            }
        }
        nch = flush(c, m, ch, nch, max_ch);
        if (nch > max_ch) nch = max_ch;
        u64 t_c = __rdtsc();
        k.ticks[1] += t_c - t_b;
        stats[7] += nch;
        int found = 0;
        for (int i = 0; i < nch; i++) {
            int w = ch[i].w;
            pt R = {Rx[w], Ry[w], 0}, P1, P2;
            if (!relation_check(c, R, ch[i].X, ch[i].u, &P1, &P2)) continue;
            nh = emit(hits, nh, max_hits, *round * W + w + 1, R, P1, P2);
            found = 1;
        }
        k.ticks[2] += __rdtsc() - t_c;
        if ((stop_on_hit && found) || nh >= max_hits) { it++; break; }
    }
    free(den); free(pre); free(inv); free(ch);
    clk_stop(&k, stats);
    return nh;
}

/* ------------------------------------------------------------------ v0 */

/* fb-search/htenum.c enum_core, keeping the hit abscissae */
static int enum_core0(const ctx_t *c, int d, u64 u0, u64 p0, u64 s0, const u64 *f, const u64 *pk, const u64 *sk,
                      u64 *hx, u64 *hu, int nh, int max_h, long long *cand)
{
    enum { B = 256 };
    u64 us[B], ps[B], ss[B], pre[B];
    long long total = 1LL << d, nc = 0;
    u64 u = u0, p = p0, s = s0;
    long long i = 0;
    const int nb = c->nb;
    while (i < total) {
        int m = 0;
        for (; m < B && i < total; i++) {
            if (i) {
                int k = __builtin_ctzll((u64)i);
                u ^= f[k]; p ^= pk[k]; s ^= sk[k];
            }
            if (!u) {
                u64 X = p;
                for (int q = 1; q < g_n; q++) X = gf_mul(X, X);
                nc++;
                if (X && !apply_tab(c->syn_tab, nb, X)) {
                    if (nh < max_h) { hx[nh] = X; hu[nh] = 0; }
                    nh++;
                }
                continue;
            }
            us[m] = u; ps[m] = p; ss[m] = s; m++;
        }
        if (!m) continue;
        pre[0] = ss[0];
        for (int j = 1; j < m; j++) pre[j] = gf_mul(pre[j - 1], ss[j]);
        u64 inv = gf_inv(pre[m - 1]);
        for (int j = m - 1; j >= 0; j--) {
            u64 invj = j ? gf_mul(inv, pre[j - 1]) : inv;
            if (j) inv = gf_mul(inv, ss[j]);
            nc++;
            u64 z = gf_mul(ps[j], invj);
            if (tr(c, z)) continue;
            u64 X = gf_mul(us[j], apply_tab(c->ht_tab, nb, z));
            if (apply_tab(c->syn_tab, nb, X)) continue;
            if (nh < max_h) { hx[nh] = X; hu[nh] = us[j]; }
            nh++;
        }
    }
    *cand += nc;
    return nh;
}

/* one sequential walk R <- R + step (one inversion per step), then the htenum.c attempt on x(R) */
int htf_run_v0(void *p, u64 *Rxy, unsigned char *Rinf, u64 sx, u64 sy, long long *index, int *pending,
               int attempts, int stop_on_hit, u64 *hits, int max_hits, long long *stats)
{
    ctx_t *c = p;
    use(c);
    const int l = c->l, nb = c->nb, nchk = c->nchk;
    clocks k;
    clk_start(&k);
    int nh = 0;
    pt R = {Rxy[0], Rxy[1], *Rinf}, step = {sx, sy, 0};
    u64 hx[256], hu[256];
    for (int it = 0; it < attempts; it++) {
        u64 t_a = __rdtsc();
        if (*pending) { R = ec_add(c, R, step); (*index)++; }
        *pending = 1;
        u64 t_b = __rdtsc();
        k.ticks[0] += t_b - t_a;
        if (R.inf || !R.x) continue;
        stats[4]++;
        u64 S = R.x;
        u64 c0 = gf_mul(c->sqrt_b, gf_inv(S));
        u64 cols[64], rowm[128], f[64], pk[64], sk[64];
        int rhs0[128], rhsS[128];
        for (int j = 0; j < l; j++) cols[j] = gf_mul(S, c->hsq[j]);
        u64 cst = gf_mul(S, apply_tab(c->ht_tab, nb, gf_mul(c0, c0)));
        int tr_rhs = tr(c, c0);
        for (int q = 0; q < nchk; q++) {
            u64 mm = 0;
            for (int j = 0; j < l; j++) mm |= (u64)__builtin_parityll(c->checks[q] & cols[j]) << j;
            rowm[q] = mm;
            rhs0[q] = __builtin_parityll(c->checks[q] & cst);
            rhsS[q] = __builtin_parityll(c->checks[q] & S);
        }
        int nhx = 0;
        for (int eps = 0; eps < 2; eps++) {
            u64 pm[64]; int pr[64]; int has[64] = {0};
            int bad = 0;
            for (int q = 0; q <= nchk && !bad; q++) {
                u64 mm = q < nchk ? rowm[q] : c->trrow;
                int r = q < nchk ? (rhs0[q] ^ (eps ? rhsS[q] : 0)) : tr_rhs;
                for (int col = 0; col < l; col++)
                    if (has[col] && ((mm >> col) & 1)) { mm ^= pm[col]; r ^= pr[col]; }
                if (!mm) { if (r) bad = 1; continue; }
                int h = 63 - __builtin_clzll(mm);
                for (int col = 0; col < l; col++)
                    if (has[col] && ((pm[col] >> h) & 1)) { pm[col] ^= mm; pr[col] ^= r; }
                pm[h] = mm; pr[h] = r; has[h] = 1;
            }
            if (bad) continue;
            stats[6]++;
            u64 x = 0;
            for (int col = 0; col < l; col++) if (has[col] && pr[col]) x |= (u64)1 << col;
            int d = 0;
            for (int fv = 0; fv < l; fv++) {
                if (has[fv]) continue;
                u64 vec = (u64)1 << fv;
                for (int col = 0; col < l; col++) if (has[col] && ((pm[col] >> fv) & 1)) vec |= (u64)1 << col;
                u64 fe = 0;
                for (int j = 0; j < l; j++) if ((vec >> j) & 1) fe ^= c->basis[j];
                f[d++] = fe;
            }
            u64 u0 = 0;
            for (int j = 0; j < l; j++) if ((x >> j) & 1) u0 ^= c->basis[j];
            u64 w = u0 ^ c0;
            u64 p0 = gf_mul(S, apply_tab(c->ht_tab, nb, gf_mul(w, w)) ^ (u64)eps);
            for (int q = 0; q < d; q++) {
                sk[q] = gf_mul(f[q], f[q]);
                pk[q] = gf_mul(S, apply_tab(c->ht_tab, nb, sk[q]));
            }
            nhx = enum_core0(c, d, u0, p0, gf_mul(u0, u0), f, pk, sk, hx, hu, nhx, 256, &stats[5]);
        }
        u64 t_c = __rdtsc();
        k.ticks[1] += t_c - t_b;
        if (nhx > 256) nhx = 256;
        stats[7] += nhx;
        int found = 0;
        for (int i = 0; i < nhx; i++) {
            pt P1, P2;
            if (!relation_check(c, R, hx[i], hu[i], &P1, &P2)) continue;
            nh = emit(hits, nh, max_hits, *index, R, P1, P2);
            found = 1;
        }
        k.ticks[2] += __rdtsc() - t_c;
        if ((stop_on_hit && found) || nh >= max_hits) break;
    }
    Rxy[0] = R.x; Rxy[1] = R.y; *Rinf = (unsigned char)R.inf;
    clk_stop(&k, stats);
    return nh;
}

/* ------------------------------------------------------------------ rho */

typedef struct { u64 x, y, a, b; } dp_entry;

/*
 * W parallel r-adding walks P <- P + T[j(P)], 32-entry table T_j = c_j G + d_j Q, distinguished
 * points by (x >> 8) & dp_mask == 0 stored in an open-addressing table (dp_cap a power of two).
 * Returns 1 with out = (a1, b1, a2, b2, sign) when two different walks reach the same x
 * (sign 1: same point, -1: opposite points), 0 when max_rounds run out.  stats: [0] steps, [1] ns,
 * [2] distinguished points stored.
 */
int htf_rho(void *p, int W, u64 *X, u64 *Y, u64 *A, u64 *B, const u64 *TX, const u64 *TY, const u64 *TC,
            const u64 *TD, u64 r, u64 dp_mask, dp_entry *tab, long long dp_cap, long long max_rounds,
            u64 *out, long long *stats)
{
    const ctx_t *c = p;
    use(c);
    struct timespec t0, t1;
    clock_gettime(CLOCK_MONOTONIC, &t0);
    u64 *den = malloc(sizeof(u64) * (size_t)W), *pre = malloc(sizeof(u64) * (size_t)W);
    u64 *ivd = malloc(sizeof(u64) * (size_t)W);
    int *sel = malloc(sizeof(int) * (size_t)W);
    int ret = 0;
    for (long long rd = 0; rd < max_rounds && !ret; rd++) {
        for (int i = 0; i < W; i++) {
            sel[i] = (int)(X[i] & 31);
            den[i] = X[i] ^ TX[sel[i]];
            if (!den[i]) den[i] = 1;
        }
        batch_inv(den, ivd, W, pre);
        for (int i = 0; i < W; i++) {
            u64 ivi = ivd[i];
            int j = sel[i];
            if (X[i] == TX[j]) {
                pt R = ec_add(c, (pt){X[i], Y[i], 0}, (pt){TX[j], TY[j], 0});
                if (R.inf) { R = (pt){TX[j], TY[j], 0}; A[i] = TC[j]; B[i] = TD[j]; }
                else { A[i] = (A[i] + TC[j]) % r; B[i] = (B[i] + TD[j]) % r; }
                X[i] = R.x; Y[i] = R.y;
            } else {
                u64 lam = gf_mul(Y[i] ^ TY[j], ivi);
                u64 x = gf_sqr(lam) ^ lam ^ X[i] ^ TX[j] ^ c->a2;
                Y[i] = gf_mul(lam, X[i] ^ x) ^ x ^ Y[i];
                X[i] = x;
                A[i] += TC[j]; if (A[i] >= r) A[i] -= r;
                B[i] += TD[j]; if (B[i] >= r) B[i] -= r;
            }
            stats[0]++;
            if ((X[i] >> 8) & dp_mask) continue;
            u64 h = (X[i] * 0x9E3779B97F4A7C15ull) & (u64)(dp_cap - 1);
            while (tab[h].x && tab[h].x != X[i]) h = (h + 1) & (u64)(dp_cap - 1);
            if (!tab[h].x) {
                tab[h] = (dp_entry){X[i], Y[i], A[i], B[i]};
                stats[2]++;
                continue;
            }
            if (tab[h].a == A[i] && tab[h].b == B[i]) continue;
            out[0] = tab[h].a; out[1] = tab[h].b; out[2] = A[i]; out[3] = B[i];
            out[4] = tab[h].y == Y[i] ? 1 : (u64)-1;
            ret = 1;
            break;
        }
    }
    free(den); free(pre); free(ivd); free(sel);
    clock_gettime(CLOCK_MONOTONIC, &t1);
    stats[1] += (long long)((t1.tv_sec - t0.tv_sec) * 1000000000LL + (t1.tv_nsec - t0.tv_nsec));
    return ret;
}
