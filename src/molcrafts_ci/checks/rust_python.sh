#!/usr/bin/env bash
# Canonical Rust/Python gate implementations, invoked only by molci.
set -euo pipefail
cd "$MOLCI_ROOT"
export UV_PYTHON=3.12.12
# Run from a git hook, GIT_DIR, GIT_INDEX_FILE, ... name the hooked
# repository; a gate's own git calls (molci partners fetching molrec, uv
# fetching a git dependency) must not inherit them.
unset $(git rev-parse --local-env-vars)
CLEANUP=()
trap '[ "${#CLEANUP[@]}" -eq 0 ] || rm -rf "${CLEANUP[@]}"' EXIT

# Every standalone workspace root besides the root one: the ABI layer and the
# language bindings.
ROOTS=(crates/molrs-ffi molpy molwasm molc molcxx)
# wasm-opt release that release.yml's npm build runs (.github/actions/setup-wasm
# reads it from here). The wasm gate is `wasm-pack test`, which runs no wasm-opt.
BINARYEN_VERSION=version_133
WASM_PACK_VERSION=0.15.0
TARGET_DIR=${CARGO_TARGET_DIR:-$PWD/target}
# --report <dir>: the test gates also write what they ran into <dir> --
# cargo-test.log (every `cargo test` of test/ffi/cxx; its `test result:`
# lines are the totals), junit.xml and coverage.json (python). Nothing reads
# them here; CI turns them into the run's summary.
REPORT=${MOLCI_REPORT_DIR:-}
if [ -n "$REPORT" ]; then mkdir -p "$REPORT"; REPORT=$(cd "$REPORT" && pwd); fi
# The molpy wheel `types`, `mrec` and `docs` install instead of building their
# own. `python` sets it to the wheel it just built and tested. CI's test.yml
# passes it in the environment to the `mrec` and `docs` jobs: the Linux wheel
# the `test / python (ubuntu-latest)` job of the SAME run built and tested,
# downloaded as an artifact. It must never name any other wheel (a stale local
# build, a PyPI download): these gates would then judge a binary no test ran
# against.
MOLPY_TESTED_WHEEL=${MOLPY_TESTED_WHEEL:-}
# Set by CI's `test / python (ubuntu-latest)`: `python` writes the wheel it
# tests here, kept after exit, so the job can upload that same file.
MOLPY_WHEEL_DIR=${MOLPY_WHEEL_DIR:-}

# `cargo test` that also appends its output to the report log.
cargo_test() {
    if [ -n "$REPORT" ]; then
        cargo "$@" | tee -a "$REPORT/cargo-test.log"
    else
        cargo "$@"
    fi
}

clippy_binder() {
    cargo clippy --locked --manifest-path "$1/Cargo.toml" --all-targets "${@:2}" -- -D warnings
}

# Sets WORK to a fresh temp dir, removed when the script exits.
scratch() {
    WORK=$(mktemp -d "${TMPDIR:-/tmp}/molrs-check.XXXXXX")
    if command -v cygpath >/dev/null; then WORK=$(cygpath -m "$WORK"); fi
    CLEANUP+=("$WORK")
}

gate_fmt() {
    cargo fmt --all --check
    for crate in "${ROOTS[@]}"; do
        cargo fmt --manifest-path "$crate/Cargo.toml" --check
    done
}

# Python lint (ruff.toml): text-mode file I/O names its encoding, so a read
# that passes on Linux cannot fail only on Windows (cp1252).
gate_ruff() {
    local requirement
    requirement=$("$MOLCI_PYTHON" -c 'from molcrafts_ci.checks.versions import load; print(next(d for d in load("molpy/pyproject.toml")["project"]["optional-dependencies"]["dev"] if d.startswith("ruff==")))')
    uvx --from "$requirement" ruff check .
    uvx --from "$requirement" ruff format --check molpy/python molpy/tests
}

