// Invert a W18 pair-output reciprocal against every XOR seed without an output index.
#define main unused_archived_resultant_main
#include "../n131_w14_coupled_fouratom_inverse_20261010/native.cpp"
#undef main

#include <algorithm>
#include <cstring>
#include <sstream>

struct LinearInverse {
    std::array<Fe,18> vectors{};
    std::array<uint32_t,18> masks{};
    std::array<uint8_t,18> pivots{};
    int rank=0;
};

static Fe halftrace(const Field& field, Fe argument) {
    Fe sum=argument,power=argument;
    for(int i=1;i<=65;++i){power=field.sq(field.sq(power));sum=xo(sum,power);}
    return sum;
}

static LinearInverse make_inverse(const Field& field, Fe seed,
                                  const std::array<Fe,18>& basis, uint32_t seed_mask) {
    std::array<Fe,131> pivot{};
    std::array<uint32_t,131> represented_by{};
    uint32_t kernel=0;
    for(int i=0;i<18;++i){
        Fe value=xo(field.sq(basis[i]),field.mul(seed,basis[i]));
        uint32_t mask=uint32_t(1U<<i);
        while(!zero(value)){
            int bit_index=highbit(value);
            if(zero(pivot[bit_index])){
                pivot[bit_index]=value;
                represented_by[bit_index]=mask;
                break;
            }
            value=xo(value,pivot[bit_index]);
            mask^=represented_by[bit_index];
        }
        if(zero(value)){
            if(kernel)throw std::runtime_error("linear kernel dimension drift");
            kernel=mask;
        }
    }
    if(kernel!=seed_mask)throw std::runtime_error("linear kernel is not seed");
    LinearInverse out;
    for(int i=130;i>=0;--i)if(!zero(pivot[i])){
        out.vectors[out.rank]=pivot[i];
        out.masks[out.rank]=represented_by[i];
        out.pivots[out.rank]=uint8_t(i);
        ++out.rank;
    }
    if(out.rank!=17)throw std::runtime_error("linear image rank drift");
    return out;
}

static bool invert_linear(const LinearInverse& map, Fe value, uint32_t& mask) {
    mask=0;
    for(int i=0;i<map.rank;++i){
        if(bit(value,map.pivots[i])){
            value=xo(value,map.vectors[i]);
            mask^=map.masks[i];
        }
    }
    return zero(value);
}

struct Hit {uint32_t seed,a,b;Fe product;};

