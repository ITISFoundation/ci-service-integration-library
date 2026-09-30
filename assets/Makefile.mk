# Shared oSPARC service Makefile machinery (SPEC-COMP T22rs).
#
# Consumers `include` this fragment (extracted from THIS pinned image, see the
# bootstrap recipe in assets/README.md) instead of re-implementing the
# "docker run <pinned tools image> ooil/bump2version with $(PWD) mounted"
# wrapper per repository. Service-specific targets (build, run, smoke,
# regression, GPU) stay in the consumer Makefile.
#
# Consumer configuration (set before the include):
#   OSPARC_TOOLS_IMAGE    exact-pinned tools image (V10; this image)
#   OSPARC_SERVICES       service dirs, each with .osparc/<svc>/metadata.yml
#   OSPARC_MOUNT          container mount point for the repo (default /repo)

OSPARC_TOOLS_IMAGE ?= itisfoundation/ci-service-integration-library:REPLACE-EXACT-RELEASE-TAG
OSPARC_MOUNT       ?= /repo

# canonical tool runner: one pinned image, one mount convention, host uid mapping
# (single-line define: safe to expand inside multi-line recipes/shell constructs)
define osparc-tools
docker run -i --rm -v $(PWD):$(OSPARC_MOUNT) -u $(shell id -u):$(shell id -g) $(OSPARC_TOOLS_IMAGE) sh -c "cd $(OSPARC_MOUNT) && $(1)"
endef

.PHONY: osparc-create-run-script osparc-compose-spec osparc-version

osparc-create-run-script: ## regenerate metadata-derived run scripts for $(OSPARC_SERVICES)
	@for svc in $(OSPARC_SERVICES); do \
		echo "==> run-creator $$svc"; \
		$(call osparc-tools,ooil run-creator --runscript $$svc/service.cli/run --metadata .osparc/$$svc/metadata.yml) || exit 1; \
	done

osparc-compose-spec: ## assemble the build compose spec from .osparc metadata
	@$(call osparc-tools,ooil compose)

# usage: make osparc-version bump=patch cfg=.bumpversion.cfg
osparc-version: ## bump a version track inside the pinned tools image
	@test -n "$(bump)" && test -n "$(cfg)" || { echo "usage: make osparc-version bump=<major|minor|patch> cfg=<bumpversion.cfg>"; exit 1; }
	@$(call osparc-tools,bump2version --verbose --list --config-file $(cfg) $(bump))
