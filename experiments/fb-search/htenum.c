/*
 * Optimized 2^d enumeration of the PDP2ht residual space, the fair baseline for residual solvers.
 *
 * For a target S and one eps branch, u = u0 + sum_k t_k f_k ranges over an affine space of
 * dimension d (Gray-code order: one XOR per step for u, u^2 and p(u), all affine in t).  For each
 * u != 0: z = p(u) / u^2; skip unless Tr(z) = 0; X = u * HT(z); X is a decomposition abscissa iff X
 * lies in V (then Y = X + u does too).  HT and the parity checks of V are F_2-linear and are applied
 * through byte tables; 1/u^2 comes from Montgomery batch inversion over blocks.
 *
 * cc -O3 -march=native -mpclmul -shared -fPIC -o libhtenum.so htenum.c
 */
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <immintrin.h>

typedef uint64_t u64;

static int g_n;
static u64 g_mod;   /* modulus without the x^n term */
static u64 g_mask;

typedef unsigned __int128 u128;

static inline u128 clmul(u64 a, u64 b)
{
    __m128i P = _mm_clmulepi64_si128(_mm_set_epi64x(0, (long long)a), _mm_set_epi64x(0, (long long)b), 0);
    return ((u128)(u64)_mm_extract_epi64(P, 1) << 64) | (u64)_mm_cvtsi128_si64(P);
}

static inline u64 gf_mul(u64 a, u64 b)
{
    /* fold the bits above x^n back with x^n = mod; a low-degree mod converges in two or three folds */
    u128 x = clmul(a, b);
    u128 t;
    while ((t = x >> g_n) != 0)
        x = (x & g_mask) ^ clmul((u64)t, g_mod);
    return (u64)x;
}

static u64 gf_inv(u64 a)
{
    /* a^(2^n - 2) by square-and-multiply */
    u64 r = 1, b = a;
    for (int i = 1; i < g_n; i++) {
        b = gf_mul(b, b);
        r = gf_mul(r, b);
    }
    return r;
}

static inline u64 apply_tab(const u64 *tab, u64 z)
{
    u64 r = 0;
    for (int j = 0; z; j++, z >>= 8) r ^= tab[j * 256 + (z & 255)];
    return r;
}

/*
 * u0, p0, s0 = u0^2; f[k], pk[k], sk[k] = f_k^2: the affine parts.  ht_tab and syn_tab: byte tables
 * (n/8 + 1 blocks of 256) of the half-trace and of the V-syndrome.  trmask: Tr(z) = parity(z & trmask).
 * Writes up to max_hits u-values with a hit to hits; returns the number of hits, *cand the candidates.
 */
static void set_field(int n, u64 mod)
{
    g_n = n;
    g_mod = mod & ((n == 64) ? ~(u64)0 : (((u64)1 << n) - 1));
    g_mask = (n == 64) ? ~(u64)0 : (((u64)1 << n) - 1);
}

static long long enum_core(int d, u64 u0, u64 p0, u64 s0, const u64 *f, const u64 *pk, const u64 *sk,
                           const u64 *ht_tab, const u64 *syn_tab, u64 trmask, u64 *hits, int max_hits,
                           long long *cand);

long long ht_enum(int n, u64 mod, int d, u64 u0, u64 p0, u64 s0, const u64 *f, const u64 *pk, const u64 *sk,
                  const u64 *ht_tab, const u64 *syn_tab, u64 trmask, u64 *hits, int max_hits, long long *cand)
{
    set_field(n, mod);
    return enum_core(d, u0, p0, s0, f, pk, sk, ht_tab, syn_tab, trmask, hits, max_hits, cand);
}

