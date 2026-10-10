// The N131 pair-output join with exact rational-mask and column screening.
#define main archived_resultant_main
#include "../n131_w14_coupled_fouratom_inverse_20261010/native.cpp"
#undef main

#include <map>
#include <set>

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

static uint64_t carryless(uint64_t a,uint64_t b) {
    uint64_t product=0;
    for (int i=0;i<14;++i) if ((a>>i)&1) product^=b<<i;
    return product;
}

int main(int argc,char**argv) {
try {
    if (argc!=6) throw std::runtime_error("usage: native_filtered input result support cap_seconds rss_cap_bytes");
    std::ifstream in(argv[1]);
    int n,d;std::string source_s,output_z;
    in>>n>>d>>source_s>>output_z;
    if (!in||n!=131||d!=14) throw std::runtime_error("requires frozen N131 W14 input");
    std::string trailing;
    if (in>>trailing) throw std::runtime_error("trailing frozen input");
    const uint64_t cap_ns=std::stoull(argv[4])*1000000000ULL;
    const uint64_t rss_cap=std::stoull(argv[5]);
    uint64_t started=ticks();
    Field f(n);Fe s=decimal(source_s),one{1,0,0};
    if (!eq(s,Fe{2,0,0})) throw std::runtime_error("requires s=t");
    auto basis=product_basis(f,d,s);
    std::vector<Fe> values{{0,0,0}};
    for (Fe v:basis) {
        size_t old=values.size();
        for (size_t i=0;i<old;++i) values.push_back(xo(values[i],v));
    }
    std::set<Fe,FeLess> value_set(values.begin(),values.end());
    std::ifstream support(argv[3]);
    if (!support) throw std::runtime_error("missing frozen W14 support");
    std::array<int,16384> columns{};columns.fill(-1);
    int mask,column,count=0;
    while (support>>mask>>column) {
        if (mask<=0||mask>=16384||column<0||columns[mask]>=0)
            throw std::runtime_error("bad support row");
        columns[mask]=column;
        ++count;
    }
    if (count!=8220||!support.eof()) throw std::runtime_error("support row count drift");
    std::map<Fe,std::vector<Fe>,FeLess> outputs;
    size_t allowed_pairs=0,root_count=0;
    Fe ss=f.sq(s);
    for (uint64_t a=1;a<16384;++a) {
        uint64_t b=a^1;
        if (a>=b||columns[a]<0||columns[b]<0||columns[a]==columns[b]) continue;
        Fe p{carryless(a,b)<<2,0,0};
        if (!value_set.count(p)) throw std::runtime_error("supported product not in V_s");
        for (Fe c:quadratic_roots(f,xo(one,f.sq(p)),p,ss)) {
            outputs[c].push_back(p);
            ++root_count;
        }
        ++allowed_pairs;
        if ((allowed_pairs&255)==0 && (ticks()-started>=cap_ns||rss()>rss_cap))
            throw std::runtime_error("setup resource cap reached");
    }
    if (allowed_pairs!=2062) throw std::runtime_error("supported pair count drift");
    uint64_t setup_ns=ticks()-started;
    uint64_t query_start=ticks();
    Fe z=decimal(output_z),zz=f.sq(z);
    if (highbit(z)>=n) throw std::runtime_error("output exceeds field");
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
        Fe aa=xo(one,f.sq(zc)),bb=zc,constant=xo(zz,f.sq(c));
        for (Fe droot:quadratic_roots(f,aa,bb,constant)) {
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
       <<",\"rational_masks\":"<<count<<",\"allowed_source_pairs\":"<<allowed_pairs
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
             <<" allowed_pairs="<<allowed_pairs<<" pair_outputs="<<outputs.size()
             <<" hits="<<hits.size()<<" setup_s="<<double(setup_ns)/1e9
             <<" query_s="<<double(query_ns)/1e9<<" rss="<<rss()<<"\n";
} catch (const std::exception& e) {
    std::cerr<<e.what()<<"\n";
    return 1;
}
}
