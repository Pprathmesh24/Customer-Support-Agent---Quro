from openai import AsyncOpenAI
from supabase import Client

from app.core.settings import settings

EMBEDDING_MODEL = "text-embedding-3-small"
_EMBED_BATCH_SIZE = 100   # OpenAI limit is 2048; 100 keeps requests small
_INSERT_BATCH_SIZE = 50   # PostgREST practical row limit per request


async def embed_and_store(
    chunks: list[str],
    document_id: str,
    supabase: Client,
    page_numbers: list[int | None] | None = None,
) -> int:
    openai_client = AsyncOpenAI(api_key=settings.openai_api_key)

    all_embeddings: list[list[float]] = []
    for i in range(0, len(chunks), _EMBED_BATCH_SIZE):
        batch = chunks[i : i + _EMBED_BATCH_SIZE]
        response = await openai_client.embeddings.create(model=EMBEDDING_MODEL, input=batch)
        all_embeddings.extend([item.embedding for item in response.data])

    # pgvector expects the vector as a bracketed comma-separated string via PostgREST
    rows = [
        {
            "document_id": document_id,
            "content": chunk,
            "embedding": "[" + ",".join(str(v) for v in embedding) + "]",
            "chunk_index": idx,
            "page_number": page_numbers[idx] if page_numbers else None,
        }
        for idx, (chunk, embedding) in enumerate(zip(chunks, all_embeddings))
    ]

    for i in range(0, len(rows), _INSERT_BATCH_SIZE):
        supabase.table("document_chunks").insert(rows[i : i + _INSERT_BATCH_SIZE]).execute()

    return len(chunks)
