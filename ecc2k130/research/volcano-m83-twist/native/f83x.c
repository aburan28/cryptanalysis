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

int main(int argc, char **argv)
{
    init_trace();
    if (argc >= 2 && !strcmp(argv[1], "tags")) return cmd_tags(argc, argv);
    if (argc >= 2 && !strcmp(argv[1], "count")) return cmd_count(argc, argv);
    fprintf(stderr, "usage: f83x tags A2 B_HEX N H FACTORS K BASIS_HEX... | f83x count H < tags\n");
    return 2;
}
