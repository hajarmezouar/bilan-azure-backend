# Self-hosted runner usage and benchmark

## Execution policy

The application pipeline deliberately separates trusted and untrusted execution:

| Event or job | Runner |
|---|---|
| Pull Request build and tests | GitHub-hosted `ubuntu-24.04` |
| Push or manual build from `main`, when enabled | `[self-hosted, linux, x64, azure-quiz]` |
| Azure deployment | GitHub-hosted runner with environment-scoped OIDC |

This prevents unreviewed Pull Request code from executing on the persistent Azure VM. The environment variable `USE_SELF_HOSTED_RUNNER` controls only trusted main-branch builds.

Enable self-hosted execution:

```bash
gh variable set USE_SELF_HOSTED_RUNNER \
  --env nonprod \
  --repo hajarmezouar/bilan-azure-backend \
  --body true
```

Disable it before runner maintenance or destruction:

```bash
gh variable set USE_SELF_HOSTED_RUNNER \
  --env nonprod \
  --repo hajarmezouar/bilan-azure-backend \
  --body false
```

## Benchmark design

The `Hosted vs self-hosted benchmark` workflow compares the same commit on both platforms and runs jobs sequentially to avoid resource contention. It measures two workloads:

- Maven application compilation and tests;
- Docker image build.

Each platform/workload combination performs one cold execution followed by three warm executions. The report uses the single cold time and the median warm time. Tool setup, queueing, builder bootstrap and artifact upload are reported separately through job durations and are excluded from command timings.

Run the benchmark:

```bash
gh workflow run runner-benchmark.yml \
  --repo hajarmezouar/bilan-azure-backend \
  --ref main
```

Download its retained evidence:

```bash
RUN_ID=$(gh run list \
  --repo hajarmezouar/bilan-azure-backend \
  --workflow runner-benchmark.yml \
  --event workflow_dispatch \
  --limit 1 \
  --json databaseId \
  --jq '.[0].databaseId')

gh run download "$RUN_ID" \
  --repo hajarmezouar/bilan-azure-backend \
  --dir "benchmark-$RUN_ID"
```

Artifacts are retained for 30 days:

- `benchmark-hosted-maven`;
- `benchmark-self-hosted-maven`;
- `benchmark-hosted-docker`;
- `benchmark-self-hosted-docker`;
- `benchmark-report`, containing the raw CSV files, job metadata and generated `report.md`.

## Interpreting results

Cold results show the initial cost without a dedicated Maven cache or reusable Docker builder. Warm Maven results reflect dependency reuse, while warm Docker results reuse layers for the same commit and therefore do not represent a complete recompilation.

A self-hosted runner is not automatically faster. Results depend on VM CPU and disk performance, network throughput, cache warmth, hosted-runner variability and the fact that a persistent machine retains build state. Conclusions should use the measured values from the generated report rather than estimates.

## Evidence

Verify the registered runner:

```bash
gh api repos/hajarmezouar/bilan-azure-backend/actions/runners \
  --jq '.runners[] | {name,status,busy,labels:[.labels[].name]}'
```

Verify which machine executed a pipeline:

```bash
gh api repos/hajarmezouar/bilan-azure-backend/actions/runs/RUN_ID/jobs \
  --jq '.jobs[] | {name,runner_name,labels,status,conclusion}'
```

The GitHub repository page under **Settings > Actions > Runners** provides the required visual evidence that `quiz-ci-runner` is online.

## Manual verification

The manual `Runner smoke test` workflow provides an independent, non-deploying verification path. Select the `main` branch and click **Run workflow**. The job can start only on a runner matching `[self-hosted, linux, x64, azure-quiz]` and verifies:

- the machine reports the expected runner name, OS and architecture;
- Java, the Java compiler and Docker are available;
- the backend Maven test suite passes;
- the production Dockerfile builds successfully;
- a workflow summary records the runner, commit and measured command durations.

The smoke test has read-only repository permission, receives no repository or environment secrets, performs no Azure login and does not deploy the application. If the job remains queued, the self-hosted runner is offline or its labels do not match.
