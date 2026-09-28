from __future__ import annotations

import json
from pathlib import Path

from molcrafts_ci.cli import main
from molcrafts_ci.manifest import Manifest, Source, Tracking
from molcrafts_ci.snapshot import Snapshot


def test_cli_validate_and_ingest(tmp_path: Path, capsys) -> None:
    snap = Snapshot(
        manifest=Manifest(
            record="molrec",
            source=Source(repository="MolCrafts/molcrafts-molrec", commit="deadbeefcafebabe"),
            producer="molrec",
            tracking=Tracking(enabled=True, generation=1),
        ),
        payload={"schema_version": "0.1"},
    )
    snap_path = tmp_path / "snapshot.json"
    snap_path.write_text(snap.model_dump_json(indent=2), encoding="utf-8")
    data_root = tmp_path / "data"

    assert main(["validate-snapshot", str(snap_path)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True

    assert (
        main(
            [
                "ingest",
                str(snap_path),
                "--project",
                "molcrafts-molrec",
                "--data-root",
                str(data_root),
            ]
        )
        == 0
    )
    assert any(data_root.rglob("*.json"))
    assert any(data_root.rglob("*.jsonl"))


def write_snapshot_file(tmp_path: Path, record: str, *, tracked: bool = True) -> Path:
    snap = Snapshot(
        manifest=Manifest(
            record=record,
            source=Source(
                repository="MolCrafts/molpy",
                commit="abc123def456789",
                timestamp="2026-09-20T12:00:00Z",
            ),
            producer="pytest-benchmark",
            profile="linux-x86_64",
            tracking=Tracking(enabled=tracked, generation=1),
        ),
        payload={"metrics": {"mean_ns": 12.5}},
    )
    path = tmp_path / f"{record}.json"
    path.write_text(snap.model_dump_json(indent=2), encoding="utf-8")
    return path


def read_lines(capsys) -> list[dict]:
    return [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]


class TestValidateSnapshot:
    def test_reports_tracking_for_every_file(self, tmp_path: Path, capsys) -> None:
        """The submit action reads `tracking` to decide whether it has to push."""
        paths = [
            write_snapshot_file(tmp_path, "benchmark"),
            write_snapshot_file(tmp_path, "tests", tracked=False),
        ]

        assert main(["validate-snapshot", *[str(p) for p in paths]]) == 0
        rows = read_lines(capsys)
        assert [r["record"] for r in rows] == ["benchmark", "tests"]
        assert [r["tracking"] for r in rows] == [True, False]

    def test_a_broken_file_does_not_hide_the_rest(self, tmp_path: Path, capsys) -> None:
        good = write_snapshot_file(tmp_path, "benchmark")
        bad = tmp_path / "bad.json"
        bad.write_text("{not json", encoding="utf-8")

        assert main(["validate-snapshot", str(bad), str(good)]) == 2
        assert [r["record"] for r in read_lines(capsys)] == ["benchmark"]


class TestIngest:
    def test_ingests_every_snapshot_of_one_run(self, tmp_path: Path, capsys) -> None:
        paths = [
            write_snapshot_file(tmp_path, "benchmark"),
            write_snapshot_file(tmp_path, "coverage"),
        ]
        data_root = tmp_path / "data"

        args = ["ingest", *[str(p) for p in paths], "--project", "molpy"]
        assert main([*args, "--data-root", str(data_root)]) == 0
        assert [r["status"] for r in read_lines(capsys)] == ["ingested", "ingested", "listed"]

    def test_publishes_an_index_listing(self, tmp_path: Path, capsys) -> None:
        """The site reads the index over HTTP, where there is nothing to enumerate."""
        path = write_snapshot_file(tmp_path, "benchmark")
        data_root = tmp_path / "data"
        main(["ingest", str(path), "--project", "molpy", "--data-root", str(data_root)])
        capsys.readouterr()

        listing = json.loads((data_root / "index-listing.json").read_text(encoding="utf-8"))
        assert listing == {
            "indexes": ["index/molpy/benchmark.jsonl"],
            "published": {"molpy": "2026-09-20T12:00:00Z"},
        }

    def test_if_exists_skip_reports_the_snapshot_as_already_stored(
        self, tmp_path: Path, capsys
    ) -> None:
        path = write_snapshot_file(tmp_path, "benchmark")
        data_root = tmp_path / "data"
        args = ["ingest", str(path), "--project", "molpy", "--data-root", str(data_root)]

        assert main(args) == 0
        capsys.readouterr()
        assert main([*args, "--if-exists", "skip"]) == 0
        assert [r["status"] for r in read_lines(capsys)] == ["skipped", "listed"]

    def test_untracked_is_an_error_unless_the_caller_opts_out(self, tmp_path: Path, capsys) -> None:
        path = write_snapshot_file(tmp_path, "tests", tracked=False)
        data_root = tmp_path / "data"
        args = ["ingest", str(path), "--project", "molpy", "--data-root", str(data_root)]

        assert main(args) == 2
        capsys.readouterr()
        assert main([*args, "--skip-untracked"]) == 0
        assert [r["status"] for r in read_lines(capsys)] == ["untracked"]
        assert not data_root.exists()


class TestSnapshot:
    def test_builds_tests_from_a_cargo_test_log(self, tmp_path: Path, capsys, monkeypatch) -> None:
        monkeypatch.setenv("GITHUB_REPOSITORY", "MolCrafts/molrs")
        monkeypatch.setenv("GITHUB_SHA", "abcdef0123456789")
        log = tmp_path / "cargo-test.log"
        log.write_text("test result: ok. 2 passed; 0 failed; 1 ignored;\n", encoding="utf-8")
        out = tmp_path / "out"

        assert main(["snapshot", "--out", str(out), "--cargo-test", str(log)]) == 0
        row = read_lines(capsys)[0]
        assert row["ok"] is True
        assert row["record"] == "tests"
        snap = json.loads((out / "tests.json").read_text(encoding="utf-8"))
        assert snap["manifest"]["producer"] == "cargo-test"
        assert snap["payload"] == {"passed": 2, "failed": 0, "skipped": 1}

    def test_refuses_junit_and_cargo_test_together(self, tmp_path: Path, capsys) -> None:
        junit = tmp_path / "junit.xml"
        junit.write_text('<testsuite tests="1" failures="0" skipped="0"/>', encoding="utf-8")
        log = tmp_path / "cargo-test.log"
        log.write_text("test result: ok. 1 passed; 0 failed; 0 ignored;\n", encoding="utf-8")

        assert (
            main(
                [
                    "snapshot",
                    "--out",
                    str(tmp_path / "out"),
                    "--junit",
                    str(junit),
                    "--cargo-test",
                    str(log),
                ]
            )
            == 2
        )
        err = json.loads(capsys.readouterr().err)
        assert "not both" in err["error"]
