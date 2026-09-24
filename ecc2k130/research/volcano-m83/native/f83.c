// Fast F_(2^83) curve arithmetic for the m=83 volcano factor-base studies,
// loaded from Sage/Python with ctypes (see scripts/f83lib.py).
//
// Field: F_2[z]/(z^83 + z^7 + z^4 + z^2 + 1), elements as fe {lo, hi} with
// bit i the coefficient of z^i -- the same integer encoding as scripts/m83.py.
// Curve: y^2 + xy = x^3 + b.  #E = 4 ELL for every curve in the isogeny class,
// E(F_q)[4] is cyclic, and a point's Z/4 tag is the index of [ELL]P in <T>.
// Sign 0 of an x-coordinate is the lift with the smaller y encoding, the
// convention of run01_comparison.py.
#include <arm_neon.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

typedef unsigned __int128 u128;
typedef uint64_t u64;

typedef struct {
    u64 lo, hi;
} fe;

#define M 83
static const u128 MASK = (((u128)1) << M) - 1;

static inline u128 F(fe a) { return (u128)a.lo | ((u128)a.hi << 64); }
static inline fe G(u128 a) {
    fe r = {(u64)a, (u64)(a >> 64)};
    return r;
}

static inline u128 pm(u64 a, u64 b) {
    uint64x2_t v = vreinterpretq_u64_p128(vmull_p64((poly64_t)a, (poly64_t)b));
    return (u128)vgetq_lane_u64(v, 0) | ((u128)vgetq_lane_u64(v, 1) << 64);
}

static inline u128 red(u128 lo, u128 hi) {
    u128 H = (lo >> M) | (hi << (128 - M));
    u128 L = lo & MASK;
    L ^= H ^ (H << 2) ^ (H << 4) ^ (H << 7);
    u128 H2 = L >> M;
    L &= MASK;
    return L ^ H2 ^ (H2 << 2) ^ (H2 << 4) ^ (H2 << 7);
}

static inline u128 mul(u128 a, u128 b) {
    u64 a0 = (u64)a, a1 = (u64)(a >> 64), b0 = (u64)b, b1 = (u64)(b >> 64);
    u128 p0 = pm(a0, b0), p1 = pm(a0, b1) ^ pm(a1, b0), p2 = pm(a1, b1);
    return red(p0 ^ (p1 << 64), (p1 >> 64) ^ p2);
}

static inline u128 sqr(u128 a) { return red(pm((u64)a, (u64)a), pm((u64)(a >> 64), (u64)(a >> 64))); }

static inline u128 sqrn(u128 a, int n) {
    while (n--) a = sqr(a);
    return a;
}

// Itoh-Tsujii, 82 = 1010010b
static u128 inv(u128 a) {
    u128 b1 = a;
    u128 b2 = mul(sqr(b1), b1);
    u128 b4 = mul(sqrn(b2, 2), b2);
    u128 b5 = mul(sqr(b4), a);
    u128 b10 = mul(sqrn(b5, 5), b5);
    u128 b20 = mul(sqrn(b10, 10), b10);
    u128 b40 = mul(sqrn(b20, 20), b20);
    u128 b41 = mul(sqr(b40), a);
    u128 b82 = mul(sqrn(b41, 41), b41);
    return sqr(b82);
}

static u128 TRMASK;
static u128 HT_TABLE[11][256];   // half-trace, byte-sliced linear map
static int ready;

static inline int trace(u128 a) {
    u128 v = a & TRMASK;
    return (__builtin_popcountll((u64)v) + __builtin_popcountll((u64)(v >> 64))) & 1;
}

static u128 halftrace_slow(u128 c) {
    u128 s = c, t = c;
    for (int i = 0; i < 41; i++) {
        t = sqr(sqr(t));
        s ^= t;
    }
    return s;
}

static inline u128 halftrace(u128 c) {
    u128 s = 0;
    for (int i = 0; i < 11; i++) s ^= HT_TABLE[i][(c >> (8 * i)) & 0xff];
    return s;
}

