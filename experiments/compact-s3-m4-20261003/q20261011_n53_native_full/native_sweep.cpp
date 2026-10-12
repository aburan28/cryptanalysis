// Q1455: complete N53 quotient-pair prefix sweep on one frozen public target.
// Input files are exported and hashed by export.py. Native matches are
// independently expanded, group-checked, and ranked by verify.py.
#include "../q20261011_n53_native_pair/native_field53.hpp"
#include <array>
#include <chrono>
#include <fstream>
#include <iomanip>
#include <sys/resource.h>
#include <unordered_map>
#include <vector>

using Clock = std::chrono::steady_clock;
using Pair = std::array<uint16_t, 2>;
using Ns = std::chrono::nanoseconds;
uint64_t elapsed(Clock::time_point a, Clock::time_point b) {
    return uint64_t(std::chrono::duration_cast<Ns>(b - a).count());
}
U read_u128(std::ifstream &input) {
    char bytes[16];
    input.read(bytes, 16);
    if (!input) throw std::runtime_error("short point file");
    U value = 0;
    for (unsigned i = 0; i < 16; ++i) value |= U(uint8_t(bytes[i])) << (8*i);
    return value;
}
std::vector<P> read_points(const std::string &path, size_t count) {
    std::ifstream input(path, std::ios::binary);
    if (!input) throw std::runtime_error("cannot open points " + path);
    std::vector<P> result;
    result.reserve(count);
    for (size_t i = 0; i < count; ++i) {
        P point{read_u128(input), read_u128(input), false};
        if ((point.x & 1) || (point.y & 1) ||
            (point.x & ~MASK) || (point.y & ~MASK))
            throw std::runtime_error("noncanonical point");
        result.push_back(point);
    }
    if (input.peek() != EOF) throw std::runtime_error("extra point data");
    return result;
}
std::vector<uint16_t> read_u16s(const std::string &path, size_t count) {
    std::ifstream input(path, std::ios::binary);
    if (!input) throw std::runtime_error("cannot open indices " + path);
    std::vector<uint16_t> out(count);
    for (size_t i = 0; i < count; ++i) {
        char bytes[2]; input.read(bytes, 2);
        if (!input) throw std::runtime_error("short index file");
        out[i] = uint16_t(uint8_t(bytes[0])) | (uint16_t(uint8_t(bytes[1])) << 8);
    }
    if (input.peek() != EOF) throw std::runtime_error("extra index data");
    return out;
}
std::vector<Pair> read_pairs(const std::string &path, size_t count) {
    auto raw = read_u16s(path, 2 * count);
    std::vector<Pair> pairs;
    pairs.reserve(count);
    for (size_t i = 0; i < count; ++i) pairs.push_back({raw[2*i], raw[2*i+1]});
    return pairs;
}
struct UHash {
    size_t operator()(U x) const {
        uint64_t a = uint64_t(x), b = uint64_t(x >> 64);
        a ^= b + 0x9e3779b97f4a7c15ull + (a << 6) + (a >> 2);
        a ^= a >> 30; a *= 0xbf58476d1ce4e5b9ull;
        a ^= a >> 27; a *= 0x94d049bb133111ebull;
        return size_t(a ^ (a >> 31));
    }
};
struct Desc {
    uint32_t ordinal;
    uint16_t first, second;
    uint8_t exponent;
    int8_t sign;
};
struct Match {
    uint32_t query, ordinal;
    uint16_t tfirst, tsecond, qfirst, qsecond;
    uint8_t texp, qexp;
    int8_t tsign, qsign;
};

