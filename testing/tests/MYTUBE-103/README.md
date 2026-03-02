# MYTUBE-103 — Deploy API Workflow: Concurrent Commits Handled Without Conflict

## Objective

Verify that the `Deploy API` GitHub Actions workflow handles multiple simultaneous
triggers without causing race conditions or inconsistent deployment states. The
latest commit must be correctly prioritised for deployment, and concurrent runs
must be managed (older runs cancelled or new runs queued) to ensure environment
consistency.

## Test Type

`ci-cd` — GitHub Actions workflow validation via static analysis and live API checks.

## Test Structure

### Part A — Concurrency Static Analysis (always runs)

Reads `.github/workflows/deploy-api.yml` and verifies:

1. A `concurrency` block is defined at the workflow level.
2. `concurrency.group` is set and references a branch expression (`github.ref` /
   `github.ref_name`) so that concurrent pushes to the same branch compete in
   the same group.
3. `concurrency.group` includes a workflow-level identifier to avoid cross-workflow
   cancellations.
4. `concurrency.cancel-in-progress: true` is set so the older run is automatically
   cancelled when a newer commit arrives.

### Part B — GitHub API Live Run History Check (requires `GITHUB_TOKEN`)

Uses the `gh` CLI to inspect recent run history on `main` and confirms:

1. At most one run is active (`in_progress` or `queued`) at any snapshot.
2. Every cancelled run has a newer run that replaced it (i.e. the cancel was
   caused by the concurrency mechanism, not an unrelated failure).
3. No two successful runs share the same commit title (which would indicate two
   deployments ran concurrently for the same commit).

## Prerequisites

- Python 3.10+
- `pytest`
- `pyyaml`
- Repository checked out (workflow file accessible at
  `.github/workflows/deploy-api.yml`)

## Environment Variables

| Variable       | Required for | Description                                      |
|----------------|--------------|--------------------------------------------------|
| `GITHUB_TOKEN` | Part B only  | GitHub personal access token or Actions token.   |

## Running the Tests

```bash
# Part A only (no credentials needed):
pytest testing/tests/MYTUBE-103/test_mytube_103.py -v

# Both parts (with live GitHub API check):
GITHUB_TOKEN=<token> pytest testing/tests/MYTUBE-103/test_mytube_103.py -v
```

## Expected Output

```
PASSED  test_concurrency_block_is_defined
PASSED  test_concurrency_group_is_set
PASSED  test_concurrency_group_includes_branch_reference
PASSED  test_cancel_in_progress_is_true
PASSED  test_concurrency_group_is_workflow_scoped
SKIPPED test_recent_runs_exist            [no GITHUB_TOKEN]
SKIPPED test_at_most_one_active_run_at_any_time
SKIPPED test_cancelled_runs_have_newer_replacement
SKIPPED test_no_concurrent_successful_runs_for_same_commit
```

With `GITHUB_TOKEN` set the skipped tests run as well.
