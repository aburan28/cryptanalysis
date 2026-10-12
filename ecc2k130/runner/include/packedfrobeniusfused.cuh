// Frobenius pass fusion. Included inside namespace eccPacked131.
// The next prefix chain visits slots in the order just used by the inverse;
// reversing that order on the following step preserves each point's update.
#if ECC_WALK_TABLE || !ECC_PACKED_POLY_STATE || ECC_PACKED_WEIGHTED_PREFIX != 2 || !ECC_PACKED_SHARED_SIGMA
#error "Frobenius fusion requires polynomial state, weighted prefix 2 and shared sigma"
#endif

__device__ __forceinline__ void frobeniusSelect(
    const WalkParams<unsigned> &p, unsigned *__restrict__ statePrefix,
    unsigned *__restrict__ stateDead, const unsigned long long *__restrict__ stateSeed,
    const unsigned long long *__restrict__ stateStart, DpRecord *__restrict__ reports,
    unsigned *__restrict__ reportCounts, unsigned *__restrict__ denominators,
    const P131 &xp, const P131 &yp, int slot, int tid,
    unsigned long long now, bool guard, bool first, P131 *prod) {
    const size_t id = size_t(slot) * p.threads + tid;
    const P131 x = fromPolynomial131(xp), y = fromPolynomial131(yp);
    const int hw = weight(x);
    if (!goal22ReadDead(stateDead, id)) {
        if (hw <= p.dpWeight) {
            if ((stateSeed[id] & 0xffffull) == 0xffffull) atomicAdd(reportCounts + 2, 1u);
            const unsigned dest = atomicAdd(reportCounts, 1u);
            if (dest < p.dpCap) {
                DpRecord rec;
                rec.seed = stateSeed[id];
                rec.iters = now - stateStart[id];
                toLimbs(x, rec.x);
                toLimbs(y, rec.y);
                reports[dest] = rec;
            }
            goal22WriteDead(stateDead, id, 1);
        } else if (guard && now - stateStart[id] >= p.maxIters) {
            if ((stateSeed[id] & 0xffffull) == 0xffffull) atomicAdd(reportCounts + 2, 1u);
            goal22WriteDead(stateDead, id, 1);
            atomicAdd(reportCounts + 1, 1u);
        }
    }
    const int jump = (hw >> 1) & 7;
    const SigmaWalkPair131 sigmas = sigmaWalkNetworkPairShared131(x, y, jump);
    const P131 dp = toPolynomial131(add131(x, sigmas.first));
    const P131 ep = toPolynomial131(add131(y, sigmas.second));
    if (first) {
        *prod = dp;
        store(statePrefix, slot, tid, p.threads, ep);
    } else {
        const PolynomialPair pair = mulPolynomialPair131(*prod, ep, dp);
        store(statePrefix, slot, tid, p.threads, pair.first);
        *prod = pair.second;
    }
    // The fused update never reads cached jump tags. Keep the denominator
    // canonical so the inverse loop also needs no tag-removal mask. This
    // scratch buffer is rebuilt at launch entry and is not checkpointed.
    store(denominators, slot, tid, p.threads, dp);
}

static __global__ void ECC_BOUNDS walk(
    WalkParams<unsigned> p, unsigned *__restrict__ stateX, unsigned *__restrict__ stateY,
    unsigned *__restrict__ statePrefix, unsigned *__restrict__ stateDead,
    unsigned long long *__restrict__ stateHistory,
    const unsigned long long *__restrict__ stateSeed,
    const unsigned long long *__restrict__ stateStart, DpRecord *__restrict__ reports,
    unsigned *__restrict__ reportCounts, const unsigned *__restrict__ walkConstants,
    unsigned *__restrict__ denominators) {
    const int tid = blockIdx.x * blockDim.x + threadIdx.x;
    initSigmaWalkShared131();
    if (tid >= p.threads || p.steps <= 0) return;
    (void)stateHistory;
    (void)walkConstants;
    P131 prod;
    const bool initialGuard = p.maxIters && p.iterBase % ECC_GUARD_PERIOD == 0;
#pragma unroll 1
    for (int slot = 0; slot < ECC_BATCH; ++slot) {
        frobeniusSelect(p, statePrefix, stateDead, stateSeed, stateStart, reports,
            reportCounts, denominators, load(stateX, slot, tid, p.threads),
            load(stateY, slot, tid, p.threads), slot, tid, p.iterBase,
            initialGuard, slot == 0, &prod);
    }
#pragma unroll 1
    for (int step = 0; step < p.steps; ++step) {
        const bool forward = (step & 1) != 0;
        const bool last = step + 1 == p.steps;
        const unsigned long long now = p.iterBase + step + 1;
        const bool guard = p.maxIters && now % ECC_GUARD_PERIOD == 0;
        P131 inv = batchInverse131(prod, p.threads);
        P131 next = {};
#pragma unroll 1
        for (int i = 0; i < ECC_BATCH; ++i) {
            const int slot = forward ? i : ECC_BATCH - 1 - i;
            const P131 x = load(stateX, slot, tid, p.threads);
            const P131 y = load(stateY, slot, tid, p.threads);
            const P131 w = load(statePrefix, slot, tid, p.threads);
            const P131 dp = load(denominators, slot, tid, p.threads);
            P131 lambda;
            if (i + 1 < ECC_BATCH) {
#if ECC_PACKED_CHAIN_FIRST
                const PolynomialPair pair = mulPolynomialPair131(inv, dp, w);
                lambda = pair.second;
                inv = pair.first;
#else
                const PolynomialPair pair = mulPolynomialPair131(inv, w, dp);
                lambda = pair.first;
                inv = pair.second;
#endif
            } else {
                lambda = mulPolynomial131(inv, w);
            }
            const P131 nx = add131(add131(squarePolynomial131(lambda), lambda), dp);
            const P131 ny = add131(add131(mulPolynomial131(lambda, add131(x, nx)), nx), y);
            store(stateX, slot, tid, p.threads, nx);
            store(stateY, slot, tid, p.threads, ny);
            if (!last) {
                frobeniusSelect(p, statePrefix, stateDead, stateSeed, stateStart,
                    reports, reportCounts, denominators, nx, ny, slot, tid,
                    now, guard, i == 0, &next);
            }
        }
        prod = next;
    }
}
