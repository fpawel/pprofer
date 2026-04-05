package app

import (
	"context"
	"time"
)

func sleepCtx(ctx context.Context, duration time.Duration) {
	t := time.NewTimer(duration)
	defer t.Stop()
	select {
	case <-ctx.Done():
	case <-t.C:
	}
}
