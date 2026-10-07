// Exercise the Q1462 SAT guard on one planted and one exact-zero state.
#define Q1462_NO_MAIN
#include "native_solver.cpp"

struct Input {
    std::string cell;
    int index = 0, pair = 0;
    U128 mid = 0;
    q1461::Leaf first, second;
};

Input read_input(std::istream &input) {
    Input row;
    std::string mid, af, ao, bf, bo;
    require(bool(input >> row.cell >> row.index >> row.pair >> mid >>
                 af >> ao >> bf >> bo), "short guard-control input");
    row.mid = q1420::parse_hex(mid);
    row.first = {q1420::parse_hex(af), q1420::parse_hex(ao)};
    row.second = {q1420::parse_hex(bf), q1420::parse_hex(bo)};
    return row;
}

void install(SparseTheory &theory, const Input &row) {
    for (int bit = 0; bit < theory.vars.n; ++bit) {
        int var = theory.vars.mids[row.pair][bit];
        theory.assignment[var] = row.mid >> bit & 1 ? 1 : -1;
    }
    for (int side = 0; side < 2; ++side) {
        q1461::Leaf leaf = side == 0 ? row.first : row.second;
        for (int bit = 0; bit < theory.vars.n; ++bit)
            if (leaf.fixed >> bit & 1) {
                int var = theory.vars.leaves[2 * row.pair + side][bit];
                theory.assignment[var] = leaf.ones >> bit & 1 ? 1 : -1;
            }
    }
}

int main(int argc, char **argv) {
    try {
        require(argc == 6,
                "usage: control_guard FIELD MAP TARGETS Q1461_INPUTS SUM_CAP");
        q1420::Field field(argv[1]);
        Variables vars(argv[2]);
        Targets targets(argv[3]);
        require(field.n == vars.n && field.n == targets.n,
                "control field/map/target mismatch");
        std::ifstream input(argv[4]);
        require(bool(input), "Q1461 control input missing");
        Input planted = read_input(input), ordinary = read_input(input);
        require(planted.cell.find("planted") != std::string::npos &&
                ordinary.cell.find("ordinary") != std::string::npos,
                "wrong Q1461 control row order");
        int max_var = 0;
        for (const auto &row : vars.leaves)
            for (int var : row) max_var = std::max(max_var, var);
        for (const auto &row : vars.mids)
            for (int var : row) max_var = std::max(max_var, var);
        for (int var : vars.selector) max_var = std::max(max_var, var);
        SparseTheory positive(field, vars, targets, max_var,
                              std::stoi(argv[5]));
        install(positive, planted);
        positive.maybe_sparse_pair(planted.pair);
        require(positive.checks == 1 && positive.x_only_hits == 1 &&
                positive.exact_pairs >= 1 && positive.pending.empty(),
                "planted pair falsely rejected");
        SparseTheory negative(field, vars, targets, max_var,
                              std::stoi(argv[5]));
        install(negative, ordinary);
        negative.maybe_sparse_pair(ordinary.pair);
        require(negative.checks == 1 && negative.no_pair_rejections == 1 &&
                negative.pending.size() == 1,
                "ordinary zero-pair state was not rejected");
        for (int lit : negative.pending.front()) {
            int var = std::abs(lit);
            require(negative.assignment[var] == (lit > 0 ? -1 : 1),
                    "negative control guard is not false");
        }
        std::cout << "{\"degree_n\":" << field.n
                  << ",\"positive_checked_sums\":"
                  << positive.checked_sums
                  << ",\"positive_exact_pairs\":"
                  << positive.exact_pairs
                  << ",\"negative_checked_sums\":"
                  << negative.checked_sums
                  << ",\"negative_guard_literals\":"
                  << negative.pending.front().size() << "}\n";
        return 0;
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
