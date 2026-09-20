/*
 * ca_cli.c - command line front end for libcryptanalysis.
 *
 *   ca version
 *   ca factor N
 *   ca prime N
 *   ca ec-order --p P --a A --b B
 *   ca gen   --group zp|ec --p P [--a A --b B] [--order N] [--x X] [--seed S]
 *   ca gpu-info
 *   ca curve --name NAME | (--group ec --p P --a A --b B [--order N]) | --list
 *            report a curve's endomorphism structure (GLV) and chosen solver
 *   ca solve --alg bsgs|rho|kangaroo|grumpy|precomp|glv|dlog|gpu-rho --group zp|ec --p P [--a A --b
 * B]
 *            --order N --g G --h H [--lo L --hi U] [--threads T] [--seed S]
 *            [--dp-bits D] [--r R] [--walks W] [--no-negation] [--m M] [--alpha F]
 *            [--solver auto|bsgs|rho|kangaroo|grumpy] [--max-ops K]
 *            gpu-rho also takes [--backend auto|cuda|emulate] [--device D]
 *            [--tpb T] [--blocks B] [--steps S]
 *            precomp also takes [--table CHAINS] [--coverage F] [--threads T]
 *            [--walks W] [--early-abort|--no-early-abort]
 *            [--max-precomp-ops K] [--max-online-ops K]
 *   ca cheon --group zp|ec --p P [--a A --b B] --order Q --g G --d D
 *            (--ga GA --gad GAD | --alpha X)
 *   ca ic    --p P --g G --h H [--method lsieve|rexp] [--B B] [--C C]
 *            [--threads T] [--seed S] [--verbose]
 *   ca dist-walk  --group ... --order N --g G --h H --campaign-seed S --unit U
 *            --steps K [--dp-bits D] [--r R] [--walks W] [--max-points P]
 *            [--out FILE]            one work unit; 32-byte records to FILE
 *   ca dist-merge --group ... --order N --g G --h H --campaign-seed S
 *            [--dp-bits D] [--r R] [--no-verify] FILE...   (- reads stdin)
 *   ca dist-info  --group ... --order N --g G --h H --campaign-seed S
 *            [--dp-bits D] [--r R]   campaign id and expected point count
 *   ca num <op>   the number-theory surface of ca_modarith.h:
 *            powmod --base B --exp E --mod M | invmod --a A --mod M
 *            gcd --a A --b B | isqrt --n N | iroot --n N --k K
 *            sqrtmod --a A --p P | legendre --a A --p P
 *            crt --r1 R --m1 M --r2 R --m2 M | next-prime --n N
 *            order --a A --p P | primitive-root --p P | sieve --bound B
 *            mont --p P --a A --b B
 *   ca group <op> --group zp|ec --p P [--a A --b B] [--order N] ... :
 *            exp --elem X --k K | div --a A --b B | order --elem X
 *            generator [--seed S] | random [--seed S] | lift-x --x X
 *
 * Elements: Z_p^* "123"; E(F_p) "x,y" or "inf".  Output is one JSON object
 * on stdout; errors go to stderr.
 *
 * Exit status distinguishes three outcomes, so a shell caller can branch on
 * them without parsing the JSON:
 *
 *   0  an answer
 *   1  a well-posed question whose answer is that there is none: the element
 *      is not invertible, the residue is not a square, the x does not lift to
 *      a curve point, the search found no generator, the log was not found
 *   2  a malformed invocation: unknown command, missing or unparseable option
 *
 * Coverage of the public headers is checked by scripts/cli_smoke.sh, which is
 * where a newly exported function that no command reaches will show up.
 */
#include "cryptanalysis/cryptanalysis.h"
#include "cryptanalysis/ca_dist.h"
#include "ca_device.cuh"

#include <fcntl.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static int argc_g;
static char **argv_g;

static _Noreturn void die(const char *msg);

/* C11 5.1.2.2.1p2 guarantees argv[0]..argv[argc-1] are non-null, but a static
 * analyser only sees a char ** of unknown provenance.  Say it once, here. */
static int arg_is(int i, const char *name)
{
    const char *a = argv_g[i];
    return a != NULL && strcmp(a, name) == 0;
}

static const char *opt(const char *name)
{
    for (int i = 2; i + 1 < argc_g; i++)
        if (arg_is(i, name)) return argv_g[i + 1];
    return NULL;
}

static int flag(const char *name)
{
    for (int i = 2; i < argc_g; i++)
        if (arg_is(i, name)) return 1;
    return 0;
}

static uint64_t opt_u64(const char *name, uint64_t def)
{
    const char *v = opt(name);
    if (!v) return def;
    char *end = NULL;
    unsigned long long u = strtoull(v, &end, 0);
    if (end == v || *end != '\0') die("option value is not an integer");
    return (uint64_t)u;
}

/* strtod, not atof: atof cannot report a malformed value (cert-err34-c). */
static double opt_f(const char *name, double def)
{
    const char *v = opt(name);
    if (!v) return def;
    char *end = NULL;
    double d = strtod(v, &end);
    if (end == v || *end != '\0') die("option value is not a number");
    return d;
}

static _Noreturn void die(const char *msg)
{
    fprintf(stderr, "error: %s\n", msg);
    exit(2);
}

static _Noreturn void die_status(ca_status rc)
{
    const char *m = ca_last_error();
    fprintf(stderr, "error: %s%s%s\n", ca_status_string(rc), m && *m ? ": " : "", m ? m : "");
    printf("{\"status\":\"%s\"}\n", ca_status_string(rc));
    exit(1);
}