int main(int argc, char **argv) {
    try {
        if (argc != 9) throw std::runtime_error(
            "usage: native_sweep INPUT_DIR TARGET_X_HEX TARGET_Y_HEX B K QUERIES TABLE_STATES WALL_SECONDS");
        auto started = Clock::now();
        std::string dir = argv[1];
        P target{readhex(argv[2]), readhex(argv[3]), false};
        size_t B = std::stoull(argv[4]), K = std::stoull(argv[5]);
        size_t query_cap = std::stoull(argv[6]), table_cap = std::stoull(argv[7]);
        uint64_t wall_cap_ns = uint64_t(std::stoull(argv[8])) * 1000000000ull;
        if (B != 24062 || K != 227 || query_cap != 1500000 ||
            table_cap != 2743068 || wall_cap_ns != 1200000000000ull)
            throw std::runtime_error("unexpected frozen parameters");
        auto base = read_points(dir + "/base.bin", B);
        auto reps = read_points(dir + "/representatives.bin", K);
        auto rep_indices = read_u16s(dir + "/representative_indices.bin", K);
        auto lifts = read_u16s(dir + "/lift_indices.bin", K * M * 2);
        auto blocks = read_pairs(dir + "/blocks.bin", K * (K + 1) / 2);
        auto queries = read_pairs(dir + "/queries.bin", query_cap);
        for (size_t i = 0; i < K; ++i) {
            if (rep_indices[i] >= B || base[rep_indices[i]].x != reps[i].x ||
                base[rep_indices[i]].y != reps[i].y)
                throw std::runtime_error("representative index mismatch");
        }
        if (mul(ONE, ONE) != ONE || mul(target.x, inv(target.x)) != ONE)
            throw std::runtime_error("field self-test failed");
        auto loaded = Clock::now();
        std::unordered_map<U, std::vector<Desc>, UHash> table;
        table.reserve(table_cap * 11 / 10);
        uint64_t repeats=0, identities=0, states=0;
        std::array<uint64_t, 3> prefix_keys{}, prefix_repeats{}, prefix_identities{};
        const std::array<uint64_t, 3> caps{2000000,2500000,2743068};
        std::string status = "completed_query_cap";
        auto table_started = Clock::now();
        for (const Pair &block : blocks) {
            unsigned i=block[0], j=block[1];
            if (i >= K || j >= K || i > j) throw std::runtime_error("bad block");
            uint16_t first_idx=rep_indices[i];
            for (unsigned k=0;k<M;++k) {
                for(unsigned sign=0;sign<2;++sign) {
                uint16_t second_idx=lifts[(j*M+k)*2+sign];
                if (second_idx >= B) throw std::runtime_error("bad lift index");
                ++states;
                P sum=add(base[first_idx],base[second_idx]);
                if (sum.inf) ++identities;
                else {
                    Key key=canonical(sum);
                    auto &items=table[key.value];
                    repeats += !items.empty();
                    items.push_back({uint32_t(states), first_idx, second_idx,
                                     uint8_t(key.exponent), int8_t(key.sign)});
                }
                for(size_t h=0;h<caps.size();++h) if(states==caps[h]) {
                    prefix_keys[h]=table.size();
                    prefix_repeats[h]=repeats;
                    prefix_identities[h]=identities;
                }
                if (states >= table_cap) break;
                if ((states & 4095) == 0 && elapsed(started,Clock::now()) >= wall_cap_ns) {
                    status="wall_cap_during_table";
                    break;
                }
                }
                if (states >= table_cap || status != "completed_query_cap") break;
            }
            if (states >= table_cap || status != "completed_query_cap") break;
        }
        auto table_ended = Clock::now();
        if (table.size()+repeats+identities!=states)
            throw std::runtime_error("table accounting mismatch");
        std::array<uint64_t,3> matched_positions{}, candidate_descriptors{};
        uint64_t query_processed=0, query_identities=0;
        std::vector<Match> matches;
        auto query_started=Clock::now();
        if(status=="completed_query_cap") for(size_t pos=0;pos<query_cap;++pos) {
            if ((pos & 4095)==0 && elapsed(started,Clock::now()) >= wall_cap_ns) {
                status="wall_cap_during_queries"; break;
            }
            ++query_processed;
            const Pair query=queries[pos];
            if(query[0]>=B||query[1]>=B)throw std::runtime_error("bad query index");
            P sum=add(base[query[0]],base[query[1]]);
            if(sum.inf){++query_identities;continue;}
            P complement=add(target,neg(sum));
            if(complement.inf)continue;
            Key qkey=canonical(complement);
            auto it=table.find(qkey.value);
            if(it==table.end())continue;
            std::array<bool,3> present{};
            for(const Desc &desc:it->second){
                for(size_t h=0;h<caps.size();++h) if(desc.ordinal<=caps[h]) {
                    present[h]=true; ++candidate_descriptors[h];
                }
                matches.push_back({uint32_t(pos+1),desc.ordinal,desc.first,desc.second,
                                   query[0],query[1],desc.exponent,
                                   uint8_t(qkey.exponent),desc.sign,int8_t(qkey.sign)});
            }
            for(size_t h=0;h<caps.size();++h)matched_positions[h]+=present[h];
        }
        auto finished=Clock::now();
        struct rusage usage{};
        getrusage(RUSAGE_SELF, &usage);
        uint64_t peak_rss_bytes = uint64_t(usage.ru_maxrss);
        std::cout<<"{\"status\":\""<<status<<"\",\"table_states_generated\":"<<states
                 <<",\"table_distinct_keys\":"<<table.size()
                 <<",\"table_same_key_repeats\":"<<repeats
                 <<",\"table_skipped_identity_pairs\":"<<identities
                 <<",\"query_samples_processed\":"<<query_processed
                 <<",\"query_skipped_identity_pairs\":"<<query_identities
                 <<",\"peak_table_keys\":"<<table.size()
                 <<",\"peak_rss_bytes\":"<<peak_rss_bytes
                 <<",\"phase_wall_ns\":{\"input_load\":"<<elapsed(started,loaded)
                 <<",\"table_allocation\":"<<elapsed(loaded,table_started)
                 <<",\"table_build\":"<<elapsed(table_started,table_ended)
                 <<",\"target_query_and_lookup\":"<<elapsed(query_started,finished)
                 <<"},\"prefix_table\":{\n";
        for(size_t h=0;h<caps.size();++h){
            if(h)std::cout<<",";
            std::cout<<"\""<<caps[h]<<"\":{\"distinct_keys\":"<<prefix_keys[h]
                     <<",\"same_key_repeats\":"<<prefix_repeats[h]
                     <<",\"identity_pairs\":"<<prefix_identities[h]<<"}";
        }
        std::cout<<"},\"cap_query\":{\n";
        for(size_t h=0;h<caps.size();++h){
            if(h)std::cout<<",";
            std::cout<<"\""<<caps[h]<<"\":{\"matched_positions\":"<<matched_positions[h]
                     <<",\"candidate_descriptors\":"<<candidate_descriptors[h]<<"}";
        }
        std::cout<<"},\"matches\":[";
        for(size_t i=0;i<matches.size();++i){
            if(i)std::cout<<",";
            const auto &m=matches[i];
            std::cout<<"["<<m.query<<","<<m.ordinal<<","<<m.tfirst<<","<<m.tsecond
                     <<","<<m.qfirst<<","<<m.qsecond<<","<<unsigned(m.texp)
                     <<","<<unsigned(m.qexp)<<","<<int(m.tsign)<<","<<int(m.qsign)<<"]";
        }
        std::cout<<"]}\n";
        return 0;
    } catch(const std::exception &e){std::cerr<<"ERROR "<<e.what()<<"\n";return 1;}
}
