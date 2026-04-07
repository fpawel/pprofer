package requestid

import (
	"context"
	"net/http"

	"github.com/rs/xid"
	slogctx "github.com/veqryn/slog-context"
)

type ctxKey struct{}

// NewContext creates a context with request id
func NewContext(ctx context.Context, rid string) context.Context {
	return context.WithValue(ctx, ctxKey{}, rid)
}

// FromContext returns the request id from context
func FromContext(ctx context.Context) string {
	v := ctx.Value(ctxKey{})
	if v == nil {
		return ""
	}

	rid, ok := v.(string)
	if !ok {
		return ""
	}
	return rid
}

// Handler sets unique request id.
// If header `X-Request-ID` is already present in the request, that is considered the
// request id. Otherwise, generates a new unique ID.
func Handler(h http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		rid := r.Header.Get("X-Request-ID")
		if rid == "" {
			rid = xid.New().String()
			r.Header.Set("X-Request-ID", rid)
		}
		ctx := NewContext(r.Context(), rid)
		ctx = slogctx.With(ctx, "request-id", rid)
		h.ServeHTTP(w, r.WithContext(ctx))
	})
}
