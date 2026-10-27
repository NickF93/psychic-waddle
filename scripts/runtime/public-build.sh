#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH='' cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/_common.sh"

"$SCRIPT_DIR/nginx-validate.sh"
"$SCRIPT_DIR/api-build.sh"
compose_profile public-tls build certbot
if [ "$(env_value CHAT_BACKEND)" = ollama ] \
    || [ "$(env_value EMBEDDING_BACKEND)" = ollama ] \
    || [ "$(optional_env_value CHAT_FALLBACK_BACKEND)" = ollama ]; then
    compose_profile ollama build ollama
fi