static _Noreturn void usage(void)
{
    fprintf(
        stderr,
        "usage: ca <command> [options]\n"
        "  version | factor N | prime N | ec-order --p P --a A --b B | gpu-info\n"
        "  gen   --group zp|ec --p P [--a A --b B] [--order N] [--x X] [--seed S]\n"
        "  solve --alg bsgs|rho|kangaroo|grumpy|precomp|glv|dlog|gpu-rho --group zp|ec --p P [--a "
        "A "
        "--b B]\n"
        "        --order N --g G --h H [--lo L --hi U] [--threads T] [--seed S] ...\n"
        "  curve --name NAME | (--group ec --p P --a A --b B [--order N]) | --list\n"
        "  cheon --group zp|ec --p P [--a A --b B] --order Q --g G --d D (--ga GA --gad GAD | "
        "--alpha X)\n"
        "  ic    --p P --g G --h H [--method lsieve|rexp] [--B B] [--C C] [--threads T] "
        "[--verbose]\n"
        "  dist-walk  --group ... --order N --g G --h H --campaign-seed S --unit U --steps K\n"
        "             [--dp-bits D] [--r R] [--walks W] [--max-points P] [--out FILE]\n"
        "  dist-merge --group ... --order N --g G --h H --campaign-seed S [--dp-bits D]\n"
        "             [--r R] [--no-verify] FILE...\n"
        "  dist-info  --group ... --order N --g G --h H --campaign-seed S [--dp-bits D]\n"
        "  num   powmod|invmod|gcd|isqrt|iroot|sqrtmod|legendre|crt|next-prime|order|\n"
        "        primitive-root|sieve|mont  (see the header comment for each op's options)\n"
        "  group exp|div|order|generator|random|lift-x --group zp|ec --p P [--a A --b B] ...\n");
    exit(2);
}

static void make_group(ca_group *g)
{
    const char *kind = opt("--group");
    uint64_t p = opt_u64("--p", 0);
    uint64_t order = opt_u64("--order", 0);
    if (!kind || !p) die("--group and --p are required");
    ca_status rc;
    if (strcmp(kind, "zp") == 0) rc = ca_group_zp_init(g, p, order);
    else if (strcmp(kind, "ec") == 0) rc = ca_group_ec_init(g, p, opt_u64("--a", 0), opt_u64("--b", 0), order);
    else die("--group must be zp or ec");
    if (rc != CA_OK) die_status(rc);
}

static void parse_elem(const ca_group *g, const char *s, ca_elem *e)
{
    uint64_t w[4] = {0, 0, 0, 0};
    if (!s) die("missing element");
    if (g->kind == CA_GROUP_ZP) {
        w[0] = strtoull(s, NULL, 0);
    } else if (strcmp(s, "inf") == 0 || strcmp(s, "O") == 0) {
        w[2] = 1;
    } else {
        char *end;
        w[0] = strtoull(s, &end, 0);
        if (*end != ',') die("EC element must be x,y or inf");
        w[1] = strtoull(end + 1, NULL, 0);
    }
    if (!ca_group_encode(g, e, w)) die("element is not in the group");
}

static void print_elem(const ca_group *g, const ca_elem *e)
{
    uint64_t w[4];
    ca_group_decode(g, w, e);
    if (g->kind == CA_GROUP_ZP) printf("\"%" PRIu64 "\"", w[0]);
    else if (w[2]) printf("\"inf\"");
    else printf("\"%" PRIu64 ",%" PRIu64 "\"", w[0], w[1]);
}

static void print_stats(const ca_stats *st)
{
    printf("\"ops\":%" PRIu64 ",\"iterations\":%" PRIu64 ",\"table_entries\":%" PRIu64
           ",\"collisions\":%" PRIu64 ",\"bytes_peak\":%" PRIu64 ",\"seconds\":%.6f,\"threads\":%u",
           st->group_ops, st->iterations, st->table_entries, st->collisions, st->bytes_peak,
           st->seconds, st->threads);
}

static int cmd_gen(void)
{
    ca_group g;
    make_group(&g);
    uint64_t seed = opt_u64("--seed", 0);
    if (g.kind == CA_GROUP_EC && g.order == 0) {
        uint64_t n;
        ca_status rc = ca_ec_count_points(g.p, g.a, g.b, &n, NULL);
        if (rc != CA_OK) die_status(rc);
        ca_factorization f;
        ca_factorize(n, &f);
        g.order = f.f[f.count - 1].p;
        g.cofactor = n / g.order;
    }
    ca_elem gen, h;
    ca_status rc = ca_group_find_generator(&g, &gen, seed);
    if (rc != CA_OK) die_status(rc);
    uint64_t x = opt("--x") ? opt_u64("--x", 0) : 0;
    if (!opt("--x")) ca_group_random_power(&g, &h, &gen, seed ? seed + 1 : 0, &x);
    else ca_group_mul(&g, &h, &gen, x, NULL);
    printf("{\"status\":\"ok\",\"group\":\"%s\",\"p\":%" PRIu64 ",", g.kind == CA_GROUP_ZP ? "zp" : "ec", g.p);
    if (g.kind == CA_GROUP_EC) printf("\"a\":%" PRIu64 ",\"b\":%" PRIu64 ",", g.a, g.b);
    printf("\"order\":%" PRIu64 ",\"cofactor\":%" PRIu64 ",\"g\":", g.order, g.cofactor);
    print_elem(&g, &gen);
    printf(",\"h\":");
    print_elem(&g, &h);
    printf(",\"x\":%" PRIu64 "}\n", x);
    return 0;
}

