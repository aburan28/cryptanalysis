/*
 * coord_net.c - the hub, the reverse channel, and the agent that dials
 * out to them.  POSIX sockets, blocking I/O, one thread per connection.
 *
 * The transport carries the lines coord.c defines and adds nothing to
 * them: every fact still arrives as a check-in and is still merged by
 * ca_coord_apply with verification on.  So this file can be wrong about
 * who is connected, or lose a connection entirely, without being able to
 * corrupt anybody's answer.
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
#include <stdio.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <unistd.h>

/* ---- small socket helpers ---------------------------------------------- */

typedef struct coord_conn {
    int fd;
    char buf[CA_COORD_LINE_MAX];
    size_t len;   /* bytes buffered */
    size_t pos;   /* bytes consumed */
    int overflow; /* a line longer than the buffer was seen */
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
        ca_set_error("%s: no TLS here; terminate it in front and pass the http:// address", url);
        return CA_ERR_UNSUPPORTED;
    }
    const char *p = url;
    if (strncmp(p, "http://", 7) == 0) p += 7;
    const char *slash = strchr(p, '/');
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

/* ---- the hub ------------------------------------------------------------ */

struct ca_coord_hub {
    const ca_coord_ctx *ctx;
    ca_coord_state *st;
    char token[256];
    int have_token;
    uint64_t lease_secs;
    uint32_t push_ms, idle_secs;
    void (*on_checkin)(void *, const ca_coord_checkin *);
    void *on_checkin_user;

    int listen_fd;
    char address[128];
    pthread_t thread;
    atomic_int stop;
    atomic_int running;

    atomic_uint_fast64_t agents, channels_total, accepted, rejected, pushed, unauthorized;
    /* Connection threads are detached, so this is what ca_coord_hub_stop
     * waits on before anything they touch is freed. */
    atomic_uint_fast64_t live_conns;
};

void ca_coord_hub_params_default(ca_coord_hub_params *p)
{
    memset(p, 0, sizeof(*p));
    p->bind = "0.0.0.0:8080";
    p->lease_secs = 120;
    p->push_ms = 500;
    p->idle_secs = 300;
}

/* Merge one check-in from an agent and run the durability hook. */
static void hub_absorb(ca_coord_hub *hub, const ca_coord_checkin *ci, uint32_t *acc, uint32_t *rej)
{
    ca_coord_outcome oc;
    ca_status rc = ca_coord_apply(hub->st, hub->ctx, ci, (uint64_t)time(NULL), 1, &oc);
    if (rc != CA_OK) {
        atomic_fetch_add(&hub->rejected, 1);
        if (rej) (*rej)++;
        return;
    }
    if (oc.fresh) {
        atomic_fetch_add(&hub->accepted, 1);
        if (hub->on_checkin) hub->on_checkin(hub->on_checkin_user, ci);
    }
    if (oc.rejected_dps) atomic_fetch_add(&hub->rejected, oc.rejected_dps);
    if (acc) *acc += oc.accepted_dps;
    if (rej) *rej += oc.rejected_dps;
}

/* Write every check-in the holder of `known` lacks, as a batch. */
typedef struct hub_push_ctx {
    coord_conn *conn;
    pthread_mutex_t *wlock;
    uint64_t count;
    int failed;
} hub_push_ctx;

static int hub_push_one(void *user, const ca_coord_checkin *ci)
{
    hub_push_ctx *hp = user;
    char line[CA_COORD_LINE_MAX];
    if (!ca_coord_checkin_encode(ci, line, sizeof(line))) return 0;
    if (hp->wlock) pthread_mutex_lock(hp->wlock);
    int rc = conn_line(hp->conn, line);
    if (hp->wlock) pthread_mutex_unlock(hp->wlock);
    if (rc < 0) {
        hp->failed = 1;
        return 1; /* stop the walk */
    }
    hp->count++;
    return 0;
}

/* Shared between a channel's reader (this thread) and its pusher. */
typedef struct hub_channel {
    ca_coord_hub *hub;
    coord_conn *conn;
    pthread_mutex_t wlock; /* the socket's write half */
    pthread_mutex_t vlock; /* `known` below */
    ca_coord_vv *known;    /* what the agent has, as best we know */
    atomic_int alive;
} hub_channel;

