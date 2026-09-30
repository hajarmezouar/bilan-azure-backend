"""Summarize successful, comparable measurements; never invent missing results."""
import csv
from datetime import datetime
import json
from pathlib import Path
import statistics
import sys


def main(root):
    rows = []
    for path in root.glob('**/timings.csv'):
        with path.open() as stream:
            rows.extend(csv.DictReader(stream))
    print('# Measured runner comparison\n')
    print('Command durations in seconds. Gain = (hosted - self-hosted) / hosted * 100.\n')
    print('| Workload | Cache | Hosted | Self-hosted | Gain |')
    print('|---|---|---:|---:|---:|')
    for workload in ('maven', 'docker'):
        for cache in ('cold', 'warm'):
            groups = [[r for r in rows if r['platform'] == p and r['workload'] == workload and r['cache'] == cache]
                      for p in ('hosted', 'self-hosted')]
            expected = 1 if cache == 'cold' else 3
            comparable = all(len(g) == expected and all(r['exit_code'] == '0' for r in g) for g in groups)
            comparable = comparable and len({r['commit'] for g in groups for r in g}) == 1
            if not comparable:
                print(f'| {workload} | {cache} | incomplete/failed | incomplete/failed | not calculated |')
                continue
            hosted, own = [statistics.median(float(r['seconds']) for r in g) for g in groups]
            gain = f'{(hosted-own)/hosted*100:.1f} %' if hosted > 0 else 'not calculated'
            print(f'| {workload} | {cache} | {hosted:.3f} | {own:.3f} | {gain} |')
    print('\nCold = first pass with an empty dedicated Maven cache or Docker builder; warm = median of the next three passes.')
    print('Warm Docker runs reuse layers for an unchanged commit; this does not measure a full recompilation.')
    print('Tool setup, builder bootstrap, queueing and upload are excluded from command durations.\n')
    jobs_file = root / 'jobs.json'
    if jobs_file.exists():
        print('| Job | Conclusion | Job duration (s) |')
        print('|---|---|---:|')
        for page in json.loads(jobs_file.read_text()):
            for job in page['jobs']:
                if job.get('completed_at') and ' / ' in job['name']:
                    seconds = (datetime.fromisoformat(job['completed_at'].replace('Z', '+00:00')) -
                               datetime.fromisoformat(job['started_at'].replace('Z', '+00:00'))).total_seconds()
                    print(f"| {job['name']} | {job['conclusion']} | {seconds:.1f} |")


if __name__ == '__main__':
    main(Path(sys.argv[1]))
