// Exact degree-eight resultant / linearized-product-space four-atom oracle.
#include "resultant_terms.hpp"

#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <sys/resource.h>
#include <vector>

struct Fe {uint64_t lo=0,mid=0,hi=0;};
static Fe xo(Fe a,Fe b){return {a.lo^b.lo,a.mid^b.mid,a.hi^b.hi};}
static bool zero(Fe a){return !(a.lo|a.mid|a.hi);}
static bool eq(Fe a,Fe b){return a.lo==b.lo&&a.mid==b.mid&&a.hi==b.hi;}
static bool bit(Fe a,int i){return i<64?(a.lo>>i)&1:i<128?(a.mid>>(i-64))&1:(a.hi>>(i-128))&1;}
static int highbit(Fe a){
    if(a.hi)return 128+63-__builtin_clzll(a.hi);
    if(a.mid)return 64+63-__builtin_clzll(a.mid);
    if(a.lo)return 63-__builtin_clzll(a.lo);
    return -1;
}
static uint64_t ticks(){return uint64_t(std::chrono::duration_cast<std::chrono::nanoseconds>(
    std::chrono::steady_clock::now().time_since_epoch()).count());}
static uint64_t rss(){rusage u{};getrusage(RUSAGE_SELF,&u);
#ifdef __APPLE__
    return uint64_t(u.ru_maxrss);
#else
    return uint64_t(u.ru_maxrss)*1024;
#endif
}

struct Field {
    int n;
    uint64_t low;
    std::array<Fe,131> square_basis{};
    explicit Field(int degree):n(degree),low(degree==41?0x9:0x2007){
        if(n!=41&&n!=131)throw std::runtime_error("unsupported exact field");
        square_basis[0]={1,0,0};
        for(int i=1;i<n;++i)square_basis[i]=xmul(xmul(square_basis[i-1]));
    }
    Fe xmul(Fe a)const{
        if(n==41){
            bool carry=(a.lo>>40)&1;
            return {((a.lo<<1)&((1ULL<<41)-1))^(carry?low:0),0,0};
        }
        bool carry=(a.hi&4)!=0;
        return {(a.lo<<1)^(carry?low:0),(a.mid<<1)|(a.lo>>63),
                ((a.hi<<1)|(a.mid>>63))&7};
    }
    Fe mul(Fe a,Fe b)const{
        Fe result{};
        for(int i=0;i<n;++i){
            if(bit(a,i))result=xo(result,b);
            b=xmul(b);
        }
        return result;
    }
    Fe sq(Fe a)const{
        Fe result{};
        for(int limb=0;limb<3;++limb){
            uint64_t word=limb==0?a.lo:limb==1?a.mid:a.hi;
            while(word){
                int offset=__builtin_ctzll(word),index=limb*64+offset;
                if(index<n)result=xo(result,square_basis[index]);
                word&=word-1;
            }
        }
        return result;
    }
    Fe inverse(Fe a)const{
        if(zero(a))throw std::runtime_error("inverse of zero");
        std::array<Fe,8> table{};table[0]=a;
        int length=1,level=0;
        while(length*2<=n-1){
            Fe raised=table[level];
            for(int i=0;i<length;++i)raised=sq(raised);
            table[level+1]=mul(raised,table[level]);
            ++level;
            length*=2;
        }
        Fe result=table[level];
        for(int j=level-1;j>=0;--j)if((n-1)&(1<<j)){
            for(int i=0;i<(1<<j);++i)result=sq(result);
            result=mul(result,table[j]);
        }
        result=sq(result);
        if(!eq(mul(a,result),Fe{1,0,0}))throw std::runtime_error("inverse replay failed");
        return result;
    }
};

