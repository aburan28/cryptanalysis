/*
 * ca_cli.c - command line front end for libcryptanalysis.
 *
 *   ca version
 *   ca factor N
 *   ca prime N
 *   ca ec-order --p P --a A --b B
 *   ca gen   --group zp|ec --p P [--a A --b B] [--order N] [--x X] [--seed S]
 *   ca gpu-info
 *   ca volcano --p P --a A --b B [--order N] [--ell 2|3] [--seed S] [--trials T]
 *            [--per-level L] [--controls C] [--radius R] [--threads T]
 *            [--no-negation] [--automorphisms] [--diagram FILE] [--trials-out FILE]
 *            [--census-out FILE] [--edges-out FILE] [--ks K1,K2,...]
 *            one ECDLP instance carried by Velu isogenies to every curve of
 *            the l-volcano; rho on each; min / mean / max per curve and level
 *   ca curve --name NAME | (--group ec --p P --a A --b B [--order N]) | --list
 *            report a curve's endomorphism structure (GLV) and chosen solver
 *   cryptanalysis bsgs|rho --group zp|ec --p P --order N --g G --h H
 *   cryptanalysis rho --curve ecc2k130 [campaign walk options]
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
#include <limits.h>
#include <pthread.h>
#include <signal.h>
#include <time.h>
#include <inttypes.h>
#include <math.h>
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
        "usage: cryptanalysis <command> [options]  (ca is a compatible alias)\n"
        "  bsgs  --group zp|ec --p P --order N --g G --h H [--lo L --hi U]\n"
        "  rho   --group zp|ec --p P --order N --g G --h H [--threads T]\n"
        "  rho   --curve ecc2k130 [--backend cuda|metal] [walk options]\n"
        "        cuda: campaign sigma walk; metal: separate table walk\n"
        "        --check [--kat F] checks the selected backend (KAT: cuda only)\n"
        "  version | factor N | prime N | ec-order --p P --a A --b B | gpu-info\n"
        "  volcano --p P --a A --b B [--order N] [--ell 2|3] [--seed S] [--trials T]\n"
        "        [--per-level L] [--controls C] [--automorphisms] [--diagram FILE]\n"
        "        [--trials-out FILE] [--census-out FILE] [--edges-out FILE] [--ks K1,K2,..]\n"
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
        "        index calculus in the multiplicative group of a prime field\n"
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

static int cmd_solve(const char *selected_alg)
{
    ca_group g;
    make_group(&g);
    if (selected_alg && opt("--alg")) die("--alg belongs to solve, not an algorithm subcommand");
    const char *alg = selected_alg ? selected_alg : opt("--alg");
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

/* ECC2K-130 walks use private curve-specific backends. CUDA uses the live
 * campaign's sigma walk; Metal uses a separate table walk and corpus. This is
 * a walk, not a general arbitrary-target DLP solver. */
