package app

import (
	"time"

	"github.com/fpawel/pprofer/internal/pprof"
)

type profConf struct {
	Interval time.Duration
	Seconds  int
}

var profConfs = map[string]profConf{
	pprof.ProfTypeGoroutine: {Interval: time.Second},
	pprof.ProfTypeHeap:      {Interval: 1500 * time.Millisecond},
	pprof.ProfTypeAlloc:     {Interval: 3 * time.Second},
	pprof.ProfTypeThread:    {Interval: 5 * time.Second},
	pprof.ProfTypeProfile:   {Interval: 10 * time.Second, Seconds: 5},
	pprof.ProfTypeBlock:     {Interval: 3 * time.Second},
	pprof.ProfTypeMutex:     {Interval: 3 * time.Second},
}
