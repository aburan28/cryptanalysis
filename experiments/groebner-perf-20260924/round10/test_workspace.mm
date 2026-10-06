#include "gpu_workspace.hpp"
#include <m4ri/m4ri.h>
#include <iostream>
#include <map>
#include <memory>
#include <random>
#include <thread>

struct Case {uint32_t rows,cols;std::vector<uint64_t> data;};
static uint32_t cpu(Case& c) {
    if(!c.rows)return 0;
    auto* a=mzd_init(c.rows,c.cols);size_t words=(c.cols+63)/64;
    for(uint32_t r=0;r<c.rows;++r)memcpy(mzd_row(a,r),c.data.data()+r*words,words*8);
    uint32_t rank=mzd_echelonize_m4ri(a,1,5);
    for(uint32_t r=0;r<c.rows;++r)memcpy(c.data.data()+r*words,mzd_row(a,r),words*8);
    mzd_free(a);return rank;
}
int main(int argc,char**argv) {
 @autoreleasepool {try {
    if(argc!=2)throw std::runtime_error("usage: test-workspace shader.metal");
    std::mt19937_64 rng(2026092501);size_t checked=0;
    for(uint32_t cols:{1u,7u,8u,9u,31u,32u,33u,63u,64u,65u,127u,128u,129u,257u,4096u}) {
        reusable_rref::Workspace workspace(cols==33?8192:4096,cols,argv[1]);
        auto check=[&](Case c) {
            Case expected=c;uint32_t rank=cpu(expected);
            for(bool indirect:{false,true}) {
                std::vector<uint64_t> out(c.data.size());
                auto stats=workspace.run(c.rows,[&](uint64_t* p){memcpy(p,c.data.data(),c.data.size()*8);},
                    [&](const uint64_t* p){memcpy(out.data(),p,out.size()*8);},indirect);
                if(stats.rank!=rank || out!=expected.data)
                    throw std::runtime_error("rank/RREF mismatch cols="+std::to_string(c.cols)+" rows="+std::to_string(c.rows)+" indirect="+std::to_string(indirect));
                ++checked;
            }
        };
        for(uint32_t rows:{0u,1u,7u,15u,16u,17u,31u,32u,33u,65u}) {
            Case c={rows,cols,std::vector<uint64_t>(size_t(rows)*((cols+63)/64))};
            for(auto& w:c.data)w=rng();
            if(cols%64)for(uint32_t r=0;r<rows;++r)c.data[size_t(r)*((cols+63)/64)+(cols+63)/64-1]&=(UINT64_C(1)<<(cols%64))-1;
            check(c);
            // Reuse after unrelated values/ranks must not retain stale pivots.
            std::fill(c.data.begin(),c.data.end(),0);check(c);
            for(uint32_t r=0;r<rows;++r)c.data[size_t(r)*((cols+63)/64)+(cols-1)/64]=UINT64_C(1)<<((cols-1)%64);
            check(c);
        }
        if(cols==33) {
            for(uint32_t rows:{4097u,8192u}) {
                Case c={rows,cols,std::vector<uint64_t>(rows)};
                for(auto& w:c.data)w=rng()&((UINT64_C(1)<<33)-1);
                check(c);
            }
        }
        if(cols==4096) {
            for(uint32_t rows:{2915u,3100u,4096u}) {
                Case c={rows,cols,std::vector<uint64_t>(size_t(rows)*64)};
                for(auto& w:c.data)w=rng();check(c);
            }
        }
    }
    // Shared workspace calls serialize numeric ownership; independent inputs
    // and their expected outputs are held by each calling thread.
    reusable_rref::Workspace shared(64,65,argv[1]);
    std::vector<std::thread> workers;std::vector<std::string> errors(4);
    std::vector<Case> inputs,expected;
    std::vector<uint32_t> ranks;
    // M4RI's allocator is not the subject of the concurrency test. Prepare
    // its independent references serially before starting Metal callers.
    for(unsigned t=0;t<4;++t) {
        std::mt19937_64 random(901+t);
        for(unsigned rep=0;rep<8;++rep) {
            Case c={17,65,std::vector<uint64_t>(34)};
            for(unsigned r=0;r<17;++r){c.data[2*r]=random();c.data[2*r+1]=random()&1;}
            inputs.push_back(c);expected.push_back(c);ranks.push_back(cpu(expected.back()));
        }
    }
    for(unsigned t=0;t<4;++t)workers.emplace_back([&,t]{try {
        for(unsigned rep=0;rep<8;++rep) {
            size_t i=t*8+rep;const Case& c=inputs[i];std::vector<uint64_t> out(34);
            auto stats=shared.run(17,[&](uint64_t*p){memcpy(p,c.data.data(),272);},[&](const uint64_t*p){memcpy(out.data(),p,272);});
            if(stats.rank!=ranks[i] || out!=expected[i].data)throw std::runtime_error("concurrent RREF mismatch");
        }
    } catch(const std::exception& e){errors[t]=e.what();}});
    for(auto& worker:workers)worker.join();
    for(const auto& error:errors)if(!error.empty())throw std::runtime_error(error);
    checked+=32;
    bool rejected=false;
    try {shared.run(65,[](uint64_t*){},[](const uint64_t*){});}catch(const std::invalid_argument&){rejected=true;}
    if(!rejected)throw std::runtime_error("capacity overflow accepted");
    std::cout<<"{\"status\":\"PASS\",\"exact_rank_rref_checks\":"<<checked<<",\"concurrent_calls\":32,\"capacity_rejected\":true}\n";
    return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
}
