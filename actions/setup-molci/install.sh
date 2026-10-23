#!/usr/bin/env bash
# Install molci from this checkout of molcrafts-ci into the venv $1, once, and
# print the venv's bin directory. Used by setup-molci, report and submit, so
# every Action runs the code of the ref the caller named.
set -euo pipefail

venv=$1
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)

bin_dir() {
    for dir in "$venv/bin" "$venv/Scripts"; do
        if [ -x "$dir/molci" ] || [ -x "$dir/molci.exe" ]; then
            echo "$dir"
            return 0
        fi
    done
    return 1
}

if bin_dir >/dev/null; then
    bin_dir
    exit 0
fi

if command -v uv >/dev/null 2>&1; then
    uv venv --quiet --python 3.12 "$venv" >&2
    uv pip install --quiet --python "$venv" -r "$root/requirements-runtime.txt" >&2
    uv pip install --quiet --python "$venv" --no-deps "$root" >&2
else
    base=""
    for candidate in python3 python; do
        if "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 12))' 2>/dev/null; then
            base=$candidate
            break
        fi
    done
    if [ -z "$base" ]; then
        echo "molci needs Python 3.12 or newer on PATH (or uv)" >&2
        exit 1
    fi
    "$base" -m venv "$venv"
    python="$venv/bin/python"
    [ -x "$python" ] || python="$venv/Scripts/python.exe"
    "$python" -m pip install --quiet --disable-pip-version-check -r "$root/requirements-runtime.txt" >&2
    "$python" -m pip install --quiet --disable-pip-version-check --no-deps "$root" >&2
fi
bin_dir
