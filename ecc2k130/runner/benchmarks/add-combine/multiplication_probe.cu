#include <cuda_runtime.h>
#include <cstdio>
#include <cstdlib>
#include <vector>
#include "/root/ecc2k130/include/packed131.h"
using eccPacked131::P131;
static void checked(cudaError_t e) {if(e!=cudaSuccess){fprintf(stderr,"%s\n",cudaGetErrorString(e));std::exit(1);}}

template<int Mode> __global__ __launch_bounds__(128,4)
void multiplicationProbe(P131 *out,int iterations) {
    unsigned tid=blockIdx.x*blockDim.x+threadIdx.x;
    unsigned s=tid+0x131263u;
    P131 a,b,c;
#pragma unroll
    for(int i=0;i<5;i++) {
        s^=s<<13;s^=s>>17;s^=s<<5;a.v[i]=s;
        s^=s<<13;s^=s>>17;s^=s<<5;b.v[i]=s;
        s^=s<<13;s^=s>>17;s^=s<<5;c.v[i]=s;
    }
    a.v[4]&=7;b.v[4]&=7;c.v[4]&=7;
#pragma unroll 1
    for(int i=0;i<iterations;i++) {
        if constexpr(Mode==0) a=eccPacked131::mul131(a,b);
        if constexpr(Mode==1) a=eccPacked131::mulPolynomial131(a,b);
        if constexpr(Mode==2) {
            auto p=eccPacked131::mulPolynomialPair131(a,b,c);
            a=p.first;c=p.second;
        }
    }
    out[tid]=Mode==2?eccPacked131::add131(a,c):a;
}

template<int Mode> void measure(const cudaDeviceProp &device) {
    int blocks;checked(cudaOccupancyMaxActiveBlocksPerMultiprocessor(&blocks,multiplicationProbe<Mode>,128,0));
    int grid=device.multiProcessorCount*blocks*2,threads=grid*128;
    P131 *out;checked(cudaMalloc(&out,size_t(threads)*sizeof(P131)));
    cudaFuncAttributes attr;checked(cudaFuncGetAttributes(&attr,multiplicationProbe<Mode>));
    multiplicationProbe<Mode><<<grid,128>>>(out,4096);checked(cudaGetLastError());checked(cudaDeviceSynchronize());
    cudaEvent_t start,end;checked(cudaEventCreate(&start));checked(cudaEventCreate(&end));
    const int iterations=131072;
    for(int repeat=0;repeat<5;repeat++) {
        checked(cudaEventRecord(start));
        multiplicationProbe<Mode><<<grid,128>>>(out,iterations);
        checked(cudaGetLastError());checked(cudaEventRecord(end));checked(cudaEventSynchronize(end));
        float ms;checked(cudaEventElapsedTime(&ms,start,end));
        double count=double(threads)*iterations*(Mode==2?2:1);
        printf("{\"mode\":%d,\"repeat\":%d,\"threads\":%d,\"residentBlocks\":%d,\"registers\":%d,\"localBytes\":%zu,\"multiplications\":%.0f,\"milliseconds\":%.6f,\"billionMultiplicationsPerSecond\":%.9f}\n",Mode,repeat,threads,blocks,attr.numRegs,attr.localSizeBytes,count,ms,count/(ms*1e6));
        fflush(stdout);
    }
    std::vector<P131> result(threads);checked(cudaMemcpy(result.data(),out,result.size()*sizeof(P131),cudaMemcpyDeviceToHost));
    unsigned checksum=0;for(auto a:result) for(unsigned x:a.v)checksum^=x;
    printf("checksum mode %d: %08x\n",Mode,checksum);
    checked(cudaEventDestroy(start));checked(cudaEventDestroy(end));checked(cudaFree(out));
}

int main() {
    cudaDeviceProp d;checked(cudaGetDeviceProperties(&d,0));
    printf("device: %s, %d SMs, L2 %d bytes, memory bus %d bits\n",d.name,d.multiProcessorCount,d.l2CacheSize,d.memoryBusWidth);
    puts("COMPONENT BENCHMARK ONLY: field multiplications, CUDA event timing; not walk iterations");
    measure<0>(d);measure<1>(d);measure<2>(d);
}
