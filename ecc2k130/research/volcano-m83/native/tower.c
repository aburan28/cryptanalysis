// See tower.h.
#include "tower.h"

#include <arm_neon.h>
#include <pthread.h>
#include <stdlib.h>
#include <string.h>

#ifndef KARATSUBA_CUTOFF
#define KARATSUBA_CUTOFF 24
#endif

static inline uint64x2_t pm(u64 a, u64 b) {
    return vreinterpretq_u64_p128(vmull_p64((poly64_t)a, (poly64_t)b));
}

static inline u128 pm128(u64 a, u64 b) {
    uint64x2_t v = pm(a, b);
    return (u128)vgetq_lane_u64(v, 0) | ((u128)vgetq_lane_u64(v, 1) << 64);
}

// c[2n] = a[n] b[n], diagonal accumulation with four independent XOR chains.
static void school(u64 *c, const u64 *a, const u64 *b, size_t n) {
    u64 carry = 0;
    for (size_t k = 0; k + 1 < 2 * n; k++) {
        size_t lo = k < n ? 0 : k - n + 1, hi = k < n ? k : n - 1;
        uint64x2_t acc0 = vdupq_n_u64(0), acc1 = acc0, acc2 = acc0, acc3 = acc0;
        size_t i = lo;
        const u64 *bb = b + k;
        for (; i + 3 <= hi; i += 4) {
            acc0 = veorq_u64(acc0, pm(a[i], bb[-(long)i]));
            acc1 = veorq_u64(acc1, pm(a[i + 1], bb[-(long)i - 1]));
            acc2 = veorq_u64(acc2, pm(a[i + 2], bb[-(long)i - 2]));
            acc3 = veorq_u64(acc3, pm(a[i + 3], bb[-(long)i - 3]));
        }
        for (; i <= hi; i++) acc0 = veorq_u64(acc0, pm(a[i], bb[-(long)i]));
        acc0 = veorq_u64(veorq_u64(acc0, acc1), veorq_u64(acc2, acc3));
        c[k] = vgetq_lane_u64(acc0, 0) ^ carry;
        carry = vgetq_lane_u64(acc0, 1);
    }
    c[2 * n - 1] = carry;
}

size_t clmul_scratch_words(size_t n) {
    if (n <= KARATSUBA_CUTOFF) return 0;
    size_t H = n - n / 2;
    return 4 * H + clmul_scratch_words(H);
}

void clmul(u64 *c, const u64 *a, const u64 *b, size_t n, u64 *s) {
    if (n <= KARATSUBA_CUTOFF) {
        school(c, a, b, n);
        return;
    }
    size_t h = n / 2, H = n - h;
    u64 *sa = s, *sb = s + H, *mid = s + 2 * H, *rest = s + 4 * H;
    for (size_t i = 0; i < H; i++) {
        sa[i] = a[h + i] ^ (i < h ? a[i] : 0);
        sb[i] = b[h + i] ^ (i < h ? b[i] : 0);
    }
    clmul(c, a, b, h, rest);
    clmul(c + 2 * h, a + h, b + h, H, rest);
    clmul(mid, sa, sb, H, rest);
    for (size_t i = 0; i < 2 * h; i++) mid[i] ^= c[i];
    for (size_t i = 0; i < 2 * H; i++) mid[i] ^= c[2 * h + i];
    for (size_t i = 0; i < 2 * H; i++) c[h + i] ^= mid[i];
}

// V = lo + hi 2^128 with deg V <= 2m-2, reduced mod f.
static inline u128 reduce_f(const tower *T, u128 lo, u128 hi) {
    int m = T->m;
    u128 H = (lo >> m) | (hi << (128 - m));
    u128 L = lo & T->mask;
    L ^= H;
    for (int i = 0; i < T->nftaps; i++) L ^= H << T->ftaps[i];
    u128 H2 = L >> m;
    L &= T->mask;
    L ^= H2;
    for (int i = 0; i < T->nftaps; i++) L ^= H2 << T->ftaps[i];
    return L;
}

