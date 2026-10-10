// Rotate source points once, then batch all pair additions in each window.
#define main archived_resultant_main
#include "../n131_w14_coupled_fouratom_inverse_20261010/native.cpp"
#undef main

struct FeLess {
    bool operator()(Fe a,Fe b)const{
        if(a.hi!=b.hi)return a.hi<b.hi;
        if(a.mid!=b.mid)return a.mid<b.mid;
        return a.lo<b.lo;
    }
};
static Fe frob(const Field&f,Fe a,int k){for(int i=0;i<k;++i)a=f.sq(a);return a;}
static Fe halftrace(const Field&f,Fe a){
    Fe h=a,power=a;
    for(int i=1;i<=(f.n-1)/2;++i){power=f.sq(f.sq(power));h=xo(h,power);}
    return h;
}
static void put16(std::ostream&o,uint16_t x){o.put(char(x));o.put(char(x>>8));}
static void put32(std::ostream&o,uint32_t x){for(int i=0;i<4;++i)o.put(char(x>>(8*i)));}
static void putfe(std::ostream&o,Fe x,unsigned char flag=0){
    if(x.hi>7||flag>1)throw std::runtime_error("field packing overflow");
    for(int j=0;j<8;++j)o.put(char(x.lo>>(8*j)));
    for(int j=0;j<8;++j)o.put(char(x.mid>>(8*j)));
    o.put(char(x.hi|(uint64_t(flag)<<3)));
}
struct Left {Fe c,h;uint32_t pair;unsigned char trace;};
struct Right {Fe c;uint32_t pair;};
static uint32_t packpair(unsigned a,unsigned b){
    if(a>=b||b>=16384)throw std::runtime_error("invalid source pair");
    return uint32_t(a)|(uint32_t(b)<<14);
}
static unsigned first(uint32_t x){return x&16383;}
static unsigned second(uint32_t x){return x>>14;}
static std::array<int,16384> support(const std::string&path){
    std::ifstream in(path);if(!in)throw std::runtime_error("missing W14 support");
    std::array<int,16384> columns{};columns.fill(-1);
    int mask,column,count=0;
    while(in>>mask>>column){
        if(mask<=0||mask>=16384||column<0||columns[mask]>=0)
            throw std::runtime_error("invalid W14 support row");
        columns[mask]=column;++count;
    }
    if(!in.eof()||count!=8220)throw std::runtime_error("W14 support count drift");
    return columns;
}
static void write_left(std::ostream&o,const Left&r){
    putfe(o,r.c);putfe(o,r.h,r.trace);put32(o,r.pair);
}
static void write_right(std::ostream&o,const Right&r){putfe(o,r.c);put32(o,r.pair);}

struct CurvePoint {Fe x,y;};

static std::vector<Fe> batch_invert(const Field&f,const std::vector<Fe>&values){
    if(values.empty())return {};
    const Fe one{1,0,0};
    std::vector<Fe> prefix(values.size()+1,one),inverse(values.size());
    for(size_t i=0;i<values.size();++i){
        if(zero(values[i]))throw std::runtime_error("batch inverse zero input");
        prefix[i+1]=f.mul(prefix[i],values[i]);
    }
    Fe tail=f.inverse(prefix.back());
    for(size_t i=values.size();i-->0;){
        inverse[i]=f.mul(tail,prefix[i]);
        tail=f.mul(tail,values[i]);
    }
    if(!eq(tail,one))throw std::runtime_error("batch inversion failed");
    return inverse;
}

