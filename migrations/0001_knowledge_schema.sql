CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE sources (
    id bigserial PRIMARY KEY,
    source_uri text NOT NULL,
    title text NOT NULL,
    reviewed_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT sources_source_uri_not_blank CHECK (length(btrim(source_uri)) > 0),
    CONSTRAINT sources_title_not_blank CHECK (length(btrim(title)) > 0),
    CONSTRAINT sources_source_uri_unique UNIQUE (source_uri)
);

CREATE TABLE facts (
    id bigserial PRIMARY KEY,
    source_id bigint NOT NULL REFERENCES sources(id) ON DELETE RESTRICT,
    category text NOT NULL,
    fact_text text NOT NULL,
    source_locator text,
    public_visible boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT facts_category_allowed CHECK (
        category IN (
            'experience',
            'education',
            'projects',
            'research',
            'skills',
            'contact'
        )
    ),
    CONSTRAINT facts_fact_text_not_blank CHECK (length(btrim(fact_text)) > 0),
    CONSTRAINT facts_source_locator_not_blank CHECK (
        source_locator IS NULL OR length(btrim(source_locator)) > 0
    ),
    CONSTRAINT facts_source_category_text_unique UNIQUE (
        source_id,
        category,
        fact_text
    )
);

CREATE TABLE chunks (
    id bigserial PRIMARY KEY,
    source_id bigint NOT NULL REFERENCES sources(id) ON DELETE RESTRICT,
    category text NOT NULL,
    chunk_index integer NOT NULL,
    chunk_text text NOT NULL,
    source_locator text,
    public_visible boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chunks_category_allowed CHECK (
        category IN (
            'experience',
            'education',
            'projects',
            'research',
            'skills',
            'contact'
        )
    ),
    CONSTRAINT chunks_chunk_index_non_negative CHECK (chunk_index >= 0),
    CONSTRAINT chunks_chunk_text_not_blank CHECK (length(btrim(chunk_text)) > 0),
    CONSTRAINT chunks_source_locator_not_blank CHECK (
        source_locator IS NULL OR length(btrim(source_locator)) > 0
    ),
    CONSTRAINT chunks_source_index_unique UNIQUE (source_id, chunk_index)
);

CREATE TABLE chunk_embeddings (
    id bigserial PRIMARY KEY,
    chunk_id bigint NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    embedding_backend text NOT NULL,
    embedding_model text NOT NULL,
    embedding_dimension integer NOT NULL,
    embedding vector NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chunk_embeddings_backend_allowed CHECK (
        embedding_backend IN (
            'ollama',
            'llama-cpp',
            'openai-compatible'
        )
    ),
    CONSTRAINT chunk_embeddings_model_not_blank CHECK (
        length(btrim(embedding_model)) > 0
    ),
    CONSTRAINT chunk_embeddings_dimension_positive CHECK (embedding_dimension > 0),
    CONSTRAINT chunk_embeddings_dimension_matches_vector CHECK (
        vector_dims(embedding) = embedding_dimension
    ),
    CONSTRAINT chunk_embeddings_chunk_backend_model_unique UNIQUE (
        chunk_id,
        embedding_backend,
        embedding_model
    )
);

CREATE INDEX facts_source_id_idx ON facts(source_id);
CREATE INDEX chunks_source_id_idx ON chunks(source_id);
CREATE INDEX chunk_embeddings_chunk_id_idx ON chunk_embeddings(chunk_id);
