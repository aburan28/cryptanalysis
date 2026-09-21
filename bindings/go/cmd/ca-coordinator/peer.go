package main

import (
	"bufio"
	"context"
	"fmt"
	"io"
	"net/http"
	"strconv"
	"strings"
	"sync/atomic"
	"time"

	ca "github.com/aburan28/cryptanalysis/bindings/go"
)

// A Peer is another coordinator this one gossips with.
//
// Federation needs no new protocol.  /v1/sync is already a symmetric
// anti-entropy exchange -- post the check-ins you hold and the version
// vector describing them, receive the ones you lack -- so a hub peers by
// being a client of the endpoint it already serves.
//
// What makes this safe rather than merely convenient is the merge.  It is
// commutative, associative and idempotent, and every record carries its own
// proof (a*G + b*H == point) which the receiver checks before accepting.  A
// peer that is broken, slow, duplicating, or hostile can waste bandwidth; it
// cannot corrupt the table or invent a solution.  So there is no leader
// among hubs, no quorum to lose, and no order the exchanges must happen in.
type Peer struct {
	Name  string
	URL   string
	Token string
}

// peerState is what this hub believes a peer already holds, so each round
// sends the difference rather than the world.
type peerState struct {
	peer    Peer
	known   ca.VersionVector
	greeted bool
}

// PeerStats counts what federation has done, per peer.  Check-ins and
// distinguished points are counted separately: one check-in carries many
// points, and conflating them makes both numbers meaningless.
type PeerStats struct {
	Name        string `json:"name"`
	URL         string `json:"url"`
	Syncs       int64  `json:"syncs"`
	CheckinsOut int64  `json:"checkins_out"`
	CheckinsIn  int64  `json:"checkins_in"`
	DPsAccepted int64  `json:"dps_accepted"`
	DPsRejected int64  `json:"dps_rejected"`
	Errors      int64  `json:"errors"`
	LastError   string `json:"last_error,omitempty"`
}

type peerCounters struct {
	syncs, out, in, dpsOK, dpsBad, errors atomic.Int64
	lastError                             atomic.Value // string
}

// peerLoop gossips with one peer until the context ends.  Each peer runs on
// its own goroutine: a peer that is unreachable delays nobody else, which is
// the point of having several.
func (h *Hub) peerLoop(ctx context.Context, p Peer, c *peerCounters) {
	interval := h.cfg.PeerInterval
	if interval <= 0 {
		interval = 5 * time.Second
	}
	st := &peerState{peer: p, known: ca.VersionVector{}}
	tick := time.NewTicker(interval)
	defer tick.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-tick.C:
		}
		if err := h.syncPeer(ctx, st, c); err != nil {
			c.errors.Add(1)
			c.lastError.Store(err.Error())
			if h.cfg.Log != nil {
				h.cfg.Log.Warn("peer sync failed", "peer", p.Name, "url", p.URL, "err", err)
			}
		}
	}
}

// syncPeer runs one exchange.
//
// The first exchange with a peer sends no check-ins, only our version
// vector: we have no idea what it holds, and the alternative -- assuming it
// holds nothing -- would dump the whole log at it after every restart of
// this process.  Its reply tells us where it stands, and from then on each
// round sends exactly the difference.
func (h *Hub) syncPeer(ctx context.Context, st *peerState, c *peerCounters) error {
	var body strings.Builder
	fmt.Fprintf(&body, "vv%s\n", h.state.VersionVector())
	sent := 0
	if st.greeted {
		lines, reached := h.state.DeltaSince(st.known)
		for _, line := range lines {
			fmt.Fprintln(&body, line)
		}
		sent = len(lines)
		// Credit the peer with what is on its way, not with everything we
		// hold; the reply's vector corrects this either way.
		st.known = reached
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost,
		strings.TrimRight(st.peer.URL, "/")+"/v1/sync", strings.NewReader(body.String()))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "text/plain")
	req.Header.Set("Content-Length", strconv.Itoa(body.Len()))
	if st.peer.Token != "" {
		req.Header.Set("Authorization", "Bearer "+st.peer.Token)
	}
	resp, err := h.peerClient().Do(req)
	if err != nil {
		return err
	}
	defer func() {
		_, _ = io.Copy(io.Discard, io.LimitReader(resp.Body, 1<<20))
		_ = resp.Body.Close()
	}()
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("%s: %s", st.peer.URL, resp.Status)
	}

	in, dpsOK, dpsBad := 0, 0, 0
	sc := bufio.NewScanner(io.LimitReader(resp.Body, 1<<24))
	sc.Buffer(make([]byte, 0, 64<<10), ca.LineMax)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		switch {
		case strings.HasPrefix(line, "vv"):
			// Where the peer stands now, including anything we just gave it.
			st.known = ca.ParseVersionVector(line)
			st.greeted = true
		case strings.HasPrefix(line, "ci "):
			// Straight through the same path an agent's check-in takes:
			// a foreign job, a forged point or a bogus solution is refused
			// exactly as it would be from an agent, and the durability
			// hook and the solved log fire the same way.  Peering grants a
			// hub no authority it did not already have.
			acc, rej := h.absorb(line)
			in++
			dpsOK += acc
			dpsBad += rej
		}
	}
	if err := sc.Err(); err != nil {
		return err
	}
	c.syncs.Add(1)
	c.out.Add(int64(sent))
	c.in.Add(int64(in))
	c.dpsOK.Add(int64(dpsOK))
	c.dpsBad.Add(int64(dpsBad))
	return nil
}

func (h *Hub) peerClient() *http.Client {
	if h.httpClient != nil {
		return h.httpClient
	}
	return http.DefaultClient
}

// PeerStats reports one row per configured peer, in configured order.
func (h *Hub) PeerStats() []PeerStats {
	out := make([]PeerStats, 0, len(h.cfg.Peers))
	for i, p := range h.cfg.Peers {
		c := h.peers[i]
		s := PeerStats{
			Name:        p.Name,
			URL:         p.URL,
			Syncs:       c.syncs.Load(),
			CheckinsOut: c.out.Load(),
			CheckinsIn:  c.in.Load(),
			DPsAccepted: c.dpsOK.Load(),
			DPsRejected: c.dpsBad.Load(),
			Errors:      c.errors.Load(),
		}
		if v, ok := c.lastError.Load().(string); ok {
			s.LastError = v
		}
		out = append(out, s)
	}
	return out
}

// StartPeering launches one goroutine per configured peer.  It returns
// immediately; the goroutines stop when ctx is cancelled.
func (h *Hub) StartPeering(ctx context.Context) {
	for i := range h.cfg.Peers {
		go h.peerLoop(ctx, h.cfg.Peers[i], h.peers[i])
	}
}
