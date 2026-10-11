// W18 four-atom join with an on-demand exact seed-pair table.
#include "../n131_w18_seedwise_hashjoin_20261011/base.hpp"

#include <unordered_map>

struct FeHash {
    size_t operator()(const Fe& x) const noexcept {
        uint64_t h=x.lo*0x9e3779b97f4a7c15ULL;
        h^=x.mid+0x9e3779b97f4a7c15ULL+(h<<6)+(h>>2);
        h^=x.hi+0x9e3779b97f4a7c15ULL+(h<<6)+(h>>2);
        return size_t(h);
    }
};
struct FeEqual {bool operator()(const Fe& x,const Fe& y) const noexcept{return eq(x,y);}};
struct Pair {uint32_t a,b;};

struct LinearHalftrace {
    std::array<Fe,131> image{};
    explicit LinearHalftrace(const Field& f){
        for(int i=0;i<131;++i){
            Fe basis{};
            if(i<64)basis.lo=uint64_t(1)<<i;
            else if(i<128)basis.mid=uint64_t(1)<<(i-64);
            else basis.hi=uint64_t(1)<<(i-128);
            image[size_t(i)]=halftrace(f,basis);
        }
    }
    Fe eval(Fe input) const {
        Fe result{};
        const uint64_t words[3]={input.lo,input.mid,input.hi};
        for(int k=0;k<3;++k){
            uint64_t remaining=words[k];
            while(remaining){
                int bitpos=__builtin_ctzll(remaining);
                int index=64*k+bitpos;
                if(index>=131)throw std::runtime_error("field element outside degree 131");
                result=xo(result,image[size_t(index)]);
                remaining&=remaining-1;
            }
        }
        return result;
    }
};

