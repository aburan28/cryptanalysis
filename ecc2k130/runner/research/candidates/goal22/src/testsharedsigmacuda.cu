// Synthetic shared/global Frobenius checks; no walk timing.
#include <cuda_runtime.h>
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>
#include "../include/packed131.h"

#if ECC_PACKED_WEIGHTED_PREFIX != 2 || !(ECC_PACKED_PERM_SIGMA & 1)
#error "Shared-sigma probe requires weighted2 and the walk network"
#endif
using eccPacked131::P131;
struct Outputs { P131 globalFirst, globalSecond, selectedFirst, selectedSecond; };
static_assert(sizeof(Outputs) == 80, "Four unpadded five-word outputs required");

static void need(bool ok, const char *why) {
    if (!ok) { std::fprintf(stderr, "FAIL: %s\n", why); std::exit(1); }
}
static void checked(cudaError_t status) {
    if (status != cudaSuccess) {
        std::fprintf(stderr, "CUDA shared-sigma test: %s\n", cudaGetErrorString(status));
        std::exit(1);
    }
}
static P131 reference(P131 a, int exponent) {
    unsigned factor = 1;
    for (int k = 0; k < exponent; ++k) factor = (2 * factor) % 263;
    P131 result{};
    for (int bit = 0; bit < 131; ++bit) if ((a.v[bit / 32] >> (bit % 32)) & 1u) {
        unsigned target = ((bit + 1) * factor) % 263;
        if (target > 131) target = 263 - target;
        --target;
        result.v[target / 32] ^= 1u << (target % 32);
    }
    return result;
}
static bool same(P131 a, P131 b) {
    return !std::memcmp(a.v, b.v, sizeof a.v) && (a.v[4] & ~7u) == 0;
}

__global__ void sigmaStorageProbe(const P131 *a, const P131 *b, const int *powers,
                                  Outputs *out, unsigned *tables, int n) {
    using namespace eccPacked131;
#if ECC_PACKED_SHARED_SIGMA
    // A prior shared allocation must not accidentally satisfy the copy test.
    for (unsigned word = threadIdx.x; word < 448; word += blockDim.x)
        sigmaWalkShared131Masks[word / 8][word % 8] =
            ~__ldg(&sigmaWalkNetwork131Masks[word / 8][word % 8]);
    __syncthreads();
    initSigmaWalkShared131();
#endif
    // Include entirely inactive blocks: table setup precedes every return.
    for (unsigned word = threadIdx.x; word < 448; word += blockDim.x) {
#if ECC_PACKED_SHARED_SIGMA
        const unsigned value = sigmaWalkShared131Masks[word / 8][word % 8];
#else
        const unsigned value = __ldg(&sigmaWalkNetwork131Masks[word / 8][word % 8]);
#endif
        tables[size_t(blockIdx.x) * 448 + word] = value;
    }
    const int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= n) return;
    const auto global = sigmaWalkNetworkPair131(a[i], b[i], powers[i] - 3);
#if ECC_PACKED_SHARED_SIGMA
    const auto selected = sigmaWalkNetworkPairShared131(a[i], b[i], powers[i] - 3);
#else
    const auto selected = sigmaWalkNetworkPair131(a[i], b[i], powers[i] - 3);
#endif
    out[i] = {global.first, global.second, selected.first, selected.second};
}

