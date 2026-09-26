/*
 * coord_net.c - the agent's side of the wire: the outbound connection it
 * holds open to a coordinator, and the one-shot calls.  POSIX sockets,
 * blocking I/O.
 *
 * The *hub* is not here.  It is a network service that has to be
 * deployed, scaled and fronted by a load balancer, so it lives in Go
 * (bindings/go/cmd/ca-coordinator) and reuses this library through cgo
 * rather than reimplementing any of it.  What stays in C is what an
 * agent needs, because an agent is a walker first and a network client
 * second.
 *
 * The transport carries the lines coord.c defines and adds nothing to
 * them: every fact still arrives as a check-in and is still merged by
 * ca_coord_apply with verification on.  So this file can be wrong about
 * what is connected, or lose a connection entirely, without being able
 * to corrupt anybody's answer.
 *
 * Why HTTP at all, for a protocol that is one line per message: because
 * the hub has to be reachable from everywhere the agents are, and what
 * is reachable from everywhere is a URL on port 443 behind somebody's
 * load balancer.  The channel is opened with an HTTP upgrade -- the
 * WebSocket move -- which is exactly the handshake proxies already know
 * how to pass through.
 */
#include "coord_internal.h"

#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <netdb.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <poll.h>
#include <signal.h>
#include <stdatomic.h>
#include <stdarg.h>
#include <stdio.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <unistd.h>

/* ---- small socket helpers ---------------------------------------------- */

typedef struct coord_conn {
    int fd;
    char buf[CA_COORD_LINE_MAX];
    size_t len; /* bytes buffered */
    size_t pos; /* bytes consumed */
} coord_conn;

static void conn_init(coord_conn *c, int fd)
{
    memset(c, 0, sizeof(*c));
    c->fd = fd;
}

static int conn_write(coord_conn *c, const char *s, size_t n)
{
    while (n) {
        ssize_t w = send(c->fd, s, n, MSG_NOSIGNAL);
        if (w < 0) {
            if (errno == EINTR) continue;
            return -1;
        }
        if (w == 0) return -1;
        s += (size_t)w;
        n -= (size_t)w;
    }
    return 0;
}

static int conn_puts(coord_conn *c, const char *s) { return conn_write(c, s, strlen(s)); }

/* Write one line plus its terminator. */
static int conn_line(coord_conn *c, const char *s)
{
    if (conn_puts(c, s) < 0) return -1;
    return conn_write(c, "\n", 1);
}

/*
 * Read one line into `out`.  Returns 1 on a line, 0 on timeout (nothing
 * available yet), -1 on EOF or error.  A line longer than the buffer is
 * an error, not a truncation: half a check-in must never be parsed.
 */
static int conn_read_line(coord_conn *c, char *out, size_t cap, int timeout_ms)
{
    for (;;) {
        for (size_t i = c->pos; i < c->len; i++) {
            if (c->buf[i] != '\n') continue;
            size_t n = i - c->pos;
            if (n && c->buf[c->pos + n - 1] == '\r') n--;
            if (n >= cap) {
                c->pos = i + 1;
                return -1;
            }
            memcpy(out, c->buf + c->pos, n);
            out[n] = 0;
            c->pos = i + 1;
            return 1;
        }
        /* Compact what is left to the front. */
        if (c->pos) {
            memmove(c->buf, c->buf + c->pos, c->len - c->pos);
            c->len -= c->pos;
            c->pos = 0;
        }
        if (c->len == sizeof(c->buf)) return -1; /* no newline in a full buffer */

        struct pollfd pf = {.fd = c->fd, .events = POLLIN};
        int pr = poll(&pf, 1, timeout_ms);
        if (pr == 0) return 0;
        if (pr < 0) {
            if (errno == EINTR) continue;
            return -1;
        }
        ssize_t r = recv(c->fd, c->buf + c->len, sizeof(c->buf) - c->len, 0);
        if (r == 0) return -1;
        if (r < 0) {
            if (errno == EINTR) continue;
            if (errno == EAGAIN || errno == EWOULDBLOCK) return 0;
            return -1;
        }
        c->len += (size_t)r;
    }
}

/*
 * Read one line, giving up after `total_ms` or as soon as `stop` is
 * set.  Shutdown correctness rests on this: every blocking read in a
 * connection thread has to notice a stop promptly, because
 * ca_coord_hub_stop waits for those threads before the state they use
 * is freed.
 */
