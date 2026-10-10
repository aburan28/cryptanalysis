// Exact linearized norm for one W15 pair-product bucket over GF(2^131).
#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <unordered_map>
#include <utility>
#include <vector>
#include <sys/resource.h>

struct Fe { uint64_t lo=0, mid=0, hi=0; };
static Fe add(Fe a, Fe b) { return {a.lo^b.lo,a.mid^b.mid,a.hi^b.hi}; }
static bool iszero(Fe a) { return !(a.lo|a.mid|a.hi); }
static bool bit(Fe a,int i) { return i<64?(a.lo>>i)&1:i<128?(a.mid>>(i-64))&1:(a.hi>>(i-128))&1; }
static int highbit(Fe a) {
    if(a.hi)return 128+63-__builtin_clzll(a.hi);
    if(a.mid)return 64+63-__builtin_clzll(a.mid);
    if(a.lo)return 63-__builtin_clzll(a.lo);
    return -1;
}
static uint64_t tick() { return uint64_t(std::chrono::duration_cast<std::chrono::nanoseconds>(
    std::chrono::steady_clock::now().time_since_epoch()).count()); }
static uint64_t rss() { rusage u{};getrusage(RUSAGE_SELF,&u);
#ifdef __APPLE__
    return uint64_t(u.ru_maxrss);
#else
    return uint64_t(u.ru_maxrss)*1024;
#endif
}

struct Field {
    std::array<Fe,131> square_basis{};
    Field() {
        square_basis[0]={1,0,0};
        for(int i=1;i<131;++i)square_basis[i]=xmul(xmul(square_basis[i-1]));
    }
    static Fe xmul(Fe a) {
        bool carry=(a.hi&4)!=0;
        return {(a.lo<<1)^(carry?0x2007:0), (a.mid<<1)|(a.lo>>63),
            ((a.hi<<1)|(a.mid>>63))&7};
    }
    Fe mul(Fe a,Fe b) const {
        Fe result{};
        for(int i=0;i<131;++i) { if(bit(a,i))result=add(result,b);b=xmul(b); }
        return result;
    }
    Fe sq(Fe a) const {
        Fe result{};
        for(int limb=0;limb<3;++limb) {
            uint64_t word=limb==0?a.lo:limb==1?a.mid:a.hi;
            while(word) {
                int i=limb*64+__builtin_ctzll(word);
                if(i<131)result=add(result,square_basis[i]);
                word&=word-1;
            }
        }
        return result;
    }
};

using Poly=std::unordered_map<uint32_t,Fe>;
static void accumulate(Poly& p,uint32_t exponent,Fe value) {
    if(iszero(value))return;
    auto [it,inserted]=p.try_emplace(exponent,value);
    if(!inserted) { it->second=add(it->second,value);if(iszero(it->second))p.erase(it); }
}
static void multiply_add(const Field& f,Poly& dest,const Poly& a,const Poly& b) {
    for(auto [i,x]:a)for(auto [j,y]:b)accumulate(dest,i+j,f.mul(x,y));
}
static std::vector<Fe> product_basis(const Field& f,int seed) {
    Fe s{uint64_t(seed)<<1,0,0},w{1,0,0};
    std::array<Fe,131> pivots{};std::vector<Fe> result;
    for(int i=1;i<=15;++i) {
        w=Field::xmul(w);
        Fe candidate=add(f.sq(w),f.mul(s,w)),reduced=candidate;
        while(!iszero(reduced)) {
            int k=highbit(reduced);
            if(iszero(pivots[k])) { pivots[k]=reduced;result.push_back(candidate);break; }
            reduced=add(reduced,pivots[k]);
        }
    }
    if(result.size()!=14)throw std::runtime_error("product basis rank drift");
    return result;
}

int main(int argc,char**argv) {
    try {
        if(argc!=5)throw std::runtime_error("usage: norm seed output.tsv cap_seconds rss_cap_bytes");
        int seed=std::stoi(argv[1]);
        if(seed<=0||seed>=32768)throw std::runtime_error("seed outside W15");
        const uint64_t cap_ns=uint64_t(std::stoull(argv[3]))*1000000000ULL;
        const uint64_t rss_cap=std::stoull(argv[4]);
        uint64_t start=tick();Field f;Fe s{uint64_t(seed)<<1,0,0};
        auto basis=product_basis(f,seed);
        std::vector<Poly> coefficients(1);coefficients[0].emplace(0,Fe{1,0,0});
        for(size_t round=0;round<basis.size();++round) {
            Fe v=basis[round],vpower=v;
            Poly value;
            for(size_t j=0;j<coefficients.size();++j) {
                Fe vnext=f.sq(vpower);
                for(auto [e,a]:coefficients[j]) {
                    accumulate(value,e+(1u<<j),f.mul(a,vpower));
                    accumulate(value,e+(1u<<(j+1)),f.mul(a,vnext));
                }
                vpower=vnext;
            }
            std::vector<Poly> next(coefficients.size()+1);
            for(size_t j=0;j<coefficients.size();++j) {
                multiply_add(f,next[j],coefficients[j],value);
                for(auto [e,a]:coefficients[j])accumulate(next[j+1],2*e,f.sq(a));
            }
            coefficients=std::move(next);
            size_t terms=0;for(auto& p:coefficients)terms+=p.size();
            std::cout<<"round="<<round+1<<" value_terms="<<value.size()
                <<" coefficient_terms="<<terms<<" elapsed_s="<<double(tick()-start)/1e9
                <<" peak_rss="<<rss()<<std::endl;
            if(tick()-start>=cap_ns||rss()>rss_cap)
                throw std::runtime_error("resource cap reached after round");
        }
        Poly result;
        for(size_t j=0;j<coefficients.size();++j) {
            for(auto [e,a]:coefficients[j]) {
                // (c^2+s^2)^(2^j) has exactly two monomials.
                Fe constant=f.sq(s);
                for(size_t k=0;k<j;++k)constant=f.sq(constant);
                accumulate(result,e,f.mul(a,constant));
                accumulate(result,e+(1u<<(j+1)),a);
            }
        }
        if(result.size()==0)throw std::runtime_error("zero norm polynomial");
        std::vector<std::pair<uint32_t,Fe>> sorted(result.begin(),result.end());
        std::sort(sorted.begin(),sorted.end(),[](auto a,auto b){return a.first<b.first;});
        std::ofstream out(argv[2]);if(!out)throw std::runtime_error("output open failed");
        for(auto [e,a]:sorted)out<<e<<'\t'<<a.lo<<'\t'<<a.mid<<'\t'<<a.hi<<'\n';
        out.close();if(!out)throw std::runtime_error("output write failed");
        std::cout<<"status=COMPLETE degree="<<sorted.back().first
            <<" terms="<<sorted.size()<<" elapsed_s="<<double(tick()-start)/1e9
            <<" peak_rss="<<rss()<<std::endl;
    } catch(const std::exception& e) {std::cerr<<e.what()<<std::endl;return 1;}
}