static long long enum_core(int d, u64 u0, u64 p0, u64 s0, const u64 *f, const u64 *pk, const u64 *sk,
                           const u64 *ht_tab, const u64 *syn_tab, u64 trmask, u64 *hits, int max_hits,
                           long long *cand)
{
    enum { B = 256 };
    u64 us[B], ps[B], ss[B], pre[B];
    long long total = 1LL << d, nh = 0, nc = 0;
    u64 u = u0, p = p0, s = s0;
    long long i = 0;
    while (i < total) {
        int m = 0;
        for (; m < B && i < total; i++) {
            if (i) {  /* Gray code: flip bit k = ctz(i) */
                int k = __builtin_ctzll((u64)i);
                u ^= f[k]; p ^= pk[k]; s ^= sk[k];
            }
            if (!u) {
                /* u = 0 is a doubling R = 2P: X^2 = p(0), so X = sqrt(p) = p^(2^(n-1)) */
                u64 X = p;
                for (int q = 1; q < g_n; q++) X = gf_mul(X, X);
                nc++;
                if (X && !apply_tab(syn_tab, X)) {
                    if (nh < max_hits) hits[nh] = 0;
                    nh++;
                }
                continue;
            }
            us[m] = u; ps[m] = p; ss[m] = s; m++;
        }
        if (!m) continue;
        /* Montgomery batch inversion of ss[0..m-1] */
        pre[0] = ss[0];
        for (int j = 1; j < m; j++) pre[j] = gf_mul(pre[j - 1], ss[j]);
        u64 inv = gf_inv(pre[m - 1]);
        for (int j = m - 1; j >= 0; j--) {
            u64 invj = j ? gf_mul(inv, pre[j - 1]) : inv;
            if (j) inv = gf_mul(inv, ss[j]);
            nc++;
            u64 z = gf_mul(ps[j], invj);
            if (__builtin_parityll(z & trmask)) continue;
            u64 X = gf_mul(us[j], apply_tab(ht_tab, z));
            if (apply_tab(syn_tab, X)) continue;
            if (nh < max_hits) hits[nh] = us[j];
            nh++;
        }
    }
    *cand = nc;
    return nh;
}

/*
 * One PDP2ht attempt per target S, entirely in C: the projection (S * HT(v_j^2) columns against the
 * parity checks of V^(2), plus the trace row) solved for each eps, then enum_core over each residual
 * space.  basis, ht_sq[j] = HT(v_j^2): l values; checks: nchk parity masks; trrow: Tr(v_j) bits.
 * hits_out[i] = hits for target i (both branches).  Returns the total number of residual candidates.
 */
long long ht_attempt_batch(int n, u64 mod, int l, const u64 *basis, const u64 *ht_sq, const u64 *checks,
                           int nchk, u64 trrow, u64 sqrt_b, const u64 *ht_tab, const u64 *syn_tab, u64 trmask,
                           const u64 *Ss, int count, long long *hits_out)
{
    set_field(n, mod);
    long long cand_total = 0;
    u64 cols[64], rowm[128], f[64], pk[64], sk[64];
    int rhs0[128], rhsS[128];
    for (int it = 0; it < count; it++) {
        u64 S = Ss[it];
        u64 c0 = gf_mul(sqrt_b, gf_inv(S));
        for (int j = 0; j < l; j++) cols[j] = gf_mul(S, ht_sq[j]);
        u64 cst = gf_mul(S, apply_tab(ht_tab, gf_mul(c0, c0)));
        int tr_rhs = __builtin_parityll(c0 & trmask);
        for (int c = 0; c < nchk; c++) {
            u64 m = 0;
            for (int j = 0; j < l; j++) m |= (u64)__builtin_parityll(checks[c] & cols[j]) << j;
            rowm[c] = m;
            rhs0[c] = __builtin_parityll(checks[c] & cst);
            rhsS[c] = __builtin_parityll(checks[c] & S);
        }
        long long hits = 0;
        for (int eps = 0; eps < 2; eps++) {
            /* reduced echelon form over l unknowns; piv[col] = (mask, rhs) */
            u64 pm[64]; int pr[64]; int has[64] = {0};
            int bad = 0;
            for (int c = 0; c <= nchk && !bad; c++) {
                u64 m = c < nchk ? rowm[c] : trrow;
                int r = c < nchk ? (rhs0[c] ^ (eps ? rhsS[c] : 0)) : tr_rhs;
                for (int col = 0; col < l; col++)
                    if (has[col] && ((m >> col) & 1)) { m ^= pm[col]; r ^= pr[col]; }
                if (!m) { if (r) bad = 1; continue; }
                int h = 63 - __builtin_clzll(m);
                for (int col = 0; col < l; col++)
                    if (has[col] && ((pm[col] >> h) & 1)) { pm[col] ^= m; pr[col] ^= r; }
                pm[h] = m; pr[h] = r; has[h] = 1;
            }
            if (bad) continue;
            u64 x = 0;
            for (int col = 0; col < l; col++) if (has[col] && pr[col]) x |= (u64)1 << col;
            int d = 0;
            for (int fv = 0; fv < l; fv++) {
                if (has[fv]) continue;
                u64 vec = (u64)1 << fv;
                for (int col = 0; col < l; col++) if (has[col] && ((pm[col] >> fv) & 1)) vec |= (u64)1 << col;
                u64 fe = 0;
                for (int j = 0; j < l; j++) if ((vec >> j) & 1) fe ^= basis[j];
                f[d++] = fe;
            }
            u64 u0 = 0;
            for (int j = 0; j < l; j++) if ((x >> j) & 1) u0 ^= basis[j];
            u64 w = u0 ^ c0;
            u64 p0 = gf_mul(S, apply_tab(ht_tab, gf_mul(w, w)) ^ (u64)eps);
            for (int k = 0; k < d; k++) {
                sk[k] = gf_mul(f[k], f[k]);
                pk[k] = gf_mul(S, apply_tab(ht_tab, sk[k]));
            }
            long long cand = 0;
            hits += enum_core(d, u0, p0, gf_mul(u0, u0), f, pk, sk, ht_tab, syn_tab, trmask, NULL, 0, &cand);
            cand_total += cand;
        }
        hits_out[it] = hits;
    }
    return cand_total;
}