static int conn_read_line_until(coord_conn *c, char *out, size_t cap, int total_ms,
                                const atomic_int *stop)
{
    for (int waited = 0;; waited += 100) {
        if (stop && atomic_load(stop)) return -1;
        int rc = conn_read_line(c, out, cap, 100);
        if (rc != 0) return rc;
        if (total_ms >= 0 && waited >= total_ms) return 0;
    }
}

/* Read exactly n bytes (for a request body). */
static int conn_read_exact(coord_conn *c, char *out, size_t n, int timeout_ms)
{
    size_t got = 0;
    while (got < n) {
        if (c->pos < c->len) {
            size_t avail = c->len - c->pos;
            size_t take = avail < n - got ? avail : n - got;
            memcpy(out + got, c->buf + c->pos, take);
            c->pos += take;
            got += take;
            continue;
        }
        c->pos = c->len = 0;
        struct pollfd pf = {.fd = c->fd, .events = POLLIN};
        int pr = poll(&pf, 1, timeout_ms);
        if (pr <= 0) return -1;
        ssize_t r = recv(c->fd, c->buf, sizeof(c->buf), 0);
        if (r <= 0) return -1;
        c->len = (size_t)r;
    }
    return 0;
}

/* Constant-time compare, so a token cannot be guessed a byte at a time. */
static int coord_token_eq(const char *a, const char *b)
{
    if (!a || !b) return 0;
    size_t la = strlen(a), lb = strlen(b);
    unsigned char diff = (unsigned char)((la ^ lb) != 0);
    size_t n = la < lb ? la : lb;
    for (size_t i = 0; i < n; i++) diff |= (unsigned char)(a[i] ^ b[i]);
    return diff == 0;
}

ca_status ca_coord_parse_url(const char *url, char *host_port, size_t hp_cap, char *prefix,
                             size_t pfx_cap)
{
    if (!url || !host_port || !prefix) return CA_ERR_INVALID;
    if (strncmp(url, "https://", 8) == 0) {
        ca_set_error("%s: this client speaks plain HTTP only. Terminate TLS in a local "
                     "sidecar (stunnel/nginx/socat) and set CA_COORDINATOR_URL to its "
                     "http://127.0.0.1 address; the sidecar dials the public https:// hub. "
                     "See docs/COORDINATOR.md \"8a. TLS: terminate it in a sidecar\"",
                     url);
        return CA_ERR_UNSUPPORTED;
    }
    const char *p = url;
    if (strncmp(p, "http://", 7) == 0) p += 7;
    const char *slash = strchr(p, '/');
    {
        /* Refuse http://user:secret@host.
         *
         * This client ignores userinfo -- it authenticates with a bearer
         * token and nothing else -- so such a URL could never work, and
         * would take its credentials on a tour of the places a URL goes:
         * the Host header, an error message, the line the agent logs when
         * it dials.  Refusing it is both honest about what is supported
         * and the end of that leak.  The message deliberately does not
         * echo the URL. */
        const char *host_end = slash ? slash : p + strlen(p);
        for (const char *q = p; q < host_end; q++) {
            if (*q != '@') continue;
            ca_set_error("coordinator URL carries credentials; this client "
                         "authenticates with a bearer token, so pass the plain "
                         "http://host:port and use --token or --token-file");
            return CA_ERR_INVALID;
        }
    }
    size_t hlen = slash ? (size_t)(slash - p) : strlen(p);
    if (!hlen || hlen >= hp_cap) {
        ca_set_error("%s: no host", url);
        return CA_ERR_INVALID;
    }
    memcpy(host_port, p, hlen);
    host_port[hlen] = 0;
    if (!strchr(host_port, ':')) {
        /* A hostname with no port is port 80 -- what a reverse proxy
         * publishes on.  Appended with a bound, not strcat. */
        if (hlen + 4 > hp_cap) return CA_ERR_INVALID;
        memcpy(host_port + hlen, ":80", 4);
    }
    prefix[0] = 0;
    if (slash) {
        /* Trailing slashes are dropped so "/rho/" and "/rho" route the same. */
        size_t plen = strlen(slash);
        while (plen > 1 && slash[plen - 1] == '/') plen--;
        if (plen > 1) {
            if (plen >= pfx_cap) return CA_ERR_INVALID;
            memcpy(prefix, slash, plen);
            prefix[plen] = 0;
        }
    }
    return CA_OK;
}

