// One canonical signed-Frobenius orbit per record, expanded only on access.
// This replaces the eager 166-point expansion in native_n83_pairs_portable.cpp.
struct CompactBase {
    std::vector<std::array<V, 2>> cycle_representatives;
    std::vector<Point> canonical_points;
    std::array<std::array<F, 256>, (N + 7) / 8> cycle_byte_to_pb{};

    explicit CompactBase(const Keyer &keyer) {
        cycle_representatives.reserve(K);
        canonical_points.reserve(K);
        std::array<F, N> images{};
        for (unsigned bit = 0; bit < N; ++bit)
            images[bit] = onb_to_pb(V(1) << keyer.coord_at_cycle[bit]);
        for (unsigned byte = 0; byte < cycle_byte_to_pb.size(); ++byte) {
            for (unsigned value = 1; value < 256; ++value) {
                unsigned low = value & -value;
                unsigned bit = 8 * byte + unsigned(__builtin_ctz(low));
                cycle_byte_to_pb[byte][value] =
                    cycle_byte_to_pb[byte][value ^ low] ^
                    (bit < N ? images[bit] : F{});
            }
        }
    }

    static V rotate(V value, unsigned shift) {
        return shift ? ((value << shift) | (value >> (N - shift))) & CYCLE_MASK
                     : value;
    }

    F to_pb(V cycle) const {
        F value{};
        for (unsigned byte = 0; byte < cycle_byte_to_pb.size(); ++byte)
            value = value ^ cycle_byte_to_pb[byte][unsigned((cycle >> (8 * byte)) & 255)];
        return value;
    }

    Point operator[](size_t index) const {
        need(index < size(), "compact base index out of range");
        unsigned orbit = unsigned(index / L);
        unsigned within = unsigned(index % L);
        unsigned shift = within % N;
        if (shift == 0) {
            Point point = canonical_points[orbit];
            return within >= N ? neg(point) : point;
        }
        const auto &entry = cycle_representatives[orbit];
        F x = to_pb(rotate(entry[0], shift));
        F y = to_pb(rotate(entry[1], shift));
        if (within >= N) y = y ^ x;
        return {x, y, false};
    }

    size_t size() const { return cycle_representatives.size() * L; }
    size_t storage_bytes() const {
        return cycle_representatives.capacity() * sizeof(cycle_representatives[0]) +
               canonical_points.capacity() * sizeof(canonical_points[0]) +
               sizeof(cycle_byte_to_pb);
    }
};

CompactBase load_base(const std::string &path, const Keyer &keyer) {
    std::ifstream in(path, std::ios::binary);
    need(bool(in), "missing base file");
    CompactBase result(keyer);
    for (unsigned orbit = 0; orbit < K; ++orbit) {
        unsigned char record[32];
        in.read(reinterpret_cast<char *>(record), 32);
        need(bool(in), "short base file");
        auto key_bit = [&](unsigned i) -> unsigned {
            return (record[i >> 3] >> (i & 7)) & 1;
        };
        V xc = 0, yc = 0;
        for (unsigned j = 0; j < N; ++j) {
            xc |= V(key_bit(N + j)) << j;
            yc |= V(key_bit(j)) << j;
        }
        result.cycle_representatives.push_back({xc, yc});
        result.canonical_points.push_back({result.to_pb(xc), result.to_pb(yc), false});
        if (orbit < 8) {
            need(on_curve(result[orbit * L]), "base representative off curve");
            Point first = result[orbit * L];
            Point last = first;
            for (unsigned j = 1; j < N; ++j) {
                last = {sqr(last.x), sqr(last.y), false};
                need(result[orbit * L + j].x == last.x &&
                     result[orbit * L + j].y == last.y,
                     "compact Frobenius expansion mismatch");
            }
            need(result[orbit * L + N].x == first.x &&
                 result[orbit * L + N].y == neg(first).y,
                 "compact signed expansion mismatch");
        }
    }
    char extra;
    need(!in.read(&extra, 1), "base file has extra bytes");
    return result;
}
