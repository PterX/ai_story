#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
failed=0

for app_name in agent mcp workflows; do
  app_dir="$repo_root/backend/apps/$app_name"
  [ -d "$app_dir" ] || continue

  leaked_files="$(find "$app_dir" \
    -type f \
    ! -name '*.so' \
    ! -name '__init__.py' \
    ! -name 'apps.py' \
    ! -name '.gitkeep' \
    ! -path '*/migrations/*.py' \
    ! -path '*/__pycache__/*' \
    -print)"

  if [ -n "$leaked_files" ]; then
    echo "Closed-source app leak detected in $app_dir:" >&2
    echo "$leaked_files" >&2
    failed=1
  fi
done

if [ "$failed" -ne 0 ]; then
  echo "Only compiled .so files and Django package/migration files may remain in closed-source apps." >&2
  exit 1
fi

echo "Closed-source app layout check passed."
