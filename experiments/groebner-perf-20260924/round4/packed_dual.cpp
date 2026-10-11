// Packed-ANF evaluation + unchanged Buchberger-Moller interpolation.
// Derived from round2/boolean_dual.cpp; the frozen comparison source is retained.
// These are established algorithms, not a claim of a novel F6 algorithm.
// Ring: GF(2)[x]/(x_i^2+x_i), grevlex x0>x1>...; squarefree mask encoding.
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <ctime>
#include <iomanip>
#include <iostream>
#include <set>
#include <mutex>
#include <string>
#include <stdexcept>
#include <vector>
using Mask=uint32_t;
using Polynomial=std::vector<Mask>;
using Bits=std::vector<uint64_t>;
using Clock=std::chrono::steady_clock;
static double seconds(Clock::time_point t) {
    return std::chrono::duration<double>(Clock::now()-t).count();
}
struct Grevlex {
    bool operator()(Mask a,Mask b) const {
        int da=__builtin_popcount(a),db=__builtin_popcount(b);
        return da!=db ? da<db : a>b;
    }
};
static int lead(const Bits& a) {
    for(int w=int(a.size())-1;w>=0;--w)
        if(a[w]) return w*64+63-__builtin_clzll(a[w]);
    return -1;
}
static void xor_bits(Bits& a,const Bits& b) {
    for(size_t i=0;i<a.size();++i) a[i]^=b[i];
}
struct DualResult {
    std::vector<Polynomial> basis;
    std::vector<Mask> roots;
    size_t standard_monomials=0,frontier_visits=0;
    double evaluation=0,interpolation=0;
};
struct PackedWorkspace {
    const uint32_t n, equations, limbs;
    std::vector<uint8_t> alive;
    std::vector<uint64_t> table;
    std::mutex mutex;
    PackedWorkspace(uint32_t variables, uint32_t count)
        : n(variables), equations(count), limbs((count+63)/64),
          alive(size_t(1)<<variables), table(size_t(1)<<variables) {}
};
static DualResult packed_basis(PackedWorkspace& workspace, const uint32_t* masks,
                              const uint64_t* coefficients, uint32_t count) {
    const uint32_t n=workspace.n, limbs=workspace.limbs;
    const Mask universe=Mask(1)<<n;
    // Validate even zero-coefficient terms. Duplicate masks cancel by XOR.
    for(uint32_t i=0;i<count;++i) {
        if(masks[i]>=universe) throw std::invalid_argument("monomial mask out of range");
        if(workspace.equations%64 &&
           coefficients[size_t(i)*limbs+limbs-1]>>(workspace.equations%64))
            throw std::invalid_argument("coefficient out of range");
    }
    DualResult out;
    auto start=Clock::now();
    auto& alive=workspace.alive;
    auto& table=workspace.table;
    std::fill(alive.begin(),alive.end(),1);
    for(uint32_t limb=0;limb<limbs;++limb) {
        std::fill(table.begin(),table.end(),0);
        for(uint32_t i=0;i<count;++i)
            table[masks[i]]^=coefficients[size_t(i)*limbs+limb];
        for(Mask step=1;step<universe;step<<=1)
            for(Mask block=0;block<universe;block+=2*step)
                for(Mask offset=0;offset<step;++offset)
                    table[block+step+offset]^=table[block+offset];
        for(Mask a=0;a<universe;++a) alive[a]&=(table[a]==0);
    }
    constexpr size_t root_cap=256;
    for(Mask a=0;a<universe;++a) if(alive[a]) out.roots.push_back(a);
    out.evaluation=seconds(start);
    // Returning a partial point set would silently enlarge the input ideal.
    // Fail explicitly so a caller can fall back, charging the failed attempt.
    if(out.roots.size()>root_cap) throw std::runtime_error("root cap exceeded; complete basis not computed");
    start=Clock::now();
    const size_t r=out.roots.size(),words=(r+63)/64;
    std::vector<Bits> values(r),combinations(r);
    std::vector<Mask> standard,leading;
    std::set<Mask,Grevlex> frontier;
    std::set<Mask> discovered;
    frontier.insert(0);discovered.insert(0);
    while(!frontier.empty()) {
        Mask monomial=*frontier.begin();frontier.erase(frontier.begin());
        ++out.frontier_visits;
        if(std::any_of(leading.begin(),leading.end(),[&](Mask lm){return (lm&monomial)==lm;})) continue;
        Bits value(words),combo(words);
        for(size_t i=0;i<r;++i)
            if((monomial&out.roots[i])==monomial) value[i/64]|=UINT64_C(1)<<(i%64);
        int pivot;
        while((pivot=lead(value))>=0 && !values[pivot].empty()) {
            xor_bits(value,values[pivot]);xor_bits(combo,combinations[pivot]);
        }
        if(pivot<0) {
            // Evaluation dependence: m + sum(combo_j * standard_j) vanishes
            // at every root. All tail monomials are standard and smaller.
            Polynomial g={monomial};
            for(size_t j=0;j<standard.size();++j)
                if((combo[j/64]>>(j%64))&1u) g.push_back(standard[j]);
            std::sort(g.begin(),g.end());out.basis.push_back(std::move(g));
            leading.push_back(monomial);
        } else {
            if(standard.size()>=r) throw std::runtime_error("evaluation rank invariant");
            size_t j=standard.size();combo[j/64]^=UINT64_C(1)<<(j%64);
            values[pivot]=std::move(value);combinations[pivot]=std::move(combo);
            standard.push_back(monomial);
            for(uint32_t variable=0;variable<n;++variable) {
                Mask multiple=monomial|(Mask(1)<<variable);
                if(discovered.insert(multiple).second) frontier.insert(multiple);
            }
        }
    }
    if(standard.size()!=r) throw std::runtime_error("incomplete quotient basis");
    out.standard_monomials=standard.size();
    auto lm=[](const Polynomial& p){return *std::max_element(p.begin(),p.end(),Grevlex{});};
    std::sort(out.basis.begin(),out.basis.end(),[&](const Polynomial& a,const Polynomial& b){return Grevlex{}(lm(b),lm(a));});
    out.interpolation=seconds(start);
    return out;
}

