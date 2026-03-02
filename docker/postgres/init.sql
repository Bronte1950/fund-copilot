-- Enable pgvector extension for vector similarity search
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify installation
DO $$
BEGIN
    RAISE NOTICE 'pgvector version: %',
        (SELECT extversion FROM pg_extension WHERE extname = 'vector');
END $$;
