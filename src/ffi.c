/*
 * ffi.c - flat C ABI on top of the structured API.
 */
#include "cryptanalysis/cryptanalysis.h"
#include "ca_internal.h"

struct ca_ctx {
    ca_group g;
};

#define ENC(ctx, e, w) \
    do { if (!ca_group_encode(&(ctx)->g, &(e), (w))) { ca_set_error("element is not in the group"); return CA_ERR_INVALID; } } while (0)

ca_ctx *ca_ctx_new_zp(uint64_t p, uint64_t order)
{
    ca_ctx *c = calloc(1, sizeof(*c));
    if (!c) return NULL;
    if (ca_group_zp_init(&c->g, p, order) != CA_OK) { free(c); return NULL; }
    return c;
}

ca_ctx *ca_ctx_new_ec(uint64_t p, uint64_t a, uint64_t b, uint64_t order)
{
    ca_ctx *c = calloc(1, sizeof(*c));
    if (!c) return NULL;
    if (ca_group_ec_init(&c->g, p, a, b, order) != CA_OK) { free(c); return NULL; }
    return c;
}

void ca_ctx_free(ca_ctx *ctx) { free(ctx); }
int ca_ctx_kind(const ca_ctx *ctx) { return (int)ctx->g.kind; }
uint64_t ca_ctx_p(const ca_ctx *ctx) { return ctx->g.p; }
uint64_t ca_ctx_order(const ca_ctx *ctx) { return ctx->g.order; }
uint64_t ca_ctx_cofactor(const ca_ctx *ctx) { return ctx->g.cofactor; }
uint64_t ca_ctx_curve_a(const ca_ctx *ctx) { return ctx->g.a; }
uint64_t ca_ctx_curve_b(const ca_ctx *ctx) { return ctx->g.b; }
void ca_ctx_set_order(ca_ctx *ctx, uint64_t order, uint64_t cofactor)
{
    ca_clear_error();
    ctx->g.order = order;
    ctx->g.cofactor = cofactor;
}

int ca_ctx_validate(const ca_ctx *ctx, const uint64_t w[4])
{
    ca_clear_error();
    ca_elem e;
    return ca_group_encode(&ctx->g, &e, w) ? 1 : 0;
}

int ca_ctx_identity(const ca_ctx *ctx, uint64_t out[4])
{
    ca_clear_error();
    ca_elem e;
    ca_group_identity(&ctx->g, &e);
    ca_group_decode(&ctx->g, out, &e);
    return CA_OK;
}

int ca_ctx_is_identity(const ca_ctx *ctx, const uint64_t w[4])
{
    ca_clear_error();
    ca_elem e;
    if (!ca_group_encode(&ctx->g, &e, w)) return 0;
    return ca_group_is_identity(&ctx->g, &e);
}

int ca_ctx_op(const ca_ctx *ctx, uint64_t out[4], const uint64_t a[4], const uint64_t b[4])
{
    ca_clear_error();
    ca_elem ea, eb, r;
    ENC(ctx, ea, a);
    ENC(ctx, eb, b);
    ca_group_op(&ctx->g, &r, &ea, &eb);
    ca_group_decode(&ctx->g, out, &r);
    return CA_OK;
}

int ca_ctx_inv(const ca_ctx *ctx, uint64_t out[4], const uint64_t a[4])
{
    ca_clear_error();
    ca_elem ea, r;
    ENC(ctx, ea, a);
    ca_group_inv(&ctx->g, &r, &ea);
    ca_group_decode(&ctx->g, out, &r);
    return CA_OK;
}

int ca_ctx_mul(const ca_ctx *ctx, uint64_t out[4], const uint64_t a[4], uint64_t k)
{
    ca_clear_error();
    ca_elem ea, r;
    ENC(ctx, ea, a);
    ca_group_mul(&ctx->g, &r, &ea, k, NULL);
    ca_group_decode(&ctx->g, out, &r);
    return CA_OK;
}

