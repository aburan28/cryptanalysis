/*
 * fuzz_ffi.c - libFuzzer harness for the flat ABI in ca_ffi.h, the surface
 * the Rust, Go and Python bindings call.  Bindings hand the library
 * whatever their callers typed, so every entry point here is driven with
 * fuzzed element words and fuzzed options structs.
 *
 * Contracts asserted:
 *   handles     : a NULL context is the only failure mode of ca_ctx_new_*,
 *                 and every context created is freed on every path.
 *   validation  : ca_ctx_validate agrees with what the element entry points
 *                 accept; a rejected element yields CA_ERR_INVALID, never a
 *                 half-written output.
 *   algebra     : op/inv/mul/equal/identity obey the group laws in the
 *                 public (non-Montgomery) word representation.
 *   solvers     : CA_OK => the returned x verifies with ca_ctx_mul.
 *   cheon       : an instance built by ca_ffi_cheon_instance is solved back
 *                 to the same alpha, or fails with a status.
 *   helpers     : ca_ffi_is_prime / next_prime / powmod / invmod /
 *                 factorize agree with the structured API.
 *
 * Same bounding as the other harnesses: moduli at most 20 bits, max_ops
 * always set, dp_bits kept inside the range the library shifts by (see
 * fuzz/README.md and fuzz/crashes/).
 */
#include "cryptanalysis/cryptanalysis.h"

#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#define CHK(cond)                                                                                  \
    do {                                                                                           \
        if (!(cond)) __builtin_trap();                                                             \
    } while (0)

typedef struct {
    const uint8_t *d;
    size_t n, i;
} fz;

