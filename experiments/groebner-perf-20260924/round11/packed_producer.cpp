#include "proof_abi.h"
#include <memory>
#include <type_traits>
// build.py extracts the unchanged Engine before its CLI adapter. The original
// round-five source and its historical evidence remain byte-identical.
#include "build/native_engine.inc"

namespace {
using Clock=std::chrono::steady_clock;
double seconds(Clock::time_point start) {
    return std::chrono::duration<double>(Clock::now()-start).count();
}
thread_local std::string failure;
struct Result {
    std::vector<uint64_t> terms,offsets;
    std::vector<ProofNode> graph;
    std::vector<uint32_t> outputs;
    ProofView view{};
};
}

extern "C" {
const char* producer_error(){return failure.c_str();}
void* produce_packed(const PackedInput* input,uint64_t max_work,uint32_t max_nodes,
                     uint32_t max_rows,uint32_t batch,ProducerStats* stats) {
    auto start=Clock::now();failure.clear();
    if(!stats){failure="null producer stats";return nullptr;}
    *stats=ProducerStats{};
    std::unique_ptr<Engine> engine;
    auto phase=start;
    unsigned phase_index=0;
    try {
        if(!input||input->nvars<1||input->nvars>64||input->equations>4096||
           (!input->equations&&input->terms)||input->terms>UINT32_MAX||
           (input->terms&&(!input->masks||!input->coefficients))||
           !max_nodes||max_nodes>10000000||!max_rows||max_rows>1000000||!batch||batch>max_rows)
            throw std::invalid_argument("invalid packed producer configuration");
        engine=std::make_unique<Engine>(max_work,max_nodes,max_rows,batch,true);
        std::vector<Poly> rows(input->equations);
        uint32_t limbs=(input->equations+63)/64;
        for(uint64_t i=0;i<input->terms;++i) {
            if(input->nvars<64 && input->masks[i]>>input->nvars)
                throw std::invalid_argument("monomial outside the ring");
            engine->charge(limbs);
            for(uint32_t limb=0;limb<limbs;++limb) {
                uint64_t bits=input->coefficients[i*limbs+limb];
                if(limb+1==limbs && input->equations%64 && bits>>(input->equations%64))
                    throw std::invalid_argument("coefficient outside the equation bitset");
                while(bits) {
                    unsigned j=__builtin_ctzll(bits);bits&=bits-1;
                    engine->charge();rows[limb*64+j].push_back(input->masks[i]);
                }
            }
        }
        for(auto& row:rows)row=engine->canonical(std::move(row));
        stats->decode_seconds=seconds(start);phase=Clock::now();phase_index=1;
        engine->compute(rows);engine->compact();
        stats->produce_seconds=seconds(phase);phase=Clock::now();phase_index=2;
        auto result=std::make_unique<Result>();
        result->offsets.push_back(0);
        for(const auto& row:engine->basis) {
            result->terms.insert(result->terms.end(),row.terms.begin(),row.terms.end());
            result->offsets.push_back(result->terms.size());result->outputs.push_back(row.proof);
        }
        result->graph.reserve(engine->nodes.size());
        for(const auto& node:engine->nodes)result->graph.push_back({node.op,node.a,node.b});
        result->view={1,input->nvars,1,0,engine->basis.size(),result->terms.size(),result->graph.size(),
            result->terms.data(),result->offsets.data(),result->graph.data(),result->outputs.data()};
        stats->work=engine->work;stats->matrices=engine->matrices;stats->matrix_rows=engine->matrix_rows;
        stats->peak_rows=engine->peak_rows;stats->pairs=engine->pairs;stats->nodes=engine->nodes.size();
        stats->export_seconds=seconds(phase);stats->total_seconds=seconds(start);
        return result.release();
    }catch(const Budget& e){stats->status=2;failure=e.what();}
    catch(const std::invalid_argument& e){stats->status=1;failure=e.what();}
    catch(const std::exception& e){stats->status=3;failure=e.what();}
    catch(...){stats->status=3;failure="unknown native producer failure";}
    // Keep partial work and exclusive elapsed phases when a budget stops the
    // attempt. An unfinished phase is not a zero-cost phase.
    if(phase_index==0)stats->decode_seconds=seconds(phase);
    else if(phase_index==1)stats->produce_seconds=seconds(phase);
    else stats->export_seconds=seconds(phase);
    if(engine){
        stats->work=engine->work;stats->nodes=engine->nodes.size();
        stats->matrices=engine->matrices;stats->matrix_rows=engine->matrix_rows;
        stats->peak_rows=engine->peak_rows;stats->pairs=engine->pairs;
    }
    stats->total_seconds=seconds(start);return nullptr;
}
const ProofView* producer_view(void* handle) {
    return handle?&static_cast<Result*>(handle)->view:nullptr;
}
void producer_destroy(void* handle){delete static_cast<Result*>(handle);}
}
