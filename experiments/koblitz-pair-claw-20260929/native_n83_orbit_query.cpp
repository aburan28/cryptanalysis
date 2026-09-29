// Bounded n=83 quotient search reusing each cross-orbit query pair sum.
// This is a stage diagnostic; Python independently verifies any exact hit.
#include "native_n83_bloom_core.hpp"

int main(int argc, char **argv) {
    try {
        need(argc == 17, "usage: native_n83_orbit_query BASE TARGET_X_ONB_HEX TARGET_Y_ONB_HEX TABLE_DESCRIPTORS QUERY_REPRESENTATIVES TABLE_BATCH TABLE_STEP TABLE_OFFSET QUERY_STEP QUERY_OFFSET BITS_PER_KEY HASHES TABLE_START QUERY_START WORKERS REPRESENTATIVE_BATCH");
        Keyer keyer;
        auto base = load_base(argv[1], keyer);
        self_test(base);
        Point target{onb_to_pb(parse_hex(argv[2])),
                     onb_to_pb(parse_hex(argv[3])), false};
        need(on_curve(target), "target off curve");
        U table_entries = std::stoull(argv[4]);
        U query_reps = std::stoull(argv[5]);
        U batch_size = std::stoull(argv[6]);
        U table_step = std::stoull(argv[7]);
        U table_offset = std::stoull(argv[8]);
        U query_step = std::stoull(argv[9]);
        U query_offset = std::stoull(argv[10]);
        unsigned bits_per_key = unsigned(std::stoul(argv[11]));
        unsigned hashes = unsigned(std::stoul(argv[12]));
        U table_start = std::stoull(argv[13]);
        U query_start = std::stoull(argv[14]);
        unsigned workers = unsigned(std::stoul(argv[15]));
        U rep_batch = std::stoull(argv[16]);
        const U d_cross = U(K) * (K - 1) / 2 * L;
        need(table_entries > 0 && table_start < d_cross &&
             table_entries <= d_cross - table_start &&
             query_reps > 0 && query_start < d_cross &&
             query_reps <= d_cross - query_start &&
             batch_size > 0 && batch_size <= 8192 &&
             rep_batch > 0 && rep_batch <= 48 &&
             workers > 0 && workers <= 64,
             "invalid bounded work");

        auto started = std::chrono::steady_clock::now();
        Bloom bloom(table_entries, bits_per_key, hashes);
        double allocation_seconds = std::chrono::duration<double>(
            std::chrono::steady_clock::now() - started).count();
        U bloom_bytes = bloom.bytes();
        std::vector<Point> left, right, sums;
        left.reserve(batch_size);
        right.reserve(batch_size);
        started = std::chrono::steady_clock::now();
        for (U position = 0; position < table_entries; position += batch_size) {
            U count = std::min(batch_size, table_entries - position);
            left.clear(); right.clear();
            for (U i = 0; i < count; ++i) {
                U rank = scheduled_rank(table_start + position + i, d_cross,
                                        table_step, table_offset);
                auto pair = cross_pair(rank);
                left.push_back(base[pair[0] * L]);
                right.push_back(base[pair[1] * L + pair[2]]);
            }
            batch_add(left, right, sums);
            for (U i = 0; i < count; ++i) {
                need(!sums[i].inf, "cross-orbit zero pair");
                bloom.insert(keyer.canonical_x(sums[i].x));
            }
        }
        double build_seconds = std::chrono::duration<double>(
            std::chrono::steady_clock::now() - started).count();

        std::array<Point, N> conjugates{};
        conjugates[0] = target;
        for (unsigned i = 1; i < N; ++i) {
            const Point &previous = conjugates[i - 1];
            conjugates[i] = {sqr(previous.x), sqr(previous.y), false};
        }
        need(sqr(conjugates[N - 1].x) == target.x &&
             sqr(conjugates[N - 1].y) == target.y,
             "target Frobenius cycle mismatch");

        struct QueryResult {
            std::vector<Candidate> candidates;
            U complement_identity = 0;
        };
        std::vector<QueryResult> results(workers);
        std::vector<std::exception_ptr> errors(workers);
        std::vector<std::thread> threads;
        U total_batches = (query_reps + rep_batch - 1) / rep_batch;
        started = std::chrono::steady_clock::now();
        for (unsigned worker = 0; worker < workers; ++worker) {
            threads.emplace_back([&, worker] {
                try {
                    std::vector<Point> qleft, qright, qsums;
                    std::vector<Point> complements_left, complements_right,
                        complements;
                    std::vector<U> encoded_positions;
                    qleft.reserve(rep_batch);
                    qright.reserve(rep_batch);
                    complements_left.reserve(rep_batch * L);
                    complements_right.reserve(rep_batch * L);
                    encoded_positions.reserve(rep_batch * L);
                    U first_batch = total_batches * worker / workers;
                    U end_batch = total_batches * (worker + 1) / workers;
                    QueryResult &result = results[worker];
                    for (U batch = first_batch; batch < end_batch; ++batch) {
                        U offset = batch * rep_batch;
                        U count = std::min(rep_batch, query_reps - offset);
                        qleft.clear(); qright.clear();
                        for (U i = 0; i < count; ++i) {
                            U position = query_start + offset + i;
                            U rank = scheduled_rank(position, d_cross,
                                                    query_step, query_offset);
                            auto pair = cross_pair(rank);
                            qleft.push_back(base[pair[0] * L]);
                            qright.push_back(base[pair[1] * L + pair[2]]);
                        }
                        batch_add(qleft, qright, qsums);
                        complements_left.clear();
                        complements_right.clear();
                        encoded_positions.clear();
                        for (U i = 0; i < count; ++i) {
                            need(!qsums[i].inf, "cross-orbit query zero pair");
                            U position = query_start + offset + i;
                            for (unsigned sign = 0; sign < 2; ++sign) {
                                Point second = sign ? qsums[i] : neg(qsums[i]);
                                for (unsigned k = 0; k < N; ++k) {
                                    complements_left.push_back(
                                        conjugates[(N - k) % N]);
                                    complements_right.push_back(second);
                                    encoded_positions.push_back(
                                        position * L + sign * N + k);
                                }
                            }
                        }
                        batch_add(complements_left, complements_right,
                                  complements);
                        for (size_t i = 0; i < complements.size(); ++i) {
                            if (complements[i].inf) {
                                ++result.complement_identity;
                                continue;
                            }
                            V key = keyer.canonical_x(complements[i].x);
                            if (bloom.contains(key))
                                result.candidates.push_back(
                                    {key, encoded_positions[i]});
                        }
                    }
                } catch (...) {
                    errors[worker] = std::current_exception();
                }
            });
        }
        for (std::thread &thread : threads) thread.join();
        for (const auto &error : errors)
            if (error) std::rethrow_exception(error);
        double query_seconds = std::chrono::duration<double>(
            std::chrono::steady_clock::now() - started).count();
        U positives = 0;
        U complement_identity = 0;
        U candidate_capacity_bytes = 0;
        for (const QueryResult &result : results) {
            positives += result.candidates.size();
            complement_identity += result.complement_identity;
            candidate_capacity_bytes +=
                U(result.candidates.capacity()) * sizeof(Candidate);
        }

        bloom.release();
        started = std::chrono::steady_clock::now();
        CandidateTable exact{size_t(positives)};
        for (const QueryResult &result : results)
            for (const Candidate &candidate : result.candidates)
                exact.insert(candidate);
        U exact_hit_keys = 0;
        if (positives) {
            for (U position = 0; position < table_entries;
                 position += batch_size) {
                U count = std::min(batch_size, table_entries - position);
                left.clear(); right.clear();
                for (U i = 0; i < count; ++i) {
                    U rank = scheduled_rank(table_start + position + i,
                                            d_cross, table_step, table_offset);
                    auto pair = cross_pair(rank);
                    left.push_back(base[pair[0] * L]);
                    right.push_back(base[pair[1] * L + pair[2]]);
                }
                batch_add(left, right, sums);
                for (U i = 0; i < count; ++i) {
                    if (sums[i].inf) continue;
                    V key = keyer.canonical_x(sums[i].x);
                    CandidateSlot *entry = exact.find(key);
                    if (entry && entry->table_position == U(-1)) {
                        entry->table_position = table_start + position + i;
                        ++exact_hit_keys;
                    }
                }
            }
        }
        U exact_hit_queries = 0;
        std::vector<Candidate> hit_samples;
        for (const QueryResult &result : results)
            for (const Candidate &candidate : result.candidates) {
                CandidateSlot *entry = exact.find(candidate.key);
                need(entry != nullptr, "missing Bloom-positive query");
                if (entry->table_position == U(-1)) continue;
                ++exact_hit_queries;
                if (hit_samples.size() < 16)
                    hit_samples.push_back(candidate);
            }
        double replay_seconds = std::chrono::duration<double>(
            std::chrono::steady_clock::now() - started).count();
        struct rusage usage{};
        getrusage(RUSAGE_SELF, &usage);
        std::cout << "{\"actual_B\":" << base.size()
                  << ",\"table_descriptors\":" << table_entries
                  << ",\"table_start\":" << table_start
                  << ",\"query_representatives\":" << query_reps
                  << ",\"query_start\":" << query_start
                  << ",\"lifted_query_pairs\":" << query_reps * L
                  << ",\"query_workers\":" << workers
                  << ",\"representative_batch\":" << rep_batch
                  << ",\"table_batch\":" << batch_size
                  << ",\"bloom_bits_per_key\":" << bits_per_key
                  << ",\"bloom_hashes\":" << hashes
                  << ",\"bloom_bytes\":" << bloom_bytes
                  << ",\"candidate_vector_capacity_bytes\":"
                  << candidate_capacity_bytes
                  << ",\"bloom_positive_queries\":" << positives
                  << ",\"duplicate_positive_keys\":"
                  << exact.duplicate_keys
                  << ",\"exact_hit_keys\":" << exact_hit_keys
                  << ",\"exact_hit_queries\":" << exact_hit_queries
                  << ",\"false_positive_queries\":"
                  << positives - exact_hit_queries
                  << ",\"complement_identity_queries\":"
                  << complement_identity
                  << ",\"allocation_seconds\":" << std::setprecision(12)
                  << allocation_seconds
                  << ",\"build_seconds\":" << build_seconds
                  << ",\"query_seconds\":" << query_seconds
                  << ",\"exact_replay_seconds\":" << replay_seconds
                  << ",\"peak_rss_bytes\":" << usage.ru_maxrss
                  << ",\"hits\":[";
        for (size_t i = 0; i < hit_samples.size(); ++i) {
            if (i) std::cout << ',';
            const Candidate &candidate = hit_samples[i];
            const CandidateSlot *entry = exact.find(candidate.key);
            U rep_position = candidate.query_position / L;
            unsigned lift = unsigned(candidate.query_position % L);
            std::cout << "{\"query_representative_position\":"
                      << rep_position
                      << ",\"frobenius_shift\":" << (lift % N)
                      << ",\"negative_query_pair\":"
                      << (lift >= N ? "true" : "false")
                      << ",\"table_position\":"
                      << entry->table_position
                      << ",\"x_key_hex\":\"" << hex(candidate.key)
                      << "\"}";
        }
        std::cout << "]}" << std::endl;
    } catch (const std::exception &e) {
        std::cerr << e.what() << std::endl;
        return 1;
    }
}
