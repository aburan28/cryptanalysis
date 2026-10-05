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

static inline u64 gf_mul(u64 a, u64 b)
{
    __m128i A = _mm_set_epi64x(0, (long long)a), B = _mm_set_epi64x(0, (long long)b);
    __m128i P = _mm_clmulepi64_si128(A, B, 0);
    u64 lo = (u64)_mm_cvtsi128_si64(P), hi = (u64)_mm_extract_epi64(P, 1);
    int n = g_n;
    /* the product has degree <= 2n - 2; reduce bits n .. 2n-2 from the top */
    for (int i = 2 * n - 2; i >= n; i--) {
        int set = i >= 64 ? (int)((hi >> (i - 64)) & 1) : (int)((lo >> i) & 1);
        if (!set) continue;
        int s = i - n;     /* x^i = x^s * x^n = x^s * mod */
        if (i >= 64) hi ^= (u64)1 << (i - 64); else lo ^= (u64)1 << i;
        /* xor mod << s into (hi, lo) */
        if (s == 0) lo ^= g_mod;
        else if (s < 64) { lo ^= g_mod << s; hi ^= s ? (g_mod >> (64 - s)) : 0; }
        else hi ^= g_mod << (s - 64);
    }
    return lo & g_mask;
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
long long ht_enum(int n, u64 mod, int d, u64 u0, u64 p0, u64 s0, const u64 *f, const u64 *pk, const u64 *sk,
                  const u64 *ht_tab, const u64 *syn_tab, u64 trmask, u64 *hits, int max_hits, long long *cand)
{
    g_n = n;
    g_mod = mod & ((n == 64) ? ~(u64)0 : (((u64)1 << n) - 1));
    g_mask = (n == 64) ? ~(u64)0 : (((u64)1 << n) - 1);
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
            if (!u) continue;
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
