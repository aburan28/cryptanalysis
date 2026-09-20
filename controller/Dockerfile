FROM golang:1.26 AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOFLAGS=-trimpath go build -ldflags="-s -w" \
    -o /out/campaign-controller ./cmd/campaign-controller

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=build /out/campaign-controller /campaign-controller
USER 65532:65532
ENTRYPOINT ["/campaign-controller"]