/*
 * The pusher: the half of the reverse channel that makes it reverse.
 * It wakes on a timer, asks the state what this agent is missing, and
 * writes it down the socket the agent opened.  An idle channel gets a
 * ping instead, because the NAT and the proxy between us both drop
 * silent connections.
 */
static void *hub_pusher(void *arg)
{
    hub_channel *ch = arg;
    ca_coord_hub *hub = ch->hub;
    uint64_t last_ping = (uint64_t)time(NULL);
    uint32_t ping_every = hub->idle_secs / 3 ? hub->idle_secs / 3 : 1;
    while (atomic_load(&ch->alive) && !atomic_load(&hub->stop)) {
        struct timespec ts = {hub->push_ms / 1000, (long)(hub->push_ms % 1000) * 1000000L};
        nanosleep(&ts, NULL);
        if (!atomic_load(&ch->alive)) break;

        ca_coord_vv *snapshot = NULL;
        if (ca_coord_vv_new(&snapshot) != CA_OK) continue;
        pthread_mutex_lock(&ch->vlock);
        for (size_t i = 0; ch->known && i < ch->known->count; i++)
            ca_coord_vv_set(snapshot, ch->known->e[i].name, ch->known->e[i].max_seq);
        pthread_mutex_unlock(&ch->vlock);

        hub_push_ctx hp = {.conn = ch->conn, .wlock = &ch->wlock};
        ca_coord_delta_for(hub->st, snapshot, hub_push_one, &hp);
        ca_coord_vv_free(snapshot);
        if (hp.failed) {
            atomic_store(&ch->alive, 0);
            break;
        }
        if (hp.count) {
            atomic_fetch_add(&hub->pushed, hp.count);
            /* The agent now holds at least what we just sent.  Its own
             * pull can still lower this, which costs one resend. */
            pthread_mutex_lock(&ch->vlock);
            ca_coord_state_vv(hub->st, ch->known);
            pthread_mutex_unlock(&ch->vlock);
            last_ping = (uint64_t)time(NULL);
            continue;
        }
        uint64_t now = (uint64_t)time(NULL);
        if (now - last_ping >= ping_every) {
            last_ping = now;
            pthread_mutex_lock(&ch->wlock);
            int rc = conn_line(ch->conn, "ping");
            pthread_mutex_unlock(&ch->wlock);
            if (rc < 0) {
                atomic_store(&ch->alive, 0);
                break;
            }
        }
    }
    return NULL;
}

