// Portable (x86-64 PCLMUL) F_(2^83) curve arithmetic for the volcano-m83 twist study.
//
// Field: F_2[z]/(z^83 + z^7 + z^4 + z^2 + 1), the encoding of ../../volcano-m83
// (bit i = coefficient of z^i).  Curve: y^2 + xy = x^3 + a2 x^2 + b, a2 in {0,1}.
// The group order is N = n * h with n the large prime and h the cofactor; every
// prime-power part of h is cyclic for the curves studied (asserted at run time).
//
//   f83x tags A2 B N H FACTORS K BASIS...
//       FACTORS = "p1^e1,p2^e2,..." of H.  For every nonzero x in span(BASIS)
//       (masks 1..2^K-1) with a rational lift, prints "mask tag", where tag is the
//       discrete log of [n]P in Z/h for the sign-0 lift P (smaller y encoding)
//       relative to a fixed generator of E(F_q)[h].  A point is eligible to sit in
//       a relation exactly through its tag: a signed sum lies in the prime
//       subgroup iff its tags sum to 0 mod h.  Header line "points C".
//       Self-checks: [N]R = O, exact order h of the generator, tag homomorphism.
//   f83x rho ...  (Pollard rho on the prime subgroup; see cmd_rho)
//   f83x count H   < tags (one per line)
//       Exact number of (4-subset, sign vector) pairs with signed tag sum 0 mod h,
//       the quantity run06_four_summand.py's eligible4() computes for h = 4.
//
// No discrete logarithm in the prime subgroup is computed.
#include <immintrin.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef unsigned __int128 u128;
typedef uint64_t u64;
typedef uint32_t u32;
#define M 83
static const u128 MASK = (((u128)1) << M) - 1;

static inline u128 pm(u64 a, u64 b)
{
    __m128i r = _mm_clmulepi64_si128(_mm_set_epi64x(0, (long long)a), _mm_set_epi64x(0, (long long)b), 0);
    return (u128)(u64)_mm_cvtsi128_si64(r) | ((u128)(u64)_mm_extract_epi64(r, 1) << 64);
}
static inline u128 red(u128 lo, u128 hi)
{
    u128 H = (lo >> M) | (hi << (128 - M));
    u128 L = lo & MASK;
    L ^= H ^ (H << 2) ^ (H << 4) ^ (H << 7);
    u128 H2 = L >> M;
    L &= MASK;
    return L ^ H2 ^ (H2 << 2) ^ (H2 << 4) ^ (H2 << 7);
}
static inline u128 fmul(u128 a, u128 b)
{
    u64 a0 = (u64)a, a1 = (u64)(a >> 64), b0 = (u64)b, b1 = (u64)(b >> 64);
    u128 l = pm(a0, b0), h = pm(a1, b1), m = pm(a0 ^ a1, b0 ^ b1) ^ l ^ h;
    return red(l ^ (m << 64), h ^ (m >> 64));
}
static inline u128 fsqr(u128 a) { return fmul(a, a); }
static inline u128 fsqrn(u128 a, int n) { while (n--) a = fsqr(a); return a; }
static u128 finv(u128 a)
{
    u128 b1 = a, b2 = fmul(fsqr(b1), b1), b4 = fmul(fsqrn(b2, 2), b2), b8 = fmul(fsqrn(b4, 4), b4);
    u128 b16 = fmul(fsqrn(b8, 8), b8), b32 = fmul(fsqrn(b16, 16), b16), b64 = fmul(fsqrn(b32, 32), b32);
    u128 b80 = fmul(fsqrn(b64, 16), b16), b82 = fmul(fsqrn(b80, 2), b2);
    return fsqr(b82);
}
static u128 TRMASK;
static int ftr(u128 a)
{
    u128 v = a & TRMASK;
    return (__builtin_popcountll((u64)v) + __builtin_popcountll((u64)(v >> 64))) & 1;
}
static u128 fhalftrace(u128 c)
{
    u128 r = c, t = c;
    for (int i = 0; i < (M - 1) / 2; i++) { t = fsqrn(t, 2); r ^= t; }
    return r;
}
static void init_trace(void)
{
    TRMASK = 0;
    for (int i = 0; i < M; i++) {
        u128 e = ((u128)1) << i, t = e, s = e;
        for (int k = 1; k < M; k++) { t = fsqr(t); s ^= t; }
        if (s & 1) TRMASK |= e;   // Tr(z^i) is 0 or 1
    }
}

