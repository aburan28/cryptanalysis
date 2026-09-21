// A tiny independent workload to separate profiler setup failures from walk code.
#include <cuda_runtime.h>
#include <cuda_profiler_api.h>
#include <cstdio>
#include <vector>
#define CHECK(call) do { auto err=(call); if(err!=cudaSuccess) { \
    std::fprintf(stderr,"CUDA smoke error: %s\n",cudaGetErrorString(err)); return 2; } } while(0)
__global__ void profilerSmoke(unsigned *output) {
    unsigned tid=blockIdx.x*blockDim.x+threadIdx.x, value=tid;
#pragma unroll 1
    for(int i=0;i<1024;++i)value=1664525u*value+1013904223u;
    output[tid]=value;
}
int main() {
    unsigned *device=nullptr;
    CHECK(cudaMalloc(&device,4096*sizeof(unsigned)));
    CHECK(cudaProfilerStart());
    profilerSmoke<<<32,128>>>(device);
    CHECK(cudaGetLastError()); CHECK(cudaDeviceSynchronize());
    CHECK(cudaProfilerStop());
    std::vector<unsigned> host(4096);
    CHECK(cudaMemcpy(host.data(),device,host.size()*sizeof(unsigned),cudaMemcpyDeviceToHost));
    CHECK(cudaFree(device));
    for(unsigned i=0;i<host.size();++i) {
        unsigned expected=i;
        for(int j=0;j<1024;++j)expected=1664525u*expected+1013904223u;
        if(host[i]!=expected)return 3;
    }
    std::puts("PASS: 4096 independent profiler smoke results");
}
