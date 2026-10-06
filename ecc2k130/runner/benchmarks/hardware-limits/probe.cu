// Hardware-limit probes for the ECC2K-130 throughput budget on one GPU.
//
// Everything here is a *ceiling measurement*, not walk throughput:
//   1. issue rate of the integer/logic instructions the packed and bitsliced
//      kernels are built from (LOP3, IADD3, SHF, PRMT, IMAD, IMAD.WIDE, POPC,
//      FFMA), alone and in mixed pairs, so pipe sharing is visible;
//   2. shared-memory and L1-hit load rates per SM per clock;
//   3. L2 and DRAM streaming bandwidth;
//   4. the SM clock actually sustained while the ALU probes run.
// Every arithmetic probe is verified on the host against a scalar model of
// the same chains, so a result that the compiler folded away cannot pass.
#include <cuda_runtime.h>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

static void check(cudaError_t e, const char *what) {
    if (e != cudaSuccess) { std::fprintf(stderr, "CUDA error in %s: %s\n", what, cudaGetErrorString(e)); std::exit(1); }
}
#define CK(x) check((x), #x)

__device__ __forceinline__ uint64_t globalTimer() {
    uint64_t t; asm volatile("mov.u64 %0, %%globaltimer;" : "=l"(t)); return t;
}

// ---- 1. ALU chains ----------------------------------------------------------
enum Op { OP_LOP3 = 0, OP_IADD3, OP_SHF, OP_PRMT, OP_IMAD, OP_IMADWIDE, OP_POPC, OP_FFMA,
          OP_LOP3_FFMA, OP_LOP3_IMADWIDE, OP_LOP3_IMAD, OP_IADD3_FFMA, OP_COUNT };
static const char *opNames[OP_COUNT] = {"lop3", "iadd3", "shf", "prmt", "imad", "imad.wide", "popc", "ffma",
                                        "lop3+ffma", "lop3+imad.wide", "lop3+imad", "iadd3+ffma"};
static const int CHAINS = 8;

__device__ __forceinline__ uint32_t chainX(uint32_t tid, int j) { return (tid * 2654435761u) ^ (uint32_t(j + 1) * 0x9e3779b9u) | 1u; }
__device__ __forceinline__ uint32_t chainY(uint32_t tid, int j) { return (tid ^ 0x5bd1e995u) * (uint32_t(j) * 0x85ebca6bu + 7u) | 2u; }
__host__ __device__ __forceinline__ uint32_t hostChainX(uint32_t tid, int j) { return (tid * 2654435761u) ^ (uint32_t(j + 1) * 0x9e3779b9u) | 1u; }
__host__ __device__ __forceinline__ uint32_t hostChainY(uint32_t tid, int j) { return (tid ^ 0x5bd1e995u) * (uint32_t(j) * 0x85ebca6bu + 7u) | 2u; }

