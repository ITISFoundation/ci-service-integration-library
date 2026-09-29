#!/usr/bin/env bash
# T26me dual-reference ownership/entrypoint migration experiment (local-only).
#
# Builds locally-tagged images that consume assets/sc-entrypoint.sh (the ported
# Sleeper ownership contract) and drives both dual-reference gates from
# SPEC-COMP.md C14/C18/T26me:
#   1. ML runners: full three-layer regression (L1 logic, L2 contract +
#      output-failure negative test, L3 GPU with golden assertions) against
#      experimental images built from the shared entrypoint.
#   2. Sleeper: parity diff shared-asset vs upstream entrypoint, then its own
#      unit+integration suite with the shared entrypoint overlaid.
#
# Hard rules: local branches/worktrees and locally-tagged images only. Never
# pushes, never touches the real consumer repositories, publishes nothing.
# Requires: docker, make, uv, a working NVIDIA GPU (L3 asserts no CPU fallback).
set -euo pipefail

ASSET="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/assets/sc-entrypoint.sh"
ML_ORIGIN="${ML_ORIGIN:-$HOME/osparc-services/osparc-python-runner-machine-learning}"
WORK="${T26ME_WORK:-/tmp/opencode/t26me}"
EXP_TAG="t26me-exp"
SKIP_SLEEPER="${SKIP_SLEEPER:-0}"
SKIP_GPU="${SKIP_GPU:-0}"   # user-directed: defer L3 GPU runs while WSL GPU is down

banner() { printf '\n=== %s ===\n' "$*"; }

# ---------------------------------------------------------------- ML side ----
banner "stage 1: experimental ML runner images (shared entrypoint)"
rm -rf "$WORK/ml"
git clone -q --shared "$ML_ORIGIN" "$WORK/ml"
git -C "$WORK/ml" checkout -q --detach
cp "$ASSET" "$WORK/ml/common/entrypoint.sh"
# migration requirement: exec gosu handoff needs an exec-able `run`; ooil's
# checked-in run files start with a blank line (shebang on line 2 -> ENOEXEC,
# historically masked by the su --command "sh fallback"). Strip in scratch only.
sed -i '1{/^$/d}' "$WORK/ml/osparc-python-runner-pytorch/service.cli/run" \
                "$WORK/ml/osparc-python-runner-tensorflow/service.cli/run"
head -c 2 "$WORK/ml/osparc-python-runner-pytorch/service.cli/run" | grep -q '#!' || { echo "run file still not exec-clean"; exit 1; }
# shared asset needs gosu + fd-find (fdfind) in the ubuntu24.04 base
sed -i 's|^FROM base AS production$|FROM base AS production\nRUN apt-get update \&\& apt-get install -y --no-install-recommends gosu fd-find \&\& rm -rf /var/lib/apt/lists/*|' "$WORK/ml/common/Dockerfile"
grep -q "fd-find" "$WORK/ml/common/Dockerfile"

banner "stage 2: build + retag experimental images $EXP_TAG"
# NB: these Makefiles expand $(PWD); must cd, `make -C` would mount the wrong dir
( cd "$WORK/ml" && make build )
# Makefile pins TAG_* to 1.1.2; retag both framework images for the experiment
docker tag simcore/services/comp/osparc-python-runner-pytorch:1.1.2 "simcore/services/comp/osparc-python-runner-pytorch:$EXP_TAG"
docker tag simcore/services/comp/osparc-python-runner-tensorflow:1.1.2 "simcore/services/comp/osparc-python-runner-tensorflow:$EXP_TAG"

banner "stage 3: ML dual gates (CPU layers then GPU regression + exit-status)"
( cd "$WORK/ml" && uv run python tools/tests/test_regression_logic.py )
( cd "$WORK/ml" && uv run python tools/tests/test_container_contract.py pytorch --tag "$EXP_TAG" )
( cd "$WORK/ml" && uv run python tools/tests/test_container_contract.py tensorflow --tag "$EXP_TAG" )
( cd "$WORK/ml" && uv run python tools/tests/test_output_failure.py pytorch --tag "$EXP_TAG" )
( cd "$WORK/ml" && uv run python tools/tests/test_output_failure.py tensorflow --tag "$EXP_TAG" )
# L3 GPU: golden predictions + device evidence + timings; compare
# startup_to_ready against the find-scan baseline in docs/regression-baseline.md
if [ "$SKIP_GPU" = "1" ]; then
    banner "L3 GPU regression SKIPPED (SKIP_GPU=1) — T26me stays ~ until GPU gate runs green"
else
( cd "$WORK/ml" && uv run python tools/validate_ml_regression.py pytorch --tag "$EXP_TAG" | tee "$WORK/measurement-pytorch.json" )
( cd "$WORK/ml" && uv run python tools/validate_ml_regression.py tensorflow --tag "$EXP_TAG" | tee "$WORK/measurement-tensorflow.json" )

banner "stage 4: before/after timing summary"
python3 - "$WORK" <<'EOF'
import json, pathlib, sys
work = pathlib.Path(sys.argv[1])
baseline = {"pytorch": 94.072, "tensorflow": 100.596}  # find-scan startup, docs/regression-baseline.md
for fw in ("pytorch", "tensorflow"):
    m = json.loads((work / f"measurement-{fw}.json").read_text())
    ready = m["timings_seconds"]["startup_to_ready"]
    print(f"{fw}: startup_to_ready {ready:.3f}s vs find-scan baseline {baseline[fw]:.3f}s "
          f"device={m['result']['actual_device']}")
EOF
fi

# ------------------------------------------------------------ Sleeper side ---
if [ "$SKIP_SLEEPER" = "1" ]; then
    banner "sleeper parity skipped (SKIP_SLEEPER=1)"
    exit 0
fi

banner "stage 5: sleeper parity diff + suite with shared entrypoint"
rm -rf "$WORK/sleeper-repo"
# sleeper lives at services/sleeper inside the github-osparc-services clone root
git clone -q --shared "${SLEEPER_REPO:-$HOME/osparc-services/github-osparc-services}" "$WORK/sleeper-repo"
SL="$WORK/sleeper-repo/services/sleeper"
git -C "$WORK/sleeper-repo" checkout -q --detach
echo "--- diff upstream entrypoint vs shared asset (expect: header + --exclude sys only) ---"
diff "$SL/docker/custom/entrypoint.sh" "$ASSET" || true
cp "$ASSET" "$SL/docker/custom/entrypoint.sh"
# integration tests consume locally-built images; build before the suite
( cd "$SL" && make build )
( cd "$SL" && make devenv tests ) \
  || echo "SLEEPER SUITE FAILED (report, do not dismiss: T26me requires the Sleeper gate green)"

banner "experiment complete — review $WORK, image tags :$EXP_TAG"
