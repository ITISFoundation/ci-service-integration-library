SHELL = /bin/sh
.DEFAULT_GOAL := help

IMAGE_NAME := itisfoundation/ci-service-integration-library

.PHONY: help
help: ## this colorful help
	@echo "Recipes for '$(notdir $(CURDIR))':"
	@echo ""
	@awk --posix 'BEGIN {FS = ":.*?## "} /^[[:alpha:][:space:]_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""

# ENVIRON ----------------------------------
.PHONY: update-requirements
update-requirements: ## upgrades requirements.txt
	# freezes requirements
	pip-compile --upgrade --build-isolation --output-file requirements/_base.txt requirements/_base.in
	pip-compile --upgrade --build-isolation --output-file requirements/_test.txt requirements/_test.in
	pip-compile --upgrade --build-isolation --output-file requirements/_tools.txt requirements/_tools.in

.PHONY: devenv
.venv:
	python3 -m venv $@
	# upgrading package managers
	$@/bin/pip3 install --upgrade \
		pip \
		wheel \
		setuptools
	# tooling
	$@/bin/pip3 install pip-tools


devenv: .venv ## create a python virtual environment with tools to dev, run and tests cookie-cutter
	# installing tooling and this package in editable mode
	pip-sync requirements/_tools.txt
	pip install -e .
	# your dev environment contains
	@$</bin/pip3 list
	@echo "To activate the virtual environment, run 'source $</bin/activate'"

.PHONY: .env-make
.env-make:	## assembles the .env file for testing
	@rm -f .env
	@cp .env-devel .env

.PHONY: codestyle
codestyle: ## fix import and format
	isort src/
	black src/

.PHONY: clean clean-force
git_clean_args = -dxf -e .vscode/ -e .venv
clean: ## cleans all unversioned files in project and temp files create by this makefile
	# Cleaning unversioned
	@git clean -n $(git_clean_args)
	@echo -n "Are you sure? [y/N] " && read ans && [ $${ans:-N} = y ]
	@echo -n "$(shell whoami), are you REALLY sure? [y/N] " && read ans && [ $${ans:-N} = y ]
	@git clean $(git_clean_args)


# REPO ----------------------------------

.PHONY:
run-dev: ## starts the script for development
	make build
	docker run -it --rm \
	-v /var/run/docker.sock:/var/run/docker.sock \
	-v $(PWD)/config.yaml:/tmp/config.yaml \
	-e REGISTRY_SPEAG_COM_ADDRESS=${REGISTRY_SPEAG_COM_ADDRESS} \
	-e REGISTRY_SPEAG_COM_PASSWORD=${REGISTRY_SPEAG_COM_PASSWORD} \
	-e REGISTRY_SPEAG_COM_USER=${REGISTRY_SPEAG_COM_USER} \
	-e GITLAB_TOKEN=${GITLAB_TOKEN} \
	-e GITLAB_USER=${GITLAB_USER} \
	-e GITLAB_PASSWORD=${GITLAB_PASSWORD} \
	${IMAGE_NAME} \
	dpos /tmp/config.yaml

.PHONY: build
build:	## Builds current image
	docker build -t ${IMAGE_NAME} .

.PHONY: shell
shell:	## Start a shell in the built image
	docker run -it --rm \
	-u $(shell id -u):$(shell id -g) \
	-v /var/run/docker.sock:/var/run/docker.sock \
	-v $(PWD)/config.yaml:/tmp/config.yaml \
	-e REGISTRY_SPEAG_COM_ADDRESS=${REGISTRY_SPEAG_COM_ADDRESS} \
	-e REGISTRY_SPEAG_COM_PASSWORD=${REGISTRY_SPEAG_COM_PASSWORD} \
	-e REGISTRY_SPEAG_COM_USER=${REGISTRY_SPEAG_COM_USER} \
	-e GITLAB_TOKEN=${GITLAB_TOKEN} \
	-e GITLAB_USER=${GITLAB_USER} \
	-e GITLAB_PASSWORD=${GITLAB_PASSWORD} \
	${IMAGE_NAME} \
	/bin/bash

.PHONY: test-installs
test-installs:	## checks all required commands are present
	docker run -it --rm -u $(shell id -u):$(shell id -g) -v /var/run/docker.sock:/var/run/docker.sock ${IMAGE_NAME} python --version
	docker run -it --rm -u $(shell id -u):$(shell id -g) -v /var/run/docker.sock:/var/run/docker.sock ${IMAGE_NAME} docker --version
	docker run -it --rm -u $(shell id -u):$(shell id -g) -v /var/run/docker.sock:/var/run/docker.sock ${IMAGE_NAME} docker compose version
	docker run -it --rm -u $(shell id -u):$(shell id -g) -v /var/run/docker.sock:/var/run/docker.sock ${IMAGE_NAME} ooil --version
	docker run -it --rm -u $(shell id -u):$(shell id -g) -v /var/run/docker.sock:/var/run/docker.sock ${IMAGE_NAME} dpos --version
	docker run -it --rm -u $(shell id -u):$(shell id -g) -v /var/run/docker.sock:/var/run/docker.sock ${IMAGE_NAME} jq --version
	docker run -it --rm -u $(shell id -u):$(shell id -g) -v /var/run/docker.sock:/var/run/docker.sock ${IMAGE_NAME} yq --version
	docker run -it --rm -u $(shell id -u):$(shell id -g) -v /var/run/docker.sock:/var/run/docker.sock ${IMAGE_NAME} bump2version --help


.PHONY: new-release
new-release:	## starts a release, usage: `make new-release tag=TAG`
	@echo "Releasing: '${tag}'"
	git tag "${tag}"
	git push
	git push --tags
	@echo "Please open below link to finish the release"
	@echo "https://github.com/ITISFoundation/ci-service-integration-library/releases/new?tag=${tag}&title=Release%20${tag}"
	