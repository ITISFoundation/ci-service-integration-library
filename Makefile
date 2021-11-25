.PHONY: build
build:	## Builds current image
	docker build -t dockerhub-service-integrationlibrary .

.PHONY: shell
shell:	## Builds current image
	docker run -it --rm -v /var/run/docker.sock:/var/run/docker.sock dockerhub-service-integrationlibrary /bin/sh