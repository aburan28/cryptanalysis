#include <cassert>
#include <iostream>
#include "build/checked.inc"

static Engine make(bool constant) {
    chain_stats={}; chain_stats.mode=CHECKED_CHAIN_MODE;
    Engine e(100000,100000,64,64,true);
    for (Mask lm: {Mask(7),Mask(25),Mask(11)}) {
        Poly row{lm}; if (constant) row.push_back(0);
        auto terms=e.canonical(std::move(row));
        const uint32_t id=e.emit(0,uint32_t(e.basis.size()));
        e.install({std::move(terms),id});
    }
    return e;
}
int main() {
    const Pair parent{5,1,0,0};
    {
        auto e=make(false); const size_t nodes=e.nodes.size();
        assert(e.chain_prune(parent));
        assert(chain_stats.pruned_pairs==1 && chain_stats.probe_zero==2);
        assert(e.nodes.size()==nodes && e.max_work==100000);
        assert(chain_stats.represented_entries<=CHAIN_CACHE_LIMIT);
    }
    {
        auto e=make(true); const size_t nodes=e.nodes.size();
        assert(!e.chain_prune(parent));
        assert(chain_stats.probe_zero==0);
        assert(chain_stats.probe_nonzero+chain_stats.probe_soft_limits==1);
        const auto probes=chain_stats.probes;
        assert(!e.chain_prune(parent));
        assert(chain_stats.probes==probes && chain_stats.failed_probe_hits>0);
        assert(e.nodes.size()==nodes && e.max_work==100000);
        if (CHAIN_PROBE_WORK>100) {
            e.install({Poly{0},e.emit(0,3)});
            assert(e.chain_prune(parent));
            assert(chain_stats.probes>probes);
        }
    }
    uint64_t work_boundaries=0,node_boundaries=0,aborted=0,soft=0;
    for (uint64_t remaining=0;remaining<=64;++remaining) {
        auto e=make(true); const size_t nodes=e.nodes.size();
        e.max_work=UINT64_MAX; e.work=UINT64_MAX-remaining;
        unsigned attempts=0;
        try { (void)e.chain_known_or_probe(0,2,attempts); }
        catch (const Budget &) {}
        assert(e.max_work==UINT64_MAX && e.work<=UINT64_MAX);
        assert(e.nodes.size()==nodes);
        assert(chain_stats.probe_zero+chain_stats.probe_nonzero+
               chain_stats.probe_soft_limits+chain_stats.probe_aborted==chain_stats.probes);
        aborted+=chain_stats.probe_aborted; soft+=chain_stats.probe_soft_limits;
        ++work_boundaries;
    }
    for (uint32_t extra=0;extra<=8;++extra) {
        auto e=make(true); const size_t nodes=e.nodes.size();
        e.max_nodes=uint32_t(nodes)+extra;
        unsigned attempts=0;
        try { (void)e.chain_known_or_probe(0,2,attempts); }
        catch (const Budget &) {}
        assert(e.max_work==100000 && e.nodes.size()==nodes);
        aborted+=chain_stats.probe_aborted; soft+=chain_stats.probe_soft_limits;
        ++node_boundaries;
    }
    assert(aborted>0);
    if (CHAIN_PROBE_WORK==8) assert(soft>0);
    std::cout<<"{\"work_boundaries\":"<<work_boundaries
             <<",\"node_boundaries\":"<<node_boundaries
             <<",\"aborted_probes\":"<<aborted
             <<",\"soft_limits\":"<<soft<<"}\n";
}