/* Split "host:port" and connect, or bind. */
static int coord_split(const char *host_port, char *host, size_t hcap, char *port, size_t pcap)
{
    const char *colon = strrchr(host_port, ':');
    if (!colon) return 0;
    size_t hlen = (size_t)(colon - host_port);
    if (hlen >= hcap || strlen(colon + 1) >= pcap) return 0;
    memcpy(host, host_port, hlen);
    host[hlen] = 0;
    snprintf(port, pcap, "%s", colon + 1);
    if (!host[0]) snprintf(host, hcap, "0.0.0.0");
    return 1;
}

static int coord_dial(const char *host_port, int timeout_ms)
{
    char host[256], port[32];
    if (!coord_split(host_port, host, sizeof(host), port, sizeof(port))) return -1;
    struct addrinfo hints, *res = NULL;
    memset(&hints, 0, sizeof(hints));
    hints.ai_family = AF_UNSPEC;
    hints.ai_socktype = SOCK_STREAM;
    if (getaddrinfo(host, port, &hints, &res) != 0) return -1;
    int fd = -1;
    for (struct addrinfo *ai = res; ai; ai = ai->ai_next) {
        fd = socket(ai->ai_family, ai->ai_socktype, ai->ai_protocol);
        if (fd < 0) continue;
        struct timeval tv = {timeout_ms / 1000, (suseconds_t)(timeout_ms % 1000) * 1000};
        setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof(tv));
        if (connect(fd, ai->ai_addr, ai->ai_addrlen) == 0) break;
        close(fd);
        fd = -1;
    }
    freeaddrinfo(res);
    if (fd >= 0) {
        int one = 1;
        setsockopt(fd, IPPROTO_TCP, TCP_NODELAY, &one, sizeof(one));
    }
    return fd;
}

/* ---- shared buffers ----------------------------------------------------- */

/* A growable text buffer, so a delta's Content-Length is known before
 * the first byte goes out. */
typedef struct coord_buf {
    char *p;
    size_t len, cap;
    int failed;
} coord_buf;

static int buf_add(coord_buf *b, const char *s, size_t n)
{
    if (b->failed) return -1;
    if (b->len + n + 1 > b->cap) {
        size_t cap = b->cap ? b->cap : 4096;
        while (cap < b->len + n + 1) cap *= 2;
        char *q = realloc(b->p, cap);
        if (!q) {
            b->failed = 1;
            return -1;
        }
        b->p = q;
        b->cap = cap;
    }
    memcpy(b->p + b->len, s, n);
    b->len += n;
    b->p[b->len] = 0;
    return 0;
}

/*
 * Append a formatted header line, failing the buffer rather than
 * truncating or over-reading.
 *
 * snprintf returns the length it *would* have written.  Passing that to
 * buf_add copies past the end of the stack buffer and sends whatever
 * followed it, which for the Authorization header means a token longer
 * than the buffer leaks stack memory to the coordinator.  Truncating
 * instead would be quieter and just as wrong: a half-written bearer
 * token is not the credential the caller asked us to present.  So a
 * request that does not fit is refused.
 */
#if defined(__GNUC__)
__attribute__((format(printf, 4, 5)))
#endif
static int
buf_add_fmt(coord_buf *b, char *scratch, size_t cap, const char *fmt, ...)
{
    if (b->failed) return -1;
    va_list ap;
    va_start(ap, fmt);
    int n = vsnprintf(scratch, cap, fmt, ap);
    va_end(ap);
    if (n < 0 || (size_t)n >= cap) {
        b->failed = 1;
        return -1;
    }
    return buf_add(b, scratch, (size_t)n);
}

/*
 * Append one "<peer>:<seq>" entry of a version vector.
 *
 * Formatted by hand rather than with snprintf, for one reason: snprintf
 * returns the length it *would* have written, not the length it wrote,
 * and passing that on unclamped reads past the buffer the moment
 * anything truncates.  Writing the bound out explicitly means the bound
 * is checked here rather than inferred from the peer-name limit three
 * files away -- and it is what -fanalyzer can actually see.
 */
