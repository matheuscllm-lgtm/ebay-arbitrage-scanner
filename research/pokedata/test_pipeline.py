"""Offline subprocess regression: a failed extraction must stop the pipeline."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

PIPELINE = Path(__file__).resolve().parent / "pipeline/run_pipeline.sh"


@unittest.skipIf(os.name == "nt", "exige bash POSIX: no Windows, o `bash` do PATH do Python é o lançador do WSL")
class PipelineFailureTests(unittest.TestCase):
    def run_stubbed(self, failed_shard):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stub = root / "python3"
            stub.write_text('''#!/bin/bash
printf '%s\\n' "$(basename "$1") ${2:-}" >> "$CALL_LOG"
if [[ "$1" == */extract.py && "${2:-}" == "$FAILED_SHARD" ]]; then
  exit 7
fi
exit 0
''')
            stub.chmod(0o755)
            env = dict(os.environ, PATH=str(root) + os.pathsep + os.environ["PATH"],
                       CALL_LOG=str(root / "calls"), FAILED_SHARD=failed_shard)
            result = subprocess.run(["bash", str(PIPELINE)], cwd=root, env=env,
                                    capture_output=True, text=True, timeout=10)
            calls = (root / "calls").read_text()
            return result, calls

    def test_each_extraction_failure_stops_downstream(self):
        for shard in ("0", "1"):
            with self.subTest(shard=shard):
                result, calls = self.run_stubbed(shard)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("detect_placeholders.py", calls)
                self.assertNotIn("build_xlsx.py", calls)

    def test_success_reaches_export(self):
        result, calls = self.run_stubbed("none")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("build_xlsx.py", calls)

    def test_classification_runs_again_after_limitless(self):
        result, calls = self.run_stubbed("none")
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = calls.splitlines()
        assemble = [i for i, line in enumerate(lines) if line.startswith("assemble.py")]
        limitless = next(i for i, line in enumerate(lines) if line.startswith("lim_jp.py"))
        export = next(i for i, line in enumerate(lines) if line.startswith("build_xlsx.py"))
        self.assertEqual(len(assemble), 2)
        self.assertLess(assemble[0], limitless)
        self.assertLess(limitless, assemble[1])
        self.assertLess(assemble[1], export)


if __name__ == "__main__":
    unittest.main()
