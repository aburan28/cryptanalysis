// Enumerate exact N41 sparse-product relaxations and join two Frobenius windows.
#define main frozen_three_pair_main
#include "../../koblitz-s5-invariant-20260924/three_pair_s7_native.cpp"
#undef main

#include <algorithm>
#include <chrono>
#include <fstream>
#include <map>
#include <set>
#include <string>
#include <unordered_map>

using Clock=std::chrono::steady_clock;
static uint64_t ns(Clock::time_point start) {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now()-start).count();
}
static uint64_t peak_rss() {
    rusage usage{};getrusage(RUSAGE_SELF,&usage);
#if defined(__APPLE__)
    return uint64_t(usage.ru_maxrss);
#else
    return uint64_t(usage.ru_maxrss)*1024;
#endif
}
static uint64_t trace41(uint64_t x) {
    uint64_t sum=0;
    for(int i=0;i<41;++i){sum^=x;x=sq(x);}
    if(sum>1)throw std::runtime_error("trace not in base field");
    return sum;
}
static uint64_t halftrace41(uint64_t x) {
    uint64_t sum=0;
    for(int i=0;i<21;++i){sum^=x;x=sq(sq(x));}
    return sum;
}
struct LinearMap {
    std::array<uint64_t,41> pivot{},repr{};
    std::vector<uint64_t> kernel;
    int rank=0;
    explicit LinearMap(uint64_t p,const std::array<uint64_t,41>& halfcols){
        for(int i=0;i<41;++i){
            uint64_t col=mul(p,1ULL<<i)^halfcols[i],r=1ULL<<i;
            while(col){
                int bit=63-__builtin_clzll(col);
                if(pivot[bit]){col^=pivot[bit];r^=repr[bit];}
                else{pivot[bit]=col;repr[bit]=r;++rank;break;}
            }
            if(!col)kernel.push_back(r);
        }
        if(rank+int(kernel.size())!=41 || kernel.size()>2)
            throw std::runtime_error("unexpected linear-map rank");
    }
    bool solve(uint64_t rhs,uint64_t& z)const{
        z=0;
        while(rhs){
            int bit=63-__builtin_clzll(rhs);
            if(!pivot[bit])return false;
            rhs^=pivot[bit];z^=repr[bit];
        }
        return true;
    }
};
struct Witness {uint16_t product_mask;uint8_t seed_sum,branch;uint64_t z;};
struct Row {Point point;Witness witness;};
static std::array<uint64_t,41> frob_basis(int rotation){
    std::array<uint64_t,41> basis{};
    for(int i=0;i<41;++i){
        uint64_t x=1ULL<<i;
        for(int j=0;j<rotation;++j)x=sq(x);
        basis[i]=x;
    }
    return basis;
}
static uint64_t apply_frob(uint64_t x,const std::array<uint64_t,41>& basis){
    uint64_t result=0;
    while(x){int i=__builtin_ctzll(x);result^=basis[i];x&=x-1;}
    return result;
}
static Point apply_frob(Point p,const std::array<uint64_t,41>& basis){
    return finite(apply_frob(p.x,basis),apply_frob(p.y,basis));
}
static bool less_point(const Row& a,const Row& b){
    if(a.point.x!=b.point.x)return a.point.x<b.point.x;
    return a.point.y<b.point.y;
}
static void write_witness(std::ostream& out,const Witness& w){
    out<<"{\"product_mask\":"<<w.product_mask<<",\"seed_sum\":"
       <<unsigned(w.seed_sum)<<",\"branch\":"<<unsigned(w.branch)
       <<",\"reciprocal_z\":"<<w.z<<"}";
}
int main(int argc,char** argv){
    try{
        if(argc!=3)throw std::runtime_error("usage: direct_join targets.txt receipt.json");
        std::ifstream input(argv[1]);if(!input)throw std::runtime_error("input open");
        int count;input>>count;if(count!=513)throw std::runtime_error("expected seeded 513-point panel");
        struct Target{std::string label;Point point;};
        std::vector<Target> targets;
        for(int i=0;i<count;++i){
            std::string label;uint64_t x,y;input>>label>>x>>y;
            Point p=finite(x,y);if(!input||!on_curve(p))throw std::runtime_error("bad target");
            targets.push_back({label,p});
        }
        std::string extra;if(input>>extra)throw std::runtime_error("trailing input");
        const auto setup_start=Clock::now();
        std::array<uint64_t,41> halfcols{};
        for(int i=0;i<41;++i)halfcols[i]=halftrace41(sq(1ULL<<i));
        std::array<uint64_t,64> halfs{};
        for(int s=1;s<64;++s)halfs[s]=halftrace41(sq(uint64_t(s)<<1));
        std::unordered_map<Point,Witness,PointHash> unique;
        unique.reserve(600000);
        std::map<int,uint64_t> ranks;
        uint64_t linear_solutions=0,trace_zero=0,rational_z=0;
        bool setup_cap=false;
        for(int pm=0;pm<2048;++pm){
            const uint64_t p=uint64_t(pm)<<2;
            LinearMap linear(p,halfcols);++ranks[linear.rank];
            for(int sm=1;sm<64;++sm){
                for(int eps=0;eps<2;++eps){
                    uint64_t particular;
                    if(!linear.solve(halfs[sm]^uint64_t(eps),particular))continue;
                    for(unsigned k=0;k<(1U<<linear.kernel.size());++k){
                        uint64_t z=particular;
                        for(size_t i=0;i<linear.kernel.size();++i)
                            if(k&(1U<<i))z^=linear.kernel[i];
                        ++linear_solutions;
                        if(!z||trace41(z))continue;
                        ++trace_zero;
                        uint64_t x=inv(z),rhs=x^sq(z);
                        if(trace41(rhs))continue;
                        ++rational_z;
                        uint64_t u=halftrace41(rhs),y=mul(x,u);
                        Point q=finite(x,y),negative=neg(q);
                        if(!on_curve(q)||!on_curve(negative))
                            throw std::runtime_error("point lift failed");
                        Witness w{uint16_t(pm),uint8_t(sm),uint8_t(eps),z};
                        unique.emplace(q,w);unique.emplace(negative,w);
                    }
                }
            }
            if((pm&31)==31 && (ns(setup_start)>120000000000ULL||
                                peak_rss()>4ULL*1024*1024*1024)){
                setup_cap=true;break;
            }
        }
        if(setup_cap)throw std::runtime_error("setup cap before complete enumeration");
        auto basis20=frob_basis(20),basis30=frob_basis(30);
        std::vector<Row> left;left.reserve(unique.size());
        std::unordered_map<Point,Witness,PointHash> right;
        right.reserve(unique.size()*2);
        for(const auto& entry:unique){
            left.push_back({apply_frob(entry.first,basis20),entry.second});
            right.emplace(apply_frob(entry.first,basis30),entry.second);
        }
        std::sort(left.begin(),left.end(),less_point);
        if(ns(setup_start)>120000000000ULL||peak_rss()>4ULL*1024*1024*1024)
            throw std::runtime_error("setup cap after rotation/index");
        const uint64_t setup_ns=ns(setup_start);
        struct QueryResult{std::string label,status;Point target,left,right;
                           Witness left_w,right_w;uint64_t probes,online_ns,replay_ns;};
        std::vector<QueryResult> results;
        for(const auto& target:targets){
            const auto query_start=Clock::now();
            QueryResult result{};result.label=target.label;result.target=target.point;
            result.status="COMPLETE_RELAXED_NO_SUM";
            for(const auto& candidate:left){
                ++result.probes;
                Point needed=add(target.point,neg(candidate.point));
                auto found=right.find(needed);
                if(found!=right.end()){
                    const auto replay_start=Clock::now();
                    if(!(add(candidate.point,needed)==target.point))
                        throw std::runtime_error("relaxed exact group hit invalid");
                    result.replay_ns=ns(replay_start);
                    result.status="RELAXED_SUM_HIT";
                    result.left=candidate.point;result.right=needed;
                    result.left_w=candidate.witness;result.right_w=found->second;
                    break;
                }
                if((result.probes&16383)==0 &&
                   (ns(query_start)>120000000000ULL||peak_rss()>4ULL*1024*1024*1024)){
                    result.status="BOUNDED_UNKNOWN";break;
                }
            }
            result.online_ns=ns(query_start);
            results.push_back(result);
        }
        std::ofstream out(argv[2]);if(!out)throw std::runtime_error("receipt open");
        out<<"{\n\"status\":\"COMPLETE_N41_RELAXED_TWO_PAIR_PANEL\","
           <<"\n\"candidate_id\":null,\"field\":\"GF(2)[t]/(t^41+t^3+1)\","
           <<"\n\"product_mask_count\":2048,\"seed_sum_count\":63,"
           <<"\n\"rank_histogram\":{\"39\":"<<ranks[39]
           <<",\"40\":"<<ranks[40]<<",\"41\":"<<ranks[41]<<"},"
           <<"\n\"raw_linear_solutions\":"<<linear_solutions
           <<",\"nonzero_trace_zero_solutions\":"<<trace_zero
           <<",\"curve_rational_reciprocals\":"<<rational_z
           <<",\"unique_unrotated_curve_points\":"<<unique.size()
           <<",\"left_rotated_points\":"<<left.size()
           <<",\"right_rotated_points\":"<<right.size()
           <<",\"reusable_setup_ns\":"<<setup_ns
           <<",\"peak_rss_bytes\":"<<peak_rss()
           <<",\"limits\":{\"setup_seconds\":120,\"online_seconds_per_query\":120,"
             "\"rss_bytes\":4294967296,\"workers\":1},\n\"queries\":[";
        for(size_t i=0;i<results.size();++i){
            const auto& r=results[i];
            out<<(i?",":"")<<"{\"label\":\""<<r.label
               <<"\",\"status\":\""<<r.status<<"\",\"target\":["
               <<r.target.x<<","<<r.target.y<<"],\"probes\":"<<r.probes
               <<",\"online_ns\":"<<r.online_ns
               <<",\"relation_check_ns\":"<<r.replay_ns;
            if(r.status=="RELAXED_SUM_HIT"){
                out<<",\"left_point\":["<<r.left.x<<","<<r.left.y
                   <<"],\"right_point\":["<<r.right.x<<","<<r.right.y
                   <<"],\"left_witness\":";
                write_witness(out,r.left_w);
                out<<",\"right_witness\":";write_witness(out,r.right_w);
            }
            out<<"}";
        }
        out<<"]}\n";
        std::cout<<"status=COMPLETE_N41_RELAXED_TWO_PAIR_PANEL points="<<unique.size();
        for(const auto& r:results)std::cout<<" "<<r.label<<":"<<r.status<<":"<<r.probes;
        std::cout<<"\n";
        return 0;
    }catch(const std::exception& error){
        std::cerr<<"error: "<<error.what()<<"\n";return 2;
    }
}