static int cmd_solve(void)
{
    ca_group g;
    make_group(&g);
    const char *alg = opt("--alg");
    if (!alg) die("--alg is required");
    ca_elem base, target;
    parse_elem(&g, opt("--g"), &base);
    parse_elem(&g, opt("--h"), &target);
    uint64_t lo = opt_u64("--lo", 0), hi = opt_u64("--hi", 0);
    ca_dlog_params dp;
    ca_dlog_params_default(&dp);
    dp.rho.threads = (uint32_t)opt_u64("--threads", 1);
    dp.rho.seed = dp.kangaroo.seed = opt_u64("--seed", 0);
    dp.rho.dp_bits = (int32_t)opt_u64("--dp-bits", (uint64_t)-1);
    dp.rho.r = (uint32_t)opt_u64("--r", 0);
    dp.rho.walks_per_thread = (uint32_t)opt_u64("--walks", 0);
    dp.rho.negation_map = !flag("--no-negation");
    dp.rho.max_ops = dp.bsgs.max_ops = dp.kangaroo.max_ops = dp.grumpy.max_ops = opt_u64("--max-ops", 0);
    dp.bsgs.table_size = opt_u64("--table", 0);
    dp.kangaroo.dp_bits = (int32_t)opt_u64("--dp-bits", (uint64_t)-1);
    dp.kangaroo.herd_size = (uint32_t)opt_u64("--herd", 0);
    dp.grumpy.m = opt_u64("--m", 0);
    dp.grumpy.alpha = opt_f("--alpha", 0.7);
    const char *solver = opt("--solver");
    if (solver) {
        if (!strcmp(solver, "auto")) dp.solver = CA_SOLVER_AUTO;
        else if (!strcmp(solver, "bsgs")) dp.solver = CA_SOLVER_BSGS;
        else if (!strcmp(solver, "rho")) dp.solver = CA_SOLVER_RHO;
        else if (!strcmp(solver, "kangaroo")) dp.solver = CA_SOLVER_KANGAROO;
        else if (!strcmp(solver, "grumpy")) dp.solver = CA_SOLVER_GRUMPY;
        else die("unknown --solver");
    }
    uint64_t x = 0;
    ca_stats st = {0};
    ca_status rc;
    if (!strcmp(alg, "gpu-rho")) {
        ca_gpu_rho_params gp;
        ca_gpu_rho_params_default(&gp);
        const char *be = opt("--backend");
        if (be) {
            if (!strcmp(be, "auto"))
                gp.backend = CA_GPU_BACKEND_AUTO;
            else if (!strcmp(be, "cuda"))
                gp.backend = CA_GPU_BACKEND_CUDA;
            else if (!strcmp(be, "emulate"))
                gp.backend = CA_GPU_BACKEND_EMULATE;
            else
                die("--backend must be auto, cuda or emulate");
        }
        gp.device = (int32_t)opt_u64("--device", 0);
        gp.threads_per_block = (uint32_t)opt_u64("--tpb", 0);
        gp.blocks = (uint32_t)opt_u64("--blocks", 0);
        gp.steps_per_launch = (uint32_t)opt_u64("--steps", 0);
        gp.r = (uint32_t)opt_u64("--r", 0);
        gp.dp_bits = (int32_t)opt_u64("--dp-bits", (uint64_t)-1);
        gp.negation_map = !flag("--no-negation");
        gp.seed = opt_u64("--seed", 0);
        gp.max_ops = opt_u64("--max-ops", 0);
        rc = ca_gpu_rho_solve(&g, &base, &target, &gp, &x, &st);
        if (rc == CA_OK) {
            printf("{\"status\":\"ok\",\"alg\":\"gpu-rho\",\"x\":%" PRIu64 ",\"launches\":%u,", x,
                   st.reserved);
            print_stats(&st);
            printf("}\n");
            return 0;
        }
        printf("{\"status\":\"%s\",\"alg\":\"gpu-rho\",", ca_status_string(rc));
        print_stats(&st);
        printf("}\n");
        fprintf(stderr, "error: %s %s\n", ca_status_string(rc), ca_last_error());
        return 1;
    }
    if (!strcmp(alg, "glv")) {
        if (g.kind != CA_GROUP_EC) die("--alg glv needs --group ec");
        ca_group cg;
        ca_curve_info info;
        rc = ca_curve_group(&cg, g.p, g.a, g.b, g.order, &info);
        if (rc != CA_OK) die_status(rc);
        /* base/target are valid in cg: identical curve and Montgomery domain. */
        rc = ca_curve_solve(&cg, &base, &target, opt_u64("--seed", 0), &x, &info, &st);
        const char *ek = info.endo == CA_CURVE_ENDO_J0      ? "j0"
                         : info.endo == CA_CURVE_ENDO_J1728 ? "j1728"
                                                            : "none";
        if (rc == CA_OK) {
            printf("{\"status\":\"ok\",\"alg\":\"glv\",\"x\":%" PRIu64
                   ",\"endomorphism\":\"%s\",\"aut_order\":%u,\"lambda\":%" PRIu64
                   ",\"rho_speedup\":%.4f,",
                   x, ek, info.aut_order, info.lambda, info.rho_speedup);
            print_stats(&st);
            printf("}\n");
            return 0;
        }
        printf("{\"status\":\"%s\",\"alg\":\"glv\",", ca_status_string(rc));
        print_stats(&st);
        printf("}\n");
        fprintf(stderr, "error: %s %s\n", ca_status_string(rc), ca_last_error());
        return 1;
    }
    if (!strcmp(alg, "precomp")) {
        ca_precomp_params pp;
        ca_precomp_params_default(&pp);
        pp.seed = opt_u64("--seed", 0);
        pp.dp_bits = (int32_t)opt_u64("--dp-bits", (uint64_t)-1);
        pp.r = (uint32_t)opt_u64("--r", 0);
        pp.table_size = opt_u64("--table", 0);
        pp.coverage = opt_f("--coverage", 0);
        pp.threads = (uint32_t)opt_u64("--threads", 1);
        pp.walks = (uint32_t)opt_u64("--walks", 0);
        pp.early_abort = flag("--early-abort") ? 1 : (flag("--no-early-abort") ? 0 : -1);
        pp.max_precomp_ops = opt_u64("--max-precomp-ops", 0);
        pp.max_online_ops = opt_u64("--max-online-ops", 0);
        ca_stats build = {0}, online = {0};
        ca_precomp_table *ptab = NULL;
        rc = ca_precomp_table_new(&g, &base, &pp, &ptab, &build);
        if (rc != CA_OK) {
            printf("{\"status\":\"%s\",\"alg\":\"precomp\"}\n", ca_status_string(rc));
            fprintf(stderr, "error: %s %s\n", ca_status_string(rc), ca_last_error());
            return 1;
        }
        int32_t dp_bits = 0;
        uint64_t chains = 0, precomp_ops = 0;
        uint32_t rr = 0;
        ca_precomp_table_info(ptab, &dp_bits, &chains, &rr, &precomp_ops);
        rc = ca_precomp_table_solve(ptab, &target, &x, &online);
        if (rc == CA_OK) {
            printf("{\"status\":\"ok\",\"alg\":\"precomp\",\"x\":%" PRIu64
                   ",\"precomp_ops\":%" PRIu64 ",\"chains\":%" PRIu64 ",\"dp_bits\":%" PRId32
                   ",\"r\":%u,",
                   x, precomp_ops, chains, dp_bits, rr);
            print_stats(&online);
            printf("}\n");
            ca_precomp_table_free(ptab);
            return 0;
        }
        printf("{\"status\":\"%s\",\"alg\":\"precomp\",\"precomp_ops\":%" PRIu64 ",",
               ca_status_string(rc), precomp_ops);
        print_stats(&online);
        printf("}\n");
        fprintf(stderr, "error: %s %s\n", ca_status_string(rc), ca_last_error());
        ca_precomp_table_free(ptab);
        return 1;
    }
    if (!strcmp(alg, "bsgs")) rc = ca_bsgs_solve(&g, &base, &target, lo, hi, &dp.bsgs, &x, &st);
    else if (!strcmp(alg, "rho")) rc = ca_rho_solve(&g, &base, &target, &dp.rho, &x, &st);
    else if (!strcmp(alg, "kangaroo")) rc = ca_kangaroo_solve(&g, &base, &target, lo, hi, &dp.kangaroo, &x, &st);
    else if (!strcmp(alg, "grumpy")) rc = ca_grumpy_solve(&g, &base, &target, lo, hi, &dp.grumpy, &x, &st);
    else if (!strcmp(alg, "dlog")) rc = ca_pohlig_hellman(&g, &base, &target, &dp, &x, &st);
    else die("unknown --alg");
    if (rc != CA_OK) {
        printf("{\"status\":\"%s\",\"alg\":\"%s\",", ca_status_string(rc), alg);
        print_stats(&st);
        printf("}\n");
        fprintf(stderr, "error: %s %s\n", ca_status_string(rc), ca_last_error());
        return 1;
    }
    printf("{\"status\":\"ok\",\"alg\":\"%s\",\"x\":%" PRIu64 ",", alg, x);
    print_stats(&st);
    printf("}\n");
    return 0;
}

