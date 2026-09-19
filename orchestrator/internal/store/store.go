// Package store is the control plane's durability: what has to survive a
// restart, and nothing else.
//
// Three kinds of state, with three different answers:
//
//   - **The corpus is the only irreplaceable thing.**  Points cost walk
//     steps, which cost machine time; everything else the control plane
//     knows can be recomputed or re-reported in seconds.  So corpus blobs
//     are written to disk first, as immutable content-addressed files, and
//     nothing is acknowledged to an agent before its bytes are fsynced.
//   - **The unit ledger is worth keeping and cheap to keep.**  It is an
//     append-only JSON-lines file replayed at boot.  Losing it would not
//     lose any points -- the corpus files are still there -- but it would
//     re-issue units that were already walked, which wastes the fleet's
//     time.
//   - **The agent registry is not worth persisting at all.**  Agents
//     re-register within a heartbeat, and a registry restored from disk
//     would be a list of pods that no longer exist.
//
// A `Dir` is a plain directory, so it works the same on an EC2 instance's
// EBS volume and on a Kubernetes PersistentVolumeClaim, and an operator can
// tar it.  Blob storage is behind an interface so that an S3 or object-store
// backend can be added without the control plane knowing.
package store

import (
	"bufio"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"sync"
)

// campaignNamePattern mirrors api's campaign-name rule; the two are checked
// against each other in the tests.
var campaignNamePattern = regexp.MustCompile(`^[a-z0-9][a-z0-9-]{0,62}$`)

// Blobs is where corpus files live.  The control plane only ever appends
// immutable, content-addressed objects, which is what makes an object store
// a drop-in alternative to a filesystem.
type Blobs interface {
	// Put writes bytes under a key.  Writing identical bytes to an existing
	// key is success (that is what a retried upload looks like); different
	// bytes under an existing key is an error, never an overwrite.
	Put(key string, data []byte) error
	Get(key string) ([]byte, error)
	List(prefix string) ([]string, error)
}

// Store is one control plane's durable state directory.
type Store struct {
	dir string

	mu     sync.Mutex
	ledger *os.File
	blobs  Blobs
}

// Open prepares a state directory, creating it if necessary.
func Open(dir string) (*Store, error) {
	for _, sub := range []string{"", "campaigns", "corpus"} {
		if err := os.MkdirAll(filepath.Join(dir, sub), 0o750); err != nil {
			return nil, fmt.Errorf("creating %s: %w", dir, err)
		}
	}
	f, err := os.OpenFile(filepath.Join(dir, "units.jsonl"), os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0o640)
	if err != nil {
		return nil, fmt.Errorf("opening the unit ledger: %w", err)
	}
	return &Store{dir: dir, ledger: f, blobs: &fsBlobs{root: filepath.Join(dir, "corpus")}}, nil
}

// Dir is the state directory, for the status output and for operators.
func (s *Store) Dir() string { return s.dir }

// SetBlobs replaces the blob backend (an object store, in a deployment that
// has one).  Call before serving.
func (s *Store) SetBlobs(b Blobs) { s.blobs = b }

func (s *Store) Close() error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.ledger == nil {
		return nil
	}
	err := s.ledger.Close()
	s.ledger = nil
	return err
}

// ---- campaigns ------------------------------------------------------------

// SaveCampaign writes a campaign definition atomically.  Campaigns are
// immutable once created, so this is write-once in practice; it is still an
// atomic replace, because a half-written campaign file at boot would be a
// control plane that cannot start.
func (s *Store) SaveCampaign(name string, v any) error {
	if err := safeName(name); err != nil {
		return err
	}
	// safeName has already rejected separators and dots, so the join below
	// cannot leave the campaigns directory; stating it with IsLocal keeps
	// that true if safeName is ever loosened.
	if !filepath.IsLocal(name + ".json") {
		return fmt.Errorf("unsafe campaign name %q", name)
	}
	blob, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		return err
	}
	return writeFileAtomic(filepath.Join(s.dir, "campaigns", name+".json"), append(blob, '\n'))
}

