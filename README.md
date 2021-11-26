# About

Builds and releases ooil as a docker image:
- current version is build and released form a PR
- while using experimental and PR features make sure to tag the releases with `-dev` suffix

# How to release a new image

Create a tag with the following format `v(OOIL-VERSION)[-dev]` where:
- `(OOIL-VERSION)` is the current version of the [ITISFoundation/osparc-simcore/tree/master/packages/service-integration](https://github.com/ITISFoundation/osparc-simcore/tree/master/packages/service-integration)
- `[-dev]` is added if you are building from a fork or for development testing reasons
- go to the releases page and create a new release form the new tag
- inside the actions tab you will see a new build
- check out [Docker Hub](https://hub.docker.com/r/itisfoundation/ci-service-integration-library/tags) fort the new tag and updated `latest` tag

# WARNING

Only use released versions in the CI's. Each time a new release is created the `latest` tag on Docker Hub is updated.
See [published releases here](https://hub.docker.com/r/itisfoundation/ci-service-integration-library/tags)