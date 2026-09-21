// Included by main.cu after the common CUDA engine and checkpoint helpers.
#pragma once
#include "packedkernels.cuh"

// Diagnostic builds only: mark a completed walk launch for Nsight range replay.
// Timed benchmark builds leave this undefined (zero).
#ifndef ECC_PROFILE_RANGE
#define ECC_PROFILE_RANGE 0
#endif
#ifndef ECC_PACKED_L2_PERSIST
#define ECC_PACKED_L2_PERSIST 0
#endif
#if ECC_PACKED_L2_PERSIST != 0 && ECC_PACKED_L2_PERSIST != 1
#error "ECC_PACKED_L2_PERSIST must be 0 or 1"
#endif
#if ECC_PROFILE_RANGE
#include <cuda_profiler_api.h>
#endif

struct PackedCudaEngine : CudaEngine<CfgF131> {
    static const int LANES = 1;
    bool restartPending = false;
    unsigned *denominators = nullptr;
    unsigned *twConsts = nullptr;
#if ECC_PACKED_L2_PERSIST
    // One allocation: the access-policy window is a single contiguous range.
    unsigned *fieldBlob = nullptr;
#endif
    // The table walk's addends and coefficients come from the resolver's
    // TableWalk so device and re-walk share one table by construction.
    const Solver<CfgF131> *sol = nullptr;

#if ECC_PHASE_PROFILE
    double profWarpSteps = 0;
#endif
    PackedCudaEngine() { P = {}; }
    ~PackedCudaEngine() override {
#if ECC_PHASE_PROFILE
        cudaDeviceSynchronize();
        if (profWarpSteps > 0) eccPacked131::phaseProfileReport(profWarpSteps);
#endif
#if ECC_PACKED_L2_PERSIST
        cudaFree(fieldBlob);
#else
        cudaFree(P.x); cudaFree(P.y); cudaFree(P.pchain);
        cudaFree(denominators);
#endif
        cudaFree(P.dead);
        cudaFree(P.seed); cudaFree(P.startIter); cudaFree(P.dp); cudaFree(P.dpCount);
        cudaFree(P.hist); cudaFree(twConsts);
    }
#if ECC_WALK_TABLE && !ECC_TABLE_GLOBAL
    static size_t dynamicSharedBytes() { return eccPacked131::TW_SHARED_BYTES; }
    unsigned checkpointVersion() const override { return 3u; }
    int laneArrayCount() const override { return 3; }
    u64 *laneArray(int i) const override { return i == 2 ? P.hist : (i ? P.startIter : P.seed); }
#elif ECC_WALK_TABLE
    static size_t dynamicSharedBytes() { return 0; }
    unsigned checkpointVersion() const override { return 3u; }
    int laneArrayCount() const override { return 3; }
    u64 *laneArray(int i) const override { return i == 2 ? P.hist : (i ? P.startIter : P.seed); }
#else
    static size_t dynamicSharedBytes() { return 0; }
    unsigned checkpointVersion() const override { return 2u; }
#endif
#include "metadata_checkpoint.inc"
    size_t fieldCount() const override { return size_t(P.threads) * BATCH * 5; }
#if ECC_PACKED_STATE_TILE
    size_t physicalFieldCount() const override {
#if ECC_PACKED_COMPACT_STATE
        // Transfer words are opaque physical storage, not logical P131 limbs.
        return eccPacked131::compactPhysicalFieldWords(size_t(P.threads));
#else
        return eccPacked131::physicalStateThreads(size_t(P.threads)) * BATCH * 5;
#endif
    }
#endif
    size_t laneCount() const override { return size_t(P.threads) * BATCH; }
    int checkpointLanes() const override { return 1; }
#if ECC_PACKED_POLY_STATE
    // Packed checkpoint v2 always stores normal-basis coordinates, including
    // when the running kernel stores polynomial coordinates. Transform only
    // the staging buffer, using the same slot/word/thread layout as load/store.
    void convertCheckpointField(std::vector<unsigned> &words, bool toPolynomial) const {
        const int threads = P.threads;
#pragma omp parallel for collapse(2) schedule(static)
        for (int slot = 0; slot < BATCH; ++slot) {
            for (int tid = 0; tid < threads; ++tid) {
                eccPacked131::P131 a;
                for (int word = 0; word < 5; ++word)
                    a.v[word] = words[(size_t(slot) * 5 + word) * threads + tid];
                const auto b = toPolynomial ? eccPacked131::toPolynomial131(a)
                                            : eccPacked131::fromPolynomial131(a);
                for (int word = 0; word < 5; ++word)
                    words[(size_t(slot) * 5 + word) * threads + tid] = b.v[word];
            }
        }
    }
    void exportCheckpointField(std::vector<unsigned> &words) const override {
#if ECC_PACKED_COMPACT_STATE
        std::vector<unsigned> logical(fieldCount());
        for (int slot = 0; slot < BATCH; ++slot)
            for (int tid = 0; tid < P.threads; ++tid) {
                const auto a = eccPacked131::compactLoad131(words.data(), slot, tid);
                for (int word = 0; word < 5; ++word)
                    logical[(size_t(slot) * 5 + word) * P.threads + tid] = a.v[word];
            }
        words.swap(logical);
#elif ECC_PACKED_STATE_TILE
        // The transfer contains every physical tile, including padding. Disk
        // coordinates remain logical SoA and use normal basis in version 2.
        std::vector<unsigned> logical(fieldCount());
        for (int slot = 0; slot < BATCH; ++slot)
            for (int word = 0; word < 5; ++word)
                for (int tid = 0; tid < P.threads; ++tid)
                    logical[(size_t(slot) * 5 + word) * P.threads + tid] =
                        words[eccPacked131::stateWordIndex(slot, word, tid)];
        words.swap(logical);
#endif
        convertCheckpointField(words, false);
    }
    void importCheckpointField(std::vector<unsigned> &words) const override {
        convertCheckpointField(words, true);
#if ECC_PACKED_COMPACT_STATE
        std::vector<unsigned> physical(physicalFieldCount(), 0u);
        for (int slot = 0; slot < BATCH; ++slot)
            for (int tid = 0; tid < P.threads; ++tid) {
                eccPacked131::P131 a;
                for (int word = 0; word < 5; ++word)
                    a.v[word] = words[(size_t(slot) * 5 + word) * P.threads + tid];
                eccPacked131::compactStore131(physical.data(), slot, tid, a);
            }
        words.swap(physical);
#elif ECC_PACKED_STATE_TILE
        // Start with zero padding. Keep device metadata indexed by logical
        // slot*P.threads+tid; only the coordinate field is tiled here.
        std::vector<unsigned> physical(physicalFieldCount(), 0u);
        for (int slot = 0; slot < BATCH; ++slot)
            for (int word = 0; word < 5; ++word)
                for (int tid = 0; tid < P.threads; ++tid)
                    physical[eccPacked131::stateWordIndex(slot, word, tid)] =
                        words[(size_t(slot) * 5 + word) * P.threads + tid];
        words.swap(physical);
#endif
    }
#endif
    static constexpr int denominatorFields = ECC_PACKED_CACHE_DENOM * (1 - ECC_TABLE_TAG_DENOM) *
        (1 + ECC_PACKED_POLY_CHAIN * (1 - ECC_PACKED_POLY_STATE));
    const char *name() const { return "cuda-packed131"; }
    u64 walksPerLaunch() const { return u64(P.threads) * BATCH; }
    bool needsReseed() const { return restartPending; }

