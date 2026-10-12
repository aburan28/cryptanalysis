// Conditional quadratic lifting. A low-degree residual is solved exactly;
// large lifted nullspaces use original-variable enumeration, never truncation.
#include "../round49/abi.h"

static_assert(sizeof(BranchStats) > 0);

#include "../round27/interpolation.hpp"
#include <array>
#include <chrono>
#include <mutex>
#include <stdexcept>
#include <string>
#include <variant>
#include <vector>
#ifdef QUADRATIC_METAL
#include "../round49/metal_backend.h"
#endif

namespace {
// Input extents are validated before narrowing. Certificates keep uint64 limbs.
template <typename T> struct NarrowWord {
  T value = 0;
  NarrowWord() = default;
  NarrowWord(uint64_t lo, uint64_t) : value(static_cast<T>(lo)) {}
  NarrowWord &operator^=(const NarrowWord &b) {
    value ^= b.value;
    return *this;
  }
  bool nonzero() const { return value != 0; }
  int pivot() const { return 63 - __builtin_clzll(value); }
  unsigned parity(const NarrowWord &b) const {
    return __builtin_parityll(value & b.value);
  }
  void toggle(uint32_t bit) { value ^= T{1} << bit; }
  uint64_t low() const { return value; }
  uint64_t high() const { return 0; }
};
struct WideWord {
  uint64_t lo = 0, hi = 0;
  WideWord &operator^=(const WideWord &b) {
    lo ^= b.lo;
    hi ^= b.hi;
    return *this;
  }
  bool nonzero() const { return lo || hi; }
  int pivot() const {
    return hi ? 127 - __builtin_clzll(hi) : 63 - __builtin_clzll(lo);
  }
  unsigned parity(const WideWord &b) const {
    return __builtin_parityll(lo & b.lo) ^ __builtin_parityll(hi & b.hi);
  }
  void toggle(uint32_t bit) {
    if (bit < 64)
      lo ^= UINT64_C(1) << bit;
    else
      hi ^= UINT64_C(1) << (bit - 64);
  }
  uint64_t low() const { return lo; }
  uint64_t high() const { return hi; }
};
using Word32 = NarrowWord<uint32_t>;
using Word64 = NarrowWord<uint64_t>;
static_assert(sizeof(Word32) == 4 && sizeof(Word64) == 8 &&
              sizeof(WideWord) == 16);
static uint32_t word_bytes(uint32_t equations) {
  return equations <= 32 ? 4 : equations <= 64 ? 8 : 16;
}
// Explicit quotient metadata; generic producers have no enabled layout.
struct NormalizationLayout {
  bool enabled = false;
  uint32_t n = 0, modulus = 0, count = 0, top = 0;
  std::array<uint32_t, 32> annihilator{};
  std::array<std::array<uint32_t, 16>, 8> inverse_six{};
  std::array<uint8_t, 56> left_exponent{}, right_exponent{};
  std::vector<std::array<std::array<uint32_t, 16>, 8>> transport;
};
static uint32_t normalization_xtime(uint32_t a, uint32_t n, uint32_t modulus) {
  return (a << 1) ^ ((a >> (n - 1)) ? modulus : 0);
}
template <class Charge>
static bool normalization_multiply(uint32_t a, uint32_t b, uint32_t n,
                                   uint32_t modulus, uint32_t &result,
                                   Charge &charge) {
  result = 0;
  while (b) {
    if (!charge())
      return false;
    if (b & 1)
      result ^= a;
    b >>= 1;
    a = normalization_xtime(a, n, modulus);
  }
  return true;
}
template <class Charge>
static bool normalization_inverse(uint32_t a, uint32_t n, uint32_t modulus,
                                  uint32_t &result, Charge &charge) {
  uint64_t u = a, v = modulus, g1 = 1, g2 = 0;
  while (u != 1) {
    if (!u || !v)
      return false;
    if (!charge())
      return false;
    int shift = int(63 - __builtin_clzll(u)) - int(63 - __builtin_clzll(v));
    if (shift < 0) {
      std::swap(u, v);
      std::swap(g1, g2);
      shift = -shift;
    }
    if (shift >= 64 || g2 > (UINT64_MAX >> shift))
      return false;
    u ^= v << shift;
    g1 ^= g2 << shift;
  }
  while (g1 >> n) {
    if (!charge())
      return false;
    const unsigned shift = unsigned(63 - __builtin_clzll(g1)) - n;
    g1 ^= uint64_t(modulus) << shift;
  }
  result = uint32_t(g1);
  return true;
}

struct Producer {
  bool partial_enabled = true;
  bool gpu_projection_enabled = true;
  const uint64_t *gpu_projection = nullptr;
  NormalizationLayout normalization{};
  uint32_t nx, ny, equations, limbs, features, branches;
  std::variant<std::vector<Word32>, std::vector<Word64>, std::vector<WideWord>>
      values;
  std::vector<uint32_t> monomials, feature_index;
  // Invariant Boolean product layout. Pivot flags are reset for every
  // branch; an active pivot always belongs to this fresh specialization.
  std::vector<uint32_t> cubic_index, product_index;
  std::vector<uint64_t> multiplier_pivots;
  std::vector<uint64_t> multiplier_dependencies;
  std::vector<uint32_t> multiplier_sources;
  std::vector<unsigned char> multiplier_active;
  uint32_t cubic_columns = 0, row_words = 0, proof_words = 0;
  std::vector<uint32_t> affine_offsets, root_offsets;
  std::mutex mutex;
#ifdef QUADRATIC_METAL
  void *metal = nullptr;
  ~Producer() {
    if (metal)
      compact_metal_destroy(metal);
  }
#endif
  Producer(uint32_t x, uint32_t y, uint32_t e)
      : nx(x), ny(y), equations(e), limbs((e + 63) / 64),
        features(y + y * (y - 1) / 2), branches(1u << x),
        feature_index(1u << y, UINT32_MAX) {
    const size_t words = size_t(branches) * (features + 1);
    if (e <= 32)
      values = std::vector<Word32>(words);
    else if (e <= 64)
      values = std::vector<Word64>(words);
    else
      values = std::vector<WideWord>(words);
    monomials.push_back(0);
    feature_index[0] = 0;
    for (uint32_t j = 0; j < y; ++j)
      monomials.push_back(1u << j);
    for (uint32_t j = 0; j < y; ++j)
      for (uint32_t k = j + 1; k < y; ++k)
        monomials.push_back((1u << j) | (1u << k));
    for (uint32_t j = 1; j < monomials.size(); ++j)
      feature_index[monomials[j]] = j;
    cubic_index.resize(1u << y, UINT32_MAX);
    for (uint32_t m = 0; m < (1u << y); ++m)
      if (__builtin_popcount(m) <= 3)
        cubic_index[m] = cubic_columns++;
    row_words = (cubic_columns + 63) / 64;
    proof_words = (y + 1) * limbs;
    product_index.resize(size_t(y + 1) * monomials.size());
    for (uint32_t slot = 0; slot <= y; ++slot)
      for (uint32_t j = 0; j < monomials.size(); ++j)
        product_index[size_t(slot) * monomials.size() + j] =
            cubic_index[monomials[j] | (slot ? (1u << (slot - 1)) : 0)];
    if (x % 2 == 0) {
      affine_offsets.resize(branches, UINT32_MAX);
      root_offsets.resize(size_t(branches) + 1);
    }
    multiplier_active.resize(cubic_columns);
    multiplier_pivots.resize(size_t(cubic_columns) * row_words);
    multiplier_dependencies.resize(size_t(cubic_columns) * row_words);
    multiplier_sources.resize(cubic_columns);
#ifdef QUADRATIC_METAL
    if (features <= 55 && equations <= 32)
      metal = compact_metal_create(branches, features, equations, ny);
#endif
  }
};
struct ProjectionStats {
  uint64_t attempts = 0;
  uint64_t certified_branches = 0;
  uint64_t rank_fallbacks = 0;
  uint64_t satisfying_fallbacks = 0;
  uint64_t budget_skips = 0;
  uint64_t input_rows = 0;
  uint64_t row_xors = 0;
  uint64_t word_xors = 0;
  uint64_t certificate_xors = 0;
  uint64_t work = 0;
  uint64_t stack_bytes = 0;
  double seconds = 0;
};
struct NormalizationStats {
  uint64_t attempts = 0;
  uint64_t prepared = 0;
  uint64_t zero_scalars = 0;
  uint64_t mismatches = 0;
  uint64_t nonunits = 0;
  uint64_t budget_skips = 0;
  uint64_t field_steps = 0;
  uint64_t guard_columns = 0;
  uint64_t inverse_steps = 0;
  uint64_t transpose_parities = 0;
  uint64_t transport_lookups = 0;
  uint64_t affine_parities = 0;
  uint64_t work = 0;
  uint64_t stack_bytes = 0;
  uint64_t workspace_bytes = 0;
  double seconds = 0;
};
struct Produced {
  GPUProjectionStats gpu_projection{};
  PartialProduceStats partial{};
  NormalizationStats normalization{};
  ProjectionStats projection{};
  DeferredStats deferred{};
  SymmetryStats symmetry{};
  BranchStats stats{};
  MultiplierStats multipliers{};
  std::vector<Mask> roots;
  std::vector<Polynomial> basis;
  // Prefix: one constant equation-combination witness per branch.
  // Sparse tail: ascending records [branch, u_0 limbs, u_1 limbs, ..., u_y
  // limbs]. A branch with neither proof still requires complete residual
  // enumeration.
  std::vector<uint64_t> contradictions;
};
static thread_local std::string error_text;
static thread_local uint32_t error_code;
static thread_local MultiplierStats failed_multiplier_stats{};
static thread_local ProjectionStats failed_projection_stats{};
static thread_local NormalizationStats failed_normalization_stats{};
static thread_local SymmetryStats failed_symmetry_stats{};
static thread_local DeferredStats failed_deferred_stats{};
static thread_local PartialProduceStats failed_partial_stats{};
static thread_local GPUProjectionStats failed_gpu_projection_stats{};
struct TimedPhase {
  double &seconds;
  std::chrono::steady_clock::time_point start =
      std::chrono::steady_clock::now();
  explicit TimedPhase(double &value) : seconds(value) {}
  ~TimedPhase() {
    seconds +=
        std::chrono::duration<double>(std::chrono::steady_clock::now() - start)
            .count();
  }
};
static uint32_t swapped(const Producer &w, uint32_t branch) {
  const uint32_t bits = w.nx / 2, mask = (1u << bits) - 1;
  return ((branch & mask) << bits) | (branch >> bits);
}
static bool reserve_proof(Produced &out, uint64_t entry) {
  if (entry > MULTIPLIER_PROOF_WORDS_LIMIT - out.contradictions.size())
    return false;
  const size_t required = out.contradictions.size() + entry;
  if (required > out.contradictions.capacity()) {
    const size_t previous = out.contradictions.capacity();
    out.contradictions.reserve(std::min<size_t>(
        MULTIPLIER_PROOF_WORDS_LIMIT, std::max(required, 2 * previous)));
    out.stats.workspace_bytes += (out.contradictions.capacity() - previous) * 8;
  }
  return true;
}
static void dimensions(uint32_t x, uint32_t y, uint32_t e) {
  if (!x || x > 20 || !y || y > 10 || x + y > 30 || !e || e > 128)
    throw std::invalid_argument(
        "dimensions: x 1..20, y 1..10, x+y<=30, equations 1..128");
  const uint64_t bytes =
      (UINT64_C(1) << x) * (1 + y + y * (y - 1) / 2) * word_bytes(e);
  if (bytes > TABLE_BYTES_LIMIT)
    throw std::length_error("specialization table exceeds 64 MiB");
}
static uint64_t mask_at(const void *masks, uint32_t width, uint32_t i) {
  return width == 32 ? static_cast<const uint32_t *>(masks)[i]
                     : static_cast<const uint64_t *>(masks)[i];
}
enum class NormalizationResult { Disabled, Ready, Mismatch, Budget };

template <typename Word, class Charge>
static NormalizationResult normalization_rows(Producer &w, const Word *columns,
                                              std::array<uint64_t, 128> &rows,
                                              std::array<Word, 128> &witnesses,
                                              uint32_t &row_count,
                                              Produced &out, Charge &charge) {
  const auto &layout = w.normalization;
  if (!layout.enabled)
    return NormalizationResult::Disabled;
  auto &stats = out.normalization;
  TimedPhase timer(stats.seconds);
  ++stats.attempts;
  bool exhausted = false;
  auto spend = [&]() {
    if (!charge()) {
      ++stats.budget_skips;
      exhausted = true;
      return false;
    }
    ++stats.work; // Included in projection.work, never counted twice.
    return true;
  };
  uint32_t alpha = 0, packed = uint32_t(columns[w.ny + 1].low());
  for (uint32_t nibble = 0; nibble < (layout.n + 3) / 4; ++nibble) {
    if (!spend())
      return NormalizationResult::Budget;
    alpha ^= layout.inverse_six[nibble][(packed >> (4 * nibble)) & 15];
  }
  std::array<uint32_t, 56> powers{};
  stats.stack_bytes = sizeof(powers);
  powers[0] = alpha;
  for (uint32_t i = 1; i <= layout.top; ++i) {
    if (!spend())
      return NormalizationResult::Budget;
    powers[i] = normalization_xtime(powers[i - 1], layout.n, layout.modulus);
    ++stats.field_steps;
  }
  // Every quadratic column is checked before any normalized consequence is
  // used.
  for (uint32_t feature = w.ny + 1; feature <= w.features; ++feature) {
    if (!spend())
      return NormalizationResult::Budget;
    ++stats.guard_columns;
    if (columns[feature].low() != (powers[layout.left_exponent[feature]] ^
                                   powers[layout.right_exponent[feature]])) {
      ++stats.mismatches;
      return NormalizationResult::Mismatch;
    }
  }
  if (!alpha) {
    ++stats.zero_scalars;
    row_count = w.equations;
    for (uint32_t e = 0; e < row_count; ++e) {
      witnesses[e].toggle(e);
      for (uint32_t feature = 0; feature <= w.ny; ++feature) {
        if (!spend())
          return NormalizationResult::Budget;
        ++stats.affine_parities;
        rows[e] |= ((columns[feature].low() >> e) & 1) << feature;
      }
    }
    ++stats.prepared;
    return NormalizationResult::Ready;
  }
  auto inverse_charge = [&]() {
    if (!spend())
      return false;
    ++stats.inverse_steps;
    return true;
  };
  uint32_t inverse = 0;
  if (!normalization_inverse(alpha, layout.n, layout.modulus, inverse,
                             inverse_charge)) {
    if (exhausted)
      return NormalizationResult::Budget;
    ++stats.nonunits;
    return NormalizationResult::Mismatch;
  }
  auto field_charge = [&]() {
    if (!spend())
      return false;
    ++stats.field_steps;
    return true;
  };
  uint32_t product = 0;
  if (!normalization_multiply(alpha, inverse, layout.n, layout.modulus, product,
                              field_charge))
    return NormalizationResult::Budget;
  if (product != 1) {
    ++stats.nonunits;
    return NormalizationResult::Mismatch;
  }
  row_count = layout.count;
  for (uint32_t row = 0; row < row_count; ++row) {
    uint32_t witness = 0;
    for (uint32_t nibble = 0; nibble < (layout.n + 3) / 4; ++nibble) {
      if (!spend())
        return NormalizationResult::Budget;
      ++stats.transport_lookups;
      witness ^= layout.transport[row][nibble][(inverse >> (4 * nibble)) & 15];
    }
    witnesses[row] = Word{witness, 0};
    for (uint32_t feature = 0; feature <= w.ny; ++feature) {
      if (!spend())
        return NormalizationResult::Budget;
      ++stats.affine_parities;
      rows[row] |=
          uint64_t(__builtin_parity(witness & uint32_t(columns[feature].low())))
          << feature;
    }
  }
  ++stats.prepared;
  return NormalizationResult::Ready;
}

enum class BranchResolution { None, Contradiction, Partial };

// Consume the fresh reduced affine rows already computed by the projection.
// Stage roots locally: an abandoned attempt cannot leak a partial root list.
template <typename Word, class Charge>
static BranchResolution
partial_resolution(Producer &w, const Word *columns, uint32_t branch,
                   Produced &out, const std::array<uint64_t, 128> &rows,
                   const std::array<Word, 128> &witnesses, uint32_t first,
                   uint32_t rank, Charge &charge) {
  auto &stats = out.partial;
  TimedPhase timing(stats.seconds);
  ++stats.attempts;
  stats.rank_sum += rank;
  std::array<uint32_t, 10> pivots{}, free_columns{};
  std::array<uint32_t, 1024> roots{};
  stats.stack_bytes = sizeof(pivots) + sizeof(free_columns) + sizeof(roots);
  auto spend = [&]() {
    if (charge())
      return true;
    ++stats.budget_skips;
    return false;
  };
  uint32_t pivot_mask = 0;
  for (uint32_t i = 0; i < rank; ++i) {
    if (!spend())
      return BranchResolution::None;
    const uint64_t variables = rows[first + i] >> 1;
    if (!variables || variables >> w.ny)
      throw std::runtime_error("partial projection is not affine");
    const uint32_t column = uint32_t(__builtin_ctzll(variables));
    if (pivot_mask & (1u << column))
      throw std::runtime_error("duplicate partial projection pivot");
    pivots[i] = column;
    pivot_mask |= 1u << column;
  }
  for (uint32_t i = 0; i < rank; ++i)
    if (((rows[first + i] >> 1) & pivot_mask) != (1u << pivots[i]))
      throw std::runtime_error("partial projection is not reduced");
  uint32_t free_count = 0;
  for (uint32_t column = 0; column < w.ny; ++column)
    if (!(pivot_mask & (1u << column)))
      free_columns[free_count++] = column;
  uint32_t found = 0;
  for (uint32_t bits = 0; bits < (1u << free_count); ++bits) {
    if (out.stats.lifted_candidates + out.stats.fallback_assignments +
            stats.assignments >=
        ENUMERATION_BUDGET)
      throw std::length_error(
          "complete query assignment budget exceeded in partial search");
    if (!spend())
      return BranchResolution::None;
    ++stats.assignments;
    uint32_t assignment = 0;
    for (uint32_t i = 0; i < free_count; ++i)
      assignment |= ((bits >> i) & 1u) << free_columns[i];
    for (uint32_t i = 0; i < rank; ++i) {
      if (!spend())
        return BranchResolution::None;
      const uint64_t row = rows[first + i];
      const unsigned value =
          (row & 1u) ^ __builtin_parityll((row >> 1) & assignment);
      assignment |= value << pivots[i];
    }
    Word value{};
    for (uint32_t feature = 0; feature <= w.features; ++feature) {
      if (!spend())
        return BranchResolution::None;
      if ((assignment & w.monomials[feature]) == w.monomials[feature]) {
        value ^= columns[feature];
        stats.equation_word_xors += w.limbs;
      }
    }
    if (!value.nonzero()) {
      ++stats.roots_found;
      if (out.roots.size() + found == ROOT_LIMIT)
        throw std::length_error("complete roots exceed 256 in partial search");
      roots[found++] = assignment;
    }
  }
  const uint64_t entry = 1 + w.proof_words;
  // Charge all output words before committing any root or proof record.
  for (uint64_t i = 0; i < entry + found; ++i)
    if (!spend())
      return BranchResolution::None;
  if (!reserve_proof(out, entry)) {
    ++stats.budget_skips;
    return BranchResolution::None;
  }
  if (out.symmetry.enabled)
    w.affine_offsets[branch] = uint32_t(out.contradictions.size());
  out.contradictions.push_back(PARTIAL_AFFINE_RECORD | branch);
  for (uint32_t row = 0; row <= w.ny; ++row) {
    const Word witness = row < rank ? witnesses[first + row] : Word{};
    out.contradictions.push_back(witness.low());
    if (w.limbs == 2)
      out.contradictions.push_back(witness.high());
  }
  for (uint32_t i = 0; i < found; ++i)
    out.roots.push_back(uint64_t(branch) | (uint64_t(roots[i]) << w.nx));
  out.stats.roots = out.roots.size();
  ++stats.handled_branches;
  stats.proof_rows += rank;
  stats.proof_words += entry;
  return BranchResolution::Partial;
}

// A sufficient degree-one proof constructor. Failure always falls through to
// the existing bounded Macaulay producer and exact residual enumeration.
template <typename Word>
static BranchResolution projection_identity(Producer &w, const Word *columns,
                                            uint32_t branch, Produced &out) {
  auto &stats = out.projection;
  TimedPhase timing(stats.seconds);
  ++stats.attempts;
  uint64_t branch_work = 0;
  auto charge = [&]() {
    if (out.multipliers.rows + out.multipliers.row_xors +
                out.deferred.reconstruction_pivots + stats.work >=
            MULTIPLIER_WORK_BUDGET ||
        branch_work >= MULTIPLIER_BRANCH_BUDGET) {
      ++stats.budget_skips;
      return false;
    }
    ++branch_work;
    ++stats.work;
    return true;
  };
  const uint64_t entry = 1 + w.proof_words;
  if (entry > MULTIPLIER_PROOF_WORDS_LIMIT - out.contradictions.size()) {
    ++stats.budget_skips;
    return BranchResolution::None;
  }
  // ny<=10: constant, linear and square-free quadratic support fits 56 bits.
  // These are bounded stack arrays, reported separately from heap workspace.
  std::array<uint64_t, 128> rows{};
  std::array<Word, 128> witnesses{};
  std::array<Word, 11> proof{};
  stats.stack_bytes = sizeof(rows) + sizeof(witnesses) + sizeof(proof);
  uint32_t equations = w.equations, rank = 0, affine_start = 0;
  if (w.gpu_projection) {
    // Fresh device rows are only proof proposals. The independent checker
    // still reconstructs every coefficient from the original input ANF.
    const uint64_t *record = w.gpu_projection + size_t(branch) * (w.ny + 2);
    const uint32_t header = uint32_t(record[0]);
    rank = (header >> 8) & 255u;
    const bool inconsistent = (header >> 16) & 1u;
    if ((header & 0xfffe0000u) != 0x80000000u || rank > w.ny ||
        (header & 255u) + rank > w.equations)
      throw std::runtime_error("invalid GPU projection header");
    equations = rank + unsigned(inconsistent);
    uint32_t pivot_mask = 0;
    for (uint32_t i = 0; i < equations; ++i) {
      if (!charge())
        return BranchResolution::None;
      const uint64_t packed = record[i < rank ? i + 1 : w.ny + 1];
      rows[i] = uint32_t(packed);
      const uint32_t combination = uint32_t(packed >> 32);
      if (!combination || (w.equations < 32 && (combination >> w.equations)) ||
          rows[i] >> (w.ny + 1))
        throw std::runtime_error("invalid GPU affine row or witness extent");
      witnesses[i] = Word{combination, 0};
      if (i < rank) {
        const uint32_t variables = uint32_t(rows[i] >> 1);
        if (!variables)
          throw std::runtime_error("missing GPU affine pivot");
        const uint32_t bit = variables & -variables;
        if (bit <= pivot_mask)
          throw std::runtime_error("unordered GPU affine pivot");
        pivot_mask |= bit;
      } else if (rows[i] != 1)
        throw std::runtime_error("invalid GPU unit row");
    }
    for (uint32_t i = 0; i < rank; ++i) {
      const uint32_t variables = uint32_t(rows[i] >> 1);
      if ((variables & pivot_mask) != (variables & -variables))
        throw std::runtime_error("GPU affine rows are not reduced");
    }
    ++out.gpu_projection.consumed_branches;
    out.gpu_projection.affine_rows += equations;
    out.gpu_projection.consumed_row_xors += record[0] >> 32;
    stats.input_rows += equations;
  } else {
    const auto normalized =
        normalization_rows(w, columns, rows, witnesses, equations, out, charge);
    if (normalized == NormalizationResult::Budget)
      return BranchResolution::None;
    if (normalized == NormalizationResult::Ready) {
      stats.input_rows += equations;
    } else {
      for (uint32_t equation = 0; equation < w.equations; ++equation) {
        if (!charge())
          return BranchResolution::None;
        ++stats.input_rows;
        witnesses[equation].toggle(equation);
        for (uint32_t feature = 0; feature <= w.features; ++feature) {
          const uint64_t bits =
              equation < 64 ? columns[feature].low() : columns[feature].high();
          if ((bits >> (equation % 64)) & 1)
            rows[equation] |= UINT64_C(1) << feature;
        }
      }
    }
    auto row_xor = [&](uint32_t target, uint32_t source) {
      if (!charge())
        return false;
      rows[target] ^= rows[source];
      witnesses[target] ^= witnesses[source];
      ++stats.row_xors;
      stats.word_xors += 1 + w.limbs;
      return true;
    };
    // Forward elimination suffices to extract all combinations with zero
    // quadratic part. Earlier rows are not needed for the affine subsystem.
    if (normalized != NormalizationResult::Ready) {
      for (uint32_t column = w.ny + 1; column <= w.features; ++column) {
        uint32_t chosen = rank;
        while (chosen < w.equations &&
               !(rows[chosen] & (UINT64_C(1) << column)))
          ++chosen;
        if (chosen == w.equations)
          continue;
        std::swap(rows[rank], rows[chosen]);
        std::swap(witnesses[rank], witnesses[chosen]);
        for (uint32_t row = rank + 1; row < w.equations; ++row)
          if (rows[row] & (UINT64_C(1) << column))
            if (!row_xor(row, rank))
              return BranchResolution::None;
        ++rank;
      }
    }
    affine_start = rank;
    for (uint32_t column = 1; column <= w.ny; ++column) {
      uint32_t chosen = rank;
      while (chosen < equations && !(rows[chosen] & (UINT64_C(1) << column)))
        ++chosen;
      if (chosen == equations)
        continue;
      std::swap(rows[rank], rows[chosen]);
      std::swap(witnesses[rank], witnesses[chosen]);
      for (uint32_t row = affine_start; row < equations; ++row)
        if (row != rank && (rows[row] & (UINT64_C(1) << column)))
          if (!row_xor(row, rank))
            return BranchResolution::None;
      ++rank;
    }
  }
  bool unit = false;
  for (uint32_t row = affine_start; row < equations; ++row)
    if (rows[row] == 1) {
      proof[0] = witnesses[row];
      unit = true;
      break;
    }
  if (!unit) {
    if (rank - affine_start < w.ny) {
      ++stats.rank_fallbacks;
      if (w.partial_enabled && rank > affine_start)
        return partial_resolution(w, columns, branch, out, rows, witnesses,
                                  affine_start, rank - affine_start, charge);
      return BranchResolution::None;
    }
    uint32_t assignment = 0;
    for (uint32_t i = 0; i < w.ny; ++i) {
      const uint64_t row = rows[affine_start + i];
      if ((row & ~UINT64_C(1)) != (UINT64_C(1) << (i + 1)))
        throw std::runtime_error("invalid projection affine pivot");
      assignment |= uint32_t(row & 1) << i;
    }
    Word value = columns[0];
    for (uint32_t feature = 1; feature <= w.features; ++feature)
      if ((assignment & w.monomials[feature]) == w.monomials[feature]) {
        if (!charge())
          return BranchResolution::None;
        value ^= columns[feature];
        stats.word_xors += w.limbs;
      }
    if (!value.nonzero()) {
      ++stats.satisfying_fallbacks;
      return BranchResolution::None;
    }
    const uint32_t bad = uint32_t(value.pivot());
    proof[0].toggle(bad);
    for (uint32_t feature = 1; feature <= w.features; ++feature) {
      const uint64_t bits =
          bad < 64 ? columns[feature].low() : columns[feature].high();
      if (!((bits >> (bad % 64)) & 1))
        continue;
      const uint32_t mask = w.monomials[feature], i = __builtin_ctz(mask);
      if (!charge())
        return BranchResolution::None;
      if (!(mask & (mask - 1))) {
        proof[0] ^= witnesses[affine_start + i];
        ++stats.certificate_xors;
        stats.word_xors += w.limbs;
      } else {
        const uint32_t j = __builtin_ctz(mask & (mask - 1));
        proof[j + 1] ^= witnesses[affine_start + i];
        ++stats.certificate_xors;
        stats.word_xors += w.limbs;
        if (assignment & (1u << i)) {
          if (!charge())
            return BranchResolution::None;
          proof[0] ^= witnesses[affine_start + j];
          ++stats.certificate_xors;
          stats.word_xors += w.limbs;
        }
      }
    }
  }
  if (!reserve_proof(out, entry)) {
    ++stats.budget_skips;
    return BranchResolution::None;
  }
  if (out.symmetry.enabled)
    w.affine_offsets[branch] = uint32_t(out.contradictions.size());
  out.contradictions.push_back(branch);
  for (uint32_t slot = 0; slot <= w.ny; ++slot) {
    out.contradictions.push_back(proof[slot].low());
    if (w.limbs == 2)
      out.contradictions.push_back(proof[slot].high());
  }
  ++stats.certified_branches;
  // Keep the existing attempts=certified+failed and proof/symmetry contracts.
  ++out.multipliers.attempts;
  ++out.multipliers.certified_branches;
  return BranchResolution::Contradiction;
}

template <typename Word, uint32_t RowWords>
static bool multiplier_identity_width(Producer &w, const Word *columns,
                                      uint32_t branch, Produced &out,
                                      uint64_t prior_work) {
  static_assert(RowWords >= 1 && RowWords <= 3);
  auto &stats = out.multipliers;
  const auto started = std::chrono::steady_clock::now();
  ++stats.attempts;
  uint64_t branch_work = prior_work;
  auto finish = [&](bool proved, bool budget) {
    stats.certified_branches += proved;
    stats.failed_branches += !proved;
    stats.budget_skips += budget;
    stats.seconds += std::chrono::duration<double>(
                         std::chrono::steady_clock::now() - started)
                         .count();
    return proved;
  };
  auto charge = [&]() {
    if (stats.rows + stats.row_xors + out.deferred.reconstruction_pivots +
                out.projection.work >=
            MULTIPLIER_WORK_BUDGET ||
        branch_work >= MULTIPLIER_BRANCH_BUDGET)
      return false;
    ++branch_work;
    return true;
  };
  const uint64_t entry_words = 1 + w.proof_words;
  if (entry_words > MULTIPLIER_PROOF_WORDS_LIMIT - out.contradictions.size())
    return finish(false, true);
  std::fill(w.multiplier_active.begin(), w.multiplier_active.end(), 0);
  const uint32_t stride = w.features + 1;
  for (uint32_t slot = 0; slot <= w.ny; ++slot) {
    const uint32_t *products = w.product_index.data() + size_t(slot) * stride;
    for (uint32_t equation = 0; equation < w.equations; ++equation) {
      if (!charge())
        return finish(false, true);
      ++stats.rows;
      std::array<uint64_t, 3> row{};
      std::array<uint64_t, 3> dependencies{};
      for (uint32_t feature = 0; feature < stride; ++feature) {
        const uint64_t coefficient =
            equation < 64 ? columns[feature].low() : columns[feature].high();
        if ((coefficient >> (equation % 64)) & 1)
          row[products[feature] / 64] ^= UINT64_C(1)
                                         << (products[feature] % 64);
      }
      while (true) {
        int pivot = -1;
        for (uint32_t limb = RowWords; limb; --limb)
          if (row[limb - 1]) {
            pivot = int(64 * (limb - 1) + 63 - __builtin_clzll(row[limb - 1]));
            break;
          }
        if (pivot < 0)
          break;
        if (pivot == 0) {
          // A polynomial identity in the Boolean quotient, not an
          // inference from a missing or inconsistent lifted root.
          std::array<Word, 11> proof{};
          const bool reconstructed = [&]() {
            TimedPhase timing(out.deferred.reconstruction_seconds);
            ++out.deferred.reconstruction_attempts;
            proof[slot].toggle(equation);
            ++out.deferred.source_toggles;
            // Highest-column-first reduction makes the dependency
            // graph triangular: pivot p only uses pivots above p.
            // Expand low columns first, preserving GF(2) cancellation.
            for (uint32_t limb = 0; limb < RowWords; ++limb) {
              while (dependencies[limb]) {
                if (out.deferred.reconstruction_pivots >=
                        DEFERRED_RECONSTRUCTION_BUDGET ||
                    !charge())
                  return false;
                const uint32_t used =
                    64 * limb + __builtin_ctzll(dependencies[limb]);
                dependencies[limb] &= dependencies[limb] - 1;
                const uint32_t source = w.multiplier_sources[used];
                proof[source / w.equations].toggle(source % w.equations);
                ++out.deferred.source_toggles;
                ++out.deferred.reconstruction_pivots;
                const uint64_t *parents =
                    w.multiplier_dependencies.data() + size_t(used) * RowWords;
                for (uint32_t j = limb; j < RowWords; ++j)
                  dependencies[j] ^= parents[j];
                out.deferred.reconstruction_word_xors += RowWords - limb;
              }
            }
            ++out.deferred.reconstructed_proofs;
            return true;
          }();
          if (!reconstructed || !reserve_proof(out, entry_words))
            return finish(false, true);
          if (out.symmetry.enabled)
            w.affine_offsets[branch] = uint32_t(out.contradictions.size());
          out.contradictions.push_back(branch);
          for (uint32_t j = 0; j <= w.ny; ++j) {
            out.contradictions.push_back(proof[j].low());
            if (w.limbs == 2)
              out.contradictions.push_back(proof[j].high());
          }
          return finish(true, false);
        }
        uint64_t *old = w.multiplier_pivots.data() + size_t(pivot) * RowWords;
        uint64_t *old_dependencies =
            w.multiplier_dependencies.data() + size_t(pivot) * RowWords;
        if (!w.multiplier_active[pivot]) {
          w.multiplier_active[pivot] = 1;
          std::copy_n(row.data(), RowWords, old);
          std::copy_n(dependencies.data(), RowWords, old_dependencies);
          w.multiplier_sources[pivot] = slot * w.equations + equation;
          ++out.deferred.inserted_pivots;
          break;
        }
        if (!charge())
          return finish(false, true);
        ++stats.row_xors;
        // Forward uint64 XOR work: coefficient row plus one dependency
        // bit. Reconstruction XORs and source toggles are separate.
        stats.word_xors += RowWords + 1;
        ++out.deferred.dependency_toggles;
        for (uint32_t limb = 0; limb < RowWords; ++limb)
          row[limb] ^= old[limb];
        dependencies[pivot / 64] ^= UINT64_C(1) << (pivot % 64);
      }
    }
  }
  return finish(false, false);
}
// The validated residual dimension fixes the coefficient-row width.
// Dispatch once per residual system; every reduction still uses fresh pivots.
template <typename Word>
static BranchResolution multiplier_identity(Producer &w, const Word *columns,
                                            uint32_t branch, Produced &out) {
  const uint64_t before = out.projection.work;
  const auto resolution = projection_identity(w, columns, branch, out);
  if (resolution != BranchResolution::None)
    return resolution;
  const uint64_t prior_work = out.projection.work - before;
  switch (w.row_words) {
  case 1:
    return multiplier_identity_width<Word, 1>(w, columns, branch, out,
                                              prior_work)
               ? BranchResolution::Contradiction
               : BranchResolution::None;
  case 2:
    return multiplier_identity_width<Word, 2>(w, columns, branch, out,
                                              prior_work)
               ? BranchResolution::Contradiction
               : BranchResolution::None;
  case 3:
    return multiplier_identity_width<Word, 3>(w, columns, branch, out,
                                              prior_work)
               ? BranchResolution::Contradiction
               : BranchResolution::None;
  default:
    throw std::logic_error("invalid residual row width");
  }
}
template <typename Word>
static void solve(Producer &w, std::vector<Word> &values, const void *masks,
                  uint32_t width, const uint64_t *coeff, uint32_t count,
                  Produced &out) {
  if ((width != 32 && width != 64) || count > TERM_LIMIT ||
      (count && (!masks || !coeff)))
    throw std::invalid_argument("packed extents");
  out.roots.reserve(ROOT_LIMIT);
  out.contradictions.resize(size_t(w.branches) * w.limbs, 0);
  out.stats.features = w.features;
  out.symmetry.workspace_bytes =
      (w.affine_offsets.size() + w.root_offsets.size()) * sizeof(uint32_t);
  out.deferred.workspace_bytes =
      w.multiplier_dependencies.size() * 8 + w.multiplier_sources.size() * 4;
  out.multipliers.workspace_bytes =
      w.multiplier_pivots.size() * 8 + out.deferred.workspace_bytes +
      w.multiplier_active.size() +
      (w.cubic_index.size() + w.product_index.size()) * 4;
  out.normalization.workspace_bytes =
      sizeof(w.normalization) + w.normalization.transport.capacity() *
                                    sizeof(w.normalization.transport[0]);
  out.stats.workspace_bytes =
      out.normalization.workspace_bytes + values.size() * sizeof(Word) +
      out.contradictions.capacity() * 8 + out.multipliers.workspace_bytes +
      out.symmetry.workspace_bytes;
  auto started = std::chrono::steady_clock::now();
  const uint64_t low = (UINT64_C(1) << w.nx) - 1;
  const uint32_t stride = w.features + 1;
  // The support-to-feature layout is invariant. Coefficients and all
  // specialization values are rebuilt from this call's packed input.
  std::fill(values.begin(), values.end(), Word{});
  for (uint32_t t = 0; t < count; ++t) {
    const uint64_t mask = mask_at(masks, width, t);
    if (mask >> (w.nx + w.ny))
      throw std::invalid_argument("mask outside ring");
    if (w.equations % 64 &&
        coeff[size_t(t) * w.limbs + w.limbs - 1] >> (w.equations % 64))
      throw std::invalid_argument("coefficient outside equations");
    Word c{coeff[size_t(t) * w.limbs],
           w.limbs == 2 ? coeff[size_t(t) * 2 + 1] : 0};
    if (!c.nonzero())
      continue;
    const uint32_t right = uint32_t(mask >> w.nx),
                   feature = w.feature_index[right];
    if (feature == UINT32_MAX)
      throw std::domain_error("residual degree exceeds two");
    values[size_t(mask & low) * stride + feature] ^= c;
  }
  // Packed-equation subset transform evaluates each residual coefficient
  // on every fixed-block assignment. No target-independent answers exist.
  for (uint32_t bit = 1; bit < w.branches; bit <<= 1)
    for (uint32_t base = 0; base < w.branches; base += 2 * bit)
      for (uint32_t j = 0; j < bit; ++j) {
        Word *dst = values.data() + size_t(base + bit + j) * stride;
        const Word *src = values.data() + size_t(base + j) * stride;
        for (uint32_t feature = 0; feature < stride; ++feature)
          dst[feature] ^= src[feature];
      }
  out.stats.transform_xors = uint64_t(w.nx) * (w.branches / 2) * stride;
  auto specialized = std::chrono::steady_clock::now();
  out.stats.specialization =
      std::chrono::duration<double>(specialized - started).count();
  // This is a fresh exact test of all residual coefficients, never a
  // shape/target-family assumption. Duplicate original terms already XORed.
  out.symmetry.shape_fallback = w.nx % 2;
  if (!out.symmetry.shape_fallback) {
    TimedPhase timing(out.symmetry.check_seconds);
    bool same = true;
    for (uint32_t a = 0; a < w.branches && same; ++a) {
      const uint32_t b = swapped(w, a);
      if (a >= b)
        continue;
      ++out.symmetry.compared_pairs;
      for (uint32_t feature = 0; feature < stride; ++feature) {
        ++out.symmetry.compared_coefficients;
        const Word &left = values[size_t(a) * stride + feature];
        const Word &right = values[size_t(b) * stride + feature];
        if (left.low() != right.low() || left.high() != right.high()) {
          same = false;
          break;
        }
      }
    }
    out.symmetry.enabled = same;
    out.symmetry.asymmetric_fallback = !same;
    if (same)
      std::fill(w.affine_offsets.begin(), w.affine_offsets.end(), UINT32_MAX);
  }
  const uint64_t *gpu_rows = nullptr;
  w.gpu_projection = nullptr;
  out.gpu_projection.requested = w.gpu_projection_enabled;
#ifdef QUADRATIC_METAL
  if (w.metal) {
    const auto gpu_started = std::chrono::steady_clock::now();
    gpu_rows = compact_metal_solve(
        w.metal, values.data(), values.size() * sizeof(Word),
        out.symmetry.enabled != 0, w.gpu_projection_enabled,
        out.stats.gpu_device);
    if (w.gpu_projection_enabled) {
      w.gpu_projection = compact_metal_projection(w.metal);
      out.gpu_projection.enabled = 1;
      out.gpu_projection.dispatched_branches =
          compact_metal_dispatched_branches(w.metal);
    }
    out.gpu_projection.output_bytes = compact_metal_projection_bytes(w.metal);
    out.stats.gpu_wall = std::chrono::duration<double>(
                             std::chrono::steady_clock::now() - gpu_started)
                             .count();
    out.stats.gpu_used = 1;
    out.symmetry.gpu_linearized_branches =
        compact_metal_dispatched_branches(w.metal);
    out.stats.workspace_bytes += compact_metal_bytes(w.metal);
  } else
    out.stats.gpu_shape_fallback = 1;
#endif
  auto add_root = [&](uint32_t x, uint32_t y) {
    if (out.roots.size() == ROOT_LIMIT) {
      out.stats.evaluation = std::chrono::duration<double>(
                                 std::chrono::steady_clock::now() - specialized)
                                 .count();
      throw std::length_error("complete roots exceed 256; no partial basis");
    }
    out.roots.push_back(uint64_t(x) | (uint64_t(y) << w.nx));
    out.stats.roots = out.roots.size();
  };
  auto charged = [&]() {
    if (out.stats.lifted_candidates + out.stats.fallback_assignments +
            out.partial.assignments >=
        ENUMERATION_BUDGET) {
      out.stats.evaluation = std::chrono::duration<double>(
                                 std::chrono::steady_clock::now() - specialized)
                                 .count();
      throw std::length_error(
          "exact enumeration budget exceeded; no partial basis");
    }
  };
  for (uint32_t x = 0; x < w.branches; ++x) {
    ++out.stats.branches;
    if (out.symmetry.enabled) {
      w.root_offsets[x] = uint32_t(out.roots.size());
      const uint32_t representative = swapped(w, x);
      if (representative < x) {
        TimedPhase timing(out.symmetry.expand_seconds);
        ++out.symmetry.aliases;
        bool constant = false;
        for (uint32_t limb = 0; limb < w.limbs; ++limb) {
          const uint64_t word =
              out.contradictions[size_t(representative) * w.limbs + limb];
          out.contradictions[size_t(x) * w.limbs + limb] = word;
          constant |= word != 0;
        }
        if (constant)
          ++out.symmetry.constant_copies;
        else {
          ++out.stats.consistent;
          const uint32_t offset = w.affine_offsets[representative];
          if (offset != UINT32_MAX) {
            const uint64_t entry = 1 + w.proof_words;
            if (entry <= SYMMETRY_COPY_WORDS_BUDGET -
                             out.symmetry.affine_copy_words &&
                reserve_proof(out, entry)) {
              const uint64_t tag =
                  out.contradictions[offset] & PARTIAL_AFFINE_RECORD;
              out.contradictions.push_back(tag | x);
              if (tag)
                ++out.partial.copied_records;
              // Reserve before indexing the source: reserve can
              // relocate storage, and self-range insert is avoided.
              for (uint32_t j = 0; j < w.proof_words; ++j)
                out.contradictions.push_back(
                    out.contradictions[size_t(offset) + 1 + j]);
              ++out.symmetry.affine_copies;
              out.symmetry.affine_copy_words += entry;
            } else
              ++out.symmetry.copy_budget_skips;
          }
        }
        const uint32_t first = w.root_offsets[representative];
        const uint32_t end = w.root_offsets[representative + 1];
        if (first == end)
          ++out.symmetry.rootless_aliases;
        for (uint32_t i = first; i < end; ++i) {
          const uint32_t y = uint32_t(out.roots[i] >> w.nx);
          add_root(x, y);
          ++out.symmetry.copied_roots;
        }
        continue;
      }
    }
    ++out.symmetry.representatives;
    const Word *columns = values.data() + size_t(x) * stride;
    std::array<uint64_t, 55> kernel{};
    uint32_t nullity = 0;
    uint64_t particular = 0;
    bool consistent = true;
    if (gpu_rows) {
      const uint64_t *rows = gpu_rows + size_t(x) * 34;
      const uint32_t rank = rows[0] & 0x7fffffffu;
      if (rank > w.features)
        throw std::runtime_error("invalid Metal rank");
      nullity = w.features - rank;
      consistent = !(rows[0] & 0x80000000u);
      if (!consistent)
        out.contradictions[x] = rows[33];
      if (consistent) {
        const uint64_t feature_mask = (UINT64_C(1) << w.features) - 1,
                       rhs_bit = UINT64_C(1) << w.features;
        uint64_t pivot_mask = 0;
        std::array<uint64_t, 32> pivot_bits{};
        for (uint32_t row = 0; row < rank; ++row) {
          const uint64_t features = rows[row + 1] & feature_mask;
          if (!features)
            throw std::runtime_error("invalid Metal pivot row");
          const uint64_t bit = UINT64_C(1) << __builtin_ctzll(features);
          pivot_mask |= bit;
          pivot_bits[row] = bit;
          if (rows[row + 1] & rhs_bit)
            particular |= bit;
        }
        // The old vector loop visits every nonpivot feature, so its
        // k == nullity check is exactly popcount(pivot_mask) == rank.
        // Preserve that validation even when no vector is consumed.
        if (uint32_t(__builtin_popcountll(pivot_mask)) != rank)
          throw std::runtime_error("invalid Metal nullspace");
        // Large-nullity branches use projection/Macaulay proofs and
        // exact original-variable fallback; neither reads kernel.
        if (nullity < w.ny) {
          uint32_t k = 0;
          for (uint32_t j = 0; j < w.features; ++j)
            if (!(pivot_mask & (UINT64_C(1) << j))) {
              uint64_t value = UINT64_C(1) << j;
              for (uint32_t row = 0; row < rank; ++row)
                if (rows[row + 1] & (UINT64_C(1) << j))
                  value |= pivot_bits[row];
              kernel[k++] = value;
            }
          if (k != nullity)
            throw std::runtime_error("invalid Metal nullspace");
        }
      }
    } else {
      std::array<Word, 128> pivots{};
      std::array<uint64_t, 128> combinations{};
      for (uint32_t j = 0; j < w.features; ++j) {
        Word column = columns[j + 1];
        uint64_t combination = UINT64_C(1) << j;
        while (column.nonzero()) {
          int p = column.pivot();
          if (!pivots[p].nonzero()) {
            pivots[p] = column;
            combinations[p] = combination;
            break;
          }
          column ^= pivots[p];
          combination ^= combinations[p];
        }
        if (!column.nonzero())
          kernel[nullity++] = combination;
      }
      Word rhs = columns[0];
      while (rhs.nonzero()) {
        int p = rhs.pivot();
        if (!pivots[p].nonzero())
          break;
        rhs ^= pivots[p];
        particular ^= combinations[p];
      }
      consistent = !rhs.nonzero();
      if (!consistent) {
        // Build a dual functional orthogonal to every column pivot.
        // Its value on the unreduced RHS pivot is one. This is only
        // proof generation; a separate library checks the identity.
        const uint32_t p = uint32_t(rhs.pivot());
        Word u{};
        u.toggle(p);
        for (uint32_t row = 0; row < w.equations; ++row)
          if (pivots[row].nonzero() && u.parity(pivots[row]))
            u.toggle(row);
        out.contradictions[size_t(x) * w.limbs] = u.low();
        if (w.limbs == 2)
          out.contradictions[size_t(x) * 2 + 1] = u.high();
      }
    }
    out.stats.max_nullity = std::max(out.stats.max_nullity, uint64_t(nullity));
    if (!consistent)
      continue;
    ++out.stats.consistent;
    if (nullity < w.ny) {
      const size_t roots_before = out.roots.size();
      uint64_t value = particular;
      for (uint32_t serial = 0; serial < (1u << nullity); ++serial) {
        charged();
        ++out.stats.lifted_candidates;
        if (serial)
          value ^= kernel[__builtin_ctz(serial)];
        const uint32_t y = uint32_t(value) & ((1u << w.ny) - 1);
        bool valid = true;
        for (uint32_t j = w.ny; j < w.features; ++j)
          if (((value >> j) & 1u) !=
              unsigned((y & w.monomials[j + 1]) == w.monomials[j + 1])) {
            valid = false;
            break;
          }
        if (valid)
          add_root(x, y);
      }
      // A small lifted search is cheaper than another matrix. If it
      // finds no actual roots, seek a proof to spare the checker its
      // independent full residual enumeration.
      if (out.roots.size() == roots_before)
        multiplier_identity(w, columns, x, out);
    } else {
      const auto resolution = multiplier_identity(w, columns, x, out);
      if (resolution != BranchResolution::None) {
        if (resolution == BranchResolution::Contradiction)
          out.multipliers.avoided_assignments += UINT64_C(1) << w.ny;
        continue;
      }
      ++out.stats.fallback_branches;
      // Exact original-variable fallback. Gray-code updates use the
      // quadratic derivative, avoiding enumeration in lifted space.
      Word value = columns[0];
      uint32_t y = 0;
      for (uint32_t serial = 0; serial < (1u << w.ny); ++serial) {
        charged();
        ++out.stats.fallback_assignments;
        if (serial) {
          const uint32_t changed = uint32_t(__builtin_ctz(serial));
          value ^= columns[changed + 1];
          for (uint32_t j = 0; j < w.ny; ++j)
            if (j != changed && ((y >> j) & 1u))
              value ^= columns[w.feature_index[(1u << j) | (1u << changed)]];
          y ^= 1u << changed;
        }
        if (!value.nonzero())
          add_root(x, y);
      }
    }
  }
  if (out.symmetry.enabled)
    w.root_offsets[w.branches] = uint32_t(out.roots.size());
  std::sort(out.roots.begin(), out.roots.end());
  out.stats.roots = out.roots.size();
  out.multipliers.proof_words = out.contradictions.size();
  out.multipliers.proof_capacity_words = out.contradictions.capacity();
  auto evaluated = std::chrono::steady_clock::now();
  out.stats.evaluation =
      std::chrono::duration<double>(evaluated - specialized).count();
  out.basis = interpolate(w.nx + w.ny, out.roots, out.stats);
  out.stats.interpolation = std::chrono::duration<double>(
                                std::chrono::steady_clock::now() - evaluated)
                                .count();
}
} // namespace
extern "C" uint32_t branch_coefficient_bits(const void *p) {
  return p ? 8 * word_bytes(static_cast<const Producer *>(p)->equations) : 0;
}
extern "C" const char *branch_error() { return error_text.c_str(); }
extern "C" uint32_t branch_error_code() { return error_code; }
extern "C" uint64_t branch_stats_size() { return sizeof(BranchStats); }
extern "C" uint64_t branch_multiplier_stats_size() {
  return sizeof(MultiplierStats);
}
extern "C" uint64_t branch_deferred_stats_size() {
  return sizeof(DeferredStats);
}
extern "C" const DeferredStats *branch_deferred_stats(const void *p) {
  return p ? &static_cast<const Produced *>(p)->deferred : nullptr;
}
extern "C" const DeferredStats *branch_last_deferred_stats() {
  return &failed_deferred_stats;
}
extern "C" uint64_t branch_symmetry_stats_size() {
  return sizeof(SymmetryStats);
}
extern "C" const SymmetryStats *branch_symmetry_stats(const void *p) {
  return p ? &static_cast<const Produced *>(p)->symmetry : nullptr;
}
extern "C" const SymmetryStats *branch_last_symmetry_stats() {
  return &failed_symmetry_stats;
}
extern "C" const MultiplierStats *branch_last_multiplier_stats() {
  return &failed_multiplier_stats;
}
extern "C" const MultiplierStats *branch_multiplier_stats(const void *p) {
  return p ? &static_cast<const Produced *>(p)->multipliers : nullptr;
}
extern "C" const char *branch_device(const void *p) {
#ifdef QUADRATIC_METAL
  auto *w = static_cast<const Producer *>(p);
  if (w && w->metal)
    return compact_metal_device(w->metal);
  return "cpu: Metal shape fallback (features>55 or equations>32)";
#else
  (void)p;
  return "cpu";
#endif
}
extern "C" void *branch_create(uint32_t x, uint32_t y, uint32_t e) {
  try {
    dimensions(x, y, e);
    return new Producer(x, y, e);
  } catch (const std::exception &e) {
    error_text = e.what();
    error_code = 6;
    return nullptr;
  }
}
extern "C" void branch_destroy(void *p) { delete static_cast<Producer *>(p); }
extern "C" void *branch_solve(void *p, const void *masks, uint32_t width,
                              const uint64_t *c, uint32_t count,
                              BranchStats *stats) {
  Produced result;
  try {
    if (!p || !stats)
      throw std::invalid_argument("null producer or result");
    *stats = {};
    auto &w = *static_cast<Producer *>(p);
    std::lock_guard<std::mutex> guard(w.mutex);
    std::visit(
        [&](auto &values) { solve(w, values, masks, width, c, count, result); },
        w.values);
    *stats = result.stats;
    return new Produced(std::move(result));
  } catch (const std::length_error &e) {
    error_text = e.what();
    error_code = 5;
  } catch (const std::domain_error &e) {
    error_text = e.what();
    error_code = 7;
  } catch (const std::invalid_argument &e) {
    error_text = e.what();
    error_code = 6;
  } catch (const std::exception &e) {
    error_text = e.what();
    error_code = 8;
  }
  if (stats)
    *stats = result.stats;
  failed_symmetry_stats = result.symmetry;
  failed_deferred_stats = result.deferred;
  failed_multiplier_stats = result.multipliers;
  failed_projection_stats = result.projection;
  failed_normalization_stats = result.normalization;
  failed_partial_stats = result.partial;
  failed_gpu_projection_stats = result.gpu_projection;
  failed_multiplier_stats.proof_words = result.contradictions.size();
  failed_multiplier_stats.proof_capacity_words =
      result.contradictions.capacity();
  return nullptr;
}
extern "C" uint32_t branch_rows(const void *p) {
  return p ? uint32_t(static_cast<const Produced *>(p)->basis.size()) : 0;
}
extern "C" uint32_t branch_row_size(const void *p, uint32_t row) {
  auto *r = static_cast<const Produced *>(p);
  return r && row < r->basis.size() ? uint32_t(r->basis[row].size()) : 0;
}
extern "C" const uint64_t *branch_row(const void *p, uint32_t row) {
  auto *r = static_cast<const Produced *>(p);
  return r && row < r->basis.size() ? r->basis[row].data() : nullptr;
}
extern "C" const uint64_t *branch_roots(const void *p) {
  return p ? static_cast<const Produced *>(p)->roots.data() : nullptr;
}
extern "C" uint64_t branch_proof_size(const void *p) {
  return p ? static_cast<const Produced *>(p)->contradictions.size() : 0;
}
extern "C" const uint64_t *branch_proof(const void *p) {
  return p ? static_cast<const Produced *>(p)->contradictions.data() : nullptr;
}
extern "C" void branch_result_destroy(void *p) {
  delete static_cast<Produced *>(p);
}

