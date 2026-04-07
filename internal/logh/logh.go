package logh

import (
	"log/slog"

	"github.com/fpawel/slogx/slogpretty"
	slogctx "github.com/veqryn/slog-context"
	sloghttp "github.com/veqryn/slog-context/http"
)

func NewLogHandler(logLevel slog.Level) slog.Handler {
	// Create the *slogctx.Handler middleware
	return slogctx.NewHandler(
		slogpretty.NewPrettyHandler().
			WithSourceInfo(false).
			WithLogLevel(logLevel), // The next or final handler in the chain
		&slogctx.HandlerOptions{
			// Prependers will first add any sloghttp.With attributes,
			// then anything else Prepended to the ctx
			Prependers: []slogctx.AttrExtractor{
				sloghttp.ExtractAttrCollection, // our sloghttp middleware extractor
				slogctx.ExtractPrepended,       // for all other prepended attributes
			},
		},
	)
}
