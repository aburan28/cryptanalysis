// Check the cache through insertion, interreduction, ordering and exhaustion.
#include "build/cached.inc"
#include <cassert>

static void check(const Engine& engine) {
    assert(engine.basis.size()==engine.basis_leads.size());
    for (size_t i=0;i<engine.basis.size();++i) {
        assert(!engine.basis[i].terms.empty());
        assert(engine.basis_leads[i]==lead(engine.basis[i].terms));
    }
}

int main() {
    uint64_t states=0;
    std::vector<std::vector<Poly>> systems={
        {},{{0}},{{0,3}},{{0,3},{0,1}},{{3,4},{0,4}},
        {{3,8},{3,4},{0,2}},{{0,3},{0,12},{0,48}},
        {{0,Mask(1)<<63},{3,4},{0,3}}
    };
    uint64_t state=0x753918dd20da71b7ULL;
    auto random=[&]() { state^=state<<13;state^=state>>7;state^=state<<17;return state; };
    for (unsigned k=0;k<64;++k) {
        std::vector<Poly> equations;
        for (unsigned row=0;row<5;++row) {
            Poly terms;
            for (unsigned j=0;j<8;++j) terms.push_back(random()%64);
            equations.push_back(std::move(terms));
        }
        systems.push_back(std::move(equations));
    }
    for (const auto& input : systems) {
        for (uint64_t budget : {uint64_t(0),uint64_t(50),uint64_t(500),uint64_t(2000000)}) {
            Engine engine(budget,100000,4096,64,false);
            try {
                std::vector<Poly> canonical;
                for (const auto& row : input) canonical.push_back(engine.canonical(row));
                engine.compute(canonical);
                engine.compact();
            } catch (const Budget&) {}
            check(engine);
            ++states;
        }
    }
    Engine installed(2000000,100000,4096,64,false);
    for (const Poly& row : std::vector<Poly>{{0,3},{0,1},{0,Mask(1)<<63}}) {
        installed.install({row,0});
        check(installed);
        ++states;
    }
    installed.compute({});
    check(installed);
    ++states;
    std::cout << "{\"cache_states\":" << states << "}\n";
}
