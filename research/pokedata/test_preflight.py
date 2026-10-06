"""Regressão offline da pré-checagem do reprocessamento (pipeline/preflight.py)."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "pipeline"
sys.path.insert(0, str(ROOT))
from preflight import (check_collection, check_disk, check_modules, check_pr53,  # noqa: E402
                       check_python, check_workdir)


class PreflightRuleTests(unittest.TestCase):
    def test_python_and_dependencies(self):
        self.assertEqual(check_python((3, 9, 1))[0], "FALHA")
        self.assertEqual(check_python((3, 12, 0))[0], "OK")
        self.assertEqual(check_modules(["cv2"])[0], "FALHA")
        self.assertEqual(check_modules([])[0], "OK")

    def test_disk(self):
        self.assertEqual(check_disk(7 * 1024 ** 3)[0], "FALHA")
        self.assertEqual(check_disk(9 * 1024 ** 3)[0], "OK")

    def test_versionable_workdir_is_refused(self):
        self.assertEqual(check_workdir(in_repo=True, ignored=False)[0], "FALHA")
        self.assertEqual(check_workdir(in_repo=True, ignored=True)[0], "OK")
        self.assertEqual(check_workdir(in_repo=False, ignored=False)[0], "OK")

    def test_incomplete_or_unproven_collection(self):
        self.assertEqual(check_collection({"complete": False}, [])[0], "FALHA")
        self.assertEqual(check_collection(None, ["result.pkl"])[0], "AVISO")
        self.assertEqual(check_collection({"complete": True}, ["result.pkl"])[0], "OK")
        self.assertEqual(check_collection(None, [])[0], "OK")

    def test_pr53_path(self):
        self.assertEqual(check_pr53("")[0], "AVISO")
        self.assertEqual(check_pr53("/nao/existe.xlsx")[0], "FALHA")
        self.assertEqual(check_pr53(__file__)[0], "OK")


class PreflightGateTests(unittest.TestCase):
    def test_failed_preflight_stops_before_any_download(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stub = root / "python3"
            stub.write_text('''#!/bin/bash
printf '%s\\n' "$(basename "$1")" >> "$CALL_LOG"
[[ "$1" == */preflight.py ]] && exit 1
exit 0
''')
            stub.chmod(0o755)
            env = dict(os.environ, PATH=str(root) + os.pathsep + os.environ["PATH"], CALL_LOG=str(root / "calls"))
            result = subprocess.run(["bash", str(ROOT / "run_pipeline.sh")], cwd=root, env=env,
                                    capture_output=True, text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((root / "calls").read_text().split(), ["preflight.py"])


if __name__ == "__main__":
    unittest.main()
