/*
 * gpu_emulate.c - host emulation of the CUDA rho kernel.
 *
 * Runs ca_dev_rho_thread for every thread id sequentially over host
 * buffers.  Slow by design (one core, no SIMD), but bit-for-bit the same
 * algorithm as the device build.
 */
#include "gpu_internal.h"
#include "ca_internal.h"

typedef struct emu_ctx {
    ca_gpu_rho_args args;
    uint64_t *mult, *state, *aux, *dp;
    uint8_t *restart;
    uint32_t dp_count;
} emu_ctx;

static ca_status emu_create(const ca_gpu_rho_args *a, uint32_t tpb, int device, void **out)
{
    (void)tpb;
    (void)device;
    emu_ctx *c = calloc(1, sizeof(*c));
    if (!c) return CA_ERR_NOMEM;
    c->args = *a;
    size_t nwalks = (size_t)a->nthreads * CA_GPU_W;
    c->mult = malloc((size_t)a->r * 4 * sizeof(uint64_t));
    c->state = calloc(nwalks * 4, sizeof(uint64_t));
    c->aux = calloc(nwalks * CA_GPU_AUX, sizeof(uint64_t));
    c->dp = calloc((size_t)a->dp_cap * 4, sizeof(uint64_t));
    c->restart = malloc(nwalks);
    if (!c->mult || !c->state || !c->aux || !c->dp || !c->restart) {
        free(c->mult); free(c->state); free(c->aux); free(c->dp); free(c->restart); free(c);
        return CA_ERR_NOMEM;
    }
    memcpy(c->mult, a->mult, (size_t)a->r * 4 * sizeof(uint64_t));
    memset(c->restart, 1, nwalks); /* seed every walk on the first launch */
    c->args.restart = c->restart;
    c->args.mult = c->mult;
    c->args.state = c->state;
    c->args.aux = c->aux;
    c->args.dp_out = c->dp;
    c->args.dp_count = &c->dp_count;
    *out = c;
    return CA_OK;
}

static ca_status emu_launch(void *ctx, const uint64_t **dps, uint32_t *count)
{
    emu_ctx *c = ctx;
    c->dp_count = 0;
    for (uint32_t tid = 0; tid < c->args.nthreads; tid++) ca_dev_rho_thread(&c->args, tid);
    *dps = c->dp;
    *count = c->dp_count < c->args.dp_cap ? c->dp_count : c->args.dp_cap;
    return CA_OK;
}

static void emu_restart(void *ctx, uint32_t wid)
{
    emu_ctx *c = ctx;
    c->restart[wid] = 1;
}

static void emu_destroy(void *ctx)
{
    emu_ctx *c = ctx;
    if (!c) return;
    free(c->mult); free(c->state); free(c->aux); free(c->dp); free(c->restart);
    free(c);
}

const ca_gpu_backend_ops ca_gpu_emulate_ops = {"emulate", emu_create, emu_launch, emu_restart, emu_destroy};