/* The channel's reader half, on the connection's own thread. */
static void hub_run_channel(ca_coord_hub *hub, coord_conn *conn)
{
    hub_channel ch;
    memset(&ch, 0, sizeof(ch));
    ch.hub = hub;
    ch.conn = conn;
    pthread_mutex_init(&ch.wlock, NULL);
    pthread_mutex_init(&ch.vlock, NULL);
    if (ca_coord_vv_new(&ch.known) != CA_OK) {
        pthread_mutex_destroy(&ch.wlock);
        pthread_mutex_destroy(&ch.vlock);
        return;
    }
    atomic_store(&ch.alive, 1);
    atomic_fetch_add(&hub->agents, 1);
    atomic_fetch_add(&hub->channels_total, 1);

    pthread_t pusher;
    int have_pusher = pthread_create(&pusher, NULL, hub_pusher, &ch) == 0;

    char line[CA_COORD_LINE_MAX];
    uint64_t last_seen = (uint64_t)time(NULL);
    while (atomic_load(&ch.alive) && !atomic_load(&hub->stop)) {
        int rc = conn_read_line(conn, line, sizeof(line), 500);
        if (rc < 0) break;
        if (rc == 0) {
            if ((uint64_t)time(NULL) - last_seen >= hub->idle_secs) break;
            continue;
        }
        last_seen = (uint64_t)time(NULL);
        if (strncmp(line, "hello ", 6) == 0 || strncmp(line, "pull ", 5) == 0) {
            /* hello <job-id> <peer> [<peer>:<seq> …]  |  pull [<peer>:<seq> …] */
            const char *p = line + (line[0] == 'h' ? 6 : 5);
            if (line[0] == 'h') {
                char *end = NULL;
                uint64_t job = (uint64_t)strtoull(p, &end, 10);
                if (end == p || job != hub->ctx->job.id) {
                    pthread_mutex_lock(&ch.wlock);
                    conn_line(conn, "err different job");
                    pthread_mutex_unlock(&ch.wlock);
                    atomic_fetch_add(&hub->rejected, 1);
                    break;
                }
                p = end;
                while (*p == ' ') p++;
                while (*p && *p != ' ') p++; /* skip the peer name */
            }
            ca_coord_vv *vv = NULL;
            if (ca_coord_vv_new(&vv) == CA_OK) {
                while (*p) {
                    while (*p == ' ') p++;
                    if (!*p) break;
                    const char *colon = strchr(p, ':');
                    const char *space = strchr(p, ' ');
                    if (!colon || (space && colon > space)) break;
                    char name[CA_COORD_PEER_MAX];
                    size_t nlen = (size_t)(colon - p);
                    if (nlen >= sizeof(name)) break;
                    memcpy(name, p, nlen);
                    name[nlen] = 0;
                    char *end = NULL;
                    uint64_t seq = (uint64_t)strtoull(colon + 1, &end, 10);
                    if (end == colon + 1) break;
                    ca_coord_vv_set(vv, name, seq);
                    p = end;
                }
                pthread_mutex_lock(&ch.vlock);
                ca_coord_vv_free(ch.known);
                ch.known = vv;
                pthread_mutex_unlock(&ch.vlock);
            }
        } else if (strncmp(line, "ci ", 3) == 0) {
            ca_coord_checkin ci;
            uint32_t acc = 0, rej = 0;
            if (ca_coord_checkin_decode(&ci, line) == CA_OK) {
                hub_absorb(hub, &ci, &acc, &rej);
            } else {
                atomic_fetch_add(&hub->rejected, 1);
                rej++;
            }
            char ack[64];
            snprintf(ack, sizeof(ack), "ack %u %u", acc, rej);
            pthread_mutex_lock(&ch.wlock);
            int wrc = conn_line(conn, ack);
            pthread_mutex_unlock(&ch.wlock);
            if (wrc < 0) break;
        } else if (strncmp(line, "ping", 4) == 0) {
            /* keepalive; nothing to do */
        }
    }

    atomic_store(&ch.alive, 0);
    if (have_pusher) pthread_join(pusher, NULL);
    pthread_mutex_lock(&ch.vlock);
    ca_coord_vv_free(ch.known);
    ch.known = NULL;
    pthread_mutex_unlock(&ch.vlock);
    pthread_mutex_destroy(&ch.wlock);
    pthread_mutex_destroy(&ch.vlock);
    atomic_fetch_sub(&hub->agents, 1);
}

static void hub_respond(coord_conn *c, int status, const char *reason, const char *body)
{
    char head[256];
    snprintf(head, sizeof(head),
             "HTTP/1.1 %d %s\r\nContent-Type: text/plain; charset=utf-8\r\n"
             "Content-Length: %zu\r\nConnection: close\r\n\r\n",
             status, reason, strlen(body));
    conn_puts(c, head);
    conn_puts(c, body);
}

