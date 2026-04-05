package internal

import (
	"fmt"
	"os"

	"github.com/alexflint/go-arg"
)

type UsagePrinter struct {
	P *arg.Parser
}

func (x UsagePrinter) Usage() {
	x.P.WriteUsage(os.Stderr)
	os.Exit(1)
}

func MustParseArgs(dest ...any) UsagePrinter {
	p, err := arg.NewParser(arg.Config{
		Out:  os.Stderr,
		Exit: os.Exit,
	}, dest...)
	if err != nil {
		_, _ = fmt.Fprintln(os.Stderr, err.Error())
		os.Exit(1)
	}
	var args []string
	if len(os.Args) != 0 {
		args = os.Args[1:]
	}
	p.MustParse(args)
	return UsagePrinter{P: p}
}