/* Affine addition on y^2 + xy = x^3 + a2 x^2 + b (P != +-Q, both finite), for checking. */
void ec_add_one(int n, u64 mod, u64 a2, u64 x1, u64 y1, u64 x2, u64 y2, u64 *x3, u64 *y3)
{
    set_field(n, mod);
    u64 lam = gf_mul(y1 ^ y2, gf_inv(x1 ^ x2));
    u64 x = gf_mul(lam, lam) ^ lam ^ x1 ^ x2 ^ a2;
    *y3 = gf_mul(lam, x1 ^ x) ^ x ^ y1;
    *x3 = x;
}

/*
 * The rho step: W independent r-adding walks P_i <- P_i + T[x(P_i) mod T], affine, with one
 * Montgomery batch inversion per round (as in batched rho implementations).  Runs `rounds` rounds;
 * returns the number of additions performed (degenerate x1 = x2 steps are skipped).
 */
long long ec_walk_batch(int n, u64 mod, u64 a2, int W, int rounds, u64 *X, u64 *Y, const u64 *TX,
                        const u64 *TY, int T)
{
    set_field(n, mod);
    u64 *den = malloc(sizeof(u64) * (size_t)W), *pre = malloc(sizeof(u64) * (size_t)W);
    int *sel = malloc(sizeof(int) * (size_t)W);
    long long adds = 0;
    for (int r = 0; r < rounds; r++) {
        u64 acc = 1;
        for (int i = 0; i < W; i++) {
            sel[i] = (int)(X[i] % (u64)T);
            den[i] = X[i] ^ TX[sel[i]];
            if (!den[i]) den[i] = 1;
            acc = gf_mul(acc, den[i]);
            pre[i] = acc;
        }
        u64 inv = gf_inv(acc);
        for (int i = W - 1; i >= 0; i--) {
            u64 invi = i ? gf_mul(inv, pre[i - 1]) : inv;
            inv = gf_mul(inv, den[i]);
            if (X[i] == TX[sel[i]]) continue;
            u64 lam = gf_mul(Y[i] ^ TY[sel[i]], invi);
            u64 x = gf_mul(lam, lam) ^ lam ^ X[i] ^ TX[sel[i]] ^ a2;
            Y[i] = gf_mul(lam, X[i] ^ x) ^ x ^ Y[i];
            X[i] = x;
            adds++;
        }
    }
    free(den); free(pre); free(sel);
    return adds;
}
