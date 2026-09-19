/*
 * ca_cli.c - command line front end for libcryptanalysis.
 *
 *   ca version
 *   ca factor N
 *   ca prime N
 *   ca ec-order --p P --a A --b B
 *   ca gen   --group zp|ec --p P [--a A --b B] [--order N] [--x X] [--seed S]
 *   ca gpu-info
 *   ca solve --alg bsgs|rho|kangaroo|grumpy|dlog|gpu-rho --group zp|ec --p P [--a A --b B]
 *            --order N --g G --h H [--lo L --hi U] [--threads T] [--seed S]
 *            [--dp-bits D] [--r R] [--walks W] [--no-negation] [--m M] [--alpha F]
 *            [--solver auto|bsgs|rho|kangaroo|grumpy] [--max-ops K]
 *            gpu-rho also takes [--backend auto|cuda|emulate] [--device D]
 *            [--tpb T] [--blocks B] [--steps S]
 *   ca cheon --group zp|ec --p P [--a A --b B] --order Q --g G --d D
 *            (--ga GA --gad GAD | --alpha X)
 *   ca ic    --p P --g G --h H [--method lsieve|rexp] [--B B] [--C C]
 *            [--threads T] [--seed S] [--verbose]
 *   ca dist-walk  --group ... --order N --g G --h H --campaign-seed S --unit U
 *            --steps K [--dp-bits D] [--r R] [--walks W] [--max-points P]
 *            [--out FILE]            one work unit; 32-byte records to FILE
 *   ca dist-merge --group ... --order N --g G --h H --campaign-seed S
 *            [--dp-bits D] [--r R] [--no-verify] FILE...   (- reads stdin)
 *
 * Elements: Z_p^* "123"; E(F_p) "x,y" or "inf".  Output is one JSON object
 * on stdout; errors go to stderr with a non-zero exit status.
 */
#include "cryptanalysis/cryptanalysis.h"
#include "cryptanalysis/ca_dist.h"
#include "ca_device.cuh"

#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

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
        "  solve --alg bsgs|rho|kangaroo|grumpy|dlog|gpu-rho --group zp|ec --p P [--a A --b B]\n"
        "        --order N --g G --h H [--lo L --hi U] [--threads T] [--seed S] ...\n"
        "  cheon --group zp|ec --p P [--a A --b B] --order Q --g G --d D (--ga GA --gad GAD | "
        "--alpha X)\n"
        "  ic    --p P --g G --h H [--method lsieve|rexp] [--B B] [--C C] [--threads T] "
        "[--verbose]\n"
        "  dist-walk  --group ... --order N --g G --h H --campaign-seed S --unit U --steps K\n"
        "             [--dp-bits D] [--r R] [--walks W] [--max-points P] [--out FILE]\n"
        "  dist-merge --group ... --order N --g G --h H --campaign-seed S [--dp-bits D]\n"
        "             [--r R] [--no-verify] FILE...\n");
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
        sink.out = fopen(path, "wb");
        if (!sink.out) die("cannot open --out for writing");
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
    FILE *report = path ? stdout : stderr;   /* records own stdout when there is no --out */
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
    FILE *in = strcmp(path, "-") == 0 ? stdin : fopen(path, "rb");
    if (!in) return -1;
    /* A partial record at the end of a file is a truncated upload, which is
     * what a killed agent leaves behind.  Read whole records and report the
     * remainder rather than guessing at it. */
    unsigned char buf[CA_DIST_POINT_BYTES * 256];
    ca_dist_point pts[256];
    size_t carry = 0;
    int rc = 0;
    for (;;) {
        size_t got = fread(buf + carry, 1, sizeof(buf) - carry, in);
        if (got == 0) break;
        size_t have = carry + got;
        size_t whole = have / CA_DIST_POINT_BYTES;
        for (size_t i = 0; i < whole; i++)
            ca_dist_point_decode(&pts[i], buf + i * CA_DIST_POINT_BYTES);
        size_t a = 0, d = 0, r = 0;
        if (ca_dist_merger_add(m, pts, whole, &a, &d, &r) != CA_OK) { rc = -2; break; }
        *acc += a; *dup += d; *rej += r;
        carry = have - whole * CA_DIST_POINT_BYTES;
        memmove(buf, buf + whole * CA_DIST_POINT_BYTES, carry);
    }
    if (carry) rc = 1;      /* truncated tail */
    if (in != stdin) fclose(in);
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
        if (a[0] == '-' && a[1] == '-') { i++; continue; }   /* skip option pairs */
        if (a[0] == '-' && a[1] != '\0' && strcmp(a, "-") != 0) continue;
        files++;
        int r = merge_file(m, a, &acc, &dup, &rej);
        if (r == -1) { ca_dist_merger_free(m); die("cannot open input file"); }
        if (r == -2) { ca_dist_merger_free(m); die_status(CA_ERR_NOMEM); }
        if (r == 1) truncated++;
    }
    if (!files) { ca_dist_merger_free(m); die("no input files (use - for stdin)"); }

    uint64_t x = 0;
    int solved = ca_dist_merger_solved(m, &x);
    printf("{\"status\":\"ok\",\"campaign\":%" PRIu64 ",\"files\":%d,\"accepted\":%" PRIu64
           ",\"duplicates\":%" PRIu64 ",\"rejected\":%" PRIu64 ",\"stored\":%zu,\"truncated\":%d,"
           "\"solved\":%s", ca_dist_campaign_id(&g, &base, &target, &c), files, acc, dup, rej,
           ca_dist_merger_size(m), truncated, solved ? "true" : "false");
    if (solved) printf(",\"x\":%" PRIu64, x);
    printf("}\n");
    ca_dist_merger_free(m);
    /* Exit 0 whether or not it solved: "no collision yet" is the normal
     * state of a campaign, and a scheduler that read it as failure would
     * retry the whole corpus every pass. */
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
    usage();
    return 2;
}