static int buf_add_vv_entry(coord_buf *b, const char *peer, uint64_t seq)
{
    char ent[CA_COORD_PEER_MAX + 32];
    size_t len = 0;
    ent[len++] = ' ';
    size_t plen = strnlen(peer, CA_COORD_PEER_MAX - 1);
    memcpy(ent + len, peer, plen);
    len += plen;
    ent[len++] = ':';
    /* u64 in decimal: 20 digits at most, and ent has 30 spare. */
    char digits[20];
    size_t nd = 0;
    do {
        digits[nd++] = (char)('0' + (seq % 10));
        seq /= 10;
    } while (seq && nd < sizeof(digits));
    while (nd) ent[len++] = digits[--nd];
    return buf_add(b, ent, len);
}

/* The whole vector, as one "vv …" line. */
static int buf_add_vv(coord_buf *b, const ca_coord_vv *vv)
{
    if (buf_add(b, "vv", 2) < 0) return -1;
    for (size_t i = 0; vv && i < vv->count; i++)
        if (buf_add_vv_entry(b, vv->e[i].name, vv->e[i].max_seq) < 0) return -1;
    return buf_add(b, "\n", 1);
}

static int buf_collect_checkin(void *user, const ca_coord_checkin *ci)
{
    coord_buf *b = user;
    char line[CA_COORD_LINE_MAX];
    if (!ca_coord_checkin_encode(ci, line, sizeof(line))) return 0;
    if (buf_add(b, line, strlen(line)) < 0) return 1;
    return buf_add(b, "\n", 1) < 0 ? 1 : 0;
}

/* ---- the agent ---------------------------------------------------------- */

/*
 * One outbound connection, held open and re-dialled with exponential
 * backoff.  The agent needs no inbound reachability: everything the hub
 * has to say to it comes back down this socket.
 */
struct ca_coord_agent {
    char host_port[256];
    char prefix[128];
    /* Heap, not a fixed field: a bearer token has no length the caller
     * owes us, and silently keeping the first 256 bytes of one would
     * authenticate the job fetch and then fail every channel upgrade --
     * an agent that walks alone and shares nothing. */
    char *token;
    int have_token;
    char peer[CA_COORD_PEER_MAX];
    const ca_coord_ctx *ctx;
    ca_coord_state *st;

    pthread_mutex_t lock; /* the outbox and the stats */
    char **outbox;        /* encoded check-in lines, oldest first */
    size_t out_count, out_cap;
    /* The first out_sent lines are on the wire and not yet acked.  A
     * line leaves the outbox on the hub's ack, not on the write: a send
     * that fails, or a socket that drops with bytes still in flight,
     * would otherwise leave the record only in this process's table. */
    size_t out_sent;
    ca_coord_agent_stats stats;

    atomic_int stop;
    pthread_t thread;
};

/*
 * Record the last error for the status line.  The text can come from the
 * hub (an "err" frame), so it is attacker-controlled: it is truncated to
 * the field explicitly and never used for anything but display.
 */
static void agent_note_error(ca_coord_agent *ag, const char *what)
{
    pthread_mutex_lock(&ag->lock);
    size_t cap = sizeof(ag->stats.last_error) - 1;
    size_t n = strnlen(what, cap);
    memcpy(ag->stats.last_error, what, n);
    ag->stats.last_error[n] = 0;
    for (size_t i = 0; i < n; i++) {
        unsigned char c = (unsigned char)ag->stats.last_error[i];
        if (c < 0x20 || c >= 0x7f) ag->stats.last_error[i] = '?';
    }
    pthread_mutex_unlock(&ag->lock);
}

void ca_coord_agent_publish(ca_coord_agent *ag, const ca_coord_checkin *ci)
{
    if (!ag || !ci) return;
    char line[CA_COORD_LINE_MAX];
    if (!ca_coord_checkin_encode(ci, line, sizeof(line))) return;
    size_t n = strlen(line) + 1;
    char *copy = malloc(n);
    if (!copy) return;
    memcpy(copy, line, n);
    pthread_mutex_lock(&ag->lock);
    if (ag->out_count == ag->out_cap) {
        size_t cap = ag->out_cap ? ag->out_cap * 2 : 32;
        char **q = realloc(ag->outbox, cap * sizeof(*q));
        if (!q) {
            pthread_mutex_unlock(&ag->lock);
            free(copy);
            return;
        }
        ag->outbox = q;
        ag->out_cap = cap;
    }
    ag->outbox[ag->out_count++] = copy;
    pthread_mutex_unlock(&ag->lock);
}

/* The hub acks check-ins in the order it read them, so an ack retires
 * the oldest line in flight. */
