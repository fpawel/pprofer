package app

import (
	"github.com/fpawel/pprofer/internal/pprof"
)

type (
	StackInfoProvider struct {
		stacks map[FuncLine]Stack
		labels []string

		chIn        chan *pprof.Metrics
		chStackReq  chan stackReq
		chLabelsReq chan labelsReq
	}

	stackReq struct {
		FuncLine
		ch chan Stack
	}
	labelsReq struct {
		ch chan []string
	}
)

func NewStackInfoProvider() *StackInfoProvider {
	h := &StackInfoProvider{
		stacks:      make(map[FuncLine]Stack),
		chIn:        make(chan *pprof.Metrics, 1000),
		chStackReq:  make(chan stackReq, 1000),
		chLabelsReq: make(chan labelsReq, 1000),
	}
	go h.run()
	return h
}

func (h *StackInfoProvider) FuncLineStack(f FuncLine) Stack {
	ch := make(chan Stack)
	h.chStackReq <- stackReq{f, ch}
	return <-ch
}

func (h *StackInfoProvider) Labels() []string {
	ch := make(chan []string)
	h.chLabelsReq <- labelsReq{ch}
	return <-ch
}

func (h *StackInfoProvider) run() {
	for {
		select {
		case req := <-h.chStackReq:
			req.ch <- h.stacks[req.FuncLine]

		case req := <-h.chLabelsReq:
			req.ch <- h.labels

		case metrics := <-h.chIn:
			if len(h.labels) == 0 {
				h.labels = metrics.Labels
			}
			for _, entry := range metrics.Items {
				if entry.Flat == 0 {
					continue
				}
				k := FuncLine{
					Func:   entry.Func,
					Line:   entry.Line,
					Inline: entry.InlineLabel,
				}

				if _, ok := h.stacks[k]; !ok {
					h.stacks[k] = entry.Stack
				}
			}
		}
	}
}

func (h *StackInfoProvider) FeedMetrics(m *pprof.Metrics) {
	h.chIn <- m
}
