"""Guard against reporting a gain from incomplete or incomparable evidence."""
import contextlib
import csv
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('report', Path(__file__).with_name('report-benchmark.py'))
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)


class EvidenceTests(unittest.TestCase):
    def render(self, *, missing=False, failed=False, different_commit=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (root / 'timings.csv').open('w', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=['platform', 'workload', 'commit', 'iteration', 'cache', 'seconds', 'exit_code'])
                writer.writeheader()
                for platform, seconds in [('hosted', 10), ('self-hosted', 5)]:
                    for iteration in range(1, 4):
                        if missing and platform == 'self-hosted' and iteration == 3:
                            continue
                        writer.writerow(dict(platform=platform, workload='maven',
                                             commit='other' if different_commit and platform == 'self-hosted' else 'same',
                                             iteration=iteration, cache='warm', seconds=seconds,
                                             exit_code=1 if failed and platform == 'self-hosted' else 0))
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                report.main(root)
            return output.getvalue()

    def test_successful_comparable_measurements(self):
        self.assertIn('| maven | warm | 10.000 | 5.000 | 50.0 % |', self.render())

    def test_missing_failed_or_different_commit_never_claim_gain(self):
        for option in ('missing', 'failed', 'different_commit'):
            with self.subTest(option=option):
                self.assertNotIn('50.0 %', self.render(**{option: True}))
                self.assertIn('not calculated', self.render(**{option: True}))


if __name__ == '__main__':
    unittest.main()
