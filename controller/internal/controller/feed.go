package controller

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

// maxFeedBytes bounds status.json reads; the real document is a few KiB.
const maxFeedBytes = 1 << 20

// Feed is the subset of the coordinator status document the controller acts on.
type Feed struct {
	// State is the coordinator's campaign state, for example COLLECTING.
	State string
	// QueueState is green, yellow, red or "" when the coordinator omitted it.
	QueueState    string
	QueueMessages int64
	Collisions    int64
	DPs           int64
	Walkers       int64
	GeneratedAt   time.Time
}

// FeedSource fetches the coordinator status document.
type FeedSource interface {
	Fetch(ctx context.Context, url string) (*Feed, error)
}

// HTTPFeedSource reads status.json over HTTP(S).
type HTTPFeedSource struct {
	Client *http.Client
}

// NewHTTPFeedSource returns a source with a bounded timeout.
func NewHTTPFeedSource(timeout time.Duration) *HTTPFeedSource {
	return &HTTPFeedSource{Client: &http.Client{Timeout: timeout}}
}

type feedDocument struct {
	State       string `json:"state"`
	GeneratedAt string `json:"generated_at"`
	Collisions  int64  `json:"collisions"`
	DPs         int64  `json:"dps"`
	Walkers     int64  `json:"walkers"`
	Queue       struct {
		State    string `json:"state"`
		Messages int64  `json:"messages"`
	} `json:"queue"`
}

// Fetch implements FeedSource.
func (s *HTTPFeedSource) Fetch(ctx context.Context, url string) (*Feed, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Accept", "application/json")
	resp, err := s.Client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("status feed returned HTTP %d", resp.StatusCode)
	}
	body, err := io.ReadAll(io.LimitReader(resp.Body, maxFeedBytes+1))
	if err != nil {
		return nil, err
	}
	if len(body) > maxFeedBytes {
		return nil, errors.New("status feed exceeds 1 MiB")
	}
	return ParseFeed(body)
}

// ParseFeed decodes a status document.
func ParseFeed(body []byte) (*Feed, error) {
	var doc feedDocument
	if err := json.Unmarshal(body, &doc); err != nil {
		return nil, fmt.Errorf("decode status feed: %w", err)
	}
	if doc.GeneratedAt == "" {
		return nil, errors.New("status feed lacks generated_at")
	}
	generated, err := time.Parse(time.RFC3339, doc.GeneratedAt)
	if err != nil {
		return nil, fmt.Errorf("status feed generated_at: %w", err)
	}
	return &Feed{
		State:         doc.State,
		QueueState:    strings.ToLower(doc.Queue.State),
		QueueMessages: doc.Queue.Messages,
		Collisions:    doc.Collisions,
		DPs:           doc.DPs,
		Walkers:       doc.Walkers,
		GeneratedAt:   generated.UTC(),
	}, nil
}