static std::array<CurvePoint,16384> source_points(const Field&f,
                                                   const std::array<int,16384>&columns){
    std::vector<Fe> masks;
    std::vector<unsigned> indices;
    for(unsigned a=1;a<16384;++a)if(columns[a]>=0){
        masks.push_back(Fe{uint64_t(a)<<1,0,0});indices.push_back(a);
    }
    if(indices.size()!=8220)throw std::runtime_error("source support drift");
    std::vector<Fe> inverses=batch_invert(f,masks);
    std::array<CurvePoint,16384> points{};
    for(size_t i=0;i<indices.size();++i){
        Fe w=masks[i],x=inverses[i];
        Fe rhs=xo(x,f.sq(w));
        Fe lambda=halftrace(f,rhs);
        if(!eq(xo(f.sq(lambda),lambda),rhs))
            throw std::runtime_error("source x is not rational");
        Fe y=f.mul(lambda,x);
        Fe curve_lhs=xo(f.sq(y),f.mul(x,y));
        Fe curve_rhs=xo(f.mul(f.sq(x),x),Fe{1,0,0});
        if(!eq(curve_lhs,curve_rhs))throw std::runtime_error("source curve replay failed");
        points[indices[i]]={x,y};
    }
    return points;
}

struct PairOutputs {std::vector<CurvePoint> sums;std::vector<Fe> reciprocal;};

static PairOutputs pair_outputs(const Field&f,
                                const std::array<CurvePoint,16384>&points,
                                const std::vector<uint32_t>&pairs){
    const unsigned count=unsigned(pairs.size());
    std::vector<Fe> denominators(count);
    for(unsigned i=0;i<count;++i){
        unsigned a=first(pairs[i]),b=second(pairs[i]);
        denominators[i]=xo(points[a].x,points[b].x);
        if(zero(denominators[i]))throw std::runtime_error("equal source x");
    }
    std::vector<Fe> inv_den=batch_invert(f,denominators);
    PairOutputs output;
    output.sums.resize(2*count);
    std::vector<Fe> sum_x(2*count);
    for(unsigned i=0;i<count;++i){
        unsigned a=first(pairs[i]),b=second(pairs[i]);
        Fe numerator=xo(points[a].y,points[b].y);
        for(unsigned sign=0;sign<2;++sign){
            Fe lambda=f.mul(xo(numerator,sign?points[b].x:Fe{}),inv_den[i]);
            Fe x=xo(xo(f.sq(lambda),lambda),denominators[i]);
            if(zero(x))throw std::runtime_error("zero pair-output x");
            Fe y=xo(xo(f.mul(lambda,xo(points[a].x,x)),x),points[a].y);
            output.sums[2*i+sign]={x,y};sum_x[2*i+sign]=x;
        }
    }
    output.reciprocal=batch_invert(f,sum_x);
    return output;
}

