// Exact joint seed/product inverse for a supplied W18 raw pair-output coordinate.
#define main unused_archived_resultant_main
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wreturn-type"
#include "../n131_w14_coupled_fouratom_inverse_20261010/native.cpp"
#pragma clang diagnostic pop
#undef main

static Fe halftrace(const Field& field,Fe argument) {
    Fe sum=argument,power=argument;
    for(int i=1;i<=65;++i){power=field.sq(field.sq(power));sum=xo(sum,power);}
    return sum;
}

struct LinearInverse {
    std::array<Fe,18> vectors{};
    std::array<uint32_t,18> masks{};
    std::array<uint8_t,18> pivots{};
    int rank=0;
};

static LinearInverse make_inverse(const Field& field,Fe seed,
                                  const std::array<Fe,18>& basis,uint32_t seed_mask) {
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

static bool invert_linear(const LinearInverse& map,Fe value,uint32_t& mask) {
    mask=0;
    for(int i=0;i<map.rank;++i)if(bit(value,map.pivots[i])){
        value=xo(value,map.vectors[i]);
        mask^=map.masks[i];
    }
    return zero(value);
}

struct Hit {uint32_t seed,a,b;Fe product;};

struct JointSolution {
    int rank=0;
    bool consistent=false;
    uint64_t coefficients=0;
};

static JointSolution solve_joint(const Field& field, Fe c,
                                 const std::array<Fe,18>& seed_basis) {
    const Fe c2=field.sq(c);
    std::array<Fe,131> pivots{};
    std::array<uint64_t,131> representations{};
    int rank=0;
    auto insert=[&](Fe value,uint64_t representation) {
        while(!zero(value)) {
            const int index=highbit(value);
            if(zero(pivots[index])) {
                pivots[index]=value;
                representations[index]=representation;
                ++rank;
                return;
            }
            value=xo(value,pivots[index]);
            representation^=representations[index];
        }
    };
    for(int i=0;i<18;++i)
        insert(field.sq(seed_basis[i]),uint64_t(1)<<i);
    Fe product_basis=field.xmul(seed_basis[0]); // t^2
    for(int i=0;i<35;++i) {
        const Fe column=xo(field.mul(c,product_basis),
                           field.mul(c2,field.sq(product_basis)));
        insert(column,uint64_t(1)<<(18+i));
        product_basis=field.xmul(product_basis);
    }
    Fe rhs=c2;
    uint64_t solution=0;
    while(!zero(rhs)) {
        const int index=highbit(rhs);
        if(zero(pivots[index]))return {rank,false,0};
        rhs=xo(rhs,pivots[index]);
        solution^=representations[index];
    }
    return {rank,true,solution};
}

static Fe product_from_solution(const Field& field,uint64_t coefficients,
                                const std::array<Fe,18>& seed_basis) {
    Fe result{},basis=field.xmul(seed_basis[0]);
    for(int i=0;i<35;++i) {
        if((coefficients>>(18+i))&1)result=xo(result,basis);
        basis=field.xmul(basis);
    }
    return result;
}

int main(int argc,char**argv) {
try {
    if(argc!=6)throw std::runtime_error(
        "usage: native support.tsv reciprocal rotation result.json cap_seconds");
    const Field field(131);
    std::array<int,262144> columns;columns.fill(-1);
    std::ifstream source(argv[1]);
    if(!source)throw std::runtime_error("missing support");
    int mask,column,loaded=0;
    while(source>>mask>>column) {
        if(mask<=0||mask>=262144||column<=0||column>=262144||columns[mask]!=-1)
            throw std::runtime_error("invalid source row");
        columns[mask]=column;++loaded;
    }
    if(!source.eof()||loaded!=131307)throw std::runtime_error("support count drift");
    std::array<Fe,18> basis{},hbasis{};
    Fe element{1,0,0};
    for(int i=0;i<18;++i) {
        element=field.xmul(element);
        basis[i]=element;
        hbasis[i]=halftrace(field,field.sq(element));
    }
    const Fe supplied=decimal(argv[2]);
    const int rotation=std::stoi(argv[3]);
    const uint64_t cap_ns=std::stoull(argv[5])*1000000000ULL;
    if(zero(supplied)||highbit(supplied)>=131||rotation<0||rotation>=131)
        throw std::runtime_error("invalid query coordinate or rotation");
    const uint64_t query_start=ticks();
    Fe c=supplied;
    for(int i=0;i<131-rotation&&rotation;++i)c=field.sq(c);
    Fe rotation_check=c;
    for(int i=0;i<rotation;++i)rotation_check=field.sq(rotation_check);
    if(!eq(rotation_check,supplied))throw std::runtime_error("rotation replay failed");

    const JointSolution joint=solve_joint(field,c,basis);
    std::vector<Hit> hits;
    uint64_t seed_checks=0,image_hits=0,source_hits=0,column_rejects=0;
    bool censored=false,oom=false;
    const bool fallback=joint.consistent&&joint.rank<53;
    auto check_product=[&](uint32_t seed,Fe product) {
        if(seed==0)return;
        const LinearInverse inverse=make_inverse(field,
            [&](){Fe v{};for(int i=0;i<18;++i)if((seed>>i)&1)v=xo(v,basis[i]);return v;}(),
            basis,seed);
        uint32_t w=0;
        if(!invert_linear(inverse,product,w))return;
        ++image_hits;
        const uint32_t a=std::min(w,w^seed),b=std::max(w,w^seed);
        if(columns[a]<0||columns[b]<0)return;
        ++source_hits;
        if(columns[a]==columns[b]){++column_rejects;return;}
        Fe wa{},wb{};
        for(int i=0;i<18;++i){if((a>>i)&1)wa=xo(wa,basis[i]);if((b>>i)&1)wb=xo(wb,basis[i]);}
        if(!eq(field.mul(wa,wb),product))throw std::runtime_error("inverse product replay failed");
        const Fe s=xo(wa,wb),c2=field.sq(c);
        if(!zero(xo(xo(c2,field.mul(c2,field.sq(product))),
                    xo(field.mul(c,product),field.sq(s)))))
            throw std::runtime_error("joint pair equation replay failed");
        hits.push_back({seed,a,b,product});
    };
    if(joint.consistent&&!fallback) {
        const uint32_t seed=uint32_t(joint.coefficients&((uint64_t(1)<<18)-1));
        const Fe product=product_from_solution(field,joint.coefficients,basis);
        seed_checks=seed!=0;
        check_product(seed,product);
    } else if(fallback) {
        // Full exact fallback for a consistent rank-deficient affine system.
        const Fe c2=field.sq(c),hc=halftrace(field,c2);
        const Fe trace=xo(xo(field.sq(hc),hc),c2);
        if(!zero(trace)&&!eq(trace,Fe{1,0,0}))
            throw std::runtime_error("halftrace consistency failure");
        if(zero(trace)) {
            const Fe inverse_c=field.inverse(c);
            std::array<Fe,18> scaled_basis{};
            for(int i=0;i<18;++i)scaled_basis[i]=field.mul(hbasis[i],inverse_c);
            const Fe constant=field.mul(hc,inverse_c);
            std::vector<Fe> scaled(262144);
            for(uint32_t seed=1;seed<262144;++seed) {
                if((seed&127)==1) {
                    if(ticks()-query_start>=cap_ns){censored=true;break;}
                    if(rss()>4ULL*1024*1024*1024){oom=true;break;}
                }
                const uint32_t low=seed&-seed;
                const int index=__builtin_ctz(low);
                scaled[seed]=xo(scaled[seed^low],scaled_basis[index]);
                ++seed_checks;
                const Fe root=xo(constant,scaled[seed]);
                check_product(seed,root);
                check_product(seed,xo(root,inverse_c));
            }
        }
    }
    if(ticks()-query_start>=cap_ns)censored=true;
    if(rss()>4ULL*1024*1024*1024)oom=true;
    const uint64_t query_ns=ticks()-query_start;
    std::ofstream output(argv[4]);
    if(!output)throw std::runtime_error("result open failed");
    output<<"{\"status\":\""<<(oom?"CENSORED_MEMORY":censored?"CENSORED_TIME":"COMPLETE")
          <<"\",\"supplied_reciprocal\":";write_fe(output,supplied);
    output<<",\"unrotated_reciprocal\":";write_fe(output,c);
    output<<",\"rotation\":"<<rotation<<",\"joint_rank\":"<<joint.rank
          <<",\"joint_consistent\":"<<(joint.consistent?"true":"false")
          <<",\"fallback\":"<<(fallback?"true":"false")
          <<",\"seeds_checked\":"<<seed_checks
          <<",\"linear_image_hits\":"<<image_hits
          <<",\"source_pair_hits\":"<<source_hits
          <<",\"column_rejects\":"<<column_rejects
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
             <<" rank="<<joint.rank<<" consistent="<<joint.consistent
             <<" fallback="<<fallback<<" hits="<<hits.size()
             <<" query_s="<<double(query_ns)/1e9<<" rss="<<rss()<<"\n";
}catch(const std::exception& error){std::cerr<<error.what()<<"\n";return 1;}
}
