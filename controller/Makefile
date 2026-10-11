CONTROLLER_GEN_VERSION ?= v0.22.0
CONTROLLER_GEN ?= go run sigs.k8s.io/controller-tools/cmd/controller-gen@$(CONTROLLER_GEN_VERSION)
CRD_DIR := deploy/helm/cryptanalysis-operator/crds
IMAGE ?= ghcr.io/aburan28/cryptanalysis-campaign-controller
TAG ?= dev

.PHONY: all generate verify-generate build test vet fmt-check helm image

all: generate build test

generate:
	$(CONTROLLER_GEN) object paths=./api/...
	$(CONTROLLER_GEN) crd:crdVersions=v1 paths=./api/... output:crd:dir=$(CRD_DIR)

verify-generate: generate
	@git diff --exit-code -- api $(CRD_DIR) || \
	  { echo "generated files are stale; run make generate" >&2; exit 1; }

build:
	go build ./...

vet:
	go vet ./...

fmt-check:
	@unformatted=$$(gofmt -l .); \
	  if [ -n "$$unformatted" ]; then echo "gofmt needed:" $$unformatted >&2; exit 1; fi

test:
	go test -race -count=1 ./...

helm:
	./deploy/helm/check.sh

image:
	docker build -t $(IMAGE):$(TAG) .
