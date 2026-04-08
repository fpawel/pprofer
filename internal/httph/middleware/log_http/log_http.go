package log_http

import (
	"log/slog"
	"net/http"
	"time"

	"github.com/dustin/go-humanize"
	requestError "github.com/fpawel/pprofer/internal/httph/middleware/request_error"
	slogctx "github.com/veqryn/slog-context"
)

func Middleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		log := slogctx.FromCtx(r.Context())

		args := requestArgs(r)
		log.With(args...).Debug("HTTP START ")

		tmStart := time.Now()

		lrw := &loggingResponseWriter{ResponseWriter: w}
		next.ServeHTTP(lrw, r)

		status := lrw.status
		if status == 0 {
			status = http.StatusOK
		}

		logLevel := slog.LevelDebug
		if status >= 500 {
			logLevel = slog.LevelError
		} else if status >= 400 {
			logLevel = slog.LevelWarn
		}

		args = append(requestArgs(r), "duration", time.Since(tmStart).String())

		if lrw.wroteHeader {
			args = append(args,
				"status", status,
				"response_size", humanize.Bytes(uint64(lrw.size)),
				"wrote_header", true)
		}

		if err := requestError.Error(r.Context()); err != nil {
			args = append(args, "error", err)

			// Если статус не 5xx, но ошибка есть — всё равно поднимем до error.
			if status < 500 {
				logLevel = slog.LevelError
			}
		}

		log.With(args...).Log(r.Context(), logLevel, "HTTP FINISH")
	})
}

func requestArgs(r *http.Request) []any {
	args := []any{
		"method", r.Method,
		"path", r.URL.Path,
	}
	if len(r.URL.Query()) != 0 {
		args = append(args, "query", r.URL.Query())
	}
	return append(args, "header", r.Header)
}

type loggingResponseWriter struct {
	http.ResponseWriter
	status      int
	size        int
	wroteHeader bool
}

func (lrw *loggingResponseWriter) WriteHeader(code int) {
	if lrw.wroteHeader {
		return
	}
	lrw.wroteHeader = true
	lrw.status = code
	lrw.ResponseWriter.WriteHeader(code)
}

func (lrw *loggingResponseWriter) Write(b []byte) (int, error) {
	if !lrw.wroteHeader {
		lrw.WriteHeader(http.StatusOK)
	}

	n, err := lrw.ResponseWriter.Write(b)
	lrw.size += n
	return n, err
}

func (lrw *loggingResponseWriter) Unwrap() http.ResponseWriter {
	return lrw.ResponseWriter
}

func (lrw *loggingResponseWriter) Flush() {
	if f, ok := lrw.ResponseWriter.(http.Flusher); ok {
		f.Flush()
	}
}
