import asyncio
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import BaseTool
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from sentence_transformers import CrossEncoder
from supabase import Client

EMBEDDING_MODEL = "text-embedding-3-small"
_HYBRID_CANDIDATES = 20
_EXACT_CANDIDATES = 10
_RERANK_TOP_K = 5

# Loaded once on first retrieval call — ~85 MB, no API cost.
_cross_encoder: CrossEncoder | None = None


def _get_cross_encoder() -> CrossEncoder:
    global _cross_encoder
    if _cross_encoder is None:
        _cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    return _cross_encoder


_ROUTER_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a query classifier for a document retrieval system. "
        "Classify the user query as one of:\n"
        "- exact_lookup: the user wants verbatim text, a specific error code, "
        "a section name, a clause number, or a precise term that must appear as-is.\n"
        "- semantic: the user wants an explanation, a summary, a how-to, or an "
        "answer where paraphrased content is acceptable.\n"
        "Respond with ONLY the label: exact_lookup or semantic.",
    ),
    ("human", "{query}"),
])

_REWRITER_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a search query optimizer for a customer support knowledge base. "
        "Rewrite the query to improve document retrieval by:\n"
        "- Expanding acronyms and abbreviations\n"
        "- Adding relevant domain context\n"
        "- Making implicit intent explicit\n"
        "Keep it concise (1-2 sentences). Respond with ONLY the rewritten query.",
    ),
    ("human", "{query}"),
])


async def _route_query(query: str, llm: ChatAnthropic) -> str:
    chain = _ROUTER_PROMPT | llm | StrOutputParser()
    label = (await chain.ainvoke({"query": query})).strip().lower()
    return label if label in {"exact_lookup", "semantic"} else "semantic"


async def _rewrite_query(query: str, llm: ChatAnthropic) -> str:
    chain = _REWRITER_PROMPT | llm | StrOutputParser()
    return (await chain.ainvoke({"query": query})).strip()


async def _embed(text: str, client: AsyncOpenAI) -> str:
    resp = await client.embeddings.create(model=EMBEDDING_MODEL, input=text)
    vec = resp.data[0].embedding
    return "[" + ",".join(str(v) for v in vec) + "]"


def _rerank(
    query: str,
    candidates: list[dict[str, Any]],
    top_k: int = _RERANK_TOP_K,
) -> list[dict[str, Any]]:
    if not candidates:
        return []
    encoder = _get_cross_encoder()
    pairs = [(query, c["content"]) for c in candidates]
    scores = encoder.predict(pairs)
    ranked = sorted(zip(scores, candidates), key=lambda x: x[0], reverse=True)
    return [c for _, c in ranked[:top_k]]


def _format_results(chunks: list[dict[str, Any]]) -> str:
    if not chunks:
        return "No relevant information found in the knowledge base."
    lines = [f"Found {len(chunks)} relevant chunk(s):\n"]
    for i, chunk in enumerate(chunks, start=1):
        page = f" (page {chunk['page_number']})" if chunk.get("page_number") else ""
        lines.append(f"[{i}] Source: {chunk['doc_name']}{page}")
        lines.append(chunk["content"])
        lines.append("")
    return "\n".join(lines)


class RetrieverInput(BaseModel):
    query: str = Field(description="The specific question or search phrase to look up")


class RetrieverTool(BaseTool):
    """
    Retrieves the most relevant document chunks for a query.

    Pipeline:
      1. Route: Haiku classifies query as exact_lookup or semantic.
      2. Exact path: BM25-only search via exact_search_chunks().
      3. Semantic path:
         a. Haiku rewrites the query (expands acronyms, adds context).
         b. OpenAI embeds the rewritten query.
         c. hybrid_search_chunks() merges HNSW cosine + BM25 via RRF (top 20).
         d. Cross-encoder re-ranks candidates → top 5.
    """

    name: str = "retriever"
    description: str = (
        "Searches the knowledge base for information relevant to a query. "
        "Use this to find answers in the uploaded product documentation. "
        "Returns the most relevant text chunks with source document and page number."
    )
    args_schema: type[BaseModel] = RetrieverInput
    supabase: Client = Field(exclude=True)
    llm: ChatAnthropic = Field(exclude=True)
    openai_client: AsyncOpenAI = Field(exclude=True)

    class Config:
        arbitrary_types_allowed = True

    def _run(self, query: str) -> str:
        # LangGraph always calls _arun; _run exists for sync test contexts only.
        return asyncio.run(self._arun(query))

    async def _arun(self, query: str) -> str:
        route = await _route_query(query, self.llm)
        print(f"  [retriever] route={route!r} query={query!r}")

        if route == "exact_lookup":
            result = self.supabase.rpc(
                "exact_search_chunks",
                {"query_text": query, "match_count": _EXACT_CANDIDATES},
            ).execute()
            return _format_results(result.data or [])

        # Semantic path
        rewritten = await _rewrite_query(query, self.llm)
        print(f"  [retriever] rewritten={rewritten!r}")

        embedding_str = await _embed(rewritten, self.openai_client)

        result = self.supabase.rpc(
            "hybrid_search_chunks",
            {
                "query_embedding": embedding_str,
                "query_text": rewritten,
                "match_count": _HYBRID_CANDIDATES,
            },
        ).execute()

        candidates = result.data or []
        reranked = _rerank(query, candidates)
        return _format_results(reranked)
