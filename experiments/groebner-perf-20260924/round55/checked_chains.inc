    // Basis rows are immutable until the queue is exhausted. A remembered pair
    // has an ordinary-ring representation whose summand leaders are below its
    // lcm, including the implicit Boolean field equations. Merely processing a
    // pair in an F4 matrix does not set this property.
    std::set<uint64_t> chain_represented;
    std::map<uint64_t, size_t> chain_failed_at_basis_size;
    static uint64_t chain_key(uint32_t i, uint32_t j) {
        return (uint64_t(std::max(i,j)) << 32) | std::min(i,j);
    }
    void chain_charge() { charge(); ++chain_stats.overhead_work; }
    void chain_remember(uint32_t i, uint32_t j) {
        chain_charge();
        const uint64_t key=chain_key(i,j);
        if (chain_represented.count(key)) return;
        if (chain_represented.size() >= CHAIN_CACHE_LIMIT) {
            ++chain_stats.cache_saturated; return;
        }
        chain_represented.insert(key);
        chain_stats.represented_entries=chain_represented.size();
    }
    bool chain_known(uint32_t i, uint32_t j) {
        chain_charge();
        if (!(basis_leads[i] & basis_leads[j])) {
            ++chain_stats.product_hits; return true;
        }
        if (chain_represented.count(chain_key(i,j))) {
            ++chain_stats.cache_hits; return true;
        }
        return false;
    }
    Row chain_spolynomial(uint32_t i, uint32_t j) {
        const Mask a=basis_leads[i], b=basis_leads[j], common=a|b;
        return add(multiply(basis[i],common&~a),multiply(basis[j],common&~b));
    }
    struct ChainProbeGuard {
        Engine &engine;
        const uint64_t old_limit, work_before;
        const size_t nodes_before;
        bool soft;
        explicit ChainProbeGuard(Engine &value)
            : engine(value), old_limit(value.max_work), work_before(value.work),
              nodes_before(value.nodes.size()), soft(false) {
            const uint64_t allowance=std::min<uint64_t>(CHAIN_PROBE_WORK,old_limit-work_before);
            engine.max_work=work_before+allowance;
            soft=engine.max_work<old_limit;
        }
        ~ChainProbeGuard() {
            chain_stats.probe_work+=engine.work-work_before;
            chain_stats.peak_probe_nodes=std::max<uint64_t>(
                chain_stats.peak_probe_nodes,engine.nodes.size()-nodes_before);
            engine.max_work=old_limit;
            // No installed row refers to a speculative node. Roll back scratch
            // DAG nodes on every exit; retain every charged work unit.
            engine.nodes.resize(nodes_before);
        }
    };
    bool chain_known_or_probe(uint32_t i, uint32_t j, unsigned &attempts) {
        if (chain_known(i,j)) return true;
        if (CHECKED_CHAIN_MODE != 1 || attempts >= CHAIN_PROBE_LIMIT) return false;
        chain_charge();
        const uint64_t key=chain_key(i,j);
        const auto found=chain_failed_at_basis_size.find(key);
        if (found!=chain_failed_at_basis_size.end() && found->second==basis.size()) {
            ++chain_stats.failed_probe_hits; return false;
        }
        ++attempts; ++chain_stats.probes;
        bool represented=false;
        {
            ChainProbeGuard guard(*this);
            try {
                Row row=normal(chain_spolynomial(i,j),basis);
                represented=row.terms.empty();
                if (represented) ++chain_stats.probe_zero;
                else ++chain_stats.probe_nonzero;
            } catch (const Budget &error) {
                if (guard.soft && std::string(error.what())=="native work budget") {
                    ++chain_stats.probe_soft_limits;
                } else {
                    ++chain_stats.probe_aborted; throw;
                }
            } catch (...) {
                ++chain_stats.probe_aborted; throw;
            }
        }
        if (represented) {
            chain_remember(i,j); return true;
        }
        chain_charge();
        if (found!=chain_failed_at_basis_size.end()) {
            found->second=basis.size();
        } else if (chain_failed_at_basis_size.size()<CHAIN_CACHE_LIMIT) {
            chain_failed_at_basis_size.emplace(key,basis.size());
            chain_stats.failed_entries=chain_failed_at_basis_size.size();
        } else ++chain_stats.cache_saturated;
        return false;
    }
    bool chain_prune(const Pair &pair) {
        ++chain_stats.candidate_pairs;
        if (chain_known(pair.i,pair.j)) {
            ++chain_stats.represented_pairs_skipped; return true;
        }
        const Mask a=basis_leads[pair.i], b=basis_leads[pair.j], common=a|b;
        unsigned probes=0;
        const size_t stop=std::min<size_t>(basis.size(),CHAIN_SCAN_LIMIT);
        for (size_t k=0;k<stop;++k) {
            chain_charge(); ++chain_stats.scanned_leaders;
            if (k==pair.i || k==pair.j) continue;
            const Mask bridge=basis_leads[k];
            // Proper divisors are a conservative search policy; the two child
            // representations, rather than degree or queue state, justify pruning.
            if (!divides(bridge,common) || (a|bridge)==common || (b|bridge)==common) continue;
            ++chain_stats.eligible_chains;
            if (chain_known_or_probe(pair.i,uint32_t(k),probes) &&
                chain_known_or_probe(uint32_t(k),pair.j,probes)) {
                chain_remember(pair.i,pair.j);
                ++chain_stats.pruned_pairs; return true;
            }
        }
        return false;
    }