static void init(void) {
    if (ready) return;
    for (int i = 0; i < M; i++) {
        u128 x = ((u128)1) << i, t = 0, s = x;
        for (int k = 0; k < M; k++) {
            t ^= s;
            s = sqr(s);
        }
        if (t) TRMASK |= ((u128)1) << i;
    }
    for (int byte = 0; byte < 11; byte++)
        for (int v = 0; v < 256; v++) {
            u128 c = ((u128)v << (8 * byte)) & MASK;
            HT_TABLE[byte][v] = halftrace_slow(c);
        }
    ready = 1;
}

// ---- curve arithmetic, affine; infinity is flagged by inf = 1 ----
typedef struct {
    u128 x, y;
    int inf;
} pt;

static u128 B;

static inline pt padd(pt P, pt Q) {
    if (P.inf) return Q;
    if (Q.inf) return P;
    pt R = {0, 0, 0};
    if (P.x == Q.x) {
        if (P.y != Q.y || P.x == 0) {   // P = -Q (or 2-torsion doubled)
            R.inf = 1;
            return R;
        }
        u128 lam = P.x ^ mul(P.y, inv(P.x));
        R.x = sqr(lam) ^ lam;
        R.y = sqr(P.x) ^ mul(lam ^ 1, R.x);
        return R;
    }
    u128 d = P.x ^ Q.x;
    u128 lam = mul(P.y ^ Q.y, inv(d));
    R.x = sqr(lam) ^ lam ^ d;
    R.y = mul(lam, P.x ^ R.x) ^ R.x ^ P.y;
    return R;
}

static inline pt pneg(pt P) {
    P.y ^= P.x;
    return P;
}

static pt pmul(pt P, const uint8_t *bits, int nbits) {
    pt R = {0, 0, 1};
    for (int i = 0; i < nbits; i++) {
        R = padd(R, R);
        if (bits[i]) R = padd(R, P);
    }
    return R;
}

// ELL = 2417851639230796216685689, big-endian bits
static uint8_t ELLBITS[96];
static int ELLN;

static void init_ell(void) {
    if (ELLN) return;
    u128 ell = 0;
    for (const char *p = "2417851639230796216685689"; *p; p++) ell = ell * 10 + (u128)(*p - '0');
    int top = 127;
    while (!((ell >> top) & 1)) top--;
    for (int i = top; i >= 0; i--) ELLBITS[ELLN++] = (uint8_t)((ell >> i) & 1);
}

// lift: returns 0 if x is not rational; else sign-0 point (smaller y)
static int lift(u128 x, pt *P) {
    if (x == 0) return 0;
    u128 ix = inv(x);
    u128 c = x ^ mul(B, sqr(ix));
    if (trace(c)) return 0;
    u128 z = halftrace(c);
    u128 y0 = mul(x, z), y1 = y0 ^ x;
    P->x = x;
    P->y = y0 < y1 ? y0 : y1;
    P->inf = 0;
    return 1;
}

static int same(pt P, pt Q) {
    if (P.inf || Q.inf) return P.inf == Q.inf;
    return P.x == Q.x && P.y == Q.y;
}

// ---- exported API (ctypes) ----

// out[mask] = 1 iff sum_{i in mask} basis[i] is a nonzero rational x.
void f83_ratx(fe b, const fe *basis, int k, uint8_t *out) {
    init();
    B = F(b);
    u64 n = 1ull << k;
    u128 x = 0;
    out[0] = 0;
    // Gray code walk; batch the inversions in blocks.
    enum { BLK = 256 };
    u128 xs[BLK], pre[BLK];
    u64 idx[BLK];
    int cnt = 0;
    for (u64 g = 1; g <= n; g++) {
        if (g < n) {
            int j = __builtin_ctzll(g);
            x ^= F(basis[j]);
            u64 mask = g ^ (g >> 1);
            if (x == 0) {
                out[mask] = 0;   // dependent basis: x = 0 is never a factor-base x
            } else {
                xs[cnt] = x;
                idx[cnt] = mask;
                cnt++;
            }
        }
        if (cnt == BLK || (g == n && cnt)) {
            pre[0] = xs[0];
            for (int i = 1; i < cnt; i++) pre[i] = mul(pre[i - 1], xs[i]);
            u128 iv = inv(pre[cnt - 1]);
            for (int i = cnt - 1; i >= 0; i--) {
                u128 ixi = i ? mul(iv, pre[i - 1]) : iv;
                if (i) iv = mul(iv, xs[i]);
                u128 c = xs[i] ^ mul(B, sqr(ixi));
                out[idx[i]] = (uint8_t)(trace(c) == 0);
            }
            cnt = 0;
        }
    }
}

