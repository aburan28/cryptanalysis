/* G1 (e) weight enumeration, rotation-canonical variant (weightenum2): only strings whose cyclic gap
 * from the last nonzero back to position 0 is >= every other gap are visited (every rotation class has such a
 * representative), which cuts the work by about a factor w.
 * Original header: every tau-adic string sum_{i in S} d_i tau^i (length 131, digits +-1, weight w,
 * normalised so that d_0 = +1) acts on the N-subgroup as e = sum d_i s^i mod N. We test e^L == 1 with
 * L = lcm of all divisors of N-1 below 2^32 (= 2^3*3*11*109*131*263*32326729), i.e. whether e (equivalently any
 * element of e*<-1,s>) has multiplicative order dividing L. Survivors are printed as position/sign lists.
 * stdin: N_hex L_decimal wmax nthreads, then 131 lines s^i mod N (hex). */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <pthread.h>
typedef unsigned __int128 u128;
typedef struct { uint64_t w[3]; } u192;
static u192 NN, R2M, ONEM; static uint64_t NINV; static uint64_t LEXP; static int WMAX;
static u192 SP[131], SN[131];
static void parse_hex(const char *s, u192 *r) {
    memset(r, 0, sizeof *r); size_t L = strlen(s);
    for (size_t i = 0; i < L; i++) { char c = s[L-1-i]; int v = (c <= '9') ? c - '0' : (c | 32) - 'a' + 10; r->w[i/16] |= (uint64_t)v << (4*(i%16)); }
}
static inline int geq(const uint64_t *a, const u192 *n) { for (int i = 2; i >= 0; i--) if (a[i] != n->w[i]) return a[i] > n->w[i]; return 1; }
static inline u192 mont(const u192 a, const u192 b) {
    uint64_t t[5] = {0,0,0,0,0};
    for (int i = 0; i < 3; i++) {
        u128 C = 0;
        for (int j = 0; j < 3; j++) { C = (u128)t[j] + (u128)a.w[j]*b.w[i] + (C >> 64); t[j] = (uint64_t)C; }
        C = (u128)t[3] + (C >> 64); t[3] = (uint64_t)C; t[4] = (uint64_t)(C >> 64);
        uint64_t m = t[0] * NINV;
        C = (u128)t[0] + (u128)m * NN.w[0];
        for (int j = 1; j < 3; j++) { C = (u128)t[j] + (u128)m*NN.w[j] + (C >> 64); t[j-1] = (uint64_t)C; }
        C = (u128)t[3] + (C >> 64); t[2] = (uint64_t)C; t[3] = t[4] + (uint64_t)(C >> 64);
    }
    u192 r;
    if (t[3] || geq(t, &NN)) { u128 B = 0; for (int j = 0; j < 3; j++) { u128 x = (u128)t[j] - NN.w[j] - B; r.w[j] = (uint64_t)x; B = (x >> 64) & 1; } }
    else { r.w[0] = t[0]; r.w[1] = t[1]; r.w[2] = t[2]; }
    return r;
}
static inline u192 addm(const u192 a, const u192 b) { /* a,b < N < 2^130 */
    u192 r; u128 C = 0;
    for (int j = 0; j < 3; j++) { C = (u128)a.w[j] + b.w[j] + (C >> 64); r.w[j] = (uint64_t)C; }
    if (geq(r.w, &NN)) { u128 B = 0; for (int j = 0; j < 3; j++) { u128 x = (u128)r.w[j] - NN.w[j] - B; r.w[j] = (uint64_t)x; B = (x >> 64) & 1; } }
    return r;
}
static inline int eq(const u192 a, const u192 b) { return a.w[0]==b.w[0] && a.w[1]==b.w[1] && a.w[2]==b.w[2]; }
static inline int test(const u192 e) { /* e^LEXP == 1 ? */
    u192 x = mont(e, R2M); /* Montgomery form */
    u192 acc = x;
    int top = 63 - __builtin_clzll(LEXP);
    for (int b = top - 1; b >= 0; b--) { acc = mont(acc, acc); if ((LEXP >> b) & 1) acc = mont(acc, x); }
    return eq(acc, ONEM);
}
static long long CNT[8]; static pthread_mutex_t LK = PTHREAD_MUTEX_INITIALIZER;
static int NJOB, NEXT; static int JP1[20000], JP2[20000];
static long long SKIP[8];
static void rec(int depth, int w, int last, int maxgap, u192 acc, int *pos, int *sg, long long *cnt, long long *skip) {
    if (depth == w) {
        if (maxgap > 131 - last) { skip[w]++; return; }
        cnt[w]++;
        if (test(acc)) {
            pthread_mutex_lock(&LK);
            printf("S w=%d", w); for (int i = 0; i < w; i++) printf(" %c%d", sg[i] > 0 ? '+' : '-', pos[i]); printf("\n"); fflush(stdout);
            pthread_mutex_unlock(&LK);
        }
        return;
    }
    for (int p = last + 1; 2 * p <= 131 + last && p < 131; p++) {
        int g = p - last; int mg = g > maxgap ? g : maxgap;
        pos[depth] = p;
        sg[depth] = 1; rec(depth + 1, w, p, mg, addm(acc, SP[p]), pos, sg, cnt, skip);
        sg[depth] = -1; rec(depth + 1, w, p, mg, addm(acc, SN[p]), pos, sg, cnt, skip);
    }
}
static void *worker(void *arg) {
    (void)arg; long long cnt[8] = {0}, skip[8] = {0};
    int pos[8], sg[8];
    for (;;) {
        pthread_mutex_lock(&LK); int j = NEXT++; pthread_mutex_unlock(&LK);
        if (j >= NJOB) break;
        /* job: second position p1 = JP1[j], its sign index JP2[j] (0:+,1:-); enumerate all weights 2..WMAX with that prefix */
        int p1 = JP1[j], sgn = JP2[j] ? -1 : 1;
        pos[0] = 0; sg[0] = 1; pos[1] = p1; sg[1] = sgn;
        u192 acc = addm(SP[0], sgn > 0 ? SP[p1] : SN[p1]);
        for (int w = 2; w <= WMAX; w++) rec(2, w, p1, p1, acc, pos, sg, cnt, skip);
    }
    pthread_mutex_lock(&LK); for (int i = 0; i < 8; i++) { CNT[i] += cnt[i]; SKIP[i] += skip[i]; } pthread_mutex_unlock(&LK);
    return NULL;
}
int main(void) {
    char nh[128]; unsigned long long L; int nth;
    if (scanf("%127s %llu %d %d", nh, &L, &WMAX, &nth) != 4) return 1;
    parse_hex(nh, &NN); LEXP = L;
    uint64_t inv = 1; for (int i = 0; i < 7; i++) inv *= 2 - NN.w[0]*inv; NINV = -inv;
    for (int i = 0; i < 131; i++) { char h[128]; if (scanf("%127s", h) != 1) return 2; parse_hex(h, &SP[i]);
        /* SN = N - SP */ u128 B = 0; for (int j = 0; j < 3; j++) { u128 x = (u128)NN.w[j] - SP[i].w[j] - B; SN[i].w[j] = (uint64_t)x; B = (x >> 64) & 1; } }
    char r2h[128], oneh[128]; if (scanf("%127s %127s", r2h, oneh) != 2) return 3;
    parse_hex(r2h, &R2M); parse_hex(oneh, &ONEM);
    /* self-test: 1 must pass; weight-1 check */
    u192 one = {{1,0,0}};
    fprintf(stderr, "selftest one passes: %d, s passes: %d\n", test(one), test(SP[1]));
    /* extra planted values after the header */
    char ph[128];
    while (scanf("%127s", ph) == 1 && strcmp(ph, "END")) { u192 v; parse_hex(ph, &v); printf("T %s %d\n", ph, test(v)); }
    NJOB = 0; for (int p1 = 1; 2 * p1 <= 131; p1++) for (int s = 0; s < 2; s++) { JP1[NJOB] = p1; JP2[NJOB] = s; NJOB++; }
    pthread_t th[64]; if (nth > 64) nth = 64;
    for (int i = 0; i < nth; i++) pthread_create(&th[i], NULL, worker, NULL);
    for (int i = 0; i < nth; i++) pthread_join(th[i], NULL);
    for (int w = 2; w <= WMAX; w++) printf("C w=%d count=%lld skipped_at_leaf=%lld\n", w, CNT[w], SKIP[w]);
    return 0;
}
