// Warm N41 W6 six-pair IC worker: index and factor logs precede the target.
#define main unused_frozen_helper_main
#include "../n131_w18_four_pairs/native_join/frozen_source/helper.cpp"
#undef main

#include <random>

struct Atom {Point point;uint8_t mask,sign,column;uint64_t coefficient;};
struct PairState {Point sum;uint8_t a,b,seed;uint32_t columns;};
struct QuadState {Point sum;uint16_t first,second;uint32_t columns;};

uint64_t ticks() {return uint64_t(std::chrono::duration_cast<std::chrono::nanoseconds>(
    std::chrono::steady_clock::now().time_since_epoch()).count());}
uint64_t rss() {rusage u{};getrusage(RUSAGE_SELF,&u);
#ifdef __APPLE__
    return uint64_t(u.ru_maxrss);
#else
    return uint64_t(u.ru_maxrss)*1024;
#endif
}

Point scalar(uint64_t k,Point p) {
    Point result{};
    while(k) {
        if(k&1)result=add(result,p);
        k>>=1;
        if(k)p=add(p,p);
    }
    return result;
}

std::vector<PairState> make_pairs(const std::vector<Atom>& atoms) {
    std::vector<PairState> out;
    for(size_t i=0;i<atoms.size();++i)for(size_t j=0;j<atoms.size();++j) {
        if(atoms[i].mask>=atoms[j].mask||atoms[i].column==atoms[j].column)continue;
        out.push_back({add(atoms[i].point,atoms[j].point),uint8_t(i),uint8_t(j),
                       uint8_t(atoms[i].mask^atoms[j].mask),
                       (uint32_t(1)<<atoms[i].column)|(uint32_t(1)<<atoms[j].column)});
    }
    return out;
}

std::vector<QuadState> same_seed_quads(const std::vector<PairState>& a,
                                      const std::vector<PairState>& b) {
    std::array<std::vector<uint16_t>,64> by_seed;
    for(size_t j=0;j<b.size();++j)by_seed[b[j].seed].push_back(uint16_t(j));
    std::vector<QuadState> out;
    for(size_t i=0;i<a.size();++i)for(uint16_t j:by_seed[a[i].seed]) {
        if(a[i].columns&b[j].columns)continue;
        out.push_back({add(a[i].sum,b[j].sum),uint16_t(i),j,
                       a[i].columns|b[j].columns});
    }
    return out;
}

