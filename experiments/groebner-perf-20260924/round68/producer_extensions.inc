extern "C" uint64_t branch_producer_transform_stats_size()
{
    return sizeof(ProducerTransformStats);
}
extern "C" const ProducerTransformStats *branch_producer_transform_stats(const void *p)
{
    return p ? &static_cast<const Produced *>(p)->transform : nullptr;
}
extern "C" const ProducerTransformStats *branch_last_producer_transform_stats()
{
    return &failed_transform_stats;
}
extern "C" int branch_producer_transform_configure(void *context, uint32_t mode)
{
    if (!context) return -1;
    auto &w = *static_cast<Producer *>(context);
    std::lock_guard<std::mutex> guard(w.mutex);
    try {
#ifdef QUADRATIC_METAL
        compact_metal_invalidate(w.metal);
#endif
        if (mode > 2) return -1;
        if (mode) {
#ifdef QUADRATIC_METAL
            if (!w.metal) return -2;
            compact_metal_configure_transform(w.metal, mode);
#else
            return -2;
#endif
        } else {
#ifdef QUADRATIC_METAL
            if (w.metal) compact_metal_configure_transform(w.metal, 0);
#endif
        }
        w.transform_mode = mode;
        return 0;
    } catch (const std::exception &e) {
        error_text = e.what();
        return -3;
    }
}