// LoadCampaigns decodes every campaign file through fn.
func (s *Store) LoadCampaigns(fn func(name string, raw []byte) error) error {
	entries, err := os.ReadDir(filepath.Join(s.dir, "campaigns"))
	if err != nil {
		return err
	}
	names := make([]string, 0, len(entries))
	for _, e := range entries {
		if !e.IsDir() && strings.HasSuffix(e.Name(), ".json") {
			names = append(names, e.Name())
		}
	}
	sort.Strings(names)
	for _, n := range names {
		raw, err := os.ReadFile(filepath.Join(s.dir, "campaigns", n))
		if err != nil {
			return err
		}
		if err := fn(strings.TrimSuffix(n, ".json"), raw); err != nil {
			return fmt.Errorf("campaign %s: %w", n, err)
		}
	}
	return nil
}

// ---- the unit ledger ------------------------------------------------------

// UnitRecord is one line of the ledger: a unit that reached a terminal state.
type UnitRecord struct {
	Campaign string `json:"campaign"`
	Unit     uint64 `json:"unit"`
	State    string `json:"state"`
	Steps    uint64 `json:"steps"`
	Points   uint64 `json:"points"`
	Attempts int    `json:"attempts"`
	Fence    uint64 `json:"fence"`
	At       int64  `json:"at"`
}

