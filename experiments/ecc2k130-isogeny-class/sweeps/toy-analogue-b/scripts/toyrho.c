/*
 * toyrho.c -- independent Pollard-rho (r-adding walk, 32 multipliers, distinguished points, parallel walks with
 * Montgomery batched inversion) and 359-isogeny transport for binary curves  y^2 + xy = x^3 + a2 x^2 + b  over
 * F_{2^179} = F_2[z]/(z^179 + z^4 + z^2 + z + 1).  Written from scratch for the toy-analogue-b experiment.
 *
 * Equivalence classes used by the walk:
 *   mode 0: {P, -P}                          (negation only; class size 2)
 *   mode 1: {+-sigma^i(P)}, sigma = (x,y)->(x^2,y^2)  (Koblitz E0 only; class size 2*179; sigma acts as s on <G>)
 * Canonical representative (mode 1): rotate the normal-basis coordinates of x to the lexicographically minimal
 * rotation, then choose the sign by min(y, y+x) as integers.  (mode 0: sign rule only.)
 * Fruitless cycles: immediate 2-cycle test + checkpoints every 64 and 2048 steps; escape = double the minimal point
 * of the cycle (deterministic, so merged walks escape identically).
 *
 * Commands (one per input line on stdin, output one JSON line per command on stdout):
 *   R id mode a2 b N s Gx Gy Hx Hy M dpbits seed          -> rho on the given curve
 *   T id b cofTw L N s Gx Gy Hx Hy M dpbits seed           -> transport floor curve [1,1,0,0,b] -> E0 via the
 *        ascending L-isogeny (kernel = rational L-subgroup of the twist [1,0,0,0,b]), then mode-1 rho on E0,
 *        then sign fix on the floor curve.   (field elements hex, integers decimal, cofTw hex)
 * build:  clang -O3 -march=armv8-a+crypto -o toyrho toyrho.c
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <time.h>
#include <arm_neon.h>

typedef unsigned __int128 u128;
#define NB 179
#define M51 ((1ULL << 51) - 1)
typedef struct { uint64_t w[3]; } fe;

static double now(void) { struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts); return ts.tv_sec + 1e-9 * ts.tv_nsec; }
static double cpu(void) { struct timespec ts; clock_gettime(CLOCK_THREAD_CPUTIME_ID, &ts); return ts.tv_sec + 1e-9 * ts.tv_nsec; }

/* ---------------- field F_{2^179} ---------------- */
static inline void clmul(uint64_t a, uint64_t b, uint64_t *lo, uint64_t *hi) {
    poly128_t r = vmull_p64((poly64_t)a, (poly64_t)b);
    uint64x2_t v = vreinterpretq_u64_p128(r);
    *lo = vgetq_lane_u64(v, 0); *hi = vgetq_lane_u64(v, 1);
}
static void clmul_soft(uint64_t a, uint64_t b, uint64_t *lo, uint64_t *hi) {   /* reference, for the self-test */
    uint64_t l = 0, h = 0;
    for (int i = 0; i < 64; i++) if ((b >> i) & 1) { l ^= a << i; if (i) h ^= a >> (64 - i); }
    *lo = l; *hi = h;
}
static inline fe reduce6(const uint64_t c[6]) {
    uint64_t h0 = (c[2] >> 51) | (c[3] << 13), h1 = (c[3] >> 51) | (c[4] << 13), h2 = (c[4] >> 51) | (c[5] << 13);
    uint64_t r0 = c[0], r1 = c[1], r2 = c[2] & M51;
    /* multiply H by z^4+z^2+z+1 */
    r0 ^= h0 ^ (h0 << 1) ^ (h0 << 2) ^ (h0 << 4);
    r1 ^= h1 ^ (h1 << 1) ^ (h1 << 2) ^ (h1 << 4) ^ (h0 >> 63) ^ (h0 >> 62) ^ (h0 >> 60);
    r2 ^= h2 ^ (h2 << 1) ^ (h2 << 2) ^ (h2 << 4) ^ (h1 >> 63) ^ (h1 >> 62) ^ (h1 >> 60);
    uint64_t top = r2 >> 51; r2 &= M51;
    r0 ^= top ^ (top << 1) ^ (top << 2) ^ (top << 4);
    fe r = {{r0, r1, r2}}; return r;
}
static inline fe fmul(fe a, fe b) {
    uint64_t c[6] = {0}, lo, hi;
    for (int i = 0; i < 3; i++) for (int j = 0; j < 3; j++) { clmul(a.w[i], b.w[j], &lo, &hi); c[i + j] ^= lo; c[i + j + 1] ^= hi; }
    return reduce6(c);
}
static fe fmul_soft(fe a, fe b) {
    uint64_t c[6] = {0}, lo, hi;
    for (int i = 0; i < 3; i++) for (int j = 0; j < 3; j++) { clmul_soft(a.w[i], b.w[j], &lo, &hi); c[i + j] ^= lo; c[i + j + 1] ^= hi; }
    return reduce6(c);
}
static inline fe fsqr(fe a) {
    uint64_t c[6];
    for (int i = 0; i < 3; i++) clmul(a.w[i], a.w[i], &c[2 * i], &c[2 * i + 1]);
    return reduce6(c);
}
static inline fe fadd(fe a, fe b) { fe r = {{a.w[0] ^ b.w[0], a.w[1] ^ b.w[1], a.w[2] ^ b.w[2]}}; return r; }
static inline int fzero(fe a) { return !(a.w[0] | a.w[1] | a.w[2]); }
static inline int feq(fe a, fe b) { return a.w[0] == b.w[0] && a.w[1] == b.w[1] && a.w[2] == b.w[2]; }
static inline int fcmp(fe a, fe b) { for (int i = 2; i >= 0; i--) { if (a.w[i] < b.w[i]) return -1; if (a.w[i] > b.w[i]) return 1; } return 0; }
static const fe FZERO = {{0, 0, 0}}, FONE = {{1, 0, 0}};
static inline fe fsqrn(fe a, int k) { while (k--) a = fsqr(a); return a; }
static fe finv(fe a) {   /* Itoh-Tsujii: a^(2^179-2) = (a^(2^178-1))^2 */
    fe b1 = a, b2 = fmul(fsqr(b1), b1), b4 = fmul(fsqrn(b2, 2), b2), b8 = fmul(fsqrn(b4, 4), b4);
    fe b16 = fmul(fsqrn(b8, 8), b8), b32 = fmul(fsqrn(b16, 16), b16), b64 = fmul(fsqrn(b32, 32), b32);
    fe b128 = fmul(fsqrn(b64, 64), b64), b160 = fmul(fsqrn(b128, 32), b32), b176 = fmul(fsqrn(b160, 16), b16);
    fe b178 = fmul(fsqrn(b176, 2), b2);
    return fsqr(b178);
}
static fe TRMASK;
static int ftrace(fe a) { uint64_t t = (a.w[0] & TRMASK.w[0]) ^ (a.w[1] & TRMASK.w[1]) ^ (a.w[2] & TRMASK.w[2]); return __builtin_popcountll(t) & 1; }
static fe fhalftrace(fe c) { fe h = c, u = c; for (int i = 1; i <= 89; i++) { u = fsqr(fsqr(u)); h = fadd(h, u); } return h; }
static void init_trace(void) {
    TRMASK = FZERO;
    for (int i = 0; i < NB; i++) {
        fe e = FZERO; e.w[i >> 6] = 1ULL << (i & 63);
        fe s = e, u = e;
        for (int k = 1; k < NB; k++) { u = fsqr(u); s = fadd(s, u); }
        if (!(fzero(s) || feq(s, FONE))) { fprintf(stderr, "trace not in F2\n"); exit(1); }
        if (feq(s, FONE)) TRMASK.w[i >> 6] |= 1ULL << (i & 63);
    }
}
static fe fhex(const char *s) {
    fe r = FZERO; if (s[0] == '0' && (s[1] == 'x' || s[1] == 'X')) s += 2;
    size_t n = strlen(s); int bit = 0;
    for (long i = (long)n - 1; i >= 0; i--, bit += 4) {
        int c = s[i], v = (c >= '0' && c <= '9') ? c - '0' : (c >= 'a' && c <= 'f') ? c - 'a' + 10 : (c >= 'A' && c <= 'F') ? c - 'A' + 10 : -1;
        if (v < 0) { fprintf(stderr, "bad hex %s\n", s); exit(1); }
        if (v && bit >= 192) { fprintf(stderr, "hex too long\n"); exit(1); }
        if (v) r.w[bit >> 6] |= (uint64_t)v << (bit & 63);
    }
    return r;
}
static void fprint(FILE *f, fe a) { fprintf(f, "\"0x%013llx%016llx%016llx\"", (unsigned long long)a.w[2], (unsigned long long)a.w[1], (unsigned long long)a.w[0]); }