// Count rational x in the subspace for several nested dimensions at once:
// counts[d] = #rational nonzero x in span(basis[0..d)), d = 0..k.
void f83_ratx_nested(fe b, const fe *basis, int k, u64 *counts) {
    uint8_t *out = malloc((size_t)1 << k);
    f83_ratx(b, basis, k, out);
    for (int d = 0; d <= k; d++) counts[d] = 0;
    for (u64 mask = 1; mask < (1ull << k); mask++) {
        if (!out[mask]) continue;
        int top = 63 - __builtin_clzll(mask);
        for (int d = top + 1; d <= k; d++) counts[d]++;
    }
    free(out);
}

// Lift n x-coordinates (all must be rational); ys[i] = sign-0 y, tags[i] = Z/4 tag
// of the sign-0 point (the sign-1 tag is -tag).  T is the first [ELL]P of order 4
// in input order (else the first nonzero, tag 2).  Returns 0, or -1 if some x
// does not lift.
int f83_points(fe b, const fe *xs, int n, fe *ys, uint8_t *tags) {
    init();
    init_ell();
    B = F(b);
    pt *tors = malloc(sizeof(pt) * (size_t)n);
    for (int i = 0; i < n; i++) {
        pt P;
        if (!lift(F(xs[i]), &P)) {
            free(tors);
            return -1;
        }
        ys[i] = G(P.y);
        tors[i] = pmul(P, ELLBITS, ELLN);
    }
    pt T = {0, 0, 1};
    int order4 = 0;
    for (int i = 0; i < n; i++) {
        if (tors[i].inf) continue;
        pt D = padd(tors[i], tors[i]);
        if (!D.inf) {
            T = tors[i];
            order4 = 1;
            break;
        }
    }
    if (!order4)
        for (int i = 0; i < n; i++)
            if (!tors[i].inf) {
                T = tors[i];
                break;
            }
    pt mult[4];
    mult[0].inf = 1;
    mult[1] = T;
    mult[2] = padd(T, T);
    mult[3] = padd(mult[2], T);
    for (int i = 0; i < n; i++) {
        int z = -1;
        if (order4) {
            for (int j = 0; j < 4; j++)
                if (same(tors[i], mult[j])) z = j;
        } else {
            z = tors[i].inf ? 0 : 2;
        }
        if (z < 0) {
            free(tors);
            return -2;
        }
        tags[i] = (uint8_t)z;
    }
    free(tors);
    return 0;
}

// sorting helper for 256-bit keys
typedef struct {
    u64 w[4];
    u64 id;   // packed witness
} key_t_;

static int keycmp(const void *a, const void *b) {
    const key_t_ *x = a, *y = b;
    for (int i = 3; i >= 0; i--) {
        if (x->w[i] != y->w[i]) return x->w[i] < y->w[i] ? -1 : 1;
    }
    return 0;
}

static inline key_t_ mkkey(pt P, u64 id) {
    key_t_ k;
    k.w[0] = (u64)P.x;
    k.w[1] = (u64)(P.x >> 64);
    k.w[2] = (u64)P.y;
    k.w[3] = (u64)(P.y >> 64);
    k.id = id;
    return k;
}

