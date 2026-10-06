#include <cuda_runtime.h>
#include <cstdio>
#include <cstdlib>
#include <vector>
#include "../include/packed131.h"

using eccPacked131::P131;
static void checked(cudaError_t status) {
    if (status != cudaSuccess) {
        fprintf(stderr, "CUDA arithmetic test: %s\n", cudaGetErrorString(status));
        std::exit(1);
    }
}

__global__ __launch_bounds__(ECC_THREADS, ECC_MINBLOCKS)
void frobeniusProbe(const P131 *input, const int *powers, P131 *output, int n) {
    int i = blockIdx.x*blockDim.x+threadIdx.x;
    if (i < n) output[i] = eccPacked131::sigma131(input[i], powers[i]);
}

static P131 expected(P131 a, int power) {
    unsigned factor = 1;
    for (int i=0;i<power;i++) factor = (2*factor)%263;
    P131 out{};
    for (int i=0;i<131;i++) if ((a.v[i/32]>>(i%32))&1u) {
        unsigned j = ((i+1)*factor)%263;
        if (j>131) j=263-j;
        --j;
        out.v[j/32] ^= 1u<<(j%32);
    }
    return out;
}

struct RawPolynomial { uint32_t v[9]; };

static P131 reduceReference(RawPolynomial h) {
    // Long division, independent of either generated reduction network.
    // The nine-word interface ignores bits above the degree-260 boundary.
    h.v[8]&=31u;
    const int terms[]={0,2,3,64,66,67,96,98,99,112,114,115,120,122,123,124,128,130,131};
    for (int degree=260;degree>=131;--degree) if ((h.v[degree/32]>>(degree%32))&1u) {
        for (int term:terms) {
            int bit=degree-131+term;
            h.v[bit/32]^=1u<<(bit%32);
        }
    }
    return P131{{h.v[0],h.v[1],h.v[2],h.v[3],h.v[4]&7u}};
}

static P131 multiplyReference(P131 a, P131 b) {
    RawPolynomial h{};
    for (int i=0;i<131;i++) if ((a.v[i/32]>>(i%32))&1u)
        for (int j=0;j<131;j++) if ((b.v[j/32]>>(j%32))&1u)
            h.v[(i+j)/32]^=1u<<((i+j)%32);
    return reduceReference(h);
}

__global__ __launch_bounds__(ECC_THREADS, ECC_MINBLOCKS)
void reductionProbe(const RawPolynomial *input, P131 *output, int n) {
    int i=blockIdx.x*blockDim.x+threadIdx.x;
    if (i<n) output[i]=eccPacked131::reducePolynomial131(input[i].v);
}

__global__ __launch_bounds__(ECC_THREADS, ECC_MINBLOCKS)
void multiplicationProbe(const P131 *a, const P131 *b, P131 *output, int n) {
    int i=blockIdx.x*blockDim.x+threadIdx.x;
    if (i<n) output[i]=eccPacked131::mulPolynomial131(a[i],b[i]);
}

__global__ __launch_bounds__(ECC_THREADS, ECC_MINBLOCKS)
void squareProbe(const P131 *input, P131 *output, int n) {
    int i=blockIdx.x*blockDim.x+threadIdx.x;
    if (i<n) output[i]=eccPacked131::squarePolynomial131(input[i]);
}

__global__ __launch_bounds__(ECC_THREADS, ECC_MINBLOCKS)
void pairedProbe(const P131 *a,const P131 *b,const P131 *c,P131 *first,P131 *second,int n) {
    int i=blockIdx.x*blockDim.x+threadIdx.x;
    if(i<n) {
        auto pair=eccPacked131::mulPolynomialPair131(a[i],b[i],c[i]);
        first[i]=pair.first;second[i]=pair.second;
    }
}

static bool same(P131 a, P131 b) {
    // Compare all five words so noncanonical output bits cannot be hidden by
    // the basis conversions used elsewhere in the arithmetic tests.
    for (int i=0;i<5;i++) if (a.v[i]!=b.v[i]) return false;
    return (a.v[4]&~7u)==0;
}

