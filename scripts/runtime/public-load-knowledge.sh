#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/_common.sh"

KNOWLEDGE_FILE=${PUBLIC_KNOWLEDGE_FILE:-"$ROOT_DIR/knowledge/profile.json"}

[ -f "$KNOWLEDGE_FILE" ] || fail "missing public knowledge file: $KNOWLEDGE_FILE"

case "$KNOWLEDGE_FILE" in
    "$ROOT_DIR"/knowledge/*) ;;
    *) fail "PUBLIC_KNOWLEDGE_FILE must point inside $ROOT_DIR/knowledge" ;;
esac

KNOWLEDGE_RELATIVE_PATH=${KNOWLEDGE_FILE#"$ROOT_DIR/knowledge/"}

run_index_embeddings() {
    EMBEDDING_BACKEND_VALUE=$(env_value EMBEDDING_BACKEND)
    case "$EMBEDDING_BACKEND_VALUE" in
        openai-compatible)
            compose run --rm api portfolio-rag-assistant knowledge index-embeddings
            ;;
        ollama)
            compose_profile ollama run --rm api portfolio-rag-assistant knowledge index-embeddings
            ;;
        llama-cpp)
            compose_profile llama-cpp run --rm api portfolio-rag-assistant knowledge index-embeddings
            ;;
        *)
            fail "unsupported EMBEDDING_BACKEND: $EMBEDDING_BACKEND_VALUE"
            ;;
    esac
}

compose run --rm --no-deps \
    --volume "$ROOT_DIR/knowledge:/knowledge:ro" \
    api portfolio-rag-assistant knowledge validate "/knowledge/$KNOWLEDGE_RELATIVE_PATH"

compose run --rm \
    --volume "$ROOT_DIR/knowledge:/knowledge:ro" \
    api portfolio-rag-assistant knowledge ingest "/knowledge/$KNOWLEDGE_RELATIVE_PATH"

run_index_embeddings
