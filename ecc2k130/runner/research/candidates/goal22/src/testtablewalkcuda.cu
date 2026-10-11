// Device table-walk primitives against the reference (tablewalk.h, ref.h).
//
// For random subgroup points the device computes the Frobenius phase, the
// pivot coordinate, the negation bit, the resolved tag under a history that
// trips the cycle rule, and the polynomial-basis addend; each must equal the
// reference.  The end-to-end check of the kernel itself is
// `ecc2k130 --packed --verify N`, which re-walks device reports on the host.
#include <cuda_runtime.h>
#include <cstdio>
#include <cstdlib>
#include <vector>
#include "../include/curveparams.h"
#include "../include/kernel.h"
#include "../include/solver.h"
#include "../include/packed131.h"
#include "../include/packedtablewalk.cuh"

#if !ECC_WALK_TABLE
#error "build with -DECC_WALK_TABLE=1"
#endif
using eccPacked131::P131;
using namespace eccPacked131;

struct In { P131 xn, yp, xp; int hw; unsigned long long hist; };
struct Out { int k, pivot, eps; unsigned tag; P131 d, e; };

static void checked(cudaError_t s) {
    if (s != cudaSuccess) { std::fprintf(stderr, "CUDA: %s\n", cudaGetErrorString(s)); std::exit(1); }
}

__global__ void probe(const In *in, Out *out, int n, const uint32_t *consts) {
#if ECC_TABLE_ADDEND_GLOBAL
    extern __shared__ uint32_t sel[];
    twLoadShared(sel, consts + TW_MASK_OFF, TW_SEL_WORDS);
    const uint32_t *tab = consts;
#else
    extern __shared__ uint32_t sel[];
    twLoadShared(sel, consts);
    const uint32_t *tab = sel;
#endif
    const int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= n) return;
    In a = in[i];
    Out o;
    const uint8_t *bytes = reinterpret_cast<const uint8_t *>(sel);
    o.k = twPhase(a.xn, a.hw, bytes + 4 * (TW_PHASE_OFF - TW_SEL0), sel + (TW_INV_OFF - TW_SEL0));
    o.pivot = twPivot(a.xn, o.k, sel + (TW_MASK_OFF - TW_SEL0), bytes + 4 * (TW_MAX_OFF - TW_SEL0),
                      bytes + 4 * (TW_LINV_OFF - TW_SEL0));
    o.eps = twCoordinate(a.yp, o.pivot, sel + (TW_ROW_OFF - TW_SEL0));
    unsigned long long hist = a.hist;
    o.tag = twSelect(a.xn, a.yp, a.hw, &hist, sel);
    twAddend(o.tag, a.xp, a.yp, tab, &o.d, &o.e);
    out[i] = o;
}

