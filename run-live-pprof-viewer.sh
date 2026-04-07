#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  ./run-live-pprof-viewer.sh <pprof-url> [backend-addr]

Examples:
  ./run-live-pprof-viewer.sh http://localhost:6060
  ./run-live-pprof-viewer.sh http://127.0.0.1:6060 127.0.0.1:8081

Environment overrides:
  GO=go
  PYTHON=python3
  GO_MAIN=...                  # optional, auto-detected if omitted
  UI_MAIN=main.py              # optional
  REQUIREMENTS_FILE=requirements.txt
  BACKEND_START_TIMEOUT=15
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" || $# -lt 1 ]]; then
  usage
  exit 0
fi

PPROF_URL="$1"
BACKEND_ADDR="${2:-127.0.0.1:8080}"

GO="${GO:-go}"
PYTHON="${PYTHON:-python3}"
UI_MAIN="${UI_MAIN:-main.py}"
REQUIREMENTS_FILE="${REQUIREMENTS_FILE:-requirements.txt}"
BACKEND_START_TIMEOUT="${BACKEND_START_TIMEOUT:-15}"

BACKEND_URL="http://${BACKEND_ADDR}"
BACK_PID=""

cleanup() {
  if [[ -n "${BACK_PID}" ]]; then
    echo
    echo "Stopping backend (pid=${BACK_PID})"
    kill "${BACK_PID}" 2>/dev/null || true
    wait "${BACK_PID}" 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "error: '$1' not found" >&2
    exit 1
  fi
}

detect_go_main() {
  if [[ -n "${GO_MAIN:-}" ]]; then
    echo "${GO_MAIN}"
    return 0
  fi

  local main_file
  main_file="$(find . -type f -name 'main.go' \
    -exec grep -l 'github.com/fpawel/pprofer/internal/app' {} + 2>/dev/null | head -n 1 || true)"
  if [[ -n "${main_file}" ]]; then
    dirname "${main_file}"
    return 0
  fi

  main_file="$(find ./cmd -type f -name 'main.go' 2>/dev/null \
    -exec grep -l '^package main$' {} + 2>/dev/null | head -n 1 || true)"
  if [[ -n "${main_file}" ]]; then
    dirname "${main_file}"
    return 0
  fi

  if [[ -f ./main.go ]] && grep -q '^package main$' ./main.go 2>/dev/null; then
    echo "."
    return 0
  fi

  echo "error: could not auto-detect Go backend entrypoint." >&2
  echo "hint: run with GO_MAIN=./path/to/backend, for example:" >&2
  echo "      GO_MAIN=./cmd/pprofer ./run-live-pprof-viewer.sh ${PPROF_URL} ${BACKEND_ADDR}" >&2
  exit 1
}

check_python_deps() {
  local missing
  missing="$("${PYTHON}" - <<'PY'
import importlib.util

modules = {
    "PyQt5": "PyQt5",
    "pyqtgraph": "pyqtgraph",
    "humanize": "humanize",
    "requests": "requests",
}

missing = [pkg for mod, pkg in modules.items() if importlib.util.find_spec(mod) is None]
print(" ".join(missing))
PY
)"

  if [[ -n "${missing}" ]]; then
    echo "error: missing Python packages: ${missing}" >&2
    echo >&2
    if [[ -f "${REQUIREMENTS_FILE}" ]]; then
      echo "install them with:" >&2
      echo "  ${PYTHON} -m pip install -r ${REQUIREMENTS_FILE}" >&2
    else
      echo "install them with:" >&2
      echo "  ${PYTHON} -m pip install ${missing}" >&2
    fi
    echo >&2
    echo "recommended:" >&2
    echo "  ${PYTHON} -m venv .venv" >&2
    echo "  source .venv/bin/activate" >&2
    if [[ -f "${REQUIREMENTS_FILE}" ]]; then
      echo "  python -m pip install -r ${REQUIREMENTS_FILE}" >&2
    else
      echo "  python -m pip install ${missing}" >&2
    fi
    exit 1
  fi
}

require_cmd "${GO}"
require_cmd "${PYTHON}"
require_cmd curl

if [[ ! -f "${UI_MAIN}" ]]; then
  echo "error: UI entrypoint not found: ${UI_MAIN}" >&2
  echo "hint: set UI_MAIN=..." >&2
  exit 1
fi

GO_MAIN="$(detect_go_main)"
check_python_deps

echo "Starting backend:"
echo "  go main    : ${GO_MAIN}"
echo "  listen addr: ${BACKEND_ADDR}"
echo "  pprof url  : ${PPROF_URL}"

"${GO}" run "${GO_MAIN}" "${BACKEND_ADDR}" "${PPROF_URL}" &
BACK_PID=$!

deadline=$((SECONDS + BACKEND_START_TIMEOUT))
until curl -fsS "${BACKEND_URL}/health" >/dev/null 2>&1; do
  if ! kill -0 "${BACK_PID}" 2>/dev/null; then
    echo "error: backend exited before becoming healthy" >&2
    wait "${BACK_PID}" || true
    exit 1
  fi

  if (( SECONDS >= deadline )); then
    echo "error: backend did not become healthy within ${BACKEND_START_TIMEOUT}s" >&2
    exit 1
  fi

  sleep 0.2
done

echo "Backend is healthy: ${BACKEND_URL}/health"
echo "Starting UI:"
echo "  python main: ${UI_MAIN}"
echo "  backend url: ${BACKEND_URL}"

exec "${PYTHON}" "${UI_MAIN}" "${BACKEND_URL}"
