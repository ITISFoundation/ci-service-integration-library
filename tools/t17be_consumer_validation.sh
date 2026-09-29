#!/usr/bin/env bash
# T17be consumer-pattern validation (local-only).
#
# Proves the README's consumer recipe end-to-end: a service image takes the
# shared entrypoint via COPY --from= the ci-service-integration-library image
# (packaging path validated by buildpacktest below), installs gosu+fd-find,
# and keeps the "/bin/sh", "-c" ENTRYPOINT tail. The blank-line-before-shebang
# generated `run` file is deliberately NOT fixed here: the tail's sh fallback
# must execute it (T26me finding). Gates: container contract x2, hardened
# output-collection negatives x2 (teardown marker required, so an exec death
# cannot pass), explicit-command job non-root + mount I/O, and one GPU L3
# regression (golden predictions + device evidence).
#
# Hard rules: scratch clone + local image tags only; the real ML repo and its
# branch are never modified; nothing pushed or published. The COPY --from tag
# here is a LOCAL build; the real consumer PRs pin an exact RELEASED library
# tag (V10) once this branch's tag is published.
set -euo pipefail

LIB_TAG="${LIB_TAG:-t17be-exp}"
LIB_IMAGE="itisfoundation/ci-service-integration-library:$LIB_TAG"
ML_ORIGIN="${ML_ORIGIN:-$HOME/osparc-services/osparc-python-runner-machine-learning}"
WORK="${T17BE_WORK:-/tmp/opencode/t17be}"
EXP_TAG="t17be-exp"
SKIP_GPU="${SKIP_GPU:-0}"

banner() { printf '\n=== %s ===\n' "$*"; }

banner "stage 0: library image packaging (assets/ -> /opt/service-integration/assets/)"
rm -rf "$WORK/pack"
mkdir -p "$WORK/pack"
cp -r "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/assets" "$WORK/pack/"
# Deriving from the published v2.2.1 exercises exactly the layer the repo
# Dockerfile adds, without re-running CI's full ooil build here.
printf 'FROM itisfoundation/ci-service-integration-library:v2.2.1\nCOPY assets/ /opt/service-integration/assets/\n' \
    > "$WORK/pack/Dockerfile"
docker build -q -t "$LIB_IMAGE" "$WORK/pack" >/dev/null
docker run --rm --entrypoint sh "$LIB_IMAGE" -c \
    'test -x /opt/service-integration/assets/sc-entrypoint.sh && sh -n /opt/service-integration/assets/sc-entrypoint.sh'
echo "packaging OK: $LIB_IMAGE carries the executable asset"

banner "stage 1: scratch ML clone with README consumer overlay (COPY --from + sh -c tail, run files untouched)"
rm -rf "$WORK/ml"
git clone -q --shared "$ML_ORIGIN" "$WORK/ml"
git -C "$WORK/ml" checkout -q --detach
# consumer requirements from assets/README.md, applied verbatim:
sed -i "s|^FROM base AS production\$|FROM base AS production\nRUN apt-get update \&\& apt-get install -y --no-install-recommends gosu fd-find \&\& rm -rf /var/lib/apt/lists/*|" "$WORK/ml/common/Dockerfile"
sed -i "s|^COPY --chown=\${SC_USER_NAME}:\${SC_USER_NAME} entrypoint.sh docker/\$|COPY --from=$LIB_IMAGE --chown=\${SC_USER_NAME}:\${SC_USER_NAME} /opt/service-integration/assets/sc-entrypoint.sh docker/entrypoint.sh|" "$WORK/ml/common/Dockerfile"
grep -q "COPY --from=$LIB_IMAGE" "$WORK/ml/common/Dockerfile" || { echo "overlay: COPY --from line not applied"; exit 1; }
sed -i 's|^ENTRYPOINT \[ "/bin/sh", "docker/entrypoint.sh" \]$|ENTRYPOINT [ "/bin/sh", "docker/entrypoint.sh", "/bin/sh", "-c" ]|' "$WORK/ml/common/Dockerfile"
grep -q 'entrypoint.sh", "/bin/sh", "-c" \]' "$WORK/ml/common/Dockerfile" || { echo "overlay: ENTRYPOINT tail not applied"; exit 1; }
# the blank line must still be there: this run validates the tail fallback path
head -c 1 "$WORK/ml/osparc-python-runner-pytorch/service.cli/run" | grep -qx '' || { echo "expected untouched blank-line run file"; exit 1; }

