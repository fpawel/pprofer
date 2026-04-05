package pprof

// ReportEntry holds a single text report entry.
type ReportEntry struct {
	Func string `json:"func"`
	Line string `json:"line"`

	// InlineLabel была ли функция встроена inline полностью или частично
	// 	- "" обычная функция
	//	- "inline"	полностью встроена
	//	- "partial-inline"	часть inline, часть нет
	InlineLabel string `json:"inline_label,omitempty"` // Not empty if inlined

	// Flat (self time / self memory)
	// Сколько ресурсов потрачено прямо в этой функции без учёта вызовов других функций.
	Flat int64 `json:"flat"` // cpu in ns, inuse_space in byte

	//Cum (cumulative) Сколько ресурсов потрачено в этой функции + во всех её дочерних вызовах
	Cum int64 `json:"cum"` // Raw values

	Stack []StackFrame `json:"stack,omitempty"`
}

func (rpt *Report) GetEntries() ([]ReportEntry, []string) {
	g, origCount, droppedNodes, _ := rpt.newTrimmedGraph()
	rpt.selectOutputUnit(g)
	labels := reportLabels(rpt, graphTotal(g), len(g.Nodes), origCount, droppedNodes, 0, false)

	var items []ReportEntry
	var flatSum int64
	for _, n := range g.Nodes {
		flat := n.FlatValue()

		flatSum += flat
		items = append(items, ReportEntry{
			Func:        n.Info.Func(),
			Line:        n.Info.Line(),
			InlineLabel: inlineLabel(n),
			Flat:        flat,
			Cum:         n.CumValue(),
			Stack:       n.Stack,
		})
	}
	return items, labels
}

func inlineLabel(n *Node) string {
	var inline, noinline bool
	for _, e := range n.In {
		if e.Inline {
			inline = true
		} else {
			noinline = true
		}
	}

	var inl string
	if inline {
		if noinline {
			inl = "(partial-inline)"
		} else {
			inl = "(inline)"
		}
	}
	return inl
}