/* ---------------- normal basis tables (from nb_tables.txt) ---------------- */
static fe P2N[23][256], N2P[23][256];
static void build_tab(fe tab[23][256], fe img[NB]) {
    for (int bi = 0; bi < 23; bi++) for (int v = 0; v < 256; v++) {
        fe r = FZERO; for (int k = 0; k < 8; k++) { int i = 8 * bi + k; if (i < NB && ((v >> k) & 1)) r = fadd(r, img[i]); }
        tab[bi][v] = r;
    }
}
static inline fe conv(fe tab[23][256], fe a) {
    fe r = FZERO;
    for (int bi = 0; bi < 23; bi++) { int v = (a.w[bi >> 3] >> (8 * (bi & 7))) & 0xff; r = fadd(r, tab[bi][v]); }
    return r;
}
static void load_nb(const char *path) {
    FILE *f = fopen(path, "r"); if (!f) { perror(path); exit(1); }
    static fe p2n[NB], n2p[NB]; char buf[256];
    for (int i = 0; i < NB; i++) { if (fscanf(f, "%255s", buf) != 1) exit(2); p2n[i] = fhex(buf); }
    for (int i = 0; i < NB; i++) { if (fscanf(f, "%255s", buf) != 1) exit(2); n2p[i] = fhex(buf); }
    fclose(f); build_tab(P2N, p2n); build_tab(N2P, n2p);
}
/* rotation of a 179-bit NB vector: bit i of result = bit (i-r mod 179) of c   (== sigma^r) */
static inline fe nbrot(fe c, int r) {
    if (r == 0) return c;
    /* (c << r) | (c >> (179-r)), masked */
    fe a = FZERO, b = FZERO; int q = r >> 6, s = r & 63;
    for (int i = 2; i >= 0; i--) { int src = i - q; if (src < 0) continue; uint64_t v = c.w[src] << s; if (s && src - 1 >= 0) v |= c.w[src - 1] >> (64 - s); a.w[i] = v; }
    int rr = NB - r; q = rr >> 6; s = rr & 63;
    for (int i = 0; i < 3; i++) { int src = i + q; if (src > 2) continue; uint64_t v = c.w[src] >> s; if (s && src + 1 <= 2) v |= c.w[src + 1] << (64 - s); b.w[i] = v; }
    fe r2 = fadd(a, b); r2.w[2] &= M51; return r2;
}
/* lexicographically minimal rotation: returns r and the rotated vector */
static inline int nbminrot(fe c, fe *out) {
    uint64_t D[7];
    /* D = c | c << 179  (bits 0..357) */
    D[0] = c.w[0]; D[1] = c.w[1]; D[2] = c.w[2] | (c.w[0] << 51);
    D[3] = (c.w[0] >> 13) | (c.w[1] << 51); D[4] = (c.w[1] >> 13) | (c.w[2] << 51); D[5] = (c.w[2] >> 13); D[6] = 0;
    uint64_t best = ~0ULL; int bests = -1, nties = 0; int ties[NB];
    for (int sft = 1; sft <= NB; sft++) {
        int off = sft + 115, li = off >> 6, sh = off & 63;
        uint64_t w = sh ? ((D[li] >> sh) | (D[li + 1] << (64 - sh))) : D[li];
        if (w < best) { best = w; bests = sft; nties = 0; ties[nties++] = sft; }
        else if (w == best) ties[nties++] = sft;
    }
    int r = NB - bests; fe v = nbrot(c, r);
    for (int t = 1; t < nties; t++) { int r2 = NB - ties[t]; fe v2 = nbrot(c, r2); if (fcmp(v2, v) < 0) { v = v2; r = r2; } }
    *out = v; return r;
}

