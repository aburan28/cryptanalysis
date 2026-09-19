/*
 * ec2k_tool.c - the host side of an ECC2K-130 campaign.
 *
 *   ec2k walk   --seed S --steps N [--dp-weight W] [--out FILE]
 *   ec2k verify --seed S --steps N [--dp-weight W] FILE...
 *   ec2k merge  FILE...
 *   ec2k start  --seed S            (a start point for a core's load window)
 *
 * Three jobs, and the split between them is the design:
 *
 *   * `walk` is the software twin of a core.  It is not how a campaign gets
 *     its work done -- that is what the FPGA is for -- it is how the
 *     protocol, the record format and the host tooling are exercised without
 *     hardware, and it is the reference the RTL is compared against.
 *   * `verify` is what makes an untrusted accelerator usable.  A board
 *     reports a point; the host replays that walk in software and requires
 *     the point to appear.  A board that is broken, overheating, or
 *     returning fabricated records is caught here rather than by a campaign
 *     that quietly never finds a collision.  It costs one replay per point
 *     against the 2^25 steps that produced it.
 *   * `merge` is the campaign's terminal event: two records with the same x
 *     from different seeds are two walks that met, which is the collision the
 *     whole exercise is for.  Resolving it into a discrete logarithm means
 *     replaying both walks with coefficients, which is deliberately not
 *     automated here -- it happens once, and it is worth a person watching.
 *
 * Output is one JSON object per invocation, like the library's `ca`, so the
 * orchestration layer can drive this the same way it drives everything else.
 */
#include "../model/ecc2k130.h"

#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static const char *opt(int argc, char **argv, const char *name)
{
    for (int i = 2; i + 1 < argc; i++)
        if (!strcmp(argv[i], name)) return argv[i + 1];
    return NULL;
}

static uint64_t opt_u64(int argc, char **argv, const char *name, uint64_t def)
{
    const char *v = opt(argc, argv, name);
    if (!v) return def;
    return strtoull(v, NULL, 0);
}

static int usage(void)
{
    fprintf(stderr,
            "usage: ec2k <command> [options]\n"
            "  walk   --seed S --steps N [--dp-weight W] [--out FILE]\n"
            "  verify --seed S --steps N [--dp-weight W] FILE...\n"
            "  merge  FILE...\n"
            "  start  --seed S\n");
    return 2;
}

/* ---- walk ---------------------------------------------------------------- */

typedef struct walk_ctx {
    FILE *out;
    uint64_t written;
    unsigned weight;
    int failed;
} walk_ctx;

static void write_record(void *ctx, const ec2k_record *rec)
{
    walk_ctx *w = ctx;
    uint8_t buf[EC2K_RECORD_BYTES];
    ec2k_record_encode(buf, rec);
    if (w->out && fwrite(buf, 1, sizeof(buf), w->out) != sizeof(buf)) {
        w->failed = 1;
        return;
    }
    w->written++;
}

/* The walk with a configurable cutoff: at the campaign's weight 34 a point
 * appears about once in 2^25 steps, so anything interactive wants a looser
 * one.  The cutoff is part of the campaign, not of the tool: two machines
 * walking at different weights produce corpora that cannot be compared. */
static uint64_t walk_weight(uint64_t seed, uint64_t steps, unsigned weight,
                            ec2k_sink sink, void *ctx, uint64_t *dps, uint64_t *restarts)
{
    ec2k_pt r;
    ec2k_point_from_seed(&r, seed);
    uint64_t taken = 0, points = 0, restarted = 0, salt = seed;
    for (uint64_t i = 0; i < steps; i++) {
        ec2k_pt next;
        if (!ec2k_step(&next, &r)) {
            salt = salt * 6364136223846793005ULL + 1442695040888963407ULL;
            ec2k_point_from_seed(&r, salt);
            restarted++;
            taken++;
            continue;
        }
        r = next;
        taken++;
        if (ec2k_is_distinguished_w(&r.x, weight)) {
            ec2k_record rec;
            rec.seed = seed;
            ec2k_orbit_min(&rec.x, &r.x);
            points++;
            if (sink) sink(ctx, &rec);
        }
    }
    if (dps) *dps = points;
    if (restarts) *restarts = restarted;
    return taken;
}

