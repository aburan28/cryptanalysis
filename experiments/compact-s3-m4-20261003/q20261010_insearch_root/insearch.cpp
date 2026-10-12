// CaDiCaL external clauses for exact roots of the two leaf-pair S3 links.
// Build with build.sh; the original S3 CNF remains in the input formula.
#include <Python.h>
#include <cadical.hpp>
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdlib>
#include <deque>
#include <fstream>
#include <iostream>
#include <set>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

static void need(bool value, const char *message) {
  if (!value) throw std::runtime_error(message);
}

class RootOracle {
  PyObject *onb = nullptr;
  PyObject *from_coords = nullptr;
  PyObject *to_coords = nullptr;
  PyObject *roots = nullptr;

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
    Py_DECREF(field); Py_DECREF(oracle); Py_DECREF(klass); Py_DECREF(degree);
    if (!onb || !from_coords || !to_coords || !roots) {
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

  ~RootOracle() {
    Py_XDECREF(onb); Py_XDECREF(from_coords); Py_XDECREF(to_coords);
    Py_XDECREF(roots); Py_Finalize();
  }
};

class PairPropagator : public CaDiCaL::ExternalPropagator {
  int n;
  std::vector<std::vector<int>> rows;
  std::vector<int> selectors;
  std::vector<int8_t> assignment;
  std::vector<std::vector<int>> trail{1};
  std::set<std::string> seen;
  std::deque<std::vector<int>> clauses;
  size_t clause_position = 0;
  RootOracle &oracle;
  std::string decision_mode;

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
  std::vector<int> guard(int pair) const {
    std::vector<int> result;
    for (int row : {2 * pair, 2 * pair + 1})
      for (int var : rows[row]) result.push_back(-assignment[var] * var);
    return result;
  }
  void add_for_pair(int pair) {
    if (!full(2 * pair) || !full(2 * pair + 1)) return;
    std::string a = coordinate(2 * pair), b = coordinate(2 * pair + 1);
    if (a.find('1') == std::string::npos || b.find('1') == std::string::npos) return;
    std::string key = std::to_string(pair) + ":" + a + ":" + b;
    if (!seen.insert(key).second) return;
    auto candidate_roots = oracle.query(a, b);
    ++root_queries;
    std::vector<int> prefix = guard(pair);
    if (candidate_roots.empty()) {
      clauses.push_back(prefix);
      ++empty_root_pairs;
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

public:
  uint64_t root_queries = 0, empty_root_pairs = 0, decision_calls = 0;
  uint64_t clauses_sent = 0, model_checks = 0;
  PairPropagator(int degree, std::vector<std::vector<int>> mapping,
                 int max_var, RootOracle &root_oracle, std::string mode)
      : n(degree), rows(std::move(mapping)), selectors{max_var + 1, max_var + 2},
        assignment(max_var + 3, 0), oracle(root_oracle), decision_mode(std::move(mode)) {
    need(rows.size() == 6, "mapping needs four leaves and two middle rows");
    for (const auto &row : rows) need(row.size() == size_t(n), "bad mapping row");
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
    int count = decision_mode == "first" ? 2 : 4;
    for (int row = 0; row < count; ++row)
      for (int var : rows[row]) if (!assignment[var]) return -var;
    return 0;
  }
  bool cb_has_external_clause(bool &forgettable) override {
    if (decision_mode == "off") return false;
    if (clauses.empty()) {
      add_for_pair(0); add_for_pair(1);
    }
    forgettable = false;
    return !clauses.empty();
  }
  int cb_add_external_clause_lit() override {
    auto &front = clauses.front();
    if (clause_position < front.size()) return front[clause_position++];
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
    need(argc == 8, "usage: insearch CNF MAP MODULE_DIR FIELD_DIR {off|none|first|all} CONFLICT_CAP WALL_SECONDS");
    int n = 0;
    auto rows = read_mapping(argv[2], n);
    CaDiCaL::Solver solver;
    solver.set("quiet", 1);
    int variables = read_cnf(solver, argv[1]);
    RootOracle oracle(argv[3], argv[4], n);
    PairPropagator propagator(n, rows, variables, oracle, argv[5]);
    need(std::string(argv[5]) == "off" || std::string(argv[5]) == "none" || std::string(argv[5]) == "first" ||
         std::string(argv[5]) == "all", "bad decision mode");
    solver.connect_external_propagator(&propagator);
    for (const auto &row : propagator.mapping())
      for (int var : row) solver.add_observed_var(var);
    for (int var : propagator.selector_vars()) solver.add_observed_var(var);
    int cap = std::stoi(argv[6]);
    need(cap > 0 && solver.limit("conflicts", cap), "invalid conflict cap");
    int wall_cap = std::stoi(argv[7]);
    need(wall_cap > 0, "invalid wall cap");
    std::atomic<bool> done(false);
    std::thread watchdog([&] {
      auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(wall_cap);
      while (!done && std::chrono::steady_clock::now() < deadline)
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
      if (!done) solver.terminate();
    });
    auto started = std::chrono::steady_clock::now();
    int status = solver.solve();
    done = true;
    watchdog.join();
    double seconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - started).count();
    std::cout << "{\"status\":" << status << ",\"seconds\":" << seconds
              << ",\"conflicts\":" << solver.get_statistic_value("conflicts")
              << ",\"root_queries\":" << propagator.root_queries
              << ",\"empty_root_pairs\":" << propagator.empty_root_pairs
              << ",\"external_clauses\":" << propagator.clauses_sent
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
