#!/usr/bin/env bash
# Run the TinyCPU electrical acceptance gate with a JAR stored in this checkout.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
jar_name="logisim-evolution-4.1.0-all.jar"

if (($# > 1)); then
  printf 'Usage: %s [path/to/%s]\n' "$0" "$jar_name" >&2
  exit 2
fi

if (($# == 1)); then
  jar="$1"
  [[ "$jar" = /* ]] || jar="$repo_root/$jar"
else
  mapfile -d '' candidates < <(
    find "$repo_root" -path "$repo_root/.git" -prune -o \
      -type f -name "$jar_name" -print0
  )
  case "${#candidates[@]}" in
    0)
      printf 'No %s found below %s.\n' "$jar_name" "$repo_root" >&2
      printf 'Copy the JAR anywhere into the checkout or pass its path explicitly.\n' >&2
      exit 2
      ;;
    1) jar="${candidates[0]}" ;;
    *)
      printf 'Multiple %s files found; pass the desired path explicitly:\n' "$jar_name" >&2
      printf '  %s\n' "${candidates[@]}" >&2
      exit 2
      ;;
  esac
fi

if [[ ! -f "$jar" ]]; then
  printf 'Logisim JAR does not exist: %s\n' "$jar" >&2
  exit 2
fi

export LOGISIM_JAR="$jar"
exec "$repo_root/scripts/test-logisim.sh"