__global__ __launch_bounds__(ECC_THREADS, ECC_MINBLOCKS)
void pairedFrobeniusProbe(const P131 *a, const P131 *b, const int *powers,
                          P131 *first, P131 *second, int n) {
    const int i=blockIdx.x*blockDim.x+threadIdx.x;
    if (i<n) {
#if ECC_PACKED_WEIGHTED_PREFIX == 2
        const auto pair=eccPacked131::sigmaWalkNetworkPair131(a[i],b[i],powers[i]-3);
        first[i]=pair.first;second[i]=pair.second;
#else
        first[i]=eccPacked131::sigma131(a[i],powers[i]);
        second[i]=eccPacked131::sigma131(b[i],powers[i]);
#endif
    }
}

static bool pairedFrobeniusChecks() {
    std::vector<P131> a,b;
    std::vector<int> powers;
    auto append=[&](P131 x,P131 y,int power) {
        a.push_back(x);b.push_back(y);powers.push_back(power);
    };
    uint32_t state=0x5349474du;
    auto random=[&]() { state^=state<<13;state^=state>>17;state^=state<<5;return state; };
    const P131 zero{},full{{~0u,~0u,~0u,~0u,7u}};
    const P131 even{{0x55555555u,0x55555555u,0x55555555u,0x55555555u,5u}};
    const P131 odd{{0xaaaaaaaau,0xaaaaaaaau,0xaaaaaaaau,0xaaaaaaaau,2u}};
    for (int power=3;power<=10;power++) {
        for (int bit=0;bit<131;bit++) {
            P131 basis{};basis.v[bit/32]=1u<<(bit%32);
            append(basis,zero,power);append(zero,basis,power);
        }
        for (int i=0;i<512;i++) {
            P131 x,y;
            for (int word=0;word<5;word++) { x.v[word]=random();y.v[word]=random(); }
            x.v[4]&=7u;y.v[4]&=7u;append(x,y,power);
        }
        append(zero,zero,power);append(full,full,power);
        append(full,zero,power);append(zero,full,power);
        append(even,odd,power);
        append(P131{{0,0,0,0,4u}},P131{{1u,0,0,0,0}},power);
    }
    const int n=int(a.size());
    if (n!=6240 || b.size()!=a.size() || powers.size()!=a.size()) {
        fprintf(stderr,"GPU paired Frobenius fixture count mismatch\n");return false;
    }
    const int padded=((n+ECC_THREADS-1)/ECC_THREADS)*ECC_THREADS;
    const P131 guardFirst{{0x53a7c219u,0x6c15e8b3u,0xa6d2047fu,0x1938fb65u,0xd74192acu}};
    const P131 guardSecond{{0x8e3165a7u,0xf4029c68u,0x271db593u,0xb68a30e4u,0x5ad7c219u}};
    std::vector<P131> first(padded+2,guardFirst),second(padded+2,guardSecond),wantFirst(n),wantSecond(n);
    for (int i=0;i<n;i++) {
        wantFirst[i]=expected(a[i],powers[i]);wantSecond[i]=expected(b[i],powers[i]);
        // A missing store must fail even when the expected result is zero.
        for (int word=0;word<5;word++) {
            first[i+1].v[word]=~wantFirst[i].v[word];
            second[i+1].v[word]=~wantSecond[i].v[word];
        }
    }
    a.resize(padded);b.resize(padded);powers.resize(padded,3);
    P131 *deviceA,*deviceB,*deviceFirst,*deviceSecond;int *devicePowers;
    const size_t inputBytes=size_t(padded)*sizeof(P131),outputBytes=size_t(padded+2)*sizeof(P131);
    checked(cudaMalloc(&deviceA,inputBytes));checked(cudaMalloc(&deviceB,inputBytes));
    checked(cudaMalloc(&deviceFirst,outputBytes));checked(cudaMalloc(&deviceSecond,outputBytes));
    checked(cudaMalloc(&devicePowers,size_t(padded)*sizeof(int)));
    checked(cudaMemcpy(deviceA,a.data(),inputBytes,cudaMemcpyHostToDevice));
    checked(cudaMemcpy(deviceB,b.data(),inputBytes,cudaMemcpyHostToDevice));
    checked(cudaMemcpy(devicePowers,powers.data(),size_t(padded)*sizeof(int),cudaMemcpyHostToDevice));
    checked(cudaMemcpy(deviceFirst,first.data(),outputBytes,cudaMemcpyHostToDevice));
    checked(cudaMemcpy(deviceSecond,second.data(),outputBytes,cudaMemcpyHostToDevice));
    pairedFrobeniusProbe<<<padded/ECC_THREADS,ECC_THREADS>>>(deviceA,deviceB,devicePowers,deviceFirst+1,deviceSecond+1,n);
    checked(cudaGetLastError());checked(cudaDeviceSynchronize());
    checked(cudaMemcpy(first.data(),deviceFirst,outputBytes,cudaMemcpyDeviceToHost));
    checked(cudaMemcpy(second.data(),deviceSecond,outputBytes,cudaMemcpyDeviceToHost));
    checked(cudaFree(deviceA));checked(cudaFree(deviceB));checked(cudaFree(devicePowers));
    checked(cudaFree(deviceFirst));checked(cudaFree(deviceSecond));
    for (int i=0;i<n;i++) if (!same(first[i+1],wantFirst[i]) || !same(second[i+1],wantSecond[i])) {
        fprintf(stderr,"GPU paired Frobenius mismatch at %d, power %d\n",i,powers[i]);return false;
    }
    for (int i=0;i<padded+2;i++) if (i==0 || i>n) {
        for (int word=0;word<5;word++) if (first[i].v[word]!=guardFirst.v[word] || second[i].v[word]!=guardSecond.v[word]) {
            fprintf(stderr,"GPU paired Frobenius output guard mismatch at %d, word %d\n",i,word);return false;
        }
    }
    printf("PASS: 6240 GPU paired Frobenius vectors, both inputs against independent routing\n");
    return true;
}