extern "C" uint64_t branch_projection_stats_size() {
  return sizeof(ProjectionStats);
}
extern "C" const ProjectionStats *branch_last_projection_stats() {
  return &failed_projection_stats;
}
extern "C" const ProjectionStats *branch_projection_stats(const void *p) {
  return p ? &static_cast<const Produced *>(p)->projection : nullptr;
}

extern "C" int branch_normalization_configure(void *context, uint64_t modulus) {
  try {
    if (!context)
      throw std::invalid_argument("null normalization context");
    auto &w = *static_cast<Producer *>(context);
    std::lock_guard<std::mutex> lock(w.mutex);
    w.normalization = {};
    error_text.clear();
    error_code = 0;
    if (!modulus)
      return 0; // Explicitly disable the optional constructor.
    if (w.equations > 31 || w.ny < 3 || 3 * w.ny - 4 >= w.equations)
      return 0;
    if ((modulus >> w.equations) != 1 || !(modulus & 1))
      throw std::invalid_argument(
          "normalization requires a monic odd modulus of the equation degree");
    NormalizationLayout next{};
    next.n = w.equations;
    next.modulus = uint32_t(modulus);
    next.top = 3 * w.ny - 4;
    next.annihilator[next.count++] = 1;
    uint32_t multiples = 0, others = 0;
    for (uint32_t i = 1; i <= next.top; ++i)
      (i % 3 ? others : multiples) |= 1u << i;
    next.annihilator[next.count++] = multiples;
    next.annihilator[next.count++] = others;
    for (uint32_t i = next.top + 1; i < next.n; ++i)
      next.annihilator[next.count++] = 1u << i;
    if (next.count != next.n - 3 * w.ny + 6)
      throw std::logic_error("normalization annihilator dimension");
    for (uint32_t feature = w.ny + 1; feature <= w.features; ++feature) {
      const uint32_t mask = w.monomials[feature];
      const uint32_t i = __builtin_ctz(mask),
                     j = __builtin_ctz(mask & (mask - 1));
      next.left_exponent[feature] = uint8_t(2 * i + j);
      next.right_exponent[feature] = uint8_t(i + 2 * j);
    }
    auto setup_charge = []() { return true; };
    uint32_t inverse = 0, product = 0;
    if (!normalization_inverse(6, next.n, next.modulus, inverse,
                               setup_charge) ||
        !normalization_multiply(6, inverse, next.n, next.modulus, product,
                                setup_charge) ||
        product != 1)
      return 0;
    for (uint32_t nibble = 0; nibble < (next.n + 3) / 4; ++nibble)
      for (uint32_t value = 0; value < 16; ++value) {
        const uint32_t coefficient =
            (value << (4 * nibble)) & ((1u << next.n) - 1);
        normalization_multiply(coefficient, inverse, next.n, next.modulus,
                               next.inverse_six[nibble][value], setup_charge);
      }
    // For each fixed annihilator a, inverse -> a M_inverse is F2-linear.
    // Build bit images before combining them into bounded nibble tables.
    next.transport.resize(next.count);
    for (uint32_t row = 0; row < next.count; ++row) {
      std::array<uint32_t, 32> images{};
      for (uint32_t bit = 0; bit < next.n; ++bit) {
        uint32_t column = 1u << bit;
        for (uint32_t e = 0; e < next.n; ++e) {
          images[bit] |=
              uint32_t(__builtin_parity(next.annihilator[row] & column)) << e;
          column = normalization_xtime(column, next.n, next.modulus);
        }
      }
      for (uint32_t nibble = 0; nibble < (next.n + 3) / 4; ++nibble)
        for (uint32_t value = 1; value < 16; ++value) {
          const uint32_t bit = __builtin_ctz(value);
          next.transport[row][nibble][value] =
              next.transport[row][nibble][value & (value - 1)] ^
              images[4 * nibble + bit];
        }
    }
    next.enabled = true;
    w.normalization = next;
    return 1;
  } catch (const std::exception &error) {
    error_text = error.what();
    error_code = 6;
    return -1;
  }
}
extern "C" uint64_t branch_normalization_stats_size() {
  return sizeof(NormalizationStats);
}
extern "C" const NormalizationStats *branch_last_normalization_stats() {
  return &failed_normalization_stats;
}
extern "C" const NormalizationStats *branch_normalization_stats(const void *p) {
  return p ? &static_cast<const Produced *>(p)->normalization : nullptr;
}