typedef struct { u128 x, y; int inf; } pt;
static u128 A2, B;
static u64 OPS;
static const pt INF = {0, 0, 1};
static pt padd(pt P, pt Q);
static pt pdbl(pt P)
{
    OPS++;
    if (P.inf || P.x == 0) return INF;
    u128 l = P.x ^ fmul(P.y, finv(P.x));
    u128 x3 = fsqr(l) ^ l ^ A2;
    pt R = {x3, fsqr(P.x) ^ fmul(l ^ 1, x3), 0};
    return R;
}
static pt padd(pt P, pt Q)
{
    if (P.inf) return Q;
    if (Q.inf) return P;
    if (P.x == Q.x) {
        if ((P.y ^ Q.y) == Q.x) { OPS++; return INF; }
        return pdbl(P);
    }
    OPS++;
    u128 l = fmul(P.y ^ Q.y, finv(P.x ^ Q.x));
    u128 x3 = fsqr(l) ^ l ^ P.x ^ Q.x ^ A2;
    pt R = {x3, fmul(l, P.x ^ x3) ^ x3 ^ P.y, 0};
    return R;
}
static pt pneg(pt P) { if (!P.inf) P.y ^= P.x; return P; }
static pt pmulk(u128 k, pt P)
{
    pt R = INF;
    for (int i = 127; i >= 0; i--) {
        R = pdbl(R);
        if ((k >> i) & 1) R = padd(R, P);
    }
    return R;
}
static int peq(pt P, pt Q) { return P.inf ? Q.inf : (!Q.inf && P.x == Q.x && P.y == Q.y); }
static int lift(u128 x, pt *P)
{
    if (x == 0) return 0;
    u128 ix = finv(x);
    u128 c = x ^ A2 ^ fmul(B, fsqr(ix));
    if (ftr(c)) return 0;
    u128 y = fmul(x, fhalftrace(c)), y2 = y ^ x;
    P->x = x; P->y = y < y2 ? y : y2; P->inf = 0;
    return 1;
}
static u64 rs = 0x9e3779b97f4a7c15ULL;
static u64 rnd(void) { rs ^= rs << 13; rs ^= rs >> 7; rs ^= rs << 17; return rs; }
static u128 rfield(void) { return (((u128)rnd() << 64) | rnd()) & MASK; }

static u128 parse_u128(const char *s, int base)
{
    u128 v = 0;
    for (; *s; s++) {
        int d = (*s >= '0' && *s <= '9') ? *s - '0' : (*s | 32) - 'a' + 10;
        v = v * base + d;
    }
    return v;
}