static bool squareChecks() {
    // Exercise every coefficient, including the three bits in the top word,
    // independently of the coefficient-spreading implementation under test.
    std::vector<P131> input(1); // Zero must remain zero.
    for (int bit=0;bit<131;bit++) {
        P131 a{};a.v[bit/32]=1u<<(bit%32);input.push_back(a);
    }
    input.push_back(P131{{~0u,~0u,~0u,~0u,7u}});
    uint32_t state=0x5131263u;
    for (int i=0;i<1024;i++) {
        P131 a;
        for (int word=0;word<5;word++) {
            state^=state<<13;state^=state>>17;state^=state<<5;
            a.v[word]=state;
        }
        a.v[4]&=7u;input.push_back(a);
    }
    int n=int(input.size());std::vector<P131> output(n);
    P131 *deviceInput,*deviceOutput;
    checked(cudaMalloc(&deviceInput,n*sizeof(P131)));
    checked(cudaMalloc(&deviceOutput,n*sizeof(P131)));
    checked(cudaMemcpy(deviceInput,input.data(),n*sizeof(P131),cudaMemcpyHostToDevice));
    squareProbe<<<(n+ECC_THREADS-1)/ECC_THREADS,ECC_THREADS>>>(deviceInput,deviceOutput,n);
    checked(cudaGetLastError());checked(cudaDeviceSynchronize());
    checked(cudaMemcpy(output.data(),deviceOutput,n*sizeof(P131),cudaMemcpyDeviceToHost));
    checked(cudaFree(deviceInput));checked(cudaFree(deviceOutput));
    for (int i=0;i<n;i++) if (!same(output[i],multiplyReference(input[i],input[i]))) {
        fprintf(stderr,"GPU polynomial square mismatch at %d\n",i);return false;
    }
    printf("PASS: %d GPU polynomial squares against independent multiplication and long division\n",n);
    return true;
}

