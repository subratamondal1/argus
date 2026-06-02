CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS chunks (
    id              BIGSERIAL PRIMARY KEY,
    corpus          TEXT        NOT NULL DEFAULT 'default',
    corpus_version  TEXT        NOT NULL DEFAULT 'v1',
    source_uri      TEXT        NOT NULL,
    content         TEXT        NOT NULL,
    embedding       vector(768),
    tsv             tsvector,
    embedding_model TEXT        NOT NULL DEFAULT 'ollama/nomic-embed-text',
    metadata        JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw
    ON chunks USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS chunks_tsv_gin
    ON chunks USING gin (tsv);

CREATE INDEX IF NOT EXISTS chunks_corpus_idx
    ON chunks (corpus, corpus_version);
