"""Schema-2 gate graph and local successful-result receipts.

Receipts are a developer optimisation, never a remote attestation. GitHub
always executes its selected gates with cache reuse disabled.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

import yaml

from molcrafts_ci.jsonutil import dumps_deterministic
from molcrafts_ci.workspace import clean_git_env


def implementation() -> Path:
    source = Path(__file__).resolve().parents[2]
    return source if (source / "profiles").is_dir() else Path(__file__).parent / "assets"


def pins(root: Path) -> dict[str, str]:
    path = root / ".github/partners.env"
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.lstrip().startswith("#"):
            key, sep, value = line.partition("=")
            if not sep or key in result:
                raise ValueError(f"{path}: invalid or duplicate pin: {line!r}")
            result[key] = value.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", result.get("CI_REF", "")):
        raise ValueError(f"{path}: CI_REF must be an immutable full lowercase commit SHA")
    return result


def profile(root: Path) -> dict:
    name = pins(root).get("CI_PROFILE", "")
    if not re.fullmatch(r"[a-z0-9-]+", name):
        raise ValueError("invalid CI_PROFILE")
    data = yaml.safe_load((implementation() / "profiles" / f"{name}.yml").read_text("utf-8"))
    if data.get("schema") != 2:
        raise ValueError(f"{name}: this command requires schema 2")
    gates = data["gates"]
    registry = {g["id"]: g for g in gates}
    if len(registry) != len(gates) or not gates:
        raise ValueError("gate IDs must be unique and nonempty")
    ordered, active = [], set()

    def visit(name: str) -> None:
        if name not in registry:
            raise ValueError(f"unknown gate dependency: {name}")
        if name in active:
            raise ValueError(f"circular gate dependency: {name}")
        gate = registry[name]
        if gate in ordered:
            return
        if gate.get("stage") not in ("pre-commit", "pre-push", "measurement") or not gate.get(
            "run"
        ):
            raise ValueError(f"{name}: stage and canonical run command are required")
        active.add(name)
        for dep in gate.get("depends_on", []):
            visit(dep)
        active.remove(name)
        ordered.append(gate)

    for name in registry:
        visit(name)
    data["gates"] = ordered
    return data


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        env=clean_git_env(),
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip("\n")


@contextmanager
def exclusive(path: Path):
    """OS locks release on interruption; the same lock protects wheel/venv writes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        if os.name == "nt":
            import msvcrt

            stream.write(b"\0")
            stream.flush()
            stream.seek(0)
            while True:
                try:
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    time.sleep(0.1)
        else:
            import fcntl

            fcntl.flock(stream, fcntl.LOCK_EX)
        yield


def digest(value) -> str:
    return hashlib.sha256(dumps_deterministic(value).encode()).hexdigest()


def execute_command(command: list[str], root: Path, env: dict, stream) -> int:
    """Keep the artifact lock until interrupted child processes have terminated."""
    child = subprocess.Popen(
        command,
        cwd=root,
        env=env,
        stdout=stream,
        stderr=subprocess.STDOUT,
        start_new_session=os.name != "nt",
    )
    try:
        return child.wait()
    except BaseException:
        if child.poll() is None:
            if os.name == "nt":
                child.terminate()
            else:
                os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                if os.name == "nt":
                    child.kill()
                else:
                    os.killpg(child.pid, signal.SIGKILL)
                child.wait()
        raise


def contents(root: Path) -> dict[str, str]:
    listed = git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    result = {}
    for name in sorted(set(listed.split("\0")) - {""}):
        path = root / name
        if path.is_symlink():
            # Include target bytes as well: a changed symlink target is an input.
            result[name] = digest([os.readlink(path), path.read_bytes().hex()])
        elif path.is_file():
            result[name] = digest([path.stat().st_mode & 0o111, path.read_bytes().hex()])
        elif path.exists():
            raise ValueError(f"unsupported source input {name} (submodule/directory)")
        else:
            result[name] = "deleted"
    return result


