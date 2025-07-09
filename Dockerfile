FROM ubuntu:24.04

LABEL maintainer="neagu@itis.swiss"
LABEL org.opencontainers.image.authors="neagu@itis.swiss"
LABEL org.opencontainers.image.source="https://github.com/ITISFoundation/ci-service-integration-library"
LABEL org.opencontainers.image.licenses="MIT"

#Set of all dependencies needed for pyenv to work on Ubuntu
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    make \
    build-essential \
    libssl-dev \
    zlib1g-dev \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    wget \
    ca-certificates \
    curl \
    llvm \
    libncurses5-dev \
    xz-utils \
    tk-dev \
    libxml2-dev \
    libxmlsec1-dev \
    libffi-dev \
    liblzma-dev \
    mecab-ipadic-utf8 \
    gnupg \
    lsb-release \
    git \
    jq

# NOTE: keep in sync with the version installed in the dynamic-sidecar
ARG UBUNTU_DOCKER_VERSION=5:28.2.0-1~ubuntu.24.04~noble
# install Docker
RUN apt-get update && \
    apt-get install ca-certificates curl && \
    install -m 0755 -d /etc/apt/keyrings && \
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc && \
    chmod a+r /etc/apt/keyrings/docker.asc && \
    echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
    $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | \
    tee /etc/apt/sources.list.d/docker.list > /dev/null && \
    apt-get update && \
    apt-get install -y docker-ce=$UBUNTU_DOCKER_VERSION docker-ce-cli=$UBUNTU_DOCKER_VERSION containerd.io docker-buildx-plugin && \
    docker --version && \
    docker compose version


# Set-up necessary Env vars for PyEnv

ENV PYENV_ROOT="/pyenv-root"
ENV PATH=$PYENV_ROOT/shims:$PYENV_ROOT/bin:$PATH
ARG PYTHON_VERSION="3.11.9"


# Install pyenv
RUN set -ex && \
    curl https://pyenv.run | bash && \
    eval "$(pyenv init -)" && \
    pyenv update && \
    pyenv install ${PYTHON_VERSION} && \
    pyenv global ${PYTHON_VERSION} && \
    pyenv rehash && \
    python --version
RUN chmod 777 /pyenv-root

ARG REPO_NAME="https://github.com/GitHK/osparc-simcore-forked.git"
ARG BRANCH_NAME="pr-osparc-upgrade-ooil"
ARG COMMIT_SHA="62091dd5b97eebae25bfc5c1fdfdcb425d2df8eb"
ARG CLONE_DIR="/osparc"

# cloning and installing ooil
RUN git clone -n ${REPO_NAME} ${CLONE_DIR} && \
    cd ${CLONE_DIR} && \
    git checkout -B ${BRANCH_NAME} ${COMMIT_SHA} && \
    # install ooil and requirements
    cd ${CLONE_DIR}/packages/service-integration && \
    pip install --upgrade pip uv && \
    uv pip sync --system requirements/prod.txt && \
    pip install --no-cache-dir . && \
    cd / && \
    # remove source directory
    rm -rf ${CLONE_DIR} && \
    # check it is working
    ooil --version

# Install this repo's tooling for managing and pushing images
ARG INSTALL_DIR="/package-install-dir"
COPY ./ ${INSTALL_DIR}
RUN cd ${INSTALL_DIR} && \
    pip install . && \
    cd / && \
    rm -rf ${INSTALL_DIR} && \
    dpos --version