template <int OP>
__global__ void __launch_bounds__(256) aluChains(uint32_t *out, uint64_t *wide, float *fout, uint32_t rounds,
                                                 uint64_t *clockRecord) {
    const uint32_t tid = blockIdx.x * blockDim.x + threadIdx.x;
    uint32_t acc[CHAINS]; uint64_t wacc[CHAINS]; float facc[CHAINS];
    uint32_t x[CHAINS], y[CHAINS];
#pragma unroll
    for (int j = 0; j < CHAINS; ++j) {
        x[j] = chainX(tid, j); y[j] = chainY(tid, j);
        acc[j] = tid ^ (uint32_t(j) * 0x27d4eb2fu);
        wacc[j] = (uint64_t(tid) << 32) ^ uint64_t(j + 17);
        facc[j] = float(j);
    }
    uint64_t c0 = 0, t0 = 0;
    const bool recorder = (tid == 0);
    if (recorder) { c0 = clock64(); t0 = globalTimer(); }
#pragma unroll 1
    for (uint32_t r = 0; r < rounds; ++r) {
#pragma unroll
        for (int j = 0; j < CHAINS; ++j) {
            if (OP == OP_LOP3 || ((OP == OP_LOP3_FFMA || OP == OP_LOP3_IMADWIDE || OP == OP_LOP3_IMAD) && (j & 1) == 0))
                asm volatile("lop3.b32 %0, %0, %1, %2, 0x96;" : "+r"(acc[j]) : "r"(x[j]), "r"(y[j]));
            if (OP == OP_IADD3 || (OP == OP_IADD3_FFMA && (j & 1) == 0))
                asm volatile("add.u32 %0, %0, %1;" : "+r"(acc[j]) : "r"(x[j]));
            if (OP == OP_SHF)
                asm volatile("shf.r.wrap.b32 %0, %0, %1, %2;" : "+r"(acc[j]) : "r"(x[j]), "r"(y[j]));
            if (OP == OP_PRMT)
                asm volatile("prmt.b32 %0, %0, %1, %2;" : "+r"(acc[j]) : "r"(x[j]), "r"(y[j]));
            if (OP == OP_IMAD || ((OP == OP_LOP3_IMAD) && (j & 1)))
                asm volatile("mad.lo.u32 %0, %1, %2, %0;" : "+r"(acc[j]) : "r"(x[j]), "r"(y[j]));
            if (OP == OP_IMADWIDE || ((OP == OP_LOP3_IMADWIDE) && (j & 1)))
                asm volatile("mad.wide.u32 %0, %1, %2, %0;" : "+l"(wacc[j]) : "r"(x[j]), "r"(y[j]));
            if (OP == OP_POPC) {
                uint32_t p; asm volatile("popc.b32 %0, %1;" : "=r"(p) : "r"(acc[j] ^ x[j])); acc[j] += p;
            }
            if (OP == OP_FFMA || ((OP == OP_LOP3_FFMA || OP == OP_IADD3_FFMA) && (j & 1)))
                asm volatile("fma.rn.f32 %0, %1, %2, %0;" : "+f"(facc[j]) : "f"(1.5f), "f"(float((x[j] & 3u) + 1u)));
        }
    }
    if (recorder) { clockRecord[0] = clock64() - c0; clockRecord[1] = globalTimer() - t0; }
#pragma unroll
    for (int j = 0; j < CHAINS; ++j) {
        out[size_t(tid) * CHAINS + j] = acc[j];
        wide[size_t(tid) * CHAINS + j] = wacc[j];
        fout[size_t(tid) * CHAINS + j] = facc[j];
    }
}

static uint32_t hostShf(uint32_t a, uint32_t b, uint32_t c) {
    const unsigned s = c & 31u;                       // shf.r.wrap: (b:a) >> s, low word
    const uint64_t v = (uint64_t(b) << 32) | a;
    return uint32_t(v >> s);
}
static uint32_t hostPrmt(uint32_t a, uint32_t b, uint32_t sel) {
    const uint8_t bytes[8] = {uint8_t(a), uint8_t(a >> 8), uint8_t(a >> 16), uint8_t(a >> 24),
                              uint8_t(b), uint8_t(b >> 8), uint8_t(b >> 16), uint8_t(b >> 24)};
    uint32_t r = 0;
    for (int i = 0; i < 4; ++i) {
        const unsigned nib = (sel >> (4 * i)) & 0xfu;
        uint8_t v = bytes[nib & 7u];
        if (nib & 8u) v = (v & 0x80u) ? 0xffu : 0u;     // sign replicate
        r |= uint32_t(v) << (8 * i);
    }
    return r;
}

