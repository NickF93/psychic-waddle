CREATE EXTENSION IF NOT EXISTS pgcrypto;

ALTER TABLE chunk_embeddings
    ADD COLUMN chunk_text_hash text;

UPDATE chunk_embeddings
SET chunk_text_hash = encode(
    digest(convert_to(chunks.chunk_text, 'UTF8'), 'sha256'),
    'hex'
)
FROM chunks
WHERE chunks.id = chunk_embeddings.chunk_id
  AND chunk_embeddings.chunk_text_hash IS NULL;

ALTER TABLE chunk_embeddings
    ALTER COLUMN chunk_text_hash SET NOT NULL;

ALTER TABLE chunk_embeddings
    ADD CONSTRAINT chunk_embeddings_text_hash_sha256 CHECK (
        chunk_text_hash ~ '^[0-9a-f]{64}$'
    );
