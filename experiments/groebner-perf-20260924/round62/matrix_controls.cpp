#include "engine.inc"

static void print_poly(const Poly &terms)
{
    std::cout << '[';
    for (size_t i = 0; i < terms.size(); ++i) {
        if (i) std::cout << ',';
        std::cout << terms[i];
    }
    std::cout << ']';
}

static void control(size_t columns, bool high, uint64_t start, uint64_t limit, uint32_t node_limit)
{
    std::set<Mask> support;
    for (size_t c = 0; c < columns; ++c) support.insert((high ? uint64_t(1) << 63 : 0) | c);
    std::vector<Poly> input;
    for (size_t r = 0; r < std::min<size_t>(18, columns); ++r) {
        Poly row;
        for (size_t c = 0; c < columns; ++c) {
            uint64_t value =
                (r + 1) * UINT64_C(0x9e3779b97f4a7c15) + c * UINT64_C(0xbf58476d1ce4e5b9);
            value ^= value >> 27;
            if (c == r || value % 7 < 3) row.push_back((high ? uint64_t(1) << 63 : 0) | c);
        }
        input.push_back(std::move(row));
    }
    top_stats = {};
    column_stats = {};
    scratch_stats = {};
    packed_stats = {};
    Engine engine(limit, node_limit, 4096, 64, true);
    engine.work = start;
    std::vector<Row> output;
    const char *status = "complete";
    const char *reason = "none";
    try {
        std::vector<Row> rows;
        for (size_t i = 0; i < input.size(); ++i) rows.push_back({input[i], engine.emit(0, i)});
        output = engine.column_matrix(std::move(rows), support, {});
    } catch (const Budget &error) {
        status = "budget";
        // Preserve the distinction without retaining a pointer to the exception.
        reason = std::string(error.what()) == "native work budget" ? "work" : "nodes";
    }
    std::cout << "{\"columns\":" << columns << ",\"high\":" << high << ",\"start\":" << start
              << ",\"limit\":" << limit << ",\"node_limit\":" << node_limit << ",\"status\":\""
              << status << "\",\"reason\":\"" << reason << "\",\"work\":" << engine.work
              << ",\"input\":[";
    for (size_t i = 0; i < input.size(); ++i) {
        if (i) std::cout << ',';
        print_poly(input[i]);
    }
    std::cout << "],\"nodes\":[";
    for (size_t i = 0; i < engine.nodes.size(); ++i) {
        if (i) std::cout << ',';
        const auto &node = engine.nodes[i];
        std::cout << '[' << node.op << ',' << node.a << ',' << node.b << ']';
    }
    std::cout << "],\"output\":[";
    for (size_t i = 0; i < output.size(); ++i) {
        if (i) std::cout << ',';
        std::cout << '[' << output[i].proof << ',';
        print_poly(output[i].terms);
        std::cout << ']';
    }
    std::cout << "],\"packed\":[" << packed_stats.matrices << ',' << packed_stats.fallback_matrices
              << ',' << packed_stats.peak_payload_words << "]}\n";
}

int main()
{
    for (size_t columns : {0, 1, 3, 4, 5, 63, 64, 65, 127, 128, 129, 255, 256, 257}) {
        for (bool high : {false, true}) {
            for (uint64_t limit :
                 {UINT64_C(0), UINT64_C(1), UINT64_C(31), UINT64_C(63), UINT64_C(64), UINT64_C(127),
                  UINT64_C(255), UINT64_C(511), UINT64_C(1024), UINT64_C(10000), UINT64_MAX})
                control(columns, high, 0, limit, UINT32_MAX);
            for (uint64_t remaining : {0, 1, 63, 64, 299, 300})
                control(columns, high, UINT64_MAX - 300, UINT64_MAX - 300 + remaining, UINT32_MAX);
            for (uint32_t nodes : {1, 2, 5, 10, 17, 18, 19, 40, 80})
                control(columns, high, 0, UINT64_MAX, nodes);
        }
    }
}
