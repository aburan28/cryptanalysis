// Q1512: exact raw-x Bloom prefilter before canonical Frobenius membership.
// A Bloom negative cannot hide an exact hit: every x in the signed orbit
// base is inserted before scanning; positives still use the exact key set.
#define main q1502_parent_main
#include "../q20261012_native_rational_guard/native_n83_pairs.cpp"
#undef main
#include <sys/resource.h>
#include <unordered_set>

struct VHash {
    size_t operator()(V x) const {
        U lo = U(x), hi = U(x >> 64);
        return size_t((lo ^ (hi * 0x9e3779b97f4a7c15ull)) *
                      0xbf58476d1ce4e5b9ull);
    }
};

U mix64(U x) {
    x ^= x >> 30; x *= 0xbf58476d1ce4e5b9ull;
    x ^= x >> 27; x *= 0x94d049bb133111ebull;
    return x ^ (x >> 31);
}

struct RawXBloom {
    std::vector<U> words;
    U mask = 0;
    unsigned hashes = 0;
    RawXBloom(unsigned log2bits, unsigned k) : hashes(k) {
        if (!log2bits) { need(k == 0, "baseline hash count"); return; }
        need(log2bits >= 20 && log2bits <= 30, "bad bloom size");
        need(k >= 2 && k <= 12, "bad bloom hash count");
        words.resize(U(1) << (log2bits - 6));
        mask = (U(1) << log2bits) - 1;
    }
    std::array<U, 2> locations(F x) const {
        U a = mix64(x.a ^ (x.b * 0x9e3779b97f4a7c15ull));
        U b = mix64(x.b ^ (x.a * 0xd6e8feb86659fd93ull) ^ 0x83a1315f25e7ull);
        return {a, b | 1};
    }
    void insert(F x) {
        auto [a, b] = locations(x);
        for (unsigned i = 0; i < hashes; ++i) {
            U bit = (a + i * b) & mask;
            words[bit >> 6] |= U(1) << (bit & 63);
        }
    }
    bool may_contain(F x, U *probes = nullptr) const {
        if (words.empty()) return true;
        auto [a, b] = locations(x);
        for (unsigned i = 0; i < hashes; ++i) {
            U bit = (a + i * b) & mask;
            if (probes) ++*probes;
            if (!(words[bit >> 6] & (U(1) << (bit & 63)))) return false;
        }
        return true;
    }
};

V raw_x(F x) { return V(x.a) | (V(x.b) << 64); }

std::vector<Point> load_base_21(const std::string &path, const Keyer &keyer) {
    std::ifstream in(path, std::ios::binary);
    need(bool(in), "missing base file");
    std::vector<Point> result(K * L);
    for (unsigned orbit = 0; orbit < K; ++orbit) {
        unsigned char record[21];
        in.read(reinterpret_cast<char *>(record), 21);
        need(bool(in), "short 21-byte base file");
        auto bit = [&](unsigned i) { return (record[i >> 3] >> (i & 7)) & 1; };
        V xc = 0, yc = 0;
        for (unsigned j = 0; j < N; ++j) {
            xc |= V(bit(N + j)) << keyer.coord_at_cycle[j];
            yc |= V(bit(j)) << keyer.coord_at_cycle[j];
        }
        Point p{onb_to_pb(xc), onb_to_pb(yc), false};
        if (orbit < 8) need(on_curve(p), "base representative off curve");
        for (unsigned j = 0; j < N; ++j) {
            result[orbit * L + j] = p;
            result[orbit * L + N + j] = neg(p);
            p = {sqr(p.x), sqr(p.y), false};
        }
    }
    char extra;
    need(!in.read(&extra, 1), "base file has extra bytes");
    return result;
}