// ---- tags in Z/h: Pohlig-Hellman over cyclic prime-power parts, BSGS per prime ----
#define MAXF 8
static int nf;
static u64 fp[MAXF], fe_[MAXF], fq[MAXF];       // prime, exponent, p^e
static pt Tl[MAXF], Gam[MAXF];                  // generator of the p^e part, its order-p element
static u64 bm[MAXF];                            // BSGS step size
static u64 *bkey[MAXF]; static u32 *bval[MAXF]; static u64 bsz[MAXF];
static u64 h_;
static u64 xkey(pt P) { return P.inf ? 0x5bd1e9955bd1e995ULL : ((u64)P.x ^ (u64)(P.x >> 64) * 0x9e3779b97f4a7c15ULL) ^ (u64)P.y * 31; }
static void bs_insert(int f, u64 key, u32 j)
{
    u64 i = key & (bsz[f] - 1);
    while (bkey[f][i] != 0 && bkey[f][i] != key + 1) i = (i + 1) & (bsz[f] - 1);
    if (bkey[f][i] == 0) { bkey[f][i] = key + 1; bval[f][i] = j; }
}
static int bs_find(int f, u64 key, u32 *j)
{
    u64 i = key & (bsz[f] - 1);
    while (bkey[f][i] != 0) { if (bkey[f][i] == key + 1) { *j = bval[f][i]; return 1; } i = (i + 1) & (bsz[f] - 1); }
    return 0;
}
static void bsgs_setup(int f)
{
    u64 p = fp[f], m = 1;
    while (m * m < p) m++;
    bm[f] = m; bsz[f] = 1; while (bsz[f] < 4 * m) bsz[f] <<= 1;
    bkey[f] = calloc(bsz[f], 8); bval[f] = calloc(bsz[f], 4);
    pt P = INF;
    for (u64 j = 0; j < m; j++) { bs_insert(f, xkey(P), (u32)j); P = padd(P, Gam[f]); }
}
static u64 dlog_p(int f, pt Z)   // Z in <Gam[f]>, order p
{
    u64 m = bm[f]; pt step = pneg(pmulk(m, Gam[f])), Y = Z; u32 j;
    for (u64 i = 0; i <= m; i++) {
        if (bs_find(f, xkey(Y), &j)) {
            u64 r = (i * m + j) % fp[f];
            if (peq(pmulk(r, Gam[f]), Z)) return r;
        }
        Y = padd(Y, step);
    }
    fprintf(stderr, "dlog_p failed\n"); exit(3);
}
static u128 NPRIME;
static u64 mulmod(u64 a, u64 b, u64 m) { return (u64)((u128)a * b % m); }
static u64 powm(u64 a, u64 e, u64 m) { u64 r = 1 % m; while (e) { if (e & 1) r = mulmod(r, a, m); a = mulmod(a, a, m); e >>= 1; } return r; }
static u64 tag_of(pt P)
{
    pt U = pmulk(NPRIME, P);
    u64 t = 0;
    for (int f = 0; f < nf; f++) {
        pt V = pmulk(h_ / fq[f], U);          // in the p^e part
        u64 x = 0, pk = 1;
        for (u64 i = 0; i < fe_[f]; i++) {
            pt W = padd(V, pneg(pmulk(x, Tl[f])));
            u64 c = 1; for (u64 r = i + 1; r < fe_[f]; r++) c *= fp[f];
            u64 d = dlog_p(f, pmulk(c, W));
            x += d * pk; pk *= fp[f];
        }
        // CRT: t = x mod q_f
        u64 Mf = h_ / fq[f], inv = powm(Mf % fq[f], fq[f] - fq[f] / fp[f] - 1, fq[f]);  // phi(q)-1
        t = (t + mulmod(mulmod(x, inv, h_), Mf % h_, h_)) % h_;
    }
    return t;
}

static int cmd_tags(int argc, char **argv)
{
    if (argc < 9) return 2;
    A2 = parse_u128(argv[2], 10); B = parse_u128(argv[3], 16);
    u128 N = parse_u128(argv[4], 10); h_ = (u64)parse_u128(argv[5], 10);
    NPRIME = N / h_;
    if (NPRIME * h_ != N) { fprintf(stderr, "h does not divide N\n"); return 2; }
    char *fs = strdup(argv[6]); nf = 0;
    for (char *tok = strtok(fs, ","); tok; tok = strtok(NULL, ",")) {
        char *c = strchr(tok, '^'); fp[nf] = strtoull(tok, NULL, 10); fe_[nf] = c ? strtoull(c + 1, NULL, 10) : 1;
        fq[nf] = 1; for (u64 i = 0; i < fe_[nf]; i++) fq[nf] *= fp[nf]; nf++;
    }
    { u64 prod = 1; for (int f = 0; f < nf; f++) prod *= fq[f]; if (prod != h_) { fprintf(stderr, "bad factors\n"); return 2; } }
    int K = atoi(argv[7]);
    if (argc < 8 + K) return 2;
    u128 basis[64];
    for (int i = 0; i < K; i++) basis[i] = parse_u128(argv[8 + i], 16);
    rs ^= (u64)B ^ (u64)(B >> 64) * 0x2545F4914F6CDD1DULL ^ (u64)A2;
    for (int i = 0; i < 10; i++) rnd();
    // generator of E[h]: [n]R of exact order h, with [N]R = O checked
    pt T;
    int checks = 0;
    for (;;) {
        pt R; if (!lift(rfield(), &R)) continue;
        if (!pmulk(N, R).inf) { fprintf(stderr, "order check failed: [N]R != O\n"); return 4; }
        checks++;
        T = pmulk(NPRIME, R);
        int ok = 1;
        for (int f = 0; f < nf && ok; f++) if (pmulk(h_ / fp[f], T).inf) ok = 0;
        if (ok) break;
        if (checks > 2000) { fprintf(stderr, "no generator of E[h]: h-part not cyclic?\n"); return 5; }
    }
    for (int f = 0; f < nf; f++) {
        Tl[f] = pmulk(h_ / fq[f], T);
        Gam[f] = pmulk(fq[f] / fp[f], Tl[f]);
        bsgs_setup(f);
    }
    u64 total = (u64)1 << K, cnt = 0;
    u64 *masks = malloc(total * 8), *tags = malloc(total * 8);
    pt *pts = malloc(total * sizeof(pt));
    for (u64 m = 1; m < total; m++) {
        u128 x = 0;
        for (int i = 0; i < K; i++) if (m >> i & 1) x ^= basis[i];
        pt P;
        if (!lift(x, &P)) continue;
        masks[cnt] = m; pts[cnt] = P; tags[cnt] = tag_of(P); cnt++;
    }
    // self-check: tag is a homomorphism (tag(P_i + P_j) = t_i + t_j, tag(-P) = -t)
    for (int s = 0; s < 24 && cnt >= 2; s++) {
        u64 i = rnd() % cnt, j = rnd() % cnt;
        pt S = padd(pts[i], pts[j]);
        if (S.inf) continue;
        if (tag_of(S) != (tags[i] + tags[j]) % h_ || tag_of(pneg(pts[i])) != (h_ - tags[i]) % h_) {
            fprintf(stderr, "tag homomorphism check failed\n"); return 6;
        }
    }
    printf("points %llu order_checks %d ops %llu\n", (unsigned long long)cnt, checks, (unsigned long long)OPS);
    for (u64 i = 0; i < cnt; i++) printf("%llu %llu\n", (unsigned long long)masks[i], (unsigned long long)tags[i]);
    return 0;
}

