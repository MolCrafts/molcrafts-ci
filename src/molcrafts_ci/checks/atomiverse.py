"""Atomiverse gates reuse its public native-wheel and benchmark interfaces."""

from __future__ import annotations

import ast
import os
import platform
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

from molcrafts_ci import partners
from molcrafts_ci.validation import git, pins

ROOT = Path(os.environ["MOLCI_ROOT"])
SOURCE = ROOT / "build/ci-partners/molpy"
BUILD = ROOT / "build/molci/native"


def main(gate: str) -> int:
    os.chdir(ROOT)
    os.environ["UV_PYTHON"] = (ROOT / "python/.python-version").read_text("utf-8").strip()
    channel = tomllib.loads((ROOT / "rust-toolchain.toml").read_text("utf-8"))["toolchain"][
        "channel"
    ]
    os.environ["RUSTUP_TOOLCHAIN"] = channel
    if gate == "benchmark-report":
        subprocess.run(
            [
                "uv",
                "run",
                "--project",
                "python",
                "--no-sync",
                "python",
                "-m",
                "benchmarks",
                "report",
                "--input",
                "build/hf-benchmark-results/results.json",
                "--out",
                "build/hf-benchmark-results",
            ],
            cwd=ROOT,
            check=True,
        )
        subprocess.run(
            [
                "uv",
                "run",
                "--project",
                "python",
                "--no-sync",
                "molci",
                "validate-snapshot",
                str(ROOT / "build/hf-benchmark-results/snapshots/benchmark.json"),
            ],
            check=True,
        )
        return 0
    if gate == "partners":
        declared = partners.load()
        for name, (repository, ref) in partners.partners(declared).items():
            if not partners.SHA.fullmatch(ref):
                raise ValueError(f"{name}: verification requires an immutable commit")
            source = partners.resolve(name, repository, ref)
            destination = ROOT / "build/ci-partners" / name.lower()
            if (destination / ".git").exists() and git(
                destination, "status", "--porcelain", "--untracked-files=all"
            ):
                raise ValueError(f"{destination}: modified validation dependency; restore it first")
            partners.fetch(name, source, destination)
        return 0

    if gate == "pins":
        declared = pins(ROOT)
        sources = tomllib.loads((ROOT / "python/pyproject.toml").read_text("utf-8"))["tool"]["uv"][
            "sources"
        ]
        for package, key in (("molcrafts-molpy", "MOLPY"), ("molcrafts-ci", "CI")):
            if sources[package].get("rev") != declared[f"{key}_REF"]:
                raise ValueError(f"{package}: uv source must match {key}_REF in partners.env")
        version_tree = ast.parse((ROOT / "python/src/atomiverse/__init__.py").read_text("utf-8"))
        version = next(
            ast.literal_eval(node.value)
            for node in version_tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "__version__"
                for target in node.targets
            )
        )
        versions = re.findall(
            r"project\(Atomiverse\s+VERSION\s+([^\s)]+)",
            (ROOT / "CMakeLists.txt").read_text("utf-8"),
        )
        if not versions or any(value != version for value in versions):
            raise ValueError(f"CMake and Python release versions must both be {version}")
        if (
            os.environ.get("GITHUB_REF_TYPE") == "tag"
            and os.environ.get("GITHUB_REF_NAME") != f"v{version}"
        ):
            raise ValueError(f"release tag must be v{version}")
        subprocess.run(["uv", "--directory", "python", "lock", "--check"], check=True)
        return 0

    # Resolve every Python dependency from one lock, without silently building
    # or replacing either project. Their exact wheels are installed below.
    if os.environ.get("MOLCI_ATV_ENV") != "1":
        extras = ["dev", "native"]
        if gate == "docs":
            extras.append("docs")
        if gate == "benchmark-hf":
            extras.append("benchmark")
        command = [
            "uv",
            "--directory",
            "python",
            "sync",
            "--locked",
            "--group",
            "ci",
            "--no-install-project",
            "--no-install-package",
            "molcrafts-molpy",
        ]
        for extra in extras:
            command += ["--extra", extra]
        subprocess.run(command, check=True)
        return subprocess.run(
            ["uv", "--directory", "python", "run", "--no-sync", "python", __file__, gate],
            env=os.environ | {"MOLCI_ATV_ENV": "1"},
            check=False,
        ).returncode

    os.environ["ATV_MOLPY_PATH"] = str(SOURCE)
    if platform.system() == "Darwin":
        prefixes = [
            subprocess.check_output(["brew", "--prefix", name], text=True).strip()
            for name in ("libomp", "openblas", "fftw")
        ]
        os.environ["CMAKE_PREFIX_PATH"] = os.pathsep.join(
            [*prefixes, os.environ.get("CMAKE_PREFIX_PATH", "")]
        )
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["OPENBLAS_NUM_THREADS"] = "1"
    jobs = int(os.environ.get("CMAKE_BUILD_PARALLEL_LEVEL", min(os.cpu_count() or 2, 8)))
    if jobs < 1:
        raise ValueError("CMAKE_BUILD_PARALLEL_LEVEL must be positive")

    if gate == "molpy-wheel":
        # The existing command is the source of truth for the paired wheel.
        sys.path.insert(0, str(ROOT / "python/src"))
        from atomiverse.cli.build import build_env, build_molpy_wheel_command, molpy_target_dir

        directory = ROOT / "build/molci/molpy"
        shutil.rmtree(directory / "dist", ignore_errors=True)
        subprocess.run(
            build_molpy_wheel_command(ROOT, directory, molpy_root=SOURCE),
            env=build_env(jobs) | {"CARGO_TARGET_DIR": str(molpy_target_dir(directory))},
            check=True,
        )
        (wheel,) = (directory / "dist").glob("molcrafts_molpy-*.whl")
        shutil.copy2(wheel, Path(os.environ["MOLCI_WHEEL_DIR"]) / wheel.name)
        return 0

    wheels = [os.environ["MOLCI_MOLPY_WHEEL"]]
    if gate != "package":
        wheels.append(
            os.environ[
                "MOLCI_ATV_NATIVE_WHEEL"
                if gate in ("native", "python", "docs", "cuda", "benchmark-hf")
                else "MOLCI_ATV_PURE_WHEEL"
            ]
        )
    subprocess.run(
        ["uv", "pip", "install", "--python", sys.executable, "--no-deps", "--reinstall", *wheels],
        check=True,
    )

    if gate == "package":
        directory = Path(os.environ["MOLCI_WHEEL_DIR"])
        subprocess.run(
            [sys.executable, "-m", "build", "python", "--no-isolation", "--outdir", str(directory)],
            check=True,
        )
        subprocess.run(
            [sys.executable, "-m", "twine", "check", "--strict", *map(str, directory.iterdir())],
            check=True,
        )
        (wheel,) = directory.glob("atomiverse-*.whl")
        subprocess.run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                sys.executable,
                "--no-deps",
                "--reinstall",
                str(wheel),
            ],
            check=True,
        )
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "python/tests/test_pure_import.py",
                "python/tests/test_install_cli.py",
                "-q",
            ],
            check=True,
        )
        distribution = ROOT / "dist"
        shutil.rmtree(distribution, ignore_errors=True)
        shutil.copytree(directory, distribution)
    elif gate in ("native-build", "cuda-build", "hf-build"):
        from atomiverse.cli.build import (
            BuildState,
            build_env,
            build_wheel_command,
            run_config,
            state_file_in_build,
        )
        from atomiverse.cli.config import PRODUCT_MODULES, InstallConfig
        from atomiverse.cli.source import resolve_source

        if gate == "cuda-build" and (platform.system(), platform.machine()) != ("Linux", "aarch64"):
            raise ValueError("CUDA validation requires the configured aarch64 GH200 environment")
        kind = gate.removesuffix("-build")
        build = BUILD if kind == "native" else ROOT / "build/molci" / kind
        modules = {name: name != "cuda" or kind == "cuda" for name in PRODUCT_MODULES}
        if kind == "hf":
            modules = {"hf": True, "evaluate": True}
        config = InstallConfig(
            modules=modules,
            options={
                "mpi": False,
                "real_storage": "double",
                "real_work": "double",
                "id_size": "bigbig",
            },
            unbound={
                "ATV_BUILD_ANALYSIS": "OFF" if kind == "hf" else "ON",
                "ATV_BUILD_IO": "ON",
                "ATV_BUILD_KOKKOS": "OFF",
                "ATV_BUILD_LAUNCHER": "OFF",
                "ATV_BUILD_XC_ORACLE": "OFF",
                "ATV_BUILD_TESTS": "OFF" if kind == "hf" else "ON",
                "ATV_BUILD_EXAMPLES": "OFF" if kind == "hf" else "ON",
                "ATV_BUILD_BENCHMARKS": "OFF" if kind == "hf" else "ON",
                "ATV_TEST_TIMEOUT_SECONDS": "10",
                "ATV_TEST_OMP_THREADS": "1",
                "CMAKE_BUILD_WITH_INSTALL_RPATH": "ON",
                "BLA_VENDOR": "OpenBLAS",
                "CMAKE_CXX_COMPILER_LAUNCHER": shutil.which("ccache") or "",
                "Rust_TOOLCHAIN": channel,
                "CORROSION_TOOLS_RUST_TOOLCHAIN": channel,
            },
        )
        run_config(config, resolve_source(str(ROOT)), build_dir=build)
        state = BuildState.load(state_file_in_build(build))
        shutil.rmtree(build / "dist", ignore_errors=True)
        subprocess.run(
            build_wheel_command(ROOT / "python", build, state.defines),
            env=build_env(jobs),
            check=True,
        )
        (wheel,) = (build / "dist").glob("atomiverse-*.whl")
        shutil.copy2(wheel, Path(os.environ["MOLCI_WHEEL_DIR"]) / wheel.name)
    elif gate in ("native", "cuda"):
        directory = BUILD if gate == "native" else ROOT / "build/molci/cuda"
        command = [
            "ctest",
            "--test-dir",
            str(directory / "cmake"),
            "--no-tests=error",
            "--output-on-failure",
            "--timeout",
            "10",
            "-j",
            str(jobs),
        ]
        command += ["-L", "cuda"] if gate == "cuda" else ["-LE", "mpi|regression|cuda"]
        subprocess.run(command, check=True)
    elif gate == "python":
        subprocess.run(
            [
                sys.executable,
                "-I",
                "-c",
                "from atomiverse._binding import require_cpp; require_cpp()",
            ],
            check=True,
        )
        subprocess.run([sys.executable, "-m", "pytest", "python/tests", "-q"], check=True)
    elif gate == "framework":
        subprocess.run([sys.executable, "-m", "pytest", "tests/benchmarks", "-q"], check=True)
    elif gate == "docs":
        subprocess.run(
            [sys.executable, "-m", "zensical", "build", "--clean", "--strict"], check=True
        )
    elif gate == "benchmark-hf":
        subprocess.run(
            [
                sys.executable,
                "-m",
                "benchmarks",
                "attest-build",
                "--build-dir",
                str(ROOT / "build/molci/hf/cmake"),
                "--jobs",
                str(jobs),
                "--out",
                "build/hf-build-receipt.json",
            ],
            check=True,
        )
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/benchmarks",
                "python/tests/test_hf_bindings.py",
                "-q",
            ],
            check=True,
        )
        subprocess.run(
            [
                sys.executable,
                "-m",
                "benchmarks",
                "run",
                "--tier",
                os.environ.get("MOLCI_BENCHMARK_TIER", "smoke"),
                "--threads",
                "1",
                *[
                    arg
                    for name in ("rhf", "uhf", "rohf", "ghf", "rks", "uks", "rmp2", "rmp3")
                    for arg in ("--method", name)
                ],
                "--repeats",
                "1",
                "--warmup",
                "0",
                "--timeout",
                "600",
                "--build-receipt",
                "build/hf-build-receipt.json",
                "--out",
                "build/hf-benchmark-results",
            ],
            check=True,
        )
    else:
        raise ValueError(f"unknown Atomiverse gate: {gate}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1]))
    except subprocess.CalledProcessError as error:
        sys.exit(error.returncode)
    except (OSError, ValueError, KeyError) as error:
        sys.exit(f"Atomiverse validation: {error}")
