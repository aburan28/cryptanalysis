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
 *   ca coord-job  --group zp|ec --p P [--a A --b B] --order N --g G --h H
 *                 [--dp-bits D] [--r R] [--negation] [--unit-size U] [--seed S]
 *                 [--out FILE]
 *   ca work       [--job FILE] [--coordinator URL] [--token T | --token-file F]
 *                 [--node NAME] [--threads T] [--max-seconds S] [--max-walkers W]
 *                 [--checkin-every N] [--lease-secs S] [--idle-when-solved]
 *   ca coord-status [--coordinator URL] [--token T | --token-file F]
 *
 * The distributed commands: `coord-job` writes the document every
 * participant shares and `work` is an agent that dials out to a
 * coordinator and needs no inbound reachability of its own.
 * --coordinator and --token fall back to $CA_COORDINATOR_URL and
 * $CA_COORDINATOR_TOKEN.
 *
 * The coordinator itself is a separate service, in Go:
 * bindings/go/cmd/ca-coordinator (Helm chart in deploy/helm).
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
#include "ca_device.cuh"
#include "ca_internal.h" /* ca_now: the CLI already links the static library */

#include <fcntl.h>
#include <pthread.h>
#include <signal.h>
#include <time.h>
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
        "  solve --alg bsgs|rho|kangaroo|grumpy|dlog|gpu-rho --group zp|ec --p P [--a A --b B]\n"
        "        --order N --g G --h H [--lo L --hi U] [--threads T] [--seed S] ...\n"
        "  cheon --group zp|ec --p P [--a A --b B] --order Q --g G --d D (--ga GA --gad GAD | "
        "--alpha X)\n"
        "  ic    --p P --g G --h H [--method lsieve|rexp] [--B B] [--C C] [--threads T] "
        "[--verbose]\n"
        "  num   powmod|invmod|gcd|isqrt|iroot|sqrtmod|legendre|crt|next-prime|order|\n"
        "        primitive-root|sieve|mont  (see the header comment for each op's options)\n"
        "  group exp|div|order|generator|random|lift-x --group zp|ec --p P [--a A --b B] ...\n"
        "  coord-job --group zp|ec --p P --order N --g G --h H [--dp-bits D] [--r R]\n"
        "            [--negation] [--unit-size U] [--seed S] [--out FILE]\n"
        "  work      [--coordinator URL] [--token-file F] [--node NAME] [--threads T]\n"
        "            [--max-seconds S] [--max-walkers W] [--checkin-every N]\n"
        "            [--lease-secs S] [--idle-when-solved]\n"
        "  coord-status [--coordinator URL] [--token-file F]\n");
    exit(2);
}