// ---- exact eligible signed 4-subsets: sweep over the split {a<b} | {c<d}, b < c ----
static u64 *hk, *hc, hsz;
static inline void hinc(u64 key)
{
    u64 i = (key * 0x9E3779B97F4A7C15ULL) & (hsz - 1);
    while (hk[i] && hk[i] != key + 1) i = (i + 1) & (hsz - 1);
    hk[i] = key + 1; hc[i]++;
}
static inline u64 hget(u64 key)
{
    u64 i = (key * 0x9E3779B97F4A7C15ULL) & (hsz - 1);
    while (hk[i]) { if (hk[i] == key + 1) return hc[i]; i = (i + 1) & (hsz - 1); }
    return 0;
}
static int cmd_count(int argc, char **argv)
{
    if (argc < 3) return 2;
    u64 h = strtoull(argv[2], NULL, 10), cap = 1 << 16, n = 0, v;
    u64 *t = malloc(cap * 8);
    while (scanf("%llu", (unsigned long long *)&v) == 1) {
        if (n == cap) t = realloc(t, (cap *= 2) * 8);
        t[n++] = v % h;
    }
    u64 entries = 4 * (n * (n - 1) / 2) + 16;
    hsz = 1; while (hsz < 2 * (entries < h ? entries : h) + 16) hsz <<= 1;
    hk = calloc(hsz, 8); hc = calloc(hsz, 8);
    u128 total = 0;
    for (u64 c = 0; c < n; c++) {
        if (c >= 1) {
            u64 b = c - 1;
            for (u64 a = 0; a < b; a++) {
                u64 p = (t[a] + t[b]) % h, q = (t[a] + h - t[b]) % h;
                hinc(p); hinc((h - p) % h); hinc(q); hinc((h - q) % h);
            }
        }
        for (u64 d = c + 1; d < n; d++) {
            u64 p = (t[c] + t[d]) % h, q = (t[c] + h - t[d]) % h;
            total += hget((h - p) % h) + hget(p) + hget((h - q) % h) + hget(q);
        }
    }
    unsigned long long hi = (unsigned long long)(total >> 64), lo = (unsigned long long)total;
    if (hi) printf("eligible_overflow %llu %llu n %llu\n", hi, lo, (unsigned long long)n);
    else printf("eligible %llu n %llu\n", lo, (unsigned long long)n);
    return 0;
}


