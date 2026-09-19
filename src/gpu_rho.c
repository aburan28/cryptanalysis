/*
 * gpu_rho.c - generic driver for the GPU / emulated Pollard rho.
 *
 * The host builds the multiplier table, chooses the walk count and the
 * distinguished-point density, then repeatedly launches the kernel and
 * drains the DP buffer into a hash table.  A second arrival at a
 * distinguished point with different (a, b) solves the logarithm; the
 * same (a, b) means the walk cycled onto its own trail and it is re-seeded.
 */
#include "gpu_internal.h"
#include "dlog_internal.h"

#include <stdio.h>

void ca_gpu_rho_params_default(ca_gpu_rho_params *p)
{
    memset(p, 0, sizeof(*p));
    p->backend = CA_GPU_BACKEND_AUTO;
    p->dp_bits = -1;
    p->negation_map = 1;
}

const char *ca_gpu_backend_name(ca_gpu_backend b)
{
    switch (b) {
    case CA_GPU_BACKEND_AUTO: return "auto";
    case CA_GPU_BACKEND_CUDA: return "cuda";
    case CA_GPU_BACKEND_EMULATE: return "emulate";
    }
    return "?";
}

int ca_gpu_device_count(void) { return ca_gpu_cuda_device_count_impl(); }
int ca_gpu_device_name(int device, char *buf, size_t len)
{
    return ca_gpu_cuda_device_name_impl(device, buf, len);
}

static int ilog2u(uint64_t v) { int l = -1; while (v) { v >>= 1; l++; } return l; }

/* Solve from a collision between (a1,b1) and (a2,b2) at one canonical point. */
static int gpu_try_solve(const ca_group *g, const ca_elem *base, const ca_elem *target, int negmap,
                         uint64_t a1, uint64_t b1, uint64_t a2, uint64_t b2, uint64_t *x)
{
    uint64_t n = g->order;
    for (int sign = 0; sign < (negmap ? 2 : 1); sign++) {
        uint64_t c, d;
        if (sign == 0) { c = ca_submod(b1, b2, n); d = ca_submod(a2, a1, n); }
        else {
            c = ca_addmod(b1, b2, n);
            d = n - ca_addmod(a1, a2, n);
            if (d == n) d = 0;
        }
        if (c == 0) continue;
        uint64_t gg = ca_gcd(c, n);
        if (d % gg) continue;
        uint64_t nn = n / gg;
        uint64_t x0 = ca_mulmod((d / gg) % nn, ca_invmod((c / gg) % nn, nn), nn);
        if (gg > 65536) gg = 65536;
        for (uint64_t k = 0; k < gg; k++) {
            uint64_t cand = x0 + k * nn;
            if (cand >= n) break;
            if (ca_verify_log(g, base, target, cand)) { *x = cand; return 1; }
        }
    }
    return 0;
}

