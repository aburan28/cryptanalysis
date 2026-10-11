/*
 * rho.c -- Pollard rho (van Oorschot-Wiener distinguished points, r-adding walk) for
 * y^2 + x y = x^3 + a2 x^2 + b over F_{2^n} (polynomial basis, modulus z^n + tail),
 * n <= 127, in the prime-order-N subgroup (N < 2^62).
 *
 * Equivalence classes (mode):
 *   none   : class size 1 (plain points)
 *   neg    : class {P, -P}                       (size 2)
 *   negtau : class {+-tau^i P, i=0..n-1}, tau(x,y)=(x^2,y^2) acting as the scalar s on <P>
 *            (only valid on a curve defined over F_2, i.e. a2 in {0,1}, b = 1)
 * Canonical representative: negtau -> minimal x^(2^i) as an integer (bitmask), then
 * the sign with the smaller y; neg -> the sign with the smaller y.
 *
 * Walk: f(P) = canon(P + R_j), j = h(P); Wiener-Zuccherato look-ahead (if h(f(P)) == j try
 * j+1, ... up to LOOKAHEAD tries) against fruitless 2-cycles; every new point is compared
 * with the previous HIST points of the walk; a repeat with identical coefficients is a
 * fruitless cycle and is left by canon(2 * min-point of the cycle) (deterministic, so walks
 * that merge stay merged); a repeat with different coefficients solves the DLP.
 *
 * Counts per instance:
 *   iters        : point additions/doublings done by the walks (the cost measure)
 *   steps        : points generated (walk starts + transitions)
 *   merge_steps  : points generated up to and including the first point that repeats a
 *                  previously generated class (found by re-walking the two colliding
 *                  trails after the DP collision); this is the birthday time and is
 *                  compared with sqrt(pi*N/(2*classsize)).
 * Every recovered log is checked (k*P == Q) and compared with the planted k.
 *
 * Input (stdin), one key per line:
 *   n <n>\n tail <hex>\n a2 <0|1>\n b <hex>\n N <dec>\n s <dec>\n mode <none|neg|negtau>\n
 *   rbits <int>\n dpbits <int>\n maxwalk <int multiple of 1/theta>\n seed <dec>\n
 *   inst <id> <Px> <Py> <Qx> <Qy> <k>   (hex coordinates, decimal k)  ... repeated
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <time.h>
#include <arm_neon.h>

typedef unsigned __int128 u128;
typedef uint64_t u64;

#ifdef FIXN
/* compile-time field (faster): -DFIXN=<n> -DFIXTAIL=<tail> */
#    define NB     FIXN
#    define TAIL   ((u64)(FIXTAIL))
#    define MASK   ((((u128)1) << FIXN) - 1)
#    define SMALLN (FIXN <= 64)
static int NB_in;
static u64 TAIL_in;
#else
static int NB; /* n */
static u128 MASK;
static u64 TAIL; /* modulus = z^n + TAIL */
static int SMALLN;
#endif
static u128 A2, B;
static u64 NORD; /* subgroup order */
static u64 SEIG; /* tau eigenvalue */
static int MODE; /* 0 none, 1 neg, 2 negtau */
static int RBITS, DPBITS, MAXWALK;
static u64 SEED;
static u64 SPOW[128];

#define LOOKAHEAD 8
#define HIST      32

static inline u128 clmul64(u64 a, u64 b)
{
    poly128_t c = vmull_p64((poly64_t)a, (poly64_t)b);
    return (u128)c;
}

static inline u128 reduce(u128 hi, u128 lo)
{
#ifdef FIXN
    /* two unconditional folds (enough when deg(tail) is small), then the generic loop */
    for (int r = 0; r < 2; r++) {
        u128 H = (lo >> NB) | (hi << (128 - NB));
        u128 p0 = clmul64((u64)H, TAIL), p1 = SMALLN ? 0 : clmul64((u64)(H >> 64), TAIL);
        lo = (lo & MASK) ^ p0 ^ (p1 << 64);
        hi = p1 >> 64;
    }
#endif
    while (hi || (lo >> NB)) {
        u128 H = (lo >> NB) | (NB < 128 ? (hi << (128 - NB)) : 0);
        u128 p0 = clmul64((u64)H, TAIL), p1 = clmul64((u64)(H >> 64), TAIL);
        lo = (lo & MASK) ^ p0 ^ (p1 << 64);
        hi = p1 >> 64;
    }
    return lo;
}