struct DualStats {
    uint32_t roots,rows,standard,frontier;
    double evaluation,interpolation;
};
static thread_local std::string dual_error_text;
extern "C" const char* dual_error() { return dual_error_text.c_str(); }
extern "C" void* packed_workspace_create(uint32_t n,uint32_t equations) {
    try {
        if(n<1 || n>20 || equations<1 || equations>4096)
            throw std::invalid_argument("packed dimensions: variables 1..20, equations 1..4096");
        return new PackedWorkspace(n,equations);
    } catch(const std::exception& e) { dual_error_text=e.what();return nullptr; }
}
extern "C" void packed_workspace_destroy(void* handle) { delete static_cast<PackedWorkspace*>(handle); }
extern "C" void* packed_dual_compute(void* handle,const uint32_t* masks,
                                    const uint64_t* coefficients,uint32_t count,DualStats* stats) {
    try {
        if(!handle || !stats || (count && (!masks || !coefficients)))
            throw std::invalid_argument("invalid packed input shape");
        *stats={};
        auto& workspace=*static_cast<PackedWorkspace*>(handle);
        std::lock_guard<std::mutex> lock(workspace.mutex);
        auto result=packed_basis(workspace,masks,coefficients,count);
        *stats={uint32_t(result.roots.size()),uint32_t(result.basis.size()),
                uint32_t(result.standard_monomials),uint32_t(result.frontier_visits),
                result.evaluation,result.interpolation};
        return new DualResult(std::move(result));
    } catch(const std::exception& e) { dual_error_text=e.what();return nullptr; }
}
extern "C" uint32_t dual_row_size(const void* handle,uint32_t row) {
    const auto* r=static_cast<const DualResult*>(handle);
    return r && row<r->basis.size() ? uint32_t(r->basis[row].size()) : 0;
}
extern "C" const uint32_t* dual_row_data(const void* handle,uint32_t row) {
    const auto* r=static_cast<const DualResult*>(handle);
    return r && row<r->basis.size() ? r->basis[row].data() : nullptr;
}
extern "C" void dual_destroy(void* handle) { delete static_cast<DualResult*>(handle); }