static int cmd_cheon(void)
{
    ca_group g;
    make_group(&g);
    ca_elem gen, ga, gad;
    parse_elem(&g, opt("--g"), &gen);
    uint64_t d = opt_u64("--d", 0);
    if (!d) {
        double cost;
        d = ca_cheon_best_divisor(g.order, &cost);
    }
    if (opt("--alpha")) {
        ca_status rc = ca_cheon_make_instance(&g, &gen, opt_u64("--alpha", 0), d, &ga, &gad);
        if (rc != CA_OK) die_status(rc);
    } else {
        parse_elem(&g, opt("--ga"), &ga);
        parse_elem(&g, opt("--gad"), &gad);
    }
    uint64_t alpha = 0;
    ca_stats st = {0};
    ca_cheon_params cp;
    ca_cheon_params_default(&cp);
    cp.max_exps = opt_u64("--max-exps", 0);
    ca_status rc = ca_cheon_solve(&g, &gen, &ga, &gad, d, &cp, &alpha, &st);
    if (rc != CA_OK) die_status(rc);
    printf("{\"status\":\"ok\",\"alpha\":%" PRIu64 ",\"d\":%" PRIu64 ",\"exponentiations\":%" PRIu64 ",",
           alpha, d, st.iterations);
    print_stats(&st);
    printf(",\"g_alpha\":");
    print_elem(&g, &ga);
    printf(",\"g_alpha_d\":");
    print_elem(&g, &gad);
    printf("}\n");
    return 0;
}

static int cmd_ic(void)
{
    uint64_t p = opt_u64("--p", 0), gg = opt_u64("--g", 0), h = opt_u64("--h", 0);
    if (!p || !gg || !h) die("--p, --g and --h are required");
    ca_ic_params pr;
    ca_ic_params_default(&pr);
    const char *m = opt("--method");
    if (m && !strcmp(m, "rexp")) pr.method = CA_IC_RANDOM_EXPONENT;
    pr.factor_base_bound = (uint32_t)opt_u64("--B", 0);
    pr.sieve_radius = (uint32_t)opt_u64("--C", 0);
    pr.threads = (uint32_t)opt_u64("--threads", 1);
    pr.seed = opt_u64("--seed", 0);
    pr.verbose = flag("--verbose") || flag("-v");
    uint64_t x = 0;
    ca_ic_stats st;
    ca_status rc = ca_ic_solve(p, gg, h, &pr, &x, &st);
    if (rc != CA_OK) die_status(rc);
    printf("{\"status\":\"ok\",\"x\":%" PRIu64 ",\"check\":%" PRIu64 ",\"factor_base\":%u,\"unknowns\":%u,"
           "\"relations\":%u,\"verified_logs\":%u,\"sieve_seconds\":%.3f,\"linalg_seconds\":%.3f,"
           "\"total_seconds\":%.3f,\"lanczos_iterations\":%u,\"threads\":%u}\n",
           x, ca_powmod(gg, x, p), st.factor_base_size, st.unknowns, st.relations, st.verified_logs,
           st.sieve_seconds, st.linalg_seconds, st.total_seconds, st.lanczos_iterations, st.threads);
    return 0;
}

/* ---- the distributed protocol ------------------------------------------ */

/* The campaign as the fleet sees it.  --campaign-seed is required rather
 * than defaulted: a walker that invents its own seed produces points that
 * merge with nobody, and it would do it silently. */
static void make_campaign(const ca_group *g, ca_dist_campaign *c)
{
    ca_dist_campaign_default(c);
    if (!opt("--campaign-seed")) die("--campaign-seed is required (the fleet must share it)");
    c->seed = opt_u64("--campaign-seed", 0);
    if (c->seed == 0) die("--campaign-seed must not be 0");
    c->r = (uint32_t)opt_u64("--r", 0);
    c->dp_bits = opt("--dp-bits") ? (int32_t)opt_u64("--dp-bits", 0) : -1;
    ca_status rc = ca_dist_resolve(g, c);
    if (rc != CA_OK) die_status(rc);
}

typedef struct walk_sink {
    FILE *out;
    uint64_t points;
    int failed;
} walk_sink;

