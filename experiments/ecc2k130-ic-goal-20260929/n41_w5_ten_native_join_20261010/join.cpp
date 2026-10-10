// Bounded exact 4+6 raw-group join on the frozen N41 W5 ten-source base.
#define main unused_frozen_helper_main
#include "../n131_w18_four_pairs/native_join/frozen_source/helper.cpp"
#undef main

#include <algorithm>
#include <random>

struct State { Point point; uint8_t column, mask, sign; };
struct Pair10 { Point sum; uint8_t a, b, col_a, col_b; };

static uint64_t now_ns() {
    return uint64_t(std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count());
}
static uint64_t rss_bytes() {
    rusage usage{};getrusage(RUSAGE_SELF,&usage);
#ifdef __APPLE__
    return uint64_t(usage.ru_maxrss);
#else
    return uint64_t(usage.ru_maxrss)*1024;
#endif
}
static Point four(Point p) {return add(add(p,p),add(p,p));}
static bool all_distinct(const std::array<uint8_t,10>& cols,int count) {
    uint16_t seen=0;
    for(int i=0;i<count;++i) {
        uint16_t bit=uint16_t(1)<<cols[i];
        if(seen&bit)return false;
        seen|=bit;
    }
    return true;
}
static std::vector<Pair10> pair_states(const std::vector<State>& a,
                                        const std::vector<State>& b) {
    std::vector<Pair10> out;out.reserve(a.size()*b.size());
    for(size_t i=0;i<a.size();++i)for(size_t j=0;j<b.size();++j) {
        if(a[i].column==b[j].column)continue;
        out.push_back({add(a[i].point,b[j].point),uint8_t(i),uint8_t(j),
                       a[i].column,b[j].column});
    }
    return out;
}
static uint32_t pack4(const Pair10& a,const Pair10& b) {
    return uint32_t(a.a)|(uint32_t(a.b)<<6)|(uint32_t(b.a)<<12)|(uint32_t(b.b)<<18);
}
static std::array<uint8_t,4> unpack4(uint32_t value) {
    return {uint8_t(value&63),uint8_t((value>>6)&63),
            uint8_t((value>>12)&63),uint8_t((value>>18)&63)};
}