static void make_group(ca_group *g)
{
    const char *kind = opt("--group");
    uint64_t p = opt_u64("--p", 0);
    uint64_t order = opt_u64("--order", 0);
    if (!kind || !p) die("--group and --p are required");
    ca_status rc;
    if (strcmp(kind, "zp") == 0)
        rc = ca_group_zp_init(g, p, order);
    else if (strcmp(kind, "ec") == 0)
        rc = ca_group_ec_init(g, p, opt_u64("--a", 0), opt_u64("--b", 0), order);
    else
        die("--group must be zp or ec");
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
    if (g->kind == CA_GROUP_ZP)
        printf("\"%" PRIu64 "\"", w[0]);
    else if (w[2])
        printf("\"inf\"");
    else
        printf("\"%" PRIu64 ",%" PRIu64 "\"", w[0], w[1]);
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
    if (!opt("--x"))
        ca_group_random_power(&g, &h, &gen, seed ? seed + 1 : 0, &x);
    else
        ca_group_mul(&g, &h, &gen, x, NULL);
    printf("{\"status\":\"ok\",\"group\":\"%s\",\"p\":%" PRIu64 ",",
           g.kind == CA_GROUP_ZP ? "zp" : "ec", g.p);
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
    dp.rho.max_ops = dp.bsgs.max_ops = dp.kangaroo.max_ops = dp.grumpy.max_ops =
        opt_u64("--max-ops", 0);
    dp.bsgs.table_size = opt_u64("--table", 0);
    dp.kangaroo.dp_bits = (int32_t)opt_u64("--dp-bits", (uint64_t)-1);
    dp.kangaroo.herd_size = (uint32_t)opt_u64("--herd", 0);
    dp.grumpy.m = opt_u64("--m", 0);
    dp.grumpy.alpha = opt_f("--alpha", 0.7);
    const char *solver = opt("--solver");
    if (solver) {
        if (!strcmp(solver, "auto"))
            dp.solver = CA_SOLVER_AUTO;
        else if (!strcmp(solver, "bsgs"))
            dp.solver = CA_SOLVER_BSGS;
        else if (!strcmp(solver, "rho"))
            dp.solver = CA_SOLVER_RHO;
        else if (!strcmp(solver, "kangaroo"))
            dp.solver = CA_SOLVER_KANGAROO;
        else if (!strcmp(solver, "grumpy"))
            dp.solver = CA_SOLVER_GRUMPY;
        else
            die("unknown --solver");
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
    if (!strcmp(alg, "bsgs"))
        rc = ca_bsgs_solve(&g, &base, &target, lo, hi, &dp.bsgs, &x, &st);
    else if (!strcmp(alg, "rho"))
        rc = ca_rho_solve(&g, &base, &target, &dp.rho, &x, &st);
    else if (!strcmp(alg, "kangaroo"))
        rc = ca_kangaroo_solve(&g, &base, &target, lo, hi, &dp.kangaroo, &x, &st);
    else if (!strcmp(alg, "grumpy"))
        rc = ca_grumpy_solve(&g, &base, &target, lo, hi, &dp.grumpy, &x, &st);
    else if (!strcmp(alg, "dlog"))
        rc = ca_pohlig_hellman(&g, &base, &target, &dp, &x, &st);
    else
        die("unknown --alg");
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
    printf("{\"status\":\"ok\",\"alpha\":%" PRIu64 ",\"d\":%" PRIu64 ",\"exponentiations\":%" PRIu64
           ",",
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
    printf("{\"status\":\"ok\",\"x\":%" PRIu64 ",\"check\":%" PRIu64
           ",\"factor_base\":%u,\"unknowns\":%u,"
           "\"relations\":%u,\"verified_logs\":%u,\"sieve_seconds\":%.3f,\"linalg_seconds\":%.3f,"
           "\"total_seconds\":%.3f,\"lanczos_iterations\":%u,\"threads\":%u}\n",
           x, ca_powmod(gg, x, p), st.factor_base_size, st.unknowns, st.relations, st.verified_logs,
           st.sieve_seconds, st.linalg_seconds, st.total_seconds, st.lanczos_iterations,
           st.threads);
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
        uint64_t p = opt_u64("--p", 0);
        ca_mont m;
        /* ca_mont_init already rejects an even or too-small modulus, but the
         * reductions below divide by p and a static analyser cannot see that
         * through the call, so the bound is stated here too. */
        if (p < 3 || !(p & 1)) die("--p must be odd and at least 3");
        if (!ca_mont_init(&m, p)) die("--p must be odd and at least 3");
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

/* ---- distributed rho ------------------------------------------------------
 *
 * Three processes and one URL: `coord-job` writes what everyone agrees
 * on, `coord` is the hub on the reachable host, `work` is an agent
 * anywhere.  The agent opens the connection and the hub answers on it,
 * so an agent behind NAT needs no address of its own.
 */

/* The token: --token, then --token-file, then the environment.  A
 * command line is world-readable on a shared box, so the file and the
 * environment are the ones a deployment should use. */
static const char *coord_token(void)
{
    const char *t = opt("--token");
    if (t) return t;
    const char *path = opt("--token-file");
    if (path) {
        static char buf[256];
        FILE *f = fopen(path, "r");
        if (!f) die("cannot read --token-file");
        const char *got = fgets(buf, sizeof(buf), f);
        fclose(f);
        if (!got) die("--token-file is empty");
        buf[strcspn(buf, "\r\n")] = 0;
        if (!buf[0]) die("--token-file is empty");
        return buf;
    }
    const char *env = getenv(CA_COORD_TOKEN_ENV);
    return env && *env ? env : NULL;
}

static const char *coord_url(void)
{
    const char *u = opt("--coordinator");
    if (u) return u;
    const char *env = getenv(CA_COORD_URL_ENV);
    return env && *env ? env : NULL;
}

static void coord_print_job(const ca_coord_job *job, const ca_coord_ctx *ctx, const char *out)
{
    printf("{\"status\":\"ok\",\"job_id\":\"%016" PRIx64 "\",\"order\":%" PRIu64
           ",\"dp_bits\":%d,\"r\":%u,\"negation\":%d,\"unit_size\":%" PRIu64
           ",\"expected_steps\":%.6e,\"expected_dps\":%.6e",
           job->id, job->order, (int)job->dp_bits, job->r, (int)job->negation_map, job->unit_size,
           ca_coord_expected_steps(ctx), ca_coord_expected_dps(ctx));
    if (out) printf(",\"written\":\"%s\"", out);
    printf("}\n");
}

static int cmd_coord_job(void)
{
    ca_group g;
    make_group(&g);
    ca_elem base, target;
    parse_elem(&g, opt("--g"), &base);
    parse_elem(&g, opt("--h"), &target);

    ca_coord_job job;
    ca_status rc = ca_coord_job_init(
        &job, &g, &base, &target,
        (int32_t)opt_u64("--dp-bits", (uint64_t)-1) == -1 ? -1 : (int32_t)opt_u64("--dp-bits", 0),
        (uint32_t)opt_u64("--r", 0), flag("--negation"), opt_u64("--unit-size", 0),
        opt_u64("--seed", 0));
    if (rc != CA_OK) die_status(rc);
    ca_coord_ctx *ctx = NULL;
    rc = ca_coord_ctx_open(&ctx, &job);
    if (rc != CA_OK) die_status(rc);

    char line[CA_COORD_LINE_MAX];
    if (!ca_coord_job_encode(&job, line, sizeof(line))) die("job does not encode");
    const char *out = opt("--out");
    if (out) {
        /* Created with an explicit mode rather than through fopen, whose
         * 0666-and-umask depends on the caller's environment.  The job
         * document is public -- it is what every participant is handed --
         * but a file this program creates should still say what it means. */
        int fd = open(out, O_WRONLY | O_CREAT | O_TRUNC, S_IRUSR | S_IWUSR | S_IRGRP | S_IROTH);
        if (fd < 0) die("cannot write --out");
        FILE *f = fdopen(fd, "w");
        if (!f) {
            close(fd);
            die("cannot write --out");
        }
        fprintf(f, "%s\n", line);
        fclose(f);
    } else {
        fprintf(stderr, "%s\n", line);
    }
    coord_print_job(&job, ctx, out);
    ca_coord_ctx_close(ctx);
    return 0;
}

/* Load the job: from --job, or from the hub named by --coordinator.  An
 * agent given a URL needs nothing on disk. */
static ca_coord_ctx *coord_load(int allow_remote)
{
    ca_coord_job job;
    const char *path = opt("--job");
    if (path) {
        FILE *f = fopen(path, "r");
        if (!f) die("cannot read --job");
        char line[CA_COORD_LINE_MAX];
        const char *got = fgets(line, sizeof(line), f);
        fclose(f);
        if (!got) die("--job is empty");
        line[strcspn(line, "\r\n")] = 0;
        ca_status rc = ca_coord_job_decode(&job, line);
        if (rc != CA_OK) die_status(rc);
    } else if (allow_remote && coord_url()) {
        ca_status rc = ca_coord_fetch_job(coord_url(), coord_token(), &job);
        if (rc != CA_OK) die_status(rc);
    } else {
        die("pass --job FILE (or --coordinator URL to fetch it)");
    }
    ca_coord_ctx *ctx = NULL;
    ca_status rc = ca_coord_ctx_open(&ctx, &job);
    if (rc != CA_OK) die_status(rc);
    return ctx;
}

/* Interrupt handling, shared by `work` (the agent) and anything else
 * that runs until told to stop. */
static volatile sig_atomic_t coord_interrupted;
static void coord_on_signal(int sig)
{
    (void)sig;
    coord_interrupted = 1;
}

/* One worker lane in its own thread. */
typedef struct work_lane {
    pthread_t thread;
    const ca_coord_ctx *ctx;
    ca_coord_state *st;
    ca_coord_agent *agent;
    char peer[CA_COORD_PEER_MAX];
    uint64_t max_walkers;
    uint64_t checkin_every;
    uint64_t lease_secs;
    ca_coord_lane_result res;
} work_lane;

static volatile sig_atomic_t work_stop;

static void work_publish(void *user, const ca_coord_checkin *ci)
{
    if (user) ca_coord_agent_publish((ca_coord_agent *)user, ci);
}

static int work_should_stop(void *user)
{
    (void)user;
    return work_stop;
}

static void *work_lane_main(void *arg)
{
    work_lane *w = arg;
    ca_coord_lane_params p;
    ca_coord_lane_params_default(&p, w->peer);
    p.max_walkers = w->max_walkers;
    if (w->checkin_every) p.checkin_every = w->checkin_every;
    if (w->lease_secs) p.lease_secs = w->lease_secs;
    ca_coord_lane_run(w->ctx, w->st, &p, w->agent ? work_publish : NULL, w->agent, work_should_stop,
                      NULL, &w->res);
    return NULL;
}

static int cmd_work(void)
{
    ca_coord_ctx *ctx = coord_load(1);
    ca_coord_state *st = NULL;
    if (ca_coord_state_init(&st, ctx) != CA_OK) die("out of memory");

    const char *node = opt("--node");
    if (!node) node = "node";
    uint64_t threads = opt_u64("--threads", 1);
    if (threads < 1) threads = 1;
    if (threads > 256) threads = 256;
    uint64_t max_seconds = opt_u64("--max-seconds", 0);
    uint64_t max_walkers = opt_u64("--max-walkers", 0);
    /* An agent normally exits once the instance is solved.  Under a
     * process supervisor that restarts it -- systemd, a Kubernetes
     * Deployment -- exiting is a restart loop: it comes back, is pushed
     * the answer it already had, and exits again.  With this flag it
     * stays up instead, holding its channel, until it is told to stop. */
    int idle_when_solved = flag("--idle-when-solved");
    /* Walkers between check-ins: how much work is at risk if this pod
     * dies, and how promptly the fleet sees what it found. */
    uint64_t checkin_every = opt_u64("--checkin-every", 0);
    /* How long this lane's claim stays live without a fresh check-in. */
    uint64_t lease_secs = opt_u64("--lease-secs", 0);

    /* The reverse channel.  Started before the lanes, so the first
     * check-in already has somewhere to go; it connects in the
     * background, so an unreachable hub delays no walking. */
    ca_coord_agent *agent = NULL;
    if (coord_url()) {
        ca_status rc = ca_coord_agent_start(&agent, coord_url(), coord_token(), node, ctx, st);
        if (rc != CA_OK) die_status(rc);
        fprintf(stderr, "[agent] dialling %s as %s%s\n", coord_url(), node,
                coord_token() ? "" : " (no token)");
    } else {
        fprintf(stderr, "[agent] no --coordinator: walking alone\n");
    }

    signal(SIGINT, coord_on_signal);
    signal(SIGTERM, coord_on_signal);
    work_lane *lanes = calloc(threads, sizeof(*lanes));
    if (!lanes) die("out of memory");
    for (uint64_t i = 0; i < threads; i++) {
        lanes[i].ctx = ctx;
        lanes[i].st = st;
        lanes[i].agent = agent;
        lanes[i].max_walkers = max_walkers;
        lanes[i].checkin_every = checkin_every;
        lanes[i].lease_secs = lease_secs;
        snprintf(lanes[i].peer, sizeof(lanes[i].peer), "%s.%" PRIu64, node, i);
        if (pthread_create(&lanes[i].thread, NULL, work_lane_main, &lanes[i]) != 0)
            die("cannot start a lane");
    }

    double start = ca_now();
    for (;;) {
        struct timespec ts = {0, 200 * 1000000L};
        nanosleep(&ts, NULL);
        if (coord_interrupted) work_stop = 1;
        if (max_seconds && ca_now() - start >= (double)max_seconds) work_stop = 1;
        if (ca_coord_solution(st, NULL)) work_stop = 1;
        if (work_stop) break;
    }
    work_stop = 1;
    for (uint64_t i = 0; i < threads; i++) pthread_join(lanes[i].thread, NULL);
    if (idle_when_solved && !coord_interrupted && ca_coord_solution(st, NULL)) {
        fprintf(stderr, "[agent] solved; idling (--idle-when-solved) until stopped\n");
        while (!coord_interrupted) {
            struct timespec ts = {1, 0};
            nanosleep(&ts, NULL);
        }
    }

    /* Drain before exiting: the queue lives in this process, and the
     * last check-in is the one carrying the solution. */
    int flushed = 1;
    if (agent) flushed = ca_coord_agent_flush(agent, 10000);

    uint64_t steps = 0, dps = 0, walkers = 0;
    for (uint64_t i = 0; i < threads; i++) {
        steps += lanes[i].res.steps;
        dps += lanes[i].res.dps;
        walkers += lanes[i].res.walkers;
    }
    uint64_t x = 0;
    int have = ca_coord_solution(st, &x);
    ca_coord_agent_stats as;
    memset(&as, 0, sizeof(as));
    if (agent) ca_coord_agent_stats_get(agent, &as);
    printf("{\"status\":\"ok\",\"solved\":%s,\"x\":%" PRIu64 ",\"node\":\"%s\",\"lanes\":%" PRIu64
           ",\"walkers\":%" PRIu64 ",\"steps\":%" PRIu64 ",\"dps\":%" PRIu64
           ",\"seconds\":%.3f,\"received\":%" PRIu64 ",\"sent\":%" PRIu64 ",\"connects\":%" PRIu64
           ",\"flushed\":%s}\n",
           have ? "true" : "false", x, node, threads, walkers, steps, dps, ca_now() - start,
           as.received, as.sent, as.connects, flushed ? "true" : "false");
    if (agent) ca_coord_agent_stop(agent);
    free(lanes);
    ca_coord_state_free(st);
    ca_coord_ctx_close(ctx);
    return have ? 0 : 3;
}

static int cmd_coord_status(void)
{
    if (!coord_url()) die("pass --coordinator URL (or set " CA_COORD_URL_ENV ")");
    ca_coord_ctx *ctx = coord_load(1);
    ca_coord_state *st = NULL;
    if (ca_coord_state_init(&st, ctx) != CA_OK) die("out of memory");
    uint64_t received = 0, rejected = 0;
    ca_status rc = ca_coord_sync_once(coord_url(), coord_token(), ctx, st, &received, &rejected);
    if (rc != CA_OK) die_status(rc);
    ca_coord_progress pr;
    ca_coord_progress_get(st, ctx, (uint64_t)time(NULL), opt_u64("--lease-secs", 120), &pr);
    printf("{\"status\":\"ok\",\"job_id\":\"%016" PRIx64 "\",\"steps\":%" PRIu64
           ",\"fraction\":%.6f,\"dps\":%" PRIu64 ",\"units_completed\":%" PRIu64
           ",\"units_active\":%" PRIu64 ",\"peers\":%" PRIu64 ",\"checkins\":%" PRIu64
           ",\"rejected_dps\":%" PRIu64 ",\"solved\":%s,\"x\":%" PRIu64 "}\n",
           ca_coord_ctx_job(ctx)->id, pr.steps, pr.fraction, pr.dps_stored, pr.units_completed,
           pr.units_active, pr.peers, pr.checkins, pr.rejected_dps,
           pr.have_solution ? "true" : "false", pr.solution);
    ca_coord_state_free(st);
    ca_coord_ctx_close(ctx);
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
    if (!strcmp(cmd, "coord-job")) return cmd_coord_job();
    if (!strcmp(cmd, "work")) return cmd_work();
    if (!strcmp(cmd, "coord-status")) return cmd_coord_status();
    if (!strcmp(cmd, "num")) return cmd_num();
    if (!strcmp(cmd, "group")) return cmd_group();
    usage();
    return 2;
}
