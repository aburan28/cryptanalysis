#include <cuda_runtime.h>
#include "curveparams.h"
#include "packed131.h"
// Select the experimental header in -Iinclude, not the original helper
// mounted beside this test source in /opt.
#include <collective_inverse.cuh>
#if defined(GOAL22_EXPECT_PHASE) && !defined(GOAL22_PHASE_INVERSE)
#error "The phase inverse probe selected the wrong implementation header"
#endif
#include <cstdio>
#include <vector>
using namespace eccPacked131;
using R = Ref<CfgF131>;
#define CK(x) do { cudaError_t e = (x); if(e != cudaSuccess) { \
    std::fprintf(stderr, "%s: %s\n", #x, cudaGetErrorString(e)); return 2; } } while(0)
template<int W> __global__ void probe(const P131 *in, P131 *out) {
    const int tid = blockIdx.x * blockDim.x + threadIdx.x;
    // Two consecutive uses also exercise scratch reuse and synchronization.
    P131 a = in[tid];
#ifdef GOAL22_GROUP_BARRIER_TEST
    const int count = 2 * (1 + (int(threadIdx.x) / (32 * W)) % 3);
#else
    const int count = 2;
#endif
    for (int i=0; i<count; ++i) {
#ifdef GOAL22_PHASE_INVERSE
        a = goal22CollectiveInverse<W>(a, unsigned(i));
#else
        a = goal22CollectiveInverse<W>(a);
#endif
    }
    out[tid] = a;
}
template<int W> __global__ void single(const P131 *in, P131 *out, unsigned phase) {
    const int tid = blockIdx.x * blockDim.x + threadIdx.x;
#ifdef GOAL22_PHASE_INVERSE
    out[tid] = goal22CollectiveInverse<W>(in[tid], phase);
#else
    out[tid] = goal22CollectiveInverse<W>(in[tid]);
#endif
}
template<int W> int check(const std::vector<P131>& input, const std::vector<P131>& expected,
                         P131 *dIn, P131 *dOut) {
    std::vector<P131> output(input.size());
#ifdef GOAL22_PHASE_INVERSE
    constexpr int phases = W;
#else
    constexpr int phases = 1;
#endif
    for (int phase=0;phase<phases;++phase) {
    single<W><<<input.size()/ECC_THREADS, ECC_THREADS>>>(dIn, dOut, phase);
    CK(cudaGetLastError()); CK(cudaDeviceSynchronize());
    CK(cudaMemcpy(output.data(), dOut, input.size()*sizeof(P131), cudaMemcpyDeviceToHost));
    for (size_t j=0;j<input.size();++j) for (int k=0;k<5;++k)
        if(output[j].v[k] != expected[j].v[k]) { std::printf("FAIL inverse W=%d input=%zu word=%d\n",W,j,k);return 1; }
    }
    probe<W><<<input.size()/ECC_THREADS, ECC_THREADS>>>(dIn, dOut);
    CK(cudaGetLastError()); CK(cudaDeviceSynchronize());
    CK(cudaMemcpy(output.data(), dOut, input.size()*sizeof(P131), cudaMemcpyDeviceToHost));
    for (size_t j=0;j<input.size();++j) for (int k=0;k<5;++k)
        if(output[j].v[k] != input[j].v[k]) { std::printf("FAIL scratch reuse W=%d input=%zu word=%d\n",W,j,k);return 1; }
    std::printf("PASS W=%d: %zu independent inverses, %d phases and consecutive-call checks, including zero lanes/blocks\n",W,input.size(),phases);
    return 0;
}
int main() {
    std::vector<P131> input(2*ECC_THREADS), expected(input.size());
    uint32_t rng=131; auto next=[&](){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng;};
    for(size_t j=0;j<input.size();++j) {
        P131 a={{next(),next(),next(),next(),next()&7u}};
        if(j<131){a=P131{};a.v[j/32]=1u<<(j%32);}
        if(j%17==0 || j>=ECC_THREADS) a=P131{};
        input[j]=a;
        const P131 normal=fromPolynomial131(a);
        unsigned long long limbs[3]={normal.v[0]|(uint64_t(normal.v[1])<<32),
            normal.v[2]|(uint64_t(normal.v[3])<<32),normal.v[4]};
        auto ref=R::inv(R::fromLimbs(limbs)); P131 inv;
        for(int k=0;k<5;++k)inv.v[k]=uint32_t(ref.v[k/2]>>(32*(k&1)));
        expected[j]=toPolynomial131(inv);
    }
    P131 *dIn,*dOut; CK(cudaMalloc(&dIn,input.size()*sizeof(P131)));CK(cudaMalloc(&dOut,input.size()*sizeof(P131)));
    CK(cudaMemcpy(dIn,input.data(),input.size()*sizeof(P131),cudaMemcpyHostToDevice));
    int status=check<2>(input,expected,dIn,dOut); if(status)return status;
    status=check<4>(input,expected,dIn,dOut);if(status)return status;
    status=check<8>(input,expected,dIn,dOut);if(status)return status;
    status=check<16>(input,expected,dIn,dOut);if(status)return status;
    CK(cudaFree(dIn)); CK(cudaFree(dOut));
}
