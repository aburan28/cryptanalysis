// Packed disk stream for the exact N131 mixed-rotation S3 inverse.
#define main legacy_resultant_main
#include "../n131_w14_coupled_fouratom_inverse_20261010/native.cpp"
#undef main

#include <map>

struct FeLess {
    bool operator()(Fe a,Fe b)const{
        if(a.hi!=b.hi)return a.hi<b.hi;
        if(a.mid!=b.mid)return a.mid<b.mid;
        return a.lo<b.lo;
    }
};
static Fe frob(const Field&f,Fe a,int k){for(int i=0;i<k;++i)a=f.sq(a);return a;}
static uint64_t carryless(uint64_t a,uint64_t b){
    uint64_t p=0;
    for(int i=0;i<14;++i)if((a>>i)&1)p^=b<<i;
    return p;
}
static Fe halftrace(const Field&f,Fe a){
    Fe h=a,power=a;
    for(int i=1;i<=(f.n-1)/2;++i){power=f.sq(f.sq(power));h=xo(h,power);}
    return h;
}
static unsigned char tracebit(const Field&f,Fe a,Fe h){
    Fe tr=xo(xo(f.sq(h),h),a);
    if(eq(tr,Fe{}))return 0;
    if(eq(tr,Fe{1,0,0}))return 1;
    throw std::runtime_error("half-trace trace identity failed");
}
static std::vector<Fe> quadratic_roots(const Field&f,Fe a,Fe b,Fe c){
    if(zero(a)){
        if(zero(b))return {};
        return {f.mul(c,f.inverse(b))};
    }
    if(zero(b)){
        Fe root=f.mul(c,f.inverse(a));
        for(int i=1;i<f.n;++i)root=f.sq(root);
        return {root};
    }
    Fe alpha=f.mul(f.mul(a,c),f.sq(f.inverse(b)));
    Fe h=halftrace(f,alpha);
    if(!eq(xo(f.sq(h),h),alpha))return {};
    Fe scale=f.mul(b,f.inverse(a)),root=f.mul(scale,h);
    return {root,xo(root,scale)};
}

static void put16(std::ostream&o,uint16_t x){o.put(char(x));o.put(char(x>>8));}
static void put32(std::ostream&o,uint32_t x){for(int i=0;i<4;++i)o.put(char(x>>(8*i)));}
static uint16_t get16(std::istream&i){
    unsigned a=unsigned(uint8_t(i.get())),b=unsigned(uint8_t(i.get()));
    if(!i)throw std::runtime_error("short packed seed header");
    return uint16_t(a|(b<<8));
}
static uint32_t get32(std::istream&i){
    uint32_t x=0;for(int j=0;j<4;++j)x|=uint32_t(uint8_t(i.get()))<<(8*j);
    if(!i)throw std::runtime_error("short packed integer");return x;
}
static void putfe(std::ostream&o,Fe x,unsigned char flag=0){
    if(x.hi>7||flag>1)throw std::runtime_error("field packing overflow");
    for(int j=0;j<8;++j)o.put(char(x.lo>>(8*j)));
    for(int j=0;j<8;++j)o.put(char(x.mid>>(8*j)));
    o.put(char(x.hi|(uint64_t(flag)<<3)));
}
static Fe getfe(std::istream&i,unsigned char*flag=nullptr){
    Fe x{};
    for(int j=0;j<8;++j)x.lo|=uint64_t(uint8_t(i.get()))<<(8*j);
    for(int j=0;j<8;++j)x.mid|=uint64_t(uint8_t(i.get()))<<(8*j);
    int top=i.get();if(!i)throw std::runtime_error("short packed field element");
    if(top&~15)throw std::runtime_error("noncanonical packed field element");
    x.hi=unsigned(top)&7;
    if(flag)*flag=static_cast<unsigned char>((unsigned(top)>>3)&1);
    else if(top&8)throw std::runtime_error("unexpected field flag");
    return x;
}

struct Left {Fe c,h;uint32_t pair;unsigned char trace;};
struct Right {Fe c;uint32_t pair;};
static uint32_t packpair(unsigned a,unsigned b){
    if(a>=b||b>=16384)throw std::runtime_error("invalid source pair");
    return uint32_t(a)|(uint32_t(b)<<14);
}
static unsigned first(uint32_t x){return x&16383;}
static unsigned second(uint32_t x){return x>>14;}
static Fe product(uint32_t x){return {carryless(first(x),second(x))<<2,0,0};}
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
static Left read_left(std::istream&i){
    Left r{};r.c=getfe(i);r.h=getfe(i,&r.trace);r.pair=get32(i);return r;
}
static Right read_right(std::istream&i){Right r{};r.c=getfe(i);r.pair=get32(i);return r;}