    static int autoThreads(int device) {
        cudaDeviceProp prop;
        CUDA_CHECK(cudaGetDeviceProperties(&prop, device));
        int blocks;
        prepareKernel();
        CUDA_CHECK(cudaOccupancyMaxActiveBlocksPerMultiprocessor(
            &blocks, eccPacked131::walk, ECC_THREADS, dynamicSharedBytes()));
        size_t freeBytes, totalBytes;
        CUDA_CHECK(cudaMemGetInfo(&freeBytes, &totalBytes));
#if ECC_PACKED_COMPACT_STATE
        // autoThreads rounds to complete 256-worker tiles; each stored field
        // consumes sixteen low bytes and one top byte per worker/slot.
        const size_t perThread = size_t(BATCH) *
            ((3 + denominatorFields) * 17 + sizeof(unsigned) + 2 * sizeof(u64));
#else
        const size_t perThread = size_t(BATCH) *
            ((3 + denominatorFields) * 5 * sizeof(unsigned) + sizeof(unsigned) + 2 * sizeof(u64));
#endif
        size_t threads = size_t(prop.multiProcessorCount) * ECC_THREADS * blocks;
        const size_t fits = (freeBytes - freeBytes / 4) / perThread;
        if (threads > fits) threads = fits;
        threads -= threads % ECC_THREADS;
        if (!threads) threads = ECC_THREADS;
        printf("device: %s, %d SMs, %d block(s) of %d packed threads resident per SM\n",
               prop.name, prop.multiProcessorCount, blocks, ECC_THREADS);
        return int(threads);
    }

