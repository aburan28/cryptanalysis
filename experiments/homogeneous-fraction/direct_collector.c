/* Compiled, exact direct collector for n=13 fraction-base screening.
 * Build: cc -O3 -std=c11 -Wall -Wextra -o direct_collector direct_collector.c
 *        add -DK=3 for the k=3 base.
 * Input: count, target rank, then count scalar targets on stdin.
 * Output: a base certificate and one complete charged attempt per target.
 */
#define _POSIX_C_SOURCE 200809L
#include "../pdp-degree-heuristics/pdpkernel.c"
#include <stdio.h>
#include <time.h>

#ifndef K
#define K 2
#endif
#if K == 2
#define R  2003
#define B  35
#define NC 8
#define NSUB 16
#elif K == 3
#define R  2003
#define B  115
#define NC 28
#define NSUB 56
#else
#error "the n=13 screening collector supports K=2 or K=3"
#endif
typedef struct {
    u64 x, y;
} point;
typedef struct {
    point sum;
    int i, j;
} pair;
static ctx_t ctx;
static point orig[B], image[B], subgroup[NSUB], reps[NC], generator;
static pair pairs[B * (B + 1) / 2];
static int pivot[NC][NC], has_pivot[NC], seen[10000][NC], nseen, rank_now;

static u64 ns(void)
{
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return (u64)t.tv_sec * 1000000000ULL + t.tv_nsec;
}
static point add(point a, point b)
{
    point o;
    ec_add(&ctx, a.x, a.y, b.x, b.y, &o.x, &o.y);
    return o;
}
static point neg(point a)
{
    if (a.x != INF_X) a.y ^= a.x;
    return a;
}
static point mul(point a, u64 n)
{
    point o;
    ec_mul(&ctx, a.x, a.y, n, &o.x, &o.y);
    return o;
}
static int cmppt(point a, point b)
{
    if (a.x != b.x) return a.x < b.x ? -1 : 1;
    if (a.y != b.y) return a.y < b.y ? -1 : 1;
    return 0;
}
static int cmppoint(const void *a, const void *b)
{
    return cmppt(*(const point *)a, *(const point *)b);
}
static int cmppair(const void *a, const void *b)
{
    const pair *p = a, *q = b;
    int c = cmppt(p->sum, q->sum);
    if (c) return c;
    if (p->i != q->i) return p->i - q->i;
    return p->j - q->j;
}
static u64 s4(u64 x, u64 y, u64 z, u64 target)
{
    u64 a = gf_sqr(&ctx, x ^ y), b = gf_mul(&ctx, x, y);
    u64 c = gf_sqr(&ctx, b) ^ 1, d = gf_sqr(&ctx, z ^ target);
    u64 e = gf_mul(&ctx, z, target), f = gf_sqr(&ctx, e) ^ 1;
    return gf_sqr(&ctx, gf_mul(&ctx, a, f) ^ gf_mul(&ctx, c, d)) ^
           gf_mul(&ctx, gf_mul(&ctx, a, e) ^ gf_mul(&ctx, b, d),
                  gf_mul(&ctx, b, f) ^ gf_mul(&ctx, c, e));
}
static int invr(int x)
{
    int y = 1;
    for (int n = R - 2; n; n >>= 1, x = (x * x) % R)
        if (n & 1) y = y * x % R;
    return y;
}
static int column(point p, int *sign)
{
    for (int j = 0; j < NC; j++) {
        if (!cmppt(p, reps[j])) {
            *sign = 1;
            return j;
        }
        if (!cmppt(p, neg(reps[j]))) {
            *sign = -1;
            return j;
        }
    }
    return -1;
}
static void row_of(int i, int j, int k, int row[NC])
{
    int ids[3] = {i, j, k};
    memset(row, 0, NC * sizeof(int));
    for (int t = 0; t < 3; t++) {
        point p = image[ids[t]];
        if (p.x == INF_X) continue;
        int s, c = column(p, &s);
        if (c < 0) {
            fprintf(stderr, "column missing\n");
            exit(3);
        }
        row[c] += s;
    }
}
static int insert(const int row[NC], int *repeat)
{
    *repeat = 0;
    for (int i = 0; i < nseen; i++)
        if (!memcmp(seen[i], row, NC * sizeof(int))) {
            *repeat = 1;
            break;
        }
    if (nseen == 10000) exit(4);
    memcpy(seen[nseen++], row, NC * sizeof(int));
    int v[NC];
    for (int j = 0; j < NC; j++) v[j] = (row[j] % R + R) % R;
    for (int j = 0; j < NC; j++)
        if (has_pivot[j] && v[j]) {
            int f = v[j];
            for (int k = 0; k < NC; k++) v[k] = (v[k] - f * pivot[j][k] % R + R) % R;
        }
    for (int j = 0; j < NC; j++)
        if (v[j]) {
            int f = invr(v[j]);
            for (int k = 0; k < NC; k++) pivot[j][k] = v[k] * f % R;
            has_pivot[j] = 1;
            rank_now++;
            return 1;
        }
    return 0;
}
static void build(void)
{
    if (ctx_init(&ctx, 13, 0x2027, 0, 1)) exit(2);
    int nb = 0, nx = 0;
    unsigned char xs[8192] = {0};
    const int width = K + 1;
    const int block_mask = (1 << width) - 1;
    for (int word = 0; word < (1 << (2 * width)); word++) {
        u64 a = word & block_mask, b = word >> width;
        if (!b) continue;
        /* Each block encodes coefficients in the basis 1,z,...,z^K. */
        xs[gf_mul(&ctx, a, gf_inv(&ctx, b))] = 1;
    }
    for (int x = 0; x < 8192; x++)
        if (xs[x]) {
            nx++;
            u64 xx = (u64)x, y;
            uint8_t ok;
            ec_lift_batch(&ctx, &xx, 1, &y, &ok);
            if (!ok) continue;
            if (nb >= B) exit(2);
            orig[nb++] = (point){xx, y};
            if (x) {
                if (nb >= B) exit(2);
                orig[nb++] = (point){xx, xx ^ y};
            }
        }
    if (nb != B) {
        fprintf(stderr, "base count %d x=%d\n", nb, nx);
        exit(2);
    }
    qsort(orig, B, sizeof(point), cmppoint);
    int ni = 0;
    for (int i = 0; i < B; i++) {
        image[i] = mul(orig[i], 4);
        if (image[i].x == INF_X) continue;
        if (mul(image[i], R).x != INF_X) exit(2);
        int found = 0;
        for (int j = 0; j < ni; j++)
            if (!cmppt(subgroup[j], image[i])) {
                found = 1;
                break;
            }
        if (!found) {
            if (ni == NSUB) exit(2);
            subgroup[ni++] = image[i];
        }
    }
    if (ni != NSUB) exit(2);
    qsort(subgroup, ni, sizeof(point), cmppoint);
    if (K == 2) {
        generator = subgroup[0];
    } else {
        /* Keep ordinary target points identical to the frozen k=2 streams.
         * Derive their canonical generator from the embedded k=2 fraction base. */
        unsigned char small_xs[8192] = {0};
        point small_subgroup[16];
        int small_nx = 0, small_ni = 0;
        for (int word = 0; word < 64; word++) {
            u64 a = word & 7, b = word >> 3;
            if (b) small_xs[gf_mul(&ctx, a, gf_inv(&ctx, b))] = 1;
        }
        for (int x = 0; x < 8192; x++) if (small_xs[x]) {
            small_nx++;
            u64 xx = (u64)x, y;
            uint8_t ok;
            ec_lift_batch(&ctx, &xx, 1, &y, &ok);
            if (!ok) continue;
            point p = mul((point){xx, y}, 4);
            if (p.x != INF_X) {
                int found = 0;
                for (int j = 0; j < small_ni; j++)
                    found |= !cmppt(small_subgroup[j], p);
                if (!found) small_subgroup[small_ni++] = p;
            }
            if (x) {
                p = mul((point){xx, xx ^ y}, 4);
                if (p.x != INF_X) {
                    int found = 0;
                    for (int j = 0; j < small_ni; j++)
                        found |= !cmppt(small_subgroup[j], p);
                    if (!found) small_subgroup[small_ni++] = p;
                }
            }
        }
        if (small_nx != 32 || small_ni != 16) exit(2);
        qsort(small_subgroup, small_ni, sizeof(point), cmppoint);
        generator = small_subgroup[0];
        int found = 0;
        for (int i = 0; i < ni; i++) found |= !cmppt(subgroup[i], generator);
        if (!found) exit(2);
    }
    int nr = 0;
    for (int i = 0; i < ni; i++) {
        point rep = cmppt(subgroup[i], neg(subgroup[i])) < 0 ? subgroup[i] : neg(subgroup[i]);
        int found = 0;
        for (int j = 0; j < nr; j++)
            if (!cmppt(reps[j], rep)) {
                found = 1;
                break;
            }
        if (!found) reps[nr++] = rep;
    }
    if (nr != NC) exit(2);
    qsort(reps, NC, sizeof(point), cmppoint);
    int p = 0;
    for (int i = 0; i < B; i++)
        for (int j = i; j < B; j++) pairs[p++] = (pair){add(orig[i], orig[j]), i, j};
    qsort(pairs, p, sizeof(pair), cmppair);
    printf("B %d %llu %llu", B, (unsigned long long)generator.x, (unsigned long long)generator.y);
    for (int i = 0; i < B; i++)
        printf(" %llu %llu", (unsigned long long)orig[i].x, (unsigned long long)orig[i].y);
    putchar('\n');
}
int main(void)
{
    int count, target_rank;
    if (scanf("%d %d", &count, &target_rank) != 2 || count < 1 || count > 10000 || target_rank != 8)
        return 2;
    int scalars[10000];
    for (int i = 0; i < count; i++)
        if (scanf("%d", &scalars[i]) != 1 || scalars[i] < 1 || scalars[i] >= R) return 2;
    u64 start = ns();
    build();
    u64 built = ns();
    for (int t = 0; t < count; t++) {
        u64 begin = ns();
        point target = mul(generator, (u64)scalars[t]);
        int witness[3] = {-1, -1, -1};
        int row[NC] = {0}, candidates = 0, repeated = 0, dependent = 0, pre = rank_now, novel = 0;
        for (int k = 0; k < B && !novel; k++) {
            point want = add(target, neg(orig[k]));
            int lo = 0, hi = B * (B + 1) / 2;
            while (lo < hi) {
                int m = (lo + hi) / 2;
                if (cmppt(pairs[m].sum, want) < 0)
                    lo = m + 1;
                else
                    hi = m;
            }
            for (int a = lo; a < B * (B + 1) / 2 && !cmppt(pairs[a].sum, want) && !novel; a++) {
                int i = pairs[a].i, j = pairs[a].j;
                candidates++;
                if (cmppt(add(pairs[a].sum, orig[k]), target) ||
                    cmppt(add(add(image[i], image[j]), image[k]), mul(target, 4)) ||
                    s4(orig[i].x, orig[j].x, orig[k].x, target.x))
                    exit(5);
                row_of(i, j, k, row);
                int nonzero = 0;
                for (int z = 0; z < NC; z++) nonzero |= row[z] != 0;
                if (!nonzero) exit(5);
                int rep = 0;
                novel = insert(row, &rep);
                repeated += rep;
                dependent += !novel && !rep;
                if (novel) {
                    witness[0] = i;
                    witness[1] = j;
                    witness[2] = k;
                }
            }
        }
        u64 done = ns();
        printf("A %d %d %llu %llu %d %d %d %d %d %d %d %d %d %llu", t, scalars[t],
               (unsigned long long)target.x, (unsigned long long)target.y,
               novel        ? 1
               : candidates ? 2
                            : 0,
               candidates, repeated, dependent, pre, rank_now, witness[0], witness[1], witness[2],
               (unsigned long long)(done - begin));
        for (int z = 0; z < NC; z++) printf(" %d", row[z]);
        putchar('\n');
        if (rank_now >= target_rank) break;
    }
    printf("T %llu %llu\n", (unsigned long long)(built - start),
           (unsigned long long)(ns() - start));
    return 0;
}
