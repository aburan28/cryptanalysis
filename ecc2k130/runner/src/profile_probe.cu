// Minimal profiler control: one block, 1 KiB of device state, no ECC arithmetic.
#include <cuda_runtime.h>
#include <cstdio>

#define CHECK(call) do { \
    cudaError_t status = (call); \
    if (status != cudaSuccess) { \
        fprintf(stderr, "%s: %s\n", #call, cudaGetErrorString(status)); \
        return 2; \
    } \
} while (0)

__global__ void probeKernel(unsigned *out) {
    const unsigned i = threadIdx.x;
    out[i] = 17u * i + 3u;
}

int main() {
    unsigned *out;
    unsigned host[256];
    CHECK(cudaMalloc(&out, sizeof(host)));
    probeKernel<<<1, 256>>>(out);
    CHECK(cudaGetLastError());
    CHECK(cudaDeviceSynchronize());
    CHECK(cudaMemcpy(host, out, sizeof(host), cudaMemcpyDeviceToHost));
    CHECK(cudaFree(out));
    for (unsigned i = 0; i < 256; ++i) {
        if (host[i] != 17u * i + 3u) {
            fprintf(stderr, "probe output mismatch at %u\n", i);
            return 3;
        }
    }
    puts("PROBE PASS: all 256 output words verified");
    return 0;
}
