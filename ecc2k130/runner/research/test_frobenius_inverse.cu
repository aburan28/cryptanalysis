#include <cstdio>
#include <vector>
#ifdef __CUDACC__
#include <cuda_runtime.h>
#endif
#include "curveparams.h"
#include "packed131.h"
#include "frobenius_inverse.h"
using namespace eccPacked131;
using R = Ref<CfgF131>;
struct Output { P131 inverse, maps[6], square; };
#ifdef __CUDACC__
__global__ void probe(const P131 *in, Output *out, int count) {
    const int i=blockIdx.x*blockDim.x+threadIdx.x;
    if(i>=count)return;
    const P131 a=in[i];
    out[i].inverse=goal22FrobeniusInverse(a);
    out[i].square=squarePolynomial131(a);
    out[i].maps[0]=goal22Frobenius<0>(a); out[i].maps[1]=goal22Frobenius<1>(a);
    out[i].maps[2]=goal22Frobenius<2>(a); out[i].maps[3]=goal22Frobenius<3>(a);
    out[i].maps[4]=goal22Frobenius<4>(a); out[i].maps[5]=goal22Frobenius<5>(a);
}
#define CK(x) do { auto e=(x); if(e!=cudaSuccess){std::printf("CUDA failure: %s\n",cudaGetErrorString(e));return 2;} } while(0)
#endif
int main() {
    std::vector<P131> in(1133);
    uint32_t rng=131; auto next=[&](){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng;};
    for(int i=0;i<int(in.size());++i){
        in[i]=P131{{next(),next(),next(),next(),next()&7u}};
        if(i<131){in[i]=P131{};in[i].v[i/32]=1u<<(i%32);}
        if(i==131)in[i]=P131{};
        if(i==132)in[i]=P131{{~0u,~0u,~0u,~0u,7}};
    }
    std::vector<Output> out(in.size());
#ifdef __CUDACC__
    P131 *di; Output *doo;
    CK(cudaMalloc(&di,in.size()*sizeof(P131)));CK(cudaMalloc(&doo,out.size()*sizeof(Output)));
    CK(cudaMemcpy(di,in.data(),in.size()*sizeof(P131),cudaMemcpyHostToDevice));
    probe<<<(in.size()+255)/256,256>>>(di,doo,int(in.size()));CK(cudaGetLastError());CK(cudaDeviceSynchronize());
    CK(cudaMemcpy(out.data(),doo,out.size()*sizeof(Output),cudaMemcpyDeviceToHost));CK(cudaFree(di));CK(cudaFree(doo));
#else
    for(size_t i=0;i<in.size();++i){const P131 a=in[i];
        out[i].inverse=goal22FrobeniusInverse(a);
        out[i].square=squarePolynomial131(a);
        out[i].maps[0]=goal22Frobenius<0>(a);out[i].maps[1]=goal22Frobenius<1>(a);
        out[i].maps[2]=goal22Frobenius<2>(a);out[i].maps[3]=goal22Frobenius<3>(a);
        out[i].maps[4]=goal22Frobenius<4>(a);out[i].maps[5]=goal22Frobenius<5>(a);
    }
#endif
    const int powers[6]={2,4,8,16,32,65};
    for(size_t i=0;i<in.size();++i){
        const P131 n=fromPolynomial131(in[i]);
        unsigned long long limbs[3]={n.v[0]|(uint64_t(n.v[1])<<32),n.v[2]|(uint64_t(n.v[3])<<32),n.v[4]};
        const auto a=R::fromLimbs(limbs);
        for(int m=-1;m<6;++m){
            auto expected=a;
            if(m<0)expected=R::inv(a);
            else for(int j=0;j<powers[m];++j)expected=R::sqr(expected);
            const P131 got=fromPolynomial131(m<0?out[i].inverse:out[i].maps[m]);
            for(int j=0;j<5;++j)if(got.v[j]!=uint32_t(expected.v[j/2]>>(32*(j&1)))){
                std::printf("FAIL case=%zu map=%d word=%d\n",i,m,j);return 1;
            }
        }
        const auto squared=R::sqr(a);
        const P131 gotSquare=fromPolynomial131(out[i].square);
        for(int j=0;j<5;++j)if(gotSquare.v[j]!=uint32_t(squared.v[j/2]>>(32*(j&1)))){
            std::printf("FAIL polynomial square case=%zu word=%d\n",i,j);return 1;
        }
    }
    std::puts("PASS 1133 inverses, 1133 polynomial squares and 6798 Frobenius maps against independent Ref<CfgF131>");
}
