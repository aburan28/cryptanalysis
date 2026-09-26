/*
 * kangaroo.c - van Oorschot-Wiener parallel kangaroos (run in one thread
 * with batched group operations).
 *
 * Positions are tracked as integers (exponents); tame kangaroos start at
 * lo + width/2 + small offsets, wild kangaroos start at target + small
 * offsets.  Jump j of size s_j = 2^j is chosen by the element hash.  When
 * a tame and a wild kangaroo land on the same distinguished point,
 * x = tame_position - wild_distance.
 */
#include "cryptanalysis/ca_kangaroo.h"
#include "dlog_internal.h"

void ca_kangaroo_params_default(ca_kangaroo_params *p)
{
    memset(p, 0, sizeof(*p));
    p->dp_bits = -1;
}

typedef struct roo {
    ca_elem Y;
    uint64_t dist;    /* tame: absolute exponent; wild: offset from x */
    uint64_t since_dp;
} roo;

ca_status ca_kangaroo_solve(const ca_group *g, const ca_elem *base, const ca_elem *target,
                            uint64_t lo, uint64_t hi, const ca_kangaroo_params *params,
                            uint64_t *x, ca_stats *st)
{
    ca_kangaroo_params def;
    if (!params) { ca_kangaroo_params_default(&def); params = &def; }
    ca_status rc = ca_resolve_interval(g, &lo, &hi);
    if (rc != CA_OK) return rc;
    double t0 = ca_now();
    uint64_t width = hi - lo; /* inclusive count minus one */
    uint64_t n = g->order;

    /* tiny interval: linear scan */
    if (width < 256) {
        ca_elem cur;
        ca_group_mul(g, &cur, base, lo, st ? &st->group_ops : NULL);
        for (uint64_t k = 0; k <= width; k++) {
            if (ca_group_equal(g, &cur, target)) {
                *x = lo + k;
                if (st) { st->group_ops += k; st->seconds += ca_now() - t0; }
                return CA_OK;
            }
            ca_group_op(g, &cur, &cur, base);
        }
        return CA_ERR_NOT_FOUND;
    }

    uint64_t sqrt_w = ca_isqrt(width) + 1;
    uint32_t herd = params->herd_size;
    /* 2 * herd must not wrap, and the herd arrays are allocated up front:
     * CA_KANGAROO_MAX_HERD kangaroos per herd is already 64 MB of state. */
    if (herd > CA_KANGAROO_MAX_HERD) herd = CA_KANGAROO_MAX_HERD;
    if (herd == 0) {
        /* each kangaroo start costs ~1.5 log2(n) operations; keep the total
         * start-up under sqrt(width)/8 */
        herd = (g->kind == CA_GROUP_EC) ? 64 : 8;
        unsigned lg = 1;
        for (uint64_t t = n ? n : width; t > 1; t >>= 1) lg++;
        uint64_t cap = sqrt_w / (24u * (uint64_t)lg);
        if (cap < 1) cap = 1;
        if (herd > cap) herd = (uint32_t)cap;
    }
    uint32_t total = 2 * herd;
    /* mean jump ~ total * sqrt(width) / 4 (vOW), realised with powers of two */
    double mean_target = (double)total * (double)sqrt_w / 4.0;
    if (mean_target < 2) mean_target = 2;
    uint32_t nj = params->jumps;
    if (nj == 0) {
        nj = 1;
        while (nj < 63 && ((double)((1ULL << nj) - 1) / (double)nj) < mean_target) nj++;
    }
    if (nj > 62) nj = 62;
    int dp = params->dp_bits;
    if (dp > 62) dp = 62; /* dp is a shift count for a 64-bit mask */
    if (dp < 0) {
        double expected = 2.0 * (double)sqrt_w; /* total jumps */
        double per_roo = expected / (32.0 * total);
        dp = 0;
        while (per_roo >= 2.0 && dp < 40) { per_roo /= 2; dp++; }
    }
    uint64_t dp_mask = dp ? ((1ULL << dp) - 1) : 0;

    /* jump table */
    ca_elem *J = calloc(nj, sizeof(ca_elem));
    uint64_t *jsz = calloc(nj, sizeof(uint64_t));
    roo *roos = calloc(total, sizeof(roo));
    ca_elem *Yn = calloc(total, sizeof(ca_elem));
    ca_elem *B = calloc(total, sizeof(ca_elem));
    uint64_t *scratch = calloc(2 * (size_t)total, sizeof(uint64_t));
    uint32_t *jidx = calloc(total, sizeof(uint32_t));
    /* hs[i] is the hash of roos[i].Y, recomputed only where Y changes: a
     * hop needs it for the distinguished-point test and again for the
     * next jump, and hashing twice was a third of a Z_p hop. */
    uint64_t *hs = calloc(total, sizeof(uint64_t));
    ca_htab tab;
    if (!J || !jsz || !roos || !Yn || !B || !scratch || !jidx || !hs ||
        ca_htab_init(&tab, 4096) != CA_OK) {
        free(J); free(jsz); free(roos); free(Yn); free(B); free(scratch); free(jidx); free(hs);
        return CA_ERR_NOMEM;
    }
    /* (h >> 32) mod nj without a divide (Lemire; exact for 32-bit values) */
    const uint64_t nj_magic = UINT64_MAX / nj + 1;
    uint64_t ops = 0;
    for (uint32_t j = 0; j < nj; j++) {
        jsz[j] = 1ULL << j;
        ca_group_mul(g, &J[j], base, jsz[j], &ops);
    }
    ca_rng rng;
    ca_rng_seed(&rng, ca_seed_or_random(params->seed));
    /* initial placement: tames around the middle, wilds at target + offset */
    uint64_t mid = lo + width / 2;
    uint64_t spacing = (uint64_t)(mean_target / (double)herd) + 1;
    for (uint32_t i = 0; i < total; i++) {
        roo *r = &roos[i];
        /* spacing >= 1 by construction, so ca_rng_below never sees 0 */
        uint64_t off = (uint64_t)(i / 2) * spacing + ca_rng_below(&rng, spacing);
        if ((i & 1) == 0) {
            r->dist = mid + off;
            ca_group_mul(g, &r->Y, base, r->dist, &ops);
        } else {
            r->dist = off;
            ca_elem t;
            ca_group_mul(g, &t, base, off, &ops);
            ca_group_op(g, &r->Y, target, &t);
            ops++;
        }
        r->since_dp = 0;
    }
    for (uint32_t i = 0; i < total; i++) hs[i] = ca_group_hash(g, &roos[i].Y);
    rc = CA_ERR_INTERNAL;
    uint64_t abandon = (uint64_t)32 << dp;
    uint64_t dps = 0, restarts = 0;
    int running = 1;
    while (running) {
        for (uint32_t i = 0; i < total; i++) {
            jidx[i] = (uint32_t)(((ca_u128)(nj_magic * (hs[i] >> 32)) * nj) >> 64);
            B[i] = J[jidx[i]];
            Yn[i] = roos[i].Y;
        }
        ca_group_batch_op(g, Yn, Yn, B, total, scratch);
        ops += total;
        for (uint32_t i = 0; i < total; i++) {
            roo *r = &roos[i];
            r->Y = Yn[i];
            r->dist += jsz[jidx[i]];
            r->since_dp++;
            uint64_t h = ca_group_hash(g, &r->Y);
            hs[i] = h;
            int tame = (i & 1) == 0;
            if ((h & dp_mask) == 0) {
                uint64_t od, otype;
                int ir = ca_htab_insert(&tab, h, r->dist, (uint64_t)tame, &od, &otype);
                dps++;
                r->since_dp = 0;
                if (ir < 0) { rc = CA_ERR_NOMEM; running = 0; break; }
                if (ir == 1) {
                    if (otype == (uint64_t)tame) {
                        /* same herd collided: re-seed this kangaroo */
                        uint64_t off = ca_rng_below(&rng, spacing * herd + 1);
                        if (tame) {
                            r->dist = mid + off;
                            ca_group_mul(g, &r->Y, base, r->dist, &ops);
                        } else {
                            r->dist = off;
                            ca_elem t;
                            ca_group_mul(g, &t, base, off, &ops);
                            ca_group_op(g, &r->Y, target, &t);
                            ops++;
                        }
                        hs[i] = ca_group_hash(g, &r->Y);
                        restarts++;
                    } else {
                        /* tame position T, wild distance D: x = T - D */
                        uint64_t T = tame ? r->dist : od;
                        uint64_t D = tame ? od : r->dist;
                        uint64_t cand = T - D;
                        if (n) cand = (uint64_t)(((ca_i128)T - (ca_i128)D) % (ca_i128)n);
                        if (n && (ca_i128)T - (ca_i128)D < 0) cand = (cand + n) % n;
                        if (ca_verify_log(g, base, target, cand) &&
                            ca_fit_interval_base(g, base, &cand, lo, hi)) {
                            /* The header promises x in [lo, hi].  A verified
                             * logarithm that cannot be shifted into the
                             * interval is not the answer that was asked for,
                             * so keep hopping rather than return it. */
                            *x = cand;
                            rc = CA_OK;
                            running = 0;
                            break;
                        }
                        /* 64-bit fingerprint collision or stale entry: ignore */
                    }
                }
            } else if (r->since_dp > abandon) {
                uint64_t off = ca_rng_below(&rng, spacing * herd + 1);
                if (tame) {
                    r->dist = mid + off;
                    ca_group_mul(g, &r->Y, base, r->dist, &ops);
                } else {
                    r->dist = off;
                    ca_elem t;
                    ca_group_mul(g, &t, base, off, &ops);
                    ca_group_op(g, &r->Y, target, &t);
                    ops++;
                }
                hs[i] = ca_group_hash(g, &r->Y);
                restarts++;
            }
        }
        if (params->max_ops && ops > params->max_ops) { rc = CA_ERR_LIMIT; running = 0; }
    }
    if (st) {
        st->group_ops += ops;
        st->iterations += dps;
        st->collisions += restarts;
        st->table_entries = ca_max_u64(st->table_entries, tab.count);
        st->bytes_peak = ca_max_u64(st->bytes_peak, ca_htab_bytes(&tab));
        st->threads = 1;
        st->seconds += ca_now() - t0;
    }
    ca_htab_free(&tab);
    free(J); free(jsz); free(roos); free(Yn); free(B); free(scratch); free(jidx); free(hs);
    return rc;
}
