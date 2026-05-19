from openai import AsyncOpenAI
from supabase import Client

_EMBEDDING_MODEL = "text-embedding-3-small"
_DEFAULT_THRESHOLD = 0.60
_DEFAULT_TTL_HOURS = 24


async def _embed(text: str, client: AsyncOpenAI) -> str:
    resp = await client.embeddings.create(model=_EMBEDDING_MODEL, input=text)
    vec = resp.data[0].embedding
    return "[" + ",".join(str(v) for v in vec) + "]"


class SemanticCache:
    """
    Full-response semantic cache keyed on user_id + query embedding.

    On a cache hit the chat route returns the stored LLM response immediately,
    skipping query rewriting, hybrid search, re-ranking, and LLM generation.
    On a cache miss the chat route calls this again after the agent responds
    to store the new (query, response) pair for future hits.

    Integrated into POST /chat at Step 6.1.
    """

    def __init__(
        self,
        supabase: Client,
        openai_client: AsyncOpenAI,
        similarity_threshold: float = _DEFAULT_THRESHOLD,
        ttl_hours: int = _DEFAULT_TTL_HOURS,
    ) -> None:
        self.supabase = supabase
        self.openai_client = openai_client
        self.similarity_threshold = similarity_threshold
        self.ttl_hours = ttl_hours

    async def check(self, query: str, user_id: str) -> str | None:
        """Returns a cached LLM response if a semantically similar query was answered recently."""
        embedding = await _embed(query, self.openai_client)
        result = self.supabase.rpc(
            "search_semantic_cache",
            {
                "p_user_id": user_id,
                "p_query_embedding": embedding,
                "similarity_threshold": self.similarity_threshold,
                "max_age_hours": self.ttl_hours,
            },
        ).execute()
        if result.data:
            hit = result.data[0]
            print(f"  [cache] HIT  similarity={hit['similarity']:.4f}")
            return str(hit["response"])
        print(f"  [cache] MISS")
        return None

    async def store(self, query: str, response: str, user_id: str) -> None:
        """Stores a query-response pair after the LLM generates a new answer."""
        embedding = await _embed(query, self.openai_client)
        self.supabase.table("semantic_cache").insert(
            {
                "user_id": user_id,
                "query_text": query,
                "query_embedding": embedding,
                "response": response,
            }
        ).execute()
        print(f"  [cache] stored: {query!r}")