int main(int argc,char**argv) {
try {
    if(argc!=8)throw std::runtime_error("usage: online_worker atoms.txt logs.txt hit.json result.json max_probes cap_seconds seed");
    std::ifstream input(argv[1]);if(!input)throw std::runtime_error("missing frozen input");
    uint64_t qx,qy,order;int blocks;input>>qx>>qy>>order>>blocks;
    constexpr uint64_t R=549756390943ULL;
    if(!input||qx!=0||qy!=0||order!=R||blocks!=6)
        throw std::runtime_error("wrong input or subgroup");
    std::ifstream log_input(argv[2]);if(!log_input)throw std::runtime_error("missing factor logs");
    std::array<uint64_t,26> logs{};
    for(auto& value:logs){log_input>>value;if(!log_input||value>=R)throw std::runtime_error("invalid factor log");}
    std::string log_tail;if(log_input>>log_tail)throw std::runtime_error("trailing factor logs");
    std::array<std::vector<Atom>,6> atoms;
    for(int block=0;block<6;++block) {
        int rotation,size;input>>rotation>>size;
        if(!input||rotation!=block*5||size!=64)throw std::runtime_error("wrong rotation block");
        for(int i=0;i<size;++i) {
            uint64_t x,y,coefficient;int mask,sign,column;input>>x>>y>>mask>>sign>>column>>coefficient;
            Point p=finite(x,y);
            if(!input||!on_curve(p)||mask<1||mask>=64||sign<0||sign>1||
               column<0||column>=26||coefficient>=R)throw std::runtime_error("invalid source atom");
            atoms[block].push_back({p,uint8_t(mask),uint8_t(sign),uint8_t(column),coefficient});
        }
    }
    std::string tail;if(input>>tail)throw std::runtime_error("trailing input");
    uint64_t start=ticks();
    std::array<std::vector<PairState>,6> pairs;
    for(int i=0;i<6;++i)pairs[i]=make_pairs(atoms[i]);
    for(int i=1;i<6;++i)if(pairs[i].size()!=pairs[0].size())
        throw std::runtime_error("pair count drift across rotations");
    if(pairs[0].size()>=4096)throw std::runtime_error("pair packing overflow");
    std::unordered_multimap<Point,uint32_t,PointHash> left;
    left.reserve(pairs[0].size()*pairs[1].size());
    for(size_t i=0;i<pairs[0].size();++i)for(size_t j=0;j<pairs[1].size();++j) {
        if(pairs[0][i].columns&pairs[1][j].columns)continue;
        left.emplace(add(pairs[0][i].sum,pairs[1][j].sum),
                     uint32_t(i)|(uint32_t(j)<<12));
    }
    auto right_a=same_seed_quads(pairs[2],pairs[3]);
    auto right_b=same_seed_quads(pairs[4],pairs[5]);
    if(right_a.empty()||right_b.empty())throw std::runtime_error("empty constrained right domain");
    uint64_t setup_ns=ticks()-start;
    const uint64_t max_probes=std::stoull(argv[5]);
    const uint64_t cap_ns=std::stoull(argv[6])*1000000000ULL;
    const uint64_t seed=std::stoull(argv[7]);
    std::cout<<"READY setup_ns="<<setup_ns<<" rss="<<rss()<<std::endl;
    if(!(std::cin>>qx>>qy))throw std::runtime_error("missing streamed target");
    uint64_t query_start=ticks();
    Point q=finite(qx,qy);
    if(!on_curve(q)||!scalar(order,q).infinity)
        throw std::runtime_error("target outside curve or prime subgroup");
    std::mt19937_64 rng(seed);
    std::uniform_int_distribution<size_t> da(0,right_a.size()-1),db(0,right_b.size()-1);
    uint64_t search_start=ticks();
    uint64_t attempts=0,accepted=0,hits=0,column_rejects=0;
    bool found=false,timed_out=false,oom=false;
    std::array<uint16_t,6> witness{};
    while(accepted<max_probes&&!found) {
        if((attempts&4095)==0) {
            if(ticks()-query_start>=cap_ns){timed_out=true;break;}
            if(rss()>4ULL*1024*1024*1024){oom=true;break;}
        }
        ++attempts;
        const auto& a=right_a[da(rng)];const auto& b=right_b[db(rng)];
        if(a.columns&b.columns)continue;
        ++accepted;
        Point right=add(a.sum,b.sum);
        Point wanted=add(q,neg(right));
        auto range=left.equal_range(wanted);
        for(auto it=range.first;it!=range.second;++it) {
            ++hits;
            uint16_t i=it->second&4095,j=it->second>>12;
            uint32_t left_cols=pairs[0][i].columns|pairs[1][j].columns;
            if(left_cols&(a.columns|b.columns)){++column_rejects;continue;}
            witness={i,j,a.first,a.second,b.first,b.second};
            found=true;break;
        }
    }
    uint64_t search_end=ticks();
    uint64_t relation_end=search_end,recovery_end=search_end,verify_end=search_end;
    uint64_t recovered=0;
    if(found) {
        Point replay{};uint32_t seen=0;
        for(int block=0;block<6;++block) {
            const auto& pair=pairs[block][witness[block]];
            if(seen&pair.columns)throw std::runtime_error("column replay collision");
            seen|=pair.columns;
            replay=add(replay,atoms[block][pair.a].point);
            replay=add(replay,atoms[block][pair.b].point);
        }
        if(!(replay==q)||pairs[2][witness[2]].seed!=pairs[3][witness[3]].seed||
           pairs[4][witness[4]].seed!=pairs[5][witness[5]].seed)
           throw std::runtime_error("relation replay failed");
        relation_end=ticks();
        for(int block=0;block<6;++block) {
            const auto& pair=pairs[block][witness[block]];
            for(const auto& atom:{atoms[block][pair.a],atoms[block][pair.b]})
                recovered=(recovered+uint64_t((__uint128_t(atom.coefficient)*logs[atom.column])%R))%R;
        }
        recovery_end=ticks();
        if(!(scalar(recovered,finite(2056947637384ULL,1635505394702ULL))==q))
            throw std::runtime_error("scalar group replay failed");
        verify_end=ticks();
    }
    uint64_t online_ns=verify_end-query_start;
    std::ofstream hit(argv[3]);if(!hit)throw std::runtime_error("cannot save hit");
    if(found) {
        hit<<"{\"status\":\"NATIVE_SCALAR_VERIFIED\",\"masks\":[";
        for(int block=0;block<6;++block) {
            const auto& pair=pairs[block][witness[block]];
            if(block)hit<<",";
            hit<<int(atoms[block][pair.a].mask)<<","<<int(atoms[block][pair.b].mask);
        }
        hit<<"],\"signs\":[";
        for(int block=0;block<6;++block) {
            const auto& pair=pairs[block][witness[block]];
            if(block)hit<<",";
            hit<<int(atoms[block][pair.a].sign)<<","<<int(atoms[block][pair.b].sign);
        }
        hit<<"],\"columns\":[";
        for(int block=0;block<6;++block) {
            const auto& pair=pairs[block][witness[block]];
            if(block)hit<<",";
            hit<<int(atoms[block][pair.a].column)<<","<<int(atoms[block][pair.b].column);
        }
        hit<<"],\"seed_sums\":[";
        for(int block=0;block<6;++block)hit<<(block?",":"")<<int(pairs[block][witness[block]].seed);
        hit<<"],\"raw_sum\":["<<q.x<<","<<q.y<<"],\"recovered_scalar\":"<<recovered<<"}\n";
    }
    hit.close();
    const char* status=found?"VERIFIED_SCALAR":oom?"OOM":
        timed_out?"CENSORED_TIME":"CENSORED_PROBES";
    std::ofstream result(argv[4]);if(!result)throw std::runtime_error("cannot save result");
    result<<"{\"status\":\""<<status<<"\",\"pair_states_per_rotation\":"
          <<pairs[0].size()<<",\"left_four_states\":"<<left.size()
          <<",\"right_quad_a\":"<<right_a.size()<<",\"right_quad_b\":"<<right_b.size()
          <<",\"attempts\":"<<attempts<<",\"accepted_probes\":"<<accepted
          <<",\"group_hits\":"<<hits<<",\"column_rejects\":"<<column_rejects
          <<",\"setup_ns\":"<<setup_ns<<",\"online_ns\":"<<online_ns
          <<",\"exclusive_phase_ns\":{\"target_query\":"<<search_start-query_start
          <<",\"target_PDP\":"<<search_end-search_start
          <<",\"target_relation_check\":"<<relation_end-search_end
          <<",\"target_descent\":"<<recovery_end-relation_end
          <<",\"target_recovery_check\":"<<verify_end-recovery_end<<"}"
          <<",\"recovered_scalar\":";
    if(found)result<<recovered;else result<<"null";
    result<<",\"scalar_group_replay_verified\":"<<(found?"true":"false")
          <<",\"peak_rss_bytes\":"<<rss()
          <<",\"rng_seed\":"<<seed<<"}\n";
    std::cout<<status<<" probes="<<accepted<<" group_hits="<<hits
             <<" online_s="<<double(online_ns)/1e9<<" rss="<<rss()<<"\n";
}catch(const std::exception& error){std::cerr<<error.what()<<"\n";return 1;}
}