/* ---------------- curve arithmetic ---------------- */
typedef struct { fe x, y; int inf; } pt;
typedef struct { fe a2, b; } curve;
static pt PINF = {{{0, 0, 0}}, {{0, 0, 0}}, 1};
static pt padd(const curve *E, pt P, pt Q);
static pt pdbl(const curve *E, pt P) {
    if (P.inf || fzero(P.x)) return PINF;
    fe l = fadd(P.x, fmul(P.y, finv(P.x)));
    pt R; R.inf = 0;
    R.x = fadd(fadd(fsqr(l), l), E->a2);
    R.y = fadd(fadd(fsqr(P.x), fmul(l, R.x)), R.x);
    return R;
}
static pt padd(const curve *E, pt P, pt Q) {
    if (P.inf) return Q; if (Q.inf) return P;
    if (feq(P.x, Q.x)) { if (feq(P.y, Q.y)) return pdbl(E, P); return PINF; }
    fe l = fmul(fadd(P.y, Q.y), finv(fadd(P.x, Q.x)));
    pt R; R.inf = 0;
    R.x = fadd(fadd(fadd(fsqr(l), l), fadd(P.x, Q.x)), E->a2);
    R.y = fadd(fadd(fmul(l, fadd(P.x, R.x)), R.x), P.y);
    return R;
}
static pt pneg(pt P) { if (!P.inf) P.y = fadd(P.y, P.x); return P; }
static int oncurve(const curve *E, pt P) {
    if (P.inf) return 1;
    fe x2 = fsqr(P.x), lhs = fadd(fsqr(P.y), fmul(P.x, P.y)), rhs = fadd(fadd(fmul(x2, P.x), fmul(E->a2, x2)), E->b);
    return feq(lhs, rhs);
}
/* Lopez-Dahab projective scalar multiplication (x = X/Z, y = Y/Z^2) */
typedef struct { fe X, Y, Z; } ldpt;
static ldpt lddbl(const curve *E, ldpt P) {
    if (fzero(P.Z)) return P;
    fe X2 = fsqr(P.X), Z2 = fsqr(P.Z), bZ4 = fmul(E->b, fsqr(Z2));
    ldpt R; R.Z = fmul(X2, Z2); R.X = fadd(fsqr(X2), bZ4);
    R.Y = fadd(fmul(bZ4, R.Z), fmul(R.X, fadd(fadd(fmul(E->a2, R.Z), fsqr(P.Y)), bZ4)));
    return R;
}
static ldpt ldaddmixed(const curve *E, ldpt P, pt Q) {
    if (Q.inf) return P;
    if (fzero(P.Z)) { ldpt R = {Q.x, Q.y, FONE}; return R; }
    fe Z2 = fsqr(P.Z), A = fadd(fmul(Q.y, Z2), P.Y), B = fadd(fmul(Q.x, P.Z), P.X);
    if (fzero(B)) {
        if (fzero(A)) { ldpt R = {Q.x, Q.y, FONE}; return lddbl(E, R); }
        ldpt R = {FONE, FZERO, FZERO}; return R;
    }
    fe C = fmul(P.Z, B), D = fmul(fsqr(B), fadd(C, fmul(E->a2, Z2)));
    ldpt R; R.Z = fsqr(C); fe Ee = fmul(A, C);
    R.X = fadd(fadd(fsqr(A), D), Ee);
    fe Fv = fadd(R.X, fmul(Q.x, R.Z)), Gv = fmul(fadd(Q.x, Q.y), fsqr(R.Z));
    R.Y = fadd(fmul(fadd(Ee, R.Z), Fv), Gv);
    return R;
}
static pt ldaffine(ldpt P) {
    if (fzero(P.Z)) return PINF;
    fe zi = finv(P.Z); pt R; R.inf = 0; R.x = fmul(P.X, zi); R.y = fmul(P.Y, fsqr(zi)); return R;
}
typedef struct { uint64_t w[4]; } bigu;   /* scalars up to 256 bits */
static bigu bu_from_u64(uint64_t v) { bigu r = {{v, 0, 0, 0}}; return r; }
static bigu bu_hex(const char *s) { fe t; bigu r = {{0, 0, 0, 0}}; t = fhex(s); r.w[0] = t.w[0]; r.w[1] = t.w[1]; r.w[2] = t.w[2]; return r; }
static pt pmul(const curve *E, bigu k, pt P) {
    ldpt R = {FONE, FZERO, FZERO};
    int top = 255; while (top >= 0 && !((k.w[top >> 6] >> (top & 63)) & 1)) top--;
    for (int i = top; i >= 0; i--) { R = lddbl(E, R); if ((k.w[i >> 6] >> (i & 63)) & 1) R = ldaddmixed(E, R, P); }
    return ldaffine(R);
}
static pt pmul_affine(const curve *E, bigu k, pt P) {   /* reference, for the self-test */
    pt R = PINF; int top = 255; while (top >= 0 && !((k.w[top >> 6] >> (top & 63)) & 1)) top--;
    for (int i = top; i >= 0; i--) { R = pdbl(E, R); if ((k.w[i >> 6] >> (i & 63)) & 1) R = padd(E, R, P); }
    return R;
}
static int pteq(pt P, pt Q) { if (P.inf || Q.inf) return P.inf == Q.inf; return feq(P.x, Q.x) && feq(P.y, Q.y); }