int ca_ctx_equal(const ca_ctx *ctx, const uint64_t a[4], const uint64_t b[4])
{
    ca_clear_error();
    ca_elem ea, eb;
    if (!ca_group_encode(&ctx->g, &ea, a) || !ca_group_encode(&ctx->g, &eb, b)) return 0;
    return ca_group_equal(&ctx->g, &ea, &eb);
}

int ca_ctx_elem_order(const ca_ctx *ctx, const uint64_t a[4], uint64_t *order)
{
    ca_clear_error();
    ca_elem ea;
    ENC(ctx, ea, a);
    uint64_t o = ca_group_elem_order(&ctx->g, &ea);
    if (o == 0) return CA_ERR_INVALID;
    *order = o;
    return CA_OK;
}

int ca_ctx_find_generator(const ca_ctx *ctx, uint64_t out[4], uint64_t seed)
{
    ca_clear_error();
    ca_elem e;
    ca_status rc = ca_group_find_generator(&ctx->g, &e, seed);
    if (rc != CA_OK) return rc;
    ca_group_decode(&ctx->g, out, &e);
    return CA_OK;
}

int ca_ctx_random_element(const ca_ctx *ctx, uint64_t out[4], uint64_t seed)
{
    ca_clear_error();
    ca_elem e;
    if (ctx->g.kind == CA_GROUP_EC) {
        ca_ec_random_point(&ctx->g, &e, seed);
        if (ctx->g.cofactor > 1) ca_group_mul(&ctx->g, &e, &e, ctx->g.cofactor, NULL);
    } else {
        ca_rng rng;
        ca_rng_seed(&rng, ca_seed_or_random(seed));
        const uint64_t w[4] = {1 + ca_rng_below(&rng, ctx->g.p - 1), 0, 0, 0};
        ca_group_encode(&ctx->g, &e, w);
        if (ctx->g.cofactor > 1) ca_group_mul(&ctx->g, &e, &e, ctx->g.cofactor, NULL);
    }
    ca_group_decode(&ctx->g, out, &e);
    return CA_OK;
}

int ca_ctx_lift_x(const ca_ctx *ctx, uint64_t out[4], uint64_t x)
{
    ca_clear_error();
    if (ctx->g.kind != CA_GROUP_EC) return CA_ERR_UNSUPPORTED;
    ca_elem e;
    if (!ca_ec_lift_x(&ctx->g, &e, x)) return CA_ERR_NOT_FOUND;
    ca_group_decode(&ctx->g, out, &e);
    return CA_OK;
}

int ca_ec_order(uint64_t p, uint64_t a, uint64_t b, uint64_t *order)
{
    ca_clear_error();
    return ca_ec_count_points(p, a, b, order, NULL);
}

/* ---- options -------------------------------------------------------------- */

void ca_ffi_options_default(ca_ffi_options *o)
{
    memset(o, 0, sizeof(*o));
    o->threads = 1;
    o->rho_dp_bits = -1;
    o->rho_negation_map = 1;
    o->kangaroo_dp_bits = -1;
    o->grumpy_alpha = 0.7;
    o->solver = CA_SOLVER_AUTO;
}

size_t ca_ffi_options_size(void) { return sizeof(ca_ffi_options); }
size_t ca_stats_size(void) { return sizeof(ca_stats); }
size_t ca_ic_params_size(void) { return sizeof(ca_ic_params); }
size_t ca_ic_stats_size(void) { return sizeof(ca_ic_stats); }

