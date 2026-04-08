# live pprof viewer

A lightweight live viewer for Go `pprof`.

It has two parts:

- a Go backend that polls a target application's `pprof` endpoints and exposes:
  - `GET /events` for SSE updates
  - `GET /stack` for stack frames
  - `GET /labels` for report labels
  - `GET /health` for readiness checks
- a PyQt desktop UI that subscribes to the SSE stream and shows live charts for `heap`, `goroutine`, `allocs`, `profile`, `block`, `mutex`, and `threadcreate`.

![img.png](doc/png/img.png)

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

`requirements.txt` contains `PyQt5`, `pyqtgraph`, `humanize`, and `requests`, which are used by the UI code.

## Run manually

Start components in separate terminals.

### 1. Start a target application with `pprof`

For a local demo, run the sample workload from `cmd/dummy` in the first terminal:

```bash
go run ./cmd/dummy
```

The dummy app exposes `pprof` on `http://localhost:6060` and generates CPU, memory, and goroutine activity so the viewer has live data to display. The sample program imports `net/http/pprof`, starts an HTTP server on `localhost:6060`, enables block and mutex profiling, and spawns background workers.

### 2. Start the backend

In the second terminal, start the backend and point it to the target application's `pprof` base URL:

```bash
go run ./cmd/app 127.0.0.1:8080 http://localhost:6060
```

The backend expects two positional arguments:

1. listen address, for example `127.0.0.1:8080`
2. `pprof` base URL, for example `http://localhost:6060`

### 3. Start the UI

In the third terminal, start the desktop UI and pass the backend base URL:

```bash
python main.py http://127.0.0.1:8080
```

If no argument is provided, the UI uses `http://127.0.0.1:8080` by default.

## Notes

- The backend publishes flat values per function/line over SSE.
- Selecting a series in the UI loads and shows its stack trace.
- The default backend URL used by the UI is `http://127.0.0.1:8080`.
