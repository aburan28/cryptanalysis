// The orchestration layer for libcryptanalysis: a control plane that owns a
// campaign and its work units, and agents that walk them.
//
// No third-party dependencies, on purpose.  This binary runs on every node
// of a fleet and in every pod of a cluster; the standard library is the one
// dependency that is already audited wherever it lands, and a control plane
// whose upgrade path is "go build" is one that actually gets upgraded.
module github.com/aburan28/cryptanalysis/orchestrator

go 1.21