static inline u128 fmul(u128 a, u128 b)
{
    if (SMALLN) return reduce(0, clmul64((u64)a, (u64)b));
    u64 a0 = (u64)a, a1 = (u64)(a >> 64), b0 = (u64)b, b1 = (u64)(b >> 64);
    u128 L = clmul64(a0, b0), H = clmul64(a1, b1);
    u128 M = clmul64(a0 ^ a1, b0 ^ b1) ^ L ^ H;
    return reduce(H ^ (M >> 64), L ^ (M << 64));
}
static inline u128 fsqr(u128 a)
{
    /* squaring is linear in char 2: no Karatsuba middle term */
    if (SMALLN) return reduce(0, clmul64((u64)a, (u64)a));
    u64 a0 = (u64)a, a1 = (u64)(a >> 64);
    return reduce(clmul64(a1, a1), clmul64(a0, a0));
}

/* x -> x^(2^k) is F_2-linear: 8-bit-chunk lookup tables for the k used by Itoh-Tsujii and
   for k = 1,2,4,...,64 (y^(2^i) in the tau-canonicalisation). Tables are built by repeated
   squaring and checked against it at start-up. */
static u128 *SQT[128];
static int NCHUNK;
static u128 pow2k_slow(u128 x, int k)
{
    for (int j = 0; j < k; j++) x = fsqr(x);
    return x;
}
static void build_sqt(int k)
{
    if (k < 2 || k >= 128 || SQT[k]) return;
    NCHUNK = (NB + 7) / 8;
    SQT[k] = malloc(sizeof(u128) * 256 * NCHUNK);
    for (int c = 0; c < NCHUNK; c++)
        for (int b = 0; b < 256; b++) {
            u128 v = ((u128)b << (8 * c)) & MASK;
            SQT[k][c * 256 + b] = pow2k_slow(v, k);
        }
}
static inline u128 pow2k(u128 x, int k)
{
    if (k < 2 || !SQT[k]) return pow2k_slow(x, k);
    const u128 *T = SQT[k];
    u128 r = 0;
    for (int c = 0; c < NCHUNK; c++) r ^= T[c * 256 + (int)((x >> (8 * c)) & 255)];
    return r;
}
static u128 finv(u128 a)
{
    /* Itoh-Tsujii: a^-1 = (a^(2^(n-1)-1))^2 */
    int m = NB - 1;
    int top = 63 - __builtin_clzll((u64)m);
    u128 beta = a;
    int k = 1;
    for (int i = top - 1; i >= 0; i--) {
        beta = fmul(pow2k(beta, k), beta);
        k *= 2;
        if ((m >> i) & 1) {
            beta = fmul(fsqr(beta), a);
            k += 1;
        }
    }
    return fsqr(beta);
}
static void build_all_sqt(void)
{
    int m = NB - 1, top = 63 - __builtin_clzll((u64)m), k = 1;
    for (int i = top - 1; i >= 0; i--) {
        build_sqt(k);
        k *= 2;
        if ((m >> i) & 1) k += 1;
    }
    for (int j = 1; j < NB; j *= 2) build_sqt(j);
}

typedef struct {
    u128 x, y;
    int inf;
} Pt;

static Pt pdbl(Pt P)
{
    Pt R;
    R.inf = 0;
    if (P.inf || P.x == 0) {
        R.inf = 1;
        R.x = R.y = 0;
        return R;
    }
    u128 lam = P.x ^ fmul(P.y, finv(P.x));
    R.x = fsqr(lam) ^ lam ^ A2;
    R.y = fsqr(P.x) ^ fmul(lam ^ 1, R.x);
    return R;
}
static Pt padd(Pt P, Pt Q)
{
    if (P.inf) return Q;
    if (Q.inf) return P;
    if (P.x == Q.x) {
        if (P.y == Q.y) return pdbl(P);
        Pt R;
        R.inf = 1;
        R.x = R.y = 0;
        return R;
    }
    Pt R;
    R.inf = 0;
    u128 lam = fmul(P.y ^ Q.y, finv(P.x ^ Q.x));
    R.x = fsqr(lam) ^ lam ^ P.x ^ Q.x ^ A2;
    R.y = fmul(lam, P.x ^ R.x) ^ R.x ^ P.y;
    return R;
}
static Pt pmul_affine(Pt P, u64 k)
{
    Pt R;
    R.inf = 1;
    R.x = R.y = 0;
    for (int i = 63; i >= 0; i--) {
        R = pdbl(R);
        if ((k >> i) & 1) R = padd(R, P);
    }
    return R;
}
/* Lopez-Dahab projective (x = X/Z, y = Y/Z^2) double-and-add with mixed addition
   (Hankerson-Menezes-Vanstone, Alg. 3.24/3.25 formulas); used only to speed up the
   setup (adding table, walk starts); self-tested against pmul_affine at start-up. */
