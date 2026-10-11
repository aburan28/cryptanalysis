// Independent checker: numeric-order specialization, equation ROW elimination,
// exact branch cardinality, direct original equations, and Boolean staircase.
// Does not include or call the producer or its interpolation.
#include "abi.h"
#include <algorithm>
#include <array>
#include <chrono>
#include <mutex>
#include <stdexcept>
#include <vector>

struct Checker {
    uint32_t x, y, equations, limbs;
    std::vector<uint64_t> rows;
    std::mutex mutex;
    Checker(uint32_t a, uint32_t b, uint32_t e)
        : x(a), y(b), equations(e), limbs((e+63)/64), rows(e*(a+1)) {}
};
static uint64_t monomial(const void* masks, uint32_t width, uint32_t i) {
    if (width == 32) return static_cast<const uint32_t*>(masks)[i];
    return static_cast<const uint64_t*>(masks)[i];
}
static void validate(const Checker& w, const void* masks, uint32_t width,
                     const uint64_t* coefficients, uint32_t count) {
    if ((width != 32 && width != 64) || count > TERM_LIMIT ||
        (count && (!masks || !coefficients))) throw std::invalid_argument("packed input");
    for (uint32_t i=0; i<count; ++i) {
        if (monomial(masks,width,i) >> (w.x+w.y)) throw std::invalid_argument("mask range");
        if (w.equations%64 &&
            coefficients[size_t(i)*w.limbs+w.limbs-1] >> (w.equations%64))
            throw std::invalid_argument("coefficient range");
    }
}
static int check(Checker& w, const void* masks, uint32_t width, const uint64_t* coefficients,
                 uint32_t count, const uint64_t* roots, uint32_t root_count,
                 const uint64_t* terms, uint32_t term_count,
                 const uint32_t* offsets, uint32_t row_count, BranchStats& stats) {
    validate(w,masks,width,coefficients,count);
    if (root_count>ROOT_LIMIT || term_count>TERM_LIMIT || row_count>4096 ||
        (root_count && !roots) || (term_count && !terms) || !offsets ||
        offsets[0] || offsets[row_count]!=term_count) return 6;
    for (uint32_t i=0; i<root_count; ++i)
        if (roots[i] >> (w.x+w.y) || (i && roots[i-1]>=roots[i])) return 2;
    std::vector<uint64_t> leading;
    for (uint32_t i=0; i<row_count; ++i) {
        if (offsets[i]>=offsets[i+1] || offsets[i+1]>term_count) return 1;
        uint64_t lm=terms[offsets[i]];
        for (uint32_t j=offsets[i]; j<offsets[i+1]; ++j) {
            auto m=terms[j];
            if (m >> (w.x+w.y) || (j>offsets[i] && terms[j-1]>=m)) return 1;
            int d=__builtin_popcountll(m), old=__builtin_popcountll(lm);
            if (d>old || (d==old && m<lm)) lm=m;
        }
        leading.push_back(lm);
    }
    const uint64_t low=(uint64_t(1)<<w.x)-1, rhs_bit=uint64_t(1)<<w.y;
    std::fill(w.rows.begin(),w.rows.end(),0);
    for (uint32_t t=0; t<count; ++t) {
        auto m=monomial(masks,width,t), left=m&low, right=m>>w.x;
        bool nonzero=false;
        for (uint32_t limb=0; limb<w.limbs; ++limb)
            nonzero |= coefficients[size_t(t)*w.limbs+limb]!=0;
        if (!nonzero) continue;
        if ((left && (left&(left-1))) || (right && (right&(right-1)))) return 7;
        uint32_t column=left ? uint32_t(__builtin_ctzll(left))+1 : 0;
        uint64_t residual=right ? right : rhs_bit;
        for (uint32_t equation=0; equation<w.equations; ++equation)
            if ((coefficients[size_t(t)*w.limbs+equation/64]>>(equation%64))&1)
                w.rows[equation*(w.x+1)+column] ^= residual;
    }
    // Binary increment toggles the low k+1 x bits, k=ctz(new assignment).
    // Prefix XORs apply that exact delta to independently decoded equation
    // rows. This is numeric order, not the producer's Gray-code column order.
    std::array<uint64_t,128> current{};
    for (uint32_t equation=0; equation<w.equations; ++equation) {
        current[equation]=w.rows[equation*(w.x+1)];
        for (uint32_t j=2; j<=w.x; ++j)
            w.rows[equation*(w.x+1)+j] ^= w.rows[equation*(w.x+1)+j-1];
    }
    // Reconstruct every branch independently. Count includes ALL solutions of
    // each affine system, even if no proposed root has that branch prefix.
    for (uint32_t assignment=0; assignment<uint32_t(1)<<w.x; ++assignment) {
        ++stats.branches;
        if (assignment) {
            const uint32_t carry=uint32_t(__builtin_ctz(assignment))+1;
            for (uint32_t equation=0; equation<w.equations; ++equation)
                current[equation] ^= w.rows[equation*(w.x+1)+carry];
        }
        std::array<uint64_t,63> pivots{};
        uint32_t rank=0;
        bool consistent=true;
        for (uint32_t equation=0; equation<w.equations; ++equation) {
            uint64_t row=current[equation];
            while (row & (rhs_bit-1)) {
                uint32_t pivot=uint32_t(__builtin_ctzll(row));
                if (!pivots[pivot]) { pivots[pivot]=row; ++rank; break; }
                row ^= pivots[pivot];
            }
            if (row==rhs_bit) { consistent=false; break; }
        }
        if (consistent) {
            ++stats.consistent;
            if (w.y-rank>8 || stats.roots+(uint64_t(1)<<(w.y-rank))>ROOT_LIMIT) return 5;
            stats.roots += uint64_t(1)<<(w.y-rank);
        }
    }
    if (stats.roots!=root_count) return 3;
    // Count + distinct actual input roots proves the proposed list is complete.
    for (uint32_t i=0; i<root_count; ++i) {
        std::array<uint64_t,2> value{};
        for (uint32_t t=0; t<count; ++t)
            if ((monomial(masks,width,t)&roots[i])==monomial(masks,width,t))
                for (uint32_t limb=0; limb<w.limbs; ++limb)
                    value[limb] ^= coefficients[size_t(t)*w.limbs+limb];
        if (value[0] || value[1]) return 2;
        for (uint32_t row=0; row<row_count; ++row) {
            bool parity=false;
            for (uint32_t t=offsets[row]; t<offsets[row+1]; ++t)
                parity ^= (terms[t]&roots[i])==terms[t];
            if (parity) return 4;
        }
    }
    auto allowed=[&](uint64_t m) {
        for (auto lm: leading) {
            if (++stats.work>PROOF_BUDGET) throw std::length_error("proof budget");
            if ((m&lm)==lm) return false;
        }
        return true;
    };
    std::vector<uint64_t> staircase;
    if (allowed(0)) staircase.push_back(0);
    for (size_t cursor=0; cursor<staircase.size(); ++cursor) {
        auto m=staircase[cursor];
        uint32_t first=m ? 64u-uint32_t(__builtin_clzll(m)) : 0;
        for (uint32_t j=first; j<w.x+w.y; ++j) {
            auto child=m|(uint64_t(1)<<j);
            if (allowed(child)) {
                if (staircase.size()==ROOT_LIMIT) return 5;
                staircase.push_back(child);
            }
        }
    }
    stats.standard=staircase.size();
    if (stats.standard!=stats.roots) return 4;
    for (uint32_t i=0; i<row_count; ++i) {
        for (uint32_t j=0; j<row_count; ++j)
            if (i!=j && (leading[i]&leading[j])==leading[j]) return 4;
        for (uint32_t t=offsets[i]; t<offsets[i+1]; ++t)
            if (terms[t]!=leading[i])
                for (auto lm: leading) if ((terms[t]&lm)==lm) return 4;
    }
    return 0;
}
extern "C" uint64_t check_stats_size() { return sizeof(BranchStats); }
extern "C" void* check_create(uint32_t x,uint32_t y,uint32_t e) {
    if (!x || x>20 || !y || y>62 || x+y>63 || !e || e>128) return nullptr;
    try { return new Checker(x,y,e); } catch (...) { return nullptr; }
}
extern "C" void check_destroy(void* p) { delete static_cast<Checker*>(p); }
extern "C" int branch_check(void* p, const void* masks, uint32_t width,
    const uint64_t* coefficients, uint32_t count, const uint64_t* roots, uint32_t root_count,
    const uint64_t* terms, uint32_t term_count, const uint32_t* offsets, uint32_t row_count,
    BranchStats* stats) {
    if (!p || !stats) return 6;
    *stats={};
    auto started=std::chrono::steady_clock::now();
    int code=8;
    try {
        auto& w=*static_cast<Checker*>(p);
        std::lock_guard<std::mutex> guard(w.mutex);
        code=check(w,masks,width,coefficients,count,roots,root_count,terms,term_count,offsets,row_count,*stats);
    } catch (const std::length_error&) { code=5; }
      catch (const std::invalid_argument&) { code=6; }
      catch (...) { code=8; }
    stats->evaluation=std::chrono::duration<double>(std::chrono::steady_clock::now()-started).count();
    return code;
}
extern "C" int branch_evaluate(void* p,const void* masks,uint32_t width,
    const uint64_t* coefficients,uint32_t count,uint64_t assignment,uint64_t* output) {
    if (!p || !output) return 6;
    try {
        auto& w=*static_cast<Checker*>(p);
        std::lock_guard<std::mutex> guard(w.mutex);
        validate(w,masks,width,coefficients,count);
        if (assignment>>(w.x+w.y)) return 6;
        output[0]=output[1]=0;
        for (uint32_t i=0; i<count; ++i)
            if ((monomial(masks,width,i)&assignment)==monomial(masks,width,i))
                for (uint32_t limb=0; limb<w.limbs; ++limb)
                    output[limb] ^= coefficients[size_t(i)*w.limbs+limb];
        return 0;
    } catch (const std::invalid_argument&) { return 6; }
      catch (...) { return 8; }
}
