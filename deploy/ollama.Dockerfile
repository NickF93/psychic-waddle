# Keep the published application and runners: newer releases change embeddings.
# Rebuild the unmodified vendor source with the patched Go runtime.
FROM golang:1.26.10-bookworm@sha256:632dff7351799a5a9954a48dc06670ade72ee44e8c351cdc0e5a57af2fea21af AS build
WORKDIR /src
ARG GOFLAGS
ADD --checksum=sha256:f344a4b3768b8ec3e64a15a370381eba75f27315300568c8070862dd666175ba https://api.github.com/repos/ollama/ollama/tarball/c28ddc0a7b273cd286b680a6db0bef0c17bc0ec0 /tmp/ollama.tar.gz
RUN tar --strip-components=1 -xzf /tmp/ollama.tar.gz -C /src \
    && CGO_ENABLED=1 go build -mod=readonly -trimpath -buildmode=pie \
        -ldflags='-w -s -X=github.com/ollama/ollama/version.Version=0.24.0' \
        -o /out/ollama .
RUN go version -m /out/ollama

FROM ollama/ollama:0.24.0@sha256:a6149234667efc71d37766d61c1a16f24c33e4cd7a0bf4125c44a7e47e2419c4
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /out/ollama /usr/bin/ollama
COPY --from=build /usr/local/go/LICENSE /usr/share/doc/ollama/GO_RUNTIME_LICENSE