static Fe decimal(const std::string& value){
    Fe result{};
    for(char ch:value){
        if(ch<'0'||ch>'9')throw std::runtime_error("bad decimal field element");
        unsigned digit=unsigned(ch-'0');
        unsigned __int128 lo=static_cast<unsigned __int128>(result.lo)*10+digit;
        unsigned __int128 mid=static_cast<unsigned __int128>(result.mid)*10+(lo>>64);
        unsigned __int128 hi=static_cast<unsigned __int128>(result.hi)*10+(mid>>64);
        result={uint64_t(lo),uint64_t(mid),uint64_t(hi)};
    }
    return result;
}
static void write_fe(std::ostream&out,Fe value){
    out<<"["<<value.lo<<","<<value.mid<<","<<value.hi<<"]";
}

struct Poly {
    std::array<Fe,17> c{};
    int degree=-1;
};
static void trim(Poly& a){
    for(int i=16;i>=0;--i)if(!zero(a.c[i])){a.degree=i;return;}
    a.degree=-1;
}
static Poly remainder(Poly a,const Poly& b,const Field& f){
    if(b.degree<0)throw std::runtime_error("division by zero polynomial");
    if(b.degree==0)return {};
    while(a.degree>=b.degree){
        Fe leading=a.c[a.degree];
        Fe multiplier=f.inverse(b.c[b.degree]);
        Fe quotient=f.mul(leading,multiplier);
        int shift=a.degree-b.degree;
        for(int j=0;j<=b.degree;++j)
            a.c[shift+j]=xo(a.c[shift+j],f.mul(quotient,b.c[j]));
        trim(a);
    }
    return a;
}
static Poly pseudo_remainder(Poly a,const Poly& b,const Field& f){
    if(b.degree<0)throw std::runtime_error("pseudo divide by zero");
    if(b.degree==0)return {};
    while(a.degree>=b.degree){
        Fe la=a.c[a.degree],lb=b.c[b.degree];
        int shift=a.degree-b.degree;
        for(int j=0;j<=a.degree;++j)a.c[j]=f.mul(a.c[j],lb);
        for(int j=0;j<=b.degree;++j)
            a.c[shift+j]=xo(a.c[shift+j],f.mul(b.c[j],la));
        trim(a);
    }
    return a;
}
static Poly gcd(Poly a,Poly b,const Field&f){
    while(b.degree>=0){
        if(b.degree==0){Poly one;one.c[0]={1,0,0};one.degree=0;return one;}
        Poly next=pseudo_remainder(a,b,f);
        a=b;b=next;
    }
    return a;
}
static Poly square_mod(const Poly& a,const Poly& monic,const Field& f){
    Poly result;
    for(int i=0;i<=a.degree;++i)result.c[2*i]=f.sq(a.c[i]);
    result.degree=2*a.degree;
    for(int k=result.degree;k>=monic.degree;--k){
        Fe factor=result.c[k];
        if(zero(factor))continue;
        for(int j=0;j<monic.degree;++j)
            result.c[k-monic.degree+j]=xo(result.c[k-monic.degree+j],
                                           f.mul(factor,monic.c[j]));
        result.c[k]={};
    }
    trim(result);
    return result;
}

