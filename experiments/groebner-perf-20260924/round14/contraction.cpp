// Execute fixed field-linear contraction edges; no curve or solver arithmetic.
#include <algorithm>
#include <cstdint>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <string>
#include <vector>

struct Edge { uint32_t source, destination, table; };
struct Value { uint64_t lo=0, hi=0; };
struct Plan {
    uint32_t equations=0, limbs=0, bytes=0;
    std::vector<uint32_t> sizes, offsets, masks;
    std::vector<Edge> edges;
    std::vector<uint64_t> tables;
    std::vector<std::vector<Value>> buffers;
    std::mutex lock;
};
static thread_local std::string error;
static void require(bool condition, const char* message) {
    if (!condition) throw std::invalid_argument(message);
}
static bool in_field(uint64_t high, uint32_t equations) {
    unsigned used=equations%64;
    return !used || !(high>>used);
}
extern "C" {
const char* contraction_error() { return error.c_str(); }
void* contraction_create(uint32_t equations, uint32_t nvars, uint32_t stages,
                         const uint32_t* sizes, const uint32_t* offsets,
                         const Edge* edges, uint32_t edge_count,
                         const uint64_t* tables, uint64_t table_words,
                         uint32_t table_count, const uint32_t* masks) {
    try {
        error.clear();
        require(equations>=1 && equations<=128 && nvars>=1 && nvars<=20,
                "field/equation or Boolean-variable bounds");
        require(stages>=1 && stages<=4 && sizes && offsets && masks,
                "stage bounds or missing layout");
        require(edge_count<=1000000 && (!edge_count || edges), "edge bounds");
        const uint32_t limbs=(equations+63)/64, bytes=(equations+7)/8;
        const uint64_t expected=uint64_t(table_count)*bytes*256*limbs;
        require(expected==table_words && table_words<=32*1024*1024 &&
                (!table_words || tables), "table dimensions or 256 MiB limit");
        require(offsets[0]==0 && offsets[stages]==edge_count, "edge offsets");
        uint64_t slots=0;
        for (uint32_t i=0;i<=stages;++i) {
            require(sizes[i]>0 && sizes[i]<=1000000, "buffer size");
            slots+=sizes[i];
        }
        require(slots<=2000000, "total scratch bound");
        for (uint32_t i=0;i<stages;++i) {
            require(offsets[i]<=offsets[i+1] && offsets[i+1]<=edge_count,
                    "nonmonotone edge offsets");
            for (uint32_t j=offsets[i];j<offsets[i+1];++j)
                require(edges[j].source<sizes[i] && edges[j].destination<sizes[i+1]
                        && edges[j].table<table_count, "edge outside layout");
        }
        for (uint64_t j=limbs-1;j<table_words;j+=limbs)
            require(in_field(tables[j],equations), "table value outside field");
        std::vector<uint32_t> ordered(masks,masks+sizes[stages]);
        for (auto mask:ordered) require(mask<(uint32_t(1)<<nvars), "monomial outside ring");
        std::sort(ordered.begin(),ordered.end());
        require(std::adjacent_find(ordered.begin(),ordered.end())==ordered.end(),
                "duplicate final monomials");
        auto p=std::make_unique<Plan>();
        p->equations=equations; p->limbs=limbs; p->bytes=bytes;
        p->sizes.assign(sizes,sizes+stages+1); p->offsets.assign(offsets,offsets+stages+1);
        if (edge_count) p->edges.assign(edges,edges+edge_count);
        if (table_words) p->tables.assign(tables,tables+table_words);
        p->masks.assign(masks,masks+sizes[stages]);
        for (auto size:p->sizes) p->buffers.emplace_back(size);
        return p.release();
    } catch (const std::exception& e) { error=e.what(); return nullptr; }
    catch (...) { error="unknown contraction construction failure"; return nullptr; }
}
void contraction_destroy(void* handle) { delete static_cast<Plan*>(handle); }
int contraction_compute(void* handle, const uint64_t* initial, uint64_t initial_words,
                        uint32_t* output_masks, uint64_t* output_coefficients,
                        uint32_t capacity, uint32_t* count) {
    if (count) *count=0;
    try {
        error.clear();
        auto* p=static_cast<Plan*>(handle);
        require(p && initial && output_masks && output_coefficients && count,
                "missing compute buffer");
        std::lock_guard<std::mutex> guard(p->lock);
        require(initial_words==uint64_t(p->sizes[0])*p->limbs &&
                capacity>=p->sizes.back(), "compute buffer dimensions");
        for (uint64_t j=p->limbs-1;j<initial_words;j+=p->limbs)
            require(in_field(initial[j],p->equations), "initial value outside field");
        // Every numeric slot is reset, including slots unreachable for this target.
        for (auto& buffer:p->buffers) std::fill(buffer.begin(),buffer.end(),Value{});
        for (uint32_t i=0;i<p->sizes[0];++i) {
            p->buffers[0][i].lo=initial[uint64_t(i)*p->limbs];
            if (p->limbs==2) p->buffers[0][i].hi=initial[uint64_t(i)*2+1];
        }
        const uint64_t stride=uint64_t(p->bytes)*256*p->limbs;
        for (uint32_t stage=0;stage+1<p->sizes.size();++stage) {
            const auto& source=p->buffers[stage]; auto& destination=p->buffers[stage+1];
            for (uint32_t j=p->offsets[stage];j<p->offsets[stage+1];++j) {
                const auto& edge=p->edges[j]; Value value=source[edge.source];
                if (!(value.lo|value.hi)) continue;
                auto& target=destination[edge.destination];
                const auto* table=p->tables.data()+uint64_t(edge.table)*stride;
                for (uint32_t byte=0;byte<p->bytes;++byte) {
                    uint64_t word=byte<8 ? value.lo : value.hi;
                    uint32_t digit=(word>>(8*(byte%8)))&255;
                    uint64_t offset=(uint64_t(byte)*256+digit)*p->limbs;
                    target.lo^=table[offset];
                    if (p->limbs==2) target.hi^=table[offset+1];
                }
            }
        }
        uint32_t used=0;
        for (uint32_t i=0;i<p->sizes.back();++i) {
            Value value=p->buffers.back()[i];
            if (!(value.lo|value.hi)) continue;
            output_masks[used]=p->masks[i];
            output_coefficients[uint64_t(used)*p->limbs]=value.lo;
            if (p->limbs==2) output_coefficients[uint64_t(used)*2+1]=value.hi;
            ++used;
        }
        *count=used;
        return 0;
    } catch (const std::invalid_argument& e) { error=e.what(); return 1; }
    catch (const std::exception& e) { error=e.what(); return 2; }
    catch (...) { error="unknown contraction failure"; return 2; }
}
}