static bool polynomialChecks() {
    uint32_t state=0x261131u;
    auto random=[&]() { state^=state<<13;state^=state>>17;state^=state<<5;return state; };
    std::vector<RawPolynomial> raw;
    for (int bit=0;bit<261;bit++) {
        RawPolynomial h{};h.v[bit/32]=1u<<(bit%32);raw.push_back(h);
    }
    for (int i=0;i<1000;i++) {
        RawPolynomial h;for (int j=0;j<9;j++) h.v[j]=random();h.v[8]&=31;raw.push_back(h);
    }
    raw.push_back(RawPolynomial{});
    RawPolynomial full;for (auto &word:full.v) word=~0u;full.v[8]=31u;raw.push_back(full);
    const size_t bounded=raw.size();
    for (size_t i=0;i<bounded;i++) {
        RawPolynomial poisoned=raw[i];poisoned.v[8]|=0xffffffe0u;raw.push_back(poisoned);
    }
    int n=int(raw.size());std::vector<P131> output(n);
    RawPolynomial *deviceRaw;P131 *deviceOutput;
    checked(cudaMalloc(&deviceRaw,n*sizeof(RawPolynomial)));
    checked(cudaMalloc(&deviceOutput,n*sizeof(P131)));
    checked(cudaMemcpy(deviceRaw,raw.data(),n*sizeof(RawPolynomial),cudaMemcpyHostToDevice));
    reductionProbe<<<(n+ECC_THREADS-1)/ECC_THREADS,ECC_THREADS>>>(deviceRaw,deviceOutput,n);
    checked(cudaGetLastError());checked(cudaDeviceSynchronize());
    checked(cudaMemcpy(output.data(),deviceOutput,n*sizeof(P131),cudaMemcpyDeviceToHost));
    checked(cudaFree(deviceRaw));checked(cudaFree(deviceOutput));
    for (int i=0;i<n;i++) if (!same(output[i],reduceReference(raw[i]))) {
        fprintf(stderr,"GPU polynomial reduction mismatch at %d\n",i);return false;
    }
    printf("PASS: %d GPU polynomial reductions against long division, including ignored upper-word bits and canonical outputs\n",n);

    std::vector<P131> a,b;
    for (int i=0;i<131;i++) for (int j=0;j<131;j++) {
        P131 x{},y{};x.v[i/32]=1u<<(i%32);y.v[j/32]=1u<<(j%32);a.push_back(x);b.push_back(y);
    }
    for (int i=0;i<1024;i++) {
        P131 x,y;for (int j=0;j<5;j++) {x.v[j]=random();y.v[j]=random();}
        x.v[4]&=7;y.v[4]&=7;a.push_back(x);b.push_back(y);
    }
    const P131 edges[]={P131{},P131{{1,0,0,0,0}},P131{{~0u,~0u,~0u,~0u,7u}}};
    for (P131 x:edges) for (P131 y:edges) { a.push_back(x);b.push_back(y); }
    n=int(a.size());output.resize(n);P131 *deviceA,*deviceB;
    checked(cudaMalloc(&deviceA,n*sizeof(P131)));checked(cudaMalloc(&deviceB,n*sizeof(P131)));
    checked(cudaMalloc(&deviceOutput,n*sizeof(P131)));
    checked(cudaMemcpy(deviceA,a.data(),n*sizeof(P131),cudaMemcpyHostToDevice));
    checked(cudaMemcpy(deviceB,b.data(),n*sizeof(P131),cudaMemcpyHostToDevice));
    multiplicationProbe<<<(n+ECC_THREADS-1)/ECC_THREADS,ECC_THREADS>>>(deviceA,deviceB,deviceOutput,n);
    checked(cudaGetLastError());checked(cudaDeviceSynchronize());
    checked(cudaMemcpy(output.data(),deviceOutput,n*sizeof(P131),cudaMemcpyDeviceToHost));
    checked(cudaFree(deviceA));checked(cudaFree(deviceB));checked(cudaFree(deviceOutput));
    for (int i=0;i<n;i++) if (!same(output[i],multiplyReference(a[i],b[i]))) {
        fprintf(stderr,"GPU polynomial multiplication mismatch at %d\n",i);return false;
    }
    printf("PASS: %d GPU polynomial products, including all 17161 basis pairs\n",n);

    std::vector<P131> c(n),second(n);
    for(int i=0;i<n;i++) {
        c[i].v[0]=(b[i].v[0]<<1)|(b[i].v[4]>>2);
        for(int j=1;j<5;j++) c[i].v[j]=(b[i].v[j]<<1)|(b[i].v[j-1]>>31);
        c[i].v[4]&=7;
    }
    P131 *deviceC,*deviceSecond;
    checked(cudaMalloc(&deviceA,n*sizeof(P131)));checked(cudaMalloc(&deviceB,n*sizeof(P131)));
    checked(cudaMalloc(&deviceC,n*sizeof(P131)));checked(cudaMalloc(&deviceOutput,n*sizeof(P131)));
    checked(cudaMalloc(&deviceSecond,n*sizeof(P131)));
    checked(cudaMemcpy(deviceA,a.data(),n*sizeof(P131),cudaMemcpyHostToDevice));
    checked(cudaMemcpy(deviceB,b.data(),n*sizeof(P131),cudaMemcpyHostToDevice));
    checked(cudaMemcpy(deviceC,c.data(),n*sizeof(P131),cudaMemcpyHostToDevice));
    pairedProbe<<<(n+ECC_THREADS-1)/ECC_THREADS,ECC_THREADS>>>(deviceA,deviceB,deviceC,deviceOutput,deviceSecond,n);
    checked(cudaGetLastError());checked(cudaDeviceSynchronize());
    checked(cudaMemcpy(output.data(),deviceOutput,n*sizeof(P131),cudaMemcpyDeviceToHost));
    checked(cudaMemcpy(second.data(),deviceSecond,n*sizeof(P131),cudaMemcpyDeviceToHost));
    checked(cudaFree(deviceA));checked(cudaFree(deviceB));checked(cudaFree(deviceC));
    checked(cudaFree(deviceOutput));checked(cudaFree(deviceSecond));
    for(int i=0;i<n;i++) if(!same(output[i],multiplyReference(a[i],b[i])) || !same(second[i],multiplyReference(a[i],c[i]))) {
        fprintf(stderr,"GPU paired multiplication mismatch at %d\n",i);return false;
    }
    printf("PASS: %d GPU paired polynomial products against independent multiplication\n",n);
    return true;
}