/* ---------------- rng ---------------- */
static uint64_t rng_s;
static inline uint64_t splitmix(uint64_t *s) { uint64_t z = (*s += 0x9E3779B97F4A7C15ULL); z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL; z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL; return z ^ (z >> 31); }
static uint64_t rnd(void) { return splitmix(&rng_s); }
static fe frand(void) { fe r = {{rnd(), rnd(), rnd() & M51}}; return r; }
static pt prandom(const curve *E) {   /* random affine point by decompression */
    for (;;) {
        fe x = frand(); if (fzero(x)) continue;
        fe xi = finv(x), c = fadd(fadd(x, E->a2), fmul(E->b, fsqr(xi)));
        if (ftrace(c)) continue;
        fe zz = fhalftrace(c); pt P; P.inf = 0; P.x = x; P.y = fmul(x, zz);
        if (rnd() & 1) P = pneg(P);
        return P;
    }
}

/* ---------------- arithmetic mod N ---------------- */
static uint64_t NMOD;
static inline uint64_t mmul(uint64_t a, uint64_t b) { return (uint64_t)(((u128)a * b) % NMOD); }
static inline uint64_t madd(uint64_t a, uint64_t b) { uint64_t c = a + b; return c >= NMOD ? c - NMOD : c; }
static inline uint64_t mneg(uint64_t a) { return a ? NMOD - a : 0; }
static uint64_t minv(uint64_t a) {
    __int128 t = 0, nt = 1, r = NMOD, nr = a % NMOD;
    while (nr) { __int128 qq = r / nr, tmp = t - qq * nt; t = nt; nt = tmp; tmp = r - qq * nr; r = nr; nr = tmp; }
    if (r != 1) return 0; if (t < 0) t += NMOD; return (uint64_t)t;
}

