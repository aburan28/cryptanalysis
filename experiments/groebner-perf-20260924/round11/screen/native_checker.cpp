// Independent exact checker. Deliberately does not include the producer.
// Hash-set parity arithmetic is independent of its sorted-vector arithmetic.
#include "proof_abi.h"
#include <chrono>
#include <stdexcept>
#include <string>
#include <unordered_set>
#include <vector>

namespace {
using Polynomial=std::unordered_set<uint64_t>;
using Clock=std::chrono::steady_clock;
double seconds(Clock::time_point start) {
    return std::chrono::duration<double>(Clock::now()-start).count();
}
struct Rejected:std::runtime_error{using std::runtime_error::runtime_error;};
struct Exhausted:std::runtime_error{using std::runtime_error::runtime_error;};
thread_local std::string failure;
class Checker {
    uint32_t variables;
    uint64_t max_work,max_terms;
public:
    CheckStats& stats;
    Checker(uint32_t n,uint64_t work,uint64_t terms,CheckStats& s)
        :variables(n),max_work(work),max_terms(terms),stats(s){}
    void charge(uint64_t amount=1) {
        if(amount>max_work-stats.work)throw Exhausted("operation budget");
        stats.work+=amount;
    }
    void valid_mask(uint64_t mask)const {
        if(variables<64 && mask>>variables)throw Rejected("monomial outside the declared ring");
    }
    static void toggle(Polynomial& p,uint64_t term) {
        auto inserted=p.insert(term);
        if(!inserted.second)p.erase(inserted.first);
    }
    uint64_t leading(const Polynomial& p) {
        charge(p.size());
        if(p.empty())throw Rejected("leading term requested for zero");
        uint64_t best=*p.begin();int degree=__builtin_popcountll(best);
        for(uint64_t term:p) {
            int next=__builtin_popcountll(term);
            if(next>degree||(next==degree&&term<best)){best=term;degree=next;}
        }
        return best;
    }
    Polynomial multiply(const Polynomial& p,uint64_t monomial) {
        charge(p.size());Polynomial result;
        for(uint64_t term:p)toggle(result,term|monomial);
        return result;
    }
    Polynomial add(const Polynomial& left,const Polynomial& right) {
        charge(left.size()+right.size());Polynomial result=left;
        for(uint64_t term:right)toggle(result,term);
        return result;
    }
    Polynomial remainder(Polynomial value,const std::vector<Polynomial>& reducers,
                         const std::vector<uint64_t>& leads) {
        Polynomial tail;
        while(!value.empty()) {
            uint64_t lm=leading(value);bool reduced=false;
            for(size_t i=0;i<reducers.size();++i) {
                charge();
                if((lm&leads[i])!=leads[i])continue;
                auto product=multiply(reducers[i],lm&~leads[i]);
                if(product.empty()||leading(product)!=lm)throw Rejected("nondecreasing reduction");
                value=add(value,product);++stats.reduction_steps;reduced=true;break;
            }
            if(!reduced){tail.insert(lm);value.erase(lm);}
        }
        return tail;
    }
    void verify(const PackedInput& input,const ProofView& proof) {
        auto phase=Clock::now();
        if(proof.version!=1||proof.nvars!=variables||proof.order!=1||proof.reserved)
            throw Rejected("proof ring/version/order mismatch");
        if(proof.rows>1000000||proof.nodes>10000000||proof.terms>UINT32_MAX||
           !proof.offsets||(proof.terms&&!proof.basis_terms)||
           (proof.nodes&&!proof.graph)||(proof.rows&&!proof.outputs))
            throw Rejected("invalid proof buffers or shape");
        if(proof.offsets[0]!=0||proof.offsets[proof.rows]!=proof.terms)
            throw Rejected("invalid basis offsets");
        charge(input.equations+proof.rows);
        std::vector<Polynomial> originals(input.equations),basis;
        uint32_t limbs=(input.equations+63)/64;
        // Decode the ORIGINAL packed bytes independently of the producer.
        for(uint64_t i=0;i<input.terms;++i) {
            valid_mask(input.masks[i]);charge(limbs);
            for(uint32_t limb=0;limb<limbs;++limb) {
                uint64_t coefficient=input.coefficients[i*limbs+limb];
                if(limb+1==limbs && input.equations%64 && coefficient>>(input.equations%64))
                    throw Rejected("coefficient outside the equation bitset");
                // Different decoder traversal from the producer's ctz loop.
                for(unsigned bit=0;coefficient;++bit,coefficient>>=1)if(coefficient&1) {
                    charge();toggle(originals[limb*64+bit],input.masks[i]);
                }
            }
        }
        basis.reserve(proof.rows);
        for(uint64_t i=0;i<proof.rows;++i) {
            uint64_t begin=proof.offsets[i],end=proof.offsets[i+1];
            if(begin>=end||end>proof.terms)throw Rejected("zero row or invalid basis offsets");
            charge(end-begin);Polynomial row;
            for(uint64_t j=begin;j<end;++j) {
                valid_mask(proof.basis_terms[j]);
                if(!row.insert(proof.basis_terms[j]).second)throw Rejected("duplicate basis term");
            }
            basis.push_back(std::move(row));
        }
        stats.decode_seconds=seconds(phase);phase=Clock::now();
        charge(proof.nodes);std::vector<Polynomial> values;values.reserve(proof.nodes);
        for(uint64_t i=0;i<proof.nodes;++i) {
            const ProofNode& node=proof.graph[i];Polynomial value;
            if(node.op==0) {
                if(node.a>=originals.size()||node.b)throw Rejected("invalid input reference");
                value=originals[node.a];
            }else if(node.op==1) {
                if(node.a>=i)throw Rejected("forward multiplication reference");
                valid_mask(node.b);value=multiply(values[node.a],node.b);
            }else if(node.op==2) {
                if(node.a>=i||node.b>=i)throw Rejected("forward XOR reference");
                value=add(values[node.a],values[node.b]);
            }else throw Rejected("unsupported proof operation");
            if(value.size()>max_terms-stats.retained_terms)throw Exhausted("proof retention budget");
            stats.retained_terms+=value.size();values.push_back(std::move(value));++stats.proof_nodes;
        }
        for(size_t i=0;i<basis.size();++i) {
            if(proof.outputs[i]>=values.size()||values[proof.outputs[i]]!=basis[i])
                throw Rejected("basis row is not its witnessed input combination");
        }
        stats.derivation_seconds=seconds(phase);phase=Clock::now();
        std::vector<uint64_t> leads;leads.reserve(basis.size());
        for(const auto& row:basis)leads.push_back(leading(row));
        // Reverse inclusion: every original generator must lie in <basis>.
        for(const auto& row:originals) {
            ++stats.generator_checks;
            if(!remainder(row,basis,leads).empty())throw Rejected("input generator has nonzero normal form");
        }
        stats.membership_seconds=seconds(phase);phase=Clock::now();
        for(size_t i=0;i<basis.size();++i)for(size_t j=0;j<leads.size();++j)if(i!=j) {
            charge(basis[i].size());
            for(uint64_t term:basis[i])if((term&leads[j])==leads[j])
                throw Rejected("basis is not reduced/minimal");
        }
        stats.reducedness_seconds=seconds(phase);phase=Clock::now();
        // Ordinary-ring Buchberger criterion with explicit implicit-field pairs.
        // For x_i | LM(g), S(g,x_i^2+x_i) modulo the field ideal is x_i*g.
        // Coprime basis/basis and basis/field leads use the product criterion.
        for(size_t i=0;i<basis.size();++i) {
            for(unsigned bit=0;bit<variables;++bit)if(leads[i]&(UINT64_C(1)<<bit)) {
                ++stats.field_pairs;
                if(!remainder(multiply(basis[i],UINT64_C(1)<<bit),basis,leads).empty())
                    throw Rejected("implicit Boolean field pair has nonzero normal form");
            }
            for(size_t j=i+1;j<basis.size();++j) {
                ++stats.basis_pairs;charge();
                if(!(leads[i]&leads[j])){++stats.product_pairs_skipped;continue;}
                uint64_t common=leads[i]|leads[j];
                auto pair=add(multiply(basis[i],common&~leads[i]),multiply(basis[j],common&~leads[j]));
                if(!remainder(pair,basis,leads).empty())throw Rejected("basis critical pair has nonzero normal form");
            }
        }
        stats.completion_seconds=seconds(phase);
    }
};
}

extern "C" {
const char* checker_error(){return failure.c_str();}
int check_packed(const PackedInput* input,const ProofView* proof,uint64_t max_work,
                 uint64_t max_retained_terms,CheckStats* stats) {
    auto start=Clock::now();failure.clear();
    if(!stats){failure="null checker stats";return 1;}
    *stats=CheckStats{};int code=0;
    try {
        if(!input||!proof||input->nvars<1||input->nvars>64||input->equations>4096||
           (!input->equations&&input->terms)||input->terms>UINT32_MAX||
           (input->terms&&(!input->masks||!input->coefficients)))
            throw Rejected("invalid packed checker configuration");
        Checker checker(input->nvars,max_work,max_retained_terms,*stats);
        checker.verify(*input,*proof);
    }catch(const Rejected& e){code=1;failure=e.what();}
    catch(const Exhausted& e){code=2;failure=e.what();}
    catch(const std::exception& e){code=3;failure=e.what();}
    catch(...){code=3;failure="unknown checker failure";}
    stats->total_seconds=seconds(start);return code;
}
}
