/*
 * util.c - hash table, seeding, error strings and version.
 */
#include "ca_internal.h"

#include <stdarg.h>
#include <stdio.h>

#if defined(__unix__) || defined(__APPLE__)
#  include <unistd.h>
#  include <fcntl.h>
#endif

const char *ca_version(void) { return CA_VERSION_STRING; }

const char *ca_status_string(ca_status s)
{
    switch (s) {
    case CA_OK: return "ok";
    case CA_ERR_INVALID: return "invalid argument";
    case CA_ERR_NOT_FOUND: return "not found";
    case CA_ERR_NOMEM: return "out of memory";
    case CA_ERR_LIMIT: return "limit reached";
    case CA_ERR_UNSUPPORTED: return "unsupported";
    case CA_ERR_INTERNAL: return "internal error";
    case CA_ERR_SINGULAR: return "singular system";
    }
    return "unknown";
}

static _Thread_local char ca_errbuf[256];

void ca_set_error(const char *fmt, ...)
{
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(ca_errbuf, sizeof(ca_errbuf), fmt, ap);
    va_end(ap);
}

const char *ca_last_error(void) { return ca_errbuf; }

void ca_clear_error(void) { ca_errbuf[0] = 0; }

uint64_t ca_seed_or_random(uint64_t seed)
{
    if (seed != 0) return seed;
    uint64_t s = 0;
#if defined(__unix__) || defined(__APPLE__)
    int fd = open("/dev/urandom", O_RDONLY);
    if (fd >= 0) {
        ssize_t n = read(fd, &s, sizeof(s));
        (void)n;
        close(fd);
    }
#endif
    if (s == 0) {
        struct timespec ts;
        clock_gettime(CLOCK_REALTIME, &ts);
        s = (uint64_t)ts.tv_nsec ^ ((uint64_t)ts.tv_sec << 32) ^ (uint64_t)(uintptr_t)&s;
    }
    if (s == 0) s = 0x1234567887654321ULL;
    return s;
}

/* ---- hash table -------------------------------------------------------- */

ca_status ca_htab_init(ca_htab *t, size_t expected)
{
    size_t cap = 16;
    while (cap < expected * 2) cap <<= 1;
    t->e = calloc(cap, sizeof(ca_htab_entry));
    if (!t->e) return CA_ERR_NOMEM;
    t->cap = cap;
    t->count = 0;
    t->max_count = cap / 2 + cap / 4; /* load factor 0.75 */
    return CA_OK;
}

void ca_htab_free(ca_htab *t)
{
    free(t->e);
    t->e = NULL;
    t->cap = t->count = 0;
}

static int htab_grow(ca_htab *t)
{
    ca_htab old = *t;
    ca_htab_entry *ne = calloc(old.cap * 2, sizeof(ca_htab_entry));
    if (!ne) return -1;
    t->e = ne;
    t->cap = old.cap * 2;
    t->count = 0;
    t->max_count = t->cap / 2 + t->cap / 4;
    for (size_t i = 0; i < old.cap; i++) {
        if (old.e[i].key) ca_htab_insert(t, old.e[i].key, old.e[i].v0, old.e[i].v1, NULL, NULL);
    }
    free(old.e);
    return 0;
}

int ca_htab_insert(ca_htab *t, uint64_t key, uint64_t v0, uint64_t v1,
                   uint64_t *old0, uint64_t *old1)
{
    if (key == 0) key = 1;
    if (t->count >= t->max_count) {
        if (htab_grow(t) != 0) return -1;
    }
    size_t mask = t->cap - 1;
    size_t i = (size_t)ca_mix64(key) & mask;
    while (1) {
        ca_htab_entry *e = &t->e[i];
        if (e->key == 0) {
            e->key = key;
            e->v0 = v0;
            e->v1 = v1;
            t->count++;
            return 0;
        }
        if (e->key == key) {
            if (old0) *old0 = e->v0;
            if (old1) *old1 = e->v1;
            return 1;
        }
        i = (i + 1) & mask;
    }
}

int ca_htab_find(const ca_htab *t, uint64_t key, uint64_t *v0, uint64_t *v1)
{
    if (key == 0) key = 1;
    if (t->cap == 0) return 0;
    size_t mask = t->cap - 1;
    size_t i = (size_t)ca_mix64(key) & mask;
    while (1) {
        const ca_htab_entry *e = &t->e[i];
        if (e->key == 0) return 0;
        if (e->key == key) {
            if (v0) *v0 = e->v0;
            if (v1) *v1 = e->v1;
            return 1;
        }
        i = (i + 1) & mask;
    }
}

size_t ca_htab_bytes(const ca_htab *t) { return t->cap * sizeof(ca_htab_entry); }
