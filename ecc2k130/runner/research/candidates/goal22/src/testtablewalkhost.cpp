// The table-walk selection primitives (packedtablewalk.cuh) on the HOST,
// against the reference (tablewalk.h, ref.h): the same probe as
// testtablewalkcuda.cu, run on the same shared-buffer layout, without a GPU.
//
// What this holds: the flat constant buffer twFillConsts builds, and the
// device-side phase, pivot, sign, tag and addend computed FROM that buffer,
// agree with the reference for every point.  It is what lets a layout change
// -- ECC_TABLE_PIVOT_BYTES packs the top words and swaps the nibble table for
// a byte table -- be checked bit for bit before a card is rented.  It does not
// exercise shared-memory loading, bank behaviour or the kernel's use of the
// primitives; test-table-walk-cuda and `--verify` do that on a GPU.
#ifndef ECC_NO_CUDA
#define ECC_NO_CUDA
#endif
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

int main() {
    typedef Ref<CfgF131> R;
    Solver<CfgF131> sol;
    sol.setup(eccF131::PX, eccF131::PY, eccF131::QX, eccF131::QY, eccF131::ELL_DEC, eccF131::S_DEC, 34, 1ull << 40);
    const TableWalk<CfgF131> &tw = sol.walk;
    if (!tw.consts.consistent()) { std::fprintf(stderr, "FAIL: L table\n"); return 1; }

    std::vector<uint32_t> shared(TW_WORDS);
    twFillConsts(tw, shared.data());
    const uint8_t *bytes = reinterpret_cast<const uint8_t *>(shared.data());

    auto pack = [](const unsigned long long *v) {
        P131 w;
        for (int i = 0; i < 5; ++i) w.v[i] = uint32_t(v[i / 2] >> (32 * (i & 1)));
        return w;
    };
    const int N = 4096;
    int badK = 0, badPivot = 0, badEps = 0, badTag = 0, badAdd = 0, ruleFired = 0;
    for (int i = 0; i < N; ++i) {
        const R::Point pt = R::startPoint(0x5eed0000ull + 7919ull * i, sol.basis, sol.target, 0, sol.ell, sol.spow);
        const P131 xn = pack(pt.x.v), xp = toPolynomial131(xn), yp = toPolynomial131(pack(pt.y.v));
        const int hw = R::weight(pt.x);
        const unsigned rawTag = tw.rawTag(pt, hw);
        unsigned long long hist = ECC_HIST_EMPTY;
        if (i % 4 == 1) hist = eccHistPush(ECC_HIST_EMPTY, rawTag ^ ECC_TAG_EPS);
        if (i % 8 == 2) hist = eccHistPush(eccHistPush(eccHistPush(ECC_HIST_EMPTY, 0x0123u ^ ECC_TAG_EPS), rawTag ^ ECC_TAG_EPS), 0x0123u);

        // device-side primitives, on the host, from the shared buffer
        const int k = twPhase(xn, hw, bytes + 4 * TW_PHASE_OFF, shared.data() + TW_INV_OFF);
        const int pivot = twPivot(xn, k, shared.data() + TW_MASK_OFF, bytes + 4 * TW_MAX_OFF, bytes + 4 * TW_LINV_OFF);
        const int eps = twCoordinate(yp, pivot, shared.data() + TW_ROW_OFF);
        unsigned long long h2 = hist;
        const unsigned tag = twSelect(xn, yp, hw, &h2, shared.data());
        P131 d, e;
        twAddend(tag, xp, yp, shared.data(), &d, &e);

        // reference
        const R::Elem rxn = R::nbCoords(pt.x), ryn = R::nbCoords(pt.y);
        const int rk = tw.phase(rxn, hw);
        unsigned long long piv[3];
        tw.consts.pivot(rxn.v, rk, piv);
        int rp = -1;
        for (int b = 0; b < 131; ++b) if ((piv[b >> 6] >> (b & 63)) & 1) rp = b;
        const int reps = tw.negationBit(rxn, ryn, rk);
        const unsigned rtag = TableWalk<CfgF131>::resolveTag(rawTag, hist);
        if (rtag != rawTag) ++ruleFired;
        const R::Point q = tw.addend(rtag);
        const P131 rd = toPolynomial131(pack(R::add(pt.x, q.x).v));
        const P131 re = toPolynomial131(pack(R::add(pt.y, q.y).v));
        badK += k != rk;
        badPivot += pivot != rp;
        badEps += eps != reps;
        badTag += tag != rtag;
        for (int w = 0; w < 5; ++w) badAdd += (d.v[w] != rd.v[w]) || (e.v[w] != re.v[w]);
    }
    std::printf("table walk host probe: %d points, cycle rule fired on %d\n", N, ruleFired);
    std::printf("  phase mismatches %d, pivot %d, sign %d, tag %d, addend words %d\n", badK, badPivot, badEps, badTag, badAdd);
    std::printf("  branches %d, pivot bytes %d, shared bytes %zu\n", TW_H, ECC_TABLE_PIVOT_BYTES, TW_SHARED_BYTES);
    const bool ok = !badK && !badPivot && !badEps && !badTag && !badAdd && ruleFired >= N / 4;
    std::printf("%s\n", ok ? "PASS" : "FAIL");
    return ok ? 0 : 1;
}