static void agent_acked(ca_coord_agent *ag)
{
    pthread_mutex_lock(&ag->lock);
    if (ag->out_sent) {
        free(ag->outbox[0]);
        memmove(ag->outbox, ag->outbox + 1, (ag->out_count - 1) * sizeof(*ag->outbox));
        ag->out_count--;
        ag->out_sent--;
    }
    pthread_mutex_unlock(&ag->lock);
}

int ca_coord_agent_flush(ca_coord_agent *ag, uint64_t timeout_ms)
{
    if (!ag) return 1;
    for (uint64_t waited = 0;; waited += 50) {
        pthread_mutex_lock(&ag->lock);
        size_t left = ag->out_count;
        pthread_mutex_unlock(&ag->lock);
        if (!left) return 1;
        if (waited >= timeout_ms) return 0;
        struct timespec ts = {0, 50 * 1000000L};
        nanosleep(&ts, NULL);
    }
}

void ca_coord_agent_stats_get(ca_coord_agent *ag, ca_coord_agent_stats *out)
{
    memset(out, 0, sizeof(*out));
    if (!ag) return;
    pthread_mutex_lock(&ag->lock);
    *out = ag->stats;
    pthread_mutex_unlock(&ag->lock);
}

/* Merge a batch line the hub pushed. */
static void agent_merge_line(ca_coord_agent *ag, const char *line)
{
    ca_coord_checkin ci;
    if (ca_coord_checkin_decode(&ci, line) != CA_OK) {
        pthread_mutex_lock(&ag->lock);
        ag->stats.rejected++;
        pthread_mutex_unlock(&ag->lock);
        return;
    }
    ca_coord_outcome oc;
    if (ca_coord_apply(ag->st, ag->ctx, &ci, (uint64_t)time(NULL), 1, &oc) != CA_OK) {
        pthread_mutex_lock(&ag->lock);
        ag->stats.rejected++;
        pthread_mutex_unlock(&ag->lock);
        return;
    }
    pthread_mutex_lock(&ag->lock);
    if (oc.fresh) ag->stats.received++;
    ag->stats.rejected += oc.rejected_dps;
    pthread_mutex_unlock(&ag->lock);
}

