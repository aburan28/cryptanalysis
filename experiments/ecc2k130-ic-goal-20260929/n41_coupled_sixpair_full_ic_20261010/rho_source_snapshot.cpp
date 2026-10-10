// One-target Pollard rho on the exact N41 public point, modulo signed Frobenius.
#include <sys/resource.h>
#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <string>
#include <unordered_map>
#include <vector>

#define main unused_three_pair_s7_main
#include "../koblitz-s5-invariant-20260924/three_pair_s7_native.cpp"
#undef main

constexpr uint64_t RHO_JUMPS = 16;
constexpr uint64_t RHO_STEP_CAP = 20'000'000;
constexpr uint64_t RHO_WALL_CAP_NS = 120'000'000'000ULL;
constexpr uint64_t RHO_RSS_CAP_BYTES = 4ULL * 1024 * 1024 * 1024;

struct RhoState {
    Point point;
    uint64_t a = 0, b = 0;
};

struct RhoJump {
    Point point;
    uint64_t a = 0, b = 0;
};

static uint64_t elapsed_ns(std::chrono::steady_clock::time_point start) {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now() - start).count();
}

static uint64_t peak_rss_bytes() {
    rusage usage{};
    if (getrusage(RUSAGE_SELF, &usage) != 0) return 0;
#if defined(__APPLE__)
    return uint64_t(usage.ru_maxrss);
#else
    return uint64_t(usage.ru_maxrss) * 1024;
#endif
}

static uint64_t add_mod(uint64_t left, uint64_t right, uint64_t modulus) {
    return uint64_t((U128(left) + right) % modulus);
}

static uint64_t sub_mod(uint64_t left, uint64_t right, uint64_t modulus) {
    return left >= right ? left - right : modulus - (right - left);
}

static uint64_t mul_mod(uint64_t left, uint64_t right, uint64_t modulus) {
    return uint64_t((U128(left) * right) % modulus);
}

static uint64_t inverse_mod(uint64_t value, uint64_t modulus) {
    __int128 old_r = value, r = modulus;
    __int128 old_s = 1, s = 0;
    while (r != 0) {
        const __int128 quotient = old_r / r;
        const __int128 next_r = old_r - quotient * r;
        old_r = r;
        r = next_r;
        const __int128 next_s = old_s - quotient * s;
        old_s = s;
        s = next_s;
    }
    if (old_r != 1) throw std::runtime_error("rho collision denominator is not invertible");
    old_s %= modulus;
    if (old_s < 0) old_s += modulus;
    return uint64_t(old_s);
}

static bool invertible_mod(uint64_t value, uint64_t modulus) {
    while (value != 0) {
        const uint64_t remainder = modulus % value;
        modulus = value;
        value = remainder;
    }
    return modulus == 1;
}

static uint64_t splitmix64(uint64_t& state) {
    uint64_t value = (state += 0x9e3779b97f4a7c15ULL);
    value = (value ^ (value >> 30)) * 0xbf58476d1ce4e5b9ULL;
    value = (value ^ (value >> 27)) * 0x94d049bb133111ebULL;
    return value ^ (value >> 31);
}

static Point frobenius(Point point) {
    if (point.infinity) return point;
    return finite(sq(point.x), sq(point.y));
}

static bool point_less(Point left, Point right) {
    if (left.infinity != right.infinity) return left.infinity;
    if (left.infinity) return false;
    if (left.x != right.x) return left.x < right.x;
    return left.y < right.y;
}

static Point scalar_mul(Point point, uint64_t scalar) {
    Point result;
    while (scalar) {
        if (scalar & 1) result = add(result, point);
        scalar >>= 1;
        if (scalar) point = add(point, point);
    }
    return result;
}

static RhoState canonicalize(RhoState state, uint64_t r,
                             const std::array<uint64_t, 41>& lambda_powers) {
    Point current = state.point;
    Point best = current;
    uint64_t best_factor = 1;
    for (uint64_t shift = 0; shift < 41; ++shift) {
        if (point_less(current, best)) {
            best = current;
            best_factor = lambda_powers[shift];
        }
        const Point negative = neg(current);
        if (point_less(negative, best)) {
            best = negative;
            best_factor = lambda_powers[shift] == 0
                ? 0 : r - lambda_powers[shift];
        }
        if (shift != 40) current = frobenius(current);
    }
    state.point = best;
    state.a = mul_mod(best_factor, state.a, r);
    state.b = mul_mod(best_factor, state.b, r);
    return state;
}