int main() {
    typedef Ref<CfgF131> R;
    Solver<CfgF131> sol;
    sol.setup(eccF131::PX, eccF131::PY, eccF131::QX, eccF131::QY, eccF131::ELL_DEC, eccF131::S_DEC, 34, 1ull << 40);
    const TableWalk<CfgF131> &tw = sol.walk;
    if (!tw.consts.consistent()) { std::fprintf(stderr, "FAIL: L table\n"); return 1; }

    std::vector<uint32_t> consts(TW_WORDS);
    twFillConsts(tw, consts.data());
    uint32_t *dConsts;
    checked(cudaMalloc(&dConsts, consts.size() * 4));
    checked(cudaMemcpy(dConsts, consts.data(), consts.size() * 4, cudaMemcpyHostToDevice));

    auto pack = [](const unsigned long long *v) {
        P131 w;
        for (int i = 0; i < 5; ++i) w.v[i] = uint32_t(v[i / 2] >> (32 * (i & 1)));
        return w;
    };
    const int N = 4096;
    std::vector<In> in(N);
    std::vector<R::Point> pts(N);
    std::vector<unsigned> rawTags(N);
    for (int i = 0; i < N; ++i) {
        // Start points of random seeds are random subgroup elements.
        pts[i] = R::startPoint(0x5eed0000ull + 7919ull * i, sol.basis, sol.target, 0, sol.ell, sol.spow);
        in[i].xn = pack(pts[i].x.v);
        in[i].xp = toPolynomial131(in[i].xn);
        in[i].yp = toPolynomial131(pack(pts[i].y.v));
        in[i].hw = R::weight(pts[i].x);
        rawTags[i] = tw.rawTag(pts[i], in[i].hw);
        // Every fourth point sees a history the raw tag would undo, every
        // eighth one a 4-cycle it would close; the rest an empty history.
        in[i].hist = ECC_HIST_EMPTY;
        if (i % 4 == 1) in[i].hist = eccHistPush(ECC_HIST_EMPTY, rawTags[i] ^ ECC_TAG_EPS);
        if (i % 8 == 2) in[i].hist = eccHistPush(eccHistPush(eccHistPush(ECC_HIST_EMPTY, 0x0123u ^ ECC_TAG_EPS), rawTags[i] ^ ECC_TAG_EPS), 0x0123u);
    }
    In *dIn; Out *dOut;
    checked(cudaMalloc(&dIn, N * sizeof(In)));
    checked(cudaMalloc(&dOut, N * sizeof(Out)));
    checked(cudaMemcpy(dIn, in.data(), N * sizeof(In), cudaMemcpyHostToDevice));
    if (TW_SHARED_BYTES > 48 * 1024)
        checked(cudaFuncSetAttribute(probe, cudaFuncAttributeMaxDynamicSharedMemorySize, int(TW_SHARED_BYTES)));
    probe<<<(N + 127) / 128, 128, TW_SHARED_BYTES>>>(dIn, dOut, N, dConsts);
    checked(cudaGetLastError());
    checked(cudaDeviceSynchronize());
    std::vector<Out> out(N);
    checked(cudaMemcpy(out.data(), dOut, N * sizeof(Out), cudaMemcpyDeviceToHost));

    int badK = 0, badPivot = 0, badEps = 0, badTag = 0, badAdd = 0, ruleFired = 0;
    for (int i = 0; i < N; ++i) {
        const R::Elem xn = R::nbCoords(pts[i].x), yn = R::nbCoords(pts[i].y);
        const int k = tw.phase(xn, in[i].hw);
        unsigned long long piv[3];
        tw.consts.pivot(xn.v, k, piv);
        int p = -1;
        for (int b = 0; b < 131; ++b) if ((piv[b >> 6] >> (b & 63)) & 1) p = b;
        const int eps = tw.negationBit(xn, yn, k);
        const unsigned tag = TableWalk<CfgF131>::resolveTag(rawTags[i], in[i].hist);
        if (tag != rawTags[i]) ++ruleFired;
        const R::Point q = tw.addend(tag);
        const P131 d = toPolynomial131(pack(R::add(pts[i].x, q.x).v));
        const P131 e = toPolynomial131(pack(R::add(pts[i].y, q.y).v));
        badK += out[i].k != k;
        badPivot += out[i].pivot != p;
        badEps += out[i].eps != eps;
        badTag += out[i].tag != tag;
        for (int w = 0; w < 5; ++w) badAdd += (out[i].d.v[w] != d.v[w]) || (out[i].e.v[w] != e.v[w]);
    }
    std::printf("table walk device probe: %d points, cycle rule fired on %d\n", N, ruleFired);
    std::printf("  phase mismatches %d, pivot %d, sign %d, tag %d, addend words %d\n", badK, badPivot, badEps, badTag, badAdd);
    std::printf("  branches %d, shared bytes %zu, addend global %d\n",
                TW_H, TW_SHARED_BYTES, ECC_TABLE_ADDEND_GLOBAL);
    const bool ok = !badK && !badPivot && !badEps && !badTag && !badAdd && ruleFired >= N / 4;
    std::printf("%s\n", ok ? "PASS" : "FAIL");
    return ok ? 0 : 1;
}