static bool verifyAlu(int op, const std::vector<uint32_t> &out, const std::vector<uint64_t> &wide,
                      const std::vector<float> &fout, uint32_t threads, uint32_t rounds, uint32_t checkThreads) {
    for (uint32_t tid = 0; tid < threads && tid < checkThreads; ++tid) {
        for (int j = 0; j < CHAINS; ++j) {
            const uint32_t x = hostChainX(tid, j), y = hostChainY(tid, j);
            uint32_t acc = tid ^ (uint32_t(j) * 0x27d4eb2fu);
            uint64_t wacc = (uint64_t(tid) << 32) ^ uint64_t(j + 17);
            float facc = float(j);
            const bool lop = op == OP_LOP3 || ((op == OP_LOP3_FFMA || op == OP_LOP3_IMADWIDE || op == OP_LOP3_IMAD) && (j & 1) == 0);
            const bool add = op == OP_IADD3 || (op == OP_IADD3_FFMA && (j & 1) == 0);
            const bool imad = op == OP_IMAD || (op == OP_LOP3_IMAD && (j & 1));
            const bool wmad = op == OP_IMADWIDE || (op == OP_LOP3_IMADWIDE && (j & 1));
            const bool ffma = op == OP_FFMA || ((op == OP_LOP3_FFMA || op == OP_IADD3_FFMA) && (j & 1));
            if (lop) acc ^= (rounds & 1u) ? (x ^ y) : 0u;
            if (add) acc += rounds * x;
            if (imad) acc += rounds * (x * y);
            if (wmad) wacc += uint64_t(rounds) * (uint64_t(x) * uint64_t(y));
            if (ffma) facc += float(rounds) * (1.5f * float((x & 3u) + 1u));   // exact: integer multiples of 1.5 below 2^24
            if (op == OP_SHF) for (uint32_t r = 0; r < rounds; ++r) acc = hostShf(acc, x, y);
            if (op == OP_PRMT) for (uint32_t r = 0; r < rounds; ++r) acc = hostPrmt(acc, x, y);
            if (op == OP_POPC) for (uint32_t r = 0; r < rounds; ++r) acc += __builtin_popcount(acc ^ x);
            const size_t i = size_t(tid) * CHAINS + j;
            if (out[i] != acc || wide[i] != wacc || fout[i] != facc) {
                std::fprintf(stderr, "MISMATCH op=%s tid=%u chain=%d rounds=%u: got %08x/%016llx/%g want %08x/%016llx/%g\n",
                             opNames[op], tid, j, rounds, out[i], (unsigned long long)wide[i], double(fout[i]),
                             acc, (unsigned long long)wacc, double(facc));
                return false;
            }
        }
    }
    return true;
}

template <int OP>
static void runAlu(const cudaDeviceProp &dev, int blocksPerSm) {
    const int block = 256;
    const uint32_t threads = uint32_t(dev.multiProcessorCount) * blocksPerSm * block;
    uint32_t *out; uint64_t *wide; float *fout; uint64_t *clockRecord;
    CK(cudaMalloc(&out, size_t(threads) * CHAINS * 4)); CK(cudaMalloc(&wide, size_t(threads) * CHAINS * 8));
    CK(cudaMalloc(&fout, size_t(threads) * CHAINS * 4)); CK(cudaMalloc(&clockRecord, 16));
    std::vector<uint32_t> hout(size_t(threads) * CHAINS); std::vector<uint64_t> hwide(hout.size()); std::vector<float> hf(hout.size());
    cudaFuncAttributes attr; CK(cudaFuncGetAttributes(&attr, aluChains<OP>));
    int resident; CK(cudaOccupancyMaxActiveBlocksPerMultiprocessor(&resident, aluChains<OP>, block, 0));
    // Instructions per round per thread: the mixed probes issue one op per chain too.
    const int opsPerRound = CHAINS;
    for (uint32_t rounds : {0u, 1u, 3u, 64u}) {
        aluChains<OP><<<threads / block, block>>>(out, wide, fout, rounds, clockRecord); CK(cudaGetLastError()); CK(cudaDeviceSynchronize());
        CK(cudaMemcpy(hout.data(), out, hout.size() * 4, cudaMemcpyDeviceToHost));
        CK(cudaMemcpy(hwide.data(), wide, hwide.size() * 8, cudaMemcpyDeviceToHost));
        CK(cudaMemcpy(hf.data(), fout, hf.size() * 4, cudaMemcpyDeviceToHost));
        if (!verifyAlu(OP, hout, hwide, hf, threads, rounds, threads)) std::exit(2);
    }
    const uint32_t rounds = 1u << 15;
    cudaEvent_t s, e; CK(cudaEventCreate(&s)); CK(cudaEventCreate(&e));
    aluChains<OP><<<threads / block, block>>>(out, wide, fout, rounds, clockRecord); CK(cudaGetLastError()); CK(cudaDeviceSynchronize());
    for (int rep = 0; rep < 5; ++rep) {
        CK(cudaEventRecord(s));
        aluChains<OP><<<threads / block, block>>>(out, wide, fout, rounds, clockRecord); CK(cudaGetLastError());
        CK(cudaEventRecord(e)); CK(cudaEventSynchronize(e));
        float ms; CK(cudaEventElapsedTime(&ms, s, e));
        uint64_t rec[2]; CK(cudaMemcpy(rec, clockRecord, 16, cudaMemcpyDeviceToHost));
        CK(cudaMemcpy(hout.data(), out, hout.size() * 4, cudaMemcpyDeviceToHost));
        CK(cudaMemcpy(hwide.data(), wide, hwide.size() * 8, cudaMemcpyDeviceToHost));
        CK(cudaMemcpy(hf.data(), fout, hf.size() * 4, cudaMemcpyDeviceToHost));
        if (!verifyAlu(OP, hout, hwide, hf, threads, rounds, 4096)) std::exit(2);
        const double ops = double(threads) * rounds * opsPerRound;
        const double perSecond = ops / (ms * 1e-3);
        const double smMHz = rec[1] ? double(rec[0]) / double(rec[1]) * 1e3 : 0.0;
        const double perSmClock = smMHz > 0 ? perSecond / (dev.multiProcessorCount * smMHz * 1e6) : 0.0;
        std::printf("{\"kind\":\"alu\",\"op\":\"%s\",\"rep\":%d,\"threads\":%u,\"residentBlocks\":%d,\"registers\":%d,"
                    "\"rounds\":%u,\"laneOps\":%.0f,\"milliseconds\":%.6f,\"teraLaneOpsPerSecond\":%.6f,"
                    "\"smClockMHzThread0\":%.1f,\"laneOpsPerSmClock\":%.2f,\"valid\":true}\n",
                    opNames[OP], rep, threads, resident, attr.numRegs, rounds, ops, ms, perSecond / 1e12, smMHz, perSmClock);
        std::fflush(stdout);
    }
    CK(cudaEventDestroy(s)); CK(cudaEventDestroy(e));
    CK(cudaFree(out)); CK(cudaFree(wide)); CK(cudaFree(fout)); CK(cudaFree(clockRecord));
}