static int cmd_walk(int argc, char **argv)
{
    uint64_t seed = opt_u64(argc, argv, "--seed", 1);
    uint64_t steps = opt_u64(argc, argv, "--steps", 1 << 16);
    unsigned weight = (unsigned)opt_u64(argc, argv, "--dp-weight", EC2K_DP_WEIGHT);
    const char *path = opt(argc, argv, "--out");

    walk_ctx ctx = {path ? fopen(path, "wb") : NULL, 0, weight, 0};
    if (path && !ctx.out) {
        fprintf(stderr, "cannot write %s\n", path);
        return 1;
    }
    uint64_t dps = 0, restarts = 0;
    double t0 = (double)clock() / CLOCKS_PER_SEC;
    uint64_t taken = walk_weight(seed, steps, weight, write_record, &ctx, &dps, &restarts);
    double secs = (double)clock() / CLOCKS_PER_SEC - t0;
    if (ctx.out) fclose(ctx.out);
    if (ctx.failed) {
        fprintf(stderr, "writing records failed\n");
        return 1;
    }
    printf("{\"status\":\"ok\",\"seed\":%" PRIu64 ",\"steps\":%" PRIu64 ",\"points\":%" PRIu64
           ",\"restarts\":%" PRIu64 ",\"dpWeight\":%u,\"seconds\":%.3f,\"stepsPerSecond\":%.0f}\n",
           seed, taken, dps, restarts, weight, secs, secs > 0 ? (double)taken / secs : 0.0);
    return 0;
}

/* ---- verify -------------------------------------------------------------- */

typedef struct expected {
    ec2k_fe *xs;
    size_t n, cap;
} expected;

static void expect_sink(void *ctx, const ec2k_record *rec)
{
    expected *e = ctx;
    if (e->n == e->cap) {
        e->cap = e->cap ? e->cap * 2 : 256;
        e->xs = realloc(e->xs, e->cap * sizeof(*e->xs));
    }
    e->xs[e->n++] = rec->x;
}

static int cmd_verify(int argc, char **argv)
{
    uint64_t seed = opt_u64(argc, argv, "--seed", 1);
    uint64_t steps = opt_u64(argc, argv, "--steps", 1 << 16);
    unsigned weight = (unsigned)opt_u64(argc, argv, "--dp-weight", EC2K_DP_WEIGHT);

    expected exp = {0};
    uint64_t dps = 0, restarts = 0;
    walk_weight(seed, steps, weight, expect_sink, &exp, &dps, &restarts);

    uint64_t checked = 0, matched = 0, wrong_seed = 0, unknown = 0, malformed = 0;
    for (int i = 2; i < argc; i++) {
        if (argv[i][0] == '-' && argv[i][1] == '-') { i++; continue; }
        FILE *f = fopen(argv[i], "rb");
        if (!f) {
            fprintf(stderr, "cannot read %s\n", argv[i]);
            free(exp.xs);
            return 1;
        }
        uint8_t buf[EC2K_RECORD_BYTES];
        size_t got;
        while ((got = fread(buf, 1, sizeof(buf), f)) == sizeof(buf)) {
            ec2k_record rec;
            checked++;
            if (!ec2k_record_decode(&rec, buf)) {
                malformed++;
                continue;
            }
            if (rec.seed != seed) {
                wrong_seed++;
                continue;
            }
            int found = 0;
            for (size_t k = 0; k < exp.n && !found; k++)
                found = ec2k_fe_equal(&exp.xs[k], &rec.x);
            if (found) matched++;
            else unknown++;
        }
        if (got != 0) malformed++;   /* a partial trailing record */
        fclose(f);
    }
    free(exp.xs);

    /* `unknown` is the number that matters: a point the replay did not
     * produce is a point the hardware did not compute from this seed. */
    printf("{\"status\":\"%s\",\"seed\":%" PRIu64 ",\"steps\":%" PRIu64 ",\"expected\":%zu,"
           "\"checked\":%" PRIu64 ",\"matched\":%" PRIu64 ",\"unknown\":%" PRIu64
           ",\"wrongSeed\":%" PRIu64 ",\"malformed\":%" PRIu64 ",\"dpWeight\":%u}\n",
           (unknown || malformed || wrong_seed) ? "mismatch" : "ok",
           seed, steps, exp.n, checked, matched, unknown, wrong_seed, malformed, weight);
    return (unknown || malformed || wrong_seed) ? 1 : 0;
}

/* ---- merge --------------------------------------------------------------- */

typedef struct entry {
    ec2k_record rec;
    int used;
} entry;

static uint64_t fe_hash(const ec2k_fe *a)
{
    uint64_t h = 0x243F6A8885A308D3ULL;
    for (int i = 0; i < EC2K_WORDS; i++) {
        h ^= a->w[i] + 0x9E3779B97F4A7C15ULL + (h << 6) + (h >> 2);
        h ^= h >> 33;
        h *= 0xff51afd7ed558ccdULL;
    }
    return h;
}