static int prepare(int argc,char**argv){
    if(argc!=9)throw std::runtime_error("prepare support index receipt first last cap_seconds rss_bytes");
    auto columns=support(argv[2]);
    const unsigned lo=std::stoul(argv[5]),hi=std::stoul(argv[6]);
    const uint64_t cap_ns=std::stoull(argv[7])*1000000000ULL;
    const uint64_t rss_cap=std::stoull(argv[8]);
    if(lo<1||hi>16383||lo>hi)throw std::runtime_error("bad seed range");
    Field f(131);Fe one{1,0,0};
    std::ofstream out(argv[3],std::ios::binary);
    if(!out)throw std::runtime_error("cannot write packed index");
    out.write("S3STRM1",8);put16(out,uint16_t(lo));put16(out,uint16_t(hi));
    uint64_t start=ticks(),pairs=0,entries=0;
    unsigned min_pairs=65535,max_pairs=0;
    for(unsigned seed=lo;seed<=hi;++seed){
        if(ticks()-start>=cap_ns||rss()>rss_cap)
            throw std::runtime_error("prepare resource cap reached");
        Fe s{uint64_t(seed)<<1,0,0};
        Fe s1=frob(f,s,26),s2=frob(f,s,39);
        std::vector<Left> left;std::vector<Right> right;
        unsigned pair_count=0;
        for(unsigned a=1;a<16384;++a){
            unsigned b=a^seed;
            if(a>=b||columns[a]<0||columns[b]<0||columns[a]==columns[b])continue;
            ++pair_count;
            uint32_t descriptor=packpair(a,b);
            Fe p=product(descriptor);
            Fe p1=frob(f,p,26),p2=frob(f,p,39);
            for(Fe c:quadratic_roots(f,xo(one,f.sq(p1)),p1,f.sq(s1))){
                if(zero(c))throw std::runtime_error("zero left coordinate");
                Fe ac=f.sq(xo(c,f.inverse(c))),h=halftrace(f,ac);
                left.push_back({c,h,descriptor,tracebit(f,ac,h)});
            }
            for(Fe d:quadratic_roots(f,xo(one,f.sq(p2)),p2,f.sq(s2))){
                if(zero(d))throw std::runtime_error("zero right coordinate");
                right.push_back({d,descriptor});
            }
        }
        if(pair_count<1974||pair_count>2147||left.size()!=2*pair_count||
           right.size()!=2*pair_count||left.size()>65535)
            throw std::runtime_error("seed support/output count drift");
        auto left_less=[](const Left&a,const Left&b){return FeLess{}(a.c,b.c);};
        auto right_less=[](const Right&a,const Right&b){return FeLess{}(a.c,b.c);};
        std::sort(left.begin(),left.end(),left_less);
        std::sort(right.begin(),right.end(),right_less);
        put16(out,uint16_t(seed));put16(out,uint16_t(left.size()));
        put16(out,uint16_t(right.size()));
        for(const auto&r:left)write_left(out,r);
        for(const auto&r:right)write_right(out,r);
        if(!out)throw std::runtime_error("packed index write failed");
        pairs+=pair_count;entries+=left.size();
        min_pairs=std::min(min_pairs,pair_count);max_pairs=std::max(max_pairs,pair_count);
    }
    out.close();
    if(!out)throw std::runtime_error("packed index close failed");
    std::ifstream stored(argv[3],std::ios::binary|std::ios::ate);
    uint64_t bytes=uint64_t(stored.tellg());
    if(bytes!=12+uint64_t(hi-lo+1)*6+59*entries)
        throw std::runtime_error("packed index size mismatch");
    std::ofstream receipt(argv[4]);
    receipt<<"{\"status\":\"COMPLETE_PACKED_SEED_PREPARE\",\"seed_first\":"<<lo
           <<",\"seed_last\":"<<hi<<",\"seed_count\":"<<(hi-lo+1)
           <<",\"usable_mask_pairs\":"<<pairs
           <<",\"entries_per_rotation\":"<<entries
           <<",\"min_pairs_per_seed\":"<<min_pairs
           <<",\"max_pairs_per_seed\":"<<max_pairs
           <<",\"packed_bytes\":"<<bytes
           <<",\"setup_ns\":"<<(ticks()-start)
           <<",\"peak_rss_bytes\":"<<rss()<<"}\n";
    return 0;
}