u128 fm_mul(const tower *T, u128 a, u128 b) {
    u64 a0 = (u64)a, a1 = (u64)(a >> 64), b0 = (u64)b, b1 = (u64)(b >> 64);
    u128 p0 = pm128(a0, b0);
    if (T->m <= 64) return reduce_f(T, p0, 0);
    u128 p1 = pm128(a0, b1) ^ pm128(a1, b0), p2 = pm128(a1, b1);
    return reduce_f(T, p0 ^ (p1 << 64), (p1 >> 64) ^ p2);
}

u128 fm_sqr(const tower *T, u128 a) {
    u64 a0 = (u64)a, a1 = (u64)(a >> 64);
    if (T->m <= 64) return reduce_f(T, pm128(a0, a0), 0);
    return reduce_f(T, pm128(a0, a0), pm128(a1, a1));
}

u128 fm_inv(const tower *T, u128 a) {
    // a^(2^m - 2) = prod_{i=1}^{m-1} a^(2^i)
    u128 r = 1, s = a;
    for (int i = 1; i < T->m; i++) {
        s = fm_sqr(T, s);
        r = fm_mul(T, r, s);
    }
    return r;
}

int fm_trace(const tower *T, u128 a) {
    u128 v = a & T->trmask;
    return (__builtin_popcountll((u64)v) + __builtin_popcountll((u64)(v >> 64))) & 1;
}

int tower_init(tower *T, int m, const int *ftaps, int nftaps, int r, const int *gtaps, int ngtaps) {
    memset(T, 0, sizeof *T);
    if (m < 2 || m > 120 || nftaps > 4 || ngtaps > 4) return -1;
    T->m = m;
    T->nftaps = nftaps;
    for (int i = 0; i < nftaps; i++) T->ftaps[i] = ftaps[i];
    T->mask = (((u128)1) << m) - 1;
    T->r = r;
    T->ngtaps = ngtaps;
    for (int i = 0; i < ngtaps; i++) T->gtaps[i] = gtaps[i];
    // Tr(z^i) = Tr of basis element: compute by m squarings of z^i.
    for (int i = 0; i < m; i++) {
        u128 x = ((u128)1) << i, s = x, t = 0;
        for (int k = 0; k < m; k++) {
            t ^= s;
            s = fm_sqr(T, s);
        }
        if (t != 0 && t != 1) return -2;
        if (t) T->trmask |= ((u128)1) << i;
    }
    // Newton identities over F_2 for the power sums p_k = Tr(Y^k) of g.
    uint8_t *e = calloc((size_t)r + 1, 1);
    T->ytrace = calloc((size_t)r, 1);
    e[r] = 1;
    for (int i = 0; i < ngtaps; i++) e[r - gtaps[i]] = 1;
    T->ytrace[0] = (uint8_t)(r & 1);
    for (int k = 1; k < r; k++) {
        int p = (k & 1) ? e[k] : 0;
        for (int i = 1; i < k; i++)
            if (e[i]) p ^= T->ytrace[k - i];
        T->ytrace[k] = (uint8_t)p;
    }
    free(e);
    T->S = (2 * m - 1 + 63) / 64;
    T->W = (m + 63) / 64;
    T->slot = 2 * m - 1;
    T->nwords = ((size_t)T->slot * (size_t)r + 64 + 63) / 64;
    T->threads = 1;
    T->pa = calloc(T->nwords, 8);
    T->pb = calloc(T->nwords, 8);
    T->pc = calloc(2 * T->nwords, 8);
    T->scratch = calloc(clmul_scratch_words(T->nwords) + 16, 8);
    T->wide = calloc(2 * (size_t)r, sizeof(u128));
    size_t H = T->nwords - T->nwords / 2;
    T->tsa = calloc(4 * H + 16, 8);
    T->tscratch = calloc(3 * (clmul_scratch_words(H) + 16), 8);
    return 0;
}

