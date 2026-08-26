#!/bin/bash
set -euo pipefail

repo_root=.
database=
limit=
hops=2
mode=literal

usage() {
  echo "usage: scripts/repo_docs_query.sh [--repo-root PATH] [--database PATH] search [--terms] [--limit 1..100] QUERY" >&2
  echo "       scripts/repo_docs_query.sh [--repo-root PATH] [--database PATH] traverse [--hops 1..2] [--limit 1..12] START" >&2
}

while (($#)); do
  case "$1" in
    --repo-root)
      (($# >= 2)) || { usage; exit 2; }
      repo_root=$2
      shift 2
      ;;
    --database)
      (($# >= 2)) || { usage; exit 2; }
      database=$2
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    --*)
      usage
      exit 2
      ;;
    *)
      command=$1
      shift
      break
      ;;
  esac
done

[[ ${command-} == search || ${command-} == traverse ]] || { usage; exit 2; }
while (($# > 1)); do
  case "$1" in
    --limit)
      (($# >= 2)) || { usage; exit 2; }
      limit=$2
      shift 2
      ;;
    --hops)
      (($# >= 2)) || { usage; exit 2; }
      hops=$2
      shift 2
      ;;
    --terms)
      mode=terms
      shift
      ;;
    *)
      usage
      exit 2
      ;;
  esac
done
[[ $# == 1 && $1 ]] || { usage; exit 2; }
value=$1
[[ $value =~ [^[:space:]] ]] || {
  echo "repo docs query error: value must contain a non-whitespace character" >&2
  exit 2
}

if [[ $command == search ]]; then
  limit=${limit:-10}
  [[ $limit =~ ^[0-9]+$ ]] && ((limit >= 1 && limit <= 100)) || {
    echo "repo docs query error: limit must be between 1 and 100" >&2
    exit 2
  }
else
  [[ $mode == literal ]] || { usage; exit 2; }
  limit=${limit:-12}
  [[ $hops =~ ^[0-9]+$ ]] && ((hops >= 1 && hops <= 2)) || {
    echo "repo docs query error: hops must be between 1 and 2" >&2
    exit 2
  }
  [[ $limit =~ ^[0-9]+$ ]] && ((limit >= 1 && limit <= 12)) || {
    echo "repo docs query error: limit must be between 1 and 12" >&2
    exit 2
  }
fi
command -v sqlite3 >/dev/null || {
  echo "repo docs query error: sqlite3 CLI is required" >&2
  exit 2
}

if [[ -z $database ]]; then
  database="$repo_root/state/repo_docs_index.sqlite"
elif [[ $database != /* ]]; then
  database="$repo_root/$database"
fi
[[ -f $database ]] || {
  echo "repo docs query error: derived index is missing; run rebuild" >&2
  exit 2
}
if ! schema_version=$(
  sqlite3 -readonly "$database" \
    "SELECT value FROM index_metadata WHERE key = 'schema_version';"
); then
  echo "repo docs query error: derived index is malformed; run rebuild" >&2
  exit 2
fi
if [[ $schema_version != repo-docs-heading-index-v3 ]]; then
  echo "repo docs query error: derived index schema is incompatible; run rebuild" >&2
  exit 2
fi

escaped=${value//\\/\\\\}
escaped=${escaped//\"/\\\"}
script_dir=${BASH_SOURCE[0]%/*}
[[ $script_dir != "${BASH_SOURCE[0]}" ]] || script_dir=.

if [[ $command == search ]]; then
  sql_file="$script_dir/repo_docs_search.sql"
  parameters=(
    ".parameter set :query \"$escaped\""
    ".parameter set :mode $mode"
    ".parameter set :limit $limit"
  )
else
  sql_file="$script_dir/repo_docs_traverse.sql"
  parameters=(
    ".parameter set :start \"$escaped\""
    ".parameter set :hops $hops"
    ".parameter set :limit $limit"
  )
fi

if ! output=$(sqlite3 -readonly "$database" \
  ".parameter init" \
  "${parameters[@]}" \
  ".read \"$sql_file\""); then
  echo "repo docs query error: native SQLite query failed" >&2
  exit 2
fi
printf '%s\n' "$output"
if [[ $output == *'"error":'* ]]; then
  exit 2
fi