banner "stage 2: build + retag consumer-pattern images $EXP_TAG"
# NB: these Makefiles expand $(PWD); must cd, `make -C` would mount the wrong dir
( cd "$WORK/ml" && make build )
docker tag simcore/services/comp/osparc-python-runner-pytorch:1.1.2 "simcore/services/comp/osparc-python-runner-pytorch:$EXP_TAG"
docker tag simcore/services/comp/osparc-python-runner-tensorflow:1.1.2 "simcore/services/comp/osparc-python-runner-tensorflow:$EXP_TAG"

banner "stage 3: consumer gates (contract, hardened negatives, explicit-command non-root)"
( cd "$WORK/ml" && uv run python tools/tests/test_regression_logic.py )
( cd "$WORK/ml" && uv run python tools/tests/test_container_contract.py pytorch --tag "$EXP_TAG" )
( cd "$WORK/ml" && uv run python tools/tests/test_container_contract.py tensorflow --tag "$EXP_TAG" )
( cd "$WORK/ml" && uv run python tools/tests/test_output_failure.py pytorch --tag "$EXP_TAG" )
( cd "$WORK/ml" && uv run python tools/tests/test_output_failure.py tensorflow --tag "$EXP_TAG" )
# basic explicit-command job through the full entrypoint chain, with real
# sidecar-style mounts (the asset refuses to start without INPUT_FOLDER
# mounted -- contract C16/C17 -- so an unmounted `docker run` is not a job)
IN_DIR="$WORK/explicit-input"; OUT_DIR="$WORK/explicit-output"
rm -rf "$IN_DIR" "$OUT_DIR"; mkdir -p "$IN_DIR" "$OUT_DIR"
IMG="simcore/services/comp/osparc-python-runner-pytorch:$EXP_TAG"
INPUT_MOUNT="$(docker image inspect "$IMG" --format '{{range .Config.Env}}{{println .}}{{end}}' | sed -n 's/^INPUT_FOLDER=//p')"
OUTPUT_MOUNT="$(docker image inspect "$IMG" --format '{{range .Config.Env}}{{println .}}{{end}}' | sed -n 's/^OUTPUT_FOLDER=//p')"
[ -n "$INPUT_MOUNT" ] && [ -n "$OUTPUT_MOUNT" ] || { echo "could not read mount envs from $IMG"; exit 1; }
EXPLICIT_OUT="$(docker run --rm -v "$IN_DIR:$INPUT_MOUNT" -v "$OUT_DIR:$OUTPUT_MOUNT" "$IMG" \
    'id -un && touch "$INPUT_FOLDER/t17be-explicit-ok" && echo WRITE-OK')"
echo "$EXPLICIT_OUT" | grep -qx scu || { echo "explicit command did not run as scu: $EXPLICIT_OUT"; exit 1; }
echo "$EXPLICIT_OUT" | grep -q WRITE-OK || { echo "explicit command file write failed: $EXPLICIT_OUT"; exit 1; }
test -f "$IN_DIR/t17be-explicit-ok" || { echo "explicit-command write did not reach the host mount"; exit 1; }
echo "explicit-command job OK: ran as scu, mounted I/O visible on the host bind"

banner "stage 4: GPU L3 regression on consumer-pattern image"
if [ "$SKIP_GPU" = "1" ]; then
    banner "L3 GPU regression SKIPPED (SKIP_GPU=1)"
else
    ( cd "$WORK/ml" && uv run python tools/validate_ml_regression.py pytorch --tag "$EXP_TAG" )
fi

banner "T17be consumer validation complete — scratch in $WORK, tags :$EXP_TAG"