int main(int argc, char **argv) {
    try {
        need(argc == 8, "usage: native_prefilter BASE RX RY PAIRS BATCH_PAIRS BLOOM_LOG2_BITS BLOOM_HASHES");
        Keyer keyer;
        auto start = std::chrono::steady_clock::now();
        auto base = load_base_21(argv[1], keyer);
        self_test(base);
        std::unordered_set<V, VHash> xkeys;
        xkeys.reserve(K * 2);
        for (unsigned orbit = 0; orbit < K; ++orbit)
            need(xkeys.insert(keyer.canonical_x(base[orbit * L].x)).second,
                 "duplicate canonical base x");
        unsigned bloom_log2_bits = std::stoul(argv[6]);
        unsigned bloom_hashes = std::stoul(argv[7]);
        RawXBloom bloom(bloom_log2_bits, bloom_hashes);
        if (bloom_log2_bits) {
            for (unsigned orbit = 0; orbit < K; ++orbit)
                for (unsigned j = 0; j < N; ++j)
                    bloom.insert(base[orbit * L + j].x);
            for (unsigned orbit = 0; orbit < K; orbit += 1237)
                for (unsigned j : {0u, 1u, 41u, 82u})
                    need(bloom.may_contain(base[orbit * L + j].x),
                         "Bloom false negative on base control");
        }
        Point r{onb_to_pb(parse_hex(argv[2])),
                onb_to_pb(parse_hex(argv[3])), false};
        need(on_curve(r), "complement off curve");
        U pair_limit = std::stoull(argv[4]);
        U batch = std::stoull(argv[5]);
        need(pair_limit > 0 && pair_limit <= U(K) * N, "bad pair limit");
        need(batch > 0 && batch <= 8192, "bad pair batch");
        double setup = std::chrono::duration<double>(
            std::chrono::steady_clock::now() - start).count();
        start = std::chrono::steady_clock::now();
        U hits = 0, exceptional = 0, bloom_positives = 0, canonical_calls = 0;
        U bloom_scan_probes = 0;
        V raw_checksum = 0, hit_key_checksum = 0;
        std::vector<F> denominator(batch), prefix(batch);
        std::vector<Point> positive(batch);
        for (U pos = 0; pos < pair_limit; pos += batch) {
            U count = std::min(batch, pair_limit - pos);
            F product = one();
            for (U i = 0; i < count; ++i) {
                U rank = pos + i;
                positive[i] = base[(rank / N) * L + (rank % N)];
                F d = r.x ^ positive[i].x;
                if (zero(d)) { ++exceptional; d = one(); }
                denominator[i] = d;
                prefix[i] = product;
                product = mul(product, d);
            }
            F inverse_product = inv(product);
            for (U i = count; i-- > 0;) {
                F inverse_d = mul(inverse_product, prefix[i]);
                inverse_product = mul(inverse_product, denominator[i]);
                Point p = positive[i];
                Point qminus, qplus;
                F slope_minus{}, slope_plus{};
                if (r.x == p.x) {
                    qminus = add(r, neg(p));
                    qplus = add(r, p);
                } else {
                    slope_minus = mul(r.y ^ p.y ^ p.x, inverse_d);
                    slope_plus = mul(r.y ^ p.y, inverse_d);
                    F xm = sqr(slope_minus) ^ slope_minus ^ (r.x ^ p.x);
                    F xp = sqr(slope_plus) ^ slope_plus ^ (r.x ^ p.x);
                    qminus = {xm, F{}, false};
                    qplus = {xp, F{}, false};
                }
                Point outputs[2] = {qminus, qplus};
                for (unsigned sign = 0; sign < 2; ++sign) {
                    Point q = outputs[sign];
                    if (q.inf) continue;
                    raw_checksum ^= raw_x(q.x);
                    if (!bloom.may_contain(q.x, &bloom_scan_probes)) continue;
                    ++bloom_positives;
                    V key = keyer.canonical_x(q.x);
                    ++canonical_calls;
                    if (xkeys.count(key)) {
                        ++hits;
                        hit_key_checksum ^= key;
                        if (!(r.x == p.x)) {
                            F slope = sign ? slope_plus : slope_minus;
                            q.y = mul(slope, r.x ^ q.x) ^ q.x ^ r.y;
                        }
                        Point replay = add(sign ? neg(p) : p, q);
                        need(!replay.inf && replay.x == r.x && replay.y == r.y,
                             "signed complement replay failed");
                        std::cout << "hit " << (pos + i) << " " << sign
                                  << " " << hex(key) << "\n";
                    }
                }
            }
        }
        double scan = std::chrono::duration<double>(
            std::chrono::steady_clock::now() - start).count();
        struct rusage usage{};
        getrusage(RUSAGE_SELF, &usage);
        std::cout << "{\"actual_B\":" << base.size()
                  << ",\"folded_K\":" << K
                  << ",\"scanned\":" << 2 * pair_limit
                  << ",\"batch_pairs\":" << batch
                  << ",\"hits\":" << hits
                  << ",\"exceptional_pairs\":" << exceptional
                  << ",\"bloom_log2_bits\":" << bloom_log2_bits
                  << ",\"bloom_hashes\":" << bloom_hashes
                  << ",\"bloom_bytes\":" << bloom.words.size() * sizeof(U)
                  << ",\"bloom_build_bit_sets\":" << U(K) * N * bloom_hashes
                  << ",\"bloom_scan_bit_probes\":" << bloom_scan_probes
                  << ",\"bloom_positives\":" << bloom_positives
                  << ",\"canonical_calls\":" << canonical_calls
                  << ",\"peak_rss_raw\":" << usage.ru_maxrss
                  << ",\"peak_rss_units\":\"bytes on Darwin, KiB on Linux\""
                  << ",\"raw_x_checksum_hex\":\"" << hex(raw_checksum)
                  << "\",\"hit_key_checksum_hex\":\"" << hex(hit_key_checksum)
                  << "\",\"setup_seconds\":" << setup
                  << ",\"scan_seconds\":" << scan << "}\n";
    } catch (const std::exception &e) {
        std::cerr << e.what() << "\n";
        return 1;
    }
    return 0;
}