# Every partner in .github/partners.env resolves, no path dependency points
# where CI has no checkout, no workflow spells a partner commit of its own;
# every binder manifest carries the workspace version (molci run partners).
gate_partners() {
    "$MOLCI_PYTHON" -m molcrafts_ci.partners check
    "$MOLCI_PYTHON" "$MOLCI_CHECKS_DIR/versions.py"
    uv --directory molpy lock --check
}

# Native clippy of the core and every binder, except molwasm: that one is a
# wasm32 crate, linted only for wasm32.
gate_clippy() {
    cargo --locked mrs-clippy -- -D warnings
    for crate in crates/molrs-ffi molcxx molpy molc; do
        clippy_binder "$crate"
    done
    clippy_binder molwasm --target wasm32-unknown-unknown
}

gate_doc() {
    RUSTDOCFLAGS="-D warnings" cargo --locked mrs-doc
}

# --lib does not run rustdoc examples, so the doctests are their own step.
gate_test() {
    cargo_test --locked mrs-test
    cargo_test --locked mrs-doctest
}

gate_ffi() {
    cargo_test test --locked --manifest-path crates/molrs-ffi/Cargo.toml
}

# The build regenerates molcxx/src/bridge.rs from build.rs's schema; the
# committed copy (what Atomiverse's CMake reads) must be what it regenerates.
gate_cxx() {
    cargo_test test --locked --manifest-path molcxx/Cargo.toml
    git diff --exit-code -- molcxx/src/bridge.rs ||
        { echo "molcxx/src/bridge.rs differs from build.rs's schema: commit the regenerated file" >&2; return 1; }
}

# molpy's locked environment (molpy/uv.lock) with one molpy wheel installed:
# the one `python` built and tested (MOLPY_TESTED_WHEEL), or, run on its own,
# a dev wheel built here. uv never builds molpy through `sync`. Sets
# MOLPY_PYTHON and MOLPY_TESTED_WHEEL.
molpy_env() {
    uv --directory molpy sync --locked --no-install-project --extra dev "$@"
    # Ask the selected environment for its real executable, including .exe.
    MOLPY_PYTHON=$(uv --directory molpy run --no-sync python -c \
        'import sys; print(sys.executable, end="")')
    uv pip check --python "$MOLPY_PYTHON"
    if [ -z "$MOLPY_TESTED_WHEEL" ]; then
        local work
        if [ -n "$MOLPY_WHEEL_DIR" ]; then
            mkdir -p "$MOLPY_WHEEL_DIR"
            work=$(cd "$MOLPY_WHEEL_DIR" && pwd)
            if command -v cygpath >/dev/null; then work=$(cygpath -m "$work"); fi
            rm -f "$work"/molcrafts_molpy-*.whl
        else
            scratch
            work=$WORK
        fi
        uv --directory molpy run --no-sync maturin build --locked \
            --interpreter "$MOLPY_PYTHON" --out "$work"
        MOLPY_TESTED_WHEEL=$(ls "$work"/molcrafts_molpy-*.whl)
    fi
    uv pip install -q --python "$MOLPY_PYTHON" --no-deps --reinstall "$MOLPY_TESTED_WHEEL"
    uv pip check --python "$MOLPY_PYTHON"
}

# Build one non-editable dev-profile molpy wheel (no --release, no LTO), then
# check molpy's format and types and run the whole Python suite on it.
# `pytest`, not `python -m pytest`. The suite imports the installed wheel.
# The package source is python/molpy (maturin python-source). `types`,
# `mrec` and `docs` reuse this wheel.
gate_python() {
    MOLPY_TESTED_WHEEL=
    molpy_env
    uv --directory molpy run --no-sync python -I -c \
        'import molpy, pathlib; p=pathlib.Path(molpy.__file__).resolve(); assert "site-packages" in str(p), p'
    uv --directory molpy run --no-sync ty check python/molpy
    local report=()
    [ -z "$REPORT" ] || report=("--junitxml=$REPORT/junit.xml" --cov=molpy --cov-branch
        "--cov-report=json:$REPORT/coverage.json")
    PYTHONWARNDEFAULTENCODING=1 uv --directory molpy run --no-sync pytest -q -n auto \
        ${report[@]+"${report[@]}"}
}

