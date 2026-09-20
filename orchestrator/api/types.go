// Package api is the wire contract between agents and the control plane.
//
// Everything an agent needs in order to walk is in the lease it is handed:
// the campaign (which defines the walk function) and the unit (which defines
// the work).  An agent holds no configuration about the cryptanalysis itself
// and can be redeployed, restarted or replaced by a different machine class
// without anybody editing a manifest.
//
// The two rules that shape these types:
//
//   - A campaign's fields are fixed once it exists.  Every agent must
//     iterate the identical walk function or the points cannot merge, so the
//     campaign carries a Fingerprint and the server rejects points computed
//     under a different one instead of quietly storing corpus that will
//     never collide.
//   - Every write an agent makes carries its lease's Fence.  A unit whose
//     lease expired may already be leased to somebody else; a fence that is
//     behind is rejected, which is what keeps a paused-then-resumed agent
//     from reporting into a unit it no longer owns.
package api

import (
	"errors"
	"fmt"
	"regexp"
	"strings"
	"time"
)

// Version is the wire-protocol version.  The agent sends it on every
// request; a server that does not recognise it refuses rather than guessing.
const Version = "v1"

// PointBytes is the size of one distinguished-point record, matching
// CA_DIST_POINT_BYTES in the C library.  Records are a flat array of these
// with no framing: the corpus is append-only and a truncated upload is a
// shorter upload, never a corrupt one.
const PointBytes = 32

// GroupKind selects one of the library's two concrete groups.
type GroupKind string

const (
	GroupZp GroupKind = "zp" // subgroup of (Z/pZ)^*
	GroupEC GroupKind = "ec" // subgroup of E(F_p), short Weierstrass
)

// Group is a cryptanalytic instance: the group, the base and the target.
type Group struct {
	Kind  GroupKind `json:"kind"`
	P     uint64    `json:"p"`
	A     uint64    `json:"a,omitempty"` // curve coefficients (ec only)
	B     uint64    `json:"b,omitempty"`
	Order uint64    `json:"order"` // n, the order of the subgroup being searched
	// Base and Target are in the CLI's element syntax: "123" for Z_p^*,
	// "x,y" for a curve point.  Kept as the library spells them so that a
	// campaign can be copied into a `ca` command line by hand when
	// something needs debugging at three in the morning.
	Base   string `json:"base"`
	Target string `json:"target"`
}

func (g Group) Validate() error {
	switch g.Kind {
	case GroupZp, GroupEC:
	default:
		return fmt.Errorf("group kind %q is not zp or ec", g.Kind)
	}
	if g.P < 5 {
		return errors.New("p must be an odd prime > 3")
	}
	if g.Order < 2 {
		return errors.New("order must be known and at least 2")
	}
	if g.Base == "" || g.Target == "" {
		return errors.New("base and target are required")
	}
	return nil
}

var campaignName = regexp.MustCompile(`^[a-z0-9][a-z0-9-]{0,62}$`)