    static eccPacked131::P131 pack(Ref<CfgF131>::Elem a) {
        eccPacked131::P131 result;
        for (int i = 0; i < 5; ++i) result.v[i] = unsigned(a.v[i / 2] >> (32 * (i & 1)));
        return result;
    }

    // Tables above the 48 KB static limit need the opt-in before any query.
    static void prepareKernel() {
        if (dynamicSharedBytes() > 0)
            CUDA_CHECK(cudaFuncSetAttribute(eccPacked131::walk,
                cudaFuncAttributeMaxDynamicSharedMemorySize, int(dynamicSharedBytes())));
    }

#if ECC_PACKED_L2_PERSIST
    static int persistFieldCount() {
        return 3 + (ECC_PACKED_CACHE_DENOM ? denominatorFields : 0);
    }

    static void applyPackedL2Persist(void *base, size_t bytes) {
        int device = 0, maxPersist = 0;
        CUDA_CHECK(cudaGetDevice(&device));
        CUDA_CHECK(cudaDeviceGetAttribute(&maxPersist,
            cudaDevAttrMaxPersistingL2CacheSize, device));
        if (maxPersist <= 0 || bytes == 0) {
            printf("packed L2 persist window: skipped (cap %d, blob %zu)\n",
                   maxPersist, bytes);
            return;
        }
        CUDA_CHECK(cudaDeviceSetLimit(cudaLimitPersistingL2CacheSize,
                                      size_t(maxPersist)));
        CUDA_CHECK(cudaCtxResetPersistingL2Cache());
        // One window per stream. Cover the coordinate fields fully: x+y+pchain
        // at automatic occupancy is ~75 MiB, under the 80 MiB cap on this SKU.
        // Denominators sit after them and take whatever of the cap remains.
        cudaAccessPolicyWindow window = {};
        window.base_ptr = base;
        window.num_bytes = bytes < size_t(maxPersist) ? bytes : size_t(maxPersist);
        window.hitRatio = 1.0f;
        window.hitProp = cudaAccessPropertyPersisting;
        window.missProp = cudaAccessPropertyStreaming;
        cudaStreamAttrValue attr = {};
        attr.accessPolicyWindow = window;
        CUDA_CHECK(cudaStreamSetAttribute(0, cudaStreamAttributeAccessPolicyWindow, &attr));
        printf("packed L2 persist window: %zu of %zu field bytes, cap %d\n",
               window.num_bytes, bytes, maxPersist);
    }
#endif

