    // The on-disk v3 schema remains unchanged: one unsigned dead flag and one
    // u64 history per lane. Only unused history bits 48..63 are canonicalized.
    void readCheckpointDead(std::vector<unsigned> &out) const override {
#if GOAL22_BYTE_DEAD
        std::vector<unsigned char> packed(slotCount());
        CUDA_CHECK(cudaMemcpy(packed.data(), P.dead, packed.size(), cudaMemcpyDeviceToHost));
        for(size_t i=0;i<out.size();++i) out[i]=packed[i];
#else
        std::vector<unsigned> packed((slotCount() + 31) / 32);
        CUDA_CHECK(cudaMemcpy(packed.data(), P.dead, packed.size() * sizeof(unsigned), cudaMemcpyDeviceToHost));
        for(size_t i=0;i<out.size();++i) out[i]=(packed[i >> 5] >> (i & 31)) & 1u;
#endif
    }
    void writeCheckpointDead(const std::vector<unsigned> &in) override {
#if GOAL22_BYTE_DEAD
        std::vector<unsigned char> packed(slotCount());
        for(size_t i=0;i<in.size();++i) packed[i]=in[i] ? 1 : 0;
        CUDA_CHECK(cudaMemcpy(P.dead, packed.data(), packed.size(), cudaMemcpyHostToDevice));
#else
        std::vector<unsigned> packed((slotCount() + 31) / 32, 0u);
        for(size_t i=0;i<in.size();++i) if(in[i]) packed[i >> 5] |= 1u << (i & 31);
        CUDA_CHECK(cudaMemcpy(P.dead, packed.data(), packed.size() * sizeof(unsigned), cudaMemcpyHostToDevice));
#endif
    }
    void readCheckpointLane(int which, std::vector<u64> &out) const override {
#if GOAL22_FULL_HIST
        CudaEngine<CfgF131>::readCheckpointLane(which,out);
#else
        if(which!=2) { CudaEngine<CfgF131>::readCheckpointLane(which,out); return; }
        std::vector<unsigned short> packed(3 * laneCount());
        CUDA_CHECK(cudaMemcpy(packed.data(), P.hist, packed.size() * sizeof(unsigned short), cudaMemcpyDeviceToHost));
        for(size_t i=0;i<out.size();++i) out[i]=0xffff000000000000ull | u64(packed[i])
            | (u64(packed[laneCount()+i]) << 16) | (u64(packed[2*laneCount()+i]) << 32);
#endif
    }
    void writeCheckpointLane(int which, const std::vector<u64> &in) override {
#if GOAL22_FULL_HIST
        CudaEngine<CfgF131>::writeCheckpointLane(which,in);
#else
        if(which!=2) { CudaEngine<CfgF131>::writeCheckpointLane(which,in); return; }
        std::vector<unsigned short> packed(3 * laneCount());
        for(size_t i=0;i<in.size();++i) {
            packed[i]=(unsigned short)in[i]; packed[laneCount()+i]=(unsigned short)(in[i] >> 16);
            packed[2*laneCount()+i]=(unsigned short)(in[i] >> 32);
        }
        CUDA_CHECK(cudaMemcpy(P.hist, packed.data(), packed.size() * sizeof(unsigned short), cudaMemcpyHostToDevice));
#endif
    }
