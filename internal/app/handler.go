package app

import (
	"context"
	"log/slog"
	"net/http"
	"sync"

	"github.com/fpawel/pprofer/internal/httph/status"
	"github.com/fpawel/pprofer/internal/pprof"
	"github.com/rs/xid"
	"github.com/tmaxmax/go-sse"
)

type Handler struct {
	*sse.Server
	pprof.Client
	Stacks *StackInfoProvider

	profs   map[string]*profHandler
	muProfs *sync.Mutex
}

func NewHandler(pprofURL string) Handler {
	return Handler{
		muProfs: &sync.Mutex{},
		profs:   make(map[string]*profHandler),
		Client:  pprof.NewClient(pprofURL),
		Server: &sse.Server{
			Provider: &sse.Joe{},
			OnSession: func(w http.ResponseWriter, r *http.Request) (topics []string, allowed bool) {
				topics = r.URL.Query()["topic"]
				// the shutdown message is sent on the default topic
				return append(topics, sse.DefaultTopic), true
			},
		},
		Stacks: NewStackInfoProvider(),
	}
}

func (p Handler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if err := p.serveHTTP(w, r); err != nil {
		status.WriteError(w, err)
	}
}

func (p Handler) serveHTTP(w http.ResponseWriter, r *http.Request) error {
	topics := r.URL.Query()["topic"]
	if len(topics) == 0 {
		return status.NewErrorCodeMsgFormat(http.StatusBadRequest,
			"you must specify at least one topic from the list %q", pprof.ProfTypes)
	}
	for _, topic := range topics {
		if !pprof.IsValidProfileType(topic) {
			return status.NewErrorCodeMsgFormat(http.StatusBadRequest,
				"invalid profile type %q; supported are %q",
				topic, pprof.ProfTypes)
		}
	}

	p.muProfs.Lock()
	for _, topic := range topics {
		if _, ok := p.profs[topic]; !ok {
			p.startProf(topic)
		}
		p.profs[topic].count++
	}
	p.muProfs.Unlock()

	p.Server.ServeHTTP(w, r)

	p.muProfs.Lock()
	for _, topic := range topics {
		if pp, ok := p.profs[topic]; ok {
			if pp.count--; pp.count == 0 {
				pp.shutdown()
				delete(p.profs, topic)
			}
		}
	}
	p.muProfs.Unlock()
	return nil
}

func (p Handler) startProf(profType string) {
	if _, ok := p.profs[profType]; ok {
		panic("prof already started: " + profType)
	}
	ctx, cancel := context.WithCancel(context.Background())
	pp := &profHandler{
		Server:        p.Server,
		Client:        p.Client,
		profType:      profType,
		cancelFunc:    cancel,
		metricsFeeder: p.Stacks,
		log:           slog.With("prof", profType, "id", xid.New()),
	}
	go pp.run(ctx)
	p.profs[profType] = pp
}
