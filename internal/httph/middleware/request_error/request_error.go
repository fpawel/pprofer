package request_error

import (
	"context"
	"errors"
	"net/http"
)

type ctxKey struct{}

type State struct {
	Errors []error
}

func Middleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		st := &State{}
		ctx := context.WithValue(r.Context(), ctxKey{}, st)
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

func FromContext(ctx context.Context) *State {
	st, _ := ctx.Value(ctxKey{}).(*State)
	return st
}

func AddError(ctx context.Context, err error) {
	if err == nil {
		return
	}
	if st := FromContext(ctx); st != nil {
		st.Errors = append(st.Errors, err)
	}
}

func Error(ctx context.Context) error {
	if st := FromContext(ctx); st != nil {
		return errors.Join(st.Errors...)
	}
	return nil
}
