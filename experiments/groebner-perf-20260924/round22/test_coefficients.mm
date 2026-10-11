// Exercise the actual decoder, device kernels and reused workspace. The oracle
// scans original sparse coefficients directly; it implements no zeta transform.
#include "coefficient_gpu.mm"
#include <iostream>
#include <memory>

static uint64_t random_state = 2026092709;
static uint64_t random_word()
{
    random_state ^= random_state << 13;
    random_state ^= random_state >> 7;
    random_state ^= random_state << 17;
    return random_state;
}

int main(int argc, const char **argv)
{
    @autoreleasepool {
        try {
            if (argc > 2) throw std::invalid_argument("usage: test-coefficients [threads]");
            const auto threads = argc == 2 ? uint32_t(std::stoul(argv[1])) : 256;
            uint64_t checked_partial = 0, checked_values = 0, checked_roots = 0;
            uint32_t cases = 0;
            std::string device_name;
            for (auto shape : std::vector<std::pair<uint32_t,uint32_t>>{
                     {1,1}, {5,31}, {6,32}, {6,33}, {7,65}, {12,128},
                     {13,31}, {18,31}, {20,63}, {20,128}}) {
                const auto n = shape.first, equations = shape.second;
                std::unique_ptr<Workspace> w(static_cast<Workspace *>(truth_create(n, equations)));
                if (!w) throw std::runtime_error(truth_gpu_error());
                if (truth_gpu_configure(w.get(),0,threads)) throw std::invalid_argument("thread count");
                device_name = w->device.name.UTF8String;
                const auto high_mask = (w->universe-1) ^ (w->low_width-1);
                for (uint32_t pattern=0; pattern<4; ++pattern) {
                    std::vector<uint32_t> masks;
                    std::vector<uint64_t> coefficients;
                    auto add = [&](uint32_t mask, const std::vector<uint64_t>& limbs) {
                        masks.push_back(mask);
                        coefficients.insert(coefficients.end(),limbs.begin(),limbs.end());
                    };
                    if (pattern == 1 || pattern == 2) {
                        const uint32_t count = n <= 12 && pattern == 1 ? w->universe : 32;
                        for (uint32_t i=0; i<count; ++i) {
                            std::vector<uint64_t> limbs(w->limbs);
                            for (auto &v : limbs) v=random_word();
                            if (equations%64) limbs.back() &= (uint64_t(1)<<(equations%64))-1;
                            add(n <= 12 && pattern == 1 ? i : uint32_t(random_word())&(w->universe-1),limbs);
                        }
                        // Duplicate parity must be handled by the decoder.
                        std::vector<uint64_t> duplicate(coefficients.begin(),coefficients.begin()+w->limbs);
                        add(masks.front(),duplicate); add(masks.front(),duplicate);
                    }
                    uint32_t planted = uint32_t(random_word())&(w->universe-1);
                    if (pattern == 2) {
                        std::vector<uint64_t> correction(w->limbs);
                        for (size_t i=0; i<masks.size(); ++i)
                            if ((masks[i]&planted)==masks[i])
                                for (uint32_t limb=0; limb<w->limbs; ++limb)
                                    correction[limb] ^= coefficients[i*w->limbs+limb];
                        add(0,correction);
                    }
                    if (pattern == 3) {
                        std::vector<uint64_t> unit(w->limbs);
                        unit[(equations-1)/64] = uint64_t(1)<<((equations-1)%64);
                        add(0,unit);
                    }
                    // An empty proposed basis is deliberate: intermediate truth
                    // must be correct even when the complete basis claim fails.
                    uint32_t offsets[] = {0}; Result result{};
                    const int code = truth_certify(w.get(),masks.data(),coefficients.data(),uint32_t(masks.size()),
                                                   nullptr,0,offsets,0,&result);
                    if (code == 6 || code == 7 || w->stats.calls != 1)
                        throw std::runtime_error("decoder/device call failed");
                    const auto *partial = static_cast<const uint32_t *>(w->transformed.contents);
                    const auto *values = w->high_width > 1 ? w->values.data() : partial;
                    std::vector<uint64_t> expected_roots(w->blocks);
                    for (uint32_t assignment=0; assignment<w->universe; ++assignment) {
                        bool zero = true;
                        for (uint32_t lane=0; lane<w->lanes; ++lane) {
                            uint32_t expected = 0, low_expected = 0;
                            for (size_t i=0; i<masks.size(); ++i) {
                                const auto c = uint32_t(coefficients[i*w->limbs+lane/2] >> ((lane%2)*32));
                                if ((masks[i]&assignment)==masks[i]) expected ^= c;
                                if ((masks[i]&high_mask)==(assignment&high_mask) &&
                                    ((masks[i]&~high_mask)&assignment)==(masks[i]&~high_mask)) low_expected ^= c;
                            }
                            const auto index = size_t(lane)*w->universe+assignment;
                            if (partial[index] != low_expected) throw std::runtime_error("low transform differs from direct original terms");
                            if (values[index] != expected) throw std::runtime_error("full truth differs from direct original terms");
                            zero = zero && expected == 0;
                            ++checked_partial; ++checked_values;
                        }
                        if (zero) expected_roots[assignment/64] |= uint64_t(1)<<(assignment%64);
                    }
                    for (uint32_t block=0; block<w->blocks; ++block) {
                        if (w->roots[block] != expected_roots[block]) throw std::runtime_error("root word differs");
                        ++checked_roots;
                    }
                    if (pattern==2 && !((w->roots[planted/64]>>(planted%64))&1)) throw std::runtime_error("planted root lost");
                    ++cases;
                    std::cout << "checked n=" << n << " e=" << equations << " pattern=" << pattern << '\n';
                }
            }
            std::cout << "PASS cases=" << cases << " partial_words=" << checked_partial
                      << " truth_words=" << checked_values << " root_words=" << checked_roots
                      << " device=" << device_name << " threads=" << threads << '\n';
            return 0;
        } catch (const std::exception& error) {
            std::cerr << "FAIL " << error.what() << '\n'; return 1;
        }
    }
}