static ca_status walk_write(void *ctx, const ca_dist_point *pt)
{
    walk_sink *w = ctx;
    unsigned char rec[CA_DIST_POINT_BYTES];
    ca_dist_point_encode(rec, pt);
    if (fwrite(rec, 1, sizeof(rec), w->out) != sizeof(rec)) {
        w->failed = 1;
        return CA_ERR_INTERNAL;
    }
    w->points++;
    return CA_OK;
}

static int cmd_dist_walk(void)
{
    ca_group g;
    make_group(&g);
    ca_elem base, target;
    parse_elem(&g, opt("--g"), &base);
    parse_elem(&g, opt("--h"), &target);
    ca_dist_campaign c;
    make_campaign(&g, &c);

    ca_dist_unit u = {0};
    u.id = opt_u64("--unit", 0);
    u.walks = (uint32_t)opt_u64("--walks", 0);
    u.max_steps = opt_u64("--steps", 0);
    u.max_points = opt_u64("--max-points", 0);
    if (!u.max_steps && !u.max_points)
        die("--steps or --max-points is required (a unit is a budget)");

    const char *path = opt("--out");
    walk_sink sink = {stdout, 0, 0};
    if (path) {
        /* open() with an explicit mode rather than fopen(): a corpus is the
         * output of machine time and there is no reason for it to be
         * world-readable by default, which is what fopen's 0666 leaves after
         * a permissive umask.  O_EXCL is deliberately absent: a unit that is
         * re-walked rewrites its own file, and refusing that would make a
         * retry an error. */
        int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, S_IRUSR | S_IWUSR);
        if (fd < 0) die("cannot open --out for writing");
        sink.out = fdopen(fd, "wb");
        if (!sink.out) {
            close(fd);
            die("cannot open --out for writing");
        }
    }
    ca_stats st = {0};
    ca_status rc = ca_dist_walk(&g, &base, &target, &c, &u, walk_write, &sink, &st);
    /* Points already written stay written: a unit that dies half way is a
     * shorter unit, not a corrupt one, because every record is complete and
     * the merger does not care how many a unit produced. */
    int flushed = fflush(sink.out) == 0;
    if (path) {
        if (fclose(sink.out) != 0) flushed = 0;
    }
    if (sink.failed || !flushed) die("writing points failed");
    if (rc != CA_OK && rc != CA_ERR_LIMIT) die_status(rc);
    FILE *report = path ? stdout : stderr; /* records own stdout when there is no --out */
    fprintf(report,
            "{\"status\":\"ok\",\"campaign\":%" PRIu64 ",\"unit\":%" PRIu64 ",\"points\":%" PRIu64
            ",\"bytes\":%" PRIu64 ",\"dp_bits\":%d,\"r\":%u,\"steps\":%" PRIu64 "}\n",
            ca_dist_campaign_id(&g, &base, &target, &c), u.id, sink.points,
            sink.points * (uint64_t)CA_DIST_POINT_BYTES, c.dp_bits, c.r, st.group_ops);
    return 0;
}

static int merge_file(ca_dist_merger *m, const char *path, uint64_t *acc, uint64_t *dup,
                      uint64_t *rej)
{
    int owned = strcmp(path, "-") != 0;
    FILE *in = owned ? fopen(path, "rb") : stdin;
    if (!in) return -1;
    /* A partial record at the end of a file is a truncated upload, which is
     * what a killed agent leaves behind.  Read whole records and report the
     * remainder rather than guessing at it. */
    unsigned char buf[CA_DIST_POINT_BYTES * 256];
    ca_dist_point pts[256];
    size_t carry = 0;
    int rc = 0;
    for (;;) {
        size_t want = sizeof(buf) - carry;
        size_t got = fread(buf + carry, 1, want, in);
        if (got == 0) break;
        size_t have = carry + got;
        size_t whole = have / CA_DIST_POINT_BYTES;
        for (size_t i = 0; i < whole; i++)
            ca_dist_point_decode(&pts[i], buf + i * CA_DIST_POINT_BYTES);
        size_t a = 0, d = 0, r = 0;
        if (ca_dist_merger_add(m, pts, whole, &a, &d, &r) != CA_OK) {
            rc = -2;
            break;
        }
        *acc += a;
        *dup += d;
        *rej += r;
        carry = have - whole * CA_DIST_POINT_BYTES;
        memmove(buf, buf + whole * CA_DIST_POINT_BYTES, carry);
        /* fread only comes back short at end-of-file or on an error, and
         * after an error the stream position is indeterminate: stop here
         * rather than read again. */
        if (got < want) break;
    }
    if (rc == 0) {
        if (ferror(in))
            rc = -3; /* an I/O error is not an end-of-file */
        else if (carry)
            rc = 1; /* truncated tail */
    }
    if (owned) fclose(in);
    return rc;
}

static int cmd_dist_merge(void)
{
    ca_group g;
    make_group(&g);
    ca_elem base, target;
    parse_elem(&g, opt("--g"), &base);
    parse_elem(&g, opt("--h"), &target);
    ca_dist_campaign c;
    make_campaign(&g, &c);

    ca_dist_merger *m = NULL;
    ca_status rc = ca_dist_merger_new(&m, &g, &base, &target, &c, 0);
    if (rc != CA_OK) die_status(rc);
    if (flag("--no-verify")) ca_dist_merger_set_verify(m, 0);

    uint64_t acc = 0, dup = 0, rej = 0;
    int truncated = 0, files = 0;
    for (int i = 2; i < argc_g; i++) {
        const char *a = argv_g[i];
        if (a[0] == '-' && a[1] == '-') {
            i++;
            continue;
        } /* skip option pairs */
        if (a[0] == '-' && a[1] != '\0' && strcmp(a, "-") != 0) continue;
        files++;
        int r = merge_file(m, a, &acc, &dup, &rej);
        if (r == -1) {
            ca_dist_merger_free(m);
            die("cannot open input file");
        }
        if (r == -2) {
            ca_dist_merger_free(m);
            die_status(CA_ERR_NOMEM);
        }
        if (r == -3) {
            ca_dist_merger_free(m);
            die("reading input file failed");
        }
        if (r == 1) truncated++;
    }
    if (!files) {
        ca_dist_merger_free(m);
        die("no input files (use - for stdin)");
    }

    uint64_t x = 0;
    int solved = ca_dist_merger_solved(m, &x);
    printf("{\"status\":\"ok\",\"campaign\":%" PRIu64 ",\"files\":%d,\"accepted\":%" PRIu64
           ",\"duplicates\":%" PRIu64 ",\"rejected\":%" PRIu64 ",\"stored\":%zu,\"truncated\":%d,"
           "\"solved\":%s",
           ca_dist_campaign_id(&g, &base, &target, &c), files, acc, dup, rej,
           ca_dist_merger_size(m), truncated, solved ? "true" : "false");
    if (solved) printf(",\"x\":%" PRIu64, x);
    printf("}\n");
    ca_dist_merger_free(m);
    /* Exit 0 whether or not it solved: "no collision yet" is the normal
     * state of a campaign, and a scheduler that read it as failure would
     * retry the whole corpus every pass. */
    return 0;
}

