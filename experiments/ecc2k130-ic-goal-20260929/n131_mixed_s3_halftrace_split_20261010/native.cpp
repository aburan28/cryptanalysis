// Shared source seed, different Frobenius rotations for the two pair outputs.
#define main archived_resultant_main
#include "../n131_w14_coupled_fouratom_inverse_20261010/native.cpp"
#undef main

#include <map>
#include <set>

struct FeLess {
    bool operator()(Fe a,Fe b)const{
        if(a.hi!=b.hi)return a.hi<b.hi;
        if(a.mid!=b.mid)return a.mid<b.mid;
        return a.lo<b.lo;
    }
};

static Fe frob(const Field&f,Fe a,int k){
    for(int i=0;i<k;++i)a=f.sq(a);
    return a;
}

static uint64_t carryless(uint64_t a,uint64_t b){
    uint64_t product=0;
    for(int i=0;i<14;++i)if((a>>i)&1)product^=b<<i;
    return product;
}

static std::vector<Fe> quadratic_roots(const Field&f,Fe a,Fe b,Fe c){
    if(zero(a)){
        if(zero(b)){
            if(zero(c))throw std::runtime_error("identically zero quadratic");
            return {};
        }
        return {f.mul(c,f.inverse(b))};
    }
    if(zero(b)){
        Fe root=f.mul(c,f.inverse(a));
        for(int i=1;i<f.n;++i)root=f.sq(root);
        return {root};
    }
    Fe inva=f.inverse(a),invb=f.inverse(b);
    Fe alpha=f.mul(f.mul(a,c),f.sq(invb));
    Fe h=alpha,power=alpha;
    for(int i=1;i<=(f.n-1)/2;++i){
        power=f.sq(f.sq(power));
        h=xo(h,power);
    }
    if(!eq(xo(f.sq(h),h),alpha))return {};
    Fe scale=f.mul(b,inva),root=f.mul(scale,h);
    if(!eq(xo(xo(f.mul(a,f.sq(root)),f.mul(b,root)),c),Fe{}))
        throw std::runtime_error("quadratic root replay failed");
    return {root,xo(root,scale)};
}

static Fe halftrace(const Field&f,Fe a){
    Fe h=a,power=a;
    for(int i=1;i<=(f.n-1)/2;++i){
        power=f.sq(f.sq(power));
        h=xo(h,power);
    }
    return h;
}

struct SplitEntry { Fe c,h; unsigned char trace; };

// For odd n, H(a)^2+H(a)+a is the absolute trace, embedded as 0 or 1.
static unsigned char halftrace_trace(const Field&f,Fe a,Fe h){
    Fe tr=xo(xo(f.sq(h),h),a);
    if(eq(tr,Fe{}))return 0;
    if(eq(tr,Fe{1,0,0}))return 1;
    throw std::runtime_error("half-trace identity failed");
}

