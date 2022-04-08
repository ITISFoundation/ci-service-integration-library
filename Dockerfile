FROM nvidia/cudagl:10.2-runtime-ubuntu18.04

LABEL maintainer="neagu@itis.swiss"
LABEL org.opencontainers.image.authors="neagu@itis.swiss"
LABEL org.opencontainers.image.source="https://github.com/ITISFoundation/ci-service-integration-library"
LABEL org.opencontainers.image.licenses="MIT"

ARG REPO_NAME="https://github.com/GitHK/osparc-simcore-forked.git"
ARG BRANCH_NAME="service-integration-library-additions"
ARG COMMIT_SHA="62146708e34969262445a7d0bf409b04b0df6397"
ARG CLONE_DIR="/opsarc"
ARG PYTHON_VERSION="3.8.10"
ARG DEBIAN_FRONTEND=noninteractive
ARG DOCKER_COMPOSE_VERSION="1.29.2"
ARG INSTALL_DIR="/package-install-dir"

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
    git

# install Docker
RUN curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg && \
    echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
    $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null && \
    apt-get update && \
    apt-get install -y docker-ce docker-ce-cli containerd.io


# Set-up necessary Env vars for PyEnv
ENV PYENV_ROOT="$HOME/.pyenv"
ENV PATH $PYENV_ROOT/shims:$PYENV_ROOT/bin:$PATH
# Install pyenv
RUN set -ex && \
    curl https://pyenv.run | bash && \
    pyenv update && \
    pyenv install ${PYTHON_VERSION} && \
    pyenv global ${PYTHON_VERSION} && \
    pyenv rehash && \
    python --version

# cloning and installing ooil
RUN git clone -n ${REPO_NAME} ${CLONE_DIR} && \
    cd ${CLONE_DIR} && \
    git checkout -b ${BRANCH_NAME} ${COMMIT_SHA} && \
    # install ooil and requirements
    cd ${CLONE_DIR}/packages/service-integration && \
    pip install --no-cache-dir --upgrade pip docker-compose==${DOCKER_COMPOSE_VERSION} && \
    pip install --no-cache-dir -r requirements/prod.txt && \
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