static std::vector<Fe> product_basis(const Field&f,int dimension,Fe s){
    std::array<Fe,131> pivots{};
    std::vector<Fe> basis;
    Fe w{1,0,0};
    for(int i=1;i<=dimension;++i){
        w=f.xmul(w);
        Fe candidate=xo(f.sq(w),f.mul(s,w));
        Fe reduced=candidate;
        while(!zero(reduced)){
            int pivot=highbit(reduced);
            if(zero(pivots[pivot])){pivots[pivot]=reduced;basis.push_back(candidate);break;}
            reduced=xo(reduced,pivots[pivot]);
        }
    }
    if(int(basis.size())!=dimension-1)throw std::runtime_error("product-space rank drift");
    return basis;
}
static std::vector<Fe> subspace_coeffs(const Field&f,const std::vector<Fe>&basis){
    std::vector<Fe> coefficients{{1,0,0}};
    for(Fe v:basis){
        Fe current=v,value{};
        for(Fe c:coefficients){value=xo(value,f.mul(c,current));current=f.sq(current);}
        if(zero(value))throw std::runtime_error("dependent product basis");
        std::vector<Fe> next(coefficients.size()+1);
        for(size_t i=0;i<coefficients.size();++i){
            next[i]=xo(next[i],f.mul(value,coefficients[i]));
            next[i+1]=xo(next[i+1],f.sq(coefficients[i]));
        }
        coefficients=std::move(next);
    }
    return coefficients;
}
static std::array<std::array<Fe,9>,9> resultant_rows(const Field&f,Fe s,Fe z){
    std::array<Fe,17> sp{};std::array<Fe,9> zp{};
    sp[0]=zp[0]={1,0,0};
    for(int i=1;i<17;++i)sp[i]=f.mul(sp[i-1],s);
    for(int i=1;i<9;++i)zp[i]=f.mul(zp[i-1],z);
    std::array<std::array<Fe,9>,9> rows{};
    for(const auto& term:TERMS){
        rows[term.q][term.p]=xo(rows[term.q][term.p],
                                  f.mul(sp[term.s],zp[term.z]));
    }
    return rows;
}
static Poly evaluate_h(const Field&f,const std::array<std::array<Fe,9>,9>&rows,Fe p){
    Poly result;
    for(int q=0;q<9;++q){
        Fe value{};
        for(int j=8;j>=0;--j)value=xo(f.mul(value,p),rows[q][j]);
        result.c[q]=value;
    }
    trim(result);
    return result;
}
static Poly subspace_gcd(const Field&f,Poly h,const std::vector<Fe>&coefficients,
                         Fe inverse_leading){
    if(h.degree<0)return h;
    if(h.degree==0){Poly one;one.c[0]={1,0,0};one.degree=0;return one;}
    for(int j=0;j<=h.degree;++j)h.c[j]=f.mul(h.c[j],inverse_leading);
    Poly power;power.c[1]={1,0,0};power.degree=1;
    if(h.degree==1)power=remainder(power,h,f);
    Poly accumulated;
    for(Fe coefficient:coefficients){
        for(int j=0;j<=power.degree;++j)
            accumulated.c[j]=xo(accumulated.c[j],f.mul(coefficient,power.c[j]));
        trim(accumulated);
        power=square_mod(power,h,f);
    }
    return gcd(h,accumulated,f);
}