# The stubs are the Python type contract of the native module:
# python/molpy/_core.pyi and the side stubs of the modules that copy its
# names at import time (python/molpy/core/{keys,schema,constants}.pyi) are
# held to themselves and to the runtime they describe, with
# molpy/pyproject.toml's [tool.mypy] (strict, the source-tree stub first on
# the path). `mypy` type-checks the stub; `mypy.stubtest` imports molpy._core
# and checks every name, signature, parameter kind and default the stub
# declares against the compiled module, and every public runtime name the
# stub misses. stubtest-allowlist.txt holds the structural exemptions only.
#
# stubtest runs from an empty directory, so the runtime it imports is the
# installed wheel. MYPYPATH points mypy at python/, where the source package
# lives; that tree has no _core, or a stale one.
gate_types() {
    molpy_env
    uv --directory molpy run --no-sync python -m mypy python/molpy/_core.pyi \
        python/molpy/core/keys.pyi python/molpy/core/schema.pyi \
        python/molpy/core/constants.pyi
    scratch
    local src=$PWD/molpy
    (cd "$WORK" && MYPYPATH="$src/python" "$MOLPY_PYTHON" -m mypy.stubtest \
        molpy._core molpy.core.keys molpy.core.schema molpy.core.constants \
        --mypy-config-file "$src/pyproject.toml" \
        --allowlist "$src/stubtest-allowlist.txt" --ignore-disjoint-bases)
}

# Profile and target dir are explicit: CMake caches both, and a build-test/
# configured once for release would otherwise keep rebuilding the release lib.
gate_capi() {
    cargo test --locked --manifest-path molc/Cargo.toml
    cmake -S molc/tests/cpp -B molc/build-test \
        -DCARGO_PROFILE=debug -DCARGO_TARGET_DIR="$TARGET_DIR"
    cmake --build molc/build-test --config Debug
    ctest --test-dir molc/build-test --build-config Debug --output-on-failure
}

