// Recover all W18 pair seeds from one proposed reciprocal coordinate by
// solving the seed-linear product-span equations before source membership.
#include "../n131_w18_seedwise_hashjoin_20261011/base.hpp"

struct PairHit {uint32_t seed,a,b;Fe product;};

struct LinearSolutions {
    int rank=0;
    bool consistent=true;
    std::vector<uint32_t> solutions;
};

static LinearSolutions solve_product_span(const Fe& constant,
                                           const std::array<Fe,19>& columns,
                                           uint8_t trace_constant,
                                           const std::array<uint8_t,18>& trace_seed) {
    constexpr uint32_t rhs=1U<<19;
    std::array<uint32_t,131> rows{};
    int count=0;
    for(int coordinate=0;coordinate<131;++coordinate) {
        if(coordinate>=2 && coordinate<=36)continue;
        uint32_t row=bit(constant,coordinate)?rhs:0;
        for(int variable=0;variable<19;++variable)
            if(bit(columns[size_t(variable)],coordinate))row^=1U<<variable;
        rows[size_t(count++)]=row;
    }
    uint32_t trace_row=trace_constant?rhs:0;
    for(int variable=0;variable<18;++variable)
        if(trace_seed[size_t(variable)])trace_row^=1U<<variable;
    rows[size_t(count++)]=trace_row;
    LinearSolutions out;
    std::array<int,19> pivot_row{};pivot_row.fill(-1);
    for(int variable=0;variable<19;++variable) {
        int found=out.rank;
        while(found<count && !(rows[size_t(found)]&(1U<<variable)))++found;
        if(found==count)continue;
        std::swap(rows[size_t(found)],rows[size_t(out.rank)]);
        pivot_row[size_t(variable)]=out.rank;
        for(int i=0;i<count;++i)if(i!=out.rank && (rows[size_t(i)]&(1U<<variable)))
            rows[size_t(i)]^=rows[size_t(out.rank)];
        ++out.rank;
    }
    for(int i=out.rank;i<count;++i)
        if(rows[size_t(i)]==rhs){out.consistent=false;return out;}
    uint32_t particular=0;
    for(int variable=0;variable<19;++variable)
        if(pivot_row[size_t(variable)]>=0 && (rows[size_t(pivot_row[size_t(variable)])]&rhs))
            particular^=1U<<variable;
    std::vector<uint32_t> nullspace;
    for(int free_variable=0;free_variable<19;++free_variable) {
        if(pivot_row[size_t(free_variable)]>=0)continue;
        uint32_t vector=1U<<free_variable;
        for(int variable=0;variable<19;++variable)
            if(pivot_row[size_t(variable)]>=0 &&
               (rows[size_t(pivot_row[size_t(variable)])]&(1U<<free_variable)))
                vector^=1U<<variable;
        nullspace.push_back(vector);
    }
    if(nullspace.size()>19)throw std::runtime_error("nullspace dimension drift");
    out.solutions.reserve(size_t(1)<<nullspace.size());
    for(uint32_t mask=0;mask<(1U<<nullspace.size());++mask) {
        uint32_t solution=particular;
        for(size_t i=0;i<nullspace.size();++i)if(mask&(1U<<i))solution^=nullspace[i];
        out.solutions.push_back(solution);
    }
    return out;
}

