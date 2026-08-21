#!/usr/bin/env bash
# Prepare a TinyLanguage development and test environment.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${TINYLANG_VENV:-$ROOT_DIR/.venv}"
INSTALL_SYSTEM=1

usage() {
  cat <<'EOF'
Usage: scripts/bootstrap-dev.sh [--skip-system-packages] [--venv PATH]

Installs Python, Git, a C/LLVM toolchain, creates a virtual environment, and
installs TinyLanguage's Python test dependencies. Supported system package
managers: apt, dnf, pacman, and Homebrew.

Options:
  --skip-system-packages  Do not invoke the operating-system package manager
  --venv PATH            Create/use the virtual environment at PATH
  -h, --help             Show this help

Environment:
  TINYLANG_VENV           Alternative default path for the virtual environment
EOF
}

while (($#)); do
  case "$1" in
    --skip-system-packages) INSTALL_SYSTEM=0; shift ;;
    --venv)
      [[ $# -ge 2 ]] || { echo "error: --venv needs a path" >&2; exit 2; }
      VENV_DIR="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "error: unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

run_as_root() {
  if [[ ${EUID:-$(id -u)} -eq 0 ]]; then
    "$@"
  elif command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  else
    echo "error: root access is required to install system packages (sudo not found)." >&2
    echo "Re-run with --skip-system-packages after installing Python 3 manually." >&2
    exit 1
  fi
}

install_system_packages() {
  if command -v apt-get >/dev/null 2>&1; then
    run_as_root apt-get update
    run_as_root apt-get install -y python3 python3-venv python3-pip git build-essential clang llvm
  elif command -v dnf >/dev/null 2>&1; then
    run_as_root dnf install -y python3 python3-pip git gcc gcc-c++ clang llvm
  elif command -v pacman >/dev/null 2>&1; then
    run_as_root pacman -Syu --needed --noconfirm python python-pip git base-devel clang llvm
  elif command -v brew >/dev/null 2>&1; then
    brew install python git llvm
  else
    echo "error: no supported package manager found (apt, dnf, pacman, or brew)." >&2
    echo "Install Python 3.9+, Git, a C compiler, Clang, and LLVM; then use --skip-system-packages." >&2
    exit 1
  fi
}

if [[ $INSTALL_SYSTEM -eq 1 ]]; then
  install_system_packages
fi

command -v python3 >/dev/null 2>&1 || {
  echo "error: python3 was not found on PATH." >&2
  exit 1
}

python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -r "$ROOT_DIR/requirements-dev.txt"

cat <<EOF

TinyLanguage development environment is ready.

Activate it with:
  source "$VENV_DIR/bin/activate"

Run the test suite with:
  "$VENV_DIR/bin/python" -m pytest
EOF