int main(int argc,char**argv){
try{
    if(argc!=6)throw std::runtime_error("usage: native input result support_or_dash cap_seconds rss_cap_bytes");
    std::ifstream in(argv[1]);
    int n,d,r1,r2;std::string source_s,output_z;
    in>>n>>d>>source_s>>r1>>r2>>output_z;
    if(!in||!((n==41&&d==6&&r1==10&&r2==15)||
              (n==131&&d==14&&r1==26&&r2==39)))
        throw std::runtime_error("wrong frozen mixed-rotation panel");
    std::string trailing;
    if(in>>trailing)throw std::runtime_error("trailing input");
    const uint64_t cap_ns=std::stoull(argv[4])*1000000000ULL;
    const uint64_t rss_cap=std::stoull(argv[5]);
    uint64_t start=ticks();
    Field f(n);Fe s=decimal(source_s),one{1,0,0};
    if(!eq(s,Fe{2,0,0}))throw std::runtime_error("requires s=t");
    auto basis=product_basis(f,d,s);
    std::vector<Fe> values{{0,0,0}};
    for(Fe v:basis){
        size_t old=values.size();
        for(size_t i=0;i<old;++i)values.push_back(xo(values[i],v));
    }
    std::vector<Fe> products;
    size_t rational_masks=0;
    if(n==41){
        if(std::string(argv[3])!="-")throw std::runtime_error("N41 support must be dash");
        products=values;
    }else{
        std::set<Fe,FeLess> value_set(values.begin(),values.end());
        std::ifstream support(argv[3]);
        if(!support)throw std::runtime_error("missing frozen W14 support");
        std::array<int,16384> columns{};columns.fill(-1);
        int mask,column;
        while(support>>mask>>column){
            if(mask<=0||mask>=16384||column<0||columns[mask]>=0)
                throw std::runtime_error("invalid support row");
            columns[mask]=column;++rational_masks;
        }
        if(rational_masks!=8220||!support.eof())
            throw std::runtime_error("support row count drift");
        for(uint64_t a=1;a<16384;++a){
            uint64_t b=a^1;
            if(a>=b||columns[a]<0||columns[b]<0||columns[a]==columns[b])continue;
            Fe p{carryless(a,b)<<2,0,0};
            if(!value_set.count(p))throw std::runtime_error("supported product outside V_s");
            products.push_back(p);
        }
        if(products.size()!=2062)throw std::runtime_error("supported pair count drift");
    }
    std::map<Fe,std::vector<Fe>,FeLess> left,right;
    Fe seeds[]={frob(f,s,r1),frob(f,s,r2)};
    size_t entries[2]={0,0};
    for(size_t i=0;i<products.size();++i){
        if((i&255)==0&&(ticks()-start>=cap_ns||rss()>rss_cap))
            throw std::runtime_error("setup resource cap reached");
        Fe p=products[i];
        std::map<Fe,std::vector<Fe>,FeLess>* tables[]={&left,&right};
        int rotations[]={r1,r2};
        for(int j=0;j<2;++j){
            Fe rotated=frob(f,p,rotations[j]);
            for(Fe c:quadratic_roots(f,xo(one,f.sq(rotated)),rotated,f.sq(seeds[j]))){
                (*tables[j])[c].push_back(p);
                ++entries[j];
            }
        }
    }
    uint64_t precompute_start=ticks();
    std::vector<SplitEntry> split;
    split.reserve(left.size());
    for(const auto& [c,ps]:left){
        if(zero(c))throw std::runtime_error("zero reciprocal pair output");
        Fe a=xo(c,f.inverse(c));
        a=f.sq(a);
        Fe h=halftrace(f,a);
        split.push_back({c,h,halftrace_trace(f,a,h)});
    }
    uint64_t precompute_ns=ticks()-precompute_start;
    uint64_t setup_ns=ticks()-start,query_start=ticks();
    Fe z=decimal(output_z);
    if(highbit(z)>=n||zero(z))throw std::runtime_error("invalid output coordinate");
    Fe zz=f.sq(z);
    Fe az=f.sq(xo(z,f.inverse(z)));
    Fe hz=halftrace(f,az);
    unsigned char trace_z=halftrace_trace(f,az,hz);
    std::vector<Fe> scales(split.size(),Fe{}),prefix;
    std::vector<size_t> invert_indices;
    std::vector<Fe> invert_terms;
    prefix.reserve(split.size()+1);
    prefix.push_back(one);
    for(size_t i=0;i<split.size();++i){
        if(split[i].trace!=trace_z)continue;
        Fe u=f.mul(z,split[i].c),k=xo(one,u);
        if(zero(k))continue;
        invert_indices.push_back(i);
        invert_terms.push_back(k);
        prefix.push_back(f.mul(prefix.back(),k));
    }
    if(!invert_indices.empty()){
        Fe tail=f.inverse(prefix.back());
        for(size_t j=invert_indices.size();j-->0;){
            Fe invk=f.mul(tail,prefix[j]);
            tail=f.mul(tail,invert_terms[j]);
            Fe u=xo(one,invert_terms[j]);
            scales[invert_indices[j]]=f.mul(u,f.sq(invk));
        }
        if(!eq(tail,one))throw std::runtime_error("batch inverse replay failed");
    }
    struct Hit{Fe p,q;};std::vector<Hit> hits;
    size_t checked=0;bool censored=false,oom=false;
    for(const auto&[c,ps]:left){
        if((checked&31)==0){
            if(ticks()-query_start>=cap_ns){censored=true;break;}
            if(rss()>rss_cap){oom=true;break;}
        }
        const SplitEntry &entry=split[checked];
        if(!eq(entry.c,c))throw std::runtime_error("split table order drift");
        if(entry.trace!=trace_z){++checked;continue;}
        Fe u=f.mul(z,c),k=xo(one,u);
        std::vector<Fe> roots;
        if(zero(k)){
            roots=quadratic_roots(f,Fe{},u,xo(zz,f.sq(c)));
        }else{
            Fe scale=scales[checked],v=xo(entry.h,hz);
            Fe droot=f.mul(scale,v);
            roots={droot,xo(droot,scale)};
        }
        for(Fe droot:roots){
            auto found=right.find(droot);
            if(found==right.end())continue;
            Fe residual=xo(xo(f.mul(f.sq(k),f.sq(droot)),f.mul(u,droot)),
                           xo(zz,f.sq(c)));
            if(!zero(residual))throw std::runtime_error("split root replay failed");
            for(Fe p:ps)for(Fe q:found->second)hits.push_back({p,q});
        }
        ++checked;
    }
    FeLess less;
    std::sort(hits.begin(),hits.end(),[&](Hit a,Hit b){
        if(less(a.p,b.p))return true;
        if(less(b.p,a.p))return false;
        return less(a.q,b.q);
    });
    hits.erase(std::unique(hits.begin(),hits.end(),[](Hit a,Hit b){
        return eq(a.p,b.p)&&eq(a.q,b.q);
    }),hits.end());
    uint64_t query_ns=ticks()-query_start;
    std::ofstream out(argv[2]);
    if(!out)throw std::runtime_error("cannot write result");
    out<<"{\"status\":\""<<(oom?"OOM":censored?"CENSORED_TIME":"COMPLETE_ALGEBRAIC_SCAN")
       <<"\",\"field_degree\":"<<n<<",\"source_dimension\":"<<d
       <<",\"rotations\":["<<r1<<","<<r2<<"]"
       <<",\"source_product_count\":"<<products.size()
       <<",\"rational_masks\":"<<rational_masks
       <<",\"pair_output_entries\":["<<entries[0]<<","<<entries[1]<<"]"
       <<",\"distinct_pair_outputs\":["<<left.size()<<","<<right.size()<<"]"
       <<",\"left_outputs_checked\":"<<checked
       <<",\"setup_ns\":"<<setup_ns
       <<",\"split_precompute_ns\":"<<precompute_ns
       <<",\"batch_inverse_terms\":"<<invert_indices.size()
       <<",\"query_ns\":"<<query_ns
       <<",\"peak_rss_bytes\":"<<rss()<<",\"hits\":[";
    for(size_t i=0;i<hits.size();++i){
        if(i)out<<",";
        out<<"{\"p\":";write_fe(out,hits[i].p);
        out<<",\"q\":";write_fe(out,hits[i].q);out<<"}";
    }
    out<<"]}\n";
    std::cout<<(oom?"OOM":censored?"CENSORED_TIME":"COMPLETE_ALGEBRAIC_SCAN")
             <<" products="<<products.size()<<" left="<<left.size()
             <<" right="<<right.size()<<" hits="<<hits.size()
             <<" setup_s="<<double(setup_ns)/1e9
             <<" query_s="<<double(query_ns)/1e9<<" rss="<<rss()<<"\n";
}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}
}