    void setup(const Options &o, const u64 *px, const u64 *py, const u64 *qx, const u64 *qy) {
        prepareKernel();
        if (o.preferL1)
            CUDA_CHECK(cudaFuncSetCacheConfig(eccPacked131::walk, cudaFuncCachePreferL1));
        P.threads = o.threads; P.steps = o.steps; P.dpWeight = o.dpWeight;
        P.runId = o.runId; P.maxIters = o.maxIters; P.iterBase = 0; P.dpCap = o.dpCap;
        const size_t bytes = physicalFieldCount() * sizeof(unsigned);
#if ECC_PACKED_L2_PERSIST
        CUDA_CHECK(cudaMalloc(&fieldBlob, bytes * size_t(persistFieldCount())));
        P.x = fieldBlob;
        P.y = fieldBlob + physicalFieldCount();
        P.pchain = fieldBlob + 2 * physicalFieldCount();
#if ECC_PACKED_CACHE_DENOM && !ECC_TABLE_TAG_DENOM
        denominators = fieldBlob + 3 * physicalFieldCount();
#endif
        applyPackedL2Persist(fieldBlob, bytes * size_t(persistFieldCount()));
#else
        CUDA_CHECK(cudaMalloc(&P.x, bytes)); CUDA_CHECK(cudaMalloc(&P.y, bytes));
        CUDA_CHECK(cudaMalloc(&P.pchain, bytes));
#if ECC_PACKED_CACHE_DENOM && !ECC_TABLE_TAG_DENOM
        CUDA_CHECK(cudaMalloc(&denominators, bytes * denominatorFields));
#endif
#endif
        CUDA_CHECK(cudaMalloc(&P.dead, eccPacked131::goal22DeadBytes(slotCount())));
        CUDA_CHECK(cudaMemset(P.dead, 0, eccPacked131::goal22DeadBytes(slotCount())));
        CUDA_CHECK(cudaMalloc(&P.seed, laneCount() * sizeof(u64)));
        CUDA_CHECK(cudaMalloc(&P.startIter, laneCount() * sizeof(u64)));
#if ECC_WALK_TABLE
        if (!sol || !sol->walk.ready) { fprintf(stderr, "packed table walk: no resolver table\n"); exit(1); }
        {
            std::vector<uint32_t> consts(eccPacked131::TW_WORDS);
            eccPacked131::twFillConsts(sol->walk, consts.data());
            CUDA_CHECK(cudaMalloc(&twConsts, consts.size() * sizeof(uint32_t)));
            CUDA_CHECK(cudaMemcpy(twConsts, consts.data(), consts.size() * sizeof(uint32_t), cudaMemcpyHostToDevice));
            P.twConsts = twConsts;
        }
        CUDA_CHECK(cudaMalloc(&P.hist, eccPacked131::goal22HistoryBytes(laneCount())));
#endif
        CUDA_CHECK(cudaMalloc(&P.dp, size_t(P.dpCap) * sizeof(DpRecord)));
        // Second counter signals overdue restarts without emitting false DPs.
        CUDA_CHECK(cudaMalloc(&P.dpCount, 3 * sizeof(unsigned)));
        CUDA_CHECK(cudaMemset(P.dpCount, 0, 3 * sizeof(unsigned)));
        using R = Ref<CfgF131>;
        auto basis = R::make(R::fromLimbs(px), R::fromLimbs(py));
        eccPacked131::P131 ox[128], oy[128];
        for (int i = 0; i < 128; ++i) {
            auto point = R::frob(basis, i);
            ox[i] = pack(point.x); oy[i] = pack(point.y);
        }
        auto xq = pack(R::fromLimbs(qx)), yq = pack(R::fromLimbs(qy));
        CUDA_CHECK(cudaMemcpyToSymbol(eccPacked131::orbitX, ox, sizeof(ox)));
        CUDA_CHECK(cudaMemcpyToSymbol(eccPacked131::orbitY, oy, sizeof(oy)));
        CUDA_CHECK(cudaMemcpyToSymbol(eccPacked131::targetX, &xq, sizeof(xq)));
        CUDA_CHECK(cudaMemcpyToSymbol(eccPacked131::targetY, &yq, sizeof(yq)));
        cudaFuncAttributes attrs;
        CUDA_CHECK(cudaFuncGetAttributes(&attrs, eccPacked131::walk));
        printf("packed kernel: %d registers/thread, %zu local bytes/thread, %zu shared bytes/block, %s multiplier\n",
               attrs.numRegs, attrs.localSizeBytes, attrs.sharedSizeBytes,
               ECC_PACKED_SINGLE_PRODUCT ? "single-product" : "two-product");
#if ECC_PACKED_SHARED_SIGMA
        int diagnosticDevice = -1, driverReservedShared = -1;
        CUDA_CHECK(cudaGetDevice(&diagnosticDevice));
        CUDA_CHECK(cudaDeviceGetAttribute(&driverReservedShared,
            cudaDevAttrReservedSharedMemoryPerBlock, diagnosticDevice));
        printf("packed driver reserved shared bytes/block: %d, device %d\n",
               driverReservedShared, diagnosticDevice);
#endif
        printf("packed denominator cache: %d\n", ECC_PACKED_CACHE_DENOM);
        printf("packed multiply by value: %d\n", ECC_PACKED_BY_VALUE);
        printf("packed Frobenius network: %d\n", ECC_PACKED_PERM_SIGMA);
        printf("packed polynomial chain: %d\n", ECC_PACKED_POLY_CHAIN);
        printf("packed polynomial state: %d\n", ECC_PACKED_POLY_STATE);
        printf("packed unrolled inversion: %d\n", ECC_PACKED_UNROLL_INV);
        printf("packed collective inverse warps: %d\n", ECC_COLLECTIVE_WARPS);
        printf("packed paired products: %d\n", ECC_PACKED_PAIR_PRODUCTS);
        printf("packed pair ilp: %d\n", ECC_PACKED_PAIR_ILP);
        printf("packed pair clmul: %d\n", ECC_PACKED_PAIR_CLMUL);
        printf("packed clmul flat: %d\n", ECC_PACKED_CLMUL_FLAT);
        printf("packed top hoist: %d\n", ECC_PACKED_TOP_HOIST);
        printf("packed onb inv: %d\n", ECC_PACKED_ONB_INV);
        printf("packed from reduced: %d\n", ECC_PACKED_FROM_REDUCED);
        printf("packed slot unroll: %d\n", ECC_UNROLL_SLOTS);
        printf("packed fused Frobenius: %d\n", ECC_FROBENIUS_FUSED);
        printf("packed slot prefetch: %d\n", ECC_PACKED_SLOT_PREFETCH);
        printf("packed slot pipeline: %d\n", ECC_PACKED_SLOT_PIPELINE);
        printf("packed L2 persist: %d\n", ECC_PACKED_L2_PERSIST);
        printf("packed direct reduction: %d\n", ECC_PACKED_DIRECT_REDUCE);
        printf("packed generated product: %d\n", ECC_PACKED_GENERATED_PRODUCT);
        printf("packed native carryless multiply: %d\n", ECC_PACKED_CLMAD);
        printf("packed native carryless square: %d\n", ECC_PACKED_CLMAD_SQUARE);
        printf("packed three-limb Karatsuba: %d\n", ECC_PACKED_KARAT3);
        printf("packed weighted prefix: %d\n", ECC_PACKED_WEIGHTED_PREFIX);
        printf("packed compact state: %d\n", ECC_PACKED_COMPACT_STATE);
        printf("packed shared sigma: %d\n", ECC_PACKED_SHARED_SIGMA);
        printf("packed top clmad: %d\n", ECC_PACKED_TOP_CLMAD);
        printf("packed state tile: %d\n", ECC_PACKED_STATE_TILE);
        printf("packed add combine: %d\n", ECC_PACKED_ADD_COMBINE);
        printf("packed alu square: %d\n", ECC_PACKED_ALU_SQUARE);
        printf("packed alu onb square: %d\n", ECC_PACKED_ALU_SQR);
        printf("packed profile ranges: %d\n", ECC_PROFILE_RANGE);
#if ECC_WALK_TABLE
        printf("packed table pivot bytes: %d, table shared bytes %zu\n", ECC_TABLE_PIVOT_BYTES, eccPacked131::TW_SHARED_BYTES);
        printf("packed table global: %d\n", ECC_TABLE_GLOBAL);
        printf("packed table addend global: %d\n", ECC_TABLE_ADDEND_GLOBAL);
#endif
        printf("packed table walk: %d (%d branches, %zu shared bytes)\n", ECC_WALK_TABLE,
               ECC_WALK_TABLE ? ECC_TABLE_BRANCHES : 0, dynamicSharedBytes());
        const int blocks = int((laneCount() + ECC_THREADS - 1) / ECC_THREADS);
        eccPacked131::init<<<blocks, ECC_THREADS>>>(P, false);
        CUDA_CHECK(cudaGetLastError()); CUDA_CHECK(cudaDeviceSynchronize());
    }

