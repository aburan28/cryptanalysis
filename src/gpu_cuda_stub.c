/*
 * gpu_cuda_stub.c - CUDA backend placeholders for builds without CA_CUDA.
 */
#include "gpu_internal.h"

static ca_status stub_create(const ca_gpu_rho_args *a, uint32_t tpb, int device, void **ctx)
{
    (void)a; (void)tpb; (void)device; (void)ctx;
    return CA_ERR_UNSUPPORTED;
}
/* NOLINTNEXTLINE(readability-non-const-parameter) signature fixed by ca_gpu_backend_ops */
static ca_status stub_launch(void *ctx, const uint64_t **dps, uint32_t *count)
{
    (void)ctx; (void)dps; (void)count;
    return CA_ERR_UNSUPPORTED;
}
static void stub_restart(void *ctx, uint32_t wid) { (void)ctx; (void)wid; }
static void stub_destroy(void *ctx) { (void)ctx; }

const ca_gpu_backend_ops ca_gpu_cuda_ops = {"cuda (not compiled)", stub_create, stub_launch,
                                            stub_restart, stub_destroy};
int ca_gpu_cuda_device_count_impl(void) { return 0; }
/* NOLINTNEXTLINE(readability-non-const-parameter) signature fixed by the ABI */
int ca_gpu_cuda_device_name_impl(int device, char *buf, size_t len)
{
    (void)device; (void)buf; (void)len;
    return -1;
}
int ca_gpu_cuda_compiled(void) { return 0; }
