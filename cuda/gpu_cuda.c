/*
 * gpu_cuda.c - host side of the CUDA backend: device memory, uploads,
 * launches through the shim in rho_kernel.cu, and downloading the
 * distinguished points.  Plain C against the CUDA runtime API, so it is
 * compiled with the same warning flags as the rest of the library.
 *
 * This file lives beside the kernel rather than in src/ because it is the
 * only source that needs the CUDA runtime headers: everything in src/ must
 * compile with a plain C compiler, which is what lets the Go and Python
 * bindings build the library from the C sources in src/ without a CUDA
 * install.
 */
#include "../src/gpu_internal.h"
#include "../src/ca_internal.h"

#include <cuda_runtime_api.h>
#include <stdio.h>

/* provided by cuda/rho_kernel.cu */
ca_status ca_gpu_cuda_launch_kernel(const ca_gpu_rho_args *args, unsigned blocks,
                                    unsigned threads_per_block);

typedef struct cuda_ctx {
    ca_gpu_rho_args args; /* with device pointers */
    uint32_t tpb, blocks;
    size_t nwalks;
    uint64_t *d_mult, *d_state, *d_aux, *d_dp;
    uint32_t *d_count;
    uint8_t *d_restart, *h_restart;
    int restart_dirty;
    uint64_t *h_dp;
} cuda_ctx;

static void cuda_destroy(void *vctx);

#define CUDA_TRY(expr)                                                                             \
    do {                                                                                           \
        cudaError_t _e = (expr);                                                                   \
        if (_e != cudaSuccess) {                                                                   \
            ca_set_error("CUDA: %s (%s)", cudaGetErrorString(_e), #expr);                          \
            return CA_ERR_INTERNAL;                                                                \
        }                                                                                          \
    } while (0)

static ca_status cuda_create(const ca_gpu_rho_args *a, uint32_t tpb, int device, void **out)
{
    if (cudaSetDevice(device) != cudaSuccess) {
        ca_set_error("CUDA: cannot select device %d", device);
        return CA_ERR_UNSUPPORTED;
    }
    cuda_ctx *c = calloc(1, sizeof(*c));
    if (!c) return CA_ERR_NOMEM;
    c->args = *a;
    c->tpb = tpb;
    c->blocks = (a->nthreads + tpb - 1) / tpb;
    c->nwalks = (size_t)a->nthreads * CA_GPU_W;
    size_t mult_bytes = (size_t)a->r * 4 * sizeof(uint64_t);
    size_t dp_bytes = (size_t)a->dp_cap * 4 * sizeof(uint64_t);
    c->h_restart = malloc(c->nwalks);
    c->h_dp = malloc(dp_bytes);
    if (!c->h_restart || !c->h_dp) {
        cuda_destroy(c);
        return CA_ERR_NOMEM;
    }
    memset(c->h_restart, 1, c->nwalks); /* seed every walk on the first launch */
    c->restart_dirty = 1;
    cudaError_t e = cudaSuccess;
    if (e == cudaSuccess) e = cudaMalloc((void **)&c->d_mult, mult_bytes);
    if (e == cudaSuccess) e = cudaMalloc((void **)&c->d_state, c->nwalks * 4 * sizeof(uint64_t));
    if (e == cudaSuccess)
        e = cudaMalloc((void **)&c->d_aux, c->nwalks * CA_GPU_AUX * sizeof(uint64_t));
    if (e == cudaSuccess) e = cudaMalloc((void **)&c->d_dp, dp_bytes);
    if (e == cudaSuccess) e = cudaMalloc((void **)&c->d_count, sizeof(uint32_t));
    if (e == cudaSuccess) e = cudaMalloc((void **)&c->d_restart, c->nwalks);
    if (e != cudaSuccess) {
        ca_set_error("CUDA: allocation failed (%s) for %zu walks", cudaGetErrorString(e),
                     c->nwalks);
        cuda_destroy(c);
        return CA_ERR_NOMEM;
    }
    e = cudaMemcpy(c->d_mult, a->mult, mult_bytes, cudaMemcpyHostToDevice);
    if (e == cudaSuccess) e = cudaMemset(c->d_state, 0, c->nwalks * 4 * sizeof(uint64_t));
    if (e == cudaSuccess) e = cudaMemset(c->d_aux, 0, c->nwalks * CA_GPU_AUX * sizeof(uint64_t));
    if (e != cudaSuccess) {
        ca_set_error("CUDA: %s", cudaGetErrorString(e));
        cuda_destroy(c);
        return CA_ERR_INTERNAL;
    }
    c->args.mult = c->d_mult;
    c->args.state = c->d_state;
    c->args.aux = c->d_aux;
    c->args.dp_out = c->d_dp;
    c->args.dp_count = c->d_count;
    c->args.restart = c->d_restart;
    *out = c;
    return CA_OK;
}

static ca_status cuda_launch(void *vctx, const uint64_t **dps, uint32_t *count)
{
    cuda_ctx *c = vctx;
    if (c->restart_dirty) {
        CUDA_TRY(cudaMemcpy(c->d_restart, c->h_restart, c->nwalks, cudaMemcpyHostToDevice));
        memset(c->h_restart, 0, c->nwalks);
        c->restart_dirty = 0;
    }
    CUDA_TRY(cudaMemset(c->d_count, 0, sizeof(uint32_t)));
    ca_status rc = ca_gpu_cuda_launch_kernel(&c->args, c->blocks, c->tpb);
    if (rc != CA_OK) return rc;
    uint32_t n = 0;
    CUDA_TRY(cudaMemcpy(&n, c->d_count, sizeof(uint32_t), cudaMemcpyDeviceToHost));
    if (n > c->args.dp_cap) n = c->args.dp_cap; /* the kernel clamps its writes */
    if (n)
        CUDA_TRY(
            cudaMemcpy(c->h_dp, c->d_dp, (size_t)n * 4 * sizeof(uint64_t), cudaMemcpyDeviceToHost));
    *dps = c->h_dp;
    *count = n;
    return CA_OK;
}

static void cuda_restart(void *vctx, uint32_t wid)
{
    cuda_ctx *c = vctx;
    if ((size_t)wid < c->nwalks) {
        c->h_restart[wid] = 1;
        c->restart_dirty = 1;
    }
}

static void cuda_destroy(void *vctx)
{
    cuda_ctx *c = vctx;
    if (!c) return;
    if (c->d_mult) cudaFree(c->d_mult);
    if (c->d_state) cudaFree(c->d_state);
    if (c->d_aux) cudaFree(c->d_aux);
    if (c->d_dp) cudaFree(c->d_dp);
    if (c->d_count) cudaFree(c->d_count);
    if (c->d_restart) cudaFree(c->d_restart);
    free(c->h_restart);
    free(c->h_dp);
    free(c);
}

const ca_gpu_backend_ops ca_gpu_cuda_ops = {"cuda", cuda_create, cuda_launch, cuda_restart,
                                            cuda_destroy};

int ca_gpu_cuda_compiled(void) { return 1; }

int ca_gpu_cuda_device_count_impl(void)
{
    int n = 0;
    if (cudaGetDeviceCount(&n) != cudaSuccess) return 0;
    return n;
}

int ca_gpu_cuda_device_name_impl(int device, char *buf, size_t len)
{
    struct cudaDeviceProp prop;
    if (cudaGetDeviceProperties(&prop, device) != cudaSuccess) return -1;
    snprintf(buf, len, "%s (sm_%d%d, %d SMs, %.1f GB)", prop.name, prop.major, prop.minor,
             prop.multiProcessorCount, (double)prop.totalGlobalMem / 1e9);
    return 0;
}