typedef struct {
    u128 X, Y, Z;
} LD;
static LD ld_dbl(LD P)
{
    if (P.Z == 0 || P.X == 0) {
        LD R = {1, 0, 0};
        return R;
    }
    u128 X2 = fsqr(P.X), Z2 = fsqr(P.Z), bZ4 = fmul(B, fsqr(Z2));
    LD R;
    R.Z = fmul(X2, Z2);
    R.X = fsqr(X2) ^ bZ4;
    R.Y = fmul(bZ4, R.Z) ^ fmul(R.X, (A2 ? R.Z : 0) ^ fsqr(P.Y) ^ bZ4);
    return R;
}
static LD ld_madd(LD P, Pt Q)
{
    if (Q.inf) return P;
    if (P.Z == 0) {
        LD R = {Q.x, Q.y, 1};
        return R;
    }
    u128 Z2 = fsqr(P.Z);
    u128 A = fmul(Q.y, Z2) ^ P.Y;
    u128 Bv = fmul(Q.x, P.Z) ^ P.X;
    if (Bv == 0) {
        if (A == 0) return ld_dbl(P);
        LD R = {1, 0, 0};
        return R;
    }
    u128 C = fmul(P.Z, Bv);
    u128 D = fmul(fsqr(Bv), C ^ (A2 ? Z2 : 0));
    LD R;
    R.Z = fsqr(C);
    u128 E = fmul(A, C);
    R.X = fsqr(A) ^ D ^ E;
    u128 F = R.X ^ fmul(Q.x, R.Z);
    u128 G = fmul(Q.x ^ Q.y, fsqr(R.Z));
    R.Y = fmul(E ^ R.Z, F) ^ G;
    return R;
}
static Pt ld_affine(LD P)
{
    Pt R;
    if (P.Z == 0) {
        R.inf = 1;
        R.x = R.y = 0;
        return R;
    }
    u128 zi = finv(P.Z);
    R.inf = 0;
    R.x = fmul(P.X, zi);
    R.y = fmul(P.Y, fsqr(zi));
    return R;
}
static Pt pmul(Pt P, u64 k)
{
    if (P.inf || k == 0) {
        Pt R;
        R.inf = 1;
        R.x = R.y = 0;
        return R;
    }
    LD R = {1, 0, 0};
    for (int i = 63 - __builtin_clzll(k); i >= 0; i--) {
        R = ld_dbl(R);
        if ((k >> i) & 1) R = ld_madd(R, P);
    }
    return ld_affine(R);
}
static int on_curve(Pt P)
{
    if (P.inf) return 1;
    u128 lhs = fsqr(P.y) ^ fmul(P.x, P.y);
    u128 x2 = fsqr(P.x);
    u128 rhs = fmul(x2, P.x) ^ (A2 ? x2 : 0) ^ B;
    return lhs == rhs;
}
static int peq(Pt P, Pt Q)
{
    return (P.inf && Q.inf) || (!P.inf && !Q.inf && P.x == Q.x && P.y == Q.y);
}

static inline u64 addm(u64 a, u64 b)
{
    u64 c = a + b;
    return c >= NORD ? c - NORD : c;
}
static inline u64 subm(u64 a, u64 b) { return a >= b ? a - b : a + NORD - b; }
static inline u64 mulm(u64 a, u64 b) { return (u64)(((u128)a * b) % NORD); }
static u64 powm(u64 a, u64 e)
{
    u64 r = 1;
    while (e) {
        if (e & 1) r = mulm(r, a);
        a = mulm(a, a);
        e >>= 1;
    }
    return r;
}
static u64 invm(u64 a) { return powm(a, NORD - 2); } /* NORD prime */

/* canonicalise in place; returns multiplier m with canon(P) = m*P */
static inline u64 canon(Pt *P)
{
    if (MODE == 0) return 1;
    u64 m = 1;
    if (MODE == 2) {
        u128 u = P->x, best = P->x;
        int bi = 0;
        for (int i = 1; i < NB; i++) {
            u = fsqr(u);
            if (u < best) {
                best = u;
                bi = i;
            }
        }
        if (bi) {
            u128 y = P->y;
            for (int j = 0; (1 << j) <= bi; j++)
                if ((bi >> j) & 1) y = pow2k(y, 1 << j);
            P->x = best;
            P->y = y;
            m = SPOW[bi];
        }
    }
    u128 yn = P->y ^ P->x;
    if (yn < P->y) {
        P->y = yn;
        m = NORD - m;
    }
    return m;
}

static inline u64 hmix(u128 x)
{
    u64 h = (u64)x ^ ((u64)(x >> 64) * 0x9E3779B97F4A7C15ULL);
    h *= 0xBF58476D1CE4E5B9ULL;
    h ^= h >> 31;
    h *= 0x94D049BB133111EBULL;
    h ^= h >> 29;
    return h;
}

