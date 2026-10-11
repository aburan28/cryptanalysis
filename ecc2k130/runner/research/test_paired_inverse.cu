#include <cstdio>
#include <vector>
#ifdef __CUDACC__
#include <cuda_runtime.h>
#endif
#include "curveparams.h"
#include "packed131.h"
#include "paired_inverse.h"
using namespace eccPacked131;
using R=Ref<CfgF131>;
#ifdef __CUDACC__
__global__ void probe(const P131 *in,Goal22FieldPair *out,int count){
    const int i=blockIdx.x*blockDim.x+threadIdx.x;
    if(i<count)out[i]=goal22PairedInverse({in[i],in[(i+37)%count]});
}
#define CK(x) do{auto e=(x);if(e!=cudaSuccess){std::printf("CUDA failure: %s\n",cudaGetErrorString(e));return 2;}}while(0)
#endif
int main(){
    std::vector<P131> in(1133),expected(1133);
    uint32_t rng=131;auto next=[&](){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng;};
    for(int i=0;i<int(in.size());++i){
        auto &a=in[i];a=P131{{next(),next(),next(),next(),next()&7u}};
        if(i<131){a=P131{};a.v[i/32]=1u<<(i%32);}if(i==131)a=P131{};
        if(i==132)a=P131{{~0u,~0u,~0u,~0u,7u}};
        unsigned long long words[3]={a.v[0]|(uint64_t(a.v[1])<<32),a.v[2]|(uint64_t(a.v[3])<<32),a.v[4]};
        auto want=R::inv(R::fromLimbs(words));for(int w=0;w<5;++w)expected[i].v[w]=uint32_t(want.v[w/2]>>(32*(w&1)));
    }
    std::vector<Goal22FieldPair> out(in.size());
#ifdef __CUDACC__
    P131 *di;Goal22FieldPair *doo;CK(cudaMalloc(&di,in.size()*sizeof(P131)));CK(cudaMalloc(&doo,out.size()*sizeof(Goal22FieldPair)));
    CK(cudaMemcpy(di,in.data(),in.size()*sizeof(P131),cudaMemcpyHostToDevice));
    probe<<<(in.size()+255)/256,256>>>(di,doo,int(in.size()));CK(cudaGetLastError());CK(cudaDeviceSynchronize());
    CK(cudaMemcpy(out.data(),doo,out.size()*sizeof(Goal22FieldPair),cudaMemcpyDeviceToHost));CK(cudaFree(di));CK(cudaFree(doo));
#else
    for(size_t i=0;i<in.size();++i)out[i]=goal22PairedInverse({in[i],in[(i+37)%in.size()]});
#endif
    for(size_t i=0;i<in.size();++i)for(int w=0;w<5;++w)
        if(out[i].first.v[w]!=expected[i].v[w] || out[i].second.v[w]!=expected[(i+37)%in.size()].v[w]){
            std::printf("FAIL paired inverse case=%zu word=%d\n",i,w);return 1;
        }
    std::puts("PASS 2266 paired inverses against independent Ref<CfgF131>, including zero and all basis inputs");
}