static void hub_status_body(ca_coord_hub *hub, char *out, size_t cap)
{
    ca_coord_progress pr;
    ca_coord_progress_get(hub->st, hub->ctx, (uint64_t)time(NULL), hub->lease_secs, &pr);
    /* JSON out, like every other thing this library prints. */
    snprintf(out, cap,
             "{\"job_id\":\"%016" PRIx64 "\",\"steps\":%" PRIu64 ",\"fraction\":%.6f,"
             "\"dps\":%" PRIu64 ",\"units_completed\":%" PRIu64 ",\"units_active\":%" PRIu64 ","
             "\"peers\":%" PRIu64 ",\"checkins\":%" PRIu64 ",\"rejected_dps\":%" PRIu64 ","
             "\"agents\":%" PRIu64 ",\"channels\":%" PRIu64 ",\"accepted\":%" PRIu64 ","
             "\"pushed\":%" PRIu64 ",\"rejected\":%" PRIu64 ",\"unauthorized\":%" PRIu64 ","
             "\"solved\":%s,\"solution\":%" PRIu64 "}\n",
             hub->ctx->job.id, pr.steps, pr.fraction, pr.dps_stored, pr.units_completed,
             pr.units_active, pr.peers, pr.checkins, pr.rejected_dps,
             (uint64_t)atomic_load(&hub->agents), (uint64_t)atomic_load(&hub->channels_total),
             (uint64_t)atomic_load(&hub->accepted), (uint64_t)atomic_load(&hub->pushed),
             (uint64_t)atomic_load(&hub->rejected), (uint64_t)atomic_load(&hub->unauthorized),
             pr.have_solution ? "true" : "false", pr.solution);
}

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