static u64 rng_state;
static inline u64 rnd(void)
{
    u64 z = (rng_state += 0x9E3779B97F4A7C15ULL);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
    return z ^ (z >> 31);
}

/* per-instance data */
static Pt P0, Q0;
static int RSZ;
static Pt *RT;
static u64 *RA, *RB;

typedef struct {
    u128 x;
    u64 a, b;
    Pt P;
} Hent;

typedef struct {
    u64 iters, steps, fruitless, retries, inf_hits;
} Stats;

/* one transition; returns 0 ok, 1 hit infinity */
static inline int fstep(Pt *P, u64 *a, u64 *b, Stats *st)
{
    int j = (int)(hmix(P->x) & (u64)(RSZ - 1));
    for (int t = 0; t < LOOKAHEAD; t++) {
        int jj = (j + t) & (RSZ - 1);
        Pt Q = padd(*P, RT[jj]);
        st->iters++;
        if (Q.inf) {
            st->inf_hits++;
            return 1;
        }
        u64 m = canon(&Q);
        int hj = (int)(hmix(Q.x) & (u64)(RSZ - 1));
        if (hj != jj || t == LOOKAHEAD - 1) {
            *a = mulm(m, addm(*a, RA[jj]));
            *b = mulm(m, addm(*b, RB[jj]));
            *P = Q;
            st->retries += t;
            return 0;
        }
    }
    return 0;
}

static inline int is_dp(u128 x) { return ((hmix(x) >> 32) & ((1ULL << DPBITS) - 1)) == 0; }

/* Walk result codes */
#define W_DP      0
#define W_ABANDON 1
#define W_SOLVED  2
#define W_INF     3

/* walk from (P,a,b) (already canonical) until DP / abandon / self-collision.
   If rec_set != NULL: record every point x into rec (array) up to cap.
   If probe: stop at first point whose x is in probe-set (sorted array), report index.  */
typedef struct {
    u128 x, y;
    u64 b, idx;
} XY;
typedef struct {
    XY *xs;
    u64 cnt, cap;
} XRec;

static int cmpxyi(const void *p, const void *q)
{
    const XY *a = p, *b = q;
    if (a->x != b->x) return a->x < b->x ? -1 : 1;
    if (a->y != b->y) return a->y < b->y ? -1 : 1;
    return a->idx < b->idx ? -1 : a->idx > b->idx;
}
static int cmpxy(const void *p, const void *q)
{
    const XY *a = p, *b = q;
    if (a->x != b->x) return a->x < b->x ? -1 : 1;
    if (a->y != b->y) return a->y < b->y ? -1 : 1;
    return 0;
}

/* Walk from (P,a,b) (canonical) until DP / abandon / collision inside the walk.
   Inside-walk repeats are found (i) against the last HIST points (short fruitless cycles are
   left deterministically via canon(2 * min point of the cycle)) and (ii) by Brent's cycle
   detection (saved point refreshed at len = 1, 2, 4, 8, ... steps), so that a walk that runs
   into a genuine rho cycle is solved instead of abandoned.  A repeat with different b solves
   the DLP (W_SOLVED); with identical coefficients it is fruitless and is escaped.
   rec: record every point (x, y, b, index); probe: stop at the first point in the sorted probe set.
 */