/* One connection's lifetime.  Returns 0 on a clean close, -1 otherwise. */
static int agent_session(ca_coord_agent *ag)
{
    int fd = coord_dial(ag->host_port, 10000);
    if (fd < 0) {
        agent_note_error(ag, "connect failed");
        return -1;
    }
    coord_conn conn;
    conn_init(&conn, fd);

    char req[1024];
    int n = snprintf(req, sizeof(req),
                     "GET %s/v1/channel HTTP/1.1\r\nHost: %s\r\nConnection: Upgrade\r\n"
                     "Upgrade: " CA_COORD_PROTOCOL "\r\n",
                     ag->prefix, ag->host_port);
    if (n < 0 || (size_t)n >= sizeof(req)) {
        close(fd);
        return -1;
    }
    if (ag->have_token) {
        /* Written in pieces rather than formatted into a buffer, so the
         * token's length is the token's business. */
        if (conn_puts(&conn, req) < 0 || conn_puts(&conn, "Authorization: Bearer ") < 0 ||
            conn_puts(&conn, ag->token) < 0 || conn_puts(&conn, "\r\n") < 0) {
            close(fd);
            return -1;
        }
    } else if (conn_puts(&conn, req) < 0) {
        close(fd);
        return -1;
    }
    if (conn_puts(&conn, "\r\n") < 0) {
        close(fd);
        return -1;
    }

    char line[CA_COORD_LINE_MAX];
    if (conn_read_line(&conn, line, sizeof(line), 15000) != 1) {
        close(fd);
        agent_note_error(ag, "no reply to the upgrade");
        return -1;
    }
    if (!strstr(line, " 101 ")) {
        char msg[128];
        snprintf(msg, sizeof(msg), "channel refused: %.90s", line);
        agent_note_error(ag, msg);
        close(fd);
        return -1;
    }
    while (conn_read_line(&conn, line, sizeof(line), 15000) == 1 && line[0]) {}

    pthread_mutex_lock(&ag->lock);
    ag->stats.connected = 1;
    ag->stats.connects++;
    ag->stats.last_error[0] = 0;
    pthread_mutex_unlock(&ag->lock);

    /* hello: who we are and what we already have, so the hub's first
     * push is exactly the difference. */
    coord_buf hello;
    memset(&hello, 0, sizeof(hello));
    char head[CA_COORD_PEER_MAX + 64];
    snprintf(head, sizeof(head), "hello %" PRIu64 " %s", ag->ctx->job.id, ag->peer);
    buf_add(&hello, head, strlen(head));
    ca_coord_vv *vv = NULL;
    if (ca_coord_vv_new(&vv) == CA_OK) {
        ca_coord_state_vv(ag->st, vv);
        for (size_t i = 0; i < vv->count; i++)
            buf_add_vv_entry(&hello, vv->e[i].name, vv->e[i].max_seq);
        ca_coord_vv_free(vv);
    }
    int rc = hello.failed ? -1 : conn_line(&conn, hello.p);
    free(hello.p);
    if (rc < 0) {
        close(fd);
        return -1;
    }

    uint64_t last_out = (uint64_t)time(NULL);
    while (!atomic_load(&ag->stop)) {
        /* Everything the lanes produced since the last turn goes up.
         * The line stays in the outbox until the hub acks it: nothing
         * else would offer it again, because the hello on the next
         * connection says what this agent *has*, so the hub pushes down
         * and never asks up, and a later check-in carries a higher unit
         * cursor rather than these points.  Only this thread retires
         * lines, so the pointer is safe to use unlocked. */
        const char *pending = NULL;
        pthread_mutex_lock(&ag->lock);
        if (ag->out_sent < ag->out_count) pending = ag->outbox[ag->out_sent];
        pthread_mutex_unlock(&ag->lock);
        if (pending) {
            if (conn_line(&conn, pending) < 0) break;
            pthread_mutex_lock(&ag->lock);
            ag->out_sent++;
            ag->stats.sent++;
            pthread_mutex_unlock(&ag->lock);
            last_out = (uint64_t)time(NULL);
        } else if ((uint64_t)time(NULL) - last_out >= 20) {
            if (conn_line(&conn, "ping") < 0) break;
            last_out = (uint64_t)time(NULL);
        }

        int r = conn_read_line(&conn, line, sizeof(line), pending ? 0 : 100);
        if (r < 0) break;
        if (r == 0) continue;
        if (!strncmp(line, "ci ", 3))
            agent_merge_line(ag, line);
        else if (!strncmp(line, "ack ", 4))
            agent_acked(ag);
        else if (!strncmp(line, "err ", 4)) {
            agent_note_error(ag, line + 4);
            close(fd);
            return -1;
        }
        /* "ping" needs no action. */
    }
    close(fd);
    return 0;
}

static void *agent_main(void *arg)
{
    ca_coord_agent *ag = arg;
    uint64_t backoff_ms = 1000;
    while (!atomic_load(&ag->stop)) {
        int rc = agent_session(ag);
        pthread_mutex_lock(&ag->lock);
        ag->stats.connected = 0;
        ag->stats.reconnects++;
        /* Whatever the hub did not ack goes again on the next connection. */
        ag->out_sent = 0;
        pthread_mutex_unlock(&ag->lock);
        if (rc == 0)
            backoff_ms = 1000;
        else
            backoff_ms = backoff_ms * 2 > 30000 ? 30000 : backoff_ms * 2;
        for (uint64_t waited = 0; waited < backoff_ms && !atomic_load(&ag->stop); waited += 100) {
            struct timespec ts = {0, 100 * 1000000L};
            nanosleep(&ts, NULL);
        }
    }
    return NULL;
}

ca_status ca_coord_agent_start(ca_coord_agent **out, const char *url, const char *token,
                               const char *peer, const ca_coord_ctx *ctx, ca_coord_state *st)
{
    if (!out || !url || !peer || !ctx || !st) return CA_ERR_INVALID;
    *out = NULL;
    ca_coord_agent *ag = calloc(1, sizeof(*ag));
    if (!ag) return CA_ERR_NOMEM;
    ca_status rc = ca_coord_parse_url(url, ag->host_port, sizeof(ag->host_port), ag->prefix,
                                      sizeof(ag->prefix));
    if (rc != CA_OK) {
        free(ag);
        return rc;
    }
    snprintf(ag->peer, sizeof(ag->peer), "%s", peer);
    if (token && token[0]) {
        ag->token = strdup(token);
        if (!ag->token) {
            free(ag);
            return CA_ERR_NOMEM;
        }
        ag->have_token = 1;
    }
    ag->ctx = ctx;
    ag->st = st;
    if (pthread_mutex_init(&ag->lock, NULL) != 0) {
        free(ag->token);
        free(ag);
        return CA_ERR_INTERNAL;
    }
    if (pthread_create(&ag->thread, NULL, agent_main, ag) != 0) {
        pthread_mutex_destroy(&ag->lock);
        free(ag->token);
        free(ag);
        return CA_ERR_INTERNAL;
    }
    *out = ag;
    return CA_OK;
}

