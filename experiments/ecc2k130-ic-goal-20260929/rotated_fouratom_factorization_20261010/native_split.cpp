// Evaluate two exact quartics and intersect each with the second product space.
#define main archived_native_main
#include "../n131_w15_rotated_fouratom_inverse_20261010/native.cpp"
#undef main
#include "factor_terms.hpp"

static Poly factor_at(const Field& f, const std::array<QuarticTerm,13>& terms, Fe p) {
    std::array<Fe,5> pp{}; pp[0]={1,0,0};
    for(int j=1;j<5;++j)pp[j]=f.mul(pp[j-1],p);
    Poly result;
    for(const auto& term:terms)
        result.c[term.q]=xo(result.c[term.q],f.mul(term.coefficient,pp[term.p]));
    trim(result);
    return result;
}

int main(int argc,char**argv){
try{
    if(argc!=5)throw std::runtime_error("usage: native_split input.txt result.json cap_seconds rss_cap_bytes");
    std::ifstream in(argv[1]);if(!in)throw std::runtime_error("missing frozen input");
    int n,dimension,r0,r1;std::string source_s,output_z;
    in>>n>>dimension>>r0>>r1>>source_s>>output_z;
    if(!in||n!=131||dimension!=15||r0!=26||r1!=39)
        throw std::runtime_error("wrong frozen N131 specialization");
    std::string trailing;if(in>>trailing)throw std::runtime_error("trailing frozen input");
    const uint64_t cap_ns=std::stoull(argv[3])*1000000000ULL;
    const uint64_t rss_cap=std::stoull(argv[4]);
    uint64_t started=ticks();
    Field f(n);Fe s=decimal(source_s),z=decimal(output_z);
    if(!eq(z,FACTOR_OUTPUT_Z)||zero(s)||bit(s,0)||highbit(s)>dimension)
        throw std::runtime_error("factor header does not match frozen seed/output");
    auto basis0=product_basis(f,dimension,s,r0);
    auto basis1=product_basis(f,dimension,s,r1);
    auto coefficients=subspace_coeffs(f,basis1);
    std::vector<Fe> values{{0,0,0}};
    for(Fe vector:basis0){size_t old=values.size();
        for(size_t i=0;i<old;++i)values.push_back(xo(values[i],vector));
    }
    uint64_t setup_ns=ticks()-started,query_start=ticks();
    struct Hit{Fe p;int factor;Poly g;};std::vector<Hit> hits;
    size_t processed=0;bool censored=false,oom=false;
    for(Fe p:values){
        if((processed&31)==0){
            if(ticks()-query_start>=cap_ns){censored=true;break;}
            if(rss()>rss_cap){oom=true;break;}
        }
        for(int branch=0;branch<2;++branch){
            Poly h=factor_at(f,QUARTIC_FACTORS[branch],p);
            Poly common=subspace_gcd(f,h,coefficients);
            if(common.degree!=0)hits.push_back({p,branch,common});
        }
        ++processed;
    }
    uint64_t query_ns=ticks()-query_start;
    const char* status=oom?"OOM":censored?"CENSORED_TIME":"COMPLETE_FACTORED_SCAN";
    std::ofstream out(argv[2]);if(!out)throw std::runtime_error("cannot save result");
    out<<"{\"status\":\""<<status<<"\",\"field_degree\":"<<n
       <<",\"source_dimension\":"<<dimension<<",\"rotations\":["<<r0<<","<<r1<<"]"
       <<",\"seed_sum\":";write_fe(out,s);
    out<<",\"output_z\":";write_fe(out,z);
    out<<",\"total_product_states\":"<<values.size()
       <<",\"processed_product_states\":"<<processed
       <<",\"setup_ns\":"<<setup_ns<<",\"query_ns\":"<<query_ns
       <<",\"peak_rss_bytes\":"<<rss()<<",\"hits\":[";
    for(size_t i=0;i<hits.size();++i){
        if(i)out<<",";
        out<<"{\"p\":";write_fe(out,hits[i].p);
        out<<",\"factor\":"<<hits[i].factor
           <<",\"gcd_degree\":"<<hits[i].g.degree<<",\"gcd_coefficients\":[";
        for(int j=0;j<=hits[i].g.degree;++j){if(j)out<<",";write_fe(out,hits[i].g.c[j]);}
        out<<"]}";
    }
    out<<"]}\n";
    if(!out)throw std::runtime_error("result output write failure");
    std::cout<<status<<" processed="<<processed<<" hits="<<hits.size()
             <<" query_s="<<double(query_ns)/1e9<<" rss="<<rss()<<"\n";
}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}
}
