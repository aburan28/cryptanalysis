// Owner serialization is supplied by Producer::mutex, or explicitly by the
// direct backend tests. There are no target-independent coefficients here.
void compact_metal_invalidate(void *context) noexcept
{
    if (!context) return;
    auto &c = *static_cast<CompactMetalBranches *>(context);
    c.phase = 0;
    c.prepared_host = nullptr;
}

uint64_t compact_metal_begin(void *context)
{
    if (!context) throw std::invalid_argument("null producer Metal context");
    auto &c = *static_cast<CompactMetalBranches *>(context);
    compact_metal_invalidate(context);
    if (c.generation == UINT64_MAX) throw std::length_error("producer Metal generation exhausted");
    ++c.generation;
    c.phase = 1; // Fresh invocation, no specialized device coefficients yet.
    return c.generation;
}

void compact_metal_configure_transform(void *context, uint32_t mode)
{
    if (!context) throw std::invalid_argument("null producer Metal context");
    auto &c = *static_cast<CompactMetalBranches *>(context);
    compact_metal_invalidate(context);
    if (mode > 2) throw std::invalid_argument("producer transform mode");
#ifdef PRODUCER_TRANSFORM_TEST_FAIL_MODE
    if (mode == PRODUCER_TRANSFORM_TEST_FAIL_MODE)
        throw std::runtime_error("injected producer transform pipeline failure");
#endif
    void *replacement = nullptr;
    if (mode) {
        const auto *parameters = static_cast<const Parameters *>(c.parameters.contents);
        replacement = producer_transform::create_borrowed(
            __builtin_ctz(c.branches), parameters->features + 1,
            static_cast<producer_transform::Mode>(mode), (__bridge void *)c.device,
            (__bridge void *)c.queue, (__bridge void *)c.input);
    }
    // Allocate pipelines before replacement; failure preserves the prior valid
    // configuration, but readiness from an earlier invocation stays revoked.
    producer_transform::destroy(c.transform);
    c.transform = replacement;
    c.transform_mode = mode;
}

void compact_metal_transform(void *context, void *values, size_t bytes, uint64_t generation,
                             producer_transform::Stats &stats)
{
    stats = {};
    if (!context) throw std::invalid_argument("null producer Metal context");
    auto &c = *static_cast<CompactMetalBranches *>(context);
    const uint32_t phase = c.phase;
    compact_metal_invalidate(context);
    if (!generation || generation != c.generation || phase != 1)
        throw std::invalid_argument("producer transform requires a fresh generation");
    if (!c.transform || !values || bytes != c.input.length)
        throw std::invalid_argument("producer transform configuration or extent");
    producer_transform::apply(c.transform, values, bytes, stats);
    c.phase = 2; // Complete, fresh and copied back; projection may consume once.
    c.prepared_host = values;
}

const uint64_t *compact_metal_solve_prepared(void *context, const void *input, size_t bytes,
                                             bool symmetric, bool projection, uint64_t generation,
                                             double &device_seconds)
{
    device_seconds = 0;
    if (!generation) {
        compact_metal_invalidate(context);
        throw std::invalid_argument("prepared projection requires a generation");
    }
    return compact_metal_solve_impl(context, input, bytes, symmetric, projection, generation,
                                    device_seconds);
}

const uint64_t *compact_metal_solve(void *context, const void *input, size_t bytes, bool symmetric,
                                    bool projection, double &device_seconds)
{
    return compact_metal_solve_impl(context, input, bytes, symmetric, projection, 0,
                                    device_seconds);
}