void ca_coord_agent_stop(ca_coord_agent *ag)
{
    if (!ag) return;
    atomic_store(&ag->stop, 1);
    pthread_join(ag->thread, NULL);
    for (size_t i = 0; i < ag->out_count; i++) free(ag->outbox[i]);
    free(ag->outbox);
    free(ag->token);
    pthread_mutex_destroy(&ag->lock);
    free(ag);
}

/* ---- one-shot client calls ---------------------------------------------- */

/*
 * One HTTP request on a fresh connection.  The reply body is returned in
 * *body (the caller frees it).  Plain HTTP only, as the header says.
 */
static ca_status coord_request(const char *url, const char *token, const char *method,
                               const char *route, const char *req_body, int *status, char **body)
{
    char host_port[256], prefix[128];
    ca_status rc = ca_coord_parse_url(url, host_port, sizeof(host_port), prefix, sizeof(prefix));
    if (rc != CA_OK) return rc;
    int fd = coord_dial(host_port, 10000);
    if (fd < 0) {
        ca_set_error("%s: connect failed", host_port);
        return CA_ERR_INVALID;
    }
    coord_conn conn;
    conn_init(&conn, fd);
    coord_buf req;
    memset(&req, 0, sizeof(req));
    char head[1024];
    buf_add_fmt(&req, head, sizeof(head), "%s %s%s HTTP/1.1\r\nHost: %s\r\nConnection: close\r\n",
                method, prefix, route, host_port);
    if (token && token[0]) {
        /* In pieces, for the same reason: buf_add_fmt would refuse a
         * token longer than the scratch buffer, and the length of a
         * bearer token is not ours to cap. */
        buf_add(&req, "Authorization: Bearer ", 22);
        buf_add(&req, token, strlen(token));
        buf_add(&req, "\r\n", 2);
    }
    if (req_body)
        buf_add_fmt(&req, head, sizeof(head), "Content-Type: text/plain\r\nContent-Length: %zu\r\n",
                    strlen(req_body));
    buf_add(&req, "\r\n", 2);
    if (req_body) buf_add(&req, req_body, strlen(req_body));
    int wrc = req.failed ? -1 : conn_write(&conn, req.p, req.len);
    free(req.p);
    if (wrc < 0) {
        close(fd);
        ca_set_error("%s: write failed", host_port);
        return CA_ERR_INVALID;
    }

    char line[CA_COORD_LINE_MAX];
    if (conn_read_line(&conn, line, sizeof(line), 30000) != 1) {
        close(fd);
        ca_set_error("%s: no reply", host_port);
        return CA_ERR_INVALID;
    }
    *status = 0;
    {
        const char *sp = strchr(line, ' ');
        if (sp) *status = (int)strtol(sp + 1, NULL, 10);
    }
    size_t length = 0;
    int have_length = 0, chunked = 0;
    for (;;) {
        int r = conn_read_line(&conn, line, sizeof(line), 30000);
        if (r != 1) {
            close(fd);
            return CA_ERR_INVALID;
        }
        if (!line[0]) break;
        if (!strncasecmp(line, "content-length:", 15)) {
            length = strtoul(line + 15, NULL, 10);
            have_length = 1;
        } else if (!strncasecmp(line, "transfer-encoding:", 18) && strstr(line, "chunked")) {
            chunked = 1;
        }
    }
    coord_buf out;
    memset(&out, 0, sizeof(out));
    if (have_length) {
        if (length >= 1u << 24) {
            close(fd);
            return CA_ERR_LIMIT;
        }
        char *buf = calloc(length + 1, 1);
        if (!buf) {
            close(fd);
            return CA_ERR_NOMEM;
        }
        if (length && conn_read_exact(&conn, buf, length, 30000) < 0) {
            free(buf);
            close(fd);
            return CA_ERR_INVALID;
        }
        out.p = buf;
        out.len = length;
    } else if (chunked) {
        /*
         * HTTP/1.1 chunked.  Not optional to support: Go sets no
         * Content-Length on a streamed body and switches to chunked once
         * it outgrows its write buffer, which a sync delta does as soon
         * as the log is more than a handful of check-ins -- and the
         * nginx in deploy/ can re-chunk whatever the hub decided.  Read
         * as payload, the size lines corrupt or drop check-in lines.
         */
        for (;;) {
            if (conn_read_line(&conn, line, sizeof(line), 30000) != 1) break;
            char *end = NULL;
            unsigned long n = strtoul(line, &end, 16);
            if (end == line) break; /* not a size line: give up on the body */
            if (n == 0) break;      /* the last chunk; trailers are ignored */
            if (n >= 1u << 24 || out.len + n >= 1u << 24) {
                free(out.p);
                close(fd);
                return CA_ERR_LIMIT;
            }
            char *chunk = malloc(n);
            if (!chunk) {
                free(out.p);
                close(fd);
                return CA_ERR_NOMEM;
            }
            if (conn_read_exact(&conn, chunk, n, 30000) < 0) {
                free(chunk);
                break;
            }
            int bad = buf_add(&out, chunk, n) < 0;
            free(chunk);
            if (bad) break;
            /* The CRLF that closes the chunk. */
            if (conn_read_line(&conn, line, sizeof(line), 30000) != 1) break;
        }
    } else {
        /* No length and no encoding: read to EOF. */
        for (;;) {
            int r = conn_read_line(&conn, line, sizeof(line), 30000);
            if (r != 1) break;
            if (buf_add(&out, line, strlen(line)) < 0 || buf_add(&out, "\n", 1) < 0) break;
        }
    }
    close(fd);
    *body = out.p ? out.p : calloc(1, 1);
    return CA_OK;
}

