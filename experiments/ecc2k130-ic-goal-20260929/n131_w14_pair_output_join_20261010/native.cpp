// Exact four-atom algebraic inverse via reusable pair-output lookup.
// Reuse the frozen field arithmetic source; only this query algorithm changes.
#define main archived_resultant_main
#include "../n131_w14_coupled_fouratom_inverse_20261010/native.cpp"
#undef main

#include <map>
#include <utility>

struct FeLess {
    bool operator()(Fe a, Fe b) const {
        if (a.hi != b.hi) return a.hi < b.hi;
        if (a.mid != b.mid) return a.mid < b.mid;
        return a.lo < b.lo;
    }
};

static std::vector<Fe> quadratic_roots(const Field& f, Fe a, Fe b, Fe c) {
    if (zero(a)) {
        if (zero(b)) {
            if (zero(c)) throw std::runtime_error("identically zero quadratic");
            return {};
        }
        return {f.mul(c,f.inverse(b))};
    }
    if (zero(b)) {
        Fe root=f.mul(c,f.inverse(a));
        for (int i=1;i<f.n;++i) root=f.sq(root);
        return {root};
    }
    Fe inva=f.inverse(a),invb=f.inverse(b);
    Fe alpha=f.mul(f.mul(a,c),f.sq(invb));
    Fe h=alpha,power=alpha;
    for (int i=1;i<=(f.n-1)/2;++i) {
        power=f.sq(f.sq(power));
        h=xo(h,power);
    }
    if (!eq(xo(f.sq(h),h),alpha)) return {};
    Fe scale=f.mul(b,inva),root=f.mul(scale,h);
    Fe other=xo(root,scale);
    if (!eq(xo(xo(f.mul(a,f.sq(root)),f.mul(b,root)),c),Fe{}))
        throw std::runtime_error("quadratic root replay failed");
    return {root,other};
}

int main(int argc,char**argv) {
try {
    if (argc!=5) throw std::runtime_error("usage: native input.txt result.json cap_seconds rss_cap_bytes");
    std::ifstream in(argv[1]);
    int n,d;std::string source_s,output_z;
    in>>n>>d>>source_s>>output_z;
    if (!in||!((n==41&&d==6)||(n==131&&d==14)))
        throw std::runtime_error("wrong exact field or source dimension");
    std::string trailing;
    if (in>>trailing) throw std::runtime_error("trailing frozen input");
    const uint64_t cap_ns=std::stoull(argv[3])*1000000000ULL;
    const uint64_t rss_cap=std::stoull(argv[4]);
    uint64_t start=ticks();
    Field f(n);Fe s=decimal(source_s);
    if (!eq(s,Fe{2,0,0})) throw std::runtime_error("unsupported frozen seed");
    auto basis=product_basis(f,d,s);
    std::vector<Fe> values{{0,0,0}};
    for (Fe v:basis) {
        size_t old=values.size();
        for (size_t i=0;i<old;++i) values.push_back(xo(values[i],v));
    }
    std::map<Fe,std::vector<Fe>,FeLess> outputs;
    Fe ss=f.sq(s),one{1,0,0};
    size_t root_count=0;
    for (size_t i=0;i<values.size();++i) {
        if ((i&255)==0 && (ticks()-start>=cap_ns || rss()>rss_cap))
            throw std::runtime_error("setup resource cap reached");
        Fe p=values[i];
        for (Fe c:quadratic_roots(f,xo(one,f.sq(p)),p,ss)) {
            outputs[c].push_back(p);
            ++root_count;
        }
    }
    uint64_t setup_ns=ticks()-start;
    uint64_t query_start=ticks();
    Fe z=decimal(output_z);
    if (highbit(z)>=n) throw std::runtime_error("output exceeds field");
    Fe zz=f.sq(z);
    struct Hit{Fe p,q;};
    std::vector<Hit> hits;
    size_t output_states=0;
    bool censored=false,oom=false;
    for (const auto& [c,ps]:outputs) {
        if ((output_states&31)==0) {
            if (ticks()-query_start>=cap_ns) {censored=true;break;}
            if (rss()>rss_cap) {oom=true;break;}
        }
        Fe zc=f.mul(z,c);
        Fe a=xo(one,f.sq(zc)),b=zc,constant=xo(zz,f.sq(c));
        for (Fe droot:quadratic_roots(f,a,b,constant)) {
            auto match=outputs.find(droot);
            if (match==outputs.end()) continue;
            for (Fe p:ps) for (Fe q:match->second) hits.push_back({p,q});
        }
        ++output_states;
    }
    FeLess less;
    std::sort(hits.begin(),hits.end(),[&](Hit a,Hit b){
        if (less(a.p,b.p)) return true;
        if (less(b.p,a.p)) return false;
        return less(a.q,b.q);
    });
    hits.erase(std::unique(hits.begin(),hits.end(),[](Hit a,Hit b){
        return eq(a.p,b.p)&&eq(a.q,b.q);
    }),hits.end());
    uint64_t query_ns=ticks()-query_start;
    std::ofstream out(argv[2]);
    if (!out) throw std::runtime_error("cannot save result");
    out<<"{\"status\":\""<<(oom?"OOM":censored?"CENSORED_TIME":"COMPLETE_ALGEBRAIC_SCAN")
       <<"\",\"field_degree\":"<<n<<",\"source_dimension\":"<<d
       <<",\"pair_products\":"<<values.size()
       <<",\"pair_output_entries\":"<<root_count
       <<",\"distinct_pair_outputs\":"<<outputs.size()
       <<",\"output_states_checked\":"<<output_states
       <<",\"setup_ns\":"<<setup_ns<<",\"query_ns\":"<<query_ns
       <<",\"peak_rss_bytes\":"<<rss()<<",\"hits\":[";
    for (size_t i=0;i<hits.size();++i) {
        if (i) out<<",";
        out<<"{\"p\":";write_fe(out,hits[i].p);
        out<<",\"q\":";write_fe(out,hits[i].q);out<<"}";
    }
    out<<"]}\n";
    std::cout<<(oom?"OOM":censored?"CENSORED_TIME":"COMPLETE_ALGEBRAIC_SCAN")
             <<" pair_outputs="<<outputs.size()<<" hits="<<hits.size()
             <<" setup_s="<<double(setup_ns)/1e9
             <<" query_s="<<double(query_ns)/1e9<<" rss="<<rss()<<"\n";
} catch (const std::exception& e) {
    std::cerr<<e.what()<<"\n";
    return 1;
}
}
