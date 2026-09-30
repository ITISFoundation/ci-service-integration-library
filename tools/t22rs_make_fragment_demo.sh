#!/usr/bin/env bash
# T22rs prototype demo (local-only).
#
# Builds the envisioned end-state tools image LOCALLY: released
# ci-service-integration-library:v2.2.1 + assets/ (entrypoint + Makefile.mk)
# + the FIXED service-integration (T28rz/T20xy worktrees), then proves an ML
# runner scratch clone replaces its hand-copied tool wrappers with an `include`
# of the image-distributed fragment and still regenerates/executes correctly.
#
# Hard rules: scratch clone + local tags only; real repos untouched; nothing
# pushed/published. The real consumer PRs will pin a RELEASED tag (V10).
set -euo pipefail

LIB_SRC="${LIB_SRC:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"   # t22rs worktree (assets/)
SIMCORE_T28="${SIMCORE_T28:-$HOME/osparc-admin/osparc-simcore-t28rz}"    # fixed run-creator
SIMCORE_T20="${SIMCORE_T20:-$HOME/osparc-admin/osparc-simcore-t20xy}"    # fixed runtime defaults
ML_ORIGIN="${ML_ORIGIN:-$HOME/osparc-services/osparc-python-runner-machine-learning}"
WORK="${T22RS_WORK:-/tmp/opencode/t22rs}"
TOOLS_IMG="itisfoundation/ci-service-integration-library:t22rs-exp"
banner() { printf '\n=== %s ===\n' "$*"; }

banner "stage 0: duplicate-surface evidence (wrappers differ only by tag/mount)"
BEFORE_LINES=$(grep -cE '^' "$ML_ORIGIN/Makefile")
grep -q "itisfoundation/ci-service-integration-library:v2.1.25" \
    "$HOME/osparc-services/cookiecutter-osparc-service/{{cookiecutter.project_slug}}/Makefile" \
    && echo "V10 drift instance: cookiecutter template pins v2.1.25, ML pins v2.2.1"

banner "stage 1: prototype tools image (released v2.2.1 + assets + patched-in ooil fixes)"
rm -rf "$WORK/imgctx"; mkdir -p "$WORK/imgctx/assets"
cp "$LIB_SRC/assets/sc-entrypoint.sh" "$LIB_SRC/assets/Makefile.mk" "$WORK/imgctx/assets/"
# derive the pinned simcore commit from the v2.2.1 tag's OWN Dockerfile (the
# released image installs that sha; the current main Dockerfile may have drifted)
PIN_SHA="$(git -C "$LIB_SRC" show v2.2.1:Dockerfile | grep -oP 'ARG COMMIT_SHA="\K[0-9a-f]+' | head -1)"
[ -n "$PIN_SHA" ] || { echo "could not read pinned ooil COMMIT_SHA from library Dockerfile"; exit 1; }
SP=$WORK/imgctx/site-packages/service_integration; mkdir -p "$SP/cli"
git -C "$SIMCORE_T28" show "$PIN_SHA:packages/service-integration/src/service_integration/cli/_run_creator.py" > "$SP/cli/_run_creator.py"
git -C "$SIMCORE_T28" show "$PIN_SHA:packages/service-integration/src/service_integration/osparc_config.py" > "$SP/osparc_config.py"
# apply the fix commits onto the PINNED files (explicit target file; hunks verified compatible)
git -C "$SIMCORE_T28/packages/service-integration" show d87352ce7 -- src/service_integration/cli/_run_creator.py \
  | ( cd "$SP" && patch -s cli/_run_creator.py ) || { echo "T28rz hunk failed on pinned base $PIN_SHA"; exit 1; }
git -C "$SIMCORE_T20/packages/service-integration" show e7d57e998 -- src/service_integration/osparc_config.py \
  | ( cd "$SP" && patch -s osparc_config.py ) || { echo "T20xy hunk failed on pinned base $PIN_SHA"; exit 1; }
cat > "$WORK/imgctx/Dockerfile" <<'EOF'
FROM itisfoundation/ci-service-integration-library:v2.2.1
COPY assets/ /opt/service-integration/assets/
COPY site-packages/service_integration/ /home/scu/.venv/lib/python3.11/site-packages/service_integration/
RUN python -c "import service_integration.cli._run_creator, service_integration.osparc_config" \
    && ooil --version