// ---- 2. shared memory and L1-hit load rates -----------------------------------
__global__ void __launch_bounds__(256) smemLoads(uint32_t *out, uint32_t rounds, uint64_t *clockRecord) {
    __shared__ uint32_t buf[4096];
    const uint32_t tid = blockIdx.x * blockDim.x + threadIdx.x;
    for (int i = threadIdx.x; i < 4096; i += blockDim.x) buf[i] = i * 2654435761u;
    __syncthreads();
    uint32_t acc[8]; uint32_t idx[8];
#pragma unroll
    for (int j = 0; j < 8; ++j) { acc[j] = 0; idx[j] = (threadIdx.x + 32u * j) & 4095u; }
    uint64_t c0 = 0, t0 = 0;
    if (tid == 0) { c0 = clock64(); t0 = globalTimer(); }
#pragma unroll 1
    for (uint32_t r = 0; r < rounds; ++r) {
#pragma unroll
        for (int j = 0; j < 8; ++j) {
            uint32_t v;
            asm volatile("ld.shared.u32 %0, [%1];" : "=r"(v) : "r"(uint32_t(__cvta_generic_to_shared(buf + idx[j]))));
            acc[j] ^= v;
            idx[j] = (idx[j] + 256u) & 4095u;     // stays conflict-free: consecutive lanes, consecutive words
        }
    }
    if (tid == 0) { clockRecord[0] = clock64() - c0; clockRecord[1] = globalTimer() - t0; }
    uint32_t s = 0;
#pragma unroll
    for (int j = 0; j < 8; ++j) s ^= acc[j] * (j + 1);
    out[tid] = s;
}
static uint32_t hostSmem(uint32_t t, uint32_t rounds) {
    uint32_t acc[8], idx[8];
    for (int j = 0; j < 8; ++j) { acc[j] = 0; idx[j] = (t + 32u * j) & 4095u; }
    for (uint32_t r = 0; r < rounds; ++r) for (int j = 0; j < 8; ++j) { acc[j] ^= idx[j] * 2654435761u; idx[j] = (idx[j] + 256u) & 4095u; }
    uint32_t s = 0; for (int j = 0; j < 8; ++j) s ^= acc[j] * (j + 1); return s;
}

