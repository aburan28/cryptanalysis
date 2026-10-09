"""Observation-only clocks inside the frozen proof-carrying F4 engine."""
from pathlib import Path

HERE = Path(__file__).resolve().parent


def once(source, old, new):
    assert source.count(old) == 1, (old, source.count(old))
    return source.replace(old, new, 1)


def engine(source):
    header = '''struct F4InnerStats {
    uint64_t initial_ns=0, pairs_ns=0, matrix_ns=0, candidate_ns=0,
             final_ns=0, compute_ns=0, compact_ns=0, symbolic_ns=0,
             column_ns=0, packed_ns=0;
};
static thread_local F4InnerStats f4_inner{};
struct F4Timer {
    uint64_t &slot;
    std::chrono::steady_clock::time_point start=std::chrono::steady_clock::now();
    bool active=true;
    explicit F4Timer(uint64_t &target):slot(target){}
    void stop() {
        if (!active) return;
        slot += uint64_t(std::chrono::duration_cast<std::chrono::nanoseconds>(
            std::chrono::steady_clock::now()-start).count());
        active=false;
    }
    ~F4Timer(){stop();}
};
'''
    source = once(source, 'class Engine {', header + 'class Engine {')
    source = once(source, 'std::vector<Row> packed_column_matrix(std::vector<Row> rows, const std::vector<Mask> &columns,\n'
                         '                                      const std::set<Mask> &reducer_heads, size_t width)\n{',
                  'std::vector<Row> packed_column_matrix(std::vector<Row> rows, const std::vector<Mask> &columns,\n'
                  '                                      const std::set<Mask> &reducer_heads, size_t width)\n{\n'
                  '    F4Timer timer(f4_inner.packed_ns);')
    source = once(source, '    std::vector<Row> matrix(std::vector<Row> rows) {\n'
                          '        std::set<Mask> reducer_heads;',
                  '    std::vector<Row> matrix(std::vector<Row> rows) {\n'
                  '        F4Timer symbolic_timer(f4_inner.symbolic_ns);\n'
                  '        std::set<Mask> reducer_heads;')
    source = once(source, '        ++matrices;matrix_rows+=rows.size();peak_rows=std::max<uint64_t>(peak_rows,rows.size());',
                  '        symbolic_timer.stop();\n'
                  '        F4Timer column_timer(f4_inner.column_ns);\n'
                  '        ++matrices;matrix_rows+=rows.size();peak_rows=std::max<uint64_t>(peak_rows,rows.size());')
    source = once(source, '    void compute(const std::vector<Poly>& input) {\n'
                          '        for (uint32_t i=0;i<input.size();++i) {',
                  '    void compute(const std::vector<Poly>& input) {\n'
                  '        F4Timer compute_timer(f4_inner.compute_ns);\n'
                  '        { F4Timer timer(f4_inner.initial_ns);\n'
                  '        for (uint32_t i=0;i<input.size();++i) {')
    source = once(source, '            if (unit()) break;\n        }\n        while (!queue.empty() && !unit()) {',
                  '            if (unit()) break;\n        }\n        }\n        while (!queue.empty() && !unit()) {')
    source = once(source, '        while (!queue.empty() && !unit()) {\n'
                          '            unsigned degree=queue.top().degree;\n'
                          '            std::vector<Row> batch;',
                  '        while (!queue.empty() && !unit()) {\n'
                  '            std::vector<Row> batch;\n'
                  '            { F4Timer timer(f4_inner.pairs_ns);\n'
                  '            unsigned degree=queue.top().degree;')
    source = once(source, '            if (batch.empty()) continue;\n'
                          '            if (batch.size()>max_rows) throw Budget("native batch row budget");\n'
                          '            auto reduced=matrix(std::move(batch));',
                  '            }\n'
                  '            if (batch.empty()) continue;\n'
                  '            if (batch.size()>max_rows) throw Budget("native batch row budget");\n'
                  '            auto reduced=[&](){F4Timer timer(f4_inner.matrix_ns);\n'
                  '                return matrix(std::move(batch));}();\n'
                  '            { F4Timer timer(f4_inner.candidate_ns);')
    source = once(source, '                if (unit()) break;\n            }\n        }\n        bool changed=true;',
                  '                if (unit()) break;\n            }\n            }\n        }\n'
                  '        { F4Timer timer(f4_inner.final_ns);\n'
                  '        bool changed=true;')
    source = once(source, '        for (const auto& row:basis) basis_leads.push_back(lead(row.terms));\n'
                          '    }\n    void compact() {',
                  '        for (const auto& row:basis) basis_leads.push_back(lead(row.terms));\n'
                  '        }\n    }\n    void compact() {\n'
                  '        F4Timer timer(f4_inner.compact_ns);')
    return source


def seeded(source):
    source = once(source, '    seeded_phases = {};\n    PhaseClock phase_clock;',
                  '    seeded_phases = {};\n    f4_inner = {};\n    PhaseClock phase_clock;')
    source += '\nextern "C" const F4InnerStats* seeded_last_inner(){return &f4_inner;}\n'
    return source