/* ---------------- rho ---------------- */
typedef struct {
    int mode; curve E; uint64_t N, s, spow[NB];
    pt G, H; pt R[32]; uint64_t rc[32], rd[32];
} rhoctx;
static inline uint64_t mix3(fe k) {
    uint64_t h = k.w[0] * 0x9E3779B97F4A7C15ULL ^ (k.w[1] + 0x632BE59BD9B4E019ULL) * 0xBF58476D1CE4E5B9ULL ^ (k.w[2] + 0x1D8E4E27C47D124FULL) * 0x94D049BB133111EBULL;
    h ^= h >> 31; h *= 0xD6E8FEB86659FD93ULL; h ^= h >> 32; return h;
}
/* canonicalize P (with multipliers a,b) in place; returns the class key */
static inline fe canon(const rhoctx *C, pt *P, uint64_t *a, uint64_t *b) {
    uint64_t m = 1; fe key;
    if (C->mode == 1) {
        fe cx = conv(P2N, P->x), cxr; int r = nbminrot(cx, &cxr);
        if (r) { P->x = conv(N2P, cxr); P->y = conv(N2P, nbrot(conv(P2N, P->y), r)); m = C->spow[r]; }
        key = cxr;
    } else key = P->x;
    fe y2 = fadd(P->y, P->x);
    if (fcmp(y2, P->y) < 0) { P->y = y2; m = mneg(m); }
    if (m != 1) { *a = mmul(*a, m); *b = mmul(*b, m); }
    return key;
}
/* one serial walk step (used for cycle traversal / escapes) */
static int stepidx(fe key) { return (int)(mix3(key) & 31); }
static int isdp(fe key, int dpbits) { return ((mix3(key) >> 16) & ((1ULL << dpbits) - 1)) == 0; }
static fe step1(const rhoctx *C, pt *W, uint64_t *a, uint64_t *b, fe key) {
    int j = stepidx(key);
    *W = padd(&C->E, *W, C->R[j]); *a = madd(*a, C->rc[j]); *b = madd(*b, C->rd[j]);
    if (W->inf) return FZERO;
    return canon(C, W, a, b);
}
typedef struct { fe key; uint64_t a, b; int used; } dpent;
typedef struct {
    uint64_t k; int found, verified; uint64_t iters, iters_escape, dps, escapes, abandoned, cyclesolved; double t_setup, t_walk, c_setup, c_walk;
} rhores;

static int verify_log(const rhoctx *C, uint64_t k) { return pteq(pmul(&C->E, bu_from_u64(k), C->G), C->H); }

