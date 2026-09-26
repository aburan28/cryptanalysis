// Experiment-only packed library boundary for the existing bounded hybrid.
#ifndef HYBRID_CPU_ONLY
#include "gpu_workspace.hpp"
#endif
#include <mutex>
#include <string>
#define BOOLEAN_F5B_M4RI_NO_MAIN
#include "../../pdp-scaling/boolean_f5b_m4ri.cpp"

namespace {
using QueryClock=std::chrono::steady_clock;
double seconds(QueryClock::time_point t) {
    return std::chrono::duration<double>(QueryClock::now()-t).count();
}
struct QueryStats {
    uint32_t basis_rows=0,matrix_rows=0,rank=0,f5_rows=0;
    double decode=0,signature=0,generation=0,population=0,elimination=0,extraction=0,total=0;
    double gpu_prepare=0,gpu_encode=0,gpu_execute=0,gpu_device=0,gpu_extract=0;
};
struct Context {
    Engine layout;
    uint32_t equations,degree,capacity,backend;
#ifndef HYBRID_CPU_ONLY
    std::unique_ptr<reusable_rref::Workspace> gpu;
#endif
    Context(uint32_t n,uint32_t eq,uint32_t d,uint32_t cap,uint32_t arm,const char* shader)
      :layout(n,8,-1),equations(eq),degree(d),capacity(cap),backend(arm) {
#ifndef HYBRID_CPU_ONLY
        if(backend)gpu=std::make_unique<reusable_rref::Workspace>(cap,1u<<n,shader);
#else
        (void)shader;
        if(backend)throw std::runtime_error("Metal backend unavailable in CPU-only build");
#endif
    }
};
struct Result { std::vector<std::vector<uint32_t>> basis; };
thread_local std::string error;
thread_local Context* active_context=nullptr;
thread_local QueryStats* active_stats=nullptr;
// M4RI has process-global allocation caches. Serialize every hybrid call,
// including calls on distinct Python contexts while ctypes releases the GIL.
std::mutex computation_mutex;
struct Active {
    Active(Context* c,QueryStats* s){active_context=c;active_stats=s;}
    ~Active(){active_context=nullptr;active_stats=nullptr;}
};
rci_t eliminate(mzd_t* a,int full,int k) {
    Context& c=*active_context;
    if(!c.backend)return mzd_echelonize_m4ri(a,full,k);
#ifndef HYBRID_CPU_ONLY
    size_t words=(a->ncols+63)/64;
    auto stats=c.gpu->run(a->nrows,[&](uint64_t* data){
        for(rci_t r=0;r<a->nrows;++r)memcpy(data+size_t(r)*words,mzd_row(a,r),words*8);
    },[&](const uint64_t* data){
        for(rci_t r=0;r<a->nrows;++r)memcpy(mzd_row(a,r),data+size_t(r)*words,words*8);
    },c.backend==2);
    active_stats->gpu_prepare=stats.prepare_ms/1000;
    active_stats->gpu_encode=stats.encode_ms/1000;
    active_stats->gpu_execute=stats.execute_ms/1000;
    active_stats->gpu_device=stats.device_ms/1000;
    active_stats->gpu_extract=stats.extract_ms/1000;
    return stats.rank;
#else
    throw std::runtime_error("Metal backend unavailable");
#endif
}
}

extern "C" {
const char* hybrid_error(){return error.c_str();}
void* hybrid_create(uint32_t n,uint32_t eq,uint32_t degree,uint32_t capacity,
                    uint32_t backend,const char* shader) {
    try {
        error.clear();
        if(n<1||n>12||eq<1||eq>64||degree>n||capacity<1||capacity>8192||backend>2||!shader)
            throw std::invalid_argument("invalid hybrid configuration");
        return new Context(n,eq,degree,capacity,backend,shader);
    }catch(const std::exception& e){error=e.what();return nullptr;}
    catch(...){error="unknown hybrid initialization failure";return nullptr;}
}
void hybrid_close(void* p){delete static_cast<Context*>(p);}
void* hybrid_compute(void* p,const uint32_t* masks,const uint64_t* coeff,uint32_t count,QueryStats* stats) {
    auto start=QueryClock::now();
    std::lock_guard<std::mutex> lock(computation_mutex);
    try {
        error.clear();
        if(!p||!stats||(count&&(!masks||!coeff)))throw std::invalid_argument("invalid packed pointers");
        *stats=QueryStats{};
        Context& c=*static_cast<Context*>(p);
        // Copy only immutable ring order. The template never receives target
        // coefficients, rewrite entries, syzygies, pivots, or basis elements.
        Engine e=c.layout;
        std::vector<Poly> inputs(c.equations);
        for(uint32_t i=0;i<count;++i) {
            if(masks[i]>=uint32_t(e.universe)||(c.equations<64&&coeff[i]>>c.equations))
                throw std::invalid_argument("invalid packed monomial or coefficient");
            uint64_t bits=coeff[i];uint32_t rank=e.rank_by_mask[masks[i]];
            while(bits) {
                unsigned j=__builtin_ctzll(bits);bits&=bits-1;
                inputs[j].w[rank/64]^=UINT64_C(1)<<(rank%64);
            }
        }
        inputs.erase(std::remove_if(inputs.begin(),inputs.end(),[&](const Poly& f){return e.zero(f);}),inputs.end());
        stats->decode=seconds(start);auto phase=QueryClock::now();
        auto consequences=f5_signature_seed(e,inputs);
        stats->signature=seconds(phase);
        MatrixStats matrix;
        Active active(&c,stats);
        auto basis=macaulay_m4ri(e,inputs,consequences,c.degree,matrix,eliminate,c.capacity);
        auto result=std::make_unique<Result>();
        for(const Poly& f:basis) {
            auto terms=e.masks(f);std::sort(terms.begin(),terms.end());
            result->basis.push_back(std::move(terms));
        }
        stats->basis_rows=result->basis.size();stats->matrix_rows=matrix.rows;
        stats->rank=matrix.rank;stats->f5_rows=matrix.f5_rows;
        stats->generation=matrix.generation;stats->population=matrix.population;
        stats->elimination=matrix.elimination;stats->extraction=matrix.extraction;
        stats->total=seconds(start);
        return result.release();
    }catch(const std::exception& e){error=e.what();return nullptr;}
    catch(...){error="unknown hybrid computation failure";return nullptr;}
}
uint32_t hybrid_row_size(void* p,uint32_t i){
    auto* r=static_cast<Result*>(p);return r&&i<r->basis.size()?r->basis[i].size():0;
}
const uint32_t* hybrid_row_data(void* p,uint32_t i){
    auto* r=static_cast<Result*>(p);return r&&i<r->basis.size()?r->basis[i].data():nullptr;
}
void hybrid_destroy(void* p){delete static_cast<Result*>(p);}
}
