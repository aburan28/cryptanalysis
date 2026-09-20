package agent

import (
	"context"

	"github.com/aburan28/cryptanalysis/orchestrator/api"
)

// RunUnitForTest exposes the per-unit path to the package's external test,
// which needs to hand it a lease the server would never have produced.
func (a *Agent) RunUnitForTest(ctx context.Context, lease *api.Lease) error {
	return a.runUnit(ctx, lease)
}
