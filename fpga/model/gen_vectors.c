/*
 * gen_vectors.c - test vectors for the RTL, produced by the golden model.
 *
 * The testbenches do not contain any arithmetic of their own.  They read
 * these files and compare, so "the hardware is correct" means exactly "the
 * hardware agrees with the model", and the model's own correctness is
 * established separately in ecc2k130_test.c against field axioms, the
 * Frobenius relation sigma^2 + sigma + 2 = 0 and the subgroup order.
 *
 *   gen_vectors <outdir> [count]
 *
 * Every file is whitespace-separated hex, one case per line, because
 * $fscanf("%h") is the one file format every Verilog simulator agrees on.
 */
#include "ecc2k130.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static uint64_t rng = 0x9E3779B97F4A7C15ULL;

static uint64_t rnd(void)
{
    uint64_t z = (rng += 0x9E3779B97F4A7C15ULL);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
    return z ^ (z >> 31);
}

static void rnd_fe(ec2k_fe *a)
{
    a->w[0] = rnd();
    a->w[1] = rnd();
    a->w[2] = rnd() & 7;
}

static FILE *open_out(const char *dir, const char *name)
{
    char path[512];
    snprintf(path, sizeof(path), "%s/%s", dir, name);
    FILE *f = fopen(path, "w");
    if (!f) {
        fprintf(stderr, "cannot write %s\n", path);
        exit(1);
    }
    return f;
}

static void put_fe(FILE *f, const ec2k_fe *a)
{
    char hex[34];
    ec2k_fe_to_hex(hex, a);
    fputs(hex, f);
}

int main(int argc, char **argv)
{
    const char *dir = argc > 1 ? argv[1] : ".";
    int count = argc > 2 ? atoi(argv[2]) : 64;
    /* The campaign's cutoff is weight 34, which yields a point about once in
     * 2^25 steps -- nothing a simulation will ever see.  The vectors carry
     * the flag at whatever cutoff is asked for and the testbench is built
     * with the same one, so the two are comparing the same rule. */
    unsigned dpw = argc > 3 ? (unsigned)atoi(argv[3]) : EC2K_DP_WEIGHT;

    /* Multiplication.  The first cases are the ones a wrong fold or a wrong
     * rotation direction gets wrong while random vectors still pass: the
     * basis elements themselves, and the field's one. */
    FILE *f = open_out(dir, "mul.vec");
    ec2k_fe a, b, y, one;
    ec2k_fe_one(&one);
    for (int i = 0; i < 8; i++) {
        ec2k_fe_zero(&a);
        a.w[i >> 6] = (uint64_t)1 << (i & 63);
        for (int j = 0; j < 8; j++) {
            ec2k_fe_zero(&b);
            b.w[j >> 6] = (uint64_t)1 << (j & 63);
            ec2k_fe_mul(&y, &a, &b);
            put_fe(f, &a); fputc(' ', f);
            put_fe(f, &b); fputc(' ', f);
            put_fe(f, &y); fputc('\n', f);
        }
    }
    for (int i = 0; i < count; i++) {
        rnd_fe(&a);
        rnd_fe(&b);
        if (i == 0) b = one;   /* a * 1 == a */
        if (i == 1) ec2k_fe_zero(&b);
        ec2k_fe_mul(&y, &a, &b);
        put_fe(f, &a); fputc(' ', f);
        put_fe(f, &b); fputc(' ', f);
        put_fe(f, &y); fputc('\n', f);
    }
    fclose(f);

    /* Frobenius powers, including the ones the iteration uses. */
    f = open_out(dir, "frob.vec");
    for (int i = 0; i < count; i++) {
        rnd_fe(&a);
        for (unsigned j = EC2K_J_MIN; j < EC2K_J_MIN + EC2K_J_COUNT; j++) {
            ec2k_fe_frob(&y, &a, j);
            put_fe(f, &a);
            fprintf(f, " %u ", j);
            put_fe(f, &y);
            fputc('\n', f);
        }
    }
    fclose(f);

    /* Inversion. */
    f = open_out(dir, "inv.vec");
    for (int i = 0; i < count; i++) {
        rnd_fe(&a);
        if (ec2k_fe_is_zero(&a)) continue;
        if (i == 0) a = one;
        ec2k_fe_inv(&y, &a);
        put_fe(f, &a); fputc(' ', f);
        put_fe(f, &y); fputc('\n', f);
    }
    fclose(f);

    /* One rho iteration: the point, the j it selects, whether it is
     * exceptional, the resulting point and whether that point is
     * distinguished. */
    f = open_out(dir, "step.vec");
    for (int i = 0; i < count; i++) {
        ec2k_pt p, q;
        ec2k_point_from_seed(&p, rnd());
        unsigned j = ec2k_step_j(&p.x);
        int ok = ec2k_step(&q, &p);
        put_fe(f, &p.x); fputc(' ', f);
        put_fe(f, &p.y);
        fprintf(f, " %u %d ", j, ok ? 0 : 1);
        if (ok) {
            put_fe(f, &q.x); fputc(' ', f);
            put_fe(f, &q.y);
            fprintf(f, " %d", ec2k_is_distinguished_w(&q.x, dpw) ? 1 : 0);
        } else {
            put_fe(f, &p.x); fputc(' ', f);
            put_fe(f, &p.y);
            fprintf(f, " 0");
        }
        fputc('\n', f);
    }
    fclose(f);

    /* A run of consecutive iterations from one start, which is what the core
     * does: the testbench loads the first point and then follows. */
    f = open_out(dir, "chain.vec");
    {
        ec2k_pt p;
        ec2k_point_from_seed(&p, 20260919);
        put_fe(f, &p.x); fputc(' ', f);
        put_fe(f, &p.y); fputc('\n', f);
        for (int i = 0; i < count * 4; i++) {
            ec2k_pt q;
            if (!ec2k_step(&q, &p)) break;
            put_fe(f, &q.x); fputc(' ', f);
            put_fe(f, &q.y);
            fprintf(f, " %d\n", ec2k_is_distinguished_w(&q.x, dpw) ? 1 : 0);
            p = q;
        }
    }
    fclose(f);

    printf("{\"status\":\"ok\",\"dir\":\"%s\",\"cases\":%d,\"dpWeight\":%u}\n", dir, count, dpw);
    return 0;
}
