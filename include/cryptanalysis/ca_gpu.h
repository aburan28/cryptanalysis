/*
 * ca_gpu.h - GPU (CUDA) Pollard rho.
 *
 * The walk kernel lives in cuda/ca_device.cuh and is compiled for the GPU
 * by nvcc or clang (CMake option CA_CUDA=ON) and, always, for the host as
 * an emulator backend.  The emulator runs the identical kernel body one
 * thread at a time; it exists so that the GPU code path (multipliers,
 * distinguished-point protocol, host-side collision handling, restarts)
 * is tested on machines without a GPU, and it doubles as a reference when
 * debugging a device build.
 *
 * ca_gpu_rho_solve solves x*base == target in a group of known order n,
 * exactly like ca_rho_solve, but with tens of thousands of walks.
 *
 * Statistics: group_ops counts walk steps summed over all walks,
 * iterations counts distinguished points reported, collisions counts walk
 * restarts, threads is the number of device threads (times CA_GPU_W walks
 * each) and `reserved` carries the number of kernel launches.
 */
#ifndef CA_GPU_H
#define CA_GPU_H

#include "ca_group.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef enum ca_gpu_backend {
    CA_GPU_BACKEND_AUTO = 0, /* CUDA if compiled in and a device exists, else emulator */
    CA_GPU_BACKEND_CUDA = 1,
    CA_GPU_BACKEND_EMULATE = 2
} ca_gpu_backend;

typedef struct ca_gpu_rho_params {
    ca_gpu_backend backend;
    int32_t device;             /* CUDA device ordinal */
    uint32_t threads_per_block; /* 0 => 128 */
    uint32_t blocks;            /* 0 => auto from the group size (and the device) */
    uint32_t steps_per_launch;  /* 0 => auto */
    uint32_t r;                 /* adding-walk multipliers, 0 => auto */
    /* Distinguished-point bits; -1 chooses automatically (never above 48).
     * An explicit value is honoured but clamped to 63, and a value anywhere
     * near that makes distinguished points so rare that max_ops should be
     * set, or the search will not terminate in practice. */
    int32_t dp_bits;
    int32_t negation_map; /* 1 => use on curves */
    uint64_t seed;        /* 0 => random */
    uint64_t max_ops;     /* 0 => unlimited */
} ca_gpu_rho_params;

CA_API void ca_gpu_rho_params_default(ca_gpu_rho_params *p);

CA_API ca_status ca_gpu_rho_solve(const ca_group *g, const ca_elem *base, const ca_elem *target,
                                  const ca_gpu_rho_params *params, uint64_t *x, ca_stats *st);

/* 1 if the library was built with the CUDA backend (CA_CUDA=ON). */
CA_API int ca_gpu_cuda_compiled(void);
/* Number of usable CUDA devices (0 when not compiled in or no driver). */
CA_API int ca_gpu_device_count(void);
/* Device name into buf; returns 0 on success. */
CA_API int ca_gpu_device_name(int device, char *buf, size_t len);
/* Name of the backend that the given params would select. */
CA_API const char *ca_gpu_backend_name(ca_gpu_backend b);

#ifdef __cplusplus
}
#endif
#endif /* CA_GPU_H */
