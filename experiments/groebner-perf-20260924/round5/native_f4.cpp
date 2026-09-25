// Sparse Boolean F4 with derivation DAGs. No 2^n monomial/root arrays.
// Degree-batched S-pairs, symbolic preprocessing and sparse Gaussian rows;
// implicit Boolean field pairs are installed alongside ordinary pairs.
// This is an experimental proof producer, not a new F6 algorithm.
#include <algorithm>
#include <chrono>
#include <charconv>
#include <cstdint>
#include <iostream>
#include <limits>
#include <map>
#include <queue>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

using Mask = uint64_t;
using Poly = std::vector<Mask>;
struct Budget : std::runtime_error { using std::runtime_error::runtime_error; };
struct Row { Poly terms; uint32_t proof; };
struct Node { unsigned op; uint32_t a; uint64_t b; };
struct Pair { unsigned degree; uint32_t i, j; Mask field; };
struct PairOrder {
    bool operator()(const Pair& a, const Pair& b) const {
        if (a.degree != b.degree) return a.degree > b.degree;
        if (a.i != b.i) return a.i > b.i;
        if (a.j != b.j) return a.j > b.j;
        return a.field > b.field;
    }
};
static bool less_monomial(Mask a, Mask b) {
    const auto da = __builtin_popcountll(a), db = __builtin_popcountll(b);
    return da != db ? da < db : a > b;
}
static Mask lead(const Poly& p) {
    return *std::max_element(p.begin(),p.end(),less_monomial);
}
static bool divides(Mask a, Mask b) { return (a & b) == a; }