static void opts_to_dlog(const ca_ffi_options *o, ca_dlog_params *d)
{
    ca_dlog_params_default(d);
    ca_ffi_options def;
    if (!o) { ca_ffi_options_default(&def); o = &def; }
    d->solver = (ca_solver)o->solver;
    if (o->bsgs_max_prime) d->bsgs_max_prime = o->bsgs_max_prime;
    d->bsgs.table_size = o->bsgs_table_size;
    d->bsgs.max_ops = o->max_ops;
    d->rho.threads = o->threads;
    d->rho.r = o->rho_r;
    d->rho.dp_bits = o->rho_dp_bits;
    d->rho.walks_per_thread = o->rho_walks_per_thread;
    d->rho.negation_map = o->rho_negation_map;
    d->rho.seed = o->seed;
    d->rho.max_ops = o->max_ops;
    d->rho.max_table_entries = o->rho_max_table_entries;
    d->kangaroo.herd_size = o->kangaroo_herd_size;
    d->kangaroo.dp_bits = o->kangaroo_dp_bits;
    d->kangaroo.jumps = o->kangaroo_jumps;
    d->kangaroo.seed = o->seed;
    d->kangaroo.max_ops = o->max_ops;
    d->grumpy.m = o->grumpy_m;
    d->grumpy.alpha = o->grumpy_alpha;
    d->grumpy.max_ops = o->max_ops;
}

int ca_ffi_bsgs(const ca_ctx *ctx, const uint64_t base[4], const uint64_t target[4], uint64_t lo,
                uint64_t hi, const ca_ffi_options *o, uint64_t *x, ca_stats *st)
{
    ca_clear_error();
    ca_elem b, t;
    ENC(ctx, b, base);
    ENC(ctx, t, target);
    ca_dlog_params d;
    opts_to_dlog(o, &d);
    return ca_bsgs_solve(&ctx->g, &b, &t, lo, hi, &d.bsgs, x, st);
}

int ca_ffi_kangaroo(const ca_ctx *ctx, const uint64_t base[4], const uint64_t target[4], uint64_t lo,
                    uint64_t hi, const ca_ffi_options *o, uint64_t *x, ca_stats *st)
{
    ca_clear_error();
    ca_elem b, t;
    ENC(ctx, b, base);
    ENC(ctx, t, target);
    ca_dlog_params d;
    opts_to_dlog(o, &d);
    return ca_kangaroo_solve(&ctx->g, &b, &t, lo, hi, &d.kangaroo, x, st);
}

int ca_ffi_grumpy(const ca_ctx *ctx, const uint64_t base[4], const uint64_t target[4], uint64_t lo,
                  uint64_t hi, const ca_ffi_options *o, uint64_t *x, ca_stats *st)
{
    ca_clear_error();
    ca_elem b, t;
    ENC(ctx, b, base);
    ENC(ctx, t, target);
    ca_dlog_params d;
    opts_to_dlog(o, &d);
    return ca_grumpy_solve(&ctx->g, &b, &t, lo, hi, &d.grumpy, x, st);
}

int ca_ffi_rho(const ca_ctx *ctx, const uint64_t base[4], const uint64_t target[4],
               const ca_ffi_options *o, uint64_t *x, ca_stats *st)
{
    ca_clear_error();
    ca_elem b, t;
    ENC(ctx, b, base);
    ENC(ctx, t, target);
    ca_dlog_params d;
    opts_to_dlog(o, &d);
    return ca_rho_solve(&ctx->g, &b, &t, &d.rho, x, st);
}

int ca_ffi_dlog(const ca_ctx *ctx, const uint64_t base[4], const uint64_t target[4],
                const ca_ffi_options *o, uint64_t *x, ca_stats *st)
{
    ca_clear_error();
    ca_elem b, t;
    ENC(ctx, b, base);
    ENC(ctx, t, target);
    ca_dlog_params d;
    opts_to_dlog(o, &d);
    return ca_pohlig_hellman(&ctx->g, &b, &t, &d, x, st);
}

int ca_ffi_cheon(const ca_ctx *ctx, const uint64_t gen[4], const uint64_t g_alpha[4],
                 const uint64_t g_alpha_d[4], uint64_t d, uint64_t max_exps, uint64_t *alpha,
                 ca_stats *st)
{
    ca_clear_error();
    ca_elem g, ga, gad;
    ENC(ctx, g, gen);
    ENC(ctx, ga, g_alpha);
    ENC(ctx, gad, g_alpha_d);
    ca_cheon_params p;
    ca_cheon_params_default(&p);
    p.max_exps = max_exps;
    return ca_cheon_solve(&ctx->g, &g, &ga, &gad, d, &p, alpha, st);
}