int main(int argc,char**argv) {
try {
    if(argc!=6)throw std::runtime_error("usage: native support.tsv reciprocal rotation result.json cap_seconds");
    const Field field(131);
    std::array<int,262144> columns;columns.fill(-1);
    std::ifstream support(argv[1]);if(!support)throw std::runtime_error("support missing");
    int mask,column,loaded=0;
    while(support>>mask>>column) {
        if(mask<=0||mask>=262144||column<=0||column>=262144||columns[mask]!=-1)
            throw std::runtime_error("invalid support row");
        columns[size_t(mask)]=column;++loaded;
    }
    if(!support.eof()||loaded!=131307)throw std::runtime_error("support count drift");
    uint64_t setup_start=ticks();
    std::array<Fe,18> basis{},half_basis{};
    std::array<uint8_t,18> trace_seed{};
    Fe element{1,0,0};
    for(int i=0;i<18;++i) {
        element=field.xmul(element);
        basis[size_t(i)]=element;
        Fe square=field.sq(element);
        half_basis[size_t(i)]=halftrace(field,square);
        trace_seed[size_t(i)]=trace_bit(field,square,half_basis[size_t(i)]);
        if(trace_seed[size_t(i)])throw std::runtime_error("W18 seed trace drift");
    }
    uint64_t setup_ns=ticks()-setup_start;
    Fe supplied=decimal(argv[2]);
    int rotation=std::stoi(argv[3]);
    uint64_t cap_ns=std::stoull(argv[5])*1000000000ULL;
    if(zero(supplied)||highbit(supplied)>=131||rotation<0||rotation>=131)
        throw std::runtime_error("invalid query coordinate or rotation");
    uint64_t query_start=ticks();
    Fe c=supplied;
    for(int i=0;i<131-rotation&&rotation;++i)c=field.sq(c);
    Fe rotated=c;
    for(int i=0;i<rotation;++i)rotated=field.sq(rotated);
    if(!eq(rotated,supplied))throw std::runtime_error("rotation replay failed");
    Fe inverse_c=field.inverse(c);
    Fe c2=field.sq(c),hc=halftrace(field,c2);
    uint8_t trace=trace_bit(field,c2,hc);
    std::array<Fe,19> variable_product{};
    Fe constant_product=field.mul(hc,inverse_c);
    for(int i=0;i<18;++i)
        variable_product[size_t(i)]=field.mul(half_basis[size_t(i)],inverse_c);
    variable_product[18]=inverse_c;
    LinearSolutions span=solve_product_span(constant_product,variable_product,trace,trace_seed);
    uint64_t span_candidates=span.solutions.size(),image_hits=0,source_hits=0,column_rejects=0;
    std::vector<PairHit> hits;
    bool censored=false,oom=false;
    for(uint32_t solution:span.solutions) {
        if(ticks()-query_start>=cap_ns){censored=true;break;}
        if(rss()>4ULL*1024*1024*1024){oom=true;break;}
        uint32_t seedmask=solution&((1U<<18)-1),branch=(solution>>18)&1;
        if(seedmask==0)continue;
        Fe seed{},hseed{},product=constant_product;
        for(int i=0;i<18;++i)if(seedmask&(1U<<i)) {
            seed=xo(seed,basis[size_t(i)]);
            hseed=xo(hseed,half_basis[size_t(i)]);
            product=xo(product,variable_product[size_t(i)]);
        }
        if(branch)product=xo(product,variable_product[18]);
        Fe z=xo(xo(hc,hseed),Fe{branch,0,0});
        if(!eq(field.mul(product,c),z))throw std::runtime_error("linear product replay failed");
        if(trace_bit(field,xo(c2,field.sq(seed)),xo(hc,hseed)))
            throw std::runtime_error("seed trace replay failed");
        Inverse inverse=make_inverse(field,seed,basis,seedmask);
        uint32_t a=0;
        if(!invert(inverse,product,a))continue;
        ++image_hits;
        uint32_t b=a^seedmask;
        if(a>b)std::swap(a,b);
        if(columns[size_t(a)]<0||columns[size_t(b)]<0)continue;
        ++source_hits;
        if(columns[size_t(a)]==columns[size_t(b)]){++column_rejects;continue;}
        Fe actual=field.mul(Fe{uint64_t(a)<<1,0,0},Fe{uint64_t(b)<<1,0,0});
        if(!eq(actual,product))throw std::runtime_error("source product replay failed");
        Fe equation=xo(xo(field.mul(xo(Fe{1,0,0},field.sq(product)),c2),
                          field.mul(product,c)),field.sq(seed));
        if(!zero(equation))throw std::runtime_error("pair equation failed");
        hits.push_back({seedmask,a,b,product});
    }
    uint64_t query_ns=ticks()-query_start;
    std::ofstream output(argv[4]);if(!output)throw std::runtime_error("result open failed");
    output<<"{\"status\":\""<<(oom?"CENSORED_MEMORY":censored?"CENSORED_TIME":"COMPLETE")
          <<"\",\"supplied_reciprocal\":";write_fe(output,supplied);
    output<<",\"unrotated_reciprocal\":";write_fe(output,c);
    output<<",\"rotation\":"<<rotation<<",\"trace_bit\":"<<unsigned(trace)
          <<",\"span_linear_rank\":"<<span.rank
          <<",\"span_consistent\":"<<(span.consistent?"true":"false")
          <<",\"span_candidates\":"<<span_candidates
          <<",\"linear_image_hits\":"<<image_hits
          <<",\"source_pair_hits\":"<<source_hits
          <<",\"column_rejects\":"<<column_rejects
          <<",\"setup_ns_exploratory\":"<<setup_ns
          <<",\"query_ns_exploratory\":"<<query_ns
          <<",\"peak_rss_bytes\":"<<rss()<<",\"hits\":[";
    for(size_t i=0;i<hits.size();++i) {
        if(i)output<<',';
        output<<"{\"seed\":"<<hits[i].seed<<",\"masks\":["<<hits[i].a<<','<<hits[i].b
              <<"],\"columns\":["<<columns[size_t(hits[i].a)]<<','<<columns[size_t(hits[i].b)]
              <<"],\"product\":";write_fe(output,hits[i].product);output<<'}';
    }
    output<<"]}\n";
    if(!output)throw std::runtime_error("result write failed");
    std::cout<<(oom?"CENSORED_MEMORY":censored?"CENSORED_TIME":"COMPLETE")
             <<" rank="<<span.rank<<" candidates="<<span_candidates
             <<" image_hits="<<image_hits<<" accepted="<<hits.size()
             <<" query_s="<<double(query_ns)/1e9<<" rss="<<rss()<<"\n";
} catch(const std::exception& e) {
    std::cerr<<e.what()<<'\n';return 1;
}
}