int main(int argc,char** argv) {
  try {
    if(argc!=6)throw std::runtime_error("usage: join input hits.jsonl result.json max_probes cap_seconds");
    std::ifstream input(argv[1]);if(!input)throw std::runtime_error("missing input");
    uint64_t qx,qy,qpx,qpy,order;int block_count;
    input>>qx>>qy>>qpx>>qpy>>order>>block_count;
    if(!input||qx!=1458168294740ULL||qy!=1672312028033ULL||
       qpx!=1496345304064ULL||qpy!=1421510518509ULL||
       order!=549756390943ULL||block_count!=10)
        throw std::runtime_error("wrong exact public target, transport, or subgroup");
    Point q=finite(qx,qy),qprime=finite(qpx,qpy);
    if(!on_curve(q)||!on_curve(qprime)||
       !(add(qprime,finite(sq(qprime.x),sq(qprime.y)))==q))
        throw std::runtime_error("target transport failed");
    std::array<Point,4> targets;
    for(auto& p:targets) {
        uint64_t x,y;input>>x>>y;p=finite(x,y);
        if(!input||!on_curve(p)||!(four(p)==qprime))
            throw std::runtime_error("invalid raw target preimage");
    }
    for(int i=0;i<4;++i)for(int j=0;j<i;++j)
        if(targets[i]==targets[j])throw std::runtime_error("duplicate target preimage");
    std::array<std::vector<State>,10> blocks;
    for(auto& block:blocks) {
        int size;input>>size;
        if(!input||size!=34)throw std::runtime_error("wrong source block size");
        for(int i=0;i<size;++i) {
            uint64_t x,y;int column,mask,sign;
            input>>x>>y>>column>>mask>>sign;
            Point p=finite(x,y);
            if(!input||!on_curve(p)||column<0||column>=14||
               mask<1||mask>=32||sign<0||sign>1)
                throw std::runtime_error("invalid source state");
            block.push_back({p,uint8_t(column),uint8_t(mask),uint8_t(sign)});
        }
    }
    std::string trailing;if(input>>trailing)throw std::runtime_error("trailing input");
    const uint64_t start=now_ns();
    const uint64_t cap_ns=std::stoull(argv[5])*1000000000ULL;
    const uint64_t max_probes=std::stoull(argv[4]);
    auto p01=pair_states(blocks[0],blocks[1]);
    auto p23=pair_states(blocks[2],blocks[3]);
    auto p45=pair_states(blocks[4],blocks[5]);
    auto p67=pair_states(blocks[6],blocks[7]);
    auto p89=pair_states(blocks[8],blocks[9]);
    std::unordered_multimap<Point,uint32_t,PointHash> left;
    left.reserve(800000);
    for(const auto& a:p01)for(const auto& b:p23) {
        std::array<uint8_t,10> cols{a.col_a,a.col_b,b.col_a,b.col_b};
        if(!all_distinct(cols,4))continue;
        left.emplace(add(a.sum,b.sum),pack4(a,b));
    }
    if(left.size()!=764544)throw std::runtime_error("distinct left-four count drift");
    const uint64_t built=now_ns();
    std::mt19937_64 rng(202610102113ULL);
    std::uniform_int_distribution<size_t> d45(0,p45.size()-1),
                                          d67(0,p67.size()-1),
                                          d89(0,p89.size()-1);
    std::ofstream hits(argv[2]);if(!hits)throw std::runtime_error("cannot open hit file");
    uint64_t attempts=0,probes=0,group_hits=0,column_rejects=0;
    bool found=false,timed_out=false,memory_capped=false;
    while(probes<max_probes&&!found) {
        if((attempts&4095)==0) {
            if(now_ns()-start>=cap_ns){timed_out=true;break;}
            if(rss_bytes()>4ULL*1024*1024*1024){memory_capped=true;break;}
        }
        ++attempts;
        const auto& a=p45[d45(rng)];
        const auto& b=p67[d67(rng)];
        const auto& c=p89[d89(rng)];
        std::array<uint8_t,10> right_cols{
            a.col_a,a.col_b,b.col_a,b.col_b,c.col_a,c.col_b};
        if(!all_distinct(right_cols,6))continue;
        ++probes;
        Point right=add(add(a.sum,b.sum),c.sum);
        for(int target_index=0;target_index<4&&!found;++target_index) {
            Point needed=add(targets[target_index],neg(right));
            auto range=left.equal_range(needed);
            for(auto it=range.first;it!=range.second;++it) {
                ++group_hits;
                auto ids4=unpack4(it->second);
                std::array<uint8_t,10> cols{
                    blocks[0][ids4[0]].column,blocks[1][ids4[1]].column,
                    blocks[2][ids4[2]].column,blocks[3][ids4[3]].column,
                    a.col_a,a.col_b,b.col_a,b.col_b,c.col_a,c.col_b};
                if(!all_distinct(cols,10)){++column_rejects;continue;}
                std::array<uint8_t,10> ids{
                    ids4[0],ids4[1],ids4[2],ids4[3],
                    a.a,a.b,b.a,b.b,c.a,c.b};
                Point replay{};
                for(int j=0;j<10;++j)replay=add(replay,blocks[j][ids[j]].point);
                if(!(replay==targets[target_index])||!(four(replay)==qprime))
                    throw std::runtime_error("native group replay failed");
                hits<<"{\"status\":\"NATIVE_RELATION_PENDING_SAGE\",\"target_preimage_index\":"
                    <<target_index<<",\"indices\":[";
                for(int j=0;j<10;++j)hits<<(j?",":"")<<int(ids[j]);
                hits<<"],\"masks\":[";
                for(int j=0;j<10;++j)hits<<(j?",":"")<<int(blocks[j][ids[j]].mask);
                hits<<"],\"signs\":[";
                for(int j=0;j<10;++j)hits<<(j?",":"")<<int(blocks[j][ids[j]].sign);
                hits<<"],\"columns\":[";
                for(int j=0;j<10;++j)hits<<(j?",":"")<<int(cols[j]);
                hits<<"],\"raw_sum\":["<<replay.x<<","<<replay.y<<"]}\n";
                found=true;break;
            }
        }
    }
    hits.close();
    std::ofstream result(argv[3]);if(!result)throw std::runtime_error("cannot open result");
    const char* status=found?"FOUND_PENDING_SAGE_REPLAY":
        memory_capped?"OOM":timed_out?"CENSORED_TIME":"CENSORED_PROBES";
    result<<"{\"status\":\""<<status<<"\",\"left_distinct_four_sums\":"
          <<left.size()<<",\"right_attempts\":"<<attempts
          <<",\"right_distinct_probes\":"<<probes
          <<",\"probe_cap\":"<<max_probes
          <<",\"group_hits\":"<<group_hits
          <<",\"column_rejects\":"<<column_rejects
          <<",\"found\":"<<(found?"true":"false")
          <<",\"build_ns\":"<<built-start
          <<",\"wall_ns\":"<<now_ns()-start
          <<",\"peak_rss_bytes\":"<<rss_bytes()<<"}\n";
    std::cout<<status<<" probes="<<probes<<" group_hits="<<group_hits
             <<" rss="<<rss_bytes()<<"\n";
  }catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}
}