int main(int argc,char**argv){
try{
    if(argc!=8)throw std::runtime_error(
        "usage: prepare support index receipt first last cap_seconds rss_bytes");
    auto columns=support(argv[1]);
    unsigned lo=std::stoul(argv[4]),hi=std::stoul(argv[5]);
    if(lo<1||hi>16383||lo>hi)throw std::runtime_error("bad seed range");
    uint64_t cap_ns=std::stoull(argv[6])*1000000000ULL;
    uint64_t rss_cap=std::stoull(argv[7]);
    uint64_t started=ticks();
    Field f(131);Fe one{1,0,0};
    auto points=source_points(f,columns);
    std::array<CurvePoint,16384> rotated_a{},rotated_b{};
    for(unsigned a=1;a<16384;++a)if(columns[a]>=0){
        rotated_a[a]={frob(f,points[a].x,26),frob(f,points[a].y,26)};
        rotated_b[a]={frob(f,rotated_a[a].x,13),frob(f,rotated_a[a].y,13)};
    }
    uint64_t source_ns=ticks()-started;
    if(source_ns>=cap_ns||rss()>rss_cap)throw std::runtime_error("source resource cap");
    std::ofstream out(argv[2],std::ios::binary);
    if(!out)throw std::runtime_error("cannot open packed index");
    out.write("S3STRM1",8);put16(out,uint16_t(lo));put16(out,uint16_t(hi));
    uint64_t total_pairs=0,total_entries=0,total_denominator_terms=0;
    unsigned min_pairs=65535,max_pairs=0;
    for(unsigned seed=lo;seed<=hi;++seed){
        if(ticks()-started>=cap_ns||rss()>rss_cap)
            throw std::runtime_error("prepare resource cap");
        std::vector<uint32_t> pairs;
        for(unsigned a=1;a<16384;++a){
            unsigned b=a^seed;
            if(a>=b||columns[a]<0||columns[b]<0||columns[a]==columns[b])continue;
            pairs.push_back(packpair(a,b));
        }
        unsigned count=unsigned(pairs.size());
        if(count<1974||count>2147)throw std::runtime_error("seed pair count drift");
        PairOutputs output_a=pair_outputs(f,rotated_a,pairs);
        PairOutputs output_b=pair_outputs(f,rotated_b,pairs);
        std::vector<Left> left;std::vector<Right> right;
        left.reserve(2*count);right.reserve(2*count);
        for(unsigned i=0;i<count;++i)for(unsigned sign=0;sign<2;++sign){
            unsigned j=2*i+sign;
            Fe c=output_a.reciprocal[j];
            Fe x=output_a.sums[j].x;
            Fe y=output_a.sums[j].y;
            Fe h=xo(f.mul(y,c),x);
            Fe argument=f.sq(xo(c,x));
            if(!eq(xo(f.sq(h),h),argument))
                throw std::runtime_error("group half-trace lift failed");
            left.push_back({c,h,pairs[i],0});
            right.push_back({output_b.reciprocal[j],pairs[i]});
        }
        auto left_less=[](const Left&a,const Left&b){
            FeLess less;
            if(less(a.c,b.c))return true;
            if(less(b.c,a.c))return false;
            return a.pair<b.pair;
        };
        auto right_less=[](const Right&a,const Right&b){
            FeLess less;
            if(less(a.c,b.c))return true;
            if(less(b.c,a.c))return false;
            return a.pair<b.pair;
        };
        std::sort(left.begin(),left.end(),left_less);
        std::sort(right.begin(),right.end(),right_less);
        put16(out,uint16_t(seed));put16(out,uint16_t(left.size()));
        put16(out,uint16_t(right.size()));
        for(const auto&r:left)write_left(out,r);
        for(const auto&r:right)write_right(out,r);
        if(!out)throw std::runtime_error("packed index write failed");
        total_pairs+=count;total_entries+=left.size();
        total_denominator_terms+=2*count;
        min_pairs=std::min(min_pairs,count);max_pairs=std::max(max_pairs,count);
    }
    out.close();if(!out)throw std::runtime_error("packed index close failed");
    std::ifstream check(argv[2],std::ios::binary|std::ios::ate);
    uint64_t bytes=uint64_t(check.tellg());
    if(bytes!=12+uint64_t(hi-lo+1)*6+59*total_entries)
        throw std::runtime_error("packed index length mismatch");
    uint64_t elapsed=ticks()-started;
    std::ofstream receipt(argv[3]);
    if(!receipt)throw std::runtime_error("cannot write receipt");
    receipt<<"{\"status\":\"COMPLETE_ROTATED_GROUP_BATCH_PREPARE\",\"seed_first\":"<<lo
           <<",\"seed_last\":"<<hi<<",\"seed_count\":"<<(hi-lo+1)
           <<",\"usable_mask_pairs\":"<<total_pairs
           <<",\"entries_per_rotation\":"<<total_entries
           <<",\"denominator_batch_terms\":"<<total_denominator_terms
           <<",\"field_inversions\":"<<(1+4*(hi-lo+1))
           <<",\"min_pairs_per_seed\":"<<min_pairs
           <<",\"max_pairs_per_seed\":"<<max_pairs
           <<",\"packed_bytes\":"<<bytes
           <<",\"source_ns\":"<<source_ns
           <<",\"setup_ns\":"<<elapsed
           <<",\"peak_rss_bytes\":"<<rss()<<"}\n";
    std::cout<<"COMPLETE_ROTATED_GROUP_BATCH_PREPARE pairs="<<total_pairs
             <<" entries="<<total_entries<<" seconds="<<double(elapsed)/1e9
             <<" rss="<<rss()<<"\n";
}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}
}
