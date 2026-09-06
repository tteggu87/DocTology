#!/bin/bash
# Finder-safe paths; no cwd assumptions, installation, or security changes.
HERE="$(cd -- "$(dirname -- "$0")" && pwd)" || exit 1
export PATH="$PATH:/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$HOME/.npm-global/bin"
if [ -n "${WIKI_STUDIO_PYTHON:-}" ]; then
  CANDIDATES=("$WIKI_STUDIO_PYTHON")
else
  CANDIDATES=(python3 /opt/homebrew/bin/python3 /usr/local/bin/python3 python)
fi
for PYTHON in "${CANDIDATES[@]}"; do
  if "$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1; then
    printf '%s\n' 'Starting Wiki Studio. Keep this terminal open; Ctrl+C stops the server.'
    "$PYTHON" "$HERE/wiki_dashboard.py" --open-browser --auto-port "$@"
    RESULT=$?
    if [ "$RESULT" -ne 0 ] && [ -t 0 ]; then
      printf '\nWiki Studio exited with code %s.\n' "$RESULT"
      read -r -p 'Press Enter to close...'
    fi
    exit "$RESULT"
  fi
done
printf '%s\n' 'Python 3.11 or newer was not found.' 'Install Python from https://www.python.org/downloads/ and try again.' 'Or set WIKI_STUDIO_PYTHON to the full path of an existing Python executable.'
if [ -t 0 ]; then read -r -p 'Press Enter to close...'; fi
exit 1
