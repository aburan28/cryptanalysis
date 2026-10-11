#include <cstdio>
#include <vector>
#ifdef __CUDACC__
#include <cuda_runtime.h>
#endif
#include "curveparams.h"
#include "packed131.h"
#include "mixed_product.h"
using namespace eccPacked131;
struct Input { P131 a,b; };
struct Output { uint32_t v[9]; };
static Output reference(const Input &in) {
    Output r{};
    for(int i=0;i<131;++i)if((in.a.v[i/32]>>(i%32))&1u)
        for(int j=0;j<131;++j)if((in.b.v[j/32]>>(j%32))&1u)
            r.v[(i+j)/32]^=1u<<((i+j)%32);
    return r;
}
#ifdef __CUDACC__
__global__ void probe(const Input *in, Output *out, int count) {
    const int i=blockIdx.x*blockDim.x+threadIdx.x;
    if(i<count)goal22ProductMixed(in[i].a,in[i].b,out[i].v);
}
#define CK(x) do { auto e=(x); if(e!=cudaSuccess){std::printf("CUDA failure: %s\n",cudaGetErrorString(e));return 2;} } while(0)
#endif
int main() {
    std::vector<Input> in;
    for(int i=0;i<131;++i)for(int j=0;j<131;++j){Input p{};p.a.v[i/32]=1u<<(i%32);p.b.v[j/32]=1u<<(j%32);in.push_back(p);}
    uint32_t rng=131; auto next=[&](){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng;};
    for(int k=0;k<1000;++k){Input p;for(int j=0;j<5;++j){p.a.v[j]=next();p.b.v[j]=next();}p.a.v[4]&=7;p.b.v[4]&=7;in.push_back(p);}
    in.push_back(Input{});
    std::vector<Output> out(in.size());
#ifdef __CUDACC__
    Input *di;Output *doo; CK(cudaMalloc(&di,in.size()*sizeof(Input)));CK(cudaMalloc(&doo,out.size()*sizeof(Output)));
    CK(cudaMemcpy(di,in.data(),in.size()*sizeof(Input),cudaMemcpyHostToDevice));
    probe<<<(in.size()+255)/256,256>>>(di,doo,int(in.size()));CK(cudaGetLastError());CK(cudaDeviceSynchronize());
    CK(cudaMemcpy(out.data(),doo,out.size()*sizeof(Output),cudaMemcpyDeviceToHost));CK(cudaFree(di));CK(cudaFree(doo));
#else
    for(size_t i=0;i<in.size();++i)goal22ProductMixed(in[i].a,in[i].b,out[i].v);
#endif
    for(size_t i=0;i<in.size();++i){const auto want=reference(in[i]);for(int j=0;j<9;++j)if(out[i].v[j]!=want.v[j]){std::printf("FAIL product %zu word %d\n",i,j);return 1;}}
    std::printf("PASS %zu mixed products against independent bit convolution\n",in.size());
}