// Exact s-summand image, s = 3 or 4, over n signed points with distinct x.
// stats[0] = all signed tuples, [1] = infinity tuples, [2] = distinct finite sums,
// [3] = eligible (tag sum 0 mod 4), [4] = eligible infinity, [5] = distinct
// eligible targets, [6] = eligible duplicate excess.  Witness ids pack the signed
// point index 2i+sign of summand t into bits 16t..16t+15.
// dup_out (optional) receives (group, id) pairs for every member of a repeated
// eligible target; targets_out (optional) receives distinct eligible targets as
// (x, y) pairs, and target_ids (optional) one witness id per target.
// Returns the number of duplicate members.
static void push(key_t_ **arr, long *cnt, long *cap, key_t_ k) {
    if (*cnt == *cap) {
        *cap *= 2;
        *arr = realloc(*arr, sizeof(key_t_) * (size_t)*cap);
    }
    (*arr)[(*cnt)++] = k;
}

long f83_image_ref(fe b, const fe *xs, const fe *ys, const uint8_t *tags, int n, int s, u64 *stats,
                   u64 *dup_out, long dup_cap, fe *targets_out, u64 *target_ids, long targets_cap) {
    init();
    B = F(b);
    pt *P = malloc(sizeof(pt) * (size_t)n * 2);
    uint8_t *tg = malloc((size_t)n * 2);
    for (int i = 0; i < n; i++) {
        P[2 * i].x = F(xs[i]);
        P[2 * i].y = F(ys[i]);
        P[2 * i].inf = 0;
        P[2 * i + 1] = pneg(P[2 * i]);
        tg[2 * i] = tags[i];
        tg[2 * i + 1] = (uint8_t)((4 - tags[i]) & 3);
    }
    long cap = 1 << 16, cnt = 0, ecap = 1 << 16, ecnt = 0;
    key_t_ *all = malloc(sizeof(key_t_) * (size_t)cap), *elig = malloc(sizeof(key_t_) * (size_t)ecap);
    u64 total = 0, infc = 0, einf = 0, eligible = 0;
    int idx[4] = {0, 0, 0, 0};
    int last = n - s;
    // iterate increasing index tuples idx[0] < ... < idx[s-1]
    for (int t = 0; t < s; t++) idx[t] = t;
    while (n >= s) {
        for (int sg = 0; sg < (1 << s); sg++) {
            pt S = {0, 0, 1};
            int tsum = 0;
            u64 id = 0;
            for (int t = 0; t < s; t++) {
                int e = 2 * idx[t] + ((sg >> t) & 1);
                S = padd(S, P[e]);
                tsum += tg[e];
                id |= (u64)e << (16 * t);
            }
            total++;
            if (S.inf) infc++;
            else push(&all, &cnt, &cap, mkkey(S, id));
            if ((tsum & 3) == 0) {
                eligible++;
                if (S.inf) einf++;
                else push(&elig, &ecnt, &ecap, mkkey(S, id));
            }
        }
        int t = s - 1;
        while (t >= 0 && idx[t] == last + t) t--;
        if (t < 0) break;
        idx[t]++;
        for (int u = t + 1; u < s; u++) idx[u] = idx[u - 1] + 1;
    }
    qsort(all, (size_t)cnt, sizeof(key_t_), keycmp);
    u64 dist = 0;
    for (long i = 0; i < cnt; i++)
        if (i == 0 || keycmp(&all[i], &all[i - 1])) dist++;
    qsort(elig, (size_t)ecnt, sizeof(key_t_), keycmp);
    u64 edist = 0;
    long nd = 0, nt = 0;
    for (long i = 0; i < ecnt;) {
        long j = i + 1;
        while (j < ecnt && !keycmp(&elig[j], &elig[i])) j++;
        if (targets_out && nt < targets_cap) {
            targets_out[2 * nt].lo = elig[i].w[0];
            targets_out[2 * nt].hi = elig[i].w[1];
            targets_out[2 * nt + 1].lo = elig[i].w[2];
            targets_out[2 * nt + 1].hi = elig[i].w[3];
            if (target_ids) target_ids[nt] = elig[i].id;
            nt++;
        }
        if (j - i > 1)
            for (long u = i; u < j; u++) {
                if (dup_out && nd < dup_cap) {
                    dup_out[2 * nd] = edist;
                    dup_out[2 * nd + 1] = elig[u].id;
                }
                nd++;
            }
        edist++;
        i = j;
    }
    stats[0] = total;
    stats[1] = infc;
    stats[2] = dist;
    stats[3] = eligible;
    stats[4] = einf;
    stats[5] = edist;
    stats[6] = eligible - einf - edist;
    free(all);
    free(elig);
    free(P);
    free(tg);
    return nd;
}