int main(int argc,char**argv){
try {
    if(argc!=7)throw std::runtime_error("usage: native support.tsv seed z result.json cap_seconds table.tsv");
    Field f(131);Fe one{1,0,0};
    int seedmask=std::stoi(argv[2]);
    if(seedmask<=0||seedmask>=262144)throw std::runtime_error("invalid seed");
    std::array<int,262144> columns;columns.fill(-1);
    std::ifstream support(argv[1]);if(!support)throw std::runtime_error("support missing");
    int mask,col,count=0;
    while(support>>mask>>col){
        if(mask<=0||mask>=262144||col<=0||col>=262144||columns[mask]!=-1)
            throw std::runtime_error("bad support row");
        columns[mask]=col;++count;
    }
    if(!support.eof()||count!=131307)throw std::runtime_error("support drift");
    Fe q=decimal(argv[3]);uint64_t cap_ns=std::stoull(argv[5])*1000000000ULL;
    if(zero(q)||highbit(q)>=131)throw std::runtime_error("invalid output z");
    uint64_t query_start=ticks();
    uint64_t build_start=query_start;
    LinearHalftrace halftrace_map(f);
    std::vector<Row> left;
    std::unordered_map<Fe,std::vector<Pair>,FeHash,FeEqual> right;
    right.reserve(135000);
    struct ProductRow {Fe p;uint32_t a,b;};
    std::vector<ProductRow> pairs;
    for(int a=1;a<262144;++a){
        int b=a^seedmask;
        if(a>=b||columns[a]<0||columns[b]<0||columns[a]==columns[b])continue;
        Fe wa{uint64_t(a)<<1,0,0},wb{uint64_t(b)<<1,0,0};
        Fe p=f.mul(wa,wb);
        if(zero(p)||eq(p,one))throw std::runtime_error("exceptional product");
        pairs.push_back({p,uint32_t(a),uint32_t(b)});
    }
    if(pairs.empty())throw std::runtime_error("empty seed bucket");
    std::vector<Fe> product_terms;product_terms.reserve(pairs.size()*2);
    for(const auto& row:pairs){product_terms.push_back(row.p);product_terms.push_back(xo(one,row.p));}
    auto inverses=batch_inverse(f,product_terms);
    Fe seed{uint64_t(seedmask)<<1,0,0},seed2=f.sq(seed);
    uint64_t right_duplicates=0;
    for(size_t i=0;i<pairs.size();++i){
        const auto& row=pairs[i];Fe p=row.p,onep=xo(one,p);
        Fe rhs=f.sq(f.mul(f.mul(onep,seed),inverses[2*i]));
        Fe h=halftrace_map.eval(rhs);
        if(trace_bit(f,rhs,h)!=0)throw std::runtime_error("pair quadratic is not split");
        Fe scale=f.mul(p,f.sq(inverses[2*i+1]));
        for(Fe root:{f.mul(scale,h),f.mul(scale,xo(h,one))}){
            Fe equation=xo(xo(f.mul(xo(one,f.sq(p)),f.sq(root)),f.mul(p,root)),seed2);
            if(!zero(equation))throw std::runtime_error("pair equation failed");
            Fe c=root;for(int j=0;j<26;++j)c=f.sq(c);
            Fe d=c;for(int j=0;j<13;++j)d=f.sq(d);
            if(zero(c)||zero(d))throw std::runtime_error("zero pair output");
            left.push_back({c,{},row.a,row.b,0});
            auto& bucket=right[d];
            if(!bucket.empty())++right_duplicates;
            bucket.push_back({row.a,row.b});
        }
    }
    if(left.size()!=2*pairs.size()||right.size()!=left.size()||right_duplicates)
        throw std::runtime_error("table count or right-coordinate collision drift");
    std::sort(left.begin(),left.end(),[](const Row& x,const Row& y){
        if(x.c.hi!=y.c.hi)return x.c.hi<y.c.hi;
        if(x.c.mid!=y.c.mid)return x.c.mid<y.c.mid;
        return x.c.lo<y.c.lo;
    });
    std::ofstream table(argv[6]);if(!table)throw std::runtime_error("table output open failed");
    for(const auto& row:left)table<<row.c.lo<<'\t'<<row.c.mid<<'\t'<<row.c.hi
                                  <<'\t'<<row.a<<'\t'<<row.b<<'\n';
    table.close();if(!table)throw std::runtime_error("table output write failed");
    std::vector<Fe> cvalues;for(const Row& row:left)cvalues.push_back(row.c);
    auto invc=batch_inverse(f,cvalues);
    for(size_t i=0;i<left.size();++i){
        Fe x=f.sq(xo(left[i].c,invc[i]));
        left[i].h=halftrace_map.eval(x);left[i].trace=trace_bit(f,x,left[i].h);
        if(left[i].trace!=0)throw std::runtime_error("left output trace drift");
    }
    uint64_t build_ns=ticks()-build_start;
    if(build_ns>=cap_ns)throw std::runtime_error("table build exceeded cap");
    uint64_t lookup_start=ticks();
    std::vector<Fe> products(left.size()),denoms(left.size());
    std::vector<Fe> terms{q};std::vector<size_t> indices;
    for(size_t i=0;i<left.size();++i){
        products[i]=f.mul(left[i].c,q);denoms[i]=xo(one,products[i]);
        if(!zero(denoms[i])){terms.push_back(denoms[i]);indices.push_back(i);}
    }
    auto invterms=batch_inverse(f,terms);
    Fe hqarg=f.sq(xo(q,invterms[0]));Fe hq=halftrace_map.eval(hqarg);
    uint8_t tq=trace_bit(f,hqarg,hq);
    std::vector<Candidate> candidates;
    uint64_t compatible=0,exceptional=0;
    for(size_t i=0;i<left.size();++i)if(zero(denoms[i])){
        ++exceptional;Fe d=f.sq(xo(left[i].c,q));check_s3(f,left[i].c,d,q);
        if(!zero(d))candidates.push_back({uint32_t(i),d});
    }
    for(size_t j=0;j<indices.size();++j){
        size_t i=indices[j];if(left[i].trace!=tq)continue;
        ++compatible;
        Fe scale=f.mul(products[i],f.sq(invterms[j+1]));
        Fe first=f.mul(scale,xo(left[i].h,hq));
        Fe second=xo(first,scale);
        for(Fe d:{first,second}){
            check_s3(f,left[i].c,d,q);
            if(!zero(d))candidates.push_back({uint32_t(i),d});
        }
    }
    uint64_t checked=0,source_hits=0,column_rejects=0;
    bool censored=false,oom=false;
    std::vector<Hit> hits;
    for(size_t i=0;i<candidates.size();++i){
        if((i&127)==0){
            if(ticks()-query_start>=cap_ns){censored=true;break;}
            if(rss()>4ULL*1024*1024*1024){oom=true;break;}
        }
        ++checked;
        auto it=right.find(candidates[i].d);
        if(it==right.end())continue;
        for(Pair pair:it->second){
            ++source_hits;
            const Row& row=left[candidates[i].row];
            int ca=columns[pair.a],cb=columns[pair.b];
            if(ca==cb||ca==columns[row.a]||ca==columns[row.b]||
               cb==columns[row.a]||cb==columns[row.b]){
                ++column_rejects;continue;
            }
            hits.push_back({candidates[i].row,candidates[i].d,pair.a,pair.b,{}});
        }
    }
    uint64_t lookup_ns=ticks()-lookup_start;
    uint64_t query_ns=ticks()-query_start;
    std::ofstream out(argv[4]);if(!out)throw std::runtime_error("output open failed");
    out<<"{\"status\":\""<<(oom?"CENSORED_MEMORY":censored?"CENSORED_TIME":"COMPLETE")
       <<"\",\"seed_mask\":"<<seedmask<<",\"output_z\":";write_fe(out,q);
    out<<",\"left_outputs\":"<<left.size()<<",\"right_outputs\":"<<right.size()
       <<",\"right_coordinate_collisions\":"<<right_duplicates
       <<",\"trace_compatible_left\":"<<compatible
       <<",\"exceptional_linear\":"<<exceptional
       <<",\"right_candidates\":"<<candidates.size()<<",\"right_checked\":"<<checked
       <<",\"source_pair_hits\":"<<source_hits<<",\"column_rejects\":"<<column_rejects
       <<",\"field_batch_inversions_query\":1"
       <<",\"source_pairs\":"<<pairs.size()
       <<",\"table_build_ns_exploratory\":"<<build_ns
       <<",\"lookup_ns_exploratory\":"<<lookup_ns
       <<",\"query_ns_exploratory\":"<<query_ns
       <<",\"peak_rss_bytes\":"<<rss()<<",\"hits\":[";
    for(size_t i=0;i<hits.size();++i){
        if(i)out<<",";
        const auto& hit=hits[i];const Row& row=left[hit.row];
        out<<"{\"first_masks\":["<<row.a<<","<<row.b
           <<"],\"second_masks\":["<<hit.a<<","<<hit.b
           <<"],\"first_reciprocal\":";write_fe(out,row.c);
        out<<",\"second_reciprocal\":";write_fe(out,hit.d);out<<"}";
    }
    out<<"]}\n";
    if(!out)throw std::runtime_error("result write failed");
    std::cout<<(oom?"CENSORED_MEMORY":censored?"CENSORED_TIME":"COMPLETE")
             <<" left="<<left.size()<<" right="<<candidates.size()
             <<" accepted="<<hits.size()<<" query_s="<<double(query_ns)/1e9
             <<" build_s="<<double(build_ns)/1e9<<" rss="<<rss()<<"\n";
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}
}