/* One connection: an HTTP request, then either a reply or a channel. */
static void hub_serve(ca_coord_hub *hub, int fd)
{
    coord_conn conn;
    conn_init(&conn, fd);
    char line[CA_COORD_LINE_MAX];
    if (conn_read_line_until(&conn, line, sizeof(line), 15000, &hub->stop) != 1) return;

    char method[16] = {0}, path[512] = {0};
    if (sscanf(line, "%15s %511s", method, path) != 2) {
        hub_respond(&conn, 400, "Bad Request", "bad request line\n");
        return;
    }
    char auth[512] = {0}, upgrade[64] = {0};
    size_t content_length = 0;
    for (;;) {
        int rc = conn_read_line_until(&conn, line, sizeof(line), 15000, &hub->stop);
        if (rc != 1) return;
        if (!line[0]) break;
        const char *colon = strchr(line, ':');
        if (!colon) continue;
        size_t nlen = (size_t)(colon - line);
        const char *val = colon + 1;
        while (*val == ' ') val++;
        if (nlen == 13 && !strncasecmp(line, "authorization", 13))
            snprintf(auth, sizeof(auth), "%s", val);
        else if (nlen == 7 && !strncasecmp(line, "upgrade", 7))
            snprintf(upgrade, sizeof(upgrade), "%s", val);
        else if (nlen == 14 && !strncasecmp(line, "content-length", 14))
            content_length = strtoul(val, NULL, 10);
    }

    /* Strip any path prefix a reverse proxy left on, then match the
     * route by its tail: a hub published under /rho answers the same. */
    const char *route = path;
    const char *v1 = strstr(path, "/v1/");
    if (v1)
        route = v1;
    else if (strstr(path, "/healthz"))
        route = strstr(path, "/healthz");

    /* /healthz is outside the token on purpose: a load balancer carries
     * no credential, and the answer says nothing about the job. */
    if (strncmp(route, "/healthz", 8) == 0) {
        hub_respond(&conn, 200, "OK", "{\"ok\":true}\n");
        return;
    }
    if (hub->have_token) {
        const char *bearer = strncmp(auth, "Bearer ", 7) == 0 ? auth + 7 : NULL;
        if (!bearer || !coord_token_eq(bearer, hub->token)) {
            atomic_fetch_add(&hub->unauthorized, 1);
            hub_respond(&conn, 401, "Unauthorized", "bad or missing bearer token\n");
            return;
        }
    }

    if (!strcmp(method, "GET") && !strncmp(route, "/v1/job", 7)) {
        char job[CA_COORD_LINE_MAX];
        char body[CA_COORD_LINE_MAX + 2];
        if (!ca_coord_job_encode(&hub->ctx->job, job, sizeof(job))) {
            hub_respond(&conn, 500, "Internal Server Error", "job does not encode\n");
            return;
        }
        if (snprintf(body, sizeof(body), "%s\n", job) < 0) {
            hub_respond(&conn, 500, "Internal Server Error", "job does not encode\n");
            return;
        }
        hub_respond(&conn, 200, "OK", body);
        return;
    }
    if (!strcmp(method, "GET") && !strncmp(route, "/v1/status", 10)) {
        char body[1024];
        hub_status_body(hub, body, sizeof(body));
        hub_respond(&conn, 200, "OK", body);
        return;
    }
    if (!strcmp(method, "POST") && !strncmp(route, "/v1/sync", 8)) {
        /* One-shot: the body is the caller's lines (a vector, then any
         * check-ins); the reply is the check-ins it lacks. */
        if (content_length >= 1u << 22) {
            hub_respond(&conn, 413, "Payload Too Large", "body too large\n");
            return;
        }
        char *body = calloc(content_length + 1, 1);
        if (!body) {
            hub_respond(&conn, 500, "Internal Server Error", "out of memory\n");
            return;
        }
        if (content_length && conn_read_exact(&conn, body, content_length, 15000) < 0) {
            free(body);
            return;
        }
        ca_coord_vv *known = NULL;
        ca_coord_vv_new(&known);
        uint32_t acc = 0, rej = 0;
        for (char *save = NULL, *tok = strtok_r(body, "\n", &save); tok;
             tok = strtok_r(NULL, "\n", &save)) {
            if (!strncmp(tok, "ci ", 3)) {
                ca_coord_checkin ci;
                if (ca_coord_checkin_decode(&ci, tok) == CA_OK)
                    hub_absorb(hub, &ci, &acc, &rej);
                else {
                    atomic_fetch_add(&hub->rejected, 1);
                    rej++;
                }
            } else if (!strncmp(tok, "vv ", 3) && known) {
                char *p = tok + 3;
                while (*p) {
                    while (*p == ' ') p++;
                    if (!*p) break;
                    char *colon = strchr(p, ':');
                    if (!colon) break;
                    char name[CA_COORD_PEER_MAX];
                    size_t nlen = (size_t)(colon - p);
                    if (nlen >= sizeof(name)) break;
                    memcpy(name, p, nlen);
                    name[nlen] = 0;
                    char *end = NULL;
                    uint64_t seq = (uint64_t)strtoull(colon + 1, &end, 10);
                    if (end == colon + 1) break;
                    ca_coord_vv_set(known, name, seq);
                    p = end;
                }
            }
        }
        free(body);

        /* The reply: our version vector first (so the caller can push
         * exactly what we lack next), then the check-ins it lacks. */
        coord_buf b;
        memset(&b, 0, sizeof(b));
        ca_coord_vv *mine = NULL;
        if (ca_coord_vv_new(&mine) == CA_OK) {
            ca_coord_state_vv(hub->st, mine);
            buf_add_vv(&b, mine);
            ca_coord_vv_free(mine);
        }
        ca_coord_delta_for(hub->st, known, buf_collect_checkin, &b);
        ca_coord_vv_free(known);
        if (b.failed) {
            free(b.p);
            hub_respond(&conn, 500, "Internal Server Error", "out of memory\n");
            return;
        }
        hub_respond(&conn, 200, "OK", b.p ? b.p : "");
        free(b.p);
        return;
    }
    if (!strcmp(method, "GET") && !strncmp(route, "/v1/channel", 11)) {
        if (strcasecmp(upgrade, CA_COORD_PROTOCOL) != 0) {
            hub_respond(&conn, 426, "Upgrade Required", "upgrade to " CA_COORD_PROTOCOL "\n");
            return;
        }
        conn_puts(&conn, "HTTP/1.1 101 Switching Protocols\r\nUpgrade: " CA_COORD_PROTOCOL
                         "\r\nConnection: Upgrade\r\n\r\n");
        hub_run_channel(hub, &conn);
        return;
    }
    hub_respond(&conn, 404, "Not Found", "no such route\n");
}

typedef struct hub_conn_arg {
    ca_coord_hub *hub;
    int fd;
} hub_conn_arg;

static void *hub_conn_main(void *arg)
{
    hub_conn_arg *a = arg;
    ca_coord_hub *hub = a->hub;
    hub_serve(hub, a->fd);
    close(a->fd);
    free(a);
    atomic_fetch_sub(&hub->live_conns, 1);
    return NULL;
}

