// Q1437: seeded leaf decision schedules with charged restart accounting.
// The original three-link S3 CNF remains in the input formula.
#include <Python.h>
#include <cadical.hpp>
#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <ctime>
#include <cstdlib>
#include <deque>
#include <fstream>
#include <iostream>
#include <set>
#include <stdexcept>
#include <string>
#include <thread>
#include <utility>
#include <vector>
#include <sys/resource.h>

static void need(bool value, const char *message) {
  if (!value) throw std::runtime_error(message);
}

class RootOracle {
  PyObject *onb = nullptr;
  PyObject *from_coords = nullptr;
  PyObject *to_coords = nullptr;
  PyObject *roots = nullptr;
  PyObject *evaluate = nullptr;
  PyObject *inverse = nullptr;

  static PyObject *long_from_bits(const std::string &bits) {
    std::string binary = "0b";
    for (auto bit = bits.rbegin(); bit != bits.rend(); ++bit) binary.push_back(*bit);
    return PyLong_FromString(binary.data(), nullptr, 0);
  }

  static std::string bits_from_long(PyObject *x, int n) {
    PyObject *s = PyObject_CallMethod(x, "__format__", "s", "b");
    need(s != nullptr, "Python integer conversion failed");
    const char *chars = PyUnicode_AsUTF8(s);
    need(chars != nullptr, "Python integer text failed");
    std::string result(chars);
    Py_DECREF(s);
    need(result.size() <= size_t(n), "root exceeds field degree");
    std::reverse(result.begin(), result.end());
    result.resize(n, '0');
    return result;
  }

public:
  RootOracle(const std::string &module_dir, const std::string &field_dir, int n) {
    Py_Initialize();
    PyObject *path = PySys_GetObject("path");
    std::string counter_dir = module_dir + "/q20261011_operation_account";
    for (const auto &dir : {module_dir, field_dir, counter_dir}) {
      PyObject *item = PyUnicode_FromString(dir.c_str());
      need(item && PyList_Insert(path, 0, item) == 0, "cannot set Python path");
      Py_DECREF(item);
    }
    PyObject *field = PyImport_ImportModule("counted_onb");
    PyObject *oracle = PyImport_ImportModule("s3_root_oracle");
    if (!field || !oracle) { PyErr_Print(); throw std::runtime_error("oracle import failed"); }
    PyObject *klass = PyObject_GetAttrString(field, "CountedOnb");
    PyObject *degree = PyLong_FromLong(n);
    onb = PyObject_CallFunctionObjArgs(klass, degree, nullptr);
    PyObject *reset = onb ? PyObject_CallMethod(onb, "reset_counts", nullptr)
                          : nullptr;
    need(reset != nullptr, "cannot reset field API counters");
    Py_DECREF(reset);
    from_coords = PyObject_GetAttrString(onb, "fromCoords");
    to_coords = PyObject_GetAttrString(onb, "toCoords");
    roots = PyObject_GetAttrString(oracle, "s3_roots");
    inverse = PyObject_GetAttrString(onb, "inv");
    PyObject *chain = PyImport_ImportModule("chain_s3");
    evaluate = chain ? PyObject_GetAttrString(chain, "evaluate_s3") : nullptr;
    Py_XDECREF(chain);
    Py_DECREF(field); Py_DECREF(oracle); Py_DECREF(klass); Py_DECREF(degree);
    if (!onb || !from_coords || !to_coords || !roots || !evaluate || !inverse) {
      PyErr_Print(); throw std::runtime_error("oracle construction failed");
    }
  }

  std::vector<std::string> query(const std::string &a, const std::string &b) {
    PyObject *ca = long_from_bits(a), *cb = long_from_bits(b);
    PyObject *pa = PyObject_CallFunctionObjArgs(from_coords, ca, nullptr);
    PyObject *pb = PyObject_CallFunctionObjArgs(from_coords, cb, nullptr);
    PyObject *result = PyObject_CallFunctionObjArgs(roots, onb, pa, pb, nullptr);
    Py_XDECREF(ca); Py_XDECREF(cb); Py_XDECREF(pa); Py_XDECREF(pb);
    if (!result) { PyErr_Print(); throw std::runtime_error("S3 root query failed"); }
    std::vector<std::string> found;
    Py_ssize_t count = PySequence_Size(result);
    for (Py_ssize_t i = 0; i < count; ++i) {
      PyObject *root = PySequence_GetItem(result, i);
      PyObject *coordinate = PyObject_CallFunctionObjArgs(to_coords, root, nullptr);
      need(coordinate != nullptr, "root coordinate conversion failed");
      found.push_back(bits_from_long(coordinate, int(a.size())));
      Py_DECREF(coordinate); Py_DECREF(root);
    }
    Py_DECREF(result);
    need(found.size() <= 2, "S3 produced more than two roots");
    return found;
  }