static int cmd_ecc2k130_rho(void)
{
    const char *selected_backend = flag("--backend") ? opt("--backend") : "cuda";
    if (!selected_backend ||
        (strcmp(selected_backend, "cuda") && strcmp(selected_backend, "metal")))
        die("--backend must be cuda or metal");
    if (!strcmp(selected_backend, "metal") && (flag("--kat") || flag("--checkpoint")))
        die("Metal table walk has no campaign KAT or CUDA checkpoint format");
    char self[PATH_MAX];
#ifdef __linux__
    ssize_t n = readlink("/proc/self/exe", self, sizeof(self) - 1);
    if (n > 0) {
        self[n] = '\0';
    } else if (!realpath(argv_g[0], self)) {
        die("cannot locate cryptanalysis executable");
    }
#else
    if (!realpath(argv_g[0], self)) die("cannot locate cryptanalysis executable");
#endif
    char *slash = strrchr(self, '/');
    if (!slash) die("cannot locate cryptanalysis executable directory");
    *slash = '\0';
    char backend[PATH_MAX];
    int npath = snprintf(backend, sizeof(backend), "%s/../libexec/cryptanalysis/ecc2k130-rho-%s",
                         self, selected_backend);
    if (npath < 0 || (size_t)npath >= sizeof(backend)) die("backend path is too long");
    if (access(backend, X_OK) != 0)
        die("selected ECC2K-130 rho backend is not installed beside cryptanalysis");
    char **args = calloc((size_t)argc_g + 1, sizeof(*args));
    if (!args) die("cannot allocate backend arguments");
    int j = 0;
    args[j++] = backend;
    if (flag("--check") && flag("--bench")) die("choose only one of --check and --bench");
    args[j++] = flag("--check") ? "check" : flag("--bench") ? "bench" : "walk";
    for (int i = 2; i < argc_g; ++i) {
        if (!strcmp(argv_g[i], "--check") || !strcmp(argv_g[i], "--bench")) continue;
        if (!strcmp(argv_g[i], "--backend")) {
            ++i;
            if (i >= argc_g || strcmp(argv_g[i], selected_backend)) die("invalid --backend value");
            continue;
        }
        if (!strcmp(argv_g[i], "--curve")) {
            ++i;
            if (i >= argc_g || strcmp(argv_g[i], "ecc2k130")) die("--curve must be ecc2k130");
            continue;
        }
        args[j++] = argv_g[i];
    }
    args[j] = NULL;
    execv(backend, args);
    die("cannot execute ECC2K-130 rho kernel");
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
        if (p < 3 || !ca_is_prime(p)) die("--p must be an odd prime");
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
        /* ca_mult_order works in (Z/pZ)^* of order p - 1: prime p only. */
        if (p < 2 || !ca_is_prime(p)) die("--p must be a prime");
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

/*
 * Split --coordinator on commas: one URL per shard, in shard order.
 *
 * Order is the interface, not a convenience.  The Nth URL is shard N, and
 * a fleet that disagrees about which hub is shard 2 splits the point space
 * two different ways -- every hub holding a fraction of a fraction, and
 * collisions parted between them.  So the count is checked against the job
 * document, which carries the number of shards inside its id.
 */
static size_t coord_url_split(const char *list, char **out, size_t max)
{
    size_t n = 0;
    const char *p = list;
    while (p && *p && n < max) {
        while (*p == ' ' || *p == ',') p++;
        if (!*p) break;
        const char *end = strchr(p, ',');
        size_t len = end ? (size_t)(end - p) : strlen(p);
        while (len && (p[len - 1] == ' ')) len--;
        if (!len) {
            if (!end) break;
            p = end + 1;
            continue;
        }
        char *dup = malloc(len + 1);
        if (!dup) break;
        memcpy(dup, p, len);
        dup[len] = 0;
        out[n++] = dup;
        if (!end) break;
        p = end + 1;
    }
    return n;
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
    /* How many hubs the point space is split across.  It goes into the
     * document, so it goes into the id: a fleet cannot half-agree about
     * its own topology. */
    uint64_t shards = opt_u64("--shards", 1);
    if (shards != 1) {
        if (shards == 0 || shards > CA_COORD_SHARDS_MAX) die("--shards out of range");
        rc = ca_coord_job_set_shards(&job, (uint32_t)shards);
        if (rc != CA_OK) die_status(rc);
    }
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
/* The agents this process holds: one per shard, in shard order. */
typedef struct work_fleet {
    ca_coord_agent **agent;
    size_t count;
} work_fleet;

typedef struct work_lane {
    pthread_t thread;
    const ca_coord_ctx *ctx;
    ca_coord_state *st;
    work_fleet *fleet;
    char peer[CA_COORD_PEER_MAX];
    uint64_t max_walkers;
    uint64_t checkin_every;
    uint64_t lease_secs;
    ca_coord_lane_result res;
} work_lane;

static volatile sig_atomic_t work_stop;

/*
 * Send a check-in to the hub that owns it.
 *
 * The library has already split the work by shard and said so in the peer
 * name it built, "<lane>#<shard>", so the shard is read back from there
 * rather than recomputed: one definition of the routing, in the library,
 * and the transport only obeys it.  An unsharded run has no suffix and one
 * agent.
 */
static void work_publish(void *user, const ca_coord_checkin *ci)
{
    work_fleet *f = user;
    if (!f || !f->count) return;
    size_t which = 0;
    const char *hash = strrchr(ci->peer, '#');
    if (hash && hash[1]) {
        char *end = NULL;
        unsigned long v = strtoul(hash + 1, &end, 10);
        if (end && *end == 0 && v < f->count)
            which = (size_t)v;
        else
            return; /* a name we did not build: drop rather than misfile */
    }
    if (f->agent[which]) ca_coord_agent_publish(f->agent[which], ci);
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
    ca_coord_lane_run(w->ctx, w->st, &p, w->fleet && w->fleet->count ? work_publish : NULL,
                      w->fleet, work_should_stop, NULL, &w->res);
    return NULL;
}

/*
 * Compose a lane's peer id, "<node>.<lane>", so that the lane part
 * always survives.
 *
 * The chart passes $(POD_NAME) as --node, and Kubernetes pod names run
 * long: a plain snprintf into CA_COORD_PEER_MAX drops the suffix first,
 * which gives every lane on the host the same identity.  Their sequence
 * numbers then collide and the CRDT discards the later check-ins as
 * duplicates -- silently, and only on the machines with long names.
 *
 * When the node name does not fit, it is cut and a hash of the *whole*
 * name is appended, so two pods sharing a long prefix stay distinct.
 */
/* Identity across a call the optimiser will not inline: it hands the name
 * builders a pointer whose pointee length the compiler cannot bound, so a
 * fixed local buffer does not make -Wformat-truncation flag lane_peer and
 * the shard-identity builder, both of which bound their own output. */
static __attribute__((noinline)) const char *coord_opaque_str(const char *s) { return s; }

static void lane_peer(char *out, size_t cap, const char *node, uint64_t lane)
{
    char suffix[32];
    int sn = snprintf(suffix, sizeof(suffix), ".%" PRIu64, lane);
    if (sn < 0 || (size_t)sn + 2 >= cap) { /* nothing sensible fits */
        snprintf(out, cap, "%" PRIu64, lane);
        return;
    }
    size_t room = cap - 1 - (size_t)sn;
    size_t n = strlen(node);
    if (n <= room) {
        snprintf(out, cap, "%s%s", node, suffix);
        return;
    }
    uint64_t h = 1469598103934665603ULL;
    for (size_t i = 0; i < n; i++) {
        h ^= (unsigned char)node[i];
        h *= 1099511628211ULL;
    }
    char tag[18];
    int tn = snprintf(tag, sizeof(tag), "~%016" PRIx64, h);
    if (tn < 0 || (size_t)tn >= room) {
        snprintf(out, cap, "%016" PRIx64 "%s", h, suffix);
        return;
    }
    size_t keep = room - (size_t)tn;
    memcpy(out, node, keep);
    memcpy(out + keep, tag, (size_t)tn);
    memcpy(out + keep + (size_t)tn, suffix, (size_t)sn + 1);
}

static int cmd_work(void)
{
    ca_coord_ctx *ctx = coord_load(1);
    ca_coord_state *st = NULL;
    if (ca_coord_state_init(&st, ctx) != CA_OK) die("out of memory");

    const char *node_arg = opt("--node");
    if (!node_arg) node_arg = "node";
    /* Fold a random per-process instance tag into the node name, so two
     * agents started with the same --node (two pods from one Deployment,
     * two shells that both defaulted it) do not mint the same peer names
     * and drop each other's check-ins as (peer, seq) duplicates.  See
     * ca_coord_node_instanced and docs/COORDINATOR.md sec. 7. */
    char node_buf[CA_COORD_PEER_MAX];
    ca_coord_node_instanced(node_buf, sizeof(node_buf), node_arg, ca_coord_instance_id());
    /* Read through coord_opaque_str so the downstream name builders see an
     * unbounded char* (as they did when --node came straight from argv),
     * not a fixed array whose worst case trips -Wformat-truncation on code
     * that already bounds its own output at runtime. */
    const char *node = coord_opaque_str(node_buf);
    fprintf(stderr,
            "[agent] node identity: %s (per-process instance tag guards against "
            "same --node collisions)\n",
            node);
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
    uint32_t shards = ca_coord_ctx_job(ctx)->shards;
    char *urls[CA_COORD_SHARDS_MAX];
    size_t nurl = 0;
    if (coord_url()) nurl = coord_url_split(coord_url(), urls, CA_COORD_SHARDS_MAX);
    if (nurl && nurl != (size_t)shards) {
        char msg[192];
        snprintf(msg, sizeof(msg),
                 "this job has %u shard(s), so --coordinator needs %u comma-separated URLs "
                 "in shard order (got %zu)",
                 shards, shards, nurl);
        die(msg);
    }

    work_fleet fleet;
    memset(&fleet, 0, sizeof(fleet));
    if (nurl) {
        fleet.agent = calloc(nurl, sizeof(ca_coord_agent *));
        if (!fleet.agent) die("out of memory");
        fleet.count = nurl;
        for (size_t i = 0; i < nurl; i++) {
            /* Each shard is dialled under its own identity, matching the
             * peer names the library builds, so a hub's view of who is
             * talking to it lines up with what it is being told. */
            char who[CA_COORD_PEER_MAX];
            if (shards > 1)
                snprintf(who, sizeof(who), "%s#%zu", node, i);
            else
                snprintf(who, sizeof(who), "%s", node);
            ca_status rc =
                ca_coord_agent_start(&fleet.agent[i], urls[i], coord_token(), who, ctx, st);
            if (rc != CA_OK) die_status(rc);
            fprintf(stderr, "[agent] shard %zu: dialling %s as %s%s\n", i, urls[i], who,
                    coord_token() ? "" : " (no token)");
        }
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
        lanes[i].fleet = &fleet;
        lanes[i].max_walkers = max_walkers;
        lanes[i].checkin_every = checkin_every;
        lanes[i].lease_secs = lease_secs;
        /* When the campaign is sharded the library appends "#<shard>" to
         * this name, so the budget here has to leave room for it: a name
         * truncated there would give two shards' streams one identity. */
        size_t room = sizeof(lanes[i].peer);
        if (shards > 1) {
            char tail[16];
            room -= (size_t)snprintf(tail, sizeof(tail), "#%u", shards - 1);
        }
        lane_peer(lanes[i].peer, room, node, i);
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
    for (size_t i = 0; i < fleet.count; i++)
        if (!ca_coord_agent_flush(fleet.agent[i], 10000)) flushed = 0;

    uint64_t steps = 0, dps = 0, walkers = 0;
    for (uint64_t i = 0; i < threads; i++) {
        steps += lanes[i].res.steps;
        dps += lanes[i].res.dps;
        walkers += lanes[i].res.walkers;
    }
    uint64_t x = 0;
    int have = ca_coord_solution(st, &x);
    /* Summed across shards: one line for the process, whatever the
     * topology underneath it. */
    ca_coord_agent_stats as;
    memset(&as, 0, sizeof(as));
    for (size_t i = 0; i < fleet.count; i++) {
        ca_coord_agent_stats one;
        ca_coord_agent_stats_get(fleet.agent[i], &one);
        as.received += one.received;
        as.sent += one.sent;
        as.connects += one.connects;
        as.rejected += one.rejected;
        as.reconnects += one.reconnects;
    }
    printf("{\"status\":\"ok\",\"solved\":%s,\"x\":%" PRIu64 ",\"node\":\"%s\",\"lanes\":%" PRIu64
           ",\"walkers\":%" PRIu64 ",\"steps\":%" PRIu64 ",\"dps\":%" PRIu64
           ",\"seconds\":%.3f,\"received\":%" PRIu64 ",\"sent\":%" PRIu64 ",\"connects\":%" PRIu64
           ",\"flushed\":%s,\"shards\":%u}\n",
           have ? "true" : "false", x, node, threads, walkers, steps, dps, ca_now() - start,
           as.received, as.sent, as.connects, flushed ? "true" : "false", shards);
    for (size_t i = 0; i < fleet.count; i++) ca_coord_agent_stop(fleet.agent[i]);
    free(fleet.agent);
    for (size_t i = 0; i < nurl; i++) free(urls[i]);
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

/* ---- volcano: one ECDLP instance on every curve of an l-isogeny volcano --
 *
 * ca volcano --p P --a A --b B [--order N] [--ell 2|3] [--seed S] [--trials T]
 *            [--per-level L] [--controls C] [--radius R] [--max-vertices M]
 *            [--threads T] [--dp-bits D] [--r R] [--no-negation]
 *            [--diagram FILE] [--trials-out FILE]
 *
 * Counts #E (unless --order), takes n the largest prime factor, draws P of
 * order n (cofactor times a seeded random point) and Q = kP, walks the
 * l-volcano (ca_volcano_walk), carries (P, Q) along every edge with Velu's
 * map (checked: on the codomain, a homomorphism, order n kept), and runs
 * ca_rho_solve --trials times on the root, up to --per-level curves of each
 * level, and --controls isomorphic re-scalings of the root.  JSON on stdout
 * with min / mean / median / max / sd / 95% CI of group operations and
 * seconds per curve, per level and pooled; a table on stderr.
 */

typedef struct vstat {
    double min, max, mean, median, sd, ci95;
} vstat;

static int cmp_dbl(const void *x, const void *y)
{
    double a = *(const double *)x, b = *(const double *)y;
    return (a > b) - (a < b);
}

static vstat vstats(const double *x, size_t n)
{
    vstat s = {0};
    if (!n) return s;
    double *t = malloc(n * sizeof(*t));
    if (!t) die("out of memory");
    memcpy(t, x, n * sizeof(*t));
    qsort(t, n, sizeof(*t), cmp_dbl);
    double sum = 0, var = 0;
    for (size_t i = 0; i < n; i++) sum += t[i];
    s.mean = sum / (double)n;
    for (size_t i = 0; i < n; i++) var += (t[i] - s.mean) * (t[i] - s.mean);
    s.sd = n > 1 ? sqrt(var / (double)(n - 1)) : 0;
    s.ci95 = 1.96 * s.sd / sqrt((double)n);
    s.min = t[0];
    s.max = t[n - 1];
    s.median = n % 2 ? t[n / 2] : (t[n / 2 - 1] + t[n / 2]) / 2;
    free(t);
    return s;
}

static void print_vstat(const char *name, vstat s)
{
    printf("\"%s\":{\"min\":%.6g,\"mean\":%.6g,\"median\":%.6g,\"max\":%.6g,\"sd\":%.6g,"
           "\"ci95_half\":%.6g}",
           name, s.min, s.mean, s.median, s.max, s.sd, s.ci95);
}

typedef struct varm {
    char label[24];
    int32_t vertex, level; /* vertex -1 for an isomorphic control */
    uint64_t a, b, j;
    uint64_t P[4], Q[4];
    double *ops, *secs;
    size_t n;
    uint32_t aut_order; /* > 0: solved by the automorphism-folded rho (ca_curve_solve) */
} varm;

static void table_row(const char *name, const char *lv, vstat o, vstat s)
{
    fprintf(stderr, "%-10s%6s%12.0f%12.0f%12.0f%11.2f\n", name, lv, o.min, o.mean, o.max,
            s.mean * 1e3);
}

static const ca_volcano_vertex *g_vsort;

static int cmp_idx_by_j(const void *x, const void *y)
{
    uint64_t a = g_vsort[*(const uint32_t *)x].j, b = g_vsort[*(const uint32_t *)y].j;
    return (a > b) - (a < b);
}

static int cmd_volcano(void)
{
    uint64_t p = opt_u64("--p", 0), a = opt_u64("--a", 0), b = opt_u64("--b", 0);
    if (!p) die("volcano needs --p P --a A --b B");
    unsigned ell = (unsigned)opt_u64("--ell", 3);
    uint64_t seed = opt_u64("--seed", 1), trials = opt_u64("--trials", 20);
    uint64_t per_level = opt_u64("--per-level", 10), controls = opt_u64("--controls", 3);
    uint64_t order = opt_u64("--order", 0);
    if (ell != 2 && ell != 3) die("--ell must be 2 or 3");
    if (!trials) die("--trials must be at least 1");
    if (p <= 3 || p >= (1ULL << 62) || !ca_is_prime(p)) die("--p must be a prime 3 < p < 2^62");
    a %= p;
    b %= p;

    ca_group g0;
    ca_status rc = ca_group_ec_init(&g0, p, a, b, 0);
    if (rc != CA_OK) die_status(rc);
    if (!order) {
        rc = ca_ec_count_points(p, a, b, &order, NULL);
        if (rc != CA_OK) die_status(rc);
    }
    unsigned depth;
    int crater;
    rc = ca_volcano_depth(p, order, ell, &depth, &crater);
    if (rc != CA_OK) die_status(rc);
    for (uint64_t i = 0; i < 8; i++) { /* a wrong --order fails here */
        ca_elem R, O;
        ca_ec_random_point(&g0, &R, ca_mix64(seed + 0x6f72646572ULL + i));
        ca_group_mul(&g0, &O, &R, order, NULL);
        if (!ca_group_is_identity(&g0, &O)) die("--order is not #E(F_p)");
    }
    ca_factorization fz;
    ca_factorize(order, &fz);
    uint64_t n = fz.f[fz.count - 1].p, cof = order / n;
    if (n % ell == 0) die("l divides the subgroup order n; use the other --ell");
    if (n < 5) die("the curve has no prime-order subgroup of order >= 5");

    uint32_t radius = (uint32_t)opt_u64("--radius", 2 * depth + 2);
    ca_volcano vo;
    rc = ca_volcano_walk(p, a, b, order, ell, radius, (uint32_t)opt_u64("--max-vertices", 20000),
                         &vo);
    if (rc != CA_OK) die_status(rc);
    for (uint32_t i = 0; i < vo.count; i++) { /* an edge moves at most one level */
        const ca_volcano_vertex *v = &vo.v[i];
        for (uint32_t q = 0; q < v->n_nbrs && v->level >= 0; q++) {
            int32_t lw = vo.v[v->nbrs[q]].level;
            if (lw >= 0 && (lw - v->level > 1 || v->level - lw > 1))
                die("internal: a volcano edge skips a level");
        }
    }
    if (vo.trace == 0)
        fprintf(stderr, "warning: t = 0, the curve is supersingular; levels may not follow an "
                        "ordinary volcano\n");

    /* The instance on the root, then carried along the breadth-first tree. */
    ca_rng rng;
    ca_rng_seed(&rng, seed);
    rc = ca_group_ec_init(&g0, p, a, b, n);
    if (rc != CA_OK) die_status(rc);
    ca_elem P, Q;
    for (;;) {
        ca_elem R;
        ca_ec_random_point(&g0, &R, ca_rng_next(&rng) | 1);
        ca_group_mul(&g0, &P, &R, cof, NULL);
        if (!ca_group_is_identity(&g0, &P)) break;
    }
    uint64_t k = 1 + ca_rng_below(&rng, n - 1);
    ca_group_mul(&g0, &Q, &P, k, NULL);
    uint64_t(*W)[8] = malloc(vo.count * sizeof(*W));
    if (!W) die("out of memory");
    ca_group_decode(&g0, W[0], &P);
    ca_group_decode(&g0, W[0] + 4, &Q);
    uint32_t verified = 0;
    for (uint32_t i = 1; i < vo.count; i++) {
        const ca_volcano_vertex *v = &vo.v[i], *u = &vo.v[v->parent];
        ca_group gu, gv;
        ca_elem eP, eQ, eS, iP, iQ, iS, chk;
        uint64_t s[4], ms[4];
        ca_velu_map(p, u->a, u->b, ell, v->kernel_x, W[v->parent], W[i]);
        ca_velu_map(p, u->a, u->b, ell, v->kernel_x, W[v->parent] + 4, W[i] + 4);
        if (ca_group_ec_init(&gu, p, u->a, u->b, n) != CA_OK ||
            ca_group_ec_init(&gv, p, v->a, v->b, n) != CA_OK)
            die("internal: a volcano curve is singular");
        ca_group_encode(&gu, &eP, W[v->parent]);
        ca_group_encode(&gu, &eQ, W[v->parent] + 4);
        ca_group_op(&gu, &eS, &eP, &eQ);
        ca_group_decode(&gu, s, &eS);
        ca_velu_map(p, u->a, u->b, ell, v->kernel_x, s, ms);
        if (!ca_group_encode(&gv, &iP, W[i]) || !ca_group_encode(&gv, &iQ, W[i] + 4) ||
            !ca_group_encode(&gv, &iS, ms))
            die("internal: a Velu image is off its codomain");
        ca_group_op(&gv, &chk, &iP, &iQ);
        if (!ca_group_equal(&gv, &chk, &iS)) die("internal: a Velu map is not a homomorphism");
        ca_group_mul(&gv, &chk, &iP, n, NULL);
        if (W[i][2] || !ca_group_is_identity(&gv, &chk))
            die("internal: a Velu map did not keep the order of P");
        verified++;
    }

    /* --census-out / --edges-out: every vertex of the walk (not a sample) and
     * every directed rational l-kernel edge, one JSON object per line, for a
     * durable census.  Vertex lines carry the transported generator g and
     * target h, a seeded native generator gn (order n, independent of the
     * transport) and two isomorphic re-scalings (u^4 a, u^6 b) with g and gn
     * carried to them.  Edge lines are re-derived from each vertex's own model
     * (kernels and Velu codomain) and matched to a vertex by j. */
    const char *cpath = opt("--census-out"), *epath = opt("--edges-out");
    /* --ks: scalars whose multiples [k]P are carried by the same tree (census hk). */
    uint64_t ks[64];
    size_t nks = 0;
    uint64_t (*Wk)[4] = NULL;
    const char *kslist = opt("--ks");
    if (kslist && cpath) {
        for (const char *c = kslist; *c && nks < 64;) {
            char *end;
            ks[nks++] = strtoull(c, &end, 10);
            if (end == c) die("--ks takes decimal scalars separated by commas");
            c = *end == ',' ? end + 1 : end;
        }
        Wk = malloc((size_t)vo.count * nks * sizeof(*Wk));
        if (!Wk) die("out of memory");
        for (size_t q = 0; q < nks; q++) {
            ca_elem Qk;
            ca_group_mul(&g0, &Qk, &P, ks[q], NULL);
            ca_group_decode(&g0, Wk[q], &Qk);
        }
        for (uint32_t i = 1; i < vo.count; i++) {
            const ca_volcano_vertex *v = &vo.v[i], *u = &vo.v[v->parent];
            for (size_t q = 0; q < nks; q++) {
                uint64_t out[3];
                ca_velu_map(p, u->a, u->b, ell, v->kernel_x, Wk[(size_t)v->parent * nks + q], out);
                Wk[(size_t)i * nks + q][0] = out[0];
                Wk[(size_t)i * nks + q][1] = out[1];
                Wk[(size_t)i * nks + q][2] = out[2];
                Wk[(size_t)i * nks + q][3] = 0;
            }
        }
    }
    if (cpath) {
        FILE *cf = fopen(cpath, "w");
        if (!cf) die("cannot open --census-out");
        for (uint32_t i = 0; i < vo.count; i++) {
            const ca_volcano_vertex *v = &vo.v[i];
            ca_group gv;
            if (ca_group_ec_init(&gv, p, v->a, v->b, n) != CA_OK) die("internal: singular vertex");
            ca_elem R, Pn;
            uint64_t wn[4];
            uint64_t s0 = ca_mix64((seed * 0x9E3779B97F4A7C15ULL) ^ v->j ^ 0x6e6174697665ULL);
            for (uint64_t t = 0;; t++) {
                ca_ec_random_point(&gv, &R, ca_mix64(s0 + t) | 1);
                ca_group_mul(&gv, &Pn, &R, cof, NULL);
                if (!ca_group_is_identity(&gv, &Pn)) break;
            }
            ca_group_decode(&gv, wn, &Pn);
            fprintf(cf,
                    "{\"id\":%" PRIu32 ",\"level\":%" PRId32 ",\"dist\":%" PRIu32
                    ",\"parent\":%" PRId32 ",\"kernel_x\":%" PRIu64 ",\"kernels\":%" PRIu32
                    ",\"a\":%" PRIu64 ",\"b\":%" PRIu64 ",\"j\":%" PRIu64 ",\"nbrs\":[",
                    i, v->level, v->dist, v->parent, v->kernel_x, v->kernels, v->a, v->b, v->j);
            for (uint32_t q = 0; q < v->n_nbrs; q++)
                fprintf(cf, "%s%" PRIu32, q ? "," : "", v->nbrs[q]);
            fprintf(cf,
                    "],\"g\":\"%" PRIu64 ",%" PRIu64 "\",\"h\":\"%" PRIu64 ",%" PRIu64
                    "\",\"gn\":\"%" PRIu64 ",%" PRIu64 "\",\"controls\":[",
                    W[i][0], W[i][1], W[i][4], W[i][5], wn[0], wn[1]);
            ca_rng cr;
            ca_rng_seed(&cr, ca_mix64(seed ^ v->j ^ 0x63746c73ULL) | 1);
            for (unsigned c = 0; c < 2; c++) {
                uint64_t u = 2 + ca_rng_below(&cr, p - 2), u2 = ca_mulmod(u, u, p);
                uint64_t u3 = ca_mulmod(u2, u, p);
                fprintf(cf,
                        "%s{\"u\":%" PRIu64 ",\"a\":%" PRIu64 ",\"b\":%" PRIu64 ",\"g\":\"%" PRIu64
                        ",%" PRIu64 "\",\"gn\":\"%" PRIu64 ",%" PRIu64 "\"}",
                        c ? "," : "", u, ca_mulmod(ca_mulmod(u2, u2, p), v->a, p),
                        ca_mulmod(ca_mulmod(u3, u3, p), v->b, p), ca_mulmod(u2, W[i][0], p),
                        ca_mulmod(u3, W[i][1], p), ca_mulmod(u2, wn[0], p), ca_mulmod(u3, wn[1], p));
            }
            fprintf(cf, "]");
            if (Wk) {
                fprintf(cf, ",\"hk\":[");
                for (size_t q = 0; q < nks; q++)
                    fprintf(cf, "%s\"%" PRIu64 ",%" PRIu64 "\"", q ? "," : "",
                            Wk[(size_t)i * nks + q][0], Wk[(size_t)i * nks + q][1]);
                fprintf(cf, "]");
            }
            fprintf(cf, "}\n");
        }
        fclose(cf);
    }
    if (epath) {
        FILE *ef = fopen(epath, "w");
        if (!ef) die("cannot open --edges-out");
        uint32_t *idx = malloc(vo.count * sizeof(*idx));
        if (!idx) die("out of memory");
        for (uint32_t i = 0; i < vo.count; i++) idx[i] = i;
        g_vsort = vo.v;
        qsort(idx, vo.count, sizeof(*idx), cmp_idx_by_j);
        for (uint32_t i = 0; i < vo.count; i++) {
            const ca_volcano_vertex *u = &vo.v[i];
            uint64_t xs[CA_VOLCANO_MAX_NBRS] = {0};
            unsigned nk = ca_isogeny_kernels(p, u->a, u->b, ell, xs);
            for (unsigned ki = 0; ki < nk; ki++) {
                uint64_t a2 = 0, b2 = 0;
                if (ca_velu_codomain(p, u->a, u->b, ell, xs[ki], &a2, &b2) != CA_OK) die("internal: Velu codomain failed");
                /* j = 1728 * 4a^3 / (4a^3 + 27 b^2) */
                uint64_t a3 = ca_mulmod(ca_mulmod(a2, a2, p), a2, p);
                uint64_t t4 = ca_mulmod(4 % p, a3, p);
                uint64_t den = ca_addmod(t4, ca_mulmod(27 % p, ca_mulmod(b2, b2, p), p), p);
                uint64_t j2 = ca_mulmod(ca_mulmod(1728 % p, t4, p), ca_invmod(den, p), p);
                int64_t to = -1;
                uint32_t lo = 0, hi = vo.count;
                while (lo < hi) {
                    uint32_t mid = (lo + hi) / 2;
                    if (vo.v[idx[mid]].j < j2) lo = mid + 1; else hi = mid;
                }
                if (lo < vo.count && vo.v[idx[lo]].j == j2) to = idx[lo];
                const char *dir = "unknown";
                if (to >= 0 && u->level >= 0 && vo.v[to].level >= 0)
                    dir = vo.v[to].level > u->level   ? "down"
                          : vo.v[to].level < u->level ? "up"
                                                      : "horizontal";
                int tree = to >= 0 && vo.v[to].parent == (int32_t)i && vo.v[to].kernel_x == xs[ki];
                int model = tree && vo.v[to].a == a2 && vo.v[to].b == b2;
                const char *special = (j2 == 0 || j2 == 1728 % p) ? "true" : "false";
                fprintf(ef,
                        "{\"from\":%" PRIu32 ",\"to\":%" PRId64 ",\"kernel_x\":%" PRIu64
                        ",\"codomain_a\":%" PRIu64 ",\"codomain_b\":%" PRIu64
                        ",\"codomain_j\":%" PRIu64
                        ",\"dir\":\"%s\",\"tree\":%s,\"model_match\":%s,\"special_j\":%s}\n",
                        i, to, xs[ki], a2, b2, j2, dir, tree ? "true" : "false",
                        model ? "true" : "false", special);
            }
        }
        free(idx);
        fclose(ef);
    }

    /* Arms: the root, up to per_level curves of each level, the controls. */
    int with_aut = flag("--automorphisms");
    size_t cap = 2 * (1 + (depth + 1) * per_level) + controls, na = 0;
    varm *arms = calloc(cap, sizeof(*arms));
    if (!arms) die("out of memory");
    uint32_t *found = calloc(depth + 1, sizeof(*found));
    if (!found) die("out of memory");
    for (uint32_t i = 0; i < vo.count; i++)
        if (vo.v[i].level >= 0) found[vo.v[i].level]++;
    for (unsigned lv = 0; lv <= depth + 1; lv++) {
        uint64_t taken = 0;
        for (uint32_t i = 0; i < vo.count && na < cap; i++) {
            const ca_volcano_vertex *v = &vo.v[i];
            int root_pass = lv == depth + 1;
            if (root_pass ? i != 0 : (i == 0 || v->level != (int32_t)lv || taken >= per_level))
                continue;
            varm *m = &arms[na++];
            snprintf(m->label, sizeof(m->label), "v%" PRIu32, i);
            m->vertex = (int32_t)i;
            m->level = v->level;
            m->a = v->a;
            m->b = v->b;
            m->j = v->j;
            memcpy(m->P, W[i], 4 * sizeof(uint64_t));
            memcpy(m->Q, W[i] + 4, 4 * sizeof(uint64_t));
            taken++;
        }
    }
    for (uint64_t c = 0; c < controls && na < cap; c++) {
        /* (u^4 a, u^6 b), (x, y) -> (u^2 x, u^3 y): the root in new coordinates. */
        uint64_t u = 2 + ca_rng_below(&rng, p - 2), u2 = ca_mulmod(u, u, p);
        uint64_t u3 = ca_mulmod(u2, u, p);
        varm *m = &arms[na++];
        snprintf(m->label, sizeof(m->label), "iso%" PRIu64, c);
        m->vertex = -1;
        m->level = vo.v[0].level;
        m->a = ca_mulmod(ca_mulmod(u2, u2, p), a, p);
        m->b = ca_mulmod(ca_mulmod(u3, u3, p), b, p);
        m->j = vo.v[0].j;
        m->P[0] = ca_mulmod(u2, W[0][0], p);
        m->P[1] = ca_mulmod(u3, W[0][1], p);
        m->Q[0] = ca_mulmod(u2, W[0][4], p);
        m->Q[1] = ca_mulmod(u3, W[0][5], p);
    }

    /* --automorphisms: every curve with automorphisms beyond negation (j = 0
     * or 1728, compatible n) also runs the folded rho of ca_curve_solve on
     * the same instance, beside its plain negation-map rho. */
    for (size_t i = 0, base_arms = na; with_aut && i < base_arms && na < cap; i++) {
        ca_curve_info ci;
        if (arms[i].vertex < 0 || ca_curve_detect(p, arms[i].a, arms[i].b, n, &ci) != CA_OK ||
            ci.endo == CA_CURVE_ENDO_NONE || !ci.lambda)
            continue;
        char base[sizeof(arms[i].label)];
        memcpy(base, arms[i].label, sizeof(base));
        varm *m = &arms[na++];
        *m = arms[i];
        snprintf(m->label, sizeof(m->label), "%.18s+aut", base);
        m->aut_order = ci.aut_order;
    }

    /* Rho: trial-major, so every curve sees the same seeds in turn. */
    ca_rho_params rp;
    ca_rho_params_default(&rp);
    rp.threads = (uint32_t)opt_u64("--threads", 1);
    rp.dp_bits = (int32_t)opt_u64("--dp-bits", (uint64_t)-1);
    rp.r = (uint32_t)opt_u64("--r", 0);
    rp.negation_map = !flag("--no-negation");
    ca_group *gs = calloc(na, sizeof(*gs));
    ca_elem *eP = calloc(na, sizeof(*eP)), *eQ = calloc(na, sizeof(*eQ));
    if (!gs || !eP || !eQ) die("out of memory");
    for (size_t i = 0; i < na; i++) {
        arms[i].ops = calloc(trials, sizeof(double));
        arms[i].secs = calloc(trials, sizeof(double));
        if (!arms[i].ops || !arms[i].secs) die("out of memory");
        ca_status gi = arms[i].aut_order ? ca_curve_group(&gs[i], p, arms[i].a, arms[i].b, n, NULL)
                                         : ca_group_ec_init(&gs[i], p, arms[i].a, arms[i].b, n);
        if (arms[i].aut_order && !gs[i].endo_kind) die("internal: automorphism not enabled");
        if (gi != CA_OK || !ca_group_encode(&gs[i], &eP[i], arms[i].P) ||
            !ca_group_encode(&gs[i], &eQ[i], arms[i].Q))
            die("internal: an instance is not on its curve");
    }
    FILE *tf = NULL;
    const char *tpath = opt("--trials-out");
    if (tpath) {
        tf = fopen(tpath, "w");
        if (!tf) die("cannot open --trials-out");
    }
    if (tf) fprintf(tf, "arm,vertex,level,trial,seed,ops,seconds\n");
    fprintf(stderr,
            "volcano: %" PRIu32 " curves, %" PRIu32 " edges verified, depth %u; rho: %zu "
            "curves x %" PRIu64 " trials\n",
            vo.count, verified, depth, na, trials);
    size_t wrong = 0;
    double t0 = ca_now();
    for (uint64_t t = 0; t < trials; t++) {
        rp.seed = ca_mix64(seed * 0x9E3779B97F4A7C15ULL + t) | 1;
        for (size_t i = 0; i < na; i++) {
            ca_stats st = {0};
            uint64_t x = 0;
            rc = arms[i].aut_order ? ca_curve_solve(&gs[i], &eP[i], &eQ[i], rp.seed, &x, NULL, &st)
                                   : ca_rho_solve(&gs[i], &eP[i], &eQ[i], &rp, &x, &st);
            if (rc != CA_OK || x != k) wrong++;
            arms[i].ops[t] = (double)st.group_ops;
            arms[i].secs[t] = st.seconds;
            arms[i].n = t + 1;
            if (tf)
                fprintf(tf, "%s,%" PRId32 ",%" PRId32 ",%" PRIu64 ",%" PRIu64 ",%" PRIu64 ",%.9f\n",
                        arms[i].label, arms[i].vertex, arms[i].level, t, rp.seed, st.group_ops,
                        st.seconds);
        }
    }
    double wall = ca_now() - t0;
    if (tf) fclose(tf);

    /* Pools: by level (isogenous curves), all isogenous, controls. */
    size_t npool = depth + 4; /* levels, all isogenous, controls, automorphism arms */
    double **pops = calloc(npool, sizeof(*pops)), **psec = calloc(npool, sizeof(*psec));
    size_t *pn = calloc(npool, sizeof(*pn)), *pc = calloc(npool, sizeof(*pc));
    if (!pops || !psec || !pn || !pc) die("out of memory");
    for (size_t q = 0; q < npool; q++) {
        pops[q] = malloc(na * trials * sizeof(double));
        psec[q] = malloc(na * trials * sizeof(double));
        if (!pops[q] || !psec[q]) die("out of memory");
    }
    for (size_t i = 0; i < na; i++) {
        size_t pools[2], np = 0;
        if (arms[i].aut_order) {
            pools[np++] = depth + 3;
        } else if (arms[i].vertex < 0) {
            pools[np++] = depth + 2;
        } else {
            pools[np++] = depth + 1;
            if (arms[i].level >= 0) pools[np++] = (size_t)arms[i].level;
        }
        for (size_t q = 0; q < np; q++) {
            memcpy(pops[pools[q]] + pn[pools[q]], arms[i].ops, arms[i].n * sizeof(double));
            memcpy(psec[pools[q]] + pn[pools[q]], arms[i].secs, arms[i].n * sizeof(double));
            pn[pools[q]] += arms[i].n;
            pc[pools[q]]++;
        }
    }

    const char *shape = crater > 0 ? "split" : crater < 0 ? "inert" : "ramified";
    double pi = 3.14159265358979323846;
    printf("{\"status\":\"%s\",\"p\":%" PRIu64 ",\"a\":%" PRIu64 ",\"b\":%" PRIu64
           ",\"order\":%" PRIu64 ",\"n\":%" PRIu64 ",\"cofactor\":%" PRIu64 ",\"trace\":%" PRId64
           ",\"ell\":%u,\"depth\":%u,\"crater\":\"%s\",\"k\":%" PRIu64 ",\"g\":\"%" PRIu64
           ",%" PRIu64 "\",\"h\":\"%" PRIu64 ",%" PRIu64 "\",",
           wrong ? "wrong" : "ok", p, a, b, order, n, cof, vo.trace, ell, depth, shape, k, W[0][0],
           W[0][1], W[0][4], W[0][5]);
    printf("\"walk\":{\"vertices\":%" PRIu32 ",\"edges\":%" PRIu32 ",\"edges_verified\":%" PRIu32
           ",\"special_j_skipped\":%" PRIu32 ",\"radius\":%" PRIu32 ",\"per_level\":[",
           vo.count, vo.edges, verified, vo.special_j, radius);
    for (unsigned lv = 0; lv <= depth; lv++) printf("%s%" PRIu32, lv ? "," : "", found[lv]);
    printf("]},\"rho\":{\"trials\":%" PRIu64 ",\"seed\":%" PRIu64 ",\"threads\":%" PRIu32
           ",\"negation_map\":%s,\"solves\":%" PRIu64 ",\"wrong\":%zu,\"wall_seconds\":%.3f,"
           "\"expected_ops\":%.1f},\"curves\":[",
           trials, seed, rp.threads ? rp.threads : 1, rp.negation_map ? "true" : "false",
           (uint64_t)na * trials, wrong, wall,
           sqrt(pi * (double)n / (rp.negation_map ? 4.0 : 2.0)));
    for (size_t i = 0; i < na; i++) {
        printf("%s{\"arm\":\"%s\",\"vertex\":%" PRId32 ",\"level\":%" PRId32
               ",\"kind\":\"%s\",\"aut_order\":%" PRIu32 ",\"a\":%" PRIu64 ",\"b\":%" PRIu64
               ",\"j\":%" PRIu64 ",\"g\":\"%" PRIu64 ",%" PRIu64 "\",\"h\":\"%" PRIu64 ",%" PRIu64
               "\",",
               i ? "," : "", arms[i].label, arms[i].vertex, arms[i].level,
               arms[i].aut_order    ? "automorphism-folded"
               : arms[i].vertex < 0 ? "isomorphic-control"
                                    : "isogenous",
               arms[i].aut_order ? arms[i].aut_order : 2, arms[i].a, arms[i].b, arms[i].j,
               arms[i].P[0], arms[i].P[1], arms[i].Q[0], arms[i].Q[1]);
        print_vstat("ops", vstats(arms[i].ops, arms[i].n));
        printf(",");
        print_vstat("seconds", vstats(arms[i].secs, arms[i].n));
        printf("}");
    }
    printf("],\"levels\":[");
    for (unsigned lv = 0, first = 1; lv <= depth; lv++) {
        if (!pn[lv]) continue;
        printf("%s{\"level\":%u,\"curves\":%zu,\"solves\":%zu,", first ? "" : ",", lv, pc[lv],
               pn[lv]);
        print_vstat("ops", vstats(pops[lv], pn[lv]));
        printf(",");
        print_vstat("seconds", vstats(psec[lv], pn[lv]));
        printf("}");
        first = 0;
    }
    printf("],\"all_isogenous\":{\"curves\":%zu,\"solves\":%zu,", pc[depth + 1], pn[depth + 1]);
    print_vstat("ops", vstats(pops[depth + 1], pn[depth + 1]));
    printf(",");
    print_vstat("seconds", vstats(psec[depth + 1], pn[depth + 1]));
    printf("},\"controls\":{\"curves\":%zu,\"solves\":%zu,", pc[depth + 2], pn[depth + 2]);
    print_vstat("ops", vstats(pops[depth + 2], pn[depth + 2]));
    printf(",");
    print_vstat("seconds", vstats(psec[depth + 2], pn[depth + 2]));
    printf("}");
    if (pn[depth + 3]) {
        /* Speed-up of the folded arms over the plain isogenous arms, mean
         * over mean, with a delta-method 95% interval; prediction
         * sqrt(aut_order / 2) beyond the negation map both arms use. */
        vstat va = vstats(pops[depth + 3], pn[depth + 3]);
        vstat vi = vstats(pops[depth + 1], pn[depth + 1]);
        double r = vi.mean / va.mean;
        double rel = sqrt(pow(va.ci95 / va.mean, 2) + pow(vi.ci95 / vi.mean, 2));
        uint32_t ao = 0;
        for (size_t i = 0; i < na; i++)
            if (arms[i].aut_order) ao = arms[i].aut_order;
        printf(",\"automorphism\":{\"curves\":%zu,\"solves\":%zu,\"aut_order\":%" PRIu32 ",",
               pc[depth + 3], pn[depth + 3], ao);
        print_vstat("ops", va);
        printf(",");
        print_vstat("seconds", vstats(psec[depth + 3], pn[depth + 3]));
        printf(",\"ops_speedup_vs_isogenous\":%.4f,\"ops_speedup_ci95_half\":%.4f,"
               "\"predicted\":%.4f}",
               r, r * rel, sqrt(ao / (rp.negation_map ? 2.0 : 1.0)));
    }
    printf("}\n");

    fprintf(stderr, "%-10s%6s%12s%12s%12s%11s\n", "curve", "level", "min ops", "mean ops",
            "max ops", "mean ms");
    for (size_t i = 0; i < na; i++) {
        char lv[16];
        snprintf(lv, sizeof(lv), "%" PRId32, arms[i].level);
        table_row(arms[i].label, lv, vstats(arms[i].ops, arms[i].n),
                  vstats(arms[i].secs, arms[i].n));
    }
    for (unsigned lv = 0; lv <= depth; lv++) {
        if (!pn[lv]) continue;
        char name[16], c[16];
        snprintf(name, sizeof(name), "L%u", lv);
        snprintf(c, sizeof(c), "%zuc", pc[lv]);
        table_row(name, c, vstats(pops[lv], pn[lv]), vstats(psec[lv], pn[lv]));
    }
    table_row("all", "iso", vstats(pops[depth + 1], pn[depth + 1]),
              vstats(psec[depth + 1], pn[depth + 1]));
    if (pn[depth + 2])
        table_row("control", "iso~", vstats(pops[depth + 2], pn[depth + 2]),
                  vstats(psec[depth + 2], pn[depth + 2]));
    if (pn[depth + 3])
        table_row("aut", "fold", vstats(pops[depth + 3], pn[depth + 3]),
                  vstats(psec[depth + 3], pn[depth + 3]));

    /* The standard volcano diagram's input (volcano-diagram/v1, aburan28/crypto). */
    const char *dpath = opt("--diagram");
    if (dpath) {
        FILE *df = fopen(dpath, "w");
        if (!df) die("cannot open --diagram");
        fprintf(df,
                "{\"schema\":\"volcano-diagram/v1\",\"ell\":%u,\"depth\":%u,"
                "\"title\":\"%u-isogeny volcano, depth %u, p = %" PRIu64 "\","
                "\"subtitle\":\"ca volcano --seed %" PRIu64 "\","
                "\"value_label\":\"mean rho group operations (ca)\",\"vertices\":[",
                ell, depth, ell, depth, p, seed);
        for (uint32_t i = 0, first = 1; i < vo.count; i++) {
            const ca_volcano_vertex *v = &vo.v[i];
            if (v->level < 0) continue;
            fprintf(df,
                    "%s{\"id\":%" PRIu32 ",\"label\":\"v%" PRIu32 "\",\"level\":%" PRId32
                    ",\"nbrs\":[",
                    first ? "" : ",", i, i, v->level);
            for (uint32_t q = 0; q < v->n_nbrs; q++)
                fprintf(df, "%s%" PRIu32, q ? "," : "", v->nbrs[q]);
            fprintf(df, "]");
            for (size_t m = 0; m < na; m++)
                if (arms[m].vertex == (int32_t)i && !arms[m].aut_order)
                    fprintf(df, ",\"value\":%.6g", vstats(arms[m].ops, arms[m].n).mean);
            if (i == 0) fprintf(df, ",\"highlight\":\"root\"");
            fprintf(df, "}");
            first = 0;
        }
        fprintf(df, "]}\n");
        fclose(df);
    }

    for (size_t q = 0; q < npool; q++) {
        free(pops[q]);
        free(psec[q]);
    }
    for (size_t i = 0; i < na; i++) {
        free(arms[i].ops);
        free(arms[i].secs);
    }
    free(pops);
    free(psec);
    free(pn);
    free(pc);
    free(gs);
    free(eP);
    free(eQ);
    free(arms);
    free(found);
    free(W);
    free(Wk);
    ca_volcano_free(&vo);
    if (wrong) {
        fprintf(stderr, "error: %zu rho solves returned no or the wrong logarithm\n", wrong);
        return 1;
    }
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
    if (!strcmp(cmd, "solve")) return cmd_solve(NULL);
    if (!strcmp(cmd, "bsgs")) return cmd_solve("bsgs");
    if (!strcmp(cmd, "rho")) {
        const char *curve = opt("--curve");
        if (flag("--curve")) {
            if (!curve || strcmp(curve, "ecc2k130")) die("--curve must be ecc2k130");
            return cmd_ecc2k130_rho();
        }
        if (flag("--check") || flag("--bench") || flag("--kat"))
            die("--check, --bench, and --kat require --curve ecc2k130");
        return cmd_solve("rho");
    }
    if (!strcmp(cmd, "cheon")) return cmd_cheon();
    if (!strcmp(cmd, "ic")) return cmd_ic();
    if (!strcmp(cmd, "coord-job")) return cmd_coord_job();
    if (!strcmp(cmd, "work")) return cmd_work();
    if (!strcmp(cmd, "coord-status")) return cmd_coord_status();
    if (!strcmp(cmd, "num")) return cmd_num();
    if (!strcmp(cmd, "group")) return cmd_group();
    if (!strcmp(cmd, "curve")) return cmd_curve();
    if (!strcmp(cmd, "volcano")) return cmd_volcano();
    usage();
    return 2;
}