EOF
docker build -q -t "$TOOLS_IMG" "$WORK/imgctx" >/dev/null
docker run --rm --entrypoint sh "$TOOLS_IMG" -c \
    'test -x /opt/service-integration/assets/sc-entrypoint.sh && test -f /opt/service-integration/assets/Makefile.mk && echo ASSETS-OK'

banner "stage 2: ML scratch clone bootstraps the fragment from the pinned tools image"
rm -rf "$WORK/ml"; git clone -q --shared "$ML_ORIGIN" "$WORK/ml"; git -C "$WORK/ml" checkout -q --detach
cd "$WORK/ml"
# the exact README bootstrap recipe:
docker run --rm --entrypoint cat "$TOOLS_IMG" /opt/service-integration/assets/Makefile.mk > .osparc-tools.mk
test -s .osparc-tools.mk || { echo "fragment extraction failed"; exit 1; }
# replace the three hand-copied wrappers with delegation to the fragment
TOOLS_IMG="$TOOLS_IMG" python3 - <<'PYEOF'
import os, re
TOOLS_IMG = os.environ["TOOLS_IMG"]
mk = open("Makefile").read()
orig = mk
# drop the docker-run _bumpversion/_create_run_script/compose-spec bodies
mk = re.sub(r"define _bumpversion.*?endef\n", "", mk, flags=re.S)
mk = re.sub(r"define _create_run_script.*?endef\n", "", mk, flags=re.S)
boot = (
    "\n# --- shared machinery (SPEC-COMP T22rs): fragment extracted from the pinned image ---\n"
    ".osparc-tools.mk:\n"
    f"\tdocker run --rm --entrypoint cat {TOOLS_IMG} /opt/service-integration/assets/Makefile.mk > \$@\n"
    "-include .osparc-tools.mk\n"
    f"OSPARC_TOOLS_IMAGE := {TOOLS_IMG}\n"
    "OSPARC_SERVICES := osparc-python-runner-pytorch osparc-python-runner-tensorflow\n\n"
)
mk = mk.replace("SHELL = /bin/sh", "SHELL = /bin/sh", 1)
mk = boot + mk
# delegate existing targets to the fragment; service-specific targets stay local
mk = mk.replace(
    "create-run-script: ## assembles run scrips for pytorch and tensorflow\n\t@$(call _create_run_script,osparc-python-runner-pytorch)\n\t@$(call _create_run_script,osparc-python-runner-tensorflow)",
    "create-run-script: osparc-create-run-script ## assembles run scrips for pytorch and tensorflow",
)
mk = re.sub(
    r"compose-spec: ## runs ooil to assemble the docker-compose\.yml file\n(?:\t.*\n)+",
    "compose-spec: osparc-compose-spec ## runs ooil to assemble the docker-compose.yml file\n",
    mk,
)
# delegate the version wrappers to the fragment too (define removed above)
for track in ("tensorflow", "pytorch"):
    mk = mk.replace(
        f"@$(call _bumpversion,$<,version-{track}-)",
        f"@$(MAKE) osparc-version bump=$(subst version-{track}-,,$@) cfg=$<",
    )
assert "_create_run_script" not in mk and "_bumpversion" not in mk and "ooil compose" not in mk, "wrapper removal incomplete"
open("Makefile", "w").write(mk)
print(f"Makefile lines: {len(orig.splitlines())} -> {len(mk.splitlines())} (delegation net includes 8-line bootstrap)")
PYEOF
grep -q "osparc-create-run-script" Makefile && grep -q "osparc-compose-spec" Makefile

banner "stage 3: fragment targets drive real ooil (fixed) on the clone"
( cd "$WORK/ml" && make compose-spec ) >/dev/null
( cd "$WORK/ml" && make create-run-script ) >/dev/null
for s in osparc-python-runner-pytorch osparc-python-runner-tensorflow; do
  head -c 2 "$WORK/ml/$s/service.cli/run" | grep -q '#!' || { echo "$s run not exec-clean"; exit 1; }
done
echo "fragment-driven create-run-script -> shebang byte 0 (fixed generator in the SAME image as the fragment)"
git -C "$WORK/ml" diff --stat -- '*/service.cli/run' | tail -1

banner "T22rs prototype demo complete — one pinned image carries entrypoint + make surface + fixed ooil"