// Scalar multiple (for tests): out = [k]P with k given as big-endian bits.
int f83_scalar(fe b, fe x, fe y, const uint8_t *bits, int nbits, fe *ox, fe *oy) {
    init();
    B = F(b);
    pt P = {F(x), F(y), 0};
    pt R = pmul(P, bits, nbits);
    if (R.inf) return 1;
    *ox = G(R.x);
    *oy = G(R.y);
    return 0;
}

int f83_add(fe b, fe x1, fe y1, fe x2, fe y2, fe *ox, fe *oy) {
    init();
    B = F(b);
    pt P = {F(x1), F(y1), 0}, Q = {F(x2), F(y2), 0};
    pt R = padd(P, Q);
    if (R.inf) return 1;
    *ox = G(R.x);
    *oy = G(R.y);
    return 0;
}

fe f83_mul(fe a, fe b) { return G(mul(F(a), F(b))); }
fe f83_inv(fe a) { return G(inv(F(a))); }
int f83_trace(fe a) {
    init();
    return trace(F(a));
}
fe f83_halftrace(fe a) {
    init();
    return G(halftrace(F(a)));
}

// ---- four-summand probes through a sorted pair table ----
// Table: every unordered pair a < b of distinct x with all four signs, keyed by
// the point S = +-P_a +-P_b.  A target T decomposes as S_i + S_j with the four
// indices distinct; counting only hits whose index sets satisfy a < b < c < d
// counts each signed decomposition {a, b, c, d} exactly once.
// table_stats: [0] entries, [1] distinct sums, [2] collision excess.
// counts[t] = decompositions of target t; witnesses (optional) receive up to
// wcap (target, id_ab, id_cd) triples.
static long find_first(const key_t_ *tab, long n, const key_t_ *k) {
    long lo = 0, hi = n;
    while (lo < hi) {
        long mid = (lo + hi) / 2;
        if (keycmp(&tab[mid], k) < 0) lo = mid + 1;
        else hi = mid;
    }
    return lo;
}

long f83_pair_probe(fe b, const fe *xs, const fe *ys, int n, const fe *tx, const fe *ty, int ntargets,
                    u64 *counts, u64 *witnesses, long wcap, u64 *table_stats) {
    init();
    B = F(b);
    long entries = 4L * n * (n - 1) / 2;
    key_t_ *tab = malloc(sizeof(key_t_) * (size_t)(entries > 0 ? entries : 1));
    long e = 0;
    for (int a = 0; a < n; a++)
        for (int c = a + 1; c < n; c++)
            for (int sg = 0; sg < 4; sg++) {
                pt P = {F(xs[a]), F(ys[a]), 0}, Q = {F(xs[c]), F(ys[c]), 0};
                if (sg & 1) P = pneg(P);
                if (sg & 2) Q = pneg(Q);
                pt S = padd(P, Q);
                u64 id = ((u64)(2 * a + (sg & 1))) | ((u64)(2 * c + ((sg >> 1) & 1)) << 16);
                tab[e++] = mkkey(S, id);   // distinct x, so S is never infinity
            }
    qsort(tab, (size_t)e, sizeof(key_t_), keycmp);
    u64 dist = 0;
    for (long i = 0; i < e; i++)
        if (i == 0 || keycmp(&tab[i], &tab[i - 1])) dist++;
    table_stats[0] = (u64)e;
    table_stats[1] = dist;
    table_stats[2] = (u64)e - dist;
    long nw = 0;
    for (int t = 0; t < ntargets; t++) {
        pt T = {F(tx[t]), F(ty[t]), 0};
        u64 cnt = 0;
        for (long i = 0; i < e; i++) {
            u64 id = tab[i].id;
            int ia = (int)((id & 0xffff) >> 1), ib = (int)(((id >> 16) & 0xffff) >> 1);
            pt S = {((u128)tab[i].w[1] << 64) | tab[i].w[0], ((u128)tab[i].w[3] << 64) | tab[i].w[2], 0};
            pt D = padd(T, pneg(S));
            if (D.inf) continue;
            key_t_ k = mkkey(D, 0);
            for (long j = find_first(tab, e, &k); j < e && !keycmp(&tab[j], &k); j++) {
                u64 jd = tab[j].id;
                int ic = (int)((jd & 0xffff) >> 1), id2 = (int)(((jd >> 16) & 0xffff) >> 1);
                if (!(ib < ic)) continue;          // a < b < c < d
                (void)id2;
                cnt++;
                if (witnesses && nw < wcap) {
                    witnesses[3 * nw] = (u64)t;
                    witnesses[3 * nw + 1] = id;
                    witnesses[3 * nw + 2] = jd;
                }
                nw++;
            }
            (void)ia;
        }
        counts[t] = cnt;
    }
    free(tab);
    return nw;
}

