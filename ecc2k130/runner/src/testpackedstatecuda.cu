// Synthetic storage-accessor checks only; no curve walk or timing.
#include <cuda_runtime.h>
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>
#include "../include/curveparams.h"
#include "../include/packedkernels.cuh"

#if ECC_PACKED_STATE_TILE != 256
#error "This bounded storage test requires the 256-worker layout"
#endif
#if ECC_PACKED_COMPACT_STATE != 0 && ECC_PACKED_COMPACT_STATE != 1
#error "This bounded storage test requires compact state 0 or 1"
#endif
static_assert(sizeof(unsigned) == 4, "Four-byte transfer words required");
static_assert(ECC_BATCH > 0 && ECC_BATCH <= 64, "Bounded tail-address signatures require at most64 slots");
using eccPacked131::P131;
static_assert(sizeof(P131) == 20, "Five-word arithmetic values required");

static void require(bool ok, const char *message) {
    if (!ok) { std::fprintf(stderr, "FAIL: %s\n", message); std::exit(1); }
}
static void checked(cudaError_t error) {
    if (error != cudaSuccess) {
        std::fprintf(stderr, "CUDA failure: %s\n", cudaGetErrorString(error));
        std::exit(1);
    }
}

// Values cover dense/zero/all-one/one-bit low limbs and every six-bit tail.
// The full six bits include the denominator's existing jump metadata.
static __host__ __device__ P131 value(int slot, int tid, int round, int threads) {
    P131 p;
    unsigned s = unsigned(tid) * 747796405u + unsigned(slot) * 2891336453u
                 + unsigned(round) * 277803737u + 0x9e3779b9u;
    for (int word = 0; word < 4; ++word) {
        s ^= s << 13; s ^= s >> 17; s ^= s << 5;
        p.v[word] = round % 4 == 0 ? s : round % 4 == 1 ? 0u :
                    round % 4 == 2 ? ~0u : 1u << ((word + slot + tid) & 31);
    }
    // Across the first three large-N rounds, these separate six-bit digits
    // identify both worker and slot in the bounded test domain. A tail-only
    // permutation of workers differing by64 must not share every test value.
    if (threads == 1) p.v[4] = unsigned(round + slot) & 63u;
    else if (round < 6) {
        const unsigned digit = round % 3 == 0 ? unsigned(tid) & 63u :
                               round % 3 == 1 ? (unsigned(tid) >> 6) & 63u :
                               unsigned(slot) & 63u;
        p.v[4] = digit ^ (round >= 3 ? 63u : 0u);
    } else {
        p.v[4] = ((unsigned(tid) * 17u) ^ (unsigned(tid) >> 6) ^
                  (unsigned(slot) * 29u) ^ (unsigned(round) * 7u)) & 63u;
    }
    return p;
}

static __global__ void writeFields(unsigned *physical, int threads, int round) {
    const int tid = blockIdx.x * blockDim.x + threadIdx.x;
    if (tid >= threads) return;
    for (int slot = 0; slot < ECC_BATCH; ++slot)
        eccPacked131::store(physical, slot, tid, threads, value(slot, tid, round, threads));
}
static __global__ void readFields(const unsigned *physical, P131 *logical, int threads) {
    const int tid = blockIdx.x * blockDim.x + threadIdx.x;
    if (tid >= threads) return;
    for (int slot = 0; slot < ECC_BATCH; ++slot)
        logical[size_t(slot) * threads + tid] =
            eccPacked131::load(physical, slot, tid, threads);
}

