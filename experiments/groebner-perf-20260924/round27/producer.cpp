// Affine-in-each-block Boolean systems: Gray-code specialization and column
// elimination over equation vectors. All numeric state is reset per call.
#include "abi.h"
#include <array>
#include <chrono>
#include <mutex>
#include <string>
#include <stdexcept>
#include <vector>
#include "interpolation.hpp"

struct Word {
    uint64_t lo = 0, hi = 0;
    Word& operator^=(const Word& b) { lo ^= b.lo; hi ^= b.hi; return *this; }
    bool nonzero() const { return lo || hi; }
    int pivot() const { return hi ? 127 - __builtin_clzll(hi) : 63 - __builtin_clzll(lo); }
};
struct Producer {
    uint32_t nx, ny, equations, limbs;
    std::vector<Word> layout, columns;
    std::mutex mutex;
    Producer(uint32_t x, uint32_t y, uint32_t e)
      : nx(x), ny(y), equations(e), limbs((e+63)/64),
        layout((x+1)*(y+1)), columns(y+1) {}
};
struct Produced {
    BranchStats stats{};
    std::vector<Mask> roots;
    std::vector<Polynomial> basis;
};
static thread_local std::string error_text;
static thread_local uint32_t error_code;
static void dimensions(uint32_t x, uint32_t y, uint32_t e) {
    if (!x || x > 20 || !y || y > 62 || x+y > 63 || !e || e > 128)
        throw std::invalid_argument("dimensions: x 1..20, y >= 1, x+y <= 63, equations 1..128");
}
static uint64_t mask_at(const void* masks, uint32_t width, uint32_t i) {
    return width == 32 ? static_cast<const uint32_t*>(masks)[i]
                       : static_cast<const uint64_t*>(masks)[i];
}
static Produced solve(Producer& w, const void* masks, uint32_t width,
                      const uint64_t* coefficients, uint32_t count) {
    if ((width != 32 && width != 64) || count > TERM_LIMIT ||
        (count && (!masks || !coefficients))) throw std::invalid_argument("packed extents");
    Produced out;
    out.roots.reserve(ROOT_LIMIT);
    const auto start = std::chrono::steady_clock::now();
    const uint64_t xmask = (uint64_t(1) << w.nx)-1;
    std::fill(w.layout.begin(), w.layout.end(), Word{});
    for (uint32_t i = 0; i < count; ++i) {
        const auto mask = mask_at(masks, width, i);
        if (mask >> (w.nx+w.ny)) throw std::invalid_argument("mask outside ring");
        Word c{coefficients[size_t(i)*w.limbs], w.limbs == 2 ? coefficients[size_t(i)*2+1] : 0};
        if (w.equations%64 && coefficients[size_t(i)*w.limbs+w.limbs-1] >> (w.equations%64))
            throw std::invalid_argument("coefficient outside equations");
        if (!c.nonzero()) continue;
        const auto x = mask & xmask, y = mask >> w.nx;
        if (__builtin_popcountll(x) > 1 || __builtin_popcountll(y) > 1)
            throw std::domain_error("nonlinear term within a block");
        const uint32_t xi = x ? uint32_t(__builtin_ctzll(x))+1 : 0;
        const uint32_t yi = y ? uint32_t(__builtin_ctzll(y))+1 : 0;
        w.layout[xi*(w.ny+1)+yi] ^= c;
    }
    std::copy_n(w.layout.begin(), w.ny+1, w.columns.begin());
    for (uint32_t serial = 0; serial < uint32_t(1) << w.nx; ++serial) {
        if (serial) {
            const uint32_t changed = uint32_t(__builtin_ctz(serial))+1;
            for (uint32_t j = 0; j <= w.ny; ++j)
                w.columns[j] ^= w.layout[changed*(w.ny+1)+j];
        }
        ++out.stats.branches;
        const uint64_t x = serial ^ (serial >> 1);
        std::array<Word, 128> pivots{};
        std::array<uint64_t, 128> combinations{};
        std::array<uint64_t,63> kernel{};
        uint32_t nullity=0;
        for (uint32_t j = 0; j < w.ny; ++j) {
            Word column = w.columns[j+1];
            uint64_t combination = uint64_t(1) << j;
            while (column.nonzero()) {
                int p = column.pivot();
                if (!pivots[p].nonzero()) {
                    pivots[p] = column; combinations[p] = combination; break;
                }
                column ^= pivots[p]; combination ^= combinations[p];
            }
            if (!column.nonzero()) kernel[nullity++]=combination;
        }
        Word rhs = w.columns[0];
        uint64_t particular = 0;
        while (rhs.nonzero()) {
            int p = rhs.pivot();
            if (!pivots[p].nonzero()) break;
            rhs ^= pivots[p]; particular ^= combinations[p];
        }
        if (rhs.nonzero()) continue;
        ++out.stats.consistent;
        if (nullity > 8 || out.roots.size() + (uint64_t(1) << nullity) > ROOT_LIMIT)
            throw std::length_error("complete root set exceeds 256; no partial basis");
        std::array<uint64_t,ROOT_LIMIT> ys{};
        ys[0]=particular;
        uint32_t used=1;
        for (uint32_t j=0; j<nullity; ++j) {
            const uint32_t prior=used;
            for (uint32_t i=0; i<prior; ++i) ys[used++]=ys[i]^kernel[j];
        }
        for (uint32_t i=0; i<used; ++i) out.roots.push_back(x | (ys[i] << w.nx));
    }
    std::sort(out.roots.begin(), out.roots.end());
    out.stats.roots = out.roots.size();
    const auto evaluated = std::chrono::steady_clock::now();
    out.stats.evaluation = std::chrono::duration<double>(evaluated-start).count();
    out.basis = interpolate(w.nx+w.ny, out.roots, out.stats);
    out.stats.interpolation = std::chrono::duration<double>(
        std::chrono::steady_clock::now()-evaluated).count();
    return out;
}
extern "C" const char* branch_error() { return error_text.c_str(); }
extern "C" uint32_t branch_error_code() { return error_code; }
extern "C" uint64_t branch_stats_size() { return sizeof(BranchStats); }
extern "C" void* branch_create(uint32_t x, uint32_t y, uint32_t e) {
    try { dimensions(x,y,e); return new Producer(x,y,e); }
    catch (const std::exception& e) { error_text=e.what(); error_code=6; return nullptr; }
}
extern "C" void branch_destroy(void* p) { delete static_cast<Producer*>(p); }
extern "C" void* branch_solve(void* p, const void* masks, uint32_t width,
                             const uint64_t* c, uint32_t count, BranchStats* stats) {
    try {
        if (!p || !stats) throw std::invalid_argument("null producer or result");
        *stats={};
        auto& w=*static_cast<Producer*>(p);
        std::lock_guard<std::mutex> guard(w.mutex);
        auto result=solve(w,masks,width,c,count);
        *stats=result.stats;
        return new Produced(std::move(result));
    } catch (const std::length_error& e) { error_text=e.what(); error_code=5; }
      catch (const std::domain_error& e) { error_text=e.what(); error_code=7; }
      catch (const std::invalid_argument& e) { error_text=e.what(); error_code=6; }
      catch (const std::exception& e) { error_text=e.what(); error_code=8; }
    return nullptr;
}
extern "C" uint32_t branch_rows(const void* p) {
    return p ? uint32_t(static_cast<const Produced*>(p)->basis.size()) : 0;
}
extern "C" uint32_t branch_row_size(const void* p, uint32_t row) {
    const auto* r=static_cast<const Produced*>(p);
    return r && row<r->basis.size() ? uint32_t(r->basis[row].size()) : 0;
}
extern "C" const uint64_t* branch_row(const void* p, uint32_t row) {
    const auto* r=static_cast<const Produced*>(p);
    return r && row<r->basis.size() ? r->basis[row].data() : nullptr;
}
extern "C" const uint64_t* branch_roots(const void* p) {
    return p ? static_cast<const Produced*>(p)->roots.data() : nullptr;
}
extern "C" void branch_result_destroy(void* p) { delete static_cast<Produced*>(p); }
