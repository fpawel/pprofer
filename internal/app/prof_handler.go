package app

import (
	"context"
	"encoding/json"
	"log/slog"
	"sync"
	"time"

	"github.com/fpawel/errorx"
	"github.com/fpawel/pprofer/internal/pprof"
	"github.com/tmaxmax/go-sse"
)

type profHandler struct {
	*sse.Server
	pprof.Client
	profType      string
	cancelFunc    context.CancelFunc
	wg            sync.WaitGroup
	count         int
	log           *slog.Logger
	metricsFeeder interface {
		FeedMetrics(m *pprof.Metrics)
	}
}

func (h *profHandler) shutdown() {
	h.log.Debug("Shutting down...")
	tm := time.Now()
	h.cancelFunc()
	h.wg.Wait()
	h.log.Debug("Shut down successfully", "elapsed", time.Since(tm).String())
}

func (h *profHandler) run(ctx context.Context) {
	h.wg.Add(1)
	h.log.Debug("Start")

	n, tm := 0, time.Now()

	defer func() {
		h.log.Debug("End", "n", n, "elapsed", time.Since(tm).String())
		h.wg.Done()
	}()

	for ; ctx.Err() == nil; n++ {
		if err := h.handle(ctx); err != nil {
			if ctx.Err() != nil {
				return
			}
			h.log.Error("Failed", "err", err.Error())
		}
		sleepCtx(ctx, profConfs[h.profType].Interval)
	}
}

func (h *profHandler) handle(ctx context.Context) error {
	settings := profConfs[h.profType]
	eb := errorx.WithShortFunction()
	metrics, err := h.Client.GetMetrics(ctx, h.profType, settings.Seconds)
	if err != nil {
		return eb.WithFileLine().Wrap(err)
	}

	h.metricsFeeder.FeedMetrics(metrics)

	for _, entry := range metrics.Items {
		if entry.Flat == 0 {
			continue
		}
		fileLineFlat := newFileLineFlat(entry)
		var fileLineFlatJson []byte
		fileLineFlatJson, err = json.Marshal(fileLineFlat)
		if err != nil {
			return eb.WithFileLine().Wrap(err)
		}

		event := &sse.Message{
			Type: sse.Type(h.profType),
		}

		event.AppendData(string(fileLineFlatJson))

		if err = h.Publish(event, h.profType); err != nil {
			return eb.WithFileLine().Wrap(err)
		}
	}

	return nil
}
