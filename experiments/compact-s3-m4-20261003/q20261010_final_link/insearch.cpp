// Q1432: exact final S3 target-coset check after both middle values are fixed.
// The original S3 CNF remains in the input formula.
#include <Python.h>
#include <cadical.hpp>
#include <algorithm>
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
    for (const auto &dir : {module_dir, field_dir}) {
      PyObject *item = PyUnicode_FromString(dir.c_str());
      need(item && PyList_Insert(path, 0, item) == 0, "cannot set Python path");
      Py_DECREF(item);
    }
    PyObject *field = PyImport_ImportModule("field");
    PyObject *oracle = PyImport_ImportModule("s3_root_oracle");
    if (!field || !oracle) { PyErr_Print(); throw std::runtime_error("oracle import failed"); }
    PyObject *klass = PyObject_GetAttrString(field, "Onb");
    PyObject *degree = PyLong_FromLong(n);
    onb = PyObject_CallFunctionObjArgs(klass, degree, nullptr);
    from_coords = PyObject_GetAttrString(onb, "fromCoords");
    to_coords = PyObject_GetAttrString(onb, "toCoords");
    roots = PyObject_GetAttrString(oracle, "s3_roots");
    PyObject *chain = PyImport_ImportModule("chain_s3");
    evaluate = chain ? PyObject_GetAttrString(chain, "evaluate_s3") : nullptr;
    Py_XDECREF(chain);
    Py_DECREF(field); Py_DECREF(oracle); Py_DECREF(klass); Py_DECREF(degree);
    if (!onb || !from_coords || !to_coords || !roots || !evaluate) {
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

  ~RootOracle() {
    Py_XDECREF(onb); Py_XDECREF(from_coords); Py_XDECREF(to_coords);
    Py_XDECREF(roots); Py_XDECREF(evaluate); Py_Finalize();
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
  std::set<std::string> target_coset;
  std::deque<std::vector<int>> clauses;
  size_t clause_position = 0;
  RootOracle &oracle;
  CaDiCaL::Solver &solver;
  std::string decision_mode;
  std::string encoding;

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

public:
  uint64_t root_queries = 0, empty_root_pairs = 0, decision_calls = 0;
  uint64_t clauses_sent = 0, model_checks = 0, external_literals = 0;
  uint64_t guard_vars = 0, guard_literals_total = 0;
  uint64_t saturated_leaves_seen = 0;
  uint64_t final_link_checks = 0, final_link_matches = 0, final_link_rejections = 0;
  PairPropagator(int degree, std::vector<std::vector<int>> mapping,
                 int max_var, RootOracle &root_oracle, CaDiCaL::Solver &sat,
                 std::string mode, std::string root_encoding, int max_weight,
                 std::set<std::string> targets)
      : n(degree), weight_bound(max_weight), rows(std::move(mapping)),
        selectors{max_var + 1, max_var + 2},
        assignment(max_var + 3, 0), oracle(root_oracle), solver(sat),
        decision_mode(std::move(mode)), encoding(std::move(root_encoding)),
        target_coset(std::move(targets)) {
    need(rows.size() == 6, "mapping needs four leaves and two middle rows");
    for (const auto &row : rows) need(row.size() == size_t(n), "bad mapping row");
    need(weight_bound > 0 && weight_bound <= n, "bad weight bound");
    need(encoding == "legacy" || encoding == "shared" || encoding == "pivot" ||
         encoding == "satpivot" || encoding == "satlegacy",
         "bad root encoding");
  }
  const std::vector<std::vector<int>> &mapping() const { return rows; }
  const std::vector<int> &selector_vars() const { return selectors; }
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
                    decision_mode == "alloffset" || decision_mode == "allstride";
    bool offset = decision_mode == "firstspread" || decision_mode == "allspread" ||
                  decision_mode == "alloffset";
    bool stride = decision_mode == "firstspread" || decision_mode == "allspread" ||
                  decision_mode == "allstride";
    int count = first_pair_only ? 2 : 4;
    for (int row = 0; row < count; ++row)
      for (int j = 0; j < n; ++j) {
        int bit = ((offset ? row * (n / 4) : 0) + (stride ? 13 : 1) * j) % n;
        int var = rows[row][bit];
        if (!assignment[var]) return positive ? var : -var;
      }
    return 0;
  }
  bool cb_has_external_clause(bool &forgettable) override {
    if (decision_mode == "off") return false;
    if (clauses.empty()) {
      add_for_pair(0); add_for_pair(1);
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
    need(argc == 11, "usage: insearch CNF MAP TARGETS_OR_MINUS MODULE_DIR FIELD_DIR BRANCH_POLICY ROOT_ENCODING WEIGHT_BOUND CONFLICT_CAP WALL_SECONDS");
    int n = 0;
    auto rows = read_mapping(argv[2], n);
    CaDiCaL::Solver solver;
    solver.set("quiet", 1);
    int variables = read_cnf(solver, argv[1]);
    auto targets = read_targets(argv[3], n);
    RootOracle oracle(argv[4], argv[5], n);
    PairPropagator propagator(n, rows, variables, oracle, solver, argv[6],
                              argv[7], std::stoi(argv[8]), std::move(targets));
    need(std::string(argv[6]) == "off" || std::string(argv[6]) == "none" ||
         std::string(argv[6]) == "first" || std::string(argv[6]) == "all" ||
         std::string(argv[6]) == "firstpos" || std::string(argv[6]) == "allpos" ||
         std::string(argv[6]) == "firstspread" || std::string(argv[6]) == "allspread" ||
         std::string(argv[6]) == "alloffset" || std::string(argv[6]) == "allstride",
         "bad decision mode");
    solver.connect_external_propagator(&propagator);
    for (const auto &row : propagator.mapping())
      for (int var : row) solver.add_observed_var(var);
    for (int var : propagator.selector_vars()) solver.add_observed_var(var);
    int cap = std::stoi(argv[9]);
    need(cap > 0 && solver.limit("conflicts", cap), "invalid conflict cap");
    int wall_cap = std::stoi(argv[10]);
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
              << ",\"decision_calls\":" << propagator.decision_calls
              << ",\"model_checks\":" << propagator.model_checks << "}" << std::endl;
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
