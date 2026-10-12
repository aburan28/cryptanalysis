// Exact complementary-pair scan over the enumerated signed Frobenius base.
#define main q1501_parent_main
#include "../q20261012_native_rational_guard/native_n83_pairs.cpp"
#undef main
#include <unordered_set>

struct VHash {
    size_t operator()(V x) const {
        U lo = U(x), hi = U(x >> 64);
        return size_t((lo ^ (hi * 0x9e3779b97f4a7c15ull)) *
                      0xbf58476d1ce4e5b9ull);
    }
};

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
        need(argc == 6, "usage: native_probe BASE RX RY LIMIT BATCH");
        Keyer keyer;
        auto start = std::chrono::steady_clock::now();
        auto base = load_base_21(argv[1], keyer);
        self_test(base);
        std::unordered_set<V, VHash> xkeys;
        xkeys.reserve(K * 2);
        for (unsigned orbit = 0; orbit < K; ++orbit)
            need(xkeys.insert(keyer.canonical_x(base[orbit * L].x)).second,
                 "duplicate canonical base x");
        Point r{onb_to_pb(parse_hex(argv[2])),
                onb_to_pb(parse_hex(argv[3])), false};
        need(on_curve(r), "complement off curve");
        U limit = std::stoull(argv[4]), batch = std::stoull(argv[5]);
        need(limit > 0 && limit <= base.size(), "bad scan limit");
        need(batch > 0 && batch <= 8192, "bad batch size");
        double setup = std::chrono::duration<double>(
            std::chrono::steady_clock::now() - start).count();
        start = std::chrono::steady_clock::now();
        std::vector<Point> left, right, out;
        U hits = 0, exceptional = 0;
        V checksum = 0;
        for (U pos = 0; pos < limit; pos += batch) {
            U count = std::min(batch, limit - pos);
            left.clear(); right.clear();
            for (U i = 0; i < count; ++i) {
                left.push_back(r);
                right.push_back(neg(base[pos + i]));
            }
            batch_add(left, right, out);
            for (U i = 0; i < count; ++i) {
                if (out[i].inf) { ++exceptional; continue; }
                V key = keyer.canonical_x(out[i].x);
                checksum ^= key;
                if (xkeys.count(key)) {
                    ++hits;
                    Point replay = add(base[pos + i], out[i]);
                    need(!replay.inf && replay.x == r.x && replay.y == r.y,
                         "complement group replay failed");
                    std::cout << "hit " << (pos + i) << " " << hex(key)
                              << " " << hex(V(out[i].x.a) | (V(out[i].x.b) << 64))
                              << "\n";
                }
            }
        }
        double scan = std::chrono::duration<double>(
            std::chrono::steady_clock::now() - start).count();
        std::cout << "{\"actual_B\":" << base.size()
                  << ",\"folded_K\":" << K
                  << ",\"scanned\":" << limit
                  << ",\"batch\":" << batch
                  << ",\"hits\":" << hits
                  << ",\"exceptional\":" << exceptional
                  << ",\"checksum_hex\":\"" << hex(checksum)
                  << "\",\"setup_seconds\":" << setup
                  << ",\"scan_seconds\":" << scan << "}\n";
    } catch (const std::exception &e) {
        std::cerr << e.what() << "\n";
        return 1;
    }
    return 0;
}
