# !!! WARNING

Only use released versions in the CI's. Each time a new release is created the `latest` tag on Docker Hub is updated.
See [published releases here](https://hub.docker.com/r/itisfoundation/ci-service-integration-library/tags)

# ci-service-integration-library

Bundles tooling required for building validating and releasing osparc services:
- [ooil](https://github.com/ITISFoundation/osparc-simcore/tree/master/packages/service-integration) used to generate `.osparc` configuration and produce `docker-compose.y*ml` specs
- **dpos** (docker-publisher-osparc-services) used in CI workflow to monitor validate and publish osparc services by monitoring their repositories.

**Warnings:**
- current version of ooil is build and released form a PR
- while using experimental and PR features make sure to tag the releases with `-dev` suffix

# How to release a new image

**NOTE:** Make sure all your changes have been **committed**!

Create a tag with the following format `v(OOIL-VERSION)[-dev]` where:
- `(OOIL-VERSION)` is the current version of the [ITISFoundation/osparc-simcore/tree/master/packages/service-integration](https://github.com/ITISFoundation/osparc-simcore/tree/master/packages/service-integration)
- `[-dev]` is added if you are building from a fork or for development testing reasons
- use `make new-release tag=TAG_NAME` to tag and push all latest changes and create a release link.
- click on the release link, open it and add the description for the release
- inside the actions tab you will see a new build
- check out [Docker Hub](https://hub.docker.com/r/itisfoundation/ci-service-integration-library/tags) fort the new tag and updated `latest` tag




# docker-publisher-osparc-services

Used to monitor osparc services managed by ooil.
When a monitored github repository has a passing CI it will:
- build a new image
- test it and
- push it to a deployment registry
