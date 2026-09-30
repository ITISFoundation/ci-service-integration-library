# T22rs — shared Makefile machinery: prototype record (2026-09-30)

Branch `t22rs/shared-make-fragment` (stacked on `t17be/shared-entrypoint`; same
`COPY assets/` packaging channel — one pinned image now carries the entrypoint
asset AND the make fragment AND, in the prototype, the ooil fixes).

## Duplicate surface found (before state)

- ML runner and the Cookie Cutter template each hand-copy the same three
  wrappers around the tools image: `_bumpversion`, `create-run-script`
  (`ooil run-creator`), `compose-spec` (`ooil compose`) — identical except the
  mount name and the pinned tag. The pins have already drifted: template
  `v2.1.25`, ML `v2.2.1` (live V10-drift instances; PyMorphoSonic even floats
  `:latest`).
- The released image's installed ooil also pinned an older simcore commit —
  read it from the `v2.2.1` TAG's own Dockerfile (`de246e2c`), not from current
  main (`c39478aa`): the first demo attempt failed on exactly this.

## Prototype (all local; `tools/t22rs_make_fragment_demo.sh`, green)

1. `assets/Makefile.mk`: `osparc-tools` runner (one image, one mount, host uid
   mapping) + `osparc-create-run-script` / `osparc-compose-spec` /
   `osparc-version`. Single-line `define` so it expands safely inside shell
   constructs.
2. Prototype tools image = released `v2.2.1` + `assets/` + T28rz/T20xy fixes
   patch-applied onto the v2.2.1-pinned ooil files (hunks verified to apply on
   that base; import + run-creator smoke checked INSIDE the image).
3. ML scratch clone: bootstrap-`include` of the fragment extracted from the
   pinned image (exact-tag V10-clean), three wrappers replaced by delegation.
   `make compose-spec` + `make create-run-script` run through the fragment;
   regenerated run files start with `#!` at byte 0 and their only diff vs
   checked-in is the two removed blank lines.
4. Measurement: ML Makefile 142 -> 128 lines (net, including the 8-line
   bootstrap); zero remaining copies of the wrapper logic.

## Related proof (this branch's tools/, ran green 2026-09-30)

`tools/t28rz_consumer_proof.sh`: with the fixed generator, the BARE
`exec gosu "$@"` handoff (NO `/bin/sh -c` tail) passes contract x2, hardened
negatives, word-form explicit-command job (non-root scu, host-visible bind
I/O) and GPU L3 goldens on `:t28rz-exp`. Consumers may drop the tail once the
fixed `service-integration` is released and pinned (V10). Side finding: the
tail was forgiving of string-form commands; array/word-form argv (production
dask-sidecar style) is the correct shape under the bare handoff (T27dk).

## Remaining before T22rs -> x (owner-gated, per C18/V10)

- Consumer PRs: ML (owned) first, then PyMorphoSonic/MedImProc (other owners)
  and the template, each pinning one released tag; Sleeper where applicable
  (its bump-my-version/bake design feeds the fragment, C14 dual-reference).
- `osparc-version` should adopt the dual-track bump-my-version design (§5)
  when `ooil`'s bump-version CLI matures — deliberately not baked here.