void tower_free(tower *T) {
    free(T->ytrace);
    free(T->pa);
    free(T->pb);
    free(T->pc);
    free(T->scratch);
    free(T->wide);
    free(T->tsa);
    free(T->tscratch);
}

u128 *tw_alloc(const tower *T) { return calloc((size_t)T->r, sizeof(u128)); }
void tw_copy(const tower *T, u128 *c, const u128 *a) { memmove(c, a, (size_t)T->r * sizeof(u128)); }
void tw_zero(const tower *T, u128 *c) { memset(c, 0, (size_t)T->r * sizeof(u128)); }
void tw_one(const tower *T, u128 *c) {
    tw_zero(T, c);
    c[0] = 1;
}
int tw_is_zero(const tower *T, const u128 *a) {
    for (int i = 0; i < T->r; i++)
        if (a[i]) return 0;
    return 1;
}
int tw_equal(const tower *T, const u128 *a, const u128 *b) {
    return memcmp(a, b, (size_t)T->r * sizeof(u128)) == 0;
}
void tw_add(const tower *T, u128 *c, const u128 *a, const u128 *b) {
    for (int i = 0; i < T->r; i++) c[i] = a[i] ^ b[i];
}

static void reduce_g(tower *T, u128 *c) {
    u128 *w = T->wide;
    int r = T->r;
    for (int d = 2 * r - 2; d >= r; d--) {
        u128 x = w[d];
        if (!x) continue;
        w[d - r] ^= x;
        for (int i = 0; i < T->ngtaps; i++) w[d - r + T->gtaps[i]] ^= x;
    }
    memcpy(c, w, (size_t)r * sizeof(u128));
}

typedef struct {
    u64 *c;
    const u64 *a, *b;
    size_t n;
    u64 *s;
} clmul_job;

static void *clmul_thread(void *p) {
    clmul_job *j = p;
    clmul(j->c, j->a, j->b, j->n, j->s);
    return NULL;
}

// One Karatsuba level with its three products on separate threads.
static void clmul_top(tower *T, u64 *c, const u64 *a, const u64 *b, size_t n) {
    if (T->threads < 2 || n <= 4 * KARATSUBA_CUTOFF) {
        clmul(c, a, b, n, T->scratch);
        return;
    }
    size_t h = n / 2, H = n - h;
    u64 *sa = T->tsa, *sb = T->tsa + H, *mid = T->tsa + 2 * H;
    for (size_t i = 0; i < H; i++) {
        sa[i] = a[h + i] ^ (i < h ? a[i] : 0);
        sb[i] = b[h + i] ^ (i < h ? b[i] : 0);
    }
    size_t per = clmul_scratch_words(H) + 16;
    clmul_job jobs[3] = {{c, a, b, h, T->tscratch},
                         {c + 2 * h, a + h, b + h, H, T->tscratch + per},
                         {mid, sa, sb, H, T->tscratch + 2 * per}};
    pthread_t th[2];
    pthread_create(&th[0], NULL, clmul_thread, &jobs[0]);
    pthread_create(&th[1], NULL, clmul_thread, &jobs[1]);
    clmul_thread(&jobs[2]);
    pthread_join(th[0], NULL);
    pthread_join(th[1], NULL);
    for (size_t i = 0; i < 2 * h; i++) mid[i] ^= c[i];
    for (size_t i = 0; i < 2 * H; i++) mid[i] ^= c[2 * h + i];
    for (size_t i = 0; i < 2 * H; i++) c[h + i] ^= mid[i];
}