static rhores rho(rhoctx *C, int M, int dpbits, uint64_t seed) {
    rhores res; memset(&res, 0, sizeof res);
    double t0 = now(), c0 = cpu();
    rng_s = seed; NMOD = C->N;
    C->spow[0] = 1; for (int i = 1; i < NB; i++) C->spow[i] = mmul(C->spow[i - 1], C->s);
    for (int j = 0; j < 32; j++) {
        C->rc[j] = rnd() % C->N; C->rd[j] = rnd() % C->N;
        pt A = pmul(&C->E, bu_from_u64(C->rc[j]), C->G), B = pmul(&C->E, bu_from_u64(C->rd[j]), C->H);
        C->R[j] = padd(&C->E, A, B);
    }
    pt *W = malloc(sizeof(pt) * M); uint64_t *A = malloc(8 * M), *B = malloc(8 * M), *steps = malloc(8 * M);
    fe *key = malloc(sizeof(fe) * M), *k1 = malloc(sizeof(fe) * M), *k2 = malloc(sizeof(fe) * M), *ck1 = malloc(sizeof(fe) * M), *ck2 = malloc(sizeof(fe) * M);
    fe *den = malloc(sizeof(fe) * M), *pre = malloc(sizeof(fe) * M); int *jj = malloc(sizeof(int) * M);
    /* starts: S0 + w*T */
    uint64_t sa = rnd() % C->N, sb = rnd() % C->N, ta = rnd() % C->N, tb = rnd() % C->N;
    pt S = padd(&C->E, pmul(&C->E, bu_from_u64(sa), C->G), pmul(&C->E, bu_from_u64(sb), C->H));
    pt T = padd(&C->E, pmul(&C->E, bu_from_u64(ta), C->G), pmul(&C->E, bu_from_u64(tb), C->H));
    for (int w = 0; w < M; w++) {
        W[w] = S; A[w] = sa; B[w] = sb; key[w] = canon(C, &W[w], &A[w], &B[w]);
        k1[w] = k2[w] = ck1[w] = ck2[w] = FZERO; steps[w] = 0;
        S = padd(&C->E, S, T); sa = madd(sa, ta); sb = madd(sb, tb);
    }
    size_t tsz = 1 << 17; dpent *tab = calloc(tsz, sizeof(dpent));
    uint64_t maxlen = (uint64_t)40 << dpbits;
    res.t_setup = now() - t0; res.c_setup = cpu() - c0; double t1 = now(), c1 = cpu();
    uint64_t guard = (uint64_t)1 << 40;
    while (!res.found && res.iters < guard) {
        /* batched addition W[w] + R[j] */
        fe acc = FONE;
        for (int w = 0; w < M; w++) {
            jj[w] = stepidx(key[w]); den[w] = fadd(W[w].x, C->R[jj[w]].x);
            if (fzero(den[w])) den[w] = FONE, jj[w] |= 64;       /* W = +-R_j : handled below */
            pre[w] = acc; acc = fmul(acc, den[w]);
        }
        fe inv = finv(acc);
        for (int w = M - 1; w >= 0; w--) {
            fe iw = fmul(inv, pre[w]); inv = fmul(inv, den[w]);
            int j = jj[w] & 31;
            if (jj[w] & 64) {   /* degenerate: restart this walk from a fresh random combination */
                uint64_t na = rnd() % C->N, nb = rnd() % C->N;
                W[w] = padd(&C->E, pmul(&C->E, bu_from_u64(na), C->G), pmul(&C->E, bu_from_u64(nb), C->H));
                A[w] = na; B[w] = nb; key[w] = canon(C, &W[w], &A[w], &B[w]); steps[w] = 0; res.abandoned++; continue;
            }
            pt P = W[w]; const pt *Rj = &C->R[j];
            fe l = fmul(fadd(P.y, Rj->y), iw);
            pt Q; Q.inf = 0;
            Q.x = fadd(fadd(fadd(fsqr(l), l), fadd(P.x, Rj->x)), C->E.a2);
            Q.y = fadd(fadd(fmul(l, fadd(P.x, Q.x)), Q.x), P.y);
            W[w] = Q; A[w] = madd(A[w], C->rc[j]); B[w] = madd(B[w], C->rd[j]);
            k2[w] = k1[w]; k1[w] = key[w];
            key[w] = canon(C, &W[w], &A[w], &B[w]);
        }
        res.iters += M;
        for (int w = 0; w < M && !res.found; w++) {
            steps[w]++;
            int cyc = feq(key[w], k2[w]);
            if ((steps[w] & 63) == 0) ck1[w] = key[w]; else if (feq(key[w], ck1[w])) cyc = 1;
            if ((steps[w] & 2047) == 0) ck2[w] = key[w]; else if (feq(key[w], ck2[w])) cyc = 1;
            if (cyc) {
                /* traverse the cycle from W[w]; find the minimal key; detect useful (non-fruitless) returns */
                pt P = W[w]; uint64_t a = A[w], b = B[w]; fe kk = key[w];
                pt Pm = P; uint64_t am = a, bm = b; fe km = kk; int len = 0;
                do {
                    kk = step1(C, &P, &a, &b, kk); len++; res.iters_escape++;
                    if (fcmp(kk, km) < 0) { km = kk; Pm = P; am = a; bm = b; }
                } while (!feq(kk, key[w]) && len < 100000);
                if (feq(kk, key[w]) && (a != A[w] || b != B[w]) && b != B[w]) {
                    uint64_t k = mmul(madd(a, mneg(A[w])), minv(madd(B[w], mneg(b))));
                    res.k = k; res.found = 1; res.cyclesolved = 1; break;
                }
                pt D = pdbl(&C->E, Pm); am = madd(am, am); bm = madd(bm, bm);
                W[w] = D; A[w] = am; B[w] = bm; key[w] = canon(C, &W[w], &A[w], &B[w]);
                k1[w] = k2[w] = FZERO; ck1[w] = ck2[w] = FZERO; steps[w] = 0; res.escapes++;
                continue;
            }
            if (isdp(key[w], dpbits)) {
                res.dps++; steps[w] = 0;
                size_t h = (mix3(key[w]) >> 24) & (tsz - 1);
                for (;;) {
                    if (!tab[h].used) { tab[h].used = 1; tab[h].key = key[w]; tab[h].a = A[w]; tab[h].b = B[w]; break; }
                    if (feq(tab[h].key, key[w])) {
                        if (tab[h].b != B[w]) {
                            uint64_t k = mmul(madd(A[w], mneg(tab[h].a)), minv(madd(tab[h].b, mneg(B[w]))));
                            res.k = k; res.found = 1;
                        } else {   /* same combination revisited: fruitless loop through a DP -> force a cycle escape next time */
                            ck1[w] = key[w];
                        }
                        break;
                    }
                    h = (h + 1) & (tsz - 1);
                }
            } else if (steps[w] > maxlen) {
                uint64_t na = rnd() % C->N, nb = rnd() % C->N;
                W[w] = padd(&C->E, pmul(&C->E, bu_from_u64(na), C->G), pmul(&C->E, bu_from_u64(nb), C->H));
                A[w] = na; B[w] = nb; key[w] = canon(C, &W[w], &A[w], &B[w]); steps[w] = 0; res.abandoned++;
            }
        }
    }
    res.t_walk = now() - t1; res.c_walk = cpu() - c1;
    if (res.found) res.verified = verify_log(C, res.k);
    free(W); free(A); free(B); free(steps); free(key); free(k1); free(k2); free(ck1); free(ck2); free(den); free(pre); free(jj); free(tab);
    return res;
}

