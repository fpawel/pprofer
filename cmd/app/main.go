package main

import (
	"context"
	"errors"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/fpawel/pprofer/internal"
	"github.com/fpawel/pprofer/internal/app"
	"github.com/fpawel/pprofer/internal/httph"
	httpSimpleJSON "github.com/fpawel/pprofer/internal/httph/middleware/simple_json"
	"github.com/fpawel/pprofer/internal/logh"
)

var exitErr = internal.ExitErr

func main() {
	logHandler := logh.NewLogHandler(slog.LevelDebug)
	slog.SetDefault(slog.New(logHandler))

	var args struct {
		Addr  string `arg:"positional,required" help:"Listen address, for example 127.0.0.1:8080"`
		Pprof string `arg:"positional,required" help:"Pprof URL, for example http://localhost:6060"`
	}
	internal.MustParseArgs(&args)

	slog.Info("Starting HTTP server " + args.Addr)

	mux := http.NewServeMux()

	profsPub := app.NewHandler(args.Pprof)

	mux.Handle("/events", profsPub)
	mux.Handle("/stack", httpSimpleJSON.MustResponse(profsPub.Stacks.Stack))
	mux.Handle("/labels", httpSimpleJSON.MustResponse(profsPub.Stacks.Labels))

	mux.Handle("/health", httpSimpleJSON.Value(map[string]string{
		"status": "healthy",
	}))

	server := &http.Server{
		Addr:              args.Addr,
		Handler:           httph.Wrap(mux),
		ReadHeaderTimeout: time.Second * 10,
		ErrorLog:          slog.NewLogLogger(logHandler, slog.LevelDebug),
	}

	// Graceful shutdown
	setupSignalHandling(server)

	slog.Info("Listening")

	if err := server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		internal.LogErr(err, "Server error")
		os.Exit(1)
	}

	slog.Debug("Server stopped gracefully")
}

func setupSignalHandling(server *http.Server) {
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)

	go func() {
		sig := <-sigChan
		slog.Warn(sig.String())
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		exitErr(server.Shutdown(ctx), "Failed to shutdown gracefully")
	}()
}
