# T17be — shared entrypoint port + consumer-pattern validation

Branch `t17be/shared-entrypoint`. Ports the reviewed `t26me/entrypoint-experiment`
asset (byte-identical) into the library, packages it in the runtime image at
`/opt/service-integration/assets/sc-entrypoint.sh`, and documents the consumer
recipe (`assets/README.md`).

## Validation record (2026-09-29, host ordonez-wkst, GPU via regenerated CDI spec)

`tools/t17be_consumer_validation.sh` (scratch clone + local tags only; nothing
pushed/published, real ML repo never modified):

| Gate | Result |
|---|---|
| Packaging: image derives published `v2.2.1` + `COPY assets/` layer | asset present, executable, `sh -n` clean |
| Consumer image built via `COPY --from=...:t17be-exp` + apt `gosu fd-find` + `"/bin/sh","-c"` tail | built; generated blank-line `run` files deliberately untouched — the tail's sh fallback executes them (T26me finding) |
| Container contract x2 (frameworks) | OK (ML test relaxed to accept both approved shapes: no-tail production, exact Sleeper tail — arbitrary tails still fail) |
| Hardened output-collection negatives x2 | caught, teardown marker present (`rc` 1 for the right reason) |
| Basic explicit-command job (real bind mounts) | ran as `scu`, write visible on host bind; note: unmounted `docker run` is correctly REFUSED by the asset ("must mount '/input'") — mount contract enforced |
| GPU L3 regression (pytorch, consumer-pattern image) | `cuda:0`, goldens + tolerances identical; `startup_to_ready` 3.265 s, wall 4.74 s (observational; baseline 94.07 s; T26me tailless variant measured 14.04 s) |

## Remaining before T17be -> x

- Every consumer Dockerfile references the shared entrypoint: consumer PRs
  (ML runner, Cookie Cutter template, PMS via replay, MedImProc variants)
  must pin an exact RELEASED library tag (V10) — publish/merge is a human
  gate, and several consumers are other owners' repos (C18).
- Library image tag containing the asset must be published by CI before any
  consumer can pin it.
