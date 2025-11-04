# syntax=docker/dockerfile:1

# Define arguments in the global scope
ARG PYTHON_VERSION="3.11.9"
ARG UV_VERSION="0.9"
ARG UBUNTU_VERSION="24.04"
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv_build

FROM python:${PYTHON_VERSION}-slim-bookworm AS base
LABEL maintainer="neagu@itis.swiss"
LABEL org.opencontainers.image.authors="neagu@itis.swiss"
LABEL org.opencontainers.image.source="https://github.com/ITISFoundation/ci-service-integration-library"
LABEL org.opencontainers.image.licenses="MIT"


# Sets utf-8 encoding for Python et al
ENV LANG=C.UTF-8

# Turns off writing .pyc files; superfluous on an ephemeral container.
ENV PYTHONDONTWRITEBYTECODE=1 \
    VIRTUAL_ENV=/home/scu/.venv

# Ensures that the python and pip executables used in the image will be
# those from our virtualenv.
ENV PATH="${VIRTUAL_ENV}/bin:$PATH"

# install UV https://docs.astral.sh/uv/guides/integration/docker/#installing-uv
COPY --from=uv_build /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
ENV PATH=/root/.local/bin:$PATH

# NOTE: python virtualenv is used here such that installed
# packages may be moved to production image easily by copying the venv
RUN uv venv "${VIRTUAL_ENV}"

FROM base AS ooil-installer


ARG OSPARC_SIMCORE_REPO_URL="https://github.com/ITISFoundation/osparc-simcore"
ARG COMMIT_SHA="acb9f05531601fc71871197d8e855b9402d1b8ec"


# install ooil we need git to install from git repos
RUN --mount=type=cache,target=/var/cache/apt,sharing=private \
    set -eux \
    && apt-get update \
    && apt-get install --assume-yes --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*


RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install \
    git+${OSPARC_SIMCORE_REPO_URL}@${COMMIT_SHA}#subdirectory=packages/service-integration \
    git+${OSPARC_SIMCORE_REPO_URL}@${COMMIT_SHA}#subdirectory=packages/models-library \
    git+${OSPARC_SIMCORE_REPO_URL}@${COMMIT_SHA}#subdirectory=packages/common-library \
    && ooil --version




FROM base AS runtime

# Starting from clean base image, copies pre-installed virtualenv from prod-only-deps
COPY --from=ooil-installer  ${VIRTUAL_ENV} ${VIRTUAL_ENV}

# ooil special ENV
ENV ENABLE_OOIL_OSPARC_VARIABLE_IDENTIFIER=1

# install docker
RUN --mount=type=cache,target=/var/cache/apt,sharing=private \
    set -eux \
    && apt-get update \
    && apt-get install --assume-yes --no-install-recommends \
    ca-certificates \
    curl \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc \
    && chmod a+r /etc/apt/keyrings/docker.asc \
    && VERSION_CODENAME="$(. /etc/os-release && echo $VERSION_CODENAME)" \
    && printf "Types: deb\nURIs: https://download.docker.com/linux/debian\nSuites: %s\nComponents: stable\nSigned-By: /etc/apt/keyrings/docker.asc\n" "$VERSION_CODENAME" > /etc/apt/sources.list.d/docker.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
    docker-ce-cli \
    docker-compose-plugin \
    && apt-get remove -y curl \
    && rm -rf /var/lib/apt/lists/*

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=.,target=/src/,rw \
    uv pip install \
    /src/ \
    && dpos --version