/*
 * fuzz_gpu.c - libFuzzer harness for the GPU Pollard rho driver
 * (src/gpu_rho.c) running on the CPU emulator backend, which executes the
 * very same kernel body as the CUDA build (cuda/ca_device.cuh).
 *
 * This is the harness that matters most for the kernel: the driver turns
 * caller-supplied dp_bits / blocks / threads_per_block / steps_per_launch /
 * r into shift counts, buffer sizes and loop bounds, and out-of-range
 * values have caused undefined behaviour there before.  dp_bits is fuzzed
 * over its whole int32 range on purpose - ca_gpu.h documents that an
 * explicit value is honoured but clamped to 63, so no value may misbehave.
 *
 * Bounding: blocks, threads_per_block and steps_per_launch are capped so
 * the emulator's per-launch work and the DP buffer stay small, and max_ops
 * is always set so the search terminates.
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

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size);

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size)
{
    if (size < 32) return 0;
    fz f = {data, size, 0};

    uint8_t flags = fz_u8(&f);
    /* n >= 4096 is what takes the driver past its brute-force shortcut, so
     * keep the modulus in [2^12, 2^20]. */
    uint8_t bits = 12 + (uint8_t)(fz_u8(&f) % 9);
    uint64_t praw = fz_u64(&f) & ((1ULL << bits) - 1);
    uint64_t ca = fz_u64(&f), cb = fz_u64(&f);
    uint64_t basew = fz_u64(&f);
    uint64_t x0raw = fz_u64(&f);

    int ec = flags & 1;
    ca_group g;
    ca_elem base, target;

    uint64_t p = ca_next_prime(ec ? 4 + praw : 2 + praw);
    if (p == 0) return 0;

    if (ec) {
        int ok = 0;
        for (int t = 0; t < 8 && !ok; t++, cb++) ok = ca_group_ec_init(&g, p, ca, cb, 0) == CA_OK;
        if (!ok) return 0;
        uint64_t n = 0;
        if (ca_ec_count_points(p, g.a, g.b, &n, NULL) != CA_OK || n < 2) return 0;
        uint64_t ea = g.a, eb = g.b;
        if (ca_group_ec_init(&g, p, ea, eb, n) != CA_OK) return 0;
        g.cofactor = 1;
        if (!ca_ec_lift_x(&g, &base, basew)) ca_ec_random_point(&g, &base, basew | 1);
    } else {
        if (ca_group_zp_init(&g, p, 0) != CA_OK) return 0;
        const uint64_t w[4] = {basew, 0, 0, 0};
        if (!ca_group_encode(&g, &base, w)) return 0;
    }
    CHK(ca_group_is_valid(&g, &base));
    uint64_t n = g.order;
    if (n < 2) return 0;

    uint64_t x0 = x0raw % n;
    ca_group_mul(&g, &target, &base, x0, NULL);

    ca_gpu_rho_params gp;
    ca_gpu_rho_params_default(&gp);
    gp.backend = CA_GPU_BACKEND_EMULATE; /* never touch a real device */
    gp.device = (int32_t)fz_u32(&f);
    /* Capped: the emulator allocates ~(blocks*tpb*CA_GPU_W) walk states and
     * runs steps_per_launch steps for each of them on one core. */
    gp.threads_per_block = fz_u32(&f) & 0x1F; /* 0 => 128 (auto) */
    gp.blocks = fz_u32(&f) & 0x1;             /* 0 => auto */
    gp.steps_per_launch = fz_u32(&f) & 0x1F;  /* 0 => auto */
    gp.r = fz_u32(&f) & 0xFF;                 /* 0 => auto */
    gp.dp_bits = (int32_t)fz_u32(&f);         /* documented: clamped to 63 */
    gp.negation_map = (int32_t)(fz_u8(&f) & 1);
    gp.seed = fz_u64(&f) | 1;
    gp.max_ops = 1 + (fz_u64(&f) & 0xFFFu);

    uint64_t x = ~0ULL;
    ca_stats st;
    memset(&st, 0, sizeof(st));
    ca_status rc = ca_gpu_rho_solve(&g, &base, &target, &gp, &x, &st);
    /* Soundness: a reported logarithm must verify. */
    if (rc == CA_OK) {
        ca_elem t;
        ca_group_mul(&g, &t, &base, x, NULL);
        CHK(ca_group_equal(&g, &t, &target));
        CHK(x < n);
    } else {
        CHK(rc == CA_ERR_LIMIT || rc == CA_ERR_NOT_FOUND || rc == CA_ERR_NOMEM ||
            rc == CA_ERR_INTERNAL || rc == CA_ERR_INVALID || rc == CA_ERR_UNSUPPORTED);
    }
    /* The statistics block must stay self-consistent. */
    CHK(st.table_entries <= st.iterations + 1);

    /* The order is a documented precondition; ask for CUDA without one. */
    {
        ca_group g0 = g;
        g0.order = 0;
        uint64_t y;
        ca_gpu_rho_params q = gp;
        CHK(ca_gpu_rho_solve(&g0, &base, &target, &q, &y, NULL) == CA_ERR_INVALID);
        q.backend = CA_GPU_BACKEND_CUDA;
        ca_status crc = ca_gpu_rho_solve(&g, &base, &target, &q, &y, NULL);
        if (!ca_gpu_cuda_compiled()) CHK(crc == CA_ERR_UNSUPPORTED);
    }
    CHK(ca_gpu_backend_name((ca_gpu_backend)(flags % 4)) != NULL);
    CHK(ca_gpu_device_count() >= 0);
    return 0;
}
