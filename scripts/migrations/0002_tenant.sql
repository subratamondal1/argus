ALTER TABLE chunks ADD COLUMN IF NOT EXISTS tenant TEXT NOT NULL DEFAULT 'public';

CREATE INDEX IF NOT EXISTS chunks_tenant_corpus_idx
    ON chunks (tenant, corpus, corpus_version);