static int walk(Pt *P, u64 *a, u64 *b, u64 maxlen, Stats *st, u64 *len_out, XRec *rec,
                const XY *probe, u64 nprobe, u64 *probe_idx, u64 *ksol)
{
    Hent hist[HIST];
    int hn = 0, hpos = 0;
    u64 len = 0;
    Pt bp = *P;
    u64 ba = *a, bb = *b, blen = 0, bpow = 1;
    for (;;) {
        if (rec && rec->cnt < rec->cap) {
            XY *r = &rec->xs[rec->cnt];
            r->x = P->x;
            r->y = P->y;
            r->b = *b;
            r->idx = len;
            rec->cnt++;
        }
        if (probe) {
            XY key;
            key.x = P->x;
            key.y = P->y;
            if (bsearch(&key, probe, nprobe, sizeof(XY), cmpxy)) {
                *probe_idx = len;
                *len_out = len;
                return W_DP;
            }
        }
        if (is_dp(P->x)) {
            *len_out = len;
            return W_DP;
        }
        if (len >= maxlen) {
            *len_out = len;
            return W_ABANDON;
        }
        /* push current */
        hist[hpos].x = P->x;
        hist[hpos].a = *a;
        hist[hpos].b = *b;
        hist[hpos].P = *P;
        hpos = (hpos + 1) % HIST;
        if (hn < HIST) hn++;
        if (fstep(P, a, b, st)) {
            *len_out = len;
            return W_INF;
        }
        len++;
        st->steps++;
        int escaped = 0;
        /* (i) compare with the recent history (exact point comparison: in mode none P and -P
           are different points; in modes neg/negtau y is canonical) */
        for (int d = 1; d <= hn; d++) {
            int idx = (hpos - d + HIST) % HIST;
            if (hist[idx].x == P->x && hist[idx].P.y == P->y) {
                if (hist[idx].b != *b && ksol) {
                    /* a P0 + b Q0 = a' P0 + b' Q0 -> k = (a - a')/(b' - b) */
                    *ksol = mulm(subm(*a, hist[idx].a), invm(subm(hist[idx].b, *b)));
                    if (rec && rec->cnt < rec->cap) {
                        XY *r = &rec->xs[rec->cnt];
                        r->x = P->x;
                        r->y = P->y;
                        r->b = *b;
                        r->idx = len;
                        rec->cnt++;
                    }
                    *len_out = len;
                    return W_SOLVED;
                }
                /* fruitless cycle of length d: points hist[idx .. hpos-1] */
                st->fruitless++;
                int bi = idx;
                u128 bx = hist[idx].x;
                for (int e = 1; e < d; e++) {
                    int ii = (idx + e) % HIST;
                    if (hist[ii].x < bx) {
                        bx = hist[ii].x;
                        bi = ii;
                    }
                }
                Pt D = pdbl(hist[bi].P);
                st->iters++;
                if (D.inf) {
                    *len_out = len;
                    return W_INF;
                }
                u64 m = canon(&D);
                *a = mulm(m, addm(hist[bi].a, hist[bi].a));
                *b = mulm(m, addm(hist[bi].b, hist[bi].b));
                *P = D;
                hn = 0;
                hpos = 0;
                escaped = 1;
                break;
            }
        }
        /* (ii) Brent */
        if (!escaped && P->x == bp.x && P->y == bp.y) {
            if (bb != *b && ksol) {
                *ksol = mulm(subm(*a, ba), invm(subm(bb, *b)));
                if (rec && rec->cnt < rec->cap) {
                    XY *r = &rec->xs[rec->cnt];
                    r->x = P->x;
                    r->y = P->y;
                    r->b = *b;
                    r->idx = len;
                    rec->cnt++;
                }
                *len_out = len;
                return W_SOLVED;
            }
            /* long fruitless cycle (length len - blen > HIST): leave it via canon(2 * min point) */
            st->fruitless++;
            u64 lam = len - blen;
            Pt C = *P, Mn = *P;
            u64 ca = *a, cb = *b, ma = *a, mb = *b;
            for (u64 i = 0; i < lam; i++) {
                if (fstep(&C, &ca, &cb, st)) {
                    *len_out = len;
                    return W_INF;
                }
                if (C.x < Mn.x) {
                    Mn = C;
                    ma = ca;
                    mb = cb;
                }
            }
            Pt D = pdbl(Mn);
            st->iters++;
            if (D.inf) {
                *len_out = len;
                return W_INF;
            }
            u64 m = canon(&D);
            *a = mulm(m, addm(ma, ma));
            *b = mulm(m, addm(mb, mb));
            *P = D;
            hn = 0;
            hpos = 0;
            escaped = 1;
        }
        if (escaped || len - blen >= bpow) {
            bp = *P;
            ba = *a;
            bb = *b;
            blen = len;
            bpow = escaped ? 1 : 2 * bpow;
        }
    }
}

typedef struct {
    u128 x, y;
    u64 a, b, sa, sb, len, wid;
    int used;
} DPent;
static DPent *DT;
static u64 DTCAP, DTN;

static DPent *dp_find(u128 x, u128 y)
{
    u64 i = hmix(x) & (DTCAP - 1);
    while (DT[i].used) {
        if (DT[i].x == x && DT[i].y == y) return &DT[i];
        i = (i + 1) & (DTCAP - 1);
    }
    return NULL;
}
static void dp_insert(DPent e)
{
    if (2 * (DTN + 1) > DTCAP) {
        DPent *old = DT;
        u64 oc = DTCAP;
        DTCAP *= 2;
        DT = calloc(DTCAP, sizeof(DPent));
        DTN = 0;
        for (u64 i = 0; i < oc; i++)
            if (old[i].used) dp_insert(old[i]);
        free(old);
    }
    u64 i = hmix(e.x) & (DTCAP - 1);
    while (DT[i].used) i = (i + 1) & (DTCAP - 1);
    e.used = 1;
    DT[i] = e;
    DTN++;
}