// agentName is what an agent may call itself.  Agent ids are not cosmetic:
// they are map keys in the registry, they appear in the status output an
// operator reads, they go into log lines, and they are compared against a
// unit's owner to decide who may write to it.  A free-form string in all of
// those places is how a broken agent becomes an unreadable log and a hostile
// one becomes a forged log line, so the shape is fixed here, once, at the
// edge -- a Kubernetes pod name and an EC2 instance id both fit it.
var agentName = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$`)

// ValidateAgentID reports whether an agent may use this id.
func ValidateAgentID(id string) error {
	if !agentName.MatchString(id) {
		return errors.New("agent id must match [A-Za-z0-9][A-Za-z0-9._-]{0,63}")
	}
	return nil
}

// MaxReasonBytes bounds the free text an agent may attach to a failed unit.
const MaxReasonBytes = 512

// CleanText makes a string from an agent safe to store and to log: control
// characters (newlines above all, which is what forges a log line) become
// spaces, and the result is truncated.  It is applied to the one free-text
// field in the protocol; everything else an agent sends is a number or a
// validated identifier.
func CleanText(s string) string {
	if len(s) > MaxReasonBytes {
		s = s[:MaxReasonBytes]
	}
	// The line breaks first and by name: they are what turns one log entry
	// into two, and a reader of this function should not have to work out
	// that the general pass below happens to cover them.
	s = strings.ReplaceAll(s, "\r\n", " ")
	s = strings.ReplaceAll(s, "\n", " ")
	s = strings.ReplaceAll(s, "\r", " ")
	// Then everything else that is not printable: NUL, escape sequences, and
	// the terminal control characters that make a log file lie about what it
	// contains.  Tabs survive because they are only ever cosmetic here.
	return strings.Map(func(r rune) rune {
		if r == '\t' || (r >= 0x20 && r != 0x7f) {
			return r
		}
		return ' '
	}, s)
}

// Campaign is the unit of work distribution: one instance, one walk
// function, one corpus.  Its fields are immutable once created.
type Campaign struct {
	Name  string `json:"name"`
	Group Group  `json:"group"`

	// Seed derives the multipliers and therefore the walk function; it is
	// the single field that must be identical across the fleet and is the
	// reason an agent is never allowed to choose one.
	Seed uint64 `json:"seed"`
	// R is the number of adding-walk multipliers, DPBits the
	// distinguished-point cutoff.  Both are resolved by the control plane
	// when the campaign is created, never by an agent.
	R      uint32 `json:"r"`
	DPBits int32  `json:"dpBits"`

	// UnitSteps is one unit's budget in walk steps, UnitWalks the number of
	// concurrent walks inside a unit (0 lets the library choose).
	UnitSteps uint64 `json:"unitSteps"`
	UnitWalks uint32 `json:"unitWalks"`

	// Fingerprint is a hash of everything above that affects the walk.  An
	// agent echoes it when it reports points and the server compares: two
	// fingerprints that differ are two different searches whose points can
	// never collide, and storing them in one corpus would waste the fleet's
	// time without ever erroring.
	Fingerprint string `json:"fingerprint"`

	CreatedAt time.Time `json:"createdAt"`
}

func (c Campaign) Validate() error {
	if !campaignName.MatchString(c.Name) {
		return errors.New("campaign name must match [a-z0-9][a-z0-9-]{0,62}")
	}
	if err := c.Group.Validate(); err != nil {
		return err
	}
	if c.Seed == 0 {
		return errors.New("campaign seed must not be zero")
	}
	if c.R < 4 || c.R > 1024 {
		return errors.New("r must be between 4 and 1024")
	}
	if c.DPBits < 0 || c.DPBits > 58 {
		return errors.New("dpBits must be between 0 and 58")
	}
	if c.UnitSteps == 0 {
		return errors.New("unitSteps must be set: a unit is a budget")
	}
	return nil
}

// UnitState is where a unit is in its life.
type UnitState string

const (
	UnitPending   UnitState = "pending"   // never leased, or returned to the queue
	UnitLeased    UnitState = "leased"    // an agent holds it
	UnitDone      UnitState = "done"      // an agent reported it finished
	UnitAbandoned UnitState = "abandoned" // failed too many times; kept for the record
)

// Unit is one budget of walk steps, identified by an id that is also the
// seed of its starting points.  A unit is replayable: handing the same id to
// two agents produces the same points, so an expired lease can be re-leased
// without any dedupe protocol beyond the merger's own.
type Unit struct {
	Campaign  string    `json:"campaign"`
	ID        uint64    `json:"id"`
	State     UnitState `json:"state"`
	MaxSteps  uint64    `json:"maxSteps"`
	Walks     uint32    `json:"walks"`
	Attempts  int       `json:"attempts"`
	Points    uint64    `json:"points,omitempty"`
	Steps     uint64    `json:"steps,omitempty"`
	Owner     string    `json:"owner,omitempty"`
	Fence     uint64    `json:"fence"`
	LeaseTill time.Time `json:"leaseTill,omitempty"`
	UpdatedAt time.Time `json:"updatedAt"`
}

// Lease is what an agent is handed: a unit, the campaign that defines how to
// walk it, and the fence that authorises its writes.
type Lease struct {
	Campaign Campaign  `json:"campaign"`
	Unit     Unit      `json:"unit"`
	Fence    uint64    `json:"fence"`
	Expires  time.Time `json:"expires"`
}

// AgentInfo is what an agent says about itself.  None of it is trusted for
// anything that affects correctness; it exists so that an operator can tell
// which pod or instance is behind a number.
type AgentInfo struct {
	ID       string            `json:"id"`
	Hostname string            `json:"hostname,omitempty"`
	Version  string            `json:"version,omitempty"`
	Platform string            `json:"platform,omitempty"`
	CPUs     int               `json:"cpus,omitempty"`
	Labels   map[string]string `json:"labels,omitempty"`
}

// Agent is the registry row for one agent.
type Agent struct {
	AgentInfo
	FirstSeen time.Time `json:"firstSeen"`
	LastSeen  time.Time `json:"lastSeen"`
	Unit      *uint64   `json:"unit,omitempty"`
	Points    uint64    `json:"points"`
	Steps     uint64    `json:"steps"`
	Units     uint64    `json:"units"`
}

// ---- requests and responses ----------------------------------------------

type RegisterRequest struct {
	Info AgentInfo `json:"info"`
}

type RegisterResponse struct {
	AgentID  string        `json:"agentId"`
	Interval time.Duration `json:"heartbeatInterval"`
	Server   string        `json:"server"`
}

type LeaseRequest struct {
	AgentID  string `json:"agentId"`
	Campaign string `json:"campaign,omitempty"` // empty: any campaign with work
}

// LeaseResponse carries a lease, or Empty when the campaign has no work
// right now -- which is a normal state (solved, paused, or every unit in
// flight), not an error.
type LeaseResponse struct {
	Lease *Lease        `json:"lease,omitempty"`
	Empty bool          `json:"empty,omitempty"`
	Retry time.Duration `json:"retryAfter,omitempty"`
}

// PointsResponse reports what the server did with an upload.  Duplicates are
// expected and are not a problem: a replayed unit produces exactly the
// points it produced the first time.
type PointsResponse struct {
	Accepted   uint64 `json:"accepted"`
	Duplicates uint64 `json:"duplicates"`
	Rejected   uint64 `json:"rejected"`
	Stored     uint64 `json:"stored"`
	Solved     bool   `json:"solved"`
	X          uint64 `json:"x,omitempty"`
}

type CompleteRequest struct {
	AgentID string `json:"agentId"`
	Fence   uint64 `json:"fence"`
	Steps   uint64 `json:"steps"`
	Points  uint64 `json:"points"`
	Failed  bool   `json:"failed,omitempty"`
	Reason  string `json:"reason,omitempty"`
}

type HeartbeatRequest struct {
	AgentID string  `json:"agentId"`
	Unit    *uint64 `json:"unit,omitempty"`
	Fence   uint64  `json:"fence,omitempty"`
	Steps   uint64  `json:"steps,omitempty"`
	Points  uint64  `json:"points,omitempty"`
}

// HeartbeatResponse tells the agent whether it still owns what it thinks it
// owns.  Lost is the important one: it means another agent holds the unit,
// and the right response is to stop walking it immediately rather than to
// finish a budget whose output will be rejected.
type HeartbeatResponse struct {
	OK      bool      `json:"ok"`
	Lost    bool      `json:"lost,omitempty"`
	Drain   bool      `json:"drain,omitempty"`
	Expires time.Time `json:"expires,omitempty"`
}

// Status is the one object the CLI, the dashboard and the alarms read.
type Status struct {
	Version   string           `json:"version"`
	Uptime    string           `json:"uptime"`
	Campaigns []CampaignStatus `json:"campaigns"`
	Agents    AgentSummary     `json:"agents"`
}

type CampaignStatus struct {
	Campaign       Campaign   `json:"campaign"`
	Units          UnitCounts `json:"units"`
	Points         uint64     `json:"points"`
	Duplicates     uint64     `json:"duplicates"`
	Rejected       uint64     `json:"rejected"`
	Stored         uint64     `json:"stored"`
	Steps          uint64     `json:"steps"`
	ExpectedPoints float64    `json:"expectedPoints"`
	ExpectedSteps  float64    `json:"expectedSteps"`
	Solved         bool       `json:"solved"`
	X              uint64     `json:"x,omitempty"`
	SolvedAt       *time.Time `json:"solvedAt,omitempty"`
}

type UnitCounts struct {
	Pending   int    `json:"pending"`
	Leased    int    `json:"leased"`
	Done      int    `json:"done"`
	Abandoned int    `json:"abandoned"`
	Next      uint64 `json:"next"`
}

type AgentSummary struct {
	Live  int     `json:"live"`
	Known int     `json:"known"`
	List  []Agent `json:"list,omitempty"`
}

// Error is the body of every non-2xx response.
type Error struct {
	Error  string `json:"error"`
	Detail string `json:"detail,omitempty"`
}