static int query(int argc,char**argv){
    if(argc!=8)throw std::runtime_error("query index support z receipt cap_seconds rss_bytes");
    uint64_t startup_start=ticks();
    auto columns=support(argv[3]);
    Field f(131);Fe one{1,0,0};
    uint64_t startup_ns=ticks()-startup_start,start=ticks();
    Fe z=decimal(argv[4]);
    if(zero(z)||highbit(z)>=131)throw std::runtime_error("invalid proposed output");
    Fe az=f.sq(xo(z,f.inverse(z))),hz=halftrace(f,az);
    unsigned char tz=tracebit(f,az,hz);
    std::ifstream in(argv[2],std::ios::binary);
    char magic[8];in.read(magic,8);
    if(!in||std::string(magic,7)!="S3STRM1"||magic[7]!='\0')
        throw std::runtime_error("bad packed index magic");
    unsigned lo=get16(in),hi=get16(in);
    const uint64_t cap_ns=std::stoull(argv[6])*1000000000ULL;
    const uint64_t rss_cap=std::stoull(argv[7]);
    if(lo<1||hi>16383||lo>hi)throw std::runtime_error("bad packed index range");
    struct Hit{unsigned seed,a,b,c,d;Fe p,q;};
    std::vector<Hit> hits;
    uint64_t entries=0,matched=0,batch_terms=0;
    for(unsigned seed=lo;seed<=hi;++seed){
        if(ticks()-start>=cap_ns||rss()>rss_cap)
            throw std::runtime_error("query resource cap reached");
        unsigned actual=get16(in),nl=get16(in),nr=get16(in);
        if(actual!=seed||nl<3948||nl>4294||nr!=nl)
            throw std::runtime_error("packed seed/count drift");
        std::vector<Left> left(nl);std::vector<Right> right(nr);
        for(auto&r:left)r=read_left(in);
        for(auto&r:right)r=read_right(in);
        entries+=nl;
        std::vector<Fe> scales(nl,Fe{}),prefix{one},terms;
        std::vector<size_t> selected;
        for(size_t i=0;i<left.size();++i){
            if(left[i].trace!=tz)continue;
            Fe k=xo(one,f.mul(z,left[i].c));
            if(zero(k))continue;
            selected.push_back(i);terms.push_back(k);
            prefix.push_back(f.mul(prefix.back(),k));
        }
        batch_terms+=selected.size();
        if(!selected.empty()){
            Fe tail=f.inverse(prefix.back());
            for(size_t j=selected.size();j-->0;){
                Fe invk=f.mul(tail,prefix[j]);tail=f.mul(tail,terms[j]);
                scales[selected[j]]=f.mul(xo(one,terms[j]),f.sq(invk));
            }
            if(!eq(tail,one))throw std::runtime_error("batch inverse failed");
        }
        auto less=[](const Right&r,Fe value){return FeLess{}(r.c,value);};
        for(size_t i=0;i<left.size();++i){
            const auto&l=left[i];
            if(l.trace!=tz)continue;
            Fe u=f.mul(z,l.c),k=xo(one,u);
            std::vector<Fe> roots;
            if(zero(k))roots=quadratic_roots(f,Fe{},u,xo(f.sq(l.c),f.sq(z)));
            else {
                Fe d=f.mul(scales[i],xo(l.h,hz));
                roots={d,xo(d,scales[i])};
            }
            for(Fe d:roots){
                auto it=std::lower_bound(right.begin(),right.end(),d,less);
                for(;it!=right.end()&&eq(it->c,d);++it){
                    ++matched;
                    unsigned a=first(l.pair),b=second(l.pair);
                    unsigned c=first(it->pair),e=second(it->pair);
                    if(columns[a]==columns[c]||columns[a]==columns[e]||
                       columns[b]==columns[c]||columns[b]==columns[e])continue;
                    hits.push_back({seed,a,b,c,e,product(l.pair),product(it->pair)});
                }
            }
        }
    }
    if(in.peek()!=EOF)throw std::runtime_error("packed index has trailing bytes");
    uint64_t elapsed=ticks()-start;
    std::ofstream out(argv[5]);
    out<<"{\"status\":\"COMPLETE_PACKED_SEED_QUERY\",\"seed_first\":"<<lo
       <<",\"seed_last\":"<<hi<<",\"seeds_queried\":"<<(hi-lo+1)
       <<",\"left_entries_checked\":"<<entries
       <<",\"batch_inverse_terms\":"<<batch_terms
       <<",\"coordinate_matches_before_cross_column\":"<<matched
       <<",\"target_independent_startup_ns\":"<<startup_ns
       <<",\"query_ns\":"<<elapsed
       <<",\"peak_rss_bytes\":"<<rss()<<",\"hits\":[";
    for(size_t i=0;i<hits.size();++i){
        if(i)out<<",";
        auto h=hits[i];
        out<<"{\"seed\":"<<h.seed<<",\"masks\":["<<h.a<<","<<h.b<<","<<h.c<<","<<h.d
           <<"],\"p\":";write_fe(out,h.p);
        out<<",\"q\":";write_fe(out,h.q);out<<"}";
    }
    out<<"]}\n";
    return 0;
}

int main(int argc,char**argv){
try{
    if(argc<2)throw std::runtime_error("missing command");
    std::string command=argv[1];
    if(command=="prepare")return prepare(argc,argv);
    if(command=="query")return query(argc,argv);
    throw std::runtime_error("unknown command");
}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}
}
