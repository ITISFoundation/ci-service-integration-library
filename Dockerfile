# syntax=docker/dockerfile:1

# Define arguments in the global scope
ARG PYTHON_VERSION="3.11.9"
ARG UV_VERSION="0.9"
ARG DEBIAN_DOCKER_VERSION=5:28.5.1-1~debian.12~bookworm
ARG DEBIAN_DOCKER_COMPOSE_VERSION=2.40.3-1~debian.12~bookworm
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv_build

FROM python:${PYTHON_VERSION}-slim-bookworm AS base
LABEL maintainer="neagu@itis.swiss"
LABEL org.opencontainers.image.authors="neagu@itis.swiss"
LABEL org.opencontainers.image.source="https://github.com/ITISFoundation/ci-service-integration-library"
LABEL org.opencontainers.image.licenses="MIT"

# for docker apt caching to work this needs to be added: [https://vsupalov.com/buildkit-cache-mount-dockerfile/]
RUN rm -f /etc/apt/apt.conf.d/docker-clean && \
    echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache

# Sets utf-8 encoding for Python et al
ENV LANG=C.UTF-8

# Turns off writing .pyc files; superfluous on an ephemeral container.
ENV PYTHONDONTWRITEBYTECODE=1 \
    VIRTUAL_ENV=/home/scu/.venv

# Ensures that the python and pip executables used in the image will be
# those from our virtualenv.
ENV PATH="${VIRTUAL_ENV}/bin:$PATH"

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
ENV PATH=/root/.local/bin:$PATH

# NOTE: python virtualenv is used here such that installed
# packages may be moved to production image easily by copying the venv
RUN --mount=from=uv_build,source=/uv,target=/bin/uv \
    uv venv "${VIRTUAL_ENV}"

FROM base AS ooil-installer

ARG OSPARC_SIMCORE_REPO_URL="https://github.com/ITISFoundation/osparc-simcore"
ARG COMMIT_SHA="de246e2c2ea177b5a05433e257f411a91f3db197"


# install ooil we need git to install from git repos
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    set -eux \
    && apt-get update \
    && apt-get install --assume-yes --no-install-recommends \
    git


RUN --mount=from=uv_build,source=/uv,target=/bin/uv \
    --mount=type=cache,target=/root/.cache/uv \
    uv pip install \
    git+${OSPARC_SIMCORE_REPO_URL}@${COMMIT_SHA}#subdirectory=packages/service-integration \
    git+${OSPARC_SIMCORE_REPO_URL}@${COMMIT_SHA}#subdirectory=packages/models-library \
    git+${OSPARC_SIMCORE_REPO_URL}@${COMMIT_SHA}#subdirectory=packages/common-library \
    && ooil --version




FROM base AS runtime
ARG DEBIAN_DOCKER_VERSION
ARG DEBIAN_DOCKER_COMPOSE_VERSION

# Copy ooil virtual environment from installer stage
COPY --from=ooil-installer  ${VIRTUAL_ENV} ${VIRTUAL_ENV}

# ooil special ENV for $$$$ variable substitution in osparc services
ENV ENABLE_OOIL_OSPARC_VARIABLE_IDENTIFIER=1

# install docker
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
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
    docker-ce-cli=${DEBIAN_DOCKER_VERSION} \
    docker-compose-plugin=${DEBIAN_DOCKER_COMPOSE_VERSION} \
    && apt-get remove -y curl

# install required depenendencies it seems we need jq??
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    set -eux \
    && apt-get update \
    && apt-get install --assume-yes --no-install-recommends \
    jq

# install dpos
RUN --mount=from=uv_build,source=/uv,target=/bin/uv \
    --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=.,target=/src/,rw \
    uv pip install \
    /src/ \
    && dpos --version