class Engine {
public:
    uint64_t work = 0, max_work;
    uint32_t max_nodes, max_rows, batch_cap;
    bool record;
    uint64_t matrices = 0, matrix_rows = 0, peak_rows = 0, pairs = 0;
    std::vector<Node> nodes;
    std::vector<Row> basis;
    std::priority_queue<Pair,std::vector<Pair>,PairOrder> queue;
    Engine(uint64_t w,uint32_t p,uint32_t rows,uint32_t batch,bool proof)
        : max_work(w),max_nodes(p),max_rows(rows),batch_cap(batch),record(proof) {}
    void charge(uint64_t amount = 1) {
        if (amount > max_work - work) throw Budget("native work budget");
        work += amount;
    }
    uint32_t emit(unsigned op,uint32_t a,uint64_t b=0) {
        if (!record) return 0;
        if (nodes.size() >= max_nodes) throw Budget("native proof node budget");
        nodes.push_back({op,a,b});
        return uint32_t(nodes.size()-1);
    }
    Poly canonical(Poly terms) {
        charge(terms.size());
        std::sort(terms.begin(),terms.end());
        size_t out=0;
        for (size_t i=0;i<terms.size();) {
            size_t j=i+1;
            while (j<terms.size() && terms[j]==terms[i]) ++j;
            if ((j-i)&1) terms[out++]=terms[i];
            i=j;
        }
        terms.resize(out);
        return terms;
    }
    Row multiply(const Row& row,Mask mask) {
        if (!mask) return row;
        Poly out;
        out.reserve(row.terms.size());
        for (Mask term:row.terms) out.push_back(term|mask);
        return {canonical(std::move(out)),emit(1,row.proof,mask)};
    }
    Row add(const Row& a,const Row& b) {
        charge(a.terms.size()+b.terms.size());
        Poly out;
        out.reserve(a.terms.size()+b.terms.size());
        std::set_symmetric_difference(a.terms.begin(),a.terms.end(),b.terms.begin(),b.terms.end(),
                                      std::back_inserter(out));
        return {std::move(out),emit(2,a.proof,b.proof)};
    }
    Row normal(Row value,const std::vector<Row>& reducers,size_t skip=SIZE_MAX) {
        std::vector<Mask> leads;
        for (const auto& g:reducers) leads.push_back(lead(g.terms));
        std::vector<size_t> choices;
        for (size_t i=0;i<reducers.size();++i) if(i!=skip) choices.push_back(i);
        std::stable_sort(choices.begin(),choices.end(),[&](size_t a,size_t b){return reducers[a].terms.size()<reducers[b].terms.size();});
        // Reduce the greatest reducible term, including tails. Each step
        // updates the witness for the WHOLE polynomial, not just its head.
        while (!value.terms.empty()) {
            charge(value.terms.size());
            Poly order=value.terms;
            std::sort(order.begin(),order.end(),[](Mask a,Mask b){return less_monomial(b,a);});
            bool changed=false;
            for (Mask term:order) {
                for (size_t i:choices) {
                    charge();
                    if (!divides(leads[i],term)) continue;
                    value=add(value,multiply(reducers[i],term&~leads[i]));
                    changed=true;
                    break;
                }
                if (changed) break;
            }
            if (!changed) break;
        }
        return value;
    }
    void install(Row row) {
        const uint32_t index=uint32_t(basis.size());
        if (basis.size() >= max_rows) throw Budget("native basis row budget");
        const Mask lm=lead(row.terms);
        for (uint32_t i=0;i<index;++i) {
            charge();
            Mask other=lead(basis[i].terms);
            if (lm&other) queue.push({unsigned(__builtin_popcountll(lm|other)),index,i,0});
        }
        Mask bits=lm;
        while (bits) {
            Mask bit=bits&(~bits+1);
            bits^=bit;
            queue.push({unsigned(__builtin_popcountll(lm))+1,index,index,bit});
        }
        basis.push_back(std::move(row));
    }
    std::vector<Row> matrix(std::vector<Row> rows) {
        std::set<Mask> seen;
        std::vector<Mask> pending;
        auto register_row=[&](const Row& row) {
            charge(row.terms.size());
            for (Mask m:row.terms) if (seen.insert(m).second) pending.push_back(m);
        };
        for (const auto& row:rows) register_row(row);
        std::vector<Mask> leads;
        for (const auto& row:basis) leads.push_back(lead(row.terms));
        std::vector<size_t> choices;
        for (size_t i=0;i<basis.size();++i) choices.push_back(i);
        std::stable_sort(choices.begin(),choices.end(),[&](size_t a,size_t b){return basis[a].terms.size()<basis[b].terms.size();});
        while (!pending.empty()) {
            Mask monomial=pending.back();pending.pop_back();
            for (size_t i:choices) {
                charge();
                if (!divides(leads[i],monomial)) continue;
                if (rows.size()>=max_rows) throw Budget("native symbolic matrix row budget");
                Row shifted=multiply(basis[i],monomial&~leads[i]);
                register_row(shifted);
                rows.push_back(std::move(shifted));
                break;
            }
        }
        ++matrices;matrix_rows+=rows.size();peak_rows=std::max<uint64_t>(peak_rows,rows.size());
        // Sparse row echelon form: pivot monomials stand in for matrix columns.
        std::map<Mask,Row> pivots;
        for (auto& initial:rows) {
            Row row=std::move(initial);
            while (!row.terms.empty()) {
                charge(row.terms.size());
                Mask lm=lead(row.terms);
                auto it=pivots.find(lm);
                if (it==pivots.end()) {pivots.emplace(lm,std::move(row));break;}
                row=add(row,it->second);
            }
        }
        std::vector<Row> out;
        for (auto& pair:pivots) out.push_back(std::move(pair.second));
        std::sort(out.begin(),out.end(),[](const Row& a,const Row& b){return less_monomial(lead(a.terms),lead(b.terms));});
        return out;
    }
    bool unit() const {
        return std::any_of(basis.begin(),basis.end(),[](const Row& row){return row.terms==Poly{0};});
    }
    void compute(const std::vector<Poly>& input) {
        for (uint32_t i=0;i<input.size();++i) {
            Row row=normal({input[i],emit(0,i)},basis);
            if (!row.terms.empty()) install(std::move(row));
            if (unit()) break;
        }
        while (!queue.empty() && !unit()) {
            unsigned degree=queue.top().degree;
            std::vector<Row> batch;
            size_t taken=0;
            while (!queue.empty() && queue.top().degree==degree && taken<batch_cap) {
                Pair p=queue.top();queue.pop();++pairs;++taken;charge();
                Row row;
                if (p.field) row=multiply(basis[p.i],p.field);
                else {
                    Mask a=lead(basis[p.i].terms),b=lead(basis[p.j].terms),common=a|b;
                    row=add(multiply(basis[p.i],common&~a),multiply(basis[p.j],common&~b));
                }
                if (!row.terms.empty()) batch.push_back(std::move(row));
            }
            if (batch.empty()) continue;
            if (batch.size()>max_rows) throw Budget("native batch row budget");
            auto reduced=matrix(std::move(batch));
            for (auto& row:reduced) {
                size_t checkpoint=nodes.size();
                Row candidate=normal(std::move(row),basis);
                if (!candidate.terms.empty()) install(std::move(candidate));
                else nodes.resize(checkpoint);
                if (unit()) break;
            }
        }
        bool changed=true;
        while (changed) {
            changed=false;
            for (size_t i=0;i<basis.size();++i) {
                Row row=normal(basis[i],basis,i);
                if (row.terms==basis[i].terms) continue;
                if (row.terms.empty()) basis.erase(basis.begin()+i);
                else basis[i]=std::move(row);
                changed=true;break;
            }
        }
        std::sort(basis.begin(),basis.end(),[](const Row& a,const Row& b){return less_monomial(lead(b.terms),lead(a.terms));});
    }
    void compact() {
        if (!record) return;
        std::vector<uint8_t> used(nodes.size());
        std::vector<uint32_t> pending;
        for (const auto& row:basis) pending.push_back(row.proof);
        while (!pending.empty()) {
            uint32_t i=pending.back();pending.pop_back();
            if (used[i]) continue;
            used[i]=1;
            if (nodes[i].op) pending.push_back(nodes[i].a);
            if (nodes[i].op==2) pending.push_back(uint32_t(nodes[i].b));
        }
        std::vector<uint32_t> mapping(nodes.size());
        std::vector<Node> out;
        for (size_t i=0;i<nodes.size();++i) if (used[i]) {
            mapping[i]=uint32_t(out.size());
            Node node=nodes[i];
            if (node.op) node.a=mapping[node.a];
            if (node.op==2) node.b=mapping[node.b];
            out.push_back(node);
        }
        for (auto& row:basis) row.proof=mapping[row.proof];
        nodes.swap(out);
    }
};

