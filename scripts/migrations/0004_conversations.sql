CREATE TABLE IF NOT EXISTS conversations (
    id         UUID NOT NULL,
    tenant     TEXT NOT NULL,
    title      TEXT NOT NULL,
    turns      JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant, id)
);

CREATE INDEX IF NOT EXISTS conversations_tenant_updated_idx
    ON conversations (tenant, updated_at DESC);
