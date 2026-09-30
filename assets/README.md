# Shared service assets

`sc-entrypoint.sh` is the approved computational-service entrypoint contract
(SPEC-COMP C15/C16/C17): mount validation, UID/GID reconciliation against the
mounted input folder, image traversal for files owned by the build-time service
UID (`fdfind`, `/proc` and `/sys` excluded), pre-existing UID-conflict removal,
and `exec gosu` handoff as `$SC_USER_NAME`.

Consuming service images:

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends gosu fd-find \
    && rm -rf /var/lib/apt/lists/*
COPY --from=itisfoundation/ci-service-integration-library:<pinned-release-tag> \
     /opt/service-integration/assets/sc-entrypoint.sh docker/entrypoint.sh
ENTRYPOINT [ "/bin/sh", "docker/entrypoint.sh", "/bin/sh", "-c" ]
CMD ["run"]
```

Requirements (all per the Sleeper reference contract):

- `gosu` and `fd-find` (`fdfind`) installed in the image;
- `SC_USER_ID`, `SC_USER_NAME`, `INPUT_FOLDER`, `OUTPUT_FOLDER` envs set;
- keep the `"/bin/sh", "-c"` ENTRYPOINT tail (or guarantee the invoked command
  is kernel-exec-able): generated `service.cli/run` files start with a blank
  line, and the tail's `sh` fallback is what executes them — a bare
  `exec gosu "$@ run"` dies with ENOEXEC (T26me finding);
- pin the library image to an exact released tag (V10).

## Shared Makefile machinery (`Makefile.mk`)

`Makefile.mk` is the inherited make surface (SPEC-COMP T22rs): the canonical
`osparc-tools` docker-run wrapper (one pinned image, one mount convention,
host uid mapping) plus `osparc-create-run-script`, `osparc-compose-spec`, and
`osparc-version` targets, replacing the per-repository copies that currently
differ only in their image tag and mount name.

Bootstrap a consumer Makefile with (fragment extracted from the same pinned
image as the entrypoint asset, so pinning stays V10-clean):

```makefile
OSPARC_TOOLS_MK := .osparc-tools.mk
$(OSPARC_TOOLS_MK):
	docker run --rm --entrypoint cat <pinned-release-tag-image> \
	    /opt/service-integration/assets/Makefile.mk > $@
-include $(OSPARC_TOOLS_MK)

OSPARC_TOOLS_IMAGE := <same pinned release tag>
OSPARC_SERVICES    := <svc-a> <svc-b>
create-run-script: osparc-create-run-script
compose-spec:      osparc-compose-spec
```