int main(int argc,char**argv){
try {
    if(argc!=6)throw std::runtime_error("usage: native support.tsv reciprocal rotation result.json cap_seconds");
    const Field field(131);
    std::array<int,262144> columns;columns.fill(-1);
    std::ifstream source(argv[1]);
    if(!source)throw std::runtime_error("missing support");
    int mask,column,loaded=0;
    while(source>>mask>>column){
        if(mask<=0||mask>=262144||column<=0||column>=262144||columns[mask]!=-1)
            throw std::runtime_error("invalid source row");
        columns[mask]=column;++loaded;
    }
    if(!source.eof()||loaded!=131307)throw std::runtime_error("support count drift");
    std::array<Fe,18> basis{},hbasis{};
    Fe element{1,0,0};
    for(int i=0;i<18;++i){
        element=field.xmul(element);
        basis[i]=element;
        hbasis[i]=halftrace(field,field.sq(element));
    }
    const uint64_t setup_start=ticks();
    std::vector<Fe> seeds(262144),hseeds(262144);
    std::vector<LinearInverse> inverses(262144);
    for(int s=1;s<262144;++s){
        int low=s&-s,index=__builtin_ctz(unsigned(low));
        seeds[s]=xo(seeds[s^low],basis[index]);
        hseeds[s]=xo(hseeds[s^low],hbasis[index]);
        inverses[s]=make_inverse(field,seeds[s],basis,uint32_t(s));
    }
    const uint64_t setup_ns=ticks()-setup_start;
    Fe supplied=decimal(argv[2]);
    int rotation=std::stoi(argv[3]);
    uint64_t cap_ns=std::stoull(argv[5])*1000000000ULL;
    if(zero(supplied)||highbit(supplied)>=131||rotation<0||rotation>=131)
        throw std::runtime_error("invalid query coordinate or rotation");
    const uint64_t query_start=ticks();
    Fe c=supplied;
    for(int i=0;i<131-rotation&&rotation;++i)c=field.sq(c);
    Fe check=c;
    for(int i=0;i<rotation;++i)check=field.sq(check);
    if(!eq(check,supplied))throw std::runtime_error("rotation replay failed");
    Fe inverse_c=field.inverse(c);
    Fe c2=field.sq(c),hc=halftrace(field,c2);
    Fe trace=xo(xo(field.sq(hc),hc),c2);
    if(!zero(trace)&&!eq(trace,Fe{1,0,0}))
        throw std::runtime_error("halftrace consistency failure");
    uint64_t seeds_checked=0,image_hits=0,source_hits=0,column_rejects=0;
    std::vector<Hit> hits;
    bool censored=false,oom=false;
    if(zero(trace))for(int s=1;s<262144;++s){
        if((s&127)==1){
            if(ticks()-query_start>=cap_ns){censored=true;break;}
            if(rss()>4ULL*1024*1024*1024){oom=true;break;}
        }
        ++seeds_checked;
        Fe h=xo(hc,hseeds[s]);
        if(!eq(xo(xo(field.sq(h),h),xo(c2,field.sq(seeds[s]))),Fe{}))
            throw std::runtime_error("seed halftrace replay failed");
        for(int root=0;root<2;++root){
            Fe product=field.mul(xo(h,Fe{uint64_t(root),0,0}),inverse_c);
            uint32_t w=0;
            if(!invert_linear(inverses[s],product,w))continue;
            ++image_hits;
            uint32_t a=std::min(w,uint32_t(w^s)),b=std::max(w,uint32_t(w^s));
            if(columns[a]<0||columns[b]<0)continue;
            ++source_hits;
            if(columns[a]==columns[b]){++column_rejects;continue;}
            Fe actual=field.mul(seeds[a],seeds[b]);
            if(!eq(actual,product))throw std::runtime_error("inverse product replay failed");
            Fe equation=xo(xo(field.mul(xo(Fe{1,0,0},field.sq(product)),c2),
                              field.mul(product,c)),field.sq(seeds[s]));
            if(!zero(equation))throw std::runtime_error("pair output equation failed");
            hits.push_back({uint32_t(s),a,b,product});
        }
    }
    const uint64_t query_ns=ticks()-query_start;
    std::ofstream output(argv[4]);if(!output)throw std::runtime_error("result open failed");
    output<<"{\"status\":\""<<(oom?"CENSORED_MEMORY":censored?"CENSORED_TIME":"COMPLETE")
          <<"\",\"supplied_reciprocal\":";write_fe(output,supplied);
    output<<",\"unrotated_reciprocal\":";write_fe(output,c);
    output<<",\"rotation\":"<<rotation
          <<",\"trace_bit\":"<<(zero(trace)?0:1)
          <<",\"seed_count\":262143,\"seeds_checked\":"<<seeds_checked
          <<",\"linear_image_hits\":"<<image_hits
          <<",\"source_pair_hits\":"<<source_hits
          <<",\"column_rejects\":"<<column_rejects
          <<",\"setup_ns_exploratory\":"<<setup_ns
          <<",\"query_ns_exploratory\":"<<query_ns
          <<",\"peak_rss_bytes\":"<<rss()<<",\"hits\":[";
    for(size_t i=0;i<hits.size();++i){
        if(i)output<<",";
        output<<"{\"seed\":"<<hits[i].seed<<",\"masks\":["
              <<hits[i].a<<","<<hits[i].b<<"],\"columns\":["
              <<columns[hits[i].a]<<","<<columns[hits[i].b]<<"],\"product\":";
        write_fe(output,hits[i].product);output<<"}";
    }
    output<<"]}\n";
    if(!output)throw std::runtime_error("result write failed");
    std::cout<<(oom?"CENSORED_MEMORY":censored?"CENSORED_TIME":"COMPLETE")
             <<" seeds="<<seeds_checked<<" image_hits="<<image_hits
             <<" source_hits="<<source_hits<<" accepted="<<hits.size()
             <<" setup_s="<<double(setup_ns)/1e9
             <<" query_s="<<double(query_ns)/1e9<<" rss="<<rss()<<"\n";
}catch(const std::exception& error){std::cerr<<error.what()<<"\n";return 1;}
}
