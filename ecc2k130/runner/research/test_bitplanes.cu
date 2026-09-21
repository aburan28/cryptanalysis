#include <cstdio>
#include <vector>
#ifdef __CUDACC__
#include <cuda_runtime.h>
#endif
#include "curveparams.h"
#include "packed131.h"
#include "packedcompactstate.cuh"
using namespace eccPacked131;
ECC_HD P131 valueFor(unsigned id,unsigned phase){
    return P131{{id*7919u+phase,~id^(phase<<5),id*0x9e3779b9u,0xffffffffu-(id^phase),(id+phase)&7u}};
}
#ifdef __CUDACC__
__global__ void writeFields(unsigned *data,int threads,unsigned phase){
    const unsigned id=blockIdx.x*blockDim.x+threadIdx.x;
    if(id<unsigned(threads*ECC_BATCH) && (!phase || id%3==0))
        compactStore131(data,id/threads,id%threads,valueFor(id,phase));
}
__global__ void readFields(const unsigned *data,P131 *out,int threads){
    const unsigned id=blockIdx.x*blockDim.x+threadIdx.x;
    if(id<unsigned(threads*ECC_BATCH))out[id]=compactLoad131(data,id/threads,id%threads);
}
#define CK(x) do{auto e=(x);if(e!=cudaSuccess){std::printf("CUDA failure: %s\n",cudaGetErrorString(e));return 2;}}while(0)
#endif
int main(){
    const int threads=544,count=threads*ECC_BATCH;
    std::vector<unsigned> storage(compactPhysicalFieldWords(threads),0xa5a5a5a5u);
    std::vector<P131> out(count);
#ifdef __CUDACC__
    unsigned *ds;P131 *doo;CK(cudaMalloc(&ds,storage.size()*4));CK(cudaMalloc(&doo,out.size()*sizeof(P131)));
    CK(cudaMemcpy(ds,storage.data(),storage.size()*4,cudaMemcpyHostToDevice));
#endif
    for(unsigned phase=0;phase<2;++phase){
#ifdef __CUDACC__
        writeFields<<<(count+255)/256,256>>>(ds,threads,phase);CK(cudaGetLastError());CK(cudaDeviceSynchronize());
        readFields<<<(count+255)/256,256>>>(ds,doo,threads);CK(cudaGetLastError());CK(cudaDeviceSynchronize());
        CK(cudaMemcpy(out.data(),doo,out.size()*sizeof(P131),cudaMemcpyDeviceToHost));
        CK(cudaMemcpy(storage.data(),ds,storage.size()*4,cudaMemcpyDeviceToHost));
#else
        for(int id=0;id<count;++id)if(!phase || id%3==0)compactStore131(storage.data(),id/threads,id%threads,valueFor(id,phase));
        for(int id=0;id<count;++id)out[id]=compactLoad131(storage.data(),id/threads,id%threads);
#endif
        for(int id=0;id<count;++id){
            const auto expected=valueFor(id,phase && id%3==0 ? 1:0);
            const auto host=compactLoad131(storage.data(),id/threads,id%threads);
            for(int w=0;w<5;++w)if(out[id].v[w]!=expected.v[w] || host.v[w]!=expected.v[w]){
                std::printf("FAIL tail codec phase=%u id=%d word=%d\n",phase,id,w);return 1;
            }
        }
    }
#ifdef __CUDACC__
    // Checkpoint import is the host encoder consumed by the device decoder.
    for(int id=0;id<count;++id)compactStore131(storage.data(),id/threads,id%threads,valueFor(id,2));
    CK(cudaMemcpy(ds,storage.data(),storage.size()*4,cudaMemcpyHostToDevice));
    readFields<<<(count+255)/256,256>>>(ds,doo,threads);CK(cudaGetLastError());CK(cudaDeviceSynchronize());
    CK(cudaMemcpy(out.data(),doo,out.size()*sizeof(P131),cudaMemcpyDeviceToHost));
    for(int id=0;id<count;++id){auto want=valueFor(id,2);for(int w=0;w<5;++w)if(out[id].v[w]!=want.v[w])return 1;}
    CK(cudaFree(ds));CK(cudaFree(doo));
#endif
    std::printf("PASS bitplane tails: %d points, full and partial-warp stores, padded tiles, host/device codec agreement\n",count);
}