// Coefficient i occupies bits [B i, B i + m) with slot width B = 2m - 1.
static void pack(const tower *T, u64 *p, const u128 *a) {
    memset(p, 0, T->nwords * 8);
    size_t B = (size_t)T->slot;
    for (int i = 0; i < T->r; i++) {
        size_t off = B * (size_t)i, w = off >> 6, s = off & 63;
        u128 v = a[i];
        p[w] ^= (u64)(v << s);
        if (s) {
            u128 rest = v >> (64 - s);
            p[w + 1] ^= (u64)rest;
            if (w + 2 < T->nwords) p[w + 2] ^= (u64)(rest >> 64);
        } else {
            p[w + 1] ^= (u64)(v >> 64);
        }
    }
}

// bits [off, off + 2m - 1) of p as (lo, hi)
static inline void extract(const tower *T, const u64 *p, size_t off, u128 *lo, u128 *hi) {
    size_t w = off >> 6, s = off & 63, last = 2 * T->nwords;
    u64 x[5];
    for (int k = 0; k < 5; k++) x[k] = (w + k < last) ? p[w + k] : 0;
    u64 y[4];
    for (int k = 0; k < 4; k++) y[k] = s ? (x[k] >> s) | (x[k + 1] << (64 - s)) : x[k];
    int bits = 2 * T->m - 1;
    if (bits < 256) {
        if (bits <= 192) y[3] = 0;
        if (bits <= 128) y[2] = 0;
        int top = bits & 63;
        int idx = bits >> 6;
        if (idx < 4 && top) y[idx] &= (((u64)1) << top) - 1;
        for (int k = idx + 1; k < 4; k++) y[k] = 0;
    }
    *lo = (u128)y[0] | ((u128)y[1] << 64);
    *hi = (u128)y[2] | ((u128)y[3] << 64);
}

void tw_mul(tower *T, u128 *c, const u128 *a, const u128 *b) {
    pack(T, T->pa, a);
    pack(T, T->pb, b);
    clmul_top(T, T->pc, T->pa, T->pb, T->nwords);
    size_t B = (size_t)T->slot;
    for (int k = 0; k < 2 * T->r - 1; k++) {
        u128 lo, hi;
        extract(T, T->pc, B * (size_t)k, &lo, &hi);
        T->wide[k] = reduce_f(T, lo, hi);
    }
    reduce_g(T, c);
}

void tw_sqr(tower *T, u128 *c, const u128 *a) {
    for (int i = 0; i < T->r; i++) {
        T->wide[2 * i] = fm_sqr(T, a[i]);
        T->wide[2 * i + 1] = 0;
    }
    reduce_g(T, c);
}

void tw_scale(const tower *T, u128 *c, const u128 *a, u128 s) {
    for (int i = 0; i < T->r; i++) c[i] = fm_mul(T, a[i], s);
}

void tw_inv(tower *T, u128 *c, const u128 *a) {
    // Itoh-Tsujii: a^-1 = (a^(2^(N-1)-1))^2 with N = m r.
    long k = (long)T->m * T->r - 1;
    int top = 63 - __builtin_clzl((unsigned long)k);
    u128 *beta = tw_alloc(T), *t = tw_alloc(T);
    tw_copy(T, beta, a);
    long cur = 1;
    for (int bit = top - 1; bit >= 0; bit--) {
        tw_copy(T, t, beta);
        for (long i = 0; i < cur; i++) tw_sqr(T, t, t);
        tw_mul(T, beta, t, beta);
        cur *= 2;
        if ((k >> bit) & 1) {
            tw_sqr(T, beta, beta);
            tw_mul(T, beta, beta, a);
            cur += 1;
        }
    }
    tw_sqr(T, c, beta);
    free(beta);
    free(t);
}

void tw_frob_q(tower *T, u128 *c, const u128 *a) {
    tw_copy(T, c, a);
    for (int i = 0; i < T->m; i++) tw_sqr(T, c, c);
}

u128 tw_trace_q(const tower *T, const u128 *a) {
    u128 s = 0;
    for (int i = 0; i < T->r; i++)
        if (T->ytrace[i]) s ^= a[i];
    return s;
}

int tw_trace2(const tower *T, const u128 *a) { return fm_trace(T, tw_trace_q(T, a)); }
