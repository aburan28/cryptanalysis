"""Batch initial F4 generators into one certificate-carrying Macaulay matrix."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENGINE_SHA256 = "fc14e10624361a7708d8034cbae59b915228b0a85553e20ca1f6741ab3199c4b"


def batched_engine(source):
    old = '''    void compute(const std::vector<Poly>& input) {
        for (uint32_t i=0;i<input.size();++i) {
            Row row=normal({input[i],emit(0,i)},basis);
            if (!row.terms.empty()) install(std::move(row));
            if (unit()) break;
        }
        while (!queue.empty() && !unit()) {'''
    new = '''    void compute(const std::vector<Poly>& input) {
        if (input.size() >= 8) {
            std::vector<Row> initial;
            initial.reserve(input.size());
            for (uint32_t i=0;i<input.size();++i)
                if (!input[i].empty()) initial.push_back({input[i],emit(0,i)});
            if (initial.size() > max_rows) throw Budget("native initial matrix row budget");
            if (!initial.empty()) {
                auto reduced=matrix(std::move(initial));
                for (auto& row:reduced) if (!row.terms.empty()) install(std::move(row));
            }
        } else {
            for (uint32_t i=0;i<input.size();++i) {
                Row row=normal({input[i],emit(0,i)},basis);
                if (!row.terms.empty()) install(std::move(row));
                if (unit()) break;
            }
        }
        while (!queue.empty() && !unit()) {'''
    assert source.count(old) == 1
    return source.replace(old, new, 1)
