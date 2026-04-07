# live pprof viewer

A lightweight live viewer for Go `pprof`.

It has two parts:

- a Go backend that polls a target application's `pprof` endpoints and exposes:
  - `GET /events` for SSE updates
  - `GET /stack` for stack frames
  - `GET /labels` for report labels
  - `GET /health` for readiness checks
- a PyQt desktop UI that subscribes to the SSE stream and shows live charts for `heap`, `goroutine`, `allocs`, `profile`, `block`, `mutex`, and `threadcreate`. fileciteturn8file1 fileciteturn8file9

## Requirements

- Go
- Python 3
- `pip`

Install UI dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

`requirements.txt` contains `PyQt5`, `pyqtgraph`, `humanize`, and `requests`, which are used by the UI code. fileciteturn3file0 fileciteturn3file1 fileciteturn3file3 fileciteturn3file6

## Quick start

Run the viewer against a target `pprof` endpoint:

```bash
./run-live-pprof-viewer.sh http://localhost:6060
```

Or with an explicit backend listen address:

```bash
./run-live-pprof-viewer.sh http://localhost:6060 127.0.0.1:8081
```

The script starts the Go backend, waits for `/health`, then launches the UI. The backend expects two positional arguments: listen address and `pprof` base URL. The UI accepts the backend base URL as its first argument. fileciteturn8file1 fileciteturn3file0

## Demo workload

For a local demo, run the sample workload from `cmd/dummy` in a separate terminal:

```bash
go run ./cmd/dummy
```

The dummy app exposes `pprof` on `http://localhost:6060` and generates CPU, memory, and goroutine activity so the viewer has live data to display. The sample program imports `net/http/pprof`, starts an HTTP server on `localhost:6060`, enables block and mutex profiling, and spawns background workers. fileciteturn0file3

Then start the viewer:

```bash
./run-live-pprof-viewer.sh http://localhost:6060
```

## Manual run

If you want to start components separately:

```bash
go run ./cmd/app 127.0.0.1:8080 http://localhost:6060
python main.py http://127.0.0.1:8080
```

## Notes

- The backend publishes flat values per function/line over SSE. fileciteturn8file2 fileciteturn8file16
- Selecting a series in the UI loads and shows its stack trace. fileciteturn3file4 fileciteturn8file11
- The default backend URL used by the UI is `http://127.0.0.1:8080`. fileciteturn3file0