def push_commit(root: Path, refs: str) -> str:
    """Fail closed for every pushed tip, including annotated tags and multiple refs."""
    head = git(root, "rev-parse", "HEAD")
    rows = [row.split() for row in refs.splitlines() if row.strip()]
    if not rows or any(len(row) != 4 for row in rows):
        raise ValueError(
            "missing Git push refs; run `molci doctor --install-hooks` to capture all refs"
        )
    for local_ref, local_sha, remote_ref, remote_sha in rows:
        if not all(re.fullmatch(r"[0-9a-f]{40}", sha) for sha in (local_sha, remote_sha)):
            raise ValueError(f"invalid push SHA for {local_ref}")
        if local_sha == "0" * 40:
            continue
        commit = git(root, "rev-parse", f"{local_sha}^{{commit}}")
        if commit != head:
            raise ValueError(
                f"{local_ref} -> {remote_ref}: pushed commit {commit} differs from HEAD {head}; "
                "push each source snapshot from its own clean worktree"
            )
    if git(root, "status", "--porcelain", "--untracked-files=normal"):
        raise ValueError("uncommitted source changes: commit/stash them before pushing")
    return head


class Runner:
    def __init__(self, root: Path, config: dict):
        self.root, self.config = root.resolve(), config
        self.gates = {g["id"]: g for g in config["gates"]}
        common = Path(git(root, "rev-parse", "--git-common-dir"))
        self.cache = (root / common).resolve() / "molci-v2"
        self.files = contents(root)
        self.keys: dict[str, str] = {}
        self.env = clean_git_env()
        self.env.pop("VIRTUAL_ENV", None)
        self.tools: dict[str, str] = {}
        self.platform = f"{platform.system()}-{platform.machine()}"
        known = [p for g in config["gates"] for p in g.get("inputs", [])]
        self.unknown = {
            p: h
            for p, h in self.files.items()
            if not any(fnmatch.fnmatchcase(p, pattern) for pattern in known)
        }

    def select(
        self, stage: str = "pre-push", gate: str | None = None, lane: str | None = None
    ) -> list[dict]:
        if gate and gate not in self.gates:
            raise ValueError(f"unknown gate: {gate}")
        lanes = self.config.get("platforms", {})
        if lane and lane not in lanes:
            raise ValueError(f"unknown platform lane: {lane}")
        wanted = (
            {gate}
            if gate
            else set(lanes[lane]["gates"])
            if lane and not lanes[lane].get("all_native")
            else {
                g["id"]
                for g in self.gates.values()
                if (stage == "pre-push" and g["stage"] in ("pre-commit", "pre-push"))
                or g["stage"] == stage
            }
        )
        pending = list(wanted)
        while pending:
            for dep in self.gates[pending.pop()].get("depends_on", []):
                if dep not in wanted:
                    wanted.add(dep)
                    pending.append(dep)
        return [g for g in self.gates.values() if g["id"] in wanted]

    def key(self, gate: dict) -> str:
        tools = {}
        for command in gate.get("tools", []):
            name = command[0]
            if not shutil.which(name):
                raise ValueError(
                    f"MISSING TOOL {name}: install it, then rerun `molci run {gate['id']}`"
                )
            identity = json.dumps(command)
            if identity not in self.tools:
                out = subprocess.run(
                    command, cwd=self.root, env=self.env, check=True, capture_output=True, text=True
                )
                self.tools[identity] = out.stdout + out.stderr
            tools[identity] = self.tools[identity]
        inputs = {
            p: h
            for p, h in self.files.items()
            if any(
                fnmatch.fnmatchcase(p, pattern)
                for pattern in self.config.get("global_inputs", []) + gate.get("inputs", [])
            )
        }
        # Ignored downloaded corpora are not source, but do affect tests.
        for pattern in gate.get("extra_inputs", []):
            for path in sorted(self.root.glob(pattern)):
                if path.is_file():
                    inputs[str(path.relative_to(self.root))] = hashlib.sha256(
                        path.read_bytes()
                    ).hexdigest()
        execution = {
            k: v
            for k, v in self.env.items()
            if (
                k.startswith(
                    ("CARGO_", "RUST", "UV_", "PYTHON", "CC", "CXX", "CMAKE_", "MOLCRAFTS_")
                )
                or k in self.config.get("environment", [])
            )
        }
        return digest(
            {
                "gate": gate,
                "profile": self.config,
                "pins": pins(self.root),
                "inputs": inputs,
                "unknown": self.unknown,
                "dependencies": {d: self.keys[d] for d in gate.get("depends_on", [])},
                "platform": [self.platform, platform.platform()],
                "python": sys.version,
                "tools": tools,
                "environment": execution,
                "engine": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            }
        )

    def artifacts(self, key: str, gate: dict) -> dict[str, str]:
        directory = self.cache / "artifacts" / key
        result = {}
        for pattern in gate.get("produces", []):
            files = sorted(directory.glob(pattern))
            if not files:
                raise ValueError(f"{gate['id']}: missing artifact {directory / pattern}")
            for path in files:
                result[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
        return result

    def cached(self, key: str, gate: dict) -> bool:
        path = self.cache / "success" / f"{key}.json"
        if not path.is_file():
            return False
        try:
            receipt = json.loads(path.read_text("utf-8"))
            return receipt == {"key": key, "artifacts": self.artifacts(key, gate)}
        except (OSError, ValueError):
            return False

    def execute(self, gates: list[dict], *, full: bool = False, explain: bool = False) -> int:
        commit = git(self.root, "rev-parse", "HEAD")
        print(
            f"MolCrafts CI v2\nCommit: {commit}\nPlatform: {self.platform}\n"
            f"Profile: {self.config['name']}",
            flush=True,
        )
        with exclusive(self.cache / "execution.lock"):
            # Re-read after locking: another process may have changed source/artifacts.
            if contents(self.root) != self.files:
                raise ValueError("source changed while waiting for validation lock; retry")
            for gate in gates:
                name = gate["id"]
                if platform.system() not in gate.get("os", [platform.system()]):
                    raise ValueError(f"UNSUPPORTED PLATFORM {self.platform}: required gate {name}")
                key = self.key(gate)
                self.keys[name] = key
                hit = not full and not gate.get("always") and self.cached(key, gate)
                if explain:
                    reason = (
                        "matching successful receipt and artifacts"
                        if hit
                        else "native requirement; no matching success"
                    )
                    print(f"{'CACHED' if hit else 'SELECT'}  {name}: {reason}")
                    if hit:
                        self.keys[name] = digest(
                            {"key": key, "artifacts": self.artifacts(key, gate)}
                        )
                    continue
                if hit:
                    print(f"CACHED  {name}", flush=True)
                else:
                    receipt = self.cache / "success" / f"{key}.json"
                    receipt.unlink(missing_ok=True)
                    artifact_dir = self.cache / "artifacts" / key
                    artifact_dir.mkdir(parents=True, exist_ok=True)
                    if gate.get("artifact_directory"):
                        self.env[gate["artifact_directory"]] = str(artifact_dir)
                    log = self.cache / "logs" / f"{name}-{key}.log"
                    log.parent.mkdir(parents=True, exist_ok=True)
                    command = gate["run"]
                    if command.startswith("molci:"):
                        command = self.internal(command)
                    else:
                        command = [
                            "bash",
                            "--noprofile",
                            "--norc",
                            "-euo",
                            "pipefail",
                            "-c",
                            command,
                        ]
                    print(f"RUN     {name} (log: {log})", flush=True)
                    started = time.monotonic()
                    with log.open("w", encoding="utf-8") as stream:
                        code = execute_command(
                            command, self.root, self.env | gate.get("env", {}), stream
                        )
                    if code:
                        print(log.read_text("utf-8", errors="replace")[-8000:], file=sys.stderr)
                        output = log.read_text("utf-8", errors="replace")
                        kind = "SOURCE/TEST FAILURE"
                        if code < 0 or code in (130, 143):
                            kind = "CANCELLED"
                        elif code == 127:
                            kind = "MISSING LOCAL TOOL"
                        elif re.search(
                            r"Could not resolve host|Connection (?:reset|refused)|timed out",
                            output,
                            re.I,
                        ):
                            kind = "NETWORK/RUNNER FAILURE"
                        elif re.search(
                            r"failed to (?:resolve|get)|No solution found|lockfile.*needs",
                            output,
                            re.I,
                        ):
                            kind = "DEPENDENCY RESOLUTION FAILURE"
                        print(
                            f"FAIL    {name}: {kind} (exit {code}); log: {log}\n"
                            f"Reproduce: molci run {name}",
                            file=sys.stderr,
                        )
                        return code if code > 0 else 128 - code
                    if contents(self.root) != self.files:
                        raise ValueError(
                            f"{name}: source changed during validation; result not cached"
                        )
                    record = {"key": key, "artifacts": self.artifacts(key, gate)}
                    receipt.parent.mkdir(parents=True, exist_ok=True)
                    with tempfile.NamedTemporaryFile(dir=receipt.parent, delete=False) as stream:
                        stream.write(dumps_deterministic(record).encode())
                        temporary = Path(stream.name)
                    temporary.replace(receipt)
                    print(f"PASS    {name} ({time.monotonic() - started:.2f}s)", flush=True)
                if gate.get("artifact_environment"):
                    artifacts = list(self.artifacts(key, gate))
                    if len(artifacts) != 1:
                        raise ValueError(f"{name}: expected exactly one exported artifact")
                    self.env[gate["artifact_environment"]] = artifacts[0]
                self.keys[name] = digest({"key": key, "artifacts": self.artifacts(key, gate)})
            if contents(self.root) != self.files:
                raise ValueError("source changed during validation; rerun before pushing")
            if not explain:
                print("Native verification: PASS", flush=True)
        return 0

    def internal(self, command: str) -> list[str]:
        hook = implementation() / "hooks/ci.py"
        return [
            sys.executable,
            str(hook),
            "--root",
            str(self.root),
            "--profile",
            "rust-python",
            "--gate",
            command.removeprefix("molci:"),
        ]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="molci")
    parser.add_argument(
        "command", choices=["doctor", "check", "verify", "run", "explain", "hook", "platform"]
    )
    parser.add_argument("gate", nargs="?")
    parser.add_argument("--root", default=".")
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--stage", choices=["pre-commit", "pre-push"], default="pre-push")
    parser.add_argument("--install-hooks", action="store_true")
    parser.add_argument("--snapshot", help=argparse.SUPPRESS)
    parser.add_argument("--completion", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    try:
        config = profile(root)
        snapshot = digest(contents(root))
        if args.snapshot and args.snapshot != snapshot:
            raise ValueError(
                "runner source snapshot differs from submitted source; refusing validation"
            )
        if args.snapshot:
            os.environ["MOLCI_ORCHESTRATED"] = "1"
        if args.command == "doctor":
            hook = Path(git(root, "rev-parse", "--git-path", "hooks/pre-push"))
            hook = root / hook
            if args.install_hooks:
                subprocess.run(
                    [
                        "uv",
                        "tool",
                        "run",
                        "--from",
                        "pre-commit==4.5.0",
                        "pre-commit",
                        "install",
                        "--overwrite",
                        "--hook-type",
                        "pre-commit",
                        "--hook-type",
                        "pre-push",
                    ],
                    cwd=root,
                    env=clean_git_env(),
                    check=True,
                )
                original = hook.with_name("pre-push.molci-transport")
                hook.replace(original)
                hook.write_text(
                    "#!/usr/bin/env bash\nset -euo pipefail\n"
                    "# molci: capture all refs before pre-commit consumes stdin.\n"
                    'export MOLCI_PUSH_REFS="$(cat)"\n'
                    'printf "%s\\n" "$MOLCI_PUSH_REFS" | '
                    '"$(dirname "$0")/pre-push.molci-transport" "$@"\n',
                    encoding="utf-8",
                )
                hook.chmod(0o755)
            if not hook.is_file() or "MOLCI_PUSH_REFS" not in hook.read_text("utf-8"):
                raise ValueError(
                    "hooks lack complete push-ref transport; run `molci doctor --install-hooks`"
                )
        if args.command == "hook" and args.stage == "pre-push":
            push_commit(root, os.environ.get("MOLCI_PUSH_REFS", ""))
        runner = Runner(root, config)
        if args.command == "doctor":
            for gate in runner.select():
                runner.keys[gate["id"]] = runner.key(gate)
            print(f"Tools: PASS\nHooks: PASS\nPins: {pins(root)}\nCache: {runner.cache}")
            return 0
        stage = "pre-commit" if args.command == "check" else args.stage
        if args.command in ("run", "explain", "platform") and not args.gate:
            raise ValueError(f"{args.command} requires a gate/platform name")
        gates = runner.select(
            stage,
            args.gate if args.command in ("run", "explain") else None,
            args.gate if args.command == "platform" else None,
        )
        remote = os.environ.get("MOLCRAFTS_HOOK_RUNNER")
        if (
            remote
            and not os.environ.get("SLURM_JOB_ID")
            and not args.snapshot
            and args.command not in ("check", "explain")
            and any(g["stage"] == "pre-push" for g in gates)
            and not (args.command == "hook" and args.stage == "pre-commit")
        ):
            if not shutil.which(remote):
                raise ValueError(
                    f"MISSING RUNNER {remote}: install/configure MOLCRAFTS_HOOK_RUNNER"
                )
            completion = runner.cache / "completion" / f"{uuid.uuid4().hex}.json"
            completion.parent.mkdir(parents=True, exist_ok=True)
            code = subprocess.run(
                [
                    remote,
                    str(root / "scripts/ci-hook.sh"),
                    *argv,
                    "--snapshot",
                    snapshot,
                    "--completion",
                    str(completion),
                ],
                cwd=root,
                env=clean_git_env(),
                check=False,
            ).returncode
            if code:
                return code if code > 0 else 128 - code
            if not completion.is_file():
                raise ValueError(
                    "RUNNER FAILURE: submission returned without completed verification; "
                    "runner must wait and preserve exit status/logs"
                )
            completed = json.loads(completion.read_text("utf-8"))
            completion.unlink()
            if completed.get("snapshot") != snapshot or digest(contents(root)) != snapshot:
                raise ValueError("RUNNER FAILURE: source changed or completion snapshot mismatched")
            return 0
        os.environ["MOLCI_ORCHESTRATED"] = "1"
        runner.env["MOLCI_ORCHESTRATED"] = "1"
        previous = signal.getsignal(signal.SIGTERM)

        def cancelled(signum, frame):
            raise KeyboardInterrupt("validation cancelled")

        signal.signal(signal.SIGTERM, cancelled)
        try:
            code = runner.execute(
                gates,
                full=args.full or bool(os.environ.get("GITHUB_ACTIONS")),
                explain=args.command == "explain",
            )
        finally:
            signal.signal(signal.SIGTERM, previous)
        if code == 0 and args.completion:
            Path(args.completion).write_text(
                dumps_deterministic(
                    {
                        "snapshot": snapshot,
                        "platform": runner.platform,
                    }
                ),
                encoding="utf-8",
            )
        return code
    except KeyboardInterrupt:
        print("MolCrafts CI: CANCELLED; no incomplete gate was cached", file=sys.stderr)
        return 130
    except (ValueError, OSError, subprocess.SubprocessError, yaml.YAMLError) as exc:
        print(f"MolCrafts CI: BLOCKED: {exc}", file=sys.stderr)
        return 2