  bool final_matches(const std::string &a, const std::string &b,
                     const std::set<std::string> &targets) {
    if (a.find('1') != std::string::npos && b.find('1') != std::string::npos) {
      for (const auto &root : query(a, b))
        if (targets.count(root)) return true;
      return false;
    }
    // s3_roots requires nonzero leading inputs. Direct evaluation covers
    // every target when either middle coordinate is zero.
    PyObject *ca = long_from_bits(a), *cb = long_from_bits(b);
    PyObject *pa = PyObject_CallFunctionObjArgs(from_coords, ca, nullptr);
    PyObject *pb = PyObject_CallFunctionObjArgs(from_coords, cb, nullptr);
    Py_DECREF(ca); Py_DECREF(cb);
    need(pa && pb, "middle-coordinate conversion failed");
    bool match = false;
    for (const auto &target : targets) {
      PyObject *ct = long_from_bits(target);
      PyObject *pt = PyObject_CallFunctionObjArgs(from_coords, ct, nullptr);
      PyObject *value = PyObject_CallFunctionObjArgs(evaluate, onb, pa, pb, pt, nullptr);
      PyObject *zero = PyLong_FromLong(0);
      if (!value) { PyErr_Print(); throw std::runtime_error("final S3 evaluation failed"); }
      int equal = PyObject_RichCompareBool(value, zero, Py_EQ);
      Py_DECREF(ct); Py_DECREF(pt); Py_DECREF(value); Py_DECREF(zero);
      need(equal >= 0, "final S3 comparison failed");
      if (equal) { match = true; break; }
    }
    Py_DECREF(pa); Py_DECREF(pb);
    return match;
  }

  std::vector<std::string> compatible_second(
      const std::string &first, const std::set<std::string> &targets) {
    std::set<std::string> compatible;
    bool first_zero = first.find('1') == std::string::npos;
    for (const auto &target : targets) {
      bool target_zero = target.find('1') == std::string::npos;
      if (!first_zero && !target_zero) {
        for (const auto &root : query(first, target)) compatible.insert(root);
      } else if (first_zero != target_zero) {
        // S3(0,u,z)=(u*z)^2+1, so z=u^{-1} for u != 0.
        const std::string &nonzero = first_zero ? target : first;
        PyObject *coords = long_from_bits(nonzero);
        PyObject *point = PyObject_CallFunctionObjArgs(from_coords, coords, nullptr);
        Py_XDECREF(coords);
        need(point != nullptr, "degenerate S3 coordinate conversion failed");
        PyObject *value = PyObject_CallFunctionObjArgs(inverse, point, nullptr);
        Py_DECREF(point);
        if (!value) { PyErr_Print(); throw std::runtime_error("degenerate S3 inverse failed"); }
        PyObject *encoded = PyObject_CallFunctionObjArgs(to_coords, value, nullptr);
        Py_DECREF(value);
        need(encoded != nullptr, "degenerate S3 inverse encoding failed");
        compatible.insert(bits_from_long(encoded, int(first.size())));
        Py_DECREF(encoded);
      }
      // S3(0,0,z)=1 has no root.
    }
    return {compatible.begin(), compatible.end()};
  }

  bool rational_koblitz_b1_x(const std::string &bits) {
    // For y^2+xy=x^3+1 and x != 0, z=y/x obeys
    // z^2+z=x+x^(-2); this has a field solution iff its trace is zero.
    if (bits.find('1') == std::string::npos) return true;
    PyObject *coords = long_from_bits(bits);
    PyObject *x = PyObject_CallFunctionObjArgs(from_coords, coords, nullptr);
    Py_XDECREF(coords);
    need(x != nullptr, "leaf coordinate conversion failed");
    PyObject *inv = PyObject_CallMethod(onb, "inv", "O", x);
    if (!inv) { Py_DECREF(x); PyErr_Print(); throw std::runtime_error("leaf inverse failed"); }
    PyObject *inv2 = PyObject_CallMethod(onb, "sqr", "O", inv);
    Py_DECREF(inv);
    need(inv2 != nullptr, "leaf inverse square failed");
    PyObject *rhs = PyObject_CallMethod(onb, "add", "OO", x, inv2);
    Py_DECREF(x); Py_DECREF(inv2);
    need(rhs != nullptr, "leaf rationality right side failed");
    PyObject *trace = PyObject_CallMethod(onb, "trace", "O", rhs);
    Py_DECREF(rhs);
    need(trace != nullptr, "leaf rationality trace failed");
    int result = PyObject_IsTrue(trace);
    Py_DECREF(trace);
    need(result >= 0, "leaf rationality truth conversion failed");
    return result == 0;
  }

