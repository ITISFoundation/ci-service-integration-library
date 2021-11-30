FROM nvidia/cudagl:10.2-runtime-ubuntu18.04

LABEL org.opencontainers.image.authors="neagu@itis.swiss"
LABEL org.opencontainers.image.source="https://github.com/ITISFoundation/ci-service-integration-library"
LABEL org.opencontainers.image.licenses="MIT"

ARG REPO_NAME="https://github.com/GitHK/osparc-simcore-forked.git"
ARG BRANCH_NAME="service-integration-library-additions"
ARG COMMIT_SHA="a2413944443f03074866d23172b32249140bd288"
ARG CLONE_DIR="/opsarc"
ARG PYTHON_VERSION="3.8.10"
ARG DEBIAN_FRONTEND=noninteractive

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
    git

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
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements/prod.txt && \
    pip install --no-cache-dir . && \
    cd / && \
    # remove source directory
    rm -rf ${CLONE_DIR} && \
    # check it is working
    ooil --version
