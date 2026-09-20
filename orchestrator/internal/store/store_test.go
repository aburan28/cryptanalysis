package store

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// The corpus is the only thing in this system that cannot be recreated
// cheaply, so the properties tested here are the ones that protect it: an
// upload that lands twice must not become two different blobs, and a blob
// must never be silently overwritten by different bytes.
func TestBlobsAreImmutableAndIdempotent(t *testing.T) {
	s, err := Open(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	defer s.Close()

	data := []byte("thirty-two bytes of nothing much")
	key, err := s.PutCorpus("demo", 7, data)
	if err != nil {
		t.Fatal(err)
	}
	// The same unit uploaded again -- a retry after a timeout -- is the same
	// key and the same bytes, so the store is idempotent by construction
	// rather than by a check somewhere.
	again, err := s.PutCorpus("demo", 7, data)
	if err != nil {
		t.Fatal(err)
	}
	if again != key {
		t.Fatalf("a re-upload landed on a different key: %s then %s", key, again)
	}

	got, err := s.GetCorpus(key)
	if err != nil {
		t.Fatal(err)
	}
	if string(got) != string(data) {
		t.Fatal("blob came back different")
	}

	// Different bytes from the same unit get a different key (the hash is in
	// it), so the first upload is never lost.
	other, err := s.PutCorpus("demo", 7, []byte("a different unit's output, also 32"))
	if err != nil {
		t.Fatal(err)
	}
	if other == key {
		t.Fatal("different bytes landed on the same key")
	}
	keys, err := s.CorpusKeys("demo")
	if err != nil {
		t.Fatal(err)
	}
	if len(keys) != 2 {
		t.Fatalf("expected both blobs, got %v", keys)
	}

	// And a key that already holds different bytes is an error rather than
	// an overwrite, for the case where a hash ever does collide.
	if err := s.blobs.Put(key, []byte("something else entirely, 32 bytes")); err == nil {
		t.Fatal("overwriting a blob with different bytes was allowed")
	}
}

func TestCampaignNamesCannotEscapeTheStateDirectory(t *testing.T) {
	dir := t.TempDir()
	s, err := Open(dir)
	if err != nil {
		t.Fatal(err)
	}
	defer s.Close()
	for _, bad := range []string{"../escape", "a/b", "", "."} {
		if err := s.SaveCampaign(bad, map[string]string{"x": "y"}); err == nil {
			t.Fatalf("campaign name %q was accepted", bad)
		}
		if _, err := s.PutCorpus(bad, 0, []byte("x")); err == nil {
			t.Fatalf("corpus for campaign %q was accepted", bad)
		}
	}
}

// A crash mid-write leaves a torn final line.  Refusing to start because of
// it would be worse than re-issuing one unit, so the ledger stops at the
// damage and keeps everything before it.
func TestATornLedgerLineDoesNotStopTheBoot(t *testing.T) {
	dir := t.TempDir()
	s, err := Open(dir)
	if err != nil {
		t.Fatal(err)
	}
	for i := 0; i < 3; i++ {
		if err := s.AppendUnit(UnitRecord{Campaign: "c", Unit: uint64(i), State: "done"}); err != nil {
			t.Fatal(err)
		}
	}
	s.Close()

	f, err := os.OpenFile(filepath.Join(dir, "units.jsonl"), os.O_WRONLY|os.O_APPEND, 0o600)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := f.WriteString(`{"campaign":"c","unit":3,"sta`); err != nil {
		t.Fatal(err)
	}
	f.Close()

	s2, err := Open(dir)
	if err != nil {
		t.Fatal(err)
	}
	defer s2.Close()
	var seen []uint64
	n, err := s2.ReplayUnits(func(r UnitRecord) { seen = append(seen, r.Unit) })
	if err != nil {
		t.Fatal(err)
	}
	if n != 3 || len(seen) != 3 {
		t.Fatalf("expected the three whole records, got %d: %v", n, seen)
	}
}

func TestLedgerSurvivesAReopen(t *testing.T) {
	dir := t.TempDir()
	s, err := Open(dir)
	if err != nil {
		t.Fatal(err)
	}
	if err := s.AppendUnit(UnitRecord{Campaign: "c", Unit: 42, State: "done", Steps: 7}); err != nil {
		t.Fatal(err)
	}
	s.Close()

	s2, err := Open(dir)
	if err != nil {
		t.Fatal(err)
	}
	defer s2.Close()
	if err := s2.AppendUnit(UnitRecord{Campaign: "c", Unit: 43, State: "done"}); err != nil {
		t.Fatal(err)
	}
	var units []uint64
	if _, err := s2.ReplayUnits(func(r UnitRecord) { units = append(units, r.Unit) }); err != nil {
		t.Fatal(err)
	}
	if len(units) != 2 || units[0] != 42 || units[1] != 43 {
		t.Fatalf("reopening the ledger lost or reordered records: %v", units)
	}
}

// A path built from a name is a path built from data, so the key that names
// a blob is checked against the one shape this store writes.  The cases
// below are the ones that matter: a key that climbs out of the store, one
// that is absolute, and one whose campaign part would not be a legal
// campaign name anywhere else in the system.
func TestBlobKeysAreCheckedAgainstTheOneShapeTheStoreWrites(t *testing.T) {
	dir := t.TempDir()
	s, err := Open(dir)
	if err != nil {
		t.Fatal(err)
	}
	defer s.Close()

	key, err := s.PutCorpus("demo", 3, []byte("a unit's worth of points, 32 by"))
	if err != nil {
		t.Fatal(err)
	}
	if !blobKey.MatchString(key) {
		t.Fatalf("the store wrote a key it would refuse to read: %q", key)
	}

	for _, bad := range []string{
		"../escape/00000000000000000003-0011223344556677.bin",
		"/demo/00000000000000000003-0011223344556677.bin",
		"demo/../../etc/passwd",
		"demo/00000000000000000003-0011223344556677.bin/extra",
		"DEMO/00000000000000000003-0011223344556677.bin",
		"demo/not-a-unit.bin",
	} {
		if _, err := s.GetCorpus(bad); err == nil {
			t.Fatalf("reading blob key %q was allowed", bad)
		}
		if err := s.blobs.Put(bad, []byte("x")); err == nil {
			t.Fatalf("writing blob key %q was allowed", bad)
		}
	}

	// Nothing was created outside the corpus directory by any of that.
	if _, err := os.Stat(filepath.Join(dir, "..", "escape")); err == nil {
		t.Fatal("a rejected key still created a directory outside the store")
	}
}

// The store's idea of a campaign name and the API's must not drift: one
// builds paths, the other validates requests, and a name that is legal to
// one and not the other is a campaign that cannot be saved or a path that
// nobody checked.
func TestCampaignNameRuleMatchesTheApi(t *testing.T) {
	for _, ok := range []string{"demo", "ecc2k-130", "c1", "a"} {
		if err := safeName(ok); err != nil {
			t.Fatalf("store refused the legal campaign name %q: %v", ok, err)
		}
	}
	for _, bad := range []string{"", "-lead", "Upper", "with space", "dot.name", "a/b", "..",
		strings.Repeat("x", 64)} {
		if err := safeName(bad); err == nil {
			t.Fatalf("store accepted the illegal campaign name %q", bad)
		}
	}
}
