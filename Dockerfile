FROM docker:20.10.11

LABEL org.opencontainers.image.authors="neagu@itis.swiss"

ARG REPO_NAME="https://github.com/GitHK/osparc-simcore-forked.git"
ARG BRANCH_NAME="service-integration-library-additions"
ARG COMMIT_SHA="a2413944443f03074866d23172b32249140bd288"
ARG CLONE_DIR="/opsarc"

# install & activate python virtuelenv
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
RUN apk add git python3 py3-pip docker-compose && \
    python3 -m venv $VIRTUAL_ENV && \
    # cloning and and selecting branch
    pip install --no-cache-dir --upgrade pip && \
    git clone -n ${REPO_NAME} ${CLONE_DIR} && \
    cd ${CLONE_DIR} && \
    git checkout -b ${BRANCH_NAME} ${COMMIT_SHA} && \
    # install ooil and requirements
    cd ${CLONE_DIR}/packages/service-integration && \
    pip install --no-cache-dir -r requirements/prod.txt && \
    pip install --no-cache-dir . && \
    cd / && \
    # remove source directory
    rm -rf ${CLONE_DIR} && \
    # check it is working
    ooil --version
