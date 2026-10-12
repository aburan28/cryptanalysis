// Independent exhaustive pair scan for Q1487 inverse-partner support.
#define Q1487_NO_MAIN
#include "native_solver.cpp"

int main(int argc, char **argv) {
    try {
        require(argc == 5,
                "usage: native_selftest FIELD VARIABLES TARGETS WINDOW_MAP");
        q1420::Field field(argv[1]);
        Variables vars(argv[2]);
        Targets targets(argv[3]);
        WindowMap windows(argv[4], vars, 1000000);
        InverseTheory theory(field, vars, targets, windows, 1000000, 4096);
        uint64_t direct_evals = 0, cases = 0, large_partner_cases = 0;
        auto set_domain = [&](int leaf, int start, int free_bits,
                              bool force_one) {
            U128 mask = windows.masks[start];
            theory.assignment[windows.selectors[leaf][start]] = 1;
            int available = 0;
            for (int j = 0; j < vars.n; ++j) {
                int bit = vars.leaves[leaf][j];
                if ((mask >> j) & 1) {
                    if (force_one && available == 0)
                        theory.assignment[bit] = 1;
                    else if (available >= free_bits)
                        theory.assignment[bit] = -1;
                    ++available;
                } else theory.assignment[bit] = -1;
            }
        };
        auto check = [&](int free_a, int free_b, int start_a,
                         int start_b, bool force_one = false) {
            std::fill(theory.assignment.begin(), theory.assignment.end(), 0);
            set_domain(0, start_a, free_a, force_one);
            set_domain(1, start_b, free_b, force_one);
            auto a = theory.leaf_state(0), b = theory.leaf_state(1);
            auto a_values = theory.options(a), b_values = theory.options(b);
            require(!a_values.empty() && !b_values.empty(),
                    "empty selftest leaf domain");
            require(std::min(a_values.size(), b_values.size()) <= 4096,
                    "selftest anchor exceeds cap");
            std::vector<U128> mids{0, U128(1), U128(2)};
            for (U128 x : a_values) {
                for (U128 y : b_values) {
                    auto roots = field.roots_onb(x, y);
                    if (!roots.empty()) {
                        mids.push_back(roots[0]);
                        goto witness_found;
                    }
                }
            }
        witness_found:
            for (U128 mid : mids) {
                bool direct = false;
                U128 mid_poly = field.to_poly(mid);
                for (U128 x : a_values) {
                    U128 x_poly = field.to_poly(x);
                    for (U128 y : b_values) {
                        ++direct_evals;
                        if (field.evaluate_s3(x_poly, field.to_poly(y),
                                              mid_poly) == 0) {
                            direct = true;
                            break;
                        }
                    }
                    if (direct) break;
                }
                bool inverse = theory.pair_supported(a, b, mid, 1);
                require(direct == inverse,
                        "inverse partner disagrees with direct S3 scan");
                ++cases;
                if (std::max(a_values.size(), b_values.size()) > 4096)
                    ++large_partner_cases;
            }
        };
        if (vars.n == 53) {
            check(6, 8, 0, 7);
            check(8, 6, 5, 12);
            check(1, 14, 0, 14);
            check(7, 9, 9, 18, true);
        } else {
            check(6, 8, 0, 11);
            check(8, 6, 17, 3);
            check(3, 15, 0, 23);
            check(15, 3, 41, 7);
            check(7, 11, 8, 29, true);
        }
        require(large_partner_cases > 0,
                "missing large-partner selftest case");
        std::cout << "{\"status\":\"passed\",\"degree_n\":" << vars.n
                  << ",\"checked_domain_midpoint_cases\":" << cases
                  << ",\"large_partner_cases\":" << large_partner_cases
                  << ",\"direct_s3_evaluations\":" << direct_evals
                  << ",\"inverse_root_calls\":" << theory.inverse_root_calls
                  << ",\"membership_checks\":"
                  << theory.inverse_membership_checks << "}\n";
        return 0;
    } catch (const std::exception &error) {
        std::cerr << error.what() << "\n";
        return 2;
    }
}
