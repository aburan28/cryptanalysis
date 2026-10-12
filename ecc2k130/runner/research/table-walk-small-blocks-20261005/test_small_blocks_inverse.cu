// Independent Euclidean inverse replay, including zero inputs and partial blocks.
#include <cuda_runtime.h>
#include <array>
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <vector>
#include "../../include/packed131.h"
#include "../../include/collective_inverse.cuh"

using eccPacked131::P131;
using Polynomial=std::array<unsigned long long,5>;
static void checked(cudaError_t status) {
    if(status!=cudaSuccess){std::fprintf(stderr,"collective inverse test: %s\n",cudaGetErrorString(status));std::exit(2);}
}
static int degree(const Polynomial &value) {
    for(int i=4;i>=0;--i)if(value[i])return i*64+63-__builtin_clzll(value[i]);
    return -1;
}
static void xorShift(Polynomial &target,const Polynomial &source,int shift) {
    const int words=shift/64,bits=shift%64;
    for(int i=4;i>=words;--i){
        unsigned long long value=source[i-words]<<bits;
        if(bits && i>words)value^=source[i-words-1]>>(64-bits);
        target[i]^=value;
    }
}
static P131 inverseReference(P131 value) {
    Polynomial modulus{};
    const int terms[]={0,2,3,64,66,67,96,98,99,112,114,115,120,122,123,124,128,130,131};
    for(int term:terms)modulus[term/64]|=1ull<<(term%64);
    Polynomial u{},v=modulus,g1{},g2{};
    for(int i=0;i<5;++i)u[i/2]|=static_cast<unsigned long long>(value.v[i])<<((i%2)*32);
    if(degree(u)<0)return P131{};
    g1[0]=1;
    int iterations=0;
    while(!(u[0]==1 && degree(u)==0)) {
        if(degree(u)<0 || ++iterations>4096){std::fprintf(stderr,"Euclidean reference failed\n");std::exit(3);}
        int shift=degree(u)-degree(v);
        if(shift<0){std::swap(u,v);std::swap(g1,g2);shift=-shift;}
        xorShift(u,v,shift);xorShift(g1,g2,shift);
    }
    while(degree(g1)>=131)xorShift(g1,modulus,degree(g1)-131);
    P131 output{};
    for(int i=0;i<5;++i)output.v[i]=static_cast<unsigned>(g1[i/2]>>((i%2)*32));
    return output;
}
static bool same(P131 a,P131 b) {
    for(int i=0;i<5;++i)if(a.v[i]!=b.v[i])return false;
    return true;
}
__global__ __launch_bounds__(ECC_THREADS,ECC_MINBLOCKS)
void inverseProbe(const P131 *input,P131 *first,P131 *second,int count) {
    int tid=blockIdx.x*blockDim.x+threadIdx.x;
    if(tid>=count)return;
    const P131 inverse=eccPacked131::batchInverse131(input[tid],count);
    first[tid]=inverse;
    second[tid]=eccPacked131::batchInverse131(inverse,count);
}
int main() {
    const int count=87040+17;
    std::vector<P131> input(count),expected(count);
    unsigned state=0x51c0131u;
    for(int i=0;i<count;++i) {
        P131 value{};
        if(i>=1 && i<=131)value.v[(i-1)/32]=1u<<((i-1)%32);
        else if(i>131){
            for(int word=0;word<5;++word){state^=state<<13;state^=state>>17;state^=state<<5;value.v[word]=state;}
            value.v[4]&=7u;
        }
        // Put zeros in different logical tree positions, including root warps.
        if(i>131 && (i%17==0 || i%67==0))value=P131{};
        input[i]=value;expected[i]=inverseReference(value);
    }
    const P131 guard{{0x13579bdfu,0x2468ace0u,0xa5a5a5a5u,0x5a5a5a5au,7u}};
    std::vector<P131> first(count+2,guard),second(count+2,guard);
    P131 *deviceInput,*deviceFirst,*deviceSecond;
    checked(cudaMalloc(&deviceInput,count*sizeof(P131)));
    checked(cudaMalloc(&deviceFirst,(count+2)*sizeof(P131)));
    checked(cudaMalloc(&deviceSecond,(count+2)*sizeof(P131)));
    checked(cudaMemcpy(deviceInput,input.data(),count*sizeof(P131),cudaMemcpyHostToDevice));
    checked(cudaMemcpy(deviceFirst,first.data(),(count+2)*sizeof(P131),cudaMemcpyHostToDevice));
    checked(cudaMemcpy(deviceSecond,second.data(),(count+2)*sizeof(P131),cudaMemcpyHostToDevice));
    inverseProbe<<<(count+ECC_THREADS-1)/ECC_THREADS,ECC_THREADS>>>(deviceInput,deviceFirst+1,deviceSecond+1,count);
    checked(cudaGetLastError());checked(cudaDeviceSynchronize());
    checked(cudaMemcpy(first.data(),deviceFirst,(count+2)*sizeof(P131),cudaMemcpyDeviceToHost));
    checked(cudaMemcpy(second.data(),deviceSecond,(count+2)*sizeof(P131),cudaMemcpyDeviceToHost));
    checked(cudaFree(deviceInput));checked(cudaFree(deviceFirst));checked(cudaFree(deviceSecond));
    for(int i=0;i<count;++i)if(!same(first[i+1],expected[i]) || !same(second[i+1],input[i])){
        std::fprintf(stderr,"collective inverse mismatch at %d\n",i);return 1;
    }
    if(!same(first.front(),guard)||!same(first.back(),guard)||!same(second.front(),guard)||!same(second.back(),guard)){
        std::fprintf(stderr,"collective inverse output guard mismatch\n");return 1;
    }
    std::printf("PASS: %d inverses against independent Euclidean replay; zeros, partial block, repeated shared-scratch use, output guards; collective warps=%d\n",count,ECC_COLLECTIVE_WARPS);
    return 0;
}
