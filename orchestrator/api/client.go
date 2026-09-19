package api

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math/rand"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"
)

// Client is an agent's view of the control plane.
//
// Two behaviours that matter more than the endpoints:
//
//   - **Retries are bounded and jittered.**  A control plane restart, or a
//     rolling update behind a load balancer, makes every agent in the fleet
//     fail at the same instant; an unjittered retry turns that into a
//     thundering herd against a server that is still starting.
//   - **A lost lease is not a retryable error.**  409 means another agent
//     holds the unit, and retrying can only waste the walk that is still
//     running.  ErrLeaseLost is returned so the agent stops immediately.
type Client struct {
	BaseURL string
	Token   string
	HTTP    *http.Client
	// Attempts bounds retries of idempotent calls.  Uploads are idempotent
	// by construction: the corpus is keyed by content, so the same points
	// sent twice are stored once.
	Attempts int
	Sleep    func(time.Duration)
	Rand     *rand.Rand
}

// ErrLeaseLost is returned when the server says the unit has moved on.
var ErrLeaseLost = errors.New("lease lost")

// ErrFingerprint means the agent and the server disagree about the walk.
var ErrFingerprint = errors.New("campaign fingerprint mismatch")

func NewClient(baseURL, token string) *Client {
	return &Client{
		BaseURL: strings.TrimRight(baseURL, "/"),
		Token:   token,
		HTTP: &http.Client{
			Timeout: 60 * time.Second,
			Transport: &http.Transport{
				MaxIdleConnsPerHost: 4,
				IdleConnTimeout:     90 * time.Second,
			},
		},
		Attempts: 5,
		Sleep:    time.Sleep,
		Rand:     rand.New(rand.NewSource(time.Now().UnixNano())),
	}
}

type httpError struct {
	Code   int
	Body   string
	Detail string
}

func (e *httpError) Error() string {
	if e.Detail != "" {
		return fmt.Sprintf("http %d: %s (%s)", e.Code, e.Body, e.Detail)
	}
	return fmt.Sprintf("http %d: %s", e.Code, e.Body)
}

// retryable: a connection problem, or a server that is unavailable or
// overloaded.  A 4xx other than 429 is the agent's own fault and repeating
// it will not help.
func retryable(err error, code int) bool {
	if err != nil {
		return true
	}
	return code == http.StatusTooManyRequests || code >= 500
}

func (c *Client) do(ctx context.Context, method, path string, body []byte, contentType string,
	out any) error {
	var last error
	attempts := c.Attempts
	if attempts < 1 {
		attempts = 1
	}
	for attempt := 0; attempt < attempts; attempt++ {
		req, err := http.NewRequestWithContext(ctx, method, c.BaseURL+path, bytes.NewReader(body))
		if err != nil {
			return err
		}
		if c.Token != "" {
			req.Header.Set("Authorization", "Bearer "+c.Token)
		}
		if contentType != "" {
			req.Header.Set("Content-Type", contentType)
		}
		resp, err := c.HTTP.Do(req)
		code := 0
		if resp != nil {
			code = resp.StatusCode
		}
		if err == nil {
			raw, readErr := io.ReadAll(io.LimitReader(resp.Body, 8<<20))
			resp.Body.Close()
			if readErr != nil {
				err = readErr
			} else {
				switch {
				case code == http.StatusConflict:
					return ErrLeaseLost
				case code == http.StatusPreconditionFailed:
					return ErrFingerprint
				case code >= 200 && code < 300:
					if out == nil || len(raw) == 0 {
						return nil
					}
					return json.Unmarshal(raw, out)
				default:
					var e Error
					_ = json.Unmarshal(raw, &e)
					last = &httpError{Code: code, Body: e.Error, Detail: e.Detail}
				}
			}
		}
		if err != nil {
			last = err
		}
		if !retryable(err, code) {
			return last
		}
		if attempt == attempts-1 {
			break
		}
		// Exponential with full jitter, capped: the cap matters because a
		// fleet that backs off to minutes takes minutes to come back after
		// the server does.
		d := time.Duration(1<<uint(attempt)) * 250 * time.Millisecond
		if d > 8*time.Second {
			d = 8 * time.Second
		}
		c.Sleep(time.Duration(c.Rand.Int63n(int64(d) + 1)))
	}
	return fmt.Errorf("after %d attempts: %w", attempts, last)
}

func (c *Client) Register(ctx context.Context, info AgentInfo) (RegisterResponse, error) {
	body, err := json.Marshal(RegisterRequest{Info: info})
	if err != nil {
		return RegisterResponse{}, err
	}
	var out RegisterResponse
	err = c.do(ctx, http.MethodPost, "/v1/agents/register", body, "application/json", &out)
	return out, err
}

func (c *Client) Heartbeat(ctx context.Context, req HeartbeatRequest) (HeartbeatResponse, error) {
	body, err := json.Marshal(req)
	if err != nil {
		return HeartbeatResponse{}, err
	}
	var out HeartbeatResponse
	err = c.do(ctx, http.MethodPost, "/v1/agents/heartbeat", body, "application/json", &out)
	return out, err
}

func (c *Client) Lease(ctx context.Context, req LeaseRequest) (LeaseResponse, error) {
	body, err := json.Marshal(req)
	if err != nil {
		return LeaseResponse{}, err
	}
	var out LeaseResponse
	err = c.do(ctx, http.MethodPost, "/v1/units/lease", body, "application/json", &out)
	return out, err
}

// SendPoints uploads a raw record array.  Idempotent: the server stores
// corpus blobs by content hash and the merger deduplicates by point, so a
// retry after a timeout costs bytes and nothing else.
func (c *Client) SendPoints(ctx context.Context, campaign, agent, fingerprint string, unit,
	fence uint64, data []byte) (PointsResponse, error) {
	q := url.Values{}
	q.Set("campaign", campaign)
	q.Set("agent", agent)
	q.Set("unit", strconv.FormatUint(unit, 10))
	q.Set("fence", strconv.FormatUint(fence, 10))
	q.Set("fingerprint", fingerprint)
	var out PointsResponse
	err := c.do(ctx, http.MethodPost, "/v1/units/points?"+q.Encode(), data,
		"application/octet-stream", &out)
	return out, err
}

func (c *Client) Complete(ctx context.Context, campaign string, unit uint64,
	req CompleteRequest) error {
	body, err := json.Marshal(req)
	if err != nil {
		return err
	}
	q := url.Values{}
	q.Set("campaign", campaign)
	q.Set("unit", strconv.FormatUint(unit, 10))
	return c.do(ctx, http.MethodPost, "/v1/units/complete?"+q.Encode(), body,
		"application/json", nil)
}

func (c *Client) Status(ctx context.Context, withAgents bool) (Status, error) {
	path := "/v1/status"
	if withAgents {
		path += "?agents=true"
	}
	var out Status
	err := c.do(ctx, http.MethodGet, path, nil, "", &out)
	return out, err
}

func (c *Client) CreateCampaign(ctx context.Context, def Campaign) (Campaign, error) {
	body, err := json.Marshal(def)
	if err != nil {
		return Campaign{}, err
	}
	var out Campaign
	err = c.do(ctx, http.MethodPost, "/v1/campaigns", body, "application/json", &out)
	return out, err
}
