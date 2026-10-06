// Standalone rho reference for the frozen EC1N83Ckb1h876c2921cb64 target.
// Coordinates are the public G and Q from runs/n83_perf_prefix.json converted
// by field.Onb(83).toCoords; no scalar or known-answer value is linked here.
#define main ecc2k130_embedded_main
#include "main.cu"
#undef main

int main(int argc, char **argv) {
    // The existing CPU engine and collision solver remain unchanged.
    static const unsigned long long px[3] = {
        0xd28edfff9d7ca5a0ull, 0x0000000000010dbcull, 0ull};
    static const unsigned long long py[3] = {
        0xd9b0b7b8bc36d66cull, 0x000000000006c82aull, 0ull};
    static const unsigned long long qx[3] = {
        0xaa4bf524e3e8e9c7ull, 0x0000000000078f3dull, 0ull};
    static const unsigned long long qy[3] = {
        0xb1e3a8d43e5becd4ull, 0x0000000000002e08ull, 0ull};
    Options o;
    o.curve = 83;
    o.threads = 4;
    o.steps = 512;
    o.dpWeight = 22;
    o.verify = 8;
    for (int i = 1; i < argc; ++i) {
        const std::string a = argv[i];
        if (i + 1 < argc && a == "--threads") o.threads = atoi(argv[++i]);
        else if (i + 1 < argc && a == "--steps") o.steps = atoi(argv[++i]);
        else if (i + 1 < argc && a == "--launches") o.launches = atol(argv[++i]);
        else if (i + 1 < argc && a == "--dp-weight") o.dpWeight = atoi(argv[++i]);
        else if (i + 1 < argc && a == "--run-id") o.runId = (unsigned)atoi(argv[++i]);
        else if (i + 1 < argc && a == "--verify") o.verify = atoi(argv[++i]);
        else if (i + 1 < argc && a == "--dp-file") o.dpFile = argv[++i];
        else if (i + 1 < argc && a == "--load") o.loadFiles.push_back(argv[++i]);
        else if (i + 1 < argc && a == "--load-max")
            o.loadMax = strtoull(argv[++i], NULL, 10);
        else if (i + 1 < argc && a == "--checkpoint") o.ckptFile = argv[++i];
        else if (a == "--bench") o.bench = true;
        else if (a == "--test") o.test = true;
        else {
            fprintf(stderr, "unknown or incomplete option: %s\n", a.c_str());
            return 1;
        }
    }
    if (o.threads < 1 || o.steps < 1 || o.launches < 0 ||
        o.dpWeight < 0 || o.dpWeight > 83 || o.runId > 65535) {
        fprintf(stderr, "invalid rho run parameters\n");
        return 1;
    }
    signal(SIGINT, onStop);
    signal(SIGTERM, onStop);
    setvbuf(stdout, NULL, _IOLBF, 0);
    if (o.bench) o.dpWeight = 0;
    return runCurve<CfgF83>(o, px, py, qx, qy,
                            eccF83::ELL_DEC, eccF83::S_DEC,
                            eccF83::DP_WEIGHT, NULL);
}
