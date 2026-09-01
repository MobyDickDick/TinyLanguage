#!/usr/bin/env bash
# Run the stable real-simulator gate; opt in to the unfinished ISA matrix.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

java_bin="${JAVA:-java}"
python_bin="${PYTHON:-python3}"
jar="${LOGISIM_JAR:-$HOME/.cache/tinylanguage/logisim-evolution-4.1.0-all.jar}"
output="${LOGISIM_OUTPUT:-artifacts/tinycpu-ap5-trace.tsv}"

if ! command -v "$java_bin" >/dev/null 2>&1; then
  printf 'Java 21 or newer is required (set JAVA to its executable).\n' >&2
  exit 2
fi

gate_args=(--trace-output "$output")
if [[ "${TINYCPU_FULL_ACCEPTANCE:-0}" == "1" ]]; then
  gate_args=(--acceptance-output "$output")
fi

exec env PYTHONPATH="$repo_root/src${PYTHONPATH:+:$PYTHONPATH}" \
  "$python_bin" "$repo_root/src/tiny_cpu_logisim.py" \
  --java "$java_bin" --jar "$jar" "${gate_args[@]}" "$@"
