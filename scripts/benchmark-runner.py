"""Measure real subprocess time; preserve failed measurements as evidence."""
import csv
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import time


def main():
    workload = os.environ['BENCH_WORKLOAD']
    runner = os.environ['BENCH_PLATFORM']
    if workload not in ('maven', 'docker'):
        raise ValueError('Unknown workload')
    out = Path('benchmark-results')
    out.mkdir(exist_ok=True)
    metadata = {
        'platform': runner, 'workload': workload, 'commit': os.environ['GITHUB_SHA'],
        'run_id': os.environ['GITHUB_RUN_ID'], 'cpu_count': os.cpu_count(),
        'os': platform.platform(),
        'cpu': Path('/proc/cpuinfo').read_text(),
        'memory': Path('/proc/meminfo').read_text(),
    }
    for name, command in [('java', ['java', '-version']), ('docker', ['docker', 'version'])]:
        result = subprocess.run(command, capture_output=True, text=True)
        metadata[name] = result.stdout + result.stderr
    (out / 'metadata.json').write_text(json.dumps(metadata, indent=2))
    cache = Path(os.environ['RUNNER_TEMP']) / ('benchmark-m2-' + os.environ['GITHUB_RUN_ID'])
    builder = 'benchmark-' + os.environ['GITHUB_RUN_ID'] + '-' + os.environ.get('GITHUB_RUN_ATTEMPT', '1')
    try:
        if workload == 'docker':
            subprocess.run(['docker', 'buildx', 'create', '--name', builder, '--driver', 'docker-container'], check=True)
            subprocess.run(['docker', 'buildx', 'inspect', builder, '--bootstrap'], check=True)
        elif cache.exists():
            shutil.rmtree(cache)
        with (out / 'timings.csv').open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=['platform', 'workload', 'commit', 'iteration', 'cache', 'seconds', 'exit_code'])
            writer.writeheader()
            for iteration in range(1, 5):
                if workload == 'maven':
                    command = ['bash', './mvnw', '-B', '-ntp', f'-Dmaven.repo.local={cache}', 'clean', 'verify']
                else:
                    command = ['docker', 'buildx', 'build', '--builder', builder, '--load', '--tag', f'quiz-benchmark:{builder}', '.']
                start = time.perf_counter()
                result = subprocess.run(command)
                writer.writerow(dict(platform=runner, workload=workload, commit=os.environ['GITHUB_SHA'],
                                     iteration=iteration, cache='cold' if iteration == 1 else 'warm',
                                     seconds=round(time.perf_counter() - start, 3), exit_code=result.returncode))
                stream.flush()
                if result.returncode:
                    raise SystemExit(result.returncode)
    finally:
        if workload == 'docker':
            subprocess.run(['docker', 'buildx', 'rm', builder], check=False)
            subprocess.run(['docker', 'image', 'rm', f'quiz-benchmark:{builder}'], check=False)
        elif cache.exists():
            shutil.rmtree(cache)


if __name__ == '__main__':
    main()
