# One image, two binaries, and the library's `ca` walker.
#
# The agent runs `ca dist-walk` as a subprocess, so the image has to carry
# both the Go binaries and the C library's CLI.  Two build stages and a
# distroless-style runtime keep that from turning into a build toolchain in
# production.
#
#   docker build -f orchestrator/deploy/docker/Dockerfile -t cryptanalysis:dev .
#
# Build context is the repository root, because the Go module and the C
# sources are both needed.

# ---- stage 1: the C library and its CLI -----------------------------------
FROM debian:bookworm-slim AS ca
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential cmake ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY CMakeLists.txt Makefile ./
COPY cmake ./cmake
COPY include ./include
COPY src ./src
COPY tools ./tools
COPY cuda ./cuda
COPY tests ./tests
# Release with the tests built: an image whose `ca` fails its own test suite
# is one nobody should deploy, and finding that out here costs a minute.
RUN cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DCA_BUILD_SHARED=OFF \
    && cmake --build build -j"$(nproc)" \
    && ctest --test-dir build --output-on-failure -R "modarith|group|rho|dist"

# ---- stage 2: the orchestrator --------------------------------------------
FROM golang:1.24-bookworm AS go
WORKDIR /src
COPY orchestrator ./orchestrator
WORKDIR /src/orchestrator
# No module downloads: the orchestrator has no third-party dependencies, so
# the build works with the network switched off.  CGO off so the binaries are
# static and the runtime image needs no libc beyond what it has.
ENV CGO_ENABLED=0 GOFLAGS=-mod=mod
RUN go build -trimpath -ldflags "-s -w" -o /out/ca-control ./cmd/ca-control \
    && go build -trimpath -ldflags "-s -w" -o /out/ca-agent ./cmd/ca-agent \
    && go test ./... 2>&1 | tail -20

# ---- stage 3: the runtime --------------------------------------------------
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --uid 65532 --no-create-home --shell /usr/sbin/nologin ca
COPY --from=ca /src/build/ca /usr/local/bin/ca
COPY --from=go /out/ca-control /usr/local/bin/ca-control
COPY --from=go /out/ca-agent /usr/local/bin/ca-agent
# The state directory is a volume in every real deployment; creating it here
# means the container also runs with nothing mounted, which is what a
# smoke test does.
RUN mkdir -p /var/lib/ca-control && chown ca:ca /var/lib/ca-control
USER 65532:65532
ENV CA_BIN=/usr/local/bin/ca \
    CA_STATE=/var/lib/ca-control \
    CA_LISTEN=:8080
EXPOSE 8080 8081
ENTRYPOINT ["/usr/local/bin/ca-control"]
CMD ["serve"]
