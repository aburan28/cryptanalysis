// Exact Boolean evaluation + Buchberger-Moller interpolation research control.
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
static DualResult dual_basis(int n,const std::vector<Polynomial>& f,size_t root_cap=256) {
    if(n<1 || n>24) throw std::runtime_error("variable bound 1..24");
    DualResult out;
    auto start=Clock::now();
    const Mask universe=Mask(1)<<n;
    std::vector<uint8_t> alive(universe,1);
    // Pack 64 EQUATIONS per machine word, not 64 assignments. After the
    // subset transform, table[a]'s j-th bit is f_j(a). Duplicate terms cancel.
    std::vector<uint64_t> table(universe);
    for(size_t first=0;first<f.size();first+=64) {
        std::fill(table.begin(),table.end(),0);
        for(size_t j=first;j<std::min(first+64,f.size());++j)
            for(Mask m:f[j]) {
                if(m>=universe) throw std::runtime_error("monomial mask out of range");
                table[m]^=UINT64_C(1)<<(j-first);
            }
        for(Mask step=1;step<universe;step<<=1)
            for(Mask block=0;block<universe;block+=2*step)
                for(Mask offset=0;offset<step;++offset)
                    table[block+step+offset]^=table[block+offset];
        for(Mask a=0;a<universe;++a) alive[a]&=(table[a]==0);
    }
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
            for(int variable=0;variable<n;++variable) {
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
static double median(std::vector<double> x) {
    std::sort(x.begin(),x.end());return x[x.size()/2];
}
#ifdef BOOLEAN_DUAL_LIBRARY
// Owned result handles keep the ABI simple. Every query still allocates fresh
// numerical work; loading the library reuses code, never a previous basis.
struct DualStats {
    uint32_t roots,rows,standard,frontier;
    double evaluation,interpolation;
};
static thread_local std::string dual_error_text;
extern "C" const char* dual_error() { return dual_error_text.c_str(); }
extern "C" void* dual_compute(uint32_t n,const uint32_t* terms,uint32_t term_count,
                              const uint32_t* offsets,uint32_t count,DualStats* stats) {
    try {
        if(n<1 || n>24 || count>4096 || !offsets || !stats || (term_count && !terms)
            || offsets[0]!=0 || offsets[count]!=term_count) throw std::runtime_error("invalid input shape");
        std::vector<Polynomial> input(count);
        for(uint32_t i=0;i<count;++i) {
            if(offsets[i]>offsets[i+1] || offsets[i+1]>term_count) throw std::runtime_error("invalid offsets");
            if(offsets[i]!=offsets[i+1]) input[i].assign(terms+offsets[i],terms+offsets[i+1]);
        }
        auto result=dual_basis(n,input);
        *stats={uint32_t(result.roots.size()),uint32_t(result.basis.size()),
                uint32_t(result.standard_monomials),uint32_t(result.frontier_visits),
                result.evaluation,result.interpolation};
        return new DualResult(std::move(result));
    } catch(const std::exception& e) {dual_error_text=e.what();return nullptr;}
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
#endif
#ifndef BOOLEAN_DUAL_NO_MAIN
int main() {
    try {
        std::ios::sync_with_stdio(false);
        int n,count,ignored_limit,ignored_degree;
        if(!(std::cin>>n>>count>>ignored_limit>>ignored_degree) || n<1 || n>24 || count<0 || count>4096) return 2;
        std::vector<Polynomial> input(count);
        for(auto& p:input) {
            int terms;if(!(std::cin>>terms) || terms<0 || terms>(1<<24)) return 2;
            for(int j=0;j<terms;++j) {
                Mask m;if(!(std::cin>>m) || m>=(Mask(1)<<n)) return 2;
                p.push_back(m);
            }
        }
        int inner=1;
        if(const char* value=std::getenv("GB_BENCH_INNER")) inner=std::max(1,std::min(10000,std::atoi(value)));
        DualResult last;std::vector<double> wall,cpu,eval,bm;
        for(int rep=0;rep<inner;++rep) {
            auto start=Clock::now();auto cpu_start=std::clock();
            auto result=dual_basis(n,input);
            cpu.push_back(double(std::clock()-cpu_start)/CLOCKS_PER_SEC);wall.push_back(seconds(start));
            eval.push_back(result.evaluation);bm.push_back(result.interpolation);
            if(rep && last.basis!=result.basis) throw std::runtime_error("nondeterministic basis");
            last=std::move(result);
        }
        // Same row protocol as the existing runner. The zero matrix metrics
        // are unused compatibility fields; detailed phases are in JSON stderr.
        std::cout<<std::setprecision(10)<<"OK "<<last.basis.size()<<' '<<median(wall)<<" 0 0 0 0 0 0 0 0 0 0 0\n";
        for(const auto& p:last.basis) {std::cout<<p.size();for(Mask m:p)std::cout<<' '<<m;std::cout<<'\n';}
        std::cerr<<std::setprecision(10)<<"{\"inner_repeats\":"<<inner<<",\"basis_cpu_seconds\":"<<median(cpu)
            <<",\"evaluation_seconds\":"<<median(eval)<<",\"interpolation_seconds\":"<<median(bm)
            <<",\"roots\":"<<last.roots.size()<<",\"standard_monomials\":"<<last.standard_monomials
            <<",\"frontier_visits\":"<<last.frontier_visits<<",\"algorithm\":\"exact_evaluation_buchberger_moller\"}\n";
        return 0;
    } catch(const std::exception& e) {
        std::cerr<<"INCONCLUSIVE: "<<e.what()<<'\n';return 3;
    }
}
#endif
