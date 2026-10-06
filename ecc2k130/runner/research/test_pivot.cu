#include <cstdio>
#include <vector>
#ifdef __CUDACC__
#include <cuda_runtime.h>
#endif
#include "curveparams.h"
#include "packed131.h"
#include "tablewalk.h"
namespace eccPacked131 {
#ifdef __CUDACC__
#define TW_FN __device__ __forceinline__
#else
#define TW_FN static inline
#endif
#include "pivot_search.cuh"
#undef TW_FN
}
using namespace eccPacked131;
struct Input { P131 x; int k; };
#ifdef __CUDACC__
__global__ void probe(const Input *in, int *out, size_t n, const uint8_t *linv){
    __shared__ uint8_t table[131];
    if(threadIdx.x<131)table[threadIdx.x]=linv[threadIdx.x];
    __syncthreads();
    const size_t i=blockIdx.x*blockDim.x+threadIdx.x;
    if(i<n)out[i]=goal22PivotSearch(in[i].x,in[i].k,table);
}
#define CK(x) do{auto e=(x);if(e!=cudaSuccess){std::printf("CUDA failure: %s\n",cudaGetErrorString(e));return 2;}}while(0)
#endif
int main(){
    TableWalkConsts<131> c;c.build();
    std::vector<uint8_t> linv(131);
    for(int i=1;i<=131;++i)linv[c.L[i]]=i-1;
    std::vector<Input> in;
    for(int i=0;i<131;++i)for(int k=0;k<131;++k){Input a{};a.x.v[i/32]=1u<<(i%32);a.k=k;in.push_back(a);}
    uint32_t rng=131;auto next=[&](){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng;};
    for(int i=0;i<1000;++i)in.push_back(Input{P131{{next()|1u,next(),next(),next(),next()&7u}},int(next()%131)});
    std::vector<int> out(in.size());
#ifdef __CUDACC__
    Input *di;int *doo;uint8_t *dl;
    CK(cudaMalloc(&di,in.size()*sizeof(Input)));CK(cudaMalloc(&doo,out.size()*sizeof(int)));CK(cudaMalloc(&dl,131));
    CK(cudaMemcpy(di,in.data(),in.size()*sizeof(Input),cudaMemcpyHostToDevice));CK(cudaMemcpy(dl,linv.data(),131,cudaMemcpyHostToDevice));
    probe<<<(in.size()+255)/256,256>>>(di,doo,in.size(),dl);CK(cudaGetLastError());CK(cudaDeviceSynchronize());
    CK(cudaMemcpy(out.data(),doo,out.size()*sizeof(int),cudaMemcpyDeviceToHost));CK(cudaFree(di));CK(cudaFree(doo));CK(cudaFree(dl));
#else
    for(size_t i=0;i<in.size();++i)out[i]=goal22PivotSearch(in[i].x,in[i].k,linv.data());
#endif
    for(size_t i=0;i<in.size();++i){
        const auto &x=in[i].x;
        unsigned long long normal[3]={x.v[0]|(uint64_t(x.v[1])<<32),x.v[2]|(uint64_t(x.v[3])<<32),x.v[4]}, pivot[3];
        c.pivot(normal,in[i].k,pivot);
        int want=-1;
        for(int b=0;b<131;++b)if((pivot[b/64]>>(b%64))&1u)want=b;
        if(out[i]!=want){std::printf("FAIL case=%zu phase=%d got=%d expected=%d\n",i,in[i].k,out[i],want);return 1;}
    }
    std::printf("PASS %zu pivot cases: every basis vector at every phase, 1000 dense vectors; independent bit-plane reference\n",in.size());
}
