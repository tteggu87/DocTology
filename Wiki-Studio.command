#!/bin/bash
# Repository convenience entry; DocTology runtime owns startup.
HERE="$(cd -- "$(dirname -- "$0")" && pwd)" || exit 1
LAUNCHER="$HERE/runtime/start_dashboard.command"
if [ ! -f "$LAUNCHER" ]; then
  printf '%s\n' 'Wiki Studio launcher is missing. Keep the complete DocTology folder together.'
  if [ -t 0 ]; then read -r -p 'Press Enter to close...'; fi
  exit 1
fi
exec /bin/bash "$LAUNCHER" "$@"