// out[i] = in[i]^(2^n), n reduced mod 83 (relative Frobenius transport of coordinates).
void f83_frobn(const fe *in, fe *out, long count, int n) {
    n %= M;
    if (n < 0) n += M;
    for (long i = 0; i < count; i++) {
        u128 x = F(in[i]);
        for (int j = 0; j < n; j++) x = sqr(x);
        out[i] = G(x);
    }
}

// Pp + P[2c + t] for c in [c0, n), t in {0, 1}; one field inversion per call
// (Montgomery's trick over the denominators x_Pp + x_c).
static void add_batch(pt Pp, const pt *P, int c0, int n, pt *out, u128 *d, u128 *pre) {
    int cnt = n - c0;
    if (cnt <= 0) return;
    if (Pp.inf) {
        for (int i = 0; i < cnt; i++) {
            out[2 * i] = P[2 * (c0 + i)];
            out[2 * i + 1] = P[2 * (c0 + i) + 1];
        }
        return;
    }
    for (int i = 0; i < cnt; i++) {
        u128 v = Pp.x ^ P[2 * (c0 + i)].x;
        d[i] = v ? v : 1;
        pre[i] = i ? mul(pre[i - 1], d[i]) : d[i];
    }
    u128 iv = inv(pre[cnt - 1]);
    for (int i = cnt - 1; i >= 0; i--) {
        u128 id = i ? mul(iv, pre[i - 1]) : iv;
        if (i) iv = mul(iv, d[i]);
        const pt *Q0 = &P[2 * (c0 + i)];
        if (Pp.x == Q0->x) {                 // doubling or inverse pair: rare, exact fallback
            out[2 * i] = padd(Pp, Q0[0]);
            out[2 * i + 1] = padd(Pp, Q0[1]);
            continue;
        }
        u128 dx = Pp.x ^ Q0->x;
        for (int t = 0; t < 2; t++) {
            u128 lam = mul(Pp.y ^ Q0[t].y, id);
            pt R;
            R.x = sqr(lam) ^ lam ^ dx;
            R.y = mul(lam, Pp.x ^ R.x) ^ R.x ^ Pp.y;
            R.inf = 0;
            out[2 * i + t] = R;
        }
    }
}

