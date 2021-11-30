.PHONY: build
build:	## Builds current image
	docker build -t dockerhub-service-integrationlibrary .

.PHONY: shell
shell:	## Start a shell in the built image
	docker run -it --rm -v /var/run/docker.sock:/var/run/docker.sock dockerhub-service-integrationlibrary /bin/bash

.PHONY: tests
tests:	## Tests the current build
	docker run -it --rm -v /var/run/docker.sock:/var/run/docker.sock dockerhub-service-integrationlibrary python --version
	docker run -it --rm -v /var/run/docker.sock:/var/run/docker.sock dockerhub-service-integrationlibrary ooil --version
	docker run -it --rm -v /var/run/docker.sock:/var/run/docker.sock dockerhub-service-integrationlibrary docker --version
	docker run -it --rm -v /var/run/docker.sock:/var/run/docker.sock dockerhub-service-integrationlibrary docker-compose --version