static uint64_t stable_partition(Point point) {
    uint64_t value = point.x ^ (point.y + 0x9e3779b97f4a7c15ULL +
                                (point.x << 6) + (point.x >> 2));
    value ^= uint64_t(point.infinity) * 0x517cc1b727220a95ULL;
    value ^= value >> 33;
    value *= 0xff51afd7ed558ccdULL;
    value ^= value >> 33;
    return value % RHO_JUMPS;
}

int main(int argc, char** argv) {
    try {
        if (argc != 3) throw std::runtime_error(
            "usage: n41_signed_frobenius_rho input.txt result.json");
        std::ifstream input(argv[1]);
        if (!input) throw std::runtime_error("cannot open one-target rho input");
        uint64_t qx, qy, gx, gy, r, lambda, seed;
        input >> qx >> qy >> gx >> gy >> r >> lambda >> seed;
        if (!input || r == 0 || lambda >= r) throw std::runtime_error("bad rho header");
        std::string extra;
        if (input >> extra) throw std::runtime_error("trailing rho input");
        const Point target = finite(qx, qy);
        const Point generator = finite(gx, gy);
        if (!on_curve(target) || !on_curve(generator))
            throw std::runtime_error("rho target or generator is off curve");
        std::array<uint64_t, 41> lambda_powers{};
        lambda_powers[0] = 1;
        for (size_t i = 1; i < lambda_powers.size(); ++i)
            lambda_powers[i] = mul_mod(lambda_powers[i - 1], lambda, r);
        if (mul_mod(lambda_powers[40], lambda, r) != 1)
            throw std::runtime_error("Frobenius eigenvalue does not have order dividing 41");
        if (!(scalar_mul(generator, lambda) == frobenius(generator)))
            throw std::runtime_error("Frobenius eigenvalue does not match the generator");

        std::unordered_map<Point, std::pair<uint64_t, uint64_t>, PointHash> table;
        table.max_load_factor(0.70f);
        table.reserve(262144);
        uint64_t rng_state = seed;
        std::array<RhoJump, RHO_JUMPS> jumps{};
        bool found = false, wall_cap = false, memory_cap = false;
        uint64_t recovered = 0, steps = 0, restarts = 0, fruitless = 0;
        uint64_t recovery_check_ns = 0;
        const auto online_start = std::chrono::steady_clock::now();
        const auto setup_start = std::chrono::steady_clock::now();
        for (RhoJump& jump : jumps) {
            jump.a = splitmix64(rng_state) % r;
            jump.b = splitmix64(rng_state) % r;
            if (jump.a == 0 && jump.b == 0) jump.a = 1;
            jump.point = add(scalar_mul(generator, jump.a), scalar_mul(target, jump.b));
        }
        const uint64_t target_setup_ns = elapsed_ns(setup_start);

        while (!found && !wall_cap && !memory_cap &&
               steps < RHO_STEP_CAP && restarts < 1000) {
            RhoState state;
            state.a = splitmix64(rng_state) % r;
            state.b = splitmix64(rng_state) % r;
            state.point = add(scalar_mul(generator, state.a),
                              scalar_mul(target, state.b));
            state = canonicalize(state, r, lambda_powers);
            bool restart = false;
            while (!restart && !found && steps < RHO_STEP_CAP) {
                auto hit = table.find(state.point);
                if (hit != table.end()) {
                    const uint64_t numerator = sub_mod(hit->second.first, state.a, r);
                    const uint64_t denominator = sub_mod(state.b, hit->second.second, r);
                    if (denominator != 0 && invertible_mod(denominator, r)) {
                        const uint64_t candidate = mul_mod(
                            numerator, inverse_mod(denominator, r), r);
                        const auto check_start = std::chrono::steady_clock::now();
                        const bool verified = scalar_mul(generator, candidate) == target;
                        recovery_check_ns += elapsed_ns(check_start);
                        if (verified) {
                            recovered = candidate;
                            found = true;
                            break;
                        }
                        ++fruitless;
                    } else {
                        ++fruitless;
                    }
                    ++restarts;
                    restart = true;
                    continue;
                }
                table.emplace(state.point, std::make_pair(state.a, state.b));
                const RhoJump& jump = jumps[stable_partition(state.point)];
                state.point = add(state.point, jump.point);
                state.a = add_mod(state.a, jump.a, r);
                state.b = add_mod(state.b, jump.b, r);
                state = canonicalize(state, r, lambda_powers);
                ++steps;
                if ((steps & 4095) == 0) {
                    wall_cap = elapsed_ns(online_start) >= RHO_WALL_CAP_NS;
                    memory_cap = peak_rss_bytes() >= RHO_RSS_CAP_BYTES;
                }
            }
            if (!found && !wall_cap && !memory_cap && !restart)
                ++restarts;
        }
        const auto online_stop = std::chrono::steady_clock::now();
        const uint64_t online_ns = uint64_t(
            std::chrono::duration_cast<std::chrono::nanoseconds>(
                online_stop - online_start).count());
        const char* status = found ? "VERIFIED_ONE_TARGET_RHO" :
            memory_cap ? "MEMORY_CAP" : wall_cap ? "WALL_CAP" :
            restarts >= 1000 ? "RESTART_CAP" : "STEP_CAP";
        std::ofstream out(argv[2]);
        if (!out) throw std::runtime_error("cannot create rho result");
        out << "{\n\"kind\":\"n41_signed_frobenius_rho_single_target\",\n"
            << "\"status\":\"" << status << "\",\n"
            << "\"candidate_id\":null,\"trial_id\":\"N41-W6-S8-ONE-TARGET-R3\",\n"
            << "\"curve_id\":\"EC1N41Ckb1h7d5e80d3c4d0\",\n"
            << "\"target_count\":1,\"workers\":1,\n"
            << "\"target\":[" << qx << "," << qy << "],\n"
            << "\"generator\":[" << gx << "," << gy << "],\n"
            << "\"subgroup_order\":" << r << ",\n"
            << "\"lambda\":" << lambda << ",\n"
            << "\"quotient_mode\":\"signed_frobenius\",\n"
            << "\"jump_count\":" << RHO_JUMPS << ",\n"
            << "\"distinguished_bits\":0,\n"
            << "\"walk_seed\":" << seed << ",\n"
            << "\"walk_steps\":" << steps << ",\n"
            << "\"table_entries\":" << table.size() << ",\n"
            << "\"fruitless_collisions\":" << fruitless << ",\n"
            << "\"restarts\":" << restarts << ",\n"
            << "\"target_dependent_setup_ns\":" << target_setup_ns << ",\n"
            << "\"online_start_monotonic_ns\":"
            << std::chrono::duration_cast<std::chrono::nanoseconds>(
                online_start.time_since_epoch()).count() << ",\n"
            << "\"online_stop_monotonic_ns\":"
            << std::chrono::duration_cast<std::chrono::nanoseconds>(
                online_stop.time_since_epoch()).count() << ",\n"
            << "\"rho_online_wall_ns\":" << online_ns << ",\n"
            << "\"exclusive_stage_phase_ns\":{"
            << "\"target_dependent_jump_setup\":" << target_setup_ns << ","
            << "\"walk_and_collision_recovery\":"
            << online_ns - target_setup_ns - recovery_check_ns << ","
            << "\"scalar_recovery_check\":" << recovery_check_ns << "},\n"
            << "\"recovered_scalar\":";
        if (found) out << recovered;
        else out << "null";
        out << ",\n\"internal_scalar_replay_verified\":" << (found ? "true" : "false")
            << ",\"peak_rss_bytes\":" << peak_rss_bytes() << ",\n"
            << "\"limits\":{\"step_cap\":" << RHO_STEP_CAP
            << ",\"wall_cap_ns\":" << RHO_WALL_CAP_NS
            << ",\"peak_rss_bytes\":" << RHO_RSS_CAP_BYTES << "}\n}\n";
        std::cout << "status=" << status << " rho_online_ns=" << online_ns
                  << " steps=" << steps << " table_entries=" << table.size() << "\n";
        return found ? 0 : 2;
    } catch (const std::exception& error) {
        std::cerr << "error: " << error.what() << "\n";
        return 1;
    }
}