int main() {
    std::vector<P131> a, b;
    std::vector<int> powers;
    auto append = [&](P131 x, P131 y, int power) {
        a.push_back(x); b.push_back(y); powers.push_back(power);
    };
    unsigned state = 0x5349474du;
    auto random = [&]() { state ^= state << 13; state ^= state >> 17; state ^= state << 5; return state; };
    const P131 zero{}, full{{~0u, ~0u, ~0u, ~0u, 7u}};
    const P131 even{{0x55555555u, 0x55555555u, 0x55555555u, 0x55555555u, 5u}};
    const P131 odd{{0xaaaaaaaau, 0xaaaaaaaau, 0xaaaaaaaau, 0xaaaaaaaau, 2u}};
    for (int power = 3; power <= 10; ++power) {
        for (int bit = 0; bit < 131; ++bit) {
            P131 basis{}; basis.v[bit / 32] = 1u << (bit % 32);
            append(basis, zero, power); append(zero, basis, power);
        }
        for (int row = 0; row < 512; ++row) {
            P131 x, y;
            for (int word = 0; word < 5; ++word) { x.v[word] = random(); y.v[word] = random(); }
            x.v[4] &= 7u; y.v[4] &= 7u; append(x, y, power);
        }
        append(zero, zero, power); append(full, full, power);
        append(full, zero, power); append(zero, full, power);
        append(even, odd, power);
        append(P131{{0, 0, 0, 0, 4u}}, P131{{1u, 0, 0, 0, 0}}, power);
    }
    need(a.size() == 6240 && b.size() == a.size() && powers.size() == a.size(), "6240-pair fixture inventory");
    std::vector<P131> wantA(a.size()), wantB(b.size());
    for (size_t i = 0; i < a.size(); ++i) { wantA[i] = reference(a[i], powers[i]); wantB[i] = reference(b[i], powers[i]); }
    // One repeat mixes all eight indices within a warp, using the same cases.
    std::vector<P131> mixedA(a.size()), mixedB(b.size());
    std::vector<int> mixedPowers(powers.size());
    for (size_t i = 0; i < a.size(); ++i) {
        const size_t source = (i % 8) * 780 + i / 8;
        mixedA[i] = a[source]; mixedB[i] = b[source]; mixedPowers[i] = powers[source];
    }
    P131 *da, *db; int *dp;
    checked(cudaMalloc(&da, a.size() * sizeof(P131))); checked(cudaMalloc(&db, b.size() * sizeof(P131)));
    checked(cudaMalloc(&dp, powers.size() * sizeof(int)));
    checked(cudaMemcpy(da, a.data(), a.size() * sizeof(P131), cudaMemcpyHostToDevice));
    checked(cudaMemcpy(db, b.data(), b.size() * sizeof(P131), cudaMemcpyHostToDevice));
    checked(cudaMemcpy(dp, powers.data(), powers.size() * sizeof(int), cudaMemcpyHostToDevice));
    unsigned expectedTable[56][8];
    static_assert(sizeof(eccPacked131::sigmaWalkNetwork131Masks) == sizeof(expectedTable), "56x8 mask table required");
    checked(cudaMemcpyFromSymbol(expectedTable, eccPacked131::sigmaWalkNetwork131Masks, sizeof(expectedTable)));
    unsigned scenarios = 0, pairs = 0, blocksChecked = 0;
    const int sizes[] = {0, 1, 3, 255, 256, 257, 6240};
    for (int n : sizes) {
        const int blocks = (n + 255) / 256 + 1, padded = blocks * 256;
        Outputs *deviceOut;
        unsigned *deviceTables;
        const size_t outBytes = size_t(padded + 2) * sizeof(Outputs);
        const size_t tableWords = size_t(blocks) * 448 + 2;
        checked(cudaMalloc(&deviceOut, outBytes)); checked(cudaMalloc(&deviceTables, tableWords * sizeof(unsigned)));
        std::vector<Outputs> hostOut(padded + 2);
        std::vector<unsigned> hostTables(tableWords);
        for (int repeat = 0; repeat < 3; ++repeat) {
            const bool mixed = repeat == 1;
            checked(cudaMemcpy(da, mixed ? mixedA.data() : a.data(), a.size() * sizeof(P131), cudaMemcpyHostToDevice));
            checked(cudaMemcpy(db, mixed ? mixedB.data() : b.data(), b.size() * sizeof(P131), cudaMemcpyHostToDevice));
            checked(cudaMemcpy(dp, mixed ? mixedPowers.data() : powers.data(), powers.size() * sizeof(int), cudaMemcpyHostToDevice));
            checked(cudaMemset(deviceOut, 0xa5, outBytes));
            checked(cudaMemset(deviceTables, 0xa5, tableWords * sizeof(unsigned)));
            sigmaStorageProbe<<<blocks, 256>>>(da, db, dp, deviceOut + 1, deviceTables + 1, n);
            checked(cudaGetLastError()); checked(cudaDeviceSynchronize());
            checked(cudaMemcpy(hostOut.data(), deviceOut, outBytes, cudaMemcpyDeviceToHost));
            checked(cudaMemcpy(hostTables.data(), deviceTables, tableWords * sizeof(unsigned), cudaMemcpyDeviceToHost));
            need(hostTables.front() == 0xa5a5a5a5u && hostTables.back() == 0xa5a5a5a5u, "table output guards");
            for (int block = 0; block < blocks; ++block)
                need(!std::memcmp(hostTables.data() + 1 + size_t(block) * 448, expectedTable, sizeof expectedTable), "every block's complete mask snapshot");
            for (int i = 0; i < n; ++i) {
                const auto &v = hostOut[i + 1];
                const size_t source = mixed ? (size_t(i) % 8) * 780 + size_t(i) / 8 : size_t(i);
                need(same(v.globalFirst, wantA[source]) && same(v.selectedFirst, wantA[source]) &&
                     same(v.globalSecond, wantB[source]) && same(v.selectedSecond, wantB[source]), "independent global/selected pair routing");
            }
            for (int i = 0; i < padded + 2; ++i) if (i == 0 || i > n) {
                const auto *bytes = reinterpret_cast<const unsigned char *>(&hostOut[i]);
                need(std::all_of(bytes, bytes + sizeof(Outputs), [](unsigned char v) { return v == 0xa5; }), "inactive output and pair guards");
            }
            ++scenarios; pairs += n; blocksChecked += blocks;
        }
        checked(cudaFree(deviceOut)); checked(cudaFree(deviceTables));
    }
    checked(cudaFree(da)); checked(cudaFree(db)); checked(cudaFree(dp));
    need(scenarios == 21 && pairs == 21036 && blocksChecked == 114, "scenario/pair/block counters");
    std::printf("packed shared sigma probe: %d\n", ECC_PACKED_SHARED_SIGMA);
    std::printf("PASS: 21 GPU sigma scenarios, 21036 input pairs, global and selected helpers against independent routing\n");
    std::printf("PASS: 114 complete block mask snapshots, 51072 words, output guards and inactive blocks\n");
    return 0;
}
