package httph

import (
	"bytes"
	"encoding/json"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"regexp"
	"testing"

	"github.com/fpawel/pprofer/internal/httph/status"
	"github.com/stretchr/testify/require"

	"github.com/fpawel/pprofer/internal/httph/middleware/simple_json"
)

func TestHealthLogging(t *testing.T) {
	var buf bytes.Buffer

	logger := slog.New(slog.NewTextHandler(&buf, &slog.HandlerOptions{
		Level: slog.LevelDebug,
	}))
	prev := slog.Default()
	slog.SetDefault(logger)
	t.Cleanup(func() {
		slog.SetDefault(prev)
	})

	mux := http.NewServeMux()
	mux.Handle("/health", simple_json.Response(func(*http.Request) (any, error) {
		return map[string]string{"status": "healthy"}, nil
	}))

	handler := Wrap(mux)

	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	rec := httptest.NewRecorder()

	handler.ServeHTTP(rec, req)

	resp := rec.Result()
	defer resp.Body.Close()

	require.Equal(t, http.StatusOK, resp.StatusCode)
	require.Equal(t, "application/json", resp.Header.Get("Content-Type"))

	var body map[string]string
	require.NoError(t, json.NewDecoder(resp.Body).Decode(&body))
	require.Equal(t, "healthy", body["status"])

	logOutput := buf.String()

	t.Log(logOutput)

	require.Contains(t, logOutput, `level=DEBUG msg="HTTP start"`)
	require.Contains(t, logOutput, `method=GET`)
	require.Contains(t, logOutput, `path=/health`)
	require.Contains(t, logOutput, `query=""`)

	require.Contains(t, logOutput, `level=DEBUG msg="HTTP finish"`)
	require.Contains(t, logOutput, `status=200`)
	require.Contains(t, logOutput, `wrote_header=true`)
	require.Contains(t, logOutput, `request-id=`)

	require.Regexp(t, regexp.MustCompile(`response_size=\d+`), logOutput)
	require.Regexp(t, regexp.MustCompile(`duration=\S+`), logOutput)
	require.Regexp(t, regexp.MustCompile(`X-Request-Id:\[[^\]]+\]`), logOutput)
}

func TestHealthLogging_Error(t *testing.T) {
	var buf bytes.Buffer

	logger := slog.New(slog.NewTextHandler(&buf, &slog.HandlerOptions{
		Level: slog.LevelDebug,
		ReplaceAttr: func(groups []string, a slog.Attr) slog.Attr {
			if a.Key == slog.TimeKey {
				return slog.Attr{}
			}
			return a
		},
	}))
	prev := slog.Default()
	slog.SetDefault(logger)
	t.Cleanup(func() {
		slog.SetDefault(prev)
	})

	mux := http.NewServeMux()
	mux.Handle("/health", simple_json.Response(func(*http.Request) (any, error) {
		return nil, status.NewErrorCodeMsg(http.StatusBadRequest, "boom")
	}))

	handler := Wrap(mux)

	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	rec := httptest.NewRecorder()

	handler.ServeHTTP(rec, req)

	logOutput := buf.String()

	t.Log(logOutput)

	require.Contains(t, logOutput, `level=ERROR msg="HTTP finish"`)
	require.Contains(t, logOutput, `error=boom`)
	require.Contains(t, logOutput, `duration=`)
	require.Contains(t, logOutput, `request-id=`)
}

func TestHTTPH_Health_OK(t *testing.T) {
	var buf bytes.Buffer

	logger := slog.New(slog.NewTextHandler(&buf, &slog.HandlerOptions{
		Level: slog.LevelDebug,
		ReplaceAttr: func(_ []string, a slog.Attr) slog.Attr {
			if a.Key == slog.TimeKey {
				return slog.Attr{}
			}
			return a
		},
	}))
	prev := slog.Default()
	slog.SetDefault(logger)
	t.Cleanup(func() {
		slog.SetDefault(prev)
	})

	mux := http.NewServeMux()
	mux.Handle("/health", simple_json.Response(func(*http.Request) (any, error) {
		return map[string]string{"status": "healthy"}, nil
	}))

	handler := Wrap(mux)

	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	rec := httptest.NewRecorder()

	handler.ServeHTTP(rec, req)

	resp := rec.Result()
	defer resp.Body.Close()

	require.Equal(t, http.StatusOK, resp.StatusCode)
	require.Equal(t, "application/json", resp.Header.Get("Content-Type"))

	var body map[string]string
	require.NoError(t, json.NewDecoder(resp.Body).Decode(&body))
	require.Equal(t, "healthy", body["status"])

	logOutput := buf.String()
	require.Contains(t, logOutput, `level=DEBUG msg="HTTP start"`)
	require.Contains(t, logOutput, `method=GET`)
	require.Contains(t, logOutput, `path=/health`)
	require.Contains(t, logOutput, `level=DEBUG msg="HTTP finish"`)
	require.Contains(t, logOutput, `status=200`)
	require.Contains(t, logOutput, `wrote_header=true`)
	require.Regexp(t, regexp.MustCompile(`response_size=\d+`), logOutput)
	require.Regexp(t, regexp.MustCompile(`duration=\S+`), logOutput)
	require.Regexp(t, regexp.MustCompile(`X-Request-Id:\[[^\]]+\]`), logOutput)
}

func TestHTTPH_Health_ErrorStatus(t *testing.T) {
	var buf bytes.Buffer

	logger := slog.New(slog.NewTextHandler(&buf, &slog.HandlerOptions{
		Level: slog.LevelDebug,
		ReplaceAttr: func(_ []string, a slog.Attr) slog.Attr {
			if a.Key == slog.TimeKey {
				return slog.Attr{}
			}
			return a
		},
	}))
	prev := slog.Default()
	slog.SetDefault(logger)
	t.Cleanup(func() {
		slog.SetDefault(prev)
	})

	mux := http.NewServeMux()
	mux.Handle("/health", simple_json.Response(func(*http.Request) (any, error) {
		return nil, status.NewErrorCodeMsg(http.StatusBadRequest, "bad request")
	}))

	handler := Wrap(mux)

	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	rec := httptest.NewRecorder()

	handler.ServeHTTP(rec, req)

	resp := rec.Result()
	defer resp.Body.Close()

	require.Equal(t, http.StatusBadRequest, resp.StatusCode)
	require.Equal(t, "bad request\n", rec.Body.String())
	require.Equal(t, "text/plain; charset=utf-8", resp.Header.Get("Content-Type"))

	logOutput := buf.String()
	require.Contains(t, logOutput, `level=DEBUG msg="HTTP start"`)
	require.Contains(t, logOutput, `method=GET`)
	require.Contains(t, logOutput, `path=/health`)
	require.Contains(t, logOutput, `level=ERROR msg="HTTP finish"`)
	require.Contains(t, logOutput, `status=400`)
	require.Contains(t, logOutput, `wrote_header=true`)
	require.Contains(t, logOutput, `error="bad request"`)
}