static int cmd_merge(int argc, char **argv)
{
    size_t cap = 1 << 16;
    entry *tab = calloc(cap, sizeof(*tab));
    if (!tab) return 1;
    uint64_t records = 0, distinct = 0, duplicates = 0, collisions = 0, malformed = 0;
    ec2k_record hit_a = {0, {{0, 0, 0}}}, hit_b = hit_a;

    for (int i = 2; i < argc; i++) {
        FILE *f = fopen(argv[i], "rb");
        if (!f) {
            fprintf(stderr, "cannot read %s\n", argv[i]);
            free(tab);
            return 1;
        }
        uint8_t buf[EC2K_RECORD_BYTES];
        size_t got;
        while ((got = fread(buf, 1, sizeof(buf), f)) == sizeof(buf)) {
            ec2k_record rec;
            records++;
            if (!ec2k_record_decode(&rec, buf)) {
                malformed++;
                continue;
            }
            if (distinct * 2 >= cap) {
                size_t ncap = cap * 2;
                entry *nt = calloc(ncap, sizeof(*nt));
                if (!nt) { fclose(f); free(tab); return 1; }
                for (size_t k = 0; k < cap; k++) {
                    if (!tab[k].used) continue;
                    size_t j = (size_t)fe_hash(&tab[k].rec.x) & (ncap - 1);
                    while (nt[j].used) j = (j + 1) & (ncap - 1);
                    nt[j] = tab[k];
                }
                free(tab);
                tab = nt;
                cap = ncap;
            }
            size_t j = (size_t)fe_hash(&rec.x) & (cap - 1);
            while (tab[j].used && !ec2k_fe_equal(&tab[j].rec.x, &rec.x))
                j = (j + 1) & (cap - 1);
            if (!tab[j].used) {
                tab[j].used = 1;
                tab[j].rec = rec;
                distinct++;
            } else if (tab[j].rec.seed == rec.seed) {
                duplicates++;
            } else {
                if (!collisions) {
                    hit_a = tab[j].rec;
                    hit_b = rec;
                }
                collisions++;
            }
        }
        if (got != 0) malformed++;
        fclose(f);
    }

    char hex[34];
    printf("{\"status\":\"ok\",\"records\":%" PRIu64 ",\"distinct\":%" PRIu64
           ",\"duplicates\":%" PRIu64 ",\"malformed\":%" PRIu64 ",\"collisions\":%" PRIu64,
           records, distinct, duplicates, malformed, collisions);
    if (collisions) {
        ec2k_fe_to_hex(hex, &hit_a.x);
        printf(",\"collision\":{\"x\":\"%s\",\"seeds\":[%" PRIu64 ",%" PRIu64 "]}",
               hex, hit_a.seed, hit_b.seed);
    }
    printf("}\n");
    free(tab);
    return 0;
}

/* ---- start --------------------------------------------------------------- */

/* The start point a core's load window wants, as the 131-bit coordinates and
 * as the five 32-bit words the register map takes, so that a bring-up script
 * can paste them straight in. */
static int cmd_start(int argc, char **argv)
{
    uint64_t seed = opt_u64(argc, argv, "--seed", 1);
    ec2k_pt p;
    ec2k_point_from_seed(&p, seed);
    char hx[34], hy[34];
    ec2k_fe_to_hex(hx, &p.x);
    ec2k_fe_to_hex(hy, &p.y);
    printf("{\"status\":\"ok\",\"seed\":%" PRIu64 ",\"onCurve\":%s,\"x\":\"%s\",\"y\":\"%s\","
           "\"xWords\":[", seed, ec2k_on_curve(&p) ? "true" : "false", hx, hy);
    for (int i = 0; i < 5; i++) {
        uint32_t w = 0;
        for (int b = 0; b < 32; b++) {
            unsigned bit = (unsigned)(i * 32 + b);
            if (bit < EC2K_M && ((p.x.w[bit >> 6] >> (bit & 63)) & 1)) w |= 1u << b;
        }
        printf("%s\"0x%08x\"", i ? "," : "", w);
    }
    printf("],\"yWords\":[");
    for (int i = 0; i < 5; i++) {
        uint32_t w = 0;
        for (int b = 0; b < 32; b++) {
            unsigned bit = (unsigned)(i * 32 + b);
            if (bit < EC2K_M && ((p.y.w[bit >> 6] >> (bit & 63)) & 1)) w |= 1u << b;
        }
        printf("%s\"0x%08x\"", i ? "," : "", w);
    }
    printf("]}\n");
    return 0;
}

int main(int argc, char **argv)
{
    if (argc < 2) return usage();
    if (!strcmp(argv[1], "walk")) return cmd_walk(argc, argv);
    if (!strcmp(argv[1], "verify")) return cmd_verify(argc, argv);
    if (!strcmp(argv[1], "merge")) return cmd_merge(argc, argv);
    if (!strcmp(argv[1], "start")) return cmd_start(argc, argv);
    return usage();
}