// Read-only diagnostic used to validate the table representation independently.
extern "C" int branch_normalization_transport(void *context, uint32_t value,
                                              uint32_t *output,
                                              uint32_t capacity) {
  if (!context || !output)
    return -1;
  auto &w = *static_cast<Producer *>(context);
  std::lock_guard<std::mutex> lock(w.mutex);
  const auto &layout = w.normalization;
  if (!layout.enabled || capacity < layout.count || (value >> layout.n))
    return -1;
  for (uint32_t row = 0; row < layout.count; ++row) {
    uint32_t witness = 0;
    for (uint32_t nibble = 0; nibble < (layout.n + 3) / 4; ++nibble)
      witness ^= layout.transport[row][nibble][(value >> (4 * nibble)) & 15];
    output[row] = witness;
  }
  return int(layout.count);
}

extern "C" uint64_t branch_partial_stats_size() {
  return sizeof(PartialProduceStats);
}
extern "C" const PartialProduceStats *branch_partial_stats(const void *p) {
  return p ? &static_cast<const Produced *>(p)->partial : nullptr;
}
extern "C" const PartialProduceStats *branch_last_partial_stats() {
  return &failed_partial_stats;
}
extern "C" int branch_partial_configure(void *p, uint32_t enabled) {
  if (!p || enabled > 1)
    return -1;
  try {
    auto &w = *static_cast<Producer *>(p);
    std::lock_guard<std::mutex> guard(w.mutex);
    w.partial_enabled = enabled != 0;
    return int(w.partial_enabled);
  } catch (...) {
    return -1;
  }
}

extern "C" uint64_t branch_gpu_projection_stats_size() {
  return sizeof(GPUProjectionStats);
}
extern "C" const GPUProjectionStats *
branch_gpu_projection_stats(const void *p) {
  return p ? &static_cast<const Produced *>(p)->gpu_projection : nullptr;
}
extern "C" const GPUProjectionStats *branch_last_gpu_projection_stats() {
  return &failed_gpu_projection_stats;
}
extern "C" int branch_gpu_projection_configure(void *context,
                                               uint32_t enabled) {
  if (!context || enabled > 1)
    return -1;
  auto &w = *static_cast<Producer *>(context);
  std::lock_guard<std::mutex> lock(w.mutex);
  w.gpu_projection_enabled = enabled != 0;
#ifdef QUADRATIC_METAL
  return w.gpu_projection_enabled && w.metal;
#else
  return 0;
#endif
}
