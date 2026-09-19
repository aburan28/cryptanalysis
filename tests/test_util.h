/* Minimal test harness. */
#ifndef CA_TEST_UTIL_H
#define CA_TEST_UTIL_H
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <inttypes.h>
#include <math.h>

static int ca_test_failures = 0;
static int ca_test_checks = 0;

#define CHECK(cond) do { \
    ca_test_checks++; \
    if (!(cond)) { \
        ca_test_failures++; \
        fprintf(stderr, "%s:%d: CHECK failed: %s\n", __FILE__, __LINE__, #cond); \
    } } while (0)

#define CHECK_EQ_U64(a, b) do { \
    uint64_t _a = (a), _b = (b); \
    ca_test_checks++; \
    if (_a != _b) { \
        ca_test_failures++; \
        fprintf(stderr, "%s:%d: CHECK_EQ failed: %s = %" PRIu64 " != %s = %" PRIu64 "\n", \
                __FILE__, __LINE__, #a, _a, #b, _b); \
    } } while (0)

#define TEST_MAIN_END() do { \
    if (ca_test_failures) { \
        fprintf(stderr, "FAILED: %d of %d checks\n", ca_test_failures, ca_test_checks); \
        return 1; \
    } \
    printf("ok: %d checks\n", ca_test_checks); \
    return 0; } while (0)

#endif