ca_status ca_coord_fetch_job(const char *url, const char *token, ca_coord_job *job)
{
    if (!url || !job) return CA_ERR_INVALID;
    int status = 0;
    char *body = NULL;
    ca_status rc = coord_request(url, token, "GET", "/v1/job", NULL, &status, &body);
    if (rc != CA_OK) return rc;
    if (status != 200) {
        ca_set_error("GET /v1/job: HTTP %d", status);
        free(body);
        return CA_ERR_INVALID;
    }
    /* One line, trailing newline trimmed. */
    char *nl = strchr(body, '\n');
    if (nl) *nl = 0;
    rc = ca_coord_job_decode(job, body);
    free(body);
    return rc;
}

ca_status ca_coord_sync_once(const char *url, const char *token, const ca_coord_ctx *ctx,
                             ca_coord_state *st, uint64_t *received, uint64_t *rejected)
{
    if (!url || !ctx || !st) return CA_ERR_INVALID;
    if (received) *received = 0;
    if (rejected) *rejected = 0;

    /* Our vector, then everything we hold: the hub keeps what it lacks
     * and ignores the rest, which is what idempotent merging buys. */
    coord_buf req;
    memset(&req, 0, sizeof(req));
    ca_coord_vv *mine = NULL;
    if (ca_coord_vv_new(&mine) == CA_OK) {
        ca_coord_state_vv(st, mine);
        buf_add_vv(&req, mine);
        ca_coord_vv_free(mine);
    }
    ca_coord_delta_for(st, NULL, buf_collect_checkin, &req);
    if (req.failed) {
        free(req.p);
        return CA_ERR_NOMEM;
    }

    int status = 0;
    char *body = NULL;
    ca_status rc =
        coord_request(url, token, "POST", "/v1/sync", req.p ? req.p : "", &status, &body);
    free(req.p);
    if (rc != CA_OK) return rc;
    if (status != 200) {
        ca_set_error("POST /v1/sync: HTTP %d", status);
        free(body);
        return CA_ERR_INVALID;
    }
    for (char *save = NULL, *tok = strtok_r(body, "\n", &save); tok;
         tok = strtok_r(NULL, "\n", &save)) {
        if (strncmp(tok, "ci ", 3) != 0) continue;
        ca_coord_checkin ci;
        if (ca_coord_checkin_decode(&ci, tok) != CA_OK) {
            if (rejected) (*rejected)++;
            continue;
        }
        ca_coord_outcome oc;
        if (ca_coord_apply(st, ctx, &ci, (uint64_t)time(NULL), 1, &oc) != CA_OK) {
            if (rejected) (*rejected)++;
            continue;
        }
        if (oc.fresh && received) (*received)++;
        if (rejected) *rejected += oc.rejected_dps;
    }
    free(body);
    return CA_OK;
}
