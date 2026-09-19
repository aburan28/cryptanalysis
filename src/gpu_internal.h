/*
 * gpu_internal.h - backend interface between the generic GPU rho driver
 * (gpu_rho.c) and the CUDA / emulator backends.
 */
#ifndef CA_GPU_INTERNAL_H
#define CA_GPU_INTERNAL_H

#include "cryptanalysis/ca_gpu.h"
#include "../cuda/ca_device.cuh"

typedef struct ca_gpu_backend_ops {
    const char *name;
    /* Allocate device resources for args (host pointers in args->mult
     * point at host memory; the backend copies them where it needs them).
     * nwalks = args->nthreads * CA_GPU_W. */
    ca_status (*create)(const ca_gpu_rho_args *args, uint32_t threads_per_block, int device,
                        void **ctx);
    /* Run one launch of args->steps steps for every thread; afterwards
     * *dps points to a host buffer with *count DP records (4 words each,
     * clamped to dp_cap) valid until the next call. */
    ca_status (*launch)(void *ctx, const uint64_t **dps, uint32_t *count);
    /* Ask the backend to re-seed walk `wid` at the start of the next launch. */
    void (*restart)(void *ctx, uint32_t wid);
    void (*destroy)(void *ctx);
} ca_gpu_backend_ops;

extern const ca_gpu_backend_ops ca_gpu_emulate_ops;
/* Provided by cuda/rho_kernel.cu when CA_CUDA is on, by gpu_cuda_stub.c otherwise. */
extern const ca_gpu_backend_ops ca_gpu_cuda_ops;
int ca_gpu_cuda_device_count_impl(void);
int ca_gpu_cuda_device_name_impl(int device, char *buf, size_t len);

#endif