/* ---------------------------------------------------------------- num ----
 * The contents of ca_modarith.h, one subcommand each.  These are the
 * primitives every solver in the library is built from; having them on the
 * command line is what makes a failing solver debuggable by hand.
 */
static const char *sub(void) { return argc_g > 2 ? argv_g[2] : NULL; }

static int cmd_num(void)
{
    const char *op = sub();
    if (!op) die("num needs an operation");

    if (!strcmp(op, "powmod")) {
        uint64_t m = opt_u64("--mod", 0);
        if (m < 2) die("--mod must be at least 2");
        printf("{\"result\":\"%" PRIu64 "\"}\n",
               ca_powmod(opt_u64("--base", 0), opt_u64("--exp", 0), m));
        return 0;
    }
    if (!strcmp(op, "invmod")) {
        uint64_t m = opt_u64("--mod", 0);
        if (m < 2) die("--mod must be at least 2");
        uint64_t a = opt_u64("--a", 0);
        uint64_t inv = ca_invmod(a, m);
        /* ca_invmod returns 0 when a is not invertible; 0 is never a unit for
         * m >= 2, so the encoding is unambiguous. */
        if (inv == 0) {
            printf("{\"invertible\":false,\"gcd\":\"%" PRIu64 "\"}\n", ca_gcd(a % m, m));
            return 1;
        }
        printf("{\"invertible\":true,\"result\":\"%" PRIu64 "\"}\n", inv);
        return 0;
    }
    if (!strcmp(op, "gcd")) {
        printf("{\"result\":\"%" PRIu64 "\"}\n", ca_gcd(opt_u64("--a", 0), opt_u64("--b", 0)));
        return 0;
    }
    if (!strcmp(op, "isqrt")) {
        uint64_t n = opt_u64("--n", 0);
        uint64_t r = ca_isqrt(n);
        printf("{\"result\":\"%" PRIu64 "\",\"exact\":%s}\n", r, r * r == n ? "true" : "false");
        return 0;
    }
    if (!strcmp(op, "iroot")) {
        unsigned k = (unsigned)opt_u64("--k", 2);
        if (k == 0) die("--k must be positive");
        printf("{\"result\":\"%" PRIu64 "\"}\n", ca_iroot(opt_u64("--n", 0), k));
        return 0;
    }
    if (!strcmp(op, "sqrtmod")) {
        uint64_t p = opt_u64("--p", 0), a = opt_u64("--a", 0), root = 0;
        if (p < 2) die("--p must be a prime at least 2");
        if (!ca_sqrtmod_prime(a, p, &root)) {
            printf("{\"square\":false}\n");
            return 1;
        }
        printf("{\"square\":true,\"root\":\"%" PRIu64 "\"}\n", root);
        return 0;
    }
    if (!strcmp(op, "legendre")) {
        uint64_t p = opt_u64("--p", 0);
        if (p < 3) die("--p must be an odd prime");
        printf("{\"result\":%d}\n", ca_legendre(opt_u64("--a", 0), p));
        return 0;
    }
    if (!strcmp(op, "crt")) {
        uint64_t m1 = opt_u64("--m1", 0), m2 = opt_u64("--m2", 0);
        if (m1 == 0 || m2 == 0) die("--m1 and --m2 are required");
        if (ca_gcd(m1, m2) != 1) die("moduli must be coprime");
        /* The combined modulus is what the result is reduced against, so a
         * product that wraps would print a modulus the answer is not taken
         * modulo.  Refuse rather than report a smaller one. */
        if (m1 > UINT64_MAX / m2) die("--m1 * --m2 overflows 64 bits");
        printf("{\"result\":\"%" PRIu64 "\",\"modulus\":\"%" PRIu64 "\"}\n",
               ca_crt2(opt_u64("--r1", 0), m1, opt_u64("--r2", 0), m2), m1 * m2);
        return 0;
    }
    if (!strcmp(op, "next-prime")) {
        uint64_t q = ca_next_prime(opt_u64("--n", 0));
        if (q == 0) {
            printf("{\"found\":false}\n");
            return 1;
        }
        printf("{\"found\":true,\"result\":\"%" PRIu64 "\"}\n", q);
        return 0;
    }
    if (!strcmp(op, "order")) {
        uint64_t p = opt_u64("--p", 0);
        if (p < 2) die("--p must be a prime at least 2");
        uint64_t o = ca_mult_order(opt_u64("--a", 0), p);
        if (o == 0) {
            printf("{\"defined\":false}\n");
            return 1;
        }
        printf("{\"defined\":true,\"order\":\"%" PRIu64 "\"}\n", o);
        return 0;
    }
    if (!strcmp(op, "primitive-root")) {
        uint64_t p = opt_u64("--p", 0);
        if (p < 2) die("--p must be a prime at least 2");
        uint64_t g = ca_primitive_root(p);
        if (g == 0) {
            printf("{\"found\":false}\n");
            return 1;
        }
        printf("{\"found\":true,\"generator\":\"%" PRIu64 "\",\"order\":\"%" PRIu64 "\"}\n", g,
               p - 1);
        return 0;
    }
    if (!strcmp(op, "sieve")) {
        uint64_t bound = opt_u64("--bound", 100);
        /* The table is sized from the bound, so an absurd bound becomes an
         * absurd allocation.  Refusing with a message beats a failing calloc. */
        if (bound > (1ULL << 32)) die("--bound above 2^32 needs a segmented sieve");
        /* pi(x) < 1.3 x / ln x for x >= 17, and the +16 covers the small cases
         * where that bound has not kicked in yet. */
        size_t cap = (size_t)(bound / 2) + 16;
        uint32_t *primes = calloc(cap, sizeof *primes);
        if (!primes) die("out of memory");
        size_t n = ca_sieve_primes(bound, primes, cap);
        printf("{\"bound\":\"%" PRIu64 "\",\"count\":%zu", bound, n);
        if (n) printf(",\"first\":%" PRIu32 ",\"last\":%" PRIu32, primes[0], primes[n - 1]);
        printf("}\n");
        free(primes);
        return 0;
    }
    if (!strcmp(op, "mont")) {
        /* Check the modulus here rather than leaning on ca_mont_init's return.
         * It does reject p < 3 and even p, but that is in another translation
         * unit, so nothing at this call site proves p != 0 before the reductions
         * below -- and clang-analyzer is right to say so.  Every other command
         * in this file states its own modulus contract; this one now does too. */
        uint64_t p = opt_u64("--p", 0);
        if (p < 3 || p % 2 == 0) die("--p must be odd and at least 3");
        ca_mont m;
        if (!ca_mont_init(&m, p)) die("ca_mont_init rejected the modulus");
        uint64_t a = opt_u64("--a", 0) % p, b = opt_u64("--b", 0) % p;
        uint64_t am = ca_mont_to(&m, a), bm = ca_mont_to(&m, b);
        uint64_t prod = ca_mont_from(&m, ca_mont_mul(&m, am, bm));
        uint64_t sq = ca_mont_from(&m, ca_mont_sqr(&m, am));
        uint64_t pw = ca_mont_from(&m, ca_mont_pow(&m, am, b));
        uint64_t iv = a ? ca_mont_from(&m, ca_mont_inv(&m, am)) : 0;
        /* Print the schoolbook answers alongside, so the command doubles as a
         * self-check of the Montgomery domain rather than only a calculator. */
        printf("{\"product\":\"%" PRIu64 "\",\"product_ref\":\"%" PRIu64 "\","
               "\"square\":\"%" PRIu64 "\",\"square_ref\":\"%" PRIu64 "\","
               "\"power\":\"%" PRIu64 "\",\"power_ref\":\"%" PRIu64 "\","
               "\"inverse\":\"%" PRIu64 "\",\"agree\":%s}\n",
               prod, ca_mulmod(a, b, p), sq, ca_mulmod(a, a, p), pw, ca_powmod(a, b, p), iv,
               (prod == ca_mulmod(a, b, p) && sq == ca_mulmod(a, a, p) &&
                pw == ca_powmod(a, b, p) && (!a || ca_mulmod(a, iv, p) == 1 % p))
                   ? "true"
                   : "false");
        return 0;
    }
    die("unknown num operation");
}