ca_status ca_gpu_rho_solve(const ca_group *g, const ca_elem *base, const ca_elem *target,
                           const ca_gpu_rho_params *params, uint64_t *x, ca_stats *st)
{
    ca_gpu_rho_params def;
    if (!params) { ca_gpu_rho_params_default(&def); params = &def; }
    if (g->order == 0) {
        ca_set_error("GPU rho requires a known group order");
        return CA_ERR_INVALID;
    }
    double t0 = ca_now();
    uint64_t n = g->order;

    /* Backend selection happens before the shortcuts below, so that asking
     * explicitly for CUDA fails predictably when CUDA is unavailable instead
     * of quietly answering from the CPU. */
    const ca_gpu_backend_ops *ops;
    switch (params->backend) {
    case CA_GPU_BACKEND_CUDA:
        if (!ca_gpu_cuda_compiled()) { ca_set_error("CUDA backend not compiled in (CA_CUDA=OFF)"); return CA_ERR_UNSUPPORTED; }
        if (ca_gpu_device_count() <= params->device) { ca_set_error("no CUDA device %d", params->device); return CA_ERR_UNSUPPORTED; }
        ops = &ca_gpu_cuda_ops;
        break;
    case CA_GPU_BACKEND_EMULATE:
        ops = &ca_gpu_emulate_ops;
        break;
    default:
        ops = (ca_gpu_cuda_compiled() && ca_gpu_device_count() > params->device) ? &ca_gpu_cuda_ops
                                                                                   : &ca_gpu_emulate_ops;
        break;
    }
    int on_gpu = ops == &ca_gpu_cuda_ops;

    if (ca_group_is_identity(g, target)) { *x = 0; return CA_OK; }
    if (n < 4096) {
        /* smaller than one launch is worth: brute force on the host */
        ca_elem cur;
        ca_group_identity(g, &cur);
        for (uint64_t k = 0; k < n; k++) {
            if (ca_group_equal(g, &cur, target)) {
                *x = k;
                if (st) { st->group_ops += k; st->seconds += ca_now() - t0; }
                return CA_OK;
            }
            ca_group_op(g, &cur, &cur, base);
        }
        return CA_ERR_NOT_FOUND;
    }

    ca_gpu_rho_args a;
    memset(&a, 0, sizeof(a));
    a.p = g->p;
    a.pinv = g->mont.pinv;
    a.one = g->mont.r1;
    a.a_mont = g->a_mont;
    a.n = n;
    a.kind = g->kind == CA_GROUP_EC ? CA_GPU_KIND_EC : CA_GPU_KIND_ZP;
    a.negmap = params->negation_map && g->kind == CA_GROUP_EC;
    a.seed = ca_seed_or_random(params->seed);
    /* internal (Montgomery) words of base and target */
    a.base_x = base->w[0];
    a.base_y = base->w[1];
    if (a.kind == CA_GPU_KIND_EC && base->w[2]) a.base_x = g->p;
    a.target_x = target->w[0];
    a.target_y = target->w[1];
    if (a.kind == CA_GPU_KIND_EC && target->w[2]) a.target_x = g->p;

    uint64_t sqrt_n = ca_isqrt(n) + 1;
    int lg = ilog2u(n) + 1;
    /* multiplier count: the table is built on the host (cheap), so use the
     * large tables that keep fruitless cycles rare whenever the group is
     * big enough for them to matter (r <= sqrt(n)/64). */
    if (params->r) a.r = params->r;
    else {
        uint64_t budget = sqrt_n / 64;
        uint32_t r = 8, cap = a.negmap ? 1024u : 64u;
        while (r * 2 <= budget && r * 2 <= cap) r *= 2;
        a.r = r;
    }
    if (a.r < 4) a.r = 4;
    /* thread count: every walk start costs ~3 log2(n) operations; keep the
     * total under sqrt(n)/8.  Threads beyond nthreads in the last block
     * exit immediately, so small groups do not pay for a full block. */
    uint32_t tpb = params->threads_per_block ? params->threads_per_block : 128;
    uint32_t blocks = params->blocks;
    uint64_t nthreads;
    if (blocks == 0) {
        uint64_t walks_cap = sqrt_n / (24u * (uint64_t)lg);
        uint64_t threads_cap = walks_cap / CA_GPU_W;
        if (threads_cap < 1) threads_cap = 1;
        uint64_t want = on_gpu ? (uint64_t)tpb * 1024 : (uint64_t)tpb * 4;
        nthreads = want > threads_cap ? threads_cap : want;
        blocks = (uint32_t)((nthreads + tpb - 1) / tpb);
    } else {
        nthreads = (uint64_t)blocks * tpb;
    }
    a.nthreads = (uint32_t)nthreads;
    uint64_t nwalks = (uint64_t)a.nthreads * CA_GPU_W;
    /* distinguished points: ~32 per walk over the expected run, at most 2^24 total */
    double expected = 1.25 * (double)sqrt_n / (a.negmap ? 1.4142 : 1.0);
    int dp = params->dp_bits;
    if (dp < 0) {
        double per_walk = expected / (32.0 * (double)nwalks);
        dp = per_walk >= 2.0 ? ilog2u((uint64_t)per_walk) : 0;
        int min_dp = ilog2u((uint64_t)expected) - 24;
        if (dp < min_dp) dp = min_dp;
        if (dp < 0) dp = 0;
        if (dp > 48) dp = 48;
    }
    /* An explicitly requested dp_bits is honoured, but a shift of 64 or more
     * is undefined, so clamp it.  (Anything near this makes distinguished
     * points so rare that a work limit is essential; see ca_gpu.h.) */
    if (dp > 63) dp = 63;
    a.dp_mask = dp ? ((1ULL << dp) - 1) : 0;
    a.abandon_shift = (uint32_t)dp;
    uint32_t steps = params->steps_per_launch;
    if (steps == 0) {
        /* Aim at about 1/16 of the expected work per launch, but run at least
         * long enough that the herd is likely to report a distinguished point
         * (one per 2^dp steps, spread over nwalks walks). */
        double per = expected / (16.0 * (double)nwalks);
        double dp_floor = (double)(1ULL << (dp > 40 ? 40 : dp)) / (double)nwalks;
        if (per < dp_floor) per = dp_floor;
        if (per < 64) per = 64;
        /* A launch is not interruptible and max_ops is only checked between
         * launches, so never put more than the whole expected run - or the
         * whole work limit - into one of them.  Without this an unusual
         * dp_bits makes a single launch dwarf the entire search. */
        double whole_run = expected / (double)nwalks + 64;
        if (per > whole_run) per = whole_run;
        if (params->max_ops) {
            double limit = (double)params->max_ops / (double)nwalks + 1;
            if (per > limit) per = limit;
        }
        if (per > 1e7) per = 1e7;
        steps = per < 1 ? 1 : (uint32_t)per;
    }
    a.steps = steps;
    /* DP buffer for one launch: twice the expected count plus slack, and
     * hard-capped so that a large group cannot ask for a huge allocation.
     * Overflowing the buffer is safe by construction: the kernel drops the
     * excess (it only writes slots below dp_cap) and the host clamps the
     * count, so an overflow costs work, never correctness. */
    double exp_dps = (double)nwalks * steps / (double)(1ULL << dp);
    uint64_t cap = (uint64_t)(exp_dps * 2) + 4096;
    if (cap > (1u << 20)) cap = 1u << 20;
    a.dp_cap = (uint32_t)cap;

    /* multipliers (host) */
    uint64_t *mult = malloc((size_t)a.r * 4 * sizeof(uint64_t));
    if (!mult) return CA_ERR_NOMEM;
    ca_rng rng;
    ca_rng_seed(&rng, a.seed);
    uint64_t setup_ops = 0;
    for (uint32_t i = 0; i < a.r; i++) {
        uint64_t al = ca_rng_below(&rng, n), be = ca_rng_below(&rng, n);
        ca_elem t1, t2, m;
        ca_group_mul(g, &t1, base, al, &setup_ops);
        ca_group_mul(g, &t2, target, be, &setup_ops);
        ca_group_op(g, &m, &t1, &t2);
        mult[4 * i] = (a.kind == CA_GPU_KIND_EC && m.w[2]) ? g->p : m.w[0];
        mult[4 * i + 1] = m.w[1];
        mult[4 * i + 2] = al;
        mult[4 * i + 3] = be;
    }
    a.mult = mult;

    void *ctx = NULL;
    ca_status rc = ops->create(&a, tpb, params->device, &ctx);
    if (rc != CA_OK) { free(mult); return rc; }
    ca_htab tab;
    if (ca_htab_init(&tab, (size_t)(expected / (double)(1ULL << dp)) + 4096) != CA_OK) {
        ops->destroy(ctx);
        free(mult);
        return CA_ERR_NOMEM;
    }
    uint64_t total_ops = setup_ops, launches = 0, dps_total = 0, restarts = 0;
    rc = CA_ERR_INTERNAL;
    for (;;) {
        const uint64_t *dps;
        uint32_t count;
        ca_status lrc = ops->launch(ctx, &dps, &count);
        if (lrc != CA_OK) { rc = lrc; break; }
        launches++;
        /* One walk step is one group operation.  Retried steps (negation-map
         * look-ahead) really do perform an operation, so they belong here;
         * the rare cycle-escape walk is device-side and is not counted, so
         * this is a very slight undercount when escapes happen. */
        total_ops += nwalks * steps;
        dps_total += count;
        int done = 0;
        for (uint32_t i = 0; i < count && !done; i++) {
            uint64_t h = dps[4 * i], da = dps[4 * i + 1], db = dps[4 * i + 2];
            uint32_t wid = (uint32_t)dps[4 * i + 3];
            uint64_t oa, ob;
            int ir = ca_htab_insert(&tab, h, da, db, &oa, &ob);
            if (ir < 0) { rc = CA_ERR_NOMEM; done = 1; break; }
            if (ir == 1) {
                if (oa == da && ob == db) {
                    ops->restart(ctx, wid);
                    restarts++;
                } else if (gpu_try_solve(g, base, target, a.negmap, oa, ob, da, db, x)) {
                    rc = CA_OK;
                    done = 1;
                } else {
                    ops->restart(ctx, wid);
                    restarts++;
                }
            }
        }
        if (done) break;
        if (params->max_ops && total_ops > params->max_ops) { rc = CA_ERR_LIMIT; break; }
    }
    if (st) {
        st->group_ops += total_ops;
        st->iterations += dps_total;
        st->collisions += restarts;
        st->table_entries = ca_max_u64(st->table_entries, tab.count);
        st->bytes_peak = ca_max_u64(st->bytes_peak, ca_htab_bytes(&tab) + nwalks * 96 + (uint64_t)a.dp_cap * 32);
        st->threads = a.nthreads;
        st->reserved = (uint32_t)launches;
        st->seconds += ca_now() - t0;
    }
    ca_htab_free(&tab);
    ops->destroy(ctx);
    free(mult);
    return rc;
}
