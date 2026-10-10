// Seed-partitioned N41 public relation join; no materialized free-four index.
#define main unused_frozen_helper_main
#include "../n131_w18_four_pairs/native_join/frozen_source/helper.cpp"
#undef main

#include <sstream>

struct Atom {Point point;uint8_t mask,sign,column;};
struct PairState {Point sum;uint8_t a,b,seed;uint32_t columns;};
struct QuadState {Point sum;uint16_t first,second;uint32_t columns;uint8_t seed;};

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
                       a[i].columns|b[j].columns,a[i].seed});
    }
    return out;
}

static void output_point(std::ostream& out, Point p) {
    if(p.infinity)out<<"null";
    else out<<"["<<p.x<<","<<p.y<<"]";
}

int main(int argc,char**argv) {
try {
    if(argc!=6)throw std::runtime_error("usage: native input hit.json result.json cap_seconds rss_cap_bytes");
    std::ifstream input(argv[1]);if(!input)throw std::runtime_error("missing frozen input");
    uint64_t qx,qy,order;int blocks;input>>qx>>qy>>order>>blocks;
    if(!input||order!=549756390943ULL||blocks!=6)
        throw std::runtime_error("wrong input or subgroup");
    Point q=finite(qx,qy);
    if(!on_curve(q)||!scalar(order,q).infinity)
        throw std::runtime_error("target outside curve or prime subgroup");
    std::array<std::vector<Atom>,6> atoms;
    for(int block=0;block<6;++block) {
        int rotation,size;input>>rotation>>size;
        if(!input||rotation!=block*5||size!=64)throw std::runtime_error("wrong rotation block");
        for(int i=0;i<size;++i) {
            uint64_t x,y;int mask,sign,column;input>>x>>y>>mask>>sign>>column;
            Point p=finite(x,y);
            if(!input||!on_curve(p)||mask<1||mask>=64||sign<0||sign>1||
               column<0||column>=26)throw std::runtime_error("invalid source atom");
            atoms[block].push_back({p,uint8_t(mask),uint8_t(sign),uint8_t(column)});
        }
    }
    std::string tail;if(input>>tail)throw std::runtime_error("trailing input");
    uint64_t start=ticks();
    std::array<std::vector<PairState>,6> pairs;
    for(int i=0;i<6;++i)pairs[i]=make_pairs(atoms[i]);
    for(int i=0;i<6;++i)if(pairs[i].size()!=1956)
        throw std::runtime_error("pair count drift");
    auto right_a=same_seed_quads(pairs[2],pairs[3]);
    auto right_b=same_seed_quads(pairs[4],pairs[5]);
    if(right_a.size()!=51840||right_b.size()!=51840)
        throw std::runtime_error("constrained quad count drift");
    std::array<std::vector<uint16_t>,64> by_a,by_b;
    for(size_t i=0;i<right_a.size();++i)by_a[right_a[i].seed].push_back(uint16_t(i));
    for(size_t i=0;i<right_b.size();++i)by_b[right_b[i].seed].push_back(uint16_t(i));
    uint64_t setup_ns=ticks()-start;
    uint64_t query_start=ticks();
    uint64_t cap_ns=std::stoull(argv[4])*1000000000ULL;
    uint64_t rss_cap=std::stoull(argv[5]);
    uint64_t right_tested=0,right_inserted=0,free_tested=0,group_hits=0,
             column_rejects=0,build_ns=0,probe_ns=0;
    size_t seeds_complete=0;
    bool found=false,censored=false,oom=false;
    uint8_t found_seed=0;
    std::array<uint16_t,6> witness{};
    for(int seed=1;seed<64&&!found&&!censored&&!oom;++seed) {
        if(ticks()-query_start>=cap_ns){censored=true;break;}
        if(rss()>rss_cap){oom=true;break;}
        uint64_t phase=ticks();
        std::unordered_multimap<Point,uint32_t,PointHash> right;
        size_t allowance=0;
        for(int other=1;other<64;++other)
            if((seed^other)<8)allowance+=by_b[other].size();
        right.reserve(by_a[seed].size()*allowance);
        for(uint16_t ai:by_a[seed]) {
            const auto& a=right_a[ai];
            for(int other=1;other<64;++other) {
                if((seed^other)>=8)continue;
                for(uint16_t bi:by_b[other]) {
                    ++right_tested;
                    const auto& b=right_b[bi];
                    if(a.columns&b.columns)continue;
                    right.emplace(add(a.sum,b.sum),uint32_t(ai)|(uint32_t(bi)<<16));
                    ++right_inserted;
                    if((right_tested&16383)==0) {
                        if(ticks()-query_start>=cap_ns){censored=true;break;}
                        if(rss()>rss_cap){oom=true;break;}
                    }
                }
                if(censored||oom)break;
            }
            if(censored||oom)break;
        }
        build_ns+=ticks()-phase;
        if(censored||oom)break;
        phase=ticks();
        for(size_t i=0;i<pairs[0].size()&&!found&&!censored&&!oom;++i) {
            const auto& first=pairs[0][i];
            for(size_t j=0;j<pairs[1].size();++j) {
                const auto& second=pairs[1][j];
                if(first.columns&second.columns)continue;
                ++free_tested;
                Point wanted=add(q,neg(add(first.sum,second.sum)));
                auto range=right.equal_range(wanted);
                for(auto it=range.first;it!=range.second;++it) {
                    ++group_hits;
                    const auto& a=right_a[it->second&65535];
                    const auto& b=right_b[it->second>>16];
                    uint32_t leftcols=first.columns|second.columns;
                    if(leftcols&(a.columns|b.columns)){
                        ++column_rejects;continue;
                    }
                    witness={uint16_t(i),uint16_t(j),a.first,a.second,b.first,b.second};
                    Point replay{};uint32_t seen=0;
                    for(int block=0;block<6;++block){
                        const auto& pair=pairs[block][witness[block]];
                        if(seen&pair.columns)throw std::runtime_error("column replay collision");
                        seen|=pair.columns;
                        replay=add(replay,atoms[block][pair.a].point);
                        replay=add(replay,atoms[block][pair.b].point);
                    }
                    if(!(replay==q)||a.seed!=seed||(a.seed^b.seed)>=8)
                        throw std::runtime_error("relation replay failed");
                    found=true;found_seed=uint8_t(seed);break;
                }
                if(found)break;
                if((free_tested&16383)==0) {
                    if(ticks()-query_start>=cap_ns){censored=true;break;}
                    if(rss()>rss_cap){oom=true;break;}
                }
            }
        }
        probe_ns+=ticks()-phase;
        if(!found&&!censored&&!oom)++seeds_complete;
    }
    uint64_t online_ns=ticks()-query_start;
    std::ofstream hit(argv[2]);if(!hit)throw std::runtime_error("cannot save hit");
    if(found){
        hit<<"{\"status\":\"NATIVE_RELATION_PENDING_SAGE\",\"masks\":[";
        for(int block=0;block<6;++block){
            const auto& p=pairs[block][witness[block]];
            if(block)hit<<",";
            hit<<unsigned(atoms[block][p.a].mask)<<","<<unsigned(atoms[block][p.b].mask);
        }
        hit<<"],\"signs\":[";
        for(int block=0;block<6;++block){
            const auto& p=pairs[block][witness[block]];
            if(block)hit<<",";
            hit<<unsigned(atoms[block][p.a].sign)<<","<<unsigned(atoms[block][p.b].sign);
        }
        hit<<"],\"columns\":[";
        for(int block=0;block<6;++block){
            const auto& p=pairs[block][witness[block]];
            if(block)hit<<",";
            hit<<unsigned(atoms[block][p.a].column)<<","<<unsigned(atoms[block][p.b].column);
        }
        hit<<"],\"seed_sums\":[";
        for(int block=0;block<6;++block){
            const auto& p=pairs[block][witness[block]];
            if(block)hit<<",";
            hit<<unsigned(p.seed);
        }
        hit<<"],\"raw_sum\":["<<q.x<<","<<q.y<<"]}\n";
    }else hit<<"{\"status\":\"NO_HIT_WITHIN_CAP\"}\n";
    std::ofstream result(argv[3]);if(!result)throw std::runtime_error("cannot save result");
    std::string status=found?"FOUND_PENDING_SAGE_REPLAY":oom?"CENSORED_MEMORY":
                       censored?"CENSORED_TIME":"COMPLETE_NO_HIT";
    result<<"{\"status\":\""<<status<<"\",\"pair_states_per_rotation\":1956"
          <<",\"right_quad_a\":"<<right_a.size()
          <<",\"right_quad_b\":"<<right_b.size()
          <<",\"free_four_index_entries\":0"
          <<",\"right_tested\":"<<right_tested
          <<",\"right_inserted\":"<<right_inserted
          <<",\"free_tested\":"<<free_tested
          <<",\"seeds_complete\":"<<seeds_complete
          <<",\"found_seed\":"<<unsigned(found_seed)
          <<",\"group_hits\":"<<group_hits
          <<",\"column_rejects\":"<<column_rejects
          <<",\"setup_ns\":"<<setup_ns
          <<",\"bucket_build_ns\":"<<build_ns
          <<",\"free_probe_ns\":"<<probe_ns
          <<",\"online_ns\":"<<online_ns
          <<",\"peak_rss_bytes\":"<<rss()<<"}\n";
    std::cout<<status<<" seed="<<unsigned(found_seed)
             <<" right_inserted="<<right_inserted
             <<" free_tested="<<free_tested
             <<" online_s="<<double(online_ns)/1e9
             <<" rss="<<rss()<<"\n";
}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}
}