static u128 parsehex(const char *s)
{
    u128 v = 0;
    if (s[0] == '0' && (s[1] == 'x' || s[1] == 'X')) s += 2;
    for (; *s; s++) {
        int d;
        if (*s >= '0' && *s <= '9')
            d = *s - '0';
        else if (*s >= 'a' && *s <= 'f')
            d = *s - 'a' + 10;
        else if (*s >= 'A' && *s <= 'F')
            d = *s - 'A' + 10;
        else
            break;
        v = (v << 4) | (u128)d;
    }
    return v;
}

static double now(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_PROCESS_CPUTIME_ID, &ts);
    return ts.tv_sec + 1e-9 * ts.tv_nsec;
}

static Pt mkpt(u64 a, u64 b) { return padd(pmul(P0, a), pmul(Q0, b)); }

static void solve(const char *id, u64 ktrue)
{
    double t0 = now();
    Stats st = {0};
    rng_state = SEED ^ (hmix((u128)ktrue) + 0x1234567ULL);
    for (const char *c = id; *c; c++) rng_state = rng_state * 131 + (u64)*c;
    /* adding table */
    for (int j = 0; j < RSZ; j++) {
        for (;;) {
            RA[j] = rnd() % NORD;
            RB[j] = rnd() % NORD;
            RT[j] = mkpt(RA[j], RB[j]);
            if (!RT[j].inf) break;
        }
    }
    u64 za, zb;
    Pt Z;
    do {
        za = rnd() % NORD;
        zb = rnd() % NORD;
        Z = mkpt(za, zb);
    } while (Z.inf);
    u64 sa, sb;
    Pt S;
    do {
        sa = rnd() % NORD;
        sb = rnd() % NORD;
        S = mkpt(sa, sb);
    } while (S.inf);
    double tsetup = now() - t0;

    DTCAP = 1024;
    DTN = 0;
    DT = calloc(DTCAP, sizeof(DPent));
    u64 maxlen = (u64)MAXWALK << DPBITS;
    u64 walks = 0, abandoned = 0, infw = 0, selfsolve = 0, degenerate = 0;
    u64 ksol = 0;
    int solved = 0;
    u64 merge_steps = 0;
    int merge_ok = 0;
    u64 steps_before_cur = 0;
    DPent hit = {0};
    u64 cur_sa = 0, cur_sb = 0, cur_len = 0;
    double t1 = now();
    while (!solved) {
        /* new walk start S <- S + Z */
        if (walks > 0) {
            S = padd(S, Z);
            sa = addm(sa, za);
            sb = addm(sb, zb);
            st.iters++;
        }
        if (S.inf) {
            S = Z;
            sa = za;
            sb = zb;
        }
        walks++;
        steps_before_cur = st.steps;
        st.steps++; /* the start point itself */
        Pt P = S;
        u64 a = sa, b = sb;
        u64 m = canon(&P);
        a = mulm(m, a);
        b = mulm(m, b);
        u64 wa0 = a, wb0 = b;
        u64 len;
        int rc = walk(&P, &a, &b, maxlen, &st, &len, NULL, NULL, 0, NULL, &ksol);
        if (rc == W_SOLVED) {
            solved = 1;
            selfsolve++;
            merge_steps = st.steps;
            merge_ok = 0;
            /* exact first genuine repeat inside this walk: re-walk it recording (x, y, b, idx) */
            Stats s3 = {0};
            u64 dummy, l3;
            XRec rr;
            rr.cap = len + 2;
            rr.cnt = 0;
            rr.xs = malloc(sizeof(XY) * rr.cap);
            Pt R = mkpt(wa0, wb0);
            u64 ra = wa0, rb = wb0;
            walk(&R, &ra, &rb, len, &s3, &l3, &rr, NULL, 0, NULL, &dummy);
            qsort(rr.xs, rr.cnt, sizeof(XY), cmpxyi);
            u64 first = (u64)-1;
            for (u64 i = 0; i < rr.cnt;) {
                u64 j = i;
                while (j + 1 < rr.cnt && rr.xs[j + 1].x == rr.xs[i].x &&
                       rr.xs[j + 1].y == rr.xs[i].y)
                    j++;
                /* group i..j sorted by idx: earliest element whose b differs from an earlier one */
                for (u64 e = i + 1; e <= j; e++) {
                    int diff = 0;
                    for (u64 f = i; f < e; f++)
                        if (rr.xs[f].b != rr.xs[e].b) {
                            diff = 1;
                            break;
                        }
                    if (diff) {
                        if (rr.xs[e].idx < first) first = rr.xs[e].idx;
                        break;
                    }
                }
                i = j + 1;
            }
            free(rr.xs);
            if (first != (u64)-1) {
                merge_steps = steps_before_cur + first + 1;
                merge_ok = 1;
            }
            break;
        }
        if (rc == W_ABANDON) {
            abandoned++;
            continue;
        }
        if (rc == W_INF) {
            infw++;
            continue;
        }
        DPent *e = dp_find(P.x, P.y);
        if (e) {
            if (e->b != b) {
                ksol = mulm(subm(a, e->a), invm(subm(e->b, b)));
                solved = 1;
                hit = *e;
                cur_sa = wa0;
                cur_sb = wb0;
                cur_len = len;
                break;
            }
            degenerate++;
            continue;
        }
        DPent ne = {0};
        ne.x = P.x;
        ne.y = P.y;
        ne.a = a;
        ne.b = b;
        ne.sa = wa0;
        ne.sb = wb0;
        ne.len = len;
        ne.wid = walks;
        dp_insert(ne);
    }
    double t2 = now();
    u64 walk_iters = st.iters, walk_steps = st.steps;
    /* merge point: re-walk the stored trail, then the current trail */
    if (solved && hit.used) {
        Stats s2 = {0};
        XRec rec;
        rec.cap = hit.len + 2;
        rec.cnt = 0;
        rec.xs = malloc(sizeof(XY) * rec.cap);
        Pt P = mkpt(hit.sa, hit.sb);
        u64 a = hit.sa, b = hit.sb; /* coefficients already canonical-adjusted */
        u64 m = canon(&P);
        (void)m;
        /* hit.sa/sb are the canonical start coefficients, so P = canon(mkpt(sa,sb)) = mkpt(sa,sb)
         */
        P = mkpt(hit.sa, hit.sb);
        u64 len;
        u64 dummy;
        walk(&P, &a, &b, hit.len, &s2, &len, &rec, NULL, 0, NULL, &dummy);
        qsort(rec.xs, rec.cnt, sizeof(XY), cmpxy);
        Pt C = mkpt(cur_sa, cur_sb);
        a = cur_sa;
        b = cur_sb;
        u64 pidx = (u64)-1;
        walk(&C, &a, &b, cur_len, &s2, &len, NULL, rec.xs, rec.cnt, &pidx, &dummy);
        if (pidx != (u64)-1) {
            merge_steps = steps_before_cur + pidx + 1;
            merge_ok = 1;
        }
        free(rec.xs);
    }
    /* verify */
    Pt V = pmul(P0, ksol);
    int ok = solved && peq(V, Q0);
    int match = (ksol == ktrue % NORD);
    double t3 = now();
    printf("%s\t%llu\t%llu\t%d\t%d\t%llu\t%llu\t%llu\t%d\t%llu\t%llu\t%llu\t%llu\t%llu\t%llu\t%"
           "llu\t%llu\t%.6f\t%.6f\n",
           id, (unsigned long long)(ktrue % NORD), (unsigned long long)ksol, ok, match,
           (unsigned long long)walk_iters, (unsigned long long)walk_steps,
           (unsigned long long)merge_steps, merge_ok, (unsigned long long)walks,
           (unsigned long long)DTN, (unsigned long long)abandoned, (unsigned long long)st.fruitless,
           (unsigned long long)st.retries, (unsigned long long)(infw + st.inf_hits),
           (unsigned long long)selfsolve, (unsigned long long)degenerate, t2 - t1,
           tsetup + (t3 - t2));
    fflush(stdout);
    free(DT);
}

