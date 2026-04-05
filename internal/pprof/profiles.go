package pprof

const (
	ProfTypeHeap      = "heap"
	ProfTypeGoroutine = "goroutine"
	ProfTypeAlloc     = "allocs"
	ProfTypeProfile   = "profile"
	ProfTypeBlock     = "block"
	ProfTypeMutex     = "mutex"
	ProfTypeThread    = "threadcreate"
	ProfTypeTrace     = "trace"
)

var (
	ProfTypes = []string{
		ProfTypeHeap, ProfTypeGoroutine, ProfTypeAlloc, ProfTypeProfile,
		ProfTypeBlock, ProfTypeMutex, ProfTypeThread,
	}
	profTypesMap = make(map[string]bool, len(ProfTypes))
)

func IsValidProfileType(profType string) bool {
	return profTypesMap[profType]
}

func init() {
	for _, profType := range ProfTypes {
		profTypesMap[profType] = true
	}
}
