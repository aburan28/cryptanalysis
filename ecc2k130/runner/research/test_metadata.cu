#include <cstdio>
#include <vector>
#ifdef __CUDACC__
#include <cuda_runtime.h>
#endif
#include "curveparams.h"
#include "packed131.h"
#include "tablewalk.h"
#include "compact_metadata.cuh"
using namespace eccPacked131;
ECC_HD unsigned checkLane(unsigned *flags, unsigned long long *hist, size_t count, size_t id, unsigned phase) {
    unsigned long long full=ECC_HIST_EMPTY;
    goal22WriteHist(hist,id,count,full);
    for(unsigned step=0;step<100;++step){
        const unsigned tag=eccTag((id+step)&7,(id*7+step*11)%131,(id+step)&1);
        const auto compact=goal22ReadHist(hist,id,count);
        if((compact&0xffffffffffffull)!=(full&0xffffffffffffull))return 1;
        if(eccTagFruitless(tag,compact)!=eccTagFruitless(tag,full))return 2;
        full=eccHistPush(full,tag);
        goal22WriteHist(hist,id,count,full);
    }
    goal22WriteDead(flags,id,1);
    goal22WriteDead(flags,id,unsigned(id%(phase?5:3)==0));
    return 0;
}
#ifdef __CUDACC__
__global__ void probe(unsigned *flags, unsigned long long *hist, unsigned *status, size_t count, unsigned phase){
    const size_t id=blockIdx.x*blockDim.x+threadIdx.x;
    if(id<count)status[id]=checkLane(flags,hist,count,id,phase);
}
#define CK(x) do {auto e=(x);if(e!=cudaSuccess){std::printf("CUDA failure: %s\n",cudaGetErrorString(e));return 2;}}while(0)
#endif
int main(){
    const size_t count=1025;
    std::vector<unsigned> flags((goal22DeadBytes(count)+3)/4,0),status(count);
    std::vector<unsigned long long> hist((goal22HistoryBytes(count)+7)/8,0);
#ifdef __CUDACC__
    unsigned *df,*ds;unsigned long long *dh;
    CK(cudaMalloc(&df,flags.size()*4));CK(cudaMalloc(&ds,status.size()*4));CK(cudaMalloc(&dh,hist.size()*8));
    CK(cudaMemset(df,0,flags.size()*4));
#endif
    for(unsigned phase=0;phase<2;++phase){
#ifdef __CUDACC__
        probe<<<(count+255)/256,256>>>(df,dh,ds,count,phase);CK(cudaGetLastError());CK(cudaDeviceSynchronize());
        CK(cudaMemcpy(flags.data(),df,flags.size()*4,cudaMemcpyDeviceToHost));
        CK(cudaMemcpy(status.data(),ds,status.size()*4,cudaMemcpyDeviceToHost));
#else
        for(size_t i=0;i<count;++i)status[i]=checkLane(flags.data(),hist.data(),count,i,phase);
#endif
        for(size_t i=0;i<count;++i)if(status[i] || goal22ReadDead(flags.data(),i)!=unsigned(i%(phase?5:3)==0)){
            std::printf("FAIL metadata phase=%u lane=%zu\n",phase,i);return 1;
        }
    }
#ifdef __CUDACC__
    CK(cudaFree(df));CK(cudaFree(ds));CK(cudaFree(dh));
#endif
    std::printf("PASS compact metadata: 1025 lanes, byte flags=%d, full history=%d, 200 history updates per lane\n", GOAL22_BYTE_DEAD, GOAL22_FULL_HIST);
}