int ca_ffi_cheon_instance(const ca_ctx *ctx, const uint64_t gen[4], uint64_t alpha, uint64_t d,
                          uint64_t g_alpha[4], uint64_t g_alpha_d[4])
{
    ca_clear_error();
    ca_elem g, ga, gad;
    ENC(ctx, g, gen);
    ca_status rc = ca_cheon_make_instance(&ctx->g, &g, alpha, d, &ga, &gad);
    if (rc != CA_OK) return rc;
    ca_group_decode(&ctx->g, g_alpha, &ga);
    ca_group_decode(&ctx->g, g_alpha_d, &gad);
    return CA_OK;
}

uint64_t ca_ffi_cheon_best_divisor(uint64_t p, double *cost_exps)
{
    ca_clear_error();
    return ca_cheon_best_divisor(p, cost_exps);
}

void ca_ffi_gpu_options_default(ca_ffi_gpu_options *o)
{
    ca_gpu_rho_params p;
    ca_gpu_rho_params_default(&p);
    memset(o, 0, sizeof(*o));
    o->backend = (int32_t)p.backend;
    o->device = p.device;
    o->threads_per_block = p.threads_per_block;
    o->blocks = p.blocks;
    o->steps_per_launch = p.steps_per_launch;
    o->r = p.r;
    o->dp_bits = p.dp_bits;
    o->negation_map = p.negation_map;
    o->seed = p.seed;
    o->max_ops = p.max_ops;
}

size_t ca_ffi_gpu_options_size(void) { return sizeof(ca_ffi_gpu_options); }

int ca_ffi_gpu_rho(const ca_ctx *ctx, const uint64_t base[4], const uint64_t target[4],
                   const ca_ffi_gpu_options *o, uint64_t *x, ca_stats *st)
{
    ca_clear_error();
    ca_elem b, t;
    ENC(ctx, b, base);
    ENC(ctx, t, target);
    ca_gpu_rho_params p;
    ca_gpu_rho_params_default(&p);
    if (o) {
        p.backend = (ca_gpu_backend)o->backend;
        p.device = o->device;
        p.threads_per_block = o->threads_per_block;
        p.blocks = o->blocks;
        p.steps_per_launch = o->steps_per_launch;
        p.r = o->r;
        p.dp_bits = o->dp_bits;
        p.negation_map = o->negation_map;
        p.seed = o->seed;
        p.max_ops = o->max_ops;
    }
    return ca_gpu_rho_solve(&ctx->g, &b, &t, &p, x, st);
}

int ca_ffi_gpu_cuda_compiled(void) { return ca_gpu_cuda_compiled(); }
int ca_ffi_gpu_device_count(void) { return ca_gpu_device_count(); }
int ca_ffi_gpu_device_name(int device, char *buf, size_t len)
{
    return ca_gpu_device_name(device, buf, len);
}

int ca_ffi_ic_solve(uint64_t p, uint64_t g, uint64_t h, const ca_ic_params *params, uint64_t *x,
                    ca_ic_stats *st)
{
    ca_clear_error();
    return ca_ic_solve(p, g, h, params, x, st);
}

int ca_ffi_is_prime(uint64_t n) { return ca_is_prime(n); }
uint64_t ca_ffi_next_prime(uint64_t n) { return ca_next_prime(n); }
uint64_t ca_ffi_primitive_root(uint64_t p) { return ca_primitive_root(p); }
uint64_t ca_ffi_powmod(uint64_t b, uint64_t e, uint64_t m) { return ca_powmod(b, e, m); }
uint64_t ca_ffi_invmod(uint64_t a, uint64_t m) { return ca_invmod(a, m); }

unsigned ca_ffi_factorize(uint64_t n, uint64_t *primes, unsigned *exps, unsigned cap)
{
    ca_clear_error();
    ca_factorization f;
    if (ca_factorize(n, &f) != CA_OK) return 0;
    for (unsigned i = 0; i < f.count && i < cap; i++) {
        primes[i] = f.f[i].p;
        exps[i] = f.f[i].e;
    }
    return f.count;
}