// Deliberately independent of every production compact/index/size helper.
static size_t fieldBytes(int threads) {
    const size_t tiles = (size_t(threads) + 255) / 256;
    return size_t(ECC_BATCH) * tiles * (ECC_PACKED_COMPACT_STATE ? 4352 : 5120);
}
static void encode(std::vector<unsigned char> &out, size_t guard,
                   int slot, int tid, P131 p) {
    const size_t tileSlot = size_t(tid / 256) * ECC_BATCH + slot;
    const size_t lane = tid % 256;
    if (ECC_PACKED_COMPACT_STATE) {
        const size_t base = guard + tileSlot * 4352;
        for (int word = 0; word < 4; ++word)
            std::memcpy(out.data() + base + lane * 16 + word * 4, &p.v[word], 4);
        out[base + 4096 + lane] = static_cast<unsigned char>(p.v[4]);
    } else {
        for (int word = 0; word < 5; ++word) {
            const size_t index = (tileSlot * 5 + word) * 256 + lane;
            std::memcpy(out.data() + guard + index * 4, &p.v[word], 4);
        }
    }
}

int main() {
    constexpr size_t guard = 256;
    unsigned endian = 1;
    require(*reinterpret_cast<unsigned char *>(&endian) == 1, "little-endian host");
    const int workers[] = {1, 3, 8, 255, 256, 257, 511, 512, 513};
    size_t cases = 0, records = 0;
    for (int n : workers) {
        const size_t physicalBytes = fieldBytes(n);
        const size_t logicalBytes = size_t(ECC_BATCH) * n * sizeof(P131);
        unsigned char *devicePhysical = nullptr, *deviceLogical = nullptr;
        checked(cudaMalloc(&devicePhysical, physicalBytes + 2 * guard));
        checked(cudaMalloc(&deviceLogical, logicalBytes + 2 * guard));
        auto *physical = reinterpret_cast<unsigned *>(devicePhysical + guard);
        auto *logical = reinterpret_cast<P131 *>(deviceLogical + guard);
        require(reinterpret_cast<uintptr_t>(physical) % 16 == 0, "aligned low records");
        const int rounds = n == 1 ? 64 : 8;
        for (int round = 0; round < rounds; ++round) {
            std::vector<unsigned char> expected(physicalBytes + 2 * guard, 0xa5);
            std::vector<unsigned char> actual(expected.size());
            std::vector<unsigned char> expectedLogical(logicalBytes + 2 * guard, 0x5a);
            std::vector<unsigned char> actualLogical(expectedLogical.size());
            for (int slot = 0; slot < ECC_BATCH; ++slot) {
                for (int tid = 0; tid < n; ++tid) {
                    const auto p = value(slot, tid, round, n);
                    encode(expected, guard, slot, tid, p);
                    std::memcpy(expectedLogical.data() + guard +
                                (size_t(slot) * n + tid) * sizeof(P131), &p, sizeof p);
                }
            }
            checked(cudaMemset(devicePhysical, 0xa5, expected.size()));
            writeFields<<<(n + 255) / 256, 256>>>(physical, n, round);
            checked(cudaGetLastError()); checked(cudaDeviceSynchronize());
            checked(cudaMemcpy(actual.data(), devicePhysical, actual.size(), cudaMemcpyDeviceToHost));
            require(actual == expected, "physical byte image, partial-tile padding and storage canaries");

            // Read from the independently encoded host image, including padding.
            checked(cudaMemcpy(devicePhysical, expected.data(), expected.size(), cudaMemcpyHostToDevice));
            checked(cudaMemset(deviceLogical, 0x5a, expectedLogical.size()));
            readFields<<<(n + 255) / 256, 256>>>(physical, logical, n);
            checked(cudaGetLastError()); checked(cudaDeviceSynchronize());
            checked(cudaMemcpy(actualLogical.data(), deviceLogical, actualLogical.size(), cudaMemcpyDeviceToHost));
            require(actualLogical == expectedLogical, "logical fields, six-bit tags and output canaries");
            ++cases; records += size_t(ECC_BATCH) * n;
        }
        checked(cudaFree(devicePhysical)); checked(cudaFree(deviceLogical));
    }
    std::printf("packed storage compact state: %d\n", ECC_PACKED_COMPACT_STATE);
    std::printf("packed storage batch: %d\n", ECC_BATCH);
    std::printf("PASS: %zu GPU storage cases, %zu records, independent physical images and logical reads with canaries\n",
                cases, records);
    return 0;
}