long f83_image(fe b, const fe *xs, const fe *ys, const uint8_t *tags, int n, int s, u64 *stats,
               u64 *dup_out, long dup_cap, fe *targets_out, u64 *target_ids, long targets_cap) {
    init();
    B = F(b);
    pt *P = malloc(sizeof(pt) * (size_t)(n > 0 ? n : 1) * 2);
    uint8_t *tg = malloc((size_t)(n > 0 ? n : 1) * 2);
    for (int i = 0; i < n; i++) {
        P[2 * i].x = F(xs[i]);
        P[2 * i].y = F(ys[i]);
        P[2 * i].inf = 0;
        P[2 * i + 1] = pneg(P[2 * i]);
        tg[2 * i] = tags[i];
        tg[2 * i + 1] = (uint8_t)((4 - tags[i]) & 3);
    }
    long cap = 1 << 16, cnt = 0, ecap = 1 << 16, ecnt = 0;
    key_t_ *all = malloc(sizeof(key_t_) * (size_t)cap), *elig = malloc(sizeof(key_t_) * (size_t)ecap);
    u64 total = 0, infc = 0, einf = 0, eligible = 0;
    pt *outb = malloc(sizeof(pt) * (size_t)(2 * (n > 0 ? n : 1)));
    u128 *d = malloc(sizeof(u128) * (size_t)(n > 0 ? n : 1)), *pre = malloc(sizeof(u128) * (size_t)(n > 0 ? n : 1));
    int idx[4] = {0, 0, 0, 0};
    int p = s - 1;                   // prefix length
    if (n >= s) {
        for (int t = 0; t < p; t++) idx[t] = t;
        while (1) {
            for (int sg = 0; sg < (1 << p); sg++) {
                pt Pp = {0, 0, 1};
                int tsum = 0;
                u64 id = 0;
                for (int t = 0; t < p; t++) {
                    int e = 2 * idx[t] + ((sg >> t) & 1);
                    Pp = padd(Pp, P[e]);
                    tsum += tg[e];
                    id |= (u64)e << (16 * t);
                }
                int c0 = idx[p - 1] + 1;
                add_batch(Pp, P, c0, n, outb, d, pre);
                for (int i = 0; i < n - c0; i++)
                    for (int t2 = 0; t2 < 2; t2++) {
                        int e = 2 * (c0 + i) + t2;
                        pt S = outb[2 * i + t2];
                        u64 fid = id | ((u64)e << (16 * p));
                        int ts = tsum + tg[e];
                        total++;
                        if (S.inf) infc++;
                        else push(&all, &cnt, &cap, mkkey(S, fid));
                        if ((ts & 3) == 0) {
                            eligible++;
                            if (S.inf) einf++;
                            else push(&elig, &ecnt, &ecap, mkkey(S, fid));
                        }
                    }
            }
            // next prefix with room for a last index after it
            int t = p - 1;
            while (t >= 0 && idx[t] == n - s + t) t--;
            if (t < 0) break;
            idx[t]++;
            for (int u = t + 1; u < p; u++) idx[u] = idx[u - 1] + 1;
        }
    }
    qsort(all, (size_t)cnt, sizeof(key_t_), keycmp);
    u64 dist = 0;
    for (long i = 0; i < cnt; i++)
        if (i == 0 || keycmp(&all[i], &all[i - 1])) dist++;
    qsort(elig, (size_t)ecnt, sizeof(key_t_), keycmp);
    u64 edist = 0;
    long nd = 0, nt = 0;
    for (long i = 0; i < ecnt;) {
        long j = i + 1;
        while (j < ecnt && !keycmp(&elig[j], &elig[i])) j++;
        if (targets_out && nt < targets_cap) {
            targets_out[2 * nt].lo = elig[i].w[0];
            targets_out[2 * nt].hi = elig[i].w[1];
            targets_out[2 * nt + 1].lo = elig[i].w[2];
            targets_out[2 * nt + 1].hi = elig[i].w[3];
            if (target_ids) target_ids[nt] = elig[i].id;
            nt++;
        }
        if (j - i > 1)
            for (long u = i; u < j; u++) {
                if (dup_out && nd < dup_cap) {
                    dup_out[2 * nd] = edist;
                    dup_out[2 * nd + 1] = elig[u].id;
                }
                nd++;
            }
        edist++;
        i = j;
    }
    stats[0] = total;
    stats[1] = infc;
    stats[2] = dist;
    stats[3] = eligible;
    stats[4] = einf;
    stats[5] = edist;
    stats[6] = eligible - einf - edist;
    free(all);
    free(elig);
    free(P);
    free(tg);
    free(outb);
    free(d);
    free(pre);
    return nd;
}