    void launch(u64 iterBase) {
        P.iterBase = iterBase;
#if ECC_PROFILE_RANGE
        CUDA_CHECK(cudaProfilerStart());
#endif
        eccPacked131::walk<<<(P.threads + ECC_THREADS - 1) / ECC_THREADS, ECC_THREADS,
                             dynamicSharedBytes()>>>(P, P.x, P.y, P.pchain, P.dead, P.hist, P.seed, P.startIter, P.dp, P.dpCount, P.twConsts, denominators);
        CUDA_CHECK(cudaGetLastError());
#if ECC_PHASE_PROFILE
        profWarpSteps += double(P.threads / 32) * P.steps;
#endif
#if ECC_PROFILE_RANGE
        CUDA_CHECK(cudaDeviceSynchronize());
        CUDA_CHECK(cudaProfilerStop());
#endif
    }
    void reseed(u64 iterBase) {
        P.iterBase = iterBase;
        eccPacked131::init<<<int((laneCount() + ECC_THREADS - 1) / ECC_THREADS), ECC_THREADS>>>(P, true);
        CUDA_CHECK(cudaGetLastError());
        restartPending = false;
    }
    unsigned fetch(std::vector<DpRecord> &out) {
        CUDA_CHECK(cudaDeviceSynchronize());
        unsigned counts[3];
        CUDA_CHECK(cudaMemcpy(counts, P.dpCount, sizeof(counts), cudaMemcpyDeviceToHost));
        const unsigned n = counts[0] < P.dpCap ? counts[0] : P.dpCap;
        out.resize(n);
        if (n) CUDA_CHECK(cudaMemcpy(out.data(), P.dp, size_t(n) * sizeof(DpRecord), cudaMemcpyDeviceToHost));
        restartPending = counts[1] != 0;
        if (counts[0] || counts[1] || counts[2]) CUDA_CHECK(cudaMemset(P.dpCount, 0, sizeof(counts)));
        return counts[2] ? ECC_SEED_EXHAUSTED : counts[0];
    }
};