static uint8_t fz_u8(fz *f) { return f->i < f->n ? f->d[f->i++] : 0; }
static uint32_t fz_u32(fz *f)
{
    uint32_t v = 0;
    for (int k = 0; k < 4; k++) v |= (uint32_t)fz_u8(f) << (8 * k);
    return v;
}
static uint64_t fz_u64(fz *f)
{
    uint64_t v = 0;
    for (int k = 0; k < 8; k++) v |= (uint64_t)fz_u8(f) << (8 * k);
    return v;
}
static void fz_words(fz *f, uint64_t w[4])
{
    w[0] = fz_u64(f);
    w[1] = fz_u64(f);
    w[2] = (uint64_t)(fz_u8(f) & 1);
    w[3] = 0;
}
static int32_t pick_dp_bits(fz *f)
{
    int32_t dp = (int32_t)fz_u32(f);
#ifndef CA_FUZZ_WILD_PARAMS
    if (dp > 63) dp = dp % 64;
    if (dp < -1) dp = -1;
#endif
    return dp;
}

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size);

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size)
{
    if (size < 48) return 0;
    fz f = {data, size, 0};

    /* The ABI must describe itself correctly, or the bindings mis-read it. */
    CHK(ca_ffi_options_size() == sizeof(ca_ffi_options));
    CHK(ca_ffi_gpu_options_size() == sizeof(ca_ffi_gpu_options));
    CHK(ca_stats_size() == sizeof(ca_stats));
    CHK(ca_ic_params_size() == sizeof(ca_ic_params));
    CHK(ca_ic_stats_size() == sizeof(ca_ic_stats));
    CHK(ca_version() != NULL && ca_last_error() != NULL);

    uint8_t flags = fz_u8(&f);
    uint8_t bits = 4 + (uint8_t)(fz_u8(&f) % 17); /* 4 .. 20 bits */
    uint64_t praw = fz_u64(&f) & ((1ULL << bits) - 1);
    uint64_t ca = fz_u64(&f), cb = fz_u64(&f);
    uint64_t oraw = fz_u64(&f);

    int ec = flags & 1;

    /* Raw parameters first: the constructor must either refuse (NULL) or
     * hand back a context that describes itself consistently. */
    {
        ca_ctx *raw = ec ? ca_ctx_new_ec(praw, ca, cb, oraw) : ca_ctx_new_zp(praw, oraw);
        if (raw) {
            CHK(ca_ctx_kind(raw) == (ec ? 2 : 1));
            CHK(ca_ctx_p(raw) == praw);
            uint64_t id[4];
            CHK(ca_ctx_identity(raw, id) == CA_OK);
            CHK(ca_ctx_validate(raw, id));
            CHK(ca_ctx_is_identity(raw, id));
            ca_ctx_free(raw);
        }
    }

    /* A context that definitely exists, so the deeper paths run. */
    uint64_t p = ca_next_prime(ec ? 4 + praw : 2 + praw);
    if (p == 0) return 0;
    ca_ctx *ctx = NULL;
    uint64_t order = 0;
    if (ec) {
        for (int t = 0; t < 8 && !ctx; t++, cb++) ctx = ca_ctx_new_ec(p, ca, cb, 0);
        if (!ctx) return 0;
        if (ca_ec_order(p, ca_ctx_curve_a(ctx), ca_ctx_curve_b(ctx), &order) != CA_OK ||
            order < 2) {
            ca_ctx_free(ctx);
            return 0;
        }
        ca_ctx_set_order(ctx, order, 1);
        CHK(ca_ctx_order(ctx) == order);
        CHK(ca_ctx_cofactor(ctx) == 1);
    } else {
        ctx = ca_ctx_new_zp(p, 0);
        if (!ctx) return 0;
        order = ca_ctx_order(ctx);
        CHK(order == p - 1);
        CHK(ca_ctx_cofactor(ctx) == 1);
    }
    if (order < 2) {
        ca_ctx_free(ctx);
        return 0;
    }

    /* ---- elements ------------------------------------------------------- */
    uint64_t wa[4], wb[4], out[4], tmp[4], id[4], base[4];
    fz_words(&f, wa);
    fz_words(&f, wb);
    CHK(ca_ctx_identity(ctx, id) == CA_OK);
    CHK(ca_ctx_validate(ctx, id));

    /* validate and the element entry points must agree */
    int va = ca_ctx_validate(ctx, wa);
    int vb = ca_ctx_validate(ctx, wb);
    CHK((ca_ctx_op(ctx, out, wa, wb) == CA_OK) == (va && vb));
    CHK((ca_ctx_inv(ctx, out, wa) == CA_OK) == (va != 0));
    CHK((ca_ctx_mul(ctx, out, wa, fz_u64(&f)) == CA_OK) == (va != 0));
    if (!va) CHK(ca_ctx_is_identity(ctx, wa) == 0);

    /* A base element that certainly exists. */
    if (va) {
        memcpy(base, wa, sizeof(base));
    } else if (ca_ctx_random_element(ctx, base, (fz_u64(&f) | 1)) != CA_OK) {
        ca_ctx_free(ctx);
        return 0;
    }
    CHK(ca_ctx_validate(ctx, base));

    /* group laws through the flat ABI */
    CHK(ca_ctx_op(ctx, out, base, id) == CA_OK);
    CHK(ca_ctx_equal(ctx, out, base));
    CHK(ca_ctx_inv(ctx, tmp, base) == CA_OK);
    CHK(ca_ctx_op(ctx, out, base, tmp) == CA_OK);
    CHK(ca_ctx_is_identity(ctx, out));
    CHK(ca_ctx_mul(ctx, out, base, 0) == CA_OK);
    CHK(ca_ctx_is_identity(ctx, out));
    CHK(ca_ctx_mul(ctx, out, base, 1) == CA_OK);
    CHK(ca_ctx_equal(ctx, out, base));
    CHK(ca_ctx_mul(ctx, out, base, 2) == CA_OK);
    CHK(ca_ctx_op(ctx, tmp, base, base) == CA_OK);
    CHK(ca_ctx_equal(ctx, out, tmp));
    {
        uint64_t eo = 0;
        if (ca_ctx_elem_order(ctx, base, &eo) == CA_OK) {
            CHK(eo != 0 && order % eo == 0);
            CHK(ca_ctx_mul(ctx, out, base, eo) == CA_OK);
            CHK(ca_ctx_is_identity(ctx, out));
        }
    }
    if (ec) {
        uint64_t lift[4];
        if (ca_ctx_lift_x(ctx, lift, fz_u64(&f)) == CA_OK) CHK(ca_ctx_validate(ctx, lift));
    } else {
        /* lift_x is EC-only and must be refused, not misinterpreted */
        uint64_t lift[4];
        CHK(ca_ctx_lift_x(ctx, lift, 3) != CA_OK);
    }

    /* ---- options and solvers -------------------------------------------- */
    uint64_t x0 = fz_u64(&f) % order;
    uint64_t target[4];
    CHK(ca_ctx_mul(ctx, target, base, x0) == CA_OK);

    ca_ffi_options o;
    ca_ffi_options_default(&o);
    o.threads = 1;
    o.seed = fz_u64(&f) | 1;
    o.max_ops = 1 + (fz_u64(&f) & 0xFFFFu);
    o.bsgs_table_size = fz_u64(&f) & 0xFFFu;
    o.rho_r = fz_u32(&f) & 0xFF;
    o.rho_dp_bits = pick_dp_bits(&f);
    o.rho_walks_per_thread = fz_u32(&f) & 0xFF;
    o.rho_negation_map = (int32_t)(fz_u8(&f) & 1);
    o.rho_max_table_entries = fz_u64(&f) & 0xFFFFu;
    o.kangaroo_herd_size = fz_u32(&f) & 0x3FF;
    o.kangaroo_dp_bits = pick_dp_bits(&f);
    o.kangaroo_jumps = fz_u32(&f) & 0x3F;
    o.grumpy_m = fz_u64(&f) & 0xFFFFu;
    o.grumpy_alpha = (double)fz_u8(&f) / 16.0;
    o.solver = (int32_t)(fz_u8(&f) % 6);
    o.bsgs_max_prime = fz_u64(&f) & 0xFFFFFFu;

    uint64_t lo = fz_u64(&f) % order, hi = fz_u64(&f) % order;
    if (hi < lo) {
        uint64_t t = lo;
        lo = hi;
        hi = t;
    }
    if (x0 < lo) lo = x0;
    if (x0 > hi) hi = x0;

    ca_stats st;
    uint64_t x;

    memset(&st, 0, sizeof(st));
    x = ~0ULL;
    if (ca_ffi_bsgs(ctx, base, target, lo, hi, &o, &x, &st) == CA_OK) {
        CHK(ca_ctx_mul(ctx, out, base, x) == CA_OK);
        CHK(ca_ctx_equal(ctx, out, target));
    }
    memset(&st, 0, sizeof(st));
    x = ~0ULL;
    if (ca_ffi_kangaroo(ctx, base, target, lo, hi, &o, &x, &st) == CA_OK) {
        CHK(ca_ctx_mul(ctx, out, base, x) == CA_OK);
        CHK(ca_ctx_equal(ctx, out, target));
    }
    memset(&st, 0, sizeof(st));
    x = ~0ULL;
    if (ca_ffi_grumpy(ctx, base, target, lo, hi, &o, &x, &st) == CA_OK) {
        CHK(ca_ctx_mul(ctx, out, base, x) == CA_OK);
        CHK(ca_ctx_equal(ctx, out, target));
    }
    memset(&st, 0, sizeof(st));
    x = ~0ULL;
    if (ca_ffi_rho(ctx, base, target, &o, &x, &st) == CA_OK) {
        CHK(ca_ctx_mul(ctx, out, base, x) == CA_OK);
        CHK(ca_ctx_equal(ctx, out, target));
    }
    memset(&st, 0, sizeof(st));
    x = ~0ULL;
    if (ca_ffi_dlog(ctx, base, target, &o, &x, &st) == CA_OK) {
        CHK(ca_ctx_mul(ctx, out, base, x) == CA_OK);
        CHK(ca_ctx_equal(ctx, out, target));
    }

    /* an element that is not in the group must be refused by every solver */
    if (!va) {
        uint64_t dummy;
        CHK(ca_ffi_bsgs(ctx, wa, target, lo, hi, &o, &dummy, NULL) == CA_ERR_INVALID);
        CHK(ca_ffi_rho(ctx, base, wa, &o, &dummy, NULL) == CA_ERR_INVALID);
        CHK(ca_last_error() != NULL);
    }

    /* ---- GPU rho through the flat ABI ----------------------------------- */
    if (flags & 2) {
        ca_ffi_gpu_options go;
        ca_ffi_gpu_options_default(&go);
        go.backend = 2; /* emulate */
        go.threads_per_block = fz_u32(&f) & 0x3F;
        go.blocks = fz_u32(&f) & 0x3;
        go.steps_per_launch = fz_u32(&f) & 0x3F;
        go.r = fz_u32(&f) & 0xFF;
        go.dp_bits = (int32_t)fz_u32(&f); /* documented as clamped to 63 */
        go.negation_map = (int32_t)(fz_u8(&f) & 1);
        go.seed = fz_u64(&f) | 1;
        go.max_ops = 1 + (fz_u64(&f) & 0xFFFFu);
        memset(&st, 0, sizeof(st));
        x = ~0ULL;
        if (ca_ffi_gpu_rho(ctx, base, target, &go, &x, &st) == CA_OK) {
            CHK(ca_ctx_mul(ctx, out, base, x) == CA_OK);
            CHK(ca_ctx_equal(ctx, out, target));
        }
        CHK(ca_ffi_gpu_cuda_compiled() == ca_gpu_cuda_compiled());
        CHK(ca_ffi_gpu_device_count() >= 0);
        char name[64];
        (void)ca_ffi_gpu_device_name((int)fz_u32(&f), name, sizeof(name));
    }

    /* ---- Cheon ----------------------------------------------------------- */
    /* Cheon needs a group of prime order, so build the order-q subgroup of
     * (Z/pZ)^* for the largest prime factor q of p-1. */
    if ((flags & 4) && !ec) {
        ca_factorization fac;
        if (ca_factorize(p - 1, &fac) == CA_OK && fac.count) {
            uint64_t q = fac.f[fac.count - 1].p;
            ca_ctx *cc = ca_ctx_new_zp(p, q);
            if (cc) {
                uint64_t gen[4];
                if (ca_ctx_find_generator(cc, gen, fz_u64(&f) | 1) == CA_OK) {
                    CHK(ca_ctx_validate(cc, gen));
                    double cost = 0;
                    uint64_t best = ca_ffi_cheon_best_divisor(q, &cost);
                    uint64_t dd = (flags & 8) ? best : (fz_u64(&f) % q) + 1;
                    uint64_t alpha = 1 + (fz_u64(&f) % (q > 1 ? q - 1 : 1));
                    uint64_t ga[4], gad[4], got = 0;
                    if (dd && (q - 1) % dd == 0 &&
                        ca_ffi_cheon_instance(cc, gen, alpha, dd, ga, gad) == CA_OK) {
                        CHK(ca_ctx_validate(cc, ga));
                        CHK(ca_ctx_validate(cc, gad));
                        memset(&st, 0, sizeof(st));
                        int rc = ca_ffi_cheon(cc, gen, ga, gad, dd, 1u << 14, &got, &st);
                        if (rc == CA_OK) {
                            /* the recovered alpha must reproduce g^alpha */
                            uint64_t chk[4];
                            CHK(ca_ctx_mul(cc, chk, gen, got) == CA_OK);
                            CHK(ca_ctx_equal(cc, chk, ga));
                        }
                    }
                }
                ca_ctx_free(cc);
            }
        }
    }

    ca_ctx_free(ctx);

    /* ---- number-theory helpers must match the structured API ------------- */
    {
        uint64_t nn = fz_u64(&f);
        CHK(ca_ffi_is_prime(nn) == ca_is_prime(nn));
        uint64_t small = nn & 0xFFFFFFu;
        CHK(ca_ffi_next_prime(small) == ca_next_prime(small));
        uint64_t mm = (nn & 0xFFFFFFu) | 1u;
        if (mm > 1) {
            CHK(ca_ffi_powmod(nn, small, mm) == ca_powmod(nn, small, mm));
            CHK(ca_ffi_invmod(nn, mm) == ca_invmod(nn, mm));
            if (ca_is_prime(mm)) CHK(ca_ffi_primitive_root(mm) == ca_primitive_root(mm));
        }
        uint64_t primes[CA_MAX_FACTORS];
        unsigned exps[CA_MAX_FACTORS];
        unsigned cap = (unsigned)(fz_u8(&f) % (CA_MAX_FACTORS + 1));
        unsigned cnt = ca_ffi_factorize(small, primes, exps, cap);
        CHK(cnt <= CA_MAX_FACTORS);
        for (unsigned i = 0; i < cnt && i < cap; i++) {
            CHK(ca_is_prime(primes[i]));
            CHK(exps[i] >= 1);
        }
    }
    ca_ctx_free(NULL); /* documented no-op */
    return 0;
}