  std::string field_api_counts_json() {
    PyObject *counts = PyObject_CallMethod(onb, "snapshot_counts", nullptr);
    need(counts != nullptr, "cannot read field API counters");
    PyObject *json = PyImport_ImportModule("json");
    need(json != nullptr, "cannot import JSON encoder");
    PyObject *encoded = PyObject_CallMethod(json, "dumps", "O", counts);
    Py_DECREF(counts); Py_DECREF(json);
    need(encoded != nullptr, "cannot encode field API counters");
    const char *chars = PyUnicode_AsUTF8(encoded);
    need(chars != nullptr, "cannot read field API JSON");
    std::string result(chars);
    Py_DECREF(encoded);
    return result;
  }

  ~RootOracle() {
    Py_XDECREF(onb); Py_XDECREF(from_coords); Py_XDECREF(to_coords);
    Py_XDECREF(roots); Py_XDECREF(evaluate); Py_XDECREF(inverse); Py_Finalize();
  }
};

static std::set<std::string> read_targets(const std::string &path, int n) {
  if (path == "-") return {};
  std::ifstream input(path);
  need(bool(input), "cannot open target coset");
  int degree = 0, count = 0;
  std::string curve_id, workload_id;
  input >> degree >> count >> curve_id >> workload_id;
  need(degree == n && count > 0, "target-coset degree or count mismatch");
  std::set<std::string> targets;
  for (int i = 0; i < count; ++i) {
    std::string bits;
    input >> bits;
    need(bits.size() == size_t(n) &&
         bits.find_first_not_of("01") == std::string::npos,
         "malformed target x coordinate");
    need(targets.insert(bits).second, "duplicate target x coordinate");
  }
  need(bool(input), "incomplete target coset");
  return targets;
}

class PairPropagator : public CaDiCaL::ExternalPropagator {
  int n;
  int weight_bound;
  std::vector<std::vector<int>> rows;
  std::vector<int> selectors;
  std::vector<int8_t> assignment;
  std::vector<std::vector<int>> trail{1};
  std::set<std::string> seen;
  std::set<std::string> seen_final;
  std::set<std::string> seen_early;
  std::set<std::string> seen_leaf;
  std::set<std::string> target_coset;
  std::deque<std::vector<int>> clauses;
  size_t clause_position = 0;
  RootOracle &oracle;
  CaDiCaL::Solver &solver;
  std::string decision_mode;
  int decision_seed;
  std::string encoding;
  std::string early_mode;
  std::string leaf_mode;
  int early_limit;