static void print_success(unsigned n,const Engine& engine,double elapsed) {
    std::cout << "{\"status\":\"gb\",\"producer_seconds\":" << elapsed
              << ",\"stats\":{\"work\":" << engine.work << ",\"matrices\":" << engine.matrices
              << ",\"matrix_rows\":" << engine.matrix_rows << ",\"peak_rows\":" << engine.peak_rows
              << ",\"pairs\":" << engine.pairs << "},\"basis\":[";
    for (size_t i=0;i<engine.basis.size();++i) {
        if (i) std::cout << ',';
        std::cout << '[';
        const auto& terms=engine.basis[i].terms;
        for (size_t j=0;j<terms.size();++j) {if(j)std::cout<<',';std::cout<<terms[j];}
        std::cout << ']';
    }
    std::cout << "],\"proof\":";
    if (!engine.record) {std::cout<<"null}"<<'\n';return;}
    std::cout << "{\"version\":1,\"nvars\":" << n << ",\"order\":\"grevlex-x0-first\",\"nodes\":[";
    for (size_t i=0;i<engine.nodes.size();++i) {
        if (i) std::cout << ',';
        const auto& node=engine.nodes[i];
        std::cout << "[\"" << (node.op==0?"input":node.op==1?"mul":"xor") << "\"," << node.a;
        if (node.op) std::cout << ',' << node.b;
        std::cout << ']';
    }
    std::cout << "],\"outputs\":[";
    for (size_t i=0;i<engine.basis.size();++i) {if(i)std::cout<<',';std::cout<<engine.basis[i].proof;}
    std::cout << "]}}\n";
}

static bool read_unsigned(uint64_t& value) {
    std::string token;
    if (!(std::cin>>token) || token.empty()) return false;
    auto parsed=std::from_chars(token.data(),token.data()+token.size(),value);
    return parsed.ec==std::errc{} && parsed.ptr==token.data()+token.size();
}

int main() {
    std::ios::sync_with_stdio(false);
    uint64_t shape[7]{};
    for (auto& value:shape) if (!read_unsigned(value)) {
        std::cout << "{\"status\":\"invalid-input\"}\n";return 2;
    }
    if (shape[0]<1 || shape[0]>64 || shape[1]>4096 || !shape[3] || shape[3]>10000000 ||
        !shape[4] || shape[4]>1000000 || !shape[5] || shape[5]>shape[4] || shape[6]>1) {
        std::cout << "{\"status\":\"invalid-input\"}\n";return 2;
    }
    const unsigned n=shape[0],count=shape[1],max_nodes=shape[3],max_rows=shape[4],batch=shape[5],proof=shape[6];
    const uint64_t max_work=shape[2];
    Engine engine(max_work,max_nodes,max_rows,batch,proof!=0);
    try {
        std::vector<Poly> input;
        for (unsigned i=0;i<count;++i) {
            uint64_t terms;
            if (!read_unsigned(terms)) throw std::invalid_argument("term count");
            engine.charge(terms);
            Poly row;
            for (uint64_t j=0;j<terms;++j) {
                uint64_t mask;
                if (!read_unsigned(mask) || (n<64 && mask>>n)) throw std::invalid_argument("monomial mask");
                row.push_back(mask);
            }
            input.push_back(engine.canonical(std::move(row)));
        }
        std::string extra;
        if (std::cin>>extra) throw std::invalid_argument("trailing input");
        auto start=std::chrono::steady_clock::now();
        engine.compute(input);
        engine.compact();
        auto elapsed=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
        print_success(n,engine,elapsed);
    } catch (const Budget& e) {
        std::cout << "{\"status\":\"inconclusive\",\"reason\":\"" << e.what()
                  << "\",\"work\":" << engine.work << ",\"proof_nodes\":" << engine.nodes.size() << "}\n";
        return 3;
    } catch (const std::invalid_argument&) {
        std::cout << "{\"status\":\"invalid-input\"}\n";return 2;
    } catch (const std::exception&) {
        std::cout << "{\"status\":\"internal-error\"}\n";return 4;
    }
}