int main(int argc,char**argv){
try{
    if(argc!=5)throw std::runtime_error("usage: native input.txt result.json cap_seconds rss_cap_bytes");
    std::ifstream in(argv[1]);if(!in)throw std::runtime_error("missing frozen input");
    int n,dimension;std::string source_s,output_z;in>>n>>dimension>>source_s>>output_z;
    if(!in||!((n==41&&dimension==6)||(n==131&&dimension==14)))
        throw std::runtime_error("wrong exact field or source dimension");
    std::string trailing;if(in>>trailing)throw std::runtime_error("trailing frozen input");
    const uint64_t cap_ns=std::stoull(argv[3])*1000000000ULL;
    const uint64_t rss_cap=std::stoull(argv[4]);
    uint64_t started=ticks();
    Field f(n);Fe s=decimal(source_s),z=decimal(output_z);
    if(!eq(s,Fe{2,0,0})||highbit(z)>=n)throw std::runtime_error("unsupported frozen seed or output");
    auto basis=product_basis(f,dimension,s);
    auto coefficients=subspace_coeffs(f,basis);
    std::vector<Fe> values{{0,0,0}};
    for(Fe vector:basis){size_t old=values.size();
        for(size_t i=0;i<old;++i)values.push_back(xo(values[i],vector));
    }
    auto rows=resultant_rows(f,s,z);
    uint64_t setup_ns=ticks()-started,query_start=ticks();
    struct Hit{Fe p;Poly g;};std::vector<Hit> hits;
    size_t processed=0;bool censored=false,oom=false;
    std::vector<Poly> polynomials;
    std::vector<size_t> inverse_indices;
    polynomials.reserve(values.size());
    inverse_indices.reserve(values.size());
    uint64_t phase_start=ticks();
    for(size_t index=0;index<values.size();++index){
        if((index&31)==0){
            if(ticks()-query_start>=cap_ns){censored=true;break;}
            if(rss()>rss_cap){oom=true;break;}
        }
        Poly h=evaluate_h(f,rows,values[index]);
        if(h.degree>0)inverse_indices.push_back(index);
        polynomials.push_back(h);
    }
    uint64_t phase_evaluate_ns=ticks()-phase_start;
    std::vector<Fe> inverse_leading(values.size());
    uint64_t field_inverse_calls=0;
    phase_start=ticks();
    if(!censored&&!oom&&!inverse_indices.empty()){
        std::vector<Fe> prefixes(inverse_indices.size());
        Fe accumulator{1,0,0};
        for(size_t i=0;i<inverse_indices.size();++i){
            prefixes[i]=accumulator;
            Fe leading=polynomials[inverse_indices[i]].c[
                polynomials[inverse_indices[i]].degree];
            accumulator=f.mul(accumulator,leading);
        }
        Fe inverse_accumulator=f.inverse(accumulator);
        ++field_inverse_calls;
        for(size_t i=inverse_indices.size();i-->0;){
            Fe leading=polynomials[inverse_indices[i]].c[
                polynomials[inverse_indices[i]].degree];
            inverse_leading[inverse_indices[i]]=f.mul(inverse_accumulator,prefixes[i]);
            inverse_accumulator=f.mul(inverse_accumulator,leading);
        }
    }
    uint64_t phase_batch_inverse_ns=ticks()-phase_start;
    phase_start=ticks();
    for(size_t index=0;index<polynomials.size()&&!censored&&!oom;++index){
        if((index&31)==0){
            if(ticks()-query_start>=cap_ns){censored=true;break;}
            if(rss()>rss_cap){oom=true;break;}
        }
        Poly common=subspace_gcd(f,polynomials[index],coefficients,
                                 inverse_leading[index]);
        if(common.degree!=0)hits.push_back({values[index],common});
        ++processed;
    }
    uint64_t phase_gcd_ns=ticks()-phase_start;
    uint64_t query_ns=ticks()-query_start;
    const char* status=oom?"OOM":censored?"CENSORED_TIME":"COMPLETE_ALGEBRAIC_SCAN";
    std::ofstream out(argv[2]);if(!out)throw std::runtime_error("cannot save result");
    out<<"{\"status\":\""<<status<<"\",\"field_degree\":"<<n
       <<",\"source_dimension\":"<<dimension<<",\"seed_sum\":";
    write_fe(out,s);out<<",\"output_z\":";write_fe(out,z);
    out<<",\"total_product_states\":"<<values.size()
       <<",\"evaluated_product_states\":"<<polynomials.size()
       <<",\"processed_product_states\":"<<processed
       <<",\"nonconstant_resultants\":"<<inverse_indices.size()
       <<",\"field_inverse_calls\":"<<field_inverse_calls
       <<",\"setup_ns\":"<<setup_ns<<",\"query_ns\":"<<query_ns
       <<",\"phase_evaluate_ns\":"<<phase_evaluate_ns
       <<",\"phase_batch_inverse_ns\":"<<phase_batch_inverse_ns
       <<",\"phase_gcd_ns\":"<<phase_gcd_ns
       <<",\"peak_rss_bytes\":"<<rss()<<",\"hits\":[";
    for(size_t i=0;i<hits.size();++i){
        if(i)out<<",";
        out<<"{\"p\":";write_fe(out,hits[i].p);
        out<<",\"gcd_degree\":"<<hits[i].g.degree<<",\"gcd_coefficients\":[";
        for(int j=0;j<=hits[i].g.degree;++j){if(j)out<<",";write_fe(out,hits[i].g.c[j]);}
        out<<"]}";
    }
    out<<"]}\n";
    std::cout<<status<<" processed="<<processed<<" hits="<<hits.size()
             <<" query_s="<<double(query_ns)/1e9<<" rss="<<rss()<<"\n";
}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}
}