// ---- Pollard rho on the prime subgroup (same arithmetic as the yield census) ----
//
//   f83x rho A2 B N H MODE LAMBDA SEED DPBITS
//       MODE 0: plain r-adding walk; 1: classes {+-P}; 2: classes {+-tau^i P} (crater only:
//       LAMBDA is the eigenvalue of tau on <G>, checked as [LAMBDA]G = (x^2, y^2)).
//       r = 32 adding walk, distinguished points (bits 1..DPBITS of the canonical x; bit 0 is
//       pinned by Tr(x) = Tr(a2) in this basis, Tr = bits {0, 79, 81}),
//       next-index rule against 2-cycles, cycle detection over the last 32 states with a
//       deterministic doubling escape, and a walk-length cap.  The target Q = [k]G is a
//       fixture from SEED; the recovered k is checked against it and by [k]G = Q.
//       Prints one "rho ..." line of counters.
#define RR 32
typedef struct { pt P; u64 a, b; } st;
static u64 NN, LAMP[M];
static int MODE;
static u64 SQR;
static u64 addm(u64 x, u64 y) { u64 s = x + y; return s >= NN ? s - NN : s; }
static u64 negm(u64 x) { return x ? NN - x : 0; }
static void canon(st *s)
{
    if (MODE == 2 && !s->P.inf) {
        u128 x = s->P.x, best = x; int bi = 0;
        for (int i = 1; i < M; i++) {
            x = fsqr(x); SQR++;
            if (x < best) { best = x; bi = i; }
        }
        s->P.x = best; s->P.y = fsqrn(s->P.y, bi); SQR += bi;
        s->a = mulmod(s->a, LAMP[bi], NN); s->b = mulmod(s->b, LAMP[bi], NN);
    }
    if (MODE >= 1 && !s->P.inf && (s->P.y ^ s->P.x) < s->P.y) {
        s->P.y ^= s->P.x; s->a = negm(s->a); s->b = negm(s->b);
    }
}
static inline int pidx(pt P) { return P.inf ? 0 : (int)((((u64)(P.x >> 20)) * 0x9E3779B97F4A7C15ULL) >> 59); }
typedef struct { u64 key; u128 x; u64 a, b; } dpe;
static dpe *dpt; static u64 dpsz, dpn;
static int cmd_rho(int argc, char **argv)
{
    if (argc < 10) return 2;
    A2 = parse_u128(argv[2], 10); B = parse_u128(argv[3], 16);
    u128 N = parse_u128(argv[4], 10); u128 H = parse_u128(argv[5], 10);
    MODE = atoi(argv[6]); u64 lam = strtoull(argv[7], NULL, 10);
    u64 seed = strtoull(argv[8], NULL, 10); int d = atoi(argv[9]);
    NPRIME = N / H; NN = (u64)NPRIME;
    if (NPRIME * H != N || NPRIME >> 63) { fprintf(stderr, "bad N/H\n"); return 2; }
    rs ^= seed * 0x2545F4914F6CDD1DULL ^ (u64)B; for (int i = 0; i < 20; i++) rnd();
    pt G;
    for (;;) { pt R; if (!lift(rfield(), &R)) continue; G = pmulk(H, R); if (!G.inf) break; }
    if (!pmulk(NPRIME, G).inf) { fprintf(stderr, "G not in the prime subgroup\n"); return 4; }
    u64 k = rnd() % NN; pt Q = pmulk(k, G);            // fixture, outside every counter below
    if (MODE == 2) {
        pt tG = {fsqr(G.x), fsqr(G.y), 0};
        if (!peq(pmulk(lam, G), tG)) { fprintf(stderr, "lambda is not tau on <G>\n"); return 7; }
        LAMP[0] = 1; for (int i = 1; i < M; i++) LAMP[i] = mulmod(LAMP[i - 1], lam, NN);
    }
    u64 setup0 = OPS;
    st Rm[RR];
    for (int j = 0; j < RR; j++) {
        Rm[j].a = rnd() % NN; Rm[j].b = rnd() % NN;
        Rm[j].P = padd(pmulk(Rm[j].a, G), pmulk(Rm[j].b, Q));
    }
    u64 ops_mult = OPS - setup0;
    dpsz = 1 << 20; dpt = calloc(dpsz, sizeof(dpe)); dpn = 0;
    u64 steps = 0, walks = 0, restarts = 0, escapes = 0, start_ops = 0, wasted = 0, useless = 0;
    u64 cap = (u64)40 << d, dmask = ((u64)1 << d) - 1;
    st ring[32]; int rn;
    u64 found = 0;
    while (!found) {
        u64 o0 = OPS;
        st s; s.a = rnd() % NN; s.b = rnd() % NN; s.P = padd(pmulk(s.a, G), pmulk(s.b, Q)); canon(&s);
        start_ops += OPS - o0; walks++; rn = 0;
        u64 len = 0, dps_on_walk = 0;
        for (;;) {
            if (s.P.inf) { restarts++; wasted += len; break; }
            if ((((u64)s.P.x >> 1) & dmask) == 0) {   // bit 0 skipped: Tr(x) = Tr(a2) on the odd-order subgroup pins it for minimal conjugates
                u64 key = (u64)s.P.x ^ (u64)(s.P.x >> 64) * 0x9E3779B97F4A7C15ULL;
                u64 i = key & (dpsz - 1);
                while (dpt[i].key && !(dpt[i].key == key + 1 && dpt[i].x == s.P.x)) i = (i + 1) & (dpsz - 1);
                if (dpt[i].key) {
                    u64 db = (dpt[i].b + NN - s.b) % NN;
                    if (db) {
                        u64 kk = mulmod((s.a + NN - dpt[i].a) % NN, powm(db, NN - 2, NN), NN);
                        if (kk == k && peq(pmulk(kk, G), Q)) { found = 1; break; }
                        // sign/Frobenius ambiguity cannot occur: equal canonical points are equal points
                        fprintf(stderr, "collision gave a wrong scalar\n"); return 8;
                    }
                    useless++; wasted += len; (void)dps_on_walk; break;
                }
                dpt[i].key = key + 1; dpt[i].x = s.P.x; dpt[i].a = s.a; dpt[i].b = s.b;
                if (++dpn * 2 > dpsz) { fprintf(stderr, "DP table full\n"); return 9; }
                dps_on_walk++; len = 0;   // keep walking (van Oorschot-Wiener, one processor)
            }
            if (len > cap) { restarts++; wasted += len; break; }
            // fruitless-cycle check over the last 32 states
            if (MODE >= 1) {
                int hit = -1;
                for (int t = 0; t < rn && t < 32; t++) if (ring[t].P.x == s.P.x && !ring[t].P.inf) { hit = t; break; }
                if (hit >= 0) {
                    st m = s;
                    for (int t = 0; t < rn && t < 32; t++) if (ring[t].P.x < m.P.x) m = ring[t];
                    s.P = pdbl(m.P); s.a = addm(m.a, m.a); s.b = addm(m.b, m.b); canon(&s);
                    escapes++; steps++; len++; rn = 0;
                    continue;
                }
                ring[rn % 32] = s; rn++;
            }
            int j = pidx(s.P);
            st t = s; t.P = padd(s.P, Rm[j].P); t.a = addm(s.a, Rm[j].a); t.b = addm(s.b, Rm[j].b); canon(&t);
            if (MODE >= 1 && pidx(t.P) == j) {
                int j2 = (j + 1) % RR;
                t = s; t.P = padd(s.P, Rm[j2].P); t.a = addm(s.a, Rm[j2].a); t.b = addm(s.b, Rm[j2].b); canon(&t);
                steps++;
            }
            s = t; steps++; len++;
        }
    }
    printf("rho mode %d n %llu k_ok 1 steps %llu walks %llu start_ops %llu multiplier_ops %llu canon_squarings %llu "
           "dp_stored %llu restarts %llu escapes %llu useless_collisions %llu wasted_steps %llu total_group_ops %llu\n",
           MODE, (unsigned long long)NN, (unsigned long long)steps, (unsigned long long)walks,
           (unsigned long long)start_ops, (unsigned long long)ops_mult, (unsigned long long)SQR,
           (unsigned long long)dpn, (unsigned long long)restarts, (unsigned long long)escapes,
           (unsigned long long)useless, (unsigned long long)wasted, (unsigned long long)(OPS - setup0));
    return 0;
}

int main(int argc, char **argv)
{
    init_trace();
    if (argc >= 2 && !strcmp(argv[1], "tags")) return cmd_tags(argc, argv);
    if (argc >= 2 && !strcmp(argv[1], "count")) return cmd_count(argc, argv);
    if (argc >= 2 && !strcmp(argv[1], "rho")) return cmd_rho(argc, argv);
    fprintf(stderr, "usage: f83x tags A2 B_HEX N H FACTORS K BASIS_HEX... | f83x count H < tags\n");
    return 2;
}
