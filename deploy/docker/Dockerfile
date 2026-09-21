# Two images from one tree: the coordinator (Go) and the agent (C).
#
# Build both:
#   docker build -f deploy/docker/Dockerfile --target coordinator -t ca-coordinator:dev .
#   docker build -f deploy/docker/Dockerfile --target agent       -t ca-agent:dev .
#
# The build context is the repository root, because both binaries
# compile the C sources from src/: the Go coordinator links the library
# through cgo so that the job, the verification and the merge are the
# same code an agent runs, in one implementation.

# ---- the coordinator -------------------------------------------------------
FROM golang:1.23-bookworm AS build-coordinator
WORKDIR /src
COPY . .
WORKDIR /src/bindings/go
# cgo is required: the package compiles ../../src/*.c.  Static linking
# keeps the runtime image at a distroless base with no libc surprises.
ENV CGO_ENABLED=1
RUN go build -trimpath -ldflags="-s -w -extldflags=-static" \
        -tags osusergo,netgo \
        -o /out/ca-coordinator ./cmd/ca-coordinator

FROM gcr.io/distroless/static-debian12:nonroot AS coordinator
COPY --from=build-coordinator /out/ca-coordinator /usr/local/bin/ca-coordinator
# 8080 is the service port; /healthz on it needs no token.
EXPOSE 8080
USER nonroot:nonroot
ENTRYPOINT ["/usr/local/bin/ca-coordinator"]

# ---- the agent -------------------------------------------------------------
FROM debian:bookworm-slim AS build-agent
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential cmake ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY . .
RUN cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DCA_BUILD_TESTS=OFF -DCA_BUILD_SHARED=OFF \
    && cmake --build build -j"$(nproc)" --target ca

FROM debian:bookworm-slim AS agent
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --uid 65532 --create-home --home-dir /var/lib/ca ca
COPY --from=build-agent /src/build/ca /usr/local/bin/ca
WORKDIR /var/lib/ca
USER 65532:65532
# An agent opens every connection it uses and listens on nothing, so this
# image needs no EXPOSE and no inbound rule anywhere.
ENTRYPOINT ["/usr/local/bin/ca"]
CMD ["work"]
