// Build with -DSOLVER_SOURCE='"/absolute/path/to/solver.cpp"' and optionally
// -DHYBRID. Same solver calls, repeated in-process to reduce sub-ms noise.
#define main solver_program_main
#include SOLVER_SOURCE
#undef main
#include <cstdlib>
#include <ctime>
#include <iomanip>

static double median(std::vector<double> values) {
    std::sort(values.begin(), values.end());
    return values[values.size()/2];
}

int main() {
    int n, count, limit, degree;
    if (!(std::cin >> n >> count >> limit >> degree) || n < 1 || n > 12) return 2;
    int repeats = 21;
    if (const char* text = std::getenv("GB_BENCH_INNER")) repeats = std::max(1, std::atoi(text));
    Engine layout(n, limit, degree);
    std::vector<Poly> input(count);
    for (auto& p: input) {
        int terms; std::cin >> terms;
        for (int j=0; j<terms; ++j) {
            uint32_t mask; std::cin >> mask;
            if (mask >= uint32_t(layout.universe)) return 3;
            uint32_t rank = layout.rank_by_mask[mask];
            p.w[rank/64] ^= uint64_t(1) << (rank%64);
        }
    }
    std::vector<Poly> retained;
    std::vector<double> cpu, elapsed;
    std::vector<std::vector<double>> phases(5);
    long long insertions=0, operations=0;
#ifdef HYBRID
    MatrixStats last;
#endif
    for (int run=0; run<=repeats; ++run) {
        Engine e(n, limit, degree);
        auto started = std::chrono::steady_clock::now();
        std::clock_t cpu_started = std::clock();
#ifdef HYBRID
        auto seed = f5_signature_seed(e, input);
        double signature = std::chrono::duration<double>(std::chrono::steady_clock::now()-started).count();
        MatrixStats stats;
        auto basis = macaulay_m4ri(e, input, seed, degree, stats);
        last = stats;
        double values[] = {signature, stats.generation, stats.population, stats.elimination, stats.extraction};
        operations = e.pairs_processed;
#else
        auto basis = e.basis(input);
        double values[] = {e.initial_seconds, e.signature_seconds, e.interreduce_seconds,
                           e.completion_seconds, e.final_reduce_seconds};
        operations = e.reductions;
#endif
        double cpu_seconds = double(std::clock()-cpu_started)/CLOCKS_PER_SEC;
        double seconds = std::chrono::duration<double>(std::chrono::steady_clock::now()-started).count();
        if (run && basis != retained) return 4;
        retained = basis;
        insertions = e.insertions;
        if (run) {
            cpu.push_back(cpu_seconds); elapsed.push_back(seconds);
            for (int i=0; i<5; ++i) phases[i].push_back(values[i]);
        }
    }
    std::cout << std::setprecision(10) << "OK " << retained.size() << ' ' << median(elapsed)
              << ' ' << insertions << ' ' << operations;
#ifdef HYBRID
    std::cout << ' ' << median(phases[0]) << ' ' << last.rows << ' ' << last.rank;
    for (int i=1; i<5; ++i) std::cout << ' ' << median(phases[i]);
    std::cout << ' ' << last.f5_rows << ' ' << last.f5_remainders;
#else
    for (int i=0; i<5; ++i) std::cout << ' ' << median(phases[i]);
#endif
    std::cout << '\n';
    for (auto& p: retained) {
        auto terms = layout.masks(p);
        std::sort(terms.begin(), terms.end());
        std::cout << terms.size();
        for (auto mask: terms) std::cout << ' ' << mask;
        std::cout << '\n';
    }
    std::cerr << std::setprecision(10) << "{\"inner_repeats\":" << repeats
              << ",\"basis_cpu_seconds\":" << median(cpu) << ",\"cpu_samples\":[";
    for (size_t i=0; i<cpu.size(); ++i) std::cerr << (i ? "," : "") << cpu[i];
    std::cerr << "]}\n";
}