  bool full(int row) const {
    for (int var : rows[row]) if (!assignment[var]) return false;
    return true;
  }
  std::string coordinate(int row) const {
    std::string value(n, '0');
    for (int i = 0; i < n; ++i)
      if (assignment[rows[row][i]] > 0) value[i] = '1';
    return value;
  }
  std::vector<int> guard(int pair, bool use_saturated_guard) {
    std::vector<int> result;
    for (int row : {2 * pair, 2 * pair + 1}) {
      int weight = 0;
      for (int var : rows[row]) weight += assignment[var] > 0;
      bool saturated = weight == weight_bound;
      if (saturated) ++saturated_leaves_seen;
      for (int var : rows[row]) {
        if (use_saturated_guard && saturated && assignment[var] < 0) continue;
        result.push_back(-assignment[var] * var);
      }
    }
    guard_literals_total += result.size();
    return result;
  }
  int new_guard_var() {
    int var = solver.vars() + 1;
    solver.add_observed_var(var);
    assignment.resize(size_t(var + 1), 0);
    ++guard_vars;
    return var;
  }
  void add_for_pair(int pair) {
    if (!full(2 * pair) || !full(2 * pair + 1)) return;
    std::string a = coordinate(2 * pair), b = coordinate(2 * pair + 1);
    if (a.find('1') == std::string::npos || b.find('1') == std::string::npos) return;
    std::string key = std::to_string(pair) + ":" + a + ":" + b;
    if (!seen.insert(key).second) return;
    auto candidate_roots = oracle.query(a, b);
    ++root_queries;
    bool use_saturated_guard = encoding == "satpivot" || encoding == "satlegacy";
    std::vector<int> prefix = guard(pair, use_saturated_guard);
    if (candidate_roots.empty()) {
      clauses.push_back(prefix);
      ++empty_root_pairs;
      return;
    }
    if (encoding == "shared" || encoding == "pivot" || encoding == "satpivot") {
      bool short_guard = encoding == "shared";
      int active = short_guard ? new_guard_var() : 0;
      std::vector<int> condition;
      if (short_guard) {
        // Exact equivalence: active iff all 2n leaf literals match this pair.
        auto activate = prefix;
        activate.push_back(active);
        clauses.push_back(std::move(activate));
        for (int lit : prefix) clauses.push_back({-active, -lit});
        condition = {-active};
      } else {
        condition = prefix;
      }
      auto add_mid_clause = [&](std::initializer_list<int> tail) {
        auto clause = condition;
        clause.insert(clause.end(), tail);
        clauses.push_back(std::move(clause));
      };
      if (candidate_roots.size() == 1) {
        for (int i = 0; i < n; ++i) {
          int var = rows[4 + pair][i];
          add_mid_clause({candidate_roots[0][i] == '1' ? var : -var});
        }
      } else {
        int pivot_bit = -1;
        for (int i = 0; i < n; ++i)
          if (candidate_roots[0][i] != candidate_roots[1][i]) {
            pivot_bit = i;
            break;
          }
        need(pivot_bit >= 0, "distinct roots have identical coordinates");
        int pivot = rows[4 + pair][pivot_bit];
        for (int i = 0; i < n; ++i) {
          int var = rows[4 + pair][i];
          if (candidate_roots[0][i] == candidate_roots[1][i]) {
            add_mid_clause({candidate_roots[0][i] == '1' ? var : -var});
          } else if (i != pivot_bit) {
            // Each differing bit is equal or opposite to the pivot in both roots.
            if (candidate_roots[0][i] == candidate_roots[0][pivot_bit]) {
              add_mid_clause({-pivot, var});
              add_mid_clause({pivot, -var});
            } else {
              add_mid_clause({pivot, var});
              add_mid_clause({-pivot, -var});
            }
          }
        }
      }
      return;
    }
    for (int i = 0; i < n; ++i) {
      int var = rows[4 + pair][i];
      if (candidate_roots.size() == 1) {
        auto clause = prefix;
        clause.push_back(candidate_roots[0][i] == '1' ? var : -var);
        clauses.push_back(std::move(clause));
      } else {
        for (int choice = 0; choice < 2; ++choice) {
          auto clause = prefix;
          clause.push_back(choice == 0 ? selectors[pair] : -selectors[pair]);
          clause.push_back(candidate_roots[choice][i] == '1' ? var : -var);
          clauses.push_back(std::move(clause));
        }
      }
    }
  }
  void add_final_check() {
    if (target_coset.empty() || !full(4) || !full(5)) return;
    std::string a = coordinate(4), b = coordinate(5);
    std::string key = a + ":" + b;
    if (!seen_final.insert(key).second) return;
    ++final_link_checks;
    if (oracle.final_matches(a, b, target_coset)) {
      ++final_link_matches;
      return;
    }
    std::vector<int> clause;
    for (int row : {4, 5})
      for (int var : rows[row]) clause.push_back(-assignment[var] * var);
    clauses.push_back(std::move(clause));
    ++final_link_rejections;
  }
  void add_early_target(int source_row) {
    if (early_mode == "off" || target_coset.empty() || !full(source_row)) return;
    int destination_row = source_row == 4 ? 5 : 4;
    std::string a = coordinate(source_row);
    std::string key = std::to_string(source_row) + ':' + a;
    if (!seen_early.insert(key).second) return;
    if (early_queries >= uint64_t(early_limit)) {
      ++early_skipped_limit;
      return;
    }
    auto compatible = oracle.compatible_second(a, target_coset);
    ++early_queries;
    if (early_state_samples.size() < 512)
      early_state_samples.push_back({source_row, a});
    else
      ++early_state_samples_truncated;
    if (source_row == 5) ++early_reverse_queries;
    early_roots_total += compatible.size();
    early_roots_max = std::max(early_roots_max, uint64_t(compatible.size()));
    std::vector<int> prefix;
    for (int var : rows[source_row]) prefix.push_back(-assignment[var] * var);
    if (compatible.empty()) {
      clauses.push_back(std::move(prefix));
      ++early_zero_root;
      if (early_zero_samples.size() < 8) early_zero_samples.push_back(a);
      return;
    }
    if (early_mode == "consensus") {
      for (int bit = 0; bit < n; ++bit) {
        char value = compatible.front()[bit];
        bool common = std::all_of(compatible.begin(), compatible.end(),
                                  [&](const auto &root) { return root[bit] == value; });
        if (common) {
          auto clause = prefix;
          clause.push_back(value == '1' ? rows[destination_row][bit]
                                        : -rows[destination_row][bit]);
          clauses.push_back(std::move(clause));
          ++early_consensus_bits;
        }
      }
      return;
    }
    std::vector<int> support = prefix;
    for (const auto &root : compatible) {
      int selector = new_guard_var();
      ++early_selector_vars;
      support.push_back(selector);
      for (int bit = 0; bit < n; ++bit)
        clauses.push_back({-selector, root[bit] == '1'
                                         ? rows[destination_row][bit]
                                         : -rows[destination_row][bit]});
    }
    clauses.push_back(std::move(support));
  }
  bool add_leaf_checks() {
    if (leaf_mode == "off") return false;
    for (int row = 0; row < 4; ++row) {
      int positive_count = 0;
      for (int var : rows[row]) positive_count += assignment[var] > 0;
      bool complete = full(row);
      bool eager = leaf_mode == "eager" &&
                   positive_count == weight_bound && !complete;
      if (!complete && !eager) continue;
      std::string x = coordinate(row);
      std::string key = std::to_string(row) + ':' + x;
      if (!seen_leaf.insert(key).second) continue;
      ++leaf_rationality_checks;
      if (eager) ++leaf_eager_checks;
      if (oracle.rational_koblitz_b1_x(x)) continue;
      ++leaf_nonrational_rejections;
      if (eager) ++leaf_eager_rejections;
      if (leaf_rejection_samples.size() < 8)
        leaf_rejection_samples.push_back({row, x});
      bool saturated = (leaf_mode == "sat" || leaf_mode == "eager") &&
                       positive_count == weight_bound;
      if (saturated) ++leaf_saturated_rejections;
      std::vector<int> clause;
      for (int var : rows[row]) {
        if (saturated && assignment[var] < 0) continue;
        clause.push_back(-assignment[var] * var);
      }
      leaf_guard_literals += clause.size();
      clauses.push_back(std::move(clause));
      return true;
    }
    return false;
  }

public:
  uint64_t root_queries = 0, empty_root_pairs = 0, decision_calls = 0;
  uint64_t clauses_sent = 0, model_checks = 0, external_literals = 0;
  uint64_t guard_vars = 0, guard_literals_total = 0;
  uint64_t saturated_leaves_seen = 0;
  uint64_t final_link_checks = 0, final_link_matches = 0, final_link_rejections = 0;
  uint64_t early_queries = 0, early_zero_root = 0, early_roots_total = 0;
  uint64_t early_roots_max = 0, early_selector_vars = 0, early_consensus_bits = 0;
  uint64_t early_skipped_limit = 0;
  uint64_t early_reverse_queries = 0;
  std::vector<std::string> early_zero_samples;
  std::vector<std::pair<int, std::string>> early_state_samples;
  uint64_t early_state_samples_truncated = 0;
  uint64_t leaf_rationality_checks = 0, leaf_nonrational_rejections = 0;
  uint64_t leaf_saturated_rejections = 0, leaf_guard_literals = 0;
  uint64_t leaf_eager_checks = 0, leaf_eager_rejections = 0;
  std::vector<std::pair<int, std::string>> leaf_rejection_samples;
  PairPropagator(int degree, std::vector<std::vector<int>> mapping,
                 int max_var, RootOracle &root_oracle, CaDiCaL::Solver &sat,
                 std::string mode, int seed, std::string root_encoding,
                 int max_weight,
                 std::string target_encoding, int target_limit,
                 std::string rationality_mode,
                 std::set<std::string> targets)
      : n(degree), weight_bound(max_weight), rows(std::move(mapping)),
        selectors{max_var + 1, max_var + 2},
        assignment(max_var + 3, 0), oracle(root_oracle), solver(sat),
        decision_mode(std::move(mode)), decision_seed(seed),
        encoding(std::move(root_encoding)),
        early_mode(std::move(target_encoding)), early_limit(target_limit),
        leaf_mode(std::move(rationality_mode)),
        target_coset(std::move(targets)) {
    need(rows.size() == 6, "mapping needs four leaves and two middle rows");
    for (const auto &row : rows) need(row.size() == size_t(n), "bad mapping row");
    need(weight_bound > 0 && weight_bound <= n, "bad weight bound");
    need(decision_seed >= 0 && decision_seed <= 1000000,
         "bad decision seed");
    need(encoding == "legacy" || encoding == "shared" || encoding == "pivot" ||
         encoding == "satpivot" || encoding == "satlegacy",
         "bad root encoding");
    need(early_mode == "off" || early_mode == "consensus" ||
         early_mode == "selector", "bad early target encoding");
    need(early_limit >= 0, "bad early target query limit");
    need(leaf_mode == "off" || leaf_mode == "full" ||
         leaf_mode == "sat" || leaf_mode == "eager",
         "bad leaf rationality mode");
  }
  const std::vector<std::vector<int>> &mapping() const { return rows; }
  const std::vector<int> &selector_vars() const { return selectors; }
  const std::vector<std::string> &zero_samples() const { return early_zero_samples; }
  const std::vector<std::pair<int, std::string>> &early_states() const {
    return early_state_samples;
  }
  const std::vector<std::pair<int, std::string>> &rejected_leaves() const {
    return leaf_rejection_samples;
  }
  void notify_assignment(const std::vector<int> &lits) override {
    for (int lit : lits) {
      int var = std::abs(lit);
      need(var < int(assignment.size()), "assignment beyond declared variables");
      assignment[var] = lit > 0 ? 1 : -1;
      trail.back().push_back(var);
    }
  }
  void notify_new_decision_level() override { trail.emplace_back(); }
  void notify_backtrack(size_t new_level) override {
    while (trail.size() > new_level + 1) {
      for (int var : trail.back()) assignment[var] = 0;
      trail.pop_back();
    }
  }
  bool cb_check_found_model(const std::vector<int> &) override {
    ++model_checks;
    return true;  // The original three S3 links are fully encoded in CNF.
  }
  int cb_decide() override {
    ++decision_calls;
    if (decision_mode == "none") return 0;
    bool first_pair_only = decision_mode == "first" || decision_mode == "firstpos" ||
                           decision_mode == "firstspread";
    bool positive = decision_mode == "firstpos" || decision_mode == "allpos" ||
                    decision_mode == "firstspread" || decision_mode == "allspread" ||
                    decision_mode == "alloffset" || decision_mode == "allstride" ||
                    decision_mode == "pair1pos" || decision_mode == "pair1spread" ||
                    decision_mode == "seededpos" || decision_mode == "seededspread";
    bool offset = decision_mode == "firstspread" || decision_mode == "allspread" ||
                  decision_mode == "alloffset" || decision_mode == "pair1spread";
    bool stride = decision_mode == "firstspread" || decision_mode == "allspread" ||
                  decision_mode == "allstride" || decision_mode == "pair1spread";
    bool seeded = decision_mode == "seededpos" ||
                  decision_mode == "seededspread";
    bool reverse = decision_mode == "pair1pos" || decision_mode == "pair1spread" ||
                   (seeded && decision_seed % 2);
    std::array<int, 4> order = reverse ? std::array<int, 4>{2, 3, 0, 1}
                                      : std::array<int, 4>{0, 1, 2, 3};
    int count = first_pair_only ? 2 : 4;
    for (int position = 0; position < count; ++position) {
      int row = order[position];
      for (int j = 0; j < n; ++j) {
        int bit;
        if (seeded) {
          int spread = decision_mode == "seededspread" ? row * (n / 4) : 0;
          int start = (decision_seed * 17 + row * 29 + spread) % n;
          int step = 1 + (decision_seed * 13 + row * 7) % (n - 1);
          bit = (start + step * j) % n;
        } else {
          bit = ((offset ? row * (n / 4) : 0) +
                 (stride ? 13 : 1) * j) % n;
        }
        int var = rows[row][bit];
        if (!assignment[var]) return positive ? var : -var;
      }
    }
    return 0;
  }
  bool cb_has_external_clause(bool &forgettable) override {
    if (decision_mode == "off") return false;
    if (clauses.empty()) {
      if (add_leaf_checks()) { forgettable = false; return true; }
      add_for_pair(0); add_for_pair(1);
      if (full(4) && !full(5)) add_early_target(4);
      if (full(5) && !full(4)) add_early_target(5);
      add_final_check();
    }
    forgettable = false;
    return !clauses.empty();
  }
  int cb_add_external_clause_lit() override {
    auto &front = clauses.front();
    if (clause_position < front.size()) {
      ++external_literals;
      return front[clause_position++];
    }
    clauses.pop_front(); clause_position = 0; ++clauses_sent;
    return 0;
  }
};

