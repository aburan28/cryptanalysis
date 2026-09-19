/*
 * rho_kernel.cu - the CUDA kernel for ca_gpu_rho_solve.
 *
 * This translation unit holds device code only: the __global__ entry point
 * (whose body is ca_dev_rho_thread from ca_device.cuh, the same code the
 * host emulator runs) and one C-callable launch shim, because the <<<>>>
 * syntax needs a CUDA compiler.  All resource management lives in
 * src/gpu_cuda.c so that this file compiles with --cuda-device-only.
 *
 * Built by nvcc, or by clang -x cuda, when CMake is configured with
 * -DCA_CUDA=ON.
 */
#include <cuda_runtime.h>

extern "C" {
#include "cryptanalysis/ca_types.h"
#include "ca_device.cuh"
void ca_set_error(const char *fmt, ...);
}

/*
 * One thread owns CA_GPU_W independent walks and shares a single field
 * inversion between them (Montgomery's trick), which is what makes affine
 * curve arithmetic worthwhile on a GPU: the inversion is a 64-step
 * exponentiation, so amortising it over 8 walks cuts the cost per walk
 * step by roughly an order of magnitude.  args is passed by value: it is
 * 128 bytes of read-mostly scalars plus device pointers, so it lands in
 * constant/parameter memory and needs no extra transfer per launch.
 */
__global__ void ca_rho_walk_kernel(ca_gpu_rho_args args)
{
    uint32_t tid = blockIdx.x * blockDim.x + threadIdx.x;
    ca_dev_rho_thread(&args, tid);
}

extern "C" ca_status ca_gpu_cuda_launch_kernel(const ca_gpu_rho_args *args, unsigned blocks,
                                               unsigned threads_per_block)
{
    ca_rho_walk_kernel<<<blocks, threads_per_block>>>(*args);
    cudaError_t e = cudaGetLastError();
    if (e == cudaSuccess) e = cudaDeviceSynchronize();
    if (e != cudaSuccess) {
        ca_set_error("CUDA kernel: %s", cudaGetErrorString(e));
        return CA_ERR_INTERNAL;
    }
    return CA_OK;
}