int main(void)
{
    char line[4096];
    char key[64];
    int header_done = 0;
    while (fgets(line, sizeof line, stdin)) {
        if (sscanf(line, "%63s", key) != 1) continue;
#ifdef FIXN
        if (!strcmp(key, "n")) {
            sscanf(line, "%*s %d", &NB_in);
            if (NB_in != FIXN) {
                fprintf(stderr, "binary compiled for n=%d\n", FIXN);
                return 2;
            }
        } else if (!strcmp(key, "tail")) {
            char h[256];
            sscanf(line, "%*s %255s", h);
            TAIL_in = (u64)parsehex(h);
            if (TAIL_in != TAIL) {
                fprintf(stderr, "binary compiled for another tail\n");
                return 2;
            }
        }
#else
        if (!strcmp(key, "n")) {
            sscanf(line, "%*s %d", &NB);
        } else if (!strcmp(key, "tail")) {
            char h[256];
            sscanf(line, "%*s %255s", h);
            TAIL = (u64)parsehex(h);
        }
#endif
        else if (!strcmp(key, "a2")) {
            int v;
            sscanf(line, "%*s %d", &v);
            A2 = (u128)v;
        } else if (!strcmp(key, "b")) {
            char h[256];
            sscanf(line, "%*s %255s", h);
            B = parsehex(h);
        } else if (!strcmp(key, "N")) {
            unsigned long long v;
            sscanf(line, "%*s %llu", &v);
            NORD = v;
        } else if (!strcmp(key, "s")) {
            unsigned long long v;
            sscanf(line, "%*s %llu", &v);
            SEIG = v;
        } else if (!strcmp(key, "mode")) {
            char m[32];
            sscanf(line, "%*s %31s", m);
            MODE = !strcmp(m, "none") ? 0 : !strcmp(m, "neg") ? 1 : !strcmp(m, "negtau") ? 2 : -1;
            if (MODE < 0) {
                fprintf(stderr, "bad mode\n");
                return 2;
            }
        } else if (!strcmp(key, "rbits"))
            sscanf(line, "%*s %d", &RBITS);
        else if (!strcmp(key, "dpbits"))
            sscanf(line, "%*s %d", &DPBITS);
        else if (!strcmp(key, "maxwalk"))
            sscanf(line, "%*s %d", &MAXWALK);
        else if (!strcmp(key, "seed")) {
            unsigned long long v;
            sscanf(line, "%*s %llu", &v);
            SEED = v;
        } else if (!strcmp(key, "inst")) {
            if (!header_done) {
                if (NB < 2 || NB > 127 || !NORD || NORD >= (1ULL << 62)) {
                    fprintf(stderr, "bad params\n");
                    return 2;
                }
#ifndef FIXN
                MASK = (((u128)1) << NB) - 1;
                SMALLN = (NB <= 64);
#endif
                RSZ = 1 << RBITS;
                RT = malloc(sizeof(Pt) * RSZ);
                RA = malloc(8 * RSZ);
                RB = malloc(8 * RSZ);
                SPOW[0] = 1;
                for (int i = 1; i < NB; i++) SPOW[i] = mulm(SPOW[i - 1], SEIG % NORD);
                if (MODE == 2 && (B != 1 || A2 > 1)) {
                    fprintf(stderr, "negtau needs a Koblitz curve\n");
                    return 2;
                }
                build_all_sqt();
                /* field self-test: a * a^-1 == 1, table powers == repeated squaring */
                rng_state = 42;
                for (int i = 0; i < 50; i++) {
                    u128 a = (((u128)rnd() << 64) | rnd()) & MASK;
                    for (int k = 2; k < NB; k++)
                        if (SQT[k] && pow2k(a, k) != pow2k_slow(a, k)) {
                            fprintf(stderr, "pow2k table self-test failed\n");
                            return 3;
                        }
                }
                for (int i = 0; i < 100; i++) {
                    u128 a = (((u128)rnd() << 64) | rnd()) & MASK;
                    if (!a) continue;
                    if (fmul(a, finv(a)) != 1) {
                        fprintf(stderr, "field inverse self-test failed\n");
                        return 3;
                    }
                }
                /* (self-test of pmul vs pmul_affine happens per instance below) */
                printf("id\tk_true\tk_found\tverified\tmatch\titers\tsteps\tmerge_steps\tmerge_"
                       "ok\twalks\tdps\tabandoned\tfruitless\tretries\tinf\tselfsolve\tdegenerate\t"
                       "walk_cpu_s\tother_cpu_s\n");
                header_done = 1;
            }
            char id[128], px[256], py[256], qx[256], qy[256];
            unsigned long long k;
            if (sscanf(line, "%*s %127s %255s %255s %255s %255s %llu", id, px, py, qx, qy, &k) !=
                6) {
                fprintf(stderr, "bad inst line\n");
                return 2;
            }
            P0.x = parsehex(px);
            P0.y = parsehex(py);
            P0.inf = 0;
            Q0.x = parsehex(qx);
            Q0.y = parsehex(qy);
            Q0.inf = 0;
            if (!on_curve(P0) || !on_curve(Q0)) {
                fprintf(stderr, "%s: point not on curve\n", id);
                return 4;
            }
            for (int tt = 0; tt < 4; tt++) {
                u64 kk = rnd() % NORD;
                if (!peq(pmul(P0, kk), pmul_affine(P0, kk))) {
                    fprintf(stderr, "%s: LD scalar mult self-test failed\n", id);
                    return 5;
                }
            }
            if (!pmul_affine(P0, NORD).inf) {
                fprintf(stderr, "%s: P order != N\n", id);
                return 4;
            }
            if (!peq(pmul(P0, k % NORD), Q0)) {
                fprintf(stderr, "%s: Q != kP (input inconsistent)\n", id);
                return 4;
            }
            if (MODE == 2) {
                Pt T;
                T.inf = 0;
                T.x = fsqr(P0.x);
                T.y = fsqr(P0.y);
                if (!peq(T, pmul(P0, SEIG))) {
                    fprintf(stderr, "%s: tau(P) != s*P\n", id);
                    return 4;
                }
            }
            solve(id, k);
        }
    }
    return 0;
}
