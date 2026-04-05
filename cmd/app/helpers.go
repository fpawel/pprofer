package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	"time"

	"github.com/rs/xid"
)

type (
	handlerFunc func(log *slog.Logger) (any, error)
	errCode     struct {
		code int
		err  error
	}
)

func (err errCode) Error() string {
	if err.err != nil {
		return err.err.Error()
	}
	return ""
}

func wrapErr(code int, err error) error {
	return errCode{code: code, err: err}
}

func handle(w http.ResponseWriter, r *http.Request, h handlerFunc) {
	requestID := r.Header.Get("X-Correlation-ID")
	if requestID == "" {
		requestID = xid.New().String()
	}
	log := slog.With("request-id", requestID)
	log.Debug("REQUEST", "method", r.Method, "path", r.URL.Path, "query", r.URL.RawQuery, "header", r.Header)
	tmStart := time.Now()
	resp, err := h(log)
	if err != nil {
		var errC errCode
		code := http.StatusInternalServerError
		if errors.As(err, &errC) {
			code = errC.code
		}
		s := fmt.Sprintf("%s request-id: %s", err, requestID)
		http.Error(w, s, code)
		log.Error("FAILED", "code", code, "err", err.Error(), "duration", time.Since(tmStart).String())
		return
	}

	w.Header().Set(HeaderContentType, ContentTypeJSON)
	if err = json.NewEncoder(w).Encode(resp); err != nil {
		log.Error("Failed to write response", "err", err.Error())
		return
	}
	log.Debug("RESPONSE", "duration", time.Since(tmStart).String())
}