// AppendUnit records a unit's terminal state.  Synced before returning: the
// ledger's whole job is to be true after a crash, and a buffered ledger is
// one that is true only after a clean shutdown.
func (s *Store) AppendUnit(r UnitRecord) error {
	blob, err := json.Marshal(r)
	if err != nil {
		return err
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.ledger == nil {
		return errors.New("store is closed")
	}
	if _, err := s.ledger.Write(append(blob, '\n')); err != nil {
		return err
	}
	return s.ledger.Sync()
}

// ReplayUnits reads the ledger back.  A truncated final line -- the shape a
// crash mid-write leaves -- is dropped with everything after it rather than
// failing the boot: a control plane that will not start because of one torn
// line is a worse outcome than re-issuing one unit.
func (s *Store) ReplayUnits(fn func(UnitRecord)) (int, error) {
	f, err := os.Open(filepath.Join(s.dir, "units.jsonl"))
	if err != nil {
		if os.IsNotExist(err) {
			return 0, nil
		}
		return 0, err
	}
	defer f.Close()
	sc := bufio.NewScanner(f)
	sc.Buffer(make([]byte, 0, 64*1024), 1024*1024)
	n := 0
	for sc.Scan() {
		line := sc.Bytes()
		if len(line) == 0 {
			continue
		}
		var r UnitRecord
		if err := json.Unmarshal(line, &r); err != nil {
			// Stop at the first unreadable line; everything after it is
			// suspect too.
			break
		}
		fn(r)
		n++
	}
	if err := sc.Err(); err != nil && !errors.Is(err, io.EOF) {
		return n, err
	}
	return n, nil
}

// ---- the corpus -----------------------------------------------------------

// PutCorpus stores one unit's points and returns the key it was stored
// under.  The key carries the content hash, so a re-uploaded unit lands on
// the same key with the same bytes and the store is idempotent by
// construction rather than by a check.
func (s *Store) PutCorpus(campaign string, unit uint64, data []byte) (string, error) {
	if err := safeName(campaign); err != nil {
		return "", err
	}
	sum := sha256.Sum256(data)
	key := fmt.Sprintf("%s/%020d-%s.bin", campaign, unit, hex.EncodeToString(sum[:8]))
	if err := s.blobs.Put(key, data); err != nil {
		return "", err
	}
	return key, nil
}

// CorpusKeys lists a campaign's blobs, oldest unit first.
func (s *Store) CorpusKeys(campaign string) ([]string, error) {
	if err := safeName(campaign); err != nil {
		return nil, err
	}
	keys, err := s.blobs.List(campaign + "/")
	if err != nil {
		return nil, err
	}
	sort.Strings(keys)
	return keys, nil
}

// GetCorpus reads one blob back.
func (s *Store) GetCorpus(key string) ([]byte, error) { return s.blobs.Get(key) }

// ---- filesystem blobs -----------------------------------------------------

type fsBlobs struct {
	root string
	mu   sync.Mutex
}

// blobKey is the only shape a corpus key may have: a campaign name, a
// zero-padded unit number and a content hash.  Every key this package writes
// is built by PutCorpus from values it validated, so the pattern is not a
// second line of defence against the caller -- it is the line of defence
// against a key that came back from somewhere else (a listing of a directory
// somebody edited, a future object-store backend, a request parameter that
// reached further than it should).  A path is derived from a name, and a
// name is data.
var blobKey = regexp.MustCompile(`^[a-z0-9][a-z0-9-]{0,62}/[0-9]{20}-[0-9a-f]{16}\.bin$`)

func (b *fsBlobs) path(key string) (string, error) {
	if !blobKey.MatchString(key) {
		return "", fmt.Errorf("bad blob key %q", key)
	}
	// Belt and braces: the pattern above already excludes "..", a leading
	// slash and anything but one separator, and filepath.IsLocal states the
	// property the pattern is there to guarantee.
	if !filepath.IsLocal(key) {
		return "", fmt.Errorf("blob key %q escapes the store", key)
	}
	return filepath.Join(b.root, filepath.FromSlash(key)), nil
}

func (b *fsBlobs) Put(key string, data []byte) error {
	p, err := b.path(key)
	if err != nil {
		return err
	}
	b.mu.Lock()
	defer b.mu.Unlock()
	if err := os.MkdirAll(filepath.Dir(p), 0o750); err != nil {
		return err
	}
	if existing, err := os.ReadFile(p); err == nil {
		if string(existing) == string(data) {
			return nil // the same upload again
		}
		return fmt.Errorf("blob %s already holds different bytes", key)
	}
	return writeFileAtomic(p, data)
}

func (b *fsBlobs) Get(key string) ([]byte, error) {
	p, err := b.path(key)
	if err != nil {
		return nil, err
	}
	return os.ReadFile(p)
}

// List walks the store and returns the keys under a prefix.  It reads the
// directory rather than trusting the prefix as a path: the prefix is only
// ever compared against keys that were found on disk, so a caller cannot use
// it to reach anywhere.
func (b *fsBlobs) List(prefix string) ([]string, error) {
	var out []string
	root := b.root
	err := filepath.WalkDir(root, func(p string, d os.DirEntry, err error) error {
		if err != nil {
			if os.IsNotExist(err) {
				return nil
			}
			return err
		}
		if d.IsDir() {
			return nil
		}
		rel, err := filepath.Rel(root, p)
		if err != nil {
			return err
		}
		rel = filepath.ToSlash(rel)
		if strings.HasPrefix(rel, prefix) {
			out = append(out, rel)
		}
		return nil
	})
	if err != nil && !os.IsNotExist(err) {
		return nil, err
	}
	return out, nil
}

// ---- helpers --------------------------------------------------------------

// writeFileAtomic writes and fsyncs a temporary file, then renames it, then
// fsyncs the directory.  Without the directory sync the rename itself can be
// lost on a power failure, which is the failure this function exists for.
func writeFileAtomic(path string, data []byte) error {
	dir := filepath.Dir(path)
	tmp, err := os.CreateTemp(dir, ".tmp-*")
	if err != nil {
		return err
	}
	name := tmp.Name()
	defer os.Remove(name)
	if _, err := tmp.Write(data); err != nil {
		tmp.Close()
		return err
	}
	if err := tmp.Sync(); err != nil {
		tmp.Close()
		return err
	}
	if err := tmp.Close(); err != nil {
		return err
	}
	if err := os.Chmod(name, 0o640); err != nil {
		return err
	}
	if err := os.Rename(name, path); err != nil {
		return err
	}
	d, err := os.Open(dir)
	if err != nil {
		return err
	}
	defer d.Close()
	return d.Sync()
}

// safeName is the campaign-name gate for every path this store builds.  It
// matches api.Campaign's own rule rather than merely excluding separators,
// because a name that reaches a filesystem should be a name the rest of the
// system would also accept.
func safeName(name string) error {
	if !campaignNamePattern.MatchString(name) {
		return fmt.Errorf("unsafe name %q", name)
	}
	return nil
}