static std::vector<std::vector<int>> read_mapping(const std::string &path, int &n) {
  std::ifstream input(path);
  need(bool(input), "cannot open mapping");
  input >> n;
  std::vector<std::vector<int>> rows(6, std::vector<int>(n));
  for (auto &row : rows) for (int &var : row) input >> var;
  need(bool(input), "incomplete mapping");
  return rows;
}

static int read_cnf(CaDiCaL::Solver &solver, const std::string &path) {
  std::ifstream input(path);
  need(bool(input), "cannot open CNF");
  std::string word;
  int variables = 0, clauses = 0, actual = 0;
  while (input >> word) {
    if (word == "c") { std::getline(input, word); continue; }
    if (word == "p") { input >> word >> variables >> clauses; need(word == "cnf", "not CNF"); continue; }
    int lit = std::stoi(word);
    solver.add(lit);
    if (!lit) ++actual;
  }
  need(actual == clauses && variables > 0, "CNF header mismatch");
  return variables;
}

int main(int argc, char **argv) {
  try {
    need(argc == 15, "usage: insearch CNF MAP TARGETS_OR_MINUS MODULE_DIR FIELD_DIR BRANCH_POLICY DECISION_SEED ROOT_ENCODING EARLY_MODE EARLY_LIMIT LEAF_MODE WEIGHT_BOUND CONFLICT_CAP WALL_SECONDS");
    int n = 0;
    auto rows = read_mapping(argv[2], n);
    CaDiCaL::Solver solver;
    solver.set("quiet", 1);
    int variables = read_cnf(solver, argv[1]);
    auto targets = read_targets(argv[3], n);
    RootOracle oracle(argv[4], argv[5], n);
    PairPropagator propagator(n, rows, variables, oracle, solver, argv[6],
                              std::stoi(argv[7]), argv[8],
                              std::stoi(argv[12]), argv[9],
                              std::stoi(argv[10]), argv[11],
                              std::move(targets));
    need(std::string(argv[6]) == "off" || std::string(argv[6]) == "none" ||
         std::string(argv[6]) == "first" || std::string(argv[6]) == "all" ||
         std::string(argv[6]) == "firstpos" || std::string(argv[6]) == "allpos" ||
         std::string(argv[6]) == "firstspread" || std::string(argv[6]) == "allspread" ||
         std::string(argv[6]) == "alloffset" || std::string(argv[6]) == "allstride" ||
         std::string(argv[6]) == "pair1pos" || std::string(argv[6]) == "pair1spread" ||
         std::string(argv[6]) == "seededpos" || std::string(argv[6]) == "seededspread",
         "bad decision mode");
    solver.connect_external_propagator(&propagator);
    for (const auto &row : propagator.mapping())
      for (int var : row) solver.add_observed_var(var);
    for (int var : propagator.selector_vars()) solver.add_observed_var(var);
    int cap = std::stoi(argv[13]);
    need(cap > 0 && solver.limit("conflicts", cap), "invalid conflict cap");
    int wall_cap = std::stoi(argv[14]);
    need(wall_cap > 0, "invalid wall cap");
    std::atomic<bool> done(false), wall_hit(false);
    std::thread watchdog([&] {
      auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(wall_cap);
      while (!done && std::chrono::steady_clock::now() < deadline)
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
      if (!done) { wall_hit = true; solver.terminate(); }
    });
    auto started = std::chrono::steady_clock::now();
    std::clock_t cpu_started = std::clock();
    int status = solver.solve();
    auto finished = std::chrono::steady_clock::now();
    double cpu_seconds = double(std::clock() - cpu_started) / CLOCKS_PER_SEC;
    done = true;
    watchdog.join();
    double seconds = std::chrono::duration<double>(finished - started).count();
    struct rusage usage{};
    getrusage(RUSAGE_SELF, &usage);
    std::cout << "{\"status\":" << status << ",\"seconds\":" << seconds
              << ",\"cpu_seconds\":" << cpu_seconds
              << ",\"wall_cap_hit\":" << (wall_hit ? "true" : "false")
              << ",\"conflicts\":" << solver.get_statistic_value("conflicts")
              << ",\"propagations\":" << solver.get_statistic_value("propagations")
              << ",\"solver_decisions\":" << solver.get_statistic_value("decisions")
              << ",\"peak_rss_raw\":" << usage.ru_maxrss
              << ",\"root_queries\":" << propagator.root_queries
              << ",\"empty_root_pairs\":" << propagator.empty_root_pairs
              << ",\"external_clauses\":" << propagator.clauses_sent
              << ",\"external_literals\":" << propagator.external_literals
              << ",\"guard_vars\":" << propagator.guard_vars
              << ",\"guard_literals_total\":" << propagator.guard_literals_total
              << ",\"saturated_leaves_seen\":" << propagator.saturated_leaves_seen
              << ",\"final_link_checks\":" << propagator.final_link_checks
              << ",\"final_link_matches\":" << propagator.final_link_matches
              << ",\"final_link_rejections\":" << propagator.final_link_rejections
              << ",\"early_queries\":" << propagator.early_queries
              << ",\"early_zero_root\":" << propagator.early_zero_root
              << ",\"early_roots_total\":" << propagator.early_roots_total
              << ",\"early_roots_max\":" << propagator.early_roots_max
              << ",\"early_selector_vars\":" << propagator.early_selector_vars
              << ",\"early_consensus_bits\":" << propagator.early_consensus_bits
              << ",\"early_skipped_limit\":" << propagator.early_skipped_limit
              << ",\"early_reverse_queries\":" << propagator.early_reverse_queries
              << ",\"early_state_samples_truncated\":"
              << propagator.early_state_samples_truncated
              << ",\"leaf_rationality_checks\":" << propagator.leaf_rationality_checks
              << ",\"leaf_nonrational_rejections\":" << propagator.leaf_nonrational_rejections
              << ",\"leaf_saturated_rejections\":" << propagator.leaf_saturated_rejections
              << ",\"leaf_guard_literals\":" << propagator.leaf_guard_literals
              << ",\"leaf_eager_checks\":" << propagator.leaf_eager_checks
              << ",\"leaf_eager_rejections\":" << propagator.leaf_eager_rejections
              << ",\"decision_seed\":" << std::stoi(argv[7])
              << ",\"field_api_calls\":" << oracle.field_api_counts_json()
              << ",\"decision_calls\":" << propagator.decision_calls
              << ",\"model_checks\":" << propagator.model_checks
              << ",\"early_zero_samples\":[";
    for (size_t i = 0; i < propagator.zero_samples().size(); ++i) {
      if (i) std::cout << ',';
      std::cout << '"' << propagator.zero_samples()[i] << '"';
    }
    std::cout << "],\"early_state_samples\":[";
    for (size_t i = 0; i < propagator.early_states().size(); ++i) {
      if (i) std::cout << ',';
      const auto &sample = propagator.early_states()[i];
      std::cout << "{\"row\":" << sample.first << ",\"x_bits\":\""
                << sample.second << "\"}";
    }
    std::cout << "],\"leaf_rejection_samples\":[";
    for (size_t i = 0; i < propagator.rejected_leaves().size(); ++i) {
      if (i) std::cout << ',';
      const auto &sample = propagator.rejected_leaves()[i];
      std::cout << "{\"row\":" << sample.first << ",\"x_bits\":\""
                << sample.second << "\"}";
    }
    std::cout << "]}" << std::endl;
    if (status == 10) {
      std::cout << "v";
      for (const auto &row : propagator.mapping())
        for (int var : row) std::cout << ' ' << solver.val(var);
      std::cout << " 0\n";
    }
    solver.disconnect_external_propagator();
    return status == 10 ? 10 : status == 20 ? 20 : 0;
  } catch (const std::exception &error) {
    std::cerr << error.what() << '\n';
    return 2;
  }
}