__global__ void __launch_bounds__(256) l1Loads(const uint32_t *__restrict__ src, uint32_t *out, uint32_t rounds, uint64_t *clockRecord) {
    // Each block walks its own 16 KB window, which stays resident in L1 after the first pass.
    const uint32_t tid = blockIdx.x * blockDim.x + threadIdx.x;
    const uint32_t *base = src + size_t(blockIdx.x) * 4096;
    uint32_t acc[8]; uint32_t idx[8];
#pragma unroll
    for (int j = 0; j < 8; ++j) { acc[j] = 0; idx[j] = (threadIdx.x + 32u * j) & 4095u; }
    uint64_t c0 = 0, t0 = 0;
    if (tid == 0) { c0 = clock64(); t0 = globalTimer(); }
#pragma unroll 1
    for (uint32_t r = 0; r < rounds; ++r) {
#pragma unroll
        for (int j = 0; j < 8; ++j) { acc[j] ^= __ldg(base + idx[j]); idx[j] = (idx[j] + 256u) & 4095u; }
    }
    if (tid == 0) { clockRecord[0] = clock64() - c0; clockRecord[1] = globalTimer() - t0; }
    uint32_t s = 0;
#pragma unroll
    for (int j = 0; j < 8; ++j) s ^= acc[j] * (j + 1);
    out[tid] = s;
}
__global__ void fillWords(uint32_t *p, size_t n) {
    for (size_t i = size_t(blockIdx.x) * blockDim.x + threadIdx.x; i < n; i += size_t(gridDim.x) * blockDim.x) p[i] = uint32_t(i & 4095u) * 2654435761u;
}

template <class Launch>
static void runLoads(const char *name, const cudaDeviceProp &dev, int blocksPerSm, Launch launch, int registers, int resident) {
    const int block = 256;
    const uint32_t threads = uint32_t(dev.multiProcessorCount) * blocksPerSm * block;
    uint32_t *out; uint64_t *clockRecord;
    CK(cudaMalloc(&out, size_t(threads) * 4)); CK(cudaMalloc(&clockRecord, 16));
    std::vector<uint32_t> hout(threads);
    for (uint32_t rounds : {0u, 1u, 5u, 100u}) {
        launch(threads / block, block, out, rounds, clockRecord); CK(cudaGetLastError()); CK(cudaDeviceSynchronize());
        CK(cudaMemcpy(hout.data(), out, hout.size() * 4, cudaMemcpyDeviceToHost));
        for (uint32_t t = 0; t < threads; ++t) if (hout[t] != hostSmem(t % 256u, rounds)) { std::fprintf(stderr, "MISMATCH %s tid=%u rounds=%u\n", name, t, rounds); std::exit(2); }
    }
    const uint32_t rounds = 1u << 14;
    cudaEvent_t s, e; CK(cudaEventCreate(&s)); CK(cudaEventCreate(&e));
    launch(threads / block, block, out, rounds, clockRecord); CK(cudaGetLastError()); CK(cudaDeviceSynchronize());
    for (int rep = 0; rep < 5; ++rep) {
        CK(cudaEventRecord(s)); launch(threads / block, block, out, rounds, clockRecord); CK(cudaGetLastError());
        CK(cudaEventRecord(e)); CK(cudaEventSynchronize(e));
        float ms; CK(cudaEventElapsedTime(&ms, s, e));
        uint64_t rec[2]; CK(cudaMemcpy(rec, clockRecord, 16, cudaMemcpyDeviceToHost));
        CK(cudaMemcpy(hout.data(), out, hout.size() * 4, cudaMemcpyDeviceToHost));
        for (uint32_t t = 0; t < 2048; ++t) if (hout[t] != hostSmem(t % 256u, rounds)) { std::fprintf(stderr, "MISMATCH %s timed tid=%u\n", name, t); std::exit(2); }
        const double loads = double(threads) * rounds * 8;
        const double perSecond = loads / (ms * 1e-3);
        const double smMHz = rec[1] ? double(rec[0]) / double(rec[1]) * 1e3 : 0.0;
        const double perSmClock = smMHz > 0 ? perSecond / (dev.multiProcessorCount * smMHz * 1e6) : 0.0;
        std::printf("{\"kind\":\"loads\",\"op\":\"%s\",\"rep\":%d,\"threads\":%u,\"residentBlocks\":%d,\"registers\":%d,\"rounds\":%u,"
                    "\"laneLoads\":%.0f,\"milliseconds\":%.6f,\"teraLaneLoadsPerSecond\":%.6f,\"smClockMHzThread0\":%.1f,"
                    "\"laneLoadsPerSmClock\":%.2f,\"bytesPerSmClock\":%.1f,\"valid\":true}\n",
                    name, rep, threads, resident, registers, rounds, loads, ms, perSecond / 1e12, smMHz, perSmClock, perSmClock * 4);
        std::fflush(stdout);
    }
    CK(cudaEventDestroy(s)); CK(cudaEventDestroy(e)); CK(cudaFree(out)); CK(cudaFree(clockRecord));
}