int main() {
    printf("packed arithmetic direct reduction: %d\n",ECC_PACKED_DIRECT_REDUCE);
    printf("packed arithmetic generated product: %d\n",ECC_PACKED_GENERATED_PRODUCT);
    printf("packed arithmetic native carryless multiply: %d\n",ECC_PACKED_CLMAD);
    printf("packed arithmetic top clmad: %d\n",ECC_PACKED_TOP_CLMAD);
    printf("packed arithmetic native carryless square: %d\n",ECC_PACKED_CLMAD_SQUARE);
    printf("packed arithmetic three-limb Karatsuba: %d\n",ECC_PACKED_KARAT3);
    printf("packed arithmetic weighted prefix: %d\n",ECC_PACKED_WEIGHTED_PREFIX);
    const int selected[] = {0,1,2,3,4,5,6,7,8,9,10,16,32,65,130,131};
    std::vector<P131> input;
    std::vector<int> powers;
    for (int k:selected) for (int bit=0;bit<131;bit++) {
        P131 a{}; a.v[bit/32]=1u<<(bit%32);
        input.push_back(a); powers.push_back(k);
    }
    uint32_t state=0x131263u;
    for (int i=0;i<1024;i++) {
        P131 a;
        for (int j=0;j<5;j++) {
            state^=state<<13; state^=state>>17; state^=state<<5;
            a.v[j]=state;
        }
        a.v[4]&=7;
        input.push_back(a); powers.push_back(selected[i%16]);
    }
    int n=int(input.size());
    std::vector<P131> output(n);
    P131 *deviceInput, *deviceOutput; int *devicePowers;
    checked(cudaMalloc(&deviceInput, n*sizeof(P131)));
    checked(cudaMalloc(&deviceOutput, n*sizeof(P131)));
    checked(cudaMalloc(&devicePowers, n*sizeof(int)));
    checked(cudaMemcpy(deviceInput,input.data(),n*sizeof(P131),cudaMemcpyHostToDevice));
    checked(cudaMemcpy(devicePowers,powers.data(),n*sizeof(int),cudaMemcpyHostToDevice));
    frobeniusProbe<<<(n+ECC_THREADS-1)/ECC_THREADS,ECC_THREADS>>>(deviceInput,devicePowers,deviceOutput,n);
    checked(cudaGetLastError()); checked(cudaDeviceSynchronize());
    checked(cudaMemcpy(output.data(),deviceOutput,n*sizeof(P131),cudaMemcpyDeviceToHost));
    checked(cudaFree(deviceInput)); checked(cudaFree(deviceOutput)); checked(cudaFree(devicePowers));
    for (int i=0;i<n;i++) {
        P131 want=expected(input[i],powers[i]);
        for (int j=0;j<5;j++) if (output[i].v[j]!=want.v[j]) {
            fprintf(stderr,"GPU Frobenius mismatch: case %d, power %d, word %d\n",i,powers[i],j);
            return 1;
        }
    }
    printf("PASS: %d GPU Frobenius vectors, every field basis vector for all selected powers plus dense cases\n",n);
    return polynomialChecks() && squareChecks() && pairedFrobeniusChecks()?0:1;
}

