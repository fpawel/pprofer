package app

import "github.com/fpawel/pprofer/internal/pprof"

type (
	FuncLine struct {
		Func   string
		Line   string
		Inline string
	}

	Stack     = []pprof.StackFrame
	profEntry = pprof.ReportEntry

	// FileLineFlat публикуемая по SSE информация об измерении pprof
	FileLineFlat struct {
		Func   string `json:"func"`
		Line   string `json:"line"`
		Inline string `json:"inline,omitempty"`
		Flat   int64  `json:"flat"` // cpu in ns, inuse_space in byte
	}
)

func newFileLineFlat(x profEntry) FileLineFlat {
	return FileLineFlat{
		Func:   x.Func,
		Line:   x.Line,
		Inline: x.InlineLabel,
		Flat:   x.Flat,
	}
}
