// Minimal CaDiCaL external-clause callback contract check for Q1420.
#include <cadical.hpp>

#include <deque>
#include <iostream>
#include <vector>

struct Probe : CaDiCaL::ExternalPropagator {
    std::deque<std::vector<int>> pending;
    std::vector<int> current;
    size_t index = 0;
    bool added = false;
    void notify_assignment(const std::vector<int> &lits) override {
        for (int lit : lits) if (lit == 1 && !added) {
            pending.push_back({-1, 2});
            added = true;
        }
    }
    void notify_new_decision_level() override {}
    void notify_backtrack(size_t) override {}
    bool cb_check_found_model(const std::vector<int> &model) override {
        bool x = false, y = false;
        for (int lit : model) {
            if (lit == 1) x = true;
            if (lit == 2) y = true;
        }
        if (x && !y && !added) {
            pending.push_back({-1, 2});
            added = true;
            return false;
        }
        return !x || y;
    }
    bool cb_has_external_clause(bool &forgettable) override {
        forgettable = false;
        return !pending.empty() || !current.empty();
    }
    int cb_add_external_clause_lit() override {
        if (current.empty()) {
            current = pending.front();
            pending.pop_front();
            index = 0;
        }
        if (index == current.size()) {
            current.clear();
            return 0;
        }
        return current[index++];
    }
};

int main() {
    CaDiCaL::Solver solver;
    solver.add(1); solver.add(0);  // x = true
    Probe probe;
    solver.connect_external_propagator(&probe);
    solver.add_observed_var(1);
    solver.add_observed_var(2);
    int status = solver.solve();
    if (status != 10 || solver.val(2) != 2 || !probe.added) return 2;
    std::cout << "PASS external clause x implies y\n";
    return 0;
}