// ---- 3. L2 and DRAM streaming bandwidth ------------------------------------------
__global__ void streamRead(const uint4 *__restrict__ p, size_t n, uint32_t passes, uint32_t *out) {
    uint32_t acc = 0;
    for (uint32_t pass = 0; pass < passes; ++pass)
        for (size_t i = size_t(blockIdx.x) * blockDim.x + threadIdx.x; i < n; i += size_t(gridDim.x) * blockDim.x) {
            const uint4 v = p[i]; acc ^= v.x ^ v.y ^ v.z ^ v.w;
        }
    out[size_t(blockIdx.x) * blockDim.x + threadIdx.x] = acc;
}
__global__ void streamWrite(uint4 *p, size_t n, uint32_t passes, uint32_t salt) {
    for (uint32_t pass = 0; pass < passes; ++pass)
        for (size_t i = size_t(blockIdx.x) * blockDim.x + threadIdx.x; i < n; i += size_t(gridDim.x) * blockDim.x)
            p[i] = make_uint4(uint32_t(i) ^ salt, uint32_t(i >> 32), salt, pass);
}
__global__ void streamCopy(const uint4 *__restrict__ src, uint4 *dst, size_t n, uint32_t passes) {
    for (uint32_t pass = 0; pass < passes; ++pass)
        for (size_t i = size_t(blockIdx.x) * blockDim.x + threadIdx.x; i < n; i += size_t(gridDim.x) * blockDim.x) dst[i] = src[i];
}
static void runBandwidth(const char *name, const cudaDeviceProp &dev, size_t bytes, uint32_t passes) {
    const size_t n = bytes / 16;
    uint4 *a, *b; uint32_t *out;
    CK(cudaMalloc(&a, bytes)); CK(cudaMalloc(&b, bytes));
    const int block = 256, grid = dev.multiProcessorCount * 8;
    CK(cudaMalloc(&out, size_t(grid) * block * 4));
    streamWrite<<<grid, block>>>(a, n, 1, 0x1234567u); CK(cudaGetLastError()); CK(cudaDeviceSynchronize());
    // Expected XOR of one read pass, computed on the host from the same fill pattern.
    cudaEvent_t s, e; CK(cudaEventCreate(&s)); CK(cudaEventCreate(&e));
    const char *modes[3] = {"read", "write", "copy"};
    for (int mode = 0; mode < 3; ++mode) {
        for (int rep = 0; rep < 4; ++rep) {
            CK(cudaEventRecord(s));
            if (mode == 0) streamRead<<<grid, block>>>(a, n, passes, out);
            if (mode == 1) streamWrite<<<grid, block>>>(b, n, passes, 0x89abcdefu + rep);
            if (mode == 2) streamCopy<<<grid, block>>>(a, b, n, passes);
            CK(cudaGetLastError()); CK(cudaEventRecord(e)); CK(cudaEventSynchronize(e));
            float ms; CK(cudaEventElapsedTime(&ms, s, e));
            const double moved = double(bytes) * passes * (mode == 2 ? 2.0 : 1.0);
            std::printf("{\"kind\":\"bandwidth\",\"region\":\"%s\",\"mode\":\"%s\",\"rep\":%d,\"bytesPerPass\":%zu,\"passes\":%u,"
                        "\"milliseconds\":%.6f,\"gigabytesPerSecond\":%.3f}\n", name, modes[mode], rep, bytes, passes, ms, moved / (ms * 1e-3) / 1e9);
            std::fflush(stdout);
        }
    }
    if (n) {   // spot-check the read kernel actually consumed the data
        std::vector<uint32_t> hout(size_t(grid) * block);
        streamRead<<<grid, block>>>(a, n, 1, out); CK(cudaGetLastError()); CK(cudaDeviceSynchronize());
        CK(cudaMemcpy(hout.data(), out, hout.size() * 4, cudaMemcpyDeviceToHost));
        uint32_t want = 0;
        for (size_t i = 0; i < n; i += size_t(grid) * block) want ^= (uint32_t(i) ^ 0x1234567u) ^ uint32_t(i >> 32) ^ 0x1234567u ^ 0u;
        if (hout[0] != want) { std::fprintf(stderr, "MISMATCH stream read checksum for %s\n", name); std::exit(2); }
    }
    CK(cudaEventDestroy(s)); CK(cudaEventDestroy(e)); CK(cudaFree(a)); CK(cudaFree(b)); CK(cudaFree(out));
}

