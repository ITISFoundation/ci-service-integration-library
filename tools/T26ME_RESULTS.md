# T26me experiment results

Local-only run of `tools/t26me_experiment.sh` (SKIP_GPU=1, per user directive
while the WSL GPU connection is dead — recovery requires `wsl --shutdown`).

## 2026-09-29 — record run (EXIT=0, log `/tmp/opencode/t26me_record.log`)

Experimental images built from `assets/sc-entrypoint.sh` (shared Sleeper
contract port, `/sys` excluded), tagged `:t26me-exp`, no consumer repo touched.

| Gate | Result |
|---|---|
| ML L1 regression logic | passed (6 tests) |
| ML L2 container contract (pytorch, tensorflow) | passed — SC_USER_ID/INPUT/OUTPUT/entrypoint shape hold with shared asset |
| ML L2 output-collection failure (pytorch, tensorflow) | passed — container exits 1, no archives (exit-status contract preserved through `exec gosu`) |
| ML L3 GPU regression | **deferred** — WSL GPU dead (`cuInit` 100 NO_DEVICE); rerun `tools/validate_ml_regression.py <fw> --tag t26me-exp` after `wsl --shutdown` |
| Sleeper parity diff | asset vs upstream: intended deltas only (header, `/sys` exclusion, wording) |
| Sleeper unit suite | 23 passed with shared entrypoint |
| Sleeper integration suite (cpu, gpu, mpi variants) | 4 passed with shared entrypoint |

Before/after startup timing (the 94.1 s / 100.6 s `find`-scan baseline in
`docs/regression-baseline.md`) requires the same deferred L3 runs; the
`fdfind --exec-batch` traversal is the expected improvement to measure.

## 2026-09-29 — INVALIDATION NOTICE for the 2026-09-28 record run

The `:t26me-exp` negative-test results above were FALSE POSITIVES: the
shared asset's `exec gosu "$@"` handoff dies with ENOEXEC ("exec format
error") because ooil's checked-in `service.cli/run` files start with a
blank line (shebang on line 2), which the historical `su --command "...
$*"` chain masked via sh's script fallback. The containers died before
teardown; `rc != 0` alone let that pass. Also, `make build` inside the
scratch clone overwrote the host's `:1.1.2` tags with experimental
builds (same repo:tag names).

Follow-ups (done): experiment strips the blank line in the scratch
overlay only and verifies the shebang at byte 0; `test_output_failure.py`
now requires the `Stopping teardown` log marker (ML repo commit
`T23fm hardening`); a real finding for upstream `ooil` run-creator
(generated run must be exec-able — V4). Full GPU rerun follows.

## 2026-09-29 — FINAL record run (GPU restored via CDI regeneration, B7): EXIT=0

Experimental `:t26me-exp` (shared entrypoint + exec-clean run overlay), same
machine same day as the production rerun — timings are observational:

| Framework | startup_to_ready (find+su baseline) | startup_to_ready (fdfind+gosu) | device | golden/probability assertions |
|---|---:|---:|---|---|
| PyTorch | 94.072 s | **14.041 s** (6.7x) | `cuda:0` | passed |
| TensorFlow | 100.596 s | **5.818 s** (17.3x) | `GPU:0` | passed |

Gates: contracts x2, hardened output-collection negatives x2 (teardown
marker required), L3 GPU regressions x2, Sleeper 23 unit + 4 integration — all green.

Production remain-green confirmation (`make validate-regression` on genuine
`:1.1.2`, same day): EXIT=0, both frameworks `device=gpu`, goldens match;
production startup measured 183.6 s / 133.8 s this run (host state differs from
the Sep-28 record; observational only — the exp-vs-prod comparison stands on
same-day runs). T26me verification columns all satisfied -> task closed.

## Open items for consumer adoption (not T26me scope)

1. Human review of this branch's diff -> if approved, T17be ports
   `assets/sc-entrypoint.sh` into `ci-service-integration-library` proper;
   consumer Dockerfiles change only then (C18).
2. Upstream `ooil` run-creator: generated `service.cli/run` must start with
   the shebang at byte 0 (currently a leading blank line; masked historically
   by `su --command`, fatal under `exec gosu`) — V4.