/* -------------------------------------------------------------- group ----
 * The group abstraction itself: scalar multiples, division, element order,
 * generator search, and the EC-specific x-coordinate lift.  `gen` and `solve`
 * use these internally; exposing them lets a user check a group by hand
 * before trusting a discrete-log run on it.
 */
static int cmd_group(void)
{
    const char *op = sub();
    if (!op) die("group needs an operation");
    ca_group g;
    make_group(&g);

    if (!strcmp(op, "exp")) {
        ca_elem x, r;
        parse_elem(&g, opt("--elem"), &x);
        ca_group_mul(&g, &r, &x, opt_u64("--k", 1), NULL);
        printf("{\"result\":");
        print_elem(&g, &r);
        printf("}\n");
        return 0;
    }
    if (!strcmp(op, "div")) {
        ca_elem a, b, r;
        parse_elem(&g, opt("--a"), &a);
        parse_elem(&g, opt("--b"), &b);
        ca_group_div(&g, &r, &a, &b);
        printf("{\"result\":");
        print_elem(&g, &r);
        printf("}\n");
        return 0;
    }
    if (!strcmp(op, "order")) {
        ca_elem x;
        parse_elem(&g, opt("--elem"), &x);
        uint64_t o = ca_group_elem_order(&g, &x);
        printf("{\"order\":\"%" PRIu64 "\",\"divides_group_order\":%s}\n", o,
               (o && g.order && g.order % o == 0) ? "true" : "false");
        return o ? 0 : 1;
    }
    if (!strcmp(op, "generator")) {
        ca_elem gen;
        ca_status rc = ca_group_find_generator(&g, &gen, opt_u64("--seed", 0));
        if (rc != CA_OK) die_status(rc);
        printf("{\"generator\":");
        print_elem(&g, &gen);
        printf(",\"order\":\"%" PRIu64 "\"}\n", ca_group_elem_order(&g, &gen));
        return 0;
    }
    if (!strcmp(op, "random")) {
        ca_elem gen, r;
        ca_status rc = ca_group_find_generator(&g, &gen, opt_u64("--seed", 0));
        if (rc != CA_OK) die_status(rc);
        uint64_t k = 0;
        ca_group_random_power(&g, &r, &gen, opt_u64("--seed", 0) ^ 0x9e3779b9u, &k);
        printf("{\"element\":");
        print_elem(&g, &r);
        printf(",\"exponent\":\"%" PRIu64 "\"}\n", k);
        return 0;
    }
    if (!strcmp(op, "lift-x")) {
        if (g.kind != CA_GROUP_EC) die("lift-x needs --group ec");
        ca_elem r;
        if (!ca_ec_lift_x(&g, &r, opt_u64("--x", 0))) {
            printf("{\"on_curve\":false}\n");
            return 1;
        }
        printf("{\"on_curve\":true,\"point\":");
        print_elem(&g, &r);
        printf("}\n");
        return 0;
    }
    die("unknown group operation");
}

/* ----------------------------------------------------------- dist-info ----
 * The campaign's identity and its expected cost, without doing any work.  A
 * distributed run that gets this wrong wastes every worker's time, so it is
 * worth being able to print it.
 */
