// Pointer-chase null object for IDEA-20261015-b41f68 (ic-probe-latency-20261015).
//
// One dependent random load per access over an anonymous array of SIZE bytes,
// 64-byte slots, a single random cycle (Sattolo) through every slot, no
// arithmetic besides the load. The page policy is the only variable:
//
//   4k       madvise(MADV_NOHUGEPAGE)       4 KiB pages
//   thp      madvise(MADV_HUGEPAGE)         transparent 2 MiB pages, as granted
//   default  no advice: the system THP mode decides
//   hugetlb  mmap(MAP_HUGETLB|MAP_HUGE_2MB) reserved 2 MiB pages (needs vm.nr_hugepages)
//
// The array is memory only (MAP_ANONYMOUS); nothing is written to disk.
// Output: one JSON line with ns/access per repetition and the page placement
// read back from /proc/self/smaps_rollup after first touch.
//
//   pchase <size_bytes> <4k|thp|default|hugetlb> <accesses> <reps> <seed>
#define _GNU_SOURCE
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>

#ifndef MAP_HUGE_2MB
#define MAP_HUGE_2MB (21 << 26)
#endif

#define SLOT 64

static uint64_t splitmix(uint64_t *s) {
    uint64_t z = (*s += 0x9E3779B97F4A7C15ull);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ull;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBull;
    return z ^ (z >> 31);
}

static double now_ns(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC_RAW, &t);
    return (double)t.tv_sec * 1e9 + (double)t.tv_nsec;
}

static long smaps_kb(const char *key) {
    FILE *f = fopen("/proc/self/smaps_rollup", "r");
    if (!f) return -1;
    char line[256];
    long v = -1;
    size_t k = strlen(key);
    while (fgets(line, sizeof line, f)) {
        if (strncmp(line, key, k) == 0 && line[k] == ':') {
            v = strtol(line + k + 1, NULL, 10);
            break;
        }
    }
    fclose(f);
    return v;
}

static int cmp(const void *a, const void *b) {
    double x = *(const double *)a, y = *(const double *)b;
    return (x > y) - (x < y);
}

int main(int argc, char **argv) {
    if (argc != 6) {
        fprintf(stderr, "usage: pchase <size_bytes> <4k|thp|default|hugetlb> <accesses> <reps> <seed>\n");
        return 2;
    }
    uint64_t size = strtoull(argv[1], NULL, 10);
    const char *mode = argv[2];
    uint64_t accesses = strtoull(argv[3], NULL, 10);
    int reps = atoi(argv[4]);
    uint64_t seed = strtoull(argv[5], NULL, 10);
    if (size < 2 * SLOT || size % (2u << 20) != 0 || reps < 1 || reps > 64) {
        fprintf(stderr, "size must be a positive multiple of 2 MiB; 1 <= reps <= 64\n");
        return 2;
    }
    // No MAP_NORESERVE: a hugetlb mapping without enough reserved pages must
    // fail at mmap (reported as mmap_failed), not SIGBUS at first touch.
    int flags = MAP_PRIVATE | MAP_ANONYMOUS;
    if (strcmp(mode, "hugetlb") == 0) flags |= MAP_HUGETLB | MAP_HUGE_2MB;
    else if (strcmp(mode, "4k") != 0 && strcmp(mode, "thp") != 0 && strcmp(mode, "default") != 0) {
        fprintf(stderr, "unknown mode %s\n", mode);
        return 2;
    }
    double t0 = now_ns();
    uint8_t *base = mmap(NULL, size, PROT_READ | PROT_WRITE, flags, -1, 0);
    if (base == MAP_FAILED) {
        printf("{\"schema\":\"pchase/v1\",\"mode\":\"%s\",\"size_bytes\":%llu,\"status\":\"mmap_failed\",\"errno\":%d}\n",
               mode, (unsigned long long)size, errno);
        return 3;
    }
    int adv = 0;
    if (strcmp(mode, "4k") == 0) adv = madvise(base, size, MADV_NOHUGEPAGE);
    if (strcmp(mode, "thp") == 0) adv = madvise(base, size, MADV_HUGEPAGE);
    uint64_t n = size / SLOT;
    // a[i] = i, then Sattolo: a single uniformly random cycle through all slots.
    for (uint64_t i = 0; i < n; i++) *(uint64_t *)(base + i * SLOT) = i;
    uint64_t s = seed;
    for (uint64_t i = n - 1; i > 0; i--) {
        uint64_t j = splitmix(&s) % i;  // 0 <= j < i
        uint64_t *pi = (uint64_t *)(base + i * SLOT), *pj = (uint64_t *)(base + j * SLOT);
        uint64_t t = *pi; *pi = *pj; *pj = t;
    }
    double t_init = now_ns() - t0;
    long anon_huge = smaps_kb("AnonHugePages");
    long hugetlb_priv = smaps_kb("Private_Hugetlb");
    long rss = smaps_kb("Rss");
    // Cycle check on a prefix: the walk must not return to its start early.
    uint64_t p = 0;
    uint64_t check = n < 1000000 ? n - 1 : 1000000;
    for (uint64_t k = 0; k < check; k++) {
        p = *(uint64_t *)(base + p * SLOT);
        if (p == 0) {
            printf("{\"schema\":\"pchase/v1\",\"status\":\"not_a_single_cycle\"}\n");
            return 4;
        }
    }
    // Warm-up: min(n, accesses) dependent loads, untimed.
    uint64_t warm = n < accesses ? n : accesses;
    for (uint64_t k = 0; k < warm; k++) p = *(uint64_t *)(base + p * SLOT);
    double ns[64];
    for (int r = 0; r < reps; r++) {
        double a = now_ns();
        for (uint64_t k = 0; k < accesses; k++) p = *(volatile uint64_t *)(base + p * SLOT);
        ns[r] = (now_ns() - a) / (double)accesses;
    }
    double sorted[64];
    memcpy(sorted, ns, sizeof(double) * reps);
    qsort(sorted, reps, sizeof(double), cmp);
    double median = reps % 2 ? sorted[reps / 2] : 0.5 * (sorted[reps / 2 - 1] + sorted[reps / 2]);
    printf("{\"schema\":\"pchase/v1\",\"status\":\"ok\",\"mode\":\"%s\",\"size_bytes\":%llu,\"slots\":%llu,"
           "\"slot_bytes\":%d,\"accesses\":%llu,\"reps\":%d,\"seed\":%llu,\"madvise_rc\":%d,"
           "\"init_ms\":%.3f,\"anon_huge_kb\":%ld,\"private_hugetlb_kb\":%ld,\"rss_kb\":%ld,"
           "\"ns_per_access_median\":%.4f,\"ns_per_access\":[",
           mode, (unsigned long long)size, (unsigned long long)n, SLOT, (unsigned long long)accesses,
           reps, (unsigned long long)seed, adv, t_init / 1e6, anon_huge, hugetlb_priv, rss, median);
    for (int r = 0; r < reps; r++) printf("%s%.4f", r ? "," : "", ns[r]);
    printf("],\"sink\":%llu}\n", (unsigned long long)p);
    munmap(base, size);
    return 0;
}