/* ---------------- transport: floor [1,1,0,0,b] -> E0 [1,1,0,0,1] via the ascending L-isogeny ---------------- */
typedef struct { fe psi[400]; int deg; double t_kernel, c_kernel; int ok_codomain, ok_order; } kernelpoly;
static kernelpoly build_kernel(fe b, bigu cofTw, int L) {
    kernelpoly K; memset(&K, 0, sizeof K);
    double t0 = now(), c0 = cpu();
    curve Et = {FZERO, b};
    pt Kg = PINF;
    for (int att = 0; att < 50; att++) {
        pt R1 = pmul(&Et, cofTw, prandom(&Et));
        if (R1.inf) continue;
        pt RL = pmul(&Et, bu_from_u64(L), R1);
        if (!RL.inf) { Kg = RL; break; }
    }
    if (Kg.inf) { K.deg = -1; return K; }
    K.ok_order = pmul(&Et, bu_from_u64(L), Kg).inf;
    int h = (L - 1) / 2; fe xs[400]; pt Q = Kg;
    for (int i = 0; i < h; i++) { xs[i] = Q.x; Q = padd(&Et, Q, Kg); }
    /* psi = prod (X + x_i), coefficients low->high */
    fe *p = K.psi; p[0] = FONE; int d = 0;
    for (int i = 0; i < h; i++) {
        p[d + 1] = p[d];
        for (int k = d; k >= 1; k--) p[k] = fadd(p[k - 1], fmul(p[k], xs[i]));
        p[0] = fmul(p[0], xs[i]); d++;
    }
    K.deg = d;
    fe v = FZERO; for (int i = 0; i < h; i++) v = fadd(v, xs[i]);
    K.ok_codomain = feq(fadd(fadd(b, v), fsqr(v)), FONE);     /* codomain [1,1,0,0,b+v+v^2] == E0 */
    K.t_kernel = now() - t0; K.c_kernel = cpu() - c0;
    return K;
}
/* x-only image X = x + x u + (x u)^2, u = psi'(x)/psi(x); then Y from the curve equation of E0 (sign unknown) */
static pt transport_pt(const kernelpoly *K, pt P, int *ok) {
    fe ps = K->psi[K->deg], dps = FZERO;
    for (int i = K->deg - 1; i >= 0; i--) ps = fadd(fmul(ps, P.x), K->psi[i]);
    /* psi'(x) = sum_{i odd} c_i x^(i-1) */
    int top = (K->deg & 1) ? K->deg : K->deg - 1; fe x2 = fsqr(P.x);
    for (int i = top; i >= 1; i -= 2) dps = fadd(fmul(dps, x2), K->psi[i]);
    fe xu = fmul(P.x, fmul(dps, finv(ps)));
    pt R; R.inf = 0; R.x = fadd(fadd(P.x, xu), fsqr(xu));
    fe xi = finv(R.x), c = fadd(fadd(R.x, FONE), fsqr(xi));
    *ok = !ftrace(c);
    R.y = fmul(R.x, fhalftrace(c));
    return R;
}

/* ---------------- self test ---------------- */
static int selftest(void) {
    int bad = 0; rng_s = 12345;
    for (int i = 0; i < 20000; i++) {
        fe a = frand(), b = frand(), c = frand();
        if (!feq(fmul(a, b), fmul_soft(a, b))) bad++;
        if (!feq(fsqr(a), fmul(a, a))) bad++;
        if (!feq(fmul(fadd(a, b), c), fadd(fmul(a, c), fmul(b, c)))) bad++;
        if (!fzero(a) && !feq(fmul(a, finv(a)), FONE)) bad++;
        fe na = conv(P2N, a);
        if (!feq(conv(N2P, na), a)) bad++;
        if (!feq(conv(P2N, fsqr(a)), nbrot(na, 1))) bad++;
        int r = (int)(rnd() % NB); if (!feq(conv(P2N, fsqrn(a, r)), nbrot(na, r))) bad++;
        fe m1, m2; int r1 = nbminrot(na, &m1), r2 = nbminrot(nbrot(na, r), &m2);
        if (!feq(m1, m2) || !feq(nbrot(na, r1), m1)) bad++; (void)r2;
        if (!ftrace(a)) { fe h = fhalftrace(a); if (!feq(fadd(fsqr(h), h), a)) bad++; }
    }
    /* z^179 = z^4+z^2+z+1 */
    fe zz = FZERO; zz.w[0] = 2; fe p = FONE; for (int i = 0; i < 179; i++) p = fmul(p, zz);
    fe expect = {{0x17, 0, 0}}; if (!feq(p, expect)) bad += 1000;
    curve E = {FONE, FONE};
    for (int i = 0; i < 50; i++) {
        pt P = prandom(&E); if (!oncurve(&E, P)) bad++;
        bigu k = {{rnd(), rnd(), rnd() >> 20, 0}};
        pt A = pmul(&E, k, P), B = pmul_affine(&E, k, P);
        if (!pteq(A, B) || !oncurve(&E, A)) bad++;
    }
    printf("{\"selftest_failures\": %d}\n", bad); return bad;
}