# `wasm-pack test` compiles the wasm32 crate once and runs the Node suite on
# it. No `wasm-pack build --release`: release.yml builds the npm artifact.
gate_wasm() {
    local have
    have=$(wasm-pack --version | awk '{print $NF}')
    [ "$have" = "$WASM_PACK_VERSION" ] || { echo "wasm-pack must be $WASM_PACK_VERSION (found $have)" >&2; return 1; }
    # Node 24 (the LTS) is the floor; every newer release, up to the latest,
    # must work too.
    have=$(node --version)
    local major=${have#v}
    major=${major%%.*}
    [ "$major" -ge 24 ] 2>/dev/null || { echo "Node >= 24 is required (found $have)" >&2; return 1; }
    (cd molwasm && wasm-pack test --node -- --locked)
}

# molrec's conformance suite through molpy.io.mrec (test.yml's `test / mrec`;
# nightly.yml's conformance snapshot runs the same suite): molrec at the
# commit molci partners resolves (fetched into
# a temp dir, never a sibling's working tree), the tested wheel (or, run on
# its own, the extension built by `maturin develop`) in a fresh venv on CI's
# Python, the conformance executor judging every case. Any case that does not
# pass fails the gate.
gate_mrec() {
    scratch
    local work=$WORK
    "$MOLCI_PYTHON" -m molcrafts_ci.partners fetch MOLREC "$work/molrec"
    molpy_env --group ci
    uv pip check --python "$MOLPY_PYTHON"
    local output=${MOLCI_CONFORMANCE_OUT:-$work/conformance.json}
    mkdir -p "$(dirname "$output")"
    local tracking=()
    [ "${MOLCI_TRACK:-}" != true ] || tracking=(--track)
    "$MOLPY_PYTHON" -I "$MOLCI_CHECKS_DIR/conformance.py" --suite "$work/molrec/tests" --out "$output" ${tracking[@]+"${tracking[@]}"}
}

# The manual (zensical.toml, docs/): every ```python block run against the
# tested molpy wheel (the documentation executor), then the site built
# --strict, its API reference imported from the same wheel.
gate_docs() {
    molpy_env --extra doc
    uv --directory molpy run --no-sync python -I "$MOLCI_CHECKS_DIR/doc_blocks.py"
    # The build runs from molpy/; the theme finds a figure's `$file` data under
    # DOCS_DIR, else under ./docs, which from molpy/ does not exist.
    DOCS_DIR="$PWD/docs" uv --directory molpy run --no-sync zensical build --clean --strict -f ../zensical.toml
}

gate_measure_rust() {
    mkdir -p .ci-out/profraw
    sysroot=$(rustc --print sysroot)
    host=$(rustc -vV | awk '/^host: / { print $2 }')
    llvm=$sysroot/lib/rustlib/$host/bin
    export RUSTFLAGS="-C instrument-coverage"
    export LLVM_PROFILE_FILE="$PWD/.ci-out/profraw/molrs-%p-%m.profraw"
    export CARGO_TERM_COLOR=never
    args=(--locked mrs-test)

    set +e
    cargo "${args[@]}" -- --color=never | tee .ci-out/cargo-test.log
    status=${PIPESTATUS[0]}
    set -e
    [ "$status" -eq 0 ] || exit "$status"

    exe=$(cargo "${args[@]}" --no-run --message-format=json | python3 -c '
    import json, sys
    found = None
    for line in sys.stdin:
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if msg.get("reason") == "compiler-artifact" and msg.get("executable") and (msg.get("profile") or {}).get("test"):
            found = msg["executable"]
    if not found:
        raise SystemExit("no instrumented test executable")
    print(found)
    ')
    "$llvm/llvm-profdata" merge -sparse .ci-out/profraw/*.profraw -o .ci-out/coverage.profdata
    "$llvm/llvm-cov" export -format=lcov -instr-profile=.ci-out/coverage.profdata \
      -ignore-filename-regex='/\.cargo/registry/' -ignore-filename-regex='/rustlib/' \
      "$exe" > .ci-out/lcov.info
}

# Host-compatible release preflights; publication remains in release.yml.
gate_package_crate() {
    cmp LICENSE crates/molrs/LICENSE
    scratch
    cargo package --list --locked --allow-dirty --manifest-path crates/molrs/Cargo.toml > "$WORK/contents"
    grep -x LICENSE "$WORK/contents"
    cargo publish --dry-run --locked --allow-dirty --manifest-path crates/molrs/Cargo.toml
}

gate_package_python() {
    [ -n "$MOLPY_TESTED_WHEEL" ] || { echo 'Run through molci: package-python requires the tested wheel' >&2; return 2; }
    molpy_env
    scratch
    cargo metadata --locked --format-version 1 --manifest-path molpy/Cargo.toml > "$WORK/metadata.json"
    uv --directory molpy run --no-sync maturin sdist --out "$WORK"
    "$MOLCI_PYTHON" "$MOLCI_CHECKS_DIR/package.py" "$MOLPY_TESTED_WHEEL" "$WORK"/*.tar.gz
}

gate_package_wasm() {
    wasm-pack build molwasm --release --target bundler --scope molcrafts --out-name molwasm -- --locked
    (cd molwasm/pkg && npm pack --dry-run)
}

# Private implementation: selection and prerequisites belong to the profile.
gate=${1:?molci must name a gate}
gate=${gate//-/_}
if ! declare -F "gate_$gate" >/dev/null; then
    echo "unknown Rust/Python gate: $gate" >&2
    exit 2
fi
"gate_$gate"
