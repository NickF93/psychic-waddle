#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH='' cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/_common.sh"

"$SCRIPT_DIR/public-down.sh"
remove_docker_image portfolio-rag-assistant:local
remove_docker_image portfolio-rag-certbot:local

info "public cleanup removed runtime containers and local API/Certbot images only"
info "database, model, certificate, ACME, and Let's Encrypt work volumes were preserved"
