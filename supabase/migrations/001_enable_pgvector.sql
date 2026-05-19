-- Enable the pgvector extension so Postgres can store and query vector embeddings.
-- Must run before any table that has a vector() column is created.
CREATE EXTENSION IF NOT EXISTS vector;