static void *hub_accept_main(void *arg)
{
    ca_coord_hub *hub = arg;
    while (!atomic_load(&hub->stop)) {
        struct pollfd pf = {.fd = hub->listen_fd, .events = POLLIN};
        int pr = poll(&pf, 1, 200);
        if (pr <= 0) continue;
        int fd = accept(hub->listen_fd, NULL, NULL);
        if (fd < 0) continue;
        hub_conn_arg *a = calloc(1, sizeof(*a));
        if (!a) {
            close(fd);
            continue;
        }
        a->hub = hub;
        a->fd = fd;
        pthread_t t;
        /* Counted before the thread exists, so the count is never lower
         * than the truth: ca_coord_hub_stop waits on it. */
        atomic_fetch_add(&hub->live_conns, 1);
        if (pthread_create(&t, NULL, hub_conn_main, a) != 0) {
            atomic_fetch_sub(&hub->live_conns, 1);
            close(fd);
            free(a);
            continue;
        }
        pthread_detach(t);
    }
    atomic_store(&hub->running, 0);
    return NULL;
}

ca_status ca_coord_hub_start(ca_coord_hub **out, const ca_coord_ctx *ctx, ca_coord_state *st,
                             const ca_coord_hub_params *p)
{
    if (!out || !ctx || !st || !p || !p->bind) return CA_ERR_INVALID;
    *out = NULL;
    ca_coord_hub *hub = calloc(1, sizeof(*hub));
    if (!hub) return CA_ERR_NOMEM;
    hub->ctx = ctx;
    hub->st = st;
    hub->lease_secs = p->lease_secs ? p->lease_secs : 120;
    hub->push_ms = p->push_ms ? p->push_ms : 500;
    hub->idle_secs = p->idle_secs ? p->idle_secs : 300;
    hub->on_checkin = p->on_checkin;
    hub->on_checkin_user = p->on_checkin_user;
    if (p->token && p->token[0]) {
        snprintf(hub->token, sizeof(hub->token), "%s", p->token);
        hub->have_token = 1;
    }

    char host[256], port[32];
    if (!coord_split(p->bind, host, sizeof(host), port, sizeof(port))) {
        ca_set_error("%s: expected host:port", p->bind);
        free(hub);
        return CA_ERR_INVALID;
    }
    struct addrinfo hints, *res = NULL;
    memset(&hints, 0, sizeof(hints));
    hints.ai_family = AF_INET;
    hints.ai_socktype = SOCK_STREAM;
    hints.ai_flags = AI_PASSIVE;
    if (getaddrinfo(host[0] ? host : NULL, port, &hints, &res) != 0) {
        ca_set_error("%s: cannot resolve", p->bind);
        free(hub);
        return CA_ERR_INVALID;
    }
    hub->listen_fd = socket(res->ai_family, res->ai_socktype, res->ai_protocol);
    if (hub->listen_fd < 0) {
        freeaddrinfo(res);
        free(hub);
        return CA_ERR_INTERNAL;
    }
    int one = 1;
    setsockopt(hub->listen_fd, SOL_SOCKET, SO_REUSEADDR, &one, sizeof(one));
    if (bind(hub->listen_fd, res->ai_addr, res->ai_addrlen) != 0 ||
        listen(hub->listen_fd, 128) != 0) {
        ca_set_error("%s: %s", p->bind, strerror(errno));
        freeaddrinfo(res);
        close(hub->listen_fd);
        free(hub);
        return CA_ERR_INVALID;
    }
    freeaddrinfo(res);

    struct sockaddr_in sin;
    memset(&sin, 0, sizeof(sin));
    socklen_t slen = sizeof(sin);
    if (getsockname(hub->listen_fd, (struct sockaddr *)&sin, &slen) == 0) {
        char ip[64];
        inet_ntop(AF_INET, &sin.sin_addr, ip, sizeof(ip));
        snprintf(hub->address, sizeof(hub->address), "%s:%u", ip, ntohs(sin.sin_port));
    } else {
        snprintf(hub->address, sizeof(hub->address), "%s", p->bind);
    }

    atomic_store(&hub->running, 1);
    if (pthread_create(&hub->thread, NULL, hub_accept_main, hub) != 0) {
        close(hub->listen_fd);
        free(hub);
        return CA_ERR_INTERNAL;
    }
    *out = hub;
    return CA_OK;
}

