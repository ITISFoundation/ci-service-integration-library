FROM nvidia/cudagl:10.2-runtime-ubuntu18.04

LABEL maintainer="neagu@itis.swiss"
LABEL org.opencontainers.image.authors="neagu@itis.swiss"
LABEL org.opencontainers.image.source="https://github.com/ITISFoundation/ci-service-integration-library"
LABEL org.opencontainers.image.licenses="MIT"

ARG REPO_NAME="https://github.com/ITISFoundation/osparc-simcore.git"
ARG BRANCH_NAME="master"
ARG COMMIT_SHA="71e5513b67b7050ef5f001583723537d13d4f9ad"
ARG CLONE_DIR="/osparc"
ARG PYTHON_VERSION="3.10.10"
ARG DEBIAN_FRONTEND=noninteractive
ARG DOCKER_COMPOSE_VERSION="1.29.2"
ARG INSTALL_DIR="/package-install-dir"
# NOTE: keep in sync with the version installed in the dynamic-sidecar
ARG DOCKER_COMPOSE_VERSION="2.20.2"

# Fixes issues with nvidia keys suddenly gone missing
# TODO: check if can be removed
RUN apt-key adv --fetch-keys https://developer.download.nvidia.com/compute/cuda/repos/ubuntu1804/x86_64/3bf863cc.pub 18
RUN apt-key adv --fetch-keys https://developer.download.nvidia.com/compute/machine-learning/repos/ubuntu1804/x86_64/7fa2af80.pub

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

# install Docker
RUN curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg && \
    echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
    $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    docker-ce \
    containerd.io \
    docker-ce-cli && \
    mkdir -p /usr/local/lib/docker/cli-plugins && \
    curl -SL https://github.com/docker/compose/releases/download/v${DOCKER_COMPOSE_VERSION}/docker-compose-linux-x86_64 -o /usr/local/lib/docker/cli-plugins/docker-compose && \
    chmod +x /usr/local/lib/docker/cli-plugins/docker-compose && \
    docker --version && \
    docker compose version


# Set-up necessary Env vars for PyEnv
ENV PYENV_ROOT="/root/.pyenv"
ENV PATH=$PYENV_ROOT/shims:$PYENV_ROOT/bin:$PATH
# Install pyenv
RUN set -ex && \
    curl https://pyenv.run | bash && \
    pyenv update && \
    pyenv install ${PYTHON_VERSION} && \
    pyenv virtualenv ${PYTHON_VERSION} venv && \
    pyenv global venv && \
    pyenv rehash && \
    python --version

# cloning and installing ooil
RUN git clone -n ${REPO_NAME} ${CLONE_DIR} && \
    cd ${CLONE_DIR} && \
    git checkout -B ${BRANCH_NAME} ${COMMIT_SHA} && \
    # install ooil and requirements
    cd ${CLONE_DIR}/packages/service-integration && \
    pip install uv && \
    uv pip sync requirements/prod.txt && \
    pip install --no-cache-dir . && \
    cd / && \
    # remove source directory
    rm -rf ${CLONE_DIR} && \
    # check it is working
    ooil --version

# Install this repo's tooling for managing and pushing images
COPY ./ ${INSTALL_DIR}
RUN cd ${INSTALL_DIR} && \
    pip install . && \
    cd / && \
    rm -rf ${INSTALL_DIR} && \
    dpos --version