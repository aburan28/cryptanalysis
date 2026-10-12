// Frozen Bloom/key data structures for the query-orbit stage.
#pragma once
// Bounded, memory-conscious n=83 quotient-key filter and exact replay.
// The Bloom filter is only a candidate screen. Every positive query key is
// checked against a second, exact pass over the deterministic table schedule.
#define main native_pair_stage_main
#include "native_n83_pairs.cpp"
#undef main

#include <sys/resource.h>
#include <thread>

struct alignas(64) BloomBlock { std::array<U, 8> word{}; };
static_assert(sizeof(BloomBlock) == 64, "Bloom block must be one cache line");

U mix64(U x) {
    x ^= x >> 30;
    x *= 0xbf58476d1ce4e5b9ull;
    x ^= x >> 27;
    x *= 0x94d049bb133111ebull;
    return x ^ (x >> 31);
}
U hash83(V key) {
    return mix64(U(key) ^ mix64(U(key >> 64) +
                              0x9e3779b97f4a7c15ull));
}

struct Bloom {
    std::vector<BloomBlock> blocks;
    unsigned hashes;
    Bloom(U entries, unsigned bits_per_key, unsigned hash_count)
        : hashes(hash_count) {
        need(bits_per_key >= 8 && bits_per_key <= 64 &&
             hash_count >= 1 && hash_count <= 32,
             "invalid Bloom parameters");
        U count = (entries * bits_per_key + 511) / 512 + 1024;
        need(count > 0 && count <= SIZE_MAX / sizeof(BloomBlock),
             "Bloom size overflow");
        blocks.resize(size_t(count));
    }
    template <typename F> void positions(V key, F action) const {
        U h = hash83(key);
        size_t block0 = size_t(h % blocks.size());
        size_t block1 = size_t(mix64(h ^ 0xbb67ae8584caa73bull) %
                               blocks.size());
        U stream = h ^ 0x6a09e667f3bcc909ull;
        for (unsigned j = 0; j < hashes; ++j) {
            stream += 0x9e3779b97f4a7c15ull;
            action((j & 1) ? block1 : block0,
                   unsigned(mix64(stream) & 511));
        }
    }
    void insert(V key) {
        positions(key, [&](size_t b, unsigned bit) {
            blocks[b].word[bit >> 6] |= U(1) << (bit & 63);
        });
    }
    bool contains(V key) const {
        bool found = true;
        positions(key, [&](size_t b, unsigned bit) {
            found &= bool(blocks[b].word[bit >> 6] &
                          (U(1) << (bit & 63)));
        });
        return found;
    }
    U bytes() const { return U(blocks.size()) * sizeof(BloomBlock); }
    void release() { std::vector<BloomBlock>().swap(blocks); }
};

struct __attribute__((packed)) Candidate { V key; U query_position; };
static_assert(sizeof(Candidate) == 24, "candidate record layout changed");
struct __attribute__((packed)) CandidateSlot {
    U lo = 0;
    uint32_t hi = 0xffffffffu;
    U query_position = 0;
    U table_position = U(-1);
};
static_assert(sizeof(CandidateSlot) == 28, "candidate slot layout changed");

struct CandidateTable {
    std::vector<CandidateSlot> slots;
    U duplicate_keys = 0;
    explicit CandidateTable(size_t count) {
        size_t capacity = count * 10 / 7 + 1024;
        need(capacity > count, "candidate table capacity overflow");
        slots.assign(capacity, CandidateSlot{});
    }
    CandidateSlot &slot(V key) {
        size_t position = size_t(hash83(key) % slots.size());
        U lo = U(key);
        uint32_t hi = uint32_t(key >> 64);
        for (size_t probes = 0; probes < slots.size(); ++probes) {
            CandidateSlot &entry = slots[position];
            if (entry.hi == 0xffffffffu ||
                (entry.lo == lo && entry.hi == hi))
                return entry;
            if (++position == slots.size()) position = 0;
        }
        throw std::runtime_error("candidate table full");
    }
    void insert(Candidate candidate) {
        CandidateSlot &entry = slot(candidate.key);
        if (entry.hi != 0xffffffffu) { ++duplicate_keys; return; }
        entry.lo = U(candidate.key);
        entry.hi = uint32_t(candidate.key >> 64);
        entry.query_position = candidate.query_position;
    }
    CandidateSlot *find(V key) {
        CandidateSlot &entry = slot(key);
        return entry.hi == 0xffffffffu ? nullptr : &entry;
    }
};