const char *ca_coord_hub_address(const ca_coord_hub *hub) { return hub ? hub->address : ""; }

void ca_coord_hub_stats_get(const ca_coord_hub *hub, ca_coord_hub_stats *out)
{
    memset(out, 0, sizeof(*out));
    if (!hub) return;
    out->agents = atomic_load(&hub->agents);
    out->channels_total = atomic_load(&hub->channels_total);
    out->accepted = atomic_load(&hub->accepted);
    out->rejected = atomic_load(&hub->rejected);
    out->pushed = atomic_load(&hub->pushed);
    out->unauthorized = atomic_load(&hub->unauthorized);
}

/*
 * Stop, and do not return until every thread that could still touch the
 * hub or the caller's state has left.  The caller frees that state right
 * after this call, so returning early is a use-after-free -- which is
 * what ThreadSanitizer reports if this loop is removed.
 */
void ca_coord_hub_stop(ca_coord_hub *hub)
{
    if (!hub) return;
    atomic_store(&hub->stop, 1);
    /* Wake the accept loop out of poll(). */
    shutdown(hub->listen_fd, SHUT_RDWR);
    pthread_join(hub->thread, NULL);
    while (atomic_load(&hub->live_conns) > 0) {
        struct timespec ts = {0, 5 * 1000000L};
        nanosleep(&ts, NULL);
    }
    close(hub->listen_fd);
    free(hub);
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
    char token[256];
    int have_token;
    char peer[CA_COORD_PEER_MAX];
    const ca_coord_ctx *ctx;
    ca_coord_state *st;

    pthread_mutex_t lock; /* the outbox and the stats */
    char **outbox;        /* encoded check-in lines, oldest first */
    size_t out_count, out_cap;
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
        char hdr[512];
        snprintf(hdr, sizeof(hdr), "Authorization: Bearer %s\r\n", ag->token);
        if (conn_puts(&conn, req) < 0 || conn_puts(&conn, hdr) < 0) {
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
        /* Everything the lanes produced since the last turn goes up. */
        char *pending = NULL;
        pthread_mutex_lock(&ag->lock);
        if (ag->out_count) {
            pending = ag->outbox[0];
            memmove(ag->outbox, ag->outbox + 1, (ag->out_count - 1) * sizeof(*ag->outbox));
            ag->out_count--;
        }
        pthread_mutex_unlock(&ag->lock);
        if (pending) {
            int wrc = conn_line(&conn, pending);
            free(pending);
            if (wrc < 0) break;
            pthread_mutex_lock(&ag->lock);
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
        else if (!strncmp(line, "err ", 4)) {
            agent_note_error(ag, line + 4);
            close(fd);
            return -1;
        }
        /* "ack" and "ping" need no action. */
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
        snprintf(ag->token, sizeof(ag->token), "%s", token);
        ag->have_token = 1;
    }
    ag->ctx = ctx;
    ag->st = st;
    if (pthread_mutex_init(&ag->lock, NULL) != 0) {
        free(ag);
        return CA_ERR_INTERNAL;
    }
    if (pthread_create(&ag->thread, NULL, agent_main, ag) != 0) {
        pthread_mutex_destroy(&ag->lock);
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
    int n = snprintf(head, sizeof(head), "%s %s%s HTTP/1.1\r\nHost: %s\r\nConnection: close\r\n",
                     method, prefix, route, host_port);
    if (n > 0) buf_add(&req, head, (size_t)n);
    if (token && token[0]) {
        n = snprintf(head, sizeof(head), "Authorization: Bearer %s\r\n", token);
        if (n > 0) buf_add(&req, head, (size_t)n);
    }
    if (req_body) {
        n = snprintf(head, sizeof(head), "Content-Type: text/plain\r\nContent-Length: %zu\r\n",
                     strlen(req_body));
        if (n > 0) buf_add(&req, head, (size_t)n);
    }
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
    int have_length = 0;
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
    } else {
        /* No length: read to EOF. */
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