int main() {
    cudaDeviceProp dev; CK(cudaGetDeviceProperties(&dev, 0));
    int smemOptin = 0; CK(cudaDeviceGetAttribute(&smemOptin, cudaDevAttrMaxSharedMemoryPerBlockOptin, 0));
    std::printf("{\"kind\":\"device\",\"name\":\"%s\",\"sms\":%d,\"l2Bytes\":%d,"
                "\"sharedPerSm\":%zu,\"sharedPerBlockOptin\":%d,\"regsPerSm\":%d,\"maxThreadsPerSm\":%d,\"maxBlocksPerSm\":%d,\"totalMemory\":%zu,\"cc\":\"%d.%d\"}\n",
                dev.name, dev.multiProcessorCount, dev.l2CacheSize,
                dev.sharedMemPerMultiprocessor, smemOptin, dev.regsPerMultiprocessor, dev.maxThreadsPerMultiProcessor,
                dev.maxBlocksPerMultiProcessor, dev.totalGlobalMem, dev.major, dev.minor);
    std::fflush(stdout);
    const int blocksPerSm = 8;   // 2048 threads requested per SM; the occupancy calculator reports what is resident
    runAlu<OP_LOP3>(dev, blocksPerSm); runAlu<OP_IADD3>(dev, blocksPerSm); runAlu<OP_SHF>(dev, blocksPerSm);
    runAlu<OP_PRMT>(dev, blocksPerSm); runAlu<OP_IMAD>(dev, blocksPerSm); runAlu<OP_IMADWIDE>(dev, blocksPerSm);
    runAlu<OP_POPC>(dev, blocksPerSm); runAlu<OP_FFMA>(dev, blocksPerSm);
    runAlu<OP_LOP3_FFMA>(dev, blocksPerSm); runAlu<OP_LOP3_IMADWIDE>(dev, blocksPerSm);
    runAlu<OP_LOP3_IMAD>(dev, blocksPerSm); runAlu<OP_IADD3_FFMA>(dev, blocksPerSm);
    {
        cudaFuncAttributes attr; CK(cudaFuncGetAttributes(&attr, smemLoads));
        int resident; CK(cudaOccupancyMaxActiveBlocksPerMultiprocessor(&resident, smemLoads, 256, 0));
        runLoads("ld.shared", dev, blocksPerSm, [](int g, int b, uint32_t *o, uint32_t r, uint64_t *c) { smemLoads<<<g, b>>>(o, r, c); }, attr.numRegs, resident);
        CK(cudaFuncGetAttributes(&attr, l1Loads));
        CK(cudaOccupancyMaxActiveBlocksPerMultiprocessor(&resident, l1Loads, 256, 0));
        const size_t words = size_t(dev.multiProcessorCount) * blocksPerSm * 4096;
        uint32_t *src; CK(cudaMalloc(&src, words * 4));
        fillWords<<<1024, 256>>>(src, words); CK(cudaGetLastError()); CK(cudaDeviceSynchronize());
        runLoads("ld.global.l1hit", dev, blocksPerSm, [src](int g, int b, uint32_t *o, uint32_t r, uint64_t *c) { l1Loads<<<g, b>>>(src, o, r, c); }, attr.numRegs, resident);
        CK(cudaFree(src));
    }
    runBandwidth("l2-resident-48MB", dev, size_t(48) << 20, 64);
    runBandwidth("dram-6GB", dev, size_t(6) << 30, 2);
    std::puts("{\"kind\":\"done\"}");
    return 0;
}
