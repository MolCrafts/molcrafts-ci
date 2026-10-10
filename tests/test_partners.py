"""Regression checks for explicit dependency resolution and immutable fetches."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent / "src/molcrafts_ci"
SPEC = importlib.util.spec_from_file_location("partner_resolver", ROOT / "partners.py")
assert SPEC is not None and SPEC.loader is not None
partners = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = partners
SPEC.loader.exec_module(partners)
SHA = "a" * 40


class ResolutionTests(unittest.TestCase):
    def test_declared_branch_is_not_overridden_by_master_or_a_sibling(self):
        with patch.object(partners, "ls_remote", return_value=SHA) as remote:
            source = partners.resolve("DEP", "MolCrafts/dep", "dev")
        self.assertEqual(source.commit, SHA)
        self.assertEqual(source.ref, "refs/heads/dev")
        remote.assert_called_once_with("https://github.com/MolCrafts/dep.git", "refs/heads/dev")

    def test_sha_needs_no_branch_lookup(self):
        with patch.object(partners, "ls_remote") as remote:
            source = partners.resolve("DEP", "MolCrafts/dep", SHA)
        remote.assert_not_called()
        self.assertEqual(source.ref, SHA)

    def test_fetch_uses_resolved_sha_even_if_branch_moves(self):
        import tempfile

        calls = []

        def git(*args, **kwargs):
            calls.append(args)
            return subprocess.CompletedProcess(args, 0, SHA + "\n", "")

        source = partners.Source(
            "MolCrafts/dep",
            "https://github.com/MolCrafts/dep.git",
            "refs/heads/dev",
            SHA,
            "test",
        )
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(partners, "git", side_effect=git),
        ):
            partners.fetch("DEP", source, Path(tmp) / "dep")
        self.assertIn(("fetch", "-q", "--depth=1", source.url, SHA), calls)
        self.assertNotIn(("fetch", "-q", "--depth=1", source.url, source.ref), calls)

    def test_checkout_mismatch_fails(self):
        import tempfile

        def git(*args, **kwargs):
            return subprocess.CompletedProcess(args, 0, "b" * 40 + "\n", "")

        source = partners.Source(
            "MolCrafts/dep", "https://github.com/MolCrafts/dep.git", SHA, SHA, "test"
        )
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(partners, "git", side_effect=git),
            self.assertRaises(SystemExit),
        ):
            partners.fetch("DEP", source, Path(tmp) / "dep")

    def test_cached_layout_checks_copied_path_dependencies(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            source, cached = Path(tmp) / "source", Path(tmp) / "cached"
            source.mkdir()
            cached.mkdir()
            subprocess.run(["git", "init", "-q", str(source)], check=True)
            manifest = '[tool.uv.sources]\ndep = {path = "../missing"}\n'
            (source / "pyproject.toml").write_text(manifest, encoding="utf-8")
            subprocess.run(["git", "add", "pyproject.toml"], cwd=source, check=True)
            (cached / "pyproject.toml").write_text(manifest, encoding="utf-8")
            with (
                patch.object(partners, "ROOT", cached),
                patch.object(partners, "resolved", return_value={}),
                patch.dict(partners.os.environ, PARTNERS_SOURCE=str(source)),
            ):
                self.assertEqual(partners.check(), 1)

    def test_layout_reuses_build_state_between_runs(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            source = home / "source"
            source.mkdir()
            subprocess.run(["git", "init", "-q", str(source)], check=True)
            with (
                patch.object(partners, "ROOT", source),
                patch.object(partners, "load", return_value={"SELF": "example"}),
                patch.object(partners, "resolved", return_value={}),
                patch.object(partners.Path, "home", return_value=home),
                patch.dict(partners.os.environ),
            ):
                partners.os.environ.pop("MOLCRAFTS_PARTNER_CACHE", None)
                make = (
                    "from pathlib import Path; Path('.venv').mkdir(); Path('.venv/marker').touch()"
                )
                check = "from pathlib import Path; assert Path('.venv/marker').exists()"
                self.assertEqual(partners.run([sys.executable, "-c", make]), 0)
                self.assertEqual(partners.run([sys.executable, "-c", check]), 0)


if __name__ == "__main__":
    unittest.main()
