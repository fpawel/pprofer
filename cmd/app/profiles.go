package main

import (
	"time"

	"github.com/fpawel/pprofer/internal/pprof"
)

type ProfileConfig struct {
	Interval time.Duration
	Seconds  int
}

var profileConfigs = map[string]ProfileConfig{
	pprof.ProfTypeGoroutine: {Interval: time.Second},
	pprof.ProfTypeHeap:      {Interval: 1500 * time.Millisecond},
	pprof.ProfTypeAlloc:     {Interval: 3 * time.Second},
	pprof.ProfTypeThread:    {Interval: 5 * time.Second},
	pprof.ProfTypeProfile:   {Interval: 15 * time.Second, Seconds: 5},
	pprof.ProfTypeBlock:     {Interval: 3 * time.Second},
	pprof.ProfTypeMutex:     {Interval: 3 * time.Second},
}
