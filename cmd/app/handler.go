package main

import (
	"log/slog"
	"net/http"
)

const (
	HeaderContentType = "Content-Type"
	ContentTypeJSON   = "application/json"
)

func handleHealth(w http.ResponseWriter, r *http.Request) {
	handle(w, r, func(log *slog.Logger) (any, error) {
		return map[string]string{
			"status": "healthy",
		}, nil
	})
}