int main(int argc, char **argv) {
    const char *nbpath = argc > 1 ? argv[1] : "nb_tables.txt";
    load_nb(nbpath); init_trace();
    if (argc > 2 && !strcmp(argv[2], "selftest")) return selftest();
    char line[8192];
    while (fgets(line, sizeof line, stdin)) {
        char cmd[8], id[64], sa2[80], sb[80], sN[40], ss[40], gx[80], gy[80], hx[80], hy[80], cof[80]; int mode, M, dpb, L; unsigned long long seed;
        if (line[0] == 'R') {
            if (sscanf(line, "%7s %63s %d %79s %79s %39s %39s %79s %79s %79s %79s %d %d %llu", cmd, id, &mode, sa2, sb, sN, ss, gx, gy, hx, hy, &M, &dpb, &seed) != 14) { fprintf(stderr, "bad R line\n"); continue; }
            rhoctx *C = calloc(1, sizeof(rhoctx));
            C->mode = mode; C->E.a2 = fhex(sa2); C->E.b = fhex(sb); C->N = strtoull(sN, 0, 10); C->s = strtoull(ss, 0, 10);
            C->G.inf = C->H.inf = 0; C->G.x = fhex(gx); C->G.y = fhex(gy); C->H.x = fhex(hx); C->H.y = fhex(hy);
            int okc = oncurve(&C->E, C->G) && oncurve(&C->E, C->H);
            rhores r = rho(C, M, dpb, seed);
            printf("{\"cmd\":\"R\",\"id\":\"%s\",\"mode\":%d,\"on_curve\":%d,\"found\":%d,\"k\":%llu,\"verified\":%d,\"iters\":%llu,\"iters_escape\":%llu,\"dps\":%llu,\"escapes\":%llu,\"abandoned\":%llu,\"cyclesolved\":%llu,\"M\":%d,\"dpbits\":%d,\"t_setup\":%.6f,\"t_walk\":%.6f,\"c_setup\":%.6f,\"c_walk\":%.6f}\n",
                   id, mode, okc, r.found, (unsigned long long)r.k, r.verified, (unsigned long long)r.iters, (unsigned long long)r.iters_escape, (unsigned long long)r.dps,
                   (unsigned long long)r.escapes, (unsigned long long)r.abandoned, (unsigned long long)r.cyclesolved, M, dpb, r.t_setup, r.t_walk, r.c_setup, r.c_walk);
            fflush(stdout); free(C);
        } else if (line[0] == 'T') {
            if (sscanf(line, "%7s %63s %79s %79s %d %39s %39s %79s %79s %79s %79s %d %d %llu", cmd, id, sb, cof, &L, sN, ss, gx, gy, hx, hy, &M, &dpb, &seed) != 14) { fprintf(stderr, "bad T line\n"); continue; }
            double t0 = now();
            rng_s = seed ^ 0xA5A5A5A5ULL; NMOD = strtoull(sN, 0, 10);
            fe b = fhex(sb); curve Ef = {FONE, b};
            pt G = {fhex(gx), fhex(gy), 0}, H = {fhex(hx), fhex(hy), 0};
            int okc = oncurve(&Ef, G) && oncurve(&Ef, H);
            kernelpoly K = build_kernel(b, bu_hex(cof), L);
            double t1 = now(), c1 = cpu();
            int ok1, ok2; pt G2 = transport_pt(&K, G, &ok1), H2 = transport_pt(&K, H, &ok2);
            double t2 = now(), c2 = cpu();
            rhoctx *C = calloc(1, sizeof(rhoctx));
            C->mode = 1; C->E.a2 = FONE; C->E.b = FONE; C->N = NMOD; C->s = strtoull(ss, 0, 10); C->G = G2; C->H = H2;
            int onE0 = oncurve(&C->E, G2) && oncurve(&C->E, H2);
            int ordN = pmul(&C->E, bu_from_u64(C->N), G2).inf && !G2.inf;
            rhores r = rho(C, M, dpb, seed);
            double t3 = now(), c3 = cpu();
            uint64_t k = r.k; int sign = 0, ver = 0;
            NMOD = C->N;
            if (r.found) {
                if (pteq(pmul(&Ef, bu_from_u64(k), G), H)) { ver = 1; sign = 1; }
                else { k = mneg(k); if (pteq(pmul(&Ef, bu_from_u64(k), G), H)) { ver = 1; sign = -1; } }
            }
            double t4 = now(), c4 = cpu();
            printf("{\"cmd\":\"T\",\"id\":\"%s\",\"on_curve\":%d,\"kernel_deg\":%d,\"kernel_order_ok\":%d,\"codomain_is_E0\":%d,\"images_on_E0\":%d,\"image_order_N\":%d,\"ytrace_ok\":%d,"
                   "\"found\":%d,\"k\":%llu,\"verified_on_floor\":%d,\"sign\":%d,\"rho_verified_on_E0\":%d,\"iters\":%llu,\"iters_escape\":%llu,\"escapes\":%llu,\"abandoned\":%llu,"
                   "\"t_kernel\":%.6f,\"t_eval\":%.6f,\"t_signfix\":%.6f,\"t_rho_setup\":%.6f,\"t_rho_walk\":%.6f,\"t_total\":%.6f,\"c_kernel\":%.6f,\"c_eval\":%.6f,\"c_signfix\":%.6f,\"c_rho_setup\":%.6f,\"c_rho_walk\":%.6f,\"M\":%d,\"dpbits\":%d}\n",
                   id, okc, K.deg, K.ok_order, K.ok_codomain, onE0, ordN, ok1 && ok2, r.found, (unsigned long long)k, ver, sign, r.verified,
                   (unsigned long long)r.iters, (unsigned long long)r.iters_escape, (unsigned long long)r.escapes, (unsigned long long)r.abandoned,
                   t1 - t0, t2 - t1, t4 - t3, r.t_setup, r.t_walk, t4 - t0, K.c_kernel, c2 - c1, c4 - c3, r.c_setup, r.c_walk, M, dpb);
            fflush(stdout); free(C);
        }
    }
    return 0;
}