static int cmd_dist_info(void)
{
    ca_group g;
    make_group(&g);
    ca_elem base, target;
    parse_elem(&g, opt("--g"), &base);
    parse_elem(&g, opt("--h"), &target);
    ca_dist_campaign c;
    make_campaign(&g, &c);
    printf("{\"campaign_id\":\"%" PRIu64 "\",\"dp_bits\":%" PRId32 ",\"r\":%" PRIu32
           ",\"expected_points\":%.3f}\n",
           ca_dist_campaign_id(&g, &base, &target, &c), c.dp_bits, c.r,
           ca_dist_expected_points(&g, &c));
    return 0;
}

/* ------------------------------------------------------------- curve ----
 * Curve-aware dispatch: report the endomorphism structure of a curve (given
 * by --name from the registry or by explicit parameters) and the solver the
 * library would pick for it.
 */
static int cmd_curve(void)
{
    if (flag("--list")) {
        const char *names[32];
        size_t n = ca_curve_list(names, 32);
        printf("{\"curves\":[");
        for (size_t i = 0; i < n && i < 32; i++) printf("%s\"%s\"", i ? "," : "", names[i]);
        printf("]}\n");
        return 0;
    }
    uint64_t p = 0, a = 0, b = 0, order = 0;
    const char *name = opt("--name");
    if (name) {
        ca_status rc = ca_curve_by_name(name, &p, &a, &b, &order);
        if (rc != CA_OK) die_status(rc);
    } else {
        p = opt_u64("--p", 0);
        a = opt_u64("--a", 0);
        b = opt_u64("--b", 0);
        order = opt_u64("--order", 0);
        if (!p) die("curve needs --name or --p [--a --b --order]");
    }
    ca_curve_info info;
    ca_status rc = ca_curve_detect(p, a, b, order, &info);
    if (rc != CA_OK) die_status(rc);
    const char *ek = info.endo == CA_CURVE_ENDO_J0      ? "j0"
                     : info.endo == CA_CURVE_ENDO_J1728 ? "j1728"
                                                        : "none";
    printf("{\"status\":\"ok\",\"p\":%" PRIu64 ",\"a\":%" PRIu64 ",\"b\":%" PRIu64
           ",\"order\":%" PRIu64 ",\"endomorphism\":\"%s\",\"aut_order\":%u,\"beta\":%" PRIu64
           ",\"lambda\":%" PRIu64 ",\"rho_speedup\":%.4f,\"solver\":\"%s\"}\n",
           p, a, b, order, ek, info.aut_order, info.beta, info.lambda, info.rho_speedup,
           info.endo != CA_CURVE_ENDO_NONE ? "glv-rho" : "rho");
    return 0;
}

int main(int argc, char **argv)
{
    argc_g = argc;
    argv_g = argv;
    if (argc < 2) usage();
    const char *cmd = argv[1];
    if (!strcmp(cmd, "version")) {
        printf("{\"version\":\"%s\"}\n", ca_version());
        return 0;
    }
    if (!strcmp(cmd, "factor")) {
        if (argc < 3) usage();
        uint64_t n = strtoull(argv[2], NULL, 0);
        ca_factorization f;
        if (ca_factorize(n, &f) != CA_OK) die("cannot factor 0");
        printf("{\"n\":%" PRIu64 ",\"factors\":[", n);
        for (unsigned i = 0; i < f.count; i++)
            printf("%s[%" PRIu64 ",%u]", i ? "," : "", f.f[i].p, f.f[i].e);
        printf("]}\n");
        return 0;
    }
    if (!strcmp(cmd, "prime")) {
        if (argc < 3) usage();
        uint64_t n = strtoull(argv[2], NULL, 0);
        printf("{\"n\":%" PRIu64 ",\"is_prime\":%s,\"next_prime\":%" PRIu64 "}\n", n,
               ca_is_prime(n) ? "true" : "false", ca_next_prime(n));
        return 0;
    }
    if (!strcmp(cmd, "ec-order")) {
        uint64_t p = opt_u64("--p", 0), n;
        if (!p) die("--p required");
        ca_stats st = {0};
        ca_status rc = ca_ec_count_points(p, opt_u64("--a", 0), opt_u64("--b", 0), &n, &st);
        if (rc != CA_OK) die_status(rc);
        ca_factorization f;
        ca_factorize(n, &f);
        printf("{\"status\":\"ok\",\"p\":%" PRIu64 ",\"order\":%" PRIu64 ",\"factors\":[", p, n);
        for (unsigned i = 0; i < f.count; i++)
            printf("%s[%" PRIu64 ",%u]", i ? "," : "", f.f[i].p, f.f[i].e);
        printf("],\"ops\":%" PRIu64 ",\"seconds\":%.6f}\n", st.group_ops, st.seconds);
        return 0;
    }
    if (!strcmp(cmd, "gpu-info")) {
        int n = ca_gpu_device_count();
        printf("{\"cuda_compiled\":%s,\"devices\":%d,\"walks_per_thread\":%d,\"names\":[",
               ca_gpu_cuda_compiled() ? "true" : "false", n, CA_GPU_W);
        for (int i = 0; i < n; i++) {
            char name[256] = "";
            if (ca_gpu_device_name(i, name, sizeof(name)) != 0)
                snprintf(name, sizeof(name), "unknown");
            printf("%s\"%s\"", i ? "," : "", name);
        }
        printf("]}\n");
        return 0;
    }
    if (!strcmp(cmd, "gen")) return cmd_gen();
    if (!strcmp(cmd, "solve")) return cmd_solve();
    if (!strcmp(cmd, "cheon")) return cmd_cheon();
    if (!strcmp(cmd, "ic")) return cmd_ic();
    if (!strcmp(cmd, "dist-walk")) return cmd_dist_walk();
    if (!strcmp(cmd, "dist-merge")) return cmd_dist_merge();
    if (!strcmp(cmd, "dist-info")) return cmd_dist_info();
    if (!strcmp(cmd, "num")) return cmd_num();
    if (!strcmp(cmd, "group")) return cmd_group();
    if (!strcmp(cmd, "curve")) return cmd_curve();
    usage();
    return 2;
}
