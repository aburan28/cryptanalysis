"""Add last-use reclamation without sharing arithmetic with the producer."""
import importlib.util
from pathlib import Path

HERE=Path(__file__).resolve().parent

def source():
    spec=importlib.util.spec_from_file_location('schedule93_for94',HERE.parent/'round93/generate.py')
    old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    text=old.source()
    def change(a,b):
        nonlocal text
        assert text.count(a)==1,a[:100]
        text=text.replace(a,b)
    change('#include <vector>','#include <vector>\n#include <algorithm>\n#include <limits>')
    change('namespace {','''struct LiveStats {
    uint64_t planning_work, metadata_bytes, live_terms, peak_terms;
    uint64_t released_terms, released_nodes;
};
namespace {''')
    change('uint64_t max_work,max_terms;', 'uint64_t max_work,max_terms;\n    uint32_t policy;\n    LiveStats& live;')
    change('Checker(uint32_t n,uint64_t work,uint64_t terms,CheckStats& s)\n        :variables(n),max_work(work),max_terms(terms),stats(s){}',
        'Checker(uint32_t n,uint64_t work,uint64_t terms,uint32_t p,LiveStats& l,CheckStats& s)\n        :variables(n),max_work(work),max_terms(terms),policy(p),live(l),stats(s){}')
    change('charge(proof.nodes);values.reserve(proof.nodes);','''// A retained value lives through every operand use and every output check.
        // Unused nodes are still evaluated and validated; only their storage dies.
        std::vector<uint32_t> uses;
        if(policy) {
            charge(proof.nodes+proof.rows);
            live.planning_work=proof.nodes+proof.rows;
            uses.assign(proof.nodes,0);
            live.metadata_bytes=proof.nodes*sizeof(uint32_t);
            for(uint64_t i=0;i<proof.nodes;++i) {
                const auto& node=proof.graph[i];
                if(node.op==0) {
                    if(node.a>=originals.size()||node.b)throw Rejected("invalid input reference");
                } else if(node.op==1) {
                    if(node.a>=i)throw Rejected("forward multiplication reference");
                    valid_mask(node.b);++uses[node.a];
                } else if(node.op==2) {
                    if(node.a>=i||node.b>=i)throw Rejected("forward XOR reference");
                    ++uses[node.a];++uses[node.b];
                } else throw Rejected("unsupported proof operation");
            }
            for(uint64_t i=0;i<proof.rows;++i) {
                if(proof.outputs[i]>=proof.nodes)throw Rejected("output reference outside graph");
                ++uses[proof.outputs[i]];
            }
        }
        // Shape bounds cap all uses at 2*10,000,000+1,000,000 < UINT32_MAX.
        auto reclaim = [&](size_t i) {
            const uint64_t terms=values[i].size();
            live.live_terms-=terms;
            live.released_terms+=terms;++live.released_nodes;
            Polynomial{}.swap(values[i]);
        };
        auto consume = [&](size_t i) {
            if(!uses[i])throw Rejected("inconsistent proof use count");
            if(--uses[i]==0)reclaim(i);
        };
        charge(proof.nodes);values.reserve(proof.nodes);''')
    change('''            if(value.size()>max_terms-stats.retained_terms)throw Exhausted("proof retention budget");
            stats.retained_terms+=value.size();values.push_back(std::move(value));++stats.proof_nodes;''','''            const uint64_t terms=value.size();
            if(terms>std::numeric_limits<uint64_t>::max()-live.live_terms)
                throw Exhausted("live proof counter overflow");
            live.peak_terms=std::max(live.peak_terms,live.live_terms+terms);
            if(policy==2) {
                if(terms>max_terms-live.live_terms)throw Exhausted("live proof retention budget");
            } else if(terms>max_terms-stats.retained_terms)throw Exhausted("proof retention budget");
            if(terms>std::numeric_limits<uint64_t>::max()-stats.retained_terms)
                throw Exhausted("cumulative proof counter overflow");
            stats.retained_terms+=terms;live.live_terms+=terms;
            values.push_back(std::move(value));++stats.proof_nodes;
            if(policy) {
                if(node.op==1)consume(node.a);
                if(node.op==2){consume(node.a);consume(node.b);}
                if(!uses[i])reclaim(i);
            }''')
    change('''                throw Rejected("basis row is not its witnessed input combination");
        }''','''                throw Rejected("basis row is not its witnessed input combination");
            if(policy)consume(proof.outputs[i]);
        }''')
    change('''int check_packed_ordered(const PackedInput* input,const ProofView* proof,uint64_t max_work,
                 uint64_t max_retained_terms,uint32_t schedule,CheckStats* stats)''','''uint64_t liveness_stats_size(){return sizeof(LiveStats);}
int check_packed_live(const PackedInput* input,const ProofView* proof,uint64_t max_work,
                 uint64_t max_retained_terms,uint32_t schedule,uint32_t policy,
                 CheckStats* stats,LiveStats* live)''')
    change('if(!stats){failure="null checker stats";return 1;}', 'if(!stats||!live){failure="null checker stats";return 1;}\n    *live=LiveStats{};')
    change('if(schedule>1||!input', 'if(policy>2||schedule>1||!input')
    change('Checker checker(input->nvars,max_work,max_retained_terms,*stats);','Checker checker(input->nvars,max_work,max_retained_terms,policy,*live,*stats);')
    return text

if __name__=='__main__':print